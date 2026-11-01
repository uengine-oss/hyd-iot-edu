"""그래프 반영 수리 도구(procsvc/projection_repair.py) — 원천과 그래프를 비교해 보여 주고(조회), 사람이 검토한 계획대로만 다시 보낸다(적용).
업무 기록을 되돌리거나 명령을 내거나 울타리를 낮추지 않는다. 원천은 실제 업무 DB · 사건 저장 파일, 그래프는 실제 Neo4j."""
import uuid

import pytest

from procsvc import machine, projection_repair as repair
from procsvc.store import Store



def _cooling_policy():
    """냉각 경보를 받은 흐름의 경보 정책(사건은 경보 정책이 있어야 만든다 — machine.Incident.from_card)."""
    import json
    from conftest import DEFINITIONS
    from procsvc import alert_policy
    return alert_policy.for_definition(json.loads((DEFINITIONS / 'anomaly_response_v22.json').read_text(encoding='utf8')), 'COOLER_DEGRADATION')


@pytest.mark.parametrize('source, graph, want', [
    ({'instance': {'status': 'RUNNING', 'end_event': None, 'proc_def_version': '1', 'rework_generation': 0, 'proc_def_id': 'c3'}, 'items': []},
     {'nodes': [{'node': {'status': 'RUNNING', 'version': '1', 'rework_generation': 0, 'definition_id': 'c3'}}], 'items': []}, []),
    ({'instance': {'status': 'COMPLETED', 'proc_def_version': '1', 'proc_def_id': 'c3'}, 'items': []},
     {'nodes': [{'node': {'status': 'RUNNING', 'version': '1', 'definition_id': 'c3'}}], 'items': []},
     [{'where': 'ProcessInstance', 'field': 'status', 'source': 'COMPLETED', 'graph': 'RUNNING'}]),
    ({'instance': {'status': 'RUNNING', 'proc_def_version': '1', 'proc_def_id': 'c3'}, 'items': []}, {'nodes': [], 'items': []},
     [{'where': 'ProcessInstance', 'field': '*', 'source': 'present', 'graph': 'missing'}]),
    ({'instance': {'status': 'RUNNING', 'proc_def_version': '1', 'proc_def_id': 'c3'}, 'items': [{'id': 'w1', 'status': 'DONE'}]},
     {'nodes': [{'node': {'status': 'RUNNING', 'version': '1', 'definition_id': 'c3'}}], 'items': []},
     [{'where': 'WorkItem:w1', 'field': '*', 'source': 'present', 'graph': 'missing'}]),
    ({'instance': {'status': 'RUNNING', 'is_deleted': True}, 'items': []}, {'nodes': [{'node': {'status': 'RUNNING'}}], 'items': []},
     [{'where': 'ProcessInstance', 'field': '*', 'source': 'deleted', 'graph': 'present'}]),
    ({'instance': None, 'items': []}, {'nodes': [], 'items': []}, []),
])

def test_실행_반영의_어긋남은_원천과_그래프가_다른_칸마다_한_줄이다(source, graph, want):
    assert repair.execution_drift(source, graph) == want


@pytest.mark.parametrize('by, reason, tamper, words', [
    ('', '다시 보냄', False, 'actor and reason'),
    ('강사', ' ', False, 'actor and reason'),
    ('강사', '다시 보냄', True, 'integrity mismatch'),
])
def test_수리_의도는_누가_왜를_적고_검토한_원천이_그대로일_때만_만든다(by, reason, tamper, words):
    plan = {'source': {'a': 1}, 'source_hash': repair.digest({'a': 1}), 'dependents': []}
    if tamper:
        plan['source'] = {'a': 2}
    with pytest.raises(ValueError) as caught:
        repair.intent(plan, by, reason, None)
    assert words in str(caught.value)


def test_원천_조회는_한_트랜잭션의_한_시점으로_읽는다(world):
    """P5-25: autocommit 연결에 `set transaction` 을 보내 경고만 남고 문장마다 따로 읽었다."""
    with repair.source_snapshot(world.rt.repo) as c:
        assert c.execute('show transaction_isolation').fetchone()['transaction_isolation'] == 'repeatable read'
        first = c.execute('select now() as t').fetchone()['t']
        second = c.execute('select now() as t').fetchone()['t']
        assert first == second                                              # 한 트랜잭션 안(now() 는 트랜잭션 시작 시각)


