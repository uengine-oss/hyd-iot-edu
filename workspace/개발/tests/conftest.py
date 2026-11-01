"""테스트 공통 준비 — 테스트 묶음 하나가 학생 PC 한 대다. 서비스는 우리 코드 그대로 이 PC에서 띄우고, 바깥만 대체한다.

돌리는 조건: 환경 변수 HYD_TEST_DSN 하나(로컬 Supabase 안의 버릴 DB — 이름이 hyd_test 로 시작해야 한다)와 Docker(그래프 · 시계열
컨테이너 — 테스트 DB 이름마다 하나 `hyd-test-<서비스>-<DB 이름>`(라벨 hyd.test.site = 그 DB 이름), 묶음이 끝나면 지운다. 이 PC 에서
한꺼번에 HEAVY_SLOTS 칸까지 — 넘으면 차례를 기다리고, 칸을 잡으면 끊긴 묶음이 남긴 컨테이너부터 지운다). 없으면 그것이 필요한 테스트는 건너뛰지 않고 「무엇이 없어 못 돌았는지」를 적고 실패한다. 화면 순회 테스트만 떠 있는
포털(HYD_TEST_PORTAL_URL)을 쓴다. 서비스 · 컨테이너는 그것을 요청한 테스트가 있을 때만 뜬다.
테스트 파일 이름: 모듈 하나당 `test_<모듈>.py`. 모듈 이름이 겹치면(main · server · tools · state …) `test_<패키지>_<모듈>.py`(process 의
main 만 `test_main.py`), 포털 화면 JS 는 `test_www_<파일>.py`, 코드 모듈이 아닌 대상(마이그레이션 · nginx · emqx 설정 · 시드 · 설치 파일)은
그 대상 이름.

학생 PC 구성                       → 테스트에서(우리 코드 그대로)                                           픽스처
  업무 DB(Supabase PostgreSQL)     → HYD_TEST_DSN 의 버릴 DB — 묶음 시작에 지우고 마이그레이션 전부 + seed.sql       pg_dsn
  지식 그래프(neo4j + kg-seed)     → 이 테스트 자리의 neo4j 컨테이너 + kg-seed 와 같은 it/neo4j/seed.sh             neo4j_graph · seeded_graph
  시작이 넣는 수업 지식            → 시작과 같은 scripts/class_knowledge.ensure(이 묶음 process 의 지식 적재 API)                     course_graph
  시계열(TimescaleDB)              → 이 테스트 자리의 timescaledb 컨테이너 + 같은 init.sql · reader.sql              timescale
  MQTT(emqx) · Kafka(redpanda)     → 이 테스트 자리의 emqx · redpanda 컨테이너 + topic-init 과 같은 topics.sh           brokers
  설비 데이터 수집기(connect-ingest) → Dockerfile 실행 명령을 하위 프로세스로, 위 두 브로커에 붙는다(agent 신선도 확인이 읽음)  stack
  process                          → 실제 procsvc.main 앱(이 프로세스 안 · 이 PC 포트). 기동은 main.restore_and_build   world
  agent · dmn-mcp(+neo4j 도구) · enterprise-mcp 셋 · enterprise-sim · effects-mcp
                                   → 각 Dockerfile 의 실행 명령을 이 PC 의 하위 프로세스로(compose 환경, 주소만 이 PC)  stack
  AI 워커                          → 실제 worker.runner.Runner(이 프로세스 안)                                      worker · world.agent
  설비(plant-sim)                  → 실제 plantsim.plant.Plant 모델(이 프로세스 안). 설비 상태 · 태그를 process 가 읽는
                                     길(원천 접수 · tag_1s)로 보고한다                                              world.plant · world.report
바깥만 대체한다:
  강의 중계(LiteLLM)  → FakeRelay(이 PC 포트, 받은 요청을 남긴다 — 유료 중계를 부르지 않는다)
  Claude Code CLI     → 키 있는 PC: RecordedCli(녹화 이벤트 + 관문 실제 호출) · 키 없는 PC: 실제 재생기(worker.ai_replay)
  SMTP(Inbucket)      → FakeSmtp
  시계                → 처리 엔진만 EngineClock(시작은 지금 벽시계, 테스트가 앞으로만 옮긴다 — sleep 으로 기다리지 않는다).
                        DB · 시계열 · agent 의 시각과 설비 보고 시각은 벽시계다(승인 현재 조건 검사가 벽시계로 신선도를 잰다)
학생 PC 구성 요소지만 테스트가 대신하는 것(까닭):
  process 의 Kafka 송수신 → KafkaRecorder: process 가 보낸 승인 원장 · 설비 명령을 남기고 테스트가 송신을 실패시킬 수 있다. 받는 쪽(경보 ·
                        설비 상태)은 테스트가 process 의 원천 접수 함수(main.receive_records — consume 과 같은 함수)로 넣는다. 브로커(brokers)는
                        떠 있어 connect-ingest 가 붙고, consume() 자체의 구독은 test_main 이 실제 redpanda 로 잰다
  감지기(detector) · 명령 관문(cmd-gateway) → 경보와 명령 확인(ACK)은 테스트가 원천 접수로 넣는다(world.raise_alert · world.ack)
주소: 묶음이 시작할 때 서비스마다 이 PC 의 빈 포트를 하나씩 정하고(PORTS), process(이 프로세스 안)는 compose 의 process 환경을 그 주소로
바꿔 받는다(pytest_configure — 끝나면 되돌림). 하위 프로세스 서비스는 이 묶음이 시작하기 전의 환경(HOST_ENV)에 compose 환경을 더해 받는다.
"""
import asyncio
import contextlib
import itertools
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace as _NS
from urllib.parse import urlsplit, urlunsplit

import pytest

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / 'it' / 'supabase' / 'migrations'
SEED = ROOT / 'it' / 'supabase' / 'seed.sql'
REPLAY_DIR = ROOT / 'it' / 'agent-worker' / 'replay'
DEFINITIONS = ROOT / 'it' / 'process' / 'definitions'
WWW = ROOT / 'it' / 'portal' / 'www'          # 포털 화면 파일(nginx 가 그대로 낸다)
SAMPLES = WWW / 'samples'                       # 수업 문서 원문 · 제공 DDL(강사 서명 · 해시 — 읽기만)
DSN_ENV = 'HYD_TEST_DSN'
TEST_DB_PREFIX = 'hyd_test'            # 묶음이 지우고 다시 만드는 DB 이름은 이것으로 시작해야 한다(다른 스택의 업무 DB 보호)
TENANT = 'hyd'
WORKER_KEY = 'worker-runtime-test-' + 'w' * 40
RELAY_KEY = 'relay-test-key-' + 'k' * 30
SERVER_SECRET = 'Bearer enterprise-test-secret-' + 's' * 24     # 테넌트의 enterprise 서버 인증 머리글(작업 폴더 .mcp.json 에 실린다)
CALLER_TOKEN = 'engine-test-caller-' + 'c' * 24                  # compose 가 시작 파일에서 받는 process 호출 값(PROCESS_CALLER_TOKEN)
FINGERPRINT_KEY = 'engine-test-fingerprint-' + 'f' * 24          # 승인 장부 지문 키(CMD_FINGERPRINT_KEY)
HOST_ENV = dict(os.environ)            # 이 묶음이 바꾸기 전의 환경 — 하위 프로세스 서비스 · 도구 시험의 바탕

COOLING = ('COOLER_DEGRADATION', 'HYD-01')
OPERATOR = dict(by='user:kim-op', role='role:operator')


# ---------------------------------------------------------------- 공통 도우미
def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def until(condition, what, timeout=15.0):
    """조건이 참이 될 때까지 기다린다(고정 sleep 이 아니라 조건 대기). 한도를 넘으면 what 을 까닭으로 실패한다."""
    end = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > end:
            raise TimeoutError(what)
        time.sleep(0.01)


def bash():
    """셸 스크립트를 돌릴 bash(Windows 는 Git for Windows 의 것이 먼저 — PATH 의 bash 가 WSL 일 수 있다). 없으면 까닭을 내고 실패한다."""
    for candidate in (r'C:\Program Files\Git\bin\bash.exe', shutil.which('bash')):
        if candidate and Path(candidate).exists():
            return candidate
    pytest.fail('bash 가 없어 셸 스크립트 테스트를 돌리지 못했다 — Git for Windows(또는 bash)를 설치한다', pytrace=False)


def git(repo, *args, inp=None):
    """repo 에서 git 한 번(경로 이름을 따옴표 없이). 실패하면 그 명령의 오류로 실패한다. 돌려줌 = 앞뒤 공백을 뗀 표준 출력."""
    return subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=repo, check=True, capture_output=True, text=True,
                          encoding='utf-8', input=inp).stdout.strip()


def _pid_alive(pid):
    """이 PC에서 그 PID 의 프로세스가 아직 살아 있는가(끊긴 테스트 실행이 남긴 컨테이너 · DB 를 가린다)."""
    if os.name == 'nt':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ---------------------------------------------------------------- 이 PC의 테스트 자리(주소)
#: compose 서비스 이름(과 테스트 대체물) → 이 묶음이 쓰는 이 PC 포트. 서비스가 뜰 때 이 포트에 붙는다.
PORTS = {name: _free_port() for name in (
    'process', 'agent', 'dmn-mcp', 'enterprise-mcp', 'enterprise-mcp-maint', 'enterprise-mcp-purchase', 'enterprise-sim',
    'effects-mcp', 'neo4j', 'timescaledb', 'agent-worker', 'plant-sim', 'relay', 'emqx', 'redpanda', 'connect-ingest')}


def _compose():
    import yaml
    return yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf8'))


def _compose_service(name):
    return _compose()['services'][name]


def _compose_default(value, given=None):
    """compose 값의 `${이름:-기본}` 을 그 기본값으로(이 PC 셸의 환경 변수는 보지 않는다 — 학생 PC 기본 구성). given 에 있는 이름은 그 값으로
    (테스트 컨테이너가 이 PC 에 연 포트 — compose 의 `HYD_PORT_<포트>` 자리)."""
    return re.sub(r'\$\{(\w+):-([^}]*)\}', lambda m: str((given or {}).get(m[1], m[2])), str(value))


_ADDRESS = re.compile(r"(?P<scheme>[a-z][a-z0-9+]*)://(?P<auth>[^@/\s'\"]+@)?(?P<host>[\w.-]+):(?P<port>\d+)(?P<path>/[^\s'\",]*)?")


def here(value):
    """compose 값 안의 서비스 주소를 이 PC 의 테스트 자리로: `http://<서비스>:<포트>` → 127.0.0.1:<PORTS>, 업무 DB
    (`postgresql://…@host.docker.internal:…/postgres`) → HYD_TEST_DSN 의 서버 · DB(계정은 그대로). 모르는 주소는 그대로 둔다."""
    test_db = urlsplit(os.environ.get(DSN_ENV) or HOST_ENV.get(DSN_ENV) or '')

    def swap(m):
        scheme, auth, host, path = m['scheme'], m['auth'] or '', m['host'], m['path'] or ''
        if scheme.startswith('postgres') and host == 'host.docker.internal':
            return f'{scheme}://{auth}{test_db.hostname}:{test_db.port}{test_db.path}' if test_db.hostname else m[0]
        if host in PORTS:
            return f'{scheme}://{auth}127.0.0.1:{PORTS[host]}{path}'
        return m[0]
    return _ADDRESS.sub(swap, str(value))


def _local_url(service, path=''):
    return f'http://127.0.0.1:{PORTS[service]}{path}'


def _dockerfile(service):
    """그 compose 서비스의 Dockerfile: (COPY 대상 → 저장소 자리, ENV, CMD)."""
    path = ROOT / _compose_service(service)['build']['dockerfile']
    copies, env, cmd = {}, {}, None
    for line in re.sub(r'\\\r?\n', ' ', path.read_text(encoding='utf8')).splitlines():
        word, _, rest = line.strip().partition(' ')
        if word == 'COPY':
            src, dst = [w for w in rest.split() if not w.startswith('--')][-2:]
            copies[dst] = ROOT / src
        elif word == 'ENV':
            for item in shlex.split(rest):
                key, _, value = item.partition('=')
                env[key] = value
        elif word == 'CMD':
            cmd = json.loads(rest)
    return copies, env, cmd


