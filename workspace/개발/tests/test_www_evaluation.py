"""판단 채점 화면(it/portal/www/evaluation.js) — 화면이 학생에게 어느 경로가 AI 인지 사실대로 말한다.

실제 index.html · evaluation.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(정답표 · 실행 목록 · 경로 안내)만
이 시험이 준다(꼴은 procsvc eval_api — 경로 안내 문장은 서버 judgment_eval.PATH_NOTES 그대로)."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen
from procsvc import judgment_eval


def test_판단_채점_화면은_AI가_판단하는_경로가_지난_처리_건_하나라고_말한다():
    """J4 D3(2026-11-01): 부제가 「AI 판단을 대어 점수를 낸다」였는데 기본 경로(규칙 판단)와 읽기 평가는 AI 모델 없이 돈다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if url.endswith('/api/eval/paths'):
            return route.fulfill(json={'paths': [{'key': k, 'note': v} for k, v in judgment_eval.PATH_NOTES.items()]})
        if url.endswith('/api/eval/items') or url.endswith('/api/eval/runs'):
            return route.fulfill(json=[])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'eval')
            page.wait_for_selector('#evalView [data-eval-ai-note]', timeout=15000)      # 판단 경로 고르기 아래의 안내(채점 조건 칸) — 화면 머리 한 문장과 따로 있다
            sub = page.inner_text('#evalView [data-eval-ai-note]')
            lead = page.inner_text('#evalView .page-head p')
            b.close()
    finally:
        served.close()
    assert 'AI가 판단하는 것은 「지난 처리 건」 하나' in sub and 'AI 판단을 대어' not in sub + lead, (sub, lead)
    assert 'AI 모델 없이' in judgment_eval.PATH_NOTES['evaluate'] and 'AI 모델 없이' in judgment_eval.PATH_NOTES['decide']


