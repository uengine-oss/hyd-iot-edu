"""성과 지표(procsvc/kpi.py) — 부품 구매비 · 부품 단가 · 부품 품질 · 보전비를 실제 업무 DB(마이그레이션 + 시드가 들어간 테스트 DB)에서 계산한다.

발주 행은 업무 DB 의 실제 ERP 실행 함수(ent.exec_skill, skill:procure-part)로 만든다 — 학생 흐름 C 의 승인 뒤 발주와 같은 길이고,
그 함수가 견적(ent.quote_rows) · AVL 을 다시 확인해 수량 · 단가 · 금액을 행에 남긴다. 작업지시도 같은 함수(skill:schedule-maintenance)로 만든다.
정답은 규칙에서 낸다: 부품 구매비 = Σ 수량 × 그 공급사 견적 단가, 단가 = 발주 건별 견적 단가 평균, 품질 = 발주 공급사 품질 점수 평균,
보전비 = Σ 작업지시 SOP 의 표준 작업비(세척 SOP 는 그 설비 정비 기준표의 세척 비용). 견적 · 기준 값은 테스트가 업무 DB 표에서 직접 읽는다.

각 테스트는 자기 행만 세도록 DB 시계로 잰 기간(행을 넣기 직전 ~ 직후)으로 지표 함수를 부른다(같은 DB 를 다른 테스트와 나눠 써도 같은 결과).
"""
import json
import uuid
from contextlib import contextmanager
from datetime import timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from procsvc import kpi


@pytest.fixture
def db(pg_dsn):
    with psycopg.connect(pg_dsn, autocommit=True, row_factory=dict_row) as conn:
        yield conn


def _now(db):
    return db.execute('SELECT clock_timestamp() AS t').fetchone()['t']


@contextmanager
def _window(db):
    """with 블록 안에서 넣은 행만 담는 기간 — 끝나면 box['w'] 에 kpi.Window."""
    box = {}
    t0 = _now(db)
    yield box
    box['w'] = kpi.Window('custom', 'test', t0, _now(db) + timedelta(milliseconds=1))


def _calc(pg_dsn, fn, w):
    src = kpi.PgSources(pg_dsn, pg_dsn, driver_factory=None)
    try:
        return fn(kpi.Fetch(src), w, {})
    finally:
        src.close()


def _exec(db, skill, asset, params):
    body = {'decision': 'test-' + uuid.uuid4().hex, 'option': 'test-option', 'skill': skill, 'asset': asset, 'by': 'kpi-test', 'params': params}
    return db.execute('SELECT ent.exec_skill(%s::jsonb) AS r', [json.dumps(body)]).fetchone()['r']


def _order(db, supplier, part_no, qty, asset='HYD-03'):
    return _exec(db, 'skill:procure-part', asset, {'supplier': supplier, 'part_no': part_no, 'qty': qty})


def _quote(db, part_no, supplier):
    """그 공급사의 그 부품 견적 단가(만원) — ERP 가 발주 때 쓰는 같은 견적 함수."""
    return float(db.execute('SELECT price FROM ent.quote_rows(%s) WHERE supplier_id = %s', [part_no, supplier]).fetchone()['price'])


def _quality(db, supplier):
    return float(db.execute('SELECT quality_score FROM ent.suppliers WHERE id = %s', [supplier]).fetchone()['quality_score'])


# ------------------------------------------------------------------ 부품 구매비 · 단가 · 품질 (발주 행)
ORDERS = {
    '발주 0건': [],
    '씰 키트 1개': [('sup:b', 'P-PMP-SEAL', 1)],
    '씰 키트 7개(수업 흐름 C 의 보충량)': [('sup:b', 'P-PMP-SEAL', 7)],
    '쿨러 코어 2개(견적이 공급사 표에만 있는 부품)': [('sup:a', 'P-CLR-CORE', 2)],
    '씰 키트 3개 + 쿨러 코어 1개(공급사 둘)': [('sup:a', 'P-PMP-SEAL', 3), ('sup:b', 'P-CLR-CORE', 1)],
}


