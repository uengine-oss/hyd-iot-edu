"""문서 등록 · 조치 방법 화면(it/portal/www/hitl.js): 적재한 표 정의의 되돌리기 결과 문장, 조치 방법의 상세와 지우기, 이미 적재한 원문의 [이 문서 개정],
올리기 단계의 두 길(제공 문서에서 고르기 · 내 파일 올리기)과 제공 문서 줄의 자리, 한 번에 적재, 적재한 문서 목록과 옆 판.

실제 index.html · hitl.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(적재한 표 정의 · 되돌리기)만 이 시험이 준다
(꼴은 procsvc GET /api/kg/ingests · DELETE /api/kg/ingests/{batch})."""
import base64

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

BATCH = 'ddl-legacy-plant-db-1'


def row_menu(page, row, item):
    """목록 줄의 더 보기 메뉴(ui.js moreMenu)를 학생처럼 연다: 줄에 마우스를 올려 「…」을 누르고 메뉴의 줄을 누른다. row = 그 줄(.row-act)을 가리키는 선택자."""
    act = page.locator(row)
    act.hover()
    act.locator('.dropdown-menu > button').click()
    act.locator(f'[role=menu] {item}').click(timeout=5000)      # 메뉴가 아래 줄에 가려 눌리지 않으면 여기서 멈춘다


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
            page.click("#docKinds [data-doc-kind='ddl']")      # 올릴 것: 업무 DB 표 정의(적재한 표 정의는 그쪽 판 아래에 있다)
            page.wait_for_selector(f"#ddlHistory [data-batch='{BATCH}']", timeout=15000)
            # 적재한 표 정의의 줄: 스키마 파일 이름과 넣은 항목. 연결 번호 같은 식별자는 첫 화면에 없고, 되돌리기는 줄의 더 보기 안에 있다
            line = page.inner_text(f"#ddlHistory [data-batch='{BATCH}']")
            assert 'legacy-plant-db.sql' in line and '입력 데이터 20' in line and BATCH not in page.inner_text('#ddlHistory')
            row_menu(page, f"#ddlHistory .row-act:has([data-batch='{BATCH}'])", f"[data-clear='{BATCH}']")
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
            # 문서에서 온 것: 지우기 없음, 더 보기 메뉴에 그 문서로 가는 길
            assert page.locator('#skDelete').count() == 0 and page.locator('#skillMore-menu #skSource').count() == 1
            # 상세의 첫 화면(디자인 기준 5-1): 머리(이름 + 종류 알약, 오른쪽 끝에 더 보기) → 절차 → 대상 고장 유형 · 승인 역할. 그 밖의 연결은 「연결된 지식」 접기 안, 식별자는 더 보기 메뉴 안
            head = page.evaluate("""() => { const r = s => { const b = document.querySelector(s).getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, b: b.bottom }; };
              return { title: r('#skillDetail .pane-title h2'), tag: r('#skillDetail .pane-title h2 .tag'), more: r('#skillMore-trigger'), pane: r('#skillDetail'), icons: document.querySelectorAll('#skillDetail .panel-head .pane-ic, #skillDetail .sk-ic').length }; }""")
            assert head['icons'] == 0 and head['title']['l'] < head['tag']['l'] and head['tag']['r'] < head['more']['l'] and abs(head['more']['r'] - head['pane']['r']) <= 1, head
            seen = page.evaluate("() => [...document.querySelectorAll('#skillDetail dt')].filter(n => n.offsetParent && !n.closest('details:not([open])')).map(n => n.textContent.trim())")
            assert seen == ['대상 고장 유형', '승인 역할'], seen
            assert page.inner_text('#skillDetail .sk-steps') == '벨트를 교체한다.' and 'skill:sop-doc-1' not in page.inner_text('#skillDetail')
            fold = page.locator('#skillDetail details.fold').first
            assert fold.locator('summary').inner_text().startswith('연결된 지식') and not fold.evaluate('d => d.open')
            fold.locator('summary').click()
            fold.locator('.fold-body dt', has_text='출처').wait_for(state='visible', timeout=5000)
            assert '출처' in fold.inner_text() and '그 문서를 개정해 고칩니다' in fold.inner_text()
            page.click('#skillMore-trigger')
            page.locator('#skillMore-menu [role=menuitem]').first.wait_for(state='visible', timeout=5000)
            assert page.locator('#skillMore-menu [role=menuitem]').all_inner_texts() == ['문서 등록에서 고치기', '조치 식별자 복사', '절차 번호 복사 (SOP-DOC-1)']
            page.keyboard.press('Escape')
            page.click("#skillList [data-skill='skill:sop-mine-2']")
            page.click('#skillMore-trigger')
            page.locator('#skDelete').click()
            assert '「규칙이 가리키는 조치」' in page.inner_text('dialog.confirm-dialog')
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            page.wait_for_selector("#skAlert [role='alert'], #skAlert .alert", timeout=8000)
            assert why in page.inner_text('#skAlert') and page.locator("#skillList [data-skill='skill:sop-mine-2']").count() == 1      # 거절: 까닭 그대로, 목록에 남는다
            page.click("#skillList [data-skill='skill:sop-mine-1']")
            page.click('#skillMore-trigger')
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
    new, loaded, also = 'HI-01_shift-inspection-supplement.md', 'HM-8_cooler-fan-manual.md', 'PM-02_powerpack-pm-checklist.md'
    posted = []

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/api/course-access'):
            return route.fulfill(json={'phase': 'course', 'actions': {}, 'documents': 'provided', 'provided_documents': [loaded, also, new],
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
            return route.fulfill(json=[_upload('doc-hm8', loaded, 'b1'), _upload('doc-pm2', also, 'b2')])
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
            page.wait_for_function("document.querySelectorAll('#providedDocs .row-meta').length === 3 && [...document.querySelectorAll('#providedDocs .row-meta')].every(n => n.textContent)", timeout=15000)
            # 처음 보이는 길은 「제공 문서에서 고르기」이고 파일 고르기 칸은 숨어 있다. 줄의 제목은 그 파일 머리의 제목 줄이다
            assert row(new).is_visible() and not page.locator('#manualPreview').is_visible()
            for f in (new, loaded):
                head = (WWW / 'samples' / f).read_text(encoding='utf-8').splitlines()[0].lstrip('# ').strip()
                assert row(f).locator('.row-title').inner_text() == head and f in row(f).locator('.row-meta').inner_text()
            assert '적재됨' in row(loaded).inner_text() and '적재됨' not in row(new).inner_text()
            # 줄의 자리(2026-11-16 사용자: 「적재됨과 원문 보기가 구분 없이 떠다닌다」): 상태 알약은 제목 쪽의 정해진 칸에, [원문 보기]는 줄 오른쪽 끝에 글 링크로 —
            # 같은 종류는 모든 줄에서 같은 세로선에 선다. 줄을 누르면 올라간다는 것은 목록 위 한 줄과 줄 끝의 꺾쇠가 말한다
            link = page.locator(f"#providedDocs [data-provided-view='{new}']")
            rows = page.evaluate("""() => [...document.querySelectorAll('#providedDocs .row-act')].map(act => { const r = e => { if (!e) return null; const b = e.getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width }; };
              const view = act.querySelector('.doc-view'), tag = act.querySelector('.tag'), cs = getComputedStyle(view), ts = tag && getComputedStyle(tag);
              return { row: r(act.querySelector('.row')), title: r(act.querySelector('.row-title')), meta: r(act.querySelector('.row-meta')), tag: r(tag), view: r(view), pick: r(act.querySelector('.doc-pick input')), go: r(act.querySelector('.doc-go')),
                viewPlain: cs.backgroundColor === 'rgba(0, 0, 0, 0)' && cs.borderTopWidth === '0px', tagPill: !!ts && ts.backgroundColor !== 'rgba(0, 0, 0, 0)' && parseFloat(ts.borderTopLeftRadius) >= 9 }; })""")
            assert len(rows) == 3 and [bool(x['tag']) for x in rows] == [True, True, False]
            same = lambda xs: max(xs) - min(xs) <= 1
            assert same([x['tag']['l'] for x in rows if x['tag']]) and same([x['view']['l'] for x in rows]) and same([x['view']['r'] for x in rows]), rows
            assert same([x['pick']['l'] for x in rows]) and same([x['title']['l'] for x in rows]) and same([x['go']['l'] for x in rows]), rows
            for x in rows:
                rw, mid = x['row'], lambda b: (b['t'] + b['b']) / 2
                assert x['pick']['r'] <= x['title']['l'] and x['title']['r'] <= x['view']['l'] and x['view']['r'] <= x['go']['l'] and x['go']['r'] <= rw['r'], x
                assert (x['view']['l'] - rw['l']) / rw['w'] > 0.8 and abs(mid(x['view']) - mid(rw)) <= 3, x                 # 동작: 줄의 오른쪽 끝 · 세로 가운데
                assert x['viewPlain'], '원문 보기는 글 링크 모양이다(상태 알약과 같은 모양이 아니다)'
                if x['tag']:
                    assert x['title']['l'] < x['tag']['l'] and (x['tag']['r'] - rw['l']) / rw['w'] < 0.6 and x['view']['l'] - x['tag']['r'] >= 3 * x['tag']['w'] and x['tagPill'], x      # 상태: 제목 쪽, 동작과 멀리
            assert '누르면 올라가' in page.inner_text('#manualPick .doc-review-bar')
            # 고르기 칸은 줄 위에 놓여 그것만 눌린다 — 눌러도 문서가 올라가지 않고 「한 번에 적재」 줄이 나온다
            page.locator(f"#providedDocs [data-batch-pick='{new}']").check(timeout=5000)
            assert posted == [] and '고른 1개 한 번에 적재' in page.inner_text('#manualBatchRun')
            page.locator(f"#providedDocs [data-batch-pick='{new}']").uncheck(timeout=5000)
            assert page.locator('#manualBatchRun').count() == 0
            # [원문 보기]는 내려받기가 아니라 새 탭에서 글로 열린다
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
            row_menu(page, "#manualHistory .row-act:has([data-doc-open='b1'])", "[data-manual-revise='doc-hm8']")
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
    (POST /api/kg/ddl/preview { filename, text, catalog })을 보내고 2단계(표와 열 고르기)로 간다. 적재한 표 정의에 그 파일의 연결이 남아 있으면 줄에 「적재됨」이 붙는다."""
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


# ------------------------------------------------------------------ 한 번에 적재 · 적재한 문서 목록 · 단계마다의 자리
def _proposal(doc, name, *, ready=True, previous=None):
    """AI 추출이 끝난 문서의 응답(procsvc manual_review 의 꼴): 고장 조치 · 구매 절차 · 참고 절차가 하나씩 — 적재 요청을 만드는 세 갈래를 모두 지난다."""
    step = lambda text: [{'order': 1, 'text': text, 'manual': 'X-1', 'anchor': None}]
    return {'filename': name, 'batch': 'b-' + doc, 'previous_batch': previous, 'status': 'READY', 'chars': 1800, 'pages': 1, 'warnings': [], 'source_id': f'manual:{doc}:abc',
            'document_id': doc, 'loaded': None, 'same_original': None, 'extraction': {'instance': 'inst-' + doc}, 'knowledge': {},
            'sections': [{'ref': 'X-1', 'title': '절 하나', 'excerpt': '본문', 'anchor': None}],
            'procedures': [
                {'id': 'SOP-A-01', 'name': '벨트 교체', 'section': 'X-1', 'anchor': None, 'steps': step('벨트를 교체한다.'),
                 'link': {'failureMode': 'fm:x', 'relation': 'MITIGATED_BY', 'kind': 'work_order', 'approver': 'role:operator', 'affects': [{'target': 'sv:ts1', 'sign': '-'}]}},
                {'id': 'SOP-A-02', 'name': '씰 구매', 'section': 'X-1', 'anchor': None, 'steps': step('씰을 발주한다.'),
                 'link': {'scope': 'purchase', 'kind': 'work_order', 'executable': True, 'parts': ['part:seal'], 'approver': 'role:buyer', 'supplier_policy': 'oem',
                          'actions': [{'action': 'action:purchase-request', 'value': 'sup:b'}]}},
                {'id': 'SOP-A-03', 'name': '상태 확인', 'section': 'X-1', 'anchor': None, 'steps': step('상태를 확인한다.'), 'link': {'kind': 'reference', 'executable': False}}],
            'validation': {'checked': True, 'technical_ready': ready, 'needs_human_review': True, 'can_commit': False,
                           'issues': [] if ready else [{'message': 'SOP-A-01: 고장 유형 연결을 확인하세요', 'sop': 'SOP-A-01', 'field': 'link.failureMode'}]}}


class _Docs:
    """문서 등록 화면이 부르는 process 응답의 대역(올리기 · AI 추출 · 개정 확인 · 적재 · 되돌리기). 적재 요청(commits)과 되돌리기(rollbacks)를 적어 둔다."""

    def __init__(self, provided, uploads=(), not_ready=()):
        self.provided, self.uploads, self.not_ready = list(provided), list(uploads), set(not_ready)
        self.commits, self.rollbacks, self.previews, self.polls = [], [], [], {}

    def doc_of(self, name):
        return next((u['document_id'] for u in self.uploads if u['filename'] == name), 'doc-' + name.split('_')[0].lower())

    def __call__(self, route):
        path, method = route.request.url.split('?')[0], route.request.method
        body = route.request.post_data_json if method == 'POST' else None
        if path.endswith('/api/course-access'):
            return route.fulfill(json={'phase': 'course', 'actions': {}, 'documents': 'provided', 'provided_documents': self.provided,
                                       'reasons': {k: '지금 단계에서는 하지 않습니다.' for k in ('assign', 'start', 'import_flow', 'document')}})
        if path.endswith('/api/kg/manuals/preview') and method == 'POST':
            self.previews.append(body)
            doc = body.get('document_id') or self.doc_of(body['filename'])
            full = _proposal(doc, body['filename'], previous='b0' if body.get('document_id') else None)
            return route.fulfill(json={k: v for k, v in full.items() if k not in ('extraction', 'sections', 'procedures', 'knowledge', 'validation')})
        if path.endswith('/extractions') and method == 'POST':
            return route.fulfill(json={'instance': 'inst-' + path.split('/sources/')[1].split('/')[0].split('%3A')[1]})
        if '/extractions/' in path:
            doc = path.rsplit('/', 1)[1][len('inst-'):]
            self.polls[doc] = self.polls.get(doc, 0) + 1
            if self.polls[doc] == 1:      # 처음 물으면 아직 읽는 중(구간 3개 가운데 1개) — 그 뒤에 결과
                return route.fulfill(json={'status': 'IN_PROGRESS', 'instance': 'inst-' + doc, 'progress': {'done': 1, 'total': 3}, 'segments': []})
            name = next(f for f in self.provided if self.doc_of(f) == doc)
            return route.fulfill(json={'status': 'DONE', 'instance': 'inst-' + doc, 'segments': [],
                                       'preview': _proposal(doc, name, ready=name not in self.not_ready, previous='b0' if any(u['document_id'] == doc for u in self.uploads) else None)})
        if path.endswith('/extractions'):
            return route.fulfill(json={'items': [], 'next_offset': None})
        if path.endswith('/api/kg/manuals/changes'):
            return route.fulfill(json={'removed': []})
        if path.endswith('/api/kg/manuals/commit'):
            self.commits.append(body)
            self.uploads[:] = [u for u in self.uploads if u['document_id'] != body['document_id']] + [_upload(body['document_id'], body['filename'], body['batch'])]
            return route.fulfill(json={'sections': 1, 'procedures': 3, 'steps': 3, 'candidate_activation': {}})
        if path.endswith('/rollback'):
            batch = path.split('/batches/')[1].split('/')[0]
            self.rollbacks.append((batch, body))
            self.uploads[:] = [u for u in self.uploads if u['batch'] != batch]
            return route.fulfill(json={'ok': True})
        if path.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'total': 0, 'next_offset': None})
        if path.endswith('/api/kg/manuals/catalog'):
            return route.fulfill(json={'parts': [{'id': 'part:seal', 'name': '펌프 축 씰', 'partNo': 'P-1'}], 'suppliers': [{'id': 'sup:b', 'name': 'B사'}], 'skills': [],
                                       'roles': [{'id': 'role:buyer', 'name': '구매 담당'}, {'id': 'role:operator', 'name': '운전원'}]})
        if path.endswith('/api/kg/catalog'):
            return route.fulfill(json={'roles': [{'id': 'role:operator', 'name': '운전원'}], 'failureModes': [{'id': 'fm:x', 'name': '벨트 느슨함'}]})
        if path.endswith('/api/kg/manuals'):
            return route.fulfill(json=list(self.uploads))
        if path.endswith('/golden-report'):
            return route.fulfill(json=None)
        if path.endswith('/api/kg/skills') or path.endswith('/api/kg/ingests'):
            return route.fulfill(json=[])
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        if path.endswith('/api/ontology/patterns'):      # 꼴이 다른 응답을 주면 셸이 알림을 띄워 화면 오른쪽 아래를 가린다
            return route.fulfill(json=[])
        return route.fulfill(json={})


def _open_docs(p, docs, answer=None):
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    b = p.chromium.launch()
    page = b.new_page()
    page.route('**/svc/**', answer or docs)
    page.goto(served.url + '/index.html')
    open_screen(page, 'knowledge')
    page.wait_for_function("n => document.querySelectorAll('#providedDocs .row-meta').length === n && [...document.querySelectorAll('#providedDocs .row-meta')].every(x => x.textContent)", arg=len(docs.provided), timeout=15000)
    page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
    return served, b, page


def test_여럿을_골라_한_번에_적재하면_문서마다_진행이_흐르고_검토가_필요한_문서는_멈추며_적재_요청은_검토_화면에서_손대지_않고_적재할_때와_같다():
    """2026-11-15 사용자: 「일괄로 맡길지 사람한테 맡길지 … 선택할 수 있게 process-gpt처럼」. 제공 문서를 여럿 골라 [고른 n개 한 번에 적재]를 누르면 문서마다
    올리기 → AI 추출 → 적재가 차례로 돌고(끝나기 전에 지금 읽는 구간이 줄에 보인다), 자동 검증이 「검토 필요」를 낸 문서는 적재하지 않고 멈춰 [검토 열기]로
    그 문서의 검토 단계가 열린다. 검토 없이 보내는 적재 요청은 같은 문서를 검토 화면에서 하나도 고치지 않고 적재할 때와 같아야 한다(두 길이 서버에 다른 것을 보내지 않는다)."""
    from playwright.sync_api import sync_playwright
    good, bad = 'HI-01_shift-inspection-supplement.md', 'HM-8_cooler-fan-manual.md'
    docs = _Docs([good, bad], not_ready=[bad])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            for f in (good, bad):
                page.locator(f"#providedDocs [data-batch-pick='{f}']").check(timeout=5000)
            assert page.inner_text('#manualBatchRun') == '고른 2개 한 번에 적재' and '검토 없이 적재합니다' in page.inner_text('#manualBatch')
            page.evaluate("""() => { window.seenBatch = []; new MutationObserver(() => { const t = document.querySelector('#manualBatch').innerText.replace(/\\s+/g, ' '); if (seenBatch.at(-1) !== t) seenBatch.push(t); })
              .observe(document.querySelector('#manualBatch'), { childList: true, subtree: true, characterData: true }); }""")
            page.click('#manualBatchRun')
            page.wait_for_selector('#manualBatchClose', timeout=30000)
            seen = page.evaluate('seenBatch')
            # 끝나기 전에 단계 이름과 지금 읽는 구간이 흘렀다(도는 고리만 보이지 않는다) — 디자인 기준 7절
            flowed = [t for t in seen if '2 / 2 처리' not in t]
            assert any('올리는 중' in t for t in flowed) and any('AI 추출 — 구간 3개 가운데 1개를 읽었습니다' in t for t in flowed) and any('지식 지도에 적재하는 중' in t for t in flowed), seen
            assert any(t.startswith('1 / 2 처리') for t in seen), seen                       # 「n / 전체 처리」가 문서 하나가 끝날 때마다 오른다
            done = page.inner_text('#manualBatch')
            assert '2 / 2 처리' in done and '적재 1 · 검토 필요 1' in done and '적재 완료 — 절 1 · 조치 방법 3 · 단계 3' in done
            assert '검토 필요 — 자동 검증이 「검토 필요 1건」을 냈습니다.' in done
            states = page.evaluate("() => [...document.querySelectorAll('#manualBatch .step')].map(s => s.dataset.state)")
            assert states == ['done', 'mine'], states                                         # 끝남은 초록 체크, 사람이 볼 문서는 「내 차례」 모양(실패가 아니다)
            # 적재된 것은 통과한 문서 하나뿐이다. 멈춘 문서는 적재 요청이 나가지 않았다
            assert [c['filename'] for c in docs.commits] == [good] and docs.commits[0]['reviewed'] is True and docs.commits[0]['by'] == '담당자'
            links = docs.commits[0]['links']
            assert links['SOP-A-01'] == {'failureMode': 'fm:x', 'relation': 'MITIGATED_BY', 'kind': 'work_order', 'approver': 'role:operator', 'affects': [{'target': 'sv:ts1', 'sign': '-'}]}
            assert links['SOP-A-02']['scope'] == 'purchase' and links['SOP-A-02']['executable'] is True and links['SOP-A-02']['parts'] == ['part:seal'] and links['SOP-A-02']['actions'] == [{'action': 'action:purchase-request', 'value': None}]
            assert links['SOP-A-03'] == {'kind': 'reference', 'executable': False, 'failureMode': None, 'relation': None, 'approver': None}
            # 다음 할 일: 지식 지도 · 결함 시뮬레이션으로 가는 링크가 결과 맨 아래에 있다
            assert page.locator("#manualBatch a.go").evaluate_all("ns => ns.map(n => n.dataset.goTab)") == ['ontology', 'scenario']
            assert page.locator(f"#providedDocs [data-provided='{good}'] .tag").inner_text() == '적재됨' and page.locator(f"#providedDocs [data-provided='{bad}'] .tag").count() == 0
            # 멈춘 문서: [검토 열기] → 그 문서의 AI 추출 결과가 검토 단계에 열린다(한 편씩 올렸을 때와 같은 화면)
            page.click(f"#manualBatch [data-batch-review='{bad}']")
            page.wait_for_selector('#manualReview #manualCommit', timeout=15000)
            assert page.get_attribute('#manualUpload', 'data-stage') == '3' and bad in page.inner_text('#manualReview .result') and '검토 필요 1건' in page.inner_text('#manualReview .doc-valid')
            # 같은 문서(통과한 문서)를 이번에는 한 편씩: 고르기 → AI 추출 → 검토 화면을 하나도 고치지 않고 적재 → 두 적재 요청이 같다
            page.click('#manualAnother')
            page.wait_for_selector(f"#providedDocs [data-provided='{good}']:not([disabled])", timeout=5000)
            assert page.locator('#manualBatch .doc-batch').count() == 0                      # 1단계로 돌아오면 끝난 결과는 걷힌다
            docs.polls.clear()
            page.click(f"#providedDocs [data-provided='{good}']")
            page.wait_for_selector('#manualAgentExtract', timeout=15000)
            page.click('#manualAgentExtract')
            page.wait_for_selector('#manualReview #manualCommit', timeout=30000)
            page.check('#manualReviewed')
            page.click('#manualCommit')
            page.wait_for_function("document.querySelector('#manualMsg')?.textContent.startsWith('적재 완료')", timeout=15000)
            assert len(docs.commits) == 2
            by_hand, at_once = dict(docs.commits[1]), dict(docs.commits[0])
            assert by_hand.pop('previous_batch') == 'b0' and at_once.pop('previous_batch') is None      # 두 번째는 방금 적재한 문서의 개정이다 — 그 밖은 글자 하나 다르지 않다
            assert by_hand == at_once
        finally:
            b.close()
            served.close()


def test_적재한_문서는_줄마다_이름과_넣은_내용이고_줄을_누르면_옆_판이_열리며_되돌리기는_더_보기에서_확인_뒤에_나간다():
    """2026-11-16: 「등록된 매뉴얼」 표와 제공 문서 목록이 같은 문서의 상태를 두 번 보였고, 줄마다 단추 둘이 늘 떠 있었다. 적재한 문서는 줄 = 이름 · 넣은 내용,
    줄을 누르면 옆 판(이 문서로 답할 수 있는 질문), 이 문서 개정 · 원본 내려받기 · 이 판본 되돌리기는 줄의 더 보기, 보관한 원문 · 등록 이력은 구역 머리의 더 보기다."""
    from playwright.sync_api import sync_playwright
    a, c = 'HM-8_cooler-fan-manual.md', 'PM-02_powerpack-pm-checklist.md'
    docs = _Docs([a, c], uploads=[_upload('doc-hm8', a, 'b1'), _upload('doc-pm2', c, 'b2')])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            page.wait_for_selector('#manualHistory .doc-loaded .row', timeout=15000)
            assert page.inner_text('#manualHistory .sec-head h2') == '적재한 문서'
            rows = page.locator('#manualHistory .doc-loaded .row').all_inner_texts()
            assert [r.split('\n')[0] for r in rows] == [a, c] and all('절 8 · 조치 방법 7 · 단계 25' in r for r in rows)
            assert page.locator('#manualHistory .tag').count() == 0 and page.locator('#manualHistory table').count() == 0      # 「적재됨」은 위의 제공 문서 목록 한 곳에만
            assert page.locator('#providedDocs .tag').all_inner_texts() == ['적재됨', '적재됨']
            # 줄 → 옆 판: 그 문서로 답할 수 있는 질문. 닫으면 목록 그대로
            page.click("#manualHistory [data-doc-open='b1']")
            page.wait_for_selector('#docSheet[open] .doc-q-title', timeout=8000)
            assert page.inner_text('#docSheet .sheet-head h2') == a and '이 문서로 답할 수 있는 질문' in page.inner_text('#docSheet')
            page.click('#docSheet [data-doc-sheet-close]')
            assert page.locator('#docSheet[open]').count() == 0
            # 구역 머리의 더 보기: 보관한 원문(옆 판)
            page.click('#docListMore-trigger')
            page.locator("#docListMore-menu [data-doc-sheet='sources']").click(timeout=5000)
            page.wait_for_selector('#docSheet[open] .empty', timeout=8000)
            assert page.inner_text('#docSheet .sheet-head h2') == '보관한 원문' and '보관한 원문이 아직 없습니다' in page.inner_text('#docSheet')
            page.keyboard.press('Escape')
            # 첫 줄의 더 보기는 아래 줄에 가리지 않고 눌린다(row_menu 가 실제로 누른다) → 확인 창 → 되돌리기 요청 → 목록에서 빠지고 결과 한 줄이 남는다
            row_menu(page, "#manualHistory .row-act:has([data-doc-open='b1'])", "[data-manual-undo='b1']")
            assert '이 판의 등록을 취소할까요' in page.inner_text('dialog.confirm-dialog')
            assert docs.rollbacks == []
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            page.wait_for_function("document.querySelector('#manualHistoryMsg')?.textContent.startsWith('등록을 취소했습니다')", timeout=15000)
            assert docs.rollbacks == [('b1', {'by': '담당자'})]
            assert [r.split('\n')[0] for r in page.locator('#manualHistory .doc-loaded .row').all_inner_texts()] == [c]
            assert page.locator(f"#providedDocs [data-provided='{a}'] .tag").count() == 0
        finally:
            b.close()
            served.close()


def test_단계_줄_아래_첫_내용은_매뉴얼과_표_정의에서_같은_높이에_서고_검토하는_동안에는_적재한_목록이_보이지_않는다():
    """기록 「지금 할 것」: 매뉴얼 보기와 표 정의 보기의 위 여백이 16px 달랐다. 두 보기는 같은 틀(단계 줄 → 지금 단계의 내용 하나 → 적재한 목록)이므로,
    같은 단계의 첫 내용이 같은 높이에서 시작해야 한다. 올린 문서를 검토하는 동안(2 · 3단계)에는 지금 단계의 내용만 보인다."""
    from playwright.sync_api import sync_playwright
    name = 'HI-01_shift-inspection-supplement.md'
    docs = _Docs([name], uploads=[_upload('doc-pm2', 'PM-02_powerpack-pm-checklist.md', 'b2')])
    ddl = {'filename': 'legacy-plant-db.sql', 'chars': 10, 'catalog': 'postgres', 'datasource': 'ds', 'warnings': [], 'systems': [], 'existingSystems': [],
           'sourceOptions': [{'id': 'ds', 'label': '업무 DB', 'schema': 'public'}], 'inputs': [], 'tables': [{'table': 'T_EQP00', 'comment': '', 'system': '', 'columns': ['EQP_CD'], 'selected': []}]}

    def answer(route):
        path = route.request.url.split('?')[0]
        if path.endswith('/api/kg/ddl/preview'):
            return route.fulfill(json=ddl)
        if path.endswith('/api/kg/ingests'):
            return route.fulfill(json=[{'batch': BATCH, 'label': 'InputData', 'nodes': 3, 'source': 'legacy-plant-db.sql'}])
        return docs(route)
    top = "s => Math.round(document.querySelector(s).getBoundingClientRect().top)"
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs, answer)
        try:
            page.wait_for_selector('#manualHistory .doc-loaded .row', timeout=15000)
            first = {'steps': page.evaluate(top, '#manualSteps'), 'bar': page.evaluate(top, '#manualPick .doc-review-bar'), 'row': page.evaluate(top, '#providedDocs .row')}
            page.click(f"#providedDocs [data-provided='{name}']")
            page.wait_for_selector('#manualResult .mprev', timeout=15000)
            second = page.evaluate(top, '#manualResult .result')
            assert page.is_hidden('#manualHistory')                                # 2단계: 지금 단계의 내용 하나만
            page.click('#manualAnother')
            page.wait_for_selector('#manualHistory .doc-loaded .row', state='visible', timeout=5000)
            page.click("#docKinds [data-doc-kind='ddl']")
            page.wait_for_selector(f"#ddlHistory [data-batch='{BATCH}']", timeout=15000)
            assert first == {'steps': page.evaluate(top, '#ddlSteps'), 'bar': page.evaluate(top, '#ddlPick .doc-review-bar'), 'row': page.evaluate(top, '#providedDdl .row')}
            page.click("#providedDdl [data-provided='legacy-plant-db.sql']")
            page.wait_for_selector('#ddlResult .mprev', timeout=15000)
            assert page.evaluate(top, '#ddlResult .result') == second and page.is_hidden('#ddlHistory')
            page.click('#ddlAnother')
            page.wait_for_selector(f"#ddlHistory [data-batch='{BATCH}']", state='visible', timeout=5000)
        finally:
            b.close()
            served.close()
