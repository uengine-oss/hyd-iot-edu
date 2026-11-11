"""output/judgement.json의 구조와 계약 검사, 정한 것 · 기대 판정 · 제공 파일 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
어떤 규칙이 맞아야 하는지, 금액이 맞는지, 어느 후보가 1위여야 하는지는 판정하지 않는다. 규칙 ID는 app/features/criteria/condition_table.csv가 있으면 그것으로 본다.
사용: python run.py check
"""
from pathlib import Path
import csv, io, json, re, sys
root = Path(__file__).resolve().parents[2]
def csv_rows(path):
    """(열 이름, 행, 첫머리 # 줄 수) — 「제공 빈 틀」 표시 줄은 데이터가 아니다."""
    lines = path.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    skip = 0
    while skip < len(lines) and lines[skip].lstrip().startswith('#'):
        skip += 1
    reader = csv.DictReader(io.StringIO(''.join(lines[skip:]), newline=''))
    return reader.fieldnames, list(reader), skip
def read_csv(path):
    head, rows, _ = csv_rows(path)
    return head, rows
def report(parts):
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs[:40]: print('    ' + e)
        if len(errs) > 40: print(f'    … 외 {len(errs) - 40}건')
        if required and state not in ('통과', '아직 비어 있음'): ok = False
    return ok
def expect_part(root):
    p = root/'app/features/expected.csv'
    if not p.is_file(): return ('expected.csv', '없음 — 받은 ZIP의 빈 틀을 지우지 않습니다', [], '', True)
    head, rows, skip = csv_rows(p)
    if head != ['사례', '후보', '기대_판정', '근거']: return ('expected.csv', '확인 필요', ['열 이름이 사례,후보,기대_판정,근거가 아닙니다.'], '', True)
    if not rows: return ('expected.csv', '아직 비어 있음', [], '실행 전에 기대 판정을 적습니다', False)
    errs = []
    for n, r in enumerate(rows, skip + 2):
        if (r.get('기대_판정') or '').strip() not in ('유지', '제외', '보류'): errs.append(f'expected.csv:{n} 기대_판정은 유지 · 제외 · 보류 가운데 하나입니다.')
        if not re.search(r'[^\s:]+:\d+', r.get('근거') or ''): errs.append(f'expected.csv:{n} 근거에 파일:줄이 없습니다.')
    return ('expected.csv', '확인 필요' if errs else '통과', errs, f'행 {len(rows)}개', True)
def chosen_part(root):
    errs = chosen_errors(root)
    p = root/'app/features/decisions.csv'
    if not errs and p.is_file() and not csv_rows(p)[1]: return ('decisions.csv', '아직 비어 있음', [], '지점마다 고른 것 · 근거를 적습니다', False)
    return ('decisions.csv', '확인 필요' if errs else '통과', errs, '', True)
def provided_part(root):
    errs = provided_errors(root)
    return ('제공 파일', '확인 필요' if errs else '통과', errs, '', True)
