"""A118 (r14 B3): per-document golden questions — an agent task answers from the graph, the server checks the grounding."""
import copy
import json
from uuid import uuid4

import pytest

from procsvc import engine, manual_golden as golden
from procsvc.definition_registry import validate_definition
from worker.runner import Runner
from test_worker import _settings, _fake_exec
from test_instances import rt

KNOWLEDGE = dict(ids=['ks:manual:doc:1', 'manual:doc:1:section:a', 'skill:sop-oil-21', 'skill:sop-oil-21:1'],
                 sections=[dict(id='manual:doc:1:section:a', ref='9.2', title='오일 교환')],
                 skills=[dict(id='skill:sop-oil-21', sopId='SOP-OIL-21', name='오일 교환')], steps=1)
RECORD = dict(batch='batch-1', document='doc', source_id='manual:doc:1', filename='HM-9.pdf', knowledge=KNOWLEDGE)
QUESTIONS = ['오일 교환 주기는 얼마인가?', '팬 베어링 교체 절차가 있는가?']


def report(**over):
    items = [dict(question=QUESTIONS[0], answer='2,000시간마다 교환한다 (SOP-OIL-21 1단계).', status='answerable', confidence='high',
                  cited=['skill:sop-oil-21', 'skill:sop-oil-21:1'], cypher="MATCH (s:Skill {sopId:'SOP-OIL-21'})-[:HAS_STEP]->(t) RETURN t"),
             dict(question=QUESTIONS[1], answer='이 문서에는 팬 베어링 절차가 없다.', status='not_yet_answerable', confidence='high', cited=[])]
    out = dict(items=items, summary='오일 교환은 답할 수 있고 팬 베어링은 이 문서 밖이다.')
    out.update(over)
    return out


def test_definition_is_a_product_shaped_agent_task():
    defn = validate_definition(golden.definition())
    a = defn.activities[golden.ACTIVITY]
    assert a['type'] == 'userTask' and a['agentMode'] == 'COMPLETE' and a['orchestration'] == 'cliagents' and engine.is_agent(a)
    assert defn.raw['forms']['golden_report']['contract'] == golden.CONTRACT


@pytest.mark.parametrize('questions', [[], ['x'] * 21, [''], ['a', 'a'], 'not a list', ['q' * 501]])
def test_question_lists_are_bounded_and_clean(questions):
    with pytest.raises(ValueError):
        golden.validate_questions(questions)


def test_request_pins_questions_and_the_documents_node_ids():
    req = golden.request(RECORD, ['  오일 교환 주기는 얼마인가? '], '검토자')
    assert req['questions'] == ['오일 교환 주기는 얼마인가?'] and req['knowledge']['ids'] == KNOWLEDGE['ids'] and req['by'] == '검토자'


def _req():
    return golden.request(RECORD, QUESTIONS, '검토자')


def test_valid_report_passes_and_is_returned_unchanged():
    assert golden.validate_report(_req(), report()) == report()


@pytest.mark.parametrize('change, word', [
    (lambda r: r['items'].pop(), '질문 수'),
    (lambda r: r['items'][0].update(question='다른 질문'), '받은 질문과 같아야'),
    (lambda r: r['items'][0].update(status='yes'), 'status'),
    (lambda r: r['items'][0].update(confidence='sure'), 'confidence'),
    (lambda r: r['items'][0].update(cited=['skill:sop-fan-11']), '이 문서에 없는 노드'),        # another document's SOP
    (lambda r: r['items'][0].update(cited=[]), '근거 없는 판정'),                                # answerable without grounding
    (lambda r: r['items'][1].update(status='partially_answerable'), '근거 없는 판정'),
    (lambda r: r['items'][0].update(answer=' '), 'answer'),
    (lambda r: r['items'][0].update(cited='skill:sop-oil-21'), 'cited'),
])
def test_ungrounded_or_malformed_reports_are_refused(change, word):
    bad = report(); change(bad)
    with pytest.raises(ValueError, match=word):
        golden.validate_report(_req(), bad)


def test_agent_task_runs_and_the_report_is_read_back_with_counts(rt, tmp_path):
    runtime, _ = rt
    inst = golden.start(runtime, _req(), str(uuid4()))
    rid = str(uuid4())
    assert golden.start(runtime, dict(_req(), batch='batch-2'), rid)['proc_inst_id'] == golden.start(runtime, dict(_req(), batch='batch-2'), rid)['proc_inst_id']   # same request id → same check
    reqs = []
    runner = Runner(_settings(tmp_path / 'worker'), runtime.repo, exec_fn=_fake_exec(json.dumps({'golden_report': report()}), requests=reqs),
                    schema_prompt='ManualSection Skill Step', resolve_provider=lambda _: object())
    assert runner.poll_once() == 1
    wi = runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    task = json.loads((tmp_path / 'worker' / 'hyd' / wi['id'] / 'context' / 'task.json').read_text(encoding='utf8'))
    assert QUESTIONS[0] in task['query'] and 'skill:sop-oil-21' in task['query']        # the agent sees the questions and the ids
    assert runtime.poll_once() == 1
    out = golden.result(runtime, 'batch-1')
    assert out['status'] == 'DONE' and out['questions'] == 2 and out['answerable'] == 1 and out['not_yet_answerable'] == 1 and out['grounded'] == 1
    assert out['report']['items'][0]['cited'] == ['skill:sop-oil-21', 'skill:sop-oil-21:1']


def test_an_ungrounded_answer_goes_back_to_the_agent_as_a_correction(rt):
    runtime, _ = rt
    inst = golden.start(runtime, _req(), str(uuid4()))
    wi = runtime.repo.fetch_pending_task('cliagents', 'test-worker')[0]
    bad = report(); bad['items'][0]['cited'] = ['skill:sop-fan-11']
    assert runtime.repo.save_task_result(wi['id'], {'golden_report': bad}, final=True)
    runtime.poll_once()
    row = runtime.repo.get_workitem(wi['id'])
    assert row['status'] == 'IN_PROGRESS' and row['draft_status'] == 'FB_REQUESTED' and '이 문서에 없는 노드' in row['feedback']['text']
    pending = golden.result(runtime, 'batch-1')
    assert pending['status'] == 'IN_PROGRESS' and pending['report'] is None and pending['corrections']['attempts'] == 1


def test_unknown_batch_is_a_404_style_key_error(rt):
    with pytest.raises(KeyError):
        golden.result(rt[0], 'no-such-batch')
