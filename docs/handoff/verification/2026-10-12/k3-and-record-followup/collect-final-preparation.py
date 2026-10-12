"""Copy bounded evidence for final documentation preparation; preserve exact source SHA."""
import hashlib
import json
from pathlib import Path

V = Path(__file__).resolve().parent
H = Path('D:/work/study/hyd-iot-edu/.evidence/k3-preparation-20261012')
names = ['F27-backend-progress.json', 'F27-backend-negative.log',
         'F27-backend-regression.log', 'F27-backend-regression-utf8.log',
         'F27-backend-shared-origin.log', 'F27-backend-ui-load-followup.log',
         'runtime-readonly-followup.json', 'remaining-acceptance-audit.json',
         'remaining-acceptance-audit.md', 'F27-ui-first.log', 'F27-ui-second.log',
         'F27-ui-third.log', 'F27-ui-fourth.log', 'F27-ui-vm-load.log']
rows = []
for name in names:
    source, target = H/name, V/name
    body = source.read_bytes()
    if target.exists():
        assert target.read_bytes() == body, f'Existing evidence differs; preserve before updating: {name}'
    else:
        target.write_bytes(body)
    rows.append({'source': str(source), 'target': name,
                 'sha256': hashlib.sha256(body).hexdigest(),
                 'label': 'intermediate UI evidence; not final stable proof' if 'F27-ui-' in name
                          else 'copied exact evidence snapshot'})
(V/'final-preparation-evidence-provenance.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'copied': len(rows), 'all_sha_verified': True}))
