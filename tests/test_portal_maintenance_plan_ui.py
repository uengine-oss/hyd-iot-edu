"""Actual PM contract metadata rendered in native, source-preserving UI."""
from copy import deepcopy
import json
import pytest
from hydcommon.maintenance_plan import plan
from test_pm_reschedule_contract import skill, facts, window
from test_portal_remaining_ui import page, record_components, WWW
from test_portal_failure_states_ui import retain


@pytest.mark.parametrize('mode',['reschedule','create','excluded'])
def test_pm_plan_shows_existing_order_or_creation_and_all_exclusion_evidence(page,mode):
    record_components(page)
    page.add_script_tag(path=str(WWW/'approvalCard.js'))
    option={'id':'skill:pm-review','name':'원문 정기 정비 일정 검토','sopId':'SOP-PM-13','feasible':True,'rank':1,'score':0,'actions':[]}
    if mode=='reschedule': option['maintenancePlan']=plan(skill(),facts(),window())
    elif mode=='create':
        source=skill(); source['actions'][0]['code']='WO_CREATE'; source['maintenance_policy']['stock_effect']='reserve'
        option['maintenancePlan']=plan(source,facts(),window())
    else:
        option.update(feasible=False,violations=[{'rule':'rule:other','annotation':'기타 검사 제외'},
            {'rule':'execution:pm-plan','annotation':'기존 정기 정비 오더가 없어 일정 변경을 할 수 없습니다.'},
            {'rule':'execution:pm-plan','annotation':'다음 정비 시간의 허용 한도를 확인할 수 없습니다.'}])
    original=deepcopy(option)
    page.evaluate("o=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=pm-plan>'+hydWords.maintenanceHtml(o)+'</div>';}",option)
    expected='기존 정기 정비 오더 일정 변경' if mode=='reschedule' else '새 정기 정비 오더 생성 계획' if mode=='create' else '정비 실행 계획 불가 · 후보 제외'
    retain(page,'pm-plan-'+mode,'#pm-plan','실제 maintenance_plan 생성기 · 독립 Chromium 합성 조회, 운영 오더 생성/일정 변경 없음',[expected])
    if mode=='reschedule':
        assert 'WO-PM' in page.locator('#pm-plan').inner_text()
        assert '2,100 h' in page.locator('#pm-plan').inner_text()
        assert '2,200 h' in page.locator('#pm-plan').inner_text()
    if mode=='excluded':
        assert '기존 정기 정비 오더가 없어' in page.locator('#pm-plan').inner_text()
        assert '다음 정비 시간의 허용 한도' in page.locator('#pm-plan').inner_text()
        assert 'execution:pm-plan' not in page.locator('#pm-plan').inner_text()
    fold=page.locator('#pm-plan details').filter(has=page.locator('summary',has_text='정비 실행 계획 · 제외 근거 원문')); fold.locator(':scope > summary').focus(); page.keyboard.press('Enter')
    raw=json.loads(fold.locator('pre').inner_text())
    assert raw.get('maintenancePlan')==option.get('maintenancePlan')
    assert raw['violations']==[v for v in option.get('violations',[]) if v['rule']=='execution:pm-plan']
    assert page.evaluate('hydWords.maintenanceHtml({id:"skill:ordinary",actions:[],violations:[]})')==''
    assert option==original
    page.evaluate("o=>document.querySelector('#pm-plan').innerHTML=hydRecord.altHtml({options:[o],recommended:null,explanation:''})",option)
    assert expected in page.locator('#pm-plan').inner_text()
    if mode=='excluded':
        page.evaluate("o=>document.querySelector('#pm-plan').innerHTML=hydApprove.html({options:[{id:'skill:ok',name:'가능한 안',feasible:true,score:1,actions:[]},o],recommended:'skill:ok',explanation:''},'skill:ok',{pending:false})",option)
        fold=page.locator('#pm-plan > div details').first if page.locator('#pm-plan > div details').count() else page.locator('#pm-plan details').first
        fold.locator(':scope > summary').focus(); page.keyboard.press('Enter')
        assert expected in page.locator('#pm-plan').inner_text()
