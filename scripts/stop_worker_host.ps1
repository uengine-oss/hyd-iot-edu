param([string]$Evidence = '.evidence/reaudit/worker-stop.json', [switch]$StopScenario)
$allProcesses = @(Get-CimInstance Win32_Process)
$roots = @($allProcesses | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -like '*worker.main*' })
if ($StopScenario) {
    $roots += @($allProcesses | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -like '*scenario_instance_test.py --worker*' })
}
$targetIds = [System.Collections.Generic.HashSet[int]]::new()
foreach ($p in $roots) { [void]$targetIds.Add([int]$p.ProcessId) }
do {
    $added = $false
    foreach ($p in $allProcesses) {
        if ($targetIds.Contains([int]$p.ParentProcessId) -and $targetIds.Add([int]$p.ProcessId)) { $added = $true }
    }
} while ($added)
$targetIds | Sort-Object -Descending | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
$after = @(Get-CimInstance Win32_Process)
$remaining = @($after | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -like '*worker.main*' })
$remainingTree = @($after | Where-Object { $targetIds.Contains([int]$_.ProcessId) } | ForEach-Object { $_.ProcessId })
$report = [pscustomobject]@{time=(Get-Date).ToString('o');terminatedTree=@($targetIds);remainingWorkers=$remaining.Count;remainingTreePids=$remainingTree}
$report | ConvertTo-Json | Set-Content -Encoding UTF8 $Evidence
$report | ConvertTo-Json
if ($remaining.Count -or $remainingTree.Count) { exit 1 }
