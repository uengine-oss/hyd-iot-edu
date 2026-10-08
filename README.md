# hyd-iot-edu — 유압설비 IoT-SCADA 학생용 프로토타입

**현재 상태(2026-10-08):** 목표와 완료 조건은 [GOAL](docs/handoff/GOAL.md) 상단 "완주 목표"의 DoD 7개다. DoD 1(회차 25개 실행 장면·제작자 증거)·2(쿨러·펌프·팬 인스턴스 완주)·3(참고 레포 구조 변경 반영)·5(회귀 18/18)는 검증됨, 4(포털 UI/UX)는 사용자 판정 대기, 6(재부팅 뒤 10분 기동)은 미실측이다. 재개 위치·근거는 [HANDOFF](docs/handoff/HANDOFF.md) §9, 기동·확인·종료는 **[RUNBOOK](docs/RUNBOOK.md)**, 회차별 실행 절차는 [docs/sessions/](docs/sessions/README.md)다. 아래의 L1~L9 설명은 2026-09-30 첫 판에서 시작한 개요이며, 바뀐 곳은 이 문서에서 고쳤다.

`유압설비_IoT-SCADA_아키텍처_v3.pdf` 4쪽 구조도(L1~L9, OT·DMZ·IT)를 학생 노트북에서 `docker compose up` 한 번으로 돌리는 구성입니다.
IoT·SCADA 층의 무거운 제품(Flink+ONNX, Kafka Connect, EdgeX, Alertmanager/Mailpit, MinIO)은 **같은 이름·같은 메시지 계약을 지키는 작은 파이썬 서비스(대역)**로 바꿨고,
가벼운 실제 제품(EMQX, FUXA, Redpanda, TimescaleDB, Grafana, Neo4j, Supabase)은 그대로 씁니다. 이것은 첫 커밋부터 의도한 선택이며 설계서 v3와 다르다(2026-10-08 사용자 결정: 현 구조 유지, DECISIONS 106; 대조 보고 `docs/보고/설계서v3_대비_실제구현.html`). 제품 교체 방향은 정했으나 보류다(DECISIONS 107).
L9의 프로세스 엔진은 ProcessGPT 제품을 설치하지 않고 제품의 데이터 모양(`proc_def`·`bpm_proc_inst`·`todolist`·`events`, 에이전트 작업 `userTask + agentMode`)을 따라 HYD가 구현했다(`docs/handoff/REFERENCE_ADOPTION.md`).

**강의의 초점은 L7~L9입니다.** L1~L6은 경보가 나면 팬을 올리는 즉각 제어까지입니다. L7 온톨로지 v2는 BSC(관점 · 전략 목표 · 성과 지표) → BPMN 프로세스 → 리소스 → 설비 진단(ISO 13374) → 조치 방법 = 스킬 = SOP · DMN 규칙(온도 · 압력 임계값) 계층을 잇고, L8 에이전트는 이상 원인의 고장 유형에 매칭된 SOP 스킬을 규칙 · 예측 · BSC 득실 · 선례로 골라 카드 2~3장을 내밀며, L9는 사람이 고른 카드를 승인 역할에 따라 PLC와 기업 시스템에서 실행합니다. 설계는 [docs/ontology/schema-v2.md](docs/ontology/schema-v2.md), 클래스 표는 [docs/ontology/class-table.md](docs/ontology/class-table.md), 클래스 연관 그림은 [docs/ontology/ontology-classes.svg](docs/ontology/ontology-classes.svg), 스키마 파일은 [it/neo4j/v2/](it/neo4j/v2/)에 있습니다. v1 설계(전사 판단 시나리오)는 [docs/l7-l9-ontology-decisions.md](docs/l7-l9-ontology-decisions.md)에 기록으로 남겨 두었습니다.

기동은 [RUNBOOK](docs/RUNBOOK.md) §1이 정본이다(Git Bash, 저장소 루트). 요약:

```
cp .env.example .env                 # 최초 1회. 강의 배포본은 .env에 PROCESS_MODE=instance, ENTERPRISE_BACKEND=supabase, PROCESS_MEM_LIMIT=768m (RUNBOOK §0)
( cd it/supabase && supabase start ) # 업무 DB · 프로세스 저장소 (instance 모드에 필요)
docker compose up -d --build          # 기본 7 프로필 (.env의 COMPOSE_PROFILES)
docker compose up -d enterprise-mcp dmn-mcp   # 에이전트용 MCP 서버 2개
bash scripts/run_worker_host.sh &     # 호스트 워커(Claude Code, 구독 로그인) — 실제 에이전트가 작업을 집게 하려면 process·agent에 AGENT_BRIDGE=off
```

