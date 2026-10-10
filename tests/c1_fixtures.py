"""확정 TODO C1 시험 대역(test double): 시나리오 문서 A(HM-8) · B(PM-02) · C(PR-07)에서 LLM 추출이 낼 만한 제안.

실제 추출은 에이전트(LLM)가 한다. 여기 값은 단위 시험 · 라이브 검증용으로 사람이 문서를 읽고 쓴 결정론 대역이며, 모든 항목은
문서 원문 인용(quote)에 묶인다 — 인용이 문서에 없으면 시험이 실패한다. 코드(procsvc)에는 이 값이 들어 있지 않다.
절 · SOP · 단계는 구조화 파서(manual_review.proposal)가 낸 것을 그대로 쓰고, 지식(knowledge)과 SOP 연결(link)만 덧붙인다.
C가 기대는 펌프 고장 지식(fm:volumetric-loss · cause:pump-seal-wear)은 B 문서(PM-02 정기 점검표)가 만든다 — 적재 순서 A → B → C.
PUMP_STANDIN은 B 확정 전에 쓰던 작은 대역 문서로, B 없이 C만 시험할 때를 위해 남겨 둔다.
"""
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'docs' / 'samples'
DOC_A = SAMPLES / 'HM-8_cooler-fan-manual.md'
DOC_C = SAMPLES / 'PR-07_spare-parts-standard.md'
DOC_B = SAMPLES / 'PM-02_powerpack-pm-checklist.md'

PUMP_STANDIN = '''# 시험 대역 — 펌프 고장 지식 (C1 시험용, 시나리오 B 문서 아님)

## TP-1.1 펌프 체적 효율 저하
펌프 체적 효율 저하는 주 펌프 A에서 생기며 토출 압력과 유량이 함께 떨어진다. 가장 흔한 원인은 축 씰 마모다(사전 확률 0.7).

### SOP-TPMP-01 씰 상태 점검
1. 주 펌프를 LOCAL로 전환하고 잠근다.
2. 축 씰 누설 흔적을 점검한다.
'''

