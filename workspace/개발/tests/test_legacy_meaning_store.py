"""옛 DB 뜻 검토 기록(procsvc/legacy_meaning_store.py) — 사람의 검토 하나를 고치지 않고 새로 쌓는다(같은 후보를 두 번 결정하면 두 기록).
실제 SQLite 파일(임시 폴더)로 판정한다."""
import pytest

from procsvc.legacy_meaning_store import LegacyMeaningStore

SOURCE = {'sha256': 'a' * 64, 'filename': 'legacy-plant-db.sql'}


def decided(by, verdict='APPROVE'):
    return {'by': by, 'decisions': [{'column': 'public.T.C', 'verdict': verdict, 'before': {}, 'after': None, 'note': ''}]}


@pytest.fixture
def store(tmp_path):
    return LegacyMeaningStore(tmp_path / 'state' / 'legacy.sqlite3')


def test_검토를_쌓고_그_id로_그대로_다시_읽는다(store):
    row = store.add('hyd', 'inst-1', 'wi-1', SOURCE, decided('수강생'))
    again = store.get('hyd', row['id'])
    assert again['review'] == decided('수강생') and (again['by'], again['filename'], again['sha256']) == ('수강생', SOURCE['filename'], SOURCE['sha256'])


def test_같은_후보를_다시_결정하면_새_기록이_되고_둘_다_남는다(store):
    first = store.add('hyd', 'inst-1', 'wi-1', SOURCE, decided('수강생'))
    second = store.add('hyd', 'inst-1', 'wi-1', SOURCE, decided('수강생', 'REJECT'))
    rows = store.list('hyd', 'inst-1')
    assert {r['id'] for r in rows} == {first['id'], second['id']} and first['id'] != second['id']


def test_다른_교육_공간의_검토는_읽지_않는다(store):
    row = store.add('hyd', 'inst-1', 'wi-1', SOURCE, decided('수강생'))
    with pytest.raises(KeyError):
        store.get('other', row['id'])
    assert store.list('other', 'inst-1') == []


def test_없는_검토_id는_KeyError다(store):
    with pytest.raises(KeyError):
        store.get('hyd', 'review:none')


def test_파일을_다시_열어도_기록이_남는다(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    row = LegacyMeaningStore(path).add('hyd', 'inst-1', 'wi-1', SOURCE, decided('수강생'))
    assert LegacyMeaningStore(path).get('hyd', row['id'])['by'] == '수강생'


def test_메모리_저장소도_같은_규칙이다():
    store = LegacyMeaningStore(':memory:')
    row = store.add('hyd', 'inst-1', 'wi-1', SOURCE, decided('수강생'))
    assert store.get('hyd', row['id'])['review'] == decided('수강생')
