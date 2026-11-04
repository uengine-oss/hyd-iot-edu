// 강사 참조 조회문 — Neo4j Browser에서는 :param 줄부터, run_reference.py는 같은 매개변수로 HTTP 실행
:param asset => 'HYD-02';
:param sop => 'SOP-COOL-14';
:param doc => 'OEM-HPP45A-MM';
:param ref => 'HM-9.4';
// 질문 1 — HYD-02 냉각 성능 상실의 조치마다 단계 · 조건과 근거 문서 · 판 · 절 · 인용
MATCH (f:FailureMode {id: 'fm:cooler-cooling-loss'})-[m:MITIGATED_BY|REMEDIED_BY]->(s:Skill)-[:ACTS_ON]->(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})
WITH DISTINCT f, m, s
OPTIONAL MATCH (k:Knowledge)-[c:CONDITION_OF|DESCRIBES]->(t) WHERE t = s OR (s)-[:HAS_STEP]->(t)
OPTIONAL MATCH (k)-[:STATED_IN]->(x:Section)<-[:HAS_SECTION]-(v:Revision)
RETURN s.id AS sop, type(m) AS kind, s.approval_role AS approval, coalesce(c.role, 'step') AS role, v.doc_id AS doc, v.rev AS rev, x.ref AS section, k.quote AS quote
ORDER BY sop, role, doc, quote;
// 질문 2 — 판정 규칙마다 근거 원문과 맞는 정도
MATCH (r:Rule) OPTIONAL MATCH (k:Knowledge)-[s:SUPPORTS]->(r) OPTIONAL MATCH (k)-[:STATED_IN]->(x:Section)<-[:HAS_SECTION]-(v:Revision)
RETURN r.id AS rule, r.when AS condition, s.match AS match, v.doc_id AS doc, x.ref AS section, k.quote AS quote ORDER BY rule, doc, quote;
// 질문 3 — 핀 세척 전에 확인할 현재 값(그래프 밖 원천)
MATCH (s:Skill {id: $sop})-[:CHECKS]->(n:Sensor)<-[:MONITORED_BY]-(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})
RETURN 'sensor' AS what, n.id AS id, n.unit AS unit, '시계열(관측값)' AS read_from
UNION
MATCH (k:Knowledge)-[:CONDITION_OF {role: 'preparation'}]->(:Skill {id: $sop}) WHERE k.quote CONTAINS 'MES'
RETURN 'plan' AS what, k.id AS id, null AS unit, 'MES 생산 계획' AS read_from;
// 질문 4 — 더한 문서(제조사 지침)의 작업이 걸리는 설비 대상
MATCH (k:Knowledge)-[:STATED_IN]->(:Section)<-[:HAS_SECTION]-(v:Revision {doc_id: $doc}) MATCH (k)-[r:APPLIES_TO|CONDITION_OF]->(t)
RETURN type(r) AS rel, labels(t)[0] AS label, t.id AS target, count(k) AS knowledge ORDER BY rel, target;
// 질문 5 — 제공되지 않은 작업: HYD-04 냉각 정비의 원문
MATCH (:Asset {id: 'HYD-04'})-[:HAS_COMPONENT]->(c:Component {id: 'HYD-04:cooler'}) OPTIONAL MATCH (k:Knowledge)-[:APPLIES_TO|CONDITION_OF]->(t) WHERE t = c OR (t:Skill AND (t)-[:ACTS_ON]->(c))
RETURN c.id AS component, count(k) AS knowledge;
// 질문 5 — 제공되지 않은 절: 트립 뒤 복귀의 원문 절
OPTIONAL MATCH (x:Section) WHERE x.ref = $ref RETURN $ref AS section, count(x) AS found;
// 보류 후보가 그래프에 없는가
MATCH (k:Knowledge) WHERE k.id IN $ids RETURN count(k) AS found;
// 카드 — 작업 하나의 준비 · 금지 · 순서 · 완료와 출처
MATCH (s:Skill {id: $sop}) OPTIONAL MATCH (s)-[:HAS_STEP]->(st:Step)
WITH s, collect(DISTINCT {order: st.order, text: st.text, source: st.source}) AS steps
OPTIONAL MATCH (k:Knowledge)-[c:CONDITION_OF|DESCRIBES]->(t) WHERE t = s OR (s)-[:HAS_STEP]->(t)
OPTIONAL MATCH (k)-[:STATED_IN]->(x:Section)<-[:HAS_SECTION]-(v:Revision)
RETURN s.id AS sop, s.name AS name, s.source AS source, s.approval_role AS approval, s.apply_conditions AS apply, s.prohibitions AS prohibitions, s.completion AS completion, steps,
       collect(DISTINCT {role: coalesce(c.role, 'step'), doc: v.doc_id, rev: v.rev, status: v.status, section: x.ref, quote: k.quote, id: k.id}) AS evidence;
