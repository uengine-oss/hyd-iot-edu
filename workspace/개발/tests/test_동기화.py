"""두 브랜치 동기화(workspace/동기화.py) — 명령줄 그대로 commit · push · pull 을 돌려 결과(브랜치 · 원격 · 작업 트리)를 본다.

규칙(정답의 출처 — 동기화.py 머리말):
  · main 에는 준 경로만, 작업 트리 모습 그대로, 실행 권한은 색인의 값대로 커밋한다(Windows core.filemode=false 에서 새 실행 파일도 100755).
  · 키 검사: 커밋은 그 커밋이 넣은 판을, push 는 origin 에 없는 커밋 하나하나를 본다 — 키를 넣고 지운 두 커밋도 push 하지 않는다.
  · GitHub 한도(100 MiB)를 넘는 파일이 든 커밋은 만들지 않는다. 커밋 메시지는 준 그대로다.
  · pull: 로컬 끝이 원격의 조상일 때만 앞으로. 원격이 고치거나 지운 파일은 로컬이 로컬 끝 판 그대로일 때만 바꾸거나 지우고,
    로컬에서 고친 파일과 겹치면 아무것도 쓰지 않고 멈춘다. 원격이 안 바꾼 파일은 로컬에서 고치거나 지웠어도 그대로 둔다.
  · commit: 원격이 로컬 끝보다 앞서 있으면 커밋하지 않고 pull 을 먼저 하라고 멈춘다.
  · 이 PC 전용 색인(.git/hyd-workspace.index)은 바뀐 파일만 다시 해시할 뿐 결과는 색인이 없을 때와 같다 — 지운 파일은 빠지고,
    크기 · 시각이 같게 고친 판도 들어가고, 빼는 자리지만 브랜치에 있는 파일은 pull 이 지금 파일로 견준다.
실제 git 으로 임시 원격(bare) 하나와 PC 두 대(clone)를 만든다. 이 저장소는 건드리지 않는다. 도구는 그 PC의 workspace/ 에 복사한 것을 그대로 부른다.
"""
import os
import shutil
import subprocess
import sys
import time

import pytest

from conftest import git, ROOT
TOOLS = {'workspace/동기화.py': ROOT / 'workspace' / '동기화.py', 'workspace/secret_scan.py': ROOT / 'workspace' / 'secret_scan.py',
         'scripts/hyd_env.py': ROOT / 'scripts' / 'hyd_env.py'}
ENV = {k: v for k, v in os.environ.items() if k not in ('HYD_ELEVENLABS_KEY_FILE', 'HYD_VSCODE_TOKEN_FILE')} | {'PYTHONUTF8': '1'}
RELAY = 'hyd' + 'relay' + '9Zq4' * 4         # 꼴 없는 키(이 파일이 걸리지 않게 조각으로)




def sync(repo, *args, script='workspace/동기화.py'):
    return subprocess.run([sys.executable, str(repo / script), *args], cwd=repo, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=ENV)


def identity(repo):
    git(repo, 'config', 'user.email', 't@example.invalid'); git(repo, 'config', 'user.name', 'test')
    git(repo, 'config', 'core.filemode', 'false')                  # Windows 와 같게


@pytest.fixture(scope='session')
def _template(tmp_path_factory):
    """원격 + 첫 PC(A)의 처음 모양을 묶음에 한 번만 만든다(명령줄 commit · push 가 들어가 몇 초씩 걸린다). 테스트마다 복사해 쓴다."""
    root = tmp_path_factory.mktemp('sync-template')
    _build_origin(root)
    return root


@pytest.fixture
def origin(_template, tmp_path):
    """원격 + 첫 PC(A): main(.gitignore · .gitattributes · scripts/hyd_env.py · 파일 둘) · workspace(파일 둘) 를 올려 둔 모양의 사본."""
    shutil.copytree(_template, tmp_path, dirs_exist_ok=True)
    remote, a = tmp_path / 'origin.git', tmp_path / 'A'
    git(a, 'remote', 'set-url', 'origin', str(remote))                # 사본의 원격 = 사본의 bare 저장소
    return remote, a


