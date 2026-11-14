"""B2 — MCP 서버 등록 · 고치기 · 지우기 + 연결 검사 게이트 + 되돌리기.

설정 원천은 그대로 public.tenants.mcp 의 mcpServers 한 칸이다(워커 bridge.py 가 실행마다 읽는 제품 형태). 포털에서 등록한 서버는
그 칸에 제품 형태 그대로 들어가고, HYD 표시는 한 키("hyd")에만 둔다 — bridge 는 url · headers 만 읽으므로 표시는 실행에 섞이지 않는다.

  "my-folder": {"type": "url", "url": "http://host.docker.internal:8301/mcp", "transport": "streamable_http", "headers": {...},
                "hyd": {"origin": "user", "created_at": …, "updated_at": …,
                        "gate": {"fingerprint": "…", "checked_at": …, "read_tools": ["read_file", …], "blocked_tools": ["write_file", …]}}}

기준 서버(BASE_SERVERS — seed.sql 의 tenants.mcp 다섯 서버)는 수정 · 삭제를 거절한다(vue3 MCPServer.vue:593-596 · 665-668 is_default 와
같은 규칙, HYD 는 이름으로 정한다 — 시드에 표시 칸이 없다). 그 밖의 서버는 모두 학생 것이다: 포털에서 등록한 것(origin=user)과
포털 밖(SQL 등)에서 넣은 것(origin=external). 되돌리기는 둘 다 지운다.

포털에 등록하는 서버는 HTTP 주소 하나다(mcp_check.normalize — 명령형 stdio 는 받지 않는다: process 안에서 남의 명령을 띄우지 않는다).

게이트(검사 통과한 서버의 읽기 표시 도구만):
  * 등록 · 고치기 = 형식 검사(mcp_check.normalize) → 실제 연결 검사(mcp_check.check) → 실패면 사유와 함께 거절(저장 안 함, 고치기면 옛 설정 유지).
  * 검사 기록(mcp_server_checks, migration 20261008000042)에 설정 해시(fingerprint)와 도구 판정을 남긴다.
  * 에이전트에 붙일 수 있음(selectable — 이 한 함수가 도구 지도 · 에이전트 폼 · 저장 검사의 판정이다): 기준 서버는 늘 붙일 수 있고(워커가
    기본 허용 목록으로 실행), 학생 서버는 마지막 검사가 ok 이고 그 해시가 지금 설정과 같으며 읽기 도구(readOnlyHint=true · 쓰기 이름 아님,
    또는 강사 확인)가 하나 이상일 때.
  * 워커: 기준이 아닌 서버는 hyd.gate 의 해시가 지금 설정과 같을 때만 연결하고, read_tools 만 허용 · blocked_tools 는 막는다
    (it/agent-worker/worker/bridge.py gate_servers). 해시 계산은 bridge.config_fingerprint 와 같아야 한다.

G2(토큰이 필요한 서버):
  * 비밀 자리표시자: 접속 헤더 값에 ${SECRET:KEY} 를 쓰면 검사 직전에 mcp_secrets 표로 채운다.
    해시는 자리표시자가 든 설정으로 계산하므로 토큰을 갈아 끼워도 도장은 그대로다. 값이 없으면 검사가 사유(error_kind=secret)와 함께 실패.
  * 강사 확인 읽기 목록(hyd.read_confirmed): readOnlyHint 표시가 없을 뿐 이름 · 표시가 쓰기가 아닌 도구(mcp_check.confirmable)를
    강사가 "읽기"로 확인하면 도장의 read_tools 에 넣는다(확인자 · 이유 · 시각 기록). 쓰기로 표시했거나 이름이 쓰기인 도구는 확인할 수 없다.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import mcp_check, mcp_secrets, progress as progress_log

#: seed.sql 의 tenants.mcp 다섯 서버 — 워커 기본 허용 목록(settings.DEFAULT_ALLOWED_TOOLS)이 적는 서버와 같다.
#: C2: 업무 MCP 를 보전용(enterprise-maint) · 구매용(enterprise-purchase)으로 나눈 두 서버도 기준이다(같은 읽기 전용 코드).
BASE_SERVERS = ("neo4j", "enterprise", "hyd-dmn", "enterprise-maint", "enterprise-purchase")
META_KEY = "hyd"
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?!-)){0,39}$")      # 도구 이름 mcp__<서버>__<도구> 가 갈라지지 않게 '_' 없음
CHECK_TIMEOUT = (0.5, 20.0, 8.0)                                      # (최소, 최대, 기본) 초 — 포털 POST 30초 제한 안
DESCRIPTION_MAX = 200


class RegistryError(Exception):
    """HTTP 상태 + 사람이 읽는 사유(+ 검사 결과)."""

    def __init__(self, status: int, reason: str, check: dict | None = None):
        super().__init__(reason)
        self.status, self.reason, self.check = status, reason, check


# ---------------------------------------------------------------- 설정 · 해시 · 출처
def fingerprint(entry: dict) -> str:
    """서버 설정의 해시 — HYD 표시(hyd)는 빼고, 키 순서와 무관. 워커 bridge.config_fingerprint 와 같은 계산."""
    body = {k: v for k, v in (entry or {}).items() if k != META_KEY}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


def origin_of(name: str, entry) -> str:
    if name in BASE_SERVERS:
        return "seed"
    meta = entry.get(META_KEY) if isinstance(entry, dict) else None
    return "user" if isinstance(meta, dict) and meta.get("origin") == "user" else "external"


ORIGIN_WORDS = {"seed": "기준(기본 제공)", "user": "내가 등록", "external": "포털 밖에서 추가(랩업 SQL 등)"}


def _unmask(new: dict, old: dict, field: str) -> dict:
    """화면은 비밀값을 ******** 로 받는다. 고칠 때 그대로 돌아온 ******** 는 옛 값을 유지한다 — 이름이 같은 칸만.
    이름을 바꾼 칸에 ******** 가 오면 옛 값을 알 수 없으므로 빈 값으로 저장하지 않고 거절한다."""
    out = {}
    for k, v in new.items():
        if v == mcp_check.MASK:
            if k not in old:
                raise RegistryError(422, f"{field}.{k}: 가린 값(********)을 받았지만 이전 설정에 같은 이름의 값이 없습니다 — 값을 다시 적으세요")
            v = old[k]
        out[k] = v
    return out


def _unmask_url(url: str, old_url: str | None) -> str:
    if not old_url or mcp_check.MASK not in url:
        return url
    return url if mcp_check.mask_url(old_url) != url else old_url


def entry_from_body(body: dict, old: dict | None = None) -> dict:
    """폼 입력 → tenants.mcp 한 칸(제품 형태). 형식이 틀리면 RegistryError(422, '칸: 사유')."""
    if not isinstance(body, dict):
        raise RegistryError(400, "요청 본문은 객체여야 합니다")
    old = old or {}
    raw: dict = {"url": body.get("url")}
    if body.get("transport") not in (None, ""):
        raw["transport"] = body.get("transport")
    if body.get("command") not in (None, ""):
        raw["command"] = body.get("command")                       # 명령형은 normalize 가 학생이 읽을 사유로 거절한다
    if body.get("headers") not in (None, ""):
        raw["headers"] = body.get("headers")
    try:
        spec = mcp_check.normalize(raw, student=True)                # 포털 · 출발본으로 들어오는 서버는 모두 학생 것이다
    except ValueError as e:
        raise RegistryError(422, f"설정 오류 — {e}") from e
    wrong = mcp_secrets.misplaced(spec)
    if wrong:
        raise RegistryError(422, "설정 오류 — " + " / ".join(wrong))
    entry = {"type": "url", "url": _unmask_url(spec["url"], old.get("url")), "transport": spec["transport"]}
    headers = _unmask(spec.get("headers") or {}, old.get("headers") or {}, "headers")
    if headers:
        entry["headers"] = headers
    note = str(body.get("description") or "").strip()
    if len(note) > DESCRIPTION_MAX:
        raise RegistryError(422, f"description: 설명은 {DESCRIPTION_MAX}자 이하로 적으세요 (지금 {len(note)}자)")
    if note:
        entry["description"] = note
    return entry


def _check_limit(raw) -> float:
    low, high, default = CHECK_TIMEOUT
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise RegistryError(400, "timeout: 초 단위 숫자여야 합니다")
    if not low <= value <= high:
        raise RegistryError(400, f"timeout: {low:g}~{high:g}초 사이여야 합니다")
    return value


def run_check(entry: dict, timeout: float, secrets: dict | None = None, *, student: bool = True, progress=progress_log.SILENT,
              then: tuple = ()) -> dict:
    """실제 연결 검사(기존 검사기) → 저장할 기록 모양. 입력 형식(input_schema)은 싣지 않는다(도구 지도가 그때그때 읽는다).
    progress: 진행 기록 — 연결하기 직전에 검사의 단계(mcp_check.check_steps)와 그 뒤에 부르는 쪽이 할 단계(then — 저장)를 적고,
    검사가 단계마다 시작 · 끝 · 실패를 적는다. 비밀 값이 없어 연결하지 않은 검사는 단계를 적지 않는다(하지 않은 일을 적지 않는다).
    G2: ${SECRET:KEY} 는 검사 직전에 secrets 로 채운다(해시는 채우기 전 설정). 값이 없으면 연결하지 않고 사유와 함께 실패.
    채운 값은 검사 결과(오류 문구 · stderr 꼬리 · 도구 설명)에서 지운다 — 기록 · 응답 · 감사로 새지 않게.
    student: 기준 다섯 서버만 False(학생 서버는 루프백 주소도 거절 — mcp_check.address_problem)."""
    spec = mcp_check.normalize(entry, student=student)
    resolved, missing = mcp_secrets.resolve(spec, secrets)
    if missing:
        result = {"status": "failed", "error": mcp_secrets.missing_reason(None, missing),
                  "error_kind": "secret", "tools": [], "elapsed_ms": 0, "checked_at": mcp_check._now_z(), "transport": spec.get("transport")}
    else:
        used = [secrets[k] for k in mcp_secrets.references(spec)] if secrets else []
        progress.plan([*mcp_check.check_steps(resolved), *then])
        try:
            with mcp_check.portal_slot(timeout):
                result = mcp_secrets.redact(mcp_check.check(resolved, timeout, progress=progress,
                                                            clean=lambda text: mcp_secrets.redact(text, used)), used)
        except mcp_check.CheckError as e:          # 자리 없음(busy) — 서버 탓이 아니니 검사 기록으로 남기지 않는다
            raise RegistryError(503, e.message) from e
    tools = [{"name": t["name"], "title": t.get("title"), "description": t.get("description") or "", "annotations": t.get("annotations") or {},
              "read_only": bool(t.get("callable")), "reason": t.get("refuse_reason"), "confirmable": bool(t.get("confirmable"))}
             for t in result.get("tools") or []]
    return {"fingerprint": fingerprint(entry), "status": "ok" if result["status"] == "ok" else "failed", "error": result.get("error"),
            "error_kind": result.get("error_kind"), "transport": result.get("transport"), "server_info": result.get("server_info"),
            "tools": tools, "elapsed_ms": result.get("elapsed_ms"), "checked_at": result.get("checked_at")}


def confirmed_of(entry) -> dict:
    """G2 ②: 강사가 읽기로 확인한 도구 {도구: {by, reason, at}} (hyd.read_confirmed)."""
    meta = entry.get(META_KEY) if isinstance(entry, dict) and isinstance(entry.get(META_KEY), dict) else {}
    found = meta.get("read_confirmed")
    return dict(found) if isinstance(found, dict) else {}


def counts_as_read(tool: dict, confirmed) -> bool:
    """서버가 읽기로 표시한 도구, 또는 강사가 확인한 도구(표시만 없고 이름 · 표시가 쓰기가 아닌 것)."""
    return bool(tool.get("read_only")) or (tool.get("name") in (confirmed or {}) and bool(tool.get("confirmable")))


def gate_of(check: dict, confirmed: dict | None = None) -> dict:
    """워커가 읽는 승인 도장: 검사한 설정 해시 + 읽기 전용 도구(+ 강사 확인) / 막을 도구."""
    out = {"fingerprint": check["fingerprint"], "checked_at": check["checked_at"],
           "read_tools": [t["name"] for t in check["tools"] if counts_as_read(t, confirmed)],
           "blocked_tools": [t["name"] for t in check["tools"] if not counts_as_read(t, confirmed)]}
    by_person = [t["name"] for t in check["tools"] if not t.get("read_only") and counts_as_read(t, confirmed)]
    if by_person:
        out["confirmed_tools"] = by_person
    return out


# ---------------------------------------------------------------- 저장소 (tenants.mcp + mcp_server_checks)
class PgMcpStore:
    """한 서버 칸만 jsonb_set / #- 로 바꾼다(다른 칸 · 다른 키는 건드리지 않는다)."""

    def __init__(self, repo):
        self.repo = repo

    def _c(self):
        return self.repo._conn()

    def servers(self, tenant_id) -> dict:
        t = self.repo.get_tenant(tenant_id)
        if t is None:
            raise RegistryError(404, f"테넌트 {tenant_id} 가 없습니다")
        mcp = t.get("mcp") or {}
        config = mcp.get("mcpServers") if isinstance(mcp, dict) else None
        return dict(config) if isinstance(config, dict) else {}

    _BASE = "case when jsonb_typeof(mcp->'mcpServers') = 'object' then mcp else coalesce(mcp, '{}'::jsonb) || '{\"mcpServers\": {}}'::jsonb end"

    def insert_server(self, tenant_id, name, entry) -> bool:
        with self._c() as c:
            row = c.execute(f"update tenants set mcp = jsonb_set({self._BASE}, array['mcpServers', %s], %s) "
                            "where id = %s and not coalesce(mcp->'mcpServers' ? %s, false) returning id",
                            (name, self.repo._Jsonb(entry), tenant_id, name)).fetchone()
        return row is not None

    def replace_server(self, tenant_id, name, entry) -> bool:
        with self._c() as c:
            row = c.execute("update tenants set mcp = jsonb_set(mcp, array['mcpServers', %s], %s) "
                            "where id = %s and coalesce(mcp->'mcpServers' ? %s, false) returning id",
                            (name, self.repo._Jsonb(entry), tenant_id, name)).fetchone()
        return row is not None

    def set_meta(self, tenant_id, name, meta) -> bool:
        with self._c() as c:
            row = c.execute("update tenants set mcp = jsonb_set(mcp, array['mcpServers', %s, %s], %s) "
                            "where id = %s and jsonb_typeof(mcp->'mcpServers'->%s) = 'object' returning id",
                            (name, META_KEY, self.repo._Jsonb(meta), tenant_id, name)).fetchone()
        return row is not None

    def delete_server(self, tenant_id, name) -> bool:
        with self._c() as c:
            row = c.execute("update tenants set mcp = mcp #- array['mcpServers', %s] "
                            "where id = %s and coalesce(mcp->'mcpServers' ? %s, false) returning id", (name, tenant_id, name)).fetchone()
        return row is not None

    def save_check(self, tenant_id, name, record, by) -> None:
        J = self.repo._Jsonb
        with self._c() as c:
            c.execute("insert into mcp_server_checks (tenant_id, server_name, fingerprint, status, error, error_kind, transport, server_info, tools, "
                      "elapsed_ms, checked_by, checked_at) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                      "on conflict (tenant_id, server_name) do update set fingerprint = excluded.fingerprint, status = excluded.status, "
                      "error = excluded.error, error_kind = excluded.error_kind, transport = excluded.transport, server_info = excluded.server_info, "
                      "tools = excluded.tools, elapsed_ms = excluded.elapsed_ms, checked_by = excluded.checked_by, checked_at = excluded.checked_at",
                      (tenant_id, name, record["fingerprint"], record["status"], record.get("error"), record.get("error_kind"), record.get("transport"),
                       J(record.get("server_info")) if record.get("server_info") is not None else None, J(record.get("tools") or []),
                       record.get("elapsed_ms"), by, record["checked_at"]))

    def checks(self, tenant_id) -> dict:
        with self._c() as c:
            if not c.execute("select to_regclass('public.mcp_server_checks') is not null as ok").fetchone()["ok"]:
                raise RegistryError(503, "검사 기록 표(mcp_server_checks)가 없습니다 — 마이그레이션 20261008000042 를 적용하세요")
            rows = c.execute("select * from mcp_server_checks where tenant_id = %s", (tenant_id,)).fetchall()
        return {r["server_name"]: self.repo._row(dict(r)) for r in rows}

    def delete_checks(self, tenant_id, names=None) -> int:
        with self._c() as c:
            if names is None:
                cur = c.execute("delete from mcp_server_checks where tenant_id = %s", (tenant_id,))
            else:
                cur = c.execute("delete from mcp_server_checks where tenant_id = %s and server_name = any(%s)", (tenant_id, list(names)))
            return cur.rowcount or 0


