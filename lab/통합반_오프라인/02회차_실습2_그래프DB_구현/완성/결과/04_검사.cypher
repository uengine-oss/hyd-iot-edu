// 이 파일은 그래프 DB에 넣은 것이 schema.json 의 정의와 맞는지 보는 검사 질의 6개를 담는다(읽기만 한다).
// 질의마다 적은 「나와야 맞는 것」은 실행해 본 결과가 아니라, graph.json 과 schema.json 을 읽어 세고 따져 본 것이다.
// 검사 1은 수를 낸다. 검사 2부터 6까지는 어긋난 것만 행으로 내므로 0행이면 통과다.

// 검사 1. 레이블별 노드의 수와 관계 유형별 관계의 수는 얼마인가?
// 나와야 맞는 것: 23행(노드 11행, 관계 12행). 노드의 수를 더하면 36, 관계의 수를 더하면 53.
//   노드: Actuator 3, Asset 3, Cause 1, Component 6, FailureMode 1, Part 3, Sensor 5, Skill 1, StateVariable 8, Supplier 3, Symptom 2
//   관계: CAUSES 1, CONTROLS 3, HAS_COMPONENT 18, INDICATES 2, MEASURES 5, MITIGATED_BY 1, MOUNTED_ON 9, OCCURS_IN 1, RELATED_TO 1, SHOWS 2, SUPPLIED_BY 7, USES_PART 3
// 그래프 DB 전체를 세므로, 위에 없는 이름의 행이 나오면 schema.json 에 없는 레이블이나 관계 유형이 들어 있는 것이다.
MATCH (n)
UNWIND labels(n) AS 이름
RETURN '노드' AS 종류, 이름, count(*) AS 수
ORDER BY 이름
UNION ALL
MATCH ()-[r]->()
RETURN '관계' AS 종류, type(r) AS 이름, count(*) AS 수
ORDER BY 이름;

// 검사 2. 같은 id 를 가진 노드가 둘 이상인 곳은 어디인가? (레이블이 달라도 잡는다)
// 나와야 맞는 것: 0행. graph.json 의 노드 36개는 id 가 모두 다르다.
MATCH (n)
WHERE n.id IS NOT NULL
WITH n.id AS id, count(n) AS 노드_수, collect(labels(n)) AS 레이블
WHERE 노드_수 > 1
RETURN id, 노드_수, 레이블
ORDER BY id;

// 검사 3. schema.json 에서 required 가 true 인 속성이 빠진 노드와 관계는 어느 것인가?
// 나와야 맞는 것: 0행. graph.json 의 노드 36개와 SUPPLIED_BY 관계 7개는 필수 속성을 모두 갖고 있다.
// 「빠진」은 속성이 아예 없는 것을 말한다. 빈 문자열은 잡지 않는다. 필수 속성이 있는 관계 유형은 SUPPLIED_BY 뿐이다.
UNWIND [
  {레이블: 'Asset', 필수: ['id', 'name', 'code']},
  {레이블: 'Component', 필수: ['id', 'name']},
  {레이블: 'Sensor', 필수: ['id', 'name', 'tag', 'virtual']},
  {레이블: 'Actuator', 필수: ['id', 'name', 'signal']},
  {레이블: 'StateVariable', 필수: ['id', 'name']},
  {레이블: 'Part', 필수: ['id', 'name', 'part_no']},
  {레이블: 'Symptom', 필수: ['id', 'name']},
  {레이블: 'FailureMode', 필수: ['id', 'name']},
  {레이블: 'Cause', 필수: ['id', 'name']},
  {레이블: 'Skill', 필수: ['id', 'name']},
  {레이블: 'Supplier', 필수: ['id', 'name', 'approved', 'grade']}
] AS 정의
MATCH (n)
WHERE 정의.레이블 IN labels(n)
WITH 정의.레이블 AS 대상, n.id AS 식별, [k IN 정의.필수 WHERE n[k] IS NULL] AS 빠진_속성
WHERE size(빠진_속성) > 0
RETURN '노드' AS 종류, 대상, 식별, 빠진_속성
UNION ALL
MATCH (a)-[r:SUPPLIED_BY]->(b)
WITH a.id + ' -> ' + b.id AS 식별, [k IN ['price', 'fail_rate', 'lead_days'] WHERE r[k] IS NULL] AS 빠진_속성
WHERE size(빠진_속성) > 0
RETURN '관계' AS 종류, 'SUPPLIED_BY' AS 대상, 식별, 빠진_속성;

// 검사 4. 양 끝의 레이블이 schema.json 의 from, to 와 다른 관계는 어느 것인가?
// 나와야 맞는 것: 0행. graph.json 의 관계 53개는 양 끝의 클래스가 모두 from, to 안에 있다.
// schema.json 에 없는 관계 유형은 여기서 잡지 않는다. 그것은 검사 1의 행으로 드러난다.
UNWIND [
  {유형: 'HAS_COMPONENT', 시작: ['Asset'], 끝: ['Component']},
  {유형: 'MOUNTED_ON', 시작: ['Sensor', 'Actuator'], 끝: ['Component']},
  {유형: 'MEASURES', 시작: ['Sensor'], 끝: ['StateVariable']},
  {유형: 'CONTROLS', 시작: ['Actuator'], 끝: ['StateVariable']},
  {유형: 'USES_PART', 시작: ['Component'], 끝: ['Part']},
  {유형: 'SHOWS', 시작: ['Sensor'], 끝: ['Symptom']},
  {유형: 'INDICATES', 시작: ['Symptom'], 끝: ['FailureMode']},
  {유형: 'CAUSES', 시작: ['Cause'], 끝: ['FailureMode']},
  {유형: 'MITIGATED_BY', 시작: ['FailureMode'], 끝: ['Skill']},
  {유형: 'OCCURS_IN', 시작: ['FailureMode'], 끝: ['Component']},
  {유형: 'RELATED_TO', 시작: ['Cause'], 끝: ['Part']},
  {유형: 'SUPPLIED_BY', 시작: ['Part'], 끝: ['Supplier']}
] AS 정의
MATCH (a)-[r]->(b)
WHERE type(r) = 정의.유형
  AND (NOT any(l IN labels(a) WHERE l IN 정의.시작) OR NOT any(l IN labels(b) WHERE l IN 정의.끝))
