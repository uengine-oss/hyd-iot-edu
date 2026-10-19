// T8 예시 — 꼭 답할 질문(문서 D1 · D2 · D3 의 "이 문서로 답할 질문" 9개를 그래프 질의로 옮긴 것).
// 형식은 it/neo4j/v2/queries.cypher 와 같다. 돌리기: python students/_template/load_graph.py ask --dir students/_template/example_meeting

// @query d1-required-attendee
// @ask (D1) 필수 참석자 한 명이 안 되는 시간은 후보가 될 수 있는가?
MATCH (r:Rule {ns: $ns})-[t:TESTS]->(i:InputData {variable: 'required_ok_ratio'}), (r)-[:DERIVED_FROM]->(s:ManualSection)
RETURN r.when AS rule, r.effect AS effect, s.ref AS section, s.excerpt AS sentence;

// @query d1-prep-48h
// @ask (D1) 내일 오전 회의를 잡으면 자료 공유 규칙을 지키는가?
MATCH (r:Rule {ns: $ns})-[t:TESTS]->(i:InputData {variable: 'prep_hours'}), (r)-[:DERIVED_FROM]->(s:ManualSection)
RETURN r.when AS rule, t.operator AS operator, t.value AS hours, r.effect AS effect, s.ref AS section;

// @query d1-room
// @ask (D1) 4인실에서 고객 회의를 해도 되는가?
MATCH (r:Rule {ns: $ns})-[t:TESTS]->(i:InputData {variable: 'room_capacity'}), (r)-[:DERIVED_FROM]->(s:ManualSection)
RETURN r.when AS rule, t.value AS min_seats, r.effect AS effect, i.table AS read_from_table, i.column AS read_from_column, s.ref AS section;

// @query d2-slot-count
// @ask (D2) 시간 후보는 몇 개를 내는가?
MATCH (g:PrepGuide {ns: $ns})-[:GUIDE_STEP]->(st:Step)-[:REFERS_TO]->(s:ManualSection {title: '시간 후보'})
RETURN st.order AS step, s.ref AS section, s.excerpt AS sentence;

// @query d2-invite-when
// @ask (D2) 초대는 언제 보내는가?
MATCH (g:PrepGuide {ns: $ns})-[:GUIDE_STEP]->(st:Step)-[:REFERS_TO]->(s:ManualSection {title: '초대'})
RETURN st.order AS step, s.ref AS section, s.excerpt AS sentence;

// @query d2-agenda-source
// @ask (D2) 안건 초안은 무엇으로 만드는가?
MATCH (g:PrepGuide {ns: $ns})-[:GUIDE_STEP]->(st:Step)-[:REFERS_TO]->(s:ManualSection {title: '안건 초안'})
RETURN st.order AS step, s.ref AS section, s.excerpt AS sentence;

// @query d3-open-issues
// @ask (D3) 이 고객의 미결 이슈는 몇 건인가?
MATCH (a:AgendaItem {ns: $ns, status: 'open'})-[:ABOUT]->(c:Customer)
RETURN c.name AS customer, count(a) AS open_issues, collect(a.name) AS issues;

// @query d3-next-quarter
// @ask (D3) 다음 분기에 무엇을 확인하기로 했는가?
MATCH (d:Document {ns: $ns})-[:HAS_SECTION]->(s:ManualSection {title: '다음 분기 확인 지표'})
RETURN d.name AS document, s.ref AS section, s.excerpt AS sentence;

// @query d3-contact-changed
// @ask (D3) 고객 쪽 담당자가 바뀌었는가?
MATCH (a:AgendaItem {ns: $ns})-[:RAISED_IN]->(d:Document), (a)-[:ABOUT]->(c:Customer)
WHERE a.name CONTAINS '인수인계'
RETURN c.name AS customer, a.name AS issue, a.status AS status, d.name AS raised_in;
