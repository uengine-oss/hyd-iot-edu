"""사건 · 판단 저장(procsvc/store.py) — process 가 다시 켜질 때 무엇을 이어 가고 무엇을 사람 검토로 넘기는가."""
import pytest

from procsvc import machine
from procsvc.store import Store


def _incident(state, **fields):
    alert = {'alertId': 'ALT-1', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}
    inc = machine.Incident.from_card('INC-test', {'alert': alert, 'recommended': []})
    inc.state = state
    for k, v in fields.items():
        setattr(inc, k, v)
    return inc


@pytest.mark.parametrize('state, after, reason', [
    ('AWAITING_APPROVAL', 'AWAITING_APPROVAL', None),
    ('CMD_ISSUED', 'ESCALATED', 'PROCESS_RESTART_REVIEW'),        # 명령을 보냈는지 모른다 — 사람 검토
    ('AWAITING_ACK', 'ESCALATED', 'PROCESS_RESTART_REVIEW'),      # 설비가 실행했는지 모른다 — 사람 검토
    ('RE_OBSERVING', 'RE_OBSERVING', None),                       # 재관측은 읽기 — 저장한 마감으로 이어 간다(A-02)
    ('RESOLVED', 'RESOLVED', None),                               # 회복 판정 뒤 — 흐름의 작업지시가 이어 간다
    ('CLOSED', 'CLOSED', None),
])
def test_다시_켜지면_명령_결과를_모르는_순간만_사람_검토로_넘긴다(tmp_path, state, after, reason):
    path = tmp_path / 'process.sqlite3'
    Store(str(path)).save({'INC-test': _incident(state)}, {}, [])
    incidents, book, audit = Store(str(path)).restore()
    inc = incidents['INC-test']
    assert (inc.state, inc.reason) == (after, reason)
    if after == 'ESCALATED':
        assert inc.history[-1]['note'] == 'PROCESS_RESTART_REVIEW' and inc.closed


def test_저장한_판단은_그대로_돌아온다(tmp_path):
    path = tmp_path / 'process.sqlite3'
    book = {'D-1': {'id': 'D-1', 'state': 'APPROVED', 'schema': 'v2', 'history': [], 'process_approval_id': 'w-1'}}
    Store(str(path)).save({}, book, [{'event': 'X'}])
    _, restored, audit = Store(str(path)).restore()
    assert restored == book and audit == [{'event': 'X'}]
