"""Django 앱 설정.

앱 이름이 'Crawling_App' 이라 테이블 이름도 대소문자가 섞인다("Crawling_App_jobposting").
psql 에서 조회할 때 큰따옴표로 감싸야 한다 — 예: SELECT * FROM "Crawling_App_subscriber";
"""

from django.apps import AppConfig


class CrawlingAppConfig(AppConfig):
    """기본 PK 를 BigAutoField 로. 공고는 계속 쌓이기만 하므로 32비트로는 언젠가 모자란다."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Crawling_App'
