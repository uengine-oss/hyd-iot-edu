"""Visible failure states, using the existing real Chromium/product harnesses.

These are isolated HTTP injections and synthetic historical records, not live
production incidents. No renderer or API expectation is replaced. Set
PORTAL_FAILURE_EVIDENCE to retain screenshots and their provenance/visible text.
"""
import json
import os
from pathlib import Path
import pytest

from test_portal_remaining_ui import page, record_components, WWW
from test_portal_approval_ui import browser, world, approval_clock, Portal
from test_instance_mode import _row


def retain(page, name, selector, provenance, expected):
    folder = os.getenv('PORTAL_FAILURE_EVIDENCE')
    for width in (1440, 1024):
        page.set_viewport_size({'width': width, 'height': 1000})
        panel = page.locator(selector)
        assert panel.is_visible()
        text = panel.inner_text()
        for phrase in expected:
            assert phrase in text, text
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        if folder:
            dest = Path(folder)
            dest.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(dest / f'{name}-{width}.png'), full_page=True)
            panel.screenshot(path=str(dest / f'{name}-{width}-panel.png'))
            (dest / f'{name}-{width}.json').write_text(json.dumps({
                'name': name, 'width': width, 'provenance': provenance,
                'selector': selector, 'visible_text': text, 'expected': expected,
                'document_overflow': False,
            }, ensure_ascii=False, indent=2), encoding='utf8')


def open_record_folds(page):
    folds = page.locator('#instRecord details')
    for i in range(folds.count()):
        for checkbox in page.locator('#instRecord input[type="checkbox"]').all():
            if checkbox.is_visible() and not checkbox.is_checked():
                checkbox.focus()
                page.keyboard.press('Space')
                assert checkbox.is_checked()
        fold = folds.nth(i)
        if not fold.evaluate('e=>e.open'):
            fold.locator(':scope > summary').focus()
            page.keyboard.press('Enter')
            assert fold.evaluate('e=>e.open')
    return folds


def render_record(page, view, ext=None):
    page.evaluate("""x=>{
      const m=hydRecord.build(x.view,x.ext || {agents:[],people:[]});selectTab('instances');
      document.querySelector('#instDetail').innerHTML='<div id="instRecord" class="cr"></div>';
      const host=document.querySelector('#instRecord');hydRecord.mount(host);
      host.innerHTML=m.steps.map((s,i)=>'<section class="cr-step open">'+
        hydRecord.stepHtml(s,i,m.steps.length,true)+'</section>').join('');
    }""", {'view': view, 'ext': ext})


def test_record_failure_reasons_are_visible_in_open_steps(page):
    record_components(page)
    view = {
        'instance': {'proc_inst_id': 'case', 'proc_inst_name': '팬 점검 기록 시험', 'status': 'COMPLETED',
                     'variables_data': [{'key': 'incident', 'value': 'INC1'}, {'key': 'recovered', 'value': False}]},
        'definition': {'activities': [{'id': 'agent', 'name': '분석'}, {'id': 'check', 'name': '효과 확인'}]},
        'workitems': [
            {'id': 'w1', 'activity_id': 'agent', 'activity_name': '분석', 'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE', 'status': 'DONE'},
            {'id': 'w2', 'activity_id': 'check', 'activity_name': '효과 확인', 'agent_orch': 'system', 'tool': 'incident:reobserve', 'status': 'DONE', 'output': {'recovered': False}},
        ],
        'events': [{'id': 'provided', 'todo_id': 'w1', 'event_type': 'task_started',
                    'data': {'skills': [{'name': '팬 점검', 'written': False, 'error': '권한 거부'}]}}],
    }
    ext = {'agents': [], 'people': [], 'incident': {'reobsSeries': {'error': '센서 기록 연결 실패'}, 'history': []}}
    render_record(page, view, ext)
    folds = open_record_folds(page)
    text = page.locator('#instRecord').inner_text()
    assert '작업 폴더에는 있었지만' not in text
    assert '실행 시작 때 작업 폴더에 넣은 본문' not in text
    assert ' · 안 읽음' not in text
    retain(page, 'record-observation-and-skill-failure', '#instRecord',
           'Existing missing-skill/reobs fixture records; actual caseRecord.build/stepHtml rendered in the existing Chromium host.',
           ['작업 폴더에 못 넣음', '권한 거부', '값 흐름을 읽지 못했습니다', '센서 기록 연결 실패'])
    # Opening the real details is keyboard accessible; failure reasons must not
    # become success labels or disappear when the student opens another fold.
    if folds.count():
        summary = folds.first.locator(':scope > summary')
        summary.focus()
        before = folds.first.evaluate('e=>e.open')
        page.keyboard.press('Enter')
        assert folds.first.evaluate('e=>e.open') != before


