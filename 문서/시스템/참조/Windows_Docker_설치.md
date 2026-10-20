# Windows 11: Hyper-V 확인부터 Docker 실행까지

학교 PC에서 **관리자 Windows PowerShell**을 열고 순서대로 진행한다. Hyper-V로 Docker가 정상 실행되면 WSL 설치와 Windows Update 레지스트리 복구를 생략한다.

이 문서의 명령은 현장에서 사용자가 실행하는 안내다. 학교 PC에서의 복구 성공을 보증하는 검증 기록은 아니다.

## 0. 재부팅하면 초기화되는 PC부터 확인

강의실 관리자에게 재부팅 복원 기능 해제 또는 설치 완료 상태 저장을 요청한다. 복원 기능이 켜져 있으면 설치와 설정 변경이 재부팅 후 사라질 수 있다.

시작 메뉴에서 **Windows PowerShell 검색 → 관리자 권한으로 실행**. 창 제목에 `관리자`가 있는지 확인한다.

## 1. Hyper-V와 Docker 설치 형태 확인 — 조회만 수행

아래 블록 전체를 붙여 넣는다. 설치·서비스·권한을 변경하지 않는다.

```powershell
$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
$pc = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$features = @(Get-WindowsOptionalFeature -Online)

Write-Host "Windows: $($os.Caption) / Build $($os.BuildNumber)"
Write-Host "하이퍼바이저 실행 중: $($pc.HypervisorPresent)"
Write-Host "BIOS 가상화: $($cpu.VirtualizationFirmwareEnabled)"

$featureNames = @(
    'Microsoft-Hyper-V-All'
    'Microsoft-Hyper-V-Hypervisor'
    'Containers'
    'VirtualMachinePlatform'
    'Microsoft-Windows-Subsystem-Linux'
)
foreach ($name in $featureNames) {
    $feature = $features |
        Where-Object { $_.FeatureName -eq $name } |
        Select-Object -First 1
    if ($feature) { Write-Host "$name : $($feature.State)" }
    else { Write-Host "$name : 이 Windows에서 기능을 찾지 못함" }
}

$allUsersDocker = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
$perUserDocker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'
Write-Host "Docker 전체 사용자용 기본 경로: $(Test-Path -LiteralPath $allUsersDocker)"
Write-Host "Docker 사용자 전용 기본 경로: $(Test-Path -LiteralPath $perUserDocker)"
Get-Service -Name 'com.docker.service','LanmanServer' -ErrorAction SilentlyContinue |
    Format-Table Name,Status,StartType
```

| 조회 결과 | 다음 행동 |
|---|---|
| 지원되는 Pro·Education·Enterprise, Hyper-V와 Containers가 `Enabled`, 하이퍼바이저 `True`, Docker 전체 사용자용 설치 | **3번으로 바로 이동** |
| 지원 에디션이고 Hyper-V 또는 Containers가 `Disabled` | **2번**에서 활성화 |
| `EnabledPending` | 작업 저장 후 재부팅하고 1번 재확인 |
| Windows Home 또는 Hyper-V 기능 없음 | **5번 WSL 경로**로 이동 |
| Docker 사용자 전용 경로만 `True`, `com.docker.service` 없음 | Hyper-V 지원 설치 형태가 아니다. WSL 경로를 사용하거나 전체 사용자용 재설치를 별도 준비 |

`HypervisorPresent=True` 하나로 Hyper-V 백엔드를 쓸 수 있다고 판단하지 않는다. Home에서도 WSL·보안 기능 때문에 하이퍼바이저가 실행될 수 있다. 에디션·Hyper-V 기능·Docker 설치 형태를 함께 확인한다.

Docker 경로 검사는 **기본 설치 경로 기준**이다. 사용자 지정 경로에 설치한 PC는 경로의 True/False만으로 설치 유무를 확정하지 않는다.

하이퍼바이저가 실행되지 않고 BIOS 가상화도 False라면 **작업 관리자 → 성능 → CPU → 가상화**를 확인한다. 꺼져 있으면 BIOS/UEFI에서 가상화를 활성화해야 한다. 하이퍼바이저가 이미 실행 중일 때는 CPU 항목만으로 BIOS 가상화가 꺼졌다고 판단하지 않는다.

## 2. Hyper-V가 꺼져 있을 때만 활성화

