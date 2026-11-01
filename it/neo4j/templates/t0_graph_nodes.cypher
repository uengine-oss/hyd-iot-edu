// 지식 지도 노드: 고른 설비 하나 + 설비와 무관한 지식 노드 전부 (다른 설비 노드와 그 설비의 사건은 뺀다). $asset: 설비 코드, $ns: 이름 공간(비면 수업 기준)
// 실행 기록(배포 판본 · 처리 건 · 작업 · 실행 담당자)과 내부 기록(투영 잠금 · 편집 영수증 · 적재 이력)은 지도에 넣지 않는다 — 처리 건 화면이 보여 준다.
// 숨기는 레이블 목록은 t0_graph_edges.cypher와 같아야 한다(관계 질의가 양 끝에 같은 목록을 쓴다).
WITH ['FlowNode','ProcessVersion','ProcessInstance','WorkItem','ExecutionActor','IngestionControl','IngestionBatch',
      'ExecutionProjection','CaseProjection','KnowledgeEdit','ManualIngestionDocument','ManualIngestionBatch'] AS hidden
MATCH (n)
WHERE none(l IN labels(n) WHERE l IN hidden)
  AND (NOT n:Asset OR n.code = $asset)
  AND (NOT n:Incident OR EXISTS { (n)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT n:DecisionCase OR EXISTS { (n)-[:FOR_INCIDENT]->(:Incident)-[:ON_ASSET]->(:Asset {code: $asset}) })
  // 이름 공간: $ns 가 비면 수업 기준(ns 없는 노드)만, 학생 ID 면 그 학생 노드 + 그 노드에 바로 닿는 기준 노드(다리 관계의 v2 쪽)
  AND CASE WHEN coalesce($ns, '') = '' THEN n.ns IS NULL
           ELSE n.ns = $ns OR (n.ns IS NULL AND EXISTS { MATCH (n)--(m) WHERE m.ns = $ns }) END
RETURN n.id AS id, labels(n)[0] AS label, coalesce(n.name, n.title, n.text, n.ref, n.id) AS name, properties(n) AS props
