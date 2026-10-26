// 설비별 센서
MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:MONITORED_BY]->(s:Sensor)
RETURN a.id AS asset, collect(s.tag) AS sensors, count(s) AS count;

// 부품별 사용 설비
MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:USES_PART]->(p:Part)
RETURN p.id AS part, collect(DISTINCT a.id) AS assets;
