"""서버가 적는 진행 기록을 화면이 따라 읽는다(it/portal/www/liveStream.js 의 hydLive.track, 그것을 쓰는 화면).

실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 진행 기록은 실제 모듈(procsvc/progress.py)과 실제 읽기 라우트(GET /api/progress/{id})다.
이 시험이 주는 것은 브라우저 밖의 「오래 걸리는 일」 하나뿐이다: 화면이 보낸 요청을 받아 진행 기록을 열고(progress.tracked — 네 동작의 라우트가 쓰는
같은 길), 시험이 풀어 주는 대로 한 걸음씩 단계를 적다가 끝난다."""
import asyncio
import json
import queue

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served
from procsvc import config_bundle, progress


class Job:
    """서버 쪽의 오래 걸리는 일. do(걸음)으로 넣은 걸음을 일하는 스레드가 차례로 하고, end(결과)로 끝난다. 받은 요청 본문은 bodies 에 남는다."""

    def __init__(self):
        self.steps, self.bodies = queue.Queue(), []

    def run(self, p):
        while True:
            step = self.steps.get(timeout=60)
            if not callable(step):
                return step
            step(p)

    def do(self, step):
        self.steps.put(step)

    def end(self, result):
        self.steps.put(result)

    def crash(self, reason):
        """일이 예외로 끝난다(요청은 500, 진행 기록은 실패)."""
        def boom(p):
            raise RuntimeError(reason)
        self.steps.put(boom)


def _serve(job, path):
    api = FastAPI()
    progress.register(api)

    @api.post(path)
    async def run_job(body: dict):
        job.bodies.append(body)
        return await asyncio.get_running_loop().run_in_executor(None, progress.tracked(body.get('request_id'), 'job', job.run))

    @api.get('/api/inbox/users')
    async def users():
        return [{'id': 'user:me', 'name': '담당자', 'roles': []}]
    app = FastAPI()
    app.mount('/svc/process', api)
    app.mount('/', StaticFiles(directory=WWW, html=True))
    return Served(app)


class Wire:
    """브라우저와 서버 사이: 진행 읽기 · 일 요청 · 담당자 목록은 실제 서버로 보내고(진행 읽기는 세고, 끊을 수 있다) 나머지 process 응답은 빈 값."""

    def __init__(self, path, answers=None):
        self.path, self.reads, self.cut, self.answers = path, 0, False, answers or {}

    def __call__(self, route):
        url = route.request.url.split('?')[0]
        if '/api/progress/' in url:
            self.reads += 1
            return route.abort() if self.cut else route.continue_()
        if (route.request.method == 'POST' and url.endswith(self.path)) or url.endswith('/api/inbox/users'):
            return route.continue_()
        return route.fulfill(json=next((body for tail, body in self.answers.items() if url.endswith(tail)), {}))


def _open(page, tab):
    """화면을 연다 — 메뉴 줄의 모양(다른 시험 test_www_shell 이 본다)에 기대지 않고 포털의 화면 전환 함수로."""
    page.wait_for_function('typeof selectTab === "function"')
    page.evaluate('tab => selectTab(tab)', tab)
    assert page.evaluate('() => state.tab') == tab, f'{tab} 화면이 열리지 않았다'


STEPS_JS = "sel => [...document.querySelectorAll(sel + ' .lv-step')].map(n => n.className.replace('lv-step ', '') + ':' + n.querySelector('b').textContent)"


def _wait_steps(page, sel, want):
    page.wait_for_function(f"([sel, want]) => JSON.stringify(({STEPS_JS})(sel)) === want", arg=[sel, json.dumps(want, ensure_ascii=False, separators=(',', ':'))],
                           timeout=8000)


