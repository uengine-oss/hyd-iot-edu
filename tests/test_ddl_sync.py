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
    graph = [{'id': 'in:a', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 't', 'column': 'a', 'sqlType': 'integer', 'state': 'OK', 'live': 'integer'},
             {'id': 'in:b', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 't', 'column': 'b', 'sqlType': 'integer', 'state': None, 'live': None},
             {'id': 'in:c', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 't', 'column': 'c', 'sqlType': 'integer', 'state': 'OK', 'live': 'integer'}]
    writes = []
    def q(cypher, **params):
        if cypher is ddl_sync.PHYSICAL_Q:
            return graph
        writes.append(params['rows']); return [{'n': len(params['rows'])}]
    live = [('ent', 't', 'a', 'integer'), ('ent', 't', 'b', 'integer'), ('ent', 't', 'c', 'text')]       # c changed type, a/b unchanged
    report = ddl_sync.sync(q, lambda: _Conn(live))
    assert report['checked'] == 3 and report['states'] == {'OK': ['in:a', 'in:b'], 'TYPE_CHANGED': ['in:c']}
    assert [r['id'] for r in writes[0]] == ['in:b', 'in:c']          # in:b had no recorded state yet; in:a unchanged is not rewritten
    graph[1].update(state='OK', live='integer'); graph[2].update(state='TYPE_CHANGED', live='text'); writes.clear()
    assert ddl_sync.sync(q, lambda: _Conn(live))['changed'] == 0 and writes == []                       # idempotent poll


def test_agent_refuses_a_binding_the_ddl_sync_marked(monkeypatch):
    item = dict(id='in:x', variable='db_x', name='x', typeRef='number', source='sys:erp', sourceName='ERP', sourceKind='System',
                datasource='hyd-enterprise', catalog='postgres', schema='ent', table='fg_inventory', column='ship_eta',
                assetColumn='asset', sqlType='timestamptz', sourceState='MISSING', sourceLiveType=None)
    called = []
    monkeypatch.setattr(decide, 'read_physical', lambda *a: called.append(a) or 1, raising=False)
    facts, prov = decide.gather_facts([item], 'HYD-01', {}, None)
    assert facts['db_x'] is None and 'DDL 동기화' in prov[0]['error'] and 'MISSING' in prov[0]['error'] and not called
