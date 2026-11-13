"""순위 식 실행기(common/hydcommon/ranking.py) — 검토된 순위 정책의 식만 계산한다. 파이썬 eval · 글 실행은 없다.

- 식: 허용한 산술 · 비교 · 논리 · 조건식과 다섯 함수(min · max · abs · round · clamp)만. 속성 · 첨자 · 목록 · 가져오기 · 거듭제곱은 거절,
  참/거짓 자리에 숫자(truthiness) · 모르는 값(None)의 산술 · 비교 · 0 나누기 · 무한 값도 거절한다.
- validate: 정책 모양(version 1 · inputs · components · tieBreak)과 이름 규칙, 식을 미리 컴파일해 본다.
- score: 정책 식마다 계산해 둘째 자리로 반올림한 몫과 그 합.
실제 정책은 시드 그래프의 `rule:rank-value`(it/neo4j/v2/instances.cypher 가 넣는 값)를 그래프에서 읽어 본다.
"""
import json
import math

import pytest

from hydcommon import ranking


@pytest.mark.parametrize('text, context, expected', [
    ('1 + 2 * 3 - 4 / 2', {}, 5.0),
    ('1 < x < 3', {'x': 2}, True),
    ('1 < x < 3', {'x': 3}, False),                 # 연쇄 비교는 둘 다 참이어야 한다
    ('x is None', {'x': None}, True),
    ('0 if x is None else x * 2', {'x': None}, 0),
    ('0 if x is None else x * 2', {'x': 4}, 8.0),
    ("s == 'keep'", {'s': 'keep'}, True),
    ("s != 'keep' and not f", {'s': 'stop', 'f': False}, True),
    ('min(x, 2, 7)', {'x': 5}, 2.0),
    ('max(x, 2)', {'x': -5}, 2.0),
    ('abs(-x)', {'x': 3}, 3.0),
    ('round(x, 1)', {'x': 1.26}, 1.3),
    ('clamp(x, 0, 1)', {'x': 5}, 1.0),
    ('clamp(x, 0, 1)', {'x': -5}, 0.0),
    ('-x', {'x': 2}, -2.0),
], ids=['산술 우선순위', '연쇄 비교 참', '연쇄 비교 거짓', 'None 확인', '조건식 None 갈래', '조건식 값 갈래', '글 비교', '논리 결합',
        'min', 'max', 'abs', 'round', 'clamp 위', 'clamp 아래', '부호'])
def test_허용한_식은_값을_계산한다(text, context, expected):
    assert ranking.evaluate_expression(text, context) == expected


@pytest.mark.parametrize('text', [
    "__import__('os')", 'x.real', '[1, 2]', 'x[0]', 'lambda: 1', 'x ** 2', 'x // 2', 'x % 2', "f'{x}'", '{1: 2}', "b'x'", '1j',
    'min(1)', 'min(1, 2, 3, 4, 5, 6, 7, 8, 9)', 'abs(1, 2)', 'round(x, ndigits=2)', 'min', 'y', '(1 + 2', '1e999', '', 'x' * 2049,
    "'" + 'a' * 129 + "'", ' + '.join(['x'] * 130), '(' * 40 + 'x' + ')' * 40 + ' + ' + '-' * 40 + 'x',
], ids=['가져오기', '속성', '목록', '첨자', 'lambda', '거듭제곱', '몫', '나머지', 'f-글', '사전', '바이트', '복소수',
        'min 인자 1', 'min 인자 9', 'abs 인자 2', '이름 붙은 인자', '부르지 않은 함수', '모르는 이름', '문법 오류', '무한 상수', '빈 식',
        '2049자', '긴 글 상수', '너무 복잡', '너무 깊음'])
def test_허용하지_않은_식은_컴파일에서_거절한다(text):
    with pytest.raises(ValueError):
        ranking.compile_expression(text, {'x'})


