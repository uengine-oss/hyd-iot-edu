"""시작 · 끄기 스크립트(scripts/start_all.sh · stop_all.sh)가 멈출 때 학생에게 하는 말 — 실제 스크립트를 임시 저장소에서 끝까지 돌려 판정한다.

규칙(정답의 출처): 시작이 멈추면 그 단계에서 실제로 일어난 일의 까닭과 학생이 할 일을 말한다. 다른 까닭의 안내(포트 겹침 · 로그 보기)만 내밀지 않는다.
  · Docker Desktop 이 Windows 컨테이너 모드면 이미지 받기까지 가지 않고 1단계에서 바꾸는 법을 말하며 멈춘다.
  · 업무 DB 를 켜다 이미지 받기(망)에서 멈추면 망을 확인하라고 말한다.
  · 4단계가 빌드 · 받기에서 멈추면 까닭은 위 출력에 있다고 말한다(뜨지도 않은 서비스의 로그를 보라고만 하지 않는다).
  · 지식 지도 내용 검사(kg-seed 되읽기)가 실패해 AI 판단 서비스가 켜지지 않으면, 검사가 짚은 줄과 그 까닭(지식 지도를 직접 고침)과 되돌리는 길을 말한다.
  · 끄기는 이 폴더의 업무 DB 이름 기록이 없어 기본 이름의 업무 DB 를 껐으면 그렇게 말한다.
Docker · Supabase CLI 는 바깥이라 대역을 PATH 앞에 둔다: 스크립트가 묻는 명령에만 답하고(모르는 명령은 실패), 실패는 그 도구가 실제로 내는 꼴의 글로 낸다.
Docker Desktop 이 깔린 PC 에서도 대역이 이긴다 — 시작은 PATH 에 docker 가 있으면 Docker Desktop 자리를 앞에 끼우지 않고(windows_paths.sh), 파이썬 보조도
PATH 차례로 docker 를 찾는다(prepare_ports.docker_exe). 전에는 진짜 docker 가 대역을 가려 이 PC 의 진짜 Docker 에 망을 만들었다(2026-11-24 남은 망
hyd-business-db-hyd-portal-latest).
스크립트 · 파이썬 보조(scripts/*) · git 은 실제 것이다. 이 PC 값은 임시 저장소 안(.env · .hyd-runtime · it/supabase/.env)에만 쓰인다.
"""
import os
import shutil
import subprocess

import pytest

from conftest import ROOT, git

DOCKER = r'''#!/bin/bash
case "$*" in
  "info --format {{.OSType}}") echo "${FAKE_OSTYPE:-linux}";;
  info*) exit 0;;
  "compose version") exit 0;;
  "compose up -d --build --remove-orphans") printf '%s\n' "${FAKE_UP_OUTPUT:-}" >&2; exit "${FAKE_UP_EXIT:-0}";;
  "compose restart ot-broker dmz-broker ot-bridge") exit 0;;
  compose\ logs*kg-seed) printf '%s\n' "${FAKE_SEED_LOG:-}";;
  "compose config --format json") printf '{"name": "hyd-fake", "networks": {"business-db": {"name": "hyd-business-db-%s"}}, "services": {}}\n' "$(sed -n 's/^HYD_SUPABASE_PROJECT=//p' .env)";;
  network\ inspect\ -f*) echo fake-net-id;;
  network\ inspect\ *) exit 0;;
  inspect\ -f*NetworkSettings.Networks*) printf '{"hyd-business-db-%s": {}}\n' "$(sed -n 's/^HYD_SUPABASE_PROJECT=//p' .env)";;      # 업무 DB · 메일함은 이미 그 망에 붙어 있다
  volume\ ls*neo4j-data*) echo hyd-fake_neo4j-data;;
  volume\ inspect\ -f*) echo 2026-11-24T16:20:08Z;;                                   # 업무 DB 데이터 볼륨을 만든 시각
  inspect\ -f*State.Running*) printf 'true\n%s\n' "${FAKE_INBUCKET_RUNNING:-true}";;    # 업무 DB · 메일함 컨테이너가 켜져 있는가
  # 업무 DB 에 묻기(psql) — FAKE_DB: ok(시드까지) · half(처음 준비 도중 끊김 — 표도 없다) · empty(표만 있고 시드 없음) · data(회사 없이 기록만)
  exec\ supabase_db_*to_regclass*) if [ "${FAKE_DB:-ok}" = half ]; then echo 'f|f'; else echo 't|t'; fi;;
  exec\ supabase_db_*"where id = 'hyd'"*) if [ "${FAKE_DB:-ok}" = ok ]; then echo 1; else echo 0; fi;;
  exec\ supabase_db_*"from public.tenants"*) if [ "${FAKE_DB:-ok}" = ok ]; then echo 1; else echo 0; fi;;
  exec\ supabase_db_*"from public.users"*) case "${FAKE_DB:-ok}" in ok) echo 18;; data) echo 3;; *) echo 0;; esac;;
  "compose --profile * stop") exit 0;;
  compose\ ps*|ps*|volume\ ls*) ;;
  *) echo "docker 대역이 모르는 명령: $*" >&2; exit 97;;
esac
'''
NPX = r'''#!/bin/bash
[ -z "${FAKE_CALLS:-}" ] || printf '%s\n' "$*" >> "$FAKE_CALLS"          # 부른 차례를 남긴다(시험이 읽는다)
case "$*" in
  *" start") printf '%s\n' "${FAKE_SUPA_OUTPUT:-}" >&2; exit "${FAKE_SUPA_EXIT:-0}";;
  *" stop"|*" stop --no-backup"|*" migration up --local") exit 0;;
  *) echo "npx 대역이 모르는 명령: $*" >&2; exit 97;;
esac
'''


