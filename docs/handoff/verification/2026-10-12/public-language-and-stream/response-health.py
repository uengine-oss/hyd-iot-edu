import time,json,concurrent.futures
from pathlib import Path
from urllib.request import urlopen
H=Path(__file__).parent
def check(path):
    t=time.monotonic()
    try:
        with urlopen('http://127.0.0.1:8080'+path,timeout=20) as r:b=r.read();return {'path':path,'status':r.status,'bytes':len(b),'seconds':time.monotonic()-t}
    except Exception as e:return {'path':path,'error':repr(e),'seconds':time.monotonic()-t}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:r=list(pool.map(check,['/healthz','/api/flows','/api/instances/c3_pm.d99ee952-f943-42fd-ba53-745b569522f7']))
(H/'response-health.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
