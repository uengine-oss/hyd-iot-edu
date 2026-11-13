"""업무 시스템 읽기(agentsvc.tools.mcp_ent.fetch) — 읽기가 실패하면 값 없음이 아니라 그 자리의 까닭(SourceUnavailable)으로 실패한다(검진 H-8).

업무 시스템 자리는 둘이다.
  실제 enterprise-sim(stack — 우리 코드, 테스트 업무 DB): 정상 읽기 · 없는 설비(404) · 답하지 않는 동안(서비스 프로세스를 얼린다).
  이 PC 의 작은 HTTP 서버(바깥 네트워크 대체 — Upstream): 실제 서비스로 만들 수 없는 응답(5xx 본문 · JSON 이 아닌 본문 · 객체가 아닌 본문 ·
  닫힌 포트 · 늦은 503).
mcp_ent 는 가져올 때 ENTERPRISE_URL 을 읽는다 — 테스트마다 그 주소를 준 환경에서 모듈 파일을 새로 읽는다(그 주소로 agent 를 켠 것과 같다).
"""
import importlib.util
import json
import socket
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg
import pytest

from conftest import ROOT

MODULE = ROOT / 'it' / 'agent' / 'agentsvc' / 'tools' / 'mcp_ent.py'


def load(url):
    """ENTERPRISE_URL=url 로 켠 agent 의 mcp_ent(이 프로세스의 다른 테스트가 쓰는 모듈은 그대로 둔다)."""
    spec = importlib.util.spec_from_file_location(f'mcp_ent_{uuid.uuid4().hex[:8]}', MODULE)
    module = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('ENTERPRISE_URL', url)
        spec.loader.exec_module(module)
    return module


def body(value):
    return json.dumps(value, ensure_ascii=False).encode()


class Upstream:
    """업무 시스템 자리의 HTTP 서버: 받은 요청 경로를 남기고 reply=(상태, 본문 bytes, 늦춤)로 답한다.
    늦춤: 0 = 바로, 초 = 그만큼 뒤에(업무 DB 연결 한도를 기다린 enterprise-sim 처럼), None = 끝날 때까지 답하지 않음."""

    def __init__(self):
        upstream, self.requests, self.reply, self.release = self, [], (200, b'{}', 0), threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                upstream.requests.append(self.path)
                status, data, hold = upstream.reply
                if hold is None:
                    upstream.release.wait()
                    return
                if hold:
                    upstream.release.wait(hold)
                self.send_response(status)
                self.send_header('content-type', 'application/json')
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def upstream():
    server = Upstream()
    yield server
    server.close()


@pytest.fixture
def ent(upstream):
    return load(upstream.url)


def test_업무_시스템의_객체_응답을_그대로_돌려주고_설비_값은_경로에_따옴표로_싣는다(upstream, ent):
    upstream.reply = (200, body({'system': 'MES', 'facts': {'due_in_h': 3.4}}), 0)
    assert ent.fetch('/mes/orders?asset={asset}', 'HYD-01&part=P-X') == {'system': 'MES', 'facts': {'due_in_h': 3.4}}
    assert upstream.requests == ['/mes/orders?asset=HYD-01%26part%3DP-X']        # 설비 값이 다른 질의 인자를 끼워 넣지 못한다


@pytest.mark.parametrize('endpoint, asset', [
    ('mes/orders?asset={asset}', 'HYD-01'),
    ('/mes/../admin?asset={asset}', 'HYD-01'),
    ('/mes/orders?asset={asset}', '../../admin'),
], ids=['앞의 / 없음', '경로에 ..', '설비 값으로 경로 벗어나기'])
def test_정해진_업무_시스템_경로_밖은_요청을_보내지_않고_거절한다(upstream, ent, endpoint, asset):
    with pytest.raises(ValueError, match='업무 시스템 읽기 경로가 허용되지 않습니다'):
        ent.fetch(endpoint, asset)
    assert upstream.requests == []


@pytest.mark.parametrize('status, data, says, retry', [
    (503, body({'detail': '업무 DB에 연결하지 못했습니다 — 잠시 뒤 다시 시도하세요: connection timeout'}), ' — 업무 DB에 연결하지 못했습니다 — 잠시 뒤 다시 시도하세요: connection timeout', False),
    (500, b'Internal Server Error', ' — Internal Server Error', True),
    (502, b'', '', True),
    (404, body({'detail': 'MES 에 그 대상의 자료가 없습니다(asset=HYD-09)'}), ' — MES 에 그 대상의 자료가 없습니다(asset=HYD-09)', False),
    (422, body({'detail': [{'loc': ['query', 'asset'], 'msg': '필수 값'}]}), ' — [{"loc": ["query", "asset"], "msg": "필수 값"}]', False),
], ids=['503 업무 DB 끊김', '500 글자 본문', '502 빈 본문', '404 없는 대상', '422 구조 있는 까닭'])
def test_업무_시스템이_오류로_답하면_상태와_까닭을_실은_SourceUnavailable_로_실패하고_5xx_만_다시_시도를_권한다(upstream, ent, status, data, says, retry):
    upstream.reply = (status, data, 0)
    with pytest.raises(ent.SourceUnavailable) as failed:
        ent.fetch('/mes/orders?asset={asset}', 'HYD-01')
    assert failed.value.status == status
    assert str(failed.value) == f'업무 시스템 /mes/orders을(를) 읽지 못했습니다(HTTP {status}){says}.' + (' 잠시 뒤 다시 시도하세요.' if retry else '')


