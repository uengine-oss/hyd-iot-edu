## Git 브랜치 운영 (2026-10-23 사용자 확정, main 단일화)

- 작업 브랜치는 main 하나다. develop은 2026-10-23에 main으로 fast-forward한 뒤 폐기했다(로컬·원격 모두 삭제).
- 예외 둘은 그대로 둔다. `other-pc`는 다른 PC 작업용이며 main에 강의 영상·음성·자막을 더한 것이다. 문서·대본·도구는 main에서 고치고 other-pc는 main을 병합해 따라간다. other-pc에서 문서가 바뀌었으면 영상·음성 없이 그 변경만 main으로 가져온 뒤 다시 병합한다. 여러 PC 세션이 other-pc에 커밋하므로 커밋 전에 원격을 받아 병합하고(rebase · 강제 push 금지) 상대가 고친 내용을 덮어쓰지 않는다. `replay-mode`는 온라인용이다(키 없는 학생 PC에서 워커가 강사 촬영 때 저장한 AI 응답을 재생, 사용자 2026-10-23). main은 오프라인용이며 재생 코드를 넣지 않는다. 공통 수정은 main에서 하고 replay-mode는 main을 병합해 따라간다.
- 모든 새 작업은 main에서 이어간다. 그 밖의 작업 브랜치를 만들지 않는다.
- 기존 분기 이력은 archive/ 태그로 보존한다. 태그는 작업 브랜치가 아니다.

# hyd-iot-edu — 프로젝트 계약 (로컬·클라우드 공통)

## 시스템 수업 준비 재개 필독 (2026-10-26)

2026-10-27 이후 재개는 `문서/시스템/6_남은_일.md` 맨 앞 「다음 세션 인계 (2026-10-27)」부터 읽는다. 교대 인수인계 단일 시나리오, 강사 승인 자료·행동만 허용, 캐시·AI 비용 통제, 기존 검증과 미해결 범위가 정리돼 있다. 아래 2026-10-26 원문 근거는 재사용한다.

수업 준비(키 하나로 켜기 · 포털 실습 전수 점검 · ProcessGPT 대조 결함 처리)는 `문서/시스템/6_남은_일.md` 맨 앞 「다음 세션 인계 (2026-10-26)」가 진입점이다(사용자가 바로잡은 규칙 · 결과 · 남은 순서, 근거 원문 `문서/시스템/검증_기록/2026-10-26/인계_대화기록.md`).

## 교재 작업 재개 필독 (2026-10-23 최신)

진입점은 둘이다. 실전반 이론 재편 · 강의 영상은 `문서/교재/인계_영상과대본점검.md`, 실습 촬영(Notion · ego 등)은 `문서/교재/인계_5분샘플_제작검증.md`. 끝난 인계는 `문서/교재/근거/지난_인계/`에 있다.

기준은 `문서/교재/2_기준.md`(공통 원칙, 「두 과정의 공통 범위와 차이」, 상세 기준 위치표)와 `문서/교재/실전반_기준.md`(실전반 2~8회차 이론만 다른 점)다. 상태는 `3_현황.md`(공통 · 통합반 · 실전반), 사용자 원문은 `5_결정_기록.md`, 재개 순서는 `6_남은_일.md`. 아래 옛 기준 번호와 우선순위보다 이 최신 결정이 우선한다.

이 저장소에서 일하는 세션이 지키는 것이다. 클라우드에서는 `.claude/hooks/cloud-bootstrap.sh`가 세션 시작 때 환경을 준비한다.

## 1. 시작할 때 읽는 순서

문서는 `문서/` 한 곳에만 있다. 대화 요약이 끊겨도 이 폴더만 읽으면 이어갈 수 있어야 한다.

| 하려는 일 | 읽을 곳 |
|---|---|
| 교재(강의 덱 · 낭독 대본 · 강의 영상 · 실습 랩) | `문서/교재/1_목적과_방향.md`부터. 기준은 `문서/교재/2_기준.md` |
| 실습 영상(촬영 · 음성 · 합성 · 동기화) | `문서/교재/방법_ego_실습영상_촬영.md`(「실습 영상 제작 안내」) 한 문서부터, 이어서 `제작용/촬영/<도구>/촬영준비.md` |
| 시스템(포털 · 설비) | `문서/시스템/1_목적과_방향.md`부터. 기준은 `문서/시스템/2_기준.md`, 켜는 법은 `문서/시스템/4_켜고_돌리는_법.md` |

두 폴더 모두 문서 여섯 개가 같은 순서다: 1 목적과 방향, 2 기준, 3 현황, 4 만드는 법(켜고 돌리는 법), 5 결정 기록, 6 남은 일.
범위는 가장 뒤의 사용자 지시가 정한다. 기준 문서의 규칙은 근거 없이 바꾸지 않는다.

교재 작업의 최신 사용자 확정 기준은 `문서/교재/2_기준.md`다. 작업 전에 그 문서의 0-2번(현재 범위)과 「두 과정의 공통 범위와 차이」, `기준_이론덱.md` 29-2번(통합반 원 덱 · 실전반 압축판), `기준_이론대본.md` 39~41번(분량) · 52 · 97-1번(촬영 경계 · 발화)을 확인한다. 실전반 2~8회차 이론은 `실전반_기준.md`를 더한다. 기준을 기억한다고 가정하거나 옛 작업자 지시문의 고정 시간 규칙을 우선하지 않는다.

## 2. 기록

- 일이 끝날 때마다 해당 폴더의 `3_현황.md`와 `6_남은_일.md`를 고친다. 정해진 것은 `2_기준.md`에, 그 경위는 `5_결정_기록.md`에 적는다. 한 규칙은 한 곳에만 적는다.
- 문서를 새로 늘리지 않는다. 옛 지침, 작업 흔적, 쓰이지 않는 파일을 남기지 않는다.
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
- 실라버스는 사용자가 직접 쓴다(기준: `문서/교재/실라버스/피지컬AI_실라버스_최종본.xlsx`). 교재(PPTX)의 제목·화법·틀은 `문서/교재/2_기준.md`를 따른다(실라버스는 틀만 정한다). 덱 원고 폴더 안내는 `제작용/기존제작/decks/README.md`.
- 대본 길이 · 말하는 법은 `문서/교재/기준_이론대본.md`가 정본이다(39~41번 시간: 자연스러운 설명의 깊이를 우선하고 분량을 측정한다. 10분 하한·240분 맞추기는 적용하지 않으며 누적 차이는 기록한다. 98 · 98-1 · 100번 영어 · 수치 · 식별자). 길이는 `제작용/기존제작/tools/deck/대본시간.py`(분당 275음절)로 잰다.
- 실습 랩: 학생의 도구는 VS Code의 GitHub Copilot과 Codex이고, 랩의 틀은 `제작용/기존제작/labs/STRUCTURE.md`, 기준은 `문서/교재/기준_실습랩.md`(가이드 · 대본은 `기준_실습가이드.md` · `기준_실습대본.md`), 작업별 진입점은 `문서/교재/4_만드는_법.md`의 표, 상태는 `3_현황.md`다. 랩은 두 과정 한 벌이다.
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

통합 시험: `scripts/scenario_instance_test.py`(쿨러, `--worker`면 실제 워커 기대), `scripts/scenario_pump_fan_test.py`(펌프·팬·가림),
`scripts/scenario_test.py --quick`(레거시, `PROCESS_MODE=legacy`로 process 재기동 필요).
