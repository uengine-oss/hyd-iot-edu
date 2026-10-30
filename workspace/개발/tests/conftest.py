"""테스트 공통 준비 — 학생 PC 구성(instance 처리 엔진 + Supabase PostgreSQL + AI 워커)을 기준으로 한다.

실제 DB: 환경 변수 HYD_TEST_DSN 하나(예: postgresql://postgres:postgres@127.0.0.1:64322/hyd_test — 로컬 Supabase 안의 버릴 데이터베이스).
테스트 묶음이 시작할 때 그 데이터베이스를 지우고 다시 만든 뒤 it/supabase/migrations 전부와 seed.sql을 차례로 넣는다(학생 PC의
`supabase start` · `migration up`과 같은 내용). 이름이 postgres인 데이터베이스(강사 · 학생의 업무 DB)는 거절한다.
HYD_TEST_DSN이 없으면 DB가 필요한 테스트는 건너뛰지 않고 「무엇이 없어 못 돌았는지」를 적고 실패한다.

바깥만 대체한다: 강의 중계(LiteLLM) 자리는 저장소의 AI 응답 녹화본(it/agent-worker/replay/)을 내는 테스트용 서버, 시계는 고정 시각.
"""
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / 'it' / 'supabase' / 'migrations'
SEED = ROOT / 'it' / 'supabase' / 'seed.sql'
DSN_ENV = 'HYD_TEST_DSN'


def _admin_dsn(dsn):
    parts = urlsplit(dsn)
    return urlunsplit(parts._replace(path='/postgres'))


@pytest.fixture(scope='session')
def pg_dsn():
    """마이그레이션 · 시드가 막 들어간 버릴 데이터베이스의 주소."""
    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        pytest.fail(f'{DSN_ENV}가 없어 실제 DB 테스트를 돌리지 못했다 — 로컬 Supabase가 켜진 PC에서 '
                    f'{DSN_ENV}=postgresql://postgres:postgres@127.0.0.1:<DB 포트>/hyd_test 를 주고 다시 돌린다', pytrace=False)
    name = urlsplit(dsn).path.lstrip('/')
    if not name or name == 'postgres':
        pytest.fail(f'{DSN_ENV}의 데이터베이스 이름이 {name or "(없음)"}이다 — 업무 DB를 지우지 않도록 따로 만든 이름(예: hyd_test)만 받는다',
                    pytrace=False)
    import psycopg
    try:
        admin = psycopg.connect(_admin_dsn(dsn), autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as exc:
        pytest.fail(f'{DSN_ENV}의 서버에 닿지 않는다({exc.__class__.__name__}: {str(exc).strip()[:200]}) — Supabase를 켠다', pytrace=False)
    with admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')
    with psycopg.connect(dsn, autocommit=True) as conn:
        for sql in sorted(MIGRATIONS.glob('*.sql')) + [SEED]:
            try:
                conn.execute(sql.read_text(encoding='utf8'))
            except psycopg.Error as exc:
                pytest.fail(f'{sql.relative_to(ROOT)}를 새 DB에 넣지 못했다: {exc}', pytrace=False)
    return dsn


@pytest.fixture
def tenant():
    """테스트 하나만 쓰는 테넌트 이름(시드 테넌트 hyd의 데이터를 건드리지 않을 때)."""
    return 't' + uuid.uuid4().hex[:10]


# ---- worker ----
# AI 워커 · 로컬 중계 관문 · 녹화 재생 테스트의 공통 준비. 시스템 밖만 대체한다:
#   강의 중계(LiteLLM)  → FakeRelay(이 PC 포트의 HTTP 서버, 받은 요청을 센다 — 유료 중계를 부르지 않는다)
#   Claude Code CLI     → RecordedCli(저장소 녹화본의 실행 이벤트를 내고, 녹화의 모델 호출 수만큼 관문을 실제로 부른다)
#   업무 도구 서버(MCP) → mcp_servers(녹화가 쓴 도구 이름을 그대로 여는 FastMCP — 쓰기 도구는 새 id 를 돌려준다)
# process 쪽 수업 판정 · 관문 · 장부 · 처리 흐름과 워커 코드는 실제 코드 · 실제 DB(pg_dsn, 시드 테넌트 hyd)다.
import gzip as _gzip
import json as _json
import socket as _socket
import threading as _threading
import time as _time
from types import SimpleNamespace as _NS

REPLAY_DIR = ROOT / 'it' / 'agent-worker' / 'replay'
DEFINITIONS = ROOT / 'it' / 'process' / 'definitions'
WORKER_KEY = 'worker-runtime-test-' + 'w' * 40
RELAY_KEY = 'relay-test-key-' + 'k' * 30
WRITE_TOOLS = {('hyd-dmn', 'submit_decision'), ('hyd-dmn', 'submit_purchase')}
SERVER_SECRET = 'Bearer enterprise-test-secret-' + 's' * 24     # 테스트 테넌트의 enterprise 서버 인증 머리글(작업 폴더 .mcp.json 에 실린다)


def recording(slot, case=''):
    """저장소 녹화 하나(수업 AI 자리 · 처리 건 종류로 찾는다 — 워커와 같은 열쇠 함수)."""
    from worker import ai_replay
    return ai_replay.Library(REPLAY_DIR).load(ai_replay.course_key(slot, case))


def model_turns(run):
    """녹화 실행에서 CLI 가 모델을 부른 횟수(stream_event message_start)."""
    return sum(1 for e in run['events'] if e['kind'] == 'unknown' and (e.get('raw') or {}).get('type') == 'stream_event'
               and ((e['raw'].get('event') or {}).get('type') == 'message_start'))


def _free_port():
    with _socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _until(condition, what, timeout=15.0):
    end = _time.monotonic() + timeout
    while not condition():
        if _time.monotonic() > end:
            raise TimeoutError(what)
        _time.sleep(0.01)


class Served:
    """ASGI 앱 하나를 이 PC 포트에서 띄운다(uvicorn, 테스트 묶음 동안)."""

    def __init__(self, app):
        import uvicorn
        self.port = _free_port()
        self.server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=self.port, log_level='warning', lifespan='on'))
        self.thread = _threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        _until(lambda: self.server.started, f'서버가 {self.port} 에서 뜨지 않았다')
        self.url = f'http://127.0.0.1:{self.port}'

    def close(self):
        self.server.should_exit = True
        self.thread.join(timeout=10)


