from pathlib import Path
import json, re, urllib.request, urllib.error
from app.utils import db as local_db
HERE = Path(__file__).resolve().parents[2]
STATE = HERE / '.lab_connection.json'
_ENDPOINT = None

WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)


PARAM = re.compile(r'\$(\w+)')


TARGET = re.compile(r'^\s*//\s*넣을 것:\s*(\S+)\s*$')


QUESTION = re.compile(r'^\s*//\s*질문\s*(\S+)')


class LabDbOff(RuntimeError):
    """랩 DB에 닿지 못함 — 결과 화면이 「랩 DB 꺼짐」으로 알린다."""


def model_graph():
    """적재할 graph.json — app/features/model/graph.json이 있으면 그것, 없으면 data/model/graph.json."""
    mine = HERE / 'app/features/model/graph.json'
    if mine.exists() and not mine.with_name('schema.json').is_file():
        raise RuntimeError('app/features/model에는 schema.json과 graph.json을 함께 둡니다.')
    path = mine if mine.is_file() else HERE / 'data/model/graph.json'
    return path, json.loads(path.read_text(encoding='utf-8-sig'))


def endpoint():
    global _ENDPOINT
    if _ENDPOINT:
        return _ENDPOINT
    if not STATE.is_file():
        raise LabDbOff('랩 DB 연결이 없습니다. python run.py db로 준비합니다.')
    state = json.loads(STATE.read_text(encoding='utf-8'))
    info = json.loads(local_db.docker('inspect', state['container']))[0]
    if info['Config']['Labels'].get('hyd.practice.id') != state['id']:
        raise RuntimeError('이 폴더의 랩 DB가 아닙니다.')
    if not info['State']['Running']:
        raise LabDbOff('랩 DB가 꺼져 있습니다. python run.py db로 다시 켭니다.')
    mapping = info['NetworkSettings']['Ports']['7474/tcp'][0]
    if mapping['HostIp'] != '127.0.0.1':
        raise RuntimeError('이 폴더 전용 로컬 DB의 포트가 아닙니다.')
    _ENDPOINT = 'http://127.0.0.1:' + mapping['HostPort'] + '/db/neo4j/tx/commit'
    return _ENDPOINT


