"""흐름 화면(it/portal/www/flows.js) — 다른 화면에서 바뀐 카탈로그(에이전트)가 다시 열 때 보인다.

실제 index.html · flows.js 를 실제 브라우저(Playwright Chromium)로 열고, 화면의 process 요청(/svc/process/…)은 실제 process 앱(world —
같은 라우트 · 같은 수업 경계)으로 넘긴다. 다른 서비스 요청은 빈 응답이다 — 이 판정과 무관하다."""
import json
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen
from procsvc.course_policy import HANDOVER

FLOW = 'ShiftHandover'
ME = 'user:me'


def test_다른_화면에서_만든_에이전트가_흐름_화면을_다시_열면_단계의_에이전트_고르기에_나온다(world):
    """한바퀴3 고침: 흐름 화면은 카탈로그를 처음 열 때 한 번만 읽어(셸 show 없음), 실라버스 118행에서 만든 인수인계 에이전트를 119행의
    단계 에이전트 고르기에서 고를 수 없었다(새로 고침 전까지)."""
    from playwright.sync_api import sync_playwright
    status, out = world.api('DELETE', f'/api/flows/{FLOW}?by={ME}')
    assert status in (200, 404), out
    status, view = world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})
    assert status == 200, view
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        parts = urlsplit(route.request.url)
        if not parts.path.startswith('/svc/process/'):
            return route.fulfill(json={})
        if parts.path.endswith('/stream'):              # 알림 스트림(SSE)은 끝나지 않는 응답이라 넘기지 않는다 — 이 판정과 무관
            return route.abort()
        path = parts.path[len('/svc/process'):] + (f'?{parts.query}' if parts.query else '')
        body = json.loads(route.request.post_data) if route.request.post_data else None
        status, out = world.api(route.request.method, path, body)
        return route.fulfill(status=status, json=out)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'flows')
            page.locator(f"#flowList [data-open='{FLOW}']").first.click()
            pick = page.locator("#flowEditor select[data-agent='task_draft']")
            pick.wait_for(timeout=15000)
            status, agent = world.api('POST', '/api/agents', {'name': '새 인수인계 에이전트', 'goal': '교대 인계안을 쓴다', 'tools': ['neo4j']})
            assert status in (200, 201), agent
            assert pick.locator(f"option[value='{agent['id']}']").count() == 0, '아직 다시 열지 않았다'
            open_screen(page, 'agents')          # 에이전트 화면에 갔다가
            open_screen(page, 'flows')           # 흐름 화면으로 돌아온다
            page.wait_for_function(f"!!document.querySelector(\"#flowEditor select[data-agent='task_draft'] option[value='{agent['id']}']\")",
                                   timeout=15000)
            b.close()
    finally:
        served.close()


