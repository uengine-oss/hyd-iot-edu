"""Explicit fictional unit fixtures, never actual class inventory or review records."""
from copy import deepcopy
import pytest
from hydcommon.maintenance_policy import policy,service,scope,ScopeError
from hydcommon.maintenance_plan import plan
from entsim.state import EnterpriseState


def contract(mode='single'):
    basic=[dict(part_no='P-PMP-SEAL',qty=1,name='펌프 축 씰 키트'),dict(part_no='P-RTN-FLT',qty=1,name='리턴 필터 엘리먼트')]
    return dict(version=1,scope=mode,stock_effect='reserve',interval_h=2000,tolerance_pct=10,model_assets=['HYD-01','HYD-02','HYD-03'],
        anchor=dict(source_id='test:pm',quote='주기 2,000 h, 4,000 h, 8,000 h'),
        model_anchor=dict(source_id='test:pm',quote='같은 모델 세 대'),packages=[
        dict(interval_h=2000,sop='SOP-PM-21',name='2,000 h 정기 점검',parts=deepcopy(basic)),
        dict(interval_h=4000,sop='SOP-PM-22',name='4,000 h 정기 점검',parts=deepcopy(basic)),
        dict(interval_h=8000,sop='SOP-PM-23',name='8,000 h 정기 점검',parts=deepcopy(basic)+
            [dict(part_no=None,qty=None,name='작동유',mapping_reason='원문 수량과 실제 부품 연결 미상')])])


def configured_state():
    state=EnterpriseState()
    state._s['erp']['spare_stock']['P-PMP-SEAL']['on_hand']=7
    state._s['erp']['spare_stock']['P-RTN-FLT']=dict(part_no='P-RTN-FLT',on_hand=5,reserved=0,on_order=0,
        reorder_point=1,target_stock=5,below_since=None,name='리턴 필터 엘리먼트')
    peer=state._s['cmms']['pm_counters']['HYD-03'];peer.update(total_h=5880,since_pm_h=1880)
    return state


def context(state,asset='HYD-02'):
    return dict(asset=asset,records=state._pm_rows(),parts=[state._stock_view(p) for p in state._s['erp']['spare_stock'].values()])


def skill(mode='single'):
    return dict(skillId='skill:pm-source',id='skill:pm-source',sopId='SOP-PM-14' if mode=='bundle' else 'SOP-PM-11',
        source_id='test:pm',maintenance_policy=contract(mode),actions=[dict(code='WO_CREATE',kind='transaction',target='sys:cmms')])


def approved_plan(state,mode='single'):
    ctx=context(state);row=next(r for r in ctx['records'] if r['asset']=='HYD-02')
    window=dict(id=row['night_window_id'],starts_at=row['night_window_at'],basis='hours_at_next_window',label='이번 예정된 정비 시간')
    return plan(skill(mode),dict(pm_context=ctx),window)


def request(state,mode='single'):
    return dict(skill='skill:schedule-maintenance-scoped',asset='HYD-02',decision='DEC-SCOPE',option='skill:pm-source',by='test:review',
        params=dict(task='원문 정비',plan=approved_plan(state,mode)))


def test_actual_counters_select_four_thousand_package_at_twelve_thousand_not_generation_one():
    state=configured_state();row=next(r for r in state._pm_rows() if r['asset']=='HYD-02')
    derived,_=service(row,policy(contract()))
    assert row['cycle']==1 and derived['service_position']==6
    assert derived['next_due_total_h']==12000 and derived['package_interval_h']==4000


def test_early_service_phase_requires_actual_completion_history_not_alert_cycle():
    row=dict(pm_since_h=1950,pm_total_h=11830,cycle=17)
    with pytest.raises(ValueError,match='이력'):service(row,contract())
    row['service_position']=5
    result,_=service(row,contract())
    assert result['service_position']==6 and result['next_due_total_h']==11880


