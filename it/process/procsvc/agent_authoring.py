"""B1 (확정 TODO B · DECISIONS 110 ①): 포털에서 에이전트 · 스킬을 만들고 고치고 붙이기, 역할 → 사람 · 단계 → 에이전트 배정, 되돌리기.

원천은 U2 와 같다(읽는 쪽은 agents_store.agent_settings — 워커 · 포털 · A10 이 같은 함수를 부른다):
  에이전트 public.users(is_agent) · 스킬 public.tenant_skills · 붙이기 public.agent_skills · 업무분장 public.role_members.
여기서 더한 것(migration 20261008000041):
  origin          'seed'(기본, 보호) | 'user'(포털에서 만든 것). 기본 행은 고치기 · 지우기를 사유와 함께 거절 → "복제해서 고치기"만.
  activity_agent_map  (정의 id, 단계 id) → 에이전트. 정의(BPMN) 원본은 그대로 두고, 흐름이 그 단계에 닿을 때 작업 행의 user_id 를
                  그 에이전트로 쓴다(apply_agent_map — inbox.apply_advance 가 엔진의 다섯 자리에서 부른다). 워커는 작업 행 user_id 로
                  프로필을 읽으므로(agent-worker context.prepare) 배정 = 실제 실행 담당. 적용 기록은 task_assignments(kind='agent_map').
  reset           포털에서 만든 것(origin='user' 에이전트 · 스킬 · 업무분장, 모든 단계 배정)만 지운다. 기본은 그대로.

원본(process-gpt-vue3@867e8cf): AgentField.vue:64-170(이름 · 역할 · 목표 · 성격 · 도구(등록된 MCP 서버) · 스킬 · 모델),
ProcessGPTBackend.ts:4250-4306(putAgent · deleteAgent), :4393-4441(replaceAgentSkills · deleteAgentSkill · deleteAgentSkillsBySkill),
AgentSelectField.vue(단계의 담당 에이전트 — 제품은 정의 activity 에 쓴다; HYD 는 정의 고정이라 배정 표), /work-assignment(역할 → 사람).
"""
from __future__ import annotations

import logging
import re
import secrets
from copy import deepcopy

from hydcommon.timeutil import now_iso

from .agents_store import SKILL_NAME_RE, csv_list, split_frontmatter

log = logging.getLogger("process.agent_authoring")

USER = "user"
SEED = "seed"
KIND_MAP = "agent_map"
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,99}$")
LIMITS = {"name": 60, "role": 200, "goal": 500, "persona": 2000, "description": 300, "content": 60000}


class AuthoringError(Exception):
    """사람이 읽을 사유와 HTTP 상태. 조용한 성공 · 빈 성공 금지 — 거절은 모두 이 예외로."""
    status = 422

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        if status is not None:
            self.status = status


def origin_of(row: dict | None) -> str:
    return (row or {}).get("origin") or SEED


def _text(body: dict, key: str, label: str, *, required: bool = False) -> str:
    value = body.get(key)
    value = "" if value is None else str(value).strip()
    if required and not value:
        raise AuthoringError(f"{label} 칸을 채워야 합니다")
    if len(value) > LIMITS[key]:
        raise AuthoringError(f"{label} 칸이 너무 깁니다({len(value)}자, 최대 {LIMITS[key]}자)")
    return value


# ---------------------------------------------------------------- 읽기 도우미
def tenant_servers(repo, tenant_id: str) -> dict[str, dict]:
    mcp = (repo.get_tenant(tenant_id) or {}).get("mcp") or {}
    servers = mcp.get("mcpServers") if isinstance(mcp, dict) else None
    return servers if isinstance(servers, dict) else {}


def server_options(repo, tenant_id: str) -> list[dict]:
    """에이전트 폼의 "쓸 도구" 선택지 = tenants.mcp 에 등록된 서버. 연결 검사 상태(B2)가 있으면 그대로 붙여 표시만 한다:
    서버 설정의 `check` 칸, 또는 저장소가 `mcp_check_status(tenant_id)` → {서버: 상태} 를 주면 그것."""
    servers = tenant_servers(repo, tenant_id)
    status = {}
    reader = getattr(repo, "mcp_check_status", None)
    if callable(reader):
        try:
            status = reader(tenant_id) or {}
        except Exception as e:  # noqa: BLE001 — 검사 상태는 보조 표시: 못 읽으면 사유를 붙이고 목록은 그대로
            log.warning("mcp check status unreadable: %s", e)
            status = {n: {"error": f"검사 상태를 읽지 못했습니다: {e}"} for n in servers}
    out = []
    for name, raw in servers.items():
        raw = raw if isinstance(raw, dict) else {}
        out.append({"name": name, "description": raw.get("description") or "",
                    "transport": "url" if raw.get("url") else "command" if raw.get("command") else None,
                    "check": status.get(name) or raw.get("check")})
    return out


def agents_of(repo, tenant_id: str) -> list[dict]:
    """AI 에이전트(시스템 수행자 제외)."""
    return [u for u in repo.list_users(None, tenant_id) if u.get("is_agent") and (u.get("agent_type") or "agent") == "agent"]


