"""실시간 표시(it/portal/www/liveStream.js 의 hydStream · hydLive) — 오래 걸리는 일의 과정이 화면에 흘러나온다.

실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 것만 이 시험이 준다: process 응답(문서 등록 · 추출 시작 · 추출 상태 ·
작업 행)과 실시간 연결(EventSource — 서버의 /api/events/stream 대역, 시험이 이벤트를 밀어 넣고 끊는다).
응답의 꼴: 추출 상태 = procsvc manual_extraction.result(status · workitem · preview), 작업 행 = instances.workitem_view(작업 행 + events),
이벤트 = agent-worker worker/events.py 의 행(task_started · tool_usage_started/finished · task_completed)."""
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

SRC, INST, WID = 'src-1', 'manual_source_extraction.t1', 'wi-1'

# 서버의 실시간 연결 대역: 시험이 __sse.push(이벤트)로 밀고 __sse.drop()으로 끊는다(끊긴 동안 새 연결은 바로 실패한다)
FAKE_ES = r"""
window.__sse = { list: [], up: true };
class FakeES {
  constructor(url) { this.url = url; this.readyState = 0; this.l = {}; __sse.list.push(this);
    setTimeout(() => { if (this.readyState === 2) return; if (__sse.up) { this.readyState = 1; this.onopen && this.onopen(); } else { this.readyState = 2; this.onerror && this.onerror(); } }, 30); }
  addEventListener(t, fn) { (this.l[t] = this.l[t] || []).push(fn); }
  close() { this.readyState = 2; }
}
FakeES.CONNECTING = 0; FakeES.OPEN = 1; FakeES.CLOSED = 2;
window.EventSource = FakeES;
__sse.push = e => { const es = __sse.list.filter(x => x.readyState === 1 && /events\/stream/.test(x.url)).at(-1); if (!es) throw new Error('열린 실시간 연결이 없다'); es.onmessage({ data: JSON.stringify(e) }); };
__sse.drop = () => { __sse.up = false; __sse.list.forEach(es => { if (es.readyState === 1) { es.readyState = 2; es.onerror && es.onerror(); } }); };
"""


class Extraction:
    """서버 쪽 사실: 추출 작업 하나(작업 행 하나)와 그 실행 이벤트. 화면이 읽은 횟수를 센다."""

    def __init__(self):
        self.status, self.events, self.preview, self.reads, self.n = 'IN_PROGRESS', [], None, 0, 0

    def event(self, event_type, data, stored=True):
        """이벤트 하나. stored=False 면 작업 행 다시 읽기에는 아직 없는 것(실시간 연결로만 온다) — 줄이 실시간 연결에서 붙는지를 가른다."""
        self.n += 1
        e = dict(id=f'ev-{self.n}', timestamp=datetime.now(timezone.utc).isoformat(timespec='milliseconds'), stream_cursor=f'{self.n:06d}', event_type=event_type,
                 job_id='run-1', todo_id=WID, proc_inst_id=INST, data=data)
        if stored:
            self.events.append(e)
        return e

    def answer(self, route):
        url, method = route.request.url.split('?')[0], route.request.method
        if url.endswith('/api/kg/manuals/preview'):
            return route.fulfill(json=dict(source_id=SRC, document_id='doc-1', filename='내문서.md', batch='b', previous_batch=None, status='READY', chars=1200, pages=1, warnings=[]))
        if url.endswith(f'/sources/{SRC}/extractions') and method == 'POST':
            return route.fulfill(json=dict(instance=INST, status='RUNNING', source_id=SRC, segments=1))
        if url.endswith(f'/sources/{SRC}/extractions'):
            return route.fulfill(json=dict(items=[], offset=0, limit=50, next_offset=None))
        if url.endswith(f'/sources/{SRC}/extractions/{INST}'):
            self.reads += 1
            return route.fulfill(json=dict(instance=INST, workitem=WID, status=self.status, log=None, preview=self.preview))
        if url.endswith('/api/todolist/' + WID):
            return route.fulfill(json=dict(id=WID, proc_inst_id=INST, activity_id='T', activity_name='원문 근거로 SOP 제안', status=self.status, draft_status=None,
                                           start_date=datetime.now(timezone.utc).isoformat(), end_date=None, user_id='sys:agent', agent_mode='COMPLETE',
                                           agent_orch='cliagents', consumer='w', log=None, output=None, generation=0, tool='formHandler:manual_proposal', events=list(self.events)))
        if url.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json=dict(total=0, items=[], limit=50, next_offset=None))
        if url.endswith('/api/kg/manuals') or url.endswith('/api/kg/ingests'):
            return route.fulfill(json=[])
        if url.endswith('/api/kg/manuals/catalog'):
            return route.fulfill(json=dict(parts=[], roles=[], skills=[]))
        return route.fulfill(json={})

    def finished(self):
        self.status = 'DONE'
        self.preview = dict(source_id=SRC, document_id='doc-1', filename='내문서.md', batch='b2', previous_batch=None, status='READY', chars=1200, sections=[], procedures=[],
                            warnings=[], page_reviews=None, validation=None, extraction=dict(instance=INST, workitem=WID, generation=0))


