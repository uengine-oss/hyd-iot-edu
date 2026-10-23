"""Atomic scoped effects on an explicitly disposable DB; fixtures always rollback."""
import json
from pathlib import Path
import pytest
from test_pm_reschedule_pg import DSN,pg
from test_pm_scoped_schedule import contract,skill,cancellation
from hydcommon.maintenance_plan import plan

pytestmark=pytest.mark.skipif(not DSN,reason='HYD_PM_PG_DSN requires an explicit disposable seeded database')


@pytest.fixture
def scoped(pg):
    cx,_=pg
    migration=Path(__file__).resolve().parents[1]/'it/supabase/migrations/20261012000056_pm_scoped_schedule.sql'
    cx.execute(migration.read_text(encoding='utf8'))
    cx.execute("update ent.pm_counters set since_pm_h=1950,total_h=11950,plan_wo=null,service_position=null where asset='HYD-02'")
    cx.execute("update ent.pm_counters set since_pm_h=1880,total_h=5880,plan_wo=null,service_position=null where asset='HYD-03'")
    cx.execute("update ent.spare_stock set on_hand=7 where part_no='P-PMP-SEAL'")
    # Fictional verified test inventory, never class data or a production seed.
    cx.execute("insert into ent.parts(part_no,name,std_price) values('P-RTN-FLT','리턴 필터 엘리먼트',1) on conflict(part_no) do nothing")
    cx.execute("insert into ent.spare_stock(part_no,on_hand,reorder_point,target_stock,base_on_hand) values('P-RTN-FLT',5,1,5,5) on conflict(part_no) do update set on_hand=5")
    rows=cx.execute('select ent.pm_status_read(null)').fetchone()[0]['records']
    parts=cx.execute('select ent.spare_stock_read(null)').fetchone()[0]['records']
    context=dict(asset='HYD-02',records=rows,parts=parts)
    row=next(r for r in rows if r['asset']=='HYD-02')
    window=dict(id=row['night_window_id'],starts_at=row['night_window_at'],basis='hours_at_next_window',label='이번 예정된 정비 시간')
    approved=plan(skill('bundle'),dict(pm_context=context),window)
    request=dict(skill='skill:schedule-maintenance-scoped',asset='HYD-02',decision='PG-SCOPE',option='skill:pm-source',by='test:review',params=dict(plan=approved,task='원문 패키지'))
    return cx,request


def execute(cx,req):
    function='ent.exec_compensation' if req['skill']=='skill:cancel-maintenance-scoped' or req['skill']=='skill:cancel-work-order' else 'ent.exec_skill'
    return cx.execute('select '+function+'(%s::jsonb)',(json.dumps(req),)).fetchone()[0]


def snapshot(cx):
    return dict(orders=cx.execute('select coalesce(jsonb_agg(to_jsonb(w) order by id),\'[]\'::jsonb) from ent.work_orders w').fetchone()[0],
        counters=cx.execute('select jsonb_agg(to_jsonb(c) order by asset) from ent.pm_counters c').fetchone()[0],
        stocks=cx.execute('select jsonb_agg(to_jsonb(s) order by part_no) from ent.spare_stock s').fetchone()[0],
        reservations=cx.execute("select coalesce(jsonb_agg(to_jsonb(r) order by work_order,part_no),'[]'::jsonb) from ent.pm_part_reservations r").fetchone()[0])


def test_pg_two_actual_orders_receipt_packages_and_idempotency(scoped):
    cx,req=scoped
    receipt=execute(cx,req)
    assert len(receipt['after']['orders'])==2
    assert {w['asset'] for w in receipt['after']['orders']}=={'HYD-02','HYD-03'}
    assert next(w for w in receipt['after']['orders'] if w['asset']=='HYD-02')['package']['package_interval_h']==4000
    assert execute(cx,req)==receipt
    assert cx.execute('select count(*) from ent.pm_part_reservations').fetchone()[0]==4


