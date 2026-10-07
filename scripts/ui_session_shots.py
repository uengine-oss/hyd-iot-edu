"""A147 — 회차 03 · 05 · 06 · 18 의 [화면] 단계를 실제 화면으로 캡처(읽기 전용: 로그인 · 선택 · 접기 열기 · 구독만, 제출 · 설정 변경 없음).

    PYTHONUTF8=1 python scripts/ui_session_shots.py            # → .evidence/sessions/<NN>/screen-*.png + screen-facts.json

03  EMQX 대시보드 Clients 목록 · WebSocket Client 로 plant/hyd01/# 구독 시도 · Grafana hyd-trend(HYD-01)
05  포털 지식 지도 → 이상 패턴 경로(쿨러 성능 저하)로 강조
06  포털 지식 지도 → 층 칩에서 "전략 목표"만 켬
18  포털 처리 건 → 완료된 쿨러 처리 건 → 기록 탭 → "지식 반영"(Execution 레이어 표) 접기 열기
각 회차 폴더의 screen-facts.json 에 화면에서 읽은 값(행 수 · 노드 수 · 오류 문구)을 남긴다. 실패도 그대로 적는다.
"""
import json
import os
import re
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / '.evidence' / 'sessions'
PORTAL = 'http://127.0.0.1:8088/'
EMQX = 'http://127.0.0.1:18083'
EMQX_USER, EMQX_PASS = 'admin', os.environ.get('EMQX_DASHBOARD_PASSWORD', 'public123')   # compose.yaml 기본값(회차 03 문서와 같음)
GRAFANA = 'http://127.0.0.1:3000/d/hyd-trend?orgId=1&var-asset=HYD-01&from=now-15m&to=now'


def save(nn, facts):
    d = EV / nn; d.mkdir(parents=True, exist_ok=True)
    (d / 'screen-facts.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding='utf8')
    print(nn, json.dumps(facts, ensure_ascii=False)[:600], flush=True)


def shot(page, nn, name, **kw):
    path = EV / nn / f'screen-{name}.png'; path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), **kw)
    return path.name


def s03(browser):
    facts = {'files': [], 'console_errors': []}
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR'); pg = ctx.new_page()
    pg.on('console', lambda m: m.type == 'error' and facts['console_errors'].append(m.text[:200]))
    pg.goto(EMQX + '/', wait_until='networkidle'); pg.wait_for_timeout(1500)
    pg.locator('input').nth(0).fill(EMQX_USER); pg.locator('input[type=password]').first.fill(EMQX_PASS)
    pg.keyboard.press('Enter'); pg.wait_for_timeout(4000)
    facts['after_login_url'] = pg.url
    body = pg.locator('body').inner_text()
    facts['password_change_asked'] = bool(re.search(r'change.*password|비밀번호.*변경|default password', body, re.I))
    if facts['password_change_asked']:
        facts['files'].append(shot(pg, '03', 'emqx-login')); facts['stopped'] = '첫 로그인 비밀번호 변경 요구 — 바꾸지 않고 멈춤'
    else:
        pg.goto(EMQX + '/#/clients', wait_until='networkidle'); pg.wait_for_timeout(3000)
        text = pg.locator('body').inner_text()
        facts['clients_seen'] = sorted(set(re.findall(r'\b(plant-sim-edge|connect-ingest|cmd-gateway|mqttjs_[0-9a-f]+)\b', text)))
        facts['files'].append(shot(pg, '03', 'emqx-clients'))
        pg.goto(EMQX + '/#/websocket', wait_until='networkidle'); pg.wait_for_timeout(2500)
        facts['ws_page_url'] = pg.url
        inputs = pg.locator('input:visible')
        facts['ws_inputs'] = [inputs.nth(i).input_value() for i in range(min(inputs.count(), 8))]
        btn = pg.get_by_role('button', name=re.compile(r'^\s*(Connect|연결)\s*$'))
        if btn.count():
            btn.first.click(); pg.wait_for_timeout(6000)
            facts['ws_after_connect'] = re.findall(r'(Connected|Disconnected|Connecting|connect(?:ion)? (?:failed|error)[^\n]*|연결[^\n]{0,20})', pg.locator('body').inner_text())[:6]
            # A148: EMQX 5.8 shows a "Disconnect" button once connected (no "Connected" text), and the Topic input carries
            # the default value "testtopic/#" with no placeholder
            facts['ws_connected'] = pg.get_by_role('button', name=re.compile(r'^\s*Disconnect\s*$')).count() > 0
            topic = pg.locator('input[placeholder*="opic"], input[placeholder*="토픽"]')
            if not topic.count():                                  # Vue keeps the value off the DOM attribute: find it by value
                vis = pg.locator('input:visible')
                for i in range(vis.count()):
                    if vis.nth(i).input_value() == 'testtopic/#':
                        topic = vis.nth(i); break
            if topic.count():
                topic.first.fill('plant/hyd01/#')
                sub = pg.get_by_role('button', name=re.compile(r'^\s*(Subscribe|구독)\s*$'))
                if sub.count() and sub.first.is_enabled():
                    sub.first.click(); pg.wait_for_timeout(5000)
                    facts['ws_messages_text'] = len(re.findall(r'plant/hyd01/', pg.locator('body').inner_text()))
                    facts['ws_subscribed_topics'] = re.findall(r'plant/hyd01/#', pg.locator('body').inner_text())[:2]
        else:
            facts['ws_connect_button'] = 'not found'
        facts['files'].append(shot(pg, '03', 'emqx-websocket', full_page=True))
    ctx.close()
    ctx = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='ko-KR'); pg = ctx.new_page()
    pg.goto(GRAFANA, wait_until='networkidle'); pg.wait_for_timeout(6000)
    text = pg.locator('body').inner_text()
    m = re.search(r'유온 TS1 \(현재\)\s*\n\s*([0-9.]+)', text)
    facts['grafana_ts1_now'] = m.group(1) if m else None
    facts['grafana_title_seen'] = 'HYD 설비 추세' in text
    facts['files'].append(shot(pg, '03', 'grafana-hyd-trend'))
    with urllib.request.urlopen('http://127.0.0.1:8000/api/state', timeout=5) as r:     # 같은 순간 plant-sim 값(비교용)
        facts['plant_ts1_now'] = json.load(r).get('units', {}).get('HYD-01', {}).get('tags', {}).get('TS1')
    ctx.close()
    save('03', facts)