동작 확인은 회귀 러너 하나로 한다(`scripts/run_regression.py` 머리말, RUNBOOK §3): `.venv314/Scripts/python.exe scripts/run_regression.py --group core --out .evidence/reaudit/reg-<태그> --kill-workers --restart-workers 2`(호스트 워커를 끈 상태의 실제 스택 20배속 검사 묶음 — 쿨러·펌프/팬·효과 보상·지식→판단·스키마 검증 등), 워커 2개를 켠 뒤 `--group worker`(업무·규칙·시계열 질문, 매뉴얼 인제스천, 워커 임대, 실행 중 취소). 10분이 넘는 측정이다. `scripts/scenario_test.py`는 **legacy 모드(`PROCESS_MODE=legacy`) 전용**이며 instance 모드에서는 사람 결정이 409로 막혀 실패하는 것이 정상이다 — 근거로 쓰지 않는다(HANDOFF A115).

포털: http://127.0.0.1:8088 — 왼쪽 메뉴는 세 묶음이다(2026-10-08, A122 개편. 화면 문구는 `it/portal/www/ui.js`의 `UI.terms` 한 곳에서 바꾼다).

| 묶음 | 메뉴 | 보는 것 |
|---|---|---|
| | 홈 | 설비 · 데이터 · AI 연결을 한 장에 그린 그림과 상태 |
| | 시스템 구성 | 층별 구성요소(실제 이름: detector · Redpanda 등)와 진입점 · 상태 |
| 설비 | 결함 시뮬레이션 | 쿨러 · 펌프 · 팬 결함 주입, 운전 모드, 수동 조작 |
| | 이상 확인 · 조치 | 설비 3기 카드, 사건별 조치 과정 시간순 카드 |
| | 실시간 모니터링 | Grafana 추세와 경보 · 조치 주석 |
| 판단과 처리 | 지식 지도 | 온톨로지 v2 계층과 이상 패턴별 강조 경로 |
| | 조치 방법 | 조치 방법(SOP 스킬)의 단계 · 매칭된 고장 유형 · 걸리는 규칙, 편집 |
| | 조치 판단 규칙 | 이상 패턴을 골라 판단 실행: 조건 → 요약 → 원인 → 후보 카드 비교, 점수 계산 · 적용 규칙 · 판단에 쓴 값은 접기 |
| | 승인과 실행 | 실제 정의에서 그린 흐름도, 판단 목록, 기업 시스템(CMMS · ERP 등) 실행 결과 |
| | 처리 건 | 프로세스 인스턴스 목록 · 에이전트 활동 · 상세(결과 / 흐름 / 기록 3탭), 내 차례(사람 작업 폼) |
| 관리 | 지식 관리 | 매뉴얼 등록 → 에이전트 추출 → 검토 → 적재, 문서 배치 카드와 "이 문서로 답할 수 있는 질문"(골든 퀘스천) 보고, 업무 데이터 연결(DDL), 질의 보기 |
| | 관리 | 원천 이벤트 접수 · 오류 확인 · 재시도, 프로세스 정의 등록 · 버전 선택 · 실행 |

## 진입점

