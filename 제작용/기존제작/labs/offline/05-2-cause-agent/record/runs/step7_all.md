# 점검 계획

## S01

**근거 상태: SUPPORTED** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: MATCH · 읽은 값 46.2
  - `evd:fin-fouling-vs1-normal`: MATCH · 읽은 값 0.575

### 가설

없음

### 해당 없음

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: NO_MATCH · 읽은 값 28.0
- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: NO_MATCH · 읽은 값 0.575

### 점검 순서

1. 쿨러 핀 오염에 따른 냉각 효율 저하를 확인하기 위해 핀 세척 후 냉각 효율 CE가 80 % 이상으로 회복되는지 점검한다.
   - 근거: `evd:fin-fouling-ce-low`
   - 조치: SOP-COOL-14

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `read_sensor` `{"case_id": "S01"}`
3. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
4. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
5. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
6. `read_sensor` `{"case_id": "S01", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `read_sensor` `{"case_id": "S01", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `read_sensor` `{"case_id": "S01", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `get_actions` `{"failure_id": "fm:cooler-performance-loss"}`
10. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`

## S02

**근거 상태: SUPPORTED** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: MATCH · 읽은 값 62.4
  - `evd:fin-fouling-vs1-normal`: MATCH · 읽은 값 0.61
- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: MATCH · 읽은 값 36.8

### 가설

없음

### 해당 없음

- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: NO_MATCH · 읽은 값 0.61

### 점검 순서

1. 캐비닛 온도 TS4 평균이 35 ℃ 이상인지 재확인한다.
   - 근거: `evd:ambient-ts4-high`
   - 조치: SOP-COOL-15
2. 쿨러 핀 오염에 따른 냉각 효율 저하를 확인하고 핀 세척을 진행한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-13, SOP-COOL-14
3. 주변 온도 상승에 따른 캐비닛 온도를 확인하고 환기를 보강한다.
   - 근거: `evd:ambient-ts4-high`
   - 조치: SOP-COOL-15

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `read_sensor` `{"case_id": "S02"}`
3. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
4. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
5. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
6. `read_sensor` `{"case_id": "S02", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `read_sensor` `{"case_id": "S02", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `read_sensor` `{"case_id": "S02", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `get_actions` `{"failure_id": "fm:cooler-performance-loss"}`
10. `read_sensor` `{"case_id": "S02", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`

## S03

**근거 상태: UNKNOWN** · 멈춤: 횟수 한도에 닿아 멈춤

### 대조

어긋남 없음

### 확인된 원인

없음

### 가설

없음

### 해당 없음

없음

### 점검 순서

1. 에이전트가 답을 내지 못했다. 사람이 직접 확인한다.

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
10. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 30}`
11. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 120}`
12. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 60}`
13. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 180}`
14. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 240}`
15. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 300}`
16. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 360}`
17. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 420}`
18. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 480}`
19. `read_sensor` `{"case_id": "S03", "tag": "TS1", "aggregate": "avg", "windowSeconds": 540}`

## S04

**근거 상태: SUPPORTED** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

- 펌프 축 씰 마모 (`cause:pump-seal-wear`)
  - `evd:ps1-low`: MATCH · 읽은 값 158.3
  - `evd:fs1-drop`: MATCH · 읽은 값 7.4

### 가설

없음

### 해당 없음

없음

### 점검 순서

1. 펌프 축 씰 마모를 확인하기 위해 축 씰 교체를 수행한다.
   - 근거: `evd:ps1-low`, `evd:fs1-drop`
   - 조치: SOP-PMP-04

### 호출 기록

1. `find_causes` `{"alarm": "PUMP_LEAKAGE"}`
2. `read_sensor` `{"case_id": "S04"}`
3. `get_evidence` `{"cause_id": "cause:pump-seal-wear"}`
4. `read_sensor` `{"case_id": "S04", "tag": "PS1", "aggregate": "avg", "windowSeconds": 120}`
5. `read_sensor` `{"case_id": "S04", "tag": "FS1", "aggregate": "avg", "windowSeconds": 120}`
6. `get_actions` `{"failure_id": "fm:volumetric-loss"}`

## S05

**근거 상태: UNKNOWN** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

없음

### 가설