def _agent(repo, tenant_id: str, agent_id: str) -> dict:
    row = next((u for u in repo.list_users([agent_id], tenant_id) if u.get("is_agent")), None)
    if row is None:
        raise AuthoringError(f"그런 에이전트가 없습니다: {agent_id}", 404)
    return row


def _name(row: dict) -> str:
    return row.get("username") or row.get("id") or ""


def _protect(row: dict, what: str) -> None:
    if origin_of(row) != USER:
        kind = "시스템 수행자" if (row.get("agent_type") or "agent") == "system" else "기본 에이전트"
        tail = " '복제해서 고치기'로 사본을 만들어 고치세요." if kind == "기본 에이전트" else ""
        raise AuthoringError(f"{kind} '{_name(row)}'은(는) {what} 수 없습니다 — 수업 기준이라 보호합니다.{tail}", 403)


# ---------------------------------------------------------------- 에이전트
def _agent_fields(repo, tenant_id: str, body: dict, *, self_id: str | None = None) -> dict:
    name = _text(body, "name", "이름", required=True)
    goal = _text(body, "goal", "목표", required=True)
    role = _text(body, "role", "역할")
    persona = _text(body, "persona", "성격 · 말투")
    model = str(body.get("model") or "").strip()
    if model and not MODEL_RE.match(model):
        raise AuthoringError(f"모델 이름 모양이 아닙니다: {model[:60]} (영문 · 숫자 · . _ : / @ - 만, 비우면 실행기 기본 모델)")
    same = [u for u in repo.list_users(None, tenant_id)
            if u.get("is_agent") and u.get("id") != self_id and _name(u).strip().lower() == name.lower()]
    if same:
        raise AuthoringError(f"같은 이름의 에이전트가 이미 있습니다: {name}", 409)
    servers = tenant_servers(repo, tenant_id)
    tools = list(dict.fromkeys(csv_list(body.get("tools"))))
    unknown = [t for t in tools if t not in servers]
    if unknown:
        raise AuthoringError(f"등록되지 않은 도구 서버입니다: {', '.join(unknown)} (등록된 서버: {', '.join(sorted(servers)) or '없음'})")
    skills = list(dict.fromkeys(csv_list(body.get("skills"))))
    if skills:
        stored = {s["skill_name"] for s in repo.list_skills(tenant_id, skills)}
        missing = [s for s in skills if s not in stored]
        if missing:
            raise AuthoringError(f"없는 스킬은 붙일 수 없습니다: {', '.join(missing)}")
    return {"username": name, "goal": goal, "role": role or None, "persona": persona or None, "model": model or None,
            "tools": ",".join(tools) if tools else None, "skills": skills}


def _new_agent_id(repo, tenant_id: str) -> str:
    for _ in range(20):
        candidate = f"agent:u-{secrets.token_hex(4)}"
        if not repo.list_users([candidate], tenant_id):
            return candidate
    raise AuthoringError("에이전트 id 를 만들지 못했습니다 — 다시 시도하세요", 500)


def create_agent(repo, tenant_id: str, body: dict, *, by: str | None = None) -> dict:
    f = _agent_fields(repo, tenant_id, body)
    skills = f.pop("skills")
    row = {"id": _new_agent_id(repo, tenant_id), **f, "is_agent": True, "agent_type": "agent", "tenant_id": tenant_id, "origin": USER}
    repo.write_agent(row, skills, create=True)
    log.info("agent created %s by %s", row["id"], by)
    return _agent(repo, tenant_id, row["id"])


def update_agent(repo, tenant_id: str, agent_id: str, body: dict, *, by: str | None = None) -> dict:
    row = _agent(repo, tenant_id, agent_id)
    _protect(row, "고칠")
    f = _agent_fields(repo, tenant_id, body, self_id=agent_id)
    skills = f.pop("skills")
    repo.write_agent({**row, **f}, skills, create=False)
    log.info("agent updated %s by %s", agent_id, by)
    return _agent(repo, tenant_id, agent_id)


def clone_agent(repo, tenant_id: str, agent_id: str, body: dict | None = None, *, by: str | None = None) -> dict:
    """기본이든 내가 만든 것이든 사본(origin=user)을 만든다. 시스템 수행자(SCADA · CMMS …)는 에이전트 설정이 없어 복제하지 않는다."""
    src = _agent(repo, tenant_id, agent_id)
    if (src.get("agent_type") or "agent") != "agent":
        raise AuthoringError(f"시스템 수행자 '{_name(src)}'은(는) 정해진 업무를 하는 시스템이라 복제할 수 없습니다", 403)
    taken = {_name(u).strip().lower() for u in repo.list_users(None, tenant_id) if u.get("is_agent")}
    name = str((body or {}).get("name") or "").strip()
    if not name:
        base = f"{_name(src)} 사본"
        name, n = base, 2
        while name.lower() in taken:
            name, n = f"{base} {n}", n + 1
    skills = [r["skill_name"] for r in repo.list_agent_skills(tenant_id, agent_id)]
    payload = {"name": name, "goal": src.get("goal") or "", "role": src.get("role") or "", "persona": src.get("persona") or "",
               "model": src.get("model") or "", "tools": csv_list(src.get("tools")), "skills": skills}
    if not payload["goal"].strip():
        payload["goal"] = f"{_name(src)}의 사본"
    return create_agent(repo, tenant_id, payload, by=by)


