"""Actual saved API records replayed offline; current execution and text bounds."""
import json
from pathlib import Path
import pytest
from test_portal_remaining_ui import page, record_components, WWW

SAVED = Path(__file__).parent/'fixtures/actual_bc_record_followup.json'

def actual():
    return json.loads(SAVED.read_text(encoding='utf-8'))

def render(page, view):
    record_components(page)
    page.evaluate("v=>{selectTab('instances');const m=hydRecord.build(v);window.recordModel=m;document.querySelector('#instDetail').innerHTML='<ol id=actualRecord>'+m.steps.map((s,i)=>'<li class=\"cr-step open\" data-step=\"'+s.key+'\">'+hydRecord.stepHtml(s,i,m.steps.length,true)+'</li>').join('')+'</ol>';document.querySelectorAll('#actualRecord details[data-open-default]').forEach(d=>d.open=true);}", view)

def test_actual_purchase_route_is_explicit_and_unknown_route_still_errors(page):
    record_components(page)
    page.add_script_tag(path=str(WWW/'approvalCard.js'))
    result=page.evaluate("()=>{try{return {value:hydWords.causeWords('purchase-part')}}catch(e){return {error:e.message}}}")
    assert 'error' not in result
    assert result['value']['cause'] == '구매 대상 부품'
    assert page.evaluate("()=>{try{hydWords.causeWords('unknown-route');return false}catch(e){return e.message.includes('cause_route')}}")
    # The completed purchase record itself remains renderable without inventing diagnosis.
    decision=actual()['C_decision']
    model=page.evaluate("x=>hydRecord.build(x.v,{decision:x.d})",{'v':actual()['C'],'d':decision})
    assert model['steps']
    kg=page.evaluate("d=>hydRecord.knowledgeHtml({v:{}},null,d)",decision)
    assert '구매 대상 부품' in kg and '펌프 축 씰 키트' in kg
    assert '고장 유형' not in kg and '원인을 정한 근거' not in kg
    agent=next(s for s in model['steps'] if s.get('w',{}).get('output',{} ) and s['w']['output'].get('decision_id'))
    assert '대안 3개' in agent['sentence'] and '대체 승인 공급사 발주' in agent['sentence']
    assert '순정(OEM)' not in agent['sentence']
    assert any('순정(OEM)' in s.get('sentence','') for s in model['steps'] if s['type']=='approve')

def test_actual_purchase_order_structured_approver_and_names_are_readable(page):
    record_components(page)
    page.add_script_tag(path=str(WWW/'approvalCard.js'))
    decision=actual()['C_decision']
    view=actual()['C']
    page.evaluate('x=>hydRecord.build(x.v,{decision:x.d})',{'v':view,'d':decision})
    source=(WWW/'taskDetail.js').read_text(encoding='utf-8').replace('window.hydTaskDetail = { open,','window.hydTaskDetail = { valueHtml, basisHtml, open,')
    page.add_script_tag(content=source)
    value=next(r['value'] for r in view['instance']['variables_data'] if r['key']=='decision')
    page.evaluate("x=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=purchaseOutput>'+hydTaskDetail.valueHtml('decision',x.d,x.v)+'</div>'}",{'d':value,'v':view})
    text=page.locator('#purchaseOutput').inner_text()
    assert '[object Object]' not in text and '구매 담당' in text
    assert 'skill:sop-pur' not in page.locator('#purchaseOutput > .td-list').inner_text()
    assert value['recommended']=='skill:sop-pur-12'
    assert page.evaluate("()=>hydTaskDetail.basisHtml({},[{event_type:'task_working',data:{type:'evidence'}}])") == ''

def test_actual_deferred_execution_has_no_active_claim_or_spinner(page):
    render(page, actual()['B'])
    step=page.evaluate("()=>recordModel.steps.find(s=>s.w?.status==='PENDING')")
    assert step['live'] is False
    assert step['state']=='wait'
    assert '평가를 보류' in step['sentence']
    assert not step['now']
    assert page.locator(f'#actualRecord [data-step="{step["key"]}"] .cr-now').count()==0
    trace=page.evaluate("v=>hydTrace.build({view:v}).steps.find(s=>s.w.status==='PENDING')",actual()['B'])
    assert trace['live'] is False and trace['state']=='pending'

def test_actual_cancelled_system_without_receipt_does_not_claim_registration(page):
    render(page, actual()['B'])
    step=page.evaluate("()=>recordModel.steps.find(s=>s.w?.status==='CANCELLED'&&s.w.tool==='enterprise:WO_CREATE')")
    assert '등록하는 중' not in step['sentence']
    assert '등록 결과가 없습니다' in step['sentence']

@pytest.mark.parametrize('width',[1440,1024])
def test_actual_start_value_text_ranges_stay_inside_grid_cells(page,width):
    page.set_viewport_size({'width':width,'height':1000})
    render(page, actual()['B'])
    bounds=page.evaluate("""()=>Array.from(document.querySelectorAll('#actualRecord .cr-kv dd')).filter(e=>e.checkVisibility()).map(e=>{const r=document.createRange();r.selectNodeContents(e);const box=e.getBoundingClientRect();return {text:e.textContent,left:box.left,right:box.right,rects:Array.from(r.getClientRects()).map(x=>({left:x.left,right:x.right}))}})""")
    assert bounds
    assert all(r['left']>=b['left']-1 and r['right']<=b['right']+1 for b in bounds for r in b['rects']),bounds

