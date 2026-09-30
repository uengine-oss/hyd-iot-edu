// T2 — 원인 → 조치(파라미터 범위·제약) → SOP 단계 → 매뉴얼 절   (parameter: $cause, e.g. 'cause:cooler-fin-fouling')
// relation = MITIGATED_BY(즉시 완화 명령) | REMEDIED_BY(근본 조치·작업지시)
MATCH (c:Cause {id: $cause})-[m:MITIGATED_BY|REMEDIED_BY]->(a:Action)
OPTIONAL MATCH (a)-[:REQUIRES]->(k:Constraint)
OPTIONAL MATCH (a)-[:TARGETS]->(x:Actuator {asset: $asset})
OPTIONAL MATCH (a)-[:FOLLOWS]->(pr:Procedure)
OPTIONAL MATCH (pr)-[:HAS_STEP]->(st:Step)
OPTIONAL MATCH (st)-[:REFERS_TO]->(ms:ManualSection)
WITH a, type(m) AS relation, pr, x,
     collect(DISTINCT {id: k.id, name: k.name, expr: k.expr}) AS constraints,
     collect(DISTINCT {id: st.id, order: st.order, text: st.text,
                       manual: CASE WHEN ms IS NULL THEN null ELSE {id: ms.id, ref: ms.ref, title: ms.title, excerpt: ms.excerpt} END}) AS steps
RETURN a.id AS actionId, a.code AS code, a.name AS name, a.kind AS kind, a.priority AS priority, a.description AS description,
       a.param AS param, a.min AS min, a.max AS max, a.default AS default,
       relation, x.id AS actuatorId, x.resource AS resource,
       CASE WHEN pr IS NULL THEN null ELSE {id: pr.id, name: pr.name} END AS procedure,
       [k IN constraints WHERE k.id IS NOT NULL] AS constraints,
       [s IN steps WHERE s.id IS NOT NULL] AS steps
ORDER BY priority
