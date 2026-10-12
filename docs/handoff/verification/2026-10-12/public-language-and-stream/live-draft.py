from pathlib import Path
import json,hashlib,uuid,datetime,time
from urllib.request import Request,urlopen
R=Path('D:/work/study/hyd-iot-edu'); H=Path(__file__).parent; B=R/'.evidence/google-meeting-import-20261012/prepared'
def call(path,data=None,method='GET'):
    req=Request('http://127.0.0.1:8080'+path,data=None if data is None else json.dumps(data).encode(),method=method,headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=45) as res:return json.loads(res.read())
def save(name,value):(H/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
assert (R/'.evidence/LIVE_LOCK').read_text(encoding='utf8').strip()==json.loads((H/'live-lock.json').read_text())['owner']
save('flows-before.json',call('/api/flows'))
id='codex-meeting-preflight-20261012-'+uuid.uuid4().hex[:8]
save('owned-draft.json',{'id':id,'registered':False,'started':False,'Google_calls':0,'cleanup':'DELETE /api/flows/'+id})
created=call('/api/flows/import',{'xml':(B/'flow.bpmn').read_text(encoding='utf8'),'file_name':'flow.bpmn','definition_id':id},'POST')
mapped=call('/api/flows/'+id+'/mapping',{'mapping':json.loads((B/'mapping.json').read_text(encoding='utf8'))},'PUT')
checked=call('/api/flows/'+id+'/check',{},'POST'); save('owned-draft-check.json',checked)
deps=checked['check']['dependencies']; assert checked['check']['ok'] and not checked['check']['problems']; assert deps['attention_count']==2 and all(x['status']=='missing_server' for x in deps['items'])
assert checked['versions']==[]
save('live-preflight-result.json',{'ok':True,'id':id,'structural_ok':True,'missing_server_count':2,'registered':False,'started':False,'Google_calls':0,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
print(json.dumps({'ok':True,'id':id,'missing_server_count':2}))
