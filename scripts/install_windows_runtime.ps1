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
        if ((Get-InstallAction $found $Versions.PYTHON_MIN) -eq 'keep') {
            Record 'Python' '있음' "$found — 기준 $($Versions.PYTHON_MIN) 이상, 유지"; return
        }
        $line = ($Versions.PYTHON_NEW -split '\.')[0..1] -join '.'
        # Older major/minor Python is a different winget package; install side by side.
        $target = Installed-App "Python $line*"
        $action = Get-InstallAction $target $Versions.PYTHON_NEW
        if ($action -eq 'keep') { throw "Python $line 설치 기록은 있으나 실행할 수 없습니다. 기존 설치 복구가 필요합니다." }
        Install-Winget "Python.Python.$line" $action @('--scope', 'machine')
        $after = Get-PythonVersion
        if ((Get-InstallAction $after $Versions.PYTHON_MIN) -ne 'keep') { throw "Python 설치 후 기준 미충족: $after" }
        Record 'Python' '설치/업데이트함' "$after — 기존 Python/Anaconda는 삭제하지 않음"
    } catch { Record 'Python' '실패' $_.Exception.Message }
}

# WSL 판은 「앱 및 기능」의 「Windows Subsystem for Linux」 항목에서 읽는다. wsl.exe --version은 WSL이 없는 PC에서
# 「아무 키나 누르면 설치」를 묻고 기다려 설치 창이 멈춘 것처럼 보였다(2026-11-06 학생 PC). 이름은 정확히 맞춘다 —
# 옛 커널 패키지 「Windows Subsystem for Linux Update」(5.10.x)를 WSL 판으로 읽지 않게.
function Get-WslVersion { Installed-App 'Windows Subsystem for Linux' }

function Ensure-WSL {
    try {
        foreach ($feature in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
            $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
            if ($state -eq 'EnablePending') { $script:restart = $true; continue }
            if ($state -ne 'Enabled') {
                # 재시작은 끝 안내로 한 번에 알린다(-NoRestart가 띄우는 경고는 숨긴다). WSL 설치는 재시작 전에도 된다(2026-11-06 학생 PC)
                Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart -WarningAction SilentlyContinue | Out-Null
                $script:restart = $true
                Record $feature '재부팅 필요' '기능을 켰습니다. PC를 다시 시작하면 적용됩니다'
            }
        }
        $found = Get-WslVersion
        $action = Get-InstallAction $found $Versions.WSL_MIN
        if ($action -eq 'keep') { Record 'WSL' '있음' "$found — 기준 $($Versions.WSL_MIN) 이상, 유지"; return }
        Say "  현재: $found / 최소 기준: $($Versions.WSL_MIN) / 작업: $action (내려받는 동안 몇 분간 화면이 조용할 수 있습니다)"
        $ErrorActionPreference = 'Continue'
        # --web-download: Microsoft Store 가 아니라 GitHub 에서 받는다 — 인증서를 가로채는 망(학교)에서 Store 원본이 막힌다(winget msstore 와 같은 까닭, 2026-11-13)
        if ($action -eq 'install') { & wsl.exe --install --no-distribution --web-download }
        else { & wsl.exe --update --web-download }
        $code = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($code -in @(1641, 3010)) { $script:restart = $true }
        elseif ($code -ne 0) { throw "WSL $action 실패(종료 코드 $code)" }
        $after = Get-WslVersion
        if ((Get-InstallAction $after $Versions.WSL_MIN) -ne 'keep') { throw "WSL $action 뒤에도 기준 $($Versions.WSL_MIN) 미충족(확인값: $after)" }
        Record 'WSL' '설치/업데이트함' "$after — 기준 이상 확인"
    } catch { Record 'WSL' '실패' $_.Exception.Message }
}
