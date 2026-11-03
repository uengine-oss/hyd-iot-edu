OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])
OPTIONAL MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p) WHERE a.status = '가동'
OPTIONAL MATCH (x:Asset)-[:HAS_COMPONENT]->(:Component)-[:USES_PART]->(p) WHERE x.status <> '가동'
WITH p, a, c, collect(DISTINCT x.id + ' ' + x.status) AS not_running
RETURN p.id AS part, a.id AS asset, c.id AS component, c.name AS component_name,
       CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN a IS NULL THEN '지금 가동하는 설비에서는 쓰지 않음' END AS note,
       not_running ORDER BY part, asset, component
