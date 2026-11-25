

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


def raw(title, text):
    """그림과 같은 내용을 담은 원문 글(터미널 출력 같은 것) — 접어 두고 눌러서 편다."""
    return {'kind': 'note', 'text': text, 'fold': title}


def ordered(block):
    """값의 차례까지 견주는 대조 표 — 화면이 조각을 다시 늘어놓지 않고 적힌 차례 그대로 보인다."""
    block['ordered'] = True
    return block


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


def walk_figure(title, walk, asked, note=''):
    """쿼리의 패턴이 랩 DB에서 실제로 지난 노드와 관계(cypher.walked가 돌려준 것)를 그린다. 지난 노드가 하나도 없으면 None.
    결과 값으로 길을 짐작하지 않는다 — 그림의 선은 모두 DB가 그 패턴으로 맞춘 관계다."""
    if not walk['nodes']:
        return None
    holds = lambda n: any(v == asked or (isinstance(v, list) and asked in v) for v in n['props'].values())
    more = []
    if walk['lost']:
        more.append(f'WITH 뒤로 넘어가지 않은 패턴 {walk["lost"]}개는 그리지 못했습니다.')
    if walk['cut']:
        more.append('LIMIT · SKIP으로 줄이기 전에 지난 길을 모두 그렸습니다.')
    return graph(title, [graph_node(n, mark='ask' if holds(n) else '') for n in walk['nodes']],
                 [edge(a, b, t, 'hit') for t, a, b in walk['rels']], note=' '.join([note] + more).strip())

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
