"""Exact reuse, non-execution, source provenance and atomic independent Neo4j undo."""
import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest

from procsvc import manual_graph as mg, manual_knowledge as mk, manual_preflight as mp, manual_references as mr, manual_review as review
from procsvc.manual_sources import ManualSources

TEXT = '# 점검\nHM-8.1 팬\n진동 VS1 0.9 mm/s 기준이다.\nSOP-FAN-11 팬 점검\n1. 설비를 정지한다.\n2. 벨트를 확인한다.\n'
SID = 'skill:sop-fan-11'
STEPS = [{'order': 1, 'text': '설비를 정지한다.'}, {'order': 2, 'text': '벨트를 확인한다.'}]
URI = os.environ.get('HYD_MANUAL_NEO4J_URI')


def source_body(archive, text=TEXT, document_id=None, previous=None):
    source = archive.save('hyd', 'manual.md', text.encode(), document_id=document_id)
    body = review.proposal(source)
    body.update(by='사용자위임 Codex자동검토', reviewed=True, previous_batch=previous,
                links={p['id']: {'kind': 'reference', 'executable': False} for p in body['procedures']})
    return source, body


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'manual.sqlite')


def target(**overrides):
    return dict(id=SID, sopId='SOP-FAN-11', owner=None, contract_sha256='a' * 64, steps=copy.deepcopy(STEPS), **overrides)


def bound_procedure(body, pin='a' * 64):
    p = body['procedures'][0]
    p.update(existing_skill_id=SID, reference_contract_sha256=pin)
    return p


def test_reference_without_fm_or_role_has_source_steps_and_no_execution_links(archive):
    source, body = source_body(archive)
    plan = review.validate(archive, 'hyd', body)
    p = plan['procedures'][0]
    assert p['kind'] == 'reference' and p['executable'] is False
    assert p['failureMode'] is p['relation'] is p['approver'] is None
    desired = mg.desired(plan)
    assert {e['type'] for e in desired['edges']} == {'PART_OF', 'HAS_STEP', 'REFERS_TO'}
    assert len([n for n in desired['nodes'] if n['labels'] == ['Step']]) == 2
    assert all(n['props']['source_id'] == source['source_id'] for n in desired['nodes'])


def test_exact_existing_skill_preserves_source_without_owning_skill_or_active_steps(archive):
    _, body = source_body(archive)
    bound_procedure(body)
    plan = review.validate(archive, 'hyd', body)
    desired = mg.desired(plan)
    assert not [n for n in desired['nodes'] if n['labels'] == ['Skill']]
    assert not [e for e in desired['edges'] if e['type'] == 'HAS_STEP']
    assert len([e for e in desired['edges'] if e['type'] == 'DOCUMENTS' and e['to_id'] == SID]) == 2
    assert SID not in {n['props']['id'] for n in desired['nodes']}
    assert mr.check_binding(plan['procedures'][0], target())['source_steps_sha256'] == mr.digest(STEPS)


@pytest.mark.parametrize('change', [{'executable': True}, {'executable': None}, {'approver': 'role:maint-mgr'},
    {'failureMode': 'fm:bearing'}, {'relation': 'REMEDIED_BY'}, {'actions': [{'action': 'action:work-order', 'value': 'SOP-FAN-11'}]},
    {'parts': ['part:fan-bearing']}, {'scope': 'purchase'}, {'affects': [{'target': 'sv:load', 'sign': 1}]}])
def test_explicit_source_only_rejects_execution_or_approval_fields(archive, change):
    _, body = source_body(archive)
    body['links']['SOP-FAN-11'].update(change)
    with pytest.raises(ValueError):
        review.validate(archive, 'hyd', body)


def test_existing_reuse_requires_explicit_reference_and_pinned_contract(archive):
    _, body = source_body(archive)
    body['procedures'][0]['existing_skill_id'] = SID
    with pytest.raises(ValueError, match='reference_contract_sha256'):
        review.validate(archive, 'hyd', body)
    body['links']['SOP-FAN-11'] = {'failureMode': 'fm:bearing'}
    with pytest.raises(ValueError, match='reference'):
        review.validate(archive, 'hyd', body)


