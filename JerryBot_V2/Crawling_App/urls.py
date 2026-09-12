from django.urls import path

from . import views

urlpatterns = [
    path('companies/', views.company_list, name='company-list'),
    path('company_list/', views.company_list, name='company-list-legacy'),
    path('postings/', views.posting_list, name='posting-list'),

    path('subscribers/<str:slack_user_id>/', views.subscriber_detail, name='subscriber-detail'),
    path('subscribers/<str:slack_user_id>/keywords/', views.subscriber_keywords, name='subscriber-keywords'),
    path('subscribers/<str:slack_user_id>/matches/', views.subscriber_matches, name='subscriber-matches'),

    # 기업별 조회. 예전 /naver/, /kakao/ 경로와 한글 기업명(/네이버/)을 함께 받는다.
    # 앞의 경로들을 모두 삼키므로 반드시 마지막에 둘 것.
    path('<str:code>/', views.company_postings, name='company-postings'),
]
