"""Amend evidence metadata without regenerating the frozen UI hashes or contacting services."""
import hashlib
import json
from pathlib import Path

V = Path(__file__).resolve().parent
T = V.parents[4]
H = Path('D:/work/study/hyd-iot-edu/.evidence/k3-preparation-20261012')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

manifest = load(V/'completed-source-manifest.json')
manifest['additional_related_test_source_sha256'] = {
    name: sha(T/name) for name in [
        'tests/test_portal_pm_deferral_ui.py', 'tests/test_portal_purchase_tools_ui.py',
        'tests/test_portal_pm_package_scope_ui.py']}
manifest['test_commands'] = {
    'new_ui_contract': 'D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe -m pytest -q '
                       'tests/test_portal_actual_record_contracts_ui.py --tb=short',
    'related_ui_contract': 'D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe -m pytest -q '
                           'tests/test_portal_actual_record_contracts_ui.py '
                           'tests/test_portal_pm_deferral_ui.py '
                           'tests/test_portal_purchase_tools_ui.py '
                           'tests/test_portal_pm_package_scope_ui.py --tb=short',
    'K3': 'D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/clean-venv/Scripts/python.exe '
          '-m pytest tests/test_google_meeting_mapping_preparation.py -q',
}
(V/'completed-source-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

original = H/'F27-actual-stored-payloads-GET.json'
actual = load(original)
assert actual['passed']
rows = []
for ref, value in actual['payloads'].items():
    body = ''.join(chunk['content'] for chunk in value['chunks'])
    refmeta = value['reference']
    body_sha = hashlib.sha256(body.encode('utf-8')).hexdigest()
    assert len(body) == refmeta['chars'] == refmeta['original_chars']
    assert body_sha == refmeta['sha256']
    assert refmeta['cut'] is False and all(value['checks'].values())
    assert all(chunk['meta']['content_sha256'] == body_sha and chunk['meta']['cut'] is False
               for chunk in value['chunks'])
    parsed = json.loads(body)
    rows.append({'case': value['case'], 'event_id': value['event_id'], 'tool': value['tool'],
                 'ref': ref, 'chars': len(body), 'sha256': body_sha, 'cut': False,
                 'checks': value['checks'], 'locally_rechecked': True,
                 'parsed_json_type': type(parsed).__name__})
proof = {'source': str(original), 'source_sha256': sha(original),
         'method': actual['method'], 'payloads': rows, 'payload_count': len(rows), 'passed': True,
         'scope': 'Root actual read-only GET; local independent length/SHA/cut/JSON verification. '
                  'No product execution, F27 fix validation, or current-case mutation claimed.'}
(V/'F27-actual-stored-payload-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
semantics = H/'F27-actual-stored-payload-semantics.json'
(V/semantics.name).write_bytes(semantics.read_bytes())
audit = H/'tool-output-consumer-audit.json'
assert (V/audit.name).read_bytes() == audit.read_bytes()
provenance = [dict(source=str(p), target=p.name, sha256=sha(p)) for p in [audit, semantics]]
(V/'documentation-evidence-provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'frozen_ui_hashes_preserved': True, 'related_test_sources_added': 3,
                  'actual_payloads_independently_rechecked': len(rows)}, ensure_ascii=False))
