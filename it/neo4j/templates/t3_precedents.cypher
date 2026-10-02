// T3-e — 선례 (parameter: $failureMode): 같은 고장 유형의 사건에서 사람이 고른 스킬과 사유 (DecisionCase -CHOSE-> Skill)
MATCH (dc:DecisionCase)-[:FOR_INCIDENT]->(:Incident)-[:DIAGNOSED_AS]->(:Cause)-[:CAUSES]->(:FailureMode {id: $failureMode})
MATCH (dc)-[:CHOSE]->(s:Skill)
RETURN s.id AS skill, count(*) AS n, collect(dc.reason)[0..5] AS reasons
