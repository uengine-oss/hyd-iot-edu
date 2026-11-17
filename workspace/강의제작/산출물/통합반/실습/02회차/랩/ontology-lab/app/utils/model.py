"""스키마와 지식 그래프를 만드는 제공 코드 — 원자료와 `app/features/`의 빈 틀(내가 정한 표 · 함수)을 읽어 `output/schema.json` · `output/graph.json`을 쓴다.

이 파일은 누가 해도 같은 일만 한다: 파일 읽기, 칸 공백 정리, 숫자 읽기, 단위를 물리량의 기준 단위로 맞추기, 교체부품 칸의 품번 찾기(괄호 속 품번 · 사내 품번 ·
품번 교차표에 하나로 적힌 표기), 계약 꼴로 쓰기, 모델에 물어보기. 무엇을 하나로 보고 무엇을 따로 둘지, 식별자를 무엇으로 짓고 관계를 어느 쪽으로 둘지는
`app/features/`의 빈 틀이 정한다. 빈 틀에 없는 것은 짐작하지 않고 파일 · 행과 함께 멈춘다.
직접 실행하지 않는다 — 루트 run.py가 요청한 기능을 실행한다.
"""
from pathlib import Path
import csv
import importlib.util
import io
import json
import re

HERE = Path(__file__).resolve().parents[2]
DATA = HERE / 'data'
OUT = HERE / 'app/features'
OUTPUT = HERE / 'output'
KINDS = ['설비', '구성 요소', '센서', '물리량', '부품']
OPTIONAL_KINDS = ['실물']      # 자리(구성 요소)와 일련번호가 붙은 실물을 나눌 때만 app/features/design.csv에 적는다
LABEL = {'설비': 'Asset', '구성 요소': 'Component', '센서': 'Sensor', '물리량': 'Quantity', '부품': 'Part', '실물': 'Unit'}
LINKS = {'설비-구성 요소': ('설비', '구성 요소'), '구성 요소-센서': ('구성 요소', '센서'), '센서-물리량': ('센서', '물리량'),
         '구성 요소-부품': ('구성 요소', '부품'), '구성 요소-실물': ('구성 요소', '실물')}
OPTIONAL_LINKS = ('구성 요소-실물',)   # 구성 요소 자리와 그 실물을 나눌 때만 적는 연결
FIELDS = {'설비': ['설비코드', '모델', '기능위치', '일련번호'], '구성 요소': ['설비코드', '구성요소', '계통'],
          '센서': ['설비코드', '태그'], '물리량': ['물리량'], '부품': ['품번'], '실물': ['설비코드', '구성요소', '일련번호']}
CARDINALITY = ('1:1', '1:N', 'N:1', 'N:M')   # 시작 쪽 수:끝 쪽 수 — 「1」 쪽은 많아야 하나
# 결정 지점(app/features/decisions.csv에 지점 이름이 미리 있는 줄)과 그것을 쓰는 단계. 그 단계를 실행할 때 고른_것 · 근거가 비었거나 미결이면 그 줄을 짚고 멈춘다.
DECISIONS = {'이름': ['구성 요소 자리와 그 실물'], '센서': ['같은 물리량의 범위'], '부품': []}
# 단위 환산(일반 지식): (원래 단위, 기준 단위) → 곱할 값
FACTOR = {('W', 'kW'): 0.001, ('kW', 'W'): 1000, ('kPa', 'bar'): 0.01, ('bar', 'kPa'): 100, ('MPa', 'bar'): 10, ('bar', 'MPa'): 0.1,
          ('l/min', 'L/min'): 1, ('L/min', 'l/min'): 1, ('lpm', 'L/min'): 1, ('°C', '℃'): 1, ('℃', '°C'): 1}
UNKNOWN = '미확인'


class Stop(Exception):
    """빈 틀에 없는 것 · 계약 어긋남. 글에 파일 · 행이 있다."""


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


def rules(name):
    """app/features/<name>.py(내가 쓴 판단 함수)를 불러온다."""
    path = OUT / f'{name}.py'
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ask(mod, fn, want, *args):
    """판단 함수 하나를 부르고 돌려준 값의 꼴을 본다(want = bool · str). 꼴이 다르면 함수 이름과 받은 값으로 멈춘다."""
    value = getattr(mod, fn)(*args)
    if want is bool and value not in (True, False):
        raise Stop(f'app/features/{mod.__name__}.py {fn}: True 또는 False를 돌려줘야 합니다(돌려준 값 {value!r}).')
    if want is str and not (isinstance(value, str) and value.strip()):
        raise Stop(f'app/features/{mod.__name__}.py {fn}: 빈칸이 아닌 글자를 돌려줘야 합니다(돌려준 값 {value!r}).')
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
    if m and m.group(1) in parts:
        return m.group(1), '괄호 속 품번'
    if cell in parts:
        return cell, '사내 품번'
    hits = sorted({c['사내품번'] for c in cross if c['다른표기'] == cell})
    if cell and len(hits) == 1 and hits[0] in parts:
        return hits[0], f'품번 교차표({next(c["표기종류"] for c in cross if c["다른표기"] == cell)})'
    return None, ''


