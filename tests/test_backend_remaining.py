"""New backend contracts, using real routes/runtime and bounded external IO doubles."""
from copy import deepcopy
from pathlib import Path

import pytest

from procsvc import work_rules
from worker import bridge, payloads, prompt
from test_b1_agent_authoring import env
from test_bpmn_import import api, LOOP, B, loop_mapping
from test_failed_attempt_trace import failing_case, world


def test_work_rules_roundtrip_preserves_omitted_and_rejects_unknown(env):
    client, rt = env
    catalog = client.get('/api/agent-authoring/options').json()['work_rules']
    assert catalog == [{'key': 'hyd-plant', 'label': work_rules.HYD_PLANT.title,
                        'content': work_rules.constitution(work_rules.HYD_PLANT)}]
    body = {'name': '업무 규칙 선택 시험', 'goal': '규칙을 따른다', 'work_rules': 'hyd-plant'}
    created = client.post('/api/agents', json=body)
    assert created.status_code == 201, created.text
    aid = created.json()['id']
    card = client.get(f'/api/agents/{aid}').json()
    assert card['work_rules_detail'] == catalog[0] and card['run']['settings']['work_rules'] == 'hyd-plant'
    body.pop('work_rules')
    assert client.put(f'/api/agents/{aid}', json=body).status_code == 200
    assert client.get(f'/api/agents/{aid}').json()['work_rules'] == 'hyd-plant'
    assert client.put(f'/api/agents/{aid}', json={**body, 'work_rules': 'missing'}).status_code == 422
    assert client.get(f'/api/agents/{aid}').json()['work_rules'] == 'hyd-plant'
    assert client.put(f'/api/agents/{aid}', json={**body, 'work_rules': None}).status_code == 200
    assert client.get(f'/api/agents/{aid}').json()['work_rules_detail'] is None


def test_invalid_stored_rule_is_visible_not_replaced(env):
    client, rt = env
    user = rt.repo.list_users(['sys:agent'], 'hyd')[0]
    rt.repo.upsert_user({**user, 'work_rules': 'removed-rule'})
    card = client.get('/api/agents/sys:agent').json()
    assert card['work_rules'] == 'removed-rule'
    assert card['work_rules_detail']['content'] is None
    assert 'removed-rule' in card['work_rules_detail']['error']


def test_mcp_reselection_revokes_old_servers_without_relocating_login(tmp_path):
    bridge.install(tmp_path, {'mcpServers': {'old': {'url': 'https://old.invalid/mcp'}}})
    new = bridge.install(tmp_path, {'mcpServers': {'new': {'url': 'https://new.invalid/mcp'}}})
    assert new.servers == ['new']
    assert '--strict-mcp-config' in new.extra_args and 'CLAUDE_CONFIG_DIR' not in new.env
    assert new.env['ENABLE_CLAUDEAI_MCP_SERVERS'] == 'false'
    assert bridge.install(tmp_path, {'mcpServers': {}}).servers == []


def test_every_continuation_keeps_korean_visible_narration_instruction():
    for text in (prompt.resume_prompt('답변'), prompt.resume_prompt('답변', restarted=True),
                 prompt.format_correction('필수 필드 누락', [{'key': 'answer', 'type': 'text'}])):
        assert prompt.LANGUAGE_RULE in text


def test_saved_output_is_bound_to_one_project_and_session(tmp_path):
    env = {'CLAUDE_CONFIG_DIR': str(tmp_path / 'config')}
    own = payloads.result_directory(str(tmp_path / 'work'), 'session1', env)
    others = [payloads.result_directory(str(tmp_path / 'work'), 'session2', env),
              payloads.result_directory(str(tmp_path / 'other-work'), 'session1', env),
              tmp_path / 'secret' / 'tool-results']
    for directory in [own, *others]:
        directory.mkdir(parents=True)
        path = directory / 'result.txt'
        path.write_text('private result', encoding='utf-8')
        message = f'Error: result (160000 characters) exceeds maximum allowed tokens. Output has been saved to {path}.'
        assert payloads.saved_path(message, allowed_directory=own) == (path.resolve() if directory == own else None)
        assert payloads.saved_path(message) is None
    assert payloads.result_directory(str(tmp_path), '../session', env) is None


