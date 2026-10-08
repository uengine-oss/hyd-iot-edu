// T3-e — 선례 (parameter: $failureMode): 같은 고장 유형의 사건에서 사람이 고른 스킬과 사유 (DecisionCase -CHOSE-> Skill)
MATCH (dc:DecisionCase)-[:FOR_INCIDENT]->(:Incident)-[:DIAGNOSED_AS]->(:Cause)-[:CAUSES]->(:FailureMode {id: $failureMode})
// 교육용 고정: 시드 선례만 센다. 이 조건을 빼면 승인할 때마다 선례가 쌓이는 학습(제품 동작)이 켜진다 — DECISIONS 110 ④
WHERE dc.seeded = true
MATCH (dc)-[:CHOSE]->(s:Skill)
RETURN s.id AS skill, count(*) AS n, collect(dc.reason)[0..5] AS reasons