def test_진행_단계가_서버가_적는_대로_하나씩_채워지고_요청이_끝나면_읽기를_멈춘다():
    """사용자 2026-11-14 「처리 과정이 블랙박스 X」: 채점 · 시험 비교 · 출발본 · 연결 검사는 「…하는 중 · 걸린 시간」뿐이었다."""
    from playwright.sync_api import sync_playwright
    job, wire = Job(), Wire('/api/job')
    served = _serve(job, '/api/job')
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', wire)
            page.goto(served.url + '/index.html')
            page.wait_for_function('!!(window.hydLive && window.hydLive.track)')
            page.evaluate("""() => {
              const host = document.createElement('div'); host.id = 'trackA'; document.querySelector('main').prepend(host);
              const T = window.T = hydLive.track({ text: '기준으로 되돌리는 중' });
              T.mount(host);
              postJ(API.process + '/api/job', { request_id: T.id }).then(r => { window.jobResult = r; }, e => { window.jobError = e.message; }).finally(() => T.stop());
            }""")
            # 서버가 아직 아무 단계도 적지 않았다: 글과 걸린 시간만 — 지어낸 단계나 진행률은 없다
            page.wait_for_function('window.T.reads >= 1', timeout=8000)
            assert page.inner_text('#trackA .lv-wait-line b') == '기준으로 되돌리는 중' and page.locator('#trackA .lv-wait-line .lv-time').count() == 1
            assert page.locator('#trackA .lv-step').count() == 0
            job.do(lambda p: (p.plan([('check', '진행 중인 처리 건 확인'), ('flows', '가져온 흐름 지우기')]), p.start('check')))
            _wait_steps(page, '#trackA', ['run:진행 중인 처리 건 확인', 'wait:가져온 흐름 지우기'])
            job.do(lambda p: (p.done('check', '막는 처리 건 없음'), p.start('flows')))
            _wait_steps(page, '#trackA', ['ok:진행 중인 처리 건 확인', 'run:가져온 흐름 지우기'])
            assert page.inner_text('#trackA .lv-step.ok .lv-note') == '막는 처리 건 없음'
            # 화면이 다시 그려져 자리가 바뀌어도 같은 목록이 새 자리로 옮겨 간다
            page.evaluate("""() => { document.getElementById('trackA').remove();
              const host = document.createElement('div'); host.id = 'trackB'; document.querySelector('main').prepend(host); T.mount(host); }""")
            _wait_steps(page, '#trackB', ['ok:진행 중인 처리 건 확인', 'run:가져온 흐름 지우기'])
            # 일하다 알게 된 단계는 뒤에 붙고, 앞 단계의 상태는 그대로다. 실패한 단계에는 사유가 남는다
            job.do(lambda p: (p.done('flows', '판본 2'), p.plan([('item:0', '쿨러 성능 저하')]), p.start('item:0')))
            _wait_steps(page, '#trackB', ['ok:진행 중인 처리 건 확인', 'ok:가져온 흐름 지우기', 'run:쿨러 성능 저하'])
            # 진행을 읽지 못하면 그 사실을 한 줄로 말하고, 다시 읽히면 그 줄을 거둔다
            wire.cut = True
            page.wait_for_selector('#trackB [data-lv-track-err]:not([hidden])', timeout=8000)
            assert page.inner_text('#trackB [data-lv-track-err]').startswith('진행 상황을 읽지 못했습니다')
            assert '끝나면 결과가 보입니다' in page.inner_text('#trackB [data-lv-track-err]')
            wire.cut = False
            page.wait_for_selector('#trackB [data-lv-track-err]', state='hidden', timeout=8000)
            # 자리가 화면에서 사라진 동안(다른 화면으로 다시 그려짐)에는 읽지 않는다
            page.evaluate("() => { window.keptHost = document.getElementById('trackB'); window.keptHost.remove(); }")
            page.wait_for_timeout(1200)
            reads = wire.reads
            page.wait_for_timeout(2500)
            assert wire.reads == reads, '자리가 화면에 없는데도 진행을 계속 읽는다'
            page.evaluate("() => document.querySelector('main').prepend(window.keptHost)")
            job.do(lambda p: p.fail('item:0', '판단 엔진에 연결하지 못했습니다'))
            _wait_steps(page, '#trackB', ['ok:진행 중인 처리 건 확인', 'ok:가져온 흐름 지우기', 'fail:쿨러 성능 저하'])
            assert page.inner_text('#trackB .lv-step.fail .lv-note') == '판단 엔진에 연결하지 못했습니다'
            # 요청이 끝나면 읽기를 멈춘다
            job.end({'ok': True})
            page.wait_for_function('window.jobResult && window.jobResult.ok === true', timeout=8000)
            page.wait_for_timeout(1200)                                               # 끝날 때 날아가 있던 읽기 하나
            reads = wire.reads
            page.wait_for_timeout(3000)
            assert wire.reads == reads, '요청이 끝났는데도 진행을 계속 읽는다'
            # 서버 기록이 끝내 생기지 않는 요청(받기 전에 거절 · 연결 실패)도, 그 요청이 끝난 자리에서 stop() 하면 읽기를 멈춘다
            page.evaluate("""() => { const host = document.createElement('div'); host.id = 'trackC'; document.querySelector('main').prepend(host);
              window.T2 = hydLive.track({ text: '연결 검사 중' }); T2.mount(host); }""")
            page.wait_for_function('window.T2.reads >= 2', timeout=8000)
            assert page.locator('#trackC .lv-step').count() == 0 and not page.locator('#trackC [data-lv-track-err]').is_visible()   # 기록 없음은 오류가 아니다
            page.evaluate('window.T2.stop()')
            page.wait_for_timeout(1200)
            reads = wire.reads
            page.wait_for_timeout(3000)
            assert wire.reads == reads, 'stop() 뒤에도 진행을 계속 읽는다'
            b.close()
    finally:
        served.close()


