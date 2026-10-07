# RUNBOOK — 재부팅 뒤 전 서비스 기동 한 장 (학생 PC · 강사 PC 공통)

목표: 재부팅 뒤 **10분 안에 모든 서비스 healthy** (10분은 목표이며 **미실측**이다 — 첫 기동은 이미지 내려받기·빌드 때문에 더 걸린다).
모든 명령은 **Git Bash** 문법이고 저장소 루트 `/d/work/study/hyd-iot-edu`에서 실행한다. 근거: `compose.yaml`, `.env.example`, `scripts/run_worker_host.sh`, `scripts/host_libpq.sh`, `docs/handoff/HANDOFF.md` §4 "환경"·§7·§10.

## 0. 사전 설치 (한 번만)

| 무엇 | 버전(제작자 PC, HANDOFF §4 2026-10-03 확인) | 비고 |
|---|---|---|
| Docker Desktop (WSL2) | 엔진 29.7.2 | 메모리 4 GB 이상 할당(`docs/student-guide.md` §1). `docs/wslconfig.example` 참고 |
| Supabase CLI | 2.119.0 (`npm i -g supabase`) | 업무 DB·프로세스 저장소(포트 54321~) |
| Node | 24 | supabase CLI·claude CLI용 |
| Python | 3.14.7 **공식 설치본**(`C:\Users\<이름>\AppData\Local\Programs\Python\Python314\python.exe`) → 가상환경 `.venv314` | uv로 받은 파이썬은 Windows Smart App Control에 막힐 수 있다(HANDOFF A105) |
| Claude Code CLI | claude 2.1.250 (구독 로그인) | 호스트 워커가 쓴다. Codex 0.151.0은 선택 |
| Git | Git Bash 포함 | `bash scripts/*.sh` 실행용 |

가상환경 준비(한 번): `"/c/Users/$USERNAME/AppData/Local/Programs/Python/Python314/python.exe" -m venv .venv314 && .venv314/Scripts/python.exe -m pip install -r requirements-dev.txt` (루트 `requirements-dev.txt`가 `it/agent`·`it/process`의 requirements를 포함한다; 워커용 `cliagents`·`psycopg`·`neo4j`는 `it/agent-worker` 요구 파일 확인. 3.14에는 고정 버전 휠이 없어 상위 호환 설치됐다 — HANDOFF §4).
`.env`가 없으면 `cp .env.example .env`. 강의 배포본은 `.env`에 `PROCESS_MODE=instance`, `ENTERPRISE_BACKEND=supabase`, `PROCESS_MEM_LIMIT=768m`을 둔다(2026-10-07 현재 제작자 `.env` 값).

## 1. 기동 순서

```bash
cd /d/work/study/hyd-iot-edu

# ① Docker Desktop 실행 → 트레이 아이콘이 "Engine running"이 될 때까지 기다린다
docker info >/dev/null 2>&1 && echo docker-ok

# ② 업무 DB(Supabase) — process·enterprise-sim·MCP가 54322 포트를 기다린다
( cd it/supabase && supabase start )

# ③ 기본 스택 7개 프로필(.env COMPOSE_PROFILES: ot,backbone,detect,knowledge,agent,enterprise,process)
docker compose up -d            # 처음이면 docker compose up -d --build

# ④ 에이전트용 MCP 서버 2개(cliagents 프로필은 기본에 없다)
docker compose --profile cliagents up -d enterprise-mcp dmn-mcp

# ⑤ 호스트 워커(Claude Code 로그인된 이 PC에서) — 1개는 필수, 2개는 임대(lease) 실습·회귀용
bash scripts/run_worker_host.sh &                                             # 8097
CONSUMER_ID=agent-worker:host2 HEALTH_PORT=8098 bash scripts/run_worker_host.sh &   # 8098 (선택)
```

- ⑤는 포털 "에이전트 현황"이 호스트 워커를 보게 하려면 `.env`의 `WORKER_URL=http://host.docker.internal:8097`로 두고 process를 다시 올린다(`compose.yaml` process 주석).
- 워커가 실제로 에이전트 작업을 집게 하려면 process·agent에 `AGENT_BRIDGE=off`가 필요하다(`.env` → `docker compose up -d process agent`). `legacy`(기본)면 서버 안의 결정론 에이전트가 네 작업을 채운다.
- 워커 스크립트는 안에서 `. scripts/host_libpq.sh`를 부르고 `CLI_MODEL=opus`를 고정한다. PowerShell만 있으면 `scripts/run_worker_host.ps1`(Codex 기본, `-Provider claude-code`).

