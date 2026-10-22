$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../scripts/install_windows_winget.ps1"

# Exercise PATH/package discovery without invoking installs or changing the machine.
function Get-Command($Name) {
    if ($Name -eq 'winget.exe' -and $script:pathExecutable) { [pscustomobject]@{Source=$script:pathExecutable} }
    if ($Name -eq 'Get-AppxPackage' -and $script:appxAvailable) { [pscustomobject]@{Name=$Name} }
}
function Get-AppxPackage {
    if ($script:appxFails) { throw 'AppX access denied' }
    $script:packages
}
function Test-WingetExecutable($path) { $script:validExecutables -contains $path }
$script:pathExecutable='C:\aliases\winget.exe'; $script:appxAvailable=$true; $script:appxFails=$false
$script:packages=@([pscustomobject]@{Version=[version]'2.0';InstallLocation='D:\Packages\AppInstaller_arm64_2'})
$packageExecutable='D:\Packages\AppInstaller_arm64_2\winget.exe'
$script:validExecutables=@($script:pathExecutable,$packageExecutable)
if ((Resolve-WingetExecutable) -ne $script:pathExecutable) { throw 'Working PATH not preferred' }
$script:validExecutables=@($packageExecutable)
if ((Resolve-WingetExecutable) -ne $packageExecutable) { throw 'Broken alias blocked package fallback' }
$script:pathExecutable=$null
if ((Resolve-WingetExecutable) -ne $packageExecutable) { throw 'Missing PATH blocked registered package' }
$script:pathExecutable='C:\aliases\winget.exe';$script:validExecutables=@($script:pathExecutable);$script:appxFails=$true
if ((Resolve-WingetExecutable) -ne $script:pathExecutable) { throw 'AppX error blocked working PATH' }
$script:appxFails=$false;$script:appxAvailable=$false
if ((Resolve-WingetExecutable) -ne $script:pathExecutable) { throw 'Unavailable AppX blocked working PATH' }
$script:pathExecutable=$null;$script:validExecutables=@()
$failed=$false
try { Resolve-WingetExecutable | Out-Null } catch { $failed=$_.Exception.Message -match 'App Installer' }
if (-not $failed) { throw 'Missing installer must produce actionable failure' }
Write-Host 'PASS: 6 winget discovery scenarios; no installs or machine changes.'
