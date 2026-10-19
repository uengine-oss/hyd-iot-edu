# 학생 PC에 실습 프로그램 8개를 설치한다(없는 것만). 저장소 루트의 설치.bat을 더블클릭하면 관리자 권한으로 이 파일을 실행한다.
#   목록과 버전은 학교 설치 목록(실습 스택 정보 xlsx, 확인일 2026-10-12)을 따른다:
#   Docker Desktop 4.87.0 · WSL 2 · VS Code 1.140.0(System) · Python 3.14.7 · Node.js 22.16.0 · Git · Arduino IDE 2.3.10 · XG5000 4.73
#   (+ supabase CLI: 목록 밖. 업무 DB를 켜는 데 쓰고, 없어도 시작.bat이 npx로 대신 받는다)
# 설치는 winget(Windows 기본 설치 도구)으로 한다. 패키지 ID와 위 버전이 microsoft/winget-pkgs에 있음을 확인했다(2026-10-19).
# XG5000(LS ELECTRIC)은 winget에 없어 내려받을 페이지를 열어 준다.
# 이미 있는 것은 건드리지 않는다. 끝에 결과 표를 보이고, 다시 시작이 필요하면 그렇게 말한다.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Say($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Stop-WithPause($text) { Say "`n[멈춤] $text" 'Red'; Read-Host '창을 닫으려면 Enter'; exit 1 }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Stop-WithPause '관리자 권한이 아닙니다. 설치.bat을 더블클릭해 실행하고, 권한을 묻는 창에서 「예」를 누르세요.' }
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Stop-WithPause 'winget이 없습니다. Microsoft Store에서 「앱 설치 관리자(App Installer)」를 설치하거나 업데이트한 뒤 다시 실행하세요.'
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Version-Of($exe, $arguments) {
    # 명령이 있으면 첫 줄을, 없으면 $null을 돌려준다
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $null }
    $ErrorActionPreference = 'Continue'   # PowerShell 5.1은 Stop일 때 외부 명령의 stderr 한 줄도 오류로 바꾼다
    $all = @(& $exe @arguments 2>&1)          # 다 받은 뒤 고른다(Select-Object -First가 파이프를 끊으면 종료 코드가 비어 버린다)
    if ($LASTEXITCODE -ne 0) { return $null }
    $out = $all | Where-Object { "$_".Trim() -replace '\x00', '' } | Select-Object -First 1
    if (-not $out) { return $null }
    return ($out.ToString() -replace '\x00', '').Trim()
}
function Install-Winget($id, $version, $extra = @()) {
    Say "  winget install $id $version" 'Cyan'
    if ($version) { $extra = @('--version', $version) + $extra }
    $ErrorActionPreference = 'Continue'
    & winget install -e --id $id --accept-package-agreements --accept-source-agreements --silent @extra
    # 0 = 설치함, -1978335189 = 이미 최신판이 있음
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { throw "winget install $id 실패(종료 코드 $LASTEXITCODE)" }
    Refresh-Path
}

$results = [System.Collections.Generic.List[object]]::new()
$restart = $false
function Record($name, $state, $note) { $results.Add([pscustomobject]@{ 프로그램 = $name; 결과 = $state; 비고 = $note }) }
function Installed-App($pattern) {
    # 「앱 및 기능」 목록에서 이름이 맞는 첫 프로그램의 판을 돌려준다(없으면 $null)
    $keys = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    $app = Get-ItemProperty $keys -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like $pattern } | Select-Object -First 1
    if ($app) { return "$($app.DisplayName) $($app.DisplayVersion)".Trim() } else { return $null }
}

Say "`n== 실습 프로그램 설치 (없는 것만 설치합니다. 처음이면 20~40분 걸릴 수 있습니다)" 'White'

