"""구매 공급사 선택(common/hydcommon/skill_scope.py) — 순정 여부는 그래프 속성 oem 이지 공급사 이름 글자가 아니다(G3b-27 · P2-11),
구매 후보 규칙 검사는 한 함수(purchase_rule_problem).

공급사 · 견적 값은 업무 DB 시드(it/supabase/seed.sql)와 그래프 시드(it/neo4j/v2/instances.cypher)의 실제 값(씰 키트 A 35 · B 55 · C 20만 원,
B-OEM 만 oem=true, C 는 AVL 밖) 그대로다.
"""
import copy

import pytest

from hydcommon import skill_scope as ss

QUOTES = {'sup:a': {'name': 'A정밀 (저가)', 'price': 35, 'lead_d': 2, 'fail_rate': 0.12, 'avl': True},
          'sup:b': {'name': 'B-OEM (순정)', 'price': 55, 'lead_d': 5, 'fail_rate': 0.02, 'avl': True},
          'sup:c': {'name': 'C트레이딩 (최저가)', 'price': 20, 'lead_d': 1, 'fail_rate': 0.30, 'avl': False}}
LINKS = [{'part': 'part:pmp-seal', 'supplier': 'sup:a', 'name': 'A정밀 (저가)', 'oem': False},
         {'part': 'part:pmp-seal', 'supplier': 'sup:b', 'name': 'B-OEM (순정)', 'oem': True},
         {'part': 'part:pmp-seal', 'supplier': 'sup:c', 'name': 'C트레이딩 (최저가)', 'oem': False}]


def _skill(policy, links=LINKS):
    return {'scope': 'purchase', 'executable': True, 'supplier_policy': policy, 'partSuppliers': copy.deepcopy(links),
            'actions': [{'code': 'PR_CREATE', 'value': None}]}


FACTS = {'spare_quotes': QUOTES, 'purchase_part': 'part:pmp-seal', 'spare_part_no': 'P-PMP-SEAL'}


@pytest.mark.parametrize('policy, chosen', [('oem', 'sup:b'), ('lowest_approved', 'sup:a'), ('fastest_quote', 'sup:c')])
def test_정책마다_실제_견적에서_공급사_하나를_고른다(policy, chosen):
    result = ss.resolve_supplier(_skill(policy), FACTS)
    assert result['actions'][0]['value'] == chosen and result['resolvedSupplier']['genuine'] is (chosen == 'sup:b')


def test_공급사_이름을_바꿔도_순정_판정은_그대로다():
    renamed = {k: dict(v, name=v['name'].replace('B-OEM (순정)', 'B사 정품')) for k, v in QUOTES.items()}
    assert ss.resolve_supplier(_skill('oem'), dict(FACTS, spare_quotes=renamed))['actions'][0]['value'] == 'sup:b'


@pytest.mark.parametrize('links, error', [
    ([dict(l, oem=None) for l in LINKS], '순정 공급사 여부'),                 # 그래프가 oem 을 주지 않으면 「순정 아님」으로 읽지 않는다
    ([dict(l, oem=False) for l in LINKS], '충족하는 실제 견적이 없습니다'),
    ([l for l in LINKS if l['supplier'] != 'sup:b'], '충족하는 실제 견적이 없습니다'),
])
def test_순정_여부가_없거나_순정_공급사가_없으면_고르지_않는다(links, error):
    with pytest.raises(ValueError, match=error):
        ss.resolve_supplier(_skill('oem', links), FACTS)


def test_최저가_정책은_AVL_밖과_순정을_빼고_동률이면_고르지_않는다():
    tie = dict(QUOTES, **{'sup:d': dict(QUOTES['sup:a'], name='D상사')})
    links = LINKS + [{'part': 'part:pmp-seal', 'supplier': 'sup:d', 'name': 'D상사', 'oem': False}]
    with pytest.raises(ss.SupplierUnresolved, match='동률'):
        ss.resolve_supplier(_skill('lowest_approved', links), dict(FACTS, spare_quotes=tie))


@pytest.mark.parametrize('tests, ok', [
    ([{'variable': 'pattern', 'operator': '==', 'value': ss.PURCHASE_PATTERN}], True),
    ([{'variable': 'pattern', 'operator': '==', 'value': 'PM_DUE'}], False),
    ([], False),
])
def test_구매_후보_규칙은_구매_경보_조건이_있어야_한다(tests, ok):
    problem = ss.purchase_rule_problem(tests)
    assert (problem is None) is ok and (ok or ss.PURCHASE_PATTERN in problem)
