MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p:Part)
WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])
RETURN p.id AS part, a.id AS asset, a.status AS status, c.id AS component, c.name AS component_name ORDER BY asset, component
