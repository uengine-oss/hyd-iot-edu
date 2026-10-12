"""Current installed metadata only; no upload, extraction, ingestion or model execution."""
from datetime import datetime,timezone
import hashlib,json,subprocess
from pathlib import Path
from urllib.request import urlopen
H=Path(__file__).parent
F=H.parent/'delegated-review-20261012'
T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
url='http://127.0.0.1:8080/api/kg/manuals'
with urlopen(url,timeout=25) as response:
    body=response.read();status=response.status
rows=json.loads(body)
keys=('batch','document_id','source_id','filename','current','status','sections','procedures','steps','by','t')
proof={'created_utc':datetime.now(timezone.utc).isoformat(),'method':'One GET of current installed manual metadata; prior actual1440/1024 PNGs inspected, no recapture/ingestion/model run','url':url,'status':status,'response_sha256':hashlib.sha256(body).hexdigest(),'total_history_rows':len(rows),'manuals':{},'checks':[],'visual_inspection':{'files':['portal-final-phase2-live/knowledge-history-1440.png','portal-final-phase2-live/knowledge-history-1024.png'],'observed':'Three named current manual cards show real installed sections/procedures/steps; delegated Codex is visibly recorded as reviewer, without human impersonation. File names are original source names. This is not final user visual acceptance.'}}
for name in ('HM-8','PM-02','PR-07'):
    accepted=json.loads((F/(name+'-official-ingest-accepted.json')).read_text(encoding='utf-8'))
    history=[u for u in rows if u['source_id']==accepted['source_id']]
    installed=[u for u in history if u.get('current') and u.get('status')=='ACTIVE']
    checks={'one_current_installed':len(installed)==1,'accepted_batch_preserved':any(u['batch']==accepted['batch'] for u in history),'delegated_reviewer_matches':bool(installed) and installed[0]['by']==accepted['by'],'review_method_not_human':accepted['review_method']=='user-delegated-ai-review'}
    proof['manuals'][name]={'accepted':accepted,'history_for_source':[{k:u.get(k) for k in keys} for u in history],'checks':checks}
    proof['checks'].extend({'label':name+' '+k,'passed':v} for k,v in checks.items())
proof['head']=subprocess.check_output(['git','-C',str(T),'rev-parse','HEAD'],text=True).strip()
proof['passed']=status==200 and all(x['passed'] for x in proof['checks'])
(H/'current-installed-manual-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
assert proof['passed'],proof['checks']
print(json.dumps({'passed':proof['passed'],'checks':len(proof['checks']),'current':[next(u for u in v['history_for_source'] if u['current'])['filename'] for v in proof['manuals'].values()]},ensure_ascii=False))
