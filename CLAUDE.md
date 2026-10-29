## 작업 종류별 진입점 — Claude·Codex 공통

사용자가 요청한 작업 종류에 맞는 정본을 읽는다. 아래 시스템 운영 규칙을 교재 제작 권한으로 확대하지 않는다.

교재 작업은 [기준_공통](문서/교재/기준_공통.md)부터 읽는다. Claude와 Codex가 같은 기준을 쓰며, 옛 요청문이나 샘플로 최신 결정을 되돌리지 않는다.

- **교재·실습·가이드·대본·영상:** [AGENTS.md](AGENTS.md) → [기준_공통](문서/교재/기준_공통.md) → G1 표가 정한 그 작업의 기준 하나(기준_이론덱 · 기준_대본 · 기준_실습랩 · 기준_촬영 · 기준_실습가이드). 촬영은 기준_촬영과 도구별 촬영준비를 읽는다. 인계 · 요청문은 레포에 두지 않는다(사용자 2026-10-28) — main은 깨끗하게 둔다 — 로컬 세션은 `.evidence/인계/`에서 이어받고, 클라우드 세션용 인계는 클라우드 전용 `other-pc` 브랜치에만 둔다.
- **시스템·포털·설비 개발:** 이 문서의 시스템 규칙과 `문서/시스템/6_남은_일.md` 맨 앞 현재 인계. 교재 작업에서 포털 로직·DB·서비스를 임의 변경하지 않는다.

교재 상세 규칙은 이 파일에 복제하지 않는다. 과정별 공통/차이, 촬영·윤문·가이드·게시 규칙은 위 담당 정본이 우선하며 같은 판본의 검증 근거를 재사용한다. Claude에서도 도구·로컬 파일·ego 사용 가능 여부는 실제 환경에서 확인한다. 다른 PC의 `.evidence`가 clone에 들어 있다고 가정하지 않는다. 문서로 해결되는 결정을 사용자에게 반복 질문하지 않는다.

## 최우선 작업 원칙 — 대화 연속성·중복 금지·극한 효율 (2026-10-27 사용자 재강조)

- **기존 대화의 확정 결정·완료 증거·실패 원인·미완료를 이어받고, 이미 끝낸 동일 작업은 반복하지 않는다. 안 했거나 완료되지 않은 일만 한다.** 시스템 작업의 재개 진입점은 `문서/시스템/6_남은_일.md` 맨 앞 현재 요약이며 상세 증거는3_현황, 확정 결정은2_기준/5_결정_기록이다. 오래된 진행 기록은 현재 작업 목록이 아니다.
- 첫 조회에서 현재 git/실행 상태와 인계의 차이만 확인한다. 이미 읽고 검증한 동일 판본의 원본 조사·전체 시험·AI 호출을 다시 하지 않는다. 변경·새 실패 때문에 새로 필요한 부분만 근거를 명시해 확인한다.
- **완료 조건에 직접 기여하는 미완료 묶음 하나를 끝낸 뒤 다음으로 간다.** 결과가 쉬운 주변 시험·추측성 감사·일반 유지보수로 최종 통합 검증을 미루지 않는다. 사용자 답변이 필요한 일과 독립적으로 가능한 일은 구분하되, 대기 시간을 채우려고 새 일을 만들지 않는다.
- 도구 조회는 관련 파일/구간에 한정하고 독립 조회는 묶는다. 대량 출력·추측한 경로의 반복 실패·같은 상태의 잦은 폴링·반복 보고를 피한다. 전체 빌드/시험/배포·세 브랜치 동기화는 의미 있는 작업 묶음 또는 인계 시점에 모아서 한다.
- 유료 실험은 목적·성공 기준·상한을 정하고, 실패 시 같은 조건을 재실행하지 않는다. 기존 결과·trace를 먼저 분석/교정한다. 실행 중 상태·결과·진단 자료를 보존하여 새 세션이 재생성 없이 이어받게 한다.
- 인계에는 현재 커밋/미반영 변경/운영 판본, **재실행 금지 목록**, 정확한 남은 실패와 다음 행동·의존성·증거 위치를 적는다. 완료/구현만 완료/실패/미확인을 섞지 않는다. 목표를 축소하거나 부분 성공을 전체 완료로 표시하지 않는다.

## Git 브랜치 운영 (2026-10-23 사용자 확정, main 단일화)

