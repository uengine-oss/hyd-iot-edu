"""Read existing actual cases through native UI. No workflow or LLM replay."""
import hashlib
import json
import sys
import traceback
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path('D:/work/study/hyd-iot-edu')
TREE = ROOT / '.claude/worktrees/codex-portal-20261011'
HERE = Path(__file__).parent
OUT = HERE / sys.argv[1]
CASES = {'B': 'c3_pm.d99ee952-f943-42fd-ba53-745b569522f7',
         'C': 'c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f'}
PORTAL = 'http://127.0.0.1:8088/'
API = 'http://127.0.0.1:8080'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def get(path):
    with urlopen(API + path, timeout=30) as r:
        return json.load(r)

def projection(view):
    return {k: view.get(k) for k in ('instance', 'workitems', 'approvals', 'effects', 'reworks')}

OUT.mkdir(exist_ok=False)
result = {'passed': False, 'method': 'native GET views of existing B/C; no workflow replay',
          'checks': [], 'pageerrors': [], 'consoleErrors': [], 'requestFailures': [],
          'blockedWrites': [], 'screenshots': [], 'whole_reruns': 0, 'llm_reruns': 0}

def check(label, value, detail=None):
    result['checks'].append({'label': label, 'passed': bool(value), 'detail': detail})

sources = {p.relative_to(TREE).as_posix(): sha(p.read_bytes())
           for p in (TREE / 'it/portal/www').rglob('*') if p.suffix in {'.js', '.css', '.html'}}
