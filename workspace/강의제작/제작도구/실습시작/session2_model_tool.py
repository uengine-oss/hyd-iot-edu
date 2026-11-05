"""설비 지식 모델을 만드는 제공 코드 — 원자료와 `결과/`의 정할 자리(내가 정한 표 · 함수)를 읽어 `결과/schema.json` · `결과/graph.json`을 쓴다.

이 파일은 누가 해도 같은 일만 한다: 파일 읽기, 칸 공백 정리, 숫자와 단위 글자 나누기, 단위 환산, 교체부품 칸의 품번 찾기(괄호 속 품번 · 사내 품번 ·
품번 교차표에 하나로 적힌 표기), 계약 꼴로 쓰기, 모델에 물어보기. 무엇을 하나로 보고 무엇을 따로 둘지, ID를 무엇으로 짓고 관계를 어느 쪽으로 둘지는
`결과/`의 정할 자리가 정한다. 정할 자리에 없는 것은 짐작하지 않고 파일 · 행과 함께 멈춘다.
직접 실행하지 않는다 — `python show_result.py`가 단계마다 부른다.
"""
from pathlib import Path
import csv
import importlib.util
import io
import json
import re

HERE = Path(__file__).resolve().parent
DATA = HERE / '자료'
OUT = HERE / '결과'
KINDS = ['설비', '구성 요소', '센서', '물리량', '부품']
LABEL = {'설비': 'Asset', '구성 요소': 'Component', '센서': 'Sensor', '물리량': 'Quantity', '부품': 'Part'}
LINKS = {'설비-구성 요소': ('설비', '구성 요소'), '구성 요소-센서': ('구성 요소', '센서'), '설비-센서': ('설비', '센서'),
         '센서-물리량': ('센서', '물리량'), '구성 요소-부품': ('구성 요소', '부품'), '부품-부품': ('부품', '부품')}
FIELDS = {'설비': ['설비코드', '모델', '기능위치', '일련번호'], '구성 요소': ['설비코드', '구성요소', '계통'],
          '센서': ['설비코드', '태그', '계장태그'], '물리량': ['물리량'], '부품': ['품번']}
# 단위 환산(일반 지식): (원래 단위, 기준 단위) → 곱할 값
FACTOR = {('W', 'kW'): 0.001, ('kW', 'W'): 1000, ('kPa', 'bar'): 0.01, ('bar', 'kPa'): 100, ('MPa', 'bar'): 10, ('bar', 'MPa'): 0.1,
          ('l/min', 'L/min'): 1, ('L/min', 'l/min'): 1, ('lpm', 'L/min'): 1, ('°C', '℃'): 1, ('℃', '°C'): 1}
UNKNOWN = '미확인'


class Stop(Exception):
    """정할 자리에 없는 것 · 계약 어긋남. 글에 파일 · 행이 있다."""


# ───────────── 읽기 ─────────────
def table(path):
    """CSV → [(편집기 줄 번호, dict)]. 첫머리 # 줄은 건너뛰고(줄 번호는 그대로 센다) 칸 앞뒤 공백을 정리한다."""
    lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    head = next((i for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith('#')), None)
    if head is None:
        raise Stop(f'{rel(path)}: 열 이름 줄이 없습니다.')
    reader = csv.reader(io.StringIO('\n'.join(lines[head:])))
    cols = [c.strip() for c in next(reader)]
    out = []
    for offset, cells in enumerate(reader, head + 2):
        if not any(c.strip() for c in cells):
            continue
        if len(cells) > len(cols) and cols[-1] == '근거':     # 맨 끝 「근거」 칸 글에 쉼표가 든 경우 — 남은 칸을 근거에 이어 붙인다
            cells = cells[:len(cols) - 1] + [','.join(cells[len(cols) - 1:])]
        if len(cells) > len(cols):
            raise Stop(f'{rel(path)}:{offset}: 칸 수가 열 이름보다 많습니다(쉼표가 든 값은 큰따옴표로 감쌉니다).')
        out.append((offset, {c: (cells[i].strip() if i < len(cells) else '') for i, c in enumerate(cols)}))
    return out


