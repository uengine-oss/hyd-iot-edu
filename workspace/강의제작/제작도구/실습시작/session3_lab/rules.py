"""결정표 읽기와 판정 — 제공 코드(일반 로직). 고치지 않는다.

결정표를 읽어 경보 한 건의 조치 후보마다 맞은 규칙을 모두 모은다(Hit Policy: Collect).
입력 값이 비어 맞는지 가릴 수 없는 조건은 「확인되지 않은 조건」이다. 제외 · 감점 규칙이면 그 후보는 제외 쪽으로, 경고 규칙이면 경고로 남긴다.
어느 후보가 허용인지는 이 파일에 없다. 결정표와 경보 표의 값이 정한다.
"""
from pathlib import Path
import csv
import io

from app.utils.results import Stop, read_text, rel

HERE = Path(__file__).resolve().parents[2]
RULE_COLUMNS = ['rule_id', '결과', '감점_만원', '적용_대상', '입력', '연산자', '기준값', '단위', '이유', '출처']
RESULTS = ('제외', '감점', '경고')
OPERATORS = ('>=', '>', '<=', '<', '==', '!=')
# 입력 데이터 이름(판단 시스템 결정표 내보내기의 id) → (경보 표의 칸, 숫자인가, 화면에 쓰는 이름). 예측 유온은 후보마다 칸이 다르다.
INPUTS = {
    'in:plc-mode': ('운전_모드', False, '운전 모드'),
    'in:fan100-hours': ('팬100_연속_h', True, '팬 100 % 연속 운전시간'),
    'in:forecast-ts1': ('예측_유온_{sop}_C', True, '조치 후 예측 유온'),
    'in:ts1': ('유온_C', True, '유온'),
    'in:ce': ('냉각효율_pct', True, '냉각 효율'),
}
STATUSES = ('허용', '제외')


