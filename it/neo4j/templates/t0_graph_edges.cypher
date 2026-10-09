// 지식 지도 관계: 위 노드들 사이의 관계 (다른 설비 노드와 그 설비의 사건 쪽 관계는 뺀다)
MATCH (a)-[r]->(b)
WHERE NOT (a:ProcessVersion OR a:ProcessInstance OR a:WorkItem OR a:IngestionControl OR a:IngestionBatch)
  AND NOT (b:ProcessVersion OR b:ProcessInstance OR b:WorkItem OR b:IngestionControl OR b:IngestionBatch)
  AND NOT EXISTS { (:ProcessVersion)-[:HAS_NODE]->(a) }
  AND NOT EXISTS { (:ProcessVersion)-[:HAS_NODE]->(b) }
  AND (NOT a:Asset OR a.code = $asset) AND (NOT b:Asset OR b.code = $asset)
  AND (NOT a:Incident OR EXISTS { (a)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT a:DecisionCase OR EXISTS { (a)-[:FOR_INCIDENT]->(:Incident)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT b:Incident OR EXISTS { (b)-[:ON_ASSET]->(:Asset {code: $asset}) })
  AND (NOT b:DecisionCase OR EXISTS { (b)-[:FOR_INCIDENT]->(:Incident)-[:ON_ASSET]->(:Asset {code: $asset}) })
  // G4 이름 공간: 수업 기준이면 양 끝 모두 ns 없음, 학생 ID 면 한쪽 끝이 그 학생 노드인 관계(다리 관계 포함)
  AND CASE WHEN coalesce($ns, '') = '' THEN a.ns IS NULL AND b.ns IS NULL ELSE a.ns = $ns OR b.ns = $ns END
RETURN a.id AS from, b.id AS to, type(r) AS type