def portal_page(browser, w=1440, h=900):
    ctx = browser.new_context(viewport={'width': w, 'height': h}, locale='ko-KR'); pg = ctx.new_page()
    errs = []
    pg.on('console', lambda m: m.type in ('error', 'warning') and errs.append(m.text[:200]))
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto(PORTAL, wait_until='networkidle'); pg.wait_for_timeout(1500)
    return ctx, pg, errs


def onto_counts(pg):
    return pg.evaluate('''() => { const m = document.querySelector('#ontoMap svg'); if (!m) return null;
      const g = Array.from(m.querySelectorAll('g.o-node')); const dim = g.filter(x => x.classList.contains('dim'));
      return { nodes: g.length, dimmed: dim.length, stats: (document.querySelector('#ontoStats') || {}).innerText || '' }; }''')


def s05_06(browser):
    ctx, pg, errs = portal_page(browser)
    pg.click('[data-tab="ontology"]'); pg.wait_for_timeout(5000)
    opts = pg.eval_on_selector_all('#ontoFocus option', 'os => os.map(o => [o.value, o.textContent])')
    cooler = next((v for v, t in opts if 'COOLER' in v.upper() or '쿨러' in t), None)
    f05 = {'focus_options': opts, 'picked': cooler}
    if cooler:
        pg.select_option('#ontoFocus', cooler); pg.wait_for_timeout(2500)
    f05['map'] = onto_counts(pg)
    f05['files'] = [shot(pg, '05', 'portal-pattern-path')]
    f05['console_errors'] = list(errs)
    save('05', f05)
    errs.clear()
    pg.select_option('#ontoFocus', ''); pg.wait_for_timeout(1000)
    chips = pg.locator('#ontoLayers label.chiptoggle')
    titles = [chips.nth(i).inner_text().strip() for i in range(chips.count())]
    for i, t in enumerate(titles):
        if t != '전략 목표':
            chips.nth(i).locator('input').uncheck(); pg.wait_for_timeout(300)
    pg.wait_for_timeout(1500)
    labels = pg.evaluate('''() => Array.from(document.querySelectorAll('#ontoMap svg text')).map(t => t.textContent.trim()).filter(Boolean)''')
    f06 = {'chips': titles, 'on': ['전략 목표'], 'map': onto_counts(pg), 'node_texts_sample': labels[:40], 'node_texts_total': len(labels)}
    f06['files'] = [shot(pg, '06', 'portal-layer-bsc')]
    f06['console_errors'] = list(errs)
    save('06', f06)
    ctx.close()


def s18(browser):
    ctx, pg, errs = portal_page(browser)
    with urllib.request.urlopen('http://127.0.0.1:8080/api/instances?status=COMPLETED&limit=50', timeout=10) as r:
        rows = json.load(r)
    pick = next((x for x in rows if str(x.get('proc_inst_id', '')).startswith('anomaly_response.')), None)
    facts = {'instance': pick and pick['proc_inst_id'], 'completed_seen': len(rows)}
    pg.click('[data-tab="instances"]'); pg.wait_for_timeout(2500)
    if pick:
        pg.evaluate('id => window.hydInstancesSelect(id)', pick['proc_inst_id']); pg.wait_for_timeout(3500)
        t = pg.locator('[data-inst-tab="log"]')
        if t.count():
            t.click(); pg.wait_for_timeout(1500)
        fold = pg.locator('details.fold', has=pg.locator('summary', has_text='지식 반영')).first
        fold.evaluate('d => d.open = true'); pg.wait_for_timeout(2500)
        fold.scroll_into_view_if_needed()
        facts['table_rows'] = fold.locator('table.inst-table tbody tr').count()
        facts['definition_line'] = (fold.locator('p.kv-line').all_inner_texts() or [''])[-1]
        facts['cypher_shown'] = fold.locator('pre').count() > 0
        facts['files'] = [fold.screenshot(path=str(EV / '18' / 'screen-portal-execution-table.png')) and 'screen-portal-execution-table.png']
    facts['console_errors'] = list(errs)
    save('18', facts)
    ctx.close()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        for fn in (s03, s05_06, s18):
            try:
                fn(b)
            except Exception as e:  # noqa: BLE001 — 실패도 증거로 남긴다
                print('FAIL', fn.__name__, repr(e)[:400], flush=True)
        b.close()


if __name__ == '__main__':
    main()
