"""A158 — capture the mini-ProcessGPT screens in their working state (not just the empty first view), for the report.

    .venv/bin/python scripts/ui_capture_a158.py .evidence/a158/screens-detail [<anomaly instance id>]

Portal :8088, process :8080. Read-only: every click here is a view, a read-only fabric query, or a dry-run calculation
(What-if loads a baseline without writing). Per screen: a screenshot of the main area, console errors, and visible English
identifiers (same rule as ui_capture_all_tabs.py). The task-detail shots open #/instances/<id>/task/<activity> for each
activity of the given (default: newest completed 설비 이상 조치) instance.
"""
import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTAL = 'http://127.0.0.1:8088/'
PROCESS = 'http://127.0.0.1:8080'
IGNORE = ('127.0.0.1:1881', 'localhost:1881', ':8085', ':9644')
RESIDUE_JS = r'''(sel) => {
    const root = document.querySelector(sel); if (!root) return ['(없음) ' + sel];
    const hits = new Set(), re = /\b[a-z][a-z0-9]*(?:[_-][a-z0-9]+)+\b|\bundefined\b|\bNaN\b|\[object \w+\]/g;
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n; (n = walk.nextNode());) {
        const el = n.parentElement; if (!el || !el.checkVisibility?.() || el.closest('code,pre,textarea,input,select')) continue;
        for (const m of n.textContent.matchAll(re)) hits.add(m[0]);
    }
    return [...hits].slice(0, 40);
}'''


def get(path):
    with urllib.request.urlopen(PROCESS + path, timeout=10) as r:
        return json.load(r)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else '.evidence/a158/screens-detail'); out.mkdir(parents=True, exist_ok=True)
    inst = sys.argv[2] if len(sys.argv) > 2 else next(i['proc_inst_id'] for i in get('/api/instances?limit=50')
                                                       if i['proc_def_id'] == 'anomaly_response' and i['status'] == 'COMPLETED')
    view = get('/api/instances/' + inst)
    done = [t for t in (view.get('workitems') or []) if t.get('activity_id')]
    acts = list(dict.fromkeys(t['activity_id'] for t in done))
    report = {'instance': inst, 'shots': {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='ko-KR').new_page()
        msgs = []
        pg.on('console', lambda m: msgs.append({'type': m.type, 'text': m.text[:300], 'url': (m.location or {}).get('url', '')}))
        pg.on('pageerror', lambda e: msgs.append({'type': 'pageerror', 'text': str(e)[:300]}))
        pg.goto(PORTAL, wait_until='networkidle'); pg.wait_for_timeout(1500)

        def shot(name, sel='main'):
            pg.wait_for_timeout(800)
            el = pg.locator(sel).first
            el.screenshot(path=str(out / f'{name}.png'))
            bad = [m for m in msgs if m['type'] in ('error', 'pageerror') and not any(k in m['text'] or k in m['url'] for k in IGNORE)]
            report['shots'][name] = {'english': pg.evaluate(RESIDUE_JS, sel), 'console_errors': bad}
            msgs.clear()
            print(name, 'english', report['shots'][name]['english'], 'errors', len(bad), flush=True)

        def tab(name):
            pg.evaluate('(t) => { location.hash = "#/" + t; }', name); pg.wait_for_timeout(2500)
            try:
                pg.wait_for_load_state('networkidle', timeout=8000)
            except Exception:  # noqa: BLE001
                pass

        # A1 처리 건 → task 상세 (단계마다)
        for i, act in enumerate(acts):
            pg.evaluate('(h) => { location.hash = h; }', f'#/instances/{inst}/task/{act}')
            try:
                pg.wait_for_selector('[data-task-detail]', timeout=15000)
            except Exception:  # noqa: BLE001
                pass
            pg.wait_for_timeout(2500)
            shot(f'a1-task-{i + 1:02d}-{act}', '[data-task-detail]' if pg.locator('[data-task-detail]').count() else 'main')
        tab('instances'); shot('a1-instances')
        # A11 데이터 연결 — 읽기 전용 교차 조회
        tab('fabric'); pg.click('#fabRun')
        try:
            pg.wait_for_selector('#fabResult .card', timeout=30000)
        except Exception:  # noqa: BLE001
            pass
        shot('a11-fabric-result')
        # A7 What-if — 기준 불러오기(시험 계산, 쓰기 없음)
        tab('whatif'); pg.click('#wiLoad')
        try:
            pg.wait_for_selector('[data-wi-tab]', timeout=90000)
        except Exception:  # noqa: BLE001
            pass
        shot('a7-whatif-base')
        # A2 에이전트 · MCP
        tab('agents'); shot('a2-agents')
        tab('mcp'); shot('a2-mcp-tools')
        if pg.locator('[data-mcp-tab="calls"]').count():
            pg.click('[data-mcp-tab="calls"]'); shot('a2-mcp-calls')
        # A3 내 작업함 — 김운전으로
        tab('inbox')
        sel = pg.locator('[data-inbox-me]').first
        if sel.count():
            opts = sel.evaluate('s => [...s.options].map(o => [o.value, o.textContent])')
            pick = next((v for v, t in opts if '김운전' in t), opts[1][0] if len(opts) > 1 else '')
            if pick:
                sel.select_option(pick); pg.wait_for_timeout(2500)
        shot('a3-inbox')
        for t in ('eval', 'compare', 'kpi'):
            tab(t); shot(f'tab-{t}')
        browser.close()
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