@pytest.mark.parametrize('text, context, word', [
    ('1 if x else 2', {'x': 5}, 'boolean'),            # 참/거짓 자리에 숫자
    ('x and f', {'x': 1, 'f': True}, 'boolean'),
    ('not x', {'x': 0}, 'boolean'),
    ('x + 1', {'x': None}, 'known numeric'),           # 모르는 값으로 계산하지 않는다
    ('x > 1', {'x': None}, 'unknown'),
    ('x + 1', {'x': True}, 'known numeric'),           # 참/거짓은 숫자가 아니다
    ('f == 1', {'f': True}, 'boolean types'),
    ('f < g', {'f': True, 'g': False}, 'boolean types'),
    ('x is 1', {'x': 1}, 'only supports None'),
    ('x / 0', {'x': 1}, 'arithmetic'),
    ('x * 10', {'x': 1e308}, 'finite'),
    ('x + 1', {'x': math.nan}, 'finite'),
    ("x < 'a'", {'x': 1}, 'numeric'),
    ('round(x, 11)', {'x': 1}, 'precision'),
    ('round(x, 0.5)', {'x': 1}, 'precision'),
    ('clamp(x, 2, 0)', {'x': 1}, 'clamp bounds'),
], ids=['조건식 숫자', '논리에 숫자', 'not 숫자', 'None 산술', 'None 비교', '참거짓 산술', '참거짓과 숫자 비교', '참거짓 크기 비교',
        'is 숫자', '0 나누기', '넘침', 'NaN 입력', '숫자와 글 비교', 'round 자리 11', 'round 자리 소수', 'clamp 거꾸로'])
def test_계산할_수_없는_값은_거절한다(text, context, word):
    with pytest.raises(ValueError) as caught:
        ranking.evaluate_expression(text, context)
    assert word in str(caught.value)


def test_calculate_는_숫자_결과만_돌려준다():
    assert ranking.calculate('x * 2', {'x': 1.5}) == 3.0
    with pytest.raises(ValueError):
        ranking.calculate('x > 1', {'x': 2})              # 참/거짓 결과는 점수가 아니다


POLICY = {'version': 1, 'inputs': {'due': 'order_due_h'}, 'components': {'bsc': 'bsc_gain * 0.333',
                                                                          'delivery': '0 if due is None else clamp((24 - due) / 24, 0, 1)'},
          'tieBreak': 'lower_approver'}


def test_올바른_정책은_정규화한_사본으로_받는다():
    for given in (POLICY, json.dumps(POLICY, ensure_ascii=False)):
        out = ranking.validate(given)
        assert out == POLICY and out is not POLICY


def _with(**change):
    p = json.loads(json.dumps(POLICY))
    for key, value in change.items():
        if value is KeyError:
            p.pop(key)
        else:
            p[key] = value
    return p


@pytest.mark.parametrize('policy, word', [
    ([], 'requires version'),
    (_with(version=KeyError), 'requires version'),
    (dict(POLICY, extra=1), 'requires version'),
    (_with(version=2), 'version or tieBreak'),
    (_with(version='1'), 'version or tieBreak'),
    (_with(version=True), 'version or tieBreak'),
    (_with(tieBreak='higher_score'), 'version or tieBreak'),
    (_with(inputs=[]), 'up to32 inputs'),
    (_with(inputs={f'i{n}': 'v' for n in range(33)}), 'up to32 inputs'),
    (_with(components={}), '1..16 components'),
    (_with(components={f'c{n}': '1' for n in range(17)}), '1..16 components'),
    (_with(inputs={'Due': 'order_due_h'}), 'name'),
    (_with(inputs={'1due': 'order_due_h'}), 'name'),
    (_with(components={'b' * 65: '1'}), 'name'),
    (_with(inputs={'production': 'order_due_h'}), 'shadow'),
    (_with(inputs={'min': 'order_due_h'}), 'shadow'),
    (_with(inputs={'due': ''}), 'explicit fact variables'),
    (_with(inputs={'due': 'v' * 161}), 'explicit fact variables'),
    (_with(inputs={'due': 3}), 'explicit fact variables'),
    (_with(components={'bsc': 'unknown_alias + 1'}), 'unknown ranking input'),
    (_with(components={'bsc': 'bsc_gain.real'}), 'unsupported'),
    ('{not json', 'invalid ranking policy JSON'),
    (json.dumps(POLICY) + ' ' * 32000, 'too large'),
], ids=['목록', 'version 없음', '모르는 칸', 'version 2', 'version 글', 'version 참거짓', 'tieBreak 다름', 'inputs 목록', 'inputs 33',
        'components 0', 'components 17', '대문자 이름', '숫자로 시작', '65자 이름', '내장 지표 가림', '함수 가림', '빈 변수', '161자 변수',
        '변수가 숫자', '모르는 별칭', '속성 식', 'JSON 깨짐', '32000자 넘음'])
def test_정책_모양이나_식이_어긋나면_거절한다(policy, word):
    with pytest.raises(ValueError) as caught:
        ranking.validate(policy)
    assert word in str(caught.value)


