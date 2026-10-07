"""Source-backed extraction lifecycle; CLI output here is explicitly a test double."""
import copy
import json
from uuid import uuid4

import pytest

from procsvc import engine, manual_extraction as extraction, manual_review
from procsvc.manual_sources import ManualSources
from worker import prompt
from worker.runner import Runner
from test_worker import _settings, _fake_exec
from test_instances import rt


def _delivered_prompt(request,workspace):
    from worker.runner import PROMPT_FILE
    return (workspace/PROMPT_FILE).read_text(encoding='utf8') if PROMPT_FILE in request.prompt else request.prompt


@pytest.fixture
def document(tmp_path):
    archive=ManualSources(tmp_path/'manual.sqlite3')
    source=archive.save('hyd','general.txt',('정비 절차\n'+'설명입니다.\n'*1700+'전원을 차단한 뒤 벨트를 점검한다.\n').encode())
    text=source['pages'][0]['text']
    def anchor(quote):
        start=text.index(quote)
        return dict(source_id=source['source_id'],page=1,start=start,end=start+len(quote),quote=quote)
    proposal=dict(source_id=source['source_id'],sections=[dict(ref='section-1',title='정비 절차',excerpt=text,anchor=anchor('정비 절차'))],
        procedures=[dict(id='SOP-EXTRACT-1',name='벨트 점검',section='section-1',anchor=anchor('전원을 차단한 뒤 벨트를 점검한다.'),
                         steps=[dict(order=1,text='전원을 차단한 뒤 벨트를 점검한다.',manual='section-1',anchor=anchor('전원을 차단한 뒤 벨트를 점검한다.'))])],
        page_reviews=[dict(page=1,note='마지막 문장의 정비 절차를 검토했습니다.')],warnings=['SOP ID는 등록 제안입니다.'])
    return archive,source,proposal


def test_general_source_uses_versioned_worker_and_requires_separate_review(rt,document,tmp_path):
    runtime,_=rt;archive,source,proposal=document
    assert manual_review.proposal(source)['procedures']==[]  # existing parser cannot extract this prose
    rid=str(uuid4());inst=extraction.start(runtime,source,rid)
    assert extraction.start(runtime,source,rid)['proc_inst_id']==inst['proc_inst_id']
    reqs=[]
    runner=Runner(_settings(tmp_path/'worker'),runtime.repo,exec_fn=_fake_exec(json.dumps({'proposal':proposal}),requests=reqs),
                  schema_prompt='ManualSection Skill Step',resolve_provider=lambda _:object())
    assert runner.poll_once()==1
    wi=runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    delivered=_delivered_prompt(reqs[0][0],tmp_path/'worker'/'hyd'/wi['id'])     # inline or context/prompt.md (A077)
    assert source['pages'][0]['text'][-20:] in json.loads(delivered.split('[InputData]\n')[1].split('\n\n##')[0])['manual_source']['pages'][0]['text']
    task=json.loads((tmp_path/'worker'/'hyd'/wi['id']/'context'/'task.json').read_text(encoding='utf8'))
    assert '전원을 차단한 뒤 벨트를 점검한다.' in task['query']
    assert runtime.poll_once()==1
    result=extraction.result(runtime,source,inst['proc_inst_id'],None)
    preview=result['preview']
    assert result['status']=='DONE' and preview['extraction']['session_id']=='sess-A'
    assert 'reviewed' not in preview and 'by' not in preview
    with pytest.raises(ValueError,match='검토'):manual_review.validate(archive,'hyd',preview)
    preview.update(reviewed=True,by='검토자',links={'SOP-EXTRACT-1':{'failureMode':'fm:bearing-degradation'}})
    assert manual_review.validate(archive,'hyd',preview)['procedures'][0]['steps'][0]['text'].startswith('전원을 차단')


