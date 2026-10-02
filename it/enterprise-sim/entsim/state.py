"""Write side of the mock enterprise systems: what happens in ERP/MES/CMMS/QMS/EMS when the L9 process executes an
approved agent skill. Only the process service calls this (the agent has no write access to enterprise systems)."""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
import secrets
import threading
from datetime import datetime, timezone

from . import data

SKILLS = {
    "skill:schedule-maintenance": "sys:cmms", "skill:reallocate-production": "sys:mes", "skill:procure-part": "sys:erp",
    "skill:hold-lot": "sys:qms", "skill:release-lot": "sys:qms", "skill:substitute-shipment": "sys:erp", "skill:demand-control": "sys:ems",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}-{datetime.now():%m%d}-{secrets.token_hex(2).upper()}"


class EnterpriseState:
    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._db = None
        self.reset()
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            row = self._db.execute("SELECT body FROM state WHERE id=1").fetchone()
            if row:
                saved = json.loads(row[0])
                self._s, self._tx, self._done = saved["state"], saved["transactions"], saved["done"]

    def _save(self):
        if self._db:
            with self._db:
                self._db.execute("INSERT OR REPLACE INTO state VALUES (1,?)",
                    (json.dumps({"state": self._s, "transactions": self._tx, "done": self._done}),))

    def reset(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self._tx: list[dict] = []
            self._done = {}
            self._s = {
                "mes": {"orders": [dict(o, asset=a, moved_from=None) for a, o in copy.deepcopy(data._ORDERS).items()]},
                "cmms": {"work_orders": []},
                "erp": {"purchase_requests": [], "shipments": []},
                "qms": {"holds": [], "releases": []},
                "ems": {"actions": []},
            }
            self._save()

    def execute(self, req: dict) -> dict:
        skill = req.get("skill")
        if skill not in SKILLS:
            raise ValueError(f"unknown or non-enterprise skill {skill!r}")
        asset = req.get("asset") or "HYD-01"
        params = req.get("params") or {}
        with self._lock:
            key = json.dumps([req.get("decision"), skill]) if req.get("decision") else None
            fingerprint = json.dumps({k: req.get(k) for k in ("decision", "option", "skill", "asset", "params")}, sort_keys=True)
            if key in self._done:
                prior = self._done[key]
                if prior["fingerprint"] != fingerprint:
                    raise ValueError("idempotency conflict: decision/skill already executed with different input")
                return copy.deepcopy(prior["tx"])
            ref, detail = self._apply(skill, asset, params, req)
            tx = {"id": _id("TX"), "t": _now(), "system": SKILLS[skill], "skill": skill, "ref": ref, "detail": detail,
                  "asset": asset, "decision": req.get("decision"), "option": req.get("option"), "by": req.get("by")}
            self._tx.insert(0, tx)
            del self._tx[300:]
            if key:
                self._done[key] = {"fingerprint": fingerprint, "tx": tx}
            self._save()
            return tx

    def _apply(self, skill: str, asset: str, params: dict, req: dict) -> tuple[str, str]:
        s = self._s
        if skill == "skill:schedule-maintenance":
            when = params.get("window") or ("야간 정비창" if "derate" in str(req.get("option")) else "즉시")
            wo = {"id": _id("WO"), "asset": asset, "task": params.get("task", "쿨러 핀 세척 (SOP-COOL-02)"), "window": when, "status": "배정됨"}
            s["cmms"]["work_orders"].insert(0, wo)
            return wo["id"], f"{asset} {wo['task']} — {when}"
        if skill == "skill:reallocate-production":
            order = next((o for o in s["mes"]["orders"] if o["asset"] == asset), None)
            if order is None:
                return "-", f"{asset}에 이관할 오더 없음"
            alt = params.get("to") or order["alt_asset"]
            order.update(moved_from=asset, asset=alt)
            return order["order_id"], f"{order['order_id']} {asset} → {alt} 이관"
        if skill == "skill:procure-part":
            sup = params.get("supplier", "sup:b")
            name = next((x["name"] for x in data._SUPPLIERS if x["id"] == sup), sup)
            part = params.get("part") or "쿨러 코어"
            pr = {"id": _id("PR"), "part": part, "supplier": sup, "supplierName": name, "asset": asset, "status": "승인됨 → 발주"}
            s["erp"]["purchase_requests"].insert(0, pr)
            return pr["id"], f"{part} 구매요청 — {name}"
        if skill == "skill:hold-lot":
            lots = data._QMS[asset]
            lot = params.get("lot") or lots["auto_lot"]
            s["qms"]["holds"].insert(0, {"lot": lot, "asset": asset, "status": "격리 · 전수검사 대기"})
            return lot, f"로트 {lot} 격리 · 전수검사"
        if skill == "skill:release-lot":
            lot = params.get("lot") or data._QMS[asset]["gen_lot"]
            s["qms"]["releases"].insert(0, {"lot": lot, "asset": asset, "status": "샘플검사 후 출하 승인"})
            return lot, f"로트 {lot} 출하 승인"
        if skill == "skill:substitute-shipment":
            inv = data._INVENTORY[asset]
            sh = {"id": _id("SH"), "item": inv["fg_item"], "qty": data._QMS[asset]["auto_qty"], "from": "WH-1 완제품 재고"}
            s["erp"]["shipments"].insert(0, sh)
            return sh["id"], f"{inv['fg_item']} {sh['qty']}개 재고 대체 출하"
        if skill == "skill:demand-control":
            act = {"action": params.get("action", "HYD-03 비긴급 오더 야간 이동에 맞춰 피크 수요 목표 설정"), "t": _now()}
            s["ems"]["actions"].insert(0, act)
            return "EMS", act["action"]
        raise ValueError(skill)

    def transactions(self) -> list[dict]:
        with self._lock:
            return list(self._tx)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._s)
