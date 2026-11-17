"""업무 DB 연결(it/enterprise-sim/entsim/supabase_backend.py) — 실제 업무 DB 함수(ent.exec_skill · ent.exec_compensation · 읽기 함수)를 부른다.

이 모듈만 쓰는 새 업무 DB(마이그레이션 전부 + seed.sql — 학생 PC 의 새 업무 DB 와 같다)에서 돈다: 거래가 재고 · 오더를 바꾸므로 묶음 DB 를 쓰는
다른 테스트에 남지 않게. 끝나면 지운다(끊긴 실행이 남긴 것은 다음 묶음이 지운다 — conftest new_database).
"""
import uuid

import psycopg
import pytest

from conftest import new_database
from entsim.supabase_backend import SupabaseEnterprise


@pytest.fixture(scope='module')
def ent_dsn(pg_dsn):
    with new_database(pg_dsn, schema=True) as dsn:
        yield dsn


@pytest.fixture
def ent(ent_dsn):
    return SupabaseEnterprise(lambda: psycopg.connect(ent_dsn, connect_timeout=5))


def sql(dsn, query, *args):
    with psycopg.connect(dsn, autocommit=True) as db:
        cur = db.execute(query, args)
        return cur.fetchall() if cur.description else None


def decision():
    return 'DEC-' + uuid.uuid4().hex[:12]


def work_order(**params):
    return {'decision': decision(), 'option': 'opt-1', 'skill': 'skill:schedule-maintenance', 'asset': 'HYD-01', 'by': 'user:park-maint',
            'params': {'task': 'SOP-COOL-04 쿨러 핀 세척', 'window': '즉시', **params}}


def purchase(part_no='P-PMP-SEAL', supplier='sup:b', qty=6, **extra):
    return {'decision': decision(), 'option': 'opt-1', 'skill': 'skill:procure-part', 'asset': 'HYD-02', 'by': 'user:jung-buy',
            'params': {'supplier': supplier, 'part_no': part_no, 'qty': qty, **extra}}


# ---------------------------------------------------------------- 읽기
@pytest.mark.parametrize('name, params, records', [
    ('spare_stock', {'part': 'P-PMP-SEAL'}, 1),
    ('spare_stock', {}, 4),                       # 부품을 비우면 관리 예비품 전부
    ('pm_status', {'asset': None}, 3),            # 설비를 비우면 세 대
    ('part_quotes', {'part': 'P-PMP-SEAL'}, 3),
], ids=['부품_하나', '부품_비움', '설비_비움', '견적'])
def test_읽기는_업무_DB_함수의_사실과_기록을_돌려준다(ent, name, params, records):
    out = ent.read(name, **params)
    assert out['facts'] is not None and len(out['records']) == records


@pytest.mark.parametrize('name, params', [
    ('spare_stock', {'part': 'P-없음'}), ('mes_orders', {'asset': 'HYD-09'}), ('part_quotes', {'part': None}),
], ids=['없는_부품', '없는_설비', '대상_비움'])
def test_업무_DB에_대상이_없으면_KeyError다(ent, name, params):
    with pytest.raises(KeyError):
        ent.read(name, **params)


# ---------------------------------------------------------------- 거래
def test_승인된_작업지시는_한_번_기록되고_같은_요청은_같은_거래를_돌려준다(ent, ent_dsn):
    body = work_order()
    first, again = ent.execute(body), ent.execute(body)
    assert again['id'] == first['id'] and first['system'] == 'sys:cmms'
    assert sql(ent_dsn, 'SELECT status, window_label FROM ent.work_orders WHERE id=%s', first['ref']) == [('배정됨', '즉시')]


