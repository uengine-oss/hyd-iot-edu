"""Real Cypher on an explicitly configured disposable graph; tenant-scoped cleanup only."""
import os
from uuid import uuid4

import pytest

from procsvc.bpmn_store import FlowStore
from procsvc.execution_graph import INSTANCE_Q, scoped
from test_bpmn_import import api, LOOP, B, loop_mapping

URI = os.getenv('HYD_CLEANUP_NEO4J_URI')
pytestmark = pytest.mark.skipif(not URI, reason='HYD_CLEANUP_NEO4J_URI must identify a disposable Neo4j')


@pytest.fixture
def graph(api):
    from neo4j import GraphDatabase
    client, rt, repo, audits = api
    # This fixture uses its own tenant for every created graph node. MemoryRepo
    # definitions are the same source as the API; no live application is involved.
    tenant = 'cleanup-test-' + uuid4().hex
    rt.repo.upsert_tenant({**rt.repo.get_tenant('hyd'), 'id': tenant, 'name': tenant})
    rt.tenant_id = tenant
    for user in rt.repo.list_users(None, 'hyd'):
        rt.repo.upsert_user({**user, 'tenant_id': tenant})
    rt.repo.upsert_proc_def(rt.defn.raw, tenant)
    rt.repo.record_deployment(rt.defn.id, rt.defn.raw['version'], tenant,
                              action='seed', actor='test', reason='isolated tenant startup', class_flow=True)
    driver = GraphDatabase.driver(URI, auth=('neo4j', os.environ['HYD_CLEANUP_NEO4J_PASSWORD']))
    writes = []
    def query(q, **params):
        with driver.session() as session:
            return [dict(row) for row in session.run(q, **params)]
    def write(q, **params):
        result = query(q, **params)
        writes.append((q, params))
        return result
    rt.hooks.record_cypher, rt.hooks.query_cypher = write, query
    yield client, rt, query, writes
    query('MATCH (n {tenant_id:$tenant}) DETACH DELETE n', tenant=tenant)
    driver.close()


def completed_case(client, rt, did='student-cleanup'):
    assert client.post('/api/flows/import', json={'xml': LOOP, 'definition_id': did}).status_code == 200
    response = client.post(f'/api/flows/{did}/register', json={'mapping': loop_mapping(B.parse_bpmn(LOOP))})
    assert response.status_code == 201, response.text
    inst = rt.start_definition(did, '1', uuid4().hex, values={'sample_id': 'S-1'})
    wi = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['status'] == 'IN_PROGRESS')
    rt.submit(wi['id'], {'iso_code': 10})
    assert rt.repo.get_instance(inst['proc_inst_id'])['status'] == 'COMPLETED'
    return inst


def test_actual_delete_removes_version_and_items_but_retains_revision_fence(graph):
    client, rt, query, writes = graph
    inst = completed_case(client, rt)
    assert rt.repo.projection_status(rt.tenant_id, inst['proc_inst_id'])['pending'] == 0
    before = next(params for q, params in writes if q == INSTANCE_Q)
    assert query('MATCH (v:ProcessVersion {tenant_id:$tenant}) RETURN count(v) AS n', tenant=rt.tenant_id)[0]['n'] == 1
    response = client.delete('/api/flows/student-cleanup')
    assert response.status_code == 200 and response.json()['projection_pending'] == 0, response.text
    assert query('MATCH (n {tenant_id:$tenant}) WHERE n:ProcessVersion OR n:FlowNode OR n:WorkItem OR n:ProcessInstance RETURN count(n) AS n', tenant=rt.tenant_id)[0]['n'] == 0
    assert query('MATCH (n:ExecutionProjection {id:$id}) RETURN count(n) AS n', id=inst['proc_inst_id'])[0]['n'] == 1
    assert query(INSTANCE_Q, **before) == []  # stale pre-delete delivery cannot resurrect the case


def test_reconciliation_reaches_legacy_hidden_case_and_instance_free_version(graph):
    client, rt, query, writes = graph
    inst = completed_case(client, rt)
    FlowStore(rt.repo, rt.tenant_id).reset()
    # Reproduce the old bug: source gone and hidden, but no pending deletion job.
    for job in rt.repo.projection_jobs.values():
        job['processed_at'] = True
    vid = scoped('proc-version', rt.tenant_id, 'never-ran', '1')
    nid = scoped('flow', rt.tenant_id, 'never-ran', '1', 'start')
    query('CREATE (v:ProcessVersion {id:$v,tenant_id:$tenant,definition_id:"never-ran",version:"1"}) '
          'CREATE (n:FlowNode {id:$n,tenant_id:$tenant,definition_id:"never-ran",version:"1"}) CREATE (v)-[:HAS_NODE]->(n)',
          v=vid, n=nid, tenant=rt.tenant_id)
    # A semantic node is not a version-scoped execution projection.
    query('CREATE (:FlowNode {id:$id,tenant_id:$tenant,name:"semantic preserved"})', id='semantic-' + rt.tenant_id, tenant=rt.tenant_id)
    rt.reconcile_projections()
    assert query('MATCH (v:ProcessVersion {tenant_id:$tenant}) RETURN count(v) AS n', tenant=rt.tenant_id)[0]['n'] == 0
    assert query('MATCH (p:ProcessInstance {id:$id}) RETURN count(p) AS n', id=inst['proc_inst_id'])[0]['n'] == 0
    assert query('MATCH (n:FlowNode {id:$id}) RETURN n.name AS name', id='semantic-' + rt.tenant_id) == [{'name': 'semantic preserved'}]


def test_registered_nonproduction_versions_are_excluded_from_orphan_candidates(graph):
    client, rt, query, writes = graph
    for index in range(23):
        raw = dict(rt.defn.raw, processDefinitionId=f'preserved-{index:02}', version='1')
        rt.repo.upsert_proc_def(raw, rt.tenant_id)
        query('CREATE (:ProcessVersion {id:$id,tenant_id:$tenant,definition_id:$did,version:"1"})',
              id=scoped('proc-version', rt.tenant_id, raw['processDefinitionId'], '1'), tenant=rt.tenant_id, did=raw['processDefinitionId'])
    orphan = scoped('proc-version', rt.tenant_id, 'zzz-orphan', '1')
    query('CREATE (:ProcessVersion {id:$id,tenant_id:$tenant,definition_id:"zzz-orphan",version:"1"})', id=orphan, tenant=rt.tenant_id)
    rt.cleanup_removed_definitions(limit=20)
    assert query('MATCH (v:ProcessVersion {id:$id}) RETURN count(v) AS n', id=orphan)[0]['n'] == 0
    assert query('MATCH (v:ProcessVersion {tenant_id:$tenant}) RETURN count(v) AS n', tenant=rt.tenant_id)[0]['n'] == 23