| L | 구성요소 | URL | 원래 아키텍처 |
|---|---------|-----|--------------|
| L9 | 설비 포탈(guide-app) | http://localhost:8088 | guide-app |
| L9 | process (프로세스 엔진: 정의 · 인스턴스 · 할일 · 승인, `PROCESS_MODE=instance`) API | http://localhost:8080/docs | Process GPT |
| L8 | 호스트 워커(Claude Code, `scripts/run_worker_host.sh`) | http://localhost:8097/health (둘째 워커 8098) | ProcessGPT agent-sdk 워커 |
| L8 | enterprise-mcp · dmn-mcp (`cliagents` 프로필, `/docs` 없음) | 8199 · 8198 | 업무 DB 읽기 · DMN 판단 MCP |
| L9 | Supabase Studio (업무 DB · 프로세스 저장소) | http://localhost:54323 | Supabase |
| L9 | enterprise-sim (ERP · MES · CMMS · QMS · SCM · EMS 목업) | http://localhost:8095/docs | SAP · MES · CMMS · QMS 등 |
| L8 | agent API (트레이스 · 전사 판단 · 온톨로지 조회) | http://localhost:8091/docs | LangGraph · mcp-kg/tsdb/prom/ent · LiteLLM |
| L7 | Neo4j Browser (neo4j / hydpass123) | http://localhost:7474 | Neo4j + n10s |
| L6 | FUXA 웹 SCADA (OT) | http://localhost:1881 | FUXA |
| L6 | Grafana (익명 Viewer, admin/admin) | http://localhost:3000/d/hyd-trend | Grafana |
| L6 | Prometheus (선택: `monitor` 프로필) | http://localhost:9090 | Prometheus · Alertmanager |
| L5 | connect-sink API · TimescaleDB 5432 (hyd/hyd) | http://localhost:8094/docs | Kafka Connect JDBC Sink · TimescaleDB |
| L4 | detector API | http://localhost:8092/docs | Apache Flink CEP + ONNX |
| L3 | Redpanda Console (선택: `tools` 프로필) | http://localhost:8085 | Apache Kafka |
| L3 | connect-ingest (DMZ) · cmd-gateway (DMZ) | http://localhost:8093/docs · http://localhost:8090/docs | Kafka Connect MQTT Source · 명령 게이트웨이 |
| L2 | EMQX 대시보드 (admin / public123, 첫 로그인 시 변경 요구 가능) | http://localhost:18083 | EMQX · EdgeX |
| L1 | plant-sim (설비 3기 + soft-PLC) API | http://localhost:8000/docs | hyd-sim · soft-plc · 고속 DAQ |

## 시나리오 (설계서 9절)

instance 모드에서는 경보 한 건이 **처리 건(프로세스 인스턴스)** 하나를 열고, 그 안에서 에이전트 작업 4개(진단 · 후보 · 규정 · 순위) → 사람 선택 → PLC 명령 → 효과 확인 → 정비 요청 → 종결이 할일(todolist) 행으로 진행된다(실행 정의 2.2, `it/process/definitions/anomaly_response_v22.json`). 쿨러 기준 따라가기는 `docs/scenario-walkthrough.md`, 펌프 · 팬은 `docs/sessions/20`·`21`.

1. 포털 **결함 시뮬레이션**에서 HYD-01 "쿨러 열화 주입".
2. 유온 TS1이 오르고, FUXA에 값과 알람이 보인다.
3. detector(L4)가 `alerts RAISE` → cmd-gateway가 `plant/hyd01/alert`로 중계 → FUXA IT 경보 표시등.
4. 처리 건이 열리고 에이전트 작업 4개가 실행된다(`AGENT_BRIDGE=off`면 호스트 워커의 Claude Code, `legacy`면 서버 안의 결정론 에이전트). 에이전트는 신선도 확인 → Neo4j 원인 후보 → TimescaleDB 증거 → 조치 · SOP · 매뉴얼 → 가드레일 → 카드 제출 순으로 근거를 모은다.
5. 포털 **이상 확인 · 조치**(또는 **처리 건**의 내 차례)에서 담당자가 카드를 골라 승인한다. 권한 없는 역할(운전원)은 403, 생산관리자 선택은 진행된다.
6. process(L9)가 `action.cmd` 발행 → cmd-gateway 검증 5종 → `cmd/auto` → PLC 검증 → `status ACK DONE`.
7. 유온이 내려가 `alerts CLEAR` → 15분 효과 확인(재관측, 시간 배율 적용) → 쿨러 세척 정비 요청(작업지시) → 종결. Grafana 추세에 주석으로 남는다.

부정 시나리오: PLC가 `REMOTE_MANUAL`이면 게이트웨이가 거부하고 감사 로그에 사유가 남는다. 조치 없이 두면 65 ℃에서 인터록 트립.

## 단계별 실습 (Compose 프로필 = 설계서 11절 M1~M7)

