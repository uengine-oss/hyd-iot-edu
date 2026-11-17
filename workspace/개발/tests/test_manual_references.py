"""참고 절차 · 이미 있는 조치 방법 다시 가리키기(procsvc/manual_references.py) — 실행 후보가 아닌 원문 절차는 실행 연결을 갖지 않고, 다른 문서의
조치 방법을 가리킬 때는 원문 번호 · 전체 단계 · 대조한 실행 계약 지문이 그대로여야 한다. 대상 조치 방법은 그래프가 돌려주는 계약 모양(dict)이다 —
그래프에서 그 계약을 읽는 길(contracts · check_plan)은 test_manual_graph 의 교대 인계 문서(HI-01) 시험 둘 — 참고 절차 적재 · 다시 가리키기 — 이 본다."""
import pytest

from procsvc import manual_references as mr

REF = {'kind': 'reference', 'executable': False}


def test_참고_절차는_실행_연결_없이_참고로만_남는다():
    assert mr.reference_shape('SOP-HO-11', REF) == dict(kind='reference', executable=False, failureMode=None, relation=None, approver=None)


@pytest.mark.parametrize('link, says', [
    ({'kind': 'reference', 'executable': True}, '실행 후보에서 빼야'),
    ({'kind': 'work_order', 'executable': False}, '일반 원문 참고 절차'),
    (dict(REF, failureMode='fm:x'), '고장 유형'),
    (dict(REF, actions=[{'action': 'action:x'}]), '원자 조치'),
    (dict(REF, scope='purchase'), '구매'),
], ids=['실행 후보', '종류가 참고 아님', '고장 유형', '원자 조치', '구매 범위'])
def test_참고_절차에_실행_연결을_붙이면_화면_말로_거절한다(link, says):
    with pytest.raises(ValueError, match=says):
        mr.reference_shape('SOP-HO-11', link)


PIN = 'a' * 64


@pytest.mark.parametrize('procedure, link, want', [
    ({'id': 'SOP-HO-11'}, REF, {}),
    ({'id': 'SOP-HO-11', 'existing_skill_id': 'skill:sop-ho-11', 'reference_contract_sha256': PIN}, REF,
     {'existing_skill_id': 'skill:sop-ho-11', 'reference_contract_sha256': PIN}),
], ids=['다시 가리키지 않음', '다시 가리킴'])
def test_다시_가리키기는_대상과_대조한_지문을_함께_적는다(procedure, link, want):
    assert mr.binding_shape(procedure, link) == want


@pytest.mark.parametrize('procedure, link, says', [
    ({'id': 'S', 'existing_skill_id': 'skill:x', 'reference_contract_sha256': PIN}, {'kind': 'work_order'}, '일반 원문 참고 절차로만'),
    ({'id': 'S', 'existing_skill_id': 'SKILL X', 'reference_contract_sha256': PIN}, REF, '조치 방법\\(skill:…\\)을 고르세요'),
    ({'id': 'S', 'existing_skill_id': 'skill:x'}, REF, '지문이 없습니다'),
], ids=['참고가 아닌 연결', '대상 id 꼴', '지문 없음'])
def test_다시_가리키기의_빈틈은_거절한다(procedure, link, says):
    with pytest.raises(ValueError, match=says):
        mr.binding_shape(procedure, link)


STEPS = [{'order': 1, 'text': '인수 확인'}, {'order': 2, 'text': '기록'}]
TARGET = {'id': 'skill:sop-ho-11', 'sopId': 'SOP-HO-11', 'steps': STEPS, 'contract_sha256': PIN, 'owner': 'doc-1'}


def bound(**over):
    return {'id': 'SOP-HO-11', 'existing_skill_id': 'skill:sop-ho-11', 'reference_contract_sha256': PIN, 'steps': STEPS, **over}


def test_번호_단계_계약이_그대로인_조치_방법만_다시_가리킨다():
    out = mr.check_binding(bound(), TARGET)
    assert (out['skill'], out['contract_sha256'], out['owner']) == ('skill:sop-ho-11', PIN, 'doc-1')
    assert out['source_steps_sha256'] == mr.digest(STEPS)


@pytest.mark.parametrize('procedure, target, says', [
    (bound(), None, '지식에 없습니다'),
    (bound(id='SOP-HO-12'), TARGET, 'SOP 번호와 다릅니다'),
    (bound(steps=[{'order': 1, 'text': '인수 확인'}]), TARGET, '똑같지 않습니다'),
    (bound(reference_contract_sha256='b' * 64), TARGET, '실행 계약이 바뀌었습니다'),
], ids=['대상 없음', '번호 다름', '단계 다름', '계약 바뀜'])
def test_대상과_다르면_까닭을_말하며_다시_가리키지_않는다(procedure, target, says):
    with pytest.raises(ValueError, match=says):
        mr.check_binding(procedure, target)


def test_지문은_키_순서와_상관없이_같은_내용이면_같다():
    assert mr.digest({'a': 1, 'b': [1, 2]}) == mr.digest({'b': [1, 2], 'a': 1}) != mr.digest({'a': 1, 'b': [2, 1]})
