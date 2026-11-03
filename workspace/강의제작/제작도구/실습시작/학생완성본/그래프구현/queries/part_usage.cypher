OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])
OPTIONAL MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p)
RETURN p.id AS part, a.id AS asset, a.status AS status, c.id AS component, c.name AS component_name,
       CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN a IS NULL THEN '쓰는 설비 없음' END AS note ORDER BY part, asset, component
