"""Production portal components in Chromium; failures injected at HTTP/storage boundaries.

The real index/CSS/scripts are used. Component harness exports are appended only
in memory; the product has no testing entry points.
"""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from test_b1_agent_authoring import env as agent_env
from test_bpmn_import import api as flow_api, LOOP
from test_close_agent_task import stuck
from test_instances import rt

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'it/portal/www'


@pytest.fixture
def page():
    pw = pytest.importorskip('playwright.sync_api')
    with pw.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        def route(r):
            path = urlsplit(r.request.url).path
            if path == '/':
                html = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', (WWW/'index.html').read_text(encoding='utf8'))
                r.fulfill(content_type='text/html', body=html)
            elif (WWW/path.lstrip('/')).is_file():
                r.fulfill(path=str(WWW/path.lstrip('/')))
            else:
                r.fulfill(content_type='application/json', body='{}')
        page.route('**/*', route)
        page.goto('http://remaining.test/')
        helper = (WWW/'app.js').read_text(encoding='utf8').split('/* ---------------- tabs')[0]
        page.add_script_tag(content=helper + "\nconst API={process:'',agent:''}; function selectTab(n){state.tab=n;document.querySelectorAll('.view').forEach(e=>e.classList.toggle('active',e.id==='view-'+n));} window.hydApp={};")
        page.add_script_tag(path=str(WWW/'ui.js'))
        page.add_script_tag(path=str(WWW/'plainWords.js'))     # 포털처럼 조사 도우미(hydWords)를 먼저 — agents.js 알림이 쓴다
        navigation=(WWW/'app.js').read_text(encoding='utf8').split('/* ---------------- tabs ---------------- */')[1].split("selectTab('main');")[0]
        page.add_script_tag(content=navigation)
        yield page
        assert not errors, errors
        browser.close()


def test_incident_poll_rejects_non_list_preserves_last_good_and_recovers(page):
    source = (WWW/'app.js').read_text(encoding='utf8')
    refresh = source.split('async function refreshSlow() {')[1].split('renderStack(); pollHealth();')[0]
    render = source.split('function renderIncList() {')[1].split('async function loadDetail')[0]
    page.add_script_tag(content="""const PATTERN_LABEL={}; function renderScada(){}; async function refreshBiz(){};
      async function loadDetail(){}; function renderDetail(){}; function incidentsFor(a){return state.incidents.filter(i=>i.asset===a);}
      function openIncidentFor(){return null;}
    """ + 'function renderIncList() {' + render + '\nasync function refreshSlow() {' + refresh)
    page.evaluate("state.tab='incidents';state.biz={};state.definition={};")
    row = {'id':'I1','asset':'HYD-01','terminal':False,'state':'WAIT_APPROVAL','created':'2026-10-12T00:00:00Z'}
    page.route('**/api/incidents', lambda r: r.fulfill(json=[row]))
    page.route('**/api/agent/runs', lambda r: r.fulfill(json=[]))
    page.route('**/api/audit', lambda r: r.fulfill(json=[]))
    page.evaluate('refreshSlow()')
    assert page.locator('#openCount').inner_text() == '1'
    page.route('**/api/incidents', lambda r: r.fulfill(json={'detail':'broken upstream'}))
    page.evaluate('refreshSlow()')
    assert page.locator('#openCount').inner_text() == '읽기 실패'
    assert '응답 형식' in page.locator('#incList').inner_text()
    assert '마지막으로 읽은 목록' in page.locator('#incList').inner_text()
    assert page.evaluate('state.incidents[0].id') == 'I1'
    page.route('**/api/incidents', lambda r: r.fulfill(json=[]))
    page.evaluate('refreshSlow()')
    assert page.locator('#openCount').inner_text() == '0'
    assert '읽지 못했습니다' not in page.locator('#incList').inner_text()


