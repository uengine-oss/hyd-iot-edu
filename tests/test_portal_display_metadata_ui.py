"""Display metadata contracts, using production Chromium renderers and raw folds."""
import json
import os
from pathlib import Path

from test_portal_remaining_ui import page, record_components, WWW
from test_portal_failure_states_ui import render_record, retain
from test_instance_mode import world
from test_failed_attempt_trace import failing_case, REPLY
from test_capstone_g3_mcp_extract import rows
from procsvc import instances
from procsvc import manual_preflight
from test_manual_preflight import catalog as manual_catalog, proposal as manual_proposal
import pytest


def test_codex_server_tool_alias_uses_same_display_contract_and_retains_raw(page):
    record_components(page)
    aliases = {
        'enterprise-maint/pm_status': '정비 계수기 · 계획 조회',
        'enterprise-maint/maintenance_windows': '정비 시간 계획 조회',
        'neo4j/read_neo4j_cypher': '지식 그래프 조회',
    }
    for raw, expected in aliases.items():
        assert page.evaluate('raw=>hydWords.toolName(raw)', raw) == expected
        assert page.evaluate('raw=>hydWords.toolName(raw)', 'mcp__'+raw.replace('/', '__')) == expected
    events = [{'id': 'tool', 'event_type': 'tool_usage_finished', 'data': {'tool': 'neo4j/read_neo4j_cypher', 'output': [], 'is_error': False}}]
    page.evaluate("""events=>{selectTab('instances');document.querySelector('#instDetail').innerHTML=
      '<div id="displayTrace" class="tr">'+hydTrace.rowsOf(events).map(r=>hydTrace.rowHtml(r,false)).join('')+'</div>';}
    """, events)
    assert 'neo4j/read_neo4j_cypher' not in page.locator('#displayTrace').inner_text()
    page.locator('#displayTrace summary').click()
    assert 'neo4j/read_neo4j_cypher' in page.locator('#displayTrace').inner_text()


@pytest.mark.parametrize('renderer', ['trace', 'record'])
def test_failed_calls_keep_each_exact_tool_identity_keyboard_accessible(page, world, renderer):
    rt, inst, calls = failing_case(world)
    wi = rows(rt, inst, 'T_check')[0]
    assert wi['status'] == 'PENDING' and len(calls) == instances.MAX_RETRIES
    record_components(page)
    if renderer == 'trace':
        page.evaluate("""events=>{selectTab('instances');document.querySelector('#instDetail').innerHTML=
          '<div id="displayTrace" class="tr">'+hydTrace.rowsOf(events).map(r=>hydTrace.rowHtml(r,false)).join('')+'</div>';}
        """, rt.repo.list_events(todo_id=wi['id']))
        selector = '#displayTrace'
    else:
        render_record(page, rt.instance_view(inst['proc_inst_id']))
        selector = '#instRecord'
        page.locator('#instRecord summary').filter(has_text='시스템 기록').click()
    panel = page.locator(selector)
    raw = 'mcp__gcal__get_event'
    folds = panel.locator('details.fold').filter(has=page.locator('summary', has_text='호출 도구 원문'))
    assert folds.count() == instances.MAX_RETRIES
    assert raw not in panel.inner_text()
    assert REPLY in panel.inner_text()
    provenance = 'Real memory-runtime failed attempts with an isolated MCP 503 response double; production Chromium renderer. No live service, worker, or stored operating record changed.'
    retain(page, 'failed-tool-identity-'+renderer+'-closed', selector, provenance, [REPLY, '호출 도구 원문'])
    for fold in folds.all():
        assert not fold.evaluate('e=>e.open')
        fold.locator(':scope > summary').focus()
        page.keyboard.press('Enter')
        assert fold.evaluate('e=>e.open')
        assert fold.locator('pre').inner_text() == raw
    assert panel.inner_text().count(raw) == instances.MAX_RETRIES
    assert REPLY in panel.inner_text()
    retain(page, 'failed-tool-identity-'+renderer+'-opened', selector, provenance, [REPLY, raw])


