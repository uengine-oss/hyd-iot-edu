"""성과 지표(BSC) 득실 경로(common/hydcommon/bsc.py) — 조치 카드가 어느 성과 지표를 어느 쪽으로 얼마나 움직이는지 경로째 계산한다.

규칙:
- 조건 문장이 붙은 관계(AFFECTS · INFLUENCES 의 condition)는 판정할 해석이 그래프에 없어 「미확인(UNKNOWN)」이다 — 조건부 영향으로 보인다.
  조건이 없는 관계는 성립(TRUE). 문장을 해석해 참/거짓을 지어내지 않는다.
- 경로: 처음은 AFFECTS, 뒤는 INFLUENCES. 방향 = 부호(+1/−1)의 곱, 무게 = INFLUENCES 강도(high 1 · medium 0.6 · low 0.3)의 곱.
  순환 · 노드와 관계가 어긋남 · 부호나 강도를 모름 · 지표 방향을 모름은 거절한다.
- 같은 지표 · 같은 방향의 경로는 묶는다: 확정 무게 = 성립 경로의 최대, 조건부 무게 = 미확인 경로 최대가 확정을 넘는 만큼만.
실제 경로는 시드 그래프의 상태 변수 · 지표 관계에 시험 스킬 하나를 이어 실제 템플릿(it/neo4j/templates/t3_tradeoffs.cypher)으로 읽는다.
"""
import copy

import pytest

from conftest import ROOT
from hydcommon import bsc, ranking


def edge(key, kind, source, target, sign=1, strength='high', condition=None):
    return {'key': key, 'type': kind, 'source': source, 'target': target, 'sign': sign, 'strength': strength, 'condition': condition}


def path(measure, direction, edges, owners=('설비보전팀',), name=None):
    nodes = [edges[0]['source']] + [e['target'] for e in edges]
    return {'skill': nodes[0], 'measure': measure, 'name': name or measure, 'direction': direction, 'owners': list(owners),
            'nodes': nodes, 'edges': edges, 'conds': [e['condition'] for e in edges if e.get('condition')]}


@pytest.mark.parametrize('condition, status', [(None, 'TRUE'), ('', 'TRUE'), ('외기 30 ℃ 이상일 때', 'UNKNOWN')],
                         ids=['조건 없음', '빈 조건', '조건 문장'])
def test_조건_문장이_붙은_관계는_판정할_해석이_없어_미확인이다(condition, status):
    result = bsc.check_condition(edge('e1', 'AFFECTS', 's', 'x', condition=condition), {'ts1': 70}, {})
    assert result['status'] == status and result['edge'] == 'e1' and result['inputs'] == {}
    assert ('error' in result) == (status == 'UNKNOWN')
    if status == 'UNKNOWN':
        assert result['description'] == condition and '해석이 없습니다' in result['error']


def test_부호는_경로를_따라_곱하고_강도는_INFLUENCES만_곱한다():
    row = path('msr:mtbf', 'DOWN', [edge('a', 'AFFECTS', 'skill:x', 'sv:ts1', sign=-1, strength='low'),     # AFFECTS 강도는 무게에 안 든다
                                    edge('b', 'INFLUENCES', 'sv:ts1', 'sv:vs1', sign=-1, strength='medium'),
                                    edge('c', 'INFLUENCES', 'sv:vs1', 'msr:mtbf', sign=1, strength='low')])
    effects, paths = bsc.evaluate_paths([row], {}, {})
    (p,) = paths
    assert (p['dir'], p['weight'], p['good'], p['status'], p['path_id']) == (1, pytest.approx(0.18), False, 'TRUE', 'a|b|c')
    assert effects == [{'measure': 'msr:mtbf', 'name': 'msr:mtbf', 'owner': '설비보전팀', 'dir': 1, 'good': False, 'weight': 0.18,
                        'conditional': False, 'conditionStatus': 'TRUE', 'conds': [], 'supportingPaths': ['a|b|c']}]


def test_AFFECTS_하나로_지표에_닿는_경로는_무게_1이다():
    row = path('msr:energy-use', 'DOWN', [edge('a', 'AFFECTS', 'skill:x', 'msr:energy-use', sign=1, strength=None)])
    effects, _ = bsc.evaluate_paths([row], {}, {})
    assert [(e['weight'], e['dir'], e['good']) for e in effects] == [(1.0, 1, False)]