def store_for(repo):
    return PgMcpStore(repo)


# ---------------------------------------------------------------- 상태 · 선택 가능 도구 (도구 지도 · 에이전트 폼 · 저장 검사의 한 판정)
def check_state(name: str, entry, record: dict | None) -> dict:
    """{status: ok|failed|stale|never, checked_at, error, error_kind, elapsed_ms, server_info, tool_count}."""
    if record is None:
        return {"status": "never", "checked_at": None, "error": "아직 연결 검사를 하지 않았습니다", "error_kind": None,
                "elapsed_ms": None, "server_info": None, "tool_count": 0}
    stale = isinstance(entry, dict) and record.get("fingerprint") != fingerprint(entry)
    out = {"status": "stale" if stale else record["status"], "checked_at": record.get("checked_at"), "error": record.get("error"),
           "error_kind": record.get("error_kind"), "elapsed_ms": record.get("elapsed_ms"), "server_info": record.get("server_info"),
           "tool_count": len(record.get("tools") or [])}
    if stale:
        out["error"] = "검사한 뒤 설정이 바뀌었습니다 — 다시 연결 검사를 하세요"
    return out


def _not_selectable_reason(state: dict, entry_error: str | None) -> str | None:
    if entry_error:
        return entry_error
    if state["status"] == "ok":
        return None
    if state["status"] == "never":
        return "연결 검사를 통과하지 않은 서버입니다 — '연결 검사'를 먼저 하세요"
    if state["status"] == "stale":
        return state["error"]
    return f"마지막 연결 검사가 실패했습니다 — {state.get('error') or '사유 없음'}"


