# HYD 운전·정비 지식 (온톨로지 역추출, 교육용 가상 설비)

이 문서는 라이브 온톨로지(Neo4j)의 노드·관계를 문서 형식으로 되돌린 것이다. 온톨로지에 없는 설명·사양·배선은 들어 있지 않다.

# 1장 고장 유형

## fm:bearing-degradation 팬 베어링 열화

발생 부품: 쿨러 팬. 원인: -. 징후: -. 이어지는 고장: 쿨러 냉각 성능 상실.

## fm:cooling-loss 쿨러 냉각 성능 상실

발생 부품: 오일 쿨러. 원인: -. 징후: -. 이어지는 고장: 작동유 열화, 과열 정지.

## fm:oil-degradation 작동유 열화

발생 부품: 작동유 탱크. 원인: -. 징후: -. 이어지는 고장: -.

## fm:overheat-trip 과열 정지

발생 부품: 구동 모터. 원인: -. 징후: -. 이어지는 고장: -.

## fm:volumetric-loss 펌프 체적 효율 저하

발생 부품: 주 펌프 (A). 원인: -. 징후: -. 이어지는 고장: 작동유 열화.

# 2장 매뉴얼 절

## HM-3.1 정비를 위한 LOCAL 전환

정비 작업 전 현장 패널에서 LOCAL로 전환하고 원격 명령을 차단한다.

근거 규칙: -. 참조 단계: SOP-COOL-04/1, SOP-PMP-04/1, SOP-FAN-03/1, SOP-FAN-04/1.

## HM-3.2 운전 모드와 원격 조치 권한

REMOTE_AUTO에서만 IT 승인 조치를 받는다. 수동 조작이 들어오면 REMOTE_MANUAL로 바뀐다.

근거 규칙: rule:auto-mode. 참조 단계: SOP-PMP-02/1, SOP-COOL-01/1, SOP-PMP-01/1, SOP-COOL-02/1, SOP-COOL-03/1.

## HM-5.2 예비 펌프 전환

주 펌프 이상 시 예비 펌프로 무부하 전환한다. 전환 후 30초 안에 압력이 회복되어야 한다.

근거 규칙: rule:ps1-warn, rule:dx-pump, rule:cand-pump, rule:standby. 참조 단계: SOP-PMP-03/2, SOP-PMP-01/3, SOP-PMP-02/3, SOP-PMP-01/2.

## HM-5.4 압력 설정 변경 금지

내부 누설이 의심될 때 압력 설정을 올리지 않는다. 씰 손상이 빨라진다.

근거 규칙: rule:no-pressure-raise. 참조 단계: SOP-PMP-03/1.

## HM-5.6 펌프 축 씰 교체

LOCAL 전환 · 잠금 후 씰 키트를 교체하고 누설 시험을 한다.

근거 규칙: -. 참조 단계: SOP-PMP-04/3, SOP-PMP-04/2.

## HM-7.3 팬 증속 운전

쿨러 성능 저하 시 팬을 80~100 %로 올린다. 100 % 연속 운전은 24시간 이내.

근거 규칙: rule:fan-24h, rule:cand-cooler, rule:dx-cooler. 참조 단계: SOP-COOL-02/2, SOP-COOL-01/2.

## HM-7.5 냉각 회복 판정

TS1 55 ℃ 미만 · 경보 해제가 15분 유지되면 완화 성공.

근거 규칙: rule:ts1-warn. 참조 단계: SOP-COOL-02/4, SOP-COOL-04/3, SOP-FAN-02/2, SOP-COOL-01/3, SOP-COOL-03/3.

## HM-7.6 쿨러 핀 세척

설비 정지 · LOCAL 전환 후 압축공기로 핀을 세척한다.

근거 규칙: -. 참조 단계: SOP-COOL-03/4, SOP-COOL-04/2.

## HM-7.7 캐비닛 환기

캐비닛 온도가 35 ℃ 이상이면 환기 필터를 청소하고 배기 팬을 점검한다.

근거 규칙: -. 참조 단계: SOP-COOL-05/2, SOP-COOL-05/3, SOP-COOL-05/1.

## HM-8.1 팬 진동 점검

VS1 1.2 mm/s 초과 시 팬 속도를 낮추고 베어링 소음 · 온도를 확인한다.

