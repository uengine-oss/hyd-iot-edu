"""처리 건 화면(it/portal/www/instances.js) — 머리 요약 칸의 셈. node 에서 실제 화면 모듈을 싣고 부른다(www_node).
instances.js 는 실릴 때 화면 요소를 찾으므로 브라우저 쪽만 최소 대역(어떤 요소든 같은 빈 요소, 바깥 요청 실패)으로 둔다."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served
from www_node import run

# 브라우저 대역(test_www_enterprise 와 같은 꼴): 어떤 요소를 찾아도 같은 빈 요소, 바깥 요청은 실패. 화면 모듈 코드는 그대로 돈다
PRELUDE = r"""
const __fakeNode = () => new Proxy({ addEventListener() {}, append() {}, querySelector: () => __fakeNode(), querySelectorAll: () => [], classList: { toggle() {}, add() {} },
  dataset: {}, style: {}, value: '', innerHTML: '' }, { get: (t, k) => k in t ? t[k] : () => __fakeNode() });
globalThis.document = { getElementById: __fakeNode, querySelector: __fakeNode, querySelectorAll: () => [], createElement: __fakeNode, readyState: 'complete', addEventListener() {} };
globalThis.$ = () => __fakeNode(); globalThis.el = __fakeNode; globalThis.state = { tab: 'main' }; globalThis.selectTab = () => {};
globalThis.hydTabs = { onShow() {} }; globalThis.getJ = () => Promise.reject(new Error('대역')); globalThis.postJ = globalThis.getJ;
globalThis.keyboardItem = () => {}; globalThis.ResizeObserver = class { observe() {} }; globalThis.CSS = { escape: s => s }; globalThis.fmt = v => String(v); globalThis.API = { agent: '', process: '', ent: '' };
"""

FILES = ['ui.js', 'plainWords.js', 'instances.js']
STUCK = {'state': 'stuck', 'label': '멈춤 — 사람 조치 필요', 'steps': ['원인 진단']}


def test_사람_조치를_기다리며_멈춘_처리_건은_진행_중에_세지_않고_멈춤으로_따로_센다():
    """FA1 검증 H-10: 서버는 멈춘 처리 건에 attention 을 싣는데 화면은 읽지 않고 상단 「진행 중」에 RUNNING 을 그대로 셌다."""
    rows = [{'proc_inst_id': 'a', 'status': 'RUNNING', 'attention': None}, {'proc_inst_id': 'b', 'status': 'RUNNING', 'attention': STUCK},
            {'proc_inst_id': 'c', 'status': 'COMPLETED', 'attention': None}]
    got = run(FILES, "const c = hydInstances.counts(DATA); out([c.running, c.stuck.map(x => x.proc_inst_id), c.stuck[0].attention.label])", rows, prelude=PRELUDE)
    assert got == [1, ['b'], '멈춤 — 사람 조치 필요']


def test_사람이_맡는_역할이_없는_흐름의_다시_수행은_폼을_내지_않고_까닭만_말한다():
    """한 바퀴 44: 질문 건의 [다시 수행]이 「새 차수를 요청할 수 있습니다.」와 「이 흐름에는 사람이 맡는 역할이 없어 다시 수행을 요청할 수 없습니다.」를
    함께 내고 사유 칸 · 요청 단추까지 그렸다. 할 수 없으면 폼을 내지 않는다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    preview = {'start_workitem': 'w1', 'affected_workitems': ['w1'], 'cancel_workitems': [], 'invalidated_variables': [], 'restored_input_variables': [], 'retained_outputs': [],
               'reasons': {}, 'blockers': [], 'effects': None, 'request_roles': [], 'execution_available': True, 'snapshot_token': 't'}

    def answer(route):
        url = route.request.url
        if '/rework-preview' in url:
            return route.fulfill(json=preview)
        if url.split('?')[0].endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            page.wait_for_function('() => window.hydRework && window.hydInbox && hydInbox.me()', timeout=15000)
            page.evaluate("""() => { const host = document.createElement('div'); host.id = 'rwProbe'; document.querySelector('main .view.active').prepend(host);
              const view = { instance: { proc_inst_id: 'ask.1', status: 'RUNNING' }, definition: { activities: [{ id: 'T_answer' }], roles: [] }, approvals: [], reworks: [],
                             workitems: [{ id: 'w1', activity_id: 'T_answer', activity_name: '질문에 답하기', status: 'PENDING', start_date: '2026-11-14T00:00:00Z' }] };
              hydRework.mount(host, { view, by: 'user:me', changed: async () => {} }); }""")
            page.locator('#rwProbe details > summary').click()
            page.select_option('#rwStart', 'w1')
            page.locator('#rwPreview').click()
            page.wait_for_selector('#rwProbe [data-rework-norole]', timeout=8000)
            text = page.inner_text('#rwProbe')
            assert '다시 수행을 요청할 수 없습니다' in text and '새 차수를 요청할 수 있습니다' not in text
            assert page.locator('#rwReason').count() == 0 and page.locator('#rwSubmit').count() == 0 and text.count('사유') == 0
            assert page.locator('#rwProbe details').first.evaluate('d => d.open')      # 단계를 고르고 영향을 본 뒤에도 접기는 열린 채다
            b.close()
    finally:
        served.close()


def test_자세한_기록은_사람_id와_안쪽_이름을_그대로_보이지_않고_이름_붙은_사건은_그_이름으로_적는다():
    """2026-11-14 화면 정돈: 처리 건 「자세한 기록」의 처리 건 값에 승인자가 `user:me` 로, 단계 표의 출력 이름에 `cliagents session id` 가 보였고,
    실시간 활동 줄은 시스템이 이름 붙인 사건(승인 접수 · 결함 시뮬레이션의 단추 · 효과 확인 시작)까지 모두 「진행 · 담당자」라 무슨 일인지 알 수 없었다."""
    t = '2026-11-14T13:53:40Z'
    view = {'instance': {'proc_inst_id': 'c.1', 'proc_def_id': 'c3_cooling', 'proc_def_version': '1', 'status': 'COMPLETED', 'start_date': t, 'end_date': t,
                         'variables_data': [{'key': 'approved_by', 'value': 'user:me'}, {'key': 'approved_role', 'value': 'role:operator'}],
                         'variable_sources': {}, 'initial_variables': None},
            'workitems': [{'id': 'w1', 'activity_id': 'T_agent', 'activity_name': '원인 진단', 'status': 'DONE', 'user_id': 'agent:cooling', 'start_date': t, 'end_date': t,
                           'output': {'cause': 'cause:x', 'text': '끝', 'cliagents_session_id': 'replay:1'}}],
            'events': [{'event_type': 'task_working', 'crew_type': 'human', 'job_id': 'SCENARIO_BUTTON', 'timestamp': t, 'data': {'by': '담당자', 'name': '결함 시뮬레이션의 [쿨러 열화 주입]'}},
                       {'event_type': 'task_working', 'crew_type': 'human', 'job_id': 'APPROVAL_ACCEPTED', 'timestamp': t, 'data': {'by': 'user:me', 'name': '승인 접수', 'role': 'role:operator'}},
                       {'event_type': 'task_working', 'crew_type': 'result', 'job_id': 'REOBSERVE_STARTED', 'timestamp': t, 'data': {'name': '효과 확인 시작 (설비 명령 뒤)', 'plan': {}}},
                       {'event_type': 'task_working', 'crew_type': 'cliagents:claude-code', 'job_id': 'run-1', 'timestamp': t, 'data': {'type': 'run_start', 'model': 'coding'}},
                       {'event_type': 'task_started', 'crew_type': 'result', 'job_id': 'run-1', 'timestamp': t, 'data': {'goal': '원인 진단', 'name': 'Claude Code'}}]}
    got = run(FILES, """UI.performers['user:me'] = '담당자'; UI.performers['role:operator'] = '운전원';
        const text = h => h.replace(/<pre[\\s\\S]*?<\\/pre>/g, '').replace(/<[^>]+>/g, '|').replace(/\\|+/g, '|');
        out({ log: text(hydInstances.logPane(DATA)), values: text(hydInstances.valuesPane(DATA, { approved_by: 'user:me' })) })""", view, prelude=PRELUDE)
    log, values = got['log'], got['values']
    assert '|승인자|담당자|' in values and 'user:me' not in values and '|승인 역할|운전원|' in values
    assert '출력 원인' in log and 'cliagents' not in log and 'session' not in log
    for line in ('|결함 시뮬레이션의 [쿨러 열화 주입]|담당자|', '|승인 접수|담당자 · 운전원|', '|효과 확인 시작 (설비 명령 뒤)|시스템|', '|진행|AI 에이전트 · AI 실행을 시작했습니다|',
                 '|단계 시작|시스템 · 원인 진단 · Claude Code|'):
        assert line in log, (line, log)
    assert '담당자 · 담당자' not in log


# ---- 2026-11-16 process-gpt-lite 인스턴스 화면을 본으로 다시 짠 처리 건 화면(디자인기준 5-1): 실제 브라우저에서 잰 관계로 판정한다 ----
def _iso(m, s=0):
    return f'2026-11-16T05:{m:02d}:{s:02d}Z'