def selectable(store, tenant_id: str) -> dict:
    """서버별 상태 · 선택 가능 여부 · 도구별 선택 가능 여부(사유). 에이전트 users.tools 에는 서버 이름(agent_value)을 적는다.
    「에이전트에 붙일 수 있나」는 이 함수 하나가 정한다 — 도구 지도(annotate) · 에이전트 폼(agent_authoring.server_options) ·
    저장 검사(refuse_reasons)가 모두 이 결과를 쓴다."""
    servers = store.servers(tenant_id)
    records = store.checks(tenant_id)
    out, picks = [], []
    for name, entry in servers.items():
        try:
            spec = mcp_check.normalize(entry)
            entry_error = None
        except ValueError as e:
            spec, entry_error = {}, f"설정 오류 — {e}"
        state = check_state(name, entry, records.get(name))
        origin = origin_of(name, entry)
        # 기준 서버(seed)는 기본 에이전트가 이미 쓰는 구성 — 워커가 기본 허용 목록으로 실행하므로 포털 연결 검사 없이 고를 수 있다
        # (연결 검사를 눌렀다면 그 결과는 상태로 보일 뿐 고를 수 있음을 바꾸지 않는다)
        reason = None if origin == "seed" and not entry_error else _not_selectable_reason(state, entry_error)
        confirmed = confirmed_of(entry)
        tools = []
        for t in (records.get(name) or {}).get("tools") or []:
            readable = counts_as_read(t, confirmed)
            if reason:
                ok, why = False, reason
            else:
                ok, why = readable, (None if readable else
                                     "에이전트에는 읽기 전용 도구만 붙입니다 — " + (t.get("reason") or "읽기 전용 표시가 없습니다"))
            tools.append({"name": t["name"], "title": t.get("title"), "description": t.get("description") or "", "read_only": bool(t.get("read_only")),
                          "confirmable": bool(t.get("confirmable")) and not t.get("read_only"),
                          "confirmed": (confirmed.get(t["name"]) if readable and not t.get("read_only") else None),
                          "selectable": ok, "reason": why, "tool_id": f"mcp__{name}__{t['name']}"})
            if ok:
                picks.append({"server": name, "tool": t["name"], "tool_id": f"mcp__{name}__{t['name']}"})
        if not reason and origin != "seed" and not any(t["selectable"] for t in tools):
            reason = ("읽기 전용(readOnlyHint=true)으로 표시한 도구가 없습니다 — 에이전트에 붙일 도구가 없습니다"
                      + (" (표시만 없는 도구는 '읽기로 확인'하면 붙일 수 있습니다)" if any(t["confirmable"] for t in tools) else ""))
        out.append({"name": name, "origin": origin, "origin_text": ORIGIN_WORDS[origin], "mine": origin != "seed", "editable": origin != "seed",
                    "transport": spec.get("transport"), "check": state, "selectable": reason is None, "reason": reason, "agent_value": name,
                    "description": entry.get("description") if isinstance(entry, dict) else None,
                    "read_confirmed": sorted(confirmed),                       # G2 ②: 강사가 읽기로 확인한 도구(이름만)
                    "secrets": mcp_secrets.references(entry), "tools": tools})  # G2 ①: 이 서버가 쓰는 비밀 이름(값 아님)
    return {"tenant": tenant_id, "servers": out, "selectable_tools": picks,
            "rule": "연결 검사를 통과했고 그 뒤 설정이 바뀌지 않은 서버의, 서버가 읽기 전용(readOnlyHint=true)으로 표시한 도구(또는 표시가 없어 "
                    "읽기로 확인한 도구)만 고를 수 있습니다. 에이전트에는 서버 이름을 적고, 실행 때 워커가 읽기 전용 도구만 허용합니다."}