- 작업 브랜치는 main 하나다. develop은 2026-10-23에 main으로 fast-forward한 뒤 폐기했다(로컬·원격 모두 삭제).
- 예외는 `other-pc` 하나다. `other-pc`는 다른 PC 작업용이며 main에 강의 영상·음성·자막을 더한 것이다. 문서·대본·도구는 main에서 고치고 other-pc는 main을 병합해 따라간다. other-pc에서 문서가 바뀌었으면 영상·음성 없이 그 변경만 main으로 가져온 뒤 다시 병합한다. 여러 PC 세션이 other-pc에 커밋하므로 커밋 전에 원격을 받아 병합하고(rebase · 강제 push 금지) 상대가 고친 내용을 덮어쓰지 않는다. AI 응답 재생(키 없는 PC에서 워커가 강사 촬영 때 저장한 응답을 재생, `AI_MODE=auto`)은 2026-10-28 사용자 지시로 main에 병합했고 `replay-mode` 브랜치는 `archive/replay-mode` 태그로만 보존한다. 재생 저장분도 main에 커밋한다.
- 모든 새 작업은 main에서 이어간다. 그 밖의 작업 브랜치를 만들지 않는다.
- 기존 분기 이력은 archive/ 태그로 보존한다. 태그는 작업 브랜치가 아니다.

# hyd-iot-edu — 프로젝트 계약 (로컬·클라우드 공통)

## 시스템 수업 준비 재개 필독 (2026-10-26)

재개는 `문서/시스템/6_남은_일.md`(지금 위치 · 다음 행동 · 재실행 금지 · 열린 항목)부터 읽는다. 2026-10-28까지의 날짜별 인계 원문(10-26 · 10-27 절 포함)은 `문서/시스템/검증_기록/지난기록/`에 보관돼 있고 필요한 줄만 찾아 읽는다(근거 원문 `문서/시스템/검증_기록/2026-10-26/인계_대화기록.md`).

이 저장소에서 일하는 세션이 지키는 것이다. 클라우드에서는 `.claude/hooks/cloud-bootstrap.sh`가 세션 시작 때 환경을 준비한다.

## 1. 시작할 때 읽는 순서

문서는 `문서/` 한 곳에만 있다. 대화 요약이 끊겨도 이 폴더만 읽으면 이어갈 수 있어야 한다.

| 하려는 일 | 읽을 곳 |
|---|---|
| 교재(강의 덱 · 낭독 대본 · 강의 영상 · 실습 랩) | 맨 위 교재 진입 순서(`문서/교재/기준_공통.md` G1). 현재 인계는 로컬 `.evidence/인계/` |
| 실습 영상(촬영 · 음성 · 합성 · 동기화) | `문서/교재/기준_촬영.md`부터, 이어서 `제작용/촬영/<도구>/촬영준비.md` |
| 시스템(포털 · 설비) | `문서/시스템/1_목적과_방향.md`부터. 기준은 `문서/시스템/2_기준.md`, 켜는 법은 `문서/시스템/4_켜고_돌리는_법.md` |

시스템 폴더는 문서 여섯 개(1 목적과 방향, 2 기준, 3 현황, 4 켜고 돌리는 법, 5 결정 기록, 6 남은 일)다. 교재 폴더는 기준 문서 여섯(`기준_공통` · `기준_이론덱` · `기준_대본` · `기준_실습랩` · `기준_촬영` · `기준_실습가이드`)과 사실표 · 실라버스만 둔다(진행 기록은 main 밖).
범위는 가장 뒤의 사용자 지시가 정한다. 기준 문서의 규칙은 근거 없이 바꾸지 않는다.

교재 기준의 읽기 범위와 동일 판본 재사용은 `문서/교재/기준_공통.md` G1을 따른다.

## 2. 기록

- 교재: main에는 정본(기준 · 산출물 · 제작 도구)만 둔다. 진행 기록 · 인계 · 결정 경위는 main에 두지 않는다(로컬 `.evidence/`, 클라우드 세션은 `other-pc`, 사용자 2026-10-28). 정해진 규칙은 해당 기준 문서의 그 문장을 고친다.
- 시스템: 일이 끝날 때마다 `문서/시스템/3_현황.md`와 `6_남은_일.md`를 고치고, 정해진 것은 `2_기준.md`에, 그 경위는 `5_결정_기록.md`에 적는다. 한 규칙은 한 곳에만 적는다.
- 같은 규칙의 사본을 늘리지 않고 담당 정본을 갱신한다. 폐기된 지시는 과거 기록으로 구분하고 현재 인계에서 연결한다. 기존 미커밋·실행 증거·실패 원본·확정 산출물을 이 규칙을 이유로 삭제하지 않는다.
- 실행 증거는 `.evidence/`에 남긴다(저장소에 올리지 않는다). 실패는 파일과 줄로 적는다.

