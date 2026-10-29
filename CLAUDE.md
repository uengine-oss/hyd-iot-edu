# hyd-iot-edu — 프로젝트 계약 (이 PC의 저장소 루트에 둔다 · workspace 브랜치에 백업 · main에는 없다)

## 0. 무엇이든 시키면

스킬 `hyd-task`의 순서를 밟는다: **작업 폴더 → 읽을 문서 하나 → 만들기 · 검사 → 제자리에 넣기(최신 하나만) → 두 브랜치 동기화 → 작업 폴더 정리.** 세션이 열리면 훅(`.claude/hooks/작업안내.sh`)이 구조와 열린 작업 폴더를 보여 준다. 열린 작업이 있으면 그 폴더의 `스펙.md` · `기록.md`부터 읽고 잇는다.

- 기존 대화의 확정 결정 · 완료 증거 · 실패 원인을 이어받고, 끝낸 일은 반복하지 않는다. 첫 조회는 git · 실행 상태와 작업 폴더 기록의 차이만 본다.
- 완료 조건에 직접 기여하는 묶음 하나를 끝낸 뒤 다음으로 간다. 유료 실행은 목적 · 성공 기준 · 상한을 정하고, 실패한 같은 조건을 재실행하지 않는다.
- 안 쓰는 것은 적대적으로 쳐낸다 — 지금 수업 · 개발에 쓰이지 않거나 최신 판이 따로 있으면 지운다(지운 것은 git 이력에 있다). 같은 사실은 한 곳에만 쓰고 나머지는 가리킨다.

## 1. 구조 — 어디에 무엇이 있나

| 자리 | 무엇 | 브랜치 |
|---|---|---|
| `README.md` · `compose*.yaml` · `.env.example` · 설치 · 시작 · 끄기 · 점검 실행 파일 · `scripts/`(실행 파일이 부르는 것만) · `it/` `ot/` `dmz/` `common/` · `문서/시스템/참조/수업_문서_원문/` | 학생이 clone해 실행하는 것 — 코드 · 프롬프트 · 설정 · 코드가 읽는 수업 데이터. 사람용 문서는 루트 README 하나 | main |
| `workspace/README.md` | **하려는 일 → 읽을 문서 하나** 색인(진입 표는 여기 한 곳) | workspace |
| `workspace/강의제작/지침/` | 산출물 문서 여섯(실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드) · 사실표 · 설계서 | workspace |
| `workspace/강의제작/산출물/` | 완성본 최신 판만(과정별 이론 · 이론_오프라인 · 실습, 영상, 실라버스 엑셀) | workspace |
| `workspace/강의제작/제작도구/` | 다시 만들 재료(원고 · 구성 · 큐 · 촬영도구 · 음성 캐시 · 촬영준비 · 검사기) | workspace |
| `workspace/개발/` | 시스템 개발용 — `문서/`(RUNBOOK · 재생모드 · UIUX_PLAN · ontology), `scripts/`(통합 시험 · 생성기 · 점검기 · 개발 워커) | workspace |
| `workspace/동기화.py` · `secret_scan.py` · `requirements-dev.txt` | 두 브랜치 동기화 · 작업 폴더 시작 · 정리 · 키 검사 · 개발 의존성 | workspace |
| `.claude/` · `CLAUDE.md` · `AGENTS.md` | Claude · Codex가 루트에서 읽는 규칙 · 스킬 · 훅 | workspace |
| `작업/<YYYY-MM-DD>_<제목>/` | 진행 중 작업 하나(`스펙.md` · `기록.md` · 원본 · 임시 출력). `작업/촬영/<도구>/` 녹화 원본, `작업/_로컬/` 공개 금지 개인 자료. 저장소 밖에 사본 clone · 결과 폴더를 따로 만들지 않는다 | 어디에도 안 올림 |
| `.env` · `.venv314/` | 이 PC 전용 | 어디에도 안 올림 |

## 2. 브랜치와 동기화

- 브랜치는 main · workspace 둘뿐이다(다른 브랜치 · 태그를 만들지 않는다). main은 `.gitignore`로 `workspace/` · `작업/` · 루트 작업 파일을 무시한다. workspace는 main과 이력을 공유하지 않고 병합하지 않는다.
- 동기화는 `PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/동기화.py` 하나로 한다 — `commit "메시지" [main 경로 …]`(workspace = 그 시점 모습 그대로, main = 준 경로만) → `push`(두 브랜치 키 검사 0일 때만, 강제 push 없음). 받기는 `pull`. 사용법 전부는 그 파일 머리에 있다.
- 노션 · 학생 링크는 커밋 고정 주소라 이력을 다시 쓰거나 브랜치를 지우지 않는다. 공개 저장소다 — 키 · 개인 정보 · 실물 매뉴얼 PDF를 어느 브랜치에도 올리지 않는다.

