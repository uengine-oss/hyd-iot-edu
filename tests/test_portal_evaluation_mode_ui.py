"""Actual pure producers + Chromium: simulated ranks cannot imply approval readiness."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re

import pytest
from agentsvc import cards, whatif
from test_agent_trial import FakeWorld, agent, run
from test_whatif import bundle, mf, ent
from test_portal_remaining_ui import page, WWW, record_components
from test_portal_failure_states_ui import retain
from test_purchase_part_route import part_pipeline
from test_purchase_candidate_scope import pipeline
from test_purchase_supplier_policy import policy_skill, quotes
from procsvc import manual_preflight, manual_knowledge
from test_cards import R, T
from test_portal_approval_ui import browser, world, approval_clock, Portal
import test_portal_approval_ui
from test_portal_purchase_review_ui import preview, catalog, open_review


def source(name):
    root=Path(os.getenv('PORTAL_EVALUATION_UI_DIR',str(WWW)))
    return (root/name).read_text(encoding='utf8')


def components(page):
    # Historical negative rendering uses archived original scripts in memory only.
    record_components(page)
    page.add_script_tag(content=source('approvalCard.js'))
    card_source=re.search(r'^function signNum[\s\S]*?\n}\n(?=function reviewMatches)',source('enterprise.js'),re.M).group(0)
    page.add_script_tag(content=card_source+'\nwindow.hydCards={cardHtml,actionLabel};')
    compare=source('compare.js').replace('window.hydCompare = {','window.hydCompare = { sideCard,')
    page.add_script_tag(content=compare)
    page.add_script_tag(content=source('whatif.js'))


def evaluated(mode='rule_analysis'):
    b=bundle()
    return cards.evaluate(b['dmn'],b['skills'],b['facts'],b['forecasts'],b['tradeoffs'],b['precedents'],b['suppliers'],
                          b['forecast_contexts'],evaluation_mode=mode)


def render_approval(page,result):
    page.evaluate("d=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=modeApproval>'+hydApprove.html(d,d.recommended,{pending:true})+'</div><div id=modeCards>'+d.options.map(o=>hydCards.cardHtml(o,{rec:d.recommended,selectable:true,pending:true,decision:d})).join('')+'</div>';}",result)


def test_rule_analysis_real_rank_is_retained_but_approval_selection_is_unavailable(page):
    result=evaluated()
    assert result['evaluation_mode']=='rule_analysis' and result['execution_checked'] is False
    assert result['recommended'] and any(o['feasible'] for o in result['options'])
    before=deepcopy(result)
    components(page)
    render_approval(page,result)
    for target in ['#modeApproval','#modeCards']:
        text=page.locator(target).inner_text()
        assert '규칙 비교 · 모의 순위' in text and '실제 승인 · 실행 준비는 확인하지 않음' in text
        assert '승인하면 시스템이' not in text and '모의 1순위' in text
        assert all(r.is_disabled() for r in page.locator(target+' input[type=radio]').all())
        assert 'rule_analysis' not in text and 'execution_checked' not in text
        raw=page.locator(target+' details[data-evaluation-raw]').last
        raw.locator('summary').focus(); page.keyboard.press('Enter')
        assert json.loads(raw.locator('pre').inner_text())['execution_checked'] is False
        raw.locator('summary').focus(); page.keyboard.press('Enter')
    assert result==before
    retain(page,'rule-analysis-real-ranks-no-approval','#modeApproval','실제 cards.evaluate · 독립 고장 규칙 fixture · 모의 모드',['모의 1순위','실제 승인 · 실행 준비는 확인하지 않음'])


@pytest.mark.parametrize('metadata',[{}, {'evaluation_mode':'execution','execution_checked':False},
                                     {'evaluation_mode':'execution','execution_checked':'true'},
                                     {'evaluation_mode':'unknown','execution_checked':True}])
def test_missing_or_invalid_execution_metadata_never_claims_checked(page,metadata):
    result=evaluated('execution')
    for entry in [result,*result['options']]:
        entry.pop('evaluation_mode');entry.pop('execution_checked');entry.update(metadata)
    components(page);render_approval(page,result)
    assert '확인 안 됨' in page.locator('#modeApproval').inner_text()
    assert '승인하면 시스템이' not in page.locator('#modeApproval').inner_text()
    if metadata:assert all(r.is_disabled() for r in page.locator('#modeCards input[type=radio]').all())


def test_actual_execution_mode_keeps_normal_action_and_rank_ui(page):
    result=evaluated('execution')
    assert result['execution_checked'] is True
    components(page);render_approval(page,result)
    assert '승인하면 시스템이' in page.locator('#modeApproval').inner_text()
    assert page.locator('#modeCards input[type=radio]:not(:disabled)').count()>0
    assert page.locator('[data-evaluation-notice]').count()==0


def test_conflicting_option_and_parent_modes_preserve_both_sources_as_unknown(page):
    result=evaluated('execution')
    result.update(evaluation_mode='rule_analysis',execution_checked=False)
    components(page);render_approval(page,result)
    assert '확인 안 됨' in page.locator('#modeApproval').inner_text()
    assert all(r.is_disabled() for r in page.locator('#modeCards input[type=radio]').all())
    raw=page.locator('#modeApproval .ap-card > details[data-evaluation-raw]')
    raw.locator('summary').focus();page.keyboard.press('Enter')
    metadata=json.loads(raw.locator('pre').inner_text())
    assert metadata['execution_checked'] is True and metadata['parent']['execution_checked'] is False


def test_real_trial_and_whatif_producers_show_analysis_scope_in_actual_renderers(page,mf):
    trial,_=run(agent(),FakeWorld())
    view=whatif.evaluate(bundle(),mf)
    assert trial['execution_checked'] is False and view['execution_checked'] is False
    assert all(c['execution_checked'] is False for c in view['cards'])
    assert all(c['execution_checked'] is False for c in trial['ranking'])
    original=deepcopy((trial,view))
    components(page)
    page.evaluate("t=>{selectTab('compare');document.querySelector('#compareView').innerHTML=hydCompare.sideCard('A',{id:'independent-trial',result:t,status:t.status,setting:{name:'독립 시험 담당'},created_at:'2026-10-12T00:00:00Z'});}",trial)
    assert '규칙 비교 · 모의 순위' in page.locator('#compareView').inner_text()
    assert '실제 승인 · 실행 준비는 확인하지 않음' in page.locator('#compareView').inner_text()
    page.evaluate("v=>{selectTab('whatif');const w=hydWhatif._W;w.el=document.querySelector('#whatifView');w.base=w.view={...v,asset:'HYD-01',created:'2026-10-12T00:00:00Z',variables:[],policy:{components:[],penalties:[]},original:{unchanged:true},summary:'독립 원천 손익 비교'};hydWhatif._render();}",view)
    assert '규칙 비교 · 모의 순위' in page.locator('#whatifView').inner_text()
    assert '실제 승인 · 실행 준비는 확인하지 않음' in page.locator('#whatifView').inner_text()
    assert (trial,view)==original
    retain(page,'whatif-real-producer-analysis-scope','#whatifView','실제 whatif.evaluate · 독립 Enterprise HTTP TestClient 원천',['규칙 비교 · 모의 순위','실제 승인 · 실행 준비는 확인하지 않음'])


def test_real_purchase_request_candidate_shows_business_values_in_approval_head(page,part_pipeline):
    tools,*_=part_pipeline
    output=tools.evaluate_purchase('HYD-03','P-KIT')
    record=output.get('document',output)
    result=record['result']
    result={**result,'facts':record['facts'],'origin':record['origin']}
    assert any(a['code']=='PR_CREATE' for o in result['options'] for a in o['actions'])
    before=deepcopy(result)
    components(page);render_approval(page,result)
    head=page.locator('#modeApproval .ap-business')
    assert '구매 요청' in head.inner_text() and 'P-KIT' in head.inner_text()
    assert '수량' in head.inner_text() and '6' in head.inner_text() and '발주 금액' in head.inner_text()
    assert '승인 · 발주 완료 아님' in head.inner_text()
    assert result==before
    retain(page,'purchase-request-actual-producer-approval-head','#modeApproval','실제 purchase_part_route producer · 독립 부품 원천 fixture',['구매 요청','P-KIT','승인 · 발주 완료 아님'])


def test_dynamic_purchase_policies_show_exact_supplier_quote_and_excluded_other_options(page,part_pipeline,pipeline):
    tools,skills,facts,*_=part_pipeline
    pipeline[1].append(R('dec:compliance','rule:ui-avl','EXCLUDE',[T('supplier_avl','==',False)]))
    produced=[]
    for policy in ['oem','lowest_approved','fastest_quote']:
        skills['skill:purchase'].update(policy_skill(policy));facts['spare_quotes']=quotes()
        record=tools.evaluate_purchase('HYD-03','P-KIT')
        option=deepcopy(record['result']['options'][0])
        option['id']=option['id']+'-'+policy
        produced.append(option)
    assert [o['resolvedSupplier']['quote']['name'] for o in produced]==['B-OEM (순정)','A정밀 (대체)','C트레이딩']
    assert produced[2]['feasible'] is False
    result={**record['result'],'options':produced,'recommended':produced[0]['id'],'facts':record['facts'],'origin':record['origin']}
    before=deepcopy(result);components(page);render_approval(page,result)
    head=page.locator('#modeApproval .ap-business').first
    for text in ['정본 순정 견적','B-OEM (순정)','단가 20만원','납기 5일','등록 승인 공급사 검사 통과']:
        assert text in head.inner_text()
    other=page.locator('#modeApproval details').filter(has=page.locator('summary',has_text='다른 안')).first
    other.locator(':scope > summary').focus();page.keyboard.press('Enter')
    for text in ['승인된 비순정 최저가','A정밀 (대체)','전체 견적 최단 납기','C트레이딩','검사 미통과','제외']:
        assert text in other.inner_text()
    assert 'sup:' not in head.inner_text() and 'PR_CREATE' not in head.inner_text()
    raw=head.locator('details').filter(has=page.locator('summary',has_text='구매요청 근거 원문'))
    raw.locator('summary').focus();page.keyboard.press('Enter')
    assert json.loads(raw.locator('pre').inner_text())['resolvedSupplier']==produced[0]['resolvedSupplier']
    assert result==before
    retain(page,'purchase-dynamic-policies-and-real-exclusion','#modeApproval','실제 구매 producer 각 정책을 독립 계산한 안 나란히 · 실제 운영 구매 판단 아님',['B-OEM (순정)','A정밀 (대체)','C트레이딩'])


def test_purchase_preflight_structure_pass_is_not_actual_execution_readiness(page):
    record=preview({'purchase_comparison_policy':{'version':1,'loss_per_failure':250,'inspection_threshold':0.1,'inspection_cost':20,'anchor':{'source_id':'manual:review','quote':'불량 1건 손실은 250만 원. 불량률이 10 %를 넘으면 전수 검사 비용 20만 원을 더한다.'}},  # 2026-10-25: 실행 구매 판단은 총비용 비교 정책을 요구한다
                    'scope':'purchase','executable':True,'parts':['part:review-seal'],'kind':'work_order',
                    'failureMode':None,'relation':None,'approver':'role:purchasing',
                    'actions':[{'action':'action:purchase-request','value':'sup:review'}]})
    choices={key:[] for key in manual_knowledge.CATALOG_Q}
    choices.update(catalog())
    choices.update(actions=[{'id':'action:purchase-request','code':'PR_CREATE','kind':'transaction'}],
                   systems=[{'id':'sys:erp'}],suppliers=[{'id':'sup:review','name':'독립 시험 공급사'}])
    choices['parts'][0]['suppliers']=[{'supplier':'sup:review','name':'독립 시험 공급사','avl':True}]
    # 2026-10-23: 실행 구매 절차는 그 문서의 후보 규칙이 있어야 판단이 후보로 낸다(없으면 CANDIDATE_RULE_MISSING) — 원문 근거 후보 규칙을 둔다
    choices['decision_tables']=[{'id':'dt:action-candidates','decision':'dec:action-candidates','inputs':[{'id':'in:pattern','variable':'pattern'}]}]
    record['knowledge']={'rules':[{'id':'rule:review-candidates','section':'구매절','anchor':{'quote':'원문 공급 조건을 확인한다.'},
        'table':'dt:action-candidates','effect':'SELECT','tests':[{'input':'in:pattern','operator':'==','value':'SPARE_BELOW_MIN'}],'outputs':['SOP-REVIEW-01']}]}
    record['validation']=manual_preflight.validate(record,choices)
    assert record['validation']['execution'][0]['ready'] is True, record['validation']['issues']
    assert record['validation']['execution'][0]['evaluation_mode']=='structural'
    assert record['validation']['execution'][0]['execution_checked'] is False
    original=deepcopy(record);open_review(page,record,choices)
    text=page.locator('#manualResult').inner_text()
    assert '연결 구조 검사 통과' in text and '실제 견적 · 재고는 실행 판단 시 확인' in text
    assert '실제 실행 가능' not in text and '현재 실제 승인 · 실행 준비는 확인하지 않음' in text
    assert not page.locator('#manualReviewed').is_checked() and record==original
    retain(page,'purchase-preflight-structural-only','#manualResult','실제 manual_preflight.validate · 독립 원문/카탈로그 입력',['연결 구조 검사 통과','실제 견적 · 재고는 실행 판단 시 확인'])


@pytest.mark.parametrize('width',[1440,1024])
def test_actual_approval_panel_blocks_analysis_and_record_keeps_simulated_rank(browser,world,width,monkeypatch):
    result=evaluated()
    opened=test_portal_approval_ui.opened
    def analysis_case(world,did):
        record=opened(world,did)
        # Supply the independent stored snapshot before the product first reads it.
        # No historical snapshot or renderer cache is rewritten after rendering.
        record[3].update({key:deepcopy(result[key]) for key in ['options','recommended','evaluation_mode','execution_checked','execution_notice']})
        return record
    monkeypatch.setattr(test_portal_approval_ui,'opened',analysis_case)
    p=Portal(browser,world,'c3_cooling',width)
    try:
        assert p.page.locator('#tdGo').is_disabled()
        assert '규칙 비교 · 모의 순위' in p.page.locator('#todoPanel').inner_text()
        assert '실제 승인 · 실행 준비는 확인하지 않음' in p.page.locator('#todoPanel').inner_text()
        assert p.posts==[] and world['executed']==[] and p.inc.cmd_id is None
        p.capture('request')
        p.page.locator('[data-inst-tab="record"]').click()
        p.page.locator('#instRecord .cr-step').filter(has_text='모의 1순위').first.wait_for()
        text=p.page.locator('#instRecord').inner_text()
        assert '모의 1순위로 계산했습니다' in text and '실제 승인 · 실행 준비는 확인하지 않았습니다' in text
        assert p.d['options']==result['options'] and p.d['recommended']==result['recommended']
        assert p.posts==[] and world['executed']==[]
        retain(p.page,'analysis-actual-task-approval-and-record-'+str(width),'#instRecord','독립 FastAPI MemoryRepo 처리 건 · 실제 cards.evaluate 모의 결과 · 운영 승인/실행 아님',['모의 1순위','실제 승인 · 실행 준비는 확인하지 않았습니다'])
    finally:p.close()
