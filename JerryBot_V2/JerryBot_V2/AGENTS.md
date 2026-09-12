<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-03 | Updated: 2026-08-03 -->

# JerryBot_V2 (설정 패키지)

## Purpose

Django 프로젝트 전역 설정. 기능 코드는 없고 설정·URL 라우팅·WSGI/ASGI 진입점만 있다.

## Key Files

| File | Description |
|------|-------------|
| `settings.py` | 전역 설정. 비밀값은 전부 `python-decouple` 의 `config()` 로 `.env` 에서 읽는다 |
| `urls.py` | 최상위 URL 라우팅. `/admin/`, `/api/`, `/Crawling_App/` 세 갈래 |
| `wsgi.py` | 동기 배포용 진입점 (gunicorn 등) |
| `asgi.py` | 비동기 배포용 진입점 |
| `__init__.py` | 패키지 선언 |

## For AI Agents

### Working In This Directory

- **비밀값을 하드코딩하지 말 것.** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `SLACK_TOKEN`,
  `JERRYBOT_API_KEY` 는 모두 `config()` 로 읽는다. 새 설정을 추가하면 `.env.example` 에도 항목을 넣는다.
- 프로젝트 고유 설정:

  | 설정 | 용도 |
  |------|------|
  | `SLACK_TOKEN` | 알림 DM 발송용 봇 토큰. 비어 있으면 크롤링은 되지만 알림은 나가지 않는다 |
  | `JERRYBOT_API_KEY` | 값이 있으면 API 호출 시 `X-API-Key` 헤더를 검사한다. 비우면 인증 없이 열린다 |
  | `CRAWLER_USER_AGENT` | 크롬 드라이버에 지정할 User-Agent (선택) |
  | `LOG_LEVEL` | `Crawling_App` 로거 레벨 |

- `urls.py` 의 `/Crawling_App/` 접두사는 예전 슬랙봇이 쓰던 경로다. 새 코드는 `/api/` 를 쓴다.
  제거하려면 구버전 봇이 더 이상 없는지 먼저 확인할 것.
- 운영 배포 시 `.env` 에 `DEBUG=False` 와 실제 `ALLOWED_HOSTS` 를 반드시 지정한다.
  `SECRET_KEY` 기본값은 개발 전용이다.

### Testing Requirements

- 설정 변경 후 `manage.py check` 로 검증한다.
- `.env` 없이도 기동되는지 확인할 것. 필수값에는 `default=` 가 지정돼 있어야 한다.

### Common Patterns

- 타임존은 `Asia/Seoul`, 언어는 `ko-kr`. 공고 마감일 표시가 한국 기준이어야 하므로 바꾸지 말 것.
- `REST_FRAMEWORK` 의 `UNICODE_JSON: True` 는 한글 공고 제목이 `\uXXXX` 로 이스케이프되지 않게 한다.
- 로깅은 `Crawling_App` 로거만 콘솔 핸들러에 연결돼 있다.

## Dependencies

### Internal

- `Crawling_App` — `INSTALLED_APPS` 에 등록되고 `urls.py` 가 그 URL 을 포함한다.

### External

- `Django` 5.0.3 — 설정 체계
- `python-decouple` 3.8 — `.env` 로드
- `djangorestframework` 3.15.1 — `REST_FRAMEWORK` 설정 대상

<!-- MANUAL: 이 줄 아래에 직접 적은 메모는 재생성해도 보존됩니다 -->