def refuse_reasons(store, tenant_id: str, server_names) -> list[str]:
    """에이전트 저장 전 검사(B1): 고른 서버 이름마다 붙일 수 없는 사유. 빈 목록이면 모두 붙일 수 있다."""
    view = {s["name"]: s for s in selectable(store, tenant_id)["servers"]}
    out = []
    for n in server_names or []:
        s = view.get(n)
        if s is None:
            out.append(f"{n}: 등록되지 않은 도구 서버입니다")
        elif not s["selectable"]:
            out.append(f"{n}: {s['reason']}")
    return out


# ---------------------------------------------------------------- 동작 (API 가 부른다)
def agents_using(repo, tenant_id: str, name: str) -> list[str]:
    from .agents_store import csv_list
    return [u.get("username") or u["id"] for u in repo.list_users(None, tenant_id) if u.get("is_agent") and name in csv_list(u.get("tools"))]


def _validate_name(name) -> str:
    name = str(name or "").strip()
    if not NAME_RE.match(name):
        raise RegistryError(422, "name: 소문자 · 숫자 · 하이픈(-)으로 1~40자, 첫 글자는 소문자나 숫자여야 합니다 (예: my-folder)")
    return name


def _now() -> str:
    return mcp_check._now_z()


def secrets_of(store, tenant_id: str, entry: dict) -> dict:
    """G2: 검사 직전에 채울 비밀 값(비밀 값 표). 값은 이 함수 밖으로 응답에 실리지 않는다.
    자리표시자가 없는 설정이면 표를 읽지 않는다(비밀 값 표가 없을 때도 비밀 없는 서버 검사는 그대로 된다)."""
    if not mcp_secrets.references(entry):
        return {}
    return mcp_secrets.load(store.repo, tenant_id)


