// 강사 참조 조회문. lab_cypher.py run 결과/query.cypher 로 실행한다.
// Q1 선택한 작업(SOP-COOL-11)의 준비·금지·완료·기준값과 출처: 절차 안 / 이 절차를 ID로 가리킴 / 같은 절의 절차 밖 문장 / 단계가 가리킨 절
MATCH (p:Procedure {id: "SOP-COOL-11"})-[:DEFINED_IN]->(s:Section)
CALL {
  WITH p MATCH (p)-[:HAS_STEP|HAS_CONDITION]->(k:Knowledge) RETURN k, '절차 안' AS via
  UNION WITH p MATCH (k:Knowledge)-[:REFERS_TO]->(p) RETURN k, 'ID로 가리킴' AS via
  UNION WITH p, s MATCH (k:Knowledge)-[:STATED_IN]->(s) WHERE NOT (k)<-[:HAS_STEP|HAS_CONDITION]-(:Procedure) RETURN k, '같은 절' AS via
  UNION WITH p MATCH (p)-[:HAS_STEP|HAS_CONDITION]->(:Knowledge)-[:REFERS_TO]->(rs:Section)<-[:STATED_IN]-(k:Knowledge) RETURN k, '가리킨 절' AS via
}
MATCH (k)-[:STATED_IN]->(ks:Section)
WHERE k.kind <> 'step' OR (k)<-[:HAS_STEP]-(p)
RETURN k.kind, ks.id, k.id, k.text, via ORDER BY k.kind, ks.id, k.id;
// Q2 다른 작업(SOP-COOL-14)도 같은 조회로 답하는지
MATCH (p:Procedure {id: "SOP-COOL-14"})-[:DEFINED_IN]->(s:Section)
CALL {
  WITH p MATCH (p)-[:HAS_STEP|HAS_CONDITION]->(k:Knowledge) RETURN k, '절차 안' AS via
  UNION WITH p MATCH (k:Knowledge)-[:REFERS_TO]->(p) RETURN k, 'ID로 가리킴' AS via
  UNION WITH p, s MATCH (k:Knowledge)-[:STATED_IN]->(s) WHERE NOT (k)<-[:HAS_STEP|HAS_CONDITION]-(:Procedure) RETURN k, '같은 절' AS via
  UNION WITH p MATCH (p)-[:HAS_STEP|HAS_CONDITION]->(:Knowledge)-[:REFERS_TO]->(rs:Section)<-[:STATED_IN]-(k:Knowledge) RETURN k, '가리킨 절' AS via
}
MATCH (k)-[:STATED_IN]->(ks:Section)
RETURN k.kind, ks.id, k.id, k.text, via ORDER BY k.kind, ks.id, k.id;
// Q3 원문이 제공하지 않는 작업·절: 결과 없음이어야 한다
MATCH (p:Procedure) WHERE p.id = "SOP-COOL-16" OR p.name CONTAINS "코어 교체" RETURN p.id, p.name;
MATCH (s:Section {id: "HM-8.9"}) RETURN s.id;
// Q4 제외·보류 후보는 DB에 없어야 한다(검토본의 excluded·pending id)
MATCH (k:Knowledge) WHERE k.id IN ["HM-8-007", "HM-8-022", "HM-8-047", "HM-8-029", "HM-8-033", "HM-8-038", "HM-8-041", "HM-8-044"] OR k.status <> "approved" RETURN count(k) AS 들어가면_안되는_후보;
// Q5 기존 모델 ID와의 연결: 물리량별 지식 수, 기존 ID가 없는 태그
MATCH (k:Knowledge)-[:ABOUT_QUANTITY]->(q:Quantity) RETURN q.id, q.name, count(k) ORDER BY q.id;
MATCH (k:Knowledge) WHERE k.unresolved_tags IS NOT NULL RETURN k.id, k.unresolved_tags;
// Q6 공급 정보: 핀 세척과 쿨러 코어 부품은 그래프에서 이어지는가, 부품의 공급 조건은 무엇인가
MATCH (p:Procedure {id: "SOP-COOL-14"}) OPTIONAL MATCH path = (p)-[*1..3]-(:Part) RETURN count(path) AS 작업과_부품_연결;
MATCH (s:Supplier)-[r:SUPPLIES]->(:Part {id: "P-CLR-CORE"}) RETURN s.name, r.approved, r.price_manwon, r.defect_rate, r.lead_days ORDER BY s.name;
