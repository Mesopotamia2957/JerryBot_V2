"""읽기는 전부 DB에서 한다. 크롤링은 crawl_jobs 배치가 따로 돌린다.

예전에는 요청이 들어올 때마다 셀레니움을 띄워 응답이 수십 초 걸렸고,
그래서 '어떤 공고가 새로 올라왔는지'도 알 수 없었다.
"""

from functools import wraps

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from . import services, webauth
from .models import Company, CrawlRequest, JobPosting, Keyword, Notification, Subscriber
from .serializers import CompanySerializer, JobPostingSerializer, SubscriberSerializer
from .sites import SITES, get_spec

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def require_api_key(view):
    """JERRYBOT_API_KEY 가 설정돼 있을 때만 X-API-Key 헤더를 검사한다."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        expected = getattr(settings, 'JERRYBOT_API_KEY', '')
        if expected and request.headers.get('X-API-Key') != expected:
            return Response({'detail': 'invalid api key'}, status=status.HTTP_401_UNAUTHORIZED)
        return view(request, *args, **kwargs)

    return wrapper


def _parse_limit(request):
    """?limit= 값을 1~MAX_LIMIT 사이로 자른다. 숫자가 아니면 기본값.

    제한을 안 걸면 공고 수천 건이 한 번에 직렬화돼 슬랙 메시지 길이 제한도 넘고 응답도 느려진다.
    """
    try:
        limit = int(request.query_params.get('limit', DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def _parse_keywords(request):
    """?keyword=백엔드,서버 또는 ?keyword=백엔드 서버 를 리스트로 편다.

    쉼표와 공백을 같이 받는 이유는 슬랙에서 사람이 둘 다 쓰기 때문이다.
    """
    raw = request.query_params.get('keyword') or request.query_params.get('keywords') or ''
    return [part for part in (token.strip() for token in raw.replace(',', ' ').split()) if part]


# ---------------------------------------------------------------------------
# 공고 조회
# ---------------------------------------------------------------------------

@api_view(['GET'])
@require_api_key
def company_list(request):
    """지원하는 기업 목록과 각 기업의 진행 중 공고 수."""
    companies = (Company.objects
                 .filter(is_active=True)
                 .annotate(open_count=Count('postings', filter=Q(postings__is_open=True))))
    if not companies.exists():
        # 아직 한 번도 크롤링하지 않은 상태에서도 목록은 보여준다.
        return Response([
            {'code': spec.code, 'name': spec.name, 'career_url': spec.url,
             'is_active': True, 'last_crawled_at': None, 'last_crawl_ok': True, 'open_count': 0}
            for spec in SITES
        ])
    return Response(CompanySerializer(companies, many=True).data)


@api_view(['GET'])
@require_api_key
def posting_list(request):
    """공고 조회. ?company=naver &keyword=백엔드 서버 &limit=50"""
    company_code = request.query_params.get('company')
    if company_code and get_spec(company_code) is None:
        return Response({'detail': f'알 수 없는 기업: {company_code}'}, status=status.HTTP_404_NOT_FOUND)

    queryset = services.list_postings(
        company_code=company_code,
        keywords=_parse_keywords(request),
        only_open=request.query_params.get('include_closed') != '1',
    )
    total = queryset.count()
    postings = queryset[:_parse_limit(request)]
    return Response({
        'count': total,
        'results': JobPostingSerializer(postings, many=True).data,
    })


@api_view(['GET'])
@require_api_key
def company_postings(request, code):
    """기업별 공고. 예전 엔드포인트(/naver/ 등)와 같은 자리를 지킨다."""
    spec = get_spec(code)
    if spec is None:
        return Response({'detail': f'알 수 없는 기업: {code}'}, status=status.HTTP_404_NOT_FOUND)

    postings = services.list_postings(company_code=spec.code, keywords=_parse_keywords(request))
    company = Company.objects.filter(code=spec.code).first()
    return Response({
        'company': spec.name,
        'url': spec.url,
        'last_crawled_at': company.last_crawled_at if company else None,
        'count': postings.count(),
        'results': JobPostingSerializer(postings[:_parse_limit(request)], many=True).data,
    })


# ---------------------------------------------------------------------------
# 구독 (사용자별 키워드)
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@require_api_key
def subscriber_detail(request, slack_user_id):
    """GET 은 구독 정보 조회, POST 는 채널/표시이름/알림 여부 갱신."""
    subscriber, _ = services.get_or_create_subscriber(
        slack_user_id,
        channel_id=request.data.get('channel_id', '') if request.method == 'POST' else '',
        display_name=request.data.get('display_name', '') if request.method == 'POST' else '',
    )
    if request.method == 'POST' and 'notify_enabled' in request.data:
        subscriber.notify_enabled = bool(request.data['notify_enabled'])
        subscriber.save(update_fields=['notify_enabled'])
    return Response(SubscriberSerializer(subscriber).data)


@api_view(['GET', 'POST', 'DELETE'])
@require_api_key
def subscriber_keywords(request, slack_user_id):
    """키워드 조회/추가/삭제. 본문: {"keywords": ["백엔드", "django"]}"""
    subscriber, _ = services.get_or_create_subscriber(
        slack_user_id, channel_id=request.data.get('channel_id', '') if request.data else '',
    )

    if request.method == 'GET':
        return Response({'keywords': subscriber.keyword_list()})

    keywords = request.data.get('keywords') or []
    if isinstance(keywords, str):
        keywords = [keywords]
    if not keywords:
        return Response({'detail': 'keywords 가 비어 있습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'POST':
        added, existing = services.add_keywords(subscriber, keywords)
        return Response({'added': added, 'already': existing, 'keywords': subscriber.keyword_list()})

    removed = services.remove_keywords(subscriber, keywords)
    return Response({'removed': removed, 'keywords': subscriber.keyword_list()})


@api_view(['GET'])
@require_api_key
def subscriber_matches(request, slack_user_id):
    """내 키워드에 맞는 공고 전체(이미 알림받은 것 포함)."""
    subscriber, _ = services.get_or_create_subscriber(slack_user_id)
    keywords = subscriber.keyword_list()
    if not keywords:
        return Response({'keywords': [], 'count': 0, 'results': []})

    queryset = JobPosting.objects.select_related('company').open().matching(keywords)
    return Response({
        'keywords': keywords,
        'count': queryset.count(),
        'results': JobPostingSerializer(queryset[:_parse_limit(request)], many=True).data,
    })


# ---------------------------------------------------------------------------
# 관리자 포털용 상태 요약 (/admin/status.json, 관리자 로그인 필요)
# ---------------------------------------------------------------------------

@staff_member_required
def portal_status(request):
    """관리자 포털 홈이 쓰는 현황 요약(기업·구독자·누적 수치).

    포털은 정적 HTML 이라 DB 를 직접 못 본다. 화면에 필요한 값을 여기서 한 번에 모아 준다.
    staff_member_required 라 로그인 안 하면 로그인 화면으로 넘어가고, 포털은 그 302 를 보고
    '로그인하세요' 안내로 바꿔 보여준다.
    """
    companies = (Company.objects
                 .annotate(open_count=Count('postings', filter=Q(postings__is_open=True)))
                 .order_by('name'))
    subscribers = Subscriber.objects.prefetch_related('keywords').order_by('slack_user_id')
    last_notification = Notification.objects.order_by('-sent_at').values_list('sent_at', flat=True).first()
    return JsonResponse({
        'companies': [{
            'code': c.code, 'name': c.name, 'url': c.career_url,
            'is_active': c.is_active, 'paused': c.paused, 'open_count': c.open_count,
            'last_crawled_at': c.last_crawled_at, 'last_crawl_ok': c.last_crawl_ok,
            'last_crawl_error': (c.last_crawl_error or '')[:120],
        } for c in companies],
        'subscribers': [{
            'slack_user_id': s.slack_user_id, 'display_name': s.display_name,
            'notify_enabled': s.notify_enabled, 'keywords': s.keyword_list(),
        } for s in subscribers],
        'totals': {
            'open_postings': JobPosting.objects.filter(is_open=True).count(),
            'all_postings': JobPosting.objects.count(),
            'keywords': Keyword.objects.count(),
            'notifications': Notification.objects.count(),
        },
        'last_notification_at': last_notification,
    })


# ---------------------------------------------------------------------------
# 웹 사용자용 — 자금관리(finance-api)의 슬랙 로그인 세션을 그대로 읽는다.
#
# 위쪽 뷰들은 X-API-Key(슬랙봇 전용)로 지키지만, 이 아래는 사람이 브라우저로 직접 쓰는
# 화면이라 방식이 다르다. require_web_login 이 finance_session 쿠키에서 슬랙 사용자 ID 를
# 꺼내고, 그 사람의 Subscriber 를 찾아(없으면 새로 만들어) 뷰에 넘긴다.
# ---------------------------------------------------------------------------

def require_web_login(view):
    """finance_session 쿠키로 로그인 여부를 확인하고, Subscriber 를 view 에 넘긴다.

    로그인 안 됐으면 401 + loginUrl 을 준다. 프론트가 이 loginUrl 로 보내면 되므로
    "크롤링" 탭도 자금관리와 똑같은 슬랙 로그인 화면을 그대로 쓸 수 있다.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        slack_user_id = webauth.current_slack_user_id(request)
        if not slack_user_id:
            return Response(
                {"detail": "로그인이 필요합니다", "loginUrl": "/api/auth/login"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        subscriber, _ = services.get_or_create_subscriber(slack_user_id)
        return view(request, subscriber, *args, **kwargs)

    return wrapper


def _crawl_request_row(r):
    """CrawlRequest 한 행을 웹 화면이 쓰는 키 이름(camelCase)으로 바꾼다."""
    return {
        "id": r.id,
        "companyName": r.company_name,
        "url": r.url,
        "note": r.note,
        "status": r.status,
        "statusLabel": r.get_status_display(),
        "adminNote": r.admin_note,
        "createdAt": r.created_at.isoformat(),
        "updatedAt": r.updated_at.isoformat(),
    }


@api_view(["GET"])
@authentication_classes([])  # Caddy basic_auth 헤더와 안 겹치게. 위 설명 참고
@require_web_login
def web_me(request, subscriber):
    """로그인한 사람 정보. 프론트가 화면을 그리기 전에 한 번 부른다."""
    return Response({
        "slackUserId": subscriber.slack_user_id,
        "displayName": subscriber.display_name,
        "notifyEnabled": subscriber.notify_enabled,
        "keywords": subscriber.keyword_list(),
        "isAdmin": webauth.current_is_admin(request),
    })


@api_view(["GET", "POST", "DELETE"])
@authentication_classes([])
@require_web_login
def web_keywords(request, subscriber):
    """내 키워드 조회(GET)·추가(POST)·삭제(DELETE). 본문: {"keywords": ["백엔드", "django"]}"""
    if request.method == "GET":
        return Response({"keywords": subscriber.keyword_list()})

    keywords = request.data.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    if not keywords:
        return Response({"detail": "keywords 가 비어 있습니다."}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "POST":
        added, existing = services.add_keywords(subscriber, keywords)
        return Response({"added": added, "already": existing, "keywords": subscriber.keyword_list()})

    removed = services.remove_keywords(subscriber, keywords)
    return Response({"removed": removed, "keywords": subscriber.keyword_list()})


@api_view(["POST"])
@authentication_classes([])
@require_web_login
def web_notify_toggle(request, subscriber):
    """DM 알림 on/off. 본문: {"enabled": true}"""
    enabled = bool(request.data.get("enabled", True))
    subscriber.notify_enabled = enabled
    subscriber.save(update_fields=["notify_enabled"])
    return Response({"notifyEnabled": subscriber.notify_enabled})


@api_view(["GET"])
@authentication_classes([])
@require_web_login
def web_postings(request, subscriber):
    """공고 피드. 일자별로 묶어서 준다.

    ?mine=1        내 키워드에 맞는 것만 (기본은 전체)
    ?company=코드   특정 기업만
    ?days=14       최근 며칠치 (기본 14, 최대 60)
    """
    try:
        days = max(1, min(int(request.query_params.get("days", 14)), 60))
    except (TypeError, ValueError):
        days = 14
    company_code = request.query_params.get("company") or None
    keywords = subscriber.keyword_list() if request.query_params.get("mine") == "1" else None
    if request.query_params.get("mine") == "1" and not keywords:
        return Response({"days": [], "notice": "등록된 키워드가 없습니다."})

    grouped = services.postings_by_date(company_code=company_code, keywords=keywords, days=days)
    return Response({
        "days": [
            {"date": day, "items": JobPostingSerializer(items, many=True).data}
            for day, items in grouped.items()
        ],
    })


@api_view(["GET", "POST"])
@authentication_classes([])
@require_web_login
def web_crawl_requests(request, subscriber):
    """크롤링 추가 요청 게시판.

    GET  은 내 요청 목록(관리자는 전체).
    POST 는 새 요청. 본문: {"companyName": "...", "url": "https://...", "note": "..."}
    상태 변경(승인/반려 등)은 여기서 하지 않는다 — Django 관리자 화면(/admin/)에서
    jerry 만 처리한다. 처리 결과는 이 목록의 status 로 다시 보인다.
    """
    if request.method == "GET":
        mine_only = not webauth.current_is_admin(request)
        rows = services.list_crawl_requests(subscriber if mine_only else None)
        return Response({"items": [_crawl_request_row(r) for r in rows]})

    company_name = request.data.get("companyName", "")
    url = request.data.get("url", "")
    note = request.data.get("note", "")
    try:
        req = services.create_crawl_request(subscriber, company_name, url, note)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_crawl_request_row(req), status=status.HTTP_201_CREATED)
