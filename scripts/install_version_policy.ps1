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
