# 작업 확인 카드 — SOP-COOL-14 쿨러 핀 세척

## 대상 작업

- SOP-COOL-14 쿨러 핀 세척 — 근거 문서 HM-8 1.1판(현행, 시행 2026-09-01) HM-8.7

## 준비 조건

- HM-8 1.1 HM-8.7: 「원인에 맞는 근본 조치를 CMMS 작업지시로 발행한다.」(검토 HM-8_1.1_검토.json#HM-8-M058)

## 금지 · 제한

- HM-8 1.1 HM-8.7: 「고압수는 쓰지 않는다.」(검토 HM-8_1.1_검토.json#HM-8-M061)
- OEM-HPP45A-MM C 7: 「Do not use a high-pressure washer.」(검토 OEM-HPP45A-MM_C_검토.json#OEM-HPP45A-MM-M053)

## 작업 순서

1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다. — HM-8 1.1 HM-8.7 「1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.」
2. 압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다. — HM-8 1.1 HM-8.7 「압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.」
3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다. — HM-8 1.1 HM-8.7 「3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.」

## 완료 기준

- HM-8 1.1 HM-8.7: 「재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.」(검토 HM-8_1.1_검토.json#HM-8-R28)

## 작업 직전 확인할 현재 값

- 쿨러 냉각 효율 CE · 유온 TS1(HYD-02) — 그래프에 없는 현재 값. 시계열(관측값)에서 읽는다(근거 HM-8_매뉴얼.md:79).
- PLC 운전 모드 · 상태 — 그래프에 없는 현재 값. PLC 상태 수신(시계열)에서 읽는다(근거 HM-8_매뉴얼.md:77).

## 승인

- 설비보전팀장 — 받은 SOP 구조. 카드는 승인을 대신하지 않는다.
- HM-8 1.1 HM-8.7: 「승인은 설비보전팀장이 한다.」(검토 HM-8_1.1_검토.json#HM-8-R27)

## 남은 질문

- 세척 전에 코어를 살펴 막힌 곳과 휘거나 손상된 핀을 기록한다. — 보류 · OEM-HPP45A-MM C 7 107줄
- 세척 뒤에도 막힌 곳이나 휜 핀이 남으면 코어를 교체한다. — 보류 · OEM-HPP45A-MM C 7 114줄
- After cleaning or replacement, run the unit at working load for 30 minutes and record the fluid temperature at the cooler inlet and outlet. The difference must not be less than the value in the commissioning record. — 보류 · OEM-HPP45A-MM C 7 116줄
- 트립 뒤 복귀 조건(조건표 R5의 출처 HM-9.4) — 제공되지 않은 절 · 자료/HM-9장_스캔본.txt 목차 HM-9.4(9-7쪽)
- SOP-COOL-14 쿨러 냉각 효율 CE · 유온 TS1(HYD-02) — 현재 값 필요 · 시계열(관측값)
- SOP-COOL-14 PLC 운전 모드 · 상태 — 현재 값 필요 · PLC 상태 수신(시계열)
