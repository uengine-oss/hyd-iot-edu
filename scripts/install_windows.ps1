# 학생 PC에 실습 프로그램 6개를 학교 설치 목록과 같은 판으로 설치한다(없는 것만). 저장소 루트의 설치.bat을 더블클릭하면 관리자 권한으로 이 파일을 실행한다.
#   학교 설치 목록(실습 스택 정보 xlsx, 확인일 2026-10-12)의 1~6번:
#   Docker Desktop 4.87.0 · WSL 2.7.12 · VS Code 1.140.0(System) · Python 3.14.7 · Node.js 22.16.0 · Git(버전 무관)
#   7번 Arduino IDE는 빼고, 8번 XG5000 4.73은 직접 설치한다(사용자 2026-10-19).
#   + supabase CLI: 목록 밖. 업무 DB를 켜는 데 쓰고, 없어도 시작.bat이 npx로 대신 받는다
# 설치는 winget(Windows 기본 설치 도구)으로 한다. 패키지 ID와 위 판이 microsoft/winget-pkgs에 있음을 확인했다(2026-10-19).
# 이미 있는 프로그램은 바꾸지 않고, 판이 목록과 다르면 결과 표에 「다른 판」으로 알린다.
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

function Check-Installed($name, $found, $want) {
    # 이미 있는 프로그램: 학교 목록의 판과 같으면 「있음」, 다르면 「다른 판」. 깔린 판은 바꾸지 않는다(낮은 판으로 되돌리면 깨지는 프로그램이 있다)
    if (-not $want -or $found -match [regex]::Escape($want)) { Record $name '있음' $found }
    else { Record $name '다른 판' "$found — 학교 목록은 $want. 맞추려면 그 프로그램을 지우고 설치.bat을 다시 실행" }
}

# 1. WSL 2 2.7.12 — Docker Desktop이 Linux 컨테이너를 돌리는 바탕. Windows 기능 두 개를 켜고 WSL 본체를 winget으로 설치한다
Say "`n[1/6] WSL 2"
$wsl = Version-Of 'wsl.exe' @('--version')   # wsl은 UTF-16으로 출력한다(Version-Of가 NUL을 지운다)
if ($wsl) { Check-Installed 'WSL 2' $wsl '2.7.12' }
else {
    $ErrorActionPreference = 'Continue'
    foreach ($feature in 'Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform') {
        & dism.exe /online /enable-feature /featurename:$feature /all /norestart | Out-Null
        if ($LASTEXITCODE -notin 0, 3010) { Record "Windows 기능 $feature" '실패' "dism 종료 코드 $LASTEXITCODE" }   # 3010 = 다시 시작하면 적용
    }
    $ErrorActionPreference = 'Stop'
    try { Install-Winget 'Microsoft.WSL' '2.7.12'; $restart = $true; Record 'WSL 2' '설치함' '2.7.12 — PC를 다시 시작해야 켜집니다' }
    catch { Record 'WSL 2' '실패' $_.Exception.Message }
}

# 2. Docker Desktop 4.87.0
Say "`n[2/6] Docker Desktop"
$dockerExe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
if (Test-Path $dockerExe) { Check-Installed 'Docker Desktop' (Installed-App 'Docker Desktop*') '4.87.0' }
else {
    try { Install-Winget 'Docker.DockerDesktop' '4.87.0'; $restart = $true; Record 'Docker Desktop' '설치함' '4.87.0 — 다시 시작한 뒤 한 번 열어 약관에 동의' }
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

# 3. Visual Studio Code 1.140.0 (System Installer = PC 전체 설치. GitHub Copilot 채팅은 VS Code 안에서 로그인)
Say "`n[3/6] Visual Studio Code"
$v = Installed-App 'Microsoft Visual Studio Code*'
if ($v) { Check-Installed 'VS Code' $v '1.140.0' }
else { try { Install-Winget 'Microsoft.VisualStudioCode' '1.140.0' @('--scope', 'machine'); Record 'VS Code' '설치함' '1.140.0' } catch { Record 'VS Code' '실패' $_.Exception.Message } }

# 4. Python 3.14.7 (PATH에 넣는다. 5회차 실습의 python llm_client.py)
Say "`n[4/6] Python"
$v = Version-Of 'py' @('-3.14', '--version')
if (-not $v -or $v -notmatch '3\.14') { $v = Version-Of 'python' @('--version'); if ($v -notmatch '3\.14') { $v = $null } }
if ($v) { Check-Installed 'Python' $v '3.14.7' }
else { try { Install-Winget 'Python.Python.3.14' '3.14.7' @('--scope', 'machine'); Record 'Python' '설치함' (Version-Of 'py' @('-3.14', '--version')) } catch { Record 'Python' '실패' $_.Exception.Message } }

# 5. Node.js 22.16.0 (+ supabase CLI: 목록 밖. 업무 DB를 켜는 데 쓰고, 없어도 시작.bat이 npx로 대신 받는다)
Say "`n[5/6] Node.js"
$v = Version-Of 'node' @('--version')
if ($v) { Check-Installed 'Node.js' $v '22.16.0' }
else { try { Install-Winget 'OpenJS.NodeJS.22' '22.16.0'; Record 'Node.js' '설치함' (Version-Of 'node' @('--version')) } catch { Record 'Node.js' '실패' $_.Exception.Message } }
$v = Version-Of 'supabase' @('--version')
if ($v) { Record 'supabase CLI' '있음' $v }
elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    $ErrorActionPreference = 'Continue'
    & npm install -g supabase@2.119.0
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -eq 0) { Refresh-Path; Record 'supabase CLI' '설치함' (Version-Of 'supabase' @('--version')) }
    else { Record 'supabase CLI' '건너뜀' 'npm 설치 실패. 시작.bat이 npx로 대신 받으니 그대로 써도 됩니다' }
}
else { Record 'supabase CLI' '건너뜀' 'npm이 없습니다(Node.js 설치 확인)' }

# 6. Git (버전 무관 — winget의 최신판. 시작.bat이 Git의 bash로 스크립트를 돌린다)
Say "`n[6/6] Git"
$v = Version-Of 'git' @('--version')
if ($v) { Record 'Git' '있음' $v }
else { try { Install-Winget 'Git.Git' $null; Record 'Git' '설치함' (Version-Of 'git' @('--version')) } catch { Record 'Git' '실패' $_.Exception.Message } }

# 메모리: Docker Desktop은 실습 스택에 4 GB 이상이 필요하다(WSL2는 PC 메모리의 절반을 쓴다)
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($ramGb -lt 8) { Record 'PC 메모리' '부족할 수 있음' "$ramGb GB — 8 GB 이상을 권장합니다" } else { Record 'PC 메모리' '충분' "$ramGb GB" }

Say "`n== 결과" 'White'
$results | Format-Table -AutoSize -Wrap | Out-String -Width 160 | Write-Host
$failed = @($results | Where-Object { $_.결과 -in @('실패', '꺼짐', '다른 판') })
if ($failed.Count) { Say "손이 필요한 항목이 $($failed.Count)개 있습니다(실패 · 꺼짐 · 다른 판). 위 비고대로 한 뒤 설치.bat을 다시 실행하세요." 'Red' }
if ($restart) { Say "PC를 다시 시작하세요. 다시 시작한 뒤 Docker Desktop을 한 번 열어 약관에 동의하고, 그다음 시작.bat을 더블클릭합니다." 'Yellow' }
elseif (-not $failed.Count) { Say "모두 준비됐습니다. 시작.bat을 더블클릭하세요." 'Green' }
Read-Host '창을 닫으려면 Enter'
