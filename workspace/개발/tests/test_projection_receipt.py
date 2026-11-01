"""그래프 반영 영수증(procsvc/projection_receipt.py) — 그래프 쓰기는 그 반영의 정확한 영수증(열쇠 · 판번호 · 내용 해시)이 한 줄로 돌아올 때만 끝난 것이다."""
import pytest

from procsvc.projection_receipt import ProjectionConflict, digest, require

KEY, REVISION, HASH = 'Incident:INC-1', 7, 'a' * 64
RECEIPT = {'projection_key': KEY, 'projection_revision': REVISION, 'projection_hash': HASH}


def test_내용_해시는_사전의_칸_차례와_상관없이_같고_값이_다르면_다르다():
    from datetime import datetime, timezone
    at = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)
    assert digest({'a': 1, 'b': [1, 2]}) == digest({'b': [1, 2], 'a': 1})
    assert digest({'a': 1}) != digest({'a': 2})
    assert digest({'시각': at}) == digest({'시각': at.isoformat(sep=' ')})       # JSON 으로 못 쓰는 값(시각)은 글로 바꿔 잰다


def test_정확한_영수증_한_줄이면_반영이_끝난_것이다():
    assert require([dict(RECEIPT, warnings=[])], KEY, REVISION, HASH) is None


@pytest.mark.parametrize('rows, why', [
    ([], '그래프가 아무것도 돌려주지 않음(울타리가 막은 늦은 쓰기)'),
    ([RECEIPT, RECEIPT], '영수증이 두 줄'),
    ([dict(RECEIPT, projection_key='Incident:INC-2')], '다른 반영의 열쇠'),
    ([dict(RECEIPT, projection_revision=REVISION - 1)], '앞 판번호'),
    ([dict(RECEIPT, projection_hash='b' * 64)], '다른 내용'),
    (None, '목록이 아님'),
    (['영수증'], '행이 사전이 아님'),
])
def test_영수증이_다르면_다시_세지_않고_사람이_비교할_충돌로_멈춘다(rows, why):
    with pytest.raises(ProjectionConflict) as caught:
        require(rows, KEY, REVISION, HASH)
    assert KEY in str(caught.value) and str(REVISION) in str(caught.value), why
