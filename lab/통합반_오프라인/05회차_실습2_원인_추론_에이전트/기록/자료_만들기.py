"""통합반 오프라인 05회차 실습 2의 시작 폴더 자료(온톨로지/graph.json · schema.json)를 만든다.
저장소의 it/neo4j/v2/instances.cypher · knowledge_a098.cypher(전체판 시드)와 docs/samples/HM-8_cooler-fan-manual.md 에서
이 실습이 쓰는 부분만 손으로 옮겨 적었다. schema.json 은 it/neo4j/v2/schema.json 에서 쓰는 클래스와 관계만 추린다.
사용: python3 자료_만들기.py <저장소 루트> <내보낼 폴더>"""
import json, sys
from pathlib import Path
REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
N, R = [], []
def node(label, **p): N.append({'labels': [label], 'props': p})
def rel(t, a, b, **p): R.append({'type': t, 'a': a, 'b': b, 'props': p})

# 설비 · 구성 요소 (instances.cypher:109-116)
for c in ('01', '02', '03'): node('Asset', id=f'asset:hyd-{c}', name=f'HYD-{c} 유압 파워팩', code=f'HYD-{c}')
COMP = [('comp:cooler', '오일 쿨러', ['쿨러', '열교환기']), ('comp:fan', '쿨러 팬', ['팬', '송풍기']), ('comp:pump-a', '주 펌프 (A)', ['펌프', '유압 펌프']),
        ('comp:pump-b', '예비 펌프 (B)', ['스탠바이 펌프']), ('comp:motor', '구동 모터', ['모터']), ('comp:tank', '작동유 탱크', ['탱크', '리저버'])]
for i, n, a in COMP:
    node('Component', id=i, name=n, aliases=a)
    for c in ('01', '02', '03'): rel('HAS_COMPONENT', f'asset:hyd-{c}', i)
# 상태 변수 (instances.cypher:119-129)
for r in [['sv:fan-speed', '팬 속도', ['팬 회전수'], '%', 'manipulated', 60, None], ['sv:load', '펌프 부하', ['부하', '생산 속도 설정'], '%', 'manipulated', 90, None],
          ['sv:ts1', '유온', ['오일 온도', '작동유 온도', 'TS1'], '℃', 'controlled', 48, 65], ['sv:ce', '냉각 효율', ['쿨러 효율', 'CE'], '%', 'controlled', 84, None],
          ['sv:ps1', '토출 압력', ['펌프 압력', 'PS1'], 'bar', 'controlled', 182, 130], ['sv:fs1', '유량', ['토출 유량', 'FS1'], 'l/min', 'controlled', 9, None],
          ['sv:vs1', '팬 진동', ['진동', 'VS1'], 'mm/s', 'controlled', 0.6, 2.0], ['sv:leak', '펌프 내부 누설', ['누설률'], '%', 'disturbance', 0, None],
          ['sv:fouling', '쿨러 핀 오염도', ['핀 막힘', '오염'], '%', 'disturbance', 0, None], ['sv:bearing-wear', '팬 베어링 마모도', ['베어링 마모'], '%', 'disturbance', 0, None]]:
    node('StateVariable', id=r[0], name=r[1], aliases=r[2], unit=r[3], kind=r[4], normal=r[5], limit=r[6])
# 센서 (instances.cypher:132-136)
for r in [['sen:ts1', '유온 센서', 'TS1', '℃', False, 'comp:cooler', 'sv:ts1'], ['sen:ce', '냉각 효율 (가상)', 'CE', '%', True, 'comp:cooler', 'sv:ce'],
          ['sen:ps1', '토출 압력 센서', 'PS1', 'bar', False, 'comp:pump-a', 'sv:ps1'], ['sen:fs1', '유량 센서', 'FS1', 'l/min', False, 'comp:pump-a', 'sv:fs1'],
          ['sen:vs1', '팬 진동 센서', 'VS1', 'mm/s', False, 'comp:fan', 'sv:vs1']]:
    node('Sensor', id=r[0], name=r[1], tag=r[2], unit=r[3], virtual=r[4]); rel('MONITORED_BY', r[5], r[0]); rel('OBSERVES', r[0], r[6])
