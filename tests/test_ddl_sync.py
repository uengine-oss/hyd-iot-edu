"""A087 (DoD 4): a business DDL change reaches the ontology — physical inputs whose column vanished or changed its meaning
are marked, and the agent never reads them (process-gpt-strategy ontology_sync: poll, apply the difference, no dangling link)."""
import pytest

from agentsvc import decide
from procsvc import ddl_sync


@pytest.mark.parametrize('declared,live,state', [
    ('numeric', 'integer', 'OK'),                                   # same meaning class (number)
    ('timestamptz', 'timestamp with time zone', 'OK'),
    ('integer', 'text', 'TYPE_CHANGED'),                            # a number became text
    ('timestamptz', 'numeric', 'TYPE_CHANGED'),                     # a point in time became a number
    ('numeric', None, 'MISSING'),                                   # the column is gone
])
def test_drift_states(declared, live, state):
    inputs = [{'id': 'in:x', 'schema': 'ent', 'table': 't', 'column': 'c', 'sqlType': declared}]
    columns = {} if live is None else {('ent', 't', 'c'): live}
    assert ddl_sync.drift(inputs, columns)[0]['state'] == state


class _Conn:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return self
    def execute(self, sql, params=None): self.params = params
    def fetchall(self): return self.rows


def test_sync_writes_only_the_inputs_whose_state_changed():
    graph = [{'id': 'in:a', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 't', 'column': 'a', 'sqlType': 'integer', 'state': 'OK', 'live': 'integer', 'baseComment': ''},
             {'id': 'in:b', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 't', 'column': 'b', 'sqlType': 'integer', 'state': None, 'live': None},
             {'id': 'in:c', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 't', 'column': 'c', 'sqlType': 'integer', 'state': 'OK', 'live': 'integer', 'baseComment': ''}]
    writes = []
    def q(cypher, **params):
        if cypher is ddl_sync.PHYSICAL_Q:
            return graph
        writes.append(params['rows']); return [{'n': len(params['rows'])}]
    live = [('ent', 't', 'a', 'integer', None), ('ent', 't', 'b', 'integer', None), ('ent', 't', 'c', 'text', None)]       # c changed type, a/b unchanged
    report = ddl_sync.sync(q, lambda: _Conn(live))
    assert report['checked'] == 3 and report['states'] == {'OK': ['in:a', 'in:b'], 'TYPE_CHANGED': ['in:c']}
    assert [r['id'] for r in writes[0]] == ['in:b', 'in:c']          # in:b had no recorded state yet; in:a unchanged is not rewritten
    graph[1].update(state='OK', live='integer', baseComment=''); graph[2].update(state='TYPE_CHANGED', live='text'); writes.clear()
    assert ddl_sync.sync(q, lambda: _Conn(live))['changed'] == 0 and writes == []                       # idempotent poll


def test_agent_refuses_a_binding_the_ddl_sync_marked(monkeypatch):
    item = dict(id='in:x', variable='db_x', name='x', typeRef='number', source='sys:erp', sourceName='ERP', sourceKind='System',
                datasource='hyd-enterprise', catalog='postgres', schema='ent', table='fg_inventory', column='ship_eta',
                assetColumn='asset', sqlType='timestamptz', sourceState='MISSING', sourceLiveType=None)
    called = []
    monkeypatch.setattr(decide, 'read_physical', lambda *a: called.append(a) or 1, raising=False)
    facts, prov = decide.gather_facts([item], 'HYD-01', {}, None)
    assert facts['db_x'] is None and 'DDL 동기화' in prov[0]['error'] and 'MISSING' in prov[0]['error'] and not called


def _row(base, live_comment, *, sql_type='integer', live_type='integer'):
    inputs = [{'id': 'in:x', 'schema': 'ent', 'table': 'fg_inventory', 'column': 'fg_stock', 'sqlType': sql_type,
               'baseComment': base}]
    return ddl_sync.drift(inputs, {('ent', 'fg_inventory', 'fg_stock'): (live_type, live_comment)})[0]


