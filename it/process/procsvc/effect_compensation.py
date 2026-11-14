"""External effects of a retired generation: exact compensation or a person's acknowledgement, never pretence (A072).

The product (process-gpt-completion `compensation.py`) inverts only what its work history proves reversible — an INSERT
becomes a DELETE of exactly those values — and refuses the whole undo when any effect cannot be reversed, handing the
rework to the agent instead of leaving a half-undone world. HYD has three kinds of effect and the same rule:

  enterprise transaction  reversible when the business system's contract for that skill names an exact inverse (CMMS work
                          order → cancel, ERP purchase request → cancel — the business DB ent.skill_contracts, carried on
                          each ledger row as inverse · irreversible_reason). The inverse is keyed by the original
                          reference; a refused inverse (record moved on) is acknowledged by a person instead.
  irreversible enterprise the contract has no inverse (goods receipt, completed maintenance, counter reset …): nothing is
                          undone; a person acknowledges.
  PLC command             never reversed by an automatic counter-command. A person acknowledges the plant state and the
                          Incident is reopened for a new decision (the command history stays).

Rework may start only when every effect is either compensated (receipt from the business system) or acknowledged
(review receipt by a role at least as high as the approval). Receipts are durable rows, replayed by request id.
"""
from copy import deepcopy
import hashlib
import json
import uuid

from . import engine, machine

PLC_REASON = "물리 명령은 자동 역명령으로 보상하지 않는다. 설비 상태를 확인한 사람의 승인 뒤 사건을 다시 연다"
#: 다시 열 수 있는 사건 상태 — 사건 모델(machine) 한 곳이 갖는다(끝난 사건 definition.TERMINAL 은 다시 열지 않는다)
REOPENABLE = machine.REOPENABLE
BLOCKER = "effects_require_compensation_or_review"


class CompensationRefused(ValueError):
    """업무 시스템이 역거래를 받지 않았다(4xx — 원 기록이 이미 다음 상태로 넘어감 등). 잠깐의 연결 실패와 달리 다시 보내도 같은 답이므로,
    그 효과는 보상 대신 사람 확인으로 정리한다(review_effects). 보상 실행 연결(main._exec_compensation)이 이 예외로 알린다."""