def test_original_numeric_nowrap_reproduces_actual_text_overlap(page):
    render(page, actual()['B'])
    page.add_style_tag(content='.cr-kv dd.num {white-space:nowrap}')
    overlaps=page.evaluate("""()=>Array.from(document.querySelectorAll('#actualRecord .cr-kv dd.num')).filter(e=>e.checkVisibility()).map(e=>{const r=document.createRange();r.selectNodeContents(e);return {text:e.textContent,width:r.getBoundingClientRect().width,cell:e.getBoundingClientRect().width}}).filter(x=>x.width>x.cell+1)""")
    assert overlaps, 'The original inherited numeric nowrap must reproduce the saved long string defect'

def test_later_execution_reactivates_pending_and_late_same_run_text_does_not(page):
    record_components(page)
    view=actual()['B'];w=next(w for w in view['workitems'] if w['status']=='PENDING')
    view['events'].append({'id':'late-text','todo_id':w['id'],'job_id':w['draft']['_deferral']['id'],'event_type':'task_working','timestamp':'2026-10-12T09:00:00Z','data':{'type':'text','content':'late historical text'}})
    assert page.evaluate("v=>hydRecord.build(v).steps.find(s=>s.w?.status==='PENDING').live",view) is False
    view['events'].append({'id':'next-start','todo_id':w['id'],'job_id':'new-execution','event_type':'task_started','timestamp':'2026-10-12T10:00:00Z','data':{}})
    assert page.evaluate("v=>hydRecord.build(v).steps.find(s=>s.w?.status==='PENDING').live",view) is True
    view['events'].extend([
        {'id':'old-terminal','todo_id':w['id'],'job_id':'old-execution','event_type':'task_deferred','timestamp':'2026-10-12T11:00:00Z','data':{}},
        {'id':'global-terminal','job_id':'new-execution','event_type':'task_completed','timestamp':'2026-10-12T11:00:00Z','data':{}},
    ])
    assert page.evaluate("v=>hydRecord.build(v).steps.find(s=>s.w?.status==='PENDING').live",view) is True

def test_queued_agent_without_recorded_start_is_waiting_without_active_spinner(page):
    view=actual()['B'];w=next(w for w in view['workitems'] if w['status']=='PENDING')
    view['events']=[ev for ev in view['events'] if ev.get('todo_id')!=w['id']]
    render(page,view)
    step=page.evaluate("()=>recordModel.steps.find(s=>s.w?.status==='PENDING')")
    assert not step['live'] and step['state']=='wait' and not step['now']
    assert '일을 받기를 기다리는' in step['sentence']

def test_actual_agent_task_open_fetches_bound_original_decision_and_preserves_current_approval(page):
    record_components(page)
    view=actual()['C'];decision=actual()['C_decision']
    worker=next(w for w in view['workitems'] if w.get('output',{} ) and w['output'].get('decision_id'))
    requested=[]
    page.route('**/api/todolist/'+worker['id'],lambda r:r.fulfill(json=worker))
    def decision_get(route):
        requested.append(route.request.url)
        route.fulfill(json=decision)
    page.route('**/api/decisions/'+worker['output']['decision_id'],decision_get)
    page.add_script_tag(path=str(WWW/'taskDetail.js'))
    page.evaluate("v=>{selectTab('instances');window.hydInstances={I:{view:v}};hydTaskDetail.mount(document.querySelector('#instDetail'));}",view)
    page.evaluate('wid=>hydTaskDetail.open(wid)',worker['id'])
    assert len(requested)==1
    output=page.locator('[data-task-detail] [data-k=output]')
    text=output.inner_text()
    assert '대체 승인 공급사 발주' in text
    assert '최단 납기 긴급 발주' in text and '구매 담당' in text
    assert '구매 부품을 기준으로 판단 · 고장 원인 판정 없음' in text
    assert '구매 대상 부품' in text and '펌프 축 씰 키트' in text and 'P-PMP-SEAL' in text
    assert '[object Object]' not in text and '표시 이름 미등록' not in text
    assert '당시 추천 · 현재 승인 선택과 별도' in text
    assert worker['output']['decision']['recommended']=='skill:sop-pur-12'
    assert decision['recommended']=='skill:sop-pur-11'
    # A current instance id from a later generation cannot replace this task's own recorded id.
    view['instance']['variables_data']= [dict(r,value='later-generation-decision') if r['key']=='decision_id' else r for r in view['instance']['variables_data']]
    page.evaluate('v=>hydInstances.I.view=v',view)
    page.evaluate('wid=>hydTaskDetail.open(wid)',worker['id'])
    assert all(url.endswith(worker['output']['decision_id']) for url in requested)
