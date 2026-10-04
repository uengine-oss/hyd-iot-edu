"""A second physical alarm can arrive while the first snapshot is serialized."""
from concurrent.futures import ThreadPoolExecutor
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
