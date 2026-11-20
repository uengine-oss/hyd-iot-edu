#!/usr/bin/env bash
# 실전반 2회차 덱 3단원에서 이 원고가 새로 화면에 올린 실행 결과(44장의 WHERE 줄을 뺀 결과와 조회 뒤의 그래프, 47장 응용 C)를
# 빈 Neo4j 5.26 Community에서 그대로 돌려 남긴다(공통 C-2: 실행 결과는 화면에 적힌 조건 그대로 돌린 값만 쓴다).
# 덱 제작 기준이 cypher_확인_결과.txt를 근거로 가리킨다. 통합 2회차에서 그대로 받는 코드 장의 결과는 ../../integrated/day02/cypher_확인_결과.txt가 근거다.
# 떠 있는 수업 스택의 Neo4j는 건드리지 않는다. 이름이 다른 임시 컨테이너를 띄우고(포트를 열지 않는다), 끝나면 지운다.
# Docker와 이미지 neo4j:5.26-community가 있어야 한다. 화면의 쿼리를 고치면 이 파일의 같은 쿼리도 고치고 다시 돌린다.
# 사용(이 폴더에서, Git Bash): MSYS_NO_PATHCONV=1 bash cypher_확인.sh > cypher_확인_결과.txt 2>&1
set -u
NAME=hyd-deck-practical2-u3-check
docker rm -f "$NAME" >/dev/null 2>&1
docker run -d --name "$NAME" --memory 900m \
  -e NEO4J_AUTH=none \
  -e NEO4J_server_memory_heap_initial__size=256m -e NEO4J_server_memory_heap_max__size=256m \
  -e NEO4J_server_memory_pagecache_size=64m \
  neo4j:5.26-community >/dev/null || { echo "컨테이너를 띄우지 못했다"; exit 1; }
trap 'docker rm -f "$NAME" >/dev/null 2>&1; echo "== 임시 컨테이너 지움: $NAME"' EXIT
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
COUNT="MATCH (n) WITH count(n) AS nodes OPTIONAL MATCH ()-[r]->() RETURN nodes, count(r) AS relationships;"
docker exec "$NAME" cypher-shell -a bolt://localhost:7687 --format plain "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;"

echo; echo "######## 1 · 2단원의 예(1~3호기, 2호기의 구성 요소 셋, 세 오일 쿨러가 같은 쿨러 코어를 쓴다)를 넣는다(통합 확인과 같은 예)"
q "예 넣기" "CREATE (e1:Asset {code: 'EQ-01', name: '1호기'}), (e2:Asset {code: 'EQ-02', name: '2호기'}), (e3:Asset {code: 'EQ-03', name: '3호기'}),
 (c1:Component {code: 'EQ-01-COOLER', name: '오일 쿨러'}), (c2:Component {code: 'EQ-02-COOLER', name: '오일 쿨러'}),
 (f2:Component {code: 'EQ-02-FAN', name: '쿨러 팬'}), (m2:Component {code: 'EQ-02-PUMP', name: '주 펌프'}),
 (c3:Component {code: 'EQ-03-COOLER', name: '오일 쿨러'}),
 (p:Part {partNo: 'CC-2040', name: '쿨러 코어'}),
 (e1)-[:HAS_COMPONENT]->(c1), (e2)-[:HAS_COMPONENT]->(c2), (e2)-[:HAS_COMPONENT]->(f2), (e2)-[:HAS_COMPONENT]->(m2), (e3)-[:HAS_COMPONENT]->(c3),
 (c1)-[:USES_PART]->(p), (c2)-[:USES_PART]->(p), (c3)-[:USES_PART]->(p);"
q "처음 노드 수 · 관계 수" "$COUNT"

echo; echo "######## 44장 조회: 화면의 네 줄, 그리고 그 네 줄에서 WHERE 줄만 뺀 쿼리"
q "44-1 화면의 네 줄(MATCH · WHERE · RETURN)" "MATCH (:Asset {code: 'EQ-02'})
      -[:HAS_COMPONENT]->(c:Component)
WHERE c.name = '오일 쿨러'
RETURN c.code;"
q "44-2 WHERE 줄을 뺀 쿼리" "MATCH (:Asset {code: 'EQ-02'})
      -[:HAS_COMPONENT]->(c:Component)
RETURN c.code;"
q "44-3 46장 역량 질문 쿼리(조회)" "MATCH (:Asset {code: 'EQ-02'})
      -[:HAS_COMPONENT]->(c:Component)
      -[:USES_PART]->(p:Part)
WHERE c.name = '오일 쿨러'
RETURN p.partNo;"
q "44-4 조회 세 번 뒤 노드 수 · 관계 수" "$COUNT"

echo; echo "######## 47장 응용 C: 같은 그래프에 조회 쿼리와 적재 쿼리를 두 번씩 돌린다"
q "47-0 돌리기 전 노드 수 · 관계 수" "$COUNT"
q "47-1 조회 쿼리(MATCH · RETURN) 첫 번째" "MATCH (a:Asset) RETURN a.code;"
q "47-2 조회 한 번 뒤 노드 수 · 관계 수" "$COUNT"
q "47-3 같은 조회 쿼리 두 번째" "MATCH (a:Asset) RETURN a.code;"
q "47-4 조회 두 번 뒤 노드 수 · 관계 수" "$COUNT"
q "47-5 적재 쿼리(MERGE) 첫 번째" "MERGE (:Asset {code: 'EQ-04'});"
q "47-6 적재 한 번 뒤 노드 수 · 관계 수" "$COUNT"
q "47-7 같은 적재 쿼리(MERGE) 두 번째" "MERGE (:Asset {code: 'EQ-04'});"
q "47-8 적재 두 번 뒤 노드 수 · 관계 수" "$COUNT"
