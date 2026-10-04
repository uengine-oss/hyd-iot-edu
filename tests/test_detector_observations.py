import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from det import cep, main
from det.observations import Observations
from det.pattern_runtime import PatternRuntime


@pytest.mark.parametrize('scale', [1, 2, 20])
def test_raise_and_clear_holds_restart_after_unobserved_gap(scale):
    st = cep.CepState()
    def tick(t, recovering=False):
        return cep.evaluate(st, 'A', t*scale, 50 if recovering else 58, 40,
                            -.02 if recovering else .02, max_gap_s=3*scale)
    assert tick(0) is None
    assert tick(100) is None and st.phase == 'CANDIDATE'
    raised = None
    for t in range(101, 162):
        raised = tick(t) or raised
    assert raised and raised['state'] == 'RAISE'
    aid = raised['alertId']
    assert tick(163, True) is None
    assert tick(300, True) is None and st.phase == 'CLEARING'
    assert st.alert_id == aid
    cleared = None
    for t in range(301, 362):
        cleared = tick(t, True) or cleared
    assert cleared and cleared['state'] == 'CLEAR' and cleared['alertId'] == aid


def test_heartbeat_is_wall_time_and_unknown_does_not_clear_alert():
    obs = Observations('lite', 2)
    obs.record('VS1', 100, 1.4)
    assert obs.problems(['VS1'], 103, 103) == {}
    assert obs.problems(['VS1'], 104, 104) == {'VS1': 'STALE'}
    assert obs.limit('PLC_STATE') == 12  # separate status heartbeat
    assert Observations('full', 2).limit('VS1') == 3
    st = cep.CepState(phase='CLEARING', since=10, alert_id='existing')
    cep.interrupt(st)
    assert st.phase == 'RAISED' and st.alert_id == 'existing' and st.since is None


