"""강사 참조 — 통합반 03회차 실습2(조치 기준)와 실전반 02회차 실습5(조치 조건표)의 갈래별 답. 학생 폴더 · ZIP에 넣지 않는다.

정할 것(구성안 4절)
- 지점1 적용 범위(통합 03-2): 가 = HYD-01~03에만 건다(HYD-04는 뺐음 — 수냉식 후속형, HM-8에 범위 문장 없음)
                               나 = HYD-04에도 냉각 성능 판정 · SOP-COOL-13(4단계 확인 필요) · SOP-COOL-15를 건다
- 지점2 현행 원문에 근거가 없는 옛 규칙 rule:ts1-hard · rule:trip-reset-only(두 반):
        가 = 옛 시스템이 건 그대로(대상 빈칸 = 네 후보) 제외 / 나 = 설명 문장대로 제어 후보(11~13)에만 / 다 = 옮기지 않음
판정 랩 입력(강사 검증 판) = 지점1 가 · 지점2 가. 지점2 가는 옛 규칙의 대상 빈칸(모든 후보)을 그대로 옮겨 작업지시 후보에도 R4 · R5를 걸므로,
그 행의 이유 칸이 그 어긋남(설명 문장은 제어 후보 · PLC 명령을 말함)을 밝힌다.
sop.json의 키는 영어 snake_case다(코딩랩.md K-55) — 값(원문 문장 · 역할 이름)은 한국어.

규칙 ID와 뜻(run_reference.py의 두 번째 구현이 이 뜻으로만 견준다 — 조건표 파일을 읽지 않는다):
R1 auto(원격 자동 아님 제외) · R2 fan24(팬 24시간 초과 감점 20) · R3 warn55(예측 55 이상 경고) · R4 hard65(예측 65 이상 제외) · R5 trip(트립 중 리셋 외 제외).
옮기지 않는 원문 조건: 펌프 부하 60 % 미만 금지(후보 설정이 모두 70 % 이상이고 계약 입력에 부하가 없다), 팬 100 % 연속 24시간 이내(SOP-COOL-11 단계 2 — 제한, 넘긴 경우의 처리는 R2).
승인은 원문 줄 그대로(APPROVAL): 승인 줄이 없는 SOP-FAN-11 · 12는 미확인, SOP-COOL-13은 SOP 승인 줄(운전원)과 4단계가 거는 작업지시의 승인(HM-8.7 설비보전팀장)을 함께 적는다.
고장 유형 → 근본 조치(REMEDIED_BY)는 원인을 없애는 절차만 — 점검만 하는 SOP-FAN-11은 원인(팬 구동 불량)을 확인하는 ADDRESSES로만 잇는다.
"""
from __future__ import annotations

import csv
import io
import json

HEADER = ['rule_id', 'action', 'condition_index', 'logic', 'input', 'operator', 'value', 'unit', 'boundary_included', 'result', 'penalty_manwon', 'reason', 'source_section']
BOUNDARY = {'>=': '예', '<=': '예', '>': '아니오', '<': '아니오', '==': '해당없음', '!=': '해당없음', 'has_other_than': '해당없음'}
P1, P2 = ('가', '나'), ('가', '나', '다')
BASE = ('가', '가')                         # 판정 랩 입력 갈래
REMOTE = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13']
FOUR = REMOTE + ['SOP-COOL-14']
SEMANTIC = {'R1': 'auto', 'R2': 'fan24', 'R3': 'warn55', 'R4': 'hard65', 'R5': 'trip'}
OLD_SOURCE = {'R4': '판단 시스템 결정표 rule:ts1-hard; 출처 ks:sr-04(설비안전규정 SR-04) 원문 미확인',
              'R5': '판단 시스템 결정표 rule:trip-reset-only; 출처 HM-9.4 원문 미확인(1.0판 · 1.1판에 없음)'}


def scope(p2):
    """지점2 갈래에서 R4 · R5를 거는 후보."""
    return {'가': FOUR, '나': REMOTE, '다': []}[p2]


