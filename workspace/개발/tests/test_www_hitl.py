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
            # 되돌린 뒤 이력을 다시 읽어 그린 때(되돌린 줄이 사라진 그 그리기 — 전에는 그 그리기가 문장을 지웠다)를 기다린 뒤에 문장을 본다
            page.wait_for_function("document.querySelectorAll('#ddlHistory [data-clear]').length === 0", timeout=15000)
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
            assert '이 원문으로 만든 판본이 지식 지도에 적재돼 있습니다' in again and page.locator('#manualReviseSame').count() == 0
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
            # 처음 보이는 길은 「제공 문서에서 고르기」이고 파일 고르기 칸은 숨어 있다. 줄의 제목은 그 파일 머리의 제목 줄이고, 끝의 출처 괄호
            # 「(HM-8, 교육용 예시)」 꼴(문서 번호 · 「교육용 예시」 — 제작 흔적)만 떼어 보인다. 괄호 없는 제목(HI-01)은 그대로다
            assert row(new).is_visible() and not page.locator('#manualPreview').is_visible()
            for f, note in ((new, ''), (loaded, ' (HM-8, 교육용 예시)')):
                head = (WWW / 'samples' / f).read_text(encoding='utf-8').splitlines()[0].lstrip('# ').strip()
                assert row(f).locator('.row-title').inner_text() + note == head and f in row(f).locator('.row-meta').inner_text()
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
            # 늘 보이는 안내는 줄을 누르라는 한 문장뿐이다 — 「사람 검토 대신 …한 번에 적재」는 체크 칸을 하나라도 고른 뒤에만 단추와 함께 나온다(사용자 2026-11-20:
            # 사람 검토를 배우는 화면에 그 길이 늘 떠 있어 체크 칸을 눌러야 하는 것으로 읽혔다)
            hint = "#manualPick .doc-review-bar [data-pick='provided']"
            assert page.inner_text(hint).strip() == '문서를 누르면 올라가 AI 추출로 넘어갑니다.' and page.inner_text('#manualBatch').strip() == ''
            assert '한 번에 적재' not in page.inner_text('#manualPick') and '사람 검토 대신' not in page.inner_text('#manualPick')
            page.locator(f"#providedDocs [data-batch-pick='{new}']").check(timeout=5000)
            assert posted == [] and '고른 1개 한 번에 적재' in page.inner_text('#manualBatchRun')
            assert '한 번에 적재 — 사람 검토 대신 자동 검증을 통과한 문서만 적재합니다.' in page.inner_text('#manualBatch') and page.inner_text(hint).strip() == '문서를 누르면 올라가 AI 추출로 넘어갑니다.'
            page.locator(f"#providedDocs [data-batch-pick='{new}']").uncheck(timeout=5000)
            assert page.locator('#manualBatchRun').count() == 0 and page.inner_text('#manualBatch').strip() == ''
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
        self.more_catalog = {}      # 그 시험이 더 싣는 지금 지식 목록(세부 동작 actions · 원인 causes …)
        self.failure_modes = [{'id': 'fm:x', 'name': '벨트 느슨함', 'component': 'comp:fan'}]      # 서버 GET /api/kg/manuals/catalog 의 failure_modes(지금 지식의 고장 유형)

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
                                       'roles': [{'id': 'role:buyer', 'name': '구매 담당'}, {'id': 'role:operator', 'name': '운전원'}], 'failure_modes': list(self.failure_modes),
                                       **self.more_catalog})
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


