# 작업 확인 카드 — SOP-COOL-14 쿨러 핀 세척

## 대상 작업

- SOP-COOL-14 쿨러 핀 세척 — 근거 문서 HM-8 1.1판(현행, 시행 2026-09-01) HM-8.7 · 설비 HYD-02(같은 모델 HYD-01 · HYD-03)

## 준비 조건

- OEM-HPP45A-MM C 7: 「Stop the pump, lock out the motor supply, and wait until the fan has stopped.」(후보 OEM-HPP45A-MM-062)

## 금지 · 제한

- HM-8 1.1 HM-8.7: 「고압수는 쓰지 않는다.」(후보 HM-8-089)
- OEM-HPP45A-MM C 7: 「Do not use a high-pressure washer. High-pressure water bends the fins.」(후보 OEM-HPP45A-MM-067)
- OEM-HPP45A-MM C 7: 「Do not use a high-pressure washer.」(후보 OEM-HPP45A-MM-068)

## 작업 순서

1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다. — HM-8 1.1 HM-8.7 「설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.」
2. 압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다. — HM-8 1.1 HM-8.7 「압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.」
3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다. — HM-8 1.1 HM-8.7 「재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.」

## 완료 기준

- HM-8 1.1 HM-8.7: 「재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.」(후보 HM-8-091)

## 작업 직전 확인할 현재 값

- 쿨러 냉각 효율 CE · 유온 TS1(HYD-02) — 그래프에 없는 현재 값. 시계열(관측값)에서 읽는다. 문서의 기준값(완료 기준)과 구별한다.
- PLC 운전 모드 · 상태 — 그래프에 없는 현재 값. PLC 상태 수신(시계열)에서 읽는다.

## 부품 준비

- 없음 — 이 작업의 단계 · 조건에 품번이 붙은 부품이 없다(재고 기준: ERP 재고 내보내기 2026-10-28 07:00)

## 지난 시행 기록

- WO-2025-04112 3호기(HYD-03) · 완료 · 완료 2026-01-01 · 기록 그대로: 「CLR fin 에어블로우 HM-7.6」 · 측정: CE 85 % · 옛 판 번호(HM-8 1.0 SOP-COOL-04)로 적힌 시행
- WO-2026-04129 2호기(HYD-02) · 완료 · 완료 2026-04-08 · 기록 그대로: 「열교환기 핀 청소 SOP-COOL-04」 · 측정: 기록 없음 — 완료 기준(CE 80 %)을 보여 주지 않음 · 옛 판 번호(HM-8 1.0 SOP-COOL-04)로 적힌 시행
- WO-2026-04143 1호기(HYD-01) · 완료 · 완료 2026-06-20 · 기록 그대로: 「SOP-COOL-04 핀세척. 저압수 세척 후 건조」 · 측정: CE 77 · 옛 판 번호(HM-8 1.0 SOP-COOL-04)로 적힌 시행
- WO-2026-04154 3호기(HYD-03) · 완료 · 완료 2026-08-09 · 기록 그대로: 「야간 핀 세척 (SOP-COOL-04) 압축공기」 · 측정: CE 79 % · 옛 판 번호(HM-8 1.0 SOP-COOL-04)로 적힌 시행
- WO-2026-04161 1호기(HYD-01) · 완료 · 완료 2026-09-03 · 기록 그대로: 「CLR 핀 세척 SOP-COOL-14. 에어블로우, LOTO 확인」 · 측정: 세척후 CE 83 %
- WO-2026-04165 HYD-01(HYD-01) · 완료 · 완료 2026-09-20 · 기록 그대로: 「쿨러 핀 막힘 - 에어로 안떨어져 고압 세척기로 마무리. LOCAL/LOTO」 · 측정: CE 81 · 고압 세척 — 현행 금지(HM-8 1.1 SOP-COOL-14 2단계)와 맞지 않는 시행
- WO-2026-04172 HYD-01(HYD-01) · 완료 · 완료 2026-10-07 · 기록 그대로: 「COOLER_DEGRADATION 경보로 핀 청소(SOP-COOL-14대로)」 · 측정: 기록 없음 — 완료 기준(CE 80 %)을 보여 주지 않음
- WO-2026-04173 HYD-02(HYD-02) · 완료 · 완료 2026-10-08 · 기록 그대로: 「쿨러 fin cln 에어블로우 SOP-COOL-14」 · 측정: 재가동후 CE 86 %

## 승인

- 설비보전팀장 — 원문(HM-8 1.1 HM-8.7). 카드는 승인을 대신하지 않는다.

## 남은 질문

- 트립 뒤 복귀 조건(R5 출처 HM-9.4) — 제공되지 않은 절 · 자료/HM-9장_스캔본.txt 15줄 · 9-7쪽 없음 — 원본 확인 요청
- HPP-45B(HYD-04) 정비 지침 — 제공되지 않은 문서 · 자료/문서_목록.csv · 제조사에 요청 중 — 파일 없음
- Inspect the core before cleaning. Record blocked areas and bent or damaged fins. — 보류 · OEM-HPP45A-MM C 7 107줄 · 사내 기준이 정하지 않은 제조사 항목 — 세척 전 코어 막힘 · 휨 확인(HM-8 · PM-02에 없음) — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다
- If blocked areas or bent fins remain after cleaning, replace the core (part no. HI-CC-45A). — 보류 · OEM-HPP45A-MM C 7 114줄 · 사내 기준이 정하지 않은 제조사 항목 — 세척 뒤 막힘 · 휨이 남으면 코어 교체(HM-8 · PM-02에 없음) — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다
- If blocked areas or bent fins remain after cleaning, replace the core (part no. — 보류 · OEM-HPP45A-MM C 7 114줄 · 사내 기준이 정하지 않은 제조사 항목 — 세척 뒤 막힘 · 휨이 남으면 코어 교체(HM-8 · PM-02에 없음) — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다
