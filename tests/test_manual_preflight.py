"""Read-only semantic checks do not fabricate review or modify source proposals."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import manual_api, manual_knowledge, manual_preflight
from procsvc.manual_sources import ManualSources


@pytest.fixture
def catalog():
    out = {k: [] for k in manual_knowledge.CATALOG_Q}
    out.update(actions=[dict(id='action:stop', code='CONTROLLED_STOP', kind='command', min=0, max=100)],
               failure_modes=[dict(id='fm:pump')], roles=[dict(id='role:maint-mgr')],
               suppliers=[dict(id='sup:a')], skills=[dict(id='skill:existing', sopId='SOP-EXISTING')],
               decision_tables=[dict(id='dt:allow-actions', decision='dec:allow',
                                     inputs=[dict(id='in:load', variable='load')])])
    return out


def proposal():
    return dict(sections=[], procedures=[dict(id='SOP-PM-12', name='계획 정지', steps=[dict(text='생산을 정지한다')])],
                links={'SOP-PM-12': dict(failureMode='fm:pump', kind='work_order', approver='role:maint-mgr',
                                       actions=[dict(action='action:stop', value=None)])})


def codes(value):
    return {i['code'] for i in value['issues']}


def test_pm_work_order_command_is_reported_without_changing_original(catalog):
    p = proposal()
    before = deepcopy(p)
    result = manual_preflight.validate(p, catalog)
    assert {'COMMAND_IN_WORK_ORDER', 'ACTION_VALUE_RANGE'} <= codes(result)
    assert result['checked'] and not result['technical_ready']
    assert result['needs_human_review'] is True and result['can_commit'] is False
    assert p == before and 'reviewed' not in p and 'by' not in p


def test_purchase_fm_null_remains_model_issue(catalog):
    p = proposal()
    p['links']['SOP-PM-12'] = dict(failureMode=None, relation=None, kind='work_order', actions=[])
    assert 'FAILURE_MODE_REQUIRED' in codes(manual_preflight.validate(p, catalog))
    assert p['links']['SOP-PM-12']['failureMode'] is None


def test_inline_extraction_link_and_explicit_empty_override_have_distinct_meanings(catalog):
    p = proposal()
    p['procedures'][0]['link'] = p.pop('links')['SOP-PM-12']
    before = deepcopy(p)
    assert 'COMMAND_IN_WORK_ORDER' in codes(manual_preflight.validate(p, catalog))
    assert 'FAILURE_MODE_REQUIRED' not in codes(manual_preflight.validate(p, catalog))
    assert p == before
    # An unrelated override must not discard this SOP's extracted connection.
    p['links'] = {'SOP-OTHER': {}}
    assert 'COMMAND_IN_WORK_ORDER' in codes(manual_preflight.validate(p, catalog))
    # An explicit empty override clears even a valid suggested connection.
    p['links']['SOP-PM-12'] = {}
    result = manual_preflight.validate(p, catalog)
    assert 'FAILURE_MODE_REQUIRED' in codes(result) and 'COMMAND_IN_WORK_ORDER' not in codes(result)
    assert p['procedures'][0]['link'] == before['procedures'][0]['link']


def test_explicit_replacement_overrides_inline_kind_and_actions(catalog):
    p = proposal()
    p['procedures'][0]['link'] = p.pop('links')['SOP-PM-12']
    p['links'] = {'SOP-PM-12': dict(failureMode='fm:pump', kind='control', approver='role:maint-mgr',
                                   actions=[dict(action='action:stop', value=80)])}
    assert manual_preflight.validate(p, catalog)['technical_ready'] is True
    assert p['procedures'][0]['link']['kind'] == 'work_order'


def test_historical_pm_storage_structure_is_distinct_from_actual_execution(catalog):
    p=proposal();p['sections']=[dict(ref='2')]
    p['links']['SOP-PM-12'].update(relation='PREVENTED_BY',actions=[dict(action='action:wo',value='SOP-PM-12')])
    catalog['actions'].append(dict(id='action:wo',code='WO_CREATE',kind='transaction',min=None,max=None))
    catalog['decision_tables'].append(dict(id='dt:action-candidates',decision='dec:action-candidates',
        inputs=[dict(id='in:pattern',variable='pattern')]))
    p['knowledge']=dict(rules=[dict(id='rule:pm-storage',section='2',anchor=dict(quote='정비 시점'),
        table='dt:action-candidates',effect='SELECT',tests=[dict(input='in:pattern',operator='==',value='PM_DUE')],outputs=['SOP-PM-12'])])
    before=deepcopy(p);result=manual_preflight.validate(p,catalog)
    assert result['technical_ready'] is True and result['can_commit'] is False, result['issues']
    execution=result['execution'][0]
    assert execution['ready'] is False and execution['execution_checked'] is False
    assert {i['code'] for i in execution['issues']}=={'PM_SCOPE_POLICY_REQUIRED','PM_ACTUAL_CONTEXT_REQUIRED'}
    assert p==before


@pytest.mark.parametrize('doc', ['PM-02', 'PR-07'])
def test_actual_stored_extraction_preview_inline_links_are_checked_without_rewriting(doc, catalog):
    path = Path(__file__).resolve().parents[1] / '.evidence' / 'a161-c3' / ('proposal-'+doc+'.json')
    if not path.exists():
        pytest.skip('actual local extraction evidence is absent; synthetic unit tests do not replace it')
    p = json.loads(path.read_text(encoding='utf-8'))['preview']
    before = deepcopy(p)
    assert not p.get('links') and all(isinstance(s.get('link'), dict) for s in p['procedures'])
    # Explicit seed-contract fixture, not a claim of a live/current database read.
    catalog['failure_modes'].append(dict(id='fm:volumetric-loss'))
    catalog['roles'].append(dict(id='role:purchasing'))
    catalog['suppliers'].append(dict(id='sup:b'))
    catalog['actions'].extend([
        dict(id='action:controlled-stop', code='STOP', kind='command', min=None, max=None),
        dict(id='action:set-load', code='LOAD_SET', kind='command', min=60, max=100),
        dict(id='action:work-order', code='WO_CREATE', kind='transaction', min=None, max=None),
        dict(id='action:purchase-request', code='PR_CREATE', kind='transaction', min=None, max=None),
    ])
    result = manual_preflight.validate(p, catalog)
    if doc == 'PM-02':
        assert any(i['code'] == 'COMMAND_IN_WORK_ORDER' and i['sop'] == 'SOP-PM-12' for i in result['issues'])
        assert 'FAILURE_MODE_REQUIRED' not in codes(result)
    else:
        expected = {s['id'] for s in p['procedures'] if not s['link'].get('failureMode')}
        assert len(expected) == 6
        assert {i['sop'] for i in result['issues'] if i['code'] == 'FAILURE_MODE_REQUIRED'} == expected
    assert p == before and result['can_commit'] is False and result['needs_human_review'] is True


def test_technical_pass_does_not_authorize_commit_or_review(catalog):
    p = proposal()
    p['links']['SOP-PM-12'].update(kind='control', actions=[dict(action='action:stop', value=80)])
    result = manual_preflight.validate(p, catalog)
    assert result == dict(checked=True, technical_ready=True, needs_human_review=True, can_commit=False, issues=[])


@pytest.mark.parametrize('action,expected', [
    (dict(action='action:missing', value=1), 'ACTION_NOT_FOUND'),
    (dict(action='action:purchase', value='sup:missing'), 'SUPPLIER_NOT_FOUND'),
    (dict(action='action:order', value='SOP-MISSING'), 'SOP_NOT_FOUND'),
])
def test_catalog_values_and_references(catalog, action, expected):
    catalog['actions'].extend([dict(id='action:purchase', code='PR_CREATE', kind='request', min=None, max=None),
                               dict(id='action:order', code='WO_CREATE', kind='request', min=None, max=None)])
    p = proposal()
    p['links']['SOP-PM-12']['actions'] = [action]
    assert expected in codes(manual_preflight.validate(p, catalog))


def test_shared_semantics_is_pure_and_commit_still_rechecks(catalog):
    plan = dict(procedures=[], knowledge={'rules': [dict(id='rule:r', table='dt:allow-actions',
                                                      tests=[dict(input='in:load')])]})
    before = deepcopy(plan)
    checked, issues = manual_knowledge.graph_semantics(plan, catalog)
    assert issues == [] and plan == before
    assert checked['knowledge']['rules'][0]['tests'][0]['variable'] == 'load'
    catalog['decision_tables'][0]['inputs'] = []
    _, issues = manual_knowledge.graph_semantics(plan, catalog)
    assert issues[0]['code'] == 'RULE_INPUT_NOT_DECLARED' and plan == before


def test_commit_helper_requeries_current_graph_and_keeps_rule_resolution(catalog):
    class Rows:
        def __init__(self, rows): self.rows = rows
        def data(self): return deepcopy(self.rows)

    class Tx:
        def run(self, query):
            rows = {manual_knowledge.CATALOG_Q['actions']: catalog['actions'],
                    manual_knowledge.CATALOG_Q['decision_tables']: catalog['decision_tables'],
                    'MATCH (s:Supplier) RETURN s.id AS id': catalog['suppliers'],
                    manual_knowledge.CATALOG_Q['skills']: catalog['skills']}
            return Rows(rows[query])

    class Session:
        def execute_read(self, fn): return fn(Tx())

    plan = dict(procedures=[], knowledge={'rules': [dict(id='rule:r', table='dt:allow-actions', tests=[dict(input='in:load')])]})
    assert manual_knowledge.check_graph(Session(), plan, lambda sop: sop) is plan
    assert plan['knowledge']['rules'][0]['tests'][0]['variable'] == 'load'
    catalog['decision_tables'][0]['inputs'] = []
    with pytest.raises(ValueError, match='REQUIRES_INPUT'):
        manual_knowledge.check_graph(Session(), plan, lambda sop: sop)


def test_ownership_and_missing_catalog_references_are_not_hidden(catalog):
    p = proposal()
    p['links']['SOP-PM-12'].update(failureMode='fm:missing', actions=[])
    p['conflicts'] = [dict(sop='SOP-PM-12', kind='admin_knowledge')]
    p['knowledge_conflicts'] = [dict(id='cause:collision')]
    result = manual_preflight.validate(p, catalog)
    assert {'REFERENCE_NOT_FOUND', 'SOP_OWNERSHIP_CONFLICT', 'KNOWLEDGE_OWNERSHIP_CONFLICT'} <= codes(result)


def test_explicit_reviewed_definition_removal_does_not_reuse_stale_extraction_conflict(catalog):
    p = proposal()
    p['knowledge_conflicts'] = [dict(id='cause:collision')]
    p['knowledge'] = {'failure_modes': [], 'causes': [], 'evidence': [], 'rules': []}
    original = deepcopy(p)
    assert 'KNOWLEDGE_OWNERSHIP_CONFLICT' not in codes(manual_preflight.validate(p, catalog))
    assert p == original
    p['knowledge'] = {'causes': 'invalid'}
    assert {'KNOWLEDGE_INVALID', 'KNOWLEDGE_OWNERSHIP_CONFLICT'} <= codes(manual_preflight.validate(p, catalog))


@pytest.fixture
def api(tmp_path, monkeypatch, catalog):
    archive = ManualSources(tmp_path / 'sources.sqlite')
    source = archive.save('hyd', 'source.md', b'# source\n')
    p = proposal()
    monkeypatch.setattr(manual_api.manual_graph, 'head', lambda *args: None)
    monkeypatch.setattr(manual_api.manual_graph, 'sop_conflicts', lambda *args: [])
    monkeypatch.setattr(manual_knowledge, 'conflicts', lambda *args: [])
    monkeypatch.setattr(manual_knowledge, 'catalog', lambda session: deepcopy(catalog))
    monkeypatch.setattr(manual_api.manual_extraction, 'result', lambda *args: dict(status='DONE', preview=deepcopy(p)))

    class Driver:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def session(self): return self
        def run(self, query):
            assert 'MATCH (f:FailureMode)' in query
            return SimpleNamespace(data=lambda: [])
        def execute_write(self, *args): raise AssertionError('preflight must not write')

    app = FastAPI()
    manual_api.register(app, archive_factory=lambda: archive, driver_factory=Driver, tenant='hyd',
                        audit=lambda *a: (_ for _ in ()).throw(AssertionError('no review/write audit')),
                        runtime_factory=lambda: SimpleNamespace(tenant_id='hyd'))
    return TestClient(app), '/api/kg/manuals/sources/'+source['source_id']+'/extractions/run', p


def test_extraction_get_adds_validation_but_preserves_proposal(api):
    client, url, p = api
    response = client.get(url)
    assert response.status_code == 200
    value = response.json()['preview']
    assert 'COMMAND_IN_WORK_ORDER' in codes(value['validation'])
    assert value['procedures'] == p['procedures'] and value['links'] == p['links']
    assert 'reviewed' not in value and 'by' not in value


def test_catalog_outage_is_explicit_503_not_empty_success(api, monkeypatch):
    client, url, _ = api
    def fail(session): raise RuntimeError('private connection detail')
    monkeypatch.setattr(manual_knowledge, 'catalog', fail)
    response = client.get(url)
    assert response.status_code == 503 and '지식을 읽지 못했습니다' in response.json()['detail']
    assert 'private connection detail' not in response.text


def test_read_only_get_preview_and_existing_post_have_same_validation_contract(api):
    client, url, _ = api
    preview_url = url.replace('/extractions/run', '/preview')
    responses = [client.get(preview_url), client.post(preview_url)]
    for response in responses:
        assert response.status_code == 200
        value = response.json()
        assert value['validation']['can_commit'] is False
        assert value['validation']['needs_human_review'] is True
        assert 'NO_PROCEDURES' in codes(value['validation'])
        assert 'reviewed' not in value and 'by' not in value


def test_manual_catalog_is_single_read_only_route_and_uses_current_catalog_errors(api, monkeypatch):
    client, _, _ = api
    routes = [r for r in client.app.routes if getattr(r,'path',None) == '/api/kg/manuals/catalog']
    assert len(routes) == 1
    response = client.get('/api/kg/manuals/catalog')
    assert response.status_code == 200 and 'parts' in response.json() and 'roles' in response.json()
    def fail(session): raise RuntimeError('private source failure')
    monkeypatch.setattr(manual_knowledge,'catalog',fail)
    response = client.get('/api/kg/manuals/catalog')
    assert response.status_code == 503 and 'private source failure' not in response.text