class _CitedDocs(_Docs):
    """06 화면 훑기(2026-11-20)에서 걸린 꼴을 모두 가진 문서: 절차의 원문 인용이 문서 서식의 제목 줄(「### SOP-A-01 벨트 교체」)이고, 이름 없는 규칙의
    원문 문장에 경보 코드(COOLER_DEGRADATION)가 있으며, 적재가 기존 후보 규칙에 절차 하나(SOP-A-01)만 이었다(서버 manual_graph.candidate_joins 의 꼴)."""

    def __call__(self, route):
        path = route.request.url.split('?')[0]
        if path.endswith('/api/ontology/patterns'):
            return route.fulfill(json=[{'id': 'pattern:cool', 'code': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하', 'failureModes': []}])
        if '/extractions/' in path:
            doc = path.rsplit('/', 1)[1][len('inst-'):]
            r = _proposal(doc, self.provided[0])
            r['procedures'][0]['anchor'] = {'page': 1, 'quote': '### SOP-A-01 벨트 교체\n벨트가 느슨하면 교체한다.', 'located': 'exact'}
            r['knowledge'] = {'rules': [{'id': 'rule:x-fouling', 'table': 'dt:diagnose-cause', 'effect': 'SELECT', 'outputs': [], 'anchor': None,
                                         'annotation': 'COOLER_DEGRADATION 경보에서 냉각 효율이 70 % 미만이면 핀 오염을 1순위 원인으로 둔다.'}]}
            return route.fulfill(json={'status': 'DONE', 'instance': 'inst-' + doc, 'segments': [], 'preview': r})
        if path.endswith('/api/kg/manuals/commit'):
            self.commits.append(route.request.post_data_json)
            return route.fulfill(json={'sections': 1, 'procedures': 3, 'steps': 3, 'candidate_activation': {'SOP-A-01': ['rule:cand-x']}})
        return super().__call__(route)


def test_검토_화면의_원문_인용과_지식_후보_제목과_적재_완료_글은_학생이_읽는_말이다():
    """06 화면 훑기(2026-11-20) 셋: ① 원문 인용 칸에 문서 서식의 제목 표시 「###」가 그대로 보였다(인용 글은 원문 그대로이고 그 표시만 뗀다).
    ② 이름 없는 규칙의 제목이 원문 문장 그대로라 「COOLER_DEGRADATION 경보에서 …」로 보였다 — 다른 화면 문장처럼 경보 이름으로 읽는다.
    ③ 적재 완료 글이 「후보 규칙에 연결: 쿨러 냉각 성능 상실 → (되돌리면 함께 빠집니다)」였다 — 서버가 고장 유형마다 고른 규칙 목록(빈 목록 포함)을 보냈고 화면이
    그대로 찍었다. 이제 서버는 실제로 기존 규칙에 이은 절차만 보내고, 화면은 그 절차의 이름을 말한다(이은 것이 없으면 아무것도 적지 않는다).
    적재 단계 목록은 서버에 가는 일만 적고(화면이 목록을 다시 읽는 일은 단계가 아니다), 넣은 수는 적재 줄 이름 하나가 말한다 — 「적재 완료: 절 … 」 한 줄과
    적재 줄 아래 메모로 같은 수를 되풀이하지 않는다(사용자 2026-11-20 「다 처리해줘」)."""
    from playwright.sync_api import sync_playwright
    name = 'HI-01_shift-inspection-supplement.md'
    docs = _CitedDocs([name])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            page.wait_for_function("() => UI.patterns && UI.patterns.COOLER_DEGRADATION === '쿨러 성능 저하'", timeout=8000)
            page.click(f"#providedDocs [data-provided='{name}']")
            page.wait_for_selector('#manualAgentExtract', timeout=15000)
            page.click('#manualAgentExtract')
            page.wait_for_selector('#manualReview #manualCommit', timeout=30000)
            page.click("[data-item='proc:SOP-A-01']")
            assert page.inner_text("[data-pane='proc:SOP-A-01'] .doc-quote blockquote").strip() == 'SOP-A-01 벨트 교체\n벨트가 느슨하면 교체한다.'
            assert page.evaluate("() => document.querySelector(\"[data-item='know:rules:rule:x-fouling'] .row-title\").textContent") == '쿨러 성능 저하 경보에서 냉각 효율이 70 % 미만이면 핀 오염을 1순위 원인으로 둔다.'
            page.check('#manualReviewed')
            page.click('#manualCommit')
            page.wait_for_function("document.querySelector('#manualCommitTitle')?.textContent === '지식 지도에 적재했습니다'", timeout=15000)
            assert page.inner_text('#manualMsg').strip() == '이미 있던 판단 규칙이 이 문서의 조치 방법 벨트 교체도 후보로 냅니다.'
            steps = page.locator('#manualCommitSteps .lv-step').all_inner_texts()
            assert len(steps) == 1 and steps[0].startswith('검토한 내용을 지식 지도에 적재 — 매뉴얼 절 1개 · 조치 방법 3개 · 단계 3개') and '다시 읽기' not in steps[0] and '\n절 1' not in steps[0], steps
        finally:
            b.close()
            served.close()


class _MemoDocs(_Docs):
    """추출 결과에 경고가 실린 문서 둘. 첫 문서는 제공 문서의 응답 꼴이다(procsvc manual_approved_cache — 추출 요청 · 결과 · 검토본에 cache 칸이 있고, 경고는 그 추출
    결과를 만든 사람이 서명 묶음에 남긴 작업 메모(proposal.warnings), cache.origin.review_notes 는 검토하며 고친 곳). 둘째 문서는 AI가 방금 읽은 결과다(cache 없음 — 경고는 AI가 낸 것).
    두 문서 모두 서버가 원문에서 찾은 수치 경고(validation.source_value_warnings)가 경고 목록에 함께 실린다(manual_extraction — preview['warnings'])."""
    MEMO, NOTE, VALUE = '후보 규칙 추가: 원인 = 팬 구동 불량 → SOP-FAN-11 (REMEDIED_BY · CMMS 작업지시)', '기존 검토본의 승인 역할/원인 연결은 유지', 'SOP-A-01: 원문 수치 80 %가 단계에 없습니다'
    PAGE = 'HM-8.3 냉각 기준표는 절 기준으로 보존하고 별도 절차로 만들지 않았습니다'      # 쪽별 추출 검토 기록(proposal.page_reviews)

    def __call__(self, route):
        path, method = route.request.url.split('?')[0], route.request.method
        cached = lambda doc: doc == self.doc_of(self.provided[0])
        if path.endswith('/extractions') and method == 'POST':
            doc = path.split('/sources/')[1].split('/')[0].split('%3A')[1]
            return route.fulfill(json={'instance': 'inst-' + doc, **({'cache': {'version': 'reviewed-1'}} if cached(doc) else {})})
        if '/extractions/' in path:
            doc = path.rsplit('/', 1)[1][len('inst-'):]
            r = _proposal(doc, next(f for f in self.provided if self.doc_of(f) == doc))
            r['warnings'] = [self.MEMO, self.VALUE]
            r['validation']['source_value_warnings'] = [self.VALUE]
            r['coverage'] = {'ratio': 0.76}
            r['page_reviews'] = [{'page': 1, 'note': self.PAGE}]
            r['procedures'][0]['anchor'] = {'page': 1, 'start': 0, 'quote': '벨트를 교체한다.', 'located': 'exact'}
            if cached(doc):
                r['extraction']['cache'] = {'version': 'reviewed-1', 'origin': {'review_notes': [self.NOTE]}}
            return route.fulfill(json={'status': 'DONE', 'instance': 'inst-' + doc, 'segments': [], 'preview': r, **({'cache': r['extraction']['cache']} if cached(doc) else {})})
        return super().__call__(route)


def test_제공_문서의_검토_화면에는_작업_메모와_인용_비율이_없고_내가_올린_문서의_AI_추출_경고는_그대로_보인다():
    """06 화면 훑기(2026-11-20) · 사용자 답: 제공 문서의 「추출 경고 3건」을 펼치면 그 추출 결과를 만든 사람의 작업 메모(REMEDIED_BY · CMMS 작업지시 …)였고,
    「추출 과정 보기」 안에도 「검토하며 고친 곳」과 「AI가 미리 읽고 사람이 … 검토해 둔 …」이 있었다 — 학생 화면에 내지 않는다. 그 메모와 한 목록에 실려 오던
    서버의 원문 수치 경고는 자동 검증 줄의 「원문 수치 확인 필요」로 보인다(가려서 사실이 빠지지 않게). 대조 줄의 기준 없는 비율 「원문 글자의 76 %가 인용에
    쓰였습니다」도 뺀다. AI가 방금 읽은 문서(cache 없음)의 추출 경고는 그대로 접기로 보인다. 「쪽별 추출 검토 기록」도 같은 까닭(제공 문서의 것은 추출 결과를 만든 사람의
    메모)으로 제공 문서에서는 빼고, AI가 방금 읽은 문서에서는 접기로 보인다. 처음 추출한 문서에는 「이 문서의 이전 추출 결과」 접기가 없다 — 지금 연 결과 말고 열 결과가 없다(사용자 2026-11-20 「다 처리해줘」)."""
    from playwright.sync_api import sync_playwright
    provided, mine = 'HM-8_cooler-fan-manual.md', 'HI-01_shift-inspection-supplement.md'
    docs = _MemoDocs([provided, mine])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, provided)
            page.wait_for_function("document.querySelector('#manualReview [data-live-trail]')?.textContent.includes('검토 화면에 올렸습니다')", timeout=15000)
            page.click('#manualProcess > summary')
            page.locator('#manualProcess [data-cached-yield] .step').first.wait_for(state='visible', timeout=3000)
            shown = page.evaluate("() => document.querySelector('#manualReview').textContent")      # 접힌 것 안까지(원문 판 포함) 화면에 실린 글 전부
            for hidden in ('추출 경고', docs.MEMO, 'REMEDIED_BY', '검토하며 고친', docs.NOTE, '미리', '원문 글자의', '76', '저장된', '이 PC에 없습니다', '쪽별 추출 검토 기록', docs.PAGE):
                assert hidden not in shown, hidden
            assert page.evaluate("document.querySelector('#manualExtractionRuns').closest('details').hidden")      # 지금 연 결과 말고 열 결과가 없다
            assert page.inner_text('#manualProcess [data-cached-note]').strip() == 'AI가 이 문서에서 절마다 뽑은 것입니다.'
            trail = page.inner_text('#manualReview [data-live-trail]')
            assert '인용 1곳이 원문의 그 자리에 있습니다 · 사람이 확인할 곳 0건' in trail, trail
            assert '원문 수치 확인 필요' in shown and docs.VALUE in page.inner_text('#manualReview .doc-valid'), shown      # 서버가 찾은 수치 경고는 남는다
            # AI가 방금 읽은 문서: 추출 경고 접기가 그대로 있고 그 안에 AI가 낸 경고가 있다(수치 경고는 그 접기에 이미 있어 되풀이하지 않는다)
            page.click('#manualAnother')
            _open_review(page, docs, mine)
            folds = page.locator('#manualReview .doc-folds > details > summary').all_inner_texts()
            assert any(t.replace('\n', ' ').startswith('추출 경고') and '2건' in t for t in folds), folds
            assert '쪽별 추출 검토 기록' in folds and docs.PAGE in page.text_content('#manualReview .doc-folds'), folds      # AI가 방금 읽은 문서의 쪽별 기록은 그대로
            assert docs.MEMO in page.evaluate("() => [...document.querySelectorAll('#manualReview .doc-folds > details')].find(d => d.querySelector('summary').textContent.startsWith('추출 경고')).textContent")
            assert '원문 수치 확인 필요' not in page.inner_text('#manualReview .doc-valid')
        finally:
            b.close()
            served.close()


class _KindDocs(_Docs):
    """구매 · 참고 절차의 서버 검사 기록(validation.execution — manual_review 의 꼴)이 실린 문서와, 참고 절차(SOP-A-03)와 번호 · 단계가 같은 등록 절차 하나가 있는 목록."""
    CONTRACT = {'id': 'skill:sop-a-03', 'sopId': 'SOP-A-03', 'contract_sha256': 'c' * 64, 'steps': [{'order': 1, 'text': '상태를 확인한다.'}], 'sections': [], 'owner': True}

    def __call__(self, route):
        path = route.request.url.split('?')[0]
        if '/extractions/' in path and self.polls.get(path.rsplit('/', 1)[1][len('inst-'):], 0) >= 1:
            doc = path.rsplit('/', 1)[1][len('inst-'):]
            r = _proposal(doc, self.provided[0])
            r['validation'].update(executable_ready=True, execution=[{'sop': 'SOP-A-02', 'executable': True, 'ready': True, 'issues': [], 'evaluation_scope': 'structural'},
                                                                     {'sop': 'SOP-A-03', 'executable': False, 'ready': True, 'issues': []}])
            return route.fulfill(json={'status': 'DONE', 'instance': 'inst-' + doc, 'segments': [], 'preview': r})
        if path.endswith('/api/kg/manuals/catalog'):
            return route.fulfill(json={'parts': [{'id': 'part:seal', 'name': '펌프 축 씰', 'partNo': 'P-1'}], 'suppliers': [{'id': 'sup:b', 'name': 'B사'}],
                                       'skills': [{'id': 'skill:sop-a-03', 'name': '교대 상태 확인', 'reference_contract': self.CONTRACT}],
                                       'roles': [{'id': 'role:buyer', 'name': '구매 담당'}, {'id': 'role:operator', 'name': '운전원'}], 'failure_modes': list(self.failure_modes)})
        return super().__call__(route)


def test_절차의_선택지는_이름만이고_구매_참고_절차는_무엇이_되는지_결론_한_줄로_말한다():
    """화면 글 검토(2026-11-20) 고칠 것 7 · 8: 고르는 이름에 검사 규칙이 붙어 있었고(「고장 조치 · 고장 유형 연결 필수」 · 「구매 원문 절차 · 구매 업무 범위」 ·
    「일반 원문 참고 절차 · 실행 후보 제외」), 구매 · 참고 절차의 검토 칸은 「~아님 · ~확인하지 않음 · ~추정하지 않습니다」를 늘어놓고 그 절차가 무엇이 되는지는 말하지
    않았다. 선택지는 이름만 보이고, 절차마다 결론 한 줄(승인하면 구매 요청을 만든다 / 원문만 보관하고 AI가 조치로 고르지 않는다)이 먼저 보인다. 이미 등록된 절차와
    잇는 자리도 결론 한 줄이 먼저이고, 두 절차의 단계를 나란히 견주는 것은 접혀 있다가 단계가 달라 이을 수 없을 때만 펴진다."""
    from playwright.sync_api import sync_playwright
    name = 'HI-01_shift-inspection-supplement.md'
    docs = _KindDocs([name])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, name)
            options = lambda sel: page.locator(sel + ' option').all_inner_texts()
            assert options("[data-manual-scope='SOP-A-01']") == ['고장 조치', '구매 절차']
            assert options("select[data-kind='SOP-A-01']") == ['정비 요청', '설비 제어', '참고 절차']
            assert options("[data-manual-executable='SOP-A-02']") == ['원문을 확인하고 선택하세요', '원문만 보관', '구매 요청을 만드는 절차']
            assert options("[data-reference-executable='SOP-A-03']") == ['원문을 확인하고 선택하세요', '원문만 보관']
            assert page.evaluate("() => [...document.querySelectorAll('#manualItems [data-item^=\"proc:\"] .row-meta')].map(n => n.textContent.split(' · ')[1])") == ['벨트 느슨함', '구매 절차', '참고 절차']
            # 구매 · 참고 절차의 결론은 접혀 있지 않다(펼친 접기) — 절차마다 한 줄
            fold = page.locator('#manualReview .doc-folds > details').filter(has_text='구매 · 참고 절차')
            assert fold.evaluate('d => d.open') and fold.locator('> summary').inner_text().replace('\n', ' ').startswith('구매 · 참고 절차')
            assert fold.locator('ul.doc-issues > li').all_inner_texts() == ['씰 구매 (SOP-A-02) · 승인하면 구매 요청을 만드는 절차입니다(견적 · 재고는 그때 확인합니다).',
                                                                           '상태 확인 (SOP-A-03) · 원문만 보관하고 AI가 조치로 고르지 않습니다.']
            # 참고 절차를 이미 등록된 같은 절차와 잇는다: 결론 한 줄, 견주는 표는 접혀 있다. 단계를 고쳐 달라지면 이을 수 없는 까닭과 함께 펴진다
            page.click("#manualItems [data-item='proc:SOP-A-03']")
            box = "[data-reference-comparison='SOP-A-03']"
            assert page.inner_text(box).strip() == '이미 등록된 절차와 연결하지 않고, 이 문서의 원문 단계만 보관합니다.'
            page.select_option("[data-reference-target='SOP-A-03']", 'skill:sop-a-03')
            assert page.inner_text(box + ' > p').strip() == '이미 등록된 「교대 상태 확인」 절차와 같은 절차로 잇습니다.'
            assert page.locator(box + ' [data-reference-detail]').evaluate('d => d.open') is False
            page.fill("textarea[data-manual-step='SOP-A-03']", '상태를 두 번 확인한다.')
            assert page.inner_text(box + ' > p').strip() == '원문의 단계가 등록된 절차의 단계와 달라 연결할 수 없습니다.'
            page.select_option("[data-reference-target='SOP-A-03']", '')
            page.select_option("[data-reference-target='SOP-A-03']", 'skill:sop-a-03')
            assert page.locator(box + ' [data-reference-detail]').evaluate('d => d.open') is True
            detail = page.inner_text(box + ' [data-reference-detail]')
            assert '상태를 두 번 확인한다.' in detail and '상태를 확인한다.' in detail and '등록된 절차의 단계 · 교대 상태 확인 (SOP-A-03)' in detail, detail
            # 방어 문장과 내부 판정 이름은 검토 화면 어디에도 없다(접힌 원문 판 밖)
            shown = page.evaluate("() => { const c = document.querySelector('#manualReview').cloneNode(true); c.querySelectorAll('details').forEach(d => { if (d.querySelector(':scope > summary')?.textContent.includes('원문')) d.remove(); }); return c.textContent; }")
            for gone in ('실행 후보', '참고 보관', '일반 원문', '연결 필수', '업무 범위 ·', '추정하지', '확인하지 않음', '확인 안 됨', '완료 아님', '짐작해', '소유 문서', '고정 판본'):
                assert gone not in shown, gone
        finally:
            b.close()
            served.close()


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
            assert page.inner_text('#manualBatchRun') == '고른 2개 한 번에 적재' and '사람 검토 대신 자동 검증을 통과한 문서만 적재합니다' in page.inner_text('#manualBatch')
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
            assert states == ['done', 'mine'], states                                         # 끝남은 초록 체크, 사람이 볼 문서는 「내가 할 일」 모양(실패가 아니다)
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
            page.wait_for_function("document.querySelector('#manualCommitTitle')?.textContent === '지식 지도에 적재했습니다'", timeout=15000)
            assert len(docs.commits) == 2
            by_hand, at_once = dict(docs.commits[1]), dict(docs.commits[0])
            assert by_hand.pop('previous_batch') == 'b0' and at_once.pop('previous_batch') is None      # 두 번째는 방금 적재한 문서의 개정이다 — 그 밖은 글자 하나 다르지 않다
            assert at_once.pop('review_scope') == 'automatic' and 'review_scope' not in by_hand     # 한 번에 적재는 사람이 검토하지 않았다는 사실만 더 싣는다(C10)
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
            # 메뉴 · 확인 창 · 결과 줄이 같은 일을 같은 이름으로 부른다(V 8절 8: 메뉴는 「이 판본 되돌리기」인데 확인 창은 「등록을 취소할까요 · [등록 취소]」였다).
            # 메뉴에 실제로 나온 이름에서 동사(「되돌리기」)와 대상(「판본」)을 읽어 확인 창 · 결과 줄에 댄다
            menu_label = page.locator("#manualHistory [data-manual-undo='b1']").text_content().strip()
            what, verb = menu_label.split()[-2:]
            row_menu(page, "#manualHistory .row-act:has([data-doc-open='b1'])", "[data-manual-undo='b1']")
            dialog = page.locator('dialog.confirm-dialog')
            assert dialog.locator("button[value='ok']").inner_text().strip() == verb, (menu_label, dialog.inner_text())
            assert what in dialog.locator('h2').inner_text() and verb[:-2] in dialog.locator('h2').inner_text() and '취소' not in dialog.locator('h2').inner_text(), dialog.inner_text()
            assert '이전 판본이 있으면 그 판본의 내용으로 돌아갑니다' in dialog.inner_text()      # 서버가 실제로 하는 일(manual_graph.rollback — 적재 전 상태로)
            assert docs.rollbacks == []
            dialog.locator("button[value='ok']").click()
            page.wait_for_function("document.querySelector('#manualHistoryMsg')?.textContent.includes('되돌렸습니다')", timeout=15000)
            done = page.inner_text('#manualHistoryMsg')
            assert done.startswith(what) and '빠졌습니다' in done and '취소' not in done, done      # 이전 판본이 없던 판(응답에 restored_batch 없음): 빠졌다고 말한다
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


# ------------------------------------------------------------------ 눌러 보기에서 찾은 것(2026-11-16): 종류 칸 · 표 정의의 고른 열 · 이미 읽은 문서
def _page(answer):
    """실제 화면을 실제 브라우저로 여는 한 벌(served · browser · page). 부른 쪽이 with 로 쓴다."""
    import contextlib

    @contextlib.contextmanager
    def cm():
        from playwright.sync_api import sync_playwright
        app = FastAPI()
        app.mount('/', StaticFiles(directory=WWW, html=True))
        served = Served(app)
        try:
            with sync_playwright() as p:
                b = p.chromium.launch()
                page = b.new_page(viewport={'width': 1440, 'height': 900})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.route('**/svc/**', answer)
                page.goto(served.url + '/index.html')
                yield page
                assert errors == [], errors
                b.close()
        finally:
            served.close()
    return cm()


def test_새_조치_방법의_종류_칸에서_고를_수_있는_것은_정비_요청_하나이고_저장_요청도_그_종류로_나간다():
    """설비에 명령을 내리는 조치(설비 제어)는 화면에서 만들 수 없다(서버가 늘 거절한다). 전에는 종류 칸에 「설비 제어」가 있어 학생이 골라 적고 저장한 뒤에야 거절을 봤다.
    [새 조치 방법] 폼의 종류 칸에 고를 수 있는 것이 「정비 요청」 하나이고, 칸을 채워 [추가]를 누르면 서버로 가는 요청의 종류가 그 값이다."""
    posted = []

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/api/kg/skills') and method == 'POST':
            posted.append(route.request.post_data_json)
            return route.fulfill(json=_skill('skill:sop-new-1', '새 조치'))
        if path.endswith('/api/kg/skills'):
            return route.fulfill(json=[_skill('skill:sop-mine-1', '내가 만든 조치')])
        if path.endswith('/api/kg/catalog'):
            return route.fulfill(json={'roles': [{'id': 'role:operator', 'name': '운전원'}], 'failureModes': [{'id': 'fm:x', 'name': '벨트 느슨함'}]})
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    with _page(answer) as page:
        open_screen(page, 'skills')
        page.wait_for_selector("#skillList [data-skill='skill:sop-mine-1']", timeout=15000)
        page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
        page.click('#skillNew')
        page.wait_for_selector('#skKind')
        kinds = page.evaluate("[...document.querySelector('#skKind').options].map(o => [o.value, o.textContent.trim()])")
        listed = page.evaluate("[...document.querySelectorAll(\"#skillList [data-skill-kind], #view-skills [data-skill-kind]\")].map(b => b.textContent.replace(/[0-9\\s]+$/, '').trim())")
        assert len(kinds) == 1 and kinds[0][1] in listed and '제어' not in kinds[0][1], (kinds, listed)      # 하나뿐이고, 그 이름은 목록 거르기의 「정비 요청」과 같은 말
        page.fill('#skName', '벨트 장력 조정'); page.select_option('#skRole', 'role:operator'); page.fill('#skSop', 'SOP-NEW-1')
        page.select_option('#skFm', 'fm:x'); page.fill('#skSteps', '현장 제어로 전환한다.\n장력을 조정한다.')
        # 고장 유형과의 관계는 사람이 고른다: 「근본 조치」가 미리 골라져 있지 않고, 고르지 않으면 저장 요청이 나가지 않으며 그 칸을 고르라고 한다(C15 — 검토 화면의 관계 칸과 같은 규칙)
        assert page.input_value('#skRel') == ''
        page.click('#skSave')
        page.wait_for_function("document.querySelector('#skMsg').textContent.includes('고장 유형과의 관계를 고르세요')", timeout=5000)
        assert posted == []
        page.select_option('#skRel', 'MITIGATED_BY')
        page.click('#skSave')
        for _ in range(60):
            if posted:
                break
            page.wait_for_timeout(50)
        assert len(posted) == 1 and posted[0]['kind'] == kinds[0][0] == 'work_order', posted                 # 서버가 받는 종류로 나간다
        assert posted[0]['relation'] == 'MITIGATED_BY', posted                                                # 고른 관계 그대로


def test_표_정의에서_열이나_출처_시스템을_바꾸면_다시_읽기_전에는_적재가_꺼지고_그_자리에_까닭이_있다():
    """눌러 보기(2026-11-16): 열 체크를 풀고 [고른 열로 다시 읽기]를 누르지 않은 채 [적재]를 누르면, 아래 표(적재할 입력)가 아직 옛 고르기라 뺀 열이 그대로 적재됐다
    (화면의 체크는 빠져 있는데 지식 지도에는 들어간다). 고르기를 바꾸면 [적재]가 꺼지고 까닭과 할 일이 그 줄에 나오며, 다시 읽으면 서버가 준 새 표로 켜지고,
    그때 [적재]가 보내는 입력에 뺀 열이 없어야 한다."""
    previews, commits = [], []
    cols = ['WO_NO', 'CST_AMT', 'RMK']

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/api/kg/ddl/preview') and method == 'POST':
            body = route.request.post_data_json
            previews.append(body)
            picked = (body.get('selection') or {}).get('T_MNT10', cols)
            return route.fulfill(json={'filename': body['filename'], 'chars': len(body['text']), 'catalog': body['catalog'], 'datasource': 'ds', 'warnings': [], 'systems': [{'id': 'sys:legacy', 'name': 'DB-LEGACY'}],
                                       'existingSystems': [], 'sourceOptions': [{'id': 'ds', 'label': '옛 설비 DB', 'schema': 'legacy'}],
                                       'inputs': [{'id': f'in:{c}', 'name': c, 'typeRef': 'string', 'schema': 'legacy', 'table': 'T_MNT10', 'column': c, 'system': 'sys:legacy', 'variable': f'db_{c}'} for c in picked],
                                       'tables': [{'table': 'T_MNT10', 'comment': '', 'system': 'sys:legacy', 'columns': cols, 'selected': picked}]})
        if path.endswith('/api/kg/ddl/commit') and method == 'POST':
            commits.append(route.request.post_data_json)
            return route.fulfill(json={'systems': 1, 'inputs': len(commits[-1]['inputs'])})
        if path.endswith('/api/kg/ingests'):
            return route.fulfill(json=[])
        if path.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'total': 0, 'next_offset': None})
        if path.endswith('/api/kg/manuals') or path.endswith('/api/kg/skills'):
            return route.fulfill(json=[])
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    with _page(answer) as page:
        open_screen(page, 'knowledge')
        page.click("#docKinds [data-doc-kind='ddl']")
        page.locator("#providedDdl [data-provided='legacy-plant-db.sql']").click()
        page.wait_for_selector('#ddlCommit', timeout=15000)
        assert page.locator('#ddlCommit').is_enabled() and page.inner_text('#ddlMsg').strip() == ''
        page.locator("#ddlResult input[data-col][value='RMK']").uncheck()
        assert page.locator('#ddlCommit').is_disabled()                                              # 다시 읽기 전에는 적재할 수 없다
        said = page.inner_text('#ddlMsg')
        assert page.inner_text('#ddlReplan').strip() in said, said                                       # 까닭 줄이 실제 단추 이름으로 할 일을 말한다
        msg, go = page.locator('#ddlMsg').bounding_box(), page.locator('#ddlCommit').bounding_box()
        assert abs((msg['y'] + msg['height'] / 2) - (go['y'] + go['height'] / 2)) < go['height'], (msg, go)   # 까닭은 꺼진 단추와 같은 줄에
        page.click('#ddlReplan')
        page.wait_for_function("document.querySelector('#ddlCommit') && !document.querySelector('#ddlCommit').disabled && !document.querySelector(\"#ddlResult input[data-col][value='RMK']\").checked", timeout=8000)
        assert previews[-1]['selection'] == {'T_MNT10': ['WO_NO', 'CST_AMT']}
        page.click('#ddlCommit')
        for _ in range(60):
            if commits:
                break
            page.wait_for_timeout(50)
        assert len(commits) == 1 and [i['column'] for i in commits[0]['inputs']] == ['WO_NO', 'CST_AMT'], commits      # 뺀 열은 가지 않는다