def test_skill_snapshot_title_and_historical_description_are_separate_from_slug(page):
    record_components(page)
    entries = [
        {'name': 'pm-schedule-planning', 'title': '정기 정비 계획', 'description': '정비 시간을 비교한다', 'path': '.agents/skills/pm-schedule-planning/SKILL.md', 'sha256': 'a'*64, 'delivery': 'prompt'},
        {'name': 'older-pm-planning', 'description': '당시 기록한 정비 계획 설명', 'path': '.claude/skills/older-pm-planning/SKILL.md', 'sha256': 'b'*64},
    ]
    view = {'instance': {'proc_inst_id': 'display', 'proc_inst_name': '스킬 이름 표시 시험', 'status': 'COMPLETED', 'variables_data': []},
            'definition': {'activities': [{'id': 'agent', 'name': '계획 제안'}]},
            'workitems': [{'id': 'w1', 'activity_id': 'agent', 'activity_name': '계획 제안', 'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE', 'status': 'DONE'}],
            'events': [{'id': 'started', 'todo_id': 'w1', 'event_type': 'task_started', 'data': {'skills': entries}}]}
    before = json.dumps(view, ensure_ascii=False, sort_keys=True)
    render_record(page, view)
    page.locator('#instRecord details').first.locator(':scope > summary').click()
    text = page.locator('#instRecord').inner_text()
    assert '정기 정비 계획' in text and '당시 기록한 정비 계획 설명' in text
    assert '당시 설명' in text
    assert 'pm-schedule-planning' not in text and 'older-pm-planning' not in text
    retain(page,'skill-display-metadata','#instRecord','Actual renderer with new title and preserved historical description; synthetic snapshots, no live changes.',['정기 정비 계획','당시 설명'])
    fold = page.locator('#instRecord details').filter(has_text='pm-schedule-planning').last
    fold.locator(':scope > summary').click()
    assert 'pm-schedule-planning' in page.locator('#instRecord').inner_text()
    assert json.dumps(view, ensure_ascii=False, sort_keys=True) == before


def test_tool_catalog_resolves_alias_without_calling_the_tool(page):
    page.route('**/api/agent-authoring/options', lambda route: route.fulfill(json={'servers': [{'name': 'student', 'description': '학생 업무 조회'}]}))
    page.route('**/api/mcp/selectable', lambda route: route.fulfill(json={'servers': [{'name': 'student', 'tools': [{'name': 'read_rows', 'title': '요청 자료 조회', 'tool_id': 'mcp__student__read_rows'}]}]}))
    requests = []
    page.on('request', lambda req: requests.append((req.method, req.url)))
    page.add_script_tag(path=str(WWW/'toolNames.js'))
    page.evaluate('hydToolNames.load()')
    name = page.evaluate('hydToolNames.resolve("student/read_rows")')
    assert name['name'] == '학생 업무 조회 · 요청 자료 조회'
    assert name['raw'] == 'student/read_rows'
    assert all(method == 'GET' for method, _ in requests)


def test_tool_name_lookup_error_is_distinct_from_missing_name_and_execution(page):
    record_components(page)
    page.route('**/api/agent-authoring/options',lambda r:r.fulfill(status=503,json={'detail':'이름 목록 연결 실패'}))
    page.route('**/api/mcp/selectable',lambda r:r.fulfill(json={'servers':[]}))
    page.add_script_tag(path=str(WWW/'toolNames.js'))
    page.evaluate('hydToolNames.load()')
    assert page.evaluate('UI.toolName("student/read_rows")')=='도구 표시 이름 읽기 실패'
    assert page.evaluate('hydToolNames.resolve("student/read_rows").state')=='error'
    events=[{'id':'done','event_type':'tool_usage_finished','data':{'tool':'student/read_rows','output':[],'is_error':False}}]
    assert page.evaluate('e=>hydTrace.rowsOf(e)[0].status',events)=='ok'
    page.route('**/api/agent-authoring/options',lambda r:r.fulfill(json={'servers':[]}))
    page.evaluate('hydToolNames.load(true)')
    assert page.evaluate('UI.toolName("student/read_rows")')=='도구 표시 이름 미등록'
    assert page.evaluate('hydToolNames.resolve("student/read_rows").raw')=='student/read_rows'


