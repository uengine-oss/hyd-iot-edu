"""사람 입력 경보(procsvc/human_alert.py) — 오일 분석 결과 입력을 센서 경보와 같은 계약으로, 같은 이상이 처리 중이면 다시 열지 않는다."""
import pytest

from conftest import OPERATOR
from procsvc import human_alert as ha
from procsvc.inbox import NOT_A_PERSON

ME = OPERATOR['by']
ENTERED = {'id': ME, 'name': '담당자'}          # 확인된 입력자(ha.entered_by 가 사용자 표에서 읽은 모양)
BODY = {'pattern': 'OIL_ANALYSIS', 'asset': 'HYD-01', 'item': 'water', 'out_of_spec': True, 'value': 650, 'by': ME, 'memo': '정기 분석'}


@pytest.mark.parametrize('body, error', [
    (dict(BODY, pattern='PRESSURE'), '받지 않는 종류'),
    (dict(BODY, asset='HYD-09'), '없는 설비입니다: HYD-09'),
    (dict(BODY, item='colour'), '목록에 없습니다'),
    (dict(BODY, out_of_spec='예'), '예/아니요로 고르세요'),
    (dict(BODY, value=float('inf')), '측정값은 숫자여야'),
    (dict(BODY, value=True), '측정값은 숫자여야'),
    (dict(BODY, memo='가' * 2001), '2000자 이내'),
    ('문장', '입력은 객체여야'),
], ids=['모르는 종류', '없는 설비', '모르는 항목', '예아니요 아님', '무한대', '참거짓 값', '메모 2001자', '객체 아님'])
def test_오일_분석_입력은_칸마다_검사하고_칸_이름과_함께_거절한다(body, error):
    with pytest.raises(ValueError, match=error):
        ha.build_alert(body, ENTERED)


def test_기준_이탈이면_센서_경보와_같은_모양의_경보를_만든다():
    alert, reason = ha.build_alert(BODY, ENTERED)
    assert {k: alert[k] for k in ('asset', 'pattern', 'state', 'source')} == {'asset': 'HYD-01', 'pattern': 'OIL_ANALYSIS', 'state': 'RAISE',
                                                                               'source': 'human_input'}
    assert alert['evidence'] == {'item': 'water', 'item_name': '수분 함량', 'unit': 'ppm', 'out_of_spec': True,
                                 'oil_analysis_out_of_spec': True, 'value': 650, 'memo': '정기 분석'}
    assert alert['enteredBy'] == ENTERED and ha.is_human_alert(alert)
    assert '같은 경로로 경보를 보냈습니다' in reason


def test_기준_안이면_경보를_만들지_않고_학생이_읽는_까닭을_준다():
    """W2-20: 전에는 「패턴 검사(오일 분석 결과 기준 이탈 == 예)를 충족하지 않습니다」 같은 지식 내부 말이 화면에 그대로 나왔다."""
    alert, reason = ha.build_alert(dict(BODY, out_of_spec=False), ENTERED)
    assert alert is None
    assert reason == '수분 함량이 기준 안이라 경보를 만들지 않았습니다 — 기준 이탈을 「예」로 고른 입력만 경보가 됩니다. 처리 건은 열리지 않습니다'


def test_사람_입력_패턴의_지식_id는_실제_시드_그래프에_있다(seeded_graph):
    """G3a-13: 전에는 머리말이 없는 시험(tests/test_b7_oil.py)으로 대조한다고 적었다 — 이제 이 테스트가 실제 시드 그래프와 대조한다."""
    k = ha.PATTERNS['OIL_ANALYSIS']['knowledge']
    rows = seeded_graph.query('MATCH (p:AnomalyPattern {id: $p})-[:TESTS]->(i:InputData {id: $i}) OPTIONAL MATCH (s {id: $s}) '
                              'RETURN p.code AS code, i.variable AS variable, s.id AS symptom', p=k['pattern'], i=k['input'], s=k['symptom'])
    assert rows == [{'code': 'OIL_ANALYSIS', 'variable': k['variable'], 'symptom': k['symptom']}], rows


def test_같은_설비의_같은_오일_이상이_처리_중이면_두_번째_입력은_처리_건을_새로_열지_않는다(world):
    """P4-28: 전에는 두 사람이 같은 이상을 입력하면 처리 건 · 사건이 둘 생겼다(수업 버튼의 「진행 중이면 거절」과 같은 규칙으로)."""
    first, body = world.api('POST', '/api/human-alerts', BODY, source_loop=True)
    assert first == 200 and body['raised'] is True and body['instance'], body
    second, refused = world.api('POST', '/api/human-alerts', dict(BODY, item='tan', value=2.1), source_loop=True)
    assert second == 409 and '아직 진행 중입니다' in refused['detail'], refused
    other_asset, body2 = world.api('POST', '/api/human-alerts', dict(BODY, asset='HYD-02'), source_loop=True)
    assert other_asset == 200 and body2['instance'] != body['instance'], '다른 설비는 따로 연다'


NOT_PEOPLE = [            # (입력자 값 — ... 은 칸 없음, 상태, 사유)
    (..., 400, NOT_A_PERSON), ('  ', 400, NOT_A_PERSON),                                    # 입력자가 없다
    ('김운전', 403, NOT_A_PERSON), ('role:operator', 403, NOT_A_PERSON), ('sys:agent', 403, NOT_A_PERSON),   # 이름만 적음 · 역할 id · 에이전트
    ('user:nobody', 403, '없는 사람 사용자입니다: user:nobody'),                              # 등록되지 않은 사람
]


def test_오일_분석_입력은_등록된_사람_사용자만_하고_입력자_이름은_사용자_표에서_읽는다(world):
    """전수 검사 01 지적 6: 입력자를 아무 글이나 받아 경보 근거(enteredBy)와 감사 기록에 사람처럼 남겼다."""
    for by, status, words in NOT_PEOPLE:
        body = {k: v for k, v in BODY.items() if k != 'by'} | ({} if by is ... else {'by': by}) | {'asset': 'HYD-03'}
        got, refused = world.api('POST', '/api/human-alerts', body, source_loop=True)
        assert (got, refused['detail']) == (status, words), (by, refused)
    assert world.rt.repo.list_instances('RUNNING', None, 'hyd', asset='HYD-03') == [], '거절한 입력은 경보도 처리 건도 만들지 않는다'
    got, body = world.api('POST', '/api/human-alerts', dict(BODY, asset='HYD-03', by_name='지어낸 이름', role='role:plant-mgr'), source_loop=True)
    assert got == 200 and body['raised'] is True, body
    assert body['alert']['enteredBy'] == ENTERED, '요청이 적어 보낸 이름 · 역할은 경보에 싣지 않는다'
