"""승인 카드(it/portal/www/approvalCard.js) — 일반 승인 제안 검사 · 진 안의 이유 줄."""
import pytest

from www_node import run

FILES = ['ui.js', 'plainWords.js', 'approvalCard.js']
A = {'name': 'A', 'reason': '팬 최대', 'score': 3.4}
B = {'name': 'B', 'reason': '부하 낮춤', 'score': 2.1}
CFG = {'options': 'proposal.options', 'key': 'name', 'recommended': 'proposal.recommended', 'losers': 'proposal.losers', 'docs': 'proposal.docs'}


@pytest.mark.parametrize('proposal, problems', [
    # 선택 칸(추천 · 지는 안 · 근거 자료)이 값에 없으면 문제가 아니다 — 서버 approval_part.CONFIG 와 같은 규칙(W1-27)
    ({'options': [A, B]}, 0),
    ({'options': [A], 'recommended': 'A', 'losers': [], 'docs': []}, 0),
    # 있는데 틀리면 문제다
    ({'options': [A], 'recommended': 'Z'}, 1),
    ({'options': [A], 'losers': 'not-a-list'}, 1),
    ({'options': [A], 'docs': [{'title': 'x', 'link': 'javascript:alert(1)'}]}, 1),
])
def test_일반_승인_제안은_선택_칸이_없어도_약속과_다르다고_하지_않는다(proposal, problems):
    got = run(FILES, "const m = hydApprove.proposal({ proposal: DATA.p }, DATA.cfg); out([m.usable, m.problems.length])", {'p': proposal, 'cfg': CFG})
    assert got == [True, problems]


def test_진_안의_이유는_승인_카드와_처리_기록이_같은_함수로_말한다():
    """W1-11 · W1-14: 진 이유 계산이 두 벌이라 승인 카드는 「납기에서 뒤짐」, 처리 기록은 「… +0.26는 앞섬」(조사 고정)으로 달랐다."""
    o = {'id': 'b', 'scoreParts': {'delivery': -0.67, 'forecast': 0.26}}
    rec = {'id': 'a', 'scoreParts': {'delivery': 0, 'forecast': 0}}
    got = run(FILES, "out([hydApprove.partDiff(DATA.o, DATA.rec, []), hydApprove.partDiff(DATA.o, DATA.rec, [], { numbers: true })])", {'o': o, 'rec': rec})
    assert got == ['납기에서 뒤짐 · 예측에서 앞섬', '납기 -0.67에서 뒤짐 · 예측 +0.26에서 앞섬']
