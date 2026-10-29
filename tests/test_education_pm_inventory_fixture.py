"""Educational ERP initialization, production policy/effects; no operating services."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import re
import os

import pytest
from entsim import data
from entsim.state import EnterpriseState
from hydcommon.maintenance_plan import plan
from hydcommon.maintenance_policy import ScopeError

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'tests/fixtures/education/PM-02.review.json'
MIGRATION = ROOT / 'it/supabase/migrations/20261012000057_b_return_filter_fixture.sql'


def source_skill(sop='SOP-PM-11'):
    review = json.loads(REVIEW.read_text(encoding='utf8'))
    policy = deepcopy(review['links'][sop]['set']['maintenance_policy'])
    return dict(id='fixture-policy',skillId='fixture-policy',sopId=sop,
                source_id=review['source_id'],maintenance_policy=policy,
                actions=[dict(code='WO_RESCHEDULE' if sop=='SOP-PM-13' else 'WO_CREATE',kind='transaction',target='sys:cmms')])


def approved(state, sop='SOP-PM-11', following=False):
    rows=state._pm_rows(); row=next(r for r in rows if r['asset']=='HYD-02')
    prefix='following' if following else 'night'
    window=dict(id=row[prefix+'_window_id'],starts_at=row[prefix+'_window_at'],
                basis='hours_at_following_window' if following else 'hours_at_next_window')
    return plan(source_skill(sop),dict(pm_context=dict(asset='HYD-02',records=rows,
                parts=[state._stock_view(s) for s in state._s['erp']['spare_stock'].values()])),window)


def test_initial_educational_inventory_allows_actual_single_four_thousand_policy():
    state=EnterpriseState(); result=approved(state)
    assert result['assets'][0]['service']['package_interval_h']==4000
    assert result['assets'][0]['service']['next_due_total_h']==12000
    assert {r['part_no']:r['qty'] for r in result['parts_totals']} == {'P-PMP-SEAL':1,'P-RTN-FLT':1}
    assert state._stock_view(state._s['erp']['spare_stock']['P-RTN-FLT'])['available']==2
    assert not state._stock_view(state._s['erp']['spare_stock']['P-RTN-FLT'])['below_reorder_point']
    assert state._stock_view(state._s['erp']['spare_stock']['P-PMP-SEAL'])['available']==1
    assert state._stock_view(state._s['erp']['spare_stock']['P-PMP-SEAL'])['below_reorder_point']


@pytest.mark.parametrize('negative',['missing_filter','shortage','reserved_filter','unknown_oil','deferral'])
def test_educational_fixture_does_not_remove_real_policy_rejections(negative):
    state=EnterpriseState()
    stock=state._s['erp']['spare_stock']
    if negative=='missing_filter':del stock['P-RTN-FLT']
    if negative=='shortage':stock['P-RTN-FLT']['on_hand']=0
    if negative=='reserved_filter':stock['P-RTN-FLT']['reserved']=stock['P-RTN-FLT']['on_hand']
    if negative=='unknown_oil':state._s['cmms']['pm_counters']['HYD-02'].update(total_h=15950,since_pm_h=1950)
    with pytest.raises(ScopeError):approved(state,'SOP-PM-13' if negative=='deferral' else 'SOP-PM-11',following=negative=='deferral')


def test_saved_memory_upgrade_adds_filter_without_overwriting_old_transactions(tmp_path):
    path=tmp_path/'state.sqlite';state=EnterpriseState(path)
    old=state._s['erp']['spare_stock'];old.pop('P-RTN-FLT')
    old['P-PMP-SEAL'].update(on_hand=19,reserved=7,on_order=5)
    state._s['erp']['purchase_requests'].append(dict(id='old-purchase',qty=7))
    state._save();before=deepcopy(old)
    reopened=EnterpriseState(path)
    for key,row in before.items():assert reopened._s['erp']['spare_stock'][key]==row
    assert reopened._s['erp']['spare_stock']['P-RTN-FLT']['on_hand']==2
    assert reopened._s['erp']['purchase_requests']==[dict(id='old-purchase',qty=7)]
    reopened._save();again=EnterpriseState(path)
    assert again._s['erp']['spare_stock']==reopened._s['erp']['spare_stock']


def additive_sql_connection():
    """Executes portable INSERT syntax, explicitly not a PostgreSQL API claim."""
    cx=sqlite3.connect(':memory:');cx.execute("attach ':memory:' as ent")
    cx.execute('create table ent.parts(part_no text primary key,name text,std_price numeric)')
    cx.execute('create table ent.spare_stock(part_no text primary key,on_hand int,reserved int,on_order int,reorder_point int,target_stock int,reserved_for text,base_on_hand int,base_reserved int,need_by_days numeric)')
    return cx


def test_additive_migration_twice_preserves_existing_stock_and_matches_memory():
    cx=additive_sql_connection()
    cx.executescript(MIGRATION.read_text(encoding='utf8'))
    assert cx.execute("select name,std_price from ent.parts where part_no='P-RTN-FLT'").fetchone()==(data.SPARE_BASE['P-RTN-FLT']['name'],12)
    row=cx.execute("select on_hand,reserved,on_order,reorder_point,target_stock,base_on_hand,base_reserved from ent.spare_stock where part_no='P-RTN-FLT'").fetchone()
    assert row==(2,0,0,1,2,2,0)
    cx.execute("update ent.spare_stock set on_hand=17,reserved=6,on_order=9 where part_no='P-RTN-FLT'")
    cx.executescript(MIGRATION.read_text(encoding='utf8'))
    assert cx.execute("select on_hand,reserved,on_order from ent.spare_stock where part_no='P-RTN-FLT'").fetchone()==(17,6,9)


def test_seed_and_incremental_migration_initialize_identical_new_part_only():
    sql=(ROOT/'it/supabase/seed.sql').read_text(encoding='utf8')
    statements=[m.group(0) for m in re.finditer(r'insert\s+into\s+ent\.(?:parts|spare_stock)\b[^;]*;',sql,re.I)
                if "'P-RTN-FLT'" in m.group(0)]
    assert len(statements)==2, 'fresh seed must initialize both part identity and inventory'
    seed=additive_sql_connection();seed.executescript('\n'.join(statements))
    upgrade=additive_sql_connection();upgrade.executescript(MIGRATION.read_text(encoding='utf8'))
    for table in ['parts','spare_stock']:
        assert seed.execute('select * from ent.'+table).fetchall()==upgrade.execute('select * from ent.'+table).fetchall()


def test_single_order_reserves_exact_package_once_and_rejects_stale_second_use():
    state=EnterpriseState();approved_plan=approved(state)
    req=dict(skill='skill:schedule-maintenance-scoped',asset='HYD-02',decision='EDU-FIXTURE',option='fixture-policy',by='isolated-test',params=dict(task='official policy exercise',plan=approved_plan))
    receipt=state.execute(req)
    assert state.execute(req)==receipt
    stock=state._s['erp']['spare_stock']
    assert stock['P-RTN-FLT']['reserved']==1 and stock['P-PMP-SEAL']['reserved']==3
    assert len(state._s['cmms']['work_orders'])==1
    other=deepcopy(req);other['decision']='EDU-FIXTURE-SECOND'
    before=deepcopy(state._s)
    with pytest.raises(ValueError):state.execute(other)
    assert state._s==before


def test_missing_initial_filter_regression_is_detected(monkeypatch):
    initial=deepcopy(data.SPARE_BASE);initial.pop('P-RTN-FLT')
    monkeypatch.setattr(data,'SPARE_BASE',initial)
    with pytest.raises(ScopeError):approved(EnterpriseState())


@pytest.mark.skipif(not os.environ.get('HYD_EDUCATION_FIXTURE_PG_DSN'), reason='Explicit isolated PostgreSQL fixture required')
def test_isolated_pg_actual_consumer_lifecycle_and_migration_twice_preserve_rows():
    import psycopg
    cx=psycopg.connect(os.environ['HYD_EDUCATION_FIXTURE_PG_DSN'])
    try:
        rows=cx.execute('select ent.pm_status_read(null)').fetchone()[0]['records']
        parts=cx.execute('select ent.spare_stock_read(null)').fetchone()[0]['records']
        row=next(r for r in rows if r['asset']=='HYD-02')
        window=dict(id=row['night_window_id'],starts_at=row['night_window_at'],basis='hours_at_next_window')
        approved_plan=plan(source_skill(),dict(pm_context=dict(asset='HYD-02',records=rows,parts=parts)),window)
        assert approved_plan['assets'][0]['service']['package_interval_h']==4000
        req=dict(skill='skill:schedule-maintenance-scoped',asset='HYD-02',decision='ISOLATED-EDU',option='fixture-policy',by='isolated-test',params=dict(plan=approved_plan,task='source policy exercise'))
        receipt=cx.execute('select ent.exec_skill(%s::jsonb)',(json.dumps(req),)).fetchone()[0]
        assert cx.execute('select ent.exec_skill(%s::jsonb)',(json.dumps(req),)).fetchone()[0]==receipt
        assert cx.execute("select reserved from ent.spare_stock where part_no='P-RTN-FLT'").fetchone()[0]==1
        assert cx.execute("select count(*) from ent.pm_part_reservations where work_order=%s",(receipt['ref'],)).fetchone()[0]==2
        tables=['parts','spare_stock','pm_part_reservations','work_orders','purchase_requests']
        def snapshot():
            return {t:cx.execute('select coalesce(jsonb_agg(to_jsonb(x)),\'[]\'::jsonb) from ent.'+t+' x').fetchone()[0] for t in tables}
        before=snapshot()
        for _ in range(2):cx.execute(MIGRATION.read_text(encoding='utf8'))
        assert snapshot()==before
    finally:
        cx.rollback();cx.close()
