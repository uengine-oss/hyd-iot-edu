"""New purchase tools are readable without turning calculation into approval."""
from copy import deepcopy
import json
import pytest

from test_portal_remaining_ui import page, record_components, WWW
from test_portal_failure_states_ui import retain
from test_purchase_candidate_scope import pipeline
from test_purchase_part_route import part_pipeline
from dmn_mcp.tools import enveloped
from hydcommon.skill_scope import resolve_supplier
from entsim import data


def compare_components(page):
    source=(WWW/'compare.js').read_text(encoding='utf8')
    source=source.replace('window.hydCompare = {','window.hydCompare = { callCell,')
    page.add_script_tag(content=source)


def test_purchase_trace_uses_real_backend_part_candidate_and_submission_records(page,part_pipeline):
    tools,_,_,_,_,submitted=part_pipeline
    records={
        'purchase_context':enveloped(tools.purchase_context)('HYD-03','P-KIT'),
        'evaluate_purchase':enveloped(tools.evaluate_purchase)('HYD-03','P-KIT'),
        'submit_purchase':enveloped(tools.submit_purchase)('HYD-03','P-KIT','INC-C'),
    }
    assert all(r['result']=='ok' for r in records.values()) and len(submitted)==1
    assert records['evaluate_purchase']['document']['status']=='EVALUATED'
    assert records['submit_purchase']['document']['status']=='SUBMITTED'
    before=deepcopy(records)
    record_components(page)
    events=[]
    for name,result in records.items():
        raw='hyd-dmn/'+name
        expected=page.evaluate('r=>UI.toolName(r)',raw)
        assert name not in expected
        assert expected==page.evaluate('r=>UI.toolName(r)','mcp__hyd-dmn__'+name)
        events.extend([
            {'id':name+'-start','event_type':'tool_usage_started','data':{'tool':raw,'tool_use_id':name,'input':{'asset':'HYD-03','part_no':'P-KIT','incident':'INC-C'}}},
            {'id':name+'-done','event_type':'tool_usage_finished','data':{'tool':raw,'tool_use_id':name,'output':{'structured_content':result,'content':[{'type':'text','text':json.dumps(result,ensure_ascii=False)}]},'is_error':False}},
        ])
    page.evaluate("evs=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=\"purchaseTrace\" class=\"tr\">'+hydTrace.rowsOf(evs).map(r=>hydTrace.rowHtml(r,false)).join('')+'</div>';}",events)
    text=page.locator('#purchaseTrace').inner_text()
    assert '씰 키트' in text and '부품 번호 P-KIT' in text and '구매 후보 1개' in text
    assert '후보 비교 완료' in text and '구매 판단 등록됨' in text
    # 2026-10-23 갱신: 공개 용어 정리로 'ERP 실행 완료 아님'→'구매 실행 완료 아님'(plainWords.js submit_purchase 요약, 2026-10-12 public-language-and-stream)
    assert '판단 등록 · 승인 · 실행 아님' in text and '사람 승인 · 구매 실행 완료 아님' in text
    for token in ('purchase_context','evaluate_purchase','submit_purchase','part:kit','skill:purchase','part_no','SUBMITTED'):
        assert token not in text
    retain(page,'purchase-tools-trace','#purchaseTrace','Real Part-scoped backend calculation/registration in a memory fixture with isolated graph/ERP/submit doubles; production trace and unchanged canonical inputs. Not operating approval or ERP execution.',
           ['씰 키트','구매 후보 1개','구매 판단 등록됨','사람 승인 · 구매 실행 완료 아님'])  # 2026-10-23 갱신: 공개 용어 정리로 'ERP 실행 완료 아님'→'구매 실행 완료 아님'(plainWords.js submit_purchase 요약, 2026-10-12 public-language-and-stream)
    for fold in page.locator('#purchaseTrace details.tr-tool').all():
        fold.locator(':scope > summary').focus()
        page.keyboard.press('Enter')
    raw_text=page.locator('#purchaseTrace').inner_text()
    for token in ('purchase_context','evaluate_purchase','submit_purchase','part:kit','skill:purchase','part_no'):
        assert token in raw_text
    assert records==before


def test_purchase_trace_keeps_unknown_long_response_exactly_in_closed_raw_detail(page):
    record_components(page)
    output={'future_schema':{'unchanged_payload':'x'*12000,'original_marker':'마지막 원문 표식'}}
    page.evaluate("o=>{selectTab('instances');const r=hydTrace.rowsOf([{id:'unknown',event_type:'tool_usage_finished',data:{tool:'hyd-dmn/evaluate_purchase',output:o,is_error:false}}])[0];document.querySelector('#instDetail').innerHTML='<div id=\"purchaseUnknown\">'+hydTrace.rowHtml(r,false)+'</div>';}",output)
    text=page.locator('#purchaseUnknown').inner_text()
    assert '결과 형식을 확인하세요' in text and 'future_schema' not in text
    summary=page.locator('#purchaseUnknown summary')
    summary.focus()
    page.keyboard.press('Enter')
    assert json.loads(page.locator('#purchaseUnknown .tr-code').last.locator('pre').inner_text())==output


