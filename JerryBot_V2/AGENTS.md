<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-03 | Updated: 2026-08-03 -->

# JerryBot_V2 (Django 프로젝트 루트)

## Purpose

Django 프로젝트의 실행 루트. `manage.py` 가 여기 있으므로 모든 관리 명령은 이 디렉터리에서 실행한다.
설정 패키지(`JerryBot_V2/`)와 유일한 앱(`Crawling_App/`)을 담고 있다.

## Key Files

| File | Description |
|------|-------------|
| `manage.py` | Django 관리 명령 진입점. `runserver`, `migrate`, `crawl_jobs` 등을 여기서 실행한다 |
| `db.sqlite3` | 개발용 SQLite DB. 공고·구독자·발송이력이 들어 있다. git 에 올리지 않는다 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `JerryBot_V2/` | 설정 패키지 — settings, urls, wsgi, asgi (see `JerryBot_V2/AGENTS.md`) |
| `Crawling_App/` | 실제 기능 전부 — 크롤링, 모델, API, 알림 (see `Crawling_App/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- 명령 실행 형태: `../.venv/bin/python manage.py <command>`
- 자주 쓰는 명령:

  | 명령 | 용도 |
  |------|------|
  | `runserver` | 개발 서버 실행 (기본 `http://localhost:8000`) |
  | `check` | 설정·모델 정합성 검사 |
  | `makemigrations Crawling_App` / `migrate` | 모델 변경 반영 |
  | `crawl_jobs` | 크롤링 배치. `-c naver` 로 기업 지정, `--notify` 로 알림까지 |
  | `notify_subscribers` | 알림만 발송. `--dry-run`, `--seed` 지원 |
  | `createsuperuser` | 관리자 계정 생성 (비밀번호 입력이 필요해 사람이 직접 실행해야 한다) |

- 앱이 하나뿐이므로 새 기능은 원칙적으로 `Crawling_App/` 안에 넣는다. 앱을 새로 만들기 전에
  정말 경계가 다른 도메인인지 먼저 판단할 것.

### Testing Requirements

- 변경 후 최소한 `manage.py check` 는 통과해야 한다.
- 모델을 고쳤다면 `makemigrations` 로 마이그레이션이 생성되는지 확인한다.
- 자동화된 테스트는 `Crawling_App/tests.py` 에 둔다 (현재 비어 있음). 실행은 `manage.py test`.

### Common Patterns

- URL 은 설정 패키지의 `urls.py` 가 `/api/` 와 `/Crawling_App/` 두 접두사로 앱 URL 을 포함한다.
  뒤쪽은 예전 슬랙봇 호환용이다.

## Dependencies

### Internal

- `JerryBot_V2/settings.py` 의 `INSTALLED_APPS` 에 `Crawling_App` 과 `rest_framework` 가 등록돼 있다.

### External

- `Django` 5.0.3

<!-- MANUAL: 이 줄 아래에 직접 적은 메모는 재생성해도 보존됩니다 -->
