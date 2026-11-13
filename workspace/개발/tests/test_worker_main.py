"""AI 워커 진입점(worker/main.py) — 켜질 때의 계약(설정 · 녹화 · CLI 격리), 상태 HTTP(/health · /agents), 폴링 실패의 상태.

워커는 Dockerfile CMD(`python -m worker.main`) 그대로 이 PC 의 하위 프로세스로 띄운다(conftest ServiceProcess — compose 환경, 주소만 이 PC).
compose 가 볼륨으로 주는 자리(녹화 폴더 · 작업 공간 · 실행기 인증 파일)와 상태 포트는 이 테스트의 자리로 준다. 이 PC 는 Linux root 가 아니라
CLI 격리를 켤 수 없으므로 켜짐 확인(cli_sandbox.verify)을 재는 테스트 말고는 개발용 호스트 워커처럼 격리를 끈다(HYD_CLI_SANDBOX 없음).
업무 DB 는 테스트 DB(마이그레이션 + seed.sql), process 는 띄우지 않는다 — 켜기 · 폴링은 일거리가 없으면 process 를 부르지 않는다.
"""
import json
import shutil
import socket
import urllib.error
import urllib.request

import psycopg
import pytest

from conftest import PORTS, REPLAY_DIR, TENANT, ServiceProcess, until
from worker import ai_replay

NEEDED = ('SUPABASE_DSN', 'PROCESS_URL', 'HYD_WORKER_RUNTIME_KEY_FILE')


@pytest.fixture
def no_work(pg_dsn):
    """처음 켠 PC: 이 테넌트의 처리 건(과 작업)이 없다 — 띄운 워커가 다른 테스트의 작업을 집지 않는다."""
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        db.execute('DELETE FROM bpm_proc_inst WHERE tenant_id=%s', (TENANT,))
        db.execute('DELETE FROM todolist WHERE tenant_id=%s', (TENANT,))
    return pg_dsn


@pytest.fixture
def launch(no_work, worker_key, tmp_path):
    """launch(**환경) → 띄운 워커(ServiceProcess). 기본은 키 없는 PC(replay) · 격리 끔. 테스트가 끝나면 끈다."""
    started = []

    def start(**env):
        base = dict(AI_MODE='replay', AI_REPLAY_DIR=str(REPLAY_DIR), HYD_WORKER_RUNTIME_KEY_FILE=str(worker_key),
                    CLIAGENTS_WORKSPACE_ROOT=str(tmp_path / 'workspace'), HEALTH_PORT=str(PORTS['agent-worker']), HYD_CLI_SANDBOX='')
        logs = tmp_path / f'logs{len(started)}'
        logs.mkdir()
        service = ServiceProcess('agent-worker', logs, dict(base, **env))
        started.append(service)
        return service
    yield start
    for service in started:
        service.close()


def get(service, path):
    """(상태 코드, 머리글 dict(소문자), 본문 JSON)."""
    try:
        with urllib.request.urlopen(service.url + path, timeout=5) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, json.loads(e.read())


def refused_start(service, timeout=120):
    """켜지지 않고 끝난 워커 → (종료 코드, 로그 글)."""
    until(lambda: service.proc.poll() is not None, f'워커가 {timeout}초 안에 끝나지 않았다(켜지면 안 되는 설정):\n{service.tail()}', timeout)
    return service.proc.returncode, service.tail()


def recordings(tmp_path, count, broken=False):
    """저장소 녹화 중 count 개를 복사한 녹화 폴더(키 없는 PC 의 /srv/replay 자리). broken=True 면 깨진 파일 하나를 더한다."""
    folder = tmp_path / 'replay'
    folder.mkdir()
    for path in sorted(REPLAY_DIR.glob('*.json.gz'))[:count]:
        shutil.copy2(path, folder / path.name)
    if broken:
        (folder / 'ffffffffffffffff.json.gz').write_bytes(b'not gzip')
    return folder


# ---------------------------------------------------------------- 켜질 때의 계약
@pytest.mark.parametrize('missing', [(n,) for n in NEEDED] + [NEEDED], ids=[*NEEDED, '셋 다'])
def test_업무_DB_process_주소_실행기_인증_파일_중_하나라도_없으면_그_이름을_말하며_켜지지_않는다(launch, missing):
    code, log = refused_start(launch(**{name: '' for name in missing}))
    assert code != 0
    assert f"{' · '.join(missing)}(업무 DB · process 주소 · 실행기 인증 파일)이 없어 AI 워커를 켜지 않습니다" in log


