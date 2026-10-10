// T2 꼭 답할 질문 틀 (전체 과정 랩업 단계 1 · 3). 문서마다 적은 "이 문서로 답할 질문"을 그래프 질의로 옮긴다.
// 형식은 it/neo4j/v2/queries.cypher 와 같다: // @query 이름, // @ask 질문, (필요하면) // @params {"키": 값}, 그 아래 Cypher.
// 질의는 $ns 로 내 이름 공간만 본다. 한 행도 안 나오면 그 질문은 "못 답함"이다: python students/<내ID>/load_graph.py ask

// @query room-rule
// @ask 고객 회의는 몇 인실에서 해야 하는가 — 근거 문장은?
MATCH (s:ManualSection {ns: $ns})-[:PART_OF]->(k:KnowledgeSource {ns: $ns})
WHERE s.title = '회의실'
RETURN k.name AS document, s.ref AS section, s.excerpt AS sentence;

// @query open-agenda
// @ask 이 회의에서 다룰 미결 안건은 무엇이고 어느 문서에서 나왔는가?
MATCH (m:Meeting {ns: $ns})-[:HAS_AGENDA]->(a:AgendaItem {status: 'open'})-[:RAISED_IN]->(k:KnowledgeSource)
RETURN m.name AS meeting, a.name AS agenda, k.name AS raised_in;

// @query materials
// @ask 회의 전에 공유할 자료는 무엇인가?
MATCH (m:Meeting {ns: $ns})-[:NEEDS_MATERIAL]->(x:Material)
RETURN m.name AS meeting, x.name AS material;
