#!/bin/bash
# 촬영용 스택 데이터 스냅샷(Git Bash · 로컬). 되돌릴 수 없는 조작(적재 · 주입 · 승인)을 리허설한 뒤 같은 시작 상태로 돌아가려고 쓴다.
#   ./스냅샷.sh save <이름>     스택을 멈추고 볼륨을 작업/촬영/포털/스냅샷/<이름>/에 묶는다. 볼륨은 바꾸지 않는다.
#   ./스냅샷.sh restore <이름>  스택을 멈추고 각 볼륨 내용을 지운 뒤 그 스냅샷으로 되돌린다(데이터 변경 — 사용자 허락을 받은 범위에서만).
#   ./스냅샷.sh list            스냅샷 목록과 크기
# 워커 인증 볼륨(worker-runtime)은 묶지 않는다. 키 · 로그인 값을 파일로 남기지 않기 위해서다.
set -u
PROJECT=hyd-iot-edu
DB=supabase_db_hyd-portal-latest
# 수업 상태를 담은 볼륨만 묶는다(시계열 · 메시지 볼륨은 커서 묶고 푸는 데 10분 넘게 걸리고, 처음 상태로 돌아가는 데 필요 없다).
VOLUMES="hyd-iot-edu_detector-data hyd-iot-edu_neo4j-data hyd-iot-edu_process-data $DB"
here="$(cd "$(dirname "$0")" && pwd)"
work="$(cd "$here" && PYTHONUTF8=1 python -c "from common import WORK;print(WORK.as_posix())")"
IMAGE=python:3.12-slim
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "이미지 없음: $IMAGE (스냅샷.sh)"; exit 2; }
db_ids() { docker ps -a --filter "name=supabase_.*_hyd-portal-latest" --format '{{.Names}}'; }
stop_stack() { docker compose -p "$PROJECT" stop >/dev/null 2>&1; docker stop $(db_ids) >/dev/null 2>&1
  [ "$(docker ps -q | wc -l)" = "0" ] || { echo "멈추지 않은 컨테이너가 있음:"; docker ps --format '{{.Names}}'; exit 3; }; }
start_stack() { clone=$(docker inspect hyd-iot-edu-portal-1 --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'); [ -n "$clone" ] || { echo "스택 폴더를 찾지 못함"; exit 4; }
  ( cd "$clone" && bash scripts/start_all.sh > "$work/start_all.log" 2>&1 ) || { echo "스택을 켜지 못함: $work/start_all.log"; tail -5 "$work/start_all.log"; exit 4; }
  echo "스택 켜짐"; }
cmd=${1:-}; name=${2:-}
case "$cmd" in
  list) du -sh "$work"/스냅샷/* 2>/dev/null;;
  save)
    [ -n "$name" ] || { sed -n 2,5p "$0"; exit 2; }
    dir="$work/스냅샷/$name"; [ -e "$dir" ] && { echo "이미 있음: $dir"; exit 2; }; mkdir -p "$dir"; win=$(cd "$dir" && pwd -W)
    stop_stack
    for v in $VOLUMES; do docker volume inspect "$v" >/dev/null || { echo "볼륨 없음: $v"; exit 2; }
      MSYS_NO_PATHCONV=1 docker run --rm -v "$v:/v:ro" -v "$win:/b" "$IMAGE" tar -C /v -cf "/b/$v.tar" . || { echo "묶기 실패: $v"; exit 5; }
      test -s "$dir/$v.tar" || { echo "빈 묶음: $v"; exit 5; }; done
    start_stack; du -sh "$dir";;
  restore)
    dir="$work/스냅샷/$name"; [ -n "$name" ] && [ -d "$dir" ] || { echo "스냅샷 없음: $dir"; exit 2; }; win=$(cd "$dir" && pwd -W)
    for v in $VOLUMES; do test -s "$dir/$v.tar" || { echo "스냅샷에 없음: $v"; exit 2; }; done
    stop_stack
    for v in $VOLUMES; do MSYS_NO_PATHCONV=1 docker run --rm -v "$v:/v" -v "$win:/b:ro" "$IMAGE" sh -c "find /v -mindepth 1 -delete && tar -C /v -xf /b/$v.tar" || { echo "되돌리기 실패: $v"; exit 5; }; done
    start_stack;;
  *) sed -n 2,5p "$0"; exit 2;;
esac
