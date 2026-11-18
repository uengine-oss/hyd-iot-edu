"""통합02 설계 랩(실습 랩 규모)의 강사 참조 시험 — 갈래마다 정답 내용을 새 사본에 넣고 실제로 실행해 판정한다. AI 호출 없음.

판정(한 기능을 여기 한 곳에서):
- 갈래 A · B · C · E마다 만든 모델(output/graph.json) 전체를 생성 정답 구조(data_session2.TRUTH → verify_reference.expected)와 견준다.
- 갈래마다 결과 화면의 대조(기대 답 ↔ 모델에 물은 답)가 줄마다 같음이고, 결정 지점마다 갈래가 다르면 그 질문의 답이 실제로 다르다.
- 빈 틀을 일부러 망가뜨리면(카디널리티 · 지난 실물 · 물리량 이름 · 빈 결정 · 처리 안 한 철거 줄 · 한 물리량에 섞인 단위) 제공 코드가 그 줄을 짚고 멈추고,
  교체부품 칸의 표기를 교차표에 없는 글로 바꾸면 잇지 않고 화면에 보인다. 모델을 망가뜨리면(ID 중복 · 끝점 없음 · 관계 방향) 구조 검사가 잡는다.
- 학생 ZIP과 완성본 ZIP을 새 폴더에 풀어 첫 명령과 재실행이 된다.
사용: python reference/session2_project_trials.py <ontology-lab 폴더>
"""
from pathlib import Path
import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_labs as B
import data_session2 as D
import session2_answers as A
import session2_project as P
import verify_reference as V
from lab_package import ROOT

ACTIONS = ['sources', 'expected', 'design', 'names', 'quantities', 'parts', 'query', 'check']


def command(folder, *args, ok=True):
    result = subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True, encoding='utf-8', env=os.environ | {'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
    output = result.stdout + result.stderr
    if (result.returncode == 0) != ok:
        raise AssertionError((str(folder), args, result.returncode, output))
    return output


def put(folder, files, convert=False):
    for name, text in files.items():
        target = folder / (P.convert(name) if convert else name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(P.convert(text) if convert else text, encoding='utf-8', newline='\n')


def blocks(folder, action):
    command(folder, 'run.py', action, '--no-open')
    return json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']


def model_answers(branch, graph):
    """학생 꼴 모델(output/graph.json)을 verify_reference.expected와 같은 꼴로 읽는다 — 구성 요소 이름은 그 설비 모델의 품목 키(build_labs.comp_key),
    물리량 이름은 강사 참조의 이름표(quantities_of)로 되짚는다."""
    pol = B.policy(branch)
    qid_of = {name: qid for qid, (name, _) in B.quantities_of(pol).items()}
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    by = {}
    for r in graph['rels']:
        by.setdefault(r['type'], []).append(r)
    owner = {r['b']: r['a'] for r in by['HAS_COMPONENT']}
    key = lambda cid: B.comp_key(props[cid]['name'], {k for k, *_ in D.MODEL_COMPONENTS[props[owner[cid]]['model']]})
    comp = lambda cid: f'{owner[cid]}:{key(cid)}'
    sensors, members, sprops, parts, units = {}, {}, {}, {a: {} for a, l in label.items() if l == 'Asset'}, {}
    for r in by['MONITORED_BY']:
        sensors.setdefault(owner[r['a']], {}).setdefault(key(r['a']), []).append(props[r['b']]['tag'])
    for r in by['OBSERVES']:
        qid, s = qid_of[props[r['b']]['name']], props[r['a']]
        members.setdefault(qid, []).append(r['a'])
        sprops[r['a']] = [qid, s['unit'], s.get('normal'), s.get('limit'), s.get('limit_direction'), None]   # 학생 꼴 모델은 kind를 두지 않는다 — 실측뿐인 실습 랩 규모의 기대 답도 None
    for cid, aid in owner.items():
        parts[aid][key(cid)] = next((r['b'] for r in by['USES_PART'] if r['a'] == cid), None)
    for r in by.get('INSTALLED_UNIT', []):
        units.setdefault(comp(r['a']), []).append([props[r['b']]['serial'], r['props']['current']])
    serials = {comp(c): p['serial'] for c, p in props.items() if label[c] == 'Component' and 'serial' in p}
    return {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors.items())},
            'quantity_members': {k: sorted(v) for k, v in sorted(members.items())}, 'sensor_props': dict(sorted(sprops.items())),
            'parts_by_asset': {a: dict(sorted(d.items())) for a, d in sorted(parts.items())},
            'units': {k: sorted(v) for k, v in sorted(units.items())}}, serials


