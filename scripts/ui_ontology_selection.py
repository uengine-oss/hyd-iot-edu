"""Read-only live checks for local relation selection and scenario context."""
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.evidence/ontology-selection'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, locale='ko-KR')
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://localhost:8088')
    page.locator('.rail [data-tab="ontology"]').click()
    expect(page.locator('#ontoMap svg')).to_be_visible()

    def ids(selector):
        return set(page.locator(selector).evaluate_all('(es)=>es.map(e=>e.dataset.id)'))

    def record(name):
        checks.append(name)
        print('PASS', name, flush=True)

    def shot(name):
        page.locator('main').evaluate('(e)=>e.scrollTop=0')
        page.locator('#ontoMap').evaluate('(e)=>{e.scrollTop=0;e.scrollLeft=0}')
        page.screenshot(path=str(OUT / f'{name}.png'), animations='disabled')

    def verify_local(node):
        graph = page.evaluate('ent.graph')
        relations = [e for e in graph['edges'] if node in (e['from'], e['to'])]
        expected = {node} | {e['from'] for e in relations} | {e['to'] for e in relations}
        assert ids('.o-node:not(.dim)') == expected
        expect(page.locator('.o-edge.hot')).to_have_count(len(relations))
        assert page.locator('.o-node.dim').count() > 0
        assert page.locator('.o-edge.dim').count() > 0
        assert len(ids('.o-node')) == len(graph['nodes']), 'Dimming must retain all nodes'

    expect(page.locator('.o-node.dim')).to_have_count(0)
    for asset in ['HYD-01', 'HYD-02', 'HYD-03']:
        page.locator('#ontoAsset').select_option(asset)
        expect(page.locator(f'.o-node[data-id="{asset}"]')).to_be_visible()
        page.locator(f'.o-node[data-id="{asset}"]').click()
        verify_local(asset)
        expect(page.locator('.o-node:not(.dim)')).to_have_count(6)
        page.locator(f'.o-node[data-id="{asset}"]').press('Enter')
        expect(page.locator('.o-node.dim')).to_have_count(0)
        expect(page.locator('.o-edge.dim')).to_have_count(0)
    record('three assets show five components; keyboard deselection restores all knowledge')

    page.locator('#ontoAsset').select_option('HYD-01')
    page.locator('.o-node[data-id="HYD-01"]').click()
    shot('asset-direct')
    for target in ['HYD-01:Cooler', 'fm:cooler-performance-loss', 'cause:cooler-fin-fouling',
                   'act:cooler-clean-wo', 'SOP-COOL-02', 'SOP-COOL-02/2', 'HM-7.6']:
        page.locator(f'#ontoNode [data-go="{target}"]').click()
        verify_local(target)
    record('detail links traverse equipment, failure, cause, action, SOP and manual')
    page.locator('.o-node[data-id="cause:cooler-fin-fouling"]').click()
    verify_local('cause:cooler-fin-fouling')
    shot('cause-direct')
    page.locator('#ontoNode [data-go="act:cooler-clean-wo"]').click()
    page.locator('#ontoNode [data-go="skill:schedule-maintenance"]').click()
    verify_local('skill:schedule-maintenance')
    expect(page.locator('#ontoNode')).to_contain_text('실행 프로세스')
    process = next(e['to'] for e in page.evaluate('ent.graph.edges')
                   if e['from'] == 'skill:schedule-maintenance' and e['type'] == 'EXECUTED_IN')
    page.locator(f'#ontoNode [data-go="{process}"]').click()
    verify_local(process)
    record('action links retain skill and business process navigation with Korean relations')

    scenarios = page.locator('#ontoFocus option').evaluate_all('(es)=>es.map(e=>e.value).filter(Boolean)')
    assert len(scenarios) == 4
    for scenario in scenarios:
        page.locator('#ontoFocus').select_option(scenario)
        baseline = ids('.o-node:not(.dim)')
        assert len(baseline) > 6
        assert scenario in baseline
        assert page.locator('.o-edge.focus').count() > 0
        page.locator(f'.o-node[data-id="{scenario}"]').click()
        assert baseline <= ids('.o-node:not(.dim)'), 'Selecting a node must preserve scenario context'
        assert page.locator('.o-edge.hot').count() > 0
        page.locator(f'.o-node[data-id="{scenario}"]').press('Space')
        assert ids('.o-node:not(.dim)') == baseline
    shot('scenario-context')
    record('all four scenarios retain their paths during local selection and keyboard deselection')

    page.locator('#ontoFocus').select_option('')
    page.locator('.o-node[data-id="HYD-01"]').click()
    page.locator('#ontoSearch').fill('CMMS')
    expect(page.locator('.o-node.match[data-id="sys:cmms"]')).to_be_visible()
    expect(page.locator('.o-node.match.dim')).to_have_count(0)
    page.locator('#ontoSearch').fill('')
    verify_local('HYD-01')
    page.locator('#ontoLayers input[value="failure"]').uncheck()
    expect(page.locator('.o-node[data-id="fm:cooler-performance-loss"]')).to_have_count(0)
    page.locator('#ontoLayers input[value="failure"]').check()
    verify_local('HYD-01')
    record('search remains legible during selection; category toggle restores related data')

    for width, height in [(1440, 900), (1024, 768), (390, 844)]:
        page.set_viewport_size({'width': width, 'height': height})
        shot(f'asset-{width}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('#ontoMap').evaluate('(e)=>e.scrollWidth >= e.clientWidth')
        expect(page.locator('#ontoMap [marker-end]')).to_have_count(0)
    record('three viewport widths retain map scrolling without page overflow or oversized arrowheads')

    page.set_viewport_size({'width': 1440, 'height': 900})
    page.route('**:8091/api/ontology/graph?*', lambda route: route.abort())
    page.locator('#ontoReload').click()
    expect(page.locator('#ontoStats')).to_have_text('불러오기 실패')
    expect(page.locator('#ontoMap svg')).to_have_count(0)
    page.unroute('**:8091/api/ontology/graph?*')
    page.locator('.rail [data-tab="home"]').click()
    page.locator('.rail [data-tab="ontology"]').click()
    expect(page.locator('#ontoMap svg')).to_be_visible()
    verify_local('HYD-01')
    record('connection failure clears the map and reopening recovers the current selection')
    assert not errors, errors
    (OUT / 'results.json').write_text(json.dumps({'checks': checks, 'page_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
