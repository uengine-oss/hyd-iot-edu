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


BAD_WORDS = re.compile(r'EXCLUDE|Rule|Skill|Step|->|권고 카드|SOP|원자 조치|TRUE|FALSE|UNKNOWN')      # 안쪽 이름 · 그래프 관계 · 옛 말(반말 끝은 아래에서 「니다」로 끝나는지로 본다)


def test_조치_후보_가드레일의_거절_문장은_화면_말로_쓴_존댓말이고_어느_후보인지를_댄다():
    """V 8절 1(2026-11-16): 승인 보류(409)에 「권고 카드 skill:…가 규정(EXCLUDE 규칙)에 걸려 있다」가 그대로 나왔다 — 「권고 카드」(화면 말은 조치 후보) ·
    「EXCLUDE 규칙」(안쪽 효과 이름) · 반말 끝. 이 문장은 승인 보류 · 미리 보기 거절 · 모의 판단의 거절 사유로 학생이 읽는다. 다섯 거절을 모두 일으켜 문장마다 본다."""
    base = {'id': 'skill:sop-cool-11', 'selectedBy': [{'rule': 'r'}], 'feasible': True, 'violations': [], 'approver': {'id': 'role:operator'}, 'steps': [{'id': 's'}]}
    cases = {'제외 규칙': dict(base, violations=[{'rule': 'rule:x', 'effect': 'EXCLUDE'}]), '실행 불가': dict(base, feasible=False), '승인 역할 없음': dict(base, approver={}),
             '단계 없음': dict(base, steps=[]), '고른 규칙 없음': dict(base, selectedBy=[]), '참고 절차': dict(base, kind='reference')}
    seen = {}
    for name, card in cases.items():
        out = guardrail.check_cards({'options': [card], 'recommended': card['id']})
        assert len(out) == 1, (name, out)
        seen[name] = out[0]
    for name, text in seen.items():
        assert text.endswith('니다') and not BAD_WORDS.search(text), (name, text)
        # 후보 id 뒤에는 받침을 타지 않는 조사 하나와 빈칸: 화면이 id 를 이름으로 바꿔도(ui.js ID_RE — 쌍점 · 점 · 붙임표는 id 로 읽는다) 문장이 어긋나지 않는다
        assert re.match(r'조치 후보 skill:sop-cool-11[의에] ', text), (name, text)
    assert seen['제외 규칙'] == seen['실행 불가'] and '제외 규칙' in seen['제외 규칙'] and '실행할 수 없습니다' in seen['제외 규칙']      # 학생이 다음에 할 일(다른 안 · 예측 다시 보기)을 아는 말
    assert len(set(seen.values())) == 5 and '승인 역할' in seen['승인 역할 없음'] and '단계' in seen['단계 없음'] and '규칙' in seen['고른 규칙 없음'] and '참고 절차' in seen['참고 절차']