def _two(confirmed_strength, possible_strength):
    sure = path('msr:availability', 'UP', [edge('a1', 'AFFECTS', 'skill:x', 'sv:ts1', sign=-1),
                                           edge('i1', 'INFLUENCES', 'sv:ts1', 'msr:availability', sign=-1, strength=confirmed_strength)])
    maybe = path('msr:availability', 'UP', [edge('a2', 'AFFECTS', 'skill:x', 'sv:vs1', sign=-1),
                                            edge('i2', 'INFLUENCES', 'sv:vs1', 'msr:availability', sign=-1, strength=possible_strength,
                                                 condition='VS1 ≥ 2.0 mm/s 진동 인터록')])
    return [sure, maybe]


def test_한_지표에_성립_경로와_미확인_경로가_있으면_조건부는_확정을_넘는_만큼만이다():
    effects, paths = bsc.evaluate_paths(_two('medium', 'high'), {}, {})
    assert [p['status'] for p in paths] == ['TRUE', 'UNKNOWN']
    assert [(e['conditionStatus'], e['weight'], e['conditional'], e['supportingPaths']) for e in effects] == [
        ('TRUE', 0.6, False, ['a1|i1']), ('UNKNOWN', 0.4, True, ['a2|i2'])]
    assert effects[1]['conds'] == ['VS1 ≥ 2.0 mm/s 진동 인터록'] and effects[0]['good'] is True


@pytest.mark.parametrize('confirmed, possible', [('high', 'high'), ('high', 'low')], ids=['같은 무게', '미확인이 더 작음'])
def test_미확인_경로가_확정보다_크지_않으면_조건부_영향은_없다(confirmed, possible):
    effects, _ = bsc.evaluate_paths(_two(confirmed, possible), {}, {})
    assert [(e['conditionStatus'], e['weight']) for e in effects] == [('TRUE', 1.0)]


def test_같은_지표라도_방향이_다르면_따로_묶는다():
    up = path('msr:energy-use', 'DOWN', [edge('a1', 'AFFECTS', 'skill:x', 'sv:fan-speed', sign=1),
                                         edge('i1', 'INFLUENCES', 'sv:fan-speed', 'msr:energy-use', strength='low')])
    down = path('msr:energy-use', 'DOWN', [edge('a2', 'AFFECTS', 'skill:x', 'sv:load', sign=-1),
                                           edge('i2', 'INFLUENCES', 'sv:load', 'msr:energy-use', strength='medium')])
    effects, _ = bsc.evaluate_paths([up, down], {}, {})
    assert sorted((e['dir'], e['weight'], e['good']) for e in effects) == [(-1, 0.6, True), (1, 0.3, False)]


def test_같은_최대_무게의_경로가_여럿이면_근거_경로와_담당을_모두_적는다():
    rows = [path('msr:throughput', 'UP', [edge(f'a{n}', 'AFFECTS', 'skill:x', f'sv:{n}'), edge(f'i{n}', 'INFLUENCES', f'sv:{n}', 'msr:throughput',
                                                                                              strength=s)], owners=[o])
            for n, s, o in [(1, 'high', '생산팀'), (2, 'high', '설비보전팀'), (3, 'low', '구매팀')]]
    (effect,), _ = bsc.evaluate_paths(rows, {}, {})
    assert effect['supportingPaths'] == ['a1|i1', 'a2|i2'] and effect['owner'] == '생산팀 / 설비보전팀'


def _bad(change):
    row = path('msr:mtbf', 'UP', [edge('a', 'AFFECTS', 'skill:x', 'sv:ts1'), edge('b', 'INFLUENCES', 'sv:ts1', 'msr:mtbf', strength='medium')])
    change(row)
    return row


@pytest.mark.parametrize('change, word', [
    (lambda r: r.__setitem__('nodes', ['skill:x', 'sv:ts1', 'skill:x']), 'cyclic'),
    (lambda r: r.__setitem__('nodes', ['skill:x', 'sv:ts1']), 'cyclic'),
    (lambda r: r['edges'][1].__setitem__('source', 'sv:vs1'), 'does not match'),
    (lambda r: r['edges'][0].__setitem__('target', 'sv:vs1'), 'does not match'),
    (lambda r: r['edges'][0].__setitem__('type', 'INFLUENCES'), 'relation kinds and signs'),
    (lambda r: r['edges'][1].__setitem__('type', 'AFFECTS'), 'relation kinds and signs'),
    (lambda r: r['edges'][1].__setitem__('sign', 0), 'relation kinds and signs'),
    (lambda r: r['edges'][1].__setitem__('sign', 2), 'relation kinds and signs'),
    (lambda r: r['edges'][1].__setitem__('sign', True), 'relation kinds and signs'),     # 참/거짓은 부호가 아니다
    (lambda r: r['edges'][1].__setitem__('sign', 1.0), 'relation kinds and signs'),
    (lambda r: r['edges'][0].__setitem__('sign', None), 'relation kinds and signs'),
    (lambda r: r['edges'][1].__setitem__('strength', 'very'), 'strength is unknown'),
    (lambda r: r['edges'][1].__setitem__('strength', None), 'strength is unknown'),
    (lambda r: r.__setitem__('direction', 'FLAT'), 'direction is unknown'),
], ids=['노드 반복(순환)', '노드 수 모자람', '관계 시작 어긋남', '관계 끝 어긋남', '처음이 INFLUENCES', '뒤가 AFFECTS', '부호 0', '부호 2',
        '부호 참거짓', '부호 소수', '부호 없음', '모르는 강도', '강도 없음', '모르는 지표 방향'])
