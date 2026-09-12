"""크롤링 결과를 DB에 반영하고, 조회·구독을 다루는 서비스 계층.

뷰는 여기 함수만 호출하고 셀레니움은 직접 건드리지 않는다.
"""

import logging

from django.db import transaction
from django.utils import timezone

from .crawler import CrawlError, crawl
from .models import Company, JobPosting, Keyword, Subscriber
from .sites import SITES, get_spec

logger = logging.getLogger(__name__)


def sync_companies():
    """sites.py 의 정의를 Company 테이블에 반영한다.

    enabled=False 인 기업(사이트 개편·차단 등으로 당분간 못 긁는 곳)은 비활성으로 표시하되
    이미 수집해둔 공고는 지우지 않는다.
    """
    for spec in SITES:
        Company.objects.update_or_create(
            code=spec.code,
            defaults={'name': spec.name, 'career_url': spec.url, 'is_active': spec.enabled},
        )
    # 정의에서 아예 빠진 기업도 크롤링 대상에서 제외하되 과거 공고는 남겨둔다.
    Company.objects.exclude(code__in=[spec.code for spec in SITES]).update(is_active=False)


@transaction.atomic
def store_postings(company, rows):
    """크롤링 결과를 저장하고 (신규 공고, 마감 처리된 수) 를 돌려준다."""
    now = timezone.now()
    new_postings = []
    seen = []

    for row in rows:
        fingerprint = JobPosting.make_fingerprint(row['url'], row['title'], row.get('has_link', True))
        seen.append(fingerprint)
        posting, created = JobPosting.objects.update_or_create(
            company=company,
            fingerprint=fingerprint,
            defaults={
                'title': row['title'],
                'url': row['url'],
                'meta': row.get('meta', ''),
                'meta_label': row.get('meta_label', ''),
                'is_open': True,
                'last_seen_at': now,
                'closed_at': None,
            },
        )
        if created:
            new_postings.append(posting)

    closed = 0
    if seen:
        closed = (JobPosting.objects
                  .filter(company=company, is_open=True)
                  .exclude(fingerprint__in=seen)
                  .update(is_open=False, closed_at=now))

    return new_postings, closed


def crawl_company(code):
    """기업 하나를 크롤링해 DB에 반영한다. 실패해도 예외를 밖으로 던지지 않는다."""
    spec = get_spec(code)
    if spec is None:
        raise ValueError(f'알 수 없는 기업 코드: {code}')

    company, _ = Company.objects.update_or_create(
        code=spec.code,
        defaults={'name': spec.name, 'career_url': spec.url},
    )

    try:
        rows = crawl(spec)
    except CrawlError as exc:
        logger.exception('[%s] 크롤링 실패', spec.code)
        Company.objects.filter(pk=company.pk).update(
            last_crawled_at=timezone.now(), last_crawl_ok=False, last_crawl_error=str(exc)[:2000],
        )
        return {'company': company, 'ok': False, 'error': str(exc), 'total': 0, 'new': [], 'closed': 0}

    new_postings, closed = store_postings(company, rows)
    Company.objects.filter(pk=company.pk).update(
        last_crawled_at=timezone.now(), last_crawl_ok=True, last_crawl_error='',
    )
    return {
        'company': company,
        'ok': True,
        'error': '',
        'total': len(rows),
        'new': new_postings,
        'closed': closed,
    }


# ---------------------------------------------------------------------------
# 조회
# ---------------------------------------------------------------------------

def list_postings(company_code=None, keywords=None, only_open=True, limit=None):
    queryset = JobPosting.objects.select_related('company')
    if only_open:
        queryset = queryset.open()
    if company_code:
        spec = get_spec(company_code)
        queryset = queryset.filter(company__code=spec.code if spec else company_code)
    if keywords:
        queryset = queryset.matching(keywords)
    if limit:
        queryset = queryset[:limit]
    return queryset


# ---------------------------------------------------------------------------
# 구독
# ---------------------------------------------------------------------------

def get_or_create_subscriber(slack_user_id, channel_id='', display_name=''):
    subscriber, created = Subscriber.objects.get_or_create(slack_user_id=slack_user_id)
    changed = False
    if channel_id and subscriber.slack_channel_id != channel_id:
        subscriber.slack_channel_id = channel_id
        changed = True
    if display_name and subscriber.display_name != display_name:
        subscriber.display_name = display_name
        changed = True
    if changed:
        subscriber.save(update_fields=['slack_channel_id', 'display_name'])
    return subscriber, created


def add_keywords(subscriber, texts):
    """키워드를 추가하고 (실제로 추가된 것, 이미 있던 것) 을 돌려준다."""
    added, existing = [], []
    for raw in texts:
        text = raw.strip().lower()
        if not text:
            continue
        _, created = Keyword.objects.get_or_create(subscriber=subscriber, text=text)
        (added if created else existing).append(text)
    return added, existing


def remove_keywords(subscriber, texts):
    wanted = {raw.strip().lower() for raw in texts if raw.strip()}
    if not wanted:
        return []
    removed = list(subscriber.keywords.filter(text__in=wanted).values_list('text', flat=True))
    subscriber.keywords.filter(text__in=wanted).delete()
    return removed
