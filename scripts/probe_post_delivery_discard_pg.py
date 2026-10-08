"""Real PG/SQLite/enterprise ledger; source and PLC are isolated test fixtures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import probe_approval_delivery as base


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--crash');args=parser.parse_args()
    out=Path(args.out).resolve();base.OUT=out
    def save(name,x):(out/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    if args.crash:
        meta=json.loads((out/'fixture.json').read_text(encoding='utf8'))
        rt,ctx,store=base.new_runtime(meta);ctx.approval_receipts=base.process_main._approval_receipts
        if args.crash=='before':
            original=rt.repo.record_events
            def die(events):original(events);os._exit(73)
            rt.repo.record_events=die
        rt.discard_approval(meta['wid'],**meta['request']);os._exit(74)
    out.mkdir(parents=True,exist_ok=False);checks=[]
    def check(name,passed):
        checks.append({'name':name,'passed':bool(passed)});save('checks',checks)
        print(('PASS ' if passed else 'FAIL ')+name,flush=True);assert passed,name
    rt,ctx,store,meta=base.fixture();ctx.approval_receipts=base.process_main._approval_receipts
    original=rt.hooks.approve_commands
    rt.hooks.approve_commands=lambda *args:(_ for _ in ()).throw(ValueError('explicit fixture current condition changed'))
    base.choose(rt,meta);rt.poll_once();rt.poll_once();rt.hooks.approve_commands=original
    inc=next(iter(ctx.incidents.values()));inc.state='RESOLVED_WITHOUT_ACTION';inc.cleared=True;ctx.persist()
    pid=meta['pid'];tenant=meta['tenant'];wid=meta['wid']
    meta['request']=dict(by='[회귀 검사] PG 검토자',role='role:prod-mgr',reason='[회귀 검사] 명령을 내기 전에 원천 경보가 끝남',request_id=str(uuid.uuid4()))
    save('fixture',meta);before=rt.instance_view(pid);disk=store.restore();save('before',before)
    try:
        preview=rt.preview_approval_discard(wid,'[회귀 검사] PG 검토자','role:prod-mgr');save('preview',preview)
        check('delivered command is stopped with no durable or external effect',preview['can_discard'] and bool(preview['unissued_commands']) and not meta['commands'])
        try:rt.preview_approval_discard(wid,'operator','role:operator')
        except PermissionError:denied=True
        else:denied=False
        check('lower role cannot close higher consent',denied and rt.instance_view(pid)==before)
        for phase,code in [('before',73),('after',74)]:
            child=subprocess.run([sys.executable,__file__,'--out',str(out),'--crash',phase],capture_output=True,timeout=60)
            save(phase+'-child',{'exit':child.returncode,'stderr':child.stderr.decode('utf8',errors='replace')})
            check(phase+' commit process actually exited',child.returncode==code)
            if phase=='before':check('process death rolls back all PG rows and preserves SQLite',rt.instance_view(pid)==before and store.restore()==disk)
        committed=rt.instance_view(pid);save('committed',committed)
        check('postcommit death leaves cancellation durable not business success',committed['instance']['status']=='CANCELLED' and rt.repo.get_approval(wid,tenant)['status']=='DISCARDED')
        def replay(_):
            peer=base.instances.InstanceRuntime(base.procdb.PgRepo(base.DSN),rt.defn,base.instance_mode._hooks(ctx),tenant_id=tenant)
            return peer.discard_approval(wid,**meta['request'])
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(replay,range(4)))
        check('four database peers replay the same cancellation',all(r==results[0] for r in results) and sum(h['status']=='DISCARDED' for h in results[0]['history'])==1)
        approval=before['approvals'][0]
        check('original delivery payload and history preserved',results[0]['payload']==approval['payload'] and results[0]['history'][:-1]==approval['history'] and results[0]['history'][-1]['previous_status']=='DELIVERED')
        store.db.close();rt,ctx,store=base.new_runtime(meta);ctx.approval_receipts=base.process_main._approval_receipts
        rt.poll_once()
        check('restart and reconciler do not resurrect cancelled commands',rt.instance_view(pid)==committed and store.restore()==disk and not meta['commands'])
        check('reopened runtime replays exact receipt',rt.discard_approval(wid,**meta['request'])==results[0])
    finally:
        store.db.close();save('result',dict(scope=__doc__,checks=checks,tenant=tenant,instance=pid,fixture_commands=meta['commands']))
    print(f'{len(checks)}/{len(checks)} passed; isolated fixtures retained',flush=True)


if __name__=='__main__':main()
