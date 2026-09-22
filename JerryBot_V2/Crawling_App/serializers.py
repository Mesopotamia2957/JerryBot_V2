"""DRF 직렬화기 — 모델을 슬랙봇·웹 화면이 쓰는 JSON 모양으로 바꾼다.

모델 필드를 그대로 다 내보내지 않는다. 여기 `fields` 에 적힌 것만 나간다 —
fingerprint(중복 판별용 해시)나 last_crawl_error(내부 오류 원문)처럼
바깥에 보일 이유가 없는 값은 일부러 뺐다.
"""

from rest_framework import serializers

from .models import Company, JobPosting, Subscriber


class CompanySerializer(serializers.ModelSerializer):
    """기업 목록용. `!목록` 명령과 포털 현황 화면이 쓴다."""

    # 모델에 없는 값이다. 뷰에서 annotate(Count(...)) 로 붙여 준다.
    open_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = ['code', 'name', 'career_url', 'is_active',
                  'last_crawled_at', 'last_crawl_ok', 'open_count']


class JobPostingSerializer(serializers.ModelSerializer):
    """공고 한 건. 슬랙 메시지와 웹 공고 피드가 같은 모양을 쓴다."""

    # 중첩 객체 대신 이름만 평평하게 펴서 내보낸다. 슬랙 메시지를 만들 때 다루기 쉽다.
    company = serializers.CharField(source='company.name', read_only=True)
    company_code = serializers.CharField(source='company.code', read_only=True)

    class Meta:
        model = JobPosting
        fields = ['id', 'company', 'company_code', 'title', 'url',
                  'meta', 'meta_label', 'first_seen_at', 'is_open']


class SubscriberSerializer(serializers.ModelSerializer):
    """구독자 정보. slack_channel_id 는 내부용이라 내보내지 않는다."""

    keywords = serializers.SerializerMethodField()

    class Meta:
        model = Subscriber
        fields = ['slack_user_id', 'display_name', 'notify_enabled', 'keywords']

    def get_keywords(self, obj):
        """키워드를 ['백엔드', '서버'] 같은 문자열 배열로 펴서 준다."""
        return obj.keyword_list()
