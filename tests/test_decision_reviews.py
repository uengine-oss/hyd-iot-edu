from copy import deepcopy
from types import SimpleNamespace
import pytest

from agentsvc import approval, cards, decide
from procsvc.decision_reviews import DecisionReviews
from procsvc.store import Store
from plantsim import thermal
from test_cards import BASE, DMN, SKILLS, TRADE
from test_forecast_model import snapshot, action
from test_forecast_source import kg


@pytest.fixture
def evaluation(monkeypatch):
    graph=kg(); model={'unit':thermal.UnitState(cooler_health=.43)}; skills=deepcopy(SKILLS)
    skills['skill:fan']['actions']=[dict(action('FAN_SET',100),param='fan_pct',min=0,max=100)]
    skills['skill:mix']['actions']=[dict(action('FAN_SET',100),param='fan_pct',min=0,max=100),
                                  dict(action('LOAD_SET',80),param='load_pct',min=60,max=100)]
    graph.dmn=lambda:DMN;graph.inputs=lambda:[];graph.skills=lambda ids:list(skills.values())
    graph.tradeoffs=lambda ids:TRADE;graph.precedents=lambda fm:[];graph.suppliers=lambda:{}
    graph.roles=lambda:[{'id':'role:x','name':'reviewer','level':2}]
    monkeypatch.setattr(decide,'_get_json',lambda url:snapshot(model['unit']))
    monkeypatch.setattr(decide,'gather_facts',lambda *a,**kw:(dict(BASE,pattern='COOLER_DEGRADATION'),[]))
    d={'id':'D','asset':'TEST-ASSET','origin':{'incident':'I','pattern':'COOLER_DEGRADATION',
       'cause':BASE['cause'],'failureMode':BASE['failure_mode']},'options':[{'id':'skill:mix'}],'state':'PENDING_APPROVAL',
       'facts':dict(BASE),'history':[]}
    return graph,d,model,skills


def test_changed_actions_are_predicted_and_rechecked_without_modifying_source(evaluation):
    graph,d,model,_=evaluation; original=deepcopy(d)
    reviewed=approval.preview(graph,None,d,'skill:mix',{'fan_pct':95,'load_pct':78})
    opt=reviewed['options'][0]
    assert d==original and opt['actions'][0]['value']==95 and opt['actions'][1]['value']==78
    assert opt['forecastContext']['actions']==opt['actions']
    assert opt['reviewed_choice']['reference_actions'][0]['value']==100
    assert approval.assess(graph,None,reviewed,'skill:mix','role:x')['allowed']
    other=approval.preview(graph,None,d,'skill:mix',{'fan_pct':70,'load_pct':90})
    assert other['options'][0]['forecast']!=opt['forecast']


@pytest.mark.parametrize('parameters',[{'fan_pct':True},{'fan_pct':float('nan')},{'fan_pct':101},
    {'load_pct':50},{'plc_mode':'REMOTE_AUTO'},{'pump':'B'}])
def test_invalid_or_non_action_parameters_cannot_enter_review(evaluation,parameters):
    graph,d,_,_=evaluation
    with pytest.raises(ValueError): approval.preview(graph,None,d,'skill:mix',parameters)


def test_policy_change_underneath_an_override_is_not_hidden(evaluation):
    graph,d,_,skills=evaluation
    reviewed=approval.preview(graph,None,d,'skill:mix',{'fan_pct':95})
    skills['skill:mix']['actions'][0]['value']=99  # effective 95 unchanged, reference policy changed
    result=approval.assess(graph,None,reviewed,'skill:mix','role:x')
    assert not result['allowed'] and any('reviewed_choice' in r for r in result['reasons'])


def test_compound_fault_still_blocks_changed_action_preview(evaluation):
    graph,d,model,_=evaluation;model['unit'].bearing_wear=.8
    reviewed=approval.preview(graph,None,d,'skill:mix',{'fan_pct':95})
    assert not reviewed['options'][0]['feasible']
    assert not approval.assess(graph,None,reviewed,'skill:mix','role:x')['allowed']


@pytest.mark.parametrize('missing',['steps','approver'])
def test_new_review_cannot_hide_missing_sop_consent_basis(evaluation,missing):
    graph,d,_,skills=evaluation
    # Missing policy evidence cannot be legitimized by making a fresh review.
    if missing=='steps':skills['skill:mix']['steps']=[]
    else:skills['skill:mix']['approver']={}
    with pytest.raises(ValueError,match='근거가 불완전'):
        approval.preview(graph,None,d,'skill:mix',{'fan_pct':95})


def test_preview_is_immutable_scoped_and_survives_store_restart(tmp_path,evaluation):
    graph,d,_,_=evaluation;store=Store(tmp_path/'process.sqlite3');book={'D':d}
    incidents={'I':SimpleNamespace(asset=d['asset'],state='AWAITING_APPROVAL')}
    scope={'kind':'instance','workitem':'W','instance':'P','tenant':'hyd'}
    service=DecisionReviews(store,book,incidents,lambda source,opt,params:approval.preview(graph,None,source,opt,params))
    review=service.create('D','skill:mix',{'fan_pct':95},scope)
    assert book['D'] is d and d['state']=='PENDING_APPROVAL'
    assert review['execution_authorized'] is False
    store.db.close();store=Store(tmp_path/'process.sqlite3')
    service=DecisionReviews(store,book,incidents,None)
    loaded=service.snapshot(review['id'],'D','skill:mix',scope)
    assert loaded['review_id']==review['id'] and loaded['original_decision']==d
    with pytest.raises(ValueError,match='덮어쓸'):
        store.put_review(dict(review,execution_authorized=True))
    with pytest.raises(ValueError,match='검토본'):
        service.snapshot(review['id'],'D','skill:mix',dict(scope,workitem='another'))
    d['explanation']='changed source decision'
    with pytest.raises(ValueError,match='원래 결정'):
        service.snapshot(review['id'],'D','skill:mix',scope)
    store.db.close()


def test_review_creation_does_not_survive_source_change_during_io(tmp_path,evaluation):
    graph,d,_,_=evaluation;store=Store(tmp_path/'s.sqlite3')
    def changed(source,opt,params):
        preview=approval.preview(graph,None,source,opt,params);d['state']='REJECTED';return preview
    service=DecisionReviews(store,{'D':d},{'I':SimpleNamespace(asset=d['asset'],state='AWAITING_APPROVAL')},changed)
    with pytest.raises(ValueError):service.create('D','skill:mix',{'fan_pct':95},{'kind':'legacy','incident':'I'})
    assert store.db.execute('select count(*) from decision_reviews').fetchone()[0]==0
    store.db.close()
