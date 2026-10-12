"""Production review DOM with isolated HTTP and the real source/reference guards."""
from copy import deepcopy
import json
import pytest
import os
from pathlib import Path
from urllib.parse import quote
from procsvc import manual_review, manual_graph, manual_references
from test_manual_references import archive, source_body, target, SID
from test_portal_remaining_ui import page
from test_portal_purchase_review_ui import open_review, catalog, check_review
from test_portal_failure_states_ui import retain


def review_screen(page, archive, *, pin=None, changed=False, override=None):
    source, record=source_body(archive)
    record.pop('reviewed'); record.pop('by')
    record['validation']={'checked':True,'technical_ready':True,'needs_human_review':True,'can_commit':False,'issues':[]}
    contract=target()
    if pin is not None:
        record['procedures'][0].update(existing_skill_id=SID,reference_contract_sha256=pin)
    contract['sections']=[{'id':'section:registered','ref':'HM-8.1','title':'등록된 팬 기준','excerpt':'진동 VS1 1.2 mm/s 기준이다.'}]
    if changed:
        contract['steps'][1]['text']='벨트를 1.2 mm/s 기준으로 확인한다.'
    if override is not None:
        record['procedures'][0]['link']={'kind':'reference','executable':False}
        record['links'][record['procedures'][0]['id']]=override
    choices=catalog()
    choices['skills']=[{'id':SID,'name':'등록 팬 점검','reference_contract':contract}]
    source_path=quote(source['source_id'],safe='')
    page.route('**/sources/'+source_path+'/extractions?*',lambda r:r.fulfill(json={'items':[],'next_offset':None}))
    page.route('**/sources/'+source_path,lambda r:r.fulfill(json={'pages':[{'page':1,'text':source['pages'][0]['text']}]}))
    requests=open_review(page,record,choices)
    plans=[]
    def commit(route):
        body=route.request.post_data_json
        plan=manual_review.validate(archive,'hyd',body)
        for p in plan['procedures']:
            if p.get('existing_skill_id'):
                manual_references.check_binding(p,contract)
        requests.append(body); plans.append(plan)
        route.fulfill(json={'sections':len(plan['sections']),'procedures':len(plan['procedures']),'steps':2,'candidate_activation':{}})
    page.route('**/api/kg/manuals/commit',commit)
    return record,contract,requests,plans


def test_general_reference_has_no_invented_role_or_execution_and_preserves_source(page,archive):
    record,contract,requests,plans=review_screen(page,archive)
    original=deepcopy(record)
    assert page.locator('[data-kind]').input_value()=='reference'
    assert page.locator('[data-fm]').is_disabled()
    assert page.locator('[data-rel]').is_disabled()
    assert page.locator('[data-reference-executable]').input_value()=='false'
    assert '미상 · 자동으로 채우지 않습니다.' in page.locator('[data-reference-comparison]').inner_text()
    assert not page.locator('#manualReviewed').is_checked()
    page.locator('#manualFullSource').click()
    page.locator('#manualSourceText summary').click()
    assert '0.9 mm/s' in page.locator('#manualSourceText').inner_text()
    retain(page,'reference-source-and-contract','#manualResult','독립 HTTP 원문 · 실제 참고 절차 검증, 운영 적재 없음',['일반 원문 참고 절차','0.9 mm/s','미상'])
    check_review(page); page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.includes('적재 완료')")
    assert requests[0]['links']['SOP-FAN-11']=={'kind':'reference','executable':False,'failureMode':None,'relation':None,'approver':None}
    assert requests[0]['procedures'][0]['steps']==original['procedures'][0]['steps']
    desired=manual_graph.desired(plans[0])
    assert not [e for e in desired['edges'] if e['type'] in ('APPROVED_BY','CONSISTS_OF','REMEDIED_BY','MITIGATED_BY','PREVENTED_BY')]
    assert record==original


