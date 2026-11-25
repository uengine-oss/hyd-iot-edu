#!/usr/bin/env bash
# 통합반 2회차 덱 3단원(42~59장) 화면의 Cypher 예를 빈 Neo4j 5.26 Community에서 그대로 돌려 결과를 남긴다
# (공통 C-2: 실행 결과는 화면에 적힌 조건 그대로 돌린 값만 쓴다). 덱 제작 기준이 cypher_확인_결과.txt를 근거로 가리킨다.
# 떠 있는 수업 스택의 Neo4j는 건드리지 않는다. 이름이 다른 임시 컨테이너를 띄우고, 끝나면 지운다. Docker와 이미지 neo4j:5.26-community가 있어야 한다.
# 화면의 쿼리를 고치면 이 파일의 같은 쿼리도 고치고 다시 돌린다.
# 사용(이 폴더에서, Git Bash): MSYS_NO_PATHCONV=1 bash cypher_확인.sh > cypher_확인_결과.txt 2>&1
set -u
NAME=hyd-deck-u3-cypher-check
docker rm -f -v "$NAME" >/dev/null 2>&1
docker run -d --name "$NAME" --memory 900m \
  -e NEO4J_AUTH=none \
  -e NEO4J_server_memory_heap_initial__size=256m -e NEO4J_server_memory_heap_max__size=256m \
  -e NEO4J_server_memory_pagecache_size=64m \
  neo4j:5.26-community >/dev/null || { echo "컨테이너를 띄우지 못했다"; exit 1; }
trap 'docker rm -f -v "$NAME" >/dev/null 2>&1; echo "== 임시 컨테이너 지움: $NAME"' EXIT
for i in $(seq 1 60); do
  docker exec "$NAME" cypher-shell -a bolt://localhost:7687 "RETURN 1;" >/dev/null 2>&1 && break
  sleep 2
done
q() {   # q "제목" "쿼리"  — 한 문장을 따로 돌리고 출력과 종료 코드를 남긴다
  echo "== $1"
  printf '%s\n' "$2" | sed 's/^/   > /'
  printf '%s\n' "$2" | docker exec -i "$NAME" cypher-shell -a bolt://localhost:7687 --format plain 2>&1
  echo "   (종료 코드 $?)"
}
docker exec "$NAME" cypher-shell -a bolt://localhost:7687 --format plain "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;"

echo; echo "######## 57장 CREATE — 빈 DB, 제약 없음"
q "57-1 CREATE 첫 번째" "CREATE (:Part {partNo: 'CC-2040'});"
q "57-2 CREATE 두 번째(같은 쿼리)" "CREATE (:Part {partNo: 'CC-2040'});"
q "57-3 품번 CC-2040인 부품 노드 수" "MATCH (p:Part {partNo: 'CC-2040'}) RETURN count(p) AS n;"
q "정리" "MATCH (p:Part) DETACH DELETE p;"

echo; echo "######## 48 · 57장 품번에 유일 제약을 건 뒤의 CREATE"
q "48-1 유일 제약 만들기" "CREATE CONSTRAINT part_partno_unique IF NOT EXISTS FOR (p:Part) REQUIRE p.partNo IS UNIQUE;"
q "48-2 CREATE 첫 번째" "CREATE (:Part {partNo: 'CC-2040'});"
q "48-3 CREATE 두 번째(같은 쿼리)" "CREATE (:Part {partNo: 'CC-2040'});"
q "48-4 품번 CC-2040인 부품 노드 수" "MATCH (p:Part {partNo: 'CC-2040'}) RETURN count(p) AS n;"
q "정리" "MATCH (p:Part) DETACH DELETE p;"
q "정리" "DROP CONSTRAINT part_partno_unique;"

echo; echo "######## 58장 MERGE — 빈 DB, 제약 없음"
q "58-1 MERGE 첫 번째" "MERGE (:Part {partNo: 'CC-2040'});"
q "58-2 MERGE 두 번째(같은 쿼리)" "MERGE (:Part {partNo: 'CC-2040'});"
q "58-3 품번 CC-2040인 부품 노드 수" "MATCH (p:Part {partNo: 'CC-2040'}) RETURN count(p) AS n;"
q "정리" "MATCH (p:Part) DETACH DELETE p;"
q "58-4 이름까지 적은 MERGE 첫 번째" "MERGE (:Part {partNo: 'CC-2040', name: '쿨러 코어'});"
q "58-5 이름을 다르게 적은 MERGE(품번은 같다)" "MERGE (:Part {partNo: 'CC-2040', name: '쿨러코어'});"
q "58-6 품번 CC-2040인 부품 노드 수" "MATCH (p:Part {partNo: 'CC-2040'}) RETURN count(p) AS n;"
q "정리" "MATCH (p:Part) DETACH DELETE p;"

