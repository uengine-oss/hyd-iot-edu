"""Actual PG/SQLite source delivery with isolated records and injected boundaries.

No live Kafka or PLC: hard process-death/consumer recovery remains a separate run.
"""
import argparse
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
from procsvc import engine,instances,instance_mode,main as service,machine,procdb
from procsvc.source_inbox import PgSourceInbox,source_record
from procsvc.source_delivery import SourceDelivery
from procsvc.store import Store


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    suffix=uuid.uuid4().hex[:10];tenant='a033-delivery-'+suffix;schema='a033_delivery_'+suffix
    repo=procdb.PgRepo(os.environ['SUPABASE_DSN'])
    with repo._conn() as c:
        c.execute('create schema '+schema)
        sql=(ROOT/'it/supabase/migrations/20261004000007_source_inbox.sql').read_text(encoding='utf-8')
        c.execute(sql.replace('public.process_source_',schema+'.process_source_'))
        c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,tenant))
    dsn=repo._psycopg.conninfo.make_conninfo(repo.dsn,options='-c search_path='+schema+',public')
    repo=procdb.PgRepo(dsn);inbox=PgSourceInbox(repo,tenant);store=Store(out/'incident.sqlite3')
    incidents={};book={};audits=[];checks=[]
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)});print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    def persist():store.save(incidents,book,audits)
    def no_effect(*a,**k):raise AssertionError('no command/CMMS effect is allowed in this storage probe')
    ctx=instance_mode.ProcessContext(incidents,book,{},20,persist,lambda *a,**k:None,lambda *a,**k:[],
        no_effect,no_effect,no_effect,lambda:None,no_effect)
    raw=json.loads((ROOT/'it/process/definitions/anomaly_response_v22.json').read_text(encoding='utf-8'))
    rt=instances.InstanceRuntime(repo,engine.Definition.from_dict(raw),instance_mode._hooks(ctx),tenant_id=tenant)
    def activate(runtime):
        instance_mode._runtime=runtime;service.incidents=incidents;service.persist=persist;service.source_inbox=inbox
        class Effects(machine.Effects):
            def emit_cmd(self,cmd):no_effect(cmd)
            def emit_audit(self,event):audits.append(event)
            def set_timer(self,*args):no_effect(args)
        service.Fx=lambda inc:Effects()
        return SourceDelivery(inbox,runtime,service._apply_source_event,owner=tenant+'-source')
    delivery=activate(rt)
    def run():return asyncio.run(delivery.run_once())
    def due(receipt_id):
        with repo._conn() as c:c.execute("update process_source_inbox set next_attempt_at=now()-interval '1 second' where tenant_id=%s and id=%s",(tenant,receipt_id))
    alert={'asset':'HYD-01','alertId':tenant+'-1','state':'RAISE','pattern':'COOLER_DEGRADATION'}
    policy=rt.alert_policy(alert['pattern'])
    try:
        first=inbox.receive(source_record('alerts',0,1,alert),policy)
        original=repo.insert_instance
        repo.insert_instance=lambda _:(_ for _ in ()).throw(OSError('fixture after Incident before PG'))
        run();repo.insert_instance=original
        check('Incident-only interruption leaves a visible retry receipt',inbox.get(first['id'])['status']=='PENDING'
              and inbox.get(first['id'])['failures']==1 and len(incidents)==1 and not repo.list_instances(tenant_id=tenant))
        store.db.close();store=Store(out/'incident.sqlite3');incidents.clear();incidents.update(store.restore()[0])
        later=deepcopy(raw);later['version']='fixture-later-default';later['alertPolicy']['patterns']['COOLER_DEGRADATION']['limit']=40
        rt=instances.InstanceRuntime(procdb.PgRepo(dsn),engine.Definition.from_dict(later),instance_mode._hooks(ctx),tenant_id=tenant)
        delivery=activate(rt);due(first['id']);settled=run()
        inst=repo.get_instance(settled['result']['instance'])
        check('new runtime rejoins same Incident using original version and criterion',settled['status']=='HANDLED'
              and inst['proc_def_version']==raw['version'] and len(incidents)==1 and next(iter(incidents.values())).recovery[2]==55)
        second=inbox.receive(source_record('alerts',0,2,dict(alert,alertId=tenant+'-2')),policy)
        finish=inbox.finish
        inbox.finish=lambda *a:(_ for _ in ()).throw(OSError('fixture after PG before receipt completion'))
        run();inbox.finish=finish
        check('PG-complete interruption remains retryable with existing instance',inbox.get(second['id'])['status']=='PENDING'
              and len(repo.list_instances(tenant_id=tenant))==2)
        due(second['id']);run()
        check('receipt retry observes existing instance without duplication',inbox.get(second['id'])['status']=='HANDLED'
              and len(repo.list_instances(tenant_id=tenant))==2 and len(incidents)==2)
        third=dict(alert,alertId=tenant+'-3')
        clear=inbox.receive(source_record('alerts',0,3,dict(third,state='CLEAR')))
        pending=run();check('early CLEAR waits visibly',pending['status']=='WAITING' and pending['failures']==0)
        raised=inbox.receive(source_record('alerts',0,4,third),policy);run();due(clear['id']);cleared=run()
        check('later RAISE unblocks original CLEAR without inventing physical recovery',cleared['status']=='HANDLED'
              and cleared['result']['state']=='RESOLVED_WITHOUT_ACTION' and cleared['result']['cleared']
              and cleared['result']['cmdId'] is None and inbox.get(raised['id'])['status']=='HANDLED')
        inc=incidents[settled['result']['incident']];inc.state='ESCALATED';inc.reason='PROCESS_RESTART_REVIEW';inc.cmd_id=tenant+'-cmd';persist()
        ack=inbox.receive(source_record('plant.status',1,1,{'asset':inc.asset,'cmdId':inc.cmd_id,'result':'DONE','t':'2026-10-04T06:20:00Z'}))
        run()
        check('late ACK is retained without overriding restart review',inbox.get(ack['id'])['status']=='HANDLED'
              and inc.state=='ESCALATED' and inc.reason=='PROCESS_RESTART_REVIEW' and inc.ack is None)
        failed=inbox.receive(source_record('alerts',0,5,dict(alert,alertId=tenant+'-api')),policy)
        claimed=inbox.claim('api-error-fixture');assert claimed['id']==failed['id']
        inbox.fail(claimed,'[회귀 검사] 시험 의존 서비스 사용 불가',max_failures=1)
        async def api_checks():
            import httpx
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),base_url='http://fixture') as client:
                listed=await client.get('/api/source-events',params={'status':'FAILED'})
                check('API exposes the failed original receipt and error',listed.status_code==200
                      and [r['id'] for r in listed.json()]==[failed['id']] and listed.json()[0]['error']=='[회귀 검사] 시험 의존 서비스 사용 불가')
                blank=await client.post(f'/api/source-events/{failed["id"]}/retry',json={'by':'','reason':''})
                check('API rejects retry without actor and reason',blank.status_code==400)
                retried=await client.post(f'/api/source-events/{failed["id"]}/retry',json={'by':'[회귀 검사] 시험 검토자','reason':'[회귀 검사] 의존 서비스 복구'})
                check('API records explicit same-event retry',retried.status_code==200 and retried.json()['id']==failed['id']
                      and retried.json()['status']=='PENDING' and retried.json()['history'][-1]['by']=='[회귀 검사] 시험 검토자')
                duplicate=await client.post(f'/api/source-events/{failed["id"]}/retry',json={'by':'[회귀 검사] 시험 검토자','reason':'[회귀 검사] 다시 시도'})
                check('API cannot reset nonfailed work or hide its status',duplicate.status_code==409)
                service.source_inbox=PgSourceInbox(repo,'another-tenant')
                hidden=await client.get(f'/api/source-events/{failed["id"]}')
                check('API receipt lookup is tenant scoped',hidden.status_code==404)
                service.source_inbox=inbox
        asyncio.run(api_checks())
        rows=inbox.list();(out/'receipts.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'instances.json').write_text(json.dumps(repo.list_instances(tenant_id=tenant),ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        (out/'result.json').write_text(json.dumps({'tenant':tenant,'schema':schema,'checks':checks,
            'scope':'actual PG and SQLite plus ASGI HTTP routing; injected write boundaries/reopened stores/new default; no actual Kafka, deployed HTTP, PLC or process kill'},ensure_ascii=False,indent=2),encoding='utf-8')
        store.db.close()
    print(f'{len(checks)}/{len(checks)} passed; isolated tenant/schema retained',flush=True)


if __name__=='__main__':main()
