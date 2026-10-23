"""P13 (2026-10-23 검수): 글자 없는 페이지가 한 장이라도 있는 PDF는 OCR_REQUIRED가 되어 [에이전트 추출 요청] · [적재]가 모두 꺼지고
끝낼 길이 없었다. 이제 모든 페이지에 글자가 없을 때만 OCR_REQUIRED이고, 일부만 없으면 그 페이지만 표시(text_missing_pages ·
경고 · 페이지 검토 기록)한 채 나머지 페이지로 추출 · 적재한다. 화면은 status가 READY일 때 두 버튼을 켠다(hitl.js)."""
import io
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from pypdf import PdfReader, PdfWriter

from procsvc import manual_extraction as extraction, manual_review
from procsvc.manual_sources import ManualSources
from test_instances import rt  # noqa: F401 — fixture

PDF_FIXTURE = Path(__file__).parent / 'fixtures/manuals/two-page-manual.pdf'


def _pdf(*pages):
    writer = PdfWriter()
    for page in pages:
        if page == 'blank':
            writer.add_blank_page(width=595, height=842)
        else:
            writer.add_page(PdfReader(PDF_FIXTURE).pages[page])
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()


@pytest.fixture
def store(tmp_path):
    return ManualSources(tmp_path / 'manuals.sqlite')


def _proposal(source):
    sid = source['source_id']
    q = lambda text: dict(source_id=sid, page=1, quote=text)       # noqa: E731
    return dict(source_id=sid, warnings=[],
                sections=[dict(ref='HM-8.1', title='Fan inspection', excerpt='', anchor=q('Section HM-8.1 - Fan inspection'))],
                procedures=[dict(id='SOP-HM8-1', name='Fan inspection', section='HM-8.1', anchor=q('Section HM-8.1 - Fan inspection'),
                                 steps=[dict(order=1, text='Stop the equipment before inspection.', manual='HM-8.1',
                                             anchor=q('1. Stop the equipment before inspection.')),
                                        dict(order=2, text='Inspect the fan belt.', manual='HM-8.1', anchor=q('2. Inspect the fan belt.'))])],
                page_reviews=[dict(page=1, note='HM-8.1 절차'), dict(page=2, note='글자가 없는 페이지')])


def test_some_pages_without_text_mark_those_pages_and_leave_the_document_extractable(store):
    a = store.save('hyd', 'mixed.pdf', _pdf(0, 'blank', 1, 'blank'))
    assert a['status'] == 'READY' and a['text_missing_pages'] == [2, 4]
    assert a['warnings'] == [a['warnings'][0]] and '페이지 2, 4' in a['warnings'][0] and '원문 PDF에서' in a['warnings'][0]
    listed = store.list('hyd')['items'][0]
    assert listed['status'] == 'READY' and listed['text_missing_pages'] == [2, 4]


def test_a_document_with_no_text_at_all_still_needs_ocr_and_says_how(store, rt):  # noqa: F811
    runtime, _ = rt
    a = store.save('hyd', 'scan.pdf', _pdf('blank', 'blank'))
    assert a['status'] == 'OCR_REQUIRED' and a['text_missing_pages'] == [1, 2] and '글자 인식(OCR)한 PDF로 다시 올리세요' in a['warnings'][0]
    with pytest.raises(ValueError, match='글자 인식'):
        extraction.start(runtime, a, str(uuid4()))
    with pytest.raises(ValueError, match='글자 인식'):
        manual_review.validate(store, 'hyd', dict(reviewed=True, by='검토자', source_id=a['source_id'], batch=str(uuid4()),
                                                   sections=[{}], procedures=[{}]))


def test_an_archive_stored_as_ocr_required_under_the_old_rule_reads_ready_with_hashes_intact(store):
    a = store.save('hyd', 'old.pdf', _pdf(0, 'blank'))
    with sqlite3.connect(store.path) as db:      # what the earlier rule wrote for the same bytes
        payload = json.loads(db.execute('SELECT extraction FROM manual_sources').fetchone()[0])
        payload.update(status='OCR_REQUIRED', warnings=['텍스트가 없는 페이지 2: OCR 또는 빈 페이지 여부 검토 필요'])
        db.execute('UPDATE manual_sources SET extraction=?', (json.dumps(payload, ensure_ascii=False),))
    b = store.get('hyd', a['source_id'])
    assert b['status'] == 'READY' and b['text_missing_pages'] == [2] and b['warnings'] == a['warnings']
    assert store.list('hyd')['items'][0]['status'] == 'READY'


def test_a_document_whose_pages_all_have_text_reads_exactly_as_before(store):
    a = store.save('hyd', 'full.pdf', PDF_FIXTURE.read_bytes())
    assert a['status'] == 'READY' and 'text_missing_pages' not in a and a['warnings'] == []   # pinned runs still compare equal


def test_extraction_preview_and_load_go_ahead_with_the_text_less_page_marked(store, rt):  # noqa: F811
    runtime, _ = rt
    source = store.save('hyd', 'mixed.pdf', _pdf(0, 'blank'))
    inst = extraction.start(runtime, source, str(uuid4()))                 # [에이전트 추출 요청] no longer refused
    assert inst and extraction.engine.variables(inst)['manual_source'] == source
    checked = extraction.validate_proposal(source, _proposal(source))
    preview = extraction._preview(source, checked, None, dict(instance=inst['proc_inst_id']))
    assert preview['status'] == 'READY' and preview['text_missing_pages'] == [2]
    assert preview['warnings'][0].startswith('텍스트가 없는 페이지 2')
    notes = {r['page']: r['note'] for r in preview['page_reviews']}
    assert notes[2].startswith(extraction.TEXT_MISSING_NOTE) and notes[1] == 'HM-8.1 절차'
    body = dict(reviewed=True, by='검토자', source_id=source['source_id'], batch=preview['batch'],
                sections=preview['sections'], procedures=preview['procedures'],
                links={'SOP-HM8-1': dict(failureMode='fm:belt-slip', relation='REMEDIED_BY', kind='work_order')})
    plan = manual_review.validate(store, 'hyd', body)                       # [검토한 내용 적재] passes the server check
    assert [p['id'] for p in plan['procedures']] == ['SOP-HM8-1'] and all(st['anchor']['page'] == 1 for st in plan['procedures'][0]['steps'])
    structured = manual_review.proposal(source)                            # the structured-parser preview carries the mark too
    assert structured['status'] == 'READY' and structured['text_missing_pages'] == [2]
