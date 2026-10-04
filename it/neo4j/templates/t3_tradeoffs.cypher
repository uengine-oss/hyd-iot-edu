// T3-c: retain each atomic path; evaluate conditions before aggregating effects.
// Scope: AFFECTS then <=4 INFLUENCES edges, stopping at the first Measure.
UNWIND $ids AS sid
MATCH (s:Skill {id: sid})-[a:AFFECTS]->(x)
MATCH p = (x)-[:INFLUENCES*0..4]->(k:Measure)
WHERE all(n IN nodes(p)[0..-1] WHERE NOT n:Measure)
OPTIONAL MATCH (k)-[:OWNED_BY]->(o:OrgUnit)
WITH s,a,p,k,collect(DISTINCT o.name) AS owners
WITH s,a,p,k,owners,a.sign * reduce(z=1,r IN relationships(p) | z*r.sign) AS dir,
     reduce(w=1.0,r IN relationships(p) | w*CASE r.strength WHEN 'high' THEN 1.0 WHEN 'medium' THEN 0.6 WHEN 'low' THEN 0.3 ELSE null END) AS weight,
     [r IN ([a]+relationships(p)) WHERE r.condition IS NOT NULL OR r.conditionPolicy IS NOT NULL | r] AS conditionalEdges
RETURN s.id AS skill,k.id AS measure,k.name AS name,k.direction AS direction,owners,
       dir,weight,(dir=1)=(k.direction='UP') AS good,size(conditionalEdges)>0 AS conditional,
       'individual_path_not_aggregated' AS aggregation,
       [s.id]+[n IN nodes(p) | n.id] AS nodes,
       [r IN ([a]+relationships(p)) | {key:elementId(r),type:type(r),source:startNode(r).id,target:endNode(r).id,
          sign:r.sign,strength:r.strength,delta:r.delta,unit:r.unit,note:r.note,
          condition:r.condition,conditionPolicy:r.conditionPolicy}] AS edges,
       [r IN ([a]+relationships(p)) WHERE r.condition IS NOT NULL | r.condition] AS conds
ORDER BY skill,measure,nodes
