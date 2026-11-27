from pathlib import Path
import csv, io, json, re, urllib.request, urllib.error
from app.utils import db as local_db
HERE = Path(__file__).resolve().parents[2]
STATE = HERE / '.lab_connection.json'
_ENDPOINT = None

WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)


PARAM = re.compile(r'\$(\w+)')


TARGET = re.compile(r'^\s*//\s*넣을 것:\s*(\S+)\s*$')


QUESTION = re.compile(r'^\s*//\s*질문\s*(\S+)')


CONSTRAINT = re.compile(r'^\s*CREATE\s+CONSTRAINT\b', re.I)


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
        raise RuntimeError(f'{path}: 실행할 쿼리가 없습니다. 현재 기능의 쿼리를 작성한 뒤 실행합니다.')
    for line, s, _ in parts:
        if WIPE.search(s):
            raise RuntimeError(f'{path}:{line}: 전체를 지우는 쿼리는 이 랩에서 실행하지 않습니다. 필요한 대상만 고치세요.')


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
            raise RuntimeError(f'{path}:{line}: $ 자리가 있는 쿼리입니다 — 이 기능은 $ 자리 없는 쿼리만 실행합니다.')
    out = []
    for line, s, _ in parts:
        try:
            out.append((line, cypher([(s, {})])[0]))
        except LabDbOff:
            raise
        except RuntimeError as e:
            raise RuntimeError(f'{path}:{line}: 실행 실패 — {e}')
    return out


def constraints_file(path):
    """제약 쿼리 파일 실행. 쿼리는 모두 제약을 거는 쿼리(CREATE CONSTRAINT …)여야 한다. [(줄, 결과)]."""
    parts = statements(read(path))
    guard(path, parts)
    for line, s, _ in parts:
        if not CONSTRAINT.match(s):
            raise RuntimeError(f'{path}:{line}: 이 파일에는 제약을 거는 쿼리(CREATE CONSTRAINT …)만 둡니다. 데이터를 넣는 쿼리는 적재 쿼리 파일에 씁니다.')
    out = []
    for line, s, _ in parts:
        try:
            out.append((line, cypher([(s, {})])[0]))
        except LabDbOff:
            raise
        except RuntimeError as e:
            raise RuntimeError(f'{path}:{line}: 실행 실패 — {e}')
    return out


def constraints():
    """랩 DB에 걸려 있는 제약. [(이름, 종류, 대상, 레이블 또는 관계 유형 목록, 속성 목록)]."""
    return rows_of(cypher([('SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties '
                            'RETURN name, type, entityType, labelsOrTypes, properties ORDER BY name', {})])[0])[1]


def duplicates(labels, key='id'):
    """레이블마다 같은 식별자 값을 가진 노드가 둘 이상인 것. [(레이블, 값, 노드 수)]."""
    quoted = lambda x: '`' + x.replace('`', '``') + '`'
    res = cypher([(f'MATCH (n:{quoted(l)}) WITH n.{quoted(key)} AS v, count(*) AS c WHERE v IS NOT NULL AND c > 1 RETURN v, c ORDER BY toString(v)', {}) for l in labels])
    return [(l, r['row'][0], r['row'][1]) for l, x in zip(labels, res) for r in x['data']]


