"""환경변수로 관리자 계정을 보장한다. 컨테이너 기동 때 호출된다.

    DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD 가 둘 다 있을 때만 동작.
    이미 있는 계정의 비밀번호는 건드리지 않는다(관리자 화면에서 바꾼 값을 덮어쓰지 않도록).
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """컨테이너가 뜰 때마다 관리자 계정이 있는지 확인하고 없으면 만든다.

    entrypoint.sh 가 migrate 직후에 부른다. 매번 실행돼도 안전해야 해서
    '없을 때만 만들고, 있으면 비밀번호를 건드리지 않는' 방식이다 —
    관리자 화면에서 바꾼 비밀번호가 재배포 때 초기화되면 안 되기 때문.
    """

    help = '환경변수 DJANGO_SUPERUSER_* 로 관리자 계정을 만든다(없을 때만).'

    def handle(self, *args, **options):
        """환경변수가 둘 다 있을 때만 동작한다. 하나라도 비면 조용히 건너뛴다."""
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        if not username or not password:
            self.stdout.write('DJANGO_SUPERUSER_USERNAME/PASSWORD 미설정 — 관리자 생성을 건너뜁니다.')
            return
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username, defaults={'is_staff': True, 'is_superuser': True})
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'관리자 계정 생성: {username}'))
        else:
            self.stdout.write(f'관리자 계정 이미 있음: {username} (비밀번호 유지)')
