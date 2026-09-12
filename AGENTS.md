<!-- Generated: 2026-08-03 | Updated: 2026-08-03 -->

# JerryBot_V2

## Purpose

채용공고 알림 서비스의 **크롤링 + API 서버**. 세 가지 일을 한다.

1. 채용 사이트 14곳을 셀레니움으로 크롤링해 공고를 DB 에 저장한다 (배치)
2. 저장된 공고를 REST API 로 제공한다 (슬랙봇과 향후 웹 프론트가 사용)
3. 사용자별 키워드에 맞는 **신규** 공고를 슬랙 DM 으로 보낸다 (배치)

핵심 설계는 **크롤링과 응답의 분리**다. 예전에는 요청이 올 때마다 셀레니움을 띄워 응답이 수십 초
걸렸고, 아무것도 저장하지 않아 "무엇이 새 공고인지" 알 수 없었다. 지금은 배치가 미리 DB 를 채우고
API 는 DB 만 읽는다. 이 분리가 있어야 키워드 알림이 성립한다.

## Key Files

| File | Description |
|------|-------------|
| `requirements.txt` | 의존 패키지 목록 |
| `.env.example` | 환경변수 템플릿. 복사해서 `.env` 로 쓴다 |
| `.env` | 실제 비밀값. git 에 올리지 않는다 |
| `.gitignore` | `.env`, `.venv/`, `db.sqlite3`, `__pycache__/` 등 제외 목록 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `JerryBot_V2/` | Django 프로젝트 루트. `manage.py` 와 앱들이 있다 (see `JerryBot_V2/AGENTS.md`) |
| `.venv/` | 가상환경. 문서화 대상이 아니다 |

## For AI Agents

### Working In This Directory

- 저장소 루트와 Django 프로젝트 디렉터리 이름이 둘 다 `JerryBot_V2` 라 헷갈리기 쉽다.
  `manage.py` 는 `JerryBot_V2/JerryBot_V2/` 가 아니라 `JerryBot_V2/` 안에 있다.
- 모든 `manage.py` 명령은 `JerryBot_V2/` 안에서 실행한다:
  `cd JerryBot_V2 && ../.venv/bin/python manage.py <command>`
- **`admin.py`, `models.py`, `views.py` 같은 앱 파일을 직접 실행하지 말 것.** 상대 임포트(`from .models import`)
  때문에 `ImportError: attempted relative import with no known parent package` 가 난다.
  이 파일들은 Django 가 불러다 쓰는 파일이지 진입점이 아니다.
- 크롤링은 크롬 브라우저와 드라이버가 설치된 환경에서만 동작한다.

### Testing Requirements

- 시스템 검사: `cd JerryBot_V2 && ../.venv/bin/python manage.py check`
- 크롤링 없이 저장/조회/알림 로직만 확인하려면 `manage.py shell` 에서 `services` 와 `notifications`
  함수를 직접 호출한다. 셀레니움 없이 검증할 수 있는 부분이 대부분이다.
- 실제 크롤링은 기업 하나씩 확인한다: `manage.py crawl_jobs -c naver`
- 알림은 먼저 전송 없이 확인한다: `manage.py notify_subscribers --dry-run`

### Common Patterns

- 설정은 `python-decouple` 의 `config()` 로 `.env` 에서 읽는다. 값을 하드코딩하지 말 것.
- 배치 작업은 관리 명령(`manage.py <name>`)으로 만든다. 뷰에서 크롤링을 부르지 않는다.

## Dependencies

### Internal

- **Slack_bot 저장소** (`../Slack_bot/`) — 이 서버의 API 를 호출하는 슬랙 클라이언트.
  API 응답 형식을 바꾸면 그쪽 `jerrybot/api.py` 와 `jerrybot/formatting.py` 도 고쳐야 한다.

### External

- `Django` 5.0.3 — 웹 프레임워크
- `djangorestframework` 3.15.1 — REST API
- `selenium` 4.19.0 — 크롤링. 크롬 드라이버 필요
- `python-decouple` 3.8 — `.env` 설정 로드
- `slack_sdk` 3.27.1 — 알림 DM 발송

<!-- MANUAL: 이 줄 아래에 직접 적은 메모는 재생성해도 보존됩니다 -->
