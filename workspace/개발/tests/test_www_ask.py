"""질문하기 화면(it/portal/www/ask.js) — 대화 틀(가운데 한 칸 · 바닥 입력창), 빈 대화의 질문 예 알약 둘, 답을 쓰는 동안 입력창 위에 흐르는 「지금 하는 일」 한 줄, 답과 「처리 건에서 보기」.

실제 index.html · ask.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(질문 기능 상태 · 질문 목록 · 질문 한 건)만 이 시험이 준다
(꼴은 procsvc/ask.py 의 GET /api/ask/status · GET/POST /api/ask · GET /api/ask/{id})."""
import json

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

AGENT = {'id': 'sys:agent', 'name': '인공지능 에이전트', 'default': True, 'mine': False, 'goal': '경보의 원인을 진단한다', 'role': '', 'servers': ['neo4j'], 'skills': [], 'left_out': []}
QUESTIONS = ['HM-8 매뉴얼의 즉시 완화 조치 절차 번호는', 'HYD-01 쿨러 팬 모터 제조사의 고객센터 전화번호는 무엇인가']
STATUS = {'ready': True, 'reason': '', 'default': 'sys:agent', 'agents': [AGENT], 'worker': {'ai_mode': 'replay', 'replay_questions': QUESTIONS}}
CALL = {'id': 't1', 'tool': 'neo4j/read_neo4j_cypher', 'raw_tool': 'mcp__neo4j__read_neo4j_cypher', 'data': True, 'running': True, 'started': '2026-11-16T07:00:01Z'}


def _view(state, **more):
    return dict({'id': 'ask_agent.q1', 'question': QUESTIONS[0], 'state': state, 'message': '', 'agent': {'id': 'sys:agent', 'name': '인공지능 에이전트'}, 'asked_by': '담당자',
                 'started': '2026-11-16T07:00:00Z', 'workitem': 'w1', 'tool_calls': [], 'result': None, 'link': '#/instances/ask_agent.q1/task/w1'}, **more)


def test_빈_대화의_질문_예를_보내면_입력창_위에_부르는_도구가_흐르고_답과_처리_건_링크가_남는다():
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    world = {'view': None, 'posted': None}

    def answer(route):
        url, method = route.request.url.split('?')[0], route.request.method
        if url.endswith('/api/ask/status'):
            return route.fulfill(json=STATUS)
        if url.endswith('/api/ask') and method == 'POST':
            world['posted'] = json.loads(route.request.post_data)
            world['view'] = _view('running', tool_calls=[CALL])
            return route.fulfill(json=world['view'])
        if url.endswith('/api/ask'):
            return route.fulfill(json=[])
        if url.endswith('/api/ask/ask_agent.q1'):
            return route.fulfill(json=world['view'])
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'ask')
            picks = page.locator('[data-ask-picks] [data-ask-pick]')
            picks.first.wait_for(timeout=15000)
            assert picks.count() == 2 and page.locator('#askSend').is_disabled()
            # 틀: 대화 칸은 720px 를 넘지 않고, 입력창은 대화 아래(창 바닥 쪽)에 있으며 에이전트 고르기 · 보내기 단추가 입력창 상자 안에 있다
            box = page.evaluate("""() => { const r = s => document.querySelector(s).getBoundingClientRect(); const col = r('.chat-col'), th = r('[data-ask-thread]'), cp = r('.composer'), ag = r('#askAgent'), sd = r('#askSend');
                return { width: col.width, below: cp.top >= th.bottom, inside: ag.top > cp.top && ag.bottom < cp.bottom && sd.right <= cp.right && sd.left > ag.right, gap: innerHeight - cp.bottom }; }""")
            assert box['width'] <= 720 and box['below'] and box['inside'] and box['gap'] < 140, box
            # 고른 에이전트의 「하는 일 · 쓰는 도구 서버」는 설명 줄이 아니라 고르기 칸의 툴팁이다
            tip = page.locator('#askAgent').get_attribute('title')
            assert '경보의 원인을 진단한다' in tip and '지식 그래프' in tip and '하는 일' not in page.locator('#askView').inner_text()
            picks.first.click()
            assert page.locator('#askText').input_value() == QUESTIONS[0] and page.locator('#askSend').is_enabled()
            page.locator('#askSend').click()
            now = page.locator('[data-ask-now]')
            now.wait_for(timeout=8000)
            assert world['posted']['question'] == QUESTIONS[0] and world['posted']['agent'] == 'sys:agent'
            assert '지식 그래프 조회' in now.inner_text() and '부르는 중' in now.inner_text()      # 답이 오기 전에 부르는 도구 이름이 보인다
            assert page.evaluate("document.querySelector('[data-ask-now]').getBoundingClientRect().bottom <= document.querySelector('.composer').getBoundingClientRect().top")
            assert picks.count() == 0                                                        # 질문 예는 빈 대화에만
            world['view'] = _view('done', tool_calls=[dict(CALL, running=False, ok=True)], result={'kind': 'answered', 'answer': '절차는 SOP-COOL-11 입니다.', 'evidence': [], 'verified': 1, 'queried': 1})
            page.locator('.ask-answer').wait_for(timeout=8000)
            page.wait_for_function("document.querySelector('[data-ask-now]').hidden")
            assert 'SOP-COOL-11' in page.locator('.ask-answer').inner_text()
            assert page.locator('.ask-a a.go').get_attribute('href') == '#/instances/ask_agent.q1/task/w1' and page.locator('.ask-a a.go').inner_text() == '처리 건에서 보기'
            assert not page.locator('.ask-evidence').evaluate('d => d.open') and '실행 기록과 맞은 근거 1건' in page.locator('.ask-evidence summary').inner_text()
            b.close()
    finally:
        served.close()


