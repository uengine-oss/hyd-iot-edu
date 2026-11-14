"""C2 (확정 TODO C) 승인 뒤 실행 부품의 처리기 — InstanceRuntime 에 섞는다(effect_parts 는 순수 계약, 여기는 실행).

모든 처리기는 _run_service 가 그 처리 건의 전이 잠금 안에서 부른다(행은 SUBMITTED, consumer '<engine>:service').
  * 끝나면 self.submit(…, by="process") 로 결과를 내고 흐름이 다음으로 간다.
  * 기다리는 부품(시간 대기 · 입고 확인 · 재관측)은 첫 실행에 끝 시각을 행의 draft · due_date 에 저장하고 SUBMITTED 로 둔다.
    폴링(reconcile_services → procdb.waiting_services)은 끝 시각이 지난 행만 다시 부르고 그때 제출한다. 재시작해도 저장한 시각을 쓴다.
  * 시각은 모두 런타임의 주입 시계(self._now)에서 온다.
  * 실패는 ServiceExecutionError(응답 그대로) → _fail. 중복 방지 미확인 외부 쓰기는 즉시 PENDING, 나머지는 3회까지 재시도한다.
  * 바깥 효과(MCP 쓰기 · ERP 발주 · 입고 · 정비 모사)는 처리 건에 사람 승인(approved_by)이 있어야 실행한다(등록 검사에 더한 이중 확인).
    업무 쪽 멱등 키(decision + skill)와 지원하는 MCP의 idempotency_key(처리 건:작업)를 쓴다. 미지원·응답 불명은 재실행을 멈춘다.
"""
from __future__ import annotations

from hydcommon.words import particle
import json
import logging
import uuid
from copy import deepcopy

from . import engine, effect_parts, inbox
from . import definition as incident_def

log = logging.getLogger("process.service_parts")

