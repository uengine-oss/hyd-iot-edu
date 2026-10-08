"""A10 에이전트 시험 실행(드라이런) — agent 서비스 쪽 순수 판단(it/agent/agentsvc/trial.py).

같은 입력 스냅숏 + 같은 설정 → 같은 결과(fingerprint), 도구 구성 차이(E4) → 사실 · 1순위 차이, 스킬 차이(E3) → 도구 호출 순서 · 인용 차이,
제출 · 명령 경로 없음. 원천은 가짜(그래프 · 시계열 · 업무 DB 없이), 판단 엔진(cards.evaluate)은 진짜.
"""
import copy
import json

import pytest

from agentsvc import trial as T
from test_cards import DMN, SKILLS, FC, TRADE, R, T as rule_test

SCENARIO = {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION"}
# fixture rule (test data, not product knowledge): a reduce-load card is ruled out when the urgent order is due within 4 h —
# a business fact from MES. Known false (due in 6 h) → no effect; unknown (no enterprise tool) → the card cannot be cleared.
DMN_TRIAL = DMN[:-1] + [R("dec:compliance", "rule:due-near", "EXCLUDE", [rule_test("order_due_h", "<", 4)], applies=["skill:mix"], ord_=6)] + DMN[-1:]
TRADE_CLEAN = TRADE + [{"skill": "skill:clean", "measure": "msr:availability", "name": "설비 가동률", "direction": "UP", "dir": -1,
                        "owner": "생산팀", "good": False, "conditional": False, "weight": 1.0, "conds": []}]


class FakeWorld:
    """Counts every live read; a replayed snapshot must not reach it."""

    def __init__(self, withheld=False, fail_facts=False):
        self.reads = []
        self.withheld, self.fail_facts = withheld, fail_facts

    def diagnose(self, asset, pattern):
        self.reads.append(("diagnose", asset, pattern))
        causes = [{"id": "cause:other", "name": "쿨러 핀 오염", "score": 0.6, "failureModeId": "fm:cool", "failureMode": "냉각 성능 상실",
                   "evidence": [{"id": "ev:ce-low", "name": "냉각 효율 낮음", "status": "PASS", "value": 61.0, "threshold": 70, "expect": "lt"}]}]
        if self.withheld:
            return {"withheld": True, "causes": causes, "reason": "현재 관측 근거로 뒷받침되는 원인이 없어 조치를 보류합니다."}
        return {"withheld": False, "causes": causes, "skills": [{"id": "skill:fan"}, {"id": "skill:mix"}],
                "citations": ["cause:other", "fm:cool", "ev:ce-low", "skill:fan", "SOP-1"]}

    def gather_facts(self, asset, pattern, cause):
        self.reads.append(("gather_facts", asset, cause["id"]))
        if self.fail_facts:
            raise ConnectionError("업무 DB 연결 거부")
        facts = {"pattern": pattern, "cause": cause["id"], "failure_mode": "fm:cool", "failure_mode_name": "냉각 성능 상실",
                 "plc_state": "RUN", "plc_mode": "REMOTE_AUTO", "fan100_hours": 0,
                 "order_due_h": 6, "order_penalty_per_h": 120, "order_customer_tier": "OEM"}
        src = {"plc_state": "sys:scada", "plc_mode": "sys:scada", "fan100_hours": "sys:historian",
               "order_due_h": "sys:mes", "order_penalty_per_h": "sys:erp", "order_customer_tier": "sys:erp"}
        prov = [{"variable": v, "name": v, "source": s, "sourceName": s, "value": facts[v], "how": "fixture"} for v, s in src.items()]
        return {"facts": facts, "provenance": prov}

    def engine_inputs(self, asset, failure_mode):
        self.reads.append(("engine", asset, failure_mode))
        return {"dmn": copy.deepcopy(DMN_TRIAL), "skills": copy.deepcopy(SKILLS), "forecasts": copy.deepcopy(FC), "forecast_contexts": None,
                "tradeoffs": copy.deepcopy(TRADE_CLEAN), "precedents": [], "suppliers": {}}

    def tool(self, server, tool, args):
        self.reads.append(("tool", server, tool, json.dumps(args, sort_keys=True)))
        if tool == "precedents":
            return [{"skill": "skill:fan", "n": 3, "reasons": ["생산 유지"]}]
        if tool == "timeseries_query":
            return {"columns": ["avg"], "rows": [[1.41]], "row_count": 1, "statement": args["sql"]}
        if tool == "mes_orders":
            return {"system": "MES", "facts": {"due_in_h": 6}, "records": []}
        raise AssertionError(f"unexpected tool {tool}")


def agent(tools=("hyd-dmn", "enterprise", "neo4j"), skills=(), aid="sys:agent"):
    return {"id": aid, "name": "AI 에이전트", "tools": list(tools), "skills": list(skills)}


def run(profile, world, entries=None, servers=("hyd-dmn", "enterprise", "neo4j")):
    snap = T.Snapshot(entries)
    out = T.run_trial(SCENARIO, profile, world, snap, list(servers) if servers is not None else None)
    return out, snap


FAN_SKILL = {"name": "fan-check", "description": "팬 진동 점검 순서",
             "content": "1. `precedents`로 같은 고장 유형에서 사람이 고른 카드를 먼저 본다.\n"
                        "2. mcp__hyd-dmn__timeseries_query 로 최근 진동 평균을 본다.\n"
                        "```sql\nselect avg(value) from tag_1s where asset = '{asset}' and name = 'VS1'\n```\n"
                        "3. 그다음 원래 순서대로 판단한다."}


def test_same_snapshot_and_same_setting_give_the_same_result_without_reading_sources_again():
    world = FakeWorld()
    first, snap = run(agent(skills=[FAN_SKILL]), world)
    live = len(world.reads)
    assert first["status"] == "EVALUATED" and live == 5            # diagnose · 2 skill tools · gather_facts · engine
    assert {c.get("source") for c in first["calls"] if c["status"] == "DONE"} == {"live"}
    second, again = run(agent(skills=[FAN_SKILL]), world, entries=snap.entries)
    assert len(world.reads) == live and again.added == {}           # replay only — same input
    assert {c.get("source") for c in second["calls"] if c["status"] == "DONE"} == {"snapshot"}
    assert second["fingerprint"] == first["fingerprint"] and second["recommended"] == first["recommended"]
    # a different agent id with the same setting concludes the same (the fingerprint is about the judgment, not the name)
    third, _ = run(agent(skills=[FAN_SKILL], aid="agent:copy"), world, entries=snap.entries)
    assert third["fingerprint"] == first["fingerprint"]


def test_tool_composition_changes_the_facts_and_the_first_card_E4():
    world = FakeWorld()
    full, snap = run(agent(), world)
    narrow, _ = run(agent(tools=("hyd-dmn",)), world, entries=snap.entries)
    blocked = {f["variable"] for f in narrow["facts"] if f.get("blocked")}
    assert blocked == {"order_due_h", "order_penalty_per_h", "order_customer_tier"}
    assert not any(f.get("blocked") for f in full["facts"])
    # 납기 조건을 못 읽으면 그 조건을 검사하는 규정이 '미확인'이 되어 감산 카드가 빠지고 1순위가 바뀐다
    assert full["recommended"]["id"] == "skill:mix" and narrow["recommended"]["id"] == "skill:fan"
    mix = next(c for c in narrow["compliance"] if c["id"] == "skill:mix")
    assert any("order_due_h" in x for x in mix["excluded"])
    by_full = {o["id"]: o for o in full["ranking"]}
    assert by_full["skill:fan"]["scoreParts"]["delivery"] > 0 and all(o["scoreParts"]["delivery"] == 0 for o in narrow["ranking"])
    gather = next(c for c in narrow["calls"] if c["tool"] == "gather_facts")
    assert gather["blocked_facts"] and "업무 DB 값 3개" in gather["summary"]
    assert full["fingerprint"] != narrow["fingerprint"]


def test_skill_adds_tool_calls_in_its_order_and_new_citations_E3():
    world = FakeWorld()
    plain, snap = run(agent(), world)
    skilled, _ = run(agent(skills=[FAN_SKILL]), world, entries=snap.entries)
    assert [c["tool"] for c in plain["calls"]] == ["diagnose", "gather_facts", "evaluate_cards"]
    assert [c["tool"] for c in skilled["calls"]] == ["diagnose", "precedents", "timeseries_query", "gather_facts", "evaluate_cards"]
    sql = skilled["calls"][2]["args"]["sql"]
    assert "'HYD-01'" in sql and "{asset}" not in sql and skilled["calls"][2]["by"] == "스킬 fan-check"
    refs = {c["ref"] for c in skilled["citations"]} - {c["ref"] for c in plain["citations"]}
    assert "도구:hyd-dmn/timeseries_query" in refs
    assert skilled["agent"]["skills"] == [{"name": "fan-check", "applied": True, "reason": None, "steps": 2}]


def test_skill_scoped_to_another_asset_is_not_followed_and_says_why():
    other = dict(FAN_SKILL, content="HYD-03 팬에서만: `precedents` 를 본다")
    out, _ = run(agent(skills=[other]), FakeWorld())
    assert [c["tool"] for c in out["calls"]] == ["diagnose", "gather_facts", "evaluate_cards"]
    assert out["agent"]["skills"][0]["applied"] is False and "HYD-03" in out["agent"]["skills"][0]["reason"]


def test_skill_without_body_is_reported_not_silently_dropped():
    out, _ = run(agent(skills=[{"name": "ghost", "content": "", "missing": "스킬 저장소(tenant_skills)가 아직 없습니다"}]), FakeWorld())
    assert out["agent"]["skills"][0] == {"name": "ghost", "applied": False, "reason": "스킬 저장소(tenant_skills)가 아직 없습니다", "steps": 0}


def test_skill_asking_for_submission_or_writes_is_blocked_and_nothing_is_read():
    risky = {"name": "risky", "content": "끝나면 `submit_decision` 을 부르고 write_neo4j_cypher 로 기록한다"}
    world = FakeWorld()
    out, _ = run(agent(skills=[risky]), world)
    blocked = [c for c in out["calls"] if c["by"] == "스킬 risky"]
    assert [c["tool"] for c in blocked] == ["submit_decision", "write_neo4j_cypher"] and all(c["status"] == "BLOCKED" for c in blocked)
    assert "제출하지 않습니다" in blocked[0]["reason"]
    assert not any(r[0] == "tool" for r in world.reads)


def test_sql_tool_without_a_code_block_fails_with_a_reason():
    out, _ = run(agent(skills=[{"name": "nosql", "content": "timeseries_query 로 본다"}]), FakeWorld())
    step = next(c for c in out["calls"] if c["tool"] == "timeseries_query")
    assert step["status"] == "FAILED" and "```sql" in step["reason"]


def test_skill_tool_on_a_server_the_agent_lacks_is_blocked():
    world = FakeWorld()
    out, _ = run(agent(tools=("hyd-dmn",), skills=[{"name": "mes", "content": "mes_orders로 납기를 본다"}]), world)
    step = next(c for c in out["calls"] if c["tool"] == "mes_orders")
    assert step["status"] == "BLOCKED" and "enterprise" in step["reason"]
    assert not any(r[0] == "tool" for r in world.reads)


def test_without_the_engine_tool_nothing_is_judged():
    world = FakeWorld()
    out, snap = run(agent(tools=("enterprise",)), world)
    assert out["status"] == "NO_ENGINE_TOOL" and "hyd-dmn" in out["reason"] and world.reads == [] and snap.added == {}
    assert out["recommended"] is None and out["calls"][0]["status"] == "BLOCKED"


def test_tool_not_registered_for_the_tenant_counts_as_missing():
    out, _ = run(agent(tools=("hyd-dmn", "enterprise")), FakeWorld(), servers=("hyd-dmn",))
    assert out["agent"]["tools"] == ["hyd-dmn"] and out["agent"]["tool_notes"][0]["tool"] == "enterprise"
    assert {f["variable"] for f in out["facts"] if f.get("blocked")} == {"order_due_h", "order_penalty_per_h", "order_customer_tier"}


def test_withheld_diagnosis_stops_before_facts_and_cards():
    world = FakeWorld(withheld=True)
    out, _ = run(agent(), world)
    assert out["status"] == "WITHHELD" and [r[0] for r in world.reads] == ["diagnose"] and out["ranking"] == []


def test_a_failed_read_is_part_of_the_frozen_input():
    world = FakeWorld(fail_facts=True)
    first, snap = run(agent(), world)
    assert first["status"] == "FAILED" and "업무 DB 연결 거부" in first["reason"]
    reads = len(world.reads)
    second, _ = run(agent(), FakeWorld(), entries=snap.entries)       # a healthy world now — but the frozen input says failed
    assert second["status"] == "FAILED" and second["fingerprint"] == first["fingerprint"] and reads == 2


def test_trial_module_has_no_write_path():
    """The trial never imports or calls the submission/command paths; the only mention of submit_decision is the refusal."""
    import inspect
    src = inspect.getsource(T)
    assert "decide.submit" not in src and "submit_card" not in src and "/api/incidents" not in src.replace("/api/incidents ·", "")
    assert "urlopen" not in src and "INSERT" not in src.upper().replace("INSERTED", "")


def test_skill_procedure_reads_korean_text_with_particles_and_fences():
    steps = T.skill_procedure("먼저 mes_orders로 납기를 보고, `inputs`를 확인한 뒤 qms_lots 결과와 비교한다.\n```sql\nselect 1\n```\n"
                              "query 라는 단어나 inputs 라는 단어는 도구가 아니다. mcp__hyd-dmn__timeseries_query")
    assert [s["tool"] for s in steps] == ["mes_orders", "inputs", "qms_lots", "timeseries_query"]
    assert steps[-1]["sql"] == "select 1" and steps[-1]["server"] == "hyd-dmn"


def test_cypher_writes_are_refused_before_touching_the_graph():
    class Boom:
        def session(self, **_):
            raise AssertionError("graph touched")
    with pytest.raises(ValueError, match="쓰기 Cypher"):
        T.read_cypher(Boom(), "MATCH (n) SET n.x = 1")


def test_agent_service_trial_endpoint_returns_trial_and_new_entries(monkeypatch):
    from agentsvc import main
    world = FakeWorld()
    monkeypatch.setattr(main, "kg", object())
    monkeypatch.setattr(T, "LiveWorld", lambda kg, tsdb: world)
    monkeypatch.setattr(main.decidelib, "submit", lambda *_: pytest.fail("trial submitted a decision"))
    monkeypatch.setattr(main, "submit_card", lambda *_: pytest.fail("trial submitted a card"))
    req = main.TrialReq(scenario=SCENARIO, agent=agent(), entries={}, tenant_servers=["hyd-dmn", "enterprise", "neo4j"])
    out = main.agent_trial(req)
    assert out["trial"]["status"] == "EVALUATED" and len(out["added"]) == 3
    again = main.agent_trial(main.TrialReq(scenario=SCENARIO, agent=agent(), entries=out["added"], tenant_servers=req.tenant_servers))
    assert again["added"] == {} and again["trial"]["fingerprint"] == out["trial"]["fingerprint"]
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        main.agent_trial(main.TrialReq(scenario={"asset": "HYD-01"}, agent=agent()))
