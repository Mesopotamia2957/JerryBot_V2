<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-03 | Updated: 2026-08-03 -->

# Crawling_App

## Purpose

이 프로젝트의 기능 전부가 들어 있는 유일한 Django 앱. 크롤링, 저장, 조회 API, 키워드 알림을 담당한다.

레이어가 명확히 나뉘어 있고, 이 경계를 지키는 것이 중요하다.

```
sites.py       사이트 정의 (무엇을 크롤링할지)
   ↓
crawler.py     셀레니움 엔진 (어떻게 크롤링할지)
   ↓
services.py    DB 반영 + 조회 + 구독 (비즈니스 로직)
   ↓
views.py       HTTP 응답 (셀레니움을 전혀 모른다)
```

`views.py` 가 크롤링을 모르게 한 이유는, 웹 프론트를 붙일 때 화면용 엔드포인트만 추가하면 되고
크롤링 코드는 건드릴 일이 없게 하기 위해서다.

## Key Files

| File | Description |
|------|-------------|
| `sites.py` | **기업 추가는 여기만 수정한다.** `SiteSpec` 데이터클래스와 사이트 18개 정의, 필터 클릭용 `PREPARE_HOOKS` |
| `crawler.py` | 셀레니움 엔진. `crawl(spec)` 하나가 모든 사이트를 처리한다. 기업이 늘어도 이 파일은 안 바뀐다 |
| `models.py` | 테이블 5개 — `Company`, `JobPosting`, `Subscriber`, `Keyword`, `Notification` |
| `services.py` | 크롤링 결과 저장(`store_postings`), 조회(`list_postings`), 구독 관리. 뷰와 배치가 호출한다 |
| `notifications.py` | 키워드 매칭 + 슬랙 DM 발송. 발송 이력을 남겨 중복 알림을 막는다 |
| `views.py` | REST API 엔드포인트 6개. DB 만 조회한다 |
| `serializers.py` | DRF 직렬화 |
| `urls.py` | 앱 URL 라우팅 |
| `admin.py` | 관리자 화면 등록. 공고·구독자를 눈으로 확인할 때 쓴다 |
| `apps.py` | Django 앱 설정 |
| `tests.py` | 회귀 테스트 56개. 셀레니움 없이 돈다 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `management/` | 배치 실행용 관리 명령 — crawl_jobs, notify_subscribers, check_sites (see `management/AGENTS.md`) |
| `migrations/` | DB 스키마 이력 (see `migrations/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- **기업을 추가할 때**: `sites.py` 의 `SITES` 에 `SiteSpec` 을 추가한다. 그게 전부다.
  `crawler.py`, `views.py`, `urls.py`, 슬랙봇 어느 것도 고치지 않는다.
  드롭다운 필터를 눌러야 하면 `PREPARE_HOOKS` 에 함수를 등록하고 `spec.prepare` 로 연결한다.
- **셀렉터가 같은 사이트는 프리셋을 공유한다**: 네이버·스노우는 `NAVER_STYLE`,
  greetinghr 를 쓰는 4개사(여기어때·SSG·야놀자·두들린)는 `GREETING_STYLE`.
- **공고 링크 수집은 필수 기능이다.** 서비스 목표가 "링크와 함께 제공"이므로 링크를 빼지 말 것.
  `crawler._link_of()` 가 `(url, has_link)` 를 돌려주고, 링크를 못 뽑는 사이트는 `has_link=False` 다.
- **`has_link=False` 처리를 없애지 말 것.** 링크가 없는 사이트는 모든 공고의 URL 이 채용 홈으로
  같아진다. 그대로 두면 `fingerprint` 가 같아져 공고 전체가 한 건으로 합쳐진다.
  `JobPosting.make_fingerprint()` 가 이 경우에만 제목으로 식별한다.
- **`href="#"` 앵커 함정** (실제로 네이버에서 터졌던 버그). 카드가
  `<a href="#n" onclick="show('30005220')">` 처럼 생긴 사이트가 있다. 브라우저가 `#n` 을 절대 주소로
  바꿔주기 때문에 href 는 비어 있지 않지만, 값이 **모든 공고에서 동일**하다. 이걸 진짜 링크로 믿으면
  지문이 전부 겹쳐 공고 10건이 1건으로 합쳐진다.
  `crawler._usable_link()` 가 "목록 페이지와 같은 주소면 링크가 아니다"로 판정해 막고 있으므로 제거하지 말 것.
  이런 사이트에서 진짜 상세 링크가 필요하면 `SiteSpec` 의 `link_attr` / `link_pattern` / `link_template` 로
  속성값의 ID를 뽑아 URL 을 조립한다 (네이버·스노우가 이 방식).
- **크롤링 URL 에 카테고리 필터를 걸 때 주의.** 사용자가 키워드로 거르는 것이 서비스 목표이므로,
  수집 단계에서 직군을 좁히면 그 키워드에 걸릴 공고가 아예 존재하지 않게 된다.
  가능하면 전체 목록을 수집한다. (네이버의 `srchClassCd`, 여기어때의 직군 필터 등을 이 이유로 제거했다)
- **빌드할 때 생성되는 클래스명을 셀렉터로 쓰지 말 것.** `iKWWXF`, `css-1q2dra3`, `c-jtvHKu` 같은
  해시 클래스는 사이트가 재배포되면 바뀐다. 실제로 이것 때문에 한 번에 9곳이 0건이 됐다.
  `[data-job-card]`, `a[data-testid="공고_아이템"]`, `a[href*="/jobs/"]` 처럼 속성이나 링크 패턴을 쓴다.
- **같은 목록 안에서도 항목 구조가 다를 수 있다.** 네이버는 서버가 그린 앞 10건이 `show('123')` 이고
  스크롤로 붙는 카드는 `show(123)` 라 따옴표가 없다. `link_pattern` 을 쓸 때는 두 형태를 모두 받도록 하고,
  패턴이 안 맞으면 일반 href 방식으로 넘어가게 둘 것.
- **공고가 몇 건까지 나오는지 페이지에서 직접 확인할 것.** 현대자동차는 전체 60건인데 한 페이지에
  10건만 보여줘서, 페이징을 붙이기 전까지 10건만 수집됐다. 목록 어딘가에 적힌 총 건수와
  `check_sites` 의 수집 건수를 대조하면 이런 누락이 드러난다.
- **중단된 사이트는 지우지 말고 `enabled=False`** 로 두고 `disabled_reason` 을 적는다.
  배치에서는 빠지지만 정의가 남아 있어 복구할 때 참고가 된다.
  `manage.py check_sites --all` 로 강제 검사할 수 있다.
- **뷰에서 크롤링을 호출하지 말 것.** 크롤링은 `management/commands/crawl_jobs.py` 배치만 한다.
  뷰가 셀레니움을 부르면 응답이 수십 초 걸리고 신규 공고 판별도 깨진다.
- `urls.py` 의 `<str:code>` 패턴은 앞의 모든 경로를 삼키므로 **반드시 맨 마지막**에 둔다.
  `slug` 가 아니라 `str` 인 이유는 `/api/네이버/` 처럼 한글 기업명을 받기 위해서다.

### 알림이 안 나갈 때

- **macOS 에서 슬랙 전송이 SSL 오류로 실패한다.** `CERTIFICATE_VERIFY_FAILED: unable to get
  local issuer certificate` 가 나오면 시스템 인증서를 못 찾은 것이다. `notifications._client()`
  가 `certifi` CA 번들을 명시해 해결하고 있으니 그 인자를 지우지 말 것.
  실제로 이것 때문에 launchd 예약 실행이 크롤링은 성공하면서 전송만 조용히 실패했다.
- **전송 실패 시 발송 기록을 남기지 않는다.** 실패했는데 보낸 것으로 기록하면 그 공고는 영영
  안 나간다. `notify_subscriber` 가 실패 시 `_mark_sent` 를 건너뛰므로 다음 실행에서 재시도된다.
- 알림이 안 왔다면 `logs/crawl.log` 에서 `슬랙 전송 실패` 를 먼저 찾아볼 것.
  요약에 찍히는 '보낼 알림이 없습니다' 는 전송 실패 후에도 나오므로 그것만 보고 판단하면 안 된다.

### 크롤링이 깨졌을 때

사이트 개편은 상시로 일어난다. 먼저 진단 명령으로 어디가 깨졌는지 확인한다.

```
python manage.py check_sites            # 정상 기업 전체
python manage.py check_sites -c naver   # 특정 기업
python manage.py check_sites --all      # 중단된 기업까지
```

수집 0건이면 `item_selector` 가, 상세 링크 0건이면 `link_selector`/`link_pattern` 이 깨진 것이다.
목록 URL 자체가 옮겨간 경우도 많으니(SSG·여기어때·당근이 그랬다) 최종 URL 을 먼저 확인할 것.

### Testing Requirements

- 셀레니움 없이 검증 가능한 범위가 넓다. `manage.py shell` 에서 `services.store_postings()` 에
  더미 row 리스트를 넣어 저장·중복방지·마감처리를 확인할 수 있다.
- row 딕셔너리 형식: `{'title', 'url', 'has_link', 'meta', 'meta_label'}`
- 반드시 확인할 시나리오:
  1. 같은 결과를 두 번 저장 → 신규 0건
  2. 한 건이 빠진 결과를 저장 → 그 건이 `is_open=False`
  3. `has_link=False` 로 제목이 다른 두 건 → 신규 2건 (1건으로 합쳐지면 버그)
  4. 알림 발송 후 재실행 → 같은 공고가 다시 안 나감
- 실제 크롤링은 기업 하나씩: `manage.py crawl_jobs -c naver`
- 알림은 `--dry-run` 으로 먼저 내용을 확인한다.

### Common Patterns

- **한 기업이 실패해도 나머지는 계속 진행한다.** `services.crawl_company()` 는 `CrawlError` 를
  잡아 결과 딕셔너리로 돌려주고 예외를 밖으로 던지지 않는다. 실패 사유는 `Company.last_crawl_error` 에 남는다.
- 크롤링 중 개별 항목 파싱 실패는 그 항목만 건너뛴다 (`StaleElementReferenceException` 등).
- 키워드 매칭은 `JobPostingQuerySet.matching()` — 제목이나 `meta` 에 `icontains` OR 조건.
- 키워드는 `Keyword.save()` 에서 소문자로 정규화된다.
- 페이지네이션은 상한(`max_pages`)과 정체 감지를 모두 둔다. 무한 루프 방지용이므로 빼지 말 것.

## Dependencies

### Internal

- `JerryBot_V2/settings.py` — `SLACK_TOKEN`, `JERRYBOT_API_KEY`, `CRAWLER_USER_AGENT` 를 읽는다
- `Slack_bot` 저장소 — 이 앱의 API 응답 형식에 의존한다. 응답 키를 바꾸면 그쪽도 고쳐야 한다

### External

- `selenium` 4.19.0 — `crawler.py`. 크롬 브라우저와 드라이버 필요
- `djangorestframework` 3.15.1 — `views.py`, `serializers.py`
- `slack_sdk` 3.27.1 — `notifications.py`. 지연 임포트라 크롤링만 할 때는 불필요

<!-- MANUAL: 이 줄 아래에 직접 적은 메모는 재생성해도 보존됩니다 -->
