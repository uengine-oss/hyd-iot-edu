"""Actual PostgreSQL receipt checks in a unique, retained isolated schema.

Does not change the running consumer or prove Kafka offset/claim recovery.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import uuid
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'it/process'), str(ROOT/'common')]
from procsvc.procdb import PgRepo
from procsvc.source_inbox import PgSourceInbox, source_record, kafka_record


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    schema='a033_receipts_'+uuid.uuid4().hex[:12]
    dsn=os.environ['SUPABASE_DSN']
    repo=PgRepo(dsn)
    checks=[]
    def check(name,condition):
        checks.append({'name':name,'passed':bool(condition)})
        print(('PASS ' if condition else 'FAIL ')+name,flush=True)
        assert condition,name
    try:
        with repo._conn() as c:
            # schema is locally generated hex, never an arbitrary identifier.
            c.execute('create schema '+schema)
            sql=(ROOT/'it/supabase/migrations/20261004000007_source_inbox.sql').read_text(encoding='utf-8')
            c.execute(sql.replace('public.process_source_',schema+'.process_source_'))
        scoped_dsn=repo._psycopg.conninfo.make_conninfo(dsn,options='-c search_path='+schema)
        repo=PgRepo(scoped_dsn);inbox=PgSourceInbox(repo,'receipt-test')
        policy={'definition':'alert_triage','version':'1.0','pattern':'NEW_SOURCE'}
        raw={'asset':'HYD-02','alertId':'receipt-test-1','state':'RAISE','pattern':'NEW_SOURCE'}
        first=inbox.receive(source_record('alerts',0,1,raw),policy)
        policy['version']='changed'
        repeat=inbox.receive(source_record('alerts',0,1,raw),policy)
        check('committed redelivery keeps receipt and original policy',first['id']==repeat['id'] and repeat['policy']['version']=='1.0')
        duplicate=inbox.receive(source_record('alerts',2,10,raw),policy)
        check('new Kafka delivery retained as duplicate of first policy',duplicate['id']!=first['id'] and duplicate['parent_id']==first['id'] and duplicate['status']=='DUPLICATE' and duplicate['policy']==first['policy'])
        changed=dict(raw,asset='HYD-03')
        conflict=inbox.receive(source_record('alerts',2,11,changed),policy)
        check('conflicting business payload retained and first unchanged',conflict['status']=='CONFLICT' and conflict['payload']==changed and inbox.get(first['id'])['payload']==raw)
        try:inbox.receive(source_record('alerts',0,1,changed),policy)
        except ValueError:check('same coordinates with different payload rejected',True)
        else:check('same coordinates with different payload rejected',False)
        other=PgSourceInbox(repo,'other-tenant')
        check('tenant read does not expose another receipt',other.get(first['id']) is None and other.list()==[])
        independent=other.receive(source_record('alerts',0,1,raw),policy)
        check('business and Kafka identity are tenant scoped',independent['id']!=first['id'] and independent['status']=='PENDING')
        clear=inbox.receive(source_record('alerts',0,2,dict(raw,state='CLEAR')))
        check('CLEAR retained independently of RAISE',clear['status']=='PENDING' and clear['kind']=='CLEAR' and clear['policy'] is None)
        ack={'asset':'HYD-02','cmdId':'receipt-cmd','result':'DONE','t':'first','tags':{'PS1':182}}
        a=inbox.receive(source_record('plant.status',0,1,ack))
        b=inbox.receive(source_record('plant.status',0,2,dict(ack,t='second',tags={'PS1':181})))
        d=inbox.receive(source_record('plant.status',0,3,dict(ack,result='REJECTED')))
        check('retained ACK heartbeat duplicates but contradictory outcome conflicts',a['status']=='PENDING' and b['status']=='DUPLICATE' and d['status']=='CONFLICT' and a['payload']!=b['payload'])
        invalid=inbox.receive(source_record('alerts',0,3,{'_raw':'malformed'}))
        check('malformed raw data visible as INVALID',invalid['status']=='INVALID' and invalid['payload']=={'_raw':'malformed'})
        def concurrent(index):
            return PgSourceInbox(PgRepo(scoped_dsn),'race').receive(source_record('alerts',index,5,raw),{'version':str(index)})
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(concurrent,range(8)))
        originals=[r for r in rows if r['parent_id'] is None]
        check('eight concurrent receivers retain one canonical business event',len(originals)==1 and sum(r['status']=='DUPLICATE' for r in rows)==7 and all(r['policy']==originals[0]['policy'] for r in rows))
        def same_origin(_):return concurrent(20)
        with ThreadPoolExecutor(max_workers=8) as pool:same=list(pool.map(same_origin,range(8)))
        check('eight same-coordinate receivers return one committed receipt',len({r['id'] for r in same})==1)
        reopened=PgSourceInbox(PgRepo(scoped_dsn),'receipt-test')
        check('new connection reads persisted original payload and policy',reopened.get(first['id'])==first)
        with repo.event_transaction('receipt-test-nesting'):
            try:inbox.receive(source_record('alerts',0,99,raw),policy)
            except RuntimeError:check('receipt cannot return before an outer transaction commits',True)
            else:check('receipt cannot return before an outer transaction commits',False)
        check('rejected nested receipt was not inserted',all(r['offset_no']!=99 for r in reopened.list()))
        wire=b'{"broken":\xff}'
        malformed=inbox.receive(kafka_record(SimpleNamespace(topic='alerts',partition=3,offset=30,value=wire)))
        check('malformed wire bytes survive storage exactly',malformed['status']=='INVALID'
              and base64.b64decode(inbox.get(malformed['id'])['wire_base64'])==wire)
        http=inbox.receive(source_record('alerts',None,None,raw,source='http'),policy)
        check('HTTP and Kafka correlate without fake offsets or new policy',http['status']=='DUPLICATE'
              and http['parent_id']==first['id'] and http['partition_no'] is None and http['policy']==first['policy'])
        check('HTTP retry reuses the exact receipt',inbox.receive(source_record('alerts',None,None,raw,source='http'),policy)['id']==http['id'])
        stamp='2026-10-04T06:00:02+00:00'
        latest={'asset':'HYD-03','t':stamp,'state':'RUN','tags':{'TS1':51}}
        new_state=inbox.receive(source_record('plant.status',4,1,latest))
        older=inbox.receive(source_record('plant.status',4,2,dict(latest,t='2026-10-04T06:00:01+00:00',state='TRIP')))
        check('out-of-order status preserves the newest source timestamp',new_state['status']==older['status']=='HANDLED'
              and reopened.latest_states()['HYD-03']==latest)
        invalid_state=inbox.receive(source_record('plant.status',4,3,dict(latest,t='no timestamp')))
        check('invalid timestamp is visible and cannot overwrite latest state',invalid_state['status']=='INVALID'
              and reopened.latest_states()['HYD-03']==latest)
        new_ack=dict(ack,t='2026-10-04T06:00:03Z',tags={'TS1':50})
        heartbeat=inbox.receive(source_record('plant.status',4,4,new_ack))
        check('duplicate retained ACK still updates its latest physical observation',heartbeat['status']=='DUPLICATE'
              and reopened.latest_states()['HYD-02']==new_ack)
        work=PgSourceInbox(PgRepo(scoped_dsn),'claims')
        work.receive(source_record('alerts',0,10,dict(raw,state='CLEAR')))
        work.receive(source_record('alerts',0,11,raw),policy)
        work.receive(source_record('alerts',0,12,dict(raw,asset='HYD-03',alertId='other-alarm')),policy)
        def claim(index):return PgSourceInbox(PgRepo(scoped_dsn),'claims').claim('worker-'+str(index))
        with ThreadPoolExecutor(max_workers=8) as pool:claims=[r for r in pool.map(claim,range(8)) if r]
        check('concurrent schedulers own at most one receipt per asset',len(claims)==2 and len({r['asset'] for r in claims})==2)
        clear_claim=next(r for r in claims if r['kind']=='CLEAR')
        other_claim=next(r for r in claims if r['asset']=='HYD-03')
        waiting=work.defer(clear_claim,'RAISE not received yet',delay_s=3600)
        check('unmatched CLEAR stays visible without consuming failure budget',waiting['status']=='WAITING' and waiting['failures']==0)
        raised=work.claim('raise-handler')
        check('waiting CLEAR does not block the RAISE it needs',raised['kind']=='RAISE' and raised['asset']=='HYD-02')
        check('explicit results settle live owned claims',work.finish(raised,{'fixture':'instance-observed'})['status']=='HANDLED'
              and work.finish(other_claim,{'fixture':'other-instance-observed'})['status']=='HANDLED')
        check('future waiting receipt is not prematurely polled',work.claim('early') is None)
        with repo._conn() as c:
            c.execute("update process_source_inbox set next_attempt_at=now()-interval '1 second' where tenant_id='claims' and id=%s",(waiting['id'],))
        old=work.claim('same-owner')
        check('waiting receipt reclaims the same identity with a new token',old['id']==waiting['id'] and old['claim_token']!=clear_claim['claim_token'] and old['failures']==0)
        with repo._conn() as c:
            c.execute("update process_source_inbox set lease_until=now()-interval '1 second' where tenant_id='claims' and id=%s",(old['id'],))
        check('expired owner cannot renew or finish even before reassignment',work.renew(old) is None and work.finish(old,{'fixture':'late'}) is None)
        new=work.claim('same-owner',max_failures=2)
        check('expired claim recovers with distinct token and recorded failure',new['id']==old['id'] and new['claim_token']!=old['claim_token'] and new['failures']==1
              and any(h['event']=='lease_expired' for h in new['history']))
        check('same owner name cannot bypass stale-token fencing',work.finish(old,{'fixture':'late'}) is None and work.defer(old,'late') is None and work.fail(old,'late') is None)
        check('current owner may renew its lease',work.renew(new,lease_s=120)['claim_token']==new['claim_token'])
        failed=work.fail(new,'fixture database unavailable',max_failures=2)
        check('failure limit stays FAILED and is not claimed as successful work',failed['status']=='FAILED' and failed['failures']==2 and failed['handled_at'] is None and work.claim('no-auto-retry') is None)
        original=deepcopy(failed)
        retried=work.retry_failed(failed['id'],by='[회귀 검사] 시험 검토자',reason='[회귀 검사] 시험 의존 서비스 복구')
        check('explicit retry retains identity payload policy and error history',retried['id']==original['id'] and retried['payload']==original['payload'] and retried['policy']==original['policy']
              and retried['failures']==0 and retried['history'][-1]['event']=='explicit_retry')
        final=work.claim('final-handler')
        check('another tenant cannot settle a known claim',other.finish(final,{'fixture':'wrong tenant'}) is None)
        complete=work.finish(final,{'fixture':'correlated CLEAR observed'})
        check('handled receipt is not completed or explicitly retried twice',complete['status']=='HANDLED' and complete['handled_at']
              and work.finish(final,{'fixture':'duplicate'}) is None and work.retry_failed(final['id'],by='[회귀 검사] 시험 검토자',reason='[회귀 검사] 중복 재시도') is None)
        (out/'claim-receipts.json').write_text(json.dumps(work.list(),ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'receipts.json').write_text(json.dumps(reopened.list(),ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        (out/'result.json').write_text(json.dumps({'schema':schema,'checks':checks,
            'scope':'Actual PG isolated receipt table only; no consumer, offset, claim or physical recovery proof.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(checks)}/{len(checks)} passed; schema retained: {schema}',flush=True)


if __name__=='__main__':main()
