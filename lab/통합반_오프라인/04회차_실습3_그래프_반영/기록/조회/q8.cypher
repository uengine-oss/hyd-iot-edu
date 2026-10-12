MATCH (n) WITH count(n) AS 노드
MATCH ()-[r]->()
RETURN 노드, count(r) AS 관계, count(r._manual_document) AS 문서에서_온_관계;
