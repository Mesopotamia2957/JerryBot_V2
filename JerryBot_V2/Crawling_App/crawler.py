"""사이트 정의(sites.py)를 받아 실제로 크롤링하는 단일 엔진.

기업이 늘어도 여기 코드는 바뀌지 않는다. sites.py 에 SiteSpec 만 추가하면 된다.
"""

import logging
import re
import time
from urllib.parse import urldefrag, urljoin

from django.conf import settings
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .sites import PREPARE_HOOKS

logger = logging.getLogger(__name__)

SCROLL_PAUSE = 1.0
MAX_SCROLLS = 40
ELEMENT_TIMEOUT = 10
PAGE_LOAD_TIMEOUT = 60


class CrawlError(Exception):
    """크롤링이 사이트 단위로 실패했을 때."""


def build_driver(headless=True):
    """셀레니움 크롬 드라이버를 만든다. 컨테이너에서 도는 걸 전제로 옵션이 잡혀 있다.

    이미지는 끄고(속도), 로케일은 ko-KR 로 못박는다. 로케일을 안 박으면 서버(Docker)에
    한국어가 없어서 Accept-Language 가 en 이 되고, 네이버 같은 곳이 영문 페이지만 내려줘
    공고가 몇 건으로 쪼그라든다 — 겉보기엔 'IP 차단'처럼 보여서 한참 헤맸던 부분이다.
    """
    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')            # 컨테이너 환경에서 필요
    options.add_argument('--disable-dev-shm-usage')  # /dev/shm 크기 제한 회피
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--blink-settings=imagesEnabled=false')  # 이미지 미로드로 속도 확보
    # 한국어 로케일이 없는 서버(Docker)에서는 Accept-Language 가 en 이 되어
    # 네이버 등이 영문 페이지(글로벌 공고 몇 건)만 내려준다. 언어를 명시적으로 고정한다.
    options.add_argument('--lang=ko-KR')
    options.add_experimental_option('prefs', {
        'profile.managed_default_content_settings.images': 2,
        'intl.accept_languages': 'ko-KR,ko,en-US,en',
    })
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    user_agent = getattr(settings, 'CRAWLER_USER_AGENT', '')
    if user_agent:
        options.add_argument(f'--user-agent={user_agent}')

    chrome_bin = getattr(settings, 'CHROME_BIN', '')
    if chrome_bin:
        options.binary_location = chrome_bin
    chromedriver = getattr(settings, 'CHROMEDRIVER', '')
    service = Service(executable_path=chromedriver) if chromedriver else None

    driver = webdriver.Chrome(options=options, service=service)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.implicitly_wait(3)
    return driver


def scroll_to_bottom(driver):
    """더 이상 새 내용이 붙지 않을 때까지 아래로 스크롤한다."""
    last_height = driver.execute_script('return document.body.scrollHeight')
    for _ in range(MAX_SCROLLS):
        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(SCROLL_PAUSE)
        height = driver.execute_script('return document.body.scrollHeight')
        if height == last_height:
            return
        last_height = height
    logger.warning('무한 스크롤이 %s회 상한에 도달했습니다.', MAX_SCROLLS)


# 제목을 감싸는 하위 요소가 없어 항목 자신의 텍스트를 써야 하는 사이트용.
# 여러 줄이면 가장 긴 줄을 고른다. '접수중' 같은 상태 배지나 날짜가 같은 요소에
# 섞여 있는 경우가 많은데, 그중 제목이 가장 길다는 점을 이용한다.
SELF = ':self'


def _text_of(item, selector, pick='first'):
    """공고 항목 하나에서 셀렉터로 텍스트를 뽑는다.

    selector 가 SELF 면 항목 전체 텍스트에서 가장 긴 줄을 고른다 — 제목용 셀렉터를 따로
    못 잡는 사이트에서, 보통 제목이 그 항목에서 제일 긴 줄이라는 경험칙을 쓴다.
    pick='last' 는 같은 셀렉터가 여러 개 잡힐 때 마지막 것(주로 갱신일자)을 쓰려는 경우다.
    """
    if not selector:
        return ''
    if selector == SELF:
        lines = [line.strip() for line in item.text.splitlines() if line.strip()]
        return max(lines, key=len) if lines else ''
    elements = item.find_elements(By.CSS_SELECTOR, selector)
    if not elements:
        return ''
    if pick == 'last':
        return elements[-1].text.strip()
    if pick == 'join':
        return ' '.join(el.text.strip() for el in elements if el.text.strip())
    return elements[0].text.strip()


