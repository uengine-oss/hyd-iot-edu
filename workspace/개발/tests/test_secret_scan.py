"""키 검사(workspace/secret_scan.py) — 공개 저장소에 올리기 전에 키가 든 파일 판 · 커밋을 잡는가.

규칙(정답의 출처 — 이 파일 머리말과 workspace/동기화.py 머리말):
  · push 전 검사는 끝 트리가 아니라 올릴 커밋 하나하나를 본다 — 키를 넣은 커밋 뒤에 지우는 커밋을 더해도 앞 커밋은 이력으로 공개된다.
  · 키 꼴(sk- 등)은 어디서나, 키 이름 줄(`…API_KEY=값` 등)은 코드가 아닌 모든 텍스트에서, `.env` 의 실제 값은 꼴과 상관없이 잡는다.
  · AI 녹화(.gz) · 학생 ZIP 은 풀어서 본다. 시험용 가짜 값 · 자리표시(`${SECRET:이름}`) · 화면에 가린 값 · 변수 이름은 키가 아니다.
git 은 실제 git 으로 임시 저장소를 만든다(이 저장소는 건드리지 않는다). 가짜 키는 이 파일 안에서 조각을 이어 만든다(이 파일이 걸리지 않게).
"""
import gzip
import importlib.util
import io
import os
import subprocess
import sys
import zipfile

import pytest

from conftest import ROOT, git
SCRIPT = ROOT / 'workspace' / 'secret_scan.py'
_spec = importlib.util.spec_from_file_location('secret_scan', SCRIPT)
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)

SK = 'sk-' + 'Q7w' * 10                      # OpenAI 꼴
RELAY = 'hyd' + 'relay' + '9Zq4' * 4         # 꼴 없는 키(LiteLLM 사용자 지정 키 같은 것)
NAME = 'LLM' + '_API_KEY'


def hits(name, text, secrets=()):
    return ss.scan(name, text.encode('utf-8') if isinstance(text, str) else text, list(secrets))


# ---------------------------------------------------------------- 한 파일의 규칙
@pytest.mark.parametrize('name, text, expected', [
    ('notes.py', f'x = "{SK}"\n', 1),                                   # 키 꼴은 코드에서도
    ('.env.example', f'{NAME}={RELAY}\n', 1),                            # 학생 템플릿에 붙여 넣은 꼴 없는 키
    ('compose.yaml', f'    environment:\n      - {NAME}={RELAY}\n', 1),  # 목록형
    ('compose.yaml', f'      {NAME}: {RELAY}\n', 1),
    ('settings.json', f'{{"{NAME}": "{RELAY}"}}\n', 1),
    ('run.sh', f'export {NAME}={RELAY}\n', 1),
    ('start.bat', f'set {NAME}={RELAY}\n', 1),
    ('start.ps1', f'$env:{NAME}="{RELAY}"\n', 1),
    ('seed.sql', f'insert into t values (\'{{"{NAME}": "{RELAY}"}}\');\n', 1),
    ('.env', f'MY_SERVICE_KEY={RELAY}\n', 1),                            # .env 는 KEY 가 든 이름이면 값이 있으면
], ids=['코드의_키_꼴', 'env_example', 'compose_목록', 'compose_칸', 'JSON', 'sh_export', 'bat_set', 'ps1_env', 'SQL', 'env_KEY_이름'])
def test_키가_든_줄은_파일_꼴과_상관없이_잡힌다(name, text, expected):
    assert hits(name, text) == expected


@pytest.mark.parametrize('name, text', [
    ('main.py', f'{NAME} = os.environ.get("{NAME}")\n'),                 # 코드의 대입(값이 아니라 식)
    ('test_x.py', f"env = {{'{NAME}': '{RELAY}'}}\n"),                  # 코드 파일의 이름 줄은 키 꼴 · 실제 값으로만 본다
    ('deck.md', '"Authorization": "Bearer ${SECRET:GOOGLE_TOKEN}"\n'),   # 자리표시
    ('seed.sh', 'PASS=${NEO4J_PASSWORD:-hydpass123}\n'),                 # 셸 기본값 자리
    ('facts.md', '`"NEO4J_PASSWORD": "********"` 처럼 화면에서 가린다\n'),
    ('deck.md', '"NEO4J_PASSWORD": "＊＊＊＊＊＊＊＊"\n'),
    ('.env.example', f'{NAME}=\n'),                                      # 빈 틀
    ('compose.yaml', f'      {NAME}: ${{{NAME}:-}}\n'),                 # compose 치환
    ('notes.md', f'{NAME}=your-key-here-please\n'),                      # 가짜 낱말
    ('notes.md', 'PROCESS_CALLER_TOKEN: RELAY_TOKEN_NAME\n'),            # 값이 아니라 이름
    ('compose.yaml', 'EMQX_DASHBOARD__DEFAULT_PASSWORD: public123   # 로컬 공개 초기값 · 키검사: 허용\n'),
], ids=['코드_대입', '코드_테스트_값', 'SECRET_자리표시', '셸_기본값', '가린_값', '전각_가린_값', '빈_틀', 'compose_치환', '가짜_낱말', '변수_이름', '허용_표시'])
def test_자리표시_가린_값_가짜_값은_키가_아니다(name, text):
    assert hits(name, text) == 0