def test_mcp_titles_and_input_labels_preserve_original_call_keys(page):
    server={'name':'student-server','description':'학생 회의 자료','transport':'streamable_http','url':'http://student.invalid/mcp',
            'agents':[],'tasks':[],'origin':'user','editable':True,'selectable':True,'check':{'status':'ok'},'read_confirmed':[]}
    tool={'name':'read_rows','title':'회의 자료 조회','description':'등록한 회의 자료를 조회합니다','callable':True,'confirmable':True,
          'input_schema':{'type':'object','properties':{'meeting_id':{'type':'string','title':'회의 번호'}},'required':['meeting_id']}}
    calls=[]
    page.route('**/api/mcp/servers',lambda r:r.fulfill(json={'servers':[server]}))
    page.route('**/api/mcp/servers/student-server/tools?*',lambda r:r.fulfill(json={'status':'ok','tools':[tool],'server_info':{'name':'student-tool-runtime'},'elapsed_ms':2}))
    page.route('**/api/mcp/secrets',lambda r:r.fulfill(json={'items':[]}))
    def call(route):
        calls.append(route.request.post_data_json)
        route.fulfill(json={'status':'ok','elapsed_ms':2,'arguments':{'meeting_id':'M-2026-1'},'result':{'is_error':False,'size_chars':2,'text':'[]','truncated':False}})
    page.route('**/api/mcp/servers/student-server/tools/read_rows/call',call)
    page.add_script_tag(path=str(WWW/'mcp.js'))
    page.evaluate("selectTab('mcp');hydMcp.mount(document.querySelector('#mcpView'))")
    page.locator('#mcpServers [data-name="student-server"]').click()
    page.locator('[data-try="read_rows"]').click()
    text=page.locator('#mcpView').inner_text()
    assert '학생 회의 자료' in text and '회의 자료 조회' in text and '회의 번호' in text
    assert 'student-server' not in text and 'student-tool-runtime' not in text
    assert 'read_rows' not in text and 'meeting_id' not in text
    retain(page,'mcp-display-metadata','#mcpView','Independent saved server/tool metadata and intercepted POST; actual MCP UI, no external request.',['학생 회의 자료','회의 자료 조회','회의 번호'])
    page.locator('#mcpCall').click()
    assert '회의 번호: 필수 입력입니다' in page.locator('#mcpResult').inner_text()
    assert 'meeting_id' not in page.locator('#mcpResult').inner_text() and calls==[]
    page.locator('[data-key="meeting_id"]').fill('M-2026-1')
    page.locator('#mcpCall').click()
    page.wait_for_function("!document.querySelector('#mcpCall').disabled")
    assert calls[0]['arguments']=={'meeting_id':'M-2026-1'}
    assert len(calls)==1
    page.locator('#mcpView details').filter(has_text='student-server').first.locator(':scope > summary').click()
    assert 'student-server' in page.locator('#mcpView').inner_text()


def test_rule_and_method_identifiers_are_available_in_closed_raw_details(page):
    skill={'id':'skill:student-method','name':'학생 팬 점검','sopId':'SOP-STUDENT-99','kind':'work_order','description':'팬을 점검합니다','steps':[],
           'failureModes':[],'causes':[],'actions':[],'affects':[],'rules':[{'id':'rule:custom-student-limit','effect':'EXCLUDE'}]}
    page.route('**/api/kg/skills',lambda r:r.fulfill(json=[skill]))
    page.route('**/api/kg/catalog',lambda r:r.fulfill(json={'roles':[],'failureModes':[]}))
    page.add_script_tag(path=str(WWW/'hitl.js'))
    page.evaluate("selectTab('skills')")
    page.locator('#skillDetail #skName').wait_for()
    assert 'SOP-STUDENT-99' not in page.locator('#skillList').inner_text()
    text=page.locator('#skillDetail').inner_text()
    assert '규칙 표시 이름 미등록' in text
    assert 'rule:custom-student-limit' not in text and 'SOP-STUDENT-99' not in text
    retain(page,'rule-method-metadata','#skillDetail','Independent saved method/rule metadata; missing registered label shown explicitly, identifiers retained in native raw details.',['규칙 표시 이름 미등록'])
    raw=page.locator('#skillDetail details').filter(has_text='rule:custom-student-limit').last
    raw.locator(':scope > summary').focus()
    page.keyboard.press('Enter')
    assert 'rule:custom-student-limit' in page.locator('#skillDetail').inner_text()


