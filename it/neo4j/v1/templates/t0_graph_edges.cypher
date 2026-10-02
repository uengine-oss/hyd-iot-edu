// 지식 지도 관계: 위 노드들 사이의 관계
MATCH (a)-[r]->(b)
WHERE (NOT a:Asset OR a.id = $asset) AND (a.asset IS NULL OR a.asset = $asset OR a.asset = 'ALL')
  AND (NOT b:Asset OR b.id = $asset) AND (b.asset IS NULL OR b.asset = $asset OR b.asset = 'ALL')
RETURN a.id AS from, b.id AS to, type(r) AS type
