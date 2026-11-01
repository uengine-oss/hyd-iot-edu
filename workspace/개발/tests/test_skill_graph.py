"""조치 방법(스킬) 지식 쓰기(procsvc/skill_graph.py) — 실제 그래프(compose neo4j 이미지 + kg-seed 와 같은 시드). 한 트랜잭션 · 영수증 · 낙관적 판본."""
import uuid

import pytest

from procsvc import skill_graph
from procsvc.main import SKILL_Q

VALUES = {'name': '시험 조치', 'description': '시험', 'kind': 'workOrder', 'sopId': 'SOP-TEST-01', 'failureMode': None, 'relation': 'REMEDIED_BY',
          'steps': ['본다', '적는다'], 'approver': None, 'affects': None}


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
    skill_graph.write(s, SKILL_Q, 'skill:test-two', values, create=True, request_id=rid)
    with pytest.raises(skill_graph.Conflict):
        skill_graph.write(s, SKILL_Q, 'skill:test-two', dict(values, name='다른 이름'), create=True, request_id=rid)


def test_쓸_수_없는_관계는_학생이_고를_말로_거절한다(session):
    s, graph = session
    with pytest.raises(ValueError) as refused:
        skill_graph.write(s, SKILL_Q, 'skill:test-rel', dict(VALUES, failureMode=fm_id(graph), relation='CAUSED_BY'), create=True)
    assert "관계 'CAUSED_BY'" in str(refused.value) and '근본 조치 · 즉시 완화 · 예방 조치' in str(refused.value)


def test_없는_스킬을_고치면_그_스킬_이름으로_KeyError(session):
    s, _ = session
    with pytest.raises(KeyError) as missing:
        skill_graph.write(s, SKILL_Q, 'skill:no-such', dict(VALUES), create=False, expected_revision='x')
    assert missing.value.args == ('skill:no-such',)


def test_쓰기마다_영수증_유일_제약을_새로_만들지_않는다(neo4j_graph):
    with neo4j_graph.driver.session() as s:
        with pytest.raises(Exception):          # 빈 그래프 — 고장 유형이 없어 쓰기는 사유로 멈춘다(제약을 만드는지만 본다)
            skill_graph.write(s, SKILL_Q, 'skill:x', dict(VALUES, failureMode='fm:none'), create=True)
    names = [r['name'] for r in neo4j_graph.query('SHOW CONSTRAINTS YIELD name RETURN name')]
    assert 'knowledge_edit_id' not in names                 # 제약은 그래프 적재 때 한 곳(constraints.cypher v2_knowledgeedit_id)
