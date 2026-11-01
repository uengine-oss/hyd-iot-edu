"""물리 입력 읽기(agentsvc.tools.physical) — 지식에 선언한 업무 DB 출처(데이터 원본 · 스키마 · 표 · 칸 · 설비 칸) 하나에서 그 설비의 한 행을 읽는다.

업무 DB 는 실제 테스트 DB(pg_dsn — 마이그레이션 전부 + seed.sql), 읽기 계정은 agent 가 compose 에서 받는 ENTERPRISE_READ_DSN 그대로
(hyd_enterprise_reader, 주소만 이 PC). 기댓값은 같은 행을 관리자 연결로 따로 읽어 정한다.
"""
import math
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import UUID

import psycopg
import pytest

from agentsvc.tools import physical
from conftest import _compose_default, _compose_service, here


@pytest.fixture
def db(pg_dsn, monkeypatch):
    """agent 가 받는 업무 DB 읽기 주소(compose agent environment 의 ENTERPRISE_READ_DSN, 주소만 이 PC) → 테스트 DB 이름."""
    monkeypatch.setenv('ENTERPRISE_READ_DSN', here(_compose_default(_compose_service('agent')['environment']['ENTERPRISE_READ_DSN'])))
    return urlsplit(pg_dsn).path.lstrip('/')


def admin(pg_dsn, sql, *args):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        return conn.execute(sql, args).fetchall()


def item(db, table, column, type_ref, **over):
    """t3_inputs 가 내는 물리 입력 한 줄의 꼴(지식에 선언한 출처). over 의 칸이 이긴다."""
    out = dict(id=f'in:test-{column}', name='시험 입력', typeRef=type_ref, datasource='hyd-enterprise', catalog=db, schema='ent',
               table=table, column=column, assetColumn='asset', sqlType=None, derive=None)
    out.update(over)
    return out


@pytest.mark.parametrize('given, physical_input', [
    ({'id': 'in:x', 'source': 'sys:cmms'}, False),
    ({'id': 'in:x', 'table': None, 'column': None}, False),
    ({'id': 'in:x', 'table': 'pm_counters'}, True),
    ({'id': 'in:x', 'sqlType': 'numeric'}, True),
], ids=['출처 시스템만', '물리 칸이 모두 비어 있음', '표 칸 하나', '열 형식 칸 하나'])
def test_물리_출처_칸이_하나라도_있으면_물리_입력이다(given, physical_input):
    assert physical.is_physical(given) is physical_input


def test_판단_기록의_입력_묶음은_정해진_칸만_싣고_없는_칸은_비워_둔다():
    out = physical.binding({'id': 'in:x', 'table': 'pm_counters', 'secret': 'x', 'value': 3})
    assert list(out) == list(physical.BINDING_FIELDS)
    assert (out['id'], out['table'], out['column']) == ('in:x', 'pm_counters', None)


UUID_X = UUID('12345678-1234-5678-1234-567812345678')
AT = datetime(2026, 10, 30, 1, 2, 3, tzinfo=timezone.utc)


@pytest.mark.parametrize('value, type_ref, out', [
    (None, 'number', None),
    (True, 'boolean', True),
    (3, 'number', 3),
    (2.5, 'number', 2.5),
    (Decimal('1200.50'), 'number', '1200.50'),
    ('RUNNING', 'string', 'RUNNING'),
    (UUID_X, 'string', str(UUID_X)),
    (AT, 'date', '2026-10-30T01:02:03+00:00'),
    (date(2026, 10, 30), 'date', '2026-10-30'),
    (time(1, 2), 'date', '01:02:00'),
], ids=['없음은 없음', '참거짓', '정수', '소수', 'DB numeric 은 자릿수 그대로 글자로', '글자', 'UUID 는 글자로', '시각', '날짜', '시각(시분)'])
def test_업무_DB_값은_선언한_형식이면_JSON_으로_옮길_수_있는_값으로_바꾼다(value, type_ref, out):
    assert physical.scalar(value, type_ref) == out


@pytest.mark.parametrize('value, type_ref, phrase', [
    (True, 'number', '형식(bool)이 지식에 선언한 형식(number)과 다릅니다'),
    (1, 'boolean', '형식(int)이 지식에 선언한 형식(boolean)과 다릅니다'),
    ('3', 'number', '형식(str)이 지식에 선언한 형식(number)과 다릅니다'),
    (3, 'string', '형식(int)이 지식에 선언한 형식(string)과 다릅니다'),
    (3, 'decimal', '형식(int)이 지식에 선언한 형식(decimal)과 다릅니다'),
    (3, None, '형식(int)이 지식에 선언한 형식(None)과 다릅니다'),
    ([1], 'number', '형식(list)이 지식에 선언한 형식(number)과 다릅니다'),
    (float('nan'), 'number', '유한한 단일 값이 아닙니다'),
    (float('inf'), 'number', '유한한 단일 값이 아닙니다'),
    (Decimal('NaN'), 'number', '유한한 단일 값이 아닙니다'),
    (Decimal('-Infinity'), 'number', '유한한 단일 값이 아닙니다'),
], ids=['참거짓은 수가 아니다', '정수는 참거짓이 아니다', '글자 숫자는 수가 아니다', '수는 글자가 아니다', '모르는 형식', '형식 선언 없음',
        '목록', 'NaN', '무한', 'DB NaN', 'DB 음의 무한'])
