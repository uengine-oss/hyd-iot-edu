from datetime import datetime, timedelta, timezone
import pytest
from agentsvc import forecasting
from test_forecast_model import snapshot, action
from plantsim import thermal
from types import SimpleNamespace
from hydcommon.forecast import MODEL_ID, MODEL_REVISION, MODEL_SCOPE


def kg(asset='TEST-ASSET'):
    return SimpleNamespace(forecast_model=lambda requested: dict(asset=asset, model_id=MODEL_ID,
        model_revision=MODEL_REVISION, scope=MODEL_SCOPE, horizon_s=900))


def test_forecast_reads_source_and_retains_provenance_without_execution(monkeypatch):
    source=snapshot(thermal.UnitState(leak=0.15))
    calls=[]
    monkeypatch.setattr(forecasting.decide,'_get_json',lambda url:(calls.append(url),source)[1])
    result=forecasting.current(kg(),'TEST-ASSET',[action('PUMP_SELECT','B')],900)
    assert result['values']['ps1']==182 and result['values']['ts1_steady'] < 55
    assert len(calls)==1 and result['provenance']['asset']=='TEST-ASSET'
    assert result['execution_authorized'] is False


@pytest.mark.parametrize('age',[60,-30])
def test_stale_or_future_source_cannot_be_used(monkeypatch,age):
    source=snapshot(thermal.UnitState());source['t']=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()
    monkeypatch.setattr(forecasting.decide,'_get_json',lambda url:source)
    with pytest.raises(ValueError,match='stale or future'):
        forecasting.current(kg(),'TEST-ASSET',[],900)


def test_forecast_cannot_accept_another_assets_state(monkeypatch):
    source=snapshot(thermal.UnitState())
    monkeypatch.setattr(forecasting.decide,'_get_json',lambda url:source)
    with pytest.raises(ValueError,match='asset'):
        forecasting.current(kg('DIFFERENT-ASSET'),'DIFFERENT-ASSET',[],900)