def _build_origin(tmp_path):
    remote, a = tmp_path / 'origin.git', tmp_path / 'A'
    git(tmp_path, 'init', '-q', '--bare', '-b', 'main', str(remote))   # 실제 원격처럼 HEAD = main(clone이 main을 체크아웃한다)
    git(tmp_path, 'init', '-q', '-b', 'main', str(a))
    identity(a)
    git(a, 'remote', 'add', 'origin', str(remote))
    shutil.copyfile(ROOT / '.gitignore', a / '.gitignore')
    shutil.copyfile(ROOT / '.gitattributes', a / '.gitattributes')                 # 줄끝 규칙도 실제와 같게
    for rel, src in TOOLS.items():
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, a / rel)
    (a / 'kept.txt').write_text('처음\n', encoding='utf-8')
    (a / 'gone.txt').write_text('지울 것\n', encoding='utf-8')
    git(a, 'add', '.gitignore', '.gitattributes', 'scripts/hyd_env.py', 'kept.txt', 'gone.txt'); git(a, 'commit', '-q', '-m', 'first')
    readme = git(a, 'hash-object', '-w', '--stdin', inp='# workspace\n')
    tree = git(a, 'mktree', inp=f'100644 blob {readme}\tREADME.md\n')
    git(a, 'update-ref', 'refs/heads/workspace', git(a, 'commit-tree', tree, '-m', 'workspace 처음'))
    git(a, 'push', '-q', 'origin', 'main', 'workspace')
    (a / 'workspace' / 'doc.txt').write_text('하나\n', encoding='utf-8')
    (a / 'workspace' / 'note.txt').write_text('둘\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 첫 작업 자료').returncode == 0
    assert sync(a, 'push').returncode == 0
    return remote, a


def second_pc(tmp_path, remote):
    """새 PC(B): main 을 clone 하고 README 안내대로 동기화.py 를 꺼내 pull."""
    b = tmp_path / 'B'
    git(tmp_path, 'clone', '-q', str(remote), str(b))
    identity(b)
    git(b, 'fetch', '-q', 'origin', '+refs/heads/workspace:refs/remotes/origin/workspace')
    (b / '동기화.py').write_bytes(subprocess.run(['git', 'show', 'origin/workspace:workspace/동기화.py'], cwd=b, capture_output=True, check=True).stdout)
    out = sync(b, 'pull', script='동기화.py')
    (b / '동기화.py').unlink()
    assert out.returncode == 0, out.stderr
    return b


def branch_put(repo, path, text, msg):
    """동기화.py가 올리지 않는 자리의 파일을 git으로 직접 workspace 브랜치에 넣어 올린다(빼는 목록이 다른 PC · 옛 판이 올린 브랜치와 같은 모양)."""
    env = os.environ | {'GIT_INDEX_FILE': str(repo / '.git' / 'test-index')}
    run = lambda *a, inp=None: subprocess.run(['git', *a], cwd=repo, env=env, check=True, capture_output=True, text=True,
                                              encoding='utf-8', input=inp).stdout.strip()
    tip = run('rev-parse', 'refs/heads/workspace')
    run('read-tree', tip)
    run('update-index', '--add', '--cacheinfo', f"100644,{run('hash-object', '-w', '--stdin', inp=text)},{path}")
    run('update-ref', 'refs/heads/workspace', run('commit-tree', run('write-tree'), '-p', tip, '-m', msg), tip)
    run('push', '-q', 'origin', 'workspace')


def modes(repo, ref='HEAD'):
    return {line.split('\t')[1]: line.split()[0] for line in git(repo, 'ls-tree', '-r', ref).splitlines()}


def remote_tip(repo, branch):
    return git(repo, 'ls-remote', 'origin', f'refs/heads/{branch}').split()[0]


# ---------------------------------------------------------------- commit
def test_main에는_준_경로만_작업_트리_모습으로_커밋하고_새_실행_파일은_실행_권한을_지킨다(origin):
    _, a = origin
    (a / '시작.command').write_text('#!/bin/bash\necho hi\n', encoding='utf-8')
    git(a, 'add', '시작.command'); git(a, 'update-index', '--chmod=+x', '--', '시작.command')
    (a / 'kept.txt').write_text('고침\n', encoding='utf-8')
    (a / 'gone.txt').unlink()
    (a / 'other.txt').write_text('다른 작업\n', encoding='utf-8'); git(a, 'add', 'other.txt')     # 섞이면 안 되는 남의 변경
    out = sync(a, 'commit', '실행 파일', '시작.command', 'kept.txt', 'gone.txt')
    assert out.returncode == 0, out.stderr
    assert {k: v for k, v in modes(a).items() if not k.startswith('scripts/')} == {'.gitattributes': '100644', '.gitignore': '100644', 'kept.txt': '100644', '시작.command': '100755'}
    assert git(a, 'show', 'HEAD:kept.txt') == '고침'
    assert git(a, 'status', '--porcelain').splitlines() == ['A  other.txt']


