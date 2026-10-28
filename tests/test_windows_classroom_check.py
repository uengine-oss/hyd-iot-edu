"""Execute only BAT's relay-check section in PowerShell, without plant actions."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).parents[1]
POWERSHELL = shutil.which('powershell')
pytestmark = pytest.mark.skipif(not POWERSHELL, reason='Windows PowerShell contract')


@pytest.mark.parametrize('managed,fail', [(True, False), (True, True), (False, False)])
def test_bat_management_authentication_never_falls_back_to_direct_model(tmp_path, managed, fail):
    (tmp_path/'scripts').mkdir()
    shutil.copyfile(ROOT/'scripts/check_classroom.py', tmp_path/'scripts/check_classroom.py')
    (tmp_path/'.env').write_text(
        'LLM_API_KEY=fixture-class-key-xxxxxxxxxxxxxxxxxxxxxxxx\n' +
        ('HYD_CLASSROOM_URL=https://classroom.example\n' if managed else
         'OPENAI_BASE_URL=https://legacy.example/v1\nLLM_MODEL=coding\n'), encoding='utf8')
    # Even an explicit lab file cannot override the root managed destination.
    (tmp_path/'alternate.env').write_text('LLM_API_KEY=alternate-fixture-key\nOPENAI_BASE_URL=https://other.example/v1\nLLM_MODEL=coding\n', encoding='utf8')
    source = (ROOT/'scripts/check_windows.ps1').read_text(encoding='utf8')
    section = source.split('# 3. 5회차 실습 2: 중계 서버 연결', 1)[1].rsplit('Show-Results', 1)[0]
    script = r"""
param($root, $failCode)
$ErrorActionPreference='Stop'
$repo=$root; $LlmEnvFile=Join-Path $root 'alternate.env'; $SkipLlm=$false
$script:directCalls=0; $script:managedCalls=0; $script:received=''; $script:argv=@(); $script:results=@()
function Say($message) {}
function Record($step,$ok,$note) { $script:results += @{ok=$ok; note=$note} }
function docker {
    $script:managedCalls++; $script:received=(@($input) -join ''); $script:argv=@($args)
    $global:LASTEXITCODE=[int]$failCode
    'fixture authentication result'
}
function Invoke-RestMethod {
    $script:directCalls++
    return @{choices=@(@{message=@{content='OK'}})}
}
""" + section + r"""
@{direct=$script:directCalls;managed=$script:managedCalls;keyViaStdin=($script:received -like 'fixture-class-key-*');keyInArgv=(($script:argv -join ' ') -like '*fixture-class-key-*');results=$script:results} | ConvertTo-Json -Depth 6 -Compress
"""
    path = tmp_path/'check.ps1'
    path.write_text(script, encoding='utf-8-sig')
    result = subprocess.run([POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(path),
                             str(tmp_path), '1' if fail else '0'], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    value = json.loads(result.stdout.decode('utf8', errors='replace'))
    assert value['managed'] == int(managed)
    assert value['direct'] == int(not managed)
    assert not value['keyInArgv']
    if managed:
        assert value['keyViaStdin']
        assert value['results'][0]['ok'] is not fail


@pytest.mark.parametrize('mode', ['replay', 'live'])
def test_no_key_online_pc_in_replay_skips_the_relay_check_instead_of_failing(tmp_path, mode):
    # 2026-10-28: 키 없는 온라인 PC(워커 ai_mode = replay)는 중계를 부르지 않는다 — 점검이 「LLM_API_KEY 설정이 필요」로 실패하지 않는다
    (tmp_path/'.env').write_text('OPENAI_BASE_URL=https://relay.example/v1\nLLM_API_KEY=\nLLM_MODEL=coding\n', encoding='utf8')
    source = (ROOT/'scripts/check_windows.ps1').read_text(encoding='utf8')
    section = source.split('# 3. 5회차 실습 2: 중계 서버 연결', 1)[1].rsplit('Show-Results', 1)[0]
    script = r"""
param($root, $mode)
$ErrorActionPreference='Stop'
$repo=$root; $LlmEnvFile=''; $SkipLlm=$false; $worker=[pscustomobject]@{status='ok'; ai_mode=$mode}
$script:calls=0; $script:results=@()
function Say($message) {}
function Record($step,$ok,$note) { $script:results += @{ok=$ok; note=$note} }
function docker { $script:calls++ }
function Invoke-RestMethod { $script:calls++ }
""" + section + r"""
@{calls=$script:calls;results=$script:results} | ConvertTo-Json -Depth 6 -Compress
"""
    path = tmp_path/'check.ps1'
    path.write_text(script, encoding='utf-8-sig')
    result = subprocess.run([POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(path), str(tmp_path), mode],
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    value = json.loads(result.stdout.decode('utf8', errors='replace'))
    assert value['calls'] == 0
    [only] = value['results'] if isinstance(value['results'], list) else [value['results']]
    assert only['ok'] is (mode == 'replay')       # 키 있는 live PC에서 키가 비면 지금처럼 실패한다
