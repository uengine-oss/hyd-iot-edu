# RUNBOOK — 시스템 켜기 · 확인 · 끄기와 개발 도구 (학생 PC · 강사 PC 공통)

학생은 `setup/`의 실행 파일 셋만 쓴다: **시작**(`시작.bat` · `시작.command`) → **점검**(`점검.bat` · `점검.command`) → **끄기**(`끄기.bat`). 각각 `scripts/start_all.sh` · `scripts/check_all.sh` · `scripts/stop_all.sh`를 부른다. 이 문서는 그 안에서 무엇이 도는지와 개발 · 강사만 쓰는 도구를 적는다. 명령은 **Git Bash** 문법이고 저장소 루트에서 실행한다.

## 0. 설치 (한 번)

- 학생 PC: `setup/설치.bat`(Windows, 관리자 승인 창이 뜬다) · `설치.command`(Mac). 기준 판은 `scripts/versions.txt` 한 곳(Docker Desktop · Node · Git · Python 3.13 이상(없으면 3.14.7) · WSL · VS Code). Supabase CLI는 따로 깔지 않는다 — 시작 · 끄기가 `npx supabase@<versions.txt의 SUPABASE_CLI>`로 부른다. Claude Code CLI는 AI 워커 이미지 안에 있다.
- 개발 PC만: 공식 Python 3.14로 `.venv314`를 만들고 `.venv314/Scripts/python.exe -m pip install -r workspace/requirements-dev.txt`. uv로 받은 파이썬은 Smart App Control에 막힌다.
- 학생이 `.env`에 넣는 것은 `LLM_API_KEY=` 한 줄(강의 중계 키)뿐이다. 나머지 `.env` 값은 시작이 정한다.

## 1. 켜기 — `scripts/start_all.sh`

| 단계 | 하는 일 |
|---|---|
| 1 Docker 확인 | 응답이 없으면 멈춤 |
| 2 `.env` · 이 PC 값 | `.env`가 없으면 `.env.example`을 복사. 키가 있으면 `AI_MODE=live`, 없으면 `replay`(강사가 저장한 응답 `it/agent-worker/replay/` 재생). process 호출 값 · 명령 지문 키를 정한다. 프로젝트 이름 · 포트는 이 PC 값(`.hyd-runtime/project.json` · `ports.json`, 업무 DB는 `it/supabase/.env`) — 같은 폴더면 이어받고, 다른 프로그램이 쓰는 포트는 피한다. **git이 추적하는 파일은 고치지 않는다** |
| 3 업무 DB | `supabase start` 뒤 새 마이그레이션 적용(`migration up --local`) |
| 4 빌드 · 기동 | `docker compose up -d --build` — 처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있다 |
| 5 서비스 확인 | 최대 3분, 포털 응답까지 |
| 6 수업 흐름 A · B · C | `scripts/c3_flows.py ensure` — 이미 수업 흐름이면 건너뜀(정본 `it/process/procsvc/course_flows.json`) |
| 7 수업용 기본 지식 | `scripts/class_knowledge.py ensure` — 검토한 HM-8 · PM-02 · PR-07을 처음 한 번(AI 없이) |
| 8 AI 단계 확인 | 키 없음: 저장 응답이 있는지. 키 있음: process가 받은 중계 주소 · 키로 강의 중계에 닿는지(거절 · 무응답이면 멈춤) |

- 두 번 눌러도 시작은 하나만 돈다. 두 번째 시작은 아무것도 바꾸지 않는다.
- 실측(2026-10-30, 이 PC, 이미지 있음, 키 없음): 처음 1분 45초 · 연달아 두 번째 1분 40초 · 끈 뒤 다시(코드가 바뀌어 다시 빌드) 2분 52초. 세 경우 모두 시작 뒤 `git status` 변화 0.
- 강사 AI 응답 저장은 `--record`(키 필요) — 보통 `workspace/개발/scripts/record_replay.sh`가 부른다(§5).

## 2. 확인 — `scripts/check_all.sh`(`scripts/check_stack.py all`)

서비스 응답 → 쿨러 사건 한 바퀴(경보 → 처리 건 → AI 판단 · 제안 → 승인 → 냉각 명령 → 재관측 → 작업지시 → 결과 보고) → 점검이 연 처리 건 닫기 · 설비 되돌리기 → 강의 중계(키 있는 PC만). 실측 약 2분(2026-10-30, 키 없음).

떠 있어야 하는 것(2026-10-30 실측): compose 서비스 24개 = 계속 떠 있는 21개(전부 healthy) + 한 번 돌고 끝나는 3개(`fuxa-init` · `topic-init` · `kg-seed`, Exited 0이 정상) + Supabase 컨테이너 9개(`supabase_*_<프로젝트 이름>`). 선택 프로필 `monitor`(prometheus) · `tools`(redpanda-console)는 기본으로 뜨지 않는다.

```bash
docker compose ps -a
cat .hyd-runtime/ports.json     # 기본 포트 → 이 PC의 바깥 포트(다른 프로그램과 겹쳐 옮긴 포트 포함)
```

화면 주소(기본 포트, 옮겼으면 `ports.json`의 값): 포털 8088 · Neo4j Browser 7474 · Grafana 3000 · FUXA 1881 · EMQX 18083 · Supabase Studio 54323.

## 3. 끄기 — `scripts/stop_all.sh`

이 폴더의 compose 서비스(선택 프로필 포함)를 멈추고 업무 DB를 끈 뒤, 켜진 컨테이너가 0개인지 확인한다. 데이터는 남는다. 실측 15.6초(2026-10-30).
데이터를 지우는 명령은 따로 있다 — `docker compose down -v`(시계열 · 그래프 · process 볼륨), `supabase stop --no-backup`(업무 DB 볼륨). 수업 자료 초기화일 때만 쓴다(강사 결정).

