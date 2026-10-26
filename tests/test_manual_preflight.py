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
                                     inputs=[dict(id='in:load', variable='load')])],
               candidate_failure_modes=[dict(id='fm:pump')])    # fm:pump 고장 조치는 기존 후보 규칙에 자동 합류한다
    return out


def proposal():
    return dict(sections=[], procedures=[dict(id='SOP-PM-12', name='계획 정지', steps=[dict(text='생산을 정지한다')])],
                links={'SOP-PM-12': dict(failureMode='fm:pump', kind='work_order', approver='role:maint-mgr',
                                       actions=[dict(action='action:stop', value=None)])})


def codes(value):
    return {i['code'] for i in value['issues']}


def test_source_numeric_discrepancies_are_reported_without_guessing_conversions(catalog):
    p = proposal()
    p['procedures'][0]['steps'][0]['anchor'] = {'quote': '팬을 100 %로 올린다'}
    p['links']['SOP-PM-12']['actions'][0]['value'] = 80
    p['knowledge'] = {
        'evidence': [{'id': 'evd:hot', 'threshold': 75, 'anchor': {'quote': '온도 70 ℃ 초과'}}],
        'rules': [{'id': 'rule:interval', 'tests': [{'input': 'in:hours', 'value': 2500}],
                   'anchor': {'quote': '정비 간격은 2,000 시간'}}]}
    notices = manual_knowledge.source_value_warnings(p)
    assert len(notices) == 3 and all('수치를 찾지 못했습니다' in n for n in notices)
    assert any('80' in n for n in notices) and any('75' in n for n in notices) and any('2500' in n for n in notices)
    p['links']['SOP-PM-12']['actions'][0]['value'] = 100
    p['knowledge']['evidence'][0]['threshold'] = 70
    p['knowledge']['rules'][0]['tests'][0]['value'] = 2000
    assert manual_knowledge.source_value_warnings(p) == []
    # 60 minutes may be 1 hour, but matching numbers alone cannot establish this.
    p['knowledge']['rules'][0]['anchor']['quote'] = '60 분 간격'
    p['knowledge']['rules'][0]['tests'][0]['value'] = 1
    assert '단위 환산' in manual_knowledge.source_value_warnings(p)[0]


def test_preflight_applies_reviewers_override_to_numeric_notice(catalog):
    p = proposal()
    p['procedures'][0]['steps'][0]['anchor'] = {'quote': '설정 100 %'}
    p['procedures'][0]['link'] = {'actions': [{'action': 'action:stop', 'value': 100}]}
    p['links']['SOP-PM-12']['actions'][0]['value'] = 80
    before = deepcopy(p)
    result = manual_preflight.validate(p, catalog)
    assert p == before and any('80' in n for n in result['source_value_warnings'])


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
    # 실제 워커 추출이 저장한 미리보기의 고정본(손질 내역: fixtures/manual-extraction-proposals/README.md).
    # 커밋하지 않는 .evidence/a161-c3 는 실행마다 바뀌어 이 시험이 그날 추출에 따라 늘 실패했다.
    path = Path(__file__).resolve().parent / 'fixtures' / 'manual-extraction-proposals' / ('proposal-'+doc+'.json')
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
        # 구매 문서의 절차는 모두 고장 유형이 없다(고정본: SOP-PUR-11·12·13 · SOP-PR7-7)
        assert expected == {s['id'] for s in p['procedures']} and len(expected) == 4
        # 지금 추출 계약은 구매 절차의 인라인 link 에 scope='purchase' 를 두고, 검사는 그 범위를 고장 유형 필수에서 뺀다
        # (manual_preflight: scope != 'purchase' 일 때만 FAILURE_MODE_REQUIRED). 인라인 link 를 읽지 않으면 네 절차 모두
        # FAILURE_MODE_REQUIRED 가 되고, 읽으면 같은 네 절차가 구매 범위 검사(실행 시스템 · 부품)를 받는다.
        assert 'FAILURE_MODE_REQUIRED' not in codes(result)
        assert {i['sop'] for i in result['issues'] if i['code'] == 'PURCHASE_SYSTEM_NOT_FOUND'} == expected
        assert {e['sop']: e['executable'] for e in result['execution']} == {s['id']: s['link']['executable'] for s in p['procedures']}
    assert p == before and result['can_commit'] is False and result['needs_human_review'] is True


