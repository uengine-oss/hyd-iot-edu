"""결과/result.json의 구조와 계약 불변식 검사, 기대결과.md 기록 칸 확인. 어떤 규칙이 맞아야 하는지·금액은 판정하지 않는다."""
from pathlib import Path
from datetime import datetime
import csv, json, re, sys
root = Path(__file__).resolve().parent
import re
HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_만원','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
LIST_INPUTS = {'skill_code'}
INPUTS = NUMERIC | {'plc_mode','plc_state','skill_kind'} | LIST_INPUTS
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
        if r['input'] in LIST_INPUTS and r['operator'] != 'has_other_than': errs.append(f'{at} 목록 입력 {r["input"]}에는 has_other_than만 씁니다(목록과 글자를 {r["operator"]}로 비교하지 않음).')
        if r['operator'] == 'has_other_than' and r['input'] not in LIST_INPUTS: errs.append(f'{at} has_other_than은 목록 입력({", ".join(sorted(LIST_INPUTS))})에만 씁니다.')
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
def excerpt_rules(path):
    """규칙 발췌(규칙_원문.txt)에 실린 규칙 ID."""
    return re.findall(r"^\s*\['(rule:[A-Za-z0-9_-]+)'", path.read_text(encoding='utf-8-sig'), re.M) if path.is_file() else []
def section_text(path, word):
    """마크다운에서 제목에 word가 들어 있는 절의 본문."""
    if not path.is_file(): return ''
    out, on = [], False
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('#'): on = word in line; continue
        if on: out.append(line)
    return '\n'.join(out)
def mentioned(rid, text):
    return re.search(re.escape(rid) + r'(?![A-Za-z0-9_-])', text) is not None
def unused_rules(rules_path, excerpt_path, record_path, word):
    """규칙 발췌의 규칙 중 조건표 source_section에도, 기록의 결정 절에도 이름이 없는 것. 옳고 그름은 판정하지 않는다."""
    if not rules_path.is_file(): return []
    with rules_path.open(encoding='utf-8-sig', newline='') as f: used = ' '.join(r.get('source_section') or '' for r in csv.DictReader(f))
    if not used.strip(): return []
    note = section_text(record_path, word)
    return [rid for rid in excerpt_rules(excerpt_path) if not mentioned(rid, used) and not mentioned(rid, note)]
def missing_kinds(path, column, kinds):
    """kinds: [(종류 이름, [찾을 말…])]. 표의 column 칸 어디에서도 찾을 말이 없는 종류 이름. 표에 행이 없으면 빈 목록."""
    if not path.is_file(): return []
    head, seen = None, []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('|'): head = None; continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if head is None: head = cells; continue
        if set(''.join(cells)) <= set('-: '): continue
        idx = [k for k, h in enumerate(head) if h.startswith(column)]
        if idx and idx[0] < len(cells) and any(cells): seen.append(cells[idx[0]])
    text = ' '.join(seen)
    if not text.strip(): return []
    return [name for name, words in kinds if not any(w in text for w in words)]
def expect_time(path):
    """기대결과.md 머리의 「기대 칸을 쓴 시각」과 「실행 시각」 정보."""
    if not path.is_file(): return []
    text = path.read_text(encoding='utf-8-sig')
    def when(label):
        m = re.search(r'^- ' + label + r'[^:\n]*:[ \t]*(.*)$', text, re.M)
        if not m or not m.group(1).strip(): return None, False
        x = re.search(r'(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})', m.group(1))
        return (f'{x.group(1)} {int(x.group(2)):02d}:{x.group(3)}' if x else None), True
    e, e_filled = when('기대 칸을 쓴 시각'); r, _ = when('실행 시각')
    if not e_filled: return ['기대결과.md 「기대 칸을 쓴 시각」이 비어 있습니다. 실행 전에 기대 칸을 쓰고 그 시각을 적으세요.']
    if e and r and e > r: return [f'기대결과.md 기대 칸을 쓴 시각({e})이 실행 시각({r})보다 뒤입니다. 실행 출력을 보고 기대를 쓰지 않았는지 확인하세요.']
    return []
def notes(lines):
    for line in lines: print('참고: ' + line)