## 4. 수업 단계와 PBL 열기

수업 경계 규칙은 `it/process/procsvc/course_policy.py` 한 곳에 있다(화면은 `GET /api/course-access`, 워커는 `POST /internal/worker/course-decision`으로 읽는다). 단계는 강사 서명 선언 `it/process/procsvc/course_phase.json`으로 정한다 — 없으면 수업 단계, 서명 · 형식이 틀리면 process가 뜨지 않는다(학생이 자기 PC에서 바꿀 수 없다). PBL은 기한이 필수이고 지나면 수업 단계로 읽는다.

```bash
python workspace/개발/scripts/course_phase_sign.py pbl <저장소 밖 비밀 키 파일> --expires 2026-12-31T23:59:59+09:00 --note "1기 PBL"
python workspace/개발/scripts/course_phase_sign.py course <비밀 키 파일>    # 다시 수업 단계로
```

바뀐 `course_phase.json`을 커밋 · push하면 학생이 `git pull` 뒤 시작할 때 적용된다. 키 쌍 만들기(`keygen`)와 비밀 키 형식은 그 파일 머리에 있다.

## 5. 개발 · 강사 도구 (`workspace/개발/scripts/`, 사용법은 각 파일 머리)

| 하려는 일 | 명령 |
|---|---|
| 단위 · 통합 테스트 전부 | `. workspace/개발/scripts/host_libpq.sh; HYD_TEST_DSN=postgresql://postgres:postgres@127.0.0.1:<업무 DB 포트>/hyd_test HYD_TEST_PORTAL_URL=http://127.0.0.1:<포털 포트> PYTHONUTF8=1 .venv314/Scripts/python.exe -m pytest -c workspace/개발/pytest.ini workspace/개발/tests` — `hyd_test`는 버리는 DB다(테스트가 지우고 다시 만든다, 이름이 `postgres`면 거절). 두 변수가 없으면 그 테스트가 무엇이 없는지 내고 실패한다 |
| 수업 한 바퀴(포털 실습을 학생처럼) | `class_round.py` |
| 펌프 · 팬 사건 확인 | `scenario_pump_fan_test.py`(PBL 단계에서만) |
| 강사 AI 응답 저장 | `bash workspace/개발/scripts/record_replay.sh`(키 필요, 처리 건 0인 새 상태에서) → `재생모드.md` |
| 개발용 호스트 워커 | `bash workspace/개발/scripts/run_worker_host.sh`(컨테이너 워커가 켜져 있으면 멈춘다 — 워커는 하나), 멈추기 `powershell -NoProfile -ExecutionPolicy Bypass -File workspace/개발/scripts/stop_worker_host.ps1` |
| 시험이 남긴 진행 중 처리 건 정리 | `cleanup_residue_instances.py --before <ISO 시각> --out <폴더>`(목록 · 백업), 확인 뒤 `--apply` |
| 포털 id → 이름 사전 다시 만들기 | `portal_names.py` → `it/portal/www/names.json` |
| FUXA · Grafana 생성물 다시 만들기 | `build_fuxa_project.py` → `ot/fuxa/project.json`, `build_grafana_dashboard.py` → `it/grafana/provisioning/dashboards/hyd-trend.json` |

떠 있는 스택을 쓰는 테스트 · 도구가 도는 동안 `docker compose build/up/restart`를 하지 않는다(process가 다시 켜져 끊긴다).

## 6. 자주 나는 오류와 첫 조치

| 증상 | 첫 조치 |
|---|---|
| 시작이 4~5단계에서 「서비스 이름」을 대며 멈춤 | `docker compose logs <그 서비스>`. 지운 모듈을 다른 서비스가 아직 가져오는 경우는 테스트 `test_service_images.py`가 먼저 잡는다 |
| process `/healthz`가 503(`consumer_dead`) | `docker compose restart process` |
| 호스트 파이썬이 psycopg를 못 올린다(libpq DLL 차단) | `. workspace/개발/scripts/host_libpq.sh`를 먼저 source(서명된 libpq 사용). Smart App Control은 끄지 않는다 |
| process가 에러 없이 다시 켜졌다(RestartCount 증가) | 커널 OOM 의심: `wsl -d docker-desktop -e sh -c "dmesg \| grep -i oom"` |
| 그래프 반영이 멈췄다(process `/healthz`의 `case_projection_pending`이 줄지 않음, 로그 `ProjectionConflict`) | 조회: `docker compose exec process python -m procsvc.projection_repair inspect --kind Incident --id <사건 id> --file /tmp/<이름>.json` → 비교를 확인한 뒤 같은 모듈의 `apply`(`--by --reason --request-id`)로 다시 반영 |
| 승인했는데 설비 응답이 없다 | 설비가 원격 수동이다 → 포털 결함 시뮬레이션 카드 **원격 자동** |
| FUXA 값이 `##.##` | `docker compose up -d --force-recreate fuxa-init` |
| 경보가 안 난다 | 감지기 상태 `curl -s 127.0.0.1:8092/api/detector/state`의 `phase` · `slope` — 후보가 설비 시간 60초 유지돼야 경보 |
| 배속(`TIME_SCALE`, 기본 20)을 바꿨다 | plant-sim · detector · process · agent에 함께 준다. 감지기 상태 파일은 배율별로(`DETECTOR_STATE_PATH=/data/detector-scale<N>.sqlite3`) |

## 7. 이 문서가 확인하지 못한 것

- 설치 실행 파일(관리자 승인 창이 필요해 2026-10-30 확인에서 건너뜀), Mac 경로, 실제 PC 재부팅 뒤 Docker Desktop 기동까지 포함한 시간.