def test_업무_DB_값이_선언한_형식과_다르거나_유한한_값이_아니면_까닭과_함께_실패한다(value, type_ref, phrase):
    with pytest.raises(ValueError, match=phrase.replace('(', r'\(').replace(')', r'\)')):
        physical.scalar(value, type_ref)


@pytest.mark.parametrize('table, column, type_ref, convert', [
    ('pm_counters', 'since_pm_h', 'number', str),
    ('production_orders', 'remaining_qty', 'number', None),
    ('production_orders', 'status', 'string', None),
    ('maintenance_profiles', 'standby_ready', 'boolean', None),
    ('production_orders', 'due_at', 'date', datetime.isoformat),
], ids=['numeric 은 자릿수 그대로', '정수', '글자', '참거짓', '시각은 ISO 글자'])
def test_선언한_업무_DB_칸에서_그_설비의_한_행_값을_읽는다(db, pg_dsn, table, column, type_ref, convert):
    (want,), = admin(pg_dsn, f'SELECT {column} FROM ent.{table} WHERE asset = %s', 'HYD-01')
    want = convert(want) if convert else want
    binding = item(db, table, column, type_ref)
    assert physical.read_physical(binding, 'HYD-01') == want
    assert physical.read_physical_fact(binding, 'HYD-01') == (want, None)


def test_시각_칸을_남은_시간으로_바꾸면_지금부터의_부호_있는_시간과_저장된_시각을_함께_낸다(db, pg_dsn):
    (due_at,), = admin(pg_dsn, "SELECT due_at FROM ent.production_orders WHERE asset = %s", 'HYD-01')
    hours, anchor = physical.read_physical_fact(item(db, 'production_orders', 'due_at', 'number', derive='hours_from_now'), 'HYD-01')
    assert anchor == due_at.isoformat()
    assert abs(float(hours) - (due_at - datetime.now(timezone.utc)).total_seconds() / 3600) < 0.02
    assert isinstance(hours, float) and math.isfinite(hours)          # 글자가 아니라 유한한 수(자릿수는 구현 몫 — 값은 위 줄이 판정)


def test_남은_시간으로_바꿀_시각_칸이_비어_있으면_값도_기준_시각도_없다(db, pg_dsn):
    assert admin(pg_dsn, "SELECT last_done_at FROM ent.pm_counters WHERE asset = %s", 'HYD-01') == [(None,)]   # 시드: 정비 완료 기록 없음
    assert physical.read_physical_fact(item(db, 'pm_counters', 'last_done_at', 'number', derive='hours_from_now'), 'HYD-01') == (None, None)


@pytest.mark.parametrize('over, asset, phrase', [
    ({'derive': 'days_from_now'}, 'HYD-01', '값 변환(days_from_now)을 엔진이 지원하지 않습니다'),
    ({'datasource': 'other-db'}, 'HYD-01', '등록된 것(hyd-enterprise · ent)이 아닙니다'),
    ({'schema': 'public'}, 'HYD-01', '등록된 것(hyd-enterprise · ent)이 아닙니다'),
    ({'catalog': ''}, 'HYD-01', 'catalog 칸이 없습니다'),
    ({'table': None}, 'HYD-01', 'table 칸이 없습니다'),
    ({'column': 'since\x00pm'}, 'HYD-01', 'column 칸이 없습니다'),
    ({'assetColumn': 3}, 'HYD-01', 'assetColumn 칸이 없습니다'),
    ({}, '', '설비가 정해지지 않았습니다'),
    ({}, None, '설비가 정해지지 않았습니다'),
], ids=['모르는 값 변환', '등록 안 된 데이터 원본', '등록 안 된 스키마', 'DB 이름 없음', '표 없음', '열 이름에 NUL', '설비 칸이 글자가 아님',
        '빈 설비', '설비 없음'])
def test_지식의_출처_선언이_모자라거나_등록_밖이면_업무_DB_에_닿기_전에_까닭과_함께_실패한다(db, over, asset, phrase):
    binding = item(db, 'pm_counters', 'since_pm_h', 'number')
    binding.update(over)
    with pytest.raises(ValueError, match=phrase.replace('(', r'\(').replace(')', r'\)')):
        physical.read_physical(binding, asset)


