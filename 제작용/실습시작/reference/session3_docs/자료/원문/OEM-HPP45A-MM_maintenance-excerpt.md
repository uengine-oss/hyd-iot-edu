# HPP-45A Hydraulic Power Pack — Maintenance Manual (Excerpt) / HPP-45A 유압 파워팩 정비 지침 (발췌)

Hanil Hydraulics, Document OEM-HPP45A-MM, Rev. C (2024-06) / 한일유압 문서 OEM-HPP45A-MM, C판(2024-06)
교육용 가상 자료(공개 현업 문제 유형을 따라 생성). 실제 회사·제조사·설비의 기록이 아니다. 수치는 교육용이다.

이 발췌는 제조사 영문 원본(EN)과 설비보전팀 사내 번역(KO)을 함께 적었다. 번역은 참고이며 뜻이 다르면 영문 원본을 따른다.
회사 기준과의 관계: PM-02와 같은 항목을 다르게 정하면 PM-02(회사 기준)를 따르고, PM-02가 정하지 않은 항목은 이 발췌를 따른다.
압력은 원본 단위 psi로 적었다. 1 bar는 14.5 psi다. 적용 범위(사내 주석): 설비 대장에 모델 HPP-45A로 등록된 설비.

## 1 Safety / 안전
EN: Before opening any hydraulic line or filter housing, stop the pump, lock out the motor supply, and discharge the accumulator to tank.
KO: 유압 배관이나 필터 하우징을 열기 전에 펌프를 세우고 모터 전원을 잠근 뒤 어큐뮬레이터를 탱크로 방압한다.
EN: Do not open the circuit until the system pressure gauge reads 0 psi.
KO: 시스템 압력계가 0 psi를 가리키기 전에는 회로를 열지 않는다.
EN: Never loosen a fitting to release trapped pressure.
KO: 남은 압력을 빼려고 피팅을 풀지 않는다.
EN: Hot fluid can cause burns. Allow the fluid to cool below 40 °C before draining.
KO: 뜨거운 작동유는 화상을 입힐 수 있다. 배유 전에 작동유를 40 °C 아래로 식힌다.

## 2 Maintenance Schedule / 정비 주기
EN: Intervals are counted from commissioning or from the last completed service, whichever is later.
KO: 주기는 시운전일과 마지막 정비 완료일 중 늦은 날부터 센다.

| Item / 항목 | Interval / 주기 | Action / 조치 | See / 참조 |
|---|---|---|---|
| Fluid level and appearance / 작동유 수위·외관 | Daily / 매일 | Visual check / 육안 확인 | 5 |
| Fluid condition (colour, odour) / 작동유 상태(색·냄새) | Monthly or every 150 h, whichever comes first / 월 1회 또는 150 h 중 먼저 오는 때 | Compare with Section 5 / 5절과 비교 | 5 |
| Return filter element, 10 µm / 리턴 필터 엘리먼트 10 µm | Indicator red, or every 1,000 h or 6 months, whichever comes first / 지시기 적색 또는 1,000 h마다 | Replace / 교체 | 3 |
| Suction strainer, 125 µm / 흡입 스트레이너 125 µm | 4,000 h | Clean / 세척 | — |
| Accumulator precharge / 어큐뮬레이터 프리차지 | See Section 4 / 4절 | Check and recharge / 점검·재충전 | 4 |
| Pump shaft seal / 펌프 축 씰 | 2,000 h | Replace / 교체 | — |
| Fluid laboratory analysis / 작동유 시험 분석 | 12 months or 2,000 h, whichever comes first / 12개월 또는 2,000 h 중 먼저 오는 때 | Particle count, water, viscosity / 입자 수·수분·점도 | 5 |
| Fluid change / 작동유 교환 | 8,000 h or when analysis fails / 8,000 h 또는 분석 불합격 때 | Drain, flush and refill / 배유·세정·주유 | — |

## 3 Return Filter / 리턴 필터
EN: The clogging indicator turns red when the differential pressure across the element reaches 25 psi.
KO: 엘리먼트 앞뒤 차압이 25 psi에 이르면 막힘 지시기가 적색으로 바뀐다.
EN: Indicator readings taken with fluid below 30 °C are not valid. Recheck at operating temperature.
KO: 작동유가 30 °C 아래일 때 본 지시기 값은 쓰지 않는다. 운전 온도에서 다시 확인한다.

### T-3.1 Return filter element replacement / 리턴 필터 엘리먼트 교체
1. EN: Carry out the safety steps in Section 1 and confirm that the gauge reads 0 psi.
   KO: 1절의 안전 조치를 하고 압력계가 0 psi인지 확인한다.
2. EN: Remove the bowl and the element. Do not clean and reuse paper elements.
   KO: 보울과 엘리먼트를 분리한다. 종이 엘리먼트는 세척해 다시 쓰지 않는다.
