"""Tool originals survive the producer, payload journal and native portal folds."""
import json
from cliagents import ExecEvent,ExecEventKind
from worker.runner import Runner
from test_worker import _repo,_settings
from test_instances import rt,ALERT,NOW,_by  # noqa: F401
from test_u1_task_detail import _scenario,_render


def test_full_input_is_journaled_and_event_original_kept(tmp_path):
    repo,inst=_repo();original=dict(query='입력'*9000+'입력끝')
    def stream(provider,request,env):
        yield ExecEvent(kind=ExecEventKind.TOOL_START,tool='read_rows',tool_use_id='read',tool_input=original)
        rows=repo.list_events(proc_inst_id=inst['proc_inst_id'])
        start=next(e for e in rows if e['event_type']=='tool_usage_started')
        assert start['data']['input']==original
        ref=start['data']['full_input'];assert ref['stored'] and ref['direction']=='input'
        assert json.loads(repo.get_event_payload(ref['ref'])['content'])==original
        yield ExecEvent(kind=ExecEventKind.RESULT,text='{"cause":"c","failure_mode":"f","guide_card":{}}')
    Runner(_settings(tmp_path),repo,exec_fn=stream,schema_prompt='s',resolve_provider=lambda _:object()).poll_once()


def test_storage_failure_is_visible_but_input_original_not_lost(tmp_path,monkeypatch):
    repo,inst=_repo();original=dict(query='입력'*5000+'실패입력끝')
    monkeypatch.setattr(repo,'store_event_payload',lambda _:(_ for _ in ()).throw(OSError('storage failure')))
    def stream(provider,request,env):
        yield ExecEvent(kind=ExecEventKind.TOOL_START,tool='read_rows',tool_use_id='read',tool_input=original)
        raise RuntimeError('tool failure')
    Runner(_settings(tmp_path),repo,exec_fn=stream,schema_prompt='s',resolve_provider=lambda _:object()).poll_once()
    start=next(e for e in repo.list_events(proc_inst_id=inst['proc_inst_id']) if e['event_type']=='tool_usage_started')
    assert start['data']['input']==original
    assert start['data']['full_input']['stored'] is False and 'storage failure' in start['data']['full_input']['error']


def test_real_task_trace_raw_fold_has_input_and_output_tails(rt,tmp_path):
    runtime,_=rt;inst=runtime.on_alert_raise(ALERT,now=NOW);task=_by(runtime,inst,'task:diagnose')
    base=dict(job_id='raw-job',todo_id=task['id'],proc_inst_id=inst['proc_inst_id'],crew_type='cliagents')
    runtime.repo.record_events([dict(base,event_type='tool_usage_started',data=dict(tool='read_rows',tool_use_id='raw',input={'query':'입력'*5000+'입력전문끝'})),
        dict(base,event_type='tool_usage_finished',data=dict(tool='read_rows',tool_use_id='raw',output='반환'*5000+'반환전문끝'))])
    html=_render(tmp_path,[_scenario(runtime,inst,task['id'],'full')])['full']['panel']
    assert '입력전문끝' in html and '반환전문끝' in html
