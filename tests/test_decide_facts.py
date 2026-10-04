"""gather_facts: every InputData is fetched from the source the ontology names for it — MES · ERP · QMS through the enterprise
endpoints (회의 L385~404: 납기 상충 판단에는 계약 · 로트 데이터가 같이 필요하다), sensors through the TSDB."""
from agentsvc import decide


class FakeTSDB:
    def latest(self, asset, name="TS1"):
        return 58.2, 2.0

    def fan100_hours(self, asset):
        return 3.0


INPUTS = [
    {"variable": "ts1", "name": "유온", "source": "sen:ts1", "sourceName": "TS1", "sourceKind": "Sensor", "tag": "TS1"},
    {"variable": "order_due_h", "name": "긴급 오더 남은 시간", "source": "sys:mes", "sourceName": "MES", "sourceKind": "System"},
    {"variable": "order_penalty_per_h", "name": "납기 지연 시 시간당 보상", "source": "sys:erp", "sourceName": "ERP", "sourceKind": "System"},
    {"variable": "order_customer_tier", "name": "고객 등급", "source": "sys:erp", "sourceName": "ERP", "sourceKind": "System"},
    {"variable": "hot_lot_claim", "name": "고온 로트 클레임 위험", "source": "sys:qms", "sourceName": "QMS", "sourceKind": "System"},
    {"variable": "hot_lot_qty", "name": "고온 로트 수량", "source": "sys:qms", "sourceName": "QMS", "sourceKind": "System"},
    {"variable": "standby_ready", "name": "예비 펌프 가용", "source": "sys:cmms", "sourceName": "CMMS", "sourceKind": "System"},
]
ENDPOINTS = {
    "/cmms/history?asset={asset}": {"system": "CMMS", "facts": {"standby_ready": True}},
    "/mes/orders?asset={asset}": {"system": "MES", "facts": {"due_in_h": 6, "remaining_qty": 1500}},
    "/erp/contract?asset={asset}": {"system": "ERP", "facts": {"customer_tier": "OEM", "penalty_per_h": 120, "failure_cost": 900, "claim_cost": 300}},
    "/qms/lots?asset={asset}": {"system": "QMS", "facts": {"hot_min": 12, "auto_lot": "L-0930-A17", "auto_qty": 800, "auto_claim": 3000, "gen_qty": 600, "gen_claim": 400}},
}


def test_delivery_and_quality_facts_come_from_erp_and_qms(monkeypatch):
    calls = []
    monkeypatch.setattr(decide.mcp_ent, "fetch", lambda ep, asset: (calls.append(ep), ENDPOINTS[ep])[1])
    facts, prov = decide.gather_facts(INPUTS, "HYD-01", {"pattern": "COOLER_DEGRADATION"}, FakeTSDB())
    assert facts["ts1"] == 58.2 and facts["order_due_h"] == 6
    assert facts["order_penalty_per_h"] == 120 and facts["order_customer_tier"] == "OEM"
    assert facts["hot_lot_claim"] == 3000 and facts["hot_lot_qty"] == 800 and facts["standby_ready"] is True
    assert calls.count("/erp/contract?asset={asset}") == 1 and calls.count("/qms/lots?asset={asset}") == 1      # one call per system
    assert calls.count('/cmms/history?asset={asset}') == 1
    how = {p["variable"]: p["how"] for p in prov}
    assert "ERP 계약" in how["order_penalty_per_h"] and "QMS" in how["hot_lot_claim"] and how["ts1"].startswith("TimescaleDB")


def test_no_hot_lot_means_no_claim_exposure(monkeypatch):
    eps = dict(ENDPOINTS, **{"/qms/lots?asset={asset}": {"system": "QMS", "facts": {"auto_qty": 0, "auto_claim": 3000}}})
    monkeypatch.setattr(decide.mcp_ent, "fetch", lambda ep, asset: eps[ep])
    facts, prov = decide.gather_facts(INPUTS[4:6], "HYD-02", {}, FakeTSDB())
    assert facts["hot_lot_claim"] == 0 and facts["hot_lot_qty"] == 0


def test_a_failing_source_is_reported_not_guessed(monkeypatch):
    def boom(ep, asset):
        raise RuntimeError("ERP down")
    monkeypatch.setattr(decide.mcp_ent, "fetch", boom)
    facts, prov = decide.gather_facts(INPUTS[2:3], "HYD-01", {}, FakeTSDB())
    assert facts["order_penalty_per_h"] is None and "ERP down" in prov[0]["error"]
