// T3-d 규정: Policy -GOVERNS-> Skill (그 스킬을 쓰는 대안에 적용) | Scenario (시나리오 전체에 적용)
MATCH (p:Policy)
RETURN p.id AS id, p.name AS name, p.kind AS kind, p.expr AS expr, p.penalty AS penalty, p.kpi AS kpi, p.source AS source,
       COLLECT { MATCH (p)-[:GOVERNS]->(k:Skill) RETURN k.id } AS skills,
       EXISTS { MATCH (p)-[:GOVERNS]->(:Scenario {id: $scenario}) } AS scenarioScope
ORDER BY p.id