def test_saved_output_symlink_cannot_escape_session(tmp_path):
    own = tmp_path / 'session' / 'tool-results'
    own.mkdir(parents=True)
    secret = tmp_path / 'secret.txt'
    secret.write_text('secret', encoding='utf-8')
    link = own / 'result.txt'
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip('OS does not permit symlink creation')
    assert payloads.saved_path(f'saved to {link}', allowed_directory=own) is None


def test_flow_single_delete_is_scoped_and_refuses_running_and_baseline(api):
    client, rt, repo, audits = api
    writes = []
    def graph(q, **params):
        writes.append((q, params))
        return [{'projection_key': params['id'], 'projection_revision': params['revision'], 'projection_hash': params['payload_hash']}]
    rt.hooks.record_cypher = graph
    for did in ['delete-one', 'keep-one']:
        assert client.post('/api/flows/import', json={'xml': LOOP, 'definition_id': did}).status_code == 200
        assert client.post(f'/api/flows/{did}/register', json={'mapping': loop_mapping(B.parse_bpmn(LOOP))}).status_code == 201
    inst = rt.start_definition('delete-one', '1', 'DELETE-CASE', values={'sample_id': 'S-1'})
    assert client.delete('/api/flows/delete-one').status_code == 409
    wi = next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['status'] == 'IN_PROGRESS')
    rt.submit(wi['id'], {'iso_code': 10})
    # A graph outage must retain the durable tombstone delivery after source deletion.
    def offline(*args, **kwargs):
        raise ConnectionError('graph offline')
    rt.hooks.record_cypher = offline
    deleted = client.delete('/api/flows/delete-one?by=student')
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()['projection_pending'] == 1
    assert repo.get_proc_def('delete-one', version='1') is None
    assert repo.get_proc_def('keep-one', version='1') is not None
    assert client.get('/api/flows/keep-one').status_code == 200
    assert client.delete('/api/flows/anomaly_response').status_code == 403
    assert client.delete('/api/flows/missing').status_code == 404
    rt.hooks.record_cypher = graph
    rt._project({'proc_inst_id': inst['proc_inst_id']})
    assert repo.projection_status('hyd', inst['proc_inst_id'])['pending'] == 0
    assert writes[-1][1]['delete_definition'] is True


def test_system_pending_can_close_without_claiming_business_success(world):
    rt, inst, calls = failing_case(world)
    wi = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id'] == 'T_check')
    original_log = wi['log']
    result = rt.close_agent_task(wi['id'], '담당자', '도구 연결 실패로 실습 종료')
    assert result['status'] == 'CANCELLED' and result['end_event'] == 'closed-by-human'
    assert original_log in rt.repo.get_workitem(wi['id'])['log']
    events = rt.repo.list_events(todo_id=wi['id'])
    assert len([e for e in events if e['event_type'] == 'error']) == 3
    assert any(e['data'].get('name') == '시스템 작업 닫음' for e in events)


@pytest.mark.parametrize('status', ['IN_PROGRESS', 'SUBMITTED', 'TODO', 'DONE'])
def test_system_live_or_unreached_or_finished_cannot_close(world, status):
    rt, inst, calls = failing_case(world)
    wi = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id'] == 'T_check')
    wi.update(status=status, draft_status='FAILED')
    rt.repo.update_workitem(wi)
    with pytest.raises(ValueError, match='멈춘'):
        rt.close_agent_task(wi['id'], '담당자', '닫기')
    assert rt.repo.get_workitem(wi['id'])['status'] == status