A_KNOWLEDGE = {
    'failure_modes': [
        dict(id='fm:cooling-loss', name='쿨러 냉각 성능 상실', component='comp:cooler', symptoms=['sym:ts1-rise', 'sym:ce-drop'],
             section='HM-8.4', quote='쿨러 냉각 성능 상실은 오일 쿨러에서 생기는 고장이며 유온 상승과 냉각 효율 저하로 나타난다.')],
    'causes': [
        dict(id='cause:cooler-fin-fouling', name='쿨러 핀 오염', aliases=['핀 막힘'], prior=0.6, failure_mode='fm:cooling-loss',
             parts=['part:cooler-core'], disturbs=[dict(target='sv:fouling', sign=1)], section='HM-8.4',
             quote='쿨러 핀 오염(먼지 · 유막으로 핀이 막힘)이 가장 흔하다(사전 확률 0.6).'),
        dict(id='cause:high-ambient', name='주변 온도 상승', aliases=['외기 고온'], prior=0.2, failure_mode='fm:cooling-loss',
             section='HM-8.4', quote='주변 온도 상승(외기 고온 · 캐비닛 환기 불량)은 사전 확률 0.2로 본다.'),
        dict(id='cause:fan-drive-fault', name='팬 구동 불량', aliases=['벨트 슬립', '베어링 마모'], prior=0.2, failure_mode='fm:cooling-loss',
             parts=['part:fan-bearing'], disturbs=[dict(target='sv:bearing-wear', sign=1)], section='HM-8.4',
             quote='팬 구동 불량(벨트 슬립 · 베어링 마모)은 사전 확률 0.2로 본다.')],
    'evidence': [
        dict(id='evd:ce-low', cause='cause:cooler-fin-fouling', name='냉각 효율 평균 70 % 미만 (최근 30초)', tag='CE', aggregate='avg',
             window_seconds=30, expect='lt', threshold=70, weight=0.6, section='HM-8.4', quote='최근 30초 냉각 효율 평균이 70 % 미만이고'),
        dict(id='evd:fan-normal', cause='cause:cooler-fin-fouling', name='팬 진동 정상 (팬 고장 아님)', tag='VS1', aggregate='avg',
             window_seconds=120, expect='lt', threshold=0.9, weight=0.4, section='HM-8.4', quote='최근 2분 팬 진동 VS1 평균이 0.9 mm/s 미만(팬은 정상)이면'),
        dict(id='evd:ambient-high', cause='cause:high-ambient', name='캐비닛 온도 35 ℃ 이상', tag='TS4', aggregate='avg',
             window_seconds=120, expect='gte', threshold=35, weight=1.0, section='HM-8.4', quote='최근 2분 캐비닛 온도 TS4 평균이 35 ℃ 이상이면'),
        dict(id='evd:fan-vibration-high', cause='cause:fan-drive-fault', name='팬 진동 0.9 mm/s 이상', tag='VS1', aggregate='avg',
             window_seconds=120, expect='gte', threshold=0.9, weight=1.0, section='HM-8.4', quote='최근 2분 팬 진동 VS1 평균이 0.9 mm/s 이상이면')],
    'rules': [
        dict(id='rule:dx-cooling-fin', table='dt:diagnose-cause', effect='SELECT',
             tests=[dict(input='in:pattern', operator='==', value='COOLER_DEGRADATION'), dict(input='in:ce', operator='<', value=70, unit='%')],
             outputs=['cause:cooler-fin-fouling'], annotation='냉각 효율이 낮으면 핀 오염이 1순위', section='HM-8.4',
             quote='경보 패턴 COOLER_DEGRADATION이 떴을 때 냉각 효율이 70 % 미만이면 핀 오염을 1순위 원인으로 둔다.'),
        dict(id='rule:cand-cooling-loss', table='dt:action-candidates', effect='SELECT',
             tests=[dict(input='in:failure-mode', operator='==', value='fm:cooling-loss')],
             outputs=['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14', 'SOP-COOL-15', 'SOP-FAN-11', 'SOP-FAN-12'],
             annotation='냉각 성능 상실 → 즉시 완화 3 + 근본 조치(세척 · 환기 · 팬 점검/벨트)', section='HM-8.5', quote='HM-8.5 즉시 완화 조치'),
        dict(id='rule:cool-remote-auto', table='dt:compliance', effect='EXCLUDE',
             tests=[dict(input='in:skill-kind', operator='==', value='control'), dict(input='in:plc-mode', operator='!=', value='REMOTE_AUTO')],
             applies_to=['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13'], annotation='원격 조치는 REMOTE_AUTO에서만', section='HM-8.8',
             quote='원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.'),
        dict(id='rule:cool-forecast-warn', table='dt:compliance', effect='WARN',
             tests=[dict(input='in:forecast-ts1', operator='>=', value=55, unit='℃')], applies_to=['SOP-COOL-11'],
             annotation='예측 유온 55 ℃ 이상이면 해제 실패 가능', section='HM-8.6',
             quote='조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있으므로 다른 조치와 비교한다.'),
        dict(id='rule:cool-fan-24h', table='dt:compliance', effect='PENALTY', penalty=20, penalizes='msr:mtbf',
             tests=[dict(input='in:fan100-hours', operator='>', value=24, unit='h')], applies_to=['SOP-COOL-11', 'SOP-COOL-12'],
             annotation='팬 100 % 연속 24시간 초과 시 수명 감점', section='HM-8.8',
             quote='이미 24시간을 넘겼다면 팬 최대 운전 조치는 팬 수명 손실로 20만 원을 감점해서 비교한다.')],
}


def _wo(sop):
    return [dict(action='action:work-order', value=sop)]


