"""Real PM policy/plan producers and Chromium; isolated, declared domain fixtures."""
from copy import deepcopy
import json
import os
import pytest
from hydcommon.maintenance_policy import policy, scope, ScopeError
from hydcommon.maintenance_plan import plan
from entsim import data
from entsim.state import EnterpriseState
from test_portal_remaining_ui import page, record_components, WWW
from test_portal_failure_states_ui import retain
from test_portal_failure_states_ui import render_record, open_record_folds


def pm_fixture(scope='single', *, unmapped=False,tolerance=5):
    anchor={'source_id':'source:pm-fixture','quote':f'독립 시험 원문: 기본 정비 간격 2,000시간과 허용 오차 {tolerance}%.'}
    # These extra Part rows are explicitly isolated test inputs, never seeded
    # into the real ERP whose filter/oil mapping is currently absent.
    base=[{'part_no':'P-PMP-SEAL','name':'펌프 축 씰 키트','qty':1},
          {'part_no':'P-UI-RETURN-FILTER','name':'리턴 필터 엘리먼트','qty':1}]
    if unmapped: base[1].update(part_no=None,qty=None,mapping_reason='실제 부품 연결과 원문 수량 미상')
    packages=[{'interval_h':h,'sop':'SOP-PM-'+sop,'name':f'{h:,}시간 정비 묶음',
               'parts':deepcopy(base)} for h,sop in [(2000,'21'),(4000,'22'),(8000,'23')]]
    packages[2]['parts'].append({'part_no':'P-UI-OIL','name':'작동유','qty':1})
    contract=policy({'version':1,'scope':scope,'stock_effect':'reserve','interval_h':2000,'tolerance_pct':tolerance,'model_assets':['HYD-02','HYD-03'],
                     'anchor':anchor,'model_anchor':{'source_id':'source:pm-fixture','quote':'독립 시험 원문: 같은 기종 HYD-02 · HYD-03'},'packages':packages})
    start='2026-10-12T12:00:00Z'
    rows=[{'asset':asset,'pm_interval_h':2000,'pm_tolerance_pct':tolerance,'pm_since_h':1950,'pm_total_h':total,
           'cycle':1,'service_position':None,'bundle_peer':'HYD-03' if asset=='HYD-02' else 'HYD-02',
           'hours_at_next_window':1959,'night_window_id':'MW-'+asset,'night_window_at':start,'pm_crew_available':2}
          for asset,total in [('HYD-02',11950),('HYD-03',9950)]]
    context={'asset':'HYD-02','records':rows,'parts':[{'part_no':no,'name':name,'available':2} for no,name in
             [('P-PMP-SEAL','펌프 축 씰 키트'),('P-UI-RETURN-FILTER','리턴 필터 엘리먼트'),('P-UI-OIL','작동유')]]}
    skill={'id':'skill:source-pm-fixture','sopId':'SOP-PM-14' if scope=='bundle' else 'SOP-PM-11','source_id':'source:pm-fixture',
           'maintenance_policy':contract,'actions':[{'code':'WO_CREATE','kind':'transaction','target':'sys:cmms','value':'정기 정비'}]}
    window={'id':'MW-HYD-02','basis':'hours_at_next_window','starts_at':start}
    return skill,{'pm_context':context},window


def components(page):
    record_components(page)
    archived=os.getenv('PORTAL_PM_WORDS_SOURCE')
    if archived: page.add_script_tag(path=archived)
    page.add_script_tag(path=str(WWW/'approvalCard.js'))


def render(page,option):
    page.evaluate("o=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=pm-package>'+hydWords.maintenanceHtml(o)+'</div>';}",option)


