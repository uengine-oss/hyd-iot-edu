"""결과/result.json의 구조와 계약 검사, 기대결과.md 기록 칸 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
어떤 규칙이 맞아야 하는지, 금액이 맞는지, 어느 후보가 1위여야 하는지는 판정하지 않는다 — 원천 · 원문 · 지표_정의.md 손계산과 따로 대조한다.
규칙 ID는 결과/내_입력/조건표.csv가 있으면 그것으로, 없으면 입력/조건표.csv로 본다(어느 쪽을 봤는지 첫 줄에 찍는다).
사용: python check.py
"""
from pathlib import Path
import csv, json, re, sys
root = Path(__file__).resolve().parent
INPUTS = ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state', 'skill_kind', 'skill_code']
RANGE = {'forecast_ts1': (0, 150, '℃'), 'forecast_ps1': (50, 300, 'bar'), 'fan100_hours': (0, 1000, 'h')}
LOSS = ['cost', 'production', 'quality', 'energy', 'penalty']
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def pick(name):
    # 검사의 기준 입력: 결과/내_입력/에 같은 이름 파일이 있으면 그것, 없으면 제공 입력/. 고른 파일을 찍는다(조용히 바꾸지 않는다).
    mine = root/'결과/내_입력'/name
    if mine.is_file():
        print(f'기준 입력: 결과/내_입력/{name} (내 입력)')
        return mine
    if (root/'결과/내_입력').is_dir():
        print(f'기준 입력: 입력/{name} — 결과/내_입력/에 {name}이 없어 제공 입력으로 봅니다')
    else:
        print(f'기준 입력: 입력/{name}')
    return root/'입력'/name

alarms = [r['경보_ID'] for r in rows(root/'자료/경보_목록.csv') if r['구분'] == 'RAISE' and r['판정_요청_시각']]
sops = [r['sop_id'] for r in rows(root/'자료/targets.csv')]
table_path = pick('조건표.csv')
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
def table_rows(path, column):
    if not path.is_file(): return None
    head, total, empty = None, 0, 0
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('|'): head = None; continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if head is None: head = cells; continue
        if set(''.join(cells)) <= set('-: '): continue
        idx = [k for k, h in enumerate(head) if h.startswith(column)]
        if not idx or not any(cells): continue
        total += 1
        if idx[0] >= len(cells) or not cells[idx[0]]: empty += 1
    return total, empty
def record_part(path, column, label):
    got = table_rows(path, column)
    if got is None: return (f'{path.name} {label}', '없음', [], '', False)
    total, empty = got
    if total == 0 or empty == total: return (f'{path.name} {label}', '아직 비어 있음', [], f'「{column}」 칸을 채웁니다', False)
    return (f'{path.name} {label}', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 빈 칸 {empty}개' if empty else f'행 {total}개', False)
def expect_time(path):
    if not path.is_file(): return []
    m = re.search(r'기대 칸을 쓴 시각[^:]*:[ \t]*(\S.*)?$', path.read_text(encoding='utf-8-sig'), re.M)
    return [] if m and m.group(1) else ['기대결과.md 「기대 칸을 쓴 시각」이 비어 있습니다 — 실행 전에 기대를 먼저 적었는지 남깁니다.']
def report(parts):
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs[:40]: print('    ' + e)
        if len(errs) > 40: print(f'    … 외 {len(errs) - 40}건')
        if required and state != '통과': ok = False
    return ok

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
    if not str(result.get('comparison_basis', '')).strip(): errs.append('comparison_basis(비교 합계와 포털 성과 지표 점수의 구분 문장)가 없습니다.')
    errs += decisions_errors(result.get('decisions'))
    events = result.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [e.get('id') for e in events if isinstance(e, dict)]
    if got != alarms: errs.append(f'events: 경보_목록.csv의 RAISE 행과 사례 · 순서가 다릅니다(빠짐 {sorted(set(alarms) - set(got))}, 더함 {sorted(set(got) - set(alarms))}).')
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
            if st != want: errs.append(f'{at}: status {st} — 제외 사유 {len(ex)}개 · 알 수 없는 규칙 {len(unknown)}개와 맞지 않습니다(뜻은 작업기준.md 4절).')
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
state, errs, note = check_result(root/'결과/result.json')
if state == '없음': print('아직 검사할 결과가 없습니다: 결과/result.json')
print('구조 검사 결과')
ok = report([('result.json', state, errs, note, True), record_part(root/'결과/기대결과.md', '고른 것', '정한 것'),
             record_part(root/'결과/기대결과.md', '실제 결과', '사례 대조'), record_part(root/'결과/기대결과.md', '프로그램', '손계산 대조')])
for line in expect_time(root/'결과/기대결과.md'): print('참고: ' + line)
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과의 어느 사례 · 후보인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양과 계약만 봅니다. 의미와 질문별 답(어떤 규칙이 맞아야 하는지, 금액, 어느 후보가 1위인지)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