@pytest.mark.parametrize('orders', ORDERS.values(), ids=ORDERS.keys())
def test_부품_구매비는_발주마다_수량_곱하기_견적단가를_더한_값이다(db, pg_dsn, orders):
    with _window(db) as box:
        for supplier, part_no, qty in orders:
            _order(db, supplier, part_no, qty)
    expected = round(sum(qty * _quote(db, part_no, supplier) for supplier, part_no, qty in orders), 2)
    calc = _calc(pg_dsn, kpi.calc_part_cost, box['w'])
    assert calc.status is None, calc.reason
    assert calc.value == expected
    assert [d['금액 만원'] for d in calc.detail] == [qty * _quote(db, p, s) for s, p, qty in orders]


@pytest.mark.parametrize('orders', [v for v in ORDERS.values() if v], ids=[k for k, v in ORDERS.items() if v])
def test_부품_단가는_발주_건별_견적단가의_평균이다(db, pg_dsn, orders):
    with _window(db) as box:
        for supplier, part_no, qty in orders:
            _order(db, supplier, part_no, qty)
    prices = [_quote(db, part_no, supplier) for supplier, part_no, _ in orders]
    calc = _calc(pg_dsn, kpi.calc_part_price, box['w'])
    assert calc.status is None, calc.reason
    assert calc.value == round(sum(prices) / len(prices), 3)


@pytest.mark.parametrize('orders', [v for v in ORDERS.values() if v], ids=[k for k, v in ORDERS.items() if v])
def test_부품_품질은_발주한_공급사_품질점수의_평균이다(db, pg_dsn, orders):
    with _window(db) as box:
        for supplier, part_no, qty in orders:
            _order(db, supplier, part_no, qty)
    scores = [_quality(db, supplier) for supplier, _, _ in orders]
    calc = _calc(pg_dsn, kpi.calc_part_quality, box['w'])
    assert calc.status is None, calc.reason
    assert calc.value == round(sum(scores) / len(scores), 3)


@pytest.mark.parametrize('fn', [kpi.calc_part_price, kpi.calc_part_quality], ids=['부품 단가', '부품 품질'])
def test_발주가_없으면_단가와_품질은_기록_없음이다(db, pg_dsn, fn):
    with _window(db) as box:
        pass
    calc = _calc(pg_dsn, fn, box['w'])
    assert (calc.value, calc.status, calc.reason) == (None, 'no_data', '기간 안 발주가 없습니다')


def test_수량_금액_없이_들어온_구매요청은_금액을_지어내지_않고_부분_실적이다(db, pg_dsn):
    """G5b-23: 「옛 길」이 아니다 — 승인 전달(approval_hooks.deliver)이 카드의 PR_CREATE 를 부품 번호 · 수량 없이 내는 꼴이 지금도 있다
    (decisions.approve 의 실행 항목에 수량이 없고, 발주 task 가 없는 흐름의 구매 카드가 이 길로 간다)."""
    with _window(db) as box:
        _order(db, 'sup:b', 'P-PMP-SEAL', 2)
        _exec(db, 'skill:procure-part', 'HYD-01', {'supplier': 'sup:a', 'part': '쿨러 코어'})   # 카드 승인 전달과 같은 인자(공급사 · 부품 이름)
    calc = _calc(pg_dsn, kpi.calc_part_cost, box['w'])
    assert calc.status == 'partial'
    assert calc.value == 2 * _quote(db, 'P-PMP-SEAL', 'sup:b')
    assert calc.reason.startswith('발주 2건 중 1건은 수량 · 금액 없이 기록된 구매요청이라 금액을 셀 수 없습니다: 쿨러 코어(')
    assert 'ent.' not in calc.reason          # 학생에게 표 이름을 보이지 않는다


def test_비승인_공급사_발주는_업무_DB가_거절해_지표에_들어가지_않는다(db, pg_dsn):
    with _window(db) as box:
        with pytest.raises(psycopg.Error, match='승인 공급사 목록\(AVL\)에 없어 발주하지 않습니다'):
            _order(db, 'sup:c', 'P-PMP-SEAL', 1)
    assert _calc(pg_dsn, kpi.calc_part_cost, box['w']).value == 0


# ------------------------------------------------------------------ 보전비 (작업지시 → SOP → 정비 표준 작업비, 조건별 손익과 같은 원천)
def _work_order(db, asset, sop, name):
    """process 가 남기는 작업지시 글('<SOP> <조치 이름> → 작업지시 <값>' — main.exec_skill)로 CMMS 작업지시를 만든다."""
    return _exec(db, 'skill:schedule-maintenance', asset, {'task': f'{sop} {name} → 작업지시 {sop}', 'window': '즉시'})


