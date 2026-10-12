"""Actual immutable stored tool payloads through all portal consumers in Chromium."""
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import pytest
from test_portal_remaining_ui import page, WWW

FIXTURE=Path(__file__).parent/'fixtures/actual_tool_payloads_followup.json'
CASES=Path(__file__).parent/'fixtures/actual_bc_record_followup.json'
PAYLOADS=json.loads(FIXTURE.read_text(encoding='utf-8'))['payloads']
EVENTS={e['data']['full_output']['ref']:e for c in json.loads(CASES.read_text(encoding='utf-8')).values() if isinstance(c,dict) for e in c.get('events',[]) if e.get('data',{}).get('full_output',{}).get('stored')}
def recorded_view(event):
    cases=json.loads(CASES.read_text(encoding='utf8'))
    return next(deepcopy(c) for c in cases.values() if isinstance(c,dict) and any(w['id']==event['todo_id'] for w in c.get('workitems',[])))

@pytest.fixture
def secure_page(page):
    page.goto('https://remaining.test/')
    helper=(WWW/'app.js').read_text(encoding='utf-8').split('/* ---------------- tabs')[0]
    page.add_script_tag(content=helper+"\nconst API={process:'',agent:''}; function selectTab(n){state.tab=n;document.querySelectorAll('.view').forEach(e=>e.classList.toggle('active',e.id==='view-'+n));} window.hydApp={};")
    for name in ('ui.js','plainWords.js','trace.js','resultReport.js','caseRecord.js','taskDetail.js'):
        source=(WWW/name).read_text(encoding='utf-8')
        if name=='caseRecord.js': source=source.replace('window.hydRecord = { mount,','window.hydRecord = { toolListHtml, stepHtml, mount,')
        if name=='taskDetail.js': source=source.replace('window.hydTaskDetail = { open,','window.hydTaskDetail = { timelineHtml, open,')
        page.add_script_tag(content=source)
    assert page.evaluate('!!crypto.subtle')
    return page

def route_payload(page,payload,transform=None):
    calls=[];ref=payload['reference']['ref']
    def handle(route):
        offset=int(parse_qs(urlsplit(route.request.url).query).get('offset',['0'])[0]);calls.append(offset)
        chunk=deepcopy(next(c for c in payload['chunks'] if c['offset']==offset))
        if transform: chunk=transform(chunk)
        route.fulfill(json=chunk)
    page.route('**/api/event-payloads/'+ref+'?*',handle)
    return calls

@pytest.mark.parametrize('ref',list(PAYLOADS))
def test_actual_full_original_is_verified_once_and_same_business_summary_in_all_consumers(secure_page,ref):
    p=secure_page;payload=PAYLOADS[ref];event=deepcopy(EVENTS[ref]);before=deepcopy(event)
    calls=route_payload(p,payload)
    initial=p.evaluate('e=>UI.toolResult(e)',event)
    assert initial['status']=='warn' and initial['state']=='needs_full'
    results=p.evaluate('e=>Promise.all([UI.loadFullToolIO(e),UI.loadFullToolIO(e)])',event)
    assert all(r['state']=='complete' for r in results)
    assert calls==[c['offset'] for c in payload['chunks']]
    expected=''.join(c['content'] for c in payload['chunks'])
    assert hashlib.sha256(expected.encode()).hexdigest()==payload['reference']['sha256']
    assert results[0]['raw']==json.loads(expected)
    result=p.evaluate('e=>UI.toolResult(e)',event)
    assert result['status']=='ok' and result['state']=='complete'
    assert '확인할 수 없습니다' not in result['summary'] and '본문' not in result['summary']
    p.evaluate("e=>{selectTab('instances');const rows=hydRecord.rowsOf([e]);const trace=hydTrace.rowsOf([e]);const w={id:e.todo_id,status:'DONE',agent_orch:'cliagents'};const v={instance:{proc_inst_id:e.proc_inst_id,status:'COMPLETED'},definition:{activities:[]},workitems:[w],events:[e]};document.querySelector('#instDetail').innerHTML='<div id=recordPayload>'+hydRecord.toolListHtml(rows,false,'saved')+'</div><div id=tracePayload>'+trace.map(r=>hydTrace.rowHtml(r,false)).join('')+'</div><div id=taskPayload>'+hydTaskDetail.timelineHtml(w,[e],v,false)+'</div>';}",event)
    for selector in ('#recordPayload','#tracePayload','#taskPayload'):
        assert result['summary'] in p.locator(selector).inner_text()
        assert p.locator(selector+' [data-tool-payload-state=complete] pre').text_content()==expected
    if payload['tool'].endswith('evaluate_purchase'):
        assert '구매 후보 3개' in result['summary'] and '대체 승인 공급사 발주' in result['summary']
        assert '판단 등록 · 승인 · 실행 아님' in result['summary']
    if payload['tool'].endswith('submit_purchase'):
        assert '구매 판단 등록됨' in result['summary'] and '사람 승인 · ERP 실행 완료 아님' in result['summary']
    if isinstance(results[0]['value'].get('document'),dict) and results[0]['value']['document'].get('status')=='NO_FEASIBLE_OPTION':
        assert '추천 가능한 대안 없음' in result['summary']
    assert event==before
    p.evaluate('e=>UI.loadFullToolIO(e)',event)
    assert len(calls)==len(payload['chunks'])

