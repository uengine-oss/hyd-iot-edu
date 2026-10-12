"""Read-only existing documented routes; no tool calls or business mutations."""
import urllib.request,json,hashlib,datetime
from pathlib import Path
out=Path(__file__).parent
routes={
 'erp-all-stock':'http://127.0.0.1:8095/erp/spare_stock',
 'cmms-all-pm':'http://127.0.0.1:8095/cmms/pm_status',
 'enterprise-state':'http://127.0.0.1:8095/api/state',
 'actual-B-case':'http://127.0.0.1:8080/api/instances/c3_pm.d99ee952-f943-42fd-ba53-745b569522f7',
}
manifest=[]
for name,url in routes.items():
 with urllib.request.urlopen(url,timeout=10) as response: raw=response.read();status=response.status
 json.loads(raw)
 (out/(name+'.json')).write_bytes(raw)
 manifest.append(dict(name=name,url=url,method='GET',status=status,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
(out/'read-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print(json.dumps(manifest,indent=2))