def test_제한_단계의_교대_흐름은_열린_칸만_그리고_저장해도_나머지_단계_설정이_그대로이며_머리의_주_단추_하나로_등록하고_시작한다(world):
    """전에는 고칠 수 없는 칸 백여 개를 꺼진 입력 칸으로 그렸다. 지금은 읽기 전용 표에 서버가 연 칸(흐름 이름 · 초안 단계의 AI 에이전트)만 입력 칸이다 —
    저장 함수가 화면에 없는 칸을 빈 값으로 읽어 시작 조건 · 갈림 조건을 지우지 않는지를 서버에 저장된 단계 설정으로 본다.
    이어서 머리의 주 단추 하나([판본 등록] → [처리 건 시작])로 끝까지 가고, 시작한 결과(「처리 건에서 보기」)가 흐름 화면에 남는지 본다."""
    from playwright.sync_api import sync_playwright
    status, out = world.api('DELETE', f'/api/flows/{FLOW}?by={ME}')
    assert status in (200, 404), out
    status, view = world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})
    assert status == 200, view
    before = world.api('GET', f'/api/flows/{FLOW}')[1]['mapping']
    status, agent = world.api('POST', '/api/agents', {'name': '내 인수인계 에이전트', 'goal': '교대 인계안을 쓴다', 'tools': ['neo4j']})
    assert status in (200, 201), agent
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        parts = urlsplit(route.request.url)
        if not parts.path.startswith('/svc/process/') or parts.path.endswith('/stream'):
            return route.fulfill(json={}) if not parts.path.startswith('/svc/process/') else route.abort()
        path = parts.path[len('/svc/process'):] + (f'?{parts.query}' if parts.query else '')
        status, out = world.api(route.request.method, path, json.loads(route.request.post_data) if route.request.post_data else None)
        return route.fulfill(status=status, json=out)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'flows')
            page.locator(f"#flowList [data-open='{FLOW}']").first.click()
            pick = page.locator("#flowEditor select[data-agent='task_draft']")
            pick.wait_for(timeout=15000)
            # 입력 칸은 열린 것뿐이고 꺼진 칸이 없다
            controls = page.locator('#flowEditor input, #flowEditor select, #flowEditor textarea, #flowEditor button')
            assert page.locator('#flowEditor :disabled').count() == 0
            assert controls.count() == 1 + page.locator('#flowEditor select[data-agent]').count() and page.locator('#flowEditor #flowName').count() == 1
            # 흐름 그림은 상세 칸의 폭을 다 쓰고 창 바닥 가까이까지 찬다(위아래로 빈 띠가 남지 않는다)
            box = page.evaluate("""() => { const c = document.querySelector('#flowPicture .flow-canvas').getBoundingClientRect(), p = document.querySelector('#flowsView').getBoundingClientRect();
                return { left: Math.round(c.left - p.left), right: Math.round(p.right - c.right), bottom: c.bottom, vh: innerHeight }; }""")
            assert box['left'] == 0 and box['right'] == 0 and box['vh'] - box['bottom'] <= 150, box
            pick.select_option(agent['id'])
            # 머리에 주 단추는 하나
            primary = page.locator('#flowHead .pane-acts > button.btn:not([data-variant])')
            assert primary.count() == 1
            page.locator('#flowMore-trigger').click()
            page.locator('#flowMore-menu [data-flow-check]').click()
            page.wait_for_function("document.querySelector('#flowMsg').textContent.includes('단계 설정을 저장했습니다')", timeout=15000)
            after = world.api('GET', f'/api/flows/{FLOW}')[1]['mapping']
            want = json.loads(json.dumps(before))
            want['tasks']['task_draft']['agent'] = agent['id']
            assert after == want, '고르지 않은 칸의 단계 설정이 저장하면서 바뀌었다'
            page.locator('#flowRegister').click()
            page.locator('#flowStartOpen').wait_for(timeout=15000)
            assert page.locator('#flowSteps').is_hidden()                          # 시작만 남은 흐름에는 단계 줄이 없다
            assert page.locator('#flowHead .pane-acts > button.btn:not([data-variant])').count() == 1
            page.locator('#flowStartOpen').click()
            form = page.locator('#flowsStart')
            form.locator("[data-sv='asset']").wait_for(timeout=15000)
            for key, value in {'asset': 'HYD-01', 'shift_label': '다음 교대', 'as_of': '2026-11-16T18:00:00+09:00', 'work_notes': '정비 완료라고 전달받음'}.items():
                form.locator(f"[data-sv='{key}']").fill(value)
            form.locator('[data-go]').click()
            link = page.locator('#flowNote a.go')
            link.wait_for(timeout=15000)
            assert link.get_attribute('href').startswith(f'#/instances/{FLOW}.') and not page.evaluate("document.getElementById('flowsStart').open")
            assert page.evaluate('state.tab') == 'flows'                           # 화면을 떠나지 않고 결과가 이 화면에 남는다
            b.close()
    finally:
        served.close()