def running_rows(repo, tenant_id: str, agent_ids: list[str]) -> list[dict]:
    """지금 워커(또는 내장 경로)가 실행 중인 작업 — 이것이 있으면 지우기를 거절한다(실행 중에 프로필이 사라지지 않게)."""
    out = []
    for aid in agent_ids:
        out += [w for w in repo.list_workitems(status="IN_PROGRESS", user_id=aid, tenant_id=tenant_id, limit=None)
                if w.get("draft_status") == "STARTED"]
    return out


def return_open_rows(rt, agent_ids: list[str], reason: str, by: str | None) -> list[dict]:
    """열려 있지만 아직 집히지 않은 단계(IN_PROGRESS, 실행 전)를 정의의 역할 담당으로 되돌린다 — 지워진 에이전트 id 로 남아
    프로필 없이 실행되는 조용한 대체를 막는다. 되돌린 기록은 task_assignments(kind=agent_map)."""
    moved = []
    for aid in agent_ids:
        for w in rt.repo.list_workitems(status="IN_PROGRESS", user_id=aid, tenant_id=rt.tenant_id, limit=None):
            if w.get("draft_status") == "STARTED":
                continue
            with rt._transition(w["proc_inst_id"]):
                row = rt.repo.get_workitem(w["id"])
                if not row or row.get("user_id") != aid or row.get("status") != "IN_PROGRESS" or row.get("draft_status") == "STARTED":
                    continue
                try:
                    defn = rt.definition_for_workitem(row)
                    binding = defn.role_binding((defn.activities.get(row["activity_id"]) or {}).get("role"))
                except (LookupError, ValueError):
                    binding = None
                endpoint = (binding or {}).get("endpoint")
                if not endpoint:
                    log.warning("no default performer for %s/%s — left with %s", row["proc_inst_id"], row["activity_id"], aid)
                    continue
                row["user_id"], row["username"] = endpoint, (binding or {}).get("name") or row.get("username")
                row["assignees"] = list(row.get("assignees") or []) + [{"endpoint": endpoint, "kind": "agent", "via": aid, "resolution": "agent-map-removed"}]
                rt.repo.update_workitem(row)
                rt.repo.insert_assignment({"tenant_id": rt.tenant_id, "proc_inst_id": row["proc_inst_id"], "todo_id": row["id"], "from_user_id": aid,
                                           "to_user_id": endpoint, "kind": KIND_MAP, "by_user": by or "sys:process", "reason": reason})
                moved.append({"todo_id": row["id"], "proc_inst_id": row["proc_inst_id"], "activity_id": row["activity_id"], "to": endpoint})
    return moved


def delete_agent(rt, agent_id: str, *, by: str | None = None) -> dict:
    repo, tenant_id = rt.repo, rt.tenant_id
    row = _agent(repo, tenant_id, agent_id)
    _protect(row, "지울")
    busy = running_rows(repo, tenant_id, [agent_id])
    if busy:
        raise AuthoringError(f"'{_name(row)}'이(가) 지금 실행 중인 작업이 {len(busy)}건 있습니다 — 끝난 뒤 다시 지우세요", 409)
    moved = return_open_rows(rt, [agent_id], f"에이전트 '{_name(row)}' 삭제 — 기본 담당으로", by)
    maps = [m for m in repo.list_agent_map(tenant_id) if m["agent_id"] == agent_id]
    repo.remove_agent(tenant_id, agent_id)
    log.info("agent deleted %s by %s", agent_id, by)
    return {"deleted": agent_id, "name": _name(row), "returned_tasks": moved,
            "removed_assignments": [{"definition_id": m["proc_def_id"], "activity_id": m["activity_id"]} for m in maps]}


# ---------------------------------------------------------------- 스킬
def _skill_fields(name: str, body: dict) -> dict:
    content = str(body.get("content") or "")
    if len(content) > LIMITS["content"]:
        raise AuthoringError(f"스킬 문서가 너무 깁니다({len(content)}자, 최대 {LIMITS['content']}자)")
    meta, text = split_frontmatter(content)
    if not text.strip():
        raise AuthoringError("빈 스킬은 저장할 수 없습니다 — SKILL.md 본문(절차)을 적으세요")
    if meta.get("name") and meta["name"] != name:
        raise AuthoringError(f"문서 머리의 name({meta['name']})이 스킬 폴더 이름({name})과 다릅니다 — 같게 맞추세요")
    description = _text(body, "description", "설명") or meta.get("description") or ""
    if not description:
        heading = next((ln.lstrip("#").strip() for ln in text.splitlines() if ln.startswith("#")), "")
        description = heading
    if not description.strip():
        raise AuthoringError("설명 한 줄을 적으세요 — 에이전트가 언제 이 스킬을 쓸지 고르는 기준입니다")
    return {"description": description[:LIMITS["description"]], "content": content}


