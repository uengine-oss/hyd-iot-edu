"""이 폴더 전용 랩 DB(lab_db.py가 켠 컨테이너)에 Cypher를 실행하는 도구. 포털 DB에 접속하지 않는다.
사용:
  python lab_cypher.py model                         설비 모델과 조치 기준(SOP 구조 · 조건표) 적재(입출력_계약.md 2절 — 그 파일이 있는 실습만)
  python lab_cypher.py load 결과/<적재 파일>.cypher    적재 파일의 문장마다 머리 주석 `// 넣을 것: <종류 또는 관계>`의 행을 $rows로 넘겨 실행
                                                    (행은 입력/graph.json — 결과/내_모델/graph.json이 있으면 그것)
  python lab_cypher.py run 결과/<파일>.cypher          파일의 문장을 차례로 실행(문장은 줄 끝 ; 로 구분). $ 자리가 있는 문장은 query로
  python lab_cypher.py query 결과/<파일>.cypher [<번호>] [--param 이름=값 …]
                                                    `// 질문 <번호>` 아래 조회 하나(번호 없으면 전부)를 $ 자리에 값을 넣어 실행
                                                    (값은 글 하나 — 여럿을 넘길 때는 쿼리가 빈칸으로 나눠 쓴다: --param "이름=값1 값2")
  python lab_cypher.py count                         전체 · 종류별 노드 수와 관계별 수
  python lab_cypher.py export 결과/<파일>.json         그래프를 graph.json과 같은 꼴로 내보냄(결과/남은_질문.json이 있으면 함께)
  python lab_cypher.py diff 결과/<전>.json 결과/<후>.json  두 내보내기를 견줘 늘어남 · 사라짐 · 속성 바뀜을 보임
전체를 지우는 문장(MATCH (n) DETACH DELETE 꼴)은 실행하지 않는다. 결과/내_입력/에 입력/과 같은 이름의 파일이 있으면 model은 그 파일을 쓴다.
"""
from pathlib import Path
import csv, io, json, re, sys, urllib.request, urllib.error

HERE = Path(__file__).resolve().parent
STATE = HERE / '랩_연결.json'
WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)
PARAM = re.compile(r'\$(\w+)')
TARGET = re.compile(r'^\s*//\s*넣을 것:\s*(\S+)\s*$')
QUESTION = re.compile(r'^\s*//\s*질문\s*(\S+)')


class LabDbOff(RuntimeError):
    """랩 DB에 닿지 못함 — 결과 화면이 「랩 DB 꺼짐」으로 알린다."""


def source(rel):
    mine = HERE / '결과/내_입력' / rel
    return mine if mine.is_file() else HERE / '입력' / rel


def model_graph():
    """적재할 graph.json — 결과/내_모델/graph.json이 있으면 그것, 없으면 입력/graph.json."""
    mine = HERE / '결과/내_모델/graph.json'
    path = mine if mine.is_file() else HERE / '입력/graph.json'
    return path, json.loads(path.read_text(encoding='utf-8-sig'))


def endpoint():
    if not STATE.is_file():
        raise LabDbOff('랩 DB 꺼짐 — 랩_연결.json이 없습니다. 먼저 python lab_db.py 를 실행하세요.')
    return json.loads(STATE.read_text(encoding='utf-8'))['http'] + '/db/neo4j/tx/commit'


