param(
    [string]$ArchivePath = (Join-Path $PSScriptRoot 'classroom-source.zip'),
    [string]$Destination = $PSScriptRoot
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$targetRoot = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\', '/')
if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
    throw '프로젝트를 둘 폴더에 이 배포 묶음을 풀어 주세요.'
}
$archiveFull = [System.IO.Path]::GetFullPath($ArchivePath)
$backupRoot = Join-Path $targetRoot ('.hyd-runtime/package-backups/' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
$changes = [System.Collections.Generic.List[object]]::new()
$kept = 0
$unchanged = 0
$written = 0
$archive = [System.IO.Compression.ZipFile]::OpenRead($archiveFull)
try {
    foreach ($entry in $archive.Entries) {
        $relative = $entry.FullName.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        $target = [System.IO.Path]::GetFullPath((Join-Path $targetRoot $relative))
        if (-not $target.StartsWith($targetRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw '배포 파일 경로가 프로젝트 폴더를 벗어났습니다.'
        }
        if ($entry.FullName.EndsWith('/')) { continue }
        # Existing per-PC environment files can contain the class key and student settings.
        if (($entry.FullName -eq 'it/supabase/config.toml' -or [System.IO.Path]::GetFileName($relative) -eq '.env') -and (Test-Path -LiteralPath $target -PathType Leaf)) {
            $kept++
            continue
        }
        $existed = Test-Path -LiteralPath $target -PathType Leaf
        if ($existed) {
            $hasher = [System.Security.Cryptography.SHA256]::Create()
            $source = $entry.Open()
            try { $sourceHash = [Convert]::ToBase64String($hasher.ComputeHash($source)) }
            finally { $source.Dispose(); $hasher.Dispose() }
            $hasher = [System.Security.Cryptography.SHA256]::Create()
            $existing = [System.IO.File]::OpenRead($target)
            try { $existingHash = [Convert]::ToBase64String($hasher.ComputeHash($existing)) }
            finally { $existing.Dispose(); $hasher.Dispose() }
            if ($sourceHash -eq $existingHash) { $unchanged++; continue }
            $backup = Join-Path $backupRoot $relative
            [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($backup)) | Out-Null
            [System.IO.File]::Copy($target, $backup, $false)
        } else { $backup = $null }
        [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($target)) | Out-Null
        $changes.Add([pscustomobject]@{Target=$target; Backup=$backup; Existed=$existed})
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
        $written++
    }
} catch {
    $failure = $_
    $rollbackErrors = [System.Collections.Generic.List[string]]::new()
    for ($i = $changes.Count - 1; $i -ge 0; $i--) {
        $change = $changes[$i]
        try {
            if ($change.Existed) { [System.IO.File]::Copy($change.Backup, $change.Target, $true) }
            elseif (Test-Path -LiteralPath $change.Target -PathType Leaf) { [System.IO.File]::Delete($change.Target) }
        } catch { $rollbackErrors.Add($change.Target) }
    }
    if ($rollbackErrors.Count) { throw "공통 파일 적용과 일부 되돌리기에 실패했습니다. 보관 폴더: $backupRoot. 원인: $failure" }
    throw "공통 파일 적용에 실패해 변경된 파일을 되돌렸습니다. 보관 폴더: $backupRoot. 원인: $failure"
} finally {
    $archive.Dispose()
}
Write-Output ('공통 파일 적용 완료: ' + $written + '개, 동일한 파일 유지: ' + $unchanged + '개')
if ($kept) { Write-Output '기존 환경 파일과 업무 DB 설정을 보존했습니다.' }
if (Test-Path -LiteralPath $backupRoot -PathType Container) { Write-Output ('변경 전 파일 보관: ' + $backupRoot) }
Write-Output '다음은 이 폴더의 시작.bat을 실행하세요. 마지막 날에는 포털에서 강사 코드만 입력합니다.'