def test_다른_화면이_여는_흐름은_시작_단추_대신_그_화면으로_가는_링크를_둔다(world):
    """「에이전트에게 질문하기」는 질문하기 화면이 질문마다 여는 흐름이다 — 흐름 화면에서 「시작 가능」 · [처리 건 시작]으로 보이면 학생이 여기서 시작하는 흐름으로 읽는다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        parts = urlsplit(route.request.url)
        if not parts.path.startswith('/svc/process/') or parts.path.endswith('/stream'):
            return route.fulfill(json={}) if not parts.path.startswith('/svc/process/') else route.abort()
        path = parts.path[len('/svc/process'):] + (f'?{parts.query}' if parts.query else '')
        status, out = world.api(route.request.method, path, json.loads(route.request.post_data) if route.request.post_data else None)
        return route.fulfill(status=status, json=out)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'flows')
            row = page.locator("#flowList [data-open='ask_agent']").first
            row.wait_for(timeout=15000)
            assert row.locator('.tag').inner_text() == '질문하기가 씀'
            row.click()
            link = page.locator('#flowHead a.go')
            link.wait_for(timeout=15000)
            page.wait_for_function("document.querySelector('#flowHead .pane-title p').textContent.includes('질문하기 화면이 시작합니다')", timeout=15000)
            assert link.inner_text() == '질문하기에서 시작' and page.locator('#flowHead #flowStartOpen').count() == 0
            link.click()
            page.wait_for_function("state.tab === 'ask'", timeout=8000)
            b.close()
    finally:
        served.close()


def test_지금_가져올_수_없는_그림을_가져오면_정해진_그림의_안내는_한_번만_나오고_오류_판은_이번_파일의_사실을_말한다(world):
    """감독 걷기(2026-11-16, D3b): 폼 맨 위 안내 판 「지금 가져올 수 있는 그림이 정해져 있습니다 …」와 아래 오류 판 「그림을 가져오지 못했습니다 — (같은 문장)」이
    같은 말을 두 번 했다. 서버(실제 process — 수업 경계)의 거절 문장이 위 안내와 같으면 오류 판은 고른 파일과 그 파일에 적힌 흐름 식별 이름만 말한다."""
    from playwright.sync_api import sync_playwright
    other = HANDOVER['xml'].replace('id="ShiftHandover"', 'id="MyOwnFlow"').replace('"ShiftHandover"', '"MyOwnFlow"')
    assert 'MyOwnFlow' in other
    status, refused = world.api('POST', '/api/flows/import', {'xml': other, 'file_name': 'my-own.bpmn'})
    rule = world.api('GET', '/api/course-access')[1]['reasons']['import_flow']
    assert status == 403 and rule in json.dumps(refused, ensure_ascii=False), (status, refused)      # 서버는 그 문장으로 거절한다(화면 밖의 호출자에게는 그대로)
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        parts = urlsplit(route.request.url)
        if not parts.path.startswith('/svc/process/') or parts.path.endswith('/stream'):
            return route.fulfill(json={}) if not parts.path.startswith('/svc/process/') else route.abort()
        path = parts.path[len('/svc/process'):] + (f'?{parts.query}' if parts.query else '')
        status, out = world.api(route.request.method, path, json.loads(route.request.post_data) if route.request.post_data else None)
        return route.fulfill(status=status, json=out)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'flows')
            page.wait_for_selector('#flowImportOpen, [data-flow-import], #flowPanel', timeout=15000)
            page.get_by_role('button', name='흐름 가져오기').first.click()
            page.wait_for_selector('#flowFile', timeout=8000)
            page.wait_for_function("document.querySelector('[data-import-only]')?.textContent.trim()", timeout=8000)
            page.set_input_files('#flowFile', {'name': 'my-own.bpmn', 'mimeType': 'application/xml', 'buffer': other.encode()})
            page.click('#flowImport')
            page.wait_for_function("document.querySelector('#flowImportMsg')?.textContent.includes('가져오지 못했습니다')", timeout=15000)
            panel, failed, note = page.inner_text('#flowPanel'), page.inner_text('#flowImportMsg'), page.inner_text('[data-import-only]')
            b.close()
    finally:
        served.close()
    assert rule in note and panel.count(rule) == 1 and rule not in failed, (note, failed)      # 정해진 그림의 안내는 위 판에 한 번
    assert 'my-own.bpmn' in failed and 'MyOwnFlow' in failed and '위 안내' in failed, failed      # 오류 판: 무엇이 안 됐는지 · 이번 파일의 사실


def test_파일_고르기_칸은_감싸기_전에_이미_고른_파일이_있으면_그_이름을_보인다():
    """감독 걷기 그림(D3b)과 이 일의 그림: 파일을 골라 [가져오기]까지 눌렀는데 칸에는 「선택한 파일 없음」이었다. 한국어 파일 고르기(ui.js enhanceFiles)는 칸이 그려진
    조금 뒤에 붙는데, 그 전에 고른 파일은 이름이 반영되지 않았다(change 를 놓침). 파일이 든 칸을 감싸면 그 이름으로 시작하고, 빈 칸은 「선택한 파일 없음」이다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', lambda route: route.fulfill(json={}))
            page.goto(served.url + '/index.html')
            page.wait_for_function("typeof UI !== 'undefined' && !!UI.enhanceFiles")
            got = page.evaluate("""() => {
              const make = file => { const host = document.createElement('div'), input = document.createElement('input'); input.type = 'file';      // 문서에 붙이지 않은 칸(저절로 감싸지지 않는다)
                if (file) { const dt = new DataTransfer(); dt.items.add(new File(['x'], file)); input.files = dt.files; }
                host.append(input); UI.enhanceFiles(host); return host.querySelector('.file-name').textContent; };
              return [make('my-own.bpmn'), make('')];
            }""")
            b.close()
    finally:
        served.close()
    assert got == ['my-own.bpmn', '선택한 파일 없음'], got