근거 규칙: rule:dx-fan, rule:cand-fan. 참조 단계: SOP-FAN-11/4, SOP-FAN-11/3, SOP-FAN-11/2, SOP-FAN-11/1, SOP-FAN-01/1, SOP-FAN-02/1, SOP-FAN-02/3, SOP-FAN-01/3.

## HM-8.2 쿨러 팬 벨트 교체

벨트 처짐이 기준을 벗어나거나 균열이 보이면 교체한다.

근거 규칙: -. 참조 단계: SOP-FAN-12/4, SOP-FAN-12/3, SOP-FAN-12/2, SOP-FAN-12/1.

## HM-8.3 팬 베어링 교체

계획 정지 후 베어링을 교체하고 VS1 0.9 mm/s 미만을 확인한다.

근거 규칙: rule:cand-fan. 참조 단계: SOP-FAN-04/2, SOP-FAN-03/3, SOP-FAN-03/2, SOP-FAN-04/3.

## HM-9.1 부하 저감 운전

펌프 부하는 60 % 미만으로 내리지 않는다 (최소 부하 인터록).

근거 규칙: rule:cand-cooler. 참조 단계: SOP-PMP-02/2, SOP-FAN-01/2, SOP-COOL-03/2, SOP-COOL-02/3.

## HM-9.4 트립 후 재기동

유온 55 ℃ 미만에서만 리셋한다. 원인 조치 없이 재기동하면 재발한다.

근거 규칙: rule:cand-trip, rule:cand-trip-fm, rule:trip-reset-only. 참조 단계: SOP-TRIP-01/1, SOP-TRIP-01/3, SOP-TRIP-01/2.

# 3장 조치 절차

### SOP-PMP-02 부하 70 %
종류: control. 설명: 부하를 70 %로 낮춰 압력 부족과 누설 진행을 늦춘다.. 적용 고장: MITIGATED_BY 펌프 체적 효율 저하.
1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.
2. 펌프 부하를 70 %로 낮춘다.
3. PS1 하락이 멈췄는지 10분간 확인한다.

### SOP-COOL-03 부하 70 % + 야간 세척
종류: control. 설명: 팬은 그대로 두고 부하를 70 %로 낮춘 뒤 야간 정비창에 쿨러를 세척한다.. 적용 고장: MITIGATED_BY 쿨러 냉각 성능 상실.
1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.
2. 펌프 부하를 70 %로 낮춘다.
3. 15분 재관측: TS1 55 ℃ 미만이면 완화 성공.
4. 야간 정비창에 쿨러 핀 세척 작업지시(SOP-COOL-04)를 건다.

### SOP-COOL-01 팬 최대
종류: control. 설명: 팬만 100 %로 올린다. 생산은 그대로 유지한다.. 적용 고장: MITIGATED_BY 쿨러 냉각 성능 상실.
1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.
2. 팬 속도를 100 %로 올린다 (연속 24시간 이내).
3. 15분 재관측: TS1 55 ℃ 미만이고 경보 해제면 완화 성공.

### SOP-COOL-02 팬 최대 + 부하 80 %
종류: control. 설명: 팬 100 %와 부하 80 %로 유온을 확실히 내린다.. 적용 고장: MITIGATED_BY 쿨러 냉각 성능 상실.
1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.
2. 팬 속도를 100 %로 올린다.
3. 펌프 부하를 80 %로 낮춘다 (최소 60 %).
4. 15분 재관측: TS1 55 ℃ 미만이고 경보 해제면 완화 성공.

### SOP-FAN-02 팬 40 %
종류: control. 설명: 팬만 40 %로 낮춘다. 생산은 그대로 유지한다.. 적용 고장: MITIGATED_BY 팬 베어링 열화.
1. 팬 속도를 40 %로 낮춘다.
2. 유온을 15분간 감시한다. 55 ℃를 넘으면 부하를 낮춘다.
3. VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.

### SOP-FAN-01 팬 40 % + 부하 80 %
종류: control. 설명: 팬을 낮춰 진동을 줄이고 부하도 낮춰 유온 상승을 막는다.. 적용 고장: MITIGATED_BY 팬 베어링 열화.
1. 팬 속도를 40 %로 낮춘다.
2. 유온이 55 ℃를 넘지 않도록 부하를 80 %로 낮춘다.
3. VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.