@pytest.mark.parametrize('kind', ['file', 'prompt', 'unknown', 'invalid_delivery', 'missing', 'empty'])
def test_skill_delivery_and_read_evidence_are_distinct(page, tmp_path, kind):
    from worker import workspace, events
    from worker.runner import _provided_skills
    from worker.skill_context import inline_skills
    from test_codex_skill_context import SKILL
    record_components(page)
    entries = []
    if kind in ('file', 'prompt'):
        provider = 'codex' if kind == 'prompt' else 'claude-code'
        ws = workspace.for_run(tmp_path, 'delivery', tenant_id='hyd')
        workspace.provision(ws, agent_id=provider, constitution='', schema_prompt='', task={}, skills=[SKILL])
        entries = _provided_skills(ws, [SKILL], provider, activity_skills=[])
        if kind == 'prompt':
            body = inline_skills(ws, [SKILL], entries, provider)
            assert '<registered-skill>' in body and entries[0]['verified_registered_content']
    elif kind == 'unknown':
        entries = [{'name': '옛 기록의 스킬'}]
    elif kind == 'invalid_delivery':
        entries = [{'name': '잘못된 전달 값', 'path': '.claude/skills/sample/SKILL.md', 'sha256': 'a'*64, 'delivery': ''}]
    data = {} if kind == 'missing' else {'skills': entries}
    evs = [{'id': 'started', 'todo_id': 'w1', 'event_type': 'task_started', 'data': data}]
    if entries and kind in ('file', 'prompt'):
        evs.append({'id': 'provided', 'todo_id': 'w1', 'event_type': 'task_working',
                    'data': events.skills_provided(entries, cli=provider, missing=[]).as_dict()})
    view = {'instance': {'proc_inst_id': 'delivery', 'proc_inst_name': '스킬 전달 기록 시험', 'status': 'COMPLETED', 'variables_data': []},
            'definition': {'activities': [{'id': 'agent', 'name': '업무 분석'}]},
            'workitems': [{'id': 'w1', 'activity_id': 'agent', 'activity_name': '업무 분석', 'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE', 'status': 'DONE'}],
            'events': evs}
    render_record(page, view)
    open_record_folds(page)
    expected = {
        'file': ['파일 전달', '파일 읽기 기록 없음'],
        'prompt': ['프롬프트로 본문 전달', '파일 읽기 없이', '업무에 적용했는지는'],
        'unknown': ['전달 상태 기록 없음'],
        'invalid_delivery': ['전달 상태 기록 없음'],
        'missing': ['스킬 전달 기록이 없습니다'],
        'empty': ['제공된 스킬 없음'],
    }[kind]
    text = page.locator('#instRecord').inner_text()
    assert ' · 안 읽음' not in text and '열어 보지 않았습니다' not in text
    assert '받은 일 지시문만 따랐습니다' not in text
    retain(page, 'skill-delivery-' + kind, '#instRecord',
           'Actual workspace/_provided_skills/inline_skills metadata for file/prompt; explicit historical missing metadata for other cases. Isolated Chromium rendering, no external CLI run.', expected)


def test_skill_delivery_event_does_not_describe_failed_files_as_delivered():
    from worker.events import skills_provided
    entries = [
        {'name': '파일 성공', 'path': '.claude/skills/ok/SKILL.md', 'sha256': 'a'*64},
        {'name': '파일 실패', 'written': False, 'error': '권한 거부'},
        {'name': '본문 전달', 'delivery': 'prompt', 'verified_registered_content': True},
        {'name': '옛 상태'},
    ]
    data = skills_provided(entries, cli='codex', missing=['본문 없음']).data
    assert data['skills'] == entries and data['missing'] == ['본문 없음']
    assert '4개를 작업 폴더에 넣고' not in data['content']
    for phrase in ('파일 전달 1개', '프롬프트로 본문 전달 1개', '전달 실패 1개', '전달 상태 기록 없음 1개', '권한 거부', '본문 없음'):
        assert phrase in data['content']


