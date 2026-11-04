"""냉각 경보 조치 판단 묶음의 원자료 코어 — 가상 사례, 고정 시드. 같은 입력이면 몇 번을 돌려도 같은 바이트가 나온다.

통합반 03회차 실습2(조치 기준) · 실습3(판단 기능), 실전반 02회차 실습5(조치 조건표) · 03회차 실습2(조치 검토 결과)가
이 한 벌을 함께 쓰고, 랩마다 대조에 쓰는 파일만 넣는다(build_judgement_labs.py). 설계 정본은 작업 폴더의 구성안 3절이다.

- 물리: main의 hydcommon.plant_model(시뮬레이터와 예측이 함께 쓰는 상수 · 식) 그대로. 설정이 바뀌지 않는 1초 사이는 닫힌 해로 적분한다.
  냉각 효율 CE는 plantsim.thermal.step의 식, 트립은 plantsim.plc.check_interlock, 조치 후 예측은 hydcommon.forecast.predict(거부 문장 그대로).
- 30일 연속 궤적(설비마다 2026-09-28 00:00 ~ 2026-10-27 02:40 +09:00): 쿨러 핀 오염 진행과 세척 복원, 주변 온도 일주기, 생산 계획 부하,
  경보 때 운전원 조치, 현장 수동 조작, 트립. 경보는 main 패턴(발생 TS1 > 55 · CE < 70 · 상승 60초 유지, 해제 TS1 < 52 · 하강 60초)으로 뽑는다.
- 수집 결함(게이트웨이 끊김 · 품질 bad · 재전송, 카운터 기록 끊김, 예측 거부 · 전달 실패 · 기준 관측 지연, HYD-03 옛 MPa 내보내기)은
  이 생성기의 현장 값으로 넣는다. 사건(10월 27일 HYD-02)과 그 전날의 운전원 조치 · 생산 계획은 SCRIPT에 적은 사람의 결정이고,
  값(유온 · 예측 · 경보 시각)은 모두 궤적에서 나온다. 경계값을 손으로 심은 독립 사례는 없다.
- 끝에 설계 조건 검사(design_checks)를 돌린다. 하나라도 어긋나면 파일을 쓰지 않고 멈춘다 — 시드 · 계획 상수를 바꾸고 값을 손으로 고치지 않는다.

시스템 코드 위치는 lab_package.system_root()(클라우드: HYD_MAIN_ROOT=../main).
사용: from data_conditions import build; files, meta = build()   files = {자료 경로: 텍스트}, meta = 강사용(reference/ 밖으로 내보내지 않는다)
      python data_conditions.py --check   두 번 생성해 바이트가 같은지, 경보 패턴이 main과, 옛 결정표 상수가 main 04efb988^ 판과,
                                          대응표(CURRENT_ID)를 거친 규칙이 main 지금 판 규칙과 같은지 확인
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import csv
import heapq
import io
import json
import math
import random
import re
import subprocess
import sys

from lab_package import system_root
import data_documents as DD

SYS = system_root()
for _extra in [SYS/'ot/plant-sim', SYS/'common']:
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))
from hydcommon import plant_model as M, forecast as F  # noqa: E402
from plantsim import plc, thermal  # noqa: E402

SEED = 20261028
KST = timezone(timedelta(hours=9))
NOTICE = '가상 사례: 공개된 현업 문제 유형과 설비 시뮬레이터 로직으로 만든 자료이며 실제 회사 · 설비의 기록이 아니다.'


def kst(*a):
    return datetime(*a, tzinfo=KST)


T0 = kst(2026, 9, 28)
T_END = kst(2026, 10, 27, 2, 40)          # 내보낸 시각(판정 서버 · 게이트웨이 기록의 끝)
N_S = int((T_END - T0).total_seconds())
ASSETS = ['HYD-01', 'HYD-02', 'HYD-03']
CANDIDATES = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']
ACTIONS = {   # 예측 서비스에 넘기는 조치(HM-8 1.1 단계의 설정 변경 · 작업지시)
    'SOP-COOL-11': [{'kind': 'command', 'code': 'FAN_SET', 'value': 100.0}],
    'SOP-COOL-12': [{'kind': 'command', 'code': 'FAN_SET', 'value': 100.0}, {'kind': 'command', 'code': 'LOAD_SET', 'value': 80.0}],
    'SOP-COOL-13': [{'kind': 'command', 'code': 'LOAD_SET', 'value': 70.0}, {'kind': 'workorder', 'code': 'WO_CREATE'}],
    'SOP-COOL-14': [{'kind': 'workorder', 'code': 'WO_CREATE'}],
}
CODES = {'SOP-COOL-11': ['FAN_SET'], 'SOP-COOL-12': ['FAN_SET', 'LOAD_SET'], 'SOP-COOL-13': ['LOAD_SET', 'WO_CREATE'], 'SOP-COOL-14': ['WO_CREATE']}

# 경보 패턴 — main it/neo4j/v2/instances.cypher 'pattern:cooler-degradation' 행(254-256줄). --check가 main 줄과 견준다.
RAISE_TS1, RAISE_CE, RAISE_HOLD_S = 55.0, 70.0, 60
CLEAR_TS1, CLEAR_HOLD_S, SLOPE_WINDOW_S = 52.0, 60, 60

# 랩 현장 값(생성기 소유 — 시스템 DAQ 계약과 따로 둔다. 랩의 PLC 자료는 엣지 게이트웨이 기록이다)
GATEWAY_HEARTBEAT_S, GATEWAY_GRACE_S = 10, 2     # 게이트웨이 설정표: 하트비트 10초, 수신 유예 2초
COUNTER_PERIOD_MIN = 10                         # PLC 팬 카운터 주기 기록
FORECAST_VALID_S, HORIZON_S = 120, 900          # 예측 서비스 설정: 기준 관측 뒤 120초 유효, 15분 뒤 예측
WINDOW_S = 180                                  # PLC 상태 내보내기: 판정 요청 전 3분
MPA_UNTIL = kst(2026, 10, 10)                   # HYD-03 예측 결과의 옛 내보내기 형식(MPa) 사용 기간
PROD_RATE, DESIGN_LOAD = 300.0, 90.0            # 업무_값.json 시간당_생산_수량(설계 부하 90 %)

# 설비마다의 궤적 상수. 세척 날짜는 data_documents.py 작업 이력(HYD-01 CM · HYD-02 PM 10월 7일, HYD-03 80일 전 뒤 없음)과 같다.
# dust = 정해 둔 먼지 외란(시작, 끝, 쿨러 상태 감소) — 예측 서비스는 이 동안 「외란 진행 중」으로 예측을 거부한다.
SCENARIO = {
    'HYD-01': dict(health0=0.88, fouling=[(T0, 0.024), (kst(2026, 10, 7, 13), 0.027)], amb=0.0, leak0=0.0, leak_per_day=0.0,
                   cleanings=[(kst(2026, 10, 7, 10, 0), 3.0)], dust=[], heartbeat_phase=3),
    'HYD-02': dict(health0=0.72, fouling=[(T0, 0.011), (kst(2026, 10, 8, 2, 0), 0.0306)], amb=0.3, leak0=0.0, leak_per_day=0.0,
                   cleanings=[(kst(2026, 10, 7, 23, 0), 3.0)], dust=[], heartbeat_phase=7,
                   counter_gaps=[(kst(2026, 10, 27, 1, 58), kst(2026, 10, 27, 2, 0, 40))]),   # 사건 직전 카운터 주기 기록 한 줄이 수집에서 빠짐(게이트웨이 끊김)
    'HYD-03': dict(health0=0.77, fouling=[(T0, 0.0074)], amb=0.6, leak0=0.11277, leak_per_day=0.0011,
                   cleanings=[], dust=[], heartbeat_phase=1),
}
# 사람의 결정(운전원 조치 · 생산 계획 · 작업 이력에 남은 일). 값은 궤적이 낸다.
#   hold = 팬을 되돌리지 않은 기간, force = 그 기간 경보에서 운전원이 고른 조치, events = 운전원 설정 변경, plan = 생산 계획 부하
SCRIPT = {
    'HYD-01': dict(
        hold=[(kst(2026, 10, 5), kst(2026, 10, 7, 6, 5))],               # 「팬 최대 운전 지속 - 누적 26 h, 야간 세척 대기」(작업 이력 10월 6일)
        force=[(kst(2026, 10, 5), kst(2026, 10, 7, 9, 59), 'SOP-COOL-11')],
        events=[(kst(2026, 10, 7, 6, 5), 'fan', 60.0)],                  # 주간조가 팬을 되돌림 → 경보 → 핀 세척(CM)
        plan=[]),
    'HYD-02': dict(
        hold=[(kst(2026, 10, 26, 1, 44), T_END)],                         # 전날 경보 뒤 팬 100 % 유지(작업 이력 10월 26일)
        force=[(kst(2026, 10, 26, 1, 44), kst(2026, 10, 26, 3, 0), 'SOP-COOL-11')],
        events=[(kst(2026, 10, 26, 1, 44, 10), 'fan', 60.0)],             # 운전원이 팬을 되돌림(연속 24시간 이내 규칙)
        plan=[(kst(2026, 10, 25, 22, 0), 80.0), (kst(2026, 10, 26, 1, 50, 30), 90.0),     # 야간조 80 %, 야간 오더 90 %
              (kst(2026, 10, 26, 6, 0), 80.0), (kst(2026, 10, 27, 1, 47, 0), 90.0)]),    # 주간 계획 80 %, 다음 날 야간 오더 90 %
    'HYD-03': dict(hold=[], force=[], events=[], plan=[]),
}
INCIDENT = dict(asset='HYD-02', day=kst(2026, 10, 27), judge_delay_s=88, drop=['SOP-COOL-12'])
INCIDENT_ORDER = dict(asset='HYD-02', release=kst(2026, 10, 26, 22, 0), qty=5550, due=kst(2026, 10, 27, 22, 15))
QUIET = (kst(2026, 10, 25, 18), T_END)         # 사건 앞뒤: 무작위 수집 결함 · 먼지 외란을 넣지 않는 구간(HYD-02)
OPS = dict(field=0.18, busy=0.18, busy_night=0.3, busy_s=(900, 4200))   # 현장 수동 조작 확률, 다른 일에 매인 운전원 확률(주간 · 야간 22~06시) · 지연(초)
# 수집 결함 · 외란의 빈도(하루 평균 횟수, 지속 초). 사례 종류가 모자라면 이 값 · 시드를 바꾸고 사례를 손으로 심지 않는다.
FAULTS = dict(outage=(18.0, (14, 240)), bad=(30.0, (15, 90)), counter_gap=(1.0, (1200, 3600)), daq_delay=(5.0, (200, 900)),
              dust=(0.25, (3600, 9000)), dust_drop=(0.02, 0.05), forecast_drop=0.04, order_fail=0.035)
PORTAL_ALARM = ('HYD-01', kst(2026, 10, 10, 11, 13, 8))   # 포털 대표 경보 — 같은 설비 · 시각에 경보가 나면 멈춘다(K-121)

# 판단 시스템 결정표(2025년 도입 판, HM-8 1.0판으로 작성) — main 04efb988 앞 판의 행을 그대로 고정한다(main이 바뀌어도 랩의 옛 판은 그대로).
# 내보내기 파일에 쓸 때만 규칙 ID를 대응표(CURRENT_ID)로 바꾸고 제작 흔적 한 곳(rule:cand-trip 설명의 「(A098: …)」 괄호)을 뺀다. --check가 그 판과 견준다.
OLD_RULES = [   # [id, 표, 순서, 조건식, 결과, 감점, 설명, 대상, 감점 지표, 출처, 검사[[입력, 연산자, 값, 단위]]] — 04efb988^:it/neo4j/v2/instances.cypher 줄 436, 438, 440, 456, 458, 460, 462, 464, 466, 468, 470, 472, 474, 476, 478, 480, 482, 484
    ['rule:ts1-hard', 'dt:compliance', 2, 'forecast_ts1 >= 65', 'EXCLUDE', None, '예측 유온이 인터록 한계 이상이면 제외 (모든 제어 후보에 예측값으로 적용)', [], None, ['ks:sr-04'], [['in:forecast-ts1', '>=', 65, '℃']]],
    ['rule:avl', 'dt:compliance', 7, 'supplier_avl == false', 'EXCLUDE', None, '핵심 부품은 승인 공급사에서만 구매', ['skill:wo-pump-seal'], None, ['ks:pr-07'], [['in:supplier-avl', '==', False, None]]],
    ['rule:rank-value', 'dt:rank-actions', 1, 'true', 'RANK', None, '점수 = BSC 득실(스킬 → 처음 닿는 성과 지표, 강도 high 1 · medium 0.6 · low 0.3, 조건부는 절반) + 예측 유온 여유 (55 − 예측)/3 (±2 한도) − 경고 0.5 − 감점/20 + 선례 비율 × 1.5 + 납기 긴급도((24 − 남은 h)/24 × 지연 보상/100, 0~1) × 생산 영향(유지 +1 · 감산 +0.4 · 정지 −1) × 1.5 − 품질 위험(고온 구간 출하 대기 로트가 있고 예측 유온 ≥ 55 ℃ 면 클레임/1000, ≤ 1) × 1.5. 제외된 카드는 뒤로, 동점이면 승인 직급이 낮은 쪽', [], None, ['ks:strategy-map'], []],
    ['rule:dx-cooler', 'dt:diagnose-cause', 1, "pattern == 'COOLER_DEGRADATION' and ce < 70", 'SELECT', None, '냉각 효율이 낮으면 쿨러 핀 오염이 1순위 (근거 evd:ce-low)', ['cause:cooler-fin-fouling'], None, ['HM-7.3'], [['in:pattern', '==', 'COOLER_DEGRADATION', None], ['in:ce', '<', 70, '%']]],
    ['rule:dx-pump', 'dt:diagnose-cause', 2, "pattern == 'PUMP_LEAKAGE' and ps1 < 165", 'SELECT', None, '토출 압력이 165 bar 미만이면 씰 마모 (근거 evd:ps1-low)', ['cause:pump-seal-wear'], None, ['HM-5.2'], [['in:pattern', '==', 'PUMP_LEAKAGE', None], ['in:ps1', '<', 165, 'bar']]],
    ['rule:dx-fan', 'dt:diagnose-cause', 3, "pattern == 'FAN_VIBRATION' and ts1 < 52", 'SELECT', None, '유온이 정상인데 진동만 오르면 베어링 (근거 evd:vs1-trend)', ['cause:fan-bearing-wear'], None, ['HM-8.1'], [['in:pattern', '==', 'FAN_VIBRATION', None], ['in:ts1', '<', 52, '℃']]],
    ['rule:cand-cooler', 'dt:action-candidates', 1, "failure_mode == 'fm:cooling-loss'", 'SELECT', None, '냉각 성능 상실 → 즉시 완화 SOP (팬 최대 · 팬 최대+부하 저감 · 부하 저감+야간 세척) + 근본 조치 작업지시 (핀 세척 · 캐비닛 환기)', ['skill:fan-max', 'skill:fan-max-derate', 'skill:derate-night-clean', 'skill:wo-cooler-clean', 'skill:wo-ventilation'], None, ['HM-7.3', 'HM-9.1'], [['in:failure-mode', '==', 'fm:cooling-loss', None]]],
    ['rule:cand-pump', 'dt:action-candidates', 2, "failure_mode == 'fm:volumetric-loss'", 'SELECT', None, '펌프 체적 효율 저하 → 즉시 완화 SOP (예비 펌프 전환 · 부하 저감 · 압력 상향) + 근본 조치 작업지시 (축 씰 교체 · 씰 키트 구매요청)', ['skill:switch-standby-pump', 'skill:derate-70', 'skill:raise-pressure', 'skill:wo-pump-seal'], None, ['HM-5.2'], [['in:failure-mode', '==', 'fm:volumetric-loss', None]]],
    ['rule:cand-fan', 'dt:action-candidates', 3, "failure_mode == 'fm:bearing-degradation'", 'SELECT', None, '팬 베어링 열화 → 팬 감속+부하 저감 · 팬 감속 · 계획 정지 + 근본 조치 작업지시 (베어링 교체)', ['skill:fan-slow-derate', 'skill:fan-slow', 'skill:planned-stop', 'skill:wo-fan-bearing'], None, ['HM-8.1', 'HM-8.3'], [['in:failure-mode', '==', 'fm:bearing-degradation', None]]],
    ['rule:cand-trip', 'dt:action-candidates', 4, "plc_state == 'TRIP' and pattern == 'OVERHEAT_TRIP'", 'SELECT', None, '과열 트립이면 제어 명령 대신 냉각 후 리셋 (A098: 저압 · 고진동 트립은 knowledge_a098.cypher의 별도 규칙)', ['skill:reset-after-cool'], None, ['HM-9.4'], [['in:plc-state', '==', 'TRIP', None], ['in:pattern', '==', 'OVERHEAT_TRIP', None]]],
    ['rule:cand-trip-fm', 'dt:action-candidates', 5, "failure_mode == 'fm:overheat-trip'", 'SELECT', None, '과열 정지로 판정되면 냉각 후 리셋 (트립 규칙과 OR — 행을 나눔)', ['skill:reset-after-cool'], None, ['HM-9.4'], [['in:failure-mode', '==', 'fm:overheat-trip', None]]],
    ['rule:no-pressure-raise', 'dt:compliance', 1, "skill_code == 'PRESSURE_SET' and failure_mode == 'fm:volumetric-loss'", 'EXCLUDE', None, '누설 의심 시 압력 설정 상향 금지', ['skill:raise-pressure'], None, ['HM-5.4'], [['in:skill-code', '==', 'PRESSURE_SET', None], ['in:failure-mode', '==', 'fm:volumetric-loss', None]]],
    ['rule:auto-mode', 'dt:compliance', 3, "skill_kind == 'control' and plc_mode != 'REMOTE_AUTO'", 'EXCLUDE', None, '원격 제어는 REMOTE_AUTO에서만', ['skill:fan-max', 'skill:fan-max-derate', 'skill:derate-night-clean', 'skill:switch-standby-pump', 'skill:derate-70', 'skill:fan-slow-derate', 'skill:fan-slow'], None, ['HM-3.2'], [['in:skill-kind', '==', 'control', None], ['in:plc-mode', '!=', 'REMOTE_AUTO', None]]],
    ['rule:standby', 'dt:compliance', 4, 'standby_ready == false', 'EXCLUDE', None, '예비 펌프가 정비 중이면 전환 불가', ['skill:switch-standby-pump'], None, ['HM-5.2'], [['in:standby-ready', '==', False, None]]],
    ['rule:ts1-warn', 'dt:compliance', 5, 'forecast_ts1 >= 55', 'WARN', None, '예측 유온이 55 ℃ 이상이면 경보 해제 실패 가능', ['skill:fan-max', 'skill:fan-slow'], None, ['HM-7.5'], [['in:forecast-ts1', '>=', 55, '℃']]],
    ['rule:ps1-warn', 'dt:compliance', 9, 'forecast_ps1 < 165', 'WARN', None, '예측 토출 압력이 165 bar 미만이면 저압 경보가 이어질 수 있음', [], None, ['HM-5.2'], [['in:forecast-ps1', '<', 165, 'bar']]],
    ['rule:fan-24h', 'dt:compliance', 6, 'fan100_hours > 24', 'PENALTY', 20, '팬 100 % 연속 24시간 초과 시 수명 감점', ['skill:fan-max', 'skill:fan-max-derate'], 'msr:mtbf', ['HM-7.3'], [['in:fan100-hours', '>', 24, 'h']]],
    ['rule:trip-reset-only', 'dt:compliance', 8, "plc_state == 'TRIP' and skill_code != 'RESET'", 'EXCLUDE', None, '트립 중에는 PLC가 리셋 외 제어 명령을 거부한다 (냉각 후 리셋만)', [], None, ['HM-9.4'], [['in:plc-state', '==', 'TRIP', None], ['in:skill-code', '!=', 'RESET', None]]],
]
# 옛 규칙 ID → 지금 시스템 ID(대응표). 학생이 이론 영상 · 포털에서 보는 이름으로 내보낸다 — 행의 다른 칸(조건식 · 대상 · 감점 지표 · 출처)은 옛 판 값 그대로.
# 바꾸는 것은 main 지금 판 규칙(course_extractions.json 문서 적재 규칙 · instances.cypher 시드 규칙)과 결정표 · 결과 · 감점 · 검사 · 고르는 대상이 같은 행뿐이다.
# 나머지 열둘은 옛 이름 그대로 — rule:ts1-hard · rule:rank-value는 지금도 같은 ID, 그 밖 열은 지금 시스템에 같은 뜻의 규칙이 없다. --check가 main 지금 판과 견준다.
CURRENT_ID = {
    'rule:avl': 'rule:pr07-approved-supplier-only',               # PR-7.3. 옛 rule:avl은 main이 지웠다(instances.cypher 「지운 시드 정리」). 대상: 옛 skill:wo-pump-seal, 지금 SOP-PUR-11~13
    'rule:dx-cooler': 'rule:hm-8-4-fouling-diagnosis',            # HM-8.4
    'rule:dx-pump': 'rule:pm-pump-leakage-seal-wear-first',       # PM-2.10. 고르는 원인 ID는 OUTPUT_ALIAS
    'rule:auto-mode': 'rule:hm-8-8-remote-auto-only',             # HM-8.8. 옛 판의 skill_kind 검사(DROPPED_TESTS) 대신 대상(SOP-COOL-11~13)으로 원격 조치를 정한다
    'rule:ts1-warn': 'rule:cooler-forecast-temperature-warning',  # HM-8.6. 대상: 옛 팬 최대 · 팬 40 %, 지금 SOP-COOL-11~13
    'rule:fan-24h': 'rule:hm-8-8-fan-life-penalty',               # HM-8.8. 감점 지표: 옛 msr:mtbf, 지금 msr:maint-cost(원문에 지표가 없어 검토용으로 이음)
}
DROPPED_TESTS = {'rule:auto-mode': [['in:skill-kind', '==', 'control', None]]}   # 지금 규칙에는 없는 옛 검사
OUTPUT_ALIAS = {'cause:pump-seal-wear': 'cause:pump-shaft-seal-wear'}           # 옛 원인 ID → 지금 ID(이름이 같다 — --check가 04efb988^ 판과 지금 names.json으로 확인)
OLD_SKILLS = [  # [id, 이름, 절차 번호, 종류, 설명, 승인, 실행 시스템, [[동작, 값]], 단계[[문장, 절]]] — 같은 파일 줄 281, 283, 285, 287, 289, 291, 293, 295, 297, 299, 301, 303, 305, 307
    ['skill:fan-max', '팬 최대', 'SOP-COOL-01', 'control', '팬만 100 %로 올린다. 생산은 그대로 유지한다.', 'role:operator', 'sys:scada', [['action:set-fan', 100]], [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-3.2'], ['팬 속도를 100 %로 올린다 (연속 24시간 이내).', 'HM-7.3'], ['15분 재관측: TS1 55 ℃ 미만이고 경보 해제면 완화 성공.', 'HM-7.5']]],
    ['skill:fan-max-derate', '팬 최대 + 부하 80 %', 'SOP-COOL-02', 'control', '팬 100 %와 부하 80 %로 유온을 확실히 내린다.', 'role:prod-mgr', 'sys:scada', [['action:set-fan', 100], ['action:set-load', 80]], [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-3.2'], ['팬 속도를 100 %로 올린다.', 'HM-7.3'], ['펌프 부하를 80 %로 낮춘다 (최소 60 %).', 'HM-9.1'], ['15분 재관측: TS1 55 ℃ 미만이고 경보 해제면 완화 성공.', 'HM-7.5']]],
    ['skill:derate-night-clean', '부하 70 % + 야간 세척', 'SOP-COOL-03', 'control', '팬은 그대로 두고 부하를 70 %로 낮춘 뒤 야간 정비창에 쿨러를 세척한다.', 'role:prod-mgr', 'sys:scada', [['action:set-load', 70], ['action:work-order', 'SOP-COOL-04']], [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-3.2'], ['펌프 부하를 70 %로 낮춘다.', 'HM-9.1'], ['15분 재관측: TS1 55 ℃ 미만이면 완화 성공.', 'HM-7.5'], ['야간 정비창에 쿨러 핀 세척 작업지시(SOP-COOL-04)를 건다.', 'HM-7.6']]],
    ['skill:wo-cooler-clean', '쿨러 핀 세척', 'SOP-COOL-04', 'work_order', '설비를 세우고 쿨러 핀을 세척한다. CMMS 작업지시로 발행한다.', 'role:maint-mgr', 'sys:cmms', [['action:work-order', 'SOP-COOL-04']], [['설비를 정지하고 LOCAL로 전환한다.', 'HM-3.1'], ['압축공기로 핀을 세척한다.', 'HM-7.6'], ['재가동 후 CE 80 % 이상 복귀를 확인한다.', 'HM-7.5']]],
    ['skill:wo-ventilation', '캐비닛 환기 개선', 'SOP-COOL-05', 'work_order', '외기 고온으로 냉각 여유가 없을 때 캐비닛 환기를 보강한다. CMMS 작업지시로 발행한다.', 'role:maint-mgr', 'sys:cmms', [['action:work-order', 'SOP-COOL-05']], [['캐비닛 온도(TS4)와 외기 온도를 기록한다.', 'HM-7.7'], ['환기 필터를 청소하고 배기 팬을 점검한다.', 'HM-7.7'], ['캐비닛 온도가 35 ℃ 아래로 내려왔는지 확인한다.', 'HM-7.7']]],
    ['skill:switch-standby-pump', '예비 펌프 전환', 'SOP-PMP-01', 'control', '예비 펌프 B로 전환해 압력을 즉시 회복한다.', 'role:prod-mgr', 'sys:scada', [['action:select-pump', 'B']], [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-3.2'], ['예비 펌프 B로 무부하 전환한다.', 'HM-5.2'], ['30초 안에 PS1이 175 bar 이상으로 회복됐는지 확인한다.', 'HM-5.2']]],
    ['skill:derate-70', '부하 70 %', 'SOP-PMP-02', 'control', '부하를 70 %로 낮춰 압력 부족과 누설 진행을 늦춘다.', 'role:operator', 'sys:scada', [['action:set-load', 70]], [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', 'HM-3.2'], ['펌프 부하를 70 %로 낮춘다.', 'HM-9.1'], ['PS1 하락이 멈췄는지 10분간 확인한다.', 'HM-5.2']]],
    ['skill:raise-pressure', '압력 설정 상향 (구 절차)', 'SOP-PMP-03', 'control', '압력 설정을 10 bar 올려 부족분을 메운다. 개정 매뉴얼에서 누설 시 금지된 옛 절차다.', 'role:operator', 'sys:scada', [['action:raise-pressure', 10]], [['압력 설정을 10 bar 올린다. 누설 의심 시에는 금지 (개정 HM-5.4).', 'HM-5.4'], ['PS1이 175 bar 이상인지 확인한다.', 'HM-5.2']]],
    ['skill:wo-pump-seal', '펌프 축 씰 교체', 'SOP-PMP-04', 'work_order', '씰 키트를 구매요청하고 교체 작업지시를 발행한다.', 'role:maint-mgr', 'sys:cmms', [['action:purchase-request', 'sup:b'], ['action:work-order', 'SOP-PMP-04']], [['주 펌프를 LOCAL로 전환하고 잠근다.', 'HM-3.1'], ['씰 키트를 교체한다.', 'HM-5.6'], ['누설 시험 후 주 펌프로 복귀한다.', 'HM-5.6']]],
    ['skill:fan-slow-derate', '팬 40 % + 부하 80 %', 'SOP-FAN-01', 'control', '팬을 낮춰 진동을 줄이고 부하도 낮춰 유온 상승을 막는다.', 'role:prod-mgr', 'sys:scada', [['action:set-fan', 40], ['action:set-load', 80]], [['팬 속도를 40 %로 낮춘다.', 'HM-8.1'], ['유온이 55 ℃를 넘지 않도록 부하를 80 %로 낮춘다.', 'HM-9.1'], ['VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.', 'HM-8.1']]],
    ['skill:fan-slow', '팬 40 %', 'SOP-FAN-02', 'control', '팬만 40 %로 낮춘다. 생산은 그대로 유지한다.', 'role:operator', 'sys:scada', [['action:set-fan', 40]], [['팬 속도를 40 %로 낮춘다.', 'HM-8.1'], ['유온을 15분간 감시한다. 55 ℃를 넘으면 부하를 낮춘다.', 'HM-7.5'], ['VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.', 'HM-8.1']]],
    ['skill:planned-stop', '계획 정지 + 베어링 교체', 'SOP-FAN-03', 'control', '설비를 계획 정지하고 바로 베어링을 교체한다.', 'role:plant-mgr', 'sys:scada', [['action:controlled-stop', 1], ['action:work-order', 'SOP-FAN-04']], [['생산오더를 마감하고 계획 정지한다.', 'HM-3.1'], ['LOCAL로 전환하고 베어링을 교체한다.', 'HM-8.3'], ['재가동 후 VS1 0.9 mm/s 미만을 확인한다.', 'HM-8.3']]],
    ['skill:wo-fan-bearing', '팬 베어링 교체', 'SOP-FAN-04', 'work_order', '다음 계획 정지 때 베어링을 교체하도록 CMMS 작업지시를 발행한다.', 'role:maint-mgr', 'sys:cmms', [['action:work-order', 'SOP-FAN-04']], [['LOCAL로 전환하고 잠근다.', 'HM-3.1'], ['베어링을 교체한다.', 'HM-8.3'], ['재가동 후 VS1 0.9 mm/s 미만을 확인한다.', 'HM-8.3']]],
    ['skill:reset-after-cool', '냉각 후 리셋', 'SOP-TRIP-01', 'control', '유온 55 ℃ 미만에서 인터록을 리셋하고 재관측한다.', 'role:prod-mgr', 'sys:scada', [['action:reset', 1]], [['유온이 55 ℃ 미만인지 확인한다.', 'HM-9.4'], ['원인 조치(세척 · 교체) 계획이 있는지 확인한다.', 'HM-9.4'], ['PLC를 리셋하고 재관측한다.', 'HM-9.4']]],
]


def sec(dt):
    return int((dt - T0).total_seconds())


def at(s):
    return T0 + timedelta(seconds=s)


def iso_kst(s):
    return at(s).astimezone(KST).isoformat(timespec='seconds')


def iso_utc(s):
    return at(s).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def table(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def r1(v):
    return f'{round(v + 0.0, 1):.1f}'


def money(v):
    """금액(만원)을 소수 둘째 자리로 사사오입(ROUND_HALF_UP — 입출력_계약 「결과」의 반올림 규칙). 부동소수 원값의 이진 오차
    (11.25 + 1.575가 12.8249…로 저장됨)는 소수 아홉째 자리에서 먼저 걷어 낸다. 판정 엔진(judge_actions.r2)과 따로 쓴 같은 규칙이다."""
    return float(Decimal(f'{v:.9f}').quantize(Decimal('0.01'), ROUND_HALF_UP))


def ce_of(health, fan):
    """냉각 효율 — plantsim.thermal.step의 식(잡음 없음). 모듈을 읽을 때 thermal.step과 같은지 한 번 견준다."""
    return 100.0 * health * (0.6 + 0.4 * fan / 100.0)


def _same_ce():
    u = thermal.UnitState()
    u.cooler_health, u.fan_pct = 0.437, 83.0
    thermal.step(u, 1.0, True)
    if abs(u.ce - ce_of(0.437, 83.0)) > 1e-9:
        raise RuntimeError('냉각 효율 식이 plantsim.thermal.step과 다릅니다 — ce_of를 main에 맞춥니다.')


_same_ce()


# ───────────── 궤적 입력: 주변 온도 · 쿨러 상태 · 누설 · 수집 결함 창 ─────────────

def windows(rnd, per_day, dur, quiet=None):
    """[시작 초, 끝 초) 목록. per_day = 하루 평균 횟수, dur = (최소, 최대) 초."""
    out, s = [], 0
    while True:
        s += int(rnd.expovariate(per_day / 86400.0))
        if s >= N_S:
            return out
        e = s + rnd.randint(*dur)
        if quiet and not (e <= sec(quiet[0]) or s >= sec(quiet[1])):
            continue
        out.append((s, e))


def inside(ws, s):
    return any(a <= s < b for a, b in ws)


def inputs(asset):
    """분 단위 주변 온도 · 쿨러 상태 · 외란 진행 표시 · 누설과, 이 설비의 수집 결함 창."""
    sc = SCENARIO[asset]
    rnd = random.Random(f'{SEED}-{asset}-inputs')
    days = N_S // 86400 + 2
    base = [23.4 - 0.05 * d + rnd.uniform(-0.8, 0.8) + sc['amb'] for d in range(days)]
    mult = [rnd.uniform(0.7, 1.3) for _ in range(days)]
    quiet = QUIET if asset == INCIDENT['asset'] else None
    dust = [(a, b, rnd.uniform(*FAULTS['dust_drop'])) for a, b in windows(rnd, *FAULTS['dust'], quiet)]
    dust += [(sec(a), sec(b), drop) for a, b, drop in sc['dust']]
    n_m = N_S // 60 + 2
    amb, health, ramp, leak = [0.0] * n_m, [0.0] * n_m, [False] * n_m, [0.0] * n_m
    clean_end = {sec(start + timedelta(hours=h)) // 60 for start, h in sc['cleanings']}
    rates = [(sec(t) // 60, r) for t, r in sc['fouling']]
    h = sc['health0']
    for m in range(n_m):
        s = m * 60
        d = s // 86400
        hour = (s % 86400) / 3600.0
        amb[m] = base[d] + 2.0 * math.sin(2 * math.pi * (hour - 9.0) / 24.0)
        if m in clean_end:
            h = 1.0
        rate = [r for start, r in rates if start <= m][-1]
        h -= rate * mult[d] / 1440.0
        for a, b, drop in dust:
            if a <= s < b:
                h -= drop / ((b - a) / 60.0)
                ramp[m] = True
        h = max(h, 0.2)
        health[m] = h
        leak[m] = sc['leak0'] + sc['leak_per_day'] * s / 86400.0
    # outage = 게이트웨이 수신 끊김, bad = 품질 bad 수신, counter_gap = 카운터 기록 수집 끊김, daq_delay = 예측 서비스가 받은 관측이 늦음
    faults = {k: windows(rnd, *FAULTS[k], quiet) for k in ('outage', 'bad', 'counter_gap', 'daq_delay')}
    faults['counter_gap'] += [(sec(a), sec(b)) for a, b in sc.get('counter_gaps', [])]   # 정해 둔 끊김(난수 흐름 뒤에 더한다)
    return amb, health, ramp, leak, dust, faults


# ───────────── 30일 궤적 ─────────────

class Unit:
    def __init__(self, asset):
        self.asset = asset
        self.rnd = random.Random(f'{SEED}-{asset}-ops')
        self.amb, self.health, self.ramp, self.leak, self.dust, self.faults = inputs(asset)
        sc, sp = SCENARIO[asset], SCRIPT[asset]
        self.script = sp
        self.fan, self.load, self.plan_load = 60.0, DESIGN_LOAD, DESIGN_LOAD
        self.mode, self.state, self.trip = 'REMOTE_AUTO', 'RUN', ''
        self.ts = M.steady_ts1(self.load, 0.0, self.fan, self.health[0], True, self.amb[0])
        self.log = [0.0] * N_S
        self.changes = []          # (초, 모드, 상태, 트립, 팬, 부하)
        self.runs = []             # 팬 100 % 연속 운전 [시작 초, 끝 초 또는 None]
        self.alarms = []           # 경보 한 건: dict
        self.prod_m = [0.0] * (N_S // 60 + 2)
        self.hot_m = [0.0] * (N_S // 60 + 2)
        self.active = None         # 진행 중 경보
        self.field = False         # 현장 수동 조작 중
        self.queue, self.order = [], 0
        for t, kind, value in sp['events']:
            self.push(sec(t), kind, value)
        for t, value in sp['plan']:
            self.push(sec(t), 'plan', value)
        for start, hours in sc['cleanings']:
            self.push(sec(start), 'clean_start', None)
            self.push(sec(start + timedelta(hours=hours)), 'clean_end', None)
        rnd = random.Random(f'{SEED}-{asset}-plan')
        for d in range(N_S // 86400 + 1):
            for hour in (6, 14, 22):
                self.push(d * 86400 + hour * 3600, 'shift', hour)
            day = T0 + timedelta(days=d)
            if rnd.random() < 0.18 and not any(abs((t - day).total_seconds()) < 2 * 86400 for t, _ in sp['plan']):
                self.push(d * 86400 + 6 * 3600 + 30, 'plan', 80.0)
                self.push(d * 86400 + 22 * 3600 + 30, 'plan', DESIGN_LOAD)
        self.note_change(0)

    def push(self, s, kind, value):
        self.order += 1
        heapq.heappush(self.queue, (s, self.order, kind, value))

    def note_change(self, s):
        self.changes.append((s, self.mode, self.state, self.trip, self.fan, self.load))
        on = self.fan >= 100.0 and self.state == 'RUN'
        if on and (not self.runs or self.runs[-1][1] is not None):
            self.runs.append([s, None])
        elif not on and self.runs and self.runs[-1][1] is None:
            self.runs[-1][1] = s
        self.dirty = True

    def in_window(self, key, s):
        return any(sec(a) <= s < sec(b) for a, b, *_ in self.script[key])

    def forced(self, s):
        return next((sop for a, b, sop in self.script['force'] if sec(a) <= s < sec(b)), None)

    def steady(self, fan, load, s):
        m = s // 60
        return M.steady_ts1(load, M.effective_leak(self.leak[m], 'A'), fan, self.health[m], True, self.amb[m])

    def run_minutes(self, s):
        if self.runs and self.runs[-1][1] is None:
            return (s - self.runs[-1][0]) / 60.0
        return 0.0

    # ── 사건 처리 ──
    def handle(self, s, kind, value):
        rnd = self.rnd
        if kind == 'fan':
            if self.state == 'RUN':
                self.fan = value
                self.note_change(s)
        elif kind == 'load':
            if self.state == 'RUN':
                self.load = value
                self.note_change(s)
        elif kind == 'plan':
            self.plan_load = value
            if self.state == 'RUN' and self.mode == 'REMOTE_AUTO' and self.load != value:
                self.load = value
                self.note_change(s)
        elif kind == 'shift':
            self.shift(s)
        elif kind == 'clean_start':
            self.state, self.mode, self.trip = 'STOP', 'LOCAL', ''
            self.note_change(s)
        elif kind == 'clean_end':
            self.state, self.mode, self.fan, self.load = 'RUN', 'REMOTE_AUTO', 60.0, self.plan_load
            self.field = False
            self.note_change(s)
        elif kind == 'field':                 # 현장 패널 수동 조작: 모드가 REMOTE_MANUAL로 바뀌고 팬을 올린다(plantsim.plc 규칙)
            if self.state == 'RUN' and self.mode == 'REMOTE_AUTO':
                self.mode, self.fan, self.field = 'REMOTE_MANUAL', 100.0, True
                self.note_change(s)
        elif kind == 'auto':
            if self.mode == 'REMOTE_MANUAL' and self.state == 'RUN':
                self.mode, self.field = 'REMOTE_AUTO', False
                self.note_change(s)
        elif kind == 'judge':
            self.judge(s, value)
        elif kind == 'act':
            sop, alarm = value
            alarm['action'] = sop
            if self.state != 'RUN' or self.mode != 'REMOTE_AUTO':
                alarm['action_applied'] = None
                return
            alarm['action_applied'] = s
            if sop in ('SOP-COOL-11', 'SOP-COOL-12'):
                self.fan = 100.0
            if sop == 'SOP-COOL-12':
                self.load = 80.0
            if sop == 'SOP-COOL-13':
                self.load = 70.0
            self.note_change(s)
        elif kind == 'reset_check':
            if self.state == 'TRIP':
                if self.ts < M.RESET_TS1 - 1.0:
                    self.push(s + rnd.randint(60, 420), 'reset', None)
                else:
                    self.push(s + 60, 'reset_check', None)
        elif kind == 'reset':
            if self.state == 'TRIP' and self.ts < M.RESET_TS1:
                self.state, self.trip, self.fan, self.load = 'RUN', '', 100.0, 80.0
                self.note_change(s)

    def shift(self, s):
        if self.state != 'RUN' or self.mode != 'REMOTE_AUTO' or self.active:
            return
        if self.fan >= 100.0 and not self.in_window('hold', s) and self.run_minutes(s) >= 240:
            m = s // 60
            if self.steady(60.0, self.load, s) + (1.0 if self.amb[m] < self.amb[min(m + 120, len(self.amb) - 1)] else 0.0) < 51.5:
                self.fan = 60.0
                self.note_change(s)
        if self.load < self.plan_load and self.steady(self.fan, self.plan_load, s) < 51.5:
            self.load = self.plan_load
            self.note_change(s)

    def judge(self, s, alarm):
        alarm['judge'] = s
        rnd = self.rnd
        if alarm['incident']:
            return                      # 사건: 판정 요청 시각이 이 자료의 끝이다
        if self.state == 'TRIP':
            alarm['action'] = None
            return
        if self.mode != 'REMOTE_AUTO':
            alarm['action'] = None
            return
        sop = self.forced(s)
        if sop is None:
            if self.fan < 100.0:
                sop = 'SOP-COOL-12' if (self.ts >= 57.5 and rnd.random() < 0.5) or rnd.random() < 0.12 else 'SOP-COOL-11'
            elif self.load > 80.0:
                sop = 'SOP-COOL-12'
            elif self.load > 70.0:
                sop = 'SOP-COOL-13'
            else:
                alarm['action'] = None
                return
        self.push(s + rnd.randint(40, 150), 'act', (sop, alarm))

    def raise_alarm(self, s):
        rnd = self.rnd
        incident = self.asset == INCIDENT['asset'] and at(s) >= INCIDENT['day']
        alarm = dict(asset=self.asset, raise_s=s, ts=self.ts, ce=ce_of(self.health[s // 60], self.fan), fan=self.fan,
                     load=self.load, mode=self.mode, clear_s=None, judge=None, action=None, action_applied=None, incident=incident)
        self.alarms.append(alarm)
        self.active = alarm
        story = self.in_window('force', s)
        if incident:
            delay = INCIDENT['judge_delay_s']
        elif story:
            delay = rnd.randint(45, 260)
        elif rnd.random() < (OPS['busy_night'] if at(s).hour >= 22 or at(s).hour < 6 else OPS['busy']):
            delay = rnd.randint(*OPS['busy_s'])     # 다른 일에 매인 운전원
        else:
            delay = rnd.randint(45, 260)
        if (not incident and not story and self.mode == 'REMOTE_AUTO' and self.fan < 100.0
                and rnd.random() < OPS['field']):
            self.push(s + rnd.randint(30, min(delay - 5, 170)), 'field', None)
        self.push(s + delay, 'judge', alarm)

    def clear_alarm(self, s):
        self.active['clear_s'] = s
        self.active['clear_ts'] = self.ts
        self.active['clear_ce'] = ce_of(self.health[s // 60], self.fan)
        self.active = None
        if self.field:
            self.push(s + self.rnd.randint(1200, 5400), 'auto', None)

    def simulate(self):
        q = self.queue
        hold_up = hold_down = 0
        coef = S = k = ce = rate = 0.0
        self.dirty = True
        log = self.log
        probe_plc, probe_unit = plc.PlcState(), thermal.UnitState()
        for s in range(N_S):
            while q and q[0][0] <= s:
                _, _, kind, value = heapq.heappop(q)
                self.handle(s, kind, value)
            m = s // 60
            if self.dirty or s % 60 == 0:
                running = self.state == 'RUN'
                leak = M.effective_leak(self.leak[m], 'A')
                coef = M.cooling_coef(self.fan, self.health[m], running)
                S = self.amb[m] + M.heat(self.load if running else 0.0, leak) / coef
                k = math.exp(-coef / M.C)
                ce = ce_of(self.health[m], self.fan)
                rate = PROD_RATE / 3600.0 * self.load / DESIGN_LOAD if running else 0.0
                self.dirty = False
                # 연속 24시간 규칙(HM-8 SOP-COOL-11 단계 2): 경보가 없고 유온이 낮으면 팬을 되돌린다
                if (s % 60 == 0 and running and self.mode == 'REMOTE_AUTO' and self.fan >= 100.0 and not self.active
                        and not self.in_window('hold', s) and self.run_minutes(s) >= 1428 and self.ts < 50.0):
                    self.fan = 60.0
                    self.note_change(s)
            ts = S + (self.ts - S) * k
            self.ts = ts
            log[s] = ts
            self.prod_m[m] += rate
            if ts >= RAISE_TS1:
                self.hot_m[m] += rate
            if self.state == 'RUN' and ts > M.TRIP_TS1 - 0.2:
                probe_plc.state = 'RUN'
                probe_unit.ts1, probe_unit.ps1, probe_unit.vs1 = ts, M.pressure(self.load, M.effective_leak(self.leak[m], 'A')), M.vibration(ts, 0.0, self.fan)
                plc.check_interlock(probe_plc, probe_unit)
                if probe_plc.state == 'TRIP':
                    self.state, self.trip = 'TRIP', probe_plc.trip
                    self.note_change(s)
                    self.push(s + 60, 'reset_check', None)
            prev = log[s - SLOPE_WINDOW_S] if s >= SLOPE_WINDOW_S else ts
            if self.active is None:
                hold_up = hold_up + 1 if (ts > RAISE_TS1 and ce < RAISE_CE and ts > prev) else 0
                if hold_up >= RAISE_HOLD_S:
                    self.raise_alarm(s)
                    hold_up = hold_down = 0
            else:
                hold_down = hold_down + 1 if (ts < CLEAR_TS1 and ts <= prev) else 0
                if hold_down >= CLEAR_HOLD_S:
                    self.clear_alarm(s)
                    hold_up = hold_down = 0
        return self

    # ── 시점의 설정 ──
    def setting_at(self, s):
        i = bisect_right([c[0] for c in self.changes], s) - 1
        return self.changes[max(i, 0)]


def simulate_all():
    return {a: Unit(a).simulate() for a in ASSETS}


# ───────────── 판단 시스템 결정표의 나머지 행(같은 판) ─────────────
OLD_DECISIONS = [   # [표, 이름, 질문, 여러 규칙이 맞을 때, 입력] — 같은 파일 418-421줄
    ['dt:diagnose-cause', '고장 유형 · 원인 판정', '이 경보의 고장 유형과 근본 원인은 무엇인가?', 'PRIORITY', ['in:pattern', 'in:ts1', 'in:ce', 'in:ps1']],
    ['dt:action-candidates', '조치 후보 선택', '이 고장 유형에 쓸 수 있는 조치 방법(스킬 = SOP)은 무엇인가? (원인 한정 스킬은 원인으로 거른다)', 'COLLECT', ['in:failure-mode', 'in:cause', 'in:plc-state']],
    ['dt:compliance', '규정 적합성', '후보 스킬 중 규정상 쓸 수 없거나 감점할 것은 무엇인가?', 'COLLECT',
     ['in:skill-kind', 'in:skill-code', 'in:failure-mode', 'in:plc-mode', 'in:plc-state', 'in:forecast-ts1', 'in:forecast-ps1', 'in:fan100-hours', 'in:standby-ready', 'in:supplier-avl']],
    ['dt:rank-actions', '조치 우선순위', '남은 후보 중 회사 가치(영업이익)에 가장 유리한 순서는?', 'UNIQUE', ['in:forecast-ts1', 'in:order-due', 'in:order-penalty', 'in:order-tier', 'in:hot-lot-claim', 'in:hot-lot-qty']],
]
OLD_NAMES = [   # 행이 가리키는 코드의 이름(같은 파일 98-105 · 183-186 · 266-272줄, 「(교육용 예시)」 꼬리표는 뺐다)
    ('role:operator', '운전원'), ('role:prod-mgr', '생산관리자'), ('role:maint-mgr', '설비보전팀장'), ('role:plant-mgr', '공장장'),
    ('sys:scada', 'SCADA · PLC'), ('sys:cmms', 'CMMS'),
    ('action:set-fan', '팬 속도 설정(FAN_SET)'), ('action:set-load', '펌프 부하 설정(LOAD_SET)'), ('action:select-pump', '운전 펌프 전환(PUMP_SELECT)'),
    ('action:raise-pressure', '압력 설정 상향(PRESSURE_SET)'), ('action:controlled-stop', '계획 정지(STOP)'), ('action:reset', '인터록 리셋(RESET)'),
    ('action:work-order', '정비 작업지시 발행(WO_CREATE)'), ('action:purchase-request', '부품 구매요청(PR_CREATE)'),
    ('ks:manual-hm', 'HYD 유압 파워팩 운전 · 정비 매뉴얼(HM)'), ('ks:sr-04', '설비안전규정 SR-04'), ('ks:pr-07', '구매규정 PR-07'),
    ('ks:strategy-map', '경남유압 BSC 전략맵'),
]
EXPORT_TRACE = ' (A098: 저압 · 고진동 트립은 knowledge_a098.cypher의 별도 규칙)'


def decision_export():
    def cell(v):
        if v is None:
            return ''
        if isinstance(v, list):
            return '; '.join(cell(x) for x in v)
        return str(v)

    def tests(ts):
        return '; '.join(' '.join(cell(x) for x in t if x is not None).replace('False', 'false') for t in ts)
    lines = ['# 판단 시스템 결정표 내보내기',
             '# 시스템: 설비 이상 조치 판단 시스템 / 결정표 판: 2025-03-17 도입 때 등록(HM-8 1.0판 기준) / 내보낸 시각: 2026-10-27 08:10 (+09:00)',
             '# ' + NOTICE,
             '# 형식: 「## 」로 시작하는 절마다 머리 줄 하나와 행들이 있다. 칸은 「 | 」로 나누고, 한 칸 안의 여러 값은 「; 」로 나눈다.',
             '# 규칙 id: 내보낸 시각의 시스템 이름으로 나온다. 시스템이 id를 바꿔도 행의 다른 칸(출처 포함)은 등록 때 값 그대로다.',
             '', '## 결정표', 'id | 이름 | 질문 | 여러 규칙이 맞을 때 | 입력']
    lines += [' | '.join(cell(x) for x in d) for d in OLD_DECISIONS]
    lines += ['', '## 규칙', 'id | 결정표 | 순서 | 조건식 | 결과 | 감점(만원) | 설명 | 대상 | 감점 지표 | 출처 | 검사']
    for r in OLD_RULES:
        rid, dt, order, when, effect, penalty, note, targets, measure, sources, ts = r
        lines.append(' | '.join([CURRENT_ID.get(rid, rid), dt, str(order), when, effect, cell(penalty), note.replace(EXPORT_TRACE, ''), cell(targets),
                                 cell(measure), cell(sources), tests(ts)]))
    lines += ['', '## 스킬', 'id | 이름 | 절차 번호 | 종류 | 설명 | 승인 | 실행 시스템 | 동작 | 단계']
    for sid, name, sop, kind, desc, approver, system, acts, steps in OLD_SKILLS:
        lines.append(' | '.join([sid, name, sop, kind, desc, approver, system, '; '.join(f'{a}={v}' for a, v in acts),
                                 '; '.join(f'{i}) {text} [{ref}]' for i, (text, ref) in enumerate(steps, 1))]))
    lines += ['', '## 코드 이름', 'id | 이름'] + [f'{k} | {v}' for k, v in OLD_NAMES]
    text = '\n'.join(lines) + '\n'
    if '교육용' in text or 'A098' in text:
        raise RuntimeError('결정표 내보내기에 제작 흔적이 남았습니다.')
    return text


# ───────────── 궤적 → 원천 기록 ─────────────

def alarm_id(asset, seq):
    key = asset.lower().replace('-', '')
    return f'ALT-{key}-{seq:04d}-{__import__("zlib").crc32(f"{SEED}-{asset}-{seq}".encode()) & 0xffff:04x}'


class Records:
    """궤적에서 판정 서버 · 게이트웨이 · 카운터 · 예측 · MES 기록과 사례(판정 요청 한 건)를 만든다."""

    def __init__(self, units):
        self.units = units
        inc = [a for a in units[INCIDENT['asset']].alarms if a['incident']]
        if len(inc) != 1 or inc[0]['judge'] is None:
            raise RuntimeError(f'사건 경보가 한 건이 아닙니다: {len(inc)}')
        self.incident = inc[0]
        self.end = inc[0]['judge'] + 20               # 내보내기 끝: 사건 판정 요청 직후
        self.cases = []
        for asset in ASSETS:
            u = units[asset]
            rnd = random.Random(f'{SEED}-{asset}-records')
            seq = rnd.randint(140, 420)
            for a in u.alarms:
                if a['raise_s'] > self.end:
                    continue
                seq += 1
                a['id'] = alarm_id(asset, seq)
                if a['clear_s'] is not None and a['clear_s'] > self.end:
                    a['clear_s'] = None
                if a['judge'] is not None and a['judge'] <= self.end:
                    self.cases.append(self.case(u, a, random.Random(f'{SEED}-{a["id"]}')))   # 사례마다 따로 — 한 사례의 결함이 다른 사례 값을 흔들지 않게
        self.cases.sort(key=lambda c: c['judge'])

    # ── 한 판정 요청 ──
    def case(self, u, a, rnd):
        J = a['judge']
        incident = a['incident']
        c = dict(id=a['id'], asset=u.asset, raise_s=a['raise_s'], judge=J, incident=incident, alarm=a)
        c['plc'] = self.plc_rows(u, J, rnd, incident)
        good = [r for r in c['plc'] if r['quality'] == 'good']
        c['plc_last'] = c['plc'][-1] if c['plc'] else None
        c['plc_last_good'] = good[-1] if good else None
        c['run'] = next((r for r in reversed(u.runs) if r[0] <= J), None)
        if c['run'] and c['run'][1] is not None and c['run'][1] <= J:
            c['run'] = None
        delay = next(((x, y) for x, y in u.faults['daq_delay'] if x <= J < y), None) if not incident else None
        tb = (delay[0] - rnd.randint(0, 5)) if delay else J - rnd.randint(6, 40)
        c['base'] = tb
        c['forecast'] = {}
        for sop in CANDIDATES:
            out, why = self.predict(u, tb, sop)
            dropped = (sop in INCIDENT['drop']) if incident else (rnd.random() < FAULTS['forecast_drop'])
            c['forecast'][sop] = dict(values=out, refusal=why, dropped=dropped)
        c['order'] = None if (not incident and rnd.random() < FAULTS['order_fail']) else self.order_at(u, J)
        return c

    def predict(self, u, tb, sop):
        m = tb // 60
        st = u.setting_at(tb)
        snap = {'forecast_model': F.MODEL_ID, 'disturbance_ramps': ['cooler_health'] if u.ramp[m] else [], 'asset': u.asset,
                't': iso_kst(tb), 'state': st[2], 'pump': 'A', 'ts1': u.log[tb], 't_amb': u.amb[m], 'fan_pct': st[4],
                'load_pct': st[5], 'cooler_health': u.health[m], 'leak': u.leak[m], 'bearing_wear': 0.0}
        try:
            out = F.predict(snap, ACTIONS[sop], HORIZON_S)
        except ValueError as e:
            if not str(e).startswith('예측할 수 없습니다'):
                raise
            return None, str(e)
        return out, None

    def plc_rows(self, u, J, rnd, incident):
        phase = SCENARIO[u.asset]['heartbeat_phase']
        start = J - WINDOW_S
        times = set(t for t in range(start - start % GATEWAY_HEARTBEAT_S + phase, J + 1, GATEWAY_HEARTBEAT_S) if start <= t <= J)
        times |= {ch[0] for ch in u.changes if start <= ch[0] <= J}
        rows = []
        for t in sorted(times):
            if not incident and inside(u.faults['outage'], t):
                continue
            ch = u.setting_at(t)
            bad = not incident and inside(u.faults['bad'], t)
            rows.append(dict(t=t, mode=ch[1], state=ch[2], trip=ch[3], fan=ch[4], load=ch[5], quality='bad' if bad else 'good'))
            if not incident and rnd.random() < 0.02:
                rows.append(dict(rows[-1]))          # 응답이 없어 같은 행을 다시 보냄
        return rows

    def order_at(self, u, J):
        orders = self.orders(u)
        o = [x for x in orders if x['release'] <= J][-1]
        cum = self.cum(u)
        done = cum[J // 60] - cum[o['release'] // 60]
        hot = sum(u.hot_m[max(0, J // 60 - 1440): J // 60])
        return dict(id=o['id'], due_h=(o['due'] - J) / 3600.0, remain=max(0, o['qty'] - int(done)), hot=int(round(hot / 10.0)) * 10)

    def cum(self, u):
        if not hasattr(u, '_cum'):
            c, acc = [], 0.0
            for x in u.prod_m:
                c.append(acc)
                acc += x
            u._cum = c
        return u._cum

    def orders(self, u):
        if hasattr(u, '_orders'):
            return u._orders
        rnd = random.Random(f'{SEED}-{u.asset}-orders')
        cum = self.cum(u)
        out, n = [], rnd.randint(20, 60)
        rel, forced = 0, sec(INCIDENT_ORDER['release']) if u.asset == INCIDENT_ORDER['asset'] else None
        while rel < N_S:
            n += 1
            if forced is not None and rel >= forced:
                o = dict(release=forced, qty=INCIDENT_ORDER['qty'], due=sec(INCIDENT_ORDER['due']))
                forced = None
            else:
                qty = rnd.randrange(2400, 7201, 100)
                o = dict(release=rel, qty=qty, due=rel + int(qty / PROD_RATE * rnd.uniform(1.3, 1.65) * 3600 + rnd.uniform(3, 10) * 3600))
            o['id'] = f'MO-{at(o["release"]):%m%d}-{n:03d}'
            out.append(o)
            target = cum[o['release'] // 60] + o['qty']
            m = next((i for i in range(o['release'] // 60, len(cum)) if cum[i] >= target), len(cum))
            rel = m * 60
            if forced is not None and rel > forced:
                rel = forced
        u._orders = out
        return out

    # ── 파일 ──
    def alarm_list(self):
        rows = []
        for asset in ASSETS:
            for a in self.units[asset].alarms:
                if a['raise_s'] > self.end:
                    continue
                rows.append((a['raise_s'], [a['id'], asset, 'COOLER_DEGRADATION', 'RAISE', iso_utc(a['raise_s']), f"{a['ts']:.2f}", f"{a['ce']:.1f}",
                                            iso_utc(a['judge']) if a['judge'] is not None and a['judge'] <= self.end else '']))
                if a['clear_s'] is not None:
                    rows.append((a['clear_s'], [a['id'], asset, 'COOLER_DEGRADATION', 'CLEAR', iso_utc(a['clear_s']), f"{a['clear_ts']:.2f}", f"{a['clear_ce']:.1f}", '']))
        rows.sort(key=lambda r: (r[0], r[1][1]))
        return table(['경보_ID', '설비', '패턴', '구분', '시각', 'TS1_C', 'CE_pct', '판정_요청_시각'], [r for _, r in rows])

    def plc_file(self):
        # 판정 요청 창이 겹치면 같은 수신이 두 사례에 들어간다 — 설비 · 시각마다 한 벌만(한 창 안의 재전송 행은 둔다)
        best = {}
        for c in self.cases:
            local = {}
            for r in c['plc']:
                local.setdefault((c['asset'], r['t']), []).append(r)
            for k, rs in local.items():
                if len(rs) > len(best.get(k, [])):
                    best[k] = rs
        rows = []
        for asset, t in sorted(best, key=lambda k: (k[1], k[0])):
            for r in best[(asset, t)]:
                good = r['quality'] == 'good'
                rows.append([asset, iso_kst(t), r['mode'] if good else '', r['state'] if good else '', r['trip'] if good else '',
                             f"{r['fan']:.0f}" if good else '', f"{r['load']:.0f}" if good else '', r['quality']])
        return table(['설비', '수신_시각', '운전_모드', '상태', '트립_원인', '팬_설정_pct', '부하_설정_pct', '품질'], rows)

    def counter_rows(self):
        if hasattr(self, '_counter'):
            return self._counter
        rows = []
        for asset in ASSETS:
            u = self.units[asset]
            gaps = u.faults['counter_gap']
            if not (u.runs and u.runs[0][0] == 0):
                rows.append((0, asset, [asset, iso_kst(0), 0, '종료']))
            for start, end in u.runs:
                if start > self.end:
                    continue
                rows.append((start, asset, [asset, iso_kst(start), 0, '시작']))
                k = 1
                stop = end if end is not None else self.end + 1
                while start + COUNTER_PERIOD_MIN * 60 * k < stop and start + COUNTER_PERIOD_MIN * 60 * k <= self.end:
                    t = start + COUNTER_PERIOD_MIN * 60 * k
                    if not inside(gaps, t):
                        rows.append((t, asset, [asset, iso_kst(t), COUNTER_PERIOD_MIN * k, '주기']))
                    k += 1
                if end is not None and end <= self.end:
                    rows.append((end, asset, [asset, iso_kst(end), 0, '종료']))
        rows.sort(key=lambda r: (r[0], r[1]))
        self._counter = rows
        return rows

    def counter_file(self):
        return table(['설비', '기록_시각', '팬100_연속_분', '기록_종류'], [r for _, _, r in self.counter_rows()])

    def counter_last(self, asset, J):
        rows = [r for t, a, r in self.counter_rows() if a == asset and t <= J]
        return rows[-1] if rows else None

    def forecast_file(self):
        rows = []
        for c in self.cases:
            for sop in CANDIDATES:
                f = c['forecast'][sop]
                if f['dropped']:
                    continue
                v = f['values']
                mpa = c['asset'] == 'HYD-03' and at(c['judge']) < MPA_UNTIL
                if v is None:
                    rows.append([c['id'], sop, iso_utc(c['judge']), iso_utc(c['base']), '거부', f['refusal'], '', '', 'MPa' if mpa else 'bar', '', '', F.MODEL_ID, str(HORIZON_S // 60)])
                    continue
                ps1 = f"{round(v['values']['ps1'] / 10.0, 2):.2f}" if mpa else r1(v['values']['ps1'])
                rows.append([c['id'], sop, iso_utc(c['judge']), iso_utc(c['base']), '완료', '', r1(v['values']['ts1']), ps1, 'MPa' if mpa else 'bar',
                             f"{v['operating']['fan_pct']:.0f}", f"{v['operating']['load_pct']:.0f}", F.MODEL_ID, str(HORIZON_S // 60)])
        return table(['경보_ID', '후보', '예측_시각', '기준_관측_시각', '상태', '거부_사유', '예측_TS1_C', '예측_PS1', 'PS1_단위', '계산_팬_pct', '계산_부하_pct', '모델', '예측_구간_분'], rows)

    def order_file(self):
        rows = []
        for c in self.cases:
            o = c['order']
            rnd = random.Random(f'{SEED}-{c["id"]}-mes')
            if o is None:
                rows.append([c['id'], c['asset'], '', iso_utc(c['judge']), '', '', '', '조회 실패(MES 응답 없음)'])
            else:
                rows.append([c['id'], c['asset'], o['id'], iso_utc(c['judge']), f"{o['due_h']:.1f}", o['remain'], o['hot'], ''])
            del rnd
        return table(['경보_ID', '설비', '생산_오더', '조회_시각', '납기까지_남은_시간_h', '오더_잔량_ea', '고온_로트_수량_ea', '비고'], rows)

    # ── 사례의 판단 입력(강사용 메타 · 확인 사례 · 설계 조건 검사가 쓴다) ──
    def made(self, c):
        J, asset = c['judge'], c['asset']
        last = c['plc_last']
        plc_ok = last is not None and last['quality'] == 'good' and J - last['t'] <= GATEWAY_HEARTBEAT_S + GATEWAY_GRACE_S
        counter = self.counter_last(asset, J)
        run = c['run']
        fresh = J - c['base'] <= FORECAST_VALID_S
        ts1, ps1, why = {}, {}, {}
        for sop in CANDIDATES:
            f = c['forecast'][sop]
            if f['dropped']:
                ts1[sop] = ps1[sop] = None
                why[sop] = '예측 결과 행 없음'
            elif f['values'] is None:
                ts1[sop] = ps1[sop] = None
                why[sop] = f['refusal']
            elif not fresh:
                ts1[sop] = ps1[sop] = None
                why[sop] = f'기준 관측이 판정 요청 {J - c["base"]}초 전'
            else:
                ts1[sop] = round(f['values']['values']['ts1'], 1)
                ps1[sop] = round(f['values']['values']['ps1'], 1)
                why[sop] = ''
        return dict(mode=last['mode'] if plc_ok else None, state=last['state'] if plc_ok else None,
                    plc_age=(J - last['t']) if last else None, plc_quality=last['quality'] if last else None,
                    counter=counter, fan_elapsed_min=((J - run[0]) / 60.0) if run else 0.0, ts1=ts1, ps1=ps1, why=why,
                    true_mode=self.units[asset].setting_at(J)[1], true_state=self.units[asset].setting_at(J)[2])

    def categories(self, c):
        mi = self.made(c)
        J, asset, a = c['judge'], c['asset'], c['alarm']
        done = [f['values']['values'] for f in c['forecast'].values() if f['values'] is not None and not f['dropped']]
        k = []
        if any(r1(v['ts1']) == '55.0' for v in done):
            k.append('경계 55')
        if any(r1(v['ts1']) == '65.0' for v in done):
            k.append('경계 65')
        if any(v['ts1'] >= 65.0 for v in done) and mi['true_state'] == 'RUN':
            k.append('운전 중 예측 65 이상')
        if any(r1(v['ps1']) == '165.0' for v in done):
            k.append('경계 165 bar')
        if asset == 'HYD-03' and at(J) < MPA_UNTIL and done:
            k.append('MPa')
        cnt = mi['counter']
        if c['run'] and cnt and cnt[3] in ('시작', '주기') and int(cnt[2]) <= 1440 < mi['fan_elapsed_min']:
            k.append('팬 1,440분 경계')
        if mi['true_mode'] == 'REMOTE_MANUAL':
            k.append('모드 수동')
        if mi['true_state'] == 'TRIP':
            k.append('트립')
        if mi['plc_age'] is None or mi['plc_age'] > GATEWAY_HEARTBEAT_S + GATEWAY_GRACE_S:
            k.append('PLC 끊김')
        if mi['plc_quality'] == 'bad':
            k.append('PLC bad')
        if any(f['refusal'] for f in c['forecast'].values() if not f['dropped']):
            k.append('예측 거부')
        if any(f['dropped'] for f in c['forecast'].values()):
            k.append('전달 실패')
        if J - c['base'] > FORECAST_VALID_S:
            k.append('120초 지남')
        if mi['true_mode'] == 'REMOTE_MANUAL' and any(v is None for v in mi['ts1'].values()):
            k.append('수동 + 누락')
        if c['order'] is None:
            k.append('오더 실패')
        if a['fan'] >= 100.0:
            k.append('재경보')
        if c['run'] and any(x < J and y > c['run'][0] for x, y in self.units[asset].faults['counter_gap']):
            k.append('카운터 끊김')
        if all(judge_ga(mi, sop)[0] for sop in CANDIDATES):
            k.append('모두 제외')
        if not k:
            k.append('정상')
        if c['incident']:
            k.append('사건')
        return k


def judge_ga(mi, sop):
    """설계 검사용: 판정 랩 입력 갈래(지점1 가 · 지점2 가)의 제외 규칙만. (확인된 제외, 미확인)"""
    excl, unknown = [], []
    if sop != 'SOP-COOL-14':
        if mi['mode'] is None:
            unknown.append('원격 자동 아님')
        elif mi['mode'] != 'REMOTE_AUTO':
            excl.append('원격 자동 아님')
    if mi['ts1'][sop] is None:
        unknown.append('예측 유온 65 이상')
    elif mi['ts1'][sop] >= 65.0:
        excl.append('예측 유온 65 이상')
    if mi['state'] is None:
        unknown.append('트립 중')
    elif mi['state'] == 'TRIP':
        excl.append('트립 중')
    return excl, unknown


# ───────────── 비교 산식(지표_정의.md와 같은 식 — 설계 검사 · 손계산 예) ─────────────
BUSINESS = {
    '설비': 'HYD-01~03',
    '안내': '사례마다 다른 오더 값(납기까지_남은_시간, 오더_잔량, 고온_로트_수량)은 오더_현황.csv에 있다. 아래 값은 세 설비 · 모든 사례에 같다.',
    '값': [
        {'이름': '시간당_생산_수량', '값': 300, '단위': 'ea/h', '시스템': 'MES', '뜻': '설계 부하 90 %로 돌 때 한 시간에 만드는 수량'},
        {'이름': '시간당_생산_가치', '값': 50, '단위': '만원/h', '시스템': 'MES', '뜻': '설계 부하 90 %로 한 시간 생산한 것의 가치'},
        {'이름': '납기_지연_위약금', '값': 120, '단위': '만원/h', '시스템': 'ERP', '뜻': '납기를 넘긴 한 시간마다 무는 금액'},
        {'이름': '계획_외_고장_비용', '값': 900, '단위': '만원', '시스템': 'ERP', '뜻': '이 설비가 계획 없이 한 번 고장 났을 때 드는 비용'},
        {'이름': '평균_고장_간격', '값': 1400, '단위': 'h', '시스템': 'CMMS', '뜻': '이 설비의 MTBF'},
        {'이름': '고온_로트_불량_확률', '값': 0.05, '단위': '확률', '시스템': 'QMS', '뜻': '고온에서 만든 로트에서 불량이 나올 확률'},
        {'이름': '고온_로트_클레임_금액', '값': 3000, '단위': '만원', '시스템': 'QMS', '뜻': '그 로트에서 불량이 나왔을 때의 클레임 금액'},
        {'이름': '팬_최대_추가_전력', '값': 6, '단위': 'kW', '시스템': 'EMS', '뜻': '팬을 60 %에서 100 %로 올릴 때 더 드는 전력'},
        {'이름': '전력_단가', '값': 0.015, '단위': '만원/kWh', '시스템': 'EMS', '뜻': '전력 1 kWh의 값'},
    ],
    '표준_작업': [{'작업': '쿨러 핀 세척', '절차': 'SOP-COOL-14', '정지_시간_h': 3, '작업비_만원': 40, '필요_부품': '없음', '시스템': 'CMMS'}],
}
CANDIDATE_SETTINGS = [   # 후보_설정.csv — 후보, 이름, 팬, 부하, 작업지시, 근본 조치(식에 쓰는 값만 — 승인은 SOP 원문 한 곳이 가진다)
    ['SOP-COOL-11', '팬 최대 운전', '100', '', '', '아니오'],
    ['SOP-COOL-12', '팬 최대 운전과 부하 80 %', '100', '80', '', '아니오'],
    ['SOP-COOL-13', '부하 70 %와 야간 핀 세척', '', '70', '쿨러 핀 세척', '예'],
    ['SOP-COOL-14', '쿨러 핀 세척', '', '', '쿨러 핀 세척', '예'],
]


def losses(sop, period, remain, lot, ts1):
    """지표_정의.md의 네 손실(만원). ts1이 None이면 품질은 None(정해지지 않음)."""
    _, _, fan, load, wo, root = next(r for r in CANDIDATE_SETTINGS if r[0] == sop)
    fan = float(fan or 60)
    load = float(load or 90)
    stop, work = (3.0, 40.0) if wo else (0.0, 0.0)
    ratio = load / 90.0
    cost = work + (0.0 if root == '예' else 900.0 * min(1.0, period / 1400.0))
    late = max(0.0, stop + remain / (300.0 * ratio) - period)
    prod = 50.0 * (period * (1 - ratio) + stop) + 120.0 * late
    qual = None if ts1 is None else (0.05 * 3000.0 if ts1 >= 55.0 and lot > 0 else 0.0)
    energy = (fan - 60.0) * 6.0 / 40.0 * period * 0.015
    return dict(비용=cost, 생산=prod, 품질=qual, 에너지=energy, 위약금=120.0 * late)


# ───────────── 문서 ─────────────
_HM8 = {r[2]: r for r in DD.REGISTER if r[0] == 'HM-8'}     # 상태 → (문서, 판, 상태, 시행일, 파일, 제목, 비고) — 문서 목록 한 곳
DOC_NOTICE = '가상 사례: 공개된 현업 문제 유형을 따라 만든 자료이며 실제 회사·제조사·설비의 기록이 아니다.'   # 문서(매뉴얼 · 이력) 사본의 첫머리 표시
# main 원문 사본의 머리 — 원문 제목 아래에 가상 사례 표시와 출처(포털 수업 문서 · 문서 목록의 판)를 덧붙인 두 문단. 본문은 꼬리표 문장만 뺀 원문 그대로.
HM8_TAGS = [('# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8, 교육용 예시)\n',
             f'# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8)\n\n{DOC_NOTICE}\n\n출처: 포털 수업 문서 HM-8 원문의 사본이다. 원문 머리에 판 · 시행일이 없어 회사 문서 목록의 값을 적는다 — '
             f'판 {_HM8["현행"][1]}, 시행 {_HM8["현행"][3]}, {_HM8["현행"][2]}. {_HM8["폐기"][1]}판(시행 {_HM8["폐기"][3]})을 대체한다.\n'),
            ('아래 값은 교육용 가상 설비의 축소 기준이다(일반 산업 설비의 경보는 보통 80 ℃ 안팎이다). ', '')]
HI01_TAGS = [('판본: 1.0 / 수업용 가상 HYD 유압 파워팩 / 2026-10-27',
              f'{DOC_NOTICE}\n\n출처: 포털 수업 문서 HI-01 원문의 사본이다.\n\n판본: 1.0 / HYD 유압 파워팩 / 2026-10-27')]


OLD_DOC_TAGS = [('# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8, 교육용 예시)\n', '# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8)\n'),
                (DD.EDU, DOC_NOTICE)]
# 1.0판 매뉴얼과 작업지시 이력은 data_documents.py가 문서 지식 묶음과 함께 쓰는 한 벌이다. 그 묶음의 검토본 해시가 원래 글자에 묶여 있어,
# 이 묶음의 사본에서만 꼬리표를 바꾼다(그 묶음을 다시 만들며 data_documents.py에서 바꾸면 이 표는 「뺄 문장이 없습니다」로 멈춘다 — 그때 지운다).


def tagged(name, text, tags):
    for old, new in tags:
        if old not in text:
            raise RuntimeError(f'{name}: 바꿀 문장이 없습니다 — 원본이 바뀌었는지 보고 표를 고칩니다: {old!r}')
        text = text.replace(old, new)
    return text


def sample(name, tags):
    """main 원문 사본. 「교육용 · 수업용」 꼬리표 문장만 빼고, 판 · 시행일이 없는 머리에는 문서 목록의 값을 적는다(main 원문 정리는 시스템 작업)."""
    return tagged(name, (SYS/'it/portal/www/samples'/name).read_text(encoding='utf-8-sig'), tags)


def sop_register(hm8):
    """HM-8 1.1의 절차 목록(### SOP-… 머리와 그 절) — targets.csv(통합 03 실습2)."""
    rows, section = [], ''
    for line in hm8.splitlines():
        m = re.match(r'## (HM-8\.\d+) ', line)
        if m:
            section = m.group(1)
        m = re.match(r'### (SOP-[A-Z]+-\d+) (.+)$', line)
        if m:
            rows.append([m.group(1), m.group(2), section])
    return table(['sop_id', 'name', 'source_section'], rows)


TARGETS = table(['sop_id', 'name', 'kind', 'codes', 'source_section'],
                [['SOP-COOL-11', '팬 최대 운전', 'control', 'FAN_SET', 'HM-8.5'], ['SOP-COOL-12', '팬 최대 운전과 부하 80 %', 'control', 'FAN_SET;LOAD_SET', 'HM-8.5'],
                 ['SOP-COOL-13', '부하 70 %와 야간 핀 세척', 'control', 'LOAD_SET;WO_CREATE', 'HM-8.5'], ['SOP-COOL-14', '쿨러 핀 세척', 'work_order', 'WO_CREATE', 'HM-8.7']])
FAILURE_MODES = table(['failure_mode_id', 'name', 'component'],   # 회사 고장 유형 목록(main 포털 이름 표 it/portal/www/names.json과 같은 ID · 이름)
                      [['fm:cooler-cooling-loss', '쿨러 냉각 성능 상실', '오일 쿨러'], ['fm:pump-volumetric-efficiency-loss', '주 펌프 체적 효율 저하', '주 펌프 (A)']])

WORK_STANDARD = f'''# 냉각 경보 조치 판단 — 작업 기준

{NOTICE}

쿨러 성능 저하 경보(COOLER_DEGRADATION)가 났을 때 검토하는 조치를 판단할 때 지키는 회사 기준이다. 실제 설비 조작은 이 기준의 범위가 아니다.

## 1. 원문

- 현행 조치 원문은 HM-8 1.1판(2026-09-01 시행)이다. 조치의 단계 · 완료 기준 · 금지와 제한 · 승인은 현행 원문을 따른다.

## 2. 조건을 옮길 때

- 원문의 「이상 · 초과 · 미만 · 이하」를 그대로 옮긴다. 같은 내용을 원문끼리 다르게 적었으면 둘 다 적고 어느 쪽을 따랐는지 검토 기록에 남긴다.
- 원문에 없는 기준값 · 단계를 만들지 않는다.

## 3. 판단 입력

- 입력은 판정을 요청한 시각을 기준으로 원천 기록에서 만든다. 그 시각 뒤에 들어온 기록은 쓰지 않는다.
- 단위가 다른 원천은 규칙의 단위로 환산한다. 비교는 환산한 원값으로 하고, 반올림은 표시할 때만 한다.
- 값이 없거나 확인이 필요한 입력은 0이나 정상값으로 채우지 않는다. 왜 없는지(원천 · 시각)를 함께 남긴다.
- 입력을 어느 파일의 어느 기록에서 어떻게 만들었는지 다른 사람이 다시 따라갈 수 있게 기록한다.

## 4. 결과 수집과 미확인

맞는 경고 · 감점 · 제외를 모두 모은다. 제외가 있으면 후보에서 빼고, 없으면 후보를 유지하되 경고 · 감점과 수행 조건을 함께 남긴다. 같은 규칙의 감점은 한 번만 반영한다.

그 후보에 걸린 규칙의 입력이 빠져 참 · 거짓을 알 수 없으면 그 규칙을 미확인으로 표시한다. 알려진 제외 사유가 있으면 제외하면서 미확인도 남기고, 제외가 없더라도 미확인 규칙이 있으면 최종 허용 판단은 보류한다.

## 5. 후보 유지와 실행

후보 유지는 실행 허가가 아니다.
'''


def collection_doc(rec):
    return f'''# 판단 입력 원천과 기록 방식

{NOTICE}

판정 서버 기록(경보 목록 · 예측 결과 · 오더 조회)의 시각은 UTC(끝의 「Z」)이고, 현장 기록(PLC 상태 수신 · 팬 운전 카운터)의 시각은 한국 표준시(+09:00)다.
내보낸 범위는 HYD-01 ~ 03, 2026-09-28 00:00 ~ {iso_kst(rec.end)[:16].replace("T", " ")} (+09:00)이다.

## 경보_목록.csv — 판정 서버 경보 기록

- 쿨러 성능 저하 경보(COOLER_DEGRADATION)가 날 때(RAISE)와 풀릴 때(CLEAR) 한 행씩 남는다. 경보가 날 때마다 새 경보 ID가 붙고, 풀리는 행은 그 경보 ID를 쓴다.
- `TS1_C` · `CE_pct`: 그 행이 남을 때 감지기가 본 유온 · 냉각 효율.
- `판정_요청_시각`: 운전원이 그 경보로 조치 판단을 요청한 시각(RAISE 행에만).

## PLC_상태_수신.csv — 엣지 게이트웨이 수신 기록

- 판정 요청마다 그 설비의 요청 전 3분 구간을 내보냈다.
- 게이트웨이는 PLC 상태를 하트비트로 보내고, 운전 모드 · 상태 · 설정이 바뀌면 그때 한 번 더 보낸다. 판정 서버의 응답을 받지 못하면 같은 행을 다시 보낸다.
- 게이트웨이 설정표: 하트비트 {GATEWAY_HEARTBEAT_S}초, 수신 유예 {GATEWAY_GRACE_S}초.
- `품질`: good(정상 수신) · bad(PLC 통신 오류 — 값 칸이 빈 수신).
- `운전_모드`: REMOTE_AUTO(원격 자동) · REMOTE_MANUAL(원격 수동 — 현장 패널에서 수동 조작이 들어온 상태) · LOCAL(현장 제어). `상태`: RUN(운전) · TRIP(인터록 정지) · STOP(계획 정지). `트립_원인`: OVERTEMP(유온 높음).
- `팬_설정_pct` · `부하_설정_pct`: 그때의 설정값.

## 팬_운전_카운터.csv — PLC 팬 100 % 연속 운전 카운터

- 팬이 100 %로 돌기 시작하면 「시작」(0분), 100 %로 도는 동안 {COUNTER_PERIOD_MIN}분마다 「주기」(시작 뒤 누적 분, 분 단위 정수), 100 %에서 내려오거나 설비가 서면 「종료」(0분)를 남긴다. 이 세 경우에만 행이 생긴다.
- 카운터는 행을 남기지 않는 동안에도 100 % 운전 시간을 센다. 행의 누적 분은 그 행을 남긴 시각의 값이므로, 그 뒤 어느 시각의 연속 운전 시간은 그 사이 100 % 운전이 이어졌을 때 그 행의 누적 분에 그 시각까지 지난 시간을 더한 값이다.
- 내보내기 첫 행(2026-09-28 00:00)은 그때의 카운터 상태다.

## 예측_결과.csv — 조치 후 예측

- 판정 요청마다 예측 서비스가 그 경보의 후보마다 「이 조치를 하면 15분 뒤」 유온 TS1과 토출 압력 PS1을 새로 계산한다(모델 `{F.MODEL_ID}`, 판 {F.MODEL_REVISION}). 계산은 `기준_관측_시각`의 관측값으로 한다.
- 예측 서비스 설정: 예측 결과는 기준 관측 뒤 {FORECAST_VALID_S}초까지 유효하다.
- `상태`: 완료 · 거부. 거부면 `거부_사유`에 예측 서비스가 낸 문장이 그대로 있다.
- `계산_팬_pct` · `계산_부하_pct`: 그 계산에 쓴 팬 · 부하 설정(후보의 조치를 적용한 뒤의 설정).
- `PS1_단위`: bar 또는 MPa. HYD-03의 2026-10-10 이전 결과는 옛 내보내기 형식이라 MPa다(1 MPa = 10 bar).

## 오더_현황.csv — MES · QMS 조회

- 판정 요청 때 판정 서버가 그 설비의 생산 오더를 MES에서, 출하 대기 고온 로트를 QMS에서 조회한 결과다. 조회에 실패하면 값이 비고 `비고`에 적힌다.
- `납기까지_남은_시간_h`: 조회 시각부터 그 오더의 납기까지. `오더_잔량_ea`: 남은 생산 수량.
- `고온_로트_수량_ea`: 지난 24시간 동안 유온 55 ℃ 이상에서 만들어 출하를 기다리는 로트 수량(QMS 보류 기준, 10 ea 단위).
'''


def hm(s):
    return at(s).astimezone(KST).strftime('%H:%M:%S')


def incident_memo(rec):
    c = next(x for x in rec.cases if x['incident'])
    u = rec.units[c['asset']]
    a = c['alarm']
    prev = [x for x in u.alarms if x['raise_s'] < a['raise_s'] and x['action_applied'] and x['action'] == 'SOP-COOL-11'][-1]
    last = c['plc_last']
    run_start = c['run'][0]
    cnt = rec.counter_last(c['asset'], c['judge'])
    plan_change = [ch for ch in u.changes if ch[0] <= c['judge'] and ch[0] >= c['judge'] - 3 * 3600 and ch[5] == 90.0]
    lines = [f'# 경보 처리 메모 — {c["asset"]} (2026-10-27 야간)', '', NOTICE, '',
             '야간 운전원이 HMI 화면에서 옮겨 적은 메모다. 시각은 한국 표준시(+09:00)다.', '',
             '## 앞 교대에서 인계받은 것(10월 26일)', '',
             f'- {hm(prev["raise_s"])} 쿨러 성능 저하 경보. {hm(prev["action_applied"])} 원격으로 팬 100 %(SOP-COOL-11) 실행.',
             f'- 15분 재관측 때 경보가 풀리지 않았다. 06:00 주간 생산 계획으로 펌프 부하 80 %, {hm(prev["clear_s"])} 경보 해제. 팬은 100 % 그대로 두었다.', '',
             '## 이번 경보', '',
             f'- 경보 ID `{a["id"]}`: {hm(a["raise_s"])} 발생. 그때 유온 TS1 {a["ts"]:.2f} ℃, 냉각 효율 CE {a["ce"]:.1f} %.',
             f'- {hm(c["judge"])} 조치 판단 요청.', '',
             f'## 판단 요청 때의 PLC 상태({hm(last["t"])} 수신)', '',
             f'- 운전 모드 {last["mode"]}, 상태 {last["state"]}',
             f'- 팬 설정 {last["fan"]:.0f} %, 펌프 부하 설정 {last["load"]:.0f} %' + (f'({hm(plan_change[-1][0])} 야간 오더로 80 → 90 %)' if plan_change else ''), '',
             '## 팬 운전 카운터', '',
             f'- 팬 100 % 「시작」 기록: {iso_kst(run_start)[:19].replace("T", " ")}',
             f'- 마지막 기록: {cnt[1][:19].replace("T", " ")} 「{cnt[3]}」 {cnt[2]}분', '',
             f'## 조치 후 예측(예측 서비스 화면 — 15분 뒤, 기준 관측 {hm(c["base"])})', '',
             '| 후보 | 예측 유온 TS1 | 예측 토출 압력 PS1 | 계산에 쓴 팬 · 부하 |', '|---|---|---|---|']
    for sop in CANDIDATES:
        f = c['forecast'][sop]
        if f['dropped']:
            lines.append(f'| {sop} | 예측 결과 없음 | | |')
        elif f['values'] is None:
            lines.append(f'| {sop} | 거부: {f["refusal"]} | | |')
        else:
            v, op = f['values']['values'], f['values']['operating']
            lines.append(f'| {sop} | {r1(v["ts1"])} ℃ | {r1(v["ps1"])} bar | {op["fan_pct"]:.0f} % · {op["load_pct"]:.0f} % |')
    o = c['order']
    lines += ['', f'## 생산 오더(MES · QMS 조회, {hm(c["judge"])})', '',
              f'- 생산 오더 {o["id"]}: 납기까지 {o["due_h"]:.1f}시간, 잔량 {o["remain"]:,} ea',
              f'- 출하 대기 고온 로트(지난 24시간 유온 55 ℃ 이상 생산): {o["hot"]:,} ea', '']
    return '\n'.join(lines)


CHECK_KINDS = [   # 확인_사례.csv(실전 02 실습5)에 넣을 사례 종류 — 고르는 순서. 강사용 이름이라 파일에는 쓰지 않는다.
    '사건', '경계 55', '모드 수동', '수동 + 누락', '트립', '운전 중 예측 65 이상', '예측 거부', '재경보', '정상']


def pick_check_cases(rec, cats):
    """확인 사례: 종류마다 궤적의 사례 하나(먼저 나온 것). 02-5에는 수집 규칙 문서가 없으므로 PLC 끊김 · bad · 120초 지남 사례는 고르지 않는다."""
    skip = {'PLC 끊김', 'PLC bad', '120초 지남'}
    chosen = []
    for kind in CHECK_KINDS:
        pool = [c for c in rec.cases if kind in cats[c['id']] and not (skip & set(cats[c['id']])) and c not in chosen]
        if kind == '경계 55':
            pool = [c for c in pool if any(f['values'] and r1(f['values']['values']['ts1']) == '55.0' for s, f in c['forecast'].items() if s != 'SOP-COOL-14' and not f['dropped'])] or pool
        if kind == '모드 수동':
            pool = [c for c in pool if (rec.made(c)['ts1']['SOP-COOL-11'] or 0) >= 55.0] or pool
        if not pool:
            raise RuntimeError(f'확인 사례 종류 「{kind}」에 맞는 사례가 궤적에 없습니다 — 시드 · 계획 상수를 바꿉니다.')
        chosen.append(pool[0])
    return sorted(chosen, key=lambda c: c['judge'])


def check_cases_file(rec, chosen):
    rows = []
    for c in chosen:
        J = c['judge']
        last = c['plc_last']
        cnt = rec.counter_last(c['asset'], J)
        head = [c['id'], c['asset'], iso_kst(J)]
        if last['quality'] == 'good':
            rows.append(head + ['', '운전_모드', last['mode'], '', 'PLC 상태 수신', iso_kst(last['t']), ''])
            rows.append(head + ['', '상태', last['state'], '', 'PLC 상태 수신', iso_kst(last['t']), ''])
        else:
            rows.append(head + ['', '운전_모드', '', '', 'PLC 상태 수신', iso_kst(last['t']), '품질 bad'])
            rows.append(head + ['', '상태', '', '', 'PLC 상태 수신', iso_kst(last['t']), '품질 bad'])
        hours = rec.made(c)['fan_elapsed_min'] / 60          # 판정 요청 때의 판단 입력(h) — 이 랩은 입력을 만들지 않고 받는다(입출력_계약 「확인 사례」)
        if (round(hours, 2) > 24) != (hours > 24):
            raise RuntimeError(f'확인 사례 {c["id"]}: 팬 연속 시간 {hours:.4f} h를 소수 둘째 자리로 적으면 24 h 경계의 판정이 바뀝니다 — 사례를 다시 고릅니다.')
        rows.append(head + ['', '팬100_연속', f'{hours:.2f}', 'h', '팬 운전 카운터', cnt[1] if cnt else '', ''])
        for sop in CANDIDATES:
            f = c['forecast'][sop]
            if f['dropped']:
                rows.append(head + [sop, '예측_TS1', '', '℃', '예측 결과', '', '예측 결과 행 없음'])
                rows.append(head + [sop, '예측_PS1', '', 'bar', '예측 결과', '', '예측 결과 행 없음'])
            elif f['values'] is None:
                rows.append(head + [sop, '예측_TS1', '', '℃', '예측 결과', iso_kst(c['base']), '거부: ' + f['refusal']])
                rows.append(head + [sop, '예측_PS1', '', 'bar', '예측 결과', iso_kst(c['base']), '거부: ' + f['refusal']])
            else:
                v = f['values']['values']
                rows.append(head + [sop, '예측_TS1', r1(v['ts1']), '℃', '예측 결과', iso_kst(c['base']), ''])
                rows.append(head + [sop, '예측_PS1', r1(v['ps1']), 'bar', '예측 결과', iso_kst(c['base']), ''])
    return table(['사례', '설비', '판정_요청_시각', '후보', '입력', '값', '단위', '원천', '원천_시각', '비고'], rows)


def metric_doc(rec, cats):
    """지표_정의.md. 손계산 예는 사건이 아닌 이력 사례 하나(SOP-COOL-12 예측 완료 · 오더 값 있음 · 고온 로트 있음)."""
    ex = None
    for c in rec.cases:
        mi = rec.made(c)
        if (not c['incident'] and c['order'] and c['order']['hot'] > 0 and mi['ts1']['SOP-COOL-12'] is not None
                and c['order']['due_h'] > 0 and 'PLC 끊김' not in cats[c['id']]):
            ex = (c, mi)
            break
    if ex is None:
        raise RuntimeError('지표 손계산 예로 쓸 이력 사례가 없습니다.')
    c, mi = ex
    o = c['order']
    period, remain, lot, ts1 = o['due_h'], float(o['remain']), float(o['hot']), mi['ts1']['SOP-COOL-12']
    period = round(period, 1)
    L = losses('SOP-COOL-12', period, remain, lot, ts1)
    finish = remain / (300 * 80 / 90)
    late = max(0.0, finish - period)
    q_text = f'{ts1:.1f} ℃는 55 ℃ 이상이고 고온 로트가 {lot:g} ea 있다: 0.05 × 3000' if L['품질'] else f'{ts1:.1f} ℃는 55 ℃보다 낮다'
    late_text = (f'완료까지 걸리는 시간은 0 + {remain:g} ÷ (300 × 80/90) = {finish:.4f}시간이고 기간 {period:g}시간보다 '
                 + ('짧아서 납기 지연 위약금이 0이다.' if late == 0 else f'{late:.4f}시간 길어서 위약금이 120 × {late:.4f} = {120 * late:.2f}이다. 금액은 끝에서만 반올림한다.'))
    return METRIC_DOC.format(notice=NOTICE, eid=c['id'], period=f'{period:g}', remain=f'{remain:g}', lot=f'{lot:g}', ts1=f'{ts1:.1f}',
                             cost=f'{money(L["비용"]):.2f}', prod=f'{money(L["생산"]):.2f}', qual=f'{money(L["품질"]):.2f}', energy=f'{money(L["에너지"]):.2f}',
                             q_text=q_text, late_text=late_text, late_term=f'120 × {late:.4f}' if late else '120 × 0', rank_rule=portal_rank_rule())


def portal_rank_rule():
    """포털 판단 화면이 후보 순위를 매기는 점수 — main 판단 규칙 rule:rank-value의 설명 그대로(지표_정의.md 「포털의 성과 지표 점수」)."""
    cy = (SYS/'it/neo4j/v2/instances.cypher').read_text(encoding='utf-8')
    m = re.search(r"\['rule:rank-value','dt:rank-actions',\d+,'RANK','([^']+)'", cy)
    if not m:
        raise RuntimeError('main instances.cypher에서 rule:rank-value 행을 찾지 못했습니다 — 지표_정의.md의 포털 순위 점수 문장을 다시 맞춥니다.')
    return m.group(1)


METRIC_DOC = '''# 조치 후보를 견주는 네 지표 — 정의와 식

{notice}

규칙을 통과한 조치 후보를 견줄 때 쓰는 주어진 비교 산식이다. 이 문서가 답하는 물음은 하나다.

> 이 조치를 하면, 이 오더의 납기까지 얼마를 잃을 것으로 예상되는가?

지표는 넷이고 모두 **예상되는 손실 금액**이다. 단위는 만 원이며 작을수록 좋다. 대상은 쿨러 성능 저하 경보가 난 설비이고, 확인된 원인은 쿨러 핀 오염으로 둔다.

| 지표 | 무엇을 잃는가 | 이어지는 성과 지표 (목표) |
|---|---|---|
| 비용 | 정비에 드는 돈과, 원인을 남겨 둔 채 돌리는 동안의 고장 위험 | 평균 고장 간격 (설비 가용성 확보) |
| 생산 | 부하를 낮추거나 설비를 세워 줄어든 생산과, 그 때문에 늦어진 납기 | 생산량 (설비 가용성 확보), 납기 준수율 (납기 신뢰) |
| 품질 | 유온이 높은 채로 만든 제품에서 나올 수 있는 클레임 | 품질 클레임 (품질 신뢰) |
| 에너지 | 팬을 더 세게 돌리는 데 드는 전력 | 전력 사용량 (에너지 효율) |

## 포털의 성과 지표 점수

포털 판단 화면은 후보의 순위를 판단 규칙 `rule:rank-value`의 점수(성과 지표 점수)로 매기고, 점수가 높을수록 앞에 둔다. 그 규칙의 설명은 다음과 같다.

> {rank_rule}

## 값이 오는 곳

| 파일 | 담긴 것 | 무엇마다 다른가 |
|---|---|---|
| `업무_값.json` | 업무 시스템 필드에서 가져온 고정 값과 표준 작업 | 모든 사례에 같다 |
| `오더_현황.csv` | 사례마다 그 설비의 오더 값: `납기까지_남은_시간_h`, `오더_잔량_ea`, `고온_로트_수량_ea` | 사례마다 |
| `후보_설정.csv` | 후보마다 팬과 부하를 얼마로 두는지, 작업지시를 거는지, 근본 조치인지 | 후보마다 |
| `예측_결과.csv` | 후보마다의 조치 후 예측 유온 | 사례마다, 후보마다 |

## 식에 쓰는 낱말

| 낱말 | 뜻 |
|---|---|
| 기간 | 그 사례의 `납기까지_남은_시간_h`(h). 이 오더의 납기까지를 견준다 |
| 오더 잔량 | 그 사례의 `오더_잔량_ea` |
| 고온 로트 수량 | 그 사례의 `고온_로트_수량_ea` |
| 부하 | 후보의 `부하_설정_퍼센트`. 칸이 비어 있으면 부하를 바꾸지 않는 후보이므로 설계 부하 90 %다 |
| 부하 비율 | 부하 ÷ 90 |
| 팬 | 후보의 `팬_설정_퍼센트`. 칸이 비어 있으면 팬을 바꾸지 않는 후보이므로 정상 운전점 60 %다 |
| 정지 시간 | 후보의 `작업지시` 칸에 적힌 표준 작업의 `정지_시간_h`. 작업지시가 없으면 0이다 |
| 작업비 | 후보의 `작업지시` 칸에 적힌 표준 작업의 `작업비_만원`. 작업지시가 없으면 0이다 |

설계 부하 90 %와 정상 팬 60 %는 설비의 정상 운전점이다. `팬_최대_추가_전력`은 팬을 60 %에서 100 %로, 곧 40 %p 올릴 때 더 드는 전력이다.

## 네 지표의 식

### 비용 = 정비 작업비 + 고장 위험
- 정비 작업비 = 작업비
- 고장 위험 = `계획_외_고장_비용` × (기간 ÷ `평균_고장_간격`)
  - 괄호 안의 값은 1을 넘지 않는다(넘으면 1로 한다).
  - `근본_조치`가 「예」인 후보의 고장 위험을 0으로 두는 것은 이 계산의 가정이다. 작업지시 발행이나 실제 정비 완료를 뜻하지 않는다.

### 생산 = 생산 감소 + 납기 지연 위약금
- 생산 감소 = `시간당_생산_가치` × (기간 × (1 − 부하 비율) + 정지 시간)
- 완료까지 걸리는 시간 = 정지 시간 + 오더 잔량 ÷ (`시간당_생산_수량` × 부하 비율)
- 납기 지연 위약금 = `납기_지연_위약금` × (완료까지 걸리는 시간 − 기간)
  - 괄호 안의 값이 0보다 작으면 0으로 한다(납기 안에 끝난다).

### 품질 = 품질 클레임 위험
- 후보의 조치 후 예측 유온이 55 ℃ 이상이고 고온 로트 수량이 0보다 크면: `고온_로트_불량_확률` × `고온_로트_클레임_금액`
- 그렇지 않으면 0
- 55 ℃는 매뉴얼의 회복 판정 기준이다(HM-8.6, 「TS1이 55 ℃ 미만」).

### 에너지 = 팬 전력비
- 에너지 = (팬 − 60) × `팬_최대_추가_전력` ÷ 40 × 기간 × `전력_단가`

## 손으로 해 보는 예

사례 {eid}의 SOP-COOL-12(팬 100 %, 부하 80 %, 작업지시 없음, 예측 유온 {ts1} ℃, 기간 {period} h, 오더 잔량 {remain} ea, 고온 로트 {lot} ea)를 위 식에 넣으면 다음과 같다.

| 지표 | 식에 넣은 값 | 값 (만 원) |
|---|---|---|
| 비용 | 0 + 900 × ({period} ÷ 1400) | {cost} |
| 생산 | 50 × ({period} × (1 − 80/90) + 0) + {late_term} | {prod} |
| 품질 | {q_text} | {qual} |
| 에너지 | (100 − 60) × 6 ÷ 40 × {period} × 0.015 | {energy} |

{late_text}

## 계산 가정

작업지시가 있는 후보의 표준 정지 시간을 기간 안에 모두 더하고, 근본 조치의 고장 위험을 0으로 놓는 단순화가 있다. 야간 작업의 실제 시작 · 완료 시각과 정비 전 위험을 따로 계산하지 않는다. 생산 감소 식은 기간 전체의 감산과 정지를 더하므로 두 효과가 겹치는 시간도 포함한다.

네 손실과 규칙의 감점 금액을 한 번씩 더한 비교 합계를 쓴다. 필요한 값이 없으면 그 후보의 지표와 합계 순위를 보류하고, 같은 합계는 동순위다. 각 지표의 원값과 가정을 보존하고, 금액은 소수 둘째 자리로 반올림해 적는다.
'''


# ───────────── 설계 조건 검사(구성안 3.3) — 하나라도 어긋나면 파일을 쓰지 않는다 ─────────────
NEED_KINDS = ['정상', '경계 55', '운전 중 예측 65 이상', '경계 165 bar', 'MPa', '팬 1,440분 경계', '모드 수동', '트립', 'PLC 끊김', 'PLC bad',
              '예측 거부', '전달 실패', '120초 지남', '수동 + 누락', '오더 실패', '재경보', '모두 제외']


def incident_totals(rec, c):
    mi = rec.made(c)
    o = c['order']
    period, remain, lot = round(o['due_h'], 1), float(o['remain']), float(o['hot'])
    over24 = mi['fan_elapsed_min'] > 1440
    out = {}
    for sop in CANDIDATES:
        L = losses(sop, period, remain, lot, mi['ts1'][sop])
        pen = 20.0 if over24 and sop in ('SOP-COOL-11', 'SOP-COOL-12') else 0.0
        known = L['비용'] + L['생산'] + L['에너지'] + pen + (L['품질'] or 0.0)
        out[sop] = dict(L, 감점=pen, 합계=None if L['품질'] is None else known, 아는_값_합계=known)
    return out


def design_checks(rec, cats, chosen):
    bad = []
    c = rec.incident
    case = next(x for x in rec.cases if x['incident'])
    mi = rec.made(case)
    u = rec.units[case['asset']]
    t1, t13, t14 = mi['ts1']['SOP-COOL-11'], mi['ts1']['SOP-COOL-13'], mi['ts1']['SOP-COOL-14']
    # 1. 사건
    if not (t1 is not None and t1 == t14 and t1 >= 55.0):
        bad.append(f'사건: 11 예측 = 14 예측 ≥ 55가 아님 ({t1}, {t14})')
    if not (t13 is not None and t13 < 55.0):
        bad.append(f'사건: 13 예측 < 55가 아님 ({t13})')
    if not case['forecast']['SOP-COOL-12']['dropped']:
        bad.append('사건: 12 예측 행이 있음')
    before = [a for a in u.alarms if a['raise_s'] < c['raise_s']]
    if not before or before[-1]['clear_s'] is None or before[-1]['clear_s'] > c['raise_s']:
        bad.append('사건: 사건 경보 앞에 같은 설비의 해제(CLEAR)가 없음')
    prev = [a for a in before if a['action_applied'] and a['action'] == 'SOP-COOL-11']
    if not prev or at(prev[-1]['raise_s']).date() != (INCIDENT['day'] - timedelta(days=1)).date():
        bad.append('사건: 전날 SOP-COOL-11 조치가 궤적에 없음')
    else:
        p = prev[-1]
        recovered = p['clear_s'] is not None and p['clear_s'] <= p['action_applied'] + 900 and max(u.log[p['action_applied']:p['action_applied'] + 900]) < 55.0
        if recovered:
            bad.append('사건: 전날 SOP-COOL-11이 15분 재관측에서 회복함(운전 기록은 미회복)')
        if not (p['clear_s'] and at(p['clear_s']).hour >= 6 and u.setting_at(p['clear_s'])[5] == 80.0):
            bad.append('사건: 전날 경보가 주간 계획 부하 80 %에서 풀리지 않음')
    cnt = rec.counter_last(case['asset'], case['judge'])
    if not (cnt and cnt[3] in ('주기', '시작') and int(cnt[2]) <= 1440 < mi['fan_elapsed_min']):
        bad.append(f'사건: 카운터 마지막 기록 ≤ 1440분 · 판정 시각 경과 > 1440분이 아님 ({cnt}, {mi["fan_elapsed_min"]:.1f})')
    if not (cnt and (case['judge'] - sec(datetime.fromisoformat(cnt[1]))) > COUNTER_PERIOD_MIN * 60 and mi['mode'] is not None
            and u.setting_at(case['judge'])[4] == 100.0):
        bad.append('사건: 카운터 마지막 기록 뒤 주기를 넘게 기록이 빠지고 PLC 팬 설정은 100 %인 상태가 아님(지점3이 사건에서 갈리지 않음)')
    tot = incident_totals(rec, case)
    if not (tot['SOP-COOL-11']['품질'] and tot['SOP-COOL-14']['품질'] and tot['SOP-COOL-13']['위약금'] > 0
            and tot['SOP-COOL-11']['위약금'] == 0 and tot['SOP-COOL-14']['위약금'] == 0 and tot['SOP-COOL-12']['위약금'] == 0):
        bad.append('사건: 품질 · 위약금이 한쪽 후보에서만 생기지 않음')
    if not all(any(tot[s][k] for s in CANDIDATES) for k in ('비용', '생산', '품질', '에너지')):
        bad.append('사건: 네 지표 가운데 어느 후보에서도 움직이지 않는 지표가 있음')
    # 2. 갈래(판정 랩): 지점3 가 · 지점4 가 → 1위 11, 지점4 나(경고 후보를 견주지 않음) → 1위 14, 지점3 나(끊긴 카운터 = 값 없음 → 11 · 12 보류) → 1위 14
    t11, t14s, t13s = tot['SOP-COOL-11']['합계'], tot['SOP-COOL-14']['합계'], tot['SOP-COOL-13']['합계']
    if not (t11 < t14s < t13s):
        bad.append(f'갈래: 순위가 11 < 14 < 13이 아님 ({t11:.2f}, {t14s:.2f}, {t13s:.2f}) — 두 지점의 갈래마다 1위가 달라지지 않음')
    # 3. 이력 사례 종류
    seen = {k for v in cats.values() for k in v}
    miss = [k for k in NEED_KINDS if k not in seen]
    if miss:
        bad.append('이력: 사례 종류가 없음 — ' + ', '.join(miss))
    # 4. 같은 사실 — 작업 이력(data_documents)과 궤적
    h1 = rec.units['HYD-01']
    if not any(a['action'] == 'SOP-COOL-11' and a['action_applied'] and at(a['raise_s']).date() == kst(2026, 10, 5).date() for a in h1.alarms):
        bad.append('같은 사실: HYD-01 10월 5일 SOP-COOL-11(작업 이력)이 궤적에 없음')
    if not any(start <= sec(kst(2026, 10, 6, 14)) and (end or N_S) - start >= 26 * 3600 for start, end in h1.runs):
        bad.append('같은 사실: HYD-01 10월 6일 팬 100 % 누적 26 h(작업 이력)가 궤적에 없음')
    for e in DD.INCIDENT_EVE:
        if DD.d(e['days']) != (INCIDENT['day'] - timedelta(days=1)).date() or e['asset'] != INCIDENT['asset']:
            bad.append(f'같은 사실: 작업 이력의 사건 전날 운전 기록({e["asset"]} {DD.d(e["days"])})이 사건 전날 · 설비와 다름')
    dd = [e for e in DD.events(random.Random(DD.SEED)) if e['kind'] in ('fin', 'op') and e['day'] >= T0.date()]
    for e in dd:
        if e['kind'] == 'fin':
            ok = any(at(sec(s)).date() == e['day'] for s, _ in SCENARIO[e['asset']]['cleanings'])
            if not ok:
                bad.append(f'같은 사실: {e["asset"]} {e["day"]} 세척(작업 이력)이 궤적에 없음')
    # 5. 포털 대표 경보와 섞지 않음(K-121)
    for a in rec.units[PORTAL_ALARM[0]].alarms:
        if abs(a['raise_s'] - sec(PORTAL_ALARM[1])) < 3600:
            bad.append('포털 대표 경보와 같은 설비 · 시각에 경보가 남')
    for asset in ASSETS:
        for a in rec.units[asset].alarms:
            if f'{a["ts"]:.2f}' == '55.71' and f'{a["ce"]:.1f}' == '46.2':
                bad.append(f'{asset}: 포털 대표 값(55.71 ℃ · 46.2 %)과 같은 경보 값')
    if len(chosen) < 8:
        bad.append(f'확인 사례가 {len(chosen)}개(8개 이상)')
    if bad:
        raise RuntimeError('설계 조건 검사 실패:\n- ' + '\n- '.join(bad))
    return tot


# ───────────── 한 벌 ─────────────

def build():
    units = simulate_all()
    rec = Records(units)
    cats = {c['id']: rec.categories(c) for c in rec.cases}
    chosen = pick_check_cases(rec, cats)
    tot = design_checks(rec, cats, chosen)
    hm8 = sample('HM-8_cooler-fan-manual.md', HM8_TAGS)
    work_orders = tagged('작업지시_이력.csv', DD.work_order_text()[0], OLD_DOC_TAGS[1:])
    files = {
        'HM-8_매뉴얼.md': hm8,
        'HM-8_1.0판_매뉴얼.md': tagged('HM-8_1.0판_매뉴얼.md', DD.HM8_OLD, OLD_DOC_TAGS),
        'HI-01_보충매뉴얼.md': sample('HI-01_shift-inspection-supplement.md', HI01_TAGS),
        '작업기준.md': WORK_STANDARD,
        '판단시스템_결정표_내보내기.txt': decision_export(),
        '작업지시_이력.csv': work_orders,
        '사건_기록_HYD-02_1027.md': incident_memo(rec),
        '확인_사례.csv': check_cases_file(rec, chosen),
        'targets_sop.csv': sop_register(hm8),
        'targets.csv': TARGETS,
        'failuremodes.csv': FAILURE_MODES,
        '수집_설명.md': collection_doc(rec),
        '경보_목록.csv': rec.alarm_list(),
        'PLC_상태_수신.csv': rec.plc_file(),
        '팬_운전_카운터.csv': rec.counter_file(),
        '예측_결과.csv': rec.forecast_file(),
        '오더_현황.csv': rec.order_file(),
        'metrics/지표_정의.md': metric_doc(rec, cats),
        'metrics/업무_값.json': json.dumps(BUSINESS, ensure_ascii=False, indent=2) + '\n',
        'metrics/후보_설정.csv': table(['후보', '이름', '팬_설정_퍼센트', '부하_설정_퍼센트', '작업지시', '근본_조치'], CANDIDATE_SETTINGS),
    }
    meta = dict(
        seed=SEED, end=iso_kst(rec.end), incident=rec.incident['id'],
        cases=[dict(id=c['id'], asset=c['asset'], judge=iso_kst(c['judge']), categories=cats[c['id']], action_taken=c['alarm']['action'],
                    inputs={k: v for k, v in rec.made(c).items() if k not in ('counter',)} | {'counter': rec.made(c)['counter']},
                    order=None if c['order'] is None else dict(due_h=round(c['order']['due_h'], 1), remain=c['order']['remain'], hot=c['order']['hot']))
               for c in rec.cases],
        check_cases=[c['id'] for c in chosen],
        incident_totals={s: {k: (None if v is None else money(v)) for k, v in d.items()} for s, d in tot.items()},
        incident_sop12_recomputed=round(rec.predict(units[INCIDENT['asset']], next(x for x in rec.cases if x['incident'])['base'], 'SOP-COOL-12')[0]['values']['ts1'], 2),
    )
    return files, meta


def cypher_value(v):
    """상수 값을 instances.cypher에 적힌 꼴로(65 · false · null · 'TRIP')."""
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)):
        return format(v, 'g')
    return f"'{v}'"