def cypher(statements):
    body = json.dumps({'statements': [{'statement': s, 'parameters': p, 'includeStats': True} for s, p in statements]}).encode()
    req = urllib.request.Request(endpoint(), body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LabDbOff(f'랩 DB 꺼짐 — 연결하지 못했습니다({e}). python lab_db.py 로 DB를 다시 준비하세요.')
    if data.get('errors'):
        raise RuntimeError('; '.join(e.get('message', '') for e in data['errors']))
    return data['results']


def rows_of(result):
    return result['columns'], [r['row'] for r in result['data']]


def show(result):
    cols, rows = rows_of(result)
    if cols:
        print(' | '.join(cols))
        for row in rows[:50]:
            print(' | '.join(json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v for v in row))
        if len(rows) > 50:
            print(f'… 외 {len(rows) - 50}행')
        print(f'({len(rows)}행)')
    stats = {k: v for k, v in result.get('stats', {}).items() if isinstance(v, int) and v}
    if stats:
        print('변경:', stats)


def table_rows():
    lines = [x for x in source('조건표.csv').read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


def model():
    graph = json.loads(source('모델/graph.json').read_text(encoding='utf-8'))
    sop = json.loads(source('sop.json').read_text(encoding='utf-8'))
    stmts = []
    by_label = {}
    for n in graph['nodes']:
        by_label.setdefault(n['labels'][0], []).append(n['props'])
    stmts += [(f'UNWIND $rows AS p MERGE (n:`{label}` {{id:p.id}}) SET n += p', {'rows': rows}) for label, rows in by_label.items()]
    by_type = {}
    for r in graph['rels']:
        by_type.setdefault(r['type'], []).append({'a': r['a'], 'b': r['b'], 'props': r['props']})
    stmts += [(f'UNWIND $rows AS r MATCH (a {{id:r.a}}), (b {{id:r.b}}) MERGE (a)-[x:`{t}`]->(b) SET x += r.props', {'rows': rows}) for t, rows in by_type.items()]
    stmts.append(('UNWIND $rows AS p MERGE (n:FailureMode {id:p.id}) SET n += p', {'rows': sop['failure_modes']}))
    stmts.append(('UNWIND $rows AS p MERGE (n:Cause {id:p.id}) SET n += p', {'rows': sop['causes']}))
    skills, steps, acts, checks = [], [], [], []
    for s in sop['sops']:
        skills.append({'id': s['id'], 'name': s['name'], 'kind': s['kind'], 'codes': s['codes'], 'source': s['source'],
                       'apply_conditions': [x['text'] for x in s['apply_conditions']], 'prohibitions': [x['text'] for x in s['prohibitions']],
                       'completion': [x['text'] for x in s['completion']], 'approval_role': s['approval']['role'], 'approval_source': s['approval']['source']})
        steps += [{'skill': s['id'], 'props': {'id': f'{s["id"]}:{st["order"]}', 'order': st['order'], 'text': st['text'], 'source': st['source']}} for st in s['steps']]
        acts += [{'skill': s['id'], 'to': c} for c in s['model_refs'].get('components', [])]
        checks += [{'skill': s['id'], 'to': c} for c in s['model_refs'].get('sensors', [])]
    stmts.append(('UNWIND $rows AS p MERGE (n:Skill {id:p.id}) SET n += p', {'rows': [{k: v for k, v in x.items() if v is not None} for x in skills]}))
    stmts.append(('UNWIND $rows AS r MATCH (s:Skill {id:r.skill}) MERGE (t:Step {id:r.props.id}) SET t += r.props MERGE (s)-[:HAS_STEP]->(t)', {'rows': steps}))
    stmts.append(('UNWIND $rows AS r MATCH (s:Skill {id:r.skill}), (c {id:r.to}) MERGE (s)-[:ACTS_ON]->(c)', {'rows': acts}))
    stmts.append(('UNWIND $rows AS r MATCH (s:Skill {id:r.skill}), (c {id:r.to}) MERGE (s)-[:CHECKS]->(c)', {'rows': checks}))
    for t in sorted({r['type'] for r in sop['relations']}):
        rows = [{'a': r['from'], 'b': r['to'], 'source': r.get('source')} for r in sop['relations'] if r['type'] == t]
        stmts.append((f'UNWIND $rows AS r MATCH (a {{id:r.a}}), (b {{id:r.b}}) MERGE (a)-[x:`{t}`]->(b) SET x.source = r.source', {'rows': rows}))
    rules, outputs = {}, {}
    for r in table_rows():
        rule = rules.setdefault(r['rule_id'], {'id': r['rule_id'], 'effect': r['result'], 'penalty_manwon': r['penalty_manwon'] or None, 'conditions': {}})
        rule['conditions'].setdefault(r['condition_index'], f'{r["input"]} {r["operator"]} {r["value"]} {r["unit"]}'.strip())
        outputs[(r['rule_id'], r['action'])] = {'rule': r['rule_id'], 'skill': r['action'], 'reason': r['reason'], 'source_section': r['source_section']}
    rows = [{'id': x['id'], 'effect': x['effect'], 'when': ' AND '.join(x['conditions'][k] for k in sorted(x['conditions'])),
             **({'penalty_manwon': float(x['penalty_manwon'])} if x['penalty_manwon'] else {})} for x in rules.values()]
    stmts.append(('UNWIND $rows AS p MERGE (n:Rule {id:p.id}) SET n += p', {'rows': rows}))
    stmts.append(('UNWIND $rows AS r MATCH (a:Rule {id:r.rule}), (b:Skill {id:r.skill}) MERGE (a)-[x:OUTPUTS]->(b) SET x.reason = r.reason, x.source_section = r.source_section',
                  {'rows': list(outputs.values())}))
    cypher(stmts)
    print(f'설비 모델과 조치 기준 적재: 설비 모델 노드 {len(graph["nodes"])}개 · 관계 {len(graph["rels"])}개, SOP {len(skills)}개 · 단계 {len(steps)}개, 규칙 {len(rows)}개 입력(다시 실행해도 늘지 않음)')
    count()


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
            raise RuntimeError(f'{path}:{line}: $ 자리가 있는 문장입니다 — python lab_cypher.py query {path} --param 이름=값 으로 실행합니다.')
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
    return out


def parse_params(pairs):
    params = {}
    for x in pairs:
        if '=' not in x:
            raise RuntimeError(f'--param 「{x}」: 이름=값 꼴이어야 합니다.')
        k, v = x.split('=', 1)
        params[k.strip()] = v.strip()
    return params


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


def count():
    c = counts()
    print(f'전체 노드 {c["노드"]}개, 관계 {c["관계"]}개')
    print('종류별:', ', '.join(f'{k[3:]} {v}' for k, v in c.items() if k.startswith('종류 ')))
    print('관계별:', ', '.join(f'{k[3:]} {v}' for k, v in c.items() if k.startswith('관계 ')))


def export_graph():
    res = cypher([('MATCH (n) RETURN labels(n) AS labels, properties(n) AS props', {}),
                  ('MATCH (a)-[r]->(b) RETURN type(r) AS type, a.id AS a, b.id AS b, properties(r) AS props', {})])
    nodes = sorted(({'labels': sorted(r['row'][0]), 'props': r['row'][1]} for r in res[0]['data']), key=lambda n: (n['labels'], str(n['props'].get('id'))))
    rels = sorted(({'type': r['row'][0], 'a': r['row'][1], 'b': r['row'][2], 'props': r['row'][3]} for r in res[1]['data']),
                  key=lambda r: (r['type'], str(r['a']), str(r['b']), json.dumps(r['props'], ensure_ascii=False, sort_keys=True)))
    return {'nodes': nodes, 'rels': rels}


def export(path):
    out = export_graph()
    questions_file = HERE / '결과/남은_질문.json'
    out['remaining_questions'] = json.loads(questions_file.read_text(encoding='utf-8')) if questions_file.is_file() else []
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'{path}: 노드 {len(out["nodes"])}개 · 관계 {len(out["rels"])}개 · 남은 질문 {len(out["remaining_questions"])}개를 내보냈습니다.')


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


def diff(a, b):
    load = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
    d = diff_graphs(load(a), load(b))
    for k, v in d.items():
        print(f'{k}: {len(v)}개')
        for x in v[:30]:
            print('  ', x if not isinstance(x, tuple) else f'{x[0]} {x[1]}: {json.dumps(x[2], ensure_ascii=False)} → {json.dumps(x[3], ensure_ascii=False)}')
        if len(v) > 30:
            print(f'   … 외 {len(v) - 30}개')


def main(argv):
    cmd = argv[:1]
    if cmd == ['model']:
        model()
    elif cmd == ['load'] and len(argv) == 2:
        for line, target, n, res in load_file(argv[1]):
            print(f'-- {argv[1]}:{line} {target} 행 {n}개')
            show(res)
        count()
    elif cmd == ['run'] and len(argv) == 2:
        for line, res in run_file(argv[1]):
            print(f'-- {argv[1]}:{line}')
            show(res)
    elif cmd == ['query'] and len(argv) >= 2:
        rest = argv[2:]
        number = rest.pop(0) if rest and rest[0] != '--param' else None
        pairs = []
        while rest:
            if rest[0] != '--param' or len(rest) < 2:
                raise RuntimeError('query 꼴: python lab_cypher.py query <파일> [<번호>] [--param 이름=값 …]')
            pairs.append(rest[1])
            rest = rest[2:]
        for num, line, cols, rows in query(argv[1], number, parse_params(pairs)):
            print(f'-- 질문 {num} ({argv[1]}:{line})')
            show({'columns': cols, 'data': [{'row': r} for r in rows]})
    elif cmd == ['count']:
        count()
    elif cmd == ['export'] and len(argv) == 2:
        export(argv[1])
    elif cmd == ['diff'] and len(argv) == 3:
        diff(argv[1], argv[2])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (OSError, ValueError, KeyError, RuntimeError) as e:
        print('실행 확인 필요: ' + str(e))
        sys.exit(1)
