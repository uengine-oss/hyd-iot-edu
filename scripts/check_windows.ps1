# 실습 스택이 끝까지 도는지 자동으로 점검한다. 저장소 루트의 점검.bat을 더블클릭하면 이 파일을 실행한다(시작.bat이 「완료」된 뒤).
# 포털을 사람이 클릭하는 대신 포털 버튼이 부르는 것과 같은 API를 부른다:
#   1) 서비스 10개와 포털이 응답하는가
#   2) 쿨러 사건 한 바퀴: 전체 초기화 → 쿨러 열화 주입 → 경보 → 처리 건 → 원인 진단 결과 → 쿨러 복구 → 점검이 연 처리 건 정리
#      새 PC(수업용 구조판 지식)에서는 「원인 진단 보류」가 정상이다. 원인 지식이 있으면 「조치 선택」까지 간다.
#   3) 5회차 실습 2 폴더의 .env: 비어 있으면 중계 주소 · 키를 물어 적고, 실제 모델(coding)에 연결되는지 본다
# 점검이 연 처리 건은 끝에 정리한다(복제 이미지에 열린 처리 건이 남지 않게). 데이터는 지우지 않는다.
param([switch]$SkipLlm)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$H = 'http://127.0.0.1'
$PROCESS = "${H}:8080"; $DETECTOR = "${H}:8092"; $PLANT = "${H}:8000"
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
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
    if ($bad.Count) { Say "실패 $($bad.Count)건. 내용을 보고 학교PC_설치확인.md C절(막혔을 때)을 따르세요." 'Red' }
    else { Say '모두 통과했습니다.' 'Green' }
    Read-Host '창을 닫으려면 Enter' | Out-Null
}

Say "`n== 실습 스택 점검 (약 3~5분)" 'White'

# 1. 서비스
Say "`n[1/3] 서비스 응답"
$down = @()
foreach ($p in 8000, 8093, 8090, 8094, 8092, 8091, 8080, 8095, 8199, 8198) {
    try { $hz = Invoke-RestMethod -Uri "${H}:$p/healthz" -TimeoutSec 5; if (-not $hz.ok) { $down += $p } } catch { $down += $p }   # $h는 $H와 같은 변수(대소문자 무시)라 쓰지 않는다
}
try { $portal = (Invoke-WebRequest -Uri "${H}:8088/" -UseBasicParsing -TimeoutSec 5).StatusCode } catch { $portal = 0 }
if ($down.Count -eq 0 -and $portal -eq 200) { Record '서비스 10개 · 포털' $true '모두 응답' }
else {
    Record '서비스 10개 · 포털' $false "응답 없음: $($down -join ', ')$(if ($portal -ne 200) { ' 포털(8088)' }) — 시작.bat을 먼저 끝까지 실행하세요"
    Show-Results; exit 1
}
$ph = Get-J "$PROCESS/healthz"
if ($ph.mode -ne 'instance' -or -not $ph.supabase) { Record '처리 엔진 설정' $false "mode=$($ph.mode) supabase=$($ph.supabase) — 시작.bat이 강의 배포본 값으로 맞춥니다. 시작.bat을 다시 실행하세요" }
else { Record '처리 엔진 설정' $true '강의 배포본(instance · 업무 DB 연결)' }

# 2. 쿨러 사건 한 바퀴
Say "`n[2/3] 쿨러 사건 한 바퀴 (경보까지 1분쯤 걸립니다)"
$instance = $null
try {
    Post-J "$PLANT/api/reset" @{} | Out-Null
    $idle = Wait-Until 120 { $s = Hyd01; if ($s.phase -ne 'RAISED') { $s } }
    if (-not $idle) { throw 'HYD-01 경보가 2분이 지나도 풀리지 않습니다. 열린 처리 건을 포털에서 먼저 끝내세요' }
    # 웹 응답의 목록은 PowerShell이 한 덩어리로 넘기므로 foreach 문으로 하나씩 돈다
    $before = @(); foreach ($i in (Get-J "$PROCESS/api/instances?limit=20")) { $before += $i.proc_inst_id }
    Post-J "$PROCESS/api/scenario/A/degrade" $who | Out-Null
    $raised = Wait-Until 240 { $s = Hyd01; if ($s.phase -eq 'RAISED') { $s } }
    if (-not $raised) { throw '쿨러 열화를 주입했지만 4분 안에 경보가 나지 않았습니다(감지 서비스 8092 확인)' }
    Record '경보' $true ("유온 {0} ℃ · 냉각 효율 {1} %" -f $raised.ts1, $raised.ce)

    $instance = Wait-Until 60 { foreach ($i in (Get-J "$PROCESS/api/instances?limit=20")) { if ($before -notcontains $i.proc_inst_id) { return $i } }; $null }
    if (-not $instance) { throw '경보가 났지만 1분 안에 처리 건이 열리지 않았습니다(처리 엔진 8080 확인)' }
    $pid_ = $instance.proc_inst_id
    Record '처리 건 열림' $true $pid_

    $outcome = Wait-Until 180 {
        $v = Get-J "$PROCESS/api/instances/$pid_"
        $diag = $v.workitems | Where-Object { $_.activity_id -eq 'task:diagnose' }
        $select = $v.workitems | Where-Object { $_.activity_id -eq 'task:select' -and $_.status -eq 'IN_PROGRESS' }
        if ($select) { '조치 선택까지 진행(원인 지식 있음) — 에이전트 단계 넷 완료, 사람 승인 대기' }
        elseif ($diag.status -eq 'PENDING' -and ($v.events | Where-Object { $_.event_type -eq 'task_deferred' })) { '원인 진단 보류(새 PC 정상: 원인 지식은 수업에서 적재) — 설비 · 수집 · 감지 · 처리 · 에이전트 · 지식 그래프 · 시계열 DB 연결 확인' }
    }
    if (-not $outcome) { throw '처리 건이 3분 안에 진단 결과(보류 또는 조치 선택)에 닿지 않았습니다(에이전트 8091 확인)' }
    Record '원인 진단' $true $outcome
}
catch { Record '쿨러 사건' $false $_.Exception.Message }
finally {
    # 쿨러 복구와 정리: 점검이 연 처리 건이 열린 채 남지 않게 한다
    try { Post-J "$PROCESS/api/scenario/A/restore" $who | Out-Null } catch { }
    if ($instance) {
        $pid_ = $instance.proc_inst_id
        $closed = Wait-Until 240 {
            $v = Get-J "$PROCESS/api/instances/$pid_"
            if ($v.instance.status -ne 'RUNNING') { return $v.instance.status }
            foreach ($w in @($v.workitems | Where-Object { $_.status -eq 'PENDING' -and $_.agent_mode })) {
                try { Post-J "$PROCESS/api/todolist/$($w.id)/close" @{ by = '설치 점검'; reason = '설치 점검이 연 처리 건 정리(쿨러 복구 뒤)' } | Out-Null } catch { }
            }
            $null
        }
        if ($closed) { Record '점검 처리 건 정리' $true "처리 건 종료($closed)" }
        else { Record '점검 처리 건 정리' $false "처리 건 $pid_ 이 아직 열려 있습니다. 포털 「처리 건」에서 확인하세요" }
    }
    try { Post-J "$PLANT/api/reset" @{} | Out-Null } catch { }
}

