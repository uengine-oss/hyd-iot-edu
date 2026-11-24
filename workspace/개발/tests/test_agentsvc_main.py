"""agent 서비스 앱(it/agent/agentsvc/main.py) — 상태 확인은 물을 때마다 그래프를 재고(H-1), 읽기 평가는 원천 RAISE 경보만 받으며 업무 경보는
센서 원인 진단으로 돌리지 않는다(탐사 N9), 판단 요청은 빠진 칸을 수업 사례로 메우지 않는다.
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
    ('/api/ontology/graph?asset=HYD-01&ns=Bad_NS', 422),
    ('/api/ontology/graph', 422),
], ids=['허용 밖 템플릿', '이름 공간 형식', '설비 없음 — HYD-01 로 대신 답하지 않는다'])
def test_온톨로지_읽기는_정한_템플릿과_이름_공간_형식만_받는다(stack, path, status):
    assert call(stack.services['agent'].url + path)[0] == status


def test_수동_판단에서_진단_지식에_없는_원인을_가정하면_1순위로_대신_판단하지_않고_원인_후보를_말하며_거절한다(world):
    """탐사 N10: 없는 원인을 가정해도 조용히 1순위 원인으로 판단을 냈다 — 학생이 가정한 원인의 결과라고 믿게 된다. 원인 후보에 있는 원인을
    가정하면 그 원인으로 판단한다."""
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.report('HYD-01')
    url = world.stack.services['agent'].url + '/api/agent/decide'
    body = {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}
    with world.reporting('HYD-01'):
        status, plain = call(url, body, 120)
        assert status == 200 and len(plain['causes']) >= 2, plain
        status, refused = call(url, dict(body, facts={'cause': 'cause:no-such-cause'}), 120)
        assert status == 422, refused
        assert 'cause:no-such-cause' in refused['detail'] and all(c['name'] in refused['detail'] for c in plain['causes']), refused
        other = plain['causes'][-1]['id']                                  # 1순위가 아닌 원인 후보
        status, assumed = call(url, dict(body, facts={'cause': other}), 120)
    assert status == 200 and assumed['causes'][0]['id'] == other != plain['causes'][0]['id'], assumed['causes']


@pytest.mark.parametrize('path, body, missing', [
    ('/api/agent/decide', {'pattern': 'COOLER_DEGRADATION'}, 'asset'),
    ('/api/agent/decide', {'asset': 'HYD-02'}, 'pattern'),
    ('/api/agent/decide', {}, 'asset'),
    ('/api/agent/whatif', {'asset': 'HYD-02'}, 'pattern'),
    ('/api/agent/whatif', {}, 'asset'),
], ids=['판단 — 설비 없음', '판단 — 경보 패턴 없음', '판단 — 빈 본문', '조건별 손익 — 경보 패턴 없음', '조건별 손익 — 빈 본문'])
def test_설비나_경보_패턴이_빠진_판단_요청은_수업_사례로_대신_돌지_않고_빠진_칸을_말한다(stack, path, body, missing):
    """가짜 · 해피패스 조사 8: 인자가 빠진 호출이 오류 대신 HYD-01 · 쿨러 열화로 돌아, 다른 설비를 물은 쪽이 그 답을 자기 설비의 것으로 읽었다."""
    status, out = call(stack.services['agent'].url + path, body)
    assert status == 422 and any(missing in (d.get('loc') or []) for d in out['detail']), out


@pytest.mark.parametrize('pattern', ['PM_DUE', 'SPARE_BELOW_MIN'], ids=['정기 정비 도래', '재고 기준 이탈'])
def test_읽기_평가는_업무_경보를_센서_진단_길로_돌리지_않고_그_까닭으로_보류한다(world, pattern):
    """탐사 N9: 업무 표 감시가 낸 경보(정기 정비 도래 · 재고 기준 이탈)를 센서 원인 진단 길로 돌려, 늘 빈 원인 후보로 보류되고 까닭이 「원인 지식이
    없어 매뉴얼을 적재하라」였다 — 매뉴얼을 넣어도 풀리지 않는 엉뚱한 까닭이다. 규칙 판단 길과 같은 문장(card.no_cause_message)으로 보류하고
    진단 단계(신선도 · 원인 후보)는 돌지 않는다. 그 경보를 받는 배포 흐름(평가가 지나는 경보 정책)은 world 가 시작처럼 설치해 둔다."""
    alert = {'alertId': f'EVAL-{pattern}', 'asset': 'HYD-02', 'pattern': pattern, 'state': 'RAISE'}
    status, run = call(world.stack.services['agent'].url + '/api/agent/evaluate', {'alert': alert}, 120)
    assert status == 200 and run['status'] == 'WITHHELD', run
    assert '고장 원인을 진단하는 이상 패턴이 아닙니다' in run['error'] and '업무 흐름' in run['error'], run['error']
    assert '매뉴얼을 적재' not in run['error'] and [s['name'] for s in run['steps']] == ['alert_policy'], run
