#!/bin/bash
# kg-seed: load the ontology v2 (schema-first: v2/schema.json -> v2/constraints.cypher + v2/instances.cypher). Idempotent.
# A graph seeded by the old v1 ontology (Scenario · Procedure · InfoType …) is cleared once, so v1 and v2 never mix.
# 확정 TODO C1: 시드는 두 판이다. SEED_EDITION=structure(수업용 구조판, 강의 배포 기본) | full(회귀용 전체판). 표시 규칙은 edition.sh.
set -e
URI=${NEO4J_URI:-bolt://neo4j:7687}
USER=neo4j; PASS=${NEO4J_PASSWORD:-hydpass123}
EDITION=${SEED_EDITION:-structure}
case "$EDITION" in structure|full) ;; *) echo "SEED_EDITION must be structure or full (got '$EDITION')"; exit 1;; esac
SEED_DIR=${SEED_DIR:-/seed}
. "$SEED_DIR/edition.sh"
cy() { cypher-shell -a "$URI" -u $USER -p $PASS --format plain "$@"; }
load() {   # $1 = file under v2/ — only the statements of this edition
  local tmp; tmp=$(mktemp)
  seed_edition_filter "$EDITION" "$SEED_DIR/v2/$1" > "$tmp"
  cy -f "$tmp"; rm -f "$tmp"
}
for i in $(seq 1 60); do
  if cy "RETURN 1" >/dev/null 2>&1; then break; fi
  echo "waiting for neo4j ($i)"; sleep 3
done
V1=$(cy "MATCH (n) WHERE n:Scenario OR n:Procedure OR n:InfoType OR n:Policy OR n:ManualUpload RETURN count(n)" | tail -1)
if [ "$V1" != "0" ]; then
  echo "v1 ontology found ($V1 marker nodes) — clearing the graph for v2"
  cy "MATCH (n) DETACH DELETE n" >/dev/null
  for c in $(cy "SHOW CONSTRAINTS YIELD name RETURN name" | tail -n +2 | tr -d '"'); do cy "DROP CONSTRAINT \`$c\` IF EXISTS" >/dev/null; done
  for x in $(cy "SHOW INDEXES YIELD name, type, owningConstraint WHERE type <> 'LOOKUP' AND owningConstraint IS NULL RETURN name" | tail -n +2 | tr -d '"'); do cy "DROP INDEX \`$x\` IF EXISTS" >/dev/null; done
fi
echo "seed edition: $EDITION (structure = 수업용 구조판, 고장 · 조치 지식은 문서 적재로 / full = 회귀용 전체판)"
echo "seeding ontology v2: constraints ..."
cy -f "$SEED_DIR/v2/constraints.cypher"
echo "seeding ontology v2: instances (가치 BSC · 프로세스 BPMN · 리소스 · 설비 진단 · 스킬=SOP · 규칙 DMN · 외부 변수) ..."
load instances.cypher
echo "seeding ontology v2: knowledge_a098 (전문가 질문 3건의 답: 유량→생산량 · 작동유 열화 원인/증상 · 저압/고진동 트립) ..."
load knowledge_a098.cypher
echo "seeding ontology v2: scenario_structure (시나리오 C 구조: 구매 담당 역할 · 재고 기준 이탈 패턴 · 판단 입력) ..."
load scenario_structure.cypher
# A156: the detector reads only AnomalyPatterns with detectionMode='held' (it/detector/det/pattern_source.py). Without this file
# a fresh volume leaves the detector unhealthy ("catalog must contain 1..64 held patterns") — seen on the first cloud boot.
# Additive and idempotent (coalesce keeps edited values), same file and order as scripts/ontology_v2.py load.
echo "seeding ontology v2: detector-patterns (held 탐지 정의: detectionMode · clearRule · 유지 시간) ..."
load detector-patterns.cypher
# A144 (O04): read back what was just loaded. Every line of seed_checks.cypher is one query that returns offending rows;
# any row means the seed did not land as the scenarios expect, and the service fails (compose: agent · dmn-mcp depend on
# kg-seed completing successfully, so a broken graph never starts the judgment services). Lines marked for one edition run only there.
echo "--- read-back checks (v2/seed_checks.cypher, $EDITION) ---"
FAILED=0; CHECKS=0
while IFS= read -r q; do
  CHECKS=$((CHECKS+1))
  ROWS=$(cy "$q" | tail -n +2 | sed '/^$/d')
  if [ -n "$ROWS" ]; then echo "CHECK FAILED: $ROWS"; FAILED=$((FAILED+1)); fi
done < <(seed_edition_checks "$EDITION" "$SEED_DIR/v2/seed_checks.cypher")
echo "read-back: $CHECKS checks, $FAILED failed"
if [ "$FAILED" != "0" ]; then echo "kg-seed FAILED read-back"; exit 1; fi
echo "--- node counts by label ---"
cy "MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS n ORDER BY l"
echo "--- 고장 유형별 조치 방법 (스킬 = SOP) ---"
cy "MATCH (fm:FailureMode)-[k:MITIGATED_BY|REMEDIED_BY]->(s:Skill) RETURN fm.name, type(k), s.sopId, s.name ORDER BY fm.name, type(k) DESC, s.sopId"
echo "kg-seed done ($EDITION)"