def _refusals():
    long_basis = '가' * 301
    return [
        (dict(work_order(), skill='skill:issue-spare'), '업무 시스템에 없는 거래'),              # 부르는 곳이 없어 지운 거래
        (dict(work_order(), asset=None), '설비(asset)가 없습니다'),
        (dict(work_order(), asset='HYD-09'), '등록되지 않은 설비'),
        (dict(work_order(), params={'window': '즉시'}), '작업 내용(task)이 없습니다'),
        (dict(work_order(), params={'task': 'SOP-COOL-04'}), '정비 시점'),                      # 옛 판은 카드 id 글자로 「즉시 / 야간」을 짐작했다
        (dict(purchase(), params={'part_no': 'P-PMP-SEAL', 'qty': 6}), '공급사(supplier)가 없습니다'),   # 옛 판은 sup:b 로 대신 발주
        (purchase(supplier='sup:c'), '승인 공급사 목록(AVL)'),
        (purchase(qty=0), '발주 수량'),
        (purchase(amount=1), '승인한 금액'),
        (dict(purchase(), params={'supplier': 'sup:b'}), '품목(part 또는 part_no)'),             # 옛 판은 「쿨러 코어」로 채웠다
        ({'decision': decision(), 'skill': 'skill:receive-goods', 'asset': 'HYD-02', 'params': {'ref': 'PR-없음', 'inspection': '합격'}},
         '부르는 쪽이 정하지 않습니다'),
        ({'decision': decision(), 'skill': 'skill:receive-goods', 'asset': 'HYD-02', 'params': {'ref': 'PR-없음', 'lot': 'LOT-임의'}},
         '부르는 쪽이 정하지 않습니다'),
        ({'decision': decision(), 'skill': 'skill:receive-goods', 'asset': 'HYD-02', 'params': {'ref': 'PR-없음', 'basis': long_basis}},
         '300자'),
    ]


REFUSALS = _refusals()


@pytest.mark.parametrize('body, reason', REFUSALS, ids=[
    '지운_거래', '설비_없음', '없는_설비', '작업_없음', '정비_시점_없음', '공급사_없음', 'AVL_밖', '수량_0', '금액_다름', '품목_없음', '검수_결과를_정해_보냄', '로트를_정해_보냄', '근거_301자'])
def test_계약_입력이_없거나_틀린_거래는_기본값으로_채우지_않고_한국어_까닭으로_거절한다(ent, body, reason):
    with pytest.raises(psycopg.Error) as err:
        ent.execute(body)
    assert err.value.sqlstate == '22023' and reason in str(err.value)


def test_같은_판단의_같은_거래를_다른_입력으로_다시_보내면_멱등_충돌이다(ent):
    body = work_order()
    ent.execute(body)
    with pytest.raises(psycopg.Error) as err:
        ent.execute(dict(body, params=dict(body['params'], task='다른 작업')))
    assert err.value.sqlstate == '23505'


@pytest.mark.parametrize('on_hand, done', [(1, True), (0, False)], ids=['실물_있음', '실물_없음'])
def test_정비_완료는_표준_부품을_실물에서_소모하고_실물이_모자라면_거절한다(ent, ent_dsn, on_hand, done):
    """G2-09: 옛 판은 실물이 0이어도 0으로 두고 원장에는 소모를 그대로 적었다(재고 원장과 실물이 어긋남)."""
    # 표준 작업 하나(시험 자료 — 실제 수업 표준 작업에는 부품 소모가 있는 행이 없다: 원문에 그 값이 없다)
    sql(ent_dsn, "INSERT INTO ent.task_standards(sop, name, stop_h, labor_cost, part_no, part_qty) VALUES ('SOP-TEST-BRG', '시험 베어링 교체', 1, 1, "
                 "'P-FAN-BRG', 1) ON CONFLICT (sop) DO NOTHING")
    sql(ent_dsn, "UPDATE ent.spare_stock SET on_hand=%s, reserved=0 WHERE part_no='P-FAN-BRG'", on_hand)
    wo = ent.execute(dict(work_order(), asset='HYD-03'))
    complete = {'decision': decision(), 'skill': 'skill:complete-maintenance', 'asset': 'HYD-03', 'by': 'user:park-maint',
                'params': {'ref': wo['ref'], 'sop': 'SOP-TEST-BRG'}}
    if done:
        tx = ent.execute(complete)
        assert 'P-FAN-BRG 1개 소모' in tx['detail']
        assert sql(ent_dsn, "SELECT on_hand FROM ent.spare_stock WHERE part_no='P-FAN-BRG'") == [(on_hand - 1,)]
    else:
        with pytest.raises(psycopg.Error) as err:
            ent.execute(complete)
        assert err.value.sqlstate == '22023' and '실물 0개' in str(err.value)
        assert sql(ent_dsn, 'SELECT status FROM ent.work_orders WHERE id=%s', wo['ref']) == [('배정됨',)]


