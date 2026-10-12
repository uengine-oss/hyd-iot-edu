"""Freeze completed record UI/K3 sources before prospective F27 edits; no tests or HTTP."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

V = Path(__file__).resolve().parent
T = V.parents[4]
if (V/'completed-source-manifest.json').exists():
    raise SystemExit('Completed source freeze already exists; do not overwrite it with later F27 sources.')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

ui = ['it/portal/www/' + name for name in
      ['caseRecord.css', 'caseRecord.js', 'plainWords.js', 'taskDetail.js', 'trace.js', 'ui.js']]
k3 = ['scripts/prepare_google_meeting_mapping.py', 'tests/test_google_meeting_mapping_preparation.py',
      'students/_template/google_meeting_mcp/README.md',
      'students/_template/google_meeting_mcp/meeting-contract.json']
test_sources = ['tests/test_portal_actual_record_contracts_ui.py', 'tests/test_portal_remaining_ui.py',
                'tests/test_portal_failure_states_ui.py', 'tests/fixtures/actual_bc_record_followup.json',
                'tests/test_bpmn_import.py', 'pytest.ini']
captured = json.loads((V/'final-c-source-before.json').read_text(encoding='utf-8-sig'))
current = {p: sha(T/p) for p in ui+k3+test_sources}
data = {
    'kind': 'completed-source-freeze-before-prospective-F27',
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=T, text=True).strip(),
    'scope': 'Six completed UI files, four K3 files and their source fixtures/import harness. '
             'This freezes exact bytes; it is not a whole-suite validation or F27 implementation proof.',
    'source_sha256': current,
    'ui_matches_final_C_capture': {p: current[p] == captured[p] for p in ui},
    'tests': {
        'new_ui_contract': {'passed': 10, 'seconds': 19.90,
                            'log': 'record-ui-final-source-contract.log'},
        'related_ui_contract': {'passed': 32, 'seconds': 50.33,
                                'log': 'record-ui-final-shared-affected.log',
                                'overlap_not_added': True},
        'broader_earlier_run': {'passed': 60, 'failed': 2, 'seconds': 106.43,
                               'log': 'record-ui-final-affected.log',
                               'failures_preserved': True},
        'K3': {'passed': 27, 'warnings': 1, 'seconds': 3.51, 'log': 'k3-pytest-final.log'},
        'live_initial': {'passed': 57, 'total': 59, 'log': 'first-result.json'},
        'live_final_C_only': {'passed': 21, 'total': 21, 'log': 'final-c-result.json'},
    },
    'evidence_sha256': {p: sha(V/p) for p in [
        'record-ui-final-source-contract.log', 'record-ui-final-shared-affected.log',
        'record-ui-final-affected.log', 'record-ui-baseline-proof-final.log',
        'k3-pytest-final.log', 'k3-pytest-final.xml', 'k3-manifest.json',
        'first-result.json', 'final-c-result.json', 'final-c-source-before.json',
        'final-c-source-after.json', 'final-c-case-state-proof.json']},
    'prior_whole_separate': {
        'result': '2673 passed, 16 skipped, 21 warnings; previous source version only',
        'reference': '../final-delegated/README.md',
        'source_manifest_reference': 'D:/work/study/hyd-iot-edu/.evidence/'
                                     'delegated-review-20261012/whole-final-source-manifest-verification.json',
        'extended_to_this_batch': False,
    },
    'F27': 'Open. Audit and design only at this freeze; implementation and tests not claimed.',
    'authenticated_google_runs': 0, 'registered_runnable_google_copies': 0,
}
assert all(data['ui_matches_final_C_capture'].values()), data['ui_matches_final_C_capture']
(V/'completed-source-manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'manifest': str(V/'completed-source-manifest.json'),
                  'ui_sha256': {p: current[p] for p in ui},
                  'ui_matches_final_C_capture': True}, ensure_ascii=False))