def test_current_milestone_package_and_both_assets_are_readable_without_calculation(page):
    components(page)
    skill,facts,window=pm_fixture('bundle')
    original=deepcopy((skill,facts,window))
    produced=plan(skill,facts,window)
    assert produced['assets'][0]['service']['package_interval_h']==4000
    assert produced['assets'][0]['service']['next_due_total_h']==12000
    option={'id':skill['id'],'name':'동시 정비 원문 계획','feasible':True,'score':0,'actions':[],
            'maintenancePlan':produced,'violations':[]}
    render(page,option)
    text=page.locator('#pm-package').inner_text()
    for expected in ['두 설비 동시 정비 계획','HYD-02','HYD-03','4,000시간 정비 묶음','12,000시간','10,000시간',
                     '동종 설비 범위 확인됨','하한 1,900시간','하한 충족 확인됨','공통 정비 시간 확인됨',
                     '총 필요 2개','실제 가용 2개','필요 4명','가용 2명','부족 2명','인력 확보 필요']:
        assert expected in text
    for internal in ['source:pm-fixture','WO_CREATE','scope','source_model_member','expected_counter']:
        assert internal not in text
    assert '확보 완료로 확인되지 않았습니다.' in text
    retain(page,'pm-bundle-package-and-milestones','#pm-package','실제 PM plan 생산기와 독립 원문 정책/재고/계수기 fixture · 운영 재고/오더/인력 확보 변경 없음',
           ['12,000시간','4,000시간','HYD-02','HYD-03','인력 확보 필요'])
    for asset in ('HYD-02','HYD-03'):
        selector=f'#pm-package [data-pm-asset="{asset}"]'
        page.locator(selector).scroll_into_view_if_needed()
        retain(page,'pm-bundle-asset-'+asset,selector,'실제 plan 생산기 · 독립 fixture의 설비별 검사, 운영 실행 완료 아님',[asset,'누적 기준','공통 정비 시간 확인됨'])
    fold=page.locator('#pm-package details').filter(has=page.locator('summary',has_text='정비 실행 계획 · 제외 근거 원문'))
    fold.locator(':scope > summary').focus(); page.keyboard.press('Enter')
    assert json.loads(fold.locator('pre').inner_text())['maintenancePlan']==produced
    assert (skill,facts,window)==original
    page.evaluate("o=>document.querySelector('#pm-package').innerHTML=hydApprove.html({options:[o],recommended:o.id,explanation:''},o.id,{pending:false})",option)
    assert '12,000시간' in page.locator('#pm-package').inner_text()
    assert '인력 확보 필요' in page.locator('#pm-package').inner_text()
    page.evaluate("o=>document.querySelector('#pm-package').innerHTML=hydRecord.altHtml({options:[o],recommended:o.id,explanation:''})",option)
    assert 'HYD-03' in page.locator('#pm-package').inner_text()


def test_infeasible_package_keeps_actual_partial_diagnostics_and_all_failures(page):
    components(page)
    skill,facts,window=pm_fixture(unmapped=True)
    with pytest.raises(ScopeError) as failure: plan(skill,facts,window)
    diagnostics=failure.value.diagnostics
    assert diagnostics['ready'] is False
    option={'id':skill['id'],'name':'정비 원문 검사','feasible':False,'actions':[],
            'maintenanceDiagnostics':diagnostics,'violations':[{'rule':'execution:pm-plan','annotation':str(failure.value)}]}
    render(page,option)
    text=page.locator('#pm-package').inner_text()
    for phrase in ['후보 제외','4,000시간 정비 묶음','12,000시간','리턴 필터','부품 근거 확인 안 됨','실제 수량·가용 재고를 확인할 수 없습니다']:
        assert phrase in text
    assert '정비 완료' not in text
    retain(page,'pm-infeasible-retains-4000-and-12000','#pm-package','실제 PM ScopeError의 부분 진단 · 독립 미연결 필터 fixture, 운영 실행 성공이 아님',
           ['후보 제외','4,000시간','12,000시간','리턴 필터'])
    fold=page.locator('#pm-package details').filter(has=page.locator('summary',has_text='정비 실행 계획 · 제외 근거 원문'))
    fold.locator(':scope > summary').focus(); page.keyboard.press('Enter')
    raw=json.loads(fold.locator('pre').inner_text())
    assert raw['maintenanceDiagnostics']==diagnostics
    assert raw['violations']==option['violations']
    assert 'maintenancePlan' not in raw