def create_skill(repo, tenant_id: str, body: dict, *, by: str | None = None) -> dict:
    name = str(body.get("skill_name") or "").strip()
    if not name:
        raise AuthoringError("스킬 폴더 이름을 적어야 합니다 (예: fan-vibration-check)")
    if not SKILL_NAME_RE.match(name):
        raise AuthoringError(f"스킬 폴더 이름은 영문 소문자 · 숫자 · 하이픈만 씁니다(최대 64자): {name[:70]}")
    if repo.get_skill(tenant_id, name) is not None:
        raise AuthoringError(f"같은 이름의 스킬이 이미 있습니다: {name}", 409)
    f = _skill_fields(name, body)
    repo.write_skill({"tenant_id": tenant_id, "skill_name": name, **f, "owner_id": by, "origin": USER}, create=True)
    return repo.get_skill(tenant_id, name)


def update_skill(repo, tenant_id: str, name: str, body: dict, *, by: str | None = None) -> dict:
    row = repo.get_skill(tenant_id, name)
    if row is None:
        raise AuthoringError(f"그런 스킬이 없습니다: {name}", 404)
    if origin_of(row) != USER:
        raise AuthoringError(f"기본 스킬 '{name}'은(는) 고칠 수 없습니다 — 수업 기준이라 보호합니다. 새 이름으로 스킬을 만들어 쓰세요.", 403)
    f = _skill_fields(name, body)
    repo.write_skill({**row, **f}, create=False)
    return repo.get_skill(tenant_id, name)


def delete_skill(repo, tenant_id: str, name: str, *, by: str | None = None) -> dict:
    row = repo.get_skill(tenant_id, name)
    if row is None:
        raise AuthoringError(f"그런 스킬이 없습니다: {name}", 404)
    if origin_of(row) != USER:
        raise AuthoringError(f"기본 스킬 '{name}'은(는) 지울 수 없습니다 — 수업 기준이라 보호합니다.", 403)
    attached = [r["user_id"] for r in repo.list_agent_skills(tenant_id) if r["skill_name"] == name]
    repo.remove_skill(tenant_id, name)
    return {"deleted": name, "detached_from": attached}


def attach_skill(repo, tenant_id: str, agent_id: str, skill_name: str) -> dict:
    row = _agent(repo, tenant_id, agent_id)
    _protect(row, "스킬을 붙일")
    if repo.get_skill(tenant_id, skill_name) is None:
        raise AuthoringError(f"그런 스킬이 없습니다: {skill_name}", 404)
    if any(r["skill_name"] == skill_name for r in repo.list_agent_skills(tenant_id, agent_id)):
        raise AuthoringError(f"'{_name(row)}'에 이미 붙어 있는 스킬입니다: {skill_name}", 409)
    repo.link_skill(tenant_id, agent_id, skill_name, True)
    return {"agent_id": agent_id, "skills": [r["skill_name"] for r in repo.list_agent_skills(tenant_id, agent_id)]}


def detach_skill(repo, tenant_id: str, agent_id: str, skill_name: str) -> dict:
    row = _agent(repo, tenant_id, agent_id)
    _protect(row, "스킬을 뗄")
    if not any(r["skill_name"] == skill_name for r in repo.list_agent_skills(tenant_id, agent_id)):
        raise AuthoringError(f"'{_name(row)}'에 붙어 있지 않은 스킬입니다: {skill_name}", 404)
    repo.link_skill(tenant_id, agent_id, skill_name, False)
    return {"agent_id": agent_id, "skills": [r["skill_name"] for r in repo.list_agent_skills(tenant_id, agent_id)]}


# ---------------------------------------------------------------- 단계 → 에이전트
def _latest_definitions(rt) -> list[dict]:
    latest: dict[str, dict] = {}
    for r in rt.repo.list_definitions(rt.tenant_id):
        latest[r["id"]] = r
    if rt.defn.id not in latest:
        latest[rt.defn.id] = {"id": rt.defn.id, "name": rt.defn.name, "prod_version": rt.defn.raw.get("version"), "definition": rt.defn.raw}
    return list(latest.values())


def agent_activities(rt) -> list[dict]:
    """배정할 수 있는 단계 = 코딩 에이전트 워커가 실행하는 단계(agentMode + cliagents) — 정의의 최신 판본 기준."""
    from . import engine
    out = []
    for d in _latest_definitions(rt):
        raw = d.get("definition") or {}
        roles = {r.get("name"): r for r in raw.get("roles") or [] if isinstance(r, dict)}
        for a in raw.get("activities") or []:
            if not isinstance(a, dict) or not a.get("id") or not engine.agent_mode_of(a):
                continue
            orch = a.get("orchestration")
            if not (orch in engine.NO_MODE or orch == engine.AGENT_ORCH):
                continue
            default = csv_list(a.get("agent")) or csv_list((roles.get(a.get("role")) or {}).get("endpoint"))
            out.append({"definition_id": d["id"], "definition_name": d.get("name") or raw.get("processDefinitionName"),
                        "version": d.get("prod_version"), "activity_id": a["id"], "name": a.get("name") or a["id"], "default_agents": default})
    return out


