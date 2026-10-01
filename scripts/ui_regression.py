"""Live Chromium portal checks. Requires the local Compose stack; writes .evidence/ui-review.

Exercises UI state, read/write flows and browser-only service failures. Existing skill
description and simulator scale are restored. Creates review decisions/transactions.
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.evidence' / 'ui-review'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []


def check(name, action):
    try:
        action()
        checks.append({'name': name, 'ok': True})
        print('PASS', name, flush=True)
    except Exception as exc:
        checks.append({'name': name, 'ok': False, 'error': str(exc)[:1000]})
        print('FAIL', name, str(exc)[:300], flush=True)
    (OUT / 'results.json').write_text(json.dumps({'checks': checks, 'page_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')


def require(value, message):
    assert value, message


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, record_video_dir=str(OUT / 'video'))
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_default_timeout(15000)
    page.goto('http://localhost:8088')
    expect(page.locator('#scale')).to_have_text('20', timeout=30000)

    def tab(name):
        if name == 'main':
            page.locator('#brandHome').click()
        else:
            page.locator(f'.rail button[data-tab="{name}"]').click()
        expect(page.locator(f'#view-{name}')).to_be_visible()

    def shot(name):
        page.screenshot(path=str(OUT / (name + '.png')))

    def scale_reload():
        tab('scenario')
        expect(page.locator('#units .unit')).to_have_count(3)
        page.locator('#selScale').select_option('5')
        expect(page.locator('#scale')).to_have_text('5')
        page.reload()
        expect(page.locator('#scale')).to_have_text('5', timeout=30000)
        tab('scenario')
        expect(page.locator('#selScale')).to_have_value('5')
        shot('scale-after')
        page.locator('#selScale').select_option('20')
        expect(page.locator('#scale')).to_have_text('20')
    check('scale matches backend after reload', scale_reload)

    def skill_drafts():
        tab('skills')
        expect(page.locator('#skName')).to_be_visible()
        original = page.locator('#skName').input_value()
        page.locator('#skName').fill('UI 임시 작성')
        tab('decision')
        tab('skills')
        expect(page.locator('#skName')).to_have_value('UI 임시 작성')
        page.locator('#skillList .item').nth(1).click()
        page.locator('#skillList .item').first.click()
        expect(page.locator('#skName')).to_have_value('UI 임시 작성')
        page.locator('#skName').fill(original)
        page.locator('#skillNew').click()
        page.locator('#skSave').click()
        expect(page.locator('#skMsg')).to_have_text('스킬 이름을 입력하세요.')
        page.locator('#skName').fill('UI 신규 임시 작성')
        tab('main')
        tab('skills')
        expect(page.locator('#skName')).to_have_value('UI 신규 임시 작성')
        shot('skill-draft-after')
        page.locator('#skillList .item').first.click()
    check('skill draft survives tab and item changes; empty name validation', skill_drafts)

    def skill_save():
        tab('skills')
        page.locator('#skillList .item').first.click()
        old = page.locator('#skDesc').input_value()
        try:
            page.locator('#skDesc').fill(old + '\nUI 회귀 검증')
            page.locator('#skSave').click()
            expect(page.locator('#skMsg')).to_have_text('온톨로지에 반영했다.')
            page.reload()
            tab('skills')
            expect(page.locator('#skDesc')).to_have_value(old + '\nUI 회귀 검증')
            shot('skill-saved-after')
        finally:
            page.locator('#skDesc').fill(old)
            page.locator('#skSave').click()
            expect(page.locator('#skMsg')).to_have_text('온톨로지에 반영했다.')
    check('skill edit saves to backend and original restored', skill_save)

    def incident_form():
        pending = [i for i in page.request.get('http://127.0.0.1:8080/api/incidents').json() if i['state'] == 'AWAITING_APPROVAL']
        if not pending:
            tab('scenario')
            page.locator('#btnReset').click()
            expect(page.locator('#scenarioMsg')).to_contain_text('정상 운전점')
            page.wait_for_function("state.det && Object.values(state.det.assets || {}).every(a => a.phase === 'IDLE')", timeout=60000)
            page.locator('#units .unit').first.locator('[data-act=degrade]').click()
        tab('incidents')
        page.wait_for_function("state.incidents.some(i => i.state === 'AWAITING_APPROVAL')", timeout=150000)
        inc_id = page.evaluate("state.incidents.find(i => i.state === 'AWAITING_APPROVAL').id")
        page.locator('#incList .item').filter(has_text=inc_id).click()
        expect(page.locator('#rejectReason')).to_be_attached(timeout=30000)
        page.locator('#rejectReason').fill('자동 갱신 후에도 유지할 사유')
        slider = page.locator('#incDetail input[type=range]').first
        slider.focus()
        slider.press('Home')
        slider.press('ArrowRight')
        chosen = slider.input_value()
        # Two polling cycles: this wait tests retention, rather than page readiness.
        page.wait_for_timeout(5000)
        expect(page.locator('#rejectReason')).to_have_value('자동 갱신 후에도 유지할 사유')
        expect(slider).to_have_value(chosen)
        require(page.locator('#incDetail input[type=range]').first.evaluate('(e) => e === document.activeElement'), 'poll stole keyboard focus')
        shot('incident-form-after')
        tab('trends')
        require(page.locator('main').evaluate('(e) => e.scrollTop') == 0, 'tab retained prior scroll')
        require(page.locator('.rail').bounding_box()['y'] == 0, 'sidebar scrolled outside viewport')
    check('incident reason, slider and focus persist; new tab starts at top', incident_form)

    def service_failure():
        tab('scenario')
        page.route('**:8000/api/**', lambda route: route.abort())
        try:
            page.locator('#btnReset').click()
            expect(page.locator('#scenarioMsg')).to_contain_text('초기화 실패')
            expect(page.locator('#simT')).to_have_text('연결 끊김', timeout=20000)
            shot('service-failure-after')
        finally:
            page.unroute('**:8000/api/**')
        expect(page.locator('#units .unit')).to_have_count(3, timeout=20000)
        expect(page.locator('#units > *')).to_have_count(3)
        expect(page.locator('#simT')).not_to_have_text('연결 끊김')
        page.route('**:8080/api/incidents', lambda route: route.abort())
        try:
            expect(page.locator('#openCount')).to_have_text('연결 끊김', timeout=20000)
        finally:
            page.unroute('**:8080/api/incidents')
        expect(page.locator('#openCount')).not_to_have_text('연결 끊김', timeout=20000)
    check('unavailable services show errors and recover', service_failure)

    def ontology():
        tab('ontology')
        expect(page.locator('#ontoMap svg')).to_be_visible(timeout=30000)
        page.locator('#ontoAsset').select_option('HYD-02')
        expect(page.locator('#ontoMap')).to_contain_text('HYD-02')
        page.locator('#ontoFocus').select_option('sc:part-procurement')
        page.locator('#ontoSearch').fill('쿨러')
        shot('ontology-search-after')
        page.locator('#ontoSearch').fill('')
        page.locator('#ontoFocus').select_option('')
        for b in page.locator('#ontoTpl button').all():
            b.click()
            expect(page.locator('#ontoTplText')).to_contain_text('MATCH')
        page.locator('#manualPreview').click()
        expect(page.locator('#manualResult')).to_contain_text('파일을 먼저')
        page.locator('#manualFile').set_input_files(str(ROOT / 'it/portal/www/samples/HM-8_cooler-fan-manual.md'))
        page.locator('#manualPreview').click()
        expect(page.locator('#manualCommit')).to_be_enabled(timeout=30000)
        shot('manual-preview-after')
        page.locator('#manualFile').set_input_files(str(ROOT / 'README.md'))
        expect(page.locator('#manualCommit')).to_have_count(0)
        expect(page.locator('#manualResult')).to_be_empty()
        page.locator('#manualFile').set_input_files(str(ROOT / 'it/portal/www/samples/HM-8_cooler-fan-manual.md'))
        page.locator('#manualPreview').click()
        expect(page.locator('#manualCommit')).to_be_enabled()
        page.locator('#manualCommit').click()
        expect(page.locator('#manualMsg')).to_contain_text('적재 완료', timeout=30000)
        expect(page.locator('#manualCommit')).to_be_disabled()
        shot('manual-committed-after')
    check('ontology asset/search/focus, nine templates and manual preview', ontology)

    def decisions():
        tab('decision')
        expect(page.locator('.scn')).to_have_count(4)
        for i in range(4):
            card = page.locator('.scn').nth(i)
            if i < 3:
                card.locator('select').select_option('HYD-02')
            card.locator('button').click()
            expect(card.locator('button')).to_be_enabled(timeout=45000)
            expect(page.locator('#decResult .mtx')).to_be_visible(timeout=45000)
            for b in page.locator('#decResult .persp button').all():
                b.click()
            shot(f'decision-{i+1}-after')
        page.locator('#goApprove').click()
        expect(page.locator('#decRole')).to_be_visible()
        page.locator('#decBy').fill('UI 검증자')
        page.locator('#decRole').select_option('role:operator')
        page.locator('#decReason').fill('UI 상태 유지 확인')
        page.wait_for_timeout(5500)
        expect(page.locator('#decBy')).to_have_value('UI 검증자')
        expect(page.locator('#decRole')).to_have_value('role:operator')
        expect(page.locator('#decReason')).to_have_value('UI 상태 유지 확인')
        page.locator('#decDetail [data-approve]').first.click()
        expect(page.locator('#decMsg')).not_to_be_empty()
        shot('decision-denied-after')
    check('all four decisions, perspectives, approval inputs and operator denial', decisions)

    def usability():
        tab('main')
        page.locator('#mainOperate').click()
        expect(page.locator('#view-incidents')).to_be_visible()
        for name, selector in [('incidents','#incList .item'),('process','#decList .item')]:
            tab(name)
            item=page.locator(selector).first
            item.focus()
            page.wait_for_timeout(5500)
            expect(item).to_be_focused()
            item.press('Enter')
        page.locator('#decReason').fill('')
        page.locator('#decReject').click()
        expect(page.locator('#decMsg')).to_have_text('반려 사유를 입력하세요.')
        expect(page.locator('#decReason')).to_be_focused()
        toggle=page.locator('#procBpmn [data-bpmn-fit]')
        toggle.click()
        expect(toggle).to_have_attribute('aria-pressed','true')
        require(page.locator('#procBpmn .bpmn-scroll').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2'),'fit diagram overflow')
        toggle.click()
        tab('ontology')
        page.locator('#ontoSearch').fill('no-such-node-20261001')
        expect(page.locator('#ontoStats')).to_contain_text('검색 결과 0개')
        page.locator('#ontoSearch').fill('쿨러')
        expect(page.locator('.o-node.match').first).to_be_visible()
        page.locator('#ontoSearch').fill('')
        node=page.locator('.o-node').first
        node.focus()
        node.press('Enter')
        expect(page.locator('.o-node.sel')).to_be_focused()
        tab('main')
        page.route('**:8000/api/**',lambda route:route.abort())
        try:
            expect(page.locator('#mainStats')).to_contain_text('설비 연결 끊김',timeout=20000)
        finally:
            page.unroute('**:8000/api/**')
        expect(page.locator('#mainStats')).not_to_contain_text('설비 연결 끊김',timeout=20000)
    check('entry action, keyboard retention, rejection validation, diagram fit, search and stale status',usability)


    def layouts():
        for width, height in [(1440, 900), (1262, 624), (1024, 768)]:
            page.set_viewport_size({'width': width, 'height': height})
            for name in ['main', 'home', 'scenario', 'incidents', 'trends', 'ontology', 'skills', 'decision', 'process']:
                tab(name)
                require(page.locator('main').evaluate('(e) => e.scrollWidth <= e.clientWidth + 2'), f'{width} {name}: main horizontal overflow')
                require(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{width} {name}: body overflow')
                shot(f'layout-{width}-{name}')
        page.set_viewport_size({'width': 1440, 'height': 900})
    check('nine screens at three desktop widths without page overflow', layouts)

    def grafana():
        tab('trends')
        page.locator('#selAsset').select_option('HYD-02')
        for sel in ['#pTs1', '#pScore', '#pCe', '#pSp', '#pAlerts']:
            # Grafana renders a panel when its iframe enters the visible area.
            page.locator(sel).scroll_into_view_if_needed()
            frame = page.frame_locator(sel)
            expect(frame.locator('body')).not_to_contain_text('Dashboard not found', timeout=30000)
            expect(frame.get_by_role('region')).to_be_visible(timeout=45000)
            if sel != '#pAlerts':  # A quiet asset can legitimately have no recent alarms.
                expect(frame.locator('body')).not_to_contain_text('No data')
        shot('grafana-after')
    check('five live Grafana panels load for selected asset', grafana)
    check('no uncaught JavaScript exceptions', lambda: require(not errors, str(errors)))
    tab('scenario')
    page.locator('#btnReset').click()
    expect(page.locator('#scenarioMsg')).to_contain_text('정상 운전점')
    context.close()
    browser.close()

print(f'{sum(c["ok"] for c in checks)}/{len(checks)} checks passed', flush=True)
raise SystemExit(0 if all(c['ok'] for c in checks) else 1)
