"""조건표(결과/조건표.csv)를 확인 사례(자료/확인_사례.csv)에 대어 사례 · 후보마다 맞은 규칙과, 입력이 없어 맞는지 알 수 없는 규칙을 낸다.
규칙은 조건표에서만 읽는다. 맞은 규칙은 모두 모으고(Hit Policy 모으기), 값이 빈 입력을 0이나 앞 값으로 채우지 않는다.
확인 사례의 입력 이름은 입출력_계약.md 「확인 사례」의 짝대로 조건표의 input으로 읽는다(값은 판정 요청 때의 판단 입력, 단위는 조건표와 같다).
사용: python 결과/apply_conditions.py      → 화면 출력과 결과/사례_대조.md
"""
from pathlib import Path
import csv

root = Path(__file__).resolve().parents[1]
NUMERIC = {'forecast_ts1', 'forecast_ps1', 'fan100_hours'}


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


groups = {}
for r in rows(root/'결과/조건표.csv'):
    g = groups.setdefault((r['rule_id'], r['action']), {'result': r['result'], 'conds': []})
    g['conds'].append(r)
targets = {r['sop_id']: r for r in rows(root/'자료/targets.csv')}

cases = {}
for r in rows(root/'자료/확인_사례.csv'):
    c = cases.setdefault(r['사례'], {'asset': r['설비'], 'common': {}, 'forecast': {}})
    if r['입력'] == '운전_모드':
        c['common']['plc_mode'] = r['값'] or None
    elif r['입력'] == '상태':
        c['common']['plc_state'] = r['값'] or None
    elif r['입력'] == '팬100_연속':
        c['common']['fan100_hours'] = float(r['값']) if r['값'] else None
    else:
        key = {'예측_TS1': 'forecast_ts1', '예측_PS1': 'forecast_ps1'}[r['입력']]
        c['forecast'].setdefault(r['후보'], {})[key] = float(r['값']) if r['값'] else None


def holds(cond, value):
    op, want = cond['operator'], cond['value']
    if op == 'has_other_than':
        return any(code != want for code in value)
    if cond['input'] in NUMERIC:
        a, b = float(value), float(want)
        return {'>=': a >= b, '>': a > b, '<=': a <= b, '<': a < b, '==': a == b, '!=': a != b}[op]
    return {'==': value == want, '!=': value != want}[op]


out = ['# 확인 사례에 조건표를 댄 결과', '', '| 사례 | 후보 | 경고 | 감점(만원) | 제외 | 알 수 없는 규칙(빠진 입력) |', '|---|---|---|---|---|---|']
for cid, c in cases.items():
    for sop, t in targets.items():
        x = {**c['common'], 'forecast_ts1': None, 'forecast_ps1': None, **c['forecast'].get(sop, {}),
             'skill_kind': t['kind'], 'skill_code': [k for k in t['codes'].split(';') if k]}
        hit = {'WARN': [], 'PENALTY': [], 'EXCLUDE': []}
        unknown = []
        for (rid, action), g in sorted(groups.items()):
            if action != sop:
                continue
            missing = [d['input'] for d in g['conds'] if x.get(d['input']) is None]
            false = any(not holds(d, x[d['input']]) for d in g['conds'] if x.get(d['input']) is not None)
            if false:
                continue
            if missing:
                unknown.append(f'{rid}({", ".join(missing)})')
            else:
                hit[g['result']].append(rid + (f' {g["conds"][0]["penalty_manwon"]}' if g['result'] == 'PENALTY' else ''))
        out.append(f'| {cid} | {sop} | {" · ".join(hit["WARN"]) or "—"} | {" · ".join(hit["PENALTY"]) or "—"} | {" · ".join(hit["EXCLUDE"]) or "—"} | {" · ".join(unknown) or "—"} |')
(root/'결과/사례_대조.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
print('\n'.join(out[2:]))
print(f'사례 {len(cases)}건 × 후보 {len(targets)} → 결과/사례_대조.md')
