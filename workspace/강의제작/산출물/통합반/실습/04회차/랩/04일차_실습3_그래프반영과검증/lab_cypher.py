"""이 폴더 전용 랩 DB(lab_db.py가 켠 컨테이너)에 Cypher를 실행하는 도구. 포털 DB에 접속하지 않는다.
사용:
  python lab_cypher.py model                       설비 모델과 조치 기준(SOP 구조 · 조건표) 적재(입출력_계약.md 2절)
  python lab_cypher.py run 결과/<파일>.cypher        파일의 문장을 차례로 실행(문장은 줄 끝 ; 로 구분, 전체를 지우는 문장은 실행하지 않음)
  python lab_cypher.py count                       전체 · 종류별 노드 수와 관계별 수
  python lab_cypher.py export 결과/지식_내보내기.json  그래프를 설비 모델 graph.json과 같은 꼴로 내보냄(결과/남은_질문.json이 있으면 함께)
결과/내_입력/에 입력/과 같은 이름의 파일이 있으면 model은 그 파일을 쓴다.
"""
from pathlib import Path
import csv, io, json, re, sys, urllib.request, urllib.error

HERE = Path(__file__).resolve().parent
STATE = HERE / '랩_연결.json'
WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)


def source(rel):
    mine = HERE / '결과/내_입력' / rel
    return mine if mine.is_file() else HERE / '입력' / rel


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
    parts, buf = [], []
    for line in text.splitlines():
        if line.strip().startswith('//') and not buf:
            continue
        buf.append(line)
        if line.rstrip().endswith(';'):
            parts.append('\n'.join(buf).rstrip().rstrip(';'))
            buf = []
    if '\n'.join(buf).strip():
        parts.append('\n'.join(buf))
    return parts


def run(path):
    parts = statements(Path(path).read_text(encoding='utf-8-sig'))
    for i, s in enumerate(parts, 1):
        if WIPE.search(s):
            raise RuntimeError(f'{i}번째 문장: 전체를 지우는 문장은 이 랩에서 실행하지 않습니다. 필요한 대상만 고치세요.')
    for i, s in enumerate(parts, 1):
        print(f'-- {i}/{len(parts)}')
        try:
            show(cypher([(s, {})])[0])
        except RuntimeError as e:
            raise RuntimeError(f'{path} {i}번째 문장 실패: {e}')


def count():
    res = cypher([('MATCH (n) RETURN count(n) AS nodes', {}), ('MATCH ()-[r]->() RETURN count(r) AS rels', {}),
                  ('MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY label', {}),
                  ('MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY t', {})])
    print(f'전체 노드 {res[0]["data"][0]["row"][0]}개, 관계 {res[1]["data"][0]["row"][0]}개')
    print('종류별:', ', '.join(f'{r["row"][0]} {r["row"][1]}' for r in res[2]['data']))
    print('관계별:', ', '.join(f'{r["row"][0]} {r["row"][1]}' for r in res[3]['data']))


def export(path):
    res = cypher([('MATCH (n) RETURN labels(n) AS labels, properties(n) AS props', {}),
                  ('MATCH (a)-[r]->(b) RETURN type(r) AS type, a.id AS a, b.id AS b, properties(r) AS props', {})])
    nodes = sorted(({'labels': sorted(r['row'][0]), 'props': r['row'][1]} for r in res[0]['data']), key=lambda n: (n['labels'], str(n['props'].get('id'))))
    rels = sorted(({'type': r['row'][0], 'a': r['row'][1], 'b': r['row'][2], 'props': r['row'][3]} for r in res[1]['data']), key=lambda r: (r['type'], str(r['a']), str(r['b'])))
    questions = HERE / '결과/남은_질문.json'
    out = {'nodes': nodes, 'rels': rels, 'remaining_questions': json.loads(questions.read_text(encoding='utf-8')) if questions.is_file() else []}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{path}: 노드 {len(nodes)}개 · 관계 {len(rels)}개 · 남은 질문 {len(out["remaining_questions"])}개를 내보냈습니다.')


if __name__ == '__main__':
    try:
        if sys.argv[1:2] == ['model']:
            model()
        elif sys.argv[1:2] == ['run'] and len(sys.argv) == 3:
            run(sys.argv[2])
        elif sys.argv[1:2] == ['count']:
            count()
        elif sys.argv[1:2] == ['export'] and len(sys.argv) == 3:
            export(sys.argv[2])
        else:
            print(__doc__)
            sys.exit(2)
    except (OSError, ValueError, KeyError, RuntimeError) as e:
        print('실행 확인 필요: ' + str(e))
        sys.exit(1)
