"""C2 (확정 TODO C) 승인 뒤 실행 부품의 처리기 — InstanceRuntime 에 섞는다(effect_parts 는 순수 계약, 여기는 실행).

모든 처리기는 _run_service 가 그 처리 건의 전이 잠금 안에서 부른다(행은 SUBMITTED, consumer '<engine>:service').
  * 끝나면 self.submit(…, by="process") 로 결과를 내고 흐름이 다음으로 간다.
  * 기다리는 부품(시간 대기 · 입고 확인 · 작업지시 뒤 재관측)은 첫 실행에 끝 시각을 행의 draft · due_date 에 저장하고 SUBMITTED 로 둔다.
    폴링(reconcile_services → procdb.waiting_services)이 2초마다 다시 부르고, 끝 시각이 지나면 제출한다. 재시작해도 저장한 시각을 쓴다.
  * 실패는 ServiceExecutionError(응답 그대로) → _fail(3회까지 재시도 뒤 PENDING, 사유 보존). 성공한 척하지 않는다.
  * 바깥 효과(MCP 쓰기 · ERP 발주 · 입고 · 정비 모사)는 처리 건에 사람 승인(approved_by)이 있어야 실행한다(등록 검사에 더한 이중 확인).
    같은 승인으로 두 번 실행되지 않게 업무 쪽 멱등 키(decision + skill)와 MCP idempotency_key(처리 건:작업)를 쓴다.
"""
from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone

from . import engine, effect_parts, inbox
from . import definition as incident_def

log = logging.getLogger("process.service_parts")

REOBSERVE_MAX_EXTENSIONS = incident_def.REOBSERVE_MAX_EXTENSIONS


def _clock(now):
    return now or datetime.now(timezone.utc)