class FakeRelay:
    """강의 중계 자리. 받은 요청(경로 · 머리글 · 본문)을 남기고, 정한 응답을 준다(기본: 짧은 Anthropic 메시지 200)."""
    OK = {'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'coding', 'content': [{'type': 'text', 'text': 'ok'}],
          'stop_reason': 'end_turn', 'usage': {'input_tokens': 1, 'output_tokens': 1}}

    def __init__(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        relay = self
        self.requests, self.reply = [], (200, self.OK)

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = self.rfile.read(int(self.headers.get('content-length') or 0))
                relay.requests.append({'path': self.path, 'headers': dict(self.headers), 'body': body})
                status, reply = relay.reply
                data = reply if isinstance(reply, bytes) else _json.dumps(reply).encode()
                self.send_response(status)
                self.send_header('content-type', 'application/json')
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        _threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def answer(self, status, body):
        self.reply = (status, body)

    def reset(self):
        self.requests.clear()
        self.reply = (200, self.OK)


def _mcp_app(name, tools):
    """도구 서버 하나: tools = {도구: 쓰기냐}. 읽기는 readOnlyHint, 쓰기는 부를 때마다 새 문서 id 를 돌려준다(판단 · 발주 등록 자리)."""
    import uuid as _uuid
    from fastmcp import FastMCP
    from fastmcp.tools import Tool
    from fastmcp.tools.tool import ToolResult
    from mcp.types import TextContent, ToolAnnotations

    class Recorded(Tool):
        async def run(self, arguments):
            body = {'result': 'ok', 'document': {'id': f'{self.name}-{_uuid.uuid4().hex[:12]}'}} if writes[self.name] else {'result': 'ok'}
            calls.append((self.name, arguments))
            return ToolResult(content=[TextContent(type='text', text=_json.dumps(body))])
    writes, calls = dict(tools), []
    app = FastMCP('test ' + name)
    for tool, write in sorted(tools.items()):
        app.add_tool(Recorded(name=tool, description=f'{name} {tool}', parameters={'type': 'object', 'additionalProperties': True},
                              annotations=ToolAnnotations(readOnlyHint=not write, destructiveHint=write)))
    return app, calls


@pytest.fixture(scope='session')
def mcp_servers():
    """녹화 6개가 쓴 도구 서버(neo4j · enterprise · hyd-dmn · enterprise-maint · enterprise-purchase)를 그 도구 이름 그대로 띄운다.
    → {'urls': {서버: 주소}, 'calls': {서버: [(도구, 인자)]}}"""
    tools = {}
    for path in sorted(REPLAY_DIR.glob('*.json.gz')):
        doc = _json.loads(_gzip.decompress(path.read_bytes()))
        for run in doc['runs']:
            for e in run['events']:
                tool = e.get('tool') or ''
                if e['kind'] == 'tool_start' and tool.startswith('mcp__'):
                    server, _, name = tool[5:].partition('__')
                    tools.setdefault(server, {})[name] = (server, name) in WRITE_TOOLS
    tools.setdefault('neo4j', {}).update(get_neo4j_schema=False, read_neo4j_cypher=False)
    served, urls, calls = [], {}, {}
    for server, names in sorted(tools.items()):
        app, calls[server] = _mcp_app(server, names)
        s = Served(app.http_app(path='/mcp'))
        served.append(s)
        urls[server] = s.url + '/mcp'
    yield {'urls': urls, 'calls': calls}
    for s in served:
        s.close()


@pytest.fixture(scope='session')
def worker_key(tmp_path_factory):
    """process · 워커가 함께 보는 실행기 인증 파일(테스트 묶음의 것)."""
    path = tmp_path_factory.mktemp('runtime') / 'runtime.key'
    path.write_text(WORKER_KEY, encoding='utf8')
    old = os.environ.get('HYD_WORKER_RUNTIME_KEY_FILE')
    os.environ['HYD_WORKER_RUNTIME_KEY_FILE'] = str(path)
    yield path
    if old is None:
        os.environ.pop('HYD_WORKER_RUNTIME_KEY_FILE', None)
    else:
        os.environ['HYD_WORKER_RUNTIME_KEY_FILE'] = old


@pytest.fixture(scope='session')
def relay():
    fake = FakeRelay()
    yield fake
    fake.server.shutdown()


@pytest.fixture(scope='session')
def process_side(pg_dsn, worker_key, relay, mcp_servers):
    """process 의 실제 처리 흐름 런타임(시드 테넌트 hyd — 도구 서버 주소만 대체 서버로) + 수업 경계 판정 · 로컬 중계 관문 · MCP 도구
    실행 API 를 붙인 HTTP 앱(이 PC 포트)."""
    import psycopg
    from fastapi import FastAPI
    from procsvc import ask, course_model, course_policy, engine, instances, mcp_api, procdb
    servers = {name: {'type': 'url', 'url': url, 'transport': 'streamable_http'} for name, url in mcp_servers['urls'].items()}
    servers['enterprise']['headers'] = {'Authorization': SERVER_SECRET}
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        db.execute("UPDATE tenants SET mcp=%s WHERE id='hyd'", (_json.dumps({'mcpServers': servers}),))
    rt = instances.InstanceRuntime(procdb.PgRepo(pg_dsn), engine.Definition.load(DEFINITIONS / 'anomaly_response_v22.json'),
                                   instances.Hooks(), tenant_id='hyd')
    ask.register_definition(rt, DEFINITIONS)
    rt.register_definition(_json.loads((DEFINITIONS / 'shift_handover_v1.json').read_text(encoding='utf8')))
    settings = {'LLM_API_KEY': RELAY_KEY, 'LLM_RELAY_URL': relay.url, 'HYD_WORKER_RUNTIME_KEY_FILE': str(worker_key)}
    app = FastAPI()
    policy = course_policy.mount(app, runtime_factory=lambda: rt, phase=course_policy.Phase('course'))
    ledger = course_model.mount(app, policy=policy, runtime_factory=lambda: rt, settings=settings)
    mcp_api.register(app, runtime_factory=lambda: rt, audit=lambda *a, **k: None)
    served = Served(app)
    yield _NS(rt=rt, url=served.url, ledger=ledger, settings=settings, dsn=pg_dsn)
    served.close()


@pytest.fixture
def course(process_side, relay):
    """테스트 하나의 시작 상태: 테넌트 hyd 의 처리 건 · 장부 · 중계 기록이 비어 있다."""
    import psycopg
    with psycopg.connect(process_side.dsn, autocommit=True) as db:
        db.execute("DELETE FROM bpm_proc_inst WHERE tenant_id='hyd'")
        db.execute('DELETE FROM hyd_course_runs')
        db.execute('DELETE FROM hyd_course_grants')
    relay.reset()
    return process_side


def start_handover(rt, *, asset='HYD-01', definition='shift_handover', version='1.1'):
    """교대 인수인계 처리 건 하나(첫 AI 단계 = 인계안 작성)."""
    import uuid as _uuid
    from datetime import datetime, timezone
    return rt.start_definition(definition, version, 'handover:' + _uuid.uuid4().hex,
                               values={'asset': asset, 'shift_label': '다음 교대', 'as_of': datetime.now(timezone.utc).isoformat(),
                                       'work_notes': '작업 메모: 정비 완료라고 전달받음. 부품 도착 예정이라고 전달받음.'})


def ask_question(rt, question):
    from procsvc import ask
    return ask.start(rt, question, None, '수강생', definitions_dir=DEFINITIONS, worker_probe=lambda: {'reachable': True})


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
        import uuid as _uuid
        from pathlib import Path as _Path
        from cliagents import ExecEvent, ExecEventKind
        self.requests.append(_NS(request=request, env=dict(env or {})))
        session = str(_uuid.uuid4())
        for _ in range(self.calls):
            body = _json.dumps({'model': request.model, 'max_tokens': 1024, 'messages': [{'role': 'user', 'content': '다음 단계'}]}).encode()
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
            target = _Path(request.workdir) / 'output' / 'result.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.result_file if isinstance(self.result_file, str) else self.result_file(request), encoding='utf8')
        for n, d in enumerate(self.run['events'], 1):
            if check_stop:
                check_stop()
            yield ExecEvent(**dict(d, kind=ExecEventKind(d['kind']), session_id=session if d.get('session_id') else None))
            if self.after:
                self.after(n, self)


@pytest.fixture
def worker(course, mcp_servers, worker_key, tmp_path):
    """make(mode, cli=…) → 실제 Runner(시드 테넌트 hyd, 실제 DB · 관문 · 녹화 · 같은 요청 저장 폴더)."""
    import dataclasses
    from procsvc import procdb
    from worker import ai_replay
    from worker.course_access import CourseAccess
    from worker.runner import Runner
    from worker.settings import Settings

    def make(mode, cli=None, *, replay_dir=REPLAY_DIR, consumer='test-worker', root=None):
        s = dataclasses.replace(Settings(), tenant_id='hyd', consumer=consumer, supabase_dsn=course.dsn, process_url=course.url,
                                runtime_key_file=str(worker_key), workspace_root=root or tmp_path / 'workspace',
                                mcp_host_rewrite='', ai_mode=mode, ai_replay_dir=replay_dir)
        responses = ai_replay.Responses(mode, course=ai_replay.Library(replay_dir, ai_replay.COURSE),
                                        cache=ai_replay.Library(s.ai_cache_dir, ai_replay.REUSE))
        return Runner(s, procdb.PgRepo(course.dsn), responses=responses, course=CourseAccess(s.process_url, s.runtime_key_file),
                      exec_fn=cli, schema_prompt='(테스트 스키마 설명)', resolve_provider=lambda: _NS(id='claude-code', display_name='Claude Code'))
    return make


def events_of(rt, todo_id, event_type=None):
    return [e for e in rt.repo.list_events(todo_id=todo_id) if event_type is None or e['event_type'] == event_type]


def task_of(rt, proc_inst_id, activity=None):
    rows = rt.repo.list_workitems(proc_inst_id=proc_inst_id, limit=None)
    return next(w for w in rows if activity is None or w['activity_id'] == activity)


# ---- engine ----
# 프로세스 엔진(처리 건 런타임) 테스트의 공통 준비. 학생 PC 구성 그대로 — 실제 처리 엔진 코드(procsvc.main · instance_mode · instances ·
# service_parts)와 실제 PG(pg_dsn, 시드 테넌트 hyd). 시스템 밖만 대체한다:
#   Kafka 송신                → KafkaRecorder(보낸 승인 원장 · 명령을 남긴다, 시험이 실패시킬 수 있다)
#   TimescaleDB(tag_1s)       → 시험 DB 안의 같은 이름 표(재관측 · 시운전이 읽는 태그 값을 시험이 넣는다)
#   Neo4j(처리 건 그래프 반영) → graph_receipt(반영마다 그 반영의 영수증을 돌려준다)
#   agent 승인 현재 조건 검사  → FakeAgent(허용 / 거절 409)
#   SMTP                      → FakeSmtp(메일 도구 서버 effects-mcp 는 실제 앱을 이 PC 포트에 띄운다)
#   업무 시스템                → 실제 enterprise-sim 앱(이 PC 포트) + 시험 DB 의 ent 스키마
#   에이전트 단계(AI)          → 저장소 녹화본의 실제 결과 — 평가 문서는 판단으로 등록(dmn-mcp submit 자리), 결과 파일은 작업 결과로 저장,
#                               도구 호출은 워커와 같은 방식으로 기록. 녹화 값은 재생 모드와 같은 규칙(ai_replay._Swaps)으로 이 처리 건 값으로 바꾼다
#   시계                       → EngineClock(정한 시각 — 시험이 앞으로만 움직인다, sleep 으로 기다리지 않는다)
import asyncio as _asyncio
import dataclasses as _dataclasses
import itertools as _itertools
import re as _re
import uuid as _uuid
from datetime import datetime as _datetime, timedelta as _timedelta, timezone as _timezone

os.environ.setdefault('PROCESS_DEFINITIONS', str(DEFINITIONS))
os.environ.setdefault('PROCESS_CALLER_TOKEN', 'engine-test-caller-' + 'c' * 24)
ENGINE_TENANT = 'hyd'
ONTOLOGY = ROOT / 'it' / 'neo4j' / 'v2'


def _ontology_roles():
    """온톨로지 정본의 역할(이름 → id · 등급): instances.cypher 2절 + scenario_structure.cypher 의 구매 담당."""
    text = (ONTOLOGY / 'instances.cypher').read_text(encoding='utf8') + (ONTOLOGY / 'scenario_structure.cypher').read_text(encoding='utf8')
    roles = {m[1]: {'id': m[0], 'name': m[1], 'level': int(m[2])} for m in _re.findall(r"\['(role:[^']+)','([^']+)','[^']*',(\d)\]", text)}
    roles.update({m[1]: {'id': m[0], 'name': m[1], 'level': int(m[2])}
                  for m in _re.findall(r"MERGE \(n:Role \{id: '(role:[^']+)'\}\) SET n\.name = '([^']+)', n\.level = (\d)", text)})
    return roles


def _ontology_actions():
    """온톨로지 정본의 원자 조치(code → kind · param · target): instances.cypher 4절."""
    text = (ONTOLOGY / 'instances.cypher').read_text(encoding='utf8')
    rows = _re.findall(r"\['action:[^']+','[^']+','([A-Z_]+)','(\w+)',(null|'[^']*'),[^,]+,[^,]+,'([^']+)'\]", text)
    return {code: {'kind': kind, 'param': None if param == 'null' else param.strip("'"), 'target': target} for code, kind, param, target in rows}


def _ontology_pm_actions():
    """pm_capabilities.cypher 의 PM 원자 조치(기존 오더 일정 변경 WO_RESCHEDULE) — code · kind · 대상 시스템."""
    text = (ONTOLOGY / 'pm_capabilities.cypher').read_text(encoding='utf8')
    return {m[0]: {'kind': m[1], 'param': None, 'target': 'sys:cmms'} for m in _re.findall(r"a\.code='([A-Z_]+)',a\.kind='(\w+)'", text)}


class EngineClock:
    """엔진의 시계(instances.InstanceRuntime(clock=…)). 정한 시각에서 시험이 앞으로만 옮긴다."""
    def __init__(self):
        self.at = _datetime.now(_timezone.utc)

    def __call__(self):
        return self.at

    def advance(self, seconds):
        self.at += _timedelta(seconds=seconds)
        return self.at


class KafkaRecorder:
    """aiokafka 송신기 자리: send 는 브로커 응답 future 를 돌려준다. fail 에 넣은 토픽은 실패로 답한다."""
    def __init__(self):
        self.sent, self.fail = [], set()

    async def send(self, topic, key=None, value=None):
        fut = _asyncio.get_running_loop().create_future()
        if topic in self.fail:
            fut.set_exception(ConnectionError(f'{topic} 브로커가 받지 않았다(시험)'))
        else:
            self.sent.append((topic, key, value))
            fut.set_result({'topic': topic})
        return fut

    def of(self, topic):
        return [v for t, _, v in self.sent if t == topic]


def _run_async(coro):
    """process 의 비동기 경로 하나를 새 스레드의 새 이벤트 루프에서 끝까지 돌린다(서버의 요청 처리 스레드 자리). 시험 스레드에 이미 다른 루프가
    돌고 있어도(세션 동안 열린 동기 playwright 브라우저 등) 같은 길이다 — 예외는 그대로 시험으로 올린다."""
    box = {}

    def run():
        try:
            box['value'] = _asyncio.run(coro)
        except BaseException as error:  # noqa: BLE001 — 시험 스레드에서 다시 올린다
            box['error'] = error
    thread = _threading.Thread(target=run)
    thread.start()
    thread.join()
    if 'error' in box:
        raise box['error']
    return box['value']


class _LoopThread:
    """process 의 이벤트 루프 자리(main.loop) — Kafka 송신 · 사건 갱신 예약이 이 루프에서 돈다."""
    def __init__(self):
        self.loop = _asyncio.new_event_loop()
        self.thread = _threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=10)