def _image_env(copies, env):
    """Dockerfile ENV 의 이미지 안 경로(/srv/…)를 그 COPY 의 저장소 자리로."""
    out = {}
    for key, value in env.items():
        for dst, src in sorted(copies.items(), key=lambda kv: -len(kv[0])):
            if value == dst or value.startswith(dst + '/'):
                value = str(src) + value[len(dst):]
                break
        out[key] = value
    return out


def _python_path(copies):
    """이미지의 /srv/<패키지> 를 만드는 COPY 들 → 그 패키지가 든 저장소 폴더(PYTHONPATH)."""
    paths = []
    for dst, src in copies.items():
        if src.is_dir() and (src / '__init__.py').exists() and PurePosixPath(dst).name == src.name and str(src.parent) not in paths:
            paths.append(str(src.parent))
    return paths


def _process_env():
    """compose 의 process 환경(주소만 이 PC) + 시작 파일이 정하는 값 + 코드 기본값이 컨테이너 이름을 가리키는 주소."""
    copies, image_env, _ = _dockerfile('process')
    env = {k: v for k, v in _image_env(copies, image_env).items() if not k.startswith('MALLOC_')}   # Dockerfile ENV(이미지 경로 → 저장소 자리 — 템플릿 등). glibc 값은 이 PC 와 무관
    env.update({k: here(_compose_default(v)) for k, v in _compose_service('process')['environment'].items()})
    env.pop('KAFKA_BOOTSTRAP')                  # 소비기 · 송신기는 테스트가 정한다(KafkaRecorder)
    env.pop('HYD_WORKER_RUNTIME_KEY_FILE')      # 실행기 인증 파일은 묶음의 임시 폴더(worker_key)
    env.update(PROCESS_CALLER_TOKEN=CALLER_TOKEN, CMD_FINGERPRINT_KEY=FINGERPRINT_KEY, LLM_API_KEY=RELAY_KEY, LLM_RELAY_URL=_local_url('relay'),
               AGENT_URL=_local_url('agent'), WORKER_URL=_local_url('agent-worker'), PLANT_SIM_URL=_local_url('plant-sim'),
               PROCESS_URL=_local_url('process'),
               EFFECT_MCP_SERVERS=json.dumps({'hyd-effects': {'type': 'url', 'url': _local_url('effects-mcp', '/mcp'),
                                                              'transport': 'streamable_http'}}))
    return env