@pytest.mark.parametrize('fault',['owner','hash','length','offset','next','json','cut','missing','source','original_chars','body_hash'])
def test_original_failure_boundaries_never_become_semantic_success(secure_page,fault):
    p=secure_page;payload=deepcopy(next(iter(PAYLOADS.values())));event=deepcopy(EVENTS[payload['reference']['ref']])
    if fault=='cut':
        event['data']['full_output']['cut']=True
        for c in payload['chunks']: c['meta']['cut']=True
    def broken(chunk):
        if fault=='owner':chunk['proc_inst_id']='different-case'
        if fault=='source':chunk['source']='wrong-source'
        if fault=='original_chars':chunk['meta']['original_chars']+=1
        if fault=='body_hash':chunk['content']='X'+chunk['content'][1:]
        if fault=='hash':chunk['meta']['content_sha256']='0'*64
        if fault=='length':chunk['chars']+=1
        if fault=='offset':chunk['offset']+=1
        if fault=='next':chunk['next_offset']=0
        if fault=='json':
            content='invalid JSON'
            chunk.update(content=content,chars=len(content),next_offset=None)
            event['data']['full_output'].update(chars=len(content),original_chars=len(content),sha256=hashlib.sha256(content.encode()).hexdigest())
            chunk['meta']['original_chars']=len(content)
            chunk['meta']['content_sha256']=event['data']['full_output']['sha256']
        return chunk
    if fault=='json':
        content='invalid JSON';event['data']['full_output'].update(chars=len(content),original_chars=len(content),sha256=hashlib.sha256(content.encode()).hexdigest())
    if fault=='missing':
        p.route('**/api/event-payloads/*',lambda r:r.fulfill(status=404,json={'detail':'removed'}))
    else: route_payload(p,payload,broken)
    result=p.evaluate('e=>UI.loadFullToolIO(e)',event)
    assert result['state'] in ('unavailable','truncated','invalid')
    if fault=='json': assert 'JSON' in result['error']
    if fault=='body_hash': assert 'SHA' in result['error']
    if fault=='source': assert '출처' in result['error']
    if fault=='original_chars': assert '길이' in result['error']
    rendered=p.evaluate('e=>UI.toolResult(e)',event)
    assert rendered['status']!='ok' and rendered['value'] is None