WORK_ORDER = {'SOP-COOL-14'}
MISMATCH = {'R4': ' 옛 설명 문장은 제어 후보만 말하므로 작업지시 후보에는 맞지 않는다',
            'R5': ' 작업지시는 PLC 제어 명령이 아니어서 이 이유와 맞지 않는다'}


def hard_reason(rid, base, p2):
    """지점2 갈래별 R4 · R5 이유 — 작업지시 후보에 건 가 갈래는 그 어긋남을 이유 칸에 밝힌다(원문 미확인)."""
    if p2 == '가':
        return lambda a: base + ' — 옛 판단 시스템이 대상 빈칸(모든 후보)으로 건 그대로' + (' 작업지시 후보에도 건다.' + MISMATCH[rid] if a in WORK_ORDER else '')
    return lambda a: base + ' — 옛 규칙 설명 문장대로 제어 후보에만'


def rules(p2):
    """[(rule_id, actions, conditions[(input, op, value, unit)], result, penalty, reason(action→문자열), source(action→문자열))]."""
    step = {'SOP-COOL-11': 3, 'SOP-COOL-12': 4, 'SOP-COOL-13': 3}
    out = [
        ('R1', REMOTE, [('skill_kind', '==', 'control', ''), ('plc_mode', '!=', 'REMOTE_AUTO', '')], 'EXCLUDE', '',
         lambda a: '원격 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 한다', lambda a: 'HM-8.5; HM-8.8'),
        ('R2', ['SOP-COOL-11', 'SOP-COOL-12'], [('fan100_hours', '>', '24', 'h')], 'PENALTY', '20',
         lambda a: '팬 100 % 연속 운전이 24시간을 넘었으면 팬 수명 손실로 감점해 비교한다', lambda a: 'HM-8.8'),
        ('R3', REMOTE, [('forecast_ts1', '>=', '55', '℃')], 'WARN', '',
         lambda a: '조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있어 다른 조치와 비교한다', lambda a: f'HM-8.6; HM-8.5 {a} 단계 {step[a]}'),
    ]
    if p2 != '다':
        out += [('R4', scope(p2), [('forecast_ts1', '>=', '65', '℃')], 'EXCLUDE', '', hard_reason('R4', '예측 유온이 인터록 한계 이상이면 제외', p2), lambda a: OLD_SOURCE['R4']),
                ('R5', scope(p2), [('plc_state', '==', 'TRIP', ''), ('skill_code', 'has_other_than', 'RESET', '')], 'EXCLUDE', '',
                 hard_reason('R5', '트립 중에는 PLC가 리셋 외 제어 명령을 거부한다', p2), lambda a: OLD_SOURCE['R5'])]
    return out


def table_rows(p2):
    rows = []
    for rid, actions, conds, result, pen, reason, src in rules(p2):
        for a in actions:
            for i, (inp, op, val, unit) in enumerate(conds, 1):
                rows.append(dict(zip(HEADER, [rid, a, str(i), 'AND', inp, op, val, unit, BOUNDARY[op], result, pen, reason(a), src(a)])))
    return rows


def table_csv(p2):
    buf = io.StringIO()
    w = csv.DictWriter(buf, HEADER, lineterminator='\n')
    w.writeheader()
    w.writerows(table_rows(p2))
    return buf.getvalue()


