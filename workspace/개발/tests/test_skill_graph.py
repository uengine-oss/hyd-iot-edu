"""조치 방법(스킬) 지식 쓰기(procsvc/skill_graph.py) — 실제 그래프(compose neo4j 이미지 + kg-seed 와 같은 시드). 한 트랜잭션 · 영수증 · 낙관적 판본."""
import uuid

import pytest

from procsvc import skill_graph
from procsvc.main import SKILL_Q

VALUES = {'name': '시험 조치', 'description': '시험', 'kind': 'work_order', 'sopId': 'SOP-TEST-01', 'failureMode': None, 'relation': 'REMEDIED_BY',
          'steps': ['본다', '적는다'], 'approver': 'role:maint-mgr', 'affects': None}


@pytest.fixture
def session(course_graph):                                   # 수업 지식(FailureMode 등)이 든 학생 PC 그래프 — kg-seed 만으로는 대상이 없다
    with course_graph.driver.session() as s:
        yield s, course_graph


def fm_id(graph):
    return graph.query('MATCH (f:FailureMode) RETURN f.id AS id ORDER BY f.id LIMIT 1')[0]['id']


def test_같은_요청을_다시_보내면_같은_결과를_돌려주고_두_번_만들지_않는다(session):
    s, graph = session
    rid, values = str(uuid.uuid4()), dict(VALUES, failureMode=fm_id(graph))
    first = skill_graph.write(s, SKILL_Q, 'skill:test-once', values, create=True, request_id=rid, by='강사')
    again = skill_graph.write(s, SKILL_Q, 'skill:test-once', values, create=True, request_id=rid, by='강사')
    assert first == again
    assert graph.query("MATCH (k:Skill {id:'skill:test-once'}) RETURN count(k) AS n")[0]['n'] == 1


def test_같은_요청_번호로_다른_내용을_보내면_충돌로_거절한다(session):
    s, graph = session
    rid, values = str(uuid.uuid4()), dict(VALUES, failureMode=fm_id(graph))
    skill_graph.write(s, SKILL_Q, 'skill:test-two', values, create=True, request_id=rid, by='user:me')
    with pytest.raises(skill_graph.Conflict):
        skill_graph.write(s, SKILL_Q, 'skill:test-two', dict(values, name='다른 이름'), create=True, request_id=rid, by='user:me')


def test_쓸_수_없는_관계는_학생이_고를_말로_거절한다(session):
    s, graph = session
    with pytest.raises(ValueError) as refused:
        skill_graph.write(s, SKILL_Q, 'skill:test-rel', dict(VALUES, failureMode=fm_id(graph), relation='CAUSED_BY'), create=True, by='user:me')
    assert "관계 'CAUSED_BY'" in str(refused.value) and '근본 조치 · 즉시 완화 · 예방 조치' in str(refused.value)


def test_없는_스킬을_고치면_그_스킬_이름으로_KeyError(session):
    s, _ = session
    with pytest.raises(KeyError) as missing:
        skill_graph.write(s, SKILL_Q, 'skill:no-such', dict(VALUES), create=False, expected_revision='x', by='user:me')
    assert missing.value.args == ('skill:no-such',)


def test_쓰기마다_영수증_유일_제약을_새로_만들지_않는다(neo4j_graph):
    with neo4j_graph.driver.session() as s:
        with pytest.raises((ValueError, KeyError)):          # 빈 그래프 — 고장 유형이 없어 쓰기는 사유로 멈춘다(제약을 만드는지만 본다). 인자 실수(TypeError)로는 지나가지 않는다
            skill_graph.write(s, SKILL_Q, 'skill:x', dict(VALUES, failureMode='fm:none'), create=True, by='user:me')
    names = [r['name'] for r in neo4j_graph.query('SHOW CONSTRAINTS YIELD name RETURN name')]
    assert 'knowledge_edit_id' not in names                 # 제약은 그래프 적재 때 한 곳(constraints.cypher v2_knowledgeedit_id)


# ---------------------------------------------------------------- 화면에서 만든 조치 방법이 판단까지 닿는가 (전수검사 10-G1 · G2 · G3)
COOLING_LOSS = 'fm:cooler-cooling-loss'


def _new_skill(world, **change):
    body = dict(name='쿨러 호스 교체', description='시험', sopId='SOP-MY-21', failureMode=COOLING_LOSS, relation='REMEDIED_BY', kind='work_order',
                steps='호스를 잠근다\n호스를 바꾼다', approver='role:maint-mgr', by='user:me', request_id=str(uuid.uuid4()))
    return world.api('POST', '/api/kg/skills', dict(body, **change))