| 단계 | 프로필 | 올라가는 것 | 확인 |
|------|--------|-------------|------|
| M1 | `ot` | plant-sim, emqx, fuxa(+init) | FUXA에 1 Hz 값, 팬 입력으로 속도 변경, 65 ℃ 트립 |
| M2 | `backbone` | redpanda(+topic-init), connect-ingest, connect-sink, timescaledb, grafana | Grafana 추세 (토픽 브라우저는 `tools` 프로필의 Redpanda Console) |
| M3 | `detect` | detector, cmd-gateway | 열화 주입 → RAISE → FUXA 알람, 복구 → CLEAR |
| M4 | `monitor` (선택) | prometheus | 6개 서비스 /metrics 수집. 경량 기본값에서는 빠져 있다 |
| M5 | `knowledge` | neo4j, kg-seed | 온톨로지 v2 적재(고장 유형별 SOP 스킬 목록 출력), T1/T2/T3 템플릿 |
| M6 | `agent` + `enterprise` | agent, enterprise-sim | 근거 인용 가이드 카드, 조치 카드 판단(DMN 규칙 · 예측 · BSC 득실 · 선례) |
| M7 | `process` | process, portal | 승인 → ACK → 재관측 → 종결, REMOTE_MANUAL 거부, 역할 기반 전사 판단 승인 → 기업 시스템 실행 |

```
docker compose --profile ot up -d --build              # M1만
docker compose --profile ot --profile backbone up -d   # M1+M2
```

### 가볍게 돌리기 (학생 노트북)

기본값이 경량 구성입니다. 전체 기동 시 컨테이너 메모리 합계는 약 1.4 GB입니다.

- `DAQ_PROFILE=lite`(기본): 지속조건·경사 계산에 쓰는 TS1·CE·PS1·FS1·VS1·LoadSP는 매초 발행합니다. 나머지 태그는 변화와 10초·30초 하트비트에 따라 발행하며 100 Hz 파형은 보내지 않습니다. 전체 태그·파형을 수집하려면 `.env`에서 `full`로 바꿉니다.
- Prometheus(`monitor`)와 Redpanda Console(`tools`)은 선택 프로필입니다. 필요하면 `.env`의 `COMPOSE_PROFILES`에 추가합니다.
- 모든 서비스에 메모리 상한과 로그 순환(5 MB × 2)이 걸려 있고, 원시 시계열은 3일 보존 · 2시간 뒤 압축입니다.
- WSL 전체 상한은 `docs/wslconfig.example`을 `%UserProfile%\.wslconfig`로 복사한 뒤 `wsl --shutdown`으로 적용합니다.

측정 전후는 [docs/l7-l9-ontology-decisions.md](docs/l7-l9-ontology-decisions.md) 7절에 있습니다.

프로필은 누적된다: `detect`·`agent`·`process`는 `backbone`(Kafka 토픽 생성 `topic-init`)에 의존하므로 `--profile backbone`을 함께 주거나, `.env`의 `COMPOSE_PROFILES`(기본 전체)를 그대로 쓴다.
서비스 하나만 다시 빌드할 때도 같은 이유로 `docker compose up -d --build process`처럼 프로필 옵션 없이(.env 사용) 실행한다.

## 저장소 구조

```
compose.yaml  .env(.example)  requirements-dev.txt  pytest.ini
common/hydcommon/   토픽 이름·페이로드 스키마·MQTT/Kafka 헬퍼 (모든 서비스가 복사)
ot/   plant-sim/ (thermal.py 물리 · plc.py soft-PLC · edge.py MQTT · daq.py 발행 프로필)   fuxa/ (build_project.py → project.json, init.py)
dmz/  connect-ingest/   cmd-gateway/ (validate.py 검증 5종)
it/   redpanda/ detector/ (features.py · cep.py) connect-sink/ timescaledb/ grafana/ prometheus/
      neo4j/ (v2/ 스키마 · 인스턴스 · OWL, templates/t0~t3, v1/ 보관) agent/ (tools/mcp_*.py · card.py · guardrail.py · llm.py · cards.py · decide.py)
      process/ (procsvc/ 엔진 · 인스턴스 · 정의 등록 · 매뉴얼 인제스천, definitions/ 실행 정의 2.2) enterprise-sim/ (entsim/data.py · state.py) portal/www/ (ui.js 문구 사전 · flow.js · components.css)
      agent-worker/ (호스트 워커: runner · bridge · outcome)  enterprise-mcp/  dmn-mcp/  supabase/ (migrations · seed.sql)
tests/   단위 테스트 (pytest)
scripts/ run_regression.py (회귀 러너 core · worker)  run_scenario_evidence.py (instance 쿨러)  run_scenario_pump_fan_evidence.py  run_worker_host.sh · stop_worker_host.ps1  host_libpq.sh  scenario_test.py (legacy 모드 전용)
video/   scenes.py · narration.py · record_demo.py   → docs/video/hyd-iot-edu-demo.mp4
docs/    RUNBOOK.md  sessions/ (25회차 실행 장면)  curriculum-75h.md  handoff/ (GOAL · HANDOFF · DECISIONS …)  student-guide.md  scenario-walkthrough.md  definition-authoring.md  topics.md  payload-schemas/  wslconfig.example
```