def test_key(inp, op, value, unit):
    """검사 한 칸을 견줄 꼴로 — 값의 꼴(65 · 65.0 · False · 'false')과 빈 단위를 맞춘다."""
    value = value.strip("'") if isinstance(value, str) else cypher_value(value)
    return (inp, op, value, unit or None)


def current_rules(cy):
    """main 지금 판의 규칙 {id: (결정표, 결과, 감점, 검사 집합, 고르는 대상)} — 문서 적재 규칙(course_extractions.json)과 시드 규칙(instances.cypher)."""
    out = {}
    bundle = json.loads((SYS/'it/process/procsvc/course_extractions.json').read_text(encoding='utf-8'))
    for doc in bundle['payload']['documents'].values():
        for r in (doc['proposal'].get('knowledge') or {}).get('rules', []):
            out[r['id']] = (r['table'], r['effect'], r.get('penalty'),
                            {test_key(t['input'], t['operator'], t['value'], t.get('unit')) for t in r['tests']}, set(r.get('outputs') or []))
    for m in re.finditer(r"\['(rule:[a-z0-9-]+)','(dt:[a-z-]+)',\d+,'([A-Z]+)'", cy):
        end = min(i for i in (cy.find("['rule:", m.end()), cy.find('] AS r', m.end())) if i >= 0)
        tests = {test_key(t[0], t[1], t[2] if t[2].startswith("'") or t[2] in ('true', 'false') else float(t[2]), None if t[3] == 'null' else t[3].strip("'"))
                 for t in re.findall(r"\['(in:[a-z0-9-]+)','([^']+)',('[^']*'|true|false|[-\d.]+),('[^']*'|null)\]", cy[m.end():end])}
        out[m.group(1)] = (m.group(2), m.group(3), None, tests, set())
    return out


