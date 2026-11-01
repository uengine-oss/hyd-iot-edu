"""판본 단위 실행 그래프(procsvc/execution_graph.py) — 정의 판본마다 흐름 노드를 따로 두고, 처리 건 · 작업 행을 그 판본 노드에 잇는다.
반영 질의는 실제 Neo4j(수업 그래프)에 실제로 쓰고 읽는다."""
import pytest

from procsvc import engine
from procsvc.execution_graph import INSTANCE_Q, definition_projection, scoped


def _defn(def_id='my flow/1', version='2'):
    raw = {'processDefinitionId': def_id, 'processDefinitionName': '내 흐름', 'version': version,
           'events': [{'id': 's', 'name': '시작', 'type': 'startEvent'}, {'id': 'e', 'name': '끝', 'type': 'endEvent'}],
           'activities': [{'id': 't', 'name': '확인', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:f'},
                          {'id': 'a', 'name': '판단', 'type': 'userTask', 'role': 'AI', 'agentMode': 'complete', 'orchestration': 'cliagents'}],
           'gateways': [{'id': 'g', 'name': '분기', 'type': 'exclusiveGateway'}],
           'sequences': [{'id': 'f1', 'source': 's', 'target': 't'}, {'id': 'f2', 'source': 't', 'target': 'g'},
                         {'id': 'f3', 'source': 'g', 'target': 'a', 'condition': "x == 'y'"},
                         {'id': 'f4', 'source': 'g', 'target': 'e', 'properties': {'default': True}}, {'id': 'f5', 'source': 'a', 'target': 'e'}],
           'roles': [{'name': '운전원', 'endpoint': 'role:operator'}, {'name': 'AI', 'endpoint': 'sys:agent'}], 'data': [], 'forms': {}}
    return engine.Definition.from_dict(raw)


@pytest.mark.parametrize('parts, want', [
    (('hyd', 'c3_cooling', '1'), 'proc-version:hyd:c3_cooling:1'),
    (('hyd', 'my flow/1', '2'), 'proc-version:hyd:my%20flow%2F1:2'),       # 구분자(:)와 겹치는 글자는 감싸서 판본 노드 id 가 섞이지 않는다
    (('t:1', 'a', '1'), 'proc-version:t%3A1:a:1'),
])
def test_판본_노드_id는_테넌트_정의_판본마다_따로이고_구분자를_감싼다(parts, want):
    assert scoped('proc-version', *parts) == want


def test_정의_판본의_노드와_선은_그_판본_id_아래에_종류별_칸으로_나온다():
    projection, node_id = definition_projection(_defn(), 'hyd')
    assert projection['version_id'] == 'proc-version:hyd:my%20flow%2F1:2'
    nodes = {n['props']['element_id']: n for n in projection['nodes']}
    assert {k: n['label'] for k, n in nodes.items()} == {'t': 'Task', 'a': 'Task', 's': 'Event', 'e': 'Event', 'g': 'Gateway'}
    assert nodes['t']['props']['taskType'] == 'user' and 'agentMode' not in nodes['t']['props']
    assert nodes['a']['props']['agentMode'] == 'COMPLETE' and nodes['a']['props']['orchestration'] == 'cliagents'
    assert nodes['s']['props']['position'] == 'start' and nodes['g']['props']['gatewayType'] == 'exclusive'
    assert node_id('t') == 'flow:hyd:my%20flow%2F1:2:t'
    flows = {f['id']: f for f in projection['flows']}
    assert flows['f3']['condition'] == "x == 'y'" and flows['f4']['isDefault'] is True and flows['f1']['isDefault'] is False
    assert flows['f2']['source'] == node_id('t') and flows['f2']['target'] == node_id('g')


def test_다른_판본의_같은_단계는_다른_노드다():
    one, _ = definition_projection(_defn(version='1'), 'hyd')
    two, _ = definition_projection(_defn(version='2'), 'hyd')
    assert {n['id'] for n in one['nodes']}.isdisjoint({n['id'] for n in two['nodes']})


def test_처리_건을_반영하면_실행_그래프에서_판본_작업_행_담당이_읽힌다(world):
    alert, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01')
    world.rt.reconcile_projections(limit=200)
    world.main.case_projector.drain()                                  # 사건 노드가 그래프에 들어가면(_incident_projected) 실행 반영을 다시 넣는다
    world.rt.reconcile_projections(limit=200)
    status, out = world.api('GET', f'/api/instances/{pid}/graph')
    assert status == 200, out
    graph, inst = out['graph'], world.inst(pid)
    assert out['projection']['pending'] == 0 and graph is not None
    assert graph['definition']['graph_id'] == scoped('proc-version', 'hyd', inst['proc_def_id'], inst['proc_def_version'])
    assert {w['activity_id'] for w in graph['workitems']} == {w['activity_id'] for w in world.rows(pid)}
    assert graph['asset'] == 'HYD-01' and graph['incident'] == world.values(pid)['incident']
    assert all(w['executes'] for w in graph['workitems']), graph['warnings']           # 작업 행마다 그 판본의 흐름 노드에 이어졌다


def test_실행_반영_질의는_전체_노드를_훑지_않는다(seeded_graph):
    """P5-26 의심: 담당 · 수행자를 라벨 없이 id 로 찾는다 — 실행 계획에 전체 노드 훑기(AllNodesScan)가 없다."""
    with seeded_graph.driver.session() as session:
        plan = session.run('EXPLAIN ' + INSTANCE_Q).consume().plan

    def operators(p):
        yield p['operatorType'].split('@')[0]
        for child in p.get('children') or []:
            yield from operators(child)
    found = list(operators(plan))
    assert 'AllNodesScan' not in found, found                          # 매개변수 없는 EXPLAIN 은 색인 찾기 꼴이 판마다 달라 「전체 훑기 없음」만 판정
