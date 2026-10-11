"""Knowledge map is business knowledge/cases, excluding implementation receipts.

Live tests require an explicitly disposable, empty Neo4j on loopback port 7787.
They run the actual templates through the HTTP route and delete only their own
UUID-tagged nodes. Production graph and schema are never modified.
"""
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from agentsvc import main
from agentsvc.tools import mcp_kg


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'it/neo4j/templates'
LEGACY_INTERNAL = {'ProcessVersion', 'ProcessInstance', 'WorkItem', 'IngestionControl', 'IngestionBatch'}
INTERNAL = {'ExecutionProjection', 'CaseProjection', 'KnowledgeEdit', 'ManualIngestionDocument', 'ManualIngestionBatch'}


def template(name):
    return (TEMPLATES / (name + '.cypher')).read_text(encoding='utf-8')


def excluded(query, variable):
    block = re.search(r'(?:WHERE|AND) NOT \(' + variable + r':(.*?)\)', query, re.S)[1]
    return {block.split()[0], *re.findall(variable + r':([A-Za-z][A-Za-z0-9]*)', block)}


def prior_map_query(name):
    """In-memory regression mutation: omit exactly the five missed filters."""
    query = template(name)
    for variable in ('n', 'a', 'b'):
        for label in INTERNAL:
            query = re.sub(r'\s+OR ' + variable + ':' + label + r'\b', '', query)
    return query


def test_schema_internal_records_are_excluded_at_every_map_endpoint():
    schema = json.loads((ROOT / 'it/neo4j/v2/schema.json').read_text(encoding='utf-8'))
    schema_internal = {c['name'] for c in schema['classes'] if c.get('standard') == '내부 기록'}
    assert schema_internal == INTERNAL  # A newly introduced internal class needs this contract reviewed.
    expected = LEGACY_INTERNAL | schema_internal
    assert excluded(template('t0_graph_nodes'), 'n') == expected
    assert excluded(template('t0_graph_edges'), 'a') == expected
    assert excluded(template('t0_graph_edges'), 'b') == expected
    assert not expected & {'Incident', 'DecisionCase', 'ManualSection', 'KnowledgeSource', 'Meeting'}


@pytest.mark.parametrize('namespace', ['', 's01'])
def test_map_http_contract_returns_graph_without_dropping_business_or_student_records(monkeypatch, namespace):
    nodes = [dict(id='section:one', label='ManualSection', name='원문', props={'id': 'section:one'}),
             dict(id='case:one', label='DecisionCase', name='승인 판단', props={'id': 'case:one'})]
    if namespace:
        nodes.append(dict(id='s01:meeting', label='Meeting', name='회의', props={'ns': 's01'}))
    payload = {'nodes': nodes, 'edges': [{'from': nodes[0]['id'], 'to': nodes[1]['id'], 'type': 'CITES'}]}
    calls = []
    graph = object.__new__(mcp_kg.KnowledgeGraph)
    graph._run = lambda name, **params: calls.append((name, params)) or payload['nodes' if name.endswith('nodes') else 'edges']
    monkeypatch.setattr(main, 'kg', graph)
    response = TestClient(main.app).get('/api/ontology/graph', params={'asset': 'HYD-01', 'ns': namespace})
    assert response.status_code == 200 and response.json() == payload
    assert calls == [('t0_graph_nodes', {'asset': 'HYD-01', 'ns': namespace}),
                     ('t0_graph_edges', {'asset': 'HYD-01', 'ns': namespace})]


@pytest.fixture
def real_graph(monkeypatch):
    uri = os.getenv('HYD_MAP_NEO4J_URI')
    if not uri:
        pytest.skip('HYD_MAP_NEO4J_URI must explicitly identify the disposable test graph')
    parsed = urlparse(uri)
    assert parsed.scheme == 'bolt' and parsed.hostname in ('127.0.0.1', 'localhost') and parsed.port == 7787
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=('neo4j', os.environ['HYD_MAP_NEO4J_PASSWORD']))
    token = uuid4().hex
    with driver.session() as session:
        assert session.run('MATCH (n) RETURN count(n) AS n').single()['n'] == 0, 'Disposable graph must be empty; no wipe performed'
    graph = object.__new__(mcp_kg.KnowledgeGraph)
    graph.driver, graph._cache = driver, {}
    monkeypatch.setattr(mcp_kg, 'TEMPLATES', TEMPLATES)
    monkeypatch.setattr(main, 'kg', graph)
    try:
        with driver.session() as session:
            yield graph, session, token
    finally:
        with driver.session() as session:
            session.run('MATCH (n {_knowledge_map_test:$token}) DETACH DELETE n', token=token).consume()
            assert session.run('MATCH (n {_knowledge_map_test:$token}) RETURN count(n) AS n', token=token).single()['n'] == 0
        driver.close()