# ───────────── 빈 틀 ─────────────
def decided(stage):
    """이 단계(와 그 앞 단계)가 쓰는 결정이 app/features/decisions.csv에 정해졌는가 — 고른 것이 맞는지는 보지 않는다(그것은 학생의 판단)."""
    order = list(DECISIONS)
    need_ = [p for s in order[:order.index(stage) + 1] for p in DECISIONS[s]]
    rows = {r['지점']: (line, r) for line, r in need(OUT / 'decisions.csv', ['지점', '고른_것', '근거', '바뀌는_답'])}
    for point in need_:
        if point not in rows:
            raise Stop(f'app/features/decisions.csv: 지점 「{point}」 줄이 없습니다 — 받은 빈 틀의 지점 줄을 지우지 않습니다.')
        line, r = rows[point]
        if not r['고른_것'] or r['고른_것'] == '미결' or not r['근거']:
            raise Stop(f'app/features/decisions.csv:{line}: 「{point}」의 고른_것 · 근거가 아직 비어 있습니다(미결 포함). 이 단계는 이 결정대로 모델을 만듭니다 — '
                       '선택지와 그 결과를 따져 보고 내가 고른 것과 근거를 적은 뒤 다시 실행합니다.')


def design():
    """design.csv → {대상: 식별자 틀}, relations.csv → {연결: (관계 이름, 시작 대상, 끝 대상, 카디널리티, 줄)}."""
    ids = {}
    for line, r in need(OUT / 'design.csv', ['대상', 'ID_만드는_법', '근거']):
        k = r['대상']
        if k not in KINDS + OPTIONAL_KINDS:
            raise Stop(f'app/features/design.csv:{line}: 대상 「{k}」 — 대상은 {" · ".join(KINDS + OPTIONAL_KINDS)} 가운데 하나입니다(실물은 구성 요소 자리와 그 실물을 나눌 때만).')
        bad = [x for x in re.findall(r'\{([^}]*)\}', r['ID_만드는_법']) if x not in FIELDS[k]]
        if bad or not re.search(r'\{[^}]+\}', r['ID_만드는_법']):
            raise Stop(f'app/features/design.csv:{line}: {k}의 ID_만드는_법 「{r["ID_만드는_법"]}」 — {{열 이름}} 꼴로 쓰고, 쓸 수 있는 열은 {", ".join(FIELDS[k])}입니다.')
        ids[k] = r['ID_만드는_법']
    miss = [k for k in KINDS if k not in ids]
    if miss:
        raise Stop('app/features/design.csv: ID_만드는_법이 없는 대상 — ' + ', '.join(miss))
    links = {}
    for line, r in need(OUT / 'relations.csv', ['연결', '관계_이름', '시작', '카디널리티', '근거']):
        k = r['연결']
        if k not in LINKS:
            raise Stop(f'app/features/relations.csv:{line}: 연결 「{k}」 — 연결은 {" · ".join(LINKS)} 가운데 하나입니다.')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', r['관계_이름']):
            raise Stop(f'app/features/relations.csv:{line}: 관계_이름 「{r["관계_이름"]}」 — 영어 대문자와 밑줄로 씁니다.')
        if r['시작'] not in LINKS[k]:
            raise Stop(f'app/features/relations.csv:{line}: 시작 「{r["시작"]}」 — {k} 연결의 시작은 {" · ".join(dict.fromkeys(LINKS[k]))} 가운데 하나입니다.')
        card = r['카디널리티'].replace(' ', '').upper()
        if card not in CARDINALITY:
            raise Stop(f'app/features/relations.csv:{line}: 카디널리티 「{r["카디널리티"]}」 — {" · ".join(CARDINALITY)} 가운데 하나입니다(시작 쪽 수:끝 쪽 수).')
        a, b = LINKS[k]
        links[k] = (r['관계_이름'], r['시작'], b if r['시작'] == a else a, card, line)
    miss = [k for k in LINKS if k not in links and k not in OPTIONAL_LINKS]
    if miss:
        raise Stop('app/features/relations.csv: 정하지 않은 연결 — ' + ', '.join(miss))
    if ('실물' in ids) != ('구성 요소-실물' in links):
        raise Stop('app/features/design.csv · app/features/relations.csv: 구성 요소 자리와 그 실물을 나누려면 design.csv에 「실물」 행과 relations.csv에 「구성 요소-실물」 행을 함께 적고, 나누지 않으면 둘 다 적지 않습니다.')
    by_name = {}
    for k, (name, start, end, card, line) in links.items():
        by_name.setdefault(name, []).append((k, line))
    for name, items in by_name.items():
        if len(items) > 1:
            raise Stop(f'app/features/relations.csv:{" · ".join(str(l) for _, l in items)}: 관계 이름 「{name}」을 연결 둘에 썼습니다 — 연결마다 다른 이름을 씁니다.')
    return ids, links


