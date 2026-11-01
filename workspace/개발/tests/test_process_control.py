"""CLI 실행을 끊을 수 있게 감싸는 곳(worker/process_control.py) — 출력 펌프, 취소 · 기한 확인, 실행마다 프로세스 나무를 통째로 죽이기.

바깥(Claude Code CLI)만 대체한다: CLI 자리는 이 PC 파이썬으로 도는 작은 프로그램(StandInCli — 줄마다 JSON 을 내고, 손자 프로세스를 띄우고,
조용히 기다린다)이고, 그것을 띄우고 읽는 것은 실제 cliagents.stream_exec 이다.
Windows(이 PC): 작업 개체(KILL_ON_JOB_CLOSE)가 나무를 묶는다. POSIX(학생 PC 의 워커 컨테이너): 프로세스 그룹 기록 · 남은 그룹 죽이기 —
이 PC 에서는 잴 수 없어 이 PC 에 지어 둔 워커 이미지(Linux, CLI 격리 켜짐) 안에서 저장소의 지금 코드로 잰다.
"""
import json
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import psutil
import pytest
from cliagents import ExecRequest, stream_exec

from conftest import ROOT, until
from worker import process_control
from worker.runner import Cancelled, RunFailed

#: 손자 프로세스를 띄우고 두 pid 를 argv[1] 파일에 적은 뒤 JSON 한 줄을 내고(내지 않으면 조용히) 오래 기다리는 CLI 자리
SILENT = textwrap.dedent('''
    import json, subprocess, sys, time
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])
    open(sys.argv[1] + '.tmp', 'w').write(json.dumps({'cli': __import__('os').getpid(), 'grandchild': child.pid}))
    __import__('os').replace(sys.argv[1] + '.tmp', sys.argv[1])
    if len(sys.argv) > 2:
        print(json.dumps({'said': sys.argv[2]}), flush=True)
    time.sleep(600)
''')


#: Claude Code CLI 자리(cliagents provider 모양) — 워커 이미지 안에서도 같은 글을 쓰도록 글로 둔다
STAND_IN = textwrap.dedent('''
    import os, sys
    from cliagents.execution import ExecParser
    class StandInCli:
        """실행 인자는 이 PC 파이썬 프로그램, 출력 해석은 cliagents 기본 해석기(줄마다 JSON → 이벤트)."""
        def __init__(self, script, *args):
            self.argv = [sys.executable, '-c', script, *map(str, args)]
        def exec_argv(self, request):
            return self.argv
        def exec_env(self, env):
            return dict(os.environ, **(env or {}))
        def exec_parser(self):
            return ExecParser()
''')
exec(STAND_IN)


def stream(cli, workdir, check_stop=lambda: None):
    return process_control.controlled_stream(stream_exec, cli, ExecRequest(prompt='', workdir=str(workdir)), {}, check_stop, RunFailed)


def pids_of(path):
    until(path.exists, f'CLI 자리가 pid 파일 {path} 을 쓰지 않았다', 60)
    return json.loads(path.read_text())


def gone(*pids):
    def dead(pid):
        try:
            return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return True
    return all(dead(p) for p in pids)


# ---------------------------------------------------------------- 출력 · 끝(모든 운영체제)
def test_CLI_가_낸_줄은_차례대로_이벤트로_오고_0으로_끝나면_흐름도_끝난다(tmp_path):
    cli = StandInCli('import json\nfor i in range(3): print(json.dumps({"n": i}), flush=True)')
    assert [e.raw for e in stream(cli, tmp_path)] == [{'n': 0}, {'n': 1}, {'n': 2}]


def test_CLI_가_0이_아닌_코드로_끝나면_그_코드와_표준_오류를_실은_실패다(tmp_path):
    cli = StandInCli('import json, sys\nprint(json.dumps({"n": 0}), flush=True)\nsys.stderr.write("인증 실패: 키 없음")\nsys.exit(3)')
    seen = []
    with pytest.raises(RunFailed) as e:
        for event in stream(cli, tmp_path):
            seen.append(event.raw)
    assert seen == [{'n': 0}] and str(e.value).startswith('CLI exit 3: ') and '인증 실패: 키 없음' in str(e.value)


def test_0으로_끝났지만_표준_오류가_있으면_실패가_아니라_워커_기록에_남긴다(tmp_path, caplog):
    cli = StandInCli('import json, sys\nprint(json.dumps({"n": 0}), flush=True)\nsys.stderr.write("deprecated flag --foo")')
    with caplog.at_level(logging.WARNING, logger='worker.process'):
        assert [e.raw for e in stream(cli, tmp_path)] == [{'n': 0}]
    assert any('CLI exit 0 with stderr' in r.getMessage() and 'deprecated flag --foo' in r.getMessage() for r in caplog.records)