def report(parts):
    """parts: [(이름, 상태, 오류, 설명)]. 단계별 상태를 나눠 출력하고, 필수 단계가 모두 통과면 0."""
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs: print('    ' + e)
        if required and state != '통과': ok = False
    return ok

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
alarms = {r['사례']: r['후보'].split(';') for r in rows(root/'자료/경보_목록.csv')}
rule_actions = {(r['rule_id'], r['action']) for r in rows(root/'입력/rules.csv')}
RULE_INPUTS = {r['input'] for r in rows(root/'입력/rules.csv')}
STATUS = {'유지','제외','보류'}
def num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
UNIT_RANGE = {'forecast_ts1': (0, 150, '℃'), 'forecast_ps1': (50, 300, 'bar'), 'fan100_hours': (0, 24*40, 'h')}
def unit_errors(at, inputs):
    out = []
    for k, (lo, hi, unit) in UNIT_RANGE.items():
        v = inputs.get(k)
        if num(v) and not lo <= v <= hi: out.append(f'{at}: {k}={v}는 계약 단위 {unit}의 범위({lo}~{hi})를 벗어납니다. 원천 단위 환산을 확인하세요.')
    return out

def check_result(path):
    if not path.is_file(): return '없음', [], ''
    try: result = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    errs = []
    if not str(result.get('comparison_basis', '')).strip(): errs.append('comparison_basis(교육용 비교값과 HYD 점수의 구분 문장)가 없습니다.')
    dec = result.get('input_decisions')
    if not isinstance(dec, list) or not dec or any(not (d.get('항목') and d.get('결정') and d.get('근거')) for d in dec): errs.append('input_decisions(판단 입력을 만든 결정: 항목·결정·근거)가 필요합니다.')
    events = result.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [e.get('id') for e in events]
    if got != list(alarms): errs.append(f'events: 경보_목록.csv의 사례 순서·구성과 다릅니다(빠짐 {sorted(set(alarms)-set(got))}, 더함 {sorted(set(got)-set(alarms))}).')
    for e in events:
        eid = e.get('id'); cands = e.get('candidates') or []
        if eid in alarms and [c.get('sop') for c in cands] != alarms[eid]: errs.append(f'{eid}: 후보 목록이 경보_목록.csv와 다릅니다.')
        for c in cands:
            at = f'{eid}/{c.get("sop")}'
            inputs, reasons = c.get('inputs'), c.get('missing_reasons')
            if not isinstance(inputs, dict) or not isinstance(reasons, dict): errs.append(f'{at}: inputs와 missing_reasons가 필요합니다.'); continue
            for k in RULE_INPUTS:
                if k not in inputs: errs.append(f'{at}: inputs에 {k}가 없습니다(값이 없으면 null).')
                elif inputs[k] is None and not reasons.get(k): errs.append(f'{at}: {k}가 null인데 missing_reasons에 이유가 없습니다.')
            errs += unit_errors(at, inputs)
            if c.get('status') not in STATUS: errs.append(f'{at}: status는 유지·제외·보류'); continue
            lists = {k: c.get(k) for k in ['warnings','penalties','exclusions','unknown']}
            if any(not isinstance(v, list) for v in lists.values()): errs.append(f'{at}: warnings·penalties·exclusions·unknown은 목록'); continue
            for k in ['warnings','penalties','exclusions']:
                for h in lists[k]:
                    if (h.get('rule_id'), c.get('sop')) not in rule_actions: errs.append(f'{at}: 조건표에 없는 규칙·후보 {h.get("rule_id")}')
                    if not h.get('source_section') or not isinstance(h.get('conditions'), list) or not h['conditions']: errs.append(f'{at} {h.get("rule_id")}: source_section과 conditions(실제 입력·비교)가 필요')
            for h in lists['penalties']:
                if not num(h.get('amount_만원')): errs.append(f'{at} {h.get("rule_id")}: amount_만원 숫자 필요')
            for u in lists['unknown']:
                if not u.get('missing'): errs.append(f'{at} {u.get("rule_id")}: unknown에는 빠진 입력 이름(missing)이 필요')
            if lists['exclusions'] and c['status'] != '제외': errs.append(f'{at}: 제외 사유가 있는데 status가 {c["status"]}입니다.')
            if not lists['exclusions'] and lists['unknown'] and c['status'] != '보류': errs.append(f'{at}: 제외 없이 미확인이 있는데 status가 {c["status"]}입니다.')
            if not lists['exclusions'] and not lists['unknown'] and c['status'] != '유지': errs.append(f'{at}: 제외·미확인이 없는데 status가 {c["status"]}입니다.')
            comp = c.get('comparison')
            if c['status'] != '유지':
                if comp: errs.append(f'{at}: 유지가 아닌 후보에 비교값이 있습니다.')
            elif comp is None:
                if not c.get('comparison_unavailable'): errs.append(f'{at}: 비교값이 없으면 comparison_unavailable 이유가 필요합니다.')
            else:
                keys = ['비용','생산','품질','에너지','감점','합계']
                if not all(num(comp.get(k)) for k in keys): errs.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.'); continue
                if abs(sum(comp[k] for k in keys[:5]) - comp['합계']) > 0.02: errs.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
                if abs(sum(p['amount_만원'] for p in lists['penalties'] if num(p.get('amount_만원'))) - comp['감점']) > 0.001: errs.append(f'{at}: 감점이 penalties 금액 합과 다릅니다.')
        ranking = e.get('ranking'); rec = e.get('recommendation') or {}
        if not isinstance(ranking, list): errs.append(f'{eid}: ranking 목록 필요'); continue
        kept = {c.get('sop') for c in cands if c.get('status') == '유지' and c.get('comparison')}
        if sorted(r.get('sop') for r in ranking) != sorted(kept): errs.append(f'{eid}: ranking에는 비교값이 있는 유지 후보만 모두 있어야 합니다.')
        totals = [r.get('합계') for r in ranking]
        if totals != sorted(totals): errs.append(f'{eid}: ranking이 합계 오름차순이 아닙니다.')
        for i, r in enumerate(ranking):
            tie = i > 0 and ranking[i-1].get('합계') == r.get('합계')
            if r.get('rank') != (ranking[i-1].get('rank') if tie else i+1): errs.append(f'{eid}: 순위 {r.get("sop")}가 동순위 규칙(1,1,3)과 다릅니다.')
        top = sorted(r.get('sop') for r in ranking if r.get('rank') == 1)
        if sorted(rec.get('sops') or []) != top: errs.append(f'{eid}: recommendation.sops는 1위 유지 후보여야 합니다.')
        if not rec.get('reason'): errs.append(f'{eid}: recommendation.reason이 필요합니다(추천이 없으면 그 사유).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_result(root/'결과/result.json')
parts = [('judge.py', '있음' if (root/'결과/judge.py').is_file() else '없음', [], '', False), ('result.json', state, errs[:40] + ([f'… 외 {len(errs)-40}건'] if len(errs) > 40 else []), note, True)]
empty, total = empty_rows(root/'결과/기대결과.md', '실제 결과')
if empty is None: parts.append(('기대결과.md', '없음', [], '', False))
elif total == 0: parts.append(('기대결과.md', '아직 비어 있음', [], '실행 전에 기대 칸을 먼저 채우세요', False))
else: parts.append(('기대결과.md', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 「실제 결과」 빈 칸 {empty}개' + (' — 실행 뒤 실제 결과를 적어 대조하세요' if empty else ''), False))
print('구조 검사 결과')
ok = report(parts)
kinds = missing_kinds(root/'결과/기대결과.md', '사례 종류', [('정상', ['정상']), ('경계', ['경계']), ('복수 조건', ['복수']), ('모두 제외·유지 후보 없음', ['모두 제외', '유지 후보 없음', '추천 없음']), ('값 없음', ['값 없음', '누락', '미확인']), ('결정에 따라 바뀌는 사례', ['결정', '갈래', '갈림'])])
notes(([f'START.md 사례 종류 중 기대결과.md 「사례 종류」 칸에서 찾지 못한 것: {", ".join(kinds)} (다른 말로 적었다면 그대로 두어도 됩니다).'] if kinds else []) + expect_time(root/'결과/기대결과.md'))
print('구조 검사는 형식과 계약의 불변식만 봅니다. 어떤 규칙이 맞아야 하는지와 금액은 원문·원자료·지표_정의.md 손계산과 별도로 대조하세요.')
sys.exit(0 if ok else 1)
