import json, hashlib
from pathlib import Path
root=Path('D:/work/study/hyd-iot-edu')
src=root/'.evidence/delegated-review-20261012/portal-final-phase2-live/cases-before.json'
dec=root/'.evidence/k3-preparation-20261012/C-original-decision-actual-GET.json'
data=json.loads(src.read_text(encoding='utf-8'))
result={'provenance':{'cases_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'decision_sha256':hashlib.sha256(dec.read_bytes()).hexdigest(),'recipe':'Keep complete B and C records verbatim from cases-before.json; keep full saved C original decision GET. No field-level modifications.','cases_source':str(src.relative_to(root)),'decision_source':str(dec.relative_to(root))},'B':data['B'],'C':data['C'],'C_decision':json.loads(dec.read_text(encoding='utf-8'))}
Path('tests/fixtures/actual_bc_record_followup.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
