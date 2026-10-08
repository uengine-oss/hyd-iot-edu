// T3-p (B5 What-if 관점 중요도): BSC 관점과 그 관점에 속한 성과 지표. 읽기만.
// Measure -MEASURES-> Objective -IN_PERSPECTIVE-> Perspective
MATCH (p:Perspective)
OPTIONAL MATCH (m:Measure)-[:MEASURES]->(:Objective)-[:IN_PERSPECTIVE]->(p)
RETURN p.id AS id, p.name AS name, p.order AS ord, collect(DISTINCT m.id) AS measures
ORDER BY ord DESC, id
