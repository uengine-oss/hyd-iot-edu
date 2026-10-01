# hyd-iot-edu — 유압설비 IoT-SCADA 학생용 프로토타입

`유압설비_IoT-SCADA_아키텍처_v3.pdf` 4쪽 구조도(L1~L9, OT·DMZ·IT)를 학생 노트북에서 `docker compose up` 한 번으로 돌리는 완성본입니다.
무거운 제품(Process-GPT, Flink, Kafka Connect, EdgeX, LangGraph/MCP 서버, LiteLLM)은 **같은 이름·같은 메시지 계약을 지키는 작은 파이썬 서비스**로 바꿨고,
가벼운 실제 제품(EMQX, FUXA, Redpanda, TimescaleDB, Grafana, Neo4j)은 그대로 씁니다.

**강의의 초점은 L7~L9입니다.** L1~L6은 경보가 나면 팬을 올리는 즉각 제어까지입니다. L7 온톨로지는 여기에 조직 · KPI · 규정 · 기업 시스템(ERP · MES · CMMS · QMS · SCM · EMS) · 에이전트 스킬 · 업무 프로세스를 잇고, L8 에이전트는 부서 간 상충하는 이익을 전사 관점에서 판단하며, L9는 온톨로지가 정한 승인 역할에 따라 기업 시스템에서 실행합니다. 설계와 시나리오는 [docs/l7-l9-ontology-decisions.md](docs/l7-l9-ontology-decisions.md)에 있습니다.

```
cp .env.example .env                 # 최초 1회 (PowerShell: Copy-Item .env.example .env)
docker compose up -d --build          # 전체 (.env의 COMPOSE_PROFILES)
python scripts/scenario_test.py       # 시나리오 자동 검증 (약 6분, L7~L9 전사 판단 포함)
```

포탈: http://localhost:8088 — 처음 화면은 전체 그림(메인)이고, 왼쪽 메뉴는 두 묶음입니다(위 L1~L6, 아래 L7~L9).

| 묶음 | 메뉴 | 보는 것 |
|---|---|---|
| | 메인 (왼쪽 위 "유압설비 포탈") | 유압 파워유닛 · IIoT/SCADA 경로 · 온톨로지 지식 지도 · 에이전트 폐루프를 한 장에 그린 그림, 실시간 유온, 세 단계 바로가기 |
| | 시스템 아키텍처 & 맵 | 레이어 L9 → L1과 진입점 · 상태 |
| 관제 · 제어 (L1~L6) | 결함 시나리오 시뮬레이션 | 쿨러 열화 주입, 모드, 수동 조작 |
| | 이상 확인 & 조치 | 설비 도식, BPMN 조치 흐름도, **HITL 조치 의사결정**(에이전트가 매긴 우선순위 중 하나를 역할 권한으로 결정), 에이전트 트레이스, 가이드 카드 |
| | 실시간 설비 모니터링 | Grafana 추세와 경보·조치 주석 |
| 지식 · 판단 · 실행 (L7~L9) | 온톨로지 지식 지도 | 설비·고장·조치 지식과 조직·KPI·규정·시스템·스킬·판단 지식, 판단별 강조 경로, 질의 템플릿, **매뉴얼 업로드 → SOP 인제스천** |
| | 에이전트 스킬 카탈로그 | 스킬 8종의 이름 · 설명 · 상세(입력 · 실행 · 파라미터 · 산출 · 가드레일), 실행 시스템 · 프로세스 · 승인 역할 편집, 새 스킬 추가 |
| | 전사 의사결정 시나리오 | 네 가지 판단: 대안 × KPI 금액 영향, 부서별 1위 vs 전사 1위, 규정 제외, 조회한 시스템 |
| | 업무 프로세스 · 시스템 연계 | BPMN 흐름도(선택한 판단의 진행 상태), 역할 기반 승인, ERP · MES · CMMS · QMS · EMS 실행 결과, 트랜잭션 로그 |

## 진입점

| L | 구성요소 | URL | 원래 아키텍처 |
|---|---------|-----|--------------|
| L9 | 설비 포탈(guide-app) | http://localhost:8088 | guide-app |
| L9 | process (미니 BPMN · 전사 판단 승인) API | http://localhost:8080/docs | Process GPT / Flowable |
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

