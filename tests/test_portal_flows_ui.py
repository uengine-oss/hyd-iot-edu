"""Real Chromium DOM + FastAPI flows API + MemoryRepo; no live services."""
import json
import os
from pathlib import Path
import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright, expect
from test_bpmn_import import api, small

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'it/portal/www'

@pytest.fixture
def browser_page(api):
    client, rt, repo, audit = api
    for uid, name, agent in [('agent:cooling','냉각 긴급 대응 에이전트',True),('agent:pm-plan','정기 정비 계획 에이전트',True),('agent:spare-buy','예비품 구매 에이전트',True),('role:maint-lead','설비보전팀장',False),('role:buyer','구매 담당',False)]:
        repo.upsert_user({'id':uid,'username':name,'is_agent':agent,'agent_type':'agent' if agent else None,'tenant_id':'hyd'})
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror', lambda error: errors.append(str(error)))
        def route(r):
            from urllib.parse import urlparse
            path=urlparse(r.request.url).path
            if path.startswith('/api/'):
                response=client.request(r.request.method,path,content=r.request.post_data,headers={'content-type':'application/json'})
                r.fulfill(status=response.status_code,body=response.content,content_type='application/json')
            elif path=='/':
                r.fulfill(content_type='text/html',body='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/tokens.css"><link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/components.css"><link rel="stylesheet" href="/flows.css"><style>body{display:block;height:auto;overflow:auto;padding:32px}main{display:block;max-width:1100px;margin:auto;overflow:visible;height:auto}</style><main id="flows"></main><script>const API={process:''};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));</script><script src="/ui.js"></script><script src="/flows.js"></script><script>hydFlows.mount(document.querySelector('main'))</script>''')
            else:
                f=WWW/path.lstrip('/')
                r.fulfill(body=f.read_bytes(),content_type='text/css' if f.suffix=='.css' else 'text/javascript')
        page.route('**/*',route)
        page.goto('http://flows.test/')
        yield page,client,repo
        assert not errors, errors
        browser.close()

def import_file(page, name):
    page.locator('#flowFile').set_input_files(ROOT/'students/flows'/f'{name}.bpmn')
    page.locator('#flowId').fill('ui_'+name)
    page.locator('#flowImport').click()
    expect(page.locator('#flowName')).to_be_visible()

def change(page, selector, value):
    if isinstance(value,(list,dict)): value=json.dumps(value,ensure_ascii=False)
    el=page.locator(selector)
    if el.evaluate('(e)=>e.tagName')=='SELECT': el.select_option(str(value))
    else:
        el.fill(str(value))
        el.dispatch_event('change')

def check(page):
    with page.expect_response(lambda r: '/mapping' in r.url and r.request.method=='PUT'):
        page.locator('#flowCheck').click()
    expect(page.locator('#flowMsg')).to_have_text('매핑을 저장했습니다')

@pytest.mark.parametrize('name',['cooling-emergency','pm-planning','spare-purchase'])
def test_reference_flow_can_be_authored_and_registered_in_browser(browser_page,name):
    page,client,repo=browser_page
    mapping=json.loads((ROOT/'students/flows'/f'{name}.mapping.json').read_text(encoding='utf8'))
    import_file(page,name)
    assert page.locator('[data-pattern]:checked').count()==0
    check(page)
    expect(page.locator('#flowProblems')).to_contain_text('하나 이상')
    for pattern in mapping['start']['patterns']: page.locator(f'[data-pattern="{pattern}"]').check()
    for tid,t in mapping['tasks'].items():
        change(page,f'[data-part="{tid}"]',t['part'])
        for key in ('role','agent','instruction'):
            if key in t: change(page,f'[data-{key}="{tid}"]',t[key])
        for key,value in t.get('config',{}).items():
            if key=='mail':
                for mk,mv in value.items(): change(page,f'[data-mail="{tid}"][data-mail-key="{mk}"]',mv)
            else: change(page,f'[data-service="{tid}"][data-cfg="{key}"]',str(value).lower() if isinstance(value,bool) else value)
    check(page)
    for fid,c in mapping['flows'].items():
        if c.get('default'): page.locator(f'[data-default="{fid}"]').check()
        else:
            change(page,f'[data-var="{fid}"]',c['var'])
            change(page,f'[data-op="{fid}"]',c['op'])
            change(page,f'[data-value="{fid}"]','예' if c['value'] is True else c['value'])
    for tid in mapping['timers']: change(page,f'[data-timer="{tid}"]','10')
    check(page)
    # 2026-10-23 갱신: 통과 문구가 '사전 검사 통과'→'구조 검사 통과 — …'로 바뀜(flows.js resultBlock, 구조만 보고 연결 성공은 보장 안 함을 밝힘)
    expect(page.locator('#flowProblems')).to_contain_text('구조 검사 통과')
    expect(page.locator('[data-agent="T_agent"] option:checked')).to_contain_text({'cooling-emergency':'냉각 긴급 대응','pm-planning':'정기 정비 계획','spare-purchase':'예비품 구매'}[name])
    page.locator('#flowRegister').click()
    expect(page.locator('#flowMsg')).to_contain_text('등록했습니다')
    stored=repo.get_proc_def('ui_'+name,version='1')['definition']['bpmnImport']['mapping']
    for tid,t in mapping['tasks'].items():
        assert stored['tasks'][tid]==t
    assert stored['flows']==mapping['flows']
    evidence=os.environ.get('FLOW_UI_EVIDENCE')
    if evidence:
        folder=Path(evidence);folder.mkdir(parents=True,exist_ok=True)
        for width in (1440,1024):
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#flowEditor').screenshot(path=str(folder/f'flow-{name}-{width}.png'))
    page.locator('[data-open]').click()
    # 2026-10-23 갱신: 통과 문구가 '사전 검사 통과'→'구조 검사 통과 — …'로 바뀜(flows.js resultBlock, 구조만 보고 연결 성공은 보장 안 함을 밝힘)
    expect(page.locator('#flowProblems')).to_contain_text('구조 검사 통과')
    # 같은 파일을 다시 가져와도 포털의 start_patterns=[]는 저장된 선택을 지우지 않는다.
    with page.expect_response(lambda r: r.url.endswith('/api/flows/import')):
        page.locator('#flowImport').click()
    expect(page.locator('#flowImportMsg')).to_contain_text('다시 가져옴')
    assert page.locator('[data-pattern]:checked').count()==len(mapping['start']['patterns'])
    for pattern in mapping['start']['patterns']:
        expect(page.locator(f'[data-pattern="{pattern}"]')).to_be_checked()
    # 2026-10-23 갱신: 통과 문구가 '사전 검사 통과'→'구조 검사 통과 — …'로 바뀜(flows.js resultBlock, 구조만 보고 연결 성공은 보장 안 함을 밝힘)
    expect(page.locator('#flowProblems')).to_contain_text('구조 검사 통과')


