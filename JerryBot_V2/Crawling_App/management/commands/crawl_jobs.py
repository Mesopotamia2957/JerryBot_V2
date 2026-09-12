"""주기적으로 돌리는 크롤링 배치.

    python manage.py crawl_jobs                 # 전체 기업
    python manage.py crawl_jobs -c naver -c line
    python manage.py crawl_jobs --notify        # 크롤링 후 신규 공고 알림까지

cron 예시 (매일 오전 9시, 오후 6시):
    0 9,18 * * * cd /path/to/JerryBot_V2 && .venv/bin/python manage.py crawl_jobs --notify
"""

from django.core.management.base import BaseCommand

from Crawling_App import notifications, services
from Crawling_App.sites import ENABLED_SITES, get_spec


class Command(BaseCommand):
    help = '채용 사이트를 크롤링해 DB에 저장한다.'

    def add_arguments(self, parser):
        parser.add_argument('-c', '--company', action='append', default=[],
                            help='기업 코드. 여러 번 지정 가능. 생략하면 전체.')
        parser.add_argument('--notify', action='store_true',
                            help='크롤링이 끝난 뒤 구독자에게 신규 공고를 알린다.')
        parser.add_argument('--seed-notifications', action='store_true',
                            help='알림을 보내지 않고 현재 공고를 전송 완료로만 기록한다(최초 1회).')

    def handle(self, *args, **options):
        services.sync_companies()

        # 기업을 직접 지정하면 중단된 곳도 돌려본다(복구 확인용).
        codes = options['company'] or [spec.code for spec in ENABLED_SITES]
        total_new = 0

        for spec in (get_spec(code) for code in codes):
            if spec is not None and not spec.enabled:
                self.stdout.write(self.style.WARNING(
                    f'! {spec.name}: 중단된 기업입니다 ({spec.disabled_reason}). 그래도 시도합니다.'))

        for code in codes:
            try:
                result = services.crawl_company(code)
            except ValueError as exc:
                self.stderr.write(self.style.ERROR(str(exc)))
                continue

            name = result['company'].name
            if not result['ok']:
                self.stderr.write(self.style.ERROR(f'✗ {name}: {result["error"]}'))
                continue

            total_new += len(result['new'])
            self.stdout.write(self.style.SUCCESS(
                f'✓ {name}: 수집 {result["total"]}건 / 신규 {len(result["new"])}건 / 마감 {result["closed"]}건'
            ))

        self.stdout.write(f'\n신규 공고 합계: {total_new}건')

        if options['seed_notifications']:
            notifications.notify_all(seed=True)
            self.stdout.write('기존 공고를 전송 완료로 기록했습니다. 다음 실행부터 신규 공고만 알립니다.')
        elif options['notify']:
            summary = notifications.notify_all()
            if summary:
                for user_id, count in summary.items():
                    self.stdout.write(f'  알림 전송: {user_id} <- {count}건')
            else:
                self.stdout.write('  보낼 알림이 없습니다.')
