"""A141 — 포털 다이어트 검증: 12탭 × (1440 · 1024) 각 1회 캡처 + 기계 검사 + 눈 검토용 조각 4장.

    PYTHONUTF8=1 .venv314/Scripts/python.exe scripts/ui_check_a141.py .evidence/a141            # 캡처 + 검사
    PYTHONUTF8=1 .venv314/Scripts/python.exe scripts/ui_check_a141.py .evidence/a141 --no-shots # 검사만(개발 중 빠른 확인, 캡처 없음)

검사(화면에 보이는 글자만 — 닫힌 접기 안은 innerText 에 포함되지 않는다):
  · 콘솔 오류 0 (선택 도구 1881 · 8085 · 9090 프로브는 제외)   · 문서 폭 넘침 0 (viewport 보다 넓은 요소)
  · 가시 텍스트에 fm: · rule: · cause: id 0                     · 영문 단계 문구 0 (알려진 영문 로그 조각 + 영어 소문자 3단어 이상 문장)
  · 탭마다 "사용자가 할 행동" 버튼의 화면 위 위치(px) — 10초 안에 보이는가의 판정 근거
조치 판단 규칙 탭은 --decide 로 규칙 전용 판단을 실제 실행(do_submit=False, 제출 없음). 승인 · 결정 버튼은 누르지 않는다.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTAL = 'http://127.0.0.1:8088/'
TABS = ['main', 'home', 'scenario', 'incidents', 'trends', 'ontology', 'skills', 'decision', 'process', 'instances', 'knowledge', 'admin']
WIDTHS = [(1440, 900), (1024, 768)]
UNLOCK_CSS = 'body{height:auto!important;overflow:visible!important} main{overflow:visible!important;min-height:0!important} .list{max-height:none!important} .split>div:first-child{position:static!important} .inst-events,.stream-list,.onto-map{max-height:none!important}'
IGNORE = ('127.0.0.1:1881', 'localhost:1881', ':8085', ':9090', ':9644')
ID_RE = re.compile(r'\b(?:fm|rule|cause):[A-Za-z0-9_.-]+')
ENGLISH_BITS = ['submitted by', 'waiting for', 'cancelled:', 'delivery pending', 'approval accepted', 'sim-s', 'cleared before', 'reclaimed by', 'issued; waiting',
                'anomaly response', 'legacy agent', 'rework superseded', 'reached by abort', 'Lease expired', 'tracked separately']
SENTENCE_RE = re.compile(r'\b[a-z]{3,} [a-z]{2,} [a-z]{3,}\b')          # 영어 소문자 단어 3개 연속 = 번역 안 된 문장 후보
ALLOW_SENTENCE = ('bar', 'mm/s', 'kW', 'l/min')                             # 단위 조합은 문장이 아니다
# 탭별 "사용자가 할 행동" 버튼(있을 때만): 화면 위에서 얼마나 아래에 있는지 잰다
ACTION = {'main': '#mainOperate', 'scenario': '#units .btn.danger', 'incidents': '#hGoInstance, #hGo, .hitl .btn, .ucard', 'decision': '#decRun', 'process': '#decApprove, #decList .item',
          'instances': '#tdGo, #tdDone, #tdAnswerGo, #todoList .item', 'knowledge': '#manualPreview', 'skills': '#skSave', 'ontology': '#ontoAsset', 'admin': '#sourceEventsPanel summary'}
CROPS = {('incidents', 1440): '#hitlPanel', ('instances', 1440): '#todoPanel', ('process', 1024): '#procBpmn', ('knowledge', 1440): '#manualHistory .manual-doc'}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a.split('=')[0]: (a.split('=', 1)[1] if '=' in a else True) for a in sys.argv[1:] if a.startswith('--')}
    out = Path(args[0] if args else '.evidence/a141'); out.mkdir(parents=True, exist_ok=True)
    shots = '--no-shots' not in flags
    tabs = flags['--tabs'].split(',') if isinstance(flags.get('--tabs'), str) else TABS
    console, layout, facts = {}, {}, {}
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
                    for key in ('flow', 'log'):          # 세 탭 모두 그려 보고 검사(캡처는 결과 탭 상태)
                        t = pg.locator(f'[data-inst-tab="{key}"]')
                        if t.count():
                            t.click(); pg.wait_for_timeout(800); collect_text(pg, facts, f'{tab}-{w}-{key}')
                    t = pg.locator('[data-inst-tab="result"]')
                    if t.count():
                        t.click(); pg.wait_for_timeout(500)
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
                    pg.wait_for_timeout(2500)
                key = f'{tab}-{w}'
                collect_text(pg, facts, key)
                sel = ACTION.get(tab)
                if sel:
                    facts[key]['actionTop'] = pg.evaluate('''(sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); const m = document.querySelector('main'); return Math.round(r.top + m.scrollTop); }''', sel)
                style = None
                if shots:
                    crop = CROPS.get((tab, w))
                    if crop and pg.locator(crop).first.count():
                        pg.locator(crop).first.screenshot(path=str(out / f'crop-{tab}-{w}.png'))
                    style = pg.add_style_tag(content=UNLOCK_CSS); pg.wait_for_timeout(400)
                    pg.screenshot(path=str(out / f'{tab}-{w}.png'), full_page=True)
                # .onto-map 안의 SVG 는 지도 자체의 스크롤 영역(A122 와 같은 12개 path) — 문서 폭 넘침이 아니다
                wide = pg.evaluate('''(vw) => Array.from(document.querySelectorAll('main *')).filter(e => !e.closest('.onto-map')).filter(e => {
                    const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > vw + 2 || r.left < -2);
                }).slice(0, 12).map(e => ({tag: e.tagName, id: e.id, cls: String(e.className).slice(0, 60), right: Math.round(e.getBoundingClientRect().right)}))''', w)
                scroll = pg.evaluate('() => ({docW: document.documentElement.scrollWidth, mainW: document.querySelector("main").scrollWidth, vw: window.innerWidth, docH: document.documentElement.scrollHeight, flowScroll: Array.from(document.querySelectorAll(".flow-scroll")).map(e => e.scrollWidth - e.clientWidth)})')
                if style is not None:
                    style.evaluate('s => s.remove()')
                layout[key] = {'overflow': wide, 'scroll': scroll}
                bad = [m for m in msgs if m['type'] in ('error', 'pageerror', 'warning')]
                ign = lambda m: any(k in m['text'] or k in m.get('url', '') for k in IGNORE)
                console[key] = {'errors': [m for m in bad if not ign(m)], 'ignored': [m for m in bad if ign(m)]}
                f = facts[key]
                print(tab, w, 'console', len(console[key]['errors']), 'overflow', len(wide), 'ids', len(f['ids']), 'english', len(f['english']), 'actionTop', f.get('actionTop'), 'flowScroll', scroll['flowScroll'], flush=True)
            ctx.close()
        browser.close()
    (out / 'console.json').write_text(json.dumps(console, ensure_ascii=False, indent=2), encoding='utf8')
    (out / 'layout.json').write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding='utf8')
    (out / 'facts.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding='utf8')
    total = {'console': sum(len(v['errors']) for v in console.values()), 'overflow': sum(len(v['overflow']) for v in layout.values()),
             'ids': sum(len(v['ids']) for v in facts.values()), 'english': sum(len(v['english']) for v in facts.values()),
             'flowScroll': sum(1 for v in layout.values() for x in v['scroll']['flowScroll'] if x > 0 and v['scroll']['vw'] <= 1100)}
    print('TOTAL', json.dumps(total))
    return 0 if not any(total.values()) else 1


def collect_text(pg, facts, key):
    # select 의 선택지는 등록된 정의 · 상태 이름(데이터)이지 단계 로그가 아니므로 뺀다
    text = pg.evaluate('''() => { const m = document.querySelector("main").cloneNode(true); m.querySelectorAll("select, pre").forEach(e => e.remove()); document.body.appendChild(m); const t = m.innerText; m.remove(); return t; }''')
    ids = sorted(set(ID_RE.findall(text)))
    english = sorted(set([b for b in ENGLISH_BITS if b in text] + [m.group(0) for m in SENTENCE_RE.finditer(text) if not any(u in m.group(0) for u in ALLOW_SENTENCE)]))
    facts[key] = {'chars': len(text), 'ids': ids, 'english': english}


if __name__ == '__main__':
    raise SystemExit(main())
