"""결과/조치검토결과.json · .md의 구조와 계약 검사, 기대결과.md 기록 칸 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
판정 · 이유 · 출처가 원문 · 원천과 맞는지, 금액, 어느 후보가 1위여야 하는지는 판정하지 않는다 — 원자료와 따로 대조한다.
규칙 ID는 결과/내_입력/조건표.csv, 승인 역할은 결과/내_입력/sop.json이 있으면 그것으로, 없으면 입력/의 파일로 본다(어느 쪽을 봤는지 찍는다).
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

sop_doc = json.loads(pick('sop.json').read_text(encoding='utf-8-sig'))
approver = {s['id']: (s.get('approval') or {}).get('role') for s in sop_doc.get('sops', [])}
def check_review(jpath, mpath):
    if not jpath.is_file(): return '없음', [], ''
    try: rv = json.loads(jpath.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    md = mpath.read_text(encoding='utf-8-sig') if mpath.is_file() else ''
    errs = [] if md else ['조치검토결과.md가 없습니다.']
    if not str(rv.get('comparison_basis', '')).strip(): errs.append('comparison_basis(비교 합계와 포털 성과 지표 점수 · 실행 승인의 구분 문장)가 없습니다.')
    errs += decisions_errors(rv.get('decisions'))
    events = rv.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [i.get('id') for i in events if isinstance(i, dict)]
    if got != alarms: errs.append(f'events: 경보_목록.csv의 RAISE 행과 사례 · 순서가 다릅니다(빠짐 {sorted(set(alarms) - set(got))}, 더함 {sorted(set(got) - set(alarms))}).')
    for it in events:
        iid = it.get('id'); cands = it.get('candidates') or []
        if md and not re.search(r'^#+\s.*(?<![A-Za-z0-9-])' + re.escape(str(iid)) + r'(?![A-Za-z0-9-])', md, re.M): errs.append(f'조치검토결과.md에 {iid}의 절 제목이 없습니다.')
        if [c.get('sop') for c in cands] != sops: errs.append(f'{iid}: 후보 목록 · 순서가 targets.csv와 다릅니다.')
        totals, ranked = {}, []
        for c in cands:
            at = f'{iid}/{c.get("sop")}'
            st = c.get('status')
            reasons = c.get('reasons') if isinstance(c.get('reasons'), list) else None
            errs += inputs_errors(at, c.get('inputs') or {}, c.get('missing_reasons'))
            if st not in ('유지', '제외', '보류'): errs.append(f'{at}: status는 유지 · 제외 · 보류 가운데 하나입니다.'); continue
            if reasons is None: errs.append(f'{at}: 이유 목록(reasons)이 필요합니다.'); continue
            for r in reasons:
                if (r.get('rule_id'), c.get('sop')) not in groups: errs.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {r.get("rule_id")}')
                if r.get('result') not in ('WARN', 'PENALTY', 'EXCLUDE', '미확인'): errs.append(f'{at} {r.get("rule_id")}: result는 WARN · PENALTY · EXCLUDE · 미확인 가운데 하나입니다.')
                if not r.get('expression') or not r.get('source') or not isinstance(r.get('actual_inputs'), dict): errs.append(f'{at} {r.get("rule_id")}: actual_inputs · expression · source가 필요합니다.')
                if r.get('result') == '미확인' and (not r.get('missing_inputs') or not r.get('missing_reason')): errs.append(f'{at} {r.get("rule_id")}: 미확인에는 missing_inputs와 missing_reason이 필요합니다.')
            kinds = [r.get('result') for r in reasons]
            want = '제외' if 'EXCLUDE' in kinds else ('보류' if '미확인' in kinds else '유지')
            if st != want: errs.append(f'{at}: 판정 {st}이 이유의 결과({", ".join(kinds) or "없음"})와 맞지 않습니다(뜻은 작업기준.md 4절).')
            if not c.get('sources'): errs.append(f'{at}: 원문 출처(sources)가 비었습니다.')
            checks = c.get('checks')
            if not isinstance(checks, list): errs.append(f'{at}: 추가로 확인할 값(checks) 목록이 필요합니다.'); checks = []
            for m in sorted({m for r in reasons if r.get('result') == '미확인' for m in r.get('missing_inputs') or []}):
                if not any(m in str(x) for x in checks): errs.append(f'{at}: 미확인 규칙의 빠진 입력 {m}이 추가로 확인할 값(checks)에 없습니다.')
            ap = c.get('approval') or {}
            if not ap.get('role') or not ap.get('source') or not ap.get('note'): errs.append(f'{at}: 승인(approval — role · source · note)이 필요합니다.')
            elif ap.get('role') != approver.get(c.get('sop')): errs.append(f'{at}: 승인 역할 {ap.get("role")}이 기준 sop.json의 {approver.get(c.get("sop"))}과 다릅니다.')
            value, rank = c.get('comparison'), c.get('rank')
            errs += kept_errors(at, st, value, c.get('no_comparison_reason'))
            if value is None and rank is not None: errs.append(f'{at}: 비교값이 없는 후보에 순위(rank)가 있습니다.')
            if st == '유지' and isinstance(value, dict):
                totals[c.get('sop')] = value.get('total'); ranked.append((c.get('sop'), rank, value.get('total')))
        errs += rank_errors(iid, ranked)
        op = it.get('review') or {}
        top = op.get('top') if isinstance(op.get('top'), list) else None
        if top is None: errs.append(f'{iid}: review.top 목록이 필요합니다(1위가 없으면 빈 목록).'); top = []
        for s in top:
            if s not in totals: errs.append(f'{iid}: review.top의 {s}는 비교값이 있는 유지 후보가 아닙니다.')
        if not op.get('reason'): errs.append(f'{iid}: review.reason이 필요합니다.')
        if not isinstance(op.get('checks'), list): errs.append(f'{iid}: review.checks 목록이 필요합니다(없으면 빈 목록).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_review(root/'결과/조치검토결과.json', root/'결과/조치검토결과.md')
if state == '없음': print('아직 검사할 결과가 없습니다: 결과/조치검토결과.json')
print('구조 검사 결과')
ok = report([('조치검토결과.json · .md', state, errs, note, True), record_part(root/'결과/기대결과.md', '고른 것', '정한 것'),
             record_part(root/'결과/기대결과.md', '실제 결과', '사례 대조'), record_part(root/'결과/기대결과.md', '프로그램', '손계산 대조')])
for line in expect_time(root/'결과/기대결과.md'): print('참고: ' + line)
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과의 어느 사례 · 후보인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양과 계약만 봅니다. 의미와 질문별 답(판정 · 이유 · 출처가 원문과 맞는지, 금액, 어느 후보가 1위인지)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
