"""A082 — a person closes an agent task that cannot continue (PENDING after bounded retries/corrections, or a worker run
that died). Human tasks, live tasks and instances whose Incident is still open are refused."""
import copy
import pytest
from uuid import uuid4

from procsvc import engine, manual_extraction as extraction
from procsvc.manual_sources import ManualSources
from test_instances import rt
from test_instance_mode import world, NOW, NoFx  # noqa: F401
from test_approval_delivery import ready


@pytest.fixture
def stuck(rt, tmp_path):
    runtime, _ = rt
    archive = ManualSources(tmp_path / 'manual.sqlite3')
    source = archive.save('hyd', 'm.txt', '정비 절차\n1. 정지한다.\n'.encode())
    inst = extraction.start(runtime, source, str(uuid4()))
    wi = runtime.repo.fetch_pending_task('cliagents', 'test-worker')[0]
    assert runtime.repo.update_task_error(wi['id'], expected_consumer='test-worker')          # the run died
    return runtime, inst, runtime.repo.get_workitem(wi['id'])


def test_failed_run_is_closed_with_reason_and_the_lone_task_instance_ends(stuck):
    runtime, inst, wi = stuck
    assert wi['status'] == 'IN_PROGRESS' and wi['draft_status'] == 'FAILED'
    out = runtime.close_agent_task(wi['id'], '지식 관리자', '시험 실행 잔재: 워커가 argv 한도로 죽음', now=NOW)
    row = runtime.repo.get_workitem(wi['id'])
    assert row['status'] == 'CANCELLED' and row['draft_status'] == 'CANCELLED' and row['consumer'] is None and '[Closed by 지식 관리자]' in row['log']
    final = runtime.repo.get_instance(inst['proc_inst_id'])
    assert out['instance_ended'] and final['status'] == 'COMPLETED' and final['end_event'] == 'closed-by-human' and final['current_activity_ids'] == []
    assert runtime.repo.fetch_pending_task('cliagents', 'test-worker') == []                  # nobody re-runs it
    events = runtime.repo.list_events(todo_id=wi['id'])
    assert any(e['event_type'] == 'task_cancelled' and e['job_id'] == 'TASK_CLOSED' and e['crew_type'] == 'human' and e['data']['reason'].startswith('시험 실행 잔재') and e['data']['previous']['draft_status'] == 'FAILED' for e in events)
    with pytest.raises(ValueError):                                                            # not twice
        runtime.close_agent_task(wi['id'], '지식 관리자', '다시', now=NOW)


def test_pending_after_correction_rounds_is_closable_but_live_or_done_is_not(stuck):
    runtime, inst, wi = stuck
    wi.update(status='PENDING', draft_status='COMPLETED'); runtime.repo.update_workitem(wi)
    assert runtime.close_agent_task(wi['id'], '검토자', '3회 거부 뒤 사람 판단: 원문이 절차 문서가 아님', now=NOW)['status'] == 'CANCELLED'


@pytest.mark.parametrize('status,draft', [('IN_PROGRESS', 'STARTED'), ('IN_PROGRESS', 'FB_REQUESTED'), ('SUBMITTED', 'COMPLETED'), ('DONE', 'COMPLETED')])
def test_live_or_finished_agent_tasks_are_refused(stuck, status, draft):
    runtime, inst, wi = stuck
    wi.update(status=status, draft_status=draft); runtime.repo.update_workitem(wi)
    with pytest.raises(ValueError, match='멈춘'):
        runtime.close_agent_task(wi['id'], '검토자', '이유', now=NOW)


def test_reason_and_person_are_required(stuck):
    runtime, inst, wi = stuck
    for by, reason in (('', '이유'), ('사람', ''), ('사람', '   ')):
        with pytest.raises(ValueError, match='사유'):
            runtime.close_agent_task(wi['id'], by, reason, now=NOW)


def test_human_task_and_open_incident_are_refused(world):
    rt_, inst, inc, d, sel = ready(world)
    with pytest.raises(PermissionError):
        rt_.close_agent_task(sel['id'], '사람', '이유', now=NOW)
    rank = next(w for w in rt_.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None) if w['activity_id'] == 'task:rank')
    rank.update(status='PENDING'); rt_.repo.update_workitem(rank)
    assert inc.state not in ('CLOSED', 'ESCALATED', 'REJECTED_BY_OPERATOR', 'RESOLVED_WITHOUT_ACTION')
    with pytest.raises(ValueError, match='사건이 아직 진행 중'):
        rt_.close_agent_task(rank['id'], '사람', '이유', now=NOW)
    assert rt_.repo.get_workitem(sel['id'])['status'] == 'IN_PROGRESS'


# ---------------------------------------------------------------- A097 · a person cancels a RUNNING agent task (vue3 FormWorkItem)
def test_running_agent_task_is_cancelled_by_a_person_the_worker_stops_and_the_row_can_be_closed(rt, tmp_path):
    runtime, _ = rt
    archive = ManualSources(tmp_path / 'manual.sqlite3')
    source = archive.save('hyd', 'm.txt', '정비 절차\n1. 정지한다.\n'.encode())
    extraction.start(runtime, source, str(uuid4()))
    with pytest.raises(ValueError):                                             # nothing is running yet
        runtime.cancel_agent_task(runtime.repo.list_workitems(limit=None)[-1]['id'], '사람', '이유', now=NOW)
    wi = runtime.repo.fetch_pending_task('cliagents', 'test-worker')[0]
    out = runtime.cancel_agent_task(wi['id'], '운전원', '잘못된 문서를 올렸다', now=NOW)
    assert out['draft_status'] == 'CANCELLED' and out['consumer'] == 'test-worker'
    row = runtime.repo.get_workitem(wi['id'])
    assert row['status'] == 'IN_PROGRESS' and row['draft_status'] == 'CANCELLED' and '[Cancel requested by 운전원]' in row['log']
    assert any(e['job_id'] == 'TASK_CANCEL_REQUESTED' for e in runtime.repo.list_events(todo_id=wi['id']))
    # the worker's own check sees the mark and gives the claim back (runner._cancelled → release_worker_claim)
    from worker.runner import Runner
    from test_worker import _settings
    runner = Runner(_settings(tmp_path / 'w'), runtime.repo, exec_fn=None, schema_prompt='x', resolve_provider=lambda _: object())
    assert runner._cancelled(dict(wi, consumer='test-worker'))
    assert runtime.repo.release_worker_claim(wi['id'], 'test-worker')
    with pytest.raises(ValueError):                                             # cannot cancel twice
        runtime.cancel_agent_task(wi['id'], '운전원', '다시', now=NOW)
    assert runtime.repo.save_task_result(wi['id'], {'proposal': {}}, final=True, expected_consumer='test-worker') is False   # a late result is refused
    assert runtime.close_agent_task(wi['id'], '운전원', '취소 뒤 닫음', now=NOW)['status'] == 'CANCELLED'


def test_cancel_refuses_human_tasks_and_needs_by_and_reason(rt):
    runtime, _ = rt
    inst = runtime.on_alert_raise({'alertId': 'c-1', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE'})
    human = [w for w in runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None) if not w.get('agent_orch')]
    if human:
        with pytest.raises(PermissionError):
            runtime.cancel_agent_task(human[0]['id'], '사람', '이유', now=NOW)
    agent = runtime.repo.fetch_pending_task('cliagents', 'w1')
    if agent:
        for by, reason in (('', '이유'), ('사람', '')):
            with pytest.raises(ValueError):
                runtime.cancel_agent_task(agent[0]['id'], by, reason, now=NOW)
