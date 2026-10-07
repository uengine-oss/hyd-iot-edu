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
# Exact inverses the business systems really offer (A072, 2026-10-05). An inverse needs the original reference and only
# applies while the record is still in the state the forward transaction created. Everything else is irreversible:
# the process must get a person's acknowledgement instead of pretending to undo it (product compensation.py principle).
COMPENSATION_SKILLS = {
    "skill:cancel-work-order": "sys:cmms", "skill:cancel-purchase-request": "sys:erp",
    "skill:restore-production": "sys:mes", "skill:release-hold": "sys:qms",
}
INVERSE_OF = {"skill:schedule-maintenance": "skill:cancel-work-order", "skill:procure-part": "skill:cancel-purchase-request",
              "skill:reallocate-production": "skill:restore-production", "skill:hold-lot": "skill:release-hold"}
# Korean display names of the business skills (system of record for the portal's names.json — A150). The forward
# names come from the v1 enterprise seed (it/neo4j/v1/seed_enterprise.cypher); the v2 graph does not carry these skills.
SKILL_NAMES = {
    "skill:schedule-maintenance": "정비 작업지시 발행", "skill:reallocate-production": "생산오더 대체 설비 이관",
    "skill:procure-part": "부품 구매요청", "skill:hold-lot": "로트 격리 · 전수검사", "skill:release-lot": "로트 출하 승인",
    "skill:substitute-shipment": "완제품 재고 대체 출하", "skill:demand-control": "수요 제어 지시",
    "skill:cancel-work-order": "정비 작업지시 취소", "skill:cancel-purchase-request": "구매요청 취소",
    "skill:restore-production": "생산오더 원래 설비 복원", "skill:release-hold": "로트 격리 해제",
}
IRREVERSIBLE = {"skill:release-lot": "출하 승인은 출하 절차로 넘어가 되돌릴 수 없다",
                "skill:substitute-shipment": "대체 출하는 물류가 움직여 되돌릴 수 없다",
                "skill:demand-control": "수요 제어 지시는 이미 외부에 전달돼 되돌릴 수 없다"}