def assignment_board(rt) -> dict:
    repo, tenant_id = rt.repo, rt.tenant_id
    names = {u["id"]: _name(u) for u in repo.list_users(None, tenant_id)}
    maps = {(m["proc_def_id"], m["activity_id"]): m for m in repo.list_agent_map(tenant_id)}
    steps = []
    for s in agent_activities(rt):
        m = maps.pop((s["definition_id"], s["activity_id"]), None)
        steps.append({**s, "default_names": [names.get(a, a) for a in s["default_agents"]],
                      "assigned": {"agent_id": m["agent_id"], "name": names.get(m["agent_id"], m["agent_id"]), "by": m.get("by_user"),
                                   "updated_at": m.get("updated_at")} if m else None})
    from . import inbox, instance_mode
    bridge = getattr(instance_mode, "AGENT_BRIDGE", None)
    members = repo.list_role_members(tenant_id)
    roles = [{"id": r["id"], "name": _name(r),
              "members": [{"id": m["user_id"], "name": names.get(m["user_id"], m["user_id"]), "origin": origin_of(m)}
                          for m in members if m["role_id"] == r["id"]]} for r in inbox.role_users(repo, tenant_id)]
    return {"steps": steps, "roles": roles, "people": [{"id": u["id"], "name": _name(u)} for u in inbox.person_users(repo, tenant_id)],
            "orphans": [{"definition_id": k[0], "activity_id": k[1], "agent_id": m["agent_id"]} for k, m in maps.items()],
            "agents": [{"id": u["id"], "name": _name(u), "origin": origin_of(u)} for u in sorted(agents_of(repo, tenant_id), key=_name)],
            "agent_bridge": bridge,
            "bridge_note": ("지금 처리 엔진은 내장 결정론 경로(AGENT_BRIDGE=legacy)로 에이전트 단계를 처리합니다 — 배정은 작업 담당으로 기록 · 표시되지만 "
                            "판단은 내장 경로가 합니다. 배정한 에이전트의 프로필 · 스킬 · 도구로 실제 실행하려면 워커 경로(AGENT_BRIDGE=off + 워커)로 켜야 합니다.")
            if bridge == "legacy" else None}


def set_assignment(rt, definition_id: str, activity_id: str, agent_id: str, *, by: str | None = None) -> dict:
    repo, tenant_id = rt.repo, rt.tenant_id
    step = next((s for s in agent_activities(rt) if s["definition_id"] == definition_id and s["activity_id"] == activity_id), None)
    if step is None:
        raise AuthoringError(f"에이전트가 맡는 단계가 아닙니다: {definition_id} · {activity_id} (사람 · 시스템 단계는 에이전트로 배정하지 않습니다)", 404)
    row = _agent(repo, tenant_id, agent_id)
    if (row.get("agent_type") or "agent") != "agent":
        raise AuthoringError(f"시스템 수행자 '{_name(row)}'에게는 에이전트 단계를 배정할 수 없습니다")
    if agent_id in step["default_agents"]:
        raise AuthoringError(f"'{_name(row)}'은(는) 이 단계의 기본 담당입니다 — 기본으로 돌리려면 배정을 지우세요")
    repo.put_agent_map({"tenant_id": tenant_id, "proc_def_id": definition_id, "activity_id": activity_id, "agent_id": agent_id,
                        "origin": USER, "by_user": by})
    return {"definition_id": definition_id, "activity_id": activity_id, "agent_id": agent_id, "name": _name(row)}


def clear_assignment(rt, definition_id: str, activity_id: str) -> dict:
    if not rt.repo.drop_agent_map(rt.tenant_id, definition_id, activity_id):
        raise AuthoringError(f"배정이 없습니다: {definition_id} · {activity_id}", 404)
    return {"definition_id": definition_id, "activity_id": activity_id, "agent_id": None}


