"""읽기는 전부 DB에서 한다. 크롤링은 crawl_jobs 배치가 따로 돌린다.

예전에는 요청이 들어올 때마다 셀레니움을 띄워 응답이 수십 초 걸렸고,
그래서 '어떤 공고가 새로 올라왔는지'도 알 수 없었다.
"""

from functools import wraps

from django.conf import settings
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import services
from .models import Company, JobPosting
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
    try:
        limit = int(request.query_params.get('limit', DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def _parse_keywords(request):
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
