import json
from copy import deepcopy
from pathlib import Path
from procsvc import mcp_dependencies as D, mcp_registry, procdb
from test_bpmn_import import api
from scripts.prepare_google_meeting_mapping import prepare, EXAMPLE

PARSED = {'tasks': [{'id': 'task', 'name': '일정 만들기'}]}
def mapping(server='calendar', tool='create_event', effect=True):
    return {'tasks': {'task': {'part': 'svc:mcp-call', 'config': {'server': server, 'tool': tool, 'effect': effect}}}}

def test_saved_diagnostics_never_leak_secret_and_writes_are_not_agent_reads():
    entry = {'url': 'https://host/mcp', 'headers': {'Authorization': 'SECRET_TOKEN'}}
    record = {'status': 'ok', 'fingerprint': mcp_registry.fingerprint(entry), 'tools': [{'name': 'create_event', 'read_only': False}]}
    result = D.diagnose(PARSED, mapping(), {'calendar': entry}, {'calendar': record})
    assert result['items'][0]['status'] == 'saved_check'
    assert not result['blocking'] and not result['authentication_verified'] and not result['input_schema_verified']
    assert 'SECRET_TOKEN' not in json.dumps(result)
    assert D.diagnose(PARSED, mapping(effect=False), {'calendar': entry}, {'calendar': record})['items'][0]['status'] == 'read_unconfirmed'

def test_missing_internal_tool_and_failed_stale_never_metadata():
    assert D.diagnose(PARSED, mapping(), {}, {})['items'][0]['status'] == 'missing_server'
    assert D.diagnose(PARSED, mapping(), {}, {}, ['calendar'])['items'][0]['status'] == 'internal'
    entry = {'url': 'https://host/mcp'}
    for record in [None, {'status': 'failed', 'fingerprint': mcp_registry.fingerprint(entry), 'error': 'SECRET_TOKEN'}, {'status': 'ok', 'fingerprint': 'old'}]:
        result = D.diagnose(PARSED, mapping(), {'calendar': entry}, {'calendar': record} if record else {})
        assert result['attention_count'] == 1
        assert 'SECRET_TOKEN' not in json.dumps(result)
    record = {'status': 'ok', 'fingerprint': mcp_registry.fingerprint(entry), 'tools': []}
    assert D.diagnose(PARSED, mapping(), {'calendar': entry}, {'calendar': record})['items'][0]['status'] == 'missing_tool'

def test_actual_memory_api_diagnostics_do_not_change_registration_policy(api):
    client, _, repo, _ = api
    m, _ = prepare(agent_id='sys:agent', organizer_role='정비관리자', calendar_server='calendar-unregistered', drive_server='drive-unregistered')
    imported = client.post('/api/flows/import', json={'xml': (EXAMPLE/'flow.bpmn').read_text(encoding='utf-8'), 'definition_id': 'meeting-diag'})
    assert imported.status_code == 200
    checked = client.post('/api/flows/meeting-diag/check', json={'mapping': m}).json()['check']
    assert checked['ok'] and checked['problems'] == []
    assert checked['dependencies']['attention_count'] == 2
    assert {row['status'] for row in checked['dependencies']['items']} == {'missing_server'}
    assert repo.list_instances() == []
    registered = client.post('/api/flows/meeting-diag/register', json={'mapping': m})
    assert registered.status_code == 201 and registered.json()['deployed'] is False
    assert repo.list_instances() == []


def test_metadata_is_scoped_to_requested_tenant_without_secret_output():
    repo = procdb.MemoryRepo()
    entry = {'url': 'https://host/mcp', 'headers': {'Authorization': 'OTHER_TENANT_SECRET'}}
    repo.upsert_tenant({'id': 'other', 'mcp': {'mcpServers': {'calendar': entry}}})
    store = mcp_registry.store_for(repo)
    store.checks_[('other', 'calendar')] = {'status': 'ok', 'fingerprint': mcp_registry.fingerprint(entry), 'tools': [{'name': 'create_event', 'read_only': False}]}
    assert D.for_repo(repo, 'hyd', PARSED, mapping())['items'][0]['status'] == 'missing_server'
    other = D.for_repo(repo, 'other', PARSED, mapping())
    assert other['items'][0]['status'] == 'saved_check'
    assert 'OTHER_TENANT_SECRET' not in json.dumps(other)