def warnings_of(entry: dict) -> list[str]:
    """비밀처럼 보이는 칸에 값을 그대로 넣었으면 ${SECRET:KEY} 로 바꾸라는 경고(거절하지 않는다 — 기존 랩업 서버와 호환)."""
    found = mcp_secrets.literal_secrets(entry)
    return [f"{' · '.join(found)}: 비밀 값을 설정에 그대로 넣었습니다 — 값은 '비밀 값'에 넣고 설정에는 ${{SECRET:이름}} 을 쓰세요 "
            "(설정은 내보내기 · 도구 지도에 실립니다)"] if found else []


SAVE_STEP = ("save", "검사 결과 저장")


def _saved(progress, record: dict, write) -> None:
    """검사 뒤의 저장. 연결한 검사면 진행 기록의 저장 단계로 적는다(비밀 값이 없어 연결하지 않은 검사는 run_check 가 단계를 적지 않았다)."""
    if record.get("error_kind") == "secret":
        write()
        return
    progress.start(SAVE_STEP[0])
    write()
    progress.done(SAVE_STEP[0])


def dry_check(store, tenant_id: str, body: dict, *, progress=progress_log.SILENT) -> dict:
    """등록 전 검사: 저장 없이 형식 → 연결 → 도구 판정."""
    entry = entry_from_body(body)
    record = run_check(entry, _check_limit(body.get("timeout")), secrets_of(store, tenant_id, entry), progress=progress)
    return {"check": record, "config": mcp_check.masked(mcp_check.normalize(entry)), "gate": gate_of(record) if record["status"] == "ok" else None,
            "warnings": warnings_of(entry)}


def _require_pass(record: dict, verb: str) -> None:
    if record["status"] != "ok":
        raise RegistryError(422, f"연결 검사 실패로 {verb} 않았습니다 — {record.get('error') or '사유 없음'}", check=record)


def register(store, tenant_id: str, body: dict, by: str, *, progress=progress_log.SILENT) -> dict:
    name = _validate_name((body or {}).get("name"))
    if name in BASE_SERVERS:
        raise RegistryError(409, f"'{name}' 는 기준(기본 제공) 서버 이름입니다 — 다른 이름을 쓰세요")
    if name in store.servers(tenant_id):
        raise RegistryError(409, f"'{name}' 서버가 이미 있습니다 — 고치기를 쓰거나 다른 이름을 쓰세요")
    entry = entry_from_body(body)
    record = run_check(entry, _check_limit(body.get("timeout")), secrets_of(store, tenant_id, entry), progress=progress, then=(SAVE_STEP,))
    _require_pass(record, "등록하지")
    now = _now()
    entry[META_KEY] = {"origin": "user", "created_at": now, "updated_at": now, "by": by, "gate": gate_of(record)}

    def write():
        if not store.insert_server(tenant_id, name, entry):
            raise RegistryError(409, f"'{name}' 서버가 이미 있습니다")
        store.save_check(tenant_id, name, record, by)
    _saved(progress, record, write)
    return {"name": name, "check": record, "gate": entry[META_KEY]["gate"], "warnings": warnings_of(entry)}