# 3. 5회차 실습 2: 중계 서버 연결
Say "`n[3/3] 5회차 실습 2 — 중계 서버 연결"
$labDir = [System.IO.Path]::Combine($repo, 'course', 'labs', 'offline', '05-2-cause-agent')
$envFile = Join-Path $labDir '.env'
if ($SkipLlm) { Record '중계 서버' $true '건너뜀(-SkipLlm)' }
elseif (-not (Test-Path $envFile)) { Record '중계 서버' $false "$envFile 이 없습니다" }
else {
    $lines = Get-Content $envFile -Encoding UTF8
    $vals = @{}
    foreach ($l in $lines) { if ($l -match '^\s*([A-Z_]+)\s*=\s*(.*)$') { $vals[$Matches[1]] = $Matches[2].Trim().Trim('"', "'") } }
    if (-not $vals['OPENAI_BASE_URL'] -or -not $vals['LLM_API_KEY']) {
        Say '실습 폴더 .env가 비어 있습니다. 수업용 중계 주소와 키를 붙여 넣으세요(건너뛰려면 그냥 Enter).' 'Yellow'
        $u = (Read-Host '중계 주소(…/v1)').Trim()
        $k = (Read-Host '중계 키(sk-…)').Trim()
        if ($u -and $k) {
            if ($u -notmatch '/v1/?$') { $u = $u.TrimEnd('/') + '/v1' }
            $vals['OPENAI_BASE_URL'] = $u; $vals['LLM_API_KEY'] = $k; $vals['LLM_MODEL'] = 'coding'
            $out = foreach ($l in $lines) {
                if ($l -match '^\s*(OPENAI_BASE_URL|LLM_API_KEY|LLM_MODEL)\s*=') { "$($Matches[1])=$($vals[$Matches[1]])" } else { $l }
            }
            [System.IO.File]::WriteAllLines($envFile, [string[]]$out, (New-Object System.Text.UTF8Encoding($false)))
            Say '실습 폴더 .env에 적었습니다. 이 PC를 이미지로 복제하면 모든 PC에 같은 키가 들어갑니다.' 'Yellow'
        }
    }
    if (-not $vals['OPENAI_BASE_URL'] -or -not $vals['LLM_API_KEY']) { Record '중계 서버' $true '건너뜀(.env 비어 있음 — 5회차 수업 때 적음)' }
    else {
        if (-not $vals['LLM_MODEL']) { $vals['LLM_MODEL'] = 'coding' }
        $body = @{ model = $vals['LLM_MODEL']; messages = @(@{ role = 'user'; content = 'Reply with exactly: OK' }); max_completion_tokens = 50 }
        try {
            $r = Invoke-RestMethod -Method Post -Uri ($vals['OPENAI_BASE_URL'].TrimEnd('/') + '/chat/completions') -Headers @{ Authorization = 'Bearer ' + $vals['LLM_API_KEY'] } `
                -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 5) -TimeoutSec 120
            Record '중계 서버' $true ("연결됨 · {0} · 답: {1}" -f $vals['LLM_MODEL'], ("$($r.choices[0].message.content)".Trim()))
        }
        catch {
            $code = $null; try { $code = [int]$_.Exception.Response.StatusCode } catch { }
            $why = switch ($code) { 401 { '키가 맞지 않거나 서버 쪽 키 문제' } 403 { 'LLM_MODEL 이름이 이 키에 허용되지 않음' } 404 { '주소가 맞지 않음(끝이 /v1인지)' } 429 { '서버가 잠시 바쁨 — 1분 뒤 다시' } default { $_.Exception.Message } }
            Record '중계 서버' $false "묻지 못했다($code): $why — 실습 폴더에서 python llm_client.py 로 자세한 문구를 볼 수 있다"
        }
    }
}

Show-Results
