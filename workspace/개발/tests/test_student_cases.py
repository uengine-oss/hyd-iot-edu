"""학생 사례 꼬리표(procsvc/student_cases.py) — 학생이 만든 구성을 사례 이름으로 묶고, 읽기는 꼬리표를 바꾸지 않는다(실제 DB)."""
from types import SimpleNamespace

import pytest

from procsvc import config_bundle, procdb, student_cases as sc


@pytest.mark.parametrize('value, allow_empty, out, error', [
    ('  냉각 사례 ', False, '냉각 사례', None),
    ('가' * 60, False, '가' * 60, None),
    ('가' * 61, False, None, '1~60자'),
    ('', False, None, '1~60자'),
    ('', True, '', None),
    ('줄\n바꿈', False, None, '제어 문자'),
    (7, False, None, '글자로 적으세요'),
], ids=['앞뒤 공백', '60자', '61자', '빈 이름', '빈 이름(떼기)', '제어 문자', '글자 아님'])
def test_사례_이름은_제어_문자_없이_60자까지다(value, allow_empty, out, error):
    if error is None:
        assert sc.clean_label(value, allow_empty=allow_empty) == out
    else:
        with pytest.raises(config_bundle.BundleError, match=error):
            sc.clean_label(value, allow_empty=allow_empty)


CONTENT = {'flows': [{'definition_id': 'my_flow'}], 'agents': [{'id': 'agent:mine', 'name': '내 에이전트'}], 'skills': [], 'mcp_servers': []}


@pytest.mark.parametrize('rows, error', [
    ([{'kind': 'flows', 'asset_id': 'my_flow', 'label': '사례 1'}], None),
    ([{'kind': 'flows', 'asset_id': 'other', 'label': '사례 1'}], '자산이 없거나 중복'),
    ([{'kind': 'agents', 'asset_id': 'agent:mine', 'label': 'a'}] * 2, '자산이 없거나 중복'),
    ('목록 아님', '목록이어야'),
], ids=['있는 자산', '없는 자산', '같은 자산 두 번', '목록 아님'])
def test_가져오는_꼬리표는_묶음에_있는_자산에_한_번씩만_붙는다(rows, error):
    if error is None:
        assert sc.validate_tags(rows, CONTENT) == [{'kind': 'flows', 'asset_id': 'my_flow', 'label': '사례 1'}]
    else:
        with pytest.raises(config_bundle.BundleError, match=error):
            sc.validate_tags(rows, CONTENT)


def test_선언된_칸만_의존을_만든다_설명글의_id는_의존이_아니다():
    task = {'agent': 'agent:mine', 'skills': 'skill-a, skill-b', 'tools': 'mcp__hyd-effects__send_mail', 'service': {'server': 'my-srv'},
            'description': 'agent:other 와 같이 쓴다'}
    assert sc.declared_refs(task) == {('agents', 'agent:mine'), ('skills', 'skill-a'), ('skills', 'skill-b'),
                                      ('mcp_servers', 'hyd-effects'), ('mcp_servers', 'my-srv')}


def _rt(world):
    return SimpleNamespace(repo=procdb.PgRepo(world.dsn), tenant_id='hyd')


def test_꼬리표를_읽어도_묶음에_없는_자산의_꼬리표는_지우지_않는다(world):
    """P4-16: 전에는 사례 목록을 읽는 GET(/api/config/cases)이 묶음에 없는 자산의 꼬리표를 지웠다(화면을 여는 것만으로 DB가 바뀜)."""
    rt = _rt(world)
    store = sc.Store(rt.repo, rt.tenant_id)
    store.replace([])
    store.set('flows', 'my_flow', '사례 1')
    store.set('flows', 'gone_flow', '사례 2')
    assert sc.live_tags(rt, CONTENT) == [{'kind': 'flows', 'asset_id': 'my_flow', 'label': '사례 1'}]
    assert {(r['asset_id'], r['label']) for r in store.rows()} == {('my_flow', '사례 1'), ('gone_flow', '사례 2')}


def test_자산을_지우는_곳이_꼬리표를_지운다(world):
    rt = _rt(world)
    store = sc.Store(rt.repo, rt.tenant_id)
    store.replace([{'kind': 'flows', 'asset_id': 'a', 'label': 'x'}, {'kind': 'flows', 'asset_id': 'b', 'label': 'x'},
                   {'kind': 'agents', 'asset_id': 'agent:mine', 'label': 'x'}])
    store.remove('flows', 'a')
    assert sorted(r['asset_id'] for r in store.rows()) == ['agent:mine', 'b']
    store.remove('flows')
    assert [r['asset_id'] for r in store.rows()] == ['agent:mine']


def test_빈_이름으로_저장하면_꼬리표만_뗀다(world):
    rt = _rt(world)
    store = sc.Store(rt.repo, rt.tenant_id)
    store.replace([])
    store.set('agents', 'agent:mine', '사례')
    store.set('agents', 'agent:mine', '')
    assert store.rows() == []