def _fp(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def inventory(evidence: dict) -> list[dict]:
    """Every external effect the case left, with its reversibility. Pure: no IO, no state change."""
    effects: list[dict] = []
    incident = evidence.get("incident") or {}
    for did, ledger in sorted((evidence.get("enterprise_receipts") or {}).items()):
        forward = [tx for tx in ledger if not tx.get("compensates")]
        inverse = [tx for tx in ledger if tx.get("compensates")]
        for tx in forward:
            skill = tx.get("skill")
            # 되돌리기 계약은 업무 시스템이 거래마다 싣는다(enterprise-sim /api/transactions ← 업무 DB ent.skill_contracts 한 곳) —
            # process 는 계약을 따로 들고 있지 않다. 칸이 없으면 계약이 어긋난 응답이라 실패한다(되돌릴 수 있다고 짐작하지 않는다)
            if "inverse" not in tx or "irreversible_reason" not in tx:
                raise ValueError(f"업무 시스템 거래 {tx.get('id')}({skill}) 응답에 되돌리기 계약(inverse · irreversible_reason)이 없습니다 — "
                                 "enterprise-sim 판을 확인하세요")
            undo = next((c for c in inverse if c.get("compensates") == tx.get("id")
                         or (c.get("skill") == tx["inverse"] and c.get("ref") == tx.get("ref"))), None)
            effects.append({"id": f"tx:{tx.get('id')}", "kind": "enterprise", "decision": did, "tx": tx.get("id"),
                            "skill": skill, "system": tx.get("system"), "ref": tx.get("ref"), "detail": tx.get("detail"),
                            "reversible": tx["inverse"] is not None, "inverse": tx["inverse"],
                            "irreversible_reason": None if tx["inverse"] is not None else tx["irreversible_reason"],
                            "compensated_by": undo.get("id") if undo else None,
                            "fingerprint": _fp(["tx", did, tx.get("id"), skill, tx.get("ref")])})
    ledger_refs = {e["ref"] for e in effects}
    # Local execution records that the enterprise ledger does not confirm (failed, missing reference, ledger lagging)
    # are unclear external state: a person must look before any rework.
    for decision in evidence.get("decisions") or []:
        for n, x in enumerate(decision.get("executions") or []):
            if x.get("status") == "DONE" and x.get("ref") and x["ref"] in ledger_refs:
                continue
            effects.append({"id": f"local:{decision['id']}:{x.get('code') or n}", "kind": "local", "decision": decision["id"],
                            "code": x.get("code"), "ref": x.get("ref"), "status": x.get("status"), "system": x.get("system"), "reversible": False,
                            "irreversible_reason": "기업 원장이 확인하지 않는 로컬 실행 기록 — 사람이 확인해야 한다",
                            "compensated_by": None, "fingerprint": _fp(["local", decision["id"], n, x.get("code"), x.get("ref"), x.get("status")])})
    if incident.get("cmdId") or incident.get("actions") or incident.get("ack"):
        cmd = incident.get("cmdId") or "unidentified"
        effects.append({"id": f"plc:{cmd}", "kind": "plc", "incident": incident.get("id"), "cmdId": incident.get("cmdId"),
                        "actions": deepcopy(incident.get("actions") or []), "ack": deepcopy(incident.get("ack")),
                        "reversible": False, "compensated_by": None,
                        "irreversible_reason": PLC_REASON if incident.get("cmdId") else "명령 ID 없이 조치/응답 기록만 있다 — 사람이 확인해야 한다",
                        "fingerprint": _fp(["plc", incident.get("id"), incident.get("cmdId"), incident.get("actions"), incident.get("ack")])})
    wo = incident.get("workOrder") or {}
    wo_ref = wo.get("ref") or wo.get("id")
    if wo_ref and wo_ref not in ledger_refs:
        effects.append({"id": f"cmms:{wo_ref}", "kind": "cmms", "incident": incident.get("id"), "ref": wo_ref, "reversible": False,
                        "irreversible_reason": "사건이 기록한 정비 요청이 기업 원장에 없다 — 사람이 확인해야 한다", "compensated_by": None,
                        "fingerprint": _fp(["cmms", incident.get("id"), wo_ref])})
    request = incident.get("workOrderRequest")
    if request and not wo_ref:
        effects.append({"id": f"cmms-request:{incident.get('id')}", "kind": "cmms-request", "incident": incident.get("id"), "request": deepcopy(request),
                        "reversible": False, "irreversible_reason": "저장된 CMMS 요청의 실제 접수 여부가 불명확하다 — 사람이 확인해야 한다",
                        "compensated_by": None, "fingerprint": _fp(["cmms-request", incident.get("id"), request])})
    return effects


def explained_services(defn, work, affected: set, effects: list[dict], outcome: dict) -> set:
    """Started services whose external effect is one the receipts settle; anything else stays a review blocker."""
    settled = set(outcome.get("compensated", [])) | set(outcome.get("acknowledged", []))
    cmd_ids = {e["cmdId"] for e in effects if e["kind"] == "plc" and e["id"] in settled and e.get("cmdId")}
    refs = {e.get("ref") for e in effects if e["id"] in settled and e.get("ref")}
    out = set()
    for w in work:
        if w["id"] not in affected:
            continue
        tool = (defn.activities.get(w["activity_id"]) or {}).get("tool") or ""
        log = w.get("log") or ""
        output = w.get("output") or {}
        if tool == "incident:command" and any(f"action.cmd {cid} " in log for cid in cmd_ids) and "external call attempted" not in log:
            out.add(w["id"])
        elif tool == "incident:reobserve" and set(output) <= {"recovered"} and "external" not in log:
            out.add(w["id"])
        elif tool.startswith("enterprise:") and ((output.get("work_order") or {}).get("ref") in refs):
            out.add(w["id"])
    return out


def refused_compensations(receipts: list[dict]) -> set[str]:
    """업무 시스템이 역거래를 거절한(CompensationRefused) 효과 id — 보상으로는 끝낼 수 없어 사람 확인으로 정리한다."""
    return {r["effect"] for x in receipts if x.get("kind") == "compensation" for r in x.get("results") or [] if r.get("refused")}


def resolution(effects: list[dict], receipts: list[dict]) -> dict:
    """Which effects are compensated, acknowledged, or still pending, judged only from durable receipts and the ledger."""
    acknowledged = {}
    for r in receipts:
        if r.get("kind") == "review" and r.get("status") == "RECORDED":
            for e in r.get("effects") or []:
                acknowledged[e["fingerprint"]] = r["request_id"]
    out = {"compensated": [], "acknowledged": [], "pending": []}
    for e in effects:
        if e.get("compensated_by"):
            out["compensated"].append(e["id"])
        elif e["fingerprint"] in acknowledged:
            out["acknowledged"].append(e["id"])
        else:
            out["pending"].append(e["id"])
    return out


def resolved(effects: list[dict], receipts: list[dict]) -> bool:
    return not resolution(effects, receipts)["pending"]


def _review_level(evidence: dict, approvals: list[dict], role: str) -> tuple[int, int]:
    """(level of the requested role, level the review needs). Levels come from the decisions' own role tables."""
    roles = {}
    for d in evidence.get("decisions") or []:
        roles.update(d.get("roles") or {})
    level = int((roles.get(role) or {}).get("level") or 0)
    need = 0
    for a in approvals:
        if a.get("status") == "DISCARDED":
            continue
        need = max(need, int((roles.get((a.get("payload") or {}).get("role")) or {}).get("level") or 0))
    return level, need


def _mark_refused(effects: list[dict], receipts: list[dict]) -> list[dict]:
    """업무 시스템이 역거래를 거절한 되돌릴 수 있는 효과는 사람 확인 대상으로 보인다(보상 단추 대신 확인 칸)."""
    refused = refused_compensations(receipts)
    for e in effects:
        if e["id"] in refused and e.get("reversible"):
            e["compensation_refused"] = True
    return effects


class EffectRuntime:
    """Compensation and review receipts on the instance; mixed into InstanceRuntime."""

    def _effect_case(self, inst):
        if not engine.variables(inst).get("incident") or self.hooks.rework_effects is None:
            raise ValueError("연결된 사건과 효과 조회가 없는 인스턴스입니다")
        evidence = self.hooks.rework_effects(deepcopy(inst))
        approvals = self.repo.list_approvals(inst["proc_inst_id"], self.tenant_id)
        receipts = self.repo.list_effect_receipts(self.tenant_id, inst["proc_inst_id"])
        return evidence, approvals, receipts

    def effects_view(self, proc_inst_id: str) -> dict:
        """조회 — 처리 건 전이 잠금을 잡지 않는다(엔진 · 워커 저장과 다투지 않고, 업무 시스템 원장 HTTP 를 잠금 안에서 기다리지 않는다).
        한 시점의 읽기 전용 스냅숏(다시 수행 미리보기와 같은 repo.read_snapshot)으로 읽는다. 보상 · 확인(쓰기)은 잠금 안에서 다시 읽어 판정한다."""
        with self.repo.read_snapshot():
            inst = self.repo.get_instance(proc_inst_id)
            if not inst or inst.get("tenant_id") != self.tenant_id:
                raise KeyError("no such instance")
            evidence, approvals, receipts = self._effect_case(inst)
            defn = self.definition_for(inst)
        effects = _mark_refused(inventory(evidence), receipts)
        roles = sorted({defn.role_endpoint(a.get("role")) for a in defn.activities.values()
                        if engine.is_human(a) and defn.role_endpoint(a.get("role"))})
        incident = evidence["incident"]
        return {"instance": proc_inst_id, "incident": {k: incident.get(k) for k in ("id", "state", "cmdId", "cleared", "workOrder")},
                "effects": effects, "resolution": resolution(effects, receipts), "receipts": receipts,
                "reopen_required": incident.get("state") != "AWAITING_APPROVAL", "review_roles": roles,
                "scope": "조회는 상태를 바꾸지 않습니다. 되돌릴 수 있는 거래는 보상 요청으로, 나머지는 사람의 확인으로만 해결됩니다."}

    def _authorize_review(self, defn, evidence, approvals, by, role, reason):
        human = {defn.role_endpoint(a.get("role")) for a in defn.activities.values() if engine.is_human(a)}
        if not all(isinstance(v, str) and v.strip() for v in (by, role, reason)):
            raise ValueError("요청자, 역할, 사유가 필요합니다")
        if role not in human:
            raise PermissionError("고정 정의의 사람 업무 담당 역할로 요청하세요")
        level, need = _review_level(evidence, approvals, role)
        if need and level < need:
            raise PermissionError("기존 승인 역할 이상이 효과를 확인해야 합니다")

    def compensate_effects(self, proc_inst_id, request_id, by, role, reason, effect_ids=None, now=None):
        """Run the business systems' exact inverses for the reversible effects; durable receipt first, delivery after."""
        request_id = str(uuid.UUID(request_id))
        with self._transition(proc_inst_id):
            inst = self.repo.get_instance(proc_inst_id)
            if not inst or inst.get("tenant_id") != self.tenant_id:
                raise KeyError("no such instance")
            prior = self.repo.get_effect_receipt(self.tenant_id, proc_inst_id, request_id)
            request = {"kind": "compensation", "by": by, "role": role, "reason": reason, "effects": sorted(effect_ids or [])}
            if prior:
                # 영수증 넣기와 결과는 한 트랜잭션이라 저장된 영수증은 늘 끝난 것(DELIVERED · FAILED)이다 — 같은 요청은 그 영수증을 그대로.
                # 실패한 보상을 이어 하려면 새 요청 ID 로 다시 요청한다(이미 보상된 효과는 원장 영수증으로 해결돼 빠진다)
                if prior["request"] != request:
                    raise ValueError("같은 요청 ID에 다른 보상 내용을 사용할 수 없습니다")
                return deepcopy(prior)
            evidence, approvals, receipts = self._effect_case(inst)
            self._authorize_review(self.definition_for(inst), evidence, approvals, by, role, reason)
            effects = inventory(evidence)
            pending = set(resolution(effects, receipts)["pending"])
            refused = refused_compensations(receipts)
            chosen = [e for e in effects if e["id"] in pending and e["reversible"] and e["id"] not in refused
                      and (not effect_ids or e["id"] in effect_ids)]
            missing = set(effect_ids or []) - {e["id"] for e in chosen}
            if missing:
                raise ValueError("보상할 수 없는 효과입니다 (되돌릴 수 없거나, 이미 해결됐거나, 업무 시스템이 역거래를 거절해 확인으로 정리할 효과): "
                                 + ", ".join(sorted(missing)))
            if not chosen:
                raise ValueError("보상할 수 있는 미해결 효과가 없습니다")
            if self.hooks.exec_compensation is None:
                raise ValueError("기업 보상 실행이 연결되지 않았습니다")
            receipt = {"tenant_id": self.tenant_id, "proc_inst_id": proc_inst_id, "request_id": request_id, "kind": "compensation",
                       "status": "PENDING", "request": request, "effects": deepcopy(chosen), "results": [], "error": None,
                       "history": [{"status": "PENDING", "t": engine.now_iso(now), "by": by, "role": role}]}
            self.repo.insert_effect_receipt(receipt)
            results, failed = [], None
            for e in receipt["effects"]:
                try:
                    tx = self.hooks.exec_compensation({"decision": e["decision"], "skill": e["inverse"], "asset": engine.variables(inst).get("asset"),
                                                       "by": by, "params": {"ref": e["ref"]}, "compensates": e["tx"]})
                    if not isinstance(tx, dict) or not tx.get("id") or tx.get("ref") != e["ref"]:
                        raise ValueError(f"보상 응답이 원거래 참조와 다릅니다: {tx}")
                    results.append({"effect": e["id"], "ok": True, "tx": tx.get("id"), "ref": tx.get("ref"), "skill": e["inverse"], "detail": tx.get("detail")})
                except Exception as error:  # noqa: BLE001 — 영수증 · 사건 기록에 그대로 남긴다(삼키지 않음)
                    failed = f"{type(error).__name__}: {str(error)[:300]}"
                    results.append({"effect": e["id"], "ok": False, "skill": e["inverse"], "error": failed,
                                    "refused": isinstance(error, CompensationRefused)})
                    break
            receipt.update(results=results, status="FAILED" if failed else "DELIVERED", error=failed)
            receipt["history"].append({"status": receipt["status"], "t": engine.now_iso(now), "error": failed})
            self.repo.update_effect_receipt(receipt)
            self.repo.record_events([{"job_id": "EFFECT_COMPENSATION", "todo_id": None, "proc_inst_id": proc_inst_id, "crew_type": "human",
                                      "event_type": "error" if failed else "task_working",
                                      "data": {"name": "기존 효과 보상 " + ("실패" if failed else "완료"), "request_id": request_id, "by": by, "role": role,
                                               "reason": reason, "results": deepcopy(results)}}])
            v = engine.variables(inst)
            self._after_commit(self.hooks.audit, v.get("asset", "-"), by, "EFFECT_COMPENSATED" if not failed else "EFFECT_COMPENSATION_FAILED",
                               {"instance": proc_inst_id, "request_id": request_id, "results": deepcopy(results)}, incident=v.get("incident"))
            return self.repo.get_effect_receipt(self.tenant_id, proc_inst_id, request_id)

    def review_effects(self, proc_inst_id, request_id, by, role, reason, effect_ids, now=None):
        """A person acknowledges irreversible effects (plant state, shipped lots…). Reversible ones must be compensated instead."""
        request_id = str(uuid.UUID(request_id))
        if not isinstance(effect_ids, list) or not effect_ids:
            raise ValueError("확인한 효과 ID 목록이 필요합니다")
        with self._transition(proc_inst_id):
            inst = self.repo.get_instance(proc_inst_id)
            if not inst or inst.get("tenant_id") != self.tenant_id:
                raise KeyError("no such instance")
            request = {"kind": "review", "by": by, "role": role, "reason": reason, "effects": sorted(effect_ids)}
            prior = self.repo.get_effect_receipt(self.tenant_id, proc_inst_id, request_id)
            if prior:
                if prior["request"] != request:
                    raise ValueError("같은 요청 ID에 다른 확인 내용을 사용할 수 없습니다")
                return deepcopy(prior)
            evidence, approvals, receipts = self._effect_case(inst)
            self._authorize_review(self.definition_for(inst), evidence, approvals, by, role, reason)
            effects = {e["id"]: e for e in inventory(evidence)}
            pending = set(resolution(list(effects.values()), receipts)["pending"])
            unknown = [i for i in effect_ids if i not in effects]
            if unknown:
                raise ValueError("현재 효과 목록에 없는 ID입니다: " + ", ".join(unknown))
            refused = refused_compensations(receipts)
            reversible = [i for i in effect_ids if effects[i]["reversible"] and not effects[i].get("compensated_by") and i not in refused]
            if reversible:
                raise ValueError("되돌릴 수 있는 거래는 확인이 아니라 보상 요청으로 처리해야 합니다(업무 시스템이 역거래를 거절했을 때만 확인으로 정리합니다): "
                                 + ", ".join(reversible))
            if any(i not in pending for i in effect_ids):
                raise ValueError("이미 해결된 효과가 포함돼 있습니다")
            if evidence["incident"].get("state") == "AWAITING_ACK":
                raise ValueError("설비 응답을 기다리는 명령은 응답 뒤에 확인할 수 있습니다")
            receipt = {"tenant_id": self.tenant_id, "proc_inst_id": proc_inst_id, "request_id": request_id, "kind": "review", "status": "RECORDED",
                       "request": request, "effects": [deepcopy(effects[i]) for i in effect_ids], "results": [],
                       "error": None, "history": [{"status": "RECORDED", "t": engine.now_iso(now), "by": by, "role": role,
                                                   "incident": {k: evidence["incident"].get(k) for k in ("id", "state", "cmdId", "ack", "cleared")}}]}
            self.repo.insert_effect_receipt(receipt)
            self.repo.record_events([{"job_id": "EFFECT_REVIEW", "todo_id": None, "proc_inst_id": proc_inst_id, "crew_type": "human",
                                      "event_type": "task_working", "data": {"name": "기존 효과 확인", "request_id": request_id, "by": by,
                                                                             "role": role, "reason": reason, "effects": effect_ids}}])
            v = engine.variables(inst)
            self._after_commit(self.hooks.audit, v.get("asset", "-"), by, "EFFECT_ACKNOWLEDGED",
                               {"instance": proc_inst_id, "request_id": request_id, "effects": effect_ids, "reason": reason}, incident=v.get("incident"))
            return self.repo.get_effect_receipt(self.tenant_id, proc_inst_id, request_id)   # the stored row: first response == replay
