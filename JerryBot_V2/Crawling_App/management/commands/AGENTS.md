<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-03 | Updated: 2026-08-03 -->

# commands

## Purpose

주기 실행용 배치 명령. 크롤링과 알림 발송은 HTTP 요청이 아니라 여기서 시작한다.

이 구조의 핵심은 **크롤링이 사용자 요청과 분리돼 있다**는 점이다. 배치가 미리 DB 를 채워두므로
API 응답이 즉시 나가고, 직전 크롤링과 비교해 "신규" 공고를 판별할 수 있다.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | 패키지 선언. 없으면 Django 가 명령을 인식하지 못한다 |
| `crawl_jobs.py` | 채용 사이트를 크롤링해 DB 에 저장한다. `--notify` 로 알림까지 이어서 실행 |
| `notify_subscribers.py` | 크롤링 없이, 저장된 공고 중 아직 안 보낸 것만 발송한다 |

## For AI Agents

### Working In This Directory

- 명령 옵션:

  | 명령 | 옵션 | 용도 |
  |------|------|------|
  | `crawl_jobs` | `-c/--company` | 기업 코드 지정. 여러 번 반복 가능. 생략하면 전체 |
  | `crawl_jobs` | `--notify` | 크롤링 후 구독자에게 신규 공고 알림 |
  | `crawl_jobs` | `--seed-notifications` | 발송 없이 현재 공고를 전송 완료로만 기록 |
  | `notify_subscribers` | `--dry-run` | 실제 전송 없이 로그로 내용만 확인 |
  | `notify_subscribers` | `--seed` | 발송 없이 전송 완료로만 기록 |

- **최초 도입 시 반드시 `--seed` 를 먼저 실행한다.** 그러지 않으면 이미 쌓인 공고 수백 건이
  구독자에게 한꺼번에 날아간다.
- 새 명령을 추가할 때는 로직을 여기 두지 말고 `services.py` 나 `notifications.py` 에 두고
  명령은 얇게 호출만 한다. 그래야 셸이나 테스트에서도 같은 로직을 쓸 수 있다.
- 명령은 사람이 읽을 진행 상황을 `self.stdout` 에, 실패를 `self.stderr` 에 쓴다.
  기업 하나가 실패해도 전체를 중단하지 않는다.

### Testing Requirements

- 알림은 항상 `--dry-run` 으로 먼저 확인한 뒤 실제 발송한다. 슬랙 DM 은 되돌릴 수 없다.
- 크롤링은 전체를 돌리기 전에 기업 하나로 확인한다: `manage.py crawl_jobs -c naver`
- 실행 위치는 `manage.py` 가 있는 디렉터리다.

### Common Patterns

- cron 등록 예시 (매일 오전 9시, 오후 6시):

  ```
  0 9,18 * * * cd /path/to/JerryBot_V2/JerryBot_V2 && ../.venv/bin/python manage.py crawl_jobs --notify
  ```

- `crawl_jobs` 는 시작할 때 `services.sync_companies()` 로 `sites.py` 정의를 DB 에 반영한다.
  따라서 기업을 추가한 뒤 별도 등록 작업이 필요 없다.

## Dependencies

### Internal

- `Crawling_App.services` — `sync_companies()`, `crawl_company()`
- `Crawling_App.notifications` — `notify_all()`
- `Crawling_App.sites` — 전체 기업 코드 목록

### External

- `Django` 5.0.3 — `BaseCommand`

<!-- MANUAL: 이 줄 아래에 직접 적은 메모는 재생성해도 보존됩니다 -->