def apply_agent_map(rt, inst: dict, adv) -> None:
    """흐름이 에이전트 단계에 닿았을 때(IN_PROGRESS) 배정 표를 보고 작업 행 담당을 배정 에이전트로 쓴다(저장 전, 같은 트랜잭션).
    배정이 없으면 아무것도 하지 않는다 — 정의의 역할 담당(new_workitem 이 쓴 user_id)이 그대로 실행한다."""
    from . import engine
    rows = [r for r in adv.reached if r.get("status") == "IN_PROGRESS" and r.get("agent_mode") and r.get("agent_orch") == engine.AGENT_ORCH]
    if not rows:
        return
    reader = getattr(rt.repo, "get_agent_map", None)
    if not callable(reader):
        return
    for row in rows:
        m = reader(rt.tenant_id, row.get("proc_def_id"), row["activity_id"])
        if not m or m["agent_id"] == row.get("user_id"):
            continue
        agent = next((u for u in rt.repo.list_users([m["agent_id"]], rt.tenant_id) if u.get("is_agent")), None)
        if agent is None:                     # FK cascade 로 생기지 않지만, 생기면 기본 담당 그대로 두고 남긴다
            log.warning("agent map %s/%s points to a missing agent %s — default performer kept", row.get("proc_def_id"), row["activity_id"], m["agent_id"])
            continue
        before = row.get("user_id")
        row["user_id"], row["username"] = agent["id"], _name(agent)
        row["assignees"] = list(row.get("assignees") or []) + [{"endpoint": agent["id"], "kind": "agent", "via": before, "resolution": "agent-map"}]
        rt.repo.insert_assignment({"tenant_id": rt.tenant_id, "proc_inst_id": row["proc_inst_id"], "todo_id": row["id"], "from_user_id": before,
                                   "to_user_id": agent["id"], "kind": KIND_MAP, "by_user": m.get("by_user") or "sys:process",
                                   "reason": f"단계 배정: {row.get('activity_name') or row['activity_id']} → {_name(agent)}"})
        participants = inst.setdefault("participants", [])
        if agent["id"] not in participants:
            participants.append(agent["id"])


# ---------------------------------------------------------------- 역할 → 사람
def add_member(repo, tenant_id: str, role_id: str, user_id: str) -> dict:
    from . import inbox
    roles = {r["id"]: r for r in inbox.role_users(repo, tenant_id)}
    people = {u["id"]: u for u in inbox.person_users(repo, tenant_id)}
    if role_id not in roles:
        raise AuthoringError(f"그런 역할이 없습니다: {role_id}", 404)
    if user_id not in people:
        raise AuthoringError(f"사람 사용자만 역할에 넣을 수 있습니다: {user_id}", 404)
    if user_id in inbox.members_of(repo, tenant_id, role_id):
        raise AuthoringError(f"{_name(people[user_id])} 님은 이미 {_name(roles[role_id])} 역할입니다", 409)
    repo.put_role_member(tenant_id, role_id, user_id, USER)
    return {"role_id": role_id, "members": inbox.members_of(repo, tenant_id, role_id)}


def remove_member(repo, tenant_id: str, role_id: str, user_id: str) -> dict:
    from . import inbox
    row = next((m for m in repo.list_role_members(tenant_id, role_id) if m["user_id"] == user_id), None)
    if row is None:
        raise AuthoringError(f"그 사람은 이 역할이 아닙니다: {user_id}", 404)
    if origin_of(row) != USER:
        names = {u["id"]: _name(u) for u in repo.list_users([role_id, user_id], tenant_id)}
        raise AuthoringError(f"기본 업무분장({names.get(role_id, role_id)} ← {names.get(user_id, user_id)})은 뺄 수 없습니다 — 수업 기준이라 보호합니다. "
                             "포털에서 넣은 사람만 뺄 수 있습니다.", 403)
    repo.set_role_member(tenant_id, role_id, user_id, False)
    return {"role_id": role_id, "members": inbox.members_of(repo, tenant_id, role_id)}


# ---------------------------------------------------------------- 되돌리기
def reset(rt, *, by: str | None = None) -> dict:
    """포털에서 만든 것만 지운다: origin=user 에이전트 · 스킬 · 업무분장, 단계 배정 전부(배정은 모두 포털에서 만든다).
    기본(seed) 행은 건드리지 않는다. 실행 중인 작업이 학생 에이전트에 있으면 아무것도 지우지 않고 거절한다."""
    repo, tenant_id = rt.repo, rt.tenant_id
    agents = [u for u in repo.list_users(None, tenant_id) if u.get("is_agent") and origin_of(u) == USER]
    ids = [u["id"] for u in agents]
    busy = running_rows(repo, tenant_id, ids)
    if busy:
        raise AuthoringError(f"내가 만든 에이전트가 지금 실행 중인 작업이 {len(busy)}건 있습니다 — 끝난 뒤 다시 되돌리세요(아무것도 지우지 않았습니다)", 409)
    moved = return_open_rows(rt, ids, "기준으로 되돌리기 — 기본 담당으로", by)
    counts = repo.reset_user_authoring(tenant_id)
    log.info("agents reset by %s: %s", by, counts)
    return {**counts, "returned_tasks": moved}