REOBSERVE_MAX_EXTENSIONS = incident_def.REOBSERVE_MAX_EXTENSIONS


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
        row = {"job_id": job, "todo_id": wi["id"], "proc_inst_id": wi["proc_inst_id"], "crew_type": crew, "event_type": event_type,
               "id": str(uuid.uuid4()), "data": dict(data, name=name)}
        context = getattr(self._local, "service_progress_context", None)
        if crew == "tool" and context is not None:
            from .service_progress import owner_hash
            row["data"].update(system_observation=True, attempt_id=context["attempt_id"], owner_claim_hash=owner_hash(context["consumer"]))
            self.repo.record_service_progress(self.tenant_id, wi["proc_inst_id"], wi["id"], context["consumer"], [row])
            context["observed"] = True
            if data.get('tool_use_id') not in context.setdefault('tool_use_ids', []):
                context['tool_use_ids'].append(data.get('tool_use_id'))
            return  # Durable observations are not replayed as failed business writes.
        self.repo.record_events([row])
        trace = getattr(self._local, "service_trace", None)
        if crew == "tool" and trace is not None:      # 이 시도가 실패해 전이가 되돌려져도 무엇을 불렀고 무엇이 돌아왔는지 남긴다
            trace.append(deepcopy(row))

    def _recover_service_progress(self, wi):
        """A recovered committed claim cannot promise a crashed call's outcome."""
        rows = self.repo.list_events(todo_id=wi['id'], limit=None)
        finished = {r.get('data', {}).get('tool_use_id') for r in rows if r.get('event_type') == 'tool_usage_finished'}
        from .service_progress import owner_hash
        for start in rows:
            data = start.get('data') or {}
            if (start.get('event_type') != 'tool_usage_started' or not data.get('system_observation')
                    or not data.get('tool_use_id') or data['tool_use_id'] in finished):
                continue
            row = {'id': str(uuid.uuid4()), 'job_id': start['job_id'], 'todo_id': wi['id'],
                   'proc_inst_id': wi['proc_inst_id'], 'crew_type': 'tool', 'event_type': 'tool_usage_finished',
                   'data': {'name': '이전 도구 호출의 응답을 확인하지 못했습니다',
                            'content': '처리가 중단되어 이전 호출의 실제 응답은 확인되지 않았습니다. 외부 실행을 되돌렸다는 뜻은 아닙니다.',
                            'output': '이전 호출의 응답이 확인되지 않았습니다.', 'is_error': True,
                            'response_unconfirmed': True, 'interrupted': True, 'system_observation': True,
                            'attempt_id': data['attempt_id'], 'tool_use_id': data['tool_use_id'],
                            'owner_claim_hash': owner_hash(wi['consumer']),
                            'original_owner_claim_hash': data.get('owner_claim_hash')}}
            self.repo.record_service_progress(self.tenant_id, wi['proc_inst_id'], wi['id'], wi['consumer'], [row])
            finished.add(data['tool_use_id'])

    def _close_service_progress(self, context, outcome):
        if not context or not context.get("observed"):
            return
        wi = context["workitem"]
        committed = outcome == "committed"
        row = {"id": str(uuid.uuid4()), "job_id": "SYSTEM_ATTEMPT_COMMITTED" if committed else "SYSTEM_ATTEMPT_ROLLED_BACK",
               "todo_id": wi["id"], "proc_inst_id": wi["proc_inst_id"], "crew_type": "result", "event_type": "task_working",
               "data": {"name": "도구 응답을 처리 건에 반영했습니다" if committed else "이번 시도의 처리를 확정하지 못했습니다",
                        "content": "도구의 실제 응답과 처리 건의 저장 결과를 구분해 기록합니다. 외부 도구의 실행을 되돌렸다는 뜻은 아닙니다.",
                        "system_observation": True, "attempt_id": context["attempt_id"], "transaction_outcome": outcome,
                        "tool_use_ids": context.get('tool_use_ids', []),
                        "attempt_failed": not committed}}
        self.repo.record_service_progress(self.tenant_id, wi["proc_inst_id"], wi["id"], context["consumer"], [row])

    def _unconfirmed_effect(self, wi):
        """A local rollback does not roll back an external write.
        「승인 뒤 MCP 호출」을 시작했는데 그 시도가 커밋되지 않았고 서버가 같은 호출을 알아볼 열쇠(idempotency)도 없으면, 쓰기가 됐는지 알 수 없다 —
        자동 재시도를 멈추고 사람이 외부 결과를 확인하게 한다. 쓰기 요청을 서버에 보내지 않은 것이 확실한 실패(not_sent — 등록 없는 서버 · 꺼진
        서버 · 없는 도구 · 맞지 않는 입력)는 여기에 들지 않는다: 전에는 지워진 서버를 가리키는 단계가 「앞선 외부 쓰기가 됐는지 확인되지
        않아」로 멈춰, 아무것도 보내지 않았는데 외부 결과를 확인하라고 했다(진짜 까닭 「도구 서버가 등록되어 있지 않습니다」가 가려졌다)."""
        rows = self.repo.list_events(todo_id=wi['id'], limit=None)
        committed = {r.get('data', {}).get('attempt_id') for r in rows
                     if r.get('job_id') == 'SYSTEM_ATTEMPT_COMMITTED'}
        finishes = {r.get('data', {}).get('tool_use_id'): r.get('data', {})
                    for r in rows if r.get('event_type') == 'tool_usage_finished'}
        for row in rows:
            data = row.get('data') or {}
            if (row.get('job_id') == 'MCP_EFFECT_CALL'
                    and row.get('event_type') == 'tool_usage_started'
                    and data.get('attempt_id') not in committed
                    and finishes.get(data.get('tool_use_id'), {}).get('idempotent') is not True
                    and finishes.get(data.get('tool_use_id'), {}).get('not_sent') is not True):
                return True
        return False

    def _nothing_sent(self, wi) -> bool:
        """이 「승인 뒤 MCP 호출」 단계의 모든 시도가 쓰기 요청을 서버에 보내지 않고 끝났는가(시도 기록이 없어도 참 — 부르기 전에 멈췄다).
        한 번이라도 보냈거나 보냈는지 모르면 거짓. 다시 수행(rework_runtime)이 「바깥에 낸 일이 없는 단계」를 가르는 데 쓴다."""
        rows = self.repo.list_events(todo_id=wi['id'], limit=None)
        finishes = {r.get('data', {}).get('tool_use_id'): r.get('data', {})
                    for r in rows if r.get('event_type') == 'tool_usage_finished'}
        return all(finishes.get((r.get('data') or {}).get('tool_use_id'), {}).get('not_sent') is True
                   for r in rows if r.get('job_id') == 'MCP_EFFECT_CALL' and r.get('event_type') == 'tool_usage_started')

    def _keep_failed_attempt_record(self) -> None:
        """실패한 시도의 기록을 전이를 되돌린 뒤 따로 남긴다 — 사건 기록과 감사 기록은 상태가 아니라 일지다
        (ProcessGPT processgpt_agent_sdk database.record_events_bulk 도 상태 변경과 따로 남긴다). 상태 변경은 되돌린 그대로 둔다.
          * 도구 호출 사건(서버.도구 · 입력 · 출력/오류) — attempt_failed 표시
          * 감사 기록(MCP_*_FAILED · SKILL_FAILED …, 성공했다면 커밋 뒤 실행됐을 것) — detail 에 attempt_failed
        왜 실패했는지는 이어서 _fail 의 error 사건이 남긴다. 성공한 시도는 이 길을 타지 않아 두 번 남지 않는다."""
        rows = getattr(self._local, "service_trace", None) or []
        if rows:
            self.repo.record_events([dict(r, data=dict(r["data"], attempt_failed=True)) for r in rows])
        for args, kwargs in getattr(self._local, "service_audits", None) or []:
            asset, actor, event, detail, *rest = args
            try:
                self.hooks.audit(asset, actor, event, dict(detail or {}, attempt_failed=True), *rest, **kwargs)
            except Exception:  # noqa: BLE001 — 커밋 뒤 효과와 같은 규칙: 감사 저장 실패가 task 실패 처리를 막지 않는다(로그에 남김)
                log.exception("audit of a failed attempt could not be written: %s", event)

    def _require_approval(self, inst: dict, wi: dict) -> dict:
        v = engine.variables(inst)
        if not v.get("approved_by"):
            raise ValueError(f"'{wi.get('activity_name') or wi['activity_id']}'{particle(wi.get('activity_name') or wi['activity_id'], '은')} 사람 승인 뒤에만 실행합니다 — 이 처리 건에 승인 기록이 없습니다")
        from hydcommon.execution_scope import require_executable
        require_executable(v.get('chosen_option') or {})
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
        """승인 뒤 MCP 호출. G3: extract 가 있으면 결과 JSON 에서 값을 꺼내 함께 낸다(못 꺼내면 이 task 실패 → 정해진 재시도 뒤 PENDING.
        재시도는 다시 부른다 — 읽기는 해가 없고, 쓰기는 같은 idempotency_key 로 부른다). effect: false(읽기 확인)는 승인 없이,
        읽기 판정을 통과한 도구만 부른다."""
        activity = self._activity_of(wi)
        cfg = activity.get("service") or {}
        read_only = effect_parts.is_read_check(activity)
        v = engine.variables(inst) if read_only else self._require_approval(inst, wi)
        extract = cfg.get("extract") or {}
        receipt, result = self._call_mcp(inst, wi, v, cfg, f"{inst['proc_inst_id']}:{wi['id']}", now, read_only=read_only)
        out = {cfg.get("output") or "mcp_receipt": receipt}
        if extract:
            try:
                values = effect_parts.extract_values(extract, result)
            except ValueError as e:
                raise ValueError(f"'{wi.get('activity_name') or wi['activity_id']}' ({cfg['server']}.{cfg['tool']}): {e}") from e
            self._event(wi, "MCP_RESULT_VALUES", "MCP 결과에서 값을 꺼냄", {
                "values": values, "extract": deepcopy(extract),
                "content": ", ".join(f"{k} = {json.dumps(x, ensure_ascii=False)} (경로 {extract[k]['path']})" for k, x in values.items())})
            out.update(values)
        self.submit(wi["id"], out, by="process", now=now)

    def _send_notice(self, inst: dict, wi: dict, values: dict, mail, now) -> dict | None:
        """작업 끝의 메일 공지. 같은 키의 중복 방지 응답이 확인된 경우만 실패 후 자동 재시도한다."""
        spec = effect_parts.notice_spec(mail)
        if spec is None:
            return None
        state = self._state(wi)
        if "notice" in state:
            return state["notice"]
        receipt, _ = self._call_mcp(inst, wi, values, spec, f"{inst['proc_inst_id']}:{wi['id']}:notice", now)
        self._save_state(wi, notice=receipt)
        return receipt

    def _call_mcp(self, inst: dict, wi: dict, v: dict, cfg: dict, key: str, now, *, read_only: bool = False) -> tuple[dict, dict]:
        """(영수증, 도구 결과 — mcp_check.shape_result 모양). read_only 면 읽기 경로(hooks.mcp_read: 호출 직전 읽기 판정)로 부른다."""
        context = dict(v, proc_inst_id=inst["proc_inst_id"], proc_inst_name=inst.get("proc_inst_name"),
                       task_name=wi.get("activity_name"))                     # 이름은 effect_parts.MCP_CONTEXT_VALUES 와 같다(등록 검사가 읽는다)
        try:
            arguments = effect_parts.render(cfg.get("arguments") or {}, context)
        except KeyError as e:
            raise ValueError(f"MCP 인자 틀의 값 {e.args[0]}{particle(e.args[0], '이')} 처리 건에 없습니다 — 빈 값으로 보내지 않습니다") from e
        server, tool = cfg["server"], cfg["tool"]
        use_id = f"{key}:{int(wi.get('retry') or 0)}"
        context = getattr(self._local, "service_progress_context", None)
        if context is not None:
            use_id = f"{key}:{context['attempt_id']}:{int(wi.get('retry') or 0)}"
        raw_tool = f"mcp__{server}__{tool}"
        # 이벤트 본문: HYD 도구 호출 기록(mcp_calls: tool · input · output)과 제품 화면(tool_name · args · result · is_error) 두 이름을 함께 둔다
        job, label = ("MCP_READ_CALL", "읽기 확인 MCP 호출") if read_only else ("MCP_EFFECT_CALL", "승인 뒤 MCP 호출")
        self._event(wi, job, label, {"tool": raw_tool, "tool_name": tool, "tool_use_id": use_id, "input": arguments,
                                                              "args": arguments, "idempotency_key": key}, event_type="tool_usage_started", crew="tool")
        try:
            res = self.hooks.mcp_read(server, tool, arguments) if read_only else self.hooks.mcp_call(server, tool, arguments, key)
        except Exception:
            self._event(wi, job, label + " 호출 실패", {"tool": raw_tool, "tool_name": tool, "tool_use_id": use_id,
                        "output": "도구 호출이 정상 응답을 반환하지 않았습니다.", "result": "도구 호출이 정상 응답을 반환하지 않았습니다.",
                        "is_error": True, "attempt_failed": bool(context and context.get('owns_transition')), "error_kind": "invocation_exception"}, event_type="tool_usage_finished", crew="tool")
            raise
        result = res.get("result") or {}
        failed = res.get("status") != "ok" or result.get("is_error")
        self._event(wi, job, label + " 결과", {"tool": raw_tool, "tool_name": tool, "tool_use_id": use_id, "output": result.get("text") or res.get("error"),
                                                                  "result": result.get("text") or res.get("error"), "idempotent": res.get("idempotent") is True,
                                                                  # 쓰기 요청을 서버에 보내지 않았다(mcp_check.call_effect 의 sent · instance_mode._runtime_server) — _unconfirmed_effect 가 읽는다
                                                                  "not_sent": (not read_only) and res.get("sent") is False,
                                                                  "is_error": bool(failed), "attempt_failed": bool(failed and context and context.get('owns_transition'))}, event_type="tool_usage_finished", crew="tool")
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", ("MCP_READ_FAILED" if failed else "MCP_READ_CALLED") if read_only else ("MCP_EFFECT_FAILED" if failed else "MCP_EFFECT_CALLED"),
                           {"instance": inst["proc_inst_id"], "server": server, "tool": tool, "idempotency_key": key,
                            "error": res.get("error")}, incident=v.get("incident"))
        if failed:
            from .instances import ServiceExecutionError
            raise ServiceExecutionError({"error": res.get("error") or (result.get("text") or "")[:300] or "MCP 도구가 오류를 돌려줬습니다",
                                         "server": server, "tool": tool, "status": res.get("status"), "error_kind": res.get("error_kind")})
        receipt = {"server": server, "tool": tool, "arguments": res.get("arguments", arguments), "idempotency_key": key,
                   "idempotent": res.get("idempotent"), "result": result.get("text"), "called_at": engine.now_iso(self._now(now))}
        return receipt, result

    # ---------------------------------------------------------------- ERP 발주
    def _run_purchase_order(self, inst: dict, wi: dict, now) -> None:
        v = self._require_approval(inst, wi)
        missing = [k for k in ("approved_supplier", "approved_part_no", "approved_qty", "approved_amount") if v.get(k) is None]
        if missing:
            raise ValueError("승인 경로가 확정한 발주 값이 없습니다(" + ", ".join(missing) + ") — 발주 후보를 사람이 승인한 처리 건에서만 발주합니다")
        opt = v.get("chosen_option") or {}
        item = {"skill": opt.get("id"), "sop": opt.get("sopId"), "code": "PR_CREATE", "name": "ERP 발주", "system": "sys:erp",
                "value": v["approved_supplier"], "part_no": v["approved_part_no"], "qty": v["approved_qty"],
                "amount": v["approved_amount"], "source": "approved-purchase"}
        res = self._exec(inst, v, item, "ERP 발주")
        notice = self._send_notice(inst, wi, dict(v, purchase_order=res), (self._activity_of(wi).get("service") or {}).get("mail"), now)
        self.submit(wi["id"], {"purchase_order": dict(res, notice=notice) if notice else res}, by="process", now=now)

    # ---------------------------------------------------------------- 시간 대기
    def _run_wait(self, inst: dict, wi: dict, now) -> None:
        clock = self._now(now)
        state = self._state(wi)
        if "wait" not in state:
            cfg = self._activity_of(wi).get("service") or {}
            try:
                plan = effect_parts.wait_for(cfg, engine.variables(inst), clock, self.time_scale)
            except KeyError as e:
                raise ValueError(f"기다릴 시각 값 {e.args[0]}{particle(e.args[0], '이')} 처리 건에 없습니다") from e
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
            state = self._save_state(wi, wait={"due_at": engine.now_iso(self._now(now)), "real_s": 0, "label": "즉시 시행", "immediate": True})
            self._event(wi, "WAIT_SKIPPED", "즉시 시행 — 예정된 정비 시간 대기 없음", {"window": (v.get("chosen_option") or {}).get("window")})
        if cfg.get("until"):                       # 예정된 정비 시간까지 먼저 기다린다(시간 대기와 같은 계산 · 같은 수업 압축)
            clock = self._now(now)
            if "wait" not in state:
                # 즉시 시행 카드가 아닌데 그 값이 없거나 비었거나 시각이 아니다 — 언제 정비할지 모르는 채로 바로 정비하지 않는다(시점을 지어내지 않음).
                # 값이 아예 없을 때와 비어 있을 때 모두 같은 까닭을 말한다(작업지시 등록 단계와 같은 문장 — work_orders.no_maintenance_time)
                from .work_orders import no_maintenance_time
                try:
                    plan = effect_parts.wait_for({"until": cfg["until"], "label": "예정된 정비 시간까지"}, v, clock, self.time_scale)
                except KeyError as e:
                    raise ValueError(f"예정된 정비 시간 값 {e.args[0]}{particle(e.args[0], '이')} 처리 건에 없습니다. " + no_maintenance_time(v.get("chosen_option"))) from e
                except ValueError as e:
                    raise ValueError(f"예정된 정비 시간 값 {cfg['until']}{particle(cfg['until'], '을')} 시각으로 읽지 못했습니다({e}). "
                                     + no_maintenance_time(v.get("chosen_option"))) from e
                wi["due_date"] = plan["due_at"]
                state = self._save_state(wi, wait=plan)
                self._event(wi, "WAIT_STARTED", "예정된 정비 시간까지 대기", {"plan": plan})
            if not effect_parts.due(state["wait"], clock):
                return
        wo = v.get(cfg.get("work_order_var") or "work_order")
        opt = v.get("chosen_option") or {}
        if isinstance(wo, dict) and wo.get("ref") and "completed" not in state:
            sop = cfg.get("sop") or opt.get("sopId")
            if "standard" not in state and self.hooks.enterprise_read is not None:
                # 작업지시 완료는 그 SOP 의 표준 작업(정비 시스템 CMMS 의 부품 · 수량)만큼 부품을 소모한다. 표준 작업이 없는 SOP(수업 문서 밖의 새
                # 절차)는 소모 없이 완료된다 — 완료하기 전에 읽어 두고, 없으면 그 사실을 정비 완료 공지 · 처리 기록 · 결과 값에 남긴다(말없이 넘기지 않는다)
                rows = (self.hooks.enterprise_read("task_standards", {"asset": v.get("asset")}) or {}).get("records") or []
                state = self._save_state(wi, standard={"sop": sop, "found": any(isinstance(r, dict) and r.get("sop") == sop for r in rows)})
            item = {"skill": opt.get("id"), "code": "WO_COMPLETE", "name": "정비 요청 완료", "system": "sys:cmms", "ref": wo["ref"],
                    "sop": sop, "source": "approved-maintenance"}
            state = self._save_state(wi, completed=self._exec(inst, v, item, "정비 수행 모사"))
        if "restored" not in state:
            # 무엇을 고쳤는가: 흐름이 대상 부품을 적었으면 그것, 아니면 승인한 조치 방법(SOP)이 지식에서 다루는 원인의 외란 변수 · 구성 요소만
            # (maintenance_scope). 전에는 흐름 A 가 component: cooler 를 적어 두어 어떤 조치를 승인해도 쿨러 결함이 지워졌다 — 틀린 조치도 「회복」.
            scope = None
            if not cfg.get("component"):
                scope = maintenance_scope(self.hooks.query_cypher, cfg.get("sop") or opt.get("sopId"))
            res = (self.hooks.plant_restore(v.get("asset"), cfg["component"]) if scope is None
                   else self.hooks.plant_restore(v.get("asset"), None, targets=[t["id"] for t in scope["targets"]]))
            if not isinstance(res, dict) or res.get("ok") is False:
                from .instances import ServiceExecutionError
                raise ServiceExecutionError(res if isinstance(res, dict) else {"error": "설비 시뮬레이터 응답이 없습니다"})
            state = self._save_state(wi, restored=res, scope=scope)
        standard = state.get("standard") or {}
        parts_note = (f"정비 시스템(CMMS)에 {standard.get('sop') or '이 절차'}의 표준 작업(부품 · 수량)이 없어 부품 소모를 기록하지 않았습니다 — "
                      "이 정비에 쓴 부품이 있으면 재고가 실제와 다릅니다") if state.get("completed") and standard.get("found") is False else None
        scope = state.get("scope")
        fixed = maintenance_sentence(scope, state["restored"], cfg.get("component"))
        notice = (f"{v.get('asset')} 정비 완료 — " + ((state.get("completed") or {}).get("detail") or "정비 요청 없이 수행")
                  + f". {fixed}" + (f". {parts_note}" if parts_note else ""))
        # component = 흐름이 직접 적은 부품(없으면 None — 고친 대상은 scope.targets 와 notice 가 말한다)
        out = {"asset": v.get("asset"), "component": cfg.get("component") or None,
               "work_order": (wo or {}).get("ref") if isinstance(wo, dict) else None,
               "completed": state.get("completed"), "restored": state.get("restored"), "notice": notice,
               **({"scope": scope} if scope is not None else {}),
               **({"parts_note": parts_note} if parts_note else {}),
               "done_at": engine.now_iso(self._now(now))}
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
        clock = self._now(now)
        state = self._state(wi)
        if "wait" not in state:
            after = po.get("after") or {}
            lead_d, delay_d = after.get("lead_d"), after.get("delay_d") or 0
            if lead_d is None and self.hooks.enterprise_read is not None:
                facts = (self.hooks.enterprise_read("purchase_order", {"ref": po["ref"]}) or {}).get("facts") or {}
                lead_d, delay_d = facts.get("lead_d"), facts.get("delay_d") or 0
            if lead_d is None:
                # 입고 예정 시각의 출처는 공급사 리드타임 하나다 — 없으면 0일(바로 입고)로 지어내지 않는다
                raise ValueError(f"발주 {po['ref']} 의 공급사 리드타임(입고까지 걸리는 날 수)을 발주 영수증에도 구매 · 재고 관리 시스템에도 찾지 못해 "
                                 "입고 예정 시각을 정할 수 없습니다 — 구매 · 재고 관리에서 그 발주의 리드타임을 확인한 뒤 이 단계를 다시 실행합니다")
            plan = effect_parts.wait_plan((float(lead_d) + float(delay_d)) * 86400, clock, self.time_scale, label="입고 예정까지",
                                          source=f"{po['ref']} 리드타임 {lead_d}일" + (f" + 지연 {delay_d:g}일" if delay_d else ""))
            plan.update(lead_d=lead_d, delay_d=float(delay_d))
            wi["due_date"] = plan["due_at"]
            state = self._save_state(wi, wait=plan)
            self._event(wi, "RECEIPT_WAIT", "입고 대기 시작", {"purchase_order": po["ref"], "plan": plan})
        if not effect_parts.due(state["wait"], clock):
            return
        if "receipt" not in state and self.hooks.enterprise_read is not None:
            # 공급사가 납기 지연을 알렸으면(ERP skill:delay-delivery — 결함 시뮬레이션의 [공급사 납기 지연]) 늦어진 입고 예정까지 더 기다린다.
            # 그 사이 이 단계에 붙은 납기 초과 타이머가 울리면 흐름은 지연 결과 보고로 간다(수업 흐름 C 의 B_late)
            facts = (self.hooks.enterprise_read("purchase_order", {"ref": po["ref"]}) or {}).get("facts") or {}
            delay_d = float(facts.get("delay_d") or 0)
            plan = state["wait"]
            if delay_d > float(plan.get("delay_d") or 0):
                extra = effect_parts.wait_plan((delay_d - float(plan.get("delay_d") or 0)) * 86400, clock, self.time_scale)
                plan = dict(plan, due_at=extra["due_at"], delay_d=delay_d, real_s=round(float(plan.get("real_s") or 0) + extra["real_s"], 1),
                            source=f"{po['ref']} 리드타임 {plan.get('lead_d')}일 + 지연 {delay_d:g}일")
                wi["due_date"] = plan["due_at"]
                state = self._save_state(wi, wait=plan)
                self._event(wi, "RECEIPT_DELAYED", "공급사 납기 지연 — 입고 예정이 늦어짐", {"purchase_order": po["ref"], "plan": plan})
                self._after_commit(inbox.notify_participants, self.repo, self.tenant_id, dict(inst), "공급사 납기 지연",
                                   f"발주 {po['ref']}의 입고 예정이 {delay_d:g}일 늦어졌습니다(공급사 통보) — 리드타임 {plan.get('lead_d')}일 + 지연 {delay_d:g}일")
                return
        if "receipt" not in state:
            item = {"skill": (v.get("chosen_option") or {}).get("id"), "code": "GR_CONFIRM", "name": "입고 · 검수", "system": "sys:erp",
                    "ref": po["ref"], "source": "approved-purchase", "basis": receipt_basis(po, state["wait"])}
            state = self._save_state(wi, receipt=self._exec(inst, v, item, "입고 확인"))
        if "stock_after" not in state and self.hooks.enterprise_read is not None:
            # C3: 입고 뒤 재고(가용 · 재주문점)를 결과 보고에 싣는다 — '재고 보충 필요' 표시가 꺼졌는지의 근거
            part_no = (state["receipt"].get("after") or {}).get("part_no") or (po.get("after") or {}).get("part_no") or v.get("approved_part_no")
            if not part_no:
                raise ValueError(f"입고 뒤 재고를 읽을 부품 번호가 없습니다 — 발주 {po['ref']} 영수증 · 승인 값(approved_part_no)")
            # 읽기 실패는 이 task 의 실패(재시도 · PENDING, 사유 보존)다 — 입고 거래는 이미 저장돼 재시도에서 다시 하지 않는다
            facts = (self.hooks.enterprise_read("spare_stock", {"part": part_no}) or {}).get("facts")
            if not facts:
                raise ValueError(f"ERP 재고에 {part_no} 행이 없습니다 — 입고 뒤 가용 재고를 확인할 수 없습니다")
            state = self._save_state(wi, stock_after={k: facts.get(k) for k in ("part_no", "on_hand", "reserved", "on_order", "available",
                                                                                 "reorder_point", "below_reorder_point") if k in facts})
        receipt = dict(state["receipt"], stock_after=state.get("stock_after") or None)
        # 입고 완료인가는 업무 시스템의 입고 기록이 말한다(검수에서 걸러 반품한 수량이 없어야 한다 — 발주 수량 전부 · 로트 기록 · 검사 합격).
        # 고른 공급사의 불량률이 여기서 결과로 돌아온다: 반품이 있으면 받은 것만 재고에 들어가고 흐름은 미달 결과 보고로 간다.
        rejected = (receipt.get("after") or {}).get("rejected_qty")
        if isinstance(rejected, bool) or not isinstance(rejected, (int, float)):
            raise ValueError(f"입고 기록 {receipt.get('ref')} 에 검수 불합격 수량(rejected_qty)이 없어 입고 완료인지 판정할 수 없습니다")
        complete = rejected == 0
        if complete and v.get("incident") and self.hooks.close_incident_effect is not None:
            self.hooks.close_incident_effect(v["incident"], {"ok": True, "ref": receipt.get("ref"), "detail": receipt.get("detail"), "kind": "goods_receipt"})
        notice = f"{'입고 확인' if complete else '부분 입고'} — {receipt.get('detail') or receipt.get('ref')}"
        self._event(wi, "GOODS_RECEIVED", "입고 확인" if complete else "부분 입고 — 검수 불합격분 반품", {"receipt": receipt})
        self._after_commit(inbox.notify_participants, self.repo, self.tenant_id, dict(inst), "입고 확인" if complete else "부분 입고", notice)
        self.submit(wi["id"], {"goods_receipt": receipt, "received": complete}, by="process", now=now)

    # ---------------------------------------------------------------- 시운전 확인 (정비 뒤)
    def _run_test_run(self, inst: dict, wi: dict, now) -> None:
        """안정 시간(가상 · 배속만) 뒤 기준 태그의 최신값을 읽어 판정한다. 통과면 CMMS 운전시간 계수기 리셋 · 다음 기한 기록(효과).
        미달이면 리셋하지 않고 passed=False — 흐름의 분기가 '미달' 결과 보고로 간다(사람 task 없음)."""
        v = self._require_approval(inst, wi)
        cfg = self._activity_of(wi).get("service") or {}
        clock = self._now(now)
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
                "passed", "received", "decision_id", "approval", "approval_reason", "approved_option")   # 끝 셋: 캡스톤 G1 사람 승인(안 고르기)
        # C3: 재관측으로 판정한 흐름(A)은 사건의 회복 기준 태그 최신값을 결과 보고 시점에 읽어 측정값으로 싣는다. 재관측 task 의 출력 계약
        # (recovered 하나)은 배포된 정의가 정하므로 바꾸지 않는다 — 결과 보고는 재관측 바로 뒤라 같은 값을 본다.
        # P5 (audit2): 명령 거절 · ACK 시간 초과 · 재시작으로 ESCALATED 된 사건은 재관측 미달이 아니다 — 흐름의 보고 틀(예: '재관측 기준 미달')
        # 대신 실제 사유를 요약으로 싣고, 틀 문구는 template_summary 로 남긴다. 명령이 실행되지 않았으면 재관측 측정값도 붙이지 않는다.
        cause = incident_def.escalation_cause(v.get("incident_reason")) if v.get("incident_outcome") == "ESCALATED" else None
        if cause:
            template_summary, summary = summary, cause[0]
        measured, values_error = dict(v), None
        if (v.get("recovered") is not None and v.get("incident") and self.hooks.recovery_reading is not None and "reobservation" not in v
                and (cause is None or cause[1])):
            try:
                reading = self.hooks.recovery_reading(v["incident"])
            except Exception as e:  # noqa: BLE001 — 측정값은 보조 정보라 결과 보고는 낸다. 못 읽은 사실과 까닭은 보고에 싣는다
                reading, values_error = None, f"회복 기준 측정값을 읽지 못했습니다 — {type(e).__name__}: {str(e)[:200]}"
            if reading and reading.get("tag"):
                measured["reobservation"] = reading
        # C3: values = 측정값 목록(포털 결과 보고 카드 계약), facts = 처리 건의 승인 · 판정 값(전의 values dict)
        report = {"outcome": outcome, "level": level, "verdict": level, "title": title, "summary": summary, "by": "sys:process",
                  "at": engine.now_iso(self._now(now)), "values": effect_parts.report_values(measured),
                  "facts": {k: v.get(k) for k in keep if v.get(k) is not None},
                  "refs": {k: (v.get(k) or {}).get("ref") for k in ("work_order", "purchase_order", "goods_receipt", "mcp_receipt")
                           if isinstance(v.get(k), dict) and (v.get(k) or {}).get("ref")}}
        if values_error:
            report["values_error"] = values_error
        if cause:
            report["cause"] = {"incident_state": "ESCALATED", "reason": v.get("incident_reason"), "text": cause[0], "reobserved": cause[1]}
            report["template_summary"] = template_summary
            report["facts"]["incident_reason"] = v.get("incident_reason")
        closed = False
        if level != "info" and v.get("incident") and self.hooks.close_incident_result is not None:
            # 반려는 사건의 사유(on_reject 의 reason 과 같은 자리)가 곧 사람이 적은 반려 사유다 — 요약(사유 틀)을 함께 싣는다
            note = f"{outcome} — {title}" + (f": {summary}" if level == "rejected" and summary else "")
            closed = self.hooks.close_incident_result(v["incident"], level, note)
        report["incident_closed"] = bool(closed)
        recipients = list(inst.get("participants") or [])
        for notice in cfg.get("notify", []):
            if engine.eval_condition(notice["when"], v):
                recipients.append(notice["role"])
        # 포털 알림은 DB 쓰기다. 결과 보고에는 바깥 효과가 없어 알림을 보고 결과와 한 트랜잭션으로 저장한다(알림이 실패하면 함께 되돌아가 재시도).
        # 정비 수행 · 입고 확인의 알림은 커밋 뒤다 — 그 단계의 바깥 효과(작업지시 완료 · 입고 거래) 기록이 알림 실패로 되돌아가면 재시도가
        # 같은 거래를 다시 부르기 때문이다.
        report["notification_count"] = inbox.notify_participants(
            self.repo, self.tenant_id, dict(inst, participants=recipients),
            f"[{outcome}] {title}", summary or title)
        self._event(wi, "RESULT_REPORT", "결과 보고", {"report": report}, event_type="task_completed")
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "RESULT_REPORT",
                           {"instance": inst["proc_inst_id"], "outcome": outcome, "level": level, "title": title}, incident=v.get("incident"))
        self.submit(wi["id"], {"result_report": report}, by="process", now=now)

    # ---------------------------------------------------------------- 재관측 (한 벌 — 명령 뒤 · 작업지시 뒤)
    AFTER_LABEL = {"command": "설비 명령 뒤", "work_order": "정비 요청 뒤"}

    def _reobserve(self, inst: dict, wi: dict, now, inc_id: str, *, after: str, cmd_id: str | None = None) -> None:
        """재관측 규칙 하나(A-02): 창(15 시뮬레이션 분 ÷ 배속)의 마감을 이 행의 draft · due_date 에 저장하고 폴링이 판정한다 — process 가 다시
        켜져도 저장한 마감으로 이어 간다(재관측은 읽기라 다시 해도 안전). 마감이 지나면 사건의 회복 기준 태그 최신값과 경보 해제(CLEAR)를 읽어
        기준 안 + 해제면 회복. 값은 기준 안인데 해제가 아직이면 창의 3분의 1씩 최대 3번 늘린다(감지기 해제 지연 60 s, A072).
        after='command': 명령을 낸 사건(RE_OBSERVING)이다 — 판정을 사건에 적는다(RESOLVED · ESCALATED). 'work_order': 명령 없이 작업지시로 닫힌
        사건(정비형 흐름)이다 — 사건은 이미 닫혔고 이 단계의 회복 여부만 낸다."""
        clock = self._now(now)
        state = self._state(wi)
        if "reobserve" not in state:
            secs = incident_def.REOBSERVE_SIM_S / max(1.0, self.time_scale)
            plan = {"kind": after, "cmd_id": cmd_id, "started_at": engine.now_iso(clock), "due_at": engine.now_iso(clock + _td(secs)),
                    "window_s": round(secs, 1), "extensions": 0}
            wi["due_date"] = plan["due_at"]
            wi["log"] = (wi.get("log") or "") + f"효과 확인 시작({self.AFTER_LABEL[after]}) — {secs:.0f}초 동안 설비 값을 지켜봅니다; "
            state = self._save_state(wi, reobserve=plan)
            self._event(wi, "REOBSERVE_STARTED", f"효과 확인 시작 ({self.AFTER_LABEL[after]})", {"plan": plan})
        plan = state["reobserve"]
        if effect_parts.parse_time(plan["due_at"]) > clock:
            return
        # A161-G3: with the window start, the reading carries the values seen during the window (reading.series)
        reading = self.hooks.recovery_reading(inc_id, since=plan["started_at"], after=after) if self.hooks.recovery_reading is not None else None
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
                self._event(wi, "REOBSERVATION_EXTENDED", "효과 확인 연장 (값은 기준 안, 경보 해제 대기)", {"reading": reading, "plan": plan})
                if after == "command" and self.hooks.reobservation_extended is not None:
                    self.hooks.reobservation_extended(inc_id, plan["cmd_id"], reading, plan["extensions"], secs)
                return
        if after == "command":
            if self.hooks.reobservation_verdict is None:
                raise ValueError("효과 확인 판정을 사건에 적는 기능이 연결되지 않았습니다")
            if not self.hooks.reobservation_verdict(inc_id, plan["cmd_id"], recovered, reading, plan["extensions"]):
                # 그 사이 사건이 다른 길로 갔다(재작업으로 명령이 바뀜 등) — 이 창의 판정을 쓰지 않고 사건의 지금 상태를 따른다
                snap = self.hooks.incident_snapshot(inc_id) or {}
                if snap.get("state"):
                    self.on_incident_update(snap["state"], inc_id, False, now)
                return
        else:
            v = engine.variables(inst)
            self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "REOBSERVATION",
                               {"instance": inst["proc_inst_id"], "after": "work_order", "passed": recovered, **{k: reading.get(k) for k in
                                ("tag", "value", "criterion", "cleared")}}, incident=inc_id)
        self._event(wi, "REOBSERVATION", f"효과 확인 판정 ({self.AFTER_LABEL[after]})", {"recovered": recovered, "reading": reading,
                                                                                         "extensions": plan["extensions"]})
        self.submit(wi["id"], {"recovered": recovered}, by="process", now=now)


