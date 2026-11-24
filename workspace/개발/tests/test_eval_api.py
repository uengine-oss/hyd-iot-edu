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
    status, body = world.api('POST', '/api/eval/golden/items', {'item': item, 'by': 'user:me'})
    assert status == 201, body
    yield item
    judgment_eval.PgEvalStore(world.dsn, TENANT).reset()


def test_정답표는_설비_목록과_가정_사실_선택지를_서버에서_주고_그_값은_판단_엔진이_그_판단_입력으로_받는다(world, course_graph):
    """표 · 열에 이은 판단 입력이 없는 시작 상태의 가정 사실 칸은 기본 제공 현장의 넷이다. 칸마다 지식 그래프의 판단 입력(InputData)이고, 칸이 내는
    값(선택지 · 숫자 칸의 하한)은 판단 엔진이 가정 사실로 받는 그 입력의 형식이다(agentsvc.decide.check_overrides — 정답표 실행이 그 값을 판단에
    넣는다). 칸 이름이나 선택지 값이 지식 · 판단 엔진과 어긋나면 학생이 고른 정답표가 채점 때 거절된다."""
    from agentsvc import decide
    status, body = world.api('GET', '/api/eval/golden')
    assert status == 200
    from hydcommon.topics import ASSETS
    assert body['assets'] == list(ASSETS)                         # 설비 목록의 정본(hydcommon.topics)
    assert set(body['facts']) == {'plc_mode', 'plc_state', 'standby_ready', 'fan100_hours'}, body['facts']
    inputs = course_graph.query('MATCH (i:InputData) WHERE i.variable IS NOT NULL RETURN i.variable AS variable, i.name AS name, i.typeRef AS typeRef')
    for key, field in body['facts'].items():
        values = [value for value, _ in field['choices']] if 'choices' in field else [field.get('min', 0)]
        for value in values:
            assert decide.check_overrides(inputs, {key: value}) == {key: value}, (key, value)
    assert all('/api/' not in note for note in body['paths'].values())


def test_그래프에_없는_이름을_적은_정답표는_저장하지_않는다(world):
    item = {'id': 'bad-names', 'title': '없는 이름', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {},
            'expected': {'cause': 'cause:no-such', 'failure_mode': 'fm:no-such'}, 'allowed_top': ['skill:no-such'], 'forbidden': [],
            'required_evidence': ['evd:no-such']}
    status, body = world.api('POST', '/api/eval/golden/items', {'item': item, 'by': 'user:me'})
    assert status == 400 and body['detail'].startswith('지금 지식 그래프에 없는 항목이 있습니다: cause:no-such, fm:no-such, skill:no-such, evd:no-such'), body
    assert '다시 고르세요' in body['detail'] and ' id ' not in body['detail']      # 학생이 할 일을 말하고, 안쪽 말(id)을 쓰지 않는다


def test_정답표_후보는_지금_그래프에_있는_것뿐이고_어느_것을_골라도_저장된다(world, course_graph):
    """V 8절 9(2026-11-16): 화면이 후보를 정적 이름 사전(names.json)에서 뽑아 그래프에 없는 업무 거래 이름(「정비 요청 취소」 등)이 후보에 섞였고,
    고르면 저장이 400 이었다. 후보는 저장 때 거르는 것과 같은 재료(지금 그래프)에서 온다 — 학생이 넣은 조치도 후보에 나오고, 나온 것은 모두 저장된다."""
    from procsvc import judgment_eval
    judgment_eval.PgEvalStore(world.dsn, TENANT).reset()
    course_graph.query("CREATE (:Skill {id: 'skill:student-own-fix', name: '학생이 넣은 조치'}), (:Rule {id: 'rule:student-own', annotation: '학생이 넣은 규칙 설명'})")
    status, choices = world.api('GET', '/api/eval/choices')
    assert status == 200 and set(choices) == {'cause', 'fm', 'skill', 'evidence', 'rule'}
    in_graph = {r['id'] for r in course_graph.query('MATCH (n) WHERE n.id IS NOT NULL RETURN n.id AS id')}
    offered = {c['id'] for kind in choices.values() for c in kind}
    assert offered and offered <= in_graph, sorted(offered - in_graph)
    assert 'skill:cancel-work-order' not in in_graph and 'skill:cancel-work-order' not in offered      # 업무 시스템의 거래 이름 — 그래프에 없다
    assert {'id': 'skill:student-own-fix', 'name': '학생이 넣은 조치'} in choices['skill']
    assert {'id': 'rule:student-own', 'name': '학생이 넣은 규칙 설명'} in choices['rule'] and {'id': 'rule:student-own', 'name': '학생이 넣은 규칙 설명'} in choices['evidence']
    skills = [c['id'] for c in choices['skill']]
    item = {'id': 'every-choice', 'title': '후보 전부', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {},
            'expected': {'cause': choices['cause'][0]['id'], 'failure_mode': choices['fm'][0]['id']}, 'allowed_top': skills[:-1],
            'forbidden': [{'skill': skills[-1], 'expect': 'excluded', 'rule': choices['rule'][0]['id']}],
            'required_evidence': [c['id'] for c in choices['evidence']]}
    try:
        status, body = world.api('POST', '/api/eval/golden/items', {'item': item, 'by': 'user:me'})
        assert status == 201, body
    finally:
        judgment_eval.PgEvalStore(world.dsn, TENANT).reset()


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
        status, run = world.api('POST', '/api/eval/runs', {'path': 'decide', 'by': 'user:me', 'repeats': 2})
    assert status == 201, run
    [item] = run['items']
    assert item['status'] not in judgment_eval.NOT_JUDGED, (item['status'], item['reason'])  # 판단이 실제로 났는지부터
    assert item['repeats'] == 2 and set(item['check_hits']) == {'cause', 'top', 'forbidden', 'evidence'}
    assert item['checks']['forbidden']['scored'] is False                                  # 정답표에 빠질 조치가 없다 — 점수에 넣지 않음