def _clean_cost(db, asset):
    return float(db.execute('SELECT clean_cost FROM ent.maintenance_profiles WHERE asset = %s', [asset]).fetchone()['clean_cost'])


def _labor(db, sop):
    return float(db.execute('SELECT labor_cost FROM ent.task_standards WHERE sop = %s', [sop]).fetchone()['labor_cost'])


def test_세척_작업지시의_보전비는_그_설비_정비_기준표의_세척_비용이다(db, pg_dsn):
    with _window(db) as box:
        _work_order(db, 'HYD-01', 'SOP-COOL-14', '쿨러 핀 세척')
    calc = _calc(pg_dsn, kpi.calc_maint_cost, box['w'])
    assert (calc.status, calc.value) == (None, _clean_cost(db, 'HYD-01'))


def test_표준_작업표의_작업비로_세고_원문에_작업비가_없는_팬_점검은_지어내지_않고_부분_실적이다(db, pg_dsn):
    """070 이 SOP-FAN-11 · 12 작업비를 지웠다(강사 서명 원문에 없는 값) — 그 작업지시는 셀 수 없음으로 남고 다른 오더는 작업비로 센다."""
    with _window(db) as box:
        _work_order(db, 'HYD-02', 'SOP-COOL-15', '캐비닛 환기 보강')
        _work_order(db, 'HYD-03', 'SOP-FAN-11', '쿨러 팬 점검 절차')
    calc = _calc(pg_dsn, kpi.calc_maint_cost, box['w'])
    assert calc.status == 'partial' and calc.reason.endswith(': SOP-FAN-11'), calc.reason
    assert calc.value == _labor(db, 'SOP-COOL-15') and calc.per_asset == {'HYD-02': _labor(db, 'SOP-COOL-15')}


def test_표준_작업표에_없는_SOP는_비용을_지어내지_않고_그_SOP를_사유에_적는다(db, pg_dsn):
    with _window(db) as box:
        _work_order(db, 'HYD-01', 'SOP-COOL-14', '쿨러 핀 세척')
        _work_order(db, 'HYD-01', 'SOP-COOL-11', '팬 최대 운전')   # 매뉴얼에서 온 조치 — 표준 작업표에 작업비가 없다
    calc = _calc(pg_dsn, kpi.calc_maint_cost, box['w'])
    assert calc.status == 'partial'
    assert calc.value == _clean_cost(db, 'HYD-01')
    assert calc.reason == '작업지시 2건 중 1건은 업무 DB 정비 표준 작업에 그 작업의 작업비가 없어 셀 수 없습니다: SOP-COOL-11'


def test_정기_정비_범위_오더는_실제_정비_패키지의_SOP로_찾는다(db, pg_dsn):
    """흐름 B 의 범위 정비 오더는 task 글 머리가 판단 SOP(SOP-PM-11)이고 실제 패키지 SOP 는 package.package_sop 에 있다 — 패키지를 본다."""
    wo = 'WO-TEST-' + uuid.uuid4().hex[:12].upper()
    with _window(db) as box:
        db.execute("""INSERT INTO ent.work_orders (id, asset, task, window_label, decision_id, option_id, requested_by, package)
                      VALUES (%s, 'HYD-02', 'SOP-PM-11 이번 예정된 정비 시간에 단독 시행 → 작업지시 SOP-PM-11', '즉시', 'test', 'test', 'kpi-test', %s::jsonb)""",
                   [wo, json.dumps({'package_sop': 'SOP-FAN-12', 'package_name': '벨트 교체 절차'})])
    calc = _calc(pg_dsn, kpi.calc_maint_cost, box['w'])
    assert calc.detail[0]['작업 SOP'] == 'SOP-FAN-12'                      # 판단 SOP(SOP-PM-11)가 아니라 패키지 SOP 로 찾았다
    assert (calc.status, calc.value) == ('partial', 0) and calc.reason.endswith(': SOP-FAN-12'), calc.reason   # 그 패키지 작업비는 원문에 없다(070)


def test_작업지시가_없으면_보전비는_0이다(db, pg_dsn):
    with _window(db) as box:
        pass
    calc = _calc(pg_dsn, kpi.calc_maint_cost, box['w'])
    assert (calc.status, calc.value, calc.note) == (None, 0, '기간 합계 · 작업지시 0건')


