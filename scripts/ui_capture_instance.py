"""Capture one process instance's detail view in the portal (instances tab → card → detail), for reports.

    .venv314/Scripts/python scripts/ui_capture_instance.py <out.png> [<card text substring>]
Picks the card whose text contains the substring (the card shows the last 8 chars of proc_inst_id); default: first COMPLETED card.
The portal's content area scrolls inside the page, so the detail panel is screenshotted as an element, the whole page as fallback.
"""
import sys

from playwright.sync_api import sync_playwright

PORTAL = 'http://127.0.0.1:8088/'


def main():
    out = sys.argv[1]; needle = sys.argv[2] if len(sys.argv) > 2 else None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_context(viewport={'width': 1440, 'height': 1600}, locale='ko-KR').new_page()
        pg.goto(PORTAL, wait_until='networkidle'); pg.wait_for_timeout(1200)
        pg.click('[data-tab="instances"]')
        try:
            pg.wait_for_selector('#instList .inst-card', timeout=20000)
        except Exception:  # noqa: BLE001
            txt = pg.locator('#instList').inner_text() if pg.locator('#instList').count() else '(no #instList)'
            print('no cards; #instList says:', txt[:200])
        cards = pg.locator('#instList .inst-card')
        n = cards.count(); target = None
        for i in range(n):
            c = cards.nth(i); txt = c.inner_text()
            if (needle and needle in txt) or (not needle and ('완료' in txt or 'COMPLETED' in txt)):
                target = c; break
        if target is None and n:
            target = cards.first
        if target is not None:
            target.scroll_into_view_if_needed(); target.click(); pg.wait_for_timeout(3000)
            try:
                pg.wait_for_load_state('networkidle', timeout=8000)
            except Exception:  # noqa: BLE001
                pass
        detail = pg.locator('#instDetail')
        box = detail.first.bounding_box() if detail.count() else None
        if box:
            detail.first.scroll_into_view_if_needed(); box = detail.first.bounding_box()
            pg.screenshot(path=out, full_page=True, clip={'x': box['x'], 'y': box['y'], 'width': box['width'], 'height': min(box['height'], 1500)})
            print('captured #instDetail (top 1500px)', out)
        else:
            pg.screenshot(path=out, full_page=True); print('captured page', out)
        print('cards', n, 'picked', (target.inner_text()[:100].replace('\n', ' | ') if target is not None else None))
        browser.close()


if __name__ == '__main__':
    main()
