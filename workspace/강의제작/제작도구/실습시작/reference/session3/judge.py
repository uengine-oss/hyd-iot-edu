"""강사 참조 판정·비교 구현(현업화 판). 학생 ZIP에 넣지 않는다.

사용: python judge.py <랩 폴더> <출력 result.json> [--counter recorded|elapsed] [--rules 경로]
랩 폴더의 입력/rules.csv(또는 --rules), 자료/의 원천 다섯(경보_목록·PLC_상태_수신·팬_운전_카운터·예측_결과·오더_현황),
자료/targets.csv, 자료/metrics/(업무_값·후보_설정)을 읽는다. 규칙은 코드에 고정하지 않고 조건표에서 읽는다.

판단 입력 만들기(강사 주 갈래, 근거는 수집_설명.md·HI-01 SOP-HI-01·작업기준.md 3절):
- PLC 모드·상태: 판단 시각 이전 마지막 수신. 품질 bad면 없음(앞 수신으로 대신하지 않음), 12초 넘게 수신이 없으면 없음.
- 팬 연속 시간: 판단 시각 이전 마지막 카운터 기록. 종료면 0. 시작·주기인데 12분 넘게 새 기록이 없으면 없음.
  counter=recorded(주 갈래): 기록값 그대로. counter=elapsed: 기록값 + 마지막 기록 뒤 경과 분. 분 → h는 60으로 나눈다.
- 예측: 행 없음(수신 실패)·거부·기준 관측 뒤 120초 지남은 없음. MPa는 ×10 bar.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import argparse
import csv
import json

OPERATORS = {'>=', '>', '<=', '<', '==', '!=', 'has_other_than'}
NUMERIC = {'forecast_ts1', 'forecast_ps1', 'fan100_hours'}
RESULTS = {'WARN', 'PENALTY', 'EXCLUDE'}
BOUNDARY = {'>=': '예', '<=': '예', '>': '아니오', '<': '아니오', '==': '해당없음', '!=': '해당없음', 'has_other_than': '해당없음'}
KIND_MAP = {'control': 'control', 'workorder': 'work_order'}
STATUS_LIMIT_S = 12
COUNTER_LIMIT_MIN = 12
FORECAST_VALID_S = 120
BASIS = '교육용 네 손실(비용·생산·품질·에너지)과 규칙 감점의 합계, 단위 만원, 작을수록 유리. HYD 일곱 성분 정책 점수가 아니며 순위는 실행 승인이 아니다.'


class ContractError(Exception):
    pass


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def ts(text):
    return datetime.fromisoformat(text)


def load_rules(path):
    """(rule_id, action) 묶음. 묶음 안의 결과·감점·이유·출처가 다르면 좌표와 함께 실패."""
    groups = {}
    for line, row in enumerate(read_csv(path), start=2):
        where = f'{path}:{line}'
        if row['logic'] != 'AND':
            raise ContractError(f'{where} logic은 AND만 허용: {row["logic"]}')
        if row['operator'] not in OPERATORS:
            raise ContractError(f'{where} 알 수 없는 연산자: {row["operator"]}')
        if row['result'] not in RESULTS:
            raise ContractError(f'{where} 알 수 없는 결과: {row["result"]}')
        if BOUNDARY[row['operator']] != row['boundary_included']:
            raise ContractError(f'{where} 경계 포함 표시가 연산자와 다름: {row["operator"]} / {row["boundary_included"]}')
        key = (row['rule_id'], row['action'])
        head = {k: row[k] for k in ['result', 'penalty_만원', 'reason', 'source_section']}
        group = groups.setdefault(key, {'rule_id': key[0], 'action': key[1], **head, 'conditions': []})
        for k, v in head.items():
            if group[k] != v:
                raise ContractError(f'{where} 같은 규칙 묶음 {key}의 {k}가 다름')
        if row['result'] == 'PENALTY' and not row['penalty_만원']:
            raise ContractError(f'{where} PENALTY에 감점 금액 없음')
        group['conditions'].append({'index': int(row['condition_index']), 'input': row['input'], 'operator': row['operator'], 'value': row['value'], 'unit': row['unit']})
    for group in groups.values():
        group['conditions'].sort(key=lambda c: c['index'])
        indexes = [c['index'] for c in group['conditions']]
        if indexes != list(range(1, len(indexes) + 1)):
            raise ContractError(f'{path} 규칙 {group["rule_id"]}/{group["action"]}의 condition_index가 1부터 연속이 아님: {indexes}')
    return groups


def load_targets(path):
    targets = {}
    for line, row in enumerate(read_csv(path), start=2):
        if row['kind'] not in KIND_MAP:
            raise ContractError(f'{path}:{line} 알 수 없는 kind: {row["kind"]}')
        targets[row['sop_id']] = {'skill_kind': KIND_MAP[row['kind']], 'skill_code': [c for c in row['codes'].split(';') if c], 'name': row['name'], 'source_section': row['source_section']}
    return targets


# ───────────── 판단 입력 만들기 ─────────────

def prepare(lab, counter='recorded'):
    if counter not in ('recorded', 'elapsed'):
        raise ContractError(f'counter는 recorded·elapsed: {counter}')
    d = Path(lab)/'자료'
    alarms = read_csv(d/'경보_목록.csv')
    status = {}
    for line, r in enumerate(read_csv(d/'PLC_상태_수신.csv'), start=2):
        status.setdefault(r['설비'], []).append((ts(r['수신_시각']), line, r))
    counters = {}
    for line, r in enumerate(read_csv(d/'팬_운전_카운터.csv'), start=2):
        counters.setdefault(r['설비'], []).append((ts(r['기록_시각']), line, r))
    fc = {}
    for line, r in enumerate(read_csv(d/'예측_결과.csv'), start=2):
        key = (r['사례'], r['후보'])
        if key in fc:
            raise ContractError(f'예측_결과.csv:{line} 같은 사례·후보 행이 두 번: {key}')
        fc[key] = (line, r)
    out = []
    for a in alarms:
        T, asset = ts(a['판단_시각']), a['설비']
        common, missing, prov = {}, {}, {}
        # PLC 상태
        rows = [x for x in status.get(asset, []) if x[0] <= T]
        if not rows:
            reason = 'PLC 상태 수신 기록 없음'
            for k in ['plc_mode', 'plc_state']:
                common[k], missing[k] = None, reason
        else:
            t, line, r = max(rows, key=lambda x: (x[0], x[1]))
            age = (T - t).total_seconds()
            prov['plc'] = f'PLC_상태_수신.csv:{line} ({r["수신_시각"]}, 판단 {age:.0f}초 전)'
            if r['품질'] != 'good':
                reason = f'PLC 상태 마지막 수신 품질 {r["품질"]}({r["수신_시각"]})'
            elif age > STATUS_LIMIT_S:
                reason = f'PLC 상태 수신 끊김(마지막 수신 {age:.0f}초 전 > {STATUS_LIMIT_S}초)'
            else:
                reason = None
            if reason:
                for k in ['plc_mode', 'plc_state']:
                    common[k], missing[k] = None, reason
            else:
                common['plc_mode'] = r['운전_모드']
                common['plc_state'] = {'RUN': 'RUNNING', 'TRIP': 'TRIP'}[r['상태']]
        # 팬 카운터
        rows = [x for x in counters.get(asset, []) if x[0] <= T]
        if not rows:
            common['fan100_hours'], missing['fan100_hours'] = None, '팬 카운터 기록 없음'
        else:
            t, line, r = max(rows, key=lambda x: (x[0], x[1]))
            age_min = (T - t).total_seconds() / 60
            prov['fan'] = f'팬_운전_카운터.csv:{line} ({r["기록_시각"]} {r["팬100_연속_분"]}분 {r["기록_종류"]}, 판단 {age_min:.1f}분 전)'
            if r['기록_종류'] == '종료':
                common['fan100_hours'] = 0.0
            elif age_min > COUNTER_LIMIT_MIN:
                common['fan100_hours'], missing['fan100_hours'] = None, f'팬 카운터 수집 끊김(마지막 {r["기록_종류"]} 기록 {age_min:.1f}분 전 > {COUNTER_LIMIT_MIN}분)'
            else:
                minutes = float(r['팬100_연속_분']) + (age_min if counter == 'elapsed' else 0.0)
                common['fan100_hours'] = minutes / 60
        cands = []
        for sop in a['후보'].split(';'):
            x, m, p = dict(common), dict(missing), dict(prov)
            hit = fc.get((a['사례'], sop))
            if hit is None:
                reason = '예측 결과 수신 실패(예측_결과.csv에 행 없음)'
            else:
                line, r = hit
                p['forecast'] = f'예측_결과.csv:{line}'
                age = (T - ts(r['기준_관측_시각'])).total_seconds()
                if r['상태'] != '완료':
                    reason = f'예측 거부: {r["거부_사유"]}'
                elif age > FORECAST_VALID_S:
                    reason = f'예측 유효 시간 지남(기준 관측 {age:.0f}초 전 > {FORECAST_VALID_S}초)'
                else:
                    reason = None
                    scale = {'bar': 1.0, 'MPa': 10.0}.get(r['PS1_단위'])
                    if scale is None:
                        raise ContractError(f'예측_결과.csv:{line} 알 수 없는 PS1 단위 {r["PS1_단위"]}')
                    x['forecast_ts1'] = float(r['예측_TS1_C'])
                    x['forecast_ps1'] = float(r['예측_PS1']) * scale
            if reason:
                for k in ['forecast_ts1', 'forecast_ps1']:
                    x[k], m[k] = None, reason
            cands.append({'sop': sop, 'inputs': x, 'missing_reasons': m, 'provenance': p})
        out.append({'id': a['사례'], 'asset': asset, 'decision_time': a['판단_시각'], 'candidates': cands})
    return out


# ───────────── 판정 ─────────────

def blank(value):
    return value is None or (isinstance(value, str) and value.strip() == '') or value == []


def test(condition, actual):
    op, expected = condition['operator'], condition['value']
    if op == 'has_other_than':
        return any(code != expected for code in actual)
    if condition['input'] in NUMERIC:
        a, b = float(actual), float(expected)
        return {'>=': a >= b, '>': a > b, '<=': a <= b, '<': a < b, '==': a == b, '!=': a != b}[op]
    return {'==': actual == expected, '!=': actual != expected}[op]


def evaluate(sop, inputs, groups):
    out = {'sop': sop, 'status': None, 'warnings': [], 'penalties': [], 'exclusions': [], 'unknown': [], 'rules': []}
    applicable = [g for g in groups.values() if g['action'] == sop]
    if not applicable:
        raise ContractError(f'조건표에 후보 {sop}의 규칙이 없음')
    for g in sorted(applicable, key=lambda g: g['rule_id']):
        evidence, missing, false_found = [], [], False
        for c in g['conditions']:
            if c['input'] not in inputs:
                raise ContractError(f'규칙 {g["rule_id"]}/{sop}의 입력 {c["input"]}을 만들 수 없음')
            actual = inputs[c['input']]
            if blank(actual):
                missing.append(c['input'])
                evidence.append({'input': c['input'], 'actual': None, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit'], 'holds': None})
                continue
            holds = test(c, actual)
            false_found = false_found or not holds
            evidence.append({'input': c['input'], 'actual': actual, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit'], 'holds': holds})
        state = '불일치' if false_found else ('미확인' if missing else '일치')
        out['rules'].append({'rule_id': g['rule_id'], 'result': g['result'], 'state': state, 'reason': g['reason'], 'source_section': g['source_section'], 'conditions': evidence})
        if state == '미확인':
            out['unknown'].append({'rule_id': g['rule_id'], 'result': g['result'], 'missing': missing, 'source_section': g['source_section']})
        elif state == '일치':
            hit = {'rule_id': g['rule_id'], 'reason': g['reason'], 'source_section': g['source_section'], 'conditions': evidence}
            if g['result'] == 'WARN':
                out['warnings'].append(hit)
            elif g['result'] == 'EXCLUDE':
                out['exclusions'].append(hit)
            else:
                out['penalties'].append({**hit, 'amount_만원': float(g['penalty_만원'])})
    out['status'] = '제외' if out['exclusions'] else ('보류' if out['unknown'] else '유지')
    return out


# ───────────── 교육용 비교 ─────────────

def metric_inputs(lab):
    m = Path(lab)/'자료/metrics'
    data = json.loads((m/'업무_값.json').read_text(encoding='utf-8-sig'))
    values = {v['이름']: v['값'] for v in data['값']}
    works = {w['작업']: w for w in data['표준_작업']}
    settings = {r['후보']: r for r in read_csv(m/'후보_설정.csv')}
    orders = {r['사례']: r for r in read_csv(Path(lab)/'자료/오더_현황.csv')}
    return values, works, settings, orders


def compare(candidate, forecast_ts1, setting, values, works, order):
    need = {'납기까지_남은_시간_h': '기간', '오더_잔량_ea': '오더 잔량', '고온_로트_수량_ea': '고온 로트 수량'}
    lost = [f'{k}({v}) 없음: {order.get("비고") or "오더 값 빈칸"}' for k, v in need.items() if blank(order.get(k))]
    if forecast_ts1 is None:
        lost.append('forecast_ts1(품질 손실 계산에 필요)')
    if lost:
        return None, lost
    period, remain, lot = float(order['납기까지_남은_시간_h']), float(order['오더_잔량_ea']), float(order['고온_로트_수량_ea'])
    load = float(setting['부하_설정_퍼센트']) if setting['부하_설정_퍼센트'] else 90.0
    fan = float(setting['팬_설정_퍼센트']) if setting['팬_설정_퍼센트'] else 60.0
    work = works[setting['작업지시']] if setting['작업지시'] else None
    stop = work['정지_시간_h'] if work else 0
    work_cost = work['작업비_만원'] if work else 0
    ratio = load / 90
    risk = 0 if setting['근본_조치'] == '예' else values['계획_외_고장_비용'] * min(1, period / values['평균_고장_간격'])
    cost = work_cost + risk
    finish = stop + remain / (values['시간당_생산_수량'] * ratio)
    production = values['시간당_생산_가치'] * (period * (1 - ratio) + stop) + values['납기_지연_위약금'] * max(0, finish - period)
    quality = values['고온_로트_불량_확률'] * values['고온_로트_클레임_금액'] if forecast_ts1 >= 55 and lot > 0 else 0
    energy = (fan - 60) * values['팬_최대_추가_전력'] / 40 * period * values['전력_단가']
    penalty = sum(p['amount_만원'] for p in candidate['penalties'])
    r = lambda v: round(v + 0.0, 2)
    return {'비용': r(cost), '생산': r(production), '품질': r(quality), '에너지': r(energy), '감점': r(penalty), '합계': r(cost + production + quality + energy + penalty)}, []


def rank(candidates):
    scored = sorted([c for c in candidates if c['status'] == '유지' and c.get('comparison')], key=lambda c: c['comparison']['합계'])
    ranking, previous, position = [], None, 0
    for i, c in enumerate(scored, start=1):
        if c['comparison']['합계'] != previous:
            position, previous = i, c['comparison']['합계']
        ranking.append({'rank': position, 'sop': c['sop'], '합계': c['comparison']['합계']})
    return ranking


def no_allowed_reason(cands):
    if all(c['status'] == '제외' for c in cands):
        rules = sorted({h['rule_id'] for c in cands for h in c['exclusions']})
        return f'모든 후보가 제외되어 추천 없음(제외 규칙 {", ".join(rules)})'
    if not any(c['status'] == '유지' for c in cands):
        return '유지 후보 없음: ' + ', '.join(f'{c["sop"]} {c["status"]}' for c in cands)
    return '유지 후보의 비교값을 계산할 수 없어 추천 없음: ' + '; '.join(f'{c["sop"]} {", ".join(c.get("comparison_unavailable") or [])}' for c in cands if c['status'] == '유지')


def run(lab, rules_path=None, counter='recorded'):
    lab = Path(lab)
    rules_path = Path(rules_path) if rules_path else lab/'입력/rules.csv'
    groups = load_rules(rules_path)
    targets = load_targets(lab/'자료/targets.csv')
    values, works, settings, orders = metric_inputs(lab)
    result = {'rules_file': str(rules_path.name), 'counter_mode': counter, 'comparison_basis': BASIS,
              'input_decisions': [
                  {'항목': 'PLC 모드·상태', '결정': f'판단 시각 이전 마지막 수신. 품질 bad 또는 {STATUS_LIMIT_S}초 넘게 수신 없음이면 값 없음', '근거': '수집_설명.md PLC_상태_수신; HI-01 SOP-HI-01 3단계'},
                  {'항목': '팬 100 % 연속 시간', '결정': ('마지막 카운터 기록값 그대로(분 ÷ 60)' if counter == 'recorded' else '마지막 카운터 기록값 + 기록 뒤 경과 분(분 ÷ 60)') + f'. 종료면 0, 시작·주기 뒤 {COUNTER_LIMIT_MIN}분 넘게 기록 없으면 값 없음', '근거': '수집_설명.md 팬_운전_카운터; 작업기준.md 3절'},
                  {'항목': '예측값', '결정': f'행 없음·거부·기준 관측 뒤 {FORECAST_VALID_S}초 지남은 값 없음. MPa는 ×10 bar', '근거': '수집_설명.md 예측_결과'}],
              'events': []}
    for e in prepare(lab, counter):
        cands = []
        for c in e['candidates']:
            if c['sop'] not in targets:
                raise ContractError(f'경보_목록.csv {e["id"]}: targets.csv에 없는 후보 {c["sop"]}')
            inputs = {**c['inputs'], 'skill_kind': targets[c['sop']]['skill_kind'], 'skill_code': targets[c['sop']]['skill_code']}
            judged = evaluate(c['sop'], inputs, groups)
            judged['inputs'] = inputs
            judged['missing_reasons'] = c['missing_reasons']
            judged['provenance'] = c['provenance']
            judged['comparison'] = None
            if judged['status'] == '유지':
                judged['comparison'], lost = compare(judged, inputs['forecast_ts1'], settings[c['sop']], values, works, orders[e['id']])
                if lost:
                    judged['comparison_unavailable'] = lost
            cands.append(judged)
        ranking = rank(cands)
        top = [r['sop'] for r in ranking if r['rank'] == 1]
        held = [c['sop'] for c in cands if c['status'] == '보류']
        if top:
            reason = '교육용 비교 합계가 가장 작은 유지 후보' + (f'. 보류 후보 {", ".join(held)}는 빠진 값을 확인한 뒤 다시 비교' if held else '')
        else:
            reason = no_allowed_reason(cands)
        result['events'].append({'id': e['id'], 'asset': e['asset'], 'decision_time': e['decision_time'], 'candidates': cands, 'ranking': ranking, 'recommendation': {'sops': top, 'reason': reason, 'held': held}})
    return result


def strip(result):
    """학생 계약 형식으로 줄임(강사 내부 필드 rules·provenance 제외)."""
    out = json.loads(json.dumps(result, ensure_ascii=False))
    for e in out['events']:
        for c in e['candidates']:
            c.pop('rules', None)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('lab'); ap.add_argument('out')
    ap.add_argument('--counter', default='recorded'); ap.add_argument('--rules')
    a = ap.parse_args()
    out = run(a.lab, a.rules, a.counter)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(strip(out), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'사례 {len(out["events"])}건 → {a.out}')