# ───────────── SOP 구조 ─────────────
SOPS = [  # id, 이름, 종류, 실행코드, 출처, 단계[(문장, 출처)]
    ('SOP-FAN-11', '쿨러 팬 점검 절차', None, [], 'HM-8.1', [   # 내보내기 「스킬」 절에 없는 절차 — 종류 · 코드 없음(계약)
        '설비를 정지하고 현장 패널에서 LOCAL로 전환한다.', '벨트 처짐을 측정한다 (기준 10~15 mm).', '베어링 소음과 표면 온도를 확인한다 (60 ℃ 이하).',
        '재가동 후 VS1이 0.9 mm/s 아래로 내려왔는지 확인한다.']),
    ('SOP-FAN-12', '벨트 교체 절차', None, [], 'HM-8.2', [
        'LOCAL 전환과 잠금(LOTO)을 확인한다.', '구 벨트를 분리하고 풀리 정렬을 점검한다.', '새 벨트를 걸고 처짐을 12 mm로 맞춘다.',
        '30분 시운전 뒤 냉각 효율 CE가 80 % 이상인지 확인한다.']),
    ('SOP-COOL-11', '팬 최대 운전', 'control', ['FAN_SET'], 'HM-8.5', [
        'PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', '팬 속도를 100 %로 올린다. 100 % 연속 운전은 24시간 이내로 한다.', '15분 재관측으로 HM-8.6 회복 판정을 한다.']),
    ('SOP-COOL-12', '팬 최대 운전과 부하 80 %', 'control', ['FAN_SET', 'LOAD_SET'], 'HM-8.5', [
        'PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', '팬 속도를 100 %로 올린다.', '펌프 부하를 80 %로 낮춘다.', '15분 재관측으로 HM-8.6 회복 판정을 한다.']),
    ('SOP-COOL-13', '부하 70 %와 야간 핀 세척', 'control', ['LOAD_SET', 'WO_CREATE'], 'HM-8.5', [
        'PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', '펌프 부하를 70 %로 낮춘다. 팬 속도는 그대로 둔다.', '15분 재관측으로 HM-8.6 회복 판정을 한다.',
        '야간 예정된 정비 시간에 SOP-COOL-14 핀 세척 작업지시를 건다.']),
    ('SOP-COOL-14', '쿨러 핀 세척', 'work_order', ['WO_CREATE'], 'HM-8.7', [
        '설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.', '압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.',
        '재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.']),
    ('SOP-COOL-15', '캐비닛 환기 보강', 'work_order', ['WO_CREATE'], 'HM-8.7', [
        '캐비닛 온도 TS4와 외기 온도를 기록한다.', '환기 필터를 청소하고 배기 팬 동작을 점검한다.', '캐비닛 온도가 35 ℃ 아래로 내려왔는지 확인한다.']),
]
CAUSES = [
    {'id': 'cause:cooler-fin-fouling', 'name': '쿨러 핀 오염', 'source': 'HM-8.4'},
    {'id': 'cause:ambient-temperature-rise', 'name': '주변 온도 상승', 'source': 'HM-8.4'},
    {'id': 'cause:fan-drive-fault', 'name': '팬 구동 불량', 'source': 'HM-8.4'},
]
RELATIONS = ([{'type': 'MITIGATED_BY', 'from': 'fm:cooler-cooling-loss', 'to': s, 'source': 'HM-8.5'} for s in REMOTE]
             + [{'type': 'REMEDIED_BY', 'from': 'fm:cooler-cooling-loss', 'to': s, 'source': src} for s, src in
                [('SOP-COOL-14', 'HM-8.7'), ('SOP-COOL-15', 'HM-8.7'), ('SOP-FAN-12', 'HM-8.4; HM-8.2')]]
             + [{'type': 'ADDRESSES', 'from': s, 'to': c, 'source': src} for s, c, src in
                [('SOP-COOL-14', 'cause:cooler-fin-fouling', 'HM-8.4; HM-8.7'), ('SOP-COOL-15', 'cause:ambient-temperature-rise', 'HM-8.4; HM-8.7'),
                 ('SOP-FAN-11', 'cause:fan-drive-fault', 'HM-8.4; HM-8.1'), ('SOP-FAN-12', 'cause:fan-drive-fault', 'HM-8.4; HM-8.2')]])