@pytest.mark.parametrize('change',[
    lambda p:p.update(source_id='another'),
    lambda p:p.update(page_reviews=[]),
    lambda p:p['page_reviews'].append(p['page_reviews'][0]),
    lambda p:p['procedures'][0]['steps'][0]['anchor'].update(quote='허구'),
    lambda p:p['procedures'][0]['steps'][0]['anchor'].update(page=True),
    lambda p:p['procedures'][0]['steps'][0].update(order=2),
    lambda p:p['procedures'][0].update(section='missing'),
    lambda p:p['procedures'][0].update(section=[]),
    lambda p:p['sections'].append(p['sections'][0]),
])
def test_unfounded_proposal_never_completes_engine_task(rt,document,change):
    runtime,_=rt;_,source,proposal=document
    change(proposal)
    inst=extraction.start(runtime,source,str(uuid4()))
    wi=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
    runtime.repo.save_task_result(wi['id'],{'proposal':proposal},final=True)
    runtime.poll_once()
    assert runtime.repo.get_workitem(wi['id'])['status']!='DONE'
    assert runtime.repo.get_instance(inst['proc_inst_id'])['status']=='RUNNING'
    assert extraction.result(runtime,source,inst['proc_inst_id'],None)['preview'] is None


def test_result_cannot_be_relabelled_for_another_document(rt,document):
    runtime,_=rt;archive,source,_=document
    inst=extraction.start(runtime,source,str(uuid4()))
    other=archive.save('hyd','other.txt',b'other')
    with pytest.raises(ValueError,match='원문'):extraction.result(runtime,other,inst['proc_inst_id'],None)


def test_explicit_no_procedures_is_a_reviewable_result_not_a_fabricated_sop(document):
    _,source,proposal=document
    proposal.update(sections=[],procedures=[],warnings=['관련 SOP 없음'])
    assert extraction.validate_proposal(source,proposal)['procedures']==[]


def test_full_draft_survives_retry_prompt():
    draft={'proposal':{'excerpt':'근거 '*5000+'마지막 안전 조건'}}
    built=prompt.build({'draft':draft},{},workdir='/workspace')
    assert json.dumps(draft,ensure_ascii=False,indent=2) in built


def test_output_cannot_claim_human_approval_or_change_graph_head(rt,document):
    runtime,_=rt;_,source,proposal=document
    inst=extraction.start(runtime,source,str(uuid4()))
    proposal.update(reviewed=True,by='forged',previous_batch='forged',extraction={'session_id':'forged'})
    wi=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
    runtime.repo.save_task_result(wi['id'],{'proposal':proposal},final=True);runtime.poll_once()
    preview=extraction.result(runtime,source,inst['proc_inst_id'],'actual-head')['preview']
    assert preview['previous_batch']=='actual-head' and 'reviewed' not in preview and 'by' not in preview
    assert preview['extraction']['session_id'] is None


def test_durable_history_is_source_scoped_paginated_and_has_no_full_document(rt,document):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import manual_api
    runtime,_=rt;archive,source,_=document
    created=[extraction.start(runtime,source,str(uuid4())) for _ in range(3)]
    other=archive.save('hyd','other.txt',b'not the source')
    extraction.start(runtime,other,str(uuid4()))
    app=FastAPI()
    manual_api.register(app,archive_factory=lambda:archive,driver_factory=lambda:None,
                        tenant='hyd',audit=lambda *a:None,runtime_factory=lambda:runtime)
    client=TestClient(app);path='/api/kg/manuals/sources/'+source['source_id']+'/extractions'
    first=client.get(path+'?limit=2').json();second=client.get(path+'?limit=2&offset=2').json()
    assert first['next_offset']==2 and second['next_offset'] is None
    assert {r['proc_inst_id'] for r in first['items']+second['items']}=={i['proc_inst_id'] for i in created}
    assert all(set(r)=={'proc_inst_id','status','start_date','end_date'} for r in first['items'])
    assert client.get(path+'?limit=101').status_code==400
    assert runtime.repo.list_source_runs('another',extraction.DEFINITION_ID,'manual-extraction:')==[]


def _bad(proposal):
    bad=copy.deepcopy(proposal);bad['procedures'][0]['steps'][0]['anchor'].update(quote='허구');return bad


