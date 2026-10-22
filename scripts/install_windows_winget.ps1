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
    throw 'App Installer (winget) is unavailable. Install or repair Microsoft App Installer from https://apps.microsoft.com/detail/9nblggh4nns1, then rerun 설치.bat.'
}
