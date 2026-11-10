"""제공 코드 — 검토한 문서 지식을 랩 DB에 잇고 조회하는 일반 로직. 누가 해도 같은 일만 한다: 입력 읽기 · 설비 모델과 조치 기준 적재 ·
MERGE 문장 만들기와 실행 · 세기 · 내보내기 · 조회 실행 · 카드 글 쓰기 · 추가 자료가 필요한 질문 파일 쓰기. 그래프의 모양 · 무엇을 어느 기존 ID에 이을지 ·
어떤 종류를 어느 카드 항목에 둘지 · 다른 문서의 조건을 이을지 · 현재값을 어디서 읽을지 · 무엇을 물을지는
app/features/의 정할 자리(graph_shape.json · link_rules.csv · aliases.csv · other_doc_conditions.csv · roles.csv · current_value_sources.csv · query_values.csv)에 내가 적은 대로만 한다.
정할 자리가 비었거나 꼴이 틀리면 그 파일 · 칸과 함께 멈춘다(다른 값으로 대신하지 않는다). 이 파일은 고치지 않는다 — run.py가 부른다.
"""
from __future__ import annotations

from pathlib import Path
import csv
import io
import json
import re

HERE = Path(__file__).resolve().parents[2]
RESULT = HERE / 'output'
MARK = '제공 빈 틀'
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
SHAPE_KEYS = ('문서', '판', '절', '지식', '문서의_판', '판의_절', '지식의_출처', '판의_대체', '규칙의_근거')
ID_KEYS = ('문서', '판', '절', '지식')
SLOTS = {'문서', '판', '절', '후보'}
METHODS = ('절차 표기와 같은 조치', '정한 대상', '별칭', '잇지 않음')
ROLE_WORDS = ('준비', '금지', '순서', '완료', '승인', '넣지 않음')
KINDS = ('step', 'precondition', 'prohibition', 'completion', 'unit_value')


class Problem(Exception):
    def __init__(self, where, message):
        super().__init__(f'{where}: {message}')
        self.where, self.message = where, message


# ───────────── 읽기 ─────────────
def read(path):
    raw = Path(path).read_bytes()
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise Problem(str(path), 'UTF-8 · CP949 어느 쪽으로도 읽히지 않음')


def csv_rows(path):
    lines = [x for x in read(path).splitlines() if x.strip() and not x.startswith('#') and not (MARK in x and ',' not in x)]
    return [{(k or '').strip(): (v or '').strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO('\n'.join(lines)))]


def basis(rel):
    mine = HERE / 'app/features/my_inputs' / rel
    return mine if mine.exists() else HERE / 'data' / rel


def register():
    return csv_rows(HERE / 'data/documents/catalog.csv')


def model_ids():
    graph = json.loads(read(basis('model/graph.json')))
    sop = json.loads(read(basis('sop.json')))
    ids = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    ids |= {x['id']: 'FailureMode' for x in sop['failure_modes']} | {x['id']: 'Cause' for x in sop['causes']}
    for s in sop['sops']:
        ids[s['id']] = 'Skill'
        ids |= {f'{s["id"]}:{st["order"]}': 'Step' for st in s['steps']}
    ids |= {r['rule_id']: 'Rule' for r in csv_rows(basis('conditions.csv'))}
    return ids, graph, sop


def reviews():
    """[(파일 이름, 검토 결과)] — 기준 입력의 검토 결과(selected_task.json 제외)."""
    return [(f.name, json.loads(read(f))) for f in sorted(basis('reviews').glob('*_review.json'))]


# ───────────── 정할 자리 ─────────────
def shape():
    """app/features/graph_shape.json — 비었으면 None, 꼴이 틀리면 Problem."""
    where = 'app/features/graph_shape.json'
    path = HERE / 'app/features/graph_shape.json'
    if not path.is_file():
        raise Problem(where, '파일이 없습니다 — 받은 ZIP에서 다시 꺼냅니다')
    try:
        data = json.loads(read(path))
    except ValueError as e:
        raise Problem(where, f'JSON으로 읽지 못함({e})')
    names, means, ids = data.get('이름') or {}, data.get('뜻') or {}, data.get('ID') or {}
    keep = data.get('판을_따로_둠')
    if not any(str(v).strip() for v in list(names.values()) + list(ids.values())) and keep is None:
        return None
    if keep not in (True, False):
        raise Problem(f'{where} 「판을_따로_둠」', 'true 또는 false')
    need = [k for k in SHAPE_KEYS if not (k in ('판', '문서의_판', '판의_대체') and not keep)]
    existing, _, _ = model_ids()
    taken = set(existing.values()) | {'Skill', 'Step', 'Rule', 'FailureMode', 'Cause'}
    for k in need:
        v = str(names.get(k) or '').strip()
        if not NAME.match(v):
            raise Problem(f'{where} 「이름」 「{k}」', f'{v!r} — 영문자로 시작하는 영문 · 숫자 · _ 이름')
        if k in ('문서', '판', '절', '지식') and v in taken:
            raise Problem(f'{where} 「이름」 「{k}」', f'{v}는 설비 모델 · 조치 기준이 이미 다른 뜻으로 쓰는 종류 이름')
        if not str(means.get(k) or '').strip():
            raise Problem(f'{where} 「뜻」 「{k}」', '뜻이 비어 있음 — 그래프를 다시 여는 사람이 같은 뜻으로 읽게 적습니다')
    for k in ID_KEYS:
        if k == '판' and not keep:
            continue
        t = str(ids.get(k) or '').strip()
        slots = set(re.findall(r'\{([^}]*)\}', t))
        if not t or not slots:
            raise Problem(f'{where} 「ID」 「{k}」', f'{t!r} — {{문서}} {{판}} {{절}} {{후보}} 자리로 짓는 꼴')
        if slots - SLOTS:
            raise Problem(f'{where} 「ID」 「{k}」', f'모르는 자리 {sorted(slots - SLOTS)}')
    return {'이름': {k: str(names.get(k) or '').strip() for k in SHAPE_KEYS}, '뜻': {k: str(means.get(k) or '').strip() for k in SHAPE_KEYS},
            '판을_따로_둠': keep, 'ID': {k: str(ids.get(k) or '').strip() for k in ID_KEYS}}


