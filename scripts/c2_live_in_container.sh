#!/usr/bin/env bash
# C2 라이브 확인을 Supabase 망 안의 버리는 컨테이너에서 돌린다(메인 compose 스택 · 공유 DB 는 건드리지 않음).
# 앞서: bash scripts/c2_scratch_db.sh  (버리는 DB c2_check)
#       docker exec supabase_db_hyd-iot-edu psql -U postgres -c "create role c2_scratch login password 'c2-scratch-local' in role postgres"
# 뒤에: docker exec supabase_db_hyd-iot-edu psql -U postgres -c "drop role c2_scratch"; bash scripts/c2_scratch_db.sh drop
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm --network supabase_network_hyd-iot-edu -v "$PWD":/w -w /w \
  -e C2_DB_HOSTPORT=supabase_db_hyd-iot-edu:5432 \
  -e C2_ADMIN_DSN=postgresql://c2_scratch:c2-scratch-local@supabase_db_hyd-iot-edu:5432/c2_check \
  python:3.12-slim sh -c "pip install -q --root-user-action=ignore 'psycopg[binary]==3.2.3' fastapi==0.115.6 'uvicorn[standard]==0.34.0' fastmcp==2.13.0.2 'starlette<0.42' pydantic sqlglot==27.24.2 >/dev/null 2>&1; python scripts/c2_live_check.py .evidence/a161-c2"