def test_만을_주면_workspace에서도_준_경로만_바꾸고_다른_작업은_브랜치_끝_그대로_둔다(origin):
    _, a = origin
    before = git(a, 'show', 'refs/heads/workspace:workspace/note.txt')
    (a / 'workspace' / 'doc.txt').write_text('고침\n', encoding='utf-8')
    (a / 'workspace' / 'note.txt').write_text('다른 작업의 미완성\n', encoding='utf-8')
    (a / 'workspace' / 'new').mkdir()
    (a / 'workspace' / 'new' / 'a.txt').write_text('새 파일\n', encoding='utf-8')
    (a / 'workspace' / 'wip.txt').write_text('다른 작업의 새 파일\n', encoding='utf-8')
    out = sync(a, 'commit', '한정 커밋', '--만', 'workspace/doc.txt', 'workspace/new/')
    assert out.returncode == 0, out.stderr
    names = git(a, 'ls-tree', '-r', '--name-only', 'refs/heads/workspace').splitlines()
    assert git(a, 'show', 'refs/heads/workspace:workspace/doc.txt') == '고침'
    assert git(a, 'show', 'refs/heads/workspace:workspace/new/a.txt') == '새 파일'
    assert git(a, 'show', 'refs/heads/workspace:workspace/note.txt') == before
    assert 'workspace/wip.txt' not in names and 'README.md' in names and 'workspace/동기화.py' in names
    assert '내용 다름 1' in sync(a, 'status').stdout                      # note.txt 내용이 다른 것을 상태가 알린다


def test_만으로_준_경로가_로컬에서_지워졌으면_브랜치에서도_뺀다(origin):
    _, a = origin
    (a / 'workspace' / 'doc.txt').unlink()
    out = sync(a, 'commit', '지움', '--만', 'workspace/doc.txt')
    assert out.returncode == 0, out.stderr
    assert 'workspace/doc.txt' not in git(a, 'ls-tree', '-r', '--name-only', 'refs/heads/workspace').splitlines()


def test_다시_만드는_장_그림_장_조각_폴더와_캐시는_전체_커밋에도_올리지_않는다(origin):
    _, a = origin
    for rel in ('슬라이드/덱/s-01.png', 'tools/video/조각_저장/합성/x.mp4', '__pycache__/x.pyc', 'keep.txt'):
        (a / 'workspace' / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / 'workspace' / rel).write_text('x', encoding='utf-8')
    assert sync(a, 'commit', '전체').returncode == 0
    names = git(a, 'ls-tree', '-r', '--name-only', 'refs/heads/workspace').splitlines()
    assert 'workspace/keep.txt' in names and not [n for n in names if '슬라이드' in n or '조각_저장' in n or '__pycache__' in n]


def test_이_PC_전용_색인을_지워도_있어도_전체_commit은_브랜치_끝과_같은_트리를_만든다(origin):
    _, a = origin
    cache = a / '.git' / 'hyd-workspace.index'
    cache.unlink()                                                      # 처음 받은 PC · 색인을 잃은 PC
    assert '바뀐 것이 없다' in sync(a, 'commit', '색인 없이').stdout
    assert cache.is_file() and '바뀐 것이 없다' in sync(a, 'commit', '색인으로').stdout


def test_크기도_시각도_같게_곧바로_고친_판도_커밋에_들어간다(origin):
    _, a = origin
    git(a, 'config', 'core.checkStat', 'minimal'); git(a, 'config', 'core.trustctime', 'false')   # stat 으로는 못 가르는 가장 거친 설정
    doc, stamp = a / 'workspace' / 'doc.txt', time.time_ns() + 3600 * 10 ** 9   # 색인보다 늦은 시각 = git 이 stat 을 믿지 않고 내용을 다시 보는 자리
    doc.write_text('가나\n', encoding='utf-8'); os.utime(doc, ns=(stamp, stamp))
    assert sync(a, 'status').returncode == 0                            # 이 판이 이 PC 전용 색인에 들어간다
    doc.write_text('다라\n', encoding='utf-8'); os.utime(doc, ns=(stamp, stamp))
    assert sync(a, 'commit', '같은 크기').returncode == 0
    assert git(a, 'show', 'refs/heads/workspace:workspace/doc.txt') == '다라'


