"""Real Neo4j/SQLite source-owned manual commit, conflict, rollback and races."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'it/process'))
from neo4j import GraphDatabase
from procsvc import manual_graph, manual_review
from procsvc.manual_sources import ManualSources


def main():
    unique = uuid.uuid4().hex[:10].upper()
    tenant = 'manual-probe-' + unique
    dest = Path('.evidence/reaudit/manual-graph-live') / unique
    dest.mkdir(parents=True)
    archive = ManualSources(dest / 'sources.sqlite')
    report = {'tenant': tenant, 'checks': []}
    env = dict(v.split('=', 1) for v in json.loads(subprocess.check_output(
        ['docker', 'inspect', 'hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=tuple(env['NEO4J_AUTH'].split('/', 1)))
    plans = []
    rule = 'rule:manual-probe:' + unique

    def query(cypher, **params):
        with driver.session() as session:
            return session.run(cypher, **params).data()

    def check(name, ok, detail=None):
        report['checks'].append(dict(name=name, passed=bool(ok), detail=detail))
        (dest / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        assert ok, name

    def make(suffix, *, document_id=None, previous=None, variant='벨트를 확인한다.'):
        raw = f'# 정비\nHM-8.1 팬\nSOP-LIVE-{unique}-{suffix} 벨트 점검\n1. 설비를 정지한다.\n2. {variant}\n'
        source = archive.save(tenant, 'same-name.md', raw.encode(), document_id=document_id)
        body = manual_review.proposal(source)
        body.update(reviewed=True, by='[회귀 검사] 실제 검증', previous_batch=previous,
                    links={p['id']: {'failureMode': 'fm:bearing-degradation'} for p in body['procedures']})
        plan = manual_review.validate(archive, tenant, body)
        plans.append(plan)
        return plan

    def commit(plan):
        with driver.session() as session:
            return manual_graph.commit(session, plan)

    def rollback(plan):
        with driver.session() as session:
            return manual_graph.rollback(session, tenant, plan['batch'], '실제 검증 정리')

    def snapshot(plan):
        with driver.session() as session:
            return session.execute_write(lambda tx: manual_graph._snapshot(tx, plan['document']))

    def conflict(fn):
        try:
            fn()
        except (manual_graph.Conflict, KeyError):
            return True
        return False

    try:
        a = make('A')
        first = commit(a)
        check('actual Neo4j nodes/edges exactly match reviewed plan', snapshot(a) == manual_graph.desired(a), first)
        check('same batch retry uses existing receipt', commit(a)['replayed'])
        b = make('B')
        commit(b)
        section_rows = query('MATCH (n:ManualSection {ref:"HM-8.1"}) WHERE n._manual_document IN $docs '
                             'RETURN n.id AS id, n.source_id AS source', docs=[a['document'], b['document']])
        check('same filename/ref from two documents stays separate', len(section_rows) == 2 and
              len({r['id'] for r in section_rows}) == 2 and len({r['source'] for r in section_rows}) == 2, section_rows)
        collision = make('A')
        check('another document cannot overwrite existing SOP', conflict(lambda: commit(collision)) and not snapshot(collision)['nodes'])
        invalid = make('INVALID')
        invalid['procedures'][0]['approver'] = 'role:does-not-exist:' + unique
        check('missing target rolls back whole graph', conflict(lambda: commit(invalid)) and not snapshot(invalid)['nodes'])
        rev = make('A', document_id=a['document_id'], previous=a['batch'], variant='변경된 장력을 확인한다.')
        real_replace = manual_graph._replace
        def fail_after_write(tx, document, state):
            real_replace(tx, document, state)
            raise RuntimeError('probe after all graph writes, before receipt')
        manual_graph._replace = fail_after_write
        try:
            try:
                commit(rev)
            except RuntimeError:
                pass
        finally:
            manual_graph._replace = real_replace
        check('actual transaction failure preserves previous graph and no receipt', snapshot(a) == manual_graph.desired(a) and
              not query('MATCH (b:ManualIngestionBatch {id:$id}) RETURN b.id', id=rev['batch']))
        sid = first['skills'][a['procedures'][0]['id']]['skill']
        query('CREATE (r:Rule {id:$rule, name:"검증 중 외부 참조"}) WITH r MATCH (s:Skill {id:$sid}) CREATE (r)-[:OUTPUTS]->(s)', rule=rule, sid=sid)
        check('rule reference prevents silent revision and rollback', conflict(lambda: commit(rev)) and conflict(lambda: rollback(a)))
        query('MATCH (r:Rule {id:$rule})-[e:OUTPUTS]->(:Skill {id:$sid}) DELETE e', rule=rule, sid=sid)
        check('external rule node is preserved', len(query('MATCH (r:Rule {id:$id}) RETURN r.id', id=rule)) == 1)
        commit(rev)
        check('explicit revision replaces complete owned graph', snapshot(rev) == manual_graph.desired(rev))
        check('old original and citations survive revision', archive.original(tenant, a['source_id']).endswith('2. 벨트를 확인한다.\n'.encode()) and
              archive.original(tenant, rev['source_id']).endswith('2. 변경된 장력을 확인한다.\n'.encode()) and
              archive.get(tenant, a['source_id'])['sha256'] == a['sha256'])
        stale = make('A', document_id=a['document_id'], previous=a['batch'], variant='오래된 검토')
        check('stale preview and out-of-order undo rejected', conflict(lambda: commit(stale)) and conflict(lambda: rollback(a)))
        query('MATCH (s:Skill {id:$id}) SET s.externalNote="다른 사용자의 편집"', id=sid)
        check('external property drift prevents undo', conflict(lambda: rollback(rev)))
        query('MATCH (s:Skill {id:$id}) REMOVE s.externalNote', id=sid)
        rollback(rev)
        check('latest rollback restores prior full graph and source', snapshot(a) == manual_graph.desired(a))
        check('repeat rollback is idempotent', rollback(rev)['replayed'])
        concurrent = make('RACE')
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: commit(concurrent), range(8)))
        check('eight concurrent requests commit exactly one batch', sum(not r['replayed'] for r in results) == 1 and
              snapshot(concurrent) == manual_graph.desired(concurrent), {'requests': len(results), 'new': sum(not r['replayed'] for r in results)})
        with driver.session() as session:
            rows = manual_graph.history(session, tenant)
            hidden = manual_graph.history(session, 'other-' + tenant)
        check('durable history separates active rolled-back and tenant', len(rows) == 4 and not hidden and
              any(r['status'] == 'ROLLED_BACK' for r in rows), rows)
        check('source archive remains readable through new object', ManualSources(dest / 'sources.sqlite').get(tenant, a['source_id'])['sha256'] == a['sha256'])
        print(f"{len(report['checks'])}/{len(report['checks'])} PASS: {dest}", flush=True)
    finally:
        # Use public rollback, newest first. Failure evidence and source files stay.
        for plan in reversed(plans):
            try:
                rollback(plan)
            except (manual_graph.Conflict, KeyError):
                pass
        query('MATCH (r:Rule {id:$id}) WHERE NOT (r)--() DELETE r', id=rule)
        docs = list({p['document'] for p in plans})
        remaining = query('MATCH (n) WHERE n._manual_document IN $docs RETURN count(n) AS n', docs=docs)[0]['n']
        report['remaining_owned_nodes'] = remaining
        (dest / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        driver.close()


if __name__ == '__main__':
    main()
