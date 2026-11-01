"""Read an explicit physical InputData binding; no name-based semantic inference.

One registered datasource, one ent relation, one asset column, exactly one row.
Joins, aggregates and LLM-generated SQL remain the separate enterprise MCP path.
"""
from datetime import date, datetime, time
from decimal import Decimal
import math
import os
from uuid import UUID

from psycopg import sql

from hydcommon.enterprise import reader_connection

BINDING_FIELDS = ('id', 'name', 'typeRef', 'source', 'represents', 'representsName',
                  'datasource', 'catalog', 'schema', 'table', 'column', 'assetColumn', 'sqlType', 'derive')
DERIVE_HOURS = 'hours_from_now'
PHYSICAL_FIELDS = ('datasource', 'catalog', 'schema', 'table', 'column', 'assetColumn', 'sqlType')


def is_physical(item):
    return any(item.get(key) is not None for key in PHYSICAL_FIELDS)


def binding(item):
    return {key: item.get(key) for key in BINDING_FIELDS}


def scalar(value, type_ref):
    if value is None:
        return None
    valid = {'boolean': type(value) is bool,
             'number': type(value) in (int, float, Decimal),
             'string': isinstance(value, (str, UUID)),
             'date': isinstance(value, (datetime, date, time))}
    if not valid.get(type_ref, False):
        raise ValueError(f'업무 DB 값의 형식({type(value).__name__})이 지식에 선언한 형식({type_ref})과 다릅니다')
    if value is None or type(value) in (bool, int, str):
        return value
    if isinstance(value, Decimal):
        if value.is_finite():
            return str(value)  # JSON-safe and preserves DB numeric precision.
    elif isinstance(value, float):
        if math.isfinite(value):
            return value
    elif isinstance(value, (datetime, date, time)):
        return value.isoformat()
    elif isinstance(value, UUID):
        return str(value)
    raise ValueError('업무 DB 값이 유한한 단일 값이 아닙니다')


def read_physical(item, asset):
    return read_physical_fact(item, asset)[0]


def read_physical_fact(item, asset):
    """(value, anchor). A point-in-time column declared derive=hours_from_now (A086) is read as signed hours from now;
    the anchor is the stored time itself — the business record a consent compares, while the hours keep moving."""
    derive = item.get('derive')
    if derive not in (None, DERIVE_HOURS):
        raise ValueError(f'지식에 선언한 값 변환({derive})을 엔진이 지원하지 않습니다')
    if item.get('datasource') != 'hyd-enterprise' or item.get('schema') != 'ent':
        raise ValueError('지식에 선언한 업무 DB 출처(데이터 원본 · 스키마)가 등록된 것(hyd-enterprise · ent)이 아닙니다')
    for key in ('catalog', 'table', 'column', 'assetColumn'):
        if not isinstance(item.get(key), str) or not item[key] or '\x00' in item[key]:
            raise ValueError(f'지식의 업무 DB 출처에 {key} 칸이 없습니다')
    if not isinstance(asset, str) or not asset:
        raise ValueError('업무 DB 값을 읽을 설비가 정해지지 않았습니다')
    dsn = os.getenv('ENTERPRISE_READ_DSN')
    if not dsn:
        raise ValueError('업무 DB 읽기 연결(ENTERPRISE_READ_DSN)이 설정되지 않았습니다 — 시작.bat 으로 다시 켜세요')
    with reader_connection(dsn) as conn:
        conn.execute('set transaction read only')
        conn.execute("set local statement_timeout='3000ms'")
        conn.execute("set local lock_timeout='1000ms'")
        if conn.execute('select current_database()').fetchone()[0] != item['catalog']:
            raise ValueError('지식에 선언한 업무 DB 이름이 연결된 DB와 다릅니다')
        column = sql.Identifier(item['column'])
        # 남은 시간은 값의 형식을 먼저 본 뒤 여기서 계산한다 — DB 식으로 빼면 시각이 아닌 칸에서 DB 영어 오류가 한국어 까닭보다 먼저 나왔다
        query = sql.SQL('select {}, now(), localtimestamp from {} where {} = %s limit 2').format(
            column, sql.Identifier(item['schema'], item['table']), sql.Identifier(item['assetColumn']))
        rows = conn.execute(query, (asset,)).fetchall()
        if len(rows) != 1:
            raise ValueError(f'업무 DB {item["schema"]}.{item["table"]}에서 이 설비의 행이 정확히 하나가 아닙니다({len(rows)}개 — 2개 이상이면 2)')
        raw, now, local_now = rows[0]
        if derive:
            if raw is not None and not isinstance(raw, datetime):
                raise ValueError('남은 시간으로 바꿀 칸이 시각 칸이 아닙니다')
            derived = None if raw is None else round((raw - (now if raw.tzinfo else local_now)).total_seconds() / 3600, 2)
            return scalar(derived, item.get('typeRef')), scalar(raw, 'date')
        return scalar(raw, item.get('typeRef')), None
