// 지식 지도 관계: t0_graph_nodes.cypher 가 고른 노드들 사이의 관계 (다른 설비 노드와 그 설비의 사건 쪽 관계는 뺀다)
// 숨기는 레이블 목록은 노드 질의와 같고 양 끝에 같은 목록을 쓴다.
WITH ['FlowNode','ProcessVersion','ProcessInstance','WorkItem','ExecutionActor','IngestionControl','IngestionBatch',
      'ExecutionProjection','CaseProjection','KnowledgeEdit','ManualIngestionDocument','ManualIngestionBatch'] AS hidden
MATCH (a)-[r]->(b)
WHERE none(l IN labels(a) + labels(b) WHERE l IN hidden)
  AND (NOT a:Asset OR a.code = $asset) AND (NOT b:Asset OR b.code = $asset)
  AND (NOT a:Incident OR EXISTS { (a)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT a:DecisionCase OR EXISTS { (a)-[:FOR_INCIDENT]->(:Incident)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT b:Incident OR EXISTS { (b)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT b:DecisionCase OR EXISTS { (b)-[:FOR_INCIDENT]->(:Incident)-[:ON_ASSET]->(:Asset {code: $asset}) })
  // 이름 공간: 수업 기준이면 양 끝 모두 ns 없음, 학생 ID 면 한쪽 끝이 그 학생 노드인 관계(다리 관계 포함).
  // 다른 끝은 같은 학생 노드이거나 수업 기준 노드다(다른 학생 노드는 노드 목록에 없으니 그 쪽 관계도 뺀다)
  AND CASE WHEN coalesce($ns, '') = '' THEN a.ns IS NULL AND b.ns IS NULL
           ELSE (a.ns = $ns OR b.ns = $ns) AND coalesce(a.ns, $ns) = $ns AND coalesce(b.ns, $ns) = $ns END
RETURN a.id AS from, b.id AS to, type(r) AS type
