#!/bin/bash
# Create the 7 Kafka topics of v3 section 5.2 (single partition, single replica for the student edition)
# 「이미 있음」(rpk: TOPIC_ALREADY_EXISTS)만 통과다. 다른 실패는 종료 코드 1 — compose 의 service_completed_successfully 가
# 하류 서비스(connect-* · detector · process · agent) 기동을 막는다(토픽 없이 뜬 서비스가 조용히 기다리지 않게).
set -euo pipefail
B=${KAFKA_BOOTSTRAP:-redpanda:9092}
DAY=86400000
create() {
  local out
  if out=$(rpk topic create "$1" --brokers "$B" -p 1 -r 1 -c "retention.ms=$2" 2>&1); then echo "$out"; return 0; fi
  if printf '%s' "$out" | grep -qiE 'already[ _]exists'; then echo "$1: 이미 있음"; return 0; fi
  printf '%s\n토픽 %s 을 만들지 못했습니다.\n' "$out" "$1" >&2
  exit 1
}
create plant.tag     $((DAY))          # 경량: 1일 (DB에 적재되므로 Kafka는 짧게)
create plant.wave    $((DAY / 4))      # DAQ_PROFILE=full일 때만 쓰임
create plant.status  $((7*DAY))
create feat.1s       $((3*DAY))
create alerts        $((365*DAY))
create action.cmd    $((365*DAY))
create audit         $((5*365*DAY))
# 이미 만들어진 토픽에도 보존 기간을 맞춘다 (재실행 안전) — 실패하면 그대로 실패
for tr in "plant.tag $((DAY))" "plant.wave $((DAY / 4))" "feat.1s $((3*DAY))" "plant.status $((7*DAY))"; do
  set -- $tr
  rpk topic alter-config "$1" --brokers "$B" --set "retention.ms=$2" >/dev/null || { echo "토픽 $1 의 보존 기간을 맞추지 못했습니다." >&2; exit 1; }
done
rpk topic list --brokers "$B"