def make_id(template, kind, values, where):
    try:
        return template.format(**values)
    except KeyError as e:
        raise Stop(f'{where}: {kind} 식별자에 쓸 {e} 칸이 비었습니다.')


def name_map(src, rows_done, model_of):
    """원자료 구성 요소 행마다 이름을 정한다. 내 규칙(app/features/name_rules.py — same_device · group_name)으로 같은 장치끼리 묶어 묶음마다 이름 하나를 쓴다.
    어느 묶음에도 들지 않은 행은 원자료 이름 그대로다. 돌려주는 것: ({(원자료 이름, 모델): 이름}, 화면용 {묶음, 다른 이름과 묶이지 않은 행})."""
    mod = rules('name_rules')
    parts = {r['품번'] for _, r in src['spare_parts.csv']}
    cross = [r for _, r in src['part_aliases.csv']]
    live_sensors = [(line, r) for line, r in src['sensors.csv'] if not rows_done.get(('sensors.csv', line))]
    items = []
    for line, r in src['components.csv']:
        if rows_done.get(('components.csv', line)) or r['설비코드'] not in model_of:
            continue
        tags = sorted(s['태그'] for _, s in live_sensors if s['설비코드'] == r['설비코드'] and s['붙은곳'] == r['구성요소'])
        items.append({'설비코드': r['설비코드'], '모델': model_of[r['설비코드']], '계통': r['계통'], '이름': r['구성요소'], '태그': tags,
                      '부품': resolve_cell(r['교체부품'], parts, cross)[0] or '', '줄': f'components.csv:{line}'})
    groups = grouped(items, lambda a, b: ask(mod, 'same_device', bool, dict(a, 태그=list(a['태그'])), dict(b, 태그=list(b['태그']))))
    named, by_rule = {}, []
    for members in groups:
        name = ask(mod, 'group_name', str, [dict(m, 태그=list(m['태그'])) for m in members]) if len(members) > 1 else members[0]['이름']
        for m in members:
            key = (m['이름'], m['모델'])
            if key in named and named[key] != name:
                raise Stop(f'app/features/name_rules.py: 같은 모델({m["모델"]})의 원자료 이름 「{m["이름"]}」이 두 묶음({named[key]} · {name})에 들어갔습니다 — {m["줄"]}.')
            named[key] = name
        if len(members) > 1:
            by_rule.append((name, len(members), ' · '.join(sorted({f'{m["이름"]}({m["설비코드"]})' for m in members}))))
    alone = [(m['줄'], m['설비코드'], m['계통'], m['이름']) for members in groups if len(members) == 1 for m in members]
    return named, {'묶음': sorted(by_rule), '그대로': sorted(alone, key=lambda x: int(x[0].split(':')[1]))}


def name_of(named, raw, model):
    """원자료 이름(붙은곳)을 같은 장치끼리 묶어 정한 이름으로. 그 모델의 구성 요소 행에 없는 이름은 원자료 이름 그대로 견준다."""
    return named.get((raw, model), raw)


def handling():
    """row_rules.csv → ({(파일, 행): (처리, 대상)}, {(파일, 행): row_rules.csv 줄}). 처리 = 빼기 · 지난 실물:<지금 행>."""
    out, where = {}, {}
    for line, r in need(OUT / 'row_rules.csv', ['파일', '행', '처리', '근거']):
        if not r['행'].isdigit():
            raise Stop(f'app/features/row_rules.csv:{line}: 행 「{r["행"]}」 — 편집기에 보이는 줄 번호(숫자)를 씁니다.')
        how = r['처리']
        r['파일'] = r['파일'].removeprefix('data/')      # 「data/sensors.csv」처럼 폴더를 붙여 적어도 같은 파일
        if r['파일'] not in ('equipment.csv', 'components.csv', 'sensors.csv'):
            raise Stop(f'app/features/row_rules.csv:{line}: 파일 「{r["파일"]}」 — equipment.csv · components.csv · sensors.csv 가운데 하나입니다.')
        key = (r['파일'], int(r['행']))
        if how == '빼기':
            out[key] = ('빼기', '')
        elif re.fullmatch(r'지난 실물:\d+', how) and r['파일'] == 'components.csv':
            out[key] = ('지난 실물', int(how.split(':', 1)[1]))
        else:
            raise Stop(f'app/features/row_rules.csv:{line}: 처리 「{how}」 — 빼기 · 지난 실물:<지금 실물 행 번호>(components.csv만) 가운데 하나로 씁니다.')
        where[key] = line
    return out, where


