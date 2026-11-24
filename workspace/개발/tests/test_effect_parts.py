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
    assert rows == [{'name': '정비 요청', 'value': 'WO-1'}, {'name': '정비 시점', 'value': '오늘 밤'}, {'name': '공지 메일', 'value': '보냄', 'ok': True}]


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
    plan = ep.wait_plan(virtual_s, NOW, scale, plant=True)
    assert plan['real_s'] == (0.0 if factor is None else round(virtual_s / (factor * compression), 1))
    assert ep.parse_time(plan['due_at']) == NOW + timedelta(seconds=plan['real_s'])


def test_가상_설비_밖의_현장을_다루는_처리_건의_대기는_벽시계다(compression):
    """S-A: 「시간 대기」가 어느 처리 건이든 배속 × 수업 압축(7200배)이라, 학생 설비의 「PT30M 뒤 다시 읽기」가 0.25초 뒤에 읽혔다."""
    site = ep.wait_for({'duration': 'PT30M'}, {}, NOW, 20, plant=False)
    assert (site['real_s'], site['time_scale'], site['compression'], site['clock']) == (1800.0, 1.0, 1.0, '벽시계'), site
    plant = ep.wait_for({'duration': 'PT30M'}, {}, NOW, 20, plant=True)
    assert plant['real_s'] == round(1800 / (20 * compression), 1) and plant['clock'] == '가상 설비 · 모의 업무 시간', plant


@pytest.mark.parametrize('template, values, out', [
    ('{asset} 정비', {'asset': 'HYD-02'}, 'HYD-02 정비'),
    ('{approved_amount}', {'approved_amount': 385}, 385),
    ({'to': ['{who}'], 'n': '{work_order.ref}'}, {'who': 'a@b', 'work_order': {'ref': 'WO-9'}}, {'to': ['a@b'], 'n': 'WO-9'}),
], ids=['글 안 치환', '통째 값은 그대로', '안쪽 칸'])
def test_인자_틀의_이름은_처리_건_값으로_바뀐다(template, values, out):
    assert ep.render(template, values) == out


@pytest.mark.parametrize('template, values', [
    ('{work_order.ref}', {'work_order': {}}),
    ('발주 {purchase_order.ref} 입고', {'purchase_order': {'ref': None}}),     # 새13: 값 칸은 있는데 비었다 — 「발주  입고」로 보내지 않는다
], ids=['없는 칸', '글 안의 빈 값'])
def test_인자_틀에_없는_값은_빈_값으로_보내지_않고_실패한다(template, values):
    with pytest.raises(KeyError, match='work_order.ref|purchase_order.ref'):
        ep.render(template, values)


def test_결과_보고_글에_없는_값은_없음으로_적고_보고는_나간다():
    assert ep.render_report('{asset} — {missing}', {'asset': 'HYD-01'}) == 'HYD-01 — (없음)'


# ---------------------------------------------------------------- 발주 값(승인 경로)
QUOTES = [{'supplier': 'sup:b', 'price': 55, 'lead_d': 5, 'avl': True, 'fail_rate': 0.02, 'name': 'B-OEM'}]
CARD = {'id': 'skill:buy', 'actions': [{'code': 'PR_CREATE', 'value': 'sup:b'}]}


@pytest.mark.parametrize('values, error', [
    ({'part_no': 'P-PMP-SEAL', 'need_qty': 6}, None),
    ({'alert': {'evidence': {'part_no': 'P-PMP-SEAL', 'need_qty': '6'}}}, None),
    ({'part_no': 'P-PMP-SEAL'}, '발주할 수량이 없습니다'),
    ({}, '발주할 부품 · 수량이 없습니다'),
    ({'part_no': 'P-FAN-BRG', 'need_qty': 1}, 'P-FAN-BRG 의 sup:b 견적이 없어'),
], ids=['처리 건 값', '경보 근거', '수량 없음', '부품 · 수량 없음', '그 부품 견적 없음'])
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
    # 새1 · D-2: 시운전 기준의 기본값(유압 운전점 셋)을 지웠다 — 쿨러 결함을 다루지 않는 조치를 승인해도 시운전이 통과했다
    ({'id': 'T', 'tool': ep.TEST_RUN_TOOL, 'service': {}, 'outputData': ['test_run', 'passed']}, '시운전 기준을 적으세요 — 고친 결함이 드러나는 태그'),
    ({'id': 'T', 'tool': ep.TEST_RUN_TOOL, 'service': {'criteria': {'TS1': ['<', 55]}}, 'outputData': ['test_run', 'passed']}, None),
    # 새4: 정비 수행의 대상 부품 · 조치 방법 칸을 지웠다 — 승인한 카드와 무관하게 같은 것을 고쳤다(고칠 대상은 승인한 조치 방법이 정한다)
    ({'id': 'T', 'tool': ep.RESTORE_TOOL, 'service': {'component': 'cooler'}, 'outputData': ['maintenance']}, '모르는 설정 칸 component'),
    ({'id': 'T', 'tool': ep.RESTORE_TOOL, 'service': {'sop': 'SOP-COOL-14'}, 'outputData': ['maintenance']}, '모르는 설정 칸 sop'),
    # 시운전의 계수기 리셋 칸을 지웠다 — 그 거래는 정기 정비 요청을 끝낸 뒤에만 받는데 업무 시스템이 정기 정비 요청의 완료를 받지 않아 성공할 길이 없었다
    ({'id': 'T', 'tool': ep.TEST_RUN_TOOL, 'service': {'criteria': {'TS1': ['<', 55]}, 'reset_counter': True}, 'outputData': ['test_run', 'passed']},
     '모르는 설정 칸 reset_counter'),
], ids=['시간 대기 정상', '기간과 시각 둘 다', '설정 칸 오타', '시운전 연산 오타', '모르는 결과', 'MCP 출력 이름', '지운 즉시 입고 설정',
        '시운전 기준 없음', '시운전 기준 있음', '정비 대상 부품 칸', '정비 조치 방법 칸', '시운전 계수기 리셋 칸'])
