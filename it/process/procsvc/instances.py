"""Instance runtime (PROCESS_MODE=instance): the process instance owns the case; the agent and the people are tasks inside it.

The runtime is the completion service of ProcessGPT in miniature (docs/handoff/REPO_GAP.md §1):

    alerts RAISE ─▶ instance RUNNING, every activity TODO, task:diagnose IN_PROGRESS (+ Incident for the PLC path)
    agent worker ─▶ fetch_pending_task (IN_PROGRESS · agent_mode COMPLETE) … save_task_result ─▶ SUBMITTED
    person       ─▶ POST /submit (form output) ─▶ SUBMITTED            (task:select additionally checks the ontology role)
    service      ─▶ reached ⇒ SUBMITTED ─▶ the runtime executes it (incident command · re-observation · CMMS work order)
    engine       ─▶ poll_once(): claim SUBMITTED rows ─▶ engine.process_submitted ─▶ DONE (+ next IN_PROGRESS) or PENDING
    timers       ─▶ fire_timeouts(): event work items past due_date ─▶ fire_event ─▶ attached task CANCELLED ─▶ escalate
    end event    ─▶ instance COMPLETED; ProcessInstance · WorkItem projected into the ontology (Execution layer)

All IO goes through small callables (hooks) so this module is unit-testable with MemoryRepo and fakes.
"""
from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable

from hydcommon.timeutil import now_iso, parse_iso
from hydcommon.process_contracts import pinned_form, validate_output
from . import engine, inbox
from . import definition as incident_def
from .definition_registry import validate_definition, PROTECTED_OUTPUTS
from .execution_graph import INSTANCE_Q, EXECUTION_Q, DELETE_INSTANCE_Q, definition_projection
from .projection_receipt import digest as projection_digest,require as require_projection_receipt
from .approval_delivery import ApprovalDelivery
from .rework_runtime import ReworkRuntime
from .effect_compensation import EffectRuntime
from .current_approval import ApprovalReviewRequired

log = logging.getLogger("process.instances")

MAX_RETRIES = 3                            # stop retrying after three failures; block for recovery, never imply success
ENGINE_CONSUMER = "process-engine"


def workitem_transition(fn):
    @wraps(fn)
    def locked(self, item, *args, **kwargs):
        row=item if isinstance(item,dict) else self.repo.get_workitem(item)
        if not row or row.get('tenant_id')!=self.tenant_id:raise KeyError('no such work item')
        with self._transition(row['proc_inst_id']):
            return fn(self,item,*args,**kwargs)
    return locked


class ServiceExecutionError(RuntimeError):
    """Keep the actual tool response with the failure instead of submitting it as successful output."""
    def __init__(self, result: dict):
        self.result = result
        super().__init__(str(result.get("error") or result.get("detail") or "service did not report success"))


@dataclass
class Hooks:
    """IO the runtime needs from the process service. Every field has a harmless default so tests can pass only what they use."""
    new_incident: Callable[..., dict | None] = lambda alert, recovery_policy=None: None
    update_incident_card: Callable[[str, dict], None] = lambda inc_id, card: None  # the agent's guide card becomes the incident's card
    approve_commands: Callable[[str, list[dict], str], dict] = lambda inc_id, commands, by: {}   # machine.on_approve wrapper -> cmd
    incident_state: Callable[[str], str | None] = lambda inc_id: None             # current Incident state (idempotent command issue)
    incident_snapshot: Callable[[str], dict | None] = lambda inc_id: None        # state/cleared restored from the Incident store
    decision_option: Callable[[str, str], dict | None] = lambda decision_id, option_id: None     # process 'book' lookup
    get_decision: Callable[[str], dict | None] | None = None
    approve_decision: Callable[[str, str, str, str, str], dict] = lambda did, option, by, role, reason: {"enterprise": [], "ot": []}
    preview_decision: Callable | None = None
    approve_review: Callable | None = None
    validate_approval: Callable[[dict], None] = lambda payload: None
    deliver_approval: Callable[[dict], list[dict]] | None = None
    record_approval: Callable[[dict], None] = lambda row: None
    approval_effects: Callable | None = None  # authoritative read only; absent means unknown
    rework_effects: Callable | None = None
    reopen_incident: Callable | None = None     # (inc_id, request_id, by, role, reason, effects) → machine.on_rework_reopen (A072)
    exec_compensation: Callable | None = None   # (request dict) → enterprise compensation transaction (A072)
    exec_enterprise: Callable[[str, dict], dict] = lambda decision_id, item: {"ok": False, "error": "no enterprise hook"}
    record_cypher: Callable[..., list] = lambda q, **params: []
    query_cypher: Callable[..., list] = lambda q, **params: []          # read the projected Execution layer back (monitoring)
    audit: Callable[..., None] = lambda asset, actor, event, detail, incident=None: None


