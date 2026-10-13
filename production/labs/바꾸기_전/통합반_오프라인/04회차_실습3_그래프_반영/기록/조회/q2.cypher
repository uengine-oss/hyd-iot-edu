MATCH (f:FailureMode {id: 'fm:cooler-cooling-performance-loss'})<-[c:CAUSES]-(k:Cause)-[:REFERS_TO]->(s:ManualSection)-[:PART_OF]->(d:KnowledgeSource)
RETURN k.name AS 원인, c.source AS 관계의_출처, s.ref AS 절, s.title AS 절_제목, d.name AS 문서
ORDER BY 원인;
