"""일반 사람 승인 부품(procsvc/approval_part.py) — 에이전트가 낸 안 목록에서 하나를 고르는 학생 흐름의 승인 계약."""
import pytest

from procsvc import approval_part as ap

ACTIVITY = {'id': 'T_pick', 'type': 'userTask', 'tool': ap.TOOL, 'approval': {'options': 'proposal.options'},
            'inputData': ['proposal'], 'outputData': list(ap.OUTPUTS)}


def _act(**changes):
    act = dict(ACTIVITY, **{k: v for k, v in changes.items() if k != 'approval'})
    if 'approval' in changes:
        act['approval'] = changes['approval']
    return act


@pytest.mark.parametrize('activity, error', [
    (ACTIVITY, None),
    (_act(approval={'options': 'proposal.options', 'recommended': 'proposal.recommended', 'losers': 'proposal.losers', 'docs': 'proposal.docs'}), None),
    (_act(type='serviceTask'), '사람이 하는 userTask'),
    (_act(approval=None), '사람 승인 설정\\(approval\\)이 없습니다'),
    (_act(approval={}), '고를 안이 든 처리 건 값'),
    (_act(approval={'options': 'proposal.options', 'extra': 'x'}), '모르는 칸'),
    (_act(approval={'options': 'proposal..options'}), 'options 는 처리 건 값 이름'),
    (_act(approval={'options': 'proposal.options', 'key': 'a-b'}), 'key 는 안 안의 칸 이름'),
    (_act(inputData=[]), '받을 값\\(inputData\\)에 넣으세요'),
    (_act(outputData=['approval']), 'outputData'),
], ids=['정상', '선택 칸 모두', '사람 단계 아님', '설정 없음', '고를 안 없음', '모르는 칸', '경로 꼴 틀림', '구분 칸 이름 틀림', '입력 값 빠짐', '출력 틀림'])
def test_사람_승인_부품은_고를_안의_자리와_입출력을_정확히_적어야_등록된다(activity, error):
    if error is None:
        ap.validate(activity)
    else:
        with pytest.raises(ValueError, match=error):
            ap.validate(activity)


CFG = {'options': 'proposal.options'}
OPTIONS = [{'slot': 'A', 'reason': '추천'}, {'slot': 'B', 'reason': '대안'}]


@pytest.mark.parametrize('values, option, error', [
    ({'proposal': {'options': OPTIONS}}, 'B', None),
    ({}, 'A', '처리 건에 없습니다'),
    ({'proposal': {'options': []}}, 'A', '비어 있거나 목록이 아닙니다'),
    ({'proposal': {'options': [{'reason': 'x'}]}}, 'A', "1번째 안에 구분 칸 'slot'"),
    ({'proposal': {'options': [{'slot': 'A'}, {'slot': 'A'}]}}, 'A', '두 번 있습니다'),
    ({'proposal': {'options': OPTIONS}}, '', '승인할 안을 고르세요'),
    ({'proposal': {'options': OPTIONS}}, 'C', "있는 안: A, B"),
], ids=['고름', '값 없음', '빈 목록', '구분 칸 없음', '구분 값 겹침', '고르지 않음', '없는 안'])
def test_고른_안은_에이전트가_낸_목록의_한_안이어야_하고_그_사본을_돌려준다(values, option, error):
    if error is None:
        chosen = ap.choose(values, CFG, option)
        assert chosen == OPTIONS[1] and chosen is not OPTIONS[1]
    else:
        with pytest.raises(ValueError, match=error):
            ap.choose(values, CFG, option)


@pytest.mark.parametrize('form, ok', [(ap.FORM, True), ({'fields_json': ap.FORM['fields_json'][:1]}, False), (None, False)],
                         ids=['부품 폼 그대로', '사유 칸을 뺀 폼', '폼 없음'])
def test_승인_폼은_학생_흐름이_바꿀_수_없다(form, ok):
    if ok:
        ap.validate_form(form, 'T_pick')
    else:
        with pytest.raises(ValueError, match='부품 폼'):
            ap.validate_form(form, 'T_pick')
