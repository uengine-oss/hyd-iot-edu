"""결과/조치검토결과.json·.md의 구조와 계약 불변식 검사, 기대결과.md 기록 칸 확인. 판정의 의미 정답은 판정하지 않는다."""
from pathlib import Path
from datetime import datetime
import csv, json, re, sys
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

def check_review(jpath, mpath):
    if not jpath.is_file(): return '없음', [], ''
    try: review = json.loads(jpath.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    md = mpath.read_text(encoding='utf-8-sig') if mpath.is_file() else ''
    errs = [] if md else ['조치검토결과.md가 없습니다.']
    if not str(review.get('비교_기준', '')).strip(): errs.append('비교_기준(교육용 비교값과 HYD 점수·실행 승인의 구분 문장)이 없습니다.')
    dec = review.get('입력_결정')
    if not isinstance(dec, list) or not dec or any(not (d.get('항목') and d.get('결정') and d.get('근거')) for d in dec): errs.append('입력_결정(판단 입력을 만든 결정: 항목·결정·근거)이 필요합니다.')
    items = review.get('항목')
    if not isinstance(items, list): return '확인 필요', errs + ['항목 목록이 없습니다.'], ''
    got = [i.get('id') for i in items]
    if got != list(alarms): errs.append(f'항목: 경보_목록.csv의 사례 순서·구성과 다릅니다(빠짐 {sorted(set(alarms)-set(got))}).')
    for item in items:
        iid = item.get('id')
        if iid not in alarms: continue
        cands = item.get('후보') or []
        if [c.get('sop') for c in cands] != alarms[iid]: errs.append(f'{iid}: 후보 목록이 경보_목록.csv와 다릅니다.')
        if md and not re.search(r'^#+\s.*(?<![A-Za-z0-9])'+re.escape(iid)+r'(?![A-Za-z0-9])', md, re.M): errs.append(f'조치검토결과.md에 {iid} 절 제목이 없습니다.')
        for c in cands:
            at = f'{iid}/{c.get("sop")}'
            inputs = c.get('입력')
            if not isinstance(inputs, dict): errs.append(f'{at}: 입력(판단 입력 값)이 필요합니다.')
            else:
                for k in RULE_INPUTS:
                    if k not in inputs: errs.append(f'{at}: 입력에 {k}가 없습니다(값이 없으면 null).')
                errs += unit_errors(at, inputs)
            status = c.get('판정')
            if status not in STATUS: errs.append(f'{at}: 판정은 유지·제외·보류'); continue
            reasons = c.get('이유')
            if not isinstance(reasons, list): errs.append(f'{at}: 이유 목록 필요'); continue
            for r in reasons:
                if (r.get('규칙'), c.get('sop')) not in rule_actions: errs.append(f'{at}: 조건표에 없는 규칙·후보 {r.get("규칙")}')
                if r.get('결과') not in {'WARN','PENALTY','EXCLUDE','미확인'}: errs.append(f'{at}: 이유의 결과는 WARN·PENALTY·EXCLUDE·미확인')
                if not r.get('비교') or not r.get('출처') or not isinstance(r.get('실제_입력'), dict): errs.append(f'{at} {r.get("규칙")}: 실제_입력·비교·출처가 필요합니다.')
                if r.get('결과') == '미확인' and (not r.get('빠진_입력') or not r.get('빠진_이유')): errs.append(f'{at} {r.get("규칙")}: 미확인에는 빠진_입력과 빠진_이유가 필요합니다.')
            kinds = {r.get('결과') for r in reasons}
            if status == '제외' and 'EXCLUDE' not in kinds: errs.append(f'{at}: 제외인데 EXCLUDE 이유가 없습니다.')
            if status == '보류' and ('EXCLUDE' in kinds or '미확인' not in kinds): errs.append(f'{at}: 보류는 제외 없이 미확인 이유가 있어야 합니다.')
            if status == '유지' and kinds & {'EXCLUDE', '미확인'}: errs.append(f'{at}: 유지인데 제외·미확인 이유가 있습니다.')
            if not c.get('원문_출처'): errs.append(f'{at}: 원문_출처가 비었습니다.')
            checks = c.get('추가_확인')
            if not isinstance(checks, list) or (status == '보류' and not checks): errs.append(f'{at}: 추가_확인 목록이 필요하고 보류 후보는 비어 있으면 안 됩니다.')
            missing = [m for r in reasons if r.get('결과') == '미확인' for m in r.get('빠진_입력', [])]
            if any(not any(m in str(x) for x in checks or []) for m in missing): errs.append(f'{at}: 빠진 입력 {missing}이 추가_확인에 없습니다.')
            approval = c.get('승인') or {}
            if not approval.get('역할') or not approval.get('출처') or not approval.get('안내'): errs.append(f'{at}: 승인(역할·출처·안내)이 필요합니다.')
            value, rank = c.get('비교값'), c.get('순위')
            if status != '유지':
                if value or rank is not None: errs.append(f'{at}: 비교값·순위는 유지 후보에만 둡니다.')
            elif value is not None:
                keys = ['비용','생산','품질','에너지','감점','합계']
                if not all(num(value.get(k)) for k in keys): errs.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.')
                elif abs(sum(value[k] for k in keys[:5]) - value['합계']) > 0.02: errs.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
            elif not c.get('비교_불가'): errs.append(f'{at}: 유지 후보에 비교값이 없으면 비교_불가 이유가 필요합니다.')
        opinion = item.get('검토_의견') or {}
        kept = [c for c in cands if c.get('판정') == '유지' and c.get('순위') is not None]
        top = sorted(c['sop'] for c in kept if c['순위'] == 1)
        if sorted(opinion.get('추천') or []) != top: errs.append(f'{iid}: 추천은 순위 1위 유지 후보여야 합니다.')
        if not opinion.get('사유'): errs.append(f'{iid}: 검토_의견.사유가 필요합니다(추천이 없으면 그 사유).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(items)}건'
state, errs, note = check_review(root/'결과/조치검토결과.json', root/'결과/조치검토결과.md')
parts = [('review.py', '있음' if (root/'결과/review.py').is_file() else '없음', [], '', False), ('조치검토결과.json·.md', state, errs[:40] + ([f'… 외 {len(errs)-40}건'] if len(errs) > 40 else []), note, True)]
empty, total = empty_rows(root/'결과/기대결과.md', '실제 결과')
if empty is None: parts.append(('기대결과.md', '없음', [], '', False))
elif total == 0: parts.append(('기대결과.md', '아직 비어 있음', [], '실행 전에 기대 칸을 먼저 채우세요', False))
else: parts.append(('기대결과.md', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 「실제 결과」 빈 칸 {empty}개' + (' — 실행 뒤 실제 결과를 적어 대조하세요' if empty else ''), False))
print('구조 검사 결과')
ok = report(parts)
print('구조 검사는 형식과 계약의 불변식만 봅니다. 판정·이유·출처가 원문·원자료와 맞는지와 금액은 별도로 대조하세요.')
sys.exit(0 if ok else 1)
