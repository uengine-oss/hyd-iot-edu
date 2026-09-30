// T3-g 현장 판단 선례 (HITL 환류): 같은 시나리오에서 사람이 승인한 대안과 사유
// Decision -ABOUT-> Scenario, Decision -DECIDED-> Option (process 서비스가 승인 때 기록)
MATCH (d:Decision)-[:ABOUT]->(:Scenario {id: $scenario})
MATCH (d)-[:DECIDED]->(o:Option)
WHERE d.state IN ['APPROVED', 'EXECUTED', 'PARTIAL']
WITH o.id AS option, count(d) AS n, collect(d.reason) AS rs
RETURN option, n, [r IN rs WHERE r IS NOT NULL AND r <> ''][..3] AS reasons