def test_업무_DB_읽기_주소가_없으면_시작_파일로_다시_켜라는_까닭과_함께_실패한다(db, monkeypatch):
    monkeypatch.delenv('ENTERPRISE_READ_DSN')
    with pytest.raises(ValueError, match=r'업무 DB 읽기 연결\(ENTERPRISE_READ_DSN\)이 설정되지 않았습니다 — 시작.bat'):
        physical.read_physical(item(db, 'pm_counters', 'since_pm_h', 'number'), 'HYD-01')


def test_전용_읽기_계정이_아닌_연결로는_읽지_않는다(db, pg_dsn, monkeypatch):
    monkeypatch.setenv('ENTERPRISE_READ_DSN', pg_dsn)                 # 관리자(postgres) 계정
    with pytest.raises(RuntimeError, match='hyd_enterprise_reader required: this connection is postgres'):
        physical.read_physical(item(db, 'pm_counters', 'since_pm_h', 'number'), 'HYD-01')


@pytest.mark.parametrize('table, column, asset, over, phrase', [
    ('pm_counters', 'since_pm_h', 'HYD-01', {'catalog': 'postgres'}, '지식에 선언한 업무 DB 이름이 연결된 DB와 다릅니다'),
    ('pm_counters', 'since_pm_h', 'HYD-09', {}, 'ent.pm_counters에서 이 설비의 행이 정확히 하나가 아닙니다(0개'),
    ('maintenance_history', 'task', 'HYD-01', {}, 'ent.maintenance_history에서 이 설비의 행이 정확히 하나가 아닙니다(2개 — 2개 이상이면 2)'),
    ('pm_counters', 'since_pm_h', 'HYD-01', {'typeRef': 'boolean'}, '형식(Decimal)이 지식에 선언한 형식(boolean)과 다릅니다'),
], ids=['다른 DB 이름', '그 설비의 행 없음', '그 설비의 행 여럿', '선언과 다른 값 형식'])
def test_업무_DB_의_실제_행이_선언과_맞지_않으면_값을_고르지_않고_실패한다(db, pg_dsn, table, column, asset, over, phrase):
    if table == 'maintenance_history':
        assert admin(pg_dsn, 'SELECT count(*) FROM ent.maintenance_history WHERE asset = %s', asset)[0][0] >= 2   # 시드: 정비 이력 여럿
    with pytest.raises(ValueError, match=phrase.replace('(', r'\(').replace(')', r'\)')):
        physical.read_physical_fact(item(db, table, column, over.get('typeRef', 'number'),
                                         **{k: v for k, v in over.items() if k != 'typeRef'}), asset)


@pytest.mark.parametrize('table, column', [('production_orders', 'status'), ('pm_counters', 'since_pm_h')], ids=['글자 칸', '수 칸'])
def test_시각이_아닌_칸을_남은_시간으로_바꾸려_하면_그_까닭으로_실패한다(db, table, column):
    """지식(DDL 적재)은 시각 칸만 남은 시간으로 선언한다 — 업무 DB 의 칸이 그 뒤 바뀌어 시각이 아니게 되면 읽는 쪽이 그 까닭을 말해야 한다."""
    with pytest.raises(ValueError, match='남은 시간으로 바꿀 칸이 시각 칸이 아닙니다'):
        physical.read_physical_fact(item(db, table, column, 'number', derive='hours_from_now'), 'HYD-01')


def test_따옴표를_섞은_열_이름은_이름으로만_읽혀_업무_DB_를_바꾸지_못한다(db, pg_dsn):
    before = admin(pg_dsn, 'SELECT count(*) FROM ent.assets')
    with pytest.raises(psycopg.errors.UndefinedColumn):
        physical.read_physical(item(db, 'assets', 'name" from ent.assets; delete from ent.assets; --', 'string', assetColumn='code'), 'HYD-01')
    assert admin(pg_dsn, 'SELECT count(*) FROM ent.assets') == before and before[0][0] >= 3


def test_업무_표가_잠겨_있으면_1초_잠금_한도로_곧_실패한다(db, pg_dsn):
    import time as clock
    holder = psycopg.connect(pg_dsn)                                   # 다른 거래가 표 전체를 잠근 동안(정비 계수기 갱신 같은)
    try:
        holder.execute('LOCK TABLE ent.pm_counters IN ACCESS EXCLUSIVE MODE')
        started = clock.monotonic()
        with pytest.raises(psycopg.errors.LockNotAvailable):
            physical.read_physical(item(db, 'pm_counters', 'since_pm_h', 'number'), 'HYD-01')
        assert clock.monotonic() - started < 2.5                        # 문장 한도(3초)보다 먼저 — 판단이 잠금에 매달리지 않는다
    finally:
        holder.rollback()
        holder.close()
