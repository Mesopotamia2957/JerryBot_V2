#!/bin/bash
# 채용 사이트를 크롤링하고, 새 공고 중 구독자 키워드에 맞는 것만 슬랙 DM으로 보낸다.
# launchd(com.bbakjae.jerrybot.plist)가 평일 09:00, 18:00 에 실행한다.
# 직접 돌려볼 때도 이 스크립트를 쓰면 launchd 와 같은 조건으로 실행된다.
set -u

PROJECT_DIR="/Users/bbakjae/PycharmProjects/JerryBot_V2"
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG="$PROJECT_DIR/logs/crawl.log"

# launchd 는 최소한의 PATH 로 실행하므로 크롬을 찾을 수 있도록 보강한다.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$PROJECT_DIR/JerryBot_V2"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 시작 =====" >> "$LOG"
"$PYTHON" manage.py crawl_jobs --notify >> "$LOG" 2>&1
STATUS=$?
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 종료 (exit=$STATUS) =====" >> "$LOG"

# 로그가 무한정 커지지 않도록 최근 2000줄만 남긴다.
tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exit $STATUS
