import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from procsvc import engine, handover
from procsvc.definition_registry import validate_definition
from test_inbox import rt, KIM, CHOI

PATH = Path(__file__).parents[1]/'it/process/definitions/shift_handover_v1.json'
START = dict(asset='HYD-01', shift_label='야간조', as_of='2026-10-27T18:00:00+09:00',
             work_notes='정비 완료라고 적혀 있으나 작업지시와 재고는 확인 필요')


def begin(runtime, values=None):
    definition = json.loads(PATH.read_text(encoding='utf8'))
    validate_definition(definition)
    runtime.register_definition(definition)
    runtime.repo.upsert_user(dict(id='agent:handover', username='교대 인수인계 에이전트', is_agent=True, agent_type='agent', tenant_id='hyd'))
    return runtime.start_definition('shift_handover', definition['version'], str(uuid4()), values=START if values is None else values)


def pending(runtime, inst, activity):
    return next(w for w in runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])
                if w['activity_id'].startswith(activity) and w['status'] in ('IN_PROGRESS', 'PENDING'))


def unknown_draft():
    return dict(handover_summary='현재 자료를 조회하지 못했습니다. 메모를 완료 증거로 사용하지 않습니다.', evidence=[],
        checks=[dict(area=area, state='needs_check', finding='조회 자료 없음', next_action='다음 근무자가 실제 상태 확인', evidence_indices=[])
                for area in sorted(handover.AREAS)])


def test_transport_metadata_does_not_allow_undeclared_business_outputs():
    result = dict(unknown_draft(), text='결과 파일 작성 완료', cliagents_session_id='session-test')
    handover.validate_result({'contract':handover.DRAFT}, {}, result)
    result['maintenance_completed'] = True
    with pytest.raises(ValueError,match='인계안은'):
        handover.validate_result({'contract':handover.DRAFT}, {}, result)


def deliver(runtime, inst, output=None):
    wi = runtime.repo.fetch_pending_task('cliagents', 'handover-test')[0]
    runtime.repo.save_task_result(wi['id'], output or unknown_draft(), final=True)
    runtime.poll_once()
    return wi


def test_missing_information_handover_requires_both_people_and_never_executes_equipment(rt):
    runtime, hooks = rt
    inst = begin(runtime)
    deliver(runtime, inst)
    sender = pending(runtime, inst, 'task:sender')
    with pytest.raises(PermissionError):
        runtime.submit_human(sender['id'], dict(sender_decision='approve', sender_notes='확인 필요 유지'), CHOI)
    runtime.submit_human(sender['id'], dict(sender_decision='approve', sender_notes='확인 필요 유지'), KIM)
    receiver = pending(runtime, inst, 'task:receiver')
    with pytest.raises(ValueError, match='설비 조치'):
        runtime.submit_human(receiver['id'], dict(receiver_decision='confirm', receiver_notes='확인', communication_only=False), CHOI)
    runtime.submit_human(receiver['id'], dict(receiver_decision='confirm', receiver_notes='미확인 항목을 이어 확인함', communication_only=True), CHOI)
    current = runtime.repo.get_instance(inst['proc_inst_id'])
    assert current['status'] == 'COMPLETED' and current['end_event'] == 'ev:confirmed'
    assert not hooks.calls and not hooks.cards
    assert engine.variables(current)['checks'][0]['state'] == 'needs_check'


def test_receiver_requests_revision_then_sender_rejects(rt):
    runtime, hooks = rt
    inst = begin(runtime); deliver(runtime, inst)
    runtime.submit_human(pending(runtime, inst, 'task:sender')['id'], dict(sender_decision='approve', sender_notes='미확인 전달'), KIM)
    runtime.submit_human(pending(runtime, inst, 'task:receiver')['id'],
        dict(receiver_decision='revise', receiver_notes='열린 작업지시를 추가 확인하세요', communication_only=False), CHOI)
    assert engine.variables(runtime.repo.get_instance(inst['proc_inst_id']))['receiver_notes'] == '열린 작업지시를 추가 확인하세요'
    deliver(runtime, inst)
    runtime.submit_human(pending(runtime, inst, 'task:sender')['id'], dict(sender_decision='reject', sender_notes='필수 확인 자료 부족'), KIM)
    assert runtime.repo.get_instance(inst['proc_inst_id'])['end_event'] == 'ev:rejected'
    assert not hooks.calls


def test_fabricated_tool_evidence_is_returned_for_correction(rt):
    runtime, _ = rt
    inst = begin(runtime)
    output = unknown_draft()
    output['evidence'] = [dict(tool='enterprise/query', query='select * from ent.work_orders', result='완료')]
    output['checks'][0].update(state='observed', evidence_indices=[0])
    wi = deliver(runtime, inst, output)
    current = runtime.repo.get_workitem(wi['id'])
    assert current['status'] != 'DONE'
    assert not any(w['activity_id'] == 'task:sender' and w['status'] in ('IN_PROGRESS', 'DONE')
                   for w in runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))


def _query_evidence():
    from hydcommon.sql_read import guard
    actual={'sql':'SELECT code FROM ent.assets ORDER BY code'}
    document={'statement':guard(actual['sql']),'columns':['code'],'rows':[['HYD-01']],
              'row_count':1,'row_limit':200,'at_row_limit':False}
    claim=dict(tool='mcp__enterprise__query',query={'sql':"SELECT code FROM ent.assets WHERE code = 'HYD-01'"},
               result={'result':'ok','document':{k:document[k] for k in ('statement','columns','rows','row_count')}})
    return actual, document, claim


