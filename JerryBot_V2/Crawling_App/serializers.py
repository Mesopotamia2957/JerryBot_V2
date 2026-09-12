from rest_framework import serializers

from .models import Company, JobPosting, Subscriber


class CompanySerializer(serializers.ModelSerializer):
    open_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = ['code', 'name', 'career_url', 'is_active',
                  'last_crawled_at', 'last_crawl_ok', 'open_count']


class JobPostingSerializer(serializers.ModelSerializer):
    company = serializers.CharField(source='company.name', read_only=True)
    company_code = serializers.CharField(source='company.code', read_only=True)

    class Meta:
        model = JobPosting
        fields = ['id', 'company', 'company_code', 'title', 'url',
                  'meta', 'meta_label', 'first_seen_at', 'is_open']


class SubscriberSerializer(serializers.ModelSerializer):
    keywords = serializers.SerializerMethodField()

    class Meta:
        model = Subscriber
        fields = ['slack_user_id', 'display_name', 'notify_enabled', 'keywords']

    def get_keywords(self, obj):
        return obj.keyword_list()
