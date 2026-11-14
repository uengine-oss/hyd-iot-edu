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


def test_판단_엔진이_고른_1순위는_AI_추천이_아니라_판단_엔진_1순위와_규칙_문장으로_말한다():
    """J4 D1(2026-11-01): 순위는 판단 엔진(DMN 결정표 + 순위 식)이 결정론으로 계산하는데 화면이 「AI 에이전트 추천」 · 「에이전트 설명 전문」이라
    불렀다. 선례는 미리 넣은 예시 고정이라 실제 승인 이력처럼 읽히지 않게 표시한다(독립 검증 2026-11-02)."""
    opt = {'id': 'skill:sop-cool-11', 'name': '팬 최대 운전', 'feasible': True, 'rank': 1, 'actions': [],
           'precedent': {'n': 2, 'share': 0.5, 'reasons': []}}
    d = {'id': 'D-1', 'recommended': 'skill:sop-cool-11', 'options': [opt], 'evaluation_mode': 'execution', 'execution_checked': True,
         'explanation': '1순위 팬 최대 운전.'}
    got = run(FILES, r"out(hydApprove.html(DATA, null).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' '))", d)
    assert '판단 엔진 1순위' in got and '판단 엔진 설명 전문 (규칙 문장)' in got, got
    assert 'AI 에이전트 추천' not in got and '에이전트 설명 전문' not in got.replace('판단 엔진 설명 전문', ''), got
    assert '과거 같은 선택 2건(미리 넣은 사례 기준)' in got, got


STALE = {'rule': 'forecast:model-unavailable', 'effect': 'EXCLUDE',
         'annotation': '현재 조치 예측을 확인할 수 없습니다: 설비 상태가 15초 전 값이라 지금 예측에 쓸 수 없습니다(15초 이내만) — 설비 시뮬레이터와 수집이 도는지 확인하고 다시 판단하세요'}
FOLLOW = {'rule': 'rule:ts1-hard', 'effect': 'EXCLUDE', 'annotation': '확인되지 않은 조건 (forecast_ts1): 예측 유온이 인터록 한계 이상이면 제외', 'unknown': ['forecast_ts1']}


def test_모든_안이_같은_까닭으로_제외되면_그_까닭을_한_번만_화면_말로_낸다():
    """독립 검토 가-3: 네 안이 같은 사유로 제외됐는데 같은 긴 문장이 네 번 되풀이되고 내부 이름(forecast_ts1)과 학생이 할 수 없는 지시가 나왔다."""
    d = {'recommended': None, 'options': [{'id': f's{i}', 'name': n, 'feasible': False, 'violations': [STALE, FOLLOW]} for i, n in enumerate(['팬 최대 운전', '쿨러 핀 세척'])]}
    got = run(FILES, "const s = hydApprove.noneSummary(DATA); out([s.same, s.reasons, hydApprove.html(DATA, null, { pending: true })])", d)
    assert got[0] is True
    assert got[1] == ['현재 조치 예측을 확인할 수 없습니다: 설비 상태가 15초 전 값이라 지금 예측에 쓸 수 없습니다(15초 이내만)']      # 운영자에게 하는 말 · 다른 값을 몰라 따라 걸린 규칙은 뺀다
    visible = got[2].split('<details')[0]      # 접기 밖(첫 화면)
    assert '팬 최대 운전' in visible and '쿨러 핀 세척' in visible
    assert 'forecast_ts1' not in visible and '시뮬레이터' not in visible and visible.count('설비 상태가 15초 전 값') == 0      # 까닭은 판의 머리가 한 번 말한다 — 안마다 되풀이하지 않는다
    assert got[2].count('forecast_ts1') == 2      # 원문은 접기 안에 그대로(안마다 한 번)


def test_안마다_제외된_까닭이_다르면_한_문장으로_뭉뚱그리지_않는다():
    other = {'rule': 'rule:role', 'effect': 'EXCLUDE', 'annotation': '정비 인력이 없습니다'}
    d = {'recommended': None, 'options': [{'id': 'a', 'name': '팬 최대 운전', 'feasible': False, 'violations': [STALE]}, {'id': 'b', 'name': '쿨러 핀 세척', 'feasible': False, 'violations': [other]}]}
    got = run(FILES, "const s = hydApprove.noneSummary(DATA); out([s.same, s.reasons, s.per.map(r => r.reasons)])", d)
    assert got[0] is False and got[1] == [] and got[2][1] == ['정비 인력이 없습니다']