def test_AI_녹화와_학생_ZIP은_풀어서_본다():
    record = gzip.compress(f'{{"tool_output": "{NAME}={RELAY}"}}'.encode())
    pack = io.BytesIO()
    with zipfile.ZipFile(pack, 'w') as z:
        z.writestr('lab/.env', f'{NAME}={RELAY}\n')
    assert (hits('it/agent-worker/replay/a.json.gz', record), hits('lab.zip', pack.getvalue())) == (1, 2)   # ZIP 안 .env: 이름 줄 + .env 값


def test_실제_값은_꼴이_없어도_어느_파일에서나_잡히고_허용_표시로도_빠지지_않는다():
    text = f'const k = "{RELAY}"  // 키검사: 허용\n'
    assert hits('app.js', text, [('.env의 LLM_API_KEY', RELAY.encode())]) == 1


def test_걸린_곳은_경로와_줄만_찍고_값은_찍지_않는다(capsys):
    hits('compose.yaml', f'a: 1\n{NAME}: {RELAY}\n')
    out = capsys.readouterr().out
    assert out.strip() == 'compose.yaml:2: 값이 든 키 이름 줄' and RELAY not in out


# ---------------------------------------------------------------- git: 트리 · 범위 · 올릴 것
def run(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in ('HYD_ELEVENLABS_KEY_FILE', 'HYD_VSCODE_TOKEN_FILE')} | {'PYTHONUTF8': '1'}
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=repo, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=env)


@pytest.fixture
def repo(tmp_path):
    origin, work = tmp_path / 'origin.git', tmp_path / 'work'
    git(tmp_path, 'init', '-q', '--bare', str(origin))
    git(tmp_path, 'init', '-q', '-b', 'main', str(work))
    git(work, 'config', 'user.email', 't@example.invalid'); git(work, 'config', 'user.name', 'test')
    git(work, 'remote', 'add', 'origin', str(origin))
    (work / 'README.md').write_text('처음\n', encoding='utf-8')
    git(work, 'add', '.'); git(work, 'commit', '-q', '-m', 'first'); git(work, 'push', '-q', 'origin', 'main')
    return work


def commit(repo, name, text, message='change'):
    (repo / name).write_text(text, encoding='utf-8')
    git(repo, 'add', name); git(repo, 'commit', '-q', '-m', message)
    return git(repo, 'rev-parse', 'HEAD')


def test_키를_넣고_지운_두_커밋은_끝_트리는_깨끗해도_범위_검사가_앞_커밋을_잡는다(repo):
    base = git(repo, 'rev-parse', 'HEAD')
    commit(repo, 'config.yaml', f'{NAME}: {RELAY}\n', 'add key')
    commit(repo, 'config.yaml', 'nothing: here\n', 'remove key')
    tree, span = run(repo, 'main'), run(repo, f'{base}..main')
    assert (tree.returncode, span.returncode) == (0, 1)
    assert 'config.yaml:1: 값이 든 키 이름 줄' in span.stdout and RELAY not in span.stdout


def test_올릴것은_origin에_없는_커밋만_보고_처음_올리는_브랜치는_이력_전부를_본다(repo):
    commit(repo, 'old.yaml', f'{NAME}: {RELAY}\n')
    git(repo, 'push', '-q', 'origin', 'main')                        # 이미 공개된 판(지금 검사로는 되돌릴 수 없다 — 키를 바꾼다)
    commit(repo, 'new.txt', '평범한 글\n')
    assert run(repo, 'main', '--올릴것').returncode == 0              # origin 에 없는 커밋은 new.txt 하나
    git(repo, 'checkout', '-q', '--orphan', 'side'); git(repo, 'rm', '-rq', '--cached', '.')
    commit(repo, 'side.yaml', f'{NAME}: {RELAY}\n')
    assert run(repo, 'side', '--올릴것').returncode == 1               # origin 에 없는 브랜치: 이력 전부


def test_커밋_메시지의_키도_잡는다(repo):
    base = git(repo, 'rev-parse', 'HEAD')
    commit(repo, 'a.txt', 'a\n', f'debug {SK}')
    out = run(repo, f'{base}..main')
    assert out.returncode == 1 and '메시지' in out.stdout


def test_저장소_env의_실제_값이_꼴_없이_들어간_파일을_잡는다(repo):
    (repo / '.env').write_text(f'{NAME}={RELAY}\n', encoding='utf-8')      # git 밖(.gitignore 없이도 add 하지 않는다)
    base = git(repo, 'rev-parse', 'HEAD')
    commit(repo, 'notes.py', f'print("{RELAY}")\n')
    out = run(repo, f'{base}..main')
    assert out.returncode == 1 and 'notes.py:1: .env의 LLM_API_KEY의 실제 값' in out.stdout and RELAY not in out.stdout


def test_git이_모르는_이름이면_까닭을_내고_2로_끝난다(repo):
    out = run(repo, 'no-such-branch')
    assert out.returncode == 2 and 'no-such-branch' in out.stderr