# 물리 영향 가운데 상태 변수끼리의 것 (instances.cypher:146-156)
for r in [['sv:fan-speed', 'sv:ts1', -1, 'high', None, '팬을 올리면 냉각이 늘어 유온이 내려간다'], ['sv:fan-speed', 'sv:vs1', 1, 'medium', '베어링 마모 시 크게', '팬이 빠를수록 진동이 크다'],
          ['sv:load', 'sv:ts1', 1, 'high', None, '부하의 제곱에 비례해 발열'], ['sv:load', 'sv:ps1', 1, 'medium', None, None], ['sv:ce', 'sv:ts1', -1, 'high', None, None],
          ['sv:fouling', 'sv:ce', -1, 'high', None, '핀이 막히면 냉각 효율이 떨어진다'], ['sv:leak', 'sv:ps1', -1, 'high', None, '내부 누설만큼 토출 압력이 떨어진다'],
          ['sv:leak', 'sv:fs1', -1, 'high', None, None], ['sv:leak', 'sv:ts1', 1, 'low', None, '누설 유량이 열이 된다'], ['sv:bearing-wear', 'sv:vs1', 1, 'high', None, None]]:
    rel('INFLUENCES', r[0], r[1], **{k: v for k, v in zip(('sign', 'strength', 'condition', 'note'), r[2:]) if v is not None})
# 역할 (instances.cypher:98-100)
for r in [['role:operator', '운전원', 1], ['role:prod-mgr', '생산관리자', 2], ['role:maint-mgr', '설비보전팀장', 2], ['role:plant-mgr', '공장장', 3]]:
    node('Role', id=r[0], name=r[1], level=r[2])
# 이상 패턴 (instances.cypher:206-209, knowledge_a098.cypher)
for r in [['pattern:cooler-degradation', '쿨러 성능 저하', 'COOLER_DEGRADATION', 'TS1 > 55 and CE < 70 and slope(TS1) > 0', 60],
          ['pattern:pump-leakage', '펌프 내부 누설', 'PUMP_LEAKAGE', "PLC.state == 'RUN' and PS1 < 165 and FS1 < 8.0 and LoadSP >= 80", 60],
          ['pattern:fan-vibration', '팬 진동 상승', 'FAN_VIBRATION', 'VS1 > 1.2 and slope(VS1) > 0', 60],
          ['pattern:overheat-trip', '과열 인터록 트립', 'OVERHEAT_TRIP', 'PLC state == TRIP', 0],
          ['pattern:low-pressure-trip', '저압 인터록 트립', 'LOW_PRESSURE_TRIP', 'PLC state == TRIP (PS1 < 130 bar)', 0],
          ['pattern:high-vibration-trip', '고진동 인터록 트립', 'HIGH_VIBRATION_TRIP', 'PLC state == TRIP (VS1 >= 2.0 mm/s)', 0],
          ['pattern:oil-analysis', '오일 분석 기준 이탈 (사람 입력)', 'OIL_ANALYSIS', 'TAN delta >= 2 or water > 2500 ppm or ISO 4406 +2 codes or viscosity out of grade', 0]]:
    node('AnomalyPattern', id=r[0], name=r[1], code=r[2], rule=r[3], holdSeconds=r[4])
# 증상 (instances.cypher:212-216, knowledge_a098.cypher)
for r in [['sym:ts1-rise', '유온 상승', ['온도 상승', '과열'], ['sen:ts1'], ['pattern:cooler-degradation', 'pattern:overheat-trip']],
          ['sym:ce-drop', '냉각 효율 저하', ['냉각 불량'], ['sen:ce'], ['pattern:cooler-degradation']],
          ['sym:ps1-drop', '토출 압력 저하', ['압력 저하', '압력 떨어짐'], ['sen:ps1'], ['pattern:pump-leakage', 'pattern:low-pressure-trip']],
          ['sym:fs1-drop', '유량 저하', ['유량 감소'], ['sen:fs1'], ['pattern:pump-leakage']],
          ['sym:vs1-rise', '진동 증가', ['떨림', '소음'], ['sen:vs1'], ['pattern:fan-vibration', 'pattern:high-vibration-trip']]]:
    node('Symptom', id=r[0], name=r[1], aliases=r[2])
    for s in r[3]: rel('OBSERVED_BY', r[0], s)
    for p in r[4]: rel('DETECTS', p, r[0])
