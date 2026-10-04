import pytest
from fastapi import HTTPException
from agentsvc import main
from agentsvc.runs import RunRegistry
from test_dmn_mcp import FakeKG,FakeTSDB


@pytest.fixture
def evaluator(monkeypatch):
    monkeypatch.setattr(main,'runs',RunRegistry())
    monkeypatch.setattr(main,'kg',FakeKG())
    monkeypatch.setattr(main,'tsdb',FakeTSDB())
    monkeypatch.setattr(main.decidelib,'_get_json',lambda *_:{'route':'response'})
    monkeypatch.setattr(main.mcp_prom,'freshness',lambda *_:{'ok':True})
    monkeypatch.setattr(main.llm,'summarize',lambda card,fallback:(fallback,'fixture'))
    monkeypatch.setattr(main,'submit_card',lambda *_:pytest.fail('read-only evaluator submitted card'))
    return main.EvaluationReq(alert={'state':'RAISE','alertId':'fixture-readonly','asset':'A','pattern':'X'})


def test_supported_evaluation_does_not_submit_card_or_decision(evaluator,monkeypatch):
    calls=[]
    def decide(*args,**kwargs):
        calls.append(kwargs)
        assert kwargs['do_submit'] is False
        return {'status':'EVALUATED','asset':'A','origin':kwargs['origin'],
                'result':{'options':[{'id':'supported-fixture'}],'rankRule':'fixture'}}
    monkeypatch.setattr(main.decidelib,'decide',decide)
    first=main.evaluate_without_submission(evaluator)
    second=main.evaluate_without_submission(evaluator)
    assert first['status']==second['status']=='EVALUATED' and first['id']!=second['id']
    assert first['incidentId'] is None and first['evaluation']['options']==[{'id':'supported-fixture'}]
    assert first['card']['alert']==evaluator.alert and len(calls)==2
    assert not any(step['name']=='submit' for step in first['steps'])


def test_unavailable_source_is_withheld_without_decision(evaluator,monkeypatch):
    monkeypatch.setattr(main.tsdb,'evaluate',lambda *_:{})
    monkeypatch.setattr(main.decidelib,'decide',lambda *a,**kw:pytest.fail('unknown source evaluated decision'))
    result=main.evaluate_without_submission(evaluator)
    assert result['status']=='WITHHELD' and result['evaluation'] is None and result['incidentId'] is None


@pytest.mark.parametrize('alert',[{}, {'state':'CLEAR','alertId':'x','asset':'A','pattern':'X'},
                                 {'state':'RAISE','alertId':'x','asset':'','pattern':'X'}])
def test_invalid_alert_rejected_before_evaluation(alert):
    with pytest.raises(HTTPException) as caught:main.evaluate_without_submission(main.EvaluationReq(alert=alert))
    assert caught.value.status_code==400


def test_concurrent_evaluation_ids_and_latest_index_survive_eviction():
    from concurrent.futures import ThreadPoolExecutor
    registry=RunRegistry(keep=3);alert={'alertId':'same','asset':'A'}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:registry.force_new(alert),range(40)))
    assert len({r.id for r in results})==40 and len(registry.all())==3
    assert registry.by_alert('same') is registry.all()[0]
    assert registry.create_if_new(alert) is None
