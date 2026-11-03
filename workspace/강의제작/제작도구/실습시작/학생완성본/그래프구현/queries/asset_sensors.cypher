MATCH (a:Asset)-[:HAS_COMPONENT*0..1]->(x)-[:MONITORED_BY]->(s:Sensor)-[:OBSERVES]->(q:Quantity)
WHERE $asset = '' OR a.id = $asset
RETURN a.id AS asset, CASE WHEN x = a THEN '(설비 전체)' ELSE x.id END AS attached_to, s.id AS sensor, s.tag AS tag, s.kind AS kind, q.name AS quantity, s.unit AS unit, s.normal AS normal, s.limit AS limit, s.limit_direction AS direction ORDER BY asset, attached_to, sensor