def test_unknown_or_negative_peer_observations_do_not_become_confirmed_conditions(page):
    components(page)
    skill,facts,window=pm_fixture('bundle')
    produced=plan(skill,facts,window)
    peer=produced['assets'][1]['applicability']
    peer.update(source_model_member=False,lower_hours_met=False,observed_hours=1880,within_limit=False,common_window_verified=False)
    produced['staffing']['confirmed']=None
    render(page,{'maintenanceDiagnostics':{**produced,'ready':False},'violations':[{'rule':'execution:pm-plan','annotation':'상대 설비가 운전시간 하한 미달이며 공통 정비 시간을 확인하지 못했습니다.'}]})
    text=page.locator('#pm-package').inner_text()
    assert '실제 1,880시간 · 하한 미달' in text
    assert '상한 초과' in text
    assert '공통 정비 시간 불일치' in text
    assert '원문 동종 설비 범위 불일치' in text
    assert '확보 완료로 확인되지 않았습니다.' in text
    peer.pop('source_model_member'); peer.pop('common_window_verified')
    render(page,{'maintenanceDiagnostics':{**produced,'ready':False},'violations':[]})
    unknown=page.locator('#pm-package').inner_text()
    assert '공통 정비 시간 확인 기록 없음' in unknown
    assert '원문 동종 설비 범위 확인 기록 없음' in unknown


