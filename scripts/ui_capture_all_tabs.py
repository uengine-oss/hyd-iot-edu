"""A098/A122 — capture every portal tab (desktop + narrow) with console errors, for a visual review of the real screens.

    .venv314/Scripts/python scripts/ui_capture_all_tabs.py .evidence/a122 [--full] [--decide] [--tabs main,home,...]

Portal on :8088 (compose `portal`, static files), process on :8080. Writes <tab>-<width>.png screenshots,
console.json (errors/warnings per tab; the FUXA :1881 health probe's ERR_CONNECTION_REFUSED is listed separately as `ignored`),
layout.json (elements wider than the viewport = horizontal overflow, plus document/main scroll widths).

--full    full-length pages: <main> normally scrolls inside the shell, so the shell is unlocked (body/main overflow visible)
          before each screenshot; the viewport itself stays 1440/1024 wide so overflow numbers are the real ones.
--decide  run the rules-only judgment on the 조치 판단 규칙 tab (POST /api/agent/decide with do_submit=False on the agent — no
          decision is submitted to the process service) so the result cards are captured too.
Each tab also selects its first item (설비 카드 HYD-01 on 이상 확인 · 조치, first 처리 건, first 판단) so detail panes render.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTAL = 'http://127.0.0.1:8088/'
TABS = ['main', 'home', 'scenario', 'incidents', 'trends', 'ontology', 'skills', 'decision', 'process', 'instances', 'knowledge', 'admin']
WIDTHS = [(1440, 900), (1024, 768)]
UNLOCK_CSS = 'body{height:auto!important;overflow:visible!important} main{overflow:visible!important;min-height:0!important} .list{max-height:none!important} .split>div:first-child{position:static!important} .inst-events,.stream-list,.onto-map{max-height:none!important}'
IGNORE = ('127.0.0.1:1881', 'localhost:1881', ':8085', ':9090', ':9644')   # optional tools (FUXA · Redpanda console · Prometheus) off: their probes fail by design


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a.split('=')[0]: (a.split('=', 1)[1] if '=' in a else True) for a in sys.argv[1:] if a.startswith('--')}
    out = Path(args[0] if args else '.evidence/a122'); out.mkdir(parents=True, exist_ok=True)
    tabs = flags['--tabs'].split(',') if isinstance(flags.get('--tabs'), str) else TABS
    full = '--full' in flags
    console, layout = {}, {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w, h in WIDTHS:
            ctx = browser.new_context(viewport={'width': w, 'height': h}, locale='ko-KR')
            pg = ctx.new_page()
            msgs = []
            pg.on('console', lambda m: msgs.append({'type': m.type, 'text': m.text[:300], 'url': (m.location or {}).get('url', '')}))
            pg.on('pageerror', lambda e: msgs.append({'type': 'pageerror', 'text': str(e)[:300]}))
            pg.goto(PORTAL, wait_until='networkidle'); pg.wait_for_timeout(1500)
            for tab in tabs:
                msgs.clear()
                pg.click(f'[data-tab="{tab}"]'); pg.wait_for_timeout(2500)
                try:
                    pg.wait_for_load_state('networkidle', timeout=8000)
                except Exception:  # noqa: BLE001
                    pass
                if tab == 'incidents':
                    card = pg.locator('.ucard').first
                    if card.count():
                        card.click(); pg.wait_for_timeout(3000)
                if tab == 'instances':
                    card = pg.locator('.inst-card').first
                    if card.count():
                        card.click(); pg.wait_for_timeout(2500)
                if tab == 'process':
                    pg.wait_for_timeout(2500)
                if tab == 'decision' and '--decide' in flags:
                    pg.click('#decRun')
                    try:
                        pg.wait_for_selector('#decResult .hitl-opts, #decResult .empty b', timeout=60000)
                    except Exception:  # noqa: BLE001
                        pass
                    pg.wait_for_timeout(1000)
                if tab in ('knowledge', 'admin'):
                    for d in pg.locator(f'#view-{tab} details.admin-panel').all():
                        d.evaluate('d => d.open = true')
                    pg.wait_for_timeout(1500)
                style = None
                if full:
                    style = pg.add_style_tag(content=UNLOCK_CSS); pg.wait_for_timeout(400)
                pg.screenshot(path=str(out / f'{tab}-{w}.png'), full_page=True)
                if '--crops' in flags:   # 1300 px pages of the same full-length page, for reading without an image library
                    (out / 'crops').mkdir(exist_ok=True)
                    docH = pg.evaluate('() => document.documentElement.scrollHeight')
                    for i in range(min(6, (docH + 1299) // 1300)):
                        pg.screenshot(path=str(out / 'crops' / f'{tab}-{w}-p{i}.png'), full_page=True, clip={'x': 0, 'y': i * 1300, 'width': w, 'height': min(1300, docH - i * 1300)})
                wide = pg.evaluate('''(vw) => Array.from(document.querySelectorAll('main *')).filter(e => {
                    const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > vw + 2 || r.left < -2);
                }).slice(0, 12).map(e => ({tag: e.tagName, id: e.id, cls: String(e.className).slice(0, 60), right: Math.round(e.getBoundingClientRect().right)}))''', w)
                scroll = pg.evaluate('() => ({docW: document.documentElement.scrollWidth, mainW: document.querySelector("main").scrollWidth, vw: window.innerWidth, docH: document.documentElement.scrollHeight})')
                if style is not None:
                    style.evaluate('s => s.remove()')
                layout[f'{tab}-{w}'] = {'overflow': wide, 'scroll': scroll}
                bad = [m for m in msgs if m['type'] in ('error', 'pageerror', 'warning')]
                ign = lambda m: any(k in m['text'] or k in m.get('url', '') for k in IGNORE)
                console[f'{tab}-{w}'] = {'errors': [m for m in bad if not ign(m)], 'ignored': [m for m in bad if ign(m)]}
                print(tab, w, 'console', len(console[f'{tab}-{w}']['errors']), 'ignored', len(console[f'{tab}-{w}']['ignored']), 'overflow', len(wide), scroll, flush=True)
            ctx.close()
        browser.close()
    (out / 'console.json').write_text(json.dumps(console, ensure_ascii=False, indent=2), encoding='utf8')
    (out / 'layout.json').write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