# ---------------------------------------------------------------- 저장소 (Memory · Pg)
class MemoryAuthoring:
    """MemoryRepo 의 쓰기 쪽. users · _skills · _agent_skills · role_members 는 MemoryRepo/MemoryAgents 의 것을 같이 쓴다."""
    def _maps(self) -> dict:
        if not hasattr(self, "_agent_map"):
            self._agent_map = {}
        return self._agent_map

    def write_agent(self, row: dict, skills: list[str], *, create: bool) -> None:
        row = {k: v for k, v in row.items() if k != "skills"}
        row["updated_at"] = now_iso()
        if create:
            row.setdefault("created_at", row["updated_at"])
        self.users[row["id"]] = deepcopy(row)
        tenant = row.get("tenant_id", "hyd")
        rows = self._agent_skill_rows()
        rows[:] = [r for r in rows if not (r["user_id"] == row["id"] and r["tenant_id"] == tenant)]
        for s in skills:
            self.attach_skill(row["id"], s, tenant)

    def remove_agent(self, tenant_id: str, agent_id: str) -> None:
        self.users.pop(agent_id, None)
        self._agent_skill_rows()[:] = [r for r in self._agent_skill_rows() if r["user_id"] != agent_id]
        for k in [k for k, m in self._maps().items() if m["agent_id"] == agent_id]:
            del self._maps()[k]

    def write_skill(self, row: dict, *, create: bool) -> None:
        now = now_iso()
        key = (row.get("tenant_id") or "hyd", row["skill_name"])
        old = self._skill_rows().get(key) or {}
        self._skill_rows()[key] = {"description": "", "content": "", **old, **row, "tenant_id": key[0], "updated_at": now,
                                   "created_at": old.get("created_at") or now}

    def remove_skill(self, tenant_id: str, name: str) -> None:
        self._skill_rows().pop((tenant_id, name), None)
        self._agent_skill_rows()[:] = [r for r in self._agent_skill_rows() if not (r["tenant_id"] == tenant_id and r["skill_name"] == name)]

    def link_skill(self, tenant_id: str, agent_id: str, name: str, on: bool) -> None:
        if on:
            self.attach_skill(agent_id, name, tenant_id)
        else:
            self._agent_skill_rows()[:] = [r for r in self._agent_skill_rows()
                                           if not (r["tenant_id"] == tenant_id and r["user_id"] == agent_id and r["skill_name"] == name)]

    def list_agent_map(self, tenant_id: str) -> list[dict]:
        return [deepcopy(m) for (t, _, _), m in sorted(self._maps().items()) if t == tenant_id]

    def get_agent_map(self, tenant_id: str, proc_def_id: str | None, activity_id: str) -> dict | None:
        m = self._maps().get((tenant_id, proc_def_id, activity_id))
        return deepcopy(m) if m else None

    def put_agent_map(self, row: dict) -> None:
        key = (row["tenant_id"], row["proc_def_id"], row["activity_id"])
        now = now_iso()
        self._maps()[key] = {**row, "created_at": (self._maps().get(key) or {}).get("created_at") or now, "updated_at": now}

    def drop_agent_map(self, tenant_id: str, proc_def_id: str, activity_id: str) -> bool:
        return self._maps().pop((tenant_id, proc_def_id, activity_id), None) is not None

    def put_role_member(self, tenant_id: str, role_id: str, user_id: str, origin: str) -> None:
        self.set_role_member(tenant_id, role_id, user_id, True)
        for m in self.role_members:
            if m["tenant_id"] == tenant_id and m["role_id"] == role_id and m["user_id"] == user_id:
                m["origin"] = origin

    def reset_user_authoring(self, tenant_id: str) -> dict:
        agents = [uid for uid, u in self.users.items() if u.get("tenant_id", "hyd") == tenant_id and u.get("is_agent") and origin_of(u) == USER]
        skills = [n for (t, n), s in self._skill_rows().items() if t == tenant_id and origin_of(s) == USER]
        maps = [k for k in self._maps() if k[0] == tenant_id]
        members = [m for m in self.role_members if m["tenant_id"] == tenant_id and origin_of(m) == USER]
        before = len(self._agent_skill_rows())
        for k in maps:
            del self._maps()[k]
        for aid in agents:
            self.remove_agent(tenant_id, aid)
        for n in skills:
            self.remove_skill(tenant_id, n)
        self.role_members = [m for m in self.role_members if m not in members]
        return {"agents": len(agents), "skills": len(skills), "attachments": before - len(self._agent_skill_rows()),
                "assignments": len(maps), "role_members": len(members)}


