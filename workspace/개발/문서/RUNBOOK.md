# RUNBOOK — 시스템 켜기 · 확인 · 끄기와 개발 도구 (학생 PC · 강사 PC 공통)

학생은 `setup/`의 실행 파일 셋만 쓴다: **시작**(`시작.bat` · `시작.command`) → **점검**(`점검.bat` · `점검.command`) → **끄기**(`끄기.bat` · `끄기.command`). 각각 `scripts/start_all.sh` · `scripts/check_all.sh` · `scripts/stop_all.sh`를 부른다. 이 문서는 그 안에서 무엇이 도는지와 개발 · 강사만 쓰는 도구를 적는다. 명령은 **Git Bash** 문법이고 저장소 루트에서 실행한다.

## 0. 설치 (한 번)

- 학생 PC: `setup/설치.bat`(Windows, 관리자 승인 창이 뜬다) · `설치.command`(Mac). 기준 판은 `scripts/versions.txt` 한 곳(Docker Desktop · Node · Git · Python 3.13 이상(없으면 3.14.7) · WSL · VS Code). Supabase CLI는 따로 깔지 않는다 — 시작 · 끄기가 `npx supabase@<versions.txt의 SUPABASE_CLI>`로 부른다. Claude Code CLI는 AI 워커 이미지 안에 있다.
- 개발 PC만: 공식 Python 3.14로 `.venv314`를 만들고 `.venv314/Scripts/python.exe -m pip install -r workspace/requirements-dev.txt`. uv로 받은 파이썬은 Smart App Control에 막힌다.
- 학생이 `.env`에 넣는 것은 `LLM_API_KEY=` 한 줄(강의 중계 키)뿐이다. 나머지 `.env` 값은 시작이 정한다. 수업 구성 값(배속 등)은 `compose.yaml`의 `x-class` 한 곳이다 — 개발 · 강사가 바꿀 때는 저장소 루트 `compose.override.yaml`(git 무시, compose가 저절로 합친다)에 `services: <서비스>: environment: {이름: 값}`.

## 1. 켜기 — `scripts/start_all.sh`

| 단계 | 하는 일 |
|---|---|
| 1 Docker 확인 | 꺼져 있으면 켜고 최대 3분 기다린다. 그래도 응답이 없으면 멈춤 |
| 2 `.env` · 이 PC 값 | `.env`가 없으면 `.env.example`을 복사. 키가 있으면 `AI_MODE=live`, 없으면 `replay`(강사가 저장한 응답 `it/agent-worker/replay/` 재생). process 호출 값 · 명령 지문 키를 정한다. 프로젝트 이름 · 포트는 이 PC 값(`.hyd-runtime/project.json` · `ports.json`, 업무 DB는 `it/supabase/.env`) — 같은 폴더면 이어받고, 다른 프로그램이 쓰는 포트는 피한다. compose가 정하는 옛 `.env` 줄은 꺼 두고 알린다. **git이 추적하는 파일은 고치지 않는다** |
| 3 업무 DB | `supabase start` 뒤 새 마이그레이션 적용(`migration up --local`) |
| 4 빌드 · 기동 | `docker compose up -d --build` — 처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있다. 지운 옛 볼륨(`<이름>_enterprise-data`)은 기동 뒤 스스로 지운다 |
| 5 서비스 확인 | 최대 3분, 포털 응답까지 |
| 6 수업 흐름 A · B · C | `scripts/c3_flows.py ensure` — 배포된 수업 흐름이 정본(`it/process/procsvc/course_flows.json`)과 같으면 그대로, 다르면 새 판본 등록 · 배포 |
| 7 수업용 기본 지식 | `scripts/class_knowledge.py ensure` — 강사 서명 묶음(`it/process/procsvc/course_extractions.json`)의 HM-8 · PM-02 · PR-07 검토본을 AI 없이 넣는다. 옛 시작 판은 다음 시작 때 묶음 판으로 바꿔 넣고, 학생이 다시 넣은 판은 그대로 둔다 |
| 8 AI 단계 확인 | 키 없음: 저장 응답이 있는지. 키 있음: process가 받은 중계 주소 · 키로 강의 중계에 닿는지(거절 · 무응답이면 멈춤) |