def test_기준으로_되돌리기_화면은_요청에_요청_번호를_싣고_서버가_적는_단계를_채우다가_끝나면_지운_것을_보인다():
    """관리 화면의 [기준으로 되돌리기](configBundle.js) — 확인 대화상자가 무엇을 지우고 무엇을 남기는지 말하고, 도는 동안 단계가 채워진다."""
    from playwright.sync_api import sync_playwright
    job, wire = Job(), Wire('/api/config/reset')
    served = _serve(job, '/api/config/reset')
    plan = [config_bundle.CHECK_STEP, *config_bundle.reset_plan(True)]              # 실제 되돌리기가 적는 단계 그대로
    names = dict(plan)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', wire)
            page.goto(served.url + '/index.html')
            _open(page, 'admin')
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            # 절의 글: 지우는 것에 지식(적재한 문서 · 표 정의 · 화면에서 만든 조치 방법)이 들어 있고, 남는 것은 한 줄이다
            what = page.inner_text('#cfgResetWhat')
            assert '내가 적재한 문서의 지식' in what and '업무 DB 표 정의' in what and '화면에서 만든 조치 방법' in what
            assert page.locator('#cfgResetWhat [data-reset-keeps]').count() == 1 and '처리 건과 처리 건 기록' in page.inner_text('#cfgResetWhat [data-reset-keeps]')
            page.locator('#cfgReset').click()
            said = page.inner_text('dialog.confirm-dialog')
            # 확인 창은 지우는 것과 남는 것(그리고 그것을 되돌리는 자리)을 둘 다 말한다. 지식은 이제 지우는 쪽이다 — 「남는 것」에서 문서 등록 · 조치 방법을 가리키지 않는다
            lost, kept = said.split('남는 것:')
            assert '내가 적재한 문서의 지식' in lost and '화면에서 만든 조치 방법' in lost and '업무 DB 표 정의' in lost
            assert '「지식 › 문서 등록」' not in said and '「지식 › 조치 방법」' not in said and '이 단추만으로 처음 상태가 되지는 않습니다' not in said
            assert '지운 흐름으로 끝난 처리 건만 목록에서 숨깁니다' in kept and '「유압 설비 › 결함 시뮬레이션」의 [설비 초기화] · [업무 데이터 초기화]' in kept and '기본 제공 문서의 지식' in kept
            assert '업무분장' not in said and 'A · B · C' not in said
            for line in config_bundle.RESET_KEPT:      # 서버가 「남긴 것」으로 돌려주는 줄마다, 화면이 미리 말하는 「남는 것」에 그 줄의 머리말이 있다
                assert line.split(' — ')[0].split('(')[0].split(' · ')[0][:8] in kept, line
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            job.do(lambda p: (p.plan(plan), p.start('check')))
            _wait_steps(page, '#cfgResetResult', ['run:' + names['check']] + ['wait:' + label for key, label in plan[1:]])
            [body] = job.bodies
            assert body['by'] == 'user:me' and progress.read(body['request_id'])['state'] == 'running'      # 화면이 실은 번호의 기록을 서버가 연다
            assert [k for k, _ in plan[:4]] == ['check', 'knowledge_reset', 'deploy_reset', 'flows_reset']      # 지식을 맨 먼저 되돌린다(서버 _reset_steps)
            job.do(lambda p: (p.done('check', '막는 처리 건 없음'), p.start('knowledge_reset'), p.done('knowledge_reset', '적재한 문서 판 1개'),
                              p.start('deploy_reset'), p.done('deploy_reset', '이미 기준 흐름입니다'), p.start('flows_reset')))
            _wait_steps(page, '#cfgResetResult', ['ok:' + names['check'], 'ok:' + names['knowledge_reset'], 'ok:' + names['deploy_reset'], 'run:' + names['flows_reset']]
                        + ['wait:' + label for key, label in plan[4:]])
            assert page.locator('#cfgReset').is_disabled() and page.inner_text('#cfgReset').startswith('되돌리는 중')
            # 실제 되돌리기의 응답 꼴(reset_summary): 지운 것 · 남긴 것 · 지금 없는 기본 제공 문서. 도구 서버를 만들 수 없는 단계라 내 서버를 남긴 경우다
            steps = [{'step': 'knowledge_reset', 'result': {'documents': [{'filename': 'my.md', 'batch': 'b2', 'restored_batch': None}], 'skills': [{'id': 'skill:x'}], 'ddl_batches': [],
                                                           'base_missing': ['HM-8_cooler-fan-manual.md']}},
                     {'step': 'agents_reset', 'result': {'agents': 2, 'skills': 0, 'roles': 0, 'assignments': 0}},
                     {'step': 'mcp_reset', 'result': {'removed_servers': [], 'removed_secrets': 0, 'kept_servers': ['my-shop'], 'kept_secrets': 1, 'locked': '지금 단계에서는 도구 서버를 등록할 수 없습니다'}}]
            summary = config_bundle.reset_summary(steps)
            job.end({'message': '기준으로 되돌렸습니다', **summary, 'steps': [{'step': k, 'label': label, 'text': '없음'} for k, label in plan[1:]]})
            page.wait_for_function("document.querySelector('#cfgResetResult').textContent.includes('지운 것')", timeout=8000)
            shown = page.inner_text('#cfgResetResult')
            for line in summary['removed'] + summary['kept']:
                assert line in shown, line
            assert '적재한 문서 판 1개' in shown and '화면에서 만든 조치 방법 1개' in shown and '내 도구 서버 1개와 비밀 값 1개' in shown and '지금 단계에서는 도구 서버를 등록할 수 없습니다' in shown
            assert 'HM-8_cooler-fan-manual.md' in page.inner_text('#cfgResetResult [data-reset-missing]') and '시작 파일을 다시 실행' in shown
            assert page.locator('#cfgResetResult details.fold').count() == 1 and not page.locator('#cfgResetResult details.fold .evid').is_visible()      # 단계별 결과는 접혀 있다
            assert page.locator('#cfgResetResult .lv-step').count() == 0 and not page.locator('#cfgReset').is_disabled()
            page.wait_for_timeout(1200)
            reads = wire.reads
            page.wait_for_timeout(3000)
            assert wire.reads == reads, '되돌리기가 끝났는데도 진행을 계속 읽는다'
            b.close()
    finally:
        served.close()


