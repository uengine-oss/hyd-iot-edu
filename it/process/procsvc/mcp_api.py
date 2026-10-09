"""U3 (A2 MCP 부분) — 도구 지도 · 도구 써 보기 · 호출 기록 API (읽기 전용).

설정 원천은 public.tenants.mcp 하나다(워커 bridge.py 가 읽는 제품 형태). 랩업(Claude Code)에서 서버를 추가하면 같은 칸에
들어가므로 여기 그대로 나타난다. B2(DECISIONS 110 ①)부터 등록 · 고치기 · 지우기 · 연결 검사 · 되돌리기는 procsvc/mcp_registry.py 에 있다
(이 모듈의 읽기 경로는 그대로, 목록에 출처 · 마지막 검사 칸만 더한다).

  GET  /api/mcp/servers                         서버 → 설정(비밀값 가림) → 쓰는 에이전트 · 맡은 task. 네트워크 연결 없음.
  GET  /api/mcp/servers/{name}/tools?timeout=   지금 연결해 상태 · 도구 목록(이름 · 설명 · 입력 형식 · 읽기 전용 판정). 저장 없음.
  POST /api/mcp/servers/{name}/tools/{tool}/call {arguments, timeout?}
                                                읽기 전용 도구만 실제 호출. 쓰기 · 표시 없음 → 403 사유, 연결 실패 → 502 사유.
  GET  /api/mcp/calls?server=&tool=&limit=      events 의 도구 호출 기록(처리 건 · task · 입력 · 결과 요약 · 시각 · 링크).

비밀값: env · headers 의 비밀 이름(pass · token · key · auth · dsn …) · 주소의 비밀번호 · 입력 · 결과 안의 비밀번호 꼴은 '********'.
"""
from __future__ import annotations

import asyncio
import json
import re

from fastapi import HTTPException

from . import mcp_calls, mcp_check, mcp_registry, mcp_secrets

CALL_SEMAPHORE = asyncio.Semaphore(3)           # 동시에 세 연결까지만 — 스레드 풀과 메모리(A131)를 지킨다
LIST_TIMEOUT = (0.5, 6.0, 4.0)                  # (최소, 최대, 기본) 초 — 포털 GET 8초 제한 안
CALL_TIMEOUT = (0.5, 25.0, 15.0)                # 포털 POST 30초 제한 안


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


