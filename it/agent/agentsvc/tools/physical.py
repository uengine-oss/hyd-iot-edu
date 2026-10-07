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
        raise ValueError('physical InputData value type does not match its declared typeRef')
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
    raise ValueError('physical InputData requires a finite scalar value')


def read_physical(item, asset):
    return read_physical_fact(item, asset)[0]


def read_physical_fact(item, asset):
    """(value, anchor). A point-in-time column declared derive=hours_from_now (A086) is read as signed hours from now;
    the anchor is the stored time itself — the business record a consent compares, while the hours keep moving."""
    derive = item.get('derive')
    if derive not in (None, DERIVE_HOURS):
        raise ValueError('physical InputData derivation is not supported')
    if item.get('datasource') != 'hyd-enterprise' or item.get('schema') != 'ent':
        raise ValueError('physical InputData datasource/schema is not registered')
    for key in ('catalog', 'table', 'column', 'assetColumn'):
        if not isinstance(item.get(key), str) or not item[key] or '\x00' in item[key]:
            raise ValueError(f'physical InputData requires explicit {key}')
    if not isinstance(asset, str) or not asset:
        raise ValueError('physical InputData requires an asset')
    dsn = os.getenv('ENTERPRISE_READ_DSN')
    if not dsn:
        raise ValueError('physical InputData reader is not configured')
    with reader_connection(dsn) as conn:
        conn.execute('set transaction read only')
        conn.execute("set local statement_timeout='3000ms'")
        conn.execute("set local lock_timeout='1000ms'")
        if conn.execute('select current_database()').fetchone()[0] != item['catalog']:
            raise ValueError('physical InputData catalog does not match the connected database')
        column = sql.Identifier(item['column'])
        hours = sql.SQL('round((extract(epoch from ({} - now())) / 3600)::numeric, 2)').format(column) if derive else sql.SQL('null')
        query = sql.SQL('select {}, {} from {} where {} = %s limit 2').format(
            column, hours, sql.Identifier(item['schema'], item['table']), sql.Identifier(item['assetColumn']))
        rows = conn.execute(query, (asset,)).fetchall()
        if len(rows) != 1:
            raise ValueError('physical InputData source row count is not one')
        raw, derived = rows[0]
        if derive:
            if raw is not None and not isinstance(raw, datetime):
                raise ValueError('hours_from_now needs a point-in-time column')
            return scalar(derived, item.get('typeRef')), scalar(raw, 'date')
        return scalar(raw, item.get('typeRef')), None