def test_이_PC_전용_색인에_있던_파일을_로컬에서_지우면_전체_commit에서_빠진다(origin):
    _, a = origin
    assert sync(a, 'status').returncode == 0                            # note.txt 가 색인에 있다
    (a / 'workspace' / 'note.txt').unlink()
    assert sync(a, 'commit', '지움').returncode == 0
    assert 'workspace/note.txt' not in git(a, 'ls-tree', '-r', '--name-only', 'refs/heads/workspace').splitlines()


def test_만의_경로가_어디에도_없으면_커밋하지_않고_경로를_알린다(origin):
    _, a = origin
    tip = git(a, 'rev-parse', 'refs/heads/workspace')
    out = sync(a, 'commit', '오타', '--만', 'workspace/없는파일.txt')
    assert out.returncode != 0 and 'workspace/없는파일.txt' in out.stderr
    assert git(a, 'rev-parse', 'refs/heads/workspace') == tip
    assert sync(a, 'commit', '빈 목록', '--만').returncode != 0


def test_준_경로에도_작업_자료에도_바뀐_것이_없으면_커밋하지_않는다(origin):
    _, a = origin
    heads = git(a, 'rev-parse', 'main', 'workspace')
    out = sync(a, 'commit', '아무것도', 'kept.txt')
    assert git(a, 'rev-parse', 'main', 'workspace') == heads and out.stdout.count('바뀐 것이 없다') == 2


def test_커밋_메시지는_준_그대로이고_공동_저자_줄을_붙이지_않는다(origin):
    _, a = origin
    (a / 'workspace' / 'doc.txt').write_text('셋\n', encoding='utf-8')
    (a / 'kept.txt').write_text('넷\n', encoding='utf-8')
    assert sync(a, 'commit', '메시지 그대로', 'kept.txt').returncode == 0
    assert git(a, 'log', '-1', '--format=%B', 'refs/heads/workspace') == git(a, 'log', '-1', '--format=%B', 'main') == '메시지 그대로'


def test_원격이_앞서_있으면_커밋하지_않고_pull을_먼저_하게_한_뒤_양쪽_변경이_함께_올라간다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    (a / 'workspace' / 'doc.txt').write_text('A가 고침\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 고침').returncode == 0 and sync(a, 'push').returncode == 0
    before = git(b, 'rev-parse', 'workspace')
    (b / 'workspace' / 'note.txt').write_text('B가 고침\n', encoding='utf-8')
    out = sync(b, 'commit', 'B 고침', '--만', 'workspace/note.txt')
    assert out.returncode == 1 and 'pull' in out.stderr and git(b, 'rev-parse', 'workspace') == before
    assert sync(b, 'pull').returncode == 0
    assert sync(b, 'commit', 'B 고침', '--만', 'workspace/note.txt').returncode == 0 and sync(b, 'push').returncode == 0
    tip = remote_tip(b, 'workspace')
    assert git(b, 'show', f'{tip}:workspace/doc.txt') == 'A가 고침' and git(b, 'show', f'{tip}:workspace/note.txt') == 'B가 고침'


def test_키가_든_파일은_main에도_workspace에도_붙이지_않는다(origin):
    _, a = origin
    heads = git(a, 'rev-parse', 'main', 'workspace')
    (a / 'settings.yaml').write_text(f'LLM_API_KEY: {RELAY}\n', encoding='utf-8')
    main_out = sync(a, 'commit', '키 든 main', 'settings.yaml')
    (a / 'workspace' / 'keys.md').write_text(f'LLM_API_KEY={RELAY}\n', encoding='utf-8')
    ws_out = sync(a, 'commit', '키 든 workspace')
    assert (main_out.returncode, ws_out.returncode) == (1, 1)
    assert git(a, 'rev-parse', 'main', 'workspace') == heads
    assert 'settings.yaml:1' in main_out.stdout and 'workspace/keys.md:1' in ws_out.stdout and RELAY not in main_out.stdout + ws_out.stdout


