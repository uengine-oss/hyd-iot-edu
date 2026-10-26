from types import SimpleNamespace

import pytest
from agentsvc.tools.mcp_tsdb import TimeSeriesDB
from agentsvc.tools.prometheus import Prometheus
from dmn_mcp.tools import enveloped
from enterprise_mcp.tools import EnterpriseTools, guarded
from test_enterprise_mcp import FakeConn, D
from test_prometheus_query import response


@pytest.mark.parametrize('cell', ['한글' * 15000, list(range(12000)), {'nested': ['x' * 30000]}], ids=['text', 'array', 'nested'])
@pytest.mark.parametrize('source', ['enterprise', 'timeseries'])
def test_one_aggregate_cell_cannot_escape_row_limit(monkeypatch, cell, source):
    conn = FakeConn([], [(cell,)], [D('aggregate')])
    if source == 'enterprise':
        result = guarded(EnterpriseTools(lambda: conn).query)('select array_agg(code) from assets')
    else:
        db = TimeSeriesDB()
        monkeypatch.setattr(db, '_conn', lambda: conn)
        result = enveloped(lambda: db.query('select array_agg(time) from tag_1s'))()
    assert result['result'] == 'error' and result['error_kind'] == 'INVALID'
    assert '20000' in result['message'] and len(str(result)) < 1000


def test_enterprise_row_boundary_is_visible_without_inventing_more_rows():
    db = EnterpriseTools(lambda: FakeConn([], [(1,)] * 200, [D('count')]))
    result = db.query('select 1')['document']
    assert result['row_limit'] == 200 and result['at_row_limit'] is True
    assert result['row_count'] == len(result['rows']) == 200


def test_prometheus_under_point_limit_can_still_exceed_character_limit(monkeypatch):
    body = dict(status='success', data=dict(resultType='matrix', result=[
        dict(metric={'job': 'a'}, values=[[i, '0.1234567890123456'] for i in range(1800)])]))
    response(monkeypatch, body)
    result = enveloped(lambda: Prometheus().query('up', start=0, end=600, step=1))()
    assert result['error_kind'] == 'INVALID' and 'step' in result['message']


def test_large_labels_also_count(monkeypatch):
    response(monkeypatch, dict(status='success', data=[{'label': 'x' * 21000}]))
    result = enveloped(lambda: Prometheus().series('up'))()
    assert result['error_kind'] == 'INVALID'


@pytest.mark.parametrize('tool', ['tradeoffs', 'fabric'])
def test_graph_paths_and_federated_cells_are_bounded(tool):
    from dmn_mcp.tools import DmnTools
    huge = [{'value': '값' * 30000}]
    db = DmnTools(kg=SimpleNamespace(tradeoffs=lambda ids: huge),
                  fabric=SimpleNamespace(query=lambda *args: huge))
    call = (lambda: db.tradeoffs(['skill:a'])) if tool == 'tradeoffs' else (lambda: db.fabric_query('HYD-01'))
    result = enveloped(call)()
    assert result['error_kind'] == 'INVALID' and len(str(result)) < 1000