def chosen_errors(root):
    """app/features/decisions.csv — 빈 칸 · 근거 꼴(파일:줄)만 본다. 고른 것이 맞는지는 보지 않는다."""
    import csv, io, re
    p = root / 'app/features' / 'decisions.csv'
    if not p.is_file():
        return ['app/features/decisions.csv가 없습니다 — 받은 ZIP의 빈 틀을 지우지 않습니다.']
    lines = [x for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')]
    rows = list(csv.DictReader(io.StringIO('\n'.join(lines))))
    need = ['지점', '고른_것', '근거', '바뀌는_답']
    if not lines or [c.strip() for c in csv.reader([lines[0]]).__next__()] != need:
        return ['app/features/decisions.csv: 열 이름이 ' + ','.join(need) + '이어야 합니다.']
    out = []
    for n, r in enumerate(rows, 1):
        empty = [c for c in need if not (r.get(c) or '').strip()]
        if empty:
            out.append(f'app/features/decisions.csv {n}번째 행: 빈 칸 ' + ', '.join(empty) + '(못 정했으면 고른_것에 「미결」).')
        elif not re.search(r'[^\s:]+:\d+', r['근거']):
            out.append(f'app/features/decisions.csv {n}번째 행: 근거에 파일:줄이 없습니다.')
    return out
import hashlib as _h
_PROVIDED = {
 "app/ui/render.py": "907e551b102d445518b4118709135b231f489299c8eab1112b70af8462730a8e",
 "app/utils/actions.py": "7f0a6fc2764157188484a4cb86a90ad55e8df7bad843e864740335dc79ce9470",
 "app/utils/condition_tools.py": "d5c7daf0b405d1a68ad86cee7d3f84e4e1eb67149534601edbe75649ce936d91",
 "app/utils/judge_tools.py": "e7b9edd8f85fb093f632e6e3ed0c0826c464eeda96afad44c5c489eafbe94416",
 "app/utils/results.py": "1c5b0596745e9ac1e9b7f06d84c7463d99720597edcf46801d32a51e640ae86b",
 "run.py": "700d5805b32e7c0318247812c16e19ad7e641edf35305e892d8aa9268c56cce6"
}
def provided_errors(root):
    out = []
    for name, digest in _PROVIDED.items():
        p = root / name
        if not p.is_file():
            out.append(f'제공 파일이 없습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
        elif _h.sha256(p.read_bytes()).hexdigest() != digest:
            out.append(f'제공 파일이 바뀌었습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
    return out
def pick(name):
    # 검사의 기준 입력: app/features/criteria/에 같은 이름 파일이 있으면 그것, 없으면 제공 data/criteria/. 고른 파일을 찍는다(조용히 바꾸지 않는다).
    mine = root/'app/features/criteria'/name
    if mine.is_file():
        print(f'기준 입력: app/features/criteria/{name} (내 입력)')
        return mine
    if (root/'app/features/criteria').is_dir():
        print(f'기준 입력: data/criteria/{name} — app/features/criteria/에 {name}이 없어 제공 입력으로 봅니다')
    else:
        print(f'기준 입력: data/criteria/{name}')
    return root/'data/criteria'/name

INPUTS = ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state', 'skill_kind', 'skill_code']
RANGE = {'forecast_ts1': (0, 150, '℃'), 'forecast_ps1': (50, 300, 'bar'), 'fan100_hours': (0, 1000, 'h')}
LOSS = ['cost', 'production', 'quality', 'energy', 'penalty']
def rows(path): return read_csv(path)[1]
alarms = [r['경보_ID'] for r in rows(root/'data/alarms.csv') if r['구분'] == 'RAISE' and r['판정_요청_시각']]
sops = [r['sop_id'] for r in rows(root/'data/targets.csv')]
table_path = pick('condition_table.csv')
table = rows(table_path)
if not table or not {'rule_id', 'action'} <= set(table[0]):
    print(f'구조 확인 필요 — {table_path.relative_to(root).as_posix()}의 열 이름이 계약(rule_id · action …)과 다릅니다. 내 입력이면 계약과 견주어 고친 뒤 다시 실행합니다.')
    sys.exit(1)
groups = {(r['rule_id'], r['action']) for r in table}
def num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
def inputs_errors(at, inputs, reasons):
    out = []
    for k in INPUTS:
        if k not in inputs: out.append(f'{at}: 입력에 {k}가 없습니다(값이 없으면 null).')
        elif inputs[k] is None and not (reasons or {}).get(k): out.append(f'{at}: {k}가 null인데 왜 없는지가 없습니다.')
    for k, (lo, hi, unit) in RANGE.items():
        v = inputs.get(k)
        if num(v) and not lo <= v <= hi: out.append(f'{at}: {k}={v}는 계약 단위 {unit}의 범위({lo} ~ {hi})를 벗어납니다. 원천의 단위를 확인합니다.')
    return out
def total_errors(at, value):
    if not isinstance(value, dict) or not all(num(value.get(k)) for k in LOSS + ['total']): return [f'{at}: 비교값(comparison)에 {LOSS + ["total"]}가 숫자로 있어야 합니다.']
    if abs(sum(value[k] for k in LOSS) - value['total']) > 0.03: return [f'{at}: 합계 total {value["total"]}가 네 손실과 감점의 합 {sum(value[k] for k in LOSS):.2f}와 다릅니다.']
    return []
def rank_errors(at, ranked):
    """ranked = [(sop, 순위, 합계)] — 합계 오름차순과 같은 합계 같은 순위(1, 1, 3)."""
    out, ranked = [], sorted(ranked, key=lambda x: (x[1] if num(x[1]) else 9e9))
    totals = [t for _, _, t in ranked]
    if totals != sorted(totals): out.append(f'{at}: 순위가 합계가 작은 순서가 아닙니다.')
    for i, (s, r, t) in enumerate(ranked):
        want = ranked[i - 1][1] if i and ranked[i - 1][2] == t else i + 1
        if r != want: out.append(f'{at}: {s}의 순위 {r} — 같은 합계는 같은 순위, 다음은 그 수만큼 건너뜁니다(1, 1, 3).')
    return out
def kept_errors(at, status, value, note):
    """비교값은 유지 후보에만, 비교값이 없는 유지 후보에는 까닭."""
    if status != '유지':
        return [f'{at}: 유지가 아닌 후보({status})에 비교값이 있습니다.'] if value is not None else []
    if value is None:
        return [] if note else [f'{at}: 유지 후보에 비교값이 없으면 no_comparison_reason에 까닭이 필요합니다.']
    return total_errors(at, value)
def decisions_errors(value):
    if not isinstance(value, list) or not value or any(not (isinstance(d, dict) and d.get('item') and d.get('decision') and d.get('basis')) for d in value):
        return ['decisions(item · decision · basis — 판단 입력을 만든 방법 · 견주는 후보 등 정한 것)가 필요합니다.']
    return []

def hit_errors(at, sop, hits, penalty=False):
    out = []
    if not isinstance(hits, list): return [f'{at}: 맞은 규칙은 목록입니다.']
    for h in hits:
        if (h.get('rule_id'), sop) not in groups: out.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {h.get("rule_id")}')
        if not h.get('source_section') or not isinstance(h.get('conditions'), list) or not h['conditions']: out.append(f'{at} {h.get("rule_id")}: source_section과 conditions(조건마다 실제 값)가 필요합니다.')
        if penalty and not num(h.get('penalty_manwon')): out.append(f'{at} {h.get("rule_id")}: penalty_manwon이 숫자로 필요합니다.')
    return out
def check_result(path):
    if not path.is_file(): return '없음', [], ''
    try: result = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    errs = []
    if not str(result.get('comparison_basis', '')).strip(): errs.append('comparison_basis(비교값과 정책 점수의 구분 문장)가 없습니다.')
    errs += decisions_errors(result.get('decisions'))
    events = result.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [e.get('id') for e in events if isinstance(e, dict)]
    if got != alarms: errs.append(f'events: alarms.csv의 RAISE 행과 사례 · 순서가 다릅니다(빠짐 {sorted(set(alarms) - set(got))}, 더함 {sorted(set(got) - set(alarms))}).')
    for e in events:
        eid = e.get('id'); cands = e.get('candidates') or []
        if [c.get('sop') for c in cands] != sops: errs.append(f'{eid}: 후보 목록 · 순서가 targets.csv와 다릅니다.')
        totals = {}
        for c in cands:
            at = f'{eid}/{c.get("sop")}'
            errs += inputs_errors(at, c.get('inputs') or {}, c.get('missing_reasons'))
            st = c.get('status')
            if st not in ('유지', '제외', '보류'): errs.append(f'{at}: status는 유지 · 제외 · 보류 가운데 하나입니다.'); continue
            errs += hit_errors(at, c.get('sop'), c.get('warnings')) + hit_errors(at, c.get('sop'), c.get('exclusions')) + hit_errors(at, c.get('sop'), c.get('penalties'), True)
            unknown = c.get('unknown') if isinstance(c.get('unknown'), list) else []
            for u in unknown:
                if (u.get('rule_id'), c.get('sop')) not in groups: errs.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {u.get("rule_id")}')
                if not u.get('missing'): errs.append(f'{at} {u.get("rule_id")}: unknown에는 빠진 입력 이름(missing)이 필요합니다.')
            ex = c.get('exclusions') or []
            want = '제외' if ex else ('보류' if unknown else '유지')
            if st != want: errs.append(f'{at}: status {st} — 제외 사유 {len(ex)}개 · 알 수 없는 규칙 {len(unknown)}개와 맞지 않습니다(뜻은 work_standard.md 4절).')
            comp = c.get('comparison')
            errs += kept_errors(at, st, comp, c.get('no_comparison_reason'))
            if st == '유지' and isinstance(comp, dict):
                totals[c.get('sop')] = comp.get('total')
                pen = sum(p.get('penalty_manwon', 0) for p in c.get('penalties') or [] if num(p.get('penalty_manwon')))
                if num(comp.get('penalty')) and abs(pen - comp['penalty']) > 0.001: errs.append(f'{at}: 감점 {comp["penalty"]}이 penalties 금액의 합 {pen}과 다릅니다.')
        ranking = e.get('ranking')
        if not isinstance(ranking, list): errs.append(f'{eid}: ranking 목록이 필요합니다.'); continue
        if sorted(r.get('sop') for r in ranking) != sorted(totals): errs.append(f'{eid}: ranking에는 비교값이 있는 후보가 모두 한 번씩 있어야 합니다(지금 {sorted(r.get("sop") for r in ranking)}, 비교값 있음 {sorted(totals)}).')
        for r in ranking:
            if r.get('total') != totals.get(r.get('sop')): errs.append(f'{eid}: ranking의 {r.get("sop")} total이 그 후보의 비교값과 다릅니다.')
        errs += rank_errors(eid, [(r.get('sop'), r.get('rank'), r.get('total')) for r in ranking])
        sel = e.get('selection') or {}
        if not sel.get('reason'): errs.append(f'{eid}: selection.reason(1위를 고른 까닭 또는 순위가 없는 까닭)이 필요합니다.')
        if not isinstance(sel.get('checks'), list): errs.append(f'{eid}: selection.checks 목록이 필요합니다(없으면 빈 목록).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_result(root/'output/judgement.json')
if state == '없음': print('아직 검사할 결과가 없습니다: output/judgement.json — python run.py write가 만듭니다')
print('구조 검사 결과')
ok = report([('judgement.json', state, errs, note, True), chosen_part(root), expect_part(root), provided_part(root)]) and state == '통과'
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과의 어느 사례 · 후보인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양과 계약만 봅니다. 의미와 질문별 답(어떤 규칙이 맞아야 하는지, 금액, 어느 후보가 1위인지)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
