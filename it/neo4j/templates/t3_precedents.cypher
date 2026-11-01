// T3-e — 선례 (parameter: $failureMode): 같은 고장 유형의 사건에서 사람이 고른 스킬과 사유 (DecisionCase -CHOSE-> Skill)
// 교육용 고정: 미리 넣은 예시 사례(seeded = true)만 센다 — 승인할 때마다 순위가 바뀌지 않게. 수업 그래프에는 그런 사례가 없어 늘 빈 결과다.
MATCH (dc:DecisionCase)-[:FOR_INCIDENT]->(:Incident)-[:DIAGNOSED_AS]->(:Cause)-[:CAUSES]->(:FailureMode {id: $failureMode})
WHERE dc.seeded = true
MATCH (dc)-[:CHOSE]->(s:Skill)
RETURN s.id AS skill, count(*) AS n, collect(dc.reason)[0..5] AS reasons