def quantity_map(src, rows_done, assets, place_of):
    """센서 행마다 물리량을 정한다. 내 규칙(app/features/quantity_rules.py — same_quantity · quantity_name)으로 같은 물리량끼리 묶는다. place_of(센서 행) = (붙은 구성 요소 이름, 계통).
    규칙이 서로 다른 묶음에 같은 물리량 이름을 붙이면 멈춘다(같은 이름이면 같은 물리량으로 합쳐지므로). 돌려주는 것: {센서 줄: 물리량}."""
    mod = rules('quantity_rules')
    items = []
    for line, r in src['sensors.csv']:
        if rows_done.get(('sensors.csv', line)) or r['설비코드'] not in assets:
            continue
        place, group = place_of(line, r)
        items.append((line, {**{k: r[k] for k in ('설비코드', '태그', '센서명', '재는것', '단위')}, '붙은곳': place, '계통': group, '줄': f'sensors.csv:{line}'}))
    out, named = {}, {}
    for members in grouped(items, lambda a, b: ask(mod, 'same_quantity', bool, dict(a[1]), dict(b[1]))):
        name = ask(mod, 'quantity_name', str, [dict(m) for _, m in members])
        if name in named:
            raise Stop(f'app/features/quantity_rules.py: 서로 다른 묶음 둘에 같은 물리량 이름 「{name}」을 붙였습니다 — {named[name]} · {members[0][1]["줄"]}. '
                       '같은 물리량이면 same_quantity가 묶게 하고, 다른 물리량이면 이름을 달리합니다.')
        named[name] = members[0][1]['줄']
        for line, _ in members:
            out[line] = name
    return out


def unit_map(src, qmap):
    """물리량마다 기준 단위(일반 처리): 그 물리량의 센서 행이 가장 많이 쓴 단위(같은 수면 센서 목록에서 먼저 나온 것). 단위가 적힌 행이 없으면 미확인.
    돌려주는 것: ({물리량: 기준 단위}, 화면용 [(물리량, 원자료에 적힌 단위, 기준 단위)])."""
    per_q = {}
    for line, r in src['sensors.csv']:
        if line in qmap:
            per_q.setdefault(qmap[line], []).append(r['단위'])
    base, shown = {}, []
    for q, units in sorted(per_q.items()):
        written = [u for u in units if u]
        base[q] = max(written, key=lambda u: (written.count(u), -written.index(u))) if written else UNKNOWN
        shown.append((q, ' · '.join(f'{u} {written.count(u)}행' for u in dict.fromkeys(written)) or '(적힌 단위 없음)', base[q]))
    return base, shown


# ───────────── 만들기(단계별) ─────────────
def raw():
    return {n: table(DATA / n) for n in ['equipment.csv', 'components.csv', 'sensors.csv', 'spare_parts.csv', 'part_aliases.csv']}


def preview_ids():
    """내 식별자 틀로 원자료 행마다 식별자를 지었을 때 겹치는 것(이름은 아직 원자료 그대로). 실물은 일련번호가 적힌 구성 요소 행으로 짓는다."""
    ids, links = design()
    src = raw()
    out = {}
    for kind, file in [('설비', 'equipment.csv'), ('구성 요소', 'components.csv'), ('센서', 'sensors.csv'), ('실물', 'components.csv')]:
        if kind not in ids:
            continue
        seen = {}
        for line, r in src[file]:
            if kind == '실물' and not r['일련번호']:
                continue
            seen.setdefault(make_id(ids[kind], kind, r, f'data/{file}:{line}'), []).append(line)
        out[kind] = {'개수': len(seen), '겹침': {k: v for k, v in seen.items() if len(v) > 1}, '파일': file}
    return ids, links, out


