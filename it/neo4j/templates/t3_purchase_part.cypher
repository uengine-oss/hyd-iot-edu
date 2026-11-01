// T3 — 부품 번호(partNo)로 부품 하나를 찾는다: 예비품 구매(시나리오 C)의 원문 구매 절차가 다루는 부품(parameter: $partNo 예 'P-PMP-SEAL').
MATCH (p:Part {partNo:$partNo})
RETURN p.id AS id,p.name AS name,p.partNo AS partNo