def test_긴_오류_까닭은_300자로_자른다(upstream, ent):
    upstream.reply = (503, body({'detail': '가' * 1000}), 0)
    with pytest.raises(ent.SourceUnavailable) as failed:
        ent.fetch('/erp/contract?asset={asset}', 'HYD-01')
    assert '가' * 300 in str(failed.value) and '가' * 301 not in str(failed.value)


@pytest.mark.parametrize('data, phrase', [
    (b'<html>maintenance</html>', '업무 시스템 /cmms/history의 응답이 JSON 이 아닙니다.'),
    (b'', '업무 시스템 /cmms/history의 응답이 JSON 이 아닙니다.'),
    (body([{'wo': 'WO-1'}]), '업무 시스템 /cmms/history의 응답이 객체가 아닙니다.'),
    (b'null', '업무 시스템 /cmms/history의 응답이 객체가 아닙니다.'),
], ids=['HTML', '빈 본문', 'JSON 목록', 'JSON null'])
def test_200_이어도_객체_JSON_이_아니면_값_없음이_아니라_까닭으로_실패한다(upstream, ent, data, phrase):
    upstream.reply = (200, data, 0)
    with pytest.raises(ent.SourceUnavailable) as failed:
        ent.fetch('/cmms/history?asset={asset}', 'HYD-01')
    assert (str(failed.value), failed.value.status) == (phrase, None)


def test_업무_시스템에_닿지_못하면_서비스를_다시_켜라는_까닭으로_실패한다():
    with socket.socket() as s:                                   # 아무도 듣지 않는 포트
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    ent = load(f'http://127.0.0.1:{port}')
    with pytest.raises(ent.SourceUnavailable) as failed:
        ent.fetch('/mes/orders?asset={asset}', 'HYD-01')
    message = str(failed.value)
    assert message.startswith('업무 시스템 /mes/orders에 닿지 못했습니다(') and message.endswith('— 시작.bat 으로 서비스를 다시 켠 뒤 다시 시도하세요.')
    assert failed.value.status is None


def test_업무_시스템이_한도_안에_답하지_않으면_기다린_시간을_말하고_실패한다(upstream, ent):
    upstream.reply = (200, b'{}', None)
    started = time.monotonic()
    with pytest.raises(ent.SourceUnavailable) as failed:
        ent.fetch('/qms/lots?asset={asset}', 'HYD-01', timeout=0.5)
    assert time.monotonic() - started < 5
    assert str(failed.value) == '업무 시스템 /qms/lots이(가) 0.5초 안에 답하지 않았습니다 — 업무 시스템 · 업무 DB 연결을 확인하고 잠시 뒤 다시 시도하세요.'
    assert failed.value.status is None


def test_기본_한도는_enterprise_sim_이_업무_DB_연결을_5초_기다린_뒤_내는_까닭을_받을_만큼_길다(upstream, ent):
    """enterprise-sim 은 읽기마다 업무 DB 연결을 5초 한도로 연다 — 끊긴 동안 그 5초가 지난 뒤 503 까닭을 낸다. 이쪽이 먼저 끊으면 「응답 없음」만 남는다."""
    upstream.reply = (503, body({'detail': '업무 DB에 연결하지 못했습니다 — 잠시 뒤 다시 시도하세요: timeout expired'}), 5.5)
    with pytest.raises(ent.SourceUnavailable) as failed:
        ent.fetch('/mes/orders?asset={asset}', 'HYD-01')
    assert failed.value.status == 503 and '업무 DB에 연결하지 못했습니다' in str(failed.value)


# ---------------------------------------------------------------- 실제 enterprise-sim(우리 코드 · 테스트 업무 DB)
@pytest.fixture
def real(stack):
    return load(stack.ent)


def test_실제_업무_시스템에서_설비의_MES_생산오더를_업무_DB_기록_그대로_읽는다(real, stack):
    out = real.fetch('/mes/orders?asset={asset}', 'HYD-01')
    with psycopg.connect(stack.dsn) as db:
        (due_at, order_id), = db.execute('SELECT due_at, order_id FROM ent.production_orders WHERE asset = %s', ('HYD-01',)).fetchall()
    assert out['system'] == 'MES' and out['facts']['order_id'] == order_id
    assert datetime.fromisoformat(out['facts']['due_at']) == due_at


def test_실제_업무_시스템에_없는_설비는_404_까닭으로_실패하고_다시_시도를_권하지_않는다(real):
    with pytest.raises(real.SourceUnavailable) as failed:
        real.fetch('/mes/orders?asset={asset}', 'HYD-09')
    assert failed.value.status == 404
    assert '그 대상의 자료가 없습니다(asset=HYD-09)' in str(failed.value) and '잠시 뒤 다시 시도하세요' not in str(failed.value)


def test_실제_업무_시스템이_멈춰_답하지_않으면_한도에서_까닭과_함께_실패한다(real, stack):
    with stack.services['enterprise-sim'].paused():
        with pytest.raises(real.SourceUnavailable) as failed:
            real.fetch('/erp/contract?asset={asset}', 'HYD-01', timeout=1)
    assert '1초 안에 답하지 않았습니다' in str(failed.value) and failed.value.status is None