def test_채점이_적은_진행_기록에_항목마다_결과와_끝난_수가_남는다(world, golden):
    """채점은 N회 판단이 모두 끝나야 결과를 준다 — 그동안 화면이 읽는 진행 기록(GET /api/progress/{request_id})에 실제 단계가 남는지.
    설비 값을 넣지 않았으므로 판단은 규칙대로 보류된다(0점) — 그 결과가 그대로 적힌다(지어낸 진행이 아니다)."""
    import uuid
    rid = str(uuid.uuid4())
    assert world.api('GET', f'/api/progress/{rid}')[1]['state'] == 'none'              # 요청 전: 404 가 아니다
    status, run = world.api('POST', '/api/eval/runs', {'path': 'decide', 'by': 'user:me', 'repeats': 2, 'request_id': rid})
    assert status == 201, run
    status, seen = world.api('GET', f'/api/progress/{rid}')
    assert status == 200 and seen['state'] == 'done' and seen['kind'] == 'eval_run'
    steps = {s['key']: s for s in seen['steps']}
    assert list(steps) == ['golden', 'knowledge', 'item:0', 'save'] and all(s['state'] == 'ok' for s in steps.values())
    [item] = run['items']
    assert steps['item:0']['label'] == golden['title']
    assert item['status'] == 'WITHHELD' and item['reason'].startswith('판단 보류: 근거 조회가 불완전')      # 거절 본문의 사유 칸(원문 JSON 이 아니다) · HTTP 응답 코드는 싣지 않는다
    assert steps['item:0']['note'] == f"항목 1/1 끝 · {item['score']}점 · 판단이 나오지 않음 — {item['reason']}"
    assert steps['golden']['note'] == '항목 1개' and steps['save']['note'] == f"평균 {run['summary']['score']}점 · 항목 1개"


def test_없는_항목을_채점하라는_요청은_진행_기록에도_실패로_남는다(world, golden):
    import uuid
    rid = str(uuid.uuid4())
    status, body = world.api('POST', '/api/eval/runs', {'path': 'decide', 'by': 'user:me', 'items': ['no-such-item'], 'request_id': rid})
    assert status == 404, body
    seen = world.api('GET', f'/api/progress/{rid}')[1]
    assert seen['state'] == 'failed' and 'no-such-item' in seen['error']
    assert [(s['key'], s['state']) for s in seen['steps']] == [('golden', 'ok'), ('knowledge', 'ok')]      # 항목 단계는 시작하지 않았다


def test_코드가_낸_KeyError는_없는_항목_404로_보이지_않는다(world, golden, monkeypatch):
    """전수 대조(2026-11-14): 채점 API 가 KeyError 를 모두 404 「없는 항목 · 실행 · 처리 건: '<열쇠>'」로 바꿔, 코드가 사전에서 없는 열쇠를 읽은
    오류도 학생에게 「없는 항목」으로 보였다. 404 는 찾는 것이 없을 때(NotFound)만이다."""
    from procsvc import judgment_eval
    # 찾는 항목이 없을 때의 404 는 위 test_없는_항목을_채점하라는_요청은… 이 본다

    def broken(self):
        return {}['rows']                                                               # 코드 결함 대역: 없는 열쇠 읽기
    monkeypatch.setattr(judgment_eval.PgEvalStore, 'golden_list', broken)
    try:
        status, body = world.api('GET', '/api/eval/golden')
    except KeyError:
        status, body = 500, None                                                         # 서버 안에서 부른 길: 처리되지 않은 예외 = 500
    assert status == 500, body


# ---------------------------------------------------------------- 지식 수의 정의(지식 지도와 같은 것을 센다)
def _map(world, asset):
    import json
    import urllib.request
    with urllib.request.urlopen(f"{world.stack.services['agent'].url}/api/ontology/graph?asset={asset}", timeout=60) as r:
        return json.loads(r.read())


