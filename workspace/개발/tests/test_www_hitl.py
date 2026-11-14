"""문서 등록 화면(it/portal/www/hitl.js)의 업무 DB 표 정의 연결 이력 — 되돌리기 결과 문장이 학생에게 남는다.

실제 index.html · hitl.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(연결 이력 · 되돌리기)만 이 시험이 준다
(꼴은 procsvc GET /api/kg/ingests · DELETE /api/kg/ingests/{batch})."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

BATCH = 'ddl-legacy-plant-db-1'


def test_연결_배치를_되돌리면_이력을_다시_그린_뒤에도_되돌리기_완료_문장이_남는다():
    """한바퀴3 고침 4: 되돌리기 성공 문장을 쓴 직후 이력을 다시 그리며(loadIngests 가 알림 줄까지 새로 만듦) 문장이 지워져, 학생은 결과를
    볼 수 없었다(06 실습 · 통합 40행)."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    rows = [{'batch': BATCH, 'label': 'InputData', 'nodes': 20, 'source': 'legacy-plant-db.sql'}]

    def answer(route):
        url, method = route.request.url.split('?')[0], route.request.method
        if url.endswith('/api/kg/ingests/' + BATCH) and method == 'DELETE':
            rows.clear()
            return route.fulfill(json={'deleted': 20, 'restored': 0, 'retained': 1})
        if url.endswith('/api/kg/ingests'):
            return route.fulfill(json=list(rows))
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'knowledge')
            page.click("#docKinds [data-doc-kind='ddl']")      # 올릴 것: 업무 DB 표 정의(연결 이력은 그쪽 판 아래에 있다)
            page.wait_for_selector(f"#ddlHistory [data-clear='{BATCH}']", timeout=15000)
            page.locator(f"#ddlHistory [data-clear='{BATCH}']").click()
            page.locator("dialog.confirm-dialog button[value='ok']").click()      # 포털 확인 대화상자(UI.confirm)
            page.wait_for_function("document.querySelectorAll('#ddlHistory [data-clear]').length === 0", timeout=15000)
            page.wait_for_timeout(300)
            assert page.inner_text('#ddlHistoryMsg') == '되돌렸습니다. 지운 항목 20개 · 되살린 항목 0개 · 남긴 항목 1개'
            b.close()
    finally:
        served.close()


def _skill(sid, name, source=None):
    return {'id': sid, 'sopId': sid.split(':')[1].upper(), 'name': name, 'description': '', 'kind': 'work_order', 'source_document': source, 'source_id': source,
            'approver': {'id': 'role:operator', 'name': '운전원', 'level': 1}, 'failureModes': [{'id': 'fm:x', 'name': '벨트 느슨함', 'relation': 'REMEDIED_BY'}],
            'causes': [], 'actions': [], 'steps': [{'text': '벨트를 교체한다.', 'order': 1, 'manual': None}], 'rules': [], 'affects': [], 'performers': [], 'revision': 'r1'}


def test_화면에서_만든_조치_방법만_지우기_단추가_있고_거절은_서버의_까닭을_지우면_남는_판단_기록_수를_말한다():
    """조치 방법 지우기(DELETE /api/kg/skills/{id}?by=). 문서에서 온 조치 방법에는 단추가 없다(그 문서를 되돌리면 지워진다). 문서의 규칙이 가리키는
    조치 방법은 서버가 409 와 까닭을 주고 화면은 그 문장을 그대로 보인다. 지워지면 그 조치 방법을 고른 판단 기록이 몇 건 남는지 말한다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    skills = [_skill('skill:sop-doc-1', '문서에서 온 조치', 'doc:1'), _skill('skill:sop-mine-1', '내가 만든 조치'), _skill('skill:sop-mine-2', '규칙이 가리키는 조치')]
    why = '문서의 규칙 1개(rule:x)가 이 조치 방법을 가리킵니다 — 그 문서를 「지식 › 문서 등록」의 등록 이력에서 먼저 되돌린 뒤 지우세요'
    deletes = []

    def answer(route):
        url, method = route.request.url, route.request.method
        path = url.split('?')[0]
        if method == 'DELETE' and '/api/kg/skills/' in path:
            sid = path.rsplit('/', 1)[1].replace('%3A', ':')
            deletes.append((sid, 'by=' in url and 'request_id=' in url))
            if sid == 'skill:sop-mine-2':
                return route.fulfill(status=409, json={'detail': why})
            skills[:] = [k for k in skills if k['id'] != sid]
            return route.fulfill(json={'id': sid, 'sopId': 'SOP-MINE-1', 'name': '내가 만든 조치', 'deleted': True, 'decision_cases': 3, 'removed_rules': ['rule:cand-x']})
        if path.endswith('/api/kg/skills'):
            return route.fulfill(json=list(skills))
        if path.endswith('/api/kg/catalog'):
            return route.fulfill(json={'roles': [{'id': 'role:operator', 'name': '운전원'}], 'failureModes': [{'id': 'fm:x', 'name': '벨트 느슨함'}]})
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'skills')
            page.wait_for_selector("#skillList [data-skill='skill:sop-doc-1']", timeout=15000)
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            assert page.locator('#skDelete').count() == 0 and page.locator('#skSource').count() == 1      # 문서에서 온 것: 지우기 없음, 출처 줄에 그 문서로 가는 링크
            page.click("#skillList [data-skill='skill:sop-mine-2']")
            page.locator('#skDelete').click()
            assert '「규칙이 가리키는 조치」' in page.inner_text('dialog.confirm-dialog')
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            page.wait_for_selector("#skAlert [role='alert'], #skAlert .alert", timeout=8000)
            assert why in page.inner_text('#skAlert') and page.locator("#skillList [data-skill='skill:sop-mine-2']").count() == 1      # 거절: 까닭 그대로, 목록에 남는다
            page.click("#skillList [data-skill='skill:sop-mine-1']")
            page.locator('#skDelete').click()
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            page.wait_for_function("!document.querySelector(\"#skillList [data-skill='skill:sop-mine-1']\")", timeout=8000)
            toast = page.locator('#toaster').inner_text()
            assert '「내가 만든 조치」 조치 방법을 지웠습니다' in toast and '판단 기록 3건은 남습니다' in toast and '후보 규칙 1개도 함께 지웠습니다' in toast
            assert deletes == [('skill:sop-mine-2', True), ('skill:sop-mine-1', True)]
            b.close()
    finally:
        served.close()
