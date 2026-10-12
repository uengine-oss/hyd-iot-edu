"""Only the C task output changed after the preserved first native capture."""
import hashlib
import json
import sys
import traceback
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright

TREE = Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
HERE = Path(__file__).parent
OUT = HERE / sys.argv[1]
CASE = 'c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f'
PORTAL = 'http://127.0.0.1:8088/'
API = 'http://127.0.0.1:8080'
OUT.mkdir(exist_ok=False)
result = {'passed': False, 'checks': [], 'screenshots': [], 'pageerrors': [], 'blockedWrites': [],
          'method': 'native C historical task output only; first B/C capture preserved', 'llm_reruns': 0, 'whole_reruns': 0}
def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
def check(label, ok, detail=None):
    result['checks'].append(dict(label=label, passed=bool(ok), detail=detail))
def get(path):
    with urlopen(API+path, timeout=30) as r:
        return json.load(r)
def source():
    return {p.relative_to(TREE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (TREE/'it/portal/www').rglob('*') if p.suffix in {'.js','.html','.css'}}
def projection(v):
    return {k:v.get(k) for k in ('instance','workitems','approvals','effects','reworks')}

frozen=source()
save('source-before.json',frozen)
before=get('/api/instances/'+CASE)
save('case-before.json',before)
try:
    previous=json.loads((HERE/'live-record-final-1/source-before.json').read_text(encoding='utf-8'))
    for name,digest in frozen.items():
        if previous.get(name)==digest: continue
        with urlopen(PORTAL+name.removeprefix('it/portal/www/')+'?sha='+digest,timeout=30) as r:
            mounted=hashlib.sha256(r.read()).hexdigest()
        check('changed mounted source matches '+name,digest==mounted,{'expected':digest,'actual':mounted})
    starts=[e for e in before.get('events',[]) if e.get('event_type')=='task_started' and any(w['id']==e.get('todo_id') and w.get('activity_id')=='T_agent' for w in before['workitems'])]
    latest=max(starts,key=lambda e:e.get('timestamp') or '')
    wid=latest['todo_id']
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        ctx=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block')
        def guard(route):
            if route.request.method in {'GET','HEAD','OPTIONS'}: route.continue_()
            else:
                result['blockedWrites'].append({'method':route.request.method,'url':route.request.url})
                route.abort()
        ctx.route('**/*',guard)
        page=ctx.new_page()
        page.set_default_timeout(20000)
        page.on('pageerror',lambda e:result['pageerrors'].append(str(e)))
        page.goto(PORTAL,wait_until='domcontentloaded')
        page.locator('[data-tab="instances"]').click()
        page.evaluate('(id)=>window.hydInstancesSelect(id)',CASE)
        page.wait_for_function('(id)=>window.hydInstances.I.view?.instance?.proc_inst_id===id',arg=CASE)
        page.locator('[data-inst-tab="record"]').click()
        page.wait_for_function('()=>hydInstances.I.record?.ext?.decision?.id && !hydInstances.I.record.fetching')
        page.locator('#instRecord [data-cr-all]').wait_for()
        if page.locator('#instRecord [data-cr-all]').inner_text()=='모두 펼치기':
            page.locator('#instRecord [data-cr-all]').click()
        record=page.locator('#instRecord')
        model=page.evaluate("()=>{const s=hydInstances.I.record.model.steps;return {agent:s.find(x=>x.type==='agent')?.sentence,approval:s.find(x=>x.type==='approve')?.sentence}}")
        check('C historical agent recommendation retains three original candidates',model['agent'] and '대안 3개' in model['agent'] and '대체 승인 공급사 발주' in model['agent'],model)
        check('C current approval retains selected OEM',model['approval'] and '순정(OEM)' in model['approval'],model)
        for width in (1440,1024):
            page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(200)
            check('C record renders '+str(width),record.locator('.cr-error').count()==0)
            text=record.inner_text();(OUT/('C-record-'+str(width)+'.txt')).write_text(text,encoding='utf-8')
            target=record.locator('[data-cr-steps] > li').nth(1)
            target.scroll_into_view_if_needed()
            target.evaluate('el=>{for(let p=el.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll/.test(s.overflowY)&&p.scrollHeight>p.clientHeight){p.scrollTop+=el.getBoundingClientRect().top-Math.max(p.getBoundingClientRect().top,110)-15;}}window.scrollBy(0,el.getBoundingClientRect().top-125);}')
            page.wait_for_timeout(200)
            filename='C-historical-agent-'+str(width)+'.png';page.screenshot(path=str(OUT/filename))
            result['screenshots'].append({'file':filename,'sha256':hashlib.sha256((OUT/filename).read_bytes()).hexdigest()})
        page.goto(PORTAL+'#/instances/'+quote(CASE,safe='')+'/task/'+quote(wid,safe=''),wait_until='domcontentloaded')
        page.wait_for_function('id=>window.hydTaskDetail?.T.wid===id && !window.hydTaskDetail.T.loading && window.hydTaskDetail.T.item?.id===id',arg=wid)
        panel=page.locator('#taskDetailPanel [data-task-detail]');panel.wait_for()
        output=panel.locator('[data-k="output"]')
        if output.get_attribute('open') is None: output.locator('summary').click()
        for width in (1440,1024):
            page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(250)
            text=output.inner_text()
            (OUT/('C-task-output-'+str(width)+'.txt')).write_text(text,encoding='utf-8')
            check('actual part named '+str(width),'펌프' in text and '씰' in text)
            check('original three named candidate procedures '+str(width), all(x in text for x in ('대체 승인 공급사 발주','순정(OEM) 공급사 표준 발주','최단 납기 긴급 발주')))
            check('no object coercion/internal skill ID '+str(width),'[object Object]' not in text and 'skill:sop-' not in text)
            check('historical recommendation retained '+str(width),'A정밀' in text and '210' in text)
            check('purchase not reported as fault diagnosis '+str(width),'고장 원인 판정 없음' in text)
            output.scroll_into_view_if_needed()
            output.evaluate('el=>{for(let p=el.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll/.test(s.overflowY)&&p.scrollHeight>p.clientHeight){p.scrollTop+=el.getBoundingClientRect().top-Math.max(p.getBoundingClientRect().top,110)-15;}}window.scrollBy(0,el.getBoundingClientRect().top-125);}')
            page.wait_for_timeout(200)
            filename='C-task-output-'+str(width)+'.png'
            page.screenshot(path=str(OUT/filename))
            result['screenshots'].append({'file':filename,'sha256':hashlib.sha256((OUT/filename).read_bytes()).hexdigest()})
        result['decision_identity']={'task':wid,'job':latest.get('job_id'),'fetched':page.evaluate('()=>hydTaskDetail.T.dec?.id || null')}
        browser.close()
except Exception:
    result['exception']=traceback.format_exc()
finally:
    after=get('/api/instances/'+CASE);save('case-after.json',after)
    check('C case/tasks/approvals/effects unchanged',projection(before)==projection(after))
    aftersource=source();save('source-after.json',aftersource)
    check('source frozen throughout capture',frozen==aftersource)
    check('no page errors',not result['pageerrors'],result['pageerrors'])
    check('no attempted writes',not result['blockedWrites'],result['blockedWrites'])
    result['passed']=not result.get('exception') and all(c['passed'] for c in result['checks'])
    result['driver_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save('result.json',result)
    print(json.dumps({'passed':result['passed'],'checks':len(result['checks']),'failures':[c for c in result['checks'] if not c['passed']],'exception':result.get('exception'),'out':str(OUT)},ensure_ascii=False))
sys.exit(0 if result['passed'] else 1)
