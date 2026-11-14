"""U3 — 도구 지도 · 도구 써 보기 · 호출 기록 API (읽기 전용). 등록 · 고치기 · 지우기 · 연결 검사 · 되돌리기는 mcp_registry.py.

설정 원천은 public.tenants.mcp 하나다(워커 bridge.py 가 읽는 제품 형태 — mcp_registry.PgMcpStore.servers 로 읽는다).

  GET  /api/mcp/servers                         서버 → 설정(비밀값 가림) → 이 서버로 실제로 도는 에이전트 단계 · 담당 · 이 서버를 부르는 흐름 단계.
                                                네트워크 연결 없음.
  GET  /api/mcp/servers/{name}/tools?timeout=   지금 연결해 상태 · 도구 목록(이름 · 설명 · 입력 형식 · 읽기 전용 판정). 저장 없음.
  POST /api/mcp/servers/{name}/tools/{tool}/call {arguments, timeout?}
                                                읽기 전용 도구만 실제 호출. 쓰기 · 표시 없음 → 403 사유, 연결 실패 → 502 사유.
  GET  /api/mcp/calls?server=&tool=&limit=      events 의 도구 호출 기록(처리 건 · task · 입력 · 결과 요약 · 시각 · 링크).

비밀값: 접속 헤더의 비밀 값 · 주소의 비밀번호 · 입력 · 결과 안의 비밀번호 꼴은 '********'.
포털이 여는 연결은 mcp_check.portal_slot 으로 동시에 PORTAL_SLOTS 개까지(연결 검사 · 등록과 같은 자리).
"""
from __future__ import annotations

import asyncio

from fastapi import HTTPException

from . import mcp_calls, mcp_check, mcp_registry, mcp_secrets

LIST_TIMEOUT = (0.5, 6.0, 4.0)                  # (최소, 최대, 기본) 초 — 포털 GET 8초 제한 안
CALL_TIMEOUT = (0.5, 25.0, 15.0)                # 포털 POST 30초 제한 안
CALL_RESULT_CHARS = 200_000                     # 도구 써 보기 · 질문 에이전트 조회 결과의 글자 수 상한(넘으면 truncated)


def _timeout(raw, bounds) -> float:
    low, high, default = bounds
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise HTTPException(400, "timeout: 초 단위 숫자여야 합니다")
    if not low <= value <= high:
        raise HTTPException(400, f"timeout: {low:g}~{high:g}초 사이여야 합니다")
    return value


def usage(rt, server_names: list[str]) -> dict[str, dict]:
    """서버 이름 → {agents: [{id, name, goal}], tasks: [{definition, definition_name, version, activity_id, activity_name, agent, fixed_tools}],
    flow_steps: [{definition, definition_name, version, activity_id, activity_name, tool, read_check, latest, running}]}.
    tasks: 이 서버로 실제로 도는 에이전트 단계 — agents_api.step_runs(배정 반영 + 워커와 같은 agent_settings · run_servers)를 그대로 읽는다.
    agents: 에이전트 자신의 설정(단계 밖)이 이 서버를 쓰는 에이전트(도구를 적지 않은 에이전트는 등록된 서버 전부).
    flow_steps: 이 서버의 도구를 부르는 흐름 단계(「승인 뒤 MCP 호출」 · 읽기 확인) — mcp_dependencies.steps_using(지우기 전 확인과 같은 판정)."""
    from . import mcp_dependencies
    from .agents_api import step_runs
    from .agents_store import agent_settings, run_servers
    steps = mcp_dependencies.steps_using(rt.repo, rt.tenant_id, server_names)
    out = {n: {"agents": [], "tasks": [], "flow_steps": steps[n]} for n in server_names}
    for u in rt.repo.list_users(None, rt.tenant_id):
        if not u.get("is_agent") or (u.get("agent_type") or "agent") != "agent":
            continue
        for n in run_servers(agent_settings(rt.repo, rt.tenant_id, u).tools, server_names):
            out[n]["agents"].append({"id": u["id"], "name": u.get("username") or u["id"], "goal": u.get("goal")})
    for s in step_runs(rt):
        for n, fixed in s["servers"].items():
            if n in out:
                out[n]["tasks"].append({"definition": s["definition_id"], "definition_name": s["definition_name"], "version": s["version"],
                                        "activity_id": s["activity_id"], "activity_name": s["name"], "agent": s["agent_name"],
                                        "fixed_tools": fixed})
    return out


def server_view(name: str, raw) -> dict:
    """설정 한 칸 → 화면용(비밀값 가림). 손편집 · 옛 형식(명령형)으로 깨진 칸도 사유와 함께 줄로 남는다(목록이 통째로 죽지 않는다)."""
    try:
        spec = mcp_check.normalize(raw)
    except ValueError as e:
        return {"name": name, "transport": None, "url": None, "headers": {}, "config_error": f"설정 오류 — {e}"}
    shown = mcp_check.masked(spec)
    return {"name": name, "transport": spec["transport"], "url": shown.get("url"), "headers": shown.get("headers") or {}, "config_error": None}


