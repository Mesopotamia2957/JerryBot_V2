from django.urls import path

from . import views

urlpatterns = [
    path('naver/', views.Naver, name='naver'),
    path('kakao/', views.Kakao, name='kakao'),
    path('hl_klemove/', views.Hl_klemove, name='hl_klemove'),
    path('snow/', views.Snow, name='snow'),
    path('gcccompany/', views.GccCompany, name='gcccompany'),
    path('musinsa/', views.Musinsa, name='musinsa'),
    path('flex/', views.Flex, name='flex'),
    path('nexon/', views.Nexon, name='nexon'),
]