1. 포탈 **결함 시나리오 시뮬레이션**에서 HYD-01 "쿨러 열화 주입".
2. 유온 TS1이 오르고, FUXA에 값과 알람이 보인다.
3. detector(L4)가 `alerts RAISE` → cmd-gateway가 `plant/hyd01/alert`로 중계 → FUXA IT 경보 표시등.
4. agent(L8)가 신선도 확인 → Neo4j T1 원인 후보 → TimescaleDB 증거 SQL → T2 조치·SOP·매뉴얼 → 가드레일 → 카드 제출.
5. 포탈 **이상 확인 & 조치**에서 운전원이 승인(팬 100 %, 부하 80 %).
6. process(L9)가 `action.cmd` 발행 → cmd-gateway 검증 5종 → `cmd/auto` → PLC 검증 → `status ACK DONE`.
7. 유온이 내려가 `alerts CLEAR` → 15분 재관측(시간 배율 적용) → 쿨러 세척 작업지시 → 종결. Grafana 추세에 주석으로 남는다.

부정 시나리오: PLC가 `REMOTE_MANUAL`이면 게이트웨이가 거부하고 감사 로그에 사유가 남는다. 조치 없이 두면 65 ℃에서 인터록 트립.

## 단계별 실습 (Compose 프로필 = 설계서 11절 M1~M7)

| 단계 | 프로필 | 올라가는 것 | 확인 |
|------|--------|-------------|------|
| M1 | `ot` | plant-sim, emqx, fuxa(+init) | FUXA에 1 Hz 값, 팬 입력으로 속도 변경, 65 ℃ 트립 |
| M2 | `backbone` | redpanda(+topic-init), connect-ingest, connect-sink, timescaledb, grafana | Grafana 추세 (토픽 브라우저는 `tools` 프로필의 Redpanda Console) |
| M3 | `detect` | detector, cmd-gateway | 열화 주입 → RAISE → FUXA 알람, 복구 → CLEAR |
| M4 | `monitor` (선택) | prometheus | 6개 서비스 /metrics 수집. 경량 기본값에서는 빠져 있다 |
| M5 | `knowledge` | neo4j, kg-seed | T1/T2 템플릿 결과, 전사 온톨로지(조직 · KPI · 규정 · 시스템 · 스킬 · 판단 시나리오) |
| M6 | `agent` + `enterprise` | agent, enterprise-sim | 근거 인용 가이드 카드, T3 전사 판단(기업 시스템 조회 → 부서별 KPI 비교) |
| M7 | `process` | process, portal | 승인 → ACK → 재관측 → 종결, REMOTE_MANUAL 거부, 역할 기반 전사 판단 승인 → 기업 시스템 실행 |

```
docker compose --profile ot up -d --build              # M1만
docker compose --profile ot --profile backbone up -d   # M1+M2
```

### 가볍게 돌리기 (학생 노트북)

기본값이 경량 구성입니다. 전체 기동 시 컨테이너 메모리 합계는 약 1.4 GB입니다.

- `DAQ_PROFILE=lite`(기본): TS1·CE만 매초, 나머지 태그는 변할 때와 10초·30초 하트비트에만 발행하고 100 Hz 파형은 보내지 않습니다. 원래 설계대로 보려면 `.env`에서 `full`로 바꿉니다.
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
      neo4j/ (seed.cypher · seed_enterprise.cypher · templates/t0~t3) agent/ (tools/mcp_*.py · card.py · guardrail.py · llm.py · decision.py · enterprise.py)
      process/ (definition.py · machine.py · decisions.py) enterprise-sim/ (entsim/data.py · state.py) portal/ (app.js · enterprise.js)