def test_later_failed_read_request_preserves_each_delivery_snapshot(page, tmp_path):
    from cliagents import ExecEvent, ExecEventKind
    from worker import workspace, events
    from worker.runner import _provided_skills
    from worker.skill_context import inline_skills
    from test_codex_skill_context import SKILL
    record_components(page)
    first = workspace.for_run(tmp_path, 'first', tenant_id='hyd')
    failed = _provided_skills(first, [SKILL], 'claude-code', activity_skills=[])
    assert failed[0]['written'] is False
    second = workspace.for_run(tmp_path, 'second', tenant_id='hyd')
    updated = dict(SKILL, content=SKILL['content']+'\n추가 확인 조건\n')
    workspace.provision(second, agent_id='codex', constitution='', schema_prompt='', task={}, skills=[updated])
    prompt = _provided_skills(second, [updated], 'codex', activity_skills=[])
    inline_skills(second, [updated], prompt, 'codex')
    assert failed[0]['sha256'] != prompt[0]['sha256'] and 'written' not in prompt[0]
    call = ExecEvent(kind=ExecEventKind.TOOL_START, tool='Read', tool_input={'file_path': prompt[0]['path']}, tool_use_id='read2')
    request = events.SkillReads(prompt).on_tool_start(call)[0]
    assert request.data['known'] is True
    assert '읽기를 요청했습니다' in request.data['content'] and '읽었습니다' not in request.data['content']
    evs = []
    for number, entries in ((1, failed), (2, prompt)):
        job = f'run-{number}'
        evs.extend([
            {'id': f'p{number}', 'todo_id': 'w1', 'job_id': job, 'event_type': 'task_working', 'data': events.skills_provided(entries, cli='codex', missing=[]).as_dict()},
            {'id': f's{number}', 'todo_id': 'w1', 'job_id': job, 'event_type': 'task_started', 'data': {'skills': entries}},
        ])
    evs.extend([
        {'id': 'read-start', 'todo_id': 'w1', 'job_id': 'run-2', 'event_type': 'tool_usage_started', 'data': {'tool': 'Read', 'tool_use_id': 'read2', 'input': call.tool_input}},
        {'id': 'request', 'todo_id': 'w1', 'job_id': 'run-2', 'event_type': 'task_working', 'data': request.as_dict()},
        {'id': 'read-failed', 'todo_id': 'w1', 'job_id': 'run-2', 'event_type': 'tool_usage_finished', 'data': {'tool': 'Read', 'tool_use_id': 'read2', 'is_error': True, 'output': '권한 거부'}},
    ])
    view = {'instance': {'proc_inst_id': 'rounds', 'proc_inst_name': '스킬 전달 회차 시험', 'status': 'COMPLETED', 'variables_data': []},
            'definition': {'activities': [{'id': 'agent', 'name': '업무 분석'}]},
            'workitems': [{'id': 'w1', 'activity_id': 'agent', 'activity_name': '업무 분석', 'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE', 'status': 'DONE'}],
            'events': evs}
    render_record(page, view)
    open_record_folds(page)
    tables = page.locator('#instRecord .cr-table')
    assert '작업 폴더에 못 넣음' in tables.nth(0).inner_text()
    assert '프롬프트로 본문 전달' in tables.nth(1).inner_text()
    assert tables.nth(0).locator('.cr-ver').get_attribute('title') == failed[0]['sha256']
    assert tables.nth(1).locator('.cr-ver').get_attribute('title') == prompt[0]['sha256']
    rows = page.evaluate('evs=>hydTrace.rowsOf(evs)', evs)
    requested = next(r for r in rows if r['key'] == 'w:request')
    assert requested['status'] == 'idle' and '읽기 성공 여부' in requested['text']
    assert 'Read' not in requested['text'] and requested['raw']['via'] == 'Read'
    # 2026-10-23 갱신: 도구 행 키가 tool_use_id 하나에서 [proc_inst_id,todo_id,job_id,tool_use_id] 4값 키로 바뀜(ui.js toolCallKey, 실행마다 id 재사용 결함 수정)
    assert next(r for r in rows if r['key'] == 'tool:' + json.dumps([None, 'w1', 'run-2', 'read2'], separators=(',', ':')))['status'] == 'fail'
    retain(page, 'skill-rounds-and-failed-read', '#instRecord',
           'Actual missing-file metadata in first workspace; changed/verified Codex prompt body in second workspace; real SkillReads TOOL_START followed by synthetic denied tool response.',
           ['실행 1', '실행 2', '파일 읽기 요청 1건', '읽기 성공을 뜻하지 않습니다', '권한 거부'])


