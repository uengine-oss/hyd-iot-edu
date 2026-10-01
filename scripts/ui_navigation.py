"""Exercise sequential navigation, mobile drawer and the offline capture viewer."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.evidence/design-navigation'
OUT.mkdir(parents=True, exist_ok=True)
TABS = ['main', 'home', 'scenario', 'incidents', 'trends', 'ontology', 'skills', 'decision', 'process']
records, errors = [], []

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':900}, reduced_motion='reduce')
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.goto('http://localhost:8088')
    expect(page.locator('#scale')).not_to_have_text('–')
    for width,height in [(1440,900),(820,1180),(768,1024),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        while page.locator('#pagePrev').is_enabled():
            page.locator('#pagePrev').click()
        expect(page.locator('#pagePrev')).to_be_disabled()
        for i,tab in enumerate(TABS):
            if i: page.locator('#pageNext').click()
            expect(page.locator(f'#view-{tab}')).to_be_visible()
            expect(page.locator('#pagePosition')).to_have_text(f'{i+1} / 9')
            expect(page.locator(f'[data-tab={tab}]')).to_have_attribute('aria-current','page')
            if tab=='ontology':
                expect(page.locator('.o-node').first).to_be_visible()
                page.locator('.o-node').first.click()
            if tab=='skills': expect(page.locator('#skName')).to_be_visible()
            if tab=='decision':
                if not page.locator('#decResult .mtx').count():
                    page.locator('.scn button').first.click()
                expect(page.locator('#decResult .mtx')).to_be_visible()
            if tab=='process':
                expect(page.locator('#procBpmn .bpmn')).to_be_visible()
                done=page.locator('#decList .item').filter(has=page.locator('.pill.EXECUTED'))
                expect(done.first).to_be_visible()
                done.first.click()
                expect(page.locator('#decDetail .prov')).to_be_visible()
            page.locator('main').evaluate('(e)=>e.scrollTop=0')
            page.wait_for_timeout(250)
            metrics=page.evaluate('''() => {
                const main=document.querySelector('main'),footer=document.querySelector('.page-navigation');
                return {overflow:main.scrollWidth>main.clientWidth+2,bodyOverflow:document.documentElement.scrollWidth>innerWidth,
                    footerOverlaps:main.getBoundingClientRect().bottom>footer.getBoundingClientRect().top+1};
            }''')
            records.append(dict(width=width,tab=tab,**metrics))
            page.screenshot(path=str(OUT/f'{width}-{tab}.png'))
            page.locator('main').evaluate('(e)=>e.scrollTop=e.scrollHeight')
            expect(page.locator('#pageNext')).to_be_visible()
        expect(page.locator('#pageNext')).to_be_disabled()
    page.locator('#menuToggle').click()
    expect(page.locator('#menuToggle')).to_have_attribute('aria-expanded','true')
    page.keyboard.press('Escape')
    expect(page.locator('#menuToggle')).to_be_focused()
    assert page.locator('#navigation').evaluate('(e)=>e.inert')
    page.locator('#menuToggle').click()
    page.locator('[data-tab=skills]').click()
    expect(page.locator('#menuToggle')).to_have_attribute('aria-expanded','false')
    page.locator('#skillList .item').first.click()
    expect(page.locator('#skName')).to_be_in_viewport()
    page.locator('#skName').fill('순서 이동 중 작성한 초안')
    page.locator('#pageNext').click()
    page.locator('#pagePrev').click()
    expect(page.locator('#skName')).to_have_value('순서 이동 중 작성한 초안')
    print('PASS sequence, boundary buttons, draft retention and mobile drawer',flush=True)

    folder=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'UIUX_캡처_2026-10-01_102354'
    page.goto((folder.resolve()/'index.html').as_uri())
    page.set_viewport_size({'width':1440,'height':900})
    total=page.locator('.card').count()
    page.locator('#start').click()
    expect(page.locator('#position')).to_have_text(f'1 / {total}')
    expect(page.locator('#prev')).to_be_disabled()
    page.keyboard.press('ArrowRight')
    expect(page.locator('#position')).to_have_text(f'2 / {total}')
    assert page.locator('#picture').evaluate('(e)=>e.complete&&e.naturalWidth>0')
    page.locator('#zoom').click()
    expect(page.locator('#zoom')).to_have_attribute('aria-pressed','true')
    page.locator('#delay').select_option('3')
    page.locator('#canvas').focus()
    page.keyboard.press('Space')
    expect(page.locator('#position')).to_have_text(f'3 / {total}',timeout=6000)
    page.keyboard.press('Space')
    expect(page.locator('#play')).to_have_attribute('aria-pressed','false')
    page.keyboard.press('Escape')
    expect(page.locator('#viewer')).not_to_be_visible()
    page.locator('#search').fill('존재하지않는사진이름')
    expect(page.locator('#start')).to_be_disabled()
    expect(page.locator('.card:visible')).to_have_count(0)
    page.locator('#search').fill('FUXA')
    count=page.locator('.card:visible').count()
    assert count>0
    page.locator('#start').click()
    expect(page.locator('#position')).to_have_text(f'1 / {count}')
    page.screenshot(path=str(OUT/'gallery-viewer.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(OUT/'gallery-mobile.png'))
    print('PASS gallery arrows, playback, zoom, filtered sequence and no-results',flush=True)
    browser.close()

(OUT/'results.json').write_text(json.dumps({'records':records,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
assert not errors,errors
assert not any(r['overflow'] or r['bodyOverflow'] or r['footerOverlaps'] for r in records), 'See results.json'
print(f'PASS {len(records)} portal layouts and gallery navigation')