def test_정답표의_고르기_후보는_서버가_준_지금_지식뿐이고_고른_것의_id가_저장_요청에_간다():
    """V 8절 9(2026-11-16): 후보를 화면의 정적 이름 사전(names.json)에서 뽑아, 지식 그래프에 없는 업무 거래 이름(「정비 요청 취소」 — skill:cancel-work-order)이
    조치 후보에 섞여 고르면 저장이 400 이었고, 학생이 적재한 조치는 사전에 없어 고를 수 없었다. 후보는 서버(GET /api/eval/choices)가 지금 그래프에서 읽은 것이다."""
    import json
    from playwright.sync_api import sync_playwright
    names = json.loads((WWW / 'names.json').read_text(encoding='utf-8'))
    assert names['skill:cancel-work-order'] == '정비 요청 취소' and names['skill:sop-cool-11']      # 사전에는 둘 다 있다(앞의 것은 그래프에 없다)
    choices = {'cause': [{'id': 'cause:cooler-fin-fouling', 'name': '쿨러 핀 오염'}], 'fm': [{'id': 'fm:student-fm', 'name': '학생이 넣은 고장 유형'}],
               'skill': [{'id': 'skill:sop-cool-11', 'name': '팬 최대 운전'}, {'id': 'skill:student-own-fix', 'name': '학생이 넣은 조치'}, {'id': 'skill:nameless', 'name': None}],
               'evidence': [{'id': 'rule:student-own', 'name': '학생이 넣은 규칙 설명'}], 'rule': [{'id': 'rule:student-own', 'name': '학생이 넣은 규칙 설명'}]}
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    posted = []

    def answer(route):
        req, url = route.request, route.request.url.split('?')[0]
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        if url.endswith('/api/ontology/patterns'):
            return route.fulfill(json=[{'id': 'pattern:cool', 'code': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하', 'failureModes': []}])
        if url.endswith('/api/eval/choices'):
            return route.fulfill(json=choices)
        if url.endswith('/api/eval/golden'):
            return route.fulfill(json={'items': [body['item'] for body in posted], 'storage': 'pg', 'paths': dict(judgment_eval.PATH_NOTES), 'weights': {}, 'max_repeats': 10,
                                       'assets': ['HYD-01'], 'facts': {}})
        if url.endswith('/api/eval/golden/items') and req.method == 'POST':
            posted.append(req.post_data_json)
            return route.fulfill(status=201, json={'item': req.post_data_json['item']})
        if url.endswith('/api/eval/runs'):
            return route.fulfill(json=[])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'eval')
            page.click('#evalView [data-act="view"][data-to="golden"]')
            page.click('#evalView [data-act="new"]')
            page.wait_for_selector('#evalView form [data-f="title"]')
            offered = page.evaluate("() => [...document.querySelectorAll('#evalDl-skill option')].map(o => o.value)")
            assert '학생이 넣은 조치' in offered and '팬 최대 운전' in offered and '정비 요청 취소' not in offered, offered
            assert len(offered) == 3 and all(':' not in o for o in offered), offered      # 이름 없는 항목도 id 가 아니라 종류로 보인다
            page.fill('#evalView [data-f="title"]', '쿨러 성능 저하')
            page.select_option('#evalView [data-f="asset"]', 'HYD-01')
            page.select_option('#evalView [data-f="pattern"]', 'COOLER_DEGRADATION')
            page.fill('#evalView [data-f="cause"]', '쿨러 핀 오염')
            page.fill('#evalView [data-f="failure_mode"]', '학생이 넣은 고장 유형')
            pick = page.locator('#evalView [data-add-to="allowed_top"]')
            pick.fill('정비 요청 취소'); pick.dispatch_event('change')      # 그래프에 없는 것: 적어 넣어도 받지 않는다
            refused = page.inner_text('#evalView [data-msg="form"]')
            picked_after_refusal = page.locator('#evalView [data-picks="allowed_top"] li').count()
            pick.fill('학생이 넣은 조치'); pick.dispatch_event('change')
            ev = page.locator('#evalView [data-add-to="required_evidence"]')
            ev.fill('학생이 넣은 규칙 설명'); ev.dispatch_event('change')
            page.click('#evalView [data-act="save"]')
            page.wait_for_selector('#evalView [data-r="golden"] table')
            row = page.inner_text('#evalView [data-r="golden"] tbody tr')
            b.close()
    finally:
        served.close()
    assert '「정비 요청 취소」: 목록에 있는 이름을 고르세요' in refused and picked_after_refusal == 0
    [body] = posted
    assert body['item']['allowed_top'] == ['skill:student-own-fix'] and body['item']['required_evidence'] == ['rule:student-own']
    assert body['item']['expected'] == {'cause': 'cause:cooler-fin-fouling', 'failure_mode': 'fm:student-fm'}
    assert '학생이 넣은 조치' in row and '학생이 넣은 고장 유형' in row and 'skill:student-own-fix' not in row, row      # 표도 사전에 없는 항목을 이름으로 보인다


def test_서버가_거절한_정답표_저장은_까닭_줄에_그_항목을_화면에_보이는_이름으로_적는다():
    """저장하는 사이 지식에서 지워진 항목(서버 eval_api 의 거절 — 「지금 지식 그래프에 없는 항목이 있습니다: skill:… — …」): 까닭 줄이 고른 줄에 보이는 이름으로 말한다.
    이름을 모르는 id 는 그대로 둔다(고른 줄의 「이름을 찾지 못한 항목 (id)」와 같은 글)."""
    from playwright.sync_api import sync_playwright
    choices = {'cause': [{'id': 'cause:c', 'name': '쿨러 핀 오염'}], 'fm': [{'id': 'fm:f', 'name': '냉각 성능 저하'}], 'skill': [{'id': 'skill:student-own-fix', 'name': '학생이 넣은 조치'}],
               'evidence': [{'id': 'evd:e', 'name': '유온 상승'}], 'rule': []}
    refusal = '지금 지식 그래프에 없는 항목이 있습니다: skill:student-own-fix, evd:gone — 지식에서 지워졌거나 이름이 바뀐 항목입니다. 그 줄을 빼고 목록에서 다시 고르세요'
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        req, url = route.request, route.request.url.split('?')[0]
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        if url.endswith('/api/ontology/patterns'):
            return route.fulfill(json=[{'id': 'pattern:cool', 'code': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하', 'failureModes': []}])
        if url.endswith('/api/eval/choices'):
            return route.fulfill(json=choices)
        if url.endswith('/api/eval/golden'):
            return route.fulfill(json={'items': [], 'storage': 'pg', 'paths': dict(judgment_eval.PATH_NOTES), 'weights': {}, 'max_repeats': 10, 'assets': ['HYD-01'], 'facts': {}})
        if url.endswith('/api/eval/golden/items') and req.method == 'POST':
            return route.fulfill(status=400, json={'detail': refusal})
        if url.endswith('/api/eval/runs'):
            return route.fulfill(json=[])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'eval')
            page.click('#evalView [data-act="view"][data-to="golden"]')
            page.click('#evalView [data-act="new"]')
            page.wait_for_selector('#evalView form [data-f="title"]')
            page.fill('#evalView [data-f="title"]', '쿨러 성능 저하')
            page.select_option('#evalView [data-f="asset"]', 'HYD-01')
            page.select_option('#evalView [data-f="pattern"]', 'COOLER_DEGRADATION')
            page.fill('#evalView [data-f="cause"]', '쿨러 핀 오염')
            page.fill('#evalView [data-f="failure_mode"]', '냉각 성능 저하')
            for field, text in (('allowed_top', '학생이 넣은 조치'), ('required_evidence', '유온 상승')):
                box = page.locator(f'#evalView [data-add-to="{field}"]')
                box.fill(text); box.dispatch_event('change')
            page.click('#evalView [data-act="save"]')
            page.wait_for_function("document.querySelector('#evalView [data-msg=form]')?.textContent.includes('지금 지식 그래프에 없는')", timeout=8000)
            said = page.inner_text('#evalView [data-msg="form"]')
            still_open = page.locator('#evalView form [data-f="title"]').count()
            b.close()
    finally:
        served.close()
    assert '「학생이 넣은 조치」' in said and 'skill:student-own-fix' not in said and 'evd:gone' in said, said
    assert still_open == 1      # 거절된 폼은 고른 값 그대로 남는다
