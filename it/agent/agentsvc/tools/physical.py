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
                  'datasource', 'catalog', 'schema', 'table', 'column', 'assetColumn', 'sqlType')
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
        query = sql.SQL('select {} from {} where {} = %s limit 2').format(
            sql.Identifier(item['column']), sql.Identifier(item['schema'], item['table']),
            sql.Identifier(item['assetColumn']))
        rows = conn.execute(query, (asset,)).fetchall()
        if len(rows) != 1:
            raise ValueError('physical InputData source row count is not one')
        return scalar(rows[0][0], item.get('typeRef'))