def test_AI가_이미_읽은_문서를_다시_열면_아직_읽기_전이라고_말하지_않고_있는_결과와_여는_길을_말한다():
    """눌러 보기(2026-11-16): AI 추출을 시작하고 다른 화면에 다녀오거나 창을 새로 연 뒤 그 문서를 다시 고르면 「아직 AI가 문서를 읽기 전입니다」라고 했다 —
    추출 결과는 접힌 「이 문서의 이전 추출 결과」 안에만 있었다. 서버가 그 문서의 추출 작업을 하나라도 주면 안내가 그 결과가 있다고 말하고 그 접기가 펴져 있어야 하며,
    하나도 없으면(처음 올린 문서) 접기는 접힌 채 「읽기 전」 안내 그대로다."""
    from playwright.sync_api import sync_playwright
    runs = {'items': [], 'next_offset': None}
    docs = _Docs(['HM-8_cooler-fan-manual.md'])

    def answer(route):
        path, method = route.request.url.split('?')[0], route.request.method
        if path.endswith('/extractions') and method == 'GET':
            return route.fulfill(json=runs)
        return docs(route)
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs, answer)
        try:
            row = page.locator("#providedDocs [data-provided='HM-8_cooler-fan-manual.md']")
            row.click()
            page.wait_for_selector('#manualStageNote', timeout=15000)
            page.wait_for_function("document.querySelector('#manualExtractionRuns').options[0].textContent !== '' && document.querySelector('#manualExtractionRuns').options.length >= 1 && !/불러오는/.test(document.querySelector('#manualExtractionRuns').options[0].textContent)", timeout=8000)
            fresh = page.inner_text('#manualStageNote')
            fold_open = lambda: page.evaluate("document.querySelector('#manualExtractionRuns').closest('details').open")
            fold_hidden = lambda: page.evaluate("document.querySelector('#manualExtractionRuns').closest('details').hidden")
            assert '읽기 전' in fresh and not fold_open() and fold_hidden()                            # 추출한 적 없는 문서: 그대로, 열 결과가 없으니 접기도 없다
            page.click('#manualAnother')
            runs['items'] = [{'proc_inst_id': 'inst-doc-hm-8', 'start_date': '2026-11-16T02:00:00Z', 'status': 'COMPLETED'}]
            row.click()
            page.wait_for_function("document.querySelector('#manualExtractionRuns')?.options.length === 2", timeout=15000)
            page.wait_for_function("!/읽기 전/.test(document.querySelector('#manualStageNote').innerText)", timeout=4000)
            said = page.inner_text('#manualStageNote')
            assert page.inner_text('#manualAgentResult').strip() in said and fold_open(), said               # 여는 단추의 이름으로 길을 말하고, 그 단추가 든 접기가 펴져 있다
            # 그 순간의 한 번 보기(is_visible)는 이 파일을 통째로 돌릴 때 세 번에 한 번꼴로 거짓이었다(고치기 전 판에서도 — 접기를 편 직후의 틈). 보일 때까지 3초 기다려 판정한다
            page.locator('#manualAgentResult').wait_for(state='visible', timeout=3000)
            assert page.input_value('#manualExtractionRuns') == 'inst-doc-hm-8' and not fold_hidden()
            # 그 결과를 열면(3단계) 목록의 유일한 결과가 지금 연 결과라 「이전 추출 결과」 접기가 없다
            page.click('#manualAgentResult')
            page.wait_for_selector('#manualReview #manualCommit', timeout=15000)
            page.wait_for_function("document.querySelector('#manualExtractionRuns')?.options.length === 2", timeout=8000)
            assert fold_hidden()
            b.close()
        finally:
            served.close()