@pytest.mark.parametrize('validation,expected',[
    ({'checked':True,'technical_ready':False,'needs_human_review':True,'can_commit':False,'issues':[{'code':'COMMAND_IN_WORK_ORDER','sop':'SOP-12','field':'steps','message':'정비 요청에 설비 명령이 들어 있습니다'}]},'수정할 항목 있음'),
    ({'checked':True,'technical_ready':True,'needs_human_review':True,'can_commit':False,'issues':[]},'기계 검사 통과'),
    ({'checked':True,'technical_ready':True,'needs_human_review':True,'can_commit':False,'issues':None},'검사 정보 읽기 실패'),
    (None,'기계 검사 결과가 없습니다'),
])
def test_manual_machine_check_does_not_claim_human_review_or_change_commit_guard(page,validation,expected):
    source=(WWW/'hitl.js').read_text(encoding='utf8')
    source=source.replace('function renderPreview() {','window.previewHarness={set:r=>{H.preview=r;renderPreview();}}; function renderPreview() {')
    page.add_script_tag(content=source)
    preview={'status':'READY','source_id':'saved-source','filename':'정비 원문.md','chars':30,'sections':[{'ref':'정비절','title':'팬 점검','excerpt':'보존 원문'}],
             'procedures':[{'id':'SOP-12','name':'팬 점검 요청','kind':'work_order','steps':[],'failure_mode':'fm:cooling-loss'}], 'warnings':[], 'validation':validation}
    page.evaluate("r=>{selectTab('knowledge');previewHarness.set(r)}",preview)
    text=page.locator('#manualResult').inner_text()
    assert expected in text
    if validation and validation['issues'] is not None:
        assert '검토 완료나 적재 승인이 아닙니다' in text
    if expected=='검사 정보 읽기 실패':
        assert '기계 검사 통과' not in text and '수정 항목은 없습니다' not in text
    assert page.locator('#manualCommit').is_enabled(), 'can_commit=false on a read check must not replace the existing human commit contract'
    assert not page.locator('#manualReviewed').is_checked()
    page.locator('#manualCommit').click()
    assert '원문을 대조하고 검토 완료를 표시하세요' in page.locator('#manualMsg').inner_text()
    name='manual-machine-check-'+('missing' if validation is None else 'malformed' if validation['issues'] is None else 'ready' if validation['technical_ready'] else 'issues')
    retain(page,name,'#manualResult','Independent proposal/validation records; actual hitl preview and unchanged unchecked-review commit guard. Not human approval or ingestion.',[expected])


