// 지식 지도 노드: 고른 설비 하나 + 설비와 무관한 지식 노드 전부 (다른 설비 노드와 그 설비의 사건은 뺀다). $ns: 이름 공간(G4, 비면 수업 기준)
// 실행 버전/작업은 인스턴스 화면에서 조회한다. 이 지도는 업무 지식과 사례를 표시한다.
MATCH (n)
WHERE NOT (n:ProcessVersion OR n:ProcessInstance OR n:WorkItem OR n:IngestionControl OR n:IngestionBatch)
  AND NOT EXISTS { (:ProcessVersion)-[:HAS_NODE]->(n) }
  AND (NOT n:Asset OR n.code = $asset)
  AND (NOT n:Incident OR EXISTS { (n)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT n:DecisionCase OR EXISTS { (n)-[:FOR_INCIDENT]->(:Incident)-[:ON_ASSET]->(:Asset {code: $asset}) })
  // G4 이름 공간: $ns 가 비면 수업 기준(ns 없는 노드)만, 학생 ID 면 그 학생 노드 + 그 노드에 바로 닿는 기준 노드(다리 관계의 v2 쪽)
  AND CASE WHEN coalesce($ns, '') = '' THEN n.ns IS NULL
           ELSE n.ns = $ns OR (n.ns IS NULL AND EXISTS { MATCH (n)--(m) WHERE m.ns = $ns }) END
RETURN n.id AS id, [l IN labels(n) WHERE l <> 'FlowNode'][0] AS label, coalesce(n.name, n.title, n.text, n.ref, CASE WHEN n:Forecast THEN '예측 ' + toString(n.value) + ' ' + n.unit END, n.id) AS name, properties(n) AS props
