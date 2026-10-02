// 시나리오 목록 (포탈 메뉴용)
MATCH (s:Scenario)
OPTIONAL MATCH (t)-[:TRIGGERS_DECISION]->(s)
WITH s, collect(DISTINCT {id: t.id, name: t.name}) AS triggers
RETURN s {.*} AS scenario, triggers, COUNT { (s)-[:HAS_OPTION]->() } AS options
ORDER BY scenario.no
