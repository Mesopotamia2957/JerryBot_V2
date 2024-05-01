import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from django.http import JsonResponse, HttpResponse

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
            },
        "MUSINSA":
            {
                "url": "https://musinsa.wd3.myworkdayjobs.com/ko-KR/MUSINSA_Careers/details/IT-Solution_JR0000001255-1?timeType=f3936bc1654610169c62c6d056dd0000&workerSubType=b420f29168e710014992a7ce0ab40000&jobFamilyGroup=770679cb715310017a8f889491da0000&jobFamilyGroup=b420f29168e710016d8808495abe0000&jobFamilyGroup=b420f29168e710016d88023e1a590000",
                "item_selector": "li.css-1q2dra3",  # Jobs list item container
                "title_selector": "h3 a.css-19uc56f",  # Job title
                "posted_selector": "div[data-automation-id='postedOn'] dd.css-129m7dg",  # Posted on information
            },
        "플렉스":
            {
                "url": "https://flex.careers.team/job-descriptions",
                "item_selector": "ul.c-jtvHKu > li.c-kouIyT",
                "title_selector": "div.c-dGcUVj span",
                "period_selector": "div.c-fyTHaI:last-child"
            },
        "넥슨":
            {
                "url": "https://career.nexon.com/user/recruit/member/postList?joinCorp=NX&jobGroupCd=22&reSubj=",
                "item_selector": "div.wrapPostGroup ul li",
                "title_selector": "dt",
                "period_selector": "dd.dueDate"
            },
        "두들린":
            {
                "url": "https://www.doodlin.co.kr/career#3276397a-a988-4ca5-ab47-9aa05e9cce30",
                "item_selector": "ul.Flex__FlexCol-sc-uu75bp-1.iKWWXF > a",  # 각 공고에 대한 링크
                "title_selector": "div.Textstyled__Text-sc-55g6e4-0.dYCGQ",  # 공고명
                "category_selector": "span.Textstyled__Text-sc-55g6e4-0.gDzMae"  # 카테고리
            },
        "SSG":
            {
                "url": "https://ssg.career.greetinghr.com/",
                "item_selector": "ul.Flex__FlexCol-sc-uu75bp-1.iKWWXF > a",  # 각 공고에 대한 링크
                "title_selector": "div.Textstyled__Text-sc-55g6e4-0.dYCGQ",  # 공고명
                "category_selector": "span.Textstyled__Text-sc-55g6e4-0.gDzMae"  # 카테고리
            },
        "신세계아이엔씨":
            {
                "url": "https://shinsegaeinc.recruiter.co.kr/career/home",
                "item_selector": ".RecruitList_list-item__RF9iK",
                "title_selector": ".RecruitList_title__nyhAL",
                "period_selector": ".RecruitList_date__4RH5k p"
            },
        "야놀자":
            {
                "url": "https://careers.yanolja.co/",
                "item_selector": "ul.Flex__FlexCol-sc-uu75bp-1.iKWWXF > a",  # 각 공고에 대한 링크
                "title_selector": "div.Textstyled__Text-sc-55g6e4-0.dYCGQ",  # 공고명
                "category_selector": "span.Textstyled__Text-sc-55g6e4-0.gDzMae"  # 카테고리
            },
        "라인":
            {
                "url": "https://careers.linecorp.com/jobs?ca=Engineering&ci=Seoul,Bundang&co=East%20Asia",
                "item_selector": "ul.job_list > li",
                "title_selector": "h3.title",  # 공고명
                "period_selector": "span.date"  # 기간
            }
    }

# 기업 리스트
def company_list(request):
    company_list = {}
    for List in SITE_CONFIG:
        company_list[List] = SITE_CONFIG[List]['url']
    return JsonResponse(company_list, safe=False)

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
        time.sleep(1)
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

# 무신사
def Musinsa(request):
    driver = initialize_driver()
    config = SITE_CONFIG["MUSINSA"]
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

    # Wait for job items to load
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, config['item_selector'])))
    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
        posted = item.find_element(By.CSS_SELECTOR, config['posted_selector']).text

        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': posted})
        else:
            crawled_data['data'].append({'name': name, 'period': posted})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# 플렉스
def Flex(request):
    driver = initialize_driver()
    config = SITE_CONFIG["플렉스"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//div[@class='c-gEhxKm c-PJLV c-PJLV-oZJzs-size-default c-PJLV-eesTsS-side-right']"))
    ).click()
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'c-jYnSkl') and text()='Product']"))
    ).click()  # Wait for job items to load

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    # Wait for job items to load
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, config['item_selector'])))
    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
        period = item.find_element(By.CSS_SELECTOR, config['period_selector']).text

        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': period})
        else:
            crawled_data['data'].append({'name': name, 'period': period})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# 넥슨