def test_부품_설정은_오타나_빠진_칸을_조용히_넘기지_않는다(activity, error):
    if error is None:
        ep.validate(activity)
    else:
        with pytest.raises(ValueError, match=error):
            ep.validate(activity)


@pytest.mark.parametrize('condition, problems', [
    ('accepted == True', []),
    ('accepted > 3', ["accepted(Boolean)에는 '>' 비교를 쓸 수 없습니다"]),
    ("count == '예'", ["count(Number)을 '예' 와 비교합니다 — 자료형이 다릅니다"]),
    ('status', ['status(Text)는 참/거짓 값이 아니라 그대로 조건으로 쓸 수 없습니다']),
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


@pytest.mark.parametrize('shown, error', [(330, None), (330.004, None), (None, None), (440, '발주 금액을 440만 원으로 계산했는데, 이 처리 건이 발주할 수량 6개 × 단가 55만 원은 330만 원')],
                         ids=['판단 금액과 같음', '반올림 차이', '판단이 금액을 싣지 않음', '판단 뒤 필요 수량이 바뀜'])
def test_판단이_계산해_보인_발주_금액과_이_처리_건이_발주할_금액이_다르면_승인을_받지_않는다(shown, error):
    """승인 화면의 금액은 판단이 판단 때의 ERP 필요 수량으로 계산한 값(안의 facts.po_amount)이고, 발주는 처리 건의 수량(경보 근거 · 시작 입력)으로 나간다.
    경보 뒤 재고가 바뀌어(예: 다른 처리 건이 같은 부품을 예약) 둘이 다르면 사람이 본 금액과 다른 금액이 발주됐다."""
    card = dict(CARD, facts={'po_amount': shown} if shown is not None else {})
    values = {'alert': {'evidence': {'part_no': 'P-PMP-SEAL', 'need_qty': 6}}}
    if error is None:
        assert ep.purchase_quote(card, values, QUOTES)['approved_amount'] == 330
    else:
        with pytest.raises(ValueError, match=error) as e:
            ep.purchase_quote(card, values, QUOTES)
        assert '반려하고 지금 재고로 새 처리 건을 시작하세요' in str(e.value)


def test_견적에_공급사_이름이_없으면_발주_값을_확정하지_않고_그_까닭으로_멈춘다():
    """공급사 이름의 정본은 업무 DB(ent.suppliers.name) — 견적에 없으면 화면이 id 를 보이게 두지 않고 승인에서 멈춘다."""
    nameless = [dict(QUOTES[0], name=None)]
    with pytest.raises(ValueError, match='공급사 이름이 없어'):
        ep.purchase_quote(CARD, {'part_no': 'P-PMP-SEAL', 'need_qty': 6}, nameless)


def test_시운전_중_바깥_변화가_있었으면_결과_값에_그_변화를_미달로_싣는다():
    """D-1 · 새1: 시운전 중에 설비가 승인한 조치 밖에서 바뀌면 값이 기준 안이어도 미달이다 — 결과 값이 기준 안 값만 보여 「왜 미달인가」가 안 보이지 않게."""
    change = {'boot': 'b', 'seq': 4, 'kind': 'reset', 'what': '[설비 초기화] — 설비 3기를 정상 운전점으로 되돌림(결함 · 보호 정지 · 팬 · 부하 지령)'}
    rows = ep.report_values({'test_run': {'passed': False, 'readings': [{'tag': 'TS1', 'op': '<', 'limit': 55, 'value': 48.0, 'ok': True}],
                                          'outside': change}})
    assert rows[-1] == {'name': '승인한 조치 밖의 설비 변화', 'value': change['what'], 'ok': False}, rows
