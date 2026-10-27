"""강사 참조 판정·비교 구현. 학생 ZIP에 넣지 않는다.

사용: python judge.py <랩 폴더> <출력 result.json>
랩 폴더의 입력/rules.csv, 자료/targets.csv, 자료/cases.csv, 자료/metrics/* 를 읽는다.
규칙은 코드에 고정하지 않고 조건표에서 읽는다.
"""
from pathlib import Path
import csv
import json
import sys

OPERATORS = {'>=', '>', '<=', '<', '==', '!=', 'has_other_than'}
NUMERIC = {'forecast_ts1', 'forecast_ps1', 'fan100_hours'}
LIST_INPUTS = {'skill_code'}
RESULTS = {'WARN', 'PENALTY', 'EXCLUDE'}
BOUNDARY = {'>=': '예', '<=': '예', '>': '아니오', '<': '아니오', '==': '해당없음', '!=': '해당없음', 'has_other_than': '해당없음'}
KIND_MAP = {'control': 'control', 'workorder': 'work_order'}
STATE_MAP = {'RUN': 'RUNNING', 'RUNNING': 'RUNNING', 'TRIP': 'TRIP'}


class ContractError(Exception):
    pass


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


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


def blank(value):
    return value is None or (isinstance(value, str) and value.strip() == '')


def number(value, where):
    if blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ContractError(f'{where} 숫자가 아닌 값: {value!r}')


def test(condition, actual):
    op, expected = condition['operator'], condition['value']
    if op == 'has_other_than':
        return any(code != expected for code in actual)
    if condition['input'] in NUMERIC:
        a, b = float(actual), float(expected)
        return {'>=': a >= b, '>': a > b, '<=': a <= b, '<': a < b, '==': a == b, '!=': a != b}[op]
    return {'==': actual == expected, '!=': actual != expected}[op]


