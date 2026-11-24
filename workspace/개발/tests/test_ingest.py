"""회사 DB 구조(DDL) 읽기(procsvc/ingest.py) — CREATE TABLE → 표 · 열, 미리보기 계획(출처 시스템 · 입력 데이터), 적재 계약 검사, 규칙 조건 → SQL.
실라버스 4회차 「업무 데이터 연결」 실습의 앞부분이다. 표본은 포털이 내주는 제공 파일 samples/legacy-plant-db.sql 과 짧은 DDL 이다."""

import pytest

from conftest import SAMPLES

from procsvc import ingest

LEGACY = (SAMPLES / 'legacy-plant-db.sql').read_text(encoding='utf-8')
SHORT = '''-- MES 생산 오더
CREATE TABLE mes.orders (
  id bigint PRIMARY KEY,
  asset text NOT NULL,       -- 설비
  due_at timestamptz,        -- 납기 일시
  qty integer,               -- 수량
  plant_id bigint REFERENCES plants(id),
  created_at timestamptz
);
COMMENT ON TABLE mes.orders IS 'MES: 생산 오더';
COMMENT ON COLUMN mes.orders.qty IS '주문 수량';
'''


def test_제공_옛_DB_파일은_표_셋과_열을_그대로_읽는다():
    tables = ingest.parse_ddl(LEGACY)
    assert [t.name for t in tables] == ['T_EQP00', 'T_EQP01', 'T_MNT10']
    eqp01 = tables[1]
    assert [c.name for c in eqp01.columns][:4] == ['SEQ_NO', 'EQP_CD', 'MSR_DTM', 'C_PRS_A']
    assert eqp01.columns[0].primary_key and not eqp01.columns[1].nullable


def test_열_주석_표_주석은_뜻으로_읽고_키_감사_열은_기본_선택에서_뺀다():
    [orders] = ingest.parse_ddl(SHORT)
    assert orders.comment == 'MES: 생산 오더' and orders.system_hint == ('sys:mes', 'MES')
    assert {c.name: c.comment for c in orders.columns}['qty'] == '주문 수량'
    assert ingest.default_selection([orders]) == {'mes.orders': ['asset', 'due_at', 'qty']}


@pytest.mark.parametrize('ddl, says', [
    ('CREATE TABLE a (x int); CREATE TABLE a (y int);', '중복 테이블'),
    ('CREATE TABLE a (x int, x text);', '중복 열'),
    ('CREATE TABLE db.s.a (x int);', '데이터베이스'),
    ("CREATE TABLE a (x int); COMMENT ON COLUMN a.nope IS '없음';", '주석 대상 열'),
])
def test_잘못된_DDL은_무엇이_잘못됐는지_말하며_거절한다(ddl, says):
    with pytest.raises(ValueError, match=says):
        ingest.parse_ddl(ddl)


@pytest.mark.parametrize('sql_type, ref', [
    ('integer', 'number'), ('numeric(6,1)', 'number'), ('double precision', 'number'), ('timestamptz', 'date'),
    ('boolean', 'boolean'), ('jsonb', 'object'), ('text[]', 'object'), ('interval', 'duration'), ('point', 'string'), ('varchar(10)', 'string'),
])
def test_열_형식은_규칙이_읽는_형으로_바꾼다(sql_type, ref):
    assert ingest.type_ref_of(sql_type) == ref


def test_미리보기_계획은_표마다_출처_시스템과_고른_열의_입력_데이터를_만든다():
    tables = ingest.parse_ddl(SHORT)
    plan = ingest.plan(tables, filename='orders.sql', batch='ingest:ddl:test', selection={'mes.orders': ['qty', 'due_at']})
    assert [s['id'] for s in plan['systems']] == ['sys:mes']
    by_column = {i['column']: i for i in plan['inputs']}
    assert by_column['qty']['typeRef'] == 'number' and by_column['qty']['assetColumn'] == 'asset'
    assert (by_column['due_at']['derive'], by_column['due_at']['typeRef']) == (ingest.DERIVE_HOURS, 'number')
    ingest.validate_plan(plan)


def test_학생이_고른_출처_시스템으로_표를_잇는다():
    tables = ingest.parse_ddl(LEGACY)
    plan = ingest.plan(tables, filename='legacy-plant-db.sql', batch='b', selection={'T_EQP01': ['C_TMP_O']}, systems={'T_EQP01': 'sys:cmms'})
    assert [(i['column'], i['system']) for i in plan['inputs']] == [('C_TMP_O', 'sys:cmms')]


