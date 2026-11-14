"""가드레일(it/agent/agentsvc/guardrail.py) — 명령 권한 없음 · 모든 주장 인용 · 미확인 근거 금지. 사유는 학생이 읽는 한국어."""
import re

import pytest

from agentsvc import guardrail

GOOD = {'citations': ['cause:a', 'evd:a', 'skill:x'], 'causes': [{'id': 'cause:a', 'evidence': [{'id': 'evd:a', 'status': 'PASS', 'passed': True}]}],
        'skills': [{'id': 'skill:x'}], 'freshness': {'ok': True}}


@pytest.mark.parametrize('change, needle', [
    ({}, None),
    ({'citations': []}, '인용한 지식 노드가 하나도 없습니다'),
    ({'freshness': {'ok': False, 'age_s': 90}}, '90초'),
    ({'cmdId': 'CMD-1'}, "설비 명령 칸 'cmdId'"),
    ({'causes': [{'id': 'cause:a', 'evidence': [{'id': 'evd:a', 'status': 'UNKNOWN', 'passed': None}]}]}, '판정이 미확인'),
    ({'skills': [{'id': 'skill:y'}]}, '조치 방법 skill:y를 인용하지 않았습니다'),
    ({'withheld': True}, '보류'),
], ids=['정상', '인용 없음', '오래된 데이터', '명령 칸', '미확인 근거', '조치 방법 미인용', '보류 카드'])
def test_가이드_카드_가드레일은_어긴_것마다_한국어_사유를_낸다(change, needle):
    violations = guardrail.check(dict(GOOD, **change))
    if needle is None:
        assert violations == []
    else:
        assert any(needle in v for v in violations), violations
        assert not any(re.search(r'\b(is|not|has|list|empty|withheld)\b', v) for v in violations)      # 영어 문장 0


def test_조치_카드_가드레일은_권고_카드의_규정_승인_역할_단계를_본다():
    rec = {'id': 'k1', 'selectedBy': [{'rule': 'r'}], 'feasible': True, 'violations': [], 'approver': {'id': 'role:operator'}, 'steps': [{'id': 's'}]}
    assert guardrail.check_cards({'options': [rec], 'recommended': 'k1'}) == []
    bad = dict(rec, selectedBy=[], approver={}, steps=[], kind='reference')
    out = guardrail.check_cards({'options': [bad], 'recommended': 'k1'})
    assert len(out) == 4 and all('k1' in v for v in out)
