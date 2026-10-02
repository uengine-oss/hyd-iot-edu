// T1 — 경보 패턴 → 증상 → 고장 유형 → 원인 후보 + 증거 규칙   (parameter: $pattern e.g. 'COOLER_DEGRADATION', $asset e.g. 'HYD-01')
// 원인은 사전 확률(prior)로 정렬한다. 증거는 시계열 DB에서 실행할 SQL과 비교 방향 · 임계값을 함께 돌려준다.
MATCH (p:AnomalyPattern {code: $pattern})-[:DETECTS]->(s:Symptom)-[:INDICATES]->(fm:FailureMode)<-[:CAUSES]-(c:Cause)
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:Evidence)
OPTIONAL MATCH (fm)-[:OCCURS_IN]->(comp:Component)
WITH c, fm, collect(DISTINCT s.name) AS symptoms, collect(DISTINCT e) AS evs, head(collect(DISTINCT comp.name)) AS component
RETURN c.id AS causeId, c.name AS cause, null AS description,
       fm.id AS failureModeId, fm.name AS failureMode, component,
       c.prior AS prior, symptoms,
       [e IN evs | {id: e.id, name: e.name, weight: e.weight, expect: e.expect, threshold: e.threshold, sql: e.sql}] AS evidence
ORDER BY prior DESC
