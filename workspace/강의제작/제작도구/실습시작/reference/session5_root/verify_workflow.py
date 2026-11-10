"""보존된 실제 반환으로 후처리 재사용·판본 혼재를 검증한다. 모델 호출 없음."""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from agent_tools import workflow as w
from agent_tools.evidence import EvidenceStore, read_json, sha
from build_agent_labs import reference_features, reference_choices


def main(actual, student, out):
    out.mkdir(parents=True, exist_ok=True)
    root = out / 'project'; features = root / 'app/features'; features.mkdir(parents=True, exist_ok=True)
    identity = 'ALT-hyd02-0172-54a5'
    actual_path = actual / '결과/runs' / identity / 'state.json'
    state = read_json(actual_path)
    protected = [actual_path, actual / '결과/policy.py'] + [actual / t['record'] for t in state['turns']]
    old = {str(p): sha(p) for p in protected}
    text = (actual / '결과/policy.py').read_text(encoding='utf-8-sig')
    tree = ast.parse(text)
    query = 'from datetime import datetime, timedelta\n\n' + '\n\n'.join(ast.get_source_segment(text, n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ['instructions', 'prepare_query'])
    (features / 'query.py').write_text(query, encoding='utf-8')
    common = (HERE / 'policy_common.py').read_text(encoding='utf-8')
    wrapper = '\ndef assess(request, ledger):\n    value = compose(request, ledger, {}, lambda c,u,s: ([], "검증"))\n    value["safety_refs"] = list(dict.fromkeys(e["id"] for e in ledger if e["tool"]=="document" and e["status"]=="ok" and e["result"].get("document",{}).get("doc_id")=="SR-04"))\n    return {k:value[k] for k in ["candidates","unresolved","safety_refs","safety"]}\n'
    (features / 'assess.py').write_text(common + wrapper, encoding='utf-8')
    def delivery(branch):
        (features / 'deliver.py').write_text(reference_features(branch)['deliver.py'], encoding='utf-8')
        (features / 'choices.csv').write_text(reference_choices(branch), encoding='utf-8')
    delivery('partial')
    store = EvidenceStore(actual)
    turns = []
    for turn in state['turns']:
        target = root / 'output/model_responses' / Path(turn['record']).name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(actual / turn['record'], target)
        turns.append(dict(turn, record=target.relative_to(root).as_posix(), record_sha256=sha(target)))
    folder = w.folder_for(root, identity)
    collected = {'request': state['request'], 'binding': w.collection_binding(root, store, state['request']), 'status': 'collected', 'ledger': state['ledger'], 'turns': turns, 'model_history': state['model_history'], 'model_report': state['plan']['model_summary'], 'origin': '보존된 실제 반환을 새 계약에 연결한 무모델 검증 fixture. 새 수집 실행 기록이 아님.'}
    path = folder / 'collection.json'; w.write_json(path, collected); initial = sha(path)
    calls = []
    def denied(messages):
        calls.append(len(messages)); raise RuntimeError('무모델 검증: 새 호출 경로에서 중단')
    assert w.collect(root, identity, store=store, ask_model=denied)['status'] == 'collected'
    assessed = w.assess(root, identity, store=store)
    assert all(c['status'] == '보류' for c in assessed['candidates'])  # 실제 반환에 적용 원문 26줄 없음
    partial = w.deliver(root, identity, store=store)
    assert len(partial['next_checks']) == len(assessed['unresolved']) and len(partial['next_checks']) > 1
    delivery('bundle'); assert not w.current_result(root, identity, store)['plan']['next_checks']
    bundle = w.deliver(root, identity, store=store)
    assert len(bundle['next_checks']) == 1 and sha(path) == initial and not calls
    (features / 'assess.py').write_text(common + wrapper + '\n# 후처리 판만 변경\n', encoding='utf-8')
    assert w.current_result(root, identity, store)['plan'] is None
    w.collect(root, identity, store=store, ask_model=denied); w.assess(root, identity, store=store); w.deliver(root, identity, store=store)
    assert sha(path) == initial and not calls
    w.show(root, identity, store=store); shutil.copyfile(root / 'output/result.html', out / 'assess_deliver.html')
    (features / 'query.py').write_text(query + '\n# 조회 판 변경\n', encoding='utf-8')
    current = w.current_result(root, identity, store)
    assert current['plan'] is None and current['ledger'] == []
    try: w.assess(root, identity, store=store)
    except ValueError as error: assert '판이 다릅니다' in str(error)
    else: raise AssertionError('조회 판이 달라도 판정 실행됨')
    try: w.collect(root, identity, store=store, ask_model=denied)
    except RuntimeError: pass
    else: raise AssertionError('새 수집 필요 경로에 도달하지 않음')
    assert len(calls) == 1 and not (folder / 'root_plan.json').exists()
    alt = 'ALT-hyd03-0289-060b'; student_state = student / '결과/runs' / alt / 'state.json'
    student_plan = student / '결과/runs' / alt / 'root_plan.json'
    protected += [student_state, student_plan]; old.update({str(p): sha(p) for p in [student_state, student_plan]})
    observed = read_json(student_state); alt_folder = w.folder_for(root, alt)
    assert observed['status'] != '완료' and observed['ledger'] and not observed.get('plan')
    fixture = {'request': observed['request'], 'binding': w.collection_binding(root, store, observed['request']), 'status': 'collecting', 'ledger': observed['ledger'], 'turns': [], 'model_history': observed['model_history'], 'origin': '실제 미완료 상태와 이전 계획 혼재 조건의 무모델 재현'}
    w.write_json(alt_folder / 'collection.json', fixture); shutil.copyfile(student_plan, alt_folder / 'root_plan.json')
    current = w.current_result(root, alt, store)
    assert current['plan'] is None and current['ledger'] == observed['ledger'] and current['previous']
    w.show(root, alt, store=store); html = (root / 'output/result.html').read_text(encoding='utf-8')
    assert 'id="candidates"' not in html and 'id="checks"' not in html and '이전판 점검 계획 원문' in html
    shutil.copyfile(root / 'output/result.html', out / 'incomplete_with_previous.html')
    assert all(sha(p) == old[str(p)] for p in protected)
    report = {'model_calls': 0, 'new_call_path_intercepted': len(calls), 'cases': ['완료 수집 재사용', '실제 반환의 적용 원문 누락 보류', '전달 변경 재사용', '판정 변경 재사용', '조회 변경 새 수집', '실제 미완료 상태와 이전 결과 혼재'], 'partial_checks': len(partial['next_checks']), 'bundle_checks': len(bundle['next_checks']), 'collection_sha256_unchanged_for_postprocess': initial, 'original_files_unchanged': old, 'sources': {p.name: sha(p) for p in [Path(w.__file__), HERE.parents[1] / 'agent_tools/evidence.py', HERE.parents[1] / 'agent_tools/result_steps.py']}}
    w.write_json(out / 'report.json', report); print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--actual', type=Path, required=True); p.add_argument('--student', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); main(a.actual, a.student, a.out)