def read_rows(path, columns=None):
    """CSV → [dict]. 줄마다 '_line'에 실제 파일 줄 번호를 붙인다. 첫머리 # 줄과 빈 줄은 건너뛴다. columns를 주면 열 이름이 같아야 한다."""
    text, _ = read_text(path)
    kept = [(no, x) for no, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')]
    if not kept:
        raise Stop(f'{rel(path)}: 열 이름 줄이 없습니다. 받은 빈 틀의 열 이름 줄을 지우지 않습니다.')
    reader = csv.reader(io.StringIO('\n'.join(x for _, x in kept)))
    head = [c.strip() for c in next(reader)]
    if columns is not None and head != list(columns):
        raise Stop(f'{rel(path)}:{kept[0][0]}: 열 이름이 ' + ','.join(columns) + ' 이어야 합니다(지금: ' + ','.join(head) + ').')
    rows = []
    for cells in reader:
        line = kept[reader.line_num - 1][0]
        if len(cells) != len(head):
            raise Stop(f'{rel(path)}:{line}: 칸이 {len(cells)}개입니다. 열 이름은 {len(head)}개입니다(쉼표가 든 값은 큰따옴표로 감쌉니다).')
        rows.append({**{k: v.strip() for k, v in zip(head, cells)}, '_line': line})
    return rows


def split(text):
    return [x.strip() for x in text.split(';') if x.strip()]


def load_rules(path):
    """결정표 → 규칙 목록. 같은 rule_id의 줄은 한 규칙의 조건들이고 모두 맞아야 그 규칙이 맞는다(AND). 꼴이 어긋나면 파일:줄을 짚고 멈춘다."""
    rules = {}
    for r in read_rows(path, RULE_COLUMNS):
        where = f'{rel(path)}:{r["_line"]}'
        if not r['rule_id']:
            raise Stop(f'{where}: rule_id가 비었습니다.')
        if r['입력'] not in INPUTS:
            raise Stop(f'{where}: 입력 「{r["입력"]}」은 이 표가 읽는 입력 데이터가 아닙니다. 쓸 수 있는 이름: ' + ' · '.join(INPUTS))
        if r['연산자'] not in OPERATORS:
            raise Stop(f'{where}: 연산자 「{r["연산자"]}」를 읽을 수 없습니다. 쓸 수 있는 연산자: ' + ' '.join(OPERATORS))
        value = r['기준값']
        if INPUTS[r['입력']][1]:
            try:
                value = float(value)
            except ValueError:
                raise Stop(f'{where}: 입력 {r["입력"]}의 기준값은 숫자여야 합니다(지금: 「{r["기준값"]}」).') from None
        elif r['연산자'] not in ('==', '!='):
            raise Stop(f'{where}: 글자 값인 입력 {r["입력"]}에는 == 또는 !=만 씁니다.')
        condition = {'input': r['입력'], 'operator': r['연산자'], 'value': value, 'unit': r['단위'], 'line': r['_line']}
        if r['rule_id'] not in rules:
            if r['결과'] not in RESULTS:
                raise Stop(f'{where}: 결과는 ' + ' · '.join(RESULTS) + f' 가운데 하나입니다(지금: 「{r["결과"]}」).')
            if not split(r['적용_대상']):
                raise Stop(f'{where}: 적용_대상이 비었습니다. 이 규칙을 댈 SOP ID를 적습니다(여럿이면 ;).')
            if (r['결과'] == '감점') != bool(r['감점_만원']):
                raise Stop(f'{where}: 감점_만원은 결과가 감점인 규칙에만, 그리고 반드시 적습니다.')
            penalty = None
            if r['감점_만원']:
                try:
                    penalty = float(r['감점_만원'])
                except ValueError:
                    raise Stop(f'{where}: 감점_만원은 숫자여야 합니다(지금: 「{r["감점_만원"]}」).') from None
            rules[r['rule_id']] = {'id': r['rule_id'], 'result': r['결과'], 'penalty': penalty, 'targets': split(r['적용_대상']),
                                   'reason': r['이유'], 'source': r['출처'], 'conditions': [condition], 'line': r['_line']}
            continue
        first = rules[r['rule_id']]
        if (split(r['적용_대상']) not in ([], first['targets']) or r['결과'] not in ('', first['result'])
                or r['이유'] not in ('', first['reason']) or r['출처'] not in ('', first['source'])):
            raise Stop(f'{where}: 같은 rule_id {r["rule_id"]}의 줄인데 결과 · 적용_대상 · 이유 · 출처가 첫 줄({first["line"]}줄)과 다릅니다. 같게 적거나 비워 둡니다.')
        first['conditions'].append(condition)
    return list(rules.values())


def value_of(row, name, sop):
    """경보 표 한 줄에서 입력 데이터 하나의 값. 칸이 없거나 비었으면 None(0이 아니다)."""
    column, numeric, _ = INPUTS[name]
    raw = (row.get(column.format(sop=sop)) or '').strip()
    if raw == '':
        return None
    if not numeric:
        return raw
    try:
        return float(raw)
    except ValueError:
        raise Stop(f'경보 {row.get("경보_ID")}의 {column.format(sop=sop)} 칸 값 「{raw}」이 숫자가 아닙니다.') from None


def holds(actual, condition):
    expected, op = condition['value'], condition['operator']
    if op == '>=':
        return actual >= expected
    if op == '>':
        return actual > expected
    if op == '<=':
        return actual <= expected
    if op == '<':
        return actual < expected
    return (actual == expected) if op == '==' else (actual != expected)


def judge(sop, row, rules):
    """후보 하나의 판정. hits = 조건이 모두 맞은 규칙, unknown = 거짓인 조건은 없고 값이 빈 조건이 있는 규칙(확인되지 않은 조건)."""
    hits, unknown = [], []
    for rule in rules:
        if sop not in rule['targets']:
            continue
        missing, false_found, seen = [], False, []
        for c in rule['conditions']:
            actual = value_of(row, c['input'], sop)
            if actual is None:
                missing.append(c['input'])
                continue
            seen.append({'input': c['input'], 'actual': actual, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit']})
            false_found = false_found or not holds(actual, c)
        if false_found:
            continue
        entry = {'rule_id': rule['id'], 'result': rule['result'], 'reason': rule['reason'], 'source': rule['source']}
        if rule['penalty'] is not None:
            entry['penalty'] = rule['penalty']
        if missing:
            unknown.append({**entry, 'missing': missing})
        else:
            hits.append({**entry, 'conditions': seen})
    excluded = any(h['result'] == '제외' for h in hits) or any(u['result'] in ('제외', '감점') for u in unknown)
    return {'sop': sop, 'status': '제외' if excluded else '허용', 'hits': hits, 'unknown': unknown}


def short(j):
    """판정 한 칸 — 「허용」 · 「허용 — 경고 R3, 감점 R2」 · 「제외 — 제외 R1」 · 「제외 — 확인되지 않은 조건 R2(팬 100 % 연속 운전시간)」."""
    parts = [f'{h["result"]} {h["rule_id"]}' for h in j['hits']]
    parts += [f'확인되지 않은 조건 {u["rule_id"]}(' + ' · '.join(INPUTS[m][2] for m in u['missing']) + ')' for u in j['unknown']]
    return j['status'] + (' — ' + ', '.join(parts) if parts else '')


def rule_ids(j):
    """그 후보에 걸린 규칙 이름(맞은 규칙과 확인되지 않은 조건으로 남은 규칙) — 기대와 견줄 때 쓰는 꼴."""
    return norm_ids(';'.join([h['rule_id'] for h in j['hits']] + [u['rule_id'] for u in j['unknown']]))


def norm_ids(text):
    return ' · '.join(sorted(split(text)))


def names(doc):
    """SOP 구조에서 이름 → id 찾기 표(고장 유형, 원인)."""
    fm = {f['name']: f['id'] for f in doc['failure_modes']}
    cause = {c['name']: c['id'] for f in doc['failure_modes'] for c in f['causes']}
    return fm, cause


def candidates(row, doc):
    """경보 한 건의 조치 후보 — [(SOP ID, 후보인가, 후보가 아닌 까닭)].
    고장 유형에 이어진 SOP 가운데, 원인이 정해진 SOP는 확인된 원인이 같을 때만, 그리고 그 설비에 걸린 SOP만 후보다."""
    fm_ids, cause_ids = names(doc)
    fm = fm_ids.get(row.get('고장_유형', ''))
    if fm is None:
        raise Stop(f'경보 {row.get("경보_ID")}의 고장_유형 「{row.get("고장_유형")}」이 고장 유형 목록에 없습니다.')
    cause = cause_ids.get(row.get('확인된_원인', ''))
    cause_name = {v: k for k, v in cause_ids.items()}
    linked = {r['to'] for r in doc['relations'] if r['type'] in ('MITIGATED_BY', 'REMEDIED_BY') and r['from'] == fm}
    out = []
    for sop in doc['sops']:
        if sop['id'] not in linked:
            continue
        needs = [r['to'] for r in doc['relations'] if r['type'] == 'ADDRESSES' and r['from'] == sop['id']]
        if needs and cause not in needs:
            out.append((sop['id'], False, '원인이 ' + ' · '.join(cause_name.get(n, n) for n in needs) + f'일 때 쓰는 조치 방법(확인된 원인: {row.get("확인된_원인") or "빈 값"})'))
        elif row['설비'] not in sop['assets']:
            out.append((sop['id'], False, f'{row["설비"]}에 걸지 않은 SOP'))
        else:
            out.append((sop['id'], True, ''))
    return out
