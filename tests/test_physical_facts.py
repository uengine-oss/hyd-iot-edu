"""Physical InputData must be reread, never replaced by a cached/guessed fact."""
from copy import deepcopy

import pytest

from agentsvc import decide


INPUT = dict(id='input:new', variable='db_new', name='remaining (h)', typeRef='number',
             source='sys:mes', sourceName='MES', sourceKind='System',
             datasource='hyd-enterprise', catalog='postgres', schema='ent',
             table='new order', column='due "hours"', assetColumn='asset', sqlType='numeric(10,3)')


def test_physical_binding_is_not_dropped_or_overridden_by_known_value(monkeypatch):
    calls = []
    monkeypatch.setattr(decide, 'read_physical', lambda i, asset: (calls.append((i, asset)), '2.125')[1], raising=False)
    facts, rows = decide.gather_facts([INPUT], 'HYD-01', {'db_new': 999}, None)
    assert facts['db_new'] == '2.125'
    assert calls == [(INPUT, 'HYD-01')]
    assert rows[0]['binding']['column'] == 'due "hours"'


@pytest.mark.parametrize('strict', [False, True])
def test_physical_failure_clears_old_value(monkeypatch, strict):
    def fail(*args):
        raise ValueError('source row count is not one')
    monkeypatch.setattr(decide, 'read_physical', fail, raising=False)
    facts, rows = decide.gather_facts([INPUT], 'HYD-01', {'db_new': 999}, None, strict=strict)
    assert facts['db_new'] is None
    assert rows[0]['error'] == 'source row count is not one'


def test_ambiguous_variable_sources_are_unknown(monkeypatch):
    other = dict(INPUT, id='input:other', table='other')
    monkeypatch.setattr(decide, 'read_physical', lambda *args: 2, raising=False)
    facts, rows = decide.gather_facts([INPUT, other], 'HYD-01', {}, None)
    assert facts['db_new'] is None
    assert all('ambiguous' in row['error'] for row in rows)


def test_identical_projection_rows_do_not_create_ambiguity(monkeypatch):
    monkeypatch.setattr(decide, 'read_physical', lambda *args: 2, raising=False)
    facts, rows = decide.gather_facts([INPUT, deepcopy(INPUT)], 'HYD-01', {}, None)
    assert facts['db_new'] == 2


@pytest.mark.parametrize('value,kind', [('false','boolean'), (1,'boolean'), (False,'number'), ('0','number'), (float('nan'),'number'), ([1],'number')])
def test_physical_type_drift_is_unknown_instead_of_truthiness(value, kind):
    from agentsvc.tools.physical import scalar
    with pytest.raises(ValueError):
        scalar(value, kind)


def test_physical_scalar_preserves_precision_and_boolean_type():
    from decimal import Decimal
    from agentsvc.tools.physical import scalar
    assert scalar(Decimal('1234567890123456789.125'), 'number') == '1234567890123456789.125'
    assert scalar(False, 'boolean') is False