def test_100MiB_넘는_파일이_든_커밋은_만들지_않고_이름과_크기를_알린다(origin):
    _, a = origin
    tip = git(a, 'rev-parse', 'workspace')
    with open(a / 'workspace' / 'big.mp4', 'wb') as f:
        f.truncate(100 * 1024 ** 2 + 1)
    out = sync(a, 'commit', '큰 영상')
    assert out.returncode == 1 and 'workspace/big.mp4 100.0 MiB' in out.stderr and git(a, 'rev-parse', 'workspace') == tip


# ---------------------------------------------------------------- push
def test_키를_넣고_지운_main_커밋이_있으면_push하지_않는다(origin):
    _, a = origin
    before = remote_tip(a, 'main')
    (a / 'settings.yaml').write_text(f'LLM_API_KEY: {RELAY}\n', encoding='utf-8')
    git(a, 'add', 'settings.yaml'); git(a, 'commit', '-q', '-m', '도구 밖에서 만든 커밋')
    (a / 'settings.yaml').write_text('LLM_API_KEY:\n', encoding='utf-8')
    git(a, 'add', 'settings.yaml'); git(a, 'commit', '-q', '-m', '키를 지움')
    assert git(a, 'show', 'main:settings.yaml') == 'LLM_API_KEY:'           # 끝 트리는 깨끗하다
    out = sync(a, 'push')
    assert out.returncode == 1 and 'settings.yaml:1' in out.stdout and remote_tip(a, 'main') == before


def test_깨끗한_커밋은_push해서_두_브랜치가_원격과_같아진다(origin):
    _, a = origin
    (a / 'workspace' / 'doc.txt').write_text('올림\n', encoding='utf-8')
    (a / 'kept.txt').write_text('올림\n', encoding='utf-8')
    assert sync(a, 'commit', '올림', 'kept.txt').returncode == 0
    assert sync(a, 'push').returncode == 0
    assert (remote_tip(a, 'main'), remote_tip(a, 'workspace')) == tuple(git(a, 'rev-parse', 'main', 'workspace').split())


# ---------------------------------------------------------------- pull
def test_새_PC는_원격의_작업_자료를_제자리에_받는다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    assert (b / 'workspace' / 'doc.txt').read_text(encoding='utf-8') == '하나\n' and git(b, 'rev-parse', 'workspace') == remote_tip(b, 'workspace')


def test_원격이_고치고_지우고_더한_파일을_따라간다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    (a / 'workspace' / 'doc.txt').write_text('A가 고침\n', encoding='utf-8')
    (a / 'workspace' / 'note.txt').unlink()
    (a / 'workspace' / 'new.txt').write_text('새 파일\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 고침').returncode == 0 and sync(a, 'push').returncode == 0
    out = sync(b, 'pull')
    assert out.returncode == 0, out.stderr
    ws = b / 'workspace'
    assert ((ws / 'doc.txt').read_text(encoding='utf-8'), (ws / 'note.txt').exists(), (ws / 'new.txt').read_text(encoding='utf-8')) == ('A가 고침\n', False, '새 파일\n')
    assert git(b, 'rev-parse', 'workspace') == remote_tip(b, 'workspace')


def test_이_PC에서_고친_파일과_겹치면_아무것도_쓰지_않고_멈춘다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    before = git(b, 'rev-parse', 'workspace')
    (b / 'workspace' / 'doc.txt').write_text('B가 고침\n', encoding='utf-8')
    (a / 'workspace' / 'doc.txt').write_text('A가 고침\n', encoding='utf-8')
    (a / 'workspace' / 'new.txt').write_text('새 파일\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 고침').returncode == 0 and sync(a, 'push').returncode == 0
    out = sync(b, 'pull')
    assert out.returncode == 1 and 'workspace/doc.txt' in out.stderr
    assert (b / 'workspace' / 'doc.txt').read_text(encoding='utf-8') == 'B가 고침\n' and not (b / 'workspace' / 'new.txt').exists()
    assert git(b, 'rev-parse', 'workspace') == before
    assert f'git show {before[:8]}:' in out.stderr                     # 안내대로 로컬 끝 판으로 되돌리면 받아진다
    (b / 'workspace' / 'doc.txt').write_bytes(subprocess.run(['git', 'show', f'{before}:workspace/doc.txt'], cwd=b, capture_output=True, check=True).stdout)
    assert sync(b, 'pull').returncode == 0 and (b / 'workspace' / 'doc.txt').read_text(encoding='utf-8') == 'A가 고침\n'


