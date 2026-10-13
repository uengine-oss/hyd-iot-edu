# 점검 계획

## S01

**근거 상태: SUPPORTED** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: 맞음 · 읽은 값 46.2
  - `evd:fin-fouling-vs1-normal`: 맞음 · 읽은 값 0.575

### 가설

없음

### 해당 없음

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: 아님 · 읽은 값 28.0
- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: 아님 · 읽은 값 0.575

### 점검 순서

1. 쿨러 핀 오염에 따른 냉각 효율 저하를 확인하고 핀 세척을 진행한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-13, SOP-COOL-14

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "COOLER_DEGRADATION"}`
2. `센서_집계` 물음 `{"사례": "S01"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:cooler-fin-fouling"}`
4. `증거_기준` 물음 `{"원인_식별자": "cause:ambient-high-temp"}`
5. `증거_기준` 물음 `{"원인_식별자": "cause:fan-drive-fault"}`
6. `센서_집계` 물음 `{"사례": "S01", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `센서_집계` 물음 `{"사례": "S01", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `센서_집계` 물음 `{"사례": "S01", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`
10. `조치_방법` 물음 `{"고장_유형_식별자": "fm:overheat-trip"}`

## S02

**근거 상태: SUPPORTED** · 멈춤: 같은 물음을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: 맞음 · 읽은 값 62.4
  - `evd:fin-fouling-vs1-normal`: 맞음 · 읽은 값 0.61
- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: 맞음 · 읽은 값 36.8

### 가설

없음

### 해당 없음

- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: 아님 · 읽은 값 0.61

### 점검 순서

1. 쿨러 핀 오염에 대해 부하 70 %로 낮추고 야간 핀 세척을 지시한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-13, SOP-COOL-14
2. 주변 온도 상승에 대해 캐비닛 환기를 보강한다.
   - 근거: `evd:ambient-ts4-high`
   - 조치: SOP-COOL-15

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "COOLER_DEGRADATION"}`
2. `센서_집계` 물음 `{"사례": "S02"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:cooler-fin-fouling"}`
4. `증거_기준` 물음 `{"원인_식별자": "cause:ambient-high-temp"}`
5. `증거_기준` 물음 `{"원인_식별자": "cause:fan-drive-fault"}`
6. `센서_집계` 물음 `{"사례": "S02", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `센서_집계` 물음 `{"사례": "S02", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `센서_집계` 물음 `{"사례": "S02", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`
10. `조치_방법` 물음 `{"고장_유형_식별자": "fm:overheat-trip"}`
11. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`

## S03

**근거 상태: UNKNOWN** · 멈춤: 같은 물음을 되풀이해 도구를 거두고 답을 받음

### 대조

- 근거_상태 UNKNOWN, 원인의 구분(가설, 해당_없음, 확인됨)에 대면 SUPPORTED

### 확인된 원인

- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: 맞음 · 읽은 값 1.05

### 가설

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: 맞음 · 읽은 값 58.0
  - `evd:fin-fouling-vs1-normal`: 아님 · 읽은 값 1.05

### 해당 없음

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: 아님 · 읽은 값 29.1

### 점검 순서

1. 팬 구동 불량을 확인하기 위해 팬 벨트 처짐과 베어링 상태를 점검한다.
   - 근거: `evd:fan-drive-vs1-high`
   - 조치: SOP-FAN-11, SOP-FAN-12
2. 쿨러 핀 오염 가설을 확인하기 위해 핀 상태를 점검하고 세척을 준비한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-14

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "COOLER_DEGRADATION"}`
2. `센서_집계` 물음 `{"사례": "S03"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:cooler-fin-fouling"}`
4. `증거_기준` 물음 `{"원인_식별자": "cause:ambient-high-temp"}`
5. `증거_기준` 물음 `{"원인_식별자": "cause:fan-drive-fault"}`
6. `센서_집계` 물음 `{"사례": "S03", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `센서_집계` 물음 `{"사례": "S03", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `센서_집계` 물음 `{"사례": "S03", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`
10. `조치_방법` 물음 `{"고장_유형_식별자": "fm:overheat-trip"}`
11. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`

## S04

**근거 상태: SUPPORTED** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

- 펌프 축 씰 마모 (`cause:pump-seal-wear`)
  - `evd:ps1-low`: 맞음 · 읽은 값 158.3
  - `evd:fs1-drop`: 맞음 · 읽은 값 7.4

### 가설

없음

### 해당 없음

없음

### 점검 순서

1. 펌프 축 씰 마모를 확인하고 씰 키트를 교체한다.
   - 근거: `evd:ps1-low`, `evd:fs1-drop`
   - 조치: SOP-PMP-04

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "PUMP_LEAKAGE"}`
2. `센서_집계` 물음 `{"사례": "S04"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:pump-seal-wear"}`
4. `센서_집계` 물음 `{"사례": "S04", "tag": "PS1", "aggregate": "avg", "windowSeconds": 120}`
5. `센서_집계` 물음 `{"사례": "S04", "tag": "FS1", "aggregate": "avg", "windowSeconds": 120}`
6. `조치_방법` 물음 `{"고장_유형_식별자": "fm:volumetric-loss"}`

## S05

**근거 상태: UNKNOWN** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

없음

### 가설

- 펌프 축 씰 마모 (`cause:pump-seal-wear`)
  - `evd:ps1-low`: 맞음 · 읽은 값 163.2
  - `evd:fs1-drop`: 아님 · 읽은 값 8.3

### 해당 없음

없음

### 점검 순서

1. 유량 FS1 평균이 8.0 l/min 미만인지 재확인하여 축 씰 마모 가설을 판정한다.
   - 근거: `evd:fs1-drop`
   - 조치: SOP-PMP-04

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "PUMP_LEAKAGE"}`
2. `센서_집계` 물음 `{"사례": "S05"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:pump-seal-wear"}`
4. `센서_집계` 물음 `{"사례": "S05", "tag": "PS1", "aggregate": "avg", "windowSeconds": 120}`
5. `센서_집계` 물음 `{"사례": "S05", "tag": "FS1", "aggregate": "avg", "windowSeconds": 120}`
6. `조치_방법` 물음 `{"고장_유형_식별자": "fm:volumetric-loss"}`

## S06

**근거 상태: SUPPORTED** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

- 팬 베어링 마모 (`cause:fan-bearing-wear`)
  - `evd:vs1-trend`: 맞음 · 읽은 값 0.34
  - `evd:ts1-normal`: 맞음 · 읽은 값 49.2

### 가설

없음

### 해당 없음

없음

### 점검 순서

1. 팬 베어링 마모에 대한 근본 조치로 계획 정지 후 베어링을 교체한다.
   - 근거: `evd:vs1-trend`, `evd:ts1-normal`
   - 조치: SOP-FAN-03, SOP-FAN-04

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "FAN_VIBRATION"}`
2. `센서_집계` 물음 `{"사례": "S06"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:fan-bearing-wear"}`
4. `센서_집계` 물음 `{"사례": "S06", "tag": "VS1", "aggregate": "max-min", "windowSeconds": 300}`
5. `센서_집계` 물음 `{"사례": "S06", "tag": "TS1", "aggregate": "avg", "windowSeconds": 120}`
6. `조치_방법` 물음 `{"고장_유형_식별자": "fm:bearing-degradation"}`

## S07

**근거 상태: SUPPORTED** · 멈춤: 같은 물음을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: 맞음 · 읽은 값 51.0
  - `evd:fin-fouling-vs1-normal`: 맞음 · 읽은 값 0.58

### 가설

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: 확인하지_못함 · 읽은 값 null

### 해당 없음

- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: 아님 · 읽은 값 0.58

### 점검 순서

1. 캐비닛 온도 TS4 평균값을 다시 확인한다.
   - 근거: `evd:ambient-ts4-high`
   - 조치: SOP-COOL-15
2. 쿨러 핀 오염에 대한 근본 조치를 수행한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-14

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "COOLER_DEGRADATION"}`
2. `센서_집계` 물음 `{"사례": "S07"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:cooler-fin-fouling"}`
4. `증거_기준` 물음 `{"원인_식별자": "cause:ambient-high-temp"}`
5. `증거_기준` 물음 `{"원인_식별자": "cause:fan-drive-fault"}`
6. `센서_집계` 물음 `{"사례": "S07", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `센서_집계` 물음 `{"사례": "S07", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `센서_집계` 물음 `{"사례": "S07", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`
10. `조치_방법` 물음 `{"고장_유형_식별자": "fm:overheat-trip"}`
11. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`

## S08

**근거 상태: UNKNOWN** · 멈춤: 같은 물음을 되풀이해 도구를 거두고 답을 받음

### 대조

어긋남 없음

### 확인된 원인

없음

### 가설

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: 확인하지_못함 · 읽은 값 66.1
  - `evd:fin-fouling-vs1-normal`: 맞음 · 읽은 값 0.6

### 해당 없음

- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: 아님 · 읽은 값 30.2
- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: 아님 · 읽은 값 0.6

### 점검 순서

1. 최근 30초 냉각 효율 CE 평균 값을 재확인한다.
   - 근거: `evd:fin-fouling-ce-low`
2. 쿨러 핀 오염 여부를 확인한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-14

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "COOLER_DEGRADATION"}`
2. `센서_집계` 물음 `{"사례": "S08"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:cooler-fin-fouling"}`
4. `증거_기준` 물음 `{"원인_식별자": "cause:ambient-high-temp"}`
5. `증거_기준` 물음 `{"원인_식별자": "cause:fan-drive-fault"}`
6. `센서_집계` 물음 `{"사례": "S08", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `센서_집계` 물음 `{"사례": "S08", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `센서_집계` 물음 `{"사례": "S08", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`
10. `조치_방법` 물음 `{"고장_유형_식별자": "fm:overheat-trip"}`
11. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`

## S09

**근거 상태: UNKNOWN** · 멈춤: 답을 냄

### 대조

어긋남 없음

### 확인된 원인

없음

### 가설

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: 확인하지_못함 · 읽은 값 48.9
  - `evd:fin-fouling-vs1-normal`: 확인하지_못함 · 읽은 값 0.57
- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: 확인하지_못함 · 읽은 값 28.3
- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: 확인하지_못함 · 읽은 값 0.57

### 해당 없음

없음

### 점검 순서

1. 신선도가 만료된 TS1 관측을 갱신한 뒤 CE·VS1·TS4 값을 다시 확인한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`, `evd:ambient-ts4-high`, `evd:fan-drive-vs1-high`
2. 쿨러 핀 오염 여부를 확인하기 위해 냉각 효율 CE와 팬 진동 VS1을 재점검한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: SOP-COOL-14
3. 주변 온도 상승 여부를 확인하기 위해 캐비닛 온도 TS4를 재점검한다.
   - 근거: `evd:ambient-ts4-high`
   - 조치: SOP-COOL-15
4. 팬 구동 불량 여부를 확인하기 위해 팬 진동 VS1을 재점검한다.
   - 근거: `evd:fan-drive-vs1-high`
   - 조치: SOP-FAN-11

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "COOLER_DEGRADATION"}`
2. `센서_집계` 물음 `{"사례": "S09"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:cooler-fin-fouling"}`
4. `증거_기준` 물음 `{"원인_식별자": "cause:ambient-high-temp"}`
5. `증거_기준` 물음 `{"원인_식별자": "cause:fan-drive-fault"}`
6. `센서_집계` 물음 `{"사례": "S09", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `센서_집계` 물음 `{"사례": "S09", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `센서_집계` 물음 `{"사례": "S09", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `조치_방법` 물음 `{"고장_유형_식별자": "fm:cooler-performance-loss"}`
10. `조치_방법` 물음 `{"고장_유형_식별자": "fm:overheat-trip"}`

## S10

**근거 상태: UNKNOWN** · 멈춤: 답을 냄

### 대조

- 근거_상태 UNKNOWN, 원인의 구분(해당_없음)에 대면 UNSUPPORTED

### 확인된 원인

없음

### 가설

없음

### 해당 없음

- 팬 베어링 마모 (`cause:fan-bearing-wear`)
  - `evd:vs1-trend`: 아님 · 읽은 값 0.12
  - `evd:ts1-normal`: 아님 · 읽은 값 56.3

### 점검 순서

없음

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "FAN_VIBRATION"}`
2. `센서_집계` 물음 `{"사례": "S10"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:fan-bearing-wear"}`
4. `센서_집계` 물음 `{"사례": "S10", "tag": "VS1", "aggregate": "max-min", "windowSeconds": 300}`
5. `센서_집계` 물음 `{"사례": "S10", "tag": "TS1", "aggregate": "avg", "windowSeconds": 120}`
6. `조치_방법` 물음 `{"고장_유형_식별자": "fm:bearing-degradation"}`

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

없음

### 호출 기록

1. `원인_후보` 물음 `{"패턴_코드": "OIL_ANALYSIS"}`
2. `센서_집계` 물음 `{"사례": "S11"}`
3. `증거_기준` 물음 `{"원인_식별자": "cause:oil-oxidation"}`
4. `증거_기준` 물음 `{"원인_식별자": "cause:water-ingress"}`
5. `증거_기준` 물음 `{"원인_식별자": "cause:particle-contamination"}`
6. `증거_기준` 물음 `{"원인_식별자": "cause:change-interval-exceeded"}`
7. `조치_방법` 물음 `{"고장_유형_식별자": "fm:oil-degradation"}`
