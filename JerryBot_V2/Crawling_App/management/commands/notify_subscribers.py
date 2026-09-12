"""이미 저장된 공고 중 아직 안 보낸 것을 구독자에게 알린다(크롤링 없이).

    python manage.py notify_subscribers
    python manage.py notify_subscribers --dry-run   # 전송 없이 내용만 확인
    python manage.py notify_subscribers --seed      # 기존 공고를 전송 완료로만 기록
"""

from django.core.management.base import BaseCommand

from Crawling_App import notifications


class Command(BaseCommand):
    help = '구독자에게 키워드에 맞는 신규 공고를 슬랙으로 보낸다.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='실제로 보내지 않고 로그만 남긴다.')
        parser.add_argument('--seed', action='store_true',
                            help='전송 없이 현재 공고를 전송 완료로 기록한다(최초 1회).')

    def handle(self, *args, **options):
        summary = notifications.notify_all(dry_run=options['dry_run'], seed=options['seed'])

        if options['seed']:
            self.stdout.write(self.style.SUCCESS('기존 공고를 전송 완료로 기록했습니다.'))
            return

        if not summary:
            self.stdout.write('보낼 알림이 없습니다.')
            return

        for user_id, count in summary.items():
            self.stdout.write(self.style.SUCCESS(f'{user_id} <- {count}건'))
