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
from reference.session2_project_trials import command, put


def fill(folder, change='남김'):
    graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
    put(folder, {'결과/load.cypher': A.load_answer(graph),
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
            row[3] = ' · '.join((status if a == retired else '가동') for a in kept) if row[2] == 'status' else ' · '.join(kept)
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


def trials(starter, work):
    records, usage = [], {}
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
        assert '실행할 문장이 없습니다' in empty
        fill(folder, change)
        with instance(folder) as state:
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
            result(folder, 'compare')
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