class PgAuthoring:
    AGENT_COLS = ("username", "role", "goal", "persona", "model", "tools")

    def write_agent(self, row: dict, skills: list[str], *, create: bool) -> None:
        with self._conn() as c, c.transaction():
            if create:
                c.execute("insert into users (id, username, role, is_agent, agent_type, goal, persona, model, tools, tenant_id, origin, updated_at) "
                          "values (%s, %s, %s, true, 'agent', %s, %s, %s, %s, %s, %s, now())",
                          (row["id"], row["username"], row.get("role"), row.get("goal"), row.get("persona"), row.get("model"), row.get("tools"),
                           row.get("tenant_id") or "hyd", row.get("origin") or USER))
            else:
                n = c.execute("update users set username=%s, role=%s, goal=%s, persona=%s, model=%s, tools=%s, updated_at=now() "
                              "where id=%s and tenant_id=%s and is_agent and origin='user'",
                              (row["username"], row.get("role"), row.get("goal"), row.get("persona"), row.get("model"), row.get("tools"),
                               row["id"], row.get("tenant_id") or "hyd")).rowcount
                if n != 1:
                    raise AuthoringError("기본 에이전트이거나 이미 지워진 에이전트라 고치지 않았습니다", 409)
            c.execute("delete from agent_skills where user_id=%s and tenant_id=%s", (row["id"], row.get("tenant_id") or "hyd"))
            for s in skills:
                c.execute("insert into agent_skills (user_id, tenant_id, skill_name) values (%s, %s, %s)", (row["id"], row.get("tenant_id") or "hyd", s))

    def remove_agent(self, tenant_id: str, agent_id: str) -> None:
        with self._conn() as c:      # agent_skills · activity_agent_map 은 FK on delete cascade
            if c.execute("delete from users where id=%s and tenant_id=%s and is_agent and origin='user'", (agent_id, tenant_id)).rowcount != 1:
                raise AuthoringError("기본 에이전트이거나 이미 지워진 에이전트라 지우지 않았습니다", 409)

    def write_skill(self, row: dict, *, create: bool) -> None:
        with self._conn() as c:
            if create:
                c.execute("insert into tenant_skills (tenant_id, skill_name, description, content, owner_id, origin) values (%s, %s, %s, %s, %s, %s)",
                          (row["tenant_id"], row["skill_name"], row["description"], row["content"], row.get("owner_id"), row.get("origin") or USER))
            elif c.execute("update tenant_skills set description=%s, content=%s, updated_at=now() where tenant_id=%s and skill_name=%s and origin='user'",
                           (row["description"], row["content"], row["tenant_id"], row["skill_name"])).rowcount != 1:
                raise AuthoringError("기본 스킬이거나 이미 지워진 스킬이라 고치지 않았습니다", 409)

    def remove_skill(self, tenant_id: str, name: str) -> None:
        with self._conn() as c:      # agent_skills 는 FK on delete cascade
            if c.execute("delete from tenant_skills where tenant_id=%s and skill_name=%s and origin='user'", (tenant_id, name)).rowcount != 1:
                raise AuthoringError("기본 스킬이거나 이미 지워진 스킬이라 지우지 않았습니다", 409)

    def link_skill(self, tenant_id: str, agent_id: str, name: str, on: bool) -> None:
        with self._conn() as c:
            if on:
                c.execute("insert into agent_skills (user_id, tenant_id, skill_name) values (%s, %s, %s) on conflict do nothing", (agent_id, tenant_id, name))
            else:
                c.execute("delete from agent_skills where user_id=%s and tenant_id=%s and skill_name=%s", (agent_id, tenant_id, name))

    def list_agent_map(self, tenant_id: str) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("select * from activity_agent_map where tenant_id=%s order by proc_def_id, activity_id",
                                                    (tenant_id,)).fetchall()]

    def get_agent_map(self, tenant_id: str, proc_def_id: str | None, activity_id: str) -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("select * from activity_agent_map where tenant_id=%s and proc_def_id=%s and activity_id=%s",
                                       (tenant_id, proc_def_id, activity_id)).fetchone())

    def put_agent_map(self, row: dict) -> None:
        with self._conn() as c:
            c.execute("insert into activity_agent_map (tenant_id, proc_def_id, activity_id, agent_id, origin, by_user) values (%s, %s, %s, %s, %s, %s) "
                      "on conflict (tenant_id, proc_def_id, activity_id) do update set agent_id=excluded.agent_id, origin=excluded.origin, "
                      "by_user=excluded.by_user, updated_at=now()",
                      (row["tenant_id"], row["proc_def_id"], row["activity_id"], row["agent_id"], row.get("origin") or USER, row.get("by_user")))

    def drop_agent_map(self, tenant_id: str, proc_def_id: str, activity_id: str) -> bool:
        with self._conn() as c:
            return c.execute("delete from activity_agent_map where tenant_id=%s and proc_def_id=%s and activity_id=%s",
                             (tenant_id, proc_def_id, activity_id)).rowcount == 1

    def put_role_member(self, tenant_id: str, role_id: str, user_id: str, origin: str) -> None:
        with self._conn() as c:
            c.execute("insert into role_members (tenant_id, role_id, user_id, origin) values (%s, %s, %s, %s) on conflict do nothing",
                      (tenant_id, role_id, user_id, origin))

    def reset_user_authoring(self, tenant_id: str) -> dict:
        with self._conn() as c, c.transaction():
            maps = c.execute("delete from activity_agent_map where tenant_id=%s", (tenant_id,)).rowcount
            attachments = c.execute("""delete from agent_skills a where a.tenant_id=%s and (
                    exists (select 1 from users u where u.id=a.user_id and u.origin='user')
                    or exists (select 1 from tenant_skills s where s.tenant_id=a.tenant_id and s.skill_name=a.skill_name and s.origin='user'))""",
                                    (tenant_id,)).rowcount
            agents = c.execute("delete from users where tenant_id=%s and is_agent and origin='user'", (tenant_id,)).rowcount
            skills = c.execute("delete from tenant_skills where tenant_id=%s and origin='user'", (tenant_id,)).rowcount
            members = c.execute("delete from role_members where tenant_id=%s and origin='user'", (tenant_id,)).rowcount
        return {"agents": agents, "skills": skills, "attachments": attachments, "assignments": maps, "role_members": members}