def test_exact_reference_pins_actual_contract_and_changes_no_active_steps(page,archive):
    record,contract,requests,plans=review_screen(page,archive)
    page.locator('[data-reference-target]').select_option(SID)
    assert page.locator('[data-reference-pin]').input_value()==contract['contract_sha256']
    assert '실행 단계 변경 없음' in page.locator('[data-reference-comparison]').inner_text()
    assert '1.2 mm/s' in page.locator('[data-reference-comparison]').inner_text()
    assert '등록된 기존 설명 · 원본 인용 기록 없음' in page.locator('[data-reference-comparison]').inner_text()
    page.locator('#manualFullSource').click(); page.locator('#manualSourceText summary').click()
    retain(page,'reference-source-and-active-section','#manualResult','독립 HTTP 새 원문 기준 0.9와 실제 catalog DTO 형식의 등록 설명 1.2 합성 대조 · 운영 적재/단계 수정 없음',['0.9 mm/s','1.2 mm/s','실행 단계 변경 없음'])
    page.locator('[data-reference-comparison]').scroll_into_view_if_needed()
    retain(page,'reference-contract-comparison','[data-reference-comparison]','실제 제품 DOM · 독립 HTTP 원문/등록 설명 DTO, 원문 0.9와 등록 설명 1.2를 수정하지 않고 대조',['0.9 mm/s','1.2 mm/s','실행 단계 변경 없음'])
    if os.getenv('PORTAL_FAILURE_EVIDENCE'):
        folder=Path(os.environ['PORTAL_FAILURE_EVIDENCE'])
        (folder/'reference-preview.html').write_text(page.locator('#manualResult').evaluate('e=>e.outerHTML'),encoding='utf8')
        (folder/'reference-source-and-contract.json').write_text(json.dumps({'provenance':'독립 HTTP 조회 · 합성 catalog, 운영 적재 없음','source':record,'registered_contract':contract},ensure_ascii=False,indent=2),encoding='utf8')
    fold=page.locator('[data-reference-comparison] summary'); fold.focus(); page.keyboard.press('Enter')
    raw=json.loads(page.locator('[data-reference-comparison] pre').inner_text())
    assert raw['existing_skill_id']==SID and raw['reference_contract_sha256']==contract['contract_sha256']
    assert raw['current_contract']==contract
    check_review(page); page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.includes('적재 완료')")
    p=requests[0]['procedures'][0]
    assert p['existing_skill_id']==SID and p['reference_contract_sha256']==contract['contract_sha256']
    desired=manual_graph.desired(plans[0])
    assert not [n for n in desired['nodes'] if n['labels']==['Skill']]
    assert not [e for e in desired['edges'] if e['type']=='HAS_STEP']
    assert len([e for e in desired['edges'] if e['type']=='DOCUMENTS'])==2


@pytest.mark.parametrize('mismatch',['pin','steps','sop'])
def test_reference_mismatch_remains_visible_and_blocks_commit_without_repair(page,archive,mismatch):
    record,contract,requests,plans=review_screen(page,archive,pin='b'*64 if mismatch=='pin' else 'a'*64,changed=mismatch=='steps')
    if mismatch=='sop': page.locator('[data-manual-id]').fill('SOP-FAN-OTHER')
    text=page.locator('[data-reference-comparison]').inner_text()
    assert ('판본이 다릅니다' if mismatch=='pin' else '실행 단계가 다릅니다' if mismatch=='steps' else '원문 번호 불일치') in text
    assert page.locator('[data-reference-pin]').input_value()==('b'*64 if mismatch=='pin' else 'a'*64)
    if mismatch=='steps':
        assert '1.2 mm/s' in text
        page.locator('#manualFullSource').click(); page.locator('#manualSourceText summary').click()
        assert '0.9 mm/s' in page.locator('#manualSourceText').inner_text()
        retain(page,'reference-source-version-mismatch','#manualResult','독립 HTTP 원문 0.9 · 별도 실행 단계 1.2 합성 대조, 운영 판본 변경 없음',['0.9 mm/s','1.2 mm/s','실행 단계가 다릅니다'])
    check_review(page); page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.includes('일치하지 않습니다')")
    assert requests==[] and plans==[]


def test_empty_override_requires_explicit_reference_and_usage_choice(page,archive):
    record,contract,requests,plans=review_screen(page,archive,override={})
    assert page.locator('[data-kind]').input_value()=='work_order'
    assert page.locator('[data-reference-executable]').input_value()==''
    page.locator('[data-kind]').select_option('reference')
    check_review(page); page.locator('#manualCommit').click()
    assert '명시적으로 선택' in page.locator('#manualMsg').inner_text()
    assert requests==[]
    page.locator('[data-reference-executable]').select_option('false')
    assert not page.locator('#manualReviewed').is_checked()
    check_review(page); page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.includes('적재 완료')")
    assert requests[0]['procedures'][0]['link']==record['procedures'][0]['link']
    assert requests[0]['links']['SOP-FAN-11']['kind']=='reference'


def test_unknown_source_role_is_preserved_as_evidence_without_automatic_assignment(page,archive):
    record,contract,requests,plans=review_screen(page,archive,override={'kind':'reference','executable':False,'approver':'role:unknown-source'})
    assert '미상 · 자동으로 채우지 않습니다.' in page.locator('[data-reference-comparison]').inner_text()
    fold=page.locator('.mproc > details').filter(has=page.locator('summary',has_text='절차 연결 원문'))
    fold.locator(':scope > summary').focus(); page.keyboard.press('Enter')
    raw=json.loads(fold.locator('pre').inner_text())
    assert raw['override']['approver']=='role:unknown-source'
    check_review(page); page.locator('#manualCommit').click()
    page.wait_for_function("document.querySelector('#manualMsg').textContent.includes('적재 완료')")
    assert requests[0]['links']['SOP-FAN-11']['approver'] is None
    assert plans[0]['procedures'][0]['approver'] is None
