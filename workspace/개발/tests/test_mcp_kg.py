"""agent 의 지식 그래프 읽기(agentsvc.tools.mcp_kg.KnowledgeGraph) — 연결 설정 · 상태 확인(ping) · 시간 한도 · 템플릿 폴더 · 「정확히 하나」 계약.

템플릿 결과의 내용은 test_neo4j_templates 가 판정한다. 여기서는 모듈의 동작을 본다.
그래프는 FX 픽스처(seeded_graph — kg-seed 결과), 템플릿은 agent 이미지와 같은 자리 설정(KG_TEMPLATES)으로 저장소 it/neo4j/templates.
그래프와의 연결선이 끊기거나 멈춘 경우는 이 PC 의 TCP 중계(BoltLine — 바깥 네트워크 대체)로 만든다.
"""
import socket
import threading
import time
from urllib.parse import urlsplit

import neo4j
import pytest

from agentsvc.tools import mcp_kg
from conftest import ROOT
from hydcommon.graphdb import GraphSettingsError

TEMPLATES = ROOT / 'it' / 'neo4j' / 'templates'


@pytest.fixture
def made(monkeypatch):
    """KnowledgeGraph 를 그때의 환경으로 만든다(테스트가 끝나면 드라이버를 닫는다)."""
    monkeypatch.setenv('KG_TEMPLATES', str(TEMPLATES))
    graphs = []

    def make(**env):
        for k, v in env.items():
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        graphs.append(mcp_kg.KnowledgeGraph())
        return graphs[-1]
    yield make
    for g in graphs:
        g.driver.close()


class BoltLine:
    """agent ↔ 그래프 사이의 연결선: 이 PC 포트 하나를 테스트 그래프의 Bolt 포트로 잇는다.
    mode 'up' 그대로 잇기 · 'down' 받자마자 닫기(그래프가 꺼짐) · 'mute' 받고 아무 말도 하지 않기(멈춘 그래프). cut() = 이어진 연결을 모두
    끊는다(그래프가 다시 뜬 것과 같다 — 풀에 남은 연결이 죽는다)."""

    def __init__(self, uri):
        far = urlsplit(uri)
        self.upstream, self.mode, self.live, self.lock = (far.hostname, far.port), 'up', [], threading.Lock()
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', 0))
        self.server.listen(32)
        self.uri = f'bolt://127.0.0.1:{self.server.getsockname()[1]}'
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            if self.mode == 'down':
                client.close()
                continue
            if self.mode == 'mute':
                with self.lock:
                    self.live.append((client,))
                continue
            try:
                far = socket.create_connection(self.upstream, timeout=5)
            except OSError:
                client.close()
                continue
            far.settimeout(None)
            with self.lock:
                self.live.append((client, far))
            for a, b in ((client, far), (far, client)):
                threading.Thread(target=self._pump, args=(a, b), daemon=True).start()

    @staticmethod
    def _pump(src, dst):
        try:
            while data := src.recv(65536):
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def cut(self):
        with self.lock:
            live, self.live = self.live, []
        for pair in live:
            for s in pair:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                s.close()

    def close(self):
        self.server.close()
        self.cut()


@pytest.fixture
def line(seeded_graph):
    wire = BoltLine(seeded_graph.uri)
    yield wire
    wire.close()


def _closed_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------- 연결 설정(hydcommon.graphdb — 결정 2)
def test_그래프_인증이_없으면_코드_기본_비밀번호로_붙지_않고_만들_때_까닭과_함께_실패한다(seeded_graph, made):
    with pytest.raises(GraphSettingsError, match='Neo4j 인증이 없습니다'):
        made(NEO4J_AUTH=None, NEO4J_USERNAME=None, NEO4J_PASSWORD=None)


def test_그래프_인증은_도구_서버_설정의_꼴_사용자_비밀번호_두_칸으로도_받는다(seeded_graph, made):
    user, password = seeded_graph.auth
    kg = made(NEO4J_AUTH=None, NEO4J_USERNAME=user, NEO4J_PASSWORD=password)
    assert (kg.ping(), kg.ping_error) == (True, None)


# ---------------------------------------------------------------- 상태 확인
@pytest.mark.parametrize('where, error', [('그래프', None), ('닫힌 포트', 'ServiceUnavailable: '), ('틀린 비밀번호', 'AuthError: ')],
                         ids=['닿음', '그래프 꺼짐', '틀린 비밀번호'])
def test_상태_확인은_닿는지를_참거짓으로_내고_닿지_못한_까닭을_남긴다(seeded_graph, made, where, error):
    env = {'그래프': {}, '닫힌 포트': {'NEO4J_URI': f'bolt://127.0.0.1:{_closed_port()}'},
           '틀린 비밀번호': {'NEO4J_AUTH': f'{seeded_graph.auth[0]}/wrong-password'}}[where]
    kg = made(**env)
    assert kg.ping() is (error is None)
    assert kg.ping_error is None if error is None else kg.ping_error.startswith(error)


