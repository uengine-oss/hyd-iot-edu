# 강사용: LiteLLM 중계키를 발급하고 실제로 답이 오는지 확인한다. 강사 PC에서 실행한다(학교 PC에서 실행하지 않는다 —
# 마스터 키를 쓰려면 gcloud 로그인이 필요하고, 학교 PC는 이미지로 복제되기 때문이다).
#
#   powershell -ExecutionPolicy Bypass -File scripts\relay_key.ps1                       # 반 공용 키 하나(별칭 gnu-class)
#   powershell -ExecutionPolicy Bypass -File scripts\relay_key.ps1 -Alias student-01 -Budget 5 -Duration 30d
#   powershell -ExecutionPolicy Bypass -File scripts\relay_key.ps1 -Verify -Key sk-…        # 이미 받은 키가 되는지만 확인
#
# 서버 주소와 GCP 프로젝트는 공개 저장소에 두지 않는다. 환경변수 HYD_LITELLM_URL · HYD_GCP_PROJECT에서 읽고, 없으면 묻는다.
# 마스터 키는 Secret Manager에서 그때그때 꺼내 쓰고 화면 · 파일에 남기지 않는다. 발급한 키는 이때 한 번만 전체가 보인다.
param(
    [string]$Url = $env:HYD_LITELLM_URL,
    [string]$Project = $env:HYD_GCP_PROJECT,
    [string]$Secret = 'knu-litellm-master-key',
    [string]$Alias = 'gnu-class',
    [string]$Duration = '30d',
    [double]$Budget = 10,
    [switch]$Verify,
    [string]$Key
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not $Url) { $Url = (Read-Host '중계 서버 주소(https://…run.app)').Trim() }
$Url = ($Url.TrimEnd('/') -replace '/v1$', '')

function Test-Key($sk) {
    # 학생 PC의 llm_client.py와 같은 요청: model=coding, max_completion_tokens(이 모델은 max_tokens를 400으로 거절한다)
    $body = @{ model = 'coding'; messages = @(@{ role = 'user'; content = 'Reply with exactly: OK' }); max_completion_tokens = 50 } | ConvertTo-Json -Depth 5
    $t = Get-Date
    $r = Invoke-RestMethod -Method Post -Uri "$Url/v1/chat/completions" -Headers @{ Authorization = "Bearer $sk" } -ContentType 'application/json' -Body $body -TimeoutSec 120
    "답: $("$($r.choices[0].message.content)".Trim()) · $([math]::Round(((Get-Date) - $t).TotalSeconds, 1)) 초"
}

if ($Verify) {
    if (-not $Key) { $Key = (Read-Host '확인할 키(sk-…)').Trim() }
    try { Write-Host "연결됨 · coding · $(Test-Key $Key)" -ForegroundColor Green }
    catch { Write-Host "실패: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
    exit 0
}

if (-not $Project) { $Project = (Read-Host 'GCP 프로젝트 ID').Trim() }
$gcloud = (Get-Command gcloud -ErrorAction SilentlyContinue).Source
if (-not $gcloud) { $gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' }
if (-not (Test-Path $gcloud)) { throw 'gcloud가 없습니다. Google Cloud SDK를 설치하고 gcloud auth login 으로 로그인한 뒤 다시 실행하세요' }

$master = (& $gcloud secrets versions access latest --secret=$Secret --project=$Project).Trim()
if (-not $master) { throw "Secret Manager에서 $Secret 을 읽지 못했습니다(gcloud 로그인 · 권한 확인)" }
$H = @{ Authorization = "Bearer $master" }

$body = @{ key_alias = $Alias; models = @('coding', 'embedding'); duration = $Duration; max_budget = $Budget; allowed_routes = @('llm_api_routes') } | ConvertTo-Json
$new = Invoke-RestMethod -Method Post -Uri "$Url/key/generate" -Headers $H -ContentType 'application/json' -Body $body
$master = $null
if (-not $new.key) { throw '발급 응답에 키가 없습니다' }

Write-Host "`n발급함: 별칭 $Alias · 모델 coding, embedding · 기한 $Duration · 한도 `$$Budget · 모델 호출만 허용" -ForegroundColor Cyan
try { Write-Host "확인: 연결됨 · coding · $(Test-Key $new.key)" -ForegroundColor Green }
catch { Write-Host "확인 실패: $($_.Exception.Message) — 키는 발급됐습니다. 잠시 뒤 -Verify로 다시 확인하세요" -ForegroundColor Yellow }

Write-Host "`n학생 PC 실습 폴더(course\labs\offline\05-2-cause-agent\.env)에 넣을 세 줄. 이 키는 지금 한 번만 전체가 보입니다:" -ForegroundColor White
Write-Host "OPENAI_BASE_URL=$Url/v1"
Write-Host "LLM_API_KEY=$($new.key)"
Write-Host "LLM_MODEL=coding"
