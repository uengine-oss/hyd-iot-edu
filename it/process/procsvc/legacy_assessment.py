"""The optional C4 legacy evaluator is a read-only worker owned by the process.

The todo row stores the claim, lease and returned bundle before publication.
An interrupted request can be retried after its lease; stale responses cannot
publish. This adapter does not generalize the deterministic C4 pipeline into a
coding agent. Other definitions/generations remain owned by the actual worker.
"""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import json
import hashlib
import uuid

from hydcommon.timeutil import parse_iso
from . import engine,task_deferral

ACTIVITIES={'task:diagnose','task:candidates','task:compliance','task:rank'}


class LegacyAssessment:
    def __init__(self, runtime, evaluate, publish, bridge, *, lease_seconds=120):
        self.rt,self.evaluate,self.publish,self.bridge=runtime,evaluate,publish,bridge
        self.lease_seconds=lease_seconds

    def _live(self, row):
        inst=self.rt.repo.get_instance(row['proc_inst_id'])
        if (not inst or inst.get('tenant_id')!=self.rt.tenant_id or inst.get('is_deleted')
                or inst.get('status')!='RUNNING' or int(inst.get('rework_generation') or 0)>0
                or int(row.get('generation') or 0)>0):return None
        if not ACTIVITIES <= set(self.rt.definition_for(inst).activities):return None
        origins=self.rt.repo.agent_task_origins(inst['proc_inst_id'],self.rt.tenant_id)
        if any(not o.startswith('legacy:') for o in origins):return None
        return inst

    def claim(self, workitem_id, now=None):
        clock=now or datetime.now(timezone.utc);repo=self.rt.repo
        row=repo.get_workitem(workitem_id)
        if not row or row.get('tenant_id')!=self.rt.tenant_id:return None
        with self.rt._transition(row['proc_inst_id']):
            row=repo.get_workitem(workitem_id);inst=self._live(row)
            if (not inst or row['activity_id']!='task:diagnose' or row['status']!='IN_PROGRESS'
                    or row.get('agent_orch')!='cliagents'):return None
            previous=(row.get('draft') or {}).get('_legacy_attempt')
            if previous:
                if row.get('consumer')!=previous['owner'] or row.get('draft_status')!='STARTED':return None
                retry_at=(previous.get('delivery') or {}).get('retry_at')
                if retry_at and parse_iso(retry_at)>clock:return None
                if previous.get('result') is not None:return row  # committed reply; no second evaluation
                if parse_iso(previous['lease_until'])>clock:return None
                # Expiration revokes the old read-only attempt. A delayed reply
                # will fail its token check before publishing any guide/decision.
                row.update(draft=None,draft_status=None,consumer=None)
                repo.update_workitem(row)
            elif row.get('draft') is not None or row.get('draft_status') is not None or row.get('consumer'):
                return None
            owner='legacy-eval:'+uuid.uuid4().hex
            claimed=repo.fetch_pending_task('cliagents',owner,limit=1,tenant_id=self.rt.tenant_id,
                                            proc_inst_id=row['proc_inst_id'])
            if not claimed or claimed[0]['id']!=workitem_id:
                if claimed:raise ValueError('legacy assessment claimed a different work item')
                return None
            row=claimed[0]
            # A115 (r14 A8, infra-docker init.sql:2559-2564): this claim keeps its own expiry in _legacy_attempt and
            # never renews the worker lease the shared claim attached; left at now+120 s, a cliagents worker would
            # reclaim the row and run it a second time once a delivery retry outlasted it.
            repo.clear_task_lease(row['id'],owner);row['lease_until']=None
            attempt=dict(owner=owner,started=clock.isoformat(),lease_until=(clock+timedelta(seconds=self.lease_seconds)).isoformat())
            row['draft']={'_legacy_attempt':attempt};repo.update_workitem(row)
            repo.record_events([dict(job_id=owner,todo_id=row['id'],proc_inst_id=row['proc_inst_id'],crew_type='legacy',
                                     event_type='task_working',data={'message':'현재 원천으로 레거시 진단을 평가합니다','attempt':attempt})])
            return row

    def _owned(self,row):
        current=self.rt.repo.get_workitem(row['id'])
        if (not current or not self._live(current) or current['status']!='IN_PROGRESS'
                or current.get('draft_status')!='STARTED' or current.get('consumer')!=row.get('consumer')):
            return None
        attempt=(current.get('draft') or {}).get('_legacy_attempt') or {}
        return current if attempt.get('owner')==row.get('consumer') else None

    def save_reply(self,row,result):
        # Reject invalid/oversized data rather than storing a partial successful
        # diagnosis. The source response remains an explicit failed observation.
        if not isinstance(result,dict) or result.get('status') not in {'EVALUATED','WITHHELD','FAILED','REJECTED_BY_GUARDRAIL'}:
            raise ValueError('agent returned no recognized evaluation status')
        if result['status']=='EVALUATED':
            card,payload=result.get('card'),result.get('evaluation')
            if (not isinstance(card,dict) or not isinstance(payload,dict) or not payload.get('options')
                    or not (payload.get('origin') or {}).get('cause') or not (payload.get('origin') or {}).get('failureMode')):
                raise ValueError('agent returned an incomplete supported evaluation')
            alert=engine.variables(self.rt.repo.get_instance(row['proc_inst_id'])).get('alert')
            if card.get('alert')!=alert or payload.get('asset')!=(alert or {}).get('asset'):
                raise ValueError('evaluation differs from the original alert/asset')
        encoded=json.dumps(result,ensure_ascii=False,allow_nan=False)
        if len(encoded.encode('utf8'))>2_000_000:raise ValueError('legacy evaluation exceeds 2 MB')
        with self.rt._transition(row['proc_inst_id']):
            current=self._owned(row)
            if not current:return False
            previous=current['draft']['_legacy_attempt'].get('result')
            if previous is not None and previous!=result:raise ValueError('saved evaluation is immutable')
            current['draft']['_legacy_attempt']['result']=deepcopy(result)
            self.rt.repo.update_workitem(current)
            return True

    def apply_reply(self,row):
        with self.rt._transition(row['proc_inst_id']):
            current=self._owned(row)
            if not current:return False
            result=current['draft']['_legacy_attempt'].get('result')
            if not isinstance(result,dict):return False
            if result.get('status')!='EVALUATED':
                # Deferral's storage transaction is deliberately outside this
                # runtime transaction; its expected-consumer fence rechecks.
                held=deepcopy(result)
            else:
                payload=deepcopy(result.get('evaluation'))
                card=deepcopy(result.get('card'))
                if not isinstance(payload,dict) or not isinstance(card,dict):raise ValueError('evaluation requires card and decision')
                inst=self.rt.repo.get_instance(row['proc_inst_id']);values=engine.variables(inst)
                if card.get('alert')!=values.get('alert') or payload.get('asset')!=values.get('asset'):
                    raise ValueError('evaluation differs from the original alert/asset')
                origin=payload.setdefault('origin',{})
                if not origin.get('cause') or not origin.get('failureMode'):raise ValueError('evaluation requires supported cause and failure mode')
                origin.update(incident=values['incident'],legacy_attempt=dict(workitem=row['id'],owner=row['consumer']))
                payload['id']='DEC-EVAL-'+row['consumer'].split(':',1)[1]
                # Publication is idempotent by this attempt's decision ID. A
                # crash after SQLite publication and before PG commit replays
                # the same saved bundle, never a new source evaluation.
                decision=self.publish(payload,card)
                output=dict(cause=origin['cause'],failure_mode=origin['failureMode'],guide_card=card)
                repo=self.rt.repo
                if not repo.save_task_result(row['id'],output,True,expected_consumer=row['consumer']):
                    raise ValueError('legacy assessment claim changed')
                job='legacy:'+decision['id']
                repo.record_events([dict(job_id=job,todo_id=row['id'],proc_inst_id=row['proc_inst_id'],crew_type='legacy',
                                         event_type=kind,data={'message':'점유된 레거시 평가 결과 접수','output_keys':list(output)})
                                    for kind in ('task_started','task_completed')])
                held=None
        if held is not None:
            status=((held.get('card') or {}).get('evidence_status') or {}).get('status')
            evidence={'run':held.get('id'),'status':held.get('status'),'steps':held.get('steps') or []}
            raw=json.dumps(evidence,ensure_ascii=False,allow_nan=False).encode('utf8')
            if len(raw)>96_000:
                # Keep a bounded, explicitly incomplete trace. An oversized
                # source trace must not strand the claim in a retry loop.
                evidence={'run':held.get('id'),'status':held.get('status'),
                          'trace_bytes':len(raw),'trace_sha256':hashlib.sha256(raw).hexdigest(),
                          'trace_truncated':True,'trace_preview':raw[:24_000].decode('utf8',errors='replace')}
            assessment=dict(status='UNSUPPORTED' if status=='UNSUPPORTED' else 'UNKNOWN',
                            reason=str(held.get('error') or (held.get('card') or {}).get('summary') or '원천 평가를 완료하지 못했습니다')[:4000],
                            evidence=evidence)
            task_deferral.defer(self.rt.repo,self.rt.tenant_id,row['id'],expected_consumer=row['consumer'],
                                request_id=row['consumer'],assessment=assessment)
        else:
            self.rt.poll_once();self.bridge(decision)
        return True

    def tick(self,now=None):
        rows=self.rt.repo.list_workitems(status='IN_PROGRESS',agent_orch='cliagents',tenant_id=self.rt.tenant_id,limit=None)
        for candidate in rows:
            row=self.claim(candidate['id'],now)
            if not row:continue
            result=row['draft']['_legacy_attempt'].get('result')
            if result is None:
                alert=engine.variables(self.rt.repo.get_instance(row['proc_inst_id'])).get('alert')
                try:
                    result=self.evaluate(alert)
                    if not self.save_reply(row,result):return 1
                except Exception as exc:
                    result={'status':'FAILED','error':f'{type(exc).__name__}: {str(exc)[:1000]}'}
                    if not self.save_reply(row,result):return 1
            try:
                self.apply_reply(row)
            except Exception as exc:
                # A failed publication must not monopolize the tenant queue.
                # Retain its exact bundle and make retry timing/error visible.
                with self.rt._transition(row['proc_inst_id']):
                    current=self._owned(row)
                    if current:
                        attempt=current['draft']['_legacy_attempt']
                        count=int((attempt.get('delivery') or {}).get('failures') or 0)+1
                        delay=min(60,2**min(count,6))
                        error=f'{type(exc).__name__}: {str(exc)[:1000]}'
                        attempt['delivery']={'failures':count,'error':error,
                            'retry_at':((now or datetime.now(timezone.utc))+timedelta(seconds=delay)).isoformat()}
                        current['log']=(current.get('log') or '')[-7000:]+'[DELIVERY RETRY] '+error+'; '
                        self.rt.repo.update_workitem(current)
                    else:
                        raise  # completion recovery owns an already submitted row
            return 1
        return 0