def test_same_case_content_dedup_preserves_first_provenance_and_cache_checks_descriptors(secure_page):
    p=secure_page;payload=next(iter(PAYLOADS.values()));event=deepcopy(EVENTS[payload['reference']['ref']]);calls=route_payload(p,payload)
    p.evaluate('e=>UI.loadFullToolIO(e)',event)
    duplicate=deepcopy(event);duplicate.update(todo_id='later-task',job_id='later-job');duplicate['data'].update(tool='another-tool',tool_use_id='another-call')
    assert p.evaluate('e=>UI.fullToolIO(e).state',duplicate)=='complete'
    for field,value in [('cut',True),('chars',1),('original_chars',1),('content_type','text'),('source','different')]:
        damaged=deepcopy(event);damaged['data']['full_output'][field]=value
        assert p.evaluate('e=>UI.toolResult(e).status',damaged)!='ok'
        assert p.evaluate('e=>UI.loadFullToolIO(e)',damaged)['state']=='invalid'
    assert calls==[0]
    crosscase=deepcopy(event);crosscase['proc_inst_id']='different-case'
    p.evaluate('e=>UI.loadFullToolIO(e)',crosscase)
    assert p.evaluate('e=>UI.toolResult(e).status',crosscase)!='ok'

def test_inline_mcp_error_outranks_structured_success_and_python_repr_is_never_evaluated(secure_page):
    p=secure_page
    for key in ('isError','is_error'):
        e={'data':{'tool':'hyd-dmn/evaluate_purchase','output':{key:True,'structuredContent':{'result':'ok','document':{'status':'EVALUATED'}}}}}
        assert p.evaluate('e=>UI.toolResult(e).status',e)=='fail'
    bad="{'content': [{'type': 'text', 'text': 'unsafe'}]}"
    assert p.evaluate('s=>UI.normalizeToolOutput(s).state',bad)=='invalid'
    assert p.evaluate("()=>UI.normalizeToolOutput({content:[]}).state")=='invalid'

def test_unicode_codepoint_pagination_and_large_input_are_verified_without_losing_original(secure_page):
    p=secure_page;body=json.dumps({'asset':'HYD-02','file_path':'D:/evidence/정비🛠️.txt','description':'실제 경계 검사 🛠️🚀'*500},ensure_ascii=False)
    sha=hashlib.sha256(body.encode()).hexdigest();ref='a'*64
    event={'proc_inst_id':'unicode-case','todo_id':'unicode-task','job_id':'unicode-job','data':{'tool':'Read','tool_use_id':'unicode-call','input':{'kind':'tool_output_preview','truncated':True,'content_type':'json','original_chars':len(body)},'full_input':{'stored':True,'ref':ref,'sha256':sha,'chars':len(body),'original_chars':len(body),'cut':False,'content_type':'json','source':'event_text'}}}
    split=2501;chunks=[]
    for offset,content,next_offset in [(0,body[:split],split),(split,body[split:],None)]:
        chunks.append({'id':ref,'proc_inst_id':'unicode-case','todo_id':'first-task','job_id':'first-job','tool':'first-tool','tool_use_id':'first-call','offset':offset,'chars':len(body),'content':content,'next_offset':next_offset,'content_type':'json','source':'event_text','meta':{'content_sha256':sha,'cut':False,'original_chars':len(body)}})
    payload={'reference':event['data']['full_input'],'chunks':chunks};calls=route_payload(p,payload)
    assert p.evaluate('e=>UI.toolAsk(e).state',event)=='needs_full'
    assert p.evaluate("e=>UI.loadFullToolIO(e,'input')",event)['state']=='complete'
    assert calls==[0,split]
    assert p.evaluate("e=>UI.fullToolIO(e,'input').text",event)==body
    assert '정비🛠️.txt' in p.evaluate('e=>UI.toolAsk(e).summary',event)


def test_native_trace_auto_hydrates_visible_original_and_does_not_repeat_get(secure_page):
    p=secure_page;payload=next(iter(PAYLOADS.values()));event=deepcopy(EVENTS[payload['reference']['ref']]);calls=route_payload(p,payload)
    view=recorded_view(event);view['events']=[event]
    p.evaluate("v=>{selectTab('instances');window.payloadTrace=hydTrace.mount(document.querySelector('#instDetail'));payloadTrace.update(v)}",view)
    p.wait_for_selector('[data-tool-payload-state=complete]',state='attached')
    assert p.locator('[data-tool-payload-state=complete] pre').text_content()==''.join(c['content'] for c in payload['chunks'])
    p.evaluate("()=>window.dispatchEvent(new CustomEvent('hyd-tool-payload'))")
    assert calls==[0]

