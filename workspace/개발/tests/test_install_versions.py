"""설치 기준 판(scripts/versions.txt) — Windows 설치와 Mac 설치가 같은 최소 판을 요구한다(점검3_I I-08).

규칙: 「같거나 높으면 그대로」의 기준은 두 OS 가 같다. 옛 판은 Mac 만 VS Code 1.143.0 · Python 3.14.7 을 요구해, 3.13 이 있는
Mac 도 Homebrew 설치를 거쳤다(Windows · README 는 VS Code 1.132.0 · Python 3.13 이상 유지).
Mac 설치(scripts/install_macos.sh)는 main 이 도는 목록 함수(required_packages)를 그대로 부른다(설치는 하지 않는다).
Windows 쪽은 설치 스크립트가 쓰는 Get-InstallVersions(scripts/install_version_policy.ps1)를 PowerShell 로 부른다.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import bash, ROOT




def mac_minimums() -> dict:
    """Mac 설치의 main 이 도는 목록(required_packages) 그대로 — 우리 함수를 바꿔 끼우지 않는다."""
    out = subprocess.run([bash(), '-c', '. scripts/install_macos.sh; required_packages'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert out.returncode == 0, out.stderr
    return {line.split()[0]: line.split()[1] for line in out.stdout.splitlines()}


def powershell(command: str, cwd: Path) -> subprocess.CompletedProcess:
    exe = shutil.which('powershell') or shutil.which('pwsh')
    if not exe:
        pytest.fail('PowerShell 이 없어 Windows 설치 기준을 읽지 못했다', pytrace=False)
    return subprocess.run([exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', '[Console]::OutputEncoding = [Text.Encoding]::UTF8; ' + command],
                          cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')


def windows_versions() -> dict:
    out = powershell('. ./scripts/install_version_policy.ps1; Get-InstallVersions | ConvertTo-Json -Compress', ROOT)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.parametrize('package, key', [
    ('docker-desktop', 'DOCKER_DESKTOP_MIN'),
    ('visual-studio-code', 'VSCODE_MIN'),
    ('node', 'NODE_MIN'),
    ('git', 'GIT_MIN'),
    ('python@3.14', 'PYTHON_MIN'),                  # Python 은 있는 판이 기준 이상이면 그대로(새로 넣을 때만 PYTHON_NEW 판)
])
def test_Mac_설치가_요구하는_최소_판은_Windows_설치와_같다(package, key):
    assert mac_minimums()[package] == windows_versions()[key]


def test_기준_판_파일의_줄이_빠지면_Windows_설치는_시작하지_않는다(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    shutil.copy(ROOT / 'scripts' / 'install_version_policy.ps1', scripts)
    (scripts / 'versions.txt').write_text('DOCKER_DESKTOP_MIN=4.87.0\n', encoding='utf-8')
    out = powershell('. ./scripts/install_version_policy.ps1; Get-InstallVersions', tmp_path)
    assert out.returncode != 0 and 'VSCODE_MIN' in out.stderr + out.stdout


@pytest.mark.parametrize('key, program', [('VSCODE_MIN', 'VS Code'), ('NODE_MIN', 'Node.js'), ('GIT_MIN', 'Git'), ('PYTHON_MIN', 'Python'),
                                          ('WSL_MIN', 'WSL'), ('DOCKER_DESKTOP_MIN', 'Docker Desktop')])
def test_README_실행_환경_표의_기준_판은_versions_txt와_같다(key, program):
    """학생이 읽는 표(README 「실행 환경」)는 설치 · 시작이 읽는 기준 판과 같은 숫자다 — Git · WSL 도 「최신판」이 아니라 같은 규칙."""
    row = next(line for line in (ROOT / 'README.md').read_text(encoding='utf-8').splitlines() if line.startswith(f'| {program} |'))
    wanted = windows_versions()[key]
    assert row.split('|')[2].strip().startswith(wanted[:-2] if key == 'PYTHON_MIN' else wanted)   # Python 은 「3.13 이상」으로 적는다


def test_winget이_없으면_학생이_할_일을_한국어로_알린다(tmp_path):
    """설치 도구를 찾는 함수를 실제로 부르되, 운영체제 쪽(PATH · 앱 목록)만 비운다."""
    out = powershell(f"$env:Path = '{tmp_path}'; function Get-AppxPackage {{ }}; . ./scripts/install_windows_winget.ps1; "
                     "try { Resolve-WingetExecutable } catch { $_.Exception.Message }", ROOT)
    assert '앱 설치 관리자' in out.stdout and '설치.bat을 다시 실행' in out.stdout and 'unavailable' not in out.stdout
