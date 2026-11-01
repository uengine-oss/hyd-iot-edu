#!/bin/bash
# kg-seed: 온톨로지 v2의 제약(v2/constraints.cypher — schema.json에서 생성)과 기준 데이터를 적재하고, 들어간 것을 되읽어 검사한다.
# 시작할 때마다 돈다(compose kg-seed). 모든 문장은 id로 MERGE · SET만 하므로 몇 번을 돌려도 그래프가 같다.
# 고장 · 원인 · 조치(SOP) · 매뉴얼 규칙은 여기서 넣지 않는다 — 수업 문서 적재가 만든다(scripts/class_knowledge.py).
# 실패는 그 자리에서 멈춘다: agent · dmn-mcp는 이 서비스가 성공해야 뜬다(compose depends_on service_completed_successfully).
set -euo pipefail
URI=${NEO4J_URI:-bolt://neo4j:7687}
USER=neo4j; PASS=${NEO4J_PASSWORD:-hydpass123}
SEED_DIR=${SEED_DIR:-/seed}
SEED_FILES=(instances.cypher scenario_structure.cypher pm_capabilities.cypher)   # 이 순서로 적재한다(뒤 파일이 앞 파일의 노드를 잇는다)
cy() { cypher-shell -a "$URI" -u "$USER" -p "$PASS" --format plain "$@"; }

WAIT_TRIES=${SEED_WAIT_TRIES:-60}; WAIT_S=3   # 기본 3분. 느린 PC · 시험은 SEED_WAIT_TRIES로 바꾼다
for ((i = 1; i <= WAIT_TRIES; i++)); do
  if cy "RETURN 1" >/dev/null 2>&1; then break; fi
  if ((i == WAIT_TRIES)); then
    echo "kg-seed FAILED: Neo4j($URI)에 $((WAIT_TRIES * WAIT_S))초 동안 닿지 못했다 — 마지막 시도의 오류:" >&2
    cy "RETURN 1" >&2 || true
    exit 1
  fi
  echo "waiting for neo4j ($i/$WAIT_TRIES)"; sleep "$WAIT_S"
done

echo "seeding ontology v2: constraints ..."
cy -f "$SEED_DIR/v2/constraints.cypher"
for f in "${SEED_FILES[@]}"; do
  echo "seeding ontology v2: $f ..."
  cy -f "$SEED_DIR/v2/$f"
done

# 되읽기 검사: seed_checks.cypher의 주석 아닌 줄 하나가 질의 하나이고 「문제가 있는 노드 · 관계」를 problem 열로 돌려준다.
# 질의가 행을 돌려주거나 질의 자체가 실패(문법 · 판 차이)하면 그 검사는 실패다 — 한 개라도 실패하면 kg-seed가 실패한다.
echo "--- read-back checks (v2/seed_checks.cypher) ---"
FAILED=0; CHECKS=0
while IFS= read -r q; do
  case "$q" in ''|//*) continue;; esac
  CHECKS=$((CHECKS + 1))
  if ! OUT=$(cy "$q" 2>&1); then
    echo "CHECK ERROR (질의가 실패했다): $q"; echo "$OUT" | tail -n 5
    FAILED=$((FAILED + 1)); continue
  fi
  ROWS=$(printf '%s\n' "$OUT" | tail -n +2 | sed '/^$/d')
  if [ -n "$ROWS" ]; then echo "CHECK FAILED: $ROWS"; FAILED=$((FAILED + 1)); fi
done < "$SEED_DIR/v2/seed_checks.cypher"
echo "read-back: $CHECKS checks, $FAILED failed"
if [ "$CHECKS" = "0" ]; then echo "kg-seed FAILED: 되읽기 검사 파일에 질의가 없다 ($SEED_DIR/v2/seed_checks.cypher)" >&2; exit 1; fi
if [ "$FAILED" != "0" ]; then echo "kg-seed FAILED read-back" >&2; exit 1; fi
echo "--- node counts by label ---"
cy "MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS n ORDER BY l"
echo "kg-seed done"