- 두 번 눌러도 시작은 하나만 돈다. 두 번째 시작은 아무것도 바꾸지 않는다.
- 걸리는 시간(이 PC 실측, 이미지 있음, 키 없음): 처음 1분 45초 · 연달아 두 번째 1분 40초 · 끈 뒤 다시(코드가 바뀌어 다시 빌드) 2분 52초. 세 경우 모두 시작 뒤 `git status` 변화 0.
- 강사 AI 응답 저장은 `--record`(키 필요) — 보통 `workspace/개발/scripts/record_replay.sh`가 부른다(§5).

## 2. 확인 — `scripts/check_all.sh`(`scripts/check_stack.py all`)

서비스 응답 → 쿨러 사건 한 바퀴(경보 → 처리 건 → AI 판단 · 제안 → 승인 → 냉각 명령 → 재관측 → 작업지시 → 결과 보고) → 점검이 연 처리 건 닫기 · 설비 되돌리기 → 강의 중계(키 있는 PC만). 약 2분(이 PC 실측, 키 없음).

떠 있어야 하는 것: compose 서비스 24개 = 계속 떠 있는 21개(전부 healthy) + 한 번 돌고 끝나는 3개(`fuxa-init` · `topic-init` · `kg-seed`, Exited 0이 정상) + Supabase 컨테이너 3개(`supabase_db` · `supabase_inbucket` · `supabase_kong`, 이름 끝에 `_<프로젝트 이름>`). 선택 프로필 `monitor`(prometheus) · `tools`(redpanda-console)는 기본으로 뜨지 않는다.

```bash
docker compose ps -a
cat .hyd-runtime/ports.json     # 기본 포트 → 이 PC의 바깥 포트(다른 프로그램과 겹쳐 옮긴 포트 포함)
```

화면 주소(기본 포트, 옮겼으면 `ports.json`의 값): 포털 8088 · Neo4j Browser 7474 · Grafana 3000 · FUXA 1881 · EMQX 18083. MQTT 바깥 입구는 호스트 1883(MQTT) · 8083(WebSocket), 계정 `student`/`student` — 구독만 된다(발행하면 연결이 끊긴다). 설비 명령 토픽은 관문(cmd-gateway)만 보낸다.

## 3. 끄기 — `scripts/stop_all.sh`

이 폴더의 compose 서비스(선택 프로필 포함)를 멈추고 업무 DB를 끈 뒤, 이 폴더의 compose 컨테이너와 이 PC 업무 DB(`com.supabase.cli.project` 라벨) 컨테이너가 모두 0개인지 센다. 데이터는 남는다. 15.6초(이 PC 실측).

**데이터를 지우는 명령은 따로 있다** — 수업 자료 초기화일 때만 쓴다(강사 결정):
- `docker compose --profile '*' down -v` — compose 볼륨 8개 전부: 시계열 · 그래프 · Redpanda · process · 감지기 · 워커 작업 공간 · 워커 인증 · 메일 멱등 기록.
- `( cd it/supabase && npx -y supabase@<SUPABASE_CLI> stop --no-backup )` — 업무 DB 볼륨. 반드시 `it/supabase` 안에서 한다(그 폴더의 `.env`가 이 PC의 project_id다).
- 시험이 남긴 진행 중 처리 건도 이것으로 비운다(한 건은 처리 건 화면의 [단계 닫기] · [거절]).
- 포털 관리 화면의 [기준으로 되돌리기]는 학생 기록 — 판단 채점 정답표 · 실행 기록, 시험 비교 기록, 비밀 값 — 까지 지운다(확인 창에 적음). 정답표는 시드가 없고 학생이 포털에서 적는 데이터다(실라버스 통합 83 · 실전 62행 「학생이 정답표 항목으로 적는다」, 마이그레이션 20261008000030).

## 4. 수업 단계와 PBL 열기

수업 경계 규칙은 `it/process/procsvc/course_policy.py` 한 곳에 있다(화면은 `GET /api/course-access`, 워커는 `POST /internal/worker/course-decision`으로 읽는다). 단계는 강사 서명 선언 `it/process/procsvc/course_phase.json`으로 정한다 — 없으면 수업 단계, 서명 · 형식이 틀리면 process가 뜨지 않는다. PBL은 기한이 필수이고 지나면 수업 단계로 읽는다. 화면 · 설정 · `.env`로는 단계를 바꿀 수 없다 — 저장소 코드를 고쳐 다시 빌드하면 바뀌므로(학생이 받은 원래 판이 아니게 된다) 비용의 마지막 방어는 강의 중계 키의 한도다.

