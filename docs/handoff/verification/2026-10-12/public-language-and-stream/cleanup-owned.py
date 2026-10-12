from pathlib import Path
import json,hashlib,datetime,subprocess
from urllib.request import Request,urlopen
R=Path('D:/work/study/hyd-iot-edu'); H=Path(__file__).parent
assert (R/'.evidence/LIVE_LOCK').read_text(encoding='utf8').strip()==json.loads((H/'live-lock.json').read_text())['owner']
id=json.loads((H/'owned-draft.json').read_text())['id']; assert id.startswith('codex-meeting-preflight-20261012-')
with urlopen(Request('http://127.0.0.1:8080/api/flows/'+id+'?by=codex-preflight-verification',method='DELETE'),timeout=45) as r:out=json.loads(r.read())
with urlopen('http://127.0.0.1:8080/api/flows',timeout=45) as r:after=json.loads(r.read())
before=json.loads((H/'flows-before.json').read_text(encoding='utf8')); assert before==after
docker='C:/Users/roede/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
inspect=json.loads(subprocess.check_output([docker,'inspect','hyd-iot-edu-process-1'],text=True))[0]
containers=subprocess.check_output([docker,'ps','--format','{{.Names}}'],text=True).splitlines()
proof={'owned_draft_deleted':out,'existing_flows_exact_unchanged':True,'registered':False,'started':False,'Google_calls':0,'process':{'StartedAt':inspect['State']['StartedAt'],'RestartCount':inspect['RestartCount'],'health':inspect['State']['Health']['Status'],'Memory':inspect['HostConfig']['Memory']},'container_names':containers,'count':len(containers),'completion_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'initial_build_failure':'COMPOSE_PROFILES absent: no such service redpanda. No build/up; corrected explicit documented profiles. Both logs retained.','first_read_failure':'Premature GET /api/flows during planned process startup: RemoteDisconnected. No POST or draft created in failed run; current owned import/check succeeded after startup complete.'}
(H/'deploy-and-cleanup.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
assert (R/'.evidence/LIVE_LOCK').read_text(encoding='utf8').strip()==json.loads((H/'live-lock.json').read_text())['owner'];(R/'.evidence/LIVE_LOCK').unlink()
print(json.dumps({'cleanup':True,'flows_unchanged':True,'process_health':proof['process']['health'],'containers':len(containers),'lock_released':True}))
