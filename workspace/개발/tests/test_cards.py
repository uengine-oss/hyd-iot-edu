"""조치 카드 판단의 순수 계산(it/agent/agentsvc/cards.py) — 정비 시점 · 생산 영향 · 읽을 판단 변수 · 설명 문장.

카드 모양은 지식 그래프 t3_skills 행 그대로(수업 지식 HM-8 의 SOP-COOL-11~14, PM-02 의 SOP-PM-12)."""
import pytest

from agentsvc import cards

CMD = 'command'
COOL = {
    'skill:sop-cool-11': {'skillId': 'skill:sop-cool-11', 'sopId': 'SOP-COOL-11', 'name': '팬 최대 운전', 'kind': 'control', 'relation': 'MITIGATED_BY',
                          'actions': [{'code': 'FAN_SET', 'kind': CMD, 'value': 100}]},
    'skill:sop-cool-13': {'skillId': 'skill:sop-cool-13', 'sopId': 'SOP-COOL-13', 'name': '부하 70 %와 야간 핀 세척', 'kind': 'control',
                          'relation': 'MITIGATED_BY', 'actions': [{'code': 'LOAD_SET', 'kind': CMD, 'value': 70},
                                                                   {'code': 'WO_CREATE', 'kind': 'transaction', 'value': 'SOP-COOL-14'}]},
    'skill:sop-cool-14': {'skillId': 'skill:sop-cool-14', 'sopId': 'SOP-COOL-14', 'name': '쿨러 핀 세척', 'kind': 'work_order', 'relation': 'REMEDIED_BY',
                          'addresses': ['cause:cooler-fin-fouling'], 'actions': [{'code': 'WO_CREATE', 'kind': 'transaction', 'value': 'SOP-COOL-14'}]},
    'skill:pm-stop': {'skillId': 'skill:pm-stop', 'sopId': 'SOP-PM-X', 'name': '정지 명령 뒤 정비', 'kind': 'work_order',
                      'actions': [{'code': 'STOP', 'kind': CMD}, {'code': 'WO_CREATE', 'kind': 'transaction', 'value': 'SOP-PM-X'}]},
}
NIGHT = {'id': 'MW-HYD-01-N-202610301510', 'starts_at': '2026-10-30T15:10:00+00:00', 'name': '이번 예정된 정비 시간'}
WINDOWS = {'hours_at_next_window': NIGHT}


@pytest.mark.parametrize('sid, windows, expect', [
    ('skill:sop-cool-11', WINDOWS, None),
    ('skill:sop-cool-13', WINDOWS, dict(NIGHT, basis='hours_at_next_window')),
    ('skill:sop-cool-13', {}, None),
    ('skill:sop-cool-14', WINDOWS, cards.IMMEDIATE),
    ('skill:sop-cool-14', None, cards.IMMEDIATE),
    ('skill:pm-stop', WINDOWS, {'immediate': True, 'label': '즉시', 'name': '명시 정지 명령 뒤 즉시 정비'}),
], ids=['명령만(팬) — 정비 없음', '완화 + 작업지시 → 다음 예정된 정비 시간', '완화 + 작업지시인데 창을 모름 → 지어내지 않음',
        '작업지시만 → 지금 정지하고 시행', '창이 없어도 작업지시만이면 즉시', '정지 명령 + 작업지시 → 즉시'])
def test_카드의_정비_시점은_조치의_모양과_예정된_정비_시간에서_한_곳이_정한다(sid, windows, expect):
    assert cards.option_window([], sid, COOL[sid], windows) == expect


def test_카드에만_걸린_규정이_시험하는_창_변수가_있으면_그_창이_먼저다():
    rules = [{'rule': 'r', 'applies': ['skill:sop-cool-14'], 'tests': [{'variable': 'hours_at_following_window'}]}]
    later = {'id': 'MW-M', 'starts_at': '2026-11-09T04:00:00+00:00', 'name': '그다음 예정된 정비 시간'}
    assert cards.option_window(rules, 'skill:sop-cool-14', COOL['skill:sop-cool-14'], {'hours_at_following_window': later})['id'] == 'MW-M'


@pytest.mark.parametrize('option, expect', [
    (dict(COOL['skill:sop-cool-14'], window=cards.IMMEDIATE), 'stop'),
    (dict(COOL['skill:sop-cool-13'], window=dict(NIGHT)), 'reduce'),
    (dict(COOL['skill:sop-cool-11']), 'keep'),
    ({'actions': [{'code': 'PR_CREATE', 'kind': 'transaction'}], 'losses': [{'measure': 'msr:availability'}]}, 'stop'),
], ids=['지금 정지하고 세척 → 정지(납기 가점 없음)', '부하 70 + 야간 세척 → 감산', '팬만 → 유지', '명령 · 작업지시 없는 카드 → 성과 지표 손실'])
def test_생산_영향은_지금_설비를_세우는지에서_읽는다(option, expect):
    """G1-05: 「지금 정지하고 세척」 카드가 명령이 없다고 생산 유지로 계산돼 납기 가점을 받았다."""
    assert cards.production_effect(option) == expect


