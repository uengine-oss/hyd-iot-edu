// T3-b — DMN 판단 정의: 판단 → 결정표 → 규칙 → 임계값 검사(TESTS) · 출력 · 적용 대상 · 근거   (no parameters)
// 에이전트는 이 규칙들을 사실(facts)에 대어 후보 선택(SELECT) · 제외(EXCLUDE) · 감점(PENALTY) · 경고(WARN)를 판정한다.
MATCH (d:Decision)-[:IMPLEMENTED_BY]->(t:DecisionTable)-[:HAS_RULE]->(r:Rule)
RETURN d.id AS decision, d.name AS decisionName, d.question AS question, t.id AS table, t.hitPolicy AS hitPolicy,
       r.id AS rule, r.order AS ord, r.effect AS effect, r.penalty AS penalty, r.when AS when, r.annotation AS annotation,
       COLLECT { MATCH (r)-[x:TESTS]->(i:InputData) RETURN {input: i.id, variable: i.variable, operator: x.operator, value: x.value, unit: x.unit} } AS tests,
       COLLECT { MATCH (r)-[:OUTPUTS]->(o) RETURN o.id } AS outputs,
       COLLECT { MATCH (r)-[:APPLIES_TO]->(s:Skill) RETURN s.id } AS applies,
       COLLECT { MATCH (r)-[:PENALIZES]->(k:Measure) RETURN k.id } AS penalizes,
       COLLECT { MATCH (r)-[:DERIVED_FROM]->(src) RETURN coalesce(src.ref, src.id) } AS sources
ORDER BY decision, ord