class ServicePartsRuntime:
    """InstanceRuntime 의 섞음(mixin). self.repo · self.hooks · self.time_scale · self.submit · self._after_commit 을 쓴다."""

    def _service_handlers(self) -> dict:
        return {effect_parts.MCP_TOOL: self._run_mcp_call, effect_parts.PR_TOOL: self._run_purchase_order,
                effect_parts.WAIT_TOOL: self._run_wait, effect_parts.RESTORE_TOOL: self._run_maintenance,
                effect_parts.GR_TOOL: self._run_goods_receipt, effect_parts.TEST_RUN_TOOL: self._run_test_run,
                effect_parts.REPORT_TOOL: self._run_report}

    # ---------------------------------------------------------------- 공통
    def _activity_of(self, wi: dict) -> dict:
        return self.definition_for_workitem(wi).activities.get(wi["activity_id"]) or {}

    @staticmethod
    def _state(wi: dict) -> dict:
        return deepcopy(wi["draft"]) if isinstance(wi.get("draft"), dict) else {}

    def _save_state(self, wi: dict, **changes) -> dict:
        state = self._state(wi)
        state.update(changes)
        wi["draft"] = state
        self.repo.update_workitem(wi)
        return state

    def _event(self, wi: dict, job: str, name: str, data: dict, *, event_type: str = "task_working", crew: str = "result") -> None:
        self.repo.record_events([{"job_id": job, "todo_id": wi["id"], "proc_inst_id": wi["proc_inst_id"], "crew_type": crew,
                                  "event_type": event_type, "data": dict(data, name=name)}])

    def _require_approval(self, inst: dict, wi: dict) -> dict:
        v = engine.variables(inst)
        if not v.get("approved_by"):
            raise ValueError(f"'{wi.get('activity_name') or wi['activity_id']}'은(는) 사람 승인 뒤에만 실행합니다 — 이 처리 건에 승인 기록이 없습니다")
        return v

    def _decision_of(self, inst: dict, v: dict) -> str:
        return v.get("decision_id") or inst["proc_inst_id"]

    def _exec(self, inst: dict, v: dict, item: dict, label: str) -> dict:
        res = self.hooks.exec_enterprise(self._decision_of(inst, v), item)
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "SKILL_EXECUTED" if res.get("ok") else "SKILL_FAILED",
                           {"instance": inst["proc_inst_id"], "code": item.get("code"), "ref": res.get("ref"),
                            "detail": res.get("detail") or res.get("error"), "part": label}, incident=v.get("incident"))
        if res.get("ok") is not True or not isinstance(res.get("ref"), str) or not res["ref"].strip():
            from .instances import ServiceExecutionError
            raise ServiceExecutionError(res)
        return res

    # ---------------------------------------------------------------- 승인 뒤 MCP 호출
    def _run_mcp_call(self, inst: dict, wi: dict, now) -> None:
        v = self._require_approval(inst, wi)
        cfg = self._activity_of(wi).get("service") or {}
        receipt = self._call_mcp(inst, wi, v, cfg, f"{inst['proc_inst_id']}:{wi['id']}", now)
        self.submit(wi["id"], {cfg.get("output") or "mcp_receipt": receipt}, by="process", now=now)

    def _send_notice(self, inst: dict, wi: dict, values: dict, mail, now) -> dict | None:
        """시스템 task 끝의 메일 공지(발주 → 공급사 · 입고 부서, 정비 오더 → 생산팀). 같은 작업의 재시도는 같은 키라 한 통만 간다."""
        spec = effect_parts.notice_spec(mail)
        if spec is None:
            return None
        state = self._state(wi)
        if "notice" in state:
            return state["notice"]
        receipt = self._call_mcp(inst, wi, values, spec, f"{inst['proc_inst_id']}:{wi['id']}:notice", now)
        self._save_state(wi, notice=receipt)
        return receipt

    def _call_mcp(self, inst: dict, wi: dict, v: dict, cfg: dict, key: str, now) -> dict:
        context = dict(v, proc_inst_id=inst["proc_inst_id"], proc_inst_name=inst.get("proc_inst_name"),
                       task_name=wi.get("activity_name"))
        try:
            arguments = effect_parts.render(cfg.get("arguments") or {}, context)
        except KeyError as e:
            raise ValueError(f"MCP 인자 틀의 값 {e.args[0]} 이(가) 처리 건에 없습니다 — 빈 값으로 보내지 않습니다") from e
        server, tool = cfg["server"], cfg["tool"]
        use_id = f"{key}:{int(wi.get('retry') or 0)}"
        raw_tool = f"mcp__{server}__{tool}"
        # 이벤트 본문: HYD 도구 호출 기록(mcp_calls: tool · input · output)과 제품 화면(tool_name · args · result · is_error) 두 이름을 함께 둔다
        self._event(wi, "MCP_EFFECT_CALL", "승인 뒤 MCP 호출", {"tool": raw_tool, "tool_name": tool, "tool_use_id": use_id, "input": arguments,
                                                              "args": arguments, "idempotency_key": key}, event_type="tool_usage_started", crew="tool")
        res = self.hooks.mcp_call(server, tool, arguments, key)
        result = res.get("result") or {}
        failed = res.get("status") != "ok" or result.get("is_error")
        self._event(wi, "MCP_EFFECT_CALL", "승인 뒤 MCP 호출 결과", {"tool": raw_tool, "tool_name": tool, "tool_use_id": use_id, "output": result.get("text") or res.get("error"),
                                                                  "result": result.get("text") or res.get("error"), "is_error": bool(failed)}, event_type="tool_usage_finished", crew="tool")
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "MCP_EFFECT_FAILED" if failed else "MCP_EFFECT_CALLED",
                           {"instance": inst["proc_inst_id"], "server": server, "tool": tool, "idempotency_key": key,
                            "error": res.get("error")}, incident=v.get("incident"))
        if failed:
            from .instances import ServiceExecutionError
            raise ServiceExecutionError({"error": res.get("error") or (result.get("text") or "")[:300] or "MCP 도구가 오류를 돌려줬습니다",
                                         "server": server, "tool": tool, "status": res.get("status"), "error_kind": res.get("error_kind")})
        return {"server": server, "tool": tool, "arguments": res.get("arguments", arguments), "idempotency_key": key,
                "idempotent": res.get("idempotent"), "result": result.get("text"), "called_at": engine.now_iso(_clock(now))}

    # ---------------------------------------------------------------- ERP 발주
    def _run_purchase_order(self, inst: dict, wi: dict, now) -> None:
        v = self._require_approval(inst, wi)
        missing = [k for k in ("approved_supplier", "approved_part_no", "approved_qty", "approved_amount") if v.get(k) is None]
        if missing:
            raise ValueError("승인 경로가 확정한 발주 값이 없습니다(" + ", ".join(missing) + ") — 발주 카드를 사람이 승인한 처리 건에서만 발주합니다")
        opt = v.get("chosen_option") or {}
        item = {"skill": opt.get("id"), "sop": opt.get("sopId"), "code": "PR_CREATE", "name": "ERP 발주", "system": "sys:erp",
                "value": v["approved_supplier"], "part_no": v["approved_part_no"], "qty": v["approved_qty"],
                "amount": v["approved_amount"], "source": "approved-purchase"}
        res = self._exec(inst, v, item, "ERP 발주")
        notice = self._send_notice(inst, wi, dict(v, purchase_order=res), (self._activity_of(wi).get("service") or {}).get("mail"), now)
        self.submit(wi["id"], {"purchase_order": dict(res, notice=notice) if notice else res}, by="process", now=now)

    # ---------------------------------------------------------------- 시간 대기
    def _run_wait(self, inst: dict, wi: dict, now) -> None:
        clock = _clock(now)
        state = self._state(wi)
        if "wait" not in state:
            cfg = self._activity_of(wi).get("service") or {}
            try:
                plan = effect_parts.wait_for(cfg, engine.variables(inst), clock, self.time_scale)
            except KeyError as e:
                raise ValueError(f"기다릴 시각 값 {e.args[0]} 이(가) 처리 건에 없습니다") from e
            wi["due_date"] = plan["due_at"]
            wi["log"] = (wi.get("log") or "") + (f"waiting {plan['virtual_s']:.0f} virtual s = {plan['real_s']:.0f} s "
                                                 f"(x{plan['time_scale']:g} x{plan['compression']:g}); ")
            state = self._save_state(wi, wait=plan)
            self._event(wi, "WAIT_STARTED", "시간 대기 시작", {"plan": plan})
        plan = state["wait"]
        if not effect_parts.due(plan, clock):
            return
        self._event(wi, "WAIT_ENDED", "시간 대기 끝", {"plan": plan})
        self.submit(wi["id"], {"waited": dict(plan, ended_at=engine.now_iso(clock))}, by="process", now=now)

    # ---------------------------------------------------------------- 정비 수행 모사
    def _run_maintenance(self, inst: dict, wi: dict, now) -> None:
        v = self._require_approval(inst, wi)
        cfg = self._activity_of(wi).get("service") or {}
        state = self._state(wi)
        immediate = bool(((v.get("chosen_option") or {}).get("window") or {}).get("immediate"))
        if cfg.get("until") and immediate and "wait" not in state:
            # C3: 승인한 카드가 '즉시(지금 정지하고 시행)'면 기다릴 예정된 정비 시간이 없다 — 바로 정비한다
            state = self._save_state(wi, wait={"due_at": engine.now_iso(_clock(now)), "real_s": 0, "label": "즉시 시행", "immediate": True})
            self._event(wi, "WAIT_SKIPPED", "즉시 시행 — 예정된 정비 시간 대기 없음", {"window": (v.get("chosen_option") or {}).get("window")})
        if cfg.get("until"):                       # 예정된 정비 시간까지 먼저 기다린다(시간 대기와 같은 계산 · 같은 수업 압축)
            clock = _clock(now)
            if "wait" not in state:
                try:
                    plan = effect_parts.wait_for({"until": cfg["until"], "label": "예정된 정비 시간까지"}, v, clock, self.time_scale)
                except KeyError as e:
                    raise ValueError(f"예정된 정비 시간 값 {e.args[0]} 이(가) 처리 건에 없습니다") from e
                wi["due_date"] = plan["due_at"]
                state = self._save_state(wi, wait=plan)
                self._event(wi, "WAIT_STARTED", "예정된 정비 시간까지 대기", {"plan": plan})
            if not effect_parts.due(state["wait"], clock):
                return
        wo = v.get(cfg.get("work_order_var") or "work_order")
        opt = v.get("chosen_option") or {}
        if isinstance(wo, dict) and wo.get("ref") and "completed" not in state:
            item = {"skill": opt.get("id"), "code": "WO_COMPLETE", "name": "작업지시 완료", "system": "sys:cmms", "ref": wo["ref"],
                    "sop": cfg.get("sop") or opt.get("sopId"), "source": "approved-maintenance"}
            state = self._save_state(wi, completed=self._exec(inst, v, item, "정비 수행 모사"))
        if "restored" not in state:
            res = self.hooks.plant_restore(v.get("asset"), cfg.get("component") or None)
            if not isinstance(res, dict) or res.get("ok") is False:
                from .instances import ServiceExecutionError
                raise ServiceExecutionError(res if isinstance(res, dict) else {"error": "설비 시뮬레이터 응답이 없습니다"})
            state = self._save_state(wi, restored=res)
        notice = (f"{v.get('asset')} 정비 완료 — " + ((state.get("completed") or {}).get("detail") or "설비 시뮬레이터 복구")
                  + (f", 대상 {cfg['component']}" if cfg.get("component") else ""))
        out = {"asset": v.get("asset"), "component": cfg.get("component") or "all", "work_order": (wo or {}).get("ref") if isinstance(wo, dict) else None,
               "completed": state.get("completed"), "restored": state.get("restored"), "notice": notice,
               "done_at": engine.now_iso(_clock(now))}
        self._event(wi, "MAINTENANCE_DONE", "정비 완료 공지", {"notice": notice})
        self._after_commit(inbox.notify_participants, self.repo, self.tenant_id, dict(inst), "정비 완료", notice)
        self.submit(wi["id"], {"maintenance": out}, by="process", now=now)

    # ---------------------------------------------------------------- 입고 확인
    def _run_goods_receipt(self, inst: dict, wi: dict, now) -> None:
        v = self._require_approval(inst, wi)
        cfg = self._activity_of(wi).get("service") or {}
        po = v.get(cfg.get("purchase_order_var") or "purchase_order")
        if not isinstance(po, dict) or not po.get("ref"):
            raise ValueError("입고를 확인할 발주 영수증(purchase_order.ref)이 처리 건에 없습니다")
        clock = _clock(now)
        state = self._state(wi)
        if cfg.get("immediate") and "wait" not in state:
            # C3 B · C 단순화: 발주 뒤 바로 입고 · 재고 반영(리드타임을 기다리지 않는다 — '처리되면 끝')
            state = self._save_state(wi, wait={"due_at": engine.now_iso(clock), "real_s": 0, "label": "즉시 입고", "immediate": True})
            self._event(wi, "RECEIPT_IMMEDIATE", "입고 대기 없음 — 발주 수량을 바로 입고 · 재고 반영", {"purchase_order": po["ref"]})
        if "wait" not in state:
            after = po.get("after") or {}
            lead_d, delay_d = after.get("lead_d"), after.get("delay_d") or 0
            if lead_d is None and self.hooks.enterprise_read is not None:
                facts = (self.hooks.enterprise_read("purchase_order", {"ref": po["ref"]}) or {}).get("facts") or {}
                lead_d, delay_d = facts.get("lead_d"), facts.get("delay_d") or 0
            plan = effect_parts.wait_plan((float(lead_d or 0) + float(delay_d)) * 86400, clock, self.time_scale, label="입고 예정까지",
                                          source=f"{po['ref']} 리드타임 {lead_d}일" + (f" + 지연 {delay_d:g}일" if delay_d else ""))
            plan.update(lead_d=lead_d, delay_d=float(delay_d))
            wi["due_date"] = plan["due_at"]
            state = self._save_state(wi, wait=plan)
            self._event(wi, "RECEIPT_WAIT", "입고 대기 시작", {"purchase_order": po["ref"], "plan": plan})
        if not effect_parts.due(state["wait"], clock):
            return
        if "receipt" not in state and self.hooks.enterprise_read is not None and not state["wait"].get("immediate"):
            # 공급사가 납기 지연을 알렸으면(수업 버튼 '공급사 납기 지연') 늦어진 입고 예정까지 더 기다린다 — 그 사이 납기 초과 타이머가 울릴 수 있다
            facts = (self.hooks.enterprise_read("purchase_order", {"ref": po["ref"]}) or {}).get("facts") or {}
            delay_d = float(facts.get("delay_d") or 0)
            plan = state["wait"]
            if delay_d > float(plan.get("delay_d") or 0):
                extra = effect_parts.wait_plan((delay_d - float(plan.get("delay_d") or 0)) * 86400, clock, self.time_scale)
                plan = dict(plan, due_at=extra["due_at"], delay_d=delay_d, source=f"{po['ref']} 리드타임 {plan.get('lead_d')}일 + 지연 {delay_d:g}일")
                wi["due_date"] = plan["due_at"]
                state = self._save_state(wi, wait=plan)
                self._event(wi, "RECEIPT_DELAYED", "공급사 납기 지연 — 입고 예정이 늦어짐", {"purchase_order": po["ref"], "plan": plan})
                return
        if "receipt" not in state:
            item = {"skill": (v.get("chosen_option") or {}).get("id"), "code": "GR_CONFIRM", "name": "입고 · 검수", "system": "sys:erp",
                    "ref": po["ref"], "source": "approved-purchase"}
            state = self._save_state(wi, receipt=self._exec(inst, v, item, "입고 확인"))
        if "stock_after" not in state and self.hooks.enterprise_read is not None:
            # C3: 입고 뒤 재고(가용 · 재주문점)를 결과 보고에 싣는다 — '재고 보충 필요' 표시가 꺼졌는지의 근거
            part_no = (state["receipt"].get("after") or {}).get("part_no") or (po.get("after") or {}).get("part_no") or v.get("approved_part_no")
            try:
                facts = (self.hooks.enterprise_read("spare_stock", {"part": part_no}) or {}).get("facts") or {} if part_no else {}
            except Exception:  # noqa: BLE001 — 보조 정보, 읽기 실패로 입고 확인을 막지 않는다
                facts = {}
            state = self._save_state(wi, stock_after={k: facts.get(k) for k in ("part_no", "on_hand", "reserved", "on_order", "available",
                                                                                 "reorder_point", "below_reorder_point") if k in facts})
        receipt = dict(state["receipt"], stock_after=state.get("stock_after") or None)
        if v.get("incident") and self.hooks.close_incident_effect is not None:
            self.hooks.close_incident_effect(v["incident"], {"ok": True, "ref": receipt.get("ref"), "detail": receipt.get("detail"), "kind": "goods_receipt"})
        notice = f"입고 확인 — {receipt.get('detail') or receipt.get('ref')}"
        self._event(wi, "GOODS_RECEIVED", "입고 확인", {"receipt": receipt})
        self._after_commit(inbox.notify_participants, self.repo, self.tenant_id, dict(inst), "입고 확인", notice)
        self.submit(wi["id"], {"goods_receipt": receipt, "received": True}, by="process", now=now)

    # ---------------------------------------------------------------- 시운전 확인 (정비 뒤)
    def _run_test_run(self, inst: dict, wi: dict, now) -> None:
        """안정 시간(가상 · 배속만) 뒤 기준 태그의 최신값을 읽어 판정한다. 통과면 CMMS 운전시간 계수기 리셋 · 다음 기한 기록(효과).
        미달이면 리셋하지 않고 passed=False — 흐름의 분기가 '미달' 결과 보고로 간다(사람 task 없음)."""
        v = self._require_approval(inst, wi)
        cfg = self._activity_of(wi).get("service") or {}
        clock = _clock(now)
        state = self._state(wi)
        if "settle" not in state:
            secs = engine.iso_duration_seconds(cfg.get("settle") or "PT10M") / max(1.0, self.time_scale)
            plan = {"due_at": engine.now_iso(clock + _td(secs)), "real_s": round(secs, 1), "virtual": cfg.get("settle") or "PT10M"}
            wi["due_date"] = plan["due_at"]
            state = self._save_state(wi, settle=plan)
            self._event(wi, "TEST_RUN_STARTED", "시운전 — 안정 대기", {"plan": plan})
        if effect_parts.parse_time(state["settle"]["due_at"]) > clock:
            return
        if "verdict" not in state:
            if self.hooks.read_tag is None:
                raise ValueError("시운전 값을 읽을 시계열 연결이 없습니다")
            criteria = {t: list(c) for t, c in (cfg.get("criteria") or effect_parts.TEST_RUN_CRITERIA).items()}
            readings = {tag: self.hooks.read_tag(v.get("asset"), tag) for tag in criteria}
            passed, rows = effect_parts.test_run_verdict(criteria, readings)
            state = self._save_state(wi, verdict={"passed": passed, "readings": rows, "at": engine.now_iso(clock)})
            self._event(wi, "TEST_RUN", "시운전 판정", state["verdict"])
        verdict = state["verdict"]
        counter = None
        if verdict["passed"] and cfg.get("reset_counter", True):
            if "counter" not in state:
                wo = v.get(cfg.get("work_order_var") or "work_order")
                item = {"skill": (v.get("chosen_option") or {}).get("id"), "code": "PM_RESET", "name": "운전시간 계수기 리셋", "system": "sys:cmms",
                        "ref": (wo or {}).get("ref") if isinstance(wo, dict) else None, "source": "approved-maintenance"}
                state = self._save_state(wi, counter=self._exec(inst, v, item, "계수기 리셋"))
            counter = state["counter"]
        out = dict(verdict, counter={k: counter.get(k) for k in ("ref", "detail", "after")} if counter else None)
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "TEST_RUN",
                           {"instance": inst["proc_inst_id"], "passed": verdict["passed"],
                            "readings": {r["tag"]: r["value"] for r in verdict["readings"]}}, incident=v.get("incident"))
        self.submit(wi["id"], {"test_run": out, "passed": verdict["passed"]}, by="process", now=now)

    # ---------------------------------------------------------------- 결과 보고
    def _run_report(self, inst: dict, wi: dict, now) -> None:
        """흐름의 결과를 담당자(처리 건 참여자)에게 알리고 기록한다. 사람 task 가 아니다 — 보기만 한다. 정상 · 미달은 사건을 닫는다."""
        v = engine.variables(inst)
        cfg = self._activity_of(wi).get("service") or {}
        outcome = cfg["outcome"]
        level = effect_parts.REPORT_OUTCOMES[outcome]
        context = dict(v, proc_inst_id=inst["proc_inst_id"], proc_inst_name=inst.get("proc_inst_name"), outcome=outcome)
        title = effect_parts.render_report(cfg.get("title") or "{asset} 처리 결과: {outcome}", context)
        summary = effect_parts.render_report(cfg.get("summary") or "", context)
        keep = ("asset", "pattern", "approved_by", "approved_role", "approved_amount", "approved_qty", "approved_supplier", "recovered",
                "passed", "received", "decision_id")
        # C3: 재관측으로 판정한 흐름(A)은 사건의 회복 기준 태그 최신값을 결과 보고 시점에 읽어 측정값으로 싣는다. 재관측 task 의 출력 계약
        # (recovered 하나)은 배포된 정의가 정하므로 바꾸지 않는다 — 결과 보고는 재관측 바로 뒤라 같은 값을 본다.
        measured = dict(v)
        if v.get("recovered") is not None and v.get("incident") and self.hooks.recovery_reading is not None and "reobservation" not in v:
            try:
                reading = self.hooks.recovery_reading(v["incident"])
            except Exception:  # noqa: BLE001 — 측정값은 보조 정보, 읽기 실패로 결과 보고를 막지 않는다
                reading = None
            if reading and reading.get("tag"):
                measured["reobservation"] = reading
        # C3: values = 측정값 목록(포털 결과 보고 카드 계약), facts = 처리 건의 승인 · 판정 값(전의 values dict)
        report = {"outcome": outcome, "level": level, "verdict": level, "title": title, "summary": summary, "by": "sys:process",
                  "at": engine.now_iso(_clock(now)), "values": effect_parts.report_values(measured),
                  "facts": {k: v.get(k) for k in keep if v.get(k) is not None},
                  "refs": {k: (v.get(k) or {}).get("ref") for k in ("work_order", "purchase_order", "goods_receipt", "mcp_receipt")
                           if isinstance(v.get(k), dict) and (v.get(k) or {}).get("ref")}}
        closed = False
        if level != "info" and v.get("incident") and self.hooks.close_incident_result is not None:
            closed = self.hooks.close_incident_result(v["incident"], level, f"{outcome} — {title}")
        report["incident_closed"] = bool(closed)
        self._event(wi, "RESULT_REPORT", "결과 보고", {"report": report}, event_type="task_completed")
        self._after_commit(inbox.notify_participants, self.repo, self.tenant_id, dict(inst), f"[{outcome}] {title}", summary or title)
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "RESULT_REPORT",
                           {"instance": inst["proc_inst_id"], "outcome": outcome, "level": level, "title": title}, incident=v.get("incident"))
        self.submit(wi["id"], {"result_report": report}, by="process", now=now)

    # ---------------------------------------------------------------- 작업지시로 닫힌 사건의 효과 재관측
    def _reobserve_after_work_order(self, inst: dict, wi: dict, now, inc_id: str) -> None:
        """설비 명령 없이 작업지시로 닫힌 사건(정비형 흐름: 예약 → 대기 → 정비 → 확인)의 재관측. 사건의 재관측(machine.on_timer)은 명령 뒤에만
        돌기 때문에, 이전에는 이 task 가 사건 상태 CLOSED 만 보고 recovered=True 를 냈다(실제 관측 없음). 이제 같은 규칙으로 실제로 본다:
        재관측 창(15 시뮬레이션 분 ÷ 배속)을 기다린 뒤 사건의 회복 기준 태그 최신값과 경보 해제(CLEAR)를 읽어, 기준 안 + 해제면 회복.
        값은 기준 안인데 해제가 아직이면 창의 3분의 1씩 최대 3번 늘린다(machine 과 같음)."""
        clock = _clock(now)
        state = self._state(wi)
        if "reobserve" not in state:
            secs = incident_def.REOBSERVE_SIM_S / max(1.0, self.time_scale)
            plan = {"kind": "work_order", "due_at": engine.now_iso(clock + _td(secs)), "window_s": round(secs, 1), "extensions": 0}
            wi["due_date"] = plan["due_at"]
            wi["log"] = (wi.get("log") or "") + f"re-observing after the work order for {secs:.0f} s; "
            state = self._save_state(wi, reobserve=plan)
            self._event(wi, "REOBSERVE_STARTED", "효과 재관측 시작 (작업지시 뒤)", {"plan": plan})
        plan = state["reobserve"]
        if effect_parts.parse_time(plan["due_at"]) > clock:
            return
        reading = self.hooks.recovery_reading(inc_id) if self.hooks.recovery_reading is not None else None
        if not reading or not reading.get("criterion"):
            recovered, reading = False, dict(reading or {}, reason="회복 기준이 없거나 읽을 수 없습니다")
        else:
            inside = bool(reading.get("inside"))
            recovered = inside and bool(reading.get("cleared"))
            if not recovered and inside and plan["extensions"] < REOBSERVE_MAX_EXTENSIONS:
                secs = incident_def.REOBSERVE_SIM_S / max(1.0, self.time_scale) / 3
                plan = dict(plan, due_at=engine.now_iso(clock + _td(secs)), extensions=plan["extensions"] + 1)
                wi["due_date"] = plan["due_at"]
                self._save_state(wi, reobserve=plan)
                self._event(wi, "REOBSERVATION_EXTENDED", "재관측 연장 (값은 기준 안, 경보 해제 대기)", {"reading": reading, "plan": plan})
                return
        v = engine.variables(inst)
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "REOBSERVATION",
                           {"instance": inst["proc_inst_id"], "after": "work_order", "passed": recovered, **{k: reading.get(k) for k in
                            ("tag", "value", "criterion", "cleared")}}, incident=inc_id)
        self._event(wi, "REOBSERVATION", "효과 재관측 판정", {"recovered": recovered, "reading": reading})
        self.submit(wi["id"], {"recovered": recovered}, by="process", now=now)


def _td(seconds: float):
    from datetime import timedelta
    return timedelta(seconds=seconds)