def _start(page, served, world):
    """문서 등록 화면을 열어 문서를 등록하고 [AI 추출 시작]을 누른다 — 2단계의 실시간 기록 칸이 뜰 때까지."""
    page.add_init_script(FAKE_ES)
    page.route('**/svc/**', world.answer)
    page.goto(served.url + '/index.html')
    open_screen(page, 'knowledge')
    page.set_input_files('#manualFile', dict(name='내문서.md', mimeType='text/markdown', buffer='# 절\n1. 단계'.encode()))
    page.locator('#manualPreview').click()
    page.locator('#manualAgentExtract').click()
    page.wait_for_selector('#manualLive .lv-work .lv-seg', timeout=15000)
    page.wait_for_function('hydStream.connected()', timeout=15000)


def _serve():
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    return Served(app)


def test_문서_AI_추출은_이벤트가_오는_대로_줄이_붙고_연결된_동안에는_서버에_되묻지_않으며_끝나면_3단계로_넘어가_기록이_남는다():
    """사용자 2026-11-14 「처리 과정이 블랙박스 X, 예: 인제스천」: 전에는 「AI 추출 중…」 글과 3초마다 끝났는지 묻는 것뿐이었다."""
    from playwright.sync_api import sync_playwright
    served, world = _serve(), Extraction()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            _start(page, served, world)
            assert 'AI가 문서를 읽고 있습니다' in page.inner_text('#manualLive [data-lv-now]')
            assert page.inner_text('#manualLive .lv-work-head [data-live-conn]') == '연결됨'
            page.evaluate('e => __sse.push(e)', world.event('task_started', dict(goal='원문 근거로 SOP 제안', name='claude-code', role='CLI 코딩 에이전트')))
            page.wait_for_timeout(800)                                                         # 단계 시작 이벤트가 부른 다시 읽기가 끝나기를
            reads = world.reads
            page.evaluate('e => __sse.push(e)', world.event('tool_usage_started', dict(tool='Write', tool_use_id='tu-1', input=dict(file_path='output/result.json', content='{}')), stored=False))
            page.wait_for_selector('#manualLive .tr-row.tr-k-tool.running', timeout=3000)      # 도는 도구 호출 한 줄이 실시간 연결에서 바로 붙는다(다시 읽기에는 아직 없는 줄)
            page.wait_for_timeout(6000)                                                        # 끊겼을 때의 묻는 간격(5초)보다 길게
            assert world.reads == reads, '실시간 연결이 살아 있는데 추출 상태를 되묻는다(폴링)'
            assert '초' in page.inner_text('#manualLive [data-lv-now] .lv-time')               # 걸린 시간이 보인다
            assert not page.locator('#manualLive [data-lv-conn]').is_visible()                 # 끊겼다는 말은 없다
            # 끝: 결과를 낸 이벤트가 오면 서버 상태를 읽고 3단계(검토 · 적재)로 넘어간다
            page.evaluate('e => __sse.push(e)', world.event('tool_usage_finished', dict(tool='Write', tool_use_id='tu-1', output='File created successfully at: output/result.json', is_error=False)))
            world.finished()
            page.evaluate('e => __sse.push(e)', world.event('task_completed', dict(output_keys=['proposal'], text='결과 파일 작성 완료: 절 1, 절차 0')))
            page.wait_for_selector('#manualCommit', timeout=8000)
            assert page.inner_text('#manualSteps .phase[data-state="now"]') == '검토'      # 단계 넷(올리기 · AI 추출 · 검토 · 적재) 가운데 셋째
            assert page.locator('#manualProcess .tr-row.tr-k-tool').count() == 1, '추출 과정 기록이 「추출 과정 보기」에 남지 않았다'
            assert not page.locator('#manualProcess .tr-row').first.is_visible()               # 접혀 있다 — 결과가 먼저
            page.locator('#manualProcess > summary').click()
            page.locator('#manualProcess .tr-row.tr-k-tool').wait_for(state='visible', timeout=3000)      # 접기는 펼쳐지는 움직임이 있다 — 다 펼쳐질 때까지
            assert 'AI 추출이 끝났습니다' in page.inner_text('#manualProcess [data-lv-now]')
            b.close()
    finally:
        served.close()


