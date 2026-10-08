# RUNBOOK — 재부팅 뒤 전 서비스 기동 한 장 (학생 PC · 강사 PC 공통)

목표: 재부팅 뒤 **10분 안에 모든 서비스 healthy**. 2026-10-08 실측(재부팅 대체 — Docker Desktop은 켜 둔 채 전 서비스·Supabase·워커를 멈춘 상태에서 시작): 아래 §1 순서로 **268초(4분 28초)**에 필수 컨테이너 전부 Up·healthz 10/10·워커 2/2(`.evidence/a148/64/`). 실제 PC 재부팅·Docker Desktop 기동 시간은 포함하지 않았다. 첫 기동은 이미지 내려받기·빌드 때문에 더 걸린다.
모든 명령은 **Git Bash** 문법이고 저장소 루트 `/d/work/study/hyd-iot-edu`에서 실행한다. 근거: `compose.yaml`, `.env.example`, `scripts/run_worker_host.sh`, `scripts/host_libpq.sh`, `docs/handoff/HANDOFF.md` §4 "환경"·§7·§10.

## 0. 사전 설치 (한 번만)

| 무엇 | 버전(제작자 PC, HANDOFF §4 2026-10-03 확인) | 비고 |
|---|---|---|
| Docker Desktop (WSL2) | 엔진 29.7.2 | 메모리 4 GB 이상 할당(`docs/student-guide.md` §1). `docs/wslconfig.example` 참고 |
| Supabase CLI | 2.119.0 (`npm i -g supabase`) | 업무 DB·프로세스 저장소(포트 54321~) |
| Node | 24 | supabase CLI·claude CLI용 |
| Python | 3.14.7 **공식 설치본**(`C:\Users\<이름>\AppData\Local\Programs\Python\Python314\python.exe`) → 가상환경 `.venv314` | uv로 받은 파이썬은 Windows Smart App Control에 막힐 수 있다(HANDOFF A105) |
| Claude Code CLI | claude 2.1.292 (구독 로그인, 2026-10-08 실측 `claude --version`) | 호스트 워커가 쓴다(DECISIONS 69). Codex 0.151.0은 선택 |
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

# ④ 에이전트용 MCP 서버 2개(cliagents 프로필은 기본에 없다 — 서비스 이름을 직접 주면 올라온다)
docker compose up -d enterprise-mcp dmn-mcp