## 3. 기록

- 진행 · 결정 · 남은 일은 그 작업 폴더의 `기록.md` 하나에 지금 상태만 고쳐 쓴다(덧붙여 쌓지 않는다). 확정되면 최종본은 산출물로 바꿔 끼우고, 재료는 제작도구로 옮기고, 동기화한 뒤 `동기화.py 정리 --실행`으로 폴더째 지운다.
- 정해진 규칙은 그 규칙이 들어간 산출물 문서마다 그 자리를 다시 써서 합친다 — 덧붙이기 · 문서 안 중복 · 문서 사이 충돌 · 찌꺼기 0. 고친 뒤 `workspace/강의제작/제작도구/검사/재편검사.py` 오류 0.
- 실패는 파일:줄로 적는다. 실행한 것만 「됐다」고 쓰고, 안 잰 것은 미검증으로 남긴다.

## 4. 시스템 규칙

- **fable 모델을 쓰지 않는다**(사용자 지시 2026-10-10). 메인 세션 · 서브에이전트 · 워커 모두. 서브에이전트는 `opus`.
- **배속 기본 20배(`TIME_SCALE=20`).** 가상 설비라 수업 · 실습 · 검사 모두 20배속이다. "1~2배속 권장" 문구를 쓰지 않는다. 20배속에서 흔들리는 코드는 배속 기준으로 고친다. 배율은 plant-sim · detector · process · agent에 함께 적용한다(`/api/time_scale`은 plant 물리만 바꾼다). 바꿀 때는 `workspace/개발/문서/RUNBOOK.md` 표를 따른다.
- **통합 시험(`workspace/개발/scripts/scenario_*`)이 도는 동안 `docker compose build/up/restart` 금지.** 의존 서비스가 바뀌면 process가 재시작돼 시험이 `RemoteDisconnected`로 끊긴다. 배포는 시험 전에 끝내고 `docker inspect hyd-iot-edu-process-1 --format '{{.State.StartedAt}} {{.RestartCount}}'`로 안정을 확인한다. 에러 없이 조용히 재시작했으면 커널 OOM을 의심한다(`wsl -d docker-desktop -e sh -c "dmesg | grep -i oom"`). 통합 시험 전에는 호스트 워커를 멈춘다(워커가 에이전트 작업을 가져간다).
- 완주 · E2E 검증은 학생 대역 1명 · 인스턴스 1건 · 1회. 학생 수만큼 동시에 돌리지 않는다.
- AI 워커(`agent-worker` 컨테이너)와 에이전트용 MCP(enterprise-mcp · -maint · -purchase · dmn-mcp)는 프로필 `cliagents`이고 `.env.example`의 `COMPOSE_PROFILES`에 들어 있다. 시스템 안의 모든 AI(에이전트 · 질문 · 문서 인제스천)는 강의 중계 LiteLLM(GCP Cloud Run, 키별 비용 한도 · 가장 싼 모델, 첫 요청은 콜드스타트로 느림 — 의도)으로 간다. 워커 CLI는 키를 받지 않고 process의 로컬 중계 관문(`procsvc/course_model.py`, 작업에 묶인 토큰 · PC당 호출 상한)을 거치며, process가 `.env`의 `LLM_API_KEY` · `LLM_RELAY_URL`로 중계를 부른다. 학생 바이브 코딩은 각자 Codex 계정이라 시스템과 별개다. 호스트 워커(`workspace/개발/scripts/run_worker_host.sh`)는 개발용이며 컨테이너 워커와 함께 돌리지 않는다(워커는 하나).
- AI 응답 재생과 저장분(`it/agent-worker/replay/`)은 main에 있다. 시작.bat(`scripts/start_all.sh`)이 `.env`의 `LLM_API_KEY`로 `AI_MODE`를 적는다: 키 있음 live, 없음 replay(강사 저장 응답). 저장은 `bash workspace/개발/scripts/record_replay.sh`(동작 · 규칙은 `workspace/개발/문서/재생모드.md`).
- Supabase 로컬: `cd it/supabase && supabase start`(PostgreSQL 15, 포트 54322). `supabase stop --no-backup`은 볼륨을 지운다.
- 컨테이너 · Supabase · 워커는 스스로 켜고 끄고, 시험 잔재(임시 DB · 시험 인스턴스)는 스스로 정리한다. 끈 뒤 실제로 꺼졌는지 확인한다. 프로젝트 데이터 볼륨 · 원자료 · 강사 손질본 삭제와 결제는 묻는다.

## 5. 내용 규칙

