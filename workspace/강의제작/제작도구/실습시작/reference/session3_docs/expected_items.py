"""강사 참조 — 문서 지식 묶음 추출 랩의 기대 항목(원문에서 손으로 적은 것). 학생 폴더 · ZIP에 넣지 않는다.

구성안 9.1: 주 대상(핀 세척 원문을 가진 문서 — HM-8 1.0 SOP-COOL-04 · 1.2 개정 요청 초안 SOP-COOL-14 · 제조사 지침 7절 ·
설비안전규정 SR-04 제4 · 5조 · 9장 스캔본 9.1~9.3과 목차의 9.4 줄)와 다른 문서(PM-02 2.4 · 2.6 · SOP-PM-21, PR-07 주요 절, HI-01).
HM-8 1.1은 3회차 강사 판 sop.json이 기준선이라 여기에 적지 않는다.
항목 = (자료 파일, 절, 절차, 종류, 인용, 값) — 인용은 원문 글자 그대로(스캔본은 문자 인식 글자 그대로)이고, 줄 번호는 적지 않고
run_reference.py가 원문에서 찾아 낸다(원문 한 곳에만 맞아야 하고, 여러 곳에 맞으면 추출 후보와 같은 규칙으로 앞 줄을 붙인다).
값 = {'value', 'unit', 'comparator'(, 'value_max')} — 종류가 unit_value일 때만. 부정(「~하지 않는다」 · Do not)은 인용에서 읽는다.
종류 'toc'는 후보가 아니다 — 원문에 절이 없다는 근거 줄(목차)이라 누락 셈에서 뺀다.
"""
HM10, HM12, OEM, SR, SCAN = 'HM-8_1.0판_매뉴얼.md', 'HM-8_1.2판_개정요청.md', 'OEM-HPP45A_정비지침_영한.md', 'SR-04_설비안전규정_발췌.txt', 'HM-9장_스캔본.txt'
PM, PR, HI = 'PM-02_정기점검표.md', 'PR-07_예비품기준.md', 'HI-01_보충매뉴얼.md'


def v(value, unit, comparator, value_max=None):
    out = {'value': value, 'unit': unit, 'comparator': comparator}
    if value_max is not None:
        out['value_max'] = value_max
    return out


