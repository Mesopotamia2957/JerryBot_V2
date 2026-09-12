"""셀레니움 없이 도는 테스트.

실제 사이트 크롤링이 정상인지는 `manage.py check_sites` 로 확인한다(네트워크 필요).
여기서는 크롤링 결과를 받은 뒤의 저장·판정 로직만 검증하므로 빠르고 항상 같은 결과가 나온다.

    python manage.py test Crawling_App
"""

from unittest.mock import patch

from django.test import TestCase, override_settings

from . import notifications, services
from .crawler import _drop_shared_links, _link_from_attrs, _usable_link
from .models import Company, JobPosting, Notification
from .sites import SITES, get_spec


def row(title, url, has_link=True, meta='상시'):
    """크롤러가 돌려주는 형식의 공고 한 건."""
    return {'title': title, 'url': url, 'has_link': has_link, 'meta': meta, 'meta_label': '마감'}


class _FakeSlack:
    """슬랙 WebClient 대역. 실제 전송 없이 호출을 기록한다."""

    def __init__(self, fail=False):
        self.messages = []
        self.fail = fail

    def chat_postMessage(self, **kwargs):
        if self.fail:
            raise RuntimeError('슬랙 전송 실패 시뮬레이션')
        self.messages.append(kwargs)
        return {'ok': True}


class UsableLinkTests(TestCase):
    """href="#" 앵커를 진짜 링크로 착각하면 공고가 한 건으로 합쳐진다(네이버 버그)."""

    PAGE = 'https://recruit.navercorp.com/rcrt/list.do'

    def test_detail_link_is_usable(self):
        self.assertTrue(_usable_link('https://recruit.navercorp.com/rcrt/view.do?annoId=1', self.PAGE))

    def test_same_page_anchor_is_not_usable(self):
        # 브라우저가 href="#n" 을 절대 주소로 바꿔 넘겨주는 상황
        self.assertFalse(_usable_link(self.PAGE + '#n', self.PAGE))

    def test_page_itself_is_not_usable(self):
        self.assertFalse(_usable_link(self.PAGE, self.PAGE))

    def test_javascript_scheme_is_not_usable(self):
        self.assertFalse(_usable_link("javascript:share('blog','30005220')", self.PAGE))

    def test_empty_is_not_usable(self):
        self.assertFalse(_usable_link('', self.PAGE))
        self.assertFalse(_usable_link(None, self.PAGE))


class _FakeElement:
    """셀레니움 요소 대역. get_attribute 만 흉내낸다."""

    def __init__(self, **attrs):
        self.attrs = attrs

    def get_attribute(self, name):
        return self.attrs.get(name)


class LinkFromAttrsTests(TestCase):
    """현대·기아처럼 상세 주소를 여러 속성으로 조립해야 하는 사이트."""

    TEMPLATE = ('https://talent.hyundai.com/apply/applyView.hc'
                '?recuYy={data-recuyy}&recuType={data-recutype}')

    def test_builds_url_from_attributes(self):
        element = _FakeElement(**{'data-recuyy': '2026', 'data-recutype': 'N2'})
        self.assertEqual(
            _link_from_attrs(element, self.TEMPLATE),
            'https://talent.hyundai.com/apply/applyView.hc?recuYy=2026&recuType=N2')

    def test_missing_attribute_gives_up(self):
        element = _FakeElement(**{'data-recuyy': '2026'})
        self.assertIsNone(_link_from_attrs(element, self.TEMPLATE))

    def test_empty_attribute_gives_up(self):
        element = _FakeElement(**{'data-recuyy': '2026', 'data-recutype': ''})
        self.assertIsNone(_link_from_attrs(element, self.TEMPLATE))


