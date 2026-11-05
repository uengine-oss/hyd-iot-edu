"""조건표 읽기와 판정 — 제공 코드(일반 로직). 고치지 않는다.

조건표(13열 계약)를 읽어 후보마다 맞은 경고 · 감점 · 제외를 모두 모으고, 입력이 없어 맞는지 알 수 없는 규칙을 미확인으로 남긴다
(`자료/작업기준.md` 4절: 제외가 있으면 제외, 제외 없이 미확인이 있으면 보류, 아니면 유지). 규칙은 조건표에서만 읽는다.
사건 메모 · 확인 사례 · 판단 시스템 결정표 내보내기를 읽는 도우미와, 원문 줄을 찾는 도우미도 여기에 있다.
"""
from __future__ import annotations

from pathlib import Path
import csv
import io
import re

OPERATORS = {'>=', '>', '<=', '<', '==', '!=', 'has_other_than'}
NUMERIC = {'forecast_ts1', 'forecast_ps1', 'fan100_hours'}
INPUTS = ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state', 'skill_kind', 'skill_code']
RESULTS = {'WARN', 'PENALTY', 'EXCLUDE'}
BOUNDARY = {'>=': '예', '<=': '예', '>': '아니오', '<': '아니오', '==': '해당없음', '!=': '해당없음', 'has_other_than': '해당없음'}
HEADER = ['rule_id', 'action', 'condition_index', 'logic', 'input', 'operator', 'value', 'unit', 'boundary_included', 'result', 'penalty_manwon', 'reason', 'source_section']
CASE_INPUT = {'운전_모드': 'plc_mode', '상태': 'plc_state', '팬100_연속': 'fan100_hours', '예측_TS1': 'forecast_ts1', '예측_PS1': 'forecast_ps1'}


class ContractError(Exception):
    """계약과 다른 입력 — 파일 · 줄을 밝혀 멈춘다."""


def csv_body(path):
    """(첫머리 # 줄을 뺀 글, 뺀 줄 수) — 「제공 빈 틀」 표시 줄은 데이터가 아니다."""
    lines = Path(path).read_text(encoding='utf-8-sig').splitlines(keepends=True)
    skip = 0
    while skip < len(lines) and lines[skip].lstrip().startswith('#'):
        skip += 1
    return ''.join(lines[skip:]), skip


def read_csv(path):
    """CSV → [dict]. 첫머리 # 줄은 건너뛴다."""
    return list(csv.DictReader(io.StringIO(csv_body(path)[0], newline='')))


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def load_table(path):
    """(rule_id, action) 묶음. 계약과 다르면 파일 · 행을 밝혀 멈춘다."""
    path = Path(path)
    body, skip = csv_body(path)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != HEADER:
        raise ContractError(f'{path.parent.name}/{path.name}:{skip + 1} 열 이름 · 순서가 계약과 다름: {",".join(reader.fieldnames or [])}')
    table = list(reader)
    groups = {}
    for line, row in enumerate(table, start=skip + 2):
        where = f'{path.parent.name}/{path.name}:{line}'
        if row['logic'] != 'AND':
            raise ContractError(f'{where} logic은 AND만: {row["logic"]}')
        if row['operator'] not in OPERATORS or row['result'] not in RESULTS:
            raise ContractError(f'{where} 계약에 없는 연산자 · 결과: {row["operator"]} / {row["result"]}')
        if BOUNDARY[row['operator']] != row['boundary_included']:
            raise ContractError(f'{where} 경계 표시가 연산자와 다름: {row["operator"]} / {row["boundary_included"]}')
        if row['input'] not in INPUTS:
            raise ContractError(f'{where} 계약에 없는 입력 {row["input"]}')
        key = (row['rule_id'], row['action'])
        head = {k: row[k] for k in ['result', 'penalty_manwon', 'reason', 'source_section']}
        g = groups.setdefault(key, {'rule_id': key[0], 'action': key[1], **head, 'conditions': [], 'lines': []})
        if any(g[k] != v for k, v in head.items()):
            raise ContractError(f'{where} 같은 묶음 {key}의 결과 · 감점 · 이유 · 출처가 다름')
        try:
            index = int(row['condition_index'])
        except ValueError:
            raise ContractError(f'{where} condition_index가 정수가 아님: {row["condition_index"]}') from None
        g['conditions'].append({'index': index, 'input': row['input'], 'operator': row['operator'], 'value': row['value'], 'unit': row['unit']})
        g['lines'].append(line)
    for g in groups.values():
        g['conditions'].sort(key=lambda c: c['index'])
        if [c['index'] for c in g['conditions']] != list(range(1, len(g['conditions']) + 1)):
            raise ContractError(f'{path.parent.name}/{path.name} 묶음 {g["rule_id"]}/{g["action"]}의 condition_index가 1부터 차례가 아님')
    return groups


