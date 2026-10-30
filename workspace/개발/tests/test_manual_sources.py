"""문서 보관소(procsvc/manual_sources.py) — 제공 문서 넷은 원문 바이트 그대로 보관되고, 추출한 글이 원문과 같으며, 수업 규칙이 아는 그 문서다."""
import hashlib
from pathlib import Path

import pytest

from procsvc import course_policy as cp
from procsvc.manual_sources import ManualSources

SAMPLES = Path(__file__).resolve().parents[3] / 'it' / 'portal' / 'www' / 'samples'
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
