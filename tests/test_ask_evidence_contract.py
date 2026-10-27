"""Generic MCP evidence stays grounded in exact successful invocation records."""
import copy
import json

import pytest

from procsvc import ask
from test_b5_ask import world, _people, _ask, _work, _cli, ANSWER, SQL


def call(tool='student/read_rows', args=None, **over):
    return dict(id='call-1', tool=tool, raw_tool='mcp__' + tool.replace('/', '__'),
                input=args, data=True, ok=True, **over)


def answer(tool, query):
    return dict(status='answered', answer='조회 결과입니다.', evidence=[dict(tool=tool, query=query, result='실제 결과 요약')])


@pytest.mark.parametrize('rows', [[], [{'tag':'TS1','unit':'℃','normal':48}]])
def test_neo4j_json_rows_in_cli_result_wrapper_are_successful_evidence(rows):
    tool='mcp__neo4j__read_neo4j_cypher'
    events=[dict(event_type='tool_usage_started',data=dict(tool=tool,tool_use_id='q',input={'query':'MATCH (s:Sensor) RETURN s'})),
            dict(event_type='tool_usage_finished',data=dict(tool=tool,tool_use_id='q',output={'result':json.dumps(rows)},is_error=False))]
    calls=ask.tool_calls(events)
    result=ask.verdict(answer(tool,'MATCH (s:Sensor) RETURN s'),calls)
    assert calls[0]['ok'] and result['evidence'][0]['verified']


@pytest.mark.parametrize('tool',['read_neo4j_cypher','get_neo4j_schema'])
def test_neo4j_row_envelope_is_data_and_explicit_errors_remain_errors(tool):
    rows={'rows':[{'name':'Skill','property_count':3}],'offset':0,'next_offset':None}
    assert ask._failed({'result':json.dumps(rows)},False,'neo4j/'+tool) is None
    assert ask._failed({'result':json.dumps(dict(rows,error='query failed'))},False,'neo4j/'+tool)
    assert ask._failed({'result':json.dumps(dict(rows,isError=True))},False,'neo4j/'+tool)
    assert '응답 한도' in ask._failed({'result':json.dumps({'rows':[],'truncated':True})},False,'neo4j/'+tool)


@pytest.mark.parametrize('output,is_error', [({'result':'rejected','message':'쓰기 금지'},False),
    ({'result':'[{"tag":'},False),({'result':'[]'},True),({'result':'[]','error':'query failed'},False),
    ({'result':'[]','isError':True},False),({'result':'ok','isError':True},False),
    ({'result':'ok','error':'query failed'},False)])
def test_neo4j_row_contract_never_turns_errors_into_success(output,is_error):
    assert ask._failed(output,is_error,'neo4j/read_neo4j_cypher')


def test_full_error_payload_is_checked_even_when_preview_is_not_json():
    events=[dict(proc_inst_id='mine',event_type='tool_usage_started',data=dict(tool='enterprise/query',tool_use_id='q',input={'sql':'Q'})),
            dict(proc_inst_id='mine',event_type='tool_usage_finished',data=dict(tool_use_id='q',output='preview...',output_truncated=True,
                 full_output={'stored':True,'ref':'payload','cut':False}))]
    calls=ask.tool_calls(events,lambda _:dict(proc_inst_id='mine',content={'result':'rejected','message':'query denied'}))
    assert calls[0]['ok'] is False and 'query denied' in calls[0]['problem']


def test_actual_output_is_compared_with_claimed_numbers_and_ids(world, tmp_path):
    rt = world['rt']; _people(rt)
    value = _ask(rt)
    wrong = copy.deepcopy(ANSWER)
    wrong['answer'] = 'HYD-03의 재고는 900개입니다.'
    wrong['evidence'][0]['result'] = 'HYD-03 | 900'
    _work(rt, tmp_path, _cli(wrong))
    result = ask.view(rt, value['id'])['result']
    evidence = result['evidence'][0]
    assert evidence['verified'] and 'HYD-02' in evidence['actual_result']
    assert evidence['result_check']['status'] == 'review'
    assert 'HYD-03' in evidence['result_check']['missing']
    assert result['answer_check']['status'] == 'review'
    assert '9E+2' in result['answer_check']['missing']


