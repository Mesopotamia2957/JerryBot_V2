"""
URL configuration for JerryBot_V2 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from Crawling_App import views

urlpatterns = [
    path("admin/status.json", views.portal_status, name="portal-status"),  # admin/ 보다 먼저
    path("admin/", admin.site.urls),
    path("api/", include('Crawling_App.urls')),
    # 예전 슬랙봇이 쓰던 경로. 새 봇은 /api/ 를 쓴다.
    path("Crawling_App/", include('Crawling_App.urls')),
]