def test_rejected_proposal_goes_back_to_the_agent_with_the_reason_and_is_corrected_in_place(rt,document,tmp_path):
    """A077: a citation defect is feedback for the same task (FB_REQUESTED), not three identical re-judgements."""
    runtime,_=rt;_,source,proposal=document
    inst=extraction.start(runtime,source,str(uuid4()))
    wi=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
    assert runtime.repo.save_task_result(wi['id'],{'proposal':_bad(proposal),'cliagents_session_id':'sess-1'},final=True)
    runtime.poll_once()
    row=runtime.repo.get_workitem(wi['id'])
    assert row['status']=='IN_PROGRESS' and row['draft_status']=='FB_REQUESTED' and row['output'] is None
    assert row['feedback']['kind']=='validation' and row['feedback']['attempt']==1 and '인용' in row['feedback']['text']
    assert row['draft']['cliagents_session_id']=='sess-1'          # the previous proposal and session survive for the resume
    pending=extraction.result(runtime,source,inst['proc_inst_id'],None)
    assert pending['preview'] is None and pending['corrections']['state']=='AWAITING_AGENT' and len(pending['corrections']['reasons'])==1
    # the worker re-claims the same row, the prompt carries the rejection and the old proposal, and the session is resumed
    reqs=[]
    runner=Runner(_settings(tmp_path/'worker'),runtime.repo,exec_fn=_fake_exec(json.dumps({'proposal':proposal}),requests=reqs),
                  schema_prompt='ManualSection Skill Step',resolve_provider=lambda _:object())
    assert runner.poll_once()==1
    sent=reqs[0][0]
    delivered=_delivered_prompt(sent,tmp_path/'worker'/'hyd'/wi['id'])
    assert '## 이전 결과에 대한 피드백' in delivered and '원문 검증에서 거부' in delivered and '허구' in delivered
    assert sent.resume_session=='sess-1'
    assert runtime.poll_once()==1
    done=extraction.result(runtime,source,inst['proc_inst_id'],None)
    assert done['status']=='DONE' and done['preview']['procedures'][0]['id']=='SOP-EXTRACT-1'
    assert done['corrections']['state']=='CORRECTED' and done['corrections']['attempts']==1


def test_three_rejections_block_the_task_for_a_person_with_every_reason_kept(rt,document):
    runtime,_=rt;_,source,proposal=document
    inst=extraction.start(runtime,source,str(uuid4()))
    for n in range(1,4):
        wi=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
        runtime.repo.save_task_result(wi['id'],{'proposal':_bad(proposal)},final=True)
        runtime.poll_once()
        row=runtime.repo.get_workitem(wi['id'])
        assert row['feedback']['attempt']==n
    assert row['status']=='PENDING' and row['output'] is None and len(row['feedback']['history'])==3
    assert runtime.repo.fetch_pending_task('cliagents','test-worker')==[]       # nobody re-runs a blocked task silently
    blocked=extraction.result(runtime,source,inst['proc_inst_id'],None)
    assert blocked['preview'] is None and blocked['corrections']['state']=='BLOCKED_FOR_REVIEW'
    assert runtime.repo.get_instance(inst['proc_inst_id'])['status']=='RUNNING'
    assert any(e['job_id']=='TASK_REJECTED' and e['data']['recovery']=='human_review' for e in runtime.repo.list_events(todo_id=wi['id']))