DMN = [
    {'decision': 'dec:action-candidates', 'rule': 'rule:cool', 'effect': 'SELECT', 'tests': [{'variable': 'pattern', 'operator': '==', 'value': 'COOLER_DEGRADATION'}],
     'outputs': ['skill:sop-cool-11', 'skill:sop-cool-13']},
    {'decision': 'dec:action-candidates', 'rule': 'rule:fin', 'effect': 'SELECT', 'tests': [{'variable': 'cause', 'operator': '==', 'value': 'cause:cooler-fin-fouling'}],
     'outputs': ['skill:sop-cool-14']},
    {'decision': 'dec:action-candidates', 'rule': 'rule:spare', 'effect': 'SELECT',
     'tests': [{'variable': 'pattern', 'operator': '==', 'value': 'SPARE_BELOW_MIN'}, {'variable': 'spare_gap', 'operator': '<', 'value': 0}], 'outputs': []},
    {'decision': 'dec:compliance', 'rule': 'rule:auto', 'effect': 'EXCLUDE', 'applies': ['skill:sop-cool-11'],
     'tests': [{'variable': 'plc_mode', 'operator': '!=', 'value': 'REMOTE_AUTO'}]},
    {'decision': 'dec:compliance', 'rule': 'rule:pm', 'effect': 'EXCLUDE', 'applies': ['skill:sop-pm-11'],
     'tests': [{'variable': 'hours_at_following_window', 'operator': '>', 'value': 2200}]},
    {'decision': 'dec:rank-actions', 'rule': 'rule:rank', 'effect': 'RANK', 'tests': [],
     'rankingPolicy': {'version': 1, 'inputs': {'due': 'order_due_h'}, 'components': {'x': '0'}, 'tieBreak': 'lower_approver'}},
]


def test_판단이_읽을_변수는_맞을_수_있는_규칙과_그_후보의_규정과_순위_입력과_정비_시점뿐이다():
    """G1-24 · H-8: 냉각 판단이 모든 판단 입력을 읽어 펌프 씰 재고 · 견적을 근거에 싣고, 쓰지 않는 원천이 끊겨도 멈췄다."""
    need = cards.needed_variables(DMN, COOL, {'pattern': 'COOLER_DEGRADATION', 'cause': 'cause:cooler-fin-fouling'})
    assert need == {'pattern', 'cause', 'plc_mode', 'order_due_h', 'hours_at_next_window'}
    assert 'spare_gap' not in need and 'hours_at_following_window' not in need


def test_원인이_다르면_그_원인의_후보와_규정만_읽는다():
    need = cards.needed_variables(DMN, COOL, {'pattern': 'COOLER_DEGRADATION', 'cause': 'cause:fan-drive-fault'})
    assert 'hours_at_next_window' in need           # SOP-COOL-13 의 작업지시가 남는다
    assert cards.candidate_skills(DMN, COOL, {'pattern': 'COOLER_DEGRADATION', 'cause': 'cause:fan-drive-fault'}).keys() == {'skill:sop-cool-11', 'skill:sop-cool-13'}


@pytest.mark.parametrize('rules, needle', [
    ([], '0개입니다'),
    ([DMN[-1], dict(DMN[-1], rule='rule:rank2')], '2개입니다'),
    ([dict(DMN[-1], effect='SELECT')], '순위(RANK)가 아닌 규칙'),
], ids=['순위 규칙 없음', '순위 규칙 둘', 'RANK 가 아닌 규칙'])
def test_순위_규칙_오류는_학생이_읽는_말로_까닭을_말한다(rules, needle):
    with pytest.raises(ValueError) as e:
        cards.rank_policy(rules, {})
    assert needle in str(e.value)


def test_설명_문장은_이어_붙인_사유의_마침표를_겹치지_않고_예측_유온은_소수_한_자리다():
    """G1-18: 「… 미루지 않는다.; '같은 기종 …' — … 있어야 한다.. 납기」 · 「예측 유온 48.001 ℃」."""
    rec = {'id': 'a', 'sopId': 'SOP-PM-11', 'name': '이번 예정된 정비 시간에 단독 시행', 'score': 1.54, 'feasible': True, 'gains': [], 'losses': [],
           'forecast': [{'variable': 'sv:ts1', 'value': 48.001, 'unit': '℃'}], 'precedent': None, 'scoreParts': {}, 'production': 'keep'}
    out = [dict(rec, id='b', name='미루기', feasible=False, violations=[{'annotation': '2,200 h를 넘으면 미루지 않는다.'}]),
           dict(rec, id='c', name='묶어 시행', feasible=False, violations=[{'annotation': '씰 키트가 2개 이상 있어야 한다.'}])]
    text = cards.explain([rec, *out], rec, {'failure_mode_name': '주 펌프 체적 효율 저하'})
    assert '.;' not in text and '..' not in text and '예측 유온 48.0 ℃.' in text and '(점수 1.54)' in text


def test_구매_카드_설명은_점수가_아니라_비교_총비용으로_말한다():
    rec = {'id': 'p', 'sopId': 'SOP-PUR-11', 'name': '승인 공급사 최저가', 'score': -420.0, 'feasible': True, 'gains': [], 'losses': [], 'forecast': [],
           'precedent': None, 'scoreParts': {}, 'economicComparison': {'purchase_amount': 330, 'expected_failure_cost': 40, 'inspection_cost': 50,
                                                                       'total_cost': 420, 'supplier': 'sup:b', 'quantity': 6}}
    text = cards.explain([rec], rec, {'purchase_part': 'part:seal', 'purchase_part_name': '펌프 축 씰 키트'})
    assert '(비교 총비용 420만 원)' in text and '점수 -420' not in text
