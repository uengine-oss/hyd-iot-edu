#!/bin/bash
# kg-seed: load the ontology v2 (schema-first: v2/schema.json -> v2/constraints.cypher + v2/instances.cypher). Idempotent.
# A graph seeded by the old v1 ontology (Scenario · Procedure · InfoType …) is cleared once, so v1 and v2 never mix.
set -e
URI=${NEO4J_URI:-bolt://neo4j:7687}
USER=neo4j; PASS=${NEO4J_PASSWORD:-hydpass123}
cy() { cypher-shell -a "$URI" -u $USER -p $PASS --format plain "$@"; }
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
echo "seeding ontology v2: constraints ..."
cy -f /seed/v2/constraints.cypher
echo "seeding ontology v2: instances (가치 BSC · 프로세스 BPMN · 리소스 · 설비 진단 · 스킬=SOP · 규칙 DMN · 외부 변수) ..."
cy -f /seed/v2/instances.cypher
echo "seeding ontology v2: knowledge_a098 (전문가 질문 3건의 답: 유량→생산량 · 작동유 열화 원인/증상 · 저압/고진동 트립) ..."
cy -f /seed/v2/knowledge_a098.cypher
echo "--- node counts by label ---"
cy "MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS n ORDER BY l"
echo "--- 고장 유형별 조치 방법 (스킬 = SOP) ---"
cy "MATCH (fm:FailureMode)-[k:MITIGATED_BY|REMEDIED_BY]->(s:Skill) RETURN fm.name, type(k), s.sopId, s.name ORDER BY fm.name, type(k) DESC, s.sopId"
echo "kg-seed done"
