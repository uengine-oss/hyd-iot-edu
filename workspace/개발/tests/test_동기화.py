"""두 브랜치 동기화(workspace/동기화.py `commit_main`) — main에는 준 경로만, 작업 트리 모습 그대로, 실행 권한은 색인의 값대로 커밋되는가.

임시 git 저장소에서 실제 git으로 돈다(이 저장소는 건드리지 않는다). Windows(core.filemode=false)에서 `git commit -- 경로`는 새 파일의
실행 권한(`git update-index --chmod=+x`)을 버려 setup/*.command가 두 번 100644로 올라갔다.
"""
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sync = importlib.import_module('동기화')


def git(repo, *args):
    return subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=repo, check=True, capture_output=True, text=True,
                          encoding='utf-8').stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, 'init', '-q', '-b', 'main')
    git(tmp_path, 'config', 'user.email', 't@example.invalid'); git(tmp_path, 'config', 'user.name', 'test')
    git(tmp_path, 'config', 'core.filemode', 'false')
    (tmp_path / 'kept.txt').write_text('처음\n', encoding='utf-8')
    (tmp_path / 'gone.txt').write_text('지울 것\n', encoding='utf-8')
    git(tmp_path, 'add', '.'); git(tmp_path, 'commit', '-q', '-m', 'first')
    monkeypatch.setattr(sync, 'ROOT', tmp_path)
    return tmp_path


def modes(repo, ref='HEAD'):
    return {line.split('\t')[1]: line.split()[0] for line in git(repo, 'ls-tree', '-r', ref).splitlines()}


def test_준_경로만_작업_트리_모습으로_커밋하고_새_실행_파일은_실행_권한을_지킨다(repo):
    (repo / '시작.command').write_text('#!/bin/bash\necho hi\n', encoding='utf-8')
    git(repo, 'add', '시작.command'); git(repo, 'update-index', '--chmod=+x', '--', '시작.command')
    (repo / 'kept.txt').write_text('고침\n', encoding='utf-8')
    (repo / 'gone.txt').unlink()
    (repo / 'other.txt').write_text('다른 작업\n', encoding='utf-8'); git(repo, 'add', 'other.txt')     # 섞이면 안 되는 남의 변경
    sync.commit_main('msg\n', ['시작.command', 'kept.txt', 'gone.txt'])
    assert modes(repo) == {'kept.txt': '100644', '시작.command': '100755'}
    assert git(repo, 'show', 'HEAD:kept.txt') == '고침\n'
    assert git(repo, 'status', '--porcelain').splitlines() == ['A  other.txt']


def test_준_경로에_바뀐_것이_없으면_커밋하지_않는다(repo, capsys):
    head = git(repo, 'rev-parse', 'HEAD')
    sync.commit_main('msg\n', ['kept.txt'])
    assert git(repo, 'rev-parse', 'HEAD') == head and '바뀐 것이 없다' in capsys.readouterr().out