def _usable_link(url, page_url):
    """상세 링크로 쓸 수 있는 주소인지 판정한다.

    href="#n" 처럼 같은 페이지를 가리키는 앵커는 브라우저가 절대 URL로 바꿔주기 때문에
    값이 비어 있지 않다. 이것을 진짜 링크로 취급하면 그 사이트의 공고가 전부 같은 URL이
    되고, URL로 만든 지문이 겹쳐 공고 여러 건이 한 건으로 합쳐진다. (네이버가 이 경우였다.)
    """
    if not url or not url.lower().startswith(('http://', 'https://')):
        return False
    return urldefrag(url).url != urldefrag(page_url).url


ATTR_FIELD = re.compile(r'\{([^}]+)\}')


def _link_from_attrs(item, template):
    """항목의 속성값들로 상세 URL 을 조립한다. 하나라도 비면 포기한다."""
    values = {}
    for name in ATTR_FIELD.findall(template):
        value = item.get_attribute(name)
        if not value:
            return None
        values[name] = value
    url = template
    for name, value in values.items():
        url = url.replace('{' + name + '}', value)
    return url


def _link_of(item, spec):
    """공고 상세 링크와, 그것이 실제 상세 링크인지 여부를 돌려준다.

    링크를 못 찾으면 채용 홈 URL로 대체하되 has_link=False 로 표시한다.
    이 구분이 지문 생성 기준을 바꾸므로(JobPosting.make_fingerprint) 없애지 말 것.
    """
    if spec.link_attr_template:
        built = _link_from_attrs(item, spec.link_attr_template)
        if built:
            return built, True

    element = item
    if spec.link_selector:
        elements = item.find_elements(By.CSS_SELECTOR, spec.link_selector)
        if not elements:
            return spec.url, False
        element = elements[0]

    # onclick="show('30005220')" 처럼 속성값에 든 ID로 상세 URL을 조립해야 하는 사이트.
    # 같은 목록 안에서도 항목마다 구조가 다를 수 있으므로(예: 스크롤로 나중에 붙는 카드)
    # 패턴이 안 맞으면 포기하지 말고 아래의 일반 href 방식으로 넘어간다.
    if spec.link_pattern and spec.link_template:
        raw = element.get_attribute(spec.link_attr) or ''
        match = re.search(spec.link_pattern, raw)
        if match:
            return spec.link_template.format(match.group(1)), True

    href = element.get_attribute('href')
    if not href and element is item:
        anchors = item.find_elements(By.CSS_SELECTOR, 'a')
        if anchors:
            href = anchors[0].get_attribute('href')
    if not href:
        return spec.url, False

    absolute = urljoin(spec.url, href)
    if not _usable_link(absolute, spec.url):
        return spec.url, False
    return absolute, True


def _wanted(item, spec, meta):
    """이 공고를 수집할지 판단한다. 사이트 쪽 필터가 부실할 때 코드에서 한 번 더 거른다.

      require_text  특정 셀렉터의 값이 정확히 일치해야 통과 (예: 상태가 '채용중'인 것만)
      include_meta  meta 에 이 단어들 중 하나라도 있어야 통과 (예: 개발 직군만)

    둘 다 없으면 전부 통과시킨다.
    """
    if spec.require_text:
        selector, expected = spec.require_text
        found = item.find_elements(By.CSS_SELECTOR, selector)
        if not found or found[0].text.strip() != expected:
            return False
    if spec.include_meta and not any(token in meta for token in spec.include_meta):
        return False
    return True