# 승인 — 원문 줄 그대로. (역할, sop.json 출처(절 · 단계), 원문 줄[(자료/HM-8_매뉴얼.md 줄 번호, 그 줄에 있어야 할 글)]) — 줄은 run_reference.py 1절이 확인한다.
NO_APPROVAL = '절에 승인 줄이 없음(설비보전팀장 승인 문장은 HM-8.7 근본 조치 절의 것)'
APPROVAL = {
    'SOP-FAN-11': ('미확인 — HM-8.1 SOP-FAN-11 ' + NO_APPROVAL, 'HM-8.1', []),
    'SOP-FAN-12': ('미확인 — HM-8.2 SOP-FAN-12 ' + NO_APPROVAL, 'HM-8.2', []),
    'SOP-COOL-11': ('운전원', 'HM-8.5 SOP-COOL-11 승인', [(52, '승인: 운전원')]),
    'SOP-COOL-12': ('운전원', 'HM-8.5 SOP-COOL-12 승인', [(60, '승인: 운전원')]),
    'SOP-COOL-13': ('운전원(조치) · 설비보전팀장(4단계 SOP-COOL-14 작업지시)', 'HM-8.5 SOP-COOL-13 승인; HM-8.5 SOP-COOL-13 단계 4; HM-8.7',
                    [(68, '승인: 운전원'), (66, 'SOP-COOL-14 핀 세척 작업지시'), (74, '승인은 설비보전팀장')]),
    'SOP-COOL-14': ('설비보전팀장', 'HM-8.7', [(74, '승인은 설비보전팀장')]),
    'SOP-COOL-15': ('설비보전팀장', 'HM-8.7', [(74, '승인은 설비보전팀장')]),
}


def approval_cite(sid):
    """승인 근거(파일 · 줄) — 판단 기록의 「승인 근거」 칸."""
    role, section, lines = APPROVAL[sid]
    if not lines:
        return f'`자료/HM-8_매뉴얼.md` {section} — 승인 줄 없음'
    return '`자료/HM-8_매뉴얼.md` ' + ' · '.join(str(n) for n, _ in lines) + '줄'
# 설비 모델 ID(입력/graph.json). 지점1 가 = HYD-01~03, 나 = HYD-04를 SOP-COOL-13 · 15에 더 건다.
MODEL = {   # SOP → (구성 요소 꼬리, 센서 꼬리)
    'SOP-FAN-11': (['fan'], ['VS1']), 'SOP-FAN-12': (['fan'], ['CE', 'VS1']),
    'SOP-COOL-11': (['cooler', 'fan'], ['TS1', 'CE', 'FanSpeedSP']), 'SOP-COOL-12': (['cooler', 'fan'], ['TS1', 'CE', 'FanSpeedSP', 'LoadSP']),
    'SOP-COOL-13': (['cooler'], ['TS1', 'CE', 'LoadSP']), 'SOP-COOL-14': (['cooler'], ['CE']), 'SOP-COOL-15': (['cabinet'], ['TS4']),
}
HYD04_ON = {'SOP-COOL-13', 'SOP-COOL-15'}
NOT_MODEL = ('HYD-05 · HYD-06(DPU-30, 다른 제조사 — 유온 태그 T_OIL · 한계 70 ℃, 냉각 효율 · 설정값 태그 없음)과 HYD-07(쿨러 · 통신 없음)은 '
             '모델에 이 조치를 판정 · 확인할 센서가 없어 걸지 않음')


def model_ref(sop, p1):
    comps, sensors = MODEL[sop]
    assets = ['HYD-01', 'HYD-02', 'HYD-03']
    if p1 == '나' and sop in HYD04_ON:
        assets = assets + ['HYD-04']
    ref = {'assets': list(assets), 'components': [f'{a}:{c}' for c in comps for a in assets], 'sensors': [f'{a}:{s}' for s in sensors for a in assets]}
    if p1 == '가':
        note = 'HYD-04는 뺐음 — HPP-45A 후속형이지만 냉각 장치가 수냉식 열교환기이고 HM-8에 적용 범위 문장이 없음. ' + NOT_MODEL
    elif sop in HYD04_ON:
        note = ('HYD-04에도 걺 — 같은 제조사 후속형, 모델에 HYD-04:TS1 · CE · LoadSP · TS4가 있음'
                + ('. 4단계 핀 세척은 확인 필요 — 수냉식이라 핀 세척 대상 아님' if sop == 'SOP-COOL-13' else '') + '. ' + NOT_MODEL)
    else:
        note = 'HYD-04는 뺐음 — 냉각 장치가 수냉식 열교환기라 팬 · 핀이 없음(모델에 HYD-04:fan · FanSpeedSP · VS1 없음). ' + NOT_MODEL
    ref['not_linked'] = note
    return ref


