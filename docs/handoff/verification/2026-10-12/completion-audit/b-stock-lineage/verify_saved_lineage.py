"""Validate saved GET evidence only; no HTTP or business evaluations."""
import json,hashlib
from pathlib import Path
p=Path(__file__).parent
read=lambda name:json.loads((p/name).read_text(encoding='utf8'))
checks=[]
def check(name,condition):
 checks.append(dict(name=name,passed=bool(condition)))
 if not condition: raise AssertionError(name)
stock=read('erp-all-stock.json')['records']
master=read('erp-parts-master.json');table=read('erp-stock-table.json')
check('master sample contains fewer rows than configured cap',master['row_count']<master['row_limit'])
check('stock sample contains fewer rows than configured cap',table['row_count']<table['row_limit'])
numbers={r['part_no'] for r in stock}
check('full ERP read and master and stock table agree',numbers=={r[0] for r in master['rows']}=={r[0] for r in table['rows']})
check('required filter absent from complete observed part sets','P-RTN-FLT' not in numbers)
check('existing seal stock is verified seven available',next(r for r in stock if r['part_no']=='P-PMP-SEAL')['available']==7)
lineage=read('actual-B-package-lineage.json');bundle=next(o for o in lineage['options'] if o['id']=='skill:sop-pm-14')['maintenanceDiagnostics']
single=next(o for o in lineage['options'] if o['id']=='skill:sop-pm-11')['maintenanceDiagnostics']
check('actual single package is four thousand hours',single['assets'][0]['service']['package_interval_h']==4000)
check('actual bundle has four and eight thousand hour packages',{a['service']['package_interval_h'] for a in bundle['assets']}=={4000,8000})
check('missing filter remains null and unverified',all(part['available'] is None and part['verified'] is False for a in bundle['assets'] for part in a['parts'] if part['part_no']=='P-RTN-FLT'))
check('unknown oil mapping and quantity preserved',any(part['part_no'] is None and part['qty'] is None and part['verified'] is False for a in bundle['assets'] for part in a['parts']))
pm=read('cmms-all-pm.json')['records'];row=next(r for r in pm if r['asset']=='HYD-02')
check('current following window exceeds exact source upper limit',row['hours_at_following_window']>2200)
source=read('PM-02-original-source-GET.json');anchor=single['model_applicability']['source_anchor'];page=next(x for x in source['pages'] if x['page']==anchor['page'])
check('actual recorded model anchor matches actual archived source',page['text'][anchor['start']:anchor['end']]==anchor['quote'])
(p/'saved-lineage-checks.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
print(len(checks),'saved-evidence checks passed')
