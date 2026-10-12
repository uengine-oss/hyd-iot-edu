"""Structural/schema proofs only; no OAuth, Google HTTP, or live registration."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import prepare_google_meeting_mapping as prep
from students._template.google_meeting_mcp.server import Failure, MeetingTools, build
from procsvc import effect_parts, mcp_check
from test_bpmn_import import api


def prepared(**kwargs):
    return prep.prepare(**dict(dict(agent_id='sys:agent', organizer_role='정비관리자',
                                    calendar_server='gcal-course', drive_server='gdrive-course'), **kwargs))


def inputs():
    # Explicit unit fixture, not observed Google identities or availability.
    option = dict(slot='2026-10-20T14:00:00+09:00', end='2026-10-20T15:00:00+09:00',
                  room='R1', room_email='room@resource.calendar.google.com', reason='fixture', score=1)
    context = dict(request_id='unit-request', meeting_calendar_id='primary', meeting_title='단위 회의',
                   meeting_duration_min=60, meeting_time_zone='Asia/Seoul',
                   meeting_attendees=[dict(email='participant@company.co.kr', required=True),
                                      dict(email='optional@company.co.kr', required=False)],
                   meeting_required_emails=['participant@company.co.kr'],
                   meeting_room_resources={'R1': option['room_email']},
                   meeting_attachments=[dict(title='단위 문서', file_url='https://docs.google.com/document/d/unit-id/edit')])
    proposal = dict(options=[option], recommended=option['slot'], losers=[],
                    docs=[dict(title='단위 문서', link=context['meeting_attachments'][0]['file_url'])])
    return context, option, proposal


def validate(context, option, proposal):
    return prep.validate_runtime(context, option, execution_key='unit-instance:unit-workitem', proposal=proposal)


def test_invalid_inputs_fail_before_any_prepared_execution():
    context, option, proposal = inputs()
    del context['meeting_calendar_id']
    with pytest.raises(ValueError, match='meeting_calendar_id'):
        validate(context, option, proposal)
    context, option, proposal = inputs()
    proposal['options'].append(dict(slot=['malformed']))
    with pytest.raises(ValueError, match='고유한'):
        validate(context, option, proposal)


def test_actual_memory_portal_import_check_and_typed_plumbing(api):
    client, _, repo, _ = api
    xml = (prep.EXAMPLE / 'flow.bpmn').read_text(encoding='utf-8')
    originals = {p.name: p.read_bytes() for p in prep.EXAMPLE.iterdir() if p.is_file()}
    mapping, requirements = prepared()
    assert client.post('/api/flows/import', json=dict(xml=xml, definition_id='qbr-prep')).status_code == 200
    result = client.post('/api/flows/qbr-prep/check', json=dict(mapping=mapping))
    assert result.status_code == 200
    checked = result.json()['check']
    assert checked['ok'], checked['problems']
    definition = checked['definition']
    types = {v['name']: v['type'] for v in definition['data']}
    assert types['all_required_accepted'] == 'Boolean' and types['event_id'] == 'Text'
    assert types['meeting_attendees'] == types['meeting_required_emails'] == 'Array'
    assert types['meeting_room_resources'] == 'Object'
    assert types['meeting_duration_min'] == 'Number'
    assert 'meeting_execution_key' not in types
    assert requirements['execution_ready'] is False and requirements['registration_verified'] is False
    assert requirements['google_read_verified'] is False
    assert repo.list_instances() == []
    assert {p.name: p.read_bytes() for p in prep.EXAMPLE.iterdir() if p.is_file()} == originals


def test_mapping_preserves_rejection_delay_and_read_confirmation(api):
    mapping, _ = prepared()
    original = json.loads((prep.EXAMPLE / 'mapping.json').read_text(encoding='utf-8'))
    assert mapping['flows'] == original['flows'] and mapping['timers'] == original['timers']
    assert mapping['tasks']['Activity_approve']['config'] == original['tasks']['Activity_approve']['config']
    for name in ('Activity_report_ok', 'Activity_report_ng', 'Activity_report_reject', 'Activity_report_delay'):
        assert mapping['tasks'][name] == original['tasks'][name]
    assert mapping['tasks']['Activity_check']['config']['effect'] is False
    assert 'idempotency_key' not in mapping['tasks']['Activity_invite']['config']['arguments']
    # Existing importer must still reject a route that bypasses approval.
    client, _, _, _ = api
    client.post('/api/flows/import', json=dict(xml=(prep.EXAMPLE/'flow.bpmn').read_text(encoding='utf-8'), definition_id='reject-proof'))
    mapping['flows']['Flow_approve_yes'] = dict(default=True)
    mapping['flows']['Flow_approve_no'] = dict(var='approval', op='==', value='승인')
    bad = client.post('/api/flows/reject-proof/check', json=dict(mapping=mapping)).json()['check']
    assert not bad['ok'] and any('반려' in p['reason'] for p in bad['problems'])


def test_registered_names_are_not_guessed_and_unknown_agent_is_rejected(api):
    for field in ('agent_id', 'organizer_role', 'calendar_server', 'drive_server'):
        with pytest.raises(ValueError):
            prepared(**{field: '<채우기>'})
    client, _, _, _ = api
    mapping, _ = prepared(agent_id='unregistered-agent')
    client.post('/api/flows/import', json=dict(xml=(prep.EXAMPLE/'flow.bpmn').read_text(encoding='utf-8'), definition_id='agent-proof'))
    bad = client.post('/api/flows/agent-proof/check', json=dict(mapping=mapping)).json()['check']
    assert not bad['ok'] and any(p['field'] == 'agent' for p in bad['problems'])


def test_exact_server_input_schema_and_typed_render_without_google(monkeypatch):
    class NoAPI:
        def request(self, *a, **kw):
            pytest.fail('schema preparation must not call Google')
    async def listed():
        # In-process MCP protocol/catalog, no HTTP listener or credential file.
        async with Client(build(MeetingTools(NoAPI()))) as client:
            return {t.name: t for t in await client.list_tools()}
    schemas = asyncio.run(listed())
    mapping, _ = prepared()
    context, option, proposal = inputs()
    full = validate(context, option, proposal)
    values = dict(context, approved_option=option, proposal=proposal)
    invite = mapping['tasks']['Activity_invite']['config']
    rendered = effect_parts.render(invite['arguments'], values)
    assert rendered == {k: v for k, v in full.items() if k != 'idempotency_key'}
    validator = Draft202012Validator(schemas['create_event'].inputSchema)
    assert any(e.validator == 'required' for e in validator.iter_errors(rendered))
    calls = []
    class LocalSession:
        def request(self, method, params):
            assert method == 'tools/call'
            calls.append(deepcopy(params['arguments']))
            validator.validate(params['arguments'])
            return {'content': [{'type': 'text', 'text': '{"document":{"event_id":"unit-event"}}'}]}
    monkeypatch.setattr(mcp_check, '_list_tools', lambda session: [
        dict(name='create_event', input_schema=schemas['create_event'].inputSchema)])
    monkeypatch.setattr(mcp_check, '_with_session', lambda spec, timeout, work: work(LocalSession()))
    for _ in range(2):
        result = mcp_check.call_effect({}, 'create_event', rendered, idempotency_key=full['idempotency_key'])
        assert result['status'] == 'ok' and result['idempotent'] is True
    assert calls == [full, full]
    assert 'idempotency_key' not in rendered
    contract = json.loads(prep.CONTRACT.read_text(encoding='utf-8'))
    assert 'idempotency_key' not in contract['Activity_invite']['arguments']
    check = mapping['tasks']['Activity_check']['config']
    read_args = effect_parts.render(check['arguments'], dict(values, event_id='unit-event'))
    Draft202012Validator(schemas['get_event'].inputSchema).validate(read_args)
    assert read_args['required_emails'] == context['meeting_required_emails']
    assert schemas['get_event'].annotations.readOnlyHint is True
    assert schemas['create_event'].annotations.readOnlyHint is False


@pytest.mark.parametrize('key', ['request_id', *[k for k, _, _ in prep.CONTEXT_FIELDS]])
def test_missing_required_context_cannot_become_success_values(key):
    context, option, proposal = inputs()
    del context[key]
    with pytest.raises(ValueError):
        validate(context, option, proposal)


@pytest.mark.parametrize('change', ['demo_attendee', 'demo_room', 'unmapped_room', 'wrong_roster',
                                   'empty_roster', 'unknown_required', 'different_duration',
                                   'missing_end', 'fake_attachment', 'different_docs', 'duplicate_slot'])
def test_fake_or_inconsistent_execution_inputs_are_rejected(change):
    context, option, proposal = inputs()
    if change == 'demo_attendee': context['meeting_attendees'][0]['email'] = 'name@example.com'
    if change == 'demo_room':
        option['room_email'] = 'room@example.com'; context['meeting_room_resources']['R1'] = option['room_email']
    if change == 'unmapped_room': context['meeting_room_resources'] = {}
    if change == 'wrong_roster': context['meeting_required_emails'] = ['optional@company.co.kr']
    if change == 'empty_roster': context['meeting_required_emails'] = []
    if change == 'unknown_required': context['meeting_attendees'][0].pop('required')
    if change == 'different_duration': context['meeting_duration_min'] = 90
    if change == 'missing_end': option.pop('end')
    if change == 'fake_attachment': context['meeting_attachments'][0]['file_url'] = 'https://drive.google.com/'
    if change == 'different_docs': proposal['docs'] = []
    if change == 'duplicate_slot': proposal['options'].append(deepcopy(option))
    with pytest.raises((ValueError, Failure)):
        validate(context, option, proposal)


def test_required_response_boolean_and_extract_meaning_are_actual_server_contract():
    class FixtureAPI:
        def __init__(self): self.response = 'needsAction'
        def request(self, method, url, **kwargs):
            assert method == 'GET'
            return dict(id='unit-event', attendees=[dict(email='participant@company.co.kr', responseStatus=self.response),
                                                   dict(email='optional@company.co.kr', responseStatus='declined')])
    api = FixtureAPI()
    tools = MeetingTools(api)
    mapping, _ = prepared()
    cfg = mapping['tasks']['Activity_check']['config']
    for response, expected in [('needsAction', False), ('declined', False), ('tentative', False), ('accepted', True)]:
        api.response = response
        result = tools.invoke(tools.get_event, 'primary', 'unit-event', ['participant@company.co.kr'])
        # Real envelope and real roster calculation; upstream response is a unit fixture.
        shaped = mcp_check.shape_result({'content': [{'type': 'text', 'text': json.dumps(result)}]}, 20000)
        assert effect_parts.extract_values(cfg['extract'], shaped) == {'all_required_accepted': expected}


def test_cli_writes_independent_copy_and_never_overwrites_original(tmp_path):
    args = ['--agent-id', 'sys:agent', '--organizer-role', '정비관리자', '--calendar-server', 'gcal-course',
            '--drive-server', 'gdrive-course', '--output-dir', str(tmp_path)]
    assert prep.main(args) == 0
    assert (tmp_path/'flow.bpmn').read_bytes() == (prep.EXAMPLE/'flow.bpmn').read_bytes()
    assert json.loads((tmp_path/'preconditions.json').read_text(encoding='utf-8'))['execution_ready'] is False
    with pytest.raises(SystemExit): prep.main(args)
    with pytest.raises(SystemExit): prep.main(args[:-1] + [str(prep.EXAMPLE)])