A_LINKS = {
    'SOP-FAN-11': dict(failureMode='fm:cooling-loss', relation='REMEDIED_BY', kind='work_order', approver='role:maint-mgr',
                       actions=_wo('SOP-FAN-11'), addresses=['cause:fan-drive-fault']),
    'SOP-FAN-12': dict(failureMode='fm:cooling-loss', relation='REMEDIED_BY', kind='work_order', approver='role:maint-mgr',
                       actions=_wo('SOP-FAN-12'), addresses=['cause:fan-drive-fault'], affects=[dict(target='msr:maint-cost', sign='+')]),
    'SOP-COOL-11': dict(failureMode='fm:cooling-loss', relation='MITIGATED_BY', kind='control', approver='role:operator',
                        actions=[dict(action='action:set-fan', value=100)], affects=[dict(target='sv:fan-speed', sign='+', note='60 → 100')]),
    'SOP-COOL-12': dict(failureMode='fm:cooling-loss', relation='MITIGATED_BY', kind='control', approver='role:operator',
                        actions=[dict(action='action:set-fan', value=100), dict(action='action:set-load', value=80)],
                        affects=[dict(target='sv:fan-speed', sign='+'), dict(target='sv:load', sign='-', note='90 → 80')]),
    'SOP-COOL-13': dict(failureMode='fm:cooling-loss', relation='MITIGATED_BY', kind='control', approver='role:operator',
                        actions=[dict(action='action:set-load', value=70)] + _wo('SOP-COOL-14'), addresses=['cause:cooler-fin-fouling'],
                        affects=[dict(target='sv:load', sign='-', note='90 → 70'), dict(target='sv:fouling', sign='-')]),
    'SOP-COOL-14': dict(failureMode='fm:cooling-loss', relation='REMEDIED_BY', kind='work_order', approver='role:maint-mgr',
                        actions=_wo('SOP-COOL-14'), addresses=['cause:cooler-fin-fouling'],
                        affects=[dict(target='sv:fouling', sign='-'), dict(target='msr:maint-cost', sign='+')]),
    'SOP-COOL-15': dict(failureMode='fm:cooling-loss', relation='REMEDIED_BY', kind='work_order', approver='role:maint-mgr',
                        actions=_wo('SOP-COOL-15'), addresses=['cause:high-ambient'],
                        affects=[dict(target='sv:ts1', sign='-'), dict(target='msr:maint-cost', sign='+')]),
}

