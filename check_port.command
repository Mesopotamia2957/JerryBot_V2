#!/bin/bash
LOG="/Users/bbakjae/PycharmProjects/JerryBot_V2/logs/port_check.log"
{
  echo "=== check $(date) ==="
  echo "--- lsof -i :8000 ---"
  lsof -nP -iTCP:8000 -sTCP:LISTEN
  echo "--- curl 127.0.0.1:8000/api/postings/ ---"
  curl -s -o /dev/null -w "HTTP_STATUS=%{http_code}\n" http://127.0.0.1:8000/api/postings/
  echo "--- curl 0.0.0.0:8080/Crawling_App/ ---"
  curl -s -o /dev/null -w "HTTP_STATUS=%{http_code}\n" http://127.0.0.1:8080/Crawling_App/
} >> "$LOG" 2>&1
