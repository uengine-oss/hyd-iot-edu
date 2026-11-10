"""냉각 경보 조치 판정 · 비교의 제공 흐름(일반 로직). 고치지 않는다.

원천 네 개(경보 · PLC 상태 · 팬 카운터 · 예측)에서 판단 입력을 `data/collection_notes.md`의 기록 방식대로 만들고, 조건표로 판정하고(condition_tools),
`data/metrics/metric_definitions.md`의 식으로 견주어 결과 계약 꼴로 쓴다. 사람마다 갈릴 수 있는 두 자리는 학생이 채우는 빈 틀 파일의 함수를 부른다:
- `app/features/gap_rule.py` fan_hours_when_gap(ctx): 팬 카운터의 정해진 주기 기록이 판정 요청 전에 끊긴 경보의 팬 100 % 연속 시간
- `app/features/compare_rule.py` choose_compared(kept): 유지 후보 가운데 비교 산식으로 견주지 않을 후보와 그 까닭
고른 것의 글은 `app/features/decisions.csv`에서 읽어 결과의 `decisions` · `comparison_basis`에 옮긴다. 이 파일은 그 두 자리의 답을 갖지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from types import SimpleNamespace
import csv
import importlib.util
import io
import json

from app.utils.condition_tools import ContractError, INPUTS, csv_body, evaluate, load_table, load_targets, read_csv, write_text

HEARTBEAT_S, GRACE_S = 10, 2          # collection_notes.md 게이트웨이 설정표
COUNTER_PERIOD_MIN = 10               # collection_notes.md 팬 카운터 「주기」
FORECAST_VALID_S = 120                # collection_notes.md 예측 서비스 설정
KST = timezone(timedelta(hours=9))
LOSSES = ['cost', 'production', 'quality', 'energy']
LOSS_NAME = {'cost': '비용', 'production': '생산', 'quality': '품질', 'energy': '에너지'}
POINT_GAP, POINT_WARN, POINT_BASIS = '빈 값의 뜻', '쓰는 사람에 따라 갈리는 답', '비교 기준 문장'
CHOICE_HEADER = ['지점', '고른_것', '근거', '바뀌는_답']


class Unfilled(Exception):
    """빈 틀이 아직 비어 있음 — 파일 · 함수 · 칸을 밝힌다."""


def ts(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def pick(root, name):
    """app/features/criteria/에 같은 이름 파일이 있으면 그것, 없으면 data/criteria/."""
    mine = Path(root)/'app/features/criteria'/name
    return mine if mine.is_file() else Path(root)/'data/criteria'/name


# ───────────── 빈 틀 읽기 ─────────────
GAP_FILE, COMPARE_FILE = 'app/features/gap_rule.py', 'app/features/compare_rule.py'


def load_function(root, rel, name):
    """빈 틀 파일의 함수 하나. 아직 채우지 않았으면(NotImplementedError가 남음) Unfilled."""
    path = Path(root)/rel
    if not path.is_file():
        raise Unfilled(f'{rel}가 없습니다(받은 ZIP의 빈 틀을 되살립니다)')
    if 'NotImplementedError' in path.read_text(encoding='utf-8-sig'):
        raise Unfilled(f'{rel}의 {name}이 아직 비어 있습니다')
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, name, None)
    if not callable(fn):
        raise Unfilled(f'{rel}에 함수 {name}이 없습니다')
    return fn


def load_choices(root):
    """app/features/decisions.csv → {지점: 행}. 이 랩의 세 지점 행이 모두 있어야 한다."""
    path = Path(root)/'app/features/decisions.csv'
    if not path.is_file():
        return {}
    body, skip = csv_body(path)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != CHOICE_HEADER:
        raise ContractError(f'app/features/decisions.csv:{skip + 1} 열 이름이 {",".join(CHOICE_HEADER)}가 아님')
    rows = []
    for line, r in enumerate(reader, start=skip + 2):
        if None in r or any(v is None for v in r.values()):
            raise ContractError(f'app/features/decisions.csv:{line} 칸 수가 열 이름과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        rows.append(r)
    out = {}
    for r in rows:
        for point in (POINT_GAP, POINT_WARN, POINT_BASIS):
            if r['지점'].strip().startswith(point):
                out[point] = r
    return out


def choice_text(choices, point):
    r = choices.get(point)
    if r is None:
        raise Unfilled(f'app/features/decisions.csv에 지점 칸이 「{point}」(으)로 시작하는 줄이 아직 없습니다 — 지점 칸은 AGENTS.md에 적힌 지점 이름 그대로')
    if not r['고른_것'].strip():
        raise Unfilled(f'app/features/decisions.csv에 「{point}」 행의 고른_것이 비어 있습니다')
    return r['고른_것'].strip()


# ───────────── 판단 입력 ─────────────
def call_gap(fn, ctx):
    got = fn(ctx)
    if not (isinstance(got, tuple) and len(got) == 2):
        raise ContractError(f'app/features/gap_rule.py:{fn.__code__.co_firstlineno} fan_hours_when_gap({ctx.alarm_id})이 (값, 까닭) 두 칸을 돌려주지 않음: {got!r}')
    hours, why = got
    if hours is None:
        if not (isinstance(why, str) and why.strip()):
            raise ContractError(f'app/features/gap_rule.py:{fn.__code__.co_firstlineno} fan_hours_when_gap({ctx.alarm_id}): 값이 None이면 까닭 글이 있어야 함')
        return None, why.strip()
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours < 0:
        raise ContractError(f'app/features/gap_rule.py:{fn.__code__.co_firstlineno} fan_hours_when_gap({ctx.alarm_id}): 값은 0 이상의 숫자(h) 또는 None: {hours!r}')
    return float(hours), None


def prepare(lab, gap_fn):
    """경보마다 후보의 판단 입력 일곱 개와 값이 없는 까닭, 근거 줄(provenance). gap_fn = 카운터 끊김 때 부를 함수."""
    d = Path(lab)/'data'
    alarms = [r for r in read_csv(d/'alarms.csv') if r['구분'] == 'RAISE' and r['판정_요청_시각']]
    plc, counter, fc = {}, {}, {}
    for line, r in enumerate(read_csv(d/'plc_status.csv'), start=2):
        plc.setdefault(r['설비'], []).append((ts(r['수신_시각']), line, r))
    for line, r in enumerate(read_csv(d/'fan_counter.csv'), start=2):
        counter.setdefault(r['설비'], []).append((ts(r['기록_시각']), line, r))
    for line, r in enumerate(read_csv(d/'forecasts.csv'), start=2):
        key = (r['경보_ID'], r['후보'])
        if key in fc:
            raise ContractError(f'forecasts.csv:{line} 같은 경보 · 후보 행이 두 번: {key}')
        fc[key] = (line, r)
    targets = load_targets(d/'targets.csv')
    out = []
    for a in alarms:
        J, asset = ts(a['판정_요청_시각']), a['설비']
        common, missing, prov = {}, {}, {}
        rows = [x for x in plc.get(asset, []) if x[0] <= J]
        plc_last, plc_reason = None, None
        if not rows:
            plc_reason = '판단 시각까지 PLC 상태 수신 기록 없음'
        else:
            t, line, r = max(rows, key=lambda x: (x[0], x[1]))
            plc_last = {**r, '줄': line}
            age = (J - t).total_seconds()
            prov['plc'] = f'plc_status.csv:{line} ({r["수신_시각"]}, 판단 {age:.0f}초 전)'
            if r['품질'] != 'good':
                plc_reason = f'PLC 상태 마지막 수신({r["수신_시각"]}) 품질 {r["품질"]}'
            elif age > HEARTBEAT_S + GRACE_S:
                plc_reason = f'PLC 상태 수신 끊김 — 마지막 수신 {age:.0f}초 전(하트비트 {HEARTBEAT_S}초 + 유예 {GRACE_S}초 넘음)'
            else:
                common['plc_mode'], common['plc_state'] = r['운전_모드'], r['상태']
        if plc_reason:
            for k in ('plc_mode', 'plc_state'):
                common[k], missing[k] = None, plc_reason
        rows = [x for x in counter.get(asset, []) if x[0] <= J]
        gap = False
        if not rows:
            common['fan100_hours'], missing['fan100_hours'] = None, '판단 시각까지 팬 카운터 기록 없음'
        else:
            t, line, r = max(rows, key=lambda x: (x[0], x[1]))
            age_min = (J - t).total_seconds() / 60
            prov['fan'] = f'fan_counter.csv:{line} ({r["기록_시각"]} {r["기록_종류"]} {r["팬100_연속_분"]}분, 판단 {age_min:.2f}분 전)'
            if r['기록_종류'] == '종료':
                common['fan100_hours'] = 0.0
            elif age_min <= COUNTER_PERIOD_MIN:
                common['fan100_hours'] = (float(r['팬100_연속_분']) + age_min) / 60
            else:
                gap = True
                ctx = SimpleNamespace(alarm_id=a['경보_ID'], asset=asset, decision_time=a['판정_요청_시각'], counter_last={**r, '줄': line},
                                      counter_age_min=age_min, counter_period_min=COUNTER_PERIOD_MIN, plc_last=plc_last, plc_reason=plc_reason)
                hours, why = call_gap(gap_fn, ctx)
                common['fan100_hours'] = hours
                if hours is None:
                    missing['fan100_hours'] = f'팬 카운터 기록 끊김 — 마지막 {r["기록_종류"]} 기록 {age_min:.1f}분 전(주기 {COUNTER_PERIOD_MIN}분), {why}'
        cands = []
        for sop, tg in targets.items():
            x, m, p = dict(common), dict(missing), dict(prov)
            x['skill_kind'], x['skill_code'] = tg['skill_kind'], tg['skill_code']
            hit = fc.get((a['경보_ID'], sop))
            if hit is None:
                reason = '예측 결과 행 없음(판정 서버가 예측을 받지 못함)'
            else:
                line, r = hit
                p['forecast'] = f'forecasts.csv:{line}'
                age = (J - ts(r['기준_관측_시각'])).total_seconds()
                if r['상태'] != '완료':
                    reason = f'예측 거부 — {r["거부_사유"]}'
                elif age > FORECAST_VALID_S:
                    reason = f'예측 유효 시간 지남 — 기준 관측이 판단 {age:.0f}초 전({FORECAST_VALID_S}초 넘음)'
                else:
                    reason = None
                    scale = {'bar': 1.0, 'MPa': 10.0}.get(r['PS1_단위'])
                    if scale is None:
                        raise ContractError(f'forecasts.csv:{line} 알 수 없는 PS1 단위 {r["PS1_단위"]}')
                    x['forecast_ts1'] = float(r['예측_TS1_C'])
                    x['forecast_ps1'] = round(float(r['예측_PS1']) * scale, 6)
            if reason:
                for k in ('forecast_ts1', 'forecast_ps1'):
                    x[k], m[k] = None, reason
            cands.append({'sop': sop, 'inputs': {k: x[k] for k in INPUTS}, 'missing_reasons': m, 'provenance': p})
        out.append({'id': a['경보_ID'], 'asset': asset, 'decision_time': a['판정_요청_시각'], 'candidates': cands, 'counter_gap': gap})
    return out, targets


# ───────────── 비교(metric_definitions.md) ─────────────
def metric_inputs(lab):
    m = Path(lab)/'data/metrics'
    data = json.loads((m/'business_values.json').read_text(encoding='utf-8-sig'))
    values = {v['이름']: v['값'] for v in data['값']}
    works = {w['작업']: w for w in data['표준_작업']}
    settings = {r['후보']: r for r in read_csv(m/'candidate_settings.csv')}
    orders = {r['경보_ID']: r for r in read_csv(Path(lab)/'data/orders.csv')}
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
    """금액을 소수 둘째 자리로 사사오입(data/contract.md). 부동소수 원값의 이진 오차는 소수 아홉째 자리에서 먼저 걷어 낸다."""
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
    """1위를 고른 까닭(또는 순위가 없는 까닭)과 추가로 확인할 사항 — 판정 · 비교 결과에서 그대로 만든다."""
    by = {c['sop']: c for c in cands}
    held = [c for c in cands if c['status'] == '보류']
    skipped = [c for c in cands if c['status'] == '유지' and not c['comparison']]
    if ranking:
        top = [r['sop'] for r in ranking if r['rank'] == 1]
        reason = f'견준 후보 가운데 비교값이 가장 작은 후보({ranking[0]["total"]:.2f}만원)'
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


def decisions(choices):
    """판단 입력을 만든 방법 · 견주는 후보 — 제공 흐름의 방법과 학생이 고른 것(decisions.csv)."""
    return [
        {'item': '판단 시각', 'decision': 'alarms.csv RAISE 행의 판정_요청_시각(UTC)을 기준으로 현장 기록(+09:00)과 시각을 맞추고 그 뒤 기록은 쓰지 않는다', 'basis': 'collection_notes.md 첫 문단; work_standard.md 3절'},
        {'item': 'PLC 모드 · 상태', 'decision': f'마지막 수신. 품질 bad이거나 {HEARTBEAT_S + GRACE_S}초 넘게 수신이 없으면 값 없음', 'basis': 'collection_notes.md PLC_상태_수신(하트비트 · 유예); work_standard.md 3절; HI-01 SOP-HI-01 3단계'},
        {'item': '팬 100 % 연속 시간', 'decision': f'마지막 카운터 기록이 종료면 0, 시작 · 주기면 기록값 + 판단 시각까지 경과(분 ÷ 60). 주기({COUNTER_PERIOD_MIN}분)를 넘게 기록이 없으면 — {choice_text(choices, POINT_GAP)}',
         'basis': 'collection_notes.md 팬_운전_카운터; HM-8.8 「이미 24시간을 넘겼다면」; work_standard.md 3절'},
        {'item': '예측값', 'decision': f'행 없음 · 거부 · 기준 관측 뒤 {FORECAST_VALID_S}초 지남은 값 없음(이유를 따로 남김). MPa는 ×10 bar', 'basis': 'collection_notes.md 예측_결과'},
        {'item': '견주는 후보', 'decision': f'제외 · 보류 후보는 견주지 않는다. {choice_text(choices, POINT_WARN)}', 'basis': 'HM-8.6 「다른 조치와 비교한다」; metric_definitions.md 계산 가정; work_standard.md 4절'},
    ]


def call_compare(fn, kept):
    got = fn([{'sop': c['sop'], 'inputs': c['inputs'], 'warnings': c['warnings'], 'penalties': c['penalties']} for c in kept])
    if not isinstance(got, dict):
        raise ContractError(f'app/features/compare_rule.py:{fn.__code__.co_firstlineno} choose_compared가 dict({{후보: 까닭}})를 돌려주지 않음: {got!r}')
    names = {c['sop'] for c in kept}
    for sop, why in got.items():
        if sop not in names:
            raise ContractError(f'app/features/compare_rule.py:{fn.__code__.co_firstlineno} choose_compared: 유지 후보가 아닌 {sop}')
        if not (isinstance(why, str) and why.strip()):
            raise ContractError(f'app/features/compare_rule.py:{fn.__code__.co_firstlineno} choose_compared: {sop}의 까닭 글이 비어 있음')
    return got


def run(lab, table, gap_fn, compare_fn, choices, basis_text):
    """판단 입력 → 판정 → 비교 → 순위 · 선택 이유. 결과 계약(judgement.json)보다 안쪽 칸(rules · provenance · _raw)을 더 가진 dict."""
    lab = Path(lab)
    groups = load_table(table)
    events, targets = prepare(lab, gap_fn)
    values, works, settings, orders = metric_inputs(lab)
    result = {'comparison_basis': basis_text, 'decisions': decisions(choices), 'events': []}
    for e in events:
        cands = []
        for c in e['candidates']:
            j = evaluate(c['sop'], c['inputs'], groups)
            j['inputs'], j['missing_reasons'], j['provenance'] = c['inputs'], c['missing_reasons'], c['provenance']
            raw, why = components(c['inputs']['forecast_ts1'], settings[c['sop']], values, works, orders.get(e['id']))
            j['_raw'], j['_why'], j['comparison'] = raw, why, None
            cands.append(j)
        skip = call_compare(compare_fn, [j for j in cands if j['status'] == '유지'])
        for j in cands:
            if j['status'] != '유지':
                continue
            if j['sop'] in skip:
                j['no_comparison_reason'] = [skip[j['sop']].strip()]
            elif any(v is None for v in j['_raw'].values()):
                j['no_comparison_reason'] = [f'{LOSS_NAME[k]}: {j["_why"][k]}' for k in LOSSES if j['_raw'][k] is None]
            else:
                pen = sum(p['penalty_manwon'] for p in j['penalties'])
                j['comparison'] = {**{k: r2(j['_raw'][k]) for k in LOSSES}, 'penalty': r2(pen), 'total': r2(sum(j['_raw'].values()) + pen)}
        for j in cands:
            j.pop('_why')
        ranking = rank(cands)
        result['events'].append({'id': e['id'], 'asset': e['asset'], 'decision_time': e['decision_time'], 'candidates': cands, 'ranking': ranking,
                                 'selection': selection(cands, ranking), '_counter_gap': e['counter_gap']})
    return result


def student_view(result):
    """결과 계약 꼴(엔진 안쪽 칸 rules · provenance · _raw · _counter_gap을 뺀다)."""
    out = json.loads(json.dumps(result, ensure_ascii=False, default=str))
    for e in out['events']:
        e.pop('_counter_gap', None)
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
                  '| 후보 | 판정 | 이유(규칙 · 결과 · 비교) | 비교값 · 순위 | 승인 역할 | 추가로 확인할 값 |', '|---|---|---|---|---|---|']
        for c in it['candidates']:
            why = '<br>'.join(f'{r["rule_id"]} {KIND[r["result"]]} {r["expression"]}' for r in c['reasons']) or '맞은 규칙 없음'
            val = f'{c["comparison"]["total"]:.2f} · {c["rank"]}위' if c['comparison'] else ('견주지 않음: ' + '; '.join(c['no_comparison_reason']) if c.get('no_comparison_reason') else '—')
            lines.append(f'| {c["sop"]} | {c["status"]} | {why} | {val} | {c["approval"]["role"]} ({c["approval"]["source"]}) | {"<br>".join(c["checks"]) or "—"} |')
        lines.append('')
    return '\n'.join(lines) + '\n'


# ───────────── 학생 폴더에서 한 번에 ─────────────
def run_folder(root, review_mode=False):
    """학생 폴더의 빈 틀 · 정한 것으로 흐름을 돌려 결과 계약 파일을 쓴다. 돌려주는 값 = (안쪽 결과, 쓴 파일 목록)."""
    root = Path(root)
    choices = load_choices(root)
    basis = choice_text(choices, POINT_BASIS)
    table = pick(root, 'condition_table.csv')
    res = run(root, table, load_function(root, GAP_FILE, 'fan_hours_when_gap'), load_function(root, COMPARE_FILE, 'choose_compared'), choices, basis)
    if review_mode:
        sop_doc = json.loads(pick(root, 'sop.json').read_text(encoding='utf-8-sig'))
        rv = review(res, sop_doc, load_table(table))
        write_text(root/'output/action_review.json', json.dumps(rv, ensure_ascii=False, indent=1) + '\n')
        write_text(root/'output/action_review.md', review_md(rv))
        return res, ['output/action_review.json', 'output/action_review.md']
    write_text(root/'output/judgement.json', json.dumps(student_view(res), ensure_ascii=False, indent=1) + '\n')
    return res, ['output/judgement.json']


def source_facts(lab):
    """경보마다 판정 요청 직전 원천 기록의 사실(판정 없음): PLC 마지막 수신 나이 · 품질, 카운터 마지막 기록 · 나이, 예측 행 상태."""
    d = Path(lab)/'data'
    alarms = [r for r in read_csv(d/'alarms.csv') if r['구분'] == 'RAISE' and r['판정_요청_시각']]
    plc, counter, fc = {}, {}, {}
    for line, r in enumerate(read_csv(d/'plc_status.csv'), start=2):
        plc.setdefault(r['설비'], []).append((ts(r['수신_시각']), line, r))
    for line, r in enumerate(read_csv(d/'fan_counter.csv'), start=2):
        counter.setdefault(r['설비'], []).append((ts(r['기록_시각']), line, r))
    for line, r in enumerate(read_csv(d/'forecasts.csv'), start=2):
        fc.setdefault(r['경보_ID'], []).append((line, r))
    out = []
    for a in alarms:
        J = ts(a['판정_요청_시각'])
        p = [x for x in plc.get(a['설비'], []) if x[0] <= J]
        c = [x for x in counter.get(a['설비'], []) if x[0] <= J]
        pl = max(p, key=lambda x: (x[0], x[1])) if p else None
        cl = max(c, key=lambda x: (x[0], x[1])) if c else None
        f = fc.get(a['경보_ID'], [])
        out.append({'경보': a['경보_ID'], '설비': a['설비'], '판정 요청(UTC)': a['판정_요청_시각'],
                    'PLC 마지막 수신': f'{(J - pl[0]).total_seconds():.0f}초 전 · {pl[2]["품질"]} · {pl[2]["운전_모드"]}/{pl[2]["상태"]} (plc_status.csv:{pl[1]})' if pl else '없음',
                    '카운터 마지막 기록': f'{cl[2]["기록_종류"]} {cl[2]["팬100_연속_분"]}분 · {(J - cl[0]).total_seconds() / 60:.1f}분 전 (fan_counter.csv:{cl[1]})' if cl else '없음',
                    '예측 행': f'{len(f)}행 · 거부 {sum(1 for _, r in f if r["상태"] != "완료")} · MPa {sum(1 for _, r in f if r["PS1_단위"] == "MPa")}'})
    return out
