"""포털 nginx(it/portal/nginx.conf) — 화면이 서비스를 부르는 같은 출처 길 /svc/<서비스>/ (결정 1).
compose 와 같은 이미지(nginx:1.27-alpine)에 이 conf · 화면 파일을 실어 버릴 망에 띄우고, 서비스 자리에는 받은 요청을 그대로 돌려주는 작은 대역
(compose 서비스 이름 process · plant-sim 으로)을 붙인다. 화면이 실제로 보내는 꼴의 요청으로 넘김 · 크기 한도 · 꺼진 서비스 · 화면 파일을 잰다.
docker 가 없으면 까닭을 내고 실패한다. 끝나면 컨테이너 · 망을 지운다."""
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

import pytest

from conftest import ROOT

IMAGE, STUB_IMAGE = 'nginx:1.27-alpine', 'python:3.12-slim'
# 서비스 대역: 받은 그대로의 경로(+쿼리) · 방식 · 본문 길이를 JSON 으로
STUB = r'''
import http.server, json
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def _do(self):
        n = int(self.headers.get('Content-Length') or 0); body = self.rfile.read(n) if n else b''
        out = json.dumps({'path': self.path, 'method': self.command, 'length': len(body), 'forwarded_host': self.headers.get('X-Forwarded-Host'),
                          'origin': self.headers.get('Origin')}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
    do_GET = do_POST = _do
    def log_message(self, *a): pass
for_port = __import__('sys').argv[1]
http.server.ThreadingHTTPServer(('0.0.0.0', int(for_port)), H).serve_forever()
'''


def _docker(*args, check=True):
    p = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', timeout=180)
    if check and p.returncode:
        pytest.fail(f'docker {" ".join(args[:3])} 실패: {p.stderr[-800:]}', pytrace=False)
    return p.stdout.strip()


def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='module')
def portal():
    if not shutil.which('docker'):
        pytest.fail('docker 가 없어 포털 nginx 를 띄우지 못했다 — Docker Desktop 을 켠 PC에서 돌린다', pytrace=False)
    tag = 'hyd-test-nginx-' + uuid.uuid4().hex[:8]
    net, made = tag, []
    _docker('network', 'create', net)
    try:
        for alias, port in (('process', 8080), ('plant-sim', 8000)):
            made.append(_docker('run', '-d', '--rm', '--network', net, '--network-alias', alias, STUB_IMAGE, 'python', '-c', STUB, str(port)))
        port = _free_port()
        www, conf = ROOT / 'it' / 'portal' / 'www', ROOT / 'it' / 'portal' / 'nginx.conf'
        env = dict(os.environ, MSYS_NO_PATHCONV='1')
        p = subprocess.run(['docker', 'run', '-d', '--rm', '--network', net, '-p', f'127.0.0.1:{port}:80', '-e', 'HYD_PORTS=8080=18080',
                            '-v', f'{www}:/usr/share/nginx/html:ro', '-v', f'{conf}:/etc/nginx/templates/default.conf.template:ro', IMAGE],
                           capture_output=True, text=True, encoding='utf-8', env=env, timeout=180)
        if p.returncode:
            pytest.fail(f'포털 nginx 를 띄우지 못했다: {p.stderr[-800:]}', pytrace=False)
        made.append(p.stdout.strip())
        base = f'http://127.0.0.1:{port}'
        deadline = time.monotonic() + 60
        while True:    # nginx · 대역이 답할 때까지(조건 대기)
            try:
                if json.loads(urllib.request.urlopen(base + '/svc/process/ready', timeout=2).read())['path'] == '/ready':
                    break
            except Exception as e:  # noqa: BLE001 — 아직 뜨는 중
                if time.monotonic() > deadline:
                    pytest.fail(f'포털 nginx · 서비스 대역이 60초 안에 답하지 않았다: {e} · nginx 로그: {_docker("logs", made[-1], check=False)[-800:]}', pytrace=False)
        yield base
    finally:
        for c in made:
            _docker('rm', '-f', c, check=False)
        _docker('network', 'rm', net, check=False)


def _get(url, data=None, method=None):
    req = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json'} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


