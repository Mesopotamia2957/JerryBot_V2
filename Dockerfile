# JerryBot_V2 — API 서버와 크롤링 배치가 같은 이미지를 쓴다.
#   docker run <img> api    → gunicorn :8000
#   docker run <img> cron   → supercronic (평일 09:00/18:00 crawl_jobs --notify)
#   docker run <img> python manage.py <cmd>   → 임의 관리 명령
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver

# chromium: 셀레니움 크롤링용. 드라이버도 apt 로 같이 받아 버전을 맞춘다.
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium chromium-driver tzdata curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# supercronic: 컨테이너용 cron. 로그가 stdout 으로 나와 docker logs 로 볼 수 있다.
ARG SUPERCRONIC_VERSION=v0.2.33
RUN curl -fsSL -o /usr/local/bin/supercronic \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY JerryBot_V2/ ./
COPY docker/crontab /etc/crontab.jerrybot
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]
