"""Real reader/Neo4j/MCP/HTTP evidence boundaries. Own fixture graph, no plant writes."""
import json
from pathlib import Path
import subprocess

OUT = Path('.evidence/reaudit/a053-live')
OUT.mkdir(exist_ok=True)
code = r"""import asyncio,json,time,uuid,urllib.request,urllib.error
from agentsvc.tools.mcp_tsdb import TimeSeriesDB
from neo4j import GraphDatabase
from fastmcp import Client

def decode(result):return json.loads(next(x.text for x in result.content if getattr(x,'type',None)=='text'))
async def main():
 result={};checks={}
 def check(name,ok):
  checks[name]=bool(ok)
  if not ok:raise AssertionError(name)
 for url in ['http://127.0.0.1:8198/healthz','http://agent:8091/healthz']:
  for _ in range(30):
   try:
    with urllib.request.urlopen(url,timeout=2) as r:assert json.load(r)['ok']
    break
   except (OSError,AssertionError):await asyncio.sleep(.5)
  else:raise RuntimeError('service not ready: '+url)
 db=TimeSeriesDB()
 base=dict(expect='gt',threshold=1.2)
 queries=[('precision','select 1.20004', 'PASS'),('zero','select 0','FAIL'),
          ('empty',"select avg(value) from tag_1s where asset='A053-NO-SUCH-ASSET'",'UNKNOWN'),
          ('bad_column','select missing_value from tag_1s','UNKNOWN'),
          ('multi_row','select value from tag_1s limit 2','UNKNOWN'),
          ('multi_column','select 1,2','UNKNOWN'),('null','select null','UNKNOWN'),
          ('nan',"select cast('NaN' as double precision)",'UNKNOWN'),
          ('infinity',"select cast('Infinity' as double precision)",'UNKNOWN'),
          ('boolean','select true','UNKNOWN'),('text',"select '9'",'UNKNOWN')]
 result['scalars']=db.evaluate([dict(base,id=name,sql=sql) for name,sql,_ in queries],'HYD-01')
 for name,sql,status in queries:
  row=result['scalars'][name]
  check('scalar_'+name,row['status']==status and (row['passed'] is None if status=='UNKNOWN' else row['passed']==(status=='PASS')))
 check('no_precomparison_rounding',result['scalars']['precision']['value']==1.20004)
 check('query_error_is_preserved',result['scalars']['bad_column']['error_kind']=='INVALID' and bool(result['scalars']['bad_column']['error']))
 check('query_after_sql_error_still_executes',result['scalars']['multi_row']['error']=='Evidence SQL must return exactly one scalar')
 nonce='a053-'+uuid.uuid4().hex
 pattern=nonce.upper()
 driver=GraphDatabase.driver('bolt://neo4j:7687',auth=('neo4j','hydpass123'))
 def graph(query,**params):
  with driver.session() as s:return [r.data() for r in s.run(query,fixture=nonce,**params)]
 graph('''CREATE (p:AnomalyPattern:A053Fixture {id:$fixture,code:$pattern,name:'A053 evidence fixture',fixture:$fixture}),
  (s:Symptom:A053Fixture {id:$fixture+'/s',name:'fixture symptom',fixture:$fixture}),
  (f:FailureMode:A053Fixture {id:$fixture+'/f',name:'fixture failure',fixture:$fixture}),
  (c1:Cause:A053Fixture {id:$fixture+'/c1',name:'known candidate',prior:0.5,fixture:$fixture}),
  (c2:Cause:A053Fixture {id:$fixture+'/c2',name:'unknown alternative',prior:0.9,fixture:$fixture}),
  (e1:Evidence:A053Fixture {id:$fixture+'/e1',name:'known numeric fixture',weight:1.0,expect:'gt',threshold:0.0,sql:'select 1',fixture:$fixture}),
  (e2:Evidence:A053Fixture {id:$fixture+'/e2',name:'invalid column fixture',weight:1.0,expect:'gt',threshold:0.0,sql:'select missing_value from tag_1s',fixture:$fixture}),
  (p)-[:DETECTS]->(s)-[:INDICATES]->(f), (c1)-[:CAUSES]->(f), (c2)-[:CAUSES]->(f),
  (c1)-[:EVIDENCED_BY]->(e1), (c2)-[:EVIDENCED_BY]->(e2)''',pattern=pattern)
 result['fixture']=dict(id=nonce,pattern=pattern,explicit_synthetic_rules=True)
 try:
  async with Client('http://127.0.0.1:8198/mcp',timeout=30) as client:
   async def diagnose():return decode(await client.call_tool('diagnose',{'asset':'HYD-01','pattern':pattern}))
   result['invalid']=await diagnose()
   invalid=result['invalid']['document']
   check('live_mcp_withholds_unknown_alternative',invalid['withheld'] and invalid['top_cause'] is None and invalid['card'] is None)
   ev=next(c for c in invalid['causes'] if c['id']==nonce+'/c2')['evidence'][0]
   check('live_mcp_preserves_query_error',ev['status']=='UNKNOWN' and ev['passed'] is None and ev['error_kind']=='INVALID')
   req=urllib.request.Request('http://agent:8091/api/agent/decide',data=json.dumps({'asset':'HYD-01','pattern':pattern,'facts':{'cause':nonce+'/c1'}}).encode(),headers={'Content-Type':'application/json'},method='POST')
   try:
    with urllib.request.urlopen(req,timeout=15) as r:result['manual']=dict(status=r.status,body=json.load(r))
   except urllib.error.HTTPError as e:result['manual']=dict(status=e.code,body=json.load(e))
   check('live_manual_override_cannot_skip_unknown',result['manual']['status']==409 and result['manual']['body']['detail']['evidence_status']['status']=='UNKNOWN')
   graph("MATCH (e:Evidence:A053Fixture {id:$id,fixture:$fixture}) SET e.sql=$sql",id=nonce+'/e2',sql="select avg(value) from tag_1s where asset='A053-NO-SUCH-ASSET'")
   result['empty']=await diagnose()
   empty=result['empty']['document']
   ev=next(c for c in empty['causes'] if c['id']==nonce+'/c2')['evidence'][0]
   check('live_no_data_is_unknown_not_failed_condition',empty['withheld'] and ev['reason']=='NO_DATA' and ev['passed'] is None)
   graph("MATCH (e:Evidence:A053Fixture {id:$id,fixture:$fixture}) SET e.sql='select 2'",id=nonce+'/e2')
   result['repaired']=await diagnose()
   repaired=result['repaired']['document']
   check('live_rule_repair_resumes_same_pattern',not repaired['withheld'] and repaired['top_cause']==nonce+'/c2')
   graph("MATCH (e:Evidence:A053Fixture {fixture:$fixture}) SET e.sql='select 0'")
   result['all_false']=await diagnose()
   check('live_disproven_candidates_do_not_choose_first',result['all_false']['document']['withheld'] and result['all_false']['document']['evidence_status']['status']=='UNSUPPORTED')
   result['normal']=decode(await client.call_tool('diagnose',{'asset':'HYD-01','pattern':'COOLER_DEGRADATION'}))
   check('existing_diagnosis_recovers_normally',result['normal']['result']=='ok' and not result['normal']['document']['withheld'])
 finally:
  graph('MATCH (n:A053Fixture {fixture:$fixture}) DETACH DELETE n')
  result['remaining_fixture_nodes']=graph('MATCH (n:A053Fixture {fixture:$fixture}) RETURN count(n) AS n')[0]['n']
  driver.close()
  check('only_own_fixture_graph_removed',result['remaining_fixture_nodes']==0)
 result['checks']=checks
 print(json.dumps(result,ensure_ascii=False,default=str))
asyncio.run(main())
"""
run = subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-'], input=code,
                     text=True, encoding='utf8', capture_output=True, timeout=150)
(OUT/'result.json').write_text(run.stdout,encoding='utf8')
(OUT/'stderr.log').write_text(run.stderr,encoding='utf8')
assert run.returncode == 0, run.stderr
data=json.loads(run.stdout)
(OUT/'checks.json').write_text(json.dumps(data['checks'],indent=2),encoding='utf8')
for name,ok in data['checks'].items():print(('PASS ' if ok else 'FAIL ')+name)
assert all(data['checks'].values())