def graph_receipt(query, **params):
    """Neo4j 자리: 처리 건 반영(payload_hash 가 있는 쓰기)에는 그 반영의 영수증을, 그 밖(제약 · 고아 판본 조회)에는 빈 결과."""
    if 'payload_hash' in params:
        return [{'projection_key': params['id'], 'projection_revision': params['revision'], 'projection_hash': params['payload_hash']}]
    return []


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
        _threading.Thread(target=self.server.serve_forever, daemon=True).start()


def _fake_agent():
    """agent 서비스 자리: 승인 현재 조건 검사. verdict['refuse'] 에 사유를 넣으면 409(현재 조건이 승인을 받지 않음)로 답한다 —
    refuse_after = n 이면 n 번째 검사 뒤부터(승인 접수 때는 받고 전달 때 거절하는 경우). verdict['hold'] = (들어옴, 풀어 줌) 사건 짝이면
    다음 검사 하나가 들어왔다고 알리고 풀어 줄 때까지 답하지 않는다(느린 agent — 콜드스타트)."""
    from fastapi import FastAPI, HTTPException
    app, verdict = FastAPI(), {'refuse': None, 'refuse_after': 0, 'checked': [], 'hold': None}

    @app.post('/api/agent/approval-check')
    def approval_check(body: dict):
        hold, verdict['hold'] = verdict['hold'], None
        if hold is not None:
            entered, release = hold
            entered.set()
            assert release.wait(60), '시험이 느린 agent 를 풀어 주지 않았다'
        verdict['checked'].append(body)
        if verdict['refuse'] and len(verdict['checked']) > verdict['refuse_after']:
            raise HTTPException(409, verdict['refuse'])
        return {'allowed': True, 'decision': body['decision']['id'], 'option': body['option'], 'reasons': [],
                'source': '시험 대체물 — agent 승인 현재 조건 검사'}
    return app, verdict


