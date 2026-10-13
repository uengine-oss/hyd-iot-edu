# 점검 계획

## S03

**근거 상태: UNKNOWN** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

- status UNKNOWN, 원인의 verdict(HYPOTHESIS, RULED_OUT, CONFIRMED)에 대면 SUPPORTED

### 확인된 원인

- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: MATCH · 읽은 값 1.05

### 가설

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: MATCH · 읽은 값 58.0
  - `evd:fin-fouling-vs1-normal`: NO_MATCH · 읽은 값 1.05

### 해당 없음

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: NO_MATCH · 읽은 값 29.1

### 점검 순서

1. 팬 진동 VS1 평균 1.05 mm/s가 기준 0.9 mm/s를 초과했으므로 팬 구동 상태를 점검한다.
   - 근거: `evd:fan-drive-vs1-high`
   - 조치: SOP-FAN-11, SOP-FAN-12
2. 냉각 효율 CE 평균 58.0 %가 기준 70 % 미만으로 확인되었으므로 쿨러 핀 오염 가능성을 점검한다.
   - 근거: `evd:fin-fouling-ce-low`
   - 조치: SOP-COOL-14

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `read_sensor` `{"case_id": "S03"}`
3. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
4. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
5. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
6. `read_sensor` `{"case_id": "S03", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `read_sensor` `{"case_id": "S03", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `read_sensor` `{"case_id": "S03", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `get_actions` `{"failure_id": "fm:cooler-performance-loss"}`
10. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