def test_그래프가_다시_닿으면_상태_확인의_까닭이_지워진다(made, line):
    kg = made(NEO4J_URI=line.uri)
    line.mode = 'down'
    assert kg.ping() is False and kg.ping_error.startswith('ServiceUnavailable')
    line.mode = 'up'
    assert (kg.ping(), kg.ping_error) == (True, None)


def test_멈춘_그래프에서도_상태_확인과_질의는_한도_안에_끝난다(made, line):
    kg = made(NEO4J_URI=line.uri)
    line.mode = 'mute'
    started = time.monotonic()
    assert kg.ping() is False
    assert time.monotonic() - started < 10
    started = time.monotonic()
    with pytest.raises(neo4j.exceptions.DriverError):                 # 연결을 얻지 못함(ServiceUnavailable · 시간 초과)
        kg.roles()
    assert time.monotonic() - started < 10


def test_그래프가_다시_떠도_다음_질의는_풀에_남은_끊긴_연결로_실패하지_않는다(made, line):
    kg = made(NEO4J_URI=line.uri)
    before = kg.roles()
    line.cut()                                                          # 풀의 연결이 모두 죽는다(neo4j 재시작 · 볼륨 교체)
    assert kg.roles() == before and before


def test_5초를_넘는_질의는_그래프가_끊는다(seeded_graph, made, tmp_path, monkeypatch):
    kg = made()
    (tmp_path / 't3_roles.cypher').write_text('UNWIND range(1, 2000000000) AS x WITH x WHERE x < 0 RETURN count(x) AS n', encoding='utf8')
    monkeypatch.setenv('KG_TEMPLATES', str(tmp_path))
    started = time.monotonic()
    with pytest.raises(neo4j.exceptions.ClientError) as failed:
        kg.roles()
    assert 'TransactionTimedOut' in (failed.value.code or '') and time.monotonic() - started < 15


# ---------------------------------------------------------------- 템플릿 폴더
def test_템플릿_폴더는_가져올_때가_아니라_처음_쓸_때_읽는다(seeded_graph, made, tmp_path, monkeypatch):
    kg = made()
    (tmp_path / 't3_roles.cypher').write_text("// 시험 템플릿\nRETURN 'role:from-folder' AS id", encoding='utf8')
    monkeypatch.setenv('KG_TEMPLATES', str(tmp_path))                  # 모듈을 가져온 · 객체를 만든 뒤에 바꿈
    assert kg.roles() == [{'id': 'role:from-folder'}]
    assert kg.template_text('t3_roles').startswith('// 시험 템플릿') and '//' not in kg.template('t3_roles')


def test_템플릿_폴더에_없는_질의는_돌지_않는다(seeded_graph, made, tmp_path, monkeypatch):
    kg = made()
    monkeypatch.setenv('KG_TEMPLATES', str(tmp_path))
    with pytest.raises(FileNotFoundError):
        kg.roles()


# ---------------------------------------------------------------- 정확히 하나
def test_부품_번호가_같은_부품이_둘이면_하나를_고르지_않고_실패한다(seeded_graph, made):
    kg = made()
    assert kg.purchase_part('P-PMP-SEAL')['id'] == 'part:pump-seal'
    seeded_graph.query("CREATE (:Part {id:'part:pump-seal-copy', name:'사본', partNo:'P-PMP-SEAL'})")
    with pytest.raises(ValueError, match='없거나 중복되었습니다'):
        kg.purchase_part('P-PMP-SEAL')


def test_같은_설비_코드에_예측_모델_묶음이_둘이면_하나를_고르지_않고_실패한다(seeded_graph, made):
    kg = made()
    assert kg.forecast_model('HYD-01')['asset_id'] == 'asset:hyd-01'
    seeded_graph.query("CREATE (:Asset {id:'asset:hyd-01-copy', code:'HYD-01', forecastModel:'other', forecastRevision:'9'})")
    with pytest.raises(ValueError, match='exactly one explicit forecast model binding'):
        kg.forecast_model('HYD-01')


def test_수업_지식을_넣기_전_kg_seed_그래프에서는_어느_경보_패턴에도_원인_후보가_없다(seeded_graph, made):
    kg = made()
    patterns = [r['code'] for r in seeded_graph.query('MATCH (p:AnomalyPattern) RETURN p.code AS code')]
    assert 'COOLER_DEGRADATION' in patterns
    assert {p: kg.t1_causes(p) for p in patterns} == {p: [] for p in patterns}