- 시나리오 · BPMN · 온톨로지는 저장소에 있는 이름만 쓴다. 작업 전에 코드(agentsvc · procsvc · entsim · seed)를 먼저 읽는다. 정본 위치: `workspace/개발/문서/ontology/schema-v2.md`, `it/neo4j/v2/instances.cypher`, 템플릿 `it/neo4j/templates/`. 온톨로지는 객체 모델(클래스 · 속성 · 관계)이다. 프로세스 설명은 온톨로지가 아니다.
- 해피패스 · 구세주 데이터 금지: 사례마다 손익으로 지는 대안과 실제로 밟는 비해피 가지가 있어야 한다.
- 승인 전 에이전트는 조회 · 계산 · 보고서만 한다. 사람 승인 1회 뒤 process가 실행한다.
- 업무 흐름은 "사건 한 건 = 프로세스 인스턴스 하나, 그 안을 task 단위(시스템 · 에이전트 · 규칙 · 사람 · 현장)"로 쓴다.
- 온톨로지 · 스키마 결과를 사용자에게 보고할 때는 전문 용어에 비유 한 줄과 "사용자가 스스로 판정할 체크 질문"을 같이 준다.
- 참고 레포와 다른 곳은 ① 실제 결함인가 ② 회의 · 계약 요구를 못 채우는가만 묻는다. 둘 다 아니면 "차이 있음, 유지"로 기록한다.
- 포털 UI 추가는 추가한 것만 다듬는다(`workspace/개발/문서/UIUX_PLAN.md`). 기존 컴포넌트 · 간격 재사용, 카드 하나에 행동 1개, 보조 정보는 접기. 판정 기준은 "학생이 10초 안에 할 일을 찾는가".
- 실라버스 정본은 `workspace/강의제작/산출물/실라버스/피지컬AI_실라버스_최종본.xlsx`다. 사용자가 요청한 편성 수정은 승인된 범위에서 수행하며, 일반 교재 제작에서는 편성을 바꾸지 않는다. 모든 교재의 범위와 시간은 실라버스 그 행의 문장과 배정 시간에서 시작하고, 시간 판정은 각 산출물 문서의 인수 조건이 정한다. 길이는 실제 강사 복제 음성으로 맞춘 계수 `workspace/강의제작/제작도구/촬영/시간계수.json` 하나로 잰다.
- 실습 랩: 학생의 도구는 VS Code의 GitHub Copilot과 Codex다. 새 코드 이름은 `workspace/강의제작/제작도구/기존제작/labs/STRUCTURE.md`. 두 과정의 공통 · 차이는 각 산출물 문서가 적는다. 모든 랩을 한 벌로 통일하지 않는다.
- 인제스천 품질 · 규모 주장은 실제 매뉴얼 실측(`작업/_로컬/realman/`, 없는 PC에서는 미확인)에 잇는다. 실물 PDF는 저작물이라 저장소에 넣지 않는다.

## 6. 환경 (로컬 Windows)

파이썬은 세 갈래가 각자 일을 한다(의도된 구조, 2026-10-30 사용자 확인): 서비스 컨테이너 = `python:3.12-slim`(Dockerfile), 학생 PC = 3.13 이상(시작.bat 보조 스크립트 · 코딩 랩, 표준 라이브러리만), 이 PC의 개발 · 제작 도구 = `.venv314`(공식 3.14, 의존성 `workspace/requirements-dev.txt`).

| | 로컬 Windows |
|---|---|
| Python | `.venv314/Scripts/python.exe`(늘 `PYTHONUTF8=1`). uv 파이썬은 Smart App Control이 막는다 |
| 단위 시험 | 저장소에 없다 — 로직 개편 세션이 새로 짠다. 옛 시험 333개 · 기준선(3,585 통과)은 git `03c23fdd:tests/`(꺼내기 `git archive 03c23fdd tests pytest.ini \| tar -x`, 돌리기 전 `. workspace/개발/scripts/host_libpq.sh`) |
| 통합 시험 | `workspace/개발/scripts/scenario_instance_test.py`(쿨러, `--worker`면 실제 워커 기대), `scenario_pump_fan_test.py`(펌프 · 팬 · 가림) |
| 워커 | `bash workspace/개발/scripts/run_worker_host.sh`(`CLIAGENTS_DEFAULT_CLI=claude-code`). 멈출 때는 `workspace/개발/scripts/stop_worker_host.ps1` 또는 PowerShell `Get-CimInstance Win32_Process \| ? CommandLine -like '*worker.main*'` → `taskkill //PID //F`, 포트 8097/8098이 내려갔는지 확인. 워커 1개가 python 2개로 보인다 |
| 로그 인코딩 | 워커 로그에 cp949가 섞인다. 바이트로 읽어 `errors='replace'`로 디코드 |
| Docker | Docker Desktop(메모리 4 GB 이상). 꺼져 있으면 직접 켜고 `docker info` 응답을 기다린다 |
