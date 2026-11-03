MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)
WHERE $asset = '' OR a.id = $asset
OPTIONAL MATCH (c)-[:USES_PART]->(p:Part)
RETURN a.id AS asset, c.id AS component, c.name AS component_name, p.id AS part, p.name AS part_name ORDER BY asset, component
