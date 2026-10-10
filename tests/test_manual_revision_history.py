"""F-2 (live-final 2-4, DECISIONS 35): a manual revision keeps the execution history that points at the document's nodes.

The case projection records "a person chose this SOP" as (DecisionCase)-[:CHOSE]->(Skill) on a document-owned Skill
(procsvc/case_projection.py). A revision must not erase that audit record, must not be blocked by it while the Skill
survives, must refuse to drop a node it points at, and must still refuse a hand-edited document graph or an unknown
foreign relationship.

The graph tests run real Cypher against a throwaway Neo4j named by HYD_MANUAL_NEO4J_URI (user neo4j, password in
HYD_MANUAL_NEO4J_PASSWORD). The database must be empty when a test starts — never point this at the class stack.
"""
import json
import os

import pytest

from procsvc import case_projection, manual_graph, manual_review
from procsvc.kgadmin import skill_id
from procsvc.manual_sources import ManualSources

URI = os.environ.get('HYD_MANUAL_NEO4J_URI')
TEXT = ('# 정비\nHM-8.1 팬 벨트\n긴 원문 설명\n'
        'SOP-REF-91 벨트 점검\n1. 정지한다.\n2. 벨트를 확인한다.\n'
        'SOP-REF-92 베어링 점검\n1. 소리를 듣는다.\n')
REVISED = ('# 정비\nHM-8.1 팬 벨트\n개정된 원문 설명\n'
           'SOP-REF-91 벨트 점검\n1. 전원을 내린다.\n2. 벨트 장력을 잰다.\n3. 기록한다.\n'
           'SOP-REF-92 베어링 점검\n1. 소리와 온도를 함께 본다.\n')
WITHOUT_92 = ('# 정비\nHM-8.1 팬 벨트\n개정된 원문 설명\n'
              'SOP-REF-91 벨트 점검\n1. 전원을 내린다.\n2. 벨트 장력을 잰다.\n')
SKILL_91, SKILL_92 = skill_id('SOP-REF-91'), skill_id('SOP-REF-92')


# ── pure checks (no database) ────────────────────────────────────────────────────────────────────────────────────────

def test_history_allowlist_is_what_the_case_projection_actually_writes():
    """The allowlist names the producer's edges; if the projection stops writing one (or the document starts owning
    that relation itself) this fails instead of silently keeping a stale exemption."""
    assert 'MERGE (x:DecisionCase' in case_projection.DECISION_CASE_Q and '(s:Skill {id:$skill})' in case_projection.DECISION_CASE_Q
    assert 'MERGE (x)-[:CHOSE]->(s)' in case_projection.DECISION_CASE_Q
    assert 'MERGE (i:Incident' in case_projection.INCIDENT_Q and '(c:Cause {id:$cause})' in case_projection.INCIDENT_Q
    assert 'MERGE (i)-[:DIAGNOSED_AS]->(c)' in case_projection.INCIDENT_Q
    assert set(manual_graph.HISTORY_RELATIONS) == {('DecisionCase', 'CHOSE', 'Skill'), ('Incident', 'DIAGNOSED_AS', 'Cause')}
    assert not {kind for _, kind, _ in manual_graph.HISTORY_RELATIONS} & set(manual_graph.RELATIONS)
    assert {own for _, _, own in manual_graph.HISTORY_RELATIONS} <= set(manual_graph.LABELS)


@pytest.mark.parametrize('edge,from_owned,to_owned,history', [
    (('DecisionCase', 'CHOSE', 'Skill'), False, True, True),
    (('Incident', 'DIAGNOSED_AS', 'Cause'), False, True, True),
    (('DecisionCase', 'CHOSE', 'Skill'), True, True, False),      # both ends the document's: its own graph, not history
    (('Skill', 'CHOSE', 'DecisionCase'), True, False, False),     # wrong direction
    (('DecisionCase', 'CITES', 'Skill'), False, True, False),     # unknown relation
    (('Execution', 'CHOSE', 'Skill'), False, True, False),        # unknown outside label
    (('DecisionCase', 'CHOSE', 'Step'), False, True, False),      # history not declared for this owned label
])
def test_only_declared_inbound_history_is_split_off(edge, from_owned, to_owned, history):
    e = dict(from_labels=[edge[0]], type=edge[1], to_labels=[edge[2]])
    assert manual_graph._is_history(e, from_owned, to_owned) is history