echo; echo "######## 48장 DB에 걸지 않은 규칙 — 품번에 유일 제약만 건 DB에 거꾸로 그은 가진다를 넣는다"
q "48-5 유일 제약 만들기" "CREATE CONSTRAINT part_partno_unique IF NOT EXISTS FOR (p:Part) REQUIRE p.partNo IS UNIQUE;"
q "48-6 오일 쿨러에서 2호기로 거꾸로 그은 가진다" "CREATE (:Component {code: 'EQ-02-COOLER', name: '오일 쿨러'})-[:HAS_COMPONENT]->(:Asset {code: 'EQ-02', name: '2호기'});"
q "48-7 구성 요소에서 설비로 간 가진다의 수" "MATCH (:Component)-[r:HAS_COMPONENT]->(:Asset) RETURN count(r) AS n;"
q "정리" "MATCH (n) DETACH DELETE n;"

echo; echo "######## 58장 품번에 유일 제약을 건 뒤의 MERGE"
q "58-7 MERGE 첫 번째" "MERGE (:Part {partNo: 'CC-2040'});"
q "58-8 MERGE 두 번째(같은 쿼리)" "MERGE (:Part {partNo: 'CC-2040'});"
q "58-9 품번 CC-2040인 부품 노드 수" "MATCH (p:Part {partNo: 'CC-2040'}) RETURN count(p) AS n;"
q "정리" "MATCH (p:Part) DETACH DELETE p;"
q "58-10 이름까지 적은 MERGE 첫 번째" "MERGE (:Part {partNo: 'CC-2040', name: '쿨러 코어'});"
q "58-11 이름을 다르게 적은 MERGE(품번은 같다)" "MERGE (:Part {partNo: 'CC-2040', name: '쿨러코어'});"
q "58-12 품번 CC-2040인 부품 노드 수" "MATCH (p:Part {partNo: 'CC-2040'}) RETURN count(p) AS n;"
q "정리" "MATCH (p:Part) DETACH DELETE p;"
q "정리" "DROP CONSTRAINT part_partno_unique;"

echo; echo "######## 1 · 2단원의 예(1~3호기, 2호기의 구성 요소 셋, 세 오일 쿨러가 같은 쿨러 코어를 쓴다)를 넣는다"
q "예 넣기" "CREATE (e1:Asset {code: 'EQ-01', name: '1호기'}), (e2:Asset {code: 'EQ-02', name: '2호기'}), (e3:Asset {code: 'EQ-03', name: '3호기'}),
 (c1:Component {code: 'EQ-01-COOLER', name: '오일 쿨러'}), (c2:Component {code: 'EQ-02-COOLER', name: '오일 쿨러'}),
 (f2:Component {code: 'EQ-02-FAN', name: '쿨러 팬'}), (m2:Component {code: 'EQ-02-PUMP', name: '주 펌프'}),
 (c3:Component {code: 'EQ-03-COOLER', name: '오일 쿨러'}),
 (p:Part {partNo: 'CC-2040', name: '쿨러 코어'}),
 (e1)-[:HAS_COMPONENT]->(c1), (e2)-[:HAS_COMPONENT]->(c2), (e2)-[:HAS_COMPONENT]->(f2), (e2)-[:HAS_COMPONENT]->(m2), (e3)-[:HAS_COMPONENT]->(c3),
 (c1)-[:USES_PART]->(p), (c2)-[:USES_PART]->(p), (c3)-[:USES_PART]->(p);"
q "50 · 55장 MATCH · RETURN" "MATCH (:Asset {code: 'EQ-02'})
      -[:HAS_COMPONENT]->(c:Component)
RETURN c.name;"
q "52 · 53장 첫째 줄 — 설비부터 적은 패턴" "MATCH (:Asset {code: 'EQ-02'})-[:HAS_COMPONENT]->(c:Component)
RETURN c.name;"
q "53장 둘째 줄 — 구성 요소부터 적은 같은 패턴" "MATCH (c:Component)<-[:HAS_COMPONENT]-(:Asset {code: 'EQ-02'})
RETURN c.name;"
q "53장 머리를 반대로 적은 줄 — 구성 요소에서 설비로 가는 가진다" "MATCH (c:Component)-[:HAS_COMPONENT]->(:Asset {code: 'EQ-02'})
RETURN c.name;"
q "56장 WHERE" "MATCH (:Asset {code: 'EQ-02'})
      -[:HAS_COMPONENT]->(c:Component)
WHERE c.name = '오일 쿨러'
RETURN c.code;"
q "56장 같은 조건을 중괄호에 적은 쿼리" "MATCH (:Asset {code: 'EQ-02'})
      -[:HAS_COMPONENT]->(c:Component {name: '오일 쿨러'})
RETURN c.code;"
q "59장 역량 질문" "MATCH (:Asset {code: 'EQ-02'})
      -[:HAS_COMPONENT]->(c:Component)
      -[:USES_PART]->(p:Part)
WHERE c.name = '오일 쿨러'
RETURN p.partNo;"
q "46장 쿨러 코어를 쓰는 구성 요소(다대다가 관계로 남았는지)" "MATCH (c:Component)-[:USES_PART]->(p:Part {partNo: 'CC-2040'})
RETURN c.code ORDER BY c.code;"
