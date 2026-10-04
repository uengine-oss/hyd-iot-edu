"""Actual HTTP/MCP/Neo4j model boundaries; simulated faults, no action approval.

Run without another plant scenario in flight. Restores graph binding and plant.
Does not purport to be a worker or end-to-end process execution test.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error
from neo4j import GraphDatabase


def http(url, data=None):
    request=urllib.request.Request(url,data=None if data is None else json.dumps(data).encode(),
                                   headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return {'error':error.code,'body':error.read().decode()}


def main(destination):
    out=Path(destination);out.mkdir(parents=True,exist_ok=False)
    report={'scope':'actual deployed HTTP/MCP and Neo4j; no PLC approval', 'checks':[]}
    agent='http://127.0.0.1:8091';plant='http://127.0.0.1:8000';process='http://127.0.0.1:8080'
    def save(name,value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    def check(name,passed,detail=None):
        report['checks'].append({'name':name,'passed':bool(passed),'detail':detail});save('report',report)
        print(('PASS ' if passed else 'FAIL ')+name,flush=True)
    def wait(fn,timeout=15):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            value=fn()
            if value:return value
            time.sleep(.3)
        raise RuntimeError('source condition not reached')
    def evaluate(name,asset='HYD-01'):
        result=http(agent+'/api/agent/decide',{'asset':asset,'pattern':'COOLER_DEGRADATION'})
        save(name,result);return result
    with GraphDatabase.driver('bolt://127.0.0.1:7687',auth=('neo4j','hydpass123')) as driver, driver.session() as session:
        original=session.run("MATCH (a:Asset {code:'HYD-01'}) RETURN a.forecastRevision AS revision").single()['revision']
        save('before-binding',{'revision':original})
        try:
            http(plant+'/api/reset',{});time.sleep(2)
            healthy=evaluate('healthy')
            opt=next(o for o in healthy['result']['options'] if o['id']=='skill:fan-max-derate')
            check('actual cards retain bound model inputs/actions/time',opt['feasible']
                  and opt['forecastContext']['binding']['asset']=='HYD-01'
                  and opt['forecastContext']['actions']==opt['actions'])
            before_decisions=[d['id'] for d in http(process+'/api/decisions')]
            code='''import asyncio,json
from fastmcp import Client
async def main():
 async with Client('http://127.0.0.1:8198/mcp') as client:
  args={'asset':'HYD-01','pattern':'COOLER_DEGRADATION','cause':'cause:cooler-fin-fouling','failure_mode':'fm:cooling-loss'}
  evaluated=await client.call_tool('evaluate_cards',args)
  rejected=await client.call_tool('submit_decision',dict(args,incident='probe-invalid-overrides',overrides={'plc_mode':'REMOTE_AUTO'}))
  def unpack(r):return json.loads(next(c.text for c in r.content if getattr(c,'type',None)=='text'))
  print(json.dumps({'evaluated':unpack(evaluated),'rejected':unpack(rejected)}))
asyncio.run(main())
'''
            result=subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-'],input=code,
                capture_output=True,text=True,encoding='utf8',timeout=50)
            (out/'mcp.stderr').write_text(result.stderr,encoding='utf8');assert result.returncode==0,result.stderr
            mcp=json.loads(result.stdout);save('mcp',mcp)
            remote=next(o for o in mcp['evaluated']['document']['result']['options'] if o['id']==opt['id'])
            check('MCP and HTTP cards use same bound prediction',remote['forecast']==opt['forecast']
                  and remote['forecastContext']['binding']==opt['forecastContext']['binding'])
            check('actual MCP live submission rejects assumed source facts',mcp['rejected'].get('error_kind')=='INVALID',mcp['rejected'])
            check('rejected submission created no decision',before_decisions==[d['id'] for d in http(process+'/api/decisions')])
            session.run("MATCH (a:Asset {code:'HYD-01'}) SET a.forecastRevision='unsupported-probe'").consume()
            mismatch=evaluate('wrong-model-revision')
            check('wrong graph model revision excludes all cards without static fallback',
                  mismatch['result']['recommended'] is None and all(not o['forecast'] and not o['feasible'] for o in mismatch['result']['options']))
            session.run("MATCH (a:Asset {code:'HYD-01'}) SET a.forecastRevision=$revision",revision=original).consume()
            http(plant+'/api/fault',{'asset':'HYD-01','type':'cooler_degradation','target':.8,'ramp_sim_s':3000})
            wait(lambda:http(process+'/api/plant/HYD-01/status').get('disturbance_ramps'))
            ramp=evaluate('active-ramp')
            check('active disturbance ramp excludes predictions until model is applicable',ramp['result']['recommended'] is None
                  and all('stationary' in o['forecastContext'].get('error','') for o in ramp['result']['options']))
            http(plant+'/api/reset',{});time.sleep(2)
            http(plant+'/api/fault',{'asset':'HYD-01','type':'cooler_degradation','target':.43,'ramp_sim_s':1})
            http(plant+'/api/fault',{'asset':'HYD-01','type':'fan_vibration','target':.8,'ramp_sim_s':1})
            wait(lambda:(s if (s:=http(process+'/api/plant/HYD-01/status')).get('cooler_health')==.43
                         and s.get('bearing_wear')==.8 and s.get('disturbance_ramps')==[] else None))
            combined=evaluate('compound-fault')
            mixed=next(o for o in combined['result']['options'] if o['id']=='skill:fan-max-derate')
            check('cool thermal forecast cannot conceal compound vibration interlock',mixed['facts']['forecast_ts1']<55
                  and not mixed['feasible'] and 'HIGH_VIBRATION' in mixed['forecastContext']['predicted_interlocks'])
            check('work order does not invent immediate physical repair',all(
                o['forecastContext'].get('operating',{}).get('cooler_health')==.43
                for o in combined['result']['options'] if not o['forecastContext'].get('error')))
        finally:
            session.run("MATCH (a:Asset {code:'HYD-01'}) SET a.forecastRevision=$revision",revision=original).consume()
            save('reset',http(plant+'/api/reset',{}));time.sleep(2)
            final=http(plant+'/api/state');save('final-plant',final)
            check('three assets restored RUN/REMOTE_AUTO without disturbances',all(u['status']['state']=='RUN'
                and u['status']['mode']=='REMOTE_AUTO' and u['disturbances']['cooler_health']==1
                and u['disturbances']['leak']==0 and u['disturbances']['bearing_wear']==0 for u in final['units'].values()))
    raise SystemExit(0 if all(c['passed'] for c in report['checks']) else 1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    main(parser.parse_args().out)
