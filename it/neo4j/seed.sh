#!/bin/bash
# kg-seed: load the ontology (idempotent) and print a summary. Runs inside the neo4j image (has cypher-shell).
set -e
URI=${NEO4J_URI:-bolt://neo4j:7687}
USER=neo4j; PASS=${NEO4J_PASSWORD:-hydpass123}
for i in $(seq 1 60); do
  if cypher-shell -a "$URI" -u $USER -p $PASS "RETURN 1" >/dev/null 2>&1; then break; fi
  echo "waiting for neo4j ($i)"; sleep 3
done
echo "seeding ontology ..."
cypher-shell -a "$URI" -u $USER -p $PASS --format plain -f /seed/seed.cypher
echo "seeding enterprise ontology (조직 · KPI · 규정 · 시스템 · 스킬 · 판단 시나리오) ..."
cypher-shell -a "$URI" -u $USER -p $PASS --format plain -f /seed/seed_enterprise.cypher
echo "--- node counts by label ---"
cypher-shell -a "$URI" -u $USER -p $PASS --format plain "MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS n ORDER BY l"
echo "--- T1 for COOLER_DEGRADATION ---"
cypher-shell -a "$URI" -u $USER -p $PASS --format plain -P "pattern => 'COOLER_DEGRADATION'" -P "asset => 'HYD-01'" \
  "MATCH (p:AnomalyPattern {code: \$pattern})-[:DETECTS]->(:Symptom)-[:INDICATES]->(fm:FailureMode)<-[r:CAUSES]-(c:Cause) RETURN DISTINCT c.id, r.weight ORDER BY r.weight DESC"
echo "kg-seed done"
