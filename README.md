# JerryBot_V2 — 채용공고 크롤링 + API 서버

채용 사이트를 주기적으로 크롤링해 공고를 DB에 쌓고, REST API로 제공하고,
사용자별 키워드에 맞는 **새 공고**를 슬랙 DM으로 보내는 서버입니다.

슬랙 클라이언트는 별도 저장소인 [Slack_bot](../Slack_bot) 입니다.

---

## 설계의 핵심: 크롤링과 응답의 분리

```
[cron 배치]  ──셀레니움──▶ [채용 사이트]
     │
     ▼
   [ DB ]  ◀──── 여기만 읽는다 ────  [REST API] ──▶ 슬랙봇 / 웹
     │
     ▼
[알림 배치] ──키워드 매칭──▶ 슬랙 DM
```

예전에는 요청이 올 때마다 셀레니움을 띄워서 응답이 수십 초 걸렸고, 아무것도 저장하지 않아
"무엇이 새 공고인지" 알 수 없었습니다. 지금은 배치가 미리 DB를 채우고 API는 DB만 읽습니다.
**이 분리가 있어야 키워드 알림이 성립합니다.**

---

## 설치

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # 값 채우기
cd JerryBot_V2
../.venv/bin/python manage.py migrate
```

크롤링에는 **크롬 브라우저**가 필요합니다. 드라이버는 셀레니움이 자동으로 받습니다.

### 환경변수

| 변수 | 설명 |
|------|------|
| `SECRET_KEY` | 운영에서는 반드시 긴 임의 문자열로 지정 |
| `DEBUG` | 운영에서는 `False` |
| `ALLOWED_HOSTS` | 쉼표로 구분. 운영에서는 실제 도메인만 |
| `SLACK_TOKEN` | 알림 발송용 봇 토큰(`xoxb-`). 없으면 크롤링은 되지만 알림이 안 나감 |
| `JERRYBOT_API_KEY` | 값을 넣으면 API 호출 시 `X-API-Key` 헤더 검사. 외부 노출 시 필수 |
| `CRAWLER_USER_AGENT` | 크롬에 지정할 User-Agent (선택) |
| `LOG_LEVEL` | 기본 `INFO` |

---

## 실행

모든 명령은 `manage.py` 가 있는 `JerryBot_V2/` 안에서 실행합니다.

```bash
cd JerryBot_V2
```

### 서버

```bash
../.venv/bin/python manage.py runserver
```

`admin.py`, `models.py` 같은 앱 파일을 직접 실행하면 `ImportError` 가 납니다.
Django 가 불러다 쓰는 파일이지 진입점이 아닙니다.

### 크롤링 배치

```bash
../.venv/bin/python manage.py crawl_jobs              # 전체
../.venv/bin/python manage.py crawl_jobs -c naver     # 특정 기업
../.venv/bin/python manage.py crawl_jobs --notify     # 크롤링 후 알림까지
```

### 알림 발송

```bash
../.venv/bin/python manage.py notify_subscribers --dry-run   # 내용만 확인
../.venv/bin/python manage.py notify_subscribers             # 실제 발송
```

> **최초 1회는 반드시 `--seed` 를 먼저 실행하세요.**
> 안 하면 이미 쌓인 공고 수백 건이 구독자에게 한꺼번에 날아갑니다.
> ```bash
> ../.venv/bin/python manage.py notify_subscribers --seed
> ```

### 자동 실행 (launchd) — 이미 등록돼 있음

평일 오전 9시, 오후 6시에 자동으로 크롤링하고 알림을 보낸다.

| 파일 | 역할 |
|------|------|
| `run_crawl_notify.sh` | 실제 실행 스크립트. 직접 돌려볼 때도 이걸 쓰면 launchd 와 같은 조건이 된다 |
| `~/Library/LaunchAgents/com.bbakjae.jerrybot.plist` | 실행 시각 정의 (평일 09:00, 18:00) |
| `logs/crawl.log` | 실행 기록. 최근 2000줄만 유지 |

```bash
launchctl list | grep jerrybot                        # 등록 확인
launchctl kickstart gui/$UID/com.bbakjae.jerrybot     # 지금 즉시 한 번 실행
tail -40 logs/crawl.log                               # 결과 확인
launchctl bootout gui/$UID/com.bbakjae.jerrybot       # 자동 실행 끄기
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.bbakjae.jerrybot.plist   # 다시 켜기
```

시각을 바꾸려면 plist 의 `StartCalendarInterval` 을 고친 뒤 `bootout` → `bootstrap` 한다.
`Weekday` 는 1=월 … 5=금, `RunAtLoad` 는 `false` 라 등록만으로는 실행되지 않는다.

**이 배치는 서버나 슬랙봇이 꺼져 있어도 동작한다.** DB와 슬랙 API를 직접 쓰기 때문이다.
서버·봇이 필요한 건 `!목록` 같은 대화형 명령뿐이다.

cron 을 쓰고 싶다면 아래와 같지만, 맥에서는 잠자기 중 예약 시각이 지나면 그 회차를 건너뛴다.

```
0 9,18 * * 1-5 /path/to/JerryBot_V2/run_crawl_notify.sh
```

---

## 크롤링 상태 점검

사이트가 개편되면 셀렉터가 깨집니다. 이 명령으로 어디가 깨졌는지 바로 알 수 있습니다.
DB에는 쓰지 않습니다.

```bash
../.venv/bin/python manage.py check_sites            # 정상 기업 전체
../.venv/bin/python manage.py check_sites -c naver   # 특정 기업
../.venv/bin/python manage.py check_sites --all      # 중단된 기업까지
```

수집 건수, 상세 링크 추출률, 중복, 부가정보를 보여주고 이상 징후를 경고합니다.

```
✓ 네이버            44건    7.4초
✓ 당근             43건    2.9초
✗ 무신사             0건   16.2초  — 수집 0건 — item_selector 가 안 맞을 수 있음
```

## 테스트

셀레니움 없이 도는 회귀 테스트입니다.

```bash
../.venv/bin/python manage.py test Crawling_App
```

---

## 기업 추가하기

`Crawling_App/sites.py` 의 `SITES` 에 `SiteSpec` 을 한 줄 추가하면 끝입니다.
크롤러도, API도, 슬랙봇도 고칠 필요가 없습니다.

```python
SiteSpec(
    code='example', name='예시기업',
    url='https://example.com/careers',
    item_selector='[data-job-card]',
    title_selector='h3',
    meta_selector='.deadline',
),
```

`SiteSpec` 의 주요 옵션:

| 옵션 | 용도 |
|------|------|
| `item_selector` | 공고 하나를 감싸는 요소 |
| `title_selector` | 공고 제목. `:self` 면 항목 자신의 텍스트 중 가장 긴 줄 |
| `meta_selector` / `meta_attr` | 마감일·직군 등 부가정보 (텍스트 또는 속성에서) |
| `link_selector` | 상세 링크. 생략하면 항목의 href, 없으면 내부 첫 `<a>` |
| `link_pattern` / `link_template` | href가 `#` 앵커라 쓸 수 없을 때 속성값의 ID로 URL 조립 |
| `link_attr_template` | 상세 URL을 항목의 여러 속성으로 조립 (현대·기아처럼 파라미터가 여러 개일 때) |
| `has_detail_link` | 공고별 상세 주소가 없는 사이트(클릭 시 모달만 뜨는 경우)는 `False` |
| `prepare` | 크롤링 전에 눌러야 하는 필터가 있을 때 |
| `next_button_selector` | 페이지네이션 |
| `initial_wait` | 공고를 늦게 그리는 사이트의 추가 대기 시간 |
| `enabled` / `disabled_reason` | 개편·차단으로 당분간 못 긁을 때 배치에서 제외 |

