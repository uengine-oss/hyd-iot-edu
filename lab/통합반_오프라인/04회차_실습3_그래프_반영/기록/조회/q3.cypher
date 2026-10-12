MATCH (f:FailureMode {id: 'fm:cooler-cooling-performance-loss'})-[:MITIGATED_BY]->(k:Skill)-[:HAS_STEP]->(t:Step)-[:REFERS_TO]->(s:ManualSection)-[:PART_OF]->(d:KnowledgeSource)
RETURN k.name AS 조치, t.order AS 순서, t.citation AS 인용, s.ref AS 절, d.ref AS 문서
ORDER BY 조치, 순서;
