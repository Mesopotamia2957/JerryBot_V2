from django.http import JsonResponse, HttpResponse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


import time
import json

SITE_CONFIG = {
        "네이버":
            {
                "url": "https://recruit.navercorp.com/rcrt/list.do?srchClassCd=1000000",
                "item_selector": "li.card_item",
                "title_selector": ".card_title",
                "period_selector": ".info_text"
            },
        "카카오":
            {
                "url": "https://careers.kakao.com/jobs",
                "item_selector": ".list_jobs > a > li",
                "title_selector": "tit_jobs",
                "period_selector": "dl.list_info dd"
            },
        "HL클레무브":
            {
                "url": "https://www.hlklemove.com/recruit/applicant.do",
                "item_selector": ".recruit-board__list .recruit-board__item",
                "title_selector": ".recruit-board__title",
                "period_selector": ".recruit-board__date"
            },
        "스노우":
            {
                "url": "https://recruit.snowcorp.com/rcrt/list.do",
                "item_selector": "li.card_item",
                "title_selector": ".card_title",
                "period_selector": ".info_text"
            },
        "여기어떄":
            {
                "url": "https://gccompany.career.greetinghr.com/",  # 실제 사이트 URL로 대체 필요
                "item_selector": "ul.Flex__FlexCol-sc-uu75bp-1.iKWWXF > a",  # 각 공고에 대한 링크
                "title_selector": "div.Textstyled__Text-sc-55g6e4-0.dYCGQ",  # 공고명
                "category_selector": "span.Textstyled__Text-sc-55g6e4-0.gDzMae"  # 카테고리
            }
    }

def initialize_driver():
    """
    Initialize and return a Selenium WebDriver with specified options.
    """
    options = Options()
    options.add_argument('--headless')  # 헤드리스 모드 활성화
    options.add_argument('--no-sandbox')  # 보안 취약점 노출을 막는 sandbox 비 활성화 (어차피 기업 채용 페이지니까)
    options.add_argument('--disable-dev-shm-usage')  # 공유 메모리 파일 시스템 크기 제한 X

    # 이미지 로드 안함, 대역폭 절약하고 로딩 속도 향상
    options.add_argument('--disable-images')
    options.add_experimental_option("prefs", {'profile.managed_default_content_settings.images': 2})
    options.add_argument('--blink-settings=imagesEnabled=false')

    # 페이지가 완전히 로드되는 것을 기다리지 않음
    caps = DesiredCapabilities.CHROME
    caps["pageLoadStrategy"] = "none"

    options.add_experimental_option("detach", True)  # 화면 꺼짐 방지
    options.add_experimental_option("excludeSwitches", ["enable-logging"])  # 불필요한 에러 메시지 제거
    driver = webdriver.Chrome(options=options)
    return driver


def perform_infinite_scroll(driver: WebDriver):
    """
    Perform an infinite scroll until no more new page content loads.

    Args:
    driver (WebDriver): The Selenium WebDriver instance used for browsing.
    """
    initial_scroll_position = driver.execute_script("return window.scrollY")
    while True:
        driver.find_element(By.CSS_SELECTOR, 'body').send_keys(Keys.END)
        # Wait for page content to load
        time.sleep(2)
        current_scroll_position = driver.execute_script("return window.scrollY")
        if current_scroll_position == initial_scroll_position:
            break
        initial_scroll_position = current_scroll_position


# 네이버
def Naver(request):
    driver = initialize_driver()
    config = SITE_CONFIG["네이버"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
        period = item.find_elements(By.CSS_SELECTOR, config['period_selector'])[-1].text

        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': period})
        else:
            crawled_data['data'].append({'name': name, 'period': period})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# 카카오
def Kakao(request):
    driver = initialize_driver()
    config = SITE_CONFIG["카카오"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    driver.find_element(By.XPATH, "//div[@class='box_select cursor_hand false']").click()
    driver.find_element(By.XPATH, "//ul[@id='companySelect']/li[span/span[text()='전체']]").click()

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        name = item.find_element(By.CLASS_NAME, config['title_selector']).text
        period = item.find_element(By.CSS_SELECTOR, config['period_selector']).text
        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': period})
        else:
            crawled_data['data'].append({'name': name, 'period': period})
    driver.quit()
    return JsonResponse(crawled_data, safe=False)


# HL 클레무브
def Hl_klemove(request):
    driver = initialize_driver()
    config = SITE_CONFIG["HL클레무브"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])
    for item in items:
        is_apply = item.find_elements(By.CSS_SELECTOR, '.recruit-board__dday .day') # 접수중인 공고만 골라내기 위함
        if is_apply and is_apply[0].text.strip() == '접수중':
            name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
            period_elements = item.find_elements(By.CSS_SELECTOR, config['period_selector'])
            period = period_elements[0].text if period_elements else 'No period info'

            if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
                crawled_data['data'].append({'name': name, 'period': period})
            else:
                crawled_data['data'].append({'name': name, 'period': period})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# 스노우
def Snow(request):
    driver = initialize_driver()
    config = SITE_CONFIG["스노우"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
        period = item.find_elements(By.CSS_SELECTOR, config['period_selector'])[-1].text

        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': period})
        else:
            crawled_data['data'].append({'name': name, 'period': period})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# 여기어때
def GccCompany(request):
    driver = initialize_driver()
    config = SITE_CONFIG["여기어떄"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        category_elements = item.find_elements(By.CSS_SELECTOR, config['category_selector'])
        # Check if '개발·데이터' is in any of the category elements
        if any("개발·데이터" in cat.text for cat in category_elements):
            name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
            category = "개발·데이터"

            if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
                crawled_data['data'].append({'name': name, 'period': category})
            else:
                crawled_data['data'].append({'name': name, 'period': category})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)