def Nexon(request):
    driver = initialize_driver()
    config = SITE_CONFIG["넥슨"]
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

    try:
        while True:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, config['item_selector']))
            )
            items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

            for item in items:
                name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
                period = item.find_element(By.CSS_SELECTOR, config['period_selector']).text
                crawled_data['data'].append({'name': name, 'period': period})

            # Attempt to find and click the next page button
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "a.page.next:not([disabled])")
                if next_button:
                    next_button.click()
                else:
                    break
            except NoSuchElementException:
                print("Reached the last page.")
                break

    except TimeoutException:
        print("Timeout while loading the page elements.")
    finally:
        driver.quit()

    return JsonResponse(crawled_data, safe=False)

# 두들린
def Doodlin(request):
    driver = initialize_driver()
    config = SITE_CONFIG["두들린"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//label[contains(@class, 'CheckBoxstyled__Layout-sc-') and contains(., 'Dev')]")
        )
    ).click()

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    # Wait for job items to load
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, config['item_selector'])))
    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        category_elements = item.find_elements(By.CSS_SELECTOR, config['category_selector'])
        # Check if '개발·데이터' is in any of the category elements
        name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
        category = item.find_element(By.CSS_SELECTOR, config['category_selector']).text
        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': category})
        else:
            crawled_data['data'].append({'name': name, 'period': category})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# SSG
def SSG(request):
    driver = initialize_driver()
    config = SITE_CONFIG["SSG"]
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

    # Wait for job items to load
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, config['item_selector'])))
    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        category_elements = item.find_elements(By.CSS_SELECTOR, config['category_selector'])
        # Check if '개발·데이터' is in any of the category elements
        name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
        category = item.find_element(By.CSS_SELECTOR, config['category_selector']).text
        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': category})
        else:
            crawled_data['data'].append({'name': name, 'period': category})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# 신세계아이엔씨
def Shinsegaeinc(request):
    options = Options()
    # options.add_argument('--headless')  # 헤드리스 모드 활성화
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
    config = SITE_CONFIG["신세계아이엔씨"]
    driver.get(config["url"])
    time.sleep(1)
    perform_infinite_scroll(driver)

    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.Dropdown_selected-name__j7u3t"))
    ).click()
    time.sleep(1)
    # Select 'IT 서비스' from the dropdown
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//div[@class='List_name__LXyi6' and text()='IT 서비스']"))
    ).click()
    time.sleep(1)
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    try:
        while True:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, config['item_selector']))
            )
            items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

            for item in items:
                name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
                period_elements = item.find_elements(By.CSS_SELECTOR, config['period_selector'])
                period = ' '.join([pe.text for pe in period_elements if pe.text])
                crawled_data['data'].append({'name': name, 'period': period})

            # Check if the next page button is available and not disabled
            next_button_elements = driver.find_elements(By.CSS_SELECTOR,
                                                        "button.Pagination_next__fY4nB:not([disabled])")
            if next_button_elements:
                next_button_elements[0].click()
                time.sleep(0.3)  # Wait for the page to load; adjust time based on actual load time
            else:
                break

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        driver.quit()

    return JsonResponse(crawled_data, safe=False)

# 야놀자
def Yanolja(request):
    driver = initialize_driver()
    config = SITE_CONFIG["야놀자"]
    driver.implicitly_wait(5)
    driver.get(config["url"])
    driver.implicitly_wait(5)

    job_group_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), '직군')]"))
    )
    job_group_button.click()

    # Wait for the dropdown to become visible and select 'R&D'
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//div[contains(@class, 'DropdownItem__Layout-sc-') and .//span[contains(text(), 'R&D')]]"))
    ).click()

    # 무한 스크롤
    perform_infinite_scroll(driver)

    keywords = []
    crawled_data = {
        'url': config["url"],
        'data': []
    }

    # Wait for job items to load
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, config['item_selector'])))
    items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])

    for item in items:
        category_elements = item.find_elements(By.CSS_SELECTOR, config['category_selector'])
        # Check if '개발·데이터' is in any of the category elements
        name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
        category = item.find_element(By.CSS_SELECTOR, config['category_selector']).text
        if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
            crawled_data['data'].append({'name': name, 'period': category})
        else:
            crawled_data['data'].append({'name': name, 'period': category})

    driver.quit()
    return JsonResponse(crawled_data, safe=False)

# 라인
def Line(request):
    driver = initialize_driver()
    config = SITE_CONFIG["라인"]
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
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, config['item_selector']))
        )
        items = driver.find_elements(By.CSS_SELECTOR, config['item_selector'])
        # logging.info(f"Found {len(items)} items.")
        for item in items:
            name = item.find_element(By.CSS_SELECTOR, config['title_selector']).text
            period = item.find_element(By.CSS_SELECTOR, config['period_selector']).text
            # logging.info(f"Crawled item: {name}, {period}")
            if keywords and any(keyword.lower() in name.lower() for keyword in keywords):
                crawled_data['data'].append({'name': name, 'period': period})
            else:
                crawled_data['data'].append({'name': name, 'period': period})
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        driver.quit()
    return JsonResponse(crawled_data, safe=False)