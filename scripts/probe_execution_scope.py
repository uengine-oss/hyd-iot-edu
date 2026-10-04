"""Real Neo4j projection: definition/version scope, empty roles, missing ontology."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from threading import Lock
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'it/process'), str(ROOT / 'common')]
from neo4j import GraphDatabase
from procsvc import engine, instances, procdb
from ontology_v2 import load_schema, validate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='.evidence/reaudit/execution-scope-live.json')
    args = ap.parse_args()
    tenant = 'scope-' + uuid.uuid4().hex[:12]
    report = {'tenant': tenant, 'checks': {}}
    c = json.loads(subprocess.check_output(['docker', 'inspect', 'hyd-iot-edu-neo4j-1']))[0]
    env = dict(x.split('=', 1) for x in c['Config']['Env'])
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=tuple(env['NEO4J_AUTH'].split('/', 1)))
    projection_writes = []
    writes_lock = Lock()

    def query(q, **args):
        with driver.session() as s:
            return s.execute_write(lambda tx: tx.run(q, **args).data())

    def check(name, passed, detail):
        report['checks'][name] = {'passed': bool(passed), 'detail': detail}
        print(name, 'PASS' if passed else 'FAIL', flush=True)

    def record(q, **params):
        rows = query(q, **params)
        with writes_lock:
            projection_writes.append(rows)
        return rows

    raw = engine.Definition.load(ROOT / 'it/process/definitions/anomaly_response.json').raw
    raw['activities'] = [deepcopy(next(a for a in raw['activities'] if a['id'] == 'task:select'))]
    raw['activities'][0]['attachedEvents'] = []
    raw['events'] = [e for e in raw['events'] if e['type'] in ('startEvent', 'endEvent')][:2]
    raw['gateways'] = []
    raw['sequences'] = [{'id': 's1', 'source': 'ev:alert', 'target': 'task:select'},
                        {'id': 's2', 'source': 'task:select', 'target': 'ev:closed'}]
    repo = procdb.MemoryRepo()
    hooks = instances.Hooks(record_cypher=record, query_cypher=query)
    try:
        query('CREATE CONSTRAINT v2_processversion_id IF NOT EXISTS FOR (n:ProcessVersion) REQUIRE n.id IS UNIQUE')
        records = []
        for did, version, roles, ref in [('a', '1', True, raw['ontologyRef']), ('b', '1', True, raw['ontologyRef']),
                                        ('a', '2', True, raw['ontologyRef']), ('empty', '1', False, raw['ontologyRef']),
                                        ('unmapped', '1', False, 'proc:' + tenant + ':missing')]:
            definition = deepcopy(raw)
            definition.update(processDefinitionId=did, version=version, ontologyRef=ref)
            if not roles:
                definition['roles'] = []
                definition['activities'][0].pop('role', None)
            rt = instances.InstanceRuntime(repo, engine.Definition.from_dict(definition), hooks, tenant_id=tenant)
            inst = rt.on_alert_raise({'asset': 'HYD-01', 'alertId': did+'-'+version})
            records.append((rt, inst))
        rows = query('MATCH (w:WorkItem)-[:IN_INSTANCE]->(i:ProcessInstance) WHERE i.tenant_id=$tenant '
                     'OPTIONAL MATCH (w)-[:EXECUTES]->(n) '
                     'RETURN i.id AS instance,w.id AS workitem,n.id AS target,n.definition_id AS definition,n.version AS version', tenant=tenant)
        by_instance = {r['instance']: r for r in rows}
        first = [by_instance.get(i['proc_inst_id']) for _, i in records[:3]]
        check('different_definitions_and_versions_have_distinct_targets', all(first) and len({r['target'] for r in first}) == 3, first)
        check('targets_carry_original_definition_and_version', all(first)
              and [(r['definition'], r['version']) for r in first] == [('a','1'),('b','1'),('a','2')], first)
        empty_id = records[3][1]['proc_inst_id']
        check('empty_roles_do_not_drop_workitems', empty_id in by_instance and bool(by_instance[empty_id]['target']), by_instance.get(empty_id))
        missing_id = records[4][1]['proc_inst_id']
        missing_graph = records[4][0].execution_view(missing_id)['graph']
        check('unmapped_ontology_keeps_execution_and_reports_warning', missing_id in by_instance
              and bool(by_instance[missing_id]['target']) and bool((missing_graph or {}).get('warnings')), missing_graph)
        check('missing_semantic_process_not_fabricated', not query('MATCH (n:Process {id:$id}) RETURN n.id', id='proc:'+tenant+':missing'), 'no placeholder')
        # Reprojection cannot keep stale assignment edges from an earlier view.
        rt, inst = records[0]
        inst['role_bindings'] = []
        repo.update_instance(inst)
        item = repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
        item['user_id'] = None; repo.update_workitem(item); rt._project(inst)
        stale = query('MATCH (i:ProcessInstance {id:$id}) OPTIONAL MATCH (i)-[r:ROLE_BOUND]->() '
                      'WITH i,count(r) AS roles OPTIONAL MATCH (:WorkItem)-[:IN_INSTANCE]->(i) '
                      'WITH i,roles OPTIONAL MATCH (w:WorkItem)-[:IN_INSTANCE]->(i) OPTIONAL MATCH (w)-[a:ASSIGNED_TO]->() '
                      'RETURN roles,count(a) AS assignments', id=inst['proc_inst_id'])[0]
        check('reprojection_removes_stale_bindings', stale == {'roles': 0, 'assignments': 0}, stale)
        inst['role_bindings'] = [{'name':'reviewer','endpoint':'role:operator'}, {'name':'requester','endpoint':'role:operator'}]
        repo.update_instance(inst)
        rt._project(inst)
        roles = query('MATCH (:ProcessInstance {id:$id})-[r:ROLE_BOUND]->(:Role {id:"role:operator"}) '
                      'RETURN r.role_name AS role ORDER BY role', id=inst['proc_inst_id'])
        check('two_roles_of_one_endpoint_are_preserved', roles == [{'role':'requester'},{'role':'reviewer'}], roles)
        before = len(projection_writes)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: rt._project(inst), range(8)))
        writes = projection_writes[before:]
        check('all_concurrent_projections_committed', len(writes) == 8
              and all(r and r[0]['projected_items'] == 1 for r in writes), writes)
        versions = query('MATCH (v:ProcessVersion {tenant_id:$tenant}) RETURN count(v) AS n,count(DISTINCT v.id) AS distinct', tenant=tenant)[0]
        flow_nodes = query('MATCH (n:FlowNode {tenant_id:$tenant}) RETURN count(n) AS n,count(DISTINCT n.id) AS distinct', tenant=tenant)[0]
        check('concurrent_reprojection_does_not_duplicate_nodes', versions == {'n':5,'distinct':5}
              and flow_nodes['n'] == flow_nodes['distinct'] == 15, {'versions':versions,'flow_nodes':flow_nodes})
        boundary_def = deepcopy(raw)
        boundary_def.update(processDefinitionId='boundary', version='1')
        boundary_def['events'].append({'id':'ev:timeout','name':'timeout','type':'boundaryEvent',
                                      'eventDefinition':'timer','timer':'PT10M','attachedTo':'task:select'})
        boundary_def['activities'][0]['attachedEvents'] = ['ev:timeout']
        boundary_def['sequences'].append({'id':'timeout-end','source':'ev:timeout','target':'ev:closed'})
        boundary_rt = instances.InstanceRuntime(repo, engine.Definition.from_dict(boundary_def), hooks, tenant_id=tenant)
        boundary_inst = boundary_rt.on_alert_raise({'asset':'HYD-01','alertId':'boundary'})
        boundary_graph = boundary_rt.execution_view(boundary_inst['proc_inst_id'])['graph']
        events = [w for w in boundary_graph['workitems'] if w['activity_id'] == 'ev:timeout']
        check('boundary_workitem_executes_versioned_event', len(events) == 1 and bool(events[0]['executes'])
              and events[0]['executes_type'] == 'Event', events)
        nodes = query('MATCH (n) WHERE n.tenant_id=$tenant RETURN labels(n) AS labels,properties(n) AS props', tenant=tenant)
        rels = query('MATCH (a)-[r]->(b) WHERE a.tenant_id=$tenant '
                     'RETURN type(r) AS type,a.id AS a,b.id AS b,labels(a) AS la,labels(b) AS lb,properties(r) AS props', tenant=tenant)
        errors = validate(nodes, rels, load_schema())
        check('projected_execution_obeys_canonical_schema', not errors, errors)
        template_dir = ROOT / 'it/neo4j/templates'
        map_nodes = query((template_dir / 't0_graph_nodes.cypher').read_text(encoding='utf-8'), asset='HYD-01')
        map_edges = query((template_dir / 't0_graph_edges.cypher').read_text(encoding='utf-8'), asset='HYD-01')
        node_ids = {n['id'] for n in map_nodes}
        runtime_labels = {'ProcessVersion','ProcessInstance','WorkItem','IngestionControl','IngestionBatch'}
        check('knowledge_map_excludes_execution_snapshots', not any(n['label'] in runtime_labels or
              (n['props'].get('definition_id') and n['props'].get('element_id')) for n in map_nodes), len(map_nodes))
        dangling = [e for e in map_edges if e['from'] not in node_ids or e['to'] not in node_ids]
        check('knowledge_map_edges_have_visible_endpoints', not dangling, dangling)
    finally:
        query('MATCH (n) WHERE n.tenant_id=$tenant DETACH DELETE n', tenant=tenant)
        report['cleanup_remaining'] = query('MATCH (n) WHERE n.tenant_id=$tenant RETURN count(n) AS n', tenant=tenant)[0]['n']
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        driver.close()
    raise SystemExit(0 if all(c['passed'] for c in report['checks'].values()) else 1)


if __name__ == '__main__':
    main()
