"""Real HTTP review/commit/rollback chain against an explicitly disposable graph.

Uses the existing empty-database guard and cleanup; never the application graph.
"""
import base64
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import manual_api
from test_manual_revision_history import (
    graph, archive, URI, TEXT, REVISED, WITHOUT_92, SKILL_91, SKILL_92,
    choose, chosen, journal,
)


@pytest.fixture
def api(graph, archive):
    from neo4j import GraphDatabase
    audits = []
    app = FastAPI()
    manual_api.register(app, archive_factory=lambda: archive,
        driver_factory=lambda: GraphDatabase.driver(URI, auth=('neo4j', os.environ['HYD_MANUAL_NEO4J_PASSWORD'])),
        tenant='hyd', audit=lambda *args, **kwargs: audits.append((args, kwargs)))
    with TestClient(app) as client:
        yield client, audits


def review(client, text, document=None):
    response = client.post('/api/kg/manuals/preview', json={
        'filename': 'manual.md', 'data': base64.b64encode(text.encode('utf-8')).decode(),
        **({'document_id': document} if document else {})})
    assert response.status_code == 200, response.text
    proposal = response.json()
    proposal.update(by='검토자', reviewed=True,
                    links={p['id']: {'failureMode': 'fm:bearing-degradation'} for p in proposal['procedures']})
    return proposal


def ingest(client, text, document=None):
    proposal = review(client, text, document)
    response = client.post('/api/kg/manuals/commit', json=proposal)
    assert response.status_code == 200, response.text
    return proposal, response.json()


def snapshot(graph):
    """Include IDs, journals, batches and ingestion lock to catch partial writes."""
    nodes = graph.run('MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props ORDER BY id').data()
    edges = graph.run('MATCH (a)-[r]->(b) RETURN elementId(r) AS id, elementId(a) AS a, '
                      'elementId(b) AS b, type(r) AS type, properties(r) AS props ORDER BY id').data()
    return {'nodes': nodes, 'edges': edges}


def test_revision_removals_are_previewed_without_writes_and_kept_in_receipt(api, graph):
    client, _ = api
    first, receipt = ingest(client, TEXT)
    revision = review(client, WITHOUT_92, first['document_id'])
    before = snapshot(graph)
    response = client.post('/api/kg/manuals/changes', json=revision)
    assert response.status_code == 200, response.text
    changes = response.json()
    assert snapshot(graph) == before
    assert changes['previous_batch'] == receipt['batch']
    removed = {n['id']: n for n in changes['removed']}
    assert removed[SKILL_92]['name'] == '베어링 점검'
    assert SKILL_91 not in removed
    applied = client.post('/api/kg/manuals/commit', json=revision)
    assert applied.status_code == 200, applied.text
    assert applied.json()['removed'] == changes['removed']
    history = client.get('/api/kg/manuals').json()
    assert next(b for b in history if b['batch'] == applied.json()['batch'])['removed'] == changes['removed']
    stale = client.post('/api/kg/manuals/changes', json=revision)
    assert stale.status_code == 409


def test_http_revision_and_initial_batch_rollback_refuse_used_node_without_any_graph_change(api, graph, archive):
    client, audits = api
    first, v1 = ingest(client, TEXT)
    choose(graph, SKILL_92, 'case:HTTP-1')
    before = snapshot(graph)
    candidate = review(client, WITHOUT_92, first['document_id'])
    assert candidate['previous_batch'] == v1['batch']
    refused = client.post('/api/kg/manuals/commit', json=candidate)
    assert refused.status_code == 409
    assert f'Skill {SKILL_92} ← CHOSE 1건' in refused.json()['detail']
    assert snapshot(graph) == before
    assert len(audits) == 1 and audits[0][0][2] == 'MANUAL_INGESTED'

    refused = client.post(f"/api/kg/manuals/batches/{v1['batch']}/rollback", json={'by': '검토자'})
    assert refused.status_code == 409
    assert f'Skill {SKILL_92} ← CHOSE 1건' in refused.json()['detail']
    assert snapshot(graph) == before and len(audits) == 1
    assert journal(graph, first)[0] == v1['batch']
    batches = client.get('/api/kg/manuals').json()
    assert len(batches) == 1 and batches[0]['status'] == 'ACTIVE' and batches[0]['current']


def test_http_revision_and_rollback_keep_surviving_node_and_real_decision_history(api, graph):
    client, audits = api
    first, v1 = ingest(client, TEXT)
    choose(graph, SKILL_91, 'case:HTTP-2')
    before = chosen(graph, SKILL_91)
    _, v2 = ingest(client, REVISED, first['document_id'])
    assert chosen(graph, SKILL_91) == before
    assert v2['history_kept'] == [{'node': 'Skill ' + SKILL_91, 'type': 'CHOSE', 'count': 1}]
    old = client.post(f"/api/kg/manuals/batches/{v1['batch']}/rollback", json={'by': '검토자'})
    assert old.status_code == 409 and '최신 판본부터 순서대로' in old.json()['detail']
    assert journal(graph, first)[0] == v2['batch']
    undone = client.post(f"/api/kg/manuals/batches/{v2['batch']}/rollback", json={'by': '검토자'})
    assert undone.status_code == 200, undone.text
    assert undone.json()['restored_batch'] == v1['batch']
    assert undone.json()['history_kept'] == v2['history_kept']
    assert journal(graph, first)[0] == v1['batch'] and chosen(graph, SKILL_91) == before
    steps = graph.run('MATCH (:Skill {id:$id})-[:HAS_STEP]->(s:Step) RETURN s.text AS text ORDER BY s.order', id=SKILL_91).data()
    assert [s['text'] for s in steps] == ['정지한다.', '벨트를 확인한다.']
    assert [event[0][2] for event in audits] == ['MANUAL_INGESTED', 'MANUAL_INGESTED', 'MANUAL_ROLLED_BACK']


def test_http_revision_batch_rollback_refuses_newly_used_node_atomically(api, graph):
    client, audits = api
    first, _ = ingest(client, WITHOUT_92)
    _, v2 = ingest(client, TEXT, first['document_id'])
    choose(graph, SKILL_92, 'case:HTTP-3')
    before = snapshot(graph)
    refused = client.post(f"/api/kg/manuals/batches/{v2['batch']}/rollback", json={'by': '검토자'})
    assert refused.status_code == 409
    assert f'Skill {SKILL_92} ← CHOSE 1건' in refused.json()['detail']
    assert snapshot(graph) == before and journal(graph, first)[0] == v2['batch']
    assert [row['c'] for row in chosen(graph, SKILL_92)] == ['case:HTTP-3']
    assert [event[0][2] for event in audits] == ['MANUAL_INGESTED', 'MANUAL_INGESTED']
