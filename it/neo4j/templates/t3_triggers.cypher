// T3-e 경보·원인에서 판단 시나리오 찾기: (Cause | AnomalyPattern) -TRIGGERS_DECISION-> Scenario
MATCH (x)-[:TRIGGERS_DECISION]->(s:Scenario) WHERE x.id IN $ids
RETURN DISTINCT s.id AS id, s.name AS name, x.id AS trigger ORDER BY s.id
