# 학생 PC에 실습 필수 프로그램이 기준 판보다 낮거나 없으면 설치·업데이트한다. setup 폴더의 설치.bat을 더블클릭하면 관리자 권한으로 이 파일을 실행한다.
#   기준 판은 scripts\versions.txt 하나(Docker Desktop · VS Code · Node.js · Git · Python · WSL · Supabase CLI — Mac 설치 · 시작도 같은 파일을 읽는다).
#   Arduino IDE는 빼고, XG5000 4.73은 직접 설치한다(사용자 2026-10-19). Supabase CLI는 npx로 받아 둔다(시작.bat도 npx로 쓴다).
# Python · WSL과 필요한 Windows 기능을 포함한다.
# 설치는 winget(Windows 기본 설치 도구)으로 한다.
# 기준과 같거나 높으면 유지, 낮거나 없으면 설치/업데이트 후 버전을 재확인한다.
# 버전을 확인할 수 없으면 실패로 표시한다. 끝에 결과와 재시작 필요 여부를 보인다.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
. (Join-Path $PSScriptRoot 'install_version_policy.ps1')
. (Join-Path $PSScriptRoot 'install_windows_winget.ps1')
$V = Get-InstallVersions

function Say($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Stop-WithPause($text) { Say "`n[멈춤] $text" 'Red'; Read-Host '창을 닫으려면 Enter'; exit 1 }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Stop-WithPause '관리자 권한이 아닙니다. 설치.bat을 더블클릭해 실행하고, 권한을 묻는 창에서 「예」를 누르세요.' }

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
Refresh-Path
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
function Install-Winget($id, $action, $extra = @()) {
    # Only require winget when a tool actually needs installation or upgrade.
    # Invoke the resolved executable directly so elevation/PATH refresh cannot lose it.
    $wingetExecutable = Resolve-WingetExecutable
    Say "  winget $action --id $id" 'Cyan'
    $ErrorActionPreference = 'Continue'
    & $wingetExecutable $action -e --id $id --accept-package-agreements --accept-source-agreements --silent @extra
    if ($action -eq 'upgrade' -and $LASTEXITCODE -eq -1978335212) {
        # 0x8A150014: winget 이 기존 설치를 자기 패키지로 알아보지 못해 업그레이드 대상이 없다(공식 설치 파일로 깐 Node 등, 2026-10-29 학교 PC).
        # 같은 패키지를 새로 설치하면 기존 설치 위에 기준 판이 올라간다 — 결과는 아래 확인(Ensure-Minimum)이 다시 판정한다
        Say "  winget 이 기존 $id 를 업그레이드 대상으로 찾지 못해 install 로 다시 실행합니다" 'Yellow'
        & $wingetExecutable install -e --id $id --accept-package-agreements --accept-source-agreements --silent @extra
    }
    if ($LASTEXITCODE -in @(1641, 3010)) { $script:restart = $true }
    elseif ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { throw "winget $action $id 실패(종료 코드 $LASTEXITCODE)" }
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

Say "`n== 실습 프로그램 설치 (없거나 기준보다 낮으면 설치/업데이트, 같거나 높으면 유지)" 'White'

# 0. BIOS 가상화 — 꺼져 있으면 WSL2 · Docker가 돌지 않는다(작업 관리자 → 성능 → CPU 「가상화」와 같은 값)
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
if (-not ($cs.HypervisorPresent -or $cpu.VirtualizationFirmwareEnabled)) {   # 대부분의 PC는 켜져 있다. 꺼졌을 때만 알린다
    Record '가상화(BIOS)' '꺼짐' 'WSL · Docker가 돌지 않으면 BIOS에서 Intel VT-x / AMD SVM을 켠다'
}

function Ensure-Minimum($name, $id, $minimum, [scriptblock]$probe, $installExtra = @()) {
    try {
        $found = & $probe
        $action = Get-InstallAction $found $minimum
        if ($action -eq 'keep') {
            Record $name '있음' "$found — 기준 $minimum 이상, 유지"
            return
        }
        Say "  현재: $found / 최소 기준: $minimum / 작업: $action"
        $extra = @()
        if ($action -eq 'install') { $extra = $installExtra }
        Install-Winget $id $action $extra
        $after = & $probe
        if ((Get-InstallAction $after $minimum) -ne 'keep') {
            throw "설치 후 기준 $minimum 미충족(확인값: $after). 창을 새로 열고 버전과 winget 결과를 확인하세요."
        }
        $state = '설치함'
        if ($action -eq 'upgrade') { $state = '업데이트함' }
        Record $name $state "$after — 기준 $minimum 이상 확인"
        if ($name -eq 'Docker Desktop') { $script:restart = $true }
    }
    catch { Record $name '실패' $_.Exception.Message }
}

. (Join-Path $PSScriptRoot 'install_windows_runtime.ps1')
Say "`n[준비] WSL 및 Windows 기능"
Ensure-WSL
Say "`n[준비] Python"
Ensure-Python

# 1. Docker Desktop
Say "`n[1/4] Docker Desktop"
function Get-DockerVersion {
$dockerExe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
foreach ($candidate in @($dockerExe, (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'), (Join-Path $env:LOCALAPPDATA 'Docker\Docker Desktop.exe'))) {
    if (Test-Path -LiteralPath $candidate) { $dockerExe = $candidate; break }
}
$dockerVersion = Installed-App 'Docker Desktop*'
if ($dockerVersion -or (Test-Path $dockerExe)) {
    if (-not $dockerVersion) { $dockerVersion = 'Docker Desktop ' + (Get-Item -LiteralPath $dockerExe).VersionInfo.ProductVersion }
    return $dockerVersion
}
return $null
}
Ensure-Minimum 'Docker Desktop' 'Docker.DockerDesktop' $V.DOCKER_DESKTOP_MIN { Get-DockerVersion }
# docker-users 그룹: 지금 로그인한 계정과 「Authenticated Users」(로그인한 모든 계정)를 넣는다.
# 학교는 이 PC를 다른 PC로 복제하고 학생은 다른 계정으로 로그인할 수 있어서, 계정 하나만 넣으면 복제된 PC에서 Docker가 막힌다.
if (Get-LocalGroup -Name 'docker-users' -ErrorAction SilentlyContinue) {
    $members = @()
    try { $members = @(Get-LocalGroupMember -Group 'docker-users' -ErrorAction Stop | ForEach-Object { $_.SID.Value }) } catch { $members = @() }
    $wanted = @(@{ Name = '로그인한 모든 계정(Authenticated Users)'; Sid = 'S-1-5-11' })
    if ($cs.UserName) {
        try { $wanted += @{ Name = $cs.UserName; Sid = (New-Object System.Security.Principal.NTAccount($cs.UserName)).Translate([System.Security.Principal.SecurityIdentifier]).Value } } catch { }
    }
    foreach ($w in $wanted) {
        if ($members -contains $w.Sid) { Record 'docker-users 그룹' '있음' $w.Name; continue }
        try { Add-LocalGroupMember -Group 'docker-users' -Member $w.Sid; $restart = $true; Record 'docker-users 그룹' '추가함' "$($w.Name) — 다시 로그인하면 적용" }
        catch { Record 'docker-users 그룹' '실패' "$($w.Name): $($_.Exception.Message)" }
    }
}

# 2. VS Code: 기준 판(2026년 8월 판) 이상이면 그대로 둔다(사용자 2026-10-29). 낮거나 없을 때만 설치 · 업데이트
#    신규는 PC 전체 설치, 업데이트는 기존 설치 범위 유지
Say "`n[2/4] Visual Studio Code"
Ensure-Minimum 'VS Code' 'Microsoft.VisualStudioCode' $V.VSCODE_MIN {
$v = Installed-App 'Microsoft Visual Studio Code*'
if (-not $v) { $v = Version-Of 'code' @('--version') }
return $v
} @('--scope', 'machine')

# 3. Node.js (+ supabase CLI: 없어도 시작.bat이 npx로 대신 받는다)
Say "`n[3/4] Node.js"
Ensure-Minimum 'Node.js' 'OpenJS.NodeJS' $V.NODE_MIN {
$v = Version-Of 'node' @('--version')
if (-not $v) { $v = Installed-App 'Node.js*' }
return $v
}
# Supabase uses the supported npx distribution, not npm global install.
try {
    $v = Version-Of 'npx.cmd' @('-y', "supabase@$($V.SUPABASE_CLI)", '--version')
    if ((Get-InstallAction $v $V.SUPABASE_CLI) -ne 'keep') { throw 'Supabase CLI 준비 실패: Node.js와 네트워크를 확인하세요.' }
    Record 'supabase CLI' '준비함' "$v — npx 실행 준비 완료"
} catch { Record 'supabase CLI' '실패' $_.Exception.Message }

# 4. Git (시작.bat이 Git Bash로 스크립트를 돌린다)
Say "`n[4/4] Git"
Ensure-Minimum 'Git' 'Git.Git' $V.GIT_MIN {
$v = Version-Of 'git' @('--version')
if (-not $v) { $v = Installed-App 'Git version *' }
return $v
}

# 저장소 폴더: 복제된 PC의 다른 계정도 쓰게 한다. 사용자 폴더(C:\Users\…) 안이면 개인 PC로 보고 그대로 둔다(여러 계정이 쓸 PC면 공용 폴더에 받으라는 안내만 — 실패가 아니다).
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$usersRoot = Join-Path $env:SystemDrive 'Users'
if ($repo.StartsWith($usersRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Record '저장소 위치' '개인 폴더' "$repo — 이 계정만 씁니다. 여러 계정이 함께 쓸(복제할) PC라면 C:\hyd-iot-edu 같은 공용 폴더에 받으세요"
}
else {
    $ErrorActionPreference = 'Continue'
    & icacls.exe $repo /grant '*S-1-5-11:(OI)(CI)M' /T /C /Q | Out-Null        # 로그인한 모든 계정에 수정 권한
    $acl = $LASTEXITCODE
    if (Get-Command git -ErrorAction SilentlyContinue) {                       # 다른 계정의 git pull이 「dubious ownership」으로 막히지 않게
        $safe = $repo -replace '\\', '/'
        $known = @(& git config --system --get-all safe.directory 2>$null)
        if ($known -notcontains $safe) { & git config --system --add safe.directory $safe }
    }
    $ErrorActionPreference = 'Stop'
    if ($acl -eq 0) { Record '저장소 위치' '공용' "$repo — 모든 계정 쓰기 · git 신뢰 폴더 등록" }
    else { Record '저장소 위치' '실패' "icacls 종료 코드 $acl" }
}

# 메모리: Docker Desktop은 실습 스택에 4 GB 이상이 필요하다(WSL2는 PC 메모리의 절반을 쓴다)
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($ramGb -lt 8) { Record 'PC 메모리' '부족할 수 있음' "$ramGb GB — 8 GB 이상을 권장합니다" } else { Record 'PC 메모리' '충분' "$ramGb GB" }

Say "`n== 결과" 'White'
$results | Format-Table -AutoSize -Wrap | Out-String -Width 160 | Write-Host
$failed = @($results | Where-Object { $_.결과 -in @('실패', '꺼짐') })
if ($failed.Count) { Say "손이 필요한 항목이 $($failed.Count)개 있습니다(실패 · 꺼짐). 위 비고대로 한 뒤 설치.bat을 다시 실행하세요." 'Red' }
if ($restart) { Say "PC를 다시 시작하세요. 다시 시작한 뒤 Docker Desktop을 한 번 열어 약관에 동의하고, 그다음 시작.bat을 더블클릭합니다." 'Yellow' }
elseif (-not $failed.Count) { Say "설치 대상 확인이 끝났습니다. Docker Linux 엔진 실행과 실습용 접속 설정을 확인한 뒤 시작.bat을 실행하세요." 'Green' }
Read-Host '창을 닫으려면 Enter'
if ($failed.Count) { exit 1 }
if ($restart) { exit 3010 }
