MATCH (c:Component)-[:USES_PART]->(p:Part) WITH p, count(DISTINCT c) AS comps WHERE comps > 1 RETURN p.id, comps;
MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor) RETURN count(*) AS rows, count(DISTINCT a) AS assets, count(DISTINCT c) AS comps, count(DISTINCT s) AS sensors;
MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p:Part) RETURN count(*) AS rows, count(DISTINCT a) AS assets, count(DISTINCT p) AS parts;
