"""사건 · 판단의 그래프 반영(procsvc/case_projection.py) — 사건 저장 파일에 저장된 것만 그래프로 옮기고, 영수증이 맞을 때만 끝난 것으로 친다.
그래프는 실제 Neo4j(kg-seed 와 같은 시드), 대기열은 실제 사건 저장 파일(SQLite)."""
import pytest

from procsvc import machine
from procsvc.case_projection import CaseProjector
from procsvc.store import Store

ALERT = {'alertId': 'ALT-CASE-1', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE', 'evidence': {'trip': None}}
CAUSE, SKILL = 'cause:case-test-fin-fouling', 'skill:case-test-cool'     # 원인 · 조치 방법은 시드가 아니라 매뉴얼 적재가 넣는다 — 시험이 넣고 지운다



def _cooling_policy():
    """냉각 경보를 받은 흐름의 경보 정책(사건은 경보 정책이 있어야 만든다 — machine.Incident.from_card)."""
    import json
    from conftest import DEFINITIONS
    from procsvc import alert_policy
    return alert_policy.for_definition(json.loads((DEFINITIONS / 'anomaly_response_v22.json').read_text(encoding='utf8')), 'COOLER_DEGRADATION')

def _incident(state='AWAITING_APPROVAL', cause=CAUSE):
    inc = machine.Incident.from_card('INC-CASE-1', {'alert': ALERT, 'recommended': [], 'topCause': cause}, _cooling_policy())
    inc.state = state
    return inc


def _decision(state='APPROVED'):
    return {'id': 'DEC-CASE-1', 'state': state, 'chosen': SKILL if state != 'PENDING_APPROVAL' else None,
            'approvedRole': 'role:operator', 'origin': {'incident': 'INC-CASE-1'}, 'created': '2026-10-30T09:00:00+00:00',
            'history': [{'state': 'APPROVED', 't': '2026-10-30T09:05:00+00:00'}], 'override': False, 'reason': '시험'}


@pytest.fixture
def case(tmp_path, seeded_graph):
    store = Store(str(tmp_path / 'process.sqlite3'))
    projected = []
    seeded_graph.query('MERGE (:Cause {id:$c}) MERGE (:Skill {id:$s})', c=CAUSE, s=SKILL)          # 매뉴얼 적재가 넣었을 지식
    try:
        yield store, CaseProjector(store, seeded_graph.query, projected.append), seeded_graph, projected
    finally:
        store.db.close()
        seeded_graph.query('MATCH (n) WHERE n.id IN [$c, $s, "INC-CASE-1", "case:DEC-CASE-1"] DETACH DELETE n', c=CAUSE, s=SKILL)
        seeded_graph.query('MATCH (f:CaseProjection) WHERE f.id IN ["Incident:INC-CASE-1", "DecisionCase:DEC-CASE-1"] DELETE f')


def _node(graph, label, node_id):
    rows = graph.query(f'MATCH (n:{label} {{id:$id}}) RETURN n{{.*}} AS n, [(n)-[r]->(m) | type(r) + ">" + coalesce(m.code, m.id)] AS out', id=node_id)
    return rows[0] if rows else None


def test_저장한_사건은_그래프에_시드의_설비_패턴_원인과_이어지고_대기열에서_빠진다(case):
    store, projector, graph, projected = case
    store.save({'INC-CASE-1': _incident()}, {}, [])
    assert projector.drain() == 1
    node = _node(graph, 'Incident', 'INC-CASE-1')
    assert node['n']['status'] == 'AWAITING_APPROVAL' and node['n']['projection_warnings'] == []
    assert sorted(node['out']) == [f'DIAGNOSED_AS>{CAUSE}', 'ON_ASSET>HYD-01', 'RAISED_BY>COOLER_DEGRADATION']
    assert store.case_projection_status()['pending'] == 0 and projected == ['INC-CASE-1']


def test_그래프에_없는_원인은_잇지_않고_사건에_경고로_남긴다(case):
    store, projector, graph, _ = case
    store.save({'INC-CASE-1': _incident(cause='cause:no-such-cause')}, {}, [])
    assert projector.drain() == 1
    node = _node(graph, 'Incident', 'INC-CASE-1')
    assert node['n']['projection_warnings'] == ['cause missing: cause:no-such-cause']
    assert sorted(node['out']) == ['ON_ASSET>HYD-01', 'RAISED_BY>COOLER_DEGRADATION']


def test_같은_판번호_같은_내용을_다시_보내도_두_번_만들지_않는다(case):
    store, projector, graph, _ = case
    store.save({'INC-CASE-1': _incident()}, {}, [])
    [job] = store.case_projection_batch()
    assert projector.deliver(job) is True and projector.deliver(dict(job)) is True          # 재전송(영수증을 잃은 뒤)
    assert graph.query('MATCH (n:Incident {id:"INC-CASE-1"}) RETURN count(n) AS n') == [{'n': 1}]


def test_늦게_도착한_앞_판번호는_새_판을_덮지_않는다(case):
    store, projector, graph, _ = case
    store.save({'INC-CASE-1': _incident()}, {}, [])
    [old] = store.case_projection_batch()
    store.save({'INC-CASE-1': _incident('RESOLVED')}, {}, [])
    [new] = store.case_projection_batch()
    assert projector.deliver(new) is True                                                      # 새 판이 앞 판 행까지 함께 끝냈다(지움)
    assert projector.deliver(dict(old, ids=old['ids'])) is False                               # 울타리가 막음 → 영수증 없음
    assert _node(graph, 'Incident', 'INC-CASE-1')['n']['status'] == 'RESOLVED'
    assert store.case_projection_status()['pending'] == 0                                      # 옛 판은 이미 반영된 새 판에 덮였다 — 남길 일 없음


def test_그래프의_울타리가_원천보다_앞서면_사람이_비교할_충돌로_남고_다시_보내지_않는다(case):
    store, projector, graph, _ = case
    graph.query('CREATE (:CaseProjection {id:"Incident:INC-CASE-1", revision: 999, payload_hash: "x"})')
    store.save({'INC-CASE-1': _incident()}, {}, [])
    assert projector.drain() == 0
    errors = store.db.execute('select last_error from case_projection_outbox where processed_at is null').fetchall()
    assert errors and all(e[0].startswith('ProjectionConflict:') for e in errors), errors
    _retry_now(store)
    assert store.case_projection_batch() == []                                                 # 충돌은 다시 보내지 않는다(수리 도구로)


def test_사건이_아직_그래프에_없으면_판단은_실패로_남았다가_사건_뒤에_반영된다(case):
    store, projector, graph, _ = case
    store.save({'INC-CASE-1': _incident()}, {'DEC-CASE-1': _decision()}, [])
    jobs = {j['kind']: j for j in store.case_projection_batch()}
    assert projector.deliver(jobs['DecisionCase']) is False                                    # 사건보다 먼저(차례가 바뀐 경우)
    row = store.db.execute("select last_error from case_projection_outbox where kind='DecisionCase'").fetchone()
    assert row[0].startswith('RuntimeError: incident source not projected')
    assert projector.deliver(jobs['Incident']) is True
    _retry_now(store)
    assert projector.drain() == 1
    case_node = _node(graph, 'DecisionCase', 'case:DEC-CASE-1')
    assert sorted(case_node['out']) == [f'CHOSE>{SKILL}', 'DECIDED_BY>role:operator', 'FOR_INCIDENT>INC-CASE-1',
                                        'INSTANCE_OF>dec:rank-actions']


def _retry_now(store):
    """실패 행의 다시 시도 시각을 지금으로(늘어나는 간격을 기다리지 않고 다음 반영이 집게)."""
    store.db.execute('update case_projection_outbox set retry_at=0')
    store.db.commit()


def test_저장_파일에서_사라진_사건은_그래프에서도_지운다(case):
    store, projector, graph, _ = case
    store.save({'INC-CASE-1': _incident()}, {}, [])
    projector.drain()
    assert _node(graph, 'Incident', 'INC-CASE-1') is not None
    store.save({}, {}, [])                                     # 사건이 없어졌다(지운 사건 — 저장 파일이 그 사실을 기억한다)
    assert projector.drain() == 1
    assert _node(graph, 'Incident', 'INC-CASE-1') is None and store.case_projection_status()['pending'] == 0


@pytest.mark.parametrize('state', ['PENDING_APPROVAL', 'REJECTED'])
def test_승인되지_않은_판단은_판단_사례로_그래프에_두지_않는다(case, state):
    store, projector, graph, _ = case
    store.save({'INC-CASE-1': _incident()}, {'DEC-CASE-1': _decision()}, [])
    projector.drain()
    _retry_now(store)
    projector.drain()
    assert _node(graph, 'DecisionCase', 'case:DEC-CASE-1') is not None
    store.save({'INC-CASE-1': _incident()}, {'DEC-CASE-1': _decision(state)}, [])
    projector.drain()
    assert _node(graph, 'DecisionCase', 'case:DEC-CASE-1') is None and store.case_projection_status()['pending'] == 0
