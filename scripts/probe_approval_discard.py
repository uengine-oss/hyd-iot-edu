"""Actual PG/SQLite/enterprise HTTP; fixture incident and PLC/graph are doubles.

Retains one cancelled fixture tenant and its evidence. Does not alter the live
HYD incident; that is a separate API acceptance run after deployment.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import traceback

import probe_approval_delivery as base


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);base.OUT=out
    checks=[];store=None
    def save(name,value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    try:
        rt,ctx,store,meta=base.fixture();save('fixture',meta)
        ctx.approval_receipts=base.process_main._approval_receipts
        original=rt.hooks.deliver_approval
        rt.hooks.deliver_approval=lambda _:(_ for _ in ()).throw(ValueError('explicit pre-effect fixture failure'))
        base.choose(rt,meta);rt.hooks.deliver_approval=original
        inc=next(iter(ctx.incidents.values()));inc.state='RESOLVED_WITHOUT_ACTION';ctx.persist()
        before=rt.repo.get_approval(meta['wid'],meta['tenant']);save('before',before)
        check('real approval starts FAILED without command',before['status']=='FAILED' and not meta['commands'])
        args=(meta['wid'],'[회귀 검사] PG 승인 폐기 검사기','role:prod-mgr','[회귀 검사] 시험 종료 — 실패한 승인을 거둠','same-request')
        preview=rt.preview_approval_discard(*args[:3]);save('preview',preview)
        check('real enterprise complete ledger reports no effect',preview['enterprise_receipts']==[] and preview['can_discard'])
        update=rt.repo.update_instance
        rt.repo.update_instance=lambda _:(_ for _ in ()).throw(OSError('explicit last write failure'))
        try:rt.discard_approval(*args)
        except OSError:pass
        else:raise AssertionError('injected failure did not surface')
        finally:rt.repo.update_instance=update
        check('PG rollback preserves original approval',rt.repo.get_approval(meta['wid'],meta['tenant'])==before)
        check('PG rollback preserves submitted task and running instance',rt.repo.get_workitem(meta['wid'])['status']=='SUBMITTED'
              and rt.repo.get_instance(meta['pid'])['status']=='RUNNING')
        def discard(_):
            other=base.instances.InstanceRuntime(base.procdb.PgRepo(base.DSN),rt.defn,base.instance_mode._hooks(ctx),tenant_id=meta['tenant'])
            return other.discard_approval(*args)
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(discard,range(4)))
        after=rt.repo.get_approval(meta['wid'],meta['tenant']);save('after',after)
        check('four real PG dispatchers return same committed discard',all(r==after for r in results) and after['status']=='DISCARDED')
        events=rt.repo.list_events(proc_inst_id=meta['pid'])
        check('only one discard event exists',sum(e['job_id']=='APPROVAL_DISCARDED' for e in events)==1)
        check('consent payload and original failure remain',before['payload']==after['payload'] and before['error']==after['error'])
        store.db.close();store=None
        restarted,restored,store=base.new_runtime(meta);restored.approval_receipts=base.process_main._approval_receipts
        replay=restarted.discard_approval(*args)
        check('SQLite reopen and fresh PG runtime replay same result',replay==after)
        restarted.poll_once()
        check('cancelled instance has no active tasks or PLC effect',restarted.repo.get_instance(meta['pid'])['status']=='CANCELLED'
              and all(w['status'] in {'DONE','CANCELLED'} for w in restarted.repo.list_workitems(proc_inst_id=meta['pid'],limit=None)) and not meta['commands'])
        save('instance',restarted.instance_view(meta['pid']));save('events',events)
    except BaseException:
        save('failure',{'traceback':traceback.format_exc()});raise
    finally:
        if store:store.db.close()
        save('result',{'checks':checks,'scope':__doc__,'fixtures':base.FIXTURES})
    print(f'{len(checks)}/{len(checks)} passed',flush=True)


if __name__=='__main__':main()
