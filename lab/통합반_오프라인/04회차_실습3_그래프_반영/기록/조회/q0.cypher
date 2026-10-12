MATCH (n) WITH count(n) AS 노드
MATCH ()-[r]->()
RETURN 노드, count(r) AS 관계;
