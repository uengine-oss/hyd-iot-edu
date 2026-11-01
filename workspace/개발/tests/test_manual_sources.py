"""문서 보관소(procsvc/manual_sources.py) — 제공 문서 넷은 원문 바이트 그대로 보관되고, 추출한 글이 원문과 같으며, 수업 규칙이 아는 그 문서다."""
import hashlib

import pytest

from procsvc import course_policy as cp
from procsvc.manual_sources import ManualSources

from conftest import ROOT
SAMPLES = ROOT / 'it' / 'portal' / 'www' / 'samples'
PROVIDED = sorted(p for p in SAMPLES.glob('*.md') if hashlib.sha256(p.read_bytes()).hexdigest() in cp.DOCUMENTS)


def test_포털의_제공_문서는_수업_규칙이_아는_넷이다():
    assert [p.stem.split('_')[0] for p in PROVIDED] == ['HI-01', 'HM-8', 'PM-02', 'PR-07']


@pytest.mark.parametrize('path', PROVIDED, ids=[p.stem.split('_')[0] for p in PROVIDED])
def test_제공_문서는_원문_그대로_보관되고_글이_원문과_같이_추출된다(tmp_path, path):
    raw = path.read_bytes()
    archive = ManualSources(tmp_path / 'manuals.sqlite3')
    saved = archive.save('hyd', path.name, raw)
    again = archive.get('hyd', saved['source_id'])
    assert (saved['sha256'], again['sha256']) == (hashlib.sha256(raw).hexdigest(),) * 2
    assert archive.original('hyd', saved['source_id']) == raw
    assert ''.join(page['text'] for page in again['pages']) == raw.decode('utf-8-sig')


@pytest.mark.parametrize('raw', [b'%PDF-1.4 garbage', b'%PDF-', b'%PDF-1.7' + bytes([10]) + b'1 0 obj<<>>endobj' + bytes([10]) + b'trailer<</Root 1 0 R>>'],
                         ids=['머리 뒤 쓰레기', '머리만', '끝이 없는 PDF'])
def test_깨진_PDF는_학생이_할_일을_말하는_ValueError로_거절한다(tmp_path, raw):
    """P2-10: pypdf 오류가 그대로 올라가 포털에 「Internal Server Error」만 보였다."""
    archive = ManualSources(tmp_path / 'manuals.sqlite3')
    with pytest.raises(ValueError, match='PDF를 읽을 수 없습니다.*다시 받아'):
        archive.save('hyd', 'manual.pdf', raw)
    assert archive.list('hyd')['total'] == 0


def test_어떤_꼴로_깨진_PDF든_학생_문장의_거절이고_다른_예외로_새지_않는다():
    """FB 검증 P2-10: pypdf 는 깨진 구조에서 PyPdfError 밖의 예외(KeyError('/Kids') · AttributeError · TypeError · UnboundLocalError)도 내
    300번 중 29번이 학생 문장 없이 404(엉뚱한 까닭) · 500 으로 끝났다. 같은 300 꼴(3쪽 PDF 를 잘라내기 · 바이트 바꾸기 · 지우기, 씨앗 1)을 그대로 쓴다."""
    import io
    import random
    from pypdf import PdfWriter
    from procsvc.manual_sources import extract
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(200, 200)
    buf = io.BytesIO()
    writer.write(buf)
    raw, rnd, leaked = buf.getvalue(), random.Random(1), []
    for i in range(300):
        r, kind = bytearray(raw), rnd.choice(['trunc', 'flip', 'del'])
        if kind == 'trunc':
            r = r[:rnd.randint(10, len(r) - 1)]
        elif kind == 'flip':
            for _ in range(rnd.randint(1, 8)):
                j = rnd.randrange(8, len(r))
                r[j] = rnd.randrange(256)
        else:
            j = rnd.randrange(8, len(r))
            del r[j:j + rnd.randint(1, 40)]
        try:
            extract(bytes(r), 'manual.pdf')
        except ValueError as exc:
            if 'PDF를 읽을 수 없습니다' not in str(exc) and 'PDF는 1~500페이지' not in str(exc) and '암호화' not in str(exc):
                leaked.append((i, kind, str(exc)[:80]))
        except Exception as exc:  # noqa: BLE001 — 새어 나온 예외를 모은다(판정)
            leaked.append((i, kind, repr(exc)[:80]))
    assert leaked == [], leaked[:5]
