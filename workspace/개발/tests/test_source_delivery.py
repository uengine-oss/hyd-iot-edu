"""원천 처리기(procsvc/source_delivery.py) — 접수 하나를 점유해 처리하고 끝(HANDLED) · 연결 대기(WAITING, 실패 횟수를 쓰지 않음) · 실패 시도
(PENDING + 실패 횟수 · 까닭)로 닫는다. 처리 자체는 실제 process 의 원천 처리 함수(world — 경보는 처리 건, 해제 · 명령 응답은 사건)다."""
import asyncio
import threading
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

from conftest import COOLING
from hydcommon import topics
from procsvc.source_delivery import SourceDelivery


def row_of(world, receipt_id):
    with psycopg.connect(world.dsn, row_factory=dict_row) as db:
        return db.execute('SELECT status, failures, error, result, history FROM process_source_inbox WHERE id=%s', (receipt_id,)).fetchone()


def run(coro):
    """코루틴을 다른 스레드의 새 이벤트 루프에서 끝까지 — 결과를 돌려주고, 예외는 그대로 다시 올린다."""
    box = {}

    def target():
        try:
            box['v'] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 — 부른 쪽에서 그대로 다시 올린다
            box['e'] = exc
    t = threading.Thread(target=target)
    t.start(); t.join()
    if 'e' in box:
        raise box['e']
    return box['v']


def test_처리할_접수가_없으면_아무것도_하지_않는다(world):
    world.deliver()
    assert run(world.main.source_delivery.run_once()) is None


def test_경보보다_먼저_온_해제는_실패로_세지_않고_연결을_기다린다(world):
    alert = {'alertId': 'ALT-' + uuid.uuid4().hex[:8], 'asset': 'HYD-02', 'pattern': COOLING[0], 'state': 'CLEAR', 't': world.now_iso()}
    receipt = world.receive(topics.K_ALERTS, alert)
    row = row_of(world, receipt['id'])
    assert (row['status'], row['failures']) == ('WAITING', 0) and '연결할 원천 사건' in row['error']
    assert row['history'][-1]['event'] == 'waiting'


def test_처리하다_틀린_접수는_실패_시도로_까닭과_함께_남는다(world):
    alert, pid = world.raise_alert(*COOLING)
    wrong = dict(alert, state='CLEAR', asset='HYD-02', t=world.now_iso())       # 사건과 다른 설비의 해제
    receipt = world.receive(topics.K_ALERTS, wrong)
    row = row_of(world, receipt['id'])
    assert (row['status'], row['failures']) == ('PENDING', 1) and row['error'].startswith('ValueError: ') and '설비' in row['error']


def test_처리_엔진이_낸_적_없는_명령의_응답은_할_일_없음으로_끝난다(world):
    """P2-01: FUXA 수동 조작처럼 사건에 없는 명령 응답이 5초마다 영원히 다시 처리됐다(대기). 처리 엔진이 낸 명령이 아니면 끝낸다."""
    receipt = world.ack('HYD-02', 'FUXA-' + uuid.uuid4().hex[:8])
    row = row_of(world, receipt['id'])
    assert row['status'] == 'HANDLED' and row['failures'] == 0


def test_같은_사건을_기다리는_쪽은_처리가_끝난_접수를_돌려받는다(world):
    alert, pid = world.raise_alert(*COOLING)
    receipt = world.main.source_inbox.get(world.main.source_inbox.list(status='HANDLED', limit=500)[-1]['id'])
    got = run(world.main.source_delivery.wait_for(receipt, timeout=5))
    assert got['status'] == 'HANDLED'


def test_충돌한_접수를_기다리면_그_까닭으로_실패한다(world):
    with pytest.raises(ValueError, match='충돌|conflict'):
        run(SourceDelivery(world.main.source_inbox, world.rt, world.main._apply_source_event, owner='t').wait_for(
            {'status': 'CONFLICT', 'error': 'same business event identity contains conflicting source data', 'id': 1, 'parent_id': None}))
