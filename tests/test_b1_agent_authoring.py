"""B1 (확정 TODO B · DECISIONS 110 ①): 포털에서 에이전트 · 스킬 만들기 · 고치기 · 붙이기, 단계 → 에이전트 · 역할 → 사람 배정, 되돌리기.

완료 기준(TODO B1): 새 에이전트 · 스킬이 워커 실행 설정(지시문 · 작업 폴더 스킬 · 도구 · 모델)에 반영 / 기본 에이전트 수정 거절 /
새 에이전트 · 스킬 · 배정을 만들어도 기본 에이전트의 실행 설정(agent_settings)이 한 글자도 안 바뀜 / 배정 → 실행 담당 변경 → 되돌리기 후 원복.
일부러 깨뜨림: 기본 에이전트에 몰래 스킬을 붙이면 불변 검사가 잡는다, 배정 적용을 끄면 실행 담당 시험이 잡는다(아래 각 시험의 '깨뜨림' 줄).
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import agent_authoring, agent_authoring_api, agents_api, engine, inbox, instance_mode, instances, procdb
from procsvc.agents_store import activity_capabilities, agent_settings
from test_instances import ALERT, DEF_PATH, NOW, FakeHooks, _by
from test_u2_agents_skills import FORM, MCP, SKILL_MD, _prompt_text, _run

KIM, CHOI, LEE = "user:kim-op", "user:choi-op", "user:lee-prod"
NEW_SKILL = "---\nname: cooler-check\ndescription: 쿨러 점검 순서\n---\n\n# 쿨러 점검\n\n1. 냉각 효율부터 본다.\n"
AGENT_STEPS = ["task:diagnose", "task:candidates", "task:compliance", "task:rank"]


def _seed(repo):
    """seed.sql 과 같은 모양(기본 = origin 없음 → 'seed'): 테넌트 MCP · 기본 에이전트 · 시스템 수행자 · 역할 · 사람 · 업무분장 · 랩업 스킬 하나."""
    repo.upsert_proc_def(engine.Definition.load(DEF_PATH).raw)
    repo.upsert_form(FORM)
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": MCP})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트 (Claude Code)", "role": "agent", "is_agent": True, "agent_type": "agent",
                      "goal": "경보의 원인을 진단하고 조치 카드를 올린다", "tools": "neo4j,enterprise,hyd-dmn", "tenant_id": "hyd"})
    repo.upsert_user({"id": "sys:scada", "username": "SCADA", "role": "system", "is_agent": True, "agent_type": "system", "tenant_id": "hyd"})
    for uid, name in (("role:operator", "운전원"), ("role:prod-mgr", "생산관리자"), ("role:maint-mgr", "설비보전팀장"),
                      (KIM, "김운전"), (CHOI, "최운전"), (LEE, "이생산")):
        repo.upsert_user({"id": uid, "username": name, "is_agent": False, "tenant_id": "hyd"})
    for role, uid in (("role:operator", KIM), ("role:operator", CHOI), ("role:prod-mgr", LEE)):
        repo.set_role_member("hyd", role, uid, True)
    repo.put_skill({"skill_name": "fan-vibration-check", "description": "팬 진동 점검 순서", "content": SKILL_MD})   # 랩업 SQL 로 넣은 것(origin 없음)
    # B2 게이트(합친 뒤): 학생 서버 fan-vib 는 연결 검사를 통과한 기록이 있어야 에이전트 도구로 붙는다
    from procsvc import mcp_registry
    entry = mcp_registry.store_for(repo).servers("hyd")["fan-vib"]
    mcp_registry.store_for(repo).save_check("hyd", "fan-vib", {"status": "ok", "fingerprint": mcp_registry.fingerprint(entry), "checked_at": "2026-10-08T00:00:00Z",
                                                               "tools": [{"name": "vibration", "read_only": True}]}, "시험")


@pytest.fixture
def env(monkeypatch):
    repo = procdb.MemoryRepo()
    _seed(repo)
    rt = instances.InstanceRuntime(repo, engine.Definition.load(DEF_PATH), FakeHooks(), time_scale=20.0)
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    agents_api.mount(app)
    agent_authoring_api.mount(app)
    return TestClient(app), rt


def _default_settings(rt) -> str:
    """기본 에이전트의 실행 설정 전부(단계 선언 없음 + 에이전트 단계 4개 각각) — 한 글자 비교용 JSON."""
    defn = rt.defn.raw
    out = {"base": agent_settings(rt.repo, "hyd", "sys:agent")}
    out.update({a: agent_settings(rt.repo, "hyd", "sys:agent", activity=activity_capabilities(defn, a)) for a in AGENT_STEPS})
    return json.dumps({k: {"summary": v.summary(), "instructions": v.instructions(), "codex": v.instructions(".agents/skills"),
                           "profile": v.profile} for k, v in out.items()}, ensure_ascii=False, sort_keys=True)


def _new_agent(client, **over):
    body = {"name": "쿨러 점검 에이전트", "role": "쿨러 열화를 먼저 본다", "goal": "쿨러 원인 근거를 모은다", "persona": "짧게 근거부터",
            "model": "claude-haiku-4-5", "tools": ["enterprise", "fan-vib"], "skills": []}
    r = client.post("/api/agents", json={**body, **over})
    assert r.status_code == 201, r.text
    return r.json()


def _new_skill(client, name="cooler-check", content=NEW_SKILL, **over):
    r = client.post("/api/skills", json={"skill_name": name, "description": "", "content": content, **over})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- 기본 보호
def test_default_agent_edit_and_delete_are_refused_with_a_reason_clone_is_allowed(env):
    client, rt = env
    before = _default_settings(rt)
    for method, url, body in (("PUT", "/api/agents/sys:agent", {"name": "바꿈", "goal": "바꿈"}), ("DELETE", "/api/agents/sys:agent", None),
                              ("POST", "/api/agents/sys:agent/skills", {"skill_name": "fan-vibration-check"}),
                              ("DELETE", "/api/agents/sys:agent/skills/fan-vibration-check", None),
                              ("PUT", "/api/agents/sys:scada", {"name": "x", "goal": "y"}), ("DELETE", "/api/agents/sys:scada", None)):
        r = client.request(method, url, json=body)
        assert r.status_code == 403, (method, url, r.text)
        assert "보호" in r.json()["detail"]
    assert "복제해서 고치기" in client.put("/api/agents/sys:agent", json={"name": "a", "goal": "b"}).json()["detail"]
    # 랩업 SQL 로 넣은 스킬(origin 없음)도 기본으로 보호된다
    assert client.put("/api/skills/fan-vibration-check", json={"content": NEW_SKILL.replace("cooler-check", "fan-vibration-check")}).status_code == 403
    assert client.delete("/api/skills/fan-vibration-check").status_code == 403
    # 복제: 같은 설정의 사본(origin=user), 이름은 겹치지 않게
    copy = client.post("/api/agents/sys:agent/clone", json={}).json()
    assert copy["origin"] == "user" and copy["id"].startswith("agent:u-") and copy["username"] == "AI 에이전트 (Claude Code) 사본"
    again = client.post("/api/agents/sys:agent/clone").json()
    assert again["username"] == "AI 에이전트 (Claude Code) 사본 2"
    a, b = agent_settings(rt.repo, "hyd", "sys:agent"), agent_settings(rt.repo, "hyd", copy["id"])
    assert (a.model, a.tools, a.skill_names) == (b.model, b.tools, b.skill_names) and b.profile["goal"] == a.profile["goal"]
    assert client.post("/api/agents/sys:scada/clone").status_code == 403          # 시스템 수행자는 에이전트 설정이 없다
    cards = {c["id"]: c for c in client.get("/api/agents").json()}
    assert cards["sys:agent"]["origin"] == "seed" and not cards["sys:agent"]["editable"]
    assert cards[copy["id"]]["origin"] == "user" and cards[copy["id"]]["editable"]
    assert _default_settings(rt) == before


# ---------------------------------------------------------------- 불변: 기본 에이전트의 실행 설정
def test_creating_agents_skills_and_assignments_leaves_the_default_run_settings_unchanged(env):
    client, rt = env
    before = _default_settings(rt)
    api_before = client.get("/api/agents/sys:agent").json()["run"]
    skill = _new_skill(client)
    agent = _new_agent(client, skills=["cooler-check", "fan-vibration-check"])
    client.post(f"/api/agents/{agent['id']}/clone", json={"name": "두 번째"})
    client.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:diagnose", "agent_id": agent["id"]})
    client.post("/api/role-members", json={"role_id": "role:prod-mgr", "user_id": KIM})
    client.put(f"/api/agents/{agent['id']}", json={"name": "쿨러 점검 에이전트", "goal": "바꾼 목표", "tools": ["neo4j"], "skills": [skill["skill_name"]]})
    assert _default_settings(rt) == before                                       # 한 글자도 안 바뀜
    api_after = client.get("/api/agents/sys:agent").json()["run"]
    assert (api_after["instructions"], api_after["settings"]) == (api_before["instructions"], api_before["settings"])
    # 깨뜨림: 버그로 기본 에이전트에 스킬이 붙으면(보호를 우회한 저장소 직접 쓰기) 같은 비교가 잡는다
    rt.repo.attach_skill("sys:agent", "cooler-check")
    assert _default_settings(rt) != before


# ---------------------------------------------------------------- 에이전트 · 스킬 입력 검사
def test_agent_and_skill_inputs_are_refused_with_reasons(env):
    client, _ = env
    bad = [({"name": "", "goal": "x"}, 422, "이름"), ({"name": "a", "goal": ""}, 422, "목표"),
           ({"name": "a", "goal": "b", "tools": ["ghost"]}, 422, "등록되지 않은 도구 서버"),
           ({"name": "a", "goal": "b", "skills": ["nope"]}, 422, "없는 스킬"),
           ({"name": "a", "goal": "b", "model": "모델 이름"}, 422, "모델"),
           ({"name": "ai 에이전트 (claude code)", "goal": "b"}, 409, "같은 이름")]
    for body, status, word in bad:
        r = client.post("/api/agents", json=body)
        assert r.status_code == status and word in r.json()["detail"], (body, r.text)
    for body, status, word in (({"skill_name": "x-y", "content": "---\nname: x-y\ndescription: d\n---\n\n  \n"}, 422, "빈 스킬"),
                               ({"skill_name": "x-y", "content": ""}, 422, "빈 스킬"),
                               ({"skill_name": "Fan Check", "content": "# a\nb"}, 422, "소문자"),
                               ({"skill_name": "", "content": "# a\nb"}, 422, "폴더 이름"),
                               ({"skill_name": "x-y", "content": NEW_SKILL}, 422, "다릅니다"),
                               ({"skill_name": "x-y", "content": "본문만 있고 제목도 설명도 없음"}, 422, "설명"),
                               ({"skill_name": "fan-vibration-check", "content": "# a\nb"}, 409, "이미")):
        r = client.post("/api/skills", json=body)
        assert r.status_code == status and word in r.json()["detail"], (body, r.text)
    made = _new_skill(client, "bare-body", "# 맨 본문\n절차 하나")
    assert made["description"] == "맨 본문" and made["origin"] == "user"
    assert _new_skill(client, "x-y", "# 제목\n본문", description="한 줄 설명")["description"] == "한 줄 설명"


def test_skill_edit_attach_detach_delete_on_my_agent(env):
    client, rt = env
    agent = _new_agent(client)
    _new_skill(client)
    assert client.post(f"/api/agents/{agent['id']}/skills", json={"skill_name": "cooler-check"}).json()["skills"] == ["cooler-check"]
    assert client.post(f"/api/agents/{agent['id']}/skills", json={"skill_name": "cooler-check"}).status_code == 409
    assert client.post(f"/api/agents/{agent['id']}/skills", json={"skill_name": "fan-vibration-check"}).status_code == 200   # 기본 스킬을 내 에이전트에 붙이기는 됨
    r = client.put("/api/skills/cooler-check", json={"content": NEW_SKILL.replace("냉각 효율부터", "온도차부터")})
    assert r.status_code == 200 and "온도차부터" in r.json()["content"]
    assert "온도차부터" in agent_settings(rt.repo, "hyd", agent["id"]).skills[0]["content"]       # 다음 실행이 읽는 같은 행
    assert client.put("/api/skills/cooler-check", json={"content": "---\nname: cooler-check\n---\n"}).status_code == 422
    assert client.delete(f"/api/agents/{agent['id']}/skills/cooler-check").json()["skills"] == ["fan-vibration-check"]
    assert client.delete(f"/api/agents/{agent['id']}/skills/cooler-check").status_code == 404
    client.post(f"/api/agents/{agent['id']}/skills", json={"skill_name": "cooler-check"})
    gone = client.delete("/api/skills/cooler-check").json()
    assert gone["detached_from"] == [agent["id"]] and agent_settings(rt.repo, "hyd", agent["id"]).skill_names == ["fan-vibration-check"]
    assert client.get("/api/skills/cooler-check").status_code == 404
    opts = client.get("/api/agent-authoring/options").json()
    assert [s["name"] for s in opts["servers"]] == list(MCP["mcpServers"]) and opts["servers"][3]["description"] == "팬 진동 조회"
    assert {s["skill_name"]: s["origin"] for s in opts["skills"]} == {"fan-vibration-check": "seed"} and opts["models"] == ["claude-haiku-4-5"]


def test_mcp_check_status_is_shown_when_the_store_has_one(env):
    _, rt = env
    rt.repo.mcp_check_status = lambda tenant: {"neo4j": {"ok": True, "checked_at": "2026-10-08T12:00:00Z"}}
    opts = agent_authoring.server_options(rt.repo, "hyd")
    assert opts[0]["check"]["ok"] is True and opts[1]["check"] is None


# ---------------------------------------------------------------- 새 에이전트 · 스킬 → 워커 실제 실행
def test_a_step_assigned_to_my_agent_runs_with_its_profile_skill_model_and_tools(env, tmp_path):
    client, rt = env
    _new_skill(client)
    agent = _new_agent(client, skills=["cooler-check"])
    r = client.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:diagnose", "agent_id": agent["id"], "by": KIM})
    assert r.status_code == 200, r.text
    inst = rt.on_alert_raise(ALERT, now=NOW)
    row = _by(rt, inst, "task:diagnose")
    assert row["user_id"] == agent["id"] and row["username"] == "쿨러 점검 에이전트"            # 깨뜨림: apply_agent_map 을 빼면 sys:agent 로 남아 실패
    hist = rt.repo.list_assignments(row["id"], "hyd")
    assert [(h["kind"], h["from_user_id"], h["to_user_id"], h["by_user"]) for h in hist] == [("agent_map", "sys:agent", agent["id"], KIM)]
    assert engine.Definition.load(DEF_PATH).raw == rt.repo.get_proc_def("anomaly_response", "hyd", version=rt.defn.raw["version"])["definition"]  # 정의 원본은 그대로
    request, ws, ran = _run(tmp_path, rt.repo)
    assert ran["id"] == row["id"] and request.model == "claude-haiku-4-5"
    text = _prompt_text(request, ws)
    assert "쿨러 점검 에이전트" in text and "쿨러 원인 근거를 모은다" in text and "짧게 근거부터" in text
    assert (ws.path / ".claude" / "skills" / "cooler-check" / "SKILL.md").read_text(encoding="utf-8") == NEW_SKILL
    assert sorted(json.loads((ws.path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]) == ["enterprise", "fan-vib"]
    task = json.loads((ws.context_dir / "task.json").read_text(encoding="utf-8"))
    assert task["agent"]["id"] == agent["id"] and task["agent"]["skills"] == ["cooler-check"]
    # 포털: 내 에이전트가 그 단계를 맡고, 기본 에이전트 목록에서는 빠진다
    mine = client.get(f"/api/agents/{agent['id']}").json()
    assert [s["activity_id"] for s in mine["steps"]] == ["task:diagnose"] and mine["steps"][0]["assigned"]
    assert [s["name"] for s in mine["run"]["steps"]] == [row["activity_name"]]
    default = client.get("/api/agents/sys:agent").json()
    assert [s["activity_id"] for s in default["steps"] if s["agent"]] == AGENT_STEPS[1:]


def test_unassigned_steps_keep_the_default_agent(env, tmp_path):
    client, rt = env
    _new_agent(client)                                       # 만들기만 하고 배정하지 않음
    inst = rt.on_alert_raise(ALERT, now=NOW)
    row = _by(rt, inst, "task:diagnose")
    assert row["user_id"] == "sys:agent" and rt.repo.list_assignments(row["id"], "hyd") == []
    request, ws, _ = _run(tmp_path, rt.repo)
    assert "AI 에이전트 (Claude Code)" in _prompt_text(request, ws) and request.model is None


def test_assignment_inputs_are_checked(env):
    client, _ = env
    agent = _new_agent(client)
    put = lambda **b: client.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:diagnose", "agent_id": agent["id"], **b})
    assert put(activity_id="task:select").status_code == 404                      # 사람 단계
    assert put(activity_id="task:command").status_code == 404                     # 시스템 단계
    assert put(agent_id="sys:scada").status_code == 422
    assert put(agent_id="agent:none").status_code == 404
    assert "기본 담당" in put(agent_id="sys:agent").json()["detail"]
    assert client.delete("/api/agent-assignments/anomaly_response/task:diagnose").status_code == 404
    board = client.get("/api/agent-assignments").json()
    assert [s["activity_id"] for s in board["steps"]] == AGENT_STEPS and all(s["assigned"] is None for s in board["steps"])
    assert board["steps"][0]["default_names"] == ["AI 에이전트 (Claude Code)"]
    client.post("/api/role-members", json={"role_id": "role:prod-mgr", "user_id": KIM})
    roles = {r["id"]: r for r in client.get("/api/agent-assignments").json()["roles"]}
    assert roles["role:prod-mgr"]["members"] == [{"id": LEE, "name": "이생산", "origin": "seed"}, {"id": KIM, "name": "김운전", "origin": "user"}]
    assert {a["id"] for a in board["agents"]} == {"sys:agent", agent["id"]}           # 시스템 수행자는 고를 수 없다


# ---------------------------------------------------------------- 배정 → 실행 담당 변경 → 지우기 · 되돌리기 후 원복
def test_mapping_changes_the_performer_and_clearing_or_reset_restores_the_default(env):
    client, rt = env
    agent = _new_agent(client)
    key = {"definition_id": "anomaly_response", "activity_id": "task:candidates"}
    client.put("/api/agent-assignments", json={**key, "agent_id": agent["id"]})
    first = rt.on_alert_raise(dict(ALERT, alertId="A-1"), now=NOW)
    assert _by(rt, first, "task:diagnose")["user_id"] == "sys:agent"             # 배정하지 않은 단계는 기본
    # 지우기 → 다음에 열리는 단계부터 기본
    assert client.delete("/api/agent-assignments/anomaly_response/task:candidates").json()["agent_id"] is None
    client.put("/api/agent-assignments", json={**key, "agent_id": agent["id"]})
    # 첫 처리 건의 진단을 끝내 후보 단계가 배정 에이전트에게 열리게 한다
    from test_instances import AGENT_OUTPUTS
    (wi,) = rt.repo.fetch_pending_task("cliagents", "w", proc_inst_id=first["proc_inst_id"])
    rt.repo.save_task_result(wi["id"], AGENT_OUTPUTS[wi["activity_id"]], final=True)
    rt.poll_once(now=NOW)
    cand = _by(rt, first, "task:candidates")
    assert cand["status"] == "IN_PROGRESS" and cand["user_id"] == agent["id"]
    # 되돌리기: 열린(아직 안 집힌) 단계는 기본 담당으로, 내가 만든 것만 지움
    out = client.post("/api/agents/reset", json={"by": KIM}).json()
    assert out["agents"] == 1 and out["assignments"] == 1
    assert [t["todo_id"] for t in out["returned_tasks"]] == [cand["id"]]
    assert rt.repo.get_workitem(cand["id"])["user_id"] == "sys:agent"
    assert rt.repo.list_assignments(cand["id"], "hyd")[-1]["kind"] == "agent_map"
    second = rt.on_alert_raise(dict(ALERT, alertId="A-2"), now=NOW)
    (wi,) = rt.repo.fetch_pending_task("cliagents", "w2", proc_inst_id=second["proc_inst_id"])
    rt.repo.save_task_result(wi["id"], AGENT_OUTPUTS[wi["activity_id"]], final=True)
    rt.poll_once(now=NOW)
    assert _by(rt, second, "task:candidates")["user_id"] == "sys:agent"
    assert client.get("/api/agent-assignments").json()["steps"][1]["assigned"] is None


def test_delete_refuses_while_running_and_returns_open_steps(env):
    client, rt = env
    agent = _new_agent(client)
    client.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:diagnose", "agent_id": agent["id"]})
    inst = rt.on_alert_raise(ALERT, now=NOW)
    (wi,) = rt.repo.fetch_pending_task("cliagents", "w", proc_inst_id=inst["proc_inst_id"])     # 워커가 집음(STARTED)
    for url in (f"/api/agents/{agent['id']}", None):
        r = client.delete(url) if url else client.post("/api/agents/reset")
        assert r.status_code == 409 and "실행 중" in r.json()["detail"]
    assert rt.repo.list_users([agent["id"]], "hyd")                                  # 아무것도 지우지 않았다
    rt.repo.release_worker_claim(wi["id"], "w")
    rt.repo.set_draft_status(wi["id"], None)
    out = client.delete(f"/api/agents/{agent['id']}").json()
    assert out["returned_tasks"][0]["to"] == "sys:agent" and out["removed_assignments"] == [{"definition_id": "anomaly_response", "activity_id": "task:diagnose"}]
    assert rt.repo.get_workitem(wi["id"])["user_id"] == "sys:agent" and rt.repo.list_agent_map("hyd") == []


# ---------------------------------------------------------------- 역할 → 사람
def test_role_members_add_remove_and_seed_protection(env):
    client, rt = env
    assert inbox.resolve(rt.repo, "hyd", "role:prod-mgr")["kind"] == "person"         # 한 명 → 그 사람
    assert client.post("/api/role-members", json={"role_id": "role:prod-mgr", "user_id": KIM}).status_code == 201
    assert inbox.resolve(rt.repo, "hyd", "role:prod-mgr")["kind"] == "role"           # 두 명 → 역할 공용
    assert client.post("/api/role-members", json={"role_id": "role:prod-mgr", "user_id": KIM}).status_code == 409
    assert client.post("/api/role-members", json={"role_id": "role:nobody", "user_id": KIM}).status_code == 404
    assert client.post("/api/role-members", json={"role_id": "role:prod-mgr", "user_id": "sys:agent"}).status_code == 404
    r = client.delete("/api/role-members", params={"role_id": "role:prod-mgr", "user_id": LEE})
    assert r.status_code == 403 and "기본 업무분장" in r.json()["detail"]
    assert client.delete("/api/role-members", params={"role_id": "role:prod-mgr", "user_id": KIM}).json()["members"] == [LEE]
    client.post("/api/role-members", json={"role_id": "role:maint-mgr", "user_id": CHOI})
    assert client.post("/api/agents/reset").json()["role_members"] == 1
    assert inbox.members_of(rt.repo, "hyd", "role:maint-mgr") == [] and inbox.members_of(rt.repo, "hyd", "role:operator") == [CHOI, KIM]


def test_reset_removes_only_what_the_portal_made(env):
    client, rt = env
    seed_users = sorted(u["id"] for u in rt.repo.list_users(None, "hyd"))
    seed_skills = [s["skill_name"] for s in rt.repo.list_skills("hyd")]
    before = _default_settings(rt)
    _new_skill(client)
    a = _new_agent(client, skills=["cooler-check", "fan-vibration-check"])
    client.post(f"/api/agents/{a['id']}/clone")
    client.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:rank", "agent_id": a["id"]})
    client.post("/api/role-members", json={"role_id": "role:prod-mgr", "user_id": KIM})
    out = client.post("/api/agents/reset").json()
    assert (out["agents"], out["skills"], out["assignments"], out["role_members"]) == (2, 1, 1, 1) and out["attachments"] == 4
    assert sorted(u["id"] for u in rt.repo.list_users(None, "hyd")) == seed_users
    assert [s["skill_name"] for s in rt.repo.list_skills("hyd")] == seed_skills and rt.repo.list_agent_skills("hyd") == []
    assert _default_settings(rt) == before
    again = client.post("/api/agents/reset").json()                                   # 두 번 눌러도 기본은 그대로
    assert (again["agents"], again["skills"], again["assignments"], again["role_members"]) == (0, 0, 0, 0)


def test_writes_say_why_in_legacy_mode(monkeypatch):
    monkeypatch.setattr(instance_mode, "_runtime", None)
    app = FastAPI()
    agent_authoring_api.mount(app)
    c = TestClient(app)
    assert c.post("/api/agents", json={"name": "a", "goal": "b"}).status_code == 409 and c.post("/api/agents/reset").status_code == 409


# ---------------------------------------------------------------- PostgreSQL (migration 000041 + seed 를 적용한 빈 DB가 있을 때)
PG_DSN = __import__("os").getenv("HYD_B1_PG_DSN")


@pytest.mark.skipif(not PG_DSN, reason="HYD_B1_PG_DSN 이 없으면 PostgreSQL 검사는 건너뛴다 (마이그레이션 전부 + seed.sql 을 적용한 버릴 DB)")
def test_pg_store_protects_seed_rows_applies_the_map_and_resets(monkeypatch, tmp_path):
    from procsvc.procdb import PgRepo
    repo = PgRepo(PG_DSN)
    defn = engine.Definition.load(DEF_PATH)
    repo.upsert_proc_def(defn.raw)
    with repo._conn() as c:
        c.execute("update tenants set mcp = %s where id = 'hyd'", (json.dumps(MCP),))
    rt = instances.InstanceRuntime(repo, defn, FakeHooks(), time_scale=20.0)
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    agents_api.mount(app)
    agent_authoring_api.mount(app)
    client = TestClient(app)
    client.post("/api/agents/reset")
    before = _default_settings(rt)
    seed_users = sorted(u["id"] for u in repo.list_users(None, "hyd"))
    assert client.put("/api/agents/sys:agent", json={"name": "a", "goal": "b"}).status_code == 403
    _new_skill(client)
    agent = _new_agent(client, skills=["cooler-check"])
    assert client.post("/api/skills", json={"skill_name": "cooler-check", "content": NEW_SKILL}).status_code == 409
    client.put(f"/api/agents/{agent['id']}", json={"name": "쿨러 점검 에이전트", "goal": "고친 목표", "model": "claude-haiku-4-5", "tools": ["enterprise"],
                                                    "skills": ["cooler-check"]})
    assert agent_settings(repo, "hyd", agent["id"]).profile["goal"] == "고친 목표"
    client.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:diagnose", "agent_id": agent["id"]})
    client.post("/api/role-members", json={"role_id": "role:prod-mgr", "user_id": KIM})
    assert client.delete("/api/role-members", params={"role_id": "role:prod-mgr", "user_id": "user:lee-prod"}).status_code == 403
    assert _default_settings(rt) == before
    tag, made = __import__('uuid').uuid4().hex[:8], []
    try:
        _pg_runs(client, repo, rt, agent, tag, made, tmp_path, before, seed_users)
    finally:
        with repo._conn() as c:                                      # 시험 처리 건 정리(실패해도)
            c.execute("delete from bpm_proc_inst where proc_inst_id = any(%s)", (made,))
        client.post("/api/agents/reset")


def _pg_runs(client, repo, rt, agent, tag, made, tmp_path, before, seed_users):
    ran_inst = rt.on_alert_raise(dict(ALERT, alertId=f"B1-PG-{tag}-1"), now=NOW)
    made.append(ran_inst["proc_inst_id"])
    request, ws, ran = _run(tmp_path, repo)                           # 실제 워커 경로(PgRepo claim → 프로필 · 스킬 · 도구)
    assert ran["user_id"] == agent["id"] and ran["proc_inst_id"] == ran_inst["proc_inst_id"]
    assert request.model == "claude-haiku-4-5" and (ws.path / ".claude" / "skills" / "cooler-check" / "SKILL.md").exists()
    assert sorted(json.loads((ws.path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]) == ["enterprise"]
    inst = rt.on_alert_raise(dict(ALERT, alertId=f"B1-PG-{tag}-2"), now=NOW)
    made.append(inst["proc_inst_id"])
    row = _by(rt, inst, "task:diagnose")
    assert row["user_id"] == agent["id"]
    assert [h["kind"] for h in repo.list_assignments(row["id"], "hyd")] == ["agent_map"]
    out = client.post("/api/agents/reset").json()
    assert (out["agents"], out["skills"], out["assignments"], out["role_members"]) == (1, 1, 1, 1)
    assert [t["todo_id"] for t in out["returned_tasks"]] == [row["id"]] and repo.get_workitem(row["id"])["user_id"] == "sys:agent"
    assert sorted(u["id"] for u in repo.list_users(None, "hyd")) == seed_users and _default_settings(rt) == before


def test_agent_tools_must_be_checked_student_servers_or_base_servers(env):
    """B1 × B2 게이트: 검사 기록 없는 학생 서버는 거절(사유), 기준 서버는 검사 없이 붙는다. 검사 기록을 지우면 다시 거절."""
    client, rt = env
    from procsvc import mcp_registry
    st = mcp_registry.store_for(rt.repo)
    st.delete_checks("hyd", ["fan-vib"])
    body = {"name": "게이트 시험", "goal": "팬 진동을 본다", "tools": ["fan-vib"], "skills": []}
    r = client.post("/api/agents", json=body)
    assert r.status_code == 422 and "fan-vib" in r.text and "연결 검사" in r.text, r.text
    r = client.post("/api/agents", json=dict(body, tools=["neo4j", "enterprise"]))
    assert r.status_code == 201, r.text

