# hyd-iot-edu — 프로젝트 계약 (로컬·클라우드 공통)

공용 헌법(`claude-skills/CLAUDE.md`)을 따른다. 로컬은 `~/.claude/CLAUDE.md`가 불러오고,
클라우드는 `.claude/hooks/cloud-bootstrap.sh`가 세션 시작 때 넣는다. 아래는 이 저장소에만 해당하는 것이다.

## 1. 시작할 때 읽는 순서

`docs/handoff/`가 생명선이다. 대화 요약이 끊겨도 이 폴더만 읽으면 이어갈 수 있어야 한다.

1. `docs/handoff/GOAL.md` — 의도와 인수조건
2. `docs/handoff/HANDOFF.md` — 현재 사실·규칙·진행 상태. §9의 첫 `[ ]`/`[~]` 항목이 다음 일이다
3. `docs/handoff/DECISIONS.md` — 결정 경위
4. `docs/handoff/QA.md`, `docs/handoff/USER_UTTERANCES.md` — 사용자가 물은 것과 답, 발화 원문
5. 실라버스·교재 작업이면 `docs/handoff/HANDOFF_실라버스교재.md`

범위는 위 문서의 **최신** 사용자 지시가 정한다. 과거 GOAL·자동 재개 문구의 조건을 완료 조건으로 다시 가져오지 않는다.
회의 근거는 `HANDOFF.md` §1의 원문 줄 번호로 댄다. HANDOFF §2(확정 방향)·§3(절대 규칙)은 근거 없이 바꾸지 않는다.

## 2. 기록

- 파일 하나 만들거나 시험 하나 돌릴 때마다 HANDOFF §9 체크박스와 근거를 먼저 갱신하고 다음 일로 간다.
- 결정은 HANDOFF §2에 이유와 함께, 경위는 DECISIONS.md, 사용자 발화 원문은 USER_UTTERANCES.md, 질문·답은 QA.md.
- 모든 실행은 `.evidence/<A번호>/`에 명령·로그·JSON을 남기고 실패는 파일:줄로 인계에 적는다.
- 전체 작업을 마치면 작업보고에 한 절 추가한다(로컬: `D:/work/작업보고/YYYY-MM-DD.md`. 클라우드에는 이 경로가 없으므로 HANDOFF §9에 남기고 사용자에게 알린다).

## 3. 시스템 규칙

- **배속 기본 20배(`TIME_SCALE=20`).** 가상 설비라 수업·실습·검사 모두 20배속이다. "1~2배속 권장" 문구를 쓰지 않는다.
  20배속에서 흔들리는 코드는 배속 기준으로 고친다. 더 높은 배속은 가짜 실패를 만드니 쓰지 않는다.
  배율은 plant-sim·detector·process·agent에 함께 적용한다(`/api/time_scale`은 plant 물리만 바꾼다). 바꿀 때는 `docs/RUNBOOK.md` 표를 따른다.
- **회귀·라이브 검사기(run_regression·probe_*)가 도는 동안 `docker compose build/up/restart` 금지.**
  compose는 의존 서비스가 바뀌면 process를 재시작시켜 검사가 `RemoteDisconnected`로 끊긴다.
  배포는 검사 전에 끝내고 `docker inspect hyd-iot-edu-process-1 --format '{{.State.StartedAt}} {{.RestartCount}}'`로 안정을 확인한다.
  에러 없이 조용히 재시작했으면 커널 OOM을 의심한다(로컬: `wsl -d docker-desktop -e sh -c "dmesg | grep -i oom"`).
- 20배속 레거시 회귀 전에는 호스트 워커를 모두 멈춘다(워커가 에이전트 작업을 가져간다).
- 완주·E2E 검증은 학생 대역 1명·인스턴스 1건·1회. 학생 수만큼 동시에 돌리지 않는다.
- enterprise-mcp·dmn-mcp는 프로필 `cliagents`에만 있다: `docker compose --profile cliagents up -d enterprise-mcp dmn-mcp`. agent-worker 컨테이너는 올리지 않는다.
- Supabase 로컬: `cd it/supabase && supabase start`(PostgreSQL 15, 포트 54322). `supabase stop --no-backup`은 볼륨을 지운다.
- 컨테이너·Supabase·워커는 스스로 켜고 끄고, 시험 잔재(임시 DB·시험 인스턴스)는 스스로 정리한다. 끈 뒤 실제로 꺼졌는지 확인한다.
  프로젝트 데이터 볼륨, 원자료, 강사 손질본 삭제와 원격 push·결제는 묻는다.

## 4. 내용 규칙

- 시나리오·BPMN·온톨로지는 저장소에 있는 이름만 쓴다. 작업 전에 시나리오 HANDOFF 0절과 코드(agentsvc·procsvc·entsim·seed)를 먼저 읽는다.
  정본 위치는 HANDOFF 자산 지도를 따른다(현재 `docs/ontology/schema-v2.md`, `it/neo4j/v2/instances.cypher`, 템플릿 `it/neo4j/templates/`).
  온톨로지는 객체 모델(클래스·속성·관계)이다. 프로세스 설명은 온톨로지가 아니다.
