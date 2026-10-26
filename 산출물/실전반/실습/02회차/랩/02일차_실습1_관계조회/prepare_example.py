"""관계 조회 실습의 제공 예제만 적재한다. 학생이 작성할 조회문은 만들지 않는다."""
from pathlib import Path
import json,urllib.request
from lab_db import prepare
HERE=Path(__file__).resolve().parent

def main():
    state=prepare()
    def run(statement):
        req=urllib.request.Request(state['http']+'/db/neo4j/tx/commit',json.dumps({'statements':[{'statement':statement}]}).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:data=json.load(response)
        if data['errors']:raise RuntimeError(data['errors'])
        return [x['row'] for x in data['results'][0]['data']]
    # 이 패키지의 고정 예제에는 문자열 내부 세미콜론이 없다.
    source='\n'.join(line for line in (HERE/'예제_적재.cypher').read_text(encoding='utf-8-sig').splitlines() if not line.strip().startswith('//'))
    for statement in source.split(';'):
        if statement.strip():run(statement)
    counts={'nodes':run('MATCH (n) RETURN count(n)')[0][0],'relationships':run('MATCH ()-[r]->() RETURN count(r)')[0][0]}
    if counts!={'nodes':20,'relationships':19}:raise RuntimeError('예제 수량 확인 필요: '+str(counts))
    (HERE/'결과').mkdir(exist_ok=True)
    (HERE/'결과/예제_준비.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2),encoding='utf-8')
    print('예제 준비 완료: 노드 20개 · 관계 19개. 조회_작성.cypher에서 질문을 작성하세요.')

if __name__=='__main__':main()