```bash
.venv314/Scripts/python.exe workspace/개발/scripts/course_phase_sign.py pbl <저장소 밖 비밀 키 파일> --expires 2026-12-31T23:59:59+09:00 --note "1기 PBL"
.venv314/Scripts/python.exe workspace/개발/scripts/course_phase_sign.py course <비밀 키 파일>    # 다시 수업 단계로
```

도구는 서명한 선언을 학생 PC와 같은 함수(`course_policy.load_phase`)로 먼저 읽어 보고, 공개 키가 `PHASE_KEYS`에 없거나(끝 `=` 유무와 상관없이 바이트로 비교) 기한이 이미 지났으면 선언 파일을 바꾸지 않고 멈춘다. 바뀐 `course_phase.json`을 커밋 · push하면 학생이 `git pull` 뒤 시작할 때 적용된다. 키 쌍 만들기(`keygen`)와 비밀 키 형식은 그 파일 머리에 있다.

## 5. 개발 · 강사 도구 (`workspace/개발/scripts/`, 사용법은 각 파일 머리)

| 하려는 일 | 명령 |
|---|---|
| 단위 · 통합 테스트 전부 | `. workspace/개발/scripts/host_libpq.sh; HYD_TEST_DSN=postgresql://postgres:postgres@127.0.0.1:<업무 DB 포트>/hyd_test HYD_TEST_PORTAL_URL=http://127.0.0.1:<포털 포트> PYTHONUTF8=1 .venv314/Scripts/python.exe -m pytest -c workspace/개발/pytest.ini workspace/개발/tests` — `hyd_test`로 시작하는 버리는 DB만 받는다(테스트가 지우고 다시 만든다). 그래프 · 시계열 · 서비스는 테스트가 버릴 컨테이너 · 하위 프로세스로 띄운다(conftest 머리말) |
| 수업 한 바퀴(실라버스 포털 실습을 학생처럼, 키 있는 · 없는 모드) | `.venv314/Scripts/python.exe workspace/개발/scripts/class_round.py --out 작업/<날짜>_<제목>/실행/<이름>` — 결과 `summary.md` 맨 위가 실라버스 행 × 네 축(지원 · 끝까지 안전 · 키 없는 PC · 여러 번)의 됨 · 안 됨 · 확인 못 함. 펌프 · 팬 사건은 실습 93(PBL 단계에서 AI까지) |
| 강사 AI 응답 저장 | `bash workspace/개발/scripts/record_replay.sh 작업/<날짜>_<제목>/실행/녹화`(키 필요, 처리 건 0인 새 상태에서) → `재생모드.md` |
| 개발용 호스트 워커 | `bash workspace/개발/scripts/run_worker_host.sh`(컨테이너 워커가 켜져 있으면 멈춘다 — 워커는 하나), 멈추기 `powershell -NoProfile -ExecutionPolicy Bypass -File workspace/개발/scripts/stop_worker_host.ps1`(워커 인증 파일 사본도 지운다). 포털 「에이전트 현황」이 호스트 워커를 보게 하려면 `compose.override.yaml`에 `services: process: environment: {WORKER_URL: http://host.docker.internal:<8097의 이 PC 포트>}` |
| AI 사용 한도에 닿았을 때(학생 화면 「…강사에게 알려 주세요」) | 업무 DB(psql · Supabase CLI)에서 PC 한도 `UPDATE hyd_course_grants SET calls=0, input_bytes=0, output_tokens=0 WHERE account='hyd';`, 한 단계만 `DELETE FROM hyd_course_runs WHERE account='hyd' AND todo_id='<작업 id>' AND state<>'OPEN';`. 비용 경계는 중계 키 한도라 풀어도 그대로다 |
| 온톨로지 생성물 다시 만들기 · 그래프 검사 | `.venv314/Scripts/python.exe workspace/개발/scripts/ontology_v2.py gen` · `validate` · `queries`(접속은 이 PC 스택 — 파일 머리) |
| 포털 id → 이름 사전 다시 만들기 | `portal_names.py` → `it/portal/www/names.json`(시작이 끝난 수업 그래프에서, 고정 재료로 — 파일 머리) |
| FUXA · Grafana 생성물 다시 만들기 | `build_fuxa_project.py` → `ot/fuxa/project.json`, `build_grafana_dashboard.py` → `it/grafana/provisioning/dashboards/hyd-trend.json` |
| 제공 문서 추출 · 검토 적재(명령줄) | `c3_ingest.py extract|commit … --out <폴더>`, 판단 채점 명령줄 `evaluate_judgment.py` |

