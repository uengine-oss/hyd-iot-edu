// T2 — 원인 → 고장 유형 → 조치 방법(스킬 = SOP) → 원자 조치 · 단계 · 매뉴얼   (parameter: $cause e.g. 'cause:cooler-fin-fouling')
// relation = MITIGATED_BY(즉시 완화) | REMEDIED_BY(근본 조치). 특정 원인에만 맞는 스킬(ADDRESSES)은 그 원인일 때만 나온다. 예방 조치(PREVENTED_BY, 정기 정비)는 경보 대응 후보가 아니므로 따라가지 않는다(정기 정비 도래 후보는 문서 규칙이 고른다).
MATCH (c:Cause {id: $cause})-[:CAUSES]->(fm:FailureMode)-[m:MITIGATED_BY|REMEDIED_BY]->(k:Skill)
WHERE NOT (k)-[:ADDRESSES]->(:Cause) OR (k)-[:ADDRESSES]->(c)
OPTIONAL MATCH (k)-[:APPROVED_BY]->(r:Role)
RETURN k.id AS skillId, k.sopId AS sopId, k.name AS name, k.kind AS kind, k.description AS description,
       type(m) AS relation, fm.id AS failureModeId,
       CASE WHEN r IS NULL THEN null ELSE {id: r.id, name: r.name, level: r.level} END AS approver,
       COLLECT { MATCH (k)-[co:CONSISTS_OF]->(a:Action) OPTIONAL MATCH (a)-[:TARGETS]->(t)
                 RETURN {id: a.id, code: a.code, name: a.name, kind: a.kind, param: a.param, min: a.min, max: a.max,
                         value: co.value, seq: co.seq, target: t.id, targetName: t.name} ORDER BY co.seq } AS actions,
       COLLECT { MATCH (k)-[:HAS_STEP]->(st:Step) OPTIONAL MATCH (st)-[:REFERS_TO]->(ms:ManualSection)
                 RETURN {id: st.id, order: st.order, text: st.text,
                         manual: CASE WHEN ms IS NULL THEN null ELSE {id: ms.id, ref: ms.ref, title: ms.title, excerpt: ms.excerpt} END} ORDER BY st.order } AS steps
ORDER BY relation DESC, sopId
