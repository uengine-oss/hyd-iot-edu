import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from det import main
from det.pattern_runtime import PatternRuntime
from det.store import Store
from test_pattern_definitions import definition, frame


def raised_runtime():
    runtime = PatternRuntime([definition()])
    events = [e for t in range(5) for e in frame(runtime,t,1.3+t*.01)]
    return runtime,events[0]


def test_checkpoint_restart_retains_alert_and_outbox_offsets(tmp_path):
    runtime,event = raised_runtime()
    db = Store(tmp_path/'state.db')
    db.save(dict(runtime=runtime.snapshot()),('tags',0,12),[event])
    db.close()
    db = Store(tmp_path/'state.db')
    restored = PatternRuntime.restore(db.load()['runtime'])
    assert db.seen('tags',0,12) and not db.seen('tags',0,13)
    assert db.pending()[0][1]['alertId']==event['alertId']
    assert restored.assets['A'].runs['CHANGED_PATTERN'].state.alert_id==event['alertId']
    assert not restored.source_ready
    # A source outage cannot clear the alert; fresh observations can clear its pinned definition.
    assert frame(restored,100,.9,gap=True)==[]
    clears=[e for t in range(101,106) for e in frame(restored,t,.9)]
    assert len(clears)==1 and clears[0]['state']=='CLEAR' and clears[0]['alertId']==event['alertId']
    assert not [e for t in range(106,113) for e in frame(restored,t,1.3+(t-106)*.01)]
    db.delivered(db.pending()[0][0]); assert db.pending()==[]
    db.close()


def test_failed_serialization_cannot_advance_checkpoint_or_offset(tmp_path):
    db=Store(tmp_path/'state.db');db.save({'old':True},('tags',0,1))
    with pytest.raises(ValueError):db.save({'new':True},('tags',0,2),[{'bad':float('nan')}])
    assert db.load()=={'old':True} and not db.seen('tags',0,2) and db.pending()==[]
    db.close()


def test_restart_drops_candidate_and_clearing_elapsed_time():
    runtime=PatternRuntime([definition()])
    frame(runtime,0,1.3);frame(runtime,1,1.4)
    restored=PatternRuntime.restore(runtime.snapshot())
    assert restored.assets['A'].runs['CHANGED_PATTERN'].state.phase=='IDLE'
    runtime,event=raised_runtime();frame(runtime,5,.9);frame(runtime,6,.9)
    restored=PatternRuntime.restore(runtime.snapshot())
    st=restored.assets['A'].runs['CHANGED_PATTERN'].state
    assert st.phase=='RAISED' and st.since is None and st.alert_id==event['alertId']


def test_outbox_failure_preserves_message_and_retry_identity(tmp_path,monkeypatch):
    db=Store(tmp_path/'state.db');runtime,event=raised_runtime()
    db.save({'runtime':runtime.snapshot()},events=[event])
    monkeypatch.setattr(main,'store',db)
    async def failure(*args,**kw):raise OSError('broker unavailable')
    with pytest.raises(OSError):asyncio.run(main.drain_alerts(SimpleNamespace(send_and_wait=failure)))
    assert db.pending()[0][1]==event
    sent=[]
    async def success(*args,**kw):sent.append(kw['value'])
    asyncio.run(main.drain_alerts(SimpleNamespace(send_and_wait=success)))
    assert sent==[event] and db.pending()==[]
    db.close()


def test_source_failure_blocks_new_raises_but_keeps_existing_revision(monkeypatch):
    runtime,event=raised_runtime()
    monkeypatch.setattr(main,'runtime',runtime);monkeypatch.setattr(main,'store',None)
    monkeypatch.setattr(main,'catalog_status',dict(ready=True))
    monkeypatch.setattr(main,'mutation_lock',asyncio.Lock())
    def failed():raise OSError('source unavailable')
    monkeypatch.setattr(main,'fetch_catalog',failed)
    assert asyncio.run(main.refresh_catalog()) is False
    assert main.catalog_status['ready'] is False and not runtime.source_ready
    assert runtime.assets['A'].runs['CHANGED_PATTERN'].state.alert_id==event['alertId']
    assert not [e for t in range(6) for e in frame(runtime,t,1.3+t*.01,asset='B')]
    monkeypatch.setattr(main,'fetch_catalog',lambda:[definition()])
    assert asyncio.run(main.refresh_catalog()) is True
    assert runtime.source_ready


def test_initial_source_failure_never_invents_builtin_patterns(monkeypatch):
    monkeypatch.setattr(main,'runtime',None);monkeypatch.setattr(main,'store',None)
    monkeypatch.setattr(main,'catalog_status',dict(ready=False));monkeypatch.setattr(main,'mutation_lock',asyncio.Lock())
    def failed():raise OSError('offline')
    monkeypatch.setattr(main,'fetch_catalog',failed)
    assert asyncio.run(main.refresh_catalog()) is False and main.runtime is None


def test_overlap_of_raise_clear_is_unknown_not_flapping():
    runtime=PatternRuntime([definition(clearRule='VS1 > 1.2')])
    assert not [e for t in range(8) for e in frame(runtime,t,1.3+t*.01)]
    assert runtime.assets['A'].runs['CHANGED_PATTERN'].quality['problems']=={'definition':'CONFLICTING_RAISE_CLEAR'}


def test_snapshot_roundtrip_keeps_definition_revision():
    runtime,event=raised_runtime()
    snapshot=deepcopy(runtime.snapshot())
    restored=PatternRuntime.restore(snapshot)
    assert restored.assets['A'].runs['CHANGED_PATTERN'].definition.revision==event['evidence']['definition']['revision']


def test_patterns_http_reads_sqlite_on_event_loop_thread(tmp_path,monkeypatch):
    import httpx
    async def check():
        db=Store(tmp_path/'state.db')
        monkeypatch.setattr(main,'store',db)
        monkeypatch.setattr(main,'runtime',PatternRuntime([definition()]))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as client:
            response=await client.get('/api/detector/patterns')
            assert response.status_code==200 and response.json()['pending_alerts']==0
        db.close()
    asyncio.run(check())
