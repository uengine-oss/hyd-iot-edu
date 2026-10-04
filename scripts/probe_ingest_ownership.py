"""Real Neo4j ownership/rollback tests, isolated by a unique datasource.

Normal cleanup uses the same clear contract. Emergency fixture cleanup touches
only the exact ids recorded by this run; production data is never matched.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'it/process'))
from neo4j import GraphDatabase
from procsvc import ingest, graph_ingest
from ontology_v2 import validate


def main():
    suffix = uuid.uuid4().hex[:12]
    ds = 'ownership_' + suffix
    prefix = 'probe:' + suffix + ':'
    report = {'checks': {}, 'datasource': ds}
    dest = Path('.evidence/reaudit/ingest-ownership-live.json')
    container = json.loads(subprocess.check_output(['docker', 'inspect', 'hyd-iot-edu-neo4j-1']))[0]
    env = dict(item.split('=', 1) for item in container['Config']['Env'])
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=tuple(env['NEO4J_AUTH'].split('/', 1)))
    ids, batches = set(), set()

    def check(name, passed, detail=None):
        report['checks'][name] = {'passed': bool(passed), 'detail': detail}
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'PASS' if passed else 'FAIL', flush=True)
        assert passed, name

    def query(q, **args):
        with driver.session() as s:
            return s.run(q, **args).data()

    def plan(key, table='items', system='a'):
        p = ingest.plan(ingest.parse_ddl(f'CREATE TABLE public.{table} (asset text, value numeric);'),
                        filename=key+'.sql', batch=prefix+key, datasource=ds,
                        selection={f'public.{table}': ['value']}, systems={f'public.{table}': prefix+system})
        ids.update(i['id'] for i in p['systems']+p['inputs'])
        batches.add(p['batch'])
        return p

    def commit(p):
        with driver.session() as s:
            return graph_ingest.commit(s, p)

    def clear(p):
        with driver.session() as s:
            return graph_ingest.clear(s, p['batch'])

    def state(p):
        return query('MATCH (i:InputData {id:$id}) OPTIONAL MATCH (i)-[:SOURCED_FROM]->(s) '
                     'RETURN properties(i) AS props, collect(s.id) AS sources', id=p['inputs'][0]['id'])

    def conflict(fn):
        try:
            fn()
        except graph_ingest.Conflict:
            return True
        return False

    try:
        a, b = plan('a'), plan('b', system='b')
        commit(a)
        check('identical_batch_replay', commit(a)['replayed'] and len(state(a)) == 1)
        changed = copy.deepcopy(a); changed['inputs'][0]['name'] = 'changed'
        check('same_batch_changed_content_rejected', conflict(lambda: commit(changed)))
        commit(b)
        check('new_revision_replaces_source', state(a)[0]['sources'] == [prefix+'b'])
        clear(b)
        restored = state(a)[0]
        check('latest_clear_restores_previous_source_and_props',
              restored['sources'] == [prefix+'a'] and restored['props']['source_id'] == a['inputs'][0]['source_id'])
        check('cleared_batch_cannot_reapply', conflict(lambda: commit(b)))
        check('clear_replay_is_idempotent', clear(b)['replayed'])
        c = plan('c', system='c'); commit(c); clear(a)
        check('earlier_clear_preserves_later_revision', state(c)[0]['sources'] == [prefix+'c'])
        clear(c)
        check('last_owner_removes_only_generated_nodes', not state(c))

        # Existing semantic data and relationship properties must be restored.
        d = plan('d', table='preexisting')
        sid, iid = d['systems'][0]['id'], d['inputs'][0]['id']
        query('CREATE (s:System {id:$s, name:"original", zone:"OT"}), '
              '(i:InputData {id:$i, name:"before", typeRef:"number", variable:"before", custom:"untouched"}), '
              '(i)-[:SOURCED_FROM {note:"original edge"}]->(s)', s=sid, i=iid)
        before = state(d)
        commit(d); out = clear(d)
        edge = query('MATCH (:InputData {id:$id})-[r:SOURCED_FROM]->(s) RETURN properties(r) AS r, s.zone AS zone', id=iid)
        check('preexisting_data_and_edge_restored', state(d) == before and out['restored'] == 2
              and edge == [{'r': {'note': 'original edge'}, 'zone': 'OT'}])

        e = plan('e', table='used'); commit(e)
        rid = prefix+'rule'; ids.add(rid)
        query('CREATE (r:Rule {id:$r}) WITH r MATCH (i:InputData {id:$i}) CREATE (r)-[:TESTS]->(i)',
              r=rid, i=e['inputs'][0]['id'])
        check('dependent_rule_blocks_clear_atomically', conflict(lambda: clear(e)) and bool(state(e))
              and query('MATCH (b:IngestionBatch {id:$id}) RETURN b.status AS status', id=e['batch'])[0]['status'] == 'ACTIVE')
        query('MATCH (r:Rule {id:$id}) DETACH DELETE r', id=rid); clear(e)

        f = plan('f', table='manual'); commit(f)
        query('MATCH (i:InputData {id:$id}) SET i.name="manual"', id=f['inputs'][0]['id'])
        check('manual_change_blocks_clear', conflict(lambda: clear(f)) and state(f)[0]['props']['name'] == 'manual')
        query('MATCH (i:InputData {id:$id}) SET i.name=$name', id=f['inputs'][0]['id'], name=f['inputs'][0]['name']); clear(f)

        extra = plan('extra', table='extension'); commit(extra)
        query('MATCH (i:InputData {id:$id}) SET i.custom="external"', id=extra['inputs'][0]['id'])
        check('external_extension_blocks_delete', conflict(lambda: clear(extra)) and state(extra)[0]['props']['custom'] == 'external')
        query('MATCH (i:InputData {id:$id}) REMOVE i.custom', id=extra['inputs'][0]['id']); clear(extra)

        g = plan('g', table='atomic')
        query('CREATE (:InputData {id:$id, ingest_batch:"legacy-test"})', id=g['inputs'][0]['id'])
        check('failure_rolls_back_system_claim_and_receipt', conflict(lambda: commit(g))
              and not query('MATCH (s:System {id:$id}) WHERE $batch IN s._ingest_batches RETURN s.id',
                            id=g['systems'][0]['id'], batch=g['batch'])
              and not query('MATCH (b:IngestionBatch {id:$id}) RETURN b.id', id=g['batch']))
        check('legacy_clear_refuses_unsafe_delete', conflict(lambda: clear({'batch': 'legacy-test'})))

        plans = [plan('concurrent'+str(n), table='concurrent') for n in range(8)]
        # Initialize constraints once before deliberately overlapping transactions.
        with driver.session() as s:
            graph_ingest.ensure_schema(s)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(commit, plans))
        row = state(plans[0])[0]
        check('concurrent_imports_preserve_all_claims', len(row['props']['_ingest_batches']) == 8 and len(results) == 8)
        active_ids = list({i['id'] for p in plans for i in p['inputs'] + p['systems']})
        nodes = query('MATCH (n) WHERE n.id IN $ids OR n:IngestionBatch OR n:IngestionControl '
                      'RETURN labels(n) AS labels, properties(n) AS props', ids=active_ids)
        relations = query('MATCH (a)-[r]->(b) WHERE a.id IN $ids '
                          'RETURN type(r) AS type,a.id AS a,b.id AS b,labels(a) AS la,labels(b) AS lb,properties(r) AS props', ids=active_ids)
        schema = json.loads(Path('it/neo4j/v2/schema.json').read_text(encoding='utf-8'))
        violations = validate(nodes, relations, schema)
        check('active_journal_obeys_canonical_schema', not violations, violations)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(clear, plans))
        check('concurrent_clears_remove_last_owner_only', not state(plans[0]) and sum(r['deleted'] for r in results) == 1)
        replay = plan('concurrent-replay', table='replayed')
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(commit, [replay] * 8))
        check('concurrent_same_batch_applied_once', sum(not r['replayed'] for r in results) == 1
              and state(replay)[0]['props']['_ingest_batches'] == [replay['batch']])
        clear(replay)
    finally:
        # Exact ids from this fixture only. Keep receipts in the report before removal.
        report['receipts'] = query('MATCH (b:IngestionBatch) WHERE b.id IN $ids RETURN properties(b) AS batch', ids=list(batches))
        query('MATCH (n) WHERE n.id IN $ids DETACH DELETE n', ids=list(ids | batches))
        report['cleanup_remaining'] = query('MATCH (n) WHERE n.id IN $ids RETURN count(n) AS n', ids=list(ids | batches))[0]['n']
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        driver.close()


if __name__ == '__main__':
    main()
