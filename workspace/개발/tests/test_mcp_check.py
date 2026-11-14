"""MCP 연결 검사 · 써 보기 클라이언트(procsvc/mcp_check.py) — 학생이 등록한 바깥 도구 서버에 붙는 자리.

바깥 서버(학생 · 강사가 띄운 MCP 서버)만 이 PC 의 작은 서버로 대체한다: 정상 FastMCP 서버, 조금씩 보내는 서버, 큰 줄을 보내는 서버.
검사기 · 읽기 판정 · 시간 · 크기 상한 · 비밀값 가림은 실제 코드다.
"""
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import Served
from procsvc import mcp_check


# ---------------------------------------------------------------- 바깥 서버 자리
def _fastmcp_server():
    from fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    app = FastMCP('학생 서버')

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_rows(limit: int) -> dict:
        """표에서 행을 찾는다"""
        return {'rows': [{'n': i} for i in range(limit)]}

    @app.tool(annotations=ToolAnnotations(readOnlyHint=False))
    def save_row(text: str) -> dict:
        """행을 저장한다"""
        return {'saved': text}
    return Served(app.http_app(path='/mcp'))


@pytest.fixture(scope='module')
def student_server():
    served = _fastmcp_server()
    yield {'transport': 'streamable_http', 'type': 'url', 'url': served.url + '/mcp', 'headers': {}}
    served.close()


class _RawServer:
    """POST 마다 SSE 스트림으로 답하는 서버. body(write) 가 무엇을 언제 보낼지 정한다."""

    def __init__(self, body):
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers.get('content-length') or 0))
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Connection', 'close')
                self.end_headers()
                try:
                    body(self.wfile)
                except OSError:
                    pass                       # 받는 쪽이 끊었다 — 검사기가 상한에서 멈춘 것

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/mcp'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


def _drip(wfile):
    """1초에 한 번 「: ping」만 — 답은 끝내 보내지 않는다(느리거나 잘못 만든 서버)."""
    for _ in range(30):
        wfile.write(b': ping\n')
        wfile.flush()
        time.sleep(1)


def _huge_line(wfile):
    """빈 줄 없이 1 MB data 줄을 계속 — 한 이벤트가 상한(2 MB)을 넘는다."""
    chunk = b'data: ' + b'x' * 1_000_000 + b'\n'
    for _ in range(60):
        wfile.write(chunk)
        wfile.flush()


# ---------------------------------------------------------------- 설정 형식
@pytest.mark.parametrize('spec, says', [
    ({'command': 'python', 'args': ['-c', 'import os']}, '명령형(stdio) 서버는 포털에 등록하지 않습니다'),
    ({'transport': 'stdio', 'url': 'http://x/mcp'}, '명령형(stdio) 서버는 포털에 등록하지 않습니다'),
    ({'url': 'http://169.254.169.254/latest/meta-data'}, '링크로컬'),
    ({'url': 'http://[fe80::1]:8080/mcp'}, '링크로컬'),
    ({'url': 'http://0.0.0.0:8080/mcp'}, '링크로컬'),
    ({'url': 'http://2852039166/latest/meta-data'}, '링크로컬'),           # 169.254.169.254 의 10진 표기
    ({'url': 'http://0251.0376.0251.0376/mcp'}, '링크로컬'),               # 같은 주소의 8진 표기
    ({'url': 'http://0/mcp'}, '링크로컬'),                                 # 0.0.0.0
    ({'url': 'http://[::ffff:169.254.169.254]/mcp'}, '링크로컬'),          # IPv6 에 넣은 IPv4
    ({'url': 'ftp://host/mcp'}, 'http:// 또는 https://'),
    ({'transport': 'websocket', 'url': 'ws://host/mcp'}, '지원하지 않습니다'),
    ({}, 'HTTP 주소가 필요합니다'),
], ids=['명령형', 'stdio 방식 이름', '클라우드 메타데이터', 'IPv6 링크로컬', '미지정 주소', '10진 숫자 IP', '8진 숫자 IP', '0 한 글자',
        'IPv4 넣은 IPv6', 'http 아닌 주소', '웹소켓', '빈 설정'])
def test_명령형_서버와_링크로컬_주소는_어떤_표기로_적어도_학생이_읽을_까닭과_함께_거절된다(spec, says):
    with pytest.raises(ValueError) as refused:
        mcp_check.normalize(spec)
    assert says in str(refused.value)


@pytest.mark.parametrize('url', ['http://127.0.0.1:8301/mcp', 'http://localhost:8301/mcp', 'http://[::1]:8301/mcp', 'http://0x7f000001:8301/mcp',
                                 'http://127.1:8301/mcp'],
                         ids=['127.0.0.1', 'localhost', 'IPv6 루프백', '16진 루프백', '줄인 루프백'])