def test_입고는_시간_근거를_입고_기록과_발주에_남기고_거래_설명에_붙인다(ent, ent_dsn):
    """H-11: 처리 엔진은 리드타임 대기를 줄여 입고한다 — 그 근거가 업무 기록에 없으면 ERP 화면이 「예정보다 일찍 입고」로 읽힌다."""
    sql(ent_dsn, "UPDATE ent.spare_stock SET on_order=0 WHERE part_no='P-PMP-SEAL'")
    pr = ent.execute(purchase())
    basis = '업무 시간 리드타임 5일을 실제 60초로 줄여 기다린 뒤 입고했습니다'
    gr = ent.execute({'decision': decision(), 'skill': 'skill:receive-goods', 'asset': 'HYD-02', 'by': 'user:jung-buy',
                      'params': {'ref': pr['ref'], 'basis': basis}})
    assert gr['detail'].endswith(' — ' + basis)
    assert sql(ent_dsn, 'SELECT g.basis, r.receipt_basis, r.status FROM ent.goods_receipts g JOIN ent.purchase_requests r ON r.id = g.pr_id '
                        'WHERE g.id=%s', gr['ref']) == [(basis, basis, '입고 완료')]


@pytest.mark.parametrize('supplier, qty, accepted, rejected, status, inspection', [
    ('sup:b', 6, 6, 0, '입고 완료', '합격'),                       # 불량률 2 % × 6개 = 0.12개 → 0개
    ('sup:a', 6, 5, 1, '부분 입고', '1개 불합격 · 반품'),            # 불량률 12 % × 6개 = 0.72개 → 1개
    ('sup:a', 4, 4, 0, '입고 완료', '합격'),                       # 12 % × 4개 = 0.48개 → 0개 — 같은 공급사도 수량이 적으면 걸러질 것이 없다
    ('sup:a', 13, 11, 2, '부분 입고', '2개 불합격 · 반품'),          # 12 % × 13개 = 1.56개 → 2개
], ids=['순정 6개', '대체 6개', '대체 4개', '대체 13개'])
def test_입고_검수는_발주_수량과_공급사_불량률로_정해지고_같은_발주면_늘_같은_결과다(ent, ent_dsn, supplier, qty, accepted, rejected, status, inspection):
    """전에는 어느 공급사든 입고 검사가 늘 「합격」이었다. 모의 공급사 규칙(migration 074): 불합격 수량 = 발주 수량 × 견적 불량률을 반올림.
    무작위가 없다 — 같은 발주를 두 번 내면 두 번 다 같은 결과다. 합격분만 실물 재고에 오르고 입고 예정은 발주 수량만큼 닫힌다."""
    sql(ent_dsn, "UPDATE ent.spare_stock SET on_hand=3, reserved=2, on_order=0 WHERE part_no='P-PMP-SEAL'")
    seen = []
    for n in (1, 2):
        pr = ent.execute(purchase(supplier=supplier, qty=qty))
        gr = ent.execute({'decision': pr['decision'], 'skill': 'skill:receive-goods', 'asset': 'HYD-02', 'by': 'user:me', 'params': {'ref': pr['ref']}})
        after = gr['after']
        seen.append((after['qty'], after['rejected_qty'], after['ordered_qty'], after['inspection']))
        assert after['lot'] == 'LOT-' + pr['ref'], '로트 번호는 발주 번호에서 만든다'
        assert sql(ent_dsn, 'SELECT status FROM ent.purchase_requests WHERE id=%s', pr['ref']) == [(status,)]
        assert sql(ent_dsn, "SELECT on_hand, on_order FROM ent.spare_stock WHERE part_no='P-PMP-SEAL'") == [(3 + accepted * n, 0)]
        if rejected:
            assert f'{qty}개 중 {accepted}개 입고 · {rejected}개 검수 불합격 반품' in gr['detail'] and f'× {qty}개 = 기대 불량' in gr['detail'], gr['detail']
        else:
            assert f'{qty}개 입고 · 검수 합격' in gr['detail'], gr['detail']
    assert seen == [(accepted, rejected, qty, inspection)] * 2, seen