def test_반영된_처리_건을_조회하면_어긋남이_없고_그래프를_바꾸면_그_칸이_보인다(world):
    alert, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01')
    world.rt.reconcile_projections(limit=200)
    plan = repair.inspect_execution(world.rt.repo, world.rt.hooks.query_cypher, 'hyd', pid)
    assert plan['kind'] == 'Execution' and plan['pending'] == [] and plan['drift'] == []
    world.rt.hooks.record_cypher('MATCH (p:ProcessInstance {id:$id}) SET p.status = $status', id=pid, status='COMPLETED')
    plan = repair.inspect_execution(world.rt.repo, world.rt.hooks.query_cypher, 'hyd', pid)
    assert {'where': 'ProcessInstance', 'field': 'status', 'source': 'RUNNING', 'graph': 'COMPLETED'} in plan['drift']


def test_실행_반영_수리는_검토한_계획대로_한_번만_다시_보내고_같은_요청은_같은_영수증이다(world):
    alert, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01')
    world.rt.reconcile_projections(limit=200)
    q = world.rt.hooks.query_cypher
    plan = repair.inspect_execution(world.rt.repo, q, 'hyd', pid)
    rid = str(uuid.uuid4())
    first = repair.repair_execution(world.rt.repo, q, 'hyd', pid, by='강사', reason='그래프 다시 보냄', plan=plan, request_id=rid)
    assert first['status'] == 'QUEUED' and world.rt.repo.projection_status('hyd', pid)['pending'] == 1
    again = repair.repair_execution(world.rt.repo, q, 'hyd', pid, by='강사', reason='그래프 다시 보냄', plan=plan, request_id=rid)
    assert again == first and world.rt.repo.projection_status('hyd', pid)['pending'] == 1
    with pytest.raises(ValueError, match='reused with a different intent'):
        repair.repair_execution(world.rt.repo, q, 'hyd', pid, by='강사', reason='다른 까닭', plan=plan, request_id=rid)
    # 보통 반영기가 실제 영수증으로 끝낸다. 반영기는 오래된 대기부터 한 번에 limit 건만 보내므로, 앞 테스트 · 지식 다시 넣기
    # (enqueue_knowledge_projections — 테넌트의 모든 처리 건)가 쌓은 대기가 limit 보다 많으면 한 번으로는 이 처리 건까지 닿지 않는다(전체 테스트 1)
    backlog = len(world.rt.repo.pending_projections('hyd', 100000))
    for _ in range(backlog // 200 + 1):
        world.rt.reconcile_projections(limit=200)
        if world.rt.repo.projection_status('hyd', pid)['pending'] == 0:
            break
    assert world.rt.repo.projection_status('hyd', pid)['pending'] == 0, f'대기 {backlog}건을 다 보낸 뒤에도 수리 작업이 남았다'


def test_원천이_조회_뒤에_바뀌면_수리하지_않고_다시_조회하라고_한다(world):
    alert, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01')
    world.rt.reconcile_projections(limit=200)
    q = world.rt.hooks.query_cypher
    plan = repair.inspect_execution(world.rt.repo, q, 'hyd', pid)
    world.clear_alert(alert)                                           # 조회 뒤 처리 건이 움직였다
    world.poll(3)
    world.rt.reconcile_projections(limit=200)
    with pytest.raises(ValueError, match='inspect again'):
        repair.repair_execution(world.rt.repo, q, 'hyd', pid, by='강사', reason='다시 보냄', plan=plan, request_id=str(uuid.uuid4()))


def test_사건_반영_수리는_울타리_위_판번호로_다시_넣는다(tmp_path, neo4j_graph):
    store = Store(str(tmp_path / 'process.sqlite3'))
    try:
        inc = machine.Incident.from_card('INC-REPAIR-1', {'alert': {'alertId': 'A-1', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'},
                                                         'recommended': []}, _cooling_policy())
        store.save({inc.id: inc}, {}, [])
        neo4j_graph.query('CREATE (:CaseProjection {id:"Incident:INC-REPAIR-1", revision: 999, payload_hash: "x"})')   # 그래프의 울타리가 원천보다 앞섰다
        plan = repair.inspect_case(store, neo4j_graph.query, 'Incident', inc.id)
        assert plan['graph']['fence']['revision'] == 999 and plan['pending']
        out = repair.repair_case(store, neo4j_graph.query, 'Incident', inc.id, by='강사', reason='울타리 앞섬', plan=plan,
                                 request_id=str(uuid.uuid4()))
        assert out['status'] == 'QUEUED' and out['revision'] > 999                                  # 다음 판번호가 울타리 위
        assert store.case_projection_batch()[0]['revision'] == out['revision']
    finally:
        store.db.close()
