"""빈 기다림이 없다(디자인기준 7절 — 사용자 2026-11-16 「아무것도 모르고 멍하게 기다리면서 바라보면 안 된다」).

요청 하나로 끝나는 일도, 누른 순간부터 서버가 답할 때까지 「지금 무엇을 하는 중인지」가 글로 보이고, 끝난 뒤에는 무엇을 했는지가 그 자리에 남는다.
실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 이 시험이 주는 것은 브라우저 밖의 process 응답뿐이고, 재려는 요청의 응답은 시험이 붙들었다가
푼다(Hold) — 서버가 답하기 전의 화면을 잰다."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen


def _serve():
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    return Served(app)


class Hold:
    """붙든 응답 하나. 화면이 요청을 보내면 keep(route, 응답)으로 붙들고, 시험이 release(page)로 푼다."""

    def __init__(self):
        self.route, self.body, self.sent = None, None, None

    def keep(self, route, body):
        self.route, self.body, self.sent = route, body, route.request.post_data_json

    def release(self, page):
        for _ in range(100):
            if self.route is not None:
                break
            page.wait_for_timeout(50)
        assert self.route is not None, '화면이 그 요청을 보내지 않았다'
        self.route.fulfill(json=self.body)


USERS = [{'id': 'user:me', 'name': '담당자', 'roles': []}]


def test_질문을_보내면_서버가_답하기_전에_내_질문과_보내는_중이_대화에_놓이고_답이_온_뒤에는_사라진다():
    """전에는 [보내기]를 누르면 서버가 처리 건을 열어 답할 때까지(실측 약 3초) 대화 칸이 빈 화면(또는 앞 질문의 답) 그대로였다."""
    from playwright.sync_api import sync_playwright
    served, hold = _serve(), Hold()
    agent = {'id': 'sys:agent', 'name': '인공지능 에이전트', 'default': True, 'mine': False, 'goal': '', 'role': '', 'servers': ['neo4j'], 'skills': [], 'left_out': []}
    view = {'id': 'ask_agent.q1', 'question': '재고가 가장 적은 설비는', 'state': 'waiting', 'message': '', 'agent': {'id': 'sys:agent', 'name': '인공지능 에이전트'}, 'asked_by': '담당자',
            'started': '2026-11-16T07:00:00Z', 'workitem': None, 'tool_calls': [], 'result': None, 'link': '#/instances/ask_agent.q1'}

    def answer(route):
        url, method = route.request.url.split('?')[0], route.request.method
        if url.endswith('/api/ask/status'):
            return route.fulfill(json={'ready': True, 'reason': '', 'default': 'sys:agent', 'agents': [agent], 'worker': {'ai_mode': 'live', 'replay_questions': []}})
        if url.endswith('/api/ask') and method == 'POST':
            return hold.keep(route, view)
        if url.endswith('/api/ask'):
            return route.fulfill(json=[])
        if url.endswith('/api/ask/ask_agent.q1'):
            return route.fulfill(json=view)
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=USERS)
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'ask')
            page.locator('#askText').wait_for(timeout=15000)
            page.wait_for_function("document.querySelector('#askAgent').options.length > 0")
            page.fill('#askText', view['question'])
            page.locator('#askSend').click()
            # 서버가 답하기 전(응답을 붙들고 있다): 1초 안에 내 질문 말풍선과 「질문을 보내는 중」이 대화 칸에 보이고, 입력창 위 한 줄도 같은 말을 한다
            page.wait_for_function("""() => { const t = document.querySelector('[data-ask-thread]'), n = document.querySelector('[data-ask-now]');
                return !!t.querySelector('.ask-bubble') && t.querySelector('.ask-bubble').textContent === '재고가 가장 적은 설비는' && /질문을 보내는 중/.test(t.innerText) && !n.hidden && /질문을 보내는 중/.test(n.innerText); }""", timeout=1000)
            assert page.locator('[data-ask-sending] .lv-time').is_visible(), '보내는 중에 걸린 시간이 보이지 않는다'
            assert '아직 보낸 질문이 없습니다' not in page.inner_text('[data-ask-thread]')
            hold.release(page)
            # 답이 왔다: 서버가 준 질문이 그 자리에 놓이고(에이전트가 받는 중) 「보내는 중」은 사라진다 — 질문 말풍선은 그대로다
            page.wait_for_function("() => /에이전트가 질문을 받는 중/.test(document.querySelector('[data-ask-thread]').innerText) && !document.querySelector('[data-ask-sending]')", timeout=5000)
            assert page.inner_text('[data-ask-thread] .ask-bubble') == view['question'] and hold.sent['question'] == view['question']
            b.close()
    finally:
        served.close()


def test_오일_분석_입력을_보내면_서버가_답하기_전에_무엇을_하는_중인지_말하고_답이_오면_결과로_바뀐다():
    from playwright.sync_api import sync_playwright
    served, hold = _serve(), Hold()
    form = {'assets': ['HYD-01', 'HYD-02'], 'patterns': [{'code': 'OIL_ANALYSIS', 'items': [{'key': 'viscosity', 'text': '점도', 'unit': 'cSt'}]}]}

    def answer(route):
        url, method = route.request.url.split('?')[0], route.request.method
        if url.endswith('/api/human-alerts/form'):
            return route.fulfill(json=form)
        if url.endswith('/api/human-alerts') and method == 'POST':
            return hold.keep(route, {'raised': False, 'reason': '기준 안이라 경보를 만들지 않았습니다.'})
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=USERS)
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'oil')
            page.locator('#oilAsset').wait_for(timeout=15000)
            page.wait_for_function("!document.querySelector('#oilSend').disabled", timeout=15000)      # 담당자를 읽은 뒤
            page.select_option('#oilAsset', 'HYD-02'); page.select_option('#oilItem', 'viscosity'); page.locator("input[name=oilOut][value='0']").check()
            page.locator('#oilSend').click()
            page.wait_for_function("() => { const s = document.querySelector('[data-oil-sending]'); return !!s && /분석 결과를 보내는 중/.test(s.innerText) && /경보를 만들지 정하는 중/.test(s.innerText); }", timeout=1000)
            assert page.locator('[data-oil-sending] .lv-time').is_visible()
            hold.release(page)
            page.wait_for_function("() => !document.querySelector('[data-oil-sending]') && /기준 안이라 경보를 만들지 않았습니다/.test(document.querySelector('#oilView').innerText)", timeout=5000)
            assert hold.sent['asset'] == 'HYD-02' and hold.sent['out_of_spec'] is False
            b.close()
    finally:
        served.close()


def test_표_정의를_적재하는_동안_지식_지도에_쓰는_것을_말하고_끝나면_쓴_것이_단계로_남는다():
    """전에는 단추가 「적재하는 중」으로만 바뀌었다. 적재는 요청 하나라서 진행률은 없다 — 실제로 보내는 수(시스템 · 입력 데이터)와 끝난 뒤 서버가 답한 수를 적는다."""
    from playwright.sync_api import sync_playwright
    served, hold = _serve(), Hold()
    inp = lambda col: {'id': f'in:{col}', 'name': col, 'typeRef': 'number', 'schema': 'public', 'table': 'T_EQP00', 'column': col, 'system': 'sys:erp', 'variable': col.lower()}
    preview = {'filename': 'mine.sql', 'chars': 23, 'catalog': 'postgres', 'datasource': 'ds', 'warnings': [], 'systems': [{'id': 'sys:erp', 'name': '전사 자원 관리'}], 'existingSystems': [],
               'sourceOptions': [{'id': 'ds', 'label': '업무 DB', 'schema': 'public'}], 'inputs': [inp('EQP_CD'), inp('RUN_H')],
               'tables': [{'table': 'T_EQP00', 'comment': '', 'system': 'sys:erp', 'columns': ['EQP_CD', 'RUN_H'], 'selected': ['EQP_CD', 'RUN_H']}]}

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/api/kg/ddl/preview') and method == 'POST':
            return route.fulfill(json=preview)
        if path.endswith('/api/kg/ddl/commit') and method == 'POST':
            return hold.keep(route, {'batch': 'ddl-1', 'systems': 1, 'inputs': 2})
        if path.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'total': 0, 'next_offset': None})
        if path.endswith('/api/kg/ingests') or path.endswith('/api/kg/manuals') or path.endswith('/api/kg/skills'):
            return route.fulfill(json=[])
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=USERS)
        return route.fulfill(json={})
    steps = "() => [...document.querySelectorAll('#ddlDone .lv-step')].map(n => n.className.replace('lv-step ', '') + ':' + n.querySelector('b').textContent)"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'knowledge')
            page.click("#docKinds [data-doc-kind='ddl']")
            page.click("#ddlPick [data-pick-mode='file']")
            page.set_input_files('#ddlFile', {'name': 'mine.sql', 'mimeType': 'text/plain', 'buffer': 'CREATE TABLE a (b int);'.encode()})
            page.click('#ddlPreview')
            page.locator('#ddlCommit').wait_for(timeout=15000)
            page.wait_for_function("!document.querySelector('#ddlCommit').disabled")
            page.locator('#ddlCommit').click()
            page.wait_for_function(f"() => JSON.stringify(({steps})()) === JSON.stringify(['run:시스템 1개 · 입력 데이터 2개를 지식 지도에 쓰는 중'])", timeout=1000)
            hold.release(page)
            page.wait_for_function(f"() => JSON.stringify(({steps})()) === JSON.stringify(['ok:지식 지도에 썼습니다'])", timeout=8000)
            first = page.locator('#ddlDone .lv-step').first
            assert '시스템 1개 · 입력 데이터 2개' in first.inner_text() and first.locator('.lv-time').inner_text().strip(), first.inner_text()
            assert page.locator('#ddlDone .doc-next a.go').count() == 2      # 다음 할 일 링크는 단계 아래에 그대로 있다
            assert hold.sent['by'] == '담당자' and len(hold.sent['inputs']) == 2
            b.close()
    finally:
        served.close()
