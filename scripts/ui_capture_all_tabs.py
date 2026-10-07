"""A098 — capture every portal tab (desktop + narrow) with console errors, for a visual review of the real screens.

    .venv314/Scripts/python scripts/ui_capture_all_tabs.py .evidence/reaudit/a098-ui-review

Portal on :8088 (compose `portal`, static files), process on :8080. Writes <tab>-<width>.png full-page screenshots,
console.json (errors/warnings per tab), layout.json (elements wider than the viewport = horizontal overflow).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTAL = 'http://127.0.0.1:8088/'
TABS = ['main', 'home', 'scenario', 'incidents', 'trends', 'ontology', 'skills', 'decision', 'process', 'instances']
WIDTHS = [(1440, 900), (1024, 768)]


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    console, layout = {}, {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w, h in WIDTHS:
            ctx = browser.new_context(viewport={'width': w, 'height': h}, locale='ko-KR')
            pg = ctx.new_page()
            msgs = []
            pg.on('console', lambda m: msgs.append({'type': m.type, 'text': m.text[:300]}))
            pg.on('pageerror', lambda e: msgs.append({'type': 'pageerror', 'text': str(e)[:300]}))
            pg.goto(PORTAL, wait_until='networkidle'); pg.wait_for_timeout(1500)
            for tab in TABS:
                msgs.clear()
                pg.click(f'[data-tab="{tab}"]'); pg.wait_for_timeout(2500)
                try:
                    pg.wait_for_load_state('networkidle', timeout=8000)
                except Exception:  # noqa: BLE001
                    pass
                if tab == 'instances':
                    card = pg.locator('.inst-card').first
                    if card.count():
                        card.click(); pg.wait_for_timeout(2000)
                pg.screenshot(path=str(out / f'{tab}-{w}.png'), full_page=True)
                wide = pg.evaluate('''(vw) => Array.from(document.querySelectorAll('main *')).filter(e => {
                    const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > vw + 2 || r.left < -2);
                }).slice(0, 12).map(e => ({tag: e.tagName, id: e.id, cls: String(e.className).slice(0, 60), right: Math.round(e.getBoundingClientRect().right)}))''', w)
                scroll = pg.evaluate('() => ({docW: document.documentElement.scrollWidth, mainW: document.querySelector("main").scrollWidth, vw: window.innerWidth})')
                layout[f'{tab}-{w}'] = {'overflow': wide, 'scroll': scroll}
                console[f'{tab}-{w}'] = [m for m in msgs if m['type'] in ('error', 'pageerror', 'warning')]
                print(tab, w, 'console', len(console[f'{tab}-{w}']), 'overflow', len(wide), scroll, flush=True)
            ctx.close()
        browser.close()
    (out / 'console.json').write_text(json.dumps(console, ensure_ascii=False, indent=2), encoding='utf8')
    (out / 'layout.json').write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
