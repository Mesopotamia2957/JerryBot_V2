import hashlib

from django.db import models
from django.utils import timezone


class Company(models.Model):
    """크롤링 대상 기업. code 는 API 경로와 슬랙 명령어에 함께 쓰인다."""

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    career_url = models.URLField()
    is_active = models.BooleanField(default=True)
    last_crawled_at = models.DateTimeField(null=True, blank=True)
    last_crawl_ok = models.BooleanField(default=True)
    last_crawl_error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name


class JobPostingQuerySet(models.QuerySet):
    def open(self):
        return self.filter(is_open=True)

    def matching(self, keywords):
        """제목이나 카테고리에 키워드 중 하나라도 포함되면 매칭."""
        if not keywords:
            return self.none()
        query = models.Q()
        for keyword in keywords:
            keyword = keyword.strip()
            if keyword:
                query |= models.Q(title__icontains=keyword) | models.Q(meta__icontains=keyword)
        return self.filter(query) if query else self.none()


class JobPosting(models.Model):
    """크롤링으로 수집한 채용 공고 한 건."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='postings')
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    meta = models.CharField(max_length=255, blank=True, default='')
    meta_label = models.CharField(max_length=20, blank=True, default='')

    # 같은 공고를 다시 수집했을 때 중복 저장을 막는 키
    fingerprint = models.CharField(max_length=64, db_index=True)

    is_open = models.BooleanField(default=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = JobPostingQuerySet.as_manager()

    class Meta:
        ordering = ['-first_seen_at', 'title']
        constraints = [
            models.UniqueConstraint(fields=['company', 'fingerprint'], name='uniq_posting_per_company'),
        ]
        indexes = [
            models.Index(fields=['company', 'is_open']),
            models.Index(fields=['-first_seen_at']),
        ]

    def __str__(self):
        return f'[{self.company.name}] {self.title}'

    @staticmethod
    def make_fingerprint(url, title, has_link=True):
        """동일 공고 판별 기준.

        상세 링크가 있으면 링크로 식별한다(제목이 수정돼도 같은 공고로 본다).
        링크를 못 뽑는 사이트는 모든 공고의 URL이 같으므로 제목으로 식별한다.
        """
        seed = (url or '').strip() if has_link and url else (title or '').strip()
        return hashlib.sha1(seed.encode('utf-8')).hexdigest()


class Subscriber(models.Model):
    """슬랙 사용자 한 명의 구독 상태."""

    slack_user_id = models.CharField(max_length=50, unique=True)
    slack_channel_id = models.CharField(max_length=50, blank=True, default='')
    display_name = models.CharField(max_length=100, blank=True, default='')
    notify_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['slack_user_id']

    def __str__(self):
        return self.display_name or self.slack_user_id

    def keyword_list(self):
        return list(self.keywords.values_list('text', flat=True))


class Keyword(models.Model):
    """구독자가 등록한 관심 키워드. 저장 시 소문자로 정규화한다."""

    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name='keywords')
    text = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['text']
        constraints = [
            models.UniqueConstraint(fields=['subscriber', 'text'], name='uniq_keyword_per_subscriber'),
        ]

    def __str__(self):
        return self.text

    def save(self, *args, **kwargs):
        self.text = self.text.strip().lower()
        super().save(*args, **kwargs)


class Notification(models.Model):
    """이미 보낸 공고를 기록해 같은 공고를 두 번 알리지 않도록 한다."""

    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name='notifications')
    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='notifications')
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-sent_at']
        constraints = [
            models.UniqueConstraint(fields=['subscriber', 'posting'], name='uniq_notification'),
        ]

    def __str__(self):
        return f'{self.subscriber} <- {self.posting_id}'