def _hold_site(config):
    """이 테스트 자리(테스트 DB 이름)를 이 묶음이 쓰는 동안 잠근다 — 같은 자리를 다른 묶음이 함께 쓰면 DB 와 컨테이너를 서로 지운다.
    잠금은 이 PC 임시 폴더의 파일(프로세스가 끝나면 운영체제가 푼다)."""
    name = urlsplit(os.environ[DSN_ENV]).path.lstrip('/')
    handle = open(_site_lock_path(name), 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise pytest.UsageError(f'테스트 자리 {name}({DSN_ENV}의 DB 이름)를 다른 테스트 묶음이 쓰고 있다 — 그 묶음이 끝난 뒤 돌리거나 '
                                f'다른 DB 이름(예: {name}_2)으로 돌린다(같은 자리는 DB 와 테스트 컨테이너를 함께 쓴다)')
    config._hyd_site_lock = handle


def pytest_configure(config):
    """process 가 가져올 때 읽는 환경(compose 의 process environment 자리)을 묶음 동안 이 PC 주소로. 끝나면 되돌린다.
    이 테스트 자리의 컨테이너가 이미 있으면(앞 묶음이 띄운 것을 다시 씀) 그 포트를 쓴다."""
    if os.environ.get(DSN_ENV):
        _hold_site(config)
        for service, inside in REUSED_CONTAINERS:
            PORTS[service] = _published_port(container_name(service), inside) or PORTS[service]
    env = _process_env()
    config._hyd_env_before = {k: os.environ.get(k) for k in env}
    os.environ.update(env)


def pytest_unconfigure(config):
    if getattr(config, '_hyd_site_lock', None) is not None:
        config._hyd_site_lock.close()
    for key, value in getattr(config, '_hyd_env_before', {}).items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


# ---------------------------------------------------------------- 업무 DB(Supabase PostgreSQL)
def _admin_dsn(dsn):
    return urlunsplit(urlsplit(dsn)._replace(path='/postgres'))


def _with_db(dsn, name):
    return urlunsplit(urlsplit(dsn)._replace(path='/' + name))


@pytest.fixture(scope='session')
def pg_dsn():
    """마이그레이션 · 시드가 막 들어간 버릴 데이터베이스의 주소."""
    import psycopg
    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        pytest.fail(f'{DSN_ENV}가 없어 실제 DB 테스트를 돌리지 못했다 — 로컬 Supabase가 켜진 PC에서 '
                    f'{DSN_ENV}=postgresql://postgres:postgres@127.0.0.1:<DB 포트>/{TEST_DB_PREFIX} 를 주고 다시 돌린다', pytrace=False)
    name = urlsplit(dsn).path.lstrip('/')
    if not re.fullmatch(TEST_DB_PREFIX + r'\w*', name):
        pytest.fail(f'{DSN_ENV}의 데이터베이스 이름이 {name or "(없음)"}이다 — 테스트는 그 DB를 지우고 다시 만들므로 이름이 '
                    f'{TEST_DB_PREFIX} 로 시작하는 버릴 DB만 받는다(업무 DB · 다른 스택의 DB 보호)', pytrace=False)
    try:
        admin = psycopg.connect(_admin_dsn(dsn), autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as exc:
        pytest.fail(f'{DSN_ENV}의 서버에 닿지 않는다({exc.__class__.__name__}: {str(exc).strip()[:200]}) — Supabase를 켠다', pytrace=False)
    with admin:
        _sweep_scratch_dbs(admin, name)
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')
    load_schema(dsn)
    return dsn


def load_schema(dsn):
    """학생 PC 의 새 업무 DB 와 같은 내용: it/supabase/migrations 전부 + seed.sql. 실패하면 그 파일 이름과 함께 실패한다."""
    import psycopg
    with psycopg.connect(dsn, autocommit=True) as conn:
        for sql in sorted(MIGRATIONS.glob('*.sql')) + [SEED]:
            try:
                conn.execute(sql.read_text(encoding='utf8'))
            except psycopg.Error as exc:
                pytest.fail(f'{sql.relative_to(ROOT)}를 새 DB에 넣지 못했다: {exc}', pytrace=False)


def _scratch_name(base):
    return f'{base}_s{os.getpid()}_{uuid.uuid4().hex[:8]}'


def _sweep_scratch_dbs(admin, base):
    """끊긴 실행(강제 종료)이 남긴 이 묶음 이름의 임시 DB(base_s<PID>_…)를 지운다 — 지금 도는 다른 실행의 것은 둔다."""
    pattern = re.compile(re.escape(base) + r'_s(\d+)_[0-9a-f]{8}')
    for (name,) in admin.execute('SELECT datname FROM pg_database').fetchall():
        m = pattern.fullmatch(name)
        if m and not _pid_alive(int(m[1])):
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@contextlib.contextmanager
def new_database(pg_dsn, *, schema=False):
    """테스트 서버에 빈 DB 하나(이름 <테스트 DB>_s<PID>_<임의>) → 주소. schema=True 면 load_schema(새 업무 DB 와 같은 내용)까지.
    블록이 끝나면 지운다. 강제 종료로 남으면 다음 묶음의 pg_dsn 이 지운다."""
    import psycopg
    name = _scratch_name(urlsplit(pg_dsn).path.lstrip('/'))
    with psycopg.connect(_admin_dsn(pg_dsn), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    try:
        dsn = _with_db(pg_dsn, name)
        if schema:
            load_schema(dsn)
        yield dsn
    finally:
        with psycopg.connect(_admin_dsn(pg_dsn), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def as_user(dsn, user, password, **query):
    """같은 서버 · DB 에 다른 계정으로(query 는 연결 옵션 — 예: connect_timeout)."""
    parts = urlsplit(dsn)
    extra = '&'.join(f'{k}={v}' for k, v in query.items())
    return urlunsplit(parts._replace(netloc=f'{user}:{password}@{parts.hostname}:{parts.port}', query=extra))


def _reader(name, dsn, query):
    """compose agent 환경의 전용 읽기 계정 주소(name)에서 계정 · 암호를 가져와 dsn 의 서버 · DB 에 붙인다(사본 없이 compose 한 곳)."""
    parts = urlsplit(_compose_default(_compose_service('agent')['environment'][name]))
    return as_user(dsn, parts.username, parts.password, **query)


def ent_reader(pg_dsn, **query):
    """업무 DB 전용 읽기 계정(hyd_enterprise_reader — agent 의 ENTERPRISE_READ_DSN)으로 테스트 DB 에."""
    return _reader('ENTERPRISE_READ_DSN', pg_dsn, query)


def ts_reader(timescale, **query):
    """시계열 전용 읽기 계정(hyd_timeseries_reader — agent 의 TSDB_READ_DSN)으로 이 자리의 시계열에."""
    return _reader('TSDB_READ_DSN', timescale.dsn, query)


@pytest.fixture
def scratch_db(pg_dsn):
    """테스트 하나만 쓰는 빈 DB 의 주소(new_database)."""
    with new_database(pg_dsn) as dsn:
        yield dsn


# ---------------------------------------------------------------- 테스트 컨테이너(compose 서비스 그대로 · 테스트 자리마다 하나를 다시 씀)
# 컨테이너 이름은 `hyd-test-<서비스>-<테스트 DB 이름>`으로 고정한다(테스트 DB 이름 = 이 테스트 자리 — 고침마다 다르다). 있으면 그대로 다시 쓰고
# (멈춰 있으면 켬, 묶음 시작에 그래프 · 표를 비운다), 없거나 띄우는 내용(이미지 · 명령 · 환경 · 붙이는 파일 · 메모리)이 바뀌었을 때만 새로 띄운다.
# 한 묶음 안에서는 다시 쓰고, 묶음이 끝나면 heavy_slot 이 이 자리의 컨테이너를 지운다(메인 지시 — Docker 가 몰려 멈췄다). 시드 결과는 디스크 캐시라 다음 묶음도 빠르다.
CONTAINER_LABEL, CONTAINER_SPEC, CONTAINER_SITE = 'hyd.test', 'hyd.test.spec', 'hyd.test.site'   # docker 라벨: 이 테스트가 만든 컨테이너 · 띄운 내용의 지문 · 테스트 자리


def _docker(*args, timeout=120, check=True):
    try:
        done = subprocess.run(['docker', *args], capture_output=True, timeout=timeout)
    except FileNotFoundError:
        pytest.fail('docker 명령이 없어 실제 그래프 · 시계열 테스트를 돌리지 못했다 — Docker Desktop을 설치 · 실행한 PC에서 다시 돌린다', pytrace=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'docker {" ".join(args[:2])} 가 {timeout}초 안에 답하지 않았다 — Docker 엔진이 멈췄거나 너무 바쁘다(docker info 로 확인)') from None
    out = done.stdout.decode('utf8', 'replace')
    if check and done.returncode:
        raise RuntimeError(f'docker {" ".join(args[:2])} 가 {done.returncode}로 끝났다: '
                           f'{(done.stderr.decode("utf8", "replace") or out).strip()[-1500:]}')
    return out


def _test_site():
    """이 테스트 자리의 이름 = HYD_TEST_DSN 의 DB 이름(동시에 도는 고침마다 다르다). 없으면 컨테이너를 정할 수 없어 까닭을 내고 실패한다."""
    name = urlsplit(os.environ.get(DSN_ENV) or '').path.lstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name or '-'):
        pytest.fail(f'{DSN_ENV}가 없거나 DB 이름이 컨테이너 이름으로 쓸 수 없는 글자다 — 테스트 컨테이너는 테스트 DB 이름마다 하나다', pytrace=False)
    return name


def container_name(service):
    return f'hyd-test-{service}-{_test_site()}'


def _published_port(name, container_port):
    """그 이름의 테스트 컨테이너가 이 PC 에 연 포트(없으면 None) — 묶음이 시작할 때 process 주소를 다시 쓰는 컨테이너에 맞춘다."""
    try:
        done = subprocess.run(['docker', 'port', name, f'{container_port}/tcp'], capture_output=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    line = done.stdout.decode('utf8', 'replace').split()
    return int(line[0].rpartition(':')[2]) if done.returncode == 0 and line else None


# ---------------------------------------------------------------- PC 전체 동시 상한(무거운 묶음 = 그래프 · 시계열 컨테이너 · 서비스 스택)
#: 이 PC 에서 한꺼번에 도는 무거운 묶음 수. 2026-10-30 실측: 묶음이 몰려 테스트 컨테이너 13~22개 · Docker 메모리 6.2/7.9 GB 뒤 엔진과
#: 업무 DB(Supabase)가 두 번 멈췄다. 셈(메모리 한도 기준): Docker 7.9 GB − 강사 스택 약 3.9 GB = 4.0 GB. 한 묶음 = Neo4j 한도 1.5 GB(compose
#: mem_limit — 시드를 연달아 다섯 번 넣고 읽을 때 최고 847 → 1047 MiB, 1 GB 한도에서는 종료 137) + 시계열 0.25 GB = 1.75 GB.
#: 셋이면 5.25 GB 로 넘고 둘이면 3.5 GB 로 든다 → 둘. 서비스 스택(stack)을 쓰는 묶음은 MQTT · Kafka 브로커(emqx 320m · redpanda 448m)가
#: 더해져 2.52 GB 라 칸 둘을 함께 잡는다(혼자 돈다 — 3.5 GB 안).
HEAVY_SLOTS = 2


def _try_lock(handle, block):
    """파일 잠금 하나(운영체제가 잡는다 — 잡은 프로세스가 죽으면 풀린다). block=True 면 그 잠금이 풀릴 때까지 기다린다(Windows 는 최대 약 10초씩)."""
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if block else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if block else fcntl.LOCK_NB))
        return True
    except OSError:
        return False


class _Held:
    """잡은 칸들 — close() 가 모두 푼다."""
    def __init__(self, handles):
        self.handles = handles

    def close(self):
        for handle in reversed(self.handles):
            handle.close()


def take_slot(directory, slots=HEAVY_SLOTS, what='', say=print, count=1):
    """directory 의 잠금 파일 slots 칸 가운데 count 칸을 잡는다 → 잡은 것(close() 로 풀림). 다 차 있으면 한 줄 알리고 잠금이 풀리기를
    기다린다(고정 sleep 이 아니라 운영체제 잠금 대기). 기다리는 묶음은 문(gate.lock)을 쥔 차례로 하나씩 — 문을 쥔 묶음이 칸을 다 잡아야
    다음이 칸을 본다(칸 여럿을 바라는 묶음이 뒤에 온 한 칸 묶음들에 밀려 끝없이 기다리지 않게). 한 칸은 아무 칸이나(칸을 돌아가며),
    여러 칸은 0번부터 차례로."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if count > slots:
        raise ValueError(f'칸 {count}개를 바라지만 이 PC 칸은 {slots}개다')
    gate = open(directory / 'gate.lock', 'a+b')
    handles = [open(directory / f'slot-{i}.lock', 'a+b') for i in range(slots)]
    told = False

    def wait_note():
        nonlocal told
        if not told:
            say(f'[테스트 차례 기다림] 이 PC 에서 그래프 · 시계열을 쓰는 다른 테스트 묶음이 돈다(칸 {slots}개) — {what or "이 묶음"}은 '
                f'칸 {count}개가 비면 이어 간다')
            told = True
    try:
        while not _try_lock(gate, block=False):
            wait_note()
            if _try_lock(gate, block=True):
                break
        if count > 1:
            for handle in handles[:count]:
                while not _try_lock(handle, block=False):
                    wait_note()
                    if _try_lock(handle, block=True):
                        break
            held = handles[:count]
        else:
            turn, held = os.getpid() % slots, None
            while held is None:
                held = next(([h] for h in handles if _try_lock(h, block=False)), None)
                if held is None:
                    wait_note()
                    if _try_lock(handles[turn], block=True):
                        held = [handles[turn]]
                    turn = (turn + 1) % slots
    except BaseException:
        for handle in handles:
            handle.close()
        raise
    finally:
        gate.close()                          # 문은 칸을 다 잡으면(또는 실패하면) 바로 놓는다
    for other in handles:
        if other not in held:
            other.close()
    return _Held(held)


def _site_lock_path(site):
    import tempfile
    return Path(tempfile.gettempdir()) / f'hyd-test-site-{site}.lock'


def remove_site_containers(site):
    """그 테스트 자리(라벨 hyd.test.site 가 정확히 site)의 테스트 컨테이너를 모두 지운다. docker 가 실패하면 남은 이름과 함께 실패한다."""
    names = _docker('ps', '-a', '--filter', f'label={CONTAINER_SITE}={site}', '--format', '{{.Names}}').split()
    for name in names:
        _docker('rm', '-f', '-v', name)
    left = _docker('ps', '-a', '--filter', f'label={CONTAINER_SITE}={site}', '--format', '{{.Names}}').split()
    if left:
        raise RuntimeError(f'테스트 자리 {site}의 컨테이너를 지웠는데 남았다: {left}')
    return names


def sweep_dead_sites(mine, say=print):
    """도는 묶음이 없는 테스트 자리(자리 잠금 파일을 아무도 쥐지 않음 — 끊긴 묶음이 남긴 것)의 테스트 컨테이너를 지운다 → 지운 자리들.
    지우는 동안 그 자리의 잠금을 쥔다(그 사이 그 자리로 시작하는 묶음은 「다른 묶음이 쓰고 있다」로 멈춘다). 자기 자리(mine)는 두지 않는다."""
    services = sorted(_compose()['services'], key=len, reverse=True)
    sites = {}
    for row in _docker('ps', '-a', '--filter', f'label={CONTAINER_LABEL}', '--format', f'{{{{.Names}}}}\t{{{{.Label "{CONTAINER_SITE}"}}}}').splitlines():
        name, _, site = row.partition('\t')
        if not site.strip():          # 자리 꼬리표 전에 만든 것: 이름 hyd-test-<compose 서비스>-<자리>
            site = next((name[len(f'hyd-test-{s}-'):] for s in services if name.startswith(f'hyd-test-{s}-')), '')
        if site.strip():
            sites.setdefault(site.strip(), []).append(name)
    swept = []
    for site, names in sorted(sites.items()):
        if site == mine:
            continue
        handle = open(_site_lock_path(site), 'a+b')
        try:
            if not _try_lock(handle, block=False):
                continue                                        # 그 자리의 묶음이 돈다
            for name in names:
                _docker('rm', '-f', '-v', name)
            remove_site_containers(site)
            say(f'[테스트 자리 정리] 도는 묶음이 없는 자리 {site}의 남은 테스트 컨테이너를 지웠다: {names}')
            swept.append(site)
        finally:
            handle.close()
    return swept


@pytest.fixture(scope='session')
def heavy_slot(request, pytestconfig):
    """무거운 묶음의 차례(PC 전체 HEAVY_SLOTS 칸 — 서비스 스택을 쓰는 묶음은 칸 전부). 칸을 잡으면 끊긴 묶음이 남긴 컨테이너를 먼저 지우고
    (칸 셈이 실제 컨테이너와 맞게), 묶음이 끝나면 이 자리의 테스트 컨테이너를 지우고 칸을 푼다. docker 가 실패하면 시끄럽게 실패한다."""
    import tempfile
    reporter = pytestconfig.pluginmanager.get_plugin('terminalreporter')
    say = (lambda line: reporter.write_line(line)) if reporter else print
    count = HEAVY_SLOTS if any('stack' in item.fixturenames for item in request.session.items) else 1
    held = take_slot(Path(tempfile.gettempdir()) / 'hyd-test-slots', what=f'테스트 자리 {_test_site()}', say=say, count=count)
    try:
        sweep_dead_sites(_test_site(), say)
        yield
    finally:
        try:
            remove_site_containers(_test_site())
        finally:
            held.close()


#: 다시 쓰는 테스트 컨테이너(서비스, 컨테이너 포트) — pytest_configure 가 이 PC 포트를 기존 컨테이너의 것으로 맞춘다
REUSED_CONTAINERS = (('neo4j', 7687), ('timescaledb', 5432), ('emqx', 1883), ('redpanda', 19092))


class ComposeContainer:
    """compose 서비스 하나(이미지 · 명령 · 환경 · 저장소 파일 붙이기 그대로)를 이 테스트 자리의 컨테이너 `hyd-test-<서비스>-<테스트 DB>`로.
    주 포트는 127.0.0.1 의 PORTS[서비스](없는 서비스면 기존 컨테이너의 포트 또는 빈 포트), extra_ports 도 같다 — `box.ports[컨테이너 포트]`가
    이 PC 포트. 이름 붙은 볼륨은 붙이지 않는다(새 컨테이너 = 처음 켠 PC). 내용 지문(라벨)이 같으면 다시 쓰고(reused=True), 다르면 지우고 새로."""

    def __init__(self, service, container_port, *, env=None, memory=None, extra_mounts=(), extra_ports=(), name=None, hosts=()):
        """name: 이 자리의 기본 이름 대신 쓸 이름(그 이름의 포트는 PORTS 가 아니라 그 컨테이너의 것 · 빈 포트).
        hosts: 컨테이너 안에서 127.0.0.1 로 풀 이름(compose 망에서 서비스 이름이 자기 자신을 가리키는 자리 — 예: redpanda).
        compose 명령의 `${HYD_PORT_<n>:-…}`(그 서비스가 호스트에 여는 포트)는 이 컨테이너가 이 PC 에 연 포트로 바꾼다."""
        import hashlib
        try:
            _docker('info', '--format', '{{.ServerVersion}}', timeout=30)
        except RuntimeError as exc:
            pytest.fail(f'Docker 엔진에 닿지 않아 {service} 테스트 컨테이너를 띄우지 못했다 — Docker Desktop을 켠다({exc})', pytrace=False)
        spec = _compose_service(service)
        self.service, self.name = service, name or container_name(service)
        self.port = (None if name else PORTS.get(service)) or _published_port(self.name, container_port) or _free_port()
        self.ports = {container_port: self.port, **{p: _published_port(self.name, p) or _free_port() for p in extra_ports}}
        self.env = {k: _compose_default(v) for k, v in (spec.get('environment') or {}).items()}
        self.env.update(env or {})
        host_ports = {}
        for line in spec.get('ports') or []:
            m = re.fullmatch(r'(?:[\d.]+:)?\$\{(\w+):-\d+\}:(\d+)', str(line))
            if m and int(m[2]) in self.ports:
                host_ports[m[1]] = self.ports[int(m[2])]
        content = ['--memory', memory or spec['mem_limit'], *(a for h in hosts for a in ('--add-host', f'{h}:127.0.0.1'))]
        for volume in list(spec.get('volumes') or []) + list(extra_mounts):
            source, target, *mode = volume.split(':')
            if source.startswith('./'):
                content += ['-v', ':'.join([str((ROOT / source).resolve()), target, *mode])]
        for k, v in self.env.items():
            content += ['-e', f'{k}={v}']
        content += [spec['image'], *(_compose_default(a, host_ports) for a in spec.get('command') or [])]
        site = [CONTAINER_SITE, _test_site()]      # 자리 꼬리표 — 묶음 끝 정리 · 죽은 자리 정리가 이 값과 정확히 같은 것만 고른다
        fingerprint = hashlib.sha256(json.dumps([content, sorted(self.ports), site]).encode()).hexdigest()[:16]
        found = _docker('ps', '-a', '--filter', f'name=^{self.name}$', '--format', f'{{{{.Label "{CONTAINER_SPEC}"}}}} {{{{.State}}}}').split()
        published = {inside: _published_port(self.name, inside) for inside in self.ports} if found else {}
        self.reused = bool(found) and found[0] == fingerprint and published == self.ports
        if self.reused:
            if found[1] != 'running':
                _docker('start', self.name)
            return
        if found:
            _docker('rm', '-f', '-v', self.name)
        ports = [a for inside, outside in self.ports.items() for a in ('-p', f'127.0.0.1:{outside}:{inside}')]
        _docker('run', '-d', '--name', self.name, '--label', f'{CONTAINER_LABEL}={service}', '--label', f'{CONTAINER_SPEC}={fingerprint}',
                '--label', '='.join(site), *ports, *content, timeout=600)      # 여러 묶음이 함께 돌면 docker run 이 5분을 넘었다(실측)

    def logs(self):
        return _docker('logs', '--tail', '40', self.name, check=False).strip()[-2500:]

    def running(self):
        return _docker('inspect', '-f', '{{.State.Running}}', self.name, check=False).strip() == 'true'

    def wait(self, ready, what, timeout):
        """ready() 가 참일 때까지(예외는 아직 뜨는 중). 컨테이너가 멈추거나 한도를 넘으면 마지막 오류 · 로그와 함께 실패한다."""
        end, last = time.monotonic() + timeout, None
        while True:
            try:
                if ready():
                    return
            except Exception as exc:  # noqa: BLE001 — 아직 뜨는 중이면 다시 묻는다. 한도를 넘으면 그 오류를 까닭으로 싣는다
                last = exc
            if not self.running() or time.monotonic() > end:      # 끝난 컨테이너는 한도까지 기다리지 않는다
                state = _docker('inspect', '-f', '{{.State.Status}} 종료 코드={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}}', self.name, check=False).strip()
                raise RuntimeError(f'테스트 컨테이너 {self.name}({what})가 준비되지 않았다({state}, 한도 {timeout}초, '
                                   f'마지막 오류 {type(last).__name__ if last else "-"}: {last}):\n{self.logs()}')
            time.sleep(0.5)

# ---------------------------------------------------------------- 지식 그래프(Neo4j)
# compose neo4j 서비스의 이미지 · 설정 그대로(메모리만 작게). 시드는 compose kg-seed 와 같은 명령(it/neo4j/seed.sh — 같은 파일 · 같은 순서 ·
# 되읽기 검사)을 그 컨테이너 안에서 한 번 돌리고, 테스트마다 그 결과(데이터 · 제약 · 색인)로 되돌린다.
#: 여러 테스트 실행이 동시에 돈다(고침 13갈래가 한꺼번에 — 2026-10-30 실측 테스트 Neo4j 9개 · 1개 350~630 MiB, Docker 7.9 GB 중 6.2 GB).
#: 테스트 그래프는 수백 노드라 힙 · 페이지 캐시를 줄이고, JVM 의 힙 밖 몫(메타 공간 · 코드 캐시)도 작게 둔다.
GRAPH_MEMORY = {'NEO4J_server_memory_heap_initial__size': '96m', 'NEO4J_server_memory_heap_max__size': '192m',
                'NEO4J_server_memory_pagecache_size': '16m',
                'NEO4J_server_jvm_additional': '-XX:MaxMetaspaceSize=192m -XX:ReservedCodeCacheSize=48m'}   # GC 는 neo4j 기본(G1) — 둘째 GC 를 고르면 JVM 이 뜨지 않는다
GRAPH_MEM_LIMIT = None       # compose neo4j 의 mem_limit 그대로 — 1g 에서는 시드의 cypher-shell(따로 뜨는 JVM)이 서버와 함께 한도를 넘어 죽었다(종료 137, 실측)
#: kg-seed 의 cypher-shell JVM 몫(서버와 같은 컨테이너에서 문장마다 새로 뜬다 — 기본 힙은 컨테이너 메모리의 1/4). JAVA_OPTS 는 cypher-shell 이 읽는다
SEED_JAVA_OPTS = '-Xmx96m -XX:MaxMetaspaceSize=96m -XX:+UseSerialGC'
GRAPH_BOOT_S, GRAPH_SEED_S = 600, 900                # 여러 묶음이 함께 돌면 neo4j 첫 기동이 3분을 넘는다(실측)


class Graph:
    """테스트 하나가 쓰는 Neo4j: uri · auth(사용자, 암호) · env(서비스가 읽는 NEO4J_URI · NEO4J_AUTH) · query(cypher, **params) → 행 dict 목록."""

    def __init__(self, server):
        self.uri, self.auth, self.env, self.driver = server.uri, server.auth, server.env, server.driver

    def query(self, cypher, **params):
        with self.driver.session() as s:
            return s.execute_write(lambda tx: [r.data() for r in tx.run(cypher, **params)])


class GraphServer:
    """이 테스트 자리의 neo4j 컨테이너(compose neo4j 서비스 그대로 — ComposeContainer). 묶음 시작에 비운다(앞 묶음이 쓴 것 0).
    주소는 process 가 받은 NEO4J_URI 와 같다."""

    def __init__(self):
        from neo4j import GraphDatabase
        seed = _compose_service('kg-seed')
        self.seed_command = seed['entrypoint']
        self.seed_env = {k: _compose_default(v) for k, v in (seed.get('environment') or {}).items()}
        env = {k: v for k, v in GRAPH_MEMORY.items()}
        self.box = ComposeContainer('neo4j', 7687, env=env, memory=GRAPH_MEM_LIMIT, extra_mounts=seed['volumes'])
        try:
            user, password = self.box.env['NEO4J_AUTH'].split('/', 1)
            self.uri, self.auth = here('bolt://neo4j:7687'), (user, password)
            self.env = {'NEO4J_URI': self.uri, 'NEO4J_AUTH': f'{user}/{password}'}
            self.driver = GraphDatabase.driver(self.uri, auth=self.auth, connection_timeout=3, max_transaction_retry_time=0)
            self.box.wait(lambda: self.driver.verify_connectivity() is None, 'Bolt', GRAPH_BOOT_S)
            self.reset()
        except BaseException:
            self.close()
            raise

    def close(self):
        if getattr(self, 'driver', None) is not None:
            self.driver.close()

    def _run(self, cypher, **params):
        with self.driver.session() as s:
            return s.execute_write(lambda tx: [r.data() for r in tx.run(cypher, **params)])

    def _schema(self):
        return sorted(r['s'] for r in self._run('SHOW CONSTRAINTS YIELD createStatement RETURN createStatement AS s')) + sorted(
            r['s'] for r in self._run("SHOW INDEXES YIELD type, owningConstraint, createStatement "
                                      "WHERE owningConstraint IS NULL AND type <> 'LOOKUP' RETURN createStatement AS s"))

    def reset(self):
        """빈 그래프: 데이터 · 제약 · 색인(LOOKUP 빼고)을 모두 지운다 — 새 볼륨에서 막 뜬 neo4j 와 같다."""
        self._run('MATCH (n) DETACH DELETE n')
        self._drop_schema()

    def _drop_schema(self):
        for row in self._run('SHOW CONSTRAINTS YIELD name RETURN name'):
            self._run(f'DROP CONSTRAINT `{row["name"]}`')
        for row in self._run("SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP' RETURN name"):
            self._run(f'DROP INDEX `{row["name"]}`')

    def seed(self):
        """compose kg-seed 와 같은 명령을 이 컨테이너 안에서(Bolt 는 같은 컨테이너의 7687). 실패하면 시드 출력과 함께 실패한다."""
        env = dict(self.seed_env, NEO4J_URI='bolt://localhost:7687', JAVA_OPTS=SEED_JAVA_OPTS)
        args = ['exec'] + [a for k, v in env.items() for a in ('-e', f'{k}={v}')] + [self.box.name, *self.seed_command]
        try:
            _docker(*args, timeout=GRAPH_SEED_S)
        except RuntimeError as exc:
            raise RuntimeError(f'테스트 그래프에 kg-seed({" ".join(self.seed_command)})가 들어가지 않았다: {exc}') from exc

    def snapshot(self):
        """지금 그래프 전부(제약 · 색인 문장, 노드 · 관계와 속성) — restore 가 그대로 다시 만든다."""
        nodes = self._run('MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props')
        rels = self._run('MATCH (a)-[r]->(b) RETURN elementId(a) AS a, elementId(b) AS b, type(r) AS type, properties(r) AS props')
        return _NS(schema=self._schema(), nodes=nodes, rels=rels, counts=self._counts())

    def _counts(self):
        return (sorted((r['l'], r['n']) for r in self._run('MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS n')),
                sorted((r['t'], r['n']) for r in self._run('MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n')),
                self._schema())

    def restore(self, snap):
        """snapshot 의 그래프로 되돌린다. 제약 · 색인이 이미 같으면 데이터만 다시 만든다(제약을 새로 만드는 데 몇 초씩 든다)."""
        self._run('MATCH (n) DETACH DELETE n')
        if self._schema() != snap.schema:
            self._drop_schema()
            for statement in snap.schema:
                self._run(statement)
        ids, groups = {}, {}
        for n in snap.nodes:
            groups.setdefault(tuple(sorted(n['labels'])), []).append({'k': n['id'], 'p': n['props']})
        for labels, rows in groups.items():
            for r in self._run(f'UNWIND $rows AS r CREATE (n{"".join(":`" + l + "`" for l in labels)}) SET n = r.p '
                               'RETURN r.k AS k, elementId(n) AS e', rows=rows):
                ids[r['k']] = r['e']
        groups = {}
        for r in snap.rels:
            groups.setdefault(r['type'], []).append({'a': ids[r['a']], 'b': ids[r['b']], 'p': r['props']})
        for kind, rows in groups.items():
            self._run(f'UNWIND $rows AS r MATCH (a) WHERE elementId(a) = r.a MATCH (b) WHERE elementId(b) = r.b '
                      f'CREATE (a)-[x:`{kind}`]->(b) SET x = r.p', rows=rows)
        after = self._counts()
        if after != snap.counts:
            diff = [(what, sorted(set(map(str, want)) ^ set(map(str, got))))
                    for what, want, got in zip(('노드 레이블 수', '관계 종류 수', '제약 · 색인'), snap.counts, after) if want != got]
            raise AssertionError(f'테스트 그래프를 저장한 상태로 되돌리지 못했다(저장 ↔ 되돌린 뒤 차이): {diff}')


@pytest.fixture(scope='session')
def graph_server(heavy_slot):
    server = GraphServer()
    yield server
    server.close()


def _seed_key():
    """시드 결과를 정하는 것 전부의 지문: neo4j · kg-seed 서비스 정의, 이미지 id, 시드 폴더(it/neo4j)의 모든 파일."""
    import hashlib
    digest = hashlib.sha256()
    compose = _compose()['services']
    digest.update(json.dumps([compose['neo4j'], compose['kg-seed']], sort_keys=True, default=str).encode())
    digest.update(_docker('image', 'inspect', '--format', '{{.Id}}', compose['neo4j']['image']).encode())
    for path in sorted((ROOT / 'it' / 'neo4j').rglob('*')):
        if path.is_file():
            digest.update(path.relative_to(ROOT).as_posix().encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


@pytest.fixture(scope='session')
def _seed_snapshot(graph_server):
    """kg-seed 결과. 같은 지문(_seed_key)으로 이 PC 에서 이미 시드한 결과가 있으면 그것을 쓴다(시드는 cypher-shell 을 30번 넘게 띄워 2분쯤
    걸린다) — 시드 파일 · 이미지 · 서비스 정의 중 하나라도 바뀌면 지문이 달라 다시 시드한다. 시드가 되읽기 검사까지 통과한 뒤에만 저장한다."""
    import tempfile
    cache = Path(tempfile.gettempdir()) / 'hyd-test-graph' / f'seed-{_seed_key()}.json'
    if cache.is_file():
        snap = _NS(**json.loads(cache.read_text(encoding='utf8')))
        labels, kinds, schema = snap.counts                      # JSON 이 튜플을 목록으로 바꿨다 — _counts() 와 같은 꼴로
        snap.counts = ([tuple(x) for x in labels], [tuple(x) for x in kinds], schema)
        graph_server.restore(snap)
        return graph_server.snapshot()
    graph_server.reset()
    graph_server.seed()
    snap = graph_server.snapshot()
    cache.parent.mkdir(parents=True, exist_ok=True)
    partial = cache.with_suffix(f'.{os.getpid()}.tmp')
    partial.write_text(json.dumps(vars(snap), ensure_ascii=False), encoding='utf8')
    os.replace(partial, cache)
    return snap


@pytest.fixture
def neo4j_graph(graph_server):
    """빈 그래프(데이터 · 제약 · 색인 없음). 주소는 묶음 동안 NEO4J_URI · NEO4J_AUTH(process 와 하위 서비스가 읽는 값)와 같다."""
    graph_server.reset()
    return Graph(graph_server)


@pytest.fixture
def seeded_graph(graph_server, _seed_snapshot):
    """kg-seed 가 막 끝난 그래프 — 테스트마다 시드 상태로 되돌린다."""
    graph_server.restore(_seed_snapshot)
    return Graph(graph_server)


@pytest.fixture(scope='session')
def _course_snapshot(graph_server, _seed_snapshot, stack, tmp_path_factory):
    """시작이 끝난 그래프: kg-seed 뒤 시작과 같은 `scripts/class_knowledge.ensure`(이 묶음 process 의 지식 적재 API)로 수업 지식을 넣은 상태."""
    import class_knowledge
    graph_server.restore(_seed_snapshot)
    world = EngineWorld(stack, tmp_path_factory.mktemp('course-knowledge'))
    try:
        class_knowledge.ensure(class_knowledge.http_call(world.url))      # 시작(start_all.sh)과 같은 적재 — 이 묶음의 process 로
    finally:
        world.close()
    return graph_server.snapshot()


@pytest.fixture
def course_graph(graph_server, _course_snapshot):
    """시작이 끝난 학생 PC 의 그래프(kg-seed + 수업 지식) — 테스트마다 그 상태로 되돌린다."""
    graph_server.restore(_course_snapshot)
    return Graph(graph_server)


# ---------------------------------------------------------------- 시계열(TimescaleDB)
class TimescaleServer:
    """이 테스트 자리의 timescaledb 컨테이너(compose 서비스 그대로 — 같은 이미지 · 명령 · init.sql · reader.sql). 묶음 시작에 비운다.
    주소는 process 가 받은 PG_DSN 과 같다."""

    def __init__(self):
        import psycopg
        self.box = ComposeContainer('timescaledb', 5432)
        env = self.box.env
        self.dsn = here(f"postgresql://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}@timescaledb:5432/{env['POSTGRES_DB']}")
        self.box.wait(lambda: psycopg.connect(self.dsn, connect_timeout=3).execute('SELECT 1 FROM tag_1m LIMIT 1').close() is None,
                      'PostgreSQL + init.sql', 120)
        self.clear()

    def clear(self):
        """설비 값 · 경보 · 명령 기록과 1분 집계까지 비운다(처음 켠 PC 의 빈 시계열 — 묶음 시작과 world 마다)."""
        import psycopg
        with psycopg.connect(self.dsn, autocommit=True) as db:
            db.execute('TRUNCATE tag_1s, feat_1s, alerts, actions, audit')
            db.execute("CALL refresh_continuous_aggregate('tag_1m', NULL, NULL)")      # 원시값이 없어진 구간의 집계도 지운다

    def write(self, asset, values):
        """설비 값 한 줄씩(시각 = 시계열 DB 의 지금 — connect-sink 가 받은 순간처럼)."""
        import psycopg
        with psycopg.connect(self.dsn, autocommit=True) as db, db.cursor() as cur:
            cur.executemany('INSERT INTO tag_1s(time, asset, name, value) VALUES (now(), %s, %s, %s)',
                            [(asset, name, float(value)) for name, value in values.items()])



@pytest.fixture(scope='session')
def timescale(heavy_slot):
    return TimescaleServer()


# ---------------------------------------------------------------- 설비 데이터 길의 브로커(MQTT · Kafka) — connect-ingest 가 붙는다
BROKER_BOOT_S = 300


class Brokers:
    """이 테스트 자리의 emqx · redpanda 컨테이너(compose 서비스 그대로 — 같은 이미지 · 명령 · 설정 파일) + compose topic-init 과 같은
    토픽 만들기(it/redpanda/topics.sh 를 redpanda 컨테이너 안에서). emqx 의 안쪽 입구(1883, 서비스 이름만)는 이 PC 의 서비스가 붙는
    자리라 이 PC 포트로 연다(compose 에서는 ot-net 안에만). redpanda 의 바깥 입구는 compose 처럼 호스트 포트를 광고한다.
    mqtt = (주소, 포트), kafka = 이 PC 에서 붙는 Kafka 주소."""

    def __init__(self):
        init = _compose_service('topic-init')
        self.mqtt_box = ComposeContainer('emqx', 1883, extra_ports=(1884, 8083))
        self.kafka_box = ComposeContainer('redpanda', 19092, extra_mounts=init['volumes'], hosts=('redpanda',))
        self.mqtt = ('127.0.0.1', self.mqtt_box.port)
        self.kafka = f'127.0.0.1:{self.kafka_box.port}'
        self.mqtt_box.wait(lambda: 'is started' in _docker('exec', self.mqtt_box.name, 'emqx', 'ctl', 'status', timeout=30),
                           'emqx ctl status', BROKER_BOOT_S)
        # 다시 쓰는 컨테이너에는 앞 묶음이 남긴 보존(retain) 메시지가 있다 — 붙자마자 그 메시지가 와서 뒤 테스트의 셈이 어긋났다
        # (전체 테스트 1: test_gw_main 경보판 시험의 malformed 2). 처음 켠 브로커처럼 비우고 시작한다(시계열 · 그래프 준비와 같은 규칙).
        _docker('exec', self.mqtt_box.name, 'emqx', 'ctl', 'retainer', 'clean', timeout=30)
        self.kafka_box.wait(lambda: re.search(r'Healthy:\s+true', _docker('exec', self.kafka_box.name, 'rpk', 'cluster', 'health', timeout=30)),
                            'rpk cluster health', BROKER_BOOT_S)
        try:
            _docker('exec', self.kafka_box.name, *init['entrypoint'], timeout=120)
        except RuntimeError as exc:
            raise RuntimeError(f'테스트 Kafka 에 토픽이 만들어지지 않았다(compose topic-init 과 같은 {" ".join(init["entrypoint"])}): {exc}') from exc


@pytest.fixture(scope='session')
def brokers(heavy_slot):
    return Brokers()


# ---------------------------------------------------------------- 서비스(각 Dockerfile 의 실행 명령을 이 PC 의 하위 프로세스로)
SERVICE_BOOT_S = 300
RECEIVE_S = 30


class ServiceProcess:
    """compose 서비스 하나: 그 Dockerfile 의 CMD(uvicorn · python -m …)를 이 PC 의 파이썬으로, 패키지 자리는 Dockerfile COPY 의 저장소
    폴더, 환경은 HOST_ENV + Dockerfile ENV + compose environment(주소만 이 PC) + overrides. 포트는 PORTS[서비스], 준비 확인은 compose
    healthcheck 의 주소. 로그는 log_dir/<서비스>.log — 뜨지 않으면 그 끝을 싣고 실패한다."""

    def __init__(self, service, log_dir, overrides=None):
        spec = _compose_service(service)
        copies, image_env, cmd = _dockerfile(service)
        health = re.search(r"http://localhost:(\d+)(/[^'\"]*)", ' '.join(spec['healthcheck']['test']))
        self.service, self.port, self.url = service, PORTS[service], _local_url(service)
        self.health = self.url + health[2]
        env = dict(HOST_ENV, PYTHONUTF8='1', PYTHONPATH=os.pathsep.join(_python_path(copies)))
        env.update(_image_env(copies, image_env))
        env.update({k: here(_compose_default(v)) for k, v in (spec.get('environment') or {}).items()})
        env.update(MCP_PORT=str(self.port), **(overrides or {}))
        self.command = self._command(cmd, health[1])
        self.log_path = Path(log_dir) / f'{service}.log'
        self.log = open(self.log_path, 'wb')
        self.proc = subprocess.Popen(self.command, cwd=str(log_dir), env=env, stdout=self.log, stderr=subprocess.STDOUT)

    def _command(self, cmd, container_port):
        head = [sys.executable, '-m', 'uvicorn'] if cmd[0] == 'uvicorn' else [sys.executable] if cmd[0] == 'python' else None
        if head is None:
            raise ValueError(f'{self.service} Dockerfile 의 CMD {cmd} 를 이 PC 에서 띄우는 법을 모른다')
        args = list(cmd[1:])
        for flag, value in (('--host', '127.0.0.1'), ('--port', str(self.port))):
            if flag in args:
                args[args.index(flag) + 1] = value
        return head + args

    def tail(self):
        self.log.flush()
        return self.log_path.read_bytes().decode('utf8', 'replace')[-3000:]

    def ready(self):
        import urllib.request
        with urllib.request.urlopen(self.health, timeout=3) as r:
            return r.status == 200

    def wait(self):
        end, last = time.monotonic() + SERVICE_BOOT_S, None
        while True:
            try:
                if self.ready():
                    return self
            except Exception as exc:  # noqa: BLE001 — 아직 뜨는 중이면 다시 묻는다. 한도를 넘으면 그 오류를 까닭으로 싣는다
                last = exc
            if self.proc.poll() is not None or time.monotonic() > end:
                raise RuntimeError(f'테스트 서비스 {self.service}({" ".join(self.command)})가 {SERVICE_BOOT_S}초 안에 {self.health} 로 답하지 '
                                   f'않았다(종료 코드 {self.proc.poll()}, 마지막 오류 {type(last).__name__ if last else "-"}: {last}):\n{self.tail()}')
            time.sleep(0.2)

    @contextlib.contextmanager
    def paused(self):
        """이 서비스가 답하지 않는 동안(느린 서비스 · 콜드스타트): 프로세스를 멈춰 두고, 블록을 나가면 다시 돌린다.
        wait_client(timeout): 이 테스트 프로세스가 그 서비스에 연결해 답을 기다리기 시작할 때까지 기다린다."""
        import psutil
        me = psutil.Process()
        launcher = psutil.Process(self.proc.pid)
        frozen = [launcher, *launcher.children(recursive=True)]   # Windows venv 의 python.exe 는 런처라 실제 서버는 그 자식이다
        for proc in frozen:
            proc.suspend()
        try:
            yield _NS(wait_client=lambda timeout=30: until(
                lambda: any(c.raddr and c.raddr.port == self.port and c.status == psutil.CONN_ESTABLISHED for c in me.net_connections('tcp')),
                f'{self.service} 에 연결한 요청이 {timeout}초 안에 없었다', timeout))
        finally:
            for proc in reversed(frozen):
                proc.resume()

    def close(self):
        # Windows venv 의 python.exe 는 런처라 실제 서버는 그 자식이다 — 런처만 끄면 서버가 남아 포트를 잡고, 다음 묶음의 같은 서비스가
        # 그 포트로 뜨지 못한다(2026-11-01 실측: 묶음이 끝난 뒤 entsim · agentsvc · dmn-mcp · enterprise-mcp 서버가 부모 없이 남음). 자식부터 끈다.
        import psutil
        if self.proc.poll() is None:
            try:
                children = psutil.Process(self.proc.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                children = []
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            psutil.wait_procs(children, timeout=10)
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(10)
        self.log.close()


class FakeRelay:
    """강의 중계 자리(묶음의 것은 PORTS['relay'] — process 가 받은 LLM_RELAY_URL). 받은 요청(method · path · 소문자 머리글 · 본문)을 남기고,
    정한 응답을 차례로 준다(마지막 것은 계속). 기본은 짧은 Anthropic 메시지 200. 응답은 (상태, 본문) 또는 (상태, 본문, content-type) —
    스트리밍(SSE) 답은 bytes 본문과 'text/event-stream'."""
    OK = {'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'coding', 'content': [{'type': 'text', 'text': 'ok'}],
          'stop_reason': 'end_turn', 'usage': {'input_tokens': 1, 'output_tokens': 1}}

    def __init__(self, port=0):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        relay = self
        self.requests, self.replies = [], [(200, self.OK)]

        class Handler(BaseHTTPRequestHandler):
            def _answer(self):
                body = self.rfile.read(int(self.headers.get('content-length') or 0))
                relay.requests.append({'method': self.command, 'path': self.path, 'body': body,
                                       'headers': {k.lower(): v for k, v in self.headers.items()}})
                status, reply, *kind = relay.replies.pop(0) if len(relay.replies) > 1 else relay.replies[0]
                if isinstance(reply, list):            # 조각 스트림: bytes 는 보내고 수는 그만큼 쉰다(실제 중계가 답을 나눠 보내듯) — 길이 머리글 없이 닫아 끝낸다
                    self.send_response(status)
                    self.send_header('content-type', kind[0] if kind else 'text/event-stream')
                    self.end_headers()
                    for part in reply:
                        if isinstance(part, bytes):
                            self.wfile.write(part)
                            self.wfile.flush()
                        else:
                            time.sleep(part)
                    self.close_connection = True
                    return
                data = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
                self.send_response(status)
                self.send_header('content-type', kind[0] if kind else 'application/json')
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _answer

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def answer(self, status, body, content_type=None):
        self.plan([(status, body, content_type) if content_type else (status, body)])

    def plan(self, replies):
        """차례로 낼 (상태 코드, 본문) 목록 — 마지막 것은 그 뒤 요청에도 계속 낸다."""
        self.replies = list(replies)

    def reset(self):
        self.requests.clear()
        self.replies = [(200, self.OK)]


class FakeSmtp:
    """SMTP 자리(Inbucket 대신): 받은 메일 본문을 남긴다."""
    def __init__(self):
        import socketserver
        smtp, self.messages = self, []

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.wfile.write(b'220 test smtp\r\n')
                data = None
                while True:
                    line = self.rfile.readline()
                    if not line:
                        return
                    if data is not None:
                        if line in (b'.\r\n', b'.\n'):
                            smtp.messages.append(b''.join(data).decode('utf8', 'replace'))
                            data = None
                            self.wfile.write(b'250 queued\r\n')
                        else:
                            data.append(line)
                        continue
                    cmd = line[:4].upper()
                    if cmd in (b'EHLO', b'HELO'):
                        self.wfile.write(b'250 test\r\n')
                    elif cmd == b'DATA':
                        data = []
                        self.wfile.write(b'354 go\r\n')
                    elif cmd == b'QUIT':
                        self.wfile.write(b'221 bye\r\n')
                        return
                    else:
                        self.wfile.write(b'250 ok\r\n')
        self.server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def student_host():
    """이 PC 의 루프백이 아닌 IPv4 주소 하나 — 학생 서버 대역을 띄우는 자리(process 는 학생 서버의 루프백 주소를 거절한다: 컨테이너 안의
    루프백은 process 자신이다). 없으면(망 연결 없는 PC) 그 테스트를 돌릴 수 없어 까닭을 내고 실패한다."""
    addresses = sorted({info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
    usable = [a for a in addresses if not a.startswith('127.')]
    if not usable:
        pytest.fail(f'이 PC 에 루프백이 아닌 IPv4 주소가 없다({addresses}) — 학생 서버 대역을 띄울 자리가 없어 이 테스트를 돌리지 못했다', pytrace=False)
    return usable[0]


def __getattr__(name):
    """`from conftest import STUDENT_HOST` — 쓰는 테스트 파일을 가져올 때 student_host() 로 정한다(그 주소가 없으면 그 파일만 실패)."""
    if name == 'STUDENT_HOST':
        return student_host()
    raise AttributeError(name)


class Served:
    """ASGI 앱 하나를 이 PC 포트에서 띄운다(uvicorn, 테스트 묶음 동안). lifespan='off' 면 앱의 시작 훅을 부르지 않는다.
    host: 묶을 주소(기본 127.0.0.1 — 학생 서버 대역은 STUDENT_HOST, 그 주소에만 묶여 다른 주소로는 열리지 않는다)."""

    def __init__(self, app, *, port=None, lifespan='on', host='127.0.0.1'):
        import uvicorn
        self.port = port or _free_port()
        self.server = uvicorn.Server(uvicorn.Config(app, host=host, port=self.port, log_level='warning', lifespan=lifespan))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        until(lambda: self.server.started, f'서버가 {self.port} 에서 뜨지 않았다')
        self.url = f'http://{host}:{self.port}'

    def close(self):
        self.server.should_exit = True
        self.thread.join(timeout=10)


@pytest.fixture(scope='session')
def worker_key(tmp_path_factory):
    """process · 워커가 함께 보는 실행기 인증 파일(테스트 묶음의 것) — process 는 HYD_WORKER_RUNTIME_KEY_FILE 로 읽는다(묶음 끝에 되돌림)."""
    path = tmp_path_factory.mktemp('runtime') / 'runtime.key'
    path.write_text(WORKER_KEY, encoding='utf8')
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('HYD_WORKER_RUNTIME_KEY_FILE', str(path))
        yield path


@pytest.fixture(scope='session')
def relay():
    fake = FakeRelay(PORTS['relay'])
    yield fake
    fake.server.shutdown()


@pytest.fixture(scope='session')
def smtp():
    fake = FakeSmtp()
    yield fake
    fake.server.shutdown()


def _tenant_mcp(dsn):
    """시드의 테넌트 도구 서버 설정(seed.sql · 마이그레이션이 정본)을 이 PC 의 서비스 주소로. enterprise 에는 인증 머리글을 싣는다."""
    import psycopg
    with psycopg.connect(dsn, autocommit=True) as db:
        (config,) = db.execute('SELECT mcp FROM tenants WHERE id=%s', (TENANT,)).fetchone()
        servers = json.loads(here(json.dumps(config)))['mcpServers']
        servers['enterprise']['headers'] = {'Authorization': SERVER_SECRET}
        db.execute('UPDATE tenants SET mcp=%s WHERE id=%s', (json.dumps({'mcpServers': servers}), TENANT))
    return servers


@pytest.fixture(scope='session')
def stack(pg_dsn, graph_server, timescale, brokers, smtp, relay, worker_key, tmp_path_factory):
    """학생 PC 의 서비스들(우리 코드)을 이 PC 에서 띄운다: connect-ingest(설비 데이터 수집기 — 실제 MQTT · Kafka 브로커에 붙음) · agent ·
    dmn-mcp(+neo4j 도구) · enterprise-mcp 셋 · enterprise-sim · effects-mcp(하위 프로세스) + process 앱(이 프로세스 안, PORTS['process']).
    → 주소 · 대체물 · 서비스 손잡이."""
    from procsvc import main
    logs = tmp_path_factory.mktemp('services')
    ingest = _local_url('connect-ingest', '/healthz')
    overrides = {'effects-mcp': {'SMTP_HOST': '127.0.0.1', 'SMTP_PORT': str(smtp.port), 'EFFECTS_STATE_PATH': str(logs / 'effects.sqlite3'),
                                 'PROCESS_CALLER_TOKEN': CALLER_TOKEN},
                 'enterprise-sim': {'PROCESS_CALLER_TOKEN': CALLER_TOKEN},
                 # compose 값 MQTT_HOST=emqx · KAFKA_BOOTSTRAP=redpanda:9092 는 scheme 없는 이름이라(here 가 못 바꿈) 이 PC 의 브로커 입구로.
                 # agent 의 INGEST_URL 은 코드 기본값(컨테이너 이름)
                 'connect-ingest': {'MQTT_HOST': brokers.mqtt[0], 'MQTT_PORT': str(brokers.mqtt[1]), 'KAFKA_BOOTSTRAP': brokers.kafka},
                 'agent': {'INGEST_URL': ingest}}
    names = ('connect-ingest', 'enterprise-sim', 'effects-mcp', 'agent', 'dmn-mcp', 'enterprise-mcp', 'enterprise-mcp-maint', 'enterprise-mcp-purchase')
    services = {}
    try:
        for name in names:
            services[name] = ServiceProcess(name, logs, overrides.get(name))
        for service in services.values():
            service.wait()
        process = Served(main.app, port=PORTS['process'], lifespan='off')     # 기동은 테스트가 main.restore_and_build 로(EngineWorld)
        # 설비 시뮬레이터 HTTP(plant-sim — 정비 수행 모사 svc:maintenance 의 복구 요청 POST /api/fault 를 받는 자리). 시작 훅을 부르지 않아
        # MQTT 로 상태를 내지 않는다 — 설비 상태 · 태그는 EngineWorld.plant · tag 가 보고한다(그 보고와 겹치지 않게)
        with pytest.MonkeyPatch.context() as env:                            # 가져올 때 읽는 compose 의 plant-sim 환경(배속 · DAQ 판)
            for key, value in _compose_service('plant-sim')['environment'].items():
                if key != 'MQTT_HOST':
                    env.setenv(key, str(value))
            import importlib
            plant_main = importlib.import_module('plantsim.main')
        plant_sim = Served(plant_main.app, port=PORTS['plant-sim'], lifespan='off')
    except BaseException:
        for service in services.values():
            service.close()
        raise
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('PROCESS_STATE_PATH', str(tmp_path_factory.mktemp('process-data') / 'process.sqlite3'))   # 문서 원문 보관 등의 이웃 파일 자리
        yield _NS(dsn=pg_dsn, graph=graph_server, timescale=timescale, smtp=smtp, relay=relay, worker_key=worker_key,
                  services=services, process_url=process.url, ent=services['enterprise-sim'].url,
                  effects=services['effects-mcp'].url + '/mcp', tools=_tenant_mcp(pg_dsn))
    process.close()
    plant_sim.close()
    for service in services.values():
        service.close()


@pytest.fixture(scope='session')
def tool_servers(stack):
    """테넌트의 도구 서버 이름 → 이 PC 의 실제 서버 주소(neo4j · enterprise · hyd-dmn · enterprise-maint · enterprise-purchase)."""
    return {name: spec['url'] for name, spec in stack.tools.items()}


# ---------------------------------------------------------------- 처리 엔진(process)
class EngineClock:
    """바깥 시계 자리(처리 엔진 instances.InstanceRuntime(clock=…) · 수업 장부 · 단계 선언처럼 시계를 받는 코드). at 에서(없으면 지금
    벽시계에서) 시작해 테스트가 옮긴다(advance · at 직접)."""
    def __init__(self, at=None):
        self.at = at or datetime.now(timezone.utc)

    def __call__(self):
        return self.at

    def advance(self, seconds):
        self.at += timedelta(seconds=seconds)
        return self.at


class KafkaRecorder:
    """aiokafka 송신기 자리: send 는 브로커 응답 future 를 돌려준다. fail 에 넣은 토픽은 실패로 답한다."""
    def __init__(self):
        self.sent, self.fail, self.stopped = [], set(), False

    async def send(self, topic, key=None, value=None):
        fut = asyncio.get_running_loop().create_future()
        if topic in self.fail:
            fut.set_exception(ConnectionError(f'{topic} 브로커가 받지 않았다(시험)'))
        else:
            self.sent.append((topic, key, value))
            fut.set_result({'topic': topic})
        return fut

    def of(self, topic):
        return [v for t, _, v in self.sent if t == topic]

    async def stop(self):
        """aiokafka 송신기의 닫기 자리(process 끄기가 부른다) — 불렸는지 stopped 로 남긴다."""
        self.stopped = True


def _run_async(coro):
    """process 의 비동기 경로 하나를 새 스레드의 새 이벤트 루프에서 끝까지 돌린다(서버의 요청 처리 스레드 자리). 시험 스레드에 이미 다른 루프가
    돌고 있어도(세션 동안 열린 동기 playwright 브라우저 등) 같은 길이다 — 예외는 그대로 시험으로 올린다."""
    box = {}

    def run():
        try:
            box['value'] = asyncio.run(coro)
        except BaseException as error:  # noqa: BLE001 — 시험 스레드에서 다시 올린다
            box['error'] = error
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if 'error' in box:
        raise box['error']
    return box['value']


class _LoopThread:
    """process 의 이벤트 루프 자리(main.loop) — Kafka 송신 · 사건 갱신 예약이 이 루프에서 돈다."""
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=10)


def rejected_first_replay(tmp_path):
    """시험이 스스로 만든 강사 녹화 묶음: 저장소 녹화를 그대로 복사하되 교대 초안(handover/draft-1)에는 「검사에 거절될 첫 실행 → 고친 둘째 실행」
    두 실행을 둔다. 첫 실행은 저장소의 실행을 복사해 확인 항목 하나의 근거 번호를 근거 목록 밖으로 바꾼 것(process 검사 handover.py 가
    「근거 번호는 … 유효한 번호」로 돌려보낸다). 강사가 다시 녹화하면 실제 AI 가 첫 답부터 맞혀 이 순서가 저장소 녹화에 없을 수 있어,
    재시도 동작은 이 녹화로 판정한다(2026-11-01 — 시험이 강사 녹화의 내용에 기댔다). 저장소 녹화는 바꾸지 않는다."""
    import copy
    import gzip
    out = tmp_path / 'replay-rejected-first'
    shutil.copytree(REPLAY_DIR, out)
    for path in out.glob('*.json.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            doc = json.load(f)
        if (doc['slot'], doc['case']) != ('handover/draft-1', ''):
            continue
        good = doc['runs'][-1]
        bad = copy.deepcopy(good)
        result = json.loads(bad['result_file'])
        result['checks'][0]['evidence_indices'] = [len(result['evidence'])]       # 근거 목록 밖 번호
        bad['result_file'] = json.dumps(result, ensure_ascii=False, indent=2)
        bad['session_id'] = str(uuid.uuid4())
        doc['runs'] = [bad, good]
        with gzip.open(path, 'wt', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False)
        return out
    raise AssertionError('저장소에 교대 초안(handover/draft-1) 녹화가 없다 — 강사 녹화를 다시 저장한다(record_replay.sh)')


def recording(slot, case=''):
    """저장소 녹화 하나(수업 AI 자리 · 처리 건 종류로 찾는다 — 워커와 같은 열쇠 함수)."""
    from worker import ai_replay
    return ai_replay.Library(REPLAY_DIR).load(ai_replay.course_key(slot, case))


def model_turns(run):
    """녹화 실행에서 CLI 가 모델을 부른 횟수(stream_event message_start)."""
    return sum(1 for e in run['events'] if e['kind'] == 'unknown' and (e.get('raw') or {}).get('type') == 'stream_event'
               and ((e['raw'].get('event') or {}).get('type') == 'message_start'))


def make_runner(dsn, process_url, worker_key, mode, cli=None, *, root, replay_dir=REPLAY_DIR, consumer='test-worker'):
    """실제 Runner 하나(시드 테넌트 hyd, 실제 DB · process · 관문 · 녹화 · 같은 요청 저장 폴더). cli 는 키 있는 PC 의 CLI 자리(RecordedCli)."""
    import dataclasses
    from procsvc import procdb
    from worker import ai_replay
    from worker.course_access import CourseAccess
    from worker.runner import Runner
    from worker.settings import Settings
    s = dataclasses.replace(Settings(), tenant_id=TENANT, consumer=consumer, supabase_dsn=dsn, process_url=process_url,
                            runtime_key_file=str(worker_key), workspace_root=root, mcp_host_rewrite='', ai_mode=mode, ai_replay_dir=replay_dir)
    responses = ai_replay.Responses(mode, course=ai_replay.Library(replay_dir, ai_replay.COURSE),
                                    cache=ai_replay.Library(s.ai_cache_dir, ai_replay.REUSE))
    return Runner(s, procdb.PgRepo(dsn), responses=responses, course=CourseAccess(s.process_url, s.runtime_key_file),
                  exec_fn=cli, schema_prompt='(테스트 스키마 설명)', resolve_provider=lambda: _NS(id='claude-code', display_name='Claude Code'))


class EngineWorld:
    """process 한 번의 기동(시드 테넌트 hyd). restart() 는 같은 DB · 같은 사건 저장 파일로 process 를 다시 켠 것과 같다.
    plant 는 실제 설비 모델(plantsim.plant.Plant) — report() 가 그 상태 · 태그를 process 가 읽는 길로 보고한다."""

    def __init__(self, stack, tmp_path):
        import psycopg
        from plantsim.plant import Plant
        self.stack, self.tmp, self.dsn, self.url = stack, tmp_path, stack.dsn, stack.process_url
        self.clock, self.kafka = EngineClock(), KafkaRecorder()
        self.offsets = itertools.count(int(time.time() * 1000))
        self.tick = 0
        self.plant = Plant(time_scale=float(os.environ['TIME_SCALE']))
        with psycopg.connect(self.dsn, autocommit=True) as db:      # 앞 시험의 진행 중 일 · 설비 최신 상태가 이 시험에 끼지 않게
            db.execute("UPDATE bpm_proc_inst SET status='CANCELLED' WHERE status='RUNNING'")
            db.execute("UPDATE process_source_inbox SET status='FAILED', error='앞 시험의 남은 접수' "
                       "WHERE status IN ('PENDING','WAITING','CLAIMED')")
            db.execute('DELETE FROM process_source_state WHERE tenant_id=%s', (TENANT,))
        stack.timescale.clear()
        from procsvc import engine
        self._compression_before = engine.wait_compression()     # 기동(instance_mode.build)이 프로세스 전역 대기 압축을 정한다 — 닫을 때 되돌린다
        self._boot()
        self.install_course_flows()

    # ------------------------------------------------------------ 기동
    def _boot(self):
        from procsvc import instance_mode, main, procdb
        self.main, self.instance_mode = main, instance_mode
        self.loop_thread = _LoopThread()
        main.loop, main.producer = self.loop_thread.loop, self.kafka        # 이벤트 루프 · Kafka 송신기는 부르는 쪽이 정한다(restore_and_build)
        self.rt = _run_async(main.restore_and_build(main.instance_context(), state_path=str(self.tmp / 'process.sqlite3'),
                                                    repo=procdb.PgRepo(self.dsn), clock=self.clock))

    def restart(self):
        """process 를 다시 켠다: 메모리(사건 · 판단 사전, 이벤트 루프)는 사라지고 사건 저장 파일 · DB 는 남는다."""
        self.close()
        self._boot()

    def close(self):
        from procsvc import engine
        # 끄기(main._shutdown)와 같은 차례: 작업 스레드의 처리 건 갱신이 끝난 뒤 루프를 멈추고 저장소를 닫는다 — 기다리지 않으면 앞 world 의
        # on_incident_update 가 다음 테스트 준비 중에 돌았다(FA1 검증 §4-6, 관측 9번)
        asyncio.run_coroutine_threadsafe(self.main.drain_scheduled_updates(), self.loop_thread.loop).result(timeout=120)
        self.loop_thread.close()
        self.main.store.db.close()
        engine.configure_wait_compression(self._compression_before)   # world 뒤에 도는 테스트가 기동의 압축(60)을 물려받지 않게

    def install_course_flows(self):
        """제공 수업 흐름 A · B · C 를 시작과 같은 길로 설치(scripts/c3_flows.ensure → POST /api/course-bootstrap). 이미 설치돼 있으면 서버가 건너뛴다."""
        import c3_flows
        assert c3_flows.ensure(self.url) == 0, '수업 흐름 설치가 0으로 끝나지 않았다(까닭은 위 표준 오류)'

    def api(self, method, path, body=None, *, source_loop=False):
        """process 의 HTTP 경로를 서버 안에서 부른다(포털 · 강사 스크립트와 같은 라우트 · 같은 수업 경계 문지기). 돌려줌 = (상태, 본문).
        source_loop: 그동안 process 의 원천 처리 루프(main.source_loop)도 함께 돈다 — 경보 접수를 기다리는 경로용."""
        import httpx

        async def call():
            loop_task = asyncio.create_task(self.main.source_loop()) if source_loop else None
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.main.app), base_url='http://process', timeout=60) as client:
                    return await client.request(method, path, json=body)
            finally:
                if loop_task is not None:
                    loop_task.cancel()
        response = _run_async(call())
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, response.text

    def import_flow(self, definition_id, xml, mapping, file_name, by=OPERATOR['by']):
        """bpmn.io 그림 하나를 흐름 가져오기(가져오기 → 사전 검사 → 등록)로 넣는다 — 등록은 포털처럼 고른 사람(by) 이름으로. 돌려줌 = 등록한 판본."""
        status, body = self.api('POST', '/api/flows/import', {'xml': xml, 'file_name': file_name, 'definition_id': definition_id})
        assert status == 200, body
        status, body = self.api('POST', f'/api/flows/{definition_id}/register', {'mapping': mapping, 'by': by})
        assert status == 201, body
        return body['version']

    def storage_fails(self, table, condition):
        """저장소(PostgreSQL) 쪽 실패를 일으킨다: table 의 INSERT · UPDATE 가운데 condition(NEW 행에 대한 SQL)이 참인 쓰기를 거절하는
        트리거를 걸고, with 블록이 끝나면 지운다. 우리 코드는 그대로 두고 바깥(DB)만 실패시킨다."""
        import psycopg
        name = 'engine_test_fail_' + uuid.uuid4().hex[:8]

        @contextlib.contextmanager
        def failing():
            with psycopg.connect(self.dsn, autocommit=True) as db:
                db.execute(f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {condition} THEN "
                           f"RAISE EXCEPTION '시험: 저장소가 이 쓰기를 거절함'; END IF; RETURN NEW; END $$")
                db.execute(f'CREATE TRIGGER {name} BEFORE INSERT OR UPDATE ON public.{table} FOR EACH ROW EXECUTE FUNCTION {name}()')
            try:
                yield
            finally:
                with psycopg.connect(self.dsn, autocommit=True) as db:
                    db.execute(f'DROP TRIGGER IF EXISTS {name} ON public.{table}')
                    db.execute(f'DROP FUNCTION IF EXISTS {name}()')
        return failing()

    # ------------------------------------------------------------ 원천(경보 · 설비 상태)
    def now_iso(self):
        return self.clock().isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def receive(self, topic, payload):
        """Kafka 한 건을 process 의 원천 받기(main.receive_records — consume 과 같은 함수: 정책 고르기 · 접수 · 설비 최신 상태)로 넣고,
        접수 행이 생겼으면 원천 처리기(SourceDelivery.run_once)를 끝날 때까지 돌린다. 돌려줌 = 그 레코드의 접수 행(설비 상태처럼 접수 행을
        남기지 않는 것은 None). 받기가 RECEIVE_S 안에 끝나지 않으면(process 는 실패한 접수를 1초마다 다시 한다) 그 까닭과 함께 실패한다."""
        import psycopg
        rec = _NS(topic=topic, partition=0, offset=next(self.offsets), value=json.dumps(payload, ensure_ascii=False).encode())
        try:
            _run_async(asyncio.wait_for(self.main.receive_records([rec]), RECEIVE_S))
        except TimeoutError:
            raise AssertionError(f'원천 받기가 {RECEIVE_S}초 안에 끝나지 않았다: {self.main.state.get("source_receive_error")}') from None
        with psycopg.connect(self.dsn) as db:
            row = db.execute('SELECT id, kind FROM process_source_inbox WHERE tenant_id=%s AND topic=%s AND partition_no=%s AND offset_no=%s',
                             (TENANT, topic, rec.partition, rec.offset)).fetchone()
        if row is None:
            return None
        if row[1] in ('RAISE', 'CLEAR', 'ACK', 'REJECT'):
            self.deliver()
        return self.main.source_inbox.get(row[0])

    def deliver(self):
        async def drain():
            while await self.main.source_delivery.run_once() is not None:
                pass
        _run_async(drain())

    def report(self, *assets):
        """설비가 지금 보고한다(plant-sim 의 1초 보고 한 번): 설비 상태(plant.status — 벽시계 시각)는 원천 접수로, 태그 값은 시계열 tag_1s 로."""
        from hydcommon import topics
        for asset in assets or tuple(self.plant.units):
            self.stack.timescale.write(asset, self.plant.tags(asset))
            self.receive(topics.K_STATUS, self.plant.status(asset))

    def reported_for(self, asset, seconds=1800):
        """설비가 지난 seconds 초 동안 1초마다 지금 태그 값을 보고한 시계열(connect-sink 가 tag_1s 에 쓰는 것과 같은 행) — 근거 규칙의
        관측 구간(windowSeconds)을 덮는다. 한 번 보고로는 구간이 비어 근거가 「관측 공백」이 된다. 끝에 지금 보고 한 번."""
        import psycopg
        tags = self.plant.tags(asset)
        with psycopg.connect(self.stack.timescale.dsn, autocommit=True) as db:
            db.execute('INSERT INTO tag_1s(time, asset, name, value) SELECT now() - make_interval(secs => s), %s, t.name, t.value::double precision '
                       'FROM generate_series(1, %s) s, jsonb_each_text(%s::jsonb) AS t(name, value)',
                       (asset, seconds, json.dumps({k: float(v) for k, v in tags.items()})))
        self.report(asset)

    @contextlib.contextmanager
    def reporting(self, asset):
        """이 블록 동안 설비가 실제처럼 1초마다 태그 값을 계속 보고한다(plant-sim 의 1초 보고 — 시계열 tag_1s). 판단 엔진의 관측 구간 근거는
        마지막 값과 지금 사이가 보고 간격 + 여유(약 3초)를 넘으면 「관측 공백」으로 보류한다(agentsvc mcp_tsdb.observation_coverage) —
        한 번 넣은 30분 기록만으로는 판단을 여러 번 도는 사이 그 3초가 지나 보류됐다(2026-11-01 전체 실행 6, test_eval_api)."""
        stop = threading.Event()

        def loop():
            while not stop.wait(1.0):
                self.stack.timescale.write(asset, self.plant.tags(asset))
        worker = threading.Thread(target=loop, name=f'report-{asset}', daemon=True)
        worker.start()
        try:
            yield
        finally:
            stop.set()
            worker.join(timeout=5)

    def settle(self, sim_seconds):
        """설비 모델을 설비 시간으로 sim_seconds 만큼 돌린다(배속 그대로 — 벽시계 sim_seconds / TIME_SCALE 초 분량)."""
        self.plant.tick(sim_seconds / self.plant.time_scale)

    def raise_alert(self, pattern, asset, **evidence):
        from hydcommon import topics
        alert = {'alertId': f'ALT-{asset}-{uuid.uuid4().hex[:10]}', 'asset': asset, 'pattern': pattern, 'state': 'RAISE',
                 't': self.now_iso(), 'severity': 'WARN', **({'evidence': evidence} if evidence else {})}
        receipt = self.receive(topics.K_ALERTS, alert)
        assert receipt['status'] == 'HANDLED', receipt
        return alert, receipt['result']['instance']

    def clear_alert(self, alert):
        from hydcommon import topics
        return self.receive(topics.K_ALERTS, dict(alert, state='CLEAR', t=self.now_iso()))

    def ack(self, asset, cmd_id, result='DONE', reason=None):
        """설비의 명령 응답(plant.status 에 실림 — report() 의 설비 상태와 같은 설비 시계 = 벽시계). 엔진 시계를 쓰면 두 시계가 섞인다:
        엔진 시계가 뒤면 앞선 보고보다 옛 상태로 버려지고, 앞서 있으면 그 뒤 보고가 최신 상태를 못 고친다(source_inbox._keep_latest_state)."""
        from hydcommon import topics
        at = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        return self.receive(topics.K_STATUS, {'asset': asset, 't': at, 'cmdId': cmd_id, 'result': result,
                                              'reason': reason, 'mode': 'REMOTE_AUTO', 'state': 'RUN'})

    def tag(self, asset, name, value):
        """시계열 tag_1s 에 1초 값 하나(시각 = 시계열 DB 의 지금) — 재관측 · 시운전이 읽는다."""
        self.stack.timescale.write(asset, {name: value})

    # ------------------------------------------------------------ 엔진
    def poll(self, rounds=1):
        """엔진 폴링 한 바퀴(instance_mode.poll_round — 실행 서비스의 2초 폴링과 같은 일)를 rounds 번. 돌려줌 = 실패한 일 이름들."""
        failed = []
        for _ in range(rounds):
            self.tick += 1
            failed += self.instance_mode.poll_round(self.rt, self.tick)
        return failed

    def inst(self, pid):
        return self.rt.repo.get_instance(pid)

    def values(self, pid):
        from procsvc import engine
        return engine.variables(self.inst(pid))

    def rows(self, pid):
        return self.rt.repo.list_workitems(proc_inst_id=pid, limit=None)

    def row(self, pid, activity, status=None):
        rows = [w for w in self.rows(pid) if w['activity_id'] == activity and (status is None or w['status'] == status)]
        assert rows, f'{pid} 에 {activity}({status or "아무 상태"}) 행이 없다: {[(w["activity_id"], w["status"]) for w in self.rows(pid)]}'
        return rows[-1]

    def events(self, pid=None, todo=None, job=None):
        return [e for e in self.rt.repo.list_events(proc_inst_id=pid, todo_id=todo, limit=5000) if job is None or e['job_id'] == job]

    def incident(self, pid):
        return self.main.incidents[self.values(pid)['incident']]

    # ------------------------------------------------------------ 에이전트 단계 · 사람 승인
    def runner(self, mode, cli=None, *, consumer=None, replay_dir=REPLAY_DIR):
        return make_runner(self.dsn, self.url, self.stack.worker_key, mode, cli, root=self.tmp / 'workspace', replay_dir=replay_dir,
                           consumer=consumer or 'engine-test-worker:' + uuid.uuid4().hex[:8])

    def agent(self, pid, activity, cli=None):
        """AI 워커 한 번: 설비가 지금 보고하고 → 실제 Runner 가 그 단계를 점유해 실행하고 결과를 제출 → 엔진 폴링.
        cli 가 없으면 키 없는 PC(재생 모드 — 강사 녹화를 이 처리 건 값으로 내고, 쓰기 도구는 이 PC 의 dmn-mcp 를 다시 불러 판단을 실제로 등록),
        있으면 키 있는 PC(cli = RecordedCli — 관문 · 강의 중계 자리를 실제로 지난다). 돌려줌 = 이 처리 건에 등록된 판단 id(없으면 None)."""
        self.report()
        handled = self.runner('live' if cli else 'replay', cli).poll_once()
        row = self.row(pid, activity)
        assert handled == 1 and row['status'] in ('SUBMITTED', 'DONE'), (handled, row['status'], self._failure(row))
        self.poll()
        made = [d for d in self.main.book.values() if ((d.get('origin') or {}).get('process_scope') or {}).get('instance') == pid]
        return max(made, key=lambda d: d.get('created') or '')['id'] if made else None

    def _failure(self, row):
        errors = [e for e in self.events(todo=row['id']) if e['event_type'] == 'error']
        return errors[-1]['data'] if errors else None

    def approve(self, pid, decision, option, who):
        """사람이 승인 카드를 고른다(포털의 승인과 같은 함수). 설비는 그동안에도 보고하고 있다 — 승인 현재 조건 검사(실제 agent)가 읽는
        최신 보고를 먼저 넣는다."""
        self.report()
        approve = self.row(pid, 'T_approve', 'IN_PROGRESS')
        return self.rt.select(approve['id'], decision, option, **who)

    def commanded(self, pid):
        """승인 뒤 process 가 보낸 마지막 설비 명령(사건은 ACK 대기)."""
        from hydcommon import topics
        cmd = self.kafka.of(topics.K_CMD)[-1]
        assert self.incident(pid).state == 'AWAITING_ACK', self.incident(pid).state
        return cmd

    def start_cooling(self):
        """흐름 A 의 시작: HYD-01 쿨러 오염(수업 강도 moderate)이 끝까지 진행돼 유온이 경보선 위에 머문 설비 → 냉각 성능 저하 경보 →
        처리 건 c3_cooling → 에이전트 단계. 돌려줌 = (경보, 처리 건 id, 판단 id)."""
        pattern, asset = COOLING
        self.plant.inject(asset, 'cooler_degradation', severity='moderate')
        self.settle(1800)
        tags = self.plant.tags(asset)
        alert, pid = self.raise_alert(pattern, asset, ts1=tags['TS1'], ce=tags['CE'])
        assert self.inst(pid)['proc_def_id'] == 'c3_cooling'
        return alert, pid, self.agent(pid, 'T_agent')


@pytest.fixture
def world(stack, course_graph, tmp_path):
    w = EngineWorld(stack, tmp_path)
    yield w
    w.close()


# ---------------------------------------------------------------- AI 워커
@pytest.fixture
def course(world, relay):
    """워커 테스트 하나의 시작 상태: 테넌트 hyd 의 처리 건 · 수업 장부 · 중계 기록이 비어 있다(process = world)."""
    import psycopg
    # 제품에는 처리 건을 지우는 길이 없다(기준으로 되돌리기는 is_deleted 표시, 보완 영수증 process_rework_receipt 는 바뀌지 않는 기록이라
    # 처리 건 삭제에 따라 지워지지 않는다 — 마이그레이션 010). 그래서 시험의 「빈 처리 건」은 영수증과 처리 건을 한 트랜잭션에서 지운다
    # (처리 건 → 영수증 FK 가 deferred 라 커밋 때 함께 맞는다. 나머지 딸린 표 todolist · 승인 보낼 함 · 효과 영수증 · 배정은 ON DELETE CASCADE).
    with psycopg.connect(world.dsn) as db, db.transaction():
        db.execute('DELETE FROM process_rework_receipt WHERE tenant_id=%s', (TENANT,))
        db.execute('DELETE FROM bpm_proc_inst WHERE tenant_id=%s', (TENANT,))
        db.execute('DELETE FROM hyd_course_runs')
        db.execute('DELETE FROM hyd_course_grants')
    relay.reset()
    return _NS(rt=world.rt, url=world.url, dsn=world.dsn, world=world,
               settings={'LLM_API_KEY': RELAY_KEY, 'LLM_RELAY_URL': relay.url, 'HYD_WORKER_RUNTIME_KEY_FILE': str(world.stack.worker_key)})


@pytest.fixture
def worker(course, tmp_path):
    """make(mode, cli=…) → 실제 Runner(시드 테넌트 hyd, 실제 DB · process · 관문 · 녹화 · 같은 요청 저장 폴더)."""
    def make(mode, cli=None, *, replay_dir=REPLAY_DIR, consumer='test-worker', root=None):
        return make_runner(course.dsn, course.url, course.world.stack.worker_key, mode, cli, root=root or tmp_path / 'workspace',
                           replay_dir=replay_dir, consumer=consumer)
    return make


def definition_version(file_name):
    """제공 정의 파일(it/process/definitions/<파일>)의 판본 — 정의가 판본을 올리면 테스트도 따라간다."""
    return json.loads((DEFINITIONS / file_name).read_text(encoding='utf8'))['version']


def start_handover(rt, *, asset='HYD-01', definition='shift_handover', version=None):
    """교대 인수인계 처리 건 하나(첫 AI 단계 = 인계안 작성). 판본을 주지 않으면 제공 정의 파일의 판본."""
    version = version or definition_version('shift_handover_v1.json')
    return rt.start_definition(definition, version, 'handover:' + uuid.uuid4().hex,
                               values={'asset': asset, 'shift_label': '다음 교대', 'as_of': datetime.now(timezone.utc).isoformat(),
                                       'work_notes': '작업 메모: 정비 완료라고 전달받음. 부품 도착 예정이라고 전달받음.'})


def ask_question(rt, question):
    from procsvc import ask
    return ask.start(rt, question, None, '수강생', definitions_dir=DEFINITIONS, worker_probe=lambda: {'reachable': True})


def events_of(rt, todo_id, event_type=None):
    return [e for e in rt.repo.list_events(todo_id=todo_id) if event_type is None or e['event_type'] == event_type]


def task_of(rt, proc_inst_id, activity=None):
    rows = rt.repo.list_workitems(proc_inst_id=proc_inst_id, limit=None)
    return next(w for w in rows if activity is None or w['activity_id'] == activity)


class RecordedCli:
    """Claude Code 자리: 정한 녹화 실행의 이벤트를 새 세션 id 로 내고, 결과 파일을 쓰고, 그 실행의 모델 호출 수만큼 관문(ANTHROPIC_BASE_URL ·
    실행 토큰)을 실제로 부른다. 관문이 거절하면 Claude Code 처럼 오류 결과(API Error: <상태> <본문>)로 끝난다.
    after(n, cli): n번째 이벤트를 낸 뒤 부르는 끼어들기(재점유 · 취소 흉내)."""
    accepts_check_stop = True

    def __init__(self, run, *, result_file=..., after=None, calls=None):
        """result_file: 녹화의 결과 파일(기본) · 글 · request → 글 함수 · None(쓰지 않음)."""
        self.run, self.after = run, after
        self.result_file = run.get('result_file') if result_file is ... else result_file
        self.calls = model_turns(run) if calls is None else calls
        self.requests = []

    def __call__(self, provider, request, env, *, check_stop=None):
        import urllib.error
        import urllib.request
        from cliagents import ExecEvent, ExecEventKind
        self.requests.append(_NS(request=request, env=dict(env or {})))
        session = str(uuid.uuid4())
        for _ in range(self.calls):
            body = json.dumps({'model': request.model, 'max_tokens': 1024, 'messages': [{'role': 'user', 'content': '다음 단계'}]}).encode()
            call = urllib.request.Request(env['ANTHROPIC_BASE_URL'] + '/v1/messages', data=body, method='POST',
                                          headers={'x-api-key': env['ANTHROPIC_API_KEY'], 'content-type': 'application/json'})
            try:
                with urllib.request.urlopen(call, timeout=15) as response:
                    response.read()
            except urllib.error.HTTPError as exc:
                yield ExecEvent(kind=ExecEventKind.RESULT, is_error=True, session_id=session,
                                text=f'API Error: {exc.code} {exc.read().decode("utf8", "replace")}')
                return
        if self.result_file is not None:
            target = Path(request.workdir) / 'output' / 'result.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.result_file if isinstance(self.result_file, str) else self.result_file(request), encoding='utf8')
        for n, d in enumerate(self.run['events'], 1):
            if check_stop:
                check_stop()
            yield ExecEvent(**dict(d, kind=ExecEventKind(d['kind']), session_id=session if d.get('session_id') else None))
            if self.after:
                self.after(n, self)
