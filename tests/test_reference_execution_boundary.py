from copy import deepcopy

import pytest

from procsvc import decisions, main
from procsvc.service_parts import ServicePartsRuntime
from test_decisions_process import dec


@pytest.mark.parametrize('flag', [{'kind': 'reference'}, {'executable': False}])
def test_source_only_option_cannot_approve_even_with_forged_feasible_and_actions(flag):
    decision = decisions.new(dec())
    option = decision['options'][0]
    option.update(flag)
    before = deepcopy(decision)
    assert decisions.may_approve(decision, option, 'role:plant-mgr') is False
    with pytest.raises(ValueError, match='참고 보관'):
        decisions.approve(decision, option['id'], '승인자', 'role:plant-mgr')
    assert decision == before


@pytest.mark.parametrize('flag', [{'kind': 'reference'}, {'executable': False}])
def test_reference_snapshot_cannot_make_commands_or_external_transaction(flag, monkeypatch):
    decision = dec()
    option = decision['options'][0]
    option.update(flag)
    decision['chosen'] = option['id']
    calls = []
    monkeypatch.setattr(main.urllib.request, 'urlopen', lambda *a, **kw: calls.append(a))
    request = main.HitlDecideReq(decision=decision['id'], option=option['id'], role='role:plant-mgr')
    with pytest.raises(ValueError, match='참고 보관'):
        main._commands_of(option, request)
    with pytest.raises(ValueError, match='참고 보관'):
        main.exec_skill(decision, {'skill': option['id'], 'code': 'WO_CREATE', 'system': 'sys:cmms'})
    inst = {'variables_data': [{'key': 'approved_by', 'value': '승인자'}, {'key': 'chosen_option', 'value': option}]}
    with pytest.raises(ValueError, match='참고 보관'):
        ServicePartsRuntime()._require_approval(inst, {'activity_id': 'T_execute'})
    assert calls == []


@pytest.mark.parametrize('missing', [None, '', '   '])
def test_purchase_missing_approved_supplier_never_uses_default(missing, monkeypatch):
    decision = dec()
    decision['chosen'] = decision['options'][0]['id']
    calls = []
    monkeypatch.setattr(main.urllib.request, 'urlopen', lambda *a, **kw: calls.append(a))
    result = main.exec_skill(decision, {'skill': decision['chosen'], 'code': 'PR_CREATE', 'system': 'sys:erp', 'value': missing})
    assert result['ok'] is False and '실제 공급사가 없습니다' in result['error']
    assert calls == []
