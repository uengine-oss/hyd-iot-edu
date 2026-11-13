"""사건이 낸 실행 효과(procsvc/effect_compensation.py) — 효과 목록 · 해결 판정 · 보상과 사람 확인, 조회는 처리 건을 잠그지 않는다."""
import threading
import uuid

import pytest

from conftest import OPERATOR
from procsvc import effect_compensation as ec

# 업무 시스템이 거래마다 싣는 되돌리기 계약(enterprise-sim /api/transactions ← 업무 DB ent.skill_contracts)
WO_TX = {'id': 'TX-1', 'skill': 'skill:schedule-maintenance', 'system': 'sys:cmms', 'ref': 'WO-1', 'detail': '작업지시',
         'inverse': 'skill:cancel-work-order', 'irreversible_reason': None}
LOT_TX = {'id': 'TX-2', 'skill': 'skill:receive-goods', 'system': 'sys:erp', 'ref': 'GR-1',
          'inverse': None, 'irreversible_reason': '입고 · 검수는 실물이 창고에 들어와 되돌릴 수 없다'}
INCIDENT = {'id': 'inc-1', 'cmdId': 'CMD-1', 'actions': [{'code': 'FAN_SET', 'fan_pct': 100}], 'ack': {'result': 'DONE'}}


def _evidence(ledger, incident=INCIDENT, decisions=()):
    return {'incident': incident, 'enterprise_receipts': {'dec-1': ledger}, 'decisions': list(decisions)}


@pytest.mark.parametrize('ledger, reversible', [
    ([WO_TX], {'tx:TX-1': True, 'plc:CMD-1': False}),
    ([LOT_TX], {'tx:TX-2': False, 'plc:CMD-1': False}),
], ids=['작업지시는 되돌림 계약이 있다', '입고는 되돌릴 수 없다'])
def test_효과_목록은_업무_시스템이_실은_되돌리기_계약대로_되돌릴_수_있는지를_낸다(ledger, reversible):
    effects = ec.inventory(_evidence(ledger))
    assert {e['id']: e['reversible'] for e in effects} == reversible
    tx = next(e for e in effects if e['kind'] == 'enterprise')
    assert (tx['inverse'], tx['irreversible_reason']) == (ledger[0]['inverse'], ledger[0]['irreversible_reason'])
    plc = next(e for e in effects if e['kind'] == 'plc')
    assert plc['irreversible_reason'] == ec.PLC_REASON


def test_되돌리기_계약이_없는_거래_응답은_되돌릴_수_있다고_짐작하지_않고_실패한다():
    """P4-09 · G2-05: 전에는 process 가 되돌리기 표 사본(업무 시스템 · 업무 DB 와 세 벌)을 들고 거래 종류로 판정했다."""
    with pytest.raises(ValueError, match='되돌리기 계약\(inverse · irreversible_reason\)이 없습니다'):
        ec.inventory(_evidence([{k: v for k, v in WO_TX.items() if k != 'inverse'}]))


def test_역거래가_원장에_있으면_보상된_것이다():
    effects = ec.inventory(_evidence([WO_TX, {'id': 'TX-9', 'skill': 'skill:cancel-work-order', 'ref': 'WO-1', 'compensates': 'TX-1',
                                              'inverse': None, 'irreversible_reason': None}]))
    assert ec.resolution(effects, []) == {'compensated': ['tx:TX-1'], 'acknowledged': [], 'pending': ['plc:CMD-1']}


def test_사람_확인_영수증은_그_효과의_지문으로만_해결한다():
    effects = ec.inventory(_evidence([LOT_TX]))
    receipt = {'kind': 'review', 'status': 'RECORDED', 'request_id': 'r1', 'effects': [e for e in effects if e['id'] == 'tx:TX-2']}
    assert ec.resolution(effects, [receipt])['pending'] == ['plc:CMD-1']
    changed = ec.inventory(_evidence([dict(LOT_TX, ref='LOT-2')]))
    assert 'tx:TX-2' in ec.resolution(changed, [receipt])['pending'], '기록이 바뀌면 옛 확인으로 해결되지 않는다'


