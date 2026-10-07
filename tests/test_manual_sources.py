"""Source identity, durable originals, exact citations, and failed writes."""
import json
import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from procsvc import manual_sources as module
from procsvc.manual_sources import ManualSources

PDF_FIXTURE = Path(__file__).parent / 'fixtures/manuals/two-page-manual.pdf'


@pytest.fixture
def store(tmp_path):
    return ManualSources(tmp_path / 'manuals.sqlite')


TEXT = '# 정비 문서\r\nHM-8.1 팬\r\n1. 정지한다.\r\n2. 벨트를 확인한다.\r\n'


def upload(store, **kwargs):
    return store.save('hyd', '정비.md', TEXT.encode(), **kwargs)


def test_same_filename_and_sections_are_different_logical_documents(store):
    a, b = upload(store), upload(store)
    assert a['document_id'] != b['document_id'] and a['source_id'] != b['source_id']
    assert a['sha256'] == b['sha256']


def test_original_extraction_and_line_endings_survive_new_store(store):
    a = upload(store)
    reopened = ManualSources(store.path)
    assert reopened.get('hyd', a['source_id'])['pages'][0]['text'] == TEXT
    assert reopened.original('hyd', a['source_id']) == TEXT.encode()


def test_revision_is_explicit_and_old_version_is_unchanged(store):
    a = upload(store)
    b = store.save('hyd', '수정.md', TEXT.replace('팬', '펌프').encode(), document_id=a['document_id'])
    assert a['document_id'] == b['document_id'] and a['source_id'] != b['source_id']
    assert store.original('hyd', a['source_id']) == TEXT.encode()
    assert '펌프' in store.get('hyd', b['source_id'])['pages'][0]['text']


def test_retry_keeps_original_name_and_extraction_after_parser_changes(store, monkeypatch):
    a = upload(store)
    monkeypatch.setattr(module, 'extract', lambda *_: pytest.fail('must reuse saved extraction'))
    b = store.save('hyd', 'renamed.md', TEXT.encode(), document_id=a['document_id'])
    assert b == a | {'replayed': True}


def test_revision_and_read_cannot_cross_tenants(store):
    a = upload(store)
    for call in (lambda: store.get('other', a['source_id']),
                 lambda: store.original('other', a['source_id']),
                 lambda: store.save('other', 'x.md', TEXT.encode(), document_id=a['document_id'])):
        with pytest.raises(KeyError):
            call()


def test_full_long_text_is_preserved_instead_of_excerpt_truncation(store):
    text = '본문과 주의사항\n' * 1000
    a = store.save('hyd', 'long.txt', text.encode('cp949'))
    assert a['pages'][0]['text'] == text and a['extractor'] == 'text:cp949:v1'


@pytest.mark.parametrize('raw,name', [(b'\xff', 'x.txt'), (b'\x00abc', 'x.txt'),
                                     (b'', 'x.md'), (b'abc', 'x.pdf'), (b'abc', 'x.exe')])
def test_unreadable_input_has_no_partial_archive(store, raw, name):
    with pytest.raises(ValueError):
        store.save('hyd', name, raw)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM manual_documents').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM manual_sources').fetchone()[0] == 0


def test_exact_anchor_and_fabricated_quote_or_position(store):
    a = upload(store)
    start = TEXT.index('벨트')
    anchor = {'source_id': a['source_id'], 'page': 1, 'start': start, 'end': start + 2, 'quote': '벨트'}
    assert store.validate_anchor('hyd', anchor) == anchor
    for bad in ({'quote': '펌프'}, {'start': start + 1}, {'page': 2}, {'end': True}, {'start': -1}):
        with pytest.raises(ValueError):
            store.validate_anchor('hyd', anchor | bad)


def test_concurrent_same_revision_is_single_saved_version(store):
    a = upload(store)
    def save(_):
        return ManualSources(store.path).save('hyd', 'v2.md', b'new version', document_id=a['document_id'])
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(save, range(12)))
    assert len({row['source_id'] for row in rows}) == 1
    assert sum(not row['replayed'] for row in rows) == 1
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM manual_sources').fetchone()[0] == 2


def test_source_insert_failure_rolls_back_document_as_well(store):
    with sqlite3.connect(store.path) as db:
        db.execute("CREATE TRIGGER fail BEFORE INSERT ON manual_sources BEGIN SELECT RAISE(ABORT,'disk fault'); END")
    with pytest.raises(sqlite3.IntegrityError, match='disk fault'):
        upload(store)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM manual_documents').fetchone()[0] == 0


def test_corrupted_original_is_not_returned_as_verified_source(store):
    a = upload(store)
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE manual_sources SET original=?', (b'corrupt',))
    with pytest.raises(ValueError, match='해시'):
        store.get('hyd', a['source_id'])


def test_corrupted_extraction_cannot_validate_a_quote(store):
    a = upload(store)
    with sqlite3.connect(store.path) as db:
        payload = json.loads(db.execute('SELECT extraction FROM manual_sources').fetchone()[0])
        payload['pages'][0]['text'] = '위조 인용'
        db.execute('UPDATE manual_sources SET extraction=?', (json.dumps(payload),))
    with pytest.raises(ValueError, match='추출 텍스트 해시'):
        store.validate_anchor('hyd', {'source_id': a['source_id'], 'page': 1,
                                     'start': 0, 'end': 2, 'quote': '위조'})


def test_actual_pdf_keeps_page_boundaries_and_original_bytes(store):
    raw = PDF_FIXTURE.read_bytes()
    a = store.save('hyd', 'manual.pdf', raw)
    assert a['status'] == 'READY' and len(a['pages']) == 2
    assert 'Fan inspection' in a['pages'][0]['text']
    assert 'Pump inspection' in a['pages'][1]['text']
    text = a['pages'][1]['text']
    start = text.index('pump seal')
    anchor = dict(source_id=a['source_id'], page=2, start=start, end=start+9, quote='pump seal')
    assert store.validate_anchor('hyd', anchor) == anchor
    assert store.original('hyd', a['source_id']) == raw
    with pytest.raises(ValueError):
        store.validate_anchor('hyd', anchor | {'page': 1})


def test_partial_pdf_with_unreadable_page_never_claims_complete_extraction(store):
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    writer.add_page(PdfReader(PDF_FIXTURE).pages[0])
    writer.add_blank_page(width=595, height=842)
    stream = io.BytesIO()
    writer.write(stream)
    a = store.save('hyd', 'partial.pdf', stream.getvalue())
    assert a['status'] == 'OCR_REQUIRED' and a['pages'][1]['text'] == ''
    assert '2' in a['warnings'][0] and len(a['pages']) == 2


def test_encrypted_pdf_is_rejected_without_partial_document(store):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt('not-a-real-secret')
    stream = io.BytesIO()
    writer.write(stream)
    with pytest.raises(ValueError, match='암호화'):
        store.save('hyd', 'encrypted.pdf', stream.getvalue())
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM manual_documents').fetchone()[0] == 0


def test_pdf_symbol_font_bullets_become_visible_bullets_at_archive_time():
    """A094 (real Daikin manual): private-use glyphs (Wingdings bullets) are invisible and vanish from agent quotes."""
    from procsvc.manual_sources import normalize_glyphs
    raw = '1.3.1 General Precautions \n DANGER \n Ensure that transportation is safe\n second item'
    out = normalize_glyphs(raw)
    assert '' not in out and '' not in out and out.count('•') == 2
    assert out.startswith('1.3.1 General Precautions \n DANGER \n• Ensure')
    assert normalize_glyphs('한글 • ASCII 그대로') == '한글 • ASCII 그대로'
