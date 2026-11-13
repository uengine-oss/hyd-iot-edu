"""정비 계획(common/hydcommon/maintenance_plan.py) — 승인한 정기 정비 효과를 실제 CMMS 정체 · 정비 창으로 짠다(plan), 시간만 흘러 바뀌는
값은 승인 대조에서 뺀다(without_elapsed). 정책은 강사 서명 묶음(course_extractions.json)의 실제 maintenance_policy 를 쓴다.
"""
import json
from copy import deepcopy

import pytest

from conftest import ROOT
from hydcommon import maintenance_plan as mp


def _policy(scope, effect):
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


ROW = {'asset': 'HYD-01', 'pm_interval_h': 2000, 'pm_tolerance_pct': 10, 'pm_since_h': 1900, 'pm_total_h': 5900, 'pm_crew_available': 2}
PARTS = [{'part_no': 'P-PMP-SEAL', 'name': '펌프 축 씰 키트', 'available': 3, 'on_hand': 3, 'reserved': 0},
         {'part_no': 'P-RTN-FLT', 'name': '리턴 필터 엘리먼트', 'available': 4, 'on_hand': 4, 'reserved': 0}]


def _skill(**change):
    policy = _policy('single', 'reserve')
    return dict({'skillId': 'SOP-PM-21', 'source_id': policy['anchor']['source_id'], 'maintenance_policy': policy,
                 'actions': [{'code': 'WO_CREATE', 'kind': 'transaction', 'target': 'sys:cmms'}]}, **change)


def _facts():
    return {'pm_context': {'asset': 'HYD-01', 'records': [dict(ROW)], 'parts': deepcopy(PARTS)}}


def test_원문_정책의_즉시_정비는_새_오더_계획으로_짜고_원문_판본을_싣는다():
    got = mp.plan(_skill(), _facts(), {'immediate': True}, [])
    assert (got['code'], got['source_id'], got['window']) == ('WO_CREATE', _skill()['source_id'], {'immediate': True})
    assert got['policy']['stock_effect'] == 'reserve'


@pytest.mark.parametrize('skill, window, error', [
    (_skill(source_id=''), {'immediate': True}, '원문 판본을 확인할 수 없습니다'),
    (_skill(source_id='ks:other'), {'immediate': True}, '원문 판본과 다릅니다'),
    (_skill(actions=[]), {'immediate': True}, '오더 발행 또는 일정 변경 Action이 없습니다'),
    (_skill(actions=[{'code': 'WO_CREATE'}, {'code': 'WO_CREATE'}]), {'immediate': True}, '중복되거나 충돌합니다'),
    (_skill(), {}, '실제 목표 정비 창을 확인할 수 없습니다'),
    (_skill(actions=[{'code': 'WO_RESCHEDULE', 'kind': 'transaction', 'target': 'sys:cmms'}]), {'immediate': True}, '기존 부품 할당 보존'),
], ids=['원문 판본 없음', '정책과 다른 판본', '오더 효과 없음', '오더 효과 둘', '정비 창 없음', '예약 정책에 일정 변경'])
def test_원문_정책과_맞지_않는_정비_후보는_계획을_짜지_않고_그_까닭으로_멈춘다(skill, window, error):
    with pytest.raises(ValueError, match=error):
        mp.plan(skill, _facts(), window, [])


@pytest.mark.parametrize('value, kept', [
    ({'hours_at_window': 12.34, 'window': {'id': 'w1'}, 'assets': [{'asset': 'HYD-01', 'applicability': {'target_hours': 1.5, 'model': 'X'}}]},
     {'window': {'id': 'w1'}, 'assets': [{'asset': 'HYD-01', 'applicability': {'model': 'X'}}]}),
    ({'window': {'id': 'w1'}}, {'window': {'id': 'w1'}}),                       # 뺄 값이 없으면 그대로
    (None, None),                                                               # 계획이 아닌 값은 그대로 돌려준다
], ids=['시간 값 둘을 뺌', '뺄 값 없음', '계획 아님'])
def test_승인_대조_꼴은_시간만_흘러_바뀌는_값만_빼고_원본은_건드리지_않는다(value, kept):
    before = deepcopy(value)
    assert mp.without_elapsed(value) == kept
    assert value == before