def item(text, source, rules=(), kind=None):
    return ({'type': kind} if kind else {}) | {'text': text, 'source': source, 'rules': list(rules)}


def sop_doc(p1, p2):
    hard = set(scope(p2))
    out = []
    for sid, name, kind, codes, section, steps in SOPS:
        apply_, forbid, done = [], [], []
        if sid in REMOTE:
            apply_.append(item('PLC 운전 모드가 REMOTE_AUTO일 때만 원격 조치를 한다.', f'HM-8.5; HM-8.5 {sid} 단계 1', ['R1']))
            forbid.append(item('원격 조치는 REMOTE_AUTO가 아닐 때 쓰지 않는다. 현장 수동 조작이 들어와 REMOTE_MANUAL이면 원격 조치를 내리지 않는다.', 'HM-8.5; HM-8.8', ['R1'], '금지'))
            forbid.append(item('펌프 부하를 60 % 미만으로 설정하지 않는다(최소 부하 인터록).', 'HM-8.5; HM-8.8', [], '제한'))
            done.append(item('조치 뒤 15분 동안 TS1이 55 ℃ 미만이고 경보가 해제된 상태가 유지되면 완화 성공, 회복하지 않으면 결과 보고에 미달로 적는다. '
                             '조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있으므로 다른 조치와 비교한다.', 'HM-8.6', ['R3']))
        if sid == 'SOP-COOL-11':
            forbid.append(item('팬 100 % 연속 운전은 24시간 이내로 한다.', 'HM-8.5 SOP-COOL-11 단계 2', [], '제한'))
        if sid in ('SOP-COOL-11', 'SOP-COOL-12'):
            forbid.append(item('팬 100 % 연속 운전이 이미 24시간을 넘었으면 팬 수명 손실로 20만 원을 감점해 비교한다.', 'HM-8.8', ['R2'], '제한'))
        if sid in hard:
            note = '(옛 판단 시스템이 대상 빈칸으로 건 그대로 — 작업지시는 제어 명령이 아님)' if sid in WORK_ORDER else ''
            forbid.append(item('조치 후 예측 유온이 65 ℃ 이상이면 이 후보를 쓰지 않는다.' + note, OLD_SOURCE['R4'], ['R4'], '금지'))
            forbid.append(item('PLC가 트립 상태이면 리셋 외 명령을 내리지 않는다.' + note, OLD_SOURCE['R5'], ['R5'], '금지'))
        if sid == 'SOP-COOL-14':
            apply_.append(item('완화에 성공해도 남은 원인이 쿨러 핀 오염일 때 원인에 맞는 근본 조치로 CMMS 작업지시를 발행한다.', 'HM-8.7; HM-8.4'))
            forbid.append(item('세척에 고압수는 쓰지 않는다.', 'HM-8.7 SOP-COOL-14 단계 2', [], '제한'))
            done.append(item('재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔다.', 'HM-8.7 SOP-COOL-14 단계 3'))
        if sid == 'SOP-COOL-15':
            apply_.append(item('원인이 주변 온도 상승(최근 2분 캐비닛 온도 TS4 평균 35 ℃ 이상)일 때 근본 조치로 CMMS 작업지시를 발행한다.', 'HM-8.7; HM-8.4'))
            done.append(item('캐비닛 온도가 35 ℃ 아래로 내려왔다.', 'HM-8.7 SOP-COOL-15 단계 3'))
        if sid == 'SOP-FAN-11':
            apply_.append(item('팬 지시값은 정상인데 냉각 효율이 떨어지고 진동 VS1이 0.9 mm/s를 넘을 때(최근 2분 VS1 평균 0.9 mm/s 이상이면 이 점검으로 넘어간다).', 'HM-8.1; HM-8.4'))
            done.append(item('재가동 후 VS1이 0.9 mm/s 아래로 내려왔다.', 'HM-8.1 SOP-FAN-11 단계 4'))
        if sid == 'SOP-FAN-12':
            apply_.append(item('벨트 처짐이 기준을 벗어나거나 균열이 보일 때.', 'HM-8.2'))
            forbid.append(item('LOCAL 전환과 잠금(LOTO)을 확인한 뒤 작업한다.', 'HM-8.2 SOP-FAN-12 단계 1', [], '제한'))
            done.append(item('30분 시운전 뒤 냉각 효율 CE가 80 % 이상이다.', 'HM-8.2 SOP-FAN-12 단계 4'))
        approval = {'role': APPROVAL[sid][0], 'source': APPROVAL[sid][1]}
        out.append({'id': sid, 'name': name, 'kind': kind, 'codes': codes, 'source': section, 'failure_mode': 'fm:cooler-cooling-loss',
                    'model_refs': model_ref(sid, p1), 'apply_conditions': apply_, 'prohibitions': forbid,
                    'steps': [{'order': i, 'text': t, 'source': f'{section} {sid} 단계 {i}'} for i, t in enumerate(steps, 1)],
                    'completion': done, 'approval': approval})
    return {'document': {'id': 'HM-8', 'revision': '1.1', 'file': '자료/HM-8_매뉴얼.md'},
            'failure_modes': [{'id': 'fm:cooler-cooling-loss', 'name': '쿨러 냉각 성능 상실', 'source': 'HM-8.3; HM-8.4'}],
            'causes': CAUSES, 'sops': out, 'relations': RELATIONS}