def test_화면에서_고장_유형에_연결한_작업지시_조치_방법은_그_고장의_판단_후보로_나오고_그_SOP_로_작업지시를_낸다(world, course_graph):
    """수업 지식의 후보 규칙은 문서가 경보 · 원인 조건으로 진술한 것뿐이라, 화면에서 만든 조치 방법은 저장만 되고 어느 판단에도 나오지 않았다
    (적용 규칙 칸 「없음」). 원자 조치도 없어, 나왔더라도 승인 뒤 그 SOP 가 아니라 일반 점검 오더가 나갔다."""
    import json, urllib.request
    from test_neo4j_seed import problems
    status, made = _new_skill(world)
    assert status == 200, made
    assert [r['id'] for r in made['rules']] == ['rule:cand-cooler-cooling-loss'], '이 고장 유형으로 고르는 후보 규칙에 합류한다'
    assert made['actions'] == [{'code': 'WO_CREATE', 'name': '정비 작업지시 발행', 'kind': 'transaction', 'value': 'SOP-MY-21'}]
    assert problems(course_graph) == [], '만든 규칙이 다음 시작의 지식 되읽기 검사(seed_checks)를 지나야 한다 — 걸리면 시스템이 켜지지 않는다'
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.reported_for('HYD-01')
    req = urllib.request.Request(world.stack.services['agent'].url + '/api/agent/decide',
                                 data=json.dumps({'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=120) as r:
        judged = json.loads(r.read())
    assert judged['status'] == 'EVALUATED', judged.get('error') or judged.get('explanation')
    cards = {o['id']: o for o in judged['result']['options']}
    mine = cards.get('skill:sop-my-21')
    assert mine, f"화면에서 만든 조치 방법이 후보에 없다: {sorted(cards)}"
    assert {'skill:sop-cool-11', 'skill:sop-cool-14'} <= set(cards), '수업 문서의 후보는 그대로다'
    assert mine['feasible'] and mine['window']['immediate'] is True and mine['approver']['id'] == 'role:maint-mgr'
    assert [(a['code'], a['value']) for a in mine['actions']] == [('WO_CREATE', 'SOP-MY-21')]
    from procsvc.instances import action_kind
    from procsvc.work_orders import request_for_option
    assert action_kind(mine) == 'work_order'
    item = request_for_option(mine)
    assert (item['sop'], item['value'], item['source']) == ('SOP-MY-21', 'SOP-MY-21', 'approved-action')


def test_같은_고장_유형에_둘째_조치_방법을_연결하면_같은_후보_규칙에_합류한다(world, course_graph):
    assert _new_skill(world)[0] == 200
    status, second = _new_skill(world, sopId='SOP-MY-22', name='쿨러 호스 점검', relation='MITIGATED_BY')
    assert status == 200 and [r['id'] for r in second['rules']] == ['rule:cand-cooler-cooling-loss'], second
    rules = course_graph.query("MATCH (:DecisionTable {id:'dt:action-candidates'})-[:HAS_RULE]->(r:Rule)-[t:TESTS]->(:InputData {id:'in:failure-mode'}) "
                                    "WHERE t.value = $fm RETURN r.id AS id, r.`when` AS w", fm=COOLING_LOSS)
    assert rules == [{'id': 'rule:cand-cooler-cooling-loss', 'w': "failure_mode == 'fm:cooler-cooling-loss'"}]


def test_예방_조치로_연결한_조치_방법은_경보_대응_후보_규칙을_만들지_않는다(world, course_graph):
    status, made = _new_skill(world, relation='PREVENTED_BY')
    assert status == 200 and made['rules'] == [], made
    assert course_graph.query("MATCH (r:Rule {id:'rule:cand-cooler-cooling-loss'}) RETURN r.id AS id") == []


@pytest.mark.parametrize('change, says', [
    ({'kind': 'control'}, '설비 명령 조치 방법은 이 화면에서 만들 수 없습니다'),
    ({'approver': ''}, '승인 역할을 고르세요'),
], ids=['설비 명령 종류 — 명령 · 값을 정할 칸이 없다', '승인 역할 없음 — 서버가 지어 넣지 않는다'])
def test_화면에서_만들_수_없는_조치_방법은_저장하지_않고_까닭과_길을_말한다(world, course_graph, change, says):
    status, out = _new_skill(world, **change)
    assert status == 400 and says in out['detail'], out
    assert course_graph.query("MATCH (k:Skill {sopId:'SOP-MY-21'}) RETURN k.id AS id") == []
    assert course_graph.query("MATCH (r:Rule {id:'rule:cand-cooler-cooling-loss'}) RETURN r.id AS id") == [], '거절한 저장이 규칙을 남겼다'