def test_공급사_견적이_사라진_발주는_검수_결과를_지어내지_않고_입고를_거절한다(ent, ent_dsn):
    pr = ent.execute(purchase(part_no='P-FAN-BRG', supplier='sup:a', qty=2))
    kept = sql(ent_dsn, "DELETE FROM ent.part_quotes WHERE part_no='P-FAN-BRG' AND supplier_id='sup:a' RETURNING price, fail_rate, lead_d")
    try:
        with pytest.raises(psycopg.Error) as err:
            ent.execute({'decision': pr['decision'], 'skill': 'skill:receive-goods', 'asset': 'HYD-02', 'by': 'user:me', 'params': {'ref': pr['ref']}})
        assert err.value.sqlstate == '22023' and '견적(불량률)이 없어 입고 검사 결과를 정할 수 없습니다' in str(err.value)
    finally:
        sql(ent_dsn, "INSERT INTO ent.part_quotes (part_no, supplier_id, price, fail_rate, lead_d) VALUES ('P-FAN-BRG', 'sup:a', %s, %s, %s)", *kept[0])
        ent.execute({'decision': pr['decision'], 'skill': 'skill:cancel-purchase-request', 'by': 'user:me', 'params': {'ref': pr['ref']}, 'compensates': pr['id']})


# ---------------------------------------------------------------- 되돌리기
def test_원거래_id가_실린_작업지시_취소는_오더를_취소로_닫는다(ent, ent_dsn):
    wo = ent.execute(work_order())
    undo = ent.execute({'decision': wo['decision'], 'skill': 'skill:cancel-work-order', 'by': 'user:park-maint',
                        'params': {'ref': wo['ref']}, 'compensates': wo['id']})
    assert undo['compensates'] == wo['id']
    assert sql(ent_dsn, 'SELECT status FROM ent.work_orders WHERE id=%s', wo['ref']) == [('취소',)]


def test_구매요청_취소는_입고_예정을_되돌린다(ent, ent_dsn):
    sql(ent_dsn, "UPDATE ent.spare_stock SET on_order=0 WHERE part_no='P-FAN-BRG'")
    pr = ent.execute(purchase(part_no='P-FAN-BRG', qty=2))
    ent.execute({'decision': pr['decision'], 'skill': 'skill:cancel-purchase-request', 'by': 'user:jung-buy',
                 'params': {'ref': pr['ref']}, 'compensates': pr['id']})
    assert sql(ent_dsn, "SELECT on_order FROM ent.spare_stock WHERE part_no='P-FAN-BRG'") == [(0,)]


@pytest.mark.parametrize('case, reason', [
    ('원거래_없음', '원거래 id compensates 와 함께'),        # 원거래 id 가 없으면 되돌리기가 아니다 — 원거래 함수가 「없는 거래」로 거절
    ('다른_원거래', '되돌릴 수 없습니다'),                   # 구매요청 거래를 작업지시 취소의 원거래로
    ('되돌리기_아님', '되돌리기 거래가 아닙니다'),
], ids=['원거래_없음', '다른_원거래', '되돌리기_아님'])
def test_되돌리기는_맞는_원거래가_있어야_한다(ent, case, reason):
    wo, pr = ent.execute(work_order()), ent.execute(purchase(part_no='P-FAN-BRG', qty=1))
    body = {'decision': wo['decision'], 'skill': 'skill:cancel-work-order', 'by': 'user:park-maint', 'params': {'ref': wo['ref']},
            'compensates': {'원거래_없음': None, '다른_원거래': pr['id'], '되돌리기_아님': wo['id']}[case]}
    if case == '되돌리기_아님':
        body['skill'] = 'skill:schedule-maintenance'
    with pytest.raises(psycopg.Error) as err:
        ent.execute(body)
    assert err.value.sqlstate == '22023' and reason in str(err.value)


# ---------------------------------------------------------------- 거래 원장 · 상태
def test_거래_원장은_원거래마다_되돌리기_계약을_싣는다(ent, ent_dsn):
    """G2-05 · P4-09: process 가 자기 표 없이 이 칸을 읽는다. 계약의 정본은 업무 DB 보기 ent.skill_contracts."""
    sql(ent_dsn, "UPDATE ent.spare_stock SET on_order=0 WHERE part_no='P-PMP-SEAL'")
    wo = ent.execute(work_order())
    undo = ent.execute({'decision': wo['decision'], 'skill': 'skill:cancel-work-order', 'by': 'b', 'params': {'ref': wo['ref']}, 'compensates': wo['id']})
    pr = ent.execute(purchase())
    gr = ent.execute({'decision': pr['decision'], 'skill': 'skill:receive-goods', 'asset': 'HYD-02', 'by': 'b', 'params': {'ref': pr['ref']}})
    legacy = 'DEC-legacy-' + uuid.uuid4().hex[:6]
    sql(ent_dsn, "INSERT INTO ent.transactions(id, system, skill, ref, detail, asset, decision_id, fingerprint) "
                 "VALUES (%s, 'sys:qms', 'skill:hold-lot', 'L-1', '옛 거래', 'HYD-01', %s, 'x')", 'TX-' + legacy, legacy)
    rows = {r['id']: r for d in (wo['decision'], pr['decision'], legacy) for r in ent.transactions(d)}
    contract = {k: (rows[k]['inverse'], rows[k]['irreversible_reason']) for k in (wo['id'], undo['id'], gr['id'], 'TX-' + legacy)}
    assert contract[wo['id']] == ('skill:cancel-work-order', None)
    assert contract[undo['id']] == (None, None)
    assert contract[gr['id']][0] is None and '실물이 창고에 들어와' in contract[gr['id']][1]
    assert contract['TX-' + legacy] == (None, SupabaseEnterprise.LEGACY_REASON)