def update(store, tenant_id: str, name: str, body: dict, by: str, *, progress=progress_log.SILENT) -> dict:
    if name in BASE_SERVERS:
        raise RegistryError(403, f"'{name}' 는 기준(기본 제공) 서버라 고칠 수 없습니다 — 새 이름으로 등록해 쓰세요")
    servers = store.servers(tenant_id)
    old = servers.get(name)
    if old is None:
        raise RegistryError(404, f"MCP 서버 '{name}' 가 없습니다")
    entry = entry_from_body(body, old if isinstance(old, dict) else {})
    record = run_check(entry, _check_limit(body.get("timeout")), secrets_of(store, tenant_id, entry), progress=progress, then=(SAVE_STEP,))
    _require_pass(record, "고치지")
    old_meta = old.get(META_KEY) if isinstance(old, dict) and isinstance(old.get(META_KEY), dict) else {}
    confirmed = confirmed_of(old)                                      # 강사 확인은 도구 이름에 붙는다 — 고쳐도 남고, 도장은 새 검사로 다시 계산
    now = _now()
    entry[META_KEY] = {"origin": old_meta.get("origin") or "external", "created_at": old_meta.get("created_at") or now, "updated_at": now,
                       "by": by, "gate": gate_of(record, confirmed)}
    if confirmed:
        entry[META_KEY]["read_confirmed"] = confirmed

    def write():
        if not store.replace_server(tenant_id, name, entry):
            raise RegistryError(404, f"MCP 서버 '{name}' 가 없습니다")
        store.save_check(tenant_id, name, record, by)
    _saved(progress, record, write)
    return {"name": name, "check": record, "gate": entry[META_KEY]["gate"], "warnings": warnings_of(entry)}


def flow_step_text(step: dict) -> str:
    """흐름 단계 한 줄(지우기 거절 문장 · 감사): 「흐름 이름」 판본 n 의 「단계 이름」(도구 x) + 진행 중인 처리 건 수."""
    live = f" · 진행 중인 처리 건 {step['running']}건" if step.get("running") else ""
    return f"「{step['definition_name']}」 판본 {step['version']}의 「{step['activity_name']}」(도구 {step['tool'] or '미정'}{live})"


def remove(store, repo, tenant_id: str, name: str, *, force: bool = False) -> dict:
    """학생 서버 하나를 지운다. 이 서버를 쓰는 것이 있으면 force 없이는 지우지 않는다(409 — 쓰는 에이전트와 흐름 단계를 함께 말한다):
    에이전트의 도구 목록, 그리고 흐름의 「승인 뒤 MCP 호출」 단계(mcp_dependencies.steps_using — 도구 지도의 쓰임과 같은 판정).
    전에는 에이전트만 봐서, 흐름 단계가 부르는 서버를 지우면 그 흐름이 실행 때에야 멈췄다."""
    if name in BASE_SERVERS:
        raise RegistryError(403, f"'{name}' 는 기준(기본 제공) 서버라 지울 수 없습니다")
    if name not in store.servers(tenant_id):
        raise RegistryError(404, f"MCP 서버 '{name}' 가 없습니다")
    from . import mcp_dependencies
    users = agents_using(repo, tenant_id, name)
    steps = mcp_dependencies.steps_using(repo, tenant_id, [name])[name]
    if (users or steps) and not force:
        from hydcommon.words import josa
        uses = ([f"에이전트 {josa(', '.join(users), '가')} 이 서버를 도구로 쓰고"] if users else []) + \
               ([f"흐름 단계 {josa(' · '.join(flow_step_text(s) for s in steps), '가')} 이 서버의 도구를 부르고"] if steps else [])
        raise RegistryError(409, f"{', '.join(uses)} 있습니다 — 에이전트 · 흐름에서 먼저 빼거나 강제로 지우세요"
                                 "(강제로 지우면 그 흐름 단계는 실행될 때 서버가 없다는 까닭으로 멈춥니다)")
    store.delete_server(tenant_id, name)
    store.delete_checks(tenant_id, [name])
    from .student_cases import Store
    Store(repo, tenant_id).remove('mcp_servers', name)
    return {"name": name, "deleted": True, "agents_still_naming_it": users, "flow_steps_still_calling_it": steps}


def check_saved(store, tenant_id: str, name: str, *, timeout=None, by: str, progress=progress_log.SILENT) -> dict:
    """등록된 서버 검사: 기록을 남기고, 학생 서버면 워커 도장(hyd.gate)을 고친다. 기준 서버 설정(tenants.mcp)은 바꾸지 않는다."""
    entry = store.servers(tenant_id).get(name)
    if entry is None:
        raise RegistryError(404, f"MCP 서버 '{name}' 가 없습니다")
    try:
        record = run_check(entry, _check_limit(timeout), secrets_of(store, tenant_id, entry), student=origin_of(name, entry) != "seed",
                           progress=progress, then=(SAVE_STEP,))
    except ValueError as e:
        raise RegistryError(422, f"MCP 서버 '{name}' 설정 오류 — {e}")

    def write():
        store.save_check(tenant_id, name, record, by)
        if origin_of(name, entry) != "seed":
            meta = dict(entry.get(META_KEY) or {}) if isinstance(entry.get(META_KEY), dict) else {}
            meta.setdefault("origin", "external")
            if record["status"] == "ok":
                meta["gate"] = gate_of(record, confirmed_of(entry))
            else:
                meta.pop("gate", None)                        # 실패한 서버는 워커가 연결하지 않는다
            store.set_meta(tenant_id, name, meta)
    _saved(progress, record, write)
    return {"name": name, "check": record, "state": check_state(name, entry, record)}


