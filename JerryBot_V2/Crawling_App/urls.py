"""Crawling_App 의 URL 목록. 프로젝트 urls.py 가 /api/ 와 /Crawling_App/ 두 곳에 붙인다.

인증 방식이 두 가지로 갈린다.
    subscribers/*, companies/, postings/, <code>/  슬랙봇 전용. X-API-Key 헤더로 지킨다.
    jobs/*                                         사람이 브라우저로 쓴다. 슬랙 세션 쿠키로 지킨다.

맨 아래 <str:code>/ 가 남은 경로를 전부 삼키므로 새 경로는 반드시 그 위에 추가할 것.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('companies/', views.company_list, name='company-list'),
    path('company_list/', views.company_list, name='company-list-legacy'),
    path('postings/', views.posting_list, name='posting-list'),

    path('subscribers/<str:slack_user_id>/', views.subscriber_detail, name='subscriber-detail'),
    path('subscribers/<str:slack_user_id>/keywords/', views.subscriber_keywords, name='subscriber-keywords'),
    path('subscribers/<str:slack_user_id>/matches/', views.subscriber_matches, name='subscriber-matches'),

    # 웹 사용자용(슬랙 세션 쿠키 로그인). /api/jobs/... 로 Caddy 가 crawler-api 에 바로 붙인다.
    # 기업명 catch-all(<str:code>/)보다 반드시 먼저 와야 한다 — 안 그러면 "jobs" 를
    # 기업 코드로 착각해서 company_postings 로 빠진다.
    path('jobs/me/', views.web_me, name='web-me'),
    path('jobs/keywords/', views.web_keywords, name='web-keywords'),
    path('jobs/notify/', views.web_notify_toggle, name='web-notify-toggle'),
    path('jobs/postings/', views.web_postings, name='web-postings'),
    path('jobs/requests/', views.web_crawl_requests, name='web-crawl-requests'),

    # 기업별 조회. 예전 /naver/, /kakao/ 경로와 한글 기업명(/네이버/)을 함께 받는다.
    # 앞의 경로들을 모두 삼키므로 반드시 마지막에 둘 것.
    path('<str:code>/', views.company_postings, name='company-postings'),
]