@pytest.mark.parametrize('base,live_comment,state,new_base', [
    (None, None, 'OK', ''),                         # first sync after ingestion: record "no comment" as the baseline
    (None, '완제품 재고 수량', 'OK', '완제품 재고 수량'),
    ('', None, 'OK', ''),
    ('완제품 재고 수량', '완제품 재고 수량', 'OK', '완제품 재고 수량'),
    ('완제품 재고 수량', '가용 재고 수량', 'COMMENT_CHANGED', '완제품 재고 수량'),   # only the meaning changed
    ('', '가용 재고 수량', 'COMMENT_CHANGED', ''),                                  # a comment appeared later
    ('완제품 재고 수량', None, 'COMMENT_CHANGED', '완제품 재고 수량'),              # the comment was dropped
])
def test_comment_change_is_measured_against_the_first_live_comment(base, live_comment, state, new_base):
    """A115 (r14 A10): with only the comment changed, the type family is the same and the binding stayed OK with the old
    meaning. The baseline is the live comment the first sync saw — not the reviewed DDL file, whose data-dictionary
    comment the database may never have had (live probe a115/ddl-drift-1 blocked a matching column that way)."""
    row = _row(base, live_comment)
    assert row['state'] == state and row['base'] == new_base and row['comment'] == live_comment


def test_type_change_outranks_a_comment_change():
    assert _row('수량', '다른 뜻', live_type='text')['state'] == 'TYPE_CHANGED'


def test_sync_records_the_baseline_once_and_marks_a_later_comment_change():
    graph = [{'id': 'in:a', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 't', 'column': 'a', 'sqlType': 'integer',
              'state': None, 'live': None, 'liveComment': None, 'baseComment': None}]
    writes = []
    def q(cypher, **params):
        if cypher is ddl_sync.PHYSICAL_Q:
            return graph
        writes.append(params['rows']); return [{'n': len(params['rows'])}]
    report = ddl_sync.sync(q, lambda: _Conn([('ent', 't', 'a', 'integer', None)]))
    assert report['states'] == {'OK': ['in:a']}
    assert writes[0] == [{'id': 'in:a', 'state': 'OK', 'live': 'integer', 'comment': None, 'base': ''}]
    graph[0].update(state='OK', live='integer', baseComment=''); writes.clear()
    assert ddl_sync.sync(q, lambda: _Conn([('ent', 't', 'a', 'integer', None)]))['changed'] == 0 and writes == []
    report = ddl_sync.sync(q, lambda: _Conn([('ent', 't', 'a', 'integer', '가용 재고 수량')]))
    assert report['states'] == {'COMMENT_CHANGED': ['in:a']}
    assert writes[0] == [{'id': 'in:a', 'state': 'COMMENT_CHANGED', 'live': 'integer', 'comment': '가용 재고 수량', 'base': ''}]
    graph[0].update(state='COMMENT_CHANGED', liveComment='가용 재고 수량'); writes.clear()
    assert ddl_sync.sync(q, lambda: _Conn([('ent', 't', 'a', 'integer', '가용 재고 수량')]))['changed'] == 0   # stays marked


def test_reingestion_clears_the_comment_baseline():
    """The reviewed re-ingestion is the new meaning: graph_ingest._claim removes sourceBaseComment."""
    import inspect
    from procsvc import graph_ingest
    assert 'REMOVE n.sourceBaseComment' in inspect.getsource(graph_ingest._claim)
    assert 'sourceBaseComment' in graph_ingest.SYNC_FIELDS


@pytest.mark.parametrize('sql_type,ref', [
    ('interval', 'duration'), ('INTERVAL DAY TO SECOND', 'duration'), ('point', 'string'),      # contained "int" → number
    ('integer', 'number'), ('BIGINT', 'number'), ('DECIMAL(10, 2)', 'number'), ('double precision', 'number'),
    ('integer[]', 'object'), ('ARRAY', 'object'), ('jsonb', 'object'),
    ('timestamptz', 'date'), ('timestamp(3) with time zone', 'date'), ('time without time zone', 'date'),
    ('VARCHAR(20)', 'string'), ('uuid', 'string'), ('USER-DEFINED', 'string'), ('boolean', 'boolean'),
])
def test_type_ref_is_matched_on_the_base_type_name(sql_type, ref):
    from procsvc.ingest import type_ref_of
    assert type_ref_of(sql_type) == ref


def test_drift_of_interval_versus_integer_is_a_type_change():
    inputs = [{'id': 'in:x', 'schema': 'ent', 'table': 't', 'column': 'c', 'sqlType': 'integer'}]
    assert ddl_sync.drift(inputs, {('ent', 't', 'c'): 'interval'})[0]['state'] == 'TYPE_CHANGED'