## 6. 자주 나는 오류와 첫 조치

| 증상 | 첫 조치 |
|---|---|
| 시작이 4~5단계에서 「서비스 이름」을 대며 멈춤 | `docker compose logs <그 서비스>`. 지운 모듈을 다른 서비스가 아직 가져오는 경우는 테스트 `test_service_images.py`가 먼저 잡는다 |
| process `/healthz`가 503 | 본문의 `stopped_loops`(멈춘 반복 이름 · 까닭) · `errors`를 보고 `docker compose restart process` |
| 호스트 파이썬이 psycopg를 못 올린다(libpq DLL 차단) | `. workspace/개발/scripts/host_libpq.sh`를 먼저 source(서명된 libpq 사용 — 없으면 그 자리에서 알린다). Smart App Control은 끄지 않는다 |
| process가 에러 없이 다시 켜졌다(RestartCount 증가) | 커널 OOM 의심: `wsl -d docker-desktop -e sh -c "dmesg \| grep -i oom"` |
| 그래프 반영이 멈췄다 | `GET /api/graph-projections`의 `pending`(사건 · 판단) · `execution.rows` · `execution.conflicts`가 줄지 않음(충돌은 다시 보내지 않는다). 조회: `docker compose exec process python -m procsvc.projection_repair inspect --kind Incident --id <사건 id> --file /tmp/<이름>.json` → 비교를 확인한 뒤 같은 모듈의 `apply`(`--by --reason --request-id`)로 다시 반영 |
| 승인했는데 설비 응답이 없다 | 설비가 원격 수동이다 → 포털 결함 시뮬레이션 카드 **원격 자동** |
| FUXA 값이 `##.##` | `docker compose up -d --force-recreate fuxa-init` |
| 경보가 안 난다 | 감지기 상태 `curl -s 127.0.0.1:8092/api/detector/state`의 `assets.<설비>.patterns.<패턴>.phase` — 후보가 설비 시간 60초 유지돼야 경보(감지기 체크포인트는 경보 때와 5초마다) |
| 보전비 지표가 「부분 실적」 | 조치 뒤 점검 작업지시는 승인한 조치의 SOP(예: 팬 최대 운전 SOP-COOL-11)를 달고 나간다(`work_orders.py`). 그 SOP가 업무 DB 정비 표준 작업표에 없으면 보전비 지표는 「부분 실적」이고 까닭에 그 SOP 이름이 적힌다(`kpi.py`). 작업비의 원문 출처가 없어 표준 작업표에 값을 넣지 않는다 |
| 포털 도구 연결이 서버를 거절한다 | HTTP 주소 서버만 받는다(명령형 stdio는 「명령형(stdio) 서버는 포털에 등록하지 않습니다 …」로 거절 — 명령형 실습은 모두 VS Code에서 연결하고 포털에 등록하지 않는다). 학생 서버 주소는 host.docker.internal · 사설 · 공인 주소를 받고, 루프백(localhost · 127.0.0.1 · ::1 — process 컨테이너 자신)과 링크로컬 · 미지정 · 멀티캐스트는 어떤 표기(10진 · 8진 숫자 IP 포함)로 적어도 거절한다(`mcp_check.address_problem`) |
| 포털 화면을 고치며 바로 보기 | 포털은 이미지로 굽는다(실행 중 손댄 파일이 옛 판 서비스 앞에 보이지 않게). 고치며 볼 때만 `compose.override.yaml`에 `services: { portal: { volumes: ["./it/portal/www:/usr/share/nginx/html:ro", "./it/portal/nginx.conf:/etc/nginx/templates/default.conf.template:ro"] } }` |
| 포털 → 서비스 길 | 화면은 같은 출처 `/svc/<서비스>/`만 부른다(nginx `it/portal/nginx.conf` — 크기 · 시간 한도, 꺼진 서비스는 JSON 502). 개발 도구는 서비스 포트를 그대로 써도 된다 |
| 배속(`TIME_SCALE`, 기본 20)을 바꾼다 | `compose.override.yaml`에 plant-sim · detector · process의 `TIME_SCALE`을 함께 적고, 감지기는 `DETECTOR_STATE_PATH: /data/detector-scale<N>.sqlite3`도(저장 상태의 배속이 다르면 감지기가 켜지기를 거절한다). agent · dmn-mcp는 process `GET /api/time-scale`에서 읽는다. 수업 압축 `PROCESS_WAIT_COMPRESSION`(기본 60)은 process에 적는다 |

