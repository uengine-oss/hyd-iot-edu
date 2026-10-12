import urllib.request,json,hashlib,datetime
from pathlib import Path
out=Path(__file__).parent
routes={'erp-parts-master':'/api/fabric/sources/hyd-enterprise/tables/parts/sample?limit=20',
        'erp-stock-table':'/api/fabric/sources/hyd-enterprise/tables/spare_stock/sample?limit=20',
        'erp-task-standards':'/api/fabric/sources/hyd-enterprise/tables/task_standards/sample?limit=20'}
manifest=[]
for name,path in routes.items():
 url='http://127.0.0.1:8080'+path
 with urllib.request.urlopen(url,timeout=10) as r: raw=r.read();status=r.status
 data=json.loads(raw);(out/(name+'.json')).write_bytes(raw)
 manifest.append(dict(method='GET',url=url,status=status,sha256=hashlib.sha256(raw).hexdigest(),observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 print(name,json.dumps(data,ensure_ascii=False))
(out/'catalog-read-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')