def confirm_read(store, tenant_id: str, name: str, tool: str, *, on: bool = True, by: str = "", reason: str = "") -> dict:
    """G2 ②: 강사가 readOnlyHint 표시가 없는 도구를 "읽기"로 확인(on) · 확인 취소(off). 확인자 · 이유가 있어야 하고,
    마지막 검사가 지금 설정에 대해 통과했어야 하며, 그 검사에서 confirmable(표시 없음뿐 · 이름이 쓰기 아님)이었던 도구만 된다.
    확인하면 워커 도장(hyd.gate)을 다시 계산한다 — 그 도구가 read_tools 로 옮겨 간다.
    취소(off)는 믿음을 거두는 쪽이라 검사가 낡았어도 받는다: 지금 설정으로 통과한 검사가 없으면 도장을 내려(워커가 이 서버를
    띄우지 않는다) 다음 연결 검사가 확인 목록으로 도장을 다시 계산하게 한다."""
    if name in BASE_SERVERS:
        raise RegistryError(403, f"'{name}' 는 기준(기본 제공) 서버라 도구 판정을 바꿀 수 없습니다")
    entry = store.servers(tenant_id).get(name)
    if not isinstance(entry, dict):
        raise RegistryError(404, f"MCP 서버 '{name}' 가 없습니다")
    by, reason = str(by or "").strip()[:60], str(reason or "").strip()[:300]
    if on and (not by or not reason):
        raise RegistryError(422, "확인한 사람(by)과 읽기라고 본 이유(reason)를 적어야 합니다 — 도구 설명 · 서버 문서에서 쓰기가 없는지 본 근거")
    record = store.checks(tenant_id).get(name)
    passed = record is not None and record.get("status") == "ok" and record.get("fingerprint") == fingerprint(entry)
    confirmed = confirmed_of(entry)
    if on:
        if not passed:
            raise RegistryError(409, "지금 설정으로 통과한 연결 검사가 없습니다 — '연결 검사'를 먼저 하세요")
        found = next((t for t in record.get("tools") or [] if t.get("name") == tool), None)
        if found is None:
            raise RegistryError(404, f"마지막 검사의 도구 목록에 '{tool}' 가 없습니다")
        if found.get("read_only"):
            raise RegistryError(409, f"'{tool}' 는 서버가 이미 읽기 전용으로 표시했습니다 — 확인할 필요가 없습니다")
        if not found.get("confirmable"):
            raise RegistryError(422, f"'{tool}' 는 읽기로 확인할 수 없습니다 — {found.get('reason') or '쓰기 도구'} "
                                     "(서버가 쓰기로 표시했거나 이름이 쓰기 · 실행을 뜻하는 도구는 승인 뒤 시스템 task 로만 씁니다)")
        confirmed[tool] = {"by": by, "reason": reason, "at": _now()}
    elif confirmed.pop(tool, None) is None:
        raise RegistryError(404, f"'{tool}' 는 읽기로 확인한 도구가 아닙니다")
    meta = dict(entry.get(META_KEY) or {})
    meta.setdefault("origin", "external")
    meta["read_confirmed"] = confirmed
    if passed:
        meta["gate"] = gate_of(record, confirmed)
    else:
        meta.pop("gate", None)
    if not confirmed:
        meta.pop("read_confirmed")
    store.set_meta(tenant_id, name, meta)
    return {"name": name, "tool": tool, "confirmed": on, "read_confirmed": confirmed, "gate": meta.get("gate")}


def reset(store, tenant_id: str, *, secrets: bool = True) -> dict:
    """기준으로 되돌리기: 기준 서버가 아닌 서버(포털 등록 · 포털 밖 추가)와 검사 기록을 모두 지운다. 기준 서버의 설정은 그대로.
    secrets=True(도구 연결 화면 · 관리 탭의 [기준으로 되돌리기]): 비밀 값(mcp_secrets)도 지운다 — 수업 뒤 자격 증명이 남지 않게.
    비밀 값을 먼저 지운다: 표가 없어 실패하면(503) 서버도 지우지 않은 채 멈춘다(반만 되돌린 상태를 남기지 않는다).
    secrets=False(출발본 불러오기 안의 되돌리기 · 실패 복원): 비밀 값은 구성이 아니라 이 PC 의 자격 증명이라 남긴다 —
    불러온 서버의 ${SECRET:이름} 이 같은 값을 다시 쓴다."""
    removed_secrets = mcp_secrets.store_for(store.repo).delete_all(tenant_id) if secrets else 0
    removed = [n for n in store.servers(tenant_id) if n not in BASE_SERVERS]
    for n in removed:
        store.delete_server(tenant_id, n)
    from .student_cases import Store
    Store(store.repo, tenant_id).remove('mcp_servers')
    return {"removed_servers": removed, "removed_checks": store.delete_checks(tenant_id), "removed_secrets": removed_secrets,
            "kept": [n for n in store.servers(tenant_id)]}


def snapshot(store, tenant_id: str) -> dict:
    """되돌리기 전 MCP 구성의 저장소 행 그대로: 학생 서버 칸(HYD 표시 · 검사 도장 포함)과 모든 검사 기록.
    출발본 불러오기가 실패하면 restore 로 이 행을 그대로 다시 쓴다 — 실시간 연결 검사를 다시 하지 않는다(그 순간 서버가 꺼져 있거나
    비밀 값이 바뀌어도 학생 구성이 사라지지 않게 — P3-01)."""
    return {"servers": {n: e for n, e in store.servers(tenant_id).items() if n not in BASE_SERVERS},
            "checks": store.checks(tenant_id)}


def restore(store, tenant_id: str, snap: dict, by: str) -> list[str]:
    """snapshot 의 행을 그대로 다시 쓴다(지금 학생 서버가 없어야 한다 — 되돌리기 뒤에 부른다). 다시 쓴 서버 이름 목록."""
    left = [n for n in store.servers(tenant_id) if n not in BASE_SERVERS]
    if left:
        raise RegistryError(409, f"되돌리기 뒤에도 학생 서버가 남아 있어 보관본을 다시 쓰지 않았습니다: {', '.join(left)}")
    for name, entry in (snap.get("servers") or {}).items():
        if not store.insert_server(tenant_id, name, entry):
            raise RegistryError(409, f"보관본의 '{name}' 서버를 다시 쓰지 못했습니다 — 같은 이름이 이미 있습니다")
    for name, record in (snap.get("checks") or {}).items():
        store.save_check(tenant_id, name, record, record.get("checked_by") or by)
    return sorted(snap.get("servers") or {})


