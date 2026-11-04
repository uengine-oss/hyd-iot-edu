"""냉각 경보 조치 판정 · 비교 — 경보마다 네 후보를 조건표로 판정하고 주어진 비교 산식으로 견주어
result.json(판단 기능) 또는 조치검토결과.json · .md(조치 검토 결과, --review)를 쓴다. 정한 것을 바꿔(--gap · --warned) 같은 기능으로 다시 돌릴 수 있다.

규칙은 코드에 적지 않고 입력 조건표(13열 계약)에서 읽는다. 원천은 실습 폴더의 자료/(경보_목록 · PLC_상태_수신 · 팬_운전_카운터 · 예측_결과 · 오더_현황 ·
targets · metrics/)다. 사용: python judge_actions.py <실습 폴더> <결과 폴더> [--table 조건표] [--sop sop.json] [--gap carry|unknown] [--warned compare|skip] [--review]

판단 입력 만들기(근거: 수집_설명.md · 작업기준.md 3 · 4절 · HI-01 SOP-HI-01 3단계):
- 판단 시각 = 경보_목록 RAISE 행의 판정_요청_시각(UTC). 현장 기록(+09:00)과 시각을 맞춰 견주고, 그 시각 뒤 기록은 쓰지 않는다.
- PLC 모드 · 상태: 판단 시각까지의 마지막 수신. 품질 bad면 값 없음(앞 수신으로 대신하지 않음), 하트비트 10초 + 유예 2초를 넘게 수신이 없으면 값 없음.
- 팬 연속 시간: 마지막 카운터 기록이 종료면 0, 시작 · 주기면 기록값 + 기록 뒤 판단 시각까지 경과(분 ÷ 60 = h) — 카운터는 행 사이에도 센다(수집_설명.md).
  주기(10분)를 넘게 기록이 없으면(끊긴 구간) 정한 것 「빈 값의 뜻」(--gap)대로 한다.
- 예측: 행 없음 · 거부 · 기준 관측 뒤 120초 지남은 값 없음(이유가 다르다). MPa는 ×10 bar.
- skill_kind · skill_code는 targets.csv의 kind · codes.
정한 것(기본값은 결과 기록 파일 「정한 것」 표의 선택):
 --gap     빈 값의 뜻(판단 입력, 끊긴 구간을 이을지) — carry = 판정 요청 때 PLC 팬 설정이 100 %면 끊긴 구간을 잇고 마지막 기록에 경과를 더한다 /
                                  unknown = 끊긴 구간을 잇지 않고 값 없음으로 둔다.
금액은 소수 둘째 자리로 사사오입한다(ROUND_HALF_UP — 입출력_계약 「결과」).
 --warned  쓰는 사람에 따라 갈리는 답(허용 후보 비교) — compare = 경고가 붙은 후보도 비교 합계로 견주어 순위에 둔다 /
                                  skip = 경고가 붙은 후보는 견주지 않고 경고 없는 후보끼리 순위를 낸다.
결과 파일의 키는 영어 snake_case다. 값의 낱말(유지 · 제외 · 보류, 사유 문장)은 한국어.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import argparse
import csv
import json

OPERATORS = {'>=', '>', '<=', '<', '==', '!=', 'has_other_than'}
NUMERIC = {'forecast_ts1', 'forecast_ps1', 'fan100_hours'}
INPUTS = ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state', 'skill_kind', 'skill_code']
RESULTS = {'WARN', 'PENALTY', 'EXCLUDE'}
BOUNDARY = {'>=': '예', '<=': '예', '>': '아니오', '<': '아니오', '==': '해당없음', '!=': '해당없음', 'has_other_than': '해당없음'}
HEARTBEAT_S, GRACE_S = 10, 2
COUNTER_PERIOD_MIN = 10
FORECAST_VALID_S = 120
KST = timezone(timedelta(hours=9))
LOSSES = ['cost', 'production', 'quality', 'energy']
LOSS_NAME = {'cost': '비용', 'production': '생산', 'quality': '품질', 'energy': '에너지'}
BASIS = ('비교값은 지표_정의.md의 네 손실(비용 · 생산 · 품질 · 에너지)과 조건표 감점의 합계(만원, 작을수록 유리)로 후보를 견주는 계산이다. '
         '포털 성과 지표의 정책 점수(성과 득실 · 예측 여유 · 선례 · 납기 긴급도 · 품질 위험을 더한 점수)와 다른 값이며, 순위는 실행 승인이 아니다.')
GAP_TEXT = {'carry': '끊긴 구간을 잇는다 — 판정 요청 때 PLC 팬 설정이 100 %면 그 사이 100 % 운전이 이어졌다고 보고 마지막 기록에 경과를 더한다',
            'unknown': '끊긴 구간을 잇지 않는다 — 그 사이 연속 운전을 확인할 수 없으므로 값 없음으로 둔다'}
WARN_TEXT = {'compare': '경고가 붙은 후보도 비교 합계로 견주어 순위에 둔다', 'skip': '경고가 붙은 후보는 견주지 않고 경고 없는 후보끼리 순위를 낸다'}
BASE_POLICY = ('carry', 'compare')          # (--gap, --warned)


class ContractError(Exception):
    pass


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def ts(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def load_table(path):
    """(rule_id, action) 묶음. 계약과 다르면 파일 · 행을 밝혀 실패한다."""
    groups = {}
    for line, row in enumerate(read_csv(path), start=2):
        where = f'{Path(path).name}:{line}'
        if row['logic'] != 'AND':
            raise ContractError(f'{where} logic은 AND만: {row["logic"]}')
        if row['operator'] not in OPERATORS or row['result'] not in RESULTS:
            raise ContractError(f'{where} 계약에 없는 연산자 · 결과: {row["operator"]} / {row["result"]}')
        if BOUNDARY[row['operator']] != row['boundary_included']:
            raise ContractError(f'{where} 경계 표시가 연산자와 다름: {row["operator"]} / {row["boundary_included"]}')
        if row['input'] not in INPUTS:
            raise ContractError(f'{where} 계약에 없는 입력 {row["input"]}')
        key = (row['rule_id'], row['action'])
        head = {k: row[k] for k in ['result', 'penalty_manwon', 'reason', 'source_section']}
        g = groups.setdefault(key, {'rule_id': key[0], 'action': key[1], **head, 'conditions': []})
        if any(g[k] != v for k, v in head.items()):
            raise ContractError(f'{where} 같은 묶음 {key}의 결과 · 감점 · 이유 · 출처가 다름')
        g['conditions'].append({'index': int(row['condition_index']), 'input': row['input'], 'operator': row['operator'], 'value': row['value'], 'unit': row['unit']})
    for g in groups.values():
        g['conditions'].sort(key=lambda c: c['index'])
        if [c['index'] for c in g['conditions']] != list(range(1, len(g['conditions']) + 1)):
            raise ContractError(f'{path} 묶음 {g["rule_id"]}/{g["action"]}의 condition_index가 1부터 차례가 아님')
    return groups


def load_targets(path):
    return {r['sop_id']: {'skill_kind': r['kind'], 'skill_code': [c for c in r['codes'].split(';') if c], 'name': r['name'], 'source_section': r['source_section']}
            for r in read_csv(path)}


# ───────────── 판단 입력 ─────────────

def fan_hours(r, age_min, fan_setting, gap_policy):
    """팬 100 % 연속 시간(h)과 값이 없을 때의 까닭. r = 판단 시각까지의 마지막 카운터 기록."""
    if r['기록_종류'] == '종료':
        return 0.0, None
    if age_min <= COUNTER_PERIOD_MIN:
        return (float(r['팬100_연속_분']) + age_min) / 60, None
    gap = f'팬 카운터 기록 끊김 — 마지막 {r["기록_종류"]} 기록 {age_min:.1f}분 전(주기 {COUNTER_PERIOD_MIN}분)'
    if gap_policy == 'carry' and fan_setting == 100.0:
        return (float(r['팬100_연속_분']) + age_min) / 60, None
    if gap_policy == 'carry':
        return None, gap + ', PLC 팬 설정으로도 100 %를 확인하지 못함'
    return None, gap + ', 그 사이 연속 운전을 확인할 수 없음'


def prepare(lab, gap_policy=BASE_POLICY[0]):
    d = Path(lab)/'자료'
    alarms = [r for r in read_csv(d/'경보_목록.csv') if r['구분'] == 'RAISE' and r['판정_요청_시각']]
    plc, counter, fc = {}, {}, {}
    for line, r in enumerate(read_csv(d/'PLC_상태_수신.csv'), start=2):
        plc.setdefault(r['설비'], []).append((ts(r['수신_시각']), line, r))
    for line, r in enumerate(read_csv(d/'팬_운전_카운터.csv'), start=2):
        counter.setdefault(r['설비'], []).append((ts(r['기록_시각']), line, r))
    for line, r in enumerate(read_csv(d/'예측_결과.csv'), start=2):
        key = (r['경보_ID'], r['후보'])
        if key in fc:
            raise ContractError(f'예측_결과.csv:{line} 같은 경보 · 후보 행이 두 번: {key}')
        fc[key] = (line, r)
    targets = load_targets(d/'targets.csv')
    out = []
    for a in alarms:
        J, asset = ts(a['판정_요청_시각']), a['설비']
        common, missing, prov = {}, {}, {}
        rows = [x for x in plc.get(asset, []) if x[0] <= J]
        fan_setting = None
        if not rows:
            reason = '판단 시각까지 PLC 상태 수신 기록 없음'
        else:
            t, line, r = max(rows, key=lambda x: (x[0], x[1]))
            age = (J - t).total_seconds()
            prov['plc'] = f'PLC_상태_수신.csv:{line} ({r["수신_시각"]}, 판단 {age:.0f}초 전)'
            if r['품질'] != 'good':
                reason = f'PLC 상태 마지막 수신({r["수신_시각"]}) 품질 {r["품질"]}'
            elif age > HEARTBEAT_S + GRACE_S:
                reason = f'PLC 상태 수신 끊김 — 마지막 수신 {age:.0f}초 전(하트비트 {HEARTBEAT_S}초 + 유예 {GRACE_S}초 넘음)'
            else:
                reason = None
                common['plc_mode'], common['plc_state'] = r['운전_모드'], r['상태']
                fan_setting = float(r['팬_설정_pct'])
        if reason:
            for k in ('plc_mode', 'plc_state'):
                common[k], missing[k] = None, reason
        rows = [x for x in counter.get(asset, []) if x[0] <= J]
        if not rows:
            common['fan100_hours'], missing['fan100_hours'] = None, '판단 시각까지 팬 카운터 기록 없음'
        else:
            t, line, r = max(rows, key=lambda x: (x[0], x[1]))
            age_min = (J - t).total_seconds() / 60
            prov['fan'] = f'팬_운전_카운터.csv:{line} ({r["기록_시각"]} {r["기록_종류"]} {r["팬100_연속_분"]}분, 판단 {age_min:.2f}분 전)'
            common['fan100_hours'], why = fan_hours(r, age_min, fan_setting, gap_policy)
            if why:
                missing['fan100_hours'] = why
        cands = []
        for sop, tg in targets.items():
            x, m, p = dict(common), dict(missing), dict(prov)
            x['skill_kind'], x['skill_code'] = tg['skill_kind'], tg['skill_code']
            hit = fc.get((a['경보_ID'], sop))
            if hit is None:
                reason = '예측 결과 행 없음(판정 서버가 예측을 받지 못함)'
            else:
                line, r = hit
                p['forecast'] = f'예측_결과.csv:{line}'
                age = (J - ts(r['기준_관측_시각'])).total_seconds()
                if r['상태'] != '완료':
                    reason = f'예측 거부 — {r["거부_사유"]}'
                elif age > FORECAST_VALID_S:
                    reason = f'예측 유효 시간 지남 — 기준 관측이 판단 {age:.0f}초 전({FORECAST_VALID_S}초 넘음)'
                else:
                    reason = None
                    scale = {'bar': 1.0, 'MPa': 10.0}.get(r['PS1_단위'])
                    if scale is None:
                        raise ContractError(f'예측_결과.csv:{line} 알 수 없는 PS1 단위 {r["PS1_단위"]}')
                    x['forecast_ts1'] = float(r['예측_TS1_C'])
                    x['forecast_ps1'] = round(float(r['예측_PS1']) * scale, 6)
            if reason:
                for k in ('forecast_ts1', 'forecast_ps1'):
                    x[k], m[k] = None, reason
            cands.append({'sop': sop, 'inputs': {k: x[k] for k in INPUTS}, 'missing_reasons': m, 'provenance': p})
        out.append({'id': a['경보_ID'], 'asset': asset, 'decision_time': a['판정_요청_시각'], 'candidates': cands})
    return out, targets


# ───────────── 판정 ─────────────

def test(c, actual):
    op, expected = c['operator'], c['value']
    if op == 'has_other_than':
        return any(code != expected for code in actual)
    if c['input'] in NUMERIC:
        a, b = float(actual), float(expected)
        return {'>=': a >= b, '>': a > b, '<=': a <= b, '<': a < b, '==': a == b, '!=': a != b}[op]
    return {'==': actual == expected, '!=': actual != expected}[op]


def evaluate(sop, inputs, groups):
    """맞은 규칙은 모두 모은다(Hit Policy 모으기). 거짓인 조건이 하나라도 있으면 그 규칙은 불일치, 아니고 값 없는 조건이 있으면 미확인."""
    out = {'sop': sop, 'warnings': [], 'penalties': [], 'exclusions': [], 'unknown': [], 'rules': []}
    for g in sorted((g for g in groups.values() if g['action'] == sop), key=lambda g: g['rule_id']):
        evidence, missing, false_found = [], [], False
        for c in g['conditions']:
            actual = inputs.get(c['input'])
            if actual is None or actual == []:
                missing.append(c['input'])
                evidence.append({'input': c['input'], 'actual': None, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit']})
                continue
            holds = test(c, actual)
            false_found = false_found or not holds
            evidence.append({'input': c['input'], 'actual': actual, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit']})
        state = '불일치' if false_found else ('미확인' if missing else '일치')
        out['rules'].append({'rule_id': g['rule_id'], 'result': g['result'], 'state': state})
        if state == '미확인':
            out['unknown'].append({'rule_id': g['rule_id'], 'result': g['result'], 'missing': missing, 'source_section': g['source_section']})
        elif state == '일치':
            hit = {'rule_id': g['rule_id'], 'reason': g['reason'], 'source_section': g['source_section'], 'conditions': evidence}
            if g['result'] == 'WARN':
                out['warnings'].append(hit)
            elif g['result'] == 'EXCLUDE':
                out['exclusions'].append(hit)
            else:
                out['penalties'].append({**hit, 'penalty_manwon': float(g['penalty_manwon'])})
    out['status'] = '제외' if out['exclusions'] else ('보류' if out['unknown'] else '유지')
    return out


# ───────────── 비교(지표_정의.md) ─────────────

def metric_inputs(lab):
    m = Path(lab)/'자료/metrics'
    data = json.loads((m/'업무_값.json').read_text(encoding='utf-8-sig'))
    values = {v['이름']: v['값'] for v in data['값']}
    works = {w['작업']: w for w in data['표준_작업']}
    settings = {r['후보']: r for r in read_csv(m/'후보_설정.csv')}
    orders = {r['경보_ID']: r for r in read_csv(Path(lab)/'자료/오더_현황.csv')}
    return values, works, settings, orders


def components(ts1, setting, values, works, order):
    """네 손실 원값. 구할 수 없는 손실은 None과 그 까닭."""
    raw, why = {}, {}
    def num(k):
        v = order.get(k, '') if order else ''
        return float(v) if v not in ('', None) else None
    period, remain, lot = num('납기까지_남은_시간_h'), num('오더_잔량_ea'), num('고온_로트_수량_ea')
    no_order = (order or {}).get('비고') or '오더 값 빈칸'
    load = float(setting['부하_설정_퍼센트']) if setting['부하_설정_퍼센트'] else 90.0
    fan = float(setting['팬_설정_퍼센트']) if setting['팬_설정_퍼센트'] else 60.0
    work = works[setting['작업지시']] if setting['작업지시'] else None
    stop, work_cost = (work['정지_시간_h'], work['작업비_만원']) if work else (0, 0)
    ratio = load / 90
    if period is None:
        for k in ('cost', 'energy'):
            raw[k], why[k] = None, f'납기까지_남은_시간_h 없음: {no_order}'
    else:
        risk = 0 if setting['근본_조치'] == '예' else values['계획_외_고장_비용'] * min(1, period / values['평균_고장_간격'])
        raw['cost'] = work_cost + risk
        raw['energy'] = (fan - 60) * values['팬_최대_추가_전력'] / 40 * period * values['전력_단가']
    if period is None or remain is None:
        raw['production'], why['production'] = None, f'납기까지_남은_시간_h · 오더_잔량_ea 없음: {no_order}'
    else:
        finish = stop + remain / (values['시간당_생산_수량'] * ratio)
        raw['production'] = values['시간당_생산_가치'] * (period * (1 - ratio) + stop) + values['납기_지연_위약금'] * max(0, finish - period)
    if lot is None or ts1 is None:
        raw['quality'] = None
        why['quality'] = (f'고온_로트_수량_ea 없음: {no_order}' if lot is None else '') + ('; ' if lot is None and ts1 is None else '') + ('forecast_ts1 없음' if ts1 is None else '')
    else:
        raw['quality'] = values['고온_로트_불량_확률'] * values['고온_로트_클레임_금액'] if ts1 >= 55 and lot > 0 else 0
    return raw, why


def r2(v):
    """금액을 소수 둘째 자리로 사사오입(ROUND_HALF_UP — 입출력_계약). 부동소수 원값의 이진 오차(11.25 + 1.575가 12.8249…로 저장됨)는 소수 아홉째 자리에서 먼저 걷어 낸다."""
    return float(Decimal(f'{v:.9f}').quantize(Decimal('0.01'), ROUND_HALF_UP)) + 0.0


def rank(cands):
    scored = sorted([c for c in cands if c.get('comparison')], key=lambda c: (c['comparison']['total'], c['sop']))
    out, prev, pos = [], None, 0
    for i, c in enumerate(scored, 1):
        if c['comparison']['total'] != prev:
            pos, prev = i, c['comparison']['total']
        out.append({'rank': pos, 'sop': c['sop'], 'total': c['comparison']['total']})
    return out


def selection(cands, ranking):
    """1위를 고른 까닭(또는 순위가 없는 까닭)과 추가로 확인할 사항."""
    by = {c['sop']: c for c in cands}
    held = [c for c in cands if c['status'] == '보류']
    skipped = [c for c in cands if c['status'] == '유지' and not c['comparison']]
    if ranking:
        top = [r['sop'] for r in ranking if r['rank'] == 1]
        reason = f'견준 후보 가운데 비교 합계가 가장 작은 후보({ranking[0]["total"]:.2f}만원)'
    else:
        top = []
        if all(c['status'] == '제외' for c in cands):
            reason = '모든 후보가 제외되어 견줄 후보가 없다(제외 규칙 ' + ', '.join(sorted({h['rule_id'] for c in cands for h in c['exclusions']})) + ')'
        elif not any(c['status'] == '유지' for c in cands):
            reason = '유지 후보가 없어 견줄 후보가 없다: ' + ', '.join(f'{c["sop"]} {c["status"]}' for c in cands)
        else:
            reason = '유지 후보를 견주지 못해 순위가 없다'
    if skipped:
        reason += '. 견주지 않은 유지 후보: ' + ', '.join(f'{c["sop"]}({"; ".join(c["no_comparison_reason"])})' for c in skipped)
    if held:
        reason += '. 보류 후보 ' + ', '.join(c['sop'] for c in held) + '는 빠진 값을 받은 뒤 다시 판정한다'
    checks = [f'{c["sop"]}: {m} — {c["missing_reasons"].get(m, "")}' for c in held for m in sorted({m for u in c['unknown'] for m in u['missing']})]
    checks += [f'{s}: 경고 {h["rule_id"]} — {h["reason"]}' for s in top for h in by[s]['warnings']]
    return {'reason': reason, 'checks': checks}


def decisions(policy):
    gap, warn = policy
    return [
        {'item': '판단 시각', 'decision': '경보_목록.csv RAISE 행의 판정_요청_시각(UTC)을 기준으로 현장 기록(+09:00)과 시각을 맞추고 그 뒤 기록은 쓰지 않는다', 'basis': '수집_설명.md 첫 문단; 작업기준.md 3절'},
        {'item': 'PLC 모드 · 상태', 'decision': f'마지막 수신. 품질 bad이거나 {HEARTBEAT_S + GRACE_S}초 넘게 수신이 없으면 값 없음', 'basis': '수집_설명.md PLC_상태_수신(하트비트 · 유예); 작업기준.md 3절; HI-01 SOP-HI-01 3단계'},
        {'item': '팬 100 % 연속 시간', 'decision': f'마지막 카운터 기록이 종료면 0, 시작 · 주기면 기록값 + 판단 시각까지 경과(분 ÷ 60). 주기({COUNTER_PERIOD_MIN}분)를 넘게 기록이 없으면 — {GAP_TEXT[gap]}',
         'basis': '수집_설명.md 팬_운전_카운터; HM-8.8 「이미 24시간을 넘겼다면」; 작업기준.md 3절'},
        {'item': '예측값', 'decision': f'행 없음 · 거부 · 기준 관측 뒤 {FORECAST_VALID_S}초 지남은 값 없음(이유를 따로 남김). MPa는 ×10 bar', 'basis': '수집_설명.md 예측_결과'},
        {'item': '견주는 후보', 'decision': f'제외 · 보류 후보는 견주지 않는다. {WARN_TEXT[warn]}', 'basis': 'HM-8.6 「다른 조치와 비교한다」; 지표_정의.md 계산 가정; 작업기준.md 4절'},
    ]


def run(lab, table=None, policy=BASE_POLICY):
    lab = Path(lab)
    table = Path(table) if table else lab/'입력/조건표.csv'
    groups = load_table(table)
    events, targets = prepare(lab, policy[0])
    values, works, settings, orders = metric_inputs(lab)
    result = {'comparison_basis': BASIS, 'decisions': decisions(policy), 'events': []}
    for e in events:
        cands = []
        for c in e['candidates']:
            j = evaluate(c['sop'], c['inputs'], groups)
            j['inputs'], j['missing_reasons'], j['provenance'] = c['inputs'], c['missing_reasons'], c['provenance']
            raw, why = components(c['inputs']['forecast_ts1'], settings[c['sop']], values, works, orders.get(e['id']))
            j['_raw'], j['comparison'] = raw, None
            if j['status'] == '유지':
                if policy[1] == 'skip' and j['warnings']:
                    j['no_comparison_reason'] = ['경고 ' + ', '.join(h['rule_id'] for h in j['warnings']) + ' — ' + WARN_TEXT['skip']]
                elif any(v is None for v in raw.values()):
                    j['no_comparison_reason'] = [f'{LOSS_NAME[k]}: {why[k]}' for k in LOSSES if raw[k] is None]
                else:
                    pen = sum(p['penalty_manwon'] for p in j['penalties'])
                    j['comparison'] = {**{k: r2(raw[k]) for k in LOSSES}, 'penalty': r2(pen), 'total': r2(sum(raw.values()) + pen)}
            cands.append(j)
        ranking = rank(cands)
        result['events'].append({'id': e['id'], 'asset': e['asset'], 'decision_time': e['decision_time'], 'candidates': cands, 'ranking': ranking,
                                 'selection': selection(cands, ranking)})
    return result


def student_view(result):
    """결과 계약 꼴(엔진 안쪽 칸 rules · provenance · _raw를 뺀다)."""
    out = json.loads(json.dumps(result, ensure_ascii=False, default=str))
    for e in out['events']:
        for c in e['candidates']:
            for k in ('rules', 'provenance', '_raw'):
                c.pop(k, None)
    return out


# ───────────── 실전반 조치 검토 결과 ─────────────
KIND = {'WARN': '경고', 'PENALTY': '감점', 'EXCLUDE': '제외', '미확인': '미확인'}
APPROVAL_NOTE = '비교 순위는 승인 요청을 검토할 순서일 뿐 실행 승인이 아니다. 실행은 이 역할이 한 번 승인한 뒤에 한다.'


def expr(c):
    return f'{c["input"]} {c["operator"]} {c["value"]}' + (f' {c["unit"]}' if c['unit'] else '')


def review(result, sop_doc, groups):
    sops = {s['id']: s for s in sop_doc['sops']}
    items = []
    for e in result['events']:
        cands, ranks = [], {r['sop']: r['rank'] for r in e['ranking']}
        for c in e['candidates']:
            reasons = []
            for kind, key in (('WARN', 'warnings'), ('PENALTY', 'penalties'), ('EXCLUDE', 'exclusions')):
                for h in c[key]:
                    reasons.append({'rule_id': h['rule_id'], 'result': kind, 'actual_inputs': {x['input']: x['actual'] for x in h['conditions']},
                                    'expression': ' AND '.join(expr(x) for x in h['conditions']), 'source': h['source_section']})
            for u in c['unknown']:
                g = groups[(u['rule_id'], c['sop'])]
                reasons.append({'rule_id': u['rule_id'], 'result': '미확인', 'actual_inputs': {x['input']: c['inputs'][x['input']] for x in g['conditions']},
                                'expression': ' AND '.join(expr(x) for x in g['conditions']), 'source': u['source_section'], 'missing_inputs': u['missing'],
                                'missing_reason': '; '.join(sorted({c['missing_reasons'].get(m, '') for m in u['missing']} - {''}))})
            s = sops[c['sop']]
            checks = [f'{m}: {c["missing_reasons"].get(m, "")} — 원천에서 다시 받는다' for m in sorted({m for u in c['unknown'] for m in u['missing']})]
            if c['status'] == '유지':
                checks += [f'실행 전 확인: {x["text"]} ({x["source"]})' for x in s['apply_conditions']] + [f'완료 기준: {x["text"]} ({x["source"]})' for x in s['completion']]
            cands.append({'sop': c['sop'], 'status': c['status'], 'inputs': c['inputs'], 'missing_reasons': c['missing_reasons'], 'reasons': reasons,
                          'sources': sorted({r['source'] for r in reasons} | {s['source']}), 'checks': checks,
                          'comparison': c['comparison'], **({'no_comparison_reason': c['no_comparison_reason']} if c.get('no_comparison_reason') else {}),
                          'rank': ranks.get(c['sop']), 'approval': {'role': s['approval']['role'], 'source': s['approval']['source'], 'note': APPROVAL_NOTE}})
        sel = e['selection']
        items.append({'id': e['id'], 'asset': e['asset'], 'decision_time': e['decision_time'], 'candidates': cands,
                      'review': {'top': [r['sop'] for r in e['ranking'] if r['rank'] == 1], 'reason': sel['reason'], 'checks': sel['checks']}})
    return {'comparison_basis': result['comparison_basis'], 'decisions': result['decisions'], 'events': items}


def review_md(rv):
    lines = ['# 조치 검토 결과', '', rv['comparison_basis'], '']
    for it in rv['events']:
        op = it['review']
        lines += [f'## {it["id"]} — {it["asset"]} (판단 {ts(it["decision_time"]).astimezone(KST):%Y-%m-%d %H:%M:%S} +09:00)', '',
                  '- 검토 의견: ' + (', '.join(op['top']) + ' 승인 요청 검토(비교 순위 1위)' if op['top'] else '승인 요청을 검토할 후보 없음') + f' — {op["reason"]}',
                  '- 먼저 확인할 값: ' + ('; '.join(op['checks']) or '없음'), '',
                  '| 후보 | 판정 | 이유(규칙 · 결과 · 비교) | 비교 합계 · 순위 | 승인 역할 | 추가로 확인할 값 |', '|---|---|---|---|---|---|']
        for c in it['candidates']:
            why = '<br>'.join(f'{r["rule_id"]} {KIND[r["result"]]} {r["expression"]}' for r in c['reasons']) or '맞은 규칙 없음'
            val = f'{c["comparison"]["total"]:.2f} · {c["rank"]}위' if c['comparison'] else ('견주지 않음: ' + '; '.join(c['no_comparison_reason']) if c.get('no_comparison_reason') else '—')
            lines.append(f'| {c["sop"]} | {c["status"]} | {why} | {val} | {c["approval"]["role"]} ({c["approval"]["source"]}) | {"<br>".join(c["checks"]) or "—"} |')
        lines.append('')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description='조건표로 경보마다 후보를 판정하고 견준다.')
    ap.add_argument('lab', help='실습 폴더(입력/ · 자료/가 있는 곳)')
    ap.add_argument('out', help='결과를 쓸 폴더')
    ap.add_argument('--table', help='조건표(기본: <실습 폴더>/입력/조건표.csv)')
    ap.add_argument('--sop', help='SOP 구조(기본: <실습 폴더>/입력/sop.json) — --review에서 승인 역할 · 실행 전 확인을 읽는다')
    ap.add_argument('--gap', choices=sorted(GAP_TEXT), default=BASE_POLICY[0], help=('빈 값의 뜻 — 팬 카운터 기록이 끊긴 구간: ' + ' / '.join(f'{k} = {v}' for k, v in GAP_TEXT.items())).replace('%', '%%'))
    ap.add_argument('--warned', choices=sorted(WARN_TEXT), default=BASE_POLICY[1], help=('쓰는 사람에 따라 갈리는 답 — 경고가 붙은 후보: ' + ' / '.join(f'{k} = {v}' for k, v in WARN_TEXT.items())).replace('%', '%%'))
    ap.add_argument('--review', action='store_true', help='조치검토결과.json · .md를 쓴다(없으면 result.json)')
    a = ap.parse_args(argv)
    lab, out = Path(a.lab), Path(a.out)
    table = Path(a.table) if a.table else lab/'입력/조건표.csv'
    res = run(lab, table, (a.gap, a.warned))
    out.mkdir(parents=True, exist_ok=True)
    if a.review:
        sop = json.loads((Path(a.sop) if a.sop else lab/'입력/sop.json').read_text(encoding='utf-8-sig'))
        rv = review(res, sop, load_table(table))
        (out/'조치검토결과.json').write_text(json.dumps(rv, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        (out/'조치검토결과.md').write_text(review_md(rv), encoding='utf-8')
        print(f'사례 {len(rv["events"])}건 → {out/"조치검토결과.json"} · {out/"조치검토결과.md"}')
    else:
        (out/'result.json').write_text(json.dumps(student_view(res), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'사례 {len(res["events"])}건 → {out/"result.json"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
