# Resolve the current user's installed App Installer without a fixed user,
# drive, architecture, or package-version directory. Do not change system PATH.
function Get-WingetCandidates {
    $command = Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { $command.Source }
    if (Get-Command Get-AppxPackage -ErrorAction SilentlyContinue) {
        try {
            Get-AppxPackage -Name Microsoft.DesktopAppInstaller -ErrorAction Stop |
                Sort-Object Version -Descending |
                ForEach-Object {
                    if ($_.InstallLocation) { Join-Path $_.InstallLocation 'winget.exe' }
                }
        } catch { } # A restricted AppX query must not invalidate a working PATH executable.
    }
}

function Test-WingetExecutable($path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
    try {
        $ErrorActionPreference = 'Continue'
        $version = @(& $path --version 2>&1)
        return ($LASTEXITCODE -eq 0 -and (($version -join ' ') -match 'v?\d+\.\d+'))
    } catch { return $false }
}

function Resolve-WingetExecutable {
    foreach ($candidate in @(Get-WingetCandidates | Select-Object -Unique)) {
        if (Test-WingetExecutable $candidate) { return $candidate }
    }
    throw 'Windows 설치 도구(winget)를 찾지 못했습니다. Microsoft Store에서 「앱 설치 관리자(App Installer)」(https://apps.microsoft.com/detail/9nblggh4nns1)를 설치하거나 업데이트한 뒤 설치.bat을 다시 실행하세요.'
}