def test_actual_memory_two_order_receipt_and_group_cancellation_stay_distinct_from_service_completion(page,monkeypatch):
    components(page)
    monkeypatch.setattr(data,'_now',lambda:data._SCENARIO_START)
    memory=EnterpriseState()
    memory._s['cmms']['pm_counters']['HYD-03'].update(since_pm_h=1950,total_h=9950)
    for no in ('P-PMP-SEAL','P-UI-RETURN-FILTER','P-UI-OIL'):
        memory._s['erp']['spare_stock'][no]={'part_no':no,'on_hand':4,'reserved':0,'on_order':0,'reorder_point':0,'target_stock':4,'below_since':None}
    skill,_,_=pm_fixture('bundle',tolerance=data.PM_SETTINGS['tolerance_pct'])
    rows=memory.pm_status()['records']; row=next(r for r in rows if r['asset']=='HYD-02')
    window={'id':row['night_window_id'],'basis':'hours_at_next_window','starts_at':row['night_window_at']}
    produced=plan(skill,{'pm_context':{'asset':'HYD-02','records':rows,'parts':memory.spare_stock()['records']}},window)
    receipt=memory.execute({'decision':'UI-PM-DECISION','option':skill['id'],'by':'독립 시험 승인자','asset':'HYD-02',
                           'skill':'skill:schedule-maintenance-scoped','params':{'plan':produced}})
    assert len(receipt['after']['orders'])==2
    assert {r['asset'] for r in receipt['after']['orders']}=={'HYD-02','HYD-03'}
    assert all(r['status']=='배정됨' for r in receipt['after']['orders'])
    page.evaluate("r=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=pm-package>'+hydWords.maintenanceReceiptHtml(r)+'</div>';}",receipt)
    text=page.locator('#pm-package').inner_text()
    assert '대상 2대의 오더 영수증' in text
    assert '영수증에 기록된 부품 처리 방식: 예약 · 실물 출고와 별도' in text
    assert '12,000시간' in text and '4,000시간' in text
    for r in receipt['after']['orders']: assert r['ref'] in text
    assert '정비를 했고' not in text
    retain(page,'pm-two-actual-memory-order-receipts','#pm-package','실제 EnterpriseState.execute의 독립 메모리 two-order 영수증 · 시험 재고만 명시 공급, 운영 재고/오더/정비 완료 아님',
           ['대상 2대','HYD-02','HYD-03','12,000시간','배정됨'])
    page.locator('#pm-package [data-pm-orders]').scroll_into_view_if_needed()
    retain(page,'pm-two-order-receipt-details','#pm-package [data-pm-orders]','동일 독립 메모리 실제 생성 영수증 · 두 실제 번호와 배정 상태, 운영 쓰기 없음',['HYD-02','HYD-03','배정됨','12,000시간'])
    fold=page.locator('#pm-package details').filter(has=page.locator('summary',has_text='정비 오더 영수증 원문'))
    fold.locator(':scope > summary').focus(); page.keyboard.press('Enter')
    assert json.loads(fold.locator('pre').inner_text())==receipt
    view={'instance':{'proc_inst_id':'UI-PM-CASE','status':'COMPLETED','variables_data':[]},
          'definition':{'activities':[{'id':'wo','name':'두 설비 정비 오더 등록'}]},
          'workitems':[{'id':'wwo','activity_id':'wo','activity_name':'두 설비 정비 오더 등록','agent_orch':'system','tool':'enterprise:WO_CREATE',
                        'status':'DONE','output':{'work_order':receipt}}],'events':[]}
    render_record(page,view); open_record_folds(page)
    assert '대상 2대의 오더 영수증' in page.locator('#instRecord').inner_text()
    assert all(r['ref'] in page.locator('#instRecord').inner_text() for r in receipt['after']['orders'])
    advanced=memory._s['cmms']['work_orders'][0]; original_status=advanced['status']; advanced['status']='완료'
    cancel_request={'decision':'UI-PM-CANCEL','option':skill['id'],'by':'독립 시험 승인자','asset':'HYD-02',
                    'skill':'skill:cancel-maintenance-scoped','compensates':receipt['id'],'params':{'ref':receipt['ref']}}
    with pytest.raises(ValueError,match='whole') as rejected: memory.execute(cancel_request)
    assert next(o for o in memory._s['cmms']['work_orders'] if o['id']==advanced['id'])['status']=='완료'
    failed=deepcopy(view); work=failed['workitems'][0]
    work.update(activity_name='전체 정비 오더 취소 검토',tool='mcp:call',status='PENDING',output={},log='ValueError: '+str(rejected.value))
    render_record(page,failed)
    text=page.locator('#instRecord').inner_text()
    assert '전체 취소를 다시 검토해야 합니다.' in text
    assert 'INVALID:' not in text and 'whole cancellation' not in text
    retain(page,'pm-group-cancel-actual-rejection','#instRecord','실제 독립 메모리 CMMS의 한 오더 상태 변경 거절 · pending 화면 · 운영 취소/신원 변경 없음',['전체 취소를 다시 검토해야 합니다.'])
    open_record_folds(page)
    original_error=page.locator('#instRecord details').filter(has=page.locator('summary',has_text='정비 실행 오류 원문'))
    assert original_error.locator('pre').inner_text()==work['log']
    next(o for o in memory._s['cmms']['work_orders'] if o['id']==advanced['id'])['status']=original_status
    cancelled=memory.execute({'decision':'UI-PM-CANCEL','option':skill['id'],'by':'독립 시험 승인자','asset':'HYD-02',
                              'skill':'skill:cancel-maintenance-scoped','compensates':receipt['id'],'params':{'ref':receipt['ref']}})
    assert len(cancelled['after']['orders'])==2
    assert all(r['status']=='취소' for r in cancelled['after']['orders'])
    page.evaluate("r=>document.querySelector('#instDetail').innerHTML='<div id=pm-package>'+hydWords.maintenanceReceiptHtml(r)+'</div>'",cancelled)
    retain(page,'pm-two-order-group-cancellation','#pm-package','동일 독립 메모리 transaction의 실제 group cancellation · 운영 취소 아님',['대상 2대의 정비 오더 취소 상태','HYD-02','HYD-03','취소'])
    page.locator('#pm-package [data-pm-orders]').scroll_into_view_if_needed()
    retain(page,'pm-two-order-cancel-details','#pm-package [data-pm-orders]','동일 독립 메모리 실제 전체 취소 영수증 · 운영 취소 없음',['HYD-02','HYD-03','취소'])


