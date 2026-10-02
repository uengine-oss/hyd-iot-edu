// T3-c — BSC 상충: 스킬 → (AFFECTS) → 상태 변수 · 성과 지표 → (INFLUENCES*) → 처음 닿는 성과 지표   (parameter: $ids)
// dir = 그 성과 지표가 움직이는 방향(+1/-1), good = 성과 지표 방향(UP/DOWN)과 맞는지, weight = 경로 강도의 곱, conds = 경로의 조건.
UNWIND $ids AS sid
MATCH (s:Skill {id: sid})-[a:AFFECTS]->(x)
MATCH p = (x)-[:INFLUENCES*0..4]->(k:Measure)
WHERE all(n IN nodes(p)[0..-1] WHERE NOT n:Measure)
OPTIONAL MATCH (k)-[:OWNED_BY]->(o:OrgUnit)
WITH s, k, o, a.sign * reduce(z = 1, r IN relationships(p) | z * r.sign) AS dir,
     reduce(w = 1.0, r IN relationships(p) | w * CASE r.strength WHEN 'high' THEN 1.0 WHEN 'medium' THEN 0.6 ELSE 0.3 END) AS weight,
     [r IN relationships(p) WHERE r.condition IS NOT NULL | r.condition] AS conds
WITH s, k, o, dir, size(conds) > 0 AS conditional, max(weight) AS weight, head(collect(conds)) AS conds
RETURN s.id AS skill, k.id AS measure, k.name AS name, k.direction AS direction, dir, o.name AS owner,
       (dir = 1) = (k.direction = 'UP') AS good, conditional, weight, conds
ORDER BY skill, measure
