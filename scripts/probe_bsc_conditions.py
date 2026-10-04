"""Owned real PG/graph fixture -> BSC condition authoring -> MCP/approval.

No decision submission, Codex call or PLC command. Receipts remain as audit data.
"""
import argparse
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import uuid

import psycopg
from psycopg import sql
from neo4j import GraphDatabase
from probe_physical_facts import http
from probe_ranking_policy import mcp


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True)
    out=Path(ap.parse_args().out); out.mkdir(parents=True,exist_ok=False)
    token=uuid.uuid4().hex[:10]; table='A070 condition '+token
    ids={n:'a070:'+token+':'+n for n in ('weak','strong','measure')}
    description='A070 reviewed explicit applicability'
    report=dict(scope='real PG/graph/API/MCP/approval; no Codex or PLC',ids=ids,table=table,checks={})
    batch=None; current=None
    args=dict(asset='HYD-01',pattern='COOLER_DEGRADATION',cause='cause:cooler-fin-fouling',failure_mode='fm:cooling-loss')
    def save():
        (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,value):
        report['checks'][name]=bool(value); print(('PASS ' if value else 'FAIL ')+name,flush=True); save()
    env=dict(x.split('=',1) for x in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    with GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1))) as graph, psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres',autocommit=True) as db:
        def cypher(query,**params):
            with graph.session() as session: return session.run(query,**params).data()
        def set_value(value):
            db.execute(sql.SQL('update {} set value=%s').format(sql.Identifier('ent',table)),(value,))
        def policy(expression='x > 1',source='fact',variable=None):
            return dict(version=1,description=description,inputs={'x':dict(source=source,variable=variable or input_variable)},expression=expression)
        def body(value):
            return dict(policy=value,expected_revision=current['revision'],request_id=str(uuid.uuid4()),by='A070 probe',reason='controlled explicit BSC condition verification')
        def update(value):
            nonlocal current
            request=body(value); current=http(8080,path,request,'PUT')
            report.setdefault('writes',[]).append(dict(request=request,result=current)); save(); return request
        def rejected(request,status):
            try: http(8080,path,request,'PUT')
            except urllib.error.HTTPError as exc:
                report.setdefault('rejections',[]).append(dict(status=exc.code,body=exc.read().decode())); save(); return exc.code==status
            return False
        def evaluate(name):
            result=mcp('evaluate_cards',args); report[name]=result; save()
            option=next(o for o in result['result']['options'] if o['id']=='skill:fan-max')
            paths=[p for p in option['tradeoffEvaluation'] if p['measure']==ids['measure']]
            effects=[e for e in option['gains']+option['losses'] if e['measure']==ids['measure']]
            return result,paths,effects
        try:
            ddl=sql.SQL('create table {} (asset text primary key,value numeric(10,3))').format(sql.Identifier('ent',table)).as_string()
            db.execute(ddl); db.execute(sql.SQL('grant select on {} to hyd_enterprise_reader').format(sql.Identifier('ent',table)))
            db.execute(sql.SQL('insert into {} values (%s,%s)').format(sql.Identifier('ent',table)),('HYD-01',2.125))
            key='ent.'+sql.Identifier(table).as_string()
            plan=http(8080,'/api/kg/ddl/preview',dict(text=ddl,filename='a070.sql',selection={key:['value']},systems={key:'sys:mes'}))
            batch=plan['batch']; report['plan']=plan; save(); http(8080,'/api/kg/ddl/commit',plan)
            input_variable=plan['inputs'][0]['variable']
            cypher('MATCH (s:Skill {id:"skill:fan-max"}) CREATE (w:StateVariable {id:$weak,name:"A070 weak"}), (h:StateVariable {id:$strong,name:"A070 strong"}), (m:Measure {id:$measure,name:"A070 measure",direction:"UP"}), (s)-[:AFFECTS {sign:1}]->(w), (s)-[:AFFECTS {sign:1}]->(h), (w)-[:INFLUENCES {sign:1,strength:"low"}]->(m), (h)-[:INFLUENCES {sign:1,strength:"high",condition:$description}]->(m)',**ids,description=description)
            raw=mcp('tradeoffs',{'skill_ids':['skill:fan-max']}); report['raw_tradeoffs']=raw; save()
            # The tool document is the list returned by KG.tradeoffs.
            rows=raw if isinstance(raw,list) else raw.get('rows',raw.get('tradeoffs',[]))
            own=[r for r in rows if r['measure']==ids['measure']]
            check('distinct_path_weight_and_condition_pairs_preserved',len(own)==2 and sorted((r['weight'],r['conds']) for r in own)==[(.3,[]),(1.0,[description])])
            conditions=http(8080,'/api/kg/bsc/conditions')
            rows=conditions if isinstance(conditions,list) else conditions.get('conditions',[])
            current=next(r for r in rows if r['source']==ids['strong'] and r['target']==ids['measure'])
            path='/api/kg/bsc/conditions/'+urllib.parse.quote(current['key'],safe='')
            first=update(policy())
            positive,paths,effects=evaluate('positive')
            check('true_condition_uses_full_strong_path',len(paths)==2 and all(p['status']=='TRUE' for p in paths) and len(effects)==1 and effects[0]['weight']==1)
            old=dict(positive,options=positive['result']['options'])
            baseline=http(8091,'/api/agent/approval-check',dict(decision=old,option='skill:fan-max',role='role:prod-mgr'))
            report['baseline_approval']=baseline; check('unchanged_current_card_can_be_approved',baseline['allowed'])
            set_value(.5)
            negative,paths,effects=evaluate('negative')
            check('false_strong_path_excluded_weak_path_retained',sorted(p['status'] for p in paths)==['FALSE','TRUE'] and len(effects)==1 and effects[0]['weight']==.3)
            assessment=http(8091,'/api/agent/approval-check',dict(decision=old,option='skill:fan-max',role='role:prod-mgr'))
            report['changed_approval']=assessment
            check('changed_bsc_fact_invalidates_old_consent',not assessment['allowed'] and any(input_variable in r or 'rankingEvidence' in r for r in assessment['reasons']))
            set_value(None)
            _,paths,effects=evaluate('unknown')
            check('unknown_only_adds_unconfirmed_increment',sorted((e['conditionStatus'],e['weight']) for e in effects)==[('TRUE',.3),('UNKNOWN',.7)] and any(p['status']=='UNKNOWN' for p in paths))
            set_value(2.125); update(policy('x > 3'))
            _,paths,effects=evaluate('changed_threshold')
            check('reviewed_expression_changes_applicability',len(effects)==1 and effects[0]['weight']==.3)
            replay=http(8080,path,first,'PUT')
            live=next(r for r in http(8080,'/api/kg/bsc/conditions') if r['key']==current['key'])
            check('replay_returns_receipt_without_reverting_policy',replay==report['writes'][0]['result'] and live['revision']==current['revision'])
            check('stale_revision_rejected',rejected(dict(first,request_id=str(uuid.uuid4())),409))
            check('different_source_text_rejected',rejected(body(dict(policy(),description='unreviewed text')),400))
            check('missing_binding_rejected',rejected(body(policy(variable='missing:'+token)),400))
            check('executable_code_rejected',rejected(body(policy('__import__("os").getcwd()')),400))
            update(None)
            _,paths,effects=evaluate('cleared')
            check('cleared_interpretation_keeps_original_text_unknown',any(p['status']=='UNKNOWN' and description in p['conds'] for p in paths) and any(e['conditionStatus']=='UNKNOWN' for e in effects))
            update(policy('x < 100',source='forecast',variable='sv:ts1'))
            forecast,paths,effects=evaluate('forecast')
            checks=[c for p in paths for c in p['checks'] if c['description']==description]
            predicted=next(x['value'] for o in forecast['result']['options'] if o['id']=='skill:fan-max' for x in o['forecast'] if x['variable']=='sv:ts1')
            check('candidate_forecast_is_explicit_distinct_input',checks[0]['inputs']['x']==dict(source='forecast',variable='sv:ts1',value=predicted) and checks[0]['status']=='TRUE')
        finally:
            cypher('MATCH (n) WHERE n.id IN $ids DETACH DELETE n',ids=list(ids.values()))
            if batch: http(8080,'/api/kg/ingests/'+urllib.parse.quote(batch,safe=''),method='DELETE')
            db.execute(sql.SQL('drop table if exists {}').format(sql.Identifier('ent',table)))
            report['fixture_cleanup']=True; save()
    return 0 if report['checks'] and all(report['checks'].values()) else 1


if __name__=='__main__': raise SystemExit(main())