def ontology(starter, work):
    records, answers = [], {}
    for branch in B.REFERENCE_BRANCHES['통합반']:
        new = work / ('new-' + branch)
        shutil.copytree(starter, new, ignore=shutil.ignore_patterns('__pycache__', 'output'))
        files = A.integrated_design(branch)
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        files['결과/기대_답.csv'] = B.expect_design_text(branch)
        put(new, files, True)
        for action in ACTIONS:
            (work / f'{branch}-{action}.txt').write_text(command(new, 'run.py', action, '--no-open'), encoding='utf-8')
        graph = json.loads((new / 'output/graph.json').read_text(encoding='utf-8'))
        exp = V.expected('통합반', branch)
        got, serials = model_answers(branch, graph)
        gap = V.diff({k: exp[k] for k in got}, got)
        assert not gap, (branch, gap)
        split = B.policy(branch)[2] == '나눔'      # 한 대상 갈래는 지금 달린 실물의 일련번호만 구성 요소 속성으로 남는다
        assert serials == ({} if split else {f'{a}:{k}': s for (a, k), s in D.SERIALS.items()}), (branch, serials)
        rows = [r for block in blocks(new, 'query') if block['kind'] == 'compare' for r in block['rows']]
        assert rows and all(r['state'] == '같음' for r in rows), (branch, [r for r in rows if r['state'] != '같음'])
        original = (new / 'output/graph.json').read_bytes()
        command(new, 'run.py', 'parts', '--no-open')
        assert original == (new / 'output/graph.json').read_bytes(), (branch, '같은 빈 틀로 다시 만든 모델이 다름')
        answers[branch] = {r['key']: r['cells'][0][1] for r in rows}
        records.append({'branch': branch, 'policy': B.policy(branch)[2:], 'nodes': len(graph['nodes']), 'relations': len(graph['rels']),
                        'model_equals_truth': True, 'repeat_equal': True, 'answers_same_rows': len(rows), 'answers': answers[branch]})
        if branch == 'A':
            records += field_damage(new, files)
            for label in ('duplicate-id', 'missing-endpoint', 'reverse-direction'):
                broken = copy.deepcopy(graph)
                if label == 'duplicate-id':
                    broken['nodes'].append(copy.deepcopy(broken['nodes'][0]))
                elif label == 'missing-endpoint':
                    broken['rels'][0]['b'] = 'missing-endpoint'
                else:
                    broken['rels'][0]['a'], broken['rels'][0]['b'] = broken['rels'][0]['b'], broken['rels'][0]['a']
                (new / 'output/graph.json').write_text(json.dumps(broken, ensure_ascii=False), encoding='utf-8')
                out = command(new, 'run.py', 'check', '--no-open', ok=False)
                assert '구조 확인 필요' in out, out
                command(new, 'run.py', 'parts', '--no-open')
                command(new, 'run.py', 'check', '--no-open')
                assert (new / 'output/graph.json').read_bytes() == original
                records.append({'broken': label, 'rejected': True, 'parts_then_check_recovers': True})
    # 결정 지점마다: 그 지점만 다른 두 갈래의 답이 실제로 다르다(같으면 결정 지점이 아니다)
    for point, index in (('구성 요소 자리와 그 실물', 2), ('같은 물리량의 범위', 3)):
        for x, y in (('A', 'B'), ('A', 'C'), ('C', 'E'), ('B', 'E')):
            px, py = B.policy(x), B.policy(y)
            if px[index] != py[index] and all(px[i] == py[i] for i in (2, 3) if i != index):
                changed = sorted(k for k in set(answers[x]) | set(answers[y]) if answers[x].get(k) != answers[y].get(k))
                assert changed, (point, x, y, '갈래가 달라도 답이 같음')
                records.append({'decision': point, 'branches': [x, y], 'changed_answers': {k: [answers[x].get(k), answers[y].get(k)] for k in changed}})
    return records