def test_업무_시스템이_역거래를_거절한_효과는_사람_확인_대상으로_바뀐다():
    """P4-11: 전에는 되돌릴 수 있는 거래인데 업무 시스템이 역거래를 거절하면 보상도 확인도 못 해 다시 수행이 영영 막혔다."""
    receipts = [{'kind': 'compensation', 'results': [{'effect': 'tx:TX-1', 'ok': False, 'refused': True, 'error': 'CompensationRefused: 이미 완료'}]},
                {'kind': 'compensation', 'results': [{'effect': 'tx:TX-3', 'ok': False, 'refused': False, 'error': 'URLError'}]}]
    assert ec.refused_compensations(receipts) == {'tx:TX-1'}, '잠깐의 연결 실패는 거절이 아니다'


def test_효과_조회는_같은_처리_건의_전이_잠금을_기다리지_않는다(world):
    """P4-04 · W1-06: 전에는 2초마다 오는 조회가 처리 건 잠금을 잡은 채 업무 시스템 원장 HTTP 를 기다렸다 — 잠금을 쥔 일이 있으면 조회가 멈췄다."""
    alert, pid, decision = world.start_cooling()
    held, release = threading.Event(), threading.Event()

    def holder():
        with world.rt._transition(pid):
            held.set()
            release.wait(30)
    t = threading.Thread(target=holder, daemon=True)
    t.start()
    assert held.wait(10)
    out = {}
    viewer = threading.Thread(target=lambda: out.update(view=world.rt.effects_view(pid)), daemon=True)
    viewer.start()
    viewer.join(10)
    release.set()
    t.join(30)
    assert 'view' in out, '잠금이 풀릴 때까지 조회가 기다렸다'
    assert out['view']['incident']['id'] == world.values(pid)['incident'] and out['view']['effects'] == []


def test_명령을_낸_사건은_설비_명령_효과를_사람_확인으로만_정리한다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    world.ack('HYD-01', cmd['cmdId'])
    view = world.rt.effects_view(pid)
    plc = next(e for e in view['effects'] if e['kind'] == 'plc')
    with pytest.raises(ValueError, match='보상할 수 있는 미해결 효과가 없습니다|보상할 수 없는 효과'):
        world.rt.compensate_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '되돌리기', [plc['id']])
    receipt = world.rt.review_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '현장 확인함', [plc['id']])
    assert receipt['status'] == 'RECORDED' and plc['id'] in world.rt.effects_view(pid)['resolution']['acknowledged']


def test_같은_요청_id로_다시_보낸_확인은_처음_영수증을_그대로_돌려준다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    world.ack('HYD-01', cmd['cmdId'])
    plc = next(e for e in world.rt.effects_view(pid)['effects'] if e['kind'] == 'plc')
    rid = str(uuid.uuid4())
    first = world.rt.review_effects(pid, rid, OPERATOR['by'], OPERATOR['role'], '현장 확인함', [plc['id']])
    assert world.rt.review_effects(pid, rid, OPERATOR['by'], OPERATOR['role'], '현장 확인함', [plc['id']]) == first
    with pytest.raises(ValueError, match='다른 확인 내용'):
        world.rt.review_effects(pid, rid, OPERATOR['by'], OPERATOR['role'], '다른 사유', [plc['id']])


def test_업무_시스템이_역거래를_거절하면_그_효과는_보상_대신_사람_확인으로_정리된다(world):
    """P4-11 실제 사슬: 흐름 A 가 정상으로 끝나며 낸 작업지시를 현장이 먼저 끝내면(업무 DB 상태 「완료」) 취소 역거래는 업무 시스템이
    거절한다(4xx) — 영수증에 거절이 남고, 그 되돌릴 수 있던 효과를 사람이 확인으로 정리할 수 있다(전에는 보상도 확인도 못 해 막혔다)."""
    import psycopg
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.tag('HYD-01', 'TS1', 50.0)
    world.clear_alert(alert)
    world.clock.advance(15 * 60 / 20 + 1)                                     # 재관측 창(15 설비 분 ÷ 배속 20)
    world.poll()
    view = world.rt.effects_view(pid)
    wo = next((e for e in view['effects'] if e.get('reversible') and (e.get('ref') or '').startswith('WO-')), None)
    assert wo is not None, [(e.get('kind'), e.get('ref'), e.get('reversible')) for e in view['effects']]
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("UPDATE ent.work_orders SET status='완료', completed_at=now() WHERE id=%s", (wo['ref'],))
    receipt = world.rt.compensate_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '되돌리기', [wo['id']])
    assert receipt['status'] == 'FAILED' and receipt['results'][0]['refused'] is True, receipt
    review = world.rt.review_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '현장에서 이미 끝냄', [wo['id']])
    assert review['status'] == 'RECORDED' and wo['id'] in world.rt.effects_view(pid)['resolution']['acknowledged']