# ------------------------------------------------------------------ 마지막 고침(2026-11-16): 문서 검토 칸 · 못 한 까닭의 자리
def _open_review(page, docs, name):
    page.click(f"#providedDocs [data-provided='{name}']")
    page.wait_for_selector('#manualAgentExtract', timeout=15000)
    page.click('#manualAgentExtract')
    page.wait_for_selector('#manualReview #manualCommit', timeout=30000)


def _quoted(proposal, sop, quote=None):
    """그 절차의 단계에 원문 인용을 단다(quote 를 주지 않으면 단계 글 그대로 — AI가 원문 문장을 그대로 뽑은 단계)."""
    for p in proposal['procedures']:
        if p['id'] == sop:
            for st in p['steps']:
                st['anchor'] = {'source_id': proposal['source_id'], 'page': 1, 'start': 0, 'end': len(quote or st['text']), 'quote': quote or st['text'], 'located': 'exact'}
    return proposal


class _QuotedDocs(_Docs):
    """추출 결과의 단계에 원문 인용이 달린 문서 대역: SOP-A-01(고장 조치) · SOP-A-03(참고 절차)은 인용 그대로, SOP-A-02 는 AI가 낸 글이 인용과 다르다."""

    def __call__(self, route):
        path = route.request.url.split('?')[0]
        if '/extractions/' in path and self.polls.get(path.rsplit('/', 1)[1][len('inst-'):], 0) >= 1:
            doc = path.rsplit('/', 1)[1][len('inst-'):]
            name = next(f for f in self.provided if self.doc_of(f) == doc)
            preview = _quoted(_quoted(_quoted(_proposal(doc, name), 'SOP-A-01'), 'SOP-A-03'), 'SOP-A-02', quote='축 씰을 순정품으로 발주한다.')
            return route.fulfill(json={'status': 'DONE', 'instance': 'inst-' + doc, 'segments': [], 'preview': preview})
        return super().__call__(route)


