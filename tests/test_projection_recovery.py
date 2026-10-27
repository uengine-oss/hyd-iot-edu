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


def test_projection_reads_only_existing_users_in_the_same_tenant():
    rt,hooks=runtime()
    rt.repo.upsert_user({'id':'user:kim','username':'김운전','tenant_id':'hyd','is_agent':False})
    rt.repo.upsert_user({'id':'agent:shift','username':'인계 에이전트','tenant_id':'hyd','is_agent':True,'agent_type':'agent'})
    rt.repo.upsert_user({'id':'user:other','username':'다른 사용자','tenant_id':'other','is_agent':False})
    inst=rt.on_alert_raise(ALERT,now=NOW)
    current=rt.repo.get_instance(inst['proc_inst_id'])
    current['role_bindings']=[{'name':'인계자','endpoint':'user:kim'},
                              {'name':'에이전트','endpoint':'agent:shift'},
                              {'name':'누락','endpoint':'user:other'}]
    rt.repo.update_instance(current)
    rt._project(current)
    actors={a['source_id']:a for a in hooks.cypher[-1]['actors']}
    assert set(actors)=={'user:kim','agent:shift'}
    assert actors['user:kim']['kind']=='User' and actors['user:kim']['username']=='김운전'
    assert actors['agent:shift']['kind']=='Agent'
    assert all(a['graph_id'].startswith('execution-actor:hyd:') for a in actors.values())


def test_projection_keeps_all_workitem_assignees_without_duplicate_rows():
    rt,hooks=runtime()
    for uid,name in [('user:kim','김운전'),('user:choi','최운전')]:
        rt.repo.upsert_user({'id':uid,'username':name,'tenant_id':'hyd','is_agent':False})
    inst=rt.on_alert_raise(ALERT,now=NOW)
    item=rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    item['user_id']='user:kim,user:choi,user:kim'
    rt.repo.update_workitem(item)
    rt._project(inst)
    projected=next(w for w in hooks.cypher[-1]['items'] if w['id']==item['id'])
    assert projected['performers']==['user:kim','user:choi']
    from procsvc.instances import format_execution
    row={'instance':{'id':'p'},'items':[{'workitem':{'id':'w'},'performer':'user:kim','performer_kind':'multi'},
                                          {'workitem':{'id':'w'},'performer':'user:choi','performer_kind':'multi'},
                                          {'workitem':{'id':'w'},'performer':'user:kim','performer_kind':'multi'}]}
    result=format_execution([row])['workitems']
    assert len(result)==1 and result[0]['assigned_to']=='user:kim,user:choi' and result[0]['assigned_kind']=='multi'


def test_actor_constraint_failure_keeps_projection_pending_and_retries():
    rt,hooks=runtime();calls=[]
    def ensure():
        calls.append('attempt')
        if len(calls)==1:raise ConnectionError('graph unavailable')
    hooks.ensure_actor_schema=ensure
    inst=rt.on_alert_raise(ALERT,now=NOW)
    status=rt.repo.projection_status('hyd',inst['proc_inst_id'])
    assert status['pending']>0 and 'graph unavailable' in status['last_error']
    rt._project(inst)
    status=rt.repo.projection_status('hyd',inst['proc_inst_id'])
    assert status['pending']==0 and calls==['attempt','attempt']
    rt.repo.update_instance(rt.repo.get_instance(inst['proc_inst_id']))
    rt._project(inst)
    assert calls==['attempt','attempt']
