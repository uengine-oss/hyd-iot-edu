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
def _case_page(width=1440, height=900):
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
            page.route('**/svc/**', _answer)
            page.goto(served.url + '/index.html#/instances')
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
    """lite ProjectList(L-7): 묶음의 차례가 거르기를 대신한다. 처리 완료는 사건 3건만 보이고(질문 같은 시스템 작업은 뒤로) 나머지는 숨은 건수를 단 「더 보기」 뒤에 있다.
    줄 = 이름 · 오른쪽 끝 상태 알약 · 그 아래 보조 줄, 끝난 줄은 옅게."""
    with _case_page() as page:
        got = page.evaluate("""() => { const box = document.getElementById('instList'), r = e => e.getBoundingClientRect();
          const kids = [...box.children].map(k => k.classList.contains('rows-group') ? 'G:' + k.firstChild.textContent : k.classList.contains('row') ? 'R:' + k.dataset.inst : 'M:' + k.innerText.trim());
          const rows = [...box.querySelectorAll('.row')].map(row => { const t = r(row.querySelector('.row-title')), c = r(row.querySelector('.tag')), m = r(row.querySelector('.row-meta')), b = r(row);
            return { id: row.dataset.inst, done: 'done' in row.dataset, pillRight: Math.round(b.right - c.right), sameLine: Math.abs((t.top + t.bottom) / 2 - (c.top + c.bottom) / 2) < 3, metaBelow: m.top >= t.bottom - 1, noOverlap: t.right <= c.left,
              ink: getComputedStyle(row.querySelector('.row-title')).color }; });
          return { kids, rows, filters: document.querySelectorAll('#view-instances .case-side .seg, #instTabs').length }; }""")
        assert got['filters'] == 0
        assert got['kids'] == ['G:내 차례', 'R:mine', 'G:진행 중', 'R:ai', 'G:처리 완료', 'R:d1', 'R:d2', 'R:d3', 'M:처리 완료 4건 더 보기'], got['kids']
        assert all(r['sameLine'] and r['metaBelow'] and r['noOverlap'] for r in got['rows']), got['rows']
        assert len({r['pillRight'] for r in got['rows']}) == 1, got['rows']                      # 상태 알약은 모든 줄에서 같은 세로선(오른쪽 끝)
        open_ink = {r['ink'] for r in got['rows'] if not r['done']}; done_ink = {r['ink'] for r in got['rows'] if r['done'] and r['id'] != page.evaluate('hydInstances.I.sel')}
        assert got['rows'][0]['done'] is False and len(done_ink) == 1 and not (open_ink & done_ink), (open_ink, done_ink)      # 끝난 줄은 옅게
        page.click('#instList [data-done-more]')
        page.wait_for_function("() => document.querySelectorAll('#instList .row[data-done]').length === 7")
        assert page.locator('#instList [data-done-more]').count() == 0


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