def test_시스템을_알_수_없는_표는_확인하라고_경고한다():
    plan = ingest.plan(ingest.parse_ddl(LEGACY), filename='legacy-plant-db.sql', batch='b', selection={'T_EQP01': ['C_TMP_O']})
    assert plan['inputs'][0]['system'] == 'sys:db-hyd-enterprise' and any('T_EQP01' in w for w in plan['warnings'])
    assert '출처 시스템' in plan['warnings'][0] and 'sys:' not in plan['warnings'][0], '무엇을 확인하라는지 말하고 내부 id 를 내밀지 않는다'
    # 사람이 그 표의 출처 시스템을 고르면(같은 값이어도) 확인한 것이다 — 적재 뒤까지 「확인할 것」이 남았다
    picked = ingest.plan(ingest.parse_ddl(LEGACY), filename='legacy-plant-db.sql', batch='b', selection={'T_EQP01': ['C_TMP_O']},
                         systems={'T_EQP01': 'sys:db-hyd-enterprise'})
    assert picked['inputs'][0]['system'] == 'sys:db-hyd-enterprise' and not any('출처 시스템 표시' in w for w in picked['warnings'])
    assert picked['warnings'] == [ingest.no_asset_key('public."T_EQP01"')]          # 설비 식별 열이 없다는 것은 시스템을 골라도 여전히 사실이다(C8)


def test_설비별_값을_읽을_열은_설비_코드를_가리키는_외래_키이고_없으면_적재_전에_말한다():
    """C8(2026-11-22): 설비 열을 이름이 asset 일 때만 알아봐, 설비 열 이름이 다른 학생 표(equipment_id → assets(code))의 판단 입력이 데이터 원천의 묶어 보기에서
    말없이 빠졌다. 설비 표의 코드를 가리키는 외래 키 열이 그 열이고, 그런 열도 asset 열도 없으면 적재 전에 경고한다."""
    ddl = '''CREATE TABLE ent.wo (id bigint PRIMARY KEY, equipment_id varchar(10) REFERENCES ent.assets(code), hours numeric);
CREATE TABLE ent.readings (id bigint PRIMARY KEY, reading numeric);'''
    plan = ingest.plan(ingest.parse_ddl(ddl), filename='mine.sql', batch='b', selection={'ent.wo': ['hours'], 'ent.readings': ['reading']}, systems={'ent.wo': 'sys:cmms', 'ent.readings': 'sys:cmms'})
    by_column = {i['column']: i for i in plan['inputs']}
    assert by_column['hours']['assetColumn'] == 'equipment_id' and by_column['reading']['assetColumn'] is None
    assert plan['warnings'] == [ingest.no_asset_key('ent.readings')]
    ingest.validate_plan(plan)


def test_표_주석이_적은_시스템_이름은_알려진_여덟이_아니어도_그_시스템이_된다():
    """C18(2026-11-22): 표 주석 머리 「-- WMS: 창고」를 시스템으로 알아보지 못해 원천 연결 이름(sys:db-…)이 출처 시스템이 됐고, 화면에서 새 시스템 이름을 정할
    길이 없었다. 주석 머리의 대문자 낱말이 그 시스템이다(알려진 MES 등은 이미 있는 id 그대로). 표 이름으로 짐작하는 것은 알려진 이름만이다."""
    ddl = '''CREATE TABLE ent.stock (id bigint PRIMARY KEY, qty integer);
COMMENT ON TABLE ent.stock IS 'WMS: 창고 재고';
CREATE TABLE ent.mes_lots (id bigint PRIMARY KEY, qty integer);
CREATE TABLE ent.notes (id bigint PRIMARY KEY, qty integer);
COMMENT ON TABLE ent.notes IS '창고 메모';'''
    plan = ingest.plan(ingest.parse_ddl(ddl), filename='mine.sql', batch='b', selection={'ent.stock': ['qty'], 'ent.mes_lots': ['qty'], 'ent.notes': ['qty']})
    assert {i['table']: i['system'] for i in plan['inputs']} == {'stock': 'sys:wms', 'mes_lots': 'sys:mes', 'notes': 'sys:db-hyd-enterprise'}
    assert {s['id']: s['name'] for s in plan['systems']}['sys:wms'] == 'WMS'
    assert any(w.startswith('ent.notes: 파일에 출처 시스템 표시가 없어') for w in plan['warnings'])
    ingest.validate_plan(plan)


@pytest.mark.parametrize('kwargs, says', [
    (dict(selection={'nope': ['x']}), 'DDL에 없는 테이블'),
    (dict(selection={'mes.orders': ['qty', 'qty']}), '중복 선택'),
    (dict(selection={'mes.orders': ['ghost']}), 'DDL 에 없는 열'),
    (dict(datasource='bad name!'), '원천 연결'),
])
def test_미리보기에_없는_표_열_원천은_거절한다(kwargs, says):
    with pytest.raises(ValueError, match=says):
        ingest.plan(ingest.parse_ddl(SHORT), filename='o.sql', batch='b', **kwargs)


