"""Deployed MCP protocol and legacy evidence checks; no coding agent invocation."""
import json
from pathlib import Path
import subprocess

OUT=Path('.evidence/reaudit/a051-mcp');OUT.mkdir(exist_ok=True)
code='''import asyncio,json
from fastmcp import Client
from agentsvc.tools.mcp_tsdb import TimeSeriesDB
def decode(result):return json.loads(next(x.text for x in result.content if getattr(x,'type',None)=='text'))
async def main():
 result={}
 async with Client('http://127.0.0.1:8198/mcp',timeout=30) as client:
  result['tools']=[t.name for t in await client.list_tools()]
  result['schema']=decode(await client.call_tool('timeseries_schema',{}))
  for name,sql in [('recent',"select time,asset,name,value from tag_1s where asset='HYD-01' and name='VS1' order by time desc limit 1"),
                   ('empty',"select value from tag_1s where asset='A051-NONE' and time>now()-interval '30 seconds'"),
                   ('bad_column','select unknown_value from tag_1s'),('outside','select * from audit')]:
   result[name]=decode(await client.call_tool('timeseries_query',{'sql':sql}))
  result['diagnosis']=decode(await client.call_tool('diagnose',{'asset':'HYD-01','pattern':'COOLER_DEGRADATION'}))
 async with Client('http://enterprise-mcp:8199/mcp',timeout=30) as client:
  result['enterprise']=decode(await client.call_tool('query',{'sql':"select code from assets where code='HYD-01' and name is not null"}))
 with TimeSeriesDB()._conn() as c:
  r=c.execute("select current_user,current_setting('transaction_read_only'),has_table_privilege(current_user,'tag_1s','INSERT')").fetchone()
 result['role']=list(r)
 print(json.dumps(result,default=str))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-'],input=code,text=True,encoding='utf8',capture_output=True,timeout=100)
(OUT/'stderr.log').write_text(r.stderr,encoding='utf8');(OUT/'result.json').write_text(r.stdout,encoding='utf8')
assert r.returncode==0,r.stderr
data=json.loads(r.stdout)
checks={
 'metadata_and_query_are_exposed':{'timeseries_schema','timeseries_query'}<=set(data['tools']),
 'actual_metadata_contains_sensor_columns':data['schema']['result']=='ok' and 'tag_1s' in data['schema']['document']['tables'],
 'actual_query_returns_current_sensor_row':data['recent']['result']=='ok' and data['recent']['document']['row_count']==1,
 'empty_is_successful_zero_rows':data['empty']['result']=='ok' and data['empty']['document']['row_count']==0,
 'bad_column_is_invalid':data['bad_column']['error_kind']=='INVALID',
 'non_sensor_table_is_rejected':data['outside']['error_kind']=='INVALID',
 'deployed_reader_is_read_only':data['role']==['hyd_timeseries_reader','on',False],
 'legacy_diagnose_reads_current_evidence':data['diagnosis']['result']=='ok' and not data['diagnosis']['document']['withheld'] and bool(data['diagnosis']['document']['causes']),
 'enterprise_boolean_query_still_works':data['enterprise']['result']=='ok' and data['enterprise']['document']['row_count']==1,
}
(OUT/'checks.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
for name,ok in checks.items():print(('PASS ' if ok else 'FAIL ')+name)
assert all(checks.values())