@pytest.mark.parametrize('path, upstream_path', [
    ('/svc/process/api/instances?limit=50&status=RUNNING', '/api/instances?limit=50&status=RUNNING'),   # 쿼리 그대로
    ('/svc/process/api/skills/%EB%83%89%EA%B0%81', '/api/skills/%EB%83%89%EA%B0%81'),                   # %인코딩을 풀지 않는다
    ('/svc/process/api/skills/a%2Fb', '/api/skills/a%2Fb'),                                             # id 속 %2F 가 경로로 바뀌지 않는다
    ('/svc/plant-sim/api/state', '/api/state'),                                                         # 같은 /api/state 라도 서비스 앞머리로 갈린다
])
def test_svc_앞머리를_떼고_그_서비스에_받은_글자_그대로_넘긴다(portal, path, upstream_path):
    status, _, body = _get(portal + path)
    assert status == 200 and json.loads(body)['path'] == upstream_path


@pytest.mark.parametrize('path, status, says', [
    ('/svc/nope/x', 404, '포털에 없는 서비스 길입니다 (nope)'),
    ('/svc/agent/healthz', 502, '서비스(agent)에 연결하지 못했습니다'),      # 서비스가 꺼져 있으면 어느 서비스인지 밝힌 JSON(화면 requestJ 가 그대로 보인다)
])
def test_없는_서비스와_꺼진_서비스는_JSON_한_줄로_까닭을_준다(portal, path, status, says):
    got, headers, body = _get(portal + path)
    assert got == status and headers['Content-Type'].startswith('application/json') and says in json.loads(body)['detail']


@pytest.mark.parametrize('path, size, status', [
    ('/svc/process/api/flows/import', 3 * 1024 * 1024, 200),          # 흐름 그림(최대 2 MB) + JSON
    ('/svc/process/api/flows/import', 5 * 1024 * 1024, 413),          # 보통 요청 한도 4 MB
    ('/svc/process/api/kg/manuals/preview', 40 * 1024 * 1024, 200),   # 수업 문서 30 MiB 의 base64
    ('/svc/process/api/kg/manuals/preview', 42 * 1024 * 1024, 413),
])
def test_본문_크기_한도는_요청마다_정해져_있고_넘으면_서비스에_닿기_전에_413(portal, path, size, status):
    got, headers, body = _get(portal + path, data=b'x' * size, method='POST')
    assert got == status, body[:200]
    if status == 413:
        assert '크기 한도' in json.loads(body)['detail']
    else:
        assert json.loads(body)['length'] == size


@pytest.mark.parametrize('path, status', [('/', 200), ('/samples/HM-8_cooler-fan-manual.md', 200), ('/samples/NOPE.md', 404), ('/api/whatever', 404)])
def test_화면_파일은_있는_것만_주고_없는_파일에_index_html_을_주지_않는다(portal, path, status):
    got, headers, _ = _get(portal + path)
    assert got == status and headers['X-Content-Type-Options'] == 'nosniff' and "frame-ancestors 'self'" in headers['Content-Security-Policy']


def test_첫_화면에_이_PC의_옮긴_포트_표를_끼워_넣는다(portal):
    _, _, body = _get(portal + '/')
    assert b'window.HYD_PORTS_RAW="8080=18080"' in body


@pytest.mark.parametrize('path', ['/svc/process/api/scenario/A/inject', '/svc/process/api/events/stream'], ids=['보통 길', '실시간 알림 길(따로 적은 머리글)'])
def test_서비스에_브라우저가_부른_포털_주인과_Origin_을_넘긴다(portal, path):
    """옛 브라우저(Sec-Fetch-Site 없음)의 쓰기를 서비스가 Origin 과 견주려면 포털 주소(브라우저가 부른 주인)가 서비스까지 가야 한다
    (hydcommon.service.foreign_write). proxy_set_header 를 따로 적은 실시간 알림 길도 같은지 본다."""
    host = portal.split('//', 1)[1]
    req = urllib.request.Request(portal + path, data=b'{}', method='POST', headers={'Content-Type': 'application/json', 'Origin': portal})
    with urllib.request.urlopen(req, timeout=15) as r:
        seen = json.loads(r.read())
    assert (seen['forwarded_host'], seen['origin']) == (host, portal)
