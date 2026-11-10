"""실제 계정 수집·판정의 바이트를 유지하며 전달 입력 변경만 검증한다. 모델 호출0."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from build_agent_labs import reference_features, reference_choices


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main(source, out):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists(): raise ValueError('새 시험 폴더를 지정합니다.')
    out.mkdir(parents=True); project = out / 'project'
    def included(path):
        return path.is_file() and path.name != '.env' and path.suffix not in ['.sqlite', '.pyc'] and '__pycache__' not in path.parts
    protected = {str(p): sha(p) for p in source.rglob('*') if included(p)}
    shutil.copytree(source, project, ignore=shutil.ignore_patterns('.env', '*.sqlite', '*.pyc', '__pycache__', '.folder_mark'))
    sys.path.insert(0, str(project))
    from app.utils import workflow as w
    from app.utils.evidence import EvidenceStore, read_json
    store = EvidenceStore(project); identity = store.manifest['default_request']
    folder = w.folder_for(project, identity); collected, assessed = folder / 'collection.json', folder / 'assessment.json'
    originals = {p.relative_to(project).as_posix(): sha(p) for p in [collected, assessed]}
    state, assessment, _, _ = w.require_assessment(project, identity, store)
    for turn in state['turns']:
        p = project / turn['record']; originals[turn['record']] = sha(p)
    assert len(state['turns']) == 7 and len(state['ledger']) == 22
    assert all(c['status'] == '보류' for c in assessment['candidates'])
    original_plan = read_json(folder / 'root_plan.json')
    assert original_plan['delivery_status'] == 'ready' and len(original_plan['next_checks']) == 4
    feature = project / 'app/features'; cases = []; calls = []
    def forbidden(messages): calls.append(True); raise AssertionError('새 모델 호출 경로')
    def command(action):
        r = subprocess.run([sys.executable, 'run.py', '--'+action, '--request', identity], cwd=project, capture_output=True, text=True, encoding='utf-8')
        return {'action': action, 'exit': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}
    def unchanged():
        assert not calls and all(sha(project/name) == expected for name, expected in originals.items())
        assert all(sha(Path(name)) == expected for name, expected in protected.items())
    (feature / 'choices.csv').write_text('decision,choice,source,changed_action\n', encoding='utf-8')
    current = w.current_result(project, identity, store)
    assert not current['plan']['next_checks'] and len(current['plan']['candidates']) == 3
    missing = w.deliver(project, identity, store=store)
    assert missing['delivery_status'] == 'needs_input' and missing['delivery_questions'] and not missing['next_checks']
    check = command('check'); assert check['exit'] == 1 and '전달 요구가 미정' in check['stdout']
    assert command('show')['exit'] == 0
    shutil.copyfile(project / 'output/result.html', out / 'missing.html')
    unchanged(); cases.append({'case': '선택 누락', 'checks': 0, 'candidates': 3, 'validation': check})
    # 방침이 바뀐 실제 요구와 그 방침을 구현한 함수를 함께 반영한다. 자연어를 일반 코드가 정답 enum으로 바꾸지 않는다.
    (feature / 'choices.csv').write_text(reference_choices('bundle'), encoding='utf-8')
    (feature / 'deliver.py').write_text(reference_features('bundle')['deliver.py'], encoding='utf-8')
    assert not w.current_result(project, identity, store)['plan']['next_checks']
    w.collect(project, identity, store=store, ask_model=forbidden)
    bundle = w.deliver(project, identity, store=store)
    assert bundle['delivery_status'] == 'ready' and len(bundle['next_checks']) == 1 and bundle['next_checks'][0]['recipient'] == '설비보전팀'
    assert bundle['_provenance']['choices_sha256'] == sha(feature / 'choices.csv')
    assert command('show')['exit'] == 0
    shutil.copyfile(project / 'output/result.html', out / 'bundle.html')
    check = command('check'); assert check['exit'] == 0
    unchanged(); cases.append({'case': '묶음 전달 요구와 구현', 'result': bundle, 'validation': check})
    delivery_code = sha(feature / 'deliver.py')
    text = (feature / 'choices.csv').read_text(encoding='utf-8').replace('32-34', '33-34')
    (feature / 'choices.csv').write_text(text, encoding='utf-8')
    invalidated = w.current_result(project, identity, store)
    assert not invalidated['plan']['next_checks'] and invalidated['previous']
    w.collect(project, identity, store=store, ask_model=forbidden)
    updated = w.deliver(project, identity, store=store)
    assert updated['_provenance']['choices_sha256'] != bundle['_provenance']['choices_sha256']
    assert updated['next_checks'] == bundle['next_checks'] and sha(feature / 'deliver.py') == delivery_code
    assert command('show')['exit'] == 0 and command('check')['exit'] == 0
    unchanged(); cases.append({'case': '출처만 정정', 'old_plan_excluded': True, 'new_choices_sha256': updated['_provenance']['choices_sha256'], 'deliver_code_unchanged': True})
    report = {'source': str(source), 'project': str(project), 'model_calls': 0, 'source_unchanged': True,
              'actual_response_count': len(state['turns']), 'actual_tool_count': len(state['ledger']),
              'collection_assessment_responses_unchanged': originals, 'source_hashes': protected,
              'cases': cases, 'method': '실제 계정 수집/판정 사본으로 전달만 무모델 재계산. 실제 학생 선택·새 모델 수행 아님.'}
    w.write_json(out / 'report.json', report)
    print(json.dumps({'cases': len(cases), 'model_calls': 0, 'source_unchanged': True, 'actual_responses_preserved': 7}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--source', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); main(args.source, args.out)