CASE_DEF = {'processDefinitionId': 'cool', 'version': '1', 'processDefinitionName': '냉각 긴급 대응',
            'roles': [{'name': 'AI 에이전트', 'endpoint': 'agent:cooling'}, {'name': '운전원', 'endpoint': 'role:operator'}, {'name': '프로세스', 'endpoint': 'sys:process'}],
            'events': [{'id': 'Start', 'type': 'startEvent', 'name': '경보'}, {'id': 'E_end', 'type': 'endEvent', 'name': '처리 완료'}, {'id': 'E_rej', 'type': 'endEvent', 'name': '처리 완료'}],
            'activities': [{'id': 'T_agent', 'name': '원인 진단', 'type': 'userTask', 'role': 'AI 에이전트', 'agent': 'agent:cooling'},
                           {'id': 'T_approve', 'name': '운전원 승인', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:approve', 'outputData': ['approval']},
                           {'id': 'T_cmd', 'name': '냉각 명령', 'type': 'serviceTask', 'role': '프로세스', 'tool': 'incident:command'},
                           {'id': 'R_ok', 'name': '결과 보고: 정상', 'type': 'serviceTask', 'role': '프로세스', 'tool': 'process:report'},
                           {'id': 'R_rej', 'name': '결과 보고: 반려', 'type': 'serviceTask', 'role': '프로세스', 'tool': 'process:report'}],
            'gateways': [{'id': 'G', 'name': '승인?', 'type': 'exclusiveGateway'}],
            'sequences': [{'id': 'F1', 'source': 'Start', 'target': 'T_agent'}, {'id': 'F2', 'source': 'T_agent', 'target': 'T_approve'}, {'id': 'F3', 'source': 'T_approve', 'target': 'G'},
                          {'id': 'F_ok', 'name': '승인', 'source': 'G', 'target': 'T_cmd'}, {'id': 'F_no', 'name': '반려', 'source': 'G', 'target': 'R_rej'},
                          {'id': 'F5', 'source': 'T_cmd', 'target': 'R_ok'}, {'id': 'F6', 'source': 'R_ok', 'target': 'E_end'}, {'id': 'F7', 'source': 'R_rej', 'target': 'E_rej'}]}


def _row(pid, name, status, minute, **more):
    return {'proc_inst_id': pid, 'proc_inst_name': name, 'status': status, 'proc_def_id': 'cool', 'proc_def_version': '1', 'start_date': _iso(minute),
            'end_date': None if status == 'RUNNING' else _iso(minute, 50), 'current_activity_ids': [], 'attention': None, 'end_label': '처리 완료', 'variables_data': [], **more}


def _wi(wid, act, status, minute, **more):
    names = {a['id']: a['name'] for a in CASE_DEF['activities']}
    return {'id': wid, 'activity_id': act, 'activity_name': names[act], 'status': status, 'start_date': _iso(minute, 1), 'end_date': _iso(minute, 30) if status == 'DONE' else None,
            'reached_at': _iso(minute, 1), 'generation': 0, 'agent_orch': 'system', 'agent_mode': None, 'user_id': 'sys:process', 'output': {}, 'log': '', **more}


REPORT = {'outcome': '정상', 'level': 'ok', 'title': 'HYD-01 긴급 대응 결과', 'summary': '유온 정상 · 경보 해제', 'refs': {'work_order': 'WO-1'}}
ROWS = [_row('mine', '냉각 긴급 대응 HYD-01', 'RUNNING', 40, current_activity_ids=['T_approve']),
        _row('ai', '냉각 긴급 대응 HYD-02 — 이름이 아주 긴 처리 건도 목록 줄에서 상태 알약을 밀어내지 않는다', 'RUNNING', 41, current_activity_ids=['T_agent']),
        _row('q1', '질문에 답하기', 'COMPLETED', 39, proc_def_id='ask_agent'),
        *[_row(f'd{i}', f'끝난 건 {i}', 'COMPLETED', 30 - i, variables_data=[{'key': 'result_report', 'value': REPORT}]) for i in range(1, 6)],
        _row('cx', '승인 전에 닫힌 건', 'COMPLETED', 10, end_label='조치 전 해소')]
VIEWS = {
    'mine': [_wi('m1', 'T_agent', 'DONE', 40, agent_orch='cliagents', agent_mode='COMPLETE', user_id='agent:cooling'),
             _wi('m2', 'T_approve', 'IN_PROGRESS', 40, agent_orch=None, user_id='role:operator', tool='formHandler:approve')],
    # 승인 전에 경보가 풀려 닫힌 건: 닿았다가 취소된 사람 단계(서버가 적은 까닭 글은 영문 머리 + 한국어)
    'cx': [_wi('c1', 'T_agent', 'DONE', 10, agent_orch='cliagents', agent_mode='COMPLETE', user_id='agent:cooling'),
           _wi('c2', 'T_approve', 'CANCELLED', 10, agent_orch=None, user_id='role:operator', tool='formHandler:approve', end_date=_iso(10, 40), log='cancelled: 조치 전 해소 — 사건 조치 전 자연 회복(경보 해제), 조치 전 종료; '),
           _wi('c3', 'T_cmd', 'CANCELLED', 10, reached_at=None, tool='incident:command', log='취소: 조치 전 해소; ')],
    'd1': [_wi('a1', 'T_agent', 'DONE', 29, agent_orch='cliagents', agent_mode='COMPLETE', user_id='agent:cooling'),
           _wi('a2', 'T_approve', 'DONE', 29, agent_orch=None, user_id='role:operator', tool='formHandler:approve', output={'approval': '승인'}),
           _wi('a3', 'T_cmd', 'DONE', 29, tool='incident:command'), _wi('a4', 'R_ok', 'DONE', 29, tool='process:report', output={'result_report': REPORT}),
           _wi('a5', 'R_rej', 'CANCELLED', 29, reached_at=None, tool='process:report')],
}
# 지나간 단계와 이름이 같은 단계가 다른 갈래에 또 있는 건(흐름 「냉각 긴급 대응」의 정비 요청 등록 · 효과 확인 · 결과 보고: 정상처럼) — 가지 않은 단계 판정
VIEWS['d2'] = VIEWS['d1'] + [_wi('a6', 'T_cmd', 'CANCELLED', 29, reached_at=None, tool='incident:command')]
TASK = {'id': 'm2', 'proc_inst_id': 'mine', 'proc_inst_name': '냉각 긴급 대응 HYD-01', 'activity_id': 'T_approve', 'activity_name': '운전원 승인', 'status': 'IN_PROGRESS',
        'user_id': 'role:operator', 'tool': 'formHandler:approve', 'agent_orch': None, 'agent_mode': None, 'draft_status': None, 'inputs': {}, 'events': []}


def _answer(route):
    from urllib.parse import urlparse, parse_qs
    u = urlparse(route.request.url); path, q = u.path, parse_qs(u.query)
    api = path.split('/api/', 1)[1] if '/api/' in path else ''
    if '/svc/process/' not in path:
        return route.fulfill(json={})
    if api == 'process/mode':
        return route.fulfill(json={'mode': 'bpmn'})
    if api == 'instances':
        st = (q.get('status') or [''])[0]
        return route.fulfill(json=[r for r in ROWS if not st or r['status'] == st])
    if api.startswith('instances/'):
        pid = api.split('/')[1]
        row = next((r for r in ROWS if r['proc_inst_id'] == pid), None)
        if not row or len(api.split('/')) > 2:
            return route.fulfill(status=404, json={'detail': '없음'})
        return route.fulfill(json={'instance': {**row, 'end_event': None if row['status'] == 'RUNNING' else 'E_end', 'variable_sources': {}, 'initial_variables': {}},
                                   'definition': CASE_DEF, 'workitems': VIEWS.get(pid, VIEWS['d1']), 'events': [], 'approvals': [], 'reworks': [], 'attention': None,
                                   'flow_order': {a['id']: i for i, a in enumerate(CASE_DEF['activities'])}})
    if api.startswith('process/definitions/'):
        return route.fulfill(json=CASE_DEF)
    if api == 'todolist':
        return route.fulfill(json=[TASK] if (q.get('proc_inst_id') or ['mine'])[0] == 'mine' else [])
    if api == 'todolist/m2':
        return route.fulfill(json=TASK)
    if api == 'inbox/users':
        return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': ['role:operator']}])
    if api.startswith('flows/') and api.endswith('/bpmn'):
        return route.fulfill(status=404, json={'detail': '그림 없음'})
    if api in ('agents', 'skills', 'inbox/notifications'):
        return route.fulfill(json=[])
    return route.fulfill(json={})


import contextlib


@contextlib.contextmanager
def _case_page(width=1440, height=900, answer=None, start='#/instances'):
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': width, 'height': height})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.route('**/svc/**', answer or _answer)
            page.goto(served.url + '/index.html' + start)
            if start == '#/instances':
                page.wait_for_selector('#instList .row', timeout=20000)
                page.wait_for_selector('#instDetail .case-progress .step', timeout=20000)
            yield page
            assert errors == [], errors
            b.close()
    finally:
        served.close()


def _pick(page, pid):
    page.locator(f"#instList .row[data-inst='{pid}']").first.click()
    page.wait_for_function("id => hydInstances.I.view && hydInstances.I.view.instance.proc_inst_id === id && document.querySelectorAll('#instRecord .step[data-step]').length > 0", arg=pid, timeout=15000)
    page.wait_for_timeout(400)


def test_목록은_거르기_단추_없이_내_차례_진행_중_처리_완료_세_묶음이고_처리_완료는_세_건과_더_보기다():
    """lite ProjectList(L-7): 묶음의 차례가 거르기를 대신한다. 처리 완료는 3건만 보이고 나머지는 숨은 건수를 단 「더 보기」 뒤에 있다.
    질문 · 문서 추출 같은 시스템 작업은 사건이 아니라 「처리 완료」에 세지 않고 맨 아래 접힌 「시스템 작업」 묶음에 있다(2026-11-20 — 사건 한 건을 처리한 학생에게 「2건 처리 완료」로 보였다).
    줄 = 이름 · 오른쪽 끝 상태 알약 · 그 아래 보조 줄, 끝난 줄은 옅게."""
    with _case_page() as page:
        got = page.evaluate("""() => { const box = document.getElementById('instList'), r = e => e.getBoundingClientRect();
          const kids = [...box.children].map(k => k.classList.contains('rows-group') ? 'G:' + k.firstChild.textContent : k.classList.contains('row') ? 'R:' + k.dataset.inst : 'M:' + k.innerText.trim());
          const rows = [...box.querySelectorAll('.row')].map(row => { const t = r(row.querySelector('.row-title')), c = r(row.querySelector('.tag')), m = r(row.querySelector('.row-meta')), b = r(row);
            return { id: row.dataset.inst, done: 'done' in row.dataset, pillRight: Math.round(b.right - c.right), sameLine: Math.abs((t.top + t.bottom) / 2 - (c.top + c.bottom) / 2) < 3, metaBelow: m.top >= t.bottom - 1, noOverlap: t.right <= c.left,
              ink: getComputedStyle(row.querySelector('.row-title')).color }; });
          return { kids, rows, filters: document.querySelectorAll('#view-instances .case-side .seg, #instTabs').length }; }""")
        assert got['filters'] == 0
        assert got['kids'] == ['G:내 차례', 'R:mine', 'G:진행 중', 'R:ai', 'G:처리 완료', 'R:d1', 'R:d2', 'R:d3', 'M:처리 완료 3건 더 보기', 'M:시스템 작업 1건 더 보기'], got['kids']
        assert page.locator('#instList .rows-group', has_text='처리 완료').locator('.num').inner_text().strip() == '6'      # 끝난 사건 6건(d1~d5 · cx) — 질문 처리 건 q1 은 세지 않는다
        assert all(r['sameLine'] and r['metaBelow'] and r['noOverlap'] for r in got['rows']), got['rows']
        assert len({r['pillRight'] for r in got['rows']}) == 1, got['rows']                      # 상태 알약은 모든 줄에서 같은 세로선(오른쪽 끝)
        open_ink = {r['ink'] for r in got['rows'] if not r['done']}; done_ink = {r['ink'] for r in got['rows'] if r['done'] and r['id'] != page.evaluate('hydInstances.I.sel')}
        assert got['rows'][0]['done'] is False and len(done_ink) == 1 and not (open_ink & done_ink), (open_ink, done_ink)      # 끝난 줄은 옅게
        page.click('#instList [data-done-more]')
        page.wait_for_function("() => document.querySelectorAll('#instList .row[data-done]').length === 6")
        assert page.locator('#instList [data-done-more]').count() == 0 and page.locator("#instList .row[data-inst='q1']").count() == 0      # 처리 완료를 다 펴도 시스템 작업은 그 묶음에 없다
        # 시스템 작업 묶음을 펴면 맨 아래에 그 묶음 머리와 줄이 선다 — 줄을 누르면 그 처리 건이 열린다
        page.click('#instList [data-jobs-more]')
        tail = page.evaluate("() => [...document.getElementById('instList').children].slice(-2).map(k => k.classList.contains('rows-group') ? 'G:' + k.firstChild.textContent + ' ' + k.querySelector('.num').textContent.trim() : 'R:' + k.dataset.inst)")
        assert tail == ['G:시스템 작업 1', 'R:q1'], tail
        _pick(page, 'q1')
        assert page.locator("#instList .row[data-inst='q1']").get_attribute('aria-current') == 'true'


def test_다른_화면의_처리_건에서_보기로_온_시스템_작업은_접힌_묶음을_편_채로_그_건을_연다():
    """질문하기 · 문서 등록의 「처리 건에서 보기」는 주소 #/instances/<처리 건>으로 온다. 시스템 작업 묶음이 접혀 있어도 그 길은 그대로 그 건을 열고,
    고른 줄이 접힌 묶음 안에 숨지 않게 묶음이 펴진 채로 보인다."""
    with _case_page(start='#/instances/q1') as page:
        page.wait_for_function("() => window.hydInstances && hydInstances.I.view && hydInstances.I.view.instance.proc_inst_id === 'q1'", timeout=20000)
        page.wait_for_selector("#instList .row[data-inst='q1'][aria-current='true']", timeout=10000)
        assert page.locator('#instList [data-jobs-more]').count() == 0
        assert page.locator('#instList .rows-group', has_text='시스템 작업').locator('.num').inner_text().strip() == '1'
        assert page.locator('#instDetail .case-title').inner_text().startswith('질문에 답하기')


def test_한_건의_머리는_이름과_알약_보조_줄_진행_막대이고_내_차례일_때만_내가_할_일이_뜨며_끝난_건에는_결과와_다음_할_일_링크가_있다():
    """lite InstanceHeader(L-3 · L-6 · L-13): 상태일 때만 나타난다 — 내 차례가 아니면 「내가 할 일」을 그리지 않고, 끝나지 않았으면 결과 카드를 그리지 않는다.
    진행 막대는 센 값만큼만 찬다(시간으로 차오르지 않는다)."""
    with _case_page() as page:
        probe = """() => { const q = s => document.querySelector('#instDetail ' + s), r = e => e.getBoundingClientRect();
          const title = r(q('.case-title > span')), pill = r(q('.case-title .tag')), meta = r(q('.case-meta')), bar = r(q('.case-bar .pbar')), fill = r(q('.case-bar .pbar > i')), menu = r(q('#caseMenu-trigger')), head = r(q('.case-head'));
          return { pillAfterName: pill.left >= title.right && Math.abs((pill.top + pill.bottom) - (title.top + title.bottom)) < 8, metaUnder: meta.top >= title.bottom - 1, barUnder: bar.top >= meta.bottom, barWide: Math.round(bar.width) === Math.round(head.width),
            fill: Math.round(fill.width / bar.width * 100), menuRight: Math.round(head.right - menu.right) <= 1, meta: q('.case-meta').innerText, pill: q('.case-title .tag').innerText,
            turn: !!q('#todoPanel .turn'), result: !!q('#caseTop .case-result'), links: [...document.querySelectorAll('#instDetail a.go')].map(a => a.dataset.goTab),
            order: ['.case-head', '#todoPanel', '#caseTop', '.case-progress'].map(s => Math.round(r(q(s)).top)) }; }"""
        _pick(page, 'mine')
        page.wait_for_selector('#todoPanel .turn #tdGo')
        a = page.evaluate(probe)
        assert a['pillAfterName'] and a['metaUnder'] and a['barUnder'] and a['barWide'] and a['menuRight'], a
        assert a['pill'] == '내 차례' and a['turn'] and not a['result'], a
        assert '1단계 끝남' in a['meta'] and '/' not in a['meta'].split('시작')[1], a      # 갈림 뒤가 정해지지 않았으면 「n/m」이라 하지 않는다
        assert 0 < a['fill'] < 100, a
        _pick(page, 'd1')
        b = page.evaluate(probe)
        assert b['pill'] == '정상' and b['result'] and not b['turn'], b
        assert '4/4 단계' in b['meta'] and '걸림' in b['meta'] and b['fill'] == 100, b
        assert b['links'] == ['process', 'flows'], b                                     # 다음 할 일: 업무 시스템 기록 · 흐름
        assert b['order'][2] < b['order'][3], b                                          # 결과가 진행 상황보다 위


def test_진행_상황의_단계_줄은_점이_한_세로선에_서고_줄을_누르면_옆_판이_열리며_흐름_그림은_세그먼트_뒤에서_위아래가_비지_않는다():
    """lite StepTimeline · AgentActivity(L-4 · L-5): 기본은 단계 목록이고 그림은 「목록 / 흐름 그림」 뒤에 있다. 단계의 자세한 것은 줄을 눌러 여는 옆 판에 있다.
    그림 칸의 높이는 보이는 그림의 높이를 따른다(6-2) — 맨 위 상자 위와 맨 아래 상자 아래에 상자 한 개 높이보다 큰 빈 띠가 없다."""
    with _case_page() as page:
        _pick(page, 'd1')
        got = page.evaluate("""() => { const r = e => e.getBoundingClientRect(); const steps = [...document.querySelectorAll('#instRecord .step')];
          return { marks: [...new Set(steps.map(s => Math.round(r(s.querySelector('.step-mark')).left)))], times: [...new Set(steps.filter(s => s.querySelector('.step-time')).map(s => Math.round(r(s.querySelector('.step-time')).right)))],
            states: steps.map(s => s.dataset.state), subs: steps.every(s => { const h = r(s.querySelector('.step-head')), b = r(s.querySelector('.step-sub')); return b.top >= h.bottom - 1; }),
            seg: [...document.querySelectorAll('#instDetail [data-case-view]')].map(b => [b.innerText.trim(), b.getAttribute('aria-pressed')]), path: document.getElementById('casePath').hidden }; }""")
        assert len(got['marks']) == 1 and len(got['times']) == 1 and got['subs'], got
        assert got['states'] == ['done', 'done', 'done', 'done', 'done', 'skip'], got              # 시작 · 단계 넷 · 가지 않은 단계(흐리게)
        assert got['seg'] == [['목록', 'true'], ['흐름 그림', 'false']] and got['path'] is True, got
        page.locator("#instRecord .step[data-step='a3'] [data-cr-sheet]").click()
        page.wait_for_selector('dialog.sheet[data-cr-sheet-box][open]')
        page.wait_for_timeout(500)                                           # 판이 들어오는 움직임(0.22초)이 끝난 뒤에 잰다
        sheet = page.evaluate("() => { const d = document.querySelector('dialog.sheet[data-cr-sheet-box]'), b = d.getBoundingClientRect(); return { title: d.querySelector('h2').innerText, right: Math.round(innerWidth - b.right), tall: Math.round(b.height) === innerHeight, tabs: [...d.querySelectorAll('[data-cr-tab]')].map(t => t.innerText.trim()) }; }")
        assert sheet == {'title': '냉각 명령', 'right': 0, 'tall': True, 'tabs': ['내용', '받은 값 · 넘긴 값', '원문']}, sheet
        page.click('dialog.sheet [data-cr-sheet-close]')
        page.wait_for_function("() => !document.querySelector('dialog.sheet[data-cr-sheet-box]').open")
        page.click("#instDetail [data-case-view='flow']")
        page.wait_for_selector('#casePath .bpmn .djs-shape', timeout=20000)
        page.wait_for_timeout(800)
        flow = page.evaluate("""() => { const r = e => e.getBoundingClientRect(); const stage = r(document.querySelector('#casePath .bpmn'));
          const boxes = [...document.querySelectorAll('#casePath .djs-shape')].filter(g => !g.classList.contains('is-lane') && g.getAttribute('data-element-id').indexOf('_label') < 0).map(r).filter(b => b.right > stage.left && b.left < stage.right && b.width > 0);
          const top = Math.min(...boxes.map(b => b.top)), bottom = Math.max(...boxes.map(b => b.bottom)), h = Math.max(...boxes.map(b => b.height));
          return { above: Math.round(top - stage.top), below: Math.round(stage.bottom - bottom), box: Math.round(h), list: document.getElementById('instRecord').hidden, inside: top >= stage.top && bottom <= stage.bottom }; }""")
        assert flow['list'] is True and flow['inside'], flow
        assert flow['above'] <= flow['box'] and flow['below'] <= flow['box'], flow
        # 목록이 가려진 그림 보기에서도 상자를 누르면 그 단계의 옆 판이 열린다
        page.locator('#casePath .djs-shape[data-element-id="T_cmd"]').click()
        page.wait_for_selector('dialog.sheet[data-cr-sheet-box][open]', timeout=5000)
        assert page.locator('dialog.sheet[data-cr-sheet-box] h2').inner_text() == '냉각 명령' and page.locator('dialog.sheet[data-cr-sheet-box]').is_visible()


def test_가지_않은_단계에는_이_처리_건이_이미_지난_단계와_같은_이름을_다시_적지_않는다():
    """06 화면 훑기(2026-11-20): 흐름은 다른 갈래에 같은 이름의 단계를 한 번 더 둔다(냉각 긴급 대응의 정비 요청 등록 · 효과 확인 · 결과 보고: 정상).
    그 이름이 「가지 않은 단계」에 또 나와, 학생은 방금 지난 단계를 하지 않은 것으로 읽었다. 지나가지 않은 길에만 있는 이름만 남고, 수도 그 이름의 수다."""
    with _case_page() as page:
        for pid, names in (('d1', '결과 보고: 반려'), ('d2', '결과 보고: 반려')):      # d2 = d1 + 같은 이름(냉각 명령)의 닿지 않은 단계
            _pick(page, pid)
            row = page.locator("#instRecord .step[data-state='skip']")
            assert row.locator('.step-sub').inner_text().strip() == '1가지 — 이 처리 건이 지나가지 않은 길에만 있는 단계입니다', pid
            assert row.locator('details .fold-body p').text_content().strip() == names, pid      # 접기 안의 이름 줄(펴지 않아도 같은 글)


def test_취소된_단계의_점과_알약은_실패의_빨강이_아니라_남은_단계와_같은_보통_색이고_그림도_멈춤으로_칠하지_않는다():
    """정상 취소(승인 전에 경보가 풀려 건이 닫힘)를 고장처럼 보이지 않는다 — 실제 브라우저에서 칠해진 색으로 판정한다: 취소된 단계의 점은 실패 단계의 점과 다른 색이고
    알약은 상태 색이 없는 보통 알약이며, 화면에 영문 머리(cancelled)가 없고 까닭은 한 번만 읽힌다. 흐름 그림의 그 상자에는 멈춤 표시가 없다."""
    with _case_page() as page:
        page.click('#instList [data-done-more]')
        _pick(page, 'cx')
        got = page.evaluate("""() => { const st = document.querySelector("#instRecord .step[data-step='c2']"), cs = e => getComputedStyle(e);
          const probe = document.createElement('div'); probe.className = 'steps'; probe.innerHTML = '<div class="step" data-state="fail"><span class="step-mark"></span></div><div class="step" data-state="todo"><span class="step-mark"></span></div>'; document.querySelector('#instRecord').appendChild(probe);
          const [fail, todo] = [...probe.querySelectorAll('.step-mark')].map(m => cs(m).backgroundColor); const mark = cs(st.querySelector('.step-mark')).backgroundColor; probe.remove();
          const pill = st.querySelector('.tag'), neutral = document.createElement('span'); neutral.className = 'tag'; st.appendChild(neutral); const plain = cs(neutral).backgroundColor; neutral.remove();
          return { mark, fail, todo, pill: pill.innerText, pillBg: cs(pill).backgroundColor, plain, text: document.getElementById('instDetail').innerText }; }""")
        assert got['mark'] == got['todo'] and got['mark'] != got['fail'], got
        assert got['pill'] == '취소' and got['pillBg'] == got['plain'], got
        assert 'cancelled' not in got['text'].lower() and got['text'].count('사건 조치 전 자연 회복') == 1 and '멈춤' not in got['text'], got['text']
        page.click("#instDetail [data-case-view='flow']")
        page.wait_for_selector('#casePath .bpmn .djs-shape', timeout=20000)
        page.wait_for_timeout(600)
        flow = page.evaluate("() => ({ cls: document.querySelector('#casePath .djs-shape[data-element-id=\"T_approve\"]').getAttribute('class'), tips: [...document.querySelectorAll('#casePath .bpmn-tip')].map(t => t.innerText) })")
        assert 'is-fail' not in flow['cls'] and 'is-todo' in flow['cls'] and flow['tips'] == [], flow


def test_반려를_확정하면_서버가_답할_때까지_판이_지금_하는_일을_말하고_다시_그려져도_남으며_답이_오면_사라진다():
    """빈 기다림 없음(디자인기준 7절): 전에는 [승인] · [반려 확정]을 누르면 서버가 답할 때까지(승인은 실측 1~2초 — 서버가 지금 조건을 다시 확인한다) 판의 단추만 꺼졌다.
    승인 · 반려 · 제출 · 답은 한 길(instances.js act)이다 — 이 세계의 처리 건은 고를 안이 없어 반려만 누를 수 있으므로 반려로 잰다. 요청의 응답을 시험이 붙들고 그 사이의 화면을 본다."""
    with _case_page() as page:
        _pick(page, 'mine')
        page.wait_for_selector('#todoPanel .turn #tdRejectOpen')
        held = []
        page.route('**/svc/process/api/todolist/*/approve', lambda route: held.append(route))
        page.wait_for_function("!document.querySelector('#tdRejectOpen').disabled", timeout=8000)
        page.click('#tdRejectOpen')
        page.fill('#tdReason', '다른 조치를 먼저 해 본다')
        assert page.locator('[data-turn-busy]').count() == 0
        page.click('#tdReject')
        page.wait_for_function("() => { const b = document.querySelector('#todoPanel .turn [data-turn-busy]'); return !!b && /반려를 보내는 중/.test(b.innerText) && !!b.querySelector('.lv-time'); }", timeout=1000)
        assert page.locator('#tdReject').is_disabled()
        # 2초마다의 다시 읽기가 판을 다시 그려도 그 줄이 남고, 2초 뒤에는 서버가 무엇을 하는지(까닭)가 붙는다
        page.wait_for_function("() => /아직 하는 중입니다 — 서버가 반려를 기록하고/.test((document.querySelector('#todoPanel [data-turn-busy]') || {}).innerText || '')", timeout=6000)
        for _ in range(100):
            if held:
                break
            page.wait_for_timeout(50)
        assert len(held) == 1 and held[0].request.post_data_json['decision'] == '반려', '반려 요청이 한 번 나가지 않았다'
        held[0].fulfill(json={})
        page.wait_for_function("() => !document.querySelector('[data-turn-busy]')", timeout=8000)


# ------------------------------------------------------------------ 눌러 보기에서 찾은 것(2026-11-16): 조치 카드의 값 조정 · 미리 보기 · 꺼진 승인의 까닭
def _opt(oid, name, rank, score, actions):
    return {'id': oid, 'kind': 'control', 'name': name, 'rank': rank, 'score': score, 'sopId': oid.split(':')[1].upper(), 'actions': actions, 'feasible': True,
            'approver': {'id': 'role:operator', 'name': '운전원', 'level': 1}, 'approvable_roles': ['role:operator'], 'evaluation_mode': 'execution', 'execution_checked': True}


_LOAD = {'id': 'action:set-load', 'max': 100, 'min': 60, 'seq': 1, 'code': 'LOAD_SET', 'kind': 'command', 'name': '펌프 부하 설정', 'param': 'load_pct', 'value': 70.0, 'target': 'actr:pump-drive', 'targetName': '펌프 부하 설정'}
_FAN = {'id': 'action:set-fan', 'max': 100, 'min': 40, 'seq': 1, 'code': 'FAN_SET', 'kind': 'command', 'name': '팬 속도 설정', 'param': 'fan_pct', 'value': 100.0, 'target': 'actr:fan', 'targetName': '팬 인버터'}
CARD_DEC = {'id': 'DEC-1', 'asset': 'HYD-01', 'recommended': 'skill:sop-cool-11', 'evaluation_mode': 'execution', 'execution_checked': True, 'scenario': {}, 'explanation': '',
            'roles': {'role:operator': {'id': 'role:operator', 'name': '운전원', 'level': 1, 'deptName': '생산팀'}},
            'options': [_opt('skill:sop-cool-11', '팬 최대 운전', 1, 3.38, [_FAN]), _opt('skill:sop-cool-13', '부하 낮추기', 2, 3.05, [_LOAD])]}


@contextlib.contextmanager
def _card_page(preview, select=None):
    """조치 카드(formHandler:select_card)가 열린 처리 건 화면. preview(parameters) → 미리 보기 응답의 options[0] 에 덮을 칸, select() → [승인] 요청의 (status, json)."""
    task = {**TASK, 'tool': 'formHandler:select_card'}
    sent = {'preview': [], 'select': []}

    def answer(route):
        from urllib.parse import urlparse
        path, method = urlparse(route.request.url).path, route.request.method
        api = path.split('/api/', 1)[1] if '/api/' in path else ''
        if api == 'decisions/DEC-1':
            return route.fulfill(json=CARD_DEC)
        if api == 'todolist/m2/decision-preview' and method == 'POST':
            body = route.request.post_data_json
            sent['preview'].append(body)
            base = next(o for o in CARD_DEC['options'] if o['id'] == body['option'])
            acts = [{**a, 'value': body['parameters'].get(a['param'], a['value'])} for a in base['actions']]
            reviewed = {**base, 'actions': acts, 'reviewed_choice': {'parameters': body['parameters'], 'reference_name': base['name'], 'reference_actions': base['actions']}, **preview(body['parameters'])}
            return route.fulfill(json={'id': 'rev-1', 'created': '2026-11-16T05:41:00Z', 'scope': {'decision': 'DEC-1', 'option': body['option'], 'workitem': 'm2'},
                                       'snapshot': {**CARD_DEC, 'options': [reviewed]}})
        if api == 'todolist/m2/select' and method == 'POST':
            sent['select'].append(route.request.post_data_json)
            status, body = select() if select else (200, {})
            return route.fulfill(status=status, json=body)
        if api == 'todolist' or api == 'todolist/m2':
            return route.fulfill(json=[task] if api == 'todolist' else task)
        if api == 'instances/mine':
            row = next(r for r in ROWS if r['proc_inst_id'] == 'mine')
            return route.fulfill(json={'instance': {**row, 'variables_data': [{'key': 'decision_id', 'value': 'DEC-1'}], 'end_event': None, 'variable_sources': {}, 'initial_variables': {}},
                                       'definition': CASE_DEF, 'workitems': [VIEWS['mine'][0], {**VIEWS['mine'][1], 'tool': 'formHandler:select_card'}], 'events': [], 'approvals': [], 'reworks': [],
                                       'attention': None, 'flow_order': {a['id']: i for i, a in enumerate(CASE_DEF['activities'])}})
        return _answer(route)
    with _case_page(height=1400) as page:
        page.route('**/svc/process/api/**', answer)
        _pick(page, 'd1'); _pick(page, 'mine')
        page.wait_for_selector('#todoPanel #tdMore', timeout=15000)
        page.sent = sent
        yield page


def _will(page):
    """「승인하면 시스템이 …」 한 줄(머리 물음 바로 아래)."""
    return page.evaluate("() => [...document.querySelectorAll('#todoPanel p')].map(p => p.innerText.trim()).find(t => t.startsWith('승인하면 시스템이')) || ''")


def test_값을_바꿔_미리_본_안은_승인하면_일어나는_일이_바꾼_값으로_적히고_승인_요청도_그_값으로_나간다():
    """눌러 보기(2026-11-16): 부하 70 %인 안을 75 %로 바꿔 미리 본 뒤에도 머리 줄은 「승인하면 시스템이 부하 70 % …를 실행합니다」였고, 승인하면 설비에는 75 %가 나갔다 —
    화면이 말한 것과 실제로 한 일이 달랐다. 미리 본 뒤의 그 줄에 바꾼 값이 있고 옛 값이 없으며, 값을 바꾸기 전 · 미리 보기 전에는 [승인]이 꺼지고 까닭 줄이 실제 단추 이름으로 할 일을 말한다."""
    with _card_page(lambda params: {}) as page:
        page.click('#tdMore')
        page.locator("input[name=hopt][value='skill:sop-cool-13']").check()
        page.wait_for_function("document.querySelector('#tdLoad')")
        before = _will(page)
        assert '70' in before, before
        page.locator('summary', has_text='미리 보기').first.click() if not page.locator('#tdLoad').is_visible() else None
        page.fill('#tdLoad', '75')
        page.wait_for_function("document.querySelector('#tdGo').disabled")
        hint = page.inner_text('#todoPanel')
        assert f"[{page.inner_text('#tdPreview').strip()}]" in hint                                # 꺼진 까닭이 실제 단추 이름으로
        page.click('#tdPreview')
        page.wait_for_function("!document.querySelector('#tdGo').disabled", timeout=8000)
        after = _will(page)
        assert page.sent['preview'][-1]['parameters'] == {'load_pct': 75} and '75' in after and '70' not in after, (before, after)
        page.click('#tdGo')
        for _ in range(60):
            if page.sent['select']:
                break
            page.wait_for_timeout(50)
        assert page.sent['select'] and page.sent['select'][0]['load_pct'] == 75 and page.sent['select'][0]['review_id'] == 'rev-1', page.sent      # 말한 값과 보내는 값이 같다


def test_미리_본_안이_지금_조건에서_실행할_수_없으면_승인이_꺼지고_그_자리에_까닭과_할_일이_있다():
    """눌러 보기(2026-11-16): 운전 모드가 현장 제어로 바뀐 뒤 미리 보면 서버가 그 안을 제외하는데, [승인]만 꺼지고 왜 꺼졌는지가 단추 줄에 없었다(까닭은 접힌 미리 보기 안에만).
    꺼진 [승인]과 같은 판 안에 까닭 줄이 생기고, 그 줄이 까닭이 적힌 접기의 실제 이름을 가리키며, 그 접기 안에 서버가 준 제외 사유가 보여야 한다."""
    why = 'PLC 운전 모드가 REMOTE_AUTO가 아니면 원격 조치를 쓰지 않는다.'
    with _card_page(lambda params: {'feasible': False, 'violations': [{'rule': 'rule:x', 'text': why}]}) as page:
        page.click('#tdMore')
        fold = page.locator('#todoPanel details', has=page.locator('#tdPreview'))
        if not fold.evaluate('d => d.open'):
            fold.locator('summary').first.click()
        quiet = page.inner_text('#todoPanel')
        page.click('#tdPreview')
        page.wait_for_function("document.querySelector('#tdReviewed b')", timeout=8000)
        assert page.locator('#tdGo').is_disabled()
        said = page.inner_text('#todoPanel').replace(quiet, '')
        new = [line for line in page.inner_text('#todoPanel').split('\n') if '승인할 수 없습니다' in line and line not in quiet]
        name = fold.locator('summary').first.inner_text().split('\n')[0].strip()
        assert len(new) == 1 and name in new[0] and '반려' in new[0], (new, name, said[:200])      # 까닭 줄 하나: 어디에 까닭이 있는지(접기의 실제 이름)와 할 수 있는 일
        go, line = page.locator('#tdGo').bounding_box(), page.get_by_text(new[0], exact=True).bounding_box()
        assert 0 <= line['y'] - (go['y'] + go['height']) < 3 * go['height'], (go, line)              # 꺼진 단추 바로 아래
        assert page.locator('#tdRejectOpen').is_enabled()                                            # 반려는 할 수 있다


def test_서버가_다시_확인하라며_승인을_돌려보내면_까닭_줄이_조치_이름과_실제_단추_이름으로_말한다():
    """눌러 보기(2026-11-16): 서버의 거절 문장에 든 내부 식별자(skill:…)가 그대로 보였고, 「[미리 보기]로 다시 확인」이라 했는데 화면의 단추 이름은 「예측 다시 보기」였다.
    식별자는 이름 사전에 있으면 그 이름으로 바뀌고, 까닭 줄이 가리키는 단추 이름이 승인 옆에 새로 나온 단추의 이름과 같아야 한다."""
    # 거절 문장은 서버가 실제로 내는 것(agentsvc guardrail.check_cards — 제외 규칙에 걸린 후보)을 process 가 붙이는 머리말(current_approval) 뒤에 둔다
    from agentsvc import guardrail
    [why] = guardrail.check_cards({'options': [{'id': 'skill:sop-cool-11', 'selectedBy': [{'rule': 'r'}], 'feasible': False, 'approver': {'id': 'role:operator'}, 'steps': [{'id': 's'}]}], 'recommended': 'skill:sop-cool-11'})
    # 응답 꼴은 process 의 것(instance_mode: 409 {code, reason, needs_new_preview}) — 앞의 대역은 까닭을 다른 칸(message)에 실어 화면이 「요청 실패 (409)」만 보였고,
    # 판정 글 「팬 최대 운전」이 카드의 다른 줄에도 있어 이 시험이 무엇이든 통과했다
    refuse = lambda: (409, {'detail': {'code': 'review_required', 'reason': '현재 조건에서 승인을 보류합니다: ' + why, 'needs_new_preview': False}})
    with _card_page(lambda params: {}, refuse) as page:
        page.evaluate("UI.names['skill:sop-cool-11'] = '팬 최대 운전'")
        page.wait_for_function("!document.querySelector('#tdGo').disabled", timeout=8000)
        page.click('#tdGo')
        page.wait_for_selector('#tdPreviewNow', timeout=8000)
        text = page.inner_text('#todoPanel')
        assert 'skill:sop-cool-11' not in text and '조치 후보 「팬 최대 운전」에 제외 규칙이 걸려 지금 조건에서는 실행할 수 없습니다' in text, text[-300:]
        assert 'EXCLUDE' not in text and '권고 카드' not in text
        assert f"[{page.inner_text('#tdPreviewNow').strip()}]" in text, text[-300:]


def test_자세한_기록의_사건_줄이_한_번에_보이는_수를_넘으면_남은_건수가_적힌_더_보기가_있고_누르면_그만큼_더_보인다():
    """눌러 보기(2026-11-16): 이 단추만 옛 꼴 「이전 활동 더 보기 (남은 N건)」이었다(다른 더 보기는 모두 「N건 더 보기」 — 수가 앞). 떠 있는 스택에서 누른 기록도 없었다.
    단추의 수가 실제로 가려진 줄 수와 같고, 누르면 그 줄들이 보이며 다 보이면 단추가 사라진다. 글의 꼴은 목록의 「처리 완료 N건 더 보기」와 같은 차례(수 → 단위 → 더 보기)다."""
    events = [{'id': f'e{i}', 'proc_inst_id': 'mine', 'event_type': 'task_started', 'timestamp': _iso(40, i % 60), 'crew_type': 'system', 'job_id': f'j{i}', 'data': {'name': f'사건 {i}'}} for i in range(27)]

    def answer(route):
        from urllib.parse import urlparse
        api = urlparse(route.request.url).path.split('/api/', 1)[1]
        if api == 'instances/mine':
            row = next(r for r in ROWS if r['proc_inst_id'] == 'mine')
            return route.fulfill(json={'instance': {**row, 'end_event': None, 'variable_sources': {}, 'initial_variables': {}}, 'definition': CASE_DEF, 'workitems': VIEWS['mine'], 'events': events,
                                       'approvals': [], 'reworks': [], 'attention': None, 'flow_order': {a['id']: i for i, a in enumerate(CASE_DEF['activities'])}})
        return _answer(route)
    with _case_page(height=1200) as page:
        page.route('**/svc/process/api/instances/mine', answer)
        _pick(page, 'd1'); _pick(page, 'mine')
        page.click('#caseMenu-trigger')
        page.locator('[role=menuitem]', has_text='자세한 기록').click()
        page.wait_for_selector('#caseLog [data-events-more]', timeout=8000)
        shown = lambda: page.locator('#caseLog .event-record').count()
        first, more = shown(), page.inner_text('#caseLog [data-events-more]')
        num = int(__import__('re').search(r'(\d+)', more).group(1))
        done_more = page.inner_text('#instList [data-done-more]')
        shape = lambda t: __import__('re').sub(r'\d+', 'N', t).split('N', 1)[1].strip()               # 수 뒤의 글(단위 + 더 보기)
        assert first + num == len(events) and shape(more) == shape(done_more), (first, more, done_more)
        page.click('#caseLog [data-events-more]')
        page.wait_for_function("n => document.querySelectorAll('#caseLog .event-record').length === n", arg=len(events), timeout=8000)
        assert page.locator('#caseLog [data-events-more]').count() == 0


# ------------------------------------------------------------------ 마지막 고침(2026-11-16): 멈춘 처리 건의 같은 실패 문장 세 번
STUCK_WHY = 'AI 키가 없을 때 쓰는 재생 모드에서는 「원인 진단」의 준비된 AI 판단을 이 처리 건에 쓸 수 없습니다. 설비 상태를 시작 상태로 되돌린 뒤 다시 시작해 주세요.'


@contextlib.contextmanager
def _stuck_page():
    """AI 단계가 실패해 사람 조치를 기다리며 멈춘 처리 건(서버 instances.attention 의 꼴 — 단계 이름 · 종류 말 · 까닭 · 그 단계의 작업 id)."""
    failed = _wi('s1', 'T_agent', 'IN_PROGRESS', 41, agent_orch='cliagents', agent_mode='COMPLETE', user_id='agent:cooling', draft_status='FAILED', log=STUCK_WHY)
    attention = {'state': 'stuck', 'label': '멈춤 — 사람 조치 필요',
                 'steps': [{'workitem': 's1', 'activity': 'T_agent', 'name': '원인 진단', 'kind': 'failed', 'label': 'AI 실행이 실패함', 'reason': STUCK_WHY, 'actions': ['rework', 'close']}]}
    events = [{'id': 'e1', 'todo_id': 's1', 'proc_inst_id': 'ai', 'event_type': 'error', 'timestamp': _iso(41, 20), 'data': {'message': STUCK_WHY, 'friendly': STUCK_WHY}}]

    def answer(route):
        from urllib.parse import urlparse
        path = urlparse(route.request.url).path
        api = path.split('/api/', 1)[1] if '/api/' in path else ''
        if api == 'instances/ai':
            row = next(r for r in ROWS if r['proc_inst_id'] == 'ai')
            return route.fulfill(json={'instance': {**row, 'end_event': None, 'variable_sources': {}, 'initial_variables': {}}, 'definition': CASE_DEF, 'workitems': [failed], 'events': events,
                                       'approvals': [], 'reworks': [], 'attention': attention, 'flow_order': {a['id']: i for i, a in enumerate(CASE_DEF['activities'])}})
        return _answer(route)
    with _case_page(height=1400) as page:
        page.route('**/svc/process/api/**', answer)
        _pick(page, 'ai')
        page.wait_for_selector('#instDetail [aria-label="멈춘 단계"]', timeout=15000)
        yield page


def test_멈춘_처리_건의_까닭_문장은_맨_위_알림에_한_번만_나오고_단계_줄은_그_알림을_가리키며_조치_단추는_그_단계에_있다():
    """V 8절 5(2026-11-16): 같은 실패 문장이 머리 알림 · 단계 줄 · 단계 아래 알림에 세 번 나왔다(디자인 기준 1-2 · 1-3 — 같은 말은 한 화면에 한 번, 결론 먼저).
    화면에 보이는 글에서 그 문장을 센다. 단계 줄은 무슨 멈춤인지와 알림의 자리만 말하고, 알림의 [이 단계에서 조치하기]를 누르면 그 단계의 [단계 닫기]가 창 안에 들어온다."""
    with _stuck_page() as page:
        key = STUCK_WHY[:40]
        got = page.evaluate("""key => {
          const seen = n => { const r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(n).visibility !== 'hidden'; };
          const leaves = [...document.querySelectorAll('#instDetail *')].filter(n => seen(n) && [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.includes(key)));
          const alert = document.querySelector('#instDetail [aria-label="멈춘 단계"]'), step = document.querySelector('#instRecord .step[data-step="s1"]');
          return { count: leaves.length, inAlert: leaves.every(n => alert.contains(n)), alertTop: alert.getBoundingClientRect().top, stepTop: step.getBoundingClientRect().top,
                   sub: step.querySelector('.step-sub').innerText, pill: step.querySelector('.step-head .badge, .step-head [data-tone]')?.innerText || '',
                   stepAlerts: step.querySelectorAll('.alert').length, alertTitle: alert.querySelector('h2').innerText };
        }""", key)
        assert got['count'] == 1 and got['inAlert'], got                                   # 한 번, 맨 위 알림에서만
        assert got['alertTop'] < got['stepTop'] and got['stepAlerts'] == 0, got            # 결론이 먼저 — 단계 아래에 같은 알림을 또 세우지 않는다
        assert got['sub'].endswith('AI 실행이 실패함 — 까닭과 할 일은 맨 위 알림에 있습니다') and got['pill'] == '실패', got
        page.evaluate("window.scrollTo(0, 0); document.querySelector('.app-main')?.scrollTo?.(0, 0)")
        page.click('#instDetail [aria-label="멈춘 단계"] [data-goto-step="s1"]')
        page.wait_for_timeout(900)
        box = page.evaluate("""() => { const b = document.querySelector('#instRecord .step[data-step="s1"] [data-close-task="s1"]'); if (!b) return null;
          const r = b.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, h: innerHeight, text: b.innerText.trim() }; }""")
        assert box and 0 <= box['top'] and box['bottom'] <= box['h'], box                    # 조치 단추는 그 단계에 있고, 알림의 단추가 거기로 데려간다


# ------------------------------------------------------------------ 마지막 고침(2026-11-16): 아무도 누르지 않은 단추 — 그 상태를 만들어 실제로 누른다
_OUT = {'rule': 'forecast:model-unavailable', 'effect': 'EXCLUDE', 'annotation': '현재 조치 예측을 확인할 수 없습니다: 설비 상태가 15초 전 값이라 지금 예측에 쓸 수 없습니다(15초 이내만)'}
NONE_DEC = {**CARD_DEC, 'recommended': None,
            'options': [{**o, 'feasible': False, 'rank': None, 'score': None, 'violations': [_OUT]} for o in CARD_DEC['options']]}
REWORK_PREVIEW = {'start_workitem': 'm1', 'affected_workitems': ['m1', 'm2'], 'cancel_workitems': ['m2'], 'invalidated_variables': ['decision_id'], 'restored_input_variables': [],
                  'retained_outputs': [], 'reasons': {}, 'blockers': [], 'effects': None, 'retire_approvals': [], 'candidate_variables': [], 'execution_available': True,
                  'request_roles': ['role:operator'], 'snapshot_token': 'tok-1'}


@contextlib.contextmanager
def _none_page():
    """실행할 수 있는 안이 하나도 없는 판단이 올라온 승인 단계(조치 카드) — 재생 모드 스택에서는 생기지 않는 상태다(AI 단계가 「준비된 판단과 다르다」로 먼저 멈춘다).
    반려(reject-card)가 나가면 처리 건은 반려로 닫힌 것으로 답한다(서버가 하는 일). sent 에 보낸 요청이 남는다."""
    task = {**TASK, 'tool': 'formHandler:select_card'}
    sent = {'reject': [], 'preview': [], 'rework': []}

    def answer(route):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(route.request.url); path, method = u.path, route.request.method
        api = path.split('/api/', 1)[1] if '/api/' in path else ''
        closed = bool(sent['reject'])
        if api == 'decisions/DEC-1':
            return route.fulfill(json=NONE_DEC)
        if api == 'todolist/m2/reject-card' and method == 'POST':
            sent['reject'].append(route.request.post_data_json)
            return route.fulfill(json={})
        if api == 'instances/mine/rework-preview':
            sent['preview'].append(parse_qs(u.query))
            return route.fulfill(json=REWORK_PREVIEW)
        if api == 'instances/mine/rework' and method == 'POST':
            sent['rework'].append(route.request.post_data_json)
            return route.fulfill(json={'generation': 1})
        if api == 'todolist':
            return route.fulfill(json=[] if closed else [task])
        if api == 'todolist/m2':
            return route.fulfill(json={**task, 'status': 'DONE'} if closed else task)
        if api == 'instances' and closed:
            return route.fulfill(json=[{**r, 'status': 'COMPLETED', 'end_date': _iso(42), 'end_label': '반려'} if r['proc_inst_id'] == 'mine' else r for r in ROWS])
        if api == 'instances/mine':
            row = next(r for r in ROWS if r['proc_inst_id'] == 'mine')
            row = {**row, 'status': 'COMPLETED', 'end_date': _iso(42), 'end_label': '반려'} if closed else row
            items = [VIEWS['mine'][0], {**VIEWS['mine'][1], 'tool': 'formHandler:select_card', **({'status': 'DONE', 'end_date': _iso(42), 'output': {'approval': '반려'}} if closed else {})}]
            return route.fulfill(json={'instance': {**row, 'variables_data': [{'key': 'decision_id', 'value': 'DEC-1'}], 'end_event': 'E_rej' if closed else None, 'variable_sources': {}, 'initial_variables': {}},
                                       'definition': CASE_DEF, 'workitems': items, 'events': [], 'approvals': [], 'reworks': [],
                                       'attention': None, 'flow_order': {a['id']: i for i, a in enumerate(CASE_DEF['activities'])}})
        return _answer(route)
    with _case_page(height=1400) as page:
        page.route('**/svc/process/api/**', answer)
        _pick(page, 'd1'); _pick(page, 'mine')
        page.wait_for_selector('#todoPanel [data-case-act="recover"]', timeout=15000)
        page.sent = sent
        yield page


def test_승인할_안이_없을_때의_반려하고_이_건_닫기는_사유를_받아_반려_요청을_보내고_건이_닫힌_것이_화면에_남는다():
    """V 보고 「못 누른 것」: 실행할 수 있는 안이 하나도 없는 판단에만 나오는 주 단추 — 아무도 누른 적이 없었다. 누르면 사유 칸이 열리고, 사유 없이는 나가지 않으며,
    [반려 확정]이 조치 카드 반려(POST …/reject-card)를 그 판단 · 담당자 · 승인 역할 · 사유로 한 번 보낸다. 끝나면 결과 알림이 뜨고 그 건은 내 차례가 아니다."""
    with _none_page() as page:
        panel = page.inner_text('#todoPanel')
        assert '지금은 승인할 수 있는 안이 없습니다' in panel and page.locator('#tdGo').count() == 0      # 꺼진 [승인]을 주 단추 자리에 두지 않는다
        page.wait_for_function("!document.querySelector('#tdRejectOpen').disabled", timeout=8000)
        assert page.inner_text('#tdRejectOpen').strip() == '반려하고 이 건 닫기'
        page.click('#tdRejectOpen')
        page.wait_for_selector('#tdRejectCard')
        page.click('#tdRejectCard')                                             # 사유 없이: 나가지 않고 까닭을 말한다
        page.wait_for_function("document.querySelector('#todoPanel').innerText.includes('반려 사유를 1~2000자로 적으세요')", timeout=5000)
        assert page.sent['reject'] == []
        page.fill('#tdReason', '예측을 확인할 수 없어 지금은 조치하지 않는다')
        page.click('#tdRejectCard')
        page.wait_for_function("() => !document.querySelector('#todoPanel #tdRejectCard')", timeout=10000)
        assert page.sent['reject'] == [{'decision': 'DEC-1', 'by': 'user:me', 'role': 'role:operator', 'reason': '예측을 확인할 수 없어 지금은 조치하지 않는다'}]
        page.wait_for_function("document.body.innerText.includes('반려했습니다. 승인 뒤 조치는 실행하지 않습니다.')", timeout=8000)      # 결과 알림
        page.wait_for_function("hydInstances.I.view && hydInstances.I.view.instance.status === 'COMPLETED'", timeout=8000)
        assert page.locator('#todoPanel #tdRejectOpen, #todoPanel [data-case-act="recover"]').count() == 0      # 내가 할 일이 걷혔다
        assert '내 차례' not in page.inner_text('#instDetail .case-title')


def test_승인할_안이_없을_때의_새_판단_요청하기는_다시_수행_폼을_창_안에_펴고_거기서_영향_확인과_요청이_그_단계로_나간다():
    """V 보고 「못 누른 것」: [새 판단 요청하기]는 자세한 기록의 「다시 수행 · 복구」 보기를 펴 그 자리로 데려가는 단추다. 눌러서 폼이 창 안에 보이는지,
    그 폼에서 AI 단계를 골라 [영향 확인] → 사유 · 확인 → 요청하면 서버로 그 단계 · 담당자 · 역할 · 사유 · 영향 확인 때 받은 토큰이 가는지, 접수 결과가 화면에 남는지 본다."""
    with _none_page() as page:
        assert page.inner_text('#todoPanel [data-case-act="recover"]').strip() == '새 판단 요청하기'
        note = page.inner_text('#todoPanel')
        assert '[새 판단 요청하기]에서 「다시 수행」을 요청하면' in note
        page.click('#todoPanel [data-case-act="recover"]')
        page.wait_for_selector('#caseMore[open] #reworkPanel details[open] #rwStart', timeout=8000)
        page.wait_for_timeout(900)                                             # 부드러운 스크롤이 끝난 뒤
        seen = page.evaluate("""() => { const r = document.querySelector('#rwStart').getBoundingClientRect(), tab = document.querySelector('#caseMoreTabs [aria-selected="true"]');
          return { inView: r.top >= 0 && r.bottom <= innerHeight, tab: tab ? tab.dataset.moreTab : '', fold: document.querySelector('#reworkPanel summary').innerText.trim(),
                   steps: [...document.querySelectorAll('#rwStart option')].filter(o => o.value).map(o => [o.value, o.textContent.trim()]) }; }""")
        assert seen['inView'] and seen['tab'] == 'recover' and '다시 수행' in seen['fold'], seen
        assert any(v == 'm1' and '원인 진단' in t for v, t in seen['steps']), seen      # 다시 판단시킬 AI 단계를 고를 수 있다
        page.select_option('#rwStart', 'm1')
        page.click('#rwPreview')
        page.wait_for_selector('#rwConfirm:not([disabled])', timeout=8000)
        assert page.sent['preview'] == [{'workitem_id': ['m1']}]
        page.fill('#rwReason', '설비 값이 다시 들어왔다')
        page.check('#rwConfirm')
        page.click('#rwSubmit')
        page.wait_for_function("document.querySelector('#reworkPanel')?.innerText.includes('요청이 접수됐습니다')", timeout=8000)
        [body] = page.sent['rework']
        assert body.pop('request_id') and body == {'workitem_id': 'm1', 'snapshot_token': 'tok-1', 'by': 'user:me', 'role': 'role:operator', 'reason': '설비 값이 다시 들어왔다'}, body
        assert '2차 요청이 접수됐습니다' in page.inner_text('#reworkPanel')
        assert page.sent['reject'] == []


PROPOSAL_CFG = {'options': 'proposal.options', 'key': 'name', 'recommended': 'proposal.recommended', 'losers': 'proposal.losers', 'docs': 'proposal.docs'}
PROPOSAL = {'options': [{'name': '야간 세척', 'reason': '생산 영향이 가장 작다', 'score': 3.4}, {'name': '즉시 정지', 'reason': '가장 빨리 회복한다', 'score': 2.1}], 'recommended': '야간 세척'}


@contextlib.contextmanager
def _proposal_page():
    """에이전트 제안을 받는 일반 승인 단계(formHandler:approve + 활동의 approval 설정 — 학생이 만든 흐름의 꼴). 기본 제공 흐름에는 없는 카드다."""
    definition = {**CASE_DEF, 'activities': [{**a, 'approval': PROPOSAL_CFG} if a['id'] == 'T_approve' else a for a in CASE_DEF['activities']]}
    task = {**TASK, 'inputs': {'proposal': PROPOSAL}}
    sent = []

    def answer(route):
        from urllib.parse import urlparse
        path, method = urlparse(route.request.url).path, route.request.method
        api = path.split('/api/', 1)[1] if '/api/' in path else ''
        if api == 'todolist/m2/approve' and method == 'POST':
            sent.append(route.request.post_data_json)
            return route.fulfill(json={})
        if api == 'todolist' or api == 'todolist/m2':
            return route.fulfill(json=[task] if api == 'todolist' else task)
        if api == 'instances/mine':
            row = next(r for r in ROWS if r['proc_inst_id'] == 'mine')
            return route.fulfill(json={'instance': {**row, 'end_event': None, 'variable_sources': {}, 'initial_variables': {}}, 'definition': definition, 'workitems': VIEWS['mine'], 'events': [],
                                       'approvals': [], 'reworks': [], 'attention': None, 'flow_order': {a['id']: i for i, a in enumerate(CASE_DEF['activities'])}})
        if api.startswith('process/definitions/'):
            return route.fulfill(json=definition)
        return _answer(route)
    with _case_page(height=1400) as page:
        page.route('**/svc/process/api/**', answer)
        _pick(page, 'd1'); _pick(page, 'mine')
        page.wait_for_selector('#todoPanel #tdMore', timeout=15000)
        page.sent = sent
        yield page


def test_일반_승인_카드에서_다른_안을_골랐다가_추천안으로_되돌리기를_누르면_물음과_승인_요청이_추천안으로_돌아온다():
    """V 보고 「못 누른 것」: 에이전트 제안을 받는 일반 승인 카드의 「다른 안 n개 비교」 · [추천안으로 되돌리기]. 다른 안을 고르면 물음이 그 안으로 바뀌고 되돌리기 단추가 나오며,
    누르면 물음 · 카드가 추천안으로 돌아오고 단추가 사라진다. 그 뒤 [승인]은 추천안으로 나간다(되돌리지 않았다면 고른 안으로 나간다 — 앞의 물음으로 확인)."""
    with _proposal_page() as page:
        asks = lambda: page.evaluate("() => [...document.querySelectorAll('#todoPanel *')].map(n => n.childNodes.length === 1 && n.firstChild.nodeType === 3 ? n.textContent.trim() : '').find(t => t.endsWith('안을 승인할까요?')) || ''")      # noqa: E731
        assert asks() == '「야간 세척」 안을 승인할까요?'
        # 이 세계는 첫 화면을 제안 없는 응답으로 연 뒤 제안을 붙이므로 카드가 펴진 채일 수 있다(약속과 다른 제안은 펴서 보인다) — 접힌 데서 시작해 [다른 안 고르기]를 누른다
        if page.get_attribute('#tdMore', 'aria-expanded') == 'true':
            page.click('#tdMore')
            page.wait_for_function("!document.querySelector('#todoPanel .ap-card')", timeout=5000)
        assert page.inner_text('#tdMore').strip() == '다른 안 고르기'
        page.click('#tdMore')
        page.wait_for_selector('#todoPanel .ap-card')
        assert page.locator('#todoPanel [data-ap-back]').count() == 0 and 'AI 에이전트 추천' in page.inner_text('#todoPanel .ap-kicker')
        fold = page.locator('#todoPanel .ap-card details', has_text='비교')
        assert '다른 안 1개' in fold.locator('summary').inner_text()
        if not fold.evaluate('n => n.open'):
            fold.locator('summary').click()
        page.locator("#todoPanel input[name=hopt][value='즉시 정지']").click()      # 고르면 카드가 다시 그려져 그 안이 머리로 올라간다(고르기 칸은 사라진다)
        page.wait_for_selector('#todoPanel [data-ap-back]')
        assert asks() == '「즉시 정지」 안을 승인할까요?' and '직접 고른 안' in page.inner_text('#todoPanel .ap-kicker')
        back = page.locator('#todoPanel [data-ap-back]')
        assert back.inner_text().strip() == '추천안으로 되돌리기'
        back.click()
        page.wait_for_function("!document.querySelector('#todoPanel [data-ap-back]')", timeout=5000)
        assert asks() == '「야간 세척」 안을 승인할까요?' and 'AI 에이전트 추천' in page.inner_text('#todoPanel .ap-kicker')
        page.wait_for_function("!document.querySelector('#tdGo').disabled", timeout=8000)
        page.click('#tdGo')
        for _ in range(100):
            if page.sent:
                break
            page.wait_for_timeout(50)
        assert page.sent == [{'decision': '승인', 'option': '야간 세척', 'by': 'user:me', 'role': 'role:operator', 'reason': ''}], page.sent


# 결과 보고 없이 끝난 건 둘: 사람이 닫은 건(기술 끝 「사람이 닫음」)과, 끝 이벤트의 이름이 뜻 없는 「처리 완료」인 건
CLOSED_ROWS = [_row('hc', '설비 이상 조치 HYD-02', 'COMPLETED', 9, end_label='사람이 닫음'), _row('pe', '끝 이름이 뜻 없는 건', 'COMPLETED', 8)]


def _answer_more(route):
    """_answer 에 더한 것: 사건 목록(GET /api/incidents — 사건은 진행 중 1 · 끝난 것 1뿐이다. 처리 건 목록과 다른 것을 센다)과, 결과 보고 없이 끝난 건 둘."""
    from urllib.parse import urlparse, parse_qs
    u = urlparse(route.request.url); api = u.path.split('/api/', 1)[1] if '/api/' in u.path else ''
    if '/svc/process/' in u.path and api == 'incidents':
        return route.fulfill(json=[{'id': 'INC-1', 'asset': 'HYD-01', 'alertId': 'A1', 'terminal': False, 'history': []}, {'id': 'INC-2', 'asset': 'HYD-01', 'alertId': 'A2', 'terminal': True, 'history': []}])
    if '/svc/process/' in u.path and api == 'instances':
        st = (parse_qs(u.query).get('status') or [''])[0]
        return route.fulfill(json=[r for r in ROWS + CLOSED_ROWS if not st or r['status'] == st])
    if '/svc/process/' in u.path and api in ('instances/hc', 'instances/pe'):
        row = next(r for r in CLOSED_ROWS if r['proc_inst_id'] == api.split('/')[1])
        return route.fulfill(json={'instance': {**row, 'end_event': 'closed-by-human' if api.endswith('hc') else 'E_end', 'variable_sources': {}, 'initial_variables': {}}, 'definition': CASE_DEF,
                                   'workitems': [_wi('h1', 'T_agent', 'CANCELLED', 9, agent_orch='cliagents', user_id='agent:cooling', end_date=_iso(9, 40), log='[담당자 단계 닫음] 닫았습니다')],
                                   'events': [], 'approvals': [], 'reworks': [], 'attention': None, 'flow_order': {a['id']: i for i, a in enumerate(CASE_DEF['activities'])}})
    return _answer(route)


def test_홈_카드의_내_차례_진행_중_처리_완료_수는_그_카드를_눌러_가는_처리_건_화면의_묶음_수와_같다():
    """대역(2026-11-16): 홈 「4 결과 보기 — 10건 처리 완료」와 처리 건 목록의 「처리 완료 13」이 달랐다. 홈은 사건(GET /api/incidents)을, 목록은 처리 건(질문 · 문서 추출 포함)을 셌다.
    같은 이름은 같은 것을 센다: 홈 카드의 수를 읽고, 그 카드를 눌러 간 처리 건 화면의 묶음 머리 수와 견준다(대역의 사건 목록은 처리 건 목록과 건수가 다르다)."""
    with _case_page(answer=_answer_more, start='#/main') as page:
        page.wait_for_function("() => /\\d/.test(document.querySelector('#mainStages a.stat:nth-child(4) .stat-value')?.firstChild?.textContent || '')", timeout=20000)
        home = page.evaluate("""() => { const card = n => document.querySelector(`#mainStages a.stat:nth-child(${n})`), num = c => c.querySelector('.stat-value').firstChild.textContent.trim();
          return { open: [num(card(3)), card(3).querySelector('.stat-value small').textContent], mine: (card(3).querySelector('.stat-pill')?.innerText || '').trim(),
                   done: [num(card(4)), card(4).querySelector('.stat-value small').textContent], nav: document.getElementById('navTodo').textContent.trim() }; }""")
        page.locator('#mainStages a.stat:nth-child(4)').click()
        page.wait_for_selector('#instList .row', timeout=20000)
        groups = page.evaluate("Object.fromEntries([...document.querySelectorAll('#instList .rows-group')].map(g => [g.firstChild.textContent, g.querySelector('.num').textContent.trim()]))")
        assert home['open'] == [groups['진행 중'], '건 진행 중'] and home['done'] == [groups['처리 완료'], '건 처리 완료'], (home, groups)
        assert home['mine'] == f"내 차례 {groups['내 차례']}" and home['nav'] == groups['내 차례'], (home, groups)
        # 사건 처리 건만 센다(2026-11-20): 끝난 처리 건 9건 가운데 질문 처리 건(q1 — 시스템 작업) 하나를 뺀 8건. 문서 한 건을 추출하고 사건 한 건을 처리한 학생에게 홈이 「2건 처리 완료」라고 했다
        ended = [r for r in ROWS + CLOSED_ROWS if r['status'] != 'RUNNING']
        assert len(ended) == 9 and home['done'][0] == str(len([r for r in ended if r['proc_def_id'] != 'ask_agent'])) == '8', (home, len(ended))
        # 묶음 머리의 수는 「더 보기」로 폈을 때 보이는 줄 수다(끝난 사건 처리 건 전부)
        page.click('#instList [data-done-more]')
        page.wait_for_function("() => !document.querySelector('#instList [data-done-more]')")
        assert page.locator('#instList .row[data-done]').count() == int(groups['처리 완료'])


def test_시스템_작업_안의_사람_차례는_내_차례로_세고_그_건을_시스템_작업_묶음에_또_두지_않는다():
    """처리 완료 · 진행 중의 수는 사건 처리 건만 세지만(2026-11-20), 사람이 할 일은 숨기지 않는다: 질문하기 처리 건에서 에이전트가 사람에게 되물은 차례도
    메뉴 곁 수와 「내 차례」 묶음에 들고, 그 건은 시스템 작업 묶음에 한 번 더 나오지 않는다. 세는 곳 하나(hydCases.groups)를 실제 페이지에서 부른다."""
    with _case_page() as page:
        got = page.evaluate("""() => { const q = { proc_inst_id: 'q9', proc_def_id: 'ask_agent', status: 'RUNNING' }, x = { proc_inst_id: 'x1', proc_def_id: 'manual_source_extraction', status: 'COMPLETED' };
          const g = hydCases.groups({ all: [q, x], running: [q], todo: [{ id: 't9', proc_inst_id: 'q9', proc_def_id: 'ask_agent', draft_status: 'HUMAN_ASKED', user_id: 'role:operator', agent_orch: null }] });
          return { mine: g.mine.map(t => t.proc_inst_id), jobs: g.jobs.map(r => r.proc_inst_id), open: g.open.length, done: g.done.length }; }""")
        assert got == {'mine': ['q9'], 'jobs': ['x1'], 'open': 0, 'done': 0}, got


def test_끝난_건의_목록_알약과_머리_알약과_결과_카드는_같은_말을_하고_사람이_닫은_건을_완료라고_하지_않는다():
    """대역(2026-11-16): 사람이 닫은 건이 목록 · 머리에서 「완료」 알약인데 결과 카드는 「사람이 닫음 — 결과 보고가 남지 않은 처리 건」이었다. 한 건의 끝을 세 자리가 같은 말로 한다:
    결과 보고가 있으면 그 보고의 말(정상), 없으면 끝 이벤트의 이름(사람이 닫음 · 조치 전 해소), 그 이름이 뜻 없는 「처리 완료」일 때만 「완료」."""
    with _case_page(answer=_answer_more) as page:
        page.click('#instList [data-done-more]')
        page.wait_for_function("() => !document.querySelector('#instList [data-done-more]')")
        said = {}
        for pid in ('hc', 'cx', 'pe', 'd1'):
            _pick(page, pid)
            said[pid] = page.evaluate("""pid => { const row = document.querySelector(`#instList .row[data-inst='${pid}']`), card = document.querySelector('#caseTop .case-result');
              return { row: row.querySelector('.tag').innerText.trim(), meta: row.querySelector('.row-meta').innerText, head: document.querySelector('#instDetail .case-title .tag').innerText.trim(),
                       card: (card.querySelector('.tag') || card.querySelector('.result-main')).innerText.trim() }; }""", pid)
        assert all(v['row'] == v['head'] == v['card'] for v in said.values()), said
        assert [said[k]['row'] for k in ('hc', 'cx', 'pe', 'd1')] == ['사람이 닫음', '조치 전 해소', '완료', '정상'], said
        assert not [k for k, v in said.items() if v['row'] in v['meta']], said      # 알약이 한 말을 보조 줄이 또 하지 않는다


# ------------------------------------------------------------------ 화면 글 2026-11-20: 학생이 「저게 뭐지」 할 자리(06 화면 훑기) — 실제 브라우저에서 읽은 글과 놓인 자리로 판정한다
def _answer_case(pid, instance, workitems, definition=None, extra=None):
    """_answer 에 처리 건 하나(pid)의 응답을 덮는다. extra: {api 경로: 응답} — 판단 · 사건 읽기."""
    def answer(route):
        from urllib.parse import urlparse
        path = urlparse(route.request.url).path
        api = path.split('/api/', 1)[1] if '/api/' in path else ''
        if '/svc/process/' in path and api in (extra or {}):
            return route.fulfill(json=extra[api])
        if '/svc/process/' in path and api == f'instances/{pid}':
            row = next(r for r in ROWS if r['proc_inst_id'] == pid)
            d = definition or CASE_DEF
            return route.fulfill(json={'instance': {**row, 'end_event': 'E_end', 'variable_sources': {}, 'initial_variables': {}, **instance}, 'definition': d, 'workitems': workitems,
                                       'events': [], 'approvals': [], 'reworks': [], 'attention': None, 'flow_order': {a['id']: i for i, a in enumerate(d['activities'])}})
        return _answer(route)
    return answer


def test_끝난_단계의_오른쪽_시각은_끝난_때이고_문장에는_시각을_또_적지_않으며_진행_중인_단계는_시작_시각이다():
    """06 화면 훑기: 「운전원 승인 02:15:54」 줄의 글이 「… 02:18:40에 … 승인했습니다」라 한 줄에 시각이 둘이었고, 오른쪽(단계가 열린 때)이 승인 시각보다 앞섰다.
    규칙은 하나다(사용자 2026-11-20): 끝난 단계의 오른쪽 시각은 끝난 때, 문장 속 시각은 없다. 아직 끝나지 않은 단계는 시작 시각(또는 시작부터의 경과)이다."""
    wis = [_wi('a1', 'T_agent', 'DONE', 28, agent_orch='cliagents', agent_mode='COMPLETE', user_id='agent:cooling'),
           # 승인 요청은 05:28:31에 올라왔고 담당자는 05:31:17에 승인했다 — 그 사이를 기다렸다
           _wi('a2', 'T_approve', 'DONE', 28, agent_orch=None, user_id='role:operator', tool='formHandler:select_card', start_date=_iso(28, 31), end_date=_iso(31, 17)),
           _wi('a3', 'T_cmd', 'DONE', 31, tool='incident:command', start_date=_iso(31, 18), end_date=_iso(31, 20)),
           _wi('a4', 'R_ok', 'DONE', 31, tool='process:report', start_date=_iso(31, 21), end_date=_iso(31, 21), output={'result_report': REPORT}),
           _wi('a5', 'R_rej', 'CANCELLED', 28, reached_at=None, tool='process:report')]
    chosen = [{'key': 'approved_by', 'value': 'user:me'}, {'key': 'approved_role', 'value': 'role:operator'}, {'key': 'chosen_skill', 'value': 'skill:sop-cool-11'},
              {'key': 'chosen_option', 'value': {'id': 'skill:sop-cool-11', 'name': '팬 최대 운전'}}, {'key': 'result_report', 'value': REPORT}]
    read = """() => [...document.querySelectorAll('#instRecord .step[data-step]')].map(s => { const t = s.querySelector('.step-time');
      return { id: s.dataset.step, time: t ? t.textContent.trim() : '', ended: !!t && 'ended' in t.dataset, since: !!t && 'since' in t.dataset, title: t ? t.title : '', sub: s.querySelector('.step-sub').innerText }; })"""
    with _case_page(answer=_answer_case('d3', {'variables_data': chosen}, wis)) as page:
        _pick(page, 'd3')
        rows = {r['id']: r for r in page.evaluate(read)}
        clock = lambda iso: page.evaluate('t => hydTrace.hhmmss(t)', iso)
        assert rows['a2']['ended'] and rows['a2']['time'] == clock(_iso(31, 17)) != clock(_iso(28, 31)), rows['a2']      # 승인한 때(끝난 때) — 승인 요청이 올라온 때가 아니다
        assert rows['a2']['sub'].endswith('‘팬 최대 운전’을 승인했습니다.') and not __import__('re').search(r'\d{1,2}:\d{2}', rows['a2']['sub']), rows['a2']
        assert clock(_iso(28, 31)) in rows['a2']['title'] or '시작' in rows['a2']['title'], rows['a2']                  # 시작한 때는 올려 보는 도움말에 남는다
        for wid, end in (('a1', _iso(28, 30)), ('a3', _iso(31, 20)), ('a4', _iso(31, 21))):                             # 모든 끝난 단계가 같은 규칙이다
            assert rows[wid]['ended'] and rows[wid]['time'] == clock(end), (wid, rows[wid])
        assert not [r for r in rows.values() if __import__('re').search(r'\d{1,2}:\d{2}:\d{2}', r['sub'])], rows       # 어느 줄의 글에도 시각이 또 나오지 않는다
        # 그 단계의 옆 판 머리도 같은 규칙이다: 끝난 때 · 걸린 시간
        page.locator("#instRecord .step[data-step='a2'] [data-cr-sheet]").click()
        page.wait_for_selector('dialog.sheet[data-cr-sheet-box][open] .sheet-head p', timeout=10000)
        head = page.locator('dialog.sheet[data-cr-sheet-box] .sheet-head p').inner_text()
        assert page.evaluate('t => UI.dateTime(t)', _iso(31, 17)) in head and '2분 46초' in head, head
        page.click('dialog.sheet [data-cr-sheet-close]')
        page.wait_for_function("() => !document.querySelector('dialog.sheet[data-cr-sheet-box]').open")
        # 아직 끝나지 않은 단계(내 차례인 승인): 끝난 때가 없다 — 시작 시각이거나 시작부터의 경과다
        _pick(page, 'mine')
        now = {r['id']: r for r in page.evaluate(read)}
        assert not now['m2']['ended'] and (now['m2']['since'] or now['m2']['time'] == clock(_iso(40, 1))) and now['m2']['title'].endswith('시작'), now['m2']
        assert now['m1']['ended'] and now['m1']['time'] == clock(_iso(40, 30)), now['m1']


_RICH_DEC = {'id': 'DEC-1', 'asset': 'HYD-01', 'recommended': 'skill:sop-cool-11', 'evaluation_mode': 'execution', 'execution_checked': True, 'scenario': {},
             'roles': {'role:operator': {'id': 'role:operator', 'name': '운전원', 'level': 1, 'deptName': '생산팀'}},
             'facts': {'order_due_h': 5.99, 'order_penalty_per_h': 120},
             'explanation': "쿨러 냉각 성능 상실 — 조치 후보 2개 중 '팬 최대 운전'(SOP-COOL-11)을 권장합니다. 납기: 오더 납기까지 5시간 59분, 늦으면 시간당 120만 원 — 생산을 유지하는 조치라 순위 점수에 +0.5점이 반영됐습니다.",
             'options': [{**_opt('skill:sop-cool-11', '팬 최대 운전', 1, 3.38, [_FAN]), 'scoreParts': {'delivery': 0.5, 'forecast': 1.73},
                          'forecast': [{'variable': 'sv:ts1', 'name': '평형 유온', 'value': 49.8, 'unit': '℃'}, {'variable': 'sv:ps1', 'name': '토출 압력', 'value': 182, 'unit': 'bar'}],
                          'gains': [{'name': '인터록 여유', 'weight': 1}], 'losses': [{'name': '전력 사용량', 'weight': 1}]},
                         {**_opt('skill:sop-cool-13', '부하 낮추기', 2, 3.05, [_LOAD]), 'scoreParts': {'delivery': -0.17, 'forecast': 2.0},
                          'forecast': [{'variable': 'sv:ts1', 'name': '평형 유온', 'value': 47.7, 'unit': '℃'}], 'gains': [], 'losses': []}]}


def test_승인_판의_납기까지는_소수_시간이_아니라_시간과_분으로_적고_한_시간_미만은_분만_적는다(monkeypatch):
    """06 화면 훑기: 승인 판 한가운데의 「납기까지 5.99 시간」 — 소수 시간은 낯설다(사용자 2026-11-20 「5시간 59분」, 1시간 미만은 「45분」처럼 분만).
    판단 설명(판단 서비스가 쓰는 글)도 같은 꼴이라, 설명에 나온 값을 먼저 놓는 차례는 그대로다(납기까지 · 지연 보상이 값 칸에 있다)."""
    import sys
    monkeypatch.setattr(sys.modules[__name__], 'CARD_DEC', _RICH_DEC)
    with _card_page(lambda p: {}) as page:
        cells = page.evaluate("() => [...document.querySelectorAll('#todoPanel dl.turn-facts > div')].map(c => [c.querySelector('dt').innerText.trim(), c.querySelector('dd').innerText.trim()])")
        assert ['납기까지', '5시간 59분'] in cells and ['조치 뒤 예측 평형 유온', '49.8℃'] in cells, cells
        assert [k for k, _ in cells if k == '지연 보상'] and not [x for _, x in cells if '5.99' in x], cells
        assert page.evaluate('[5.99, 0.75, 6, 0.999, 24.5].map(h => UI.hoursText(h))') == ['5시간 59분', '45분', '6시간', '1시간', '24시간 30분']


def test_판단_근거의_결론_아래는_이름과_값이_칸으로_나뉘고_후보_비교는_무엇을_견준_축인지_말한다(monkeypatch):
    """06 화면 훑기: 결론 밑 「예측 평형 유온 49.8 °C · 토출 압력 182 bar · 좋아지는 것 인터록 여유 · 감수할 것 전력 사용량」은 이름과 값이 구분 없이 이어졌고,
    후보 비교의 「예측에서 앞섬」은 무엇을 견준 축인지 화면에 없었다. 값은 승인 판과 같은 값 칸(이름 위 · 값 아래, 칸마다 나란히)에 놓이고, 견준 축은 「예측 유온 여유」다."""
    import sys
    monkeypatch.setattr(sys.modules[__name__], 'CARD_DEC', _RICH_DEC)
    with _card_page(lambda p: {}) as page:
        page.wait_for_selector('#todoPanel [data-open-step]', timeout=15000)
        page.click('#todoPanel [data-open-step]')                                   # 승인 판의 「판단 근거 · 후보 비교 보기」 — AI 단계의 옆 판 「판단」 보기
        page.wait_for_selector('dialog.sheet[data-cr-sheet-box][open] .cr-judge', timeout=10000)
        page.wait_for_timeout(500)
        got = page.evaluate("""() => { const d = document.querySelector('dialog.sheet[data-cr-sheet-box]'), r = e => e.getBoundingClientRect();
          const cells = [...d.querySelectorAll('.cr-judge dl.turn-facts > div')].map(c => { const k = c.querySelector('dt'), v = c.querySelector('dd');
            return { name: k.innerText.trim(), value: v.innerText.trim(), below: r(v).top >= r(k).bottom - 1, left: Math.round(r(c).left), top: Math.round(r(c).top) }; });
          return { cells, main: d.querySelector('.cr-judge .result-main').innerText.trim(), judge: d.querySelector('.cr-judge').innerText, notes: [...d.querySelectorAll('.opts tr, .opts li')].map(x => x.innerText).join(' | ') }; }""")
        assert [(c['name'], c['value']) for c in got['cells']] == [('예측 평형 유온', '49.8℃'), ('예측 토출 압력', '182bar'), ('좋아지는 것', '인터록 여유'), ('감수할 것', '전력 사용량')], got['cells']
        assert all(c['below'] for c in got['cells']) and len({c['left'] for c in got['cells']}) == 4 and len({c['top'] for c in got['cells']}) == 1, got['cells']      # 이름 위 · 값 아래, 네 칸이 한 줄에 나란히
        assert '「팬 최대 운전」을 추천합니다' in got['main'] and '49.8 ℃ · 토출 압력' not in got['judge'], got
        assert '납기에서 뒤짐 · 예측 유온 여유에서 앞섬' in got['notes'] and '예측에서 앞섬' not in got['notes'], got['notes']


def test_효과_확인의_판정_문장은_판정_근거인_마지막_값을_먼저_말하고_기준_안에_있던_시간은_덧붙임이다():
    """06 화면 훑기: 「… 기준(55 ℃ 아래) 안에 있던 시간 60 % — 회복으로 판정했습니다」는 60 %인데 회복이라 의아했다. 서버의 판정은 판정 때 읽은 마지막 값이
    기준 안이고 경보가 꺼졌는가다(procsvc service_parts._reobserve · reobs_series.inside_last) — 그 근거가 문장 앞에 서고, 기준 안에 있던 시간(inside_share)은 괄호 안이다."""
    a, b = _iso(31, 22), _iso(32, 24)
    inc = {'id': 'INC-9', 'asset': 'HYD-01', 'state': 'CLOSED', 'cleared': True, 'recoveryPolicy': {'criterion': ['TS1', '<', 55]},
           'history': [{'state': 'RE_OBSERVING', 't': a, 'reobservation': {'sim_s': 900}},
                       {'state': 'RESOLVED', 't': b, 'note': '재관측 결과 회복', 'reobservation': {'tag': 'TS1', 'op': '<', 'limit': 55, 'value': 51.4, 'cleared': True, 'recovered': True, 'sim_s': 1200}}],
           'reobsSeries': {'tag': 'TS1', 'op': '<', 'limit': 55, 'first': 61.5, 'last': 51.4, 'min': 51.4, 'max': 61.5, 'samples': 2, 'inside_share': 0.6, 'inside_last': True, 'from': a, 'to': b,
                           'points': [{'t': a, 'v': 61.5}, {'t': b, 'v': 51.4}]}}
    definition = {**CASE_DEF, 'activities': CASE_DEF['activities'] + [{'id': 'T_reobs', 'name': '효과 확인', 'type': 'serviceTask', 'role': '프로세스', 'tool': 'incident:reobserve'}]}
    wis = [_wi('a1', 'T_agent', 'DONE', 28, agent_orch='cliagents', agent_mode='COMPLETE', user_id='agent:cooling'), _wi('a3', 'T_cmd', 'DONE', 31, tool='incident:command'),
           {**_wi('a3', 'T_cmd', 'DONE', 31), 'id': 'r1', 'activity_id': 'T_reobs', 'activity_name': '효과 확인', 'tool': 'incident:reobserve', 'start_date': a, 'end_date': b, 'output': {'recovered': True}},
           _wi('a4', 'R_ok', 'DONE', 33, tool='process:report', output={'result_report': REPORT})]
    variables = [{'key': 'incident', 'value': 'INC-9'}, {'key': 'recovered', 'value': True}, {'key': 'asset', 'value': 'HYD-01'}, {'key': 'result_report', 'value': REPORT}]
    with _case_page(answer=_answer_case('d3', {'variables_data': variables}, wis, definition, {'incidents/INC-9': inc})) as page:
        _pick(page, 'd3')
        page.wait_for_function("() => (document.querySelector(\"#instRecord .step[data-step='r1'] .step-sub\")?.innerText || '').includes('판정했습니다')", timeout=10000)
        sub = page.locator("#instRecord .step[data-step='r1'] .step-sub").inner_text()
        assert '유온의 마지막 값(51.4 ℃)이 기준(55 ℃ 아래) 안이고 경보도 꺼져 회복으로 판정했습니다' in sub, sub
        page.locator("#instRecord .step[data-step='r1'] [data-cr-sheet]").click()
        page.wait_for_selector('dialog.sheet[data-cr-sheet-box][open] .cr-say', timeout=10000)
        say = page.locator('dialog.sheet[data-cr-sheet-box] .cr-say').inner_text()
        assert say == '유온의 마지막 값(51.4 ℃)이 기준(55 ℃ 아래) 안이고 경보도 꺼져 회복으로 판정했습니다 (설비 시간 15분 + 연장 5분 (실제 1분 2초) 동안 61.5→51.4 ℃ · 기준 안에 있던 시간 60 %).', say
        assert say.index('마지막 값') < say.index('회복으로 판정') < say.index('기준 안에 있던 시간 60 %'), say