def test_incomplete_bundle_receipt_or_plan_only_does_not_claim_two_orders_registered(page):
    components(page)
    skill,facts,window=pm_fixture('bundle')
    produced=plan(skill,facts,window)
    for orders in ([],[{'asset':'HYD-02','ref':'WO-ONLY-ONE','status':'배정됨'}]):
        receipt={'after':{'plan':produced,'orders':orders}}
        page.evaluate("r=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=pm-package>'+hydWords.maintenanceReceiptHtml(r)+'</div>';}",receipt)
        summary=page.evaluate('r=>hydWords.maintenanceReceiptSummary(r)',receipt)
        assert '대상 2대의 오더 영수증이 기록되었습니다' not in summary
        assert '판단하지 않습니다' in summary


def test_stored_base_package_is_labeled_as_configuration_not_selected_milestone(page):
    components(page)
    stored={'package':'2,000시간 등록 설정','configured_base_package':'2,000시간 등록 설정','package_semantics':'base_interval_configuration'}
    assert page.evaluate('x=>hydWords.fieldName("package",x)',stored)=='등록된 기본 정비 내용'
    assert page.evaluate('hydWords.fieldName("package")')=='정비 묶음'
    output=page.evaluate('x=>hydWords.got("mcp__enterprise-maint__pm_status",JSON.stringify({facts:x}))',stored)
    assert '등록된 기본 정비 내용' in output
    assert '이번 차례 패키지 선택 아님' in output
    assert 'base_interval_configuration' not in output
    source=(WWW/'taskDetail.js').read_text(encoding='utf8').replace('window.hydTaskDetail = {','window.hydTaskDetail = { valueHtml,')
    page.add_script_tag(content=source)
    for value in (stored,[stored]):
        page.evaluate("x=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=pm-package>'+hydTaskDetail.valueHtml('pm_read',x,{})+'</div>';}",value)
        text=page.locator('#pm-package').inner_text()
        assert '등록된 기본 정비 내용' in text
        assert '이번 차례 패키지 선택 아님' in text
        assert 'package_semantics' not in text and 'base_interval_configuration' not in text


@pytest.mark.parametrize('effect',['issue','preserve'])
def test_physical_stock_or_owned_allocation_is_not_reclassified_as_new_reservation(page,effect):
    components(page)
    skill,facts,window=pm_fixture()
    contract=deepcopy(skill['maintenance_policy']); contract['stock_effect']=effect
    context=facts['pm_context']
    for part in context['parts']: part.update(on_hand=2,reserved=0)
    context['records'][0]['existing_pm_order']={'id':'WO-EXISTING','reserved_parts':[{'part_no':'P-PMP-SEAL','qty':1},{'part_no':'P-UI-RETURN-FILTER','qty':1}]}
    derived=scope(contract,context,'HYD-02',window)
    page.evaluate("p=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=pm-package>'+hydWords.maintenanceScopeHtml(p)+'</div>';}",derived)
    text=page.locator('#pm-package').inner_text()
    if effect=='issue':
        assert '부품 실물 출고 계획' in text
        assert '현재고 2개 · 이미 예약한 수량 0개' in text
        assert '입고 예정과 실물 출고 가능 여부를 구분합니다.' in text
    else:
        assert '기존 오더 부품 할당 보존' in text
        assert '기존 오더의 확인된 할당 1개' in text
        assert '새 부품을 자동 할당하지 않습니다.' in text
        assert all(p['owned_qty']==1 for p in derived['assets'][0]['parts'])
    assert '부품 예약 계획' not in text
