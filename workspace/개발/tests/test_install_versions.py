"""설치 기준 판(scripts/versions.txt) — Windows 설치와 Mac 설치가 같은 최소 판을 요구한다(점검3_I I-08).

규칙: 「같거나 높으면 그대로」의 기준은 두 OS 가 같다. 옛 판은 Mac 만 VS Code 1.143.0 · Python 3.14.7 을 요구해, 3.13 이 있는
Mac 도 Homebrew 설치를 거쳤다(Windows · README 는 VS Code 1.132.0 · Python 3.13 이상 유지).
Mac 설치(scripts/install_macos.sh)의 main 을 실제로 부르되, 설치하는 함수(ensure_package)와 OS 확인 · npx 만 대역으로 바꿔 요구 판을 받는다.
Windows 쪽은 설치 스크립트가 쓰는 Get-InstallVersions(scripts/install_version_policy.ps1)를 PowerShell 로 부른다.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def bash() -> str:
    for candidate in (r'C:\Program Files\Git\bin\bash.exe', shutil.which('bash')):
        if candidate and Path(candidate).exists():
            return candidate
    pytest.fail('bash 가 없어 install_macos.sh 를 돌리지 못했다', pytrace=False)


def mac_minimums() -> dict:
    script = ('. scripts/install_macos.sh; uname() { echo Darwin; }; id() { echo 501; }; npx() { echo "$SUPABASE_CLI"; }; '
              'ensure_package() { echo "PKG $1 $2"; }; main 2>/dev/null | grep "^PKG"')
    out = subprocess.run([bash(), '-c', script], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    return {line.split()[1]: line.split()[2] for line in out.stdout.splitlines()}


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
