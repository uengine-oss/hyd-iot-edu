MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)-[:OBSERVES]->(q:Quantity)
WHERE $quantity = '' OR q.name = $quantity
RETURN a.id AS asset, c.id AS component, s.id AS sensor, s.tag AS tag, s.kind AS kind, q.name AS quantity, s.unit AS unit, s.normal AS normal, s.limit AS limit, s.limit_direction AS direction ORDER BY asset,component,sensor
