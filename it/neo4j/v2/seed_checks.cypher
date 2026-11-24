// kg-seed 되읽기 검사 — seed.sh가 적재 직후 한 줄씩 실행한다(시작할 때마다).
// 규약: 주석 아닌 줄 하나가 질의 하나이며 「문제가 있는 노드 · 관계」를 problem 열로 돌려준다. 한 줄이라도 행을 돌려주거나 질의가 실패하면 kg-seed가 실패한다.
// 전체 스키마 검사(속성 · 끝점 · 다중도)는 workspace/개발/scripts/ontology_v2.py validate(개발 PC)가 한다. 여기는 컨테이너(cypher-shell만 있음)에서
// 「kg-seed가 넣은 기준 데이터가 그대로 들어갔는가」와 「판단이 읽는 결정표 규칙의 꼴」을 재는 단언이다.
// 문서 적재 · 조치 방법 화면이 넣은 지식(고장 유형 · 원인 · 조치 방법과 그 연결)은 여기서 단언하지 않는다 — 그 꼴은 쓰는 곳이 쓸 때 지키고(manual_review.validate ·
// manual_graph.commit · skill_graph.write), 바깥에서 고친 것은 그 문서의 다음 개정 · 되돌리기가 적재 기록과 대조해 짚는다. 학생이 포털로 넣은 지식 하나가
// 다음 시작(kg-seed 성공에 기대는 agent · dmn-mcp)을 멈추게 하지 않는다. 학생 이름 공간 노드(ns가 있는 노드, 업무 스키마 실습)도 같은 까닭으로 보지 않는다.
MATCH (n) WITH collect(DISTINCT labels(n)) AS have UNWIND ['Action','Actuator','AnomalyPattern','Asset','Component','Decision','DecisionTable','ExternalVariable','InputData','KnowledgeSource','Measure','Objective','OrgUnit','Part','Perspective','Process','Role','Rule','Sensor','StateVariable','Symptom','System'] AS want WITH want, [l IN have WHERE want IN l] AS hit WHERE size(hit) = 0 RETURN 'empty label ' + want AS problem
MATCH (m:Measure) WHERE m.ns IS NULL AND (m.kpiRole IS NULL OR m.direction IS NULL OR m.unit IS NULL) RETURN 'measure without kpiRole/direction/unit ' + m.id AS problem
MATCH (a:Measure {kpiRole:'lagging'})-[:INFLUENCES]->(b:Measure {kpiRole:'leading'}) WHERE a.ns IS NULL AND b.ns IS NULL RETURN 'lagging influences leading ' + a.id + ' -> ' + b.id AS problem
MATCH (m:Measure {kpiRole:'leading'}) WHERE m.ns IS NULL AND NOT EXISTS { (m)-[:INFLUENCES*1..6]->(:Measure {kpiRole:'lagging'}) } RETURN 'leading measure reaches no lagging measure ' + m.id AS problem
MATCH (o:Objective) WHERE o.ns IS NULL AND NOT (o)-[:IN_PERSPECTIVE]->(:Perspective) RETURN 'objective without perspective ' + o.id AS problem
MATCH (m:Measure) WHERE m.ns IS NULL AND (NOT (m)-[:MEASURES]->(:Objective) OR NOT (m)-[:OWNED_BY]->(:OrgUnit)) RETURN 'measure without objective/owner ' + m.id AS problem
// 수업 시나리오 A가 기대는 설비 패턴: 감지기가 직접 감지하는 셋(held)과 PLC 보호 정지 셋(plc-trip). 하나라도 없거나 감지 방식이 다르면 실패한다.
UNWIND [['COOLER_DEGRADATION','held'],['PUMP_LEAKAGE','held'],['FAN_VIBRATION','held'],['OVERHEAT_TRIP','plc-trip'],['LOW_PRESSURE_TRIP','plc-trip'],['HIGH_VIBRATION_TRIP','plc-trip']] AS e OPTIONAL MATCH (p:AnomalyPattern {code: e[0]}) WITH e, p WHERE p IS NULL OR coalesce(p.detectionMode, '(없음)') <> e[1] RETURN 'course equipment pattern ' + e[0] + ' is missing or not ' + e[1] AS problem
// 감지기가 실행하는 패턴(held)은 해제 조건 · 유지 시간 · 경사 창 · 심각도가 모두 있어야 한다(it/detector/det/patterns.compile_pattern이 같은 계약을 검사한다).
MATCH (p:AnomalyPattern {detectionMode:'held'}) WHERE p.ns IS NULL AND (p.clearRule IS NULL OR p.holdSeconds IS NULL OR p.clearHoldSeconds IS NULL OR p.slopeWindowSeconds IS NULL OR p.severity IS NULL) RETURN 'held pattern without full detector contract ' + p.id AS problem
// 사람이 읽는 패턴 조건(rule)은 TESTS 행에서 만든다 — 판단 입력 id가 틀려 TESTS가 빠지면 문장의 조건 수와 TESTS 수가 달라져 여기서 잡힌다.
MATCH (p:AnomalyPattern) WHERE p.ns IS NULL OPTIONAL MATCH (p)-[t:TESTS]->(:InputData) WITH p, collect(t) AS ts WITH p, ts, split(split(coalesce(p.rule, ''), ' (')[0], ' and ') AS atoms WHERE size(ts) = 0 OR size(atoms) <> size(ts) OR any(t IN ts WHERE NOT p.rule CONTAINS (t.operator + ' ' + CASE WHEN t.value IS :: STRING THEN "'" + t.value + "'" ELSE toString(t.value) END)) RETURN 'pattern rule does not state exactly its TESTS ' + p.id + ': ' + coalesce(p.rule, '(없음)') AS problem
// 이상 패턴은 임계값의 근거 출처(수업 문서 절을 가리키는 기준 · 감시 임계값 회사 설정값 · 정기 정비 계획 기준)를 가진다 — 규칙이 원문 절을 가리키듯 감지 기준도 어디서 왔는지 그래프로 보인다.
MATCH (p:AnomalyPattern) WHERE p.ns IS NULL AND NOT (p)-[:DERIVED_FROM]->(:KnowledgeSource) RETURN 'pattern without source ' + p.id AS problem
// 설비 패턴은 증상까지 이어져 있어야 수업 문서가 증상 → 고장 유형을 이을 수 있다(업무 표 감시 패턴 PM_DUE · SPARE_BELOW_MIN은 설비 증상이 아니라 잇지 않는다).
MATCH (p:AnomalyPattern) WHERE p.ns IS NULL AND p.detectionMode IN ['held','plc-trip'] AND NOT EXISTS { (p)-[:DETECTS]->(:Symptom) } RETURN 'equipment pattern without symptom ' + p.id AS problem
// 판단 규칙: 결정표 안에 있고, 검사하는 입력은 그 판단이 선언한 입력이며, 사람이 읽는 조건(when)이 TESTS 그대로다. 판단은 모든 규칙을 읽으므로 이 셋은 모든 규칙에 건다 —
// 시드 · 문서 적재(manual_knowledge.desired · when_text) · 조치 방법 화면(skill_graph.ensure_candidate_rule)이 모두 이 꼴로 쓰므로 바깥에서 고친 규칙만 걸린다.
// when의 값은 글자가 아니라 값으로 견준다: 문서 값 0.0005를 파이썬은 '0.0005'로, Cypher toString은 '5.0E-4'로 적는다(같은 값을 다른 글로 적어 시작이 멈추던 것).
MATCH (r:Rule) WHERE r.ns IS NULL AND NOT (:DecisionTable)-[:HAS_RULE]->(r) RETURN 'rule outside a decision table ' + r.id AS problem
MATCH (d:Decision) WHERE d.ns IS NULL AND NOT (d)-[:IMPLEMENTED_BY]->(:DecisionTable) RETURN 'decision without table ' + d.id AS problem
MATCH (d:Decision)-[:IMPLEMENTED_BY]->(:DecisionTable)-[:HAS_RULE]->(r:Rule)-[:TESTS]->(i:InputData) WHERE r.ns IS NULL AND NOT (d)-[:REQUIRES_INPUT]->(i) RETURN 'rule ' + r.id + ' tests ' + i.id + ' that ' + d.id + ' does not require' AS problem
MATCH (r:Rule) WHERE r.ns IS NULL OPTIONAL MATCH (r)-[t:TESTS]->(i:InputData) WITH r, collect({t: t, v: i.variable}) AS ts WITH r, [x IN ts WHERE x.t IS NOT NULL] AS ts WHERE (size(ts) = 0 AND coalesce(r.when, '') <> 'true') OR (size(ts) > 0 AND (size(split(coalesce(r.when, ''), ' and ')) <> size(ts) OR any(x IN ts WHERE NOT any(a IN split(r.when, ' and ') WHERE a STARTS WITH (x.v + ' ' + x.t.operator + ' ') AND coalesce(CASE WHEN x.t.value IS :: STRING THEN substring(a, size(x.v + ' ' + x.t.operator + ' ')) = "'" + x.t.value + "'" WHEN x.t.value IS :: BOOLEAN THEN substring(a, size(x.v + ' ' + x.t.operator + ' ')) = toString(x.t.value) ELSE toFloat(substring(a, size(x.v + ' ' + x.t.operator + ' '))) = toFloat(x.t.value) END, false))))) RETURN 'rule when does not state exactly its TESTS ' + r.id + ': ' + coalesce(r.when, '(없음)') AS problem
// 순위 결정표에는 실행되는 순위 정책이 정확히 하나다(agent cards.ranking_rule이 UNIQUE로 요구한다).
MATCH (:DecisionTable {id:'dt:rank-actions'})-[:HAS_RULE]->(r:Rule) WITH count(CASE WHEN r.rankingPolicy IS NOT NULL THEN 1 END) AS n WHERE n <> 1 RETURN 'rank-actions table must hold exactly one ranking policy, has ' + toString(n) AS problem
MATCH (a:Asset) WHERE a.ns IS NULL AND (a.forecastModel IS NULL OR a.forecastRevision IS NULL OR a.forecastHorizonS IS NULL) RETURN 'asset without explicit forecast model binding ' + a.id AS problem
MATCH (p:Process) WHERE p.ns IS NULL AND (NOT (p)-[:ACHIEVES]->(:Objective) OR NOT (p)-[:ACTS_ON]->(:Asset)) RETURN 'process without objective/asset ' + p.id AS problem
// 업무 흐름의 정본은 실행 정의다 — 그래프의 흐름 노드는 처리 엔진이 배포 판본(ProcessVersion)에서 투영한 것뿐이어야 한다(손으로 쓴 흐름 사본 금지).
MATCH (n:FlowNode) WHERE n.ns IS NULL AND NOT EXISTS { (:ProcessVersion)-[:HAS_NODE]->(n) } RETURN 'flow node outside a deployed process version ' + n.id AS problem
