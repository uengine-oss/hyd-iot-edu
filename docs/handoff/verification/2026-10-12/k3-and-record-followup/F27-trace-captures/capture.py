"""Two native existing processing trace captures; GET only, no replay."""
import hashlib,json,traceback
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

OUT=Path(__file__).parent
T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
CASES={'B':'c3_pm.d99ee952-f943-42fd-ba53-745b569522f7','C':'c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f'}
proof={'method':'native GET-only latest actual agent step click, 1440px processing pane', 'checks':[], 'screenshots':[], 'blockedWrites':[], 'pageerrors':[], 'consoleErrors':[]}
def save(n,v): (OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def check(n,v):proof['checks'].append({'label':n,'passed':bool(v)})
def sources():return {p.relative_to(T).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (T/'it/portal/www').rglob('*') if p.suffix in {'.js','.html','.css'}}
def get(i):
    with urlopen('http://127.0.0.1:8080/api/instances/'+i,timeout=30) as r:return json.load(r)
def persisted(v):return {k:v.get(k) for k in ('instance','workitems','approvals','effects','reworks')}
before=sources();save('source-before.json',before)
cases={k:get(v) for k,v in CASES.items()};save('cases-before.json',cases)
try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block')
        def guard(route):
            if route.request.method in {'GET','HEAD','OPTIONS'}:route.continue_()
            else:proof['blockedWrites'].append({'method':route.request.method,'url':route.request.url});route.abort()
        context.route('**/*',guard)
        page=context.new_page();page.set_default_timeout(30000)
        page.on('pageerror',lambda e:proof['pageerrors'].append(str(e)))
        page.on('console',lambda m:proof['consoleErrors'].append(m.text) if m.type=='error' else None)
        page.goto('http://127.0.0.1:8088/',wait_until='domcontentloaded')
        page.locator('[data-tab=instances]').click()
        for key,case in CASES.items():
            page.evaluate('(id)=>hydInstancesSelect(id)',case)
            page.wait_for_function('(id)=>hydInstances.I.view?.instance?.proc_inst_id===id',arg=case)
            page.locator('[data-inst-tab=flow]').click()
            starts=[e for e in cases[key]['events'] if e['event_type']=='task_started' and any(w['id']==e.get('todo_id') and w.get('activity_id')=='T_agent' for w in cases[key]['workitems'])]
            latest=max(starts,key=lambda e:e.get('timestamp') or '')
            wid=latest['todo_id']
            step=page.locator('#instTrace .tr-step[data-key="'+wid+'"]')
            head=step.locator('[data-tr-head]');head.wait_for(state='visible')
            if head.get_attribute('aria-expanded')!='true':head.click()
            page.wait_for_function('(wid)=>document.querySelector("#instTrace .tr-step[data-key="+CSS.escape(wid)+"]")?.classList.contains("open")',arg=wid)
            expected='추천 가능한 대안 없음' if key=='B' else '구매 판단 등록됨'
            target=step.locator('.tr-row.tr-k-tool').filter(has_text=expected).first
            target.wait_for(state='visible')
            check(key+' latest agent step expanded by native click',head.get_attribute('aria-expanded')=='true')
            text=target.inner_text()
            check(key+' original semantic summary present',expected in text)
            check(key+' approval/execution boundary explicit','승인 · 실행 아님' in text if key=='B' else '사람 승인 · ERP 실행 완료 아님' in text)
            check(key+' no missing/object replacement','[object Object]' not in text and '결과 기록을 확인할 수 없습니다' not in text)
            target.scroll_into_view_if_needed()
            target.evaluate('el=>{for(let p=el.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll/.test(s.overflowY)&&p.scrollHeight>p.clientHeight)p.scrollTop+=el.getBoundingClientRect().top-Math.max(p.getBoundingClientRect().top,110)-15;}window.scrollBy(0,el.getBoundingClientRect().top-125);}')
            page.wait_for_timeout(200)
            filename=key+'-latest-native-flow-trace-1440.png'
            page.screenshot(path=str(OUT/filename))
            proof['screenshots'].append({'file':filename,'sha256':hashlib.sha256((OUT/filename).read_bytes()).hexdigest(),'case':case,'todo_id':wid,'job_id':latest.get('job_id'),'visible_target_text':text})
            (OUT/(key+'-latest-native-flow-trace-1440.txt')).write_text(step.inner_text(),encoding='utf-8')
        browser.close()
except Exception:proof['exception']=traceback.format_exc()
finally:
    after=sources();save('source-after.json',after);check('source unchanged',before==after)
    cases_after={k:get(v) for k,v in CASES.items()};save('cases-after.json',cases_after)
    for k in cases:check(k+' persisted business state unchanged',persisted(cases[k])==persisted(cases_after[k]))
    check('no pageerrors',not proof['pageerrors']);check('no console errors',not proof['consoleErrors']);check('no writes attempted',not proof['blockedWrites'])
    proof['driver_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    proof['passed']=not proof.get('exception') and all(c['passed'] for c in proof['checks'])
    save('result.json',proof)
    print(json.dumps({'passed':proof['passed'],'checks':len(proof['checks']),'exception':proof.get('exception'),'screenshots':proof['screenshots']},ensure_ascii=False))
raise SystemExit(0 if proof['passed'] else 1)