def annotate(store, tenant_id: str) -> dict[str, dict]:
    """도구 지도(GET /api/mcp/servers)에 붙일 칸: 출처 · 고칠 수 있음 · 마지막 검사 상태 · 에이전트에 붙일 수 있음(selectable 한 판정)."""
    keys = ("origin", "origin_text", "mine", "editable", "check", "selectable", "reason", "description", "read_confirmed", "secrets")
    return {s["name"]: {k: s[k] for k in keys} for s in selectable(store, tenant_id)["servers"]}


# ---------------------------------------------------------------- HTTP
def mount(app, *, runtime_factory, audit):
    import asyncio

    from fastapi import HTTPException

    def runtime():
        rt = runtime_factory()
        if rt is None:
            from .instances import NOT_READY      # 런타임 모듈 — 이 모듈이 먼저 읽혀도 순환 import 가 되지 않게 여기서
            raise HTTPException(503, NOT_READY)
        return rt

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except RegistryError as e:
            raise HTTPException(e.status, {"reason": e.reason, "check": e.check} if e.check is not None else e.reason) from e
        except mcp_secrets.SecretError as e:                  # 비밀 값 표를 읽지 못함(503) — 500 이 아니라 사유로
            raise HTTPException(e.status, e.reason) from e

    def by_of(body) -> str:
        from .inbox import actor_or_400
        return actor_or_400((body or {}).get("by"))[:60]

    def note(action, name, by, extra):
        audit("-", by, action, dict({"server": name}, **extra))

    @app.get("/api/mcp/selectable")
    async def selectable_route():
        rt = runtime()
        return await run(lambda: selectable(store_for(rt.repo), rt.tenant_id))

    def tracked(body, kind: str, work):
        return progress_log.tracked((body or {}).get("request_id"), kind, work)

    @app.post("/api/mcp/check")
    async def dry_check_route(body: dict | None = None):
        rt = runtime()
        out = await run(tracked(body, "mcp_check", lambda p: dry_check(store_for(rt.repo), rt.tenant_id, body or {}, progress=p)))
        return out

    @app.post("/api/mcp/servers", status_code=201)
    async def register_route(body: dict | None = None):
        rt = runtime()
        by = by_of(body)

        def work(p):
            try:
                out = register(store_for(rt.repo), rt.tenant_id, body or {}, by, progress=p)
            except RegistryError as e:
                note("MCP_SERVER_REJECTED", str((body or {}).get("name") or ""), by, {"reason": e.reason})
                raise
            note("MCP_SERVER_REGISTERED", out["name"], by, {"tools": len(out["check"]["tools"]), "read_tools": out["gate"]["read_tools"]})
            return out
        return await run(tracked(body, "mcp_register", work))

    @app.put("/api/mcp/servers/{name}")
    async def update_route(name: str, body: dict | None = None):
        rt = runtime()
        by = by_of(body)

        def work(p):
            try:
                out = update(store_for(rt.repo), rt.tenant_id, name, body or {}, by, progress=p)
            except RegistryError as e:
                note("MCP_SERVER_REJECTED", name, by, {"reason": e.reason})
                raise
            note("MCP_SERVER_UPDATED", name, by, {"read_tools": out["gate"]["read_tools"]})
            return out
        return await run(tracked(body, "mcp_update", work))

    @app.delete("/api/mcp/servers/{name}")
    async def delete_route(name: str, force: bool = False, by: str = ""):
        from .inbox import actor_or_400
        by = actor_or_400(by)[:60]
        rt = runtime()

        def work():
            out = remove(store_for(rt.repo), rt.repo, rt.tenant_id, name, force=force)
            note("MCP_SERVER_DELETED", name, by[:60], {"force": force})
            return out
        return await run(work)

    @app.post("/api/mcp/servers/{name}/check")
    async def check_route(name: str, body: dict | None = None):
        rt = runtime()
        by = by_of(body)
        return await run(tracked(body, "mcp_check_saved", lambda p: check_saved(store_for(rt.repo), rt.tenant_id, name,
                                                                                timeout=(body or {}).get("timeout"), by=by, progress=p)))

    @app.post("/api/mcp/servers/{name}/read-confirm")
    async def read_confirm_route(name: str, body: dict | None = None):
        """G2 ②: {tool, on(기본 true), by, reason} — 강사가 표시 없는 도구를 읽기로 확인 · 취소."""
        rt = runtime()
        body = body or {}
        on = body.get("on", True)
        if not isinstance(on, bool):                          # "false" 같은 글자를 확인(on)으로 읽지 않는다
            raise HTTPException(422, "on: true(확인) 또는 false(취소)여야 합니다")

        def work():
            out = confirm_read(store_for(rt.repo), rt.tenant_id, name, str(body.get("tool") or ""), on=on,
                               by=body.get("by") or "", reason=body.get("reason") or "")
            note("MCP_READ_CONFIRMED" if out["confirmed"] else "MCP_READ_UNCONFIRMED", name, by_of(body),
                 {"tool": out["tool"], "reason": str(body.get("reason") or "")[:300]})
            return out
        return await run(work)

    @app.post("/api/mcp/reset")
    async def reset_route(body: dict | None = None):
        rt = runtime()

        def work():
            out = reset(store_for(rt.repo), rt.tenant_id)
            note("MCP_RESET", "*", by_of(body), out)
            return out
        return await run(work)
