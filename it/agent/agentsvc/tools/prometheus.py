"""Read-only Prometheus API. Metadata is observed, never inferred from sensor tags.

Keep this separate from mcp_prom.freshness (Timescale + ingest health).
Supports the deployed Prometheus 2.55 API, including servers without query limit.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 2_000_000
MAX_SERIES = 200
MAX_POINTS = 20_000
MAX_WINDOW = 86400


class SourceError(RuntimeError):
    """Source unavailable or invalid response; not a successful empty query."""


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite Unix timestamp/seconds number')
    return float(value)


def window(start, end):
    start, end = number(start, 'start'), number(end, 'end')
    if start > end or end - start > MAX_WINDOW:
        raise ValueError('start <= end and window <= 86400 seconds required')
    return start, end


class Prometheus:
    def __init__(self, url=None):
        self.url = (url or os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')).rstrip('/')

    def _get(self, endpoint, params):
        # Only internal constant read endpoints are passed here. No caller URL/path.
        url = self.url + '/api/v1/' + endpoint + '?' + urllib.parse.urlencode(params)
        status = 200
        try:
            response = urllib.request.urlopen(url, timeout=8)
        except urllib.error.HTTPError as exc:
            response, status = exc, exc.code
        except (OSError, urllib.error.URLError) as exc:
            raise SourceError(f'Prometheus unavailable: {type(exc).__name__}') from exc
        with response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Prometheus response exceeds 2 MB; narrow the query/selector')
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise SourceError(f'Prometheus returned non-JSON (HTTP {status})') from exc
        if not isinstance(body, dict) or body.get('status') not in ('success', 'error'):
            raise SourceError('Invalid Prometheus response envelope')
        if status != 200 or body['status'] == 'error':
            kind = body.get('errorType', 'unknown')
            message = f"Prometheus {kind}: {str(body.get('error', 'request failed'))[:250]}"
            if status in (400, 422) and kind in ('bad_data', 'execution'):
                raise ValueError(message)
            raise SourceError(message)
        if 'data' not in body:
            raise SourceError('Prometheus response has no data')
        return body

    @staticmethod
    def _document(body, **fields):
        return dict(source='hyd-prometheus', dialect='promql', **fields,
                    data=body['data'], warnings=body.get('warnings', []), infos=body.get('infos', []))

    def metadata(self, metric=None):
        if metric is not None and (not isinstance(metric, str) or not metric.strip() or len(metric) > 512):
            raise ValueError('metric must be a nonempty exact metric name <= 512 characters')
        params = {'limit': MAX_SERIES + 1}
        if metric is not None:
            params['metric'] = metric
        body = self._get('metadata', params)
        if not isinstance(body['data'], dict):
            raise SourceError('Invalid metric metadata')
        # Discovery may be partial; make this explicit instead of claiming absence.
        truncated = len(body['data']) > MAX_SERIES
        body['data'] = dict(list(body['data'].items())[:MAX_SERIES])
        return self._document(body, metric=metric, truncated=truncated,
                              note='Scraped metric HELP/type/unit; missing metadata does not prove missing series. Use series discovery, including for generated metrics such as up.')

    def series(self, selector, start=None, end=None):
        self._expression(selector)
        if (start is None) != (end is None):
            raise ValueError('Provide both start and end, or neither')
        end = time.time() if end is None else end
        start = end - 300 if start is None else start
        start, end = window(start, end)
        body = self._get('series', {'match[]': selector, 'start': start, 'end': end})
        data = body['data']
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise SourceError('Invalid series metadata')
        if len(data) > MAX_SERIES:
            raise ValueError('More than 200 series; narrow the selector')
        return self._document(body, selector=selector, start=start, end=end,
                              series_count=len(data), note='Labels identify series; presence does not guarantee samples in this window. Query values and timestamps separately.')

    @staticmethod
    def _expression(expression):
        if not isinstance(expression, str) or not expression.strip() or len(expression) > 16000:
            raise ValueError('PromQL/selector must be nonempty and <= 16000 characters')

    def query(self, expression, at=None, start=None, end=None, step=None):
        self._expression(expression)
        params = {'query': expression, 'timeout': '5s'}
        ranged = any(x is not None for x in (start, end, step))
        if ranged:
            if at is not None or any(x is None for x in (start, end, step)):
                raise ValueError('Range requires start/end/step and no at')
            start, end = window(start, end)
            step = number(step, 'step')
            if step <= 0 or (end - start) / step >= 1100:
                raise ValueError('Positive step and <= 1100 evaluation points per series required')
            params.update(start=start, end=end, step=step)
        else:
            params['time'] = time.time() if at is None else number(at, 'at')
        body = self._get('query_range' if ranged else 'query', params)
        data = body['data']
        if not isinstance(data, dict) or data.get('resultType') not in ('vector', 'matrix', 'scalar', 'string') or not isinstance(data.get('result'), list):
            raise SourceError('Invalid Prometheus query result')
        result = data['result']
        series_count = None
        if data['resultType'] in ('vector', 'matrix'):
            series_count = len(result)
            if any(not isinstance(row, dict) for row in result):
                raise SourceError('Invalid series result')
            points = sum(len(row.get('values', [])) + len(row.get('histograms', [])) if data['resultType'] == 'matrix' else 1 for row in result)
            if series_count > MAX_SERIES or points > MAX_POINTS:
                raise ValueError('Result exceeds 200 series or 20000 points; narrow query/window or increase step')
        return self._document(body, expression=expression, parameters=params,
                              series_count=series_count, empty=not result,
                              note='Evaluation timestamps are not necessarily source sample times. Check timestamp(), observation coverage and gaps for sustained conditions. NaN/Inf strings are preserved.')
