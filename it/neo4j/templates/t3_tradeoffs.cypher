// T3-c — 후보 스킬마다 성과 지표 득실 경로(parameter: $ids 스킬 id 목록): AFFECTS 하나 뒤 INFLUENCES 최대 4개, 처음 닿는 성과 지표에서 멈춘다.
// 경로를 하나씩 그대로 돌려준다(합치지 않는다): 방향 dir = 부호의 곱, weight = 강도의 곱(high 1 · medium 0.6 · low 0.3, 모르는 강도면 null).
// 조건이 붙은 관계가 있으면 conditional — 조건은 판정할 해석이 없어 「미확인」 영향으로 남고 점수에서 조건부(절반)로 센다(hydcommon.bsc).
UNWIND $ids AS sid
MATCH (s:Skill {id: sid})-[a:AFFECTS]->(x)
MATCH p = (x)-[:INFLUENCES*0..4]->(k:Measure)
WHERE all(n IN nodes(p)[0..-1] WHERE NOT n:Measure)
OPTIONAL MATCH (k)-[:OWNED_BY]->(o:OrgUnit)
WITH s,a,p,k,collect(DISTINCT o.name) AS owners
WITH s,a,p,k,owners,a.sign * reduce(z=1,r IN relationships(p) | z*r.sign) AS dir,
     reduce(w=1.0,r IN relationships(p) | w*CASE r.strength WHEN 'high' THEN 1.0 WHEN 'medium' THEN 0.6 WHEN 'low' THEN 0.3 ELSE null END) AS weight,
     [r IN ([a]+relationships(p)) WHERE r.condition IS NOT NULL | r] AS conditionalEdges
RETURN s.id AS skill,k.id AS measure,k.name AS name,k.direction AS direction,owners,
       dir,weight,(dir=1)=(k.direction='UP') AS good,size(conditionalEdges)>0 AS conditional,
       'individual_path_not_aggregated' AS aggregation,
       [s.id]+[n IN nodes(p) | n.id] AS nodes,
       [r IN ([a]+relationships(p)) | {key:elementId(r),type:type(r),source:startNode(r).id,target:endNode(r).id,
          sign:r.sign,strength:r.strength,delta:r.delta,unit:r.unit,note:r.note,
          condition:r.condition}] AS edges,
       [r IN ([a]+relationships(p)) WHERE r.condition IS NOT NULL | r.condition] AS conds
ORDER BY skill,measure,nodes