def test_점수는_식마다_둘째_자리로_반올림한_몫의_합이다():
    out = ranking.score(POLICY, {'bsc_gain': 1}, {'order_due_h': 6})
    assert out == {'score': 1.08, 'scoreParts': {'bsc': 0.33, 'delivery': 0.75}}


def test_정책이_None_을_다루지_않은_사실이_없으면_점수를_내지_않는다():
    """사실이 없으면 0 으로 치지 않는다 — 정책 식이 `is None` 으로 직접 다룬 것만 계산된다."""
    assert ranking.score(POLICY, {'bsc_gain': 0}, {})['scoreParts']['delivery'] == 0
    no_guard = _with(components={'delivery': 'clamp((24 - due) / 24, 0, 1)'})
    with pytest.raises(ValueError, match='known numeric'):
        ranking.score(no_guard, {}, {})


def test_같은_정책은_같은_지문이고_다르면_다른_지문이다():
    assert ranking.fingerprint(POLICY) == ranking.fingerprint(json.loads(json.dumps(POLICY)))
    assert ranking.fingerprint(POLICY) != ranking.fingerprint(_with(version=2))
    with pytest.raises(ValueError):
        ranking.canonical({'x': math.nan})              # NaN 은 정규 글이 없다


def _graph_policy(graph):
    rows = graph.query("MATCH (r:Rule {id: 'rule:rank-value'}) RETURN r.rankingPolicy AS policy")
    assert len(rows) == 1 and rows[0]['policy'], rows
    return rows[0]['policy']


def test_시드_그래프의_순위_정책은_검사를_통과하고_읽는_사실은_모두_판단_입력이다(seeded_graph):
    policy = ranking.validate(_graph_policy(seeded_graph))
    variables = {r['v'] for r in seeded_graph.query('MATCH (i:InputData) RETURN i.variable AS v')}
    assert set(policy['inputs'].values()) <= variables, set(policy['inputs'].values()) - variables


FEATURES = {'bsc_gain': 1.0, 'bsc_loss': 0.3, 'bsc_conditional_gain': 0.6, 'bsc_conditional_loss': 0.0, 'forecast_ts1': 49.0,
            'warning_count': 1, 'penalty_total': 10, 'precedent_share': 0.5, 'production': 'keep'}


@pytest.mark.parametrize('features, facts, parts', [
    # 규칙 설명(rule:rank-value annotation)대로 손으로 계산한 값:
    #   bsc = 1 + 0.5×0.6 − 0.3 − 0 = 1.0 · forecast = (55−49)/3 = 2(±2 한도) · warn = −0.5 · penalty = −10/20 · precedent = 0.5×1.5
    #   delivery = round((24−12)/24 × 50/100, 2) × 1(유지) × 1.5 = 0.375 → 0.38 · quality = 0(예측 유온 < 55)
    (FEATURES, {'order_due_h': 12, 'order_penalty_per_h': 50, 'hot_lot_claim': 500, 'hot_lot_qty': 10},
     {'bsc': 1.0, 'forecast': 2.0, 'warn': -0.5, 'penalty': -0.5, 'precedent': 0.75, 'delivery': 0.38, 'quality': 0}),
    # 정지(−1) · 예측 유온 58 ≥ 55 이고 출하 대기 로트가 있으면 품질 위험 −1.5 × min(1, 500/1000) = −0.75, forecast = (55−58)/3 = −1
    (dict(FEATURES, production='stop', forecast_ts1=58.0), {'order_due_h': 12, 'order_penalty_per_h': 50, 'hot_lot_claim': 500, 'hot_lot_qty': 10},
     {'bsc': 1.0, 'forecast': -1.0, 'warn': -0.5, 'penalty': -0.5, 'precedent': 0.75, 'delivery': -0.38, 'quality': -0.75}),
    # 예측이 없고 납기 사실이 없으면 그 몫은 0 이다(정책이 None 을 직접 다룬다)
    (dict(FEATURES, forecast_ts1=None), {},
     {'bsc': 1.0, 'forecast': 0, 'warn': -0.5, 'penalty': -0.5, 'precedent': 0.75, 'delivery': 0, 'quality': 0}),
], ids=['유지 · 여유 있음', '정지 · 고온 로트', '예측 · 납기 없음'])
def test_시드_그래프의_순위_정책은_규칙_설명대로_점수를_낸다(seeded_graph, features, facts, parts):
    out = ranking.score(_graph_policy(seeded_graph), features, facts)
    assert out['scoreParts'] == pytest.approx(parts)
    assert out['score'] == pytest.approx(round(sum(parts.values()), 2))