def sop_json(p1, p2):
    return json.dumps(sop_doc(p1, p2), ensure_ascii=False, indent=2) + '\n'


# ───────────── 판단 시스템 결정표 내보내기 행마다 처리(통합 03-2 요구사항의 대조 표) ─────────────
def export_treatment(p2):
    hard = {'가': ('옮김', '옛 시스템이 대상 빈칸(모든 후보)으로 건 그대로 네 후보에 제외로, 출처는 옛 규칙 ID와 원문 미확인'),
            '나': ('고침', '설명 문장(「모든 제어 후보」 · 「제어 명령」)대로 원격 제어 후보 SOP-COOL-11~13에만, 출처는 옛 규칙 ID와 원문 미확인'),
            '다': ('뺌', '제공 원문(HM-8 1.1 · 1.0)에서 근거 문장을 찾지 못해 옮기지 않음 — 인터록 문장(HM-8.3)은 설비 정지 기준이고 후보 제외 규칙이 아님')}[p2]
    return [
        ['rule:ts1-hard', hard[0], hard[1], '내보내기 16행 출처 ks:sr-04(원문 없음); HM-8_매뉴얼.md HM-8.3 인터록 65 ℃ 이상'],
        ['rule:pr07-approved-supplier-only', '뺌', '구매 규정(PR-07) · 펌프 씰 작업지시 — 냉각 계통 밖', '내보내기 17행 대상 skill:wo-pump-seal'],
        ['rule:rank-value', '뺌', '순위 규칙(dt:rank-actions) — 경고 · 감점 · 제외 조건이 아님, 판정 실습의 비교 산식과 다른 계산', '내보내기 18행'],
        ['rule:hm-8-4-fouling-diagnosis', '뺌', '원인 판정(dt:diagnose-cause) — 조건표가 아니라 sop.json의 causes · ADDRESSES로 반영(현행 HM-8.4)', '내보내기 19행 출처 HM-7.3 → 1.0판 HM-7.4 · 1.1판 HM-8.4'],
        ['rule:pm-pump-leakage-seal-wear-first', '뺌', '펌프 계통 원인 판정', '내보내기 20행 출처 HM-5.2'],
        ['rule:dx-fan', '뺌', '원인 판정 — 현행 HM-8.4의 팬 구동 불량(VS1 기준)은 causes로 반영', '내보내기 21행 출처 HM-8.1(1.0판 체계 밖)'],
        ['rule:cand-cooler', '뺌', '후보 선택 — relations(MITIGATED_BY · REMEDIED_BY)로 반영, 스킬 ID는 단계 문장으로 SOP-COOL-01~05 → 11~15에 대응',
         '내보내기 22행 · 스킬 절; HM-8_1.0판_매뉴얼.md SOP-COOL-01~05; HM-8_매뉴얼.md HM-8.5 · 8.7'],
        ['rule:cand-pump', '뺌', '펌프 계통 후보 선택', '내보내기 23행 출처 HM-5.2'],
        ['rule:cand-fan', '뺌', '「팬 베어링 열화」는 회사 고장 유형 목록에 없음 — 현행 원문은 팬 구동 불량을 냉각 성능 상실의 원인으로 두고 SOP-FAN-11 · 12로 잇는다',
         '내보내기 24행; failuremodes.csv; HM-8_매뉴얼.md HM-8.4'],
        ['rule:cand-trip', '뺌', '냉각 후 리셋 절차(SOP-TRIP-01)와 출처 HM-9.4가 제공 원문에 없음', '내보내기 25행'],
        ['rule:cand-trip-fm', '뺌', '위와 같음', '내보내기 26행'],
        ['rule:no-pressure-raise', '뺌', '펌프 계통(압력 설정 상향)', '내보내기 27행 출처 HM-5.4'],
        ['rule:hm-8-8-remote-auto-only', '옮김', 'R1 — 원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO에서만, 출처를 현행 절로', '내보내기 28행 출처 HM-3.2 → HM-8_매뉴얼.md HM-8.5 · HM-8.8'],
        ['rule:standby', '뺌', '펌프 계통(예비 펌프)', '내보내기 29행'],
        ['rule:cooler-forecast-temperature-warning', '고침', 'R3 — 옛 판은 팬 최대만 대상이고 1.0판 HM-7.5에 예측 문장이 없음, 현행 HM-8.6을 단계에서 가리키는 SOP-COOL-11~13에 건다',
         '내보내기 30행; HM-8_1.0판_매뉴얼.md HM-7.5; HM-8_매뉴얼.md HM-8.6 · HM-8.5 단계'],
        ['rule:ps1-warn', '뺌', '토출 압력 조건 · 펌프 장(HM-5.2) — 냉각 계통 조치 원문에 없는 다른 계통 조건', '내보내기 31행'],
        ['rule:hm-8-8-fan-life-penalty', '옮김', 'R2 — 「넘으면」은 초과, 팬을 최대로 올리는 두 조치(SOP-COOL-11 · 12)에 감점 20만 원', '내보내기 32행 출처 HM-7.3 → HM-8_매뉴얼.md HM-8.8'],
        ['rule:trip-reset-only', hard[0], hard[1], '내보내기 33행 출처 HM-9.4(1.0판에 HM-9.1 · 9.2뿐, 1.1판에 없음)'],
    ]


