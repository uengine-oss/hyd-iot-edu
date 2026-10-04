import pytest

from det.patterns import DefinitionError, Expression, compile_catalog, compile_pattern
from det.pattern_runtime import PatternRuntime


def definition(**changes):
    return dict(id='pattern:changed', code='CHANGED_PATTERN', detectionMode='held', severity='HIGH',
                rule='VS1 > 1.2 and slope(VS1) > 0', clearRule='VS1 < 1.1',
                holdSeconds=60, clearHoldSeconds=40, slopeWindowSeconds=60,
                tests=[dict(variable='vs1', operator='>', value=1.2),
                       dict(variable='vs1_slope', operator='>', value=0)]) | changes


@pytest.mark.parametrize('text', ["__import__('os').system('whoami')", 'VS1.__class__ == 1',
                                  'unknown > 1', 'VS1 + 1 > 2', 'VS1 > float("nan")',
                                  'VS1 > True', 'VS1 > 1e999', '0 < VS1 < 1',
                                  'slope(VS1, 2) > 0', "PLC.state > 'RUN'", 'VS1 > "1"'])
def test_unsupported_expressions_are_explicit_errors(text):
    with pytest.raises(DefinitionError):Expression(text)


def test_boolean_grammar_collects_inputs_and_does_not_hide_missing_branch():
    expr = Expression("PLC.state == 'RUN' and (PS1 < 165 or FS1 < 8) and not LoadSP < 80")
    assert expr.inputs == {'PLC_STATE','PS1','FS1','LoadSP'}
    assert expr.evaluate({'PLC_STATE':'RUN','PS1':160,'FS1':9,'LoadSP':90}, {}) is True
    with pytest.raises(KeyError):expr.evaluate({'PLC_STATE':'STOP'}, {})


@pytest.mark.parametrize('changes', [{'holdSeconds':0}, {'clearHoldSeconds':None}, {'slopeWindowSeconds':float('nan')},
                                    {'severity':'FAKE'}, {'tests':[]}, {'rule':None}, {'code':'bad-name'},
                                    {'detectionMode':'trip'}])
def test_incomplete_or_conflicting_definition_rejected(changes):
    with pytest.raises(DefinitionError):compile_pattern(definition(**changes))


def test_reporting_contract_and_slope_resolution_are_checked():
    d = definition(rule='TS2 > 10', clearRule='TS2 < 9', tests=[dict(variable='ts2',operator='>',value=10)])
    with pytest.raises(DefinitionError, match='periodic'):compile_catalog([d])
    assert compile_catalog([d], profile='full')['CHANGED_PATTERN'].inputs == {'TS2'}
    p = compile_pattern(definition())
    with pytest.raises(DefinitionError, match='intervals'):p.validate_reporting('lite', 40)
    with pytest.raises(DefinitionError, match='duplicate'):compile_catalog([definition(),definition()])


def test_tests_are_executable_source_and_rule_remains_human_summary():
    pattern = compile_pattern(definition(rule='This prose is documentation, not code.'))
    assert pattern.rule.evaluate({'VS1':1.3}, {'VS1':.01}) is True
    with pytest.raises(DefinitionError, match='operator'):
        compile_pattern(definition(tests=[dict(variable='vs1',operator='contains',value=1)]))


def frame(runtime, t, value, asset='A', gap=False):
    if not gap: runtime.observe(asset,'VS1',value,t)
    return runtime.observe(asset,'TS1',48,t)


def test_new_pattern_code_threshold_and_duration_change_results():
    runtime = PatternRuntime([definition()], time_scale=20)
    events = [e for t in range(6) for e in frame(runtime,t,1.21+t*.01)]
    assert [e['state'] for e in events] == ['RAISE']
    assert events[0]['pattern']=='CHANGED_PATTERN'
    assert events[0]['evidence']['definition']['revision']==runtime.catalog['CHANGED_PATTERN'].revision
    changed = definition(holdSeconds=100)
    changed['rule']='VS1 > 1.4 and slope(VS1) > 0'; changed['tests'][0]['value']=1.4
    second=PatternRuntime([changed],time_scale=20)
    assert not [e for t in range(6) for e in frame(second,t,1.21+t*.01)]
    assert not [e for t in range(6,11) for e in frame(second,t,1.41+(t-6)*.01)]
    assert frame(second,11,1.5)[0]['state']=='RAISE'


def test_catalog_replacement_atomic_and_candidate_clock_restarts():
    runtime=PatternRuntime([definition()])
    for t in range(3):frame(runtime,t,1.3+t*.01)
    old=runtime.catalog['CHANGED_PATTERN'].revision
    with pytest.raises(DefinitionError):runtime.replace([definition(holdSeconds=-1)])
    assert runtime.catalog['CHANGED_PATTERN'].revision==old
    runtime.replace([definition(holdSeconds=100)])
    assert not [e for t in range(3,8) for e in frame(runtime,t,1.3+t*.01)]
    assert frame(runtime,8,1.4)[0]['state']=='RAISE'


def test_raised_revision_pinned_until_clear_even_after_removal():
    runtime=PatternRuntime([definition()])
    raised=[e for t in range(5) for e in frame(runtime,t,1.3+t*.01)][0]
    runtime.replace([definition(id='new', code='ANOTHER_PATTERN',clearRule='VS1 < .1')])
    events=[e for t in range(5,10) for e in frame(runtime,t,.9)]
    assert [(e['state'],e['alertId']) for e in events]==[('CLEAR',raised['alertId'])]
    assert events[0]['evidence']['definition']['revision']==raised['evidence']['definition']['revision']
    assert 'CHANGED_PATTERN' not in runtime.assets['A'].runs


def test_gap_bad_quality_and_missing_input_cannot_clear_raised_alert():
    runtime=PatternRuntime([definition()])
    raised=[e for t in range(5) for e in frame(runtime,t,1.3+t*.01)][0]
    for t in range(5,10):assert frame(runtime,t,.9,gap=True)==[]
    assert runtime.assets['A'].runs['CHANGED_PATTERN'].state.alert_id==raised['alertId']
    runtime.observe('A','VS1',None,10,quality='bad')
    assert runtime.observe('A','TS1',48,10)==[]
    assert runtime.describe()['assets']['A']['CHANGED_PATTERN']['quality']['status']=='UNKNOWN'
    events=[e for t in range(11,17) for e in frame(runtime,t,.9)]
    assert [(e['state'],e['alertId']) for e in events]==[('CLEAR',raised['alertId'])]


def test_assets_and_duplicate_late_future_records_are_independent():
    runtime=PatternRuntime([definition()])
    for t in range(3):frame(runtime,t,1.3+t*.01)
    assert runtime.observe('A','VS1',9,1)==[]
    assert runtime.observe('A','VS1',9,999,now=3)==[]
    assert runtime.assets['A'].runs['CHANGED_PATTERN'].state.phase=='IDLE'
    for t in range(5):assert frame(runtime,t,.6,asset='B')==[]
    assert not runtime.assets['B'].runs['CHANGED_PATTERN'].state.alert_id
