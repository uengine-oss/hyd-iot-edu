"""새 통합02 프로젝트를 실제 실행해 경로 이전 전후 결과와 오류 검출을 대조한다. AI 호출 없음."""
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
from lab_package import ROOT


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


def ontology(starter, work):
    records = []
    # 옛 산출물 폴더를 지운 뒤에도 동일한 계산 원본으로 이전 전 대조를 재현한다.
    old = work / 'legacy-fixture'
    old.mkdir()
    D.write_sources(old / '자료')
    shutil.copyfile(HERE / 'session2_model_tool.py', old / 'model_tool.py')
    put(old, {name: text for name, text in B.design_integrated()['files'].items() if name.startswith('결과/')})
    for branch in B.REFERENCE_BRANCHES['통합반']:
        new = work / ('new-' + branch)
        legacy = work / ('old-' + branch)
        shutil.copytree(starter, new, ignore=shutil.ignore_patterns('__pycache__', 'output'))
        shutil.copytree(old, legacy, ignore=shutil.ignore_patterns('__pycache__'))
        files = A.integrated_design(branch)
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        files['결과/기대_답.csv'] = B.expect_design_text(branch)
        put(new, files, True)
        put(legacy, files)
        command(legacy, '-c', "import model_tool; model_tool.build('부품')")
        actions = ['sources', 'expected', 'design', 'names', 'quantities', 'units', 'parts', 'query', 'check'] if branch in ('A', 'D') else ['parts', 'query', 'check']
        for action in actions:
            out = command(new, 'run.py', action, '--no-open')
            (work / f'{branch}-{action}.txt').write_text(out, encoding='utf-8')
        for name in ('schema.json', 'graph.json'):
            expected = json.loads(P.convert((legacy / '결과' / name).read_text(encoding='utf-8')))
            actual = json.loads((new / 'output' / name).read_text(encoding='utf-8'))
            assert actual == expected, (branch, name, '이전 전후 불일치')
        # 갈래마다 정답 보기대로 채운 모델의 답이 그 갈래의 기대 답(강사 참조 모델에서 뽑은 것)과 줄마다 같다(K-14 ③)
        command(new, 'run.py', 'query', '--no-open')
        result = json.loads((new / 'output/result.json').read_text(encoding='utf-8'))
        rows = [r for block in result['blocks'] if block['kind'] == 'compare' for r in block['rows']]
        assert rows and all(r['state'] == '같음' for r in rows), (branch, [r for r in rows if r['state'] != '같음'])
        original = (new / 'output/graph.json').read_bytes()
        command(new, 'run.py', 'parts', '--no-open')
        assert original == (new / 'output/graph.json').read_bytes()
        graph = json.loads(original)
        records.append({'branch': branch, 'nodes': len(graph['nodes']), 'relations': len(graph['rels']), 'legacy_equal': True, 'repeat_equal': True,
                        'answers_same_rows': len(rows), 'answers': {r['key']: r['cells'][0][1] for r in rows}})
        if branch == 'A':
            records += new_field_damage(new, files)
        if branch == 'A':
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
            (new / 'output/graph.json').write_bytes(original)
            command(new, 'run.py', 'query', '--no-open')
            result = json.loads((new / 'output/result.json').read_text(encoding='utf-8'))
            assert all(r['state'] == '같음' for block in result['blocks'] if block['kind'] == 'compare' for r in block['rows'])
    return records


def new_field_damage(folder, files):
    """새 칸 손상: 카디널리티를 원자료보다 좁게 적기 · 없는 카디널리티 · 실물 없이 지난 실물 · 물리량 이름 겹침 · 없는 후보 품번 — 제공 코드가 줄을 짚고 멈추는지."""
    out = []
    rel = P.convert(files['결과/관계.csv'])
    cases = {
        'cardinality-too-tight': ('app/features/relations.csv', rel.replace('설비-구성 요소,HAS_COMPONENT,설비,1:N', '설비-구성 요소,HAS_COMPONENT,설비,1:1'), 'names', 'names',
                                  'relations.csv:3: HAS_COMPONENT 카디널리티 1:1'),
        'cardinality-unknown': ('app/features/relations.csv', rel.replace('센서-물리량,OBSERVES,센서,N:1', '센서-물리량,OBSERVES,센서,여럿'), 'design', 'design', '카디널리티 「여럿」'),
        'past-unit-without-split': ('app/features/row_rules.csv', P.convert(files['결과/행_처리.csv']).replace(',빼기,', ',지난 실물:17,'), 'names', 'names', '「지난 실물」은 구성 요소 자리와 그 실물을 나눌 때'),
        'quantity-name-collision': ('app/features/quantity_rules.py', P.convert(files['결과/quantity_rules.py']).replace("    names = [m['재는것'] for m in members]", "    return '온도'\n    names = [m['재는것'] for m in members]"), 'quantities', 'quantities', '같은 물리량 이름 「온도」'),
        'empty-decision': ('app/features/decisions.csv', '\n'.join('같은 물리량의 범위,,,' if x.startswith('같은 물리량의 범위,') else x for x in P.convert(files['결과/정한_것.csv']).split('\n')),
                           'quantities', 'quantities', 'decisions.csv:'),
        'candidate-unknown-part': ('app/features/part_rules.py', P.convert(files['결과/part_rules.py']).replace("    if len(hits) == 1:\n        return hits[0]", "    if not cell:\n        return ['P-NOT-IN-LIST']\n    if len(hits) == 1:\n        return hits[0]"), 'parts', 'parts', '확인 필요 후보'),
    }
    for name, (path, broken, _, action, want) in cases.items():
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
            assert '같은 물리량의 범위' in text and 'AI가 대신 고르지 않습니다' in text, text[-600:]
        out.append({'new_field_damage': name, 'stopped_with': want})
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
    records.append({'fresh_starter': True, 'first_command': 'python run.py --no-open', 'actual_blocks': len(data['blocks'])})
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
    with tempfile.TemporaryDirectory(prefix='trials-', dir=base) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(base) and work != base
        records = ontology(args.folder.resolve(), work)
        records += fresh_packages(args.folder.resolve(), work)
        report = base / 'ontology-results.json'
        report.write_text(json.dumps({'kind': '강사 코드 실행·이전 대조; 학생 AI 시험 아님', 'records': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 실행 대조 통과: {report}')


if __name__ == '__main__':
    main()