@pytest.mark.parametrize('mutation', ['different_sop', 'different_text', 'missing_step', 'extra_step', 'changed_contract'])
def test_reuse_rejects_alias_partial_or_changed_target(archive, mutation):
    _, body = source_body(archive)
    bound_procedure(body)
    p = review.validate(archive, 'hyd', body)['procedures'][0]
    t = target()
    if mutation == 'different_sop': t['sopId'] = 'SOP-COOL-01'
    elif mutation == 'different_text': t['steps'][0]['text'] = '원격으로 정지한다.'
    elif mutation == 'missing_step': t['steps'].pop()
    elif mutation == 'extra_step': t['steps'].append({'order': 3, 'text': '추가 단계'})
    else: t['contract_sha256'] = 'b' * 64
    with pytest.raises(ValueError):
        mr.check_binding(p, t)


def test_reference_text_cannot_be_fabricated_under_real_anchor(archive):
    _, body = source_body(archive)
    body['procedures'][0]['steps'][0]['text'] = '원문에 없는 PLC 명령을 보낸다.'
    with pytest.raises(ValueError, match='원문 인용'):
        review.validate(archive, 'hyd', body)


def test_unknown_source_approver_is_not_defaulted_to_maintenance(archive):
    _, body = source_body(archive)
    body['links']['SOP-FAN-11'] = {'failureMode': 'fm:bearing-degradation', 'kind': 'work_order'}
    p = review.validate(archive, 'hyd', body)['procedures'][0]
    assert p['approver'] is None
    assert not [e for e in mg.desired(review.validate(archive, 'hyd', body))['edges'] if e['type'] == 'APPROVED_BY']


def test_nonreference_fault_keeps_required_fm(archive):
    _, body = source_body(archive)
    body['links']['SOP-FAN-11'] = {'kind': 'work_order'}
    with pytest.raises(ValueError, match='failureMode'):
        review.validate(archive, 'hyd', body)


def test_existing_owner_step_and_section_drift_are_real_hash_inputs():
    class Result:
        def __init__(self, rows): self.rows = rows
        def data(self): return self.rows
    class TX:
        def __init__(self, row): self.row = row
        def run(self, *_args, **_kwargs): return Result([self.row])
    row = dict(skill={'id': SID, 'sopId': 'SOP-FAN-11'}, outgoing=[{'type': 'APPROVED_BY', 'node': {'id': 'role:maint-mgr'}}], incoming=[],
               steps=[{'step': {'order': 1, 'text': '설비를 정지한다.'}, 'manuals': [{'section': {'excerpt': 'VS1 1.2'}}]}])
    baseline = mr.contracts(TX(row))[SID]['contract_sha256']
    changed = copy.deepcopy(row)
    changed['steps'][0]['manuals'][0]['section']['excerpt'] = 'VS1 0.9'
    assert mr.contracts(TX(changed))[SID]['contract_sha256'] != baseline
    changed = copy.deepcopy(row)
    changed['outgoing'][0]['node']['id'] = 'role:operator'
    assert mr.contracts(TX(changed))[SID]['contract_sha256'] != baseline


def test_schema_reference_exception_is_explicit_and_forbids_execution_edges(archive):
    spec = importlib.util.spec_from_file_location('reference_ontology_v2', Path(__file__).resolve().parents[1] / 'scripts/ontology_v2.py')
    ontology = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ontology)
    _, body = source_body(archive)
    desired = mg.desired(review.validate(archive, 'hyd', body))
    nodes = [{'labels': n['labels'], 'props': n['props']} for n in desired['nodes']]
    edges = [{'type': e['type'], 'a': e['from_id'], 'b': e['to_id'], 'la': e['from_labels'], 'lb': e['to_labels'], 'props': e['props']} for e in desired['edges']]
    schema = ontology.load_schema()
    assert ontology.validate(nodes, edges, schema) == []
    skill = next(n for n in nodes if n['labels'] == ['Skill'])
    skill['props']['executable'] = True
    assert any('executable=false' in error for error in ontology.validate(nodes, edges, schema))
    skill['props']['executable'] = False
    edges.append(dict(type='HAS_SKILL', a='sys:cmms', b=skill['props']['id'], la=['System'], lb=['Skill'], props={}))
    assert any('참고 Skill에는 실행' in error for error in ontology.validate(nodes, edges, schema))
    edges.pop()
    skill['props']['kind'] = 'work_order'
    assert any('필수 관계 위반' in error for error in ontology.validate(nodes, edges, schema))