# ---------------------------------------------------------------- 정비 수행이 고치는 것 (지식 지도에서 읽는다)
#: 승인한 조치 방법(Skill = SOP)과 그것이 근본 조치 · 예방 조치로 이어진 고장 유형. 즉시 완화(MITIGATED_BY)는 원인을 없애는 조치가 아니라 세지 않는다
#: (수업 문서 HM-8.7 「완화에 성공해도 원인은 남아 있다」).
SCOPE_SKILL_Q = ("MATCH (k:Skill {sopId: $sop}) RETURN k.name AS name, [(k)-[:ADDRESSES]->(c:Cause) | c.id] AS addressed, "
                 "[(fm:FailureMode)-[:REMEDIED_BY|PREVENTED_BY]->(k) | fm.id] AS failure_modes")
#: 그 고장 유형들의 모든 원인과, 원인이 흔드는 상태 변수. 흔드는 변수가 외란(kind = disturbance)이 아니면 그 변수에 영향을 주는 외란 변수까지 본다
#: (예: 팬 구동 불량 → 팬 진동 ← 팬 베어링 마모도).
SCOPE_CAUSES_Q = ("MATCH (c0:Cause)-[:CAUSES]->(fm0:FailureMode) WHERE c0.id IN $addressed OR fm0.id IN $fms WITH DISTINCT fm0 AS fm "
                  "MATCH (c:Cause)-[:CAUSES]->(fm) RETURN c.id AS cause, c.name AS cause_name, fm.id AS fm, fm.name AS fm_name, "
                  "[(fm)-[:OCCURS_IN]->(comp:Component) | {id: comp.id, name: comp.name}] AS components, "
                  "[(c)-[:DISTURBS]->(sv:StateVariable) | {id: sv.id, name: sv.name, kind: sv.kind, "
                  "upstream: [(d:StateVariable {kind: 'disturbance'})-[:INFLUENCES]->(sv) | {id: d.id, name: d.name}]}] AS disturbs "
                  "ORDER BY cause")


