"""Source purchase review in production Chromium, with isolated HTTP records."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pytest
from hydcommon.skill_scope import purchase_shape
from procsvc import manual_preflight, manual_knowledge

from test_portal_remaining_ui import page, WWW
from test_portal_failure_states_ui import retain


def catalog():
    return {'parts':[{'id':'part:review-seal','name':'검토용 씰 키트','partNo':'PART-REVIEW-01','suppliers':[]}],
            'roles':[{'id':'role:purchasing','name':'구매 담당','level':2}],
            'failure_modes':[{'id':'fm:review-pressure','name':'검토 압력 저하'}]}


def preview(link=None):
    return {'status':'READY','source_id':'review-source','document_id':'review-document','filename':'구매 원문.md','chars':60,
            'warnings':[],'sections':[{'ref':'구매절','title':'구매 확인','excerpt':'원문 공급 조건을 확인한다.'}],
            'procedures':[{'id':'SOP-REVIEW-01','name':'구매 조건 원문 확인','section':'구매절',
                           'steps':[{'order':1,'text':'원문 공급 조건을 확인한다.','manual':'구매절'}],
                           'link':link or {}}],
            'validation':{'checked':True,'technical_ready':True,'needs_human_review':True,'can_commit':False,'issues':[]}}


def open_review(page, record, choices=None, status=200):
    requests=[]
    page.route('**/api/kg/catalog',lambda r:r.fulfill(json={'roles':catalog()['roles'],'failureModes':catalog()['failure_modes']}))
    page.route('**/api/kg/manuals/catalog',lambda r:r.fulfill(status=status,json=choices if choices is not None else catalog()))
    page.route('**/api/kg/manuals/sources?*',lambda r:r.fulfill(json={'total':1,'limit':20,'next_offset':None,'items':[{'source_id':'review-source','filename':'구매 원문.md','status':'READY'}]}))
    page.route('**/api/kg/manuals/sources/review-source/preview',lambda r:r.fulfill(json=record))
    page.route('**/api/kg/manuals/sources/review-source/extractions?*',lambda r:r.fulfill(json={'items':[],'next_offset':None}))
    page.route('**/api/kg/manuals',lambda r:r.fulfill(json=[]))
    page.route('**/api/kg/ingests',lambda r:r.fulfill(json=[]))
    def commit(route):
        body = route.request.post_data_json
        for link in body['links'].values():
            if link.get('scope') == 'purchase':
                purchase_shape(link, source_backed=True)
        requests.append(body)
        route.fulfill(json={'sections':1,'procedures':1,'steps':1,'candidate_activation':{}})
    page.route('**/api/kg/manuals/commit',commit)
    # Negative audit can load an archived, unmodified product script in memory;
    # no checkout or operating portal file is replaced.
    page.add_script_tag(path=str(Path(os.getenv('PORTAL_PURCHASE_HITL_SOURCE',str(WWW/'hitl.js')))))
    page.evaluate("selectTab('knowledge')")
    page.locator('#manualSources > details > summary').click()
    page.locator('[data-manual-reopen="review-source"]').click()
    page.locator('#manualReviewed').wait_for()
    return requests


def check_review(page):
    page.locator('#manualReviewed').focus()
    page.keyboard.press('Space')
    assert page.locator('#manualReviewed').is_checked()


def test_revision_lists_removals_and_cancel_never_commits(page):
    record=preview({'scope':'purchase','executable':False,'parts':['part:review-seal'],
                    'kind':'work_order','actions':[]})
    record['previous_batch']='old-batch'
    record['sections'][0]['anchor']={'page':1,'quote':'원문 공급 조건을 확인한다.','located':'loose'}
    calls=open_review(page,record)
    page.route('**/api/kg/manuals/changes',lambda r:r.fulfill(json={'previous_batch':'old-batch',
        'removed':[{'id':'rule:lost','labels':['Rule'],'name':'안전 온도 제한'}]}))
    assert '대략 일치 — 문맥 확인 필요' in page.locator('#manualResult').inner_text()
    check_review(page); page.locator('#manualCommit').click()
    dialog=page.locator('.confirm-dialog[open]')
    dialog.wait_for()
    assert '판단 규칙: 안전 온도 제한' in dialog.inner_text() and calls==[]
    dialog.locator('button[value="cancel"]').click()
    assert calls==[]
    page.locator('#manualCommit').click()
    dialog.wait_for(); dialog.locator('button[value="ok"]').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.includes('적재 완료')")
    assert len(calls)==1


def test_purchase_reference_keeps_source_and_explicit_fields_without_fault_or_execution(page):
    link={'scope':'purchase','executable':False,'parts':['part:review-seal'],'failureMode':None,'relation':None,
          'kind':'work_order','approver':None,'actions':[],'affects':[{'target':'msr:maint-cost','sign':'+'}]}
    record=preview(link)
    record['validation'].update(executable_ready=False,execution=[{'sop':'SOP-REVIEW-01','executable':False,'ready':False,'issues':[]}])
    original=deepcopy(record)
    requests=open_review(page,record)
    text=page.locator('#manualResult').inner_text()
    # 2026-10-23 갱신: 공개 용어 정리로 범위 선택지가 'ERP 업무 범위'→'구매 업무 범위'(hitl.js '구매 원문 절차 · 구매 업무 범위')
    assert '구매 업무 범위' in text and '실행 후보 제외' in text and '구매 담당' in text
    assert '검토용 씰 키트' in text and 'part:review-seal' not in text
    assert not page.locator('#manualReviewed').is_checked()
    assert page.get_by_label('원문 절차의 사용 방식').input_value()=='false'
    assert page.get_by_label('구매 대상 부품').is_enabled()
    assert page.locator('[data-affects]').input_value()=='msr:maint-cost:+'
    page.locator('#manualCommit').click()
    assert requests==[] and '원문을 대조하고 검토 완료를 표시하세요' in page.locator('#manualMsg').inner_text()
    page.locator('#manualResult').evaluate("e=>{const m=document.querySelector('main');m.scrollTop+=e.getBoundingClientRect().top-m.getBoundingClientRect().top-16;}")
    retain(page,'purchase-reference-review','#manualResult','Independent source-backed purchase/reference record; real GET catalogs and native review controls. No live commit, supplier fabrication, or ERP action.',
           ['구매 업무 범위','실행 후보 제외','검토용 씰 키트'])  # 2026-10-23 갱신: 공개 용어 정리로 범위 선택지가 'ERP 업무 범위'→'구매 업무 범위'(hitl.js '구매 원문 절차 · 구매 업무 범위')
    retain(page,'purchase-reference-fields','[data-purchase-fields]','Actual native scope/parts/use/role controls from an independent source review; source canonical values unchanged and human checkbox remains unchecked.',
           ['원문 절차의 사용 방식','구매 대상 부품','구매 승인 담당 역할'])
    check_review(page)
    page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.startsWith('적재 완료')")
    assert len(requests)==1
    sent=requests[0]
    assert sent['reviewed'] is True and sent['links']['SOP-REVIEW-01']==link
    assert sent['procedures']==record['procedures'] and sent['sections']==record['sections']
    assert record==original


def test_purchase_use_is_never_inferred_and_legacy_fault_still_requires_fm(page):
    requests=open_review(page,preview())
    check_review(page)
    page.locator('#manualCommit').click()
    assert '고장 유형을 고르세요' in page.locator('#manualMsg').inner_text() and requests==[]
    assert '일반 원문 참고 절차' in page.locator('#manualMsg').inner_text()   # 2026-10-25: 고장 조치가 아니면 무엇을 할지
    page.locator('[data-manual-scope]').select_option('purchase')
    assert not page.locator('#manualReviewed').is_checked()
    assert page.locator('[data-manual-executable]').input_value()==''
    check_review(page)
    page.locator('#manualCommit').click()
    assert '명시적으로 선택하세요' in page.locator('#manualMsg').inner_text() and requests==[]
    page.locator('[data-manual-executable]').select_option('false')
    assert not page.locator('#manualReviewed').is_checked()
    check_review(page)
    page.locator('#manualCommit').click()
    assert '구매 대상 부품을 선택하세요' in page.locator('#manualMsg').inner_text() and requests==[]
    page.locator('[data-manual-parts]').select_option(['part:review-seal'])
    page.locator('[data-rel]').select_option('')
    assert not page.locator('#manualReviewed').is_checked()
    assert '원래 제안 기준' in page.locator('#manualReviewChanged').inner_text()
    check_review(page)
    page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.startsWith('적재 완료')")
    assert requests[0]['links']['SOP-REVIEW-01']['scope']=='purchase'
    assert requests[0]['links']['SOP-REVIEW-01']['executable'] is False
    assert requests[0]['links']['SOP-REVIEW-01']['failureMode'] is None


def test_purchase_execution_requires_real_role_and_preserves_existing_pr_action(page):
    link={'scope':'purchase','executable':True,'parts':['part:review-seal'],'failureMode':None,'relation':None,
          'kind':'work_order','actions':[{'action':'action:purchase-request','value':'sup:registered'}]}
    record=preview(link)
    requests=open_review(page,record)
    check_review(page)
    page.locator('#manualCommit').click()
    assert '구매 승인 담당 역할을 선택하세요' in page.locator('#manualMsg').inner_text() and requests==[]
    page.get_by_label('구매 승인 담당 역할').select_option('role:purchasing')
    assert not page.locator('#manualReviewed').is_checked()
    check_review(page)
    page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.startsWith('적재 완료')")
    sent=requests[0]['links']['SOP-REVIEW-01']
    assert sent['executable'] is True and sent['approver']=='role:purchasing'
    assert sent['actions']==link['actions'] and sent['parts']==link['parts']
    assert sent['failureMode'] is None and sent['relation'] is None


@pytest.mark.parametrize('status,choices,expected',[(503,{'detail':'구매 지식을 읽지 못했습니다'},'구매 지식을 읽지 못했습니다'),(200,{'parts':None,'roles':[]},'응답 형식')])
def test_purchase_catalog_failure_is_explicit_and_does_not_commit(page,status,choices,expected):
    record=preview({'scope':'purchase','executable':False,'parts':['part:review-seal'],'failureMode':None,'relation':None})
    requests=open_review(page,record,choices,status)
    assert expected in page.locator('#manualResult').inner_text()
    assert page.locator('[data-manual-parts]').is_disabled()
    check_review(page)
    page.locator('#manualCommit').click()
    assert expected in page.locator('#manualMsg').inner_text() and requests==[]


def test_top_link_empty_override_does_not_reuse_inline_purchase_metadata(page):
    record=preview({'scope':'purchase','executable':True,'parts':['part:review-seal'],'failureMode':None,'relation':None})
    record['links']={'SOP-REVIEW-01':{}}
    requests=open_review(page,record)
    assert page.locator('[data-manual-scope]').input_value()=='fault'
    assert page.locator('[data-manual-executable]').input_value()==''
    check_review(page)
    page.locator('#manualCommit').click()
    assert '고장 유형을 고르세요' in page.locator('#manualMsg').inner_text() and requests==[]
    raw=page.locator('#manualResult details').filter(has=page.locator('summary',has_text='절차 연결 원문'))
    raw.locator(':scope > summary').focus()
    page.keyboard.press('Enter')
    saved=json.loads(raw.locator('pre').inner_text())
    assert saved['inline']==record['procedures'][0]['link'] and saved['override']=={}


@pytest.mark.parametrize('related', [True,False])
def test_purchase_execution_displays_real_preflight_relationship_result_without_claiming_approval(page,related):
    choices={key:[] for key in manual_knowledge.CATALOG_Q}
    choices.update(catalog())
    choices['parts'][0]['suppliers']=[{'supplier':'sup:registered','name':'등록 공급사','avl':True}] if related else []
    choices['suppliers']=[{'id':'sup:registered','name':'등록 공급사','avl':True}]
    choices['systems']=[{'id':'sys:erp','name':'구매 업무 시스템'}]
    choices['actions']=[{'id':'action:purchase-request','name':'구매 요청','code':'PR_CREATE','kind':'transaction','min':None,'max':None}]
    record=preview({'purchase_comparison_policy':{'version':1,'loss_per_failure':250,'inspection_threshold':0.1,'inspection_cost':20,'anchor':{'source_id':'manual:review','quote':'불량 1건 손실은 250만 원. 불량률이 10 %를 넘으면 전수 검사 비용 20만 원을 더한다.'}},  # 2026-10-25: 실행 구매 판단은 총비용 비교 정책을 요구한다
                    'scope':'purchase','executable':True,'parts':['part:review-seal'],'approver':'role:purchasing',
                    'failureMode':None,'relation':None,'kind':'work_order','actions':[{'action':'action:purchase-request','value':'sup:registered'}]})
    # 2026-10-23 갱신: 적재 전 검사에 CANDIDATE_RULE_MISSING(manual_preflight.py)이 들어와, 실행 구매 절차는 그 문서의 후보 규칙이 있어야 준비됨 — 원문 근거 후보 규칙을 둔다
    choices['decision_tables']=[{'id':'dt:action-candidates','decision':'dec:action-candidates','inputs':[{'id':'in:pattern','variable':'pattern'}]}]
    record['knowledge']={'rules':[{'id':'rule:review-candidates','section':'구매절','anchor':{'quote':'원문 공급 조건을 확인한다.'},
        'table':'dt:action-candidates','effect':'SELECT','tests':[{'input':'in:pattern','operator':'==','value':'SPARE_BELOW_MIN'}],'outputs':['SOP-REVIEW-01']}]}
    record['validation']=manual_preflight.validate(record,choices)
    expected='실행 후보 기계 검사 통과' if related else '실행 후보 연결 확인 필요'
    assert record['validation']['execution'][0]['ready'] is related, record['validation']['issues']
    open_review(page,record,choices)
    text=page.locator('#manualResult').inner_text()
    # 2026-10-23 갱신: 공개 용어 정리로 'ERP 실행 완료'→'구매 실행 완료'(hitl.js 실행 후보 구조 검사 안내)
    assert expected in text and '실제 구매 승인이나 구매 실행 완료를 뜻하지 않습니다' in text
    assert not page.locator('#manualReviewed').is_checked()
    if not related:
        assert '등록 공급사' in text and '검토용 씰 키트' in text
        assert 'sup:registered' not in text and 'part:review-seal' not in text
        assert 'PURCHASE_SUPPLIER_PART_MISMATCH' not in text
        folds=page.locator('#manualResult details').filter(has=page.locator('summary',has_text='검사 항목 원문'))
        for fold in folds.all():
            fold.locator(':scope > summary').focus()
            page.keyboard.press('Enter')
        assert 'PURCHASE_SUPPLIER_PART_MISMATCH' in page.locator('#manualResult').inner_text()
    retain(page,'purchase-execution-'+('ready' if related else 'mismatch'),'#manualResult',
           'Actual backend read-only preflight and production Chromium over an independent catalog fixture, with and without the Supplier/Part relationship. No actual approval or ERP transaction.',[expected])


@pytest.mark.parametrize('policy',['oem','lowest_approved','fastest_quote'])
def test_explicit_supplier_policy_keeps_source_fixed_value_and_sends_unresolved_action(page,policy):
    link={'scope':'purchase','executable':True,'parts':['part:review-seal'],'failureMode':None,'relation':None,
          'kind':'work_order','approver':'role:purchasing','actions':[{'action':'action:purchase-request','value':'sup:registered'}]}
    record=preview(link)
    original=deepcopy(record)
    choices=catalog()
    choices['suppliers']=[{'id':'sup:registered','name':'원문 지정 공급사'}]
    requests=open_review(page,record,choices)
    assert page.get_by_label('원문 공급사 선정 기준').input_value()==''
    assert '원문 고정 공급사: 원문 지정 공급사' in page.locator('#manualResult').inner_text()
    check_review(page)
    page.get_by_label('원문 공급사 선정 기준').select_option(policy)
    assert not page.locator('#manualReviewed').is_checked()
    assert '고정 공급사 값을 함께 보내지 않으며' in page.locator('[data-supplier-review]').inner_text()
    check_review(page)
    page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.startsWith('적재 완료')")
    selected=requests[0]['links']['SOP-REVIEW-01']
    assert selected['supplier_policy']==policy
    assert selected['actions']==[{'action':'action:purchase-request','value':None}]
    assert requests[0]['procedures'][0]['link']['actions'][0]['value']=='sup:registered'
    assert record==original


def test_unknown_fixed_supplier_is_not_guessed_and_reference_rejects_policy(page):
    record=preview({'scope':'purchase','executable':True,'parts':['part:review-seal'],'failureMode':None,'relation':None,
                    'approver':'role:purchasing','actions':[{'action':'action:purchase-request','value':None}]})
    requests=open_review(page,record)
    assert '원문 고정 공급사 값 미상' in page.locator('#manualResult').inner_text()
    assert page.get_by_label('원문 공급사 선정 기준').input_value()==''
    page.get_by_label('원문 절차의 사용 방식').select_option('false')
    page.get_by_label('원문 공급사 선정 기준').select_option('oem')
    check_review(page)
    page.locator('#manualCommit').click()
    assert '정책 선택을 해제하세요' in page.locator('#manualMsg').inner_text() and requests==[]
    page.get_by_label('원문 공급사 선정 기준').select_option('')
    check_review(page)
    page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.startsWith('적재 완료')")
    selected=requests[0]['links']['SOP-REVIEW-01']
    assert selected['actions']==[] and 'supplier_policy' not in selected