@pytest.fixture
def graph():
    if not URI:
        pytest.skip('독립 빈 Neo4j는 root가 순차 제공한다')
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(URI, auth=('neo4j', os.environ['HYD_MANUAL_NEO4J_PASSWORD']))
    with driver.session() as session:
        count = session.run('MATCH (n) RETURN count(n) AS n').single()['n']
        if count:
            driver.close()
            pytest.fail('버릴 빈 Neo4j가 아니면 이 시험을 실행하지 않습니다')
        session.run("CREATE (k:Skill {id:$id,sopId:'SOP-FAN-11',name:'팬 점검',kind:'work_order',description:'기존 실행 계약'}), "
                    "(r:Role {id:'role:maint-mgr',name:'기존 승인'}),(sys:System {id:'sys:cmms',name:'CMMS'}),"
                    "(fm:FailureMode {id:'fm:bearing-degradation',name:'베어링'}),"
                    "(a:Action {id:'action:work-order',name:'작업지시',code:'WO_CREATE',kind:'transaction'}),"
                    "(ms:ManualSection {id:'HM-8.1',ref:'HM-8.1',title:'기존 절',excerpt:'VS1 1.2 mm/s 기준'}),"
                    "(k)-[:APPROVED_BY]->(r),(sys)-[:HAS_SKILL]->(k),(fm)-[:REMEDIED_BY]->(k),"
                    "(k)-[:CONSISTS_OF {seq:1,value:'SOP-FAN-11'}]->(a) "
                    "WITH k,ms UNWIND $steps AS s CREATE (st:Step {id:'seed-step:'+toString(s.order),order:s.order,text:s.text}),"
                    "(k)-[:HAS_STEP]->(st),(st)-[:REFERS_TO]->(ms)", id=SID, steps=STEPS).consume()
    try:
        with driver.session() as session:
            yield session
    finally:
        with driver.session() as session:
            session.run('MATCH (n) DETACH DELETE n').consume()
        driver.close()


def contract(session, sid=SID):
    return session.execute_read(lambda tx: mr.contracts(tx, [sid]))[sid]


def pinned_body(session, archive, text=TEXT, document_id=None, previous=None):
    source, body = source_body(archive, text, document_id, previous)
    bound_procedure(body, contract(session)['contract_sha256'])
    return source, body


def commit(session, archive, body):
    plan = review.validate(archive, 'hyd', body)
    mk.check_graph(session, plan, mg.skill_id)
    return mg.commit(session, plan)


def test_neo4j_exact_reuse_two_sources_revision_rollback_and_history_leave_seed_unchanged(graph, archive):
    before = contract(graph)
    source, body = pinned_body(graph, archive)
    first = commit(graph, archive, body)
    graph.run("CREATE (:DecisionCase {id:'case:test'})-[:CHOSE]->(:Skill {id:'history-only',sopId:'SOP-HISTORY-01'})").consume()
    graph.run("MATCH (c:DecisionCase {id:'case:test'}),(k:Skill {id:$id}) CREATE (c)-[:CHOSE]->(k)", id=SID).consume()
    other_source, other = pinned_body(graph, archive)
    second = commit(graph, archive, other)
    assert contract(graph) == before
    assert graph.run('MATCH (:Skill {id:$id})-[:HAS_STEP]->(s) RETURN count(s) AS n', id=SID).single()['n'] == 2
    assert graph.run('MATCH (:Step)-[:DOCUMENTS]->(:Skill {id:$id}) RETURN count(*) AS n', id=SID).single()['n'] == 4
    revised_source, revised = pinned_body(graph, archive, TEXT.replace('0.9', '0.8'), source['document_id'], first['batch'])
    revision = commit(graph, archive, revised)
    assert mg.rollback(graph, 'hyd', revision['batch'], '사용자위임 Codex자동검토')['status'] == 'ROLLED_BACK'
    assert mg.rollback(graph, 'hyd', second['batch'], '사용자위임 Codex자동검토')['status'] == 'ROLLED_BACK'
    assert mg.rollback(graph, 'hyd', first['batch'], '사용자위임 Codex자동검토')['status'] == 'ROLLED_BACK'
    assert contract(graph) == before
    assert graph.run('MATCH (:DecisionCase {id:"case:test"})-[:CHOSE]->(:Skill {id:$id}) RETURN count(*) AS n', id=SID).single()['n'] == 1


