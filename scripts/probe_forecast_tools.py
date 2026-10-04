"""Actual deployed HTTP + MCP forecast tools, with state immutability checks."""
import json
import argparse
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

OUT=Path('.evidence/reaudit/a030-tools-live')


def http(url,data=None):
    req=urllib.request.Request(url,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        return {'error':e.code,'body':e.read().decode()}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={'checks':[]}
    def save(name,value):
        (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    def check(name,ok,detail=None):
        report['checks'].append({'name':name,'passed':bool(ok),'detail':detail});save('report',report)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    before=http('http://127.0.0.1:8000/api/state');save('before',before)
    decisions_before=http('http://127.0.0.1:8080/api/decisions')
    args={'asset':'HYD-01','actions':[{'kind':'command','code':'FAN_SET','value':100},{'kind':'command','code':'LOAD_SET','value':80}], 'horizon_s':900}
    api=http('http://127.0.0.1:8091/api/agent/forecast',args);save('http-forecast',api)
    check('HTTP returns current-source model and all variables',api.get('execution_authorized') is False
          and {'ts1','ps1','vs1'} <= api.get('values',{}).keys(),api.get('provenance'))
    other=http('http://127.0.0.1:8091/api/agent/forecast',dict(args,actions=[{'kind':'command','code':'LOAD_SET','value':100}]))
    save('changed-actions',other)
    check('changed action values change the model output',other.get('values',{}).get('ts1_steady') != api.get('values',{}).get('ts1_steady'))
    badargs=dict(args,actions=[{'kind':'command','code':'PRESSURE_SET','value':190}])
    invalid=http('http://127.0.0.1:8091/api/agent/forecast',badargs);save('http-unsupported',invalid)
    check('HTTP refuses unsupported effects explicitly',invalid.get('error')==409,invalid)
    code='''import asyncio,json
from fastmcp import Client
async def main():
 async with Client("http://127.0.0.1:8198/mcp") as c:
  names=[x.name for x in await c.list_tools()]
  good=await c.call_tool("forecast_actions", ARGS)
  bad=await c.call_tool("forecast_actions", BADARGS)
  def decode(r):
   return json.loads(next(x.text for x in r.content if getattr(x,"type",None)=="text"))
  print(json.dumps({"tools":names,"good":decode(good),"bad":decode(bad)}))
asyncio.run(main())
'''.replace('BADARGS',repr(badargs)).replace('ARGS',repr(args))
    result=subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-'],input=code,text=True,
                          encoding='utf8',capture_output=True,timeout=45)
    (OUT/'mcp-client.stderr').write_text(result.stderr,encoding='utf8')
    assert result.returncode==0,result.stderr
    mcp=json.loads(result.stdout);save('mcp',mcp)
    check('actual MCP exposes and executes the read-only forecast tool','forecast_actions' in mcp['tools'] and mcp['good'].get('result')=='ok')
    doc=mcp['good']['document']
    check('HTTP and MCP share model revision and action-dependent steady output',doc['model_revision']==api['model_revision']
          and doc['values']['ts1_steady']==api['values']['ts1_steady'] and doc['execution_authorized'] is False)
    check('MCP returns INVALID for unsupported effects',mcp['bad'].get('error_kind')=='INVALID',mcp['bad'])
    after=http('http://127.0.0.1:8000/api/state');save('after',after)
    keys=['cmdId','fan_pct','load_pct','pump','mode','state']
    check('forecast calls do not command or change any asset',all(
        {k:u['status'][k] for k in keys}=={k:after['units'][a]['status'][k] for k in keys} for a,u in before['units'].items()))
    check('forecast calls do not submit a process decision',
          [d['id'] for d in decisions_before]==[d['id'] for d in http('http://127.0.0.1:8080/api/decisions')])
    raise SystemExit(0 if all(c['passed'] for c in report['checks']) else 1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default=str(OUT))
    OUT=Path(parser.parse_args().out)
    main()
