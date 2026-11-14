"""agent 서비스 앱(it/agent/agentsvc/main.py) — 상태 확인은 물을 때마다 그래프를 재고(H-1), 읽기 평가는 매번 새 실행이며 쌓지 않는다(G1-07).
실제 agent 서비스(stack — Dockerfile 의 실행 명령 그대로) · 실제 Neo4j 컨테이너."""
import contextlib
import json
import urllib.error
import urllib.request

import pytest

from conftest import until


def call(url, body=None, timeout=30):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'}, method='GET' if body is None else 'POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'null')


class BoltLine:
    """agent 와 Neo4j 사이의 연결선(바깥 — 네트워크). cut() 하면 듣기를 멈추고 이어진 연결을 끊는다(Neo4j 가 꺼진 것과 같다),
    join() 하면 같은 주소로 다시 듣는다(Neo4j 가 다시 뜬 것과 같다)."""

    def __init__(self, target_port):
        import socket
        self.target, self.port, self.pairs, self.server = target_port, None, [], None
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            self.port = probe.getsockname()[1]
        self.join()

    def join(self):
        import socket
        import threading
        self.server = socket.create_server(('127.0.0.1', self.port))
        threading.Thread(target=self._accept, args=(self.server,), daemon=True).start()

    def _accept(self, server):
        import socket
        import threading
        while True:
            try:
                client, _ = server.accept()
            except OSError:
                return
            upstream = socket.create_connection(('127.0.0.1', self.target))
            self.pairs.append((client, upstream))
            for src, dst in ((client, upstream), (upstream, client)):
                threading.Thread(target=self._pipe, args=(src, dst), daemon=True).start()

    @staticmethod
    def _pipe(src, dst):
        try:
            while data := src.recv(65536):
                dst.sendall(data)
        except OSError:
            pass
        for sock in (src, dst):
            try:
                sock.close()
            except OSError:
                pass

    def cut(self):
        import socket
        # 리눅스에서는 듣는 소켓을 닫기만 하면 accept 에서 기다리던 스레드가 그 소켓을 쥔 채 남아 다음 연결 하나를 그대로 받는다(끊은 뒤의 상태
        # 확인이 200 이었다). shutdown 이 그 accept 를 깨워 끝낸다. 윈도우는 듣는 소켓의 shutdown 을 거절하고 close 만으로 끝난다.
        with contextlib.suppress(OSError):
            self.server.shutdown(socket.SHUT_RDWR)
        self.server.close()
        for pair in self.pairs:
            for sock in pair:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError:
                    pass
        self.pairs.clear()


@pytest.fixture
def agent_via_line(stack, graph_server, tmp_path, monkeypatch):
    """두 번째 agent(같은 Dockerfile 실행 명령 · 같은 코드)를 연결선 너머의 Neo4j 에 붙여 띄운다."""
    import conftest
    from urllib.parse import urlsplit
    line = BoltLine(urlsplit(graph_server.uri).port)
    monkeypatch.setitem(conftest.PORTS, 'agent', conftest._free_port())
    service = conftest.ServiceProcess('agent', tmp_path, {'NEO4J_URI': f'bolt://127.0.0.1:{line.port}'}).wait()
    yield service, line
    service.close()
    line.cut()


def test_그래프가_끊기면_상태_확인이_503_과_까닭이고_다시_이어지면_같은_프로세스가_200_이다(agent_via_line):
    """H-1: 켜질 때 한 번 잰 연결 여부를 박아 두어, Neo4j 보다 먼저 뜬 날은 영영 503 이었다(시작 5단계 멈춤)."""
    service, line = agent_via_line
    health = service.url + '/healthz'
    assert call(health)[0] == 200
    line.cut()
    status, body = call(health)
    assert status == 503 and body['neo4j'] is False and body['neo4j_error']
    line.join()
    until(lambda: call(health)[0] == 200, 'agent 상태 확인이 그래프가 다시 이어진 뒤 200', timeout=60)
    assert call(health)[1]['neo4j'] is True


@pytest.mark.parametrize('alert', [
    {'alertId': 'A', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'CLEAR'},
    {'alertId': '', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE'},
    {'alertId': 'A', 'asset': 'HYD-01', 'state': 'RAISE'},
], ids=['해제 경보', '빈 id', '패턴 없음'])
def test_읽기_평가는_원천_RAISE_경보만_받는다(stack, alert):
    status, body = call(stack.services['agent'].url + '/api/agent/evaluate', {'alert': alert})
    assert status == 400 and 'RAISE' in body['detail']


@pytest.mark.parametrize('path, status', [
    ('/api/ontology/template/drop_all', 404),
    ('/api/ontology/graph?ns=Bad_NS', 422),
], ids=['허용 밖 템플릿', '이름 공간 형식'])
def test_온톨로지_읽기는_정한_템플릿과_이름_공간_형식만_받는다(stack, path, status):
    assert call(stack.services['agent'].url + path)[0] == status


def test_같은_경보를_두_번_평가하면_서로_다른_실행이고_서비스에_쌓이지_않는다(world):
    """G1-07: 평가 실행이 메모리 장부에 쌓였고 읽는 곳이 없었다(지운 /api/runs)."""
    world.report('HYD-01')
    url = world.stack.services['agent'].url
    alert = {'alertId': 'EVAL-HYD-01', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE'}
    (s1, a), (s2, b) = call(url + '/api/agent/evaluate', {'alert': alert}, 120), call(url + '/api/agent/evaluate', {'alert': alert}, 120)
    assert s1 == s2 == 200 and a['id'] != b['id'] and a['status'] and b['status']
    assert call(url + '/api/runs')[0] == 404
