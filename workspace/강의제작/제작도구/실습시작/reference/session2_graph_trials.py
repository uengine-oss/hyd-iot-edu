"""새 그래프 랩의 실제 별도 DB 실행·갈래·재실행 검증. AI 호출과 촬영을 하지 않는다."""
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


def fill(folder, change='남김', running=False):
    graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
    choices = B.graph_chosen('통합반')
    put(folder, {'결과/load.cypher': A.load_answer(graph),
                 '결과/update.cypher': A.UPDATE_INTEGRATED[change],
                 '결과/query.cypher': A.query_text([A.QUERY_INTEGRATED[1], A.QUERY_INTEGRATED[2], A.QUERY_PART_USAGE['빠짐' if running else '상태와 함께']]),
                 '결과/정한_것.csv': B.chosen_text([choices['가동 설비만' if running else '상태와 함께'], choices['수정본 지움' if change == '삭제' else '수정본 남김']])}, True)
    expectation(folder, graph, running)


def expectation(folder, graph, running, changed=False, deleted=False):
    rows = B.graph_expect_rows('통합반', graph)
    for row in rows:
        if row[0:2] == ['3', 'RF-10'] and changed:   # 수정본 구성요소_변경.csv 3줄: HYD-03 리턴 필터가 P-RTN-FLT-25로 바뀜
            row[3] = ' · '.join(x for x in row[3].split(' · ') if x != 'HYD-03')
        if row[0:2] == ['3', 'P-RTN-FLT-25'] and changed:
            row[3] = 'HYD-03'
        if row[0:2] == ['3', 'RF-10'] and (running or (changed and deleted)):
            row[3] = ' · '.join(x for x in row[3].split(' · ') if x != 'HYD-07')
            row[4] += ' · ' + ('입력/자료_변경분/2026-10-20_수정본/설비_대장_변경.csv:3' if changed else '입력/자료/설비_대장.csv:9')
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


def normalized(graph):
    return sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in graph['nodes']), sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in graph['rels'])


def trials(starter, work):
    records = []
    for change in ('남김', '삭제'):
        folder = work / change / starter.name
        shutil.copytree(starter, folder, ignore=shutil.ignore_patterns('__pycache__', 'output', '.lab_connection.json'))
        graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
        branch = B.GRAPH_LAB_INPUT['통합반']     # 제공 모델 = 설계 랩 강사 참조 그 갈래(실물 · 확인 필요 후보 · 붙은 자리까지 물리량)
        assert V.answers_from_graph('통합반', branch, graph) == V.expected('통합반', branch)
        assert not V.diff(V.answers_from_graph('통합반', branch, graph), V.answers_from_graph('통합반', branch, B.reference_model(False, branch)[1]))
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
            # 빈 결정이면 멈춤: 정한_것.csv 지점 줄이 비어 있으면 그 결정을 쓰는 기능(사용 설비 조회 · 수정본 반영)이 그 줄을 짚고 멈춘다
            decisions = folder / 'app/features/decisions.csv'
            filled = decisions.read_bytes()
            decisions.write_text(P.convert(B.decision_template(B.GRAPH_POINTS['통합반'])), encoding='utf-8', newline='\n')
            for action, point in (('usage', '시점과 상태'), ('update', '불용 결정 설비')):
                out = command(folder, 'run.py', action, '--no-open', ok=False)
                assert 'decisions.csv:' in out and point in out, out[-500:]
                records.append({'empty_decision': action, 'stopped_on': point})
            decisions.write_bytes(filled)
            for running in (False, True):
                fill(folder, change, running)
                equal_answers(result(folder, 'usage'))
            update = result(folder, 'update')
            assert any(b['kind'] == 'note' and '더 바뀐 것 없음' in b['text'] for b in update)
            after = json.loads((folder / 'output/after_update.json').read_text(encoding='utf-8'))
            props = {n['props']['id']: n['props'] for n in after['nodes']}
            assert props['HYD-02']['name'] == 'HYD-02 2라인 2호 파워팩'
            assert props['HYD-06:I_MOTOR']['normal'] == 18.5
            assert props['HYD-03:VS1']['unit'] == 'mm/s'
            assert 'HYD-01:TS1' in props
            # 수정본의 교체부품 확인 줄: 그 자리의 확인 필요 후보가 사라지고 확인된 품번 하나로만 이어진다
            pump = [(r['type'], r['b']) for r in after['rels'] if r['a'] == 'HYD-03:pump-a' and r['type'] in ('USES_PART', 'CANDIDATE_PART')]
            assert pump == [('USES_PART', 'P-PMP-SEAL')], pump
            rtn = [(r['type'], r['b']) for r in after['rels'] if r['a'] == 'HYD-03:rtn-filter' and r['type'] == 'USES_PART']
            assert rtn == [('USES_PART', 'P-RTN-FLT-25')], rtn   # 잇는 부품이 바뀐 수정 — 옛 관계는 지워지고 새 관계 하나
            if change == '남김':
                assert props['HYD-07']['status'] == '불용(매각 예정)'
                assert len(after['nodes']) == len(graph['nodes']) and len(after['rels']) == len(graph['rels'])
            else:
                units = sum(1 for (aid, _), _s in D.SERIALS.items() if aid == 'HYD-07')   # 그 설비 자리에 달린 실물도 함께 지운다
                gone = 1 + len(D.TRUTH['assets']['HYD-07']['components']) + len(D.TRUTH['assets']['HYD-07']['sensors']) + units
                assert 'HYD-07' not in props and len(graph['nodes']) - len(after['nodes']) == gone
            for running in (False, True):
                fill(folder, change, running)
                expectation(folder, graph, running, changed=True, deleted=change == '삭제')
                equal_answers(result(folder, 'usage'))
                records.append({'change': change, 'running_only': running, 'initial_nodes': len(initial['nodes']), 'after_nodes': len(after['nodes']), 'after_rels': len(after['rels']), 'answers': 'pass'})
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
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    base = ROOT / '작업/검사/session2-projects'
    with tempfile.TemporaryDirectory(prefix='graph-trials-', dir=base) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(base.resolve()) and work != base.resolve()
        records = trials(args.folder.resolve(), work)
        (base / 'graph-results.json').write_text(json.dumps({'kind': '실제 별도 DB·강사 참조; 학생 AI 또는 GUI 시험 아님', 'records': records, 'created_containers_removed': True}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 검증 통과')


if __name__ == '__main__':
    main()