**지원되는 Pro·Education·Enterprise이고 BIOS 가상화가 준비된 PC에서만** 실행한다. 이미 두 기능이 Enabled이면 생략한다. Home에서 Hyper-V를 강제 설치하는 우회 절차는 사용하지 않는다.

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V,Containers -All -NoRestart -ErrorAction Stop
```

성공하면 열어 둔 작업을 저장하고 복원 기능이 해제됐는지 확인한 후 재부팅한다. 오류가 나면 다음 명령으로 넘어가지 않는다.

```powershell
Restart-Computer
```

재부팅 후 1번을 다시 확인한다. Hyper-V가 Enabled인데 하이퍼바이저가 False라면 부팅 설정을 조회한다.

```powershell
bcdedit.exe /enum '{current}'
```

**`hypervisorlaunchtype Off`가 명시적으로 보일 때만** 다음을 실행하고 다시 재부팅한다. 항목이 없다는 이유만으로 Off로 판단하지 않는다.

```powershell
bcdedit.exe /set hypervisorlaunchtype auto
```

## 3. Docker 설정 전환

전체 사용자용 기본 경로에 설치되어 있을 때 Docker Desktop을 연다. 이미 열려 있으면 설정으로 이동한다.

```powershell
Start-Process -FilePath "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
```

1. **설정(톱니바퀴) → General**.
2. **Use the WSL 2 based engine** 체크 해제.
3. **Apply & Restart**. 관리자 승인 창은 사용자가 승인한다.
4. 엔진 시작 후 4번으로 이동.

체크 항목이 없거나 잠겨 있거나 전환 오류가 나면 에디션·Windows 기능·Docker 설치 형태를 다시 확인한다. 사용자 전용에서 전체 사용자용으로 바꾸려면 공식적으로 제거 후 재설치가 필요하다. 기존 데이터 삭제나 초기화를 해결책으로 바로 실행하지 않는다.

**Switch to Windows containers는 선택하지 않는다.** 이 프로젝트는 Hyper-V 방식에서도 Linux 컨테이너를 사용한다.

Docker 오류에서 Server 서비스를 지목하고 `LanmanServer`가 Disabled 또는 Stopped라면, 관리자가 허용한 PC에서만 아래를 한 줄씩 실행한다.

```powershell
Set-Service -Name LanmanServer -StartupType Automatic -ErrorAction Stop
Start-Service -Name LanmanServer -ErrorAction Stop
```

## 4. Docker 정상 실행 확인 → 성공하면 7번으로

새 PowerShell 창에서 실행한다.

```powershell
docker version
docker info --format '{{.OSType}}'
```

`docker`를 찾지 못하고 전체 사용자용 기본 경로에 설치했다면 직접 호출한다.

```powershell
& "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe" version
& "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe" info --format '{{.OSType}}'
```

**Client와 Server가 모두 나오고 `linux`가 출력되면 실습에 필요한 Docker Linux 엔진이 응답하는 것이다.** 이 출력만으로 백엔드 종류까지 증명되는 것은 아니다.

성공하면 **5·6번 WSL·레지스트리 절차를 생략하고 7번으로 이동**한다.

현재 `설치.bat`은 WSL 설치를 시도하므로 Hyper-V 경로에서 전체 설치.bat을 반복 실행하지 않는다. 나머지 도구가 준비됐다면 바로 시작·점검하고, 빠진 도구가 있으면 해당 도구만 준비한다.

## 5. Hyper-V를 사용할 수 없을 때만 WSL

먼저 조회한다.

```powershell
wsl.exe --version
wsl.exe --status
```

WSL이 준비됐고 Docker가 정상 실행된다면 재설치는 생략한다. 설치가 필요하면 **다른 설치가 끝난 상태**에서 관리자 PowerShell로 실행한다.

```powershell
wsl.exe --install --web-download --no-distribution
```

설치가 성공하면 안내에 따라 재부팅한다. Docker용으로 Ubuntu를 별도 설치할 필요는 없다. 재부팅 후 위 조회와 4번 Docker 실행 확인을 진행한다.

실패하면 같은 설치 명령을 반복하지 말고 서비스 상태를 확인한다.

```powershell
Get-Service -Name wuauserv,BITS,msiserver -ErrorAction SilentlyContinue |
    Format-Table Name,Status,StartType
```

`wuauserv`가 Disabled라면 아래를 **한 줄씩** 실행한다. 오류가 나면 다음 줄은 실행하지 않는다.

```powershell
Set-Service -Name wuauserv -StartupType Manual -ErrorAction Stop
Start-Service -Name wuauserv -ErrorAction Stop
Get-Service wuauserv | Format-Table Name,Status,StartType
```

BITS와 msiserver가 Manual/Stopped인 것만으로 장애라고 판단하지 않는다. 첫 줄에서 액세스 거부가 나오는 경우에만 6번 권한을 확인한다. 서비스가 정상인데 WSL이 실패하면 별도의 설치 오류를 확인해야 한다.

## 6. 액세스 거부일 때만 해당 키 권한 확인·복구

### 6-1. 조회와 백업

```powershell
$ErrorActionPreference = 'Stop'
$keyPath = 'HKLM:\SYSTEM\CurrentControlSet\Services\wuauserv'
$keyAcl = Get-Acl -LiteralPath $keyPath
$keyAcl | Format-List Owner
$keyAcl.Access |
    Format-Table IdentityReference,RegistryRights,AccessControlType