def test_검토에서_고친_이름은_목록_줄과_판_머리가_바로_따라가고_참고_절차의_단계는_읽기_전용이며_까닭을_한_번_말한다():
    """V 8절 6(2026-11-16): 이름 칸을 고쳐도 목록 줄 · 판 머리는 적재 전까지 옛 이름이었고, 참고 절차의 단계 칸은 열려 있지만 고치면 적재 때 서버가
    「참고 단계 내용은 검증한 원문 인용에 그대로 있어야 합니다」로 거절했다. 인용 그대로인 단계는 고칠 것이 없으므로 읽기 전용으로 보이고 그 자리에서 까닭을 한 번 말한다.
    다른 종류에서 고친 단계 글은 참고로 바꾸면 원문으로 돌아가고(잠긴 칸에 고친 글이 남아 거절되지 않게), 적재 요청에는 원문 단계가 간다.
    AI가 낸 글이 인용과 다른 단계는 잠그지 않는다 — 원문 문장으로 고쳐야 적재되는 칸이다(잠그면 고칠 길이 없다). 그때는 무엇으로 고쳐야 하는지 말한다."""
    from playwright.sync_api import sync_playwright
    name = 'HI-01_shift-inspection-supplement.md'
    docs = _QuotedDocs([name])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, name)
            row = "#manualItems [data-item='proc:SOP-A-01'] .row-title"
            head = "#manualPanes [data-pane='proc:SOP-A-01'] .panel-head h2"
            page.click("#manualItems [data-item='proc:SOP-A-01']")
            assert page.inner_text(row) == '벨트 교체'
            page.fill("[data-manual-name='SOP-A-01']", '쿨러 팬 벨트 교체')
            assert page.inner_text(row) == '쿨러 팬 벨트 교체' and page.inner_text(head).startswith('쿨러 팬 벨트 교체'), (page.inner_text(row), page.inner_text(head))
            # 고장 조치(정비 요청)의 단계는 고칠 수 있고 잠금 안내가 없다
            step1 = page.locator("textarea[data-manual-step='SOP-A-01']")
            assert not step1.evaluate('n => n.readOnly') and not page.locator("[data-step-lock='SOP-A-01']").is_visible()
            step1.fill('벨트를 새것으로 교체한다.')
            # 참고 절차: 단계 칸은 읽기 전용이고(쳐도 바뀌지 않는다), 그 구역에 까닭 한 줄이 보인다
            page.click("#manualItems [data-item='proc:SOP-A-03']")
            step3 = page.locator("textarea[data-manual-step='SOP-A-03']")
            lock = page.locator("[data-step-lock='SOP-A-03']")
            assert step3.evaluate('n => n.readOnly') and lock.is_visible()
            step3.click(); page.keyboard.type('고친 글')
            assert step3.input_value() == '상태를 확인한다.'
            why = lock.inner_text()
            assert '원문 그대로' in why and '고칠 수 없습니다' in why and '종류' in why, why
            assert page.locator('#manualPanes [data-step-lock]:visible').count() == 1      # 까닭은 그 판에서 한 번
            assert step3.evaluate("n => getComputedStyle(n).cursor") == 'default' and step3.evaluate("n => getComputedStyle(n).backgroundColor") != step1.evaluate("n => getComputedStyle(n).backgroundColor")
            # AI가 낸 글이 원문 인용과 다른 절차를 참고 절차로 바꾸면: 그 단계는 열려 있고(원문 문장으로 고쳐야 적재된다), 안내가 그렇게 말한다
            page.click("#manualItems [data-item='proc:SOP-A-02']")
            page.select_option("select[data-kind='SOP-A-02']", 'reference')
            step2 = page.locator("textarea[data-manual-step='SOP-A-02']")
            said = page.inner_text("[data-step-lock='SOP-A-02']")
            assert not step2.evaluate('n => n.readOnly') and '원문 문장 그대로 고쳐야 적재됩니다' in said and '고칠 수 없습니다' not in said, said
            step2.fill('축 씰을 순정품으로 발주한다.')
            page.select_option("select[data-kind='SOP-A-02']", 'work_order')                 # 이 절차는 구매 절차로 두고 적재한다
            # 고쳐 둔 고장 조치를 참고 절차로 바꾸면: 단계가 원문으로 돌아가 잠기고, 되돌리면 다시 열린다
            page.click("#manualItems [data-item='proc:SOP-A-01']")
            page.select_option("select[data-kind='SOP-A-01']", 'reference')
            assert step1.evaluate('n => n.readOnly') and step1.input_value() == '벨트를 교체한다.' and page.locator("[data-step-lock='SOP-A-01']").is_visible()
            page.select_option("select[data-kind='SOP-A-01']", 'work_order')
            assert not step1.evaluate('n => n.readOnly') and not page.locator("[data-step-lock='SOP-A-01']").is_visible()
            page.select_option("select[data-kind='SOP-A-01']", 'reference')
            page.select_option("[data-reference-executable='SOP-A-01']", 'false')
            page.check('#manualReviewed')
            page.click('#manualCommit')
            page.wait_for_function("document.querySelector('#manualCommitTitle')?.textContent === '지식 지도에 적재했습니다'", timeout=15000)
            [sent] = docs.commits
            steps = {p['id']: [s['text'] for s in p['steps']] for p in sent['procedures']}
            assert steps['SOP-A-01'] == ['벨트를 교체한다.'] and steps['SOP-A-03'] == ['상태를 확인한다.'] and steps['SOP-A-02'] == ['축 씰을 순정품으로 발주한다.'], steps
            assert next(p['name'] for p in sent['procedures'] if p['id'] == 'SOP-A-01') == '쿨러 팬 벨트 교체'      # 화면에 따라간 이름이 그대로 적재된다
        finally:
            b.close()
            served.close()