def test_원격이_안_바꾼_파일은_이_PC에서_고치는_중이어도_그대로_두고_원격_변경을_받는다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    (b / 'workspace' / 'note.txt').write_text('B의 미커밋\n', encoding='utf-8')
    (a / 'workspace' / 'doc.txt').write_text('A가 고침\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 고침').returncode == 0 and sync(a, 'push').returncode == 0
    out = sync(b, 'pull')
    assert out.returncode == 0, out.stderr
    assert (b / 'workspace' / 'doc.txt').read_text(encoding='utf-8') == 'A가 고침\n'
    assert (b / 'workspace' / 'note.txt').read_text(encoding='utf-8') == 'B의 미커밋\n'
    assert git(b, 'rev-parse', 'workspace') == remote_tip(b, 'workspace')


def test_이_PC에만_있는_파일과_같은_이름을_원격이_다른_내용으로_올리면_멈춘다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    before = git(b, 'rev-parse', 'workspace')
    (b / 'workspace' / 'video.mp4').write_text('이 PC의 옛 판\n', encoding='utf-8')
    (a / 'workspace' / 'video.mp4').write_text('원격의 새 판\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 영상').returncode == 0 and sync(a, 'push').returncode == 0
    out = sync(b, 'pull')
    assert out.returncode == 1 and 'workspace/video.mp4' in out.stderr
    assert (b / 'workspace' / 'video.mp4').read_text(encoding='utf-8') == '이 PC의 옛 판\n' and git(b, 'rev-parse', 'workspace') == before
    (b / 'workspace' / 'video.mp4').unlink()                           # 안내대로 치우면 받아진다
    assert sync(b, 'pull').returncode == 0 and (b / 'workspace' / 'video.mp4').read_text(encoding='utf-8') == '원격의 새 판\n'


def test_빼는_자리지만_브랜치에_있는_파일은_pull이_지금_파일로_견주어_원격_판을_받는다(origin, tmp_path):
    remote, a = origin
    branch_put(a, 'workspace/슬라이드/s-01.png', '하나', '빼는 자리 첫 판')
    b = second_pc(tmp_path, remote)
    png = b / 'workspace' / '슬라이드' / 's-01.png'
    assert png.read_text(encoding='utf-8') == '하나'
    branch_put(a, 'workspace/슬라이드/s-01.png', '둘', '빼는 자리 고친 판')
    out = sync(b, 'pull')
    assert out.returncode == 0, out.stderr                             # 「이 PC에서 지웠다」로 잘못 멈추지 않는다
    assert png.read_text(encoding='utf-8') == '둘'


def test_이_PC에서_지운_파일은_되살리지_않는다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    (b / 'workspace' / 'note.txt').unlink()                            # 이 PC에서 지움(아직 commit 전)
    (a / 'workspace' / 'doc.txt').write_text('A가 고침\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 고침').returncode == 0 and sync(a, 'push').returncode == 0
    assert sync(b, 'pull').returncode == 0
    assert not (b / 'workspace' / 'note.txt').exists() and (b / 'workspace' / 'doc.txt').read_text(encoding='utf-8') == 'A가 고침\n'


def test_올리지_않은_로컬_커밋이_있으면_원격_판으로_떼어_내지_않고_멈춘다(origin, tmp_path):
    remote, a = origin
    b = second_pc(tmp_path, remote)
    (b / 'workspace' / 'b.txt').write_text('B의 일\n', encoding='utf-8')
    assert sync(b, 'commit', 'B 커밋(올리지 않음)').returncode == 0
    mine = git(b, 'rev-parse', 'workspace')
    (a / 'workspace' / 'doc.txt').write_text('A가 고침\n', encoding='utf-8')
    assert sync(a, 'commit', 'A 고침').returncode == 0 and sync(a, 'push').returncode == 0
    out = sync(b, 'pull')
    assert out.returncode == 1 and '갈라졌다' in out.stderr and git(b, 'rev-parse', 'workspace') == mine
