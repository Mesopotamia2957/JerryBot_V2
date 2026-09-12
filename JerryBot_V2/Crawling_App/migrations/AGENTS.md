<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-03 | Updated: 2026-08-03 -->

# migrations

## Purpose

DB 스키마 변경 이력. Django 가 `models.py` 와 실제 테이블을 맞추기 위해 사용한다.
직접 손으로 작성하지 않고 `makemigrations` 로 생성한다.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | 패키지 선언. 없으면 Django 가 마이그레이션을 인식하지 못한다 |
| `0001_initial.py` | 최초 스키마. `Company`, `JobPosting`, `Subscriber`, `Keyword`, `Notification` 5개 테이블과 인덱스·유니크 제약 |

## For AI Agents

### Working In This Directory

- **파일을 직접 편집하지 말 것.** `models.py` 를 고친 뒤 명령으로 생성한다:
  `manage.py makemigrations Crawling_App`
- 이미 적용된 마이그레이션 파일을 수정하거나 삭제하면 다른 환경의 DB 와 어긋난다.
  되돌리려면 새 마이그레이션을 추가한다.
- `0001_initial.py` 에 담긴 제약은 데이터 정합성의 핵심이므로 제거하지 말 것:

  | 제약 | 목적 |
  |------|------|
  | `uniq_posting_per_company` | 같은 공고 중복 저장 방지 (`company` + `fingerprint`) |
  | `uniq_notification` | 같은 공고를 같은 사람에게 두 번 발송 방지 |
  | `uniq_keyword_per_subscriber` | 키워드 중복 등록 방지 |

### Testing Requirements

- 마이그레이션 생성 후 적용까지 확인: `manage.py migrate`
- 모델과 마이그레이션이 어긋나지 않는지 확인: `manage.py makemigrations --check --dry-run`
  (변경할 게 없으면 아무것도 생성되지 않아야 한다)

### Common Patterns

- 개발 중 스키마를 갈아엎어야 하면 `db.sqlite3` 와 `0001_initial.py` 를 지우고 다시 생성하는 편이
  빠르다. 단, 이미 배포된 환경이 있으면 절대 이 방법을 쓰지 않는다.

## Dependencies

### Internal

- `Crawling_App/models.py` — 마이그레이션의 원본

### External

- `Django` 5.0.3 — 마이그레이션 프레임워크

<!-- MANUAL: 이 줄 아래에 직접 적은 메모는 재생성해도 보존됩니다 -->