node('Symptom', id='sym:oil-analysis-out-of-spec', name='오일 분석 기준 이탈', aliases=['TAN 상승', '수분 2,500 ppm 초과', 'ISO 4406 등급 2단계 악화', '점도 변화'],
     note='실시간 센서가 없다. 정기 오일 분석(점도 · 산가 TAN · 수분 Karl Fischer · 청정도 ISO 4406) 결과를 사람이 입력한다.')
rel('DETECTS', 'pattern:oil-analysis', 'sym:oil-analysis-out-of-spec')
# 고장 유형. 냉각 성능 상실은 HM-8.4(덱과 같은 이름과 식별자), 나머지는 전체판 시드(instances.cypher:222-233, knowledge_a098.cypher)
for r in [['fm:cooler-performance-loss', '쿨러 냉각 성능 상실', 'comp:cooler', ['sym:ts1-rise', 'sym:ce-drop']],
          ['fm:volumetric-loss', '펌프 체적 효율 저하', 'comp:pump-a', ['sym:ps1-drop', 'sym:fs1-drop']],
          ['fm:bearing-degradation', '팬 베어링 열화', 'comp:fan', ['sym:vs1-rise']],
          ['fm:overheat-trip', '과열 정지', 'comp:motor', ['sym:ts1-rise']],
          ['fm:oil-degradation', '작동유 열화', 'comp:tank', ['sym:oil-analysis-out-of-spec']],
          ['fm:low-pressure-trip', '저압 정지', 'comp:pump-a', ['sym:ps1-drop']],
          ['fm:high-vibration-trip', '고진동 정지', 'comp:fan', ['sym:vs1-rise']]]:
    node('FailureMode', id=r[0], name=r[1]); rel('OCCURS_IN', r[0], r[2])
    for s in r[3]: rel('INDICATES', s, r[0])
for a, b in [['fm:cooler-performance-loss', 'fm:overheat-trip'], ['fm:cooler-performance-loss', 'fm:oil-degradation'], ['fm:volumetric-loss', 'fm:oil-degradation'],
             ['fm:bearing-degradation', 'fm:cooler-performance-loss'], ['fm:volumetric-loss', 'fm:low-pressure-trip'], ['fm:bearing-degradation', 'fm:high-vibration-trip']]:
    rel('LEADS_TO', a, b)
# 원인. 냉각 셋은 HM-8.4, 나머지는 시드(instances.cypher:236-246, knowledge_a098.cypher)
for r in [['cause:cooler-fin-fouling', '쿨러 핀 오염', ['핀 오염', '핀 막힘'], 0.6, 'fm:cooler-performance-loss', 'HM-8.4'],
          ['cause:ambient-high-temp', '주변 온도 상승', ['외기 고온', '캐비닛 환기 불량'], 0.2, 'fm:cooler-performance-loss', 'HM-8.4'],
          ['cause:fan-drive-fault', '팬 구동 불량', ['벨트 슬립', '베어링 마모'], 0.2, 'fm:cooler-performance-loss', 'HM-8.4'],
          ['cause:pump-seal-wear', '펌프 축 씰 마모', ['씰 마모', '내부 누설'], 0.7, 'fm:volumetric-loss', None],
          ['cause:fan-bearing-wear', '팬 베어링 마모', ['베어링 마모', '베어링 손상'], 0.8, 'fm:bearing-degradation', None],
          ['cause:oil-oxidation', '고온 운전에 의한 산화', ['산화', '열 열화'], 0.4, 'fm:oil-degradation', None],
          ['cause:water-ingress', '수분 혼입', ['수분', '물 혼입', '결로'], 0.25, 'fm:oil-degradation', None],
          ['cause:particle-contamination', '오염 입자 유입', ['오염', '마모 입자', '청정도 저하'], 0.25, 'fm:oil-degradation', None],
          ['cause:change-interval-exceeded', '교환 주기 초과', ['장기 사용', '교환 지연'], 0.1, 'fm:oil-degradation', None]]:
    p = dict(id=r[0], name=r[1], aliases=r[2], prior=r[3])
    if r[5]: p['section'] = r[5]
    node('Cause', **p); rel('CAUSES', r[0], r[4])
