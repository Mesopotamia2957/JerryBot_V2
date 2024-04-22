from django.http import JsonResponse, HttpResponse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

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
            }
    }

def initialize_driver():
    """
    Initialize and return a Selenium WebDriver with specified options.
    """
    options = Options()
    options.add_argument('--headless')  # 헤드리스 모드 활성화
    options.add_argument('--window-size=1920x1080')  # 창 크기 지정
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
