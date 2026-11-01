"""처리 건 화면(it/portal/www/instances.js) — 머리 요약 칸의 셈. node 에서 실제 화면 모듈을 싣고 부른다(www_node).
instances.js 는 실릴 때 화면 요소를 찾으므로 브라우저 쪽만 최소 대역(어떤 요소든 같은 빈 요소, 바깥 요청 실패)으로 둔다."""
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