for a, b in [['cause:cooler-fin-fouling', 'sv:fouling'], ['cause:pump-seal-wear', 'sv:leak'], ['cause:fan-bearing-wear', 'sv:bearing-wear']]: rel('DISTURBS', a, b, sign=1)
# 증거. [id, 원인, 이름, rule, tag, aggregate, windowSeconds, expect, threshold, section]
for r in [['evd:fin-fouling-ce-low', 'cause:cooler-fin-fouling', '최근 30초 냉각 효율 평균 70 % 미만', 'avg(CE) over 30s < 70', 'CE', 'avg', 30, 'lt', 70, 'HM-8.4'],
          ['evd:fin-fouling-vs1-normal', 'cause:cooler-fin-fouling', '최근 2분 팬 진동 VS1 평균 0.9 mm/s 미만 (팬은 정상)', 'avg(VS1) over 2m < 0.9', 'VS1', 'avg', 120, 'lt', 0.9, 'HM-8.4'],
          ['evd:ambient-ts4-high', 'cause:ambient-high-temp', '최근 2분 캐비닛 온도 TS4 평균 35 ℃ 이상', 'avg(TS4) over 2m >= 35', 'TS4', 'avg', 120, 'gte', 35, 'HM-8.4'],
          ['evd:fan-drive-vs1-high', 'cause:fan-drive-fault', '최근 2분 팬 진동 VS1 평균 0.9 mm/s 이상', 'avg(VS1) over 2m >= 0.9', 'VS1', 'avg', 120, 'gte', 0.9, 'HM-8.4'],
          ['evd:ps1-low', 'cause:pump-seal-wear', '토출 압력 평균 165 bar 미만', 'avg(PS1) over 2m < 165', 'PS1', 'avg', 120, 'lt', 165, None],
          ['evd:fs1-drop', 'cause:pump-seal-wear', '유량 평균 8.0 l/min 미만', 'avg(FS1) over 2m < 8.0', 'FS1', 'avg', 120, 'lt', 8.0, None],
          ['evd:vs1-trend', 'cause:fan-bearing-wear', '진동 상승폭 0.2 mm/s 초과 (최근 5분)', 'max(VS1) - min(VS1) over 5m > 0.2', 'VS1', 'max-min', 300, 'gt', 0.2, None],
          ['evd:ts1-normal', 'cause:fan-bearing-wear', '유온 52 ℃ 미만 (냉각 문제 아님)', 'avg(TS1) over 2m < 52', 'TS1', 'avg', 120, 'lt', 52, None]]:
    p = dict(id=r[0], name=r[2], rule=r[3], tag=r[4], aggregate=r[5], windowSeconds=r[6], expect=r[7], threshold=r[8])
    if r[9]: p['section'] = r[9]
    node('Evidence', **p); rel('EVIDENCED_BY', r[1], r[0])