- 펌프 축 씰 마모 (`cause:pump-seal-wear`)
  - `evd:ps1-low`: MATCH · 읽은 값 163.2
  - `evd:fs1-drop`: NO_MATCH · 읽은 값 8.3

### 해당 없음

없음

### 점검 순서

1. 유량 평균 8.0 l/min 미만 여부를 FS1 센서로 재확인한다.
   - 근거: `evd:fs1-drop`
   - 조치: SOP-PMP-04

### 호출 기록

1. `find_causes` `{"alarm": "PUMP_LEAKAGE"}`
2. `read_sensor` `{"case_id": "S05"}`
3. `get_evidence` `{"cause_id": "cause:pump-seal-wear"}`
4. `read_sensor` `{"case_id": "S05", "tag": "PS1", "aggregate": "avg", "windowSeconds": 120}`
5. `read_sensor` `{"case_id": "S05", "tag": "FS1", "aggregate": "avg", "windowSeconds": 120}`
6. `get_actions` `{"failure_id": "fm:volumetric-loss"}`
7. `read_sensor` `{"case_id": "S05", "tag": "PS1", "aggregate": "avg", "windowSeconds": 120}`

## S06

**근거 상태: SUPPORTED** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

- 팬 베어링 마모 (`cause:fan-bearing-wear`)
  - `evd:vs1-trend`: MATCH · 읽은 값 0.34
  - `evd:ts1-normal`: MATCH · 읽은 값 49.2

### 가설

없음

### 해당 없음

없음

### 점검 순서

1. 팬 베어링 마모에 대한 근본 조치(베어링 교체)를 진행한다.
   - 근거: `evd:vs1-trend`, `evd:ts1-normal`
   - 조치: SOP-FAN-03, SOP-FAN-04

### 호출 기록

1. `find_causes` `{"alarm": "FAN_VIBRATION"}`
2. `read_sensor` `{"case_id": "S06"}`
3. `get_evidence` `{"cause_id": "cause:fan-bearing-wear"}`
4. `read_sensor` `{"case_id": "S06", "tag": "VS1", "aggregate": "max-min", "windowSeconds": 300}`
5. `read_sensor` `{"case_id": "S06", "tag": "TS1", "aggregate": "avg", "windowSeconds": 120}`
6. `get_actions` `{"failure_id": "fm:bearing-degradation"}`
7. `get_actions` `{"failure_id": "fm:high-vibration-trip"}`

## S07

**근거 상태: SUPPORTED** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: MATCH · 읽은 값 51.0
  - `evd:fin-fouling-vs1-normal`: MATCH · 읽은 값 0.58

### 가설

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: NOT_CHECKED · 읽은 값 null

### 해당 없음

- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: NO_MATCH · 읽은 값 0.58

### 점검 순서

1. 캐비닛 온도 TS4 평균값을 다시 확인한다.
   - 근거: `evd:ambient-ts4-high`
   - 조치: SOP-COOL-15