$backupDir = Join-Path $env:USERPROFILE ('wuauserv-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir | Out-Null
$keyAcl.Sddl | Set-Content (Join-Path $backupDir 'permissions-sddl.txt')
$keyAcl.Owner | Set-Content (Join-Path $backupDir 'original-owner.txt')
reg.exe export 'HKLM\SYSTEM\CurrentControlSet\Services\wuauserv' (Join-Path $backupDir 'wuauserv.reg') /y
if ($LASTEXITCODE -ne 0) { throw '레지스트리 값 백업 실패. 변경을 중단하세요.' }
Write-Host "백업 위치: $backupDir"
```

백업 오류가 나면 변경을 진행하지 않는다. `.reg`는 값의 백업이고 SDDL 파일이 권한 백업이다. `SYSTEM`과 `Administrators` 모두 `ReadKey`뿐인 상태가 학교 PC 사진에서 확인됐다. 이 경우 설정 변경이 거부될 근거가 있다. 이미 권한이 정상이면 아래 변경을 적용하지 않는다.

### 6-2. GUI에서 필요한 키만 수정

관리자 PowerShell에서 편집기를 연다.

```powershell
regedit.exe
```

주소창에 다음을 입력한다.

```text
HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\wuauserv
```

1. 왼쪽 **wuauserv 우클릭 → 사용 권한 → 고급**.
2. 권한 편집이 안 되고 소유자 변경이 필요하면, 기존 소유자를 기록한 뒤 **소유자 옆 변경 → Administrators 입력 → 이름 확인 → 확인 → 적용**. 이미 Administrators로 바꿨다면 반복하지 않는다.
3. 창을 닫고 사용 권한 → 고급으로 다시 들어간다.
4. **Administrators 선택 → 편집 → 유형: 허용 / 적용 대상: 이 키만 / 모든 권한 → 확인**.
5. **SYSTEM**에도 같은 설정. 대상이 없거나 상속 항목이라 편집이 안 되면 **추가 → 보안 주체 선택**에서 해당 대상을 선택해 `이 키만` 적용하는 허용 항목을 추가한다.
6. 두 항목 확인 후 **적용 → 확인**.

**소유자 변경만으로 작업이 끝나지 않는다. 수정 권한도 별도로 필요하다.** Everyone·Users와 상위 Services 전체 권한은 변경하지 않는다. 하위 개체 소유자 변경·모든 자식 개체 권한 교체는 체크하지 않는다. 거부 항목을 임의 삭제하거나 상속을 일괄 변경하지 않는다.

적용이 거부되거나 권한이 즉시 되돌아가면 오류를 기록하고 PC 관리자와 차단 프로그램·관리 정책 여부를 확인한다. 어떤 프로그램이 원인인지는 현재 확인되지 않았다.

복구 후 5번 서비스 명령을 다시 한 줄씩 실행한다. `Running / Manual`이 되면 WSL 설치를 재시도한다. 이 복구만으로 모든 WSL 설치 문제가 해결된다고 보장할 수는 없다.

## 7. 실습 시작·점검

Docker Linux 엔진과 Git·Python·Node 등 나머지 도구가 준비된 후 실행한다. 아래 경로는 학교 PC의 예이므로 실제 저장소 경로에 맞춘다.

```powershell
Set-Location -LiteralPath 'C:\uengine\hyd-iot-edu'
.\시작.bat
```

시작 완료를 확인한 뒤 실행한다.

```powershell
.\점검.bat
```

검증 완료 후 재부팅해 설치 상태가 유지되는지 확인하고, 정상 상태를 복구 기준 또는 배포 이미지로 저장한다.

기존 프로그램은 버전과 관계없이 유지하는 것이 설치 스크립트의 정책이다. Python·Anaconda도 있으면 설치를 건너뛴다. 이미 추가 설치된 Python을 자동 삭제하는 변경은 아니다. 키를 공개 문서나 저장소에 넣지 않는다.

## 공식 참고

- [Microsoft: Hyper-V 활성화와 지원 조건](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/get-started/install-hyper-v?pivots=windows)
- [Docker: Windows 설치 형태·Hyper-V 요구 사항](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker: 설정 항목](https://docs.docker.com/desktop/settings-and-maintenance/settings/)
- [Microsoft: WSL 명령](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
- [Microsoft: 레지스트리 키 접근 권한](https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-key-security-and-access-rights)
