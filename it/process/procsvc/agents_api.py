"""Read-only HTTP routes for agents and skills (U2 · TODO A2). Mounted by main.py after instance_mode.mount.

    GET /api/agents              agent cards: name · role · goal · model · MCP servers · skills · steps it takes
    GET /api/agents/{id}         one agent: the card + persona, each server's registration, each step's run settings
                                 (agents_store.agent_settings — the same function the worker runs with) and the prompt section
    GET /api/skills              skills (tenant_skills): title · description · agents it is attached to · steps that declare it
    GET /api/skills/{name}       one skill with its SKILL.md text

These routes only read. B1 (DECISIONS 110 ①) added the writes in agent_authoring_api.py (create · edit · clone · delete agents
and skills, step → agent assignment, reset); the wrap-up (Claude Code → SQL) still writes the same rows. Each card carries
`origin` ('seed' = protected default, 'user' = made in the portal) and a step's performer follows the step → agent assignment
(activity_agent_map) when there is one — the same rule the engine applies when the step opens (agent_authoring.apply_agent_map).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from . import engine, instance_mode
from .agent_authoring import origin_of
from .agents_store import activity_capabilities, agent_settings, csv_list, role_text, skill_title


def _servers(repo, tenant_id: str) -> dict[str, dict]:
    mcp = (repo.get_tenant(tenant_id) or {}).get("mcp") or {}
    servers = mcp.get("mcpServers") if isinstance(mcp, dict) else None
    return servers if isinstance(servers, dict) else {}


def _latest_definitions(rt) -> list[dict]:
    """Registered definitions, newest version of each id; the running definition when nothing is registered under its id."""
    latest: dict[str, dict] = {}
    for r in rt.repo.list_definitions(rt.tenant_id):
        latest[r["id"]] = r                       # ordered by (id, version): the last one wins
    if rt.defn.id not in latest:
        latest[rt.defn.id] = {"id": rt.defn.id, "name": rt.defn.name, "prod_version": rt.defn.raw.get("version"), "definition": rt.defn.raw}
    return list(latest.values())


def agent_steps(definitions: list[dict], maps: dict | None = None) -> list[dict]:
    """Every activity of the definitions with its performers: the activity's own `agent` (the product's AgentSelectField
    writes it) or the role's endpoint (HYD definitions: role "AI 에이전트" → sys:agent, "SCADA" → sys:scada).
    `agent` marks the steps a coding-agent worker runs (agentMode set, orchestration cliagents) — only those have run settings."""
    out = []
    for d in definitions:
        raw = d.get("definition") or {}
        roles = {r.get("name"): r for r in raw.get("roles") or [] if isinstance(r, dict)}
        for a in raw.get("activities") or []:
            if not isinstance(a, dict) or not a.get("id"):
                continue
            performers = csv_list(a.get("agent")) or csv_list((roles.get(a.get("role")) or {}).get("endpoint"))
            if not performers:
                continue
            orch = a.get("orchestration")
            is_agent = bool(engine.agent_mode_of(a)) and (orch in engine.NO_MODE or orch == engine.AGENT_ORCH)
            mapped = (maps or {}).get((d["id"], a["id"])) if is_agent else None
            default = performers
            if mapped:                                   # B1: 단계 → 에이전트 배정이 이긴다(정의 원본은 그대로)
                performers = [mapped]
            out.append({"definition_id": d["id"], "definition_name": d.get("name") or raw.get("processDefinitionName"),
                        "version": d.get("prod_version"), "activity_id": a["id"], "name": a.get("name") or a["id"], "agent": is_agent,
                        "performers": performers, "default_performers": default, "assigned": bool(mapped), "caps": activity_capabilities(raw, a["id"]) if is_agent else {}})
    return out


def _card(user: dict, attached: list[str], steps: list[dict]) -> dict:
    mine = [s for s in steps if user["id"] in s["performers"]]
    return {"id": user["id"], "name": user.get("username") or user["id"], "kind": "system" if (user.get("agent_type") or "agent") == "system" else "agent",
            "origin": origin_of(user), "editable": origin_of(user) == "user",
            "role": role_text(user.get("role")), "goal": user.get("goal") or "", "model": user.get("model") or None,
            "tools": csv_list(user.get("tools")), "skills": attached,
            "steps": [{k: s[k] for k in ("definition_id", "definition_name", "version", "activity_id", "name", "agent", "assigned")} for s in mine]}


def mount(app: FastAPI) -> None:
    def _context():
        rt = instance_mode._rt()
        reader = getattr(rt.repo, "list_agent_map", None)
        maps = {(m["proc_def_id"], m["activity_id"]): m["agent_id"] for m in reader(rt.tenant_id)} if callable(reader) else {}
        steps = agent_steps(_latest_definitions(rt), maps)
        attached: dict[str, list[str]] = {}
        for r in rt.repo.list_agent_skills(rt.tenant_id):
            attached.setdefault(r["user_id"], []).append(r["skill_name"])
        return rt, steps, attached

    @app.get("/api/agents")
    def list_agents():
        rt, steps, attached = _context()
        cards = [_card(u, attached.get(u["id"], []), steps) for u in rt.repo.list_users(None, rt.tenant_id) if u.get("is_agent")]
        return sorted(cards, key=lambda c: (c["kind"] != "agent", c["name"]))

    @app.get("/api/agents/{agent_id}")
    def get_agent(agent_id: str):
        rt, steps, attached = _context()
        rows = [u for u in rt.repo.list_users([agent_id], rt.tenant_id) if u.get("is_agent")]
        if not rows:
            raise HTTPException(404, "그런 에이전트가 없습니다")
        user = rows[0]
        card = _card(user, attached.get(agent_id, []), steps)
        servers = _servers(rt.repo, rt.tenant_id)
        card["persona"] = user.get("persona") or ""
        card["tools"] = [{"name": t, "registered": t in servers, "description": (servers.get(t) or {}).get("description") or "",
                          "transport": "url" if (servers.get(t) or {}).get("url") else "command" if (servers.get(t) or {}).get("command") else None}
                         for t in card["tools"]]
        skills = {s["skill_name"]: s for s in rt.repo.list_skills(rt.tenant_id, card["skills"])} if card["skills"] else {}
        card["skills"] = [{"skill_name": n, "found": n in skills, "title": skill_title(skills[n]) if n in skills else "",
                           "description": (skills.get(n) or {}).get("description") or ""} for n in card["skills"]]
        # what the worker will run with — the same function, per step (a step may declare its own tools/skills/model)
        base = agent_settings(rt.repo, rt.tenant_id, user)
        card["run"] = {"instructions": base.instructions(), "settings": base.summary(),
                       "steps": [{"definition_id": s["definition_id"], "definition_name": s["definition_name"], "activity_id": s["activity_id"], "name": s["name"],
                                  "settings": agent_settings(rt.repo, rt.tenant_id, user, activity=s["caps"]).summary()}
                                 for s in steps if s["agent"] and agent_id in s["performers"]],
                       "servers_registered": [{"name": n, "description": (servers.get(n) or {}).get("description") or ""} for n in sorted(servers)]}
        card["source"] = {"table": "public.users", "updated_at": user.get("updated_at") or user.get("created_at")}
        return card

    @app.get("/api/skills")
    def list_skills():
        rt, steps, attached = _context()
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
        rt, steps, attached = _context()
        row = rt.repo.get_skill(rt.tenant_id, name)
        if row is None:
            raise HTTPException(404, "그런 스킬이 없습니다")
        names = {u["id"]: u.get("username") or u["id"] for u in rt.repo.list_users(None, rt.tenant_id)}
        return {**row, "title": skill_title(row), "origin": origin_of(row),
                "agents": [{"id": uid, "name": names.get(uid, uid)} for uid, ss in attached.items() if name in ss],
                "steps": [{"definition_id": st["definition_id"], "definition_name": st["definition_name"], "activity_id": st["activity_id"], "name": st["name"]}
                          for st in steps if name in (st["caps"].get("skills") or [])]}
