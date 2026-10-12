import json,hashlib,urllib.request,urllib.parse,datetime
from pathlib import Path
p=Path(__file__).parent
case=json.loads((p/'actual-B-case.json').read_text(encoding='utf8'))
event=[e for e in case['events'] if e['event_type']=='task_deferred'][-1]
evaluation=event['data']['receipt']['assessment']['evidence']['evaluate_cards']['document']
options=[{k:o[k] for k in ('id','name','feasible','window','maintenanceDiagnostics','forecast_error','violations') if k in o} for o in evaluation['options']]
source_id=options[0]['maintenanceDiagnostics']['model_applicability']['source_anchor']['source_id']
url='http://127.0.0.1:8080/api/kg/manuals/sources/'+urllib.parse.quote(source_id,safe='')
with urllib.request.urlopen(url,timeout=10) as response: raw=response.read();status=response.status
(p/'PM-02-original-source-GET.json').write_bytes(raw)
manifest=dict(method='GET',url=url,status=status,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
(p/'source-read-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
result=dict(instance_id=case['instance']['proc_inst_id'],instance_status=case['instance']['status'],event_id=event['id'],recorded_receipt=event['data']['receipt']['id'],evaluation_id=evaluation['id'],evaluation_status=evaluation['status'],recommended=evaluation['recommended'],options=options)
(p/'actual-B-package-lineage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('source GET',status,'bytes',len(raw),'options',len(options))
