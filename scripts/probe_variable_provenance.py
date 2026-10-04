"""Real HTTP/PG input provenance on a new non-HYD definition; no Codex or PLC."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import uuid
from urllib.request import Request,urlopen
import psycopg

BASE='http://127.0.0.1:8080'
DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False);checks=[]
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def call(path,body=None):
        req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=30) as response:return json.load(response)
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    raw=json.loads(Path('docs/examples/inspection-review-v1.json').read_text(encoding='utf8'))
    raw['processDefinitionId']='provenance_'+uuid.uuid4().hex[:10]
    raw['processDefinitionName']='Start input and result provenance acceptance'
    save('definition',raw)
    definition=call('/api/process/definitions',{'definition':raw});save('registered',definition)
    values={'score':2,'request':{'source':'A036 actual HTTP input','revision':1}}
    opened=call('/api/instances/start',{'definition_id':raw['processDefinitionId'],'version':raw['version'],
                 'event_id':'A036-'+uuid.uuid4().hex,'variables':values});save('opened',opened)
    pid=opened['proc_inst_id'] if 'proc_inst_id' in opened else opened['instance']['proc_inst_id']
    before=call('/api/instances/'+pid);save('before',before)
    inst=before['instance']
    check('HTTP start records exact immutable input',inst['initial_variables']==values)
    check('start variables identify input source',inst['variable_sources']=={k:{'kind':'input'} for k in values})
    wi=next(w for w in before['workitems'] if w['activity_id']=='task:review')
    result=call('/api/todolist/'+wi['id']+'/submit',{'by':'A036 provenance reviewer','output':{'score':7}});save('submitted',result)
    final=call('/api/instances/'+pid);save('after',final)
    live={v['key']:v['value'] for v in final['instance']['variables_data']}
    check('changed result reaches correct gateway',live['score']==7 and final['instance']['end_event']=='accepted')
    check('old input survives new task result',final['instance']['initial_variables']==values)
    check('result identifies exact producing task and version',final['instance']['variable_sources']['score']==
          {'kind':'workitem','id':wi['id'],'activity':wi['activity_id'],'version':wi['version']})
    failures=[]
    for tampered in ({'score':999},None):
        with psycopg.connect(DSN,autocommit=True) as connection:
            try:
                connection.execute('update bpm_proc_inst set initial_variables=%s where proc_inst_id=%s',
                                   (psycopg.types.json.Jsonb(tampered) if tampered is not None else None,pid))
            except psycopg.Error as exc:failures.append(str(exc))
    save('tamper-errors',failures)
    check('DB rejects both start replacement and removal',len(failures)==2 and all('immutable' in f for f in failures))
    readback=call('/api/instances/'+pid);save('readback',readback)
    check('API state survives rejected DB writes',readback['instance']==final['instance'])
    with psycopg.connect(DSN) as connection:
        old=connection.execute('select initial_variables from bpm_proc_inst where proc_inst_id=%s',
           ('anomaly_response.d6a2392c-f5b2-4772-9593-b7b104c8a493',)).fetchone()
    check('old instance remains explicitly without start snapshot',old==(None,))
    save('result',{'checks':checks,'instance':pid,'scope':__doc__})
    print(f'{len(checks)}/{len(checks)} passed')


if __name__=='__main__':main()
