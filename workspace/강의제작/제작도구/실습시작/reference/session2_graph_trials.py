"""통합02 그래프 랩(실습 랩 규모)의 강사 참조 시험 — 실제 별도 랩 DB에서 적재 · 조회 · 수정본 갈래 · 재실행을 판정한다. AI 호출과 촬영을 하지 않는다.

판정: 제공 모델이 생성 정답 구조와 같다. 적재한 그래프가 모델 파일과 같고 다시 적재해도 같다. 조회 셋의 답이 기대 답(제공 모델과 원자료에서)과 같다.
수정본 갈래 남김 · 삭제마다 이름이 바뀐 설비가 같은 식별자로 남고, 불용 설비가 그 갈래대로 남거나 그 설비에만 딸린 대상과 함께 사라지며(남은 설비의 대상 수는 그대로),
한 번 더 반영해도 바뀌지 않는다. 두 갈래의 사용 설비 조회 답이 실제로 다르다. 빈 결정이면 수정본 반영이 그 줄을 짚고 멈춘다.
이 시험이 만든 랩 DB 컨테이너는 라벨을 다시 확인한 뒤 지운다.
사용: python reference/session2_graph_trials.py <graph-lab 폴더>
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_labs as B
import data_session2 as D
import session2_answers as A
import session2_project as P
import verify_reference as V
from lab_package import ROOT
from reference.session2_project_trials import command, put, student_condition_selftest


def fill(folder, change='남김'):
    graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
    schema = json.loads((folder / 'data/model/schema.json').read_text(encoding='utf-8'))
    put(folder, {A.CONSTRAINT_FILE: A.constraint_answer(schema), '결과/load.cypher': A.load_answer(graph, schema, only=A.STUDENT_LOAD),
                 '결과/update.cypher': A.update_integrated(change),
                 '결과/query.cypher': A.query_text([A.QUERY_INTEGRATED[n] for n in (1, 2, 3)]),
                 '결과/정한_것.csv': B.chosen_text(B.graph_chosen('통합반')[change])}, True)
    expectation(folder)


def expectation(folder, after=None):
    """기대 답 표. 질문 1에는 태그 줄에 더해 한계 줄(한계가 없는 센서는 「없음」)을 원자료 센서 목록에서 따로 센다.
    after = 수정본을 반영한 갈래(남김 · 삭제)면 불용 설비 · 목록에서 빠진 센서가 걸린 줄을 수정본 줄에서 다시 정하고(제공 모델이 아니라 D.changes에서), 새로 등록된 표기로 물은 줄을 더한다."""
    import csv, io
    graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
    rows = B.graph_expect_rows('통합반', graph)
    asked = B.GRAPH_ASK['sensors']
    raw = [r for r in csv.DictReader(io.StringIO((folder / 'data/sensors.csv').read_text(encoding='utf-8-sig'))) if r['설비코드'] == asked]
    code, tag, _ = D.LAB_SENSOR_REMOVED
    if after == '삭제' and code == asked:
        raw = [r for r in raw if r['태그'] != tag]
        tags = next(r for r in rows if r[0] == '1' and r[2] == 'tag')
        tags[3] = ' · '.join(sorted(r['태그'] for r in raw))
    rows.insert(1, ['1', asked, 'limit', ' · '.join(r['한계'] or '없음' for r in raw), '입력/자료/센서_목록.csv 한계 칸'])
    if after:
        retired, status = D.LAB_RETIRED
        where = B.retired_change_line()
        for row in rows:
            if row[0] != '3' or row[2] not in ('status', 'asset'):
                continue
            parts = V.code_to_parts(row[1])           # 물은 품번 · 표기가 가리키는 사내 품번 — 그 부품을 쓰는 설비는 정답 구조(TRUTH)에서 센다
            assets = sorted(a for a, t in D.TRUTH['assets'].items() if set(parts) & set(t['components'].values()))
            if retired not in assets:
                continue                               # 불용 결정 설비가 쓰지 않는 부품의 줄은 수정본으로 바뀌지 않는다
            kept = [a for a in assets if not (after == '삭제' and a == retired)]
            row[3] = (' · '.join((status if a == retired else '가동') for a in kept) if row[2] == 'status' else ' · '.join(kept)) or '없음'   # 쓰던 설비가 모두 지워진 부품은 조회 한 줄의 빈 칸
            row[4] += ' · ' + where
        part, alias = D.LAB_ALIAS_ADDED[:2]            # 새로 등록된 표기로 물어도 같은 부품의 사용 설비가 나온다
        users = sorted(a for a, t in D.TRUTH['assets'].items() if part in t['components'].values() and not (after == '삭제' and a == retired))
        rows.append(['3', alias, 'asset', ' · '.join(users), '입력/자료_변경분 품번_교차표_변경.csv:2 · 입력/자료/구성요소_목록.csv 교체부품 칸'])
    put(folder, {'결과/기대_답.csv': B.graph_expect_text(rows, '통합반')}, True)


def docker(*args):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


@contextmanager
def instance(folder):
    """이 시험이 새 폴더에서 만든 컨테이너만 라벨을 재확인한 뒤 정리한다."""
    state_path = folder / '.lab_connection.json'
    if state_path.exists():
        raise ValueError('기존 DB 연결이 있는 폴더를 시험하지 않습니다.')
    try:
        command(folder, 'run.py', 'db', '--no-open')
        yield json.loads(state_path.read_text(encoding='utf-8'))
    finally:
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding='utf-8'))
            info = json.loads(docker('inspect', state['container']))[0]
            assert state['container'] == 'hyd-student-' + state['id']
            assert info['Config']['Labels']['hyd.practice.id'] == state['id']
            docker('rm', '-f', '-v', state['container'])
            assert not docker('ps', '-a', '-q', '--filter', 'name=^/' + state['container'] + '$')
            state_path.unlink()


def result(folder, action):
    command(folder, 'run.py', action, '--no-open')
    return json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']


def equal_answers(blocks):
    compare = [b for b in blocks if b['kind'] == 'compare']
    assert compare and all(r['state'] == '같음' for b in compare for r in b['rows']), compare
    return {r['key']: r['cells'][0][1] for b in compare for r in b['rows']}


def normalized(graph):
    return sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in graph['nodes']), sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in graph['rels'])


def per_asset(graph):
    """설비마다 딸린 구성 요소 · 센서 · 실물 수(수정본 반영 뒤 원자료와 다시 세는 값)."""
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    owner = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT'}
    out = {a: {'Component': 0, 'Sensor': 0, 'Unit': 0} for a, l in label.items() if l == 'Asset'}
    for c, a in owner.items():
        out[a]['Component'] += 1
    for r in graph['rels']:
        if r['type'] in ('MONITORED_BY', 'INSTALLED_UNIT') and r['a'] in owner:
            out[owner[r['a']]][label[r['b']]] += 1
    return out


def http(folder, statement):
    """시험이 랩 DB에 직접 보내는 쿼리(제공 코드 밖 — 겹친 노드를 일부러 만들고 지우거나 개수를 따로 세는 데만 쓴다)."""
    import urllib.request
    state = json.loads((folder / '.lab_connection.json').read_text(encoding='utf-8'))
    body = json.dumps({'statements': [{'statement': statement}]}).encode()
    with urllib.request.urlopen(urllib.request.Request(state['http'] + '/db/neo4j/tx/commit', body, {'Content-Type': 'application/json'}), timeout=60) as r:
        data = json.loads(r.read())
    assert not data['errors'], data['errors']
    return [x['row'] for x in data['results'][0]['data']]


def walk_view(folder, action):
    """질문 화면의 「쿼리가 따라간 길」 그림마다 (노드 식별자, 관계, 관계 표시)."""
    return {b['title']: (sorted(n['id'] for n in b['nodes']), sorted((l['text'], l['a'], l['b']) for l in b['links']), sorted({l['mark'] for l in b['links']}))
            for b in result(folder, action) if b['kind'] == 'graph' and b['title'].startswith('쿼리가 따라간 길')}


def walk_trials(folder, graph):
    """질문 화면의 「쿼리가 따라간 길」(리허설 v55 막힘 1) — 쿼리의 패턴이 랩 DB에서 실제로 지난 노드 · 관계만 그리고(쓰지 않은 관계 · 다른 설비의 같은 이름 대상을 칠하지 않는다),
    결과 열을 식별자 대신 이름으로 돌려줘도 세 질문 모두 같은 길이며, 읽지 못하는 쿼리는 그림 없이 까닭을 말한다."""
    import csv, io, re
    query = folder / 'app/features/query.cypher'
    kept = query.read_bytes()
    text = kept.decode('utf-8')
    first = {a: walk_view(folder, a) for a in ('sensors', 'parts', 'usage')}
    assert all(first.values()), first
    rows = [r for r in csv.DictReader(io.StringIO('\n'.join(x for x in (folder / 'app/features/expected.csv').read_text(encoding='utf-8-sig').splitlines() if not x.startswith('#'))))]
    asked = next(r['물을_값'] for r in rows if r['질문'] == '1')
    rels = graph['rels']
    comps = {r['b'] for r in rels if r['type'] == 'HAS_COMPONENT' and r['a'] == asked}
    seen = [('MONITORED_BY', r['a'], r['b']) for r in rels if r['type'] == 'MONITORED_BY' and r['a'] in comps]
    q1 = text[text.index('// 질문 1'):text.index(';', text.index('// 질문 1'))]
    if 'OBSERVES' in q1:
        seen += [('OBSERVES', r['a'], r['b']) for r in rels if r['type'] == 'OBSERVES' and r['a'] in {b for _, _, b in seen}]
    want = sorted(seen + [('HAS_COMPONENT', asked, c) for c in {a for t, a, _ in seen if t == 'MONITORED_BY'}])      # 생성 모델에서 따로 센 질문 1의 길
    (nodes, links, marks), = first['sensors'].values()
    assert links == want and marks == ['hit'] and nodes == sorted({asked} | {x for _, a, b in want for x in (a, b)}), (links[:5], want[:5])
    assert not any(t == 'USES_PART' for t, _, _ in links)
    renamed, count = re.subn(r'\b(\w+)\.id AS (\w+)', r'\1.name AS \2', text)      # 결과 열을 식별자 대신 이름으로(센서처럼 이름이 없으면 빈 값)
    assert count >= 3, count
    query.write_text(renamed, encoding='utf-8', newline='\n')
    again = {a: walk_view(folder, a) for a in ('sensors', 'parts', 'usage')}
    assert again == first, '결과 열의 꼴을 바꾸니 따라간 길이 달라졌다'
    body = q1.split('\n', 1)[1]
    query.write_text(text.replace(q1, q1 + '\nUNION\n' + body), encoding='utf-8', newline='\n')
    blocks = result(folder, 'sensors')
    assert not [b for b in blocks if b['kind'] == 'graph'], '읽지 못하는 쿼리에 그림을 그렸다'
    said = [c for b in blocks if b['kind'] == 'cards' for c in b['items'] if c['title'] == '이 쿼리에서 길을 읽지 못했습니다']
    assert said and 'UNION' in said[0]['text'], said
    equal_answers(blocks)
    query.write_bytes(kept)
    return [{'walked_path': 'sensors · parts · usage', 'only_pattern_relations': True, 'same_when_columns_are_names': True, 'unreadable_query_says_why': True}]


def constraint_view(folder):
    blocks = result(folder, 'constraints')
    table = next(b for b in blocks if b['kind'] == 'table' and b['title'].startswith('종류마다'))
    return {row[0]: row for row in table['rows']}, blocks


def constraint_trials(folder, graph, empty='실행할 쿼리가 없습니다', convert=P.convert):
    """유일 제약 걸음(빈 랩 DB에서) — 빈 틀 · 제약이 아닌 쿼리는 멈추고, 건 종류만 DB가 거절하며, 시험이 데이터를 남기지 않고, 다시 걸어도 되고,
    제약이 걸린 뒤 CREATE로 넣는 쿼리는 두 번째 실행에서 DB가 거절한다."""
    out = []
    path = folder / 'app/features/constraints.cypher'
    answer = path.read_text(encoding='utf-8')
    schema = json.loads((folder / 'data/model/schema.json').read_text(encoding='utf-8'))
    labels = sorted(schema['classes'])
    assert sorted({n['labels'][0] for n in graph['nodes']}) == labels, '제공 모델의 종류와 인스턴스의 레이블이 다름'
    count = lambda: http(folder, 'MATCH (n) RETURN count(n)')[0][0]
    constraints = lambda: http(folder, 'SHOW CONSTRAINTS YIELD name RETURN count(*)')[0][0]
    path.write_text(convert(A.CONSTRAINT_BLANK), encoding='utf-8', newline='\n')
    assert empty in command(folder, 'run.py', 'constraints', '--no-open', ok=False)
    path.write_text(answer + "CREATE (:Asset {id: 'X'});\n", encoding='utf-8', newline='\n')
    stopped = command(folder, 'run.py', 'constraints', '--no-open', ok=False)
    assert f'constraints.cypher:{len(labels) + 2}: 이 파일에는 제약을 거는 쿼리' in stopped, stopped[-400:]
    assert count() == 0 and constraints() == 0, '멈춘 실행이 랩 DB를 바꿈'
    out.append({'constraints': 'blank-and-non-constraint-query', 'stopped': True, 'db_untouched': True})
    # 한 종류를 빼고 걸면: 그 종류만 「없음」 · 「받아 줌」이고, 시험한 노드는 남지 않는다
    missing = 'Part'
    lines = answer.splitlines(keepends=True)
    assert sum(f'(n:{missing})' in x for x in lines) == 1
    path.write_text(''.join(x for x in lines if f'(n:{missing})' not in x), encoding='utf-8', newline='\n')
    rows, _ = constraint_view(folder)
    assert sorted(rows) == labels
    assert rows[missing][2] == '없음' and rows[missing][4].startswith('받아 줌'), rows[missing]
    assert all(rows[l][2] != '없음' and rows[l][4].startswith('거절') and 'already exists' in rows[l][4] for l in labels if l != missing), rows
    assert count() == 0, '유일 제약 시험이 노드를 남김'
    out.append({'constraints': 'one-class-left-out', 'unconstrained_accepts_twice': missing, 'others_rejected': len(labels) - 1, 'nodes_left': 0})
    path.write_text(answer, encoding='utf-8', newline='\n')
    rows, blocks = constraint_view(folder)
    assert all(rows[l][2] != '없음' and rows[l][4].startswith('거절') for l in labels), rows
    shown = next(b for b in blocks if b['kind'] == 'table' and 'SHOW CONSTRAINTS' in b['title'])
    assert len(shown['rows']) == len(labels) == constraints()
    again, _ = constraint_view(folder)       # 다시 걸어도 같다(IF NOT EXISTS)
    assert again == rows and count() == 0
    out.append({'constraints': 'all-classes', 'unique_constraints': len(labels), 'rejected': len(labels), 'rerun_same': True, 'nodes_left': 0})
    # 유일 제약이 걸린 뒤: MERGE 대신 CREATE로 넣는 쿼리는 처음에는 들어가고, 다시 넣으면 DB가 거절해 오류로 멈추며 개수는 그대로다(이론 57장)
    load = folder / 'app/features/load.cypher'
    merge = load.read_text(encoding='utf-8')
    create = merge.replace('MERGE (n:', 'CREATE (n:').replace(' ON CREATE SET n = row;', ' SET n = row;')
    assert create.count('CREATE (n:') == merge.count('MERGE (n:') >= 1      # 학생이 쓴 노드 쿼리(통합반은 설비 하나, 실전반은 종류마다)
    load.write_text(create, encoding='utf-8', newline='\n')
    try:
        result(folder, 'load')
        assert count() == len(graph['nodes'])
        refused = command(folder, 'run.py', 'repeat', '--no-open', ok=False)
        assert 'load.cypher:' in refused and 'already exists' in refused, refused[-500:]
        assert count() == len(graph['nodes']), 'DB가 거절한 다시 넣기가 노드를 늘림'
    finally:
        load.write_text(merge, encoding='utf-8', newline='\n')
    rows, _ = constraint_view(folder)        # 데이터가 들어 있는 랩 DB에서 다시 실행: 첫 CREATE부터 거절되고 개수는 그대로
    assert all(rows[l][4].startswith('거절') for l in labels) and count() == len(graph['nodes'])
    out.append({'constraints': 'create-instead-of-merge', 'first_load_ok': True, 'second_load_rejected_by_db': True, 'nodes_unchanged': count(), 'rerun_on_loaded_db': True})
    return out


def legacy_db_trials(folder, graph):
    """제약 없이 먼저 넣은 랩 DB(앞 판으로 실습하던 폴더)에서 유일 제약 걸음이 도는가 — 겹친 노드가 있으면 종류 · 식별자 · 개수를 짚고 멈추고, 겹침을 정리하면 걸린다."""
    result(folder, 'load')
    labels = sorted({n['labels'][0] for n in graph['nodes']})
    first = next(n['props']['id'] for n in graph['nodes'] if n['labels'] == ['Asset'])
    http(folder, f"CREATE (:Asset {{id: '{first}', lab_trial: true}})")
    stopped = command(folder, 'run.py', 'constraints', '--no-open', ok=False)
    assert f'Asset 「{first}」 2개' in stopped and 'constraints.cypher:' in stopped, stopped[-600:]
    http(folder, 'MATCH (n:Asset {lab_trial: true}) DELETE n')
    rows, _ = constraint_view(folder)
    assert all(rows[l][2] != '없음' and rows[l][4].startswith('거절') for l in labels), rows
    assert http(folder, 'MATCH (n) RETURN count(n)') == [[len(graph['nodes'])]]
    return [{'constraints': 'on-db-loaded-without-constraints', 'duplicate_named_and_stopped': f'Asset {first}', 'after_cleanup_all_constrained': len(labels), 'nodes_unchanged': True}]


def swapped(folder, name, old, new, count=1):
    """빈 틀 파일의 한 곳을 바꾼 사본을 쓰고 원래 바이트를 돌려준다."""
    path = folder / 'app/features' / name
    kept = path.read_bytes()
    text = kept.decode('utf-8')
    assert text.count(old) == count, (name, old, text.count(old))
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')
    return path, kept


def cards_of(blocks, title):
    return [c for b in blocks if b['kind'] == 'cards' and b['title'].startswith(title) for c in b['items']]


def wrong_choices_before_update(folder, graph):
    """그럴듯하지만 틀린 선택을 실제로 넣어 돌린다(수정본 반영 전) — 결과(화면 · 답)가 달라지는가. 걸리는 것은 DB의 실제 답뿐이다."""
    out = []
    nodes = lambda: http(folder, 'MATCH (n) RETURN count(n)')[0][0]
    # 넣기 전 실험: 유일 제약이 지키는 둘은 거절, 지키지 못하는 셋은 오류 없이 받아 준다. 실험은 랩 DB에 아무것도 남기지 않는다
    start = nodes()
    cards = cards_of(result(folder, 'probe'), '넣는 쿼리를 이렇게 쓰면')
    said = [c['badge'] for c in cards]
    assert said == ['DB가 거절', 'DB가 거절', '오류 없이 받아 줌', '오류 없이 받아 줌', '오류 없이 받아 줌'], said
    assert 'already exists' in cards[0]['text'] and 'already exists' in cards[1]['text'] and '2개' in cards[2]['text'], [c['text'] for c in cards[:3]]
    assert '만든 관계 1개' in cards[3]['text'] and '물으면 0행, 거꾸로 물으면 1행' in cards[3]['text'] and '만든 관계는 0개' in cards[4]['text'], [c['text'] for c in cards[3:]]
    assert nodes() == start
    out.append({'wrong_choice': 'probe', 'db_answers': said, 'nodes_left_by_probe': 0})
    # 관계 쿼리가 끝 노드를 레이블 없이 식별자만으로 찾으면: 개수는 같지만 DB의 실행 계획이 모든 노드를 훑는다
    path, kept = swapped(folder, 'load.cypher', 'MATCH (a:Component {id: row.a}), (b:Part {id: row.b})', 'MATCH (a {id: row.a}), (b {id: row.b})')
    try:
        seek = {c['title']: c for c in cards_of(result(folder, 'load'), '내 쿼리가 노드를 찾는 법')}
        assert seek['USES_PART']['state'] == 'warn' and 'AllNodesScan' in seek['USES_PART']['lines'][1][1], seek['USES_PART']
        assert seek['Asset']['state'] == 'ok' and seek['INSTALLED_UNIT']['state'] == 'ok', seek
    finally:
        path.write_bytes(kept)
    seek = cards_of(result(folder, 'load'), '내 쿼리가 노드를 찾는 법')
    assert len(seek) == 3 and all(c['state'] == 'ok' and 'Seek' in c['lines'][1][1] for c in seek), seek
    out.append({'wrong_choice': 'relation-endpoints-without-labels', 'plan_scans_all_nodes': True, 'with_labels_all_seek': 3})
    # 질문 3을 사내 품번으로만 찾으면: 다른 표기 · 없는 품번으로 물은 줄이 기대 답과 달라진다
    path, kept = swapped(folder, 'query.cypher', ' OR $part IN coalesce(p.other_codes, [])', '')
    try:
        rows = [r for b in result(folder, 'usage') if b['kind'] == 'compare' for r in b['rows']]
        off = [r['key'] for r in rows if r['state'] != '같음']
        assert len(off) == len(B.GRAPH_ASK['aliases']) and all(any(a in k for a in B.GRAPH_ASK['aliases']) for k in off), off
    finally:
        path.write_bytes(kept)
    equal_answers(result(folder, 'usage'))
    out.append({'wrong_choice': 'usage-by-part-number-only', 'rows_different': len(off), 'of_rows': len(rows)})
    # 질문 1에서 없는 한계를 0으로 채우면: 한계 줄이 기대 답(없음)과 달라진다
    path, kept = swapped(folder, 'query.cypher', 's.limit AS limit', 'coalesce(s.limit, 0) AS limit')
    try:
        rows = [r for b in result(folder, 'sensors') if b['kind'] == 'compare' for r in b['rows']]
        off = [r['key'] for r in rows if r['state'] != '같음']
        assert len(off) == 1 and 'limit' in off[0], off
    finally:
        path.write_bytes(kept)
    equal_answers(result(folder, 'sensors'))
    out.append({'wrong_choice': 'missing-limit-filled-with-zero', 'rows_different': 1, 'of_rows': len(rows)})
    # 질문 1의 화살표를 거꾸로 적으면: 0줄
    path, kept = swapped(folder, 'query.cypher', '-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->', '<-[:HAS_COMPONENT]-(c:Component)-[:MONITORED_BY]->')
    try:
        rows = [r for b in result(folder, 'sensors') if b['kind'] == 'compare' for r in b['rows']]
        assert rows and all(r['state'] != '같음' and r['cells'][0][1] == '0줄' for r in rows), rows
    finally:
        path.write_bytes(kept)
    equal_answers(result(folder, 'sensors'))
    out.append({'wrong_choice': 'query-arrow-reversed', 'answer': '0줄', 'rows_different': len(rows)})
    return out


def wrong_choices_after_update(folder, renamed, new_name):
    """수정본을 반영한 뒤에야 드러나는 틀린 선택 — 값을 매번 덮어쓰는 적재 쿼리, 패턴에 이름을 적은 MERGE. 끝나면 정답 쿼리와 수정본 반영으로 되돌린다."""
    out = []
    name = lambda: http(folder, f"MATCH (a:Asset {{id: '{renamed}'}}) RETURN a.name")[0][0]
    assert name() == new_name
    path, kept = swapped(folder, 'load.cypher', 'MERGE (n:Asset {id: row.id}) ON CREATE SET n = row;', 'MERGE (n:Asset {id: row.id}) SET n = row;')
    try:
        again = result(folder, 'repeat')
        back = [c for c in cards_of(again, '한 번 더 넣어서 달라진 것') if c.get('badge') == '값이 바뀜']
        assert again[0]['state'] == 'bad' and renamed in [c['title'] for c in back] and name() != new_name, (again[0], back)
    finally:
        path.write_bytes(kept)
    result(folder, 'update')
    assert name() == new_name and result(folder, 'repeat')[0]['state'] == 'ok'
    out.append({'wrong_choice': 'set-without-on-create', 'reload_reverts_updated_values': len(back), 'on_create_set_keeps_them': True})
    path, kept = swapped(folder, 'load.cypher', 'MERGE (n:Asset {id: row.id}) ON CREATE SET n = row;', 'MERGE (n:Asset {id: row.id, name: row.name}) ON CREATE SET n = row;')
    try:
        refused = command(folder, 'run.py', 'repeat', '--no-open', ok=False)
        assert 'load.cypher:' in refused and 'already exists' in refused, refused[-500:]
    finally:
        path.write_bytes(kept)
    assert name() == new_name and result(folder, 'repeat')[0]['state'] == 'ok'
    out.append({'wrong_choice': 'merge-pattern-with-name', 'reload_after_rename_rejected_by_db': True})
    return out


def wrong_update(folder):
    """수정 쿼리의 틀린 선택(랩 DB를 실제로 바꾸므로 이 갈래의 맨 끝에서) — 삭제 줄을 받는 쿼리가 없음, 새 표기를 매번 덧붙임, 글자로 온 수를 그대로 넣음."""
    out = []
    update = folder / 'app/features/update.cypher'
    kept = update.read_bytes()
    text = kept.decode('utf-8')
    head = '// 반영할 것: sensor_changes.csv 삭제\n'
    assert text.count(head) == 1
    a = text.index(head)
    update.write_text(text[:a] + text[text.index('\n// 반영할 것:', a):], encoding='utf-8', newline='\n')
    blocks = result(folder, 'update')
    lost = cards_of(blocks, '아직 쿼리가 없는 수정본 줄')
    assert blocks[0]['state'] == 'warn' and len(lost) == 1 and 'sensor_changes.csv' in lost[0]['title'] and '삭제' in lost[0]['title'], (blocks[0], lost)
    out.append({'wrong_choice': 'no-query-for-deleted-rows', 'rows_not_applied': lost[0]['badge']})
    bad = text.replace(' WHERE NOT row.다른표기 IN coalesce(p.other_codes, [])\n', '\n').replace('toFloat(row.한계)', 'row.한계')
    assert bad != text and bad.count('toFloat(row.정상값)') == 1
    update.write_text(bad, encoding='utf-8', newline='\n')
    blocks = result(folder, 'update')
    assert blocks[0]['state'] == 'warn' and '또 바뀌었습니다' in blocks[0]['detail'] and '자료형이 바뀐 값 1개' in blocks[0]['detail'], blocks[0]
    result(folder, 'export')
    failed = command(folder, 'run.py', 'check', '--no-open', ok=False)
    assert 'number 이어야 함' in failed and '숫자 자리에 글자' in failed, failed[-500:]
    update.write_bytes(kept)
    out.append({'wrong_choice': 'alias-appended-every-run-and-number-kept-as-text', 'second_run_changes_again': True, 'type_change_shown': 1, 'check_fails': True})
    return out


def trials(starter, work):
    records, usage, sensors = student_condition_selftest(starter, work, 'sources'), {}, {}
    (renamed, new_name), (retired, status) = D.LAB_RENAMED, D.LAB_RETIRED
    truth = D.TRUTH['assets']
    counted = {a: {'Component': len(t['components']), 'Sensor': len(t['sensors']), 'Unit': sum(1 for (x, _) in D.SERIALS if x == a) + (D.REMOVED_PUMP[0] == a)}
               for a, t in truth.items()}      # 생성 정답 구조에서 센 설비별 대상 수
    for change in ('남김', '삭제'):
        folder = work / change / starter.name
        shutil.copytree(starter, folder, ignore=shutil.ignore_patterns('__pycache__', 'output', '.lab_connection.json'))
        graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
        branch = B.GRAPH_LAB_INPUT['통합반']     # 제공 모델 = 설계 랩 강사 참조 그 갈래(실물을 나눔 · 붙은 자리까지 물리량)
        assert not V.diff(V.expected('통합반', branch), V.answers_from_graph('통합반', branch, graph))
        assert per_asset(graph) == counted, (per_asset(graph), counted)
        command(folder, 'run.py', '--no-open')
        # 빈 기능을 이미 실행된 결과처럼 보이지 않는다.
        empty = command(folder, 'run.py', 'load', '--no-open', ok=False)
        assert '실행할 쿼리가 없습니다' in empty
        fill(folder, change)
        # 기대 답에 같은 (질문 · 물을_값) 짝을 두 줄 쓰면 그 두 줄을 짚고, 다른 열을 견줄 길(다른 표기로 물은 줄)을 말하며 멈춘다
        expected_file = folder / 'app/features/expected.csv'
        kept = expected_file.read_bytes()
        last = kept.decode('utf-8').rstrip('\n').split('\n')[-2]       # 사용 설비를 묻는 줄 하나를 그대로 한 번 더
        expected_file.write_bytes(kept + (last + '\n').encode('utf-8'))
        twice = command(folder, 'run.py', 'expected', '--no-open', ok=False)
        assert '두 줄입니다' in twice and '볼_열을 바꾼 줄' in twice, twice[-400:]
        expected_file.write_bytes(kept)
        records.append({'same_pair_twice': 'expected', 'stopped_with_way_out': True})
        with instance(folder) as state:
            records += constraint_trials(folder, graph) if change == '남김' else legacy_db_trials(folder, graph)
            result(folder, 'load')
            result(folder, 'export')
            initial = json.loads((folder / 'output/graph.json').read_text(encoding='utf-8'))
            assert normalized(initial) == normalized(graph)
            result(folder, 'repeat')
            result(folder, 'export')
            assert normalized(initial) == normalized(json.loads((folder / 'output/graph.json').read_text(encoding='utf-8')))
            equal_answers(result(folder, 'sensors'))
            equal_answers(result(folder, 'parts'))
            before = equal_answers(result(folder, 'usage'))
            if change == '남김':
                records += walk_trials(folder, graph)
                records += wrong_choices_before_update(folder, graph)
            # 빈 결정이면 멈춤: 정한_것.csv 지점 줄이 비어 있으면 그 결정을 쓰는 기능(수정본 반영)이 그 줄을 짚고 멈춘다
            decisions = folder / 'app/features/decisions.csv'
            filled = decisions.read_bytes()
            for i, point in enumerate(B.GRAPH_POINTS['통합반']):
                lines = filled.decode('utf-8').rstrip('\n').split('\n')
                at = next(k for k, x in enumerate(lines) if x.startswith(point + ','))
                decisions.write_text('\n'.join(lines[:at] + [point + ',,,'] + lines[at + 1:]) + '\n', encoding='utf-8', newline='\n')
                out = command(folder, 'run.py', 'update', '--no-open', ok=False)
                assert 'decisions.csv:' in out and point in out, out[-500:]
                records.append({'empty_decision': 'update', 'stopped_on': point})
            decisions.write_bytes(filled)
            update = result(folder, 'update')
            assert any(b['kind'] == 'note' and '더 바뀐 것 없음' in b['text'] for b in update)
            assert update[0]['kind'] == 'verdict' and update[0]['state'] == 'ok', update[0]
            assert not [b for b in update if b['kind'] == 'cards' and b['title'].startswith(('아직 쿼리가 없는', 'DB에서 아무것도'))], '처음 반영에서 받지 못했거나 아무것도 바꾸지 않은 수정본 줄이 있음'
            after = json.loads((folder / 'output/after_update.json').read_text(encoding='utf-8'))
            props = {n['props']['id']: n['props'] for n in after['nodes']}
            assert props[renamed]['name'] == new_name                      # 이름이 바뀐 설비는 같은 식별자로 남는다
            kinds = lambda g, label: sorted(n['props']['id'] for n in g['nodes'] if n['labels'] == [label])
            assert kinds(after, 'Part') == kinds(graph, 'Part') and kinds(after, 'Quantity') == kinds(graph, 'Quantity')   # 공용 대상은 어느 갈래에서도 남는다
            (lc, lt, limit, _), (rc, rt, _), (part, alias, *_) = D.LAB_SENSOR_LIMIT, D.LAB_SENSOR_REMOVED, D.LAB_ALIAS_ADDED
            assert props[f'{lc}:{lt}']['limit'] == float(limit) and isinstance(props[f'{lc}:{lt}']['limit'], float)      # 글자로 온 값을 수로 넣었다
            assert props[part]['other_codes'].count(alias) == 1                                                        # 새 표기는 한 번만 더해진다(두 번 반영해도)
            gone = f'{rc}:{rt}'
            if change == '남김':
                assert props[retired]['status'] == status and props[gone]['status'] == '떼어 냄'
                assert per_asset(after) == counted
                assert len(after['nodes']) == len(graph['nodes']) and len(after['rels']) == len(graph['rels'])
            else:
                assert retired not in props and gone not in props
                left = {a: dict(c, Sensor=c['Sensor'] - (a == rc)) for a, c in counted.items() if a != retired}
                assert per_asset(after) == left, (per_asset(after), left)      # 남은 설비의 대상은 떼어 낸 센서 하나 말고는 사라지지 않는다
                assert len(graph['nodes']) - len(after['nodes']) == 1 + sum(counted[retired].values()) + 1
            expectation(folder, after=change)
            usage[change] = equal_answers(result(folder, 'usage'))
            sensors[change] = equal_answers(result(folder, 'sensors'))
            assert usage[change] != before, (change, '수정본을 반영해도 사용 설비 조회의 답이 그대로')
            records.append({'change': change, 'initial_nodes': len(initial['nodes']), 'after_nodes': len(after['nodes']), 'after_rels': len(after['rels']),
                            'per_asset_after': per_asset(after), 'usage_before': before, 'usage_after': usage[change], 'sensors_after': sensors[change]})
            # 수정본 반영 뒤 모델을 한 번 더 넣으면: 남김은 그대로이고, 삭제는 지운 노드가 모델 파일에서 다시 생긴다(수정본을 다시 반영하면 다시 지워진다)
            again = result(folder, 'repeat')
            if change == '남김':
                assert again[0]['state'] == 'ok', again[0]
                records += wrong_choices_after_update(folder, renamed, new_name)
            else:
                back = [c['title'] for b in again if b['kind'] == 'cards' for c in b['items'] if c.get('badge') == '다시 생김']
                assert again[0]['state'] == 'bad' and retired in back and gone in back, (again[0], back)
                result(folder, 'update')
                result(folder, 'export')
                assert normalized(json.loads((folder / 'output/graph.json').read_text(encoding='utf-8'))) == normalized(after)
                records.append({'reload_after_delete': 'deleted nodes come back from the model file', 'came_back': len(back), 'update_again_restores': True})
            result(folder, 'export')
            result(folder, 'check')
            if change == '남김':
                # 새 프로세스로 DB를 다시 켜도 같은 폴더의 그래프가 유지되는지 확인한다.
                docker('stop', state['container'])
                result(folder, 'db')
                result(folder, 'export')
                saved = (folder / 'output/graph.json').read_bytes()
                assert normalized(json.loads(saved)) == normalized(after)
                for broken in ('duplicate-id', 'missing-endpoint', 'reverse-direction'):
                    damaged = copy.deepcopy(after)
                    if broken == 'duplicate-id':
                        damaged['nodes'].append(copy.deepcopy(damaged['nodes'][0]))
                    elif broken == 'missing-endpoint':
                        damaged['rels'][0]['b'] = 'not-in-graph'
                    else:
                        damaged['rels'][0]['a'], damaged['rels'][0]['b'] = damaged['rels'][0]['b'], damaged['rels'][0]['a']
                    (folder / 'output/graph.json').write_text(json.dumps(damaged), encoding='utf-8')
                    assert '구조 확인 필요' in command(folder, 'run.py', 'check', '--no-open', ok=False)
                    records.append({'broken': broken, 'rejected': True})
                (folder / 'output/graph.json').write_bytes(saved)
                state_path = folder / '.lab_connection.json'
                original = state_path.read_bytes()
                state_path.write_text(json.dumps(state | {'id': 'wrong-owner'}), encoding='utf-8')
                try:
                    assert '이 폴더의 랩 DB가 아닙니다' in command(folder, 'run.py', 'status', '--no-open', ok=False)
                finally:
                    state_path.write_bytes(original)
                records.append({'restart_preserves_graph': True, 'wrong_owner_rejected': True, 'empty_feature_rejected': True})
                records += wrong_update(folder)
        print(change + ' 실행·정리 통과', flush=True)
    assert usage['남김'] != usage['삭제'], '불용 결정 설비의 두 갈래가 같은 답을 냄'
    assert sensors['남김'] != sensors['삭제'], '목록에서 빠진 센서의 두 갈래가 같은 답을 냄'
    records.append({'decision': '목록에서 빠진 센서', 'changed_answers': {k: [sensors['남김'].get(k), sensors['삭제'].get(k)] for k in sensors['남김'] if sensors['남김'][k] != sensors['삭제'].get(k)}})
    records.append({'decision': '불용 결정 설비', 'changed_answers': {k: [usage['남김'].get(k), usage['삭제'].get(k)] for k in usage['남김'] if usage['남김'][k] != usage['삭제'].get(k)}})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    base = ROOT / '작업/검사/session2-projects'
    base.mkdir(parents=True, exist_ok=True)
    with D.for_course('통합반'), tempfile.TemporaryDirectory(prefix='graph-trials-', dir=base) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(base.resolve()) and work != base.resolve()
        records = trials(args.folder.resolve(), work)
        (base / 'graph-results.json').write_text(json.dumps({'kind': '실제 별도 DB·강사 참조; 학생 AI 또는 GUI 시험 아님', 'records': records, 'created_containers_removed': True}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 검증 통과')


if __name__ == '__main__':
    main()
