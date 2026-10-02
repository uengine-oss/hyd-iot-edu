// 지식 지도 노드: 한 설비의 인스턴스 + 설비와 무관한 지식 노드 전부
MATCH (n)
WHERE (NOT n:Asset OR n.id = $asset) AND (n.asset IS NULL OR n.asset = $asset OR n.asset = 'ALL')
RETURN n.id AS id, labels(n)[0] AS label, coalesce(n.name, n.title, n.text, n.ref, n.id) AS name, properties(n) AS props