## 2. 확인

```bash
docker ps --format '{{.Names}}\t{{.Status}}' | sort
for p in 8000 8093 8090 8094 8092 8091 8080 8095 8199 8198; do printf "%s " $p; curl -s -m 3 http://127.0.0.1:$p/healthz; echo; done
curl -s http://127.0.0.1:8097/health     # 호스트 워커 (8098은 둘째)
( cd it/supabase && supabase status )
```

기대 개수(`compose.yaml`에서 센 값):

| 묶음 | 계속 떠 있는 컨테이너 | 한 번 돌고 끝나는 것(Exited 0이 정상) |
|---|---|---|
| 기본 7 프로필 | 15: emqx · plant-sim · fuxa · connect-ingest · cmd-gateway · redpanda · timescaledb · connect-sink · grafana · detector · neo4j · agent · process · enterprise-sim · portal | 3: fuxa-init · topic-init · kg-seed |
| cliagents(④) | 2: enterprise-mcp · dmn-mcp (agent-worker 컨테이너는 호스트 워커를 쓰면 올리지 않는다) | — |
| Supabase | 7 (2026-10-07 관측): supabase_db · kong · auth · rest · realtime · studio · pg_meta (이름 접미사 `_hyd-iot-edu`) | — |
| 선택 프로필 | monitor → prometheus(9090), tools → redpanda-console(8085) | — |

즉 `docker ps`에 **hyd-iot-edu-* 17개 + supabase_* 7개 = 24개**가 "Up"이면 된다(fuxa·grafana·portal·prometheus·console은 healthcheck가 없어 "(healthy)" 표시가 없다). **개수만 보지 말고 위 이름 15+2를 대조한다** — 2026-10-07 대조(`.evidence/a124/runbook-check.md`) 때는 fuxa가 Exited(137)인데 선택 프로필 prometheus가 떠 있어 개수는 17로 같았다(FUXA 1881 응답 없음). 빠진 서비스는 `docker compose up -d <서비스>`로 올린다. healthz 기대값: 각 서비스 `{"ok":true,…}`, process는 `"mode":"instance","supabase":true`, enterprise-mcp는 `"role":"hyd_enterprise_reader","read_only":true`, 워커 `/health`는 `"status":"ok"`(워커 응답 키는 10-07 대조 때 워커가 꺼져 있어 미검증). `supabase status`는 `Stopped services: [inbucket storage imgproxy edge_runtime analytics vector pooler]`를 먼저 찍는데 이는 `it/supabase/config.toml`에서 꺼 둔 것(`enabled = false`)이라 정상이다.

화면 주소: 포털 http://127.0.0.1:8088 (홈 상태 점 전부 초록) · Neo4j Browser http://127.0.0.1:7474 (neo4j / hydpass123) · Grafana http://127.0.0.1:3000 · FUXA http://127.0.0.1:1881 · EMQX http://127.0.0.1:18083 (admin / public123) · Supabase Studio http://127.0.0.1:54323 · FastAPI 서비스 8개(8000·8093·8090·8094·8092·8091·8080·8095)의 `/docs` (MCP 2개 8199·8198은 `/docs`가 없다, 404).

포털 원문 id → 이름 사전 재생성(지식 그래프를 바꾼 뒤, A141): `PYTHONUTF8=1 .venv314/Scripts/python.exe scripts/portal_names.py` → `it/portal/www/names.json` (정적 파일, 재기동 불필요).

## 3. 자주 나는 오류와 첫 조치