def test_줄을_내지_않는_CLI_도_취소하면_곧바로_멈추고_그_나무가_모두_죽는다(tmp_path):
    """펌프 스레드가 읽기에 막혀 있어도 부르는 쪽은 0.025초마다 취소 · 기한을 본다 — CLI 와 그 손자까지 끝난다."""
    record = tmp_path / 'pids.json'

    def check_stop():
        if record.exists():
            raise Cancelled('담당자가 취소함')
    with pytest.raises(Cancelled):
        for _ in stream(StandInCli(SILENT, record), tmp_path, check_stop):
            pass
    pids = pids_of(record)
    until(lambda: gone(pids['cli'], pids['grandchild']), f'취소 뒤에도 CLI 나무가 살아 있다: {pids}', 30)


def test_부르는_쪽이_도중에_그만_읽으면_CLI_나무를_죽인다(tmp_path):
    record = tmp_path / 'pids.json'
    events = stream(StandInCli(SILENT, record, '첫 줄'), tmp_path)
    assert next(events).raw == {'said': '첫 줄'}
    pids = pids_of(record)
    assert not gone(pids['cli'], pids['grandchild'])
    events.close()
    until(lambda: gone(pids['cli'], pids['grandchild']), f'읽기를 그만둔 뒤에도 CLI 나무가 살아 있다: {pids}', 30)


# ---------------------------------------------------------------- 워커가 풀지 못하고 죽을 때(운영체제마다)
WORKER = STAND_IN + 'SILENT = ' + repr(SILENT) + textwrap.dedent('''
    from cliagents import ExecRequest, stream_exec
    from worker import process_control
    from worker.runner import RunFailed
    for event in process_control.controlled_stream(stream_exec, StandInCli(SILENT, sys.argv[2], 'started'),
                                                   ExecRequest(prompt='', workdir=sys.argv[1]), {}, lambda: None, RunFailed):
        print(event.raw, flush=True)
''')


@pytest.mark.skipif(os.name != 'nt', reason='Windows 작업 개체 경로 — POSIX 는 아래 워커 이미지 테스트가 잰다')
def test_Windows_워커가_강제로_끝나도_작업_개체가_CLI_나무를_함께_닫는다(tmp_path):
    """워커가 finally 없이 죽어도(작업 관리자 종료 · 메모리 부족) 작업 개체 핸들이 닫히며 CLI 와 손자가 끝난다 — 남은 그룹 기록이 필요 없다."""
    record = tmp_path / 'pids.json'
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / 'it' / 'agent-worker'), str(ROOT / 'it' / 'process'), str(ROOT / 'common')]))
    worker = subprocess.Popen([sys.executable, '-c', WORKER, str(tmp_path), str(record)], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        pids = pids_of(record)
        assert not gone(pids['cli'], pids['grandchild'])
        worker.kill()                                                     # TerminateProcess — 워커의 finally 는 돌지 않는다
        worker.wait(30)
        until(lambda: gone(pids['cli'], pids['grandchild']), f'워커가 죽은 뒤에도 CLI 나무가 살아 있다: {pids}', 30)
        assert process_control.reap_stale_group(tmp_path) is None and not (tmp_path / process_control.GROUP_FILE).exists()
    finally:
        if worker.poll() is None:
            worker.kill()


#: 워커 이미지 안에서 도는 판정(저장소의 지금 worker · procsvc · hydcommon 을 /srv 에 붙인다). 잰 사실을 JSON 한 줄로 낸다.
IN_IMAGE = textwrap.dedent(r'''
    import json, os, signal, subprocess, sys, time
    from pathlib import Path
    from worker import cli_sandbox, process_control
    def alive(pid):
        try:
            state = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
        except OSError:
            return False
        return state != 'Z'
    def wait(cond, seconds=30):
        end = time.monotonic() + seconds
        while not cond():
            if time.monotonic() > end:
                return False
            time.sleep(0.05)
        return True
    out = {'sandbox': cli_sandbox.enabled()}
    work = Path('/workspace/hyd/fgb-job'); work.mkdir(parents=True)
    pids = work / 'pids.json'
    worker = subprocess.Popen([sys.executable, '-c', sys.argv[1], str(work), str(pids)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not wait(pids.exists, 60):
        worker.kill(); out['worker_error'] = worker.communicate()[1].decode()[-1500:]; print(json.dumps(out)); sys.exit()
    tree = json.loads(pids.read_text())
    record = cli_sandbox.group_file(work) if cli_sandbox.enabled() else work / process_control.GROUP_FILE
    out['record_before'] = json.loads(record.read_text()) if record.exists() else None
    out['cli_pgid'] = os.getpgid(tree['cli'])
    worker.send_signal(signal.SIGKILL); worker.wait()                # 워커가 풀지 못하고 죽는다(OOM · kill -9)
    out['orphans_alive_after_worker_death'] = alive(tree['cli']) and alive(tree['grandchild'])
    out['reaped'] = process_control.reap_stale_group(work)
    out['tree_gone'] = wait(lambda: not alive(tree['cli']) and not alive(tree['grandchild']))
    out['record_after'] = record.exists()
    out['reap_again'] = process_control.reap_stale_group(work)
    # 기록의 pid 가 다른 시각에 시작한 프로세스면(pid 재사용) 그 그룹은 건드리지 않는다
    other = subprocess.Popen(['sleep', '600'], start_new_session=True)
    record.write_text(json.dumps({'pgid': other.pid, 'start': 'proc:0'}))
    out['reused_pid_reaped'] = process_control.reap_stale_group(work)
    out['reused_pid_alive'] = alive(other.pid)
    out['reused_record_after'] = record.exists()
    other.kill(); other.wait()
    record.write_text('{깨진 기록')
    out['broken_record_reaped'] = process_control.reap_stale_group(work)
    out['broken_record_after'] = record.exists()
    out['tree'] = tree
    print(json.dumps(out))
''')


def worker_image():
    """이 PC 에 지어 둔 워커 이미지(시작 스크립트가 정한 compose 프로젝트 이름 — .hyd-runtime/project.json). 없으면 까닭을 내고 실패한다."""
    record = ROOT / '.hyd-runtime' / 'project.json'
    if not record.is_file():
        pytest.fail('이 PC 에 시작 기록(.hyd-runtime/project.json)이 없어 워커 이미지를 찾지 못했다 — 시작.bat 으로 스택을 한 번 켠다', pytrace=False)
    image = json.loads(record.read_text(encoding='utf8'))['compose'] + '-agent-worker'
    found = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], capture_output=True, timeout=120)
    if found.returncode:
        pytest.fail(f'워커 이미지 {image} 가 없다(docker compose build agent-worker): {found.stderr.decode("utf8", "replace")[-300:]}', pytrace=False)
    return image


