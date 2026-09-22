"""크롤링 대상 사이트 정의.

사이트를 추가할 때는 SITES 에 SiteSpec 을 한 줄 추가하면 된다.
클릭이 필요한 필터가 있으면 PREPARE_HOOKS 에 함수를 등록하고 spec.prepare 로 연결한다.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@dataclass(frozen=True)
class SiteSpec:
    """사이트 한 곳을 어떻게 긁을지 적어 둔 명세.

    crawler.py 는 이 값만 보고 움직인다. 그래서 기업을 추가할 때 엔진 코드는 건드리지 않고
    아래 SITES 리스트에 SiteSpec 한 줄만 넣으면 된다.

    필드가 많은 이유는 사이트마다 HTML 구조가 제각각이기 때문이다. 대부분은 기본값으로 두고,
    그 사이트에서만 특이한 것들(링크를 못 뽑는다, 필터를 눌러야 한다, 무한스크롤이 아니다 …)만
    지정하면 된다. frozen=True 라 한 번 만들면 못 고친다 — 정의가 런타임에 바뀌는 일이 없게.
    """

    code: str                      # API 경로 / 슬랙 명령어에 쓰이는 식별자
    name: str                      # 사람이 읽는 기업명
    url: str
    item_selector: str             # 공고 한 건을 감싸는 요소
    title_selector: str            # 공고명

    # 마감일이나 직군처럼 제목 옆에 붙여줄 부가 정보
    meta_selector: Optional[str] = None
    meta_label: str = '마감'
    meta_pick: str = 'first'       # first | last | join
    # 텍스트가 아니라 item 의 속성에서 부가정보를 읽어야 하는 사이트용 (예: data-department-slugs)
    meta_attr: Optional[str] = None

    # 공고 링크. None 이면 item 자체의 href, 없으면 item 안의 첫 <a> 를 쓴다.
    link_selector: Optional[str] = None

    # href 가 "#" 앵커라 쓸모없고, onclick 같은 다른 속성에 든 ID로 상세 URL을 조립해야 하는 사이트용.
    # 예: onclick="show('30005220')" -> link_pattern 으로 ID를 뽑아 link_template 에 끼운다.
    link_attr: str = 'href'
    link_pattern: Optional[str] = None
    link_template: Optional[str] = None

    # 상세 URL 을 항목의 여러 속성으로 조립해야 하는 사이트용.
    # 예: 'https://.../applyView.hc?recuYy={data-recuyy}&recuType={data-recutype}'
    # 중괄호 안에는 항목(item)의 속성 이름을 그대로 적는다.
    link_attr_template: Optional[str] = None

    # 공고별 상세 주소가 아예 없는 사이트(클릭하면 모달만 뜨는 경우)는 False.
    # 링크를 못 뽑는 게 정상이므로 check_sites 가 경고하지 않는다.
    has_detail_link: bool = True

    # 항목 필터링
    include_meta: tuple = ()       # meta 에 이 문자열이 있는 공고만 수집
    require_text: Optional[tuple] = None  # (selector, text) 가 일치하는 공고만 수집

    # 페이지 조작
    prepare: Optional[str] = None  # PREPARE_HOOKS 키
    # 공고를 늦게 그리는 사이트용. 페이지를 연 뒤 이 시간만큼 더 기다린다.
    initial_wait: float = 0
    infinite_scroll: bool = True
    next_button_selector: Optional[str] = None
    max_pages: int = 20
    headless: bool = True
    aliases: tuple = field(default=())  # 슬랙에서 함께 받아줄 이름들

    # 사이트가 개편됐거나 접근이 막혀 당분간 못 긁는 경우 False. 정의는 남겨두고 배치에서만 뺀다.
    # 복구되면 True 로 되돌리고 `manage.py check_sites -c <code>` 로 확인할 것.
    enabled: bool = True
    disabled_reason: str = ''


# ---------------------------------------------------------------------------
# 페이지 사전 조작 (필터 클릭 등)
# ---------------------------------------------------------------------------

def _click(driver, by, selector, timeout=10):
    """요소가 클릭 가능해질 때까지 기다렸다가 누른다.

    바로 click() 하면 아직 안 그려졌거나 다른 요소에 가려 있어서 실패하는 일이 잦다.
    prepare 훅들이 공통으로 쓴다.
    """
    WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, selector))).click()


def prepare_kakao(driver):
    """카카오: 공고 목록을 긁기 전에 회사 선택을 '전체'로 바꾼다.

    기본값이 특정 계열사라 그냥 긁으면 일부만 나온다. 드롭다운을 열고 '전체'를 고르는
    두 번의 클릭이 필요하다.
    """
    _click(driver, By.XPATH, "//div[@class='box_select cursor_hand false']")
    _click(driver, By.XPATH, "//ul[@id='companySelect']/li[span/span[text()='전체']]")


PREPARE_HOOKS: dict = {
    'kakao': prepare_kakao,
}


# ---------------------------------------------------------------------------
# 사이트 정의
# ---------------------------------------------------------------------------

# 네이버 계열 채용 페이지(네이버·스노우)는 마크업이 같다.
# 카드의 href 는 "#n" 이라 쓸 수 없고, onclick="show('30005220')" 의 ID로 상세 URL을 만들어야 한다.
# 상세 URL 의 도메인이 다르므로 link_template 은 사이트마다 따로 지정한다.
NAVER_STYLE = dict(
    item_selector='li.card_item',
    title_selector='.card_title',
    meta_selector='.info_text',
    meta_pick='last',
    link_selector='a.card_link',
    link_attr='onclick',
    # 처음 10개는 show('30005189') 이고 스크롤로 추가되는 카드는 show(30005146) 이라
    # 따옴표를 선택적으로 둬야 한다. 안 그러면 앞의 10건만 링크가 붙는다.
    link_pattern=r"show\(['\"]?(\d+)['\"]?\)",
)

# greetinghr 를 쓰는 기업(여기어때·SSG·야놀자·두들린)은 마크업이 같다.
#
# 예전에는 ul.Flex__FlexCol-sc-uu75bp-1.iKWWXF 처럼 빌드할 때 생성되는 해시 클래스를 썼는데,
# 사이트가 재배포되면서 클래스명이 바뀌어 4곳이 한꺼번에 0건이 됐다.
# data-testid / data-variant 는 빌드마다 바뀌지 않으므로 이쪽을 쓴다. 해시 클래스로 되돌리지 말 것.
GREETING_STYLE = dict(
    item_selector='a[data-testid="공고_아이템"]',
    title_selector='span[data-variant="title-01"]',
    meta_selector='span[data-testid^="공고리스트_subtext"]',
    meta_label='직군',
)


SITES = [
    SiteSpec(
        code='naver', name='네이버',
        # 예전에는 ?srchClassCd=1000000 카테고리 필터가 걸려 있어 10건만 수집됐다.
        # 사용자가 키워드로 거르는 구조이므로 수집 단계에서는 전체를 가져온다.
        url='https://recruit.navercorp.com/rcrt/list.do',
        link_template='https://recruit.navercorp.com/rcrt/view.do?annoId={}',
        **NAVER_STYLE,
    ),
    SiteSpec(
        code='kakao', name='카카오',
        url='https://careers.kakao.com/jobs',
        # 링크는 li 를 감싸는 a 에 있으므로 item 을 a 기준으로 잡는다.
        item_selector='.list_jobs > a',
        title_selector='.tit_jobs',
        meta_selector='dl.list_info dd',
        prepare='kakao',
    ),
    SiteSpec(
        code='hl_klemove', name='HL클레무브',
        url='https://www.hlklemove.com/recruit/applicant.do',
        item_selector='.recruit-board__list .recruit-board__item',
        title_selector='.recruit-board__title',
        meta_selector='.recruit-board__date',
        require_text=('.recruit-board__dday .day', '접수중'),
        aliases=('hl클레무브', 'HL클레무브'),
    ),
    SiteSpec(
        code='snow', name='스노우',
        url='https://recruit.snowcorp.com/rcrt/list.do',
        link_template='https://recruit.snowcorp.com/rcrt/view.do?annoId={}',
        **NAVER_STYLE,
    ),
    SiteSpec(
        code='gcccompany', name='여기어때',
        # 루트는 소개 페이지로 바뀌었고 공고 목록은 /ko/apply 로 옮겨갔다.
        url='https://gccompany.career.greetinghr.com/ko/apply',
        # 예전에는 '개발·데이터' 직군만 남겼으나, 사용자가 키워드로 거르므로 전체를 수집한다.
        **GREETING_STYLE,
    ),
    SiteSpec(
        code='musinsa', name='무신사',
        url='https://musinsa.wd3.myworkdayjobs.com/ko-KR/MUSINSA_Careers',
        item_selector='li.css-1q2dra3',
        title_selector='h3 a.css-19uc56f',
        link_selector='h3 a.css-19uc56f',
        meta_selector="div[data-automation-id='postedOn'] dd.css-129m7dg",
        meta_label='등록',
        # Workday 가 점검 중이라(community.workday.com/maintenance-page 로 리다이렉트) 확인 불가.
        # 점검이 끝나면 check_sites 로 셀렉터를 다시 확인할 것. css-* 는 빌드마다 바뀌므로
        # data-automation-id 기반으로 교체하는 편이 안전하다.
        enabled=False,
        disabled_reason='Workday 점검 중 (셀렉터 확인 불가)',
    ),
    SiteSpec(
        code='flex', name='플렉스',
        url='https://flex.careers.team/job-descriptions',
        # 해시 클래스(c-jtvHKu 등) 대신 공고 상세 링크와 data-scope 속성으로 잡는다.
        item_selector='a[href*="/job-descriptions/"]',
        title_selector='span[data-scope="typography"]',
        # 항목 안의 마지막 span 이 고용형태(정규직 등)다. 첫 span 은 제목이라 pick='last' 여야 한다.
        meta_selector='span',
        meta_pick='last',
        meta_label='고용형태',
        # 예전에는 'Product' 필터를 클릭했으나 키워드로 거르므로 전체를 수집한다.
    ),
    SiteSpec(
        code='nexon', name='넥슨',
        # career.nexon.com 은 DNS 자체가 사라졌고, careers.nexon.com 은 봇 차단 페이지
        # ("잠시만 기다리십시오…")를 띄워 헤드리스 브라우저로는 목록에 도달하지 못한다.
        # 차단을 우회하려 하지 말고, 공개 채용 API 나 RSS 가 있는지 먼저 확인할 것.
        url='https://careers.nexon.com/',
        item_selector='div.wrapPostGroup ul li',
        title_selector='dt',
        meta_selector='dd.dueDate',
        next_button_selector='a.page.next:not([disabled])',
        enabled=False,
        disabled_reason='도메인 변경 + 봇 차단 페이지',
    ),
    SiteSpec(
        code='doodlin', name='두들린',
        url='https://www.doodlin.co.kr/ko/career',
        # 예전에는 'Dev' 체크박스를 눌러 직군을 좁혔으나, 사용자가 키워드로 거르는 구조이므로
        # 수집 단계에서는 전체를 가져온다.
        **GREETING_STYLE,
    ),
    SiteSpec(
        code='ssg', name='SSG',
        url='https://ssg.career.greetinghr.com/ko/career',
        **GREETING_STYLE,
    ),
    SiteSpec(
        code='shinsegaeinc', name='신세계아이엔씨',
        url='https://shinsegaeinc.recruiter.co.kr/career/home',
        item_selector='a[href*="/career/jobs/"]',
        # 제목이 링크 자신의 텍스트라 하위 요소가 없다.
        title_selector=':self',
        # 공고 목록을 늦게 그려서 기다리지 않으면 0건으로 잡힌다.
        initial_wait=5,
        # 이 사이트는 href 에 절대 URL 을 통째로 덧붙이는 버그가 있어
        # /career/https://shinsegaeinc.recruiter.co.kr/career/jobs/20175 같은 주소가 나온다.
        # 그래서 href 를 그대로 쓰지 않고 공고 번호만 뽑아 URL 을 다시 만든다.
        link_pattern=r'/career/jobs/(\d+)',
        link_template='https://shinsegaeinc.recruiter.co.kr/career/jobs/{}',
    ),
    SiteSpec(
        code='yanolja', name='야놀자',
        # 사이트가 개편되면서 공고 목록 페이지가 사라졌다. /ko/apply, /ko/career, /ko/jobs,
        # /ko/recruit, /ko/o 를 모두 확인했지만 공고가 없고, 내비게이션에도 채용공고 항목이 없다.
        # 채용을 다른 플랫폼으로 옮긴 것으로 보이므로 목록 URL을 다시 찾아야 한다.
        url='https://careers.yanolja.co/ko/home',
        **GREETING_STYLE,
        enabled=False,
        disabled_reason='공고 목록 페이지를 찾을 수 없음 (사이트 개편)',
    ),
    SiteSpec(
        code='samsung', name='삼성전자',
        # 삼성 관계사 채용을 한곳에 모아 보여주는 페이지다.
        url='https://www.samsungcareers.com/hr/',
        item_selector='a[data-value]',
        title_selector='h3.title',
        meta_selector='span.period',
        # 공고를 누르면 모달이 뜰 뿐 주소가 바뀌지 않아 공고별 링크를 만들 수 없다.
        # href 가 "/#none" 이라 그대로 두면 전 공고가 같은 주소가 되는데,
        # crawler._drop_shared_links 가 이를 걸러 제목 기준으로 식별하게 한다.
        has_detail_link=False,
        aliases=('삼성',),
    ),
    SiteSpec(
        code='hyundai', name='현대자동차',
        url='https://talent.hyundai.com/apply/applyList.hc',
        # 공고 링크가 javascript:void(0) 이지만 부모 li 의 data 속성에 필요한 값이 다 들어 있다.
        item_selector='li[data-recuyy]',
        title_selector='.top strong',
        meta_attr='data-dispdate',
        link_attr_template=('https://talent.hyundai.com/apply/applyView.hc'
                            '?recuYy={data-recuyy}&recuType={data-recutype}'
                            '&recuCls={data-recucls}&ntcGroupNo={data-ntcgroupno}'),
        initial_wait=4,
        # 한 페이지에 10건씩만 나온다(전체 60건). 페이지 번호가 <li class="on"> 로 표시되므로
        # 그 다음 형제가 '다음 페이지' 버튼 역할을 한다. 마지막 페이지에서는 매칭되지 않아 자동으로 멈춘다.
        next_button_selector='ul.list__pages li.on + li',
        aliases=('현대', '현대차'),
    ),
    SiteSpec(
        code='kia', name='기아',
        # recruit.kia.com 은 career.kia.com 으로 넘어간다. 현대자동차와 같은 그룹 채용 시스템이라
        # 공고 li 의 data 속성 구성이 같고, 상세 주소만 .hc -> .kc 로 다르다.
        url='https://career.kia.com/apply/applyList.kc',
        item_selector='li[data-recuyy]',
        title_selector='h3.tit',
        meta_selector='.day__box',
        link_attr_template=('https://career.kia.com/apply/applyView.kc'
                            '?recuYy={data-recuyy}&recuType={data-recutype}'
                            '&recuCls={data-recucls}&ntcGroupNo={data-ntcgroupno}'),
        initial_wait=4,
        # 현재는 9건이라 한 페이지지만, 늘어나면 현대와 같은 페이징이 나타난다.
        next_button_selector='ul.list__pages li.on + li',
    ),
    SiteSpec(
        code='mobis', name='현대모비스',
        # 신세계아이엔씨와 같은 recruiter.co.kr 플랫폼이라 구조가 같다.
        url='https://mobis.recruiter.co.kr/career/jobs',
        item_selector='a[href*="/career/jobs/"]',
        title_selector=':self',
        link_pattern=r'/career/jobs/(\d+)',
        link_template='https://mobis.recruiter.co.kr/career/jobs/{}',
        initial_wait=5,
        aliases=('모비스',),
    ),
    SiteSpec(
        code='line', name='라인',
        url='https://careers.linecorp.com/jobs?ca=Engineering&ci=Seoul,Bundang&co=East%20Asia',
        item_selector='ul.job_list > li',
        title_selector='h3.title',
        meta_selector='span.date',
    ),
    SiteSpec(
        code='daangn', name='당근',
        # about.daangn.com/jobs/ 는 careers.daangn.com/jobs/ 로 리다이렉트된다.
        url='https://careers.daangn.com/jobs/',
        # data-job-card 속성은 빌드마다 바뀌지 않는다. 해시 클래스로 되돌리지 말 것.
        item_selector='[data-job-card]',
        title_selector='h3',
        meta_attr='data-department-slugs',
        meta_label='직군',
    ),
]

SITES_BY_CODE = {spec.code: spec for spec in SITES}

ENABLED_SITES = [spec for spec in SITES if spec.enabled]


def get_spec(code):
    """코드나 별칭(한글 기업명 포함)으로 사이트 정의를 찾는다."""
    if not code:
        return None
    key = code.strip().lower()
    if key in SITES_BY_CODE:
        return SITES_BY_CODE[key]
    for spec in SITES:
        if spec.name.lower() == key or key in {alias.lower() for alias in spec.aliases}:
            return spec
    return None