@pytest.mark.parametrize('mutation', ['role', 'action', 'active_section'])
def test_neo4j_changed_contract_after_preview_is_atomic_conflict(graph, archive, mutation):
    _, body = pinned_body(graph, archive)
    if mutation == 'role':
        graph.run("MATCH (r:Role {id:'role:maint-mgr'}) SET r.name='기존 승인 개정'").consume()
    elif mutation == 'action':
        graph.run('MATCH (:Skill {id:$id})-[r:CONSISTS_OF]->(:Action) SET r.value="다른 실행 값"', id=SID).consume()
    else:
        graph.run("MATCH (ms:ManualSection {id:'HM-8.1'}) SET ms.excerpt='수정된 실행 원문'").consume()
    plan = review.validate(archive, 'hyd', body)
    with pytest.raises(ValueError, match='실행 계약'):
        mk.check_graph(graph, plan, mg.skill_id)
    assert graph.run('MATCH (n:ManualIngestionBatch) RETURN count(n) AS n').single()['n'] == 0


def test_neo4j_no_pin_drift_between_check_and_commit(graph, archive):
    _, body = pinned_body(graph, archive)
    plan = review.validate(archive, 'hyd', body)
    mk.check_graph(graph, plan, mg.skill_id)
    graph.run("MATCH (s:Step {id:'seed-step:1'}) SET s.text='다른 단계'").consume()
    with pytest.raises(mg.Conflict, match='단계'):
        mg.commit(graph, plan)
    assert graph.run('MATCH (n:ManualIngestionBatch) RETURN count(n) AS n').single()['n'] == 0


def test_neo4j_rollback_rejects_mutated_source_without_touching_target(graph, archive):
    before = contract(graph)
    _, body = pinned_body(graph, archive)
    receipt = commit(graph, archive, body)
    graph.run('MATCH (s:Step) WHERE s._manual_document=$doc SET s.text="위조"', doc=review.document_key('hyd', body['document_id'])).consume()
    with pytest.raises(mg.Conflict, match='속성이 바뀐'):
        mg.rollback(graph, 'hyd', receipt['batch'], '사용자위임 Codex자동검토')
    assert contract(graph) == before


def test_neo4j_owned_target_keeps_verified_provenance_but_refuses_drop_or_revision(graph, archive):
    # Fresh document-owned Skill, then another document references it.
    own_text = TEXT.replace('SOP-FAN-11', 'SOP-FAN-92')
    own_source, own_body = source_body(archive, own_text)
    own_body['links']['SOP-FAN-92'] = {'failureMode': 'fm:bearing-degradation', 'kind': 'work_order', 'approver': 'role:maint-mgr'}
    owned = commit(graph, archive, own_body)
    owned_sid = 'skill:sop-fan-92'
    source, body = source_body(archive, own_text)
    body['procedures'][0].update(existing_skill_id=owned_sid, reference_contract_sha256=contract(graph, owned_sid)['contract_sha256'])
    referenced = commit(graph, archive, body)
    def read_snapshot(tx):
        row = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.snapshot AS snapshot', id=review.document_key('hyd', own_source['document_id'])).single()
        expected = json.loads(row['snapshot'])
        current, history = mg._snapshot(tx, review.document_key('hyd', own_source['document_id']), mg.owned_keys(expected))
        assert current == mg._sort(expected) and history == []
    graph.execute_write(read_snapshot)
    with pytest.raises(mg.Conflict, match='원문 참조'):
        mg.rollback(graph, 'hyd', owned['batch'], '검토자')
    _, revision_body = source_body(archive, own_text.replace('0.9', '0.8'), own_source['document_id'], owned['batch'])
    revision_body['links']['SOP-FAN-92'] = dict(own_body['links']['SOP-FAN-92'])
    with pytest.raises(mg.Conflict, match='실행 계약을 참조'):
        commit(graph, archive, revision_body)
    mg.rollback(graph, 'hyd', referenced['batch'], '검토자')
    assert mg.rollback(graph, 'hyd', owned['batch'], '검토자')['status'] == 'ROLLED_BACK'


