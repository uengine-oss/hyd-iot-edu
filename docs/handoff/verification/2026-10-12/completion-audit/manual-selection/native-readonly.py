"""Only the changed document-selector journey, actual GET data and native clicks."""
from datetime import datetime,timezone
import hashlib,json,traceback
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright
T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
H=Path(__file__).parent
OUT=H/'native-final'
OUT.mkdir(exist_ok=False)
paths=['it/portal/www/index.html','it/portal/www/hitl.js','tests/test_portal_manual_document_selection_ui.py']
def hashes():return {p:hashlib.sha256((T/p).read_bytes()).hexdigest() for p in paths}
def history():
    with urlopen('http://127.0.0.1:8080/api/kg/manuals',timeout=25) as response:return json.load(response)
before=history();frozen=hashes()
proof={'created_utc':datetime.now(timezone.utc).isoformat(),'method':'Native actual GET named-document selection and stored source reopening only; no upload, ingestion or model calls','checks':[],'pageerrors':[],'consoleErrors':[],'blockedWrites':[],'source_before':frozen,'screenshots':[],'whole_reruns':0,'llm_reruns':0}
def check(label,passed,detail=None):proof['checks'].append({'label':label,'passed':bool(passed),'detail':detail})
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
try:
    for path in paths[:2]:
        with urlopen('http://127.0.0.1:8088/'+path.removeprefix('it/portal/www/')+'?sha='+frozen[path]) as response:
            check('mounted '+path,hashlib.sha256(response.read()).hexdigest()==frozen[path])
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1440,'height':1000},service_workers='block')
        def guard(route):
            if route.request.method in ('GET','HEAD','OPTIONS'):route.continue_()
            else:proof['blockedWrites'].append({'url':route.request.url,'method':route.request.method});route.abort()
        page.route('**/*',guard)
        page.on('pageerror',lambda e:proof['pageerrors'].append(str(e)))
        page.on('console',lambda m:proof['consoleErrors'].append(m.text) if m.type=='error' else None)
        page.goto('http://127.0.0.1:8088/',wait_until='domcontentloaded')
        page.locator('[data-tab=knowledge]').click()
        page.locator('#manualHistory h2').wait_for()
        current=[u for u in before if u.get('current')]
        selector=page.locator('#manualDocumentId')
        check('selector is named select',selector.evaluate('el=>el.tagName')=='SELECT')
        check('initial new-document choice',selector.input_value()=='')
        options=selector.locator('option').evaluate_all('(els)=>els.map(e=>({value:e.value,text:e.textContent}))')
        save('initial-options.json',options)
        check('only current documents plus new in primary list',{x['value'] for x in options}=={''}|{u['document_id'] for u in current})
        check('no opaque ids in displayed option text',all(not any(u['document_id'] in x['text'] for u in before) for x in options))
        check('no document ID label',page.locator('label[for=manualDocumentId]').inner_text()=='등록할 문서')
        target=next(u for u in current if u['filename'].startswith('PM-02'))
        selector.select_option(target['document_id'])
        check('named selection preserves exact current id',selector.input_value()==target['document_id'])
        check('named selection shows original source filename',target['filename'] in selector.locator('option:checked').inner_text())
        for width in (1440,1024):
            page.set_viewport_size({'width':width,'height':1000})
            page.locator('#manualUpload').scroll_into_view_if_needed()
            file=f'form-named-document-{width}.png';page.screenshot(path=str(OUT/file));proof['screenshots'].append({'file':file,'sha256':hashlib.sha256((OUT/file).read_bytes()).hexdigest()})
        source_selector='[data-manual-reopen="'+target['source_id']+'"]'
        for _ in range(6):
            if page.locator(source_selector).count():break
            fold=page.locator('#manualSources > details')
            if fold.get_attribute('open') is None:fold.locator(':scope > summary').click()
            next_button=page.locator('#manualSourcesNext')
            assert next_button.count(),'Actual source was not in the bounded source list'
            with page.expect_response(lambda r:r.request.method=='GET' and '/api/kg/manuals/sources?' in r.url):next_button.click()
        fold=page.locator('#manualSources > details')
        if fold.get_attribute('open') is None:fold.locator(':scope > summary').click()
        with page.expect_response(lambda r:r.request.method=='GET' and '/preview' in r.url) as response:
            page.locator(source_selector).click()
        preview=response.value.json();save('actual-preview-identity.json',{k:preview.get(k) for k in ('document_id','source_id','filename')})
        page.locator('#manualResult .mprev').wait_for()
        check('actual original-source preview GET',response.value.status==200)
        check('preview stays bound to exact source document',preview['document_id']==target['document_id'] and selector.input_value()==preview['document_id'])
        check('preview target cannot change underneath draft',selector.is_disabled())
        check('preview does not mark reviewed',not page.locator('#manualReviewed').is_checked())
        for width in (1440,1024):
            page.set_viewport_size({'width':width,'height':1000})
            page.locator('#manualUpload').scroll_into_view_if_needed()
            file=f'form-review-document-locked-{width}.png';page.screenshot(path=str(OUT/file));proof['screenshots'].append({'file':file,'sha256':hashlib.sha256((OUT/file).read_bytes()).hexdigest()})
        browser.close()
except Exception:proof['exception']=traceback.format_exc()
finally:
    after=history()
    check('installed history unchanged',before==after)
    proof['source_after']=hashes();check('source unchanged during capture',frozen==proof['source_after'])
    check('page errors zero',not proof['pageerrors']);check('console errors zero',not proof['consoleErrors']);check('writes attempted zero',not proof['blockedWrites'])
    proof['driver_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    proof['passed']=not proof.get('exception') and all(x['passed'] for x in proof['checks'])
    save('result.json',proof)
    print(json.dumps({'passed':proof['passed'],'checks':len(proof['checks']),'failures':[c for c in proof['checks'] if not c['passed']],'exception':proof.get('exception')},ensure_ascii=False))
if not proof['passed']:raise SystemExit(1)
