"""Seed data of the mock enterprise systems (교육용 가상 데이터 — 회사 · 고객 · 금액은 모두 예시).

Every read endpoint returns {"system", "facts": {...}, "records": [...]}. `facts` are the scalars the agent's
decision engine uses (the ontology formulas name them as <prefix>_<key>); `records` are what a user would see in
that system's screen. Money is in 만원 (KRW 10k), times in hours unless the key says otherwise.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

ASSETS = ("HYD-01", "HYD-02", "HYD-03")

# A086: the hour/day numbers below are the teaching scenario *at its start* (납기 6 h …), not frozen facts. Like the Supabase
# backend (due_at · ship_at · performed_at), the current value is computed from the scenario start, which reset() re-anchors.
_SCENARIO_START = datetime.now(timezone.utc)
_CLEAN_HISTORY_DAYS = {"HYD-01": [21, 38, 55], "HYD-02": [21], "HYD-03": [80]}   # CMMS 쿨러 핀 세척 이력 (시작 시점 기준 경과일)


def reanchor(now: datetime | None = None) -> None:
    global _SCENARIO_START
    _SCENARIO_START = now or datetime.now(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _at(hours_from_start: float) -> datetime:
    return _SCENARIO_START + timedelta(hours=hours_from_start)


def hours_from_now(at: datetime | None) -> float | None:
    return None if at is None else round((at - _now()).total_seconds() / 3600, 2)


def current_order(o: dict) -> dict:
    """An order row with its time fields as of now (due_at · alt_free_at stored, hours computed)."""
    due_at, alt_at = _at(o["due_in_h"]), (_at(o["alt_free_h"]) if o.get("alt_free_h") is not None else None)
    return dict(o, due_at=due_at.isoformat(), alt_free_at=alt_at.isoformat() if alt_at else None,
                due_in_h=hours_from_now(due_at), alt_free_h=hours_from_now(alt_at))

# MES: the order each unit is running now and where it could go
_ORDERS = {
    "HYD-01": {"order_id": "MO-0930-0412", "item": "FG-AUTO-7 (유압 브래킷)", "customer": "가나자동차 (OEM, 교육용 가상)", "due_in_h": 6,
               "remaining_qty": 1500, "rate_per_h": 300, "hour_value": 50, "alt_asset": "HYD-02", "alt_free_h": 8, "alt_rate_per_h": 270, "changeover_h": 1},
    "HYD-02": {"order_id": "MO-0930-0415", "item": "FG-IND-3 (산업용 매니폴드)", "customer": "다라산업 (일반, 교육용 가상)", "due_in_h": 20,
               "remaining_qty": 800, "rate_per_h": 250, "hour_value": 40, "alt_asset": "HYD-03", "alt_free_h": 4, "alt_rate_per_h": 240, "changeover_h": 1},
    "HYD-03": {"order_id": "MO-0930-0419", "item": "FG-AUTO-9 (실린더 블록)", "customer": "가나자동차 (OEM, 교육용 가상)", "due_in_h": 3,
               "remaining_qty": 600, "rate_per_h": 300, "hour_value": 50, "alt_asset": "HYD-01", "alt_free_h": 2, "alt_rate_per_h": 280, "changeover_h": 1},
}
# ERP: contract terms of that order + cost of an unplanned failure on this unit
_CONTRACT = {
    "HYD-01": {"sales_order": "SO-2609-118", "customer_tier": "OEM", "penalty_per_h": 120, "failure_cost": 900, "claim_cost": 300},
    "HYD-02": {"sales_order": "SO-2609-131", "customer_tier": "일반", "penalty_per_h": 20, "failure_cost": 500, "claim_cost": 80},
    "HYD-03": {"sales_order": "SO-2609-140", "customer_tier": "OEM", "penalty_per_h": 120, "failure_cost": 900, "claim_cost": 300},
}
_INVENTORY = {"HYD-01": {"fg_item": "FG-AUTO-7", "fg_stock": 900, "ship_in_h": 2},
              "HYD-02": {"fg_item": "FG-IND-3", "fg_stock": 100, "ship_in_h": 10},
              "HYD-03": {"fg_item": "FG-AUTO-9", "fg_stock": 200, "ship_in_h": 3}}
# CMMS: maintenance profile of the cooler (세척 횟수 · 마지막 세척은 _CLEAN_HISTORY_DAYS 이력에서 계산)
_CMMS = {"HYD-01": {"clean_h": 3, "clean_cost": 40, "night_in_h": 9, "oil_risk_per_h": 5, "mtbf_h": 1400, "standby_ready": True},
         "HYD-02": {"clean_h": 3, "clean_cost": 40, "night_in_h": 9, "oil_risk_per_h": 5, "mtbf_h": 2600, "standby_ready": True},
         "HYD-03": {"clean_h": 3, "clean_cost": 40, "night_in_h": 9, "oil_risk_per_h": 5, "mtbf_h": 3100, "standby_ready": True}}
# QMS: lots produced during the last over-temperature window
_QMS = {"HYD-01": {"hot_min": 12, "auto_lot": "L-0930-A17", "auto_qty": 800, "gen_lot": "L-0930-G05", "gen_qty": 600,
                   "inspect_h": 4, "inspect_cost": 60, "sample_cost": 10, "gen_defect_p": 0.03, "gen_claim": 400, "auto_defect_p": 0.05, "auto_claim": 3000},
        "HYD-02": {"hot_min": 0, "auto_lot": "-", "auto_qty": 0, "gen_lot": "L-0930-G09", "gen_qty": 500,
                   "inspect_h": 3, "inspect_cost": 40, "sample_cost": 8, "gen_defect_p": 0.01, "gen_claim": 200, "auto_defect_p": 0.0, "auto_claim": 0},
        "HYD-03": {"hot_min": 5, "auto_lot": "L-0930-A21", "auto_qty": 400, "gen_lot": "-", "gen_qty": 0,
                   "inspect_h": 3, "inspect_cost": 35, "sample_cost": 0, "gen_defect_p": 0.0, "gen_claim": 0, "auto_defect_p": 0.04, "auto_claim": 3000}}
# SCM: quotes for the cooler core (P-CLR-CORE); standard price is the purchasing KPI baseline
_SUPPLIERS = [
    {"id": "sup:a", "key": "a", "name": "A정밀 (저가)", "price": 180, "fail": 0.12, "lead_d": 3, "avl": True, "quality_score": 0.78},
    {"id": "sup:b", "key": "b", "name": "B-OEM (순정)", "price": 260, "fail": 0.02, "lead_d": 5, "avl": True, "quality_score": 0.97},
    {"id": "sup:c", "key": "c", "name": "C트레이딩 (최저가)", "price": 120, "fail": 0.20, "lead_d": 2, "avl": False, "quality_score": 0.61},
]
_STD_PRICE = {"P-CLR-CORE": 250}
# EMS: this afternoon's demand vs contract (폭염)
_EMS = {"contract_kw": 450, "demand_kw": 438, "fan_boost_kw": 6, "basic_rate": 0.8, "peak_h": 3, "peak_window": "14:00-17:00", "outdoor_c": 35, "energy_rate": 0.015}


def _check(asset: str) -> str:
    if asset not in ASSETS:
        raise KeyError(asset)
    return asset


def mes_orders(asset: str) -> dict:
    o = current_order(_ORDERS[_check(asset)])
    return {"system": "MES", "facts": {k: v for k, v in o.items() if isinstance(v, (int, float))} | {"order_id": o["order_id"], "alt_asset": o["alt_asset"], "due_at": o["due_at"]},
            "records": [dict(o, asset=asset)], "as_of": _now().isoformat()}


def erp_contract(asset: str) -> dict:
    c = _CONTRACT[_check(asset)]
    return {"system": "ERP", "facts": dict(c), "records": [dict(c, asset=asset, order=_ORDERS[asset]["order_id"], customer=_ORDERS[asset]["customer"])]}


def erp_inventory(asset: str) -> dict:
    i = _INVENTORY[_check(asset)]
    ship_at = _at(i["ship_in_h"])
    cur = dict(i, ship_in_h=hours_from_now(ship_at), ship_at=ship_at.isoformat())
    return {"system": "ERP", "facts": cur, "records": [dict(cur, warehouse="WH-1 완제품 창고")], "as_of": _now().isoformat()}


def cmms_history(asset: str) -> dict:
    c = _CMMS[_check(asset)]
    done = [_SCENARIO_START - timedelta(days=d) for d in _CLEAN_HISTORY_DAYS[asset]]
    now = _now()
    recs = [{"wo": f"WO-HIST-{asset[-2:]}-{n}", "task": "쿨러 핀 세척", "performed_at": t.isoformat(), "days_ago": int((now - t).total_seconds() // 86400)}
            for n, t in enumerate(done, 1)]
    facts = {k: v for k, v in c.items() if k != "night_in_h"} | {
        "night_in_h": hours_from_now(_at(c["night_in_h"])),
        "cleans_60d": sum(1 for t in done if now - t < timedelta(days=60)),
        "last_clean_days": int((now - max(done)).total_seconds() // 86400) if done else None}
    return {"system": "CMMS", "facts": facts, "records": recs, "as_of": now.isoformat()}


def qms_lots(asset: str) -> dict:
    q = _QMS[_check(asset)]
    recs = [r for r in ({"lot": q["auto_lot"], "customer": "OEM", "qty": q["auto_qty"], "status": "출하 대기"},
                        {"lot": q["gen_lot"], "customer": "일반", "qty": q["gen_qty"], "status": "출하 대기"}) if r["qty"]]
    return {"system": "QMS", "facts": dict(q), "records": recs}


def scm_suppliers(part: str) -> dict:
    facts = {"std_price": _STD_PRICE.get(part, 0)}
    for s in _SUPPLIERS:
        facts |= {f"{s['key']}_price": s["price"], f"{s['key']}_fail": s["fail"], f"{s['key']}_lead_d": s["lead_d"], f"{s['key']}_avl": int(s["avl"])}
    return {"system": "SCM", "facts": facts, "records": [dict(s, part=part) for s in _SUPPLIERS]}


def ems_demand() -> dict:
    return {"system": "EMS", "facts": dict(_EMS), "records": [dict(_EMS, site="창원 1공장 (교육용 가상)")]}


def prefixed(resp: dict) -> dict:
    """{"system": "MES", "facts": {"due_in_h": 6}} -> {"mes_due_in_h": 6} (the names the ontology formulas use)."""
    p = resp["system"].lower()
    return {f"{p}_{k}": v for k, v in resp["facts"].items()}
