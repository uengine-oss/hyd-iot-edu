"""U5 (mini ProcessGPT TODO 5): 역할 → 사람 배정 · 내 작업함 · 알림.

HYD 에는 로그인이 없다. 작업(todolist)의 user_id 는 정의의 역할 바인딩(role:operator …, engine.new_workitem)이고 포털은
"나"를 브라우저에서 고른다. 이 모듈이 그 사이를 잇는다(vue3 의 /work-assignment · delegation_history · /my-inbox · /notifications 에 해당):

    업무분장  role_members(역할 → 사람). 역할에 사람이 **한 명**이면 단계가 열릴 때 그 사람(user:*)에게 바로 배정하고,
             **여럿**이면 역할 공용(user_id 는 역할 그대로)으로 남긴다. 아무도 없으면 역할 그대로(누구의 작업함에도 안 뜬다 — 조용한 성공 금지,
             작업함 응답의 unassigned_roles 로 알린다).
    배정 이력 task_assignments(auto). 업무분장으로 사람에게 바로 배정된 것만 남는다. 수동 재배정·위임은 범위 밖(TODO A3).
    승인자   포털의 "나"(user:*)로 승인하면 check_actor 가 그 사람이 내세운 역할의 구성원인지 본다(아니면 403). 역할 등급 검사
             (Skill -APPROVED_BY-> Role, hooks.approve_decision)는 그대로 — 권한이 낮은 역할의 승인은 여전히 403.
    알림      notifications. 사람 단계가 열리면 배정된 사람(역할 공용이면 역할 구성원 모두)에게, 처리 건이 끝나면 참여자에게 쓴다.
             에이전트의 질문 알림은 워커가 쓴다(agent-worker runner._asker_of → role:operator). 역할 id 로 온 알림은 그 역할 사람이 모두 본다.

엔진 훅: 흐름이 단계에 닿는 다섯 자리(process_workitem · _fire_timeout · _abort_before_action · start_definition · rework)에서
apply_advance(rt, inst, adv) 를 저장 전에 부른다 — 배정은 같은 트랜잭션에 쓰이고 알림은 커밋 뒤(_after_commit) 쓴다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from hydcommon.timeutil import parse_iso

log = logging.getLogger("process.inbox")

PERSON = "user:"
ROLE = "role:"
TYPE_TASK = "task_assigned"          # 사람 단계가 나에게 옴
TYPE_END = "instance_completed"      # 내 처리 건이 끝남
TYPE_QUESTION = "workitem_bpm"       # 에이전트의 질문 (agent-worker 가 쓰는 type)


# ---------------------------------------------------------------- 업무분장 조회
def person_users(repo, tenant_id: str) -> list[dict]:
    """사람 사용자: is_agent 가 아니고 id 가 user:* 인 행(역할 사용자 role:* 는 온톨로지 Role 이지 사람이 아니다)."""
    return [u for u in repo.list_users(None, tenant_id) if not u.get("is_agent") and str(u.get("id", "")).startswith(PERSON)]


def role_users(repo, tenant_id: str) -> list[dict]:
    return [u for u in repo.list_users(None, tenant_id) if str(u.get("id", "")).startswith(ROLE)]


def members_of(repo, tenant_id: str, role_id: str) -> list[str]:
    return sorted({m["user_id"] for m in repo.list_role_members(tenant_id, role_id)})


def roles_of(repo, tenant_id: str, user_id: str) -> list[str]:
    return sorted({m["role_id"] for m in repo.list_role_members(tenant_id) if m["user_id"] == user_id})


def resolve(repo, tenant_id: str, endpoint: str | None) -> dict:
    """역할 바인딩 하나를 사람으로 해석한다. {'kind': 'person'|'role'|'none', 'user_id': 배정할 user_id, 'members': [...]}.
    사람 한 명이면 person(그 사람), 여럿이면 role(역할 공용), 없으면 none(역할 그대로, 작업함에 안 뜸)."""
    if not endpoint:
        return {"kind": "none", "user_id": endpoint, "members": []}
    if endpoint.startswith(PERSON):
        return {"kind": "person", "user_id": endpoint, "members": [endpoint]}
    if endpoint.startswith(ROLE):
        members = members_of(repo, tenant_id, endpoint)
        if len(members) == 1:
            return {"kind": "person", "user_id": members[0], "members": members}
        return {"kind": "role" if members else "none", "user_id": endpoint, "members": members}
    return {"kind": "none", "user_id": endpoint, "members": []}


def is_human_row(row: dict) -> bool:
    return not row.get("agent_orch") and not row.get("agent_mode") and not str(row.get("user_id") or "").startswith("sys:")


def notification_targets(repo, tenant_id: str, endpoint: str | None) -> list[str]:
    """알림을 받을 사람들. 사람이면 그 사람, 역할이면 구성원 모두, 구성원이 없으면 역할 id 그대로(나중에 역할에 들어온 사람이 본다)."""
    r = resolve(repo, tenant_id, endpoint)
    return r["members"] or ([endpoint] if endpoint else [])


# ---------------------------------------------------------------- 엔진 훅
def apply_advance(rt, inst: dict, adv) -> None:
    """흐름이 닿은 사람 단계를 업무분장으로 해석해 user_id 를 쓰고(저장 전, 같은 트랜잭션), 알림을 커밋 뒤에 예약한다."""
    tenant = rt.tenant_id
    from .agent_authoring import apply_agent_map
    apply_agent_map(rt, inst, adv)        # B1: 에이전트 단계 → 배정 표(activity_agent_map)의 에이전트(없으면 정의의 역할 담당 그대로)
    for row in adv.reached:
        if row.get("status") != "IN_PROGRESS" or not is_human_row(row):
            continue
        endpoint = row.get("user_id")
        r = resolve(rt.repo, tenant, endpoint)
        if r["kind"] == "person" and r["user_id"] != endpoint:
            row["user_id"] = r["user_id"]
            row["assignees"] = list(row.get("assignees") or []) + [{"endpoint": r["user_id"], "kind": "person", "via": endpoint, "resolution": "sole-member"}]
            rt.repo.insert_assignment({"tenant_id": tenant, "proc_inst_id": row["proc_inst_id"], "todo_id": row["id"], "from_user_id": endpoint, "to_user_id": r["user_id"],
                                       "kind": "auto", "by_user": "sys:process", "reason": f"업무분장: {endpoint} 에 사람이 한 명"})
            participants = inst.setdefault("participants", [])
            if r["user_id"] not in participants:
                participants.append(r["user_id"])
        rt._after_commit(_notify_task, rt.repo, tenant, inst, dict(row), endpoint)
    if adv.ended:
        try:
            end_name = (rt.definition_for(inst).events.get(adv.ended) or {}).get("name") or "종료"
        except (LookupError, ValueError):
            end_name = "종료"
        rt._after_commit(_notify_end, rt.repo, tenant, dict(inst), end_name)


def task_url(proc_inst_id: str, todo_id: str) -> str:
    """포털 주소(해시 뒤): 처리 건 하나의 단계 하나. 알림·작업함 링크가 같은 모양을 쓴다."""
    return f"/instances/{proc_inst_id}/task/{todo_id}"


def _notify_task(repo, tenant, inst, row, endpoint):
    name = inst.get("proc_inst_name") or inst.get("proc_inst_id")
    targets = notification_targets(repo, tenant, endpoint)
    shared = len(targets) > 1
    for user_id in targets:
        repo.insert_notification({"title": row.get("activity_name") or row.get("activity_id"), "type": TYPE_TASK,   # 제목 = 단계 이름(포털이 화면 이름으로 바꾼다)
                                  "description": f"{name} · " + ("역할 공용 작업이 열렸습니다" if shared else "내 차례입니다"),
                                  "user_id": user_id, "tenant_id": tenant, "url": task_url(row["proc_inst_id"], row["id"]), "from_user_id": "sys:process"})


def _notify_end(repo, tenant, inst, end_name):
    name = inst.get("proc_inst_name") or inst.get("proc_inst_id")
    seen: list[str] = []
    for p in inst.get("participants") or []:
        if str(p).startswith("sys:"):
            continue
        for user_id in notification_targets(repo, tenant, p):
            if user_id not in seen:
                seen.append(user_id)
    for user_id in seen:
        repo.insert_notification({"title": f"{name} 종료", "type": TYPE_END, "description": f"끝난 곳: {end_name}",
                                  "user_id": user_id, "tenant_id": tenant, "url": f"/instances/{inst['proc_inst_id']}", "from_user_id": "sys:process"})


# ---------------------------------------------------------------- 승인자 = "나"
def check_actor(repo, tenant_id: str, by: str | None, role: str | None) -> str | None:
    """포털의 "나"(사람 사용자 id)로 승인할 때, 그 사람이 내세운 역할의 구성원인지 서버가 확인한다.
    by 가 user:* 가 아니면(회귀 검사기·옛 화면의 자유 입력) 아무것도 하지 않는다 — 역할 등급 검사(approve_decision)는 어느 쪽이든 그대로다.
    통과하면 사람 id 를, 아니면 PermissionError(→ 403)."""
    if not str(by or "").startswith(PERSON):
        return None
    user = next(iter(repo.list_users([by], tenant_id)), None)
    if user is None or user.get("is_agent"):
        raise PermissionError(f"없는 사람 사용자입니다: {by}")
    mine = roles_of(repo, tenant_id, by)
    if role not in mine:
        names = {r["id"]: r.get("username") or r["id"] for r in role_users(repo, tenant_id)}
        held = ", ".join(names.get(r, r) for r in mine) or "없음"
        raise PermissionError(f"{user.get('username') or by} 님은 {names.get(role, role)} 역할이 아니어서 그 역할로 승인할 수 없습니다(내 역할: {held})")
    return by


# ---------------------------------------------------------------- 내 작업함
def inbox_view(rt, user_id: str, now=None) -> dict:
    """나에게 배정된 것 · 내 역할 공용인 것 · 내 역할에 온 에이전트 질문. 각 항목은 처리 건 이름 · 단계 이름 · 기한(붙은 타이머)을 품는다."""
    repo, tenant = rt.repo, rt.tenant_id
    user = next((u for u in repo.list_users([user_id], tenant)), None)
    if user is None or not str(user_id).startswith(PERSON):
        raise LookupError(f"없는 사람 사용자입니다: {user_id}")
    my_roles = roles_of(repo, tenant, user_id)
    mine = set(my_roles) | {user_id}
    instances = {i["proc_inst_id"]: i for i in repo.list_instances(status="RUNNING", limit=500, tenant_id=tenant)}
    rows = repo.list_workitems(status="IN_PROGRESS", limit=500, tenant_id=tenant)
    tasks, asked, unassigned = [], [], {}
    timers: dict[str, list[dict]] = {}
    for w in rows:
        timers.setdefault(w["proc_inst_id"], []).append(w)
    for w in rows:
        inst = instances.get(w["proc_inst_id"])
        if inst is None:
            continue
        if w.get("draft_status") == "HUMAN_ASKED":
            bound = {b.get("endpoint") for b in inst.get("role_bindings") or []} | set(inst.get("participants") or [])
            if bound & mine:
                asked.append(_item(rt, inst, w, timers, "question", "role", now))
            continue
        if not is_human_row(w):
            continue
        owner = w.get("user_id")
        if owner == user_id:
            tasks.append(_item(rt, inst, w, timers, _kind(rt, inst, w), "me", now))
        elif owner in my_roles:
            tasks.append(_item(rt, inst, w, timers, _kind(rt, inst, w), "role", now))
        elif str(owner or "").startswith(ROLE) and not members_of(repo, tenant, owner):
            unassigned[owner] = unassigned.get(owner, 0) + 1
    tasks.sort(key=lambda t: (t["assignment"] != "me", t.get("due_date") or "9", t["start_date"]))
    return {"user": user, "roles": my_roles, "tasks": tasks, "asked": asked,
            "unassigned_roles": [{"role_id": r, "open_tasks": n} for r, n in sorted(unassigned.items())],
            "unread": repo.count_unread_notifications(tenant, sorted(mine))}


def _kind(rt, inst, w) -> str:
    try:
        tool = (rt.definition_for(inst).activities.get(w["activity_id"]) or {}).get("tool") or ""
    except (LookupError, ValueError):
        tool = ""
    return "select" if tool == "formHandler:select_card" else "form"


def _item(rt, inst, w, timers, kind, assignment, now=None) -> dict:
    due = None
    try:
        attached = {e["id"] for e in rt.definition_for(inst).attached_events(w["activity_id"])}
    except (LookupError, ValueError):
        attached = set()
    for t in timers.get(w["proc_inst_id"], []):
        if t["activity_id"] in attached and t.get("due_date"):
            due = t["due_date"] if due is None else min(due, t["due_date"])
    return {"id": w["id"], "proc_inst_id": w["proc_inst_id"], "proc_inst_name": inst.get("proc_inst_name"), "proc_def_id": inst.get("proc_def_id"),
            "activity_id": w["activity_id"], "activity_name": w.get("activity_name"), "status": w["status"], "draft_status": w.get("draft_status"),
            "user_id": w.get("user_id"), "username": w.get("username"), "start_date": w.get("start_date"), "due_date": due,
            "kind": kind, "assignment": assignment, "generation": w.get("generation") or 0,
            "elapsed_s": _elapsed(w.get("start_date"), now), "link": "#" + task_url(w["proc_inst_id"], w["id"])}


def _elapsed(start, now=None) -> int | None:
    """단계가 열린 뒤 지난 실제 초(벽시계). 시작 시각이 없거나 읽을 수 없으면 None — 화면은 '–'로 보인다."""
    if not start:
        return None
    try:
        began = start if isinstance(start, datetime) else parse_iso(str(start))
    except ValueError:
        return None
    if began.tzinfo is None:
        began = began.replace(tzinfo=timezone.utc)
    return max(0, int(((now or datetime.now(timezone.utc)) - began).total_seconds()))


# ---------------------------------------------------------------- 알림
def with_links(repo, notes: list[dict]) -> list[dict]:
    """알림마다 포털 링크(link)를 붙인다. 워커의 질문 알림은 url 이 /todolist/<id> 라 처리 건 id 를 작업에서 찾는다.
    작업이 지워졌으면 link 는 None 이고 link_error 에 사유를 둔다(빈 링크로 조용히 두지 않는다)."""
    out = []
    for n in notes:
        n = dict(n)
        url = str(n.get("url") or "")
        if url.startswith("/instances/"):
            n["link"] = "#" + url
        elif url.startswith("/todolist/"):
            wi = repo.get_workitem(url.rsplit("/", 1)[-1])
            n["link"] = "#" + task_url(wi["proc_inst_id"], wi["id"]) if wi else None
            if not wi:
                n["link_error"] = "알림이 가리키는 작업을 찾지 못했습니다"
        else:
            n["link"] = None
        out.append(n)
    return out


def user_ids_for(repo, tenant_id: str, user_id: str) -> list[str]:
    """알림 조회 대상 id: 나 + 내 역할(역할 id 로 온 알림, 예: 워커의 질문 알림)."""
    return sorted({user_id, *roles_of(repo, tenant_id, user_id)})


def assignment_board(repo, tenant_id: str) -> dict:
    """업무분장 화면: 역할마다 구성원, 사람마다 역할."""
    members = repo.list_role_members(tenant_id)
    roles = [{"id": r["id"], "name": r.get("username") or r["id"], "members": sorted({m["user_id"] for m in members if m["role_id"] == r["id"]})}
             for r in role_users(repo, tenant_id)]
    people = [{"id": u["id"], "name": u.get("username") or u["id"], "email": u.get("email"), "roles": sorted({m["role_id"] for m in members if m["user_id"] == u["id"]})}
              for u in person_users(repo, tenant_id)]
    return {"roles": roles, "people": people}