def check_cardinality(links, rels, where_of):
    """relations.csv에 적은 카디널리티를 지금까지 만든 연결과 견준다. 「1」 쪽에 둘 이상 이어진 대상이 있으면 그 relations.csv 줄과 원자료 줄을 짚고 멈춘다.
    돌려주는 것: 화면용 [(연결, 관계, 적은 것, 시작 하나에 이어진 끝 최대 수, 끝 하나에 이어진 시작 최대 수, 견줌)]."""
    shown = []
    for link, (name, _, _, card, line) in links.items():
        out_n, in_n = {}, {}
        for i, r in enumerate(rels):
            if r['type'] == name:
                out_n.setdefault(r['a'], []).append(i)
                in_n.setdefault(r['b'], []).append(i)
        if not out_n:
            continue
        most_out, most_in = max(len(v) for v in out_n.values()), max(len(v) for v in in_n.values())
        start_side, end_side = card.split(':')
        for side, count, word in [(end_side, out_n, '시작 하나에 끝이'), (start_side, in_n, '끝 하나에 시작이')]:
            if side == '1':
                over = [(x, v) for x, v in count.items() if len(v) > 1]
                if over:
                    x, v = over[0]
                    raise Stop(f'app/features/relations.csv:{line}: {name} 카디널리티 {card} — {word} 많아야 하나인데, {x}에 {len(v)}개가 이어집니다'
                               f'({" · ".join(where_of[i] for i in v[:4])}). 원자료가 맞으면 카디널리티를, 연결이 잘못이면 그 판단을 고칩니다'
                               f'(이렇게 걸린 대상 {len(over)}개).')
        loose = (start_side != '1' and most_in == 1) or (end_side != '1' and most_out == 1)
        shown.append((link, name, card, most_out, most_in, '적은 것보다 실제 연결이 좁음(N 쪽에 하나뿐)' if loose else '맞음'))
    return shown


