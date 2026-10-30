# Loaded by install_windows.ps1 after the shared probe/install functions.
function Get-PythonVersion {
    $candidates = @('python.exe', 'python3.exe')
    foreach ($base in @("$env:LOCALAPPDATA\Programs\Python", $env:ProgramFiles)) {
        $candidates += @(Get-ChildItem -Path "$base\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    }
    $versions = @()
    foreach ($exe in ($candidates | Select-Object -Unique)) {
        # Skip Windows Store aliases which can open the Store instead of Python.
        $cmd = Get-Command $exe -ErrorAction SilentlyContinue
        if (-not $cmd -or $cmd.Source -like '*\WindowsApps\*') { continue }
        $v = Version-Of $exe @('--version')
        if (ConvertTo-InstallVersion $v) { $versions += $v }
    }
    $v = Version-Of 'py.exe' @('-3', '--version')
    if (ConvertTo-InstallVersion $v) { $versions += $v }
    return $versions | Sort-Object { ConvertTo-InstallVersion $_ } -Descending | Select-Object -First 1
}

function Ensure-Python {
    try {
        $found = Get-PythonVersion
        # 기준(PYTHON_MIN) 이상이면 학교 PC의 Python을 그대로 쓰고(사용자 2026-10-29), 없거나 낮을 때만 PYTHON_NEW 판을 옆에 설치한다
        if ((Get-InstallAction $found $V.PYTHON_MIN) -eq 'keep') {
            Record 'Python' '있음' "$found — 기준 $($V.PYTHON_MIN) 이상, 유지"; return
        }
        $line = ($V.PYTHON_NEW -split '\.')[0..1] -join '.'
        # Older major/minor Python is a different winget package; install side by side.
        $target = Installed-App "Python $line*"
        $action = Get-InstallAction $target $V.PYTHON_NEW
        if ($action -eq 'keep') { throw "Python $line 설치 기록은 있으나 실행할 수 없습니다. 기존 설치 복구가 필요합니다." }
        Install-Winget "Python.Python.$line" $action @('--scope', 'machine')
        $after = Get-PythonVersion
        if ((Get-InstallAction $after $V.PYTHON_MIN) -ne 'keep') { throw "Python 설치 후 기준 미충족: $after" }
        Record 'Python' '설치/업데이트함' "$after — 기존 Python/Anaconda는 삭제하지 않음"
    } catch { Record 'Python' '실패' $_.Exception.Message }
}

function Ensure-WSL {
    try {
        foreach ($feature in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
            $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
            if ($state -eq 'EnablePending') { $script:restart = $true; continue }
            if ($state -ne 'Enabled') {
                Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart | Out-Null
                $script:restart = $true
                Record $feature '재부팅 필요' '기능 활성화 요청 완료'
            }
        }
        $found = Version-Of 'wsl.exe' @('--version')
        $action = Get-InstallAction $found $V.WSL_MIN
        if ($action -eq 'keep') { Record 'WSL' '있음' "WSL $(ConvertTo-InstallVersion $found) — 기준 $($V.WSL_MIN) 이상, 유지"; return }
        $ErrorActionPreference = 'Continue'
        if ($action -eq 'install') { & wsl.exe --install --no-distribution }
        else { & wsl.exe --update }
        $code = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($code -eq 3010) { $script:restart = $true }
        elseif ($code -ne 0) { throw "WSL $action 실패(종료 코드 $code)" }
        $after = Version-Of 'wsl.exe' @('--version')
        if ((Get-InstallAction $after $V.WSL_MIN) -ne 'keep') {
            if ($script:restart) { Record 'WSL' '재부팅 후 재확인' '재부팅 후 설치.bat을 다시 실행하세요. 완료 판정 전입니다.'; return }
            throw "WSL 설치 후 기준 미충족: $after"
        }
        Record 'WSL' '설치/업데이트함' "WSL $(ConvertTo-InstallVersion $after) — 기준 이상 확인"
    } catch { Record 'WSL' '실패' $_.Exception.Message }
}