class InstanceRuntime(ApprovalDelivery, ReworkRuntime, EffectRuntime):
    def __init__(self, repo, defn: engine.Definition, hooks: Hooks, time_scale: float = 20.0, tenant_id: str = "hyd",
                 consumer: str = ENGINE_CONSUMER):
        self.repo, self.defn, self.hooks, self.time_scale, self.tenant_id, self.consumer = repo, defn, hooks, time_scale, tenant_id, consumer
        self._local=threading.local()
        self.repo.upsert_proc_def(defn.raw, tenant_id)

    @contextmanager
    def _transition(self, pid):
        active=getattr(self._local,'transition',None)
        if active is not None:
            if active['pid']!=pid:raise RuntimeError('cross-instance nested transition')
            yield
            return
        state={'pid':pid,'effects':[]}
        try:
            with self.repo.instance_transaction(self.tenant_id,pid):
                self._local.transition=state
                yield
        finally:
            self._local.transition=None
        # Reached service rows are durable SUBMITTED work before external IO.
        # A crash here is recovered by polling, not by replaying an in-memory queue.
        for fn,args,kwargs in state['effects']:
            try:fn(*args,**kwargs)
            except Exception:log.exception('post-commit effect failed for %s',pid)

    def _after_commit(self,fn,*args,**kwargs):
        active=getattr(self._local,'transition',None)
        if active is None:return fn(*args,**kwargs)
        active['effects'].append((fn,args,kwargs))

    def _check_deadline(self,wi,inst,defn,now):
        if inst.get('status')!='RUNNING':raise ValueError('instance is not running')
        clock=now or datetime.now(timezone.utc)
        event_ids={e['id'] for e in defn.attached_events(wi['activity_id'])}
        if any(w['activity_id'] in event_ids and w['status']=='IN_PROGRESS'
               and w.get('due_date') and parse_iso(w['due_date'])<=clock
               for w in self.repo.list_workitems(proc_inst_id=wi['proc_inst_id'],limit=None)):
            raise ValueError('task deadline expired')

    def definition_for(self, inst: dict) -> engine.Definition:
        if inst and inst.get('tenant_id') != self.tenant_id:
            raise KeyError('no such instance')
        if not inst or not inst.get("proc_def_version"):
            raise LookupError("인스턴스의 고정 정의 버전이 없습니다")
        row = self.repo.get_proc_def(inst["proc_def_id"], inst["tenant_id"], version=inst["proc_def_version"])
        if not row or not row.get("definition"):
            raise LookupError(f"고정 정의를 찾을 수 없습니다: {inst['proc_def_id']}@{inst['proc_def_version']}")
        return engine.Definition.from_dict(row["definition"])

    def register_definition(self, raw: dict) -> dict:
        defn = validate_definition(raw)
        self.repo.upsert_proc_def(defn.raw, self.tenant_id)
        return self.repo.get_proc_def(defn.id, self.tenant_id, version=defn.raw['version'])

    def preview_rework(self, proc_inst_id: str, workitem_id: str):
        """Read one consistent local snapshot; external effects still need live review."""
        from . import rework
        with self._transition(proc_inst_id):
            inst = self.repo.get_instance(proc_inst_id)
            if not inst or inst.get('tenant_id') != self.tenant_id:
                raise KeyError('no such instance')
            return self._rework_proposal(inst, workitem_id)

    def definition_for_workitem(self, wi):
        if not wi or wi.get('tenant_id') != self.tenant_id:
            raise KeyError('no such work item')
        inst = self.repo.get_instance(wi['proc_inst_id'])
        defn = self.definition_for(inst)
        if wi.get('proc_def_id') != inst['proc_def_id'] or wi.get('version') != inst['proc_def_version']:
            raise ValueError('작업과 인스턴스의 정의 버전이 다릅니다')
        if wi['activity_id'] not in defn.activities and wi['activity_id'] not in defn.events:
            raise ValueError('정의 버전에 없는 작업입니다')
        return defn

    def workitem_view(self, wid):
        wi = self.repo.get_workitem(wid)
        defn = self.definition_for_workitem(wi)
        activity = defn.activities.get(wi['activity_id']) or {}
        tool = activity.get('tool') or ''
        form = pinned_form(defn.raw, tool)
        source = 'definition-version' if form is not None else 'legacy-live'
        if form is None and tool.startswith('formHandler:'):
            form = self.repo.get_form(tool.split(':',1)[1], self.tenant_id)
        inst = self.repo.get_instance(wi['proc_inst_id'])
        values = engine.variables(inst)
        inputs = {key:deepcopy(values.get(key)) for key in activity.get('inputData', [])}
        snapshot = (inst.get('flow_state') or {}).get('input_snapshots', {}).get(wid)
        if snapshot is not None:
            inputs = deepcopy(snapshot['inputs'])
        elif activity.get('inputBindings'):
            inputs = {key:value for key,value in inputs.items() if key not in activity['inputBindings']}
        return wi | {'tool':tool, 'form':form, 'form_source':source, 'inputs':inputs,
                     'input_sources':deepcopy(snapshot['sources']) if snapshot else None,
                     'input_state':'captured' if snapshot else ('waiting' if activity.get('inputBindings') else 'current'),
                     'events':self.repo.list_events(todo_id=wid)}

    def start_definition(self, def_id, version, event_id, values=None, alert=None, name=None, now=None, _alert_policy=None):
        if not isinstance(event_id,str) or not event_id.strip():
            raise ValueError('중복 실행을 구분할 event_id가 필요합니다')
        if not isinstance(version,str) or not version.strip():
            raise ValueError('실행할 정의 버전을 지정하세요')
        defn = self.definition_for({'proc_def_id':def_id,'proc_def_version':version,'tenant_id':self.tenant_id})
        if defn.start_events()[0].get('eventDefinition') == 'message' and alert is None:
            raise ValueError('메시지 시작 정의에는 경보 입력이 필요합니다')
        from . import alert_policy
        policy=_alert_policy
        if alert is not None:
            policy=policy or alert_policy.for_definition(defn.raw,alert.get('pattern'))
            if policy['route']=='triage':
                if (def_id,version)!=(policy['target']['definition'],policy['target']['version']):
                    raise ValueError('이 정의는 경보를 지원하지 않습니다. 지정된 사람 검토 경로를 사용하세요')
                alert_policy.require_triage(defn)
        values = dict(values or {})
        if (PROTECTED_OUTPUTS | {'decision_id'}).intersection(values):
            raise ValueError('시작 변수로 Incident/승인 결과를 주입할 수 없습니다')
        key = json.dumps([self.tenant_id,def_id,event_id])
        with self.repo.event_transaction(key):
            if self.repo.find_event_instance(self.tenant_id,def_id,event_id):
                return None
            if alert is not None:
                if not alert.get('asset') or not alert.get('alertId'):
                    raise ValueError('alert에는 asset과 alertId가 필요합니다')
                inc = (self.hooks.new_incident(alert,recovery_policy=policy)
                       if defn.raw.get('alertPolicy') or policy['route']=='triage' else self.hooks.new_incident(alert))
                values.update(asset=alert['asset'],alert=alert,alert_id=alert['alertId'],
                              pattern=alert.get('pattern'),incident=(inc or {}).get('id'))
            inst = engine.new_instance(defn, values, name=name, now=now, tenant_id=self.tenant_id)
            inst['start_event_id'] = event_id
            adv = engine.start(defn, inst, now=now, time_scale=self.time_scale)
            self.repo.insert_instance(inst)
            inbox.apply_advance(self, inst, adv)
            self.repo.insert_workitems(adv.created)
            self.repo.update_instance(inst)
        self.hooks.audit(values.get('asset','-'),'process','INSTANCE_STARTED',
                         {'instance':inst['proc_inst_id'],'event_id':event_id,'definition':def_id,'version':version},
                         incident=values.get('incident'))
        self._project(inst)
        return inst

    # ---------------------------------------------------------------- start
    def find_by_alert(self, alert_id: str) -> dict | None:
        return self.repo.find_event_instance(self.tenant_id, self.defn.id, alert_id)

    def alert_policy(self, pattern):
        from . import alert_policy
        defn=self.definition_for({'proc_def_id':self.defn.id,'tenant_id':self.tenant_id,'proc_def_version':self.defn.raw['version']})
        return alert_policy.for_definition(defn.raw,pattern)

    def on_alert_raise(self, alert: dict, now: datetime | None = None) -> dict | None:
        """Message start event: one RAISE alert opens one instance (duplicates of the same alertId are ignored)."""
        alert_id, asset = alert.get("alertId"), alert.get("asset")
        if not alert_id or not asset:
            return None
        policy=self.alert_policy(alert.get('pattern'));target=policy['target']
        return self.start_definition(target['definition'],target['version'],alert_id,alert=alert,now=now,_alert_policy=policy)

    def receive_alert(self, alert: dict, policy: dict) -> dict:
        """Resume one durable source receipt using its original immutable policy."""
        from . import alert_policy
        from .source_inbox import digest
        raw=self.definition_for({'tenant_id':self.tenant_id,'proc_def_id':policy['definition'],
                                 'proc_def_version':policy['version']}).raw
        if digest(alert_policy.for_definition(raw,alert.get('pattern')))!=digest(policy):
            raise ValueError('접수 당시 정의와 원천 경보 정책이 일치하지 않습니다')
        target=policy['target']
        def stored():
            return self.repo.find_event_instance(self.tenant_id,target['definition'],alert['alertId'])
        inst=stored()
        if inst is None:
            self.start_definition(target['definition'],target['version'],alert['alertId'],alert=alert,_alert_policy=policy)
            inst=stored()
        if inst is None:raise RuntimeError('접수한 경보의 인스턴스 저장을 확인할 수 없습니다')
        values=engine.variables(inst)
        if inst.get('proc_def_version')!=target['version'] or values.get('alert')!=alert:
            raise ValueError('기존 인스턴스의 원천 경보 또는 고정 버전이 접수 기록과 다릅니다')
        inc_id=values.get('incident')
        if not inc_id or self.hooks.incident_snapshot(inc_id) is None:
            raise RuntimeError('인스턴스에 연결된 원천 사건 저장을 확인할 수 없습니다')
        return {'instance':inst['proc_inst_id'],'incident':inc_id,'definition':target}

    # ---------------------------------------------------------------- turning work in
    @workitem_transition
    def submit(self, workitem_id: str, output: dict | None, by: str | None = None, now: datetime | None = None) -> dict:
        """A person / a service turns a work item in: SUBMITTED, then the engine processes it right away (the polling loop
        would otherwise pick it up within its interval). Returns {instance, workitem, reached, ended, pending}."""
        wi = self.repo.get_workitem(workitem_id)
        if not wi:
            raise KeyError(workitem_id)
        inst = self.repo.get_instance(wi["proc_inst_id"])
        defn = self.definition_for_workitem(wi)
        self._check_deadline(wi,inst,defn,now)
        form = pinned_form(defn.raw, (defn.activities.get(wi['activity_id']) or {}).get('tool'))
        if form is not None:
            validate_output(form, output)
            from .manual_extraction import validate_result
            validate_result(form, inst, output)
        engine.submit(defn, inst, wi, output, now=now)
        wi["consumer"] = self.consumer
        if by:
            wi["log"] = (wi.get("log") or "") + f"submitted by {by}; "
        self.repo.update_workitem(wi)
        return self.process_workitem(wi, now=now)

    @workitem_transition
    def process_workitem(self, wi: dict, now: datetime | None = None) -> dict:
        """The engine's turn for one SUBMITTED row (the product's handle_workitem): judge, DONE/PENDING, reach the next."""
        fresh=self.repo.get_workitem(wi['id'])
        inst = self.repo.get_instance(wi["proc_inst_id"])
        if (not fresh or fresh['status']!='SUBMITTED' or fresh.get('consumer')!=wi.get('consumer')
                or inst.get('status')!='RUNNING'):
            return {'instance':inst,'workitem':fresh,'reached':[],'ended':None,'pending':False,'skipped':True}
        wi=fresh
        approval = self.repo.get_approval(wi['id'], self.tenant_id)
        if approval is not None and approval['status'] != 'DELIVERED':
            wi['consumer'] = 'approval:waiting'
            self.repo.update_workitem(wi)
            return {'instance':inst, 'workitem':wi, 'reached':[], 'ended':None,
                    'pending':True, 'approval_status':approval['status']}
        defn = self.definition_for_workitem(wi)
        form = pinned_form(defn.raw, (defn.activities.get(wi['activity_id']) or {}).get('tool'))
        if form is not None:
            validate_output(form, wi.get('output'))
            from .manual_extraction import validate_result, CORRECTABLE_CONTRACTS
            try:
                validate_result(form, inst, wi.get('output'))
            except ValueError as rejected:
                if form.get('contract') not in CORRECTABLE_CONTRACTS:
                    raise
                # A077: a cited-extraction defect goes back to the agent as feedback (same CLI session) instead of
                # re-judging the identical output three times. Bounded like the product's validator loop.
                return self._return_for_correction(wi, inst, str(rejected))
        if (int(inst.get('rework_generation') or 0) > 0 and engine.variables(inst).get('incident')
                and 'decision_id' in (wi.get('output') or {})):
            from .decision_scope import validate_output as validate_decision_output
            decision = self.hooks.get_decision(wi['output']['decision_id']) if self.hooks.get_decision else None
            validate_decision_output(inst, wi, decision)
        rows = self.repo.list_workitems(proc_inst_id=wi["proc_inst_id"], limit=None)
        rows = [r if r["id"] != wi["id"] else wi for r in rows]
        adv = engine.process_submitted(defn, inst, wi, rows, now=now, time_scale=self.time_scale)
        output = wi.get("output") or {}
        if not adv.pending and isinstance(output.get("guide_card"),dict) and engine.variables(inst).get("incident"):
            # This is required durable input for later approval, not a best-effort
            # projection. Persist it before committing DONE/next task. If the PG
            # commit then fails, replay writes the same guide; no command is sent.
            self.hooks.update_incident_card(engine.variables(inst)["incident"],output["guide_card"])
        inbox.apply_advance(self, inst, adv)      # U5: 사람 단계 → 업무분장으로 담당자 해석(저장 전) · 알림(커밋 뒤)
        for row in adv.updated:
            self.repo.update_workitem(row)
        self.repo.insert_workitems(adv.created)
        self.repo.update_instance(inst)
        out = {"instance": inst, "workitem": wi, "reached": adv.reached, "ended": adv.ended, "pending": adv.pending}
        if adv.pending:
            self._after_commit(self.hooks.audit,engine.variables(inst).get("asset", "-"), "process", "TASK_PENDING",
                             {"instance": inst["proc_inst_id"], "task": wi["activity_id"], "log": wi.get("log")}, incident=engine.variables(inst).get("incident"))
            return out
        self._after_commit(self.hooks.audit,engine.variables(inst).get("asset", "-"), wi.get("user_id") or "process", "TASK_COMPLETED",
                         {"instance": inst["proc_inst_id"], "task": wi["activity_id"], "next": [w["activity_id"] for w in adv.reached], "ended": adv.ended},
                         incident=engine.variables(inst).get("incident"))
        self._after_commit(self._project,inst)
        for row in adv.reached:
            if row["status"] == "SUBMITTED" and row.get("agent_orch") == engine.PROCESS_ORCH:
                self._after_commit(self._run_service,inst,row,now)
        return out

    def poll_once(self, now: datetime | None = None) -> int:
        """Completion polling: claim SUBMITTED rows nobody holds and process them; a failure counts a retry, the third one
        blocks as PENDING with its error for recovery. An explicit current-condition
        refusal stops immediately for new judgment and consent."""
        delivered = self.reconcile_approvals(now)
        claimed = self.repo.claim_submitted(self.consumer, tenant_id=self.tenant_id)
        for wi in claimed:
            try:
                if wi.get("agent_orch") == engine.PROCESS_ORCH and not wi.get("output"):
                    inst = self.repo.get_instance(wi["proc_inst_id"])
                    self._run_service(inst, wi, now)
                else:
                    self.process_workitem(wi, now=now)
            except Exception as e:  # every failure releases or blocks the claim
                self._fail(wi, e, now)
        serviced = self.reconcile_services(now)
        aborted = self.reconcile_terminal_incidents(now)
        self.reconcile_projections()
        return delivered+len(claimed)+serviced+aborted

    CORRECTION_ROUNDS = 3   # product process_validator: bounded correction rounds, then stop with the best-known state

    def _return_for_correction(self, wi: dict, inst: dict, reason: str) -> dict:
        """A077 (meeting L253~302): the extraction proposal failed the citation/structure contract. Hand the exact reason
        back to the agent as feedback and let it correct the *same* proposal in the same CLI session; after
        CORRECTION_ROUNDS rejections the task blocks as PENDING for a person, with every reason kept."""
        feedback = wi.get('feedback') if isinstance(wi.get('feedback'), dict) else {}
        history = list(feedback.get('history') or []) + [reason]
        attempt = len(history)
        wi['log'] = (wi.get('log') or '') + f'[Rejected {attempt}/{self.CORRECTION_ROUNDS}] {reason[:300]}; '
        wi['feedback'] = {'kind': 'validation', 'attempt': attempt, 'history': history,
                          'text': (f'추출 제안이 원문 검증에서 거부되었습니다({attempt}/{self.CORRECTION_ROUNDS}): {reason}\n'
                                   '입력 데이터의 이전 proposal을 고쳐 같은 형식으로 다시 제출하세요. 인용(anchor)은 page.text의 '
                                   '정확한 부분 문자열과 좌표여야 하며, 모든 페이지에 page_reviews가 있어야 합니다. '
                                   '원문에 없는 절차를 추가하지 마세요.')}
        wi['draft'] = deepcopy(wi.get('output'))          # the previous proposal (and its cliagents_session_id) stays readable
        wi['output'] = None
        if attempt >= self.CORRECTION_ROUNDS:
            wi.update(status='PENDING', consumer=None, end_date=None)
            event = {'name': '추출 제안 거부 · 사람 확인 필요', 'recovery': 'human_review', 'attempt': attempt, 'reasons': history}
        else:
            wi.update(status='IN_PROGRESS', draft_status='FB_REQUESTED', consumer=None, end_date=None)
            event = {'name': '추출 제안 거부 · 에이전트 재작업', 'recovery': 'agent_correction', 'attempt': attempt, 'reasons': history}
        self.repo.update_workitem(wi)
        self.repo.record_events([{'job_id': 'TASK_REJECTED', 'todo_id': wi['id'], 'proc_inst_id': wi['proc_inst_id'], 'crew_type': 'agent',
                                  'event_type': 'error', 'data': event}])
        self._after_commit(self._project, inst)
        return {'instance': inst, 'workitem': wi, 'reached': [], 'ended': None, 'pending': True, 'correction': event}

    @workitem_transition
    def _fail(self, wi: dict, err: Exception, now: datetime | None) -> None:
        fresh = self.repo.get_workitem(wi["id"]) or wi
        if fresh['status']!='SUBMITTED' or fresh.get('consumer')!=wi.get('consumer'):
            return
        retry = int(fresh.get("retry") or 0) + 1
        review_required = isinstance(err, ApprovalReviewRequired)
        msg = f"{type(err).__name__}: {str(err)[:300]}"
        log.warning("%s %s failed (%d/%d): %s", fresh["proc_inst_id"], fresh["activity_id"], retry, MAX_RETRIES, msg)
        fresh.update(retry=retry, consumer=None, log=(fresh.get("log") or "") + f"[Error] {msg}; ")
        if review_required or retry >= MAX_RETRIES:
            fresh.update(status="PENDING", end_date=None)
        self.repo.update_workitem(fresh)
        self.repo.record_events([{"job_id": "TASK_REVIEW_REQUIRED" if review_required else "TASK_ERROR", "todo_id": fresh["id"], "proc_inst_id": fresh["proc_inst_id"], "crew_type": "agent",
                                  "event_type": "error", "data": {"name": "현재 조건 변경 · 새 판단과 승인 필요" if review_required else "엔진 오류", "raw_error": msg, "retry": retry,
                                                                  "recovery": "new_judgment_and_consent" if review_required else "bounded_retry",
                                                                  "assessment": deepcopy(err.report) if review_required else None,
                                                                  "service_result": err.result if isinstance(err, ServiceExecutionError) else None}}])
        inst = self.repo.get_instance(fresh["proc_inst_id"])
        if inst:
            self._after_commit(self._project,inst)

    # ---------------------------------------------------------------- the human task: pick one action card (form select_card)
    def _review_scope(self, wi, inst):
        values = engine.variables(inst)
        return {'kind':'instance','tenant':self.tenant_id,'instance':wi['proc_inst_id'],'workitem':wi['id'],
                'asset':values.get('asset'),'incident':values.get('incident')}

    def _require_new_generation_decision(self, inst, decision_id):
        if not int(inst.get('rework_generation') or 0):
            return
        values = engine.variables(inst)
        source = (inst.get('variable_sources') or {}).get('decision_id') or {}
        producer = self.repo.get_workitem(source.get('id')) if source.get('id') else None
        if (not decision_id or values.get('decision_id') != decision_id or not producer
                or producer['status'] != 'DONE' or producer.get('generation') != inst['rework_generation']):
            raise ValueError('새 세대의 판단 작업이 완료된 뒤 새 카드를 검토·승인하세요')
        from .decision_scope import validate_output as validate_decision_output
        decision = self.hooks.get_decision(decision_id) if self.hooks.get_decision else None
        validate_decision_output(inst, producer, decision)

    @workitem_transition
    def preview_choice(self, workitem_id, decision_id, option_id, parameters, now=None):
        wi = self.repo.get_workitem(workitem_id)
        if self._tool_of(wi) != 'formHandler:select_card' or wi['status'] != 'IN_PROGRESS':
            raise ValueError('진행 중인 카드 선택 작업에서만 새 예측을 검토할 수 있습니다')
        inst = self.repo.get_instance(wi['proc_inst_id'])
        self._check_deadline(wi,inst,self.definition_for(inst),now)
        self._require_new_generation_decision(inst, decision_id)
        if engine.variables(inst).get('decision_id') != decision_id:
            raise ValueError('decision does not belong to this instance')
        if self.hooks.preview_decision is None:
            raise ValueError('예측 검토 기능이 연결되지 않았습니다')
        review = self.hooks.preview_decision(decision_id,option_id,parameters,self._review_scope(wi,inst))
        self._check_deadline(wi,inst,self.definition_for(inst),now)
        return review

    @workitem_transition
    def select(self, workitem_id: str, decision_id: str, option_id: str, by: str, role: str, reason: str = "",
               fan_pct: float | None = None, load_pct: float | None = None, now: datetime | None = None,
               review_id: str | None = None) -> dict:
        """Permission and feasibility are judged by the decision (ontology roles: Skill -APPROVED_BY-> Role), then the form
        output {chosen_skill, chosen_skill_kind} is submitted and gw:control decides the path."""
        wi = self.repo.get_workitem(workitem_id)
        if not wi or self._tool_of(wi) != "formHandler:select_card":
            raise KeyError(workitem_id)
        if wi["status"] != "IN_PROGRESS":
            raise ValueError(f"{wi['activity_id']} is {wi['status']}")
        inst = self.repo.get_instance(wi["proc_inst_id"])
        self._check_deadline(wi,inst,self.definition_for(inst),now)
        values = engine.variables(inst)
        self._require_new_generation_decision(inst, decision_id)
        if values.get("decision_id") not in (None, decision_id):
            raise ValueError("decision does not belong to this instance")
        opt = deepcopy(self.hooks.decision_option(decision_id, option_id))
        if opt is None:
            raise ValueError("unknown option")
        person = inbox.check_actor(self.repo, self.tenant_id, by, role)   # U5: "나"로 승인하면 그 역할의 구성원인지(아니면 403)
        # Validation must be pure: this hook returns an approved COPY, never mutates the external book.
        if review_id:
            if self.hooks.approve_review is None:
                raise ValueError('검토본 승인 기능이 연결되지 않았습니다')
            plan = self.hooks.approve_review(decision_id,option_id,by,role,reason,review_id,self._review_scope(wi,inst))
        else:
            plan = self.hooks.approve_decision(decision_id, option_id, by, role, reason)
        opt = plan.get('option') or opt
        commands = _commands_of(opt, fan_pct, load_pct)
        payload = {'plan':plan, 'decision':decision_id, 'option':option_id, 'by':by, 'role':role,
                   'reason':reason, 'commands':commands, 'asset':values.get('asset'), 'incident':values.get('incident')}
        self.hooks.validate_approval(payload)
        self._check_deadline(wi,inst,self.definition_for(inst),now)
        kind = "control" if any(a.get("kind") == "command" for a in opt.get("actions") or []) else "work_order"
        engine.set_variables(self.definition_for(inst), inst, {"commands": commands,
                                               "chosen_option": dict(deepcopy(opt), kind=kind),
                                               "approved_by": by, "approved_role": role})
        if role and role not in (inst.get("participants") or []):      # a higher role may take the operator's task: they took part too
            inst.setdefault("participants", []).append(role)
        if person and person not in inst.setdefault("participants", []):                # U5: 승인한 사람도 참여자 — 종결 알림을 받는다
            inst["participants"].append(person)
        self.repo.update_instance(inst)
        approval = {'todo_id':wi['id'], 'proc_inst_id':wi['proc_inst_id'], 'tenant_id':self.tenant_id,
                    'decision_id':decision_id, 'payload':payload, 'status':'PENDING', 'attempts':0,
                    'results':[], 'error':None, 'history':[{'status':'PENDING', 't':engine.now_iso(now), 'by':by, 'role':role}]}
        self.repo.insert_approval(approval)
        defn = self.definition_for(inst)
        output = {'chosen_skill':opt.get('id'), 'chosen_skill_kind':kind}
        form = pinned_form(defn.raw, self._tool_of(wi))
        if form is not None:
            validate_output(form, output)
        engine.submit(defn, inst, wi, output, now=now)
        wi['consumer'] = 'approval:waiting'
        wi['log'] = (wi.get('log') or '') + f'approval accepted by {by}; delivery pending; '
        self.repo.update_workitem(wi)
        # This deadline measures the person's response, not external delivery time.
        attached = {e['id'] for e in defn.attached_events(wi['activity_id'])}
        for timer in self.repo.list_workitems(proc_inst_id=wi['proc_inst_id'], limit=None):
            if timer['activity_id'] in attached and timer['status']=='IN_PROGRESS':
                timer.update(status='CANCELLED', end_date=engine.now_iso(now), log='human approval accepted; delivery tracked separately')
                self.repo.update_workitem(timer)
        inst['current_activity_ids'] = [a for a in inst.get('current_activity_ids', []) if a not in attached]
        self.repo.update_instance(inst)
        self.repo.record_events([{'job_id':'APPROVAL_ACCEPTED', 'todo_id':wi['id'], 'proc_inst_id':wi['proc_inst_id'],
            'crew_type':'human', 'event_type':'task_working', 'data':{'name':'승인 접수', 'decision':decision_id, 'by':by, 'role':role}}])
        self._after_commit(self.deliver_approval, wi['id'], now)
        return {'instance':inst, 'workitem':wi, 'accepted':True, 'approval_status':'PENDING',
                'plan':{k:v for k,v in plan.items() if k!='_snapshot'}, 'enterprise_results':[]}

    # ---------------------------------------------------------------- a person closes an agent task that cannot continue (A082)
    HUMAN_CLOSE_END_EVENT = 'closed-by-human'

    @workitem_transition
    def cancel_agent_task(self, workitem_id: str, by: str, reason: str, now: datetime | None = None) -> dict:
        """A097 (process-gpt-vue3 FormWorkItem: a person cancels a running agent task → draft_status CANCELLED): the worker
        sees the mark on its next check (runner._cancelled), stops the CLI, releases its claim and records task_cancelled.
        The row then waits for the person — close it (A082) or let a rework/re-judgment start a new generation."""
        wi = self.repo.get_workitem(workitem_id)
        if not wi:
            raise KeyError(workitem_id)
        if not isinstance(by, str) or not by.strip() or not isinstance(reason, str) or not reason.strip():
            raise ValueError('취소하는 사람과 사유가 필요합니다')
        if not wi.get('agent_mode') or not wi.get('agent_orch'):
            raise PermissionError('에이전트 작업만 취소할 수 있습니다')
        if not (wi['status'] == 'IN_PROGRESS' and wi.get('draft_status') == 'STARTED' and wi.get('consumer')):
            raise ValueError('워커가 실행 중인 에이전트 작업(STARTED)만 취소할 수 있습니다')
        now = now or datetime.now(timezone.utc)
        wi.update(draft_status='CANCELLED', log=(wi.get('log') or '') + f'[Cancel requested by {by.strip()}] {reason.strip()[:300]}; ')
        self.repo.update_workitem(wi)
        self.repo.record_events([{'job_id': 'TASK_CANCEL_REQUESTED', 'todo_id': wi['id'], 'proc_inst_id': wi['proc_inst_id'], 'crew_type': 'human',
                                  'event_type': 'task_cancelled', 'timestamp': engine.now_iso(now),
                                  'data': {'name': '실행 취소 요청', 'goal': f'{by.strip()}: {reason.strip()[:300]}', 'by': by.strip(),
                                           'consumer': wi.get('consumer')}}])
        return dict(workitem=wi['id'], status=wi['status'], draft_status='CANCELLED', consumer=wi.get('consumer'))

    def close_agent_task(self, workitem_id: str, by: str, reason: str, now: datetime | None = None) -> dict:
        """A082: PENDING after bounded retries/corrections, or a worker run that died (draft FAILED) — the product's task
        cancel for the HYD case. Human tasks and live tasks are refused; an instance whose Incident is still open is
        refused too (use re-judgment / escalation). The row is CANCELLED with the reason kept; when nothing else is open
        the instance ends with the technical end event 'closed-by-human', never a business end event."""
        wi = self.repo.get_workitem(workitem_id)
        if not wi:
            raise KeyError(workitem_id)
        if not isinstance(by, str) or not by.strip() or not isinstance(reason, str) or not reason.strip():
            raise ValueError('닫는 사람과 사유가 필요합니다')
        if not wi.get('agent_mode') or not wi.get('agent_orch'):
            raise PermissionError('에이전트 작업만 이 경로로 닫습니다. 사람 작업은 제출로, 서비스 작업은 사건 경과·에스컬레이션으로 끝납니다')
        stuck = wi['status'] == 'PENDING' or (wi['status'] == 'IN_PROGRESS' and wi.get('draft_status') in ('FAILED', 'CANCELLED'))
        if not stuck:
            raise ValueError('멈춘 에이전트 작업(PENDING, 실행 실패 또는 취소된 실행)만 닫을 수 있습니다')
        inst = self.repo.get_instance(wi['proc_inst_id'])
        if not inst or inst.get('status') != 'RUNNING':
            raise ValueError('실행 중인 인스턴스의 작업만 닫을 수 있습니다')
        inc_id = engine.variables(inst).get('incident')
        if inc_id:
            state = self.hooks.incident_state(inc_id)
            if state is not None and state not in incident_def.TERMINAL:
                raise ValueError(f'사건이 아직 진행 중입니다({state}). 재판단·에스컬레이션으로 처리하세요')
        now = now or datetime.now(timezone.utc)
        previous = dict(status=wi['status'], draft_status=wi.get('draft_status'), retry=wi.get('retry'))
        wi.update(status='CANCELLED', draft_status='CANCELLED', consumer=None, end_date=engine.now_iso(now),
                  log=(wi.get('log') or '') + f'[Closed by {by.strip()}] {reason.strip()[:300]}; ')
        self.repo.update_workitem(wi)
        # event_type is the product's enum (no 'task_closed'); the person's close is a task_cancelled with job_id TASK_CLOSED
        self.repo.record_events([{'job_id': 'TASK_CLOSED', 'todo_id': wi['id'], 'proc_inst_id': wi['proc_inst_id'], 'crew_type': 'human',
                                  'event_type': 'task_cancelled',
                                  'data': {'name': '에이전트 작업 닫음', 'by': by.strip(), 'reason': reason.strip()[:1000], 'previous': previous}}])
        rows = self.repo.list_workitems(proc_inst_id=wi['proc_inst_id'], limit=None)
        defn = self.definition_for_workitem(wi)
        live = [r for r in rows if r['id'] != wi['id'] and r['status'] in ('TODO', 'IN_PROGRESS', 'SUBMITTED', 'PENDING')
                and r['activity_id'] not in defn.events]
        ended = False
        if not live:
            for r in rows:
                if r['id'] != wi['id'] and r['status'] in ('TODO', 'IN_PROGRESS') and r['activity_id'] in defn.events:
                    r.update(status='CANCELLED', end_date=engine.now_iso(now), log=(r.get('log') or '') + 'cancelled: instance closed by a person; ')
                    self.repo.update_workitem(r)
            inst.update(status='COMPLETED', end_event=self.HUMAN_CLOSE_END_EVENT, end_date=engine.now_iso(now), current_activity_ids=[])
            self.repo.update_instance(inst)
            ended = True
        self._after_commit(self.hooks.audit, engine.variables(inst).get('asset', '-'), by.strip(), 'AGENT_TASK_CLOSED',
                           {'workitem': wi['id'], 'instance': wi['proc_inst_id'], 'reason': reason.strip()[:300], 'instance_ended': ended})
        self._after_commit(self._project, inst)
        return {'workitem': wi['id'], 'status': wi['status'], 'instance': wi['proc_inst_id'],
                'instance_status': inst['status'], 'instance_ended': ended, 'end_event': inst.get('end_event')}

    # ---------------------------------------------------------------- HITL: the agent asked a person (human_asked → human_response)
    @workitem_transition
    def human_response(self, workitem_id: str, job_id: str, answer: str, by: str) -> dict:
        """A person answers the worker's question: the answer is an event the worker reads, and the row goes back to the
        worker's queue as FB_REQUESTED (fetch_pending_task picks it up and resumes the session)."""
        wi = self.repo.get_workitem(workitem_id)
        if not wi:
            raise KeyError(workitem_id)
        self.definition_for_workitem(wi)
        if wi.get('status') != 'IN_PROGRESS' or wi.get('draft_status') != 'HUMAN_ASKED':
            raise ValueError('이 작업은 사람의 답변을 기다리는 상태가 아닙니다')
        pending=(wi.get('draft') or {}).get('_human_request') if isinstance(wi.get('draft'),dict) else None
        if isinstance(pending,dict) and pending.get('job_id')!=job_id:
            raise ValueError('현재 대기 중인 질문과 일치하지 않습니다')
        events = self.repo.list_events(todo_id=wi['id'])
        if not any(e.get('job_id') == job_id and e.get('event_type') == 'human_asked' for e in events):
            raise ValueError('이 작업의 질문을 찾을 수 없습니다')
        if any(e.get('job_id') == job_id and e.get('event_type') == 'human_response' for e in events):
            raise ValueError('이미 답변한 질문입니다')
        if not answer.strip():
            raise ValueError('답변을 입력하세요')
        self.repo.record_events([{"job_id": job_id, "todo_id": wi["id"], "proc_inst_id": wi["proc_inst_id"], "crew_type": "human",
                                  "event_type": "human_response", "status": "APPROVED", "data": {"answer": answer, "by": by}}])
        wi["feedback"] = {"human_answer": answer, "by": by, "job_id": job_id}
        wi["draft_status"], wi["consumer"] = "FB_REQUESTED", None
        self.repo.update_workitem(wi)
        return wi

    # ---------------------------------------------------------------- timers
    def fire_timeouts(self, now: datetime | None = None) -> list[dict]:
        """Boundary timer work items past their due_date fire: the attached human task is cancelled and the flow escalates."""
        now = now or datetime.now(timezone.utc)
        fired = []
        for wi in self.repo.due_timers(self.tenant_id,now):
            if self._fire_timeout(wi,now):fired.append(self.repo.get_workitem(wi['id']))
        return fired

    @workitem_transition
    def _fire_timeout(self,wi,now):
        wi=self.repo.get_workitem(wi['id'])
        inst=self.repo.get_instance(wi['proc_inst_id'])
        if (wi['status']!='IN_PROGRESS' or inst['status']!='RUNNING'
                or not wi.get('due_date') or parse_iso(wi['due_date'])>now):return False
        defn=self.definition_for_workitem(wi)
        if (defn.events.get(wi['activity_id']) or {}).get('eventDefinition')!='timer':return False
        rows=self.repo.list_workitems(proc_inst_id=wi['proc_inst_id'],limit=None)
        adv=engine.fire_event(defn,inst,wi,rows,now=now,time_scale=self.time_scale)
        inbox.apply_advance(self,inst,adv)
        for row in adv.updated:self.repo.update_workitem(row)
        self.repo.insert_workitems(adv.created)
        self.repo.update_instance(inst)
        self._after_commit(self.hooks.audit,engine.variables(inst).get('asset','-'),'process','SELECT_TIMEOUT',
                           {'instance':inst['proc_inst_id'],'event':wi['activity_id'],'next':[w['activity_id'] for w in adv.reached]},
                           incident=engine.variables(inst).get('incident'))
        self._after_commit(self._project,inst)
        return True

    def reconcile_services(self,now=None):
        """Scan the service queue by key, including rows held before a restart.

        Includes a crash after claim but before the service transaction commits.
        Only idempotent Incident/CMMS handlers are included. The owning instance
        lock and fresh row recheck prevent a live competing handler from replaying
        a completed task. Still-waiting early pages must not hide later work.
        """
        changed=0;after=None
        while True:
            rows=self.repo.waiting_services(self.tenant_id,after_id=after)
            if not rows:break
            for wi in rows:
                self._run_service(self.repo.get_instance(wi['proc_inst_id']),wi,now)
                fresh=self.repo.get_workitem(wi['id'])
                changed+=int(fresh is not None and fresh['status']!=wi['status'])
            after=rows[-1]['id']
        return changed

    # ---------------------------------------------------------------- service tasks the process executes itself
    def _tool_of(self, wi: dict) -> str:
        """The definition's execution contract, independent of a designer's activity ID."""
        inst = self.repo.get_instance(wi["proc_inst_id"])
        definition = self.definition_for_workitem(wi)
        activity = definition.activities.get(wi["activity_id"], {})
        return str(activity.get("tool") or "")

    def _run_service(self, inst: dict, wi: dict, now: datetime | None) -> None:
        try:
            with self._transition(wi['proc_inst_id']):
                fresh=self.repo.get_workitem(wi['id'])
                inst=self.repo.get_instance(wi['proc_inst_id'])
                if (not fresh or fresh['status']!='SUBMITTED' or inst['status']!='RUNNING'
                        or fresh.get('consumer')!=wi.get('consumer')):return
                tool = self._tool_of(fresh)
                handler = {"incident:command": self._run_command, "incident:reobserve": self._run_reobserve,
                           "enterprise:WO_CREATE": self._run_work_order}.get(tool)
                if handler is None:
                    raise ValueError(f"unsupported service tool: {tool!r} ({fresh['activity_id']})")
                fresh['consumer']=f'{self.consumer}:service'
                self.repo.update_workitem(fresh)
                handler(inst,fresh,now)
        except Exception as e:  # noqa: BLE001
            log.exception("service task %s failed", wi["activity_id"])
            self._fail(wi, e, now)

    def _run_command(self, inst: dict, wi: dict, now) -> None:
        """Issue the chosen skill's PLC commands through the Incident (machine.on_approve). Completes when the ACK arrives."""
        v = engine.variables(inst)
        inc_id, commands = v.get("incident"), v.get("commands") or []
        if not inc_id or not commands:
            raise ValueError("command task requires an incident and approved commands")
        state=self.hooks.incident_state(inc_id)
        if state is None:raise ValueError('incident state unavailable; command not issued')
        if state != 'AWAITING_APPROVAL':
            self.on_incident_update(state,inc_id,False,now)
            return
        cmd = self.hooks.approve_commands(inc_id, commands, v.get("approved_by") or "process")
        if not cmd.get("cmdId"):
            raise ServiceExecutionError({"error": "command service returned no cmdId", "result": cmd})
        wi["log"] = (wi.get("log") or "") + f"action.cmd {cmd['cmdId']} issued; waiting ACK; "
        self.repo.update_workitem(wi)

    def _run_reobserve(self, inst: dict, wi: dict, now) -> None:
        """The Incident decides; rereading its durable state recovers a lost callback."""
        if not wi.get('log'):
            wi['log']='waiting for the incident re-observation verdict; '
            self.repo.update_workitem(wi)
        inc_id=engine.variables(inst).get('incident')
        state=self.hooks.incident_state(inc_id)
        if state:self.on_incident_update(state,inc_id,False,now)

    def _run_work_order(self, inst: dict, wi: dict, now) -> None:
        from .work_orders import request_for_option
        v = engine.variables(inst)
        opt = v.get("chosen_option") or {}
        item = request_for_option(opt)
        res = self.hooks.exec_enterprise(v.get("decision_id") or inst["proc_inst_id"], item)
        self._after_commit(self.hooks.audit,v.get("asset", "-"), "process", "SKILL_EXECUTED" if res.get("ok") else "SKILL_FAILED",
                         {"instance": inst["proc_inst_id"], "code": "WO_CREATE", "ref": res.get("ref"), "detail": res.get("detail") or res.get("error")},
                         incident=v.get("incident"))
        if res.get("ok") is not True or not isinstance(res.get('ref'), str) or not res['ref'].strip():
            raise ServiceExecutionError(res)
        self.submit(wi["id"], {"work_order": res}, by="process", now=now)

    @workitem_transition
    def retry_work_order(self, workitem_id: str, by: str, role: str, now=None):
        """A person restarts a bounded retry cycle for the same approved CMMS request."""
        from . import decisions
        wi=self.repo.get_workitem(workitem_id)
        if wi is None:
            raise KeyError(workitem_id)
        self.definition_for_workitem(wi)
        inst=self.repo.get_instance(wi['proc_inst_id'])
        if self._tool_of(wi)!='enterprise:WO_CREATE' or wi['status']!='PENDING' or inst['status']!='RUNNING':
            raise ValueError('재시도할 실패 작업지시가 아닙니다')
        if not by.strip() or not role.strip():
            raise ValueError('복구 요청자와 역할이 필요합니다')
        approval=next((a for a in self.repo.list_approvals(inst['proc_inst_id'],self.tenant_id)
                       if a['status']=='DELIVERED' and a['decision_id']==engine.variables(inst).get('decision_id')),None)
        if not approval or not approval['payload']['plan'].get('_snapshot'):
            raise ValueError('승인 원문이 없어 같은 내용의 재시도를 검증할 수 없습니다')
        snapshot=deepcopy(approval['payload']['plan']['_snapshot'])
        snapshot['state']='PENDING_APPROVAL'
        decisions.approve(snapshot,approval['payload']['option'],by,role,'same CMMS request retry')
        wi.update(status='SUBMITTED',consumer=None,retry=0,rework_count=int(wi.get('rework_count') or 0)+1)
        wi['log']=(wi.get('log') or '')+f'CMMS retry requested by {by} ({role}); '
        self.repo.update_workitem(wi)
        self.repo.record_events([{'job_id':'WORK_ORDER_RETRY','todo_id':wi['id'],'proc_inst_id':inst['proc_inst_id'],
            'crew_type':'human','event_type':'task_working','data':{'name':'동일 작업지시 재전달','by':by,'role':role,
            'rework_count':wi['rework_count']}}])
        self._after_commit(self._run_service,inst,wi,now)
        return wi

    # ---------------------------------------------------------------- incident → service-task completion
    def on_incident_update(self, inc_state: str, inc_id: str, cleared: bool, now: datetime | None = None) -> None:
        """Called after every Incident transition. Maps the PLC path onto the two waiting service tasks."""
        inst = self._instance_of_incident(inc_id)
        if not inst or inst["status"] != "RUNNING":
            return
        with self._transition(inst['proc_inst_id']):
            inst=self.repo.get_instance(inst['proc_inst_id'])
            if inst['status']!='RUNNING':return
            snapshot=self.hooks.incident_snapshot(inc_id)
            if snapshot is not None:
                inc_state,cleared=snapshot['state'],bool(snapshot.get('cleared'))
            self._apply_incident_update(inst,inc_state,inc_id,cleared,now)

    def _apply_incident_update(self, inst, inc_state, inc_id, cleared, now):
        cmd, reobs = self._open_tool(inst, "incident:command"), self._open_tool(inst, "incident:reobserve")
        if inc_state in ("RE_OBSERVING", "ACKED") and cmd:
            self.submit(cmd["id"], {}, by="process", now=now)
        elif inc_state in ("RESOLVED", "WORK_ORDER_CREATED", "CLOSED", "ESCALATED", "RESOLVED_WITHOUT_ACTION"):
            if cmd:
                self.submit(cmd["id"], {}, by="process", now=now)
                reobs = self._open_tool(inst, "incident:reobserve")
            if reobs:
                recovered = {"ESCALATED": False, "RESOLVED_WITHOUT_ACTION": bool(cleared)}.get(inc_state, True)
                self.submit(reobs["id"], {"recovered": recovered}, by="process", now=now)
        if inc_state in incident_def.TERMINAL:
            rows = self.repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None)
            if (self._command_never_issued(rows, self.hooks.incident_snapshot(inc_id), generation=inst.get("rework_generation"))
                    and self._escalation_not_open(rows)):
                self._abort_before_action(inst, rows, inc_state, cleared, now)

    CONTROL_PATH = ("task:command", "task:reobserve", "task:work-order")
    # B3: a flow imported from bpmn.io keeps its drawn task ids; its parts carry the same tool contract as these activities
    CONTROL_TOOLS = ("incident:command", "incident:reobserve", "enterprise:WO_CREATE")
    ESCALATE_TOOL = "formHandler:escalate"

    @staticmethod
    def _command_never_issued(rows, snap=None, generation=0) -> bool:
        """No approved action of the generation the Incident now serves reached the plant before the Incident ended.
        The Incident's record comes first: a current cmdId is an action whatever generation its row belongs to. Without one,
        only this generation's control-path rows count — a rework that reopened the Incident (A072) retired the earlier
        generation's command to `superseded` after a person reviewed its effect, and the Incident's own verdict ('cleared
        before any action') is about the new generation (A156 item 55: generation 0's DONE task:command and the superseded
        entry kept generation 1 RUNNING on an ended Incident). Either no control-path work item of this generation started,
        or (A083) the only one that did is task:command left PENDING because delivery was refused (ApprovalReviewRequired:
        recovery is a new judgment, impossible once the alert cleared). Without the Incident's record (snap None) a started
        row alone is taken as an action."""
        if snap is not None and snap.get("cmdId"):
            return False
        current = int(generation or 0)
        started = [w for w in rows if (w["activity_id"] in InstanceRuntime.CONTROL_PATH or w.get("tool") in InstanceRuntime.CONTROL_TOOLS)
                   and w["status"] not in ("TODO", "CANCELLED") and int(w.get("generation") or 0) == current]
        if not started:
            return True
        return snap is not None and all((w["activity_id"] == "task:command" or w.get("tool") == "incident:command")
                                        and w["status"] == "PENDING" for w in started)

    @staticmethod
    def _escalation_not_open(rows) -> bool:
        return not any((w["activity_id"] == "task:escalate" or w.get("tool") == InstanceRuntime.ESCALATE_TOOL)
                       and w["status"] not in ("TODO", "CANCELLED") for w in rows)

    def _abort_before_action(self, inst, rows, inc_state, cleared, now):
        """A074: the case ended (alert cleared / rejected / escalated) while agent or selection work was still open — until now
        such instances stayed RUNNING forever (A072: adbf8350, 8b917b16, 99130019). Cancel the open work and hand the outcome
        to the escalation review so the instance ends through ev:escalated with the recorded reason."""
        defn = self.definition_for(inst)
        target = "task:escalate" if "task:escalate" in defn.activities else next(
            (a["id"] for a in defn.activities.values() if a.get("tool") == self.ESCALATE_TOOL), None)
        if target is None:
            return
        reason = f"incident {inc_state} before any action (cleared={bool(cleared)})"
        adv = engine.abort_to(defn, inst, rows, target, reason, now, self.time_scale)
        engine.set_variables(defn, inst, {"recovered": bool(cleared), "incident_outcome": inc_state},
                             source={"kind": "runtime", "by": "process", "reason": reason})
        inbox.apply_advance(self, inst, adv)
        for row in adv.updated:
            self.repo.update_workitem(row)
        self.repo.insert_workitems(adv.created)
        self.repo.update_instance(inst)
        self.repo.record_events([{"job_id": "INCIDENT_ENDED_BEFORE_ACTION", "todo_id": adv.reached[0]["id"], "proc_inst_id": inst["proc_inst_id"],
                                  "crew_type": "result", "event_type": "task_working",
                                  "data": {"name": "조치 전 사건 종료 → 에스컬레이션 검토", "incident_state": inc_state, "cleared": bool(cleared),
                                           "cancelled": [w["activity_id"] for w in adv.updated]}}])
        v = engine.variables(inst)
        self._after_commit(self.hooks.audit, v.get("asset", "-"), "process", "INCIDENT_ENDED_BEFORE_ACTION",
                           {"instance": inst["proc_inst_id"], "state": inc_state, "cleared": bool(cleared), "cancelled": [w["activity_id"] for w in adv.updated]},
                           incident=v.get("incident"))
        self._after_commit(self._project, inst)

    def reconcile_terminal_incidents(self, now=None) -> int:
        """Housekeeping: RUNNING instances whose Incident already ended before any action (missed callback, restart, or rows
        created before A074) are routed to the escalation review. Idempotent; one instance per transition lock."""
        changed = 0
        for inst in self.repo.list_instances(status="RUNNING", limit=200, tenant_id=self.tenant_id):
            inc_id = engine.variables(inst).get("incident")
            if not inc_id:
                continue
            snap = self.hooks.incident_snapshot(inc_id)
            if not snap or snap.get("state") not in incident_def.TERMINAL:
                continue
            with self._transition(inst["proc_inst_id"]):
                fresh = self.repo.get_instance(inst["proc_inst_id"])
                if not fresh or fresh["status"] != "RUNNING":
                    continue
                rows = self.repo.list_workitems(proc_inst_id=fresh["proc_inst_id"], limit=None)
                if self._command_never_issued(rows, snap, generation=fresh.get("rework_generation")) and self._escalation_not_open(rows):
                    self._abort_before_action(fresh, rows, snap["state"], bool(snap.get("cleared")), now)
                    changed += 1
        return changed

    def _open_tool(self, inst: dict, tool: str) -> dict | None:
        return next((w for w in self.repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None)
                     if self._tool_of(w) == tool and w["status"] == "SUBMITTED"), None)

    def _instance_of_incident(self, inc_id: str) -> dict | None:
        # Runtime routing must filter in storage, not scan a 100-row UI page.
        rows = self.repo.list_instances(status="RUNNING", limit=1,
                                       tenant_id=self.tenant_id, incident_id=inc_id)
        return rows[0] if rows else None

    instance_of_incident = _instance_of_incident

    # ---------------------------------------------------------------- views
    def instance_view(self, proc_inst_id: str) -> dict | None:
        inst = self.repo.get_instance(proc_inst_id)
        if not inst or inst.get('tenant_id') != self.tenant_id:
            return None
        items = self.repo.list_workitems(proc_inst_id=proc_inst_id, limit=None)
        defn = self.definition_for(inst)
        return {"instance": inst, "definition":defn.raw, "workitems": items, "timeline": engine.timeline(defn, inst, items),
                "events": self.repo.list_events(proc_inst_id=proc_inst_id),
                "approvals":self.repo.list_approvals(proc_inst_id, self.tenant_id),
                "reworks":self.repo.list_reworks(self.tenant_id, proc_inst_id),
                "effects":self.repo.list_effect_receipts(self.tenant_id, proc_inst_id)}

    def execution_view(self, proc_inst_id: str) -> dict | None:
        """The Execution layer as the graph holds it (회의 L434~435: the instance monitoring screen). Read back from Neo4j, not
        from Supabase, so students see that the graph is a projection of the relational source and can repeat the Cypher."""
        inst = self.repo.get_instance(proc_inst_id)
        if not inst or inst.get('tenant_id') != self.tenant_id:
            return None
        rows = self.hooks.query_cypher(EXECUTION_Q, id=proc_inst_id)
        return {"cypher": EXECUTION_Q.strip(), "params": {"id": proc_inst_id}, "graph": format_execution(rows),
                "projection": self.repo.projection_status(self.tenant_id, proc_inst_id)}

    # ---------------------------------------------------------------- ontology Execution layer (ProcessGPT SCHEMA.md §4.4 / §5.4)
    def reconcile_projections(self, limit=20):
        for pid in self.repo.pending_projections(self.tenant_id, limit):
            self._project({"proc_inst_id": pid})

    def _project(self, inst: dict) -> None:
        """Caller supplies identity only; durable source changes drive delivery."""
        snapshot = None
        try:
            with self.repo.projection_snapshot(self.tenant_id, inst['proc_inst_id']) as snapshot:
                if snapshot is None:
                    return
                self._write_projection(inst['proc_inst_id'], snapshot)
                self.repo.finish_projection(snapshot)
        except Exception as e:
            if snapshot is not None:
                try:
                    self.repo.finish_projection(snapshot, f'{type(e).__name__}: {str(e)[:1000]}')
                except Exception:
                    log.exception('projection failure receipt unavailable; queue remains pending')
            log.warning("execution projection pending: %s", e)

    def _write_projection(self, pid, snapshot):
        inst = snapshot['instance']
        if not inst or inst.get('is_deleted'):
            self._confirmed_projection(DELETE_INSTANCE_Q,dict(id=pid,tenant=self.tenant_id,revision=snapshot['revision']))
            return
        if inst['tenant_id'] != self.tenant_id:
            raise ValueError('projection tenant mismatch')
        defn = self.definition_for(inst)
        process_node = defn.raw.get('ontologyRef')
        items = snapshot['items']
        v = engine.variables(inst)
        projection, node_id = definition_projection(defn, inst["tenant_id"])
        params=dict(**projection, revision=snapshot["revision"], id=inst["proc_inst_id"], name=inst.get("proc_inst_name"), status=inst["status"],
                                 start=inst.get("start_date"), end=inst.get("end_date"), end_event=inst.get("end_event"),
                                 current=inst.get("current_activity_ids") or [], version=inst.get("proc_def_version"),
                                 asset=v.get("asset"), incident=v.get("incident"), process=process_node,
                                 tenant=inst.get("tenant_id") or self.tenant_id,
                                 generation=inst.get('rework_generation') or 0,
                                 bindings=[{"role": b.get("name"), "endpoint": b.get("endpoint")} for b in inst.get("role_bindings") or []],
                                 items=[{"id": w["id"], "activity": w["activity_id"], "target": node_id(w["activity_id"]), "name": w.get("activity_name"), "status": w["status"],
                                         "tool": w.get("tool"), "agent_mode": w.get("agent_mode"), "orch": w.get("agent_orch"),
                                         "draft_status": w.get("draft_status"), "retry": w.get("retry") or 0, "rework": w.get("rework_count") or 0,
                                         "generation": w.get('generation') or 0, "request_id": w.get('rework_request_id'), "supersedes": w.get('supersedes_id'),
                                         "duration": w.get("duration"), "performer": w.get("user_id"), "start": w.get("start_date"),
                                         "end": w.get("end_date"), "due": w.get("due_date")} for w in items])
        self._confirmed_projection(INSTANCE_Q,params)

    def _confirmed_projection(self,query,params):
        params['payload_hash']=projection_digest({k:v for k,v in params.items() if k!='revision'})
        rows=self.hooks.record_cypher(query,**params)
        require_projection_receipt(rows,params['id'],params['revision'],params['payload_hash'])