def test_service_types_failure_and_part_switch(browser_page):
    page,client,repo=browser_page
    xml=small('<bpmn:startEvent id="S"/><bpmn:serviceTask id="T" name="도구 호출"/><bpmn:endEvent id="E"/><bpmn:sequenceFlow id="F1" sourceRef="S" targetRef="T"/><bpmn:sequenceFlow id="F2" sourceRef="T" targetRef="E"/>')
    page.locator('#flowFile').set_input_files({'name':'tool.bpmn','mimeType':'text/xml','buffer':xml.encode()})
    page.locator('#flowImport').click()
    expect(page.locator('#flowName')).to_be_visible()
    change(page,'[data-part="T"]','svc:mcp-call')
    for key,value in {'server':'hyd-effects','tool':'read_status','arguments':'{"active": false, "nested": {"count": 2}}','effect':'false','output':'result'}.items():
        change(page,f'[data-service="T"][data-cfg="{key}"]',value)
    check(page)
    saved=client.get('/api/flows/Process_small').json()['mapping']['tasks']['T']['config']
    assert saved['effect'] is False and saved['arguments']['nested']=={'count':2}
    page.locator('[data-open]').click()
    expect(page.locator('[data-service="T"][data-cfg="effect"]')).to_have_value('false')
    assert json.loads(page.locator('[data-service="T"][data-cfg="arguments"]').input_value())==saved['arguments']
    change(page,'[data-service="T"][data-cfg="arguments"]','[]')
    page.locator('#flowRegister').click()
    expect(page.locator('#flowMsg')).to_contain_text('이름과 값')
    assert repo.get_proc_def('Process_small',version='1') is None
    change(page,'[data-service="T"][data-cfg="arguments"]','{}')
    change(page,'[data-part="T"]','svc:wait')
    change(page,'[data-service="T"][data-cfg="duration"]','PT10M')
    check(page)
    saved=client.get('/api/flows/Process_small').json()['mapping']['tasks']['T']
    assert saved=={'part':'svc:wait','config':{'duration':'PT10M'}}
    # 2026-10-23 갱신: 통과 문구가 '사전 검사 통과'→'구조 검사 통과 — …'로 바뀜(flows.js resultBlock, 구조만 보고 연결 성공은 보장 안 함을 밝힘)
    expect(page.locator('#flowProblems')).to_contain_text('구조 검사 통과')


def test_missing_human_role_is_reported_without_losing_form(browser_page):
    page,client,repo=browser_page
    xml=small('<bpmn:startEvent id="S"/><bpmn:userTask id="T" name="담당자 확인"/><bpmn:endEvent id="E"/><bpmn:sequenceFlow id="F1" sourceRef="S" targetRef="T"/><bpmn:sequenceFlow id="F2" sourceRef="T" targetRef="E"/>')
    page.locator('#flowFile').set_input_files({'name':'role.bpmn','mimeType':'text/xml','buffer':xml.encode()})
    page.locator('#flowImport').click()
    expect(page.locator('#flowName')).to_be_visible()
    change(page,'[data-part="T"]','human')
    change(page,'#flowName','담당자 역할 확인')
    check(page)
    expect(page.locator('#flowProblems')).to_contain_text('역할')
    page.locator('#flowRegister').click()
    expect(page.locator('#flowMsg')).to_contain_text('등록하지 않았습니다')
    expect(page.locator('#flowName')).to_have_value('담당자 역할 확인')
    change(page,'[data-role="T"]','운전원')
    check(page)
    # 2026-10-23 갱신: 통과 문구가 '사전 검사 통과'→'구조 검사 통과 — …'로 바뀜(flows.js resultBlock, 구조만 보고 연결 성공은 보장 안 함을 밝힘)
    expect(page.locator('#flowProblems')).to_contain_text('구조 검사 통과')