def _plan():
    return ingest.plan(ingest.parse_ddl(SHORT), filename='o.sql', batch='b', selection={'mes.orders': ['qty']})


@pytest.mark.parametrize('change, says', [
    (lambda p: p['inputs'][0].update(variable='db_other'), '다시 미리보기'),
    (lambda p: p['inputs'][0].update(system='sys:nope'), '다시 미리보기'),
    (lambda p: p['inputs'][0].update(extra=1), '허용되지 않은 입력'),
    (lambda p: p['systems'][0].update(zone='MOON'), '영역'),
    (lambda p: p['inputs'].append(dict(p['inputs'][0])), '중복 입력'),
    (lambda p: p['inputs'][0].update(derive=ingest.DERIVE_HOURS), '시각 열만'),
    (lambda p: p.update(batch=''), '배치'),
])
def test_적재_계약은_미리보기와_다른_식별자_칸을_받지_않는다(change, says):
    plan = _plan()
    change(plan)
    with pytest.raises(ValueError, match=says):
        ingest.validate_plan(plan)


def test_규칙_조건은_그_열의_원천_표에서_확인하는_SQL이_되고_그_SQL은_조건에_맞는_설비의_행만_낸다(scratch_db):
    """13B-9: 전에는 만든 SQL 의 글자 모양만 봤다 — 따옴표 · 시각 열 파생 · 매개변수 이름이 틀려 실행이 깨져도 통과했다. 실제 DB 에 그 표를 만들어 돌린다."""
    import psycopg
    plan = ingest.plan(ingest.parse_ddl(SHORT), filename='o.sql', batch='b', selection={'mes.orders': ['qty', 'due_at']})
    inputs = {i['variable']: i for i in plan['inputs']}
    qty, due = (next(i for i in plan['inputs'] if i['column'] == c) for c in ('qty', 'due_at'))
    out = ingest.tests_to_sql([{'variable': qty['variable'], 'operator': '>=', 'value': 10},
                               {'variable': due['variable'], 'operator': '<', 'value': 24},
                               {'variable': 'unknown', 'operator': '==', 'value': 1}], inputs)
    [query] = out['queries']
    assert query['params'] == {'asset': '<asset>', 'v0': 10, 'v1': 24} and out['unmapped'] == ['unknown']
    with psycopg.connect(scratch_db, autocommit=True) as db:
        db.execute('CREATE SCHEMA mes')
        db.execute('CREATE TABLE mes.orders (id bigint PRIMARY KEY, asset text NOT NULL, due_at timestamptz, qty integer)')
        db.execute("""INSERT INTO mes.orders VALUES (1, 'HYD-01', now() + interval '10 hours', 12),     -- 수량 · 납기 둘 다 맞음
                                                    (2, 'HYD-02', now() + interval '10 hours', 5),      -- 수량이 모자람
                                                    (3, 'HYD-03', now() + interval '50 hours', 12)""")  # 납기가 멀다

        def rows(asset):
            return db.execute(query['sql'], dict(query['params'], asset=asset)).fetchall()
        [hit] = rows('HYD-01')
        assert hit[0] == 'HYD-01' and hit[1] == 12 and 9 < float(hit[2]) <= 10          # 설비 · 수량 · 납기까지 남은 시간(파생 열)
        assert rows('HYD-02') == [] and rows('HYD-03') == [] and rows('HYD-09') == []


@pytest.mark.parametrize('test, says', [
    ({'operator': '~', 'value': 1}, '연산자'),
    ({'operator': '>', 'value': None}, 'NULL'),
    ({'operator': '==', 'value': [1, 2]}, '단일 값'),
])
def test_SQL로_옮길_수_없는_조건은_거절한다(test, says):
    plan = _plan()
    inputs = {i['variable']: i for i in plan['inputs']}
    with pytest.raises(ValueError, match=says):
        ingest.tests_to_sql([dict(test, variable=plan['inputs'][0]['variable'])], inputs)


def test_원천_식별자는_연결_DB_스키마_표_열로_정해진다():
    a = ingest.physical_identity('hyd-enterprise', 'postgres', 'mes', 'orders', 'qty')
    assert a == ingest.physical_identity('hyd-enterprise', 'postgres', 'mes', 'orders', 'qty')
    assert a != ingest.physical_identity('hyd-enterprise', 'postgres', 'mes', 'orders', 'qty2')
    with pytest.raises(ValueError, match='식별자'):
        ingest.physical_identity('hyd-enterprise', 'postgres', '', 'orders', 'qty')