def test_학생_서버가_루프백을_가리키면_host_docker_internal_로_적으라고_거절한다(url):
    """process 컨테이너 안의 루프백은 process 자신이다 — 학생 서버가 될 수 없고, process 의 내부 경로에 요청을 보내는 길이 된다."""
    with pytest.raises(ValueError) as refused:
        mcp_check.normalize({'url': url}, student=True)
    assert 'host.docker.internal' in str(refused.value)


@pytest.mark.parametrize('url, student', [('http://host.docker.internal:8301/mcp', True), ('https://mcp.example.com/mcp', True),
                                          ('http://127.0.0.1:8301/mcp', False)],
                         ids=['내 PC 서버', '공인 주소', '기준 서버의 이 PC 자리(테스트 · 개발)'])
def test_내_PC와_공인_HTTP_주소는_받는다(url, student):
    assert mcp_check.normalize({'url': url}, student=student) == {'transport': 'streamable_http', 'url': url, 'type': 'url', 'headers': {}}


@pytest.mark.parametrize('key, value, secret', [
    ('Authorization', 'Bearer ${SECRET:MY_TOKEN}', False),      # 비밀 이름 참조 — 비밀이 아니다
    ('X-Api-Key', '${SECRET:KEY_A}', False),
    ('Authorization', 'Bearer abcdef123456', True),
    ('X-Api-Key', 'plain-key-value', True),
    ('Accept', 'application/json', False),
    ('X-Dsn', '', False),
], ids=['참조 Bearer', '참조 그대로', '그대로 적은 토큰', '그대로 적은 키', '비밀 아님', '빈 값'])
def test_비밀값_판정은_참조는_비밀로_보지_않고_그대로_적은_값만_비밀로_본다(key, value, secret):
    assert mcp_check.is_secret_value(key, value) is secret


# ---------------------------------------------------------------- 실제 연결
def test_정상_서버는_도구와_읽기_전용_판정을_돌려준다(student_server):
    out = mcp_check.check(student_server, 5)
    tools = {t['name']: t for t in out['tools']}
    assert out['status'] == 'ok'
    assert (tools['find_rows']['callable'], tools['save_row']['callable']) == (True, False)
    assert tools['save_row']['refuse_reason'] == '서버가 이 도구를 쓰기 도구로 표시했습니다 — 포털 써 보기에서는 쓰기 도구를 부르지 않습니다'


@pytest.mark.parametrize('arguments, status, says', [
    ({'limit': 2}, 'ok', None),
    ({}, 'refused', '꼭 넣어야 할 칸이 빠졌습니다'),
    ({'limit': 'two'}, 'refused', '값의 종류'),
], ids=['정상', '필수 칸 빠짐', '종류 틀림'])
def test_써_보기_입력은_서버의_입력_형식으로_검사하고_거절_까닭을_학생_말로_준다(student_server, arguments, status, says):
    out = mcp_check.call(student_server, 'find_rows', arguments, 5)
    assert out['status'] == status
    if says:
        assert says in out['error'] and 'two' not in out['error']          # 거절된 값은 싣지 않는다
    else:
        assert json.loads(out['result']['text'])['rows'] == [{'n': 0}, {'n': 1}]


def test_쓰기_도구는_써_보기에서_부르지_않는다(student_server):
    out = mcp_check.call(student_server, 'save_row', {'text': 'x'}, 5)
    assert (out['status'], out['error_kind']) == ('refused', 'not_read_only')


def test_조금씩_보내는_서버도_마감_시각에_끝난다():
    server = _RawServer(_drip)
    try:
        started = time.monotonic()
        out = mcp_check.check({'transport': 'streamable_http', 'url': server.url, 'headers': {}}, 2)
        took = time.monotonic() - started
    finally:
        server.close()
    assert (out['status'], out['error_kind']) == ('failed', 'timeout')
    assert took < 3.5                       # 옛 판: 서버가 보내기를 멈출 때까지(30초) 붙잡혔다


def test_한_이벤트가_상한을_넘으면_다_모으기_전에_멈춘다():
    import tracemalloc
    server = _RawServer(_huge_line)
    tracemalloc.start()
    try:
        out = mcp_check.check({'transport': 'streamable_http', 'url': server.url, 'headers': {}}, 20)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        server.close()
    assert (out['status'], out['error_kind']) == ('failed', 'too_large')
    assert peak < 12_000_000                # 옛 판: 60 MB 를 다 모은 뒤 크기를 봤다(최고 120 MB)


