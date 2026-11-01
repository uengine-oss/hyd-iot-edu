"""FUXA 화면 올리기(ot/fuxa/init.py) — 올린 뒤 FUXA 가 같은 화면 · 장치를 내는지 확인하고, 아니면 1 로 끝난다(G3b-29).

FUXA 는 바깥(외부 제품)이라 그 HTTP 꼴(GET /api/settings · POST /api/project · GET /api/project)로 답하는 작은 서버를 띄운다.
"""
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import ROOT

PROJECT = ROOT / 'ot' / 'fuxa' / 'project.json'


def _fuxa(keep_upload=True):
    stored = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send(200, {'version': 1.4} if self.path == '/api/settings' else stored.get('project', {}))

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            stored['project'] = body if keep_upload else {'hmi': {'views': []}, 'devices': {}}
            self._send(200, {})
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def init(monkeypatch):
    def load(server):
        monkeypatch.setenv('FUXA_URL', f'http://127.0.0.1:{server.server_port}')
        monkeypatch.setenv('FUXA_PROJECT', str(PROJECT))
        spec = importlib.util.spec_from_file_location('fuxa_init', ROOT / 'ot' / 'fuxa' / 'init.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def test_올린_화면과_장치를_FUXA가_내면_0으로_끝난다(init):
    server = _fuxa()
    try:
        assert init(server).main(pause=0) == 0
    finally:
        server.shutdown()


def test_FUXA가_올린_프로젝트를_내지_않으면_1로_끝난다(init):
    server = _fuxa(keep_upload=False)
    try:
        assert init(server).main(pause=0) == 1
    finally:
        server.shutdown()


def test_저장소_프로젝트의_요약은_화면_하나와_MQTT_장치_하나다(init):
    server = _fuxa()
    try:
        views, devices = init(server).summary(json.loads(PROJECT.read_text(encoding='utf-8')))
    finally:
        server.shutdown()
    assert views == ['설비 현황'] and devices == [('emqx', 'mqtt://emqx:1883')]
