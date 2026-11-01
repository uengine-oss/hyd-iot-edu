"""수집 계약(common/hydcommon/daq_contract.py) — 태그 목록 · 보고 주기 · 관측 여유 한 곳(G3b-24 · 29 · G4-14)."""
import pytest

from hydcommon import daq_contract as d


def test_모든_태그는_세_무리_중_정확히_하나에_있다():
    groups = [d.ALWAYS, d.AUX, set(d.DEADBAND)]
    assert all(sum(tag in g for g in groups) == 1 for tag in d.TAGS) and set().union(*groups) == set(d.TAGS)


@pytest.mark.parametrize('tag, profile, seconds', [
    ('TS1', 'lite', 1.), ('LoadSP', 'lite', 1.),           # 지속 판정 입력은 lite 에서도 매초
    ('TS2', 'lite', 30.), ('EPS1', 'lite', 10.),            # 보조 30 초 · 데드밴드 10 초 하트비트
    ('TS2', 'full', 1.), ('EPS1', 'full', 1.),
    ('PLC_STATE', 'lite', 1.), ('PLC_STATE', 'full', 1.),   # G3b-29: 상태는 매초 발행된다(10초가 아니다)
])
def test_보고_주기는_태그와_수집_방식으로_정한다(tag, profile, seconds):
    assert d.reporting_interval(tag, profile) == seconds


@pytest.mark.parametrize('tag, profile', [('TS1', 'fast'), ('XX1', 'lite')])
def test_없는_수집_방식이나_태그는_거절한다(tag, profile):
    with pytest.raises(ValueError):
        d.reporting_interval(tag, profile)


@pytest.mark.parametrize('env, ok', [({'DAQ_PROFILE': 'lite'}, True), ({'DAQ_PROFILE': 'full'}, True),
                                     ({}, False), ({'DAQ_PROFILE': 'Lite'}, False), ({'DAQ_PROFILE': 'fulll'}, False)])
def test_수집_방식은_compose_값_그대로이고_다른_글자를_lite로_바꾸지_않는다(env, ok):
    if ok:
        assert d.profile_from_env(env) == env['DAQ_PROFILE']
    else:
        with pytest.raises(ValueError, match='DAQ_PROFILE'):
            d.profile_from_env(env)