@pytest.mark.parametrize('stored', [{'fields': None}, {'name':'old draft'}, '{broken'])
def test_skill_invalid_local_draft_is_preserved_until_explicit_discard(page, stored):
    skill = {'id':'skill:sample','name':'팬 점검','revision':1,'kind':'work_order'}
    raw = stored if isinstance(stored,str) else json.dumps(stored)
    page.evaluate('(v)=>sessionStorage.setItem("hyd:skill-edit:skill:sample",v)', raw)
    page.route('**/api/kg/skills', lambda r: r.fulfill(json=[skill]))
    page.route('**/api/kg/catalog', lambda r: r.fulfill(json={'roles':[],'failureModes':[]}))
    page.add_script_tag(path=str(WWW/'hitl.js'))
    page.evaluate("selectTab('skills')")
    page.locator('#skMsg').filter(has_text='초안').wait_for()
    assert page.locator('#skSave').is_disabled()
    assert page.evaluate('sessionStorage.getItem("hyd:skill-edit:skill:sample")') == raw
    page.locator('#skReload').click()
    page.locator('dialog button[value=cancel]').click()
    assert page.evaluate('sessionStorage.getItem("hyd:skill-edit:skill:sample")') == raw
    page.locator('#skReload').click()
    page.locator('dialog button[value=ok]').click()
    page.wait_for_function('!document.querySelector("#skSave").disabled')
    assert page.locator('#skName').input_value() == '팬 점검'
    assert page.evaluate('sessionStorage.getItem("hyd:skill-edit:skill:sample")') is None


def test_invalid_json_is_reported_not_replaced_with_empty_success(page):
    page.route('**/broken', lambda r: r.fulfill(content_type='text/html', body='unavailable'))
    message = page.evaluate("requestJ('/broken').then(()=> 'unexpected success', e=>e.message)")
    assert '응답을 읽을 수 없습니다' in message


def record_components(page):
    for name in ('plainWords.js','trace.js','resultReport.js','caseRecord.js'):
        source = (WWW/name).read_text(encoding='utf8')
        if name == 'caseRecord.js':
            source = source.replace('window.hydRecord = { mount, build, rowsOf,', 'window.hydRecord = { stepHtml, sysDetail, mount, build, rowsOf,')
        page.add_script_tag(content=source)


def test_record_loose_effects_failure_and_restore_values_are_visible(page):
    record_components(page)
    events = [
        {'id':'restore','job_id':'SCENARIO_BUTTON','event_type':'task_working','timestamp':'2026-10-12T00:00:01Z','data':{'name':'쿨러 복구','by':'김운전','setpoints':{'before':{'FanSpeedSP':100,'LoadSP':70},'after':{'FanSpeedSP':60,'LoadSP':90}}}},
        {'id':'review','job_id':'EFFECT_REVIEW','event_type':'task_working','timestamp':'2026-10-12T00:00:02Z','data':{'by':'김담당','role':'role:student','reason':'실제 영향을 확인함','effects':['effect1']}},
        {'id':'undo','job_id':'EFFECT_COMPENSATION','event_type':'error','timestamp':'2026-10-12T00:00:03Z','data':{'by':'김담당','reason':'발주 취소 필요','results':[{'ok':False,'error':'업무 시스템 연결 실패'}]}},
    ]
    view = {'instance':{'proc_inst_id':'student.case','proc_def_id':'student_flow','proc_inst_name':'학생 흐름','status':'COMPLETED','variables_data':[], 'initial_variables':{},'start_date':'2026-10-12T00:00:00Z'},
            'definition':{'processDefinitionName':'학생 요청 처리','roles':[{'endpoint':'role:student','name':'행사 담당'}]}, 'events':events, 'workitems':[]}
    page.evaluate("""view=>{const m=hydRecord.build(view,{agents:[],people:[]});window.recordModel=m;
      const host=document.createElement('div');host.id='instRecord';host.className='cr';host.innerHTML=m.steps.map((s,i)=>'<section class="cr-step open">'+hydRecord.stepHtml(s,i,m.steps.length,true)+'</section>').join('');
      const restore=hydRecord.rowsOf(view.events)[0];host.insertAdjacentHTML('beforeend',hydRecord.sysDetail(restore));selectTab('instances');
      document.querySelector('#instDetail').innerHTML=host.outerHTML;
    }""", view)
    text = page.locator('#instDetail').inner_text()
    assert '팬 지령 100 % → 60 %' in text and '부하 지령 70 % → 90 %' in text
    assert '이전 조치 영향 확인' in text and '행사 담당' in text
    assert '되돌림 실패: 업무 시스템 연결 실패' in text
    assert '학생 요청 처리' in text and 'student_flow' not in text
    assert page.evaluate("recordModel.steps.find(s=>s.key==='effect:undo').state") == 'fail'
    trace = page.evaluate('(events)=>hydTrace.rowsOf(events).map(r=>r.text).join(" ")', events)
    assert '팬 지령 100 % → 60 %' in trace and '실제 영향을 확인함' in trace
    capture(page,'record-effects')


