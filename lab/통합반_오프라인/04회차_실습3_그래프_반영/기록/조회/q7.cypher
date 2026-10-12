MATCH (n)
WHERE n.name IN ['쿨러 핀 세척', '캐비닛 환기 보강']
RETURN labels(n)[0] AS 레이블, n.id AS id, n.name AS 이름;