### 셀렉터를 고를 때

**빌드할 때 생성되는 클래스명을 쓰지 마세요.** `iKWWXF`, `css-1q2dra3`, `c-jtvHKu` 같은 것들은
사이트가 재배포되면 바뀌어서 크롤링이 통째로 깨집니다. 실제로 이것 때문에 한 번에 9곳이 멈췄습니다.

대신 이런 것을 쓰세요.

- `[data-job-card]`, `[data-testid="공고_아이템"]` — 테스트용 속성은 잘 안 바뀝니다
- `a[href*="/jobs/"]` — 링크 경로 패턴
- `h3`, `li` 같은 의미 있는 태그

### `href="#"` 함정

카드가 `<a href="#n" onclick="show('30005220')">` 처럼 생긴 사이트가 있습니다.
브라우저가 `#n` 을 절대 주소로 바꿔주기 때문에 href 는 비어 있지 않지만,
**모든 공고에서 값이 같습니다.** 이걸 진짜 링크로 믿으면 지문이 겹쳐 공고 10건이 1건으로 합쳐집니다.

`crawler._usable_link()` 가 막고 있으니 제거하지 마세요.
진짜 상세 링크가 필요하면 `link_pattern` / `link_template` 로 ID를 뽑아 URL을 만듭니다.

