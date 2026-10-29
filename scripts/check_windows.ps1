# 실습 스택이 끝까지 도는지 자동으로 점검한다. 저장소 루트의 점검.bat을 더블클릭하면 이 파일을 실행한다(시작.bat이 「완료」된 뒤).
# 포털을 사람이 클릭하는 대신 포털 버튼이 부르는 것과 같은 API를 부른다:
#   1) 서비스 12개 · AI 워커 · 포털이 응답하는가
#   2) 쿨러 사건 한 바퀴(수업 흐름 c3_cooling): 설비 초기화 → 쿨러 열화 주입 → 경보 → 처리 건 → AI 워커의 「판단 · 제안」(강의 중계 모델)
#      → 쿨러 복구 → 점검이 연 처리 건 정리(「조치 전 해소」로 스스로 닫힌다)
#      시작.bat이 수업용 기본 지식(HM-8 · PM-02 · PR-07 검토본)을 넣으므로 「운전원 승인 대기」까지 간다. 기본 지식이 빠진 PC면 「판단 보류」로 멈춘다(그때는 시작.bat을 다시).
#   3) 루트 .env를 우선 사용하고, 미설정이면 기존 실습 폴더 .env로 중계 연결을 확인한다.
#      키 없는 온라인 PC(워커 ai_mode = replay)는 중계를 부르지 않으므로 건너뛴다 — AI 단계는 강사가 저장한 AI 응답 재생(문서/시스템/참조/재생모드.md).
# 점검이 연 처리 건은 끝에 정리한다(복제 이미지에 열린 처리 건이 남지 않게). 데이터는 지우지 않는다.
param([switch]$SkipLlm, [string]$LlmEnvFile)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$H = 'http://127.0.0.1'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
# 서비스 점검 포트는 시작.bat이 저장한 숫자 포트 표에서 읽는다.
$portMap = @{}
$portFile = Join-Path $repo '.hyd-runtime/ports.json'
if (Test-Path $portFile) {
    $savedPorts = Get-Content -LiteralPath $portFile -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $savedPorts.PSObject.Properties) {
        $port = 0
        if ($entry.Name -notmatch '^\d+$' -or -not [int]::TryParse([string]$entry.Value, [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
            throw '포트 설정이 올바르지 않습니다. 시작.bat을 다시 실행하세요.'
        }
        $portMap[[int]$entry.Name] = $port
    }
}
function Host-Port([int]$port) {
    if ($portMap.ContainsKey($port)) { return $portMap[$port] }
    return $port
}
function Service-Url([int]$port) { return "${H}:$(Host-Port $port)" }
$PROCESS = Service-Url 8080; $DETECTOR = Service-Url 8092; $PLANT = Service-Url 8000
$who = @{ by = '설치 점검'; user_id = $null; roles = @() }

$results = [System.Collections.Generic.List[object]]::new()
function Record($step, $ok, $note) { $results.Add([pscustomobject]@{ 점검 = $step; 결과 = $(if ($ok) { '통과' } else { '실패' }); 내용 = $note }) }
function Say($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Get-J($url) { Invoke-RestMethod -Uri $url -TimeoutSec 15 }
function Post-J($url, $body) {
    $json = $body | ConvertTo-Json -Depth 6 -Compress
    Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec 60
}
function Wait-Until($seconds, [scriptblock]$probe) {
    # $probe가 $null이 아닌 값을 낼 때까지 기다린다. 시간이 지나면 $null
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try { $v = & $probe; if ($null -ne $v) { return $v } } catch { }
        Start-Sleep -Seconds 2
    }
    return $null
}
function Hyd01 { (Get-J "$DETECTOR/api/detector/state").assets.'HYD-01' }
function Show-Results {
    Say "`n== 결과" 'White'
    $results | Format-Table -AutoSize -Wrap | Out-String -Width 160 | Write-Host
    $bad = @($results | Where-Object { $_.결과 -eq '실패' })
    if ($bad.Count) { Say "실패 $($bad.Count)건. 위 표에서 실패 항목의 「내용」을 보고 고친 뒤 다시 점검하세요." 'Red' }
    else { Say '모두 통과했습니다.' 'Green' }
    Read-Host '창을 닫으려면 Enter' | Out-Null
}

Say "`n== 실습 스택 점검 (약 5~8분)" 'White'

# 1. 서비스
Say "`n[1/3] 서비스 응답"
$down = @()
foreach ($p in 8000, 8093, 8090, 8094, 8092, 8091, 8080, 8095, 8199, 8198, 8196, 8195) {
    try { $hz = Invoke-RestMethod -Uri "$(Service-Url $p)/healthz" -TimeoutSec 5; if (-not $hz.ok) { $down += (Host-Port $p) } } catch { $down += (Host-Port $p) }   # $h는 $H와 같은 변수(대소문자 무시)라 쓰지 않는다
}
# AI 워커는 일을 하는 중에도 응답한다(status ok). 켜지는 중(starting)이면 1분까지 기다린다
$worker = Wait-Until 60 { $w = Invoke-RestMethod -Uri "$(Service-Url 8097)/healthz" -TimeoutSec 5; if ($w.status -eq 'ok') { $w } }
if (-not $worker) { $down += "$(Host-Port 8097)(AI 워커)" }
try { $portal = (Invoke-WebRequest -Uri "$(Service-Url 8088)/" -UseBasicParsing -TimeoutSec 5).StatusCode } catch { $portal = 0 }
if ($down.Count -eq 0 -and $portal -eq 200) { Record '서비스 12개 · AI 워커 · 포털' $true '모두 응답' }
else {
    Record '서비스 12개 · AI 워커 · 포털' $false "응답 없음: $($down -join ', ')$(if ($portal -ne 200) { " 포털($(Host-Port 8088))" }) — 시작.bat을 먼저 끝까지 실행하세요"
    Show-Results; exit 1
}
$ph = Get-J "$PROCESS/healthz"
if ($ph.mode -ne 'instance' -or -not $ph.supabase) { Record '처리 엔진 설정' $false "mode=$($ph.mode) supabase=$($ph.supabase) — 시작.bat이 강의 배포본 값으로 맞춥니다. 시작.bat을 다시 실행하세요" }
else { Record '처리 엔진 설정' $true '강의 배포본(instance · 업무 DB 연결)' }

# 2. 쿨러 사건 한 바퀴 (수업 흐름 c3_cooling: T_agent 판단 · 제안 → T_approve 운전원 승인)
Say "`n[2/3] 쿨러 사건 한 바퀴 (경보까지 1분, AI 판단까지 2~4분 걸립니다)"
$instance = $null
try {
    Post-J "$PLANT/api/reset" @{} | Out-Null
    $idle = Wait-Until 120 { $s = Hyd01; if ($s.phase -ne 'RAISED') { $s } }
    if (-not $idle) { throw 'HYD-01 경보가 2분이 지나도 풀리지 않습니다. 열린 처리 건을 포털에서 먼저 끝내세요' }
    # 웹 응답의 목록은 PowerShell이 한 덩어리로 넘기므로 foreach 문으로 하나씩 돈다
    $before = @(); foreach ($i in (Get-J "$PROCESS/api/instances?limit=20")) { $before += $i.proc_inst_id }
    Post-J "$PROCESS/api/scenario/A/degrade" $who | Out-Null
    $raised = Wait-Until 240 { $s = Hyd01; if ($s.phase -eq 'RAISED') { $s } }
    if (-not $raised) { throw '쿨러 열화를 주입했지만 4분 안에 경보가 나지 않았습니다(감지 서비스 확인)' }
    Record '경보' $true ("유온 {0} ℃ · 냉각 효율 {1} %" -f $raised.ts1, $raised.ce)

    $instance = Wait-Until 60 { foreach ($i in (Get-J "$PROCESS/api/instances?limit=20")) { if ($before -notcontains $i.proc_inst_id) { return $i } }; $null }
    if (-not $instance) { throw '경보가 났지만 1분 안에 처리 건이 열리지 않았습니다(처리 엔진 확인)' }
    $pid_ = $instance.proc_inst_id
    if ($instance.proc_def_id -ne 'c3_cooling') { throw "처리 건이 수업 흐름이 아닌 $($instance.proc_def_id) 로 열렸습니다 — 시작.bat을 다시 실행하면 수업 흐름을 배포합니다" }
    Record '처리 건 열림' $true "$pid_ (수업 흐름 냉각 긴급 대응)"

    # AI 워커가 강의 중계 모델로 판단한다. 느린 PC · 중계 지연까지 7분 기다린다(2026-10-25 실측 약 2분)
    $outcome = Wait-Until 420 {
        $v = Get-J "$PROCESS/api/instances/$pid_"
        $agent = $v.workitems | Where-Object { $_.activity_id -eq 'T_agent' }
        $approve = $v.workitems | Where-Object { $_.activity_id -eq 'T_approve' -and $_.status -eq 'IN_PROGRESS' }
        if ($approve) { '판단 완료 — 추천 카드가 나와 운전원 승인 대기(수업용 기본 지식으로 판단)' }
        elseif ($agent.status -eq 'PENDING' -and ($v.events | Where-Object { $_.event_type -eq 'task_deferred' })) { throw '판단이 보류됐습니다 — 수업용 기본 지식이 없는 것 같습니다. 시작.bat을 다시 실행하세요(7단계가 기본 지식을 넣습니다)' }
        elseif ($agent.status -in @('FAILED', 'ERROR', 'CANCELLED')) { throw "AI 워커가 판단하지 못했습니다($($agent.status)): $("$($agent.log)".Trim()) — $(if ($worker.ai_mode -eq 'replay') { 'git pull로 강사가 저장한 AI 응답(it/agent-worker/replay)이 든 최신 판을 받았는지 확인하세요' } else { '.env의 LLM_API_KEY와 인터넷 연결을 확인하세요' })" }
    }
    if (-not $outcome) { throw '처리 건이 7분 안에 판단 결과(보류 또는 승인 대기)에 닿지 않았습니다 — 포털 「처리 건」에서 판단 · 제안 단계의 기록을 확인하세요' }
    Record 'AI 판단 · 제안' $true $outcome
}
catch { Record '쿨러 사건' $false $_.Exception.Message }
finally {
    # 쿨러 복구와 정리: 점검이 연 처리 건이 열린 채 남지 않게 한다
    try { Post-J "$PROCESS/api/scenario/A/restore" $who | Out-Null } catch { }
    if ($instance) {
        $pid_ = $instance.proc_inst_id
        # 보류된 건은 쿨러 복구로 경보가 풀리면 「조치 전 해소」로 스스로 닫힌다(실측 약 1분). 3분이 지나도 열려 있으면 보류 단계를 닫는다
        $deadline = (Get-Date).AddSeconds(180)
        $closed = Wait-Until 300 {
            $v = Get-J "$PROCESS/api/instances/$pid_"
            if ($v.instance.status -ne 'RUNNING') { return $v.instance.status }
            if ((Get-Date) -gt $deadline) {
                foreach ($w in @($v.workitems | Where-Object { $_.status -eq 'PENDING' -and $_.agent_mode })) {
                    try { Post-J "$PROCESS/api/todolist/$($w.id)/close" @{ by = '설치 점검'; reason = '설치 점검이 연 처리 건 정리(쿨러 복구 뒤)' } | Out-Null } catch { }
                }
            }
            $null
        }
        if ($closed) { Record '점검 처리 건 정리' $true "처리 건 종료($closed)" }
        else {
            $v = Get-J "$PROCESS/api/instances/$pid_"
            if ($v.workitems | Where-Object { $_.activity_id -eq 'T_approve' -and $_.status -eq 'IN_PROGRESS' }) {
                # 문서를 적재한 PC: 운전원 승인 단계가 열려 있다. 점검이 대신 승인하거나 거절하지 않는다
                Record '점검 처리 건 정리' $true "운전원 승인 단계가 열린 채 남음 — 포털 「작업함」에서 이 건을 거절해 닫으세요($pid_)"
            }
            else { Record '점검 처리 건 정리' $false "처리 건 $pid_ 이 아직 열려 있습니다. 포털 「처리 건」에서 확인하세요" }
        }
    }
    try { Post-J "$PLANT/api/reset" @{} | Out-Null } catch { }
}

# 3. 5회차 실습 2: 중계 서버 연결
Say "`n[3/3] 5회차 실습 2 — 중계 서버 연결"
function Read-RelaySettings($path) {
    $values = @{}
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        foreach ($line in (Get-Content -LiteralPath $path -Encoding UTF8)) {
            if ($line -match '^\s*(OPENAI_BASE_URL|LLM_API_KEY|LLM_MODEL|HYD_CLASSROOM_URL)\s*=\s*(.*)$') {
                $values[$Matches[1]] = $Matches[2].Trim().Trim('"', "'")
            }
        }
    }
    return $values
}
function Select-RelaySettings($root, $explicitFile) {
    $rootPath = Join-Path $root '.env'
    $rootValues = Read-RelaySettings $rootPath
    # A lab file override must not turn a managed classroom check into a
    # direct model request. The server still enforces the real cost boundary.
    if ($rootValues['HYD_CLASSROOM_URL']) {
        return [pscustomobject]@{ Path = $rootPath; Values = $rootValues }
    }
    if ($explicitFile) {
        $path = [System.IO.Path]::GetFullPath($explicitFile)
        return [pscustomobject]@{ Path = $path; Values = (Read-RelaySettings $path) }
    }
    $paths = @((Join-Path $root '.env'), (Join-Path $root 'course/labs/offline/05-2-cause-agent/.env'))
    foreach ($path in $paths) {
        $values = Read-RelaySettings $path
        # 키가 있는 파일을 선택한 뒤 누락 항목을 보고한다. 서로 다른 파일의 값을 섞지 않는다.
        if ($values['LLM_API_KEY']) { return [pscustomobject]@{ Path = $path; Values = $values } }
    }
    return [pscustomobject]@{ Path = $paths[0]; Values = @{} }
}
function Test-ClassroomKey($root, $values) {
    # Reuse the startup contract inside the already-running process container.
    # Only public code and URL are argv; the key travels through stdin.
    $source = Get-Content -LiteralPath (Join-Path $root 'scripts/check_classroom.py') -Raw -Encoding UTF8
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($source))
    $program = "exec(__import__('base64').b64decode('$encoded'))"
    $message = $values['LLM_API_KEY'] | & docker compose exec -T process python -c $program $values['HYD_CLASSROOM_URL'] 2>$null
    if ($LASTEXITCODE -ne 0) { throw '관리 서버 인증 실패. HTTPS 주소·수업 키·권한·실행 중 process를 확인하세요.' }
    return ($message -join ' ')
}
if ($SkipLlm) { Record '중계 서버' $true '건너뜀(-SkipLlm)' }
elseif ($worker.ai_mode -eq 'replay') { Record '중계 서버' $true '건너뜀 — 키 없는 온라인 수업(AI 단계는 강사가 미리 진행한 결과 재생)' }
else {
    $selected = Select-RelaySettings $repo $LlmEnvFile
    $vals = $selected.Values
    if ($vals['HYD_CLASSROOM_URL']) {
        try { Record '관리 서버' $true (Test-ClassroomKey $repo $vals) }
        catch { Record '관리 서버' $false '관리 서버 인증 실패. HTTPS 주소·수업 키·권한·실행 중 process를 확인하세요. 직접 모델 호출로 우회하지 않습니다.' }
    }
    else {
        $missing = @('OPENAI_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL' | Where-Object { -not $vals[$_] })
        if ($missing.Count) { Record '중계 서버' $false ("{0}: {1} 설정이 필요합니다. 저장 후 점검.bat을 다시 실행하세요." -f $selected.Path, ($missing -join ', ')) }
        else {
            $body = @{ model = $vals['LLM_MODEL']; messages = @(@{ role = 'user'; content = 'Reply with exactly: OK' }); max_completion_tokens = 50 }
            try {
                $r = Invoke-RestMethod -Method Post -Uri ($vals['OPENAI_BASE_URL'].TrimEnd('/') + '/chat/completions') -Headers @{ Authorization = 'Bearer ' + $vals['LLM_API_KEY'] } `
                    -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 5) -TimeoutSec 120
                Record '중계 서버' $true ("연결됨 · {0} · 답: {1}" -f $vals['LLM_MODEL'], ("$($r.choices[0].message.content)".Trim()))
            }
            catch {
                $code = $null; try { $code = [int]$_.Exception.Response.StatusCode } catch { }
                $why = switch ($code) { 401 { '키가 맞지 않거나 서버 쪽 키 문제' } 403 { 'LLM_MODEL 이름이 이 키에 허용되지 않음' } 404 { '주소가 맞지 않음(끝이 /v1인지)' } 429 { '서버가 잠시 바쁨 — 1분 뒤 다시' } default { $_.Exception.Message } }
                Record '중계 서버' $false "묻지 못했다($code): $why — 선택된 설정 파일: $($selected.Path)"
            }
        }
    }
}

Show-Results
if (@($results | Where-Object { $_.결과 -eq '실패' }).Count) { exit 1 }