def build(stage):
    """stage = '이름' · '센서' · '부품'까지 만든다. 돌려주는 것: 화면용 값과 (부품 단계면) 쓴 모델."""
    ids, links = design()
    decided(stage)
    split = '실물' in ids
    src = raw()
    rows_done, rule_line = handling()
    nodes, rels, where_of, index, info = [], [], [], {}, {}
    used_rows = set()

    def handled(file, line):
        h = rows_done.get((file, line))
        if h:
            used_rows.add((file, line))
        return h

    def node(label, id_, where, **props):
        if id_ in index:
            raise Stop(f'{where}: 식별자 「{id_}」가 이미 있습니다(겹친 행). app/features/row_rules.csv에 이 행을 어떻게 할지 정하거나 app/features/design.csv의 식별자를 바꿉니다.')
        index[id_] = label
        nodes.append({'labels': [label], 'props': {'id': id_, **{k: v for k, v in props.items() if v not in (None, '', [])}}})

    def rel_(link, a, b, where, **props):
        name, start, *_ = links[link]
        first = LINKS[link][0]
        x, y = (a, b) if start == first else (b, a)
        rels.append({'type': name, 'a': x, 'b': y, 'props': {k: v for k, v in props.items() if v not in (None, '')}})
        where_of.append(where)

    for (file, line), (how, target) in rows_done.items():
        if how == '지난 실물' and not split:
            raise Stop(f'app/features/row_rules.csv:{rule_line[(file, line)]}: 「지난 실물」은 구성 요소 자리와 그 실물을 나눌 때(app/features/design.csv에 실물 행)만 씁니다 — 나누지 않으면 「빼기」로 둡니다.')

    # 설비
    assets, model_of = {}, {}
    for line, r in src['equipment.csv']:
        if handled('equipment.csv', line):
            continue
        assets[r['설비코드']] = make_id(ids['설비'], '설비', r, f'data/equipment.csv:{line}')
        model_of[r['설비코드']] = r['모델']
        node('Asset', assets[r['설비코드']], f'data/equipment.csv:{line}', name=r['설비명'], model=r['모델'], maker=r['제조사'], serial=r['일련번호'],
             functional_location=r['기능위치'], installed=r['설치일'], status=r['상태'])
    # 구성 요소(자리)와, 나누기로 했으면 그 자리의 실물
    comps, per_asset, comp_at_row = {}, {}, {}
    for line, r in src['components.csv']:
        if r['설비코드'] not in assets and not rows_done.get(('components.csv', line)):
            raise Stop(f'data/components.csv:{line}: 설비코드 「{r["설비코드"]}」가 모델의 설비에 없습니다.')
    named, name_info = name_map(src, rows_done, model_of)
    info['이름'] = name_info
    units = []

    def unit(cid, r, line, current):
        uid = make_id(ids['실물'], '실물', {**r, '구성요소': name_of(named, r['구성요소'], model_of[r['설비코드']])}, f'data/components.csv:{line}')
        node('Unit', uid, f'data/components.csv:{line}', serial=r['일련번호'])
        rel_('구성 요소-실물', cid, uid, f'components.csv:{line}', current=current)
        units.append((cid, r['일련번호'], '지금' if current else '지난', f'components.csv:{line}'))
    for line, r in src['components.csv']:
        per_asset.setdefault(r['설비코드'], [0, 0])[0] += 1
        if handled('components.csv', line):
            continue
        code = r['설비코드']
        cname = name_of(named, r['구성요소'], model_of[code])
        cid = make_id(ids['구성 요소'], '구성 요소', {**r, '구성요소': cname}, f'data/components.csv:{line}')
        node('Component', cid, f'data/components.csv:{line}', name=cname, group=r['계통'], serial=None if split else r['일련번호'],
             aliases=[r['구성요소']] if r['구성요소'] != cname else None)
        rel_('설비-구성 요소', assets[code], cid, f'components.csv:{line}')
        comps[(code, cname)] = (cid, line, r)
        comp_at_row[line] = (code, cname, cid)
        per_asset[code][1] += 1
        if split and r['일련번호']:
            unit(cid, r, line, True)
    by_line = dict(src['components.csv'])
    for (file, line), (how, target) in sorted(rows_done.items()):
        if how != '지난 실물':
            continue
        r = by_line.get(line)
        now = comp_at_row.get(target)
        if r is None or now is None or (r['설비코드'], name_of(named, r['구성요소'], model_of.get(r['설비코드'], ''))) != now[:2]:
            raise Stop(f'app/features/row_rules.csv:{rule_line[(file, line)]}: 「지난 실물:{target}」 — components.csv:{target}이 이 행(:{line})과 같은 설비 · 같은 자리의 살아 있는 행이어야 합니다.')
        if not r['일련번호']:
            raise Stop(f'app/features/row_rules.csv:{rule_line[(file, line)]}: components.csv:{line}에 일련번호가 없어 지난 실물로 남길 수 없습니다.')
        unit(now[2], r, line, False)
    info['구성 요소'] = {code: tuple(v) for code, v in sorted(per_asset.items())}
    info['실물'] = units if split else None
    if stage == '이름':
        check_cardinality(links, rels, where_of)
        info.update(unused=[k for k in rows_done if k not in used_rows and k[0] in ('equipment.csv', 'components.csv')])
        return info, None
    # 센서와 물리량 — 단위는 물리량의 기준 단위로 맞춘다(일반 처리)
    for line, r in src['sensors.csv']:
        if r['설비코드'] not in assets and not rows_done.get(('sensors.csv', line)):
            raise Stop(f'data/sensors.csv:{line}: 설비코드 「{r["설비코드"]}」가 모델의 설비에 없습니다.')

    def place_of(line, r):
        cname = name_of(named, r['붙은곳'], model_of[r['설비코드']])
        if (r['설비코드'], cname) not in comps:
            raise Stop(f'data/sensors.csv:{line}: 붙은곳 「{r["붙은곳"]}」(→ {cname})이 {r["설비코드"]}의 구성 요소에 없습니다 — 같은 장치의 이름이 하나로 묶였는지 봅니다.')
        return cname, comps[(r['설비코드'], cname)][2]['계통']
    qmap = quantity_map(src, rows_done, assets, place_of)
    base, base_shown = unit_map(src, qmap)
    info['단위'] = base_shown
    sensors, quants, convs = [], {}, []
    for line, r in src['sensors.csv']:
        if handled('sensors.csv', line):
            continue
        code, qname = r['설비코드'], qmap[line]
        qid = make_id(ids['물리량'], '물리량', {'물리량': qname}, f'data/sensors.csv:{line}')
        sid = make_id(ids['센서'], '센서', r, f'data/sensors.csv:{line}')
        normal, limit = number(r['정상값']), number(r['한계'])
        for col in ('정상값', '한계'):
            if r[col] and not re.fullmatch(r'-?\d+(?:\.\d+)?', r[col]):
                raise Stop(f'data/sensors.csv:{line}: {col} 칸 「{r[col]}」 — 숫자만 읽습니다. 글이 섞인 값은 이 도구가 바꾸지 못합니다.')
        unit_ = r['단위'] or UNKNOWN
        if unit_ == UNKNOWN or base[qname] == UNKNOWN:
            factor, out_unit = 1, None
        elif unit_ == base[qname]:
            factor, out_unit = 1, unit_
        elif (unit_, base[qname]) in FACTOR:
            factor, out_unit = FACTOR[(unit_, base[qname])], base[qname]
        else:
            raise Stop(f'data/sensors.csv:{line}: 단위 「{unit_}」를 물리량 「{qname}」의 기준 단위 「{base[qname]}」로 바꾸는 법을 모릅니다'
                       f'(이 도구가 아는 환산: {", ".join(f"{a}→{b}" for a, b in FACTOR)}). 단위가 다른 것을 재는 센서가 한 물리량에 묶였는지 봅니다.')
        if out_unit != unit_:
            convs.append((f'sensors.csv:{line}', sid, qname, unit_, out_unit or UNKNOWN,
                          f'{r["정상값"] or "없음"} / {r["한계"] or "없음"}', f'{"없음" if normal is None else "%g" % round(normal * factor, 6)} / {"없음" if limit is None else "%g" % round(limit * factor, 6)}'))
        node('Sensor', sid, f'data/sensors.csv:{line}', tag=r['태그'], name=r['센서명'], unit=out_unit, source_unit=unit_ if out_unit and out_unit != unit_ else None,
             normal=None if normal is None else round(normal * factor, 6), limit=None if limit is None else round(limit * factor, 6),
             limit_direction={'상한': 'upper', '하한': 'lower'}.get(r['한계구분']))
        rel_('구성 요소-센서', comps[(code, place_of(line, r)[0])][0], sid, f'sensors.csv:{line}')
        quants.setdefault(qid, (qname, None if base[qname] == UNKNOWN else base[qname]))
        rel_('센서-물리량', sid, qid, f'sensors.csv:{line}')
        sensors.append((sid, code, r['태그'], qname))
    for qid, (qname, unit_) in quants.items():
        node('Quantity', qid, f'app/features/quantity_rules.py ({qname})', name=qname, unit=unit_)
    info['센서'] = sensors
    info['변환'] = convs
    if stage == '센서':
        check_cardinality(links, rels, where_of)
        info.update(unused=[k for k in rows_done if k not in used_rows])
        return info, None
    # 부품 — 식별자는 사내 품번, 다른 표기는 그 부품의 다른 이름(other_codes)
    parts = {r['품번']: (line, r) for line, r in src['spare_parts.csv']}
    cross = [r for _, r in src['part_aliases.csv']]
    part_id, codes = {}, []
    for pid, (line, r) in parts.items():
        part_id[pid] = make_id(ids['부품'], '부품', r, f'data/spare_parts.csv:{line}')
        other = sorted({c['다른표기'] for c in cross if c['사내품번'] == pid})
        node('Part', part_id[pid], f'data/spare_parts.csv:{line}', name=r['품명'], other_codes=other)
        codes.append((part_id[pid], r['품명'], ' · '.join(other) or '없음'))
    linked, lost = [], []
    for (code, cname), (cid, line, r) in comps.items():
        cell = r['교체부품']
        pid, how = resolve_cell(cell, parts, cross)
        if pid is None:      # 품번으로 풀리지 않는 칸은 짐작해 잇지 않고 화면에 보인다
            lost.append((f'components.csv:{line}', code, cname, cell or '(빈칸)'))
            continue
        rel_('구성 요소-부품', cid, part_id[pid], f'components.csv:{line}', source_text=cell)
        linked.append((f'components.csv:{line}', code, cname, cell, pid, how))
    info['카디널리티'] = check_cardinality(links, rels, where_of)
    info.update(이은_부품=linked, 못_찾은_칸=lost, 다른_표기=codes, unused=[k for k in rows_done if k not in used_rows])
    return info, write_model(ids, links, nodes, rels)


