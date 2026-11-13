"""구매 총비용 비교(common/hydcommon/purchase_comparison.py) — 원문 정책(PR-07)대로 공급사별 총비용을 계산한다.

원문(PR-7.4절): 총비용 = 단가 × 수량 + 불량 기대비용(수량 × 불량률 × 불량 1건 손실 250만 원). 불량률이 10 %를 넘는 승인(AVL) 공급사에
발주하면 전수 검사 비용 20만 원을 더한다. 정책 수치는 원문 인용에서 다시 읽어 대조한다 — 인용과 다른 수치는 받지 않는다.
정책은 저장소의 강사 서명 추출 묶음(it/process/procsvc/course_extractions.json) 그대로, 견적은 업무 DB 시드(it/supabase/seed.sql 의
쿨러 코어 공급사 셋)와 같은 값이다.
"""
import copy
import json
import math

import pytest

from conftest import ROOT
from hydcommon.purchase_comparison import compare, policy


def _signed():
    found = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get('purchase_comparison_policy'), dict):
                found.append(x['purchase_comparison_policy'])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(json.loads((ROOT / 'it' / 'process' / 'procsvc' / 'course_extractions.json').read_text(encoding='utf-8')))
    return found


SIGNED = _signed()
POLICY = SIGNED[0]
# 업무 DB 시드의 쿨러 코어(P-CLR-CORE) 견적: A정밀 (저가) · B-OEM (순정) · C트레이딩 (최저가, AVL 아님)
QUOTES = {'sup:a': {'price': 180, 'fail_rate': 0.12, 'lead_d': 3, 'avl': True},
          'sup:b': {'price': 260, 'fail_rate': 0.02, 'lead_d': 5, 'avl': True},
          'sup:c': {'price': 120, 'fail_rate': 0.20, 'lead_d': 2, 'avl': False}}


def test_서명된_구매_정책은_모두_원문_인용과_수치가_같아_통과한다():
    assert len(SIGNED) >= 3 and all(policy(p) == p for p in SIGNED)
    assert (POLICY['loss_per_failure'], POLICY['inspection_threshold'], POLICY['inspection_cost']) == (250, 0.1, 20)
    assert policy(json.dumps(POLICY, ensure_ascii=False)) == POLICY


def _with(**change):
    p = copy.deepcopy(POLICY)
    for key, value in change.items():
        if value is KeyError:
            p.pop(key)
        else:
            p[key] = value
    return p


@pytest.mark.parametrize('value, word', [
    (None, '검토된 원문 정책이 없습니다'),
    ([], '검토된 원문 정책이 없습니다'),
    (_with(version=2), '검토된 원문 정책이 없습니다'),
    (_with(version=True), '검토된 원문 정책이 없습니다'),
    (_with(loss_per_failure=KeyError), '실제 수치가 필요합니다: loss_per_failure'),
    (_with(loss_per_failure='250'), '실제 수치가 필요합니다: loss_per_failure'),
    (_with(inspection_cost=-20), '실제 수치가 필요합니다: inspection_cost'),
    (_with(inspection_cost=math.inf), '실제 수치가 필요합니다: inspection_cost'),
    (_with(inspection_threshold=10), '0부터1 사이'),
    (_with(anchor=None), '원문 판본과 인용'),
    (_with(anchor={'source_id': 'provided-source', 'quote': ''}), '원문 판본과 인용'),
    (_with(loss_per_failure=200), '원문 인용과 다릅니다: loss_per_failure'),
    (_with(inspection_threshold=0.15), '원문 인용과 다릅니다: inspection_threshold'),
    (_with(inspection_cost=25), '원문 인용과 다릅니다: inspection_cost'),
    (_with(anchor=dict(POLICY['anchor'], quote='단가 × 수량으로만 비교한다.')), '원문 인용과 다릅니다: loss_per_failure'),
], ids=['없음', '목록', 'version 2', 'version 참거짓', '손실 없음', '손실 글', '검사 비용 음수', '검사 비용 무한', '기준 10(퍼센트 그대로)',
        '인용 없음', '빈 인용', '손실 다름', '기준 다름', '검사 비용 다름', '인용에 수치 없음'])
def test_정책이_없거나_수치가_원문_인용과_다르면_거절한다(value, word):
    with pytest.raises(ValueError) as caught:
        policy(value)
    assert word in str(caught.value)


def _skill(supplier, **change):
    skill = {'source_id': POLICY['anchor']['source_id'], 'purchase_comparison_policy': POLICY, 'parts': ['part:cooler-core'],
             'actions': [{'code': 'PR_CREATE', 'value': supplier}]}
    skill.update(change)
    return skill


def _facts(**change):
    facts = {'purchase_part': 'part:cooler-core', 'spare_quotes': copy.deepcopy(QUOTES), 'need_qty': 2, 'need_by_days': 4}
    facts.update(change)
    return facts