## 7. 확인하지 못한 것 · 아직 정하지 않은 것

**확인 못 함**
- 설치 실행 파일(관리자 승인 창이 필요해 건너뜀), Mac 경로, 실제 PC 재부팅 뒤 Docker Desktop 기동까지 포함한 시간.

**알고 두는 위험**
- 업무 DB 포트(이 PC 64322 등)는 `supabase start`가 PC 밖(0.0.0.0)에도 연다 — 비밀번호는 기본값이고 Supabase CLI에는 묶을 주소 설정이 없다. 지금은 수업 PC 방화벽에 맡긴다.
- 공용 PC: 설치가 사용자 폴더 밖 저장소에 「로그인한 모든 계정 수정」 권한을 주므로(`scripts/install_windows.ps1`) `.env`의 중계 키를 다음 계정도 읽는다. 학생 한 명 전용 PC면 문제없다. 근본 해결은 키를 계정별 자리로 옮기는 것 — 키를 읽는 곳 `scripts/hyd_env.py`와 README 안내를 함께 바꾼다.

**정한 것과 되돌리는 법**
- PBL 단계 선언의 서명 키: 제공 문서 추출 묶음에 서명한 강사 키를 함께 쓴다(`course_policy.PHASE_KEYS`, 서명 영역이 달라 서로 재사용은 안 됨). 따로 쓰려면 `course_phase_sign.py keygen <저장소 밖 파일>` 뒤 화면에 나온 공개 키로 `PHASE_KEYS`를 바꾼다.
- 녹화가 없는 AI 단계(교대 보완 2 · 재작업 · 재평가)는 `재생모드.md` 7절.
- 지운 것 — 로그인 연결: process `mcp_oauth.py`(외부 계정 로그인 OAuth · 접속키 · 간편 연결 API `/api/mcp/connections*`) · `mcp_worker_relay.py` · `oauth_access_log.py` · `worker_credentials`의 중계 승인, 포털 `mcpConnections.js · .css`와 도구 연결 화면의 「서비스 연결」 자리, compose `HYD_MCP_OAUTH_*`, 워커 `runtime_credentials.py`. 까닭: 암호화 키 파일을 만드는 곳이 없어 모든 PC에서 503이었고 실라버스 · 교재 · 랩에 쓰는 곳이 0, 토큰이 필요한 서버는 `${SECRET:이름}` + 비밀 값 표로 된다. 되살리려면 main `04efb988^`에서 그 파일들을 가져오고 키 파일을 process 시작 때 만드는 곳을 새로 둔다.
- Supabase Studio · REST · 로그인(업무 DB의 쓰지 않는 컨테이너)은 꺼 두었다. 개발 PC에서 켜려면 `it/supabase/config.toml`의 해당 칸(켜면 그 파일 머리의 문제가 그 PC에서 되살아난다).
- 경계 타이머의 시계: 그 타이머가 감싼 일의 시계(사람 일 = 벽시계, 설비 · 대기 = 배속). 되돌리려면 `procsvc.engine.timer_scale` 한 곳.