| 증상 | 첫 조치 | 근거 |
|---|---|---|
| process `/healthz`가 503이거나 본문에 `consumer_dead`가 있다, 또는 로그에 IPv6 주소로 DB 연결 실패 | `docker restart hyd-iot-edu-process-1` | HANDOFF §10 "환경", `procsvc/main.py` 412행 |
| 호스트에서 파이썬이 psycopg를 못 올린다(libpq DLL 차단, os error 4551) | `. scripts/host_libpq.sh` 를 먼저 source(LibreOffice의 서명된 libpq 사용). Smart App Control 끄기는 사용자 결정 | HANDOFF A105 |
| process 컨테이너가 메모리로 죽는다(OOM, RestartCount 증가) | `.env`의 `PROCESS_MEM_LIMIT=768m` 확인 후 `docker compose up -d process` | `.env.example` 주석(A115: 512m에서 509 MiB 도달) |
| 시험·실습 뒤 RUNNING 인스턴스 잔재가 "내 할일"에 남는다 | `. scripts/host_libpq.sh; .venv314/Scripts/python.exe scripts/cleanup_residue_instances.py --before <ISO시각, 예 2026-10-07T12:20Z> --out .evidence/residue/<이름>` 로 먼저 목록·백업, 확인 뒤 `--apply` | 스크립트 머리말(A115) |
| 워커를 다시 띄워야 한다 | 저장소 루트에서 PowerShell `scripts/stop_worker_host.ps1` 로 트리째 종료 → §1 ⑤ 다시. 스크립트는 명령줄에 `worker.main`이 있는 `python(w).exe`(sh·ps1 기동 둘 다 해당)와 그 자식 프로세스 전부(CLI·MCP)를 `Stop-Process -Force`하고 결과를 `.evidence/reaudit/worker-stop.json`에 쓴다(남으면 exit 1). `-StopScenario`를 주면 `scenario_instance_test.py --worker`도 함께 끝낸다 | `scripts/stop_worker_host.ps1` |
| `process.sqlite3`가 수백 MB로 커진다(처리 완료된 투영 아웃박스 행이 안 지워짐, A115: 8,615행 188 MB) | `.venv314/Scripts/python.exe scripts/prune_projection_outbox.py --older-than-days 1` 로 먼저 세고(dry-run, 컨테이너 실행 중에도 안전), 회귀가 돌지 않을 때 `--apply`(500행씩 짧은 트랜잭션). 디스크를 실제로 돌려받으려면 `docker compose stop process` 뒤 `--apply --vacuum`(실행 중이면 거부) → `docker compose up -d process` | 스크립트 머리말(A124), `.evidence/a124/prune-dry.txt` |
| 승인했는데 PLC ACK가 없다(게이트웨이 `MODE`) | 설비가 REMOTE_MANUAL이다 → 포털 결함 시뮬레이션 카드 **원격 자동** | `docs/student-guide.md` §7 |
| FUXA 값이 `##.##` | `docker compose up -d --force-recreate fuxa-init` | 같은 문서 |
| 경보가 안 난다 | `curl -s 127.0.0.1:8092/api/detector/state` 의 `phase`·`slope`; CANDIDATE가 60 시뮬레이션-초 유지돼야 RAISED | 같은 문서 |
| Supabase 포트 충돌·기동 실패 | `( cd it/supabase && supabase stop )` 뒤 다시 `supabase start`; 포트는 `it/supabase/config.toml` 54321~54329 | config.toml |
| 처음 `docker compose up`이 오래 걸린다 | 이미지 내려받기·빌드 5~10분(student-guide §1). 10분 목표는 **두 번째 기동부터** | — |

핵심 회귀(core 12)는 호스트 워커를 **끈 상태**에서 `.venv314/Scripts/python.exe scripts/run_regression.py --group core --out .evidence/reaudit/reg-<태그> --kill-workers --restart-workers 2`, 워커 묶음(6)은 워커 2개를 켠 상태에서 `--group worker`(`scripts/run_regression.py` 머리말). 10분을 넘는 측정은 먼저 알린다.

## 4. 종료 순서

```bash
powershell -NoProfile -File scripts/stop_worker_host.ps1        # ① 호스트 워커(자식 CLI·MCP 프로세스까지)
docker compose --profile cliagents stop enterprise-mcp dmn-mcp   # ② MCP 2개
docker compose stop                                              # ③ 기본 스택 (볼륨·데이터 보존)
( cd it/supabase && supabase stop )                              # ④ 업무 DB
```

`docker compose down -v`는 TimescaleDB·Neo4j·프로세스 데이터 볼륨을 지우므로 수업 자료를 초기화할 때만 쓴다(원자료 삭제에 해당하므로 강사 결정).

## 5. 이 문서가 확인하지 못한 것

- 10분 안 기동 시간: **미실측**. 재부팅 → §1 → §2 "24개 Up"까지 한 번 재서 숫자를 넣어야 한다.
- 학생 PC(제작자 PC가 아닌 다른 Windows·macOS)에서의 Smart App Control·libpq 문제 재현 여부.
- Supabase 컨테이너 7개는 2026-10-07 제작자 PC 관측값이며 CLI 버전에 따라 늘 수 있다(`supabase status`로 확인).
