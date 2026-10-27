"""결과/sop.json과 결과/rules.csv의 구조 검사. 의미 정답은 판정하지 않는다."""
from pathlib import Path
import csv, json, sys
root = Path(__file__).resolve().parent
errors = []
HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_만원','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
INPUTS = NUMERIC | {'plc_mode','plc_state','skill_kind','skill_code'}
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)
_, targets = rows(root/'자료/targets.csv')
sop_ids = [t['sop_id'] for t in targets]
_, fms = rows(root/'자료/failuremodes.csv')
graph = json.loads((root/'입력/graph.json').read_text(encoding='utf-8-sig'))
model_ids = {n['props']['id'] for n in graph['nodes']}
def refs(value):
    if isinstance(value, str): yield value
    elif isinstance(value, list):
        for v in value: yield from refs(v)
    elif isinstance(value, dict):
        for v in value.values(): yield from refs(v)
try:
    sop = json.loads((root/'결과/sop.json').read_text(encoding='utf-8-sig'))
    fm_ids = {f['reference_id'] for f in fms} | {f.get('id') for f in sop.get('고장유형', [])}
    items = sop.get('SOP', [])
    found = [s.get('id') for s in items]
    for sid in sop_ids:
        if found.count(sid) != 1: errors.append(f'sop.json: {sid}가 {found.count(sid)}번 있습니다(1번이어야 함).')
    for s in items:
        sid = s.get('id')
        if sid not in sop_ids: errors.append(f'sop.json: targets.csv에 없는 SOP {sid}')
        if not s.get('출처'): errors.append(f'sop.json {sid}: 출처 없음')
        for key in ['적용_조건','금지_조건','수행_단계','완료_기준']:
            value = s.get(key)
            if not isinstance(value, list): errors.append(f'sop.json {sid}: {key}는 목록이어야 합니다.'); continue
            for i, item in enumerate(value, 1):
                if not isinstance(item, dict) or not item.get('내용') or not item.get('출처'):
                    errors.append(f'sop.json {sid}.{key}[{i}]: 내용·출처가 필요합니다.')
        steps = [x.get('순서') for x in s.get('수행_단계') or [] if isinstance(x, dict)]
        if not steps or steps != list(range(1, len(steps)+1)): errors.append(f'sop.json {sid}: 수행_단계 순서가 1부터 연속이 아닙니다: {steps}')
        approval = s.get('승인')
        if not isinstance(approval, dict) or not approval.get('역할') or not approval.get('출처'): errors.append(f'sop.json {sid}: 승인(역할·출처)이 필요합니다.')
        if s.get('고장유형') not in fm_ids: errors.append(f'sop.json {sid}: 고장유형 {s.get("고장유형")}을 찾을 수 없습니다.')
        for ref in refs(s.get('모델_참조', {})):
            if ref not in model_ids: errors.append(f'sop.json {sid}: 모델에 없는 ID {ref} (새 ID를 만들지 말고 미기재로 남기세요)')
        if not list(refs(s.get('모델_참조', {}))): errors.append(f'sop.json {sid}: 모델_참조가 비어 있습니다.')
    for f in sop.get('고장유형', []):
        for ref in refs(f.get('모델_참조', {})):
            if ref not in model_ids: errors.append(f'sop.json 고장유형 {f.get("id")}: 모델에 없는 ID {ref}')
except (OSError, ValueError, TypeError, AttributeError) as e:
    errors.append(f'sop.json: {e}')
groups = {}
try:
    header, table = rows(root/'결과/rules.csv')
    if header != HEADER: errors.append('rules.csv 열 이름·순서가 계약과 다릅니다: '+','.join(header or []))
    elif not table: errors.append('rules.csv에 규칙 행이 없습니다.')
    for line, r in enumerate(table if header == HEADER else [], 2):
        at = f'rules.csv:{line}'
        if r['action'] not in sop_ids: errors.append(f'{at} targets.csv에 없는 action {r["action"]}')
        if r['logic'] != 'AND': errors.append(f'{at} logic은 AND')
        if r['input'] not in INPUTS: errors.append(f'{at} 계약에 없는 input {r["input"]}')
        if r['operator'] not in OPS: errors.append(f'{at} 계약에 없는 operator {r["operator"]}')
        elif OPS[r['operator']] != r['boundary_included']: errors.append(f'{at} boundary_included({r["boundary_included"]})가 operator {r["operator"]}와 맞지 않습니다.')
        if r['result'] not in {'WARN','PENALTY','EXCLUDE'}: errors.append(f'{at} result는 WARN·PENALTY·EXCLUDE')
        if r['input'] in NUMERIC:
            try: float(r['value'])
            except ValueError: errors.append(f'{at} 숫자 입력의 기준값이 숫자가 아닙니다.')
            if not r['unit']: errors.append(f'{at} 숫자 입력의 unit이 비었습니다.')
        if r['result'] == 'PENALTY':
            try: float(r['penalty_만원'])
            except ValueError: errors.append(f'{at} PENALTY에 penalty_만원이 없습니다.')
        elif r['penalty_만원']: errors.append(f'{at} PENALTY가 아닌 행에 penalty_만원이 있습니다.')
        if not r['reason'] or not r['source_section']: errors.append(f'{at} reason·source_section이 필요합니다.')
        key = (r['rule_id'], r['action'])
        head = (r['result'], r['penalty_만원'], r['reason'], r['source_section'])
        g = groups.setdefault(key, {'head': head, 'index': []})
        if g['head'] != head: errors.append(f'{at} 같은 묶음 {key}의 result·penalty·reason·source가 다릅니다.')
        try: g['index'].append(int(r['condition_index']))
        except ValueError: errors.append(f'{at} condition_index가 정수가 아닙니다.')
    for key, g in groups.items():
        if sorted(g['index']) != list(range(1, len(g['index'])+1)): errors.append(f'rules.csv 묶음 {key}: condition_index가 1부터 연속이 아닙니다: {g["index"]}')
except (OSError, ValueError) as e:
    errors.append(f'rules.csv: {e}')
if errors:
    print('구조 확인 필요'); print('\n'.join(errors)); sys.exit(1)
print(f'구조 검사 통과: SOP {len(items)}개, 규칙 묶음 {len(groups)}개. 원문의 의미·경계·적용 대상은 결과/사례대조.md에서 원문과 별도로 대조하세요.')
