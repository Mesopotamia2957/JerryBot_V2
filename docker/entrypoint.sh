#!/bin/sh
set -e
cd /app

case "$1" in
  api)
    python manage.py migrate --noinput
    python manage.py ensure_superuser
    exec gunicorn JerryBot_V2.wsgi:application \
      --bind 0.0.0.0:8000 --workers 2 --timeout 60 --access-logfile - --error-logfile -
    ;;
  cron)
    exec /usr/local/bin/supercronic -passthrough-logs /etc/crontab.jerrybot
    ;;
  *)
    exec "$@"
    ;;
esac
