"""결과/조건표.csv의 구조 검사와 판단기록.md 기록 칸 확인. 의미 정답은 판정하지 않는다."""
from pathlib import Path
import csv, sys
root = Path(__file__).resolve().parent
HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_만원','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
INPUTS = NUMERIC | {'plc_mode','plc_state','skill_kind','skill_code'}
def check_rules(path, sop_ids):
    """(상태, 오류 목록, 묶음 수). 상태: 없음·빈 틀·통과·확인 필요."""
    if not path.is_file(): return '없음', [], 0
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f); header = reader.fieldnames; table = list(reader)
    errs, groups = [], {}
    if header != HEADER: return '확인 필요', ['열 이름·순서가 계약과 다릅니다: '+','.join(header or [])], 0
    if not table: return '빈 틀', [], 0
    for line, r in enumerate(table, 2):
        at = f'{path.name}:{line}'
        if r['action'] not in sop_ids: errs.append(f'{at} targets.csv에 없는 action {r["action"]}')
        if r['logic'] != 'AND': errs.append(f'{at} logic은 AND')
        if r['input'] not in INPUTS: errs.append(f'{at} 계약에 없는 input {r["input"]}')
        if r['operator'] not in OPS: errs.append(f'{at} 계약에 없는 operator {r["operator"]}')
        elif OPS[r['operator']] != r['boundary_included']: errs.append(f'{at} boundary_included({r["boundary_included"]})가 operator {r["operator"]}와 맞지 않습니다.')
        if r['result'] not in {'WARN','PENALTY','EXCLUDE'}: errs.append(f'{at} result는 WARN·PENALTY·EXCLUDE')
        if r['input'] in NUMERIC:
            try: float(r['value'])
            except ValueError: errs.append(f'{at} 숫자 입력의 기준값이 숫자가 아닙니다.')
            if not r['unit']: errs.append(f'{at} 숫자 입력의 unit이 비었습니다.')
        if r['result'] == 'PENALTY':
            try: float(r['penalty_만원'])
            except ValueError: errs.append(f'{at} PENALTY에 penalty_만원이 없습니다.')
        elif r['penalty_만원']: errs.append(f'{at} PENALTY가 아닌 행에 penalty_만원이 있습니다.')
        if not r['reason'] or not r['source_section']: errs.append(f'{at} reason·source_section이 필요합니다.')
        key = (r['rule_id'], r['action']); head = (r['result'], r['penalty_만원'], r['reason'], r['source_section'])
        g = groups.setdefault(key, {'head': head, 'index': []})
        if g['head'] != head: errs.append(f'{at} 같은 묶음 {key}의 result·penalty·reason·source가 다릅니다.')
        try: g['index'].append(int(r['condition_index']))
        except ValueError: errs.append(f'{at} condition_index가 정수가 아닙니다.')
    for key, g in groups.items():
        if sorted(g['index']) != list(range(1, len(g['index'])+1)): errs.append(f'{path.name} 묶음 {key}: condition_index가 1부터 연속이 아닙니다: {g["index"]}')
    return ('확인 필요' if errs else '통과'), errs, len(groups)
def empty_rows(path, column):
    """마크다운 표에서 column 칸이 빈 데이터 행 수와 데이터 행 수."""
    if not path.is_file(): return None, 0
    head, empty, total = None, 0, 0
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('|'): head = None; continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if head is None: head = cells; continue
        if set(''.join(cells)) <= set('-: '): continue
        idx = [k for k, h in enumerate(head) if h.startswith(column)]
        if not idx: continue
        if not any(cells): continue
        total += 1
        i = idx[0]
        if i >= len(cells) or not cells[i]: empty += 1
    return empty, total
def report(parts):
    """parts: [(이름, 상태, 오류, 설명)]. 단계별 상태를 나눠 출력하고, 필수 단계가 모두 통과면 0."""
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs: print('    ' + e)
        if required and state != '통과': ok = False
    return ok

with (root/'자료/targets.csv').open(encoding='utf-8-sig', newline='') as f:
    sop_ids = [r['sop_id'] for r in csv.DictReader(f)]
state, errs, n = check_rules(root/'결과/조건표.csv', sop_ids)
parts = [('조건표.csv', state, errs, f'규칙 묶음 {n}개' if n else '', True)]
for column, label in [('정한 내용', '사람이 정한 결정'), ('만드는 방법', '판단 입력'), ('판정', '사례 대조')]:
    empty, total = empty_rows(root/'결과/판단기록.md', column)
    if empty is None: parts.append(('판단기록.md', '없음', [], '', False)); break
    if total == 0 or empty == total: parts.append((f'판단기록.md {label}', '아직 비어 있음', [], f'「{column}」 칸을 채우세요', False))
    else: parts.append((f'판단기록.md {label}', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 빈 칸 {empty}개' if empty else f'행 {total}개', False))
print('구조 검사 결과')
ok = report(parts)
print('구조 검사는 형식만 봅니다. 경계·적용 대상·출처가 원문과 맞는지, 사례 판정이 원자료와 맞는지는 판단기록.md에서 별도로 대조하세요.')
sys.exit(0 if ok else 1)
