import pytest
from procsvc import ingest


def test_physical_identity_does_not_merge_sources_or_schemas():
    tables = ingest.parse_ddl('CREATE TABLE east.orders (asset text, value numeric); CREATE TABLE west.orders (asset text, value numeric);')
    first = ingest.plan(tables, filename='x.sql', batch='one', datasource='factory_a', catalog='postgres')
    second = ingest.plan(tables, filename='x.sql', batch='two', datasource='factory_b', catalog='postgres')
    again = ingest.plan(tables, filename='renamed.sql', batch='three', datasource='factory_a', catalog='postgres')
    all_inputs = first['inputs'] + second['inputs']
    assert len({i['id'] for i in all_inputs}) == len(all_inputs)
    assert len({i['variable'] for i in all_inputs}) == len(all_inputs)
    assert [i['id'] for i in first['inputs']] == [i['id'] for i in again['inputs']]
    assert first['inputs'][0]['source_id'] != again['inputs'][0]['source_id']


def test_exact_empty_selection_and_invalid_columns():
    tables = ingest.parse_ddl('CREATE TABLE east.orders (value numeric); CREATE TABLE west.orders (value numeric);')
    assert ingest.plan(tables, filename='x', batch='b', selection={'east.orders': [], 'west.orders': ['value']})['inputs'][0]['schema'] == 'west'
    with pytest.raises(ValueError, match='모호'):
        ingest.plan(tables, filename='x', batch='b', selection={'orders': ['value']})
    with pytest.raises(ValueError, match='없는 열'):
        ingest.plan(tables, filename='x', batch='b', selection={'east.orders': ['nope']})


def test_postgres_quoted_identifiers_and_literals_are_preserved():
    table, = ingest.parse_ddl('CREATE TABLE "East Bay"."Order.Items" (asset text, "Net,Value" numeric(10,2), note text default \'a,b;--z\');')
    assert table.schema == 'East Bay' and table.name == 'Order.Items'
    assert [c.name for c in table.columns] == ['asset', 'Net,Value', 'note']
    assert table.columns[-1].default == "'a,b;--z'"
    p = ingest.plan([table], filename='x', batch='b')
    inp = next(i for i in p['inputs'] if i['column'] == 'Net,Value')
    out = ingest.tests_to_sql([{'variable': inp['variable'], 'operator': '<', 'value': 8}], {inp['variable']: inp})
    assert '"East Bay"."Order.Items"' in out['queries'][0]['sql']
    assert '"Net,Value" < %(v0)s' in out['queries'][0]['sql']
    assert out['queries'][0]['params']['v0'] == 8


def test_sql_rejects_unknown_operator_and_keeps_source_partition():
    sources = {'a': {'datasource': 'a', 'catalog': 'db', 'schema': 's', 'table': 't', 'column': 'v'},
               'b': {'datasource': 'b', 'catalog': 'db', 'schema': 's', 'table': 't', 'column': 'v'}}
    rows = [{'variable': v, 'operator': '<', 'value': 3} for v in sources]
    out = ingest.tests_to_sql(rows, sources)
    assert len(out['queries']) == 2
    assert {q['datasource'] for q in out['queries']} == {'a', 'b'}
    with pytest.raises(ValueError, match='연산자'):
        ingest.tests_to_sql([{'variable': 'a', 'operator': '> 0; DROP TABLE t;--', 'value': 3}], sources)