def test_reviewer_feedback_is_pinned_into_the_next_extraction_and_reaches_the_agent(rt,document,tmp_path):
    """A077 (ontology-studio): the previous round's human verdicts ride into the next extraction as pinned input."""
    runtime,_=rt;_,source,proposal=document
    feedback={'previous_instance':'manual_source_extraction.prev','by':'검토자',
              'items':[{'target':'SOP-EXTRACT-1','verdict':'WRONG','note':'2단계가 빠졌다'},{'target':'section-1','verdict':'OK'}]}
    inst=extraction.start(runtime,source,str(uuid4()),review_feedback=feedback)
    reqs=[]
    runner=Runner(_settings(tmp_path/'worker'),runtime.repo,exec_fn=_fake_exec(json.dumps({'proposal':proposal}),requests=reqs),
                  schema_prompt='ManualSection Skill Step',resolve_provider=lambda _:object())
    assert runner.poll_once()==1
    wi0=runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    delivered=_delivered_prompt(reqs[0][0],tmp_path/'worker'/'hyd'/wi0['id'])
    inputs=json.loads(delivered.split('[InputData]\n')[1].split('\n\n##')[0])
    assert inputs['review_feedback']['items'][0]['note']=='2단계가 빠졌다' and inputs['review_feedback']['by']=='검토자'
    assert 'review_feedback' in delivered and 'WRONG' in delivered
    assert runtime.poll_once()==1 and extraction.result(runtime,source,inst['proc_inst_id'],None)['status']=='DONE'
    # a run without feedback carries no review_feedback input at all
    inst2=extraction.start(runtime,source,str(uuid4()))
    wi=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
    assert 'review_feedback' not in json.loads(wi['query'].split('[InputData]\n')[1])


@pytest.mark.parametrize('bad',[
    'text', {'items':'x'}, {'items':[{'verdict':'MAYBE'}]}, {'items':[{'verdict':'WRONG','note':''}]},
    {'items':[{'verdict':'WRONG','note':'이유'}]},                       # no reviewer name
    {'items':[{'verdict':'OK'}]*21,'by':'x'},
])
def test_malformed_reviewer_feedback_is_rejected_before_any_instance_starts(rt,document,bad):
    runtime,_=rt;_,source,_=document
    with pytest.raises(ValueError):extraction.start(runtime,source,str(uuid4()),review_feedback=bad)
    assert runtime.repo.list_instances(limit=None)==[]


def test_citation_coverage_is_computed_from_anchor_spans_not_self_reported(document):
    _,source,proposal=document
    cov=extraction.coverage(source,proposal)
    text=source['pages'][0]['text']
    quoted=len('정비 절차')+len('전원을 차단한 뒤 벨트를 점검한다.')   # section anchor + step anchor (procedure anchor overlaps the step)
    assert cov['pages'][0]['chars']==len(text) and cov['pages'][0]['cited']==quoted and cov['cited']==quoted
    assert 0<cov['ratio']<0.1
    proposal['sections'][0]['anchor']=dict(source_id=source['source_id'],page=1,start=0,end=len(text),quote=text)
    assert extraction.coverage(source,proposal)['ratio']==1.0


def test_sop_conflicts_lists_only_skills_owned_by_others():
    from procsvc import manual_graph
    class Tx:
        def run(self,q,**kw):
            rows=[dict(sop='SOP-A',id='skill:a',owner='doc-1'),dict(sop='SOP-B',id='skill:b',owner='doc-2'),dict(sop='SOP-C',id='skill:c',owner=None)]
            class R:
                def data(self_inner):return [r for r in rows if r['sop'] in kw['ids']]
            return R()
    class Session:
        def execute_read(self,fn):return fn(Tx())
    out=manual_graph.sop_conflicts(Session(),'doc-1',['SOP-A','SOP-B','SOP-C','SOP-NEW'])
    assert [(c['sop'],c['kind']) for c in out]==[('SOP-B','other_document'),('SOP-C','admin_knowledge')]
    assert manual_graph.sop_conflicts(Session(),'doc-1',[])==[]


