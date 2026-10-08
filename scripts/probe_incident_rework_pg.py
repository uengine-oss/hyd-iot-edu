"""Real PG/SQLite + enterprise ledger reads. Fixture source/current-check/PLC/graph; no Codex or physical command."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import probe_approval_delivery as base
from procsvc import decision_scope


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--crash');parser.add_argument('--delivered',action='store_true');args=parser.parse_args()
    out=Path(args.out).resolve();base.OUT=out
    if args.crash:
        meta=json.loads((out/'fixture.json').read_text(encoding='utf8'))
        rt,ctx,store=base.new_runtime(meta);ctx.approval_receipts=base.process_main._approval_receipts
        if args.crash=='before':
            original=rt.repo.record_events
            def die(events): original(events);os._exit(73)
            rt.repo.record_events=die
        rt.request_rework(meta['pid'],**meta['request'])
        os._exit(74)
    out.mkdir(parents=True,exist_ok=False);checks=[]
    def save(name,value): (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,passed):
        checks.append({'name':name,'passed':bool(passed)});save('checks',checks)
        print(('PASS ' if passed else 'FAIL ')+name,flush=True);assert passed,name
    rt,ctx,store,meta=base.fixture();ctx.approval_receipts=base.process_main._approval_receipts
    if args.delivered:
        original=rt.hooks.approve_commands
        rt.hooks.approve_commands=lambda *args:(_ for _ in ()).throw(ValueError('explicit fixture current command preflight rejection'))
        base.choose(rt,meta);rt.poll_once();rt.poll_once()
        rt.hooks.approve_commands=original
        assert rt.repo.get_approval(meta['wid'],meta['tenant'])['status']=='DELIVERED'
    else:
        original=rt.hooks.deliver_approval
        rt.hooks.deliver_approval=lambda _:(_ for _ in ()).throw(ValueError('explicit fixture pre-effect failure'))
        base.choose(rt,meta);rt.hooks.deliver_approval=original
    pid=meta['pid'];tenant=meta['tenant']
    def latest(aid): return base.engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid,limit=None))[aid]
    rank=latest('task:rank');prior=rt.repo.get_approval(meta['wid'],tenant)
    preview=rt.preview_rework(pid,rank['id']);save('preview',preview)
    check('real complete enterprise ledger permits active pre-effect rework',preview['execution_available'] and all(v==[] for v in preview['effects']['enterprise_receipts'].values()))
    meta['request']={'workitem_id':rank['id'],'request_id':str(uuid.uuid4()),'snapshot_token':preview['snapshot_token'],
                     'by':'[회귀 검사] PG 재작업 검토자','role':'role:prod-mgr','reason':'[회귀 검사] 근거가 바뀜 — 실패한 승인을 거두고 다시 판단'}
    save('fixture',meta);before=rt.instance_view(pid);before_disk=store.restore();save('before',before)
    try:
        for phase,exit_code in [('before',73),('after',74)]:
            child=subprocess.run([sys.executable,__file__,'--out',str(out),'--crash',phase],capture_output=True,timeout=60)
            save(phase+'-child',{'exit':child.returncode,'stderr':child.stderr.decode('utf8',errors='replace')})
            assert child.returncode==exit_code
            if phase=='before':
                check('actual process death before commit rolls back retirement rows receipt and events',rt.instance_view(pid)==before)
                check('PG rollback leaves SQLite original cards and incident untouched',store.restore()==before_disk)
        committed=rt.instance_view(pid);save('committed-after-death',committed)
        check('death after commit leaves generation and discarded original consent durable',committed['instance']['rework_generation']==1
              and rt.repo.get_approval(meta['wid'],tenant)['status']=='DISCARDED')
        def replay(_):
            peer=base.instances.InstanceRuntime(base.procdb.PgRepo(base.DSN),rt.defn,base.instance_mode._hooks(ctx),tenant_id=tenant)
            return peer.request_rework(pid,**meta['request'])
        with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(replay,range(4)))
        check('four PG peers replay one immutable receipt',all(r==results[0] for r in results) and len(rt.repo.list_reworks(tenant,pid))==1)
        retired=rt.repo.get_approval(meta['wid'],tenant)
        check('old consent payload error and history remain',retired['payload']==prior['payload'] and retired['error']==prior['error'] and retired['history'][:-1]==prior['history'])
        store.db.close();rt,ctx,store=base.new_runtime(meta);ctx.approval_receipts=base.process_main._approval_receipts
        check('reopened SQLite and fresh PG runtime retain generation and exact replay',rt.request_rework(pid,**meta['request'])==results[0] and store.restore()==before_disk)
        check('old worker cannot overwrite completed prior rank',not rt.repo.save_task_result(rank['id'],{'decision_id':'stale'},True,expected_consumer=tenant))
        claimed,=rt.repo.fetch_pending_task('cliagents','old-id-test',tenant_id=tenant,proc_inst_id=pid)
        old_output=deepcopy(rank['output'])
        assert rt.repo.save_task_result(claimed['id'],old_output,True,expected_consumer='old-id-test')
        rt.poll_once()
        bad=rt.repo.get_workitem(claimed['id']);save('rejected-old-result',bad)
        check('engine rejects old decision ID and does not open human selection',bad['status']=='SUBMITTED' and bad['retry']==1 and latest('task:select')['status']=='TODO')
        p=rt.preview_rework(pid,claimed['id'])
        rt.request_rework(pid,claimed['id'],str(uuid.uuid4()),p['snapshot_token'],'[회귀 검사] PG 검토자','role:prod-mgr','[회귀 검사] 거절된 옛 판단 출력을 새 세대로 바로잡음')
        new,=rt.repo.fetch_pending_task('cliagents','new-decision-test',tenant_id=tenant,proc_inst_id=pid)
        inst=rt.repo.get_instance(pid);scope=decision_scope.expected(inst,new)|{'consumer':new['consumer']}
        decision_scope.validate_submission(inst,rt.definition_for(inst),new,scope)
        fresh=base.decisions.new(deepcopy(ctx.book[meta['decision']]));fresh.pop('process_approval_id',None)
        fresh.update(id='DEC-rework-'+uuid.uuid4().hex)
        fresh['origin']['process_scope']=scope;ctx.book[fresh['id']]=fresh;ctx.persist()
        payload=deepcopy(rank['output']);payload['decision_id']=fresh['id']
        assert rt.repo.save_task_result(new['id'],payload,True,expected_consumer='new-decision-test')
        rt.poll_once();selection=latest('task:select')
        check('generation 2 scoped decision advances while original decision stays immutable',selection['status']=='IN_PROGRESS'
              and rt.repo.get_workitem(new['id'])['status']=='DONE' and ctx.book[meta['decision']]==before_disk[1][meta['decision']])
        check('new judgment alone sends no command and has no consent',not meta['commands'] and rt.repo.get_approval(selection['id'],tenant) is None)
        rt.select(selection['id'],fresh['id'],fresh['options'][0]['id'],'[회귀 검사] 새 검토자','role:prod-mgr')
        approval=rt.repo.get_approval(selection['id'],tenant)
        check('new explicit approval has new workitem and decision; one fixture command',approval['status']=='DELIVERED'
              and approval['decision_id']==fresh['id'] and approval['todo_id']!=prior['todo_id'] and len(meta['commands'])==1)
        p=rt.preview_rework(pid,new['id']);save('after-effect-preview',p)
        check('after an effect the same restart is blocked for compensation review',not p['execution_available']
              and any(b['code']=='incident_effects_require_compensation' for b in p['blockers']))
        save('final',rt.instance_view(pid));save('sqlite-final',{'incidents':{k:v.to_dict() for k,v in ctx.incidents.items()},'book':ctx.book})
    finally:
        store.db.close();save('result',{'scope':__doc__,'tenant':tenant,'instance':pid,'checks':checks,'fixture_commands':meta['commands']})
    print(f'{len(checks)}/{len(checks)} passed; fixture retained',flush=True)


if __name__=='__main__':main()