def check_mapping(now):
    """대응표를 거친 옛 규칙이 main 지금 판 규칙과 같은 뜻인지 — 결정표 · 결과 · 감점 · 검사(DROPPED_TESTS를 뺀 것) · 고르는 대상(OUTPUT_ALIAS를 거친 것).
    옛 이름 그대로 둔 규칙은 지금 판에 같은 결정표 · 결과 · 검사의 규칙이 생기지 않았는지 본다(생겼으면 대응표를 다시 본다)."""
    errs = []
    for rid, dt, _, _, effect, penalty, _, targets, _, _, tests in OLD_RULES:
        new = CURRENT_ID.get(rid, rid)
        old_tests = {test_key(*t) for t in tests}
        if new not in now:
            if new != rid:
                errs.append(f'대응표 {rid} → {new}: main 지금 판 규칙에 없습니다.')
            twins = sorted(k for k, v in now.items() if (v[0], v[1], v[3]) == (dt, effect, old_tests))
            if twins:
                errs.append(f'옛 이름으로 둔 {rid}와 결정표 · 결과 · 검사가 같은 지금 판 규칙이 있습니다({", ".join(twins)}) — 대응표를 다시 봅니다.')
            continue
        table, eff, pen, now_tests, outs = now[new]
        diff = [f'결정표 {dt} ≠ {table}'] if table != dt else []
        diff += [f'결과 {effect} ≠ {eff}'] if eff != effect else []
        diff += [f'감점 {penalty} ≠ {pen}'] if (penalty or None) != (pen or None) else []
        want_tests = old_tests - {test_key(*t) for t in DROPPED_TESTS.get(rid, [])}
        diff += [f'검사 {sorted(want_tests)} ≠ {sorted(now_tests)}'] if want_tests != now_tests else []
        if effect == 'SELECT' and {OUTPUT_ALIAS.get(t, t) for t in targets} != outs:
            diff.append(f'고르는 대상 {targets} ≠ {sorted(outs)}')
        if diff:
            errs.append(f'대응표 {rid} → {new}: ' + '; '.join(diff))
    return errs


