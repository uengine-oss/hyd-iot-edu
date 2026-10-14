# 점검 계획

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

1. 펌프 축 씰 마모를 확인하기 위해 축 씰 교체를 진행한다.
   - 근거: `evd:ps1-low`, `evd:fs1-drop`
   - 조치: SOP-PMP-04

### 호출 기록

1. `find_causes` `{"alarm": "PUMP_LEAKAGE"}`
2. `read_sensor` `{"case_id": "S04"}`
3. `get_evidence` `{"cause_id": "cause:pump-seal-wear"}`
4. `read_sensor` `{"case_id": "S04", "tag": "PS1", "aggregate": "avg", "windowSeconds": 120}`
5. `read_sensor` `{"case_id": "S04", "tag": "FS1", "aggregate": "avg", "windowSeconds": 120}`
6. `get_actions` `{"failure_id": "fm:volumetric-loss"}`