def test_실제_AI_로_답할_때의_질문_예는_그_질문에_답할_기본_제공_도구_서버를_쓰는_에이전트에게만_보인다():
    """질문 예 둘은 기본 제공 현장(업무 시스템의 재고 · 가상 설비의 진동)을 묻는다 — 전에는 어느 에이전트를 골라도 보여, 내 도구 서버만 붙인 에이전트에게
    답할 수 없는 질문을 권했다. 에이전트의 질문용 도구 서버(servers)에 그 서버가 있을 때만 그 예가 보인다."""
    from playwright.sync_api import sync_playwright
    mine = dict(AGENT, id='agent:mine', name='내 설비 에이전트', default=False, mine=True, servers=['my-plant'])
    half = dict(AGENT, id='agent:half', name='재고 에이전트', default=False, mine=True, servers=['enterprise', 'my-plant'])
    base = dict(AGENT, servers=['neo4j', 'enterprise', 'hyd-dmn'])
    status = dict(STATUS, agents=[base, half, mine], worker={'ai_mode': 'live', 'replay_questions': []})
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if url.endswith('/api/ask/status'):
            return route.fulfill(json=status)
        if url.endswith('/api/ask'):
            return route.fulfill(json=[])
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'ask')
            picks = page.locator('[data-ask-picks] [data-ask-pick]')
            picks.first.wait_for(timeout=15000)
            shown = {}
            for agent in ('sys:agent', 'agent:half', 'agent:mine'):
                page.select_option('#askAgent', agent)
                page.wait_for_function("n => document.querySelectorAll('[data-ask-picks] [data-ask-pick]').length === n", arg={'sys:agent': 2, 'agent:half': 1, 'agent:mine': 0}[agent])
                shown[agent] = picks.all_inner_texts()
            b.close()
    finally:
        served.close()
    assert len(shown['sys:agent']) == 2 and shown['agent:half'] == [shown['sys:agent'][0]] and '재고' in shown['agent:half'][0], shown
    assert shown['agent:mine'] == [], shown


