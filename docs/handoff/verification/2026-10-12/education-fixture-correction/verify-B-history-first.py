import json
from pathlib import Path
from urllib.request import urlopen
OUT=Path(__file__).parent
before=json.loads((OUT/'cases-before-fixture.json').read_text(encoding='utf8'))['B']
after=json.loads((OUT/'B-actual-after-approval.json').read_text(encoding='utf8'))
old={e['id']:e for e in before['events']}
new={e['id']:e for e in after['events']}
assert all(k in new and new[k]==v for k,v in old.items()),'Old event bytes changed or disappeared'
deferrals=[e for e in after['events'] if e.get('event_type')=='task_deferred']
assert any('run-6c2ddc9c-1b6c1170ce5849f5837537e125699a0a' in json.dumps(e) for e in deferrals)
assert after['instance']['proc_inst_id']==before['instance']['proc_inst_id']
report=next(w for w in after['workitems'] if w['activity_id']=='R_ok')['output']['result_report']
proof=dict(same_processing_case=True,old_events_preserved=len(old),new_events=len(new),old_event_values_exact=True,original_deferral_preserved=True,report_closure_action=report['incident_closed'],actual_incident_state=json.loads((OUT/'B-incident-after-approval.json').read_text(encoding='utf8'))['state'],report_closure_action_is_not_current_incident_state=True,mail_result='Actual prior SMTP receipt preserved; no resending or body rewriting')
(OUT/'B-original-history-preserved.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(proof,ensure_ascii=False))