@pytest.mark.parametrize('entry', ['stored-source', 'linked-method'])
def test_reopening_manual_source_is_get_only_and_keeps_review_unchecked(page, entry):
    preview={'status':'READY','source_id':'saved-source','document_id':'document-one','filename':'정비 원문.md','chars':30,
             'sections':[{'ref':'정비절','title':'팬 점검','excerpt':'보존 원문'}],
             'procedures':[{'id':'SOP-12','name':'팬 점검 요청','kind':'work_order','steps':[],'failure_mode':'fm:cooling-loss'}],
             'warnings':[], 'validation':{'checked':True,'technical_ready':True,'needs_human_review':True,'can_commit':False,'issues':[]}}
    calls=[]
    def source_preview(route):
        calls.append((route.request.method,route.request.post_data))
        route.fulfill(json=preview)
    page.route('**/api/kg/manuals/sources/saved-source/preview',source_preview)
    page.route('**/api/kg/manuals/sources?*',lambda r:r.fulfill(json={'total':1,'limit':20,'next_offset':None,'items':[{'source_id':'saved-source','filename':'정비 원문.md','status':'READY'}]}))
    page.route('**/api/kg/manuals',lambda r:r.fulfill(json=[]))
    page.route('**/api/kg/ingests',lambda r:r.fulfill(json=[]))
    page.route('**/api/kg/catalog',lambda r:r.fulfill(json={'roles':[],'failureModes':[]}))
    page.route('**/api/kg/skills',lambda r:r.fulfill(json=[{'id':'skill:sample','name':'팬 점검','revision':1,'kind':'work_order','source_id':'saved-source','source_document':'document-one'}]))
    page.add_script_tag(path=str(WWW/'hitl.js'))
    if entry == 'stored-source':
        page.evaluate("selectTab('knowledge')")
        page.locator('#manualSources > details > summary').click()
        page.locator('[data-manual-reopen="saved-source"]').click()
    else:
        page.evaluate("selectTab('skills')")
        page.locator('#skSource').click()
    page.locator('#manualReviewed').wait_for()
    assert calls == [('GET',None)]
    assert not page.locator('#manualReviewed').is_checked()
    assert page.locator('#manualDocumentId').input_value() == preview['document_id']
    page.locator('#manualResult summary').filter(has_text='절 본문 전체').focus()
    page.keyboard.press('Enter')
    assert '보존 원문' in page.locator('#manualResult').inner_text()
    assert '검토 완료나 적재 승인이 아닙니다' in page.locator('#manualResult').inner_text()


def test_preflight_uses_registered_names_and_keeps_all_warnings_and_issues_accessible(page, manual_catalog):
    preview = manual_proposal()
    preview.update(status='READY',source_id='saved-review',filename='검토 원문.md',chars=700,
                   sections=[{'ref':'검토절','title':'검토 범위','excerpt':'원문 보존'}],
                   warnings=[f'원문 대조 경고 {n}: '+('제안 내용을 확인하세요. '*18) for n in range(1,24)],
                   knowledge_conflicts=[{'id':'fm:pump'},{'id':'cause:student-registered'},{'id':'cause:student-unlabeled'}])
    preview['procedures'][0]['name']='계획 정지 검토'
    manual_catalog['failure_modes'][0]['name']='현장 펌프 효율 저하'
    manual_catalog['causes']=[{'id':'cause:student-registered','name':'필터 통과 입자 유입'}]
    manual_catalog['actions'][0]['name']='설비 정지'
    preview['validation']=manual_preflight.validate(preview,manual_catalog)
    original=json.dumps(preview,ensure_ascii=False,sort_keys=True)
    source=(WWW/'hitl.js').read_text(encoding='utf8').replace('function renderPreview() {',
        'window.reviewHarness={set:(r,c)=>{H.preview=r;H.catalog=c;renderPreview();}}; function renderPreview() {')
    page.add_script_tag(content=source)
    page.evaluate("x=>{selectTab('knowledge');window.reviewOriginal=JSON.stringify(x);reviewHarness.set(x.preview,x.catalog);window.reviewInput=x;}",{'preview':preview,'catalog':manual_catalog})
    panel=page.locator('#manualResult')
    text=panel.inner_text()
    assert '현장 펌프 효율 저하' in text and '필터 통과 입자 유입' in text
    assert '원인 표시 이름 미등록' in text
    assert '계획 정지 검토 (SOP-PM-12)' in text
    assert '원자 조치 1' in text and '설비 제어' in text
    for raw in ('fm:pump','cause:student-registered','cause:student-unlabeled','COMMAND_IN_WORK_ORDER','link.actions'):
        assert raw not in text
    assert '추출 경고 23개' in text and '원문과 대조' in text
    assert preview['warnings'][0] not in text and preview['warnings'][-1] not in text
    assert not page.locator('#manualReviewed').is_checked()
    retain(page,'preflight-names-warnings-closed','#manualResult','Actual read-only backend preflight over an independent saved-review fixture and real catalog labels; production Chromium renderer, no operating source changed.',
           ['현장 펌프 효율 저하','필터 통과 입자 유입','원인 표시 이름 미등록','추출 경고 23개'])
    warnings=panel.locator('details').filter(has=page.locator('summary',has_text='추출 경고 원문 23개'))
    warnings.locator(':scope > summary').focus()
    page.keyboard.press('Enter')
    assert warnings.locator('li').all_text_contents() == preview['warnings']
    issues=panel.locator('details').filter(has=page.locator('summary',has_text='검사 항목 원문'))
    assert issues.count()==len(preview['validation']['issues'])
    for fold, expected in zip(issues.all(),preview['validation']['issues']):
        fold.locator(':scope > summary').focus()
        page.keyboard.press('Enter')
        assert json.loads(fold.locator('pre').inner_text()) == expected
    assert page.evaluate('JSON.stringify(reviewInput)===reviewOriginal')
    assert json.dumps(preview,ensure_ascii=False,sort_keys=True)==original
    assert not page.locator('#manualReviewed').is_checked()


