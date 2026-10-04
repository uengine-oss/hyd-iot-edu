"""Actual silent child processes, not generators that conveniently emit a tick."""
import json
from pathlib import Path
import sys
import threading
import time

import pytest
from cliagents import ExecRequest
from procsvc.procdb import MemoryRepo
from worker.codex_provider import WorkerCodexProvider
from worker.runner import Runner,RunFailed,Cancelled
from worker.settings import Settings


class SilentProcess(WorkerCodexProvider):
    def __init__(self,path):
        super().__init__();self.path=path

    def exec_argv(self,request):
        return [sys.executable,'-u',str(self.path)]


def setup_run(tmp_path,timeout=10):
    script=tmp_path/'silent_agent.py'
    script.write_text('import time,json\ntime.sleep(3)\nprint(json.dumps('+repr({
        'type':'item.completed','item':{'type':'agent_message','text':'{"answer":"late"}'}})+'))\n',encoding='utf-8')
    repo=MemoryRepo()
    row={'id':'silent-test','proc_inst_id':'probe','activity_id':'task',
         'status':'IN_PROGRESS','draft_status':'STARTED','consumer':'test-owner',
         'tenant_id':'hyd','start_date':'2026-10-04T00:00:00Z'}
    repo.insert_workitems([row])
    runner=Runner(Settings(consumer='test-owner',run_timeout_s=timeout,cancel_check_every_s=.025,
                  workspace_root=tmp_path),repo,schema_prompt='')
    return runner,repo,row,SilentProcess(script),ExecRequest(prompt='test',workdir=str(tmp_path))


def test_wall_clock_timeout_stops_silent_process_without_waiting_for_output(tmp_path):
    runner,repo,row,provider,request=setup_run(tmp_path,timeout=.25)
    started=time.monotonic()
    with pytest.raises(RunFailed,match='제한 시간'):
        runner._stream(row,'job',provider,request,None,'test')
    assert time.monotonic()-started < 1.5,'deadline was checked only after the silent process emitted output'


@pytest.mark.parametrize('cancel',[
    {'draft_status':'CANCELLED'},
    {'status':'CANCELLED'},
])
def test_silent_process_observes_draft_and_engine_cancellation(tmp_path,cancel):
    runner,repo,row,provider,request=setup_run(tmp_path)
    timer=threading.Timer(.25,lambda:repo.update_workitem(repo.get_workitem(row['id'])|cancel))
    started=time.monotonic();timer.start()
    try:
        with pytest.raises(Cancelled):
            runner._stream(row,'job',provider,request,None,'test')
        assert time.monotonic()-started < 1.5,'cancellation waited for another CLI event'
    finally:
        timer.cancel();timer.join()
