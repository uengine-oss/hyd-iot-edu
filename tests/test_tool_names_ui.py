"""Saved display metadata must not change execution status or call live tools."""
import os
from pathlib import Path

from test_portal_remaining_ui import page, WWW

RAW='mcp__overnight-internal-123__describe_table'


def setup(page):
    page.evaluate("() => {window.EventSource=class {static CLOSED=2;readyState=1;close(){} addEventListener(){}}}")
    page.add_script_tag(path=str(WWW/'toolNames.js'))
    page.add_script_tag(path=str(WWW/'liveStream.js'))
    page.evaluate('hydStream.S.connected=true')


def push(page,kind='tool_usage_started',id='start',tool=RAW,**data):
    page.evaluate('e=>hydStream.push(e,true)',{'id':id,'event_type':kind,'timestamp':'2026-10-12T01:00:00Z','data':{'tool':tool,'tool_use_id':'call1',**data}})


def metadata(page):
    page.route('**/api/agent-authoring/options',lambda r:r.fulfill(json={'servers':[{'name':'overnight-internal-123','description':'학생 참석 응답표'}]}))
    page.route('**/api/mcp/selectable',lambda r:r.fulfill(json={'servers':[{'name':'overnight-internal-123','tools':[{'name':'describe_table','title':'표 구조 조회','description':'표의 칸과 자료형을 확인합니다.','tool_id':RAW}]}]}))


def test_ticker_uses_registered_names_keeps_raw_in_fold_and_standard_translation(page):
    metadata(page);setup(page);push(page)
    page.locator('#streamTicker summary b').filter(has_text='학생 참석 응답표 · 표 구조 조회').wait_for()
    assert 'overnight-internal' not in page.locator('#streamTicker summary').inner_text()
    assert RAW not in page.locator('#streamTicker').inner_text()
    page.locator('#streamTicker summary').click()
    assert RAW in page.locator('.ticker-detail').inner_text()
    assert '등록된 표시 이름' in page.locator('.ticker-detail').inner_text()
    folder=os.getenv('STUDENT_CASES_EVIDENCE')
    if folder:
        for width in (1440,1024):
            page.set_viewport_size({'width':width,'height':1000})
            page.screenshot(path=str(Path(folder)/f'tool-display-{width}.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    push(page,id='standard',tool='mcp__neo4j__read_neo4j_cypher')
    assert page.locator('#streamTicker summary b').inner_text()=='지식 그래프 조회'
    assert page.evaluate('UI.toolName("mcp__neo4j__read_neo4j_cypher")')=='지식 그래프 조회'


def test_catalog_failure_is_name_failure_not_execution_failure_and_raw_is_available(page):
    page.route('**/api/agent-authoring/options',lambda r:r.fulfill(status=503,json={'detail':'표시 목록 연결 실패'}))
    page.route('**/api/mcp/selectable',lambda r:r.fulfill(json={'servers':[]}))
    setup(page);push(page)
    page.wait_for_function("hydToolNames.resolve('"+RAW+"').reason.includes('실제 도구 실행 결과와는 별개')")
    assert page.locator('#streamTicker summary').inner_text()=='도구 실행 중'
    page.locator('#streamTicker summary').click()
    assert '표시 목록 연결 실패' in page.locator('.ticker-detail').inner_text()
    assert RAW in page.locator('.ticker-detail').inner_text()
    push(page,'tool_usage_finished','failed',is_error=True)
    assert page.locator('#streamTicker summary').inner_text()=='도구 호출 실패'


def test_unregistered_tool_is_not_invented_and_late_metadata_cannot_replace_new_event(page):
    held=[]
    page.route('**/api/agent-authoring/options',lambda r:held.append(r))
    page.route('**/api/mcp/selectable',lambda r:r.fulfill(json={'servers':[]}))
    setup(page)
    with page.expect_request('**/api/agent-authoring/options'): push(page)
    assert page.locator('#streamTicker summary').inner_text()=='도구 실행 중'
    push(page,'task_working','later',type='text',content='판단을 정리합니다')
    for route in held: route.fulfill(json={'servers':[]})
    page.evaluate('hydToolNames.load()')
    assert page.locator('#streamTicker summary b').inner_text()=='에이전트 판단'
    push(page,id='unknown')
    page.locator('#streamTicker summary').click()
    assert '한글 표시 이름이 없습니다' in page.locator('.ticker-detail').inner_text()
    assert page.locator('#streamTicker summary').inner_text()=='도구 실행 중'