@pytest.fixture(scope='session')
def engine_services(pg_dsn, tmp_path_factory):
    """바깥 서비스 대체물(세션 하나): 업무 시스템(실제 enterprise-sim) · 메일 도구(실제 effects-mcp + FakeSmtp) · agent 검사 · tag_1s 표."""
    import psycopg
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        db.execute('CREATE TABLE IF NOT EXISTS public.tag_1s (time timestamptz NOT NULL, asset text NOT NULL, name text NOT NULL, '
                   'value double precision)')
    smtp = FakeSmtp()
    state = tmp_path_factory.mktemp('engine-services')
    os.environ.update(SMTP_HOST='127.0.0.1', SMTP_PORT=str(smtp.port), EFFECTS_STATE_PATH=str(state / 'effects.sqlite3'), SUPABASE_DSN=pg_dsn)
    import entsim.main as entsim_main
    import effects_mcp.server as effects_server
    entsim_main.SUPABASE_DSN = pg_dsn
    ent, effects = Served(entsim_main.app), Served(effects_server.mcp.http_app(path='/mcp'))
    agent_app, verdict = _fake_agent()
    agent = Served(agent_app)
    yield _NS(dsn=pg_dsn, ent=ent.url, effects=effects.url + '/mcp', agent=agent.url, verdict=verdict, smtp=smtp)
    for s in (ent, effects, agent):
        s.close()
    smtp.server.shutdown()


