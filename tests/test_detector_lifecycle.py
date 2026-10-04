import asyncio
from types import SimpleNamespace

import pytest

from det import main
from hydcommon import kafka


@pytest.mark.parametrize('phase', ['load', 'scope', 'refresh', 'consumer', 'stop'])
def test_failure_at_each_startup_phase_closes_acquired_resources(monkeypatch, phase):
    closed = []

    class Store:
        def __init__(self, path): pass
        def load(self):
            if phase == 'load': raise ValueError('invalid checkpoint')
            return {'scope': 'different'} if phase == 'scope' else None
        def close(self): closed.append('store')

    async def refresh():
        if phase == 'refresh': raise asyncio.CancelledError()
    async def stop():
        closed.append('producer')
        if phase == 'stop': raise OSError('stop failed')
    async def producer(): return SimpleNamespace(stop=stop)
    async def consumer(*args, **kwargs): raise OSError('consumer startup failed')
    monkeypatch.setattr(main, 'Store', Store)
    monkeypatch.setattr(main, 'runtime', None)
    monkeypatch.setattr(main, 'store', None)
    monkeypatch.setattr(main, 'refresh_catalog', refresh)
    monkeypatch.setattr(main, 'make_producer', producer)
    monkeypatch.setattr(main, 'make_consumer', consumer)
    with pytest.raises((ValueError, RuntimeError, OSError, asyncio.CancelledError)):
        asyncio.run(main.run())
    assert closed == (['producer', 'store'] if phase in ('consumer', 'stop') else ['store'])
    assert main.store is None
    assert main.state['kafka'] is False


@pytest.mark.parametrize('kind', ['producer', 'consumer'])
def test_cancel_during_kafka_start_closes_unreturned_client(monkeypatch, kind):
    closed = []
    class Client:
        def __init__(self, *args, **kwargs): pass
        async def start(self): raise asyncio.CancelledError()
        async def stop(self): closed.append(kind)
    monkeypatch.setattr(kafka, 'AIOKafkaProducer' if kind == 'producer' else 'AIOKafkaConsumer', Client)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(kafka.producer() if kind == 'producer' else kafka.consumer(['tags'], 'test'))
    assert closed == [kind]
