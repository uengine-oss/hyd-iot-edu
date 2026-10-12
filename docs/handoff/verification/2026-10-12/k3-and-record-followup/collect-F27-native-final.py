"""Preserve scoped native final evidence and failed attempts; do not contact services."""
import hashlib
import json
from pathlib import Path

V = Path(__file__).resolve().parent
T = V.parents[4]
H = Path('D:/work/study/hyd-iot-edu/.evidence/k3-preparation-20261012')
rows = []

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def copy(source, target):
    body = source.read_bytes()
    p = V/target
    assert not p.exists() or p.read_bytes() == body, target
    p.write_bytes(body)
    rows.append(dict(source=str(source), target=target, sha256=sha(p)))

for run in (1, 2, 3):
    folder = H/f'live-F27-final-{run}'
    copy(folder/'result.json', f'F27-native-{run}-result.json')
    copy(H/f'F27-live-native-final-{run}.log', f'F27-live-native-final-{run}.log')
    if run == 3:
        for p in folder.iterdir():
            if p.suffix in ('.png', '.txt') or p.name in ('source-before.json', 'source-after.json',
                                                        'B-resolved-tools.json', 'C-resolved-tools.json'):
                copy(p, 'F27-native-final-'+p.name)
copy(H/'F27-live-native-driver.py', 'F27-live-native-final-driver.py')
for name in ('F27-final-source-manifest.json', 'F27-final-source-manifest.py',
             'F27-final-source-verification.json'):
    copy(H/name, name)
final = load(H/'live-F27-final-3/result.json')
assert final['passed'] and len(final['checks']) == 96 and all(c['passed'] for c in final['checks'])
assert final['driver_sha256'] == sha(H/'F27-live-native-driver.py')
before = load(H/'live-F27-final-3/cases-before.json')
after = load(H/'live-F27-final-3/cases-after.json')
proof = []
def persisted(v):
    return {k: v.get(k) for k in ('instance', 'workitems', 'approvals', 'effects', 'reworks')}
def digest(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()
for case, value in before.items():
    a, b = persisted(value), persisted(after[case])
    assert a == b
    proof.append(dict(case=case, proc_inst_id=value['instance']['proc_inst_id'],
                      status=value['instance']['status'], persisted_before_sha256=digest(a),
                      persisted_after_sha256=digest(b), unchanged=True,
                      canonicalization='UTF8 JSON sort_keys=true separators=comma/colon of '
                                       'instance/workitems/approvals/effects/reworks',
                      full_before_source=str(H/'live-F27-final-3/cases-before.json'),
                      full_before_file_sha256=sha(H/'live-F27-final-3/cases-before.json'),
                      full_after_source=str(H/'live-F27-final-3/cases-after.json'),
                      full_after_file_sha256=sha(H/'live-F27-final-3/cases-after.json')))
(V/'F27-native-final-case-state-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
source = load(H/'F27-final-source-manifest.json')['source_sha256']
current_checks = {p: sha(T/p) == s for p, s in source.items()}
assert len(source) == 807 and all(current_checks.values())
summary = dict(kind='F27 scoped implementation and native verification', checks_passed=96,
               native_result='F27-native-3-result.json', source_files=807,
               current_source_matches_frozen=True, previous_whole_extended=False,
               backend_final_passed=23, backend_log='F27-backend-final-23.log',
               ui_error_priority_passed=3, ui_typed_text_passed=4, counts_combined=False,
               failed_attempts=['F27-native-1-result.json', 'F27-native-2-result.json'],
               source_proof='F27-final-source-verification.json',
               producer_live_next_start='Unit validated; no new worker/LLM run performed',
               business_cases_unchanged=True, llm_reruns=0, whole_reruns=0,
               U16_U20_F13='open', whole_UIUX_173_pair_coverage='UNVERIFIED',
               K3_external_authentication='unverified',
               pre_F27_manifest_sha256=sha(V/'completed-source-manifest.json'),
               pre_F27_manifest_unchanged=True)
(V/'F27-final-scoped-manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(V/'F27-native-final-evidence-provenance.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'copied': len(rows), 'native_passed': 96,
                  'source_files_match': 807, 'unchanged_cases': len(proof)}))