def write_model(ids, links, nodes, rels):
    split = '실물' in ids
    classes = {
        'Asset': {'meaning': '개별 설비', 'required': {'id': 'string', 'name': 'string', 'model': 'string', 'status': 'string'},
                  'optional': {'maker': 'string', 'serial': 'string', 'functional_location': 'string', 'installed': 'string'}},
        'Component': ({'meaning': '설비 안의 정비 가능 품목이 놓인 자리', 'required': {'id': 'string', 'name': 'string', 'group': 'string'},
                       'optional': {'aliases': 'list'}} if split else
                      {'meaning': '설비 안의 정비 가능 품목', 'required': {'id': 'string', 'name': 'string', 'group': 'string'},
                       'optional': {'serial': 'string', 'aliases': 'list'}}),
        'Sensor': {'meaning': '설비별 계측 채널', 'required': {'id': 'string', 'tag': 'string'},
                   'optional': {'name': 'string', 'unit': 'string', 'normal': 'number', 'limit': 'number', 'limit_direction': ['upper', 'lower'], 'source_unit': 'string'}},
        'Quantity': {'meaning': '재는 물리량과 기준 단위', 'required': {'id': 'string', 'name': 'string'}, 'optional': {'unit': 'string'}},
        'Part': {'meaning': '사내 품번 하나로 관리하는 부품. 다른 표기는 other_codes', 'required': {'id': 'string', 'name': 'string'}, 'optional': {'other_codes': 'list'}}}
    if split:
        classes['Unit'] = {'meaning': '일련번호가 붙은 실물 한 대', 'required': {'id': 'string', 'serial': 'string'}}
    relations, names = {}, {}
    for link, (name, start, end, card, _) in links.items():
        relations[name] = {'from': LABEL[start], 'to': LABEL[end], 'cardinality': card}
        if link == '구성 요소-부품':
            relations[name]['properties'] = {'source_text': 'string'}
        if link == '구성 요소-실물':
            relations[name]['properties'] = {'current': 'boolean'}
        names[link] = name
    schema = {'classes': classes, 'relations': relations, 'identity': {LABEL[k]: v for k, v in ids.items()}, 'links': names}
    graph = {'nodes': nodes, 'rels': rels}
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / 'schema.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (OUTPUT / 'graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return schema, graph


