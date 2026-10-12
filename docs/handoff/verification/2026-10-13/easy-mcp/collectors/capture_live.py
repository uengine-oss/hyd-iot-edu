"""Native portal GET-only verification after deployment; references are preserved captures."""
from pathlib import Path
import hashlib,json,shutil,time,urllib.request
from playwright.sync_api import sync_playwright
R=Path('D:/work/study/hyd-iot-edu');T=R/'.claude/worktrees/codex-portal-20261011';H=R/'.evidence/easy-mcp-20261013/native-live'
H.mkdir(parents=True,exist_ok=True)
result={'kind':'actual deployed portal native browser; GET only','checks':[],'page_errors':[],'console_errors':[],'writes':[],'screens':[]}
def check(name,value):result['checks'].append({'name':name,'passed':bool(value)});assert value,name
names=['index.html','mcpConnections.js','mcpConnections.css','mcp.js','tokens.css','styles.css']
before={name:hashlib.sha256((T/'it/portal/www'/name).read_bytes()).hexdigest() for name in names}
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(args=['--disable-gpu'])
        page=browser.new_page(viewport={'width':1440,'height':1100},locale='ko-KR')
        page.on('pageerror',lambda e:result['page_errors'].append(str(e)))
        page.on('console',lambda m:result['console_errors'].append({'text':m.text,'location':m.location}) if m.type=='error' else None)
        page.on('request',lambda r:result['writes'].append({'method':r.method,'path':r.url.split('?')[0]}) if r.method not in ['GET','OPTIONS'] else None)
        page.goto('http://localhost:8088/',wait_until='domcontentloaded')
        page.locator('[data-tab="mcp"]').click()
        page.locator('#mcpConnectService option[value="other"]').wait_for(state='attached',timeout=20000)
        check('new connection UI loaded from deployed index',page.locator('#mcpConnections').is_visible())
        check('operator settings closed initially',not page.locator('#mcpOperator').evaluate('(e)=>e.open'))
        check('shared educational connection explicitly explained','공용 연결' in page.locator('#mcpConnections').inner_text())
        check('Google Drive and Calendar presets present',all(x in page.locator('#mcpConnectService').inner_text() for x in ['드라이브','캘린더']))
        check('no portal login form',page.locator('input[type="password"]:visible').count()==0)
        check('preset hides custom address visually',not page.locator('#mcpConnectUrl').is_visible())
        for action in ['reopen','cancel','disconnect']:
            check('unused '+action+' action hidden visually',not page.locator('[data-connect-'+action+']').is_visible())
        page.locator('#mcpConnectService').select_option('other')
        page.locator('#mcpConnectUrl').fill('https://example.com/mcp')
        page.locator('#mcpConnectUrl').focus()
        time.sleep(2)
        check('custom address retained with focus',page.locator('#mcpConnectUrl').input_value()=='https://example.com/mcp' and page.locator('#mcpConnectUrl').evaluate('(e)=>document.activeElement===e'))
        page.locator('#mcpConnectService').select_option('google-drive')
        check('custom address hides again after selecting preset',not page.locator('#mcpConnectUrl').is_visible())
        for width in [1440,1024]:
            page.set_viewport_size({'width':width,'height':1100})
            check('no horizontal overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            name='mcp-connections-'+str(width)+'.png';page.screenshot(path=str(H/name),full_page=True);result['screens'].append(name)
        check('native page errors absent',not result['page_errors'])
        check('native console errors absent',not result['console_errors'])
        check('production writes absent',not result['writes'])
        browser.close()
    served={}
    for name in names:
        with urllib.request.urlopen('http://localhost:8088/'+name,timeout=15) as response:served[name]=hashlib.sha256(response.read()).hexdigest()
    check('served product bytes equal frozen source',served==before)
    check('source unchanged during capture',before=={name:hashlib.sha256((T/'it/portal/www'/name).read_bytes()).hexdigest() for name in names})
    result['source_sha']=before
    refs=json.loads((R/'.evidence/delegated-review-20261012/reference-provenance.json').read_text(encoding='utf-8'))
    for row in refs:
        src=Path(row['copy']);assert hashlib.sha256(src.read_bytes()).hexdigest()==row['sha256'];shutil.copyfile(src,H/('reference-'+row['label'].lower()+'.png'))
    result['reference_provenance']=refs
    html='''<!doctype html><html lang=ko><meta charset=utf-8><title>참고 화면과 실제 HYD</title><style>body{font-family:Arial,sans-serif;margin:20px;background:#f2f4f7;color:#172338}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}article{background:white;padding:12px;border:1px solid #d9dee8}img{width:100%;height:auto}h2{font-size:20px}p{font-size:16px}</style><h1>보존 참고 화면 · 현재 실제 포털</h1><p>ProcessGPT와 Dify는 출처·SHA가 있는 보존 캡처입니다. HYD는 배포 후 실제 브라우저 GET 화면입니다. 로그인 동작 증거는 별도 격리 HTTP 시험이며 실제 Google 동의를 뜻하지 않습니다.</p><div class=grid><article><h2>ProcessGPT · 보존 원본</h2><img src=reference-processgpt.png></article><article><h2>Dify · 보존 원본</h2><img src=reference-dify.png></article><article><h2>HYD · 실제 1440px</h2><img src=mcp-connections-1440.png></article></div></html>'''
    (H/'comparison.html').write_text(html,encoding='utf-8')
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':2400,'height':1200})
        page.goto((H/'comparison.html').as_uri());page.wait_for_function('Array.from(document.images).every(x=>x.complete && x.naturalWidth>0)')
        page.screenshot(path=str(H/'comparison.png'),full_page=True);browser.close()
    result['ok']=True
finally:
    (H/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ok':result.get('ok',False),'checks':result['checks'],'page_errors':result['page_errors'],'console_errors':result['console_errors'],'writes':result['writes']},ensure_ascii=False))
