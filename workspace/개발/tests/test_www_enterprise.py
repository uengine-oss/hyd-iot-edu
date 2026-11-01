"""승인과 실행 화면(it/portal/www/enterprise.js)의 업무 시스템 보드 — 업무 상태(/api/state)가 주는 표만 그린다.
enterprise.js 는 실릴 때 화면 요소를 찾으므로 브라우저 쪽만 최소 대역(요소 · 탭 표)으로 두고 실제 모듈을 싣는다."""
from www_node import run

# 브라우저 대역: 어떤 요소를 찾아도 같은 빈 요소, 바깥 요청은 실패. 화면 모듈 코드는 그대로 돈다
PRELUDE = r"""
const __fakeNode = () => new Proxy({ addEventListener() {}, append() {}, querySelector: () => __fakeNode(), querySelectorAll: () => [], classList: { toggle() {}, add() {} },
  dataset: {}, style: {}, value: '', innerHTML: '' }, { get: (t, k) => k in t ? t[k] : () => __fakeNode() });
globalThis.document = { getElementById: __fakeNode, querySelector: __fakeNode, querySelectorAll: () => [], createElement: __fakeNode, readyState: 'complete', addEventListener() {} };
globalThis.$ = () => __fakeNode(); globalThis.el = __fakeNode; globalThis.state = { tab: 'main' }; globalThis.selectTab = () => {};
globalThis.hydTabs = { onShow() {} }; globalThis.getJ = () => Promise.reject(new Error('대역')); globalThis.postJ = globalThis.getJ;
globalThis.keyboardItem = () => {}; globalThis.ResizeObserver = class { observe() {} }; globalThis.CSS = { escape: s => s }; globalThis.fmt = v => String(v); globalThis.API = { agent: '', process: '', ent: '' };
"""
STATE = {'mes': {'orders': [{'order_id': 'MO-1', 'asset': 'HYD-01', 'due_in_h': 30}]},
         'cmms': {'work_orders': [{'id': 'WO-1', 'asset': 'HYD-01', 'task': '핀 세척', 'window': '야간'}]},
         'erp': {'purchase_requests': [{'id': 'PR-1', 'supplierName': 'B-OEM', 'status': 'ORDERED'}],
                 'goods_receipts': [{'id': 'GR-1', 'part_no': 'P-SEAL', 'qty': 2, 'inspection': '합격'}]}}


def test_업무_보드는_지금_업무_상태의_표만_읽고_뺀_칸이_없어도_그린다():
    """FE 070이 대체 출하 · 로트 처분 · 전력 칸을 /api/state에서 뺐다 — 화면이 erp.shipments 를 읽으면 보드 전체가 멈췄다."""
    got = run(['ui.js', 'plainWords.js', 'approvalCard.js', 'enterprise.js'],
              "out(hydEnt.systemBoards(DATA).map(([sys, rows]) => [sys, rows.map(r => r.a || r.order_id || r.id)]))", STATE, prelude=PRELUDE)
    assert got == [['생산 관리', ['MO-1']], ['정비 관리', ['WO-1']], ['구매 · 재고 관리', ['PR-1', 'GR-1']]]


def test_구매_카드의_공급사는_그_카드가_정한_견적의_업무_DB_이름으로_보이고_다른_공급사는_그대로다():
    """넘김 FW → FT 덧: 공급사(sup:*)는 이름 사전에 없어 조치 줄이 「구매 요청 sup:c」로 보였다 — 카드가 정한 공급사(resolvedSupplier)의 견적 이름이 정본."""
    option = {'resolvedSupplier': {'id': 'sup:c', 'quote': {'name': '대성유압'}}}
    got = run(['ui.js', 'plainWords.js', 'approvalCard.js', 'enterprise.js'],
              "out([hydCards.actionLabel({ code: 'PR_CREATE', value: 'sup:c' }, DATA), hydCards.actionLabel({ code: 'PR_CREATE', value: 'sup:a' }, DATA)])",
              option, prelude=PRELUDE)
    assert got == ['구매 요청 대성유압', '구매 요청 sup:a']
