"""강사 참조 모델만 별도 교육 DB에서 검증. 학생/AI 수행 증거와 구별한다."""
from pathlib import Path
import json,re,urllib.request
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
URL='http://127.0.0.1:17474/db/neo4j/tx/commit'
def run(statement,parameters=None):
    body=json.dumps({'statements':[{'statement':statement,'parameters':parameters or {}}]}).encode()
    req=urllib.request.Request(URL,body,{'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:data=json.load(r)
    if data['errors']:raise RuntimeError(data['errors'])
    return [x['row'] for x in data['results'][0]['data']]
def ident(value):
    if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',value):raise ValueError(value)
    return value
def load(graph):
    for label in sorted({x for n in graph['nodes'] for x in n['labels']}):
        run(f'CREATE CONSTRAINT teaching_{ident(label)} IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE')
    for n in graph['nodes']:
        labels=':'.join(ident(x) for x in n['labels'])
        run(f'MERGE (n:{labels} {{id:$id}}) SET n += $props',{'id':n['props']['id'],'props':n['props']})
    for r in graph['rels']:
        run(f'MATCH (a {{id:$a}}),(b {{id:$b}}) MERGE (a)-[r:{ident(r["type"])}]->(b) SET r += $props',r)
def counts():return [run('MATCH (n) RETURN count(n)')[0][0],run('MATCH ()-[r]->() RETURN count(r)')[0][0]]
record={'kind':'강사 참조 모델 검증 — 학생 AI 수행/촬영 아님','url':URL,'courses':{}}
before=counts()
if before != [0,0]:raise RuntimeError(f'새 검증 DB가 비어 있지 않음: {before}')
for course in ['통합반','실전반']:
    graph=json.loads((HERE/'reference'/course/'graph.json').read_text(encoding='utf-8'))
    load(graph);first=counts();load(graph);second=counts()
    assert first==second==[len(graph['nodes']),len(graph['rels'])],(first,second)
    sensors=run('MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:MONITORED_BY]->(s:Sensor) RETURN a.id,collect(s.tag),count(s) ORDER BY a.id')
    assert len(sensors)==3 and all(x[2]==5 for x in sensors)
    parts=run('MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:USES_PART]->(p:Part) RETURN p.id,collect(DISTINCT a.id) ORDER BY p.id')
    assert len(parts)==3 and all(len(x[1])==3 for x in parts)
    entry={'first':first,'second':second,'sensors':sensors,'part_usage':parts}
    if course=='실전반':
        supply=run('MATCH (s:Supplier)-[r:SUPPLIES]->(p:Part) WHERE p.id=$sku RETURN s.name,r.approved,r.price_manwon,r.defect_rate,r.lead_days ORDER BY s.name',{'sku':'P-PMP-SEAL'})
        assert len(supply)==3 and sum(x[1] for x in supply)==2
        absent=run('MATCH (s:Supplier)-[r:SUPPLIES]->(p:Part) WHERE p.id=$sku RETURN s.name',{'sku':'NO-SUCH-PART'})
        assert absent==[]
        entry.update(supply=supply,unknown_part=absent)
    record['courses'][course]=entry
dest=ROOT/'.evidence/practice-20261026/reference-verification.json'
dest.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
