"""결과/조건표.csv의 구조 검사와 판단기록.md 기록 칸 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
의미(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)는 판정하지 않는다 — 원자료와 따로 대조한다.
사용: python check.py
"""
from pathlib import Path
import csv, sys
root = Path(__file__).resolve().parent
HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_manwon','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
TEXT = {'plc_mode': {'REMOTE_AUTO','REMOTE_MANUAL','LOCAL'}, 'plc_state': {'RUN','TRIP','STOP'}, 'skill_kind': {'control','work_order'}}
LIST_INPUTS = {'skill_code'}
INPUTS = NUMERIC | set(TEXT) | LIST_INPUTS
def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)
def check_table(path, sop_ids):
    """(상태, 오류 목록, 규칙 묶음 수, rule_id 집합). 상태: 없음 · 빈 틀 · 통과 · 확인 필요."""
    if not path.is_file(): return '없음', [], 0, set()
    header, table = read_csv(path)
    if header != HEADER: return '확인 필요', ['열 이름 · 순서가 계약과 다릅니다: ' + ','.join(header or [])], 0, set()
    if not table: return '빈 틀', [], 0, set()
    errs, groups = [], {}
    for line, r in enumerate(table, 2):
        at = f'{path.name}:{line}'
        if r['action'] not in sop_ids: errs.append(f'{at} targets.csv에 없는 action {r["action"]}')
        if r['logic'] != 'AND': errs.append(f'{at} logic은 AND입니다(OR는 다른 rule_id로 나눕니다).')
        if r['input'] not in INPUTS: errs.append(f'{at} 계약에 없는 input {r["input"]}')
        if r['operator'] not in OPS: errs.append(f'{at} 계약에 없는 operator {r["operator"]}')
        elif OPS[r['operator']] != r['boundary_included']: errs.append(f'{at} boundary_included({r["boundary_included"]})가 operator {r["operator"]}와 맞지 않습니다.')
        if r['input'] in LIST_INPUTS and r['operator'] != 'has_other_than': errs.append(f'{at} 목록 입력 {r["input"]}에는 has_other_than만 씁니다.')
        if r['operator'] == 'has_other_than' and r['input'] not in LIST_INPUTS: errs.append(f'{at} has_other_than은 목록 입력에만 씁니다.')
        if r['input'] in TEXT and r['operator'] in ('==', '!=') and r['value'] not in TEXT[r['input']]: errs.append(f'{at} {r["input"]}의 값 {r["value"]}은 계약에 없는 값입니다.')
        if r['input'] in NUMERIC:
            try: float(r['value'])
            except ValueError: errs.append(f'{at} 숫자 입력의 기준값이 숫자가 아닙니다.')
            if not r['unit']: errs.append(f'{at} 숫자 입력의 unit이 비었습니다.')
        if r['result'] not in {'WARN','PENALTY','EXCLUDE'}: errs.append(f'{at} result는 WARN · PENALTY · EXCLUDE 가운데 하나입니다.')
        if r['result'] == 'PENALTY':
            try: float(r['penalty_manwon'])
            except ValueError: errs.append(f'{at} PENALTY 행에 penalty_manwon이 없습니다.')
        elif r['penalty_manwon']: errs.append(f'{at} PENALTY가 아닌 행에 penalty_manwon이 있습니다.')
        if not r['reason'] or not r['source_section']: errs.append(f'{at} reason · source_section이 필요합니다.')
        key = (r['rule_id'], r['action']); head = (r['result'], r['penalty_manwon'], r['reason'], r['source_section'])
        g = groups.setdefault(key, {'head': head, 'index': []})
        if g['head'] != head: errs.append(f'{at} 같은 묶음 {key}의 result · penalty · reason · source가 다릅니다.')
        try: g['index'].append(int(r['condition_index']))
        except ValueError: errs.append(f'{at} condition_index가 정수가 아닙니다.')
    for key, g in groups.items():
        if sorted(g['index']) != list(range(1, len(g['index']) + 1)): errs.append(f'{path.name} 묶음 {key}: condition_index가 1부터 차례가 아닙니다: {g["index"]}')
    return ('확인 필요' if errs else '통과'), errs, len(groups), {k[0] for k in groups}
def table_rows(path, column):
    """마크다운 표에서 column으로 시작하는 칸이 있는 표의 (데이터 행 수, 그 칸이 빈 행 수)."""
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
def report(parts):
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs: print('    ' + e)
        if required and state != '통과': ok = False
    return ok
def record_part(path, column, label):
    got = table_rows(path, column)
    if got is None: return (f'{path.name} {label}', '없음', [], '', False)
    total, empty = got
    if total == 0 or empty == total: return (f'{path.name} {label}', '아직 비어 있음', [], f'「{column}」 칸을 채웁니다', False)
    return (f'{path.name} {label}', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 빈 칸 {empty}개' if empty else f'행 {total}개', False)

sop_ids = [r['sop_id'] for r in read_csv(root/'자료/targets.csv')[1]]
state, errs, n, _ = check_table(root/'결과/조건표.csv', sop_ids)
if state == '없음':
    print('아직 검사할 결과가 없습니다: 결과/조건표.csv')
print('구조 검사 결과')
ok = report([('조건표.csv', state, errs, f'규칙 묶음 {n}개' if n else '', True),
             record_part(root/'결과/판단기록.md', '고른 것', '정한 것'), record_part(root/'결과/판단기록.md', '맞은 규칙', '사례 대조'),
             record_part(root/'결과/판단기록.md', '승인 역할', '남은 후보와 실행 승인')])
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 조건표의 어느 행인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양만 봅니다. 의미와 질문별 답(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
