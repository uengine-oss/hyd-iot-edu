"""운전 전제·출처 연결 고침을 원자료와 무모델 함수 실행으로 확인한다.

python verify_conditions.py --lab <동결 실행 폴더> --actual-state <실제 state.json> --out <작업 판정 폴더>
기존 관측 색인은 읽기 전용으로 연다. 원 실행·학생 폴더에는 쓰지 않는다.
"""
from pathlib import Path
import argparse
import copy
import csv
import gzip
import hashlib
import json
import sqlite3
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from agent_tools.evidence import EvidenceStore
from agent_tools.runner import structural_errors
from run_reference import dump, ledger_for, load_policy


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_check(root, result, tag):
    """집계 반환과 별도로 압축 원자료에서 같은 조건을 골라 숫자를 대조한다."""
    values = []; rows = []; source_lines = []
    for source in result['source_files']:
        with gzip.open(root / source, 'rt', encoding='utf-8-sig', newline='') as stream:
            next(stream)
            for number, row in enumerate(csv.DictReader(stream), 3):
                if row['asset'] != result['asset'] or not result['start_exclusive'] < row['observed_at'] <= result['end_inclusive']: continue
                filters = result['filters']
                if filters.get('state') is not None and row['state'] != filters['state']: continue
                if filters.get('load_pct') is not None and float(row['load_pct']) != filters['load_pct']: continue
                rows.append(row)
                if row['quality'] == 'good' and row[tag] != '':
                    values.append(float(row[tag])); source_lines.append({'file': source, 'line': number})
    stats = result['statistics'][tag]
    assert len(rows) == result['row_count'] and len(values) == stats['count']
    mean = sum(values) / len(values) if values else None
    assert mean is None and stats['mean'] is None or mean is not None and abs(mean - stats['mean']) < 1e-9
    return {'tag': tag, 'count': len(values), 'mean': mean, 'source_rows': [source_lines[0], source_lines[-1]] if source_lines else [],
            'load_pct': sorted({row['load_pct'] for row in rows}), 'states': sorted({row['state'] for row in rows})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lab', type=Path, required=True)
    parser.add_argument('--actual-state', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); root = args.lab.resolve(); args.out.mkdir(parents=True, exist_ok=True)
    actual = json.loads(args.actual_state.read_text(encoding='utf-8-sig'))
    protected = json.loads((root / 'provided_manifest.json').read_text(encoding='utf-8-sig'))
    paths = [root / name for name in protected] + [args.actual_state, args.actual_state.with_name('root_plan.json'), root / '결과/policy.py', root / '결과/observation_index.sqlite']
    paths += [root / turn['record'] for turn in actual['turns']]
    unchanged = {str(path): sha(path) for path in paths}
    store = EvidenceStore(root)
    store.connection = sqlite3.connect((root / '결과/observation_index.sqlite').as_uri() + '?mode=ro', uri=True)
    assert store.connection.execute('SELECT source_hash FROM metadata').fetchone()[0] == sha(root / '자료/data_manifest.json')
    policies = {branch: load_policy(args.out / (branch + '_policy.py'), branch) for branch in ['partial', 'bundle']}
    expected = {
        'ALT-hyd02-0172-54a5': ['해당 없음', '충족', '해당 없음'],
        'OBS-HYD-03-000': ['보류', '보류', '보류'],
        'ALT-hyd03-0289-060b': ['보류', '보류', '보류'],
        'ALT-hyd03-0280-beaf': ['해당 없음', '충족', '해당 없음'],
        'ALT-hyd03-0294-4bf7': ['보류', '보류', '보류'],
        'ALT-hyd03-0305-aa1f': ['보류', '보류', '보류'],
        'ALT-hyd03-0306-fba5': ['보류', '보류', '보류'],
    }
    cases = []; stored = {}
    for identity, wanted in expected.items():
        request = store.request(identity); ledger = ledger_for(store, request, policies['partial']); stored[identity] = (request, ledger)
        raw = [raw_check(root, entry['result'], tag) for entry in ledger if entry['tool'] == 'observations' for tag in entry['result']['statistics']]
        for branch, policy in policies.items():
            plan = policy.build_plan(request, ledger, {'summary': '원자료의 직접 도구 조회 뒤 함수 검증. 모델 호출 아님.'})
            assert not structural_errors(plan, ledger)
            assert [row['status'] for row in plan['candidates']] == wanted, (identity, branch, plan)
            for candidate in plan['candidates']:
                assert candidate['assessment']['knowledge_sources']
                assert candidate['assessment']['application_sources'][0]['line'] == 26
                assert candidate['assessment']['condition_result'] is None if candidate['status'] == '보류' else candidate['assessment']['condition_result'] is not None
            dump(args.out / branch / (identity + '.json'), {'method': '직접 도구 조회·무모델 함수 실행', 'request': request, 'ledger': ledger, 'plan': plan, 'raw_checks': raw})
            cases.append({'request': identity, 'branch': branch, 'candidate_states': wanted, 'checks': len(plan['next_checks']),
                          'unresolved': len(plan['unresolved']), 'values': [c['assessment']['observations'] for c in plan['candidates']]})
    for identity in ['OBS-HYD-03-000', 'ALT-hyd03-0289-060b']:
        counts = {row['branch']: row['checks'] for row in cases if row['request'] == identity}
        assert counts['partial'] > counts['bundle'] == 1

    # 원 실제 응답은 불변. 현재 반환만으로 가능한 것과 직접 원문 조회 보완을 구분한다.
    policy = policies['partial']; original = copy.deepcopy(actual['ledger'])
    old_only = policy.build_plan(actual['request'], original, actual['plan']['model_summary'])
    assert all(c['status'] == '보류' for c in old_only['candidates'])
    assert all(not c['assessment']['application_sources'] for c in old_only['candidates'])
    assert all(c['assessment']['knowledge_sources'] for c in old_only['candidates'])
    supplement = {'id': 'F001', 'tool': 'document', 'arguments': {'doc_id': 'HM-8', 'revision': '1.1', 'section': 'HM-8.3'},
                  'status': 'ok', 'method': '검토자의 추가 원문 조회; 원 모델 호출 아님'}
    supplement['result'] = store.call(supplement['tool'], supplement['arguments'])
    supplemented = policy.build_plan(actual['request'], original + [supplement], actual['plan']['model_summary'])
    assert [row['status'] for row in supplemented['candidates']] == expected[actual['request']['request_id']]
    assert all({'T003', 'T009', 'F001'} <= set(c['evidence_refs']) for c in supplemented['candidates'])
    assert supplemented['model_summary'] == actual['plan']['model_summary']
    dump(args.out / 'existing_actual_derivation.json', {'method': '기존 실제 반환의 재판정과 별도 원문 조회 보완. 새 모델 실행 아님.',
         'actual_state_sha256': sha(args.actual_state), 'original_only': old_only, 'new_document_lookup': supplement, 'supplemented': supplemented})

    request, ledger = stored['ALT-hyd02-0172-54a5']; checks = []
    for kind in ['missing_stated_in', 'obsolete_knowledge', 'wrong_document_revision', 'missing_application_source', 'no_operating_proof']:
        damaged = copy.deepcopy(ledger)
        for entry in damaged:
            if entry['tool'] == 'graph_query':
                if kind == 'missing_stated_in': entry['result']['rels'] = [r for r in entry['result']['rels'] if r['type'] != 'STATED_IN']
                if kind == 'obsolete_knowledge':
                    for node in entry['result']['nodes']:
                        if 'Knowledge' in node['labels']: node['props']['doc_status'] = '폐기'
            if entry['tool'] == 'document' and kind == 'wrong_document_revision': entry['result']['document']['revision'] = '1.0'
            if entry['tool'] == 'document' and kind == 'missing_application_source': entry['result']['lines'] = [r for r in entry['result'].get('lines', []) if r['line'] != 26]
            if entry['tool'] == 'observations' and kind == 'no_operating_proof': entry['result']['filters'] = {'state': None, 'load_pct': None}
        if kind == 'no_operating_proof': damaged = [e for e in damaged if not (e['tool'] == 'history' and e['result'].get('source') == '자료/state_changes.csv')]
        plan = policy.build_plan(request, damaged, {})
        assert all(c['status'] == '보류' for c in plan['candidates']), kind
        checks.append({'kind': kind, 'method': '일부러 손상한 근거 계약 검사; 실제 사건 자료 아님', 'result': [c['status'] for c in plan['candidates']]})

    # 측정값0은 값없음이 아니다. 이 한 항목은 실제 관측을 꾸미지 않는 구조 단위검사다.
    observation = copy.deepcopy(next(e for e in ledger if e['tool'] == 'observations' and 'CE' in e['result']['statistics'] and e['result']['dataset'] == '1s'))
    for key in ['mean', 'min', 'max', 'first', 'last']: observation['result']['statistics']['CE'][key] = 0
    zero = policy.evidence_for([observation], 'CE', 30, request)
    assert zero['value_state'] == 'zero' and zero['valid']
    failed = {'id': 'F-ERROR', 'tool': 'observations', 'status': 'error', 'arguments': {'asset': request['asset'], 'tags': ['CE']}, 'error': '구조 검사 입력'}
    assert policy.evidence_for([failed], 'CE', 30, request)['value_state'] == 'query_failed'
    assert policy.evidence_for([], 'CE', 30, request)['value_state'] == 'not_queried'
    checks.append({'kind': 'zero_null_failure', 'method': '명시적 구조 단위검사. 0 관측 사례를 생성/추가하지 않음', 'zero': zero['value_state'], 'failed': 'query_failed', 'absent': 'not_queried'})
    store.connection.close()
    assert all(sha(Path(path)) == digest for path, digest in unchanged.items())
    report = {'model_calls': 0, 'method': '원자료 직접 조회·무모델 함수 검증', 'cases': cases, 'contract_checks': checks,
              'source_unchanged': True, 'source_sha256': unchanged,
              'reference_sha256': {p.name: sha(p) for p in [HERE / 'policy_common.py', HERE / 'run_reference.py', Path(__file__)]},
              'positive_coverage': {'cooler': ['ALT-hyd02-0172-54a5', 'ALT-hyd03-0280-beaf'],
                  'ambient': '미확인 — 기존 외기 양성 요청은70% 부하여서 보류로 변경. 원자료 수정 없음.',
                  'fan': '미확인 — 기존 팬 양성 요청은80%; 90% 요청은 최대 공백37초로 보류. 원자료 수정 없음.'},
              'original_actual': '기존 실제 반환만으로는 적용 원문26줄이 빠져 보류. 별도 직접 조회 F001을 명시해 보완하면 T009 운전 이력·T003 채택 지식 출처로 기본 판정 가능. 새 정책의 모델 조회 성공으로 세지 않음.'}
    dump(args.out / 'report.json', report)
    print(json.dumps({'cases': len(cases), 'contract_checks': len(checks), 'source_unchanged': True, 'model_calls': 0,
                      'positive_coverage': report['positive_coverage']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