## 3. 시스템 규칙

- **fable 모델을 쓰지 않는다**(사용자 지시 2026-10-10). 메인 세션 · 서브에이전트 · 워커 모두 해당한다. 서브에이전트는 `opus`로 지정한다.

- **배속 기본 20배(`TIME_SCALE=20`).** 가상 설비라 수업·실습·검사 모두 20배속이다. "1~2배속 권장" 문구를 쓰지 않는다.
  20배속에서 흔들리는 코드는 배속 기준으로 고친다. 더 높은 배속은 가짜 실패를 만드니 쓰지 않는다.
  배율은 plant-sim·detector·process·agent에 함께 적용한다(`/api/time_scale`은 plant 물리만 바꾼다). 바꿀 때는 `문서/시스템/참조/RUNBOOK.md` 표를 따른다.
- **회귀·라이브 검사기(run_regression·probe_*)가 도는 동안 `docker compose build/up/restart` 금지.**
  compose는 의존 서비스가 바뀌면 process를 재시작시켜 검사가 `RemoteDisconnected`로 끊긴다.
  배포는 검사 전에 끝내고 `docker inspect hyd-iot-edu-process-1 --format '{{.State.StartedAt}} {{.RestartCount}}'`로 안정을 확인한다.
  에러 없이 조용히 재시작했으면 커널 OOM을 의심한다(로컬: `wsl -d docker-desktop -e sh -c "dmesg | grep -i oom"`).
- 20배속 레거시 회귀 전에는 호스트 워커를 모두 멈춘다(워커가 에이전트 작업을 가져간다).
- 완주·E2E 검증은 학생 대역 1명·인스턴스 1건·1회. 학생 수만큼 동시에 돌리지 않는다.
- AI 워커(`agent-worker` 컨테이너)와 에이전트용 MCP(enterprise-mcp · -maint · -purchase · dmn-mcp)는 프로필 `cliagents`이고, 강의 배포본 `.env.example`의 `COMPOSE_PROFILES`에 들어 있다(2026-10-25). 워커의 모델 호출은 `.env`의 `LLM_API_KEY` · `LLM_RELAY_URL` · `LLM_MODEL`로 강의 중계에 간다(`문서/시스템/2_기준.md` 6절). 호스트 워커(`run_worker_host.sh`)는 개발용이며 컨테이너 워커와 함께 돌리지 않는다(워커는 하나).
- Supabase 로컬: `cd it/supabase && supabase start`(PostgreSQL 15, 포트 54322). `supabase stop --no-backup`은 볼륨을 지운다.
- 컨테이너·Supabase·워커는 스스로 켜고 끄고, 시험 잔재(임시 DB·시험 인스턴스)는 스스로 정리한다. 끈 뒤 실제로 꺼졌는지 확인한다.
  프로젝트 데이터 볼륨, 원자료, 강사 손질본 삭제와 원격 push·결제는 묻는다.

## 4. 내용 규칙

- 시나리오·BPMN·온톨로지는 저장소에 있는 이름만 쓴다. 작업 전에 `문서/시스템/1_목적과_방향.md` 3절과 코드(agentsvc·procsvc·entsim·seed)를 먼저 읽는다.
  정본 위치: `문서/시스템/참조/ontology/schema-v2.md`, `it/neo4j/v2/instances.cypher`, 템플릿 `it/neo4j/templates/`.
  온톨로지는 객체 모델(클래스·속성·관계)이다. 프로세스 설명은 온톨로지가 아니다.
