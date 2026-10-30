"""Mac PATH 준비(scripts/macos_paths.sh 의 hyd_brew_first) — Homebrew 를 /usr/bin 「항목」 바로 앞에 끼우고, 다른 항목은 깨뜨리지 않는다.

규칙: PATH 는 「:」로 나뉜 항목 목록이다. 결과의 항목 목록 = 원래 항목 목록에서 첫 /usr/bin 항목 바로 앞에 Homebrew 항목들을 끼운 것
(/usr/bin 항목이 없으면 끝에 붙인 것). 옛 판은 글자 치환이라 macOS 13+ 의 /System/Cryptexes/App/usr/bin 안의 「/usr/bin」에 걸려
그 항목을 /System/Cryptexes/App/opt/homebrew/bin 으로 깨뜨리고 독립된 /opt/homebrew/bin 항목을 만들지 못했다(점검3_I I-02, 재현).
bash 함수를 bash(3.2 호환 문법)로 직접 부른다.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'macos_paths.sh'
BREW = ['/opt/homebrew/bin', '/usr/local/bin']


def bash() -> str:
    for candidate in (r'C:\Program Files\Git\bin\bash.exe', shutil.which('bash')):
        if candidate and Path(candidate).exists():
            return candidate
    pytest.fail('bash 가 없어 macos_paths.sh 를 돌리지 못했다 — Git for Windows(또는 bash)를 설치한다', pytrace=False)


def brew_first(path: str, brew: list[str]) -> list[str]:
    out = subprocess.run([bash(), '-c', '. "$1"; hyd_brew_first "$2" "$3"', '_', SCRIPT.as_posix(), path, ''.join(f'{b}:' for b in brew)],
                         capture_output=True, text=True, check=True)
    return out.stdout.split(':')


@pytest.mark.parametrize('path', [
    '/usr/local/bin:/System/Cryptexes/App/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin',      # macOS 13+ 기본(Finder 로 연 창)
    '/usr/bin:/bin:/usr/sbin:/sbin',                                                  # Cryptexes 없는 옛 macOS
    '/Users/me/.local/bin:/usr/bin:/bin',                                             # 사용자 항목이 앞에 있음
    '/bin:/usr/sbin',                                                                 # /usr/bin 항목이 없음
    '/opt/x/usr/bin/tools:/usr/bin:/usr/bin',                                         # 「/usr/bin」을 품은 다른 항목 · 같은 항목 두 번
])
def test_Homebrew는_usr_bin_항목_바로_앞에_끼고_다른_항목은_그대로다(path):
    entries = path.split(':')
    at = entries.index('/usr/bin') if '/usr/bin' in entries else len(entries)
    assert brew_first(path, BREW) == entries[:at] + BREW + entries[at:]


def test_끼울_항목이_없으면_PATH가_그대로다():
    path = '/usr/local/bin:/System/Cryptexes/App/usr/bin:/usr/bin:/bin'
    assert brew_first(path, []) == path.split(':')