class EngineWorld:
    """처리 건 엔진 하나(process 한 번의 기동). restart() 는 같은 DB · 같은 사건 저장 파일로 process 를 다시 켠 것과 같다."""
    def __init__(self, services, tmp_path):
        import psycopg
        self.services, self.tmp = services, tmp_path
        self.clock = EngineClock()
        self.kafka = KafkaRecorder()
        self.offsets = _itertools.count(int(_time.time() * 1000))
        self.tick = 0
        self.roles, self.actions = _ontology_roles(), {**_ontology_pm_actions(), **_ontology_actions()}
        with psycopg.connect(services.dsn, autocommit=True) as db:      # 앞 시험의 진행 중 일이 이 시험의 폴링에 끼지 않게
            db.execute("UPDATE bpm_proc_inst SET status='CANCELLED' WHERE status='RUNNING'")
            db.execute("UPDATE process_source_inbox SET status='FAILED', error='앞 시험의 남은 접수' "
                       "WHERE status IN ('PENDING','WAITING','CLAIMED')")
        self.services.verdict.update(refuse=None, refuse_after=0, hold=None)
        self.services.verdict['checked'].clear()
        self._boot(fresh=True)

    # ------------------------------------------------------------ 기동
    def _boot(self, fresh):
        from procsvc import instance_mode, main, procdb
        from procsvc.source_delivery import SourceDelivery
        from procsvc.source_inbox import PgSourceInbox
        from procsvc.store import Store
        self.main, self.instance_mode = main, instance_mode
        self.loop_thread = _LoopThread()
        main.incidents.clear()
        main.book.clear()
        main.audit_log.clear()
        main.plant_status.clear()
        main.store = Store(str(self.tmp / 'process.sqlite3'))
        if not fresh:                                         # main._startup 과 같은 복원(사건 · 판단 · 감사)
            incidents, book, audit = main.store.restore()
            main.incidents.update(incidents)
            main.book.update(book)
            main.audit_log[:] = audit
            main.persist()
        main.loop, main.producer = self.loop_thread.loop, self.kafka
        main.PG_DSN, main.ENTERPRISE_URL = self.services.dsn, self.services.ent
        instance_mode.ENTERPRISE_URL = self.services.ent
        instance_mode.EFFECT_MCP_SERVERS = {'hyd-effects': {'type': 'url', 'url': self.services.effects, 'transport': 'streamable_http'}}
        os.environ['AGENT_URL'] = self.services.agent
        ctx = _dataclasses.replace(main._instance_context(), cypher=graph_receipt)
        self.rt = instance_mode.build(ctx, repo=procdb.PgRepo(self.services.dsn), clock=self.clock)
        main.source_inbox = PgSourceInbox(self.rt.repo, self.rt.tenant_id)
        main.source_delivery = SourceDelivery(main.source_inbox, self.rt, main._apply_source_event, owner=self.rt.consumer + '-source')
        self._course_flows()

    def restart(self):
        """process 를 다시 켠다: 메모리(사건 · 판단 사전, 이벤트 루프)는 사라지고 사건 저장 파일 · DB 는 남는다."""
        self.loop_thread.close()
        self.main.store.db.close()
        self._boot(fresh=False)

    def close(self):
        self.loop_thread.close()
        self.main.store.db.close()

    def _course_flows(self):
        """제공 수업 흐름 A · B · C 를 서버 안 호출(/api/course-bootstrap)로 가져오기 · 등록 · 배포 — 학생 PC 의 시작과 같은 길."""
        import httpx
        heads = {h['id'] for h in self.rt.repo.deployed_heads(ENGINE_TENANT) if h.get('class_flow')}
        if {'c3_cooling', 'c3_pm', 'c3_spare'} <= heads:
            return

        async def boot():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.main.app), base_url='http://process') as client:
                return await client.post('/api/course-bootstrap', json={})
        response = _run_async(boot())
        assert response.status_code == 200, response.text

    def api(self, method, path, body=None, *, source_loop=False):
        """process 의 HTTP 경로를 서버 안에서 부른다(포털 · 강사 스크립트와 같은 라우트 · 같은 수업 경계 문지기). 돌려줌 = (상태, 본문).
        source_loop: 그동안 process 의 원천 처리 루프(main._source_loop)도 함께 돈다 — 경보 접수를 기다리는 경로용."""
        import httpx

        async def call():
            loop_task = _asyncio.create_task(self.main._source_loop()) if source_loop else None
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

    def import_flow(self, definition_id, xml, mapping, file_name):
        """bpmn.io 그림 하나를 흐름 가져오기(가져오기 → 사전 검사 → 등록)로 넣는다. 돌려줌 = 등록한 판본."""
        status, body = self.api('POST', '/api/flows/import', {'xml': xml, 'file_name': file_name, 'definition_id': definition_id})
        assert status == 200, body
        status, body = self.api('POST', f'/api/flows/{definition_id}/register', {'mapping': mapping})
        assert status == 201, body
        return body['version']

    def storage_fails(self, table, condition):
        """저장소(PostgreSQL) 쪽 실패를 일으킨다: table 의 INSERT · UPDATE 가운데 condition(NEW 행에 대한 SQL)이 참인 쓰기를 거절하는
        트리거를 걸고, with 블록이 끝나면 지운다. 우리 코드는 그대로 두고 바깥(DB)만 실패시킨다."""
        import contextlib
        import psycopg
        name = 'engine_test_fail_' + _uuid.uuid4().hex[:8]

        @contextlib.contextmanager
        def failing():
            with psycopg.connect(self.services.dsn, autocommit=True) as db:
                db.execute(f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {condition} THEN "
                           f"RAISE EXCEPTION '시험: 저장소가 이 쓰기를 거절함'; END IF; RETURN NEW; END $$")
                db.execute(f'CREATE TRIGGER {name} BEFORE INSERT OR UPDATE ON public.{table} FOR EACH ROW EXECUTE FUNCTION {name}()')
            try:
                yield
            finally:
                with psycopg.connect(self.services.dsn, autocommit=True) as db:
                    db.execute(f'DROP TRIGGER IF EXISTS {name} ON public.{table}')
                    db.execute(f'DROP FUNCTION IF EXISTS {name}()')
        return failing()

    # ------------------------------------------------------------ 원천(경보 · 설비 상태)
    def now_iso(self):
        return self.clock().isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def receive(self, topic, payload):
        """Kafka 한 건을 원천 접수(main.consume 과 같은 PgSourceInbox.receive)하고 원천 처리기(SourceDelivery.run_once)를 끝날 때까지 돌린다."""
        from procsvc.source_inbox import source_record
        record = source_record(topic, 0, next(self.offsets), dict(payload))
        policy = self.rt.alert_policy(payload.get('pattern')) if record['kind'] == 'RAISE' else None
        receipt = self.main.source_inbox.receive(record, policy)
        if record['kind'] in ('RAISE', 'CLEAR', 'ACK'):
            self.deliver()
        return self.main.source_inbox.get(receipt['id']) if receipt.get('id') else receipt

    def deliver(self):
        async def drain():
            while await self.main.source_delivery.run_once() is not None:
                pass
        _run_async(drain())

    def raise_alert(self, pattern, asset, **evidence):
        from hydcommon import topics
        alert = {'alertId': f'ALT-{asset}-{_uuid.uuid4().hex[:10]}', 'asset': asset, 'pattern': pattern, 'state': 'RAISE',
                 't': self.now_iso(), 'severity': 'WARN', **({'evidence': evidence} if evidence else {})}
        receipt = self.receive(topics.K_ALERTS, alert)
        assert receipt['status'] == 'HANDLED', receipt
        return alert, receipt['result']['instance']

    def clear_alert(self, alert):
        from hydcommon import topics
        return self.receive(topics.K_ALERTS, dict(alert, state='CLEAR', t=self.now_iso()))

    def ack(self, asset, cmd_id, result='DONE', reason=None):
        from hydcommon import topics
        return self.receive(topics.K_STATUS, {'asset': asset, 't': self.now_iso(), 'cmdId': cmd_id, 'result': result,
                                              'reason': reason, 'mode': 'REMOTE_AUTO', 'state': 'RUN'})

    def tag(self, asset, name, value):
        """TimescaleDB 자리에 1초 값 하나(지금 벽시계 시각) — 재관측 · 시운전이 읽는다."""
        import psycopg
        with psycopg.connect(self.services.dsn, autocommit=True) as db:
            db.execute('INSERT INTO tag_1s(time, asset, name, value) VALUES (now(), %s, %s, %s)', (asset, name, value))

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

    # ------------------------------------------------------------ 에이전트 단계(녹화본)
    @staticmethod
    def recording_of(step):
        for path in sorted(REPLAY_DIR.glob('*.json.gz')):
            doc = _json.loads(_gzip.decompress(path.read_bytes()))
            if doc.get('step') == step:
                return doc
        raise LookupError(f'저장소에 「{step}」 녹화가 없다')

    def agent(self, pid, activity, step):
        """AI 워커 한 번의 몫을 녹화본으로: 그 단계를 점유 → 도구 호출 기록(녹화의 실행을 차례로 — 첫 실행 뒤 같은 세션을 이어 간
        결과 형식 교정 실행까지) → (판단 단계면) 판단 등록 → 마지막 실행의 결과 파일 저장 → 엔진 폴링. 돌려줌 = 등록한 판단 id(없으면 None)."""
        from worker import ai_replay
        runs = self.recording_of(step)['runs']
        record = dict(runs[-1], context=runs[0]['context'], events=[e for r in runs for e in r['events']])
        consumer = 'engine-test-worker:' + _uuid.uuid4().hex[:8]
        claimed = self.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id=ENGINE_TENANT, proc_inst_id=pid)
        assert claimed and claimed[0]['activity_id'] == activity, (activity, [(w['activity_id'], w['status']) for w in claimed])
        wi, inst = claimed[0], self.inst(pid)
        scope = {'tenant': ENGINE_TENANT, 'instance': pid, 'workitem': wi['id'], 'generation': int(wi.get('generation') or 0),
                 'version': inst['proc_def_version'], 'consumer': consumer}
        swaps = ai_replay._Swaps()
        swaps.pair_case(record['context'], {'id': wi['id'], 'proc_inst_id': pid, 'process_scope': scope,
                                            'inputs': self.rt.workitem_view(wi['id'])['inputs']}, step)
        self._record_tool_calls(record, wi, swaps)
        decision_id = self._submit_recorded_decision(record, swaps)
        result = swaps.apply(_json.loads(record['result_file']))
        assert self.rt.repo.save_task_result(wi['id'], result, final=True, expected_consumer=consumer)
        self.poll()
        return decision_id

    def _record_tool_calls(self, record, wi, swaps):
        """워커(runner)와 같은 행: 녹화 이벤트 → events.translate → row_of, 미리보기가 잘린 도구 결과는 원문을 event_payloads 에(_keep_full_output)."""
        from worker import ai_replay, events as ui_events
        from worker.runner import Runner
        keeper = _NS(repo=self.rt.repo, _secrets=[])
        job = 'replay-' + _uuid.uuid4().hex[:8]
        rows = [{'job_id': job, 'todo_id': wi['id'], 'proc_inst_id': wi['proc_inst_id'], 'crew_type': 'agent', 'event_type': 'task_started',
                 'data': {'name': 'engine-test', 'goal': wi.get('activity_name')}}]
        row = dict(wi)
        for d in record['events']:
            ev = ai_replay._event_from(swaps.apply(d))
            for ui in ui_events.translate(ev):
                if ui.type == 'tool_start':           # runner 와 같게: 잘린 입력도 원문을 남긴다(full_input)
                    raw = ev.tool_input
                    kept = Runner._keep_full_output(keeper, ui, _dataclasses.replace(ev, text=_json.dumps(raw, ensure_ascii=False, default=str),
                                                                                       tool_output=None), row, job)
                    meta = kept.data.get('full_output')
                    fallback = bool(meta and not meta.get('stored'))
                    ui = ui_events.UiEvent(ui.type, dict(ui.data, input=raw if fallback else ui.data.get('input'),
                                                         input_truncated=ui_events.preview_cut(raw) and not fallback,
                                                         **({'full_input': dict(meta, direction='input')} if meta else {})))
                if ui.type == 'tool_end':
                    ui = Runner._keep_full_output(keeper, ui, ev, row, job)
                out = ui_events.row_of(ui, job_id=job, todo_id=wi['id'], proc_inst_id=wi['proc_inst_id'], crew_type='agent')
                if out:
                    rows.append(out)
        for i in range(0, len(rows), 200):
            self.rt.repo.record_events(rows[i:i + 200])

    def _submit_recorded_decision(self, record, swaps):
        """dmn-mcp submit_decision · submit_purchase 자리: 녹화가 제출 직전에 받은 평가 문서(카드 · 근거)를 판단으로 등록한다(main 의
        POST /api/decisions 처리 함수). 평가 보기에 빠진 칸(승인 역할 id · 등급, 원자 조치 종류)은 온톨로지 정본에서 채운다."""
        submit = next((e for e in record['events'] if e.get('kind') == 'tool_start'
                       and str(e.get('tool') or '').endswith(('__submit_decision', '__submit_purchase'))), None)
        if submit is None:
            return None
        index = record['events'].index(submit)
        doc = next(_json.loads(e['text'])['document'] for e in reversed(record['events'][:index])
                   if e.get('kind') == 'tool_end' and '"options"' in (e.get('text') or '') and '"document"' in (e.get('text') or ''))
        doc, args = swaps.apply(doc), swaps.apply(submit['tool_input'])
        submitted = next(_json.loads(e['text'])['document']['id'] for e in record['events'][index:]
                         if e.get('kind') == 'tool_end' and e.get('tool_use_id') == submit['tool_use_id'])
        new_id = 'DEC-ENGINE-' + _uuid.uuid4().hex[:12]
        swaps.exact[submitted] = new_id
        if submit['tool'].endswith('__submit_purchase'):
            origin = {'kind': 'alert', 'pattern': 'SPARE_BELOW_MIN', 'cause_route': 'purchase-part', 'part': doc.get('part'),
                      'cause_basis': '실제 ERP 부족부품 → Part ← 원문 구매 Skill', 'incident': args['incident'], 'alertId': args.get('alert_id')}
        else:
            origin = {'kind': 'alert', 'alertId': args.get('alert_id'), 'incident': args['incident'], 'pattern': args['pattern'],
                      'cause': args.get('cause'), 'failureMode': args.get('failure_mode')}
        origin['process_scope'] = args['process_scope']
        options = [dict(o, approver=self.roles[o['approver']], evaluation_mode='execution', execution_checked=True,
                        actions=[dict(a, **self.actions[a['code']]) for a in o.get('actions') or []]) for o in doc['options']]
        payload = {'id': new_id, 'schema': 'v2', 'scenario': doc.get('scenario'), 'asset': doc.get('asset') or args['asset'], 'origin': origin,
                   'recommended': doc.get('recommended'), 'explanation': doc.get('explanation'), 'options': options,
                   'rankRule': doc.get('rankRule'), 'roles': {r['id']: {'name': r['name'], 'level': r['level']} for r in self.roles.values()},
                   'facts': doc.get('facts') or {}, 'evaluation_mode': 'execution', 'execution_checked': True, 'provenance': [], 'applicable': True}
        out = self.main._create_decision(payload)
        assert out['id'] == new_id and out['state'] == 'PENDING_APPROVAL', out
        return new_id


@pytest.fixture
def world(engine_services, tmp_path):
    w = EngineWorld(engine_services, tmp_path)
    yield w
    w.close()
