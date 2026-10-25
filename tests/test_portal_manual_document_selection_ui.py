"""Isolated Chromium checks of production manual selection; no live services."""
from test_portal_remaining_ui import page, WWW


def setup_selection(page):
    page.route('**/api/kg/manuals', lambda r: r.fulfill(json=[]))
    source = (WWW / 'hitl.js').read_text(encoding='utf8')
    source = source.replace('const instanceMode =',
        'window.manualSelectionTest={select:selectManualDocument,update:updateManualDocuments,render:renderPreview,H}; const instanceMode =', 1)
    page.add_script_tag(content=source)
    page.evaluate("selectTab('knowledge')")
    page.locator('#manualHistory h2').wait_for()


def test_named_documents_deduplicate_revisions_and_preserve_exact_ids(page):
    setup_selection(page)
    page.evaluate("""manualSelectionTest.update([
      {document_id:'opaque:one',filename:'original.md',current:false},
      {document_id:'opaque:one',filename:'current.md',current:true},
      {document_id:'opaque:two',filename:'foreign raw name.md',current:true}]);""")
    options = page.locator('#manualDocumentId option')
    assert options.count() == 3
    assert 'opaque:' not in options.all_text_contents().__str__()
    page.locator('#manualDocumentId').select_option('opaque:one')
    assert page.locator('#manualDocumentId').input_value() == 'opaque:one'
    assert page.locator('#manualDocumentId option:checked').inner_text() == 'current.md · 문서 개정'


def test_unknown_selection_never_falls_back_to_new_or_leaks_id(page):
    setup_selection(page)
    page.evaluate("manualSelectionTest.select('unknown-private-id');manualSelectionTest.update([])")
    assert page.locator('#manualDocumentId').input_value() == 'unknown-private-id'
    assert '확인할 수 없습니다' in page.locator('#manualDocumentId option:checked').inner_text()
    assert 'unknown-private-id' not in page.locator('#manualDocumentId').inner_text()


def test_source_before_history_keeps_filename_identity_and_draft(page):
    setup_selection(page)
    page.evaluate("""manualSelectionTest.H.preview={document_id:'source-only',filename:'原文.md',draft:'keep'};
      manualSelectionTest.select('source-only','原文.md');manualSelectionTest.update([]);""")
    assert page.locator('#manualDocumentId').input_value() == 'source-only'
    assert '原文.md' in page.locator('#manualDocumentId option:checked').inner_text()
    assert page.evaluate('manualSelectionTest.H.preview.draft') == 'keep'


def test_history_failure_retains_selection_and_draft(page):
    setup_selection(page)
    page.evaluate("""manualSelectionTest.update([{document_id:'keep-id',filename:'kept.md',current:true}]);
      manualSelectionTest.select('keep-id');manualSelectionTest.H.preview={draft:'keep'};""")
    page.route('**/api/kg/manuals', lambda r: r.fulfill(status=503, json={'detail':'unavailable'}))
    page.evaluate("selectTab('knowledge')")
    page.locator('#manualHistory').get_by_text('등록 이력을 읽지 못했습니다', exact=False).wait_for()
    assert page.locator('#manualDocumentId').input_value() == 'keep-id'
    assert 'kept.md' in page.locator('#manualDocumentId option:checked').inner_text()
    assert page.evaluate('manualSelectionTest.H.preview.draft') == 'keep'


def test_duplicate_filenames_keep_distinct_documents_with_actual_times(page):
    setup_selection(page)
    page.evaluate("""manualSelectionTest.update([
      {document_id:'first',filename:'same.md',current:true,t:'2026-10-12T01:00:00Z'},
      {document_id:'second',filename:'same.md',current:true,t:'2026-10-12T02:00:00Z'}]);""")
    labels = page.locator('#manualDocumentId option').all_text_contents()
    assert len(labels) == 3 and labels[1] != labels[2]
    assert page.locator('#manualDocumentId option').evaluate_all('(xs)=>xs.map(x=>x.value)') == ['', 'first', 'second']


def test_historical_only_documents_stay_out_of_primary_choices_but_explicit_revision_survives(page):
    setup_selection(page)
    history = [{'document_id':'active', 'filename':'current.md','current':True,'status':'ACTIVE'},
               {'document_id':'old-only', 'filename':'preserved-original.md','current':False,'status':'ROLLED_BACK'}]
    page.evaluate('rows=>manualSelectionTest.update(rows)', history)
    assert page.locator('#manualDocumentId option').evaluate_all('(xs)=>xs.map(x=>x.value)') == ['', 'active']
    page.evaluate("manualSelectionTest.select('old-only')")
    assert page.locator('#manualDocumentId').input_value() == 'old-only'
    assert 'preserved-original.md' in page.locator('#manualDocumentId option:checked').inner_text()
    page.evaluate('rows=>manualSelectionTest.update(rows)', history)
    assert page.locator('#manualDocumentId').input_value() == 'old-only'
    assert 'preserved-original.md' in page.locator('#manualDocumentId option:checked').inner_text()


