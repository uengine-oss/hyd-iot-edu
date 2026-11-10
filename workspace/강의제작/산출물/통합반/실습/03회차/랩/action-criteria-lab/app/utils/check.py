"""output/sop.json · condition_table.csv의 구조 검사와 정한 것 · 기대 판정 · 제공 파일 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
의미(조건 · 경계 · 출처가 원문과 맞는지, 사건의 판정)는 판정하지 않는다 — 원자료와 따로 대조한다. 모델 ID는 app/features/model/graph.json이 있으면 그것으로 본다.
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
 "app/ui/render.py": "794a7c0de17bbbf7dd6e2896397c1db32cb4079b6fe7dfa88dc67160c2a0d81e",
 "app/utils/actions.py": "f309fa62710b8b52339c99371c4b74c413cb55e6f0527d8ca0a9186841c71ff6",
 "app/utils/condition_tools.py": "d5c7daf0b405d1a68ad86cee7d3f84e4e1eb67149534601edbe75649ce936d91",
 "app/utils/results.py": "1c5b0596745e9ac1e9b7f06d84c7463d99720597edcf46801d32a51e640ae86b",
 "app/utils/sop_tools.py": "dab57265878012a0a6a87af1f2ebde6f9f72223b4fa1507c8002f39670c9756c",
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
def pick(name):
    # 검사의 기준 입력: app/features/model/에 같은 이름 파일이 있으면 그것, 없으면 제공 data/model/. 고른 파일을 찍는다(조용히 바꾸지 않는다).
    mine = root/'app/features/model'/name
    if mine.is_file():
        print(f'기준 입력: app/features/model/{name} (내 입력)')
        return mine
    if (root/'app/features/model').is_dir():
        print(f'기준 입력: data/model/{name} — app/features/model/에 {name}이 없어 제공 입력으로 봅니다')
    else:
        print(f'기준 입력: data/model/{name}')
    return root/'data/model'/name

sop_ids = [r['sop_id'] for r in read_csv(root/'data/targets.csv')[1]]
fm_ids = {r['failure_mode_id'] for r in read_csv(root/'data/failuremodes.csv')[1]}
graph = json.loads(pick('graph.json').read_text(encoding='utf-8-sig'))
kind_of = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
SLOT = {'assets': 'Asset', 'components': 'Component', 'sensors': 'Sensor'}
RELATIONS = {'MITIGATED_BY': ('failure_modes', 'sops'), 'REMEDIED_BY': ('failure_modes', 'sops'), 'ADDRESSES': ('sops', 'causes')}
def items(value, key):
    v = value.get(key)
    return v if isinstance(v, list) else None
def check_sop(path, rule_ids):
    if not path.is_file(): return '없음', [], ''
    try: sop = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    if not isinstance(sop, dict) or not sop.get('sops'): return '아직 비어 있음', [], ''
    errs, unconfirmed = [], []
    fms = [f.get('id') for f in sop.get('failure_modes') or [] if isinstance(f, dict)]
    causes = [c.get('id') for c in sop.get('causes') or [] if isinstance(c, dict)]
    for f in fms:
        if f not in fm_ids: errs.append(f'failure_modes {f}: failuremodes.csv에 없는 고장 유형 ID입니다.')
    for c in causes:
        if not isinstance(c, str) or not re.fullmatch(r'cause:[a-z0-9]+(-[a-z0-9]+)*', c): errs.append(f'causes {c}: 원인 ID는 cause:로 시작하는 영어 소문자 · 하이픈 이름입니다.')
    for name, ids in [('failure_modes', fms), ('causes', causes)]:
        for x in set(ids):
            if ids.count(x) > 1: errs.append(f'{name} {x}가 {ids.count(x)}번 있습니다.')
    found = [s.get('id') for s in sop['sops'] if isinstance(s, dict)]
    for sid in sop_ids:
        if found.count(sid) != 1: errs.append(f'{sid}가 {found.count(sid)}번 있습니다(1번이어야 합니다).')
    for s in sop['sops']:
        if not isinstance(s, dict): errs.append('sops의 항목이 객체가 아닙니다.'); continue
        sid = s.get('id')
        if sid not in sop_ids: errs.append(f'targets.csv에 없는 SOP {sid}')
        if not s.get('source'): errs.append(f'{sid}: 출처(source)가 없습니다.')
        if s.get('failure_mode') not in fms: errs.append(f'{sid}: 고장 유형 {s.get("failure_mode")}을 sop.json failure_modes에서 찾을 수 없습니다.')
        for key in ['apply_conditions', 'prohibitions', 'steps', 'completion']:
            value = items(s, key)
            if value is None: errs.append(f'{sid}: {key}는 목록이어야 합니다.'); continue
            for i, item in enumerate(value, 1):
                if not isinstance(item, dict) or not item.get('text') or not item.get('source'): errs.append(f'{sid}.{key}[{i}]: 내용(text) · 출처(source)가 필요합니다.'); continue
                for rid in item.get('rules') or []:
                    if rule_ids and rid not in rule_ids: errs.append(f'{sid}.{key}[{i}]: 조건표에 없는 규칙 {rid}')
        steps = [x.get('order') for x in items(s, 'steps') or [] if isinstance(x, dict)]
        if not steps or steps != list(range(1, len(steps) + 1)): errs.append(f'{sid}: 수행 단계(steps)의 순서가 1부터 차례가 아닙니다: {steps}')
        approval = s.get('approval')
        if not isinstance(approval, dict) or not approval.get('role') or not approval.get('source'): errs.append(f'{sid}: 승인(approval — role · source)이 필요합니다. 원문에서 승인을 찾지 못했으면 role을 「미확인」으로 시작하고 source에 찾아본 절을 적습니다.')
        elif str(approval['role']).startswith('미확인'): unconfirmed.append(sid)
        ref = s.get('model_refs')
        if not isinstance(ref, dict): errs.append(f'{sid}: 모델 참조(model_refs)는 객체여야 합니다.'); continue
        used = 0
        for slot, want in SLOT.items():
            for x in ref.get(slot) or []:
                used += 1
                if x not in kind_of: errs.append(f'{sid}: 모델에 없는 ID {x} (새 ID를 만들지 말고 not_linked에 까닭을 적습니다)')
                elif kind_of[x] != want: errs.append(f'{sid}: {slot} 자리에 {kind_of[x]} ID {x}가 있습니다.')
        if not used and not ref.get('not_linked'): errs.append(f'{sid}: 모델 참조(model_refs)가 비어 있습니다(걸 대상이 없으면 not_linked에 까닭을 적습니다).')
    ends = {'failure_modes': set(fms), 'sops': set(found), 'causes': set(causes)}
    rels = sop.get('relations')
    if not isinstance(rels, list) or not rels: errs.append('관계 목록(relations)이 비어 있습니다.')
    else:
        for i, r in enumerate(rels, 1):
            t = r.get('type') if isinstance(r, dict) else None
            if t not in RELATIONS: errs.append(f'relations[{i}]: type {t}은 계약의 셋(MITIGATED_BY · REMEDIED_BY · ADDRESSES) 가운데 하나가 아닙니다.'); continue
            a, b = RELATIONS[t]
            if r.get('from') not in ends[a]: errs.append(f'relations[{i}] {t}: 시작 {r.get("from")}이 sop.json {a}에 없습니다.')
            if r.get('to') not in ends[b]: errs.append(f'relations[{i}] {t}: 끝 {r.get("to")}이 sop.json {b}에 없습니다.')
            if not r.get('source'): errs.append(f'relations[{i}]: source가 필요합니다.')
    return ('확인 필요' if errs else '통과'), errs, f'SOP {len(found)}개 · 관계 {len(rels) if isinstance(rels, list) else 0}개' + (f' · 승인 미확인 {", ".join(unconfirmed)}' if unconfirmed else '')
t_state, t_errs, n, rule_ids = check_table(root/'app/features/condition_table.csv', sop_ids)
s_state, s_errs, s_note = check_sop(root/'output/sop.json', rule_ids)
if s_state == '없음':
    print('아직 검사할 결과가 없습니다: output/sop.json — python run.py classify가 판단 표로 만듭니다')
print('구조 검사 결과')
ok = report([('sop.json', s_state, s_errs, s_note, True), ('condition_table.csv', t_state, t_errs, f'규칙 묶음 {n}개' if n else '', True),
             chosen_part(root), expect_part(root), provided_part(root)])
ok = ok and s_state == '통과' and t_state == '통과'
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양만 봅니다. 의미와 질문별 답(조건 · 경계 · 출처가 원문과 맞는지, 사건의 판정)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
