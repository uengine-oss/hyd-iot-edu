// 위에서부터 한 문장씩 실행합니다. 전체 파일을 한 번에 실행하지 않습니다.
// CREATE 문장은 한 번 실행합니다. 준비된 설비와 별도의 연습장치·연습센서만 수정·삭제합니다.

CREATE (a:연습장치 {id:'basic-A', name:'연습 펌프', score:40}),
       (b:연습장치 {id:'basic-B', name:'연습 팬', score:70});

MATCH (n:연습장치)
RETURN n;

MATCH (n:연습장치)
RETURN n;

MATCH (n:연습장치)
RETURN n.name AS name,n.score AS score
ORDER BY score;

MATCH (n:연습장치)
WHERE n.score >= 50
RETURN n;

MATCH (n:연습장치)
WHERE n.score >= 30
RETURN n;

MATCH (n:연습장치)
WHERE (n.name='연습 펌프' OR n.name='연습 팬')
  AND n.score >= 50
RETURN n;

MATCH (n:연습장치)
WHERE n.name='연습 펌프' OR n.name='연습 팬'
  AND n.score >= 50
RETURN n;

MERGE (s:연습센서 {id:'basic-S1'})
SET s.name='연습 온도 센서', s.unit='℃'
RETURN s;

MERGE (s:연습센서 {id:'basic-S1'})
SET s.name='연습 온도 센서', s.unit='℃'
WITH s
MATCH (n:연습센서)
RETURN count(n) AS sensor_count;

MATCH (p:연습장치 {id:'basic-A'}),(s:연습센서 {id:'basic-S1'})
MERGE (p)-[r:관측]->(s)
RETURN p,r,s;

MATCH (s:연습센서 {id:'basic-S1'})
SET s.name='연습 유온 센서'
RETURN s;

MATCH p=(:연습장치 {id:'basic-A'})-[:관측]->(:연습센서 {id:'basic-S1'})
RETURN p;

MATCH (p:연습장치 {id:'basic-A'})-[r:관측]->(s:연습센서 {id:'basic-S1'})
DELETE r
RETURN p,s;

MATCH (p:연습장치 {id:'basic-A'}),(s:연습센서 {id:'basic-S1'})
MERGE (p)-[r:관측]->(s)
RETURN p,r,s;

MATCH (s:연습센서 {id:'basic-S1'})
DETACH DELETE s
RETURN count(s) AS removed_sensors;

MATCH (n)
WHERE n:연습장치 OR n:연습센서
RETURN n;

MATCH (n:연습장치)
WHERE n.id IN ['basic-A','basic-B']
DELETE n
RETURN count(n) AS removed_devices;

MATCH (n)
WHERE n:연습장치 OR n:연습센서
RETURN count(n) AS remaining_practice_nodes;