SKILLS.update(COMPENSATION_SKILLS)
CANCELLED = "취소"


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
        # A115 (r14 A7, wms `INVALID: unknown sku`; same checks as ent.exec_skill/exec_compensation, migration 22)
        if (req.get("asset") is not None or skill not in COMPENSATION_SKILLS) and asset not in data.ASSETS:
            raise ValueError(f"INVALID: unknown asset {asset}")
        if skill == "skill:procure-part" and params.get("supplier", "sup:b") not in {x["id"] for x in data._SUPPLIERS}:
            raise ValueError(f"INVALID: unknown supplier {params.get('supplier')}")
        if skill == "skill:reallocate-production" and "to" in params and (params["to"] not in data.ASSETS or params["to"] == asset):
            raise ValueError(f"INVALID: unknown or same target asset {params['to']}")
        with self._lock:
            # a compensation is keyed by the record it reverses: one decision may undo several references
            key = (json.dumps([req.get("decision"), skill, params.get("ref")]) if skill in COMPENSATION_SKILLS
                   else json.dumps([req.get("decision"), skill])) if req.get("decision") else None
            fingerprint = json.dumps({k: req.get(k) for k in ("decision", "option", "skill", "asset", "params")}, sort_keys=True)
            if key in self._done:
                prior = self._done[key]
                if prior["fingerprint"] != fingerprint:
                    raise ValueError("idempotency conflict: decision/skill already executed with different input")
                return copy.deepcopy(prior["tx"])
            before = copy.deepcopy(self._affected(skill, asset, params.get("ref") or params.get("order")))   # A103: row before (update-type skills)
            ref, detail = self._apply(skill, asset, params, req)
            after = copy.deepcopy(self._affected(skill, asset, ref))
            tx = {"id": _id("TX"), "t": _now(), "system": SKILLS[skill], "skill": skill, "ref": ref, "detail": detail,
                  "asset": asset, "decision": req.get("decision"), "option": req.get("option"), "by": req.get("by"),
                  "compensates": req.get("compensates") if skill in COMPENSATION_SKILLS else None,
                  "before": before if skill in ("skill:reallocate-production",) or skill in COMPENSATION_SKILLS else None, "after": after}
            self._tx.insert(0, tx)
            del self._tx[300:]
            if key:
                self._done[key] = {"fingerprint": fingerprint, "tx": tx}
            self._save()
            return tx

    def _affected(self, skill: str, asset: str, ref: str | None) -> dict | None:
        """A103 (product audit_events before/after): the one business row an execution creates or changes, found the way
        the ledger refers to it. Same meaning as ent.exec_skill's v_before/v_after (migration 19)."""
        s = self._s
        if skill in ("skill:reallocate-production", "skill:restore-production"):
            return next((o for o in s["mes"]["orders"] if (o["order_id"] == ref) or (ref is None and o["asset"] == asset)), None)
        if skill in ("skill:schedule-maintenance", "skill:cancel-work-order"):
            return next((w for w in s["cmms"]["work_orders"] if w["id"] == ref), None)
        if skill in ("skill:procure-part", "skill:cancel-purchase-request"):
            return next((p for p in s["erp"]["purchase_requests"] if p["id"] == ref), None)
        if skill in ("skill:hold-lot", "skill:release-hold"):
            return next((h for h in s["qms"]["holds"] if h["lot"] == ref), None)
        if skill == "skill:release-lot":
            return next((h for h in s["qms"]["releases"] if h["lot"] == ref), None)
        if skill == "skill:substitute-shipment":
            return next((x for x in s["erp"]["shipments"] if x["id"] == ref), None)
        if skill == "skill:demand-control":
            return s["ems"]["actions"][0] if s["ems"]["actions"] else None
        return None

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
        if skill in COMPENSATION_SKILLS:
            return self._compensate(skill, params)
        raise ValueError(skill)

    def _compensate(self, skill: str, params: dict) -> tuple[str, str]:
        """Reverse exactly one forward record by its reference, only from the state the forward transaction left."""
        s = self._s
        ref = params.get("ref")
        if not ref:
            raise ValueError(f"{skill} needs the reference of the record to reverse (params.ref)")
        if skill == "skill:cancel-work-order":
            wo = next((w for w in s["cmms"]["work_orders"] if w["id"] == ref), None)
            if wo is None:
                raise ValueError(f"no such work order {ref}")
            if wo["status"] != "배정됨":
                raise ValueError(f"work order {ref} cannot be cancelled in status {wo['status']}")
            wo.update(status=CANCELLED, cancelled_at=_now())
            return ref, f"{wo['asset']} 작업지시 {ref} 취소 ({wo['task']})"
        if skill == "skill:cancel-purchase-request":
            pr = next((p for p in s["erp"]["purchase_requests"] if p["id"] == ref), None)
            if pr is None:
                raise ValueError(f"no such purchase request {ref}")
            if pr["status"] != "승인됨 → 발주":
                raise ValueError(f"purchase request {ref} cannot be cancelled in status {pr['status']}")
            pr.update(status=CANCELLED, cancelled_at=_now())
            return ref, f"구매요청 {ref} 취소 ({pr['part']} — {pr['supplierName']})"
        if skill == "skill:restore-production":
            order = next((o for o in s["mes"]["orders"] if o["order_id"] == ref), None)
            if order is None or not order.get("moved_from"):
                raise ValueError(f"order {ref} has no reallocation to restore")
            previous, moved_from = order["asset"], order["moved_from"]
            order.update(asset=moved_from, moved_from=None)
            return ref, f"{ref} {previous} → {moved_from} 원복"
        if skill == "skill:release-hold":
            hold = next((h for h in s["qms"]["holds"] if h["lot"] == ref), None)
            if hold is None:
                raise ValueError(f"no hold on lot {ref}")
            if hold["status"] != "격리 · 전수검사 대기":
                raise ValueError(f"lot {ref} hold cannot be released in status {hold['status']}")
            hold.update(status="격리 해제", released_at=_now())
            return ref, f"로트 {ref} 격리 해제"
        raise ValueError(skill)

    def transactions(self, decision: str | None = None) -> list[dict]:
        with self._lock:
            if decision is not None:
                # The display feed is capped at 300; the idempotency ledger is
                # durable and complete for requests carrying this decision ID.
                return copy.deepcopy([item['tx'] for item in self._done.values()
                                      if item['tx'].get('decision') == decision])
            return list(self._tx)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._s)
