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
    for branch in ('A', 'B', 'C'):
        new = work / ('new-' + branch)
        legacy = work / ('old-' + branch)
        shutil.copytree(starter, new, ignore=shutil.ignore_patterns('__pycache__', 'output'))
        shutil.copytree(old, legacy, ignore=shutil.ignore_patterns('__pycache__'))
        files = A.integrated_design(branch)
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        files['결과/기대_답.csv'] = B.expect_design_text()
        put(new, files, True)
        put(legacy, files)
        command(legacy, '-c', "import model_tool; model_tool.build('부품')")
        actions = ['sources', 'expected', 'design', 'names', 'quantities', 'units', 'parts', 'query', 'check'] if branch == 'A' else ['parts', 'check']
        for action in actions:
            out = command(new, 'run.py', action, '--no-open')
            (work / f'{branch}-{action}.txt').write_text(out, encoding='utf-8')
        for name in ('schema.json', 'graph.json'):
            expected = json.loads(P.convert((legacy / '결과' / name).read_text(encoding='utf-8')))
            actual = json.loads((new / 'output' / name).read_text(encoding='utf-8'))
            assert actual == expected, (branch, name, '이전 전후 불일치')
        original = (new / 'output/graph.json').read_bytes()
        command(new, 'run.py', 'parts', '--no-open')
        assert original == (new / 'output/graph.json').read_bytes()
        graph = json.loads(original)
        records.append({'branch': branch, 'nodes': len(graph['nodes']), 'relations': len(graph['rels']), 'legacy_equal': True, 'repeat_equal': True})
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