# ── real graph ───────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def graph():
    if not URI:
        pytest.skip('HYD_MANUAL_NEO4J_URI 가 없으면 실제 Neo4j 개정 시험은 건너뛴다 (버릴 빈 Neo4j)')
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(URI, auth=('neo4j', os.environ['HYD_MANUAL_NEO4J_PASSWORD']))
    with driver.session() as s:
        left = s.run('MATCH (n) RETURN count(n) AS n').single()['n']
        if left:
            driver.close()
            pytest.fail(f'{URI} 에 노드 {left}개가 있습니다 — 버릴 빈 Neo4j 가 아니면 이 시험을 돌리지 않습니다')
        s.run("CREATE (:FailureMode {id:'fm:bearing-degradation'}), (:Role {id:'role:maint-mgr'}), "
              "(:System {id:'sys:cmms'}), (:System {id:'sys:scada'})").consume()
    try:
        with driver.session() as s:
            yield s
    finally:
        with driver.session() as s:
            s.run('MATCH (n) DETACH DELETE n').consume()
        driver.close()


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'manuals.sqlite')


def commit(session, archive, text, document_id=None, previous=None):
    source = archive.save('hyd', 'manual.md', text.encode(), document_id=document_id)
    body = manual_review.proposal(source)
    body.update(by='검토자', reviewed=True, previous_batch=previous,
                links={p['id']: {'failureMode': 'fm:bearing-degradation'} for p in body['procedures']})
    return source, manual_graph.commit(session, manual_review.validate(archive, 'hyd', body))


def choose(session, skill, case):
    """The real producer: the case projection's DecisionCase write."""
    session.run(case_projection.DECISION_CASE_Q, key='DecisionCase:' + case, revision=1, payload_hash='h', id=case,
                at='2026-10-09T00:00:00Z', reason='시험', followed=True, status='APPROVED', incident=None,
                skill=skill, role='role:maint-mgr').consume()


def chosen(session, skill):
    return session.run('MATCH (c:DecisionCase)-[:CHOSE]->(k:Skill {id:$id}) RETURN elementId(k) AS k, c.id AS c ORDER BY c',
                       id=skill).data()


def journal(session, source):
    row = session.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.head AS head, d.snapshot AS snapshot',
                      id=manual_review.document_key('hyd', source['document_id'])).single()
    return row['head'], row['snapshot']


def test_revision_keeps_decision_history_on_a_surviving_skill_and_rollback_keeps_it_too(graph, archive):
    first, v1 = commit(graph, archive, TEXT)
    for case in ('case:DEC-1', 'case:DEC-2', 'case:DEC-3'):
        choose(graph, SKILL_91, case)
    before = chosen(graph, SKILL_91)
    assert len(before) == 3

    _, v2 = commit(graph, archive, REVISED, document_id=first['document_id'], previous=v1['batch'])

    after = chosen(graph, SKILL_91)
    assert after == before                                   # same three records on the very same Skill node
    assert v2['history_kept'] == [dict(node='Skill ' + SKILL_91, type='CHOSE', count=3)]
    steps = graph.run('MATCH (:Skill {id:$id})-[:HAS_STEP]->(s:Step) RETURN s.text AS t ORDER BY s.order', id=SKILL_91).data()
    assert [s['t'] for s in steps] == ['전원을 내린다.', '벨트 장력을 잰다.', '기록한다.']
    assert graph.run('MATCH (s:Step) RETURN count(s) AS n').single()['n'] == 4          # 3 + 1, old steps not left behind
    assert journal(graph, first)[0] == v2['batch']

    undone = manual_graph.rollback(graph, 'hyd', v2['batch'], '검토자')
    assert undone['history_kept'] == [dict(node='Skill ' + SKILL_91, type='CHOSE', count=3)]
    assert chosen(graph, SKILL_91) == before
    steps = graph.run('MATCH (:Skill {id:$id})-[:HAS_STEP]->(s:Step) RETURN s.text AS t ORDER BY s.order', id=SKILL_91).data()
    assert [s['t'] for s in steps] == ['정지한다.', '벨트를 확인한다.']
    head, snapshot = journal(graph, first)
    assert head == v1['batch']
    # the document graph equals the restored journal again (history split off), so the next revision is not blocked
    current, history = graph.execute_write(lambda tx: manual_graph._snapshot(
        tx, manual_review.document_key('hyd', first['document_id']), manual_graph.owned_keys(json.loads(snapshot))))
    assert current == manual_graph._sort(json.loads(snapshot)) and len(history) == 3


