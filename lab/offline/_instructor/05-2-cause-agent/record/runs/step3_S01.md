# 점검 계획

## S01

**근거 상태: UNKNOWN** · 멈춤: 같은 호출을 되풀이해 도구를 거두고 답을 받음

### 대조

- 호출 기록에 없는 절차 번호: HM-8.4
- 호출 기록에 없는 절차 번호: HM-8.4
- 호출 기록에 없는 절차 번호: HM-8.4

### 확인된 원인

없음

### 가설

- 쿨러 핀 오염 (`cause:cooler-fin-fouling`)
  - `evd:fin-fouling-ce-low`: NOT_CHECKED · 읽은 값 null
  - `evd:fin-fouling-vs1-normal`: NOT_CHECKED · 읽은 값 null
- 주변 온도 상승 (`cause:ambient-high-temp`)
  - `evd:ambient-ts4-high`: NOT_CHECKED · 읽은 값 null
- 팬 구동 불량 (`cause:fan-drive-fault`)
  - `evd:fan-drive-vs1-high`: NOT_CHECKED · 읽은 값 null

### 해당 없음

없음

### 점검 순서

1. 확인하지 못한 센서 값을 다시 확인한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`, `evd:ambient-ts4-high`, `evd:fan-drive-vs1-high`
2. 쿨러 핀 오염 여부를 점검한다.
   - 근거: `evd:fin-fouling-ce-low`, `evd:fin-fouling-vs1-normal`
   - 조치: HM-8.4
3. 주변 온도 상승 여부를 점검한다.
   - 근거: `evd:ambient-ts4-high`
   - 조치: HM-8.4
4. 팬 구동 불량 여부를 점검한다.
   - 근거: `evd:fan-drive-vs1-high`
   - 조치: HM-8.4

### 호출 기록

1. `find_causes` `{"alarm": "COOLER_DEGRADATION"}`
2. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
3. `get_evidence` `{"cause_id": "cause:ambient-high-temp"}`
4. `get_evidence` `{"cause_id": "cause:fan-drive-fault"}`
5. `get_evidence` `{"cause_id": "cause:cooler-fin-fouling"}`