# ------------------------------------------------------------------ 판정 · 합성 · 사유 문장
def _evaluate(pg_dsn, measure, others=()):
    src = kpi.PgSources(pg_dsn, pg_dsn, driver_factory=None)
    try:
        measures = {m['id']: m for m in (measure, *others)}
        w = kpi.window(start='2001-01-01T00:00:00Z', end='2001-01-02T00:00:00Z')      # 다른 테스트의 행이 없는 기간(실적 0)
        return kpi.evaluate(measure, kpi.Fetch(src), w, {'measures': measures, 'tenant': 'hyd', 'time_scale': 20.0, 'window': w}, {})
    finally:
        src.close()


@pytest.mark.parametrize('mid', ['msr:maint-cost', 'msr:part-cost'], ids=['보전비', '부품 구매비'])
def test_기간_합계_실적은_월_목표와_견주지_않고_까닭을_적는다(pg_dsn, mid):
    """W2-24: 전에는 1시간 · 30일 합계를 같은 월 목표와 비교해 기간을 바꾸면 판정이 뒤집혔다."""
    out = _evaluate(pg_dsn, {'id': mid, 'name': '비용', 'unit': '만원/월', 'target': 100.0, 'direction': 'DOWN'})
    assert out['status'] == 'incomparable' and out['met'] is None and out['rate'] is None
    assert out['reason'].startswith('실적은 만원 (기간 합계)이고 목표는 만원/월이라 견주지 않습니다')


def test_같은_단위의_목표면_달성과_미달을_판정한다(pg_dsn):
    out = _evaluate(pg_dsn, {'id': 'msr:part-cost', 'name': '부품 구매비', 'unit': '만원 (기간 합계)', 'target': 10 ** 9, 'direction': 'DOWN'})
    assert out['status'] == 'met' and out['met'] is True


def test_단위가_다른_구성_지표는_합성_지표에서_더하지_않는다(pg_dsn):
    """P4-18: 전에는 기간 합계(보전비)와 다른 단위의 값을 더해 합성 지표로 냈다."""
    maint = {'id': 'msr:maint-cost', 'name': '보전비', 'unit': '만원/월'}
    stock = {'id': 'msr:inventory', 'name': '완제품 재고', 'unit': '개'}
    total = {'id': 'msr:test-total', 'name': '시험 합계', 'unit': '만원/월', 'formula': 'msr:maint-cost + msr:inventory'}
    out = _evaluate(pg_dsn, total, (maint, stock))
    assert out['status'] == 'unavailable' and out['value'] is None
    assert out['reason'] == '구성 지표의 단위가 달라 더할 수 없습니다: 보전비 = 만원 (기간 합계) / 완제품 재고 = 개'
    assert [d['지표'] for d in out['detail']] == ['보전비', '완제품 재고'], '계산 근거 표는 한국어 열 이름'


def test_같은_단위의_구성_지표는_합성_지표로_더하고_그_단위를_쓴다(pg_dsn):
    maint = {'id': 'msr:maint-cost', 'name': '보전비', 'unit': '만원/월'}
    parts = {'id': 'msr:part-cost', 'name': '부품 구매비', 'unit': '만원/월'}
    total = {'id': 'msr:test-total', 'name': '시험 합계', 'unit': '만원 (기간 합계)', 'formula': 'msr:maint-cost + msr:part-cost'}
    out = _evaluate(pg_dsn, total, (maint, parts))
    assert out['displayUnit'] == '만원 (기간 합계)' and out['value'] == round(sum(d['실적'] for d in out['detail']), 2)


@pytest.mark.parametrize('mid', sorted(m for m, d in kpi.DEFINITIONS.items() if 'reason' in d))
def test_계산_불가_사유는_업무_말로_적고_표_열_이름을_쓰지_않는다(mid):
    """W2-04: 전에는 사유를 표 · 열 이름으로 쓰고 화면이 단어를 갈아 끼워 「유온 유온 은」 같은 문장이 나왔다."""
    import re
    reason = kpi.DEFINITIONS[mid]['reason']
    assert not re.search(r'\b[a-z]+_[a-z_0-9]+\b|ent\.|\b(?:TS1|EPS1|LoadSP)\b', reason), reason