def evaluate(sop, inputs, groups):
    """후보 하나. 적용 대상(action)인 규칙만 평가. 알려진 거짓이 있으면 불일치, 아니면 누락 시 미확인."""
    out = {'sop': sop, 'status': None, 'warnings': [], 'penalties': [], 'exclusions': [], 'unknown': [], 'rules': []}
    applicable = [g for g in groups.values() if g['action'] == sop]
    if not applicable:
        raise ContractError(f'조건표에 후보 {sop}의 규칙이 없음')
    for g in sorted(applicable, key=lambda g: g['rule_id']):
        evidence, missing, false_found = [], [], False
        for c in g['conditions']:
            actual = inputs.get(c['input'])
            if c['input'] not in inputs:
                raise ContractError(f'규칙 {g["rule_id"]}/{sop}의 입력 {c["input"]}을 사례 입력에서 만들 수 없음')
            if blank(actual) or actual == []:
                missing.append(c['input'])
                evidence.append({'input': c['input'], 'actual': None, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit'], 'holds': None})
                continue
            holds = test(c, actual)
            false_found = false_found or not holds
            evidence.append({'input': c['input'], 'actual': actual, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit'], 'holds': holds})
        state = '불일치' if false_found else ('미확인' if missing else '일치')
        item = {'rule_id': g['rule_id'], 'result': g['result'], 'state': state, 'reason': g['reason'], 'source_section': g['source_section'], 'conditions': evidence}
        out['rules'].append(item)
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


def metric_values(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    values = {v['이름']: v['값'] for v in data['값']}
    works = {w['작업']: w for w in data['표준_작업']}
    return values, works


def compare(candidate, forecast_ts1, setting, values, works):
    """지표_정의.md의 교육용 네 손실. 필요한 값이 없으면 계산 불가."""
    period = values['납기까지_남은_시간']
    load = float(setting['부하_설정_퍼센트']) if setting['부하_설정_퍼센트'] else 90.0
    fan = float(setting['팬_설정_퍼센트']) if setting['팬_설정_퍼센트'] else 60.0
    work = works[setting['작업지시']] if setting['작업지시'] else None
    stop = work['정지_시간_h'] if work else 0
    work_cost = work['작업비_만원'] if work else 0
    if forecast_ts1 is None:
        return None, ['forecast_ts1(품질 손실 계산에 필요)']
    ratio = load / 90
    risk = 0 if setting['근본_조치'] == '예' else values['계획_외_고장_비용'] * min(1, period / values['평균_고장_간격'])
    cost = work_cost + risk
    finish = stop + values['오더_잔량'] / (values['시간당_생산_수량'] * ratio)
    production = values['시간당_생산_가치'] * (period * (1 - ratio) + stop) + values['납기_지연_위약금'] * max(0, finish - period)
    quality = values['고온_로트_불량_확률'] * values['고온_로트_클레임_금액'] if forecast_ts1 >= 55 and values['고온_로트_수량'] > 0 else 0
    energy = (fan - 60) * values['팬_최대_추가_전력'] / 40 * period * values['전력_단가']
    penalty = sum(p['amount_만원'] for p in candidate['penalties'])
    total = cost + production + quality + energy + penalty
    r = lambda x: round(x + 0.0, 2)
    return {'비용': r(cost), '생산': r(production), '품질': r(quality), '에너지': r(energy), '감점': r(penalty), '합계': r(total), '완료까지_h': r(finish)}, []


def rank(candidates):
    scored = sorted([c for c in candidates if c['status'] == '유지' and c.get('comparison')], key=lambda c: c['comparison']['합계'])
    ranking, previous, position = [], None, 0
    for i, c in enumerate(scored, start=1):
        if c['comparison']['합계'] != previous:
            position, previous = i, c['comparison']['합계']
        ranking.append({'rank': position, 'sop': c['sop'], '합계': c['comparison']['합계']})
    return ranking


def case_inputs(row, target):
    return {'forecast_ts1': row['forecast_ts1_C'], 'forecast_ps1': row['forecast_ps1_bar'], 'plc_mode': row['plc_mode'], 'plc_state': row['plc_state'], 'fan100_hours': row['fan100_hours'], **target}


def normalize(inputs, where):
    out = dict(inputs)
    for k in NUMERIC:
        out[k] = number(out.get(k), f'{where} {k}')
    for k in ['plc_mode', 'plc_state']:
        out[k] = None if blank(out.get(k)) else out[k]
    if out['plc_state'] is not None:
        if out['plc_state'] not in STATE_MAP:
            raise ContractError(f'{where} 알 수 없는 plc_state: {out["plc_state"]}')
        out['plc_state'] = STATE_MAP[out['plc_state']]
    return out


def run(lab):
    lab = Path(lab)
    groups = load_rules(lab/'입력/rules.csv')
    targets = load_targets(lab/'자료/targets.csv')
    values, works = metric_values(lab/'자료/metrics/업무_값.json')
    settings = {r['후보']: r for r in read_csv(lab/'자료/metrics/후보_설정.csv')}
    result = {'rules_file': '입력/rules.csv', 'comparison_basis': '교육용 네 손실(비용·생산·품질·에너지)과 규칙 감점의 합계, 단위 만원, 작을수록 유리. HYD 일곱 성분 정책 점수가 아니다.', 'cases': [], 'requests': []}
    for line, row in enumerate(read_csv(lab/'자료/cases.csv'), start=2):
        where = f'자료/cases.csv:{line}'
        cands = []
        for sop in row['candidate_sops'].split(';'):
            if sop not in targets:
                raise ContractError(f'{where} targets.csv에 없는 후보 {sop}')
            inputs = normalize(case_inputs(row, targets[sop]), where)
            cands.append(evaluate(sop, inputs, groups))
        allowed = [c['sop'] for c in cands if c['status'] == '유지']
        entry = {'id': row['case'], 'candidates': cands, 'allowed': allowed}
        if not allowed:
            entry['no_allowed_reason'] = no_allowed_reason(cands)
        result['cases'].append(entry)
    requests = json.loads((lab/'자료/metrics/판정_요청.json').read_text(encoding='utf-8-sig'))
    for request in requests['요청']:
        where = f'자료/metrics/판정_요청.json {request["번호"]}'
        cands = []
        for cand in request['후보']:
            sop = cand['sop']
            inputs = normalize({'forecast_ts1': cand.get('forecast_ts1'), 'forecast_ps1': cand.get('forecast_ps1'), 'plc_mode': request.get('plc_mode'), 'plc_state': request.get('plc_state'), 'fan100_hours': request.get('fan100_hours'), **targets[sop]}, where)
            judged = evaluate(sop, inputs, groups)
            if judged['status'] == '유지':
                judged['comparison'], missing = compare(judged, inputs['forecast_ts1'], settings[sop], values, works)
                if missing:
                    judged['comparison_unavailable'] = missing
            else:
                judged['comparison'] = None
            cands.append(judged)
        ranking = rank(cands)
        top = [r['sop'] for r in ranking if r['rank'] == 1]
        held = [c['sop'] for c in cands if c['status'] == '보류']
        if top:
            reason = '비교 합계가 가장 작은 유지 후보' + (f'. 보류 후보 {", ".join(held)}는 누락 값을 확인한 뒤 다시 비교' if held else '')
        else:
            reason = no_allowed_reason(cands)
        result['requests'].append({'id': request['번호'], 'plc_mode': request.get('plc_mode'), 'plc_state': STATE_MAP.get(request.get('plc_state')), 'fan100_hours': request.get('fan100_hours'), 'candidates': cands, 'ranking': ranking, 'recommendation': {'sops': top, 'reason': reason, 'held': held}})
    return result


def no_allowed_reason(cands):
    if all(c['status'] == '제외' for c in cands):
        return '모든 후보가 제외되어 추천 없음'
    return '유지 후보 없음: ' + ', '.join(f'{c["sop"]} {c["status"]}' for c in cands)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('사용: python judge.py <랩 폴더> <출력 result.json>')
    out = run(sys.argv[1])
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'사례 {len(out["cases"])}건, 요청 {len(out["requests"])}건 → {sys.argv[2]}')
