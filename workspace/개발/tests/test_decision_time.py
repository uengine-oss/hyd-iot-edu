"""판단 설명의 시각 표기(common/hydcommon/decision_time.py) — 설명 글에 쓴 숫자 시각은 날짜와 시간대가 붙은 꼴이어야 한다.

AI 가 「12:30에 정비」처럼 날짜 · 시간대 없는 시각을 쓰면 사람이 다른 날 · 다른 시간대로 읽는다. 판단 폼(decision · decision_id 칸)의 결과를
받을 때 process_contracts.validate_output 이 이 검사를 부른다 — 그 길도 함께 본다.
"""
import json

import pytest

from conftest import DEFINITIONS
from hydcommon import process_contracts
from hydcommon.decision_time import validate_explanation


def _out(text):
    return {'decision': {'explanation': text}}


@pytest.mark.parametrize('text', [
    '2026-10-30 12:30 KST 정비 시간에 맞춰 팬을 올린다',
    '2026-10-30T03:30:00+00:00 창이 열린다',
    '2026-10-30T03:30Z 부터',
    '2026-10-30 12:30:15.5 (KST) 기록',
    '2026-10-30 03:30 UTC 와 2026-10-30 12:30 KST 는 같은 때다',
    '이번 예정된 정비 시간에 맞춘다',            # 시각을 쓰지 않으면 검사할 것이 없다
    '부품 123:45 번 묶음',                       # 세 자리 앞은 시각이 아니다
], ids=['KST', 'ISO 시간대', 'Z', '초 소수와 괄호 시간대', '두 시각 모두 표기', '시각 없음', '시각 아닌 숫자'])
def test_날짜와_시간대가_붙은_시각은_받는다(text):
    assert validate_explanation(_out(text)) is None


@pytest.mark.parametrize('text', [
    '12:30에 정비한다',
    '2026-10-30 12:30 에 정비',                  # 날짜는 있으나 시간대가 없다
    '오늘 12:30 KST',                            # 시간대는 있으나 날짜가 없다
    '2026-13-40 12:30 KST',                      # 있을 수 없는 날짜는 표기가 아니다
    '2026-10-30 12:30 KST 뒤 14:00 재관측',      # 하나라도 맨 시각이면 거절
    '2026-10-30 12:30 PST',                      # 정한 시간대(Z · ±hh:mm · UTC · KST) 밖
], ids=['맨 시각', '시간대 없음', '날짜 없음', '없는 날짜', '하나만 표기', '모르는 시간대'])
def test_날짜나_시간대가_빠진_숫자_시각은_고칠_방법과_함께_거절한다(text):
    with pytest.raises(ValueError) as caught:
        validate_explanation(_out(text))
    assert '날짜·시간대가 필요합니다' in str(caught.value) and 'window.starts_at' in str(caught.value)


@pytest.mark.parametrize('output', [{}, {'decision': None}, {'decision': '12:30'}, {'decision': {'explanation': None}},
                                    {'decision': {'explanation': ['12:30']}}],
                         ids=['판단 없음', '판단 null', '판단이 글', '설명 null', '설명이 목록'])
def test_설명_글이_없는_결과는_이_검사의_대상이_아니다(output):
    """설명이 글이 아니면 형식은 폼 검사(validate_output)가 판정한다 — 여기서는 시각 표기만 본다."""
    assert validate_explanation(output) is None


def _rank_form():
    definition = json.loads((DEFINITIONS / 'anomaly_response_v22.json').read_text(encoding='utf-8'))
    return process_contracts.pinned_form(definition, 'formHandler:rank')


def test_실제_판단_폼의_결과를_받을_때_맨_시각이면_거절한다():
    """anomaly_response 정의의 rank 폼(decision · decision_id 칸) 그대로 — 엔진 · 워커가 결과를 받을 때 지나는 길."""
    form = _rank_form()
    process_contracts.validate_output(form, {'decision': {'explanation': '2026-10-30 12:30 KST 에 맞춘다'}, 'decision_id': 'd-1'})
    with pytest.raises(ValueError, match='날짜·시간대'):
        process_contracts.validate_output(form, {'decision': {'explanation': '12:30에 맞춘다'}, 'decision_id': 'd-1'})
