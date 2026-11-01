"""정기 정비 정책(common/hydcommon/maintenance_policy.py) — 서명된 제공 문서 정책은 그대로 통과하고, 한 문서 고유 모양(부품 이름 ·
패키지 셋 · 2배/4배)은 요구하지 않으며(PBL 문서), 묶음 필요 인원은 원문 규칙에서 읽는다(G3b-27).

정책 원본은 저장소의 강사 서명 추출 묶음(it/process/procsvc/course_extractions.json) 그대로다.
"""
import copy
import json

import pytest

from conftest import ROOT
from hydcommon import maintenance_policy as mp


def _signed_policies():
    found = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get('maintenance_policy'), dict):
                found.append(x['maintenance_policy'])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(json.loads((ROOT / 'it' / 'process' / 'procsvc' / 'course_extractions.json').read_text(encoding='utf-8')))
    return found


SIGNED = _signed_policies()


def test_서명된_제공_문서의_정책은_모두_통과한다():
    assert len(SIGNED) >= 2 and {mp.policy(p)['scope'] for p in SIGNED} == {'single', 'bundle'}


def _pbl():
    """다른 공장의 PM 문서: 기본 500 h, 패키지 둘(500 · 1,500 h), 부품 이름도 다르다."""
    p = copy.deepcopy(SIGNED[0])
    p['interval_h'] = 500
    p['packages'] = [{'interval_h': 500, 'sop': 'SOP-X-1', 'name': '500 h 점검', 'parts': [{'part_no': 'P-X-1', 'qty': 2, 'name': '오링'}]},
                     {'interval_h': 1500, 'sop': 'SOP-X-2', 'name': '1,500 h 점검',
                      'parts': [{'part_no': 'P-X-1', 'qty': 2, 'name': '오링'}, {'part_no': 'P-X-2', 'qty': 1, 'name': '흡입 스트레이너'}]}]
    return p


def test_다른_문서의_정책도_간격_포함_관계만_맞으면_받는다():
    assert [k['interval_h'] for k in mp.policy(_pbl())['packages']] == [500, 1500]


@pytest.mark.parametrize('change, word', [
    (lambda p: p['packages'].__setitem__(1, dict(p['packages'][1], interval_h=1250)), '정수배'),
    (lambda p: p['packages'].__setitem__(1, dict(p['packages'][1], interval_h=500)), '겹치거나'),
    (lambda p: p.__setitem__('packages', p['packages'][1:]), '가장 짧은'),
    (lambda p: p['packages'][1].__setitem__('parts', p['packages'][1]['parts'][1:]), '포함'),     # 큰 패키지가 작은 것의 부품을 빠뜨림
    (lambda p: p.__setitem__('packages', []), '하나 이상'),
    (lambda p: p.__setitem__('tolerance_pct', 100), '허용 오차'),
])
def test_간격이_정수배가_아니거나_포함_관계가_깨지면_거절한다(change, word):
    p = _pbl()
    change(p)
    with pytest.raises(ValueError, match=word):
        mp.policy(p)


RULES = [{'rule': 'rule:pm-bundle-crew', 'applies': ['skill:sop-pm-14'],
          'tests': [{'variable': mp.CREW_VARIABLE, 'operator': '<', 'value': 4}]},
         {'rule': 'rule:other', 'applies': ['skill:sop-pm-11'], 'tests': [{'variable': 'spare_available', 'operator': '<', 'value': 1}]}]


@pytest.mark.parametrize('rules, skill, crew', [
    (RULES, 'skill:sop-pm-14', 4),
    (RULES, 'skill:sop-pm-11', None),                       # 그 SOP 에 인원 규칙이 없다
    ([dict(RULES[0], applies=[])], 'skill:any', 4),          # 대상이 없는 규칙은 모두에
])
def test_묶음_필요_인원은_그_SOP에_걸린_원문_규칙의_값이다(rules, skill, crew):
    assert mp.crew_required(rules, skill) == crew


def test_인원_규칙이_서로_다르면_오류다():
    with pytest.raises(ValueError, match='둘 이상'):
        mp.crew_required(RULES + [dict(RULES[0], tests=[{'variable': mp.CREW_VARIABLE, 'operator': '<', 'value': 5}])], 'skill:sop-pm-14')


def _bundle_context():
    window = {'id': 'W-1', 'basis': 'hours_at_next_window', 'starts_at': '2026-10-30T22:00:00Z'}
    row = lambda asset, since, peer: {'asset': asset, 'bundle_peer': peer, 'pm_interval_h': 2000, 'pm_tolerance_pct': 10,
                                       'pm_since_h': since, 'pm_total_h': since + 6000, 'night_window_id': 'W-1',
                                       'night_window_at': window['starts_at'], 'hours_at_next_window': since + 9,
                                       mp.CREW_VARIABLE: 2, 'service_position': 0}   # 다음 차례 = 2,000 h 패키지
    parts = [{'part_no': p, 'name': p, 'available': 10, 'on_hand': 10, 'reserved': 0}
             for p in {x['part_no'] for k in SIGNED[-1]['packages'] for x in k['parts'] if x.get('part_no')}]
    return {'records': [row('HYD-01', 1950, 'HYD-03'), row('HYD-03', 1880, 'HYD-01')], 'parts': parts}, window


def test_묶음_정비는_원문_규칙의_인원으로_부족을_계산하고_규칙이_없으면_실패한다():
    bundle = next(p for p in SIGNED if p['scope'] == 'bundle')
    context, window = _bundle_context()
    scoped = mp.scope(mp.policy(bundle), context, 'HYD-01', window, crew_required=3)      # 다른 공장 문서: 3명
    assert scoped['staffing'] == {'required': 3, 'available': 2, 'shortfall': 1, 'arrangement_required': True, 'confirmed': False}
    with pytest.raises(mp.ScopeError, match='정비 인원'):
        mp.scope(mp.policy(bundle), context, 'HYD-01', window)