def maintenance_scope(query, sop: str | None) -> dict:
    """승인한 조치 방법(SOP)이 지식에서 실제로 다루는 것 → 정비 수행이 가상 설비에서 되돌릴 대상. 흐름 정의에 부품을 손으로 적지 않는다.

    다루는 원인 = 그 조치 방법이 원인 한정(ADDRESSES)으로 이어진 원인. 한정이 없으면 그 조치가 근본 조치 · 예방 조치인 고장 유형의 모든 원인
    (스키마 v2: 한정 없는 조치는 그 고장 유형 어느 원인에도 쓰는 조치다 — templates/t2_skills.cypher 와 같은 뜻).
    되돌릴 대상 = 다루는 원인이 흔드는 외란 변수(Cause -DISTURBS-> StateVariable). 그 고장 유형의 지식이 원인별 외란 변수를 하나도 말하지 않으면
    고장 유형이 생기는 구성 요소(FailureMode -OCCURS_IN-> Component)로 넓힌다 — 지식이 말하는 가장 좁은 단위를 쓴다.
    지식의 이름(sv:* · comp:*)을 가상 설비의 외란 변수로 잇는 표는 ot/plant-sim plantsim.plant.COMPONENTS 한 곳이다.
    돌려줌 {sop, name, causes[{id, name}], targets[{id, name, via}], why} — targets 가 비면 why 가 그 까닭이다(정비는 가상 설비를 바꾸지 않는다)."""
    out = {"sop": sop, "name": None, "causes": [], "targets": [], "why": None}
    if not sop:
        return dict(out, why="승인한 카드에 조치 방법(SOP) 번호가 없어 이 정비가 무엇을 고치는지 지식에서 찾지 못했습니다")
    rows = query(SCOPE_SKILL_Q, sop=sop)
    if not rows:
        return dict(out, why=f"지식 지도에 조치 방법 {sop}{particle(sop, '이')} 없어 이 정비가 무엇을 고치는지 찾지 못했습니다")
    skill = rows[0]
    out["name"] = skill.get("name")
    addressed, fms = list(skill.get("addressed") or []), list(skill.get("failure_modes") or [])
    if not fms:
        return dict(out, why=f"지식 지도에서 {sop}{particle(sop, '은')} 어느 고장 유형의 근본 조치 · 예방 조치로도 이어져 있지 않습니다(즉시 완화 조치는 원인을 없애지 않습니다)")
    causes = query(SCOPE_CAUSES_Q, addressed=addressed, fms=fms)
    handled = [c for c in causes if (c["cause"] in addressed if addressed else c["fm"] in fms)]
    if not handled:
        return dict(out, why=f"지식 지도에 {sop}{particle(sop, '이')} 막거나 고치는 고장 유형의 원인이 없어 이 정비가 무엇을 고치는지 찾지 못했습니다")

    def disturbances(c):
        return [d for sv in c.get("disturbs") or [] for d in ([sv] if sv.get("kind") == "disturbance" else sv.get("upstream") or [])]
    by_cause = {c["fm"] for c in causes if disturbances(c)}        # 원인별 외란 변수를 말하는 고장 유형
    targets, unknown = {}, []
    for c in handled:
        found = disturbances(c)
        for d in found:
            targets.setdefault(d["id"], {"id": d["id"], "name": d.get("name"), "via": "cause"})
        if not found and c["fm"] not in by_cause:
            for comp in c.get("components") or []:
                targets.setdefault(comp["id"], {"id": comp["id"], "name": comp.get("name"), "via": "component"})
        elif not found:
            unknown.append(c.get("cause_name") or c["cause"])
    out["causes"] = [{"id": c["cause"], "name": c.get("cause_name")} for c in handled]
    out["targets"] = list(targets.values())
    if not out["targets"]:
        names = " · ".join(c["name"] or c["id"] for c in out["causes"])
        out["why"] = f"{sop}{particle(sop, '이')} 다루는 원인({names})이 설비의 어느 상태를 바꾸는지 지식 지도에 없습니다"
    return out


