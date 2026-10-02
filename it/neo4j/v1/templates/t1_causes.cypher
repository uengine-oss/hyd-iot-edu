// T1 — 경보 패턴 → 원인 후보 + 증거 규칙   (parameter: $pattern, e.g. 'COOLER_DEGRADATION')
// 원인은 CAUSES 관계의 weight(사전 확률)로 정렬된다. LEADS_TO(연쇄)는 따라가지 않으므로 2차 결과(작동유 열화)는 원인으로 나오지 않는다.
MATCH (p:AnomalyPattern {code: $pattern})-[:DETECTS]->(s:Symptom)-[:INDICATES]->(fm:FailureMode)<-[r:CAUSES]-(c:Cause)
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:Evidence)
OPTIONAL MATCH (fm)-[:OCCURS_IN]->(comp:Component {asset: $asset})
WITH c, fm, r.weight AS prior, collect(DISTINCT s.name) AS symptoms, collect(DISTINCT e) AS evs, head(collect(DISTINCT comp.name)) AS component
RETURN c.id AS causeId, c.name AS cause, c.description AS description,
       fm.id AS failureModeId, fm.name AS failureMode, component,
       prior, symptoms,
       [e IN evs | {id: e.id, name: e.name, weight: e.weight, expect: e.expect, threshold: e.threshold, sql: e.sql}] AS evidence
ORDER BY prior DESC