# 0. BIOS 가상화 — 꺼져 있으면 WSL2 · Docker가 돌지 않는다(작업 관리자 → 성능 → CPU 「가상화」와 같은 값)
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
if ($cs.HypervisorPresent -or $cpu.VirtualizationFirmwareEnabled) { Record '가상화(BIOS)' '켜짐' '' }
else { Record '가상화(BIOS)' '꺼짐' 'BIOS에서 Intel VT-x / AMD SVM을 켜야 Docker가 돈다' }

# 1. WSL2 — Docker Desktop이 Linux 컨테이너를 돌리는 바탕
Say "`n[1/8] WSL2"
$wsl = Version-Of 'wsl.exe' @('--version')   # wsl은 UTF-16으로 출력한다(Version-Of가 NUL을 지운다)
if ($wsl) { Record 'WSL2' '있음' $wsl }
else {
    $ErrorActionPreference = 'Continue'
    & wsl.exe --install --no-distribution
    if ($LASTEXITCODE -eq 0) { $restart = $true; Record 'WSL2' '설치함' 'PC를 다시 시작해야 켜집니다' }
    else { Record 'WSL2' '실패' "wsl --install --no-distribution 종료 코드 $LASTEXITCODE — Windows 업데이트 뒤 다시" }
    $ErrorActionPreference = 'Stop'
}

# 2. Docker Desktop
Say "`n[2/8] Docker Desktop"
$dockerExe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
if (Test-Path $dockerExe) { Record 'Docker Desktop' '있음' (Version-Of 'docker' @('--version')) }
else {
    try { Install-Winget 'Docker.DockerDesktop' '4.87.0'; $restart = $true; Record 'Docker Desktop' '설치함' '다시 시작한 뒤 한 번 열어 약관에 동의' }
    catch { Record 'Docker Desktop' '실패' $_.Exception.Message }
}
# 학생 계정을 docker-users 그룹에 넣는다(학교 목록). 관리자 승인 계정이 아니라 지금 로그인한 계정이다.
$who = $cs.UserName
if ($who -and (Get-LocalGroup -Name 'docker-users' -ErrorAction SilentlyContinue)) {
    $member = $null
    try { $member = Get-LocalGroupMember -Group 'docker-users' -ErrorAction Stop | Where-Object { $_.Name -eq $who } } catch { $member = $null }
    if ($member) { Record 'docker-users 그룹' '있음' $who }
    else {
        try { Add-LocalGroupMember -Group 'docker-users' -Member $who; $restart = $true; Record 'docker-users 그룹' '추가함' "$who — 다시 로그인하면 적용" }
        catch { Record 'docker-users 그룹' '실패' "$who : $($_.Exception.Message)" }
    }
}

# 3. Git (시작.bat이 Git의 bash로 스크립트를 돌린다)
Say "`n[3/8] Git"
$v = Version-Of 'git' @('--version')
if ($v) { Record 'Git' '있음' $v }
else { try { Install-Winget 'Git.Git' $null; Record 'Git' '설치함' (Version-Of 'git' @('--version')) } catch { Record 'Git' '실패' $_.Exception.Message } }

# 4. Python 3.14 (5회차 실습의 python llm_client.py)
Say "`n[4/8] Python 3.14"
$v = Version-Of 'py' @('-3.14', '--version')
if (-not $v -or $v -notmatch '3\.14') { $v = Version-Of 'python' @('--version'); if ($v -notmatch '3\.14') { $v = $null } }
if ($v) { Record 'Python 3.14' '있음' $v }
else { try { Install-Winget 'Python.Python.3.14' '3.14.7' @('--scope', 'machine'); Record 'Python 3.14' '설치함' (Version-Of 'py' @('-3.14', '--version')) } catch { Record 'Python 3.14' '실패' $_.Exception.Message } }