def create_node(session, token, label, node_id, **props):
    # Labels below are local test constants, never caller-provided Cypher.
    session.run(f'CREATE (n:{label}) SET n = $props', props={'id': node_id, '_knowledge_map_test': token, **props}).consume()


def create_edge(session, source, target, relation):
    session.run(f'MATCH (a {{id:$source}}), (b {{id:$target}}) CREATE (a)-[:{relation}]->(b)', source=source, target=target).consume()


@pytest.mark.parametrize('namespace', ['', 's01'])
def test_real_map_queries_and_http_preserve_cases_knowledge_and_students_exclude_all_internal_ends(real_graph, namespace):
    graph, session, token = real_graph
    base = {'asset:one': ('Asset', {'code': 'HYD-01', 'name': '설비'}),
            'incident:one': ('Incident', {'name': '사건'}), 'case:one': ('DecisionCase', {'name': '판단'}),
            'manual:one': ('ManualSection', {'title': '근거 절'}), 'knowledge:one': ('KnowledgeSource', {'name': '판단 근거'})}
    for node_id, (label, props) in base.items():
        create_node(session, token, label, node_id, **props)
    create_edge(session, 'incident:one', 'asset:one', 'ON_ASSET')
    create_edge(session, 'case:one', 'incident:one', 'FOR_INCIDENT')
    create_edge(session, 'case:one', 'manual:one', 'CITES')
    create_edge(session, 'knowledge:one', 'manual:one', 'DOCUMENTED_IN')
    create_node(session, token, 'Asset', 'asset:other', code='HYD-02')
    create_node(session, token, 'Incident', 'incident:other')
    create_node(session, token, 'DecisionCase', 'case:other')
    create_edge(session, 'incident:other', 'asset:other', 'ON_ASSET')
    create_edge(session, 'case:other', 'incident:other', 'FOR_INCIDENT')
    create_node(session, token, 'Meeting', 's01:meeting', ns='s01', name='학생 회의')
    create_node(session, token, 'StudentNote', 's01:note', ns='s01', name='학생 노트')
    create_edge(session, 's01:meeting', 's01:note', 'HAS_NOTE')
    for node_id in base:
        create_edge(session, 's01:meeting', node_id, 'USES')
    create_node(session, token, 'Meeting', 's02:meeting', ns='s02')
    create_edge(session, 's01:meeting', 's02:meeting', 'OTHER_STUDENT')
    for label in sorted(LEGACY_INTERNAL | INTERNAL):
        for ns in ('', 's01'):
            node_id = 'internal:' + label + ':' + (ns or 'base')
            create_node(session, token, label + ':ManualSection', node_id, **({'ns': ns} if ns else {}))
            for business in ('manual:one', 's01:meeting'):
                create_edge(session, node_id, business, 'INTERNAL_TO_BUSINESS')
                create_edge(session, business, node_id, 'BUSINESS_TO_INTERNAL')
    create_node(session, token, 'Event:FlowNode', 'projected:event')
    create_edge(session, 'internal:ProcessVersion:base', 'projected:event', 'HAS_NODE')
    before = session.run('MATCH (n) RETURN count(n) AS n').single()['n']
    # Restoring the previous omission must reproduce internal records in nodes
    # AND edges at both ends. No production template/file is mutated.
    prior_nodes = session.run(prior_map_query('t0_graph_nodes'), asset='HYD-01', ns=namespace).data()
    assert any(n['id'].startswith('internal:') for n in prior_nodes)
    prior_edges = session.run(prior_map_query('t0_graph_edges'), asset='HYD-01', ns=namespace).data()
    assert any(e['from'].startswith('internal:') for e in prior_edges)
    assert any(e['to'].startswith('internal:') for e in prior_edges)
    response = TestClient(main.app).get('/api/ontology/graph', params={'asset': 'HYD-01', 'ns': namespace})
    assert response.status_code == 200, response.text
    actual = response.json()
    expected_ids = set(base) | ({'s01:meeting', 's01:note'} if namespace else set())
    assert {n['id'] for n in actual['nodes']} == expected_ids
    assert all(set(n['props']) >= {'id'} and {'id', 'label', 'name', 'props'} == set(n) for n in actual['nodes'])
    assert all(e['from'] in expected_ids and e['to'] in expected_ids for e in actual['edges'])
    expected_edges = ({('s01:meeting', node_id, 'USES') for node_id in base} |
                      {('s01:meeting', 's01:note', 'HAS_NOTE')}) if namespace else {
                          ('incident:one', 'asset:one', 'ON_ASSET'), ('case:one', 'incident:one', 'FOR_INCIDENT'),
                          ('case:one', 'manual:one', 'CITES'), ('knowledge:one', 'manual:one', 'DOCUMENTED_IN')}
    assert {(e['from'], e['to'], e['type']) for e in actual['edges']} == expected_edges
    assert session.run('MATCH (n) RETURN count(n) AS n').single()['n'] == before
