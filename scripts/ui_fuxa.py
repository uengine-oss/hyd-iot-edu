"""Live FUXA read/write and layout smoke, restoring HYD-02 setpoints/mode."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

out = Path(__file__).resolve().parents[1] / '.evidence/ui-review'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={'width': 1262, 'height': 768}, record_video_dir=str(out / 'fuxa-video'))
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://localhost:1881')
    mode = page.get_by_role('combobox', name='HYD-02 mode set', exact=True)
    fan = page.get_by_role('textbox', name='HYD-02 fan write', exact=True)
    expect(mode).to_be_visible(timeout=30000)

    def unit():
        return page.request.get('http://127.0.0.1:8000/api/state').json()['units']['HYD-02']

    def until(fn):
        limit = time.monotonic() + 15
        while time.monotonic() < limit:
            u = unit()
            if fn(u):
                return u
            page.wait_for_timeout(250)
        raise AssertionError(unit())

    original = unit()
    evidence = {}
    try:
        assert mode.input_value() in ('', '0', '1', '2')
        mode.select_option('1')
        until(lambda u: u['status']['mode'] == 'REMOTE_MANUAL')
        fan.fill('80')
        fan.press('Enter')
        evidence['valid'] = until(lambda u: u['tags']['FanSpeedSP'] == 80 and u['status']['result'] == 'DONE')
        fan.fill('150')
        fan.press('Enter')
        evidence['invalid'] = until(lambda u: u['status']['reason'] == 'OUT_OF_RANGE')
        assert evidence['invalid']['tags']['FanSpeedSP'] == 80
        expect(page.locator('[data-name="HYD-02 ack reason"]')).to_have_text('허용 범위 초과', timeout=5000)
        page.screenshot(path=str(out / 'fuxa-range-rejected.png'))
        mode.select_option('0')
        until(lambda u: u['status']['mode'] == 'LOCAL')
        fan.fill('75')
        fan.press('Enter')
        evidence['local'] = until(lambda u: u['status']['reason'] == 'MODE_MISMATCH')
        expect(page.locator('[data-name="HYD-02 ack reason"]')).to_have_text('운전 모드 확인 필요', timeout=5000)
        mode.select_option('1')
        until(lambda u: u['status']['mode'] == 'REMOTE_MANUAL')
        fan.fill('75')
        fan.press('Enter')
        evidence['recovered'] = until(lambda u: u['tags']['FanSpeedSP'] == 75 and u['status']['result'] == 'DONE')
        expect(page.locator('#home')).not_to_contain_text('##.##')
        # HTTP state can precede the MQTT -> FUXA -> browser update. Require the
        # actual cleared widget within 5 s instead of sampling after a fixed nap.
        recovery_started = time.monotonic()
        expect(page.locator('[data-name="HYD-02 ack reason"]')).to_have_text('–', timeout=5000)
        evidence['reason_recovery_wait_ms'] = round((time.monotonic() - recovery_started) * 1000)
        evidence['reason_display'] = page.locator('[data-name="HYD-02 ack reason"]').text_content()
        assert 'MODE_MISMATCH' not in evidence['reason_display'] and 'OUT_OF_RANGE' not in evidence['reason_display'], evidence['reason_display']
        for width, height in [(1024, 768), (1262, 624), (1440, 900)]:
            page.set_viewport_size({'width': width, 'height': height})
            box = page.locator('#home #content > svg').bounding_box()
            assert box['x'] + box['width'] <= width + 1, box
            page.locator('.hyd-unit-0').scroll_into_view_if_needed()
            for card in page.locator('.hyd-unit').all():
                r=card.bounding_box()
                assert r['x']>=0 and r['x']+r['width']<=width, r
                # Native-sized cards reflow; they are never shrunk into tiny controls.
                assert r['width']>=370, r
            page.screenshot(path=str(out / f'fuxa-{width}-after.png'))
            if width < 1400:
                page.locator('.hyd-unit-2').scroll_into_view_if_needed()
                page.screenshot(path=str(out / f'fuxa-{width}-third-unit.png'))
        assert not errors, errors
        evidence['ok'] = True
        print('PASS FUXA manual mode, valid write, range denial, LOCAL denial, recovery, three widths', flush=True)
    finally:
        mode.select_option('1')
        until(lambda u: u['status']['mode'] == 'REMOTE_MANUAL')
        fan.fill(str(original['tags']['FanSpeedSP']))
        fan.press('Enter')
        until(lambda u: u['tags']['FanSpeedSP'] == original['tags']['FanSpeedSP'])
        mode.select_option({'LOCAL': '0', 'REMOTE_MANUAL': '1', 'REMOTE_AUTO': '2'}[original['status']['mode']])
        until(lambda u: u['status']['mode'] == original['status']['mode'])
        evidence['page_errors'] = errors
        (out / 'fuxa.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        ctx.close()
        browser.close()