def test_목록은_읽기_전에_없다고_하지_않고_AI_답과_쿼리는_원문대로이며_사람이_닫은_질문은_초록_점이_아니다():
    """2026-11-25 감사 · 화면 탐사: ① 지난 질문이 있는데 열자마자 「아직 지난 질문이 없습니다」가 1~2초 보였다. ② AI 의 답에 화면 말 바꾸기(UI.words)가
    걸려 학생 MES 의 「작업지시」가 「정비 요청」으로, 사전에 없는 학생 지식 id 가 「원인 표시 이름 미등록」으로 바뀌어 보였다 — 표에 있는 경보 코드만
    이름으로 읽는다. ③ 객체로 넘긴 쿼리가 「[object Object]」로 보였다. ④ 사람이 닫은 질문의 처리 과정 머리에 초록(정상) 점이 붙고 「종료」라 불렀다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    said = '생산 작업지시 WO-12 와 재관측 기록을 보면 cause:apu-air-leak 이고 COOLER_DEGRADATION 경보와는 다릅니다.'
    done = _view('done', tool_calls=[dict(CALL, running=False, ok=True)], result={
        'kind': 'answered', 'answer': said, 'verified': 1, 'queried': 1,
        'evidence': [{'tool': 'mcp__apu-ops__get_status', 'verified': True, 'query': {'asset': 'APU-01', 'window': '1h'}, 'result': 'RUN'}]})
    closed = _view('closed', id='ask_agent.q2', message='사람이 닫은 질문입니다 — 사유: 시연 끝', link='#/instances/ask_agent.q2/task/w1')
    world = {'held': None, 'views': {'ask_agent.q1': done, 'ask_agent.q2': closed}}
    history = [{'id': 'ask_agent.q1', 'question': QUESTIONS[0], 'state': 'done', 'verdict': 'answered', 'agent': done['agent'], 'started': done['started']},
               {'id': 'ask_agent.q2', 'question': QUESTIONS[1], 'state': 'closed', 'agent': closed['agent'], 'started': closed['started']}]

    def answer(route):
        url = route.request.url.split('?')[0]
        if url.endswith('/api/ask/status'):
            return route.fulfill(json=STATUS)
        if url.endswith('/api/ask'):
            world['held'] = route                       # 목록 응답을 잡아 둔다 — 읽기 전의 화면을 잰다
            return None
        for key, view in world['views'].items():
            if url.endswith('/api/ask/' + key):
                return route.fulfill(json=view)
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'ask')
            hist = page.locator('[data-ask-history]')
            page.wait_for_function("() => document.querySelector('[data-ask-history]').innerText.includes('불러오는 중')", timeout=15000)
            assert '아직 지난 질문이 없습니다' not in hist.inner_text()                         # ① 읽기 전에는 「없음」이 아니다
            world['held'].fulfill(json=history)
            page.locator('[data-ask-open="ask_agent.q1"]').wait_for(timeout=10000)
            page.locator('[data-ask-open="ask_agent.q1"]').click()
            page.locator('.ask-answer').wait_for(timeout=8000)
            text = page.locator('.ask-answer').inner_text()
            assert '작업지시 WO-12' in text and '재관측' in text and 'cause:apu-air-leak' in text, text          # ② 원문대로
            code = page.evaluate("UI.patterns.COOLER_DEGRADATION || 'COOLER_DEGRADATION'")              # 표에 있는 경보 코드만 이름으로(이름표가 없으면 코드 그대로)
            assert '정비 요청' not in text and '표시 이름 미등록' not in text and code in text, text
            page.locator('.ask-evidence summary').first.click()
            ev = page.locator('.ask-evidence').inner_text()
            assert '[object Object]' not in ev and '"asset": "APU-01"' in page.locator('.ask-evidence').evaluate('d => d.textContent'), ev   # ③
            page.locator('[data-ask-open="ask_agent.q2"]').click()
            page.wait_for_function("() => (document.querySelector('#askView [data-lv-now]') || {}).textContent?.includes('사람이 닫음')", timeout=8000)
            tone = page.locator('#askView [data-lv-now] .dot').get_attribute('data-tone')
            assert tone not in ('ok', 'run'), tone                                                                 # ④ 초록 · 진행 점이 아니다
            b.close()
    finally:
        served.close()