### SOP-FAN-03 계획 정지 + 베어링 교체
종류: control. 설명: 설비를 계획 정지하고 바로 베어링을 교체한다.. 적용 고장: REMEDIED_BY 팬 베어링 열화.
1. 생산오더를 마감하고 계획 정지한다.
2. LOCAL로 전환하고 베어링을 교체한다.
3. 재가동 후 VS1 0.9 mm/s 미만을 확인한다.

### SOP-PMP-03 압력 설정 상향 (구 절차)
종류: control. 설명: 압력 설정을 10 bar 올려 부족분을 메운다. 개정 매뉴얼에서 누설 시 금지된 옛 절차다.. 적용 고장: MITIGATED_BY 펌프 체적 효율 저하.
1. 압력 설정을 10 bar 올린다. 누설 의심 시에는 금지 (개정 HM-5.4).
2. PS1이 175 bar 이상인지 확인한다.

### SOP-TRIP-01 냉각 후 리셋
종류: control. 설명: 유온 55 ℃ 미만에서 인터록을 리셋하고 재관측한다.. 적용 고장: MITIGATED_BY 과열 정지.
1. 유온이 55 ℃ 미만인지 확인한다.
2. 원인 조치(세척 · 교체) 계획이 있는지 확인한다.
3. PLC를 리셋하고 재관측한다.

### SOP-FAN-11 쿨러 팬 점검 절차
종류: work_order. 설명: 매뉴얼 HM-8_cooler-fan-manual.md에서 등록한 SOP. 적용 고장: REMEDIED_BY 팬 베어링 열화.
1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한다.
2. 벨트 처짐을 측정한다 (기준 10~15 mm).
3. 베어링 소음과 표면 온도를 확인한다 (60 ℃ 이하).
4. 재가동 후 VS1이 0.9 mm/s 아래로 내려왔는지 확인한다.

### SOP-FAN-12 벨트 교체 절차
종류: work_order. 설명: 매뉴얼 HM-8_cooler-fan-manual.md에서 등록한 SOP. 적용 고장: REMEDIED_BY 팬 베어링 열화.
1. LOCAL 전환과 잠금(LOTO)을 확인한다.
2. 구 벨트를 분리하고 풀리 정렬을 점검한다.
3. 새 벨트를 걸고 처짐을 12 mm로 맞춘다.
4. 30분 시운전 뒤 냉각 효율 CE가 80 % 이상인지 확인한다.

### SOP-PMP-01 예비 펌프 전환
종류: control. 설명: 예비 펌프 B로 전환해 압력을 즉시 회복한다.. 적용 고장: MITIGATED_BY 펌프 체적 효율 저하.
1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.
2. 예비 펌프 B로 무부하 전환한다.
3. 30초 안에 PS1이 175 bar 이상으로 회복됐는지 확인한다.

### SOP-COOL-04 쿨러 핀 세척
종류: work_order. 설명: 설비를 세우고 쿨러 핀을 세척한다. CMMS 작업지시로 발행한다.. 적용 고장: REMEDIED_BY 쿨러 냉각 성능 상실.
1. 설비를 정지하고 LOCAL로 전환한다.
2. 압축공기로 핀을 세척한다.
3. 재가동 후 CE 80 % 이상 복귀를 확인한다.

### SOP-FAN-04 팬 베어링 교체
종류: work_order. 설명: 다음 계획 정지 때 베어링을 교체하도록 CMMS 작업지시를 발행한다.. 적용 고장: REMEDIED_BY 팬 베어링 열화.
1. LOCAL로 전환하고 잠근다.
2. 베어링을 교체한다.
3. 재가동 후 VS1 0.9 mm/s 미만을 확인한다.

### SOP-PMP-04 펌프 축 씰 교체
종류: work_order. 설명: 씰 키트를 구매요청하고 교체 작업지시를 발행한다.. 적용 고장: REMEDIED_BY 펌프 체적 효율 저하.
1. 주 펌프를 LOCAL로 전환하고 잠근다.
2. 씰 키트를 교체한다.
3. 누설 시험 후 주 펌프로 복귀한다.

### SOP-COOL-05 캐비닛 환기 개선
종류: work_order. 설명: 외기 고온으로 냉각 여유가 없을 때 캐비닛 환기를 보강한다. CMMS 작업지시로 발행한다.. 적용 고장: REMEDIED_BY 쿨러 냉각 성능 상실.
1. 캐비닛 온도(TS4)와 외기 온도를 기록한다.
2. 환기 필터를 청소하고 배기 팬을 점검한다.
3. 캐비닛 온도가 35 ℃ 아래로 내려왔는지 확인한다.

