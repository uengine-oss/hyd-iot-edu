"""L8 action cards on ontology v2 (pure): DMN candidate rules, compliance rules, forecasts, BSC trade-offs, precedents, ranking."""
from agentsvc import cards
import json
from pathlib import Path
from hydcommon import ranking


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
DMN[-1]['rankingPolicy'] = (Path(ranking.__file__).with_name('ranking-default.json')).read_text(encoding='utf8')


def skill(sid, sop, kind="control", codes=("FAN_SET",), level=1, addresses=()):
    return {"skillId": sid, "sopId": sop, "name": sid, "kind": kind, "description": "", "relation": "MITIGATED_BY",
            "approver": {"id": "role:x", "name": "x", "level": level}, "addresses": list(addresses),
            "actions": [{"id": "a:" + c, "code": c, "kind": "command", "param": None, "value": 1} for c in codes], "steps": [{"id": sop + "/1"}]}


SKILLS = {s["skillId"]: s for s in [
    skill("skill:fan", "SOP-1"), skill("skill:mix", "SOP-2", codes=("FAN_SET", "LOAD_SET"), level=2),
    skill("skill:clean", "SOP-3", kind="work_order", codes=(), addresses=("cause:other",)),   # work order only: production effect from its BSC losses
    skill("skill:reset", "SOP-T", codes=("RESET",))]}
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


def test_unknown_exclusion_fact_never_fires_but_prevents_claim_of_feasibility():
    r = run({"plc_mode": None})
    assert all(not o['feasible'] for o in r['options']) and r['recommended'] is None
    assert all(any(v.get('unknown') == ['plc_mode'] for v in o['violations']) for o in r['options'])
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


def test_delivery_urgency_favours_the_card_that_keeps_production(monkeypatch):
    # The delivery/quality terms come from the reviewed rankingPolicy data (A069/A078), not from helper code.
    # 회의 L385~404: an OEM order due in 6 h with 120만원/h penalty — the card that keeps running gains, the one that stops loses
    trade = TRADE + [{"skill": "skill:clean", "measure": "msr:availability", "name": "설비 가동률", "direction": "UP", "dir": -1, "owner": "생산팀", "good": False, "conditional": False, "weight": 1.0, "conds": []}]
    base = dict(BASE, cause="cause:other", order_due_h=6, order_penalty_per_h=120, order_customer_tier="OEM")
    r = cards.evaluate(DMN, SKILLS, base, FC, trade, [], {})
    by = {o["id"]: o for o in r["options"]}
    assert by["skill:fan"]["production"] == "keep" and by["skill:mix"]["production"] == "reduce" and by["skill:clean"]["production"] == "stop"
    assert cards.production_effect({"actions": [{"code": "STOP", "kind": "command", "value": 1}, {"code": "WO_CREATE", "kind": "transaction"}]}) == "stop"
    assert cards.production_effect({"actions": [{"code": "LOAD_SET", "kind": "command", "value": 80}, {"code": "FAN_SET", "kind": "command", "value": 100}]}) == "reduce"
    assert cards.production_effect({"actions": [{"code": "FAN_SET", "kind": "command", "value": 100}], "losses": [{"measure": "msr:availability"}]}) == "keep"   # commands win over BSC guesses
    assert cards.production_effect({"actions": [{"code": "PUMP_SELECT", "kind": "command", "value": "B"}]}) == "keep"
    assert by["skill:fan"]["scoreParts"]["delivery"] == 1.12 and by["skill:mix"]["scoreParts"]["delivery"] == 0.45 and by["skill:clean"]["scoreParts"]["delivery"] == -1.12
    assert "납기" in r["explanation"] and "OEM" in r["explanation"] and "6 h" in r["explanation"]
    # no urgent order → the delivery term is 0 and the old ranking stands (backward compatible)
    r0 = run()
    assert all(o["scoreParts"]["delivery"] == 0 and o["scoreParts"]["quality"] == 0 for o in r0["options"]) and "납기" not in r0["explanation"]


def test_hot_lot_quality_risk_charges_only_the_hot_forecast_card():
    # QMS: 800 ea of an OEM lot waiting for shipment (claim 3000만원) — only the card whose forecast stays ≥ 55 ℃ is charged
    base = dict(BASE, hot_lot_claim=3000, hot_lot_qty=800)
    r = run(base)
    by = {o["id"]: o for o in r["options"]}
    assert by["skill:fan"]["scoreParts"]["quality"] == -1.5 and by["skill:mix"]["scoreParts"]["quality"] == 0      # 55.4 ℃ vs 49.0 ℃
    assert "품질" in r["explanation"] and "800" in r["explanation"]