@pytest.fixture
def stream(monkeypatch):
    epoch = 1_800_000_000.
    clock = [epoch]
    monkeypatch.setattr(main, 'time', SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(main, 'assets', {})
    monkeypatch.setattr(main, 'state', {'kafka': True, 't0': None, 'tags': 0, 'waves': 0, 'alerts': 0})
    monkeypatch.setattr(main, 'TIME_SCALE', 20)
    monkeypatch.setattr(main, 'DAQ_PROFILE', 'lite')
    rows = json.loads((Path(__file__).parent/'fixtures/detector-patterns.json').read_text(encoding='utf8'))
    monkeypatch.setattr(main, 'runtime', PatternRuntime(rows))
    monkeypatch.setattr(main, 'store', None)
    messages = []
    async def send(topic, key, value):messages.append((topic, value))
    prod = SimpleNamespace(send=send)
    def stamp(t):return datetime.fromtimestamp(epoch+t, timezone.utc).isoformat()
    def tag(t, name, value, quality='good', event=None):
        clock[0] = epoch+t
        asyncio.run(main.on_tag(prod, dict(asset='FIXTURE', name=name, v=value, q=quality, t=stamp(t if event is None else event))))
    def status(t, state, event=None):
        clock[0] = epoch+t
        asyncio.run(main.on_status(prod, dict(asset='FIXTURE', state=state, t=stamp(t if event is None else event), trip='OVERTEMP')))
    def frame(t):
        tag(t, 'CE', 40)
        tag(t, 'TS1', 57 + t*.01)
    return SimpleNamespace(tag=tag, status=status, frame=frame, messages=messages, clock=clock,
                           asset=lambda: main.get('FIXTURE'))


def test_detector_does_not_bridge_clock_gap_then_recovers(stream):
    stream.frame(0);stream.frame(1)
    assert stream.asset().cep_state.phase == 'CANDIDATE'
    stream.frame(10)
    assert stream.asset().cep_state.phase == 'IDLE'  # slope restarted too
    assert not [v for topic,v in stream.messages if topic == main.topics.K_ALERTS]
    for t in range(11, 15):stream.frame(t)
    alerts = [v for topic,v in stream.messages if topic == main.topics.K_ALERTS]
    assert len(alerts) == 1 and alerts[0]['state'] == 'RAISE'
    assert alerts[0]['evidence']['observation']['time_scale'] == 20


def test_missing_or_stale_input_is_unknown_not_default_healthy_value(stream):
    for t in range(6):stream.tag(t, 'TS1', 57+t*.1)
    assert stream.asset().data_quality['COOLER_DEGRADATION']['problems']['CE'] == 'MISSING'
    assert stream.asset().score is None
    stream.tag(6, 'CE', 40)
    for t in range(6, 9):stream.tag(t, 'TS1', 58+t*.1)
    stream.tag(10, 'TS1', 60)
    assert stream.asset().data_quality['COOLER_DEGRADATION']['problems']['CE'] == 'STALE'
    assert stream.asset().cep_state.phase == 'IDLE'
    assert not [v for topic,v in stream.messages if topic == main.topics.K_ALERTS]


@pytest.mark.parametrize('value,quality', [(None,'good'), (float('nan'),'good'), (float('inf'),'good'), (True,'good'), (60,'bad')])
def test_bad_measurement_interrupts_pending_hold(stream, value, quality):
    stream.frame(0);stream.frame(1)
    stream.tag(2, 'CE', value, quality)
    assert stream.asset().cep_state.phase == 'IDLE'
    assert 'CE' not in stream.asset().latest
    assert stream.asset().observations.view(stream.clock[0])['CE']['value'] is None


def test_old_duplicate_conflicting_and_future_events_do_not_accumulate_time(stream):
    stream.frame(0);stream.frame(1)
    old = stream.asset().latest['TS1']
    stream.tag(2, 'TS1', 99, event=0)
    assert stream.asset().latest['TS1'] == old
    stream.tag(2, 'TS1', old, event=1)
    assert stream.asset().cep_state.phase == 'CANDIDATE'
    stream.tag(2, 'TS1', old+1, event=1)
    assert stream.asset().cep_state.phase == 'IDLE'
    stream.tag(3, 'TS1', 99, event=100)
    assert stream.asset().observations.samples['TS1']['time'] < stream.clock[0]
    stream.frame(4)
    assert stream.asset().latest['TS1'] == 57.04


def test_invalid_status_does_not_clear_trip_and_late_status_does_not_overwrite(stream):
    stream.status(1, 'TRIP')
    aid = stream.asset().trip_state.alert_id
    stream.status(2, None)
    assert stream.asset().trip_state.tripped and stream.asset().trip_state.alert_id == aid
    stream.status(3, 'RUN', event=0)
    assert stream.asset().trip_state.tripped
    stream.status(4, 'RUN')
    alerts = [v for topic,v in stream.messages if topic == main.topics.K_ALERTS]
    assert len(alerts) == 2 and alerts[1]['state'] == 'CLEAR' and alerts[1]['alertId'] == aid


def test_old_positive_slope_expires_without_new_vibration_sample(stream):
    stream.tag(0, 'VS1', 1.3);stream.frame(0)
    stream.tag(1, 'VS1', 1.4);stream.frame(1)
    assert stream.asset().fan_state.phase == 'CANDIDATE'
    for t in range(2, 6):stream.frame(t)
    assert stream.asset().data_quality['FAN_VIBRATION']['problems']['slope(VS1)'] == 'INSUFFICIENT_WINDOW'
    assert not [v for topic,v in stream.messages if topic == main.topics.K_ALERTS and v['pattern']=='FAN_VIBRATION']


def test_pump_requires_observed_running_state_and_fresh_inputs(stream):
    def frame(t):
        for name,value in [('PS1',160),('FS1',7),('LoadSP',90),('TS1',48)]:stream.tag(t,name,value)
    for t in range(5):frame(t)
    assert stream.asset().data_quality['PUMP_LEAKAGE']['problems']['PLC_STATE'] == 'MISSING'
    stream.status(5,'RUN')
    for t in range(5,10):frame(t)
    alerts=[v for topic,v in stream.messages if topic == main.topics.K_ALERTS]
    assert len(alerts)==1 and alerts[0]['pattern']=='PUMP_LEAKAGE'
    for t in range(10,19):frame(t)
    assert stream.asset().data_quality['PUMP_LEAKAGE']['problems']['PLC_STATE'] == 'STALE'
    assert stream.asset().pump_state.phase=='RAISED'


def test_fan_fresh_ramp_then_stale_window_then_fresh_recovery(stream):
    for t in range(5):
        stream.tag(t,'VS1',1.3+.05*t);stream.tag(t,'TS1',48)
    assert stream.asset().fan_state.phase=='RAISED'
    aid=stream.asset().fan_state.alert_id
    for t in range(5,9):stream.tag(t,'TS1',48)
    assert stream.asset().fan_state.phase=='RAISED' and stream.asset().fan_state.alert_id==aid
    assert stream.asset().data_quality['FAN_VIBRATION']['problems']['slope(VS1)']=='INSUFFICIENT_WINDOW'
    for t in range(9,15):
        stream.tag(t,'VS1',1.-.01*t);stream.tag(t,'TS1',48)
    alerts=[v for topic,v in stream.messages if topic==main.topics.K_ALERTS]
    assert [v['state'] for v in alerts]==['RAISE','CLEAR'] and all(v['alertId']==aid for v in alerts)


@pytest.mark.parametrize('scale', [1, 2, 20])
def test_lite_daq_to_detector_preserves_slow_fan_ramp_and_clear(stream, monkeypatch, scale):
    from plantsim.daq import DaqFilter
    monkeypatch.setattr(main, 'TIME_SCALE', scale)
    main.runtime.time_scale = scale
    daq = DaqFilter('lite')
    for t in range(150):
        # Plant order: TS1 precedes VS1. Every increment is below the old .02 deadband.
        values = {'TS1': 48, 'VS1': 1.201 + t*.0001 if t < 75 else 1. - (t-75)*.0001, 'CE': 84}
        for name, value in daq.select('FIXTURE', values, t).items():
            stream.tag(t, name, value)
    alerts = [v for topic,v in stream.messages if topic==main.topics.K_ALERTS and v['pattern']=='FAN_VIBRATION']
    assert [v['state'] for v in alerts] == ['RAISE', 'CLEAR']
    assert alerts[0]['alertId'] == alerts[1]['alertId']
    assert stream.asset().data_quality['FAN_VIBRATION']['status'] == 'VALID'


def test_fan_clear_uses_continuous_hysteresis_not_sign_of_normal_noise(stream):
    for t in range(5):
        stream.tag(t, 'VS1', 1.3+t*.02);stream.tag(t, 'TS1', 48)
    aid = stream.asset().fan_state.alert_id
    assert aid
    for t in range(5, 30):
        stream.tag(t, 'VS1', .91+.002*(t%5));stream.tag(t, 'TS1', 48)
    alerts = [v for topic,v in stream.messages if topic==main.topics.K_ALERTS and v['pattern']=='FAN_VIBRATION']
    assert [(v['state'], v['alertId']) for v in alerts] == [('RAISE', aid), ('CLEAR', aid)]


def test_fan_crossing_clear_threshold_restarts_hold():
    st = cep.CepState(phase='RAISED', alert_id='existing')
    assert cep.evaluate_fan(st, 'A', 0, 1., .01) is None
    assert cep.evaluate_fan(st, 'A', 40, 1.11, -.01) is None
    assert st.phase == 'RAISED'
    assert cep.evaluate_fan(st, 'A', 50, 1., .01) is None
    assert cep.evaluate_fan(st, 'A', 90, 1., .01) is None
    cleared = cep.evaluate_fan(st, 'A', 110, 1., .01)
    assert cleared and cleared['state'] == 'CLEAR' and cleared['alertId'] == 'existing'
