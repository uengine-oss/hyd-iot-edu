"""U5 — 역할 → 사람 배정 · 내 작업함 · 알림 (procsvc/inbox.py · inbox_api.py · migration 000029 의 MemoryRepo 대응).
인수: 담당자별 작업함(업무분장이 바뀌면 그 사람 작업함에만 뜸) · 역할 권한이 낮은 사람의 승인은 여전히 403 · "나"가 아닌 역할로 승인하면 403 ·
알림 생성(사람 단계 도착 · 에이전트 질문 · 내 처리 건 종결)과 읽음 · SSE 는 내 것만."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import engine, inbox, inbox_api, instance_mode, instances, procdb
from test_instances import ALERT, DEF_PATH, NOW, FakeHooks, _agent_tasks, _by

KIM, CHOI, LEE, PARK = "user:kim-op", "user:choi-op", "user:lee-prod", "user:park-maint"


def _people(repo):
    """seed.sql 과 같은 업무분장: 운전원 2명(역할 공용) · 생산관리자 1명(그 사람에게 바로) · 정비관리자 1명."""
    for uid, name in (("role:operator", "운전원"), ("role:prod-mgr", "생산관리자"), ("role:maint-mgr", "정비관리자")):
        repo.upsert_user({"id": uid, "username": name, "is_agent": False, "tenant_id": "hyd"})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트", "is_agent": True, "agent_type": "agent", "tenant_id": "hyd"})
    for uid, name in ((KIM, "김운전"), (CHOI, "최운전"), (LEE, "이생산"), (PARK, "박정비")):
        repo.upsert_user({"id": uid, "username": name, "is_agent": False, "tenant_id": "hyd"})
    for role, uid in (("role:operator", KIM), ("role:operator", CHOI), ("role:prod-mgr", LEE), ("role:maint-mgr", PARK)):
        repo.set_role_member("hyd", role, uid, True)


@pytest.fixture
def rt():
    hooks = FakeHooks()
    repo = procdb.MemoryRepo()
    _people(repo)
    return instances.InstanceRuntime(repo, engine.Definition.load(DEF_PATH), hooks, time_scale=20.0), hooks


def _notes(repo, user_id, kind=None):
    return [n for n in repo.notifications if n["user_id"] == user_id and (kind is None or n["type"] == kind)]


def _select_open(rt):
    inst = rt.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(rt)
    return inst, _by(rt, inst, "task:select")


def test_resolution_rule_sole_member_person_many_role_shared(rt):
    rt, _ = rt
    assert inbox.resolve(rt.repo, "hyd", "role:prod-mgr") == {"kind": "person", "user_id": LEE, "members": [LEE]}
    assert inbox.resolve(rt.repo, "hyd", "role:operator") == {"kind": "role", "user_id": "role:operator", "members": [CHOI, KIM]}
    assert inbox.resolve(rt.repo, "hyd", "role:nobody")["kind"] == "none"
    assert inbox.resolve(rt.repo, "hyd", KIM)["kind"] == "person"
    assert inbox.roles_of(rt.repo, "hyd", KIM) == ["role:operator"] and inbox.members_of(rt.repo, "hyd", "role:maint-mgr") == [PARK]


def test_shared_role_task_shows_in_every_member_inbox_and_notifies_each(rt):
    rt, _ = rt
    inst, sel = _select_open(rt)
    assert sel["user_id"] == "role:operator"                          # 운전원이 2명 → 역할 공용으로 남는다
    for uid in (KIM, CHOI):
        box = inbox.inbox_view(rt, uid)
        assert [(t["activity_id"], t["assignment"], t["kind"]) for t in box["tasks"]] == [("task:select", "role", "select")]
        assert box["tasks"][0]["proc_inst_name"] == inst["proc_inst_name"] and box["tasks"][0]["due_date"]   # 붙은 선택 시간 초과 타이머의 기한
        assert len(_notes(rt.repo, uid, inbox.TYPE_TASK)) == 1 and _notes(rt.repo, uid)[0]["url"] == f"/instances/{inst['proc_inst_id']}/task/{sel['id']}"
        assert box["tasks"][0]["link"] == f"#/instances/{inst['proc_inst_id']}/task/{sel['id']}" and box["tasks"][0]["elapsed_s"] >= 0
    assert inbox.inbox_view(rt, LEE)["tasks"] == [] and _notes(rt.repo, LEE) == []
    assert rt.repo.list_assignments(sel["id"], "hyd") == []            # 자동 해석 이력은 사람에게 배정됐을 때만


def test_sole_member_role_assigns_the_person_on_reach_with_history(rt):
    rt, _ = rt
    inst, sel = _select_open(rt)
    assert rt.fire_timeouts(now=NOW.replace(year=2027))               # 선택 시간 초과 → 상급자 호출(생산관리자) 단계가 열린다
    esc = _by(rt, inst, "task:escalate")
    assert esc["status"] == "IN_PROGRESS" and esc["user_id"] == LEE  # 생산관리자는 1명 → 이생산에게 바로
    assert esc["assignees"][-1] == {"endpoint": LEE, "kind": "person", "via": "role:prod-mgr", "resolution": "sole-member"}
    (auto,) = rt.repo.list_assignments(esc["id"], "hyd")
    assert auto["kind"] == "auto" and auto["from_user_id"] == "role:prod-mgr" and auto["to_user_id"] == LEE
    box = inbox.inbox_view(rt, LEE)
    assert [(t["activity_id"], t["assignment"]) for t in box["tasks"]] == [("task:escalate", "me")]
    assert LEE in rt.repo.get_instance(inst["proc_inst_id"])["participants"]
    assert [(n["title"], n["description"]) for n in _notes(rt.repo, LEE, inbox.TYPE_TASK)] == [(esc["activity_name"], f"{inst['proc_inst_name']} · 내 차례입니다")]
    assert inbox.inbox_view(rt, KIM)["tasks"] == []                   # 취소된 선택 단계는 더 이상 운전원 작업함에 없다


def test_membership_change_moves_shared_task_to_sole_member_only(rt):
    """담당자별 작업함: 업무분장에서 최운전이 빠지면 다음에 열리는 운전원 단계는 김운전 한 사람에게 바로 가고, 최운전 작업함에는 없다."""
    rt, _ = rt
    rt.repo.set_role_member("hyd", "role:operator", CHOI, False)
    inst, sel = _select_open(rt)
    assert sel["user_id"] == KIM and [a["to_user_id"] for a in rt.repo.list_assignments(sel["id"], "hyd")] == [KIM]
    assert [t["assignment"] for t in inbox.inbox_view(rt, KIM)["tasks"]] == ["me"]
    assert inbox.inbox_view(rt, CHOI)["tasks"] == [] and inbox.inbox_view(rt, LEE)["tasks"] == []
    assert [n["description"].rsplit(" · ", 1)[-1] for n in _notes(rt.repo, KIM, inbox.TYPE_TASK)] == ["내 차례입니다"] and _notes(rt.repo, CHOI) == []


def test_role_without_members_is_reported_not_silently_dropped(rt):
    """역할에 아무도 없으면 단계는 역할 그대로 남아 누구의 작업함에도 안 뜬다 — 그 사실을 작업함 응답이 말한다(조용한 성공 금지)."""
    rt, _ = rt
    for uid in (KIM, CHOI):
        rt.repo.set_role_member("hyd", "role:operator", uid, False)
    inst, sel = _select_open(rt)
    assert sel["user_id"] == "role:operator" and rt.repo.list_assignments(sel["id"], "hyd") == []
    box = inbox.inbox_view(rt, LEE)
    assert box["tasks"] == [] and box["unassigned_roles"] == [{"role_id": "role:operator", "open_tasks": 1}]
    assert _notes(rt.repo, "role:operator", inbox.TYPE_TASK)                # 알림은 역할 앞으로 남아 나중에 들어온 사람이 본다


def test_approve_as_me_requires_role_membership_and_level(rt):
    """승인자 입력 대체: "나"(user:*)로 승인하면 그 사람의 역할로만 — 남의 역할을 내세우면 403. 역할 등급 검사도 그대로 403."""
    rt, hooks = rt
    inst, sel = _select_open(rt)
    with pytest.raises(PermissionError, match="김운전 님은 생산관리자 역할이 아니어서"):
        rt.select(sel["id"], "DEC-1003-001", "skill:fan-max-derate", by=KIM, role="role:prod-mgr", now=NOW)
    with pytest.raises(PermissionError, match="없는 사람 사용자"):
        rt.select(sel["id"], "DEC-1003-001", "skill:fan-max-derate", by="user:ghost", role="role:operator", now=NOW)
    hooks.approve_decision = hooks._deny                                   # 카드의 승인 역할이 운전원보다 높다
    with pytest.raises(PermissionError):
        rt.select(sel["id"], "DEC-1003-001", "skill:fan-max-derate", by=KIM, role="role:operator", now=NOW)
    assert rt.repo.get_workitem(sel["id"])["status"] == "IN_PROGRESS" and rt.repo.list_approvals(inst["proc_inst_id"], "hyd") == []
    # 자유 입력 승인자(회귀 검사기·옛 화면)는 역할 구성원 검사를 건너뛰고 등급 검사만 받는다
    assert inbox.check_actor(rt.repo, "hyd", "OP-17", "role:prod-mgr") is None
    assert inbox.check_actor(rt.repo, "hyd", LEE, "role:prod-mgr") == LEE


def test_instance_end_notifies_every_participant_once(rt):
    rt, hooks = rt
    inst, sel = _select_open(rt)
    rt.select(sel["id"], "DEC-1003-001", "skill:fan-max-derate", by=LEE, role="role:prod-mgr", reason="납기", fan_pct=90, now=NOW)
    assert LEE in rt.repo.get_instance(inst["proc_inst_id"])["participants"]       # "나"로 승인한 사람도 참여자
    rt.on_incident_update("RE_OBSERVING", "INC-1003-01", cleared=False, now=NOW)
    rt.on_incident_update("RESOLVED", "INC-1003-01", cleared=True, now=NOW)
    assert rt.repo.get_instance(inst["proc_inst_id"])["status"] == "COMPLETED"
    for uid in (KIM, CHOI, LEE):                                        # 운전원(역할 공용 → 두 사람) · 승인한 생산관리자
        (note,) = _notes(rt.repo, uid, inbox.TYPE_END)
        assert note["url"] == f"/instances/{inst['proc_inst_id']}" and note["description"] == "끝난 곳: 종결"
    assert _notes(rt.repo, PARK, inbox.TYPE_END) == []


def test_notifications_read_and_role_addressed_question_visible_to_members(rt):
    rt, _ = rt
    inst, sel = _select_open(rt)
    # 워커가 쓰는 질문 알림(role:operator 앞으로)은 역할 구성원 모두가 본다
    rt.repo.insert_notification({"title": "현장 펌프 소음이 있나요?", "type": inbox.TYPE_QUESTION, "user_id": "role:operator", "from_user_id": "sys:agent",
                                 "url": f"/todolist/{sel['id']}"})
    ids = inbox.user_ids_for(rt.repo, "hyd", KIM)
    assert ids == ["role:operator", KIM]
    assert rt.repo.count_unread_notifications("hyd", ids) == 2
    rows = rt.repo.list_notifications("hyd", ids, unread_only=True)
    assert rows[0]["type"] == inbox.TYPE_QUESTION and rows[1]["type"] == inbox.TYPE_TASK      # 최신 먼저
    assert rt.repo.mark_notifications_read("hyd", ids, [rows[0]["id"]]) == 1
    assert rt.repo.count_unread_notifications("hyd", ids) == 1 and rt.repo.mark_notifications_read("hyd", ids) == 1
    assert rt.repo.count_unread_notifications("hyd", ids) == 0 and rt.repo.mark_notifications_read("hyd", ids) == 0
    # 역할 앞으로 온 알림은 역할 공용 받은 함 한 행이다: 한 사람이 읽으면 역할이 읽은 것. 최운전 개인 알림(내 차례)은 그대로 안 읽음.
    assert rt.repo.count_unread_notifications("hyd", inbox.user_ids_for(rt.repo, "hyd", CHOI)) == 1
    assert [n["type"] for n in rt.repo.list_notifications("hyd", [CHOI], unread_only=True)] == [inbox.TYPE_TASK]


@pytest.fixture
def client(rt, monkeypatch):
    runtime, hooks = rt
    monkeypatch.setattr(instance_mode, "_runtime", runtime)
    monkeypatch.setattr(instance_mode, "_ctx", SimpleNamespace(audit=lambda *a, **k: None))
    app = FastAPI()
    instance_mode.mount(app, "instance")
    inbox_api.mount(app)
    with TestClient(app) as c:
        yield c, runtime, hooks


def test_routes_inbox_notifications_and_403(client):
    c, rt, hooks = client
    inst = rt.on_alert_raise(ALERT)                                   # 실제 시각으로 연다: 경로의 기한 검사(실시간)가 선택 타이머를 만료로 보지 않게
    from test_instances import AGENT_OUTPUTS
    for _ in range(4):
        (wi,) = rt.repo.fetch_pending_task("cliagents", "worker-test")
        rt.repo.save_task_result(wi["id"], AGENT_OUTPUTS[wi["activity_id"]], final=True)
        assert rt.poll_once() == 1
    sel = _by(rt, inst, "task:select")
    people = c.get("/api/inbox/users").json()
    assert {p["id"] for p in people} == {KIM, CHOI, LEE, PARK} and next(p for p in people if p["id"] == KIM)["roles"] == ["role:operator"]
    assert next(p for p in people if p["id"] == LEE)["name"] == "이생산"
    box = c.get("/api/inbox", params={"user_id": CHOI}).json()
    assert box["roles"] == ["role:operator"] and [t["assignment"] for t in box["tasks"]] == ["role"] and box["unread"] == 1
    assert box["tasks"][0]["link"] == f"#/instances/{inst['proc_inst_id']}/task/{sel['id']}"
    assert c.get("/api/inbox", params={"user_id": LEE}).json()["tasks"] == []
    assert c.get("/api/inbox", params={"user_id": "user:nobody"}).status_code == 404
    assert c.get("/api/inbox", params={"user_id": "role:operator"}).status_code == 404       # 역할은 "나"가 될 수 없다
    assert c.get(f"/api/todolist/{sel['id']}/assignments").json() == []                      # 역할 공용: 자동 배정 이력 없음
    assert c.post(f"/api/todolist/{sel['id']}/assign", json={"to_user_id": KIM}).status_code in (404, 405)   # 위임·재배정은 범위 밖
    # 업무분장(읽기 전용)
    board = c.get("/api/inbox/assignments").json()
    assert next(r for r in board["roles"] if r["id"] == "role:operator")["members"] == [CHOI, KIM]
    assert c.post("/api/inbox/assignments", json={"role_id": "role:maint-mgr", "user_id": KIM, "member": True, "by": "x"}).status_code == 405
    # 알림: 목록(포털 링크) · 안 읽은 수 · 읽음. 워커의 질문 알림(url=/todolist/<id>)도 처리 건 링크로 풀린다
    rt.repo.insert_notification({"title": "현장 소음이 있나요?", "type": inbox.TYPE_QUESTION, "user_id": "role:operator", "from_user_id": "sys:agent",
                                 "url": f"/todolist/{sel['id']}"})
    rt.repo.insert_notification({"title": "지워진 작업", "type": inbox.TYPE_QUESTION, "user_id": KIM, "url": "/todolist/00000000-0000-0000-0000-000000000000"})
    notes = c.get("/api/inbox/notifications", params={"user_id": KIM, "unread": "true"}).json()
    assert [n["type"] for n in notes] == [inbox.TYPE_QUESTION, inbox.TYPE_QUESTION, inbox.TYPE_TASK]
    assert notes[1]["link"] == notes[2]["link"] == f"#/instances/{inst['proc_inst_id']}/task/{sel['id']}"
    assert notes[0]["link"] is None and notes[0]["link_error"] == "알림이 가리키는 작업을 찾지 못했습니다"
    assert c.get("/api/inbox/notifications/unread-count", params={"user_id": KIM}).json()["unread"] == 3
    assert c.post("/api/inbox/notifications/read", json={"user_id": KIM, "ids": ["not-a-uuid"]}).status_code == 400
    assert c.post("/api/inbox/notifications/read", json={"user_id": KIM, "ids": [notes[2]["id"]]}).json()["unread"] == 2
    assert c.post("/api/inbox/notifications/read", json={"user_id": CHOI, "ids": [notes[0]["id"]]}).json()["marked"] == 0   # 남의 알림은 못 읽음 처리
    assert c.post("/api/inbox/notifications/read", json={"user_id": KIM}).json() == {"user_id": KIM, "marked": 2, "unread": 0}
    assert c.get("/api/inbox/notifications", params={"user_id": "user:nobody"}).status_code == 404
    # "나"로 승인: 남의 역할을 내세우면 403, 내 역할이어도 카드의 승인 등급보다 낮으면 403 — 작업은 그대로 열려 있다
    r = c.post(f"/api/todolist/{sel['id']}/select", json={"decision": "DEC-1003-001", "option": "skill:fan-max-derate", "by": KIM, "role": "role:prod-mgr"})
    assert r.status_code == 403 and "역할이 아니어서" in r.json()["detail"], r.json()
    hooks.approve_decision = hooks._deny
    r = c.post(f"/api/todolist/{sel['id']}/select", json={"decision": "DEC-1003-001", "option": "skill:fan-max-derate", "by": KIM, "role": "role:operator"})
    assert r.status_code == 403 and "승인 권한" in r.json()["detail"], r.json()
    assert rt.repo.get_workitem(sel["id"])["status"] == "IN_PROGRESS"


def test_notification_stream_sends_only_mine(rt):
    """SSE: 처음엔 내 것(나 + 내 역할) 기록, 그 뒤 새로 생긴 내 알림만. 남의 알림은 한 줄도 보내지 않는다."""
    rt, _ = rt
    inst, sel = _select_open(rt)                                      # 김운전 · 최운전에게 알림 1건씩
    rt.repo.insert_notification({"title": "질문", "type": inbox.TYPE_QUESTION, "user_id": "role:operator", "from_user_id": "sys:agent", "url": "/todolist/x"})
    mine = inbox.user_ids_for(rt.repo, "hyd", KIM)
    fetch = lambda since, limit: rt.repo.list_notifications_since(since, limit, "hyd", mine)
    calls = {"n": 0}

    async def disconnected():
        calls["n"] += 1
        if calls["n"] == 1:                                           # 연결 뒤 새 알림: 남의 것 하나, 내 것 하나
            rt.repo.insert_notification({"title": "남의 것", "type": inbox.TYPE_TASK, "user_id": CHOI, "url": "/instances/x"})
            rt.repo.insert_notification({"title": "새 내 것", "type": inbox.TYPE_TASK, "user_id": KIM, "url": "/instances/y"})
        return calls["n"] > 2

    async def collect():
        return [f async for f in instance_mode.event_stream(rt.repo, None, disconnected, interval=0.01, fetch=fetch, ts_key="created_at")]
    frames = asyncio.run(collect())
    history = [f for f in frames if f.startswith("event: history")]
    assert len(history) == 2 and all(('"user_id": "user:kim-op"' in f) or ('"user_id": "role:operator"' in f) for f in history)
    live = [f for f in frames if not f.startswith("event: history") and "data:" in f]
    assert len(live) == 1 and "새 내 것" in live[0]
    assert not any('"user_id": "user:choi-op"' in f for f in frames)