@pytest.mark.parametrize('mode', ['', 'auto', 'REPLAY'], ids=['빈 값', '모르는 값', '대문자'])
def test_AI_모드가_세_모드_밖이면_실제_AI_로_조용히_켜지지_않고_멈춘다(launch, mode):
    code, log = refused_start(launch(AI_MODE=mode))
    assert code != 0 and 'AI_MODE 는 live, record, replay 중 하나여야 합니다' in log


def test_CLI_격리가_켜진_워커는_켜질_때_격리를_확인하고_걸_수_없는_곳이면_켜지지_않는다(launch):
    """G1-25: 이미지 빌드 때 옵션만 보던 시절, 격리를 못 거는 커널에서 상태 점은 초록인데 모든 AI 단계가 실패했다. 이 PC(Windows)는 격리를
    걸 수 없는 곳이다 — 이미지 값(HYD_CLI_SANDBOX=landlock) 그대로 켜면 그 까닭으로 멈춰야 한다."""
    code, log = refused_start(launch(HYD_CLI_SANDBOX='landlock'))
    assert code != 0 and 'AI 실행 격리(HYD_CLI_SANDBOX=landlock)에는 Linux root · setpriv 가 필요합니다' in log


def test_깨진_녹화_파일이_있으면_키_없는_PC_의_워커는_켜지지_않는다(launch, tmp_path):
    code, log = refused_start(launch(AI_REPLAY_DIR=str(recordings(tmp_path, 1, broken=True))))
    assert code != 0 and 'ffffffffffffffff.json.gz' in log


# ---------------------------------------------------------------- 상태 HTTP
def test_키_없는_PC_의_상태는_워커가_실제로_읽은_녹화_수와_그_질문을_낸다(launch, tmp_path):
    """G5b-19: 점검이 파일 수가 아니라 워커가 읽은 녹화 수를 본다 — 녹화 폴더에 넣은 만큼이 나와야 한다."""
    folder = recordings(tmp_path, 3)
    expected_questions = ai_replay.Library(folder).questions()
    service = launch(AI_REPLAY_DIR=str(folder)).wait()
    status, headers, body = get(service, '/health')
    assert status == 200 and body['status'] == 'ok' and body['ai_mode'] == 'replay'
    assert body['replay_recordings'] == 3 and body['replay_questions'] == expected_questions
    assert body['runs_in_flight'] == 0 and body['error'] is None


def test_키_있는_PC_의_상태에는_녹화_수가_없다(launch):
    service = launch(AI_MODE='live').wait()
    _, _, body = get(service, '/healthz')
    assert (body['ai_mode'], body['replay_recordings'], body['replay_questions']) == ('live', None, [])


@pytest.mark.parametrize('path, status', [('/health', 200), ('/healthz', 200), ('/agents', 200), ('/fgb-none', 404)])
def test_상태_HTTP_는_다른_출처_허용_머리글을_내지_않는다(launch, path, status):
    """결정 1: 포털은 같은 출처(/svc/agent-worker/)로 읽는다 — 아무 웹페이지나 워커 상태를 읽게 두지 않는다."""
    service = launch().wait()
    code, headers, _ = get(service, path)
    assert code == status and not any(k.startswith('access-control-') for k in headers)


def test_agents_는_이_워커가_돌리는_CLI_하나의_설치_여부만_낸다(launch):
    from worker.settings import PROVIDER
    service = launch().wait()
    _, _, body = get(service, '/agents')
    [agent] = body['agents']
    assert agent['agent_id'] == PROVIDER and isinstance(agent['installed'], bool)
    assert (agent['install_hint'] is None) == agent['installed']


def test_업무_DB_에_닿지_않으면_상태가_오류와_그_까닭으로_바뀐다(launch):
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    service = launch(SUPABASE_DSN=f'postgresql://postgres:postgres@127.0.0.1:{port}/postgres')
    seen = {}

    def errored():
        try:
            seen['reply'] = get(service, '/health')
        except OSError:
            return False
        return seen['reply'][2]['status'] == 'error'
    until(errored, f'워커 상태가 오류로 바뀌지 않았다:\n{service.tail()}', 60)
    code, _, body = seen['reply']
    kind = body['error'].split(':', 1)[0]
    assert code == 503 and issubclass(getattr(psycopg.errors, kind, None) or getattr(psycopg, kind), psycopg.OperationalError), body
