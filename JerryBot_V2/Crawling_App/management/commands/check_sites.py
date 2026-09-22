"""사이트별 크롤링이 정상인지 진단한다. DB 에는 쓰지 않는다.

    python manage.py check_sites              # 전체 기업
    python manage.py check_sites -c naver -c line
    python manage.py check_sites --sample 3   # 수집 샘플을 3건씩 출력

셀렉터가 깨졌거나 링크 추출이 실패하면 여기서 드러난다. 크롤링 코드를 고친 뒤
전체 배치를 돌리기 전에 이 명령으로 먼저 확인할 것.
"""

import time

from django.core.management.base import BaseCommand

from Crawling_App.crawler import CrawlError, crawl
from Crawling_App.sites import ENABLED_SITES, SITES, get_spec


class Command(BaseCommand):
    """셀렉터가 아직 유효한지 확인하는 진단 도구. DB 에는 한 글자도 쓰지 않는다.

    채용 사이트는 예고 없이 개편된다. 그러면 크롤링은 "성공"하면서 0건을 가져오거나,
    링크가 전부 같은 주소로 뭉개지는 식으로 조용히 망가진다. 배치 로그만 봐서는
    잘 안 드러나서, 사람이 눈으로 확인할 수 있게 지표를 뽑아 주는 것이 이 명령의 역할이다.

    sites.py 를 고쳤으면 전체 배치를 돌리기 전에 여기부터 통과시킬 것.
    """

    help = '사이트별 크롤링 결과를 진단한다 (DB에 저장하지 않음).'

    def add_arguments(self, parser):
        """--all 은 중단(enabled=False)해 둔 기업까지 검사한다. 복구됐는지 볼 때 쓴다."""
        parser.add_argument('-c', '--company', action='append', default=[],
                            help='기업 코드. 여러 번 지정 가능. 생략하면 전체.')
        parser.add_argument('--sample', type=int, default=1,
                            help='기업마다 출력할 샘플 공고 수 (기본 1).')
        parser.add_argument('--all', action='store_true',
                            help='중단된 기업(enabled=False)까지 함께 검사한다.')

    def handle(self, *args, **options):
        """대상 기업을 정하고 하나씩 진단한 뒤 마지막에 요약을 출력한다."""
        pool = SITES if options['all'] else ENABLED_SITES
        codes = options['company'] or [spec.code for spec in pool]
        results = []

        if not options['company'] and not options['all']:
            skipped = [spec for spec in SITES if not spec.enabled]
            for spec in skipped:
                self.stdout.write(self.style.WARNING(
                    f'- {spec.name} 건너뜀: {spec.disabled_reason} (--all 로 강제 검사)'))

        for code in codes:
            spec = get_spec(code)
            if spec is None:
                self.stderr.write(self.style.ERROR(f'알 수 없는 기업 코드: {code}'))
                continue
            results.append(self._check(spec, options['sample']))

        self._summarize(results)

    def _check(self, spec, sample_size):
        """기업 하나를 실제로 크롤링해 지표를 뽑고 문제를 진단한다.

        수집 건수만 보면 "0건이 아니니 괜찮다"고 착각하기 쉬워서, 고유 링크 수·고유 제목 수·
        부가정보 건수를 같이 낸다. 샘플 공고도 몇 건 찍어 눈으로 확인할 수 있게 한다.
        """
        self.stdout.write(f'\n{"=" * 62}\n{spec.name} ({spec.code})\n{spec.url}')
        started = time.monotonic()

        try:
            rows = crawl(spec)
        except CrawlError as exc:
            elapsed = time.monotonic() - started
            self.stderr.write(self.style.ERROR(f'  ✗ 크롤링 실패 ({elapsed:.1f}초): {exc}'))
            return {'spec': spec, 'ok': False, 'total': 0, 'problems': ['크롤링 실패'], 'elapsed': elapsed}

        elapsed = time.monotonic() - started
        total = len(rows)
        linked = [row for row in rows if row.get('has_link')]
        unique_links = {row['url'] for row in linked}
        unique_titles = {row['title'] for row in rows}
        with_meta = [row for row in rows if row.get('meta')]

        self.stdout.write(f'  수집       {total}건 ({elapsed:.1f}초)')
        self.stdout.write(f'  상세 링크  {len(linked)}건 / 고유 {len(unique_links)}개')
        self.stdout.write(f'  고유 제목  {len(unique_titles)}개')
        self.stdout.write(f'  부가정보   {len(with_meta)}건 ({spec.meta_label})')

        problems = self._diagnose(spec, rows, total, linked, unique_links, unique_titles, with_meta)

        for row in rows[:sample_size]:
            self.stdout.write(f'    · {row["title"][:48]}')
            self.stdout.write(f'      {row["url"][:88]}')
            self.stdout.write(f'      {spec.meta_label}: {row.get("meta") or "(없음)"}')

        if problems:
            for problem in problems:
                self.stderr.write(self.style.WARNING(f'  ⚠ {problem}'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ 이상 없음'))

        return {'spec': spec, 'ok': not problems, 'total': total,
                'problems': problems, 'elapsed': elapsed}

    def _diagnose(self, spec, rows, total, linked, unique_links, unique_titles, with_meta):
        """지표를 보고 "이건 깨진 것" 을 판정해 사람이 읽을 수 있는 문장으로 돌려준다.

        각 규칙은 실제로 겪은 고장에서 나왔다. 특히 '링크가 전부 같은 주소' 는 네이버에서
        href="#" 앵커 때문에 터졌던 건으로, 지문(fingerprint)이 겹쳐 공고 수십 건이 한 건으로
        합쳐졌다. 지금은 크롤러가 막지만 다시 새지 않게 여기서도 계속 본다.

        부가정보를 아예 설정하지 않은 사이트는 정상이므로, 설정했는데 못 뽑을 때만 경고한다.
        """
        problems = []

        if total == 0:
            problems.append(f'수집 0건 — item_selector 가 안 맞을 수 있음: {spec.item_selector}')
            return problems

        if not linked and spec.has_detail_link:
            problems.append('상세 링크를 한 건도 못 뽑음 — 목록 URL로 대체됨. '
                            'link_selector 또는 link_pattern/link_template 확인 필요')
        elif len(unique_links) == 1 and len(linked) > 1:
            # 네이버에서 실제로 터졌던 케이스. 지금은 _usable_link 가 막지만 방어적으로 계속 검사한다.
            problems.append(f'상세 링크 {len(linked)}건이 전부 같은 주소 — '
                            f'href="#" 앵커일 가능성. 지문이 겹쳐 공고가 한 건으로 합쳐진다')
        elif len(unique_links) < len(linked):
            problems.append(f'링크 중복 {len(linked) - len(unique_links)}건 — 같은 공고가 여러 번 잡히는지 확인')

        if len(unique_titles) < total:
            problems.append(f'제목 중복 {total - len(unique_titles)}건')

        # 부가정보를 아예 설정하지 않은 사이트는 정상이다. 설정했는데 못 뽑을 때만 경고한다.
        if not with_meta and (spec.meta_selector or spec.meta_attr):
            problems.append('부가정보를 한 건도 못 뽑음 — meta_selector/meta_attr 확인: '
                            f'{spec.meta_selector or spec.meta_attr}')

        if spec.include_meta and total < 2:
            problems.append(f'include_meta={spec.include_meta} 필터가 너무 좁을 수 있음')

        return problems

    def _summarize(self, results):
        """기업별 한 줄 + 정상/문제 개수. 기업이 여러 곳이면 위쪽 상세 출력이 길어서 필요하다."""
        if not results:
            return

        self.stdout.write(f'\n{"=" * 62}\n요약\n')
        ok = [r for r in results if r['ok']]
        bad = [r for r in results if not r['ok']]

        for result in results:
            mark = '✓' if result['ok'] else '✗'
            style = self.style.SUCCESS if result['ok'] else self.style.ERROR
            line = f'  {mark} {result["spec"].name:12} {result["total"]:4d}건  {result["elapsed"]:5.1f}초'
            if result['problems']:
                line += f'  — {result["problems"][0][:52]}'
            self.stdout.write(style(line))

        total_postings = sum(r['total'] for r in results)
        self.stdout.write(f'\n  정상 {len(ok)}곳 / 문제 {len(bad)}곳 / 총 수집 {total_postings}건')
        if bad:
            self.stdout.write('  문제가 있는 기업: ' + ', '.join(r['spec'].code for r in bad))