def try_create_twice(label, value, key='id'):
    """같은 식별자 값으로 노드를 두 번 만드는 것(CREATE)을 한 트랜잭션에서 시도하고, 받아 주든 거절하든 되돌려 랩 DB에 남기지 않는다.
    DB가 거절하면 DB의 답(글)을, 둘 다 받아 주면 None을 돌려준다."""
    quoted = lambda x: '`' + x.replace('`', '``') + '`'
    one = {'statement': f'CREATE (n:{quoted(label)} {{{quoted(key)}: $value}})', 'parameters': {'value': value}}
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    try:
        opened = urllib.request.Request(endpoint().removesuffix('/commit'), json.dumps({'statements': [one, one]}).encode(), headers)
        with urllib.request.urlopen(opened, timeout=60) as r:
            data = json.loads(r.read())
        if data.get('errors'):      # 오류가 난 트랜잭션은 DB가 되돌린다
            return '; '.join(e.get('message', '') for e in data['errors'])
        with urllib.request.urlopen(urllib.request.Request(data['commit'].removesuffix('/commit'), headers=headers, method='DELETE'), timeout=60) as r:
            if json.loads(r.read()).get('errors'):
                raise RuntimeError('유일 제약을 시험한 트랜잭션을 되돌리지 못했습니다.')
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LabDbOff(f'랩 DB 꺼짐 — 연결하지 못했습니다({e}). python run.py db 로 DB를 다시 준비하세요.')
    return None


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
            raise RuntimeError(f'{path}:{line}: 쿼리 바로 위에 `// 넣을 것: <종류 또는 관계>` 주석이 한 줄 있어야 합니다(있는 종류: {", ".join(sorted(nodes))} / 관계: {", ".join(sorted(rels))}).')
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


CHANGE = re.compile(r'^\s*//\s*반영할 것:\s*(\S+)\s+(\S+)\s*$')


def load_plan(path, graph=None):
    """적재 파일 → [(줄, 대상, 쿼리, 넘길 행)]. 쿼리마다 머리 주석 `// 넣을 것: <종류 또는 관계>`가 있어야 하고, 그 종류의 노드 props(또는 그 관계의 {a, b, props})를 $rows로 넘긴다."""
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
            raise RuntimeError(f'{path}:{line}: 쿼리 바로 위에 `// 넣을 것: <종류 또는 관계>` 주석이 한 줄 있어야 합니다(있는 종류: {", ".join(sorted(nodes))} / 관계: {", ".join(sorted(rels))}).')
        target = heads[0]
        if target not in nodes and target not in rels:
            raise RuntimeError(f'{path}:{line}: 「{target}」는 graph.json에 없는 종류 · 관계입니다.')
        if '$rows' not in s:
            raise RuntimeError(f'{path}:{line}: 행은 $rows로 받습니다(UNWIND $rows AS row …).')
        plan.append((line, target, s, nodes.get(target) or rels.get(target), target in nodes))
    return plan


def load_files(mine, provided):
    """제공 적재 쿼리(provided)와 내 적재 쿼리(mine)를 함께 실행한다 — 제공 쿼리의 노드 → 내 쿼리(적힌 차례) → 제공 쿼리의 관계. 관계는 양 끝 노드가 먼저 있어야 이어진다.
    돌려주는 것: ([(파일, 줄, 대상, 넘긴 행 수, 결과)], 어느 쿼리도 넣지 않은 종류 · 관계)."""
    _, graph = model_graph()
    own = load_plan(mine, graph)
    given = load_plan(provided, graph)
    order = [(provided, x) for x in given if x[4]] + [(mine, x) for x in own] + [(provided, x) for x in given if not x[4]]
    out = []
    for path, (line, target, s, rows, _) in order:
        try:
            out.append((path, line, target, len(rows), cypher([(s, {'rows': rows})])[0]))
        except LabDbOff:
            raise
        except RuntimeError as e:
            raise RuntimeError(f'{path}:{line}: 실행 실패 — {e}')
    every = {n['labels'][0] for n in graph['nodes']} | {r['type'] for r in graph['rels']}
    return out, sorted(every - {target for _, _, target, _, _ in out})