def field_damage(folder, files):
    """빈 틀과 원자료를 일부러 망가뜨린다 — 제공 코드가 그 줄을 짚고 멈추는지(또는 잇지 않고 화면에 보이는지)."""
    out = []
    rel = P.convert(files['결과/관계.csv'])
    rules = P.convert(files['결과/quantity_rules.py'])
    (gone, now, _), = A.removed_rows()
    stops = {
        'cardinality-too-tight': ('app/features/relations.csv', rel.replace('설비-구성 요소,HAS_COMPONENT,설비,1:N', '설비-구성 요소,HAS_COMPONENT,설비,1:1'), 'names', 'relations.csv:3: HAS_COMPONENT 카디널리티 1:1'),
        'cardinality-unknown': ('app/features/relations.csv', rel.replace('센서-물리량,OBSERVES,센서,N:1', '센서-물리량,OBSERVES,센서,여럿'), 'design', '카디널리티 「여럿」'),
        'past-unit-without-split': ('app/features/row_rules.csv', P.convert(files['결과/행_처리.csv']).replace(',빼기,', f',지난 실물:{now},'), 'names', '「지난 실물」은 구성 요소 자리와 그 실물을 나눌 때'),
        'removed-row-not-handled': ('app/features/row_rules.csv', '\n'.join(P.convert(files['결과/행_처리.csv']).split('\n')[:2]) + '\n', 'names', f'components.csv:{now}: 식별자 「'),
        'quantity-name-collision': ('app/features/quantity_rules.py', rules.replace("    return value_kind(members[0])\n", "    return '온도'\n"), 'quantities', '같은 물리량 이름 「온도」'),
        'units-mixed-in-one-quantity': ('app/features/quantity_rules.py', rules.replace('    return value_kind(a) == value_kind(b)', '    return True'), 'quantities', '바꾸는 법을 모릅니다'),
        'empty-decision': ('app/features/decisions.csv', '\n'.join('같은 물리량의 범위,,,' if x.startswith('같은 물리량의 범위,') else x for x in P.convert(files['결과/정한_것.csv']).split('\n')),
                           'quantities', 'decisions.csv:'),
    }
    for name, (path, broken, action, want) in stops.items():
        target = folder / path
        original = target.read_bytes()
        assert broken != original.decode('utf-8'), (name, '손상이 적용되지 않음')
        target.write_text(broken, encoding='utf-8', newline='\n')
        try:
            text = command(folder, 'run.py', action, '--no-open', ok=False)
            assert want in text, (name, text[-600:])
        finally:
            target.write_bytes(original)
        if name == 'empty-decision':
            assert '같은 물리량의 범위' in text, text[-600:]
        out.append({'damage': name, 'stopped_with': want})
    # 교차표에 없는 표기: 짐작해 잇지 않고 「사내 품번을 찾지 못한 교체부품 칸」에 보인다. 그 부품의 사용 설비에서 그 설비가 빠져 대조가 「다름」이 된다.
    target = folder / 'data/components.csv'
    original = target.read_bytes()
    assert original.count(b',RF-10,') == 1
    target.write_bytes(original.replace(b',RF-10,', b',RF-99,'))
    try:
        lost = next(b for b in blocks(folder, 'parts') if b['kind'] == 'table' and '찾지 못한' in b['title'])
        assert len(lost['rows']) == 1 and 'RF-99' in json.dumps(lost['rows'], ensure_ascii=False), lost
        states = [r['state'] for b in blocks(folder, 'query') if b['kind'] == 'compare' for r in b['rows']]
        assert '다름' in states, states
    finally:
        target.write_bytes(original)
    out.append({'damage': 'part-code-not-in-alias-table', 'shown_unlinked': 1, 'answer_marked_different': True})
    command(folder, 'run.py', 'parts', '--no-open')
    return out


def fresh_packages(starter, work):
    records = []
    with zipfile.ZipFile(starter.with_suffix('.zip')) as archive:
        archive.extractall(work / 'received')
    folder = work / 'received' / starter.name
    assert not (folder / 'output').exists()
    command(folder, 'run.py', '--no-open')
    data = json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))
    assert data['action'] == 'sources' and data['blocks']
    assert not any(block['kind'] == 'error' for block in data['blocks'])
    # 받은 그대로는 빈 틀이 비어 있어, 모델을 만드는 기능이 채울 파일을 짚고 멈춘다(빈 틀을 실행된 것처럼 보이지 않는다)
    stopped = command(folder, 'run.py', 'names', '--no-open', ok=False)
    assert 'app/features/design.csv' in stopped, stopped[-400:]
    records.append({'fresh_starter': True, 'first_command': 'python run.py --no-open', 'actual_blocks': len(data['blocks']), 'blank_feature_stops': True})
    archive = starter.parent / (starter.name + '-completed.zip')
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            z.extractall(work / 'received-completed')
        folder = work / 'received-completed' / starter.name
        before = {name: (folder / 'output' / name).read_bytes() for name in ('graph.json', 'schema.json')}
        for action in ('parts', 'query', 'check'):
            command(folder, 'run.py', action, '--no-open')
        assert all((folder / 'output' / name).read_bytes() == data for name, data in before.items())
        records.append({'fresh_completed': True, 'regenerated_models_equal': True, 'check': 'pass'})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    base = (ROOT / '작업/검사/session2-projects').resolve()
    base.mkdir(parents=True, exist_ok=True)
    with D.for_course('통합반'), tempfile.TemporaryDirectory(prefix='trials-', dir=base) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(base) and work != base
        records = ontology(args.folder.resolve(), work)
        records += fresh_packages(args.folder.resolve(), work)
        report = base / 'ontology-results.json'
        report.write_text(json.dumps({'kind': '강사 참조 실행; 학생 AI 시험 아님', 'records': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 실행 대조 통과: {report}')


if __name__ == '__main__':
    main()