# ⑤ 호스트 워커(Claude Code 로그인된 이 PC에서) — 1개는 필수, 2개는 임대(lease) 실습·회귀용
bash scripts/run_worker_host.sh &                                             # 8097
CONSUMER_ID=agent-worker:host2 HEALTH_PORT=8098 bash scripts/run_worker_host.sh &   # 8098 (선택)
```

- ④에 `--profile cliagents`를 붙이지 않는다: `--profile`을 주면 `.env`의 `COMPOSE_PROFILES`가 무시되어 `service "dmn-mcp" depends on undefined service "kg-seed"`로 실패한다(2026-10-08 실측 rc=1, `.evidence/a148/64/boot_mcp_runbook.txt`). 위 명령은 의존 서비스(topic-init·kg-seed)를 다시 확인하느라 약 85초 걸린다.
- 2026-10-08 측정 구간(정지 상태 기준, `.evidence/a148/64/boot.log`): ② Supabase 32 s → ③ 기본 스택 133 s → ④ MCP 85 s → ⑤ 워커 5 s 안에 `/health ok` → 전부 healthy 268 s.
- ⑤는 process의 워커 상태 API(`GET /api/agents/status`, 포털 화면에는 없음)가 호스트 워커를 보게 하려면 `.env`의 `WORKER_URL=http://host.docker.internal:8097`로 두고 process를 다시 올린다(`compose.yaml` process 주석).
- 워커가 실제로 에이전트 작업을 집게 하려면 process·agent에 `AGENT_BRIDGE=off`가 필요하다(`.env` → `docker compose up -d process agent`). `legacy`(기본)면 서버 안의 결정론 에이전트가 네 작업을 채운다.
- 워커 스크립트는 안에서 `. scripts/host_libpq.sh`를 부르고 `CLI_MODEL=opus`를 고정한다. PowerShell만 있으면 `scripts/run_worker_host.ps1` — 이 ps1의 기본 `-Provider`는 Codex이므로 배포본(Claude Code 워커, DECISIONS 69)과 같게 하려면 `-Provider claude-code`를 붙인다. 2026-10-08 실측: `bash scripts/run_worker_host.sh`로 띄운 워커가 12 s 안에 `/health` `status ok`, `/agents?check_auth=1`은 claude-code·codex 둘 다 `installed true · authenticated true`(`.evidence/a148/1-apply/`). 2차 실측(`.evidence/a148/65/`): 기동 로그는 1초 안에 `cliagents agent type up: consumer=agent-worker:host … cli=claude-code permission=workspace_write http=:8097`; 첫 폴링에서 곧바로 작업을 집으면 그 작업이 끝날 때까지 `/health`가 `"status":"starting"`(`polls 0`, `runs_in_flight 1`)으로 보일 수 있다 — 고장이 아니다.
- 워커 스크립트는 **Git Bash 창에서 직접** 실행한다. Windows의 다른 프로그램(PowerShell·Python `subprocess`)에서 `bash`라고만 부르면 WSL bash가 잡혀 `set: pipefail: invalid option name`으로 바로 끝난다(2026-10-08 실측, `.evidence/a148/70/B/worker-8097.log`).
- 같은 PC에서 워커를 여러 개 띄우면 모두 같은 8097에 바인딩될 수 있다(SO_REUSEADDR). `netstat -ano | grep :8097`로 LISTEN PID가 하나인지 확인하고, 옛 워커는 아래 §3 종료 절차로 먼저 끝낸다.

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
| Supabase | 8 (2026-10-08 `supabase stop` → `start` 뒤 관측): supabase_db · kong · auth · rest · realtime · studio · pg_meta · edge_runtime (이름 접미사 `_hyd-iot-edu`). 10-07에는 edge_runtime 없이 7개였다 — `it/supabase/config.toml`에 `[edge_runtime]` 절이 없어 기본값(켜짐)이다 | — |
| 선택 프로필 | monitor → prometheus(9090), tools → redpanda-console(8085) | — |

즉 `docker ps`에 **hyd-iot-edu-* 17개 + supabase_* 7~8개 = 24~25개**가 "Up"이면 된다(선택 prometheus까지 켜면 하나 더; 2026-10-08 실측 26개)(fuxa·grafana·portal·prometheus·console은 healthcheck가 없어 "(healthy)" 표시가 없다). **개수만 보지 말고 위 이름 15+2를 대조한다** — 2026-10-07 대조(`.evidence/a124/runbook-check.md`) 때는 fuxa가 Exited(137)인데 선택 프로필 prometheus가 떠 있어 개수는 17로 같았다(FUXA 1881 응답 없음). 빠진 서비스는 `docker compose up -d <서비스>`로 올린다. healthz 기대값: 각 서비스 `{"ok":true,…}`, process는 `"mode":"instance","supabase":true`, enterprise-mcp는 `"role":"hyd_enterprise_reader","read_only":true`, 워커 `/health`는 `{"status":"ok","agent_type":"cliagents","runs_in_flight":0,"max_concurrent_runs":1,"polls":N,"handled":N,"last_poll":"<UTC>","error":null}`(2026-10-08 실측, `.evidence/a148/1-apply/worker_health.json`). `supabase start`·`status`는 `Stopped services: [inbucket storage imgproxy analytics vector pooler]`를 찍는데 이는 `it/supabase/config.toml`에서 꺼 둔 것(`enabled = false`)이라 정상이다(2026-10-08 실측 목록, edge_runtime은 켜져 있음).

화면 주소: 포털 http://127.0.0.1:8088 (홈 상태 점 전부 초록) · Neo4j Browser http://127.0.0.1:7474 (neo4j / hydpass123) · Grafana http://127.0.0.1:3000 · FUXA http://127.0.0.1:1881 · EMQX http://127.0.0.1:18083 (admin / public123) · Supabase Studio http://127.0.0.1:54323 · FastAPI 서비스 8개(8000·8093·8090·8094·8092·8091·8080·8095)의 `/docs` (MCP 2개 8199·8198은 `/docs`가 없다, 404).

