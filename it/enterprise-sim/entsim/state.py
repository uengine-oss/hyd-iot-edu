"""Write side of the mock enterprise systems: what happens in ERP/MES/CMMS/QMS/EMS when the L9 process executes an
approved agent skill. Only the process service calls this (the agent has no write access to enterprise systems)."""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
import secrets
import threading
from datetime import datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))

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
# C2 (확정 TODO C): 승인 뒤 실행 부품이 부르는 업무 거래 + 수업 원인 버튼(예비품 출고). ent.exec_skill(migration 20261009000045)과 같은 규칙.
# 되돌리기 계약이 없는 거래다(입고 · 정비 완료는 실물이 움직였고, 일정 · 기록 · 출고는 새 기록으로 바로잡는다) — effect_compensation 이 사유를 보인다.
C2_SKILLS = {"skill:receive-goods": "sys:erp", "skill:complete-maintenance": "sys:cmms", "skill:calendar-entry": "sys:cmms",
             "skill:record-case": "sys:cmms", "skill:issue-spare": "sys:erp"}
C2_IRREVERSIBLE = {"skill:receive-goods": "입고 · 검수는 실물이 창고에 들어와 되돌릴 수 없다(반품은 별도 절차)",
                   "skill:complete-maintenance": "정비는 현장에서 이미 수행되어 되돌릴 수 없다",
                   "skill:calendar-entry": "일정은 공지된 뒤라 취소 일정을 새로 등록한다",
                   "skill:record-case": "처리 건 기록은 이력이라 지우지 않고 정정 기록을 남긴다",
                   "skill:issue-spare": "출고된 예비품은 반납 입고로 되돌린다(수업은 재고 초기화)"}
SKILLS.update(C2_SKILLS)
SKILL_NAMES.update({"skill:receive-goods": "입고 · 검수", "skill:complete-maintenance": "정비 완료 · 부품 소모",
                    "skill:calendar-entry": "CMMS 일정 등록", "skill:record-case": "처리 건 기록", "skill:issue-spare": "예비품 출고"})