def test_failed_attempt_and_extracted_values_are_visible_as_failures(page):
    record_components(page)
    events = [
        {'id': 'e1', 'event_type': 'tool_usage_finished', 'data': {'tool': 'mcp__enterprise__erp_inventory', 'output': {'available': 3}, 'attempt_failed': True}},
        {'id': 'e2', 'event_type': 'task_working', 'job_id': 'MCP_RESULT_VALUES', 'data': {'name': 'MCP 결과에서 값을 꺼냄', 'values': {'available': 3}, 'attempt_failed': True}},
    ]
    data = page.evaluate('events=>({record:hydRecord.rowsOf(events),trace:hydTrace.rowsOf(events)})', events)
    assert data['record'][0]['status'] == data['trace'][0]['status'] == 'fail'
    assert data['trace'][1]['status'] == 'fail'
    page.evaluate("""x=>{
      selectTab('instances');
      document.querySelector('#instDetail').innerHTML='<div id="failureTrace" class="tr">'+
        x.trace.map(r=>hydTrace.rowHtml(r,false)).join('')+'</div><div id="failureValues" class="cr">'+
        hydRecord.sysDetail(x.record[1])+'</div>';
    }""", data)
    assert page.locator('#failureTrace .tr-row.fail').count() == 2
    summary = page.locator('#failureTrace details.tr-tool > summary')
    summary.focus()
    page.keyboard.press('Enter')
    assert page.locator('#failureTrace details.tr-tool').evaluate('e=>e.open')
    assert '3' in page.locator('#failureTrace .tr-io').inner_text()
    retain(page, 'attempt-failed-and-mcp-values', '#instDetail',
           'Existing synthetic attempt_failed/MCP_RESULT_VALUES records; actual trace rows, keyboard-open response, and caseRecord value detail.',
           ['실패한 시도', '가용 재고', '3'])


def test_instance_list_http_failure_is_visible_and_recovers(browser, world):
    p = Portal(browser, world, 'c3_pm')
    try:
        assert p.page.locator('#instList .item').count() >= 1
        p.page.route('**/api/instances?*', lambda route: route.fulfill(status=503, json={'detail': '처리 건 저장소 연결 실패'}))
        p.page.evaluate('hydInstances.load(true)')
        retain(p.page, 'instance-list-http-503', '#instList',
               'Independent browser HTTP 503 injection on /api/instances?limit=50; other requests use real FastAPI TestClient/MemoryRepo.',
               ['처리 건 목록을 읽지 못했습니다', '처리 건 저장소 연결 실패'])
        assert '아직 처리 건이 없습니다' not in p.page.locator('#instList').inner_text()
        p.page.unroute('**/api/instances?*')
        p.page.evaluate('hydInstances.load(true)')
        assert p.page.locator('#instList .item').count() >= 1
        assert '읽지 못했습니다' not in p.page.locator('#instList').inner_text()
        assert not p.errors
    finally:
        p.close()