---

## API

기본 경로는 `/api/` 입니다. (`/Crawling_App/` 은 예전 슬랙봇 호환용)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/companies/` | 기업 목록과 진행 중 공고 수 |
| GET | `/api/postings/?keyword=백엔드&limit=50` | 전체 공고에서 키워드 검색 |
| GET | `/api/<기업코드>/` | 기업별 공고. 한글 기업명도 됩니다 (`/api/네이버/`) |
| GET·POST | `/api/subscribers/<slack_user_id>/` | 구독자 정보 조회·수정 |
| GET·POST·DELETE | `/api/subscribers/<slack_user_id>/keywords/` | 키워드 관리 |
| GET | `/api/subscribers/<slack_user_id>/matches/` | 내 키워드에 맞는 공고 |

```bash
curl 'http://localhost:8000/api/postings/?keyword=백엔드'
curl -X POST http://localhost:8000/api/subscribers/U123/keywords/ \
     -H 'Content-Type: application/json' -d '{"keywords":["백엔드","django"]}'
```

관리자 화면(`/admin/`)에서 공고와 구독자를 눈으로 확인할 수 있습니다.
계정은 `manage.py createsuperuser` 로 만듭니다.

---

## 데이터 모델

```
Company ──1:N──▶ JobPosting
                     ▲
                     │ (키워드 매칭)
Subscriber ──1:N──▶ Keyword
    │
    └──1:N──▶ Notification ──▶ JobPosting
              (이미 보낸 공고 기록 → 중복 알림 방지)
```

- `JobPosting.fingerprint` — 재크롤링 시 같은 공고를 중복 저장하지 않게 하는 키.
  상세 링크가 있으면 링크로, 없으면 제목으로 식별합니다.
- `JobPosting.is_open` — 목록에서 사라진 공고는 자동으로 마감 처리됩니다.
  단, 크롤링 결과가 비면(셀렉터가 깨진 경우) 기존 공고를 마감시키지 않습니다.
- `Notification` — 이게 있어야 같은 공고를 매일 다시 보내지 않습니다.

---

## 프로젝트 구조

```
JerryBot_V2/
└── JerryBot_V2/
    ├── manage.py
    ├── JerryBot_V2/          설정 (settings, urls, wsgi)
    └── Crawling_App/
        ├── sites.py          ★ 기업 추가는 여기만
        ├── crawler.py        셀레니움 엔진 (기업 늘어도 안 바뀜)
        ├── models.py         테이블 5개
        ├── services.py       크롤링 결과 저장·조회·구독
        ├── notifications.py  키워드 매칭 + DM 발송
        ├── views.py          API (DB만 조회)
        ├── tests.py          회귀 테스트
        └── management/commands/
            ├── crawl_jobs.py
            ├── notify_subscribers.py
            └── check_sites.py
```
