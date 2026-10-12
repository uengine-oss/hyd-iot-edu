MATCH (n)
RETURN labels(n)[0] AS 레이블, count(*) AS 전체, count(n._manual_document) AS 문서에서_온_것
ORDER BY 레이블;
