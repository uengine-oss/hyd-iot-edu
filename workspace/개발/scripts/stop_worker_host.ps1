# 개발용 호스트 워커(run_worker_host.sh — python -m worker.main)와 그 자식(Claude Code CLI · MCP 서버)을 모두 끝내고, 끝났는지 확인한다.
#   powershell -File workspace/개발/scripts/stop_worker_host.ps1                 (결과를 화면에)
#   powershell -File workspace/개발/scripts/stop_worker_host.ps1 -Evidence 작업/<날짜>_<제목>/worker-stop.json   (결과를 파일로도)
# 통합 테스트(scenario_*) 전에 부른다(워커가 에이전트 작업을 가져간다).
param([string]$Evidence = '')
$allProcesses = @(Get-CimInstance Win32_Process)
$roots = @($allProcesses | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -like '*worker.main*' })
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
# 워커 상태 포트(8097)와 그 옆 포트(8098)를 파이썬이 아직 쥐고 있지 않은지(CLAUDE.md 6절). 컨테이너 워커의 포트는 Docker 가 쥐므로 세지 않는다.
$pythons = @($after | Where-Object { $_.Name -match '^python(w)?\.exe$' } | ForEach-Object { [int]$_.ProcessId })
$listening = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 8097, 8098 -and $pythons -contains [int]$_.OwningProcess } |
    ForEach-Object { [pscustomobject]@{port=$_.LocalPort; pid=$_.OwningProcess} })
$report = [pscustomobject]@{time=(Get-Date).ToString('o');terminatedTree=@($targetIds);remainingWorkers=$remaining.Count;remainingTreePids=$remainingTree;listening=$listening}
if ($Evidence) { $report | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $Evidence }
$report | ConvertTo-Json -Depth 4
if ($remaining.Count -or $remainingTree.Count -or $listening.Count) { exit 1 }
