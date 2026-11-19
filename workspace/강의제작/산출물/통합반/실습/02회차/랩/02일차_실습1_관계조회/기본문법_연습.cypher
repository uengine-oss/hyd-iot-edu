// 안내 문서의 쿼리를 절 번호 · 칸 차례대로 담았습니다. Neo4j Browser 입력칸에서 한 칸씩 돌립니다.
// 2-1의 CREATE는 한 번만 돌립니다. 다시 돌리면 같은 노드가 둘 더 생깁니다.

// 2-1
CREATE (a:연습장치 {id:'basic-A', name:'연습 펌프', score:40}),
       (b:연습장치 {id:'basic-B', name:'연습 팬', score:70});

// 3-1
MATCH (n:연습장치)
RETURN n;

// 3-2
MATCH (n:연습장치)
RETURN n.name AS 이름, n.score AS 점수
ORDER BY 점수;

// 4-1
MATCH (n:연습장치)
WHERE n.score >= 50
RETURN n;

// 5-1
MERGE (s:연습센서 {id:'basic-S1'})
SET s.name = '연습 온도 센서', s.unit = '℃'
RETURN s;

// 5-2
MERGE (s:연습센서 {id:'basic-S1'})
SET s.name = '연습 온도 센서', s.unit = '℃'
RETURN s;

// 5-3
MATCH (p:연습장치 {id:'basic-A'})
MATCH (s:연습센서 {id:'basic-S1'})
MERGE (p)-[r:감시된다]->(s)
RETURN p, r, s;

// 6-1
MATCH (p:연습장치 {id:'basic-A'})-[r:감시된다]->(s:연습센서 {id:'basic-S1'})
SET s.name = '연습 유온 센서'
RETURN p, r, s;

// 7-1
MATCH (p:연습장치 {id:'basic-A'})
DETACH DELETE p;

// 7-2
MATCH (n:연습장치|연습센서)
RETURN n;

// 7-3
MATCH (n:연습장치|연습센서)
DELETE n;

// 7-4
MATCH (n:연습장치|연습센서)
RETURN count(n) AS 남은수;

// 8-1
MATCH (n)
RETURN labels(n) AS 레이블, count(n) AS 개수
ORDER BY 개수 DESC;

// 9-1
MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)
RETURN c.name AS 구성요소;

// 10-1
MATCH path = (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(:Component)-[:USES_PART]->(:Part)
RETURN path;

// 10-2
MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p:Part)
WHERE c.name = '오일 쿨러'
RETURN c.name AS 구성요소, p.name AS 부품, p.partNo AS 품번;

// 11-1
MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)
RETURN c.name AS 구성요소, s.name AS 센서, s.virtual AS 가상
ORDER BY 구성요소, 센서;

// 11-2
MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)
WHERE s.virtual = false
RETURN c.name AS 구성요소, s.name AS 센서, s.virtual AS 가상
ORDER BY 구성요소, 센서;

// 11-3
MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)
RETURN c.name AS 구성요소, count(s) AS 센서수, collect(s.name) AS 센서목록
ORDER BY 센서수 DESC, 구성요소;