def test_missing_filter_blocks_with_known_four_thousand_diagnostics_and_name():
    state=configured_state();del state._s['erp']['spare_stock']['P-RTN-FLT']
    with pytest.raises(ScopeError,match='리턴 필터') as failed:approved_plan(state)
    diagnostic=failed.value.diagnostics
    assert diagnostic['ready'] is False and diagnostic['assets'][0]['service']['package_interval_h']==4000
    assert any(p['part_no']=='P-RTN-FLT' and p['available'] is None and not p['verified'] for p in diagnostic['assets'][0]['parts'])


@pytest.mark.parametrize('change',['wrong_roster','peer_lower','peer_window','part_shortage','unknown_crew','ambiguous_phase','existing_plan'])
def test_bundle_never_falls_back_to_one_asset_or_unknown_scope(change):
    state=configured_state();req=request(state,'bundle')
    if change=='wrong_roster':req['params']['plan']['policy']['model_assets'].remove('HYD-03')
    if change=='peer_lower':state._s['cmms']['pm_counters']['HYD-03']['since_pm_h']=1700
    if change=='peer_window':req['params']['plan']['assets'][1]['window']['id']='wrong'
    if change=='part_shortage':state._s['erp']['spare_stock']['P-PMP-SEAL']['on_hand']=3
    if change=='unknown_crew':req['params']['plan']['staffing']['available']=None
    if change=='ambiguous_phase':state._s['cmms']['pm_counters']['HYD-03']['total_h']=5870
    if change=='existing_plan':state._s['cmms']['pm_counters']['HYD-03']['plan_wo']='existing'
    before=deepcopy(state._s)
    with pytest.raises(ValueError):state.execute(req)
    assert state._s==before and not state._tx


def test_bundle_actual_two_orders_pointers_reservations_receipt_and_complete_replay():
    state=configured_state();req=request(state,'bundle');prior_count=len(state._s['cmms']['work_orders'])
    before=state._s['erp']['spare_stock']['P-PMP-SEAL']['reserved'];receipt=state.execute(req)
    assert len(receipt['after']['orders'])==2
    assert {o['asset'] for o in receipt['after']['orders']}=={'HYD-02','HYD-03'}
    assert len(state._s['cmms']['work_orders'])==prior_count+2
    assert state._s['erp']['spare_stock']['P-PMP-SEAL']['reserved']==before+2
    assert all(state._s['cmms']['pm_counters'][o['asset']]['plan_wo']==o['id'] for o in receipt['after']['orders'])
    assert receipt['after']['plan']['staffing']['shortfall']==2 and not receipt['after']['plan']['staffing']['confirmed']
    assert state.execute(req)==receipt


def cancellation(receipt):
    return dict(skill='skill:cancel-maintenance-scoped',asset='HYD-02',decision='DEC-UNDO',option='skill:pm-source',
                by='test:review',compensates=receipt['id'],params=dict(ref=receipt['ref']))


def test_group_compensation_cancels_both_and_restores_both_pointers_and_parts_atomically():
    state=configured_state();before={k:p['reserved'] for k,p in state._s['erp']['spare_stock'].items()}
    forward=state.execute(request(state,'bundle'));req=cancellation(forward);receipt=state.execute(req)
    assert len(receipt['after']['orders'])==2 and all(o['status']=='취소' for o in receipt['after']['orders'])
    assert all(state._s['cmms']['pm_counters'][a]['plan_wo'] is None for a in ('HYD-02','HYD-03'))
    assert {k:p['reserved'] for k,p in state._s['erp']['spare_stock'].items()}==before
    assert state.execute(req)==receipt


def test_one_advanced_peer_blocks_entire_group_compensation_and_legacy_single_cancel():
    state=configured_state();forward=state.execute(request(state,'bundle'))
    state._s['cmms']['work_orders'][0]['status']='완료';before=deepcopy(state._s)
    with pytest.raises(ValueError,match='whole'):state.execute(cancellation(forward))
    assert state._s==before
    with pytest.raises(ValueError,match='그룹'):state.execute(dict(cancellation(forward),skill='skill:cancel-work-order'))
    assert state._s==before