**사용자 결정 대기(선택지 · 지금 상태)**
- 교대 인수인계 정의가 두 벌이다(학생이 가져오는 `ShiftHandover`, 제공 정의 `shift_handover` — 같은 녹화 자리). 제공 정의를 지우면 관리할 곳이 줄지만 녹화 도구 · 교재 참조를 함께 고쳐야 한다.
- 학생 도구 서버가 컨테이너 망 안 서비스 이름(process · supabase · enterprise-mcp 등)을 가리키는 것을 막을지 — 지금: 막지 않음(기준 서버와 같은 이름 자리라 PBL에서 학생이 기준 서버를 직접 등록해 보는 길). 막으려면 `mcp_check.address_problem`에 compose 서비스 이름 거절을 더한다.
- 「그다음 예정된 정비 시간」을 월간 창으로 볼지 — 바꾸면 교재 값 1,950 / 1,959 / 2,230 h가 바뀐다(덱 `제작도구/온라인/decks/integrated/day10/통합반_10일차.md` 781 · 788줄 등, 결정이 나면 다시 잰 값으로). PR-7.2 문장과 표 중 어느 쪽이 목표 재고 정의인지, 정기 정비 부품 예약에 입고 예정을 셀지.
- C 구매의 납기 지연 가지(`skill:delay-delivery`): 업무 거래와 process 입고 대기 가지(`service_parts` 「지연 n일」)는 있으나 부르는 버튼이 없어 수업에서 밟을 수 없다. 선택지: 포털 버튼으로 다시 연결(비해피 가지가 생김 — 포털 · process 시나리오 · 교재) / 거래와 가지를 지움. 지금: 그대로 둠.
- XG5000(LS 산전 PLC 편집 프로그램, 394 MB): README · `scripts/install_windows.ps1`이 설치를 안내하지만 이 과정 실라버스 · 실습에 쓰는 곳이 0이다(「직접 설치」 결정은 선행 SCADA 교육 때문일 수 있음). 선택지: 그대로 / 두 줄을 지움.
- 수업 데이터 보관 기간: 처리 건 · 처리 기록 · 알림 · 사건 스냅숏을 지금은 지우지 않는다(데이터 비우기는 §3). 선택지: 그대로 / 기간을 정해 지움.
- 순위의 선례 몫: 미리 넣은 예시 사례(seeded)만 세는데 수업 그래프에는 그런 사례가 없어 늘 0이다(교재 03회차 「해당 선례가 반영되지 않으면 그 성분도 영」과 같음). 선택지: (가) 지금대로 (나) 승인으로 쌓인 사례를 셈 — `templates/t3_precedents.cypher`의 `seeded = true` 한 줄, 같은 처리 건을 다시 하면 순위가 바뀌어 녹화 재생 · 교재 수치가 흔들린다 (다) 수업 지식 id로 예시 사례를 서명 묶음과 함께 넣음 (라) 선례 성분을 정책 · 화면 · 교재에서 지움. 지금: (가).
- 강사 서명 묶음(`course_extractions.json`) 재검토: PM-02 「씰 키트 가용 0 → 시행 안 함」이 패키지 SOP에 걸려 What-if가 반응하지 않음, HM-8 팬 점검 규칙이 원문에 없는 FAN_VIBRATION 조건, 원문에 없는 절차 번호(SOP-PM-2-9 · SOP-PR7-7) 표시, HM-8 벨트 교체(SOP-FAN-12)를 고르는 후보 규칙이 없어 카드로 나오지 않음. 선택지: 강사가 고쳐 다시 서명 / 그대로(지금 — 실제 승인 판단은 `maintenance_policy`가 키트 부족을 막는다). 같은 재서명 거리: 설비 감지 패턴(냉각 성능 저하 등)의 근거를 원문 절 노드(HM-8.3 · PM-2.9 · PM-2.10 · PR-7.2)에 직접 잇기 — 절 노드 id 가 PC마다 다르게 만들어져(`manual:<테넌트 해시>:<문서 id>:…:section:…`, 첫 적재 문서 id 는 임의값) 시드가 잇지 못한다. 지금: 시드의 출처 노드가 그 절 번호를 가리킨다(`ks:monitoring-hm-8` · `-pm-02` · `-pm-02-fan` · `-pr-07`, 문서에 없는 기준만 `ks:monitoring-standard`). 선택지: 강사가 패턴 근거를 서명 묶음에 넣어 다시 서명하고 수업 지식 적재가 그 근거를 그 절에 잇게 함 / 그대로(지금).
