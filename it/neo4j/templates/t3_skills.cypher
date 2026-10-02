// T3-a — 스킬 상세 (parameter: $ids). t2_skills와 같은 모양. 후보 선택 규칙이 고른 스킬의 카드 내용을 채운다.
MATCH (k:Skill) WHERE k.id IN $ids
OPTIONAL MATCH (k)-[:APPROVED_BY]->(r:Role)
OPTIONAL MATCH (fm:FailureMode)-[m:MITIGATED_BY|REMEDIED_BY]->(k)
WITH k, r, head(collect(type(m))) AS relation, head(collect(fm.id)) AS fmId
RETURN k.id AS skillId, k.sopId AS sopId, k.name AS name, k.kind AS kind, k.description AS description,
       relation, fmId AS failureModeId,
       CASE WHEN r IS NULL THEN null ELSE {id: r.id, name: r.name, level: r.level} END AS approver,
       COLLECT { MATCH (k)-[co:CONSISTS_OF]->(a:Action) OPTIONAL MATCH (a)-[:TARGETS]->(t)
                 RETURN {id: a.id, code: a.code, name: a.name, kind: a.kind, param: a.param, min: a.min, max: a.max,
                         value: co.value, seq: co.seq, target: t.id, targetName: t.name} ORDER BY co.seq } AS actions,
       COLLECT { MATCH (k)-[:HAS_STEP]->(st:Step) OPTIONAL MATCH (st)-[:REFERS_TO]->(ms:ManualSection)
                 RETURN {id: st.id, order: st.order, text: st.text,
                         manual: CASE WHEN ms IS NULL THEN null ELSE {id: ms.id, ref: ms.ref, title: ms.title, excerpt: ms.excerpt} END} ORDER BY st.order } AS steps,
       COLLECT { MATCH (k)-[:ADDRESSES]->(c:Cause) RETURN c.id } AS addresses
ORDER BY sopId