def _collect_page(driver, spec):
    """현재 화면에 보이는 공고를 모두 읽어 리스트로 돌려준다."""
    try:
        WebDriverWait(driver, ELEMENT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, spec.item_selector))
        )
    except TimeoutException:
        logger.warning('[%s] 공고 목록 요소를 찾지 못했습니다: %s', spec.code, spec.item_selector)
        return []

    rows = []
    for item in driver.find_elements(By.CSS_SELECTOR, spec.item_selector):
        try:
            title = _text_of(item, spec.title_selector)
            if not title:
                continue
            if spec.meta_attr:
                meta = (item.get_attribute(spec.meta_attr) or '').strip()
            else:
                meta = _text_of(item, spec.meta_selector, spec.meta_pick)
            # 슬랙 메시지에서 한 줄로 붙으므로 줄바꿈을 정리한다.
            meta = ' · '.join(line.strip() for line in meta.splitlines() if line.strip())
            if not _wanted(item, spec, meta):
                continue
            url, has_link = _link_of(item, spec)
            rows.append({
                'title': title,
                'url': url,
                'has_link': has_link,
                'meta': meta,
                'meta_label': spec.meta_label,
            })
        except StaleElementReferenceException:
            # 스크롤/렌더링 중 DOM이 갈아끼워진 경우. 해당 항목만 건너뛴다.
            continue
        except WebDriverException as exc:
            logger.debug('[%s] 항목 파싱 실패: %s', spec.code, exc)
            continue
    return rows


def _go_next_page(driver, spec):
    """다음 페이지 버튼을 눌러 넘어간다. 더 갈 곳이 없으면 False.

    JS 로 클릭하는 이유는, 버튼이 화면 밖에 있거나 다른 요소에 가려 있으면
    셀레니움의 일반 click() 이 ElementClickIntercepted 로 죽기 때문이다.
    """
    buttons = driver.find_elements(By.CSS_SELECTOR, spec.next_button_selector)
    if not buttons or not buttons[0].is_enabled():
        return False
    try:
        driver.execute_script('arguments[0].click();', buttons[0])
    except WebDriverException:
        return False
    time.sleep(SCROLL_PAUSE)
    return True


def crawl(spec):
    """사이트 하나를 크롤링해 공고 dict 리스트를 돌려준다.

    같은 공고가 여러 번 잡히면 링크(없으면 제목) 기준으로 한 번만 남긴다.
    """
    driver = build_driver(headless=spec.headless)
    collected = {}
    try:
        driver.get(spec.url)
        if spec.initial_wait:
            time.sleep(spec.initial_wait)

        hook = PREPARE_HOOKS.get(spec.prepare) if spec.prepare else None
        if hook:
            try:
                hook(driver)
                time.sleep(SCROLL_PAUSE)
            except (TimeoutException, WebDriverException) as exc:
                # 필터를 못 눌러도 전체 목록은 읽을 수 있으므로 경고만 남기고 진행한다.
                logger.warning('[%s] 사전 필터 적용 실패, 필터 없이 진행합니다: %s', spec.code, exc)

        for page in range(spec.max_pages):
            if spec.infinite_scroll:
                scroll_to_bottom(driver)

            before = len(collected)
            for row in _collect_page(driver, spec):
                collected.setdefault((row['url'], row['title']), row)

            if not spec.next_button_selector:
                break
            if len(collected) == before and page > 0:
                # 다음 버튼은 있는데 새 공고가 없다 → 같은 페이지를 맴돌고 있는 것
                logger.info('[%s] 새 공고가 없어 페이지 순회를 멈춥니다 (page=%s).', spec.code, page + 1)
                break
            if not _go_next_page(driver, spec):
                break
        else:
            logger.warning('[%s] 페이지 상한 %s에 도달했습니다.', spec.code, spec.max_pages)

    except WebDriverException as exc:
        raise CrawlError(f'{spec.name} 크롤링 실패: {exc}') from exc
    finally:
        driver.quit()

    return _drop_shared_links(list(collected.values()), spec)


def _drop_shared_links(rows, spec):
    """공고 전체가 같은 링크를 가리키면 그건 상세 링크가 아니다.

    href="#none" 같은 앵커나 목록 페이지 주소를 상세 링크로 착각하면, URL 로 만든 지문이
    전부 겹쳐 공고 여러 건이 한 건으로 합쳐진다(네이버에서 실제로 터졌던 버그).
    사이트마다 개별 대응하는 대신 여기서 한 번 더 걸러 둔다.
    """
    linked = [row for row in rows if row.get('has_link')]
    if len(linked) > 1 and len({row['url'] for row in linked}) == 1:
        logger.warning('[%s] 공고 %s건의 링크가 모두 같아 상세 링크가 아닌 것으로 처리합니다: %s',
                       spec.code, len(linked), linked[0]['url'])
        for row in linked:
            row['url'] = spec.url
            row['has_link'] = False
    return rows
