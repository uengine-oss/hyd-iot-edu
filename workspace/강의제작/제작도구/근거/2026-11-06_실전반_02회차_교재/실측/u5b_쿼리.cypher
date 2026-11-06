MATCH (x:StateVariable)-[r:INFLUENCES]->(:StateVariable {id: 'sv:ts1'}) WHERE r.sign = 1 RETURN x.name ORDER BY x.name;
MATCH (d:Actuator)-[:MANIPULATES]->(x:StateVariable)-[r:INFLUENCES]->(:StateVariable {id: 'sv:ts1'}) WHERE r.sign = 1 RETURN d.name, x.name ORDER BY x.name;
MATCH (c:Component {id: 'comp:cooler'})-[:MONITORED_BY]->(s:Sensor) RETURN c.name;
MATCH (c:Component {id: 'comp:cooler'})-[:MONITORED_BY]->(s:Sensor) RETURN DISTINCT c.name;
MATCH (c:Component {id: 'comp:cooler'})-[:MONITORED_BY]->(s:Sensor) RETURN DISTINCT c.name, s.tag;
MATCH (a:Asset {id: 'asset:hyd-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor) RETURN c.id AS componentId, c.name AS component, count(DISTINCT s) AS sensors ORDER BY sensors DESC, componentId;
MATCH (a:Asset {id: 'asset:hyd-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)-[:OBSERVES]->(v:StateVariable) WHERE (c.id = 'comp:cooler' OR c.id = 'comp:fan') AND v.limit IS NOT NULL RETURN c.name, s.tag, v.name, v.unit, v.limit ORDER BY s.tag;
MATCH (x:StateVariable)-[r:INFLUENCES]->(:StateVariable {id: 'sv:ts1'}) RETURN x.id, x.name, x.kind, r.sign ORDER BY x.id;
MATCH (d:Actuator)-[:MANIPULATES]->(x:StateVariable) RETURN d.id, d.name, x.id, x.name;