def test_출발본_불러오기_화면은_파일과_요청_번호를_싣고_서버가_적는_단계를_채우다가_멈추면_그_까닭을_보인다():
    """관리 화면의 [불러오기](configBundle.js) — 길면 3분인 일이다. 도는 동안 단계가 채워지고, 서버가 멈추면 진행 목록 자리에 서버의 까닭이 남는다."""
    from playwright.sync_api import sync_playwright
    job, wire = Job(), Wire('/api/config/import')
    served = _serve(job, '/api/config/import')
    plan = [*config_bundle.IMPORT_HEAD, *config_bundle.reset_plan(False), *config_bundle.STEPS, config_bundle.VERIFY_STEP]      # 실제 불러오기가 적는 단계 그대로
    bundle = {'format': config_bundle.FORMAT, 'format_version': config_bundle.FORMAT_VERSION, 'summary': {'roles': 1, 'flows': 0, 'deployments': 0, 'provided_flows': 3},
              'content': {'roles': [{'id': 'role:u-x', 'name': '내 역할', 'kind': 'manager'}]}}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', wire)
            page.goto(served.url + '/index.html')
            _open(page, 'admin')
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            page.set_input_files('#cfgFile', {'name': '출발본.json', 'mimeType': 'application/json', 'buffer': json.dumps(bundle, ensure_ascii=False).encode()})
            page.wait_for_function("document.querySelector('#cfgImportMsg').textContent.includes('역할 1개')", timeout=8000)
            # 파일의 요약: 서버가 내 것(flows · deployments)과 기본 제공 흐름(provided_flows)을 갈라 센 수를 그대로 말한다
            assert page.inner_text('#cfgImportMsg') == '출발본.json — 역할 1개 · 함께 담긴 기본 제공 흐름 3개(지금 배포된 판본)'
            page.locator('#cfgImport').click()
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            job.do(lambda p: (p.plan(plan), p.start('validate'), p.done('validate'), p.start('check')))
            _wait_steps(page, '#cfgImportResult', ['ok:' + plan[0][1], 'run:' + plan[1][1]] + ['wait:' + label for key, label in plan[2:]])
            [body] = job.bodies
            assert body['bundle'] == bundle and body['by'] == 'user:me' and progress.read(body['request_id'])['state'] == 'running'
            assert page.locator('#cfgImport').is_disabled() and page.inner_text('#cfgImport').startswith('불러오는 중')
            job.crash('진행 중인 처리 건이 있어 불러오지 않았습니다')
            page.wait_for_function("document.querySelector('#cfgImportMsg').textContent.trim() !== ''", timeout=8000)
            assert page.locator('#cfgImportResult .lv-step').count() == 0 and not page.locator('#cfgImport').is_disabled()
            seen = progress.read(body['request_id'])
            assert seen['state'] == 'failed' and [s['state'] for s in seen['steps'][:3]] == ['ok', 'fail', 'wait']
            _reads_stop(page, wire, '불러오기가 끝났는데도 진행을 계속 읽는다')
            b.close()
    finally:
        served.close()


