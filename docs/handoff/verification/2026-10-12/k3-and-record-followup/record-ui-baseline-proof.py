import subprocess
from test_portal_remaining_ui import page, record_components

def test_existing_key_expectation_mismatch_is_already_in_head(page):
    record_components(page)
    events=[{'id':'read-start','todo_id':'w1','job_id':'run-2','event_type':'tool_usage_started','data':{'tool':'Read','tool_use_id':'read2','input':{}}},
            {'id':'read-failed','todo_id':'w1','job_id':'run-2','event_type':'tool_usage_finished','data':{'tool':'Read','tool_use_id':'read2','is_error':True,'output':'권한 거부'}}]
    current=page.evaluate('evs=>hydTrace.rowsOf(evs)',events)
    source=subprocess.check_output(['git','show','HEAD:it/portal/www/trace.js']).decode('utf-8')
    page.add_script_tag(content=source)
    baseline=page.evaluate('evs=>hydTrace.rowsOf(evs)',events)
    assert current == baseline
    assert current[0]['status']=='fail'
    assert current[0]['key']=='tool:[null,"w1","run-2","read2"]'
    assert not any(row['key']=='tool:read2' for row in baseline)