@pytest.mark.parametrize('supplier, amount, failure, inspection', [
    ('sup:a', 360, 2 * 0.12 * 250, 20),     # AVL · 불량률 12 % > 10 % → 전수 검사 20
    ('sup:b', 520, 2 * 0.02 * 250, 0),
    ('sup:c', 240, 2 * 0.20 * 250, 0),      # 불량률은 높지만 AVL 이 아니라 전수 검사 대상이 아니다(원문: 「승인 공급사에 발주할 때」)
], ids=['저가 · 전수 검사', '순정', '최저가 · AVL 아님'])
def test_총비용은_원문_식대로_단가_수량_불량_기대비용_전수_검사를_더한다(supplier, amount, failure, inspection):
    out = compare(_skill(supplier), _facts())
    assert (out['purchase_amount'], out['expected_failure_cost'], out['inspection_cost']) == (amount, pytest.approx(failure), inspection)
    assert out['total_cost'] == pytest.approx(amount + failure + inspection)
    q = QUOTES[supplier]
    assert (out['supplier'], out['unit_price'], out['fail_rate'], out['lead_days'], out['avl']) == (supplier, q['price'], q['fail_rate'], q['lead_d'], q['avl'])
    assert out['lead_slack_days'] == 4 - q['lead_d'] and out['policy'] == POLICY and out['source_id'] == POLICY['anchor']['source_id']


def test_소수_금액도_어긋남_없이_더한다():
    """십진 계산이라 0.1 + 0.2 같은 이진 소수 오차가 합계에 붙지 않는다."""
    quotes = {'sup:a': {'price': 0.1, 'fail_rate': 0.0, 'lead_d': 1, 'avl': True}}
    out = compare(_skill('sup:a'), _facts(spare_quotes=quotes, need_qty=3))
    assert out['purchase_amount'] == 0.3 and out['total_cost'] == 0.3


@pytest.mark.parametrize('fail_rate, inspected', [(0.1, False), (0.1001, True)], ids=['딱 10 %', '10 % 넘음'])
def test_전수_검사는_불량률이_기준을_넘을_때만_더한다(fail_rate, inspected):
    quotes = {'sup:a': dict(QUOTES['sup:a'], fail_rate=fail_rate)}
    assert compare(_skill('sup:a'), _facts(spare_quotes=quotes))['inspection_cost'] == (20 if inspected else 0)


def test_리드타임이_필요일보다_길면_여유가_음수로_나온다():
    out = compare(_skill('sup:b'), _facts(need_by_days=3))
    assert out['lead_slack_days'] == -2


@pytest.mark.parametrize('skill_change, facts_change, word', [
    ({'source_id': 'other-source'}, {}, '원문 판본이 다릅니다'),
    ({'purchase_comparison_policy': None}, {}, '검토된 원문 정책이 없습니다'),
    ({}, {'purchase_part': None}, '검토된 원문 범위에 없습니다'),
    ({}, {'purchase_part': 'part:fan-bearing'}, '검토된 원문 범위에 없습니다'),
    ({'actions': []}, {}, '발주 Action 하나'),
    ({'actions': [{'code': 'PR_CREATE', 'value': 'sup:a'}, {'code': 'PR_CREATE', 'value': 'sup:b'}]}, {}, '발주 Action 하나'),
    ({'actions': [{'code': 'PR_CREATE', 'value': None}]}, {}, '발주 Action 하나'),
    ({'actions': [{'code': 'PR_CREATE', 'value': 'sup:z'}]}, {}, '견적·AVL을 확인할 수 없습니다'),
    ({}, {'spare_quotes': {'sup:a': dict(QUOTES['sup:a'], avl=None)}}, '견적·AVL을 확인할 수 없습니다'),
    ({}, {'spare_quotes': {'sup:a': dict(QUOTES['sup:a'], avl='Y')}}, '견적·AVL을 확인할 수 없습니다'),
    ({}, {'spare_quotes': {'sup:a': dict(QUOTES['sup:a'], price=None)}}, '필수 수치를 확인할 수 없습니다: price'),
    ({}, {'spare_quotes': {'sup:a': dict(QUOTES['sup:a'], price=math.nan)}}, '필수 수치를 확인할 수 없습니다: price'),
    ({}, {'spare_quotes': {'sup:a': dict(QUOTES['sup:a'], lead_d=-1)}}, '필수 수치를 확인할 수 없습니다: lead_d'),
    ({}, {'need_qty': None}, '필수 수치를 확인할 수 없습니다: quantity'),
    ({}, {'need_qty': True}, '필수 수치를 확인할 수 없습니다: quantity'),
    ({}, {'need_by_days': '4'}, '필수 수치를 확인할 수 없습니다: need_by_days'),
    ({}, {'need_qty': 0}, '수량 또는 불량률'),
    ({}, {'spare_quotes': {'sup:a': dict(QUOTES['sup:a'], fail_rate=1.2)}}, '수량 또는 불량률'),
], ids=['판본 다름', '정책 없음', '부품 없음', '범위 밖 부품', '발주 없음', '발주 둘', '공급사 미정', '견적 없는 공급사', 'AVL 없음', 'AVL 글',
        '단가 없음', '단가 NaN', '리드타임 음수', '수량 없음', '수량 참거짓', '필요일 글', '수량 0', '불량률 120 %'])
def test_비교에_필요한_실제_사실이_없거나_어긋나면_거절한다(skill_change, facts_change, word):
    with pytest.raises(ValueError) as caught:
        compare(_skill('sup:a', **skill_change), _facts(**facts_change))
    assert word in str(caught.value)