def test_경로가_순환하거나_노드와_관계가_어긋나거나_부호_강도를_모르면_거절한다(change, word):
    with pytest.raises(ValueError) as caught:
        bsc.evaluate_paths([_bad(change)], {}, {})
    assert word in str(caught.value)


def test_경로_없이_미리_계산된_영향은_그래프_근거_없이_받고_조건부면_미확인이다():
    rows = [{'measure': 'msr:mtbf', 'name': 'MTBF', 'direction': 'UP', 'dir': 1, 'good': True, 'weight': 0.5, 'owner': '설비보전팀'},
            {'measure': 'msr:oil-life', 'name': '작동유 수명', 'direction': 'UP', 'dir': -1, 'good': False, 'weight': 0.3, 'conditional': True}]
    effects, paths = bsc.evaluate_paths(rows, {}, {})
    assert {p['path_id']: p['status'] for p in paths} == {'projection:' + ranking.fingerprint(rows[0]): 'TRUE',
                                                          'projection:' + ranking.fingerprint(rows[1]): 'UNKNOWN'}
    assert all(p['projection'] == 'materialized_without_path' and p['checks'] == [] for p in paths)
    assert sorted((e['measure'], e['conditional']) for e in effects) == [('msr:mtbf', False), ('msr:oil-life', True)]


@pytest.mark.parametrize('weight', [-0.1, None, 'NaN', True], ids=['음수', '없음', 'NaN', '참거짓'])
def test_미리_계산된_영향의_무게가_음수거나_숫자가_아니면_거절한다(weight):
    with pytest.raises(ValueError):
        bsc.evaluate_paths([{'measure': 'm', 'name': 'm', 'direction': 'UP', 'dir': 1, 'good': True, 'weight': weight}], {}, {})


def test_동의_기록용_경로는_판정_결과를_뺀_깊은_사본이다():
    _, paths = bsc.evaluate_paths(_two('medium', 'high'), {}, {})
    before = copy.deepcopy(paths)
    consented = bsc.consent_paths(paths)
    assert all('checks' not in p for p in consented) and [p['path_id'] for p in consented] == [p['path_id'] for p in paths]
    consented[0]['edges'][0]['sign'] = 99
    assert paths == before


TRADEOFFS = (ROOT / 'it' / 'neo4j' / 'templates' / 't3_tradeoffs.cypher').read_text(encoding='utf-8')


def test_시드_그래프의_실제_득실_경로를_계산하면_템플릿의_방향_무게_조건부와_같다(seeded_graph):
    """시드의 상태 변수 → 지표 관계(조건 문장 있는 것 · 없는 것 섞임)에 시험 스킬 하나를 잇고 실제 템플릿으로 경로를 읽는다.
    템플릿(Cypher)이 낸 방향 · 무게 · 조건부와 bsc 계산이 같아야 하고, 조건 문장이 있는 경로만 미확인이다."""
    seeded_graph.query("MATCH (t:StateVariable {id: 'sv:ts1'}), (f:StateVariable {id: 'sv:fan-speed'}) "
                       "CREATE (s:Skill {id: 'skill:fo2-probe'}) CREATE (s)-[:AFFECTS {sign: -1}]->(t) CREATE (s)-[:AFFECTS {sign: 1}]->(f)")
    rows = seeded_graph.query(TRADEOFFS, ids=['skill:fo2-probe'])
    assert {r['measure'] for r in rows} >= {'msr:oil-life', 'msr:safety-margin', 'msr:energy-use'}, rows
    effects, paths = bsc.evaluate_paths(rows, {}, {})
    by_id = {p['path_id']: p for p in paths}
    for r in rows:
        p = by_id['|'.join(e['key'] for e in r['edges'])]
        assert (p['dir'], p['weight'], p['good']) == (r['dir'], pytest.approx(r['weight']), r['good']), r
        assert (p['status'] == 'UNKNOWN') == r['conditional'], r
    conditional = {e['measure'] for e in effects if e['conditional']}
    assert 'msr:oil-life' in conditional and 'msr:safety-margin' not in conditional        # 「유온 60 ℃ 이상에서 크게」만 조건 문장
