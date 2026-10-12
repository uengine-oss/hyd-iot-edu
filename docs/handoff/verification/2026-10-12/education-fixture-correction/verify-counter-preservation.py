import json
from pathlib import Path
OUT=Path(__file__).parent
old=json.loads((OUT/'erp-after-fixture.json').read_text(encoding='utf8'))
new=json.loads((OUT/'B-actual-erp-after-approval.json').read_text(encoding='utf8'))
before=next(r for r in old['pm_counters'] if r['asset']=='HYD-02')
after=next(r for r in new['pm_counters'] if r['asset']=='HYD-02')
keys=['cycle','total_h','since_pm_h','last_done_at','service_position']
assert all(before[k]==after[k] for k in keys)
assert after['plan_wo']=='WO-B6F6633D2BF9E6FA'
proof=dict(before=before,after=after,unchanged_operating_counters=keys,physical_repair_or_counter_reset_claimed=False,verified_change='Only plan/order linkage recorded; no physical maintenance or counter reset')
(OUT/'B-counter-preserved.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
print('B operating counters unchanged; only work-order plan recorded')