def test_long_manual_prompt_is_delivered_through_the_workspace_file_not_argv(rt,tmp_path):
    """A077: a correction round carried a 21 KB previous proposal in argv and CreateProcess failed (WinError 206).
    Long prompts (long manuals, correction rounds) go to context/prompt.md; short ones stay inline."""
    from worker.runner import PROMPT_FILE
    runtime,_=rt
    archive=ManualSources(tmp_path/'manual.sqlite3')
    long_source=archive.save('hyd','long.txt',('긴 정비 매뉴얼\n'+'절차 설명 문장입니다.\n'*2500).encode())
    short_source=archive.save('hyd','short.txt','짧은 매뉴얼\n1. 설비를 정지한다.\n'.encode())
    extraction.start(runtime,long_source,str(uuid4()));extraction.start(runtime,short_source,str(uuid4()))
    reqs=[]
    runner=Runner(_settings(tmp_path/'worker'),runtime.repo,exec_fn=_fake_exec('{"proposal":{}}',requests=reqs),
                  schema_prompt='S',resolve_provider=lambda _:object())
    assert runner.poll_once()==1 and runner.poll_once()==1
    long_req=next(r for r,_ in reqs if PROMPT_FILE in r.prompt); short_req=next(r for r,_ in reqs if PROMPT_FILE not in r.prompt)
    assert len(long_req.prompt)<1000 and 'Read' in long_req.prompt
    wi=next(w for w in runtime.repo.list_workitems(limit=None) if w['activity_id']==extraction.ACTIVITY and long_source['source_id'] in (w.get('query') or ''))
    full=(tmp_path/'worker'/'hyd'/wi['id']/PROMPT_FILE).read_text(encoding='utf8')
    assert full.count('절차 설명 문장입니다.')>=2500 and '## 지시사항' in full and '## 결과 제출 형식' in full   # JSON-escaped newlines
    assert '짧은 매뉴얼' in short_req.prompt and '## 결과 제출 형식' in short_req.prompt


def test_quote_only_anchors_are_located_by_the_server_and_stored_with_offsets(rt,document,tmp_path):
    """A117 (r14 B2): the agent's proposal carries page + quote only; the stored result has start/end filled in and the
    reviewer's validation (archive.validate_anchor, offsets required) accepts it unchanged."""
    runtime,_=rt;archive,source,proposal=document
    quoted=copy.deepcopy(proposal)
    for a in [quoted['sections'][0]['anchor'],quoted['procedures'][0]['anchor'],quoted['procedures'][0]['steps'][0]['anchor']]:
        a.pop('start');a.pop('end')
    quoted['sections'][0]['anchor']['quote']='정비  절차'                          # whitespace the LLM changed
    inst=extraction.start(runtime,source,str(uuid4()))
    runner=Runner(_settings(tmp_path/'worker'),runtime.repo,exec_fn=_fake_exec(json.dumps({'proposal':quoted})),
                  schema_prompt='ManualSection Skill Step',resolve_provider=lambda _:object())
    assert runner.poll_once()==1 and runtime.poll_once()==1
    result=extraction.result(runtime,source,inst['proc_inst_id'],None)
    assert result['status']=='DONE' and (result.get('corrections') or {}).get('attempts',0)==0
    stored=result['preview']['procedures'][0]['steps'][0]['anchor']
    assert stored['start']==proposal['procedures'][0]['steps'][0]['anchor']['start'] and stored['end']==proposal['procedures'][0]['steps'][0]['anchor']['end']
    assert result['preview']['sections'][0]['anchor']['quote']=='정비 절차'      # the source's own characters
    preview=result['preview'];preview.update(reviewed=True,by='검토자',links={'SOP-EXTRACT-1':{'failureMode':'fm:bearing-degradation'}})
    assert manual_review.validate(archive,'hyd',preview)['procedures'][0]['id']=='SOP-EXTRACT-1'


def test_an_ambiguous_short_quote_goes_back_to_the_agent_as_a_correction(rt,document):
    runtime,_=rt;_,source,proposal=document
    bad=copy.deepcopy(proposal);a=bad['procedures'][0]['steps'][0]['anchor'];a.pop('start');a.pop('end');a['quote']='설명입니다.'
    inst=extraction.start(runtime,source,str(uuid4()))
    wi=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
    assert runtime.repo.save_task_result(wi['id'],{'proposal':bad},final=True)
    runtime.poll_once()
    row=runtime.repo.get_workitem(wi['id'])
    assert row['draft_status']=='FB_REQUESTED' and '긴 인용' in row['feedback']['text']
