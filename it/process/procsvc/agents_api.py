"""Read routes for agents and skills (U2). Mounted by main.py after instance_mode.mount. Writes are in agent_authoring_api.py (B1).

    GET /api/agents              agent cards: name · role · goal · model · MCP servers · skills · steps it takes
    GET /api/agents/{id}         one agent: the card + persona, each server's registration, each step's run settings
                                 (agents_store.agent_settings + run_servers — the same functions the worker runs with)
    GET /api/skills              skills (tenant_skills): title · description · agents it is attached to · steps that declare it
    GET /api/skills/{name}       one skill with its SKILL.md text

Each card carries `origin` ('seed' = protected default, 'user' = made in the portal) and a step's performer follows the step → agent
assignment (activity_agent_map) when there is one — the same rule the engine applies when the step opens (agent_authoring.apply_agent_map).
`step_runs()` is the one answer to "which agent runs this step, with which MCP servers" — the agent detail and the tool map (mcp_api)
both read it.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from . import instance_mode, mcp_registry, work_rules
from .agent_authoring import default_performers, is_agent_activity, latest_definitions, origin_of
from .agents_store import activity_capabilities, agent_settings, csv_list, role_text, run_servers, skill_title


def agent_steps(definitions: list[dict], maps: dict) -> list[dict]:
    """Every activity of the definitions with its performers: the activity's own `agent` (the product's AgentSelectField
    writes it) or the role's endpoint (HYD definitions: role "AI 에이전트" → sys:agent, "SCADA" → sys:scada).
    `agent` marks the steps a coding-agent worker runs (agent_authoring.is_agent_activity) — only those have run settings."""
    out = []
    for d in definitions:
        raw = d.get("definition") or {}
        for a in raw.get("activities") or []:
            if not isinstance(a, dict) or not a.get("id"):
                continue
            performers = default_performers(raw, a)
            if not performers:
                continue
            is_agent = is_agent_activity(a)
            mapped = maps.get((d["id"], a["id"])) if is_agent else None
            default = performers
            if mapped:                                   # B1: 단계 → 에이전트 배정이 이긴다(정의 원본은 그대로)
                performers = [mapped]
            out.append({"definition_id": d["id"], "definition_name": d.get("name") or raw.get("processDefinitionName"),
                        "version": d.get("prod_version"), "activity_id": a["id"], "name": a.get("name") or a["id"], "agent": is_agent,
                        "performers": performers, "default_performers": default, "assigned": bool(mapped),
                        "caps": activity_capabilities(raw, a["id"]) if is_agent else {}})
    return out


def _context(rt):
    maps = {(m["proc_def_id"], m["activity_id"]): m["agent_id"] for m in rt.repo.list_agent_map(rt.tenant_id)}
    steps = agent_steps(latest_definitions(rt), maps)
    attached: dict[str, list[str]] = {}
    for r in rt.repo.list_agent_skills(rt.tenant_id):
        attached.setdefault(r["user_id"], []).append(r["skill_name"])
    return steps, attached


def step_runs(rt) -> list[dict]:
    """에이전트 단계마다 실제로 맡는 에이전트(배정 반영)와 그 실행이 쓰는 도구 서버 — 워커와 같은 두 함수(agent_settings · run_servers).
    → [{definition_id, definition_name, version, activity_id, name, agent_id, agent_name, servers: {서버: 정해진 읽기 도구 | None}}]"""
    steps, _ = _context(rt)
    users = {u["id"]: u for u in rt.repo.list_users(None, rt.tenant_id)}
    tenant = mcp_registry.store_for(rt.repo).servers(rt.tenant_id)
    out = []
    for s in steps:
        if not s["agent"]:
            continue
        performer = next((p for p in s["performers"] if (users.get(p) or {}).get("is_agent")), None)
        settings = agent_settings(rt.repo, rt.tenant_id, users.get(performer), activity=s["caps"])
        out.append({k: s[k] for k in ("definition_id", "definition_name", "version", "activity_id", "name")}
                   | {"agent_id": performer, "agent_name": (users.get(performer) or {}).get("username") or performer,
                      "servers": run_servers(settings.tools, tenant, s["caps"].get("contract"))})
    return out


def _card(user: dict, attached: list[str], steps: list[dict]) -> dict:
    mine = [s for s in steps if user["id"] in s["performers"]]
    return {"id": user["id"], "name": user.get("username") or user["id"], "kind": "system" if (user.get("agent_type") or "agent") == "system" else "agent",
            "origin": origin_of(user), "editable": origin_of(user) == "user",
            "role": role_text(user.get("role")), "goal": user.get("goal") or "", "model": user.get("model") or None,
            "tools": csv_list(user.get("tools")), "skills": attached,
            "work_rules": user.get("work_rules") or None,
            "work_rules_detail": work_rules.rule_card(user.get("work_rules")),
            "steps": [{k: s[k] for k in ("definition_id", "definition_name", "version", "activity_id", "name", "agent", "assigned")} for s in mine]}


def mount(app: FastAPI) -> None:
    @app.get("/api/agents")
    def list_agents():
        rt = instance_mode._rt()
        steps, attached = _context(rt)
        cards = [_card(u, attached.get(u["id"], []), steps) for u in rt.repo.list_users(None, rt.tenant_id) if u.get("is_agent")]
        return sorted(cards, key=lambda c: (c["kind"] != "agent", c["name"]))

    @app.get("/api/agents/{agent_id}")
    def get_agent(agent_id: str):
        rt = instance_mode._rt()
        steps, attached = _context(rt)
        rows = [u for u in rt.repo.list_users([agent_id], rt.tenant_id) if u.get("is_agent")]
        if not rows:
            raise HTTPException(404, "그런 에이전트가 없습니다")
        user = rows[0]
        card = _card(user, attached.get(agent_id, []), steps)
        servers = mcp_registry.store_for(rt.repo).servers(rt.tenant_id)
        card["persona"] = user.get("persona") or ""
        card["tools"] = [{"name": t, "registered": t in servers, "description": (servers.get(t) or {}).get("description") or ""}
                         for t in card["tools"]]
        skills = {s["skill_name"]: s for s in rt.repo.list_skills(rt.tenant_id, card["skills"])} if card["skills"] else {}
        card["skills"] = [{"skill_name": n, "found": n in skills, "title": skill_title(skills[n]) if n in skills else "",
                           "description": (skills.get(n) or {}).get("description") or ""} for n in card["skills"]]
        # what the worker will run with — the same functions, per step (a step may declare its own tools/skills/model, and the
        # class AI steps with a fixed read list use only those tools — run_servers)
        base = agent_settings(rt.repo, rt.tenant_id, user)
        rows = []
        for s in steps:
            if not (s["agent"] and agent_id in s["performers"]):
                continue
            settings = agent_settings(rt.repo, rt.tenant_id, user, activity=s["caps"])
            rows.append({"definition_id": s["definition_id"], "definition_name": s["definition_name"], "activity_id": s["activity_id"],
                         "name": s["name"], "settings": settings.summary(), "servers": run_servers(settings.tools, servers, s["caps"].get("contract"))})
        card["run"] = {"instructions": base.instructions(), "settings": base.summary(), "steps": rows,
                       "servers_registered": [{"name": n, "description": (servers.get(n) or {}).get("description") or ""} for n in sorted(servers)]}
        card["source"] = {"table": "public.users", "updated_at": user.get("updated_at") or user.get("created_at")}
        return card

    @app.get("/api/skills")
    def list_skills():
        rt = instance_mode._rt()
        steps, attached = _context(rt)
        names = {u["id"]: u.get("username") or u["id"] for u in rt.repo.list_users(None, rt.tenant_id)}
        out = []
        for s in rt.repo.list_skills(rt.tenant_id):
            n = s["skill_name"]
            out.append({"skill_name": n, "title": skill_title(s), "description": s.get("description") or "", "updated_at": s.get("updated_at"),
                        "origin": origin_of(s),
                        "chars": len(s.get("content") or ""),
                        "agents": [{"id": uid, "name": names.get(uid, uid)} for uid, ss in attached.items() if n in ss],
                        "steps": [{"definition_id": st["definition_id"], "definition_name": st["definition_name"], "activity_id": st["activity_id"], "name": st["name"]}
                                  for st in steps if n in (st["caps"].get("skills") or [])]})
        return out

    @app.get("/api/skills/{name}")
    def get_skill(name: str):
        rt = instance_mode._rt()
        steps, attached = _context(rt)
        row = rt.repo.get_skill(rt.tenant_id, name)
        if row is None:
            raise HTTPException(404, "그런 스킬이 없습니다")
        names = {u["id"]: u.get("username") or u["id"] for u in rt.repo.list_users(None, rt.tenant_id)}
        return {**row, "title": skill_title(row), "origin": origin_of(row),
                "agents": [{"id": uid, "name": names.get(uid, uid)} for uid, ss in attached.items() if name in ss],
                "steps": [{"definition_id": st["definition_id"], "definition_name": st["definition_name"], "activity_id": st["activity_id"], "name": st["name"]}
                          for st in steps if name in (st["caps"].get("skills") or [])]}