C_PURCHASE = ['SOP-PUR-11', 'SOP-PUR-12', 'SOP-PUR-13']
C_KNOWLEDGE = {
    'failure_modes': [], 'causes': [], 'evidence': [],
    'rules': [
        dict(id='rule:cand-spare-purchase', table='dt:action-candidates', effect='SELECT',
             tests=[dict(input='in:pattern', operator='==', value='SPARE_BELOW_MIN')], outputs=C_PURCHASE,
             annotation='재고 기준 이탈 → 발주 절차 3안', section='PR-7.6', quote='재고 기준 이탈 경보로 열린 처리 건에서만 아래 발주 절차를 쓴다.'),
        dict(id='rule:pur-equipment-alert', table='dt:compliance', effect='EXCLUDE',
             tests=[dict(input='in:pattern', operator='!=', value='SPARE_BELOW_MIN')], applies_to=C_PURCHASE,
             annotation='설비 경보 처리 건에서는 발주 절차 제외', section='PR-7.6', quote='설비 경보로 열린 처리 건에서는 발주 절차를 후보로 내지 않는다.'),
        dict(id='rule:pur-avl', table='dt:compliance', effect='EXCLUDE',
             tests=[dict(input='in:supplier-avl', operator='==', value=False)], applies_to=C_PURCHASE,
             annotation='비승인 공급사 발주 금지(긴급 포함)', section='PR-7.3', quote='긴급 발주여도 승인되지 않은 공급사에는 발주하지 않는다.'),
        dict(id='rule:pur-amount', table='dt:compliance', effect='WARN',
             tests=[dict(input='in:po-amount', operator='>', value=300, unit='만원')], applies_to=C_PURCHASE,
             annotation='300만 원 초과 — 전결 기준 초과 표시(승인은 구매 담당 1회)', section='PR-7.5',
             quote='300만 원을 넘으면 발주안 요약에 전결 기준 초과를 표시하고'),
        # 입력 in:supplier-fail-rate(시드 구조, 2026-10-10)가 생기기 전에는 skill_code == PR_CREATE + applies_to SOP-PUR-12로
        # "SOP-PUR-12의 공급사는 불량 10 % 초과"를 손으로 박았다 — 다른 SOP가 같은 공급사를 가리키면 감점이 빠졌다(라이브 4차).
        dict(id='rule:pur-inspection', table='dt:compliance', effect='PENALTY', penalty=20, penalizes='msr:part-quality',
             tests=[dict(input='in:supplier-fail-rate', operator='>', value=0.1)], applies_to=C_PURCHASE,
             annotation='불량률 10 % 초과 승인 공급사 — 전수 검사 비용 20만 원 감점', section='PR-7.4',
             quote='불량률이 10 %를 넘는 승인 공급사에 발주할 때는 입고 검사를 전수 검사로 강화하고, 전수 검사 비용 20만 원을 더해 비교한다.'),
        dict(id='rule:pur-lead', table='dt:compliance', effect='WARN',
             tests=[dict(input='in:lead-slack-days', operator='<', value=0, unit='일')], applies_to=C_PURCHASE,
             annotation='리드타임이 필요일보다 길면 결품 위험', section='PR-7.4',
             quote='리드타임이 필요일(결품 전 남은 날)보다 길면 그 공급사로는 결품을 막지 못한다.')],
}


def _purchase(supplier, cost, quality):
    return dict(failureMode='fm:volumetric-loss', relation='REMEDIED_BY', kind='work_order', approver='role:purchasing',
                actions=[dict(action='action:purchase-request', value=supplier)], addresses=['cause:pump-seal-wear'],
                affects=[dict(target='msr:part-cost', sign=cost), dict(target='msr:part-quality', sign=quality)])


C_LINKS = {'SOP-PUR-11': _purchase('sup:b', '+', '+'), 'SOP-PUR-12': _purchase('sup:a', '-', '-'), 'SOP-PUR-13': _purchase('sup:c', '-', '-')}

STANDIN_KNOWLEDGE = {
    'failure_modes': [dict(id='fm:volumetric-loss', name='펌프 체적 효율 저하', component='comp:pump-a', symptoms=['sym:ps1-drop', 'sym:fs1-drop'],
                           section='TP-1.1', quote='펌프 체적 효율 저하는 주 펌프 A에서 생기며 토출 압력과 유량이 함께 떨어진다.')],
    'causes': [dict(id='cause:pump-seal-wear', name='펌프 축 씰 마모', prior=0.7, failure_mode='fm:volumetric-loss', parts=['part:pump-seal'],
                    disturbs=[dict(target='sv:leak', sign=1)], section='TP-1.1', quote='가장 흔한 원인은 축 씰 마모다(사전 확률 0.7).')],
    'evidence': [], 'rules': []}
STANDIN_LINKS = {'SOP-TPMP-01': dict(failureMode='fm:volumetric-loss', relation='REMEDIED_BY', kind='work_order', approver='role:maint-mgr',
                                     actions=_wo('SOP-TPMP-01'), addresses=['cause:pump-seal-wear'])}

