from django.contrib import admin

from .models import Company, JobPosting, Keyword, Notification, Subscriber


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'last_crawled_at', 'last_crawl_ok']
    list_filter = ['is_active', 'last_crawl_ok']
    search_fields = ['name', 'code']


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'meta', 'is_open', 'first_seen_at']
    list_filter = ['is_open', 'company']
    search_fields = ['title', 'meta']
    date_hierarchy = 'first_seen_at'


class KeywordInline(admin.TabularInline):
    model = Keyword
    extra = 1


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ['slack_user_id', 'display_name', 'notify_enabled', 'created_at']
    list_filter = ['notify_enabled']
    search_fields = ['slack_user_id', 'display_name']
    inlines = [KeywordInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['subscriber', 'posting', 'sent_at']
    date_hierarchy = 'sent_at'
