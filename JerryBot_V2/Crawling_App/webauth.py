"""자금관리(finance-api)가 발급한 슬랙 로그인 세션을 그대로 읽는다.

이 앱은 별도 로그인을 만들지 않는다. finance-api 의 /api/auth/login 으로 슬랙 로그인을
한 번 하면, 같은 도메인(jerrybbak.duckdns.org)에 깔리는 쿠키 하나로 이 앱도 "누구인지" 안다.
두 서비스가 SESSION_SECRET 이라는 같은 비밀을 공유하고, 같은 HMAC 서명 방식을 쓰기 때문이다.
(finance-api 쪽 원본: vps-infra/finance/api/app.py 의 sign()/unsign())

크롤러의 Subscriber.slack_user_id 와 자금관리의 user_mst.slack_user_id 는 같은 값이다 —
슬랙 사용자 ID 가 두 서비스를 잇는 공통 키다. 그래서 세션 쿠키에는 finance 내부의 uid
(user_mst_id) 가 아니라 slack_user_id 를 실어 보낸다("sub" 필드, auth_callback 참고).

주의: SESSION_SECRET 이 비어 있으면 무조건 로그인 안 된 것으로 취급한다(폴백 없음).
2026-09-22 에 finance-api 가 "슬랙 미설정 시 1번 사용자로 대체"하는 폴백을 뒀다가,
Caddy 계정만 있으면 그 사람이 곧장 관리자 데이터를 보는 사고가 났다. 그 폴백은 딱 그
서비스가 원래 1인용이었을 때의 임시 장치였고, 다른 사람이 실제로 들어오는 지금 이 모듈에는
같은 패턴을 절대 넣지 않는다 — 비밀키가 없으면 그냥 막는다.
"""

import base64
import hashlib
import hmac
import json
import time

from django.conf import settings

SESSION_COOKIE = "finance_session"


def _b64d(txt: str) -> bytes:
    """finance-api 의 _b64e 로 인코딩된 문자열을 되돌린다."""
    return base64.urlsafe_b64decode(txt + "=" * (-len(txt) % 4))


def _unsign(token: str) -> dict | None:
    """서명을 검사하고 내용을 돌려준다. 위조·만료·형식 오류면 무조건 None."""
    secret = getattr(settings, "SESSION_SECRET", "")
    if not secret or not token or "." not in token:
        return None
    body, _, sig = token.rpartition(".")
    want = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, want):
        return None
    try:
        data = json.loads(_b64d(body))
    except Exception:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data


def current_slack_user_id(request) -> str | None:
    """이 요청을 보낸 사람의 슬랙 사용자 ID. 로그인 안 됐으면 None."""
    data = _unsign(request.COOKIES.get(SESSION_COOKIE, ""))
    if not data:
        return None
    return data.get("sub") or None


def current_is_admin(request) -> bool:
    """자금관리 쪽 관리자(jerry) 여부. 요청 게시판 전체 조회 등에 쓴다."""
    data = _unsign(request.COOKIES.get(SESSION_COOKIE, ""))
    return bool(data and data.get("admin"))
