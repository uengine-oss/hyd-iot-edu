#!/bin/bash
# Create the 7 Kafka topics of v3 section 5.2 (single partition, single replica for the student edition)
set -e
B=${KAFKA_BOOTSTRAP:-redpanda:9092}
DAY=86400000
create() { rpk topic create "$1" --brokers "$B" -p 1 -r 1 -c "retention.ms=$2" 2>&1 | grep -v -i "already exists" || true; }
create plant.tag     $((DAY))          # 경량: 1일 (DB에 적재되므로 Kafka는 짧게)
create plant.wave    $((DAY / 4))      # DAQ_PROFILE=full일 때만 쓰임
create plant.status  $((7*DAY))
create feat.1s       $((3*DAY))
create alerts        $((365*DAY))
create action.cmd    $((365*DAY))
create audit         $((5*365*DAY))
# 이미 만들어진 토픽에도 보존 기간을 맞춘다 (재실행 안전)
for tr in "plant.tag $((DAY))" "plant.wave $((DAY / 4))" "feat.1s $((3*DAY))" "plant.status $((7*DAY))"; do
  set -- $tr; rpk topic alter-config "$1" --brokers "$B" --set "retention.ms=$2" >/dev/null 2>&1 || true
done
rpk topic list --brokers "$B"