def test_executable_sop_no_candidate_rule_can_reach_is_reported(catalog):
    # 2026-10-23 리허설: 구조판에 후보 규칙이 없고 문서도 후보 규칙을 내지 않으면 적재돼도 판단이 그 절차를 후보로 내지 못한다
    catalog['candidate_failure_modes'] = []
    p = proposal()
    p['links']['SOP-PM-12'].update(kind='control', actions=[dict(action='action:stop', value=80)])
    result = manual_preflight.validate(p, catalog)
    assert [(i['code'], i['sop'], i['field']) for i in result['issues']] == [('CANDIDATE_RULE_MISSING', 'SOP-PM-12', 'knowledge.rules')]
    # 예방 정비(PREVENTED_BY)는 기존 후보 규칙이 있어도 자동 합류하지 않는다
    catalog['candidate_failure_modes'] = [dict(id='fm:pump')]
    p['links']['SOP-PM-12']['relation'] = 'PREVENTED_BY'
    assert 'CANDIDATE_RULE_MISSING' in codes(manual_preflight.validate(p, catalog))
    # 참고 절차 · 실행하지 않는 절차는 후보가 아니므로 묻지 않는다
    p['links']['SOP-PM-12'] = dict(kind='reference', executable=False, actions=[], addresses=[], affects=[],
                                   scope=None, parts=None, supplier_policy=None, failureMode=None, relation=None, approver=None)
    assert 'CANDIDATE_RULE_MISSING' not in codes(manual_preflight.validate(p, catalog))


def test_blank_link_values_mean_absent_as_the_extraction_instruction_says(catalog):
    # 지시는 「확인할 수 없는 link 값은 비워 두라」 — 2026-10-23 리허설에서 ''로 비운 고장 유형이 잘못된 id로 거부됐다
    p = proposal()
    p['links']['SOP-PM-12'].update(kind='control', relation='', approver='', actions=[dict(action='action:stop', value=80)])
    assert manual_preflight.validate(p, catalog)['technical_ready'] is True
    p['links']['SOP-PM-12']['failureMode'] = ''
    assert 'FAILURE_MODE_REQUIRED' in codes(manual_preflight.validate(p, catalog))    # 값이 꼭 필요한 곳은 여전히 「필요합니다」


def test_technical_pass_does_not_authorize_commit_or_review(catalog):
    p = proposal()
    p['links']['SOP-PM-12'].update(kind='control', actions=[dict(action='action:stop', value=80)])
    result = manual_preflight.validate(p, catalog)
    assert {k: result[k] for k in ('checked','technical_ready','needs_human_review','can_commit','issues')} == dict(checked=True, technical_ready=True, needs_human_review=True, can_commit=False, issues=[])
    assert any('80' in n for n in result['source_value_warnings'])


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


def test_revision_preview_resolves_rule_input_ids_before_rendering(catalog, tmp_path):
    from procsvc import manual_graph, manual_review
    from test_manual_review import reviewed
    archive = ManualSources(tmp_path / 'review.sqlite')
    _, body = reviewed(archive)
    plan = manual_review.validate(archive, 'hyd', body)
    plan['knowledge'] = {'rules': [dict(id='rule:review', table='dt:allow-actions',
        tests=[dict(input='in:load', operator='>=', value=60, unit='')], effect='ALLOW',
        order=1, annotation='', penalty=None, outputs=[], applies_to=[], penalizes=None,
        section=plan['sections'][0]['ref'])]}
    class Rows:
        def __init__(self, rows): self.rows = rows
        def data(self): return deepcopy(self.rows)
        def single(self): return None
    class Session:
        def execute_read(self, fn): return fn(self)
        def run(self, query, **params):
            assert query.startswith('MATCH '), '미리보기에서 쓰기를 실행하면 안 됨'
            if 'ManualIngestionDocument' in query: return Rows([])
            return Rows({manual_knowledge.CATALOG_Q['actions']: catalog['actions'],
                manual_knowledge.CATALOG_Q['decision_tables']: catalog['decision_tables'],
                'MATCH (s:Supplier) RETURN s.id AS id': catalog['suppliers'],
                manual_knowledge.CATALOG_Q['skills']: catalog['skills']}[query])
    assert manual_graph.revision_preview(Session(), plan)['removed'] == []
    assert plan['knowledge']['rules'][0]['tests'][0]['variable'] == 'load'
    catalog['decision_tables'][0]['inputs'] = []
    with pytest.raises(ValueError, match='REQUIRES_INPUT'):
        manual_graph.revision_preview(Session(), plan)


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


