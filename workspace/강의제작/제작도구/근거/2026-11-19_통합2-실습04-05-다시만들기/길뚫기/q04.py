# 칸 원고(통합반_관계조회_칸.json)의 쿼리를 실습 DB에 대본 차례로 돌려 결과 · 통계 · 알림을 적는다.
# 쓰는 법(저장소 루트에서): PYTHONUTF8=1 .venv314/Scripts/python.exe <이 파일> [<랩_연결.json>] > <같은 폴더>/q04_결과.txt
#   랩_연결.json을 주지 않으면 이 PC 자리(작업/촬영/neo4j/lab/…)를 읽는다. 클라우드는 작업 폴더의 lab/… 자리를 준다(neo4j 촬영준비 길 1).
# 처음에 우리가 붙인 레이블(PracticeDevice · PracticeSensor)이 남아 있으면 멈춘다. 끝에 우리가 만든 것만 지우고 수를 센다. 설비 데이터는 건드리지 않는다.
import json,urllib.request,sys,datetime
ROOT='workspace/강의제작/'
H=json.load(open(sys.argv[1] if len(sys.argv)>1 else '작업/촬영/neo4j/lab/02회차/랩/02일차_실습1_관계조회/랩_연결.json',encoding='utf-8'))['http']
CELLS={c['id']:c['query'] for c in json.load(open(ROOT+'제작도구/촬영/neo4j/통합반_관계조회_칸.json',encoding='utf-8'))['cells']}
def run(q):
    body={'statements':[{'statement':q.rstrip().rstrip(';'),'includeStats':True,'resultDataContents':['row','graph']}]}
    req=urllib.request.Request(H+'/db/neo4j/tx/commit',json.dumps(body).encode('utf-8'),{'Content-Type':'application/json; charset=utf-8'})
    d=json.load(urllib.request.urlopen(req,timeout=30))
    if d['errors']: return {'오류':d['errors']}
    r=d['results'][0]
    nodes=set();rels=set()
    for x in r['data']:
        g=x.get('graph') or {}
        for n in g.get('nodes',[]):nodes.add(n['id'])
        for e in g.get('relationships',[]):rels.add(e['id'])
    st={k:v for k,v in (r.get('stats') or {}).items() if v and k!='contains_updates'}
    out={'칸이름':r['columns'],'행':[x['row'] for x in r['data']],'그림':{'노드':len(nodes),'관계':len(rels)},'통계':st}
    if d.get('notifications'): out['알림']=[n.get('title') or n.get('code') for n in d['notifications']]
    return out
def show(name,q):
    r=run(q);print(f'[{name}]\n{q}\n  -> '+json.dumps(r,ensure_ascii=False));return r
COUNT=[('노드 수','MATCH (n) RETURN count(n) AS 노드수'),('관계 수','MATCH ()-[r]->() RETURN count(r) AS 관계수'),('연습 레이블','MATCH (n) WHERE n:PracticeDevice OR n:PracticeSensor RETURN count(n) AS 남은수')]
print(f'==== 칸 원고 전체 실행 — q04.py · {datetime.date.today()} · 칸 {len(CELLS)}개 ====')
start=[show('처음 '+n,q)['행'][0][0] for n,q in COUNT]
if start[2]!=0: sys.exit('처음부터 연습 레이블이 남아 있다 — 멈춘다: '+str(start))
EXTRA={  # 그 칸 뒤(또는 앞)에 함께 돌리는, 대본에 없는 근거 쿼리
 '5-2':[('센서 수 확인(대본에 없음)','MATCH (s:PracticeSensor) RETURN count(s) AS 센서수')],
 '6-1':[('6-1 뒤 센서 속성(대본에 없음 — 정보 칸 값)',"MATCH (s:PracticeSensor {id:'basic-S1'}) RETURN s.id, s.name, s.unit"),
        ('그냥 DELETE 시도(대본에서는 말로만 — 오류가 나야 한다)',"MATCH (p:PracticeDevice {id:'basic-A'})\nDELETE p;")],
}
for cid,q in CELLS.items():
    if cid=='5-3': show('5-3 EXPLAIN(알림이 없어야 한다)','EXPLAIN '+q)
    show(cid,q)
    for n,x in EXTRA.get(cid,[]): show(n,x)
show('뒷정리(우리가 만든 것만)','MATCH (n) WHERE n:PracticeDevice OR n:PracticeSensor DETACH DELETE n')
end=[show('끝 '+n,q)['행'][0][0] for n,q in COUNT]
print('처음',start,'끝',end,'— 같음' if (start,end)==([20,19,0],[20,19,0]) else '— 다름')