def test_검토_체크_없이_적재를_누르면_까닭이_누른_단추의_줄에_나오고_요청은_나가지_않는다():
    """V 8절 7(2026-11-16): 안내가 단추 줄 아래 왼쪽에 떨어져 나왔다(디자인 기준 1-6 — 못 한 까닭은 그 자리에). 잰 관계: 까닭 글이 [검토한 내용 적재]와 같은 줄
    (세로로 겹침)이고 그 왼쪽이며 창 안에 보인다. 체크하고 다시 누르면 까닭이 걷히고 적재가 나간다."""
    from playwright.sync_api import sync_playwright
    name = 'HI-01_shift-inspection-supplement.md'
    docs = _Docs([name])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, name)
            page.click('#manualCommit')
            page.wait_for_function("[...document.querySelectorAll('#manualUpload [role=alert]')].some(n => n.textContent.trim())", timeout=5000)
            got = page.evaluate("""() => {
              const why = [...document.querySelectorAll('#manualUpload [role=alert]')].filter(n => n.textContent.trim() && n.getBoundingClientRect().height > 0);
              const w = why[0].getBoundingClientRect(), c = document.querySelector('#manualCommit').getBoundingClientRect();
              return { n: why.length, text: why[0].textContent.trim(), sameRow: w.top < c.bottom && w.bottom > c.top, left: w.right <= c.left, inView: w.top >= 0 && w.bottom <= innerHeight,
                       tone: why[0].dataset.tone, foot: !!why[0].closest('footer') && why[0].closest('footer') === document.querySelector('#manualCommit').closest('footer') };
            }""")
            assert got == {'n': 1, 'text': '원문과 견준 뒤 검토 완료를 표시하세요.', 'sameRow': True, 'left': True, 'inView': True, 'tone': 'danger', 'foot': True}, got
            assert docs.commits == []
            page.check('#manualReviewed')
            page.click('#manualCommit')
            page.wait_for_function("document.querySelector('#manualCommitTitle')?.textContent === '지식 지도에 적재했습니다'", timeout=15000)
            assert len(docs.commits) == 1 and page.evaluate("document.querySelector('#manualCommitWhy')?.textContent || ''") == ''
        finally:
            b.close()
            served.close()


class _KnowDocs(_Docs):
    """지식 후보가 서로를 가리키는 문서 대역: 원인 「원인 하나」(고장 유형 fm:x)를 증거 「증거 하나」와 절차 SOP-A-01 의 대상 원인이 가리키고, 규칙 하나가
    SOP-A-01 을 조치 후보로 낸다. SOP-A-01 의 정비 요청 값은 그 절차 번호다. 적재가 끝나면 그 문서의 고장 유형이 지금 지식(GET …/manuals/catalog)에 생긴다."""
    held, issues = (), ()
    tweak = None      # 그 시험이 추출 결과(preview)를 더 고치는 함수

    def __call__(self, route):
        path = route.request.url.split('?')[0]
        if '/extractions/' in path and self.polls.get(path.rsplit('/', 1)[1][len('inst-'):], 0) >= 1:
            doc = path.rsplit('/', 1)[1][len('inst-'):]
            name = next(f for f in self.provided if self.doc_of(f) == doc)
            r = _proposal(doc, name)
            r['procedures'][0]['link'].update(addresses=['cause:c1'], actions=[{'action': 'action:work-order', 'value': 'SOP-A-01'}])
            r['knowledge'] = {
                'failure_modes': [{'id': f'fm:{doc}-new', 'name': f'{doc} 새 고장', 'component': 'comp:fan', 'symptoms': [], 'leads_to': [], 'anchor': None}],
                'causes': [{'id': 'cause:c1', 'name': '원인 하나', 'prior': 0.5, 'failure_mode': 'fm:x', 'anchor': None}],
                'evidence': [{'id': 'evd:e1', 'name': '증거 하나', 'cause': 'cause:c1', 'tag': 'TS1', 'aggregate': 'avg', 'window_seconds': 30, 'expect': 'gt', 'threshold': 55, 'anchor': None}],
                'rules': [{'id': 'rule:a-cand', 'table': 'dt:action-candidates', 'effect': 'SELECT', 'outputs': ['SOP-A-01'], 'applies_to': [], 'anchor': None,
                           'annotation': '벨트가 느슨하면 벨트 교체를 후보로 낸다'}]}
            if self.held:      # 이 문서가 다시 정의한, 이미 지식에 있는 항목(서버 manual_knowledge.conflicts 의 꼴)
                r['knowledge_conflicts'] = list(self.held)
                r['validation'] = dict(r['validation'], technical_ready=False, issues=list(self.issues))
            if self.tweak:
                self.tweak(r)
            return route.fulfill(json={'status': 'DONE', 'instance': 'inst-' + doc, 'segments': [], 'preview': r})
        if path.endswith('/api/kg/manuals/commit'):
            body = route.request.post_data_json
            self.failure_modes += [f for f in body['knowledge'].get('failure_modes', []) if f['id'] not in {x['id'] for x in self.failure_modes}]
        return super().__call__(route)


def test_검토본_안의_참조를_한_번에_대조하고_번호를_고치면_가리키는_곳도_따라가며_앞_문서가_넣은_고장_유형을_다음_문서에서_고른다():
    """C2 · C3 · C7 · C15(2026-11-22) — 학생이 검토에서 할 수 있는 선택이 엉뚱한 까닭으로 막히지 않는다.
    ① 원인을 [적재에서 제외]했는데 증거 · 절차가 그 원인을 가리키면, 적재 요청을 보내지 않고 무엇이 가리키는지 이름으로 말한다(전에는 서버가 영문 레이블로 거절).
    ② 규칙이 조치 후보로 내는 절차를 「참고 절차」로 바꾸면 그 규칙을 말한다. ③ AI가 관계를 비운(여기서는 종류를 바꿨다 되돌려 비운) 고장 조치는 「근본 조치」로
    미리 골라지지 않고 고르라고 한다. ④ 절차 번호를 고치면 규칙의 결과 · 정비 요청 값도 새 번호로 실린다. ⑤ 같은 화면에서 앞 문서를 적재하면 그 문서가
    넣은 고장 유형이 다음 문서 검토의 고르기 칸에 바로 있다(전에는 한 번 읽은 목록을 써서 새로 고침해야 보였다)."""
    from playwright.sync_api import sync_playwright
    first, second = 'HI-01_shift-inspection-supplement.md', 'HM-8_cooler-fan-manual.md'
    docs = _KnowDocs([first, second])
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, first)
            why = lambda: page.inner_text('#manualCommitWhy')
            commit = lambda: (page.check('#manualReviewed'), page.click('#manualCommit'))
            # ① 원인 제외 → 가리키는 증거 · 절차를 이름으로
            page.click("[data-review-kind='know']")
            page.click("#manualItems [data-item='know:causes:cause:c1']")
            page.check("[data-know-drop='causes'][value='cause:c1']")
            commit()
            said = why()
            assert '적재에서 제외한 원인 「원인 하나」를 남은 항목이 가리킵니다' in said and '증거 「증거 하나」' in said and '절차 「벨트 교체」(SOP-A-01)의 대상 원인' in said, said
            assert docs.commits == [] and page.get_attribute('#manualUpload', 'data-stage') == '3'
            page.uncheck("[data-know-drop='causes'][value='cause:c1']")
            # ② 후보로 나오는 절차를 참고 절차로
            page.click("[data-review-kind='proc']")
            page.click("#manualItems [data-item='proc:SOP-A-01']")
            page.select_option("select[data-kind='SOP-A-01']", 'reference')
            page.select_option("[data-reference-executable='SOP-A-01']", 'false')
            commit()
            said = why()
            assert '「벨트 교체」(SOP-A-01): 원문만 보관하는 참고 절차로 바꾸면' in said and '규칙 「벨트가 느슨하면 벨트 교체를 후보로 낸다」' in said, said
            assert docs.commits == []
            # ③ 종류를 되돌리면 관계가 비어 있다 — 「근본 조치」로 미리 골라 보내지 않는다
            page.select_option("select[data-kind='SOP-A-01']", 'work_order')
            commit()
            assert '고장 유형과의 관계를 고르세요: SOP-A-01' in why() and docs.commits == []
            page.select_option("select[data-rel='SOP-A-01']", 'MITIGATED_BY')
            # ④ 번호를 회사 번호로
            page.fill("[data-manual-id='SOP-A-01']", 'SOP-B-07')
            commit()
            page.wait_for_function("document.querySelector('#manualCommitTitle')?.textContent === '지식 지도에 적재했습니다'", timeout=15000)
            sent = docs.commits[-1]
            assert [p_['id'] for p_ in sent['procedures']][0] == 'SOP-B-07' and 'SOP-A-01' not in sent['links']
            assert sent['links']['SOP-B-07']['actions'] == [{'action': 'action:work-order', 'value': 'SOP-B-07'}]
            assert sent['knowledge']['rules'][0]['outputs'] == ['SOP-B-07']
            # ⑤ 다음 문서: 앞 문서가 넣은 고장 유형을 고를 수 있다
            page.click('#manualNext')
            _open_review(page, docs, second)
            options = page.locator("select[data-fm='SOP-A-01'] option").all_inner_texts()
            assert f'{docs.doc_of(first)} 새 고장' in options, options
        finally:
            b.close()
            served.close()


