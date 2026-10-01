"""Read-only browser review of information order, copy and expanded UI states.

Uses existing incident/decision records. Does not approve or change equipment.
Screenshots complement the structural checks; they do not certify visual quality.
"""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.evidence/ui-purpose/details'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors, images = [], [], []

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, locale='ko-KR')
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://localhost:8088')
    expect(page.locator('#scale')).not_to_have_text('–')

    def tab(name):
        page.locator(f'[data-tab={name}]').click()
        expect(page.locator(f'#view-{name}')).to_be_visible()

    def shot(name, locator=None):
        # The portal scrolls inside main. Element screenshots taller than that
        # viewport include the fixed footer over the content; capture real views.
        if locator is not None:
            locator.evaluate('(e)=>e.scrollIntoView({block:"start"})')
        path = OUT / f'{name}.png'
        page.screenshot(path=str(path))
        images.append(path.name)
        if locator is not None and locator.bounding_box()['height'] > page.locator('main').bounding_box()['height']:
            main_box = page.locator('main').bounding_box()
            delta = locator.bounding_box()['y'] + locator.bounding_box()['height'] - (main_box['y'] + main_box['height'] - 6)
            page.locator('main').evaluate('(e,dy)=>e.scrollTop+=dy', delta)
            path = OUT / f'{name}-bottom.png'
            page.screenshot(path=str(path))
            images.append(path.name)

    def record(name):
        checks.append(name)
        print('PASS', name, flush=True)

    tab('home')
    expect(page.locator('#stack .layer')).to_have_count(9)
    expect(page.locator('#stack .comp')).to_have_count(16)
    assert all(page.locator('#stack .role-desc').all_text_contents())
    expect(page.locator('#stack')).not_to_contain_text('구현 비교')
    record('nine layers and sixteen components retain readable purpose descriptions')
    page.route('**:8085/**', lambda route: route.abort())
    page.wait_for_function('!pollHealth.busy')
    page.evaluate('pollHealth()')
    console_link = page.locator('[data-entry="http://localhost:8085/topics"]')
    console_status = page.locator('[data-entry-status="http://localhost:8085/topics"]')
    expect(console_status).to_have_text('(메시지 조회 화면 미실행)', timeout=15000)
    expect(console_link).to_have_attribute('aria-disabled', 'true', timeout=15000)
    assert console_link.get_attribute('href') is None
    page.unroute('**:8085/**')
    # Simulate only console availability; the core event-service probe is unchanged.
    page.route('**:8085/**', lambda route: route.fulfill(status=200, body='Console reachable'))
    page.wait_for_function('!pollHealth.busy')
    page.evaluate('pollHealth()')
    expect(console_link).to_have_attribute('href', 'http://localhost:8085/topics')
    expect(console_status).to_have_text('')
    page.unroute('**:8085/**')
    page.wait_for_function('!pollHealth.busy')
    page.evaluate('pollHealth()')
    # Screenshots show the real local availability, after removing both routes.
    shot('architecture-top')
    shot('architecture-stack', page.locator('#stack'))
    record('optional console availability disables or restores its entry independently of core service health')

    tab('scenario')
    expect(page.locator('#units .unit')).to_have_count(3)
    expect(page.locator('#units [aria-pressed=true]')).to_have_count(3)
    controls = page.locator('#units .ctl').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().top)')
    assert max(controls) - min(controls) < 2, controls
    shot('equipment-controls', page.locator('#units'))
    record('three equipment controls align and show actual active modes')

    tab('skills')
    expect(page.get_by_label('스킬 이름', exact=True)).to_be_visible()
    expect(page.get_by_label('어떤 작업을 하나요?', exact=True)).to_be_visible()
    shot('skill-editor', page.locator('#skillDetail'))
    record('skill editor labels explain the input instead of database field names')

    tab('ontology')
    expect(page.locator('#ontoMap svg')).to_be_visible()
    asset = page.locator('#ontoAsset').input_value()
    page.locator(f'.o-node[data-id="{asset}"]').click()
    expect(page.locator('.o-node.dim')).to_have_count(0)
    shot('ontology-selection')
    history = page.locator('#manualHistory details')
    expect(history).to_be_visible()
    history.locator('summary').click()
    assert history.locator('tbody tr').count() > 0
    shot('manual-history', page.locator('#manualUpload'))
    page.locator('#manualPreview').click()
    expect(page.locator('#manualResult')).to_contain_text('파일을 먼저')
    shot('manual-missing-file', page.locator('#manualUpload'))
    assert not re.search(r'\bT[123](?:\b|[-_])', page.locator('#ontoTpl').inner_text())
    record('cross-domain visibility, manual history table, missing-file message and friendly query labels')

    page.route('**:8091/api/ontology/graph?*', lambda route: route.abort())
    page.locator('#ontoReload').click()
    expect(page.locator('#ontoStats')).to_have_text('불러오기 실패')
    shot('ontology-connection-error')
    tab('home')
    tab('ontology')
    expect(page.locator('#ontoMap svg')).to_have_count(0)
    expect(page.locator('#ontoNode')).to_be_empty()
    page.unroute('**:8091/api/ontology/graph?*')
    tab('home')
    tab('ontology')
    expect(page.locator('#ontoMap svg')).to_be_visible()
    record('ontology recovers when reopened after a connection failure')

    tab('incidents')
    expect(page.locator('#incList .item').first).to_be_visible()
    page.locator('#incList .item').first.click()
    expect(page.locator('#incDetail .causes')).to_be_visible()
    trace = page.locator('#incDetail > details.technical')
    assert page.locator('#incDetail .causes').bounding_box()['y'] < trace.bounding_box()['y']
    trace.locator(':scope > summary').click()
    expect(trace.locator('.trace .step').first).to_be_visible()
    assert not re.search(r'\bT[123](?:\b|[-_])', trace.locator('.trace').inner_text())
    shot('incident-analysis', trace)
    step = trace.locator('.step details').filter(has_text='t1_causes').first
    step.locator('summary').click()
    expect(step.locator('pre')).to_be_visible()
    assert step.locator('pre').inner_text()
    shot('incident-raw-evidence', step)
    record('action evidence comes before trace; friendly trace and full raw output remain available')

    tab('process')
    expect(page.locator('#procBpmn svg')).to_be_visible()
    assert not re.search(r'\bT[123](?:\b|[-_])', page.locator('#procBpmn').inner_text())
    page.locator('#procBpmn [data-bpmn-fit]').click()
    shot('business-process-complete', page.locator('#procBpmn'))
    page.locator('#procBpmn [data-bpmn-fit]').click()
    record('business-process labels describe tasks and full-flow view works')
    assert not errors, errors
    browser.close()

(OUT / 'results.json').write_text(json.dumps({'checks': checks, 'page_errors': errors, 'images': images}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'{len(checks)} readability checks passed')
