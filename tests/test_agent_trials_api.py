"""A10 에이전트 시험 실행 · 비교 — process 서비스 쪽(it/process/procsvc/agent_trials.py).

에이전트 설정은 users(is_agent)·스킬 저장소에서 읽기만, 시험은 처리 건 · 작업 · 판단 · 명령을 만들지 않음, 같은 스냅숏 재사용 → 같은 결과,
설정 차이(도구 빼 보기 · 스킬) → 비교 결과에 차이 표시. agent 서비스 호출 자리에는 진짜 trial.run_trial + 가짜 원천을 꽂는다.
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentsvc import trial as T
from procsvc import agent_trials as AT
from procsvc.procdb import MemoryRepo
from test_agent_trial import FakeWorld, FAN_SKILL

MCP = {"mcpServers": {"neo4j": {}, "enterprise": {}, "hyd-dmn": {}}}


class SkillRepo(MemoryRepo):
    """MemoryRepo + the A2/U2 skill store reader (list_skills) the trials read through when it exists."""

    def __init__(self, skills):
        super().__init__()
        self._skill_store = skills

    def list_skills(self, tenant_id="hyd", names=None):
        return [dict(skill_name=k, **v) for k, v in self._skill_store.items() if names is None or k in names]


def make_repo(with_store=True):
    repo = SkillRepo({"fan-check": {"description": FAN_SKILL["description"], "content": FAN_SKILL["content"]}}) if with_store else MemoryRepo()
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": MCP})
    for u in [
        {"id": "sys:agent", "username": "AI 에이전트 (Claude Code)", "is_agent": True, "agent_type": "agent", "tools": "neo4j,enterprise,hyd-dmn", "tenant_id": "hyd"},
        {"id": "agent:fan", "username": "팬 점검 에이전트", "is_agent": True, "agent_type": "agent", "tools": "hyd-dmn,enterprise", "skills": "fan-check", "tenant_id": "hyd"},
        {"id": "sys:scada", "username": "SCADA", "is_agent": True, "agent_type": "system", "tenant_id": "hyd"},
        {"id": "role:operator", "username": "운전원", "is_agent": False, "tenant_id": "hyd"},
    ]:
        repo.upsert_user(u)
    return repo


@pytest.fixture
def env():
    repo, world = make_repo(), FakeWorld()

    def evaluate(scenario, agent, entries, servers):
        snap = T.Snapshot(entries)
        out = T.run_trial(scenario, agent, world, snap, servers)
        return {"trial": out, "added": snap.added}
    app = FastAPI()
    rt = SimpleNamespace(repo=repo, tenant_id="hyd")
    AT.register(app, runtime_factory=lambda: rt, evaluate=evaluate)
    return SimpleNamespace(client=TestClient(app), repo=repo, world=world)


def test_agent_settings_are_read_from_users_and_the_skill_store():
    p = AT.agent_profiles(make_repo(), "hyd")
    assert [a["id"] for a in p["agents"]] == ["agent:fan", "sys:agent"]          # systems and people are not agents
    fan = p["agents"][0]
    assert fan["tools"] == ["hyd-dmn", "enterprise"] and fan["skills"][0]["name"] == "fan-check" and "precedents" in fan["skills"][0]["content"]
    assert p["tenant_servers"] == ["enterprise", "hyd-dmn", "neo4j"] and p["skill_store"] is None


def test_missing_skill_store_is_a_reason_on_the_skill_not_a_silent_drop():
    p = AT.agent_profiles(make_repo(with_store=False), "hyd")
    fan = next(a for a in p["agents"] if a["id"] == "agent:fan")
    # after U2 merged, every repo has the skill store (list_skills); a skill with no body is still a stated reason, never a silent drop
    assert [(s["name"], s["content"]) for s in fan["skills"]] == [("fan-check", "")]
    assert fan["skills"][0]["missing"] in ("스킬 저장소(tenant_skills)를 읽을 수 없는 저장소입니다", "스킬 저장소에 이 이름의 스킬 본문이 없습니다")


def test_compare_runs_both_on_one_snapshot_and_creates_no_instance_task_or_decision(env):
    r = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "sys:agent"},
                                                       "b": {"agent": "sys:agent", "variant": {"without_tools": ["enterprise"]}}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["a"]["snapshot_id"] == body["b"]["snapshot_id"] == body["snapshot"]["id"] and body["snapshot"]["reused"] is False
    d = body["diff"]
    assert d["same_input"] is True and d["same_result"] is False
    assert d["recommended"]["a"] == "skill:mix" and d["recommended"]["b"] == "skill:fan" and d["recommended"]["same"] is False
    assert {f["variable"] for f in d["facts"]} == {"order_due_h", "order_penalty_per_h", "order_customer_tier"}
    assert body["b"]["variant"] == {"without_tools": ["enterprise"], "without_skills": []}
    assert body["b"]["setting"]["tools"] == ["neo4j", "hyd-dmn"]
    # the live sources were read once for both agents (B replayed A's input)
    assert [r[0] for r in env.world.reads] == ["diagnose", "gather_facts", "engine"]
    # 원본은 그대로: no process instance, work item, event, notification; the stored agent setting is unchanged
    assert env.repo.instances == {} and env.repo.workitems == {} and env.repo.events == [] and env.repo.notifications == []
    assert env.repo.users["sys:agent"]["tools"] == "neo4j,enterprise,hyd-dmn"


def test_skill_difference_shows_up_as_call_order_and_citation_difference_E3(env):
    r = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "agent:fan", "variant": {"without_skills": ["fan-check"]}},
                                                       "b": {"agent": "agent:fan"}}).json()
    d = r["diff"]
    assert d["order_same"] is False and d["calls_only_a"] == 0 and d["calls_only_b"] == 2
    only_b = [row for row in d["calls"] if row["a"] is None]
    assert [r["b"]["result"]["calls"][row["b"]]["tool"] for row in only_b] == ["precedents", "timeseries_query"]
    assert "도구:hyd-dmn/timeseries_query" in d["citations"]["only_b"]
    assert d["recommended"]["same"] is True                     # 스킬은 조회 순서·인용을 바꾸고, 같은 엔진 입력이면 1순위는 그대로


def test_same_snapshot_and_same_setting_reproduce_the_same_result(env):
    first = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "agent:fan"}}).json()
    reads = len(env.world.reads)
    again = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "agent:fan"},
                                                           "snapshot": first["snapshot"]["id"]}).json()
    assert again["snapshot"]["reused"] is True and len(env.world.reads) == reads
    assert again["a"]["fingerprint"] == first["a"]["fingerprint"] and again["a"]["id"] != first["a"]["id"]
    latest = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "agent:fan"}, "reuse_latest": True}).json()
    assert latest["snapshot"]["id"] == first["snapshot"]["id"] and latest["a"]["fingerprint"] == first["a"]["fingerprint"]
    # stored trials are listed and can be compared later (전·후)
    listed = env.client.get("/api/agent-trials?asset=HYD-01").json()
    assert {t["id"] for t in listed} >= {first["a"]["id"], again["a"]["id"]} and listed[0]["recommended"] == "SOP-2"
    diff = env.client.get(f"/api/agent-trials/diff?a={first['a']['id']}&b={again['a']['id']}").json()["diff"]
    assert diff["same_input"] and diff["same_result"] and diff["order_same"] and diff["facts"] == []


def test_different_snapshots_are_flagged_as_different_input(env):
    a = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "sys:agent"}}).json()["a"]
    b = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "sys:agent"}}).json()["a"]
    d = env.client.get(f"/api/agent-trials/diff?a={a['id']}&b={b['id']}").json()["diff"]
    assert d["same_input"] is False and d["same_result"] is True        # 입력이 다르면 그 사실을 따로 표시한다


@pytest.mark.parametrize("body,code,needle", [
    ({"scenario": "boiler", "a": {"agent": "sys:agent"}}, 400, "고정 시나리오"),
    ({"scenario": "cooler"}, 400, "에이전트"),
    ({"scenario": "cooler", "a": {"agent": "agent:nobody"}}, 404, "에이전트를 찾을 수 없습니다"),
    ({"scenario": "cooler", "a": {"agent": "sys:agent", "variant": {"without_tools": ["slack"]}}}, 400, "slack"),
    ({"scenario": "cooler", "a": {"agent": "sys:agent"}, "snapshot": "SNAP-none"}, 404, "스냅숏"),
])
def test_bad_requests_are_refused_with_readable_reasons(env, body, code, needle):
    r = env.client.post("/api/agent-trials/run", json=body)
    assert r.status_code == code and needle in r.json()["detail"]


def test_snapshot_of_another_scenario_is_refused(env):
    snap = env.client.post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "sys:agent"}}).json()["snapshot"]["id"]
    r = env.client.post("/api/agent-trials/run", json={"scenario": "fan", "a": {"agent": "sys:agent"}, "snapshot": snap})
    assert r.status_code == 400 and "시나리오" in r.json()["detail"]


def test_options_and_unavailable_runtime():
    app = FastAPI()
    AT.register(app, runtime_factory=lambda: None, evaluate=lambda *a: pytest.fail("evaluated without runtime"))
    r = TestClient(app).get("/api/agent-trials/options")
    assert r.status_code == 503 and "instance" in r.json()["detail"]
    app2 = FastAPI()
    AT.register(app2, runtime_factory=lambda: SimpleNamespace(repo=make_repo(), tenant_id="hyd"))
    opts = TestClient(app2).get("/api/agent-trials/options").json()
    assert [s["key"] for s in opts["scenarios"]] == ["cooler", "pump", "fan"]
    assert [s["asset"] for s in opts["scenarios"]] == ["HYD-01", "HYD-02", "HYD-03"]


def test_agent_service_down_is_a_readable_503(monkeypatch):
    monkeypatch.setenv("AGENT_URL", "http://127.0.0.1:9")
    app = FastAPI()
    AT.register(app, runtime_factory=lambda: SimpleNamespace(repo=make_repo(), tenant_id="hyd"))
    r = TestClient(app).post("/api/agent-trials/run", json={"scenario": "cooler", "a": {"agent": "sys:agent"}})
    assert r.status_code == 503 and "판단 서비스" in r.json()["detail"]


def test_align_marks_inserted_calls():
    a = [{"server": "s", "tool": "x", "args": {}}, {"server": "s", "tool": "z", "args": {}}]
    b = [{"server": "s", "tool": "x", "args": {}}, {"server": "s", "tool": "y", "args": {}}, {"server": "s", "tool": "z", "args": {}}]
    assert AT.align(a, b) == [{"a": 0, "b": 0, "same": True}, {"a": None, "b": 1, "same": False}, {"a": 1, "b": 2, "same": True}]


def test_process_main_registers_the_trial_routes():
    from procsvc import main
    paths = {r.path for r in main.app.routes}
    assert {"/api/agent-trials/run", "/api/agent-trials/options", "/api/agent-trials/diff", "/api/agent-trials/{trial_id}"} <= paths


PG_DSN = __import__("os").getenv("HYD_TRIAL_PG_DSN")


@pytest.mark.skipif(not PG_DSN, reason="HYD_TRIAL_PG_DSN 이 없으면 Supabase 표 검사는 건너뛴다 (migration 000001 + 000040 적용된 빈 DB)")
def test_pg_store_round_trip_and_first_read_wins():
    from procsvc.procdb import PgRepo
    repo = PgRepo(PG_DSN)
    with repo._conn() as c:
        c.execute("insert into tenants (id, name, mcp) values ('hyd', 'hyd', %s) on conflict (id) do update set mcp = excluded.mcp",
                  (__import__("json").dumps(MCP),))
        c.execute("insert into users (id, username, is_agent, agent_type, tools, tenant_id) values "
                  "('sys:agent', 'AI 에이전트', true, 'agent', 'neo4j,enterprise,hyd-dmn', 'hyd') on conflict (id) do nothing")
        before = c.execute("select (select count(*) from bpm_proc_inst) + (select count(*) from todolist) + (select count(*) from events) as n").fetchone()["n"]
    world = FakeWorld()

    def evaluate(scenario, agent, entries, servers):
        snap = T.Snapshot(entries)
        return {"trial": T.run_trial(scenario, agent, world, snap, servers), "added": snap.added}
    svc = AT.TrialService(repo, "hyd", evaluate)
    assert isinstance(svc.store, AT.PgTrials)
    out = svc.run({"scenario": "cooler", "a": {"agent": "sys:agent"}, "b": {"agent": "sys:agent", "variant": {"without_tools": ["enterprise"]}}})
    assert out["diff"]["recommended"]["same"] is False and out["diff"]["same_input"] is True
    sid = out["snapshot"]["id"]
    stored = svc.store.get_snapshot("hyd", sid)
    assert len(stored["entries"]) == 3
    key = next(iter(stored["entries"]))
    svc.store.add_entries("hyd", sid, {key: {"kind": "observation", "ok": False, "error": "덮어쓰기 시도"}, "extra|[]": {"ok": True, "value": 1}})
    again = svc.store.get_snapshot("hyd", sid)["entries"]
    assert again[key] == stored["entries"][key] and again["extra|[]"]["value"] == 1          # recorded input never replaced
    same = svc.run({"scenario": "cooler", "a": {"agent": "sys:agent"}, "snapshot": sid})
    assert same["a"]["fingerprint"] == out["a"]["fingerprint"] and len(world.reads) == 3
    listed = svc.store.list_trials("hyd", "HYD-01")
    assert same["a"]["id"] in {t["id"] for t in listed}
    assert svc.diff(out["a"]["id"], same["a"]["id"])["diff"]["same_result"] is True
    with repo._conn() as c:
        after = c.execute("select (select count(*) from bpm_proc_inst) + (select count(*) from todolist) + (select count(*) from events) as n").fetchone()["n"]
        assert after == before
        missing = AT.agent_profiles(repo, "hyd")["skill_store"]
        assert missing in (None, "스킬 저장소(tenant_skills)가 아직 없습니다")
