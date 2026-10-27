from copy import deepcopy
import pytest
from procsvc import manual_extraction as extraction

SOURCE={'pages':[{'page':1,'text':'조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있으므로 다른 조치와 비교한다.'}]}


def proposal():
    return {'procedures':[{'id':pid,'link':{'kind':'control','relation':'MITIGATED_BY','failureMode':'fm:cooler'}} for pid in ('SOP-COOL-11','SOP-COOL-12')],
        'knowledge':{'rules':[{'table':'dt:compliance','effect':'WARN','applies_to':['SOP-COOL-11','SOP-COOL-12'],
             'tests':[{'input':'in:forecast-ts1','operator':'>=','value':55,'unit':'℃'}]}]}}


@pytest.mark.parametrize('change',[
    lambda p:p['knowledge'].update(rules=[]),
    lambda p:p['knowledge']['rules'][0].update(effect='EXCLUDE'),
    lambda p:p['knowledge']['rules'][0]['tests'][0].update(value=65),
    lambda p:p['knowledge']['rules'][0]['tests'][0].update(operator='>'),
    lambda p:p['knowledge']['rules'][0].update(applies_to=['SOP-COOL-11']),
    lambda p:p['knowledge']['rules'][0]['tests'].append({'input':'in:pattern','operator':'==','value':'other'})],
    ids=['missing','wrong-effect','wrong-threshold','wrong-boundary','missing-target','extra-guard'])
def test_source_comparison_cannot_disappear_or_change_meaning(change):
    p=proposal();change(p)
    with pytest.raises(ValueError,match='예측 유온'):extraction.check_forecast_warnings(p,SOURCE)


def test_source_warning_is_kept_without_inventing_a_rule_for_other_text():
    extraction.check_forecast_warnings(proposal(),SOURCE)
    extraction.check_forecast_warnings({'knowledge':{}},{'pages':[{'page':1,'text':'TS1 55 ℃ 미만이면 성공이다.'}]})
    changed=deepcopy(SOURCE);changed['pages'][0]['text']=changed['pages'][0]['text'].replace('55','57.5')
    p=proposal();p['knowledge']['rules'][0]['tests'][0]['value']=57.5
    extraction.check_forecast_warnings(p,changed)


def test_old_execution_contract_is_not_rewritten_by_the_new_checker():
    for version in ('2.15','2.17','legacy'):
        assert not extraction._forecast_contract({'proc_def_version':version})
    assert extraction._forecast_contract({'proc_def_version':'2.18'})
    p={'procedures':[],'knowledge':{'rules':[]}}
    assert extraction.content_issues(p,SOURCE,None,forecast_scope=False)==[]
    assert '예측 유온' in extraction.content_issues(p,SOURCE,None)[0]