RETURN type(r) AS 유형, a.id AS 시작_id, labels(a) AS 시작_레이블, b.id AS 끝_id, labels(b) AS 끝_레이블
ORDER BY 유형, 시작_id, 끝_id;

// 검사 5. enum 속성의 값이 schema.json 의 허용값 밖인 노드는 어느 것인가?
// 나와야 맞는 것: 0행. limit_direction 은 sv:ts1 'upper', sv:ps1 'lower', sv:vs1 'upper' 이고, grade 는 sup:a '저가', sup:b '순정', sup:c '최저가' 다.
// limit_direction 은 필수가 아니므로 없는 노드는 통과다. grade 가 없는 노드는 여기가 아니라 검사 3이 잡는다.
MATCH (n:StateVariable)
WHERE n.limit_direction IS NOT NULL AND NOT n.limit_direction IN ['upper', 'lower']
RETURN 'StateVariable' AS 레이블, n.id AS id, 'limit_direction' AS 속성, n.limit_direction AS 값
UNION ALL
MATCH (n:Supplier)
WHERE n.grade IS NOT NULL AND NOT n.grade IN ['저가', '순정', '최저가']
RETURN 'Supplier' AS 레이블, n.id AS id, 'grade' AS 속성, n.grade AS 값;

// 검사 6. schema.json 의 cardinality 가 1:1, N:1, 1:N 인 관계에서 「1」 쪽을 넘겨 이어진 곳은 어디인가? (어긋난 것만 행으로 낸다. 0행이면 통과)
// 나와야 맞는 것: 0행. graph.json 에서는 센서마다 MEASURES 가 하나, 구동기와 상태 변수마다 CONTROLS 가 하나, 부품마다 USES_PART 가 하나,
//   센서와 증상마다 SHOWS 가 하나, 증상마다 INDICATES 가 하나, 고장 유형마다 OCCURS_IN 이 하나를 넘지 않는다.
// cardinality 는 왼쪽이 from 쪽, 오른쪽이 to 쪽이다. 오른쪽이 1이면(N:1, 1:1) from 쪽 노드 하나에서 나가는 관계가 하나를 넘으면 안 되고,
//   왼쪽이 1이면(1:N, 1:1) to 쪽 노드 하나로 들어오는 관계가 하나를 넘으면 안 된다. 1:1 은 양쪽을 다 본다.
// N:M 인 관계(HAS_COMPONENT, MOUNTED_ON, CAUSES, MITIGATED_BY, RELATED_TO, SUPPLIED_BY)는 보지 않는다.
// 수는 관계의 수로 센다. 같은 두 노드 사이에 같은 유형의 관계가 겹쳐 있어도 잡힌다.
UNWIND [
  {유형: 'MEASURES', cardinality: 'N:1'},
  {유형: 'CONTROLS', cardinality: '1:1'},
  {유형: 'USES_PART', cardinality: '1:N'},
  {유형: 'SHOWS', cardinality: '1:1'},
  {유형: 'INDICATES', cardinality: 'N:1'},
  {유형: 'OCCURS_IN', cardinality: 'N:1'}
] AS 정의
MATCH (a)-[r]->(b)
WHERE type(r) = 정의.유형 AND 정의.cardinality IN ['N:1', '1:1']
WITH 정의.유형 AS 유형, 정의.cardinality AS cardinality, a, count(r) AS 관계_수, collect(b.id) AS 이어진_id
WHERE 관계_수 > 1
RETURN 유형, cardinality, 'from 쪽 노드 하나에서 나가는 관계가 여럿' AS 어긋난_곳, a.id AS id, labels(a) AS 레이블, 관계_수, 이어진_id
UNION ALL
UNWIND [
  {유형: 'MEASURES', cardinality: 'N:1'},
  {유형: 'CONTROLS', cardinality: '1:1'},
  {유형: 'USES_PART', cardinality: '1:N'},
  {유형: 'SHOWS', cardinality: '1:1'},
  {유형: 'INDICATES', cardinality: 'N:1'},
  {유형: 'OCCURS_IN', cardinality: 'N:1'}
] AS 정의
MATCH (a)-[r]->(b)
WHERE type(r) = 정의.유형 AND 정의.cardinality IN ['1:N', '1:1']
WITH 정의.유형 AS 유형, 정의.cardinality AS cardinality, b, count(r) AS 관계_수, collect(a.id) AS 이어진_id
WHERE 관계_수 > 1
RETURN 유형, cardinality, 'to 쪽 노드 하나로 들어오는 관계가 여럿' AS 어긋난_곳, b.id AS id, labels(b) AS 레이블, 관계_수, 이어진_id;
