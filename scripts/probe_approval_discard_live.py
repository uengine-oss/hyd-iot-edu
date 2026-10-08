"""Capture/verify the original failed HYD approval around an actual UI discard.

--phase before performs read/preview/denied-role checks. The human UI action is
performed separately. --phase after verifies the durable outcome and replays
the already committed request, never fabricating success by changing DB rows.
"""
import argparse,json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

PID='anomaly_response.d6a2392c-f5b2-4772-9593-b7b104c8a493'
WID='6e50dcef-082b-48eb-a243-2d9b8ce82448'
BASE='http://127.0.0.1:8080'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--phase',choices=['before','after'],required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);checks=[]
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    def call(path,body=None):
        req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json'})
        try:res=urlopen(req,timeout=25)
        except HTTPError as exc:res=exc
        return res.status,json.loads(res.read())
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)});save(args.phase+'-checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    status,view=call('/api/instances/'+PID);assert status==200
    approval=next(a for a in view['approvals'] if a['todo_id']==WID)
    _,incident=call('/api/incidents/'+approval['payload']['incident'])
    save(args.phase+'-instance',view);save(args.phase+'-incident',incident)
    prefix='/api/todolist/'+WID
    if args.phase=='before':
        check('original unresolved process with failed consent',view['instance']['status']=='RUNNING' and approval['status']=='FAILED')
        status,error=call(prefix+'/approval-discard-preview',{'by':'[회귀 검사] A035 운전원','role':'role:operator'})
        save('operator-denied',{'status':status,'response':error});check('insufficient role denied',status==403)
        status,preview=call(prefix+'/approval-discard-preview',{'by':'[회귀 검사] A035 복구 관리자','role':'role:prod-mgr'})
        save('preview',preview);check('actual ledger and ended Incident allow explicit discard',status==200 and preview['can_discard'] and not preview['enterprise_receipts'])
        check('no physical command before discard',incident['cmdId'] is None and incident['state']=='RESOLVED_WITHOUT_ACTION')
    else:
        before=json.loads((out/'before-instance.json').read_text(encoding='utf8'))
        prior=next(a for a in before['approvals'] if a['todo_id']==WID)
        check('UI committed discard and explicit cancellation',approval['status']=='DISCARDED' and view['instance']['status']=='CANCELLED')
        check('original approval payload and failure retained',approval['payload']==prior['payload'] and approval['error']==prior['error'])
        check('original Incident remains ended without command',incident==json.loads((out/'before-incident.json').read_text(encoding='utf8')))
        check('all remaining tasks terminal',all(w['status'] in {'DONE','CANCELLED'} for w in view['workitems']))
        history=approval['history'][-1]
        status,replay=call(prefix+'/approval-discard',{k:history[k] for k in ['by','role','reason','request_id']})
        save('replay',replay);check('HTTP replay returns same immutable result',status==200 and replay==approval)
        status,error=call(prefix+'/approval-retry',{'by':history['by'],'role':history['role']})
        save('retry-denied',{'status':status,'response':error});check('discarded approval cannot be delivered again',status==409)
        _,final=call('/api/instances/'+PID);save('final-instance',final)
        check('one durable discard event',sum(e['job_id']=='APPROVAL_DISCARDED' for e in final['events'])==1)
        status,graph=call('/api/instances/'+PID+'/graph');save('graph',graph)
        projected=graph.get('graph') or {}
        check('execution graph retains cancellation and task states',status==200 and projected.get('instance',{}).get('status')=='CANCELLED'
              and {w['id']:w['status'] for w in projected.get('workitems',[])}=={w['id']:w['status'] for w in final['workitems']})
    save(args.phase+'-result',{'checks':checks,'scope':__doc__})
    print(f'{len(checks)}/{len(checks)} passed')


if __name__=='__main__':main()
