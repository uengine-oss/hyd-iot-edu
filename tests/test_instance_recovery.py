"""Lost callbacks, due timers and competing transitions must preserve one flow."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import time
import uuid

import pytest

from procsvc import engine, instances, procdb
from test_instances import FakeHooks, AGENT_OUTPUTS, ALERT, DEF_PATH, NOW, _agent_tasks, _by


def runtime(repo=None):
    hooks=FakeHooks()
    rt=instances.InstanceRuntime(repo or procdb.MemoryRepo(),engine.Definition.load(DEF_PATH),hooks)
    inst=rt.on_alert_raise(ALERT,now=NOW)
    return rt,hooks,inst


def test_due_timer_is_not_hidden_by_older_human_work():
    rt,hooks,inst=runtime();_agent_tasks(rt)
    selection=_by(rt,inst,'task:select')
    for n in range(205):
        other=deepcopy(inst);other['proc_inst_id']='older.'+str(uuid.uuid4())
        rt.repo.insert_instance(other)
        w=deepcopy(selection);w.update(id=str(uuid.uuid4()),proc_inst_id=other['proc_inst_id'],
                                      start_date=(NOW-timedelta(days=1,seconds=n)).isoformat())
        rt.repo.insert_workitems([w])
    assert len(rt.fire_timeouts(now=NOW+timedelta(seconds=31)))==1
    assert _by(rt,inst,'task:escalate')['status']=='IN_PROGRESS'


def test_lost_terminal_callback_recovers_after_runtime_recreation_without_reissuing_command():
    rt,hooks,inst=runtime();_agent_tasks(rt)
    rt.select(_by(rt,inst,'task:select')['id'],'DEC-1003-001','skill:fan-max-derate','tester','role:prod-mgr',now=NOW)
    hooks.inc_state='RESOLVED'
    restarted=instances.InstanceRuntime(rt.repo,rt.defn,hooks,consumer='new-engine')
    restarted.poll_once(now=NOW+timedelta(seconds=20))
    assert rt.repo.get_instance(inst['proc_inst_id'])['end_event']=='ev:closed'
    assert sum(c[0]=='approve_commands' for c in hooks.calls)==1


def test_concurrent_timer_ticks_fire_once(monkeypatch):
    rt,hooks,inst=runtime();_agent_tasks(rt)
    fire=engine.fire_event
    def slow(*args,**kwargs):
        time.sleep(.03)
        return fire(*args,**kwargs)
    monkeypatch.setattr(engine,'fire_event',slow)
    with ThreadPoolExecutor(8) as pool:
        results=list(pool.map(lambda _:rt.fire_timeouts(now=NOW+timedelta(seconds=31)),range(8)))
    assert sum(map(len,results))==1
    assert hooks.audits.count('SELECT_TIMEOUT')==1


def test_expired_selection_cannot_approve_before_timer_poll():
    rt,hooks,inst=runtime();_agent_tasks(rt)
    with pytest.raises(ValueError,match='expired'):
        rt.select(_by(rt,inst,'task:select')['id'],'DEC-1003-001','skill:fan-max-derate','tester','role:prod-mgr',now=NOW+timedelta(seconds=31))
    assert not hooks.calls


def test_transition_rolls_back_all_rows_when_instance_save_fails(monkeypatch):
    rt,hooks,inst=runtime()
    wid=_by(rt,inst,'task:diagnose')['id']
    before=rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])
    def fail(_):raise RuntimeError('injected final instance write failure')
    monkeypatch.setattr(rt.repo,'update_instance',fail)
    with pytest.raises(RuntimeError,match='injected'):
        rt.submit(wid,AGENT_OUTPUTS['task:diagnose'],now=NOW)
    assert rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])==before
    assert 'TASK_COMPLETED' not in hooks.audits


def test_late_claim_replay_and_error_cannot_change_completed_work():
    rt,hooks,inst=runtime()
    wi,=rt.repo.fetch_pending_task('cliagents','worker')
    rt.repo.save_task_result(wi['id'],AGENT_OUTPUTS['task:diagnose'],True)
    claimed,=rt.repo.claim_submitted(rt.consumer)
    rt.process_workitem(claimed,now=NOW)
    before=rt.repo.get_instance(inst['proc_inst_id'])
    rt.process_workitem(claimed,now=NOW)
    rt._fail(claimed,RuntimeError('late failure'),NOW)
    assert rt.repo.get_workitem(wi['id'])['status']=='DONE'
    assert rt.repo.get_workitem(wi['id'])['retry']==0
    assert rt.repo.get_instance(inst['proc_inst_id'])==before
    assert hooks.audits.count('TASK_COMPLETED')==1


def test_concurrent_approval_has_one_winner(monkeypatch):
    rt,hooks,inst=runtime();_agent_tasks(rt)
    wid=_by(rt,inst,'task:select')['id']
    approve=hooks.approve_decision
    def slow(*args):
        time.sleep(.03)
        return approve(*args)
    hooks.approve_decision=slow
    def choose(_):
        try:rt.select(wid,'DEC-1003-001','skill:fan-max-derate','tester','role:prod-mgr',now=NOW)
        except ValueError:return False
        return True
    with ThreadPoolExecutor(8) as pool:results=list(pool.map(choose,range(8)))
    assert sum(results)==1
    assert sum(c[0]=='approve_decision' for c in hooks.calls)==1
    assert sum(c[0]=='approve_commands' for c in hooks.calls)==1