def test_extraction_submit_rejects_work_order_without_sop_value_like_commit_would(catalog):
    """2026-10-25 수업 한 바퀴: PM-02 추출이 SOP-PM-13(미루기)의 작업지시 값을 null 로 냈고 추출은 통과 — 적재에서야 「작업지시 값은 SOP
    번호여야 합니다(None)」로 막혔다(학생 화면에 고칠 칸 없음). 제출 때 같은 규칙으로 교정 사유를 준다. 다른 결함(명령 범위 등)은 여전히 사람 검토 몫."""
    from procsvc import manual_extraction
    catalog['actions'].append(dict(id='action:order', code='WO_CREATE', kind='transaction', min=None, max=None))
    p = proposal()
    p['links']['SOP-PM-12']['actions'] = [dict(action='action:order', value=None)]
    with pytest.raises(ValueError, match='작업지시 값은 SOP 번호여야 합니다'):
        manual_extraction.check_action_values(p, catalog)
    p['links']['SOP-PM-12']['actions'] = [dict(action='action:order', value='SOP-PM-12')]
    manual_extraction.check_action_values(p, catalog)                 # 자기 SOP ID 면 통과
    p['links']['SOP-PM-12']['actions'] = [dict(action='action:stop', value=None)]
    manual_extraction.check_action_values(p, catalog)                 # 범위 · 명령 위치 결함은 교정 대상이 아니다(사람 검토)
    manual_extraction.check_action_values(p, None)                    # 카탈로그 없이 시작한 옛 실행


def test_executable_purchase_sop_without_comparison_policy_is_not_ready(catalog):
    """2026-10-25 수업 한 바퀴: 4회차에 다시 적재한 PR-07 제안에 총비용 비교 정책이 없었고 적재 전 검사는 말이 없었다 → 뒤의 C 판단이 보류."""
    catalog['actions'].append(dict(id='action:purchase-request', code='PR_CREATE', kind='transaction', min=None, max=None))
    catalog['systems'] = [dict(id='sys:erp')]
    catalog['parts'] = [dict(id='part:seal', suppliers=[dict(supplier='sup:a', name='B-OEM (순정)')])]
    p = dict(sections=[], procedures=[dict(id='SOP-PUR-11', name='순정 발주', steps=[dict(text='순정 공급사에 발주한다')])],
             links={'SOP-PUR-11': dict(scope='purchase', kind='work_order', executable=True, parts=['part:seal'], approver='role:maint-mgr',
                                       actions=[dict(action='action:purchase-request', value=None)], supplier_policy='oem')})
    row = manual_preflight.validate(p, catalog)['execution'][0]
    assert row['ready'] is False and 'PURCHASE_COMPARISON_POLICY_REQUIRED' in {i['code'] for i in row['issues']}


def test_extraction_submit_returns_undeclared_rule_input_and_blank_failure_mode_for_correction(catalog):
    """2026-10-25 수업 한 바퀴(final3): 같은 HM-8 세 번 추출의 검사 결과가 갈렸다 — 결정표가 선언하지 않은 입력을 쓴 규칙 1회,
    relation · addresses 는 적고 failureMode 를 비운 SOP-FAN-12 1회. 둘 다 원문 · 카탈로그로 고칠 수 있어 제출 때 교정 사유로 준다."""
    from procsvc import manual_extraction
    catalog['actions'].append(dict(id='action:order', code='WO_CREATE', kind='transaction', min=None, max=None))
    p = proposal()
    p['links']['SOP-PM-12']['actions'] = [dict(action='action:order', value='SOP-PM-12')]
    manual_extraction.check_action_values(p, catalog)
    p['links']['SOP-PM-12'].update(failureMode=None, relation='REMEDIED_BY')
    with pytest.raises(ValueError, match='failureMode 가 비었습니다'):
        manual_extraction.check_action_values(p, catalog)
    p['links']['SOP-PM-12'].update(failureMode='fm:pump')
    p['sections'] = [dict(ref='S', title='절')]
    catalog['decision_tables'].append(dict(id='dt:action-candidates', decision='dec:action-candidates', inputs=[dict(id='in:pattern', variable='pattern')]))
    p['knowledge'] = dict(rules=[dict(id='rule:x', section='S', anchor=dict(quote='q'), table='dt:action-candidates', effect='SELECT',
                                      tests=[dict(input='in:undeclared', operator='==', value=1)], outputs=['SOP-PM-12'])])
    with pytest.raises(ValueError, match='선언하지 않았습니다'):
        manual_extraction.check_action_values(p, catalog)
