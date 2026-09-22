"""채용공고 크롤러의 도메인 모델 5종.

    Company      크롤링 대상 기업. 정본은 sites.py 코드이고 이 테이블은 그 사본 + 운영 상태다.
    JobPosting   수집한 공고 한 건. 사라지면 지우지 않고 is_open=False 로 닫는다.
    Subscriber   슬랙 사용자 한 명. slack_user_id 가 자금관리(user_mst)와 이어지는 공통 키다.
    Keyword      구독자별 관심 키워드. 소문자로 정규화해 저장한다.
    Notification 이미 보낸 공고 기록. 같은 공고를 두 번 알리지 않게 하는 장치.
    CrawlRequest "이 회사도 크롤링해줘" 요청 게시판.

공고는 지우지 않는 것이 원칙이다. 마감돼도 닫기만 해서 "언제 올라와서 언제 닫혔는지"가 남는다.
"""

import hashlib

from django.db import models
from django.utils import timezone


class Company(models.Model):
    """크롤링 대상 기업. code 는 API 경로와 슬랙 명령어에 함께 쓰인다."""

    code = models.SlugField(max_length=50, unique=True)   # 'naver' 처럼 URL·슬랙 명령어에 그대로 쓰는 식별자
    name = models.CharField(max_length=100)               # 화면·알림에 보이는 이름 ('네이버')
    career_url = models.URLField()                        # 채용 페이지 주소. 크롤링 시작점
    # 코드(sites.py)에 정의가 살아 있는지. sync_companies 가 맞춰 준다. 사람이 끄는 스위치는 paused 쪽이다.
    is_active = models.BooleanField(default=True)
    # 관리자 화면에서 끄는 스위치. is_active 는 코드(sites.py)의 상태를 비추고, paused 는 사람이 정한다.
    paused = models.BooleanField(default=False, verbose_name='일시 중지',
                                 help_text='켜면 배치 크롤링에서 제외한다. 기존 공고는 유지된다.')
    # 마지막 크롤링 결과. 배치가 조용히 실패해도 관리자 화면에서 바로 보이게 남긴다.
    last_crawled_at = models.DateTimeField(null=True, blank=True)
    last_crawl_ok = models.BooleanField(default=True)
    last_crawl_error = models.TextField(blank=True, default='')   # 실패 사유 원문(최대 2000자로 잘라 저장)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name


class JobPostingQuerySet(models.QuerySet):
    """공고 조회에서 반복되는 필터를 모아 둔 곳. JobPosting.objects 가 이걸 쓴다."""

    def open(self):
        """아직 진행 중인 공고만. 마감된 공고도 테이블에는 남아 있어서 매번 걸러야 한다."""
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
    url = models.URLField(max_length=1000)     # 상세 페이지. 못 뽑는 사이트는 목록 URL 이 들어간다
    # 사이트마다 다른 부가 정보(직군·경력·마감일 등). 키워드 매칭은 title 과 이 값을 같이 본다.
    meta = models.CharField(max_length=255, blank=True, default='')
    meta_label = models.CharField(max_length=20, blank=True, default='')   # meta 가 무엇인지 ('경력', '직군')

    # 같은 공고를 다시 수집했을 때 중복 저장을 막는 키
    fingerprint = models.CharField(max_length=64, db_index=True)

    # 마감돼도 행을 지우지 않고 닫기만 한다. 언제 올라와 언제 사라졌는지를 남기기 위해서다.
    is_open = models.BooleanField(default=True)
    first_seen_at = models.DateTimeField(default=timezone.now)   # 처음 수집한 시각 = 공고 피드의 '날짜'
    last_seen_at = models.DateTimeField(default=timezone.now)    # 마지막으로 목록에서 본 시각
    closed_at = models.DateTimeField(null=True, blank=True)      # 목록에서 사라진 것을 확인한 시각

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

    # 슬랙 사용자 ID. 자금관리 user_mst.slack_user_id 와 같은 값이라 두 서비스를 잇는 공통 키가 된다.
    slack_user_id = models.CharField(max_length=50, unique=True)
    # 알림을 보낼 대화방. 비어 있으면 slack_user_id 로 보내고, 그러면 슬랙이 DM 으로 처리한다.
    # 공개 채널 ID 는 일부러 저장하지 않는다(handlers.py) — 개인 알림이 채널에 노출되기 때문.
    slack_channel_id = models.CharField(max_length=50, blank=True, default='')
    display_name = models.CharField(max_length=100, blank=True, default='')
    notify_enabled = models.BooleanField(default=True)   # 끄면 키워드는 남기고 발송만 멈춘다
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['slack_user_id']

    def __str__(self):
        return self.display_name or self.slack_user_id

    def keyword_list(self):
        """이 사람의 키워드를 문자열 리스트로. 매칭·화면·슬랙 응답이 전부 이걸 쓴다."""
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
        """저장 전에 소문자로 정규화한다.

        '백엔드' 와 'Backend' 처럼 대소문자만 다른 키워드가 중복 등록되는 것을 막는다.
        유니크 제약(subscriber, text)이 정규화된 값 기준으로 동작하게 하는 것도 목적이다.
        """
        self.text = self.text.strip().lower()
        super().save(*args, **kwargs)


class CrawlRequest(models.Model):
    """"이 회사도 크롤링해줘" 요청 게시판.

    누구나(로그인한 구독자) 새 기업·페이지를 요청할 수 있고, 관리자가 상태를 바꾸며 처리한다.
    url 을 필수로 받는 이유는 없으면 관리자가 sites.py 에 SiteSpec 을 만들 때 매번 되물어야 하기 때문이다.
    """

    STATUS_CHOICES = [
        ('pending', '대기'),
        ('in_progress', '진행 중'),
        ('done', '완료'),
        ('rejected', '반려'),
    ]

    requester = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name='crawl_requests')
    company_name = models.CharField(max_length=100, verbose_name='기업/사이트 이름')
    url = models.URLField(max_length=1000, verbose_name='채용공고 페이지 주소')
    note = models.TextField(blank=True, default='', verbose_name='요청 메모')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True, default='', verbose_name='관리자 답변')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.company_name} ({self.requester})'


class Notification(models.Model):
    """이미 보낸 공고를 기록해 같은 공고를 두 번 알리지 않도록 한다."""

    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name='notifications')
    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='notifications')
    sent_at = models.DateTimeField(default=timezone.now)
    # UniqueConstraint(subscriber, posting) 가 중복 발송을 DB 차원에서 막는다.
    # 배치가 동시에 두 번 돌아도 ignore_conflicts 로 조용히 넘어간다(notifications.py).

    class Meta:
        ordering = ['-sent_at']
        constraints = [
            models.UniqueConstraint(fields=['subscriber', 'posting'], name='uniq_notification'),
        ]

    def __str__(self):
        return f'{self.subscriber} <- {self.posting_id}'