# 4장 판정 기준 (결정표)

## dt:action-candidates 조치 후보 선택 결정표

| 순서 | 조건 | 효과 | 설명 |
|---|---|---|---|
| 1 | failure_mode == 'fm:cooling-loss' | SELECT | 냉각 성능 상실 → 즉시 완화 SOP (팬 최대 · 팬 최대+부하 저감 · 부하 저감+야간 세척) |
| 2 | failure_mode == 'fm:volumetric-loss' | SELECT | 펌프 체적 효율 저하 → 즉시 완화 SOP (예비 펌프 전환 · 부하 저감 · 압력 상향) |
| 3 | failure_mode == 'fm:bearing-degradation' | SELECT | 팬 베어링 열화 → 팬 감속+부하 저감 · 팬 감속 · 계획 정지 |
| 4 | plc_state == 'TRIP' | SELECT | 트립 중이면 제어 명령 대신 냉각 후 리셋 |
| 5 | failure_mode == 'fm:overheat-trip' | SELECT | 과열 정지로 판정되면 냉각 후 리셋 (트립 규칙과 OR — 행을 나눔) |

## dt:compliance 규정 적합성 결정표

| 순서 | 조건 | 효과 | 설명 |
|---|---|---|---|
| 1 | skill_code == 'PRESSURE_SET' and failure_mode == 'fm:volumetric-loss' | EXCLUDE | 누설 의심 시 압력 설정 상향 금지 |
| 2 | forecast_ts1 >= 65 | EXCLUDE | 예측 유온이 인터록 한계 이상이면 제외 (모든 제어 후보에 예측값으로 적용) |
| 3 | skill_kind == 'control' and plc_mode != 'REMOTE_AUTO' | EXCLUDE | 원격 제어는 REMOTE_AUTO에서만 |
| 4 | standby_ready == false | EXCLUDE | 예비 펌프가 정비 중이면 전환 불가 |
| 5 | forecast_ts1 >= 55 | WARN | 예측 유온이 55 ℃ 이상이면 경보 해제 실패 가능 |
| 6 | fan100_hours > 24 | PENALTY | 팬 100 % 연속 24시간 초과 시 수명 감점 |
| 7 | supplier_avl == false | EXCLUDE | 핵심 부품은 승인 공급사에서만 구매 |
| 8 | plc_state == 'TRIP' and skill_code != 'RESET' | EXCLUDE | 트립 중에는 PLC가 리셋 외 제어 명령을 거부한다 (냉각 후 리셋만) |
| 9 | forecast_ps1 < 165 | WARN | 예측 토출 압력이 165 bar 미만이면 저압 경보가 이어질 수 있음 |

## dt:diagnose-cause 고장 유형 · 원인 판정 결정표

| 순서 | 조건 | 효과 | 설명 |
|---|---|---|---|
| 1 | pattern == 'COOLER_DEGRADATION' and ce < 70 | SELECT | 냉각 효율이 낮으면 쿨러 핀 오염이 1순위 (근거 evd:ce-low) |
| 2 | pattern == 'PUMP_LEAKAGE' and ps1 < 165 | SELECT | 토출 압력이 165 bar 미만이면 씰 마모 (근거 evd:ps1-low) |
| 3 | pattern == 'FAN_VIBRATION' and ts1 < 52 | SELECT | 유온이 정상인데 진동만 오르면 베어링 (근거 evd:vs1-trend) |

## dt:rank-actions 조치 우선순위 결정표

| 순서 | 조건 | 효과 | 설명 |
|---|---|---|---|
| 1 | true | RANK | 점수 = BSC 득실(스킬 → 처음 닿는 성과 지표, 강도 high 1 · medium 0.6 · low 0.3, 조건부는 절반) + 예측 유온 여유 (55 − 예측)/3 (±2 한도) − 경고 0.5 − 감점/20 + 선례 비율 × 1.5 + 납기 긴급도((24 − 남은 h)/24 × 지연 보상/100, 0~1) × 생산 영향(유지 +1 · 감산 +0.4 · 정지 −1) × 1.5 − 품질 위험(고온 구간 출하 대기 로트가 있고 예측 유온 ≥ 55 ℃ 면 클레임/1000, ≤ 1) × 1.5. 제외된 카드는 뒤로, 동점이면 승인 직급이 낮은 쪽 |

