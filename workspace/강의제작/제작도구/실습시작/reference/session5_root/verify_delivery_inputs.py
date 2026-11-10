"""전달 요구 계약의 변경 영향을 실제 원자료·무모델 함수 실행으로 검증한다.

모델 실행의 대체 증거가 아니다. 작업 폴더에 만든 collection은 직접 조회 fixture라고 표시한다.
"""
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import csv
import gzip
import json
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from build_agent_labs import LAB, DEFAULT_REQUEST, reference_features, reference_choices
from run_reference import ledger_for


def main(out):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)
    project = out / 'project'
    if project.exists(): raise ValueError('이미 있는 시험 폴더를 덮어쓰지 않습니다.')
    shutil.copytree(LAB, project, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.env', 'output'))
    sys.path.insert(0, str(project))
    from app.utils import workflow as w
    from app.utils.evidence import EvidenceStore, read_json, sha
    store = EvidenceStore(project)
    began = time.perf_counter(); store.index(); index_seconds = time.perf_counter() - began
    feature = project / 'app/features'
    protected = {str(p): sha(p) for p in (project / 'data').rglob('*') if p.is_file()}
    snapshot = read_json(out.parent / '새구조_K3_입력경계.json')
    changed_data = [name for name, old in snapshot['raw_data_before'].items() if sha(LAB / name) != old]
    assert set(changed_data) == {'data/data_manifest.json', 'data/field_notes.md'}, changed_data
    assert store.manifest['default_request'] == DEFAULT_REQUEST
    original_requests = project / 'data/requests.csv'
    assert sha(original_requests) == snapshot['raw_data_before']['data/requests.csv']
    for name, content in reference_features('partial').items(): (feature / name).write_text(content, encoding='utf-8')
    for branch in ['partial', 'bundle']:
        target = out / 'reference_features' / branch; target.mkdir(parents=True)
        for name, content in reference_features(branch).items(): (target / name).write_text(content, encoding='utf-8')
        (target / 'choices.csv').write_text(reference_choices(branch), encoding='utf-8')
    query = w.feature(project, 'query', ['instructions', 'prepare_query'])
    cases = []; calls = []
    def no_model(messages):
        calls.append(True); raise AssertionError('새 모델 호출을 시도했습니다.')
    for identity in [DEFAULT_REQUEST, 'ALT-hyd02-0172-54a5']:
        request = store.request(identity); ledger = ledger_for(store, request, query)
        folder = w.folder_for(project, identity); collected = folder / 'collection.json'
        fixture = {'request': request, 'binding': w.collection_binding(project, store, request), 'status': 'collected',
                   'ledger': ledger, 'turns': [], 'model_history': [], 'model_report': None,
                   'method': '원자료의 직접 도구 조회 fixture. 실제 모델 응답 또는 수집 실행 기록이 아님.'}
        w.write_json(collected, fixture)
        assessed = w.assess(project, identity, store=store)
        source_hashes = {str(p): sha(p) for p in [collected, folder / 'assessment.json']}
        (feature / 'choices.csv').write_text('decision,choice,source,changed_action\n', encoding='utf-8')
        missing = w.deliver(project, identity, store=store)
        assert missing['delivery_status'] == 'needs_input' and not missing['next_checks'] and missing['delivery_questions']
        assert len(missing['candidates']) == 3 and not w.current_result(project, identity, store)['plan']['next_checks']
        w.show(project, identity, store=store)
        page = (project / 'output/result.html').read_text(encoding='utf-8')
        assert '전달 요구 확인 필요' in page and '다음 점검 계획이 아닙니다' in page
        child = subprocess.run([sys.executable, 'run.py', '--check', '--request', identity], cwd=project, capture_output=True, text=True, encoding='utf-8')
        assert child.returncode == 1 and '전달 요구가 미정' in child.stdout, child.stdout + child.stderr
        shutil.copyfile(project / 'output/result.html', out / (identity + '-missing.html'))
        branch_outputs = {}
        for branch in ['partial', 'bundle']:
            (feature / 'choices.csv').write_text(reference_choices(branch), encoding='utf-8')
            (feature / 'deliver.py').write_text(reference_features(branch)['deliver.py'], encoding='utf-8')
            current = w.current_result(project, identity, store)
            assert not current['plan']['next_checks']  # 옛 선택의 전달 결과를 현재로 쓰지 않음
            assert w.collect(project, identity, store=store, ask_model=no_model)['status'] == 'collected'
            result = w.deliver(project, identity, store=store)
            assert result['delivery_status'] == 'ready' and result['_provenance']['choices_sha256'] == sha(feature / 'choices.csv')
            assert result['delivery_choices'][0]['choice'] == w.delivery_choices(project)[0]['choice']
            assert all(sha(Path(p)) == value for p, value in source_hashes.items()) and not calls
            branch_outputs[branch] = result
            w.write_json(out / branch / (identity + '.json'), result)
            w.show(project, identity, store=store)
            shutil.copyfile(project / 'output/result.html', out / (identity + '-' + branch + '.html'))
        if identity == DEFAULT_REQUEST:
            assert [c['status'] for c in assessed['candidates']] == ['보류'] * 3
            assert {x['recipient'] for x in branch_outputs['partial']['next_checks']} == {'운전원', '설비보전팀'}
            assert len(branch_outputs['bundle']['next_checks']) == 1
            assert branch_outputs['bundle']['next_checks'][0]['recipient'] == '설비보전팀'
            assert branch_outputs['partial']['next_checks'] != branch_outputs['bundle']['next_checks']
        else:
            assert [c['status'] for c in assessed['candidates']] == ['해당 없음', '충족', '해당 없음']
            assert branch_outputs['partial']['next_checks'] == branch_outputs['bundle']['next_checks']
        original_delivery = sha(feature / 'deliver.py')
        text = (feature / 'choices.csv').read_text(encoding='utf-8').replace('32-34', '33-34')
        (feature / 'choices.csv').write_text(text, encoding='utf-8')
        assert not w.current_result(project, identity, store)['plan']['next_checks']
        corrected_source = w.deliver(project, identity, store=store)
        assert corrected_source['_provenance']['choices_sha256'] == sha(feature / 'choices.csv')
        assert sha(feature / 'deliver.py') == original_delivery
        assert all(sha(Path(p)) == value for p, value in source_hashes.items()) and not calls
        cases.append({'request': request, 'candidate_states': [x['status'] for x in assessed['candidates']],
                      'missing_choice_check_exit': child.returncode, 'collection_assessment_unchanged': True,
                      'source_only_change_recomputed_delivery': True, 'old_delivery_excluded': True,
                      'branches': {b: {'checks': p['next_checks'], 'choices': p['delivery_choices'], 'provenance': p['_provenance']} for b, p in branch_outputs.items()}})
    # 새 주 입력의 수치와 적용 조건을 모델 전에 직접 원천 CSV로 고정한다.
    request = store.request(DEFAULT_REQUEST); end = datetime.fromisoformat(request['as_of'])
    beginning = (end - timedelta(seconds=120)).isoformat(); source = project / 'data/observations/hyd_03_1s.csv.gz'
    with gzip.open(source, 'rt', encoding='utf-8-sig', newline='') as stream:
        next(stream); rows = [(i, row) for i, row in enumerate(csv.DictReader(stream), 3) if beginning < row['observed_at'] <= request['as_of']]
    raw = {}
    for tag, seconds in [('CE', 30), ('VS1', 120), ('TS4', 120), ('TS1', 60)]:
        start = (end - timedelta(seconds=seconds)).isoformat()
        selected = [(i, r) for i, r in rows if start < r['observed_at'] and r['quality'] == 'good' and r[tag] != '']
        vals = [float(r[tag]) for _, r in selected]
        raw[tag] = {'seconds': seconds, 'count': len(vals), 'mean': sum(vals)/len(vals) if vals else None,
                    'source_lines': [selected[0][0], selected[-1][0]] if selected else [],
                    'load_pct': sorted({r['load_pct'] for _, r in selected}), 'states': sorted({r['state'] for _, r in selected})}
    assert raw['CE']['count'] == 30 and abs(raw['CE']['mean'] - 44.748) < 1e-8
    assert raw['VS1']['count'] == 120 and all(x['load_pct'] == ['80.0'] for x in raw.values())
    assert not [r for _, r in rows if float(r['load_pct']) == 90]
    expected = {'request': request, 'model_calls': 0, 'frozen_before_new_model': True, 'raw_source': str(source.relative_to(project)),
                'raw_sha256': sha(source), 'raw_values': raw, 'condition_90_rows': 0,
                'expected_states': ['보류'] * 3, 'reason': 'HM-8.3:26의 부하90% 조건에 맞는 현재 창 관측이 없다. 무필터 수치가 임계값에 맞아도 원인 조건 충족으로 쓰지 않는다.',
                'branches': cases[0]['branches'], 'transfer_candidate': 'ALT-hyd02-0172-54a5',
                'transfer_expected': ['해당 없음', '충족', '해당 없음']}
    w.write_json(out / '새주입력_모델전기대.json', expected)
    assert all(sha(Path(p)) == value for p, value in protected.items())
    assert all(sha(Path(p)) == value for p, value in snapshot['frozen_external'].items())
    invalid = ['decision,choice,source,changed_action\ndeliver,선택,,행동\n', 'decision,choice,source,changed_action\n다른키,선택,근거,행동\n']
    failures = []
    for text in invalid:
        (feature / 'choices.csv').write_text(text, encoding='utf-8')
        try: w.delivery_choices(project)
        except ValueError as error: failures.append(str(error))
        else: raise AssertionError('잘못된 전달 입력을 받음')
    report = {'model_calls': 0, 'method': '원자료 직접 조회 fixture와 실제 후처리 함수·자식 프로세스 실행. 새 모델 수행 기록 아님.',
              'index_seconds': round(index_seconds, 3), 'cases': cases, 'new_default': DEFAULT_REQUEST, 'changed_metadata': changed_data,
              'raw_values_unchanged': True, 'frozen_external_unchanged': True, 'raw_source_sha256': sha(source),
              'invalid_choice_errors': failures, 'package_sha256': sha(LAB.with_suffix('.zip')),
              'source_hashes': {str(p.relative_to(project)): sha(p) for p in [project / 'app/utils/workflow.py', project / 'app/utils/contracts.py', project / 'app/ui/render.py']}}
    w.write_json(out / 'report.json', report)
    print(json.dumps({'cases': len(cases), 'model_calls': 0, 'new_default': DEFAULT_REQUEST, 'raw_values_unchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
