// kg-seed 되읽기 검사 (A144, O04 "seed 뒤 되읽기 단언"). seed.sh가 적재 직후 한 줄씩 실행한다.
// 규약: 각 줄은 질의 하나이며 "문제가 있는 노드·관계"를 problem 열로 돌려준다. 한 줄이라도 행을 돌려주면 seed.sh는 실패(exit 1)한다.
// 전체 스키마 검사는 scripts/ontology_v2.py validate(파이썬, 호스트)가 한다. 여기는 컨테이너(cypher-shell만 있음)에서
// 적재가 끝까지 들어갔는지 보는 최소 단언이다: 시드 파일이 MERGE하는 모든 레이블이 비어 있지 않고, 수업 시나리오가 기대는 연결이 있다.
// 아래 레이블 목록은 tests/test_ontology_schema.py가 instances.cypher·knowledge_a098.cypher의 MERGE 레이블과 대조한다(빠지면 시험 실패).
MATCH (n) WITH collect(DISTINCT labels(n)) AS have UNWIND ['Action','Actuator','AnomalyPattern','Asset','Cause','Component','Decision','DecisionCase','DecisionTable','Event','Evidence','ExternalVariable','FailureMode','FlowNode','Forecast','Gateway','Incident','InputData','KnowledgeSource','ManualSection','Measure','Objective','OrgUnit','Part','Perspective','Process','Role','Rule','Sensor','Skill','StateVariable','Step','Supplier','Symptom','System','Task'] AS want WITH want, [l IN have WHERE want IN l] AS hit WHERE size(hit) = 0 RETURN 'empty label ' + want AS problem
MATCH (m:Measure) WHERE m.kpiRole IS NULL OR m.direction IS NULL OR m.unit IS NULL RETURN 'measure without kpiRole/direction/unit ' + m.id AS problem
MATCH (a:Measure {kpiRole:'lagging'})-[:INFLUENCES]->(b:Measure {kpiRole:'leading'}) RETURN 'lagging influences leading ' + a.id + ' -> ' + b.id AS problem
MATCH (m:Measure {kpiRole:'leading'}) WHERE NOT EXISTS { (m)-[:INFLUENCES*1..6]->(:Measure {kpiRole:'lagging'}) } RETURN 'leading measure reaches no lagging measure ' + m.id AS problem
MATCH (o:Objective) WHERE NOT (o)-[:IN_PERSPECTIVE]->(:Perspective) RETURN 'objective without perspective ' + o.id AS problem
MATCH (m:Measure) WHERE NOT (m)-[:MEASURES]->(:Objective) OR NOT (m)-[:OWNED_BY]->(:OrgUnit) RETURN 'measure without objective/owner ' + m.id AS problem
MATCH (f:FailureMode) WHERE NOT (f)-[:MITIGATED_BY|REMEDIED_BY]->(:Skill) AND NOT (:Cause)-[:CAUSES]->(f) RETURN 'failure mode with neither skill nor cause ' + f.id AS problem
MATCH (k:Skill) WHERE NOT (k)-[:HAS_STEP]->(:Step) RETURN 'skill without steps ' + k.id AS problem
MATCH (k:Skill) WHERE NOT (:FailureMode)-[:MITIGATED_BY|REMEDIED_BY]->(k) RETURN 'skill not matched to a failure mode ' + k.id AS problem
MATCH (r:Rule) WHERE NOT (:DecisionTable)-[:HAS_RULE]->(r) RETURN 'rule outside a decision table ' + r.id AS problem
MATCH (d:Decision) WHERE NOT (d)-[:IMPLEMENTED_BY]->(:DecisionTable) RETURN 'decision without table ' + d.id AS problem
MATCH (p:AnomalyPattern) WHERE NOT EXISTS { (p)-[:DETECTS]->(:Symptom)-[:INDICATES]->(:FailureMode) } RETURN 'pattern not linked to a failure mode ' + p.id AS problem
MATCH (c:Cause) WHERE NOT (c)-[:CAUSES]->(:FailureMode) RETURN 'cause without failure mode ' + c.id AS problem
MATCH (a:Asset) WHERE a.forecastModel IS NULL OR a.forecastRevision IS NULL OR a.forecastHorizonS IS NULL RETURN 'asset without explicit forecast model binding ' + a.id AS problem
MATCH (p:Process) WHERE NOT (p)-[:ACHIEVES]->(:Objective) OR NOT (p)-[:ACTS_ON]->(:Asset) RETURN 'process without objective/asset ' + p.id AS problem
// A156: the detector needs held patterns (detector-patterns.cypher); none means a fresh volume would start it unhealthy
MATCH (p:AnomalyPattern) WITH count(CASE WHEN p.detectionMode = 'held' THEN 1 END) AS held WHERE held = 0 RETURN 'no held AnomalyPattern: detector-patterns.cypher not loaded' AS problem
// B4 (DECISIONS 110 ④): 선례 조회는 seeded=true 사례만 센다 — 시드 선례가 하나도 표시되지 않았으면 선례 몫이 모두 0이 된다
MATCH (c:DecisionCase) WHERE c.seeded = true WITH count(c) AS n WHERE n = 0 RETURN 'no seeded DecisionCase (precedent query would count nothing)' AS problem