# ---------------------------------------------------------------- B 정기 정비 (PM-02)
B_OPTIONS = ['SOP-PM-11', 'SOP-PM-12', 'SOP-PM-13', 'SOP-PM-14']      # 이번 정비 시간 단독 · 지금 정지 · 미루기 · 두 대 묶기
B_NOW = ['SOP-PM-11', 'SOP-PM-12', 'SOP-PM-14']                      # 지금 부품을 쓰는 방식
B_KNOWLEDGE = {
    'failure_modes': [dict(id='fm:volumetric-loss', name='펌프 체적 효율 저하', component='comp:pump-a', symptoms=['sym:ps1-drop', 'sym:fs1-drop'],
                           section='PM-2.10', quote='펌프 체적 효율 저하는 주 펌프 A에서 생기며 토출 압력과 유량이 함께 떨어진다.')],
    'causes': [
        dict(id='cause:pump-seal-wear', name='펌프 축 씰 마모', aliases=['씰 마모'], prior=0.7, failure_mode='fm:volumetric-loss',
             parts=['part:pump-seal'], disturbs=[dict(target='sv:leak', sign=1)], section='PM-2.10', quote='가장 흔한 원인은 축 씰 마모다(사전 확률 0.7).'),
        dict(id='cause:oil-contamination', name='작동유 오염', aliases=['리턴 필터 막힘'], prior=0.3, failure_mode='fm:volumetric-loss',
             parts=['part:return-filter'], disturbs=[dict(target='sv:leak', sign=1)], section='PM-2.10',
             quote='작동유 오염(리턴 필터가 막혀 걸러지지 않은 입자가 펌프를 닳게 함)은 사전 확률 0.3으로 본다.')],
    'evidence': [
        dict(id='evd:pm-ps1-low', cause='cause:pump-seal-wear', name='토출 압력 평균 165 bar 미만 (최근 1분)', tag='PS1', aggregate='avg',
             window_seconds=60, expect='lt', threshold=165, weight=1.0, section='PM-2.10', quote='최근 1분 토출 압력 PS1 평균이 165 bar 미만이면'),
        dict(id='evd:pm-fs1-low', cause='cause:oil-contamination', name='유량 평균 8.0 l/min 미만 (최근 1분)', tag='FS1', aggregate='avg',
             window_seconds=60, expect='lt', threshold=8.0, weight=0.5, section='PM-2.10', quote='최근 1분 유량 FS1 평균이 8.0 l/min 미만이면')],
    'rules': [
        dict(id='rule:dx-pump-seal', table='dt:diagnose-cause', effect='SELECT',
             tests=[dict(input='in:pattern', operator='==', value='PUMP_LEAKAGE'), dict(input='in:ps1', operator='<', value=165, unit='bar')],
             outputs=['cause:pump-seal-wear'], annotation='토출 압력이 낮으면 축 씰 마모가 1순위', section='PM-2.10',
             quote='경보 패턴 PUMP_LEAKAGE가 떴을 때 토출 압력이 165 bar 미만이면 축 씰 마모를 1순위 원인으로 둔다.'),
        dict(id='rule:cand-pm-due', table='dt:action-candidates', effect='SELECT',
             tests=[dict(input='in:pattern', operator='==', value='PM_DUE'), dict(input='in:hours-since-pm', operator='>=', value=1800, unit='h')],
             outputs=B_OPTIONS, annotation='정기 정비 도래(허용 오차 하한 1,800 h 이상) → 시행 방식 네 가지 비교', section='PM-2.5',
             quote='정기 정비 도래로 열린 처리 건에서 마지막 정기 정비 뒤 운전시간이 허용 오차 하한 1,800 h 이상이면 아래 시행 방식 네 가지를 비교한다.'),
        dict(id='rule:pm-window-limit', table='dt:compliance', effect='EXCLUDE',
             tests=[dict(input='in:next-scheduled-time', operator='>', value=2200, unit='h')], applies_to=['SOP-PM-11', 'SOP-PM-14'],
             annotation='이번 예정된 정비 시간이 허용 오차 상한 2,200 h를 넘으면 기다리지 않음', section='PM-2.5',
             quote='이번 예정된 정비 시간에 닿을 때의 운전시간이 2,200 h를 넘으면 그 시간까지 기다리지 않는다.'),
        dict(id='rule:pm-defer-limit', table='dt:compliance', effect='EXCLUDE',
             tests=[dict(input='in:hours-if-deferred', operator='>', value=2200, unit='h')], applies_to=['SOP-PM-13'],
             annotation='미루면 허용 오차 상한 2,200 h를 넘음 — 보증 기록 요건 위반', section='PM-2.5',
             quote='그다음 예정된 정비 시간까지 미룰 때의 운전시간이 2,200 h를 넘으면 미루지 않는다(보증 기록 요건 위반).'),
        dict(id='rule:pm-stop-order', table='dt:compliance', effect='PENALTY', penalty=80, penalizes='msr:penalty',
             tests=[dict(input='in:order-due', operator='<', value=24, unit='h')], applies_to=['SOP-PM-12'],
             annotation='납기 24시간 안 생산 오더가 있는데 지금 정지 — 오더 손실 감점', section='PM-2.5',
             quote='납기가 24시간 안에 있는 생산 오더가 있는데 지금 바로 설비를 세우면 오더 손실로 80만 원을 감점해서 비교한다.'),
        dict(id='rule:pm-bundle-crew', table='dt:compliance', effect='PENALTY', penalty=60, penalizes='msr:maint-cost',
             tests=[dict(input='in:pm-crew', operator='<', value=4, unit='명')], applies_to=['SOP-PM-14'],
             annotation='두 대 묶음에 정비 인원 4명 미만 — 초과 근무 · 외주 감점', section='PM-2.5',
             quote='그 시간의 정비 인원이 4명보다 적으면 초과 근무 · 외주 비용으로 60만 원을 감점해서 비교한다.'),
        dict(id='rule:pm-spare-warn', table='dt:compliance', effect='WARN',
             tests=[dict(input='in:spare-available', operator='<', value=3, unit='ea')], applies_to=B_NOW,
             annotation='씰 키트 출고 뒤 재주문점 아래 — 구매 경보 예정', section='PM-2.5',
             quote='씰 키트 가용 재고가 3개 미만이면 출고 뒤 재주문점(2개) 아래로 내려가므로, 제안에 구매 경보 예정을 표시한다.'),
        dict(id='rule:pm-spare-none', table='dt:compliance', effect='EXCLUDE',
             tests=[dict(input='in:spare-available', operator='<', value=1, unit='ea')], applies_to=B_NOW,
             annotation='씰 키트가 없으면 시행 불가', section='PM-2.5', quote='씰 키트 가용 재고가 없으면 정기 정비를 시행하지 않는다.'),
        dict(id='rule:pm-bundle-spare', table='dt:compliance', effect='EXCLUDE',
             tests=[dict(input='in:spare-available', operator='<', value=2, unit='ea')], applies_to=['SOP-PM-14'],
             annotation='두 대 묶음에는 씰 키트 2개 필요', section='PM-2.5', quote='두 대를 묶으려면 씰 키트가 2개 이상 있어야 한다.')],
}