@pytest.mark.parametrize('failure',['second_insert','peer_hours','peer_window','parts','crew','phase','package_label'])
def test_pg_invalid_or_mid_second_asset_failure_is_wholly_atomic(scoped,failure):
    import psycopg
    cx,req=scoped
    if failure=='second_insert':
        cx.execute("create function ent.test_reject_peer() returns trigger language plpgsql as $$begin if new.asset='HYD-03' and new.scope_group is not null then raise exception 'second scoped order failure';end if;return new;end$$")
        cx.execute('create trigger test_reject_peer before insert on ent.work_orders for each row execute function ent.test_reject_peer()')
    if failure=='peer_hours':cx.execute("update ent.pm_counters set since_pm_h=1700 where asset='HYD-03'")
    if failure=='peer_window':req['params']['plan']['assets'][1]['window']['id']='wrong'
    if failure=='parts':cx.execute("delete from ent.spare_stock where part_no='P-RTN-FLT'")
    if failure=='crew':req['params']['plan']['staffing']['available']=99
    if failure=='phase':cx.execute("update ent.pm_counters set total_h=5870 where asset='HYD-03'")
    if failure=='package_label':req['params']['plan']['assets'][0]['service']['package_name']='wrong'
    before=snapshot(cx);cx.execute('savepoint reject_scope')
    with pytest.raises(psycopg.Error):execute(cx,req)
    cx.execute('rollback to savepoint reject_scope')
    assert snapshot(cx)==before
    assert cx.execute("select count(*) from ent.transactions where decision_id='PG-SCOPE'").fetchone()[0]==0


def test_pg_group_compensation_restores_both_pointers_reservations_and_replays(scoped):
    cx,req=scoped
    before=cx.execute('select part_no,reserved from ent.spare_stock order by part_no').fetchall()
    forward=execute(cx,req);undo=cancellation(forward);receipt=execute(cx,undo)
    assert len(receipt['after']['orders'])==2 and all(w['status']=='취소' for w in receipt['after']['orders'])
    assert cx.execute('select part_no,reserved from ent.spare_stock order by part_no').fetchall()==before
    assert cx.execute("select count(*) from ent.pm_counters where asset in('HYD-02','HYD-03') and plan_wo is not null").fetchone()[0]==0
    assert execute(cx,undo)==receipt


def test_pg_changed_peer_blocks_all_compensation_and_single_ref_bypass(scoped):
    import psycopg
    cx,req=scoped;forward=execute(cx,req)
    cx.execute("update ent.work_orders set status='완료' where scope_group is not null and asset='HYD-03'")
    before=snapshot(cx)
    for skill_name in ('skill:cancel-maintenance-scoped','skill:cancel-work-order'):
        undo=cancellation(forward);undo['skill']=skill_name;cx.execute('savepoint refuse_undo')
        with pytest.raises(psycopg.Error):execute(cx,undo)
        cx.execute('rollback to savepoint refuse_undo');assert snapshot(cx)==before


@pytest.mark.parametrize('mode',['bundle','single'])
def test_pg_issue_uses_physical_stock_ledger_and_refuses_unconfirmed_return(scoped,mode):
    import psycopg
    cx,req=scoped
    selected=skill(mode);selected['maintenance_policy']['stock_effect']='issue'
    if mode=='bundle':selected['sopId']='TEST-GROUP-ISSUE'  # Fictional group effect contract, not source PM14.
    ctx=dict(asset='HYD-02',records=cx.execute('select ent.pm_status_read(null)').fetchone()[0]['records'],
             parts=cx.execute('select ent.spare_stock_read(null)').fetchone()[0]['records'])
    row=next(r for r in ctx['records'] if r['asset']=='HYD-02')
    window=(dict(id=row['night_window_id'],starts_at=row['night_window_at'],basis='hours_at_next_window',label='가상 시험 공통 창')
            if mode=='bundle' else dict(immediate=True,label='즉시'))
    req['params']['plan']=plan(selected,dict(pm_context=ctx),window)
    before=dict((r[0],r[1:]) for r in cx.execute('select part_no,on_hand,reserved from ent.spare_stock').fetchall())
    receipt=execute(cx,req)
    for number in ('P-PMP-SEAL','P-RTN-FLT'):
        actual=cx.execute('select on_hand,reserved from ent.spare_stock where part_no=%s',(number,)).fetchone()
        if mode=='bundle':assert actual==(before[number][0]-2,before[number][1])
        else:assert actual==(before[number][0]-1,before[number][1])
    count=cx.execute("select count(*) from ent.pm_part_reservations where stock_effect='issue' and released_at is null").fetchone()[0]
    if mode=='bundle':assert count==4
    else:assert count==2
    after=snapshot(cx);cx.execute('savepoint no_fake_return')
    with pytest.raises(psycopg.Error):execute(cx,cancellation(receipt))
    cx.execute('rollback to savepoint no_fake_return');assert snapshot(cx)==after