def make_id(template, doc, rev, sec='', cand=''):
    return template.replace('{문서}', doc).replace('{판}', rev).replace('{절}', sec).replace('{후보}', cand)


def slot_rows(name, columns, keys=None):
    """app/features/<name> — [(줄 번호, 행)]. 줄 번호는 파일의 실제 줄(「#」 줄 · 빈 줄도 센다). 열 이름 · 칸 수가 틀리면 그 파일:줄로 멈춘다.
    keys에 든 칸이 모두 빈 행은 건너뛴다(빈 줄처럼)."""
    rel = f'app/features/{name}'
    path = HERE / 'app/features' / name
    if not path.is_file():
        raise Problem(rel, '파일이 없습니다 — 받은 ZIP에서 다시 꺼냅니다')
    kept = [(n, x) for n, x in enumerate(read(path).splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')]
    if not kept:
        return []
    head_n, head = kept[0]
    got = [c.strip() for c in next(csv.reader([head]))]
    if got != list(columns):
        raise Problem(f'{rel}:{head_n}', f'열 이름 · 순서가 {",".join(columns)}이어야 함(지금 {",".join(got)})')
    out = []
    for n, line in kept[1:]:
        vals = next(csv.reader([line]))
        if len(vals) != len(columns):
            raise Problem(f'{rel}:{n}', f'칸 {len(vals)}개 — 열 {len(columns)}개({",".join(columns)})와 같아야 함(글 안의 쉼표는 칸 전체를 큰따옴표로 감쌈)')
        row = {k: v.strip() for k, v in zip(columns, vals)}
        if any(row[k] for k in (keys or columns)):
            out.append((n, row))
    return out


def no_twice(rel, rows, key, what):
    """같은 짝이 두 줄이면 뒤 줄이 앞 줄을 조용히 덮으므로 두 줄 번호를 대고 멈춘다."""
    seen = {}
    for n, r in rows:
        k = key(r)
        if k in seen:
            raise Problem(f'{rel}:{seen[k]} · {n}', f'같은 {what}({" ".join(x for x in k if x)})이 두 줄 — 한 줄로 합칩니다')
        seen[k] = n


def basis_ok(text):
    """근거 칸에 원문 파일:줄(또는 계약 절)이 있는가 — 꼴만 본다."""
    return bool(re.search(r'[^\s:]+:\d+', text or '')) or 'data/contract' in (text or '')


def basis_lines(text):
    """근거 칸의 (data/documents/ 아래 파일 이름, 줄) — 「 · 」 또는 「;」로 이은 여러 값. data/documents/ 앞머리는 떼고 읽는다."""
    out = []
    for part in re.split(r'\s*[;·]\s*', text or ''):
        m = re.match(r'^(?:data/documents/)?([^\s:]+):(\d+)', part.strip())
        if m:
            out.append((m.group(1), int(m.group(2))))
    return out


def review_keys():
    return {(str(d['doc_id']), str(d.get('rev') or '')) for _, d in reviews()}


def role_rows():
    rows = slot_rows('roles.csv', ('종류', '인용에_든_글자', '항목', '근거'))
    for n, r in rows:
        where = f'app/features/roles.csv:{n}'
        if r['종류'] not in KINDS:
            raise Problem(where, f'종류 {r["종류"]!r} — {" · ".join(KINDS)} 중 하나')
        if r['항목'] not in ROLE_WORDS:
            raise Problem(where, f'항목 {r["항목"]!r} — {" · ".join(ROLE_WORDS)} 중 하나')
        if not r['근거']:
            raise Problem(where, '근거가 비어 있음')
    no_twice('app/features/roles.csv', rows, lambda r: (r['종류'], r['인용에_든_글자']), '종류 · 글자')
    return [r for _, r in rows]


ROLE_DEFAULT = {}   # 종류마다 계약의 기본 항목 — 실전 카드 랩의 app/utils/actions가 채운다(roles.csv는 기본과 다르게 둘 것만). 비어 있으면 roles.csv에 맞는 행만 쓴다


def role_of(c, roles):
    for r in roles:
        if r['종류'] == c['kind'] and (not r['인용에_든_글자'] or r['인용에_든_글자'] in c['quote']):
            return r['항목']
    return ROLE_DEFAULT.get(c['kind'])


def alias_rows(known):
    rows = slot_rows('aliases.csv', ('원문_이름', '기존_ID', '근거'))
    for n, r in rows:
        where = f'app/features/aliases.csv:{n}'
        if not r['원문_이름']:
            raise Problem(where, '원문_이름이 비어 있음')
        if not r['기존_ID']:
            raise Problem(where, '기존_ID가 비어 있음')
        for t in r['기존_ID'].split():
            if t not in known:
                raise Problem(where, f'기존_ID {t!r}는 설비 모델 · SOP 구조 · 조건표에 없는 ID(여럿이면 빈칸으로 띄움)')
        if not basis_ok(r['근거']):
            raise Problem(where, '근거에 원문 파일:줄이 없음')
    no_twice('app/features/aliases.csv', rows, lambda r: (r['원문_이름'],), '원문_이름')
    return [r for _, r in rows]


def link_rows(known):
    """app/features/link_rules.csv — 문서 · 판은 검토 결과의 짝, 절은 비우면 그 문서 전체. 아직 정하지 않은 문서는 행을 두지 않는다."""
    rows = slot_rows('link_rules.csv', ('문서', '판', '절', '잇는_방법', '관계', '대상', '까닭', '근거'), keys=('잇는_방법', '관계', '대상', '까닭', '근거'))
    have = review_keys()
    for n, r in rows:
        where = f'app/features/link_rules.csv:{n}'
        if not r['잇는_방법']:
            raise Problem(where, '잇는_방법이 비어 있음 — ' + ' · '.join(METHODS) + ' 중 하나')
        if (r['문서'], r['판']) not in have:
            raise Problem(where, f'문서 · 판 {r["문서"]!r} {r["판"]!r}는 읽은 검토 결과(app/features/my_inputs/reviews가 있으면 그것, 없으면 data/reviews)에 없는 짝 — 검토 결과의 doc_id · rev 그대로')
        if r['잇는_방법'] not in METHODS:
            raise Problem(where, f'잇는_방법 {r["잇는_방법"]!r} — {" · ".join(METHODS)} 중 하나')
        if r['잇는_방법'] != '잇지 않음' and not NAME.match(r['관계']):
            raise Problem(where, f'관계 {r["관계"]!r} — 영문 관계 이름')
        if r['잇는_방법'] == '정한 대상':
            if not r['대상']:
                raise Problem(where, '정한 대상이면 대상(기존 ID, 여럿이면 빈칸으로)이 필요')
            for t in r['대상'].split():
                if t not in known:
                    raise Problem(where, f'대상 {t!r}는 설비 모델 · SOP 구조 · 조건표에 없는 ID')
        if not r['까닭'] or not basis_ok(r['근거']):
            raise Problem(where, '까닭이 비었거나 근거에 원문 파일:줄이 없음')
    no_twice('app/features/link_rules.csv', rows, lambda r: (r['문서'], r['판'], r['절']), '문서 · 판 · 절')
    return [r for _, r in rows]


def other_rows(known):
    """app/features/other_doc_conditions.csv — 다른 문서의 조건을 이 작업에 이을지(잇는다 예 · 아니오). 아니오도 고른 것이라 행으로 남긴다."""
    rows = slot_rows('other_doc_conditions.csv', ('문서', '판', '절', '인용에_든_글자', '작업', '잇는다', '관계', '근거'))
    have = review_keys()
    for n, r in rows:
        where = f'app/features/other_doc_conditions.csv:{n}'
        for k in ('문서', '판', '절', '인용에_든_글자', '작업', '잇는다', '근거'):
            if not r[k]:
                raise Problem(where, f'{k}가 비어 있음')
        if (r['문서'], r['판']) not in have:
            raise Problem(where, f'문서 · 판 {r["문서"]!r} {r["판"]!r}는 읽은 검토 결과(app/features/my_inputs/reviews가 있으면 그것, 없으면 data/reviews)에 없는 짝 — 검토 결과의 doc_id · rev 그대로')
        if r['잇는다'] not in ('예', '아니오'):
            raise Problem(where, f'잇는다 {r["잇는다"]!r} — 예 또는 아니오')
        if known.get(r['작업']) != 'Skill':
            raise Problem(where, f'작업 {r["작업"]!r}는 SOP 구조의 조치 ID가 아님')
        if r['잇는다'] == '예' and not NAME.match(r['관계']):
            raise Problem(where, f'관계 {r["관계"]!r} — 영문 관계 이름')
        if not basis_ok(r['근거']):
            raise Problem(where, '근거에 원문 파일:줄이 없음')
    no_twice('app/features/other_doc_conditions.csv', rows, lambda r: (r['문서'], r['판'], r['절'], r['인용에_든_글자'], r['작업']), '문서 · 판 · 절 · 글자 · 작업')
    return [r for _, r in rows]


def now_rows():
    rows = slot_rows('current_value_sources.csv', ('작업', '확인할_값', '읽을_원천', '근거'))
    for n, r in rows:
        for k in ('작업', '확인할_값', '읽을_원천', '근거'):
            if not r[k]:
                raise Problem(f'app/features/current_value_sources.csv:{n}', f'{k}가 비어 있음')
    no_twice('app/features/current_value_sources.csv', rows, lambda r: (r['작업'], r['확인할_값']), '작업 · 확인할_값')
    return [r for _, r in rows]


ASKS = {('q1', 'asset'): 'Asset', ('q3', 'sop'): 'Skill', ('q3', 'asset'): 'Asset', ('q4', 'doc'): '문서', ('q5_target', 'target'): None,
        ('q5_section', 'section'): None, ('hold', 'ids'): '후보', ('card', 'sop'): 'Skill', ('card_other', 'sop'): 'Skill'}


def ask_values():
    """app/features/query_values.csv — {질문: {이름: 값}}. 모르는 질문 · 이름 짝, 같은 짝 두 줄, 꼴이 틀린 값은 그 줄로 멈춘다.
    q5(제공되지 않은 것을 묻는 자리)의 값은 일부러 없는 것을 물으므로 보지 않는다."""
    rows = slot_rows('query_values.csv', ('질문', '이름', '값'))
    known = model_ids()[0]
    docs = {k for k, _ in review_keys()}
    cands = {fname: {c['id'] for c in d['candidates']} for fname, d in reviews()}
    out, seen = {}, {}
    for n, r in rows:
        where = f'app/features/query_values.csv:{n}'
        pair = (r['질문'], r['이름'])
        if pair not in ASKS:
            raise Problem(where, f'질문 · 이름 {r["질문"]!r} {r["이름"]!r} — data/contract.md 「정할 자리」의 짝 가운데 하나')
        if pair in seen:
            raise Problem(f'app/features/query_values.csv:{seen[pair]} · {n}', f'같은 짝 {r["질문"]} {r["이름"]}이 두 줄 — 한 줄로 합칩니다')
        seen[pair] = n
        if not r['값']:
            continue
        kind = ASKS[pair]
        if kind == 'Asset' and known.get(r['값']) != 'Asset':
            raise Problem(where, f'{r["값"]!r}는 설비 모델의 설비 ID가 아님')
        if kind == 'Skill' and known.get(r['값']) != 'Skill':
            raise Problem(where, f'{r["값"]!r}는 SOP 구조의 조치 ID가 아님')
        if kind == '문서' and r['값'] not in docs:
            raise Problem(where, f'{r["값"]!r}는 data/reviews의 문서 식별자가 아님')
        if kind == '후보':
            for t in r['값'].split():
                f, _, i = t.partition('#')
                if f not in cands or i not in cands[f]:
                    raise Problem(where, f'{t!r} — 검토 결과 파일 이름#후보 id(data/reviews의 파일과 그 안의 후보 id), 여럿이면 빈칸으로')
        out.setdefault(r['질문'], {})[r['이름']] = r['값']
    return out


def expect_rows(items=None):
    """app/features/expected.csv — [행]. items가 있으면 질문 칸은 그 항목 이름(카드 항목), 없으면 「질문 1」 ~ 「질문 5」로 시작. 근거는 파일:줄."""
    rows = slot_rows('expected.csv', ('질문', '기대_답', '근거'))
    for n, r in rows:
        where = f'app/features/expected.csv:{n}'
        if items is not None and r['질문'] not in items:
            raise Problem(where, f'질문 칸 {r["질문"]!r} — 카드 항목 이름(' + ' · '.join(f'「{x}」' for x in items) + ') 가운데 하나')
        if items is None and not re.match(r'^질문 [1-5](\s|$)', r['질문']):
            raise Problem(where, f'질문 칸 {r["질문"]!r} — 「질문 1」 ~ 「질문 5」로 시작(한 질문을 여러 줄로 나누면 뒤에 무엇인지 짧게)')
        if not r['기대_답']:
            raise Problem(where, '기대_답이 비어 있음(없으면 「없음」)')
        if not basis_ok(r['근거']):
            raise Problem(where, '근거에 원문 파일:줄이 없음')
    no_twice('app/features/expected.csv', rows, lambda r: (r['질문'],), '질문 칸')
    return [r for _, r in rows]


# ───────────── 적재 ─────────────
def q(v):
    return json.dumps(v, ensure_ascii=False)


def props(d):
    return '{' + ', '.join(f'`{k}`: {q(v)}' for k, v in d.items() if v is not None) + '}'


def linked_docs(rules):
    """연결 규칙에서 잇는 방법을 정한 (문서, 판) — 이것만 적재한다(아직 정하지 않은 문서는 다음에)."""
    return sorted({(r['문서'], r['판']) for r in rules})


def plan_links(sh, rules, aliases, others, roles, known):
    """승인 후보마다 (지식 ID, 후보, 검토 파일, [(관계, 대상 ID, 속성)]) — 연결 규칙대로. 맞는 규칙이 없거나 잇지 않음이면 출처 절에만 잇는다."""
    out, notes = [], []
    reg = {(r['문서 식별자'], r['판']): r for r in register()}
    docs = set(linked_docs(rules))
    skills = {k for k, v in known.items() if v == 'Skill'}
    for fname, data in reviews():
        key = (str(data['doc_id']), str(data.get('rev') or ''))
        if key not in docs:
            continue
        mine = [r for r in rules if (r['문서'], r['판']) == key]
        for c in data['candidates']:
            if c.get('status') != 'approved':
                continue
            by_proc = next((r for r in mine if r['잇는_방법'] == '절차 표기와 같은 조치' and r.get('절') in ('', None, c['section'])), None) if c.get('procedure') in skills else None
            rule = by_proc or next((r for r in mine if r.get('절') and r['절'] == c['section']), None) or next((r for r in mine if not r.get('절')), None)
            role = role_of(c, roles)
            links = []
            if rule and rule['잇는_방법'] == '절차 표기와 같은 조치':
                proc = c.get('procedure')
                step = f'{proc}:{c.get("order")}' if c['kind'] == 'step' and c.get('order') else None
                if step and step in known:
                    links.append((rule['관계'], step, {'role': '순서'}))
                elif proc in skills:
                    links.append((rule['관계'], proc, {'role': role}))
            elif rule and rule['잇는_방법'] == '정한 대상':
                for t in rule['대상'].split():
                    links.append((rule['관계'], t, {'role': role} if known.get(t) == 'Skill' else {}))
            elif rule and rule['잇는_방법'] == '별칭':
                for a in aliases:
                    if a['원문_이름'] in c['quote']:
                        for t in a['기존_ID'].split():
                            links.append((rule['관계'], t, {'role': role} if known.get(t) == 'Skill' else {}))
            for o in others:
                if o['잇는다'] == '예' and (o['문서'], o['판'], o['절']) == (key[0], key[1], c['section']) and o['인용에_든_글자'] in c['quote']:
                    links.append((o['관계'], o['작업'], {'role': role}))
            seen, uniq = set(), []
            for rel, t, p in links:
                if (rel, t) not in seen:
                    seen.add((rel, t))
                    uniq.append((rel, t, p))
            if any(known.get(t) == 'Skill' and not p.get('role') for _, t, p in uniq):
                notes.append(f'{fname}#{c["id"]}({c["kind"]}): roles.csv에 맞는 행이 없어 조치에 이을 때 항목을 정하지 못함')
            kid = make_id(sh['ID']['지식'], key[0], key[1], c['section'], c['id'])
            out.append((kid, c, fname, data, uniq))
    return out, notes


def load_statements(sh, planned):
    """문서 · 판 · 절 · 지식과 연결 — MERGE · SET만. 돌려주는 값: (문장 목록, 같은 ID에 서로 다른 대상이 겹친 목록)."""
    n = sh['이름']
    reg = {(r['문서 식별자'], r['판']): r for r in register()}
    out, owners = [], {}
    def own(i, what):
        owners.setdefault(i, set()).add(what)
    docs_done, revs_done, secs_done = set(), set(), set()
    for kid, c, fname, data, links in planned:
        doc, rev = str(data['doc_id']), str(data.get('rev') or '')
        row = reg.get((doc, rev), {})
        did = make_id(sh['ID']['문서'], doc, rev)
        own(did, f'문서 {doc}')
        if did not in docs_done:
            docs_done.add(did)
            out.append(f'MERGE (d:`{n["문서"]}` {{id: {q(did)}}}) SET d += {props({"doc_id": doc, "title": row.get("제목"), "owner": row.get("소유 부서")})};')
        parent, parent_label = did, n['문서']
        if sh['판을_따로_둠']:
            vid = make_id(sh['ID']['판'], doc, rev)
            own(vid, f'판 {doc} {rev}')
            if vid not in revs_done:
                revs_done.add(vid)
                out.append(f'MERGE (v:`{n["판"]}` {{id: {q(vid)}}}) SET v += {props({"doc_id": doc, "rev": rev, "status": row.get("상태"), "effective": row.get("시행일") or None, "file": row.get("파일"), "sha256": row.get("SHA-256"), "replaces_note": row.get("대체 관계") or None})};')
                out.append(f'MATCH (d:`{n["문서"]}` {{id: {q(did)}}}), (v:`{n["판"]}` {{id: {q(vid)}}}) MERGE (d)-[:`{n["문서의_판"]}`]->(v);')
            parent, parent_label = vid, n['판']
        sid = make_id(sh['ID']['절'], doc, rev, c['section'])
        own(sid, f'절 {doc} {rev} {c["section"]}')
        if sid not in secs_done:
            secs_done.add(sid)
            out.append(f'MATCH (p:`{parent_label}` {{id: {q(parent)}}}) MERGE (x:`{n["절"]}` {{id: {q(sid)}}}) SET x += {props({"ref": c["section"], "doc_id": doc, "rev": rev})} MERGE (p)-[:`{n["판의_절"]}`]->(x);')
        own(kid, f'지식 {fname}#{c["id"]}')
        kp = {'doc_id': doc, 'rev': rev, 'doc_status': data.get('doc_status'), 'section': c['section'], 'candidate': f'{fname}#{c["id"]}', 'kind': c['kind'],
              'text': c['text'], 'quote': c['quote'], 'line_start': c['line_start'], 'line_end': c['line_end'], 'page': c.get('page'), 'lang': c.get('lang'),
              'value': c.get('value'), 'value_max': c.get('value_max'), 'unit': c.get('unit'), 'comparator': c.get('comparator'), 'value_text': c.get('value_text'),
              'decision': c.get('decision'), 'reason': c.get('reason')}
        out.append(f'MATCH (x:`{n["절"]}` {{id: {q(sid)}}}) MERGE (k:`{n["지식"]}` {{id: {q(kid)}}}) SET k += {props(kp)} MERGE (k)-[:`{n["지식의_출처"]}`]->(x);')
        for rel, target, rp in links:
            setp = f' SET r += {props(rp)}' if any(v is not None for v in rp.values()) else ''
            out.append(f'MATCH (k:`{n["지식"]}` {{id: {q(kid)}}}), (t {{id: {q(target)}}}) MERGE (k)-[r:`{rel}`]->(t){setp};')
        for link in data.get('rule_links', []):
            if c['id'] in link.get('candidates', []):
                out.append(f'MATCH (k:`{n["지식"]}` {{id: {q(kid)}}}), (r:Rule {{id: {q(link["rule_id"])}}}) MERGE (k)-[s:`{n["규칙의_근거"]}`]->(r) SET s += {props({"match": link["match"], "note": link["note"]})};')
    if sh['판을_따로_둠']:
        for (doc, rev), row in reg.items():
            m = re.match(r'^(\S+)판을 대체$', row.get('대체 관계') or '')
            a, b = make_id(sh['ID']['판'], doc, rev), make_id(sh['ID']['판'], doc, m.group(1)) if m else None
            if m and a in revs_done and b in revs_done:
                out.append(f'MATCH (a:`{n["판"]}` {{id: {q(a)}}}), (b:`{n["판"]}` {{id: {q(b)}}}) MERGE (a)-[:`{n["판의_대체"]}`]->(b);')
    clash = sorted((i, sorted(w)) for i, w in owners.items() if len(w) > 1)
    return out, clash


def schema_ext(sh, rules, others):
    n, m = sh['이름'], sh['뜻']
    classes = {n['문서']: {'meaning': m['문서'], 'required': {'id': 'string', 'doc_id': 'string'}},
               n['절']: {'meaning': m['절'], 'required': {'id': 'string', 'ref': 'string'}},
               n['지식']: {'meaning': m['지식'], 'required': {'id': 'string', 'kind': 'string', 'quote': 'string', 'line_start': 'number', 'line_end': 'number', 'decision': 'string'}}}
    rels = {n['판의_절']: {'from': n['판'] if sh['판을_따로_둠'] else n['문서'], 'to': n['절'], 'meaning': m['판의_절']},
            n['지식의_출처']: {'from': n['지식'], 'to': n['절'], 'meaning': m['지식의_출처']},
            n['규칙의_근거']: {'from': n['지식'], 'to': 'Rule', 'meaning': m['규칙의_근거'], 'properties': {'match': 'string', 'note': 'string'}}}
    if sh['판을_따로_둠']:
        classes[n['판']] = {'meaning': m['판'], 'required': {'id': 'string', 'doc_id': 'string', 'rev': 'string', 'status': 'string'}}
        rels[n['문서의_판']] = {'from': n['문서'], 'to': n['판'], 'meaning': m['문서의_판']}
        rels[n['판의_대체']] = {'from': n['판'], 'to': n['판'], 'meaning': m['판의_대체']}
    for r in rules + [o for o in others if o['잇는다'] == '예']:
        if r.get('관계') and r['관계'] not in rels:
            rels[r['관계']] = {'from': n['지식'], 'to': '기존 ID', 'meaning': r.get('까닭') or r.get('근거'), 'properties': {'role': 'string'}}
    return {'classes': classes, 'relations': rels, 'constraints': [f'새 대상 ID — {k} = {v}' for k, v in sh['ID'].items() if v]}


# ───────────── DB ─────────────
def db():
    from app.utils import cypher as lab_cypher
    return lab_cypher


def run(stmts):
    """[(문장, 매개변수)]를 한 번에 실행해 결과 목록을 돌려준다."""
    return db().cypher(stmts)


def counts():
    res = run([('MATCH (n) RETURN count(n)', {}), ('MATCH ()-[r]->() RETURN count(r)', {}),
               ('MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) ORDER BY l', {}), ('MATCH ()-[r]->() RETURN type(r), count(*) ORDER BY 1', {})])
    return {'nodes': res[0]['data'][0]['row'][0], 'rels': res[1]['data'][0]['row'][0],
            'labels': {r['row'][0]: r['row'][1] for r in res[2]['data']}, 'types': {r['row'][0]: r['row'][1] for r in res[3]['data']}}


def export_graph():
    res = run([('MATCH (n) RETURN labels(n), properties(n)', {}), ('MATCH (a)-[r]->(b) RETURN type(r), a.id, b.id, properties(r)', {})])
    nodes = sorted(({'labels': sorted(r['row'][0]), 'props': r['row'][1]} for r in res[0]['data']), key=lambda x: (x['labels'], str(x['props'].get('id'))))
    rels = sorted(({'type': r['row'][0], 'a': r['row'][1], 'b': r['row'][2], 'props': r['row'][3]} for r in res[1]['data']), key=lambda x: (x['type'], str(x['a']), str(x['b'])))
    return {'nodes': nodes, 'rels': rels}


def diff_graph(before, after):
    """기존 노드 속성이 바뀐 것 · 사라진 노드 · 사라진 관계 · 늘어난 수."""
    bn = {n['props'].get('id'): n for n in before['nodes']}
    an = {n['props'].get('id'): n for n in after['nodes']}
    changed = sorted(i for i in bn if i in an and bn[i] != an[i])
    gone = sorted(i for i in bn if i not in an)
    key = lambda r: (r['type'], r['a'], r['b'])
    br, ar = {key(r): r for r in before['rels']}, {key(r): r for r in after['rels']}
    lost = sorted(k for k in br if k not in ar)
    rchanged = sorted(k for k in br if k in ar and br[k] != ar[k])
    return {'added_nodes': len(set(an) - set(bn)), 'added_rels': len(set(ar) - set(br)), 'changed_nodes': changed, 'gone_nodes': gone, 'lost_rels': lost, 'changed_rels': rchanged}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def dump(v):
    return json.dumps(v, ensure_ascii=False, indent=2) + '\n'


def preview(sh):
    """적재하지 않고 — 승인 후보 전부를 정한 ID 꼴로 지으면 노드가 몇 개이고, 서로 다른 대상이 같은 ID에 겹치는 곳은 어디인지."""
    planned = []
    for fname, data in reviews():
        key = (str(data['doc_id']), str(data.get('rev') or ''))
        for c in data['candidates']:
            if c.get('status') == 'approved':
                planned.append((make_id(sh['ID']['지식'], key[0], key[1], c['section'], c['id']), c, fname, data, []))
    stmts, clash = load_statements(sh, planned)
    kinds = {}
    for s in stmts:
        m = re.match(r'^(?:MATCH .*? )?MERGE \(\w+:`(\w+)`', s)
        if m:
            kinds[m.group(1)] = kinds.get(m.group(1), 0) + 1
    statuses = {}
    for fname, data in reviews():
        for c in data['candidates']:
            statuses[c['status']] = statuses.get(c['status'], 0) + 1
    return {'approved': len(planned), 'statuses': statuses, 'clash': clash, 'merges': kinds}


def load_all():
    """정할 자리대로 적재 파일을 쓰고 실행한다. 돌려주는 값: 상태 dict(전후 수 · 겹친 ID · 이은 수 · 추가 전 비교)."""
    known, _, _ = model_ids()
    sh = shape()
    if sh is None:
        return None
    roles, aliases = role_rows(), alias_rows(known)
    rules, others = link_rows(known), other_rows(known)
    before = counts()
    db().model()
    after_model = counts()
    state_path = HERE / 'output/.loaded_docs.json'
    loaded_before = json.loads(read(state_path)) if state_path.is_file() else []
    now_docs = [list(x) for x in linked_docs(rules)]
    snap = HERE / 'output/export_before_add.json'
    added = [d for d in now_docs if d not in loaded_before]
    if loaded_before and added:
        write(snap, dump(export_graph()))          # 새 문서를 더하기 전 그래프 — 기존 연결이 그대로인지 견줄 기준
    planned, notes = plan_links(sh, rules, aliases, others, roles, known)
    stmts, clash = load_statements(sh, planned)
    write(HERE / 'output/load.cypher', '// run.py가 정할 자리(그래프_모양 · 연결_규칙 · 별칭 · 다른문서_조건 · 역할)로 만든 적재 — MERGE · SET만\n' + '\n'.join(stmts) + '\n')
    write(HERE / 'output/schema_ext.json', dump(schema_ext(sh, rules, others)))
    if stmts:
        run([(s.rstrip(';'), {}) for s in stmts])
    after = counts()
    write(state_path, dump(now_docs))
    compare = diff_graph(json.loads(read(snap)), export_graph()) if snap.is_file() else None
    statuses = {}
    for fname, data in reviews():
        for c in data['candidates']:
            statuses[c['status']] = statuses.get(c['status'], 0) + 1
    linked = sum(1 for p in planned if p[4])
    return {'before': before, 'after_model': after_model, 'after': after, 'clash': clash, 'notes': notes, 'docs': now_docs, 'added_docs': added,
            'compare': compare, 'statuses': statuses, 'knowledge': len(planned), 'linked': linked, 'statements': len(stmts)}


# ───────────── 조회 ─────────────
def queries(sh):
    n = sh['이름']
    K, SRC, SEC, RG = n['지식'], n['지식의_출처'], n['절'], n['규칙의_근거']
    return {
        'q1': ("MATCH (f:FailureMode)-[m:MITIGATED_BY|REMEDIED_BY]->(s:Skill)-[:ACTS_ON]->(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})\n"
               "WITH DISTINCT m, s\n"
               f"OPTIONAL MATCH (k:`{K}`)-[c]->(t) WHERE (t = s OR (s)-[:HAS_STEP]->(t)) AND type(c) <> '{SRC}'\n"
               "RETURN s.id AS sop, type(m) AS kind, s.approval_role AS approval, c.role AS role, k.doc_id AS doc, k.rev AS rev, k.section AS section, k.quote AS quote\n"
               "ORDER BY sop, role, doc, quote", ('asset',)),
        'q2': (f"MATCH (r:Rule) OPTIONAL MATCH (k:`{K}`)-[s:`{RG}`]->(r)\n"
               "RETURN r.id AS rule, r.when AS condition, s.match AS match, k.doc_id AS doc, k.section AS section, k.quote AS quote ORDER BY rule, doc, quote", ()),
        'q3': ("MATCH (s:Skill {id: $sop})-[:CHECKS]->(n:Sensor)<-[:MONITORED_BY]-(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})\n"
               "RETURN n.id AS sensor, n.unit AS unit ORDER BY sensor", ('sop', 'asset')),
        'q4': (f"MATCH (k:`{K}` {{doc_id: $doc}})-[r]->(t) WHERE type(r) <> '{SRC}'\n"
               "RETURN type(r) AS rel, labels(t)[0] AS label, t.id AS target, count(k) AS knowledge ORDER BY rel, target", ('doc',)),
        'q5_target': (f"OPTIONAL MATCH (t {{id: $target}}) OPTIONAL MATCH (k:`{K}`)-[r]->(t) WHERE type(r) <> '{SRC}'\n"
                      "RETURN $target AS target, count(DISTINCT t) AS found, count(DISTINCT k) AS knowledge", ('target',)),
        'q5_section': (f"OPTIONAL MATCH (x:`{SEC}`) WHERE x.ref = $section RETURN $section AS section, count(x) AS found", ('section',)),
        'hold': (f"OPTIONAL MATCH (k:`{K}`) WHERE k.candidate IN split($ids, ' ') RETURN size(split($ids, ' ')) AS asked, count(k) AS found", ('ids',)),
        'card': ("MATCH (s:Skill {id: $sop}) OPTIONAL MATCH (s)-[:HAS_STEP]->(st:Step)\n"
                 "WITH s, collect(DISTINCT {order: st.order, text: st.text, source: st.source}) AS steps\n"
                 f"OPTIONAL MATCH (k:`{K}`)-[c]->(t) WHERE (t = s OR (s)-[:HAS_STEP]->(t)) AND type(c) <> '{SRC}'\n"
                 "RETURN s.id AS sop, s.name AS name, s.source AS source, s.approval_role AS approval, steps,\n"
                 "       collect(DISTINCT {role: c.role, doc: k.doc_id, rev: k.rev, status: k.doc_status, section: k.section, quote: k.quote, id: k.candidate, step: t.id}) AS evidence", ('sop',)),
    }


NUMBER = {'q1': '1', 'q2': '2', 'q3': '3', 'q4': '4', 'q5_target': '5대상', 'q5_section': '5절', 'hold': '보류', 'card': '카드'}


def arg(p, v):
    """터미널 한 줄의 --param — 값에 빈칸이 있으면 큰따옴표로 감싼다(PowerShell · cmd 같게)."""
    return f'--param "{p}={v}"' if ' ' in v else f'--param {p}={v}'


def query_file(sh, values):
    """output/query.cypher — 질문마다 `// 질문 <번호>`(app/utils/cypher.py query가 읽는 머리) 아래 조회 하나.
    매개변수는 주석 줄로 둔다: 「터미널:」 줄은 그대로 복사해 실행하는 명령, 「Browser:」 줄은 Neo4j Browser에 먼저 붙여 넣는 :param."""
    out = ['// run.py가 graph_shape.json · query_values.csv로 만든 쿼리(읽기만). 질문마다 「터미널:」 줄을 복사해 실행하거나, '
           'Neo4j Browser에서는 「Browser:」 줄의 :param부터 붙여 넣는다.']
    for name, (text, params) in queries(sh).items():
        num = NUMBER[name]
        got = {p: values.get(name, {}).get(p) for p in params}
        out.append(f'// 질문 {num}')
        if all(v is not None for v in got.values()):
            out.append(f'// 터미널: python -m app.utils.cypher query output/query.cypher {num}' + ''.join(' ' + arg(k, v) for k, v in got.items()))
            out += [f'// Browser: :param {k} => {q(v)};' for k, v in got.items()]
        else:
            out.append(f'// 아직 app/features/query_values.csv에 {" · ".join(k for k, v in got.items() if v is None)} 값이 없음')
        out.append(text + ';')
    return '\n'.join(out) + '\n'


def linked_to(sh, sop):
    """조치(와 그 단계)에 이은 지식 — (열, 행). 결과 화면이 「핀 세척에 이어진 지식」을 보인다(쿼리을 학생이 쓰지 않게)."""
    n = sh['이름']
    text = (f"MATCH (s:Skill {{id: $sop}}) MATCH (k:`{n['지식']}`)-[c]->(t) WHERE (t = s OR (s)-[:HAS_STEP]->(t)) AND type(c) <> '{n['지식의_출처']}'\n"
            "RETURN t.id AS target, type(c) AS rel, c.role AS role, k.doc_id AS doc, k.rev AS rev, k.section AS section, k.line_start AS line, k.quote AS quote ORDER BY target, role, doc, line")
    res = run([(text, {'sop': sop})])[0]
    return res['columns'], [r['row'] for r in res['data']]


def ask(name, values):
    """조회 하나 — (열, 행) 또는 None(매개변수를 query_values.csv에 아직 적지 않음)."""
    sh = shape()
    text, params = queries(sh)[name]
    got = values.get(name, {})
    if any(p not in got for p in params):
        return None
    args = {p: got[p] for p in params}
    res = run([(text, args)])[0]
    return res['columns'], [r['row'] for r in res['data']]


# ───────────── 추가 자료가 필요한 질문 · 카드 ─────────────
def remaining(values):
    """그래프에 넣지 않은 것 — 보류 후보, 원문 없음 조건, 받은 파일이 없는 문서, 없는 절 · 대상 조회가 0인 것, 현재값 필요(current_value_sources.csv)."""
    out = []
    for fname, data in reviews():
        for c in data['candidates']:
            if c.get('status') == 'pending':
                out.append({'item': c['text'], 'kind': '보류', 'source': f'{data["doc_id"]} {data.get("rev")} {c["section"]} {c["line_start"]}줄 ({fname}#{c["id"]})', 'note': c.get('reason') or ''})
        for link in data.get('rule_links', []):
            if link.get('match') == '원문 없음':
                out.append({'item': f'조건 {link["rule_id"]}의 근거 원문', 'kind': '원문 미확인', 'source': fname, 'note': link.get('note') or ''})
    for r in register():
        if not r.get('파일'):
            out.append({'item': f'{r["문서 식별자"]} {r["제목"]}', 'kind': '제공되지 않은 문서', 'source': 'data/documents/catalog.csv', 'note': r.get('비고') or '목록에만 있고 받은 파일이 없음'})
    for name, key, kind in (('q5_section', 'section', '제공되지 않은 절'), ('q5_target', 'target', '제공되지 않은 대상')):
        got = ask(name, values)
        if got and got[1] and got[1][0][-1] == 0:
            out.append({'item': values[name][key], 'kind': kind, 'source': f'output/query.cypher 질문 {NUMBER[name]}', 'note': '그래프 조회 결과 없음 — 원문 · 연결된 지식이 없다'})
    for r in now_rows():
        out.append({'item': f'{r["작업"]} {r["확인할_값"]}', 'kind': '현재값 필요', 'source': r['읽을_원천'], 'note': f'그래프에 두지 않음 — 근거 {r["근거"]}'})
    return out


def card_text(sop_id, values=None):
    """조회 결과로 작업 확인 카드 글 — data/contract.md 4절의 제목 순서. 현재값은 current_value_sources.csv, 추가 자료가 필요한 질문은 remaining_questions.json에서."""
    got = run([(queries(shape())['card'][0], {'sop': sop_id})])[0]
    if not got['data']:
        return None
    sop, name, source, approval, steps, ev = got['data'][0]['row']
    ev = [e for e in ev if e.get('quote')]
    reg = {(r['문서 식별자'], r['판']): r for r in register()}
    sopj = json.loads(read(basis('sop.json')))
    doc = sopj.get('document') or {}
    base = reg.get((str(doc.get('id') or ''), str(doc.get('revision') or '')), {})
    def line(e):
        return f'- {e["doc"]} {e["rev"]} {e["section"]}: 「{e["quote"].splitlines()[-1].strip()}」(검토 {e["id"]})'
    def part(role):
        seen, out = set(), []
        for e in sorted(ev, key=lambda x: (str(x['doc']), str(x['section']), str(x['id']))):
            k = e['quote'].splitlines()[-1].strip()
            if e.get('role') == role and k not in seen:
                seen.add(k)
                out.append(line(e))
        return out
    out = [f'# 작업 확인 카드 — {sop} {name}', '', '## 대상 작업', '',
           f'- {sop} {name} — 근거 문서 {doc.get("id", "")} {doc.get("revision", "")}판({base.get("상태", "")}, 시행 {base.get("시행일", "")}) {source}', '',
           '## 준비 조건', ''] + (part('준비') or ['- 없음 — 이 작업에 이은 준비 지식이 그래프에 없음(추가 자료가 필요한 질문 참고)'])
    out += ['', '## 금지 · 제한', ''] + (part('금지') or ['- 없음 — 이 작업에 이은 금지 지식이 그래프에 없음'])
    out += ['', '## 작업 순서', '']
    by_step = {e['step']: e for e in ev if e.get('role') == '순서'}
    for st in sorted([s for s in steps if s.get('order')], key=lambda s: s['order']):
        hit = by_step.get(f'{sop}:{st["order"]}')
        out.append(f'{st["order"]}. {st["text"]} — ' + (f'{hit["doc"]} {hit["rev"]} {hit["section"]} 「{hit["quote"].splitlines()[-1].strip()}」' if hit else f'{st["source"]} 「{st["text"]}」(받은 SOP 구조)'))
    out += ['', '## 완료 기준', ''] + (part('완료') or ['- 없음 — 이 작업에 이은 완료 지식이 그래프에 없음'])
    nows = [r for r in now_rows() if r['작업'] == sop]
    out += ['', '## 작업 직전 확인할 현재값', ''] + ([f'- {r["확인할_값"]} — 그래프에 없는 현재값. {r["읽을_원천"]}에서 읽는다(근거 {r["근거"]}).' for r in nows]
                                               or ['- 없음 — current_value_sources.csv에 이 작업의 행이 없음'])
    out += ['', '## 승인', '', f'- {approval} — 받은 SOP 구조. 카드는 승인을 대신하지 않는다.'] + part('승인')
    rq = json.loads(read(HERE / 'output/remaining_questions.json')) if (HERE / 'output/remaining_questions.json').is_file() else []
    sel = basis('reviews/selected_task.json')
    picked = json.loads(read(sel)).get('remaining_questions', []) if sel.is_file() and json.loads(read(sel)).get('task') == sop else []
    mine = picked + [x for x in rq if sop in (x.get('item', '') + x.get('source', '') + x.get('note', '')) and x not in picked]
    out += ['', '## 추가 자료가 필요한 질문', ''] + ([f'- {x["item"]} — {x["kind"]} · {x["source"]}' for x in mine] or ['- 없음 — remaining_questions.json에 이 작업을 가리키는 항목이 없음'])
    return '\n'.join(out) + '\n'