class DropSharedLinksTests(TestCase):
    """공고 전체가 같은 링크면 상세 링크가 아니다 (삼성의 href="/#none" 등)."""

    spec = get_spec('naver')

    def test_all_same_link_is_demoted(self):
        rows = [row('공고 A', 'https://ex.com/#none'), row('공고 B', 'https://ex.com/#none')]
        result = _drop_shared_links(rows, self.spec)

        self.assertTrue(all(not r['has_link'] for r in result))
        self.assertTrue(all(r['url'] == self.spec.url for r in result))

    def test_distinct_links_are_kept(self):
        rows = [row('공고 A', 'https://ex.com/1'), row('공고 B', 'https://ex.com/2')]
        result = _drop_shared_links(rows, self.spec)

        self.assertTrue(all(r['has_link'] for r in result))
        self.assertEqual(result[0]['url'], 'https://ex.com/1')

    def test_single_posting_is_not_demoted(self):
        """공고가 하나뿐이면 링크가 하나인 게 당연하다."""
        rows = [row('공고 A', 'https://ex.com/1')]
        self.assertTrue(_drop_shared_links(rows, self.spec)[0]['has_link'])

    def test_demoted_postings_stay_distinct(self):
        """강등된 뒤에도 제목으로 구분돼 한 건으로 합쳐지지 않아야 한다."""
        company = Company.objects.create(code='samsung', name='삼성전자', career_url=self.spec.url)
        rows = _drop_shared_links(
            [row('공고 A', 'https://ex.com/#none'), row('공고 B', 'https://ex.com/#none')], self.spec)
        new, _ = services.store_postings(company, rows)
        self.assertEqual(len(new), 2)


class FingerprintTests(TestCase):
    def test_link_identifies_posting_when_available(self):
        """링크가 있으면 제목이 바뀌어도 같은 공고로 본다."""
        first = JobPosting.make_fingerprint('https://ex.com/1', '백엔드 개발자', has_link=True)
        second = JobPosting.make_fingerprint('https://ex.com/1', '백엔드 개발자 (경력)', has_link=True)
        self.assertEqual(first, second)

    def test_title_identifies_posting_without_link(self):
        """링크가 없으면 URL이 전부 같으므로 제목으로 구분해야 한다."""
        home = 'https://www.hlklemove.com/recruit/applicant.do'
        first = JobPosting.make_fingerprint(home, '자율주행 SW', has_link=False)
        second = JobPosting.make_fingerprint(home, '영상인식 SW', has_link=False)
        self.assertNotEqual(first, second)


class StorePostingsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code='naver', name='네이버', career_url='https://recruit.navercorp.com/rcrt/list.do')

    def test_first_crawl_creates_all(self):
        new, closed = services.store_postings(self.company, [
            row('백엔드 개발자', 'https://ex.com/1'),
            row('iOS 개발자', 'https://ex.com/2'),
        ])
        self.assertEqual(len(new), 2)
        self.assertEqual(closed, 0)

    def test_same_crawl_twice_creates_nothing(self):
        rows = [row('백엔드 개발자', 'https://ex.com/1')]
        services.store_postings(self.company, rows)
        new, _ = services.store_postings(self.company, rows)
        self.assertEqual(new, [])
        self.assertEqual(JobPosting.objects.count(), 1)

    def test_missing_posting_is_closed(self):
        services.store_postings(self.company, [
            row('백엔드 개발자', 'https://ex.com/1'),
            row('iOS 개발자', 'https://ex.com/2'),
        ])
        new, closed = services.store_postings(self.company, [row('백엔드 개발자', 'https://ex.com/1')])

        self.assertEqual(len(new), 0)
        self.assertEqual(closed, 1)
        gone = JobPosting.objects.get(title='iOS 개발자')
        self.assertFalse(gone.is_open)
        self.assertIsNotNone(gone.closed_at)

    def test_reopened_posting_clears_closed_at(self):
        services.store_postings(self.company, [row('백엔드 개발자', 'https://ex.com/1')])
        JobPosting.objects.all().update(is_open=False)
        services.store_postings(self.company, [row('백엔드 개발자', 'https://ex.com/1')])

        posting = JobPosting.objects.get(title='백엔드 개발자')
        self.assertTrue(posting.is_open)
        self.assertIsNone(posting.closed_at)

    def test_postings_without_links_are_not_merged(self):
        """네이버에서 10건이 1건으로 합쳐졌던 버그의 회귀 테스트."""
        home = self.company.career_url
        new, _ = services.store_postings(self.company, [
            row('백엔드 개발자', home, has_link=False),
            row('iOS 개발자', home, has_link=False),
            row('데이터 엔지니어', home, has_link=False),
        ])
        self.assertEqual(len(new), 3)
        self.assertEqual(JobPosting.objects.open().count(), 3)

    def test_empty_crawl_does_not_close_everything(self):
        """크롤링이 빈 결과를 주면(셀렉터 깨짐 등) 기존 공고를 마감시키지 않는다."""
        services.store_postings(self.company, [row('백엔드 개발자', 'https://ex.com/1')])
        new, closed = services.store_postings(self.company, [])

        self.assertEqual(closed, 0)
        self.assertTrue(JobPosting.objects.get(title='백엔드 개발자').is_open)


class KeywordMatchingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code='naver', name='네이버', career_url='https://ex.com')
        services.store_postings(self.company, [
            row('백엔드 개발자 (Java)', 'https://ex.com/1'),
            row('iOS 개발자', 'https://ex.com/2'),
            row('데이터 엔지니어', 'https://ex.com/3', meta='개발·데이터'),
        ])

    def test_matches_title(self):
        self.assertEqual(JobPosting.objects.open().matching(['백엔드']).count(), 1)

    def test_matching_is_case_insensitive(self):
        self.assertEqual(JobPosting.objects.open().matching(['java']).count(), 1)

    def test_matches_meta(self):
        self.assertEqual(JobPosting.objects.open().matching(['개발·데이터']).count(), 1)

    def test_multiple_keywords_are_or(self):
        self.assertEqual(JobPosting.objects.open().matching(['백엔드', 'ios']).count(), 2)

    def test_no_keywords_matches_nothing(self):
        self.assertEqual(JobPosting.objects.open().matching([]).count(), 0)

    def test_closed_postings_are_excluded(self):
        JobPosting.objects.filter(title='iOS 개발자').update(is_open=False)
        self.assertEqual(JobPosting.objects.open().matching(['ios']).count(), 0)


class SubscriberTests(TestCase):
    def test_keywords_are_normalized_to_lowercase(self):
        subscriber, _ = services.get_or_create_subscriber('U1')
        added, existing = services.add_keywords(subscriber, ['Django', 'BACKEND'])
        self.assertEqual(sorted(added), ['backend', 'django'])
        self.assertEqual(existing, [])

    def test_duplicate_keyword_is_reported_not_duplicated(self):
        subscriber, _ = services.get_or_create_subscriber('U1')
        services.add_keywords(subscriber, ['백엔드'])
        added, existing = services.add_keywords(subscriber, ['백엔드'])

        self.assertEqual(added, [])
        self.assertEqual(existing, ['백엔드'])
        self.assertEqual(subscriber.keywords.count(), 1)

    def test_remove_keyword(self):
        subscriber, _ = services.get_or_create_subscriber('U1')
        services.add_keywords(subscriber, ['백엔드', 'django'])
        removed = services.remove_keywords(subscriber, ['DJANGO'])

        self.assertEqual(removed, ['django'])
        self.assertEqual(subscriber.keyword_list(), ['백엔드'])

    def test_channel_id_is_updated(self):
        services.get_or_create_subscriber('U1')
        subscriber, created = services.get_or_create_subscriber('U1', channel_id='D1', display_name='재열')

        self.assertFalse(created)
        self.assertEqual(subscriber.slack_channel_id, 'D1')
        self.assertEqual(subscriber.display_name, '재열')


class NotificationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code='naver', name='네이버', career_url='https://ex.com')
        services.store_postings(self.company, [
            row('백엔드 개발자', 'https://ex.com/1'),
            row('iOS 개발자', 'https://ex.com/2'),
        ])
        self.subscriber, _ = services.get_or_create_subscriber('U1', channel_id='D1')
        services.add_keywords(self.subscriber, ['백엔드'])

    def test_only_matching_postings_are_pending(self):
        pending = list(notifications.pending_postings(self.subscriber))
        self.assertEqual([p.title for p in pending], ['백엔드 개발자'])

    def test_subscriber_without_keywords_gets_nothing(self):
        other, _ = services.get_or_create_subscriber('U2')
        self.assertEqual(notifications.pending_postings(other).count(), 0)

    def test_seed_marks_sent_without_sending(self):
        sent = notifications.notify_subscriber(self.subscriber, seed=True)
        self.assertEqual(sent, 0)
        self.assertEqual(notifications.pending_postings(self.subscriber).count(), 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_posting_is_not_sent_twice(self):
        client = _FakeSlack()
        first = notifications.notify_subscriber(self.subscriber, client=client)
        second = notifications.notify_subscriber(self.subscriber, client=client)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(len(client.messages), 1)

    def test_new_matching_posting_is_sent_later(self):
        client = _FakeSlack()
        notifications.notify_subscriber(self.subscriber, client=client)
        services.store_postings(self.company, [
            row('백엔드 개발자', 'https://ex.com/1'),
            row('iOS 개발자', 'https://ex.com/2'),
            row('백엔드 개발자 (신규)', 'https://ex.com/3'),
        ])
        sent = notifications.notify_subscriber(self.subscriber, client=client)

        self.assertEqual(sent, 1)
        self.assertIn('백엔드 개발자 (신규)', client.messages[-1]['text'])

    def test_message_contains_clickable_link(self):
        client = _FakeSlack()
        notifications.notify_subscriber(self.subscriber, client=client)
        self.assertIn('<https://ex.com/1|백엔드 개발자>', client.messages[0]['text'])

    def test_dm_channel_is_used(self):
        client = _FakeSlack()
        notifications.notify_subscriber(self.subscriber, client=client)
        self.assertEqual(client.messages[0]['channel'], 'D1')

    def test_send_failure_does_not_mark_as_sent(self):
        """전송이 실패했는데 보낸 것으로 기록하면 그 공고는 영영 안 나간다."""
        client = _FakeSlack(fail=True)
        sent = notifications.notify_subscriber(self.subscriber, client=client)

        self.assertEqual(sent, 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(notifications.pending_postings(self.subscriber).count(), 1)

    def test_notify_all_skips_disabled_subscribers(self):
        self.subscriber.notify_enabled = False
        self.subscriber.save(update_fields=['notify_enabled'])
        with patch.object(notifications, '_client', return_value=_FakeSlack()):
            summary = notifications.notify_all()
        self.assertEqual(summary, {})


class SlackClientTests(TestCase):
    def test_client_uses_explicit_ca_bundle(self):
        """macOS 파이썬은 시스템 인증서를 못 찾아 슬랙 전송이 SSL 오류로 실패한다.

        certifi CA 번들을 명시하지 않으면 launchd/cron 에서 알림이 조용히 안 나간다.
        실제로 이 문제로 예약 실행이 전송에 실패했었다.
        """
        with override_settings(SLACK_TOKEN='xoxb-test-token'):
            client = notifications._client()
        self.assertIsNotNone(client.ssl, 'WebClient 에 ssl 컨텍스트가 지정돼 있어야 한다')

    def test_missing_token_fails_loudly(self):
        with override_settings(SLACK_TOKEN=''):
            with self.assertRaises(RuntimeError):
                notifications._client()


class SiteSpecTests(TestCase):
    def test_codes_are_unique(self):
        codes = [spec.code for spec in SITES]
        self.assertEqual(len(codes), len(set(codes)))

    def test_lookup_by_code(self):
        self.assertEqual(get_spec('naver').name, '네이버')

    def test_lookup_by_korean_name(self):
        self.assertEqual(get_spec('여기어때').code, 'gcccompany')

    def test_lookup_by_alias(self):
        self.assertEqual(get_spec('hl클레무브').code, 'hl_klemove')

    def test_unknown_returns_none(self):
        self.assertIsNone(get_spec('없는회사'))
        self.assertIsNone(get_spec(''))

    def test_link_template_present_when_pattern_used(self):
        """link_pattern 만 있고 template 이 없으면 링크를 못 만든다."""
        for spec in SITES:
            if spec.link_pattern:
                self.assertIsNotNone(spec.link_template, f'{spec.code}: link_template 누락')


class ApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code='naver', name='네이버', career_url='https://ex.com')
        services.store_postings(self.company, [row('백엔드 개발자', 'https://ex.com/1')])

    def test_company_list(self):
        response = self.client.get('/api/companies/')
        self.assertEqual(response.status_code, 200)

    def test_company_postings_include_url(self):
        response = self.client.get('/api/naver/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['url'], 'https://ex.com/1')

    def test_unknown_company_returns_404(self):
        self.assertEqual(self.client.get('/api/없는회사/').status_code, 404)

    def test_korean_company_name_in_path(self):
        self.assertEqual(self.client.get('/api/네이버/').status_code, 200)

    def test_keyword_search(self):
        response = self.client.get('/api/postings/?keyword=백엔드')
        self.assertEqual(response.json()['count'], 1)

    def test_add_and_remove_keywords(self):
        added = self.client.post('/api/subscribers/U1/keywords/',
                                 {'keywords': ['백엔드']}, content_type='application/json')
        self.assertEqual(added.json()['added'], ['백엔드'])

        removed = self.client.delete('/api/subscribers/U1/keywords/',
                                     {'keywords': ['백엔드']}, content_type='application/json')
        self.assertEqual(removed.json()['keywords'], [])

    def test_empty_keywords_rejected(self):
        response = self.client.post('/api/subscribers/U1/keywords/',
                                    {'keywords': []}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_matches_endpoint(self):
        self.client.post('/api/subscribers/U1/keywords/',
                         {'keywords': ['백엔드']}, content_type='application/json')
        response = self.client.get('/api/subscribers/U1/matches/')
        self.assertEqual(response.json()['count'], 1)

    def test_legacy_path_still_works(self):
        self.assertEqual(self.client.get('/Crawling_App/naver/').status_code, 200)


class AdminOpsTests(TestCase):
    """관리자 화면의 운영 동작: 일시 중지, 즉시 크롤링, 포털 상태."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        self.admin = get_user_model().objects.create_superuser('admin', 'a@b.c', 'pw')
        self.client.force_login(self.admin)

    def _fake_result(self, code):
        company, _ = Company.objects.get_or_create(code=code, defaults={'name': code, 'career_url': 'https://ex.com'})
        return {'company': company, 'ok': True, 'error': '', 'total': 0, 'new': [], 'closed': 0}

    def test_crawl_jobs_skips_paused_companies(self):
        from django.core.management import call_command
        services.sync_companies()
        Company.objects.filter(code='naver').update(paused=True)
        with patch('Crawling_App.services.crawl_company', side_effect=self._fake_result) as crawl:
            call_command('crawl_jobs', verbosity=0)
        crawled = {call.args[0] for call in crawl.call_args_list}
        self.assertNotIn('naver', crawled)
        self.assertIn('kakao', crawled)

    def test_explicit_company_ignores_pause(self):
        from django.core.management import call_command
        services.sync_companies()
        Company.objects.filter(code='naver').update(paused=True)
        with patch('Crawling_App.services.crawl_company', side_effect=self._fake_result) as crawl:
            call_command('crawl_jobs', company=['naver'], verbosity=0)
        self.assertEqual([c.args[0] for c in crawl.call_args_list], ['naver'])

    def test_sync_companies_keeps_pause(self):
        services.sync_companies()
        Company.objects.filter(code='naver').update(paused=True)
        services.sync_companies()
        self.assertTrue(Company.objects.get(code='naver').paused)

    def test_crawl_now_action_spawns_background_process(self):
        services.sync_companies()
        ids = list(Company.objects.filter(code__in=['naver', 'kakao']).values_list('pk', flat=True))
        with patch('Crawling_App.admin.subprocess.Popen') as popen:
            response = self.client.post('/admin/Crawling_App/company/',
                                        {'action': 'crawl_now', '_selected_action': ids}, follow=True)
        self.assertEqual(response.status_code, 200)
        popen.assert_called_once()
        cmd = popen.call_args.args[0]
        self.assertIn('crawl_jobs', cmd)
        self.assertIn('--notify', cmd)
        self.assertEqual(cmd.count('-c'), 2)

    def test_portal_status_requires_staff(self):
        self.client.logout()
        response = self.client.get('/admin/status.json')
        self.assertEqual(response.status_code, 302)

    def test_portal_status_summarises(self):
        company = Company.objects.create(code='naver', name='네이버', career_url='https://ex.com')
        services.store_postings(company, [row('백엔드 개발자', 'https://ex.com/1')])
        subscriber, _ = services.get_or_create_subscriber('U1')
        services.add_keywords(subscriber, ['백엔드'])
        data = self.client.get('/admin/status.json').json()
        self.assertEqual(data['totals']['open_postings'], 1)
        self.assertEqual(data['companies'][0]['open_count'], 1)
        self.assertEqual(data['subscribers'][0]['keywords'], ['백엔드'])

    def test_admin_changelists_render(self):
        services.sync_companies()
        for path in ['/admin/', '/admin/Crawling_App/company/', '/admin/Crawling_App/jobposting/',
                     '/admin/Crawling_App/subscriber/', '/admin/Crawling_App/keyword/',
                     '/admin/Crawling_App/notification/']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