# ───────────── 물어보기(모델만 읽는다 — 원자료를 다시 읽지 않는다) ─────────────
def load_model():
    schema = json.loads((OUTPUT / 'schema.json').read_text(encoding='utf-8'))
    graph = json.loads((OUTPUT / 'graph.json').read_text(encoding='utf-8'))
    return schema, graph


def value_text(p):
    """질문 2 센서 값 — 「단위 · 정상값 · 한계 · 한계구분」 차례. 값 없음은 「없음」, 단위를 정하지 못했으면 「미확인」."""
    def num(v):
        return '없음' if v is None else ('%g' % v)
    return ' · '.join([p.get('unit') or UNKNOWN, num(p.get('normal')), num(p.get('limit')), {'upper': '상한', 'lower': '하한'}.get(p.get('limit_direction'), '없음')])


def answers(asks):
    """asks = [(질문, 물을 값)] → [{'질문','물을_값','항목','답'}].
    질문 1 = 설비 코드 → 구성 요소마다 붙은 센서 태그(항목 = 구성 요소 이름)와 그 자리에 달린 실물의 일련번호(항목 = 「구성 요소 이름 실물」 —
    실물을 따로 둔 모델이면 「일련번호(지금)」 · 「일련번호(지난)」, 아니면 구성 요소의 일련번호 속성 하나).
    질문 2 = 물리량 이름 → 그 물리량을 재는 센서(설비코드:태그, 항목 빈칸)와 센서마다 값(항목 = 설비코드:태그, 답 = 단위 · 정상값 · 한계 · 한계구분).
    질문 3 = 품번 · 표기 → 그 부품을 쓰는 설비. 없으면 답 「없음」."""
    schema, graph = load_model()
    unit_type = schema.get('links', {}).get('구성 요소-실물')
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
            if label.get(value) != 'Asset' and not any(label[i] == 'Asset' and p.get('id') == value for i, p in props.items()):
                out.append({'질문': q, '물을_값': value, '항목': '', '답': '없음'})
                continue
            for c in neighbours(value, 'Component'):
                tags = sorted(props[s]['tag'] for s in neighbours(c, 'Sensor'))
                if tags:      # 센서가 없는 구성 요소는 센서 줄을 내지 않는다
                    out.append({'질문': q, '물을_값': value, '항목': props[c]['name'], '답': ' · '.join(tags)})
                if unit_type:
                    held = sorted(((not r['props'].get('current'), props[r['b'] if r['a'] == c else r['a']]['serial']) for r in rel_by.get(c, []) if r['type'] == unit_type))
                    serials = ' · '.join(f'{s}({"지난" if past else "지금"})' for past, s in held)
                else:
                    serials = props[c].get('serial', '')
                if serials:
                    out.append({'질문': q, '물을_값': value, '항목': props[c]['name'] + ' 실물', '답': serials})
        elif q == '2':
            hit = [i for i, p in props.items() if label[i] == 'Quantity' and p.get('name') == value]
            if not hit:
                out.append({'질문': q, '물을_값': value, '항목': '', '답': '없음'})
                continue
            found = []
            for s in neighbours(hit[0], 'Sensor'):
                asset = next((a for c in neighbours(s, 'Component') for a in neighbours(c, 'Asset')), '')
                key = f'{props[asset]["id"] if asset else "?"}:{props[s]["tag"]}'
                found.append(key)
                out.append({'질문': q, '물을_값': value, '항목': key, '답': value_text(props[s])})
            out.append({'질문': q, '물을_값': value, '항목': '', '답': ' · '.join(sorted(found))})
        elif q == '3':
            ids = sorted(i for i, p in props.items() if label[i] == 'Part' and (i == value or value in p.get('other_codes', [])))
            if not ids:
                out.append({'질문': q, '물을_값': value, '항목': '', '답': '없음'})
                continue
            for pid in ids:
                assets = sorted({a for c in neighbours(pid, 'Component') for a in neighbours(c, 'Asset')})
                out.append({'질문': q, '물을_값': value, '항목': pid, '답': ' · '.join(props[a]['id'] for a in assets) or '쓰는 설비 없음'})
        else:
            raise Stop(f'app/features/expected.csv: 질문 「{q}」 — 질문은 1 · 2 · 3입니다.')
    return out
