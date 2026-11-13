"""경보 패턴 정의(it/detector/det/patterns.py) — 그래프의 TESTS · clearRule 을 닫힌 문법으로만 실행한다(G5b-02 · G3a-10).

판정 대상은 실제 시드의 세 패턴(it/neo4j/v2/instances.cypher 의 쿨러 · 펌프 · 팬과 같은 꼴)이다 — 경계값에서 켜지는지 본다.
"""
import pytest

from det.patterns import DefinitionError, Expression, compile_catalog, compile_pattern

COOLER = {'id': 'pattern:cooler-degradation', 'code': 'COOLER_DEGRADATION', 'severity': 'HIGH', 'detectionMode': 'held',
          'rule': 'TS1 > 55 and CE < 70 and slope(TS1) > 0', 'clearRule': 'TS1 < 52 and slope(TS1) <= 0',
          'holdSeconds': 60, 'clearHoldSeconds': 60, 'slopeWindowSeconds': 60,
          'tests': [{'variable': 'ts1', 'operator': '>', 'value': 55}, {'variable': 'ce', 'operator': '<', 'value': 70},
                    {'variable': 'ts1_slope', 'operator': '>', 'value': 0}]}
PUMP = {'id': 'pattern:pump-leakage', 'code': 'PUMP_LEAKAGE', 'severity': 'HIGH', 'detectionMode': 'held',
        'rule': "PLC.state == 'RUN' and PS1 < 165", 'clearRule': "PLC.state == 'RUN' and ((PS1 >= 168 and FS1 >= 8) or LoadSP < 80)",
        'holdSeconds': 60, 'clearHoldSeconds': 60, 'slopeWindowSeconds': 60,
        'tests': [{'variable': 'plc_state', 'operator': '==', 'value': 'RUN'}, {'variable': 'ps1', 'operator': '<', 'value': 165},
                  {'variable': 'fs1', 'operator': '<', 'value': 8.0}, {'variable': 'load', 'operator': '>=', 'value': 80}]}


@pytest.mark.parametrize('ts1, ce, slope, fires', [(55.1, 69, 0.01, True), (55.0, 69, 0.01, False), (60, 70, 0.01, False),
                                                    (60, 50, 0.0, False)])
def test_쿨러_패턴은_TESTS_경계에서_켜진다(ts1, ce, slope, fires):
    p = compile_pattern(COOLER)
    assert p.rule.evaluate({'TS1': ts1, 'CE': ce}, {'TS1': slope}) is fires


@pytest.mark.parametrize('state, ps1, fs1, load, fires', [('RUN', 164, 7.9, 80, True), ('STOP', 164, 7.9, 80, False),
                                                          ('RUN', 165, 7.9, 80, False), ('RUN', 164, 7.9, 79.9, False)])
def test_펌프_패턴은_운전_중_압력_유량_부하로_켜진다(state, ps1, fs1, load, fires):
    p = compile_pattern(PUMP)
    assert p.rule.evaluate({'PLC_STATE': state, 'PS1': ps1, 'FS1': fs1, 'LoadSP': load}, {}) is fires


@pytest.mark.parametrize('text', ['__import__("os")', 'TS1 > x', 'TS1 + 1 > 2', 'slope(TS1, 2) > 0', 'TS1 > 1 > 0', "PLC.state > 'RUN'",
                                  'TS1 > "55"', 'NOPE > 1', 'x' * 3000, ''])
def test_닫힌_문법_밖의_식은_정의_오류다(text):
    with pytest.raises(DefinitionError):
        Expression(text)


def test_빠진_값은_짧게_끊지_않고_오류다():
    p = compile_pattern(COOLER)
    with pytest.raises(ValueError):
        p.rule.evaluate({'TS1': 50.0, 'CE': None}, {'TS1': 0.1})        # TS1 만으로 거짓이어도 CE 미상은 미상


@pytest.mark.parametrize('change, word', [
    ({'detectionMode': 'plc-trip'}, 'held'), ({'code': 'bad code'}, 'code'), ({'severity': 'WARNING'}, 'severity'),
    ({'tests': []}, 'TESTS'), ({'tests': [{'variable': 'nope', 'operator': '>', 'value': 1}]}, 'variable'),
    ({'tests': [{'variable': 'ts1', 'operator': '=~', 'value': 1}]}, 'operator'), ({'holdSeconds': 0}, 'holdSeconds'),
    ({'rule': ''}, 'summary'), ({'clearRule': 'TS1 <'}, 'syntax'),
])
def test_계약이_빠진_정의는_이름을_대며_거절한다(change, word):
    with pytest.raises(DefinitionError, match=word):
        compile_pattern(dict(COOLER, **change))


def test_정의_판본은_실행에_쓰는_칸으로만_정해진다():
    a, b = compile_pattern(COOLER), compile_pattern(dict(COOLER, tests=list(reversed(COOLER['tests']))))
    assert a.revision == b.revision and a.revision != compile_pattern(dict(COOLER, holdSeconds=61)).revision


@pytest.mark.parametrize('profile, scale, ok', [('lite', 20, True), ('full', 20, True), ('lite', 40, False)])
def test_기울기_창은_보고_주기_두_번을_배속으로_담아야_한다(profile, scale, ok):
    if ok:
        assert set(compile_catalog([COOLER, PUMP], profile, scale)) == {'COOLER_DEGRADATION', 'PUMP_LEAKAGE'}
    else:
        with pytest.raises(DefinitionError, match='slope window'):
            compile_catalog([COOLER], profile, scale)          # 60 설비 초 창 < 2 × 1 s × 40


def test_틀린_패턴_하나는_그것만_빠지고_나머지는_감지에_남는다():
    """학생이 패턴 하나를 잘못 쓰면 수업 패턴까지 감지가 모두 멈추던 것(2026-11-14). 까닭은 뺀 목록에 남는다."""
    broken = dict(PUMP, holdSeconds=-1)
    rejected = []
    assert set(compile_catalog([COOLER, broken], 'lite', 20, rejected)) == {'COOLER_DEGRADATION'}
    assert [(r['code'], bool(r['reason'])) for r in rejected] == [('PUMP_LEAKAGE', True)]
    with pytest.raises(DefinitionError):
        compile_catalog([COOLER, broken], 'lite', 20)            # 뺀 목록을 받지 않는 호출은 예전처럼 첫 오류에서 멈춘다
    with pytest.raises(DefinitionError, match='no valid pattern'):
        compile_catalog([broken], 'lite', 20, [])                # 맞는 패턴이 하나도 없으면 적용하지 않는다


@pytest.mark.parametrize('rows', [[], [COOLER, COOLER], [COOLER] * 65])
def test_목록은_1_64개이고_겹치면_안_된다(rows):
    with pytest.raises(DefinitionError):
        compile_catalog(rows, 'lite', 20)
