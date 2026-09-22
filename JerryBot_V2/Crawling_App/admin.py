"""관리자 화면. 기업 목록·상태, 구독자 키워드, 공고, 알림 이력을 다룬다.

기업 자체(URL, 셀렉터)는 sites.py 코드가 정본이라 여기서 추가/수정하지 않는다.
여기서는 "일시 중지"와 "지금 크롤링" 같은 운영 동작만 한다.
"""

import os
import subprocess
import sys

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import Company, CrawlRequest, JobPosting, Keyword, Notification, Subscriber
from .sites import get_spec

admin.site.site_header = 'JerryBot 관리'
admin.site.site_title = 'JerryBot 관리'
admin.site.index_title = '채용공고 크롤러'


def spawn_crawl(codes, notify=True):
    """크롤링을 백그라운드 프로세스로 띄운다. 웹 요청 안에서 셀레니움을 돌리면 수 분 걸려 타임아웃이 난다.

    출력은 컨테이너 stdout(/proc/1/fd/1)으로 보내 `docker logs crawler-api` 에서 보이게 한다.
    결과는 Company.last_crawled_at / last_crawl_ok 로 확인한다.
    """
    manage = os.path.join(settings.BASE_DIR, 'manage.py')
    cmd = [sys.executable, manage, 'crawl_jobs']
    for code in codes:
        cmd += ['-c', code]
    if notify:
        cmd.append('--notify')
    try:
        out = open('/proc/1/fd/1', 'ab')
    except OSError:
        out = subprocess.DEVNULL
    return subprocess.Popen(cmd, cwd=settings.BASE_DIR, stdout=out, stderr=subprocess.STDOUT,
                            start_new_session=True)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """기업 목록과 크롤링 상태. 추가/수정은 막고 운영 동작(중지·즉시 크롤링)만 연다.

    기업 정의(URL·셀렉터)의 정본은 sites.py 코드다. 여기서 고치면 다음 sync_companies 때
    코드 값으로 덮어써져 혼란만 생기므로 읽기 전용으로 뒀다.
    """

    list_display = ['name', 'code', 'site_link', 'paused', 'code_status', 'open_count',
                    'last_crawled_at', 'last_crawl_ok', 'error_short']
    list_editable = ['paused']
    list_filter = ['paused', 'is_active', 'last_crawl_ok']
    search_fields = ['name', 'code']
    ordering = ['name']
    fields = ['name', 'code', 'career_url', 'paused', 'code_status',
              'last_crawled_at', 'last_crawl_ok', 'last_crawl_error']
    readonly_fields = ['name', 'code', 'career_url', 'code_status',
                       'last_crawled_at', 'last_crawl_ok', 'last_crawl_error']
    actions = ['crawl_now', 'crawl_now_silent', 'pause', 'resume']

    def has_add_permission(self, request):
        """기업 추가 버튼을 없앤다 — 기업을 늘리는 방법은 sites.py 에 SiteSpec 을 넣는 것이다."""
        return False

    def get_queryset(self, request):
        """목록에 '진행 중 공고 수'를 같이 세어 온다. 행마다 세면 기업 수만큼 쿼리가 나간다."""
        return super().get_queryset(request).annotate(
            open_count=Count('postings', filter=Q(postings__is_open=True)))

    @admin.display(description='채용 페이지')
    def site_link(self, obj):
        """채용 페이지를 새 탭으로 여는 링크. 셀렉터가 깨졌을 때 원본을 바로 보려고 둔다."""
        return format_html('<a href="{}" target="_blank" rel="noopener">열기</a>', obj.career_url)

    @admin.display(description='코드 상태')
    def code_status(self, obj):
        """이 기업이 코드(sites.py)에 살아 있는지 보여준다.

        DB 의 is_active 만 봐서는 '코드에서 뺐다'와 '사이트가 막혔다'를 구분할 수 없어서,
        SiteSpec 을 직접 찾아 사유까지 같이 보여준다.
        """
        spec = get_spec(obj.code)
        if spec is None:
            return '코드에 정의 없음 (배치 제외)'
        if not spec.enabled:
            return f'코드에서 중단: {spec.disabled_reason}'
        return '정상'

    @admin.display(description='진행 중 공고', ordering='open_count')
    def open_count(self, obj):
        """get_queryset 에서 annotate 한 값. 정렬도 그 컬럼으로 된다."""
        return obj.open_count

    @admin.display(description='마지막 오류')
    def error_short(self, obj):
        """목록이 밀리지 않게 오류를 80자만. 전문은 상세 화면에서 본다."""
        return (obj.last_crawl_error or '')[:80]

    @admin.action(description='지금 크롤링 (신규 공고 알림 포함)')
    def crawl_now(self, request, queryset):
        """고른 기업을 지금 크롤링하고, 새 공고가 있으면 구독자에게 알림까지 보낸다.

        응답을 기다리지 않고 백그라운드로 띄운다(spawn_crawl). 결과는 목록의
        '마지막 크롤링' 시각으로 확인한다.
        """
        codes = list(queryset.values_list('code', flat=True))
        spawn_crawl(codes, notify=True)
        self.message_user(request, f'{len(codes)}개 기업 크롤링을 백그라운드로 시작했습니다. '
                                   '1~3분 뒤 새로고침해서 "마지막 크롤링" 시각을 확인하세요.', messages.INFO)

    @admin.action(description='지금 크롤링 (알림 없이 수집만)')
    def crawl_now_silent(self, request, queryset):
        """수집만 하고 알림은 안 보낸다.

        셀렉터를 고친 뒤 제대로 긁히는지 확인할 때처럼, 구독자를 귀찮게 하면 안 되는 상황용.
        """
        codes = list(queryset.values_list('code', flat=True))
        spawn_crawl(codes, notify=False)
        self.message_user(request, f'{len(codes)}개 기업 수집을 백그라운드로 시작했습니다.', messages.INFO)

    @admin.action(description='일시 중지 (배치에서 제외)')
    def pause(self, request, queryset):
        """배치 크롤링에서 뺀다. 이미 수집한 공고는 그대로 둔다."""
        n = queryset.update(paused=True)
        self.message_user(request, f'{n}개 기업을 일시 중지했습니다.')

    @admin.action(description='다시 시작')
    def resume(self, request, queryset):
        """일시 중지를 푼다."""
        n = queryset.update(paused=False)
        self.message_user(request, f'{n}개 기업을 다시 시작했습니다.')


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    """수집된 공고 열람용. 공고는 크롤링 결과라 손으로 만들지 않는다.

    유일한 예외가 '마감 처리' 액션 — 사이트에서는 내려갔는데 크롤러가 아직 못 잡은 공고를
    사람이 직접 닫을 때 쓴다.
    """

    list_display = ['title_link', 'company', 'meta', 'is_open', 'first_seen_at', 'closed_at']
    list_filter = ['is_open', 'company']
    search_fields = ['title', 'meta']
    date_hierarchy = 'first_seen_at'
    ordering = ['-first_seen_at']
    readonly_fields = ['company', 'title', 'url', 'meta', 'meta_label', 'fingerprint',
                       'first_seen_at', 'last_seen_at', 'closed_at']
    actions = ['mark_closed']

    def has_add_permission(self, request):
        """공고는 크롤링 결과라 사람이 만들 일이 없다."""
        return False

    @admin.display(description='공고', ordering='title')
    def title_link(self, obj):
        """제목 자체를 공고 링크로. 목록에서 바로 원문을 열 수 있게."""
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.url, obj.title)

    @admin.action(description='마감 처리')
    def mark_closed(self, request, queryset):
        """사람이 직접 마감 처리한다. 크롤러가 놓친 공고를 손으로 닫을 때 쓴다."""
        from django.utils import timezone
        n = queryset.filter(is_open=True).update(is_open=False, closed_at=timezone.now())
        self.message_user(request, f'{n}건을 마감 처리했습니다.')