def asset_scope(p1):
    on4 = p1 == '나'
    return [
        ['HYD-01 · 02 · 03', '걸었음', '같은 모델 HPP-45A(설비 대장), 모델에 cooler · fan · cabinet과 TS1 · CE · FanSpeedSP · LoadSP · VS1 · TS4가 있음'],
        ['HYD-04', '걸었음(SOP-COOL-13 · 15만)' if on4 else '뺐음',
         ('같은 제조사 후속형 HPP-45B, 모델에 HYD-04:TS1 · CE · LoadSP · TS4 — 팬이 없어 11 · 12는 못 걸고, 13의 4단계(핀 세척)와 14는 수냉식이라 맞지 않아 확인 필요'
          if on4 else 'HPP-45A 후속형이지만 수냉식 열교환기(설비 대장 비고), 모델에 fan · FanSpeedSP · VS1 없음, 작업 이력의 냉각 정비는 냉각수측 스케일 제거 — HM-8에 적용 범위 문장 없음')],
        ['HYD-05 · 06', '뺐음', '다른 제조사 DPU-30, 유온 태그 T_OIL(한계 70 ℃)이고 냉각 효율 · 설정값 태그가 없어 HM-8.3 판정 · 완료 기준을 잴 수 없음'],
        ['HYD-07', '뺐음', '이동식 예비 파워팩 — 쿨러 · 통신 없음(모델에 cooler 없음)'],
    ]


def md_table(head, rows):
    return '\n'.join(['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)] + ['| ' + ' | '.join(str(x) for x in r) + ' |' for r in rows])