## 테스트

호스트 파이썬은 `.venv314`(Python 3.14 공식 설치본, RUNBOOK §0)이고, psycopg가 서명 없는 DLL 차단에 걸리지 않게 먼저 `. scripts/host_libpq.sh`를 source한다(HANDOFF A105).

```
. scripts/host_libpq.sh
.venv314/Scripts/python.exe -m pytest -q             # 단위 (2026-10-08 A131 기준 1,210)
.venv314/Scripts/python.exe scripts/run_regression.py --group core --out .evidence/reaudit/reg-<태그> --kill-workers --restart-workers 2
.venv314/Scripts/python.exe scripts/run_regression.py --group worker --out .evidence/reaudit/reg-<태그>   # 워커 2개 필요
```

`scripts/scenario_test.py`는 `PROCESS_MODE=legacy` 스택에서만 쓴다(instance 모드에서는 409로 막혀 실패하는 것이 정상, HANDOFF A115).

## LLM

두 축이 따로 있다(DECISIONS 69, HANDOFF §9 A073 "정정"·"내부 LLM → GPU 실측").

- **에이전트 작업(워커)**: Claude Code(Opus, 구독 로그인)를 호스트 워커가 서브프로세스로 부른다(`scripts/run_worker_host.sh`, `CLI_MODEL=opus`). Codex 경로는 코드·기록으로만 남아 있다.
- **시스템 내부 LLM 호출**: 한 곳, `it/agent/agentsvc/llm.py summarize`(가이드 카드 서술 요약)뿐이다. 제작자 배포본은 **사내 GPU 모델 서버(SGLang, OpenAI 호환)**를 쓴다 — `.env`의 `OPENAI_BASE_URL`(GPU 서버 `/v1`), `LLM_MODEL`(그 서버의 모델명), `LLM_API_KEY`(비OpenAI 엔드포인트 키, 없으면 `OPENAI_API_KEY`), `LLM_EXTRA_BODY`(예 `{"chat_template_kwargs":{"enable_thinking":false}}`). 키 값은 문서에 적지 않는다. LiteLLM 중계는 예비이며 GPU가 운영 지점에서 계약 실패를 반복할 때 같은 입력으로 비교한 뒤 전환한다. `.env.example`의 기본값(`LLM_PROVIDER=auto`, OpenAI 호환 주소, 모델 미지정 시 `gpt-4o-mini`)으로도 동작하고, 키가 없거나 오류 · 빈 응답 · 시간 초과(기본 8초, 재시도 없음)면 템플릿 문장을 쓴다. 설정 변경은 `docker compose up -d agent`로 적용한다.

판단(카드 후보 · 순위 · 승인 권한)은 LLM이 바꾸지 않는다. 온톨로지 · DMN 규칙의 산식과 규정으로 결정하며, 내부 LLM은 카드 설명문만 쓴다. 설명문의 사실 정확성은 별도 검토 대상이다.

## 설명 영상

`docs/video/hyd-iot-edu-demo.mp4`(2026-09-30 첫 판 화면 기준 — 현재 포털 메뉴 · 처리 건 화면과 다르다. 10분, 한국어 내레이션·자막, 23장면: L1~L6 폐루프 → L7~L9 지식 지도 · 전사 판단 · 역할 승인 → 부정 시나리오). 다시 만들려면 스택을 올린 뒤 `python video/narration.py && python video/record_demo.py`.

## 운영 메모