def test_saved_pm_extraction_preflight_uses_proposal_knowledge_names(page, manual_catalog):
    # 실제 워커 추출 저장본의 고정본(손질 내역: tests/fixtures/manual-extraction-proposals/README.md)
    path=Path(__file__).resolve().parent/'fixtures/manual-extraction-proposals/proposal-PM-02.json'
    preview=json.loads(path.read_text(encoding='utf8'))['preview']
    original=json.dumps(preview,ensure_ascii=False,sort_keys=True)
    preview['validation']=manual_preflight.validate(preview,manual_catalog)
    source=(WWW/'hitl.js').read_text(encoding='utf8').replace('function renderPreview() {',
        'window.reviewHarness={set:(r,c)=>{H.preview=r;H.catalog=c;renderPreview();}}; function renderPreview() {')
    page.add_script_tag(content=source)
    page.evaluate("x=>{selectTab('knowledge');reviewHarness.set(x.preview,x.catalog);}",{'preview':preview,'catalog':manual_catalog})
    text=page.locator('#manualResult').inner_text()
    for row in preview['knowledge']['failure_modes']+preview['knowledge']['causes']:
        assert row['name'] in text
        assert row['id'] not in text
    assert preview['warnings'][0] not in text
    assert not page.locator('#manualReviewed').is_checked()
    retain(page,'saved-pm-preflight-names','#manualResult','Read-only browser replay of fixtures/manual-extraction-proposals/proposal-PM-02.json (saved actual extraction) with independent catalog preflight; original extraction retained. Not a current live database check or human approval.',
           ['펌프 체적 효율 저하','작동유 오염','추출 경고'])
    preview.pop('validation')
    assert json.dumps(preview,ensure_ascii=False,sort_keys=True)==original


def test_business_start_waits_for_status_before_success_and_updates_visible_state(page):
    source=(WWW/'app.js').read_text(encoding='utf8')
    business='const EXPERIMENT = {'+source.split('const EXPERIMENT = {')[1].split("$('#btnReset').addEventListener")[0]
    units='const FAULT_LABEL'+source.split('const FAULT_LABEL')[1].split('/* C3 B')[0]
    page.add_script_tag(content='function refreshFast(){};\n'+business+units)
    unit={'tags':{'TS1':40,'TS3':30,'CE':90,'FanSpeedSP':60,'LoadSP':70,'EPS1':2,'PS1':100},
          'status':{'mode':'REMOTE_AUTO','state':'RUN'}}
    page.evaluate("u=>{state.plant={units:{'HYD-02':u}};state.det={};state.incidents=[];state.biz={failed:'직전 읽기 실패'};selectTab('scenario');renderUnits();}",unit)
    pending=[]
    page.route('**/api/scenario/status',lambda r:pending.append(r))
    page.route('**/api/scenario/B/start',lambda r:r.fulfill(json={'evidence':{'hours_since_pm':500},'reanchored':False}))
    with page.expect_request(lambda r:r.method=='GET' and r.url.endswith('/api/scenario/status')):
        page.locator('#units [data-act="biz-start"]').click()
    assert page.locator('#scenarioMsg').inner_text()=='HYD-02 처리 중…'
    assert len(pending)==1
    assert '표시를 읽지 못함' in page.locator('#units .biz-alert').inner_text()
    pending[0].fulfill(json={'scenarios':{'B':{'title':'정기 점검','running':{'instance':'independent-running-case'}}}})
    page.wait_for_function("document.querySelector('#scenarioMsg').textContent.includes('시나리오 시각 기준점은 그대로')")
    assert '정기 점검 처리 중' in page.locator('#units .biz-alert').inner_text()
    assert '표시를 읽지 못함' not in page.locator('#units .biz-alert').inner_text()
    assert '처리 건 시작' in page.locator('#scenarioMsg').inner_text()