def test_neo4j_forged_documents_tag_is_foreign_drift(graph, archive):
    _, body = source_body(archive, TEXT.replace('SOP-FAN-11', 'SOP-FAN-92'))
    body['links']['SOP-FAN-92'] = {'failureMode': 'fm:bearing-degradation', 'kind': 'work_order'}
    receipt = commit(graph, archive, body)
    graph.run("MATCH (k:Skill {id:'skill:sop-fan-92'}) CREATE (:Step {id:'forged',order:1,text:'위조'})-[:DOCUMENTS {_manual_document:'fake'}]->(k)").consume()
    with pytest.raises(mg.Conflict, match='기록에 없는 관계'):
        mg.rollback(graph, 'hyd', receipt['batch'], '검토자')


def test_neo4j_catalog_exposes_pin_without_mutating_source_and_preflight_accepts_exact_reference(graph, archive):
    _, body = pinned_body(graph, archive)
    body['conflicts'] = [{'sop': 'SOP-FAN-11', 'skill': SID, 'owner': 'admin'}]
    before = copy.deepcopy(body)
    catalog = mk.catalog(graph)
    target = next(s for s in catalog['skills'] if s['id'] == SID)['reference_contract']
    assert target['contract_sha256'] == contract(graph)['contract_sha256']
    checked = mp.validate(body, catalog)
    assert checked['technical_ready'] is True and body == before


@pytest.mark.parametrize('mutation', ['duplicate_documents', 'source_section', 'source_journal'])
def test_neo4j_forged_or_changed_incoming_provenance_is_never_ignored(graph, archive, mutation):
    own_text = TEXT.replace('SOP-FAN-11', 'SOP-FAN-92')
    own_source, own_body = source_body(archive, own_text)
    own_body['links']['SOP-FAN-92'] = {'failureMode': 'fm:bearing-degradation', 'kind': 'work_order'}
    owned = commit(graph, archive, own_body)
    _, body = source_body(archive, own_text)
    body['procedures'][0].update(existing_skill_id='skill:sop-fan-92',
                                 reference_contract_sha256=contract(graph, 'skill:sop-fan-92')['contract_sha256'])
    referenced = commit(graph, archive, body)
    document = review.document_key('hyd', body['document_id'])
    if mutation == 'duplicate_documents':
        graph.run('MATCH (st:Step)-[r:DOCUMENTS]->(k:Skill) WHERE st._manual_document=$doc '
                  'WITH st,k,properties(r) AS p LIMIT 1 CREATE (st)-[duplicate:DOCUMENTS]->(k) SET duplicate=p', doc=document).consume()
    elif mutation == 'source_section':
        graph.run('MATCH (s:ManualSection) WHERE s._manual_document=$doc SET s.excerpt="위조 원문"', doc=document).consume()
    else:
        graph.run('MATCH (d:ManualIngestionDocument {id:$doc}) SET d.snapshot="{}"', doc=document).consume()
    with pytest.raises(mg.Conflict, match='기록에 없는 관계'):
        mg.rollback(graph, 'hyd', owned['batch'], '검토자')
    assert graph.run('MATCH (b:ManualIngestionBatch {id:$id}) RETURN b.status AS status', id=owned['batch']).single()['status'] == 'ACTIVE'


def test_neo4j_rollback_does_not_restore_an_old_pin_after_explicit_rebinding(graph, archive):
    source, body = pinned_body(graph, archive)
    first = commit(graph, archive, body)
    graph.run("MATCH (r:Role {id:'role:maint-mgr'}) SET r.name='정식으로 개정된 대상 승인'").consume()
    _, revised_body = pinned_body(graph, archive, TEXT.replace('0.9', '0.8'), source['document_id'], first['batch'])
    second = commit(graph, archive, revised_body)
    with pytest.raises(mg.Conflict, match='실행 계약'):
        mg.rollback(graph, 'hyd', second['batch'], '검토자')
    assert mg.head(graph, 'hyd', source['document_id']) == second['batch']
