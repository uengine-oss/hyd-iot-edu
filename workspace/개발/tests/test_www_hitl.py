"""문서 등록 화면(it/portal/www/hitl.js): 업무 DB 표 정의 연결 이력의 되돌리기 결과 문장, 조치 방법 지우기, 이미 적재한 원문의 [이 문서 개정],
올리기 단계의 두 길(제공 문서에서 고르기 · 내 파일 올리기).

실제 index.html · hitl.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(연결 이력 · 되돌리기)만 이 시험이 준다
(꼴은 procsvc GET /api/kg/ingests · DELETE /api/kg/ingests/{batch})."""
import base64

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


def test_적재한_파일을_새_문서로_다시_올리면_적재_사실과_이_문서_개정이_나오고_누르면_그_문서의_개정으로_다시_올린다():
    """2026-11-14: 이미 적재한 매뉴얼을 「새 문서 등록」으로 다시 올리면 화면이 「아직 AI가 문서를 읽기 전입니다」라고 했고, 그대로 검토 · 적재하면
    「다른 원천/기존 지식이 소유합니다」로 끝났다. 서버는 같은 원본으로 적재한 문서(same_original)를 올린 응답에 싣는다(procsvc manual_api.preview) —
    화면은 그 사실을 말하고 주 단추를 [이 문서 개정]으로 두며, 누르면 방금 고른 파일을 그 문서의 개정(document_id)으로 다시 올린다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    name, loaded_doc = 'HI-01_shift-inspection-supplement.md', 'doc-loaded'
    fact = {'batch': 'b1', 'at': '2026-11-14T02:00:00+00:00', 'by': '담당자', 'source_id': f'manual:{loaded_doc}:abc', 'filename': name, 'sections': 5,
            'procedures': 3, 'steps': 12, 'provided': False, 'extraction': None}
    base = {'filename': name, 'batch': 'b2', 'previous_batch': None, 'status': 'READY', 'chars': 1800, 'pages': 1, 'warnings': []}
    posted = []

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/api/kg/manuals/preview') and method == 'POST':
            body = route.request.post_data_json
            posted.append(body.get('document_id'))
            if body.get('document_id') == loaded_doc:            # 그 문서의 개정으로 올림: 적재된 판이 이 원문에서 나왔다
                return route.fulfill(json={**base, 'source_id': f'manual:{loaded_doc}:abc', 'document_id': loaded_doc, 'previous_batch': 'b1',
                                           'loaded': {**fact, 'same_source': True}, 'same_original': None})
            return route.fulfill(json={**base, 'source_id': 'manual:doc-new:abc', 'document_id': 'doc-new', 'loaded': None,
                                       'same_original': {**fact, 'document_id': loaded_doc}})
        if path.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'total': 0, 'next_offset': None})
        if path.endswith('/api/kg/manuals') or path.endswith('/api/kg/skills') or path.endswith('/api/kg/ingests'):
            return route.fulfill(json=[])
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'knowledge')
            page.click("#manualPick [data-pick-mode='file']")      # 올리기 단계의 「내 파일 올리기」
            page.set_input_files('#manualFile', {'name': name, 'mimeType': 'text/markdown', 'buffer': '# 보충 매뉴얼\n'.encode()})
            page.click('#manualPreview')
            page.wait_for_selector('#manualResult .mprev', timeout=15000)
            said = page.inner_text('#manualResult .result')
            assert '이미 적재한 원문' in said and f'「{name}」로 이미 적재돼 있습니다' in said and '절차 3개' in said and '담당자' in said
            assert '아직 AI가 문서를 읽기 전' not in said
            # 주 단추는 [이 문서 개정] 하나이고 AI 추출 시작은 보조 단추다(그대로 적재하면 거절된다는 것을 위에서 말했다)
            assert page.locator('#manualReviseSame').get_attribute('data-variant') is None
            assert page.locator('#manualAgentExtract').get_attribute('data-variant') == 'outline'
            page.click('#manualReviseSame')
            page.wait_for_function("document.querySelector('#manualResult .result-label')?.textContent === '이미 적재된 문서'", timeout=15000)
            assert posted == [None, loaded_doc]                   # 처음은 새 문서로, [이 문서 개정]은 그 문서의 개정으로
            again = page.inner_text('#manualResult .result')
            assert '이 원문으로 만든 판이 지식 지도에 적재돼 있습니다' in again and page.locator('#manualReviseSame').count() == 0
            assert page.locator('#manualAgentExtract').get_attribute('data-variant') is None      # 이제 주 단추는 AI 추출 시작
            b.close()
    finally:
        served.close()


def _upload(doc, name, batch):
    return {'batch': batch, 'document_id': doc, 'source_id': f'manual:{doc}:abc', 'filename': name, 'current': True, 'status': 'ACTIVE', 'by': '담당자',
            't': '2026-11-14T02:00:00+00:00', 'sections': 8, 'procedures': 7, 'steps': 25}


def test_제공_문서를_목록에서_고르면_내려받지_않고_그_원문_그대로_올리고_적재된_문서는_그_문서의_개정으로_올린다():
    """2026-11-15 사용자: 「매뉴얼 자체를 다운받아서 한다는 것부터가 이상함」. 올리기 단계의 「제공 문서에서 고르기」는 서버가 준 제공 문서 목록
    (GET /api/course-access provided_documents)을 문서 제목과 함께 보이고, 줄을 누르면 화면이 같은 출처의 samples/<파일>을 읽어 「내 파일 올리기」와 같은
    요청(POST /api/kg/manuals/preview)을 보낸다. 서버는 문서를 내용(sha256)으로 알아보므로 보낸 바이트가 그 파일과 한 바이트도 다르면 안 된다.
    이미 적재된 제공 문서는 목록에서 「적재됨」으로 보이고, 고르면 그 문서의 개정(document_id)으로 올라간다. 등록된 문서의 [이 문서 개정]은
    새 판본 파일을 올리는 길이라 「내 파일 올리기」가 열린다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    new, loaded = 'HI-01_shift-inspection-supplement.md', 'HM-8_cooler-fan-manual.md'
    posted = []

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/api/course-access'):
            return route.fulfill(json={'phase': 'course', 'actions': {}, 'documents': 'provided', 'provided_documents': [loaded, new],
                                       'reasons': {k: '지금 단계에서는 하지 않습니다.' for k in ('assign', 'start', 'import_flow', 'document')}})
        if path.endswith('/api/kg/manuals/preview') and method == 'POST':
            body = route.request.post_data_json
            posted.append(body)
            doc = body.get('document_id') or 'doc-new'
            return route.fulfill(json={'filename': body['filename'], 'batch': 'b9', 'previous_batch': None, 'status': 'READY', 'chars': 1800, 'pages': 1, 'warnings': [],
                                       'source_id': f'manual:{doc}:abc', 'document_id': doc, 'loaded': None, 'same_original': None})
        if path.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'total': 0, 'next_offset': None})
        if path.endswith('/api/kg/manuals'):
            return route.fulfill(json=[_upload('doc-hm8', loaded, 'b1')])
        if path.endswith('/api/kg/skills') or path.endswith('/api/kg/ingests'):
            return route.fulfill(json=[])
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'knowledge')
            row = lambda f: page.locator(f"#providedDocs [data-provided='{f}']")
            page.wait_for_function("document.querySelectorAll('#providedDocs .row-meta').length === 2 && [...document.querySelectorAll('#providedDocs .row-meta')].every(n => n.textContent)", timeout=15000)
            # 처음 보이는 길은 「제공 문서에서 고르기」이고 파일 고르기 칸은 숨어 있다. 줄의 제목은 그 파일 머리의 제목 줄이다
            assert row(new).is_visible() and not page.locator('#manualPreview').is_visible()
            for f in (new, loaded):
                head = (WWW / 'samples' / f).read_text(encoding='utf-8').splitlines()[0].lstrip('# ').strip()
                assert row(f).locator('.row-title').inner_text() == head and f in row(f).locator('.row-meta').inner_text()
            assert '적재됨' in row(loaded).inner_text() and '적재됨' not in row(new).inner_text()
            # [원문 보기]는 내려받기가 아니라 새 탭에서 글로 열린다
            link = page.locator(f"#providedDocs [data-provided-view='{new}']")
            assert link.get_attribute('target') == '_blank' and link.get_attribute('download') is None
            kind = page.evaluate("async href => (await fetch(href)).headers.get('content-type')", link.get_attribute('href'))
            assert kind.startswith('text/plain')
            for f, doc in ((new, None), (loaded, 'doc-hm8')):
                row(f).click()
                page.wait_for_selector('#manualResult .mprev', timeout=15000)
                body = posted[-1]
                assert body['filename'] == f and body['document_id'] == doc
                assert base64.b64decode(body['data']) == (WWW / 'samples' / f).read_bytes()      # 서버가 내용으로 알아본다 — 원문 그대로
                page.click('#manualAnother')
                page.wait_for_selector('#manualPick', state='visible')
            assert len(posted) == 2 and row(new).is_enabled()
            # 등록된 문서의 [이 문서 개정] → 「내 파일 올리기」가 열리고 「등록할 문서」가 그 문서다. 고른 파일은 그 문서의 개정으로 올라간다
            page.click("#manualHistory [data-manual-revise='doc-hm8']")
            assert page.locator('#manualPreview').is_visible() and not row(new).is_visible()
            assert page.locator('#manualDocumentId').input_value() == 'doc-hm8'
            page.set_input_files('#manualFile', {'name': loaded, 'mimeType': 'text/markdown', 'buffer': '# 새 판본\n'.encode()})
            page.click('#manualPreview')
            page.wait_for_selector('#manualResult .mprev', timeout=15000)
            assert posted[-1]['document_id'] == 'doc-hm8' and base64.b64decode(posted[-1]['data']) == '# 새 판본\n'.encode()
            b.close()
    finally:
        served.close()