SKILLS.update(COMPENSATION_SKILLS)
CANCELLED = "취소"
PO_OPEN = "승인됨 → 발주"
PO_RECEIVED = "입고 완료"


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
                self._c2_defaults()

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
            self._c2_defaults()
            self._save()

    # ---------------------------------------------------------------- C2: 예비품 재고 · 입고 · 일정 · 기록
    def _c2_defaults(self) -> None:
        """C2 칸이 없는 옛 저장 상태도 같은 모양으로 맞춘다(재고는 기준값에서 시작)."""
        s = self._s
        s["erp"].setdefault("spare_stock", {p: {"part_no": p, "on_hand": b["on_hand"], "reserved": b["reserved"], "on_order": 0,
                                                "reorder_point": b["reorder_point"], "target_stock": b["target_stock"],
                                                "reserved_for": b["reserved_for"], "below_since": None}
                                            for p, b in data.SPARE_BASE.items()})
        s["erp"].setdefault("stock_movements", [])
        s["erp"].setdefault("goods_receipts", [])
        s["cmms"].setdefault("calendar", [])
        s["cmms"].setdefault("case_records", [])

    @staticmethod
    def _stock_view(row: dict) -> dict:
        avail = row["on_hand"] - row["reserved"]
        return dict(row, available=avail, need_qty=max(row["target_stock"] - avail - row["on_order"], 0),
                    below_reorder_point=avail < row["reorder_point"], name=data.SPARE_BASE.get(row["part_no"], {}).get("name"))

    def _move(self, part: str, kind: str, qty: int, asset, ref, by, reason) -> None:
        row = self._s["erp"]["spare_stock"][part]
        avail = row["on_hand"] - row["reserved"]
        row["below_since"] = (row["below_since"] or _now()) if avail < row["reorder_point"] else None
        self._s["erp"]["stock_movements"].insert(0, {"part_no": part, "kind": kind, "qty": qty, "asset": asset, "ref": ref, "by_whom": by,
                                                     "reason": reason, "on_hand_after": row["on_hand"], "available_after": avail, "at": _now()})
        del self._s["erp"]["stock_movements"][200:]

    def spare_stock(self, part: str | None = None) -> dict:
        with self._lock:
            self._c2_defaults()
            rows = [self._stock_view(r) for p, r in sorted(self._s["erp"]["spare_stock"].items()) if part in (None, p)]
            if part is not None and not rows:
                raise KeyError(part)
            moves = [m for m in self._s["erp"]["stock_movements"] if part in (None, m["part_no"])][:20]
            return {"system": "ERP", "facts": copy.deepcopy(rows[0]) if rows else None, "records": copy.deepcopy(rows),
                    "movements": copy.deepcopy(moves), "as_of": _now()}

    def reset_spare_stock(self, part: str | None = None) -> dict:
        with self._lock:
            self._c2_defaults()
            for p, b in data.SPARE_BASE.items():
                if part not in (None, p):
                    continue
                row = self._s["erp"]["spare_stock"][p]
                delta = b["on_hand"] - row["on_hand"]
                row.update(on_hand=b["on_hand"], reserved=b["reserved"], on_order=0, below_since=None)
                self._move(p, "RESET", delta, None, "RESET", "instructor", "수업 초기화")
            self._save()
        return self.spare_stock(part)

    def purchase_order(self, ref: str) -> dict:
        with self._lock:
            pr = next((p for p in self._s["erp"]["purchase_requests"] if p["id"] == ref), None)
            if pr is None:
                raise KeyError(ref)
            grs = [g for g in self._s["erp"].get("goods_receipts", []) if g["pr_id"] == ref]
            return {"system": "ERP", "facts": copy.deepcopy(pr), "records": copy.deepcopy(grs)}

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
            self._c2_defaults()
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
        if skill == "skill:receive-goods":
            return next((g for g in s["erp"]["goods_receipts"] if g["id"] == ref), None)
        if skill == "skill:complete-maintenance":
            return next((w for w in s["cmms"]["work_orders"] if w["id"] == ref), None)
        if skill == "skill:calendar-entry":
            return next((c for c in s["cmms"]["calendar"] if c["id"] == ref), None)
        if skill == "skill:record-case":
            return next((c for c in s["cmms"]["case_records"] if c["id"] == ref), None)
        if skill == "skill:issue-spare":
            move = next((m for m in s["erp"]["stock_movements"] if m.get("ref") == ref), None)
            return s["erp"]["spare_stock"].get(move["part_no"]) if move else None
        return None

    def _apply(self, skill: str, asset: str, params: dict, req: dict) -> tuple[str, str]:
        s = self._s
        if skill == "skill:schedule-maintenance":
            when, window_id, starts_at = params.get("window"), None, params.get("window_starts_at")
            if params.get("window_id"):                     # C2: 승인된 정비창 id → 라벨 · 시작 시각 (ent.exec_skill 과 같은 검사)
                win = next((w for w in data.next_windows(asset, 14) if w["id"] == params["window_id"]), None)
                if win is None:
                    raise ValueError(f"INVALID: unknown maintenance window {params['window_id']} for {asset}")
                window_id, starts_at = win["id"], win["starts_at"]
                when = when or f"{win['label']} {datetime.fromisoformat(win['starts_at']).astimezone(_KST):%m-%d %H:%M}"
            when = when or ("야간 정비창" if "derate" in str(req.get("option")) else "즉시")
            wo = {"id": _id("WO"), "asset": asset, "task": params.get("task", "쿨러 핀 세척 (SOP-COOL-02)"), "window": when, "status": "배정됨",
                  "window_id": window_id, "window_starts_at": starts_at}
            s["cmms"]["work_orders"].insert(0, wo)
            return wo["id"], f"{asset} {wo['task']} — {when}"
        if skill == "skill:receive-goods":
            pr = next((p for p in s["erp"]["purchase_requests"] if p["id"] == params.get("ref")), None)
            if pr is None:
                raise ValueError(f"INVALID: no such purchase request {params.get('ref')}")
            if not pr.get("qty"):
                raise ValueError(f"INVALID: purchase request {pr['id']} has no quantity to receive")
            if pr["status"] != PO_OPEN:
                raise ValueError(f"INVALID: purchase request {pr['id']} cannot be received in status {pr['status']}")
            inspection = params.get("inspection") or "합격"
            gr = {"id": _id("GR"), "pr_id": pr["id"], "part_no": pr.get("part_no"), "qty": pr["qty"],
                  "lot": params.get("lot") or f"LOT-{datetime.now():%y%m%d}-{secrets.token_hex(2).upper()[:3]}",
                  "inspection": inspection, "decision_id": req.get("decision"), "received_at": _now()}
            s["erp"]["goods_receipts"].insert(0, gr)
            pr.update(status=PO_RECEIVED, received_at=gr["received_at"])
            row = s["erp"]["spare_stock"].get(pr.get("part_no"))
            if row is not None:
                row["on_hand"] += pr["qty"]
                row["on_order"] = max(row["on_order"] - pr["qty"], 0)
                self._move(pr["part_no"], "RECEIPT", pr["qty"], asset, gr["id"], req.get("by"), f"발주 {pr['id']} 입고")
            return gr["id"], f"{pr['part']} {pr['qty']}개 입고 · 검수 {inspection} (발주 {pr['id']}, 로트 {gr['lot']})"
        if skill == "skill:complete-maintenance":
            wo = next((w for w in s["cmms"]["work_orders"] if w["id"] == params.get("ref")), None)
            if wo is None:
                raise ValueError(f"INVALID: no such work order {params.get('ref')}")
            if wo["status"] != "배정됨":
                raise ValueError(f"INVALID: work order {wo['id']} cannot be completed in status {wo['status']}")
            wo.update(status="완료", completed_at=_now())
            std = next((t for t in data._TASKS if t["sop"] == params.get("sop")), None)
            used = ""
            if std and std.get("part_no") and std.get("part_qty") and std["part_no"] in s["erp"]["spare_stock"]:
                row = s["erp"]["spare_stock"][std["part_no"]]
                row["on_hand"] = max(row["on_hand"] - std["part_qty"], 0)
                self._move(std["part_no"], "CONSUME", std["part_qty"], wo["asset"], wo["id"], req.get("by"), f"{params.get('sop')} 정비 소모")
                used = f" — {std['part_no']} {std['part_qty']}개 소모"
            return wo["id"], f"{wo['asset']} 작업지시 {wo['id']} 완료 ({wo['task']}){used}"
        if skill == "skill:calendar-entry":
            title = params.get("title") or "정비 일정"
            cal = {"id": _id("CAL"), "asset": asset, "title": title, "starts_at": params.get("starts_at") or _now(),
                   "duration_h": params.get("duration_h"), "wo_ref": params.get("wo_ref"), "note": params.get("note"),
                   "decision_id": req.get("decision"), "created_at": _now()}
            s["cmms"]["calendar"].insert(0, cal)
            return cal["id"], f"{asset} 일정 등록 — {title}"
        if skill == "skill:record-case":
            title = params.get("title") or "처리 건 기록"
            rec = {"id": _id("CASE"), "asset": asset, "title": title, "body": params.get("body"), "proc_inst_id": params.get("proc_inst_id"),
                   "decision_id": req.get("decision"), "created_at": _now()}
            s["cmms"]["case_records"].insert(0, rec)
            return rec["id"], f"처리 건 기록 — {title}"
        if skill == "skill:issue-spare":
            part, qty = params.get("part_no") or "P-PMP-SEAL", int(params.get("qty") or 1)
            row = s["erp"]["spare_stock"].get(part)
            if row is None:
                raise ValueError(f"INVALID: {part} is not a managed spare part")
            if qty <= 0:
                raise ValueError("INVALID: issue quantity must be positive")
            if row["on_hand"] < qty:
                raise ValueError(f"INVALID: only {row['on_hand']} of {part} on hand")
            row["on_hand"] -= qty
            ref = _id("GI")
            reason = params.get("reason") or "예비품 출고"
            self._move(part, "ISSUE", qty, asset, ref, req.get("by"), reason)
            return ref, f"{part} {qty}개 출고 ({reason}) — 가용 {row['on_hand'] - row['reserved']} / 재주문점 {row['reorder_point']}"
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
            pr = {"id": _id("PR"), "part": part, "supplier": sup, "supplierName": name, "asset": asset, "status": PO_OPEN}
            if params.get("part_no"):                       # C2: 수량 · 금액이 있는 발주 — 견적 · AVL · 금액 재확인 (ent.exec_skill 과 같음)
                part_no, qty = params["part_no"], params.get("qty")
                if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
                    raise ValueError("INVALID: purchase quantity must be positive")
                quote = next((q for q in data.quote_rows(part_no) if q["supplier"] == sup), None)
                if quote is None:
                    raise ValueError(f"INVALID: supplier {sup} has no quote for {part_no}")
                if not quote["avl"]:
                    raise ValueError(f"INVALID: supplier {sup} is not on the approved vendor list (AVL)")
                if "amount" in params and float(params["amount"]) != quote["price"] * qty:
                    raise ValueError(f"INVALID: approved amount {params['amount']} differs from quote {qty} x {quote['price']}")
                part = data.SPARE_BASE.get(part_no, {}).get("name") or part
                pr.update(part=part, part_no=part_no, qty=qty, unit_price=quote["price"], amount=quote["price"] * qty, lead_d=quote["lead_d"],
                          expected_at=(datetime.now(timezone.utc) + timedelta(days=quote["lead_d"])).isoformat(), received_at=None)
                if part_no in s["erp"]["spare_stock"]:
                    s["erp"]["spare_stock"][part_no]["on_order"] += qty
                s["erp"]["purchase_requests"].insert(0, pr)
                return pr["id"], f"{part} {qty}개 발주 — {name}, {pr['amount']:g}만원, 리드타임 {quote['lead_d']}일"
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