def test_이미_지식에_있는_항목을_다시_정의한_제안은_그_정의를_빼면_남은_항목이_있는_항목을_가리킨_채_적재된다():
    """학생 문서의 추출이 이미 지식에 있는 원인(다른 문서가 넣은 같은 id)을 다시 정의하면 그 정의는 덮어쓰기라 적재되지 않는다 — 할 일은 [적재에서 제외]다.
    그런데 화면이 「제외한 원인을 남은 항목이 가리킵니다」로 막아, 그 원인은 둘 수도 뺄 수도 없었다(2026-11-23). 서버가 이미 있다고 알린 항목(knowledge_conflicts)은
    빼도 남은 증거 · 절차가 이미 있는 그 원인을 가리킨다: 요청이 나가고, 요청의 지식에 그 원인 정의는 없으며 증거 · 절차의 대상 원인은 그대로다.
    이 문서만의 항목(같은 문서의 규칙)은 전처럼 이름으로 막는다."""
    from playwright.sync_api import sync_playwright
    name = 'HI-01_shift-inspection-supplement.md'
    docs = _KnowDocs([name])
    docs.held = [{'id': 'cause:c1', 'label': 'Cause', 'owner': 'tenant:other-doc', 'kind': 'other_document', 'owner_name': 'HM-8_cooler-fan-manual.md'}]
    # 서버 적재 전 검사(manual_preflight)가 내는 문장 그대로: 이미 있는 항목, 그리고 지금 지식에 없는 id 를 가리킨 항목
    docs.issues = [
        {'code': 'KNOWLEDGE_OWNERSHIP_CONFLICT', 'sop': 'cause:c1', 'field': 'knowledge_conflicts',
         'message': 'cause:c1: 같은 원인이 이미 지식에 있습니다(다른 문서 「HM-8_cooler-fan-manual.md」가 넣은 것) — 이 문서로 덮어쓰지 않으니 이 항목을 적재에서 제외하세요. '
                    '이 문서의 다른 항목은 이미 있는 그 항목을 가리킵니다'},
        {'code': 'REFERENCE_NOT_FOUND', 'sop': 'evd:e1', 'field': 'cause',
         'message': 'evd:e1: 원인 칸에 적은 cause:valve-stuck이 지금 지식에 없습니다 — 이 문서의 원인 목록에 넣거나 지금 지식에 있는 원인을 고르세요'}]
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, name)
            # 검사 문장: 항목은 이름으로 부르고(내부 id 를 내지 않는다), 가진 문서의 파일 이름은 그대로, 이름을 모르는 id(지금 지식에 없는 것)는 종류 이름으로
            # 바꾸지 않고 그대로 둔다(C12 — 바꾸면 AI가 무엇을 적었는지가 사라진다)
            shown = page.locator('.doc-valid > ul.doc-issues > li').all_inner_texts()
            assert shown[0].startswith('원인 하나: 같은 원인이 이미 지식에 있습니다(다른 문서 「HM-8_cooler-fan-manual.md」가 넣은 것)') and '적재에서 제외하세요' in shown[0], shown
            assert shown[1].startswith('증거 하나: 원인 칸에 적은 cause:valve-stuck이 지금 지식에 없습니다'), shown
            page.click("[data-review-kind='proc']")
            page.click("#manualItems [data-item='proc:SOP-A-01']")
            if not page.input_value("select[data-rel='SOP-A-01']"):
                page.select_option("select[data-rel='SOP-A-01']", 'REMEDIED_BY')
            page.click("[data-review-kind='know']")
            page.click("#manualItems [data-item='know:causes:cause:c1']")
            page.check("[data-know-drop='causes'][value='cause:c1']")
            page.check('#manualReviewed')
            page.click('#manualCommit')
            page.wait_for_function("document.querySelector('#manualCommitTitle')?.textContent === '지식 지도에 적재했습니다'", timeout=15000)
            sent = docs.commits[-1]
            assert sent['knowledge']['causes'] == [] and [e['cause'] for e in sent['knowledge']['evidence']] == ['cause:c1'], sent['knowledge']
            assert sent['links']['SOP-A-01']['addresses'] == ['cause:c1']
        finally:
            b.close()
            served.close()


def test_절차_판은_AI가_정한_세부_동작_값과_대상_원인과_정책을_고칠_칸_없이_한_줄씩_보이고_값이_없는_절차에는_줄이_없다():
    """2026-11-13 03-21 · 사용자 2026-11-23: 세부 동작 값(팬 속도 100 % 등) · 대상 원인 · 정기 정비와 구매 비교 기준은 AI가 낸 값 그대로 적재되는데 화면에는
    「절차 연결 원문」 접기의 JSON 에만 있었다. 고칠 칸은 두지 않고, 절차 판에 접기 밖의 읽기 전용 줄로 보인다. 세부 동작은 지금 지식의 이름과 값으로, 대상 원인은
    이름으로, 이름을 모르는 id 는 그대로(C12), 그 절차의 「원문 수치 확인 필요」 알림은 같은 자리에. 값이 없는 절차(참고 절차)에는 줄도 묶음도 없고, 고칠 칸(input ·
    select)도 없다. 사람이 종류를 「참고 절차」로 바꾸면 적재되지 않을 그 값은 가려진다."""
    from playwright.sync_api import sync_playwright
    name = 'HI-01_shift-inspection-supplement.md'
    docs = _KnowDocs([name])
    docs.more_catalog = {'actions': [{'id': 'action:set-fan', 'name': '팬 속도 설정', 'code': 'FAN_SET', 'kind': 'command', 'param': 'fan_pct', 'min': 0, 'max': 100},
                                     {'id': 'action:work-order', 'name': '정비 작업지시 발행', 'code': 'WO_CREATE', 'kind': 'transaction'},
                                     {'id': 'action:purchase-request', 'name': '구매 요청', 'code': 'PR_CREATE', 'kind': 'transaction'}],
                         'causes': [{'id': 'cause:known', 'name': '지식에 있는 원인', 'failureModes': ['fm:x']}]}
    warn = 'SOP-A-01 · action:set-fan.value=100: 해당 인용에서 같은 수치를 찾지 못했습니다. 원문의 값·단위 환산·계산 근거를 확인하세요'

    def tweak(r):
        r['procedures'][0]['link'].update(
            actions=[{'action': 'action:set-fan', 'value': 100}, {'action': 'action:work-order', 'value': 'SOP-A-01'}, {'action': 'action:valve-open', 'value': 3}],
            addresses=['cause:c1', 'cause:known', 'cause:not-there'],
            maintenance_policy={'version': 1, 'scope': 'bundle', 'stock_effect': 'reserve', 'interval_h': 2000, 'tolerance_pct': 10, 'model_assets': ['HYD-01', 'HYD-02'],
                                'packages': [{'interval_h': 2000, 'sop': 'SOP-A-01', 'name': '기본 점검', 'parts': []}]})
        r['procedures'][1]['link']['purchase_comparison_policy'] = {'version': 1, 'loss_per_failure': 500, 'inspection_threshold': 0.1, 'inspection_cost': 30}
        r['validation'] = dict(r['validation'], source_value_warnings=[warn, 'SOP-A-02 · maintenance_policy.interval_h=1: 다른 절차의 알림'])
    docs.tweak = tweak
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, name)
            facts = lambda sop: page.evaluate("""sop => { const box = document.querySelector(`[data-link-facts="${sop}"]`);
                return box && { rows: Object.fromEntries([...box.querySelectorAll('dl.kv dt')].map(dt => [dt.textContent.trim(), dt.nextElementSibling.textContent.trim()])),
                                warns: [...box.querySelectorAll('[data-link-warn] li')].map(li => li.textContent.trim()), edits: box.querySelectorAll('input, select, textarea').length,
                                inFold: !!box.closest('details'), hidden: box.hidden }; }""", sop)
            one = facts('SOP-A-01')
            assert one['rows'] == {
                '세부 동작': '팬 100 % · 정비 요청 SOP-A-01 · action:valve-open 3',
                '대상 원인': '원인 하나 · 지식에 있는 원인 · cause:not-there',
                '정기 정비 기준': '정비 주기 2,000시간 · 허용 오차 10 % · 적용 설비 HYD-01 · HYD-02 · 여러 대를 묶어 시행 · 부품 출고 예약 · 정비 묶음 2,000시간 기본 점검'}, one
            assert one['warns'] == [warn] and one['edits'] == 0 and one['inFold'] is False and one['hidden'] is False, one
            two = facts('SOP-A-02')
            assert two['rows'] == {'세부 동작': '구매 요청 B사', '구매 비교 기준': '불량 1건 손실 500만 원 · 전수 검사로 바꾸는 불량률 10 % · 전수 검사 비용 30만 원'}, two
            assert two['warns'] == ['SOP-A-02 · maintenance_policy.interval_h=1: 다른 절차의 알림']
            assert facts('SOP-A-03') is None                      # 참고 절차 — 값이 없다: 빈 줄 · 「없음」 자리표를 만들지 않는다
            page.click("[data-review-kind='proc']")
            page.click("#manualItems [data-item='proc:SOP-A-01']")
            assert page.locator("[data-link-facts='SOP-A-01']").is_visible()
            page.select_option("select[data-kind='SOP-A-01']", 'reference')
            assert facts('SOP-A-01')['hidden'] is True
            page.select_option("select[data-kind='SOP-A-01']", 'work_order')
            assert facts('SOP-A-01')['hidden'] is False
        finally:
            b.close()
            served.close()


