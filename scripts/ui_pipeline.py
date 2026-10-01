"""Real UI: fault -> new incident -> role denial -> HITL -> PLC ACK -> closed.

Requires local Compose stack. Resets simulated units before and after the run.
All mutations go through visible portal controls; API reads corroborate results.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

out = Path(__file__).resolve().parents[1] / '.evidence/ui-review'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, record_video_dir=str(out / 'pipeline-video'))
    page = ctx.new_page()
    page.set_default_timeout(20000)
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.post_data_json) if '/decide' in r.url and '/incidents/' in r.url and r.method == 'POST' else None)
    page.goto('http://localhost:8088')

    def tab(name):
        page.locator(f'.rail button[data-tab="{name}"]').click()

    def reset():
        tab('scenario')
        page.locator('#btnReset').click()
        expect(page.locator('#scenarioMsg')).to_contain_text('정상 운전점')

    result = {}
    try:
        reset()
        page.wait_for_function("state.det && Object.values(state.det.assets || {}).every(a => a.phase === 'IDLE')", timeout=60000)
        old = {i['id'] for i in page.request.get('http://127.0.0.1:8080/api/incidents').json()}
        page.locator('#units .unit').first.locator('[data-act=degrade]').click()
        print('Fault injected through UI', flush=True)
        tab('incidents')
        page.locator('#scada .ucard').first.click()
        page.wait_for_function('(ids) => state.incidents.some(i => !ids.includes(i.id) && i.asset === "HYD-01" && i.state === "AWAITING_APPROVAL")', arg=list(old), timeout=150000)
        incident = page.evaluate('(ids) => state.incidents.find(i => !ids.includes(i.id) && i.asset === "HYD-01" && i.state === "AWAITING_APPROVAL").id', list(old))
        page.locator('#incList .item').filter(has_text=incident).click()
        expect(page.locator('#hGo')).to_be_visible(timeout=45000)
        page.locator('.hopt').filter(has_text='즉시 제어 포함').first.click()
        page.locator('#hFan').focus()
        page.locator('#hFan').press('Home')
        for _ in range(15):
            page.locator('#hFan').press('ArrowRight')
        page.locator('#hLoad').focus()
        page.locator('#hLoad').press('Home')
        for _ in range(10):
            page.locator('#hLoad').press('ArrowRight')
        page.locator('#hBy').fill('UI 파이프라인 검증')
        page.locator('#hReason').fill('실제 UI 승인값과 PLC ACK 및 종결 검증')
        page.locator('#hRole').select_option('role:operator')
        page.wait_for_timeout(3500)
        expect(page.locator('#hFan')).to_have_value('95')
        expect(page.locator('#hLoad')).to_have_value('70')
        page.locator('#hGo').click()
        expect(page.locator('#hMsg')).not_to_be_empty(timeout=20000)
        page.screenshot(path=str(out / 'pipeline-denied.png'))
        expect(page.locator('#hFan')).to_have_value('95')
        page.locator('#hRole').select_option('role:prod-mgr')
        page.locator('#hGo').click()
        page.wait_for_function('state.detail && state.detail.ack && state.detail.ack.result === "DONE"', timeout=30000)
        print('Role denial followed by approved UI command, PLC ACK DONE', flush=True)
        page.screenshot(path=str(out / 'pipeline-ack.png'))
        page.wait_for_function('state.detail && state.detail.state === "CLOSED"', timeout=150000)
        detail = page.request.get(f'http://127.0.0.1:8080/api/incidents/{incident}').json()
        plant = page.request.get('http://127.0.0.1:8000/api/state').json()
        assert requests[-1]['fan_pct'] == 95 and requests[-1]['load_pct'] == 70
        assert requests[-1]['role'] == 'role:prod-mgr'
        assert detail['ack']['result'] == 'DONE'
        assert detail['state'] == 'CLOSED'
        assert not errors, errors
        result = {'ok': True, 'incident': incident, 'state': detail['state'], 'ack': detail['ack'], 'submitted': requests, 'history': detail.get('history'), 'unit': plant['units']['HYD-01'], 'page_errors': errors}
        page.screenshot(path=str(out / 'pipeline-closed.png'))
        print(f'PASS {incident}: fault -> denied -> 95/70 approval -> ACK DONE -> CLOSED', flush=True)
    except Exception as e:
        result = {'ok': False, 'error': str(e), 'submitted': requests, 'page_errors': errors}
        page.screenshot(path=str(out / 'pipeline-failure.png'))
        raise
    finally:
        (out / 'pipeline.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        reset()
        ctx.close()
        browser.close()