def _record_query(repo, inst, wi, actual, document, *, call_id='source', truncated=False):
    common=dict(job_id='source-job',todo_id=wi['id'],proc_inst_id=inst['proc_inst_id'],crew_type='agent')
    repo.record_events([
        dict(common,event_type='tool_usage_started',data=dict(tool='mcp__enterprise__query',tool_use_id=call_id,input=actual)),
        dict(common,event_type='tool_usage_finished',data=dict(tool='mcp__enterprise__query',tool_use_id=call_id,
             output={'result':'ok','document':document},output_truncated=truncated,is_error=False)),
    ])


def test_identical_full_response_corrects_query_with_audited_normal_processing(rt):
    runtime,hooks=rt;inst=begin(runtime)
    wi=runtime.repo.fetch_pending_task('cliagents','handover-test')[0]
    actual,document,claim=_query_evidence();_record_query(runtime.repo,inst,wi,actual,document)
    output=unknown_draft();output['evidence']=[claim]
    output['checks'][0].update(state='observed',evidence_indices=[0]);original=deepcopy(output)
    runtime.repo.save_task_result(wi['id'],output,final=True);runtime.poll_once()
    saved=runtime.repo.get_workitem(wi['id'])
    assert saved['status']=='DONE' and saved['output']['evidence'][0]['query']==actual
    assert output==original and original['evidence'][0]['query']!=actual
    audit=[e for e in runtime.repo.list_events(todo_id=wi['id']) if str(e.get('job_id','')).startswith('citation-reconcile:')]
    assert len(audit)==1 and audit[0]['data']['changes'][0]['original_query']==original['evidence'][0]['query']
    assert audit[0]['data']['changes'][0]['actual_query']==actual and not hooks.calls
    assert pending(runtime,inst,'task:sender')['status']=='IN_PROGRESS'


@pytest.mark.parametrize('defect',['altered_rows','incomplete_claim','truncated_output','row_limit','two_candidates','unsafe_sql','forged_statement'])
def test_ambiguous_or_untrusted_response_is_never_reconciled(rt,defect):
    runtime,_=rt;inst=begin(runtime);wi=runtime.repo.fetch_pending_task('cliagents','handover-test')[0]
    actual,document,claim=_query_evidence()
    if defect=='altered_rows':claim['result']['document']['rows']=[['HYD-02']]
    if defect=='incomplete_claim':del claim['result']['document']['rows']
    if defect=='row_limit':document['at_row_limit']=True
    if defect=='unsafe_sql':claim['query']={'sql':'DELETE FROM ent.assets'}
    if defect=='forged_statement':
        document['statement'] += ' OFFSET 1'
        claim['result']['document']['statement']=document['statement']
    _record_query(runtime.repo,inst,wi,actual,document,truncated=defect=='truncated_output')
    if defect=='two_candidates':_record_query(runtime.repo,inst,wi,actual,document,call_id='other')
    output=unknown_draft();output['evidence']=[claim];original=deepcopy(output)
    corrected,changes=handover.reconcile_trace(runtime.repo,wi,{'contract':handover.DRAFT},output)
    assert corrected==original and output==original and changes==[]
    with pytest.raises(ValueError,match='모든 조회 근거'):
        handover.validate_trace(runtime.repo,wi,{'contract':handover.DRAFT},corrected)


def test_one_unrepairable_claim_does_not_partially_rewrite_other_evidence(rt):
    runtime,_=rt;inst=begin(runtime);wi=runtime.repo.fetch_pending_task('cliagents','handover-test')[0]
    actual,document,claim=_query_evidence();_record_query(runtime.repo,inst,wi,actual,document)
    fabricated=deepcopy(claim);fabricated['result']['document']['rows']=[['HYD-02']]
    output=unknown_draft();output['evidence']=[claim,fabricated];original=deepcopy(output)
    corrected,changes=handover.reconcile_trace(runtime.repo,wi,{'contract':handover.DRAFT},output)
    assert corrected==original and output==original and changes==[]


def test_handover_initial_and_correction_prompts_identify_real_tool_inputs():
    from worker import prompt
    fields=[{'key':'handover_summary','type':'textarea'}]
    initial=prompt.build({}, {'form_fields':fields,'form_contract':handover.DRAFT},workdir='/workspace')
    correction=prompt.format_correction('조회 근거 불일치',fields,form_contract=handover.DRAFT)
    for text in (initial,correction):
        assert '호출에 보낸 SQL 원문' in text and '정규화된 statement' in text and 'needs_check' in text
    assert '호출에 보낸 SQL 원문' not in prompt.build({}, {'form_fields':fields,'form_contract':'other'},workdir='/workspace')


def test_repeated_revision_stops_as_unconfirmed_followup(rt):
    runtime, hooks = rt
    inst = begin(runtime)
    for _ in range(3):
        deliver(runtime, inst)
        runtime.submit_human(pending(runtime, inst, 'task:sender')['id'],
            dict(sender_decision='revise', sender_notes='필수 자료를 더 확인하세요'), KIM)
    current = runtime.repo.get_instance(inst['proc_inst_id'])
    assert current['end_event'] == 'ev:followup'
    assert engine.variables(current).get('receiver_decision') != 'confirm'
    assert not hooks.calls


@pytest.mark.parametrize('extra', [dict(receiver_decision='confirm'), dict(incident='fake')])
def test_start_cannot_inject_completion_or_incident(rt, extra):
    with pytest.raises(ValueError, match='시작'):
        begin(rt[0], dict(START, **extra))