def test_실시간_연결이_끊기면_그_사실을_말하고_5초마다_묻고_화면을_떠나_있는_동안에는_묻지_않다가_돌아오면_이어_받는다():
    """말없이 폴링으로 바꾸지 않는다 · 가려진 화면은 구독을 멈춘다(새지 않게)."""
    from playwright.sync_api import sync_playwright
    served, world = _serve(), Extraction()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            _start(page, served, world)
            page.evaluate('__sse.drop()')
            page.wait_for_selector('#manualLive [data-lv-conn]:not([hidden])', timeout=5000)
            assert '실시간 연결이 끊겨 5초마다 확인합니다' in page.inner_text('#manualLive [data-lv-conn]')
            assert page.inner_text('#manualLive .lv-work-head [data-live-conn]') in ('다시 연결 중', '끊김 · 다시 연결을 시도하는 중')
            # 끊긴 동안 서버에서 생긴 줄(화면에 밀려오지 않는다)이 5초 묻기로 보인다
            world.event('task_started', dict(goal='원문 근거로 SOP 제안', name='claude-code', role='CLI 코딩 에이전트'))
            world.event('tool_usage_started', dict(tool='Write', tool_use_id='tu-1', input=dict(file_path='output/result.json', content='{}')))
            page.wait_for_selector('#manualLive .tr-row.tr-k-tool', timeout=9000)
            # 다른 화면으로 가면 묻기를 멈춘다
            open_screen(page, 'skills')
            page.wait_for_timeout(500)
            reads = world.reads
            page.wait_for_timeout(6500)
            assert world.reads == reads, '문서 등록 화면을 떠났는데도 추출 상태를 계속 묻는다'
            # 돌아오면 바로 한 번 읽어 그사이 것을 이어 받고(끝났으면 3단계로), 묻기를 다시 시작한다
            world.finished()
            open_screen(page, 'knowledge')
            page.wait_for_selector('#manualCommit', timeout=4000)
            b.close()
    finally:
        served.close()


def test_이어지는_일은_다음_사실을_기다려_한_줄씩_채우고_한_번에_결과만_오는_일은_3초_뒤_무엇을_기다리는지_말한다():
    """hydLive.follow(결함 주입 → 경보 → 처리 건 같은 일) · hydLive.waitHtml · hydLive.busy — 서버가 주지 않는 진행률은 그리지 않고 걸린 시간만."""
    from playwright.sync_api import sync_playwright
    served = _serve()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.add_init_script(FAKE_ES)
            page.route('**/svc/**', lambda route: route.fulfill(json={}))
            page.goto(served.url + '/index.html')
            page.wait_for_function('window.hydLive')
            page.evaluate("""() => {
              const host = document.createElement('div'); host.id = 'followHost'; document.querySelector('main').prepend(host);
              window.fact = {};
              hydLive.follow(host, [
                { key: 'alert', label: '경보를 기다리는 중', check: () => window.fact.alert || null, done: a => `경보가 났습니다 — ${a.name}` },
                { key: 'case', label: '처리 건이 열리기를 기다리는 중', check: a => { if (window.fact.fail) throw new Error('응답 없음'); return window.fact.inst || null; }, done: () => '처리 건이 열렸습니다',
                  link: i => ({ text: '처리 건 보기 →', go: () => { window.went = i.id; } }) },
              ], { every_ms: 200 });
              const w = document.createElement('div'); w.id = 'waitHost'; w.innerHTML = hydLive.waitHtml('연결 검사 중', { hint: '도구 서버의 응답을 기다립니다.' }) + '<button class="btn" id="busyBtn">저장</button>';
              document.querySelector('main').prepend(w);
              window.endBusy = hydLive.busy(document.getElementById('busyBtn'), '저장하는 중');
            }""")
            steps = lambda: page.evaluate("[...document.querySelectorAll('#followHost .lv-step')].map(n => n.className.replace('lv-step ', '') + ':' + n.querySelector('b').textContent)")
            assert steps() == ['run:경보를 기다리는 중', 'wait:처리 건이 열리기를 기다리는 중']
            assert page.locator('#followHost .lv-step.run .lv-time').count() == 1               # 기다리는 줄에 걸린 시간
            page.evaluate("window.fact.alert = { name: '쿨러 성능 저하' }; window.fact.fail = true")
            page.wait_for_function("document.querySelector('#followHost .lv-step.ok')")
            page.wait_for_function("(document.querySelector('#followHost .lv-step.run .lv-note') || {}).textContent === '확인하지 못했습니다(응답 없음) — 다시 확인합니다'")   # 실패를 삼키지 않는다
            page.evaluate("window.fact.fail = false; window.fact.inst = { id: 'inst-9' }")
            page.wait_for_function("document.querySelectorAll('#followHost .lv-step.ok').length === 2")
            assert steps() == ['ok:경보가 났습니다 — 쿨러 성능 저하', 'ok:처리 건이 열렸습니다']
            page.locator('#followHost [data-lv-go]').click()
            assert page.evaluate('window.went') == 'inst-9'
            # 한 번에 결과만 오는 일: 처음에는 「글 · 걸린 시간」, 3초가 지나면 무엇을 기다리는지 한 줄
            assert not page.locator('#waitHost .lv-late').is_visible()
            assert page.inner_text('#busyBtn').startswith('저장하는 중') and page.locator('#busyBtn').is_disabled()
            page.wait_for_selector('#waitHost .lv-late:not([hidden])', timeout=5000)
            assert page.inner_text('#waitHost .lv-late') == '아직 하는 중입니다 — 도구 서버의 응답을 기다립니다.'
            page.evaluate('window.endBusy()')
            assert page.inner_text('#busyBtn') == '저장' and not page.locator('#busyBtn').is_disabled()
            b.close()
    finally:
        served.close()
