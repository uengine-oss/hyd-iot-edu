# 점검 계획

## S01

**근거 상태: SUPPORTED** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

- 호출 기록에 없는 절차 번호: HM-8.4

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

1. 쿨러 핀 오염을 확인하기 위해 냉각 효율과 팬 진동을 점검한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: HM-8.4

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `read_sensor` `{"case_id": "S01"}`
3. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
4. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
5. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
6. `read_sensor` `{"case_id": "S01", "tag": "CE", "aggregate": "avg", "windowSeconds": 30}`
7. `read_sensor` `{"case_id": "S01", "tag": "VS1", "aggregate": "avg", "windowSeconds": 120}`
8. `read_sensor` `{"case_id": "S01", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
9. `read_sensor` `{"case_id": "S01", "tag": "TS4", "aggregate": "avg", "windowSeconds": 120}`
