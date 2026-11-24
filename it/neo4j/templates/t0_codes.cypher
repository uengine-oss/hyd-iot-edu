// T0 — 지식 지도가 아는 설비 코드와 부품 번호 (판단 실험이 스킬 본문이 어느 설비 · 부품을 가리키는지 읽을 때 — 이름 꼴로 짐작하지 않는다)
MATCH (a:Asset) WHERE a.code IS NOT NULL RETURN 'asset' AS kind, a.code AS code
UNION
MATCH (p:Part) WHERE p.partNo IS NOT NULL RETURN 'part' AS kind, p.partNo AS code
