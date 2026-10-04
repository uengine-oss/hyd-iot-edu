"""Read actual Prometheus through deployed MCP. Queries are probe-authored, not Codex."""
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

OUT = Path('.evidence/reaudit/a052-mcp')
OUT.mkdir(exist_ok=True)
code = '''import asyncio,json,time,urllib.request
from fastmcp import Client
from agentsvc.tools.prometheus import Prometheus
from dmn_mcp.tools import enveloped
def decode(result):return json.loads(next(x.text for x in result.content if getattr(x,'type',None)=='text'))
async def main():
 result={}
 at=time.time()
 async with Client('http://127.0.0.1:8198/mcp',timeout=30) as client:
  result['tools']=[t.name for t in await client.list_tools()]
  async def call(name,args):return decode(await client.call_tool(name,args))
  result['catalog']=await call('prometheus_metadata',{})
  result['series']=await call('prometheus_series',{'selector':'up','start':at-60,'end':at})
  result['up']=await call('prometheus_query',{'expression':'up','at':at})
  result['range']=await call('prometheus_query',{'expression':'sum by (job) (up)','start':at-40,'end':at,'step':10})
  metadata=result['catalog']['document']['data']
  metric=next(name for name,entries in metadata.items() if any(e['type']=='gauge' for e in entries))
  result['selected_metric']=metric
  result['exact_metadata']=await call('prometheus_metadata',{'metric':metric})
  result['selected_series']=await call('prometheus_series',{'selector':metric,'start':at-60,'end':at})
  labels=result['selected_series']['document']['data'][0]
  selector=metric+'{'+','.join(k+'='+json.dumps(v) for k,v in labels.items() if k!='__name__')+'}'
  result['selected_value']=await call('prometheus_query',{'expression':selector,'at':at})
  value=float(result['selected_value']['document']['data']['result'][0]['value'][1])
  result['above']=await call('prometheus_query',{'expression':selector+' > bool '+str(value-1),'at':at})
  result['below']=await call('prometheus_query',{'expression':selector+' > bool '+str(value+1),'at':at})
  for name,expression in [('empty','up{job="A052_DOES_NOT_EXIST"}'),('invalid','sum('),('zero','0'),('nan','0/0'),('sample_age','time()-timestamp(up)')]:
   result[name]=await call('prometheus_query',{'expression':expression,'at':at})
  result['bad_range']=await call('prometheus_query',{'expression':'up','start':at,'end':at-1,'step':10})
  result['sensor_schema']=await call('timeseries_schema',{})
  result['diagnosis']=await call('diagnose',{'asset':'HYD-01','pattern':'COOLER_DEGRADATION'})
 result['unavailable']=enveloped(lambda:Prometheus('http://127.0.0.1:1').query('up'))()
 with urllib.request.urlopen('http://prometheus:9090/api/v1/status/buildinfo') as r:result['version']=json.load(r)
 print(json.dumps(result,default=str))
asyncio.run(main())
'''
run = subprocess.run(['docker', 'exec', '-i', 'hyd-iot-edu-dmn-mcp-1', 'python', '-'],
                     input=code, text=True, encoding='utf8', capture_output=True, timeout=120)
(OUT / 'stderr.log').write_text(run.stderr, encoding='utf8')
(OUT / 'result.json').write_text(run.stdout, encoding='utf8')
assert run.returncode == 0, run.stderr
data = json.loads(run.stdout)
def doc(key):
    assert data[key]['result'] == 'ok', data[key]
    return data[key]['document']
checks = {
    'three_mcp_tools_exposed': {'prometheus_metadata','prometheus_series','prometheus_query'} <= set(data['tools']),
    'deployed_version_2_55_1': data['version']['data']['version'] == '2.55.1',
    'actual_catalog_has_type_and_help': bool(doc('catalog')['data']) and not doc('catalog')['truncated'],
    'exact_metadata_matches_discovered_metric': list(doc('exact_metadata')['data']) == [data['selected_metric']],
    'actual_six_scrape_jobs': len({r['job'] for r in doc('series')['data']}) == 6,
    'instant_returns_observed_series': doc('up')['series_count'] == 6,
    'range_returns_timestamped_matrix': doc('range')['data']['resultType'] == 'matrix' and all(len(r['values']) == 5 for r in doc('range')['data']['result']),
    'changed_threshold_changes_same_observation_truth': doc('above')['data']['result'][0]['value'][1] == '1' and doc('below')['data']['result'][0]['value'][1] == '0',
    'absent_label_is_empty_success': doc('empty')['empty'] and doc('empty')['series_count'] == 0,
    'scalar_zero_is_not_empty': doc('zero')['data']['result'][1] == '0' and not doc('zero')['empty'],
    'nan_is_not_normal_zero': doc('nan')['data']['result'][1] == 'NaN',
    'invalid_promql_is_invalid': data['invalid']['error_kind'] == 'INVALID',
    'bad_range_is_invalid': data['bad_range']['error_kind'] == 'INVALID',
    'actual_connection_failure_is_unknown': data['unavailable']['error_kind'] == 'UNKNOWN',
    'sample_timestamp_query_returns_ages': doc('sample_age')['series_count'] == 6 and all(float(r['value'][1]) >= 0 for r in doc('sample_age')['data']['result']),
    'sensor_source_remains_separate': 'tag_1s' in doc('sensor_schema')['tables'],
    'existing_diagnosis_remains_available': not doc('diagnosis')['withheld'] and bool(doc('diagnosis')['causes']),
}
(OUT / 'checks.json').write_text(json.dumps(checks, indent=2), encoding='utf8')
for name, passed in checks.items():
    print(('PASS ' if passed else 'FAIL ') + name)
assert all(checks.values()), checks

if '--outage' in sys.argv:
    # Explicit optional source lifecycle probe. Preserve its container/data; always restore.
    outage = {}
    read_code = '''import asyncio,json
from fastmcp import Client
async def main():
 async with Client('http://127.0.0.1:8198/mcp',timeout=20) as client:
  result=await client.call_tool('prometheus_query',{'expression':'up'})
  print(next(x.text for x in result.content if getattr(x,'type',None)=='text'))
asyncio.run(main())
'''
    def read_mcp():
        reply = subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-'],
                               input=read_code,text=True,encoding='utf8',capture_output=True,timeout=40)
        assert reply.returncode == 0, reply.stderr
        return json.loads(reply.stdout)
    try:
        subprocess.run(['docker','stop','hyd-iot-edu-prometheus-1'],check=True,capture_output=True,timeout=30)
        outage['stopped'] = read_mcp()
        assert outage['stopped']['error_kind'] == 'UNKNOWN', outage
    finally:
        subprocess.run(['docker','start','hyd-iot-edu-prometheus-1'],check=True,capture_output=True,timeout=30)
        ready = False
        for _ in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:9090/-/ready',timeout=2) as response:
                    ready = response.status == 200
                if ready:break
            except OSError:pass
            time.sleep(0.5)
        outage['ready_after_restart'] = ready
        outage['restored'] = read_mcp()
        (OUT/'outage.json').write_text(json.dumps(outage,indent=2),encoding='utf8')
    assert outage['ready_after_restart'] and outage['restored']['result'] == 'ok', outage
    assert outage['restored']['document']['series_count'] == 6, outage
    print('PASS actual_source_stop_returns_UNKNOWN_and_restart_restores_six_series')
