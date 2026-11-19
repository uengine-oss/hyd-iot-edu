# 새 차례(대본 g판)의 쿼리를 실습 DB에 차례로 돌려 결과 · 통계 · 알림을 적는다. lab/ 에서 실행.
import json,urllib.request,sys
H=json.load(open('랩_연결.json',encoding='utf-8'))['http']
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
Q=[
('처음 수','MATCH (n) RETURN count(n) AS 노드수'),
('처음 관계 수','MATCH ()-[r]->() RETURN count(r) AS 관계수'),
('2-1',"CREATE (a:연습장치 {id:'basic-A', name:'연습 펌프', score:40}),\n       (b:연습장치 {id:'basic-B', name:'연습 팬', score:70});"),
('3-1','MATCH (n:연습장치)\nRETURN n;'),
('3-2','MATCH (n:연습장치)\nRETURN n.name AS 이름, n.score AS 점수\nORDER BY 점수;'),
('4-1','MATCH (n:연습장치)\nWHERE n.score >= 50\nRETURN n;'),
('5-1',"MERGE (s:연습센서 {id:'basic-S1'})\nSET s.name = '연습 온도 센서', s.unit = '℃'\nRETURN s;"),
('5-2(같은 쿼리 다시)',"MERGE (s:연습센서 {id:'basic-S1'})\nSET s.name = '연습 온도 센서', s.unit = '℃'\nRETURN s;"),
('센서 수 확인(대본에 없음)','MATCH (s:연습센서) RETURN count(s) AS 센서수'),
('5-3 후보A EXPLAIN(쉼표 한 MATCH)',"EXPLAIN MATCH (p:연습장치 {id:'basic-A'}), (s:연습센서 {id:'basic-S1'})\nMERGE (p)-[r:감시된다]->(s)\nRETURN p, r, s"),
('5-3 후보B EXPLAIN(MATCH 두 줄)',"EXPLAIN MATCH (p:연습장치 {id:'basic-A'})\nMATCH (s:연습센서 {id:'basic-S1'})\nMERGE (p)-[r:감시된다]->(s)\nRETURN p, r, s"),
('5-3',"MATCH (p:연습장치 {id:'basic-A'})\nMATCH (s:연습센서 {id:'basic-S1'})\nMERGE (p)-[r:감시된다]->(s)\nRETURN p, r, s;"),
('6-1',"MATCH (p:연습장치 {id:'basic-A'})-[r:감시된다]->(s:연습센서 {id:'basic-S1'})\nSET s.name = '연습 유온 센서'\nRETURN p, r, s;"),
('6-1 뒤 센서 속성(대본에 없음 — 정보 칸 값)',"MATCH (s:연습센서 {id:'basic-S1'}) RETURN s.id, s.name, s.unit"),
('그냥 DELETE 시도(대본에서는 말로만)',"MATCH (p:연습장치 {id:'basic-A'})\nDELETE p;"),
('7-1',"MATCH (p:연습장치 {id:'basic-A'})\nDETACH DELETE p;"),
('7-2','MATCH (n:연습장치|연습센서)\nRETURN n;'),
('7-2 이름(대본에 없음)','MATCH (n:연습장치|연습센서) RETURN n.name ORDER BY n.name'),
('7-3','MATCH (n:연습장치|연습센서)\nDELETE n;'),
('7-4','MATCH (n:연습장치|연습센서)\nRETURN count(n) AS 남은수;'),
('8-1','MATCH (n)\nRETURN labels(n) AS 레이블, count(n) AS 개수\nORDER BY 개수 DESC;'),
('9-1',"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)\nRETURN c.name AS 구성요소;"),
('10-1',"MATCH path = (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(:Component)-[:USES_PART]->(:Part)\nRETURN path;"),
('10-2',"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p:Part)\nWHERE c.name = '오일 쿨러'\nRETURN c.name AS 구성요소, p.name AS 부품, p.partNo AS 품번;"),
('11-1',"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)\nRETURN c.name AS 구성요소, s.name AS 센서, s.tag AS 태그, s.virtual AS 가상\nORDER BY 구성요소, 태그;"),
('11-2',"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)\nWHERE s.virtual = false\nRETURN c.name AS 구성요소, s.name AS 센서, s.tag AS 태그, s.virtual AS 가상\nORDER BY 구성요소, 태그;"),
('11-3',"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)\nRETURN c.name AS 구성요소, count(s) AS 센서수, collect(s.tag) AS 태그목록\nORDER BY 센서수 DESC, 구성요소;"),
('끝 수','MATCH (n) RETURN count(n) AS 노드수'),
('끝 관계 수','MATCH ()-[r]->() RETURN count(r) AS 관계수'),
('끝 연습 레이블','MATCH (n:연습장치|연습센서) RETURN count(n) AS 남은수'),
]
print('\n==== 새 차례(대본 g판) 쿼리 실행 — q04c.py ====')
for name,q in Q:
    print(f'[{name}]\n{q}\n  -> '+json.dumps(run(q),ensure_ascii=False))
