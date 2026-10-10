#!/usr/bin/env bash
# C2 마이그레이션 검사: 실행 중인 로컬 Supabase(supabase_db_hyd-iot-edu) 안에 버리는 DB(c2_check)를 만들어 마이그레이션 전부 + seed 를
# 순서대로 적용한다. 공유 DB(postgres)는 건드리지 않는다. 끝나면 `bash scripts/c2_scratch_db.sh drop` 으로 지운다.
set -euo pipefail
D=${SUPABASE_DB_CONTAINER:-supabase_db_hyd-iot-edu}
DB=${C2_SCRATCH_DB:-c2_check}
cd "$(dirname "$0")/../it/supabase"
if [ "${1:-}" = "drop" ]; then
  docker exec "$D" psql -U postgres -q -c "drop database if exists $DB"
  echo "dropped $DB"; exit 0
fi
docker exec "$D" psql -U postgres -q -c "drop database if exists $DB" -c "create database $DB"
for f in $(ls migrations/*.sql | sort); do
  if ! out=$(docker exec -i "$D" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 -q < "$f" 2>&1); then
    echo "FAIL $f"; echo "$out" | tail -8; exit 1
  fi
done
docker exec -i "$D" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 -q < seed.sql
echo "OK $DB"
