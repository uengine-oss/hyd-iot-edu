"""Deployed policy authoring -> MCP calculation -> approval invalidation.

Restores the reviewed original policy and removes only owned PG/InputData fixtures.
No Codex invocation, submitted decision, or PLC command.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import uuid

import psycopg
from psycopg import sql
from probe_physical_facts import http


def mcp(name, params):
    code = '''import asyncio,json
from fastmcp import Client
async def main():
 async with Client('http://127.0.0.1:8198/mcp',timeout=45) as c:
  r=await c.call_tool(NAME,PARAMS)
  print(next(x.text for x in r.content if getattr(x,'type',None)=='text'))
asyncio.run(main())
'''.replace('NAME',repr(name)).replace('PARAMS',repr(params))
    proc=subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-'],
        input=code,text=True,encoding='utf8',capture_output=True,timeout=60)
    if proc.returncode: raise RuntimeError(proc.stderr)
    result=json.loads(proc.stdout)
    if result['result']!='ok': raise RuntimeError(str(result))
    return result['document']


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True)
    out=Path(ap.parse_args().out); out.mkdir(parents=True,exist_ok=False)
    path='/api/kg/ranking-policy/rule%3Arank-value'
    original=http(8080,path)
    if not original['policy']: raise RuntimeError('install and review initial policy first')
    current=original; batch=None; token=uuid.uuid4().hex[:10]; table='A069 priority '+token
    report={'scope':'real HTTP/Neo4j/PG/MCP/approval; no Codex or PLC', 'original':original,'checks':{}}
    args=dict(asset='HYD-01',pattern='COOLER_DEGRADATION',cause='cause:cooler-fin-fouling',failure_mode='fm:cooling-loss')
    def save():
        (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    def check(name, value):
        report['checks'][name]=bool(value); print(('PASS ' if value else 'FAIL ')+name,flush=True);save()
    def request(policy, annotation='A069 explicit test formula'):
        return dict(policy=policy,annotation=annotation,expected_revision=current['revision'],
                    request_id=str(uuid.uuid4()),reason='[회귀 검사] A069 순위 정책 실행 중 변경 검증',by='[회귀 검사] A069 검사기')
    def update(policy, annotation='A069 explicit test formula'):
        nonlocal current
        body=request(policy,annotation); current=http(8080,path,body,'PUT')
        report.setdefault('writes',[]).append({'request':body,'result':current});save()
        return body
    def evaluate(name):
        result=mcp('evaluate_cards',args); report[name]=result;save(); return result
    def policy(expr,inputs=None):
        return {'version':1,'inputs':inputs or {},'components':{'value':expr},'tieBreak':'lower_approver'}
    def rejected(body,status):
        try: http(8080,path,body,'PUT')
        except urllib.error.HTTPError as exc:
            report.setdefault('rejections',[]).append({'status':exc.code,'body':exc.read().decode()});save()
            return exc.code==status
        return False
    with psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres',autocommit=True) as db:
        try:
            low_body=update(policy('-forecast_ts1'))
            low=evaluate('low_forecast')
            check('stored_policy_reaches_MCP',low['result']['rankRule']['rankingPolicy']==current['policy'])
            update(policy('forecast_ts1'))
            high=evaluate('high_forecast')
            check('changed_formula_reverses_recommendation',low['recommended']!=high['recommended'])
            for name,result,direction in [('lowest',low,-1),('highest',high,1)]:
                opts=[o for o in result['result']['options'] if o['feasible']]
                check(name+'_actual_forecast_rank',result['recommended']==max(opts,key=lambda o:direction*next(x['value'] for x in o['forecast'] if x['variable']=='sv:ts1'))['id'])
            old=dict(low,options=low['result']['options'])
            assessment=http(8091,'/api/agent/approval-check',dict(decision=old,option=low['recommended'],role='role:prod-mgr'))
            report['changed_policy_assessment']=assessment
            check('old_card_requires_new_policy_review',not assessment['allowed'] and any('policy_sha256' in r or 'rankingEvidence' in r for r in assessment['reasons']))
            replay=http(8080,path,low_body,'PUT')
            check('request_replay_returns_original_receipt_without_reverting_live_policy',replay==report['writes'][0]['result'] and http(8080,path)['revision']==current['revision'])
            stale=dict(low_body,request_id=str(uuid.uuid4()))
            check('stale_revision_rejected',rejected(stale,409))
            bad=request(policy('__import__("os").getcwd()'))
            check('non_arithmetic_code_rejected_before_write',rejected(bad,400))
            bad=request(policy('x',{'x':'no_such_input_'+token}))
            check('unbound_input_rejected_before_write',rejected(bad,400))
            check('rejections_leave_live_policy_unchanged',http(8080,path)['revision']==current['revision'])
            update(policy('1 / (forecast_ts1 - forecast_ts1)'))
            failed=evaluate('arithmetic_failure')
            check('runtime_error_does_not_fall_back_to_fixed_formula',failed['status']=='FAILED' and not failed.get('recommended'))
            ddl=sql.SQL('create table {} (asset text primary key, priority numeric(10,3))').format(sql.Identifier('ent',table)).as_string()
            db.execute(ddl)
            db.execute(sql.SQL('grant select on {} to hyd_enterprise_reader').format(sql.Identifier('ent',table)))
            db.execute(sql.SQL('insert into {} values (%s,%s)').format(sql.Identifier('ent',table)),('HYD-01',100))
            key='ent.'+sql.Identifier(table).as_string()
            plan=http(8080,'/api/kg/ddl/preview',dict(text=ddl,filename='a069.sql',selection={key:['priority']},systems={key:'sys:mes'}))
            batch=plan['batch'];report['plan']=plan;save();http(8080,'/api/kg/ddl/commit',plan)
            variable=plan['inputs'][0]['variable']
            update(policy('priority if production == "keep" else 0',{'priority':variable}))
            positive=evaluate('positive_priority')
            check('new_physical_column_used_by_authored_formula',positive['recommended']=='skill:fan-max' and positive['facts'][variable]=='100.000')
            old=dict(positive,options=positive['result']['options'])
            db.execute(sql.SQL('update {} set priority=-100').format(sql.Identifier('ent',table)))
            negative=evaluate('negative_priority')
            check('actual_business_change_reverses_recommendation',negative['recommended']!='skill:fan-max' and negative['facts'][variable]=='-100.000')
            assessment=http(8091,'/api/agent/approval-check',dict(decision=old,option='skill:fan-max',role='role:prod-mgr'))
            report['physical_input_assessment']=assessment
            check('rank_only_physical_input_change_requires_review',not assessment['allowed'] and any(variable in r for r in assessment['reasons']))
            db.execute(sql.SQL('update {} set priority=NULL').format(sql.Identifier('ent',table)))
            missing=evaluate('unknown_priority')
            check('unknown_policy_input_withholds_recommendation',missing['status']=='FAILED' and not missing.get('recommended'))
        finally:
            # CAS restore: never overwrite another writer's intervening change.
            update(original['policy'],original['annotation'])
            check('original_policy_restored',current['policy']==original['policy'] and current['annotation']==original['annotation'])
            if batch: http(8080,'/api/kg/ingests/'+urllib.parse.quote(batch,safe=''),method='DELETE')
            db.execute(sql.SQL('drop table if exists {}').format(sql.Identifier('ent',table)))
            report['fixture_cleanup']=True;save()
    return 0 if report['checks'] and all(report['checks'].values()) else 1


if __name__=='__main__': raise SystemExit(main())
