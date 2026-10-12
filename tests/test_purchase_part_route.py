"""Explicit purchasing route keeps real Part evidence and never invents a Cause/FM."""
from copy import deepcopy

import pytest

from dmn_mcp.tools import enveloped
from agentsvc import decide
from agentsvc.tools import mcp_ent
from test_purchase_candidate_scope import pipeline, purchase
from test_purchase_scope_model import runtime_skill


@pytest.fixture
def part_pipeline(pipeline, monkeypatch):
    tools, rules, skills, facts, forecasts, submitted = pipeline
    k = dict(purchase(), **runtime_skill())
    skills['skill:purchase'] = k
    facts.update(spare_part_no='P-KIT', spare_quotes={'sup:b':dict(price=2,lead_d=1,fail_rate=.01,avl=True)})
    monkeypatch.setattr(decide,'gather_facts',lambda inputs,asset,known,tsdb: (dict(deepcopy(facts),**known),[]))
    stock = [dict(part_no='P-KIT',below_reorder_point=True)]
    monkeypatch.setattr(mcp_ent,'fetch',lambda path,asset: {'records':deepcopy(stock)})
    part_rows = [dict(id='part:kit',name='씰 키트',partNo='P-KIT')]
    def graph(query, **params):
        if 'RETURN p.id' in query:
            assert params == {'part':'P-KIT'}
            return deepcopy(part_rows)
        assert "scope:'purchase'" in query and params == {'part':'part:kit'}
        return [dict(id=k['skillId'],executable=k['executable'],source_id=k['source_id'])]
    monkeypatch.setattr(tools,'_graph',graph)
    return tools, skills, facts, stock, part_rows, submitted


@pytest.mark.parametrize('submit',[False,True])
def test_source_backed_part_route_evaluates_and_submits_without_cause_or_failure_mode(part_pipeline,submit):
    tools, _, _, _, _, submitted = part_pipeline
    result = enveloped(tools.submit_purchase if submit else tools.evaluate_purchase)(
        'HYD-03','P-KIT',*(('INC-C',) if submit else ()))
    assert result['result'] == 'ok',result
    record = result['document']
    assert record['origin']['cause_route'] == 'purchase-part'
    assert record['origin']['part']['id'] == 'part:kit'
    assert 'cause' not in record['origin'] and 'failureMode' not in record['origin']
    assert record['facts']['cause'] is None and record['facts']['failure_mode'] is None
    assert {o['id'] for o in record['result']['options']} == {'skill:purchase'}
    assert '씰 키트' in record['explanation'] and 'None —' not in record['explanation']
    assert len(submitted) == int(submit)


def test_unknown_or_non_shortage_part_is_refused_before_calculation(part_pipeline):
    tools, _, _, stock, _, submitted = part_pipeline
    for part in ['P-UNKNOWN','P-KIT']:
        if part == 'P-KIT': stock[0]['below_reorder_point'] = False
        result = enveloped(tools.evaluate_purchase)('HYD-03',part)
        assert result['result'] == 'error' and '재주문점 이탈' in result['message']
    assert submitted == [] and tools.registry.all() == []


def test_unknown_or_duplicate_graph_part_is_not_guessed(part_pipeline):
    tools, _, _, _, rows, _ = part_pipeline
    rows.append(deepcopy(rows[0]))
    result = enveloped(tools.evaluate_purchase)('HYD-03','P-KIT')
    assert result['result'] == 'error' and '중복' in result['message']


def test_reference_or_other_part_sop_never_becomes_a_candidate(part_pipeline):
    tools, skills, _, _, _, submitted = part_pipeline
    for key,value in [('executable',False),('parts',['part:other'])]:
        original = deepcopy(skills['skill:purchase'])
        skills['skill:purchase'][key] = value
        result = enveloped(tools.submit_purchase)('HYD-03','P-KIT','INC-C')
        assert result['result'] == 'error' and '구매 후보 지식' in result['message']
        skills['skill:purchase'] = original
    assert submitted == []


def test_missing_actual_quotes_is_explicit_error_not_legacy_supplier_master_fallback(part_pipeline):
    tools, _, facts, _, _, submitted = part_pipeline
    facts['spare_quotes'] = {}
    result = enveloped(tools.submit_purchase)('HYD-03','P-KIT','INC-C')
    assert result['result'] == 'error' and '견적·AVL' in result['message']
    assert submitted == []


def test_requested_part_cannot_use_other_part_stock_and_quotes(part_pipeline):
    tools, _, facts, _, _, submitted = part_pipeline
    facts['spare_part_no'] = 'P-OTHER'
    result = enveloped(tools.evaluate_purchase)('HYD-03','P-KIT')
    assert result['result'] == 'error' and '실제 ERP 부족부품 사실이 다릅니다' in result['message']
    assert submitted == []


def test_purchase_context_reports_reference_state_without_publishing_cards(part_pipeline):
    tools, skills, _, _, _, submitted = part_pipeline
    skills['skill:purchase']['executable'] = False
    result = enveloped(tools.purchase_context)('HYD-03','P-KIT')
    # The read protocol fixture's graph answer is deliberately independent of its mutable skill object.
    assert result['result'] == 'ok' and result['document']['route'] == 'purchase-part'
    assert submitted == [] and tools.registry.all() == []


def test_purchase_part_route_requires_explicit_business_candidate_rule(part_pipeline,pipeline):
    tools, _, _, _, _, submitted = part_pipeline
    # Shared protocol fixture rule object; keep the real evaluation path.
    rules = pipeline[1]
    rule = next(r for r in rules if r['rule'] == 'rule:purchase')
    rule['tests'] = []
    result = enveloped(tools.evaluate_purchase)('HYD-03','P-KIT')
    assert result['result'] == 'error' and 'SPARE_BELOW_MIN 조건' in result['message']
    assert submitted == []