def test_등록된_도구_서버의_연결_검사는_서버가_적는_연결_단계를_그_서버_상세에_채우다가_끝나면_목록을_다시_읽는다():
    """도구 연결 화면(mcp.js)에서 등록된 서버를 골라 누르는 [연결 검사] — 단계는 실제 검사가 적는 것(mcp_check.check_steps)에 저장 단계가 붙는다."""
    from playwright.sync_api import sync_playwright
    from procsvc import mcp_check, mcp_registry
    server = {'name': 'tool-wear', 'transport': 'streamable_http', 'url': 'http://host.docker.internal:8301/mcp', 'headers': {}, 'config_error': None,
              'agents': [], 'tasks': [], 'origin': 'user', 'origin_text': '내가 등록', 'mine': True, 'editable': True, 'selectable': True, 'reason': None,
              'description': None, 'check': {'status': 'ok', 'checked_at': '2026-11-01T09:24:23Z', 'tool_count': 1}, 'read_confirmed': [], 'secrets': []}
    path = '/api/mcp/servers/tool-wear/check'
    job, wire = Job(), Wire(path, {'/api/mcp/servers/tool-wear/tools': {'status': 'ok', 'tools': [{'name': 'read_tool_wear', 'read': True}]},
                                   '/api/mcp/servers': {'servers': [server], 'list_timeout_s': 5}})
    served = _serve(job, path)
    plan = [*mcp_check.check_steps({'transport': 'streamable_http'}), mcp_registry.SAVE_STEP]
    names = dict(plan)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', wire)
            page.goto(served.url + '/index.html')
            _open(page, 'mcp')
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            page.locator("#mcpServers [data-name='tool-wear']").click()
            page.locator('#mcpProbe').click()
            job.do(lambda p: (p.plan(plan), p.start('initialize')))
            _wait_steps(page, '#mcpDetail', ['run:' + names['initialize'], 'wait:' + names['tools'], 'wait:' + names['save']])
            [body] = job.bodies
            assert body['by'] == 'user:me' and progress.read(body['request_id'])['state'] == 'running'
            job.do(lambda p: (p.done('initialize', '공구 서버 1.0'), p.start('tools'), p.done('tools', '도구 1개'), p.start('save')))
            _wait_steps(page, '#mcpDetail', ['ok:' + names['initialize'], 'ok:' + names['tools'], 'run:' + names['save']])
            job.end({'name': 'tool-wear', 'check': {'status': 'ok', 'tools': [{'name': 'read_tool_wear'}]}, 'state': {}})
            page.wait_for_function("document.querySelector('#mcpDetail') && !document.querySelector('#mcpDetail .lv-step') "
                                   "&& document.querySelector('#mcpDetail').textContent.includes('도구 1개')", timeout=8000)      # 끝난 뒤 다시 읽은 서버 상태
            _reads_stop(page, wire, '연결 검사가 끝났는데도 진행을 계속 읽는다')
            b.close()
    finally:
        served.close()