- 해피패스·구세주 데이터 금지: 사례마다 손익으로 지는 대안과 실제로 밟는 비해피 가지가 있어야 한다.
- 승인 전 에이전트는 조회·계산·보고서만 한다. 사람 승인 1회 뒤 process가 실행한다.
- 업무 흐름은 "사건 한 건 = 프로세스 인스턴스 하나, 그 안을 task 단위(시스템·에이전트·규칙·사람·현장)"로 쓴다.
- 시스템 문서는 구조와 데이터 리니지(출생→변환→저장→소비, 실패·분기)가 목적이다. 수치 표보다 구조 정확성을 우선한다.
- 온톨로지·스키마 결과를 사용자에게 보고할 때는 전문 용어에 비유 한 줄과 "사용자가 스스로 판정할 체크 질문"을 같이 준다.
- 참고 레포와 다른 곳은 ① 실제 결함인가 ② 회의·계약 요구를 못 채우는가만 묻는다. 둘 다 아니면 "차이 있음, 유지"로 기록한다.
- 포털 UI 추가는 추가한 것만 다듬는다. 기존 컴포넌트·간격 재사용, 카드 하나에 행동 1개, 보조 정보는 접기. 판정 기준은 "학생이 10초 안에 할 일을 찾는가".
- 실라버스 정본은 `문서/교재/실라버스/피지컬AI_실라버스_최종본.xlsx`다. 사용자가 요청한 편성 수정은 승인된 범위에서 수행하며, 일반 교재 제작에서는 임의로 편성을 바꾸지 않는다. 교재(PPTX)의 제목·화법·틀은 `문서/교재/기준_이론덱.md`를 따른다.
- 모든 교재의 범위와 시간은 `문서/교재/기준_공통.md` 맨 앞 「범위와 시간」이 정본이다(실라버스 그 행의 문장과 배정 시간에서 시작). 대본의 말하는 법은 `문서/교재/기준_대본.md`. 길이는 실제 강사 복제 음성으로 맞춘 계수 `제작용/촬영/시간계수.json` 하나로 잰다(이론 대본 `제작용/기존제작/tools/deck/대본시간.py`, 실습 큐 `제작용/촬영/시간계산.py`, 오프라인 덱 `제작용/오프라인/decks/시간.py`).
- 실습 랩: 학생의 도구는 VS Code의 GitHub Copilot과 Codex이고, 기준은 `문서/교재/기준_실습랩.md`(그 L1 순서가 단계마다 기준_대본 · 기준_촬영 · 기준_실습가이드를 부른다), 새 코드 이름은 `제작용/기존제작/labs/STRUCTURE.md`다. 두 과정의 공통/차이는 `문서/교재/기준_공통.md` G2를 따른다. 모든 랩을 한 벌로 통일하지 않는다.
- 인제스천 품질·규모 주장은 실제 매뉴얼 실측(`.evidence/realman/`)에 연결한다. 실물 PDF는 저작물이라 레포 픽스처로 넣지 않는다.

## 5. 환경 (OS별)

이 표에 없는 로컬 macOS(colima)는 `문서/시스템/4_켜고_돌리는_법.md`가 기준이다(파이썬 `.venv` 3.12, `host_libpq.sh` 불필요, 워커 멈춤은 `pkill -f worker.main`).

| | 로컬 Windows | 클라우드 Linux |
|---|---|---|
| Python | `.venv314/Scripts/python.exe`(공식 3.14). uv 파이썬은 Smart App Control이 막는다 | `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt` |
| 단위 시험 | `. scripts/host_libpq.sh; PYTHONUTF8=1 .venv314/Scripts/python -m pytest -q` (서명된 libpq를 PATH 앞에 둬 DLL 차단을 피한다) | `.venv/bin/python -m pytest -q` (host_libpq.sh 불필요) |
| 워커 | `bash scripts/run_worker_host.sh` (`CLIAGENTS_DEFAULT_CLI=claude-code`). 멈출 때는 PowerShell `Get-CimInstance Win32_Process \| ? CommandLine -like '*worker.main*'`로 찾아 `taskkill //PID //F`, 포트 8097/8098이 내려갔는지 확인. 워커 1개가 python 2개로 보인다 | `bash scripts/run_worker_host.sh`, 멈출 때 `pkill -f worker.main` 후 포트 확인 |
| 로그 인코딩 | 워커 로그에 cp949가 섞인다. 바이트로 읽어 `errors='replace'`로 디코드 | UTF-8 |
| Docker | Docker Desktop(메모리 4 GB 이상). 꺼져 있으면 직접 켜고 `docker info` 응답을 기다린다 | Docker·`docker compose` 기본 설치(VM 약 4 vCPU·16 GB). `docker info`가 안 되면 `dockerd`부터 켠다. 컨테이너는 세션마다 새로 띄운다(이미지는 환경 캐시에 남음, 느리면 환경 설정 스크립트에 `docker compose pull`). 메모리가 모자라 멈추면 그 사실을 보고한다 |

