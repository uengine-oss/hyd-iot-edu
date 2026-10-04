"""Actual PG -> deployed MCP metadata/query -> DDL input contract.

Only uniquely named fixture tables are created/dropped. No agent invocation.
The same checks run before and after deployment; failures remain evidence.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'it/process'))
import psycopg
from psycopg import sql
from procsvc import ingest
from neo4j import GraphDatabase


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex[:10]
    parent, table, view = 'A067 parent '+token, 'A067 order '+token, 'A067 view '+token
    column = 'due "hours"'
    comment = "MES: actual fixture; O'Brien\nsecond line /* source */"
    col_comment = "remaining time (h); keep 'quotes' and\nline breaks"
    report = {'scope': 'real PG and deployed MCP; no Codex', 'fixtures': [parent,table,view], 'checks': {}}
    batches=[]
    def http(path,body=None,method=None):
        req=urllib.request.Request('http://127.0.0.1:8080'+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type':'application/json'},method=method)
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    def check(name, value):
        report['checks'][name] = bool(value)
        print(('PASS ' if value else 'FAIL ')+name, flush=True)
    def save():
        (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def remote():
        query = sql.SQL('select {} from {} where asset={}').format(sql.Identifier(column),sql.Identifier('ent',table),sql.Literal('HYD-01')).as_string()
        payload = json.dumps({'sql':query},ensure_ascii=False)
        code = '''import asyncio,json
from fastmcp import Client
async def main():
 async with Client('http://127.0.0.1:8199/mcp',timeout=30) as c:
  names=[t.name for t in await c.list_tools()]
  def text(r): return next(x.text for x in r.content if getattr(x,'type',None)=='text')
  result={'tools':names,'ddl':text(await c.call_tool('describe_schema',{}))}
  if 'describe_catalog' in names: result['catalog']=json.loads(text(await c.call_tool('describe_catalog',{})))
  result['query']=json.loads(text(await c.call_tool('query',PAYLOAD)))
  print(json.dumps(result,ensure_ascii=False))
asyncio.run(main())
'''.replace('PAYLOAD',repr(json.loads(payload)))
        r=subprocess.run(['docker','exec','-i','hyd-iot-edu-enterprise-mcp-1','python','-'],input=code,text=True,encoding='utf8',capture_output=True,timeout=60)
        (out/'mcp-stderr.log').write_text(r.stderr,encoding='utf8')
        if r.returncode: raise RuntimeError(r.stderr)
        return json.loads(r.stdout)
    with psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres',autocommit=True) as db:
        try:
            db.execute(sql.SQL('create table {} (asset text primary key)').format(sql.Identifier('ent',parent)))
            db.execute(sql.SQL('create table {} (asset text primary key references {}(asset), {} numeric(10,3) not null, "select" text[])').format(sql.Identifier('ent',table),sql.Identifier('ent',parent),sql.Identifier(column)))
            db.execute(sql.SQL('comment on table {} is {}').format(sql.Identifier('ent',table),sql.Literal(comment)))
            db.execute(sql.SQL('comment on column {} is {}').format(sql.Identifier('ent',table,column),sql.Literal(col_comment)))
            db.execute(sql.SQL('insert into {} values (%s)').format(sql.Identifier('ent',parent)),('HYD-01',))
            db.execute(sql.SQL('insert into {} values (%s,%s,%s)').format(sql.Identifier('ent',table)),('HYD-01',2.125,['keep']))
            db.execute(sql.SQL('create view {} as select * from {}').format(sql.Identifier('ent',view),sql.Identifier('ent',table)))
            for name in [parent,table,view]:
                db.execute(sql.SQL('grant select on {} to hyd_enterprise_reader').format(sql.Identifier('ent',name)))
            report.update(remote()); save()
            actual=report['query'].get('document',{}).get('rows',[])
            check('quoted_identifier_query_returns_actual_value',len(actual)==1 and float(actual[0][0])==2.125)
            catalog=report.get('catalog',{}).get('document',{})
            rel=next((r for r in catalog.get('relations',[]) if r['name']==table),{})
            col=next((c for c in rel.get('columns',[]) if c['name']==column),{})
            check('catalog_preserves_database_identity',catalog.get('catalog')=='postgres' and catalog.get('schema')=='ent')
            check('catalog_preserves_comments',rel.get('comment')==comment and col.get('comment')==col_comment)
            check('catalog_preserves_precision',col.get('type')=='numeric(10,3)')
            check('catalog_contains_declared_fk',any(c['type']=='f' and parent in c['definition'] for c in rel.get('constraints',[])))
            check('view_kind_is_distinct',any(r['name']==view and r['kind']=='v' for r in catalog.get('relations',[])))
            try:
                parsed=ingest.parse_ddl(report['ddl'])
                t=next(t for t in parsed if t.name==table)
                c=next(c for c in t.columns if c.name==column)
                check('ddl_roundtrip_identifiers',True)
                check('ddl_roundtrip_comments',t.comment==comment and c.comment==col_comment)
                check('ddl_roundtrip_precision',c.type=='numeric(10,3)')
                check('view_not_ingested_as_table',all(t.name!=view for t in parsed))
                plan=ingest.plan([t],filename='actual-catalog.sql',batch='a067:'+token,selection={t.qualified:[column]},systems={t.qualified:'sys:mes'})
                i=plan['inputs'][0]
                q=ingest.tests_to_sql([{'variable':i['variable'],'operator':'<','value':3}],{i['variable']:i})['queries'][0]
                with psycopg.connect('postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@127.0.0.1:54322/postgres') as reader:
                    params=dict(q['params'],asset='HYD-01')
                    values=reader.execute(q['sql'],params).fetchall()
                check('physical_source_to_rule_sql_reads_actual_row',len(values)==1 and float(values[0][1])==2.125)
                report['input_plan']=plan; report['rule_query']=q
            except Exception as e:
                report['ddl_error']=str(e)
                check('ddl_roundtrip_identifiers',False)
            # Metadata refresh must observe a committed source change.
            db.execute(sql.SQL('comment on column {} is {}').format(sql.Identifier('ent',table,column),sql.Literal('changed source meaning')))
            fresh=remote(); report['after_change']=fresh
            cols=next((r['columns'] for r in fresh.get('catalog',{}).get('document',{}).get('relations',[]) if r['name']==table),[])
            check('metadata_refresh_observes_source_change',any(c['name']==column and c['comment']=='changed source meaning' for c in cols))
            if catalog:
                env=dict(x.split('=',1) for x in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
                key='ent.'+sql.Identifier(table).as_string()
                def preview(ddl):
                    return http('/api/kg/ddl/preview',{'text':ddl,'filename':'actual-catalog.sql',
                        'selection':{key:[column]},'systems':{key:'sys:mes'}})
                old_plan=preview(report['ddl']); new_plan=preview(fresh['ddl'])
                report['http_plans']=[old_plan,new_plan];save()
                iid=old_plan['inputs'][0]['id']
                check('http_preview_keeps_source_meaning',old_plan['inputs'][0]['name']==col_comment)
                with GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1))) as driver:
                    def graph():
                        with driver.session() as session:
                            return session.run('MATCH (i:InputData {id:$id})-[:SOURCED_FROM]->(s:System) RETURN i.name AS name,i.column AS column,s.id AS source',id=iid).data()
                    for current in [old_plan,new_plan]:
                        batches.append(current['batch']);http('/api/kg/ddl/commit',current)
                    check('same_batch_retry_has_durable_receipt',http('/api/kg/ddl/commit',new_plan).get('replayed') is True)
                    check('source_change_reingest_keeps_identity',new_plan['inputs'][0]['id']==iid and graph()==[{'name':'changed source meaning','column':column,'source':'sys:mes'}])
                    query=http('/api/kg/rules/sql',{'tests':[{'variable':new_plan['inputs'][0]['variable'],'operator':'<','value':3}]})['queries'][0]
                    with psycopg.connect('postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@127.0.0.1:54322/postgres') as reader:
                        values=reader.execute(query['sql'],dict(query['params'],asset='HYD-01')).fetchall()
                    check('http_graph_rule_query_reads_actual_source',len(values)==1 and float(values[0][1])==2.125)
                    http('/api/kg/ingests/'+urllib.parse.quote(batches[-1],safe=''),method='DELETE');batches.pop()
                    check('rollback_restores_original_meaning',graph()==[{'name':col_comment,'column':column,'source':'sys:mes'}])
                    http('/api/kg/ingests/'+urllib.parse.quote(batches[-1],safe=''),method='DELETE');batches.pop()
                    check('owned_input_removed_after_final_clear',graph()==[])
                report['http_plans']=[old_plan,new_plan];report['http_rule_query']=query
        finally:
            for batch in reversed(batches):
                http('/api/kg/ingests/'+urllib.parse.quote(batch,safe=''),method='DELETE')
            db.execute(sql.SQL('drop view if exists {}').format(sql.Identifier('ent',view)))
            db.execute(sql.SQL('drop table if exists {}').format(sql.Identifier('ent',table)))
            db.execute(sql.SQL('drop table if exists {}').format(sql.Identifier('ent',parent)))
            report['fixture_cleanup']=True;save()
    return 0 if all(report['checks'].values()) else 1


if __name__=='__main__':
    raise SystemExit(main())