def test_large_original_is_used_but_another_cases_payload_is_never_evidence():
    raw = '본문 ' * 3000 + ' skill:tail-node 78123'
    events = [dict(proc_inst_id='mine', event_type='tool_usage_started', data=dict(tool='neo4j/read_neo4j_cypher', tool_use_id='c', input={'query': 'Q'})),
              dict(proc_inst_id='mine', event_type='tool_usage_finished', data=dict(tool_use_id='c', output='잘린 미리보기', output_truncated=True,
                   full_output={'stored': True, 'ref': 'p', 'cut': False}))]
    load = lambda _: dict(proc_inst_id='mine', content=raw, meta={'cut': False})
    calls = ask.tool_calls(events, load)
    assert ask.result_comparison('skill:tail-node 78123', calls)['status'] == 'literal_match'
    assert len(calls[0]['output_text']) <= 601
    foreign = ask.tool_calls(events, lambda _: dict(proc_inst_id='other', content=raw))
    assert ask.result_comparison('78123', foreign)['status'] == 'unavailable'
    cut = ask.tool_calls(events, lambda _: dict(proc_inst_id='mine', content=raw, meta={'cut': True}))
    assert ask.result_comparison('78123', cut)['status'] == 'unavailable'


@pytest.mark.parametrize('args', [{}, {'table': 'parts', 'limit': 2},
    {'filter': {'active': False, 'ids': [1, '2'], 'deleted': None}, 'columns': ['name', 'count']}])
def test_structured_arguments_match_exact_successful_tool(args):
    out = answer('mcp__student__read_rows', copy.deepcopy(args))
    ask.validate_answer(out)
    result = ask.verdict(out, [call(args=args)])
    assert result['kind'] == 'answered' and result['evidence'][0]['call'] == 'call-1'


@pytest.mark.parametrize('claimed', [
    {'table': 'parts'}, {'table': 'parts', 'limit': 1, 'extra': None},
    {'table': 'parts', 'limit': True}, {'table': 'parts', 'limit': '1'},
    {'table': 'PARTS', 'limit': 1}, {},
])
def test_missing_extra_changed_or_wrongly_typed_argument_is_not_evidence(claimed):
    out = answer('student/read_rows', claimed)
    ask.validate_answer(out)
    assert ask.verdict(out, [call(args={'limit': 1, 'table': 'parts'})])['kind'] == 'unanswerable'


def test_key_order_is_irrelevant_but_array_order_and_tool_server_are_not():
    actual = call(args={'columns': ['name', 'count'], 'filter': {'x': 1, 'y': 2}})
    out = answer('student/read_rows', {'filter': {'y': 2, 'x': 1}, 'columns': ['name', 'count']})
    assert ask.verdict(out, [actual])['kind'] == 'answered'
    out['evidence'][0]['query']['columns'].reverse()
    assert ask.verdict(out, [actual])['kind'] == 'unanswerable'
    for tool in ('other/read_rows', 'student/describe_table', 'read_rows'):
        assert ask.verdict(answer(tool, actual['input']), [actual])['kind'] == 'unanswerable'


def test_empty_args_do_not_match_missing_input_or_failed_or_running_call():
    out = answer('student/list_tables', {})
    for candidate in (call('student/list_tables'),
                      dict(call('student/list_tables', {}), ok=False),
                      dict(call('student/list_tables', {}), ok=None)):
        assert ask.verdict(out, [candidate])['kind'] == 'unanswerable'


