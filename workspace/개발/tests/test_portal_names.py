"""포털 이름 사전 생성기(workspace/개발/scripts/portal_names.py) — 고정 재료(시드 · 서명 묶음 · 업무 스킬)만으로, 누가 언제 돌려도 같은 사전이 나오는가."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import portal_names  # noqa: E402


def build(graph):
    with graph.driver.session() as session:
        return portal_names.build(session)


def test_수업_그래프에서_만든_사전은_시드_수업_지식_업무_스킬을_담고_실행_기록은_뺀다(course_graph):
    names = build(course_graph)
    from entsim.state import SKILL_NAMES
    assert {'skill:sop-cool-11', 'fm:cooler-cooling-loss', 'cause:cooler-fin-fouling', 'asset:hyd-01'} <= set(names)
    assert set(SKILL_NAMES) <= set(names)
    assert not [i for i in names if i.startswith(('execution-actor:', 'ks:manual:', 'INC-', 'DEC-'))]


def test_실행_기록이나_학생이_만든_노드가_더해져도_사전은_같다(course_graph):
    before = build(course_graph)
    course_graph.query("CREATE (:ExecutionActor {id: 'execution-actor:hyd:user%3Akim-op', name: '김운전'}), "
                       "(:Skill {id: 'skill:student-made', name: '학생이 만든 조치'})")
    assert build(course_graph) == before


def test_수업_지식을_넣기_전_그래프에서는_까닭을_대고_멈춘다(seeded_graph):
    with pytest.raises(RuntimeError, match='class_knowledge.py ensure'):
        build(seeded_graph)


def test_포털의_이름_사전_파일은_생성기_결과와_같다(course_graph):
    assert portal_names.OUT.read_text(encoding='utf-8') == portal_names.render(build(course_graph)), \
        'it/portal/www/names.json 이 생성기 결과와 다르다 — portal_names.py 로 다시 만든다'
    assert json.loads(portal_names.OUT.read_text(encoding='utf-8'))


def test_수업_지식은_시작이_넣는_문서만_세고_실습_중에_넣는_보충_자료는_뺀다():
    from class_knowledge import ORDER
    docs = portal_names.start_documents()
    assert sorted(d['filename'].split('_')[0] for d in docs) == sorted(ORDER)
    ids = portal_names.material_ids()
    assert 'skill:sop-cool-12' in ids and 'skill:sop-pur-11' in ids
    assert not [i for i in ids if i.startswith('skill:sop-hi-')]          # HI-01 은 실습 17에서 학생이 넣는다


def test_시드가_지우는_옛_노드의_id는_이름_재료에_넣지_않는다():
    ids = portal_names.seed_ids()
    assert {'asset:hyd-01', 'pattern:cooler-degradation'} <= ids
    assert not ids & {'in:chosen-skill', 'rule:avl', 'ks:pricing', 'task:compliance', 'ev:alert'}   # instances.cypher 끝의 DETACH DELETE 문장


def test_화면_이름은_id_로_정해_시드_이름이_바뀌어도_전문어가_돌아오지_않는다(course_graph):
    """넘김 FW → FT: 쉬운 말 표가 옛 시드 이름을 열쇠로 써 「이상 감지기 (CEP)」 · 영문 high · medium · low 가 화면에 돌아왔다."""
    names = build(course_graph)
    assert (names['sys:cep'], names['sys:scada'], names['sys:historian'], names['sys:process']) == ('센서 경보 감지기', '설비 제어', '센서 기록', '업무 처리')
    assert 'high 1' not in names['rule:rank-value'] and '높음 1 · 중간 0.6 · 낮음 0.3' in names['rule:rank-value']


@pytest.mark.parametrize('names, problem', [
    ({**{i: 'x' for i in portal_names.PLAIN if i != 'sys:cep'}, 'r': '정비 작업지시 · high 1 · medium 0.6 · low 0.3'}, "PLAIN 의 id \['sys:cep'\]"),
    ({**{i: 'x' for i in portal_names.PLAIN}, 'r': '정비 작업지시 발행'}, 'high 1 · medium 0.6 · low 0.3'),
], ids=['표의 id 가 재료에 없음', '바꿀 낱말이 어느 이름에도 없음'])
def test_쉬운_말_표가_재료와_어긋나면_조용히_넘기지_않고_멈춘다(names, problem):
    with pytest.raises(RuntimeError, match=problem):
        portal_names.display_names(names)


def test_쉬운_말_표가_맞으면_표의_id_는_그_이름_나머지는_낱말만_바꾼다():
    names = {**{i: 'x' for i in portal_names.PLAIN}, 'r': '정비 작업지시 · high 1 · medium 0.6 · low 0.3', 'w': '정비 작업지시 발행'}
    out = portal_names.display_names(names)
    assert out['sys:cep'] == '센서 경보 감지기'
    assert out['r'] == '정비 오더 · 높음 1 · 중간 0.6 · 낮음 0.3' and out['w'] == '정비 오더 발행'