def test_업무_상태는_표마다_최근_행만_싣는다(ent, ent_dsn):
    """G2-11: 포털이 2.5초마다 표 전체를 읽었다."""
    sql(ent_dsn, "INSERT INTO ent.work_orders(id, asset, task, window_label, created_at) "
                 "SELECT 'WO-BULK-' || g, 'HYD-02', '대량', '즉시', now() + make_interval(secs => g) FROM generate_series(1, %s) g",
        SupabaseEnterprise.SNAPSHOT_ROWS + 5)
    rows = ent.snapshot()['cmms']['work_orders']
    assert len(rows) == SupabaseEnterprise.SNAPSHOT_ROWS and rows[0]['id'] == f'WO-BULK-{SupabaseEnterprise.SNAPSHOT_ROWS + 5}'


def test_정비_이력의_다음_야간_정비_시간은_예정된_정비_시간_규칙에서_나온다(ent, ent_dsn):
    """G2-15: 옛 판은 프로필의 고정 시각(기준점 + 9 h)을 읽어, 규칙의 창이 지나간 뒤에도 같은 값(또는 음수)을 냈다.
    야간 규칙의 첫 창을 30시간 전으로 옮기면(주기 24 h · 길이 4 h) 다음 창은 18시간 뒤다."""
    sql(ent_dsn, "UPDATE ent.maintenance_window_rules SET first_at = now() - interval '30 hours' WHERE asset='HYD-01' AND kind='N'")
    night = ent.read('cmms_history', asset='HYD-01')['facts']['night_in_h']
    assert 17.9 < night <= 18.0


def test_정비_이력은_작업지시를_최근_20건과_전체_수로_싣는다(ent, ent_dsn):
    sql(ent_dsn, "INSERT INTO ent.work_orders(id, asset, task, window_label, maintenance_plan) "
                 "SELECT 'WO-HIST-BULK-' || g, 'HYD-03', '대량', '즉시', '{\"big\": true}'::jsonb FROM generate_series(1, 25) g")
    out = ent.read('cmms_history', asset='HYD-03')
    assert len(out['work_orders']) == 20 and out['work_orders_total'] >= 25
    assert all('maintenance_plan' not in w for w in out['work_orders'])


@pytest.mark.parametrize('dsn_ok', [True, False], ids=['업무_DB_있음', '업무_DB_꺼짐'])
def test_건강_검사는_연결_한_번에_설비와_거래_수를_세고_실패는_까닭과_함께_알린다(ent_dsn, dsn_ok):
    if dsn_ok:   # G2-20: 옛 판은 거래 300행만 읽어 300에서 잘린 수를 냈다 — 300건을 넘게 둔다
        sql(ent_dsn, "INSERT INTO ent.transactions(id, system, skill, ref, detail, asset, decision_id, fingerprint) SELECT 'TX-H-' || g, 'sys:cmms', "
                     "'skill:schedule-maintenance', 'WO-x', '건강 시험', 'HYD-01', 'DEC-H-' || g, 'x' FROM generate_series(1, 301) g ON CONFLICT DO NOTHING")
    dsn = ent_dsn if dsn_ok else 'postgresql://postgres:postgres@127.0.0.1:9/postgres'
    h = SupabaseEnterprise(lambda: psycopg.connect(dsn, connect_timeout=3)).health()
    if dsn_ok:
        assert h['ok'] is True and h['assets'] == 3 and h['transactions'] == sql(ent_dsn, 'SELECT count(*) FROM ent.transactions')[0][0]
    else:
        assert h['ok'] is False and h['error']