def test_failed_tool_attempt_and_mcp_extracted_values_are_not_success(page):
    record_components(page)
    events=[{'id':'e1','event_type':'tool_usage_finished','data':{'tool':'mcp__enterprise__erp_inventory','output':{'available':3},'attempt_failed':True}},
            {'id':'e2','event_type':'task_working','job_id':'MCP_RESULT_VALUES','data':{'name':'MCP 결과에서 값을 꺼냄','values':{'available':3},'attempt_failed':True}}]
    data=page.evaluate('events=>({record:hydRecord.rowsOf(events),trace:hydTrace.rowsOf(events)})',events)
    assert data['record'][0]['status']=='fail' and data['trace'][0]['status']=='fail'
    assert data['record'][0]['badge']=='실패한 시도'
    assert '가용 재고' in data['trace'][1]['text'] and '실패한 시도' in data['trace'][1]['text']
    assert '가용 재고' in page.evaluate('r=>hydRecord.sysDetail(r)',data['record'][1])


def route_client(page, client):
    def route(r):
        url=urlsplit(r.request.url)
        response=client.request(r.request.method,url.path+('?' + url.query if url.query else ''),content=r.request.post_data,headers={'content-type':'application/json'})
        r.fulfill(status=response.status_code,content_type='application/json',body=response.content)
    page.route('**/api/**',route)


