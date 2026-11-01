"""판단 채점 API(procsvc/eval_api.py) — 학생 PC 구성(world: 실제 process · agent · 수업 지식 그래프)에서 포털과 같은 경로로."""
import pytest

from procsvc import judgment_eval

TENANT = 'hyd'


@pytest.fixture
def golden(world, course_graph):
    """정답표 항목 하나 — 수업 지식 그래프에 있는 원인 → 고장 유형 → 조치 이름으로(schema: Cause-CAUSES->FailureMode-REMEDIED_BY->Skill)."""
    from procsvc import judgment_eval
    judgment_eval.PgEvalStore(world.dsn, TENANT).reset()
    rows = course_graph.query("MATCH (c:Cause)-[:CAUSES]->(f:FailureMode)-[:MITIGATED_BY|REMEDIED_BY]->(k:Skill) "
                              "RETURN c.id AS cause, f.id AS fm, k.id AS skill ORDER BY c.id, k.id LIMIT 1")
    if not rows:
        pytest.fail('수업 지식 그래프에서 원인 → 고장 유형 → 조치 한 줄을 찾지 못했다 — course_graph 시드 확인')
    row = rows[0]
    item = {'id': 'cooler-auto', 'title': '쿨러 성능 저하', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {},
            'expected': {'cause': row['cause'], 'failure_mode': row['fm']}, 'allowed_top': [row['skill']], 'forbidden': [],
            'required_evidence': [row['skill']]}
    status, body = world.api('POST', '/api/eval/golden/items', {'item': item, 'by': '수강생'})
    assert status == 201, body
    yield item
    judgment_eval.PgEvalStore(world.dsn, TENANT).reset()


def test_정답표는_설비_목록과_가정_사실_선택지를_서버에서_준다(world):
    status, body = world.api('GET', '/api/eval/golden')
    assert status == 200
    assert body['assets'] == ['HYD-01', 'HYD-02', 'HYD-03']
    assert {'plc_mode', 'plc_state', 'standby_ready', 'fan100_hours'} == set(body['facts'])
    assert all('/api/' not in note for note in body['paths'].values())


def test_그래프에_없는_이름을_적은_정답표는_저장하지_않는다(world):
    item = {'id': 'bad-names', 'title': '없는 이름', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {},
            'expected': {'cause': 'cause:no-such', 'failure_mode': 'fm:no-such'}, 'allowed_top': ['skill:no-such'], 'forbidden': [],
            'required_evidence': ['evd:no-such']}
    status, body = world.api('POST', '/api/eval/golden/items', {'item': item, 'by': '수강생'})
    assert status == 400 and '지식 그래프에 없는 이름' in body['detail']


@pytest.mark.parametrize('path', ['/api/eval/runs?limit=0', '/api/eval/runs?limit=101', '/api/eval/worker-candidates?limit=-1'],
                         ids=['실행 0', '실행 101', '후보 음수'])
def test_목록_수는_1부터_100까지만_받는다(world, path):
    status, body = world.api('GET', path)
    assert status == 400 and '1~100' in body['detail']


def test_규칙_판단으로_여러_번_채점하면_검사마다_맞은_횟수가_남는다(world, golden):
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.reported_for('HYD-01')                               # 설비 값이 없으면 판단은 「근거 조회 불완전」으로 보류된다(규칙대로)
    with world.reporting('HYD-01'):                            # 판단을 두 번 도는 동안에도 설비는 1초마다 보고한다(실제 설비처럼)
        status, run = world.api('POST', '/api/eval/runs', {'path': 'decide', 'by': '수강생', 'repeats': 2})
    assert status == 201, run
    [item] = run['items']
    assert item['status'] not in judgment_eval.NOT_JUDGED, (item['status'], item['reason'])  # 판단이 실제로 났는지부터
    assert item['repeats'] == 2 and set(item['check_hits']) == {'cause', 'top', 'forbidden', 'evidence'}
    assert item['checks']['forbidden']['scored'] is False                                  # 정답표에 빠질 조치가 없다 — 점수에 넣지 않음