클라우드 `.env`: 레포에 없다(.gitignore). 세션 시작 훅(`.claude/hooks/cloud-env.sh`)이 `.env.example`로 만들고,
LLM은 LiteLLM 중계(모델 `coding`) 하나이고 GPU는 없다(`문서/시스템/2_기준.md` 6절). LLM 키·주소(`OPENAI_API_KEY`·`LLM_API_KEY`·`OPENAI_BASE_URL`·`LLM_MODEL`·`LLM_PROVIDER`)는 claude.ai/code 환경 설정의
환경변수로 들어온다(compose는 `${VAR:-기본값}`만 쓰므로 셸 환경변수가 우선). LLM 서버 도메인은 환경의 네트워크 허용 목록에 있어야 한다.
클라우드 `.env` 값: 예시 파일이 곧 강의 배포본이다(`PROCESS_MODE=instance` · `ENTERPRISE_BACKEND=supabase` · `AGENT_BRIDGE=off` · `cliagents` 포함, 빈칸은 `LLM_API_KEY` 하나). core 회귀만 `AGENT_BRIDGE=legacy`로 바꿔 돌린다.
클라우드 셸 변수 주의(2026-10-25 실측): 이 환경 설정은 셸에 `AGENT_BRIDGE=legacy` · `COMPOSE_PROFILES`(cliagents 없음) · `SUPABASE_DSN`(54322 고정) · `LLM_API_KEY` 등을 내보내고 compose는 셸 값을 `.env`보다 우선한다. 강의실 조건을 재현할 때는 그 변수들을 `unset`하고 시작 스크립트를 돌린다(안 지우면 포트가 옮겨진 PC 시험에서 업무 시스템이 옛 DB 포트로 붙어 멈춘다). 시작 스크립트의 Python 3.14.7 요구는 강의실 기준이라 클라우드(uv 최신 3.14.6)는 그 한 줄만 낮춘 임시 사본으로 돌리고 지운다.
클라우드 이미지 받기: Docker Hub가 429(익명 한도)를 내면 `mirror.gcr.io/<이름>`(공식 이미지는 `library/<이름>`)으로 받아 원래 이름으로 `docker tag`한다.
클라우드 Supabase: `cd it/supabase && npx -y supabase start`로 뜬다(2026-10-08 실측, 마이그레이션 25개·seed 적용, ghcr 403이 몇 번 나도 재시도로 통과).
클라우드 이미지 빌드: 에이전트 프록시가 TLS를 다시 서명하므로 빌드 안 `pip`가 `CERTIFICATE_VERIFY_FAILED`로 실패한다. 세션마다 한 번, 베이스 이미지에 프록시 CA를 넣는다(레포 Dockerfile은 그대로):
`docker tag python:3.12-slim python:3.12-slim-orig` 뒤 `FROM python:3.12-slim-orig` + CA 사본을 `/usr/local/share/ca-certificates/`에 두고 `/etc/ssl/certs/ca-certificates.crt`에 덧붙임 + `ENV PIP_CERT=… SSL_CERT_FILE=… REQUESTS_CA_BUNDLE=… CURL_CA_BUNDLE=… NODE_EXTRA_CA_CERTS=<CA 사본>`으로 `docker build -t python:3.12-slim`(워커 이미지의 curl · npm까지 된다).
CA 사본은 전체 묶음 `/root/.ccr/ca-bundle.crt`를 쓴다. `agent-proxy-ca.crt` 한 장만 넣으면 빌드 안 `pip`가 여전히 `self-signed certificate in certificate chain`으로 실패한다(2026-10-28 실측).
클라우드 Python Playwright: `.venv`의 판본이 미리 설치된 브라우저(`/opt/pw-browsers/*-1243`)와 빌드 번호가 다르다. 설치하지 말고 기대 번호 이름으로 심볼릭 링크를 둔 폴더를 `PLAYWRIGHT_BROWSERS_PATH`로 준다(예: `/tmp/pwb/chromium_headless_shell-1248 → /opt/pw-browsers/chromium_headless_shell-1243`).
클라우드 시작 스크립트의 실습랩 키 동기화는 저장소에 추적된 `course/labs/offline/05-2-cause-agent/.env`에 키를 쓴다. 시작이 끝나면 `git checkout -- 그 파일`로 되돌리고 절대 스테이징하지 않는다.

통합 시험: `scripts/scenario_instance_test.py`(쿨러, `--worker`면 실제 워커 기대), `scripts/scenario_pump_fan_test.py`(펌프·팬·가림),
`scripts/scenario_test.py --quick`(레거시, `PROCESS_MODE=legacy`로 process 재기동 필요).
