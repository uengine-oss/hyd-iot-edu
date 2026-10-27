"""Question binding through a disposable PostgreSQL runtime and real worker."""
from uuid import uuid4

import pytest

from procsvc import ask
from test_backend_pg_contracts import DSN, pg
from test_b5_ask import DEFS, UP, _cli
from worker.runner import Runner
from worker.settings import Settings

pytestmark = pytest.mark.skipif(not DSN, reason='requires a disposable migrated PostgreSQL')


def prepare(pg):
    _, runtime, _ = pg
    with runtime.repo._conn() as db:
        db.execute("insert into users(id,username,is_agent,agent_type,tenant_id,goal,tools) "
                   "values(%s,%s,true,'agent',%s,%s,%s)",
                   ('sys:agent','시험 에이전트',runtime.tenant_id,'기존 목표','enterprise'))
    return runtime


def start(runtime, request):
    return ask.start(runtime, '현재 수업 상태는?', 'sys:agent', '수강생', request,
                     definitions_dir=DEFS, worker_probe=UP, bridge='off')


def test_pg_reused_request_binds_goal_and_display_name_is_flexible(pg):
    runtime = prepare(pg)
    request = str(uuid4())
    first = start(runtime, request)
    with runtime.repo._conn() as db:
        db.execute('update users set username=%s where id=%s', ('새 이름','sys:agent'))
    assert start(runtime, request)['id'] == first['id']
    with runtime.repo._conn() as db:
        db.execute('update users set goal=%s where id=%s', ('변경된 목표','sys:agent'))
    with pytest.raises(ValueError, match='다른.*조건'):
        start(runtime, request)
    assert start(runtime, str(uuid4()))['id'] != first['id']


def test_pg_queued_profile_change_stops_before_model(pg, tmp_path):
    runtime = prepare(pg)
    first = start(runtime, str(uuid4()))
    with runtime.repo._conn() as db:
        db.execute('update users set goal=%s where id=%s', ('변경된 목표','sys:agent'))
    requests = []
    runner = Runner(Settings(workspace_root=tmp_path, tenant_id=runtime.tenant_id,
                             consumer='binding-pg', cancel_check_every_s=0),
                    runtime.repo, exec_fn=_cli({'status':'cannot_answer','reason':'fixture'}, requests=requests),
                    schema_prompt='# fixture', resolve_provider=lambda _:object())
    assert runner.poll_once() == 1
    row = runtime.repo.get_workitem(first['workitem'])
    assert not requests and row['draft_status'] == 'FAILED' and row['output'] is None


def test_pg_unchanged_question_reaches_worker_once(pg, tmp_path):
    runtime = prepare(pg)
    first = start(runtime, str(uuid4()))
    requests = []
    runner = Runner(Settings(workspace_root=tmp_path, tenant_id=runtime.tenant_id,
                             consumer='binding-pg', cancel_check_every_s=0),
                    runtime.repo, exec_fn=_cli({'status':'cannot_answer','reason':'fixture'}, requests=requests),
                    schema_prompt='# fixture', resolve_provider=lambda _:object())
    assert runner.poll_once() == 1
    row = runtime.repo.get_workitem(first['workitem'])
    assert len(requests) == 1 and row['status'] == 'SUBMITTED'