def _pm(affects, value='SOP-PM-21', addresses=None):
    link = dict(failureMode='fm:volumetric-loss', relation='PREVENTED_BY', kind='work_order', approver='role:maint-mgr',
                actions=_wo(value), affects=[dict(target=t, sign=s, note=n) for t, s, n in affects])
    if addresses:
        link['addresses'] = addresses
    return link


B_LINKS = {
    'SOP-PM-11': _pm([('msr:mtbf', '+', '씰 · 필터를 제때 바꿔 고장을 막음'), ('msr:maint-cost', '+', '정기 정비 비용')]),
    'SOP-PM-12': _pm([('msr:mtbf', '+', '씰 · 필터 교체'), ('msr:maint-cost', '+', '정기 정비 비용'),
                      ('msr:availability', '-', '생산 중 정지'), ('msr:throughput', '-', '정비 시간만큼 생산 멈춤')]),
    'SOP-PM-13': _pm([('msr:availability', '+', '지금은 서지 않음'), ('msr:mtbf', '-', '씰이 더 오래 닳음')]),
    'SOP-PM-14': _pm([('msr:mtbf', '+', '두 대 모두 교체'), ('msr:maint-cost', '+', '정비 인원 두 배'),
                      ('msr:availability', '+', '정지 횟수 한 번 줄어듦')]),
    'SOP-PM-21': _pm([], 'SOP-PM-21', ['cause:pump-seal-wear', 'cause:oil-contamination']),
    'SOP-PM-22': _pm([], 'SOP-PM-22', ['cause:pump-seal-wear', 'cause:oil-contamination']),
    'SOP-PM-23': _pm([], 'SOP-PM-23', ['cause:pump-seal-wear', 'cause:oil-contamination']),
}
for _sop in ('SOP-PM-21', 'SOP-PM-22', 'SOP-PM-23'):
    del B_LINKS[_sop]['affects']