def register(app, *, runtime_factory, audit):
    def runtime():
        rt = runtime_factory()
        if rt is None:
            from .instances import NOT_READY      # 런타임 모듈 — 이 모듈이 먼저 읽혀도 순환 import 가 되지 않게 여기서
            raise HTTPException(503, NOT_READY)
        return rt

    def servers_of(rt) -> dict:
        return mcp_registry.store_for(rt.repo).servers(rt.tenant_id)

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except mcp_registry.RegistryError as e:
            raise HTTPException(e.status, e.reason) from e
        except mcp_secrets.SecretError as e:
            raise HTTPException(e.status, e.reason) from e
        except KeyError as exc:
            raise HTTPException(404, str(exc.args[0]) if exc.args else "찾을 수 없습니다") from exc

    def spec_of(rt, name: str) -> tuple[dict, list[str]]:
        """(부를 설정, 채운 비밀 값) — 비밀 값은 결과 · 오류 · 감사에서 지우는 데만 쓴다(mcp_secrets.redact)."""
        raw = servers_of(rt).get(name)
        if raw is None:
            raise KeyError(f"MCP 서버 '{name}' 가 설정(tenants.mcp)에 없습니다")
        try:
            mcp_check.normalize(raw)
        except ValueError as e:
            raise HTTPException(422, f"MCP 서버 '{name}' 설정 오류 — {e}")
        resolved, used = mcp_secrets.runtime_spec(rt.repo, rt.tenant_id, name, raw)   # G2: 부르기 직전에만 채운다(응답에는 싣지 않는다)
        return mcp_check.normalize(resolved), used

    def in_slot(limit, fn):
        """포털 연결 자리(mcp_check.portal_slot)를 얻어 부른다. 자리가 나지 않으면 503 — 서버 탓이 아니므로 결과로 꾸미지 않는다."""
        try:
            with mcp_check.portal_slot(limit):
                return fn()
        except mcp_check.CheckError as e:
            raise HTTPException(503, e.message) from e

    @app.get("/api/mcp/servers")
    async def list_servers():
        rt = runtime()

        def work():
            servers = servers_of(rt)
            used = usage(rt, list(servers))
            marks = mcp_registry.annotate(mcp_registry.store_for(rt.repo), rt.tenant_id)   # B2: 출처 · 고칠 수 있음 · 마지막 검사 · 붙일 수 있음
            return {"tenant": rt.tenant_id, "source": "tenants.mcp", "list_timeout_s": LIST_TIMEOUT[2],
                    "servers": [dict(server_view(n, raw), **used[n], **marks[n]) for n, raw in servers.items()]}
        return await run(work)

    @app.get("/api/mcp/servers/{name}/tools")
    async def server_tools(name: str, timeout: float | None = None):
        rt = runtime()
        limit = _timeout(timeout, LIST_TIMEOUT)

        def work():
            spec, used = spec_of(rt, name)
            return mcp_secrets.redact(in_slot(limit, lambda: mcp_check.check(spec, limit)), used)
        result = await run(work)
        return {"name": name, "timeout_s": limit, **{k: result[k] for k in ("status", "tools", "error", "error_kind", "checked_at",
                                                                           "elapsed_ms", "server_info", "protocol_version", "transport")}}

    @app.post("/api/mcp/servers/{name}/tools/{tool}/call")
    async def call_tool(name: str, tool: str, body: dict | None = None):
        rt = runtime()
        body = body or {}
        from .inbox import actor_or_400
        by = actor_or_400(body.get("by"))      # 도구를 부르기 전에 확인한다(부른 뒤 거절하지 않는다)
        arguments = body.get("arguments", {})
        if not isinstance(arguments, dict):
            raise HTTPException(400, "arguments: 이름→값 객체여야 합니다")
        limit = _timeout(body.get("timeout"), CALL_TIMEOUT)

        def work():
            spec, used = spec_of(rt, name)
            confirmed = frozenset(mcp_registry.confirmed_of(servers_of(rt).get(name)))   # G2 ②: 강사가 읽기로 확인한 도구 — 써 보기도 같은 판정
            return mcp_secrets.redact(in_slot(limit, lambda: mcp_check.call(spec, tool, arguments, limit, max_chars=CALL_RESULT_CHARS,
                                                                            confirmed=confirmed)), used)
        result = await run(work)
        audit("-", by, "MCP_TOOL_TRIED",
              {"server": name, "tool": tool, "status": result["status"], "error": result.get("error"),
               "arguments": mcp_calls.brief(mcp_check.mask_value(arguments), 300)})
        if result["status"] == "refused":
            status = {"not_read_only": 403, "no_tool": 404, "input": 422, "input_schema": 502}.get(result.get("error_kind"), 404)
            raise HTTPException(status, result["error"])
        if result["status"] != "ok":
            raise HTTPException(502, f"{name}: {result['error']}")
        return {"server": name, "tool": tool, "arguments": mcp_check.mask_value(arguments), "result": result["result"],
                "elapsed_ms": result["elapsed_ms"], "checked_at": result["checked_at"], "server_info": result["server_info"]}

    @app.get("/api/mcp/calls")
    async def tool_calls(server: str | None = None, tool: str | None = None, limit: int = 50):
        rt = runtime()
        if not 1 <= limit <= 200:
            raise HTTPException(400, "limit: 1~200 사이여야 합니다")

        def work():
            rows = mcp_calls.recent_tool_events(rt.repo)
            return {"calls": mcp_calls.calls(rows, server=server, tool=tool, limit=limit), "scanned": len(rows),
                    "scan_limit": mcp_calls.SCAN_LIMIT}
        return await run(work)
