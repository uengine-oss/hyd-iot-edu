MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p:Part)
WHERE (p.id = $part OR $part IN coalesce(p.other_codes, [])) AND a.status = '가동'
RETURN p.id AS part, a.id AS asset, c.id AS component, c.name AS component_name ORDER BY asset, component
