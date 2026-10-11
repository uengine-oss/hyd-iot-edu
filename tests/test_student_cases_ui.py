"""K1 Chromium with production shell/component and real FastAPI/MemoryRepo."""
import json
import os
from pathlib import Path

from test_portal_remaining_ui import page, route_client, WWW
from test_b6_config_bundle import env, http, build_student, ok
from test_student_cases import tag


def test_browser_case_edit_filter_export_and_remove(page,env,http,tmp_path):
    ids=build_student(env,http)
    ok(tag(env,'flows','my_cooler','정비 사례'))
    ok(tag(env,'agents',ids['a2'],'다른 사례'))
    route_client(page,env)
    page.add_script_tag(path=str(WWW/'studentCases.js'))
    page.evaluate("selectTab('admin');document.querySelector('#configBundlePanel').open=true;hydStudentCases.mount(document.querySelector('#configBundleView'))")
    page.locator('#caseAssets [data-case-row]').first.wait_for()
    card=page.locator('[data-case-row]').filter(has_text='내 쿨러 흐름')
    assert card.count()==1
    assert 'agent:u-' not in page.locator('#caseAssets').inner_text()
    card.locator('input').fill('회의 자료 준비')
    page.route('**/api/config/cases/tag',lambda r:r.fulfill(status=500,json={'detail':'저장 연결 실패'}))
    card.locator('button').click()
    card.locator('.form-msg').filter(has_text='저장 연결 실패').wait_for()
    assert card.locator('input').input_value()=='회의 자료 준비'
    page.unroute('**/api/config/cases/tag')
    card.locator('button').click()
    page.locator('#caseMessage').filter(has_text='저장했습니다').wait_for()
    # Reload the component: metadata comes back from the server, not browser memory.
    page.evaluate("hydStudentCases.mount(document.querySelector('#configBundleView'))")
    page.locator('#caseFilter option').filter(has_text='회의 자료 준비').wait_for(state='attached')
    page.locator('#caseFilter').select_option('회의 자료 준비')
    assert page.locator('[data-case-row]').count()==1
    assert '다른 사례' not in page.locator('#caseAssets').inner_text()
    with page.expect_download() as received:
        page.locator('#caseExport').click()
    downloaded=tmp_path/'case.json';received.value.save_as(downloaded)
    bundle=json.loads(downloaded.read_text(encoding='utf8'))
    assert bundle['case_selection']['label']=='회의 자료 준비'
    assert bundle['case_tags']==[{'kind':'flows','asset_id':'my_cooler','label':'회의 자료 준비'}]
    assert {r['id'] for r in bundle['content']['agents']}=={ids['a1']}
    assert bundle['content']['flows'][0]['versions'][0]['bpmn'].startswith('<?xml')
    page.locator('#caseMessage').filter(has_text='연결 구성 4개').wait_for()
    folder=os.getenv('STUDENT_CASES_EVIDENCE')
    if folder:
        Path(folder).mkdir(parents=True,exist_ok=True)
        for width in (1440,1024):
            page.set_viewport_size({'width':width,'height':1000})
            page.screenshot(path=str(Path(folder)/f'student-case-{width}.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('[data-case-row] input').fill('')
    page.locator('[data-case-save]').click()
    page.locator('#caseMessage').filter(has_text='뗐습니다').wait_for()
    assert '회의 자료 준비' not in env.get('/api/config/cases').json()['labels']
    assert env.repo.get_proc_def('my_cooler','hyd',version='2')


def test_failed_catalog_and_export_are_visible_errors(page,env):
    route_client(page,env)
    page.route('**/api/config/cases',lambda r:r.fulfill(status=503,json={'detail':'구성 저장소 연결 실패'}))
    page.add_script_tag(path=str(WWW/'studentCases.js'))
    page.evaluate("selectTab('admin');document.querySelector('#configBundlePanel').open=true;hydStudentCases.mount(document.querySelector('#configBundleView'))")
    page.locator('#caseMessage').filter(has_text='구성 저장소 연결 실패').wait_for()
    assert page.locator('#caseExport').is_disabled()
    assert '아직 묶을 구성이 없습니다' not in page.locator('#caseAssets').inner_text()