def test_late_payload_completion_renders_current_view_without_old_call(secure_page):
    p=secure_page;payload=next(iter(PAYLOADS.values()));event=deepcopy(EVENTS[payload['reference']['ref']]);pending=[]
    p.route('**/api/event-payloads/*',lambda route:pending.append(route))
    view=recorded_view(event);view['events']=[event]
    p.evaluate("v=>{selectTab('instances');window.payloadTrace=hydTrace.mount(document.querySelector('#instDetail'));payloadTrace.update(v)}",view)
    p.wait_for_selector('[data-tool-payload-state=loading]',state='attached')
    assert len(pending)==1
    p.evaluate("()=>payloadTrace.update({events:[],workitems:[],instance:{proc_inst_id:'another-case',status:'COMPLETED'}})")
    pending[0].fulfill(json=payload['chunks'][0])
    p.wait_for_function('e=>UI.fullToolIO(e).state===\'complete\'',arg=event)
    assert p.locator('[data-tool-payload]').count()==0

def test_send_mail_receipt_required_and_declared_error_never_claims_sent(secure_page):
    p=secure_page
    cases=json.loads(CASES.read_text(encoding='utf8'))
    mail=next(e for c in cases.values() if isinstance(c,dict) for e in c.get('events',[]) if 'send_mail' in e.get('data',{}).get('tool','') and 'output' in e.get('data',{}))
    assert '보냄 · 발송 영수증 확인' in p.evaluate('e=>UI.toolResult(e).summary',mail)
    for output in ({},{'result':'ok','document':{}},{'result':'ok','document':{'message_id':'m','sent_at':'invalid','to':['a']}},{'is_error':True,'structuredContent':{'result':'ok','document':{'message_id':'m','sent_at':'2026-10-12T01:00:00Z','to':['a']}}}):
        event=deepcopy(mail);event['data']['output']=output;event['data'].pop('full_output',None)
        assert '보냄' not in p.evaluate('e=>UI.toolResult(e).summary',event)
        assert p.evaluate('e=>UI.toolResult(e).status',event)!='ok'
    blocked=deepcopy(mail);blocked['data']['output']='send_mail requires approval';blocked['data'].pop('full_output',None)
    result=p.evaluate('e=>UI.toolResult(e)',blocked)
    assert result['status']=='blocked'
    assert '영수증' not in result['summary'] and '보냄' not in result['summary']

@pytest.mark.parametrize('body',['{ code: original(); }\nThis is text, not JSON.',''])
def test_declared_text_original_does_not_guess_json_or_mark_empty_response_success(secure_page,body):
    p=secure_page;sha=hashlib.sha256(body.encode()).hexdigest();ref='b'*64
    reference={'stored':True,'ref':ref,'sha256':sha,'chars':len(body),'original_chars':len(body),'cut':False,'content_type':'text','source':'event_text'}
    event={'proc_inst_id':'text-case','todo_id':'text-task','job_id':'text-job','data':{'tool':'Read','output':'shortened','output_truncated':True,'full_output':reference}}
    chunk={'id':ref,'proc_inst_id':'text-case','offset':0,'chars':len(body),'content':body,'next_offset':None,'content_type':'text','source':'event_text','meta':{'cut':False,'original_chars':len(body),'content_sha256':sha}}
    route_payload(p,{'reference':reference,'chunks':[chunk]})
    loaded=p.evaluate('e=>UI.loadFullToolIO(e)',event)
    result=p.evaluate('e=>UI.toolResult(e)',event)
    assert p.evaluate('e=>UI.fullToolIO(e).text',event)==body
    if body:
        assert loaded['value']==body and result['status']=='ok'
        assert '{ code: original(); }' in result['summary'] and 'JSON' not in result['summary']
        assert p.evaluate('e=>UI.fullToolIOHtml(e)',event).find('{ code: original(); }')>=0
    else:
        assert loaded['value'] is None and loaded['state']=='invalid' and result['status']!='ok'
        assert '비어 있거나' in result['summary']
