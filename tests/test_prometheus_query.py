import io
import json
import urllib.error
import urllib.parse

import pytest

from agentsvc.tools.prometheus import Prometheus
from dmn_mcp.tools import enveloped


def response(monkeypatch, body, status=200):
    seen = []
    def open_url(url, timeout):
        seen.append((url, timeout))
        raw = io.BytesIO(json.dumps(body).encode())
        if status != 200:
            raise urllib.error.HTTPError(url, status, 'test', {}, raw)
        return raw
    monkeypatch.setattr('urllib.request.urlopen', open_url)
    return seen


def test_scalar_zero_nan_empty_and_warnings_are_preserved(monkeypatch):
    client = Prometheus('http://source:9090')
    for kind, value in [('scalar', [123, '0']), ('scalar', [123, 'NaN']), ('vector', [])]:
        seen = response(monkeypatch, dict(status='success', data=dict(resultType=kind, result=value), warnings=['partial'], infos=['annotation']))
        result = client.query('sum(up)', at=123)
        assert result['data']['result'] == value
        assert result['empty'] == (kind == 'vector')
        assert result['warnings'] == ['partial'] and result['infos'] == ['annotation']
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0][0]).query)
        assert params == {'query': ['sum(up)'], 'time': ['123.0'], 'timeout': ['5s']}


@pytest.mark.parametrize('status,kind,expected', [(400, 'bad_data', 'INVALID'), (422, 'execution', 'INVALID'), (503, 'timeout', 'UNKNOWN'), (500, 'internal', 'UNKNOWN')])
def test_source_failure_classification(monkeypatch, status, kind, expected):
    response(monkeypatch, dict(status='error', errorType=kind, error='observed error'), status)
    result = enveloped(lambda: Prometheus().query('up'))()
    assert result['error_kind'] == expected and 'observed error' in result['message']


@pytest.mark.parametrize('body', [[], {}, {'status': 'success'}, {'status': 'success', 'data': {}}, {'status': 'success', 'data': {'resultType': 'matrix', 'result': ['bad']}}])
def test_malformed_source_is_unknown_not_bad_user_query(monkeypatch, body):
    response(monkeypatch, body)
    assert enveloped(lambda: Prometheus().query('up'))()['error_kind'] == 'UNKNOWN'


@pytest.mark.parametrize('params', [dict(start=1), dict(start=1, end=2), dict(start=1, end=2, step=0), dict(start=2, end=1, step=1), dict(start=0, end=90000, step=100), dict(start=0, end=1100, step=1), dict(start=0, end=2, step=1e-309), dict(at=float('nan')), dict(at=True), dict(at=1, start=1, end=2, step=1)])
def test_invalid_ranges_do_not_call_source(monkeypatch, params):
    def unexpected(*a, **kw):pytest.fail('invalid request reached source')
    monkeypatch.setattr('urllib.request.urlopen', unexpected)
    assert enveloped(lambda: Prometheus().query('up', **params))()['error_kind'] == 'INVALID'


def test_range_bounds_and_encoded_expression(monkeypatch):
    seen = response(monkeypatch, dict(status='success', data=dict(resultType='matrix', result=[])))
    expr = 'sum by (job) (rate(requests_total{job="a&b"}[5m]))'
    result = Prometheus().query(expr, start=100, end=120, step=10)
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0][0]).query)
    assert '/query_range?' in seen[0][0] and params['query'] == [expr]
    assert result['parameters']['step'] == 10 and result['series_count'] == 0


def test_response_limits_reject_partial_query_and_catalog_marks_partial(monkeypatch):
    response(monkeypatch, dict(status='success', data=dict(resultType='vector', result=[dict(metric={}, value=[1, '1'])] * 201)))
    assert enveloped(lambda: Prometheus().query('up'))()['error_kind'] == 'INVALID'
    response(monkeypatch, dict(status='success', data={f'm{i}': [] for i in range(201)}))
    catalog = Prometheus().metadata()
    assert catalog['truncated'] and len(catalog['data']) == 200
    response(monkeypatch, dict(status='success', data=dict(resultType='matrix', result=[dict(metric={}, values=[[1, '1']] * 20001)])))
    assert enveloped(lambda: Prometheus().query('up[1d]'))()['error_kind'] == 'INVALID'


def test_series_requires_both_bounds_and_preserves_labels(monkeypatch):
    seen = response(monkeypatch, dict(status='success', data=[dict(__name__='up', job='process', instance='process:8080')]))
    result = Prometheus().series('up{job="process"}', start=1, end=2)
    assert result['data'][0]['job'] == 'process' and result['series_count'] == 1
    assert 'match%5B%5D=' in seen[0][0]
    assert enveloped(lambda: Prometheus().series('up', start=1))()['error_kind'] == 'INVALID'
