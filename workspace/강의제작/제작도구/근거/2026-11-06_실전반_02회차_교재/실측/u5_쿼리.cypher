MATCH (x:StateVariable)-[r:INFLUENCES]->(:StateVariable {id: 'sv:ts1'}) WHERE r.sign = -1 RETURN x.name ORDER BY x.name;
MATCH (d:Actuator)-[:MANIPULATES]->(x:StateVariable)-[r:INFLUENCES]->(:StateVariable {id: 'sv:ts1'}) WHERE r.sign = -1 RETURN d.name, x.name;
MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor {id: 'sen:ts1'}) RETURN count(*) AS rows, count(DISTINCT s) AS sensors;
MATCH (a:Asset {id: 'asset:hyd-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor) RETURN c.name AS component, count(DISTINCT s) AS sensors ORDER BY sensors DESC, component;
MATCH (a:Asset {id: 'asset:hyd-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)-[:OBSERVES]->(v:StateVariable) WHERE (c.id = 'comp:cooler' OR c.id = 'comp:fan') AND v.limit IS NOT NULL RETURN c.name, s.tag, v.name, v.limit ORDER BY s.tag;
MATCH (a:Asset {id: 'asset:hyd-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)-[:OBSERVES]->(v:StateVariable) WHERE c.id = 'comp:cooler' OR c.id = 'comp:fan' AND v.limit IS NOT NULL RETURN c.name, s.tag, v.name, v.limit ORDER BY s.tag;
MATCH (c:Component {id: 'comp:cooler'})-[r:MONITORED_BY]->(s:Sensor) RETURN c.name, s.tag;
