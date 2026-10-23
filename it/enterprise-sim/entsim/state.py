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
    "skill:schedule-maintenance-scoped": "sys:cmms",
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
C2_COMPENSATION_SKILLS = {"skill:cancel-maintenance-scoped": "sys:cmms"}
C2_INVERSE_OF = {"skill:schedule-maintenance-scoped": "skill:cancel-maintenance-scoped"}
ALL_COMPENSATION_SKILLS = {**COMPENSATION_SKILLS, **C2_COMPENSATION_SKILLS}
ALL_INVERSE_OF = {**INVERSE_OF, **C2_INVERSE_OF}
# Korean display names of the business skills (system of record for the portal's names.json — A150). The forward
# names come from the v1 enterprise seed (it/neo4j/v1/seed_enterprise.cypher); the v2 graph does not carry these skills.
SKILL_NAMES = {
    "skill:cancel-maintenance-scoped": "등록한 원문 정비 범위 전체 취소",
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
C2_SKILLS = {"skill:receive-goods": "sys:erp", "skill:complete-maintenance": "sys:cmms", "skill:issue-spare": "sys:erp",
             "skill:reschedule-maintenance": "sys:cmms",
             # 시나리오 B: 운전시간 계수기(운전시간 진행 · 시운전 통과 뒤 리셋), 시나리오 C: 공급사 납기 지연 통보(입고 대기 흐름의 지연 가지)
             "skill:pm-advance": "sys:cmms", "skill:pm-reset": "sys:cmms", "skill:delay-delivery": "sys:scm"}
C2_IRREVERSIBLE = {"skill:receive-goods": "입고 · 검수는 실물이 창고에 들어와 되돌릴 수 없다(반품은 별도 절차)",
                   "skill:reschedule-maintenance": "정비 일정은 기존 오더 상태와 기한을 다시 검토한 새 일정 변경으로 정정한다",
                   "skill:complete-maintenance": "정비는 현장에서 이미 수행되어 되돌릴 수 없다",
                   "skill:issue-spare": "출고된 예비품은 반납 입고로 되돌린다(수업은 재고 초기화)",
                   "skill:pm-advance": "운전시간은 흘러간 시간이라 되돌리지 않는다(수업은 계수기 초기화)",
                   "skill:pm-reset": "정기 정비가 끝나 다음 주기가 시작됐다(정정은 새 기록으로)",
                   "skill:delay-delivery": "공급사가 알린 납기 변경이라 되돌리지 않는다"}
SKILLS.update(C2_SKILLS)
SKILL_NAMES.update({"skill:receive-goods": "입고 · 검수", "skill:complete-maintenance": "정비 완료 · 부품 소모",
                    "skill:schedule-maintenance-scoped": "원문 패키지와 설비 범위 정비 오더 등록",
                    "skill:reschedule-maintenance": "기존 PM 오더 일정 변경",
                    "skill:issue-spare": "예비품 출고",
                    "skill:pm-advance": "운전시간 계수기 진행", "skill:pm-reset": "운전시간 계수기 리셋 · 다음 기한 기록",
                    "skill:delay-delivery": "공급사 납기 지연 통보"})
SKILLS.update(ALL_COMPENSATION_SKILLS)
CANCELLED = "취소"
PO_OPEN = "승인됨 → 발주"
PO_RECEIVED = "입고 완료"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _now_us() -> str:
    """created_at 처럼 순서를 가르는 시각(마이크로초) — 같은 초에 생긴 로트 격리 · 출하 승인도 최근 것부터 놓인다."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _id(prefix: str) -> str:
    """실행 기록 · 오더 · 요청 번호: 접두-월일-16진 12자리(48비트). 4자리(16비트)는 같은 날 수백 건에서 겹쳐
    PG 는 기본키 위반으로 승인 실행이 거절되고 메모리는 다른 오더를 집었다(점검 E7, ent.new_ref 와 같은 꼴)."""
    return f"{prefix}-{datetime.now():%m%d}-{secrets.token_hex(6).upper()}"


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
                self._archive = saved.get("archive", [])
                if saved.get("anchor"):             # 시나리오 시각 기준점도 저장 상태와 같이 — 재시작이 기준점을 옮기지 않게(점검 E8)
                    data.reanchor(datetime.fromisoformat(saved["anchor"]))
                self._c2_defaults()

    def _save(self):
        if self._db:
            with self._db:
                self._db.execute("INSERT OR REPLACE INTO state VALUES (1,?)",
                    (json.dumps({"state": self._s, "transactions": self._tx, "done": self._done, "archive": self._archive,
                                "anchor": data.scenario_start().isoformat()}),))

    # 수업 초기화가 옮겨 두는 실행 기록(ent.execution_archive 와 같은 뜻) — 표 이름 → 이 상태 안의 경로, 따라가기 키
    _ARCHIVED = (("work_orders", ("cmms", "work_orders"), "id"), ("purchase_requests", ("erp", "purchase_requests"), "id"),
                 ("shipments", ("erp", "shipments"), "id"), ("goods_receipts", ("erp", "goods_receipts"), "id"),
                 ("lot_holds", ("qms", "holds"), "lot"), ("lot_releases", ("qms", "releases"), "lot"), ("ems_actions", ("ems", "actions"), None),
                 # 재고 이동 · 운전시간 원장도 보관 뒤 비운다(ent.reset_executions, migration 061 — 점검 E11)
                 ("stock_movements", ("erp", "stock_movements"), "ref"), ("pm_counter_log", ("cmms", "pm_log"), "ref"))

    def _archive_executions(self) -> list[dict]:
        """초기화 전 실행 기록을 보관 목록으로 옮긴다(Supabase ent.reset_executions 와 같은 규칙 — 지우지 않고 보관)."""
        old = getattr(self, "_archive", [])
        if not hasattr(self, "_s"):
            return old
        reset_no = 1 + max((a["reset_no"] for a in old), default=0)
        rows = [{"reset_no": reset_no, "table": "transactions", "ref": t.get("ref"), "decision_id": t.get("decision"), "row": t} for t in self._tx]
        for table, (sys_key, key), ref in self._ARCHIVED:
            for r in self._s.get(sys_key, {}).get(key, []):
                rows.append({"reset_no": reset_no, "table": table, "ref": r.get(ref) if ref else None, "decision_id": r.get("decision"), "row": r})
        return old + copy.deepcopy(rows)

    def archive(self, ref: str | None = None) -> dict:
        with self._lock:
            return {"records": copy.deepcopy([a for a in reversed(self._archive) if ref in (None, a["ref"], a["decision_id"])])}

    def reset(self) -> None:
        """업무 전체 초기화(ent.reset_executions 와 같은 규칙): 실행 기록 · 원장을 보관하고 비운 뒤, 재고 · 계수기를 C · B [초기화]와 같은
        함수로 시작값에 — 그 함수가 남기는 RESET · BASE 한 줄씩으로 원장이 다시 시작한다. 처음 만들 때(이전 상태 없음)는 시작값 그대로다."""
        with getattr(self, "_lock", threading.Lock()):
            old = getattr(self, "_s", None)
            self._archive = self._archive_executions()
            self._tx: list[dict] = []
            self._done = {}
            self._s = {
                "mes": {"orders": [dict(o, asset=a, moved_from=None) for a, o in copy.deepcopy(data._ORDERS).items()]},
                "cmms": {"work_orders": []},
                "erp": {"purchase_requests": [], "shipments": []},
                "qms": {"holds": [], "releases": []},
                "ems": {"actions": []},
            }
            if old is not None:
                self._s["erp"]["spare_stock"] = old.get("erp", {}).get("spare_stock", {})
                self._s["cmms"]["pm_counters"] = old.get("cmms", {}).get("pm_counters", {})
            self._c2_defaults()
            if old is not None:
                self._reset_stock(None)
                self._reset_counters(None)
            self._save()

    def reanchor(self, now: datetime | None = None) -> None:
        """시나리오 시각 기준점을 지금으로(ent.reanchor_scenario_times) — 저장 상태에도 남긴다."""
        with self._lock:
            data.reanchor(now)
            self._save()

    # ---------------------------------------------------------------- C2: 예비품 재고 · 입고 · 일정 · 기록
    def _c2_defaults(self) -> None:
        """C2 칸이 없는 옛 저장 상태도 같은 모양으로 맞춘다(재고는 기준값에서 시작)."""
        s = self._s
        # B-ERP-20261012-v1: migration 057과 같이 없는 초기 품목만 추가한다.
        # 저장된 실물·예약·발주와 다른 현재 행은 그대로 보존한다(수업 reset과 구별).
        stocks = s["erp"].setdefault("spare_stock", {})
        for p, b in data.SPARE_BASE.items():
            stocks.setdefault(p, {"part_no": p, "on_hand": b["on_hand"], "reserved": b["reserved"], "on_order": 0,
                                  "reorder_point": b["reorder_point"], "target_stock": b["target_stock"],
                                  "reserved_for": b["reserved_for"],
                                  # C3: 시작값이 재주문점 아래면(씰 키트) 시작부터 '재고 보충 필요'
                                  "below_since": _now() if b["on_hand"] - b["reserved"] < b["reorder_point"] else None})
        s["erp"].setdefault("stock_movements", [])
        s["erp"].setdefault("goods_receipts", [])
        due_h = data.PM_SETTINGS["interval_h"] - data.PM_SETTINGS["notice_h"]
        s["cmms"].setdefault("pm_counters", {a: dict(b, cycle=1, last_done_at=None, due_since=_now() if b["since_pm_h"] >= due_h else None,
                                                     plan_wo=None, plan_window=None, planned_at=None, updated_at=_now())
                                             for a, b in data.PM_BASE.items()})
        s["cmms"].setdefault("pm_log", [])

    @staticmethod
    def _available(row: dict) -> int:
        """가용 재고 = 현재고 − 정비 예약 + 입고 예정 (PR-07 7.2, 온톨로지 in:spare-gap 의 정의)."""
        return row["on_hand"] - row["reserved"] + row["on_order"]

    @classmethod
    def _stock_view(cls, row: dict) -> dict:
        avail = cls._available(row)
        return dict(row, available=avail, spare_gap=avail - row["reorder_point"], need_qty=max(row["target_stock"] - avail, 0),
                    need_by_days=data.SPARE_BASE.get(row["part_no"], {}).get("need_by_days"),
                    below_reorder_point=avail < row["reorder_point"], name=data.SPARE_BASE.get(row["part_no"], {}).get("name"))

    def _move(self, part: str, kind: str, qty: int, asset, ref, by, reason) -> None:
        row = self._s["erp"]["spare_stock"][part]
        avail = self._available(row)
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
            self._reset_stock(part)
            self._save()
        return self.spare_stock(part)

    def _pm_holds(self, asset: str | None = None) -> list[tuple[dict, dict, str]]:
        """정기 정비 오더(시나리오 B)가 아직 잡고 있는 부품: (오더, 부품 줄, 'reserve' | 'issue'). B [초기화]가 되돌리는 것과 같은 범위
        (ent.pm_part_reservations released_at is null · 오더 배정됨)."""
        held = []
        for o in self._s["cmms"]["work_orders"]:
            if o.get("status") != "배정됨" or o.get("reservations_released") or asset not in (None, o.get("asset")):
                continue
            held += [(o, x, "reserve") for x in o.get("reserved_parts") or []]
            held += [(o, x, "issue") for x in o.get("issued_parts") or []]
        return held

    def _reset_stock(self, part: str | None) -> None:
        """C [초기화]: 이 부품의 열린 발주를 취소로 닫고, 재고를 시작값으로 — 단 아직 진행 중인 B 정비 오더가 잡은 수량은 남긴다
        (ent.reset_spare_stock 과 같은 규칙). 예전에는 행 전체를 시작값으로 덮어 B 예약이 장부에서 사라지고 발주는 열린 채였다(점검 E1 · E3)."""
        s = self._s
        holds = self._pm_holds()
        todo = []
        for p, b in data.SPARE_BASE.items():               # 먼저 모두 검사 — 하나라도 어긋나면 아무것도 바꾸지 않는다
            if part not in (None, p):
                continue
            held_reserved = sum(x["qty"] for _o, x, e in holds if x["part_no"] == p and e == "reserve")
            held_issued = sum(x["qty"] for _o, x, e in holds if x["part_no"] == p and e == "issue")
            if b["on_hand"] - held_issued < 0:
                raise ValueError(f"INVALID: {p} 실물 {held_issued}개가 진행 중인 정비 오더에 출고돼 있어 재고를 시작값으로 되돌릴 수 없습니다(B [초기화] 먼저)")
            todo.append((p, b, held_reserved, held_issued))
        for p, b, held_reserved, held_issued in todo:
            row = s["erp"]["spare_stock"][p]
            closed = [pr for pr in s["erp"]["purchase_requests"] if pr.get("part_no") == p and pr.get("qty") and pr["status"] == PO_OPEN]
            for pr in closed:
                pr.update(status=CANCELLED, cancelled_at=_now())
            delta = b["on_hand"] - held_issued - row["on_hand"]
            open_qty = sum(pr["qty"] for pr in s["erp"]["purchase_requests"] if pr.get("part_no") == p and pr.get("qty") and pr["status"] == PO_OPEN)
            row.update(on_hand=b["on_hand"] - held_issued, reserved=b["reserved"] + held_reserved, on_order=open_qty, below_since=None)
            for pr in closed:
                self._move(p, "CANCEL", pr["qty"], pr.get("asset"), pr["id"], "instructor", f"수업 초기화 — 발주 {pr['id']} 취소")
            self._move(p, "RESET", delta, None, "RESET", "instructor", "수업 초기화")   # 시작값이 재주문점 아래면 이탈 시각을 바로 남긴다

    def _release_pm_holds(self, asset: str | None) -> None:
        """B [초기화]: 아직 부품을 잡은 정기 정비 오더를 취소로 닫고, 그 오더가 잡은 수량만 되돌린다(예약 −, 즉시 출고면 실물 +).
        부품 행 전체를 시작값으로 덮으면 같은 부품을 쓰는 C 발주의 입고 예정이 지워졌다(점검 E2, ent.reset_pm_counters 와 같은 규칙)."""
        stocks = self._s["erp"]["spare_stock"]
        holds = self._pm_holds(asset)
        totals: dict[tuple[str, str], list] = {}
        for o, x, effect in holds:
            entry = totals.setdefault((x["part_no"], effect), [0, []])
            entry[0] += x["qty"]
            if o["id"] not in entry[1]:
                entry[1].append(o["id"])
        for (p, effect), (qty, _orders) in totals.items():     # 먼저 모두 검사 — 하나라도 어긋나면 아무것도 바꾸지 않는다
            if p not in stocks:
                raise ValueError(f"INVALID: {p} is not a managed spare part")
            if effect == "reserve" and stocks[p]["reserved"] < qty:
                raise ValueError(f"INVALID: {p} 예약 {stocks[p]['reserved']}개가 정비 오더가 잡은 {qty}개보다 적습니다(재고 장부 확인 필요)")
        for o in {id(o): o for o, _x, _e in holds}.values():
            o.update(status=CANCELLED, cancelled_at=_now(), reservations_released=True)
        for (p, effect), (qty, orders) in sorted(totals.items()):
            row = stocks[p]
            if effect == "reserve":
                row["reserved"] -= qty
            else:
                row["on_hand"] += qty
            row["updated_at"] = _now()
            self._move(p, "RESET", qty if effect == "issue" else 0, None, "RESET", "instructor",
                       f"수업 초기화 — 정비 오더 {', '.join(orders)} " + ("예약 해제" if effect == "reserve" else "출고 반납"))

    # ---------------------------------------------------------------- C2 시나리오 B: 정기 정비 계획 · 운전시간 계수기
    def _pm_rows(self) -> list[dict]:
        counters = self._s["cmms"]["pm_counters"]
        spare = self._s["erp"]["spare_stock"].get(data.PM_KIT["part_no"])
        view = self._stock_view(spare) if spare else None
        rows=[data.pm_row(a, counters[a], view, counters) for a in sorted(counters)]
        for row in rows:
            row['service_position']=counters[row['asset']].get('service_position')
            row['package_semantics']='base_interval_configuration'
            row['configured_base_package']=row['package']
            order=next((w for w in self._s['cmms']['work_orders'] if w.get('id')==row.get('pm_planned_wo')),None)
            row['selected_service']=copy.deepcopy(order.get('package')) if order and order.get('maintenance_plan') else None
            row['existing_pm_order']=copy.deepcopy(order) if order else None
        return rows

    def pm_status(self, asset: str | None = None) -> dict:
        """CMMS: 정기 정비 계획 · 운전시간 계수기(설비별 한 행, ent.pm_status 와 같은 칸). asset 없으면 전부."""
        with self._lock:
            self._c2_defaults()
            rows = [r for r in self._pm_rows() if asset in (None, r["asset"])]
            if asset is not None and not rows:
                raise KeyError(asset)
            log = [m for m in self._s["cmms"]["pm_log"] if asset in (None, m["asset"])][:20]
            for row in rows:
                row['pm_cycle'] = row['cycle']
                row['existing_pm_order'] = copy.deepcopy(next((w for w in self._s['cmms']['work_orders']
                    if w.get('id') == row.get('pm_planned_wo') and w.get('asset') == row['asset']),None))
            return {"system": "CMMS", "facts": copy.deepcopy(rows[0]) if rows else None, "records": copy.deepcopy(rows),
                    "log": copy.deepcopy(log), "settings": dict(data.PM_SETTINGS), "as_of": _now()}

    def _pm_log(self, asset, kind, delta, ref, by, reason) -> None:
        c = self._s["cmms"]["pm_counters"][asset]
        lower = data.PM_SETTINGS["interval_h"] - data.PM_SETTINGS["notice_h"]
        c["due_since"] = (c["due_since"] or _now()) if c["since_pm_h"] >= lower else None
        c["updated_at"] = _now()
        self._s["cmms"]["pm_log"].insert(0, {"asset": asset, "kind": kind, "delta_h": delta, "since_after": c["since_pm_h"],
                                             "total_after": c["total_h"], "cycle": c["cycle"], "ref": ref, "by_whom": by, "reason": reason, "at": _now()})
        del self._s["cmms"]["pm_log"][200:]

    def reset_pm_counters(self, asset: str | None = None) -> dict:
        with self._lock:
            self._c2_defaults()
            # 아직 부품을 잡은 정기 정비 오더를 취소로 닫고 그 오더가 잡은 수량만 되돌린다(ent.reset_pm_counters 와 같은 규칙).
            # 계수기만 되돌리면 다시 연 B가 "도래"인데 부품 가용이 0이라 단독 · 즉시 시행이 재고 부족으로 빠졌다(2026-10-23 라이브).
            self._release_pm_holds(asset)
            self._reset_counters(asset)
            self._save()
        return self.pm_status(asset)

    def _reset_counters(self, asset: str | None) -> None:
        """운전시간 계수기 · 이번 회차 오더 표시를 시작값으로, 원장에 BASE(되돌린 시간)를 남긴다(ent.reset_pm_counters 의 계수기 부분)."""
        for a, b in data.PM_BASE.items():
            if asset not in (None, a):
                continue
            c = self._s["cmms"]["pm_counters"][a]
            delta = b["since_pm_h"] - c["since_pm_h"]
            c.update(since_pm_h=b["since_pm_h"], total_h=b["total_h"], cycle=1, last_done_at=None, due_since=None,
                     plan_wo=None, plan_window=None, planned_at=None)
            self._pm_log(a, "BASE", delta, "RESET", "instructor", "수업 초기화")

    def purchase_order(self, ref: str) -> dict:
        with self._lock:
            pr = next((p for p in self._s["erp"]["purchase_requests"] if p["id"] == ref), None)
            if pr is None:
                raise KeyError(ref)
            grs = [g for g in self._s["erp"].get("goods_receipts", []) if g["pr_id"] == ref]
            facts = copy.deepcopy(pr)
            if pr.get("expected_at"):
                facts["expected_in_h"] = data.hours_from_now(datetime.fromisoformat(pr["expected_at"]))
            return {"system": "ERP", "facts": facts, "records": copy.deepcopy(grs)}

    def execute(self, req: dict) -> dict:
        skill = req.get("skill")
        if skill not in SKILLS:
            raise ValueError(f"unknown or non-enterprise skill {skill!r}")
        asset = req.get("asset") or "HYD-01"
        params = req.get("params") or {}
        # A115 (r14 A7, wms `INVALID: unknown sku`; same checks as ent.exec_skill/exec_compensation, migration 22)
        if (req.get("asset") is not None or skill not in ALL_COMPENSATION_SKILLS) and asset not in data.ASSETS:
            raise ValueError(f"INVALID: unknown asset {asset}")
        if skill == "skill:procure-part" and params.get("supplier", "sup:b") not in {x["id"] for x in data._SUPPLIERS}:
            raise ValueError(f"INVALID: unknown supplier {params.get('supplier')}")
        if skill == "skill:reallocate-production" and "to" in params and (params["to"] not in data.ASSETS or params["to"] == asset):
            raise ValueError(f"INVALID: unknown or same target asset {params['to']}")
        with self._lock:
            self._c2_defaults()
            # a compensation is keyed by the record it reverses: one decision may undo several references
            key = (json.dumps([req.get("decision"), skill, params.get("ref")]) if skill in ALL_COMPENSATION_SKILLS
                   else json.dumps([req.get("decision"), skill])) if req.get("decision") else None
            fingerprint = json.dumps({k: req.get(k) for k in ("decision", "option", "skill", "asset", "params")}, sort_keys=True)
            if key in self._done:
                prior = self._done[key]
                if prior["fingerprint"] != fingerprint:
                    raise ValueError("idempotency conflict: decision/skill already executed with different input")
                return copy.deepcopy(prior["tx"])
            rollback = copy.deepcopy((self._s,self._done,self._tx)) if skill in ('skill:reschedule-maintenance','skill:schedule-maintenance-scoped','skill:cancel-maintenance-scoped') else None
            before = copy.deepcopy(self._affected(skill, asset, params.get("ref") or params.get("order")))   # A103: row before (update-type skills)
            try:
                ref, detail = self._apply(skill, asset, params, req)
            except Exception:
                if rollback is not None:self._s,self._done,self._tx=rollback
                raise
            after = copy.deepcopy(self._affected(skill, asset, ref))
            tx = {"id": _id("TX"), "t": _now(), "system": SKILLS[skill], "skill": skill, "ref": ref, "detail": detail,
                  "asset": asset, "decision": req.get("decision"), "option": req.get("option"), "by": req.get("by"),
                  "compensates": req.get("compensates") if skill in ALL_COMPENSATION_SKILLS else None,
                  "before": before if skill in ("skill:reallocate-production","skill:reschedule-maintenance") or skill in ALL_COMPENSATION_SKILLS else None, "after": after}
            self._tx.insert(0, tx)
            del self._tx[300:]
            if key:
                self._done[key] = {"fingerprint": fingerprint, "tx": tx}
            try:
                self._save()
            except Exception:
                if rollback is not None:
                    self._s,self._done,self._tx = rollback
                raise
            return tx

    def _affected(self, skill: str, asset: str, ref: str | None) -> dict | None:
        """A103 (product audit_events before/after): the one business row an execution creates or changes, found the way
        the ledger refers to it. Same meaning as ent.exec_skill's v_before/v_after (migration 19)."""
        s = self._s
        if skill in ('skill:schedule-maintenance-scoped','skill:cancel-maintenance-scoped'):
            first=next((w for w in s['cmms']['work_orders'] if w.get('id')==ref),None)
            if first is None:return None
            orders=[copy.deepcopy(w) for w in s['cmms']['work_orders'] if w.get('scope_group')==first.get('scope_group')]
            return dict(plan=copy.deepcopy(first['maintenance_plan']),orders=[dict(w,ref=w['id']) for w in orders])
        if skill in ("skill:reallocate-production", "skill:restore-production"):
            return next((o for o in s["mes"]["orders"] if (o["order_id"] == ref) or (ref is None and o["asset"] == asset)), None)
        if skill in ("skill:schedule-maintenance", "skill:cancel-work-order", "skill:reschedule-maintenance"):
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
        if skill == "skill:issue-spare":
            move = next((m for m in s["erp"]["stock_movements"] if m.get("ref") == ref), None)
            return s["erp"]["spare_stock"].get(move["part_no"]) if move else None
        if skill in ("skill:pm-advance", "skill:pm-reset"):
            return s["cmms"]["pm_counters"].get(asset)
        if skill == "skill:delay-delivery":
            return next((p for p in s["erp"]["purchase_requests"] if p["id"] == ref), None)
        return None

    def _apply(self, skill: str, asset: str, params: dict, req: dict) -> tuple[str, str]:
        s = self._s
        if skill == 'skill:schedule-maintenance-scoped':
            from hydcommon.maintenance_plan import recheck
            approved=params.get('plan')
            if not req.get('decision') or not req.get('by') or not req.get('option'):
                raise ValueError('INVALID: source maintenance requires approval identity')
            context=dict(asset=asset,records=self._pm_rows(),parts=[self._stock_view(p) for p in s['erp']['spare_stock'].values()])
            recheck(approved,context)
            if approved.get('code')!='WO_CREATE':raise ValueError('INVALID: scheduling requires explicit WO_CREATE plan')
            group=req['decision']+':'+req['option'];orders=[]
            for member in approved['assets']:
                code=member['asset'];counter=s['cmms']['pm_counters'][code]
                if counter.get('plan_wo'):raise ValueError('INVALID: this PM cycle already has a work order')
            for member in approved['assets']:
                code=member['asset'];counter=s['cmms']['pm_counters'][code];win=member['window']
                order=dict(id=_id('WO'),asset=code,task=params.get('task') or member['service']['package_name'],status='배정됨',
                    window=approved['window'].get('label') or ('즉시' if win.get('immediate') else '예정된 정비 시간'),
                    window_id=None if win.get('immediate') else win['id'],window_starts_at=win.get('starts_at'),
                    scope_group=group,maintenance_plan=copy.deepcopy(approved),package=copy.deepcopy(member['service']),
                    stock_effect=approved['stock_effect'],part_allocations=copy.deepcopy(member['parts']),
                    reserved_parts=copy.deepcopy(member['parts']) if approved['stock_effect']=='reserve' else [],
                    issued_parts=copy.deepcopy(member['parts']) if approved['stock_effect']=='issue' else [],reservations_released=False)
                if any(w['id']==order['id'] for w in s['cmms']['work_orders']):raise ValueError('work order identity collision')
                s['cmms']['work_orders'].insert(0,order);orders.append(order)
                counter.update(plan_wo=order['id'],plan_window=order['window'],planned_at=_now(),updated_at=_now())
            for part in approved['parts_totals']:
                stock=s['erp']['spare_stock'][part['part_no']]
                if approved['stock_effect']=='reserve':stock['reserved']+=part['qty']
                elif approved['stock_effect']=='issue':stock['on_hand']-=part['qty']
                else:raise ValueError('INVALID: new maintenance order requires reservation or actual issue')
                stock['updated_at']=_now()
            return orders[0]['id'],'원문 정비 범위 '+', '.join(w['asset'] for w in orders)+' 오더 등록'
        if skill == 'skill:reschedule-maintenance':
            if params.get('plan'):
                from hydcommon.maintenance_plan import recheck
                recheck(params['plan'],dict(asset=asset,records=self._pm_rows(),parts=[self._stock_view(p) for p in s['erp']['spare_stock'].values()]))
            counter = s['cmms']['pm_counters'].get(asset) or {}
            order = next((w for w in s['cmms']['work_orders'] if w.get('id') == counter.get('plan_wo') and w.get('asset') == asset),None)
            row = next((r for r in self._pm_rows() if r['asset'] == asset),{})
            if not req.get('decision') or not req.get('by') or not req.get('option') or not order or order != params.get('expected_order') \
                    or order.get('id') != params.get('ref') or counter.get('cycle') != params.get('cycle') \
                    or order.get('status') != '배정됨' or order.get('completed_at') is not None:
                raise ValueError('INVALID: existing PM order changed or is not this approved cycle plan')
            if not params.get('window_id') or params['window_id'] != row.get('following_window_id') \
                    or row.get('hours_at_following_window') is None \
                    or row['hours_at_following_window'] > row['pm_interval_h']*(1+row['pm_tolerance_pct']/100):
                raise ValueError('INVALID: following maintenance window unknown or beyond PM deadline')
            window = next((w for w in data.next_windows(asset,14) if w['id'] == params['window_id']),None)
            if window is None: raise ValueError('INVALID: target maintenance window missing')
            order.update(window_id=window['id'],window_starts_at=window['starts_at'],window=window['label'])
            counter.update(plan_window=window['label'],planned_at=_now(),updated_at=_now())
            return order['id'],'PM order rescheduled to '+window['id']
        if skill == 'skill:cancel-maintenance-scoped':
            first=next((w for w in s['cmms']['work_orders'] if w.get('id')==params.get('ref')),None)
            if first is None or not first.get('maintenance_plan'):raise ValueError('INVALID: source scoped work order group missing')
            if first.get('stock_effect')=='issue':
                raise ValueError('출고한 부품의 실제 반납 확인 없이 정비 범위 전체 취소를 원상 복구로 기록하지 않습니다')
            forward=next((entry['tx'] for entry in self._done.values() if entry['tx'].get('skill')=='skill:schedule-maintenance-scoped'
                          and entry['tx'].get('ref')==first['id']),None)
            if forward is None or req.get('compensates')!=forward['id']:
                raise ValueError('INVALID: compensation must identify actual original scope transaction')
            orders=[w for w in s['cmms']['work_orders'] if w.get('scope_group')==first['scope_group']]
            if len(orders)!=len(first['maintenance_plan']['assets']):raise ValueError('INVALID: scoped order group incomplete')
            expected={a['asset']:a for a in first['maintenance_plan']['assets']}
            original_orders={o['id']:o for o in (forward.get('after') or {}).get('orders') or []}
            for order in orders:
                counter=s['cmms']['pm_counters'][order['asset']]
                if dict(order,ref=order['id'])!=original_orders.get(order['id']) or order['status']!='배정됨' or order.get('reservations_released') or counter.get('plan_wo')!=order['id'] \
                        or counter['cycle']!=expected[order['asset']]['expected_counter']['cycle']:
                    raise ValueError('INVALID: one scoped order advanced; whole cancellation needs review')
            for part in first['maintenance_plan']['parts_totals']:
                if s['erp']['spare_stock'][part['part_no']]['reserved']<part['qty']:
                    raise ValueError('INVALID: actual scoped part reservations changed')
            for order in orders:
                order.update(status=CANCELLED,cancelled_at=_now(),reservations_released=True)
                s['cmms']['pm_counters'][order['asset']].update(plan_wo=None,plan_window=None,planned_at=None,updated_at=_now())
            for part in first['maintenance_plan']['parts_totals']:
                s['erp']['spare_stock'][part['part_no']]['reserved']-=part['qty']
            return first['id'],'원문 정비 범위 전체 취소'
        if skill == "skill:schedule-maintenance":
            when, window_id, starts_at = params.get("window"), None, params.get("window_starts_at")
            if params.get("window_id"):                     # C2: 승인된 예정된 정비 시간 id → 라벨 · 시작 시각 (ent.exec_skill 과 같은 검사)
                win = next((w for w in data.next_windows(asset, 14) if w["id"] == params["window_id"]), None)
                if win is None:
                    raise ValueError(f"INVALID: unknown maintenance window {params['window_id']} for {asset}")
                window_id, starts_at = win["id"], win["starts_at"]
                when = when or f"{win['label']} {datetime.fromisoformat(win['starts_at']).astimezone(_KST):%m-%d %H:%M}"
            when = when or ("예정된 정비 시간 (야간)" if "derate" in str(req.get("option")) else "즉시")
            wo = {"id": _id("WO"), "asset": asset, "task": params.get("task", "쿨러 핀 세척 (SOP-COOL-02)"), "window": when, "status": "배정됨",
                  "window_id": window_id, "window_starts_at": starts_at}
            s["cmms"]["work_orders"].insert(0, wo)
            # C3 B · C 단순화: 정기 정비 도래 설비에 예정된 정비 시간(window_id)으로 잡힌 작업지시 = 이번 회차 정기 정비 오더(마이그레이션 47 트리거 ent.mark_pm_plan 과 같음)
            c = s["cmms"].get("pm_counters", {}).get(asset)
            if (c is not None and window_id and not c.get("plan_wo")
                    and c["since_pm_h"] >= data.PM_SETTINGS["interval_h"] - data.PM_SETTINGS["notice_h"]):
                c.update(plan_wo=wo["id"], plan_window=when, planned_at=_now())
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
            candidate=next((w for w in s['cmms']['work_orders'] if w.get('id')==params.get('ref')),None)
            if candidate and candidate.get('maintenance_plan'):
                raise ValueError('원문 패키지의 현장 점검·시운전 완료 검증 없이 기본 정비 완료로 대체하지 않습니다')
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
        if skill == "skill:issue-spare":
            # ent.exec_skill 과 같이: 없으면 기본값, 있으면 그 값 그대로(0 · 음수는 거절 — 예전 `or 1` 은 0 을 1개 출고로 바꿨다, 점검 E11)
            part = "P-PMP-SEAL" if params.get("part_no") is None else params["part_no"]
            try:
                qty = 1 if params.get("qty") is None else int(str(params["qty"]).strip())
            except ValueError:
                raise ValueError(f"INVALID: issue quantity must be an integer, got {params['qty']!r}") from None
            if qty <= 0:
                raise ValueError("INVALID: issue quantity must be positive")
            row = s["erp"]["spare_stock"].get(part)
            if row is None:
                raise ValueError(f"INVALID: {part} is not a managed spare part")
            if row["on_hand"] < qty:
                raise ValueError(f"INVALID: only {row['on_hand']} of {part} on hand")
            row["on_hand"] -= qty
            ref = _id("GI")
            reason = params.get("reason") or "예비품 출고"
            self._move(part, "ISSUE", qty, asset, ref, req.get("by"), reason)
            return ref, f"{part} {qty}개 출고 ({reason}) — 가용 {self._available(row)} / 재주문점 {row['reorder_point']}"
        if skill == "skill:pm-advance":                    # 운전시간 진행 (설비 한 대)
            hours = params.get("hours", 300)
            if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not 0 < hours <= 5000:
                raise ValueError("INVALID: hours must be between 0 and 5000")
            c = s["cmms"]["pm_counters"][asset]
            c["since_pm_h"] += hours
            c["total_h"] += hours
            ref = _id("RUN")
            self._pm_log(asset, "ADVANCE", hours, ref, req.get("by"), params.get("reason") or "운전시간 진행")
            return ref, f"{asset} 운전시간 +{hours:g} h — 마지막 정기 정비 뒤 {c['since_pm_h']:g} h / 주기 {data.PM_SETTINGS['interval_h']} h"
        if skill == "skill:pm-reset":                      # 시운전 통과 뒤: 계수기 리셋 · 다음 기한 기록
            planned=s['cmms']['pm_counters'].get(asset,{}).get('plan_wo')
            if any(w.get('id')==planned and w.get('maintenance_plan') for w in s['cmms']['work_orders']):
                raise ValueError('원문 패키지의 실제 완료 기록 없이 정비 차례와 계수기를 리셋하지 않습니다')
            c = s["cmms"]["pm_counters"][asset]
            done = c["since_pm_h"]
            c.update(since_pm_h=0, cycle=c["cycle"] + 1, last_done_at=_now(), plan_wo=None, plan_window=None, planned_at=None)
            ref = _id("PMR")
            self._pm_log(asset, "RESET", -done, ref, req.get("by"), params.get("reason") or f"정기 정비 완료 ({params.get('ref') or '-'})")
            return ref, (f"{asset} 운전시간 계수기 리셋 ({done:g} h 에 정기 정비) — 다음 기한 {data.PM_SETTINGS['interval_h']} h "
                         f"(허용 {data.PM_SETTINGS['interval_h'] * (1 - data.PM_SETTINGS['tolerance_pct'] / 100):g}~"
                         f"{data.PM_SETTINGS['interval_h'] * (1 + data.PM_SETTINGS['tolerance_pct'] / 100):g} h)")
        if skill == "skill:delay-delivery":                # 공급사 납기 지연 통보 (열린 발주 한 건)
            days = params.get("days", 3)
            if isinstance(days, bool) or not isinstance(days, (int, float)) or not 0 < days <= 60:
                raise ValueError("INVALID: days must be between 0 and 60")
            open_po = [p for p in s["erp"]["purchase_requests"] if p.get("status") == PO_OPEN and p.get("qty")
                       and (params.get("ref") in (None, p["id"])) and (params.get("part_no") in (None, p.get("part_no")))]
            if not open_po:
                raise ValueError("INVALID: no open purchase order to delay")
            pr = open_po[0]
            pr["delay_d"] = (pr.get("delay_d") or 0) + days
            pr["expected_at"] = (datetime.fromisoformat(pr["expected_at"]) + timedelta(days=days)).isoformat()
            return pr["id"], f"발주 {pr['id']} 납기 {days:g}일 지연 통보 — 리드타임 {pr['lead_d']}+{pr['delay_d']:g}일"
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
                pr.update(part=part, part_no=part_no, qty=qty, unit_price=quote["price"], amount=quote["price"] * qty, lead_d=quote["lead_d"], delay_d=0,
                          expected_at=(datetime.now(timezone.utc) + timedelta(days=quote["lead_d"])).isoformat(), received_at=None)
                if part_no in s["erp"]["spare_stock"]:
                    s["erp"]["spare_stock"][part_no]["on_order"] += qty
                    self._move(part_no, "ORDER", qty, asset, pr["id"], req.get("by"), f"발주 {pr['id']} 입고 예정")
                s["erp"]["purchase_requests"].insert(0, pr)
                return pr["id"], f"{part} {qty}개 발주 — {name}, {pr['amount']:g}만원, 리드타임 {quote['lead_d']}일"
            s["erp"]["purchase_requests"].insert(0, pr)
            return pr["id"], f"{part} 구매요청 — {name}"
        if skill == "skill:hold-lot":
            lots = data._QMS[asset]
            lot = params.get("lot") or lots["auto_lot"]
            s["qms"]["holds"].insert(0, {"lot": lot, "asset": asset, "status": "격리 · 전수검사 대기", "decision_id": req.get("decision"), "created_at": _now_us()})
            return lot, f"로트 {lot} 격리 · 전수검사"
        if skill == "skill:release-lot":
            lot = params.get("lot") or data._QMS[asset]["gen_lot"]
            s["qms"]["releases"].insert(0, {"lot": lot, "asset": asset, "status": "샘플검사 후 출하 승인", "decision_id": req.get("decision"), "created_at": _now_us()})
            return lot, f"로트 {lot} 출하 승인"
        if skill == "skill:substitute-shipment":
            inv = data._INVENTORY[asset]
            sh = {"id": _id("SH"), "item": inv["fg_item"], "qty": data._QMS[asset]["auto_qty"], "from": "WH-1 완제품 재고"}
            s["erp"]["shipments"].insert(0, sh)
            return sh["id"], f"{inv['fg_item']} {sh['qty']}개 재고 대체 출하"
        if skill == "skill:demand-control":
            act = {"action": params.get("action", "HYD-03 비긴급 오더 야간 이동에 맞춰 피크 수요 목표 설정"), "t": _now(), "decision_id": req.get("decision")}
            s["ems"]["actions"].insert(0, act)
            return "EMS", act["action"]
        if skill in ALL_COMPENSATION_SKILLS:
            return self._compensate(skill, params, req)
        raise ValueError(skill)

    def _compensate(self, skill: str, params: dict, req: dict | None = None) -> tuple[str, str]:
        """Reverse exactly one forward record by its reference, only from the state the forward transaction left."""
        s = self._s
        ref = params.get("ref")
        if not ref:
            raise ValueError(f"{skill} needs the reference of the record to reverse (params.ref)")
        if skill == "skill:cancel-work-order":
            wo = next((w for w in s["cmms"]["work_orders"] if w["id"] == ref), None)
            if wo is None:
                raise ValueError(f"no such work order {ref}")
            if wo.get('scope_group'):
                raise ValueError('원문 설비 범위의 작업지시는 그룹 전체 취소가 필요합니다')
            if wo["status"] != "배정됨":
                raise ValueError(f"work order {ref} cannot be cancelled in status {wo['status']}")
            wo.update(status=CANCELLED, cancelled_at=_now())
            # 이 오더가 '이번 회차 정기 정비 오더'로 표시돼 있었으면 표시도 지운다 — 남기면 '정기 점검 도래'가 꺼진 채 B가 거절됐다(점검 E6)
            for c in s["cmms"].get("pm_counters", {}).values():
                if c.get("plan_wo") == ref:
                    c.update(plan_wo=None, plan_window=None, planned_at=None, updated_at=_now())
            return ref, f"{wo['asset']} 작업지시 {ref} 취소 ({wo['task']})"
        if skill == "skill:cancel-purchase-request":
            pr = next((p for p in s["erp"]["purchase_requests"] if p["id"] == ref), None)
            if pr is None:
                raise ValueError(f"no such purchase request {ref}")
            if pr["status"] != "승인됨 → 발주":
                raise ValueError(f"purchase request {ref} cannot be cancelled in status {pr['status']}")
            # 수량 발주(C2)면 재고의 입고 예정도 되돌린다 — 남기면 취소한 발주가 가용을 부풀려 '재고 보충 필요'가 꺼진 채였다(점검 E4)
            row = s["erp"]["spare_stock"].get(pr.get("part_no")) if pr.get("qty") else None
            if row is not None and row["on_order"] < pr["qty"]:
                raise ValueError(f"INVALID: on-order quantity of {pr['part_no']} ({row['on_order']}) is less than purchase request {ref} ({pr['qty']})")
            pr.update(status=CANCELLED, cancelled_at=_now())
            if row is not None:
                row["on_order"] -= pr["qty"]
                self._move(pr["part_no"], "CANCEL", pr["qty"], pr.get("asset"), ref, (req or {}).get("by"), f"발주 {ref} 취소")
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

    def maintenance_records(self, asset: str) -> tuple[list[dict], list[dict]]:
        """CMMS 정비 이력에 더할 것(ent.cmms_history 와 같은 출처): 완료한 작업지시(ent.maintenance_history 행 = 완료 때 넣는 이력)와
        이 설비의 작업지시(최근 것부터, work_orders 칸)."""
        with self._lock:
            orders = [w for w in self._s["cmms"]["work_orders"] if w.get("asset") == asset]
            done = [{"wo": w["id"], "task": w.get("task"), "performed_at": w["completed_at"]} for w in orders
                    if w.get("status") == "완료" and w.get("completed_at")]
            return copy.deepcopy(done), [_view_row("work_orders", w) for w in orders]


# ---------------------------------------------------------------- GET /api/state 의 한 모양 (두 백엔드 공통, 점검 E9)
# 메모리 상태는 화면용 칸 이름(window · supplierName · from · qms.holds/releases · ems.actions)을, 업무 DB 는 표 칸 그대로(window_label ·
# supplier_name · source · qms.lot_dispositions · ems.ems_actions)를 내어 포털 '업무 시스템' 표가 백엔드마다 '–' 나 빈 표를 보였다.
# 이제 두 백엔드 모두 아래 모양을 낸다: 표 이름은 업무 DB 표 이름, 행에는 두 이름을 모두 싣는다(같은 값).
SNAPSHOT_TABLES = {"cmms": ("work_orders",), "erp": ("purchase_requests", "shipments", "goods_receipts"),
                   "qms": ("lot_dispositions",), "ems": ("ems_actions",)}
_ALIASES = {"work_orders": (("window", "window_label"),), "purchase_requests": (("supplierName", "supplier_name"),),
            "shipments": (("from", "source"),), "ems_actions": (("t", "created_at"),)}


def _view_row(table: str, row: dict) -> dict:
    out = dict(row)
    for a, b in _ALIASES.get(table, ()):
        value = out.get(a) if out.get(a) is not None else out.get(b)
        out[a] = out[b] = value
    return out


def snapshot_view(mes_orders: list[dict], tables: dict[str, list[dict]]) -> dict:
    """tables = 업무 DB 표 이름 → 행(최근 것부터). 메모리 · 업무 DB 백엔드가 같은 함수로 /api/state 를 만든다."""
    out = {"mes": {"orders": mes_orders}}
    for system, names in SNAPSHOT_TABLES.items():
        out[system] = {name: [_view_row(name, r) for r in tables.get(name, [])] for name in names}
    return out


def memory_tables(s: dict) -> dict[str, list[dict]]:
    """메모리 상태 → 업무 DB 표 이름의 행. 로트 격리 · 출하 승인은 ent.lot_dispositions 처럼 kind(HOLD · RELEASE)를 단 한 표로 합친다."""
    lots = [dict(h, kind="HOLD") for h in s["qms"]["holds"]] + [dict(r, kind="RELEASE") for r in s["qms"]["releases"]]
    lots.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"work_orders": s["cmms"]["work_orders"], "purchase_requests": s["erp"]["purchase_requests"],
            "shipments": s["erp"]["shipments"], "goods_receipts": s["erp"].get("goods_receipts", []),
            "lot_dispositions": lots, "ems_actions": s["ems"]["actions"]}