def test_app_business_status_loading_failure_and_anchor_message(page):
    source = (WWW / 'app.js').read_text(encoding='utf8')
    # Reuse the real app functions in the existing component harness. Plant
    # inputs and HTTP replies are explicitly synthetic, with no live requests.
    business = 'const EXPERIMENT = {' + source.split('const EXPERIMENT = {')[1].split("$('#btnReset').addEventListener")[0]
    units = 'const FAULT_LABEL' + source.split('const FAULT_LABEL')[1].split('/* C3 B')[0]
    page.add_script_tag(content='function refreshFast(){};\n' + business + units)
    unit = {'tags': {'TS1': 40, 'TS3': 30, 'CE': 90, 'FanSpeedSP': 60, 'LoadSP': 70, 'EPS1': 2, 'PS1': 100},
            'status': {'mode': 'REMOTE_AUTO', 'state': 'RUN'}}
    page.evaluate("""u=>{state.plant={units:{'HYD-02':u}};state.det={};state.incidents=[];state.biz=undefined;
      selectTab('scenario');renderUnits();}""", unit)
    retain(page, 'app-business-loading', '#units', 'Synthetic plant unit; actual app renderUnits/bizAlertHtml with status not yet read.', ['표시 확인 중'])
    page.route('**/api/scenario/status', lambda route: route.fulfill(status=503, json={'detail': '업무 상태 서비스 연결 실패'}))
    page.evaluate('async()=>{await refreshBiz();renderUnits();}')
    assert '업무 상태 서비스 연결 실패' in page.locator('#units .biz-alert .tone-danger').get_attribute('title')
    retain(page, 'app-business-unreadable', '#units', 'Independent HTTP 503 /api/scenario/status; actual refreshBiz error path and renderUnits.', ['표시를 읽지 못함'])
    page.route('**/api/scenario/status', lambda route: route.fulfill(json={'scenarios': {
        'B': {'title': '정기 점검', 'running': {'instance': 'synthetic-running-case'}},
    }}))
    page.route('**/api/scenario/B/start', lambda route: route.fulfill(json={'evidence': {'hours_since_pm': 500}, 'reanchored': False}))
    page.locator('#units [data-act="biz-start"]').click()
    page.wait_for_function("document.querySelector('#scenarioMsg').textContent.includes('시나리오 시각 기준점은 그대로')")
    # Background plant polling is outside this component harness. Render the
    # completed status read explicitly before preserving the resulting screen.
    page.evaluate('renderUnits()')
    assert '정기 점검 처리 중' in page.locator('#units .biz-alert').inner_text()
    assert '표시를 읽지 못함' not in page.locator('#units .biz-alert').inner_text()
    retain(page, 'app-business-anchor-retained', '#scenarioMsg',
           'Synthetic POST reply reanchored=false; actual unitAction/anchorNote/logLine/scenarioMessage; no live scenario mutation.',
           ['시나리오 시각 기준점은 그대로', '진행 중인 처리 건이 있음'])


def test_authorized_approval_screen_after_real_role_denial(browser, world):
    p = Portal(browser, world, 'c3_pm')
    try:
        p.page.locator('#tdReason').fill('생산 일정을 확인하고 승인합니다.')
        p.page.locator('#tdRole').select_option('role:operator')
        with p.page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/select')) as denied:
            p.page.locator('#tdGo').click()
        p.settle()
        assert denied.value.status == 403
        assert _row(p.rt, p.inst, 'T_approve')['status'] == 'IN_PROGRESS'
        assert not p.out.calls and not p.out.mails and not world['executed']
        retain(p.page, 'approval-role-denied', '#todoPanel',
               'Real FastAPI/MemoryRepo authorization returns 403 for role:operator; role selector is not login authentication.', ['권한'])
        assert p.page.locator('#tdReason').input_value() == '생산 일정을 확인하고 승인합니다.'
        p.page.locator('#tdRole').select_option('role:prod-mgr')
        with p.page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/select')) as approved:
            p.page.locator('#tdGo').click()
        p.settle()
        assert approved.value.status == 200
        assert _row(p.rt, p.inst, 'T_approve')['output']['approval'] == '승인'
        assert p.out.calls
        p.page.locator('[data-inst-tab="record"]').click()
        retain(p.page, 'approval-role-accepted-record', '#instRecord',
               'Real FastAPI/MemoryRepo role:prod-mgr approval and outside-system doubles; approval record after 200. Not production auth or execution.',
               ['승인', '생산 일정을 확인하고 승인합니다.'])
        assert not p.errors
    finally:
        p.close()
