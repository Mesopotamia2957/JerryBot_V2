<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-03 | Updated: 2026-08-03 -->

# management

## Purpose

Django 관리 명령을 담기 위한 컨테이너 디렉터리. 실제 명령은 `commands/` 안에 있다.
이 두 단계 구조와 각 단계의 `__init__.py` 는 Django 가 명령을 찾기 위해 요구하는 규약이다.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | 패키지 선언. 비어 있지만 없으면 Django 가 명령을 인식하지 못한다 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `commands/` | 실제 배치 명령 (see `commands/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- 이 디렉터리에는 파일을 추가하지 않는다. 새 명령은 `commands/` 에 만든다.
- `__init__.py` 를 지우지 말 것. 삭제하면 `manage.py crawl_jobs` 가 "Unknown command" 로 실패한다.

### Testing Requirements

- 명령이 인식되는지 확인: `manage.py help` 목록에 `crawl_jobs` 와 `notify_subscribers` 가 보여야 한다.

## Dependencies

### Internal

- `Crawling_App` — 명령들이 이 앱의 `services`, `notifications`, `sites` 를 임포트한다.

<!-- MANUAL: 이 줄 아래에 직접 적은 메모는 재생성해도 보존됩니다 -->