def test_mid_second_order_fault_rolls_back_all_pointers_orders_and_reservations(monkeypatch):
    from entsim import state as module
    state=configured_state();req=request(state,'bundle');before=deepcopy(state._s);original=module._id;calls=[]
    def fail_second(prefix):
        calls.append(prefix)
        if len(calls)==2:raise OSError('second order failure')
        return original(prefix)
    monkeypatch.setattr(module,'_id',fail_second)
    with pytest.raises(OSError):state.execute(req)
    assert state._s==before and not state._done and not state._tx


def test_registered_source_orders_are_not_physical_completion_or_fake_service_history():
    state=configured_state();receipt=state.execute(request(state));before=deepcopy(state._s)
    for operation in ('skill:complete-maintenance','skill:pm-reset'):
        with pytest.raises(ValueError):state.execute(dict(skill=operation,asset='HYD-02',decision=operation,params=dict(ref=receipt['ref'])))
        assert state._s==before


def test_immediate_issue_deducts_actual_stock_and_cannot_fake_return_on_cancel():
    state=configured_state();selected=skill();selected['maintenance_policy']['stock_effect']='issue'
    row=next(r for r in context(state)['records'] if r['asset']=='HYD-02')
    selected_plan=plan(selected,dict(pm_context=context(state)),dict(immediate=True,label='즉시'))
    req=request(state);req['params']['plan']=selected_plan
    before={k:(p['on_hand'],p['reserved']) for k,p in state._s['erp']['spare_stock'].items()}
    receipt=state.execute(req)
    for number in ('P-PMP-SEAL','P-RTN-FLT'):
        stock=state._s['erp']['spare_stock'][number]
        assert stock['on_hand']==before[number][0]-1 and stock['reserved']==before[number][1]
    after=deepcopy(state._s)
    with pytest.raises(ValueError):state.execute(cancellation(receipt))
    assert state._s==after


def test_incoming_stock_does_not_satisfy_immediate_issue():
    state=configured_state();selected=skill();selected['maintenance_policy']['stock_effect']='issue'
    state._s['erp']['spare_stock']['P-RTN-FLT'].update(on_hand=0,on_order=20)
    with pytest.raises(ScopeError):
        plan(selected,dict(pm_context=context(state)),dict(immediate=True,label='즉시'))


@pytest.mark.parametrize('effect',['reserve','issue'])
def test_b_reset_cancels_part_holding_orders_and_restores_their_parts_to_class_start(effect):
    """2026-10-23 라이브: B [초기화]가 계수기만 되돌려, 다시 연 B는 '도래'인데 앞 오더가 잡은 씰 · 필터 때문에 단독 · 즉시 시행이 재고 부족으로 빠졌다."""
    state=configured_state();req=request(state)
    if effect=='issue':
        selected=skill();selected['maintenance_policy']['stock_effect']='issue'
        req['params']['plan']=plan(selected,dict(pm_context=context(state)),dict(immediate=True,label='즉시'))
    start={k:(v['on_hand'],v['reserved'],v['on_order']) for k,v in state._s['erp']['spare_stock'].items()}
    receipt=state.execute(req);ref=receipt['ref']
    other=dict(id='WO-OTHER',asset='HYD-01',task='작업지시만',status='배정됨')   # 부품을 잡지 않은 오더는 그대로 둔다
    state._s['cmms']['work_orders'].append(other)
    state.reset_pm_counters()
    order=next(o for o in state._s['cmms']['work_orders'] if o['id']==ref)
    assert order['status']=='취소' and order['cancelled_at'] and order['reservations_released']
    assert other['status']=='배정됨'
    # 2026-10-23 점검 E2: B [초기화]는 그 오더가 잡은 수량만 되돌린다 — 이 시험 재고(씰 7 · 필터 5)는 수업 시작값이 아니므로 B 직전 값으로 돌아와야 한다
    assert {k:(v['on_hand'],v['reserved'],v['on_order']) for k,v in state._s['erp']['spare_stock'].items()}==start
    assert all(c['plan_wo'] is None for c in state._s['cmms']['pm_counters'].values())
    again=deepcopy(state._s['erp']['spare_stock']);state.reset_pm_counters()
    assert {k:(v['on_hand'],v['reserved']) for k,v in state._s['erp']['spare_stock'].items()}=={k:(v['on_hand'],v['reserved']) for k,v in again.items()}
