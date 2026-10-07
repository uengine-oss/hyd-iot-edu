"""A second physical alarm can arrive while the first snapshot is serialized."""
from concurrent.futures import ThreadPoolExecutor
import json
from concurrent.futures import TimeoutError
from threading import Event

from procsvc import machine, store as storage


def test_simultaneous_alarm_save_keeps_both_incidents(tmp_path,monkeypatch):
    store=storage.Store(tmp_path/'state.sqlite3')
    def incident(name):
        inc=machine.Incident.from_card(name,{'alert':{'alertId':name,'asset':'HYD-01','pattern':'PLC_TRIP'}})
        machine.on_card(inc)
        return inc
    first=incident('first');second=incident('second');incidents={first.id:first}
    serializing,release=Event(),Event();original=storage.asdict
    def paused(obj):
        if not serializing.is_set():
            serializing.set()
            assert release.wait(5),'test coordination timeout'
        return original(obj)
    monkeypatch.setattr(storage,'asdict',paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(store.save,incidents,{},[])
        assert serializing.wait(5)
        incidents[second.id]=second
        two=pool.submit(store.save,incidents,{},[])
        release.set()
        one.result(timeout=5);two.result(timeout=5)
    restored,_,_=store.restore()
    assert set(restored)=={'first','second'}
    assert all(i.state=='ESCALATED' and i.recovery is None for i in restored.values())


def test_snapshot_never_captures_a_half_applied_transition(tmp_path, monkeypatch):
    """A143 (remaining-sweep 13): store.save() runs on executor threads (instance hooks) while the event loop drives an
    Incident transition, and the other way round. Incident/decision mutation and the snapshot capture must exclude each
    other, or the durable snapshot can hold a state that disagrees with its own history (restore then judges on it)."""
    import dataclasses
    from datetime import datetime, timezone
    store = storage.Store(tmp_path / 'state.sqlite3')
    inc = machine.Incident.from_card('torn', {'alert': {'alertId': 'torn', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'},
                                              'recommended': [{'code': 'FAN_SET', 'kind': 'command', 'param': 'fan_pct', 'paramRange': [0, 100]}]})
    machine.on_card(inc)
    assert inc.state == 'AWAITING_APPROVAL'
    incidents = {inc.id: inc}

    class NoFx(machine.Effects):
        def emit_cmd(self, cmd): pass
        def emit_audit(self, evt): pass
        def set_timer(self, name, seconds): pass

    at_history, release = Event(), Event()
    original = dataclasses._asdict_inner

    def paused(obj, dict_factory):
        if obj is inc.history and not at_history.is_set():       # state was read, history is about to be copied
            at_history.set()
            assert release.wait(5), 'test coordination timeout'
        return original(obj, dict_factory)
    monkeypatch.setattr(dataclasses, '_asdict_inner', paused)

    def transition():
        machine.on_approve(inc, 'op', [{'code': 'FAN_SET', 'fan_pct': 100}],
                           datetime(2026, 10, 8, tzinfo=timezone.utc), NoFx(), time_scale=20)
    with ThreadPoolExecutor(max_workers=2) as pool:
        saving = pool.submit(store.save, incidents, {}, [])
        assert at_history.wait(5)
        moving = pool.submit(transition)
        try:
            moving.result(timeout=0.5)                  # without exclusion the transition lands inside the capture
        except TimeoutError:
            pass                                        # with exclusion it waits for the capture to finish
        release.set()
        saving.result(timeout=5); moving.result(timeout=5)
    body = json.loads(store.db.execute('select body from snapshot where id=1').fetchone()[0])
    saved = body['incidents'][0]
    assert saved['state'] == saved['history'][-1]['state'], (saved['state'], [h['state'] for h in saved['history']])
    assert inc.state == 'AWAITING_ACK' and inc.history[-1]['state'] == 'AWAITING_ACK'