def test_context_reference_unknown_usage_and_errors_do_not_become_candidates_or_success(page):
    record_components(page)
    context={'result':'ok','document':{'part':{'id':'part:review','name':'검토 부품','partNo':'P-REVIEW'},'procedures':[
        {'id':'skill:reference','name':'공급 조건 확인','executable':False},{'id':'skill:missing','name':'이름 확인 절차'}]}}
    summary=page.evaluate('o=>hydWords.got("hyd-dmn/purchase_context",o)',context)
    assert '실행 후보 검토 대상 0개' in summary and '참고 보관 1개' in summary and '사용 방식 기록 미확인 1개' in summary
    assert '공급 조건 확인' in summary and '판단 등록 없음' in summary
    error={'result':'error','error_kind':'INVALID','message':'실제 ERP 재주문점 이탈을 확인할 수 없습니다'}
    summary=page.evaluate('o=>hydWords.got("hyd-dmn/evaluate_purchase",o)',error)
    assert '확인할 수 없습니다' in summary and '후보 비교 완료' not in summary
    assert '원문' in page.evaluate('hydWords.got("hyd-dmn/evaluate_purchase",{future_schema:123})')
    malformed={'result':'ok','document':{'id':'evaluation-only','status':'EVALUATED','result':{'options':[],'recommended':None}}}
    summary=page.evaluate('o=>hydWords.got("hyd-dmn/submit_purchase",o)',malformed)
    assert '등록 완료 기록 없음' in summary and '구매 판단 등록됨' not in summary
    assert '가정값을 넣은 비교' in page.evaluate('hydWords.ask("hyd-dmn/evaluate_purchase",{asset:"HYD-03",part_no:"P-REVIEW",overrides:{need_qty:8}})')
    events=[{'id':'invalid','event_type':'tool_usage_finished','data':{'tool':'hyd-dmn/evaluate_purchase','output':{'structured_content':error},'is_error':False}}]
    state=page.evaluate('evs=>({trace:hydTrace.rowsOf(evs)[0],record:hydRecord.rowsOf(evs)[0]})',events)
    assert state['trace']['status']==state['record']['status']=='fail'
    assert '재주문점 이탈을 확인할 수 없습니다' in state['trace']['result']
    assert state['record']['output']==events[0]['data']['output']


@pytest.mark.parametrize('status',['BLOCKED','FAILED','DONE'])
def test_compare_keeps_purchase_request_and_unknown_result_original_accessible(page,status):
    record_components(page)
    compare_components(page)
    call={'server':'hyd-dmn','tool':'submit_purchase','status':status,'args':{'asset':'HYD-03','part_no':'P-REVIEW','process_scope':{'workitem':'original-workitem'}},
          'reason':'원래 진단 사유','summary':'original_internal_summary','future_result':{'unknown_field':17}}
    original=deepcopy(call)
    page.evaluate("c=>{selectTab('compare');document.querySelector('#compareView').innerHTML=hydCompare.callCell(c,1);}",call)
    text=page.locator('#compareView').inner_text()
    assert '구매 판단 등록 (승인 · 실행 아님)' in text and '부품 번호 P-REVIEW' in text
    assert '구매 판단 등록됨' not in text
    assert 'original_internal_summary' not in text and 'process_scope' not in text and 'original-workitem' not in text
    assert ('차단' if status=='BLOCKED' else '실패' if status=='FAILED' else '상세 결과 값 기록 없음') in text
    fold=page.locator('#compareView details')
    fold.locator(':scope > summary').focus()
    page.keyboard.press('Enter')
    assert json.loads(fold.locator('pre').inner_text())==original
    assert call==original


@pytest.mark.parametrize('policy,expected_supplier,price,lead,avl',[
    ('oem','B-OEM (순정)',55,5,True),('lowest_approved','A정밀 (저가)',35,2,True),('fastest_quote','C트레이딩 (최저가)',20,1,False)])
def test_resolved_supplier_summary_keeps_actual_quote_policy_and_avl_distinct_from_human_approval(page,policy,expected_supplier,price,lead,avl):
    quotes=data.quote_rows('P-PMP-SEAL')
    facts={'purchase_part':'part:pump-seal','spare_part_no':'P-PMP-SEAL','spare_quotes':{q['supplier']:{k:v for k,v in q.items() if k!='supplier'} for q in quotes}}
    skill={'scope':'purchase','executable':True,'supplier_policy':policy,'actions':[{'code':'PR_CREATE','value':None}],
           'partSuppliers':[{'part':'part:pump-seal','supplier':q['supplier']} for q in quotes]}
    original=deepcopy((skill,facts))
    resolved=resolve_supplier(skill,facts)
    record_components(page)
    dto={'result':'ok','document':{'status':'EVALUATED','origin':{'part':{'id':'part:pump-seal','name':'펌프 축 씰 키트','partNo':'P-PMP-SEAL'}},
         'facts':{'need_qty':6},'result':{'options':[{'id':'skill:purchase-policy','name':'원문 구매 정책','feasible':avl,'resolvedSupplier':resolved['resolvedSupplier']}],
         'recommended':'skill:purchase-policy' if avl else None}}}
    summary=page.evaluate('o=>hydWords.got("hyd-dmn/evaluate_purchase",o)',dto)
    assert expected_supplier in summary and f'단가 {price}만원' in summary and f'납기 {lead}일' in summary
    assert ('등록 AVL 통과' if avl else '등록 AVL 미통과') in summary
    assert '판단 등록 · 승인 · 실행 아님' in summary
    assert policy not in summary and 'sup:' not in summary
    assert (skill,facts)==original