class _NewItemDocs(_Docs):
    """다른 설비 문서의 대역: 지금 지식에 없는 그 설비의 구성 요소 둘(「흡기 밸브」 — 고장 유형 · 센서가 가리킴, 「구동 모터」 — 아무것도 가리키지 않음) ·
    증상 하나 · 센서 하나(태그 TP2)를 새 항목으로 제안하고, 그 고장 유형 「흡기 밸브 고착」에 SOP-A-01 을 잇는다(서버 manual_knowledge.NEW_KINDS 의 꼴)."""

    def __call__(self, route):
        path = route.request.url.split('?')[0]
        if '/extractions/' in path and self.polls.get(path.rsplit('/', 1)[1][len('inst-'):], 0) >= 1:
            doc = path.rsplit('/', 1)[1][len('inst-'):]
            name = next(f for f in self.provided if self.doc_of(f) == doc)
            r = _proposal(doc, name)
            r['procedures'][0]['link'] = {'failureMode': 'fm:apu-intake-stuck', 'relation': 'REMEDIED_BY', 'kind': 'work_order', 'approver': 'role:operator',
                                          'addresses': ['cause:apu-piston']}
            r['knowledge'] = {
                'failure_modes': [{'id': 'fm:apu-intake-stuck', 'name': '흡기 밸브 고착', 'component': 'comp:apu-intake-valve', 'symptoms': ['sym:apu-tp2-no-rise'], 'leads_to': [], 'anchor': None}],
                'causes': [{'id': 'cause:apu-piston', 'name': '흡기 밸브 피스톤 오염', 'prior': 0.7, 'failure_mode': 'fm:apu-intake-stuck', 'anchor': None}],
                'evidence': [{'id': 'evd:apu-tp2', 'name': '압축기 압력 기동 기준 미달', 'cause': 'cause:apu-piston', 'tag': 'TP2', 'aggregate': 'max', 'window_seconds': 600,
                              'expect': 'lt', 'threshold': 8.2, 'anchor': None}],
                'components': [{'id': 'comp:apu-intake-valve', 'name': '흡기 밸브', 'aliases': [], 'anchor': None},
                               {'id': 'comp:apu-motor', 'name': '구동 모터', 'aliases': [], 'anchor': None}],
                'symptoms': [{'id': 'sym:apu-tp2-no-rise', 'name': '압축기 압력 오르지 않음', 'sensors': ['sen:apu-tp2'], 'anchor': None}],
                'sensors': [{'id': 'sen:apu-tp2', 'name': '압축기 압력', 'tag': 'TP2', 'unit': 'bar', 'component': 'comp:apu-intake-valve', 'anchor': None}]}
            return route.fulfill(json={'status': 'DONE', 'instance': 'inst-' + doc, 'segments': [], 'preview': r})
        return super().__call__(route)


def test_새_항목_제안은_사람이_항목마다_넣기_제외를_골라야_적재되고_제외한_항목을_남은_항목이_가리키면_이름으로_막힌다():
    """다른 설비 문서(학생 PBL)의 새 항목(구성 요소 · 증상 · 센서)은 지식 후보처럼 미리 넣어 두지 않는다 — 몰래 만들지 않는다.
    ① 검토 화면에 「새 항목 제안」 묶음이 생기고 줄마다 「넣기 · 제외 고르기」가 붙는다 ② 하나도 고르지 않고 적재를 누르면 요청을 보내지 않고 처음 고를 항목을 연다
    ③ 고장 유형 · 센서가 가리키는 구성 요소를 제외하면 무엇이 가리키는지 이름으로 말한다 ④ 넣기를 고른 항목만 approved 표시와 함께 적재 요청에 실리고,
    제외한 항목(아무것도 가리키지 않는 구동 모터)은 빠진다 ⑤ 한 번에 적재(사람이 고르지 않는 길)는 그런 문서를 적재하지 않고 검토 필요로 멈춘다."""
    from playwright.sync_api import sync_playwright
    name, other = 'HI-01_shift-inspection-supplement.md', 'HM-8_cooler-fan-manual.md'
    docs = _NewItemDocs([name, other])

    def pick(group, nid, choice):
        """학생처럼: 목록의 그 줄을 눌러 판을 열고 넣기 · 제외를 고른다."""
        page.click(f"#manualItems [data-item='new:{group}:{nid}']")
        page.check(f"[data-new-pick='{group}'][value='{nid}'][data-choice='{choice}']")
    with sync_playwright() as p:
        served, b, page = _open_docs(p, docs)
        try:
            _open_review(page, docs, name)
            commit = lambda: (page.check('#manualReviewed'), page.click('#manualCommit'))      # noqa: E731
            why = lambda: page.inner_text('#manualCommitWhy')      # noqa: E731
            # ① 묶음과 줄
            assert '새 항목 제안 4개' in page.inner_text('#manualReview .result-main')
            page.click("[data-review-kind='new']")
            rows = page.locator("#manualItems [data-group='new']")
            assert rows.count() == 4 and all('넣기 · 제외 고르기' in t for t in rows.all_inner_texts()), rows.all_inner_texts()
            assert '새 센서 · 태그 TP2 · bar · 흡기 밸브' in page.inner_text("#manualItems [data-item='new:sensors:sen:apu-tp2']")
            # ② 고르지 않고 적재
            commit()
            assert why() == '새 항목 제안 4개는 넣을지 사람이 하나씩 골라야 적재합니다 — 새 구성 요소 「흡기 밸브」부터 「넣기」 또는 「제외」를 고르세요.', why()
            assert docs.commits == [] and page.locator("#manualPanes [data-pane='new:components:comp:apu-intake-valve']").is_visible()
            # ③ 가리키는 항목이 남은 구성 요소를 제외
            pick('components', 'comp:apu-intake-valve', 'drop')
            pick('components', 'comp:apu-motor', 'drop')
            pick('symptoms', 'sym:apu-tp2-no-rise', 'keep')
            pick('sensors', 'sen:apu-tp2', 'keep')
            assert page.inner_text("#manualItems [data-item='new:components:comp:apu-motor'] [data-item-tag]") == '제외'
            commit()
            said = why()
            assert said.startswith('적재에서 제외한 새 구성 요소 「흡기 밸브」를 남은 항목이 가리킵니다 — 고장 유형 「흡기 밸브 고착」의 구성 요소 · 센서 「압축기 압력」의 구성 요소.') \
                and '이 새 항목의 「넣기」를 고르세요.' in said, said
            assert docs.commits == []
            # ④ 넣기를 고른 것만 실린다
            pick('components', 'comp:apu-intake-valve', 'keep')
            commit()
            page.wait_for_function("document.querySelector('#manualCommitTitle')?.textContent === '지식 지도에 적재했습니다'", timeout=15000)
            [sent] = docs.commits
            k = sent['knowledge']
            assert [(c['id'], c['approved']) for c in k['components']] == [('comp:apu-intake-valve', True)]
            assert [(s['id'], s['approved']) for s in k['symptoms']] == [('sym:apu-tp2-no-rise', True)] and [s['approved'] for s in k['sensors']] == [True]
            assert all('approved' not in x for g in ('failure_modes', 'causes', 'evidence') for x in k[g])      # 지식 후보는 그대로(넣기 표시는 새 항목만)
            # ⑤ 한 번에 적재는 새 항목이 있는 문서를 멈춘다
            page.click('#manualNext')
            page.wait_for_selector(f"#providedDocs [data-provided='{other}']:not([disabled])", timeout=5000)
            docs.polls.clear()
            page.locator(f"#providedDocs [data-batch-pick='{other}']").check(timeout=5000)
            page.click('#manualBatchRun')
            page.wait_for_selector('#manualBatchClose', timeout=30000)
            done = page.inner_text('#manualBatch')
            assert '검토 필요 — 새 항목 제안 4개는 넣을지 사람이 하나씩 골라야 적재합니다' in done and len(docs.commits) == 1, done
        finally:
            b.close()
            served.close()
