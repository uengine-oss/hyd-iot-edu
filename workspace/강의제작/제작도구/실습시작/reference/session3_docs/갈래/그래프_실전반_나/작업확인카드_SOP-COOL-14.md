# 작업 확인 카드 — SOP-COOL-14 쿨러 핀 세척

## 대상 작업

- SOP-COOL-14 쿨러 핀 세척 — 근거 문서 HM-8 1.1판(현행, 시행 2026-09-01) HM-8.7 · 설비 HYD-02(같은 모델 HYD-01 · HYD-03)

## 준비 조건

- HM-8 1.1 HM-8.7: 「원인에 맞는 근본 조치를 CMMS 작업지시로 발행한다.」(후보 HM-8-M058)
- OEM-HPP45A-MM C 7: 「Stop the pump, lock out the motor supply, and wait until the fan has stopped.」(후보 OEM-HPP45A-MM-M050)

## 금지 · 제한

- HM-8 1.1 HM-8.7: 「고압수는 쓰지 않는다.」(후보 HM-8-M061)
- OEM-HPP45A-MM C 7: 「Do not use a high-pressure washer.」(후보 OEM-HPP45A-MM-M053)
- OEM-HPP45A-MM C 7: 「Do not use a high-pressure washer. High-pressure water bends the fins.」(후보 OEM-HPP45A-MM-R07)

## 작업 순서

1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다. — HM-8 1.1 HM-8.7 「설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.」
2. 압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다. — HM-8 1.1 HM-8.7 「압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.」
3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다. — HM-8 1.1 HM-8.7 「재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.」

## 완료 기준

- HM-8 1.1 HM-8.7: 「재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.」(후보 HM-8-R28)

## 작업 직전 확인할 현재 값

- 쿨러 냉각 효율 CE · 유온 TS1(HYD-02) — 그래프에 없는 현재 값. 시계열(관측값)에서 읽는다. 문서의 기준값(완료 기준)과 구별한다.
- PLC 운전 모드 · 상태 — 그래프에 없는 현재 값. PLC 상태 수신(시계열)에서 읽는다.

## 승인

- 설비보전팀장 — 원문(HM-8 1.1 HM-8.7). 카드는 승인을 대신하지 않는다.

## 남은 질문

- 트립 뒤 복귀 조건(R5 출처 HM-9.4) — 제공되지 않은 절 · 자료/HM-9장_스캔본.txt 15줄 · 9-7쪽 없음 — 원본 확인 요청
- HPP-45B(HYD-04) 정비 지침 — 제공되지 않은 문서 · 자료/문서_목록.csv · 제조사에 요청 중 — 파일 없음
- 세척 전에 코어를 살펴 막힌 곳과 휘거나 손상된 핀을 기록한다. — 보류 · OEM-HPP45A-MM C 7 107줄 · 사내 기준이 정하지 않은 제조사 항목 — 세척 전 코어 막힘 · 휨 확인(HM-8 · PM-02에 없음) — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다
- 세척 뒤에도 막힌 곳이나 휜 핀이 남으면 코어를 교체한다. — 보류 · OEM-HPP45A-MM C 7 114줄 · 사내 기준이 정하지 않은 제조사 항목 — 세척 뒤 막힘 · 휨이 남으면 코어 교체(HM-8 · PM-02에 없음) — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다
- After cleaning or replacement, run the unit at working load for 30 minutes and record the fluid temperature at the cooler inlet and outlet. The difference must not be less than the value in the commissioning record. — 보류 · OEM-HPP45A-MM C 7 116줄 · 사내 기준이 정하지 않은 제조사 항목 — 부하 운전 뒤 쿨러 입구 · 출구 유온 차 확인(HM-8의 완료 기준은 CE 80 %) — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다 — 이 항목을 담은 후보가 없어(까닭은 missing의 note) 검토자가 원문 문장으로 더함