save('source-before.json', sources)
before = {}
try:
    mount = []
    for name, digest in sources.items():
        with urlopen(PORTAL + name.removeprefix('it/portal/www/') + '?sha=' + digest, timeout=30) as r:
            actual = sha(r.read())
        mount.append({'path': name, 'expected': digest, 'actual': actual, 'matches': actual == digest})
    save('mounted-source-checks.json', mount)
    check('all mounted portal bytes match captured source', all(x['matches'] for x in mount))
    if not all(x['matches'] for x in mount):
        raise AssertionError('Mounted source mismatch')
    before = {k: get('/api/instances/' + v) for k, v in CASES.items()}
    save('cases-before.json', before)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, service_workers='block')
        def guard(route):
            if route.request.method in {'GET', 'HEAD', 'OPTIONS'}:
                route.continue_()
            else:
                result['blockedWrites'].append({'method': route.request.method, 'url': route.request.url})
                route.abort()
        context.route('**/*', guard)
        page = context.new_page()
        page.set_default_timeout(20000)
        page.on('pageerror', lambda e: result['pageerrors'].append(str(e)))
        page.on('console', lambda m: result['consoleErrors'].append(m.text) if m.type == 'error' else None)
        page.on('requestfailed', lambda r: result['requestFailures'].append({'url': r.url, 'failure': r.failure}))
        def shot(name, target, width):
            target.scroll_into_view_if_needed()
            target.evaluate('el=>{for(let p=el.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll/.test(s.overflowY)&&p.scrollHeight>p.clientHeight){p.scrollTop+=el.getBoundingClientRect().top-Math.max(p.getBoundingClientRect().top,110)-15;}}window.scrollBy(0,el.getBoundingClientRect().top-125);}')
            page.wait_for_timeout(200)
            filename = name + '-' + str(width) + '.png'
            page.screenshot(path=str(OUT / filename))
            result['screenshots'].append({'file': filename, 'sha256': sha((OUT / filename).read_bytes())})
        page.goto(PORTAL, wait_until='domcontentloaded')
        page.locator('[data-tab="instances"]').click()
        for key, case in CASES.items():
            page.evaluate('(id)=>window.hydInstancesSelect(id)', case)
            page.wait_for_function('(id)=>window.hydInstances.I.view?.instance?.proc_inst_id===id', arg=case)
            page.locator('[data-inst-tab="record"]').click()
            page.locator('#instRecord [data-cr-all]').wait_for()
            if page.locator('#instRecord [data-cr-all]').inner_text() == '모두 펼치기':
                page.locator('#instRecord [data-cr-all]').click()
            host = page.locator('#instRecord')
            for width in (1440, 1024):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.wait_for_timeout(250)
                text = host.inner_text()
                check(key + ' record renderer succeeds ' + str(width), host.locator('.cr-error').count() == 0 and '처리 기록을 그리지 못했습니다' not in text)
                check(key + ' record has actual steps ' + str(width), host.locator('[data-cr-steps] > li').count() > 0)
                check(key + ' no object coercion ' + str(width), '[object Object]' not in text)
                if key == 'B':
                    bounds = host.locator('.cr-kv dd').evaluate_all('els=>els.filter(e=>e.checkVisibility()).map(e=>{const r=document.createRange();r.selectNodeContents(e);const b=e.getBoundingClientRect();return {text:e.textContent,left:b.left,right:b.right,rects:Array.from(r.getClientRects()).map(x=>({left:x.left,right:x.right}))}})')
                    bad = [b for b in bounds if any(r['left'] < b['left'] - 1 or r['right'] > b['right'] + 1 for r in b['rects'])]
                    check('B actual value ranges fit cells ' + str(width), bool(bounds) and not bad, bad)
                    check('B actual source package remains visible ' + str(width), '2,000' in text or '2000' in text)
                (OUT / (key + '-record-' + str(width) + '.txt')).write_text(text, encoding='utf-8')
                shot(key + '-record', host, width)
                steps = host.locator('[data-cr-steps] > li')
                for n, step in enumerate(steps.all(), 1):
                    st = step.inner_text()
                    if key == 'B' and ('다시 수행으로 대체됨' in st or '평가 보류' in st or '확인할 수 없' in st or '작동유' in st):
                        check('B inactive step no live text ' + str(n) + '/' + str(width),
                              '지금 일하는 중입니다' not in st and '다음 행동을 정하는 중' not in st)
                        check('B inactive step no active spinner ' + str(n) + '/' + str(width), step.locator('.cr-now .tr-spin').count() == 0)
                        shot('B-step-' + str(n).zfill(2), step, width)
            if key in {'B', 'C'}:
                starts = [e for e in before[key].get('events', []) if e.get('event_type') == 'task_started' and any(w['id'] == e.get('todo_id') and w.get('activity_id') == 'T_agent' for w in before[key]['workitems'])]
                latest = max(starts, key=lambda e: e.get('timestamp') or '')
                wid = latest['todo_id']
                page.goto(PORTAL + '#/instances/' + quote(case, safe='') + '/task/' + quote(wid, safe=''), wait_until='domcontentloaded')
                page.wait_for_function('id=>window.hydTaskDetail?.T.wid===id', arg=wid)
                panel = page.locator('#taskDetailPanel [data-task-detail]')
                panel.wait_for()
                for width in (1440, 1024):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    page.wait_for_timeout(200)
                    text = panel.inner_text()
                    if key == 'B':
                        check('B deferred task no live claim ' + str(width), '지금 일하는 중입니다' not in text and '다음 행동을 정하는 중' not in text)
                        check('B deferred task not labeled live ' + str(width), panel.locator('.card-chips .live-dot').count() == 0)
                    check(key + ' task no object coercion ' + str(width), '[object Object]' not in text)
                    (OUT / (key + '-task-' + str(width) + '.txt')).write_text(text, encoding='utf-8')
                    shot(key + '-task', panel, width)
                    if key == 'C':
                        output = panel.locator('[data-k="output"]')
                        if output.get_attribute('open') is None:
                            output.locator('summary').click()
                        check('C purchase output no internal skill ID ' + str(width), 'skill:sop-' not in output.inner_text())
                        check('C purchase scope names actual part ' + str(width), '펌프' in output.inner_text() and '씰' in output.inner_text())
                        shot('C-task-output', output, width)
                page.locator('[data-tab="instances"]').click()
        browser.close()
except Exception:
    result['exception'] = traceback.format_exc()
finally:
    if before:
        after = {k: get('/api/instances/' + v) for k, v in CASES.items()}
        save('cases-after.json', after)
        for k in before:
            check(k + ' persisted case/task/approval/effect unchanged', projection(before[k]) == projection(after[k]))
    after_sources = {p.relative_to(TREE).as_posix(): sha(p.read_bytes()) for p in (TREE / 'it/portal/www').rglob('*') if p.suffix in {'.js', '.css', '.html'}}
    save('source-after.json', after_sources)
    check('source stable throughout capture', sources == after_sources)
    check('no uncaught page errors', not result['pageerrors'], result['pageerrors'])
    check('no console errors', not result['consoleErrors'], result['consoleErrors'])
    check('no attempted writes', not result['blockedWrites'], result['blockedWrites'])
    result['passed'] = not result.get('exception') and all(x['passed'] for x in result['checks'])
    save('result.json', result)
    print(json.dumps({'passed': result['passed'], 'checks': len(result['checks']), 'failures': [x for x in result['checks'] if not x['passed']], 'exception': result.get('exception'), 'out': str(OUT)}, ensure_ascii=False))
sys.exit(0 if result['passed'] else 1)
