"""사건이 낸 실행 효과(procsvc/effect_compensation.py) — 효과 목록 · 해결 판정 · 보상과 사람 확인, 조회는 처리 건을 잠그지 않는다."""
import threading
import uuid

import pytest

from conftest import OPERATOR
from procsvc import effect_compensation as ec
from test_instances import _effect, _report

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


def test_정리된_효과로_설명되는_단계는_그_행이_낸_명령과_그_행이_낸_거래로_가린다():
    """전수검사 12-5: 판정이 작업 행 log 의 글 모양(적는 곳과 읽는 곳이 따로 적은 글)에 기댔고, 「external … 이 없음」 조건은 그 글을 적는 곳이 없어
    늘 참이었다. 명령 표시는 적는 곳(설비 명령 단계)과 읽는 곳이 같은 함수(command_mark)를 쓴다 — 다른 명령(번호가 이 번호로 시작하는 것 포함)을 낸 행,
    정리되지 않은 명령을 낸 행, 다른 거래를 낸 행은 설명되지 않는다."""
    from types import SimpleNamespace
    defn = SimpleNamespace(activities={'cmd': {'tool': 'incident:command'}, 'obs': {'tool': 'incident:reobserve'},
                                       'wo': {'tool': 'enterprise:work_order'}, 'call': {'tool': 'mcp:call'}})
    effects = ec.inventory(_evidence([WO_TX]))                                       # 설비 명령 CMD-1 · 작업지시 WO-1
    work = [{'id': 'w-cmd', 'activity_id': 'cmd', 'log': ec.command_mark('CMD-1') + 'issued; waiting ACK until 2026-11-23T00:00:30Z; ', 'output': None},
            {'id': 'w-cmd-other', 'activity_id': 'cmd', 'log': ec.command_mark('CMD-10') + 'issued; ', 'output': None},
            {'id': 'w-cmd-none', 'activity_id': 'cmd', 'log': None, 'output': None},
            {'id': 'w-obs', 'activity_id': 'obs', 'log': None, 'output': {'recovered': True}},
            {'id': 'w-obs-more', 'activity_id': 'obs', 'log': None, 'output': {'recovered': False, 'work_order': {'ref': 'WO-9'}}},
            {'id': 'w-wo', 'activity_id': 'wo', 'log': None, 'output': {'work_order': {'ref': 'WO-1'}}},
            {'id': 'w-wo-other', 'activity_id': 'wo', 'log': None, 'output': {'work_order': {'ref': 'WO-2'}}},
            {'id': 'w-po', 'activity_id': 'wo', 'log': None, 'output': {'purchase_order': {'ref': 'WO-1', 'detail': '영수증 값 이름이 달라도 번호로 가린다'}}},
            {'id': 'w-gr-waiting', 'activity_id': 'wo', 'log': 'waiting for delivery; ', 'output': None},          # 아직 거래를 내지 않은 업무 단계
            {'id': 'w-call', 'activity_id': 'call', 'log': None, 'output': {'ok': True}},
            {'id': 'w-outside', 'activity_id': 'cmd', 'log': ec.command_mark('CMD-1'), 'output': None}]
    affected = {w['id'] for w in work} - {'w-outside'}
    settled = {'compensated': ['tx:TX-1'], 'acknowledged': ['plc:CMD-1'], 'pending': []}
    assert ec.explained_services(defn, work, affected, effects, settled) == {'w-cmd', 'w-obs', 'w-wo', 'w-po', 'w-gr-waiting'}
    nothing = {'compensated': [], 'acknowledged': [], 'pending': ['tx:TX-1', 'plc:CMD-1']}
    assert ec.explained_services(defn, work, affected, effects, nothing) == {'w-obs'}
    assert ec.commanded(work[0]['log']) and ec.commanded(work[1]['log']) and not ec.commanded(None) and not ec.commanded('waiting')


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
    world.forward(cmd['cmdId'])
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
    world.forward(cmd['cmdId'])
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
    world.forward(world.commanded(pid)['cmdId'])                               # 승인한 팬 최대가 관문 · PLC 를 거쳐 설비 지령이 된다
    _effect(world, pid)                                                        # 효과 확인이 설비가 낸 값으로 판정할 때까지(시험은 값 · 해제를 넣지 않는다)
    assert _report(world, pid)['outcome'] == '정상', world.values(pid).get('result_report')
    view = world.rt.effects_view(pid)
    wo = next((e for e in view['effects'] if e.get('reversible') and (e.get('ref') or '').startswith('WO-')), None)
    assert wo is not None, [(e.get('kind'), e.get('ref'), e.get('reversible')) for e in view['effects']]
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("UPDATE ent.work_orders SET status='완료', completed_at=now() WHERE id=%s", (wo['ref'],))
    receipt = world.rt.compensate_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '되돌리기', [wo['id']])
    assert receipt['status'] == 'FAILED' and receipt['results'][0]['refused'] is True, receipt
    review = world.rt.review_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '현장에서 이미 끝냄', [wo['id']])
    assert review['status'] == 'RECORDED' and wo['id'] in world.rt.effects_view(pid)['resolution']['acknowledged']


@pytest.mark.parametrize('by, role, words', [
    ('현장 반장', OPERATOR['role'], None),                         # 사용자 표에 없는 이름 글
    (OPERATOR['by'], 'role:no-such', '역할이 아니어서'),             # 사람이지만 내세운 역할의 구성원이 아님
], ids=['이름 글', '구성원 아닌 역할'])
def test_효과_확인은_사용자_표의_사람이_자기_역할로만_한다(world, by, role, words):
    """새9: 효과 확인 영수증은 「설비 상태를 확인한 사람」으로 남고 다시 수행의 문을 연다 — 전에는 빈 값과 역할 등급만 봐서 아무 이름 글이나
    받았다. 승인과 같은 규칙(사람 + 그 역할의 구성원)으로 받는다."""
    from conftest import COOLING
    pattern, asset = COOLING
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')        # 쿨러 오염이 끝까지 진행된 설비가 30분 동안 보고한 뒤의 냉각 경보
    world.settle(1800)
    world.reported_for(asset)
    tags = world.plant.tags(asset)
    alert, pid = world.raise_alert(pattern, asset, ts1=tags['TS1'], ce=tags['CE'])
    decision = world.agent(pid, 'T_agent')
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.forward(world.commanded(pid)['cmdId'])
    plc = next(e for e in world.rt.effects_view(pid)['effects'] if e['kind'] == 'plc')
    with pytest.raises(PermissionError) as refused:
        world.rt.review_effects(pid, str(uuid.uuid4()), by, role, '현장 확인함', [plc['id']])
    assert words is None or words in str(refused.value), str(refused.value)
    assert world.rt.effects_view(pid)['receipts'] == [], '거절된 확인은 영수증을 남기지 않는다'
    receipt = world.rt.review_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '현장 확인함', [plc['id']])
    assert receipt['status'] == 'RECORDED', '담당자가 자기 역할로 하면 받는다'