def cypher(statements):
    body = json.dumps({'statements': [{'statement': s, 'parameters': p, 'includeStats': True} for s, p in statements]}).encode()
    req = urllib.request.Request(endpoint(), body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LabDbOff(f'랩 DB 꺼짐 — 연결하지 못했습니다({e}). python run.py db 로 DB를 다시 준비하세요.')
    if data.get('errors'):
        raise RuntimeError('; '.join(e.get('message', '') for e in data['errors']))
    return data['results']


def rows_of(result):
    return result['columns'], [r['row'] for r in result['data']]


def statements(text):
    """[(첫 줄 번호, 문장, 앞 주석 줄들)]. 문장은 줄 끝 ; 로 나뉘고, 문장 앞 주석(// …)은 그 문장의 머리로 함께 돌려준다."""
    parts, buf, notes, start = [], [], [], None
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith('//') and not buf:
            notes.append(line)
            continue
        if not buf and not line.strip():
            continue
        if start is None:
            start = n
        buf.append(line)
        if line.rstrip().endswith(';'):
            parts.append((start, '\n'.join(buf).rstrip().rstrip(';'), notes))
            buf, notes, start = [], [], None
    if '\n'.join(buf).strip():
        parts.append((start, '\n'.join(buf), notes))
    return parts


def guard(path, parts):
    if not parts:
        raise RuntimeError(f'{path}: 실행할 문장이 없습니다. 현재 기능의 문장을 작성한 뒤 실행합니다.')
    for line, s, _ in parts:
        if WIPE.search(s):
            raise RuntimeError(f'{path}:{line}: 전체를 지우는 문장은 이 랩에서 실행하지 않습니다. 필요한 대상만 고치세요.')


def read(path):
    p = Path(path)
    if not p.is_file():
        raise RuntimeError(f'{path}: 파일이 없습니다.')
    return p.read_text(encoding='utf-8-sig')


def run_file(path):
    """$ 자리 없는 문장들을 차례로 실행한다. [(줄, 결과)]."""
    parts = statements(read(path))
    guard(path, parts)
    for line, s, _ in parts:
        if PARAM.search(s):
            raise RuntimeError(f'{path}:{line}: $ 자리가 있는 문장입니다 — 조회 기능에서 {path} --param 이름=값 으로 실행합니다.')
    out = []
    for line, s, _ in parts:
        try:
            out.append((line, cypher([(s, {})])[0]))
        except LabDbOff:
            raise
        except RuntimeError as e:
            raise RuntimeError(f'{path}:{line}: 실행 실패 — {e}')
    return out


def load_file(path, graph=None):
    """적재 파일 실행. 문장마다 머리 주석 `// 넣을 것: <종류 또는 관계>`가 있어야 하고, 그 종류의 노드 props(또는 그 관계의 {a, b, props})를 $rows로 넘긴다.
    [(줄, 대상, 넘긴 행 수, 결과)]."""
    if graph is None:
        _, graph = model_graph()
    nodes, rels = {}, {}
    for n in graph['nodes']:
        nodes.setdefault(n['labels'][0], []).append(n['props'])
    for r in graph['rels']:
        rels.setdefault(r['type'], []).append({'a': r['a'], 'b': r['b'], 'props': r.get('props', {})})
    parts = statements(read(path))
    guard(path, parts)
    plan = []
    for line, s, notes in parts:
        heads = [m.group(1) for m in (TARGET.match(x) for x in notes) if m]
        if len(heads) != 1:
            raise RuntimeError(f'{path}:{line}: 문장 바로 위에 `// 넣을 것: <종류 또는 관계>` 주석이 한 줄 있어야 합니다(있는 종류: {", ".join(sorted(nodes))} / 관계: {", ".join(sorted(rels))}).')
        target = heads[0]
        if target not in nodes and target not in rels:
            raise RuntimeError(f'{path}:{line}: 「{target}」는 graph.json에 없는 종류 · 관계입니다.')
        if '$rows' not in s:
            raise RuntimeError(f'{path}:{line}: 행은 $rows로 받습니다(UNWIND $rows AS row …).')
        plan.append((line, target, s, nodes.get(target) or rels.get(target)))
    out = []
    for line, target, s, rows in plan:
        try:
            out.append((line, target, len(rows), cypher([(s, {'rows': rows})])[0]))
        except LabDbOff:
            raise
        except RuntimeError as e:
            raise RuntimeError(f'{path}:{line}: 실행 실패 — {e}')
    return out


def questions(path):
    """조회 파일 → {번호: (줄, 문장)}. 문장 앞 주석 `// 질문 <번호>`로 질문마다 나눈다."""
    out = {}
    for line, s, notes in statements(read(path)):
        nums = [m.group(1) for m in (QUESTION.match(x) for x in notes) if m]
        if not nums:
            raise RuntimeError(f'{path}:{line}: 조회 위에 `// 질문 <번호>` 주석이 없습니다.')
        out[nums[-1]] = (line, s)
        for k, body_line in enumerate(s.splitlines()):
            m = QUESTION.match(body_line)
            if m and k:
                raise RuntimeError(f'{path}:{line + k}: 「// 질문 {m.group(1)}」가 질문 {nums[-1]} 조회 문장 안에 있습니다 — 질문 {nums[-1]} 조회({line}행부터) 끝에 ;가 없습니다.')
    return out


def query(path, number=None, params=None):
    """`// 질문 <번호>` 조회 하나(또는 전부)를 실행. [(번호, 줄, 열, 행)]. 문장의 $ 자리 가운데 params에 없는 것이 있으면 멈춘다."""
    qs = questions(path)
    if number is not None and str(number) not in qs:
        raise RuntimeError(f'{path}: 「// 질문 {number}」 조회가 없습니다(있는 번호: {", ".join(qs)}).')
    params = dict(params or {})
    out = []
    for num, (line, s) in qs.items():
        if number is not None and num != str(number):
            continue
        guard(path, [(line, s, [])])
        need = sorted(set(PARAM.findall(s)))
        missing = [k for k in need if k not in params]
        if missing:
            raise RuntimeError(f'{path}:{line}: 질문 {num}의 $ 자리 {", ".join(missing)}에 넣을 값이 없습니다(--param {missing[0]}=값).')
        try:
            cols, rows = rows_of(cypher([(s, {k: params[k] for k in need})])[0])
        except LabDbOff:
            raise
        except RuntimeError as e:
            raise RuntimeError(f'{path}:{line}: 질문 {num} 실행 실패 — {e}')
        out.append((num, line, cols, rows))
    return out


def counts():
    """{'노드': n, '관계': n, '종류 <레이블>': n, '관계 <유형>': n}."""
    res = cypher([('MATCH (n) RETURN count(n) AS nodes', {}), ('MATCH ()-[r]->() RETURN count(r) AS rels', {}),
                  ('MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY label', {}),
                  ('MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY t', {})])
    out = {'노드': res[0]['data'][0]['row'][0], '관계': res[1]['data'][0]['row'][0]}
    out.update({f'종류 {r["row"][0]}': r['row'][1] for r in res[2]['data']})
    out.update({f'관계 {r["row"][0]}': r['row'][1] for r in res[3]['data']})
    return out


def export_graph():
    res = cypher([('MATCH (n) RETURN labels(n) AS labels, properties(n) AS props', {}),
                  ('MATCH (a)-[r]->(b) RETURN type(r) AS type, a.id AS a, b.id AS b, properties(r) AS props', {})])
    nodes = sorted(({'labels': sorted(r['row'][0]), 'props': r['row'][1]} for r in res[0]['data']), key=lambda n: (n['labels'], str(n['props'].get('id'))))
    rels = sorted(({'type': r['row'][0], 'a': r['row'][1], 'b': r['row'][2], 'props': r['row'][3]} for r in res[1]['data']),
                  key=lambda r: (r['type'], str(r['a']), str(r['b']), json.dumps(r['props'], ensure_ascii=False, sort_keys=True)))
    return {'nodes': nodes, 'rels': rels}


def keyed(graph):
    """내보내기 → ({노드 id: (레이블, props)}, {(유형, a, b, 관계 id): props}). id 없는 노드는 멈춘다."""
    nodes, rels = {}, {}
    for n in graph['nodes']:
        if 'id' not in n['props']:
            raise RuntimeError(f'id 속성이 없는 노드가 있습니다: {n["labels"]} {n["props"]}')
        nodes[n['props']['id']] = (tuple(n['labels']), n['props'])
    for r in graph['rels']:
        key = (r['type'], r['a'], r['b'], r.get('props', {}).get('id'))
        rels.setdefault(key, []).append(r.get('props', {}))
    return nodes, rels


def diff_graphs(before, after):
    """{'늘어난 노드': [...], '사라진 노드': [...], '속성 바뀐 노드': [(id, 속성, 전, 후)], '늘어난 관계': [...], '사라진 관계': [...]}."""
    bn, br = keyed(before)
    an, ar = keyed(after)
    changed = []
    for i in sorted(set(bn) & set(an), key=str):
        p, q = bn[i][1], an[i][1]
        for k in sorted(set(p) | set(q)):
            if p.get(k) != q.get(k):
                changed.append((i, k, p.get(k), q.get(k)))
    fmt = lambda k: f'{k[1]} -{k[0]}-> {k[2]}' + (f' ({k[3]})' if k[3] is not None else '')
    grew = [fmt(k) for k in sorted(set(ar) - set(br), key=str)] + [fmt(k) + ' (하나 더)' for k in sorted(set(ar) & set(br), key=str) if len(ar[k]) > len(br[k])]
    gone = [fmt(k) for k in sorted(set(br) - set(ar), key=str)] + [fmt(k) + ' (하나 줄어듦)' for k in sorted(set(ar) & set(br), key=str) if len(ar[k]) < len(br[k])]
    rel_changed = []
    for k in sorted(set(ar) & set(br), key=str):
        if len(ar[k]) == len(br[k]) == 1:
            p, q = br[k][0], ar[k][0]
            rel_changed += [(fmt(k), x, p.get(x), q.get(x)) for x in sorted(set(p) | set(q)) if p.get(x) != q.get(x)]
    return {'늘어난 노드': sorted(set(an) - set(bn), key=str), '사라진 노드': sorted(set(bn) - set(an), key=str), '속성 바뀐 노드': changed,
            '늘어난 관계': grew, '사라진 관계': gone, '속성 바뀐 관계': rel_changed}
