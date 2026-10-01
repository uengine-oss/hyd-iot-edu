"""Regression checks for defects found while viewing all 173 source images.

Creates one unapproved comparison decision; does not execute equipment actions.
Screenshot review remains a separate step.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, TimeoutError
from ui_capture_ready import trends_ready

OUT = Path(__file__).resolve().parents[1] / '.evidence/visual-173/contracts'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1024, 'height': 768}, timezone_id='Asia/Seoul')
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://localhost:8088')
    expect(page.locator('#scale')).not_to_have_text('–')
    page.locator('[data-tab=process]').click()
    pending = page.locator('#decList .item').filter(has=page.locator('.pill.PENDING_APPROVAL')).first
    expect(pending).to_be_visible()
    pending.click()
    expect(page.locator('[data-approve]').first).to_be_visible()
    for width in [1920, 1440, 1262, 1024, 820, 768, 390]:
        page.set_viewport_size({'width': width, 'height': 900})
        for button in page.locator('[data-approve]').all():
            button.scroll_into_view_if_needed()
            r = button.bounding_box()
            assert 0 <= r['x'] and r['x'] + r['width'] <= width, (width, r)
            button.click(trial=True)  # Verify reachability without submitting approval.
    checks.append('approval controls reachable at seven widths without horizontal scrolling')

    page.set_viewport_size({'width': 1024, 'height': 768})
    region = page.locator('#procBpmn .bpmn-scroll')
    expect(region).to_be_visible()
    region.scroll_into_view_if_needed()
    region.evaluate('(e)=>e.scrollLeft=e.scrollWidth')
    region.focus()
    left = region.evaluate('(e)=>e.scrollLeft')
    assert left > 0
    # Force the real redraw path on the same selected record, as a state update would.
    page.locator('#procBpmn').evaluate('(e)=>e.dataset.sig=""')
    page.wait_for_function('document.querySelector("#procBpmn").dataset.sig !== ""')
    assert abs(region.evaluate('(e)=>e.scrollLeft') - left) < 2
    expect(region).to_be_focused()
    page.locator('#procBpmn [data-bpmn-fit]').click()
    page.locator('#procBpmn').evaluate('(e)=>e.dataset.sig=""')
    page.wait_for_function('document.querySelector("#procBpmn").dataset.sig !== ""')
    expect(page.locator('#procBpmn [data-bpmn-fit]')).to_have_attribute('aria-pressed', 'true')
    assert region.evaluate('(e)=>e.scrollWidth<=e.clientWidth+2')
    checks.append('same-record BPMN redraw retains scroll, keyboard focus and fit mode')

    page.locator('[data-tab=incidents]').click()
    expect(page.locator('#incList .item').first).to_be_visible()
    page.locator('#incList .item').first.click()
    expect(page.locator('.causes')).to_be_visible()
    assert page.locator('.causes').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2')
    page.locator('.causes').scroll_into_view_if_needed()
    page.screenshot(path=str(OUT / 'narrow-cause-cards.png'))
    checks.append('narrow incident pane keeps cause, probabilities and evidence together')

    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.locator('[data-tab=ontology]').click()
    expect(page.locator('#ontoMap svg')).to_be_visible()
    ratio = page.locator('#ontoMap').evaluate('(e)=>e.querySelector("svg").getBoundingClientRect().width/e.clientWidth')
    assert .95 < ratio < 1.02, ratio
    checks.append('knowledge map uses available desktop width')
    with page.expect_file_chooser():
        page.locator('.file-picker .btn').click()
    checks.append('custom file label opens the native file chooser')

    page.set_viewport_size({'width':1024, 'height':768})
    page.locator('[data-tab=decision]').click()
    page.locator('.scn button').first.click()
    matrix = page.locator('.mtx-wrap')
    expect(matrix).to_be_visible()
    matrix.scroll_into_view_if_needed()
    matrix.evaluate('(e)=>{e.scrollLeft=e.scrollWidth;e.scrollTop=e.scrollHeight}')
    bounds = matrix.bounding_box()
    assert matrix.evaluate('(e)=>e.scrollLeft>0 && e.scrollTop>0')
    assert abs(matrix.locator('tbody tr').last.locator('td').first.bounding_box()['x']-bounds['x']) < 3
    assert matrix.locator('thead').bounding_box()['y'] >= bounds['y']-2
    checks.append('comparison retains option names and column headers at both scroll ends')

    # A blank/loading chart must fail; a painted chart with a table must pass.
    probe = browser.new_page()
    probe.set_content('<main>' + ''.join(f'<iframe id="{x}"></iframe>' for x in ['pTs1','pScore','pCe','pSp','pAlerts']) + '</main>')
    try:
        trends_ready(probe, timeout=100)
        raise AssertionError('blank panels passed capture readiness')
    except TimeoutError:
        pass
    for frame in probe.frames[1:]:
        frame.set_content('<div class="uplot"><canvas width="10" height="10"></canvas></div><div role="table">경보 유형</div>')
        frame.evaluate('document.querySelector("canvas").getContext("2d").fillRect(0,0,10,10)')
    trends_ready(probe, timeout=1000)
    probe.close()
    checks.append('capture readiness rejects blank charts and accepts rendered charts')
    assert not errors, errors
    browser.close()

(OUT / 'results.json').write_text(json.dumps({'checks':checks,'page_errors':errors}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'PASS {len(checks)} visual regression contracts')
