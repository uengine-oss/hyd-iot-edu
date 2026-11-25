from pathlib import Path
import csv, io, json, re, traceback
HERE = Path(__file__).resolve().parents[2]

class Stop(Exception):
    """단계를 멈추는 알려진 까닭(계약 어긋남 · 랩 DB 꺼짐). 글은 그대로 화면에 빨갛게 쓴다."""


class Blank(Stop):
    """`app/features/` 파일 안에서 이 단계 몫이 아직 비었음(예: 조회 파일에 이 질문의 조회가 아직 없음). 해당 조회를 작성한 뒤 실행한다."""


def rel(path):
    """화면에 쓰는 경로 — 이 폴더 기준 상대 경로(절대 경로를 쓰지 않는다)."""
    p = Path(path)
    try:
        return p.resolve().relative_to(HERE).as_posix()
    except ValueError:
        return p.name


def read_text(path):
    """(글, 글자 방식). UTF-8(BOM 포함)로 읽고, 안 되면 CP949로 읽는다 — 어느 쪽으로 읽었는지 함께 돌려준다."""
    data = Path(path).read_bytes()
    try:
        return data.decode('utf-8-sig'), 'UTF-8'
    except UnicodeDecodeError:
        return data.decode('cp949'), 'CP949'


def read_table(path):
    """CSV 한 장 → [dict]. 첫머리의 # 줄(「제공 빈 틀」 표시 · 설명)은 건너뛰고, 칸 앞뒤 공백은 정리한다."""
    text, _ = read_text(path)
    kept = [(no, x) for no, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')]
    if not kept:
        raise Stop(f'{rel(path)}: 열 이름 줄이 없습니다 — 받은 빈 틀의 열 이름 줄을 지우지 않습니다.')
    rows = []
    reader = csv.DictReader(io.StringIO('\n'.join(x for _, x in kept)))
    for row in reader:
        line = kept[reader.line_num - 1][0]      # 건너뛴 # 줄 · 빈 줄을 셈에 넣은 실제 파일 줄 번호
        if None in row:      # 넘친 칸을 끝 칸에 이어 붙이지 않는다 — 앞 칸에 쉼표가 든 줄은 값이 한 칸씩 밀린 채 조용히 지나간다
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름({len(reader.fieldnames)}칸)보다 많습니다 — 값 안에 쉼표가 있으면 그 값을 큰따옴표로 감싸거나 쉼표를 「 · 」로 바꿉니다.')
        if None in row.values():
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름({len(reader.fieldnames)}칸)보다 적습니다 — 빈 칸도 쉼표로 자리를 둡니다.')
        rows.append({k.strip(): (v or '').strip() for k, v in row.items() if k is not None})
    return rows


def read_json(path):
    try:
        return json.loads(read_text(path)[0])
    except json.JSONDecodeError as e:
        raise Stop(f'{rel(path)}:{e.lineno}: JSON 꼴이 아닙니다 — {e.msg}')


def source_lines(path, start, end=None):
    """원문 줄 보기 블록 — (파일, 줄 범위)를 줄 번호와 함께. 글자 방식을 함께 적는다."""
    text, enc = read_text(path)
    lines = text.splitlines()
    end = end or start
    if not 1 <= start <= end <= len(lines):
        raise Stop(f'{rel(path)}: {start}~{end}줄이 없습니다(전체 {len(lines)}줄).')
    return {'kind': 'source', 'title': f'{rel(path)} {start}' + (f'~{end}' if end != start else '') + f'줄 ({enc})',
            'lines': [(n, lines[n - 1]) for n in range(start, end + 1)]}


def table(title, columns, rows, note=''):
    """표. rows = [[칸, …]] 또는 [dict]. 행이 많으면 접고, 글자 거르기 · 정렬을 붙인다."""
    rows = [[r.get(c, '') for c in columns] if isinstance(r, dict) else list(r) for r in rows]
    return {'kind': 'table', 'title': title, 'columns': list(columns), 'rows': rows, 'note': note}


def counts(title, items, note=''):
    """개수 — items = [(이름, 값)]. 직전 실행의 같은 이름 값과 나란히 보인다(전후 비교)."""
    return {'kind': 'counts', 'title': title, 'items': [(str(k), v) for k, v in items], 'note': note}


def compare(title, key, expected, actual, columns, note='', same=None):
    """기대 ↔ 실제 대조. expected · actual = [dict], key = 짝을 짓는 열, columns = 견줄 열.
    칸에는 앞뒤 · 겹친 공백만 정리한 원래 글을 보인다. same(기대 글, 실제 글)을 주면 그것으로 견주고, 없으면 그 글이 같아야 같음.
    행마다 같음 · 다름 · 실제 없음 · 기대 밖."""
    def norm(v):
        return re.sub(r'\s+', ' ', str(v if v is not None else '')).strip()
    for side, data in (('기대', expected), ('실제', actual)):
        keys = [norm(r.get(key)) for r in data]
        twice = sorted({k for k in keys if keys.count(k) > 1})
        if twice:      # 조용히 한 줄만 남기지 않는다
            raise Stop(f'{title}: {side} 쪽에 같은 짝이 두 번 있습니다 — ' + ', '.join(twice))
    exp = {norm(r.get(key)): r for r in expected}
    act = {norm(r.get(key)): r for r in actual}
    rows = []
    for k in list(exp) + [k for k in act if k not in exp]:
        e, a = exp.get(k), act.get(k)
        if e is None:
            state = '기대 밖'
        elif a is None:
            state = '실제 없음'
        else:
            state = '같음' if all((same or str.__eq__)(norm(e.get(c)), norm(a.get(c))) for c in columns) else '다름'
        rows.append({'key': k, 'state': state, 'cells': [(norm(e.get(c)) if e else '', norm(a.get(c)) if a else '') for c in columns]})
    return {'kind': 'compare', 'title': title, 'key': key, 'columns': list(columns), 'rows': rows, 'note': note}


def before_after(title, before, after, note=''):
    """전후 비교 — before · after = {이름: 값}. 늘어남 · 사라짐 · 값 바뀜만 표로."""
    rows = []
    for k in sorted(set(before) | set(after)):
        if k not in before:
            rows.append((k, '늘어남', '', after[k]))
        elif k not in after:
            rows.append((k, '사라짐', before[k], ''))
        elif before[k] != after[k]:
            rows.append((k, '값 바뀜', before[k], after[k]))
    return {'kind': 'diff', 'title': title, 'rows': [[str(c) if not isinstance(c, str) else c for c in r] for r in rows],
            'same': len(set(before) & set(after)) - sum(r[1] == '값 바뀜' for r in rows), 'note': note}


def note(text):
    return {'kind': 'note', 'text': text}


def error(title, text):
    return {'kind': 'error', 'title': title, 'text': text}


def where(exc):
    """예외가 난 곳 가운데 이 폴더 안 파일의 마지막 줄(파일:줄)."""
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        try:
            return f'{Path(frame.filename).resolve().relative_to(HERE).as_posix()}:{frame.lineno}'
        except ValueError:
            continue
    return ''


# ───────────── 그림 블록(app/ui/render.py가 그린다) — 값은 모두 실행한 기능이 넘긴 실제 결과다 ─────────────
def verdict(state, text, detail=''):
    """결과 화면 맨 위의 결론 한 줄. state = 'ok'(맞음) · 'warn'(볼 곳 있음) · 'bad'(다름) · 'info'(본 것)."""
    return {'kind': 'verdict', 'state': state, 'text': text, 'detail': detail}


def node(id, kind, text=None, sub='', props=None, mark='', badge='', at=None):
    """그림의 노드 하나. kind = 종류(색을 정한다), props = 마우스를 올리면 보일 속성, mark = ask · bad · new · gone · dim, at = 그림 도구가 준 자리 (x, y)."""
    return {'id': str(id), 'kind': kind, 'text': str(id if text is None else text), 'sub': sub, 'props': props or {}, 'mark': mark, 'badge': badge, 'at': at}


def edge(a, b, text='', mark=''):
    """그림의 관계 하나(a → b). mark = hit(따라간 길) · bad · dim · gone."""
    return {'a': str(a), 'b': str(b), 'text': text, 'mark': mark}


def graph(title, nodes, links, note='', columns=None, marks=None):
    """노드와 관계 그림. columns = 왼쪽부터 놓을 종류 차례(없으면 관계 방향을 따라 시작 쪽이 왼쪽), marks = 범례에 쓸 표시의 뜻 {mark: 글}."""
    return {'kind': 'graph', 'title': title, 'nodes': nodes, 'links': links, 'note': note, 'columns': columns, 'marks': marks or {}}


def gather(title, heads, rows, note=''):
    """여럿이 하나로 모이는 그림. heads = (왼쪽 머리, 가운데 머리[, 오른쪽 머리]), rows = [{'left': [조각], 'mid': 조각, 'right': [조각], 'mark': ''}].
    조각 = 글 또는 {'text', 'kind'(색), 'sub', 'mark'}."""
    return {'kind': 'gather', 'title': title, 'heads': list(heads), 'rows': rows, 'note': note}


def cards(title, items, note='', wide=False):
    """카드 묶음. items = [{'title', 'badge', 'state'(ok · bad · warn), 'icon'(ok · bad · warn · lock · open), 'kind'(색), 'text', 'lines': [글 또는 (머리, 「 · 」로 이은 값)]}]."""
    return {'kind': 'cards', 'title': title, 'items': items, 'note': note, 'wide': wide}


def bars(title, heads, items, note=''):
    """개수 막대 두 줄 견주기. heads = (왼쪽 이름, 오른쪽 이름), items = [(항목, 왼쪽 수, 오른쪽 수)]."""
    return {'kind': 'bars', 'title': title, 'heads': list(heads), 'items': [(str(k), a, b) for k, a, b in items], 'note': note}


def pair(title, left, right, note=''):
    """두 그림을 나란히."""
    return {'kind': 'pair', 'title': title, 'items': [left, right], 'note': note}


def link(text, url, note=''):
    return {'kind': 'link', 'text': text, 'url': url, 'note': note}


def folded(block):
    """근거 표를 접어 둔다(눌러서 편다)."""
    block['fold'] = True
    return block


def graph_node(n, mark='', badge=''):
    """graph.json 꼴의 노드({'labels', 'props'})를 그림의 노드로 — 글은 식별자, 아래 작은 글은 이름(없으면 태그)."""
    p = n['props']
    sub = p.get('name') or p.get('tag') or ''
    return node(p.get('id'), n['labels'][0], sub='' if sub == p.get('id') else str(sub), props=p, mark=mark, badge=badge)


def class_map(title, data, note=''):
    """graph.json 꼴의 그래프를 종류마다 한 노드(개수 배지)와 종류 사이의 관계(이름 · 개수)로 줄인 그림."""
    label = {n['props'].get('id'): n['labels'][0] for n in data['nodes']}
    count, links = {}, {}
    for n in data['nodes']:
        count[n['labels'][0]] = count.get(n['labels'][0], 0) + 1
    for r in data['rels']:
        if r['a'] in label and r['b'] in label:
            key = (label[r['a']], r['type'], label[r['b']])
            links[key] = links.get(key, 0) + 1
    return graph(title, [node(k, k, badge=f'{v}개') for k, v in count.items()],
                 [edge(a, b, f'{t} {n}개') for (a, t, b), n in sorted(links.items())], note=note)


def count_bars(title, heads, left, right, note=''):
    """{'노드': n, '관계': n, '종류 …': n, '관계 …': n} 두 벌을 막대로 견준다."""
    keys = [k for k in ('노드', '관계') if k in left or k in right] + sorted(k for k in set(left) | set(right) if k not in ('노드', '관계'))
    return bars(title, heads, [(k, left.get(k, 0), right.get(k, 0)) for k in keys], note=note)


def path_figure(title, data, asked, cells, note=''):
    """물은 값에서 쿼리 결과에 나온 대상까지, 그래프의 관계를 따라 가장 짧게 이어지는 길을 그린다.
    data = graph.json 꼴의 그래프, asked = 물은 값, cells = 쿼리 결과의 칸 값들. 물은 값과 같은 식별자(또는 그 값을 속성에 가진) 노드가 없으면 None."""
    nodes = {n['props'].get('id'): n for n in data['nodes']}
    near = {}
    for r in data['rels']:
        near.setdefault(r['a'], []).append((r['b'], r))
        near.setdefault(r['b'], []).append((r['a'], r))
    holds = lambda n, value: any(v == value or (isinstance(v, list) and value in v) for v in n['props'].values())
    start = [i for i in nodes if i == asked] or [i for i, n in nodes.items() if holds(n, asked)]
    if not start:
        return None
    back, depth, queue = {s: None for s in start}, {s: 0 for s in start}, list(start)
    while queue:
        cur = queue.pop(0)
        for other, r in near.get(cur, []):
            if other not in back and other in nodes:
                back[other], depth[other] = (cur, r), depth[cur] + 1
                queue.append(other)
    values = {v for v in cells if isinstance(v, str) and len(v) > 1}
    hits = {i for i in back if i in values and i not in start}
    if not hits:      # 결과에 식별자가 없으면, 물은 값 둘레(세 걸음 안)에서 결과의 값을 속성으로 가진 노드
        hits = {i for i in back if 0 < depth[i] <= 3 and any(holds(nodes[i], v) for v in values)}
    used, on_path = set(start), []
    for i in hits:
        while back.get(i):
            cur, r = back[i]
            on_path.append((r['type'], r['a'], r['b']))
            used.add(i)
            i = cur
    on_path += [(r['type'], r['a'], r['b']) for r in data['rels'] if r['a'] in used and r['b'] in used]
    on_path = list(dict.fromkeys(on_path))
    out = [graph_node(nodes[i], mark='ask' if i in start else '') for i in nodes if i in used]
    links = [edge(a, b, t, 'hit') for t, a, b in on_path]
    around = {}
    for s in start:
        for other, r in near.get(s, []):
            if other not in used and other in nodes:
                around.setdefault(other, r)
    for other, r in list(around.items())[:8]:
        out.append(graph_node(nodes[other], mark='dim'))
        links.append(edge(r['a'], r['b'], r['type'], 'dim'))
    more = f' 둘레의 다른 대상은 {len(around)}개 가운데 8개만 흐리게 그렸습니다.' if len(around) > 8 else ''
    return graph(title, out, links, note=note + more)


def graph_counts(data):
    """graph.json 꼴의 그래프 → {'노드': n, '관계': n, '종류 <레이블>': n, '관계 <유형>': n}."""
    out = {'노드': len(data['nodes']), '관계': len(data['rels'])}
    for n in data['nodes']:
        out['종류 ' + n['labels'][0]] = out.get('종류 ' + n['labels'][0], 0) + 1
    for r in data['rels']:
        out['관계 ' + r['type']] = out.get('관계 ' + r['type'], 0) + 1
    return out


def around_figure(title, data, root, far=14, note=''):
    """root에서 관계 방향으로 두 걸음까지의 노드와 관계. 둘째 걸음의 노드는 첫 걸음 노드마다 고르게 돌아가며 far개까지만 그린다."""
    nodes = {n['props'].get('id'): n for n in data['nodes']}
    one = [r for r in data['rels'] if r['a'] == root and r['b'] in nodes]
    first = list(dict.fromkeys(r['b'] for r in one))
    under = {f: [r for r in data['rels'] if r['a'] == f and r['b'] in nodes and r['b'] != root and r['b'] not in first] for f in first}
    total = len({r['b'] for rs in under.values() for r in rs})
    two, second, turn = [], [], 0
    while len(second) < far and any(len(rs) > turn for rs in under.values()):
        for rs in under.values():
            if len(rs) > turn and len(second) < far:
                two.append(rs[turn])
                if rs[turn]['b'] not in second:
                    second.append(rs[turn]['b'])
        turn += 1
    more = f'두 걸음째 대상은 {total}개 가운데 {len(second)}개만 그렸습니다.' if total > len(second) else ''
    return graph(title, [graph_node(nodes[i]) for i in [root] + first + second],
                 [edge(r['a'], r['b'], r['type']) for r in one + two], note=(note + ' ' + more).strip())
