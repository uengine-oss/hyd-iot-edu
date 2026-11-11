"""app/features/condition_table.csv · approvals.csv의 구조 검사와 정한 것 · 기대 판정 · 제공 파일 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
의미(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)는 판정하지 않는다 — 원자료와 따로 대조한다.
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
 "app/utils/actions.py": "f49f6e8174d187d4d1819baeeebc0cf1f5545bebe5cf5d3083b5ac269e66b9fe",
 "app/utils/condition_tools.py": "d5c7daf0b405d1a68ad86cee7d3f84e4e1eb67149534601edbe75649ce936d91",
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
HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_manwon','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
TEXT = {'plc_mode': {'REMOTE_AUTO','REMOTE_MANUAL','LOCAL'}, 'plc_state': {'RUN','TRIP','STOP'}, 'skill_kind': {'control','work_order'}}
LIST_INPUTS = {'skill_code'}
INPUTS = NUMERIC | set(TEXT) | LIST_INPUTS
def check_table(path, sop_ids):
    """(상태, 오류 목록, 규칙 묶음 수, rule_id 집합). 상태: 없음 · 아직 비어 있음 · 통과 · 확인 필요."""
    if not path.is_file(): return '없음', [], 0, set()
    header, table, skip = csv_rows(path)
    if header != HEADER: return '확인 필요', [f'{path.name}:{skip + 1} 열 이름 · 순서가 계약과 다릅니다: ' + ','.join(header or [])], 0, set()
    if not table: return '아직 비어 있음', [], 0, set()
    errs, groups = [], {}
    for line, r in enumerate(table, skip + 2):
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

sop_ids = [r['sop_id'] for r in read_csv(root/'data/targets.csv')[1]]
def approval_part():
    p = root/'app/features/approvals.csv'
    if not p.is_file(): return ('approvals.csv', '없음 — 받은 ZIP의 빈 틀을 지우지 않습니다', [], '', True)
    head, rows, skip = csv_rows(p)
    if head != ['sop_id', '승인_역할', '원문']: return ('approvals.csv', '확인 필요', ['열 이름이 sop_id,승인_역할,원문이 아닙니다.'], '', True)
    if not rows: return ('approvals.csv', '아직 비어 있음', [], '', False)
    errs = []
    for n, r in enumerate(rows, skip + 2):
        if r['sop_id'] not in sop_ids: errs.append(f'approvals.csv:{n} targets.csv에 없는 SOP {r["sop_id"]}')
        if not r['승인_역할'].strip(): errs.append(f'approvals.csv:{n} 승인_역할이 비었습니다(찾지 못했으면 「미확인」으로 시작).')
        if not re.fullmatch(r'\s*(data/hm8_manual\.md:)?\d+(\s*;\s*(data/hm8_manual\.md:)?\d+)*\s*', r['원문'] or ''): errs.append(f'approvals.csv:{n} 원문은 data/hm8_manual.md의 줄 번호(45 또는 data/hm8_manual.md:45, ;로 나눔)입니다.')
    for s in sop_ids:
        if [r['sop_id'] for r in rows].count(s) > 1: errs.append(f'approvals.csv: {s}가 두 줄 이상입니다.')
    return ('approvals.csv', '확인 필요' if errs else '통과', errs, f'행 {len(rows)}개', True)
state, errs, n, _ = check_table(root/'app/features/condition_table.csv', sop_ids)
print('구조 검사 결과')
ok = report([('condition_table.csv', state, errs, f'규칙 묶음 {n}개' if n else '', True), approval_part(), chosen_part(root), expect_part(root), provided_part(root)])
ok = ok and state == '통과'
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양만 봅니다. 의미와 질문별 답(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