def _names(raw) -> list[str]:
    """users.tools · activity.tools: 'a,b' 문자열이나 목록 → 이름 목록."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw) if raw.strip().startswith("[") else None
        except ValueError:
            parsed = None
        raw = parsed if isinstance(parsed, list) else raw.split(",")
    if isinstance(raw, dict):
        raw = list(raw)
    return [str(x).strip() for x in raw if str(x).strip()] if isinstance(raw, list) else []


def _version_key(v) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", str(v or ""))) or (0,)


def usage(repo, tenant_id: str, server_names: list[str]) -> dict[str, dict]:
    """서버 이름 → {agents: [{id, name, declared}], tasks: [{definition, definition_name, version, activity_id, activity_name, agent, declared}]}.
    agents: users.is_agent 의 tools 칸에 이 서버가 있는 에이전트. tasks: 정의(판본마다 가장 새 판본)의 에이전트 단계 —
    단계가 tools 를 적었으면 그 서버만, 안 적었으면 테넌트 서버 전부(워커 bridge.select_servers 와 같은 규칙, declared=false)."""
    out = {n: {"agents": [], "tasks": []} for n in server_names}
    users = repo.list_users(None, tenant_id)
    agents = {u["id"]: u for u in users if u.get("is_agent") and (u.get("agent_type") or "agent") == "agent"}
    for u in agents.values():
        for n in _names(u.get("tools")):
            if n in out:
                out[n]["agents"].append({"id": u["id"], "name": u.get("username") or u["id"], "goal": u.get("goal")})
    latest: dict[str, dict] = {}
    for d in repo.list_definitions(tenant_id):
        cur = latest.get(d["id"])
        if cur is None or _version_key(d.get("prod_version")) >= _version_key(cur.get("prod_version")):
            latest[d["id"]] = d
    for d in latest.values():
        definition = d.get("definition") or {}
        roles = {r.get("name"): r.get("endpoint") for r in definition.get("roles") or [] if isinstance(r, dict)}
        for a in definition.get("activities") or []:
            if not isinstance(a, dict):
                continue
            endpoints = [e.strip() for e in str(roles.get(a.get("role")) or "").split(",") if e.strip()]
            agent_ids = [e for e in endpoints if e in agents]
            if not agent_ids:
                continue
            declared = _names(a.get("tools") or a.get("mcpServers"))
            for n in (declared if declared else server_names):
                if n in out:
                    out[n]["tasks"].append({"definition": d["id"], "definition_name": d.get("name") or definition.get("processDefinitionName"),
                                            "version": d.get("prod_version"), "activity_id": a.get("id"), "activity_name": a.get("name"),
                                            "agent": agents[agent_ids[0]].get("username") or agent_ids[0], "declared": bool(declared)})
    return out


def server_view(name: str, raw) -> dict:
    """설정 한 칸 → 화면용(비밀값 가림). 손편집으로 깨진 칸도 사유와 함께 줄로 남는다(목록이 통째로 죽지 않는다)."""
    try:
        spec = mcp_check.normalize(raw)
    except ValueError as e:
        return {"name": name, "transport": None, "url": None, "command": None, "args": [], "env": {}, "headers": {},
                "config_error": f"설정 오류 — {e}"}
    shown = mcp_check.masked(spec)
    return {"name": name, "transport": spec["transport"], "url": shown.get("url"), "command": shown.get("command"),
            "args": [mcp_check.mask_text(a) for a in shown.get("args") or []], "env": shown.get("env") or {},
            "headers": shown.get("headers") or {}, "config_error": None}


def register(app, *, runtime_factory, audit):
    def runtime():
        rt = runtime_factory()
        if rt is None:
            raise HTTPException(503, "도구 지도에는 instance 실행 서비스가 필요합니다 (PROCESS_MODE=instance)")
        return rt

    def servers_of(rt) -> dict:
        tenant = rt.repo.get_tenant(rt.tenant_id)
        if tenant is None:
            raise KeyError(f"테넌트 {rt.tenant_id} 가 없습니다")
        mcp = tenant.get("mcp") or {}
        config = mcp.get("mcpServers") if isinstance(mcp, dict) else None
        return dict(config) if isinstance(config, dict) else {}

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except KeyError as exc:
            raise HTTPException(404, str(exc.args[0]) if exc.args else "찾을 수 없습니다") from exc

    def spec_of(rt, name: str) -> tuple[dict, list[str]]:
        """(부를 설정, 채운 비밀 값) — 비밀 값은 결과 · 오류 · 감사에서 지우는 데만 쓴다(mcp_secrets.redact)."""
        raw = servers_of(rt).get(name)
        if raw is None:
            raise KeyError(f"MCP 서버 '{name}' 가 설정(tenants.mcp)에 없습니다")
        try:
            spec = mcp_check.normalize(raw)
        except ValueError as e:
            raise HTTPException(422, f"MCP 서버 '{name}' 설정 오류 — {e}")
        try:                                                     # G2: ${SECRET:KEY} 는 부르기 직전에만 채운다(응답에는 싣지 않는다)
            return mcp_secrets.runtime_spec(rt.repo, rt.tenant_id, name, spec)
        except mcp_secrets.SecretError as e:
            raise HTTPException(e.status, e.reason)

    def confirmed_of(rt, name: str) -> frozenset:
        """G2 ②: 강사가 읽기로 확인한 도구 — 써 보기에서도 같은 판정(호출 직전 다시 받은 목록에서 여전히 confirmable 일 때만)."""
        return frozenset(mcp_registry.confirmed_of(servers_of(rt).get(name)))

    @app.get("/api/mcp/servers")
    async def list_servers():
        rt = runtime()

        def work():
            servers = servers_of(rt)
            used = usage(rt.repo, rt.tenant_id, list(servers))
            try:                                                                                     # B2: 출처 · 고칠 수 있음 · 마지막 검사
                marks = mcp_registry.annotate(mcp_registry.store_for(rt.repo), rt.tenant_id, servers)
            except mcp_registry.RegistryError as e:
                raise HTTPException(e.status, e.reason) from e
            return {"tenant": rt.tenant_id, "source": "tenants.mcp",
                    "servers": [dict(server_view(n, raw), **used[n], **marks[n]) for n, raw in servers.items()]}
        return await run(work)

    @app.get("/api/mcp/servers/{name}/tools")
    async def server_tools(name: str, timeout: float | None = None):
        rt = runtime()
        limit = _timeout(timeout, LIST_TIMEOUT)
        spec, used = await run(lambda: spec_of(rt, name))
        async with CALL_SEMAPHORE:
            result = mcp_secrets.redact(await run(lambda: mcp_check.check(spec, limit)), used)
        return {"name": name, "timeout_s": limit, **{k: result[k] for k in ("status", "tools", "error", "error_kind", "checked_at",
                                                                           "elapsed_ms", "server_info", "protocol_version", "transport")}}

    @app.post("/api/mcp/servers/{name}/tools/{tool}/call")
    async def call_tool(name: str, tool: str, body: dict | None = None):
        rt = runtime()
        body = body or {}
        arguments = body.get("arguments", {})
        if not isinstance(arguments, dict):
            raise HTTPException(400, "arguments: 이름→값 객체여야 합니다")
        limit = _timeout(body.get("timeout"), CALL_TIMEOUT)
        spec, used = await run(lambda: spec_of(rt, name))
        async with CALL_SEMAPHORE:
            confirmed = await run(lambda: confirmed_of(rt, name))
            result = mcp_secrets.redact(await run(lambda: mcp_check.call(spec, tool, arguments, limit, confirmed=confirmed)), used)
        audit("-", str(body.get("by") or "포털"), "MCP_TOOL_TRIED",
              {"server": name, "tool": tool, "status": result["status"], "error": result.get("error"),
               "arguments": mcp_calls.brief(mcp_check.mask_value(arguments), 300)})
        if result["status"] == "refused":
            raise HTTPException(403 if result.get("error_kind") == "not_read_only" else 404, result["error"])
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