# 5장 근거 창

| 근거 | 이름 | 규칙 | 태그 | 창(초) | 가중치 |
|---|---|---|---|---|---|
| evd:ambient-high | 캐비닛 온도 35 ℃ 이상 | avg(TS4) over 2m >= 35 | TS4 | 120 | 1.0 |
| evd:ce-low | 냉각 효율 평균 70 % 미만 (최근 30초) | avg(CE) over 30s < 70 | CE | 30 | 0.6 |
| evd:fan-normal | 팬 진동 정상 (팬 고장 아님) | avg(VS1) over 2m < 0.9 | VS1 | 120 | 0.4 |
| evd:fs1-drop | 유량 평균 8.0 l/min 미만 | avg(FS1) over 2m < 8.0 | FS1 | 120 | 0.4 |
| evd:ps1-low | 토출 압력 평균 165 bar 미만 | avg(PS1) over 2m < 165 | PS1 | 120 | 0.6 |
| evd:ts1-normal | 유온 52 ℃ 미만 (냉각 문제 아님) | avg(TS1) over 2m < 52 | TS1 | 120 | 0.4 |
| evd:vs1-trend | 진동 상승폭 0.2 mm/s 초과 (최근 5분) | max(VS1) - min(VS1) over 5m > 0.2 | VS1 | 300 | 0.6 |

# 6장 입력 항목

| 입력 | 이름 | 변수 | 형 |
|---|---|---|---|
| in:cause | 판정 원인 | cause | string |
| in:ce | 냉각 효율 | ce | number |
| in:chosen-skill | 사람이 고른 스킬 | chosen_skill | string |
| in:failure-mode | 판정 고장 유형 | failure_mode | string |
| in:fan100-hours | 팬 100 % 연속 운전 시간 | fan100_hours | number |
| in:forecast-ps1 | 조치 후 예측 토출 압력 | forecast_ps1 | number |
| in:forecast-ts1 | 조치 후 예측 유온 | forecast_ts1 | number |
| in:fs1 | 유량 | fs1 | number |
| in:hot-lot-claim | 고온 구간 출하 대기 로트의 클레임 위험 (만원) | hot_lot_claim | number |
| in:hot-lot-qty | 고온 구간 출하 대기 수량 | hot_lot_qty | number |
| in:load | 펌프 부하 설정 | load | number |
| in:order-due | 긴급 오더 남은 시간 | order_due_h | number |
| in:order-penalty | 납기 지연 시 시간당 보상 | order_penalty_per_h | number |
| in:order-tier | 고객 등급 | order_customer_tier | string |
| in:pattern | 경보 패턴 | pattern | string |
| in:plc-mode | PLC 운전 모드 | plc_mode | enum |
| in:plc-state | PLC 상태 | plc_state | enum |
| in:ps1 | 토출 압력 | ps1 | number |
| in:skill-code | 후보 스킬의 명령 코드 | skill_code | string |
| in:skill-kind | 후보 스킬 종류 | skill_kind | enum |
| in:standby-ready | 예비 펌프 가용 | standby_ready | boolean |
| in:supplier-avl | 공급사 승인 여부 | supplier_avl | boolean |
| in:ts1 | 유온 | ts1 | number |
| in:ts1-slope | 유온 상승률 | ts1_slope | number |
| in:vs1 | 팬 진동 | vs1 | number |
| in:vs1-slope | 진동 상승률 | vs1_slope | number |

# 7장 예비품과 공급사

- part:cooler-core 쿨러 코어: C트레이딩 (최저가)(AVL False, 120.0, 2일); A정밀 (저가)(AVL True, 180, 3일); B-OEM (순정)(AVL True, 260, 5일)
- part:fan-bearing 팬 베어링: B-OEM (순정)(AVL True, 28, 3일); A정밀 (저가)(AVL True, 18, 1일)
- part:pump-seal 펌프 축 씰 키트: A정밀 (저가)(AVL True, 35, 2일); C트레이딩 (최저가)(AVL False, 20, 1일); B-OEM (순정)(AVL True, 55, 5일)