class KeywordInline(admin.TabularInline):
    """구독자 화면 안에서 키워드를 바로 편집하게 붙이는 인라인.

    키워드는 항상 '누구의 것'인지와 같이 봐야 의미가 있어서 별도 화면보다 여기가 편하다.
    """

    model = Keyword
    extra = 1
    fields = ['text', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    """구독자와 그 사람의 키워드. 알림 on/off 를 목록에서 바로 바꿀 수 있다."""

    list_display = ['slack_user_id', 'display_name', 'keyword_summary', 'notify_enabled', 'created_at']
    list_editable = ['notify_enabled']
    list_filter = ['notify_enabled']
    search_fields = ['slack_user_id', 'display_name']
    inlines = [KeywordInline]

    @admin.display(description='키워드')
    def keyword_summary(self, obj):
        """목록에서 키워드를 한 줄로 훑어보기 위한 요약."""
        return ', '.join(obj.keyword_list()) or '-'


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    """키워드 전체 목록. '이 단어를 누가 등록했나'를 반대 방향으로 찾을 때 쓴다."""

    list_display = ['text', 'subscriber', 'created_at']
    list_filter = ['subscriber']
    search_fields = ['text']
    ordering = ['subscriber', 'text']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """발송 이력(읽기 전용). '이 공고를 이 사람에게 보냈나'를 확인하는 감사 기록이다.

    여기 행이 있으면 다시 보내지 않으므로, 지우면 같은 공고가 재발송된다.
    """

    list_display = ['sent_at', 'subscriber', 'posting']
    list_filter = ['subscriber']
    date_hierarchy = 'sent_at'
    ordering = ['-sent_at']
    readonly_fields = ['subscriber', 'posting', 'sent_at']

    def has_add_permission(self, request):
        """발송 기록은 배치가 남기는 것이라 손으로 만들지 않는다."""
        return False


def _notify_requester(crawl_request, message):
    """요청 처리 결과를 요청자에게 DM 한다. 실패해도 관리자 작업은 막지 않는다."""
    try:
        from . import notifications
        client = notifications._client()
        channel = crawl_request.requester.slack_channel_id or crawl_request.requester.slack_user_id
        client.chat_postMessage(channel=channel, text=message, unfurl_links=False)
    except Exception:
        pass


@admin.register(CrawlRequest)
class CrawlRequestAdmin(admin.ModelAdmin):
    """크롤링 추가 요청 게시판. 사람은 /api/jobs/requests/ 로 올리고, 처리는 여기서 한다."""

    list_display = ['company_name', 'url_link', 'requester', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['company_name', 'url', 'requester__slack_user_id', 'requester__display_name']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['requester', 'company_name', 'url', 'note', 'created_at', 'updated_at']
    fields = ['requester', 'company_name', 'url', 'note', 'status', 'admin_note', 'created_at', 'updated_at']
    actions = ['mark_in_progress', 'mark_done', 'mark_rejected']

    def has_add_permission(self, request):
        """요청은 사용자가 웹 화면(/api/jobs/requests/)에서 만든다. 관리자는 처리만 한다."""
        return False

    @admin.display(description='채용 페이지')
    def url_link(self, obj):
        """요청자가 낸 채용 페이지를 새 탭으로. 이걸 보고 sites.py 에 SiteSpec 을 만든다."""
        return format_html('<a href="{}" target="_blank" rel="noopener">열기</a>', obj.url)

    @admin.action(description='진행 중으로 변경')
    def mark_in_progress(self, request, queryset):
        """'보고는 있다'는 신호. 요청자 화면의 상태 배지가 바뀐다(DM 은 안 보낸다)."""
        n = queryset.update(status='in_progress')
        self.message_user(request, f'{n}건을 진행 중으로 바꿨습니다.')

    @admin.action(description='완료 처리 (+요청자에게 DM)')
    def mark_done(self, request, queryset):
        """완료 처리 + 요청자에게 DM. sites.py 에 실제로 추가하고 크롤링이 도는 것을 확인한 뒤 누른다.

        DM 이 실패해도 상태 변경은 그대로 진행된다(_notify_requester 가 예외를 삼킨다).
        """
        for req in queryset:
            _notify_requester(req, f'요청하신 "{req.company_name}" 크롤링 추가가 완료됐어요. '
                                    f'!키워드추가 로 키워드를 등록해 두면 새 공고가 올라올 때 알려드려요.')
        n = queryset.update(status='done')
        self.message_user(request, f'{n}건을 완료 처리했습니다.')

    @admin.action(description='반려 처리 (+요청자에게 DM)')
    def mark_rejected(self, request, queryset):
        """반려 처리 + 요청자에게 DM. 사유는 admin_note 에 적어 두면 요청자 화면에 같이 보인다."""
        for req in queryset:
            _notify_requester(req, f'요청하신 "{req.company_name}" 크롤링 추가가 반려됐어요. '
                                    f'사유는 관리자에게 문의해 주세요.')
        n = queryset.update(status='rejected')
        self.message_user(request, f'{n}건을 반려 처리했습니다.')
