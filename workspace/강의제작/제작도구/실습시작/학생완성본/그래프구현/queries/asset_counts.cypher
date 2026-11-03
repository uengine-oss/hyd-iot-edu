MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)
OPTIONAL MATCH (c)-[:MONITORED_BY]->(s:Sensor)
RETURN a.id AS asset, count(DISTINCT c) AS components, count(DISTINCT s) AS sensors ORDER BY asset
