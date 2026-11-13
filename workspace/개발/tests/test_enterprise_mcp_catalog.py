"""업무 표 메타데이터의 쪽 나누기 · DDL 글(it/enterprise-mcp/enterprise_mcp/catalog.py) — 실제 업무 DB 카탈로그로."""
import pytest
import sqlglot
from sqlglot import exp

from enterprise_mcp.catalog import page, render
from enterprise_mcp.tools import EnterpriseTools
from hydcommon.enterprise import reader_connection
from conftest import ent_reader


@pytest.fixture(scope='module')
def catalog(pg_dsn):
    dsn = ent_reader(pg_dsn)
    return EnterpriseTools(lambda: reader_connection(dsn)).describe_catalog()['document']


@pytest.mark.parametrize('offset, limit', [(0, 1), (0, 20), (5, 12)])
def test_표_목록은_쪽마다_limit개이고_다음_쪽_자리를_알려준다(catalog, offset, limit):
    total = len(catalog['relations'])
    out = page(catalog, None, offset, limit)
    assert len(out['relations']) == min(limit, total - offset) and out['total'] == total
    assert out['next_offset'] == (offset + limit if offset + limit < total else None)


@pytest.mark.parametrize('table', ['spare_stock', 'ent.spare_stock'], ids=['이름', '스키마_붙은_이름'])
def test_표_하나는_열과_제약을_한_줄로_세어_쪽으로_준다(catalog, table):
    relation = next(r for r in catalog['relations'] if r['name'] == 'spare_stock')
    out = page(catalog, table, 0, 20)
    assert out['table'] == 'spare_stock' and out['total'] == len(relation['columns']) + len(relation['constraints'])


@pytest.mark.parametrize('table, offset, limit', [('없는표', 0, 12), (None, -1, 12), (None, 0, 0), (None, 0, 21)],
                         ids=['없는_표', '음수_offset', 'limit_0', 'limit_21'])
def test_없는_표나_범위_밖_쪽은_ValueError다(catalog, table, offset, limit):
    with pytest.raises(ValueError):
        page(catalog, table, offset, limit)


def test_DDL_글은_표마다_실제_열을_그대로_적은_create_table이다(catalog):
    """render 글을 SQL 파서(sqlglot)로 다시 읽어 표 · 열이 카탈로그와 같은지 본다(보기는 주석 한 줄이라 표에 없다)."""
    tables = {}
    for statement in sqlglot.parse(render(catalog), read='postgres'):
        if isinstance(statement, exp.Create) and statement.kind == 'TABLE':
            schema = statement.this
            tables[schema.this.name] = [c.name for c in schema.expressions if isinstance(c, exp.ColumnDef)]
    expected = {r['name']: [c['name'] for c in r['columns']] for r in catalog['relations'] if r['kind'] in ('r', 'p')}
    assert tables == expected