def need(path, columns):
    rows = table(path)
    have = list(rows[0][1]) if rows else [c.strip() for c in next(csv.reader(io.StringIO(
        next(x for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')))))]
    miss = [c for c in columns if c not in have]
    if miss:
        raise Stop(f'{rel(path)}: 열 {", ".join(miss)}이 없습니다(받은 빈 틀의 열 이름을 바꾸지 않습니다).')
    return rows


def rel(path):
    try:
        return Path(path).resolve().relative_to(HERE).as_posix()
    except ValueError:
        return Path(path).name


def number(text):
    m = re.match(r'\s*(-?\d+(?:\.\d+)?)', text or '')
    return float(m.group(1)) if m else None


def rules(name='part_rules'):
    """결과/<name>.py(내가 쓴 판단 함수)를 불러온다."""
    path = OUT / f'{name}.py'
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ask(mod, fn, want, *args):
    """판단 함수 하나를 부르고 돌려준 값의 꼴을 본다(want = bool · str). 꼴이 다르면 함수 이름과 받은 값으로 멈춘다."""
    value = getattr(mod, fn)(*args)
    if want is bool and value not in (True, False):
        raise Stop(f'결과/{mod.__name__}.py {fn}: True 또는 False를 돌려줘야 합니다(돌려준 값 {value!r}).')
    if want is str and not (isinstance(value, str) and value.strip()):
        raise Stop(f'결과/{mod.__name__}.py {fn}: 빈칸이 아닌 글자를 돌려줘야 합니다(돌려준 값 {value!r}).')
    return value.strip() if want is str else value


def grouped(items, same):
    """items를 판단 함수 same(a, b)가 True인 짝끼리 이어 묶는다(이어진 것은 모두 한 묶음). 묶음 = 원래 차례의 목록."""
    root = list(range(len(items)))

    def top(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if top(i) != top(j) and same(items[i], items[j]):
                root[top(j)] = top(i)
    out = {}
    for i, x in enumerate(items):
        out.setdefault(top(i), []).append(x)
    return list(out.values())


def resolve_cell(cell, parts, cross):
    """교체부품 칸 → (사내 품번, 찾은 법)(일반 로직): 괄호 속 품번 · 사내 품번 · 품번 교차표에 하나로 적힌 표기. 못 풀면 (None, '')."""
    m = re.search(r'\((P-[A-Z0-9-]+)\)', cell)
    if m:
        return m.group(1), '괄호 속 품번'
    if cell in parts:
        return cell, '사내 품번'
    hits = sorted({c['사내품번'] for c in cross if c['다른표기'] == cell})
    if cell and len(hits) == 1:
        return hits[0], '품번 교차표'
    return None, ''


# ───────────── 정할 자리 ─────────────
def design():
    """설계.csv → {대상: ID 틀}, 관계.csv → {연결: (관계 이름, 시작 대상, 끝 대상)}."""
    ids = {}
    for line, r in need(OUT / '설계.csv', ['대상', 'ID_만드는_법', '근거']):
        k = r['대상']
        if k not in KINDS:
            raise Stop(f'결과/설계.csv:{line}: 대상 「{k}」 — 대상은 {" · ".join(KINDS)} 가운데 하나입니다.')
        bad = [x for x in re.findall(r'\{([^}]*)\}', r['ID_만드는_법']) if x not in FIELDS[k]]
        if bad or not re.search(r'\{[^}]+\}', r['ID_만드는_법']):
            raise Stop(f'결과/설계.csv:{line}: {k}의 ID_만드는_법 「{r["ID_만드는_법"]}」 — {{열 이름}} 꼴로 쓰고, 쓸 수 있는 열은 {", ".join(FIELDS[k])}입니다.')
        ids[k] = r['ID_만드는_법']
    miss = [k for k in KINDS if k not in ids]
    if miss:
        raise Stop('결과/설계.csv: ID_만드는_법이 없는 대상 — ' + ', '.join(miss))
    links = {}
    for line, r in need(OUT / '관계.csv', ['연결', '관계_이름', '시작', '근거']):
        k = r['연결']
        if k not in LINKS:
            raise Stop(f'결과/관계.csv:{line}: 연결 「{k}」 — 연결은 {" · ".join(LINKS)} 가운데 하나입니다.')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', r['관계_이름']):
            raise Stop(f'결과/관계.csv:{line}: 관계_이름 「{r["관계_이름"]}」 — 영어 대문자와 밑줄로 씁니다.')
        if r['시작'] not in LINKS[k]:
            raise Stop(f'결과/관계.csv:{line}: 시작 「{r["시작"]}」 — {k} 연결의 시작은 {" · ".join(dict.fromkeys(LINKS[k]))} 가운데 하나입니다.')
        a, b = LINKS[k]
        links[k] = (r['관계_이름'], r['시작'], b if r['시작'] == a else a)
    miss = [k for k in LINKS if k not in links and k != '부품-부품']
    if miss:
        raise Stop('결과/관계.csv: 정하지 않은 연결 — ' + ', '.join(miss))
    return ids, links


def make_id(template, kind, values, where):
    try:
        return template.format(**values)
    except KeyError as e:
        raise Stop(f'{where}: {kind} ID에 쓸 {e} 칸이 비었습니다.')


def names():
    """이름.csv(규칙으로 정해지지 않는 이름만) → {(원자료 이름, 모델 또는 ''): (구성 요소 이름, 줄)}. 비어 있어도 된다."""
    out = {}
    for line, r in need(OUT / '이름.csv', ['원자료_이름', '모델', '구성요소_이름', '근거']):
        if not r['원자료_이름'] or not r['구성요소_이름']:
            raise Stop(f'결과/이름.csv:{line}: 원자료_이름과 구성요소_이름을 모두 적습니다.')
        key = (r['원자료_이름'], r['모델'])
        if key in out and out[key][0] != r['구성요소_이름']:
            raise Stop(f'결과/이름.csv:{line}: 「{r["원자료_이름"]}」({r["모델"] or "모든 모델"})이 두 이름에 묶였습니다.')
        out[key] = (r['구성요소_이름'], line)
    return out


def name_map(src, rows_done, model_of):
    """5단계: 원자료 구성 요소 행마다 이름을 정한다. 내 규칙(결과/name_rules.py — same_device · group_name)으로 같은 장치끼리 묶어
    묶음마다 이름 하나를 쓰고, 결과/이름.csv에 적은 원자료 이름은 그 이름으로 바꾼다. 어느 것에도 걸리지 않은 행은 원자료 이름 그대로다.
    돌려주는 것: ({(원자료 이름, 모델): 이름}, 화면용 {묶음, 이름표로 바꾼 행, 다른 이름과 묶이지 않은 행, 안 쓴 이름표 행})."""
    mod = rules('name_rules')
    parts = {r['품번'] for _, r in src['예비품_목록.csv']}
    cross = [r for _, r in src['품번_교차표.csv']]
    live_sensors = [(line, r) for line, r in src['센서_목록.csv'] if not rows_done.get(('센서_목록.csv', line))]
    items = []
    for line, r in src['구성요소_목록.csv']:
        if rows_done.get(('구성요소_목록.csv', line)) or r['설비코드'] not in model_of:
            continue
        tags = sorted(s['태그'] for _, s in live_sensors if s['설비코드'] == r['설비코드'] and s['붙은곳'] == r['구성요소'])
        items.append({'설비코드': r['설비코드'], '모델': model_of[r['설비코드']], '계통': r['계통'], '이름': r['구성요소'], '태그': tags,
                      '부품': resolve_cell(r['교체부품'], parts, cross)[0] or '', '줄': f'구성요소_목록.csv:{line}'})
    groups = grouped(items, lambda a, b: ask(mod, 'same_device', bool, dict(a, 태그=list(a['태그'])), dict(b, 태그=list(b['태그']))))
    named, by_rule = {}, []
    for members in groups:
        name = ask(mod, 'group_name', str, [dict(m, 태그=list(m['태그'])) for m in members]) if len(members) > 1 else members[0]['이름']
        for m in members:
            key = (m['이름'], m['모델'])
            if key in named and named[key] != name:
                raise Stop(f'결과/name_rules.py: 같은 모델({m["모델"]})의 원자료 이름 「{m["이름"]}」이 두 묶음({named[key]} · {name})에 들어갔습니다 — {m["줄"]}.')
            named[key] = name
        if len(members) > 1:
            by_rule.append((name, len(members), ' · '.join(sorted({f'{m["이름"]}({m["설비코드"]})' for m in members}))))
    table_ = names()
    fixed = []
    for (raw, model), name in sorted(named.items()):
        hit = table_.get((raw, model)) or table_.get((raw, ''))
        if hit:
            named[(raw, model)] = hit[0]
            fixed.append((f'결과/이름.csv:{hit[1]}', raw, model, name, hit[0]))
    unused = sorted(f'결과/이름.csv:{line}' for (raw, model), (_, line) in table_.items()
                    if not any(r == raw and model in ('', m) for r, m in named))
    fixed_keys = {(f[1], f[2]) for f in fixed}
    alone = [(m['줄'], m['설비코드'], m['계통'], m['이름']) for members in groups if len(members) == 1 for m in members
             if (m['이름'], m['모델']) not in fixed_keys and sum(1 for x in items if x['이름'] == m['이름']) == 1]
    return named, {'묶음': sorted(by_rule), '이름표': fixed, '그대로': sorted(alone, key=lambda x: int(x[0].split(':')[1])), '안_쓴_이름표': unused}


def name_of(named, raw, model):
    """원자료 이름(붙은곳 · 쓰는곳)을 5단계에서 정한 이름으로. 그 모델의 구성 요소 행에 없는 이름은 원자료 이름 그대로 견준다."""
    return named.get((raw, model), raw)


def handling():
    """행_처리.csv → {(파일, 행): (처리, 대상)}. 처리 = 빼기 · 하나로:<남길 행> · 옛 코드:<설비코드>."""
    out = {}
    for line, r in need(OUT / '행_처리.csv', ['파일', '행', '처리', '근거']):
        if not r['행'].isdigit():
            raise Stop(f'결과/행_처리.csv:{line}: 행 「{r["행"]}」 — 편집기에 보이는 줄 번호(숫자)를 씁니다.')
        how = r['처리']
        r['파일'] = r['파일'].removeprefix('자료/')      # 「자료/센서_목록.csv」처럼 폴더를 붙여 적어도 같은 파일
        if r['파일'] not in ('설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv'):
            raise Stop(f'결과/행_처리.csv:{line}: 파일 「{r["파일"]}」 — 설비_대장.csv · 구성요소_목록.csv · 센서_목록.csv 가운데 하나입니다.')
        if how == '빼기':
            out[(r['파일'], int(r['행']))] = ('빼기', '')
        elif re.fullmatch(r'하나로:\d+', how):
            out[(r['파일'], int(r['행']))] = ('하나로', how.split(':', 1)[1])
        elif re.fullmatch(r'옛 코드:\S+', how):
            out[(r['파일'], int(r['행']))] = ('옛 코드', how.split(':', 1)[1])
        else:
            raise Stop(f'결과/행_처리.csv:{line}: 처리 「{how}」 — 빼기 · 하나로:<남길 행 번호> · 옛 코드:<그 설비코드> 가운데 하나로 씁니다.')
    return out


KIND_NAMES = ('실측', '계산값', '설정값')


def quantities():
    """물리량.csv(규칙으로 정해지지 않는 재는것만) → {재는것: (물리량, 종류, 줄)}. 종류 = 실측 · 계산값 · 설정값. 비어 있어도 된다."""
    out = {}
    for line, r in need(OUT / '물리량.csv', ['재는것', '물리량', '종류', '근거']):
        if r['종류'] not in KIND_NAMES:
            raise Stop(f'결과/물리량.csv:{line}: 종류 「{r["종류"]}」 — 실측 · 계산값 · 설정값 가운데 하나입니다.')
        if not r['재는것'] or not r['물리량']:
            raise Stop(f'결과/물리량.csv:{line}: 재는것과 물리량을 모두 적습니다.')
        out[r['재는것']] = (r['물리량'], r['종류'], line)
    return out


def quantity_map(src, rows_done, asset_rows):
    """6단계: 센서 행마다 (물리량, 종류)를 정한다. 내 규칙(결과/quantity_rules.py — same_quantity · quantity_name · kind_of)으로 같은 물리량끼리 묶고,
    결과/물리량.csv에 적은 재는것은 그 물리량 · 종류로 바꾼다. 돌려주는 것: ({센서 줄: (물리량, 종류)}, 화면용 {이름표로 바꾼 행, 안 쓴 이름표 행})."""
    mod = rules('quantity_rules')
    items = []
    for line, r in src['센서_목록.csv']:
        if rows_done.get(('센서_목록.csv', line)) or r['설비코드'] not in asset_rows:
            continue
        a = asset_rows[r['설비코드']]
        items.append((line, {**{k: r[k] for k in ('설비코드', '태그', '계장태그', '재는것', '단위', '수집방식', '비고')},
                             '모델': a['모델'], '제조사': a['제조사'], '줄': f'센서_목록.csv:{line}'}))
    out = {}
    for members in grouped(items, lambda a, b: ask(mod, 'same_quantity', bool, dict(a[1]), dict(b[1]))):
        name = ask(mod, 'quantity_name', str, [dict(m) for _, m in members])
        for line, m in members:
            kind = ask(mod, 'kind_of', str, dict(m))
            if kind not in KIND_NAMES:
                raise Stop(f'결과/quantity_rules.py kind_of: {m["줄"]}에 「{kind}」를 돌려줬습니다 — 실측 · 계산값 · 설정값 가운데 하나입니다.')
            out[line] = (name, kind)
    table_ = quantities()
    fixed = []
    for line, m in items:
        hit = table_.get(m['재는것'])
        if hit:
            fixed.append((f'결과/물리량.csv:{hit[2]}', m['줄'], f'{m["설비코드"]}:{m["태그"]}', m['재는것'], ' · '.join(out[line]), f'{hit[0]} · {hit[1]}'))
            out[line] = hit[:2]
    unused = sorted(f'결과/물리량.csv:{v[2]}' for k, v in table_.items() if not any(m['재는것'] == k for _, m in items))
    return out, {'이름표': fixed, '안_쓴_이름표': unused}


def units():
    """단위.csv(규칙으로 정해지지 않는 것만) → ({물리량: (기준 단위, 줄)}, {센서_목록.csv 행: (단위 또는 미확인, 줄)}). 비어 있어도 된다."""
    base, rows = {}, {}
    for line, r in need(OUT / '단위.csv', ['대상', '값', '근거']):
        if not r['대상'] or not r['값']:
            raise Stop(f'결과/단위.csv:{line}: 대상과 값을 모두 적습니다.')
        m = re.fullmatch(r'센서_목록\.csv:(\d+)', r['대상'])
        if m:
            rows[int(m.group(1))] = (r['값'], line)
        else:
            base[r['대상']] = (r['값'], line)
    return base, rows


def unit_map(src, rows_done, asset_rows, qmap):
    """7단계: 물리량마다 기준 단위와, 단위 칸이 빈 센서 행의 단위를 정한다. 내 규칙(결과/unit_rules.py — base_unit · blank_unit)으로 정하고,
    결과/단위.csv에 적은 대상은 그 값으로 바꾼다. 돌려주는 것: ({물리량: 기준 단위}, {빈 단위 센서 줄: 단위 또는 미확인}, 화면용 {기준 표, 안 쓴 이름표 행})."""
    mod = rules('unit_rules')
    live = [(line, r) for line, r in src['센서_목록.csv'] if line in qmap]

    def row_of(line, r):
        return {**{k: r[k] for k in ('설비코드', '태그', '단위', '정상값', '한계', '한계구분')}, '모델': asset_rows[r['설비코드']]['모델'],
                '물리량': qmap[line][0], '줄': f'센서_목록.csv:{line}'}
    per_q = {}
    for line, r in live:
        per_q.setdefault(qmap[line][0], []).append(r)
    table_base, table_rows = units()
    base, shown = {}, []
    for q, members in sorted(per_q.items()):
        written = [r['단위'] for r in members if r['단위']]
        if q in table_base:
            unit, how = table_base[q][0], f'결과/단위.csv:{table_base[q][1]}'
        elif written:
            unit, how = ask(mod, 'base_unit', str, q, list(written)), 'base_unit'
        else:
            raise Stop(f'물리량 「{q}」: 단위가 적힌 센서 행이 없습니다 — 결과/단위.csv에 이 물리량의 기준 단위나 {UNKNOWN}을 적습니다.')
        base[q] = unit
        counts = {}
        for u in written:
            counts[u] = counts.get(u, 0) + 1
        shown.append((q, ' · '.join(f'{u} {n}행' for u, n in counts.items()), unit, how))
    blank = {}
    for line, r in live:
        if r['단위']:
            continue
        if line in table_rows:
            blank[line] = table_rows[line][0]
            continue
        cands = [row_of(n, x) for n, x in live if x['단위'] and qmap[n][0] == qmap[line][0]]
        blank[line] = ask(mod, 'blank_unit', str, row_of(line, r), cands)
    unused = sorted([f'결과/단위.csv:{v[1]}' for k, v in table_base.items() if k not in per_q] +
                    [f'결과/단위.csv:{v[1]}' for k, v in table_rows.items() if k not in blank])
    return base, blank, {'기준': shown, '안_쓴_이름표': unused}


# ───────────── 만들기(단계별) ─────────────
def raw():
    return {n: table(DATA / n) for n in ['설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv', '예비품_목록.csv', '품번_교차표.csv']}


def preview_ids():
    """4단계: 내 ID 틀로 원자료 행마다 ID를 지었을 때 겹치는 ID(이름은 아직 원자료 그대로)."""
    ids, links = design()
    src = raw()
    out = {}
    for kind, file, fields in [('설비', '설비_대장.csv', None), ('구성 요소', '구성요소_목록.csv', None), ('센서', '센서_목록.csv', None)]:
        seen = {}
        for line, r in src[file]:
            seen.setdefault(make_id(ids[kind], kind, r, f'자료/{file}:{line}'), []).append(line)
        out[kind] = {'개수': len(seen), '겹침': {k: v for k, v in seen.items() if len(v) > 1}, '파일': file}
    return ids, links, out


def build(stage):
    """stage = '이름' · '센서' · '단위' · '부품'까지 만든다. 돌려주는 것: 화면용 값과 (부품 단계면) 쓴 모델."""
    ids, links = design()
    src = raw()
    rows_done = handling()
    nodes, rels, index, info = [], [], {}, {}
    used_rows = set()

    def handled(file, line):
        h = rows_done.get((file, line))
        if h:
            used_rows.add((file, line))
        return h

    def node(label, id_, where, **props):
        if id_ in index:
            raise Stop(f'{where}: ID 「{id_}」가 이미 있습니다(겹친 행). 결과/행_처리.csv에 이 행을 어떻게 할지 정하거나 결과/설계.csv의 ID를 바꿉니다.')
        index[id_] = label
        nodes.append({'labels': [label], 'props': {'id': id_, **{k: v for k, v in props.items() if v not in (None, '', [])}}})

    def rel_(link, a, b, **props):
        name, start, _ = links[link]
        first = LINKS[link][0]
        x, y = (a, b) if start == first else (b, a)
        rels.append({'type': name, 'a': x, 'b': y, 'props': {k: v for k, v in props.items() if v not in (None, '')}})

    # 설비
    assets, model_of, legacy = {}, {}, {}
    for line, r in src['설비_대장.csv']:
        h = handled('설비_대장.csv', line)
        if h and h[0] == '옛 코드':
            legacy.setdefault(h[1], []).append(r['설비코드'])
            continue
        if h:
            continue
        aid = make_id(ids['설비'], '설비', r, f'자료/설비_대장.csv:{line}')
        assets[r['설비코드']] = aid
        model_of[r['설비코드']] = r['모델']
    for line, r in src['설비_대장.csv']:
        code = r['설비코드']
        if code in assets:
            node('Asset', assets[code], f'자료/설비_대장.csv:{line}', name=r['설비명'], model=r['모델'], maker=r['제조사'], serial=r['일련번호'],
                 functional_location=r['기능위치'], installed=r['설치일'], status=r['상태'], legacy_codes=legacy.get(code))
    for target in legacy:
        if target not in assets:
            raise Stop(f'결과/행_처리.csv: 옛 코드를 남길 설비 「{target}」가 설비 대장에 없습니다.')
    # 구성 요소
    comps = {}
    per_asset = {}
    for line, r in src['구성요소_목록.csv']:
        if r['설비코드'] not in assets and not rows_done.get(('구성요소_목록.csv', line)):
            raise Stop(f'자료/구성요소_목록.csv:{line}: 설비코드 「{r["설비코드"]}」가 모델의 설비에 없습니다.')
    named, name_info = name_map(src, rows_done, model_of)
    info['이름'] = name_info
    for line, r in src['구성요소_목록.csv']:
        per_asset.setdefault(r['설비코드'], [0, 0])[0] += 1
        if handled('구성요소_목록.csv', line):
            continue
        code = r['설비코드']
        cname = name_of(named, r['구성요소'], model_of[code])
        cid = make_id(ids['구성 요소'], '구성 요소', {**r, '구성요소': cname}, f'자료/구성요소_목록.csv:{line}')
        node('Component', cid, f'자료/구성요소_목록.csv:{line}', name=cname, group=r['계통'], serial=r['일련번호'],
             aliases=[r['구성요소']] if r['구성요소'] != cname else None)
        rel_('설비-구성 요소', assets[code], cid)
        comps[(code, cname)] = (cid, line, r)
        per_asset[code][1] += 1
    info['구성 요소'] = {code: tuple(v) for code, v in sorted(per_asset.items())}
    if stage == '이름':
        info.update(unused=[k for k in rows_done if k not in used_rows and k[0] in ('설비_대장.csv', '구성요소_목록.csv')])
        return info, None
    # 센서
    for line, r in src['센서_목록.csv']:
        if r['설비코드'] not in assets and not rows_done.get(('센서_목록.csv', line)):
            raise Stop(f'자료/센서_목록.csv:{line}: 설비코드 「{r["설비코드"]}」가 모델의 설비에 없습니다.')
    asset_rows = {r['설비코드']: r for _, r in src['설비_대장.csv'] if r['설비코드'] in assets}
    qmap, q_info = quantity_map(src, rows_done, asset_rows)
    info['물리량'] = q_info
    if stage in ('단위', '부품'):
        base, blank_units, u_info = unit_map(src, rows_done, asset_rows, qmap)
        info['단위'] = u_info
    else:
        base, blank_units = {}, {}
    sensors, quants, convs = [], {}, []
    for line, r in src['센서_목록.csv']:
        if handled('센서_목록.csv', line):
            continue
        code = r['설비코드']
        qname, kind = qmap[line]
        qid = make_id(ids['물리량'], '물리량', {'물리량': qname}, f'결과/물리량.csv ({r["재는것"]})')
        sid = make_id(ids['센서'], '센서', r, f'자료/센서_목록.csv:{line}')
        props = dict(tag=r['태그'], instrument_tag=r['계장태그'], kind={'실측': 'measured', '계산값': 'derived', '설정값': 'setpoint'}[kind],
                     derived=kind == '계산값', limit_direction={'상한': 'upper', '하한': 'lower'}.get(r['한계구분']),
                     sample_hz=number(r['표본주기']), collection=r['수집방식'])
        normal, limit = number(r['정상값']), number(r['한계'])
        if stage in ('단위', '부품'):
            unit = r['단위'] or blank_units[line]
            if unit == UNKNOWN or base[qname] == UNKNOWN:
                factor, out_unit = 1, None
            elif unit == base[qname]:
                factor, out_unit = 1, unit
            elif (unit, base[qname]) in FACTOR:
                factor, out_unit = FACTOR[(unit, base[qname])], base[qname]
            else:
                raise Stop(f'자료/센서_목록.csv:{line}: 단위 「{unit}」를 「{base[qname]}」로 바꾸는 법을 모릅니다(이 도구가 아는 환산: {", ".join(f"{a}→{b}" for a, b in FACTOR)}).')
            if factor != 1 or (r['단위'] and r['단위'] != (out_unit or r['단위'])) or (not r['단위'] and unit != UNKNOWN):
                convs.append((f'센서_목록.csv:{line}', sid, r['단위'] or '(빈칸)', unit, out_unit or UNKNOWN,
                              f'{r["정상값"]} / {r["한계"]}', f'{"" if normal is None else round(normal * factor, 6)} / {"" if limit is None else round(limit * factor, 6)}'))
            props.update(unit=out_unit, source_unit=unit if (factor != 1 or not r['단위']) and unit != UNKNOWN else None,
                         normal=None if normal is None else round(normal * factor, 6), limit=None if limit is None else round(limit * factor, 6))
        else:
            props.update(normal=normal, limit=limit)
        node('Sensor', sid, f'자료/센서_목록.csv:{line}', **props)
        place = r['붙은곳']
        if place == '설비 전체':
            rel_('설비-센서', assets[code], sid)
        else:
            cname = name_of(named, place, model_of[code])
            if (code, cname) not in comps:
                raise Stop(f'자료/센서_목록.csv:{line}: 붙은곳 「{place}」(→ {cname})이 {code}의 구성 요소에 없습니다.')
            rel_('구성 요소-센서', comps[(code, cname)][0], sid)
        if qid not in quants:
            quants[qid] = (qname, None if base.get(qname) == UNKNOWN else base.get(qname))
        rel_('센서-물리량', sid, qid)
        sensors.append((sid, code, r['태그'], qname, kind))
    for qid, (qname, unit) in quants.items():
        node('Quantity', qid, f'결과/물리량.csv ({qname})', name=qname, unit=unit)
    info['센서'] = sensors
    info['변환'] = convs
    if stage in ('센서', '단위'):
        info.update(unused=[k for k in rows_done if k not in used_rows])
        return info, None
    # 부품
    parts = {r['품번']: (line, r) for line, r in src['예비품_목록.csv']}
    cross = [r for _, r in src['품번_교차표.csv']]
    for pid, (line, r) in parts.items():
        node('Part', make_id(ids['부품'], '부품', r, f'자료/예비품_목록.csv:{line}'), f'자료/예비품_목록.csv:{line}', name=r['품명'],
             other_codes=sorted({c['다른표기'] for c in cross if c['사내품번'] == pid}))
    part_id = {pid: make_id(ids['부품'], '부품', r, '') for pid, (_, r) in parts.items()}
    mod = rules()
    spares = [dict(r) for _, r in src['예비품_목록.csv']]
    asked, linked = [], []
    for (code, cname), (cid, line, r) in comps.items():
        cell = r['교체부품']
        pid, how = resolve_cell(cell, parts, cross)
        if pid is None:
            def same_component(raw_name, model=model_of[code], cname=cname):
                """원자료 이름이 이 구성 요소와 같은 것인가 — 5단계에서 정한 이름 기준(그 모델의 행에 없는 이름은 원자료 이름 그대로 견줌)."""
                return name_of(named, raw_name, model) == cname
            pid = mod.find_part(cell, {'설비코드': code, '모델': model_of[code]}, cname, spares, [dict(c) for c in cross], same_component)
            how = '내 판단 함수'
            asked.append((f'구성요소_목록.csv:{line}', code, cname, cell or '(빈칸)', pid if pid else '잇지 않음'))
        if pid is not None:
            if pid not in parts:
                raise Stop(f'결과/part_rules.py find_part: 자료/구성요소_목록.csv:{line}에 돌려준 「{pid}」는 예비품 목록에 없는 사내 품번입니다.')
            rel_('구성 요소-부품', cid, part_id[pid], source_text=cell or '(빈칸)')
            linked.append((code, cname, pid, how))
    groups = {}
    for c in cross:
        if c['표기종류'] == '제조사 품번':
            groups.setdefault(c['다른표기'], set()).add(c['사내품번'])
    same = []
    for code, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        verdict = mod.same_item(code, sorted(members))
        if verdict not in (True, False):
            raise Stop(f'결과/part_rules.py same_item: 「{code}」에 True 또는 False를 돌려줘야 합니다(돌려준 값 {verdict!r}).')
        same.append((code, sorted(members), verdict))
        if verdict:
            if '부품-부품' not in links:
                raise Stop('결과/관계.csv: 같은 물품으로 이을 「부품-부품」 연결의 관계 이름이 없습니다.')
            first, *rest = sorted(members)
            for other in rest:
                rel_('부품-부품', part_id[other], part_id[first], maker_part_no=code)
    info.update(물은_행=asked, 이은_부품=linked, 같은_규격=same, unused=[k for k in rows_done if k not in used_rows])
    model = write_model(ids, links, nodes, rels, bool([s for s in same if s[2]]))
    return info, model


def write_model(ids, links, nodes, rels, same_item):
    classes = {
        'Asset': {'meaning': '개별 설비', 'required': {'id': 'string', 'name': 'string', 'model': 'string', 'status': 'string'},
                  'optional': {'maker': 'string', 'serial': 'string', 'functional_location': 'string', 'installed': 'string', 'legacy_codes': 'list'}},
        'Component': {'meaning': '설비 안의 정비 가능 품목', 'required': {'id': 'string', 'name': 'string', 'group': 'string'},
                      'optional': {'serial': 'string', 'aliases': 'list'}},
        'Sensor': {'meaning': '설비별 계측 채널(실측 · 계산값 · 설정값)', 'required': {'id': 'string', 'tag': 'string', 'kind': ['measured', 'derived', 'setpoint'], 'derived': 'boolean'},
                   'optional': {'unit': 'string', 'normal': 'number', 'limit': 'number', 'limit_direction': ['upper', 'lower'], 'instrument_tag': 'string',
                                'sample_hz': 'number', 'collection': 'string', 'source_unit': 'string'}},
        'Quantity': {'meaning': '재는 물리량과 기준 단위', 'required': {'id': 'string', 'name': 'string'}, 'optional': {'unit': 'string'}},
        'Part': {'meaning': '사내 품번 하나로 관리하는 부품', 'required': {'id': 'string', 'name': 'string'}, 'optional': {'other_codes': 'list'}}}
    relations = {}
    for link, (name, start, end) in links.items():
        if link == '부품-부품' and not same_item:
            continue
        spec = relations.setdefault(name, {'from': [], 'to': LABEL[end], 'cardinality': ''})
        if spec['to'] != LABEL[end]:
            raise Stop(f'결과/관계.csv: 관계 이름 「{name}」을 끝이 다른 연결 둘에 썼습니다.')
        spec['from'].append(LABEL[start])
        if link == '구성 요소-부품':
            spec['properties'] = {'source_text': 'string'}
        if link == '부품-부품':
            spec['properties'] = {'maker_part_no': 'string'}
    for spec in relations.values():
        spec['from'] = spec['from'][0] if len(spec['from']) == 1 else spec['from']
        spec['cardinality'] = 'N:M'
    schema = {'classes': classes, 'relations': relations, 'identity': {LABEL[k]: v for k, v in ids.items()}}
    graph = {'nodes': nodes, 'rels': rels}
    OUT.mkdir(exist_ok=True)
    (OUT / 'schema.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (OUT / 'graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return schema, graph


# ───────────── 물어보기(모델만 읽는다 — 원자료를 다시 읽지 않는다) ─────────────
def load_model():
    schema = json.loads((OUT / 'schema.json').read_text(encoding='utf-8'))
    graph = json.loads((OUT / 'graph.json').read_text(encoding='utf-8'))
    return schema, graph


def answers(asks):
    """asks = [(질문, 물을 값)] → [{'질문','물을_값','항목','답'}]. 질문 1 = 설비 코드 → 구성 요소마다 붙은 센서 태그,
    질문 2 = 물리량 이름 → 그 물리량을 재는 센서(설비코드:태그), 질문 3 = 품번 · 표기 → 그 부품마다 쓰는 설비. 없으면 답 「없음」."""
    schema, graph = load_model()
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    rel_by = {}
    for r in graph['rels']:
        rel_by.setdefault(r['a'], []).append(r)
        rel_by.setdefault(r['b'], []).append(r)

    def neighbours(i, want):
        return sorted({(r['b'] if r['a'] == i else r['a']) for r in rel_by.get(i, []) if label.get(r['b'] if r['a'] == i else r['a']) == want})

    out = []
    for q, value in asks:
        q = str(q).strip()
        if q == '1':
            hit = [i for i, p in props.items() if label[i] == 'Asset' and (p.get('id') == value or value in p.get('legacy_codes', []))]
            if not hit:
                out.append({'질문': q, '물을_값': value, '항목': '', '답': '없음'})
                continue
            a = hit[0]
            for c in neighbours(a, 'Component'):
                tags = sorted(props[s]['tag'] for s in neighbours(c, 'Sensor'))
                if tags:      # 센서가 없는 구성 요소는 질문 1의 답이 아니다
                    out.append({'질문': q, '물을_값': value, '항목': props[c]['name'], '답': ' · '.join(tags)})
            direct = neighbours(a, 'Sensor')
            if direct:
                out.append({'질문': q, '물을_값': value, '항목': '설비 전체', '답': ' · '.join(sorted(props[s]['tag'] for s in direct))})
        elif q == '2':
            hit = [i for i, p in props.items() if label[i] == 'Quantity' and p.get('name') == value]
            if not hit:
                out.append({'질문': q, '물을_값': value, '항목': '', '답': '없음'})
                continue
            found = []
            for s in neighbours(hit[0], 'Sensor'):
                asset = next((a for c in neighbours(s, 'Component') for a in neighbours(c, 'Asset')), None) or next(iter(neighbours(s, 'Asset')), '')
                found.append(f'{props[asset]["id"] if asset else "?"}:{props[s]["tag"]}')
            out.append({'질문': q, '물을_값': value, '항목': '', '답': ' · '.join(sorted(found))})
        elif q == '3':
            ids = sorted(i for i, p in props.items() if label[i] == 'Part' and (i == value or value in p.get('other_codes', [])))
            if not ids:
                out.append({'질문': q, '물을_값': value, '항목': '', '답': '없음'})
                continue
            for pid in ids:
                group = {pid} | set(neighbours(pid, 'Part'))
                assets = sorted({a for p in group for c in neighbours(p, 'Component') for a in neighbours(c, 'Asset')})
                out.append({'질문': q, '물을_값': value, '항목': pid, '답': ' · '.join(props[a]['id'] for a in assets) or '쓰는 설비 없음'})
        else:
            raise Stop(f'결과/기대_답.csv: 질문 「{q}」 — 질문은 1 · 2 · 3입니다.')
    return out
