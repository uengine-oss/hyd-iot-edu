"""mcp-ent (read-only): GET the enterprise-system endpoints that InfoType nodes of the ontology point to.

The agent never hard-codes which system holds a fact: it asks the ontology (T3-a) and calls the endpoint found there.
Only GET is possible through this tool; writes to ERP/MES/CMMS/QMS/EMS belong to the process service after approval.

읽기가 실패하면 그 자리의 까닭 그대로 SourceUnavailable 로 실패한다(값 없음으로 바꾸지 않는다 — 검진 H-8). 다시 시도는 부르는 쪽
(AI 단계의 도구 호출 · 사람)이 정한다: 업무 DB 가 몇 초 끊긴 동안 여기서 몰래 되풀이하면 판단 하나가 그만큼 늘어지고, 끊김은 감춰진다.
"""
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

ENTERPRISE_URL = os.getenv("ENTERPRISE_URL", "http://enterprise-sim:8095")
#: enterprise-sim 은 읽기마다 업무 DB 연결을 새로 열고 그 연결 한도가 5초다(entsim/main.py connect_timeout=5). 이쪽 한도가 그보다 길어야
#: 업무 DB 가 끊겼을 때 enterprise-sim 이 내는 까닭(503 「업무 DB에 연결하지 못했습니다」)을 받는다 — 같은 5초면 늘 이쪽이 먼저 끊고
#: 「응답 없음」만 남았다(2026-10-30 키 있는 한 바퀴 실습 12: 06:10:40~46 업무 DB 연결이 끊긴 동안 재고 조회가 5초에 끊김).
TIMEOUT_S = 15.0


class SourceUnavailable(RuntimeError):
    """업무 시스템 읽기 실패 — 문장은 무엇(경로) · 왜 · 다음에 무엇을. status: HTTP 상태(닿지 못했으면 None).
    transient: 곧 풀릴 수 있는 까닭(닿지 못함 · 시간 초과 · 5xx)인가 — 거절(4xx)과 꼴이 틀린 응답은 다시 읽어도 같다."""

    def __init__(self, message: str, status: int | None = None, *, transient: bool = False):
        super().__init__(message)
        self.status, self.transient = status, transient


def _detail(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read(4001).decode("utf-8", "replace")
    except OSError:
        return ""
    try:
        detail = json.loads(body).get("detail")
    except (ValueError, AttributeError):
        return body.strip()[:300]
    return detail.strip()[:300] if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)[:300]


def fetch(endpoint: str, asset: str, timeout: float = TIMEOUT_S) -> dict:
    path = endpoint.replace("{asset}", urllib.parse.quote(asset))
    if not path.startswith("/") or ".." in path:
        raise ValueError(f"업무 시스템 읽기 경로가 허용되지 않습니다: {endpoint}")
    where = f"업무 시스템 {path.split('?', 1)[0]}"
    try:
        with urllib.request.urlopen(ENTERPRISE_URL + path, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        detail = _detail(e)
        hint = " 잠시 뒤 다시 시도하세요." if e.code >= 500 and "다시 시도" not in detail else ""      # 서버 까닭에 이미 있으면 한 번만
        raise SourceUnavailable(f"{where}을(를) 읽지 못했습니다(HTTP {e.code}){' — ' + detail if detail else ''}.{hint}", e.code,
                                transient=e.code >= 500) from None
    except (TimeoutError, socket.timeout):
        raise SourceUnavailable(f"{where}이(가) {timeout:g}초 안에 답하지 않았습니다 — 업무 시스템 · 업무 DB 연결을 확인하고 잠시 뒤 다시 시도하세요.", transient=True) from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise SourceUnavailable(f"{where}에 닿지 못했습니다({reason}) — 시작.bat 으로 서비스를 다시 켠 뒤 다시 시도하세요.", transient=True) from None
    try:
        out = json.loads(body)
    except ValueError:
        raise SourceUnavailable(f"{where}의 응답이 JSON 이 아닙니다.") from None
    if not isinstance(out, dict):
        raise SourceUnavailable(f"{where}의 응답이 객체가 아닙니다.")
    return out