def test_도구_서버_등록_폼의_연결_검사는_서버가_적는_연결_단계를_채우다가_끝나면_검사_결과를_보인다():
    """도구 연결 화면(mcp.js)의 [연결 검사만] — 단계 이름은 실제 검사가 적는 것(mcp_check.check_steps) 그대로."""
    from playwright.sync_api import sync_playwright
    from procsvc import mcp_check
    job, wire = Job(), Wire('/api/mcp/check', {'/api/mcp/servers': {'servers': [], 'list_timeout_s': 5}})
    served = _serve(job, '/api/mcp/check')
    plan = mcp_check.check_steps({'transport': 'streamable_http'})
    names = dict(plan)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', wire)
            page.goto(served.url + '/index.html')
            _open(page, 'mcp')
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            page.locator('#mcpAdd').click()
            page.locator("#mcpForm [data-f='name']").fill('my-rows')
            page.locator("#mcpForm [data-f='url']").fill('http://host.docker.internal:8301/mcp')
            page.locator('#mcpDry').click()
            job.do(lambda p: (p.plan(plan), p.start('initialize')))
            _wait_steps(page, '#mcpFormResult', ['run:' + names['initialize'], 'wait:' + names['tools']])
            [body] = job.bodies
            assert (body['name'], body['by']) == ('my-rows', 'user:me') and progress.read(body['request_id'])['state'] == 'running'
            job.do(lambda p: (p.done('initialize', '학생 서버 1.0'), p.start('tools')))
            _wait_steps(page, '#mcpFormResult', ['ok:' + names['initialize'], 'run:' + names['tools']])
            assert page.inner_text('#mcpFormResult .lv-step.ok .lv-note') == '학생 서버 1.0'
            job.end({'check': {'status': 'ok', 'tools': [], 'elapsed_ms': 12}, 'config': {}, 'gate': None, 'warnings': []})
            page.wait_for_function("document.querySelector('#mcpFormResult').textContent.includes('연결 검사를 통과했습니다')", timeout=8000)
            assert page.locator('#mcpFormResult .lv-step').count() == 0
            page.wait_for_timeout(1200)
            reads = wire.reads
            page.wait_for_timeout(3000)
            assert wire.reads == reads, '연결 검사가 끝났는데도 진행을 계속 읽는다'
            b.close()
    finally:
        served.close()


