"""L8 action cards on ontology v2 (pure): DMN candidate rules, compliance rules, forecasts, BSC trade-offs, precedents, ranking."""
from agentsvc import cards


def T(var, op, val):
    return {"variable": var, "operator": op, "value": val}


def R(decision, rule, effect, tests, outputs=(), applies=(), penalty=None, ord_=1, kpi=None):
    return {"decision": decision, "rule": rule, "ord": ord_, "effect": effect, "penalty": penalty, "when": rule, "annotation": rule,
            "tests": tests, "outputs": list(outputs), "applies": list(applies), "penalizes": [kpi] if kpi else [], "sources": ["HM-x"]}


DMN = [
    R("dec:action-candidates", "rule:cand-cool", "SELECT", [T("failure_mode", "==", "fm:cool")], ["skill:fan", "skill:mix", "skill:clean"]),
    R("dec:action-candidates", "rule:cand-trip", "SELECT", [T("plc_state", "==", "TRIP")], ["skill:reset"], ord_=2),
    R("dec:compliance", "rule:auto", "EXCLUDE", [T("skill_kind", "==", "control"), T("plc_mode", "!=", "REMOTE_AUTO")],
      applies=["skill:fan", "skill:mix", "skill:clean"]),
    R("dec:compliance", "rule:hard", "EXCLUDE", [T("forecast_ts1", ">=", 65)], ord_=2),
    R("dec:compliance", "rule:warn", "WARN", [T("forecast_ts1", ">=", 55)], applies=["skill:fan"], ord_=3),
    R("dec:compliance", "rule:fan24", "PENALTY", [T("fan100_hours", ">", 24)], applies=["skill:fan", "skill:mix"], penalty=20, ord_=4, kpi="msr:mtbf"),
    R("dec:compliance", "rule:nopress", "EXCLUDE", [T("skill_code", "==", "PRESSURE_SET")], ord_=5),
    R("dec:rank-actions", "rule:rank", "RANK", []),
]


def skill(sid, sop, kind="control", codes=("FAN_SET",), level=1, addresses=()):
    return {"skillId": sid, "sopId": sop, "name": sid, "kind": kind, "description": "", "relation": "MITIGATED_BY",
            "approver": {"id": "role:x", "name": "x", "level": level}, "addresses": list(addresses),
            "actions": [{"id": "a:" + c, "code": c, "kind": "command", "param": None, "value": 1} for c in codes], "steps": [{"id": sop + "/1"}]}


SKILLS = {s["skillId"]: s for s in [
    skill("skill:fan", "SOP-1"), skill("skill:mix", "SOP-2", codes=("FAN_SET", "LOAD_SET"), level=2),
    skill("skill:clean", "SOP-3", addresses=("cause:other",)), skill("skill:reset", "SOP-T", codes=("RESET",))]}
FC = {"skill:fan": {"sv:ts1": {"variableName": "유온", "value": 55.4, "unit": "℃", "method": "m", "id": "fc1"}},
      "skill:mix": {"sv:ts1": {"variableName": "유온", "value": 49.0, "unit": "℃", "method": "m", "id": "fc2"}}}
TRADE = [{"skill": "skill:fan", "measure": "msr:margin", "name": "인터록 여유", "direction": "UP", "dir": 1, "owner": "생산팀", "good": True, "conditional": False, "weight": 1.0, "conds": []},
         {"skill": "skill:mix", "measure": "msr:margin", "name": "인터록 여유", "direction": "UP", "dir": 1, "owner": "생산팀", "good": True, "conditional": False, "weight": 1.0, "conds": []},
         {"skill": "skill:mix", "measure": "msr:tp", "name": "생산량", "direction": "UP", "dir": -1, "owner": "생산팀", "good": False, "conditional": False, "weight": 1.0, "conds": []}]
BASE = {"failure_mode": "fm:cool", "failure_mode_name": "냉각 성능 상실", "cause": "cause:fouling", "plc_state": "RUN", "plc_mode": "REMOTE_AUTO", "fan100_hours": 0}


def run(base=None, dmn=DMN, precedents=()):
    return cards.evaluate(dmn, SKILLS, dict(BASE, **(base or {})), FC, TRADE, list(precedents), {})


def test_candidates_come_from_the_failure_mode_rule_and_cause_limited_skills_are_filtered():
    r = run()
    assert {o["id"] for o in r["options"]} == {"skill:fan", "skill:mix"}          # skill:clean addresses another cause
    assert all(o["selectedBy"][0]["rule"] == "rule:cand-cool" for o in r["options"])


def test_forecast_and_warning_rank_the_cooler_card_first():
    r = run()
    assert r["recommended"] == "skill:mix" and r["options"][0]["id"] == "skill:mix"
    fan = next(o for o in r["options"] if o["id"] == "skill:fan")
    assert [w["rule"] for w in fan["warnings"]] == ["rule:warn"] and fan["scoreParts"]["warn"] == -0.5
    assert "SOP-2" in r["explanation"] and "49.0" in r["explanation"]


def test_mode_rule_excludes_every_control_card_and_nothing_is_recommended():
    r = run({"plc_mode": "REMOTE_MANUAL"})
    assert r["recommended"] is None and all(not o["feasible"] for o in r["options"])
    assert "제외" in r["explanation"]


def test_unknown_fact_never_fires_a_rule():
    r = run({"plc_mode": None})
    assert all(o["feasible"] for o in r["options"])
    tr = [t for t in r["trace"] if t["rule"] == "rule:auto"]
    assert tr and all(not t["fired"] and "plc_mode" in t["unknown"] for t in tr)


def test_penalty_applies_only_when_its_threshold_is_crossed():
    assert not any(o["penalties"] for o in run()["options"])
    r = run({"fan100_hours": 30})
    assert all(o["penalties"][0]["penalty"] == 20 and o["scoreParts"]["penalty"] == -1.0 for o in r["options"])


def test_skill_code_list_matches_any_command_of_the_card():
    s = dict(SKILLS)
    s["skill:fan"] = skill("skill:fan", "SOP-1", codes=("FAN_SET", "PRESSURE_SET"))
    r = cards.evaluate(DMN, s, BASE, FC, TRADE, [], {})
    fan = next(o for o in r["options"] if o["id"] == "skill:fan")
    assert not fan["feasible"] and fan["violations"][0]["rule"] == "rule:nopress"


def test_trip_state_adds_the_reset_card():
    r = run({"plc_state": "TRIP"})
    assert "skill:reset" in {o["id"] for o in r["options"]}


def test_precedent_share_is_scored_per_card():
    # share of past human choices within the same failure mode × 1.5 is added to the card's score
    r = run(precedents=[{"skill": "skill:fan", "n": 9, "reasons": ["생산 유지"]}, {"skill": "skill:mix", "n": 1, "reasons": []}])
    fan = next(o for o in r["options"] if o["id"] == "skill:fan")
    assert fan["precedent"] == {"n": 9, "share": 0.9, "reasons": ["생산 유지"]} and fan["scoreParts"]["precedent"] == 1.35
    assert r["rankRule"]["rule"] == "rule:rank"


def test_test_ok_operators():
    assert cards.test_ok(T("x", ">=", 65), {"x": 65}) and not cards.test_ok(T("x", "<", 1), {"x": 2})
    assert cards.test_ok(T("b", "==", False), {"b": False}) and cards.test_ok(T("s", "!=", "A"), {"s": "B"})
    assert cards.test_ok(T("x", ">", 1), {}) is None