- **포트는 127.0.0.1에만 열린다.** 같은 노트북의 브라우저만 접근할 수 있다. 다른 기기(예: 강의실 프로젝터 PC)에서 봐야 하면 `compose.yaml`의 `127.0.0.1:` 접두어를 지운다. 이때 OT 브로커(1883)와 plant-sim(8000)이 LAN에 노출되므로 EMQX 인증/ACL(학생 가이드 과제 5)을 먼저 켜는 것이 맞다.
- **process와 enterprise-sim은 상태를 전용 볼륨에 보존합니다.** 승인 대기·종료 기록은 재시작 후 유지됩니다. 명령 실행/재관측 도중 process가 재시작되면 `PROCESS_RESTART_REVIEW`로 에스컬레이션하며 명령을 자동 재발행하지 않습니다. 승인 도중이던 기업 판단은 `PARTIAL`로 남아 확인이 필요합니다. 같은 decision/skill의 기업 실행 재요청은 기존 결과를 반환합니다. `docker compose down -v`는 이 기록과 DB를 지웁니다.
- **agent 실행 트레이스는 메모리 상태입니다.** agent 재시작 시 사라집니다. `/api/agent/replay/{alertId}`는 그 agent가 아직 기억하는 경보에만 사용할 수 있습니다. 제출된 카드는 process에 보존됩니다.
- **DB 장애 시 connect-sink는 소비 확정을 보류하고 재연결합니다.** DB 기록과 Kafka 위치를 같은 트랜잭션으로 저장하여 장애 후 재처리 중 중복 적재를 막습니다. 잘못된 메시지는 위치를 로그에 남기고 건너뜁니다. 토픽을 삭제·재생성하면 오프셋이 초기화되므로 새 DB/볼륨을 함께 사용해야 합니다.
- **서비스 /healthz는 소비 루프가 죽으면 503**을 돌려준다(포탈 홈의 점이 빨강). 잘못된 메시지(예: Redpanda Console에서 손으로 보낸 비JSON `action.cmd`)는 스키마 검증에서 거부되고 서비스는 계속 산다.
- **시간 배율**: 기본은 **20배속**(`TIME_SCALE=20`)이다. 가상 설비라 수업 · 실습 · 검사 모두 20배속으로 하며 1~2배속을 권장하지 않는다(2026-10-08, HANDOFF §6). 20배속 쿨러는 호스트 워커의 네 작업이 끝나기 전에 트립하므로 워커 실습은 팬 경보로 한다(`docs/curriculum-75h.md` §4). `.env`의 `TIME_SCALE`은 plant-sim·detector·process가 공통으로 읽는다. 포털/`POST /api/time_scale`은 plant-sim의 물리 속도만 바꾼다(탐지 유지 시간·재관측 타이머는 그대로).
- **오류 첫 조치**(process 503·IPv6 DB 연결 실패·OOM·잔재 인스턴스·워커 재기동·아웃박스 정리)는 RUNBOOK §3 표를 따른다.

장애 복구 검증(첫 판 시기 도구, 현재 회귀 러너 묶음에는 없음): 실제 LLM을 설정하고 전체 시나리오가 끝난 뒤 `python scripts/stability_test.py`를 실행합니다. 실제 DB 중단, 수집기 재시작, Kafka 재처리, process/enterprise 재시작을 수행하므로 시연 중에는 실행하지 않습니다. 개발 의존성은 `.venv314`에 `requirements-dev.txt`로 설치합니다(RUNBOOK §0). `python scripts/scenario_test.py --require-llm`은 legacy 모드 전용입니다. 실행별 결과·로그·캡처는 `.evidence/`에 생성하며 Git과 Docker 빌드에 포함하지 않습니다. 보관용 사진·검수 기록은 저장소 밖의 단일 HTML로 관리합니다.

## 범위 밖 (설계서 v3와 다른 곳)

IoT·SCADA 층: EdgeX/Modbus 실제 연동, Flink/ONNX 실제 모델, Kafka Connect 커넥터, EMQX ACL 강제, MinIO, Alertmanager/Mailpit, prom-agent, 3망 구역 라우터. 지식 층: n10s(OWL/SHACL). 각각의 연결 지점은 `docs/student-guide.md`의 "실제 제품으로 바꾸려면" 절, 차이와 결정은 DECISIONS 106(현 구조 유지)·107(제품 교체 방향은 정했으나 보류)을 보세요. ProcessGPT 제품 자체는 설치하지 않는다(데이터 모양·호출 방식만 따름). 데이터 패브릭은 구현하지 않고 24회차에서 설명만 한다.
이력: 첫 판(09-30)의 이 목록에 있던 "MCP 서버 분리 · LiteLLM · Process-GPT"는 이후 MCP 서버(enterprise-mcp · dmn-mcp · Neo4j MCP)와 ProcessGPT 모양 프로세스 엔진이 들어오면서 빠졌다. LiteLLM 프록시 컨테이너는 여전히 compose에 없다(외부 엔드포인트를 `OPENAI_BASE_URL`로 지정).