def test_업무_DB_표_정의의_제공_예시를_고르면_그_파일_글_그대로_읽기_요청을_보내고_표와_열_고르기로_간다():
    """「업무 DB 표 정의」 보기도 같은 원칙이다: 제공 예시 줄을 누르면 화면이 samples/legacy-plant-db.sql 을 읽어 「내 파일 올리기」와 같은 요청
    (POST /api/kg/ddl/preview { filename, text, catalog })을 보내고 2단계(표와 열 고르기)로 간다. 연결 이력에 그 파일의 연결이 남아 있으면 줄에 「적재됨」이 붙는다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    name = 'legacy-plant-db.sql'
    posted, ingests = [], []

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/api/kg/ddl/preview') and method == 'POST':
            body = route.request.post_data_json
            posted.append(body)
            ingests.append({'batch': 'ddl-1', 'label': 'InputData', 'nodes': 3, 'source': name})      # 시험 편의: 읽은 뒤 이력에 그 파일의 연결이 있다고 답한다
            return route.fulfill(json={'filename': body['filename'], 'chars': len(body['text']), 'catalog': body['catalog'], 'datasource': 'ds', 'warnings': [], 'systems': [],
                                       'existingSystems': [], 'sourceOptions': [{'id': 'ds', 'label': '업무 DB', 'schema': 'public'}], 'inputs': [],
                                       'tables': [{'table': 'T_EQP00', 'comment': '', 'system': '', 'columns': ['EQP_CD'], 'selected': []}]})
        if path.endswith('/api/kg/ingests'):
            return route.fulfill(json=list(ingests))
        if path.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'total': 0, 'next_offset': None})
        if path.endswith('/api/kg/manuals') or path.endswith('/api/kg/skills'):
            return route.fulfill(json=[])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'knowledge')
            page.click("#docKinds [data-doc-kind='ddl']")
            row = page.locator(f"#providedDdl [data-provided='{name}']")
            assert row.is_visible() and not page.locator('#ddlPreview').is_visible() and '적재됨' not in row.inner_text()
            row.click()
            page.wait_for_selector('#ddlResult .mprev', timeout=15000)
            assert len(posted) == 1 and posted[0]['filename'] == name and posted[0]['catalog'] == 'postgres'
            assert posted[0]['text'] == (WWW / 'samples' / name).read_text(encoding='utf-8')
            assert '표 1개를 읽었습니다' in page.inner_text('#ddlResult .result') and page.locator('#ddlPick').is_hidden()
            page.click('#ddlAnother')
            page.wait_for_selector('#ddlPick', state='visible')
            assert '적재됨' in row.inner_text() and row.is_enabled()
            # 「내 파일 올리기」는 파일 고르기 그대로다
            page.click("#ddlPick [data-pick-mode='file']")
            assert page.locator('#ddlPreview').is_visible() and not row.is_visible()
            page.set_input_files('#ddlFile', {'name': 'mine.sql', 'mimeType': 'text/plain', 'buffer': 'CREATE TABLE a (b int);'.encode()})
            page.click('#ddlPreview')
            page.wait_for_function("document.querySelector('#ddlResult .result-main')?.textContent.includes('mine.sql')", timeout=15000)
            assert posted[-1]['filename'] == 'mine.sql' and posted[-1]['text'] == 'CREATE TABLE a (b int);'
            b.close()
    finally:
        served.close()
