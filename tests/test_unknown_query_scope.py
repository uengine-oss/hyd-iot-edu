from types import SimpleNamespace

import pytest
from dmn_mcp.tools import DmnTools, enveloped
from enterprise_mcp.tools import EnterpriseTools, guarded
from test_enterprise_mcp import FakeConn


@pytest.mark.parametrize('kind', ['rules', 'precedents', 'tradeoffs'])
@pytest.mark.parametrize('exists', [False, True])
def test_existing_subject_without_matches_differs_from_unknown_subject(kind, exists):
    kg = SimpleNamespace(dmn=lambda: [], precedents=lambda x: [], tradeoffs=lambda x: [])
    tool = DmnTools(kg=kg)
    tool._graph = lambda query, **params: [{'id': 'target'}] if exists else []
    call = {'rules': lambda: tool.dmn_rules('target'),
            'precedents': lambda: tool.precedents('target'),
            'tradeoffs': lambda: tool.tradeoffs(['target'])}[kind]
    result = enveloped(call)()
    assert result['result'] == ('ok' if exists else 'error')
    if not exists:
        assert result['error_kind'] == 'INVALID' and 'target' in result['message']


def test_unknown_enterprise_asset_is_not_a_successful_empty_read():
    log = []
    tool = EnterpriseTools(lambda: FakeConn(log, [(False,)]))
    result = guarded(tool.read)('mes_orders', asset='HYD-missing')
    assert result['error_kind'] == 'INVALID'
    assert not any('ent.mes_orders(' in sql for sql, _ in log)
