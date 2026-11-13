"""CLI 격리(worker/cli_sandbox.py) — 설정 출처 · 훅 끔, 내장 도구 셋, 승인 스킬만 읽기 전용 묶음, 격리를 켤 수 없는 곳에서는 실행하지 않는다.

Landlock 이 실제로 무는지는 이 PC(Windows)에서 잴 수 없다 — 워커 이미지 안에서는 시작 때 verify() 가 잰다(FG_고침.md 에 docker exec 실측)."""
import json
import sys

import pytest

from worker import cli_sandbox

SKILL = {'skill_name': 'my-review', 'description': '검토', 'content': '# 검토'}


def test_CLI_는_사용자_프로젝트_설정과_훅_없이_내장_도구_셋만_쓴다(tmp_path, monkeypatch):
    monkeypatch.delenv('HYD_CLI_SANDBOX', raising=False)
    args = cli_sandbox.cli_args(tmp_path, [])
    assert args[:2] == ['--setting-sources', ''] and json.loads(args[3]) == {'disableAllHooks': True}
    assert args[args.index('--tools') + 1] == 'Read,Write,Edit'


def test_승인_스킬은_묶음으로_주고_Skill_도구를_더한다(tmp_path, monkeypatch):
    monkeypatch.delenv('HYD_CLI_SANDBOX', raising=False)
    args = cli_sandbox.cli_args(tmp_path, [SKILL])
    plugin = args[args.index('--plugin-dir') + 1]
    assert args[args.index('--tools') + 1] == 'Read,Write,Edit,Skill'
    assert (tmp_path / plugin.split('/')[-1].split('\\')[-1] / 'skills' / 'my-review' / 'SKILL.md').is_file()


@pytest.mark.parametrize('name', ['..', 'a/b', 'a\\b', ''], ids=['위로', '슬래시', '역슬래시', '빈 이름'])
def test_작업_폴더_밖을_가리키는_스킬_이름은_거절한다(tmp_path, name, monkeypatch):
    monkeypatch.delenv('HYD_CLI_SANDBOX', raising=False)
    with pytest.raises(RuntimeError):
        cli_sandbox.cli_args(tmp_path, [dict(SKILL, skill_name=name)])


def test_격리를_끈_개발용_호스트_워커는_확인할_것이_없다(monkeypatch):
    monkeypatch.delenv('HYD_CLI_SANDBOX', raising=False)
    assert cli_sandbox.verify() is None


@pytest.mark.skipif(sys.platform == 'linux', reason='Linux 에서는 setpriv 가 있으면 실제 격리를 시도한다')
def test_격리를_켰는데_Linux_root_setpriv_가_없으면_켜지지_않고_까닭을_말한다(monkeypatch):
    """G1-25: 이미지 빌드 때 옵션만 확인해 지원하지 않는 커널에서는 상태 점이 초록인데 모든 AI 단계가 일반 실패했다 — 켜질 때 잰다."""
    monkeypatch.setenv('HYD_CLI_SANDBOX', 'landlock')
    with pytest.raises(RuntimeError) as e:
        cli_sandbox.verify()
    assert 'Linux root · setpriv' in str(e.value)
