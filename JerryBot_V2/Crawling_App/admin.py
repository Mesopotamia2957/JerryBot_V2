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

from .models import Company, JobPosting, Keyword, Notification, Subscriber
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
        return False  # 기업 추가는 sites.py 에 SiteSpec 을 넣는 것

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            open_count=Count('postings', filter=Q(postings__is_open=True)))

    @admin.display(description='채용 페이지')
    def site_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">열기</a>', obj.career_url)

    @admin.display(description='코드 상태')
    def code_status(self, obj):
        spec = get_spec(obj.code)
        if spec is None:
            return '코드에 정의 없음 (배치 제외)'
        if not spec.enabled:
            return f'코드에서 중단: {spec.disabled_reason}'
        return '정상'

    @admin.display(description='진행 중 공고', ordering='open_count')
    def open_count(self, obj):
        return obj.open_count

    @admin.display(description='마지막 오류')
    def error_short(self, obj):
        return (obj.last_crawl_error or '')[:80]

    @admin.action(description='지금 크롤링 (신규 공고 알림 포함)')
    def crawl_now(self, request, queryset):
        codes = list(queryset.values_list('code', flat=True))
        spawn_crawl(codes, notify=True)
        self.message_user(request, f'{len(codes)}개 기업 크롤링을 백그라운드로 시작했습니다. '
                                   '1~3분 뒤 새로고침해서 "마지막 크롤링" 시각을 확인하세요.', messages.INFO)

    @admin.action(description='지금 크롤링 (알림 없이 수집만)')
    def crawl_now_silent(self, request, queryset):
        codes = list(queryset.values_list('code', flat=True))
        spawn_crawl(codes, notify=False)
        self.message_user(request, f'{len(codes)}개 기업 수집을 백그라운드로 시작했습니다.', messages.INFO)

    @admin.action(description='일시 중지 (배치에서 제외)')
    def pause(self, request, queryset):
        n = queryset.update(paused=True)
        self.message_user(request, f'{n}개 기업을 일시 중지했습니다.')

    @admin.action(description='다시 시작')
    def resume(self, request, queryset):
        n = queryset.update(paused=False)
        self.message_user(request, f'{n}개 기업을 다시 시작했습니다.')


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ['title_link', 'company', 'meta', 'is_open', 'first_seen_at', 'closed_at']
    list_filter = ['is_open', 'company']
    search_fields = ['title', 'meta']
    date_hierarchy = 'first_seen_at'
    ordering = ['-first_seen_at']
    readonly_fields = ['company', 'title', 'url', 'meta', 'meta_label', 'fingerprint',
                       'first_seen_at', 'last_seen_at', 'closed_at']
    actions = ['mark_closed']

    def has_add_permission(self, request):
        return False  # 공고는 크롤링 결과다

    @admin.display(description='공고', ordering='title')
    def title_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.url, obj.title)

    @admin.action(description='마감 처리')
    def mark_closed(self, request, queryset):
        from django.utils import timezone
        n = queryset.filter(is_open=True).update(is_open=False, closed_at=timezone.now())
        self.message_user(request, f'{n}건을 마감 처리했습니다.')


class KeywordInline(admin.TabularInline):
    model = Keyword
    extra = 1
    fields = ['text', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ['slack_user_id', 'display_name', 'keyword_summary', 'notify_enabled', 'created_at']
    list_editable = ['notify_enabled']
    list_filter = ['notify_enabled']
    search_fields = ['slack_user_id', 'display_name']
    inlines = [KeywordInline]

    @admin.display(description='키워드')
    def keyword_summary(self, obj):
        return ', '.join(obj.keyword_list()) or '-'


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ['text', 'subscriber', 'created_at']
    list_filter = ['subscriber']
    search_fields = ['text']
    ordering = ['subscriber', 'text']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['sent_at', 'subscriber', 'posting']
    list_filter = ['subscriber']
    date_hierarchy = 'sent_at'
    ordering = ['-sent_at']
    readonly_fields = ['subscriber', 'posting', 'sent_at']

    def has_add_permission(self, request):
        return False  # 발송 기록은 배치가 남긴다
