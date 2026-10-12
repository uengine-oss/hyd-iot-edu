"""Preserve final frozen F27 sources and bounded logs, without claiming live acceptance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

V = Path(__file__).resolve().parent
T = V.parents[4]
H = Path('D:/work/study/hyd-iot-edu/.evidence/k3-preparation-20261012')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

names = ['F27-ui-source-freeze.json', 'F27-ui-typed-text-followup.log',
         'F27-ui-final-error-followup.log', 'F27-ui-final-focused.log',
         'F27-backend-final-23.log', 'F27-backend-final-23-proof.json',
         'F27-live-native-driver.py']
copies = []
for name in names:
    p = H/name
    target = V/name
    body = p.read_bytes()
    assert not target.exists() or target.read_bytes() == body, name
    target.write_bytes(body)
    copies.append(dict(source=str(p), target=name, sha256=sha(p)))
ui = json.loads((H/'F27-ui-source-freeze.json').read_text(encoding='utf-8-sig'))
backend = json.loads((H/'F27-backend-final-23-proof.json').read_text(encoding='utf-8-sig'))
checks = [dict(path=p, frozen_sha256=s, actual_sha256=sha(T/p), matches=sha(T/p) == s)
          for p, s in ui.items()]
checks += [dict(path=row['path'], frozen_sha256=row['sha256'],
                actual_sha256=sha(T/row['path']), matches=sha(T/row['path']) == row['sha256'])
           for row in backend['source_checks']]
assert all(row['matches'] for row in checks), checks
manifest = {
    'kind': 'F27-final-source-preparation-separate-from-pre-F27-freeze',
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'source_checks': checks, 'all_sources_match_frozen': True,
    'preserved_copies': copies,
    'backend_final': {'passed': 23, 'seconds': 7.40,
                      'log': 'F27-backend-final-23.log', 'proof': 'F27-backend-final-23-proof.json'},
    'ui_focused_first': {'passed': 58, 'failed': 1, 'seconds': 151.93,
                         'log': 'F27-ui-final-focused.log', 'failure_preserved': True},
    'ui_error_priority_followup': {'passed': 3, 'seconds': 7.50,
                                   'log': 'F27-ui-final-error-followup.log'},
    'ui_typed_text_followup': {'passed': 4, 'seconds': 12.08,
                              'log': 'F27-ui-typed-text-followup.log'},
    'counts_not_combined': 'Different and overlapping source-scoped runs; do not claim one stable all59 run.',
    'backend_initial_22_raw_log': 'Not preserved; initial progress claim retained, final23 raw proof authoritative.',
    'live_acceptance': 'Awaiting root native capture result and final source/state review; F27 not closed here.',
    'pre_F27_manifest_sha256': sha(V/'completed-source-manifest.json'),
    'pre_F27_manifest_unchanged': True,
    'K3_external_authenticated_execution': False,
    'whole_UIUX_173_pair_coverage': 'UNVERIFIED, not zero',
}
(V/'F27-final-preparation-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'copied': len(copies), 'source_checks': len(checks),
                  'all_match': True, 'live_acceptance': 'awaiting root'}))