def format_execution(rows: list[dict]) -> dict | None:
    """Flatten the EXECUTION_Q row into {instance, process, bindings, workitems[]} — None when the graph has no projection yet."""
    if not rows or not rows[0].get("instance"):
        return None
    r = rows[0]
    items = [it for it in (r.get("items") or []) if it and it.get("workitem")]
    result = {"instance": r["instance"], "process": {"id": r.get("process"), "name": r.get("process_name"), "version": r.get("version")},
            "asset": r.get("asset"), "incident": r.get("incident"),
            "bindings": [b for b in (r.get("bindings") or []) if b],
            "workitems": [{**it["workitem"], "executes": it.get("task"), "executes_name": it.get("task_name"), "executes_type": it.get("task_type"),
                           "assigned_to": it.get("performer"), "assigned_kind": it.get("performer_kind")} for it in items]}
    result["warnings"] = r.get("warnings") or []
    result["definition"] = {"id": r.get("definition_id"), "version": r.get("version"), "graph_id": r.get("version_node")}
    return result


def _commands_of(opt: dict, fan_pct: float | None, load_pct: float | None) -> list[dict]:
    """The chosen SOP skill's PLC commands as action.cmd items (same rule as main.hitl_decide: a person may adjust fan/load)."""
    out = []
    for a in opt.get("actions") or []:
        if a.get("kind") != "command":
            continue
        item = {"code": a["code"]}
        if a.get("param"):
            v = a.get("value")
            if a["param"] == "fan_pct" and fan_pct is not None:
                v = fan_pct
            if a["param"] == "load_pct" and load_pct is not None:
                v = load_pct
            item[a["param"]] = v
        out.append(item)
    return out
