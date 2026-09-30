// T3-c KPI와 소유 부서, 전사 목표 기여 가중치: KPI -OWNED_BY-> Department ; KPI -CONTRIBUTES_TO{weight}-> Goal(전사 영업이익)
MATCH (k:KPI)-[:OWNED_BY]->(d:Department)
OPTIONAL MATCH (k)-[c:CONTRIBUTES_TO]->(:Goal {id: 'goal:op-profit'})
RETURN k.id AS id, k.name AS name, k.unit AS unit, d.id AS owner, d.name AS ownerName, coalesce(c.weight, 0.0) AS weight, k.value_per_share AS value_per_share
ORDER BY k.id