DOCS = {'A': (DOC_A, A_KNOWLEDGE, A_LINKS), 'B': (DOC_B, B_KNOWLEDGE, B_LINKS), 'C': (DOC_C, C_KNOWLEDGE, C_LINKS)}

# B 판단 사실(시나리오 보고서 2026-10-09 B): 운전시간 1,950 h에 도래 경보, 이번 예정된 정비 시간 9 h 뒤(1,959 h),
# 그다음 예정된 정비 시간은 다음 주 계획 정지(2,230 h, 상한 넘음), 납기 20 h 생산 오더, 정비 인원 2명, 씰 키트 가용 2개.
B_FACTS = dict(pattern='PM_DUE', hours_since_pm=1950, hours_at_next_window=1959, hours_at_following_window=2230,
               order_due_h=20, order_penalty_per_h=50, pm_crew_available=2, spare_available=2,
               plc_mode='REMOTE_AUTO', plc_state='RUN', failure_mode=None, cause=None)


def anchor(source, quote):
    hits = [(p['page'], p['text'].find(quote)) for p in source['pages'] if quote in p['text']]
    assert len(hits) == 1 and source['pages'][hits[0][0] - 1]['text'].count(quote) == 1, f'인용이 문서에 한 번만 있어야 합니다: {quote}'
    page, start = hits[0]
    return dict(source_id=source['source_id'], page=page, start=start, end=start + len(quote), quote=quote)


def knowledge(source, spec):
    out = {}
    for kind, items in spec.items():
        out[kind] = []
        for item in items:
            item = deepcopy(item)
            item['anchor'] = anchor(source, item.pop('quote'))
            out[kind].append(item)
    return out


def proposal(source, spec, links):
    """The extraction contract shape (manual-source-proposal-v1, definition 2.0): sections · procedures · page_reviews ·
    warnings from the structured parse, plus knowledge and a suggested link per SOP."""
    from procsvc import manual_review
    parsed = manual_review.proposal(source)
    procs = []
    for p in parsed['procedures']:
        p = {k: p[k] for k in ('id', 'name', 'section', 'anchor', 'steps')}
        if p['id'] in links:
            p['link'] = deepcopy(links[p['id']])
        procs.append(p)
    return dict(source_id=source['source_id'], sections=parsed['sections'], procedures=procs,
                page_reviews=[dict(page=pg['page'], note='검토함') for pg in source['pages']], warnings=[],
                knowledge=knowledge(source, spec))


def reviewed_body(source, prop, by='검토자'):
    """What the review screen sends after a person confirmed every suggestion (POST /api/kg/manuals/commit)."""
    from procsvc import manual_review
    parsed = manual_review.proposal(source)
    links = {p['id']: p['link'] for p in prop['procedures'] if p.get('link')}
    return dict(parsed, sections=prop['sections'], procedures=[{k: v for k, v in p.items() if k != 'link'} for p in prop['procedures']],
                knowledge=prop['knowledge'], links=links, by=by, reviewed=True)