포털 원문 id → 이름 사전 재생성(지식 그래프를 바꾼 뒤, A141): `PYTHONUTF8=1 .venv314/Scripts/python.exe scripts/portal_names.py` → `it/portal/www/names.json` (정적 파일, 재기동 불필요).

## 3. 자주 나는 오류와 첫 조치

| 증상 | 첫 조치 | 근거 |
|---|---|---|
| process `/healthz`가 503이거나 본문에 `consumer_dead`가 있다, 또는 로그에 IPv6 주소로 DB 연결 실패 | `docker restart hyd-iot-edu-process-1` | HANDOFF §10 "환경", `procsvc/main.py` 412행 |
| 호스트에서 파이썬이 psycopg를 못 올린다(libpq DLL 차단, os error 4551) | `. scripts/host_libpq.sh` 를 먼저 source(LibreOffice의 서명된 libpq 사용). Smart App Control은 끄지 않는다(DECISIONS 96 확정) | HANDOFF A105, DECISIONS 96 |
| process가 Supabase보다 먼저 뜨거나 DB가 잠시 멈춘 사이 재시작되면 기동 중 `psycopg.OperationalError … Network is unreachable`로 한 번 종료되고 RestartCount가 1 오른다 | 그대로 둔다: `restart: unless-stopped`가 다시 띄워 DB가 돌아오면 정상 기동한다(2026-10-08 실측: DB 20 s 정지 중 재시작 → 재개 2 s 뒤 healthy, 진행 중 인스턴스는 그대로 이어져 종결, 중복 0). 계속 재시작하면 §1 ② Supabase부터 확인 | `.evidence/a148/70/summary.json`, `procsvc/procdb.py` 459행(`connect_timeout=5`, 재시도 없음) |
| process 컨테이너가 메모리로 죽는다(OOM, RestartCount 증가) | `.env`의 `PROCESS_MEM_LIMIT=768m` 확인 후 `docker compose up -d process` | `.env.example` 주석(A115: 512m에서 509 MiB 도달) |
| 시험·실습 뒤 RUNNING 인스턴스 잔재가 "내 할일"에 남는다 | `. scripts/host_libpq.sh; .venv314/Scripts/python.exe scripts/cleanup_residue_instances.py --before <ISO시각, 예 2026-10-07T12:20Z> --out .evidence/residue/<이름>` 로 먼저 목록·백업, 확인 뒤 `--apply` | 스크립트 머리말(A115) |
| 워커를 다시 띄워야 한다 | 저장소 루트에서 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_worker_host.ps1` 로 트리째 종료 → §1 ⑤ 다시(2026-10-08 실측: 실행 정책이 Restricted인 PC에서는 `-ExecutionPolicy Bypass`가 없으면 "스크립트를 실행할 수 없으므로"로 멈춘다). 스크립트는 명령줄에 `worker.main`이 있는 `python(w).exe`(sh·ps1 기동 둘 다 해당)와 그 자식 프로세스 전부(CLI·MCP)를 `Stop-Process -Force`하고 결과를 `.evidence/reaudit/worker-stop.json`에 쓴다(남으면 exit 1). `-StopScenario`를 주면 `scenario_instance_test.py --worker`도 함께 끝낸다 | `scripts/stop_worker_host.ps1` |
| `process.sqlite3`가 수백 MB로 커진다(처리 완료된 투영 아웃박스 행이 안 지워짐, A115: 8,615행 188 MB) | `.venv314/Scripts/python.exe scripts/prune_projection_outbox.py --older-than-days 1` 로 먼저 세고(dry-run, 컨테이너 실행 중에도 안전), 회귀가 돌지 않을 때 `--apply`(500행씩 짧은 트랜잭션). 디스크를 실제로 돌려받으려면 `docker compose stop process` 뒤 `--apply --vacuum`(실행 중이면 거부) → `docker compose up -d process` | 스크립트 머리말(A124), `.evidence/a124/prune-dry.txt`; 2026-10-08 정지 상태 `--older-than-days 1 --apply --vacuum` 실측: 21행 삭제·VACUUM 6.5 s, 320.5 → 300.1 MB(`.evidence/a148/67/`) |
| 승인했는데 PLC ACK가 없다(게이트웨이 `MODE`) | 설비가 REMOTE_MANUAL이다 → 포털 결함 시뮬레이션 카드 **원격 자동** | `docs/student-guide.md` §7 |
| FUXA 값이 `##.##` | `docker compose up -d --force-recreate fuxa-init` | 같은 문서 |
| 경보가 안 난다 | `curl -s 127.0.0.1:8092/api/detector/state` 의 `phase`·`slope`; CANDIDATE가 60 시뮬레이션-초 유지돼야 RAISED | 같은 문서 |
| 시간 배율(`TIME_SCALE`)을 바꿨다 | 감지기 상태 파일은 배율별로 따로 둔다: `.env`의 `TIME_SCALE`과 함께 `DETECTOR_STATE_PATH=/data/detector-scale<N>.sqlite3`를 detector에 주고 `docker compose up -d plant-sim detector process agent`(배율은 네 서비스에 함께). 기본 20배속은 `/data/detector.sqlite3`. 다른 배율의 상태 파일이 볼륨에 남아 있으면(`docker exec hyd-iot-edu-detector-1 ls /data`) 기본으로 돌아온 뒤 지운다 | `compose.yaml` detector, HANDOFF A127·A128 |
| 승인하지 않은 명령이 `action.cmd`에 올라와도 PLC가 움직이면 안 된다 | cmd-gateway 검사 ⑤ APPROVAL(2026-10-08): process가 승인마다 audit 토픽에 `CMD_APPROVAL_RECORDED`(cmdId·approvalId·HMAC 지문)를 먼저 쓰고, 관문은 그 기록이 있고 지문이 맞는 명령만 보낸다. `curl 127.0.0.1:8090/api/gateway/log`에 `check: APPROVAL`로 거절이 남는다. 키는 `.env` `CMD_FINGERPRINT_KEY`(process·cmd-gateway 동일) | `dmz/cmd-gateway/gw/validate.py`, `.evidence/a148/69/` |
| Supabase 포트 충돌·기동 실패 | `( cd it/supabase && supabase stop )` 뒤 다시 `supabase start`; 포트는 `it/supabase/config.toml` 54321~54329 | config.toml |
| 처음 `docker compose up`이 오래 걸린다 | 이미지 내려받기·빌드 5~10분(student-guide §1). 10분 목표는 **두 번째 기동부터** | — |

