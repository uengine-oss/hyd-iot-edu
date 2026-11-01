# 개발용 호스트 워커(run_worker_host.sh — python -m worker.main)와 그 자식(Claude Code CLI · MCP 서버)을 모두 끝내고, 끝났는지 확인한다.
#   powershell -NoProfile -ExecutionPolicy Bypass -File workspace/개발/scripts/stop_worker_host.ps1                 (결과를 화면에)
#   powershell -NoProfile -ExecutionPolicy Bypass -File workspace/개발/scripts/stop_worker_host.ps1 -Evidence 작업/<날짜>_<제목>/worker-stop.json
# 컨테이너 워커를 다시 켜기 전에 부른다(워커는 하나). 남은 워커 인증 파일 사본(.hyd-runtime/worker-runtime.key)도 지운다.
param([string]$Evidence = '')
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
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
$key = Join-Path $root '.hyd-runtime\worker-runtime.key'
if (Test-Path $key) { Remove-Item -LiteralPath $key -Force }
$after = @(Get-CimInstance Win32_Process)
$remaining = @($after | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -like '*worker.main*' })
$remainingTree = @($after | Where-Object { $targetIds.Contains([int]$_.ProcessId) } | ForEach-Object { $_.ProcessId })
# 워커 상태 포트(시작이 정한 이 PC의 8097 바깥 포트 — .hyd-runtime/ports.json)를 파이썬이 아직 쥐고 있지 않은지. 컨테이너 워커의 포트는 Docker 가 쥐므로 세지 않는다.
$healthPort = 8097
$portsFile = Join-Path $root '.hyd-runtime\ports.json'
if (Test-Path $portsFile) { $healthPort = [int]((Get-Content -Raw -Encoding UTF8 $portsFile | ConvertFrom-Json).'8097') }
$pythons = @($after | Where-Object { $_.Name -match '^python(w)?\.exe$' } | ForEach-Object { [int]$_.ProcessId })
$listening = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $healthPort -and $pythons -contains [int]$_.OwningProcess } |
    ForEach-Object { [pscustomobject]@{port=$_.LocalPort; pid=$_.OwningProcess} })
$report = [pscustomobject]@{time=(Get-Date).ToString('o');terminatedTree=@($targetIds);remainingWorkers=$remaining.Count;remainingTreePids=$remainingTree;listening=$listening;keyRemoved=-not (Test-Path $key)}
if ($Evidence) { $report | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $Evidence }
$report | ConvertTo-Json -Depth 4
if ($remaining.Count -or $remainingTree.Count -or $listening.Count -or (Test-Path $key)) { exit 1 }
