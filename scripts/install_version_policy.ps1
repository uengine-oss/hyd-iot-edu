# 설치 부작용 없이 버전 판정만 공유한다. Windows PowerShell 5.1 호환.
function ConvertTo-InstallVersion($text) {
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    $match = [regex]::Match($text, '(?<!\d)(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?')
    if (-not $match.Success) { return $null }
    $revision = 0
    if ($match.Groups[4].Success) { $revision = [int]$match.Groups[4].Value }
    return [version]::new([int]$match.Groups[1].Value, [int]$match.Groups[2].Value, [int]$match.Groups[3].Value, $revision)
}

function Get-InstallAction($found, $minimum) {
    $required = ConvertTo-InstallVersion $minimum
    if ($null -eq $required) { throw "잘못된 기준 버전: $minimum" }
    if ([string]::IsNullOrWhiteSpace($found)) { return 'install' }
    $current = ConvertTo-InstallVersion $found
    if ($null -eq $current) { throw "기존 버전을 확인할 수 없습니다: $found" }
    if ($current -lt $required) { return 'upgrade' }
    return 'keep'
}

# 기준 판은 scripts\versions.txt 하나에서 읽는다(Mac 설치 · 시작도 같은 파일). 빠진 줄이 있으면 설치를 시작하지 않는다.
function Get-InstallVersions {
    $path = Join-Path $PSScriptRoot 'versions.txt'
    $values = @{}
    foreach ($line in (Get-Content -LiteralPath $path -Encoding UTF8)) {
        if ($line -match '^([A-Z_]+)=(\S+)$') { $values[$Matches[1]] = $Matches[2] }
    }
    foreach ($name in 'DOCKER_DESKTOP_MIN', 'VSCODE_MIN', 'NODE_MIN', 'GIT_MIN', 'PYTHON_MIN', 'PYTHON_NEW', 'WSL_MIN', 'SUPABASE_CLI') {
        if (-not $values[$name]) { throw "기준 판 파일($path)에 $name 줄이 없습니다." }
    }
    return $values
}
