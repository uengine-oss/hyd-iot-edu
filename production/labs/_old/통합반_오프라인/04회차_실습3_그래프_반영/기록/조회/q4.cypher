MATCH (k:Skill)-[r:REFERS_TO]->(s:ManualSection)
WHERE r.kind IS NOT NULL
RETURN k.name AS 조치, r.kind AS 구분, r.text AS 내용, s.ref AS 절
ORDER BY 조치;
