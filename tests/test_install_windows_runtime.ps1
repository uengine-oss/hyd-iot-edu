$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../scripts/install_version_policy.ps1"
. "$PSScriptRoot/../scripts/install_windows_runtime.ps1"
function Record($name,$state,$note) { $script:lastState=$state; $script:lastNote=$note }
function Get-PythonVersion { $script:pythonVersion }
function Installed-App { $script:pythonTarget }
function Install-Winget($id,$action,$extra) {
    $script:calls++; $script:lastAction=$action
    if ($script:succeeds) { $script:pythonVersion='Python 3.14.7' }
}
foreach ($case in @(
 @('Python 3.14.7',$null,0,'', $true),
 @('Python 3.15.0',$null,0,'', $true),
 @('Python 3.13.5',$null,0,'', $true),
 @('Python 3.12.0',$null,1,'install',$true),
 @('Python 3.12.9','Python 3.14.6',1,'upgrade',$true),
 @($null,$null,1,'install',$false)
)) {
 $script:pythonVersion=$case[0]; $script:pythonTarget=$case[1]
 $script:calls=0; $script:lastAction=''; $script:succeeds=$case[4]
 Ensure-Python
 if ($script:calls -ne $case[2] -or $script:lastAction -ne $case[3]) { throw 'Python install policy mismatch' }
 if (-not $case[4] -and $script:lastState -ne ([char]0xC2E4).ToString()+[char]0xD328) { throw 'Python failed postcheck accepted' }
}
function Get-WindowsOptionalFeature { [pscustomobject]@{State=$script:featureState} }
function Enable-WindowsOptionalFeature { $script:enabled++ }
function Version-Of { $script:wslVersion }
function wsl.exe {
 $script:wslCalls++; $script:wslArgs=$args -join ' '
 if ($script:succeeds) { $script:wslVersion='WSL 2.7.12.0' }
 $global:LASTEXITCODE=0
}
foreach ($case in @(
 @('WSL 2.7.12.0','Enabled',0,0,''),
 @('WSL 2.8.0.0','Enabled',0,0,''),
 @('WSL 2.6.0.0','Enabled',1,0,'--update'),
 @($null,'Disabled',1,2,'--install --no-distribution')
)) {
 $script:wslVersion=$case[0]; $script:featureState=$case[1]; $script:wslCalls=0
 $script:enabled=0; $script:wslArgs=''; $script:succeeds=$true; $script:restart=$false
 Ensure-WSL
 if ($script:wslCalls -ne $case[2] -or $script:enabled -ne $case[3] -or $script:wslArgs -ne $case[4]) { throw 'WSL install policy mismatch' }
 if ($case[3] -gt 0 -and -not $script:restart) { throw 'Missing reboot notice' }
}
Write-Host 'PASS: 6 Python and 4 WSL mocked scenarios; no machine changes.'