2. 쿨러 핀 오염에 대한 근본 조치를 수행한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-14

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `read_sensor` `{"case_id": "S07"}`
3. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
4. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
5. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
6. `read_sensor` `{"case_id": "S07", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `read_sensor` `{"case_id": "S07", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `read_sensor` `{"case_id": "S07", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `get_actions` `{"failure_id": "fm:cooler-performance-loss"}`
10. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`

## S08

**근거 상태: UNKNOWN** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

없음

### 가설

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: NOT_CHECKED · 읽은 값 66.1
  - `evd:fin-fouling-vs1-normal`: MATCH · 읽은 값 0.6

### 해당 없음

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: NO_MATCH · 읽은 값 30.2
- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: NO_MATCH · 읽은 값 0.6

### 점검 순서

1. CE 센서의 커버리지 공백을 해소하여 최근 30초 냉각 효율 평균을 다시 확인한다.
   - 근거: `evd:fin-fouling-ce-low`
2. 쿨러 핀 오염 여부를 확인하기 위해 핀 상태를 점검한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-14

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `read_sensor` `{"case_id": "S08"}`
3. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
4. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
5. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
6. `read_sensor` `{"case_id": "S08", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `read_sensor` `{"case_id": "S08", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `read_sensor` `{"case_id": "S08", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `get_actions` `{"failure_id": "fm:cooler-performance-loss"}`
10. `read_sensor` `{"case_id": "S08", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`

## S09

**근거 상태: SUPPORTED** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: MATCH · 읽은 값 48.9
  - `evd:fin-fouling-vs1-normal`: MATCH · 읽은 값 0.57

### 가설

없음

### 해당 없음

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: NO_MATCH · 읽은 값 28.3
- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: NO_MATCH · 읽은 값 0.57

### 점검 순서

1. 신선도가 만료된 TS1(유온) 값을 최신 데이터로 다시 확인한다.
2. 쿨러 핀 오염에 대한 근본 조치로 핀 세척을 수행한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-14

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `read_sensor` `{"case_id": "S09"}`
3. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
4. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
5. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
6. `read_sensor` `{"case_id": "S09", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `read_sensor` `{"case_id": "S09", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `read_sensor` `{"case_id": "S09", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `get_actions` `{"failure_id": "fm:cooler-performance-loss"}`
10. `read_sensor` `{"case_id": "S09", "tag": "TS1", "aggregate": "avg", "windowSeconds": 30}`
11. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`

## S10

**근거 상태: UNKNOWN** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

- cause:fan-bearing-wear: verdict HYPOTHESIS, 증거의 result(NO_MATCH, NO_MATCH)에 대면 RULED_OUT

### 확인된 원인

없음

### 가설

- 팬 베어링 마모 (`cause:fan-bearing-wear`)
  - `evd:vs1-trend`: NO_MATCH · 읽은 값 0.12
  - `evd:ts1-normal`: NO_MATCH · 읽은 값 56.3

### 해당 없음

없음

### 점검 순서

1. VS1 진동 상승폭(최근 5분 max-min)이 0.2 mm/s를 초과하는지 재확인한다.
   - 근거: `evd:vs1-trend`
   - 조치: SOP-FAN-03, SOP-FAN-04
2. TS1 유온(최근 120초 평균)이 52 ℃ 미만인지 재확인한다.
   - 근거: `evd:ts1-normal`
   - 조치: SOP-FAN-03, SOP-FAN-04

### 호출 기록

1. `find_causes` `{"alarm": "FAN_VIBRATION"}`
2. `read_sensor` `{"case_id": "S10"}`
3. `get_evidence` `{"cause_id": "cause:fan-bearing-wear"}`
4. `read_sensor` `{"case_id": "S10", "tag": "VS1", "aggregate": "max-min", "windowSeconds": 300}`
5. `read_sensor` `{"case_id": "S10", "tag": "TS1", "aggregate": "avg", "windowSeconds": 120}`
6. `get_actions` `{"failure_id": "fm:bearing-degradation"}`
7. `get_actions` `{"failure_id": "fm:high-vibration-trip"}`
8. `get_evidence` `{"cause_id": "cause:fan-bearing-wear"}`

## S11

**근거 상태: UNKNOWN** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

없음

### 가설

- 고온 운전에 의한 산화 (`cause:oil-oxidation`)
  - 증거: 없음
- 수분 혼입 (`cause:water-ingress`)
  - 증거: 없음
- 오염 입자 유입 (`cause:particle-contamination`)
  - 증거: 없음
- 교환 주기 초과 (`cause:change-interval-exceeded`)
  - 증거: 없음

### 해당 없음

없음

### 점검 순서

1. 고온 운전에 의한 산화 원인의 증거가 등록되지 않아 확인이 필요함
2. 수분 혼입 원인의 증거가 등록되지 않아 확인이 필요함
3. 오염 입자 유입 원인의 증거가 등록되지 않아 확인이 필요함
4. 교환 주기 초과 원인의 증거가 등록되지 않아 확인이 필요함

### 호출 기록

1. `find_causes` `{"alarm": "OIL_ANALYSIS"}`
2. `read_sensor` `{"case_id": "S11"}`
3. `get_evidence` `{"cause_id": "cause:oil-oxidation"}`
4. `get_evidence` `{"cause_id": "cause:water-ingress"}`
5. `get_evidence` `{"cause_id": "cause:particle-contamination"}`
6. `get_evidence` `{"cause_id": "cause:change-interval-exceeded"}`
7. `get_actions` `{"failure_id": "fm:oil-degradation"}`
