"""옛 DB 뜻 복원 API 와 적재 다리(procsvc/legacy_meaning_api.py) — 미리보기가 적용할 뜻 검토는 같은 DDL 파일의 것만, 적재는 사람이 승인한 뜻 ·
REPRESENTS 만 받는다(check_commit). AI 후보 요청(POST /api/kg/ddl/meanings)은 수업 단계 문지기가 막고(test_course_policy), 여기서는 다리의 판정과
실제 process 앱의 읽기 경로를 본다. 검토 기록은 실제 SQLite 저장소(임시 파일)."""

import pytest

from conftest import SAMPLES

from procsvc import ingest, legacy_meaning as lm
from procsvc.legacy_meaning_api import Bridge
from procsvc.legacy_meaning_store import LegacyMeaningStore

LEGACY = (SAMPLES / 'legacy-plant-db.sql').read_text(encoding='utf-8')
ONTOLOGY = {'stateVariables': [{'id': 'sv:ts1', 'name': '작동유 온도', 'unit': '℃'}], 'measures': [], 'assets': [{'tag': 'HYD-01'}]}
KEY = 'public.T_EQP01.C_TMP_O'


@pytest.fixture
def store(tmp_path):
    return LegacyMeaningStore(tmp_path / 'legacy.sqlite3')


def approved(store, verdict='APPROVE'):
    tables = ingest.parse_ddl(LEGACY)
    req = lm.request(filename='legacy-plant-db.sql', text=LEGACY, tables=tables, ontology=ONTOLOGY, datasource='hyd-enterprise',
                     catalog='postgres', by='수강생')
    items = [{'column': c['key'], 'status': 'no_evidence', 'meaning': None, 'confidence': 0.1, 'evidence': [], 'reason': '근거 부족'}
             for c in req['columns']]
    items[[c['key'] for c in req['columns']].index(KEY)] = {'column': KEY, 'status': 'proposed', 'meaning': '작동유 온도', 'unit': '℃',
                                                            'link': {'kind': 'represents', 'target': 'sv:ts1'},
                                                            'evidence': [{'kind': 'name', 'text': 'TMP'}], 'confidence': 0.8}
    candidates = lm.validate_candidates(req, {'items': items})['items']
    review = lm.validate_review(req, candidates, {'by': '수강생', 'decisions': [{'column': KEY, 'verdict': verdict}]})
    return store.add('hyd', 'inst-1', 'wi-1', req['source'], review)


def plan_with(review_row=None):
    tables = ingest.parse_ddl(LEGACY)
    refl = lm.apply_comments(tables, review_row['review']) if review_row else {}
    plan = ingest.plan(tables, filename='legacy-plant-db.sql', batch='b', selection={'T_EQP01': ['C_TMP_O', 'C_PRS_A']})
    if review_row:
        lm.apply_links(plan, refl, review_row['id'])
    return plan


def test_뜻_검토_없이_고른_열은_그대로_적재할_수_있다(store):
    """실라버스 4회차 40행: AI 없이 미리보기 → 표마다 출처 시스템 · 열 선택 → 적재."""
    Bridge(lambda: store, 'hyd').check_commit(plan_with())


def test_사람이_승인한_뜻은_그_이름과_연결로_적재된다(store):
    row = approved(store)
    Bridge(lambda: store, 'hyd').check_commit(plan_with(row))


@pytest.mark.parametrize('change, says', [
    (lambda p, row: p['inputs'][0].update(represents='sv:ts1', meaningReview=None), '사람이 승인한 뜻 검토에서만'),
    (lambda p, row: p['inputs'][0].update(meaningReview='review:none'), '뜻 검토 기록이 없습니다'),
    (lambda p, row: next(i for i in p['inputs'] if i['column'] == 'C_TMP_O').update(name='다른 이름'), '승인한 뜻과 입력 이름'),
    (lambda p, row: next(i for i in p['inputs'] if i['column'] == 'C_TMP_O').update(represents='sv:other'), '승인한 온톨로지 연결'),
    (lambda p, row: next(i for i in p['inputs'] if i['column'] == 'C_PRS_A').update(meaningReview=row['id']), '승인하지 않은 열'),
], ids=['검토 없는 연결', '없는 검토', '이름 바꿈', '연결 바꿈', '승인 안 한 열'])
def test_승인하지_않은_뜻_연결은_적재에서_거절한다(store, change, says):
    row = approved(store)
    plan = plan_with(row)
    change(plan, row)
    with pytest.raises(ValueError, match=says):
        Bridge(lambda: store, 'hyd').check_commit(plan)


def test_미리보기는_같은_DDL_파일의_뜻_검토만_적용한다(store):
    row = approved(store)
    bridge = Bridge(lambda: store, 'hyd')
    assert bridge.review_for(row['id'], LEGACY)['id'] == row['id'] and bridge.review_for(None, LEGACY) is None
    with pytest.raises(ValueError, match='다른 DDL 파일'):
        bridge.review_for(row['id'], LEGACY + '\n-- 고침\n')
    with pytest.raises(ValueError, match='검토 기록이 없습니다'):
        bridge.review_for('review:none', LEGACY)


def test_없는_뜻_후보_작업은_404다(world):
    status, body = world.api('GET', '/api/kg/ddl/meanings/legacy_column_meaning.none')
    assert status == 404


def test_DDL_미리보기는_수업_단계에서도_AI_없이_뜻_없는_열을_알린다(world):
    status, plan = world.api('POST', '/api/kg/ddl/preview', {'filename': 'legacy-plant-db.sql', 'text': LEGACY,
                                                             'selection': {'T_EQP01': ['C_TMP_O']}, 'systems': {'T_EQP01': 'sys:cmms'}})
    assert status == 200, plan
    assert plan['legacy']['targets'] == 23 and [i['column'] for i in plan['inputs']] == ['C_TMP_O']
