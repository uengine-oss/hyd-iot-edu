// show_result.py가 그래프_모양.json · 질문_값.csv로 만든 조회문(읽기만). 질문마다 「터미널:」 줄을 복사해 실행하거나, Neo4j Browser에서는 「Browser:」 줄의 :param부터 붙여 넣는다.
// 질문 1
// 터미널: python lab_cypher.py query 결과/query.cypher 1 --param asset=HYD-02
// Browser: :param asset => "HYD-02";
MATCH (f:FailureMode)-[m:MITIGATED_BY|REMEDIED_BY]->(s:Skill)-[:ACTS_ON]->(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})
WITH DISTINCT m, s
OPTIONAL MATCH (k:`Knowledge`)-[c]->(t) WHERE (t = s OR (s)-[:HAS_STEP]->(t)) AND type(c) <> 'STATED_IN'
RETURN s.id AS sop, type(m) AS kind, s.approval_role AS approval, c.role AS role, k.doc_id AS doc, k.rev AS rev, k.section AS section, k.quote AS quote
ORDER BY sop, role, doc, quote;
// 질문 2
// 터미널: python lab_cypher.py query 결과/query.cypher 2
MATCH (r:Rule) OPTIONAL MATCH (k:`Knowledge`)-[s:`SUPPORTS`]->(r)
RETURN r.id AS rule, r.when AS condition, s.match AS match, k.doc_id AS doc, k.section AS section, k.quote AS quote ORDER BY rule, doc, quote;
// 질문 3
// 터미널: python lab_cypher.py query 결과/query.cypher 3 --param sop=SOP-COOL-14 --param asset=HYD-02
// Browser: :param sop => "SOP-COOL-14";
// Browser: :param asset => "HYD-02";
MATCH (s:Skill {id: $sop})-[:CHECKS]->(n:Sensor)<-[:MONITORED_BY]-(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})
RETURN n.id AS sensor, n.unit AS unit ORDER BY sensor;
// 질문 4
// 터미널: python lab_cypher.py query 결과/query.cypher 4 --param doc=OEM-HPP45A-MM
// Browser: :param doc => "OEM-HPP45A-MM";
MATCH (k:`Knowledge` {doc_id: $doc})-[r]->(t) WHERE type(r) <> 'STATED_IN'
RETURN type(r) AS rel, labels(t)[0] AS label, t.id AS target, count(k) AS knowledge ORDER BY rel, target;
// 질문 5대상
// 터미널: python lab_cypher.py query 결과/query.cypher 5대상 --param target=HYD-04:cooler
// Browser: :param target => "HYD-04:cooler";
OPTIONAL MATCH (t {id: $target}) OPTIONAL MATCH (k:`Knowledge`)-[r]->(t) WHERE type(r) <> 'STATED_IN'
RETURN $target AS target, count(DISTINCT t) AS found, count(DISTINCT k) AS knowledge;
// 질문 5절
// 터미널: python lab_cypher.py query 결과/query.cypher 5절 --param section=HM-9.4
// Browser: :param section => "HM-9.4";
OPTIONAL MATCH (x:`Section`) WHERE x.ref = $section RETURN $section AS section, count(x) AS found;
// 질문 보류
// 터미널: python lab_cypher.py query 결과/query.cypher 보류 --param "ids=HM-9_1.0_검토.json#HM-9-M008 OEM-HPP45A-MM_C_검토.json#OEM-HPP45A-MM-M054"
// Browser: :param ids => "HM-9_1.0_검토.json#HM-9-M008 OEM-HPP45A-MM_C_검토.json#OEM-HPP45A-MM-M054";
OPTIONAL MATCH (k:`Knowledge`) WHERE k.candidate IN split($ids, ' ') RETURN size(split($ids, ' ')) AS asked, count(k) AS found;
// 질문 카드
// 아직 결과/질문_값.csv에 sop 값이 없음
MATCH (s:Skill {id: $sop}) OPTIONAL MATCH (s)-[:HAS_STEP]->(st:Step)
WITH s, collect(DISTINCT {order: st.order, text: st.text, source: st.source}) AS steps
OPTIONAL MATCH (k:`Knowledge`)-[c]->(t) WHERE (t = s OR (s)-[:HAS_STEP]->(t)) AND type(c) <> 'STATED_IN'
RETURN s.id AS sop, s.name AS name, s.source AS source, s.approval_role AS approval, steps,
       collect(DISTINCT {role: c.role, doc: k.doc_id, rev: k.rev, status: k.doc_status, section: k.section, quote: k.quote, id: k.candidate, step: t.id}) AS evidence;
