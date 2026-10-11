"""Real Chromium + portal modules + FastAPI/MemoryRepo approval integration.

Only outside systems are doubles (test_approval_stage.opened). The host loads the
actual index.html template and all its styles, with only the relevant renderers
and request helper. No product exports or API responses are rewritten.
Set APPROVAL_UI_EVIDENCE to retain screenshots.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from procsvc import engine, instance_mode
from test_instance_mode import world, _row, NOW
from test_approval_stage import opened, THREE, OVERDUE_S
import test_approval_stage
import test_instance_mode

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "it/portal/www"
NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def approval_clock(monkeypatch):
    # Fresh cases keep elapsed-time screenshots meaningful. The flow and decision
    # fixtures themselves are unchanged; only their explicit test clock moves.
    monkeypatch.setattr(test_approval_stage, 'NOW', NOW)
    monkeypatch.setattr(test_instance_mode, 'NOW', NOW)


@pytest.fixture
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


class Portal:
    def __init__(self, browser, world, did, width=1440):
        self.rt, self.inst, self.inc, self.d, self.out = opened(world, did)
        self.world, self.did = world, did
        self.posts, self.fail, self.errors = [], None, []
        app = FastAPI()
        instance_mode.mount(app, "instance")

        @app.get('/api/decisions/{did}')
        def decision(did):
            return world['book'][did]

        @app.get('/api/agents')
        def agents():
            return []

        @app.get('/api/incidents/{iid}')
        def incident(iid):
            return vars(world['incidents'][iid])

        self.client = TestClient(app, raise_server_exceptions=False)
        self.page = browser.new_page(viewport={"width": width, "height": 1000}, locale='ko-KR')
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('**/*', self.route)
        self.page.goto('http://approval.test/')
        self.page.evaluate("""() => {
          document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
          document.querySelector('#view-instances').classList.add('active');
          document.querySelectorAll('.rail nav button').forEach(el => el.classList.toggle('active', el.dataset.tab === 'instances'));
        }""")
        self.page.clock.install(time=NOW)
        app_source = (WWW / 'app.js').read_text(encoding='utf-8')
        helper = app_source.split('/* ---------------- tabs')[0]
        self.page.add_script_tag(content=helper + "\nstate.tab='instances'; const API={process:'',agent:''}; const P=()=>''; function selectTab(){}; window.hydApp={};")
        for name in ['ui.js', 'enterprise.js', 'approvalCard.js', 'plainWords.js', 'trace.js', 'caseRecord.js', 'resultReport.js', 'instanceSteps.js', 'flow.js', 'instances.js']:
            source = (WWW / name).read_text(encoding='utf-8')
            if name == 'enterprise.js':
                source = source.split('/* ================================================= 조치 판단 규칙 */')[0]
            self.page.add_script_tag(content=source)
            if name == 'ui.js':
                navigation = app_source.split('/* ---------------- tabs ---------------- */')[1].split("selectTab('main');")[0]
                self.page.add_script_tag(content=navigation + "selectTab('instances');")
        self.page.evaluate('hydInstances.load(true)')
        assert not self.errors, self.errors
        self.page.locator('#tdGo').wait_for()
        self.page.locator('#tdBy').fill('이생산')
        assert self.page.locator('#tdRole option:checked').inner_text()
        assert self.page.locator('.rr-card').count() == 0, 'Waiting for approval is not system execution'

    def route(self, route):
        req = route.request
        parsed = urlsplit(req.url)
        path = parsed.path
        if path == '/':
            markup = (WWW / 'index.html').read_text(encoding='utf-8')
            markup = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', markup)
            route.fulfill(content_type='text/html', body=markup)
        elif (WWW / path.lstrip('/')).is_file():
            file = WWW / path.lstrip('/')
            route.fulfill(path=str(file))
        else:
            if req.method == 'POST':
                self.posts.append((path, req.post_data_json))
                if self.fail:
                    route.fulfill(status=self.fail, content_type='application/json', body=json.dumps({'detail': 'Internal Server Error'}))
                    return
            response = self.client.request(req.method, path + ('?' + parsed.query if parsed.query else ''), content=req.post_data, headers={'content-type': 'application/json'})
            route.fulfill(status=response.status_code, content_type='application/json', body=response.content)

    def settle(self):
        self.page.wait_for_function('!hydInstances.I.busy && !hydInstances.I.loading')

    def capture(self, stage):
        dest = os.getenv('APPROVAL_UI_EVIDENCE')
        if dest:
            folder = Path(dest)
            folder.mkdir(parents=True, exist_ok=True)
            width = self.page.viewport_size['width']
            self.page.wait_for_timeout(900)  # Let the product's new-row fade finish.
            if stage in ['request', 'delayed', 'permission-error', 'server-error']:
                self.page.locator('#todoPanel').evaluate("el => el.scrollIntoView({block: 'start'})")
            if stage == 'rejected-record':
                self.page.screenshot(path=str(folder / f'approval-{self.did}-{stage}-{width}-overview.png'), full_page=True)
                self.page.locator('#instRecord .cr-step').filter(has_text='요청을 거절했습니다').evaluate("el => el.scrollIntoView({block: 'start'})")
            self.page.screenshot(path=str(folder / f'approval-{self.did}-{stage}-{width}.png'), full_page=True)
            if stage in ['request', 'delayed']:
                self.page.locator('#todoPanel').screenshot(path=str(folder / f'approval-{self.did}-{stage}-{width}-panel.png'))
        assert not self.errors
        assert self.page.evaluate('document.documentElement.scrollWidth <= innerWidth')

    def close(self):
        self.page.close()
        self.client.close()


@pytest.mark.parametrize('did', THREE)
@pytest.mark.parametrize('width', [1440, 1024])
def test_browser_rejects_without_effects_and_shows_reason(browser, world, did, width):
    p = Portal(browser, world, did, width)
    try:
        p.capture('request')
        p.page.locator('#tdReason').fill('생산 일정 확인 후 다시 검토합니다.')
        p.page.locator('#tdRejectCard').click()
        p.settle()
        done = p.rt.repo.get_instance(p.inst['proc_inst_id'])
        assert done['end_event'] == 'E_rejected'
        assert p.inc.cmd_id is None and p.out.calls == [] and p.out.mails == [] and world['executed'] == []
        p.page.locator('[data-inst-tab="result"]').click()
        assert p.page.locator('[data-pane="result"] .rr-badge').inner_text() == '반려'
        assert '생산 일정 확인 후' in p.page.locator('[data-pane="result"] .rr-card').inner_text()
        p.capture('rejected-result')
        p.page.locator('[data-inst-tab="record"]').click()
        assert '요청을 거절했습니다' in p.page.locator('#instRecord').inner_text()
        assert '생산 일정 확인 후' in p.page.locator('#instRecord').inner_text()
        assert 'agent:' not in p.page.locator('#instRecord').inner_text()
        p.capture('rejected-record')
        p.page.locator('[data-inst-tab="flow"]').click()
        p.page.locator('.tr-step').filter(has_text='거절 접수').locator('[data-tr-head]').click()
        assert '사유: 생산 일정 확인 후' in p.page.locator('#instTrace').inner_text()
        assert 'approval_reason' not in p.page.locator('#instTrace').inner_text()
        p.capture('rejected-live')
    finally:
        p.close()


def test_browser_rejection_validation_permissions_and_retry_preserve_input(browser, world):
    p = Portal(browser, world, 'c3_pm')
    try:
        p.page.locator('#tdReason').fill('   ')
        p.page.locator('#tdRejectCard').click()
        assert len(p.posts) == 0
        assert '1~2000' in p.page.locator('#todoPanel .form-msg').inner_text()
        p.page.locator('#tdReason').fill('가' * 2001)
        p.page.locator('#tdRejectCard').click()
        assert len(p.posts) == 0
        p.page.locator('#tdReason').fill('예산 검토가 필요합니다.')
        p.page.locator('#tdRole').select_option('role:operator')
        p.page.locator('#tdRejectCard').click()
        p.settle()
        assert '권한' in p.page.locator('#todoPanel .form-msg').inner_text()
        assert p.page.locator('#tdReason').input_value() == '예산 검토가 필요합니다.'
        assert p.page.locator('#tdRole').input_value() == 'role:operator'
        p.capture('permission-error')
        p.page.locator('#tdRole').select_option('role:prod-mgr')
        p.fail = 500
        p.page.locator('#tdRejectCard').click()
        p.settle()
        assert '서버 내부 오류' in p.page.locator('#todoPanel .form-msg').inner_text()
        assert p.page.locator('#tdReason').input_value() == '예산 검토가 필요합니다.'
        assert p.page.locator('#tdBy').input_value() == '이생산'
        assert p.page.locator('#tdRole').input_value() == 'role:prod-mgr'
        p.capture('server-error')
        p.fail = None
        p.page.locator('#tdRejectCard').click()
        p.settle()
        assert p.rt.repo.get_instance(p.inst['proc_inst_id'])['end_event'] == 'E_rejected'
    finally:
        p.close()


@pytest.mark.parametrize('did', THREE)
def test_browser_delay_keeps_approval_open_and_accepts_approval(browser, world, did):
    p = Portal(browser, world, did)
    try:
        p.page.locator('#tdReason').fill('확인하고 승인합니다.')
        p.page.locator('#tdReason').focus()
        p.page.clock.fast_forward(1100)
        assert p.page.locator('[data-approval-until]').inner_text() != '지연 알림까지 30초'
        p.rt.fire_timeouts(now=NOW + timedelta(seconds=OVERDUE_S + 1))
        p.settle()
        p.page.evaluate('hydInstances.load(false)')
        p.page.locator('.approval-delay').wait_for(state='visible')
        assert p.page.locator('.approval-delay').is_visible()
        assert p.page.locator('#tdReason').input_value() == '확인하고 승인합니다.'
        assert p.page.locator('#tdReason').evaluate('el=>el===document.activeElement')
        assert p.page.locator('#tdGo').is_enabled() and p.page.locator('#tdRejectCard').is_enabled()
        assert _row(p.rt, p.inst, 'T_approve')['status'] == 'IN_PROGRESS'
        p.capture('delayed')
        # Same event loop: duplicate clicks cannot produce two writes, and both
        # buttons visibly disable before the network response arrives.
        p.page.evaluate("""() => { const go=document.querySelector('#tdGo'); go.click(); go.click(); window.locked = document.querySelector('#tdGo').disabled && document.querySelector('#tdRejectCard').disabled; }""")
        p.settle()
        assert p.page.evaluate('window.locked')
        assert len(p.posts) == 1 and p.posts[0][0].endswith('/select')
        assert _row(p.rt, p.inst, 'T_approve')['output']['approval'] == '승인'
        assert p.inc.cmd_id if did == 'c3_cooling' else p.out.calls
        assert not p.errors
    finally:
        p.close()


def test_browser_event_only_poll_preserves_focus_and_reject_is_single_submission(browser, world):
    p = Portal(browser, world, 'c3_pm')
    try:
        p.page.locator('#tdReason').fill('검토 중인 사유')
        p.page.locator('#tdReason').evaluate('el => el.setSelectionRange(2, 4)')
        before = p.rt.repo.list_workitems(proc_inst_id=p.inst['proc_inst_id'])
        # Notification arriving alone must update the panel even when all task
        # statuses are unchanged. This exercises the normal poll signature.
        p.rt.repo.record_events([{'job_id': 'APPROVAL_NOTICE', 'todo_id': _row(p.rt, p.inst, 'T_approve')['id'],
                                 'proc_inst_id': p.inst['proc_inst_id'], 'crew_type': 'system', 'event_type': 'task_working',
                                 'data': {'name': '승인 지연 알림', 'report': {'outcome': '승인 지연'}}}])
        p.settle()
        p.page.evaluate('hydInstances.load(false)')
        p.page.locator('.approval-delay').wait_for(state='visible')
        assert p.page.locator('.approval-delay').is_visible()
        assert p.page.locator('#tdReason').input_value() == '검토 중인 사유'
        assert p.page.locator('#tdReason').evaluate('el => [el.selectionStart, el.selectionEnd]') == [2, 4]
        assert p.rt.repo.list_workitems(proc_inst_id=p.inst['proc_inst_id']) == before
        p.page.evaluate("""() => { const reject=document.querySelector('#tdRejectCard'); reject.click(); reject.click(); window.locked = document.querySelector('#tdGo').disabled && document.querySelector('#tdRejectCard').disabled; }""")
        p.settle()
        assert p.page.evaluate('window.locked')
        assert len(p.posts) == 1 and p.posts[0][0].endswith('/reject-card')
        assert p.rt.repo.get_instance(p.inst['proc_inst_id'])['end_event'] == 'E_rejected'
    finally:
        p.close()
