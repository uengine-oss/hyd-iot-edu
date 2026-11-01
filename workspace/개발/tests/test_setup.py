"""학생 실행 파일(setup/)과 그것이 부르는 scripts/ — 학생 clone 에 다 있고, 부르지 않는 파일은 없는가.

규칙(정답의 출처 — CLAUDE.md 1절 · .gitignore): scripts 에는 setup 의 실행 파일이 실제로 부르는 것만 둔다. 옛 판은 이것을 무시 목록(파일 목록의
둘째 사본)으로 지켜, 새 스크립트를 만들면 git 이 조용히 무시해 학생 clone 에서 빠질 수 있었다. 이제 이 테스트가 지킨다:
  · setup 에서 시작해 이름으로 닿는 scripts 파일(셸 `.` · 경로 · PowerShell Join-Path · 파이썬 import)은 모두 git 이 추적한다.
  · git 이 추적하는 scripts 파일은 모두 setup 에서 닿는다(쓰지 않는 파일이 학생 PC에 가지 않게).
  · Mac 실행 파일(.command)은 git 에 실행 권한(100755)으로 들어 있다(Windows core.filemode=false 에서 잃기 쉽다).
"""
import re
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT


def tracked(root: Path) -> dict[str, str]:
    """{경로: 모드} — git 색인."""
    out = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files', '-s', '-z', '--', 'setup', 'scripts'], cwd=root,
                         capture_output=True, check=True).stdout.decode('utf-8')
    return {entry.split('\t', 1)[1]: entry.split()[0] for entry in out.split('\0') if entry}


def reachable(root: Path) -> set[str]:
    """setup/* 에서 이름으로 닿는 scripts 파일(작업 트리에 있는 것 기준 — 추적 여부와 상관없이)."""
    candidates = {p.name: f'scripts/{p.name}' for p in (root / 'scripts').iterdir() if p.is_file() and p.suffix != '.pyc'}
    seen, todo = set(), [p for p in (root / 'setup').iterdir() if p.is_file()]
    while todo:
        text = todo.pop().read_text(encoding='utf-8-sig', errors='replace')
        for name, rel in candidates.items():
            stem = name[:-3] if name.endswith('.py') else None
            mentioned = re.search(rf'(?<![\w.-]){re.escape(name)}(?![\w-])', text) or (
                stem and re.search(rf'^\s*(?:import|from)\s+{re.escape(stem)}\b', text, re.M))
            if mentioned and rel not in seen:
                seen.add(rel)
                todo.append(root / rel)
    return seen


def test_setup이_부르는_scripts_파일은_모두_git에_있다():
    missing = sorted(reachable(ROOT) - set(tracked(ROOT)))
    assert not missing, f'학생 clone 에 빠지는 파일(git 에 없음 — git add 한다): {missing}'


def test_git의_scripts_파일은_모두_setup에서_닿는다():
    unused = sorted(p for p in tracked(ROOT) if p.startswith('scripts/') and p not in reachable(ROOT))
    assert not unused, f'setup 의 실행 파일이 부르지 않는 scripts 파일(지우거나 workspace/개발/scripts 로): {unused}'


def test_Mac_실행_파일은_git에_실행_권한으로_들어_있다():
    files = {p.name for p in (ROOT / 'setup').glob('*.command')}
    modes = tracked(ROOT)
    wrong = sorted(f'setup/{n} {modes.get(f"setup/{n}", "git 에 없음")}' for n in files if modes.get(f'setup/{n}') != '100755')
    assert files and not wrong, f'더블클릭이 안 되는 Mac 실행 파일(git add 뒤 git update-index --chmod=+x): {wrong}'


def test_Windows와_Mac에_같은_단계의_실행_파일이_있다():
    names = {p.stem: p.suffix for p in (ROOT / 'setup').iterdir()}
    stems = {p.stem for p in (ROOT / 'setup').iterdir()}
    assert {s for s in stems if not (ROOT / 'setup' / f'{s}.bat').exists() or not (ROOT / 'setup' / f'{s}.command').exists()} == set(), names


def test_이_검사는_새로_만들고_git에_넣지_않은_스크립트를_잡는다(tmp_path):
    """검사가 무엇을 잡는지의 확인: setup 이 부르는 새 스크립트를 git 에 넣지 않은 저장소."""
    for folder in ('setup', 'scripts'):
        (tmp_path / folder).mkdir()
    (tmp_path / 'setup' / '시작.bat').write_text('bash scripts/start_all.sh\n', encoding='utf-8')
    (tmp_path / 'scripts' / 'start_all.sh').write_text('. scripts/new_step.sh\n', encoding='utf-8')
    (tmp_path / 'scripts' / 'new_step.sh').write_text('echo new\n', encoding='utf-8')
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'add', 'setup/시작.bat', 'scripts/start_all.sh'], cwd=tmp_path, check=True)
    assert reachable(tmp_path) - set(tracked(tmp_path)) == {'scripts/new_step.sh'}