def test_워커_컨테이너에서_워커가_풀지_못하고_죽으면_다음_실행이_그_작업_폴더의_남은_CLI_그룹을_죽인다():
    """POSIX 에는 작업 개체가 없다: kill -9 · OOM 으로 죽은 워커의 CLI 그룹은 살아남아 도구를 계속 부를 수 있다. 같은 작업 폴더의 다음 실행이
    기록(격리가 켜진 이미지는 CLI 가 고칠 수 없는 /run/hyd-worker/groups)으로 그 그룹을 죽인다. pid 가 재사용됐으면 남의 그룹이라 두고, 깨진
    기록은 지운다."""
    mounts = []
    for source, target in (('it/agent-worker/worker', '/srv/worker'), ('it/process/procsvc', '/srv/procsvc'), ('common/hydcommon', '/srv/hydcommon')):
        mounts += ['-v', f'{(ROOT / source).resolve()}:{target}:ro']
    done = subprocess.run(['docker', 'run', '--rm', '-i', '--network', 'none', '--tmpfs', '/workspace', '-e', 'PYTHONDONTWRITEBYTECODE=1',
                           *mounts, '--entrypoint', 'python', worker_image(), '-', WORKER], input=IN_IMAGE.encode(), capture_output=True, timeout=300)
    assert done.returncode == 0, done.stderr.decode('utf8', 'replace')[-3000:]
    out = json.loads(done.stdout.decode().strip().splitlines()[-1])
    assert 'worker_error' not in out, out.get('worker_error')
    assert out['sandbox'] is True                                           # 이미지 그대로 CLI 격리가 켜진 길
    assert out['record_before'] and out['record_before']['pgid'] == out['tree']['cli'] == out['cli_pgid']
    assert out['orphans_alive_after_worker_death'] is True                  # 기록이 없으면 남았을 것
    assert out['reaped'] == out['tree']['cli'] and out['tree_gone'] is True and out['record_after'] is False
    assert out['reap_again'] is None
    assert (out['reused_pid_reaped'], out['reused_pid_alive'], out['reused_record_after']) == (None, True, False)
    assert (out['broken_record_reaped'], out['broken_record_after']) == (None, False)
