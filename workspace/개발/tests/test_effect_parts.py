"""승인 뒤 실행 부품 계약(procsvc/effect_parts.py) — 설정 검사 · 인자 틀 · 대기 계산 · 발주 값 · 결과 보고 측정값(순수 함수)."""
from datetime import datetime, timedelta, timezone

import pytest

from procsvc import effect_parts as ep, engine

NOW = datetime(2026, 10, 30, 6, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- 결과 보고 측정값
@pytest.mark.parametrize('reading, name, unit, limit', [
    ({'tag': 'EPS1', 'value': 2.81, 'op': '<', 'limit': 3.5, 'ok': True}, '모터 전력 (EPS1)', ' kW', '< 3.5 kW'),
    ({'tag': 'PS1', 'value': 181.96, 'op': '>=', 'limit': 165.0, 'ok': True}, '토출 압력 (PS1)', ' bar', '≥ 165 bar'),
    ({'tag': 'VS1', 'value': 0.61, 'op': '<', 'limit': 1.2, 'ok': True}, '팬 진동 (VS1)', ' mm/s', '< 1.2 mm/s'),
], ids=['모터 전력은 kW', '토출 압력', '팬 진동'])
def test_시운전_측정값은_온톨로지_센서_이름과_설비_모형의_단위로_보인다(reading, name, unit, limit):
    """P4-06: 전에는 모터 전력이 W 로 나왔다(설비 모형 · 성과 지표는 kW)."""
    row = ep.report_values({'test_run': {'readings': [reading]}})[0]
    assert (row['name'], row['unit'], row['limit'], row['ok']) == (name, unit, limit, True)


def test_값을_읽지_못한_측정은_지어내지_않고_값_없음으로_보인다():
    row = ep.report_values({'test_run': {'readings': [{'tag': 'FS1', 'value': None, 'op': '>=', 'limit': 8.0, 'ok': False}]}})[0]
    assert row['value'] == '값 없음' and 'unit' not in row and row['ok'] is False


@pytest.mark.parametrize('idempotent', [True, False, None], ids=['중복 방지 키 받음', '중복 방지 키 없음', '모름'])
def test_정비_오더_공지_메일은_도구의_중복_방지_여부와_상관없이_보냄으로만_적는다(idempotent):
    """P4-20: 전에는 idempotent=False(도구가 중복 방지 키를 받지 않음)를 「재전송 아님」으로 거꾸로 읽어 적었다."""
    rows = ep.report_values({'work_order': {'ref': 'WO-1', 'after': {'window_label': '오늘 밤'}, 'notice': {'idempotent': idempotent}}})
    assert rows == [{'name': '정비 오더', 'value': 'WO-1'}, {'name': '정비 시점', 'value': '오늘 밤'}, {'name': '공지 메일', 'value': '보냄', 'ok': True}]


@pytest.mark.parametrize('criteria, readings, passed', [
    ({'PS1': ['>=', 165.0], 'VS1': ['<', 1.2]}, {'PS1': 182.0, 'VS1': 0.6}, True),
    ({'PS1': ['>=', 165.0]}, {'PS1': 165.0}, True),
    ({'VS1': ['<', 1.2]}, {'VS1': 1.2}, False),
    ({'PS1': ['>=', 165.0]}, {'PS1': None}, False),
], ids=['모두 통과', '경계 이상 통과', '경계 미만 실패', '값 없음은 미달'])
def test_시운전은_기준마다_최신값을_비교하고_모르는_값을_통과로_치지_않는다(criteria, readings, passed):
    ok, rows = ep.test_run_verdict(criteria, readings)
    assert ok is passed and [r['tag'] for r in rows] == list(criteria)


# ---------------------------------------------------------------- 대기 · 인자 틀
@pytest.fixture
def compression():
    """수업용 대기 압축 60(compose 값)을 이 테스트 동안만 — 앞 테스트(process 기동 등)가 전역에 남긴 값에 기대지 않고, 끝나면 앞 값으로 되돌린다."""
    before = engine.wait_compression()
    engine.configure_wait_compression(60)
    yield 60
    engine.configure_wait_compression(before)


@pytest.mark.parametrize('virtual_s, scale, factor', [(5 * 86400, 20, 20), (-60, 20, None), (3600, 0.5, 1)],
                         ids=['리드타임 5일', '지난 시각은 0', '배속 1 미만은 1로'])
def test_기다리는_부품의_실제_대기는_업무_시간을_배속과_수업_압축으로_나눈_값이다(compression, virtual_s, scale, factor):
    plan = ep.wait_plan(virtual_s, NOW, scale)
    assert plan['real_s'] == (0.0 if factor is None else round(virtual_s / (factor * compression), 1))
    assert ep.parse_time(plan['due_at']) == NOW + timedelta(seconds=plan['real_s'])


@pytest.mark.parametrize('template, values, out', [
    ('{asset} 정비', {'asset': 'HYD-02'}, 'HYD-02 정비'),
    ('{approved_amount}', {'approved_amount': 385}, 385),
    ({'to': ['{who}'], 'n': '{work_order.ref}'}, {'who': 'a@b', 'work_order': {'ref': 'WO-9'}}, {'to': ['a@b'], 'n': 'WO-9'}),
], ids=['글 안 치환', '통째 값은 그대로', '안쪽 칸'])
def test_인자_틀의_이름은_처리_건_값으로_바뀐다(template, values, out):
    assert ep.render(template, values) == out


def test_인자_틀에_없는_값은_빈_값으로_보내지_않고_실패한다():
    with pytest.raises(KeyError, match='work_order.ref'):
        ep.render('{work_order.ref}', {'work_order': {}})


def test_결과_보고_글에_없는_값은_없음으로_적고_보고는_나간다():
    assert ep.render_report('{asset} — {missing}', {'asset': 'HYD-01'}) == 'HYD-01 — (없음)'


# ---------------------------------------------------------------- 발주 값(승인 경로)
QUOTES = [{'supplier': 'sup:b', 'price': 55, 'lead_d': 5, 'avl': True, 'fail_rate': 0.02, 'name': 'B-OEM'}]
CARD = {'id': 'skill:buy', 'actions': [{'code': 'PR_CREATE', 'value': 'sup:b'}]}


@pytest.mark.parametrize('values, error', [
    ({'part_no': 'P-PMP-SEAL', 'need_qty': 6}, None),
    ({'alert': {'evidence': {'part_no': 'P-PMP-SEAL', 'need_qty': '6'}}}, None),
    ({'part_no': 'P-PMP-SEAL'}, '수량을 확정할 수 없습니다'),
    ({'part_no': 'P-FAN-BRG', 'need_qty': 1}, 'P-FAN-BRG 의 sup:b 견적이 없어'),
], ids=['처리 건 값', '경보 근거', '수량 없음', '그 부품 견적 없음'])
def test_발주_금액은_견적_단가_곱하기_수량이고_모르면_승인을_받지_않는다(values, error):
    quotes = QUOTES if 'FAN' not in str(values) else []
    if error is None:
        got = ep.purchase_quote(CARD, values, quotes)
        assert (got['approved_qty'], got['approved_unit_price'], got['approved_amount']) == (6, 55, 330)
        assert (got['approved_supplier'], got['approved_supplier_name']) == ('sup:b', 'B-OEM')   # 화면이 쓰는 이름은 견적(업무 DB 공급사 원장)의 것
    else:
        with pytest.raises(ValueError, match=error):
            ep.purchase_quote(CARD, values, quotes)


# ---------------------------------------------------------------- 등록 검사
@pytest.mark.parametrize('activity, error', [
    ({'id': 'T', 'tool': ep.WAIT_TOOL, 'service': {'duration': 'PT9H'}, 'outputData': ['waited']}, None),
    ({'id': 'T', 'tool': ep.WAIT_TOOL, 'service': {'duration': 'PT9H', 'until': 'x'}, 'outputData': ['waited']}, '하나를 정합니다'),
    ({'id': 'T', 'tool': ep.WAIT_TOOL, 'service': {'durration': 'PT9H'}, 'outputData': ['waited']}, '모르는 설정 칸 durration'),
    ({'id': 'T', 'tool': ep.TEST_RUN_TOOL, 'service': {'criteria': {'PS1': ['=>', 165]}}, 'outputData': ['test_run', 'passed']}, '시운전 기준'),
    ({'id': 'T', 'tool': ep.REPORT_TOOL, 'service': {'outcome': '좋음'}, 'outputData': ['result_report']}, '결과\\(outcome\\)'),
    ({'id': 'T', 'tool': ep.MCP_TOOL, 'service': {'server': 'hyd-effects', 'tool': 'send_mail'}, 'outputData': ['x']}, 'outputData 는'),
    ({'id': 'T', 'tool': ep.GR_TOOL, 'service': {'immediate': True}, 'outputData': ['goods_receipt', 'received']}, '모르는 설정 칸 immediate'),
], ids=['시간 대기 정상', '기간과 시각 둘 다', '설정 칸 오타', '시운전 연산 오타', '모르는 결과', 'MCP 출력 이름', '지운 즉시 입고 설정'])
def test_부품_설정은_오타나_빠진_칸을_조용히_넘기지_않는다(activity, error):
    if error is None:
        ep.validate(activity)
    else:
        with pytest.raises(ValueError, match=error):
            ep.validate(activity)


@pytest.mark.parametrize('condition, problems', [
    ('accepted == True', []),
    ('accepted > 3', ["accepted(Boolean)에는 '>' 비교를 쓸 수 없습니다"]),
    ("count == '예'", ["count(Number)을(를) '예' 와 비교합니다 — 자료형이 다릅니다"]),
    ('status', ['status(Text)은(는) 참/거짓 값이 아니라 그대로 조건으로 쓸 수 없습니다']),
], ids=['맞는 비교', '참거짓을 크기 비교', '수를 글과 비교', '글을 그대로 조건'])
def test_분기_조건은_꺼낸_값의_자료형대로_써야_한다(condition, problems):
    assert ep.condition_type_problems(condition, {'accepted': 'Boolean', 'count': 'Number', 'status': 'Text'}) == problems


@pytest.mark.parametrize('result, out, error', [
    ({'text': '{"attendees": [{"status": "accepted"}]}'}, {'s': 'accepted'}, None),
    ({'text': 'not json'}, None, 'JSON 이 아니라'),
    ({'text': '{"attendees": []}'}, None, "경로 'attendees.0.status'"),
    ({'text': '{"attendees": [{"status": 1}]}'}, None, 'Text 가 아닙니다'),
    ({'text': '{"a": 1}', 'truncated': True, 'size_chars': 99999}, None, '잘렸습니다'),
], ids=['꺼냄', 'JSON 아님', '경로 없음', '자료형 다름', '잘린 결과'])
def test_MCP_결과에서_값을_꺼내지_못하면_빈_값이_아니라_까닭과_함께_실패한다(result, out, error):
    extract = {'s': {'path': 'attendees.0.status', 'type': 'Text'}}
    if error is None:
        assert ep.extract_values(extract, result) == out
    else:
        with pytest.raises(ValueError, match=error):
            ep.extract_values(extract, result)


def test_견적에_공급사_이름이_없으면_발주_값을_확정하지_않고_그_까닭으로_멈춘다():
    """공급사 이름의 정본은 업무 DB(ent.suppliers.name) — 견적에 없으면 화면이 id 를 보이게 두지 않고 승인에서 멈춘다."""
    nameless = [dict(QUOTES[0], name=None)]
    with pytest.raises(ValueError, match='공급사 이름이 없어'):
        ep.purchase_quote(CARD, {'part_no': 'P-PMP-SEAL', 'need_qty': 6}, nameless)
