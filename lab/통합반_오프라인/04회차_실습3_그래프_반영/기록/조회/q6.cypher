MATCH (n)
WITH n.id AS id, count(*) AS 개수
WHERE 개수 > 1
RETURN id, 개수;
