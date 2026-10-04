"""Measure received source timestamps, not HTTP poll rate or simulator time."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
import urllib.request

out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=False)
duration=float(sys.argv[2]) if len(sys.argv)>2 else 23
samples=[]; start=time.monotonic()
while time.monotonic()-start<duration:
    for asset in ('HYD-01','HYD-02','HYD-03'):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:8080/api/plant/{asset}/status',timeout=5) as r: row=json.load(r)
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(row['t'].replace('Z','+00:00'))).total_seconds()
            samples.append(dict(asset=asset,t=row['t'],age=age,observed=datetime.now(timezone.utc).isoformat()))
        except Exception as exc: samples.append(dict(asset=asset,error=str(exc)))
    time.sleep(.25)
report={}
for asset in ('HYD-01','HYD-02','HYD-03'):
    rows=[r for r in samples if r['asset']==asset]
    timestamps=sorted({r['t'] for r in rows if 't' in r})
    times=[datetime.fromisoformat(t.replace('Z','+00:00')) for t in timestamps]
    gaps=[(b-a).total_seconds() for a,b in zip(times,times[1:])]
    max_age=max((r['age'] for r in rows if 'age' in r),default=float('inf'))
    report[asset]=dict(unique_timestamps=len(times),max_source_gap=max(gaps,default=None),max_age=max_age,
        errors=[r['error'] for r in rows if 'error' in r],
        passed=len(times)>=duration*.6 and max_age<3 and bool(gaps) and max(gaps)<2.5 and all('error' not in r for r in rows))
(out/'samples.json').write_text(json.dumps(samples,indent=2),encoding='utf8')
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2),flush=True)
sys.exit(0 if all(v['passed'] for v in report.values()) else 1)