def seek_plan(statement, rows):
    """쿼리를 실행하지 않고 DB가 세운 실행 계획(EXPLAIN)에서 노드를 찾는 연산자 이름만 뽑는다 — 식별자로 바로 찾는지(…IndexSeek), 훑는지(…Scan)."""
    body = json.dumps({'statements': [{'statement': 'EXPLAIN ' + statement, 'parameters': {'rows': rows[:1]}}]}).encode()
    req = urllib.request.Request(endpoint(), body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LabDbOff(f'랩 DB 꺼짐 — 연결하지 못했습니다({e}). python run.py db 로 DB를 다시 준비하세요.')
    if data.get('errors'):
        raise RuntimeError('; '.join(e.get('message', '').split('\n')[0] for e in data['errors']))
    found = []

    def walk(node):
        name = str(node.get('operatorType', '')).split('@')[0]
        if 'Scan' in name or 'Seek' in name:
            found.append(name)
        for child in node.get('children', []):
            walk(child)
    plan = data['results'][0].get('plan') or {}
    walk(plan.get('root', plan))
    return found


def tried(queries):
    """쿼리들([(쿼리, 넣을 값)])을 한 트랜잭션에서 차례로 실행해 보고, 받아 주든 거절하든 모두 되돌려 랩 DB에 남기지 않는다.
    돌려주는 것: ([쿼리마다 {'stats', 'columns', 'rows'}] — 거절된 쿼리 앞까지, DB가 거절하며 한 말 또는 None)."""
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    body = json.dumps({'statements': [{'statement': s, 'parameters': p, 'includeStats': True} for s, p in queries]}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(endpoint().removesuffix('/commit'), body, headers), timeout=60) as r:
            data = json.loads(r.read())
        if not data.get('errors'):      # 오류가 난 트랜잭션은 DB가 되돌린다
            with urllib.request.urlopen(urllib.request.Request(data['commit'].removesuffix('/commit'), headers=headers, method='DELETE'), timeout=60) as r:
                if json.loads(r.read()).get('errors'):
                    raise RuntimeError('실험한 트랜잭션을 되돌리지 못했습니다.')
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LabDbOff(f'랩 DB 꺼짐 — 연결하지 못했습니다({e}). python run.py db 로 DB를 다시 준비하세요.')
    done = [{'stats': {k: v for k, v in x.get('stats', {}).items() if isinstance(v, int) and not isinstance(v, bool) and v},
             'columns': x['columns'], 'rows': [d['row'] for d in x['data']]} for x in data['results']]
    return done, ('; '.join(e.get('message', '').split('\n')[0] for e in data['errors']) or None) if data.get('errors') else None


def change_rows():
    """수정본 폴더의 표 → {(파일, 변경): [(편집기 줄, {열 이름: 값})]}. 열 이름과 값은 수정본에 적힌 글자 그대로다(숫자도 글자로 온다)."""
    out = {}
    for p in sorted((HERE / 'data/changes/').glob('*/*.csv')):
        text = p.read_text(encoding='utf-8-sig')
        for n, row in enumerate(csv.DictReader(io.StringIO(text)), 2):
            out.setdefault((p.name, (row.get('변경') or '').strip()), []).append((n, {k: (v or '').strip() for k, v in row.items()}))
    return out


def apply_changes(path):
    """수정 쿼리 파일 실행. 쿼리마다 머리 주석 `// 반영할 것: <수정본 파일 이름> <변경>`이 있어야 하고, 그 파일에서 「변경」 칸이 그 값인 줄을 $rows로 넘긴다.
    줄마다 따로 넘겨 DB가 그 줄로 바꾼 것을 받는다. 돌려주는 것: ([(쿼리 줄, 파일, 변경, [(수정본 줄, 행, 바뀐 수)])], 쿼리가 하나도 없는 (파일, 변경))."""
    rows = change_rows()
    have = ' / '.join(f'{name} {kind}' for name, kind in sorted(rows))
    parts = statements(read(path))
    guard(path, parts)
    plan = []
    for line, s, notes in parts:
        heads = [m.groups() for m in (CHANGE.match(x) for x in notes) if m]
        if len(heads) != 1:
            raise RuntimeError(f'{path}:{line}: 쿼리 바로 위에 `// 반영할 것: <수정본 파일 이름> <변경>` 주석이 한 줄 있어야 합니다(수정본에 있는 것: {have}).')
        if heads[0] not in rows:
            raise RuntimeError(f'{path}:{line}: 「{heads[0][0]} {heads[0][1]}」에 해당하는 수정본 줄이 없습니다(수정본에 있는 것: {have}).')
        if '$rows' not in s:
            raise RuntimeError(f'{path}:{line}: 수정본의 줄은 $rows로 받습니다(UNWIND $rows AS row …). 값을 쿼리에 직접 적지 않습니다.')
        plan.append((line, heads[0][0], heads[0][1], s))
    out = []
    for line, name, kind, s in plan:
        done = []
        for n, row in rows[(name, kind)]:
            try:
                stats = cypher([(s, {'rows': [row]})])[0].get('stats', {})
            except LabDbOff:
                raise
            except RuntimeError as e:
                raise RuntimeError(f'{path}:{line}: 실행 실패({name}:{n} 줄을 넘겼을 때) — {e}')
            done.append((n, row, {k: v for k, v in stats.items() if isinstance(v, int) and not isinstance(v, bool) and v}))
        out.append((line, name, kind, done))
    return out, sorted(k for k in rows if k not in {(name, kind) for _, name, kind, _ in out})


def questions(path):
    """조회 파일 → {번호: (줄, 문장)}. 문장 앞 주석 `// 질문 <번호>`로 질문마다 나눈다."""
    out = {}
    for line, s, notes in statements(read(path)):
        nums = [m.group(1) for m in (QUESTION.match(x) for x in notes) if m]
        if not nums:
            raise RuntimeError(f'{path}:{line}: 쿼리 위에 `// 질문 <번호>` 주석이 없습니다.')
        out[nums[-1]] = (line, s)
        for k, body_line in enumerate(s.splitlines()):
            m = QUESTION.match(body_line)
            if m and k:
                raise RuntimeError(f'{path}:{line + k}: 「// 질문 {m.group(1)}」가 질문 {nums[-1]} 쿼리 안에 있습니다 — 질문 {nums[-1]} 쿼리({line}행부터) 끝에 ;가 없습니다.')
    return out


CLAUSE = re.compile(r'\b(OPTIONAL\s+MATCH|MATCH|WHERE|WITH|RETURN|UNWIND|CALL|ORDER\s+BY|SKIP|LIMIT|UNION|CREATE|MERGE|SET|DELETE|DETACH|REMOVE|FOREACH|LOAD\s+CSV)\b', re.I)


WRITES = {'CREATE', 'MERGE', 'SET', 'DELETE', 'DETACH', 'REMOVE', 'FOREACH', 'LOAD CSV'}


def top_level(text):
    """쿼리 글과 같은 길이의 글 — 따옴표 · 주석 · 괄호((), [], {}) 안은 빈칸으로 바꿔, 맨 바깥에 적힌 절 이름과 쉼표만 남긴다."""
    out, depth, i, n = [], 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch in '\'"`':
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if text[j] == chr(92) else 1
            out.append(' ' * (min(j, n - 1) - i + 1))
            i = j + 1
        elif text.startswith('//', i):
            j = text.find('\n', i)
            j = n if j < 0 else j
            out.append(' ' * (j - i))
            i = j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(' ' * (j - i))
            i = j
        else:
            if ch in ')]}':
                depth = max(0, depth - 1)
            out.append(ch if depth == 0 and ch not in '([{' or ch == '\n' else ' ')
            if ch in '([{':
                depth += 1
            i += 1
    return ''.join(out)[:n]


def path_query(text):
    """조회 쿼리 → (같은 패턴을 그대로 두고 패턴마다 경로 이름을 붙여 RETURN *로 끝낸 쿼리, 붙인 경로 수, 뺀 꼬리에 LIMIT · SKIP이 있었는가).
    쿼리가 랩 DB에서 실제로 지난 노드와 관계를 받으려고 쓴다. 학생의 쿼리 파일은 바꾸지 않는다. 읽지 못하는 꼴이면 그 까닭을 말하며 멈춘다."""
    flat = top_level(text)
    marks = [(m.start(), m.end(), re.sub(r'\s+', ' ', m.group(1).upper())) for m in CLAUSE.finditer(flat)]
    wrote = sorted({k for _, _, k in marks if k in WRITES})
    if wrote:
        raise RuntimeError('데이터를 바꾸는 절(' + ' · '.join(wrote) + ')이 있는 쿼리라 길을 보려고 다시 실행하지 않았습니다.')
    if any(k == 'UNION' for _, _, k in marks):
        raise RuntimeError('UNION으로 이은 쿼리는 갈래마다 패턴이 달라 한 그림으로 읽지 못합니다.')
    ends = [i for i, m in enumerate(marks) if m[2] == 'RETURN']
    if not ends:
        raise RuntimeError('맨 바깥에 RETURN이 없어 어디까지가 패턴인지 읽지 못했습니다.')
    out, pos, named = [], 0, 0
    for i, (start, end, kind) in enumerate(marks[:ends[-1]]):
        if kind not in ('MATCH', 'OPTIONAL MATCH'):
            continue
        stop = marks[i + 1][0]
        cuts = [end] + [end + k for k, ch in enumerate(flat[end:stop]) if ch == ','] + [stop]
        pieces = []
        for a, b in zip(cuts, cuts[1:]):
            piece = text[a:b].lstrip(',')
            if re.match(r'\s*[A-Za-z_]\w*\s*=', flat[a:b].lstrip(',')):      # 이미 경로 이름이 있는 패턴
                pieces.append(piece)
            else:
                named += 1
                pieces.append(f' path_for_picture_{named} = ' + piece.strip() + ' ')
        out.append(text[pos:end] + ','.join(pieces))
        pos = stop
    if not out:
        raise RuntimeError('맨 바깥에 MATCH 패턴이 없어 따라간 길을 읽지 못했습니다.')
    tail = flat[marks[ends[-1]][0]:]
    return ''.join(out) + text[pos:marks[ends[-1]][0]] + 'RETURN *', named, bool(re.search(r'(?<![.\w])(LIMIT|SKIP)\s+[\d$]', tail, re.I))


def walked(path, number, params):
    """`// 질문 <번호>` 쿼리의 패턴이 랩 DB에서 실제로 지난 노드와 관계. {'nodes': [{'labels', 'props'}], 'rels': [(유형, 시작 id, 끝 id)], 'lost': 그리지 못한 패턴 수, 'cut': LIMIT · SKIP이 있었는가}.
    결과 열을 무엇으로 돌려주든(식별자 · 이름) 패턴이 같으면 같은 길이다. 읽지 못하면 까닭을 RuntimeError로 알린다."""
    line, text = questions(path)[str(number)]
    query, named, cut = path_query(text)
    need = sorted(set(PARAM.findall(query)))
    body = json.dumps({'statements': [{'statement': query, 'parameters': {k: params[k] for k in need if k in params}, 'resultDataContents': ['graph']}]}).encode()
    req = urllib.request.Request(endpoint(), body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LabDbOff(f'랩 DB 꺼짐 — 연결하지 못했습니다({e}). python run.py db 로 DB를 다시 준비하세요.')
    if data.get('errors'):
        raise RuntimeError('패턴에 경로 이름을 붙여 다시 실행하니 DB가 받지 않았습니다 — ' + '; '.join(e.get('message', '').split('\n')[0] for e in data['errors']))
    result = data['results'][0]
    nodes, rels, key = {}, [], {}
    for item in result['data']:
        for n in item['graph']['nodes']:
            key[n['id']] = n['properties'].get('id', n['id'])
            nodes[key[n['id']]] = {'labels': sorted(n['labels']), 'props': n['properties']}
    for item in result['data']:
        for r in item['graph']['relationships']:
            if r['startNode'] in key and r['endNode'] in key:
                rels.append((r['type'], key[r['startNode']], key[r['endNode']]))
    kept = sum(1 for c in result['columns'] if c.startswith('path_for_picture_'))
    return {'nodes': list(nodes.values()), 'rels': list(dict.fromkeys(rels)), 'lost': named - kept, 'cut': cut}


def query(path, number=None, params=None):
    """`// 질문 <번호>` 조회 하나(또는 전부)를 실행. [(번호, 줄, 열, 행)]. 문장의 $ 자리 가운데 params에 없는 것이 있으면 멈춘다."""
    qs = questions(path)
    if number is not None and str(number) not in qs:
        raise RuntimeError(f'{path}: 「// 질문 {number}」 쿼리가 없습니다(있는 번호: {", ".join(qs)}).')
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