def test_upload_selects_generated_identity_locks_review_and_next_file_unlocks(page):
    setup_selection(page)
    calls = []
    preview = {'document_id':'generated-exact-id','source_id':'saved-source','filename':'raw.md',
               'chars':4,'sections':[],'procedures':[],'warnings':[], 'draft':'untouched'}
    def upload(route):
        calls.append(route.request.post_data_json)
        route.fulfill(json=preview)
    page.route('**/api/kg/manuals/preview', upload)
    page.route('**/api/kg/catalog', lambda r: r.fulfill(json={'roles':[], 'failureModes':[]}))
    page.route('**/api/kg/manuals/sources?*', lambda r: r.fulfill(json={'items':[], 'total':0}))
    page.locator('#manualFile').set_input_files({'name':'raw.md','mimeType':'text/plain','buffer':b'body'})
    page.locator('#manualPreview').click()
    page.wait_for_function("document.querySelector('#manualDocumentId').value==='generated-exact-id'")
    assert calls[0]['document_id'] is None
    assert page.locator('#manualDocumentId').is_disabled()
    assert '검토 중인 원문' in page.locator('#manualDocumentId option:checked').inner_text()
    assert page.evaluate('manualSelectionTest.H.preview.document_id') == 'generated-exact-id'
    assert page.evaluate('manualSelectionTest.H.preview.draft') == 'untouched'
    page.locator('#manualFile').set_input_files({'name':'next.md','mimeType':'text/plain','buffer':b'next'})
    assert page.locator('#manualDocumentId').is_enabled()
    assert page.evaluate('manualSelectionTest.H.preview') is None
    page.locator('#manualPreview').click()
    page.wait_for_function("manualSelectionTest.H.preview !== null")
    assert calls[1]['document_id'] == 'generated-exact-id'
    assert page.locator('#manualDocumentId').is_disabled()


def test_extracted_knowledge_is_reviewable_and_excluded_items_are_not_committed(page):
    """2026-10-25 수업 한 바퀴: 검토 화면에 AI가 뽑은 원인 · 증거 · 규칙이 없어 학생이 원문과 대조해 뺄 수 없었다."""
    setup_selection(page)
    sent = {}
    page.route('**/api/kg/manuals/commit', lambda r: (sent.update(body=r.request.post_data_json), r.fulfill(json={'batch': 'b1', 'procedures': 1, 'steps': 1, 'skills': {}, 'candidate_activation': {}}))[1])
    page.route('**/extractions**', lambda r: r.fulfill(json={'items': [], 'next_offset': None}))
    anchor = {'source_id': 's1', 'page': 1, 'start': 0, 'end': 4, 'quote': '원문 문장'}
    page.evaluate("""a => { manualSelectionTest.H.preview = {filename:'HM-8.md', chars:10, status:'READY', source_id:'s1', document_id:'d1', batch:'b1', warnings:[],
      sections:[{ref:'HM-8.5', title:'즉시 완화', excerpt:'x', anchor:a}],
      procedures:[{id:'SOP-COOL-11', name:'팬 최대 운전', section:'HM-8.5', anchor:a, steps:[{order:1, text:'팬 속도를 100 %로 올린다.', manual:'HM-8.5', anchor:a}],
                   link:{failureMode:'fm:cooler-cooling-loss', relation:'MITIGATED_BY', kind:'control', approver:'role:operator', actions:[]}}],
      knowledge:{failure_modes:[{id:'fm:cooler-cooling-loss', name:'쿨러 냉각 성능 상실', symptoms:[], anchor:a}],
                 causes:[{id:'cause:cooler-fin-fouling', name:'쿨러 핀 오염', prior:0.6, failure_mode:'fm:cooler-cooling-loss', anchor:a}],
                 rules:[{id:'rule:remote-auto-only', table:'dt:compliance', effect:'EXCLUDE', tests:[], annotation:'REMOTE_AUTO가 아니면 원격 조치를 쓰지 않는다', anchor:a},
                        {id:'rule:wrong', table:'dt:compliance', effect:'PENALTY', penalty:99, tests:[], annotation:'원문에 없는 감점', anchor:a}]}};
      manualSelectionTest.render(); }""", anchor)
    box = page.locator('#manualResult')
    assert '추출한 지식 후보' in box.inner_text() and 'REMOTE_AUTO가 아니면 원격 조치를 쓰지 않는다' in box.inner_text() and '쿨러 핀 오염' in box.inner_text()
    page.locator("[data-know-drop='rules'][value='rule:wrong']").check()
    assert not page.locator('#manualReviewed').is_checked()
    page.locator('#manualBy').fill('학생')
    page.locator('#manualReviewed').check()
    page.locator('#manualCommit').click()
    page.wait_for_function("() => document.querySelector('#manualMsg').textContent.length > 0")
    rules = [x['id'] for x in sent['body']['knowledge']['rules']]
    assert rules == ['rule:remote-auto-only'] and [c['id'] for c in sent['body']['knowledge']['causes']] == ['cause:cooler-fin-fouling']


def test_a_new_extraction_request_is_the_selected_run_not_the_one_already_opened(page):
    """결과를 연 문서(preview.extraction = 옛 작업)에서 다시 추출을 요청하면, 목록은 방금 접수한 작업을 골라야 한다."""
    setup_selection(page)
    page.route('**/extractions?offset=0', lambda r: r.fulfill(json={'items': [
        {'proc_inst_id': 'run-new', 'start_date': '2026-10-25T10:00:00Z', 'status': 'RUNNING'},
        {'proc_inst_id': 'run-old', 'start_date': '2026-10-25T09:00:00Z', 'status': 'COMPLETED'}], 'next_offset': None}))
    page.evaluate("""() => { sessionStorage.setItem('hyd.manual.extraction.s1', JSON.stringify({request_id: 'x', instance: 'run-new'}));
      const a = {source_id:'s1', page:1, start:0, end:1, quote:'q'};
      manualSelectionTest.H.preview = {filename:'HM-8.md', chars:1, status:'READY', source_id:'s1', document_id:'d1', batch:'b1', warnings:[],
        extraction:{instance:'run-old'}, sections:[{ref:'A', title:'t', excerpt:'', anchor:a}], procedures:[], knowledge:{}};
      manualSelectionTest.render(); }""")
    page.wait_for_function("() => document.querySelector('#manualExtractionRuns').options.length > 2")
    assert page.locator('#manualExtractionRuns').input_value() == 'run-new'
