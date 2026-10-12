"""Source-backed purchase scope is additive; no seed or live graph writes."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from hydcommon.skill_scope import purchase_graph_issues
from procsvc import kgadmin, manual_graph, manual_knowledge, manual_preflight, manual_review, skill_graph
from procsvc.manual_sources import ManualSources
from agentsvc import cards


TEXT = '# 구매 지침\nPR-7.6 발주 절차\nSOP-PUR-11 순정 공급사 발주\n1. ERP 발주서를 작성한다.\n2. 입고 수량과 로트를 확인한다.\n'


def link(executable=True):
    return dict(scope='purchase', executable=executable, parts=['part:kit'], kind='work_order',
                failureMode=None, relation=None, approver='role:purchasing' if executable else None,
                actions=[dict(action='action:purchase-request', value='sup:b')] if executable else [])


@pytest.fixture
def source_proposal(tmp_path):
    archive = ManualSources(tmp_path / 'manual.sqlite')
    source = archive.save('hyd', 'purchasing.md', TEXT.encode())
    body = manual_review.proposal(source)
    # A temporary unit fixture's reviewer, not an actual review record.
    body.update(by='test:source-contract', reviewed=True, links={'SOP-PUR-11': link()})
    return archive, source, body


@pytest.fixture
def catalog():
    c = {key: [] for key in manual_knowledge.CATALOG_Q}
    c.update(parts=[dict(id='part:kit', name='씰 키트', partNo='P-KIT', suppliers=[dict(supplier='sup:b')])],
             systems=[dict(id='sys:erp')], roles=[dict(id='role:purchasing')], suppliers=[dict(id='sup:b')],
             actions=[dict(id='action:purchase-request', code='PR_CREATE', kind='transaction', min=None, max=None)],
             decision_tables=[dict(id='dt:action-candidates', decision='dec:action-candidates', inputs=[dict(id='in:pattern',variable='pattern')])])
    return c


def checked_plan(archive, body, catalog):
    plan = manual_review.validate(archive, 'hyd', body)
    checked, issues = manual_knowledge.graph_semantics(plan, catalog)
    assert issues == [], issues
    return checked


def graph_records(snapshot):
    return snapshot['nodes'], [dict(a=r['from_id'], b=r['to_id'], la=r['from_labels'], lb=r['to_labels'],
                                    type=r['type'], props=r['props']) for r in snapshot['edges']]


def external_nodes_and_edges(snapshot):
    for label, props in [('Part',dict(id='part:kit')), ('Supplier',dict(id='sup:b')),
                         ('Action',dict(id='action:purchase-request',code='PR_CREATE',kind='transaction')),
                         ('System',dict(id='sys:erp')), ('Role',dict(id='role:purchasing'))]:
        snapshot['nodes'].append(dict(labels=[label],props=props))
    snapshot['edges'].append(dict(from_id='part:kit',to_id='sup:b',from_labels=['Part'],to_labels=['Supplier'],type='SUPPLIED_BY',props={}))
    return snapshot


@pytest.mark.parametrize('executable', [True, False])
def test_purchase_document_plan_graph_and_preflight_share_one_model(source_proposal, catalog, executable):
    archive, _, body = source_proposal
    body['links']['SOP-PUR-11'] = link(executable)
    before = deepcopy(body)
    plan = checked_plan(archive, body, catalog)
    p = plan['procedures'][0]
    assert p['failureMode'] is None and p['relation'] is None and p['executable'] is executable
    snapshot = external_nodes_and_edges(manual_graph.desired(plan))
    nodes, relationships = graph_records(snapshot)
    assert purchase_graph_issues(nodes, relationships) == []
    assert not any(r['type'] in kgadmin.FAILURE_RELATIONS for r in relationships)
    assert any(r['a'] == 'sys:erp' and r['type'] == 'HAS_SKILL' for r in relationships)
    assert not any(r['a'] == 'sys:cmms' and r['type'] == 'HAS_SKILL' for r in relationships)
    assert body == before
    validation = manual_preflight.validate(body, catalog)
    assert validation['technical_ready'] is True
    assert validation['execution'][0]['ready'] is executable
    assert validation['executable_ready'] is executable
    assert validation['execution'][0]['evaluation_mode'] == 'structural'
    assert validation['execution'][0]['execution_checked'] is False
    assert '실제 견적·재고' in validation['execution'][0]['source_notice']
    assert '확인하지 않았습니다' in validation['execution'][0]['source_notice']
    assert validation['can_commit'] is False and validation['needs_human_review'] is True


def test_purchase_cannot_be_created_by_general_admin_or_fake_source_id():
    body = dict(link(), name='발주', sopId='SOP-PUR-11', steps=['발주'], source_id='claimed-source')
    with pytest.raises(ValueError, match='매뉴얼 검토 경로'):
        kgadmin.validate_skill(body, create=True)
    with pytest.raises(ValueError, match='failureMode'):
        kgadmin.validate_skill(dict(name='기존 조치', sopId='SOP-X-01', steps=['점검']), create=True)
    with pytest.raises(ValueError, match='매뉴얼 검토/개정'):
        skill_graph.write(None, '', 'skill:x', dict(scope='purchase'), create=True)


@pytest.mark.parametrize('change, phrase', [
    ({'parts':[]}, 'Part'), ({'executable':None}, '실행 후보 여부'), ({'executable':1}, '실행 후보 여부'),
    ({'kind':'control'}, 'work_order'), ({'failureMode':'fm:invented'}, '고장 유형'),
    ({'addresses':['cause:invented']}, '대상 원인'), ({'approver':'role:operator'}, '구매 담당'),
    ({'actions':[]}, 'PR_CREATE'), ({'actions':[dict(action='action:set-load',value=70)]}, 'PR_CREATE'),
    ({'executable':False}, '참고 보관'),
])
def test_source_purchase_shape_does_not_loosen_execution_or_fault_checks(source_proposal, change, phrase):
    archive, _, body = source_proposal
    body['links']['SOP-PUR-11'].update(change)
    with pytest.raises(ValueError, match=phrase):
        manual_review.validate(archive,'hyd',body)


def test_purchase_catalog_requires_actual_part_supplier_system_role_and_action(source_proposal, catalog):
    archive, _, body = source_proposal
    plan = manual_review.validate(archive,'hyd',body)
    c = deepcopy(catalog)
    c['parts'][0]['suppliers'] = []
    c['roles'] = []
    c['systems'] = []
    c['actions'][0]['kind'] = 'command'
    _, issues = manual_knowledge.graph_semantics(plan,c)
    assert {'PURCHASE_SUPPLIER_PART_MISMATCH','PURCHASE_ROLE_NOT_FOUND','PURCHASE_SYSTEM_NOT_FOUND','PURCHASE_ACTION_CONTRACT_INVALID'} <= {i['code'] for i in issues}


def test_purchase_rule_cannot_select_reference_or_omit_business_pattern(source_proposal, catalog):
    archive, _, body = source_proposal
    plan = manual_review.validate(archive,'hyd',body)
    plan['knowledge'] = dict(rules=[dict(id='rule:purchase',table='dt:action-candidates',effect='SELECT',
        tests=[dict(input='in:pattern',operator='==',value='SPARE_BELOW_MIN')],outputs=['SOP-PUR-11'])])
    _, issues = manual_knowledge.graph_semantics(plan,catalog)
    assert issues == []
    plan['procedures'][0].update(executable=False,actions=[],approver=None)
    _, issues = manual_knowledge.graph_semantics(plan,catalog)
    assert 'RULE_OUTPUT_NOT_EXECUTABLE' in {i['code'] for i in issues}
    plan['knowledge']['rules'][0]['tests'][0]['value'] = 'PUMP_LEAKAGE'
    _, issues = manual_knowledge.graph_semantics(plan,catalog)
    assert 'PURCHASE_RULE_PATTERN_REQUIRED' in {i['code'] for i in issues}
    plan['knowledge']['rules'][0]['outputs'] = [kgadmin.skill_id('SOP-PUR-11')]
    _, issues = manual_knowledge.graph_semantics(plan,catalog)
    assert {'PURCHASE_RULE_PATTERN_REQUIRED','RULE_OUTPUT_NOT_EXECUTABLE'} <= {i['code'] for i in issues}


def test_schema_exemption_is_only_explicit_purchase_and_common_graph_validator_is_used(source_proposal,catalog):
    archive, _, body = source_proposal
    snapshot = external_nodes_and_edges(manual_graph.desired(checked_plan(archive,body,catalog)))
    nodes, rels = graph_records(snapshot)
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('purchase_ontology_schema',root/'scripts/ontology_v2.py')
    ov = importlib.util.module_from_spec(spec); spec.loader.exec_module(ov)
    errors = ov.validate(nodes,rels,ov.load_schema())
    assert not any('고장 유형 하나 이상' in e for e in errors)
    skill = next(n for n in nodes if 'Skill' in n['labels'])
    skill['props'].pop('scope'); skill['props'].pop('executable')
    errors = ov.validate(nodes,rels,ov.load_schema())
    assert any('고장 유형 하나 이상' in e for e in errors)
    assert any('Part 업무 범위' in e for e in errors)


def runtime_skill():
    return dict(skillId='skill:purchase',scope='purchase',executable=True,kind='work_order',parts=['part:kit'],supplierParts=['part:kit'],
                performers=['sys:erp'],source_id='source',citation='source citation',approver=dict(id='role:purchasing'),
                purchase_comparison_policy=dict(version=1,loss_per_failure=250,inspection_threshold=.1,inspection_cost=20,anchor=dict(source_id='source',quote='불량 1건 손실은 250만 원. 불량률이 10 %를 넘으면 전수 검사 비용 20만 원.')),
                steps=[dict(source_id='source',citation='step citation',manual=dict(id='section'))],
                actions=[dict(id='action:purchase-request',code='PR_CREATE',kind='transaction',value='sup:b')])


def test_runtime_purchase_requires_explicit_part_and_never_enters_fault_or_reference_scope():
    skill = runtime_skill()
    assert cards.scoped_skills('SPARE_BELOW_MIN',{skill['skillId']:skill},'part:kit') == {skill['skillId']:skill}
    assert cards.scoped_skills('SPARE_BELOW_MIN',{skill['skillId']:skill}) == {}
    assert cards.scoped_skills('PUMP_LEAKAGE',{skill['skillId']:skill}) == {}
    assert cards.scoped_skills('SPARE_BELOW_MIN',{skill['skillId']:skill},'part:other') == {}
    for key,value in [('executable',False),('supplierParts',[]),('performers',['sys:cmms']),('source_id',None),('steps',[])]:
        changed = dict(skill,**{key:value})
        assert cards.scoped_skills('SPARE_BELOW_MIN',{skill['skillId']:changed},'part:kit') == {}


def test_purchase_commit_rechecks_external_supply_inside_transaction_before_batch_write(source_proposal,catalog,monkeypatch):
    archive, _, body = source_proposal
    plan = checked_plan(archive,body,catalog)
    catalog['parts'][0]['suppliers'] = []  # changed after the reviewed plan was checked
    monkeypatch.setattr(manual_graph,'ensure_schema',lambda session: None)
    calls = []

    class Rows:
        def __init__(self, rows): self.rows = rows
        def data(self): return deepcopy(self.rows)
        def single(self): return self.rows[0] if self.rows else None
        def consume(self): return None

    class Tx:
        def run(self, query, **kwargs):
            calls.append(query)
            if query in manual_knowledge.CATALOG_Q.values():
                key = next(k for k,q in manual_knowledge.CATALOG_Q.items() if q == query)
                return Rows(catalog[key])
            if 'IngestionControl' in query or 'ManualIngestionBatch' in query:
                return Rows([])
            raise AssertionError('must fail before graph/batch replacement: '+query)

    class Session:
        def execute_write(self, fn): return fn(Tx())

    with pytest.raises(ValueError,match='SUPPLIED_BY'):
        manual_graph.commit(Session(),plan)
    assert not any('CREATE (b:ManualIngestionBatch' in q or 'MERGE (d:ManualIngestionDocument' in q for q in calls)