tests/   순수 로직 단위 테스트 (pytest)      scripts/scenario_test.py   통합 시나리오 (L1~L9)
video/   scenes.py · narration.py · record_demo.py   → docs/video/hyd-iot-edu-demo.mp4
docs/    l7-l9-ontology-decisions.md  student-guide.md  topics.md  payload-schemas/  wslconfig.example  superpowers/(설계서·계획)
```

## 테스트

```
pip install -r requirements-dev.txt
python -m pytest -q                    # 단위: 열 모델, PLC, 게이트웨이 5종, CEP, 카드/가드레일, 프로세스, DAQ, 전사 판단 엔진, 판단 승인, 기업 시스템 목업
python scripts/scenario_test.py        # 통합: 스택이 떠 있어야 함
```

## LLM (선택)

`.env`의 `OPENAI_API_KEY`를 넣으면 카드 요약문을 OpenAI로 작성합니다(`LLM_PROVIDER=auto`, 기본 모델 `gpt-4o-mini`). LiteLLM을 사용하려면 `OPENAI_BASE_URL`을 프록시의 `/v1` 주소로, `LLM_MODEL`을 그 배포 모델 이름으로 설정합니다. `LLM_PROVIDER=anthropic`과 `ANTHROPIC_API_KEY`도 지원합니다. 키가 없거나 API 오류·빈 응답·시간 초과가 생기면 템플릿 문장을 사용합니다. 기본 호출 제한은 8초이고 자동 재시도는 하지 않습니다. 설정 변경은 `docker compose up -d agent`로 적용합니다.

전사 판단은 LLM을 쓰지 않습니다. 온톨로지의 산식과 규정으로 결정합니다. LLM은 카드 설명만 작성하며, 구조화된 권고나 승인 권한을 바꾸지 않습니다. 설명문의 사실 정확성은 별도의 검토 대상입니다.

## 설명 영상

`docs/video/hyd-iot-edu-demo.mp4` (10분, 한국어 내레이션·자막, 23장면: L1~L6 폐루프 → L7~L9 지식 지도 · 전사 판단 · 역할 승인 → 부정 시나리오). 다시 만들려면 스택을 올린 뒤 `python video/narration.py && python video/record_demo.py`.

## 운영 메모

- **포트는 127.0.0.1에만 열린다.** 같은 노트북의 브라우저만 접근할 수 있다. 다른 기기(예: 강의실 프로젝터 PC)에서 봐야 하면 `compose.yaml`의 `127.0.0.1:` 접두어를 지운다. 이때 OT 브로커(1883)와 plant-sim(8000)이 LAN에 노출되므로 EMQX 인증/ACL(학생 가이드 과제 5)을 먼저 켜는 것이 맞다.
- **process와 enterprise-sim은 상태를 전용 볼륨에 보존합니다.** 승인 대기·종료 기록은 재시작 후 유지됩니다. 명령 실행/재관측 도중 process가 재시작되면 `PROCESS_RESTART_REVIEW`로 에스컬레이션하며 명령을 자동 재발행하지 않습니다. 승인 도중이던 기업 판단은 `PARTIAL`로 남아 확인이 필요합니다. 같은 decision/skill의 기업 실행 재요청은 기존 결과를 반환합니다. `docker compose down -v`는 이 기록과 DB를 지웁니다.
- **agent 실행 트레이스는 메모리 상태입니다.** agent 재시작 시 사라집니다. `/api/agent/replay/{alertId}`는 그 agent가 아직 기억하는 경보에만 사용할 수 있습니다. 제출된 카드는 process에 보존됩니다.
- **DB 장애 시 connect-sink는 소비 확정을 보류하고 재연결합니다.** DB 기록과 Kafka 위치를 같은 트랜잭션으로 저장하여 장애 후 재처리 중 중복 적재를 막습니다. 잘못된 메시지는 위치를 로그에 남기고 건너뜁니다. 토픽을 삭제·재생성하면 오프셋이 초기화되므로 새 DB/볼륨을 함께 사용해야 합니다.
- **서비스 /healthz는 소비 루프가 죽으면 503**을 돌려준다(포탈 홈의 점이 빨강). 잘못된 메시지(예: Redpanda Console에서 손으로 보낸 비JSON `action.cmd`)는 스키마 검증에서 거부되고 서비스는 계속 산다.
- **시간 배율**: `.env`의 `TIME_SCALE`은 plant-sim·detector·process가 공통으로 읽는다. 포탈/`POST /api/time_scale`은 plant-sim의 물리 속도만 바꾼다(탐지 유지 시간·재관측 타이머는 그대로).

장애 복구 검증: 실제 LLM을 설정하고 전체 시나리오가 끝난 뒤 `python scripts/stability_test.py`를 실행합니다. 실제 DB 중단, 수집기 재시작, Kafka 재처리, process/enterprise 재시작을 수행하므로 시연 중에는 실행하지 않습니다. 개발 의존성은 `pip install -r requirements-dev.txt`로 설치합니다(Python 3.12). LLM 사용을 필수로 검사하려면 `python scripts/scenario_test.py --require-llm`을 사용합니다. 실행별 결과·로그·캡처는 `.evidence/`에 생성하며 Git과 Docker 빌드에 포함하지 않습니다. 보관용 사진·검수 기록은 저장소 밖의 단일 HTML로 관리합니다.

## 범위 밖 (학생용 간소화)

EdgeX/Modbus 실제 연동, Flink/ONNX 실제 모델, Kafka Connect 커넥터, MCP 서버 분리, LiteLLM, Process-GPT/Flowable, EMQX ACL 강제, MinIO, Alertmanager/Mailpit, prom-agent, n10s(OWL/SHACL). 각각의 연결 지점은 `docs/student-guide.md`의 "실제 제품으로 바꾸려면" 절을 보세요.