ITEMS = [
    # ── 주 대상: HM-8 1.0(폐기) — 핀 세척 원문의 옛 판, 옛 작업지시(SOP-COOL-04)를 읽을 때만
    (HM10, 'HM-3.1', None, 'precondition', '현장 작업은 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 한다.', None),
    (HM10, 'HM-7.6', None, 'precondition', '원인이 핀 오염이면 CMMS 작업지시로 세척한다.', None),
    (HM10, 'HM-7.6', None, 'precondition', '승인은 설비보전팀장이 한다.', None),
    (HM10, 'HM-7.3', 'SOP-COOL-03', 'step', '야간 정비창에 SOP-COOL-04 핀 세척 작업지시를 건다.', None),
    (HM10, 'HM-7.3', 'SOP-COOL-03', 'precondition', '승인: 생산관리자.', None),
    (HM10, 'HM-7.6', 'SOP-COOL-04', 'step', 'HM-3.1에 따라 설비를 정지하고 LOCAL로 전환한다.', None),
    (HM10, 'HM-7.6', 'SOP-COOL-04', 'step', '압축공기 또는 저압수로 핀을 세척한다.', None),
    (HM10, 'HM-7.6', 'SOP-COOL-04', 'step', '재가동 후 냉각 효율 CE가 75 % 이상으로 돌아왔는지 확인한다.', None),
    (HM10, 'HM-7.6', 'SOP-COOL-04', 'completion', '재가동 후 냉각 효율 CE가 75 % 이상으로 돌아왔는지 확인한다.', None),
    (HM10, 'HM-7.6', 'SOP-COOL-04', 'unit_value', '재가동 후 냉각 효율 CE가 75 % 이상으로 돌아왔는지 확인한다.', v(75, '%', '>=')),
    (HM10, 'HM-7.2', None, 'unit_value', '| 유온 TS1 | 52 ℃ 미만 | 55 ℃ 초과이면서 상승 중 | 65 ℃ 초과 (설비 정지) |', v(65, '℃', '>')),
    # ── 주 대상: HM-8 1.2 개정 요청 초안(미승인)
    (HM12, 'HM-8.0', None, 'precondition', '이 매뉴얼은 설비 대장에 모델 HPP-45A로 등록된 공랭식 오일 쿨러 유압 파워팩에 적용한다.', None),
    (HM12, 'HM-8.6', None, 'precondition', '조치 후 예측 유온이 55 ℃를 넘으면 경보 해제에 실패할 수 있으므로 다른 조치와 비교한다.', None),
    (HM12, 'HM-8.6', None, 'unit_value', '조치 후 예측 유온이 55 ℃를 넘으면 경보 해제에 실패할 수 있으므로 다른 조치와 비교한다.', v(55, '℃', '>')),
    (HM12, 'HM-8.7', None, 'precondition', '원인에 맞는 근본 조치를 CMMS 작업지시로 발행한다. 승인은 설비보전팀장이 한다.', None),
    (HM12, 'HM-8.7', 'SOP-COOL-14', 'step', '설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.', None),
    (HM12, 'HM-8.7', 'SOP-COOL-14', 'step', '압축공기 또는 저압수(0.2 MPa 이하)로 핀 바깥쪽에서 안쪽으로 세척한다.', None),
    (HM12, 'HM-8.7', 'SOP-COOL-14', 'unit_value', '압축공기 또는 저압수(0.2 MPa 이하)로 핀 바깥쪽에서 안쪽으로 세척한다.', v(0.2, 'MPa', '<=')),
    (HM12, 'HM-8.7', 'SOP-COOL-14', 'prohibition', '2. [변경] 압축공기 또는 저압수(0.2 MPa 이하)로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.', None),
    (HM12, 'HM-8.7', 'SOP-COOL-14', 'completion', '재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.', None),
    (HM12, 'HM-8.7', 'SOP-COOL-14', 'unit_value', '재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.', v(80, '%', '>=')),
    # ── 주 대상: 제조사 지침 7절(인용 근거는 영문 원본 — 머리말 6줄)
    (OEM, '7', None, 'precondition', 'Clean the core when the fins are visibly blocked or the fluid temperature stays above normal at working load.', None),
    (OEM, '7', 'T-7.1', 'step', 'Stop the pump, lock out the motor supply, and wait until the fan has stopped.', None),
    (OEM, '7', 'T-7.1', 'precondition', 'Inspect the core before cleaning. Record blocked areas and bent or damaged fins.', None),
    (OEM, '7', 'T-7.1', 'step', 'Clean with compressed air or with low-pressure water at no more than 30 psi.', None),
    (OEM, '7', 'T-7.1', 'unit_value', 'Clean with compressed air or with low-pressure water at no more than 30 psi.', v(30, 'psi', '<=')),
    (OEM, '7', 'T-7.1', 'prohibition', 'Do not use a high-pressure washer.', None),
    (OEM, '7', 'T-7.1', 'precondition', 'If blocked areas or bent fins remain after cleaning, replace the core (part no. HI-CC-45A).', None),
    (OEM, '7', 'T-7.1', 'step', 'After cleaning or replacement, run the unit at working load for 30 minutes and record the fluid temperature at the cooler inlet and outlet.', None),
    (OEM, '7', 'T-7.1', 'completion', 'The difference must not be less than the value in the commissioning record.', None),
    # ── 주 대상: SR-04 발췌(CP949) — 판정 조건 R4 · R5의 출처 후보
    (SR, '제4조', None, 'precondition', '유압 설비의 실측 유온이 인터록 한계(65 ℃)를 넘으면 설비가 정지한다.', None),
    (SR, '제4조', None, 'unit_value', '유압 설비의 실측 유온이 인터록 한계(65 ℃)를 넘으면 설비가 정지한다.', v(65, '℃', '>')),
    (SR, '제4조', None, 'prohibition', '운전 중에는 인터록 한계에 다가가는 조치를 하지 않는다.', None),
    (SR, '제4조', None, 'precondition', '인터록으로 정지한 설비의 복귀는 종합 정비 매뉴얼 HM-9.4를 따른다.', None),
    (SR, '제5조', None, 'precondition', '유압 회로를 여는 정비는 모터 전원을 잠그고(LOTO) 잔압이 0인지 압력계로 확인한 뒤 시작한다.', None),
    (SR, '제5조', None, 'precondition', '잠금은 정비를 맡은 사람이 걸고 그 사람이 푼다.', None),
    (SR, '제5조', None, 'precondition', '정비를 마치면 공구와 사람이 설비 밖에 있는지 확인한 뒤 잠금을 푼다.', None),
    # ── 주 대상: 9장 스캔본(문자 인식 글자 그대로)
    (SCAN, 'HM-9.1', None, 'prohibition', '펌프 부하는 6 0 % 아래로 내리지 않는다(최소 부하 인터록).', None),
    (SCAN, 'HM-9.1', None, 'unit_value', '펌프 부하는 6 0 % 아래로 내리지 않는다(최소 부하 인터록).', v(60, '%', '<')),
    (SCAN, 'HM-9.2', None, 'prohibition', '원격 조치(SOP-C0OL-0 1~03)는 REM0TE_AUTO가 아닐 때 쓰지 않는다.', None),
    (SCAN, 'HM-9.3', None, 'precondition', '운전 중인 설비가 아래 한계에 닿으면 PLC 인터록이 설비를 세우고 정지 원인을 표시한다.', None),
    (SCAN, 'HM-9.3', None, 'prohibition', '자동으로 다시 운전에 들어가지 않는다.', None),
    (SCAN, 'HM-9.3', None, 'unit_value', '유온 TS1  6 5 ℃ 초과  정지(OVERTEMP)', v(65, '℃', '>')),
    (SCAN, 'HM-9.3', None, 'unit_value', '토출 압력 PS1  130 bar 미만  정지(LOW_PRESSURE)', v(130, 'bar', '<')),
    (SCAN, 'HM-9.3', None, 'unit_value', '팬 진동 VS1  2.0 mm/s 이상  정지(HIGH_VIBRATI0N)', v(2.0, 'mm/s', '>=')),
    (SCAN, 'HM-9.0', None, 'toc', 'HM-9.4 트립 후 복귀 .......... 9-7', None),
    # ── 다른 문서: PM-02 2.4 · 2.6 · SOP-PM-21
    (PM, 'PM-2.4', None, 'precondition', 'CMMS는 마지막 정기 정비 뒤 운전시간이 1,950 h에 닿으면 정기 정비 도래 경보 PM_DUE를 낸다(주기 50 h 전, 회사 설정).', None),
    (PM, 'PM-2.4', None, 'unit_value', 'CMMS는 마지막 정기 정비 뒤 운전시간이 1,950 h에 닿으면 정기 정비 도래 경보 PM_DUE를 낸다(주기 50 h 전, 회사 설정).', v(1950, 'h', '>=')),
    (PM, 'PM-2.4', None, 'precondition', '예정된 정비 시간은 생산 오더가 없는 시간(주로 야간)이며 MES 생산 계획에 잡혀 있다.', None),
    (PM, 'PM-2.4', None, 'prohibition', '낮에 생산 중인 설비는 세우지 않는 것이 원칙이다.', None),
    (PM, 'PM-2.6', None, 'prohibition', '잠금(LOTO)과 잔압 해제를 확인하기 전에는 배관을 열지 않는다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'step', '설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'step', '펌프 모터 전원을 차단하고 어큐뮬레이터 잔압을 탱크로 배출한다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'step', '압력계 PS1이 0 bar인지 확인한 뒤에만 배관을 연다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'precondition', '압력계 PS1이 0 bar인지 확인한 뒤에만 배관을 연다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'step', '주 펌프 축 씰 키트를 교체한다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'step', '리턴 필터 엘리먼트를 교체하고 필터 차압 지시기를 초기화한다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'step', '누유와 호스 상태를 육안으로 점검하고 기록한다.', None),
    (PM, 'PM-2.6', 'SOP-PM-21', 'step', '잠금을 풀고 PM-2.9 시운전 확인을 한다.', None),
    # ── 다른 문서: PR-07 주요 절
    (PR, 'PR-7.1', None, 'precondition', '유압 파워팩 HYD-01~03은 같은 모델이라 예비품을 함께 쓴다.', None),
    (PR, 'PR-7.2', None, 'precondition', '가용 재고가 재주문점 아래로 떨어지면 재고 기준 이탈 경보 SPARE_BELOW_MIN이 열린다.', None),
    (PR, 'PR-7.2', None, 'unit_value', '| 쿨러 코어 | 1개 | 2개 |', v(1, '개', None)),
    (PR, 'PR-7.3', None, 'prohibition', '긴급 발주여도 승인되지 않은 공급사에는 발주하지 않는다.', None),
    (PR, 'PR-7.4', None, 'unit_value', '불량 기대비용 = 수량 × 불량률 × 불량 1건 손실이고, 불량 1건 손실(재교체 · 재작업 · 설비 정지)은 250만 원으로 본다(회사 설정).', v(250, '만 원', None)),
    (PR, 'PR-7.5', None, 'prohibition', '전결 기준을 피하려고 한 건을 나눠 발주하지 않는다.', None),
    (PR, 'PR-7.6', None, 'prohibition', '설비 경보로 열린 처리 건에서는 발주 절차를 후보로 내지 않는다.', None),
    # ── 다른 문서: HI-01(보충)
    (HI, 'HI-1', None, 'precondition', '설비 운전·정비·발주는 기존 승인 절차를 따른다.', None),
    (HI, 'HI-1.2', 'SOP-HI-02', 'step', '작업 메모에 정비 완료라고 적혀 있어도 작업지시가 열려 있거나 완료시각이 없으면 불일치 또는 확인 필요로 남긴다.', None),
    (HI, 'HI-1.2', 'SOP-HI-02', 'prohibition', '정비 이력을 임의로 닫지 말고 다음 근무자가 담당자에게 확인할 작업지시 식별자와 미확인 내용을 전달한다.', None),
    (HI, 'HI-1.3', 'SOP-HI-03', 'prohibition', '입고 예정 수량을 현재고로 합산해 도착 완료라고 보고하지 않는다.', None),
    (HI, 'HI-1.3', 'SOP-HI-03', 'step', '부품의 실제 도착이나 사용 가능 여부를 확인할 근거가 없으면 확인 필요로 남기고, 발주·입고 처리·재고 변경은 하지 않는다.', None),
    (HI, 'HI-1.4', None, 'prohibition', '인계자 검토와 인수자 확인 절차 자체를 SOP나 고장 유형으로 추출하지 않는다.', None),
]
MAIN_TARGET = {HM10, HM12, OEM, SR, SCAN}       # 11단계(주 대상) — 나머지는 14단계(다른 문서)
