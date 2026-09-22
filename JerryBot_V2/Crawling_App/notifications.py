"""구독자에게 신규 공고를 슬랙으로 알린다.

'무엇을 보낼지'는 여기서 정하고, 실제 전송은 슬랙 Web API 를 쓴다.
이미 보낸 공고는 Notification 에 남겨 두 번 보내지 않는다.
"""

import logging

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import JobPosting, Notification, Subscriber

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_MESSAGE = 20


def pending_postings(subscriber):
    """이 구독자의 키워드에 맞으면서 아직 안 보낸 공개 공고."""
    keywords = subscriber.keyword_list()
    if not keywords:
        return JobPosting.objects.none()
    return (JobPosting.objects
            .select_related('company')
            .open()
            .matching(keywords)
            .exclude(notifications__subscriber=subscriber)
            .order_by('company__name', '-first_seen_at'))


def format_postings(postings, header):
    """슬랙 mrkdwn 으로 공고 목록을 만든다. 제목 자체가 공고 링크가 된다."""
    lines = [header]
    current_company = None
    for posting in postings:
        if posting.company_id != current_company:
            current_company = posting.company_id
            lines.append(f'\n*🏢 {posting.company.name}*')
        meta = f' _({posting.meta_label} {posting.meta})_' if posting.meta else ''
        lines.append(f'• <{posting.url}|{posting.title}>{meta}')
    return '\n'.join(lines)


def _client():
    """슬랙 Web API 클라이언트. 토큰이 없으면 여기서 바로 막는다.

    slack_sdk 를 지연 임포트하는 이유는 크롤링만 돌리는 경우(알림 없이 수집만) 이 의존성이
    필요 없기 때문이다. certifi 를 명시하는 건 셸 설정이 없는 cron/launchd 환경에서
    시스템 인증서를 못 찾아 SSL 검증이 실패하는 것을 막기 위해서다.
    """
    import ssl

    import certifi
    from slack_sdk import WebClient  # 지연 임포트: 크롤링만 돌릴 때는 필요 없다.

    token = getattr(settings, 'SLACK_TOKEN', '')
    if not token:
        raise RuntimeError('SLACK_TOKEN 이 설정되지 않아 알림을 보낼 수 없습니다.')
    # macOS 파이썬은 시스템 인증서를 찾지 못해 SSL 검증에 실패한다
    # (CERTIFICATE_VERIFY_FAILED). certifi 의 CA 번들을 명시해야
    # launchd/cron 처럼 셸 설정이 없는 환경에서도 전송이 된다.
    return WebClient(token=token, ssl=ssl.create_default_context(cafile=certifi.where()))


def _mark_sent(subscriber, postings):
    """전송 완료 기록. 동시에 두 번 돌아도 UniqueConstraint 로 중복이 막힌다."""
    try:
        with transaction.atomic():
            Notification.objects.bulk_create(
                [Notification(subscriber=subscriber, posting=posting) for posting in postings],
                ignore_conflicts=True,
            )
    except IntegrityError:
        logger.warning('알림 기록 저장 중 충돌이 발생했습니다 (subscriber=%s).', subscriber.slack_user_id)


def notify_subscriber(subscriber, client=None, dry_run=False, seed=False):
    """한 구독자에게 신규 공고를 보낸다. 보낸 건수를 돌려준다.

    seed=True 면 전송 없이 '보낸 것으로' 기록만 한다. 최초 도입 시
    기존 공고 수백 건이 한꺼번에 날아가는 것을 막는 용도.
    """
    postings = list(pending_postings(subscriber))
    if not postings:
        return 0

    if seed:
        _mark_sent(subscriber, postings)
        return 0

    channel = subscriber.slack_channel_id or subscriber.slack_user_id
    client = client or _client()

    sent = 0
    for start in range(0, len(postings), MAX_ITEMS_PER_MESSAGE):
        chunk = postings[start:start + MAX_ITEMS_PER_MESSAGE]
        header = f'🔔 등록하신 키워드에 맞는 새 공고 {len(chunk)}건이 올라왔어요.'
        text = format_postings(chunk, header)

        if dry_run:
            logger.info('[dry-run] %s 에게 보낼 내용:\n%s', subscriber.slack_user_id, text)
            sent += len(chunk)
            continue

        try:
            client.chat_postMessage(channel=channel, text=text, unfurl_links=False)
        except Exception:
            # 한 사람 전송이 실패해도 나머지 구독자 처리는 계속한다.
            logger.exception('슬랙 전송 실패 (subscriber=%s)', subscriber.slack_user_id)
            return sent
        _mark_sent(subscriber, chunk)
        sent += len(chunk)

    return sent


def notify_all(dry_run=False, seed=False):
    """알림이 켜진 모든 구독자를 처리하고 요약을 돌려준다."""
    client = None if (dry_run or seed) else _client()
    summary = {}
    for subscriber in Subscriber.objects.filter(notify_enabled=True).prefetch_related('keywords'):
        count = notify_subscriber(subscriber, client=client, dry_run=dry_run, seed=seed)
        if count:
            summary[subscriber.slack_user_id] = count
    return summary