def _reads_stop(page, wire, what):
    page.wait_for_timeout(1200)
    reads = wire.reads
    page.wait_for_timeout(3000)
    assert wire.reads == reads, what


def test_시험_비교_화면은_서버가_적는_단계를_채우고_화면이_다시_그려져도_이어_보이며_실패로_끝나도_읽기를_멈춘다():
    """에이전트 시험 비교(compare.js) — 이 화면은 무엇이든 바뀌면 통째로 다시 그린다. 도는 중의 진행 목록이 그때 사라지지 않아야 한다."""
    from playwright.sync_api import sync_playwright
    from procsvc import agent_trials
    options = {'scenarios': agent_trials.SCENARIOS, 'tenant_servers': [],
               'agents': [{'id': 'sys:agent', 'name': '판단 에이전트', 'goal': '설비 이상 판단', 'model': None, 'tools': [], 'skills': [], 'trial_note': None}]}
    job, wire = Job(), Wire('/api/agent-trials/run', {'/api/agent-trials/options': options})
    served = _serve(job, '/api/agent-trials/run')
    plan = [('input', '입력 스냅숏 준비'), ('side:0', '에이전트 A 시험'), ('side:1', '에이전트 B 시험'), ('compare', '두 결과 비교')]
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', wire)
            page.goto(served.url + '/index.html')
            _open(page, 'compare')
            page.wait_for_selector("#compareView [data-f='scenario']", timeout=8000)
            page.select_option("#compareView [data-f='scenario']", 'cooler')
            page.locator("#compareView [data-act='run']").click()
            job.do(lambda p: (p.plan(plan), p.start('input')))
            _wait_steps(page, "#compareView [data-r='result']", ['run:입력 스냅숏 준비', 'wait:에이전트 A 시험', 'wait:에이전트 B 시험', 'wait:두 결과 비교'])
            [body] = job.bodies
            assert body['scenario'] == 'cooler' and progress.read(body['request_id'])['state'] == 'running'
            page.select_option("#compareView [data-f='input']", 'latest')                # 화면이 통째로 다시 그려진다
            job.do(lambda p: (p.done('input', '새 입력 스냅숏을 만듦'), p.start('side:0')))
            _wait_steps(page, "#compareView [data-r='result']", ['ok:입력 스냅숏 준비', 'run:에이전트 A 시험', 'wait:에이전트 B 시험', 'wait:두 결과 비교'])
            assert page.locator("#compareView [data-r='result'] .lv-steps").count() == 1       # 목록은 하나다(다시 그릴 때마다 늘지 않는다)
            job.crash('판단 서비스(agent)에 연결하지 못했습니다')
            page.wait_for_function("document.querySelector('#compareView').textContent.includes('시험을 실행하지 못했습니다')", timeout=8000)
            assert page.locator('#compareView .lv-step').count() == 0 and not page.locator("#compareView [data-act='run']").is_disabled()
            seen = progress.read(body['request_id'])
            assert seen['state'] == 'failed' and [s['state'] for s in seen['steps']] == ['ok', 'fail', 'wait', 'wait']
            _reads_stop(page, wire, '시험 비교가 끝났는데도 진행을 계속 읽는다')
            b.close()
    finally:
        served.close()