def test_채점이_말하는_지식_항목_수는_지식_지도가_그리는_항목을_설비_3기에_걸쳐_센_것이고_처리_건을_돌려도_실행_기록은_세지_않는다(world, course_graph):
    """판단 채점은 「지금 지식: 항목 651개」, 홈 · 지식 지도는 349개라고 했다 — 채점이 실행 기록(처리 건 · 작업 · 실행 담당자) 노드까지 세어,
    질문 하나만 해도 「지식 항목 647 → 651」이 되고 전 · 후 비교에 지식 변화로 나왔다. 두 화면이 같은 정의로 센다: 지식 지도가 그리는 것."""
    world.start_cooling()                                   # 실행 기록이 그래프에 생긴다(처리 건 · 작업 · 실행 담당자 투영)
    (records,) = course_graph.query('MATCH (n) WHERE n:ProcessInstance OR n:WorkItem OR n:ExecutionActor RETURN count(n) AS n')
    assert records['n'] > 0, '실행 기록 노드가 없으면 이 시험이 성립하지 않는다'
    status, now = world.api('GET', '/api/eval/knowledge')
    assert status == 200, now
    maps = [_map(world, asset) for asset in ('HYD-01', 'HYD-02', 'HYD-03')]
    shown = {n['id'] for m in maps for n in m['nodes']}
    assert now['nodes'] == len(shown), (now['nodes'], len(shown))
    assert now['scope'] and '설비 3기' in now['scope']
    status, later = world.api('GET', '/api/eval/knowledge')
    assert later['fingerprint'] == now['fingerprint']       # 아무것도 고치지 않았다 — 같은 지식이다


def test_표_정의를_적재해_만든_판단_입력은_정답표의_가정_사실_칸에_그_형식으로_나온다(world, course_graph):
    """탐사 N6: 정답표 화면의 가정 사실 칸이 수업 변수 넷뿐이라, 학생이 지식 › 데이터 원천에서 표 정의를 적재해 만든 판단 입력(업무 DB 표 · 열에 이은
    InputData)을 가정 사실로 적을 수 없었다. 칸은 지금 지식에서 읽는다 — 숫자 · 참/거짓 · 글 형식이 그 칸이 되고, 표 · 열에 잇지 않은 입력과 판단 엔진이
    가정으로 받지 않는 형식은 나오지 않는다. 그 칸으로 적은 항목은 저장된다."""
    from procsvc import judgment_eval
    judgment_eval.PgEvalStore(world.dsn, TENANT).reset()
    course_graph.query("UNWIND [['in:test-line-priority','라인 우선순위','line_priority','number','line_priority'],"
                       "['in:test-shift','교대조','shift_name','string','shift_name'],['in:test-running','라인 가동','line_running','boolean','running'],"
                       "['in:test-blob','첨부','line_blob','json','blob'],['in:test-unbound','표에 잇지 않은 입력','line_note','string',null]] AS r "
                       "CREATE (i:InputData {id:r[0], name:r[1], variable:r[2], typeRef:r[3]}) "
                       "FOREACH (_ IN CASE WHEN r[4] IS NULL THEN [] ELSE [1] END | SET i.table='line_status', i.column=r[4])")
    status, body = world.api('GET', '/api/eval/golden')
    assert status == 200
    added = {k: v for k, v in body['facts'].items() if k not in judgment_eval.FACT_CHOICES}
    assert added == {'line_priority': {'label': '라인 우선순위', 'number': True}, 'shift_name': {'label': '교대조', 'text': True},
                     'line_running': {'label': '라인 가동', 'choices': [[True, '참'], [False, '거짓']]}}, added
    assert {k: body['facts'][k] for k in judgment_eval.FACT_CHOICES} == judgment_eval.FACT_CHOICES
    row = course_graph.query("MATCH (c:Cause)-[:CAUSES]->(f:FailureMode)-[:MITIGATED_BY|REMEDIED_BY]->(k:Skill) RETURN c.id AS cause, f.id AS fm, k.id AS skill ORDER BY c.id LIMIT 1")[0]
    item = {'id': 'line-facts', 'title': '라인 우선순위 2 · 야간조', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION',
            'facts': {'line_priority': 2, 'shift_name': '야간조', 'line_running': False}, 'expected': {'cause': row['cause'], 'failure_mode': row['fm']},
            'allowed_top': [row['skill']], 'forbidden': [], 'required_evidence': [row['skill']]}
    try:
        status, saved = world.api('POST', '/api/eval/golden/items', {'item': item, 'by': 'user:me'})
        assert status == 201, saved
        status, again = world.api('GET', '/api/eval/golden')
        assert [it['facts'] for it in again['items'] if it['id'] == 'line-facts'] == [item['facts']]
    finally:
        judgment_eval.PgEvalStore(world.dsn, TENANT).reset()