def check_main():
    """경보 패턴이 main과, 옛 결정표 상수가 main 04efb988^ 판과, 대응표를 거친 규칙 · 결정표 ID가 main 지금 판과 같은지."""
    errs = []
    cy = (SYS/'it/neo4j/v2/instances.cypher').read_text(encoding='utf-8')
    i = cy.find("['pattern:cooler-degradation'")
    row = cy[i:cy.find("['pattern:", i + 10)] if i >= 0 else ''
    want = [f"'COOLER_DEGRADATION',{RAISE_HOLD_S},'held'", f"['in:ts1','TS1','>',{RAISE_TS1:g},'℃']", f"['in:ce','CE','<',{RAISE_CE:g},'%']",
            "['in:ts1-slope','slope(TS1)','>',0,", f"['TS1 < {CLEAR_TS1:g} and slope(TS1) <= 0',{CLEAR_HOLD_S},{SLOPE_WINDOW_S},"]
    if not row or any(w not in row for w in want):
        errs.append('main 경보 패턴(pattern:cooler-degradation)이 생성기 상수와 다릅니다.')
    for d in OLD_DECISIONS:   # 결정표 ID · 여러 규칙이 맞을 때는 지금 판에도 같다(옛 이름 그대로)
        if f"'{d[0]}','{d[3]}'" not in cy:
            errs.append(f'결정표 {d[0]}({d[3]})가 main 지금 판에 없습니다 — 대응표에 결정표 ID를 더합니다.')
    errs += check_mapping(current_rules(cy))
    try:
        old = subprocess.run(['git', 'show', '04efb988^:it/neo4j/v2/instances.cypher'], cwd=SYS, capture_output=True, text=True, check=True).stdout
        for r in OLD_RULES:
            at = old.find(f"['{r[0]}','{r[1]}',{r[2]},")
            end = old.find("\n  ['rule:", at + 1)
            tests = '[' + ','.join('[' + ','.join(cypher_value(x) for x in t) + ']' for t in r[10]) + ']'
            if at < 0 or tests not in old[at:end if end > 0 else None]:
                errs.append(f'옛 결정표 {r[0]} 행이 04efb988^ 판과 다릅니다.')
        names = json.loads((SYS/'it/portal/www/names.json').read_text(encoding='utf-8'))
        for was, now_id in OUTPUT_ALIAS.items():
            m = re.search(rf"\['{was}','([^']+)'", old)
            if not m or m.group(1) != names.get(now_id):
                errs.append(f'원인 {was}(04efb988^)와 {now_id}(지금 names.json)의 이름이 다릅니다.')
    except (OSError, subprocess.CalledProcessError):
        print('참고: git으로 04efb988^ 판을 읽지 못해 옛 결정표 대조를 건너뜁니다.')
    return errs


if __name__ == '__main__':
    import hashlib
    a, meta = build()
    if '--check' in sys.argv:
        b, _ = build()
        same = a == b
        errs = check_main()
        for name in sorted(a):
            print(f'{name}: {a[name].count(chr(10))}줄 {hashlib.sha256(a[name].encode()).hexdigest()[:12]}')
        print('두 번 생성 결과 같음' if same else '두 번 생성 결과 다름')
        for e in errs:
            print('오류:', e)
        sys.exit(0 if same and not errs else 1)
    from collections import Counter
    print(Counter(k for c in meta['cases'] for k in c['categories']))
