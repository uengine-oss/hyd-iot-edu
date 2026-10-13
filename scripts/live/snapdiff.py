"""읽기 전용: PR-07 문서 기록(d.snapshot)과 지금 그래프를 비교한다(manual_graph._snapshot 과 같은 범위, SET 없음)."""
import json, sys
from neo4j import GraphDatabase
DOC = '4010c166b291e580108f81f875ed1a133af9e5fe6f7e169ecb3496752729294d:339d914c-d3e7-45da-b822-3ae36895a795'
canon = lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
drv = GraphDatabase.driver('bolt://127.0.0.1:7687', auth=('neo4j', 'hydpass123'))
with drv.session() as s:
    snap = json.loads(s.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.snapshot AS s', id=DOC).single()['s'])
    owned = sorted({(n['labels'][0], n['props']['id']) for n in snap['nodes']})
    rows = {}
    for label, nid in owned:
        for r in s.run(f'MATCH (n:{label} {{id:$id}}) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props', id=nid).data():
            rows[r['eid']] = r
    for r in s.run('MATCH (n) WHERE n._manual_document=$d RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props', d=DOC).data():
        rows[r['eid']] = r
    nodes = [dict(labels=sorted(r['labels']), props=r['props']) for r in rows.values()]
    edges = s.run('MATCH (a)-[r]->(b) WHERE elementId(a) IN $e OR elementId(b) IN $e RETURN labels(a) AS from_labels, a.id AS from_id, labels(b) AS to_labels, b.id AS to_id, type(r) AS type, properties(r) AS props', e=list(rows)).data()
    for e in edges: e['from_labels'].sort(); e['to_labels'].sort()
cur = {'nodes': nodes, 'edges': edges}
for k in ('nodes', 'edges'):
    a = {canon(x) for x in snap[k]}; b = {canon(x) for x in cur[k]}
    print(f'== {k}: 기록 {len(a)} 지금 {len(b)}')
    for x in sorted(a - b): print('  기록에만', x[:600])
    for x in sorted(b - a): print('  지금만 ', x[:600])