# 조치 방법(스킬 = SOP). [id, name, sopId, kind, description, 승인 역할, [[단계, 근거 절]]]
SK = [
 ['skill:sop-cool-11', '팬 최대 운전', 'SOP-COOL-11', 'control', '팬만 100 %로 올린다. 생산은 그대로 유지된다.', 'role:operator',
  [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-8.5'], ['팬 속도를 100 %로 올린다. 100 % 연속 운전은 24시간 이내로 한다.', 'HM-8.5'], ['15분 재관측으로 HM-8.6 회복 판정을 한다.', 'HM-8.6']]],
 ['skill:sop-cool-12', '팬 최대 운전과 부하 80 %', 'SOP-COOL-12', 'control', '팬 100 %와 부하 80 %. 생산 속도가 줄어든다.', 'role:operator',
  [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-8.5'], ['팬 속도를 100 %로 올린다.', 'HM-8.5'], ['펌프 부하를 80 %로 낮춘다.', 'HM-8.5'], ['15분 재관측으로 HM-8.6 회복 판정을 한다.', 'HM-8.6']]],
 ['skill:sop-cool-13', '부하 70 %와 야간 핀 세척', 'SOP-COOL-13', 'control', '팬은 그대로 두고 부하를 70 %로 낮춘 뒤 야간 정비 시간에 핀 세척 작업지시를 건다. 생산 속도가 줄어든다.', 'role:operator',
  [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-8.5'], ['펌프 부하를 70 %로 낮춘다. 팬 속도는 그대로 둔다.', 'HM-8.5'], ['15분 재관측으로 HM-8.6 회복 판정을 한다.', 'HM-8.6'], ['야간 예정된 정비 시간에 SOP-COOL-14 핀 세척 작업지시를 건다.', 'HM-8.5']]],
 ['skill:sop-cool-14', '쿨러 핀 세척', 'SOP-COOL-14', 'work_order', '설비를 세우고 쿨러 핀을 세척한다. CMMS 작업지시로 발행한다.', 'role:maint-mgr',
  [['설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.', 'HM-8.7'], ['압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.', 'HM-8.7'], ['재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.', 'HM-8.7']]],
 ['skill:sop-cool-15', '캐비닛 환기 보강', 'SOP-COOL-15', 'work_order', '캐비닛 환기를 보강한다. CMMS 작업지시로 발행한다.', 'role:maint-mgr',
  [['캐비닛 온도 TS4와 외기 온도를 기록한다.', 'HM-8.7'], ['환기 필터를 청소하고 배기 팬 동작을 점검한다.', 'HM-8.7'], ['캐비닛 온도가 35 ℃ 아래로 내려왔는지 확인한다.', 'HM-8.7']]],
 ['skill:sop-fan-11', '쿨러 팬 점검 절차', 'SOP-FAN-11', 'work_order', '벨트 슬립이나 베어링 마모가 의심될 때 쿨러 팬을 점검한다.', None,
  [['설비를 정지하고 현장 패널에서 LOCAL로 전환한다.', 'HM-8.1'], ['벨트 처짐을 측정한다 (기준 10~15 mm).', 'HM-8.1'], ['베어링 소음과 표면 온도를 확인한다 (60 ℃ 이하).', 'HM-8.1'], ['재가동 후 VS1이 0.9 mm/s 아래로 내려왔는지 확인한다.', 'HM-8.1']]],
 ['skill:sop-fan-12', '벨트 교체 절차', 'SOP-FAN-12', 'work_order', '벨트 처짐이 기준을 벗어나거나 균열이 보이면 교체한다.', None,
  [['LOCAL 전환과 잠금(LOTO)을 확인한다.', 'HM-8.2'], ['구 벨트를 분리하고 풀리 정렬을 점검한다.', 'HM-8.2'], ['새 벨트를 걸고 처짐을 12 mm로 맞춘다.', 'HM-8.2'], ['30분 시운전 뒤 냉각 효율 CE가 80 % 이상인지 확인한다.', 'HM-8.2']]],
 ['skill:switch-standby-pump', '예비 펌프 전환', 'SOP-PMP-01', 'control', '예비 펌프 B로 전환해 압력을 즉시 회복한다.', 'role:prod-mgr',
  [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-3.2'], ['예비 펌프 B로 무부하 전환한다.', 'HM-5.2'], ['30초 안에 PS1이 175 bar 이상으로 회복됐는지 확인한다.', 'HM-5.2']]],
 ['skill:derate-70', '부하 70 %', 'SOP-PMP-02', 'control', '부하를 70 %로 낮춰 압력 부족과 누설 진행을 늦춘다.', 'role:operator',
  [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-3.2'], ['펌프 부하를 70 %로 낮춘다.', 'HM-9.1'], ['PS1 하락이 멈췄는지 10분간 확인한다.', 'HM-5.2']]],
 ['skill:raise-pressure', '압력 설정 상향 (구 절차)', 'SOP-PMP-03', 'control', '압력 설정을 10 bar 올려 부족분을 메운다. 개정 매뉴얼에서 누설 시 금지된 옛 절차다.', 'role:operator',
  [['압력 설정을 10 bar 올린다. 누설 의심 시에는 금지 (개정 HM-5.4).', 'HM-5.4'], ['PS1이 175 bar 이상인지 확인한다.', 'HM-5.2']]],
 ['skill:wo-pump-seal', '펌프 축 씰 교체', 'SOP-PMP-04', 'work_order', '씰 키트를 구매요청하고 교체 작업지시를 발행한다.', 'role:maint-mgr',
  [['주 펌프를 LOCAL로 전환하고 잠근다.', 'HM-3.1'], ['씰 키트를 교체한다.', 'HM-5.6'], ['누설 시험 후 주 펌프로 복귀한다.', 'HM-5.6']]],
 ['skill:fan-slow-derate', '팬 40 % + 부하 80 %', 'SOP-FAN-01', 'control', '팬을 낮춰 진동을 줄이고 부하도 낮춰 유온 상승을 막는다.', 'role:prod-mgr',
  [['팬 속도를 40 %로 낮춘다.', 'HM-8.1'], ['유온이 55 ℃를 넘지 않도록 부하를 80 %로 낮춘다.', 'HM-9.1'], ['VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.', 'HM-8.1']]],
 ['skill:fan-slow', '팬 40 %', 'SOP-FAN-02', 'control', '팬만 40 %로 낮춘다. 생산은 그대로 유지한다.', 'role:operator',
  [['팬 속도를 40 %로 낮춘다.', 'HM-8.1'], ['유온을 15분간 감시한다. 55 ℃를 넘으면 부하를 낮춘다.', 'HM-7.5'], ['VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.', 'HM-8.1']]],
 ['skill:planned-stop', '계획 정지 + 베어링 교체', 'SOP-FAN-03', 'control', '설비를 계획 정지하고 바로 베어링을 교체한다.', 'role:plant-mgr',
  [['생산오더를 마감하고 계획 정지한다.', 'HM-3.1'], ['LOCAL로 전환하고 베어링을 교체한다.', 'HM-8.3'], ['재가동 후 VS1 0.9 mm/s 미만을 확인한다.', 'HM-8.3']]],
 ['skill:wo-fan-bearing', '팬 베어링 교체', 'SOP-FAN-04', 'work_order', '다음 계획 정지 때 베어링을 교체하도록 CMMS 작업지시를 발행한다.', 'role:maint-mgr',
  [['LOCAL로 전환하고 잠근다.', 'HM-3.1'], ['베어링을 교체한다.', 'HM-8.3'], ['재가동 후 VS1 0.9 mm/s 미만을 확인한다.', 'HM-8.3']]],
 ['skill:reset-after-cool', '냉각 후 리셋', 'SOP-TRIP-01', 'control', '유온 55 ℃ 미만에서 인터록을 리셋하고 재관측한다.', 'role:prod-mgr',
  [['유온이 55 ℃ 미만인지 확인한다.', 'HM-9.4'], ['원인 조치(세척 · 교체) 계획이 있는지 확인한다.', 'HM-9.4'], ['PLC를 리셋하고 재관측한다.', 'HM-9.4']]],
 ['skill:reset-after-pressure', '압력 복귀 후 리셋', 'SOP-TRIP-02', 'control', '누설 조치(예비 펌프 전환 또는 씰 교체) 뒤 토출 압력이 130 bar 이상으로 돌아온 것을 확인하고 저압 인터록을 리셋한다.', 'role:prod-mgr',
  [['저압 원인 조치(예비 펌프 전환 · 씰 교체)가 끝났는지 확인한다.', 'HM-9.4'], ['PS1이 130 bar 이상으로 회복했는지 확인한다.', 'HM-5.2'], ['PLC를 리셋하고 재관측한다.', 'HM-9.4']]],
 ['skill:reset-after-vibration', '진동 확인 후 리셋', 'SOP-TRIP-03', 'control', '팬 감속 또는 베어링 교체 뒤 진동이 1.2 mm/s 아래로 내려온 것을 확인하고 고진동 인터록을 리셋한다.', 'role:prod-mgr',
  [['진동 원인 조치(팬 감속 · 베어링 교체)가 끝났는지 확인한다.', 'HM-9.4'], ['VS1이 1.2 mm/s 미만인지 확인한다.', 'HM-8.1'], ['PLC를 리셋하고 재관측한다.', 'HM-9.4']]]]
for r in SK:
    node('Skill', id=r[0], name=r[1], sopId=r[2], kind=r[3], description=r[4], steps=[{'order': i + 1, 'text': t, 'section': s} for i, (t, s) in enumerate(r[6])])
    if r[5]: rel('APPROVED_BY', r[0], r[5])
for f, t, ss in [['fm:cooler-performance-loss', 'MITIGATED_BY', ['skill:sop-cool-11', 'skill:sop-cool-12', 'skill:sop-cool-13']],
                 ['fm:cooler-performance-loss', 'REMEDIED_BY', ['skill:sop-cool-14', 'skill:sop-cool-15', 'skill:sop-fan-11', 'skill:sop-fan-12']],
                 ['fm:volumetric-loss', 'MITIGATED_BY', ['skill:switch-standby-pump', 'skill:derate-70', 'skill:raise-pressure']],
                 ['fm:volumetric-loss', 'REMEDIED_BY', ['skill:wo-pump-seal']],
                 ['fm:bearing-degradation', 'MITIGATED_BY', ['skill:fan-slow-derate', 'skill:fan-slow']],
                 ['fm:bearing-degradation', 'REMEDIED_BY', ['skill:planned-stop', 'skill:wo-fan-bearing']],
                 ['fm:overheat-trip', 'MITIGATED_BY', ['skill:reset-after-cool']], ['fm:low-pressure-trip', 'MITIGATED_BY', ['skill:reset-after-pressure']],
                 ['fm:high-vibration-trip', 'MITIGATED_BY', ['skill:reset-after-vibration']]]:
    for s in ss: rel(t, f, s)
for s, c in [['skill:sop-cool-14', 'cause:cooler-fin-fouling'], ['skill:sop-cool-13', 'cause:cooler-fin-fouling'], ['skill:sop-cool-15', 'cause:ambient-high-temp'],
             ['skill:sop-fan-11', 'cause:fan-drive-fault'], ['skill:sop-fan-12', 'cause:fan-drive-fault'], ['skill:wo-pump-seal', 'cause:pump-seal-wear'],
             ['skill:planned-stop', 'cause:fan-bearing-wear'], ['skill:wo-fan-bearing', 'cause:fan-bearing-wear']]:
    rel('ADDRESSES', s, c)

ids = [n['props']['id'] for n in N]; assert len(ids) == len(set(ids))
for r in R: assert r['a'] in ids and r['b'] in ids, r
def dump(objs): return ',\n'.join('    ' + json.dumps(o, ensure_ascii=False) for o in objs)
(OUT / 'graph.json').write_text('{\n  "nodes": [\n' + dump(N) + '\n  ],\n  "rels": [\n' + dump(R) + '\n  ]\n}\n', encoding='utf-8')

# schema.json: 저장소 스키마에서 이 그래프가 쓰는 클래스 · 관계 · 속성만 추린다
S = json.loads((REPO / 'it/neo4j/v2/schema.json').read_text(encoding='utf-8'))
labels = {n['labels'][0] for n in N}; used = {}
for n in N: used.setdefault(n['labels'][0], set()).update(n['props'])
ADD = {'Evidence': [{'name': 'aggregate', 'type': 'string', 'description': '구간 값을 하나로 줄이는 방법. avg(평균) 또는 max-min(최댓값에서 최솟값을 뺀 폭)'}, {'name': 'section', 'type': 'string', 'description': '이 증거를 정한 매뉴얼 절'}],
       'Cause': [{'name': 'section', 'type': 'string', 'description': '이 원인을 정한 매뉴얼 절'}],
       'Skill': [{'name': 'steps', 'type': 'list', 'description': '절차의 단계. 단계마다 order(순서), text(할 일), section(근거 매뉴얼 절)'}]}
classes = []
for c in S['classes']:
    if c['name'] not in labels: continue
    props = [p for p in c['properties'] if p['name'] in used[c['name']]] + ADD.get(c['name'], [])
    assert {p['name'] for p in props} == used[c['name']], (c['name'], used[c['name']] - {p['name'] for p in props})
    classes.append({'name': c['name'], 'label_ko': c['label_ko'], 'description': c['description'], 'properties': props})
types = {r['type'] for r in R}; rels = []
for r in S['relationships']:
    if r['type'] not in types: continue
    o = {'type': r['type'], 'from': [x for x in r['from'] if x in labels], 'to': [x for x in r['to'] if x in labels], 'cardinality': r.get('cardinality'), 'description': r['description']}
    pp = {k for x in R if x['type'] == r['type'] for k in x['props']}
    if pp: o['properties'] = [p for p in r.get('properties', []) if p['name'] in pp]
    rels.append(o)
assert {r['type'] for r in rels} == types, types - {r['type'] for r in rels}
lab = {n['props']['id']: n['labels'][0] for n in N}
for r in R:
    d = next(x for x in rels if x['type'] == r['type']); assert lab[r['a']] in d['from'] and lab[r['b']] in d['to'], r
sch = {'name': 'HYD 유압 파워팩 공용 온톨로지 (설비 진단 부분)', 'version': S['version'],
       'conventions': {k: S['conventions'][k] for k in ('id', 'name', 'sign', 'label_ko')}, 'classes': classes, 'relationships': rels}
(OUT / 'schema.json').write_text(json.dumps(sch, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
from collections import Counter
print(len(N), len(R), Counter(n['labels'][0] for n in N), Counter(r['type'] for r in R))
