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
    put(folder, {A.CONSTRAINT_FILE: A.constraint_answer(schema), '결과/load.cypher': A.load_answer(graph),
                 '결과/update.cypher': A.update_integrated(change),
                 '결과/query.cypher': A.query_text([A.QUERY_INTEGRATED[n] for n in (1, 2, 3)]),
                 '결과/정한_것.csv': B.chosen_text([B.graph_chosen('통합반')[change]])}, True)
    expectation(folder)


def expectation(folder, after=None):
    """기대 답 표. after = 수정본을 반영한 갈래(남김 · 삭제)면 불용 설비가 걸린 줄을 수정본 줄에서 다시 정한다(제공 모델이 아니라 D.changes에서)."""
    graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
    rows = B.graph_expect_rows('통합반', graph)
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


def constraint_view(folder):
    blocks = result(folder, 'constraints')
    table = next(b for b in blocks if b['kind'] == 'table' and b['title'].startswith('종류마다'))
    return {row[0]: row for row in table['rows']}, blocks


def constraint_trials(folder, graph):
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
    path.write_text(P.convert(A.CONSTRAINT_BLANK), encoding='utf-8', newline='\n')
    assert '실행할 쿼리가 없습니다' in command(folder, 'run.py', 'constraints', '--no-open', ok=False)
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
    assert create.count('CREATE (n:') == len(labels)
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


def trials(starter, work):
    records, usage = student_condition_selftest(starter, work, 'sources'), {}
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
        assert '두 줄입니다' in twice and '다른 표기로 물은 줄' in twice, twice[-400:]
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
            # 빈 결정이면 멈춤: 정한_것.csv 지점 줄이 비어 있으면 그 결정을 쓰는 기능(수정본 반영)이 그 줄을 짚고 멈춘다
            decisions = folder / 'app/features/decisions.csv'
            filled = decisions.read_bytes()
            decisions.write_text(P.convert(B.decision_template(B.GRAPH_POINTS['통합반'])), encoding='utf-8', newline='\n')
            out = command(folder, 'run.py', 'update', '--no-open', ok=False)
            assert 'decisions.csv:' in out and '불용 결정 설비' in out, out[-500:]
            records.append({'empty_decision': 'update', 'stopped_on': '불용 결정 설비'})
            decisions.write_bytes(filled)
            update = result(folder, 'update')
            assert any(b['kind'] == 'note' and '더 바뀐 것 없음' in b['text'] for b in update)
            after = json.loads((folder / 'output/after_update.json').read_text(encoding='utf-8'))
            props = {n['props']['id']: n['props'] for n in after['nodes']}
            assert props[renamed]['name'] == new_name                      # 이름이 바뀐 설비는 같은 식별자로 남는다
            kinds = lambda g, label: sorted(n['props']['id'] for n in g['nodes'] if n['labels'] == [label])
            assert kinds(after, 'Part') == kinds(graph, 'Part') and kinds(after, 'Quantity') == kinds(graph, 'Quantity')   # 공용 대상은 어느 갈래에서도 남는다
            if change == '남김':
                assert props[retired]['status'] == status
                assert per_asset(after) == counted
                assert len(after['nodes']) == len(graph['nodes']) and len(after['rels']) == len(graph['rels'])
            else:
                assert retired not in props
                assert per_asset(after) == {a: c for a, c in counted.items() if a != retired}      # 남은 설비의 대상은 하나도 사라지지 않는다
                assert len(graph['nodes']) - len(after['nodes']) == 1 + sum(counted[retired].values())
            expectation(folder, after=change)
            usage[change] = equal_answers(result(folder, 'usage'))
            assert usage[change] != before, (change, '수정본을 반영해도 사용 설비 조회의 답이 그대로')
            records.append({'change': change, 'initial_nodes': len(initial['nodes']), 'after_nodes': len(after['nodes']), 'after_rels': len(after['rels']),
                            'per_asset_after': per_asset(after), 'usage_before': before, 'usage_after': usage[change]})
            reference = json.loads((folder / 'data/reference_map.json').read_text(encoding='utf-8'))['관계']
            shown = [b for b in result(folder, 'compare') if b['kind'] == 'table' and b['title'].startswith('기준 지도')]
            assert len(shown) == 1 and len(shown[0]['rows']) == len(reference), '비교 화면에 기준 지도 표가 관계 수만큼 보여야 한다'
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
        print(change + ' 실행·정리 통과', flush=True)
    assert usage['남김'] != usage['삭제'], '불용 결정 설비의 두 갈래가 같은 답을 냄'
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
