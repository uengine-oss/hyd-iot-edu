"""결과 교정 안내(procsvc/result_correction.py) — 폼 계약마다 그 폼의 교정 글만 준다(다른 폼의 규칙을 섞지 않는다)."""
import pytest

from procsvc import result_correction as rc


@pytest.mark.parametrize('contract, name, words', [
    ('manual-source-proposal-v1', '추출 제안', ['page.text', 'page_reviews']),
    ('ask-answer-v1', '질문 답변', ['cannot_answer', 'evidence']),
    ('shift-handover-draft-v1', '인계안', ['needs_check', 'evidence_indices']),
    ('manual-golden-report-v1', '문서 질문 보고', ['golden_request']),
    ('legacy-meaning-candidates-v1', '열 의미 후보', ['legacy_request']),
    (None, '작업 결과', ['폼의 필드']),
], ids=['문서 추출', '질문', '교대', '골든 질문', '옛 DB 뜻', '그 밖'])
def test_교정_안내는_그_폼_계약의_글이다(contract, name, words):
    got = rc.guidance({'contract': contract} if contract else {})
    assert got[0] == name and all(w in got[2] for w in words)


@pytest.mark.parametrize('contract, expected', [('ask-answer-v1', rc.ASK_INSTRUCTIONS), ('shift-handover-draft-v1', rc.HANDOVER_INSTRUCTIONS),
                                                ('manual-source-proposal-v1', '')], ids=['질문', '교대', '작업 지시가 없는 폼'])
def test_첫_실행_지시에_붙는_계약_글은_질문과_교대_폼에만_있다(contract, expected):
    assert rc.instructions(contract) == expected
