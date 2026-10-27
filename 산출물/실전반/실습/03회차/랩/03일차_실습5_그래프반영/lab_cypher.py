"""이 폴더 전용 랩 DB(lab_db.py가 만든 컨테이너)에 Cypher를 실행하는 도구. 포털 DB에 접속하지 않는다.
사용:
  python lab_cypher.py model              입력/모델/graph.json(앞 단계 완성 모델)을 적재
  python lab_cypher.py run 결과/load.cypher  파일의 문장을 차례로 실행(문장은 줄 끝 ; 로 구분)
  python lab_cypher.py count              전체·종류별 노드 수와 관계 수
"""
from pathlib import Path
import json, re, sys, urllib.request, urllib.error

HERE = Path(__file__).resolve().parent
STATE = HERE / '랩_연결.json'
WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)


def endpoint():
    if not STATE.is_file():
        raise RuntimeError('랩_연결.json이 없습니다. 먼저 python lab_db.py 를 실행하세요.')
    return json.loads(STATE.read_text(encoding='utf-8'))['http'] + '/db/neo4j/tx/commit'


def cypher(statements):
    body = json.dumps({'statements': [{'statement': s, 'parameters': p, 'includeStats': True} for s, p in statements]}).encode()
    req = urllib.request.Request(endpoint(), body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f'랩 DB에 연결하지 못했습니다({e}). python lab_db.py 로 DB를 다시 준비하세요.')
    if data.get('errors'):
        raise RuntimeError('; '.join(e.get('message', '') for e in data['errors']))
    return data['results']


def show(result):
    cols = result['columns']
    rows = [r['row'] for r in result['data']]
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


def model():
    graph = json.loads((HERE / '입력/모델/graph.json').read_text(encoding='utf-8'))
    by_label = {}
    for n in graph['nodes']:
        by_label.setdefault(n['labels'][0], []).append(n['props'])
    stmts = [(f'UNWIND $rows AS p MERGE (n:`{label}` {{id:p.id}}) SET n += p', {'rows': rows}) for label, rows in by_label.items()]
    by_type = {}
    for r in graph['rels']:
        by_type.setdefault(r['type'], []).append({'a': r['a'], 'b': r['b'], 'props': r['props']})
    stmts += [(f'UNWIND $rows AS r MATCH (a {{id:r.a}}), (b {{id:r.b}}) MERGE (a)-[x:`{t}`]->(b) SET x += r.props', {'rows': rows}) for t, rows in by_type.items()]
    cypher(stmts)
    print(f'앞 단계 모델 적재: 노드 {len(graph["nodes"])}개·관계 {len(graph["rels"])}개 입력(MERGE, 다시 실행해도 늘지 않음)')
    count()


def run(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    parts, buf = [], []
    for line in text.splitlines():
        if line.strip().startswith('//') and not buf:
            continue
        buf.append(line)
        if line.rstrip().endswith(';'):
            parts.append('\n'.join(buf).rstrip().rstrip(';')); buf = []
    if '\n'.join(buf).strip():
        parts.append('\n'.join(buf))
    for i, s in enumerate(parts, 1):
        if WIPE.search(s):
            raise RuntimeError(f'{i}번째 문장: 전체 삭제문은 이 랩에서 실행하지 않습니다. 필요한 대상만 고치세요.')
        print(f'-- {i}/{len(parts)}')
        try:
            show(cypher([(s, {})])[0])
        except RuntimeError as e:
            raise RuntimeError(f'{path} {i}번째 문장 실패: {e}')


def count():
    res = cypher([('MATCH (n) RETURN count(n) AS nodes', {}), ('MATCH ()-[r]->() RETURN count(r) AS rels', {}),
                  ('MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY label', {})])
    print(f'전체 노드 {res[0]["data"][0]["row"][0]}개, 관계 {res[1]["data"][0]["row"][0]}개')
    print('종류별:', ', '.join(f'{r["row"][0]} {r["row"][1]}' for r in res[2]['data']))


if __name__ == '__main__':
    try:
        if sys.argv[1:2] == ['model']:
            model()
        elif sys.argv[1:2] == ['run'] and len(sys.argv) == 3:
            run(sys.argv[2])
        elif sys.argv[1:2] == ['count']:
            count()
        else:
            print(__doc__); sys.exit(2)
    except (OSError, ValueError, KeyError, RuntimeError) as e:
        print('실행 확인 필요: ' + str(e)); sys.exit(1)
