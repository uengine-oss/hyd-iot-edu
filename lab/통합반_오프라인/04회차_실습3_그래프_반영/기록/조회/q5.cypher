MATCH (k:Skill)
WHERE NOT (:FailureMode)-[:MITIGATED_BY]->(k)
RETURN k.id AS id, k.name AS 조치, k._manual_document AS 문서
ORDER BY id;
