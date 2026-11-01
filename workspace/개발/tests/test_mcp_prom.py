"""데이터 신선도 검사(agentsvc.tools.mcp_prom.freshness) — 추론 전에 설비 값을 믿을 수 있는지(시계열의 최신 유온 나이 + 수집기 상태).

시계열은 실제 timescaledb(test_mcp_tsdb 와 같은 agent 읽기 — 읽기 전용 계정), 설비 값은 테스트마다 다른 설비 이름으로 넣는다.
수집기(connect-ingest)의 /healthz 는 이 PC 의 작은 HTTP 서버로 대체한다 — 진짜 수집기는 MQTT · Kafka 브로커가 있어야 켜지고 테스트 묶음은
브로커를 띄우지 않는다(conftest 머리말). mcp_prom 은 가져올 때 INGEST_URL 을 읽으므로 그 주소를 준 환경에서 모듈 파일을 새로 읽는다.
"""
import importlib.util
import json
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import ROOT
from test_mcp_tsdb import put, tsdb, tsdb_module  # noqa: F401 — 같은 시계열 읽기 준비(픽스처)

MODULE = ROOT / 'it' / 'agent' / 'agentsvc' / 'tools' / 'mcp_prom.py'
OK = (200, b'{"ok": true, "mqtt": true, "kafka": true}', 0)


def load(url):
    spec = importlib.util.spec_from_file_location(f'mcp_prom_{uuid.uuid4().hex[:8]}', MODULE)
    module = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('INGEST_URL', url)
        spec.loader.exec_module(module)
    return module


class Ingest:
    """수집기 /healthz 자리: reply=(상태, 본문, 늦춤 — None 이면 끝날 때까지 답하지 않음)."""

    def __init__(self):
        ingest, self.reply, self.release = self, OK, threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, data, hold = ingest.reply
                if hold is None:
                    ingest.release.wait()
                    return
                self.send_response(status)
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/healthz'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def ingest():
    server = Ingest()
    yield server
    server.close()


@pytest.fixture
def prom(ingest):
    return load(ingest.url)


@pytest.fixture
def asset():
    return f'T-{uuid.uuid4().hex[:8]}'


STALE = '초 전 것입니다(허용 60초) — 설비 시뮬레이터와 수집이 도는지 확인하세요'
AHEAD = '앞서 있습니다(허용 2초) — PC 시계를 확인하세요'
MISSING = '이 설비의 유온(TS1) 값이 시계열 DB에 없습니다'
INGEST = '설비 데이터 수집기(connect-ingest)가 정상이 아니라 최신 설비 값을 믿을 수 없습니다'


@pytest.mark.parametrize('rows, low, high, ok, reason', [
    ([('TS1', 45.0, 0)], 0, 1, True, None),
    ([('TS1', 45.0, 59)], 59, 60, True, None),
    ([('TS1', 45.0, 61)], 61, 63, False, STALE),
    ([('TS1', 45.0, -1)], -1, 0, True, None),
    ([('TS1', 45.0, -3)], -3, -2, False, AHEAD),
    ([('TS1', 40.0, 300), ('TS1', 45.0, 1)], 1, 2, True, None),
    ([], None, None, False, MISSING),
    ([('TS2', 45.0, 0)], None, None, False, MISSING),
], ids=['막 들어온 값', '59초 전은 믿는다', '61초 전은 낡았다', '1초 앞선 값은 시계 오차로 받는다', '3초 앞선 값은 시계 결함',
        '가장 새 값으로 잰다', '값 없음', '유온이 아닌 태그만'])
def test_유온_최신_값이_60초_안이고_2초보다_앞서지_않을_때만_믿는다(prom, tsdb, timescale, asset, rows, low, high, ok, reason):
    put(timescale, asset, rows)
    out = prom.freshness(tsdb, asset)
    assert (out['ok'], out['max_age_s'], out['max_skew_s']) == (ok, 60.0, 2.0)
    assert out['reason'] is None if reason is None else reason in out['reason']
    if low is None:
        assert (out['age_s'], out['latest_ts1']) == (None, None)
    else:
        assert low <= out['age_s'] < high and out['latest_ts1'] == 45.0


@pytest.mark.parametrize('reply, error', [
    ((200, b'{"ok": false, "mqtt": false}', 0), None),
    ((200, b'{"ok": "true"}', 0), None),
    ((200, b'starting', 0), 'JSONDecodeError'),
    ((503, b'{"ok": false}', 0), 'HTTPError'),
], ids=['수집기가 비정상이라고 답함', 'ok 가 참거짓이 아님', 'JSON 이 아닌 답', '503'])
def test_수집기가_정상이라고_답하지_않으면_값이_새로워도_믿지_않는다(prom, ingest, tsdb, timescale, asset, reply, error):
    ingest.reply = reply
    put(timescale, asset, [('TS1', 45.0, 0)])
    out = prom.freshness(tsdb, asset)
    assert (out['ok'], out['reason']) == (False, INGEST)
    assert out['ingest'].get('error') == error


def test_수집기와_값이_함께_나쁘면_수집기_까닭을_먼저_말한다(prom, ingest, tsdb, timescale, asset):
    ingest.reply = (200, b'{"ok": false}', 0)
    put(timescale, asset, [('TS1', 45.0, 120)])
    assert prom.freshness(tsdb, asset)['reason'] == INGEST


def test_수집기에_닿지_못하면_그_까닭의_종류를_남기고_믿지_않는다(tsdb, timescale, asset):
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    put(timescale, asset, [('TS1', 45.0, 0)])
    out = load(f'http://127.0.0.1:{port}/healthz').freshness(tsdb, asset)
    assert (out['ok'], out['ingest'], out['reason']) == (False, {'ok': False, 'error': 'URLError'}, INGEST)


def test_수집기가_답하지_않아도_신선도_검사는_3초_한도_안에_끝난다(prom, ingest, tsdb, timescale, asset):
    ingest.reply = (200, b'', None)
    put(timescale, asset, [('TS1', 45.0, 0)])
    started = time.monotonic()
    out = prom.freshness(tsdb, asset)
    assert time.monotonic() - started < 6
    assert (out['ok'], out['ingest']['error'], out['reason']) == (False, 'TimeoutError', INGEST)