def maintenance_sentence(scope: dict | None, restored: dict, component: str | None) -> str:
    """정비 완료 공지의 「무엇을 고쳤는가」 한 문장. 정비는 사람이 한 일을 가상 설비에서 흉내 낸 것이라는 것과, 고친 대상이 어디서 왔는지를 말한다."""
    changed = bool((restored or {}).get("targets"))
    if scope is None:                       # 흐름이 대상 부품을 직접 적었다(component). 적지 않은 채 범위도 없는 것은 이 규칙 전에 복구를 끝낸 행뿐이다
        what = f"흐름 설정이 정한 대상({component})" if component else "설비 전체"
        return (f"가상 설비에서 {what}{particle(what, '을')} 정상으로 되돌렸습니다" if changed
                else f"{what}{particle(what, '은')} 가상 설비에서 이미 정상이라 바꾼 것이 없습니다")
    if not scope.get("targets"):
        return f"{scope['why']} — 가상 설비의 상태는 바꾸지 않았습니다"
    causes = " · ".join(c.get("name") or c["id"] for c in scope["causes"])
    names = " · ".join(t.get("name") or t["id"] for t in scope["targets"])
    missing = [t for t in scope["targets"] if t["id"] in ((restored or {}).get("not_modeled") or [])]
    if changed:
        return f"승인한 조치 방법 {scope['sop']}{particle(scope['sop'], '이')} 다루는 원인({causes})에 따라 가상 설비의 {names}{particle(names, '을')} 정상으로 되돌렸습니다"
    if missing and len(missing) == len(scope["targets"]):
        return f"승인한 조치 방법 {scope['sop']}{particle(scope['sop'], '이')} 다루는 {names}{particle(names, '은')} 가상 설비가 모형으로 갖지 않아 설비 상태를 바꾸지 않았습니다"
    return (f"승인한 조치 방법 {scope['sop']}{particle(scope['sop'], '이')} 다루는 원인({causes})의 {names}{particle(names, '은')} 가상 설비에서 이미 정상이라 바꾼 것이 없습니다 — "
            "설비에 다른 결함이 있으면 그대로 남아 있습니다")


def receipt_basis(po: dict, plan: dict) -> str:
    """입고 거래에 싣는 시간 근거(업무 DB 입고 기록에 남는다 — ERP 의 입고 예정 시각과 실제 입고 시각이 왜 다른지).
    업무 시스템의 입고 예정(expected_at)은 업무 시각(발주 + 리드타임 일)이고, 처리 엔진은 그 대기를 배속 × 대기 압축으로 줄여 기다린다."""
    after = po.get("after") if isinstance(po.get("after"), dict) else {}
    lead, delay = plan.get("lead_d", after.get("lead_d")), float(plan.get("delay_d") or 0)
    planned = f"리드타임 {lead}일" + (f" + 공급사 지연 {delay:g}일" if delay else "")
    return (f"업무 시간 {planned}을 실제 {float(plan.get('real_s') or 0):g}초로 줄여 기다린 뒤 입고했습니다"
            f"(배속 {float(plan.get('time_scale') or 1):g} × 대기 압축 {float(plan.get('compression') or 1):g})")


def _td(seconds: float):
    from datetime import timedelta
    return timedelta(seconds=seconds)