def test_판단_채점_화면은_항목이_끝날_때마다_서버가_적는_결과를_채우고_끝나면_읽기를_멈춘다():
    """판단 채점(evaluation.js) — 정답표 읽기 · 지식 상태 읽기 뒤에 항목 단계가 붙는다(서버는 정답표를 읽은 뒤에야 항목을 안다)."""
    from playwright.sync_api import sync_playwright
    from procsvc import judgment_eval as je
    item = je.validate_item({'id': 'cooler-auto', 'title': '쿨러 성능 저하', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {},
                             'expected': {'cause': 'cause:a', 'failure_mode': 'fm:a'}, 'allowed_top': ['skill:a'], 'forbidden': [],
                             'required_evidence': ['evd:a']})
    golden = {'items': [item], 'storage': 'pg', 'paths': je.PATH_NOTES, 'weights': je.DEFAULT_WEIGHTS, 'max_repeats': je.MAX_REPEATS,
              'assets': ['HYD-01'], 'facts': je.FACT_CHOICES, 'empty_note': None}
    job, wire = Job(), Wire('/api/eval/runs', {'/api/eval/golden': golden, '/api/eval/runs': [],
                                               '/api/ontology/patterns': [{'code': 'COOLER_DEGRADATION', 'name': '냉각 성능 저하'}]})
    served = _serve(job, '/api/eval/runs')
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', wire)
            page.goto(served.url + '/index.html')
            _open(page, 'eval')
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            page.wait_for_selector("#evalView [data-act='run']:not([disabled])", timeout=8000)
            page.locator("#evalView [data-act='run']").click()
            job.do(lambda p: (p.plan([('golden', '정답표 읽기'), ('knowledge', '지식 상태 읽기')]), p.start('golden')))
            _wait_steps(page, "#evalView [data-r='live']", ['run:정답표 읽기', 'wait:지식 상태 읽기'])
            [body] = job.bodies
            assert (body['path'], body['by'], body['repeats']) == ('decide', 'user:me', 1) and progress.read(body['request_id'])['state'] == 'running'
            job.do(lambda p: (p.done('golden', '항목 1개'), p.start('knowledge'), p.done('knowledge'),
                              p.plan([('item:0', item['title']), ('save', '채점 기록 저장')]), p.start('item:0')))
            _wait_steps(page, "#evalView [data-r='live']", ['ok:정답표 읽기', 'ok:지식 상태 읽기', 'run:쿨러 성능 저하', 'wait:채점 기록 저장'])
            job.do(lambda p: (p.done('item:0', '항목 1/1 끝 · 100.0점 · 원인 맞음 · 1위 조치 맞음'), p.start('save')))
            _wait_steps(page, "#evalView [data-r='live']", ['ok:정답표 읽기', 'ok:지식 상태 읽기', 'ok:쿨러 성능 저하', 'run:채점 기록 저장'])
            assert '항목 1/1 끝 · 100.0점' in page.inner_text("#evalView [data-r='live'] [data-step='item:0'] .lv-note")
            # 진행 막대는 서버가 적은 항목 단계를 센 값이다(항목 1개 가운데 1개 끝남) — 항목 단계가 생기기 전에는 없다
            assert page.inner_text("#evalView [data-r='live'] .io-progress [data-r='count']") == '항목 1개 가운데 1개 끝남'
            assert page.get_attribute("#evalView [data-r='live'] [role='progressbar']", 'aria-valuenow') == '1'
            assert page.locator("#evalView [data-act='run']").is_disabled() and page.inner_text("#evalView [data-act='run']").startswith('채점하는 중')
            job.crash('채점 기록을 저장하지 못했습니다')
            page.wait_for_selector("#evalView [data-act='run']:not([disabled])", timeout=8000)
            assert page.locator('#evalView .lv-step').count() == 0
            assert '채점하지 못했습니다' in page.inner_text("#evalView [data-r='live'] [role='alert']")      # 실시간 상자가 있던 자리에 왜 안 됐는지가 남는다
            _reads_stop(page, wire, '채점이 끝났는데도 진행을 계속 읽는다')
            b.close()
    finally:
        served.close()