def test_revision_that_drops_a_skill_with_decision_history_is_refused_and_changes_nothing(graph, archive):
    first, v1 = commit(graph, archive, TEXT)
    choose(graph, SKILL_92, 'case:DEC-9')
    with pytest.raises(manual_graph.Conflict) as refused:
        commit(graph, archive, WITHOUT_92, document_id=first['document_id'], previous=v1['batch'])
    assert f'Skill {SKILL_92} ← CHOSE 1건' in str(refused.value)
    assert journal(graph, first)[0] == v1['batch']                                   # whole transaction rolled back
    assert [r['c'] for r in chosen(graph, SKILL_92)] == ['case:DEC-9']
    assert graph.run('MATCH (s:Step) RETURN count(s) AS n').single()['n'] == 3       # v1 graph untouched
    # undoing the first batch would delete that Skill too: same refusal
    with pytest.raises(manual_graph.Conflict, match=f'Skill {SKILL_92} ← CHOSE 1건'):
        manual_graph.rollback(graph, 'hyd', v1['batch'], '검토자')
    assert journal(graph, first)[0] == v1['batch']


def test_hand_edited_document_graph_is_still_refused_naming_the_change(graph, archive):
    first, v1 = commit(graph, archive, TEXT)
    choose(graph, SKILL_91, 'case:DEC-1')                   # allowed history alongside must not hide the hand edit
    graph.run("MATCH (k:Skill {id:$id}) SET k.name='손으로 고친 이름'", id=SKILL_91).consume()
    with pytest.raises(manual_graph.Conflict) as refused:
        commit(graph, archive, REVISED, document_id=first['document_id'], previous=v1['batch'])
    assert f'속성이 바뀐 노드 1건: Skill {SKILL_91}' in str(refused.value)
    assert journal(graph, first)[0] == v1['batch']
    with pytest.raises(manual_graph.Conflict, match='속성이 바뀐 노드'):
        manual_graph.rollback(graph, 'hyd', v1['batch'], '검토자')


@pytest.mark.parametrize('outside,kind', [('DecisionCase', 'CITES'), ('Execution', 'CHOSE')])
def test_unknown_foreign_relation_on_a_document_node_is_refused(graph, archive, outside, kind):
    first, v1 = commit(graph, archive, TEXT)
    graph.run(f"MATCH (k:Skill {{id:$id}}) CREATE (:{outside} {{id:'x:1'}})-[:{kind}]->(k)", id=SKILL_91).consume()
    with pytest.raises(manual_graph.Conflict) as refused:
        commit(graph, archive, REVISED, document_id=first['document_id'], previous=v1['batch'])
    assert f'({outside} x:1)-[:{kind}]->(Skill {SKILL_91})' in str(refused.value)
    assert '이력으로 허용되지 않은 바깥 관계) 1건' in str(refused.value)
    assert journal(graph, first)[0] == v1['batch']
