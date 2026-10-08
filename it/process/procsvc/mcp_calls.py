"""U3 (A2 MCP 부분) — 도구 호출 기록: events 의 도구 호출(tool_usage_started/finished)을 서버 · 도구별로 모은다(읽기 전용).

워커가 남기는 도구 이름은 CLI 마다 다르다 — Claude Code 'mcp__<서버>__<도구>', Codex '<서버>/<도구>'(cliagents codex.py).
둘 다 같은 (서버, 도구)로 읽는다. 시작 · 끝 이벤트는 tool_use_id 로 한 줄로 묶어 입력 · 결과 · 걸린 시간을 보인다.
입력 · 결과는 비밀값을 가리고(mcp_check.mask_value) 글자 수를 줄여 돌려준다. 원본 events 행은 건드리지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime

from . import mcp_check

TOOL_EVENTS = ("tool_usage_started", "tool_usage_finished")
SCAN_LIMIT = 3000                       # 최근 도구 이벤트 몇 개까지 훑나 (오래된 것은 목록에 없다고 화면이 알린다)
SUMMARY_CHARS = 160
DETAIL_CHARS = 4000


def parse_tool(raw) -> tuple[str | None, str]:
    """'mcp__hyd-dmn__diagnose' → ('hyd-dmn', 'diagnose'); 'hyd-dmn/diagnose' → 같음; 'Read' → (None, 'Read')."""
    name = str(raw or "")
    if name.startswith("mcp__"):
        server, sep, tool = name[5:].partition("__")
        return (server, tool) if sep and server and tool else (None, name)
    if "/" in name:
        server, _, tool = name.partition("/")
        return (server, tool) if server and tool else (None, name)
    return None, name


def same_server(found: str | None, wanted: str) -> bool:
    """Codex 는 서버 이름의 '-' 를 '_' 로 바꿔 쓰기도 한다(probe_codex_tool_scope: mcp__hyd_dmn__)."""
    return found is not None and (found == wanted or found.replace("-", "_") == wanted.replace("-", "_"))


def brief(value, limit: int) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
        try:                                                       # 결과가 JSON 문자열이면 한 줄로 다시 쓴다
            if text.strip()[:1] in ("{", "["):
                text = json.dumps(json.loads(text), ensure_ascii=False)
        except ValueError:
            pass
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    text = mcp_check.mask_text(text) if isinstance(value, str) else text
    return text if len(text) <= limit else text[:limit] + " …"


def _masked(value):
    if isinstance(value, str):
        try:
            if value.strip()[:1] in ("{", "["):
                return mcp_check.mask_value(json.loads(value))
        except ValueError:
            pass
    return mcp_check.mask_value(value)


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value is not None else None)


def _ms(a, b) -> int | None:
    try:
        return int((datetime.fromisoformat(_iso(b).replace("Z", "+00:00")) - datetime.fromisoformat(_iso(a).replace("Z", "+00:00"))).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None


def recent_tool_events(repo, limit: int = SCAN_LIMIT) -> list[dict]:
    """최근 도구 이벤트(새것 먼저) + 그 단계 이름 · 처리 건 이름. PgRepo 는 한 번의 SQL, MemoryRepo 는 사전을 훑는다."""
    if hasattr(repo, "_conn") and hasattr(repo, "_row"):
        with repo._conn() as c:
            rows = c.execute("""select e.id, e.todo_id, e.proc_inst_id, e.event_type::text as event_type, e.data, e.timestamp,
                                       t.activity_id, t.activity_name, i.proc_inst_name
                                  from events e
                                  left join todolist t on t.id::text = e.todo_id
                                  left join bpm_proc_inst i on i.proc_inst_id = e.proc_inst_id
                                 where e.event_type::text = any(%s)
                                 order by e.timestamp desc limit %s""", (list(TOOL_EVENTS), limit)).fetchall()
        return [repo._row(r) for r in rows]
    events = [e for e in getattr(repo, "events", []) if e.get("event_type") in TOOL_EVENTS]
    events = sorted(events, key=lambda e: str(e.get("timestamp") or ""), reverse=True)[:limit]
    out, items, insts = [], {}, {}
    for e in events:
        tid, pid = e.get("todo_id"), e.get("proc_inst_id")
        if tid and tid not in items:
            items[tid] = repo.get_workitem(tid) or {}
        if pid and pid not in insts:
            insts[pid] = repo.get_instance(pid) or {}
        w, i = items.get(tid) or {}, insts.get(pid) or {}
        out.append(dict(e, activity_id=w.get("activity_id"), activity_name=w.get("activity_name"), proc_inst_name=i.get("proc_inst_name")))
    return out


def calls(rows: list[dict], *, server: str | None = None, tool: str | None = None, limit: int = 50) -> list[dict]:
    """도구 이벤트 행(새것 먼저) → 호출 한 줄씩(새것 먼저). server · tool 로 거른다."""
    groups: dict[tuple, dict] = {}
    order: list[tuple] = []
    for e in rows:
        data = e.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                data = {}
        srv, name = parse_tool(data.get("tool"))
        if srv is None or (server and not same_server(srv, server)) or (tool and name != tool):
            continue
        key = (e.get("todo_id"), data.get("tool_use_id")) if data.get("tool_use_id") else ("event", e.get("id"))
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"server": srv, "tool": name, "raw_tool": data.get("tool"), "proc_inst_id": e.get("proc_inst_id"),
                               "instance_name": e.get("proc_inst_name"), "todo_id": e.get("todo_id"), "activity_id": e.get("activity_id"),
                               "task_name": e.get("activity_name"), "started_at": None, "finished_at": None, "input": None, "output": None,
                               "is_error": None}
            order.append(key)
        if e.get("event_type") == "tool_usage_started":
            g["started_at"], g["input"] = e.get("timestamp"), data.get("input")
        else:
            g["finished_at"], g["output"], g["is_error"] = e.get("timestamp"), data.get("output"), bool(data.get("is_error"))
    out = []
    for key in order[:limit]:
        g = groups[key]
        at = g["started_at"] or g["finished_at"]
        out.append({
            "server": g["server"], "tool": g["tool"], "raw_tool": g["raw_tool"],
            "proc_inst_id": g["proc_inst_id"], "instance_name": g["instance_name"], "todo_id": g["todo_id"],
            "activity_id": g["activity_id"], "task_name": g["task_name"],
            "at": _iso(at),
            "state": "error" if g["is_error"] else ("done" if g["finished_at"] else "running"),
            "duration_ms": _ms(g["started_at"], g["finished_at"]) if g["started_at"] and g["finished_at"] else None,
            "input_summary": brief(_masked(g["input"]), SUMMARY_CHARS), "output_summary": brief(_masked(g["output"]), SUMMARY_CHARS),
            "input": brief(_masked(g["input"]), DETAIL_CHARS), "output": brief(_masked(g["output"]), DETAIL_CHARS),
            "link": f"#/instances/{g['proc_inst_id']}/task/{g['todo_id']}" if g["proc_inst_id"] and g["todo_id"] else None,
        })
    return out