def load_targets(path):
    """targets.csv의 후보 — kind · codes 칸이 있는 판(판정 랩 · 실전 02-5)."""
    return {r['sop_id']: {'skill_kind': r['kind'], 'skill_code': [c for c in r['codes'].split(';') if c], 'name': r['name'], 'source_section': r['source_section']}
            for r in read_csv(path)}


def test(c, actual):
    op, expected = c['operator'], c['value']
    if op == 'has_other_than':
        return any(code != expected for code in actual)
    if c['input'] in NUMERIC:
        a, b = float(actual), float(expected)
        return {'>=': a >= b, '>': a > b, '<=': a <= b, '<': a < b, '==': a == b, '!=': a != b}[op]
    return {'==': actual == expected, '!=': actual != expected}[op]


def evaluate(sop, inputs, groups):
    """맞은 규칙은 모두 모은다(Hit Policy 모으기). 거짓인 조건이 하나라도 있으면 그 규칙은 불일치, 아니고 값 없는 조건이 있으면 미확인."""
    out = {'sop': sop, 'warnings': [], 'penalties': [], 'exclusions': [], 'unknown': [], 'rules': []}
    for g in sorted((g for g in groups.values() if g['action'] == sop), key=lambda g: g['rule_id']):
        evidence, missing, false_found = [], [], False
        for c in g['conditions']:
            actual = inputs.get(c['input'])
            if actual is None or actual == []:
                missing.append(c['input'])
                evidence.append({'input': c['input'], 'actual': None, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit']})
                continue
            holds = test(c, actual)
            false_found = false_found or not holds
            evidence.append({'input': c['input'], 'actual': actual, 'operator': c['operator'], 'value': c['value'], 'unit': c['unit']})
        state = '불일치' if false_found else ('미확인' if missing else '일치')
        out['rules'].append({'rule_id': g['rule_id'], 'result': g['result'], 'state': state})
        if state == '미확인':
            out['unknown'].append({'rule_id': g['rule_id'], 'result': g['result'], 'missing': missing, 'source_section': g['source_section']})
        elif state == '일치':
            hit = {'rule_id': g['rule_id'], 'reason': g['reason'], 'source_section': g['source_section'], 'conditions': evidence}
            if g['result'] == 'WARN':
                out['warnings'].append(hit)
            elif g['result'] == 'EXCLUDE':
                out['exclusions'].append(hit)
            else:
                out['penalties'].append({**hit, 'penalty_manwon': float(g['penalty_manwon'])})
    out['status'] = '제외' if out['exclusions'] else ('보류' if out['unknown'] else '유지')
    return out


def short(j):
    """판정 한 줄 — 「유지 경고 R3 감점 R2」."""
    return j['status'] + ''.join(f' {k} ' + ','.join(h['rule_id'] for h in j[key]) for k, key in (('경고', 'warnings'), ('감점', 'penalties'), ('제외', 'exclusions')) if j[key]) \
        + (' 미확인 ' + ','.join(u['rule_id'] for u in j['unknown']) if j['unknown'] else '')


# ───────────── 자료 읽기 도우미 ─────────────
def case_inputs(path, kinds):
    """확인_사례.csv(긴 꼴) → {사례: {후보: 판단 입력}}. kinds = {후보: (skill_kind, skill_code 목록)}. 빈 값은 None 그대로."""
    cases = {}
    for line, r in enumerate(read_csv(path), start=2):
        c = cases.setdefault(r['사례'], {'common': {}, 'fc': {}})
        key = CASE_INPUT.get(r['입력'])
        if key is None:
            raise ContractError(f'{Path(path).name}:{line} 계약에 없는 입력 이름 {r["입력"]}')
        value = (float(r['값']) if key in NUMERIC else r['값']) if r['값'] else None
        if r['후보']:
            c['fc'].setdefault(r['후보'], {})[key] = value
        else:
            c['common'][key] = value
    out = {}
    for cid, c in cases.items():
        out[cid] = {sop: {'forecast_ts1': None, 'forecast_ps1': None, **c['common'], **c['fc'].get(sop, {}), 'skill_kind': k, 'skill_code': list(codes)}
                    for sop, (k, codes) in kinds.items()}
    return out


def memo_inputs(text, kinds):
    """사건 메모(HMI에서 옮겨 적은 글) → {후보: 판단 입력}. 팬 연속 시간은 마지막 카운터 기록에 판정 요청까지 지난 시간을 더한 값(수집_설명.md 팬 카운터)."""
    from datetime import datetime

    def grab(pat):
        m = re.search(pat, text, re.M)
        if not m:
            raise ContractError(f'사건 메모에서 찾지 못함: {pat}')
        return m.groups()
    req = grab(r'^- (\d\d:\d\d:\d\d) 조치 판단 요청')[0]
    mode, state = grab(r'^- 운전 모드 (\S+), 상태 (\S+)')
    t_cnt, kind, minutes = grab(r'^- 마지막 기록: (\S+ \S+) 「(\S+)」 (\d+)분')
    day = t_cnt.split()[0]
    age = (datetime.fromisoformat(f'{day}T{req}+09:00') - datetime.fromisoformat(t_cnt.replace(' ', 'T') + '+09:00')).total_seconds() / 60
    fan = 0.0 if kind == '종료' else round((float(minutes) + age) / 60, 2)
    out = {}
    for sop, (k, codes) in kinds.items():
        m = re.search(rf'^\| {sop} \| ([0-9.]+) ℃ \| ([0-9.]+) bar', text, re.M)
        out[sop] = {'forecast_ts1': float(m.group(1)) if m else None, 'forecast_ps1': float(m.group(2)) if m else None, 'fan100_hours': fan,
                    'plc_mode': mode, 'plc_state': state, 'skill_kind': k, 'skill_code': list(codes)}
    return out


def export_rules(path):
    """판단 시스템 결정표 내보내기의 「규칙」 절 → [{줄, id, 조건식, 결과, 감점, 설명, 대상, 출처}]."""
    rows, head, section = [], None, None
    for no, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if line.startswith('## '):
            section, head = line[3:].strip(), None
            continue
        if section != '규칙' or not line.strip() or line.startswith('#'):
            continue
        cells = [c.strip() for c in line.split(' | ')]
        if head is None:
            head = cells
            continue
        r = dict(zip(head, cells))
        rows.append({'줄': no, 'id': r['id'], '조건식': r['조건식'], '결과': r['결과'], '감점': r['감점(만원)'], '설명': r['설명'], '대상': r['대상'], '출처': r['출처']})
    return rows


MANUAL = 'HM-8_매뉴얼.md'
SENTENCE = re.compile(r'(?<=\.)\s+')
RULE_REF = re.compile(r'rule:[a-z0-9-]+')            # 출처 칸의 결정표 규칙 ID(괄호 · 파일:줄이 붙어도 ID만)
SOURCE_FORMS = ('받는 꼴: 절 「HM-8.<절>」, SOP 단계 「HM-8.<절> SOP-<ID> 단계 <n>」, 승인 「HM-8.<절> SOP-<ID> 승인」(문서 이름 · 판은 붙이지 않음), '
                '자료 파일의 줄 「파일:줄」, 결정표에서 가져온 행은 「판단 시스템 결정표 rule:<id>」(원문 줄이 없는 조각으로 남음)')


def manual_lines(lab):
    """매뉴얼 줄마다 (절, SOP, 단계 번호 또는 '승인' 또는 None, 본문 글)."""
    sec = sop = None
    out = {}
    for no, line in enumerate((Path(lab)/'자료'/MANUAL).read_text(encoding='utf-8').splitlines(), 1):
        if m := re.match(r'## (HM-\d+\.\d+) ', line):
            sec, sop = m.group(1), None
            out[no] = (sec, None, None, line[3:])
            continue
        if m := re.match(r'### (SOP-[A-Z]+-\d+) ', line):
            sop = m.group(1)
            out[no] = (sec, sop, None, line[4:])
            continue
        if sop and (m := re.match(r'(\d+)\. (.+)', line)):
            out[no] = (sec, sop, int(m.group(1)), m.group(2))
        elif sop and line.startswith('승인'):
            out[no] = (sec, sop, '승인', line)
        else:
            out[no] = (sec, sop if line.strip() else None, None, line.lstrip('- ').strip())
    return out


def sentences(lab):
    """원문 줄 · 문장 목록 — 판단 표의 「원문」 칸에 쓰는 번호(줄 또는 줄.문장)와 그 글."""
    rows = []
    for no, (sec, sop, step, text) in manual_lines(lab).items():
        if not text or text.startswith('#') or sec is None:
            continue
        parts = SENTENCE.split(text)
        for i, s in enumerate(parts, 1):
            rows.append({'원문': f'{no}' if len(parts) == 1 else f'{no}.{i}', '절': sec, 'SOP': sop or '', '단계': step if isinstance(step, int) else (step or ''), '글': s})
    return rows


def source_parts(lab, source):
    """출처 칸(;로 나눈 조각)마다 (조각, 원문 줄 번호 또는 None, 원문 글 또는 까닭). 매뉴얼의 절 · SOP 단계 · 승인 줄, 또는 자료의 「파일:줄」."""
    lines = manual_lines(lab)
    secs = {v[0]: no for no, v in lines.items() if v[0] and v[1] is None and v[3].startswith(v[0])}
    steps = {(v[1], v[2]): no for no, v in lines.items() if v[1] and v[2] is not None}
    out = []
    for part in [p.strip() for p in source.split(';') if p.strip()]:
        part = part[len('자료/'):] if part.startswith('자료/') else part
        m = re.fullmatch(r'(HM-8\.\d+)(?: (SOP-[A-Z]+-\d+) (?:단계 (\d+)|(승인)))?', part)
        f = re.fullmatch(r'([^:]+):(\d+)', part)
        if m:
            sec, sid, st, _ = m.groups()
            no = steps.get((sid, int(st) if st else '승인')) if sid else secs.get(sec)
            out.append((part, no, lines[no][3] if no else '원문에서 찾지 못함'))
        elif f and (Path(lab)/'자료'/f.group(1)).is_file():
            text = (Path(lab)/'자료'/f.group(1)).read_text(encoding='utf-8').splitlines()
            no = int(f.group(2))
            out.append((part, no if 1 <= no <= len(text) else None, text[no - 1] if 1 <= no <= len(text) else '그 줄이 없음'))
        elif part.startswith('판단 시스템 결정표 ') and RULE_REF.fullmatch(part[len('판단 시스템 결정표 '):]):
            out.append((part, None, '결정표 규칙 — 받은 원문에 그 줄이 없음'))
        else:
            out.append((part, None, f'받은 원문 줄로 찾지 못함 — {SOURCE_FORMS}'))
    return out


SECTION = re.compile(r'^## (HM-\d+\.\d+) ')


def manual_sections(path):
    """매뉴얼의 절 번호 → 머리 줄 번호."""
    return {m.group(1): no for no, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1) if (m := SECTION.match(line))}


def export_facts(lab):
    """내보내기 규칙마다 사실만: 출처 칸의 절이 현행 · 1.0판 원문에 절 머리로 있는가(판정 · 처리 제안 없음)."""
    d = Path(lab)/'자료'
    now = manual_sections(d/'HM-8_매뉴얼.md')
    old = manual_sections(d/'HM-8_1.0판_매뉴얼.md') if (d/'HM-8_1.0판_매뉴얼.md').is_file() else None
    out = []
    for r in export_rules(d/'판단시스템_결정표_내보내기.txt'):
        refs = [x.strip() for x in r['출처'].split(';') if x.strip()]
        where = []
        for ref in refs:
            got = []
            if ref in now:
                got.append(f'현행 {now[ref]}줄')
            if old is not None and ref in old:
                got.append(f'1.0판 {old[ref]}줄')
            where.append(f'{ref}: ' + (' · '.join(got) if got else '제공 원문에 그 절 머리 없음'))
        out.append({**r, '출처_절': '; '.join(where)})
    return out
