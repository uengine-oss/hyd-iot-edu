"""오프라인1 제공 적재 절차. 온라인2 구현 과제에는 배포하지 않는다."""
from pathlib import Path
import json,re,urllib.request
from lab_db import prepare
HERE=Path(__file__).resolve().parent

def main():
    state=prepare()
    graph=json.loads((HERE/'입력/graph.json').read_text(encoding='utf-8-sig'))
    def ident(value):
        if not isinstance(value,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',value):raise ValueError('종류/관계 이름 확인: '+str(value))
        return value
    statements=[]
    for label in sorted({ident(x) for n in graph['nodes'] for x in n['labels']}):
        statements.append({'statement':f'CREATE CONSTRAINT practice_{label} IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE','parameters':{}})
    def run(items):
        req=urllib.request.Request(state['http']+'/db/neo4j/tx/commit',json.dumps({'statements':items}).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=60) as response:data=json.load(response)
        if data['errors']:raise RuntimeError(data['errors'])
        return data['results']
    run(statements);statements=[]
    for n in graph['nodes']:
        label=':'.join(ident(x) for x in n['labels'])
        statements.append({'statement':f'MERGE (n:{label} {{id:$id}}) SET n += $props','parameters':{'id':n['props']['id'],'props':n['props']}})
    for r in graph['rels']:
        statements.append({'statement':f'MATCH (a {{id:$a}}),(b {{id:$b}}) MERGE (a)-[r:{ident(r["type"])}]->(b) SET r += $props','parameters':r})
    run(statements)
    counts=[run([{'statement':q}])[0]['data'][0]['row'][0] for q in ['MATCH (n) RETURN count(n)','MATCH ()-[r]->() RETURN count(r)']]
    record={'nodes':counts[0],'relationships':counts[1],'input_nodes':len(graph['nodes']),'input_relationships':len(graph['rels'])}
    (HERE/'결과').mkdir(exist_ok=True)
    (HERE/'결과/적재_확인.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False));print('적재 완료. Browser에서 질문별 결과를 확인하세요.')

if __name__=='__main__':main()
