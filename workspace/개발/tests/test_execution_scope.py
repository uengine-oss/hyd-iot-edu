"""실행 관문(common/hydcommon/execution_scope.py) — 승인 · 실행 직전에 「이 조치 카드가 실제로 실행해도 되는 것인가」를 판정한다.

- 규칙 비교 결과(evaluation_mode=rule_analysis · execution_checked=False)는 실행 준비를 검사하지 않은 것이라 승인 · 실행할 수 없다.
- 실행 검사 표시를 하나라도 적었으면 둘 다(execution · True)여야 한다.
- 참고 보관 절차(kind=reference · executable=False)는 실행할 수 없다.
- 정기 정비 경보(maintenance_policy.PM_PATTERN — 업무 감시 계약의 CMMS 경보와 같은 값)의 카드는 검증된 원문 정비 정책과 실제 범위 ·
  오더 효과가 든 정비 계획(maintenancePlan)이 있어야 한다. 계획은 실제 hydcommon.maintenance_plan.plan 으로 만든다.
- require_decision_option: 판단 자체의 표시와 판단의 패턴(origin → scenario → facts → 카드 순)으로 카드를 판정한다.
정책은 저장소의 강사 서명 추출 묶음(it/process/procsvc/course_extractions.json) 그대로다.
"""
import copy
import json

import pytest

from conftest import ROOT
from hydcommon import maintenance_plan
from hydcommon.execution_scope import require_decision_option, require_executable
from hydcommon.maintenance_policy import PM_PATTERN
from procsvc import business_monitor


def _signed(scope, effect):
    found = []

    def walk(x):
        if isinstance(x, dict):
            p = x.get('maintenance_policy')
            if isinstance(p, dict) and p['scope'] == scope and p['stock_effect'] == effect:
                found.append(p)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(json.loads((ROOT / 'it' / 'process' / 'procsvc' / 'course_extractions.json').read_text(encoding='utf-8')))
    assert found, (scope, effect)
    return found[0]


def _real_plan():
    """단독 · 예약 정책으로 HYD-01 즉시 정비 계획 — 정비 뒤 1,900 h(허용 1,800~2,200 h), 앞선 정비 두 번(4,000 h), 부품 재고 있음."""
    policy = _signed('single', 'reserve')
    skill = {'skillId': 'SOP-PM-21', 'source_id': policy['anchor']['source_id'], 'maintenance_policy': policy,
             'actions': [{'code': 'WO_CREATE', 'kind': 'transaction', 'target': 'sys:cmms'}]}
    row = {'asset': 'HYD-01', 'pm_interval_h': 2000, 'pm_tolerance_pct': 10, 'pm_since_h': 1900, 'pm_total_h': 5900,
           'pm_crew_available': 2}
    parts = [{'part_no': 'P-PMP-SEAL', 'name': '펌프 축 씰 키트', 'available': 3, 'on_hand': 3, 'reserved': 0},
             {'part_no': 'P-RTN-FLT', 'name': '리턴 필터 엘리먼트', 'available': 4, 'on_hand': 4, 'reserved': 0}]
    return maintenance_plan.plan(skill, {'pm_context': {'asset': 'HYD-01', 'records': [row], 'parts': parts}}, {'immediate': True}, [])


def _pm_option(**change):
    option = {'pattern': PM_PATTERN, 'evaluation_mode': 'execution', 'execution_checked': True, 'maintenancePlan': _real_plan()}
    option.update(change)
    return option


@pytest.mark.parametrize('option', [
    {}, {'kind': 'control', 'pattern': 'COOLER_DEGRADATION'}, {'evaluation_mode': 'execution', 'execution_checked': True},
    {'kind': 'work_order', 'executable': True},
], ids=['표시 없음', '설비 조치', '실행 검사 표시', '실행 가능 표시'])
def test_보통_조치는_실행_검사_표시가_없거나_맞으면_통과한다(option):
    assert require_executable(option) is None


@pytest.mark.parametrize('option, word', [
    ({'evaluation_mode': 'rule_analysis'}, '규칙 비교 결과'),
    ({'execution_checked': False}, '규칙 비교 결과'),
    ({'evaluation_mode': 'rule_analysis', 'execution_checked': True}, '규칙 비교 결과'),
    ({'evaluation_mode': 'execution'}, '명시한 실행 검사'),
    ({'execution_checked': True}, '명시한 실행 검사'),
    ({'evaluation_mode': 'preview', 'execution_checked': True}, '명시한 실행 검사'),
    ({'evaluation_mode': 'execution', 'execution_checked': 'true'}, '명시한 실행 검사'),      # 글 'true' 는 확인이 아니다
    ({'kind': 'reference'}, '참고 보관 절차'),
    ({'executable': False}, '참고 보관 절차'),
], ids=['규칙 비교 모드', '확인 안 함', '규칙 비교 + 확인 표시', '확인 표시 없음', '모드 없음', '다른 모드', '확인이 글', '참고 절차',
        '실행 불가 표시'])