def capture(page, name):
    folder=os.getenv('PORTAL_REMAINING_EVIDENCE')
    if not folder: return
    Path(folder).mkdir(parents=True,exist_ok=True)
    for width in (1440,1024):
        page.set_viewport_size({'width':width,'height':1000})
        page.screenshot(path=str(Path(folder)/f'{name}-{width}.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_agent_work_rules_save_reload_and_failed_save_keeps_draft(page, agent_env):
    client,rt=agent_env
    route_client(page,client)
    page.add_script_tag(path=str(WWW/'agents.js'))
    page.evaluate("selectTab('agents');hydAgents.mount(document.querySelector('#agentsView'))")
    page.locator('[data-new-agent]').click()
    page.locator('[data-f=name]').fill('학생 행사 담당')
    page.locator('[data-f=goal]').fill('행사 요청 근거를 모은다')
    page.locator('[data-f=work_rules]').select_option('hyd-plant')
    page.route('**/api/agents',lambda r: r.fulfill(status=500,json={'detail':'저장 실패'}))
    page.locator('[data-ag-form] button[type=submit]').click()
    page.locator('[data-ag-form] .form-msg').filter(has_text='저장 실패').wait_for()
    assert page.locator('[data-f=name]').input_value()=='학생 행사 담당'
    assert page.locator('[data-f=work_rules]').input_value()=='hyd-plant'
    page.unroute('**/api/agents')
    page.locator('[data-ag-form] button[type=submit]').click()
    page.locator('[data-edit-agent]').wait_for()
    assert '업무 규칙' in page.locator('[data-ag-detail]').inner_text()
    uid=next(a['id'] for a in client.get('/api/agents').json() if a['name']=='학생 행사 담당')
    assert client.get('/api/agents/'+uid).json()['work_rules']=='hyd-plant'
    capture(page,'agent-work-rules')
    page.locator('[data-edit-agent]').click()
    assert page.locator('[data-f=work_rules]').input_value()=='hyd-plant'
    page.locator('[data-f=work_rules]').select_option('')
    page.locator('[data-ag-form] button[type=submit]').click()
    page.locator('[data-edit-agent]').wait_for()
    assert client.get('/api/agents/'+uid).json()['work_rules'] is None


def test_delete_one_flow_ui_requires_actor_preserves_on_error_then_removes_only_one(page, flow_api):
    client,rt,repo,audit=flow_api
    for id in ('student_one','student_two'):
        assert client.post('/api/flows/import',json={'xml':LOOP,'file_name':'loop.bpmn','definition_id':id}).status_code==200
    route_client(page,client)
    page.add_script_tag(path=str(WWW/'flows.js'))
    page.evaluate("selectTab('flows');hydFlows.mount(document.querySelector('#flowsView'))")
    page.locator('[data-delete-flow=student_one]').click()
    box=page.locator('[data-delete-box=student_one]')
    box.locator('[data-delete-confirm]').click()
    assert '담당자를' in box.inner_text()
    box.locator('[data-delete-by]').fill('학생')
    page.route('**/api/flows/student_one?*',lambda r:r.fulfill(status=409,json={'detail':{'reason':'진행 중인 처리 건이 있습니다'}}))
    box.locator('[data-delete-confirm]').click()
    box.locator('.form-msg').filter(has_text='진행 중').wait_for()
    assert box.locator('[data-delete-by]').input_value()=='학생'
    capture(page,'flow-delete-denied')
    page.unroute('**/api/flows/student_one?*')
    box.locator('[data-delete-confirm]').click()
    page.locator('[data-delete-flow=student_one]').wait_for(state='detached')
    assert page.locator('[data-delete-flow=student_two]').count()==1
    assert client.get('/api/flows/student_one').status_code==404
    assert client.get('/api/flows/student_two').status_code==200


def test_pending_system_close_real_route_requires_reason_and_preserves_failed_input(page, stuck, monkeypatch):
    from copy import deepcopy
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import instance_mode
    runtime, inst, wi=stuck
    definition=deepcopy(runtime.repo.get_proc_def(inst['proc_def_id'],version=inst['proc_def_version'])['definition'])
    next(a for a in definition['activities'] if a['id']==wi['activity_id'])['type']='serviceTask'
    definition['version']='system-ui'
    runtime.repo.upsert_proc_def(definition)
    inst['proc_def_version']='system-ui';runtime.repo.update_instance(inst)
    wi.update(agent_mode=None,agent_orch=None,status='PENDING',draft_status=None,log='도구 연결 실패',version='system-ui')
    runtime.repo.update_workitem(wi)
    monkeypatch.setattr(instance_mode,'_runtime',runtime)
    app=FastAPI();instance_mode.mount(app,'instance');client=TestClient(app)
    route_client(page,client)
    view={'instance':inst,'definition':definition,'workitems':[wi]}
    source=(WWW/'instances.js').read_text(encoding='utf8')
    step='function stepExtra(s) {'+source.split('function stepExtra(s) {')[1].split('function mountFlow(view)')[0]
    wire='function wireStepButtons(box) {'+source.split('function wireStepButtons(box) {')[1].split('async function sendDiscard')[0]
    page.evaluate('v=>{window.closeView=v;selectTab("instances")}',view)
    page.add_script_tag(content="""const I={view:closeView,form:{by:''},closing:null,msg:'',busy:false};
      const load=async()=>{}; const chip=s=>UI.chip(s);
    """+step+wire+"""I.trace={draw:()=>{document.querySelector('#instDetail').innerHTML=stepExtra({w:I.view.workitems[0]});}};
      I.trace.draw();wireStepButtons(document.querySelector('#instDetail'));""")
    page.locator('[data-close-task]').click()
    page.locator('[data-close-go]').click()
    assert '담당자를' in page.locator('[data-reason-form]').inner_text()
    page.locator('[data-close-by]').fill('학생 담당')
    page.locator('[data-close-go]').click()
    assert runtime.repo.get_workitem(wi['id'])['status']=='PENDING'
    page.locator('[data-close-reason]').fill('도구 연결 실패로 실습 종료')
    page.route('**/api/todolist/*/close',lambda r:r.fulfill(status=500,json={'detail':'일시 저장 실패'}))
    page.locator('[data-close-go]').click()
    page.locator('[data-reason-form]').filter(has_text='일시 저장 실패').wait_for()
    assert page.locator('[data-close-reason]').input_value()=='도구 연결 실패로 실습 종료'
    capture(page,'pending-system-close')
    page.unroute('**/api/todolist/*/close')
    page.locator('[data-close-go]').click()
    page.wait_for_function('!I.busy')
    assert page.evaluate('I.closing === null'), page.locator('[data-reason-form]').inner_text()
    assert runtime.repo.get_workitem(wi['id'])['status']=='CANCELLED'
    assert runtime.repo.get_instance(inst['proc_inst_id'])['end_event']=='closed-by-human'


def test_background_plant_poll_handles_null_units_on_skills_tab(page):
    source=(WWW/'app.js').read_text(encoding='utf8')
    fast='async function refreshFast() {'+source.split('async function refreshFast() {')[1].split('async function refreshSlow()')[0]
    page.add_script_tag(content=fast)
    page.route('**/undefined/api/state',lambda r:r.fulfill(json={'units':None}))
    page.evaluate("async()=>{state.tab='skills';await refreshFast();}")
    page.locator('.clock-pop').evaluate('e=>e.open=true')
    assert page.locator('#simT').inner_text()=='설비 상태 읽기 실패'
    assert '응답 형식' in page.locator('#simT').get_attribute('title')


def test_generic_approval_record_uses_event_choice_not_later_current_values(page):
    record_components(page)
    view={'instance':{'proc_inst_id':'student.case','proc_def_id':'student','proc_inst_name':'행사 요청','status':'COMPLETED','variables_data':[{'key':'approved_option','value':{'slot':'현재 다음 회차 안'}}]},
          'definition':{'roles':[{'name':'행사 담당','endpoint':'role:demo-organizer'}],'activities':[{'id':'approve','name':'행사 승인','approval':{'key':'slot'}}]},
          'workitems':[{'id':'old','activity_id':'approve','activity_name':'행사 승인','tool':'formHandler:approve','status':'DONE','output':{'approval':'승인'},'user_id':'role:demo-organizer'}],
          'events':[{'id':'accepted','todo_id':'old','job_id':'APPROVAL_ACCEPTED','event_type':'task_working','data':{'by':'김담당','role':'role:demo-organizer','option':{'slot':'오전 10시'},'reason':'참석 가능'}}]}
    model=page.evaluate('v=>hydRecord.build(v,{agents:[],people:[]})',view)
    step=next(s for s in model['steps'] if s['key']=='old')
    assert '오전 10시' in step['sentence'] and '현재 다음 회차' not in step['sentence']
    assert '행사 담당' in step['sections'][0]['body'] and 'role:demo-organizer' not in step['sections'][0]['body']
    assert page.evaluate('d=>UI.roleName("role:demo-organizer",d)',view['definition'])=='행사 담당'


def test_record_shows_missing_skill_file_and_unreadable_observation_series(page):
    record_components(page)
    view={'instance':{'proc_inst_id':'case','status':'COMPLETED','variables_data':[{'key':'incident','value':'INC1'},{'key':'recovered','value':False}]},
          'definition':{'activities':[{'id':'agent','name':'분석'},{'id':'check','name':'효과 확인'}]},
          'workitems':[{'id':'w1','activity_id':'agent','activity_name':'분석','agent_orch':'cliagents','agent_mode':'COMPLETE','status':'DONE'},
                       {'id':'w2','activity_id':'check','activity_name':'효과 확인','agent_orch':'system','tool':'incident:reobserve','status':'DONE','output':{'recovered':False}}],
          'events':[{'id':'provided','todo_id':'w1','event_type':'task_started','data':{'skills':[{'name':'팬 점검','written':False,'error':'권한 거부'}]}}]}
    ext={'agents':[],'people':[],'incident':{'reobsSeries':{'error':'센서 기록 연결 실패'},'history':[]}}
    model=page.evaluate('x=>hydRecord.build(x.view,x.ext)',{'view':view,'ext':ext})
    rendered=json.dumps(model,ensure_ascii=False)
    assert '작업 폴더에 못 넣음' in rendered and '권한 거부' in rendered
    assert '값 흐름을 읽지 못했습니다' in rendered and '센서 기록 연결 실패' in rendered


def test_old_task_inputs_do_not_present_new_round_as_historical_input(page):
    source=(WWW/'taskDetail.js').read_text(encoding='utf8').replace('window.hydTaskDetail = { open,','window.hydTaskDetail = { inputsHtml, open,')
    page.add_script_tag(content=source)
    view={'definition':{'activities':[{'id':'analysis','inputData':['sample']}],'data':[{'name':'sample','description':'시료'}]},
          'instance':{'variables_data':[{'key':'sample','value':'현재 시료'}]},
          'workitems':[{'id':'old','activity_id':'analysis','generation':0},{'id':'new','activity_id':'analysis','generation':1}]}
    page.evaluate("v=>{selectTab('instances');document.querySelector('#instDetail').innerHTML=hydTaskDetail.inputsHtml(v.workitems[0],{input_state:'current',inputs:{sample:'현재 시료'}},v)}",view)
    assert '이 회차가 받은 값은 저장되어 있지 않습니다' in page.locator('#instDetail').inner_text()
    assert '현재 시료' not in page.locator('#instDetail').inner_text()
    page.locator('#instDetail details').evaluate('e=>e.open=true')
    assert '현재 시료' in page.locator('#instDetail').inner_text()
    capture(page,'older-task-current-values')


def test_business_approval_context_uses_business_values_without_plant_forecast(page):
    page.add_script_tag(path=str(WWW/'plainWords.js'))
    page.add_script_tag(path=str(WWW/'approvalCard.js'))
    for code,facts,expected in [('PO_CREATE',{'part_no':'P-PMP-SEAL','need_qty':8,'po_amount':160,'lead_slack_days':2},'구매 요청'),
                                ('WO_CREATE',{'hours_since_pm':510,'pm_interval_h':500,'pm_due_in_h':-10,'spare_available':3},'정비 요청')]:
        opt={'id':'one','name':'추천 업무','kind':'work_order','score':1,'actions':[{'code':code,'name':expected}],'forecast':[{'variable':'ts1','value':40,'name':'유온','unit':'℃'}]}
        d={'options':[opt],'recommended':'one','facts':facts}
        html=page.evaluate('d=>hydApprove.html(d,"one",{})',d)
        assert f'aria-label="{expected}"' in html
        assert '40℃' not in html and '예측 유온' not in html
        page.evaluate("html=>{selectTab('instances');document.querySelector('#instDetail').innerHTML=html}",html)
        capture(page,'business-'+code.lower())

def test_kpi_explains_business_sources_without_internal_table_names(page):
    page.add_script_tag(path=str(WWW/'kpi.js'))
    measure={'id':'msr:revenue','name':'매출','status':'unavailable','unit':'ea','value':None,
             'reason':'production_orders.hour_value 는 계획 생산 가치, shipments 는 수량만 있고 단가가 없습니다',
             'definition':{'kind':'unavailable'}}
    rendered=page.evaluate('m=>hydKpi._card(m)',measure)
    assert '계획 시간당 생산 가치' in rendered and '대체 출하 기록' in rendered
    assert 'production_orders' not in rendered and 'shipments' not in rendered
    assert measure['reason'].startswith('production_orders.hour_value')


def test_ontology_uses_registered_flow_names_preserves_unknown_and_retries_failure(page):
    page.add_script_tag(content="function P(){return ''}")
    page.evaluate("selectTab('ontology')")
    page.route('**/api/ontology/graph?*',lambda r:r.fulfill(json={'nodes':[
        {'id':'alert_triage','name':'alert_triage','label':'Process'},
        {'id':'student_flow','name':'student_flow','label':'Process'},
        {'id':'old_test_unknown','name':'old_test_unknown','label':'Process'},
        {'id':'rule:known','name':'rule:known','label':'Rule','props':{'annotation':'실제 규칙 설명'}},
    ],'edges':[]}))
    page.route('**/api/ontology/patterns',lambda r:r.fulfill(json=[]))
    page.route('**/api/ontology/namespaces',lambda r:r.fulfill(json=[]))
    page.route('**/api/process/definitions',lambda r:r.fulfill(json=[
        {'id':'student_flow','name':'학생이 등록한 조회 흐름','version':'1.0','deployed':True}]))
    page.add_script_tag(path=str(WWW/'enterprise.js'))
    page.evaluate('loadGraph(true)')
    assert '미지원 경보 현장 검토' in page.locator('#ontoMap').inner_text()
    assert '학생이 등록한 조회 흐름' in page.locator('#ontoMap').inner_text()
    assert 'old_test_unknown' not in page.locator('#ontoMap').inner_text()
    assert '이름 미등록 흐름' in page.locator('#ontoMap').inner_text()
    page.locator('.o-node[data-id=old_test_unknown]').click()
    assert page.locator('#ontoNode h3').inner_text()=='이름 미등록 흐름'
    assert 'old_test_unknown' not in page.locator('#ontoNode').inner_text()
    page.locator('#ontoNode details').evaluate('e=>e.open=true')
    assert 'old_test_unknown' in page.locator('#ontoNode').inner_text()
    page.locator('.o-node[data-id=student_flow]').click()
    assert page.locator('#ontoNode h3').inner_text()=='학생이 등록한 조회 흐름'
    page.route('**/api/process/definitions',lambda r:r.fulfill(status=503,json={'detail':'정의 서비스 중단'}))
    page.evaluate('loadGraph(true)')
    assert '흐름 이름 조회 실패' in page.locator('#ontoStats').inner_text()
    assert '흐름 이름 확인 불가' in page.locator('#ontoMap').inner_text()
    page.route('**/api/process/definitions',lambda r:r.fulfill(json=[
        {'id':'student_flow','name':'바뀐 실제 등록 이름','version':'1.1','deployed':True}]))
    page.evaluate('loadGraph(true)')
    assert '조회 실패' not in page.locator('#ontoStats').inner_text()
    assert '바뀐 실제 등록 이름' in page.locator('#ontoMap').inner_text()


def test_flow_list_keeps_identifier_in_closed_details_only(page):
    page.route('**/api/flows/catalog',lambda r:r.fulfill(json={'roles':[],'agents':[],'parts':[]}))
    page.route('**/api/flows',lambda r:r.fulfill(json={'drafts':[],'versions':[
        {'id':'student_flow','name':'학생이 등록한 흐름','version':'1.0','registered_at':'2026-10-12T00:00:00Z'}]}))
    page.add_script_tag(path=str(WWW/'flows.js'))
    page.evaluate("selectTab('flows');hydFlows.mount(document.querySelector('#flowsView'))")
    page.locator('#flowList h3').wait_for()
    assert '학생이 등록한 흐름' in page.locator('#flowList').inner_text()
    assert 'student_flow' not in page.locator('#flowList').inner_text()
    page.locator('#flowList details').evaluate('e=>e.open=true')
    assert 'student_flow' in page.locator('#flowList').inner_text()
    assert page.locator('[data-start=student_flow]').count()==1