- 해피패스·구세주 데이터 금지: 사례마다 손익으로 지는 대안과 실제로 밟는 비해피 가지가 있어야 한다.
- 승인 전 에이전트는 조회·계산·보고서만 한다. 사람 승인 1회 뒤 process가 실행한다.
- 업무 흐름은 "사건 한 건 = 프로세스 인스턴스 하나, 그 안을 task 단위(시스템·에이전트·규칙·사람·현장)"로 쓴다.
- 시스템 문서는 구조와 데이터 리니지(출생→변환→저장→소비, 실패·분기)가 목적이다. 수치 표보다 구조 정확성을 우선한다.
- 온톨로지·스키마 결과를 사용자에게 보고할 때는 전문 용어에 비유 한 줄과 "사용자가 스스로 판정할 체크 질문"을 같이 준다.
- 참고 레포와 다른 곳은 ① 실제 결함인가 ② 회의·계약 요구를 못 채우는가만 묻는다. 둘 다 아니면 "차이 있음, 유지"로 기록한다.
- 포털 UI 추가는 추가한 것만 다듬는다. 기존 컴포넌트·간격 재사용, 카드 하나에 행동 1개, 보조 정보는 접기. 판정 기준은 "학생이 10초 안에 할 일을 찾는가".
- 실라버스·교재 제목은 기술 이름이 아니라 가치 문장("무엇을 해서 무엇을 알아보기")이다.
- **랩업 계약**(`HANDOFF_실라버스교재.md` §7): 막마다 "이 기능이 이렇게 만들어진다"를 VS Code 터미널의 Claude Code 바이브 코딩으로 직접 만들어 보는 랩업을 둔다.
  대상은 온톨로지 스키마·데이터 적재, MCP 만들어 붙이기, 판단 규칙, 에이전트·툴. 마지막은 SDD(명세 먼저, 기존 기능을 깨지 않고 추가).
  랩업마다 "만들 것·확인할 결과·필요한 출발본"을 적는다. 에이전트의 툴 호출은 콘솔 로그로 보여 준다.
- 인제스천 품질·규모 주장은 실제 매뉴얼 실측(`.evidence/realman/`, HANDOFF A092~A094)에 연결한다. 실물 PDF는 저작물이라 레포 픽스처로 넣지 않는다.

## 5. 환경 (OS별)

| | 로컬 Windows | 클라우드 Linux |
|---|---|---|
| Python | `.venv314/Scripts/python.exe`(공식 3.14). uv 파이썬은 Smart App Control이 막는다 | `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt` |
| 단위 시험 | `. scripts/host_libpq.sh; PYTHONUTF8=1 .venv314/Scripts/python -m pytest -q` (서명된 libpq를 PATH 앞에 둬 DLL 차단을 피한다) | `.venv/bin/python -m pytest -q` (host_libpq.sh 불필요) |
| 워커 | `bash scripts/run_worker_host.sh` (`CLIAGENTS_DEFAULT_CLI=claude-code`). 멈출 때는 PowerShell `Get-CimInstance Win32_Process \| ? CommandLine -like '*worker.main*'`로 찾아 `taskkill //PID //F`, 포트 8097/8098이 내려갔는지 확인. 워커 1개가 python 2개로 보인다 | `bash scripts/run_worker_host.sh`, 멈출 때 `pkill -f worker.main` 후 포트 확인 |
| 로그 인코딩 | 워커 로그에 cp949가 섞인다. 바이트로 읽어 `errors='replace'`로 디코드 | UTF-8 |
| Docker | Docker Desktop(메모리 4 GB 이상). 꺼져 있으면 직접 켜고 `docker info` 응답을 기다린다 | Docker·`docker compose` 기본 설치(VM 약 4 vCPU·16 GB). `docker info`가 안 되면 `dockerd`부터 켠다. 컨테이너는 세션마다 새로 띄운다(이미지는 환경 캐시에 남음, 느리면 환경 설정 스크립트에 `docker compose pull`). 메모리가 모자라 멈추면 그 사실을 보고한다 |

클라우드 `.env`: 레포에 없다(.gitignore). 세션 시작 훅(`.claude/hooks/cloud-env.sh`)이 `.env.example`로 만들고,
LLM 키·주소(`OPENAI_API_KEY`·`LLM_API_KEY`·`OPENAI_BASE_URL`·`LLM_MODEL`·`LLM_PROVIDER`·`LLM_EXTRA_BODY`)는 claude.ai/code 환경 설정의
환경변수로 들어온다(compose는 `${VAR:-기본값}`만 쓰므로 셸 환경변수가 우선). LLM 서버 도메인은 환경의 네트워크 허용 목록에 있어야 한다.
클라우드에는 Supabase가 없으므로 `PROCESS_MODE=instance`·`ENTERPRISE_BACKEND=supabase` 검증은 로컬에서 하거나 미검증으로 남긴다.

통합 시험: `scripts/scenario_instance_test.py`(쿨러, `--worker`면 실제 워커 기대), `scripts/scenario_pump_fan_test.py`(펌프·팬·가림),
`scripts/scenario_test.py --quick`(레거시, `PROCESS_MODE=legacy`로 process 재기동 필요).
