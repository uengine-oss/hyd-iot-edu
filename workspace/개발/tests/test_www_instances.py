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