def test_머리글_값에_줄바꿈이_섞여도_오류_문구에_그_값이_실리지_않는다(student_server):
    spec = dict(student_server, headers={'Authorization': 'Bearer HEADERVALUE0123456789\r\nX-Evil: 1'})
    out = mcp_check.check(spec, 5)
    assert out['status'] == 'failed'
    assert 'HEADERVALUE0123456789' not in json.dumps(out, ensure_ascii=False)


def test_닿지_않는_주소는_연결_거부로_알린다():
    out = mcp_check.check({'transport': 'streamable_http', 'url': 'http://127.0.0.1:9/mcp', 'headers': {}}, 8)   # 윈도는 거부를 몇 번 다시 확인한다(약 2초)
    assert (out['status'], out['error_kind']) == ('failed', 'refused')


def test_MCP_가_아닌_주소의_응답_본문은_오류에_싣지_않는다():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = b'internal-service-secret-response'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        out = mcp_check.check({'transport': 'streamable_http', 'url': f'http://127.0.0.1:{server.server_address[1]}/', 'headers': {}}, 3)
    finally:
        server.shutdown()
    assert out['error_kind'] == 'not_mcp' and 'internal-service-secret-response' not in out['error'], out


# ---------------------------------------------------------------- 포털 연결 자리
def test_포털_연결_자리가_다_차면_기다리다_까닭과_함께_거절한다():
    held = [mcp_check.portal_slot(0.1) for _ in range(mcp_check.PORTAL_SLOTS)]
    for slot in held:
        slot.__enter__()
    try:
        with pytest.raises(mcp_check.CheckError) as busy:
            with mcp_check.portal_slot(0.2):
                pass
        assert busy.value.kind == 'busy'
    finally:
        for slot in held:
            slot.__exit__(None, None, None)
    with mcp_check.portal_slot(0.1):       # 자리를 돌려주면 다시 열린다
        pass


@pytest.mark.parametrize('tool, ok, words', [
    ({'name': 'submit_decision', 'annotations': {'readOnlyHint': False}}, False, ['쓰기 도구로 표시했습니다']),
    ({'name': 'drop_rows', 'annotations': {'destructiveHint': True}}, False, ['되돌릴 수 없는 쓰기 도구로 표시했습니다']),
    ({'name': 'set_speed', 'annotations': {'readOnlyHint': True}}, False, ["이름의 'set' 가 쓰기·실행을 뜻합니다"]),
    ({'name': 'find_rows', 'annotations': {'readOnlyHint': True}}, True, []),
], ids=['쓰기 표시', '되돌릴 수 없는 쓰기 표시', '읽기 표시지만 쓰기 이름', '읽기 도구'])
def test_써_보기_거부_사유는_도구_연결_화면의_학생_문장이라_표시_이름을_쓰지_않는다(tool, ok, words):
    """한바퀴3 고침 3: 「쓰기 도구(readOnlyHint=false)」처럼 서버 표시 이름이 화면에 그대로 보였다(10 실습 · 통합 63행)."""
    allowed, reason = mcp_check.read_only_verdict(tool)
    assert allowed is ok
    if not ok:
        assert all(w in reason for w in words) and not re.search(r'[A-Za-z]+Hint', reason), reason


# ---------------------------------------------------------------- 승인 뒤 쓰기 호출: 쓰기 요청을 서버에 보냈는가
@pytest.mark.parametrize('url, tool, arguments, status, sent', [
    (None, 'save_row', {'text': 'x'}, 'ok', True),
    (None, 'no_such_tool', {}, 'refused', False),
    (None, 'save_row', {'text': 3}, 'refused', False),
    ('http://127.0.0.1:9/mcp', 'save_row', {'text': 'x'}, 'failed', False),
], ids=['정상', '없는 도구', '맞지 않는 입력', '꺼진 서버'])
def test_승인_뒤_쓰기_호출은_쓰기_요청을_서버에_보냈는지_알려_준다(student_server, url, tool, arguments, status, sent):
    """process 는 이 표시로 「아무것도 보내지 않은 실패」(다시 시도해도 된다)와 「보낸 뒤 결과를 모르는 실패」(외부 결과를 확인해야 한다)를 가른다 —
    전에는 꺼진 서버 · 등록 없는 서버도 「앞선 외부 쓰기가 됐는지 확인되지 않아」로 멈췄다."""
    out = mcp_check.call_effect(dict(student_server, url=url) if url else student_server, tool, arguments, timeout=8)
    assert (out['status'], out['sent']) == (status, sent), out