# 5. Node 22 + supabase CLI (업무 DB를 켠다. CLI가 없어도 시작.bat이 npx로 대신 받는다)
Say "`n[5/8] Node 22 + supabase CLI"
$v = Version-Of 'node' @('--version')
if ($v -and $v -notmatch '^v22\.') { Record 'Node' '다른 판' "$v — 그대로 둡니다(시작.bat은 npx만 씁니다)" }
elseif ($v) { Record 'Node 22' '있음' $v }
else { try { Install-Winget 'OpenJS.NodeJS.22' '22.16.0'; Record 'Node 22' '설치함' (Version-Of 'node' @('--version')) } catch { Record 'Node 22' '실패' $_.Exception.Message } }
$v = Version-Of 'supabase' @('--version')
if ($v) { Record 'supabase CLI' '있음' $v }
elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    $ErrorActionPreference = 'Continue'
    & npm install -g supabase@2.119.0
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -eq 0) { Refresh-Path; Record 'supabase CLI' '설치함' (Version-Of 'supabase' @('--version')) }
    else { Record 'supabase CLI' '건너뜀' 'npm 설치 실패. 시작.bat이 npx로 대신 받으니 그대로 써도 됩니다' }
}
else { Record 'supabase CLI' '건너뜀' 'npm이 없습니다(Node 설치 확인)' }

# 6. VS Code (GitHub Copilot 채팅은 VS Code 안에서 로그인)
Say "`n[6/8] VS Code"
$codeExe = @((Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\Code.exe'), (Join-Path $env:ProgramFiles 'Microsoft VS Code\Code.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($codeExe -or (Get-Command code -ErrorAction SilentlyContinue)) { Record 'VS Code' '있음' '' }
else { try { Install-Winget 'Microsoft.VisualStudioCode' '1.140.0' @('--scope', 'machine'); Record 'VS Code' '설치함' '' } catch { Record 'VS Code' '실패' $_.Exception.Message } }

# 7. Arduino IDE
Say "`n[7/8] Arduino IDE"
$v = Installed-App 'Arduino IDE*'
if ($v) { Record 'Arduino IDE' '있음' $v }
else { try { Install-Winget 'ArduinoSA.IDE.stable' '2.3.10' @('--scope', 'machine'); Record 'Arduino IDE' '설치함' (Installed-App 'Arduino IDE*') } catch { Record 'Arduino IDE' '실패' $_.Exception.Message } }

# 8. XG5000 (LS ELECTRIC PLC 편집기) — winget에 없다. 내려받을 페이지를 열어 준다
Say "`n[8/8] XG5000"
$v = Installed-App '*XG5000*'
if ($v) { Record 'XG5000' '있음' $v }
else {
    Start-Process 'https://ssq.ls-electric.com/kr/ko/product/document/2201'
    Record 'XG5000' '직접 설치' '열린 페이지에서 버전 4.73을 골라 내려받아 설치한 뒤 설치.bat을 다시 실행'
}

# 메모리: Docker Desktop은 실습 스택에 4 GB 이상이 필요하다(WSL2는 PC 메모리의 절반을 쓴다)
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($ramGb -lt 8) { Record 'PC 메모리' '부족할 수 있음' "$ramGb GB — 8 GB 이상을 권장합니다" } else { Record 'PC 메모리' '충분' "$ramGb GB" }

Say "`n== 결과" 'White'
$results | Format-Table -AutoSize -Wrap | Out-String -Width 160 | Write-Host
$failed = @($results | Where-Object { $_.결과 -in @('실패', '꺼짐', '직접 설치') })
if ($failed.Count) { Say "손이 필요한 항목이 $($failed.Count)개 있습니다(실패 · 꺼짐 · 직접 설치). 위 비고대로 한 뒤 설치.bat을 다시 실행하세요." 'Red' }
if ($restart) { Say "PC를 다시 시작하세요. 다시 시작한 뒤 Docker Desktop을 한 번 열어 약관에 동의하고, 그다음 시작.bat을 더블클릭합니다." 'Yellow' }
elseif (-not $failed.Count) { Say "모두 준비됐습니다. 시작.bat을 더블클릭하세요." 'Green' }
Read-Host '창을 닫으려면 Enter'
