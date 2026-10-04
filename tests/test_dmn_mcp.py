"""hyd-dmn MCP tools wrap the existing deterministic engine without changing it (fake graph · fake TSDB · no network)."""
from dmn_mcp import tools as dmn


class FakeKG:
    def __init__(self):
        self.calls = []

    def t1_causes(self, pattern, asset):
        self.calls.append(("t1", pattern, asset))
        return [{"causeId": "cause:cooler-fin-fouling", "cause": "쿨러 핀 오염", "prior": 0.6, "failureModeId": "fm:cooling-loss", "failureMode": "냉각 능력 상실",
                 "evidence": [{"id": "ev:ce-high", "name": "CE 높음", "weight": 1.0, "expect": "gt", "threshold": 80, "sql": "select 1"}]},
                {"causeId": "cause:high-ambient", "cause": "외기 고온", "prior": 0.3, "failureModeId": "fm:cooling-loss", "failureMode": "냉각 능력 상실",
                 "evidence": [{"id": "ev:ambient", "name": "외기 35도", "weight": 1.0, "expect": "gt", "threshold": 33, "sql": "select 2"}]}]

    def t2_skills(self, cause_id):
        self.calls.append(("t2", cause_id))
        return [{"skillId": "skill:fan-max-derate", "sopId": "SOP-COOL-02", "name": "팬 최대 + 부하 80 %", "kind": "control", "relation": "MITIGATED_BY",
                 "actions": [{"id": "act:fan", "code": "FAN_SET", "kind": "command", "param": "fan_pct", "value": 100, "min": 0, "max": 100, "seq": 1}],
                 "steps": [{"id": "SOP-COOL-02/1", "order": 1, "text": "팬 100 %", "manual": {"ref": "HM-8 §4.2"}}]}]

    def dmn(self):
        return [{"decision": "dec:action-candidates", "rule": "rule:a", "effect": "SELECT"}, {"decision": "dec:compliance", "rule": "rule:b", "effect": "EXCLUDE"}]

    def inputs(self):
        return [{"id": "in:ts1", "variable": "ts1", "source": "sen:ts1", "sourceKind": "Sensor"}]

    def precedents(self, fm):
        return [{"skill": "skill:fan-max-derate", "n": 3}]

    def tradeoffs(self, ids):
        return [{"skill": i, "measure": "msr:op-profit", "dir": 1} for i in ids]

    def ping(self):
        return True


class FakeTSDB:
    def evaluate(self, evidence, asset):
        return {e["id"]: {"value": 91.0 if e["id"] == "ev:ce-high" else 30.0, "passed": e["id"] == "ev:ce-high"} for e in evidence}

    def latest(self, asset, name="TS1"):
        return 58.2, 2.0


def test_diagnose_ranks_causes_and_builds_a_cited_card(monkeypatch):
    monkeypatch.setattr(dmn.mcp_prom, "freshness", lambda tsdb, asset: {"ok": True, "age_s": 2.0, "latest_ts1": 58.2})
    t = dmn.DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    out = t.diagnose("HYD-01", "COOLER_DEGRADATION")
    assert out["withheld"] is False and out["top_cause"] == "cause:cooler-fin-fouling" and out["failure_mode"] == "fm:cooling-loss"
    assert [c["id"] for c in out["causes"]] == ["cause:cooler-fin-fouling", "cause:high-ambient"]
    card = out["card"]
    assert card["topCause"] == "cause:cooler-fin-fouling" and card["recommended"][0]["code"] == "FAN_SET" and card["recommended"][0]["paramRange"] == [0, 100]
    assert {"cause:cooler-fin-fouling", "ev:ce-high", "skill:fan-max-derate", "act:fan", "SOP-COOL-02/1", "HM-8 §4.2"} <= set(card["citations"])
    assert t.kg.calls[0] == ("t1", "COOLER_DEGRADATION", "HYD-01") and ("t2", "cause:cooler-fin-fouling") in t.kg.calls


def test_diagnose_is_withheld_when_data_is_stale(monkeypatch):
    monkeypatch.setattr(dmn.mcp_prom, "freshness", lambda tsdb, asset: {"ok": False, "reason": "data age is 300 s"})
    out = dmn.DmnTools(kg=FakeKG(), tsdb=FakeTSDB()).diagnose("HYD-01", "COOLER_DEGRADATION")
    assert out["withheld"] is True and out["card"] is None and "300 s" in out["reason"]


def test_rules_inputs_precedents_tradeoffs_pass_through():
    t = dmn.DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    assert [r["rule"] for r in t.dmn_rules()] == ["rule:a", "rule:b"] and t.dmn_rules("dec:compliance")[0]["rule"] == "rule:b"
    assert t.inputs()[0]["variable"] == "ts1" and t.precedents("fm:cooling-loss")[0]["n"] == 3
    assert t.tradeoffs(["skill:x"])[0]["skill"] == "skill:x"
    assert t._cause("cause:x", "fm:y") == {"id": "cause:x", "name": "cause:x", "failureModeId": "fm:y", "failureMode": "fm:y"}
    assert t.health()["neo4j"] is True


def test_envelope_wraps_results_and_turns_exceptions_into_errors():
    assert dmn.enveloped(lambda: [1, 2])() == {"result": "ok", "document": [1, 2]}
    bad = dmn.enveloped(lambda: (_ for _ in ()).throw(KeyError("dec:nope")))()
    assert bad["result"] == "error" and bad["error_kind"] == "INVALID" and "dec:nope" in bad["message"]
    boom = dmn.enveloped(lambda: (_ for _ in ()).throw(RuntimeError("neo4j down")))()
    assert boom["result"] == "error" and boom["error_kind"] == "UNKNOWN" and "neo4j down" in boom["message"]