@pytest.fixture
def pc(tmp_path):
    """학생 PC 하나: 저장소에서 시작 · 끄기가 읽는 파일만 담은 git 저장소 + Docker · npx 대역. run(스크립트, **대역 답) → (종료 코드, 화면 글)."""
    bash = shutil.which('bash')      # PATH 의 bash(Git bash) — 이름만 주면 Windows 는 PATH 보다 System32 를 먼저 찾아 WSL bash 를 부른다
    if bash is None:
        pytest.fail('bash 가 없어 시작 스크립트를 돌릴 수 없습니다')
    repo, bin_dir = tmp_path / 'repo', tmp_path / 'bin'
    shutil.copytree(ROOT / 'scripts', repo / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
    (repo / 'it' / 'supabase').mkdir(parents=True)
    for name in ('.env.example', '.gitignore', 'compose.yaml', 'it/supabase/config.toml'):
        shutil.copy(ROOT / name, repo / name)
    git(repo, 'init', '-q', '.')
    git(repo, 'add', '-A')
    git(repo, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '-qm', '시험 저장소')
    bin_dir.mkdir()
    for name, body in (('docker', DOCKER), ('npx', NPX)):
        (bin_dir / name).write_text(body, encoding='utf-8', newline='\n')
        (bin_dir / name).chmod(0o755)
    if os.name == 'nt':      # 파이썬 보조(prepare_ports)는 셸과 같은 PATH 차례로 docker 를 찾는다(shutil.which — PATHEXT) — 같은 대역으로 잇는다
        (bin_dir / 'docker.cmd').write_text(f'@"{bash}" "%~dp0docker" %*\r\n', encoding='oem', newline='')
    keep = {k: v for k, v in os.environ.items() if k not in ('LLM_API_KEY', 'OPENAI_BASE_URL', 'LLM_MODEL', 'AI_MODE', 'COMPOSE_PROFILES')}

    def run(script, **fake):
        env = dict(keep, PATH=f'{bin_dir}{os.pathsep}{keep["PATH"]}', **{f'FAKE_{k.upper()}': str(v) for k, v in fake.items()})
        out = subprocess.run([bash, f'scripts/{script}'], cwd=repo, env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
        return out.returncode, out.stdout + out.stderr
    run.repo = repo
    return run


def stopped(text):
    """화면 글에서 「[멈춤] …」 한 줄(스크립트가 멈추며 하는 말)."""
    lines = [line for line in text.splitlines() if line.startswith('[멈춤]')]
    assert len(lines) == 1, text
    return lines[0]


def test_Windows_컨테이너_모드면_이미지를_받기_전에_바꾸는_법을_말하며_멈춘다(pc):
    """전수 대조 07-15: Docker 가 응답하면 그대로 4단계까지 가서 이미지 받기가 「no matching manifest」로 멈췄고, 안내는 약관 동의 · Engine running 뿐이었다."""
    code, text = pc('start_all.sh', ostype='windows')
    said = stopped(text)
    assert code == 1 and 'Windows 컨테이너 모드' in said and 'Switch to Linux containers' in said
    assert '2/8' not in text                                   # 이 PC 값 준비 · 이미지 받기로 넘어가지 않았다


def test_업무_DB를_켜다_이미지_받기에서_멈추면_포트가_아니라_망을_확인하라고_말한다(pc):
    """전수 대조 07-17: 3단계 실패 안내가 포트 겹침만 말해, 학교망에서 이미지를 못 받은 학생이 끄기만 되풀이했다."""
    code, text = pc('start_all.sh', supa_exit=1, supa_output='failed to pull docker image: net/http: TLS handshake timeout')
    said = stopped(text)
    assert code == 1 and '업무 DB' in said and '인터넷 연결을 확인' in said and '이어서 받습니다' in said
    assert 'port is already allocated' in said                 # 포트가 겹친 경우의 길도 그대로 말한다(오류 글로 가려 쓰게)
    assert '4/8' not in text


def test_빌드에서_멈추면_까닭이_위_출력에_있다고_말하고_서비스_로그만_가리키지_않는다(pc):
    """전수 대조 07-16: 빌드 · 이미지 받기 실패에도 「docker compose logs <서비스>를 확인하세요」만 안내했다 — 뜨지 않은 서비스에는 로그가 없다."""
    code, text = pc('start_all.sh', up_exit=1, up_output='failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully')
    said = stopped(text)
    assert code == 1 and '위 오류' in said and '빌드' in said and '인터넷 연결을 확인' in said
    assert said.index('빌드') < said.index('docker compose logs')        # 로그 보기는 서비스가 뜬 뒤 멈춘 경우의 길로만 뒤에 온다
    assert '지식 지도' not in said                                       # 지식 지도 검사 실패가 아닌데 그 까닭을 대지 않는다
    assert '5/8' not in text


def test_지식_지도_내용_검사가_실패하면_검사가_짚은_줄과_까닭과_되돌리는_길을_말한다(pc):
    """전수 대조 12-3: 학생이 Neo4j Browser 에서 적재 지식의 관계 하나를 지우면 다음 시작에서 kg-seed 가 실패해 AI 판단 서비스(agent · dmn-mcp)가 뜨지
    않는데, 시작 창은 「시스템을 켜지 못했습니다 … docker compose logs」만 말했고 까닭은 kg-seed 로그의 영문 한 줄뿐이었다. kg-seed 의 실제 출력
    꼴(it/neo4j/seed.sh — 「CHECK FAILED: …」 · 「kg-seed FAILED read-back」)로 판정한다."""
    seed_log = 'CHECK FAILED: rule when does not state exactly its TESTS rule:ts1-hard: forecast_ts1 >= 60\nread-back: 25 checks, 1 failed\nkg-seed FAILED read-back'
    code, text = pc('start_all.sh', up_exit=1, up_output='service "kg-seed" didn\'t complete successfully: exit 1', seed_log=seed_log)
    said = stopped(text)
    assert code == 1 and '지식 지도의 내용 검사가 실패' in said and 'AI 판단 서비스' in said
    assert '  CHECK FAILED: rule when does not state exactly its TESTS rule:ts1-hard' in text       # 검사가 짚은 줄을 그대로 보인다
    assert '포털에서 넣은 문서' in said                         # 포털로 넣은 지식은 이 검사에 걸리지 않는다(seed_checks 머리말) — 그것을 까닭으로 대지 않는다
    assert 'Neo4j Browser' in said and '다시 만든 뒤' in said                            # 까닭과 첫째 길(지운 것을 다시 만든다)
    assert "docker volume rm hyd-fake_neo4j-data" in said                               # 둘째 길: 이 PC 의 실제 볼륨 이름으로
    assert '다시 넣어야 합니다' in said                                                   # 그 길이 지우는 것(직접 적재한 지식)을 말한다


@pytest.mark.parametrize('db, inbucket, said, calls', [
    ('half', 'false', '처음 준비(구조 · 기본 데이터)를 마치지 못한 채', ['start', 'stop --no-backup', 'start', 'migration up --local']),
    ('empty', 'true', '처음 준비(구조 · 기본 데이터)를 마치지 못한 채', ['start', 'stop --no-backup', 'start', 'migration up --local']),
    ('ok', 'false', '업무 DB 를 다시 켭니다(쌓인 데이터는 그대로)', ['start', 'stop', 'start', 'migration up --local']),
    ('ok', 'true', None, ['start', 'migration up --local']),
], ids=['처음_준비_도중_끊긴_DB', '끊긴_뒤_끄고_켠_DB', '메일함_꺼짐', '정상'])
def test_업무_DB를_켠_뒤_처음_준비가_끊긴_DB는_비우고_다시_준비하고_빠진_컨테이너는_다시_켠다(pc, tmp_path, db, inbucket, said, calls):
    """2026-11-25 실측(학생 PC 「Supabase 가 남아서 안 된다」): 처음 시작이 업무 DB 준비 도중 끊기면 CLI 는 다음 시작에서 「이미 켜짐」으로 보고
    빠진 메일함 · 시드를 채우지 않아, 다시 눌러도 끄고 켜도 process 가 「tenant hyd 없음」으로 죽었다. 시작은 그 DB 를 알아보고 비운 뒤 처음부터
    준비하고(정상 첫 시작과 같은 CLI 길), 시드가 있는데 메일함만 없거나 꺼졌으면 데이터를 둔 채 업무 DB 를 다시 켠다. 4단계는 일부러 멈춘다(이
    시험은 3단계를 잰다 — 그 뒤 단계가 이 PC 의 진짜 포털을 부르지 않게)."""
    log = tmp_path / 'npx.log'
    code, text = pc('start_all.sh', db=db, inbucket_running=inbucket, calls=log, up_exit=1, up_output='3단계 뒤에서 멈춤')
    assert [line.split(' ', 2)[2] for line in log.read_text(encoding='utf-8').splitlines()] == calls, text
    assert (said in text) if said else ('처음 준비' not in text and '다시 켭니다' not in text), text
    assert '4/8' in text and '시스템을 켜지 못했습니다' in stopped(text)          # 3단계를 지나갔다


def test_업무_DB에_회사_없이_기록이_있으면_지우지_않고_까닭을_말하며_멈춘다(pc, tmp_path):
    log = tmp_path / 'npx.log'
    code, text = pc('start_all.sh', db='data', calls=log)
    assert code == 1 and '업무 DB 의 상태를 확인하지 못했습니다' in stopped(text) and 'public.users 3줄' in text and '지우지 않고 멈춥니다' in text
    assert [line.split(' ', 2)[2] for line in log.read_text(encoding='utf-8').splitlines()] == ['start'] and '4/8' not in text


@pytest.mark.parametrize('known, note', [(False, True), (True, False)], ids=['이름 기록 없음', '이름 기록 있음'])
def test_끄기는_업무_DB_이름_기록이_없어_기본_이름으로_껐으면_그렇게_말한다(pc, known, note):
    """전수 대조 07-20: it/supabase/.env 가 없으면 Supabase CLI 는 커밋된 기본 이름(config.toml project_id)의 업무 DB 를 끈다 — 다른 폴더의 업무 DB 일 수
    있는데 「꺼짐」만 말했다."""
    if known:
        (pc.repo / 'it' / 'supabase' / '.env').write_text('SUPABASE_PROJECT_ID=hyd-mine\n', encoding='utf-8', newline='\n')
    code, text = pc('stop_all.sh')
    assert code == 0 and '꺼짐: 이 폴더의 시스템과 업무 DB' in text, text
    assert ('기본 이름(hyd-portal-latest)의 업무 DB를 껐습니다' in text) is note