3. EN: Inspect the old element. If metal particles are visible, take a fluid sample for analysis before restart.
   KO: 떼어 낸 엘리먼트를 살핀다. 금속 입자가 보이면 재가동 전에 작동유 시료를 채취해 분석을 맡긴다.
4. EN: Fit a new 10 µm element (part no. HI-RF-10) with a new O-ring and tighten the bowl to 35 N·m.
   KO: 새 10 µm 엘리먼트(부품 번호 HI-RF-10)를 새 O링과 함께 끼우고 보울을 35 N·m로 조인다.
5. EN: Reset the indicator, restart, and run for 10 minutes. Check the housing for leaks.
   KO: 지시기를 초기화하고 재가동해 10분 운전한 뒤 하우징 누유를 확인한다.
6. EN: At operating temperature the differential pressure must be below 10 psi. Record the reading and the element lot number.
   KO: 운전 온도에서 차압이 10 psi 미만이어야 한다. 읽은 값과 엘리먼트 로트 번호를 기록한다.

## 4 Accumulator / 어큐뮬레이터
EN: Nominal precharge is 1,450 psi of dry nitrogen at 20 °C, as stamped on the nameplate.
KO: 프리차지 기준은 명판에 새긴 대로 20 °C에서 건조 질소 1,450 psi다.
EN: Use dry nitrogen only. Never charge with oxygen or compressed air.
KO: 건조 질소만 쓴다. 산소나 압축공기로 충전하지 않는다.
EN: Check the precharge 2 weeks or 100 operating hours after installation or recharge, whichever comes first.
KO: 설치나 재충전 뒤 2주 또는 100 운전시간 중 먼저 오는 때에 프리차지를 점검한다.
EN: If the precharge has fallen by more than 200 psi since the previous check, check weekly or every 50 operating hours. Otherwise check every 4 weeks or 200 operating hours.
KO: 직전 점검보다 200 psi 넘게 떨어졌으면 매주 또는 50 운전시간마다 점검한다. 그렇지 않으면 4주 또는 200 운전시간마다 점검한다.
EN: Recharge if the precharge is below 90 % of the nameplate value.
KO: 프리차지가 명판 값의 90 % 미만이면 재충전한다.

### T-4.1 Precharge check / 프리차지 점검
1. EN: Carry out the safety steps in Section 1. The fluid side must read 0 psi before the charging kit is connected.
   KO: 1절의 안전 조치를 한다. 충전 키트를 연결하기 전에 유압 쪽이 0 psi여야 한다.
2. EN: Connect the charging kit to the gas valve and read the precharge.
   KO: 충전 키트를 가스 밸브에 연결하고 프리차지를 읽는다.
3. EN: Correct the reading to 20 °C with the table on the nameplate.
   KO: 명판의 표로 읽은 값을 20 °C 기준으로 보정한다.
4. EN: If the corrected value is below 90 % of the nameplate value, recharge with dry nitrogen to the nameplate value.
   KO: 보정한 값이 명판 값의 90 % 미만이면 건조 질소로 명판 값까지 재충전한다.
5. EN: Record the corrected value, the date and the hour meter reading, and set the next check from Section 4.
   KO: 보정한 값과 날짜, 운전시간 계수기 값을 기록하고 4절에 따라 다음 점검을 정한다.

## 5 Fluid Condition / 작동유 상태 판정

| Observation / 관찰 | Likely cause / 추정 원인 | Action / 조치 |
|---|---|---|
| Milky or cloudy / 우윳빛·탁함 | Water ingress, check the heat exchanger / 수분 유입, 열교환기 확인 | Laboratory analysis, change fluid / 시험 분석, 작동유 교환 |
| Dark with burnt odour / 짙은 색·탄 냄새 | Oxidation from overheating / 과열에 의한 산화 | Laboratory analysis, check cooler / 시험 분석, 쿨러 점검 |
| Sediment after standing overnight / 하룻밤 뒤 침전물 | Filter element failure / 필터 엘리먼트 파손 | Inspect filters, see Section 3 / 필터 점검, 3절 참조 |
| Level low / 수위 낮음 | External leak / 외부 누유 | Find and repair the leak / 누유 부위 수리 |
| Level high / 수위 높음 | Water through the heat exchanger / 열교환기를 통한 물 유입 | Stop and inspect the heat exchanger / 정지 후 열교환기 점검 |

EN: Maximum operating fluid temperature is 70 °C (158 °F).
KO: 작동유 최고 운전 온도는 70 °C(158 °F)다.

## 6 After Service / 정비 후 확인
EN: After any service, run the unit for 15 minutes at working pressure and confirm that there are no leaks.
KO: 정비 뒤에는 작업 압력으로 15분 운전하고 누유가 없는지 확인한다.
EN: Record the pump outlet pressure, flow and fluid temperature. The readings must be within the limits of the commissioning record.
KO: 펌프 토출 압력·유량·작동유 온도를 기록한다. 값은 시운전 기록의 한계 안에 있어야 한다.