def test_codex_advertised_server_alias_matches_real_trace_but_rejects_collision():
    # Actual student-complete trace: Codex advertises underscores, events keep
    # the registered hyphenated MCP server. Tool and full arguments stay exact.
    server = 'overnight-20261012-3721fe7d-table'
    args = {'limit': 100, 'table': 'attendee', 'where': {'meeting_id': 's00:meeting-q3'},
            'columns': ['email', 'required', 'response']}
    out = answer('mcp__overnight_20261012_3721fe7d_table__read_rows', args)
    original = call(server + '/read_rows', args)
    result = ask.verdict(out, [original])
    assert result['kind'] == 'answered' and result['evidence'][0]['call'] == original['id']
    assert ask.verdict(out, [original, dict(original, id='repeat')])['kind'] == 'answered'
    collision = call(server.replace('-', '_') + '/read_rows', args)
    assert ask.verdict(out, [original, collision])['kind'] == 'unanswerable'
    assert ask.verdict(out, [call(server + '/read_rows', {'table': 'other', 'limit': 5})])['kind'] == 'unanswerable'
    assert ask.verdict(out, [call(server + '/describe_table', args)])['kind'] == 'unanswerable'
    assert ask.verdict(out, [call('unrelated/read_rows', args)])['kind'] == 'unanswerable'


def test_sql_legacy_shape_requires_whole_query_and_actual_tool():
    successful = call('enterprise/query', {'sql': SQL})
    assert ask.verdict(ANSWER, [successful])['kind'] == 'answered'
    assert ask.verdict(answer('enterprise/query', SQL + ';\n'), [successful])['kind'] == 'answered'
    for query in (SQL.replace(' limit 1', ''), SQL + '0', "select asset from x where name='UPPER'"):
        assert ask.verdict(answer('enterprise/query', query), [successful])['kind'] == 'unanswerable'
    assert ask.verdict(answer('wrong/query', SQL), [successful])['kind'] == 'unanswerable'
    assert ask.verdict(answer('enterprise/query', "select * from x where name='upper'"),
                       [call('enterprise/query', {'sql': "select * from x where name='UPPER'"})])['kind'] == 'unanswerable'
    assert ask.verdict(answer('student/read_rows', 'parts'),
                       [call(args={'table': 'parts', 'limit': 1})])['kind'] == 'unanswerable'


@pytest.mark.parametrize('bad', [None, [], True, 1, '', {'x': float('nan')}])
def test_invalid_query_shapes_are_rejected(bad):
    with pytest.raises(ValueError, match='query'):
        ask.validate_answer(answer('student/read_rows', bad))


def test_generic_mcp_end_to_end_and_form_specific_correction(world, tmp_path):
    rt = world['rt']; _people(rt)
    view = _ask(rt)
    requests = []
    invalid = dict(status='answered', answer='조회했습니다', evidence=[dict(tool='enterprise/read_rows', query=None)])
    _work(rt, tmp_path, _cli(invalid, requests=requests))
    row = rt.repo.get_workitem(view['workitem'])
    assert row['draft_status'] == 'FB_REQUESTED'
    feedback = row['feedback']['text']
    assert '질문 답변' in feedback and 'arguments JSON' in feedback and 'cannot_answer' in feedback
    assert not any(word in feedback for word in ('proposal', 'anchor', 'page_reviews', '추출 제안'))
    assert 'arguments JSON' in requests[0].prompt
    args = {'table': 'inventory', 'limit': 2, 'where': {'active': False}}
    fixed = answer('enterprise/read_rows', args)
    _work(rt, tmp_path, _cli(fixed, calls=(('mcp__enterprise__read_rows', args, '{"rows": []}'),), requests=requests))
    result = ask.view(rt, view['id'])
    assert result['state'] == 'done' and result['result']['kind'] == 'answered'
    assert requests[1].resume_session == 's1' and '질문 답변' in requests[1].prompt
    assert len(rt.repo.get_workitem(view['workitem'])['feedback']['history']) == 1


def test_three_bad_answers_block_with_question_specific_event(world, tmp_path):
    rt = world['rt']; _people(rt)
    view = _ask(rt)
    for _ in range(3):
        _work(rt, tmp_path, _cli(dict(status='answered', answer='근거 없음')))
    row = rt.repo.get_workitem(view['workitem'])
    assert row['status'] == 'PENDING' and len(row['feedback']['history']) == 3
    events = [e for e in rt.repo.list_events(todo_id=row['id']) if e['job_id'] == 'TASK_REJECTED']
    assert events[-1]['data']['name'] == '질문 답변 거부 · 사람 확인 필요'
    assert events[-1]['data']['recovery'] == 'human_review'