@pytest.mark.parametrize('stale',[False,True])
def test_pg_reschedule_preserves_owned_allocations_with_no_free_inventory(scoped,stale):
    import psycopg
    cx,req=scoped
    req['params']['plan']['policy']['scope']='single'
    ctx=dict(asset='HYD-02',records=cx.execute('select ent.pm_status_read(null)').fetchone()[0]['records'],parts=cx.execute('select ent.spare_stock_read(null)').fetchone()[0]['records'])
    row=next(r for r in ctx['records'] if r['asset']=='HYD-02')
    req['params']['plan']=plan(skill(),dict(pm_context=ctx),dict(id=row['night_window_id'],starts_at=row['night_window_at'],basis='hours_at_next_window',label='예정'))
    forward=execute(cx,req)
    cx.execute("update ent.pm_counters set since_pm_h=1800,total_h=11800 where asset='HYD-02'")
    cx.execute("update ent.spare_stock set on_hand=reserved,on_order=0 where part_no in('P-PMP-SEAL','P-RTN-FLT')")
    read=cx.execute("select ent.pm_status_read('HYD-02')").fetchone()[0]
    facts=read['facts'];facts['pm_context']=dict(asset='HYD-02',records=cx.execute('select ent.pm_status_read(null)').fetchone()[0]['records'],parts=cx.execute('select ent.spare_stock_read(null)').fetchone()[0]['records'])
    row=next(r for r in facts['pm_context']['records'] if r['asset']=='HYD-02')
    # Match the production facts projection from actual row/settings, never a default limit.
    facts['pm_limit_hours']=row['pm_interval_h']*(1+row['pm_tolerance_pct']/100)
    selected=skill();selected['actions'][0]['code']='WO_RESCHEDULE';selected['maintenance_policy']['stock_effect']='preserve'
    approved=plan(selected,facts,dict(id=facts['following_window_id'],starts_at=facts['following_window_at'],basis='hours_at_following_window',label='그다음'))
    change=dict(skill='skill:reschedule-maintenance',asset='HYD-02',decision='PG-OWNED',option='skill:pm-source',by='test:review',params=dict(ref=approved['ref'],expected_order=approved['expected_order'],cycle=approved['cycle'],plan=approved,window_id=approved['window']['id']))
    if stale:cx.execute('update ent.pm_part_reservations set qty=qty+1 where work_order=%s',(forward['ref'],))
    before=snapshot(cx)
    if stale:
        cx.execute('savepoint stale_allocation')
        with pytest.raises(psycopg.Error):execute(cx,change)
        cx.execute('rollback to savepoint stale_allocation');assert snapshot(cx)==before
    else:
        result=execute(cx,change)
        assert result['ref']==forward['ref']
        after=snapshot(cx)
        assert after['stocks']==before['stocks'] and after['reservations']==before['reservations']
        assert len(after['orders'])==len(before['orders'])


def test_pg_b_reset_releases_held_parts_and_full_reset_archives_reservations(scoped):
    """2026-10-23: B [초기화]가 예약을 남겨 다시 연 B의 부품 가용이 0이었고, 업무 전체 초기화는 예약 행의 FK 때문에 실패했다."""
    cx,req=scoped
    cx.execute((Path(__file__).resolve().parents[1]/'it/supabase/migrations/20261023000059_reset_releases_pm_parts.sql').read_text(encoding='utf8'))
    forward=execute(cx,req)
    assert cx.execute('select count(*) from ent.pm_part_reservations where released_at is null').fetchone()[0]>0
    cx.execute('select ent.reset_pm_counters(null)')
    orders=cx.execute("select status from ent.work_orders where scope_group=(select scope_group from ent.work_orders where id=%s)",(forward['ref'],)).fetchall()
    assert orders and {s for (s,) in orders}=={'취소'}
    assert cx.execute('select count(*) from ent.pm_part_reservations where released_at is null').fetchone()[0]==0
    assert cx.execute("select bool_and(on_hand=base_on_hand and reserved=base_reserved) from ent.spare_stock where part_no in('P-PMP-SEAL','P-RTN-FLT')").fetchone()[0]
    held=cx.execute('select count(*) from ent.pm_part_reservations').fetchone()[0]
    cx.execute('select ent.reset_executions()')
    assert cx.execute('select count(*) from ent.work_orders').fetchone()[0]==0
    assert cx.execute("select count(*) from ent.execution_archive where table_name='pm_part_reservations' and reset_no=(select max(reset_no) from ent.execution_archive)").fetchone()[0]==held