핵심 회귀(core 12)는 호스트 워커를 **끈 상태**에서 `.venv314/Scripts/python.exe scripts/run_regression.py --group core --out .evidence/reaudit/reg-<태그> --kill-workers --restart-workers 2`, 워커 묶음(6)은 워커 2개를 켠 상태에서 `--group worker`(`scripts/run_regression.py` 머리말). 2026-10-08 결과: core 13/13 PASS(약 15분), worker 5/6(rule-questions r1 하나는 검사 기대값이 낡음 — HYD-03 `standby_ready` 결측 가정), `.evidence/reaudit/reg-a148-core/`·`reg-a148-worker/`. 10분을 넘는 측정은 먼저 알린다.

## 4. 종료 순서

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_worker_host.ps1   # ① 호스트 워커(자식 CLI·MCP 프로세스까지)
docker compose stop enterprise-mcp dmn-mcp                       # ② MCP 2개 (--profile cliagents를 붙이면 실패, §1 ④ 참고)
docker compose stop                                              # ③ 기본 스택 (볼륨·데이터 보존)
( cd it/supabase && supabase stop )                              # ④ 업무 DB
```

`docker compose down -v`는 TimescaleDB·Neo4j·프로세스 데이터 볼륨을 지우므로 수업 자료를 초기화할 때만 쓴다(원자료 삭제에 해당하므로 강사 결정).

## 5. 이 문서가 확인하지 못한 것

- 10분 안 기동 시간: 전 서비스 정지 상태 → §1 → §2까지 268 s로 **실측**(2026-10-08, `.evidence/a148/64/`). 실제 재부팅과 Docker Desktop 재시작을 포함한 시간은 재지 않았다.
- 학생 PC(제작자 PC가 아닌 다른 Windows·macOS)에서의 Smart App Control·libpq 문제 재현 여부.
- Supabase 컨테이너 7개는 2026-10-07 제작자 PC 관측값이며 CLI 버전에 따라 늘 수 있다(`supabase status`로 확인).
