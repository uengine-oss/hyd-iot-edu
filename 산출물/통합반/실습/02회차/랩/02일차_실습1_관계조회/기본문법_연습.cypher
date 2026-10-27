// 위에서부터 한 문장씩 실행합니다. 전체 파일을 한 번에 실행하지 않습니다.
// 준비된 설비와 다른 연습장치·연습센서 레이블을 사용합니다.

// 1. 크리에이트 뒤에 두 노드의 패턴을 적겠습니다. 에이와 비는 이 문장 안에서 각각의 노드를 가리키는 변수입니다. 중괄호 안에는 저장할 속성을 넣었고, 리턴에는 실제로 만들어진 노드의 이름과 점수를 적었습니다.
CREATE (a:연습장치 {id:'basic-A', name:'연습 펌프', score:40}),
       (b:연습장치 {id:'basic-B', name:'연습 팬', score:70})
RETURN a.name AS name, a.score AS score, b.name AS other_name, b.score AS other_score;

// 2. 매치 뒤에 연습장치 레이블을 적고, 리턴 엔으로 찾은 노드를 받을 수 있습니다. 먼저 속성값을 표로 확인할게요. 엔 점 이름과 엔 점 점수를 반환하고, 에이에스로 열 제목을 붙이겠습니다.
MATCH (n:연습장치)
RETURN n.name AS name, n.score AS score
ORDER BY score;

// 3. 같은 매치 문장에 웨어 조건을 넣어 보겠습니다. 점수가 오십 이상인 노드만 고르고, 반환할 열은 그대로 두겠습니다. 앞의 두 행 중에서는 점수가 칠십인 팬이 남아야겠죠.
MATCH (n:연습장치)
WHERE n.score >= 50
RETURN n.name AS name, n.score AS score;

// 4. 조건의 오십을 삼십으로 바꾸겠습니다. 나머지는 그대로입니다. 같은 데이터에 조건 하나만 바꿨을 때 결과가 어떻게 달라지는지 보세요.
MATCH (n:연습장치)
WHERE n.score >= 30
RETURN n.name AS name, n.score AS score
ORDER BY score;

// 5. 이번에는 연습 센서를 등록하겠습니다. 머지에는 변하지 않을 아이디를 넣고, 셋에는 이름과 단위를 넣을게요. 같은 패턴이 있으면 찾아 쓰고, 없으면 만드는 것이 머지입니다.
MERGE (s:연습센서 {id:'basic-S1'})
SET s.name='연습 온도 센서', s.unit='℃'
RETURN s.id AS id, s.name AS name, s.unit AS unit;

// 6. 같은 머지와 셋을 다시 실행하고, 이번에는 등록된 연습 센서 수를 세겠습니다. 뒤의 매치로 연습 센서를 모두 찾고 카운트로 개수를 받겠습니다.
MERGE (s:연습센서 {id:'basic-S1'})
SET s.name='연습 온도 센서', s.unit='℃'
WITH s
MATCH (n:연습센서)
RETURN count(n) AS sensor_count;

// 7. 같은 센서의 이름을 바꿔 보겠습니다. 머지의 아이디는 그대로 두고, 셋의 이름만 연습 유온 센서로 바꾸겠습니다. 이름을 검색 조건에 함께 넣지 않는 점을 보세요.
MERGE (s:연습센서 {id:'basic-S1'})
SET s.name='연습 유온 센서'
RETURN s.id AS id, s.name AS name, s.unit AS unit;

// 8. 매치로 연습 펌프와 센서를 각각 찾고, 두 변수 사이에 관측 관계를 머지하겠습니다. 대괄호 안의 알은 관계 변수이고, 콜론 뒤 관측은 관계 유형입니다.
MATCH (p:연습장치 {id:'basic-A'}), (s:연습센서 {id:'basic-S1'})
MERGE (p)-[r:관측]->(s)
RETURN p.name AS device, type(r) AS relationship, s.name AS sensor;

// 9. 같은 두 노드와 관계를 찾되, 이번에는 이름 대신 피, 알, 에스를 돌려받겠습니다. 노드와 관계 자체를 반환하면 그래프로 읽을 수 있습니다.
MATCH (p:연습장치 {id:'basic-A'})-[r:관측]->(s:연습센서)
RETURN p,r,s;

// 10. 이제 연습 결과를 정리하겠습니다. 화면 카드를 비우는 것과 데이터베이스에서 노드를 지우는 것은 다릅니다. 여기서는 방금 만든 연습장치와 연습센서만 찾아 연결과 함께 삭제하겠습니다. 준비된 설비 데이터는 이 레이블을 쓰지 않습니다.
MATCH (n)
WHERE (n:연습장치 AND n.id IN ['basic-A','basic-B'])
   OR (n:연습센서 AND n.id='basic-S1')
DETACH DELETE n
RETURN count(n) AS removed;
