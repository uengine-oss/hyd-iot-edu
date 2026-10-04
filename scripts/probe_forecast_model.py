"""Actual plant HTTP experiment for the standalone candidate model.

Uses explicit local-panel writes, not agent/HITL execution. Records every input
and observed value; restores the teaching plant in finally. No forecast is
inserted into Neo4j and the decision pipeline is not changed by this probe.
"""
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'common'))
from hydcommon.forecast import predict

BASE = 'http://127.0.0.1:8000'
OUT = ROOT / '.evidence/reaudit/a030-model-live'


def request(path, data=None):
    req = urllib.request.Request(BASE + path, data=None if data is None else json.dumps(data).encode(),
                                 headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'scope':'actual simulator/local panel; standalone forecast only', 'checks':[]}
    def save(name, data):
        (OUT / (name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    def check(name, ok, detail):
        report['checks'].append({'name':name,'passed':bool(ok),'detail':detail})
        save('report',report)
        print(('PASS ' if ok else 'FAIL ')+name+' '+str(detail),flush=True)
    cases = {
        'HYD-01': {'faults':{'cooler_degradation':0.43}, 'writes':{'FanSpeedSP':100,'LoadSP':80},
                   'actions':[{'kind':'command','code':'FAN_SET','value':100},{'kind':'command','code':'LOAD_SET','value':80}]},
        'HYD-02': {'faults':{'pump_leakage':0.15}, 'writes':{'PumpSelect':1},
                   'actions':[{'kind':'command','code':'PUMP_SELECT','value':'B'}]},
        'HYD-03': {'faults':{'cooler_degradation':0.65,'pump_leakage':0.1,'fan_vibration':0.3},
                   'writes':{'FanSpeedSP':50,'LoadSP':80},
                   'actions':[{'kind':'command','code':'FAN_SET','value':50},{'kind':'command','code':'LOAD_SET','value':80}]}}
    try:
        save('initial-reset',request('/api/reset',{}))
        for asset, case in cases.items():
            for kind, target in case['faults'].items():
                request('/api/fault',{'asset':asset,'type':kind,'target':target,'ramp_sim_s':1})
        limit=time.monotonic()+10
        while True:
            state=request('/api/state')
            if all(not u['faults'] for u in state['units'].values()):
                break
            assert time.monotonic()<limit,'disturbances did not settle'
            time.sleep(0.2)
        sources={}
        for asset, case in cases.items():
            source=request('/api/state')['units'][asset]['status']
            sources[asset]=source
            save(asset+'-before',source)
            save(asset+'-forecast',predict(source,case['actions'],600))
            command=request('/api/manual',{'asset':asset,'writes':case['writes']})
            save(asset+'-command',command)
            check(asset+' actual local-panel action accepted',command['result']=='DONE',command)
        target=max(s['sim_t'] for s in sources.values())+600
        limit=time.monotonic()+60
        while True:
            observed=request('/api/state')
            if observed['sim_t']>=target:
                break
            assert time.monotonic()<limit,'physical observation timeout'
            time.sleep(0.5)
        save('observed',observed)
        for asset, source in sources.items():
            actual=observed['units'][asset]
            elapsed=observed['sim_t']-source['sim_t']
            result=predict(source,cases[asset]['actions'],elapsed)
            save(asset+'-aligned-forecast',result)
            check(asset+' remains RUN without forecast interlock',actual['status']['state']=='RUN' and not result['predicted_interlocks'],actual['status']['state'])
            for var, tag, tolerance in [('ts1','TS1',0.1),('ps1','PS1',2.0),('vs1','VS1',0.12)]:
                error=abs(actual['tags'][tag]-result['values'][var])
                check(asset+' observed '+tag+' matches stated model tolerance',error<=tolerance,
                      {'actual':actual['tags'][tag],'forecast':result['values'][var],'error':error,'tolerance':tolerance,'elapsed_sim_s':elapsed})
    finally:
        final=request('/api/reset',{})
        save('final-reset',final)
        check('all simulated assets restored',all(u['status']['state']=='RUN' and not u['faults'] and u['status']['mode']=='REMOTE_AUTO' for u in final['units'].values()),'RUN/REMOTE_AUTO/no faults')
    raise SystemExit(0 if all(c['passed'] for c in report['checks']) else 1)


if __name__ == '__main__':
    main()
