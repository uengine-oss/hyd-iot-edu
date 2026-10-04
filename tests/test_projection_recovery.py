"""Execution projection must survive failure and ignore obsolete caller snapshots."""
from test_instances import ALERT, NOW, FakeHooks, DEF_PATH
from procsvc import engine, instances, procdb
import pytest


def runtime(repo=None, hooks=None):
    hooks = hooks or FakeHooks()
    return instances.InstanceRuntime(repo or procdb.MemoryRepo(), engine.Definition.load(DEF_PATH), hooks), hooks


def test_failed_projection_retried_by_new_runtime():
    rt, hooks = runtime()
    def unavailable(*args, **kwargs):
        raise ConnectionError('test graph offline')
    hooks.record_cypher = unavailable
    inst = rt.on_alert_raise(ALERT, now=NOW)
    restored, good = runtime(rt.repo)
    restored.poll_once(now=NOW)
    assert any(p.get('id') == inst['proc_inst_id'] for p in good.cypher)


def test_obsolete_caller_snapshot_cannot_restore_old_state():
    rt, hooks = runtime()
    old = rt.on_alert_raise(ALERT, now=NOW)
    current = rt.repo.get_instance(old['proc_inst_id'])
    current['status'] = 'COMPLETED'
    rt.repo.update_instance(current)
    rt._project(old)
    assert hooks.cypher[-1]['status'] == 'COMPLETED'


def test_source_rollback_does_not_enqueue_or_change_projection():
    rt, hooks = runtime()
    inst = rt.on_alert_raise(ALERT, now=NOW)
    pid = inst['proc_inst_id']
    with pytest.raises(RuntimeError):
        with rt.repo.instance_transaction('hyd', pid):
            inst['status'] = 'COMPLETED'
            rt.repo.update_instance(inst)
            raise RuntimeError('rollback')
    assert rt.repo.projection_status('hyd', pid)['pending'] == 0
    assert rt.repo.get_instance(pid)['status'] == 'RUNNING'


def test_worker_claim_and_result_enqueue_without_runtime_transition():
    rt, hooks = runtime()
    inst = rt.on_alert_raise(ALERT, now=NOW)
    wi, = rt.repo.fetch_pending_task('cliagents', 'projection-test')
    assert rt.repo.projection_status('hyd', inst['proc_inst_id'])['pending'] > 0
    rt.reconcile_projections()
    assert any(i['draft_status'] == 'STARTED' for i in hooks.cypher[-1]['items'])
    rt.repo.save_task_result(wi['id'], {'cause': 'example'}, final=True)
    rt.reconcile_projections()
    assert any(i['status'] == 'SUBMITTED' for i in hooks.cypher[-1]['items'])


def test_source_change_during_delivery_remains_pending():
    rt, hooks = runtime()
    inst = rt.on_alert_raise(ALERT, now=NOW)
    inst['status'] = 'COMPLETED'
    rt.repo.update_instance(inst)
    def concurrent_change(*args, **kwargs):
        inst['status'] = 'RUNNING'
        rt.repo.update_instance(inst)
        return [dict(projection_key=kwargs['id'],projection_revision=kwargs['revision'],projection_hash=kwargs['payload_hash'])]
    hooks.record_cypher = concurrent_change
    rt._project(inst)
    assert rt.repo.projection_status('hyd', inst['proc_inst_id'])['pending'] == 1
