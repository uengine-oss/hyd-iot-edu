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
    assert source['pages'][0]['text'][-20:] in json.loads(reqs[0][0].prompt.split('[InputData]\n')[1].split('\n\n##')[0])['manual_source']['pages'][0]['text']
    wi=runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
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
