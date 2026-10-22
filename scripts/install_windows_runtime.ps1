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
        if ((Get-InstallAction $found '3.14.7') -eq 'keep') {
            Record 'Python' '있음' "$found — 기준 3.14.7 이상, 유지"; return
        }
        # Older major/minor Python is a different winget package; install side by side.
        $target = Installed-App 'Python 3.14*'
        $action = Get-InstallAction $target '3.14.7'
        if ($action -eq 'keep') { throw 'Python 3.14 설치 기록은 있으나 실행할 수 없습니다. 기존 설치 복구가 필요합니다.' }
        Install-Winget 'Python.Python.3.14' $action @('--scope', 'machine')
        $after = Get-PythonVersion
        if ((Get-InstallAction $after '3.14.7') -ne 'keep') { throw "Python 설치 후 기준 미충족: $after" }
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
        $action = Get-InstallAction $found '2.7.12.0'
        if ($action -eq 'keep') { Record 'WSL' '있음' "$found — 기준 2.7.12.0 이상, 유지"; return }
        $ErrorActionPreference = 'Continue'
        if ($action -eq 'install') { & wsl.exe --install --no-distribution }
        else { & wsl.exe --update }
        $code = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($code -eq 3010) { $script:restart = $true }
        elseif ($code -ne 0) { throw "WSL $action 실패(종료 코드 $code)" }
        $after = Version-Of 'wsl.exe' @('--version')
        if ((Get-InstallAction $after '2.7.12.0') -ne 'keep') {
            if ($script:restart) { Record 'WSL' '재부팅 후 재확인' '재부팅 후 설치.bat을 다시 실행하세요. 완료 판정 전입니다.'; return }
            throw "WSL 설치 후 기준 미충족: $after"
        }
        Record 'WSL' '설치/업데이트함' "$after — 기준 이상 확인"
    } catch { Record 'WSL' '실패' $_.Exception.Message }
}
