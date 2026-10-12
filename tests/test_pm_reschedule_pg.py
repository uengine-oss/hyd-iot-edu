"""Run only against an explicitly supplied disposable enterprise database.

Each connection rolls back migration, fixture rows and transactions. No default DSN.
"""
import json
import os
from pathlib import Path
from uuid import uuid4
import pytest

DSN=os.environ.get('HYD_PM_PG_DSN')
pytestmark=pytest.mark.skipif(not DSN,reason='HYD_PM_PG_DSN must be an explicit disposable seeded database')


@pytest.fixture
def pg():
    import psycopg
    connection=psycopg.connect(DSN)
    try:
        migration=Path(__file__).resolve().parents[1]/'it/supabase/migrations/20261012000054_pm_reschedule.sql'
        connection.execute(migration.read_text(encoding='utf8'))
        connection.execute("update ent.pm_counters set since_pm_h=1000,plan_wo=null where asset='HYD-02'")
        ref='WO-TEST-'+uuid4().hex
        connection.execute("insert into ent.work_orders(id,asset,task,window_label) values(%s,'HYD-02','fixture PM','previous')",(ref,))
        connection.execute("update ent.pm_counters set plan_wo=%s where asset='HYD-02'",(ref,))
        order=connection.execute('select to_jsonb(w) from ent.work_orders w where id=%s',(ref,)).fetchone()[0]
        facts=connection.execute("select ent.pm_status_read('HYD-02')->'facts'").fetchone()[0]
        request=dict(skill='skill:reschedule-maintenance',asset='HYD-02',by='test:review',option='skill:pm13',
                     decision='DEC-TEST-'+uuid4().hex,params=dict(ref=ref,expected_order=order,cycle=facts['pm_cycle'],window_id=facts['following_window_id']))
        yield connection,request
    finally:
        connection.rollback();connection.close()


def execute(connection,request):
    return connection.execute('select ent.exec_skill(%s::jsonb)',(json.dumps(request),)).fetchone()[0]


def test_pg_reschedules_existing_row_and_idempotent_receipt(pg):
    cx,request=pg
    before=cx.execute('select count(*) from ent.work_orders').fetchone()[0]
    result=execute(cx,request)
    assert result['ref']==request['params']['ref']
    assert execute(cx,request)==result
    assert cx.execute('select count(*) from ent.work_orders').fetchone()[0]==before
    row=cx.execute('select window_id from ent.work_orders where id=%s',(result['ref'],)).fetchone()
    assert row[0]==request['params']['window_id']


@pytest.mark.parametrize('change',['no_plan','stale_order','deadline','window','cycle'])
def test_pg_invalid_reschedule_is_atomic(pg,change):
    import psycopg
    cx,request=pg
    if change=='no_plan':cx.execute("update ent.pm_counters set plan_wo=null where asset='HYD-02'")
    if change=='stale_order':request['params']['expected_order']['task']='wrong'
    if change=='deadline':cx.execute("update ent.pm_counters set since_pm_h=3000 where asset='HYD-02'")
    if change=='window':request['params']['window_id']='missing'
    if change=='cycle':request['params']['cycle']+=1
    before=cx.execute('select to_jsonb(w) from ent.work_orders w where id=%s',(request['params']['ref'],)).fetchone()[0]
    cx.execute('savepoint invalid_request')
    with pytest.raises(psycopg.Error):execute(cx,request)
    cx.execute('rollback to savepoint invalid_request')
    after=cx.execute('select to_jsonb(w) from ent.work_orders w where id=%s',(request['params']['ref'],)).fetchone()[0]
    assert before==after
    assert cx.execute('select count(*) from ent.transactions where decision_id=%s',(request['decision'],)).fetchone()[0]==0
