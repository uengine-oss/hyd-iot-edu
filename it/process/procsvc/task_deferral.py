"""Durable, fenced task deferral and explicit reassessment.

Missing/unsupported observations are not completed business forms. Receipts and
work item state commit together under the existing instance transaction. This
module does not evaluate evidence, submit a decision or issue a command.
"""
from copy import deepcopy
import hashlib
import json

from hydcommon.timeutil import now_iso


def _text(value, name, maximum=200):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum:
        raise ValueError(f'{name} must be nonblank text, at most {maximum} characters')
    return value.strip()


def _json(value):
    try:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError) as exc:raise ValueError('assessment must contain finite JSON values') from exc


def validate(value):
    if not isinstance(value,dict) or set(value)!={'status','reason','evidence'}:
        raise ValueError('deferral requires only status, reason and evidence')
    if value['status'] not in ('UNKNOWN','UNSUPPORTED'):
        raise ValueError('deferral status must be UNKNOWN or UNSUPPORTED')
    reason=_text(value['reason'],'reason',4000)
    if not isinstance(value['evidence'],dict):raise ValueError('evidence must be an object')
    result=dict(status=value['status'],reason=reason,evidence=deepcopy(value['evidence']))
    if len(_json(result).encode('utf-8'))>131072:raise ValueError('deferral evidence exceeds 128 KiB')
    return result


def control(text):
    """Only a whole JSON control object may bypass the business form contract."""
    try:value=json.loads(text)
    except (TypeError,ValueError):return None
    if not isinstance(value,dict) or '__deferred__' not in value:return None
    if set(value)!={'__deferred__'}:raise ValueError('deferral and business output cannot be mixed')
    return validate(value['__deferred__'])


def _row(repo, tenant_id, workitem_id):
    row=repo.get_workitem(workitem_id)
    if not row or row.get('tenant_id')!=tenant_id:raise KeyError('no such work item')
    return row


def _live(repo, row, tenant_id):
    inst=repo.get_instance(row['proc_inst_id'])
    if (not inst or inst.get('tenant_id')!=tenant_id or inst.get('is_deleted')
            or inst.get('status')!='RUNNING'
            or int(row.get('generation') or 0)!=int(inst.get('rework_generation') or 0)):
        raise ValueError('task is no longer in the active instance generation')
    if row.get('agent_mode') not in ('DRAFT','COMPLETE') or not row.get('agent_orch'):
        raise ValueError('only agent tasks can defer an assessment')


def _receipt(repo, row, job, kind, body):
    prior=repo.find_task_event(row['id'],job,kind)
    if prior:
        if prior['data'].get('request_sha')!=hashlib.sha256(_json(body).encode()).hexdigest():
            raise ValueError('same request id contains different input')
        return deepcopy(prior['data']['receipt'])


def _event(repo,row,job,kind,body,receipt):
    repo.record_events([dict(job_id=job,todo_id=row['id'],proc_inst_id=row['proc_inst_id'],
                             crew_type='human' if kind=='task_reassessment_requested' else 'agent',
                             event_type=kind,data=dict(request_sha=hashlib.sha256(_json(body).encode()).hexdigest(),
                                                      receipt=receipt,message=receipt.get('reason')))])


def defer(repo,tenant_id,workitem_id,*,expected_consumer,request_id,assessment,session_id=None):
    request_id=_text(request_id,'request_id');_text(expected_consumer,'expected_consumer',500)
    assessment=validate(assessment)
    if session_id is not None:_text(session_id,'session_id',500)
    body=dict(assessment=assessment,consumer=expected_consumer,session_id=session_id)
    job='deferral:'+request_id
    row=_row(repo,tenant_id,workitem_id)
    with repo.instance_transaction(tenant_id,row['proc_inst_id']):
        row=_row(repo,tenant_id,workitem_id)
        prior=_receipt(repo,row,job,'task_deferred',body)
        if prior:return prior
        _live(repo,row,tenant_id)
        if (row['status']!='IN_PROGRESS' or row.get('draft_status')!='STARTED'
                or row.get('consumer')!=expected_consumer):
            raise ValueError('assessment no longer owns this task attempt')
        receipt=dict(id=request_id,workitem_id=workitem_id,assessment=assessment,reason=assessment['reason'],
                     at=now_iso(),generation=int(row.get('generation') or 0),agent_orch=row['agent_orch'],session_id=session_id)
        row.update(status='PENDING',consumer=None,draft_status=None,output=None,
                   draft={'_deferral':receipt},log=(row.get('log') or '')+'[DEFERRED] '+assessment['reason']+'; ')
        repo.update_workitem(row)
        _event(repo,row,job,'task_deferred',body,receipt)
        return receipt


def reassess(repo,tenant_id,workitem_id,*,deferral_id,request_id,by,reason):
    body=dict(deferral_id=_text(deferral_id,'deferral_id'),request_id=_text(request_id,'request_id'),
              by=_text(by,'by'),reason=_text(reason,'reason',2000))
    job='reassessment:'+body['request_id']
    row=_row(repo,tenant_id,workitem_id)
    with repo.instance_transaction(tenant_id,row['proc_inst_id']):
        row=_row(repo,tenant_id,workitem_id)
        prior=_receipt(repo,row,job,'task_reassessment_requested',body)
        if prior:return prior
        _live(repo,row,tenant_id)
        previous=(row.get('draft') or {}).get('_deferral')
        if (row['status']!='PENDING' or row.get('consumer') is not None or not isinstance(previous,dict)
                or previous.get('id')!=body['deferral_id']):
            raise ValueError('task is not waiting for this deferral')
        receipt=dict(body,workitem_id=workitem_id,at=now_iso(),status='QUEUED')
        feedback={'reassessment':receipt,'text':f"새 근거로 다시 평가하세요. 이전 보류: {previous['reason']}\n"
                                                f"요청자 {body['by']}: {body['reason']}\n이전 결과를 재사용하지 말고 원천을 다시 조회하세요."}
        # Do not resume a CLI session with a stale answer. Its id and evidence
        # remain in the prior committed event, even if the workspace is gone.
        row.update(status='IN_PROGRESS',draft=None,draft_status=None,consumer=None,output=None,feedback=feedback)
        repo.update_workitem(row)
        _event(repo,row,job,'task_reassessment_requested',body,receipt)
        return receipt