def test_saved_actual_b_record_uses_historical_metadata_without_changing_source(page):
    path=os.getenv('PORTAL_SAVED_B_VIEW')
    if not path:
        pytest.skip('Saved actual B evidence is supplied only for the explicit display audit; other CI tests use independent records.')
    view=json.loads(Path(path).read_text(encoding='utf8'))
    assert view['instance']['status']=='RUNNING'
    record_components(page)
    page.evaluate("""v=>{
      window.savedBView=v;window.savedBOriginal=JSON.stringify(v);
      const m=hydRecord.build(v,{agents:[],people:[]});selectTab('instances');
      document.querySelector('#instDetail').innerHTML='<div id="instRecord" class="cr"></div>';
      const host=document.querySelector('#instRecord');hydRecord.mount(host);
      host.innerHTML=m.steps.map((s,i)=>'<section class="cr-step open">'+hydRecord.stepHtml(s,i,m.steps.length,true)+'</section>').join('');
    }""",view)
    for summary in page.locator('#instRecord details[data-open-default] > summary').all():
        summary.focus()
        page.keyboard.press('Enter')
    text=page.locator('#instRecord').inner_text()
    for raw in ('pm-schedule-planning','enterprise-maint/pm_status','neo4j/read_neo4j_cypher','codex/list_mcp_resources'):
        assert raw not in text
    assert '당시 설명' in text and '프롬프트로 본문 전달' in text
    assert page.evaluate('JSON.stringify(savedBView)===savedBOriginal')
    assert page.evaluate('savedBView.instance.status')=='RUNNING'
    retain(page,'saved-actual-b-record','#instRecord',
           'Read-only browser replay of skill-delivery-approved/before.json from actual B. Saved input unchanged; no live HTTP calls, CLI run, or task completion.',
           ['당시 설명','프롬프트로 본문 전달'])


def test_business_chip_returns_to_due_after_reset_following_a_rejection(page):
    """2026-10-25 수업 한 바퀴(final3 · 92): B 를 거절(반려)한 뒤 [초기화]를 눌러도 카드 머리 표시가 「반려」로 남았다."""
    source=(WWW/'app.js').read_text(encoding='utf8')
    business='const EXPERIMENT = {'+source.split('const EXPERIMENT = {')[1].split("$('#btnReset').addEventListener")[0]
    page.add_script_tag(content='function refreshFast(){};\n'+business)
    last={'instance':'c3_pm.x','status':'COMPLETED','ended_at':'2026-10-25T22:00:00Z','outcome':'반려'}
    b={'label':'정기 점검 도래','title':'정기 정비','alert':True,'facts':{},'running':None,'last':last}
    html=lambda presses: page.evaluate("([b,p])=>{state.biz={scenarios:{B:b},presses:p};return bizAlertHtml('HYD-02');}",[b,presses])
    assert '반려' in html({'HYD-02':{'button':'정기 점검','at':'2026-10-25T21:59:00Z'}})          # 거절 직후: 결과를 보인다
    after=html({'HYD-02':{'button':'초기화','at':'2026-10-25T22:01:00Z'}})
    assert '정기 점검 도래' in after and '반려' not in after                                     # 거절 뒤 [초기화]: 다시 도래