def test_실행_준비를_검사하지_않은_카드와_참고_절차는_승인_실행할_수_없다(option, word):
    with pytest.raises(ValueError) as caught:
        require_executable(option)
    assert word in str(caught.value)


def test_실제_정비_계획이_든_정기_정비_카드는_통과한다():
    plan = _pm_option()['maintenancePlan']
    assert plan['code'] == 'WO_CREATE' and [a['asset'] for a in plan['assets']] == ['HYD-01']
    assert require_executable(_pm_option()) is None


def _broken_policy(plan):
    plan['policy']['packages'][1]['interval_h'] = 2500          # 기본 간격 2,000 h 의 정수배가 아니다


@pytest.mark.parametrize('change, word', [
    (dict(evaluation_mode=None, execution_checked=None), 'PM 실행에는'),
    (dict(maintenancePlan=None), 'PM 실행에는'),
    (dict(maintenancePlan='WO_CREATE'), 'PM 실행에는'),
    (lambda o: o['maintenancePlan'].__setitem__('code', 'PR_CREATE'), '오더 효과'),
    (lambda o: o['maintenancePlan'].__setitem__('assets', []), '오더 효과'),
    (lambda o: o['maintenancePlan'].__setitem__('policy', None), '원문 PM 적용 정책'),
    (lambda o: _broken_policy(o['maintenancePlan']), '정수배'),
], ids=['실행 검사 표시 없음', '계획 없음', '계획이 글', '오더 효과 아님', '설비 없음', '정책 없음', '정책 간격 어긋남'])
def test_정기_정비_카드에_검증된_정책_범위_오더_효과가_없으면_거절한다(change, word):
    option = _pm_option()
    if callable(change):
        change(option)
    else:
        option.update(change)
        option = {k: v for k, v in option.items() if v is not None or k == 'maintenancePlan'}
    with pytest.raises(ValueError) as caught:
        require_executable(option)
    assert word in str(caught.value)


def test_업무_감시_계약의_정기_정비_경보면_실행_관문이_정비_계획을_요구한다():
    """경보를 내는 쪽(procsvc.business_monitor 의 CMMS 경보)과 실행 관문이 같은 패턴 값을 본다 — 한쪽 이름만 바뀌면 계획 없는 정비 카드가 통과한다."""
    (pattern,) = [p for p, spec in business_monitor.PATTERNS.items() if spec['source'] == business_monitor.CMMS_SOURCE]
    assert pattern == PM_PATTERN
    with pytest.raises(ValueError, match='PM 실행에는'):
        require_executable({'pattern': pattern, 'evaluation_mode': 'execution', 'execution_checked': True})


@pytest.mark.parametrize('decision', [
    {'origin': {'pattern': PM_PATTERN}},
    {'scenario': {'pattern': PM_PATTERN}},
    {'facts': {'pattern': PM_PATTERN}},
    {'origin': {'pattern': PM_PATTERN}, 'facts': {'pattern': 'COOLER_DEGRADATION'}},
], ids=['출처 패턴', '시나리오 패턴', '사실 패턴', '출처가 사실보다 먼저'])
def test_판단의_패턴이_정기_정비면_카드에_패턴이_없어도_정비_계획을_요구한다(decision):
    option = {'evaluation_mode': 'execution', 'execution_checked': True, 'pattern': 'COOLER_DEGRADATION'}
    with pytest.raises(ValueError, match='PM 실행에는'):
        require_decision_option(decision, option)
    plan = {'evaluation_mode': 'execution', 'execution_checked': True, 'maintenancePlan': _real_plan()}
    assert require_decision_option(decision, plan) is None


def test_판단_자체가_규칙_비교_결과면_카드가_실행_검사_표시를_가져도_거절한다():
    with pytest.raises(ValueError, match='규칙 비교 결과'):
        require_decision_option({'evaluation_mode': 'rule_analysis', 'origin': {'pattern': 'COOLER_DEGRADATION'}},
                                {'evaluation_mode': 'execution', 'execution_checked': True})


def test_판단에_패턴이_없으면_카드의_패턴으로_판정한다():
    option = {'pattern': PM_PATTERN, 'evaluation_mode': 'execution', 'execution_checked': True}
    with pytest.raises(ValueError, match='PM 실행에는'):
        require_decision_option({}, option)
    assert require_decision_option({}, dict(option, pattern='COOLER_DEGRADATION')) is None


def test_관문은_카드를_바꾸지_않는다():
    option = _pm_option()
    before = copy.deepcopy(option)
    require_executable(option)
    require_decision_option({'origin': {'pattern': PM_PATTERN}}, option)
    assert option == before
