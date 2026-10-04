# 회의 요구 · 관련 레포 · HYD 실제 구현 대조

현재 계약은 [GOAL](GOAL.md) 상단, 재개 순서는 [HANDOFF §9 G](HANDOFF.md). 이 문서는 조사/검증 원장이며 새 요구를 임의로 만드는 문서가 아니다.

## 판정과 증거

- 상태: 미검토 / 문서 확인 / 코드 대조 / 실행 검증 / 결함 확정 / 수정 후 검증. 클론/파일 존재는 열람이나 구현 증거가 아니다.
- 원문 기준: [회의 2](sources/meeting-2.txt) 1~461행. 사용자 최신 확장은 [발화 원문](USER_UTTERANCES_CODEX_20261004.md).
- 원자료 바이트/해시: [provenance.json](sources/provenance.json). [47개 지도](sources/repository-map/REPOSITORY_MAP.md), [67개 연결](sources/repository-map/CONNECTIONS.md), 내부 경로 8개·미확정 4개도 보존한다.
- HYD 기준 HEAD `aad500b47c928d0fc2d6bb65bc20dadc5ccd3f5d` + 기존 WIP. 참고 17개 커밋/변경 상태는 `.evidence/reaudit/2026-10-04-baseline/repository-snapshots.json`. 이 스냅샷은 원격 최신이라는 주장이 아니다.
- 이전 REPO_GAP는 과거 기록이다. 각 항목에 이번 실제 확인을 추가하기 전에는 재검증됨으로 표시하지 않는다.

## 최신 사용자 범위 정정

C17에 따라 시스템 개발·실제 검증이 대상이다. 아래 R13/R14의 강의 목적은 시스템 설계 배경이며 교재·시수·강의 리허설 산출물을 요구하지 않는다. 현재 수용 조건은 GOAL 상단이다. 과거 A절의 교재 작업/미완료 기록을 현행 할 일로 가져오지 않는다.

## 요구별 추적 (초기 표 2026-10-04 10:00, 후속 실제 증거는 아래 A절)

다음 '확인 방법'은 구현 적합성을 판단할 검증 설계다. 회의가 특정 테스트 명령/횟수를 지정했다는 뜻이 아니다.

| ID | 원문/지위 | 요구 | 후보 원본 | HYD 조사 시작점 | 확인 방법 / 학생 행동 | 현재 |
|---|---|---|---|---|---|---|
| R01 | 1~30 | 최소 스키마의 BSC·프로세스·리소스·진단·조치·실행 연결 | vue3 ontology, strategy, ontology-studio | it/neo4j/v2 | 스키마·인스턴스 관계와 실제 조회를 연결해 설명 | 부분 실행 검증: A013/A015 schema·Execution; 전체 의미 연결 재감사 남음 |
| R02 | 253~293 | DDL·SOP로 인스턴스 적재, 과정 학습, 초기화/재적재 | ontology-studio, bpmn-extractor, memento, ontologic | procsvc/ingest.py, manual_extraction.py, manual_api.py | 새 자료→추출/검토→적재→조회; 변경·되돌림; 출처 보존 | DDL A004/SOP A026, A050 추출 작업 연결·실제계약13+5·포털; 실제 Codex 일반문서 추출 정확성 미완료 |
| R03 | 88~112 | MCP 스키마 탐색→Cypher 생성→관계 기반 판단 | ontology-studio MCP, cliagents, cli-agent | agent-worker, agentsvc/tools | 새 질문/관계에 실제 질의와 결과·근거 확보 | F 실제 Neo4j MCP 호출 검증; 새 관계·질문 변경 범위 남음 |
| R04 | 350~404 | 기업 RDB/DDL/MCP로 업무 사실 조회 | WMS, agent-sdk, agent-utils | enterprise-mcp, supabase ent | 납기/계약 변경→실조회→판단 변화 | A022 읽기역할/AST·실제DB+MCP49/49·Codex 생성SQL/컬럼오류수정; A042 MES6/36/0h 실제MCP·권고변화; 새Codex/계약 변경 종합검증 남음 |
| R05 | 51~79,123~138 | 현황값은 원천에서 조회, 그래프는 연결/의미 | ontology-studio, strategy, HYD 기존 경로 | agentsvc/decide.py, dmn-mcp | 값 변경·조회 실패·데이터 없음 구분, 시점/출처 | A027 현재 원천·신선도/미확인 방어, 실제MES/CMMS 변경검사; 전체원천/동적예측은미완료 |
| R06 | 289~350 | 규칙/DDL/메타데이터로 질의 생성·실행 | agent-utils, ontology-studio, 관련 연결 추적 | rules/sql, enterprise query, worker prompt | 미리 고정되지 않은 조건/컬럼의 질의와 실제 결과 | A017/A022 LLM schema→SQL→실행·컬럼오류수정/빈결과 두정의 검증; PromQL·규칙/메타데이터 일반화 미완료 |
| R07 | 134~178 | 범용 코딩 에이전트의 실제 도구 실행 | cli-agent, cliagents, deepagents, codex | worker/runner.py, bridge.py | 모의 CLI가 아닌 도구 호출·출력 계약·실패 로그 | A020취소·A024질문재개·A034 실제Codex42/42; 재작업/변경지식의 새Codex는 정책거절 이후 미실행 |
| R08 | 175~214 | 이벤트→서버의 에이전트 실행→통합 UI | cli-agent, SDK, completion | detector, instances, worker, portal | 외부 이벤트부터 이벤트/화면까지 추적 | F 외부경보→실제Codex→제어 검증(2×); 20×지연/중복경계 후속 |
| R09 | 385~413 | 설비·납기 상충 대안 및 사람 선택 | strategy, WMS, agent-utils | cards.py, instance select | 업무 데이터 변화·대안 이유·승인 결과 비교 | A042 MES6→0h 권고역전/포털새동의/PLC·CMMS 확인(합성경보·기록진단·실제DMN); 계약/품질 등 전체변화는 남음 |
| R10 | 405~430 | 알림/HITL, 사람 선택과 제어 책임 | vue3, SDK, WMS | portal, decisions, cmd-gateway | 승인 거부/권한/시간초과·직접 제어 우회 불가 | A027/A031 현재조건·변경조치; A040 새세대 판단/별도사람선택 가동18·승인폐기 PG13; A041 포털 일반정의13; A042 Incident UI/역할/새세대PLC·CMMS(합성경보); 새Codex·실제고장 후속 |
| R11 | 19~24,193,434~436 + 사용자 | 인스턴스/태스크 실행 구조 | completion, SDK, cli-agent, generation-skill | engine.py, procdb.py, instances.py | 새 정의·분기·오류·중복 제출을 동일 엔진으로 실행 | A007/14~17 정의·폼·중복,A021 동시전이,A028 CMMS복구,A038 일반세대,A040 활성사건재작업13/18; 효과보상/의존스케줄러/전체graph outbox 후속 |
| R12 | 434~435 | 에이전트·인스턴스 모니터링 | vue3, analytic, cli-agent | instances.js, events, graph | UI와 원천 상태 일치·실패/대기 상태 표시 | 실제UI/Execution/CLI trace 일부검증; 전체 상태/복구 화면 검수 남음 |
| R13 | 154~174,437~457 | 기본 모델→제품/패브릭 확장·컨설팅 활용 | 지도 전체 관련 기능 | 교재13, curriculum | 실제 한계와 추가 제품 기능 비교; 필수/확장 구분 | 관련레포의 시스템 기능 대조·전체 확장 대응 미완료; 교재는 C17 범위 제외 |
| R14 | 187~188,222~238,29~30 + 기존 계약 | 온톨로지·에이전트 중심 시나리오 강의·75h 후보 | docs, 관련 기능/실습 | 세 시나리오, 시스템교재 | 학생이 정의/자료/조건 변경 후 결과 설명; 시수는 예상/실측 구분 | 설비 및 정의변경 실습 추가·일부 실제검증; 시스템 변경 입력/다중 경로 검증 후속; 시수/리허설은 C17 범위 제외 |

## 관련성 검토 원칙

47개를 모두 지도 수준에서 분류한 뒤 실제 요구에 연결된 코드를 깊게 읽는다. 지도에 없는 의존성도 실제 코드가 참조하면 추적한다. 전체 설치나 모든 파일 통독을 진척 지표로 삼지 않는다. 채택/보류/확장 후보에는 근거와 강의 가치·비용을 기록한다. '제품에 없다'는 결론에는 조사한 경로와 남은 미확인 범위를 명시한다.

## 최초 발견 기록 · 후속 판정은 요구표와 각 A절 참조

- A001: 기존 원문 313~348행의 '결정론 원칙' 해석은 불일치. 문서 현재 계약은 정정. 실제 동적 질의/DMN 구현 적합성은 미검토.
- A002: 기존 브리지는 Claude 전용, runner의 allowedTools도 프로바이더 구분 없음. F의 Codex 경로는 미검증.
- A003: 이전 대조표의 '제품에 없음', ontology-studio 문서 열람만으로 인제스천 구현 선택, ontology_sync 앞부분만 참조한 판단을 재검토해야 한다. 아직 코드 결함으로 확정하지 않는다.

### 이번 실행으로 확인한 반례 (2026-10-04)

기준 회귀: `.venv314/Scripts/python.exe -m pytest -q --junitxml=.evidence/reaudit/2026-10-04-baseline/pytest.xml` → **259 passed, 2 warnings, 3.74s**. 기존 코드 시험이며 새 요구 충족 판정이 아니다.

추가 실험: `scripts/audit_behavior_probes.py` → 기대 충족 **0/5**. 실제 HYD 함수 + MemoryRepo + 명시적인 enterprise 가짜 응답으로 실행했다. DB/PLC/UI 통합 시험이 아니다. 원시 출력: `.evidence/reaudit/2026-10-04-baseline/behavior-probes.json`.

| ID | 기대와 실제 | 코드 위치 | 영향/다음 조치 |
|---|---|---|---|
| A004 | plant_a.readings.value와 plant_b.readings.value가 모두 in:readings.value / readings_value | ingest.plan, INPUT_Q | 다른 스키마 식별자 충돌. schema를 그래프에 저장하지 않고 rules/sql은 ent로 고정함(main.py:717). 원천 식별/스키마 보존 설계 필요 |
| A005 | 동일 enterprise:WO_CREATE tool, task:work-order는 완료; task:maintenance-order로 ID만 변경하면 호출 0·SUBMITTED·consumer 점유 상태로 정지 | instances._run_service:220 | 실행이 tool 계약보다 고정 task ID에 종속. 도구 계약으로 디스패치하고 미지원 도구는 명시 실패 처리해야 함 |
| A006 | 새 정의 ontologyRef=proc:audit-work-order인데 투영 인수는 proc:anomaly-response | instances._project:324 | 정의를 바꿔도 다른 프로세스에 실행 투영. 정의/버전별 원천 참조 필요 |
| A007 | 완료 뒤 동일 alertId 재전달 시 새 인스턴스 생성 | instances.find_by_alert:55 | RUNNING만 조회하는 중복 검사. 영속 중복/동시성 계약 확인 필요 |
| A008 | enterprise 응답 ok=false, error=database unavailable인데 작업 DONE·인스턴스 COMPLETED | instances._run_work_order:268 | 실패를 종결 성공 경로로 연결함. 결과/실패 상태 및 재시도·복구 계약 재설계 필요 |

원본 대조 주의: completion `workitem_processor.py:5161~5190`도 성공/실패를 집계하고 DONE을 기록한다. 제품에서 DONE이 '실행 처리 종료'인 것과 HYD에서 성공 종결을 의미하는 것은 구분해야 한다. 제품 코드를 복사했다는 이유로 HYD의 실패 결과를 정상 성공으로 표시하는 것을 정당화하지 않는다. 차이는 DECISIONS에 근거를 남긴다.

## 이번에 직접 읽은 원본 코드

| 저장소/커밋 | 파일/읽은 범위 | 확인 내용/한계 |
|---|---|---|
| ontology-studio / 6a229be8dcce2aeb533ecdba360b5b4564ffb777 | README·docs/ontology-mcp-server.md 전문; backend/src/modules/agent_session/service.py 69~352; modules/ontology/tools.py 520~665 | 원자료 유형별 추출→nodes/relationships→batch_ingest→질문별 실제 Cypher 검증 루프. `_source_id`/`_parent_source_id`를 사용한다. HYD의 ingest_batch를 원본 기능처럼 쓴 주석은 부정확. 실행은 미검증 |
| process-gpt-completion / b272c9ab458f3ca3e18fe286e4e770d291b99e89 | polling_service/polling_service.py 1~150; workitem_processor.py 5026~5258 | 정의/버전을 조회해 활동 type으로 분기; 업무 도구 결과/실패 집계. 원본 전체 실행은 미검증 |
| HYD / 기준 HEAD+WIP | ingest.py 1~319, kgadmin.py 전문, worker/prompt.py·context.py 전문, dmn_mcp/tools.py·enterprise_mcp/tools.py 전문; instances.py 1~150,219~342; main.py 645~718 | 단순 정규식 문서 파서, DDL 계획/적재/SQL 경로, 고정 service ID와 실제 데이터 읽기 도구가 함께 존재. '전부 하드코딩'으로 단정하지 않음 |

[저장소 전체 관련성](REPOSITORY_REVIEW.md)은 47개 지도 항목 각각의 다음 조사 목적을 관리한다. 코드 대조 완료와 구분한다.

## 다음 작업

47개 관련성 분류를 확정하고 온톨로지/인제스천/질의 실행의 원본 코드와 HYD를 연결한다. 구현 전에 서로 다른 입력으로 기존 동작을 확인하여 코드가 실제로 고정 답을 반환하는지 또는 정의 기반인지 판별한다.

## G2 서비스 계약 수정 진행

A005/A006/A008 대응 코드를 변경했다(DECISIONS 16). 관련 함수/배선 테스트 22 passed, 전체 263 passed. 증거 `service-contract-red.xml`(수정 전 5 failed/11 passed), `service-contract-green.xml`, `service-contract-regression.xml`은 `.evidence/reaudit/`에 있다. 원시 반례 JSON은 변경 전 증거로 보존한다. A004/A007 미수정. 새 프로세스의 등록·버전·그래프 노드 생성, 실제 실패 복구 UI, 다중 정의/동시성은 후속이며 현재 수정으로 범용 실행 전체를 충족했다고 하지 않는다.

실제 회귀: process 재빌드 후 `scenario_instance_test.py` exit 0, **35/35 PASS**. instance `anomaly_response.582b42fa-1615-4aba-ad9b-a6e68fc60abc`, incident `INC-1003-01-ee33`, command `CMD-1003-0001-925c`, CMMS `WO-1003-AEFB`. 실제 DB/PLC/승인/재관측/투영 검증. 레거시 다리이며 Codex 판단 증거가 아님. 로그 `.evidence/reaudit/service-contract-instance.log`.

## F Codex 호환 조사

설치 CLI 0.151.0. cliagents McpServer는 name/command/args/env만 있으며 install_bridge는 HTTP 미지원. 기존 F의 HTTP 지원 설명은 정정한다. 호출별 `--ignore-user-config -c mcp_servers=...`로 tenant 설정을 전달하여 사용자 config/인증을 변경하지 않는다. 원본 exec_parser를 유지하고 resume 앞에 exec 전용 옵션을 놓는 작은 adapter를 사용한다. 공식 MCP 설정 근거: https://learn.chatgpt.com/docs/extend/mcp?surface=cli (2026-10-04 확인), 실제 local CLI help도 확인. 읽기 전용 샌드박스는 MCP 쓰기를 막는다는 뜻이 아님: Neo4j 도구 allowlist를 적용하며 hyd-dmn.submit_decision은 카드 제출 쓰기임을 명시한다. PLC/승인은 별도 서비스/사람 책임.

실제 단독 검증: startup 실패(HTTP ws 구현/Neo4j fastmcp API) → 의존성 고정·HTTP ws none → 도구 실패(APOC/승인 정책) → APOC 및 headless tenant tool 승인 설정 → 세 MCP 호출 성공/실패 0, schema 라벨 38, 동일 세션 재개, 사용자 config 해시 불변. 증거/세션은 HANDOFF G2.

최종 F 통합: `codex-instance-scale2.log` **35/35 PASS exit0**, instance `1dfcaa53-0ba0-4d6d-844d-3a9ad4bb6035` 종결. 실제 agent 작업4·독립CLI세션4·MCP시작/종료23/23·도구오류0, 사람 역할403·승인·ACK·재관측594초·WO-1003-3389·Execution관계 확인. 모델 gpt-5.6-sol/low, 시뮬레이션2배속 조건이다. 20배속 실패는 A011로 유지. PowerShell 워커0, 기본20배속/legacy복구·설비reset 및 config해시불변 확인. F완료와 전체G완료는 별개다.

교재13장/시수표 반영: 프로바이더별 설정·네작업독립세션·서비스실패PENDING·Codex HITL 미검증·배율 일괄설정으로 교정. 변경전사본 `.evidence/reaudit/book-before/`; 구조검사0문제,1280/390 렌더 넘침/콘솔오류/깨진이미지0.1280 전체9조각 직접검토 중 도형 밖 설명문을 줄임. 새CLI설명을 반영한 것이며 인제스천/제품대응/동적질의 등 장전체 의미검증 완료는 아니다.

A009 실제 통합에서 process bridge=off여도 별도 agent Kafka consumer가 레거시 카드를 제출함. `agentsvc/main.consume`에 instance+off skip, compose에 두 설정 전달. A010 workspace가 저장소 안에 있어 상위 개발용 AGENTS가 업무 실행에 유입됨. 실행 trace에서 docs/handoff 파일 열기 시도 확인. Codex의 프로젝트 문서 읽기를 끄고 업무 지침·스키마를 직접 제공. 첫 혼합 실행은 완료 판정에서 제외하고 clean 실행으로 검증한다.

A011 두 번째 20배속 통합 시험도 완주하지 못함: 실제 LLM 작업 지연 중 HYD-01 OVERTEMP TRIP. `codex-clean-plant-state.json`: leak=0인데 FS1=0, PS1≈155, LoadSP=90이어서 PUMP_LEAKAGE도 발생. detector.main.on_tag가 이미 보유한 plc_state를 evaluate_pump에 반영하지 않음(CEP 조건상 '부하 중'을 설정값만으로 판단). 별도 trip 및 pump 인스턴스까지 열려 단일 워커 큐가 늘어났다. 이것은 현장에서 지연/트립/복합 경보를 처리하는 계약이 필요하다는 실행 증거다. 가속률을 줄인 성공만으로 이 결함을 해결했다고 하지 않는다.

진단 시험 인스턴스 6개 원시 snapshot은 `attempt-<uuid>.json`으로 보존. 중단 시 진행 중인 에이전트 작업은 FAILED와 AUDIT_INTERRUPTED 이벤트를 남겼고 삭제하지 않았다. 2배속 재검증은 초기 RAISE 및 재관측 대기 상한만 물리 시간 비율에 맞춰 늘린다. 판정 임계값/승인/PLC 인터록/완료 기준은 유지. worker 추론 effort는 low로 명시(설정 가능), default CLI model gpt-5.6-sol 실제 session 기록. 단일 성공 사례와 시간 임계/예외 검증을 구분한다.

원본 추가 열람: robo-data-catalog cf41148의 contracts/object_resolution.py 전문(명시 datasource/schema/reference unique key), graph/scope.py 전문(owner 경계), graph/schema_queries.py 1~105(datasource/schema/owner 질의), samples/discovery.py 1~125(quoted catalog/schema/name identity). 원본 실행은 미검증. A004는 단순 컬럼 ID 문자열 교체뿐 아니라 원천 연결·정확한 schema·재적재/삭제의 소유권을 함께 다뤄야 한다.

A012 명령 미발행을 완료 처리: `_run_command`가 incident/commands 없음 또는 approve_commands의 ValueError를 빈 성공 submit으로 바꿨다. 명령 없음을 오류로, ValueError는 서비스 실패로 보존, cmdId 없는 응답도 실패 처리하도록 수정. 거부 명령이 PENDING/재시도 3회, 재관측 TODO인 검사 포함 관련 17 passed. 진행 중 통합 컨테이너에는 아직 미반영. terminal 상태 콜백과 현재 설비 상태 재검증은 별도 후속이다.

상세 후속 구현 순서와 수용 조건은 [REBUILD.md](REBUILD.md). 문서는 작업 계획이며 완료 증거가 아니다.

A007 수정/DB 검증: `start_event_id` + tenant/definition/event unique index, 이벤트 잠금 안에서 인스턴스와 초기 작업을 한 트랜잭션으로 기록. 관련 단위 34 passed, 전체 **271 passed, 2 warnings**(`event-identity-regression.xml`). `probe_event_identity.py` 실제 PostgreSQL 별도 schema에서 **7/7**(16개 동시 요청→인스턴스 1·작업 9, 완료 뒤 중복 없음, DB unique 위반 확인, 부분 저장 롤백·재시도, 다른 tenant 독립). 임시 schema 제거 확인. 실제 마이그레이션 기존 20/20 backfill, 중복 그룹 0. Incident/graph는 외부 저장이므로 SQL 트랜잭션 범위를 넘어선 exactly-once 주장은 하지 않는다(DECISIONS 18). process 컨테이너 배포는 현재 F 시험 종료 뒤.
## A004 원천 식별 수정 및 실측 (2026-10-04 04:09 KST)

관련 원본: Catalog contracts/object_resolution.py 전체, graph/scope.py 전체, graph/schema_queries.py1~105, samples/discovery.py1~125. neo4j-text2sql app/core/sql_guard.py 전체와 uv.lock SQLGlot27.24.2. HYD DDL 파서는 AST로 교체하고 물리 식별을 datasource/catalog/schema/table/column으로 분리했다. graph에 원천 속성 보존, ruleSQL은 그래프에서 실제schema를 읽고 connection별로 구분하며 quote+params를 사용한다. 미리보기 잘못된선택/변조된ID/연산자는 오류로 반환한다. 한계: LLM 동적 SQL생성 루프 완료가 아니라 원천 메타데이터/결정표SQL 계약 수정이다.

새 반례4failed→관련10passed→전체275passed,2warnings. `probe_ingest_identity.py` 실제 API/Neo4j/PostgreSQL8/8: 같은 quoted표/열·다른schema·값2/20 조건<8에서1행/0행, 잘못된ID/연산자400. 이실험7노드/임시schema2개 정리. 증거 `.evidence/reaudit/ingest-identity-{red,unit,regression}.xml`, `ingest-identity-live.json`. build wrapper exit1이었으나 로그의이미지/기동 완료와 현재healthy/실제API변경은 확인했다. exit0라고 쓰지 않는다.

포털 agent-browser 실제 조작: 원천연결 입력→두schema DDL선택→preview→east MES/west ERP선택→asset체크해제→선택반영에서 올바른두행과서로다른ID/변수 확인. UI의긴ID가표를세로로늘리는문제를 발견해 실제위치/업무시스템을본표에, ID/변수는펼치기로변경하고재캡처(`ingest-preview-ui-final.png`). 데스크톱넘침false, UI적재버튼실행은아직별도(적재API검증과구분). 배치재적재/되돌리기소유권은다음구현대상.


## A004 반복 적재/복원 후속 실측 (2026-10-04)

기존 `ingest_batch` 최초 생성자/DETACH DELETE 방식을 `graph_ingest.py`의 배치 영수증 + 소유 속성/출처 이전 상태 + 활성 이력으로 교체했다. Neo4j 한 트랜잭션/직렬화 잠금, 같은 배치 동일내용 멱등, 변경내용/clear된ID 거절, 앞 배치 clear 시 뒤 배치 유지, 뒤 배치 clear 시 원래 출처 복원. 외부 참조·속성/타입 확장·수동 수정·이력 없는 구배치는409로 보존한다. 실제18/18, HTTP12/12, 새 구현의 실제 SQL8/8. 자세한 시험별 판정은 `.evidence/reaudit/ingest-ownership-live.json`, `ingest-ownership-http.json`, `ingest-identity-journal-live.json`. UI에서도 외부 속성 추가시 거부→시험 속성만 제거→5노드clear, 두 캡처 직접 확인. 교재13장 §6 동기화,1280/390 렌더 오류0. 외부 원천 연결 등록, SOP ownership, LLM 동적 SQL/PromQL은 후속이다.

## A013 Execution 투영과 정본 스키마 불일치

전체 DB를 정본으로 검사하자 1195위반: ProcessInstance21/WorkItem194의 미선언 및 INSTANCE_OF/EXECUTES/ON_ASSET 끝점, HANDLES/IN_INSTANCE/ASSIGNED_TO/ROLE_BOUND 미선언. 반복된 계약 누락이며1195개의 독립적인 코드 결함을 뜻하지 않는다. 기존 정적 seed 검사는 runtime 레이어를 보지 못했다.

원본 vue3 HEAD `d88f78ca0b60d979d9de4988f0cd2969949f7ece`, ontology/SCHEMA.md L1~26,68~106,166~184를 읽었다. ProcessGPT는 ProcessDefinition/Activity/User/Agent이며 HYD는 Process/Task/Role/System으로 어댑트됐다는 차이를 기록. schema2.4.1에 실제 투영 계약을 선언하고 shared relationship의 허용 끝점 쌍을 validator/prompt/TTL 주석에 명시. 교차 오연결 반례 포함 관련15passed, 전체276passed/2warnings. 실제535노드1574관계에서 schema위반0/integrity위반0 (`execution-schema-live.json`), 제약2개 적용. 정의별 task ID·버전·dangling 처리와 빈 bindings 투영은 여전히 미해결.

정의 버전 원본 추가 열람: completion b272c9a의 `proc_def_versioning.py` 전체(첫 출력 일부 잘림은116~206 재열람으로 보충), `polling_service/proc_def_versioning.py` 전체. 명시 archive/tag/version 조회 후 현재 작업본으로 fallback한다. 주석 첫머리의 prod_version 우선 설명과 실제 구현의 작업본 우선이 다르므로 실제 코드를 따른다. HYD의 기존 실행 버전 고정 요구는 fallback 없이 명시 실패할 필요가 있으며 다음 설계에서 결정한다. 원본 서비스 실행은 검증하지 않았다.


## A014 실행/워커의 정의 버전 미고정

반례4failed(`definition-versions-red.xml`): 구 버전 조회 API 부재, 새 런타임이 기존 인스턴스를 새 ontologyRef로 투영, 기존 workitem의 모델 설정이 최신 정의로 변경, 없는 고정 버전도 오류 없이 처리. `procdb.py`의 immutable 버전 등록/정확 조회, `instances.py`의 instance별 정의 해석, `worker/context.py`의 row.version 조회로 교체했다. 같은 tenant/id/version에 다른 내용은 거부하며 누락된 버전의 최신 fallback을 제거했다. 사용자/LLM이 프로세스 정의를 실제 등록·선택하는 API/UI는 후속이다.

실제 PostgreSQL `probe_definition_versions.py`8/8, 동시16등록→한 내용만 승리, 이전 모델 설정 보존, 구/신 인스턴스와 다른 정의 처리. 임시schema 삭제. 관련50passed/전체280passed. `20261004000002_immutable_definitions.sql` 적용, 이전001 migration도 Supabase 이력에 반영(이전 실제DDL 적용은 이미 돼 있어 멱등). 원천 백업 `definition-pre-migration.json`: proc_def1개, 이전 version0개, RUNNING6개(과거 실패보존: IN_PROGRESS+draftFAILED6, DONE4, TODO44). 백필된 현재 정의는 과거 실행 원문 복원이 아니며 migration message에 한계를 남겼다. `definition-versions-build.log` process배포exit0; 배포API/시나리오 확인은 후속.


A014 배포 후 `definition-legacy-scenario.log`35/35 exit0, Incident INC-1003-01-40d3/command CMD-1003-0001-8ec5/CMMS WO-1003-C837, 종결/그래프 확인 및 설비reset. 새 정의 고정 코드의 legacy 통합 회귀이며 Codex 재시험은 후속 전체 경로에서 한다. 원본 completion `polling_service/workitem_processor.py`4660~4726를 추가로 읽어 workitem version 우선과 instance archive fallback 호출부를 확인했다. 이식은 scope·정의 내용 불변성과 누락시 명시 실패까지 포함한다.


## A015 실행 그래프의 활동 식별 충돌과 빈 역할 투영 누락

같은 activity_id를 가진 다른 정의/버전, roles 없는 정의, ontologyRef 누락, 재배정 반례에서 수정 전6개 중5실패. definition별 ProcessVersion/FlowNode snapshot, WorkItem→Task/Event, 업무 노드 MAPS_TO, nullable 업무 연결과 경고, 역할/담당자 재투영으로 교정했다. 실제 Neo4j13/13에는 8동시 커밋 모두 성공, 경계 이벤트 참조, canonical검사, 지식지도에 runtime snapshot 제외 및 모든 edge endpoint 존재를 포함한다. 업무 지도의 API는 업무 지식/사례에 집중하고 인스턴스 화면에서 실행 버전을 보여 준다. 전체280passed/기존FastAPI경고2. process/agent rebuild exit0.

첫 실제 시나리오는 관리자 제출 전에 PT10M/20=30초가 지나 CANCELLED로 실패. localhost3요청2.056~2.072초 대127.0.0.1의0.003~0.017초 실측(`loopback-http-timing.json`). 스크립트를 Compose IPv4 bind로 맞추고 관리자 제출 실패시 즉시 실패하도록 바꿨다. 실제 프로세스 제한시간은 그대로다. 실패 로그/인스턴스/그래프 보존(`execution-scope-scenario.log`, `execution-scope-timeout-instance.json`), IPv4 재실행 결과는 후속 기록한다. 이 실패를 그래프 성공 수치에 섞지 않는다.


A015 배포 후 IPv4 시나리오35/35 exit0(20배속 legacy), 완료 instance85bd6268…/INC-1003-01-3090/CMD-1003-0001-6823/WO-1003-D0F1. 10작업 모두 scoped노드에 연결, boundary는Event. 첫localhost는23/28 exit1이며 강제종료 전에 자체종료했다. 전체실제그래프599노드1791관계 schema0/integrity0, 지도313노드815관계 runtime혼입0/dangling0. 오래된 실행은 아직 전체 재투영하지 않았고 version snapshot 없는 조회는 경고를 표시한다. 초기 백필 정의가 과거 원문과 같다는 주장은 하지 않는다. 교재13장 §5/포털 반영·직접화면확인, checker0/1280·390 렌더오류0. 사용자 전체 목표의 완료가 아니며 다음은 정의등록/선택·폼계약·tenant경계다.


## A016 정의 등록/선택, 버전별 폼, tenant 실행 경계

원본 vue3 ProcessGPTBackend.ts 421~572/615~700/943~1045의 폼 등록·버전 발행·실행 선택을 대조했다(HEAD와 범위는 REPOSITORY_REVIEW). 원본의 mutable form UUID 재사용을 HYD의 불변 실행 계약으로 주장하지 않는다. DECISIONS24에 명시한 교육용 차이로 새 정의 JSON 안에 forms를 보존한다. public registration은 검증한 activity/tool/단일 exclusive/무순환 범위만 받으며 미지원 형식을 거절한다. 엔진 자체의 반복 기능 부재를 뜻하지 않는다.

정의 목록/정확버전조회/불변등록/선택시작 API, 시작 event_id 중복 방지, tenant별 API조회와worker/engine SQLclaim, pinned form에 따른 제출 type/required 검증을 구현했다. 일반 submit으로 select_card 승인을 우회하거나 시작 변수로 commands/approved_by 등을 주입할 수 없다. 완료 task에 human-response를 보내 다시 큐에 넣는 경로도409로 막았다. form contract는 API/worker/engine이 공유한다. 포털은 선택 instance의 정의·폼·모든 변수를 읽고 JSON upload/등록/버전선택/시작을 제공한다. 폴링 중 중복 reload로 상세가 비는 문제도 수정했다. 인증/운영 RLS 완료는 아니다.

실측: 최종 process rebuild exit0, 전체294passed/기존FastAPI경고2(`definition-registry-regression.xml`), 실제HTTP/Pg/Neo4j15/15(`definition-registry-live.json`). 실제 검사에는 mutable form_def 변경 후 API/worker prepare의 구폼 보존, 같은입력 다른버전 분기,8동시등록4성공4충돌, 타tenant 조회/submit/event읽기 거부와 worker/engine claim격리가 포함된다. 임시SQL/graph잔존0. 기본 실제20×legacy경로35/35 exit0(`definition-registry-legacy-scenario.log`): instance8e1c1fb1-bbb1-4626-a8e6-c2b56dce8899,INC-1003-01-a912,CMD-1003-0001-7f37; 물리제어/재관측/작업지시/종결 후 reset. 이 회귀는 실제Codex 실행이 아니다.

포털 agent-browser로 registry-9457bf4b09의 두 JSON파일 upload→등록→선택→시작→제출을 조작했다. v1 점수7 accepted; v2 메모누락은거부, 점수7+메모 rejected. 캡처 `definition-registry-ui-form-v2.png`, `definition-registry-ui-v2-variables.png` 직접확인. API원문/그래프는 `definition-registry-ui.json` 저장 후 해당fixture만삭제(SQL/graph0). 1440/390 가로넘침false·browser errors0. UI의 모든 화면/모든 타입 직접검증을 뜻하지 않는다.

강의자료: `docs/examples/inspection-review-v1.json`/v2(자동seed아님), `docs/definition-authoring.md`,교재13장,75h실습표를 동기화했다. 점수5/10은 임의 교육예제임을 명시. 교재check_book 문제0,1280/390 넘침/깨진이미지/JS오류0 및 해당절캡처 직접확인(`definition-registry-book.json`). 학생 전체리허설/시수실측은 미완료. PowerShell 프로세스확인remainingWorkers0(`definition-registry-process-check.json`),자체브라우저종료. 서비스는 다음검증을위해기동유지.

남은 경계: 기존 anomaly_response1.0 폼은 legacy-live, tenant MCP/사용자 정보도 실시간이다. 새 등록정의의 실제Codex/MCP는 이번시험에없으며 우선후속. 전체BPMN, 인증, 시작입력의 전체계약, unknown event routing, Incident terminal callback/동시상태변경/재시도복구는 아직 별도 감사대상이다.

## A017 기본 HYD2.0 계약 및 새 정의의 실제 Codex SQL 실행

A016에 이어 기본 설비 정의를2.0으로 발행했다(DECISIONS25). 기존1.0바이트/archive는그대로이고 새6폼계약+상급자note출력보존을 명시했다. 관련21passed/전체295passed2warnings(`definition-v2-regression.xml`). process rebuild0. 빌드직후 준비전 첫시도는RemoteDisconnected exit1(`definition-v2-legacy-scenario.log`); API기동/버전2.0확인뒤 실제경로35/35exit0(`definition-v2-legacy-ready-scenario.log`),INC-1003-01-0c6e/CMD-1003-0001-fefe/WO-1003-61A0 및reset확인. 실패를삭제하거나성공으로바꾸지않았다.

새 `scripts/probe_registered_codex.py`로 등록API→실제worker.main poll/claim→Codex(cliagents)→enterprise describe_schema→모델작성 SELECT→실제query→typed폼저장→엔진분기를 실행했다. 정의 codex-registry-df9b60d2의 v1은 `code LIKE 'HYD-%'` 결과3/multiple, v2는 `code='HYD-01'` 결과1/single 및필수note를 제출했다. 두작업DONE/COMPLETED,두독립session,실제모델gpt-5.6-sol/low. 각 describe_schema/query1회,총4MCP호출/오류0. 도구반환행 [[3]]/[[1]]을직접DB집계 및최종출력과대조했다. 프로세스가고정숫자를돌려준시험이아니다.

증거 `.evidence/reaudit/codex-registry-df9b60d2/{report.json,instance-1.json,instance-2.json,events-*.json,graph-*.json,v*-*.events.jsonl,rollout-*.jsonl}`. 워커가쓴원시CLI trace가실제로보존됨을확인했다(이전F에서는코드만추가했던공백해소). 실행23초/25초가량은로그 task시각기준이며수업시간측정아님. 두완료실행/정의는실제조회사례로DB에보존했다. PowerShell종료 remainingWorkers0(`registered-codex-worker-stop.json`),사용자config해시이전baseline과동일. 기본서비스는20×/legacy유지,이검사에서설비/업무쓰기없음.

이것은 등록정의와폼변경이실제LLM SQL/분기를바꾼증거다. 규칙→시계열SQL/PromQL·오류수정루프·자연어프로세스생성 전체검증은아니다. HYD2.0의네Codex판단작업+PLC전체경로는아직별도이며 F의1.0결과와혼동하지않는다. 남은동시전이/오래된승인/미지원경보/실패복구/SOP근거를계속감사한다.

A017 교재13장·definition-authoring·요구추적표 동기화 후 check_book0,1280/390 가로넘침/JS오류/깨진이미지0,새설명절두캡처직접확인(`definition-v2-book.json`). 현재process instance/legacy/20×,plant API200. 전체목표는active이며 다음재개점은HANDOFF§9 G다.

## A018 legacy bridge의 다건 claim 누수와 큐 기아

원본 agent-sdk58ca16d8680345ce0b030808c12712823248bd49의 function.sql8~47은원자적CTE/UPDATE/SKIP LOCKED, database.py131~170은p_limit1로전체큐를폴링한다. HYD의레거시브리지는특정결정한건만아는데limit10조회후자기행에서return하여뒤행을STARTED/consumer=legacy-agent로남겼다. 앞행반환도FB_REQUESTED를NULL로변경했다. 11번째대상은못찾았다. 새반례2실패(`claim-scope-red.xml`)로확인.

fetch_pending_task에선택적proc_inst_id범위를추가해tenant/instance필터를LIMIT앞에두었다. _claim_own은대상1개만claim하고타행의상태를건드리지않는다. 실제worker는기존전체tenant큐폴링을유지한다. 단순히반환뒤남은행을푸는임시조치는재개요청소실/처음10개기아를해결하지않으므로사용하지않는다.

수정후관련35passed/전체297passed2warnings. 실제PostgreSQL `probe_claim_scope.py`7/7:14인스턴스의첫/12번째claim,타행byte-equivalent상태보존,FB_REQUESTED보존,타tenant거부,8동시소비자중1승자,일반worker가나머지11개수신. 임시tenant/인스턴스정리잔존0(`claim-scope-live.json`). 컨테이너배포는다음묶음에수행한다.


## A019 Incident 실행 검색에 UI 목록 한도가 유입됨

_instance_of_incident가최근RUNNING100개를읽고Python에서incident를찾았다. 105개새실행뒤오래된대상은None,같은Incident문자열의다른tenant실행이더새로우면그행을선택하는반례2실패(`incident-lookup-red.xml`). list_instances의선택적incident_id를JSONB포함조건으로SQL에서tenant/status와함께LIMIT전에적용하고런타임조회는limit1로바꿨다. 화면의페이지크기를늘리는우회는하지않았다.

수정후관련29passed/전체299passed2warnings. 실제PostgreSQL107인스턴스(자기tenant106+foreign1)에서5/5:기본첫페이지밖임을확인→정확대상조회→foreign은자기행만→종료된대상은foreignfallback없음→없는incident없음. fixture정리0(`incident-lookup-live.json`). A018buildexit0후A019도process배포exit0(`incident-lookup-build.log`),healthz준비확인후현재legacy실제경로재검증중(`claim-lookup-legacy-scenario.log`).

남은동일tenant/동일Incident다중실행의소유권은아직정의하지않았고현행최신실행한건선택을유지한다. 이조회수정이callback영속전달/동시전이/전체프로세스복구를보장하지않는다. machine.py144~208을대조하면정상CLOSED는성공재관측뒤에도달하므로'모든terminal을거짓성공으로처리한다'고결함확정하지않는다. callback유실후_run_command/_run_reobserve대기복구와늦은승인은별도반례가필요하다.

### 다음 반례 후보 (아직 수정/실행 검증 전)

- fire_timeouts는IN_PROGRESS최대200행을가져온뒤due를거른다. 타작업에가려진timer의기아가능성을실제반례로확인할것.
- worker._stream은이벤트가도착해야취소/timeout을검사한다. upstreamcli-agent4475bf797a91fb6c6540e8a4f4b7f98012cf21b7의core/runner.py전체는stream_exec on_start로자식핸들을받고큐/별도pump와시계시간제한으로무출력실행을종료한다. 설치cliagents execution.py196~354도on_start를제공한다. 기존HYD는이를사용하지않는다. 다음에원본방법을동기워커에이식하되실제무출력자식프로세스/자식트리잔존/취소후늦은결과로상태가되살아나는문제를검증한다. 단순모의이벤트취소검사로대체하지않는다.

A018/A019 배포 후 실제 HYD2.0 legacy 경로 **35/35, exit0**. INC-1003-01-53c3 / CMD-1003-0001-b8fd / WO-1003-397D, PLC ACK·재관측·작업지시·ev:closed·Execution 투영 및 마지막 reset 확인. `.evidence/reaudit/claim-lookup-legacy-scenario.log`. PowerShell에서 worker/scenario 프로세스 잔존0(`claim-lookup-process-check.json`). 이번에는 Codex를 다시 실행하지 않았으며 A017 두 정의 조회의 결과와 구분한다.


## A020 무출력 CLI 중단과 취소 후 늦은 결과 차단

실제 3초 무출력 Python CLI로 deadline 0.25초·draft 취소·엔진 status 취소를 검사했을 때 3개 실패했다(`worker-control-red.xml`). stdout 이벤트를 기다리는 루프 안에만 중단 검사가 있어 출력이 없으면 확인하지 못했다. 취소 직후 결과/오류를 저장하는 반례도 2개 실패했다(`worker-late-result-red-valid.xml`). 앞선 `worker-late-result-red.xml`의 save 사례는 빈 guide_card fixture 오류였으므로 유효한 race 증거에서 제외한다.

cli-agent4475bf7 core/runner.py의 pump/queue/on_start 계약을 참고해 `worker/process_control.py`를 분리했다. 별도 reader와 주기적 deadline/취소 검사, 원본 cliagents parser/teardown, reader thread 안의 _LAST_RUN 읽기를 유지한다. Windows Job Object의 KILL_ON_JOB_CLOSE로 CLI와 그 자식 MCP를 함께 정리한다. 직접 부모가 먼저 끝나도 pipe를 잡은 자식을 정리한다. Microsoft 원문: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects . Linux process group 구현은 이번 실행 환경에서 실측하지 않았다.

각 claim은 고유 consumer token, 각 CLI/HITL 작업은 UUID job ID를 쓴다. 결과·오류·질문대기 저장은 DB의 consumer 일치 + IN_PROGRESS + STARTED 조건 UPDATE로 수행한다. 취소·재할당·이미 완료된 작업에 도착한 결과는 거절한다. 성공 이벤트는 결과 저장 성공 뒤에 기록한다. 이 보장은 새 worker의 조건부 저장 경로이며 legacy RPC 등 owner 인자를 생략하는 기존 호출까지 보호한다고 하지 않는다. 상태와 events의 원자적 outbox, 엔진 전체 동시전이는 후속이다.

검증: 관련32passed, 최종 전체 **304passed, 2 기존 FastAPI warnings** (`worker-control-regression-final.xml`). `scripts/probe_worker_control.py` 실제 Pg/Windows **9/9 exit0**, `.evidence/reaudit/worker-control-a1a05c37/report.json`: 취소status/draft/재할당/DONE에서 늦은 result/error/pause 모두 거부, 동시8writer 중1개 성공, DRAFT 보존, timeout .862초/cancel .371초/부모선종료 .844초에 트리 종료. PowerShell로 대상PID6개 remaining[] 확인, SQL fixture remaining0. 이는 Python 자식으로 중단 경로를 검사한 것이며 실제 Codex 강제취소 실측과 구분한다.

정상경로: `probe_registered_codex.py` 실제 worker.main/Codex가 새 정의 `codex-registry-477f7e6f` v1/v2를 실행했다. v1 ent.assets HYD-% 3건→multiple, v2 HYD-01 1건+필수note→single, 두 작업 DONE. 각각 describe_schema/query 1회씩·도구오류0, raw CLI trace 보존. `.evidence/reaudit/codex-registry-477f7e6f/report.json`, `controlled-codex-probe.log`. 실행정의/결과는 증거로 DB에 남긴다. PowerShell 중단검사 `controlled-codex-worker-stop.json` remainingWorkers0. 해당 실행 뒤 job_id UUID 변경은 최종304테스트로 확인했으며 다음 HYD 실제 경로는 새 worker로 검증한다.


## A021 후속 반례 관찰 — 타이머 페이지 한도와 유실된 callback (관찰 당시 미수정)

A020 HYD2.0 실제 실행 대기 중 MemoryRepo/FakeHooks로 별도 관찰했다. 타이머가 열린 대상 뒤에 start_date가 더 이른 정상 IN_PROGRESS 작업205개를 생성하면 총207개 중 list_workitems 기본200개에 타이머가 없다. 만료 후3회 fire_timeouts 호출 모두0이며 타이머 IN_PROGRESS가 유지된다. `.evidence/reaudit/timer-callback-observation.json`. fire_timeouts의 IN_PROGRESS 일반 목록→파이썬 due_date 필터 순서가 원인이다. 실행용 due timer 조회를 화면용 목록과 분리할 필요가 있다. 실제Pg/수정/회귀는 아직 하지 않았다.

같은 관찰에서 command를 실제 runtime.select로 실행해 SUBMITTED+service consumer 상태로 두고 FakeHooks의 Incident 상태를 RESOLVED로 바꿨으나 callback을 전달하지 않았다. poll_once3회0, command SUBMITTED/instance RUNNING 유지. 이것은 실제 네트워크 장애 재현이 아닌 콜백 누락 모델이며, 재기동/시간경과 후 회복 전체 검증은 아니다. 영속 상태 재조회와 엔진의 순서·동시성·소유권을 함께 설계해야 한다.

참고 completion b272c9ab458f3ca3e18fe286e4e770d291b99e89의 polling_service/workitem_processor.py1741~1950을 읽었다. 원본은 dueDate→Quartz cron fallback 및 tenant/process/activity/task ID를 register_cron_intermidiated RPC에 전달한다. HYD는 현재 경계 타이머를 SQL 작업으로 폴링하므로 원본 크론 실행이 이미 이식됐다고 말하지 않는다. 원본 RPC 정의·스케줄러 실행부는 아직 미열람이다. 실행 중인 HYD2.0 컨테이너/워커 로직에는 이 관찰로 인한 변경을 하지 않았다.


## A022 업무 MCP 조회 경계와 SQL 오류수정 원본 (미수정)

`enterprise_mcp/sql_guard.py`는 SELECT 전용 DB role까지 3층이라고 설명하지만 server.py의 DSN 및 compose ENTERPRISE_DSN은 postgres다. 실제 실행 중 enterprise-mcp 컨테이너의 EnterpriseTools.query에 `SELECT current_user AS role`와 `SELECT count(*) AS count FROM public.todolist`를 전달했다. 둘 다 result ok, role postgres, public 작업260행 집계. `.evidence/reaudit/enterprise-reader-boundary.json`. 개인정보/작업 본문을 읽지 않고 역할과 집계만 관찰했다. ent 전용 도구라는 설명과 실제 접근 범위가 다르다. read-only transaction과 statement_timeout은 코드상 있지만 이것이 ent만 읽는 권한을 뜻하지 않는다. 실제쓰기 우회는 시험하지 않았다. 기존 SQL 문자열 필터 대신 AST/허용원천과 전용 SELECT 역할을 함께 검증해야 한다. 실행 중 HYD Codex 경로의 MCP는 아직 변경하지 않았다.

neo4j-text2sql25ab12a8b9129b99fa3e83519214e71e12962a9d `app/react/tools/validate_sql.py`1~180,299~542, `generators/validate_sql_repair_generator.py` 전체 및 prompts/validate_sql_repair_prompt.md 전체를 읽었다. SQLGuard→Postgres EXPLAIN→preview, 오류를 FAIL/selected_sql/suggested_fixes로 반환하고 규칙수정 후 LLM수정 후보를 다시 guard에 넣는 계약을 확인했다. 설명주석은 one-shot이나 flag는 유효한 변경SQL이 반환된 때만 설정되므로 실패호출까지 정확히1회라고 주장하지 않는다. 실제 LLM 호출은 아직 실행하지 않았다. sql_autorepair.py는 한 번 출력이 잘려 부분 열람이며 전체 분석으로 세지 않는다. HYD MCP는 현재 INVALID/UNKNOWN envelope만 반환한다. 기존 A017 정상 SELECT 생성 실측은 오류수정 루프의 증거가 아니다. 후속은 없는컬럼/빈결과/업무원천밖/금지쓰기/연결실패를 실제 Codex와 검사하고 원질의·수정질의·판정·현재값 출처를 보존하는 것이다.


### A020 실제 Codex 취소 추가 검증

`probe_codex_cancellation.py`가 별도 정의 codex-cancel-be9ed0bb를 HTTP 등록·시작하고 실제 session01a103a6-e8ce-7720-93b9-78f96f925069를 관찰했다. 정확한 작업/consumer/IN_PROGRESS/STARTED 조건으로 DB 취소 신호1행만 주입했다. **1.027초 후 CANCELLED/consumer null/task_cancelled, 출력·task_completed 없음**. PowerShell에서 해당 workdir의 codex.exe와 자식6개(conhost,uvx,uv,mcp-neo4j-cypher,python2) 수집 후 전부 remaining[] 확인. report/instance/rollout/summary는 `.evidence/reaudit/codex-cancel-be9ed0bb/`, 실행log `actual-codex-cancel.log`, exit0. 사용자용 취소API/UI 또는 전체인스턴스 취소를 구현했다는 뜻은 아니다. 이 의도적중단 fixture는 instance RUNNING + 작업 CANCELLED로 보존하고 성공으로 바꾸지 않았다.

### A020 HYD2.0 전체경로 진행 중 발견한 검사기 오류

2×bridge off·네 Codex 작업270초 DONE·고정폼2.0·운전원403·생산관리자 승인·PLC ACK 후 재관측 진행. 새 검사 `selection uses ... pinned form`에서 raw 정의 폼과 API 폼의 dict 전체 동일성을 비교해 실패했다. 실제 API는 공통 pinned_form 계약에 따라 `id:select_card`를 추가한다. fields_json/선택지/버전/source는 동일(`controlled-hyd-v2-form-comparison.json`). 검사기를 해당 metadata 규약에 맞춰 고쳤다. 같은 실제 인스턴스에 수정검사와 필드/선택지/source/버전 변조4반례를 실행해 **5/5**(`controlled-hyd-v2-form-recheck.json`). 이미 실행 중인 원본 전체 시험의 실패는 삭제·PASS로변조하지 않는다. 전체결과는 원본로그 종료 후 별도 기록한다.


### A022 실제 Codex 컬럼 오류 수정 실험

`probe_codex_sql_repair.py`가 별도 정의 `codex-sql-repair-aac86b9d`를 등록해 의도적으로 옛 컬럼 asset_code를 가진 조회부터 실행시켰다. 실제 Codex(session01a103a8-e7d4-7b61-a82e-7dfe9e198016)가 enterprise/query→describe_schema→query 순서로 수행했다. 첫 쿼리는 column asset_code does not exist, 현행 schema의 code로 최소 수정한 두 번째 쿼리 결과1건, 최종폼 count1/sql/note 및 DONE/COMPLETED 확인. `.evidence/reaudit/codex-sql-repair-aac86b9d/{report,instance,summary}.json`, rawCLI/rollout와 `actual-codex-sql-repair.log`, exit0. 명시적 오류 주입 실험이며 모든 SQL 오류복구/PromQL/원천격리 완료는 아니다. ent외조회 권한 결함은 그대로 미수정이다.

오류계수 경계도 교정했다. 이 경우 MCP 프로토콜 is_error는 false지만 반환 envelope는 result:error다. collect_worker_evidence.py에 business_tool_errors를 별도로 추가하여 이 실험의 transport오류0/업무오류1을 확인했다. 잘린 events 출력까지 오류없음을 증명한다고 하지 않으며 rawCLI 검토가 필요하다.

최신 worker 종료: `controlled-hyd-v2-worker-stop.json` **remainingWorkers0/remainingTreePids[]**, PowerShell exit0. SQL복구와취소 추가실험 완료 뒤 종료했으며 main HYD 재관측은 별개로 계속된다.


## A023 실제 CLI 중간 실패와 도구 이력 완전성 (후속)

A020 HYD2.0 네 작업은 정상폼을 제출했지만 events에는 tool_start17/tool_end16이다. task별(job_id,tool_use_id)로 짝지으면 rank의 Neo4j item_1 종료가 없다. tool_use_id는 세션마다 재사용되므로 전역 ID만 비교하면 이 누락을 놓친다. raw ExecEvent trace도 동일, 실제 Codex rollout의 완료 MCP는2+3+4+7=16이다. rank rollout에는 context/schema_prompt.md를 PowerShell Get-Content로 읽으려다 blocked by policy가 된 functions.exec 실패1건, 이후 재조회·카드제출로 진행한 기록이 있다. 연결되지 않은 tool_start와 이실패의 정확한 CLI 이벤트 생성 관계는 아직 미분석이며 parser오류라고 단정하지 않는다. `.evidence/reaudit/controlled-hyd-v2/{event-completeness,rollout-audit}.json` 및 원본rollout4개. 네 모델은 모두gpt-5.6-sol/low.

collect_worker_evidence.py는 이제 job_id와 tool_use_id를 함께 써 unmatched_tool_starts를 별도 기록한다. 업무완료와 중간오류/이력완전성을 구별한다. 이번 실행을 '도구17회모두성공/오류0'이라 쓰지 않는다. rank의 tool discovery에는 HYD 외 설치된 앱 도구 메타데이터도 보였으나 해당 외부업무도구 호출은 이실험에서 확인되지 않았다. tenants.mcp 세 서버만 존재하는 완전격리 환경으로 설명하지 않는다. 호스트 CLI 도구노출/읽기권한/중단이력정규화는 후속 조사다. 전역Codex config는 변경하지 않았다.


### A020 최종 HYD2.0 실행과 복구 (06:35 KST)

instance anomaly_response.18272c67-6fb2-4780-b519-e789b4ca3cec / INC-1003-01-4e20 / CMD-1003-0001-0896 / WO-1003-7972. 2×실험: 경보322초, Codex4작업270초, 사람권한403/승인, PLC ACK, 재관측601초(복구값충족/CLEAR대기1회연장), 8작업DONE·2가지CANCELLED·ev:closed/COMPLETED, Execution그래프 및 CMMS실제행 확인. 원본검사 **35/36 exit1**(`controlled-hyd-v2-scenario.log`). 실패는 추가폼검사기의 id metadata 처리 오류였고 같은실제인스턴스의 수정검사/4변조검사 **5/5**. 수정후 전체36개 재실행은 하지 않았다. 기록을36/36으로 바꾸지 않는다.

모든세션 gpt-5.6-sol/low. tool_start17/end16 및 내부파일읽기실패1은A023에별도보존. 원본rollout4개·ExecEvent trace4개·instance/incident/graph/summary/configuration-and-errors는 `.evidence/reaudit/controlled-hyd-v2/`에있다. 명시된완료MCP결과16건의isError/result:error없음은 내부script실패나미종료start없음과다르다.

기본복구 compose exit0(`controlled-hyd-v2-restore.log`). 실제환경 plant-sim/detector/process TIME_SCALE20, process/agent AGENT_BRIDGE legacy, process WORKER_URL 기본agent-worker. healthok·설비3대reset/RUN·PowerShellworker0/remainingTreePids[](`controlled-hyd-v2-restored.json`, `controlled-hyd-v2-final-process-check.json`). 사용자config SHA256 836330d564fe7cbd72946985bfa2ca90bd1b7eac22aa5aa6143489972cd0db0a 동일. 진행중실험없음. 취소 fixture만 의도적으로RUNNING/작업CANCELLED 보존했으며 성공상태로변경하지않았다.

교재13의 폼 버전계약/취소원리 및 실제취소검증 경계를 동기화했고1280/390새문단렌더를직접검수했다. 학생리허설시간과전체교재검수는미완료다. 다음은 A022 읽기경계, A021 기한/콜백복구, A023 CLI도구환경·이력, 그뒤 전체36검사 재실행이다.


### A022 조회 경계 수정과 실제 검증 (2026-10-04)

수정 전 추가15검사 중12실패/전체18통과를 보존했다(`enterprise-scope-red.xml`). 문자열 regex를 sqlglot27.24.2 AST/Scope 검사로 교체했다. 단일 SELECT/집합 연산, 실제 ent 테이블, 함수 허용 목록, 쓰기/잠금/사용자 정의 cast 금지, 바깥 LIMIT 최대200을 검사한다. 문자열 안 delete/주석 표시는 보존하고 CTE/CASE/중첩 LIMIT/OFFSET을 처리한다. 별도 역할 hyd_enterprise_reader를 도입해 MCP에 postgres를 넣으면 연결 단계에서 거절한다. 고정 조회/스키마/임의 조회 모두 read-only/5초/search_path 제한을 사용한다.

`20261004000003_enterprise_reader.sql`을 기존 DB에 트랜잭션으로 적용했다(해시 `enterprise-reader-migration.json`). 현재 ent16표 SELECT와 조회 RLS 정책, 7읽기 RPC를 부여했다. PostgreSQL 함수의 기본 PUBLIC EXECUTE 때문에 기존 anon/authenticated만 회수한 쓰기 RPC는 여전히 상속 실행 권한이 있었다. 두 쓰기 RPC의 PUBLIC EXECUTE를 회수하고 service_role은 유지했다. SECURITY DEFINER 함수/ent뷰·외부표는 현재 DB에 없음을 확인했다. 새 데이터원/함수 추가에는 별도 권한 검토가 필요하다. 참고: PostgreSQL 공식 [권한 문서](https://www.postgresql.org/docs/current/ddl-priv.html), 구현 대조 neo4j-text2sql25ab12a app/core/sql_guard.py 전체.

enterprise-mcp 재빌드 후 `/healthz` role=hyd_enterprise_reader/read_only=true. `scripts/probe_enterprise_scope.py`를 배포 컨테이너에서 실행해 실제 DB+HTTP MCP **49/49**. ent16표 행 수가 관리자 조회와 일치(0행 표도 포함), 7도구 facts 정상. default read-only를 고의로 해제한 별도 롤백 트랜잭션에서도 public.todolist/UPDATE/DELETE/SET ROLE/두 쓰기 RPC는42501거절, service_role EXECUTE 유지. schema/CTE/CASE/문자열/LIMIT/OFFSET/정상0행·집계0 통과, 불법 조회 INVALID/없는컬럼 UNKNOWN. 전체 **319 passed, 기존경고2**. `enterprise-reader-live.json`, `enterprise-reader-regression.xml`.

실제 Codex `codex-registry-03530b1a` v1/v2는 count3→multiple/count1+note→single, 둘 다DONE. `codex-sql-repair-a0967013`은 asset_code오류→describe_schema→code로수정/1건/DONE. 원문SQL/오류/수정SQL/실행정의/rawCLI보존. 전체HYD2.0 36검사는 2×/bridge off 조건으로 실행 중이며 아직 결과를 판정하지 않는다. DB권한 검증은 이 공장의 업무표 접근 범위이며 외부 앱/호스트 Codex 도구 전체격리는 A023 미결이다.


### A021 실제 DB에서 같은 반례 관찰 (미수정)

`scripts/observe_timer_recovery.py`를 별도 tenant로 실행했다. 정상 userTask 인스턴스205건이 먼저 있는 DB에서 대상 timer는200행 조회 밖이고, 만료 후3회 검사 모두0/IN_PROGRESS다. 같은 인스턴스의 명령을 FakeHooks로1회만 발행하고 Incident를RESOLVED로 바꾸되 callback을 생략했다. runtime 객체를 새로 만들어3회poll해도0/command SUBMITTED/instance RUNNING이다. `.evidence/reaudit/timer-observe-252521ec.json`. 이 검사는 실제PostgreSQL/가짜외부효과이며 실제프로세스재시작·PLC통신장애를 재현한 것은 아니다. 실험tenant와인스턴스는정확한키로정리했고잔여0. 전체HYD물리시험과분리했다.

원본 process-gpt3335272b3f6978886e2b661b9977a0acfe7991e9 `docker-infra/volumes/db/init.sql`2101~2270에서 register_cron_intermidiated/update_todolist_status_with_year/update_todolist_status 본문을 확인했다. pg_cron에 등록해해당proc_inst_id/activity_id를SUBMITTED로 바꾸고unschedule한다. 이 본문은 tenant/task_id/기존status 조건을 사용하지 않으므로 HYD에 그대로 복사해 동시성·고정실행계약이 해결됐다고 할 수 없다. completion b272c9a database.py1016~1045는30분updated_at 기반consumer해제이며, HYD가이미발행한명령의영속상태재조회를대신하지않는다.

후속 구현은 실행용due timer 조회와 tenant/정의/실행조건을 LIMIT 이전에 적용하고, 동일인스턴스전이의DB트랜잭션/잠금과재조회로 승인-시간초과 및 callback-poll 경합을 처리해야 한다. 상태전이뒤감사/그래프투영·외부명령의실패복구는별도효과경계로검증한다. 단순목록한도증가나command재발행으로덮지않는다.


### A023 추가 추적 — 원문 도구 호출과 조기 실패

기존rank rollout01a103a5의response_item20~21을확인했다. functions.exec가Get-Content와6개MCP를Promise.all로동시호출했고,PowerShell실행은정책거절로script전체가즉시실패했다.27~34에서MCP만다시호출해완료했다. 시작만남은MCP는이실패묶음과시간상일치하며rawCLI에도종료가없다. 라이브러리parser가종료이벤트를버렸다고단정할근거는없다. allSettled로각실패를회수하고완료/중단/미확인상태를구분하는방향이필요하다.

CONSTITUTION이Codex에빠졌다는가설은runner.py98에서반증됐다. project_doc_max_bytes0일때도규칙과스키마는prompt앞에직접들어간다. 파일읽기정책을우회할필요없이이본문/MCP로업무를수행할수있다. 로컬codex exec --help와features list는호출별--disable 기능 및apps=true를보인다. apps비활성화로외부도구가실제로사라지는지는아직실행검증전이며현재워커설정은변경하지않았다. 사용자config/rules는수정하지않았다.


### A022 실제 Codex의 0행/거절 판정

`probe_codex_query_boundaries.py`가 등록한 codex-query-boundary-0978b30c v1/v2를 실제 워커가 실행했다. v1은 존재하지 않는 설비 코드를 조회해 MCP result:ok/rows:[]/row_count:0을 받고 outcome:empty로 제출했다. v2는 public.todolist 집계를 의도적으로 요청해 MCP INVALID 거절을 받고 outcome:rejected로 제출했다. 둘 다 DONE/COMPLETED이며 실패를 정상0건으로 바꾸지 않았다. report/instance/rawCLI를 보존했다. 처음 시험 정의는 select 폼에 options를 써서 등록400으로 거절됐고, 현행 계약인 items로 고친 뒤 새 정의로 실행했다. 첫 실패 로그도 보존한다.

### A023 호출별 앱 도구 비활성화 적용

별도 `probe_codex_tool_scope.py`에서 사용자 설정은 그대로 두고 --disable apps를 전달했다. 첫 실행 codex-tool-scope-64283d7b는 raw ALL_TOOLS 목록에 업무 MCP19개만 보였으나 모델이 enterprise query 인자를 query로 잘못 넣어 실패하고 sql로 수정해 재시도했다. 도구실패0 조건을 통과하지 못한 기록으로 보존했다. 정확한 인자 계약을 프롬프트에 적은 새 실행 codex-tool-scope-1fdcc51c에서는 같은19도구만 노출되고 Neo4j schema/enterprise SELECT count3/hyd-dmn inputs 세 호출 모두 완료했다. 사용자config 해시는 기존값과 동일하다.

이 실측을 근거로 worker.bridge에 --disable apps를 적용했다. 설치된 CLI의 built-in shell/browser 같은 도구까지 없어진다는 뜻은 아니며 OS 파일 접근 격리도 별도다. workspace.py의 '디렉터리만으로 격리' 주석을 실제 경계에 맞게 고쳤다. 기존 워커/자식0을 PowerShell로 확인하고(reader-worker-before-apps-stop.json) 새 워커를 시작해 두 정의를 재검증 중이다. 네 태스크를 마친 현재 HYD 전체 시험은 앱 비활성화 전 워커로 수행한 기록이다. 실행 중인 process/plant/시계 조건은 바꾸지 않았다.


A023 적용 후 worker.main 재실행: codex-registry-d5b5ac11 v1 count3→multiple/v2 count1+note→single, 둘 다 DONE. `.evidence/reaudit/reader-apps-registered.log`, 해당 정의 report/instance/rawCLI가 근거다. 변경 후 전체319 passed/기존경고2(`reader-apps-regression.xml`). `reader-apps-worker-stop.json`에서 PowerShell이 워커/자식0을 확인했다. 전체 HYD2.0 시험의 재관측은 워커 없이 process 서비스에서 계속 진행 중이다.

교재13에 업무SQL 권한/실패와0행 구별 설명을 추가했다. 1280/390 렌더 직접 검수 및 check_book 문제0(`a022-book-check.log`, `book-render/a022-reader-*.png`). 현재 실행의 포털 실제화면도 agent-browser로 확인해 정의2.0/6개완료/재관측을 캡처했다(`a022-portal-flow.png`, `a022-portal-reobserve.png`). 이는 해당 두 화면의 관찰이며 전체UI 검수나 강의 리허설 완료를 뜻하지 않는다.


### A022 최종 전체 경로와 환경 복구

`reader-hyd-v2-scenario.log`는 **36/36, exit0**. 인스턴스 anomaly_response.d8e0d27e-8388-4fec-a7b8-eb869ac85dd0, Incident INC-1003-01-7ee1, CMD-1003-0001-6d21. 경보322초, 네 Codex 태스크246초, 고정폼2.0/403/승인/ACK, 재관측600초(경보해제 대기로1회연장), WO-1003-DC51, ev:closed/COMPLETED. 이전 원본35/36을 다시 표시한 것이 아니라 새 독립 실행이다.

`reader-hyd-v2/`에 최종instance/incident/graph/summary, rawExecEvent4개·rollout4개와모델감사를 보존했다. 모두gpt-5.6-sol/low, MCP시작17/종료17, 기록된transport/업무오류0, 미종료start0, rollout custom-tool의Script failed0. 포털의 실제완료8/8 화면도 직접검수했다(`a022-portal-completed.png`). 전체CLI/권한/강의완료를 뜻하지 않는다.

복구 compose exit0. `reader-hyd-v2-restored.json`: plant/detector/process TIME_SCALE20, process/agent AGENT_BRIDGE legacy, 3설비reset/RUN, 기업MCP 전용reader/read_only/healthy. `reader-hyd-v2-final-process-check.json`: PowerShell워커0/자식[]. config SHA256 836330d564fe7cbd72946985bfa2ca90bd1b7eac22aa5aa6143489972cd0db0a 동일. 브라우저검수세션도종료했다. 진행중실험없음. 임시기동wrapper의상대Python경로오류는시험실행전에발생했고, PowerShell에서실제시험을시작한로그/exit로판정했다.

남은 A021/A023/HITL/승인재검증/문서인제스천·강의검수는미완료다. 최종재개위치를 HANDOFF §0/§9 G에 갱신했고 오래된 30초브리핑은 sources 보존본으로옮겼다.


## A021 적용 — 원자 전이·대기 서비스 복구와 실제 강제 종료

실행용 due_timers는 tenant/실행상태/due_date를 SQL에서 필터한 뒤 한도를 적용한다. waiting_services는 service consumer가 가진 command/reobserve를 키 순서로 끝까지 읽는다. 각 전이는 인스턴스와 자식 작업 행을 잠근 뒤 최신 상태/consumer를 확인하며 같은 DB 트랜잭션에서 작업·인스턴스·오류 이벤트를 저장한다. 외부 서비스는 SUBMITTED 행을 커밋한 뒤 실행한다. 만료 승인 차단, 늦은 claim/error 무시, callback 시 저장된 Incident 상태 재조회가 포함됐다. 엔진 내부의 한 인스턴스 작업 조회는 화면의 200행 한도를 쓰지 않는다.

새 반례7개 모두 기존 실패(a021-red.xml), 첫34/2실패 반환상태/잘못된 fixture 수정 후 관련36/36, 전체326 passed/기존FastAPI경고2(a021-regression.xml). 실제 Pg probe_instance_recovery.py **11/11**: 205개 오래된 작업 뒤 timer, 연결8개 동시 timer/승인/만료경합/callback, 마지막 instance 저장 실패 시 전체롤백, 새 runtime의 누락 callback 복구, 늦은 claim/error, 낡은 callback보다 현재 ESCALATED 사용, 외부 명령 성공 직후 SQL실패와 재처리, 대기105개 뒤의 완료대상 복구. FakeHooks 외부효과이고 실제 PLC 검사가 아니다. fixture 잔여0. 처음8/9는 escalation 사람이 확인하기 전에 자동 종료를 기대한 검사기 오류였으며 instance-recovery-pg-first.json에 보존했다. 최종 instance-recovery-pg.json/로그에 각 판정과 의도적으로 주입한 오류가 있다.

새 process 이미지 build exit0 뒤 **실제38/38 exit0**: scenario_instance_test.py --restart-during-reobserve, legacy bridge/정의2.0/20×. 인스턴스 anomaly_response.ac514778-4e59-49c4-b60b-69884d9fb597, INC-1003-01-034f. 실제 PLC ACK/CMD-1003-0001-a6b5 뒤 RE_OBSERVING에서 docker kill/start. 건강9.2초, 복구된 확인 작업0.2초. Store.restore의 기존 PROCESS_RESTART_REVIEW 정책을 유지하고 서비스 재조회가 reobserve recovered=false/생산관리자 작업을 연결한다. CMD_PUBLISHED1회/ID유지, 작업지시 미실행, 과거 승인400, 사람의 확인 뒤 ev:escalated. a021-live-restart.log 및 restart-anomaly_response.ac514778-4e59-49c4-b60b-69884d9fb597/에 전후 Incident/Instance/audit/graph 저장. 정상 회복이나 Codex 실행 증거로 대체하지 않는다.

남은 경계: 일반 engine claim 후 프로세스가 죽은 경우 기존30분stale해제/5분점검 정책이 남아 있다. SQL 전이 원자성이 Incident SQLite·CMMS·Kafka·Neo4j까지 분산 트랜잭션을 제공하지 않는다. 커밋 후 audit/graph/card 통지에는 durable outbox가 없으므로 임의 지점의 강제중단까지 보장하지 않는다. timer의 잘못된 정의/예외 행 격리와 전체 전이 복구, 승인 시 현재 PLC/업무조건 재검증은 후속이다. 현재 2×/bridge off/new worker로 새 Codex4개 정상경로 검사를 진행 중이다.


## A021 실제 Codex 재실행 실패와 부모/자식 잠금 순서 수정

첫 수정의 Pg11/11과 실제 강제종료38/38 뒤, 새 Codex 전체 실행은 task:compliance 결과 저장에서 DeadlockDetected로 실패했다. anomaly_response.c1cabf20-7981-44a7-bef9-dc6c8f731fef, INC-1003-01-bde2. diagnose/candidates 완료, compliance FAILED, instance RUNNING을 그대로 보존했다. a021-deadlock/에 3CLI세션/DB이벤트10시작10종료/오류1을 저장했고 a021-codex-scenario.log는 강제중단되어 전체검사 완료 로그가 아니다. PowerShell a021-deadlock-stop.json worker0/자식0, 설비reset을 확인했다.

원인은 todolist AFTER UPDATE 트리거가 부모 bpm_proc_inst.updated_at를 갱신하는데 워커는 자식→부모, 새 엔진 전이는 부모→자식 순서였기 때문이다. probe_process_lock_order.py --baseline은 보존된 a021-source/procdb.py와 이전 DB함수를 사용해 save/draft/release/update/worker claim/engine claim/raw save RPC 7경로 모두 교착을 재현했다. process-lock-order-baseline.json에 PostgreSQL 오류 원문을 보존했다.

새 migration20261004000004_process_lock_order.sql은 부모를 먼저 점유하는 claim_process_workitems와 이전RPC wrapper/save/stale정리를 정의한다. PgRepo의 개별 결과·상태·점유해제·일반 작업수정도 같은 순서의 트랜잭션을 쓴다. 잠긴 부모의 큐는 SKIP LOCKED로 건너뛰고 다음 poll에서 다시 받는다. 새 claim은 RUNNING이고 삭제되지 않은 프로세스 인스턴스 작업을 대상으로 한다. 인스턴스 없는 adhoc 큐는 이 경로의 지원 대상이 아니다. raw SQL로 직접 자식부터 갱신하는 임의 외부 클라이언트까지 잠금 순서가 강제되는 것은 아니다.

migration 적용/등록 SHA256 4b51fc7cee658fbc0adba50ea8d6ea12a5b07c1d6dcb6c2b0c5d6a9d334fc5ff. 같은 잠금 경합7/7, 기존claim범위7/7, Pg복구11/11, 질문원자성4/4, 전체334 passed/기존경고2를 재검증했다. a021-lock-process-build.log exit0 후 새 actual Codex 전체경로 재실행 중(a021-lock-codex-scenario.log). 이번 실패를 새 실행의 성공으로 덮지 않는다. 일반stale 지연/outbox 경계는 여전히 남는다.

## A024 실제 업무 질문·답변·동일 세션 재개

회의405~430은 사람 선택/알림 포털 요구다. 한 에이전트 작업 중 부족한 정보를 묻는 기능은 제품참고+사용자 확장 범위로 구분한다. 원본 cli-agent4475bf7 core/hitl.py 전문/executor.py291~465와 설치cliagents Codex parser281~454를 대조했다. 원본은 permission 이벤트와 세션/워크스페이스 pause 기록을 연결하지만 모든 업무 질문을 자동 지원하는 것은 아니다. HYD에서 파일쓰기 실패를 주입하자 HUMAN_ASKED인데 human_asked이벤트0/재점유0이 됐다. 자연어 질문은 필수폼 불일치로 FAILED가 됐다(hitl-observation/report.json; MemoryRepo/FakeCLI).

새4반례가 모두 기존코드에서 실패(a024-red.xml)한 뒤 질문·세션·이벤트·알림을 하나의 DB거래로 기록하고 파일은 cache로 낮췄다. 답변 job와 연결된 DB세션을 우선해 재개한다. 세션이 정말 없으면 기존업무/폼맥락을 포함해 새 실행임을 알린다. 명시적 __human_input__ 제어 JSON은 업무 질문이며 폼 완료결과와 혼용하지 않는다. 제어필드를 폼이름으로 예약하고 잘못된질문/권한확대필드를 거절한다. 포털에 선택지 버튼을 추가했으며 답변이 설비승인/CLI권한확대가 아님을 표시한다.

전체334검사와 실제Pg4/4(FakeCLI): cache쓰기실패에도 질문존재, 이벤트/알림저장실패는전체롤백후FAILED, 파일없는새worker동일세션, 연결8개동시답변중1개만저장. 기존 probe의 잔여0은 인스턴스 수만 확인한 값이며 events에 FK가 없음을 발견했다. 이후 probe cleanup에는 해당실행ID의 events 삭제/잔여검사를 추가했다. 이전 events 정리까지 검증됐다고 쓰지 않는다.

실제 Codex **두 실행 모두 통과**: codex-human-355872d8 같은정의1의 A/B. 질문각1/HUMAN_ASKED 후 worker PowerShell종료0, pending파일은 별도 이름으로 보존해 원래경로부재를 확인하고 새worker시작. 답변API에서 잘못된job409/정상200/중복409. A=HYD-02→pump, B=HYD-03→fan; 각각 enterprise schema/query 실제호출2회, 같은session유지, DONE/COMPLETED. A session01a103ed-9128-77f3-90aa-4f36ae712efb, B01a103ed-add9-7f30-a848-d40564925fb8, raw model gpt-5.6-sol. 폴더 report.json/answer-api.json/session-evidence-A,B/raw CLI에 보존했다. 검사기 첫400기대는 route의409계약으로 정정했고 그 전에는 정상답변을 보내지 않았다.

UI 직접클릭검증은 미완료다. 자동승인검사가 agent-browser를 포함한 실행명령을 거절했고 CUA getBrowser/createBrowserTab은 사용가능브라우저없음을 반환했다. 안전한 파일이름변경과 독립worker실행은 성공했다. 질문답변은 실제HTTP API를 테스트드라이버가 호출했다. 포털 JS문법검사는통과했지만 화면/버튼을직접봤다고쓰지않는다. 최종worker정리/환경복구는 진행중설비전체검사 뒤 수행한다.


## A025 후속 관찰 — 승인 결정과 인스턴스 저장이 갈라짐 (미수정)

MemoryRepo+실제 instance_mode._hooks/declib.approve/Incident 상태기계에 instance저장실패를 주입했다. select는 approve_decision에서 book을 APPROVED로바꾸고persist/audit한 뒤SQL인스턴스를저장한다. 뒤의저장이실패하면DB작업은IN_PROGRESS로롤백되지만book의APPROVED는남아다음선택이decision is APPROVED로거절된다. Incident는AWAITING_APPROVAL/외부업무호출0이었다. approval-atomicity-observation.json. 실제PostgreSQL/SQLite/PLC장애를검증한것은아니다. SQL트랜잭션추가만으로교차저장소원자성이해결되지않는반례다. 원자적승인의도와idempotent외부실행/영속outbox, 현재조건재검증을함께설계한다. 가동중실제전체검사코드는이관찰로수정하지않았다.


## A026 SOP 인제스천 원천 충돌·부분저장 관찰 (미수정)

HYD kgadmin.parse_manual1~83/main.py575~638을 다시 대조했다. 서로 다른 fan-a.md/pump-b.md의 HM-8.1 절이 동일ref로 반환되고 commit은 filename과무관하게 ManualSection{id:ref}를MERGE한다. 모든절을ks:manual-hm에PART_OF로연결하는고정경로도있다. 제목/원문sha/문서판본/절위치가식별계약에없다.

실제parse/commit함수에가짜_q 기록기를붙여, 유효한절+스킬이름이빈절차를전달했다. 결과400(스킬이름이비어있다) 전에ManualSection MERGE1회가호출됐다. main._q가각자Neo4j거래를열기때문에코드의all-or-nothing주석이성립하지않는경로다. manual-ingest-observation.json. 가짜_q 관찰이므로이번실험에서실제Neo4j잔여노드를생성했다고쓰지않는다. 가동중설비경로/온톨로지는변경하지않았다.

원본 ontology-studio6a229be8의tools.py520~663 batch_ingest를재열람했다. _source_id/parent_id와명시관계구조를참고하지만원본도노드/관계별오류를모아status:ok+errors를반환하고문자열은2000자에서자른다. 이를문서원문보존·원자적배치·인용정확성의보장으로복사하지않는다. HYD의A004 배치소유권/되돌림과문서원문/판본/절위치보존을연결하고, 파싱제안→사람검토→검증된한거래적재→실제질의까지검증해야한다.


## A021 수정 후 실제 Codex 전체 경로 (2026-10-04 08:04)

`scenario_instance_test.py --worker` 새 실행은36/36, exit0이다. 인스턴스 `anomaly_response.2884980d-60ed-4882-8b9f-a9bbe76cfb08`, INC-1003-01-1844/CMD-1003-0001-d45c/WO-1003-53C4. 실제4작업248초, gpt-5.6-sol 4세션, MCP18시작18종료/오류0. 2×에서450초 첫재관측 TS1=52.61/CLEAR아님으로150초연장, 최종TS1=51.42/CLEAR·recovered=true·ev:closed. 사람권한403/승인/PLC/CMMS/실제Neo4j연결까지검사했다. `a021-lock-codex-scenario.log`, `a021-lock-codex/`에원시CLI4/ExecEvent4/DB뷰/Incident/감사/graph/업무기록을보존했다. 첫실패교착증거를대체하지않는다.

PowerShell종료 `a021-lock-final-stop.json`: worker0/자식0. 기본20×/legacy와설비3기RUN복구 `a021-lock-restored.json`; config SHA256 836330d564fe7cbd72946985bfa2ca90bd1b7eac22aa5aa6143489972cd0db0a 불변. 이어지는A025승인전달모듈은이실행후연결하므로이36/36을A025검증이라고쓰지않는다.


## A025 승인 의도와 전달 복구 (2026-10-04 08:12)

승인복사본 검증→같은PG트랜잭션에승인의도/사람제출/타이머취소→커밋뒤전달→전달완료뒤후속작업으로구조를바꿨다. 외부업무응답실패는FAILED/작업SUBMITTED이며역할검사후같은스냅샷재전달만허용한다. legacyAPI우회도차단했다. 상세 [APPROVAL_RECOVERY.md](APPROVAL_RECOVERY.md).

실패11개→수정후API포함14개, 전체348passed/기존경고2. 실제Pg/SQLite/HTTP4/4(실제child os._exit73 뒤 PR-1003-17EC 한건유지; PLC/graph는대역), 기존Pg복구11/11. 배포뒤legacy실제설비36/36/e8e0dff5-fa85-4d9b-8485-b8b78acc98f6/WO-1003-0CC5, 승인DELIVERED/attempt1. 새Codex38검사실행중; 아직성공판정안함. 포털은문법검사와API경로검사만이며직접클릭미검수. 교재추가절1280/390직접렌더검토/check_book0. 일반outbox/현재조건재검증/전체강의검수는별도미완료다.


## A026 원문 보관 단계 (2026-10-04 08:28, 서비스 연결 전)

`manual_sources.py`는 SQLite에 tenant/논리문서UUID/원본SHA/원문bytes/추출기버전/페이지별전체텍스트·해시를 같은 트랜잭션으로 저장한다. 파일명으로 문서를 합치지 않으며 개정은 기존 ID를 명시한다. 인용의 페이지/문자좌표/문자열을 원문과 대조하고 알 수 없는 인코딩을 replacement로 감추지 않는다. PDF 빈 페이지는 OCR_REQUIRED다.

독립검사19 passed(`a026-sources.xml`), 전체367 passed/기존경고2(`a026-source-regression.xml`). 같은 파일명 두 문서, 기존 판본 보존, 새 프로세스 객체 재개, tenant거절, 동시12요청중한번저장, INSERT실패문서롤백, 원문/추출변조, 실제PDF두페이지/빈페이지/암호화를 검사했다. 합성PDF2페이지를 렌더 직접 확인했다. 이 자료는 실제 현장 매뉴얼·복잡한 표·OCR 정확도의 증거가 아니다. 기존API/Neo4j commit 결함은 아직 연결/교체 전이며 실제Codex추출·사람검토·개정/되돌리기·전체화면 검증은 미완료다. 설계는 MANUAL_INGESTION.md.


## A025 새 실제Codex 결과 (2026-10-04 08:36)

`a025-codex-scenario.log` 38/38 exit0. 2×/bridge off, instance666d3935-cd1b-4b15-bf3b-e82b2d4dfcd1, INC-1003-01-0bab, DEC-1003-026-a5f5, CMD-1003-0001-967c, WO-1003-4CBB. 네작업269초, 네세션실제모델gpt-5.6-sol, MCP20시작/20종료. 승인DELIVERED/attempts1, 운영자403후생산관리자승인. 450초관측52.71/CLEARfalse→150초연장→51.49/CLEARtrue, 총601초후ev:closed. `a025-codex/`에instance/incident/graph/audit/enterprise/원시ExecEvents/rollout/해시와raw-review를보존했다. 명시적MCP/JSON result:error/ExecEvent오류0이며 자연어의모든주장검증을뜻하지않는다.

PowerShell `a025-worker-stop.json`08:33: worker0/자식0. `a025-restored.json`:20×/legacy/3설비RUN, configSHA836330d564fe7cbd72946985bfa2ca90bd1b7eac22aa5aa6143489972cd0db0a불변. 복구확인첫시도는잘못쓴/api/mode가404였고실제/api/process/mode로정정했다.

## A028 실제 작업지시와 Incident 기록 불일치 (발견 당시 기록, 수정 결과는 아래)

위38검사결과를원본끼리대조해확인했다. `a028-work-order-observation.json`: Incident.workOrder.id=WO-INC-1003-01-0bab/sop=SOP-COOL-03, 실제service출력/enterprise.ref=WO-1003-4CBB, enterprise상세는SOP-COOL-02다. 감사WORK_ORDER_CREATED/INCIDENT_CLOSED는23:31:15.085Z, 실제업무service시작15.418Z/CMMS transaction15.557632Z다. 즉실제발행전성공기록이다.

코드근거: machine.on_timer201~208의WO-{inc.id} 임시번호생성/즉시CLOSED; instances._run_work_order502~513의별도HTTP업무호출; card._actions_for는같은action code중첫Skill의SOP를대표로쓴다. 실제업무오류시인스턴스는A008덕분에막히지만Incident는이미닫힐수있다. 작업지시만고른경로에서는Incident가AWAITING_APPROVAL에남는지도후속재현대상이다(아직그경로의실제재현은안함).

후속우선순위: 승인한후속정비입력과원천SOP를명확히보존하고, 실제CMMS성공ref를Incident/태스크/감사에일치시킨다. 실패·응답유실·SQL/SQLite실패·재시작·작업지시만선택·레거시경로를같이검증한다. 가이드의다른대안SOP나새정비조치를사람승인없이임의선택해일치시키지않는다. A028은아직구현변경전이다. A027번호는오래된승인/미지원경보검사후속을위해남겨두며검증완료로표시하지않는다.

### A028 수정/검증 (2026-10-04 09:25)

구현과 실패증거를 [WORK_ORDER_RECOVERY.md](WORK_ORDER_RECOVERY.md)에 연결했다. 신규7실패에서 출발해 실제요청/영수증/종결경계와 승인옵션 actions 유실, claim뒤 service표식 전 강제종료 회수를 수정했다. 전체382passed, 실제Pg/SQLite/HTTP6/6(PLC/graph대역), 실제20×legacy bridge 인스턴스40/40, 직접legacy48/48 exit0다. 실제CMMS ref/접수뒤종결과8경쟁자HTTP1회까지 검사했다. 교재13장1280/390 정적렌더·JS문법통과이며 포털클릭검수는 아니다. 새Codex 시작명령은 자동 승인 심사 blocked by policy로 거절돼 미실행, 우회하지 않고 instance/20×/legacy·설비3RUN·PowerShellworker0·개인config불변으로 복구했다. A026 원문 연결, A027 현재조건, 일반outbox/claim지연/전체강의검수는 여전히 미완료다.

08:40 추가실측: `scripts/probe_work_order_consistency.py`를위인스턴스에실행해2/4 exit1(`a028-closure-first.json/log`). 실제CMMS일치영수증과태스크완료시간은통과, Incident참조와종결순서는실패다. 읽기전용검사이며임의수정/새업무발행없음. 이실패를수정후검사와대조한다.


## A026 원문/검토/원자적 그래프 연결 (2026-10-04 09:56)

기존부분저장API를manual_api/review/graph로교체했다. 원문좌표전체검증→명시사람검토→한Neo4j거래적재, 문서/판본별출처, 문서소유전체before/after, 기대head개정, 최신순되돌리기, 외부규칙/실행/속성충돌거절을연결했다. 실제Neo4j/SQLite17/17(629F7E5CBE), 배포HTTP21/21(0A07CC4CEC, process실제재시작포함), 기존매뉴얼시나리오7/7, 형식거절3/3,105단계preview/commit/실제조회/rollback4/4다. 전체403passed/기존경고2후 3자리단계파서개선은관련40검사통과. 실패harness(summary없음,지원안하는개별조회405)는성공기록으로대체하지않고보존했다.

원본/전체페이지/보관목록/재검토/개정/되돌리기UI와교재13장추가절을반영했다. JS문법/교재구조0/1280·390정적렌더직접검토범위이며포털직접클릭은미검증이다. 실제Codex 일반문서추출/표·OCR정확성/참조중SOP병행판본은남아있다. A028뒤worker시작정책거절을우회하지않고독립범위만수행했다. 상세계약/증거파일은MANUAL_INGESTION. 원문과배치기록은보존하며시험그래프는정상rollback했다.


### A029 — 레거시 에이전트의 일시적 빈 claim 뒤 정지 (10:25)
A027 실제 시험 중 저장된 판단이 있음에도 네 번째 rank가 IN_PROGRESS로 멈췄다. 브리지 단발 호출의 빈 claim 반환 뒤 재시도 부재다. poll에서 Incident 소유 인스턴스·저장된 원래 판단·전체 task_started job 출처를 확인해 pending 단계만 재개한다. Codex가 수행한 작업은 legacy로 인수하지 않는다. 신규2반례 실패→관련10통과, 배포 후 기존 인스턴스 rank DONE/select IN_PROGRESS와 시작4개를 실제 확인했다. 근거 a027-stale-first/, a029-unit-final.xml, a029-recovered-instance.json. 일반 모든 워커 임대/claim 복구 완료를 뜻하지 않는다.

### A027 — 오래된 판단의 승인 전 현재조건 누락 (10:25, 진행 중)
실제 판단 생성 후 REMOTE_MANUAL로 바꿔 기존 fan-max-derate를 선택했다. HTTP 성공·명령 ID 생성·선택 소비까지 진행하여 기대한 사전 거부 3개 모두 실패(exit1). a027-stale-second/report.json과 원시 응답·설비·게이트웨이·감사 보존. 실제 PLC의 거절은 이 결함을 없애지 않는다. 현재 규칙/역할/센서 신선도/업무 입력을 다시 읽는도우미16검사, 초기연결관련26검사는 통과했으나 배포·실제재검증은 미완료다. 미지원 경보의 cooler 회복기준 기본값도 아직 남아 있다.


### A027 후속 — 현재 승인 경계 연결/실행 (10:49)
[CURRENT_APPROVAL](CURRENT_APPROVAL.md)에 상세계약/미완료를정리했다. 전체431passed, 배포모드변경5/5, 실제legacy bridge 인스턴스40/40, 실제원천변경7/7이다. 새Codex 미실행. 첫정상39/40·첫원천exit1을삭제하거나성공으로바꾸지않았다. 현재조건검사는선택접수/전달/명령직전이며source오류는통과값으로대체하지않는다. WARN미확인은공개경고로유지하고EXCLUDE/PENALTY미확인은보류한다. 신규경고/카드내용/업무판단조건변경은새검토대상이다. 교재13 current-approval-contract 구조0·1280/390직접렌더확인. 포털클릭/실제모델이전일반재작업은미완료.

### A030 — 펌프의 필수 예측 누락과 정적 예측 적용 범위 (발견 당시; 후속 연결은 아래)
실제CMMS readiness=true여도 pump판단이 NO_FEASIBLE_OPTION이다. 원본그래프 it/neo4j/v2/instances.cypher549~550은PS1설계예측만정의하지만rule:ts1-hard는모든후보의forecast_ts1을검사한다. 예전에는unknown규칙을발동하지않아통과했으나현재는미확인실행을보류한다. `a027-live-sources.log`가최초반례, `a027-live-sources-fixed/pump-ready.json`가현재원시조건/미확인규칙이다. 확인된경계를검사한7/7은펌프실행성공을뜻하지않는다. 실제상태·고장조합·사용자조치값을입력으로받고유효범위를표시하는예측계약이필요하다. 쿨러정상40/40을다른시나리오정상으로확대하지않는다.


### A030 독립 모델과 실제 조회 도구 (11:08, 카드/승인 연결 전)
FORECAST_MODEL.md 참조. HYD thermal/plc/plant 실제식과일반입력계약을대조해패턴/SOP분기없는counterfactual을만들었다. 모델전용상태/주변온도/동일시점온도/열화진행을명시하고입력누락/도메인/뜨거운RESET/미지원명령을거절한다. 24조합시뮬레이터적분비교를포함한관련56검사, 전체471검사, 실제3설비16/16·배포HTTP/MCP8/8을확인했다. 읽기호출에서설비명령/판단제출은없다. 시뮬레이터내부상태를실제공장직접측정값으로설명하지않는다. 현재결정카드의정적Forecast와연결은미완료이며기존펌프보류가해소된증거가아니다. 조치값변경후예측검토·모델판본·현재승인검사를함께연결해야한다.


### A030 카드/승인 모델 연결과 실제세설비 (11:43)
FORECAST_MODEL.md 참조. Asset 모델ID/판본/적용범위/시간을 명시하고 하나의 원천 스냅샷으로 후보별 조치를 계산한다. 카드/평가/제출/현재승인검사가 동일제공자를 사용한다. 평형DMN값과900초뒤/구간최대 예측을분리하고 예상인터록·원천실패·모델불일치면 제외한다. 모든 조치/입력/계수/버전/시각/가정을보존하고 관련정책SHA 변경도재검토한다. 실submit은가정facts덮어쓰기를거부하고선택·전달·명령경계는검토카드와명령일치를검사한다.

전체491passed(기존경고2), HTTP/MCP/Neo4j9/9, 실제업무원천7/7, bound예측도구8/8. 실제legacy bridge쿨러40/40(a030-card-instance.log, WO-1004-BB6C), 펌프13/13(a030-pump-final/, WO-1004-56AE), 팬12/12(a030-fan-instance/)로PLC/재관측/종결을확인했다. 펌프는CMMS준비=true를명시적으로설정하고원값복원한시험이며원천미확인을준비됨으로추측하지않는다.

첫펌프6/8 실패는열화가끝났는데상태10초heartbeat에종료가늦게반영되는생산자결함이었다. 시작/종료즉시상태발행으로수정했다. 그뒤12/13은물리경로가종결했지만ACK직후압력값갱신을가정한검사기결함이며실제수집을15초한도관찰하도록수정했다. 두실패원본과실제상태는보존했다. 변경값의새카드미리보기·재작업·미지원경보·새Codex검증은미완료이고세기본시나리오통과로전체Goal완료라하지않는다.


A030 11:51 추가증거: mask14/14는경보해제에도압력157.17bar미회복을실패로에스컬레이션했다(a030-mask-instance). 변경값/모드8/8(a030-stale-actions-final). 최초6/7(a030-stale-actions)은자동모드복원사이에유온2.52℃상승했는데도기존동의가자동복원돼야한다는검사기가정실패다. 새모델의악화거부를유지하고현재원천의새읽기판단/평가를추가했다. 일반재작업으로새판단을기존할일에교체·승인했다는증거는아니다. 현재상태/원문승인/CMMS/파일SHA는a030-card-runtime-final, a030-card-executions, a030-card-files에보존했다.


### A031 변경 조치 검토와 명시 승인 (12:48)

DECISION_REVIEWS.md와 DECISIONS38 참조. 기존 SOP는 보존하고 팬/부하 변경값을 현재 모델/원천/규칙으로 다시 계산한다. 검토본 UUID/원본SHA/소유범위를 SQLite에 불변 저장한 뒤, 명시한 사람 승인을 기존 PG 승인/outbox에 같은 스냅샷으로 넣는다. 선택/전달/명령은 현재조건과 정확값을 계속 확인한다. 작업 기한도 원천조회 뒤 다시 검사한다. 원래 카드에 없던 SOP/새 원인 진단을 이 기능으로 끼워 넣지 않는다.

전체505passed(경고3), legacy 우회차단에 preview API를 추가한 관련20검사, 실제5배속24/24(95/78 적용·CMMS WO-1004-19B2·ev:closed), 검토저장뒤실제SIGKILL/start28/28(동일검토승인·WO-1004-400F·종결). 다른값94,낮은역할,facts override,현재수동모드,완료된작업의재사용을거부했다. 70/90은평형65.182℃로제외됐다. 실제포털클릭/새Codex 증거가 아니다. 순수JS컴포넌트10검사와교재13의3절1280/390정적렌더6개를별도로확인했다.

첫20배속실행은모델키검사오기와클라이언트20초timeout/사람30초기한초과로exit1이다. 서버감사는수동모드/예측악화거절을남겼다. 원본a031-review-instance와timing로그를보존하고정책을완화하지않았다. Windows기존psycopg DLL앱제어차단,첫Linux검사httpx누락,legacy재생성직후준비전연결종료도원본을보존했다. legacy변경안완주는별도진행중이다.

원본completion b272c9a의compensation_handler/compensation 두전체본문을읽고파일SHA/열람범위/수정없음을a031-reference-review에보존했다. workitem별효과와역순보상판정을참고하며일반재작업은다음단계다. 원본의자동파일삭제/SQL역변환을물리조치보상으로그대로쓰지않는다.


A031 12:52 추가: legacy HITL17/17 exit0(a031-legacy-review-ready, 실제CMMS WO-1004-70CE)까지확인했다. 12:51 instance/20×/legacy 복원·3RUN/REMOTE_AUTO/열화0·PowerShell worker0·개인config SHA불변(a031-runtime-final). 첫실패두건만원본보존뒤관리자확인으로ev:escalated 종료(a031-fixture-cleanup). 현재선택작업의새검토범위완료이며일반완료작업재실행/새Codex/포털직접검수는완료가아니다.


### A032 미지원 경보·원천 보존·정의별 회복·그래프

ALERT_ROUTING 및 DECISIONS39 참조. 모든 PLC 트립을 과열로 표시하고 미지원 경보에도 TS1 기준을 쓰던 결함을 수정했다. anomaly_response2.1에 세 기준과 alert_triage1.0 경로를 선언하고 생성 당시 기준/원문을 저장한다. 사람 검토·CLEAR를 명령 승인/정상 회복으로 바꾸지 않는다. 늦은 가이드·결정도 원문/경로를 승격할 수 없다.

동시 실제 경보가 snapshot 직렬화 오류를 드러냈다. 두 스레드 재현1failed 후 Store 저장 순서와 목록 멤버십을 수정하고 전체528passed를 확인했다. 실제45/45 뒤 별도 그래프 조회에서 Process/Incident 연결 누락을 추가 발견해 seed/사건 원문 투영/누락 경고를 보강했다(관련50passed). 기존 네 사건의 실제 원문/PG 이력으로 그래프 복구·재조회 후 새 실제 Kafka/PLC/재시작/사람 검토/그래프49/49 exit0를 확인했다.

정상 쿨러는5배속42/42 exit0(CMD-1004-0001-958b, 실제CMMS WO-1004-B2B5, ev:closed)이며 legacy bridge 경로다. 20배속의 기존 카드 및 새 검토본 실패는 현재 예측 악화에 따른 거부로 보존하고 보호 기준을 완화하지 않았다. 실패 승인 한 건은 폐기/재검토 구현의 실제 미결 사례다. 펌프·팬·mask 회귀는 진행 중. 새 Codex/포털 클릭은 아직 미검증, 전체 원천 이벤트 inbox·그래프 outbox·일반 재작업은 미구현이다.

A032 추가: 20배속 정상 펌프/팬 및 mask37/37 exit0(a032-pump-fan). 펌프 CMMS WO-1004-34FD, mask의 실제PS1=156.99미회복은MITIGATION_FAILED/ev:escalated이며작업지시는취소됐다. standby_ready시험값은NULL복원확인. 새Codex는승인환경변경후재검증준비중으로아직성공증거가없다.


### A033 — 원천 접수·처리·담당자 조회와 장애 복구 (부분 검증)

A034 실제 Codex 경로는 **42/42, exit 0**이다. 네 작업 321초, MCP 시작/종료 25쌍, 명시 오류 0을 확인했고 사람 승인→PLC ACK→재관측→CMMS→종결/그래프까지 이어졌다. 원본 실패 A032 26/27은 별도 보존했다. 워커 종료 PowerShell 0과 개인 config 해시 불변도 확인했다(a034-codex/, a034-worker-stop.json).

A033은 public migration00007과 수신/처리/API를 배포했다. 전체563검사, 실제PG/SQLite+ASGI12/12, 실제Kafka·process 강제종료/재시작22/22(a033-kafka-recovery-retry/)를 확인했다. 접수 직후·claim 중·Incident만 저장된 경계를 검사했고, 중복/충돌/지연 CLEAR와 동일 사건 재연결을 확인했다. 첫 검사기의 상세조회 오류는 a033-kafka-recovery/에 보존한다.

배포 후 펌프·팬·경보 가림은20배속 legacy bridge에서 **37/37**이다(a033-pump-fan/checks.json, stdout.log). PowerShell에서 검사 프로세스와 워커가 남아 있지 않음을 확인했다. CMMS standby_ready는 원래 NULL로 복원됐다. Codex를 쓴 A034 경로와 새 A033 수신기를 쓴 이 회귀는 서로 다른 실행 증거다.

쿨러는5배속/instance/legacy에서 **42/42, exit0**(a033-cooler/)이다. 승인DELIVERED1회→CMD-1004-0001-2be1/ACK→재관측181초→CMMS WO-1004-F54F→ev:closed/그래프를 확인했다. 추가로 PG 인스턴스 저장 후 접수완료 쓰기를 막고 실제process를kill/start한 **10/10**(a033-kafka-after-instance/)도 통과했다. 같은 접수·사건·인스턴스로 복구됐고 추가PLC명령은없었다.

포털은 agent-browser 실제클릭으로 충돌3건 조회, FAILED의 담당자/이유 필수입력, 같은접수503/562재시도→HANDLED, 원문/정의/hash유지와실제triage생성을 확인했다(a033-source-ui/). 이 UI 시험의 실패는 명시 주입이며 실제DB장애가 아니다. 재시도후목록에옛실패표시가남는결함을수정하고 선택접수새로고침·모바일입력배치를 재검증했다. 390폭가로넘침없음/1280상세화면을직접봤다. 시험사건두건은원문보존후사람검토API로종결, PLC명령0. 브라우저종료확인. 세션중 errors 명령의 빈 오류 출력은 원인확인되지않았으므로 브라우저콘솔오류0이라고 주장하지않는다.

교재 정본은 D:/work/study/시스템교재/13_확장_ProcessGPT.html이다(docs/src/master_body.html 아님). source-receipt-contract 절에 접수/업무/회복구분·상태표·화면재시도·장애실험판단을추가했다. 구조검사0문제, 변경절1280/390렌더 직접확인/넘침없음(a033-book-check,book-render/a033-*). 전체교재직접검수나학생리허설완료가아니다.

최종runtime20배속/instance/legacy·health ok, PowerShell 워커/시나리오/복구검사프로세스0(a033-runtime-after-ui.json,a033-process-stop-check.json). 소스수정은문법검사와실제브라우저로검증했다. git diff --check는 기존 tests/test_guardrail.py:114, test_stability.py:157의 EOF빈줄을보고한다. 이번영향파일외기존WIP는고치지않았다.

남은 A033 경계: ACK/CLEAR 처리 중 hard kill, Kafka 접수 전 DB 실패, 새 수신기에서 실제 Codex 완주. 전체 강의 검수·일반 재작업·일반문서 AI 추출·전체 그래프 outbox 등 전체 Goal 미결은 계속 유지한다. 최신 권한은 danger-full-access/never이며 사용자 부재 중 일반 명령 승인을 요청하지 않는다. 새 결제·push·개인 설정 기존내용 변경은 별도 계약이다.

### A034 — 실제 Codex 가이드 저장과 태스크 완료 순서

A032 새실행9c8ee1ba…는26/27 exit1: 4작업/MCP21쌍 뒤 가이드가 Incident에 저장되지 않아 FAN_SET 승인 거절. 명령/승인0, 증거a032-codex-durable/. 원인은 부분 경보 ID 거절과 post-commit 실패 은폐다. 새검사4실패 재현→수정후영향77passed→전체549passed/경고3→실제Pg/SQLite7/7. GUIDE_COMMIT.md에 계약/범위를 남겼다. 배포 후 실제Codex a034-codex42/42 exit0, 네작업/MCP25쌍과 승인/PLC/재관측/CMMS/종결을 확인했다. A033의 이후 수신기 변경은 별도 검증한다.

### A033 저장 실패와 CLEAR·ACK 완료 경계 — 실제 검증

`probe_source_persistence_failure.py` 재검사 **10/10**: 시험 경보 한 건에만 PG INSERT 예외를 주입했다. 원문이 저장되지 않은 동안 실제 Kafka process 그룹의 committed offset이 경보를 넘어가지 않았고, 오류 제거 뒤 동일 좌표·원문으로 처리됐다. health에도 실패/회복이 나타났다. CLEAR 반영 후 접수 완료 SQL이 대기 중임을 확인하고 process SIGKILL과 해당 DB 연결 종료를 수행했다. 원래 접수가 2시도로 이어졌고 사건은 ESCALATED를 유지했다. 증거 `a033-persistence-failure-retry/`. 이것은 DB 전체 접속 장애가 아닌 범위를 한정한 실제 쓰기 오류다.

첫 `a033-persistence-failure/`는 7통과 뒤 2시도를 기대한 검사 1개가 실패했다. 앱을 죽인 뒤에도 DB가 이미 받은 완료 쓰기를 끝내 1시도 HANDLED가 됐다. 원본 실패/관측값은 보존했고 시험 사건은 명시 검토로 종료했다. 앱 종료가 DB 거래 중단과 같다는 가정을 폐기했다. 재검사는 대기 중인 정확한 완료 SQL/backend를 기록하고 그 연결까지 종료한 범위를 명시한다.

`probe_source_ack_recovery.py` **9/9** 및 설정 단계4/4: 실제 HYD-03 팬 결함→legacy 에이전트→사람 승인→팬40/부하80→PLC ACK 뒤 같은 완료 경계를 끊었다. 재시작 후 같은 ACK/명령 ID를 재처리했고 PROCESS_RESTART_REVIEW를 유지했다. Kafka action.cmd에서 CMD-1004-0001-28bd는 partition0/offset43의 **1회 발행**으로 확인했다. 사람 검토→ev:escalated, CMMS 가지 CANCELLED. instance39edd9a3…, Incident INC-1004-01-32e7. `a033-ack-recovery/`에 실제 command 메시지·접수·사건·결과를 보존했다. Codex를 쓴 검사는 아니다.

범위를 한정한 DB trigger/function은 모두 제거됐고, `a033-worker-preflight.json`에서 잔여 시험 함수0/기존 워커 대상 작업0을 확인했다. 첫 실패 원문을 성공으로 덮지 않는다. 이 단계는 수신 완료 거래의 재시도를 검증하며 Kafka의 모든 장애 유형이나 모든 외부 효과의 원자성을 증명하지 않는다.

### 최신 Codex 경로 — 실행 도구 차단으로 미실행

2배속/off로 바꾸고 Codex 워커 PID1916은 실제 기동됐다. 그러나 상태조회와 `run_scenario_evidence.py --worker --fresh-review --out .evidence/reaudit/a033-codex` 시작을 포함한 명령이 실행 도구의 `blocked by policy`로 거절됐다. 구체적인 사유는 제공되지 않았다. 현재 danger-full-access/never여도 이 거절이 발생했으며 사용자 승인 요청이나 우회 실행을 하지 않았다. `a033-codex` 결과 폴더도 생성되지 않았다. A03442/42를 새 A033 Codex 성공으로 재사용하지 않는다.

켜진 워커1916과 확인된 자식23512/21896을 종료했고 PowerShell로 remainingWorkers0/remainingTree0을 확인했다(`a033-worker-stop.json`). 개인 config SHA는836330D5…불변. process/plant/detector를20배속/instance/legacy로 복원했다. 다음은 독립적인 DB 접속 실패 검사 준비, 남은 일반 재작업/문서 추출/강의 요구 대조다. 같은 차단된 Codex 시작 명령은 정책 변화나 허용 확인 없이 반복하지 않는다. 전체 Goal은 active이며 이 차단 하나가 독립 작업 전체를 막지는 않는다.

### A033 DB 연결 중단과 여러 설비의 접수 복구 — 15/15

`probe_source_connection_failure.py`를 실제 실행했다. process에만 시험 전용 TCP 중계기 DSN을 적용하고 중계기를 중지했다. 공유 PostgreSQL/Kafka는 계속 가동했다. handler에서 실제 Connection refused, receiver에서 DNS 접속 오류가 관측됐고 health ok=false였다. 세 설비의 서로 다른 경보와 동일 경보 중복 한 건이 Kafka에 발행됐으나 접수/사건은 생기지 않았으며, 두 시점의 process 그룹 committed offset은 네 원문을 넘어가지 않았다.

중계기를 다시 켜자 **process 컨테이너 재시작 없이** 세 원문 HANDLED/세 고유 인스턴스와 중복 한 건 DUPLICATE로 처리됐다. 네 Kafka 좌표가 보존된 뒤 offset이 전진했다. 세 사건은 원래 미지원 경보의 사람검토 경로로 갔으며 PLC 명령은 없었다. 명시 검토 결과까지 저장했다. 총15/15 exit0. 증거 `.evidence/reaudit/a033-connection-failure/`의 result/health-outage/offsets-outage/recovered-receipts/offsets-recovered 및 설비별 instance 원문이다.

finally에서 process의 원래 환경변수 전체가 같음을 확인하고 20배속/instance/legacy·health ok로 복원했다. 시험 label을 대조한 중계기는 제거했고 잔여0이다. PowerShell 워커/시나리오/검사 프로세스0와 개인 config SHA 불변은 `a033-connection-process-check.json`에 기록했다. 공유 DB 서버 자체의 장애·모든 네트워크 분할 유형·새 Codex 실행을 증명하지 않는다. 최신 A033 Codex 시작은 기존 정책 차단으로 계속 미검증이다.

다음은 CURRENT_APPROVAL의 완료 태스크 재작업 및 실패 승인 폐기/새 판단 경로를 ProcessGPT 원본과 대조해 설계·구현하는 것이다. 원천 접수 장애 검사만으로 전체 Goal을 완료하지 않는다.

### A035 — 새 판단 재작업·실패 승인 폐기 (현재 상태 확인, 구현 전)

실제 API/PG를 재조회했다. d6a2392c… 인스턴스는 RUNNING, 승인6e50dcef…는 FAILED/1시도이지만 Incident INC-1004-07-b30f는 RESOLVED_WITHOUT_ACTION/cmdId 없음이다. OpenAPI에는 동일 승인 재시도만 있고 일반 rework/discard가 없다. 현재 상태는 `a035-rework-baseline/`에 보존했다. cmdId 없음만으로 기업 효과까지 없다고 판정하지 않는다.

completion b272c9a의 process_engine.py791~1040을 재대조해 새 UUID/rework_count/원본 보존 구조를 확인했다. HEAD·clean working tree·SHA·발췌본을 같은 증거 폴더에 기록했다. HYD는 변수 시작 원문/출력 소유권·명시 세대·실패 승인 폐기·실제 효과 확인 계약이 추가로 필요하다. [REWORK.md](REWORK.md)에 구현 순서와 실제 수용 기준을 작성했다. 설계 문서이며 아직 A035 코드 변경/완주 증거가 아니다. 종료된 사건의 명시 정리와 활성 사건의 새 판단 경로를 각각 구현한다.

### A035 실패 승인 폐기 — 실제 연결·검증, 일반 재작업은 미완료

승인 snapshot/error/history를 보존한 `DISCARDED`와 성공 완료와 구분되는 인스턴스 `CANCELLED`를 migration00008에 추가했다. 폐기 미리보기/실행은 동일 인스턴스 잠금에서 tenant·원래 승인 역할·FAILED/SUBMITTED·다른 승인/서비스 상태를 확인한다. 종료 사건이라도 명령/작업지시/기업 실행 또는 불명확한 기록이 있으면 거절한다. 요청자/역할/사유/요청 ID/효과 조회를 이력과 PG 이벤트로 함께 저장한다. 같은 요청은 같은 결과, 다른 요청은 충돌이며 폐기 후 재전달은 불가하다. 이전 DONE 작업과 원래 Incident/decision은 덮지 않는다. 이 로컬 역할 입력을 운영 신원 인증 구현으로 설명하지 않는다.

효과 조회에 최근300건 거래 목록을 쓰면 오래된 거래를 놓칠 수 있어 enterprise API에 결정 ID별 전체 원장 조회를 연결했다. PG는 decision_id 조건을 쓰고 목록 한도를 적용하지 않으며, 메모리 backend는 영속 멱등 원장을 읽는다. 조회 오류/잘못된 응답은 빈 결과로 바꾸지 않는다. 실제 기존 효과를 보상하는 기능은 아직 추가하지 않았고 해당 사례는 명시 보류한다.

신규검사 최초10실패→관련42passed→전체580passed/경고2. `a035-discard-red/unit/full` 로그/XML. 실제 PG/SQLite/기업HTTP **9/9**에서 마지막 쓰기 실패 rollback, 네 dispatcher 동시 요청 한 번 반영, 저장소 재개/멱등 응답과 명령0을 확인했다(`a035-discard-pg/`). 이 별도 tenant의 종료 사건/PLC/그래프는 명시 시험 대역이며 실제 HYD 실행으로 확대하지 않는다. fixture tenant와 원문은 보존했다.

가동 enterprise/process를 배포하고 과거 실제 실패 인스턴스 d6a2392c…를 포털에서 선택했다. 담당자/역할/사유 누락 안내→생산관리자 조회→기업 원장0건/종료 사건/남은5작업 확인→명시 폐기를 실제 클릭했다. 사전API **4/4**, 사후API **8/8**: 원래 승인·오류·Incident 원문 불변, CANCELLED/DISCARDED, 남은 작업 종료, 같은 요청 replay, 재전달409, 폐기 이벤트1건, Neo4j 취소/작업 상태 일치. `a035-discard-live/`에 전후와 실제 화면을 보존했다. 그래프에는 기존 사건 원천 누락 경고 `incident source not projected: INC-1004-07-b30f`가 남아 있어 전체 그래프 정합 완료는 아니다.

포털 폐기 상태의 실제 데스크톱/390 화면을 직접 확인했고 390 가로 넘침은 false였다. 앞 element 캡처는 고정 헤더에 일부 가려져 viewport 캡처 screenshot-1791101939468/9811을 최종 화면 근거로 쓴다. 브라우저 종료 확인. 교재13 `approval-discard-contract`에 필요성·원장 전체 조회·담당자 판단·동작과 재작업의 구분을 반영했다. 구조0문제, 변경절1280/390 렌더 직접확인/넘침없음(`a035-book-check`, `book-render/a035-*`). 전체 학생 리허설은 아니다.

process 실제 restart 뒤에도 CANCELLED/DISCARDED가 유지됐고 health ok,20배속/instance/legacy,PowerShell 워커/검사 프로세스0,개인 config SHA 불변이다(`a035-restart-final.json`). 최초 build 명령은 PowerShell stderr 취급으로 NativeCommandError/종료1이었지만 로그에는 두 이미지 Built가 있었고 그 이미지의 실제 recreate/API/재시작으로 배포를 확인했다. 실패 출력은 지우지 않았다.

다음은 REWORK 계약의 활성 사건/새 일반 정의에서 새 작업 UUID·세대·시작 입력/출력 출처·변경 원천 조회·새 판단/승인으로 이어가는 구현이다. 이번 명시 취소 기능을 일반 재작업 완료로 축소하지 않는다. 새 A033 이후 Codex 전체 실행은 기존 도구 정책 차단으로 미검증이며 우회 시도하지 않았다. 일반 문서 AI 추출·전체 그래프 outbox·전체 강의 검수도 남는다.

### A036 시작 입력 보존과 변수 생산 작업 — 실제 기반 연결

재작업에서 누적 결과를 최초 입력으로 오인하지 않도록 `initial_variables`와 `variable_sources`를 연결했다. engine.new_instance가 전달받은 시작 입력을 깊은 복사로 보존한다. 업무 결과가 변수를 만들면 실제 workitem UUID/활동/정의 판본을 출처로 저장하고, 별도 서버 갱신은 runtime으로 구분한다. migration00009의 DB trigger와 MemoryRepo는 저장된 시작 입력의 교체/제거를 거절한다. 기존 인스턴스는 NULL로 남기며 누적 결과로 시작 입력을 추측하지 않는다. 이는 현재 값의 마지막 기록 출처이며 모든 외부 사실의 진실성/전체 변수 변경 이력까지 증명하지 않는다.

신규4검사 red 재현→관련51passed→전체584passed/경고2. 최초 red 중 World.items 검사기 오타를 World.rows로 수정한 뒤 기능4실패를 다시 확인했고 두 원본을 보존했다. 이미지 build/deploy는 subprocess에서 종료0을 확인했다. 실제 새 비HYD 정의를 HTTP로 등록/시작/제출한 **8/8**에서 입력score2→업무결과7→accepted, 시작2 보존, 생산 작업9d47b2bd… 연결, 실제PG 입력 변조/제거 거절, 기존 사건 입력NULL을 확인했다. 증거 `a036-provenance-live/`, `a036-provenance-unit/full`, `a036-migration.json`이다. 인스턴스 `provenance_a463e4c7a1.92497170-0dee-42ba-b072-a159463c50ce`를 보존했다. Codex/PLC를 수행한 검사는 아니다.

포털에 시작 입력 펼쳐보기와 현재 변수의 출처를 연결했다. 실제 클릭으로 score2/현재7/작업ID를 확인하고1280·390 화면을 직접 봤다.390 가로 넘침false. 최종 화면 screenshot-1791102680901/1791102664456이며 이전 인스턴스의 원문 없음 안내는 old-input-panel.txt로 기록했다. 브라우저 종료 확인. `docs/definition-authoring.md`도 같은 계약으로 갱신했다. 전체 교재/학생 리허설 검증을 뜻하지 않는다.

현재20배속/instance/legacy·health ok,PowerShell 워커/검사 프로세스0/개인 config 불변(`a036-runtime-final.json`). 이번 단계는 일반 재작업의 입력 기반이며 재작업 요청 API/새 작업 세대/재진단/새 승인까지 구현한 것은 아니다. 다음은 고정 정의의 흐름·input/output 의존성으로 영향 범위를 계산하고, 이 snapshot/생산 작업 ID에 근거해 재사용·무효화할 변수를 결정하는 계획기와 원자적 재작업 접수/세대 전이를 연결한다. 이전 입력이 없는 인스턴스에는 임의 seed를 채우지 않는다. A035 실패승인 폐기와 효과 확인 계약을 재사용하되 활성 사건을 CANCELLED로 끝내는 것으로 재작업을 대체하지 않는다.

### A037 재작업 영향 계산 — 실제 HTTP/PG 미리보기 검증

`procsvc/rework.py`와 `GET /api/instances/{id}/rework-preview?workitem_id=...`를 연결했다. 서버는 고정 정의의 모든 후행 가지, input/output 의존성, 분기 조건의 변수, boundary timer와 실제 reference_ids를 닫힌 범위가 될 때까지 추적한다. HYD 활동 이름을 고정하지 않는다. 같은 인스턴스 잠금에서 정의·작업·변수·승인을 읽고 상태를 바꾸지 않는다. 시작 snapshot과 비영향 DONE 생산자의 실제 UUID/판본/출력값을 대조해 재사용 후보를 만들며, 무효 출력과 같은 이름의 시작 입력이 있으면 그 원문을 복원 후보로 표시한다. 출처 불명·옛 입력 NULL·종료 인스턴스·동시각 최신 행 모호·기존 승인·시작된 서비스는 사유로 남는다. `snapshot_token`은 로컬 계획 근거의 해시이며 외부 효과가 없다는 증명이나 승인 토큰이 아니다.

ProcessGPT completion의 새 UUID·입출력 참조 코드(고정 HEAD b272c9ab…/process_engine.py818~927)를 다시 읽었다. 원문 열람을 원본 서비스 실행으로 쓰지 않는다. HYD의 `rework_count`는 `retry_work_order`에서 동일 CMMS 요청 재전달에도 증가하므로 새 세대 순서로 사용하지 않았다. 새 세대 식별자/접수 receipt/옛 작업 fencing은 다음 구현이며 현재 미리보기는 `execution_available=false`다. 권한 승인, 실제 효과 조회·보상, 새 Codex 실행, UI 버튼은 이 단계에서 수행하지 않았다.

신규16passed→전체600passed/기존 경고2(`a037-planner-unit/full.log/xml`). 전이 의존성, 분기조건만 참조하는 변수, 정의 밖 실제 reference, 잘못된 생산자/판본/값/상태, tenant/인스턴스 혼입, 타이머, 승인/서비스 기록, 같은 시각 행과 읽기 전후 불변을 검사했다. build/deploy 모두 종료0(`a037-build/deploy.log`). 실제 HTTP/PG **10/10 exit0**(`a037-planner-live/`)에서 새2단계 일반 정의를 등록하고 score2→사람 결과7→다음 작업의 입력을 확인했다. 미리보기는 원래2/무효화7/취소 대상인 현재 후행 작업을 구분하고 이전 DONE 결과·이벤트·변수를 변경하지 않았다. 외부 작업 ID는409, 기존 취소 사건은 원문없음/종료 상태를 유지했다. 일반 진행으로 score8을 제출해 accepted/COMPLETED로 끝냈으며 시험용 인스턴스 `rework_plan_b8b09342f5.3a79f1f1-884f-4b2c-9350-63ede5e960c5`와 원문을 보존했다. 새 세대 재실행 증거는 아니다.

최종20배속/instance/legacy,healthz ok/PG·Kafka 연결,PowerShell 워커/검사 프로세스0,개인config SHA 불변(`a037-runtime-final.json`). 최초 상태 확인 명령은 잘못된 `/health`로404였고 실제 계약 `/healthz`로 재확인했다. 서비스 장애나 기능검사 실패로 해석하지 않는다.

다음: 재작업 receipt와 명시 generation을 저장하고 동일 인스턴스 거래에서 관측 token/작업 ID를 재검사한다. 완료된 옛 행/출력은 보존하고 살아 있는 영향 작업·타이머는 fence하며 새 UUID와 유효 선행 참조를 연결한다. 기존 승인/runtime 변수는 원래 효과·권한 계약을 다시 확인한 뒤 폐기/새 판단에 연결해야 한다. 활성 사건의 실제 Codex/MCP→새 결정→새 사람 승인까지 미완료이며 이전 도구 정책 거부 경로는 우회하지 않았다. 일반문서 AI 추출·전체 그래프 outbox·전체 강의/학생 리허설도 계속 남는다.

### A038 일반 정의의 새 작업 세대 — 실제 PG/HTTP/그래프 검증

migration00010은 인스턴스의 rework_generation/현재 요청 UUID, 작업의 generation/rework_request_id/supersedes_id, 불변 process_rework_receipt를 추가했다. 요청 UUID·미리보기 token·담당자/정의의 사람 역할/사유를 확인하고 같은 인스턴스 거래에서 재검사한다. 완료된 옛 행·출력은 보존하며 영향받는 live/TODO 행·타이머는 CANCELLED로 남기고 새 UUID와 세대를 만든다. 새 입력·query·선행 참조를 재구성하고 옛 claim/제출은 취소 상태로 차단한다. 세대 식별 정보와 요청 원문은 DB trigger로 변경을 거절한다. 같은 요청 재전달은 같은 접수 결과, 다른 내용 재사용/관측 후 상태변화는409, 정의 밖 역할은403이다. 역할 문자열 검사는 운영 신원 인증을 의미하지 않는다.

중간 작업이 같은 변수 이름을 덮어쓰는 반례도 처리했다. seed2→측정7→검토9에서 검토를 다시 하면 유효 선행 결과7을 복원한다. seed2를 항상 쓰거나 현재9를 재사용하면 잘못된다. 여러 선행 생산자가 순서상 비교되지 않으면 추측하지 않고 명시 검토로 남긴다. engine/rework planner/timeline/포털 단계는 generation 우선이며 rework_count는 기존 CMMS 동일요청 재전달 횟수와 혼동하지 않는다. 새 타이머도 요청과 세대를 이어받는다. Execution 투영은 모든 작업 UUID의 세대/이전작업/요청 ID를 보존한다.

관련24passed→전체608passed/기존경고2, 최종 그래프·타이머 보강 후 전체608 재확인(`a038-generation-first/full/final.log/xml`). migration00010 적용 및 process build/deploy 종료0(`a038-migration`, `a038-build/deploy.log`). 원문/기존 인스턴스는 삭제하지 않았다.

실제PG **10/10 exit0**(`a038-generation-pg/`): 자식 프로세스가 마지막 쓰기 후 commit 전에 os._exit(73)하면 작업/receipt/event 전체 rollback, commit 직후 os._exit(74)하면 새runtime에서 같은 결과 재개. 네 PG runtime의 replay가 한 receipt/이벤트를 반환했고 실제 old-worker RPC 결과는 거절됐다. 새 claim UUID→명시 시험 출력→다음 작업 참조→종결, SQL 세대/요청 변조 거절도 확인했다. 별도 retained tenant의 명시 시험 payload이며 Codex/PLC/그래프 대역 실행을 실제 에이전트 판단으로 쓰지 않는다.

가동HTTP/PG/Neo4j **11/11 exit0**(`a038-generation-http/`): 새3작업 정의 등록,2→7→9,검토부터 재작업입력7,옛DONE/선행작업 원문 보존,새timer/UUID,취소된옛사람제출400,잘못된역할403,요청ID다른내용409,동일요청4개 동시접수1회/같은결과,서로다른요청2개 동시접수200+409,process 실제restart뒤 전체행/receipt 동일,세대2에서11제출→COMPLETED. Neo4j에서 모든 UUID의 상태/세대/이전 작업 ID와 인스턴스 세대2를 실제 조회했다. 인스턴스 `rework_inspection_5ebe5c93.17f3683e-663e-42a9-a373-4012347095a8`은 보존됐다. 이는 Codex/활성 Incident 재작업 완주가 아니다.

포털에 현재 세대·작업별 세대/이전 작업 ID·재작업 요청 이력을 표시했다. 실제 인스턴스 탭→요청 연결 펼치기→1280×900/390×844 화면을 직접 확인했다(`screenshot-1791104272841.png`, `screenshot-1791104282402.png`).390 가로 넘침false,브라우저 종료. 첫 inline geometry 평가가 셸 quoting으로 실패해 base64 평가로 실제390/390을 다시 확인했다. 포털 요청 버튼은 아직 없으며 API로 요청한다. 예제정의/definition-authoring/교재13 `rework-generation-contract` 동기화,구조검사0문제,변경절1280/390 렌더 직접확인·넘침false(`a038-book-check`, `book-render/a038-*`). 전체 학생 리허설이 아니다.

남은 연결: 활성 Incident의 원래 효과/종료 여부, 이전 승인 snapshot과 runtime 명령 변수 무효화, 새 decision 생성·기존 decision 재사용 차단·새 사람 승인, 실제 Codex/MCP, 포털 재작업 요청 동선. 현재 Incident/기존 승인·효과가 있거나 시작점의 제어 흐름 밖 의존 활동이 필요한 계획은 명시 보류한다. 이 제한을 최종 범위 축소로 확정하지 않으며 실제 효과 확인/보상 계약과 의존 작업 스케줄러를 이어 구현한다. 전체 그래프 outbox·일반문서 AI 추출·전체 강의/리허설도 미결이다. 이전 Codex 실제 시나리오 도구 정책 거부를 우회하지 않았다.


### A039 판단 생산 작업 연결 — 가동 HTTP/PG/MCP 확인

종료된 프로세스의 Incident가 AWAITING_APPROVAL로 남은 경우 무scope 새 판단을 받는 반례를 추가 재현했다(1failed/23passed, a039-ended-red). 새 판단은409로 막고 기존 판단 ID의 중복 재전달은 원문/상태를 보존한다. 최종 전체 **632passed/기존 경고2, exit0**(a039-final-full.log/xml). process/dmn-mcp build 및 deploy 종료0이다. 최초 --profile cliagents 지정이 기본 프로필을 대체해 process 의존성 누락으로 build1이었고, .env 기본 프로필에 cliagents를 더한 환경으로 수정했다. 원래 실패 로그 a039-build.log는 보존했다.

가동 검사 a039-scope-live: MCP tools/list에 process_scope 노출, tenant/instance/generation/consumer/version/생산 작업 불일치6종409·저장없음, 실제 DMN MCP의 현재 원천 평가→새 판단 제출→정확한 scope 저장, 같은 live claim 중복 원문 보존, 다른 claim 중복 거절, legacy bridge 미개입, 실제 PG save_task_result→사람 선택 대기, 완료 claim의 늦은 새 판단 거절을 확인했다. 앞3작업은 A034 기록 출력의 명시 시험 재사용이다. 새 Codex 실행이나 활성 Incident 재작업 검증이 아니다. 실제 접수는 generation0이며 generation>0은 단위검사 범위다.

첫 검사 실행은 호스트 fastmcp 미설치로 인스턴스 생성 전에 종료1이었다. 서버 이미지의 설치된 fastmcp Client로 실제 HTTP MCP endpoint를 호출하도록 바꿨다. 다음 실행은9검사 통과 후 사람 폼에 허용되지 않는 escalated 필드를 넣어400/종료1이었다. note만 허용하는 정의 계약을 유지하고 검사기를 수정했다. 같은 보존 인스턴스에서 note만 제출한 후속 종료0으로 남은2검사를 확인했다. **합계11/11은 원래9검사+수정 후 동일 사례2검사의 합산이며 전체 검사기 단일 exit0 재실행을 뜻하지 않는다.** 실패 로그/전후 응답/수정 후 result-with-corrected-finish.json을 모두 보존했다.

instance anomaly_response.e3dfb2bb-e2ef-410d-b8c0-120e18bc9d36, Incident INC-1004-01-fe3d. 명시 시험 CLEAR가 실제 Kafka 접수 경로로 반영됐고 정의의 선택 시간초과→사람 검토 제출로 COMPLETED가 됐다. 명령/작업지시 없음, 종료 인스턴스의 새 무scope 판단409를 확인했다. 시험 원문은 삭제하지 않았다. 다음은 활성 Incident의 실제 효과·기존 승인 snapshot·새 판단/새 사람 승인을 재작업 세대에 연결하는 일이다. 의존 작업 스케줄링·전체 그래프 outbox·일반문서 AI 추출·남은 시스템 UI 검증도 남는다. 교재·시수·강의 리허설은 최신 사용자 지시로 범위 밖이다.


### A040 활성 사건 재작업 — 배포 및 실제 검증

원래 Incident/모든 관련 판단/기업 전체 원장을 대조하고, 효과 없는 승인 대기 사건에 새 판단 세대를 연결했다. PENDING/FAILED 원래 승인은 역할 검사 뒤 같은 PG 거래에서 폐기하되 payload/error/history와 SQLite 원문은 보존한다. 새 세대의 새 판단·새 사람 승인이 필수이며, 기존 효과가 있으면 보상 검토로 남긴다. 현재 인스턴스의 decision_id로 명령 대상을 선택한다.

최종전체652passed/경고2,process build/deploy0. 실제PG/SQLite/기업HTTP13/13(강제종료/rollback/동시replay/옛판단거절/새승인;PLC대역), 가동HTTP/PG/DMNMCP/Neo4j18/18(실제 세대1 새판단·별도사람선택대기·옛카드거절·정상검토종료;앞3작업기록출력). 실제Codex/세대1PLC완주는미검증. 첫PG9검사뒤의반복재작업결함과수정/원본은 [REWORK A040](REWORK.md)에 기록했다. 증거 a040-final-tests.*, a040-incident-pg-retry/, a040-incident-live/.

다음은 포털의 재작업 요청·영향/효과 검토와 실패/새판단 대기를 실제 사용 동선에 연결하고, 진단부터 변경 원천을 읽는 실제 실행을 확인한다. 효과 보상/의존 작업 스케줄러/일반문서AI추출/그래프 outbox도 남는다. 새Codex의 기존 도구 정책 거절은 우회하지 않았으며 가동MCP 검사를 Codex 성공으로 세지 않는다. 시스템 작업이며 교재·시수·강의리허설은 제외한다.


### A041 포털 재작업 접수·응답 복구

일반 정의의 실제 브라우저/HTTP13항목 통과: 영향 검토/명시 확인, 전송 전 실패·새로고침·같은본문 재시도, 접수 후 응답 유실의 receipt 복구, 동시 사람 작업 뒤409, 옛 결과 보존/새 결과8/정상 종결,390px 폼. 삭제된 approve export의 초기화 오류와 input/change 상태 반영을 실제 화면에서 수정했다. 상세·주입기 최초 실패·경계는 [REWORK A041](REWORK.md). 새 Incident UI 전체/Codex/PLC 검증을 대신하지 않는다.


### A042 변경 MES의 새 판단·포털 동의·실행

실제 납기6→36/0h 변경이 옛카드 거절·새세대 점수/권고역전으로 이어졌다. Incident 포털 재작업/역할/효과보류 및 새세대PLC·CMMS까지 실제 연결했다. 첫 CLEAR 누락과 두번째 검사기ACK결함/승인FAILED는 보존했으며, 수정후 동의재전달/별도 합성CLEAR로 두번째 finish exit0. 최종 대조17/17의 정확한 범위·실패/복원은 [REWORK A042](REWORK.md). 새Codex/실제고장 재진단 증거가 아니다. 공용 카드의 납기·품질 점수 내역도 표시했다.


### A043 R11/R12 실행 투영 복구 보강

PG 원천 트리거/outbox·일관 snapshot·revision fence·재시도 배포. 전체657/실제PG·Neo4j14/API·서비스재시작4. 원문과 참고, 실패 이력은 HANDOFF §9 G A043 및 [운영 계약](../execution-projection.md). SQLite 사건/판단과 선행 연결 재조정은 미완료. pending0을 전체 의미 연결 완료로 세지 않는다.


### A044/A045 현재 추가 근거 — R09/R10/R11/R12

SQLite원천/outbox·상태/관계재투영666/실제16/API6검증,사건120건graph상태일치,포털반영대기표시. 실제쿨러경로는승인전달DELIVERED뒤현재예측악화로command PENDING,cmdId없음. 새검토경로도현재재작업blocker8개로막혀있음. 이실패를새성공통계에합치지않는다. A045권한있는효과확인/검토종결·새판단·새동의를우선구현한다. HANDOFF §9 A044/A045와 `.evidence/reaudit/a044-service/`가근거다.

A045 추가: 미실행 명령의 새 판단/동의와 종료사건 취소 구현·배포. 전체685/실제PG23, 실제 A044 실패 인스턴스는 포털에서 CANCELLED 및 재시작 보존9+9검증. 활성사건 실제PLC/새Codex 범위는 여전히 미완료. HANDOFF §9 A045.

A046 R05/R09/R10/R11: 현재조건 거절과 일시 오류를 분리하고 실제 MES6→36 변경 뒤 새 판단/동의→PLC ACK/CMMS8건·재시작11건 확인. 전체691. synthetic 경보/처음3작업 기록 출력으로 새Codex 검증이 아니다. HANDOFF §9 A046.

A047 R01/R02: 실제 strategy/ontology-studio 동기화·출처 코드를 대조하고 HYD 스킬 편집의 부분 저장 결함2건을 재현했다. 원자적 저장/수정 충돌/요청 재확인/원문 소유권 보호를 배포했다. 실제Neo4j14/API6 및 포털 응답 유실·재시작·오래된 초안 거절, 전체693. 지식 변경에 따른 기존 실행의 의미 관계 재연결은 다음 A048이며 전체 완료로 세지 않는다. HANDOFF §9 A047.

A048 R01/R12: 실제 지식 조인 변화 후 누락 CHOSE와 오래된 MAPS_TO를 재현하고, 저장된 원천 재투영/두 저장소 중단복구/의미 연결 경고를 구현·배포했다. 전체700/실제SQLite·PG·Neo4j10/가동6/서비스재시작4. 사용자에게 원판단을 새 지식으로 다시 썼다고 주장하지 않는다. 투영만 훼손된 경우와 백업 불일치 복원은 A049 미완료. 상세 실패 로그·근거는 HANDOFF §9 A048.

A049 R01/R12: 거절된 쓰기의 잘못된 완료 처리와 복원 SQLite 동일 revision 덮어쓰기3건을 실제 재현했다. 정확한 영수증·충돌 보류·검토 계획 기반 재등록/원장·의존 판단 복구를 구현하고 배포했다. 전체713/실제SQLite·PG·Neo4j11/가동CLI·사건 전체 복원·업무 불변·재시작9, A048 회귀10. SQLite 실제 백업 복원과 PG 그래프 fence 불일치의 범위를 구분한다. PG 전체 백업 복원/새Codex는 미검증이다. 명령·증거·최종PowerShell확인은 HANDOFF §9 A049. 점수62.5 유지하며 R02/R06 실제 레포 대조로 이어간다.

A050 R02/R07: ontology-studio6a229be8 `agent_session/service.py` L71~250, bpmn-extractor c7992ce9 `extractors/entity_extractor.py` L1~200을 현재 코드와 대조했다. 일반 문서의 고정 원문→정의 기반 cliagents 추출 작업→엔진 인용 검사→생산 작업 출처가 있는 사람 검토/적재와 서버 이력을 구현·배포했다. 전체728/실제API·SQLite·PG·Neo4j 계약13/실제PG 이력·포털 생성 작업5 및 직접 화면 확인. 실제 그래프 단계·원문 관계 조회 후 소유 배치만 되돌렸다. 출력은 명시 합성이며 실제 Codex 일반문서/PDF 추출 미검증이다. HANDOFF §9 A050, MANUAL_INGESTION 참조. 전체 점수62.5 유지.

A051 R05/R06/R07: 회의2 L299~348/neo4j-text2sql25ab12a8 `app/core/sql_guard.py` L1~155와 현재 시계열 경로를 대조했다. 실제 dmn-mcp 센서 연결의 쓰기 계정 사용을 읽기 조회로 확인하고 전용 reader/AST/읽기세션/시간제한을 적용했다. 실제 메타데이터·태그와 생성 SQL 조회를 hyd-dmn에 노출했다. 전체743/실제 Timescale13/가동MCP9; 정상 AND·BOOL_AND AST 거절 결함도 수정했다. SQL은 검사기 작성이며 새Codex 생성 증거가 아니다. PromQL과 지속시간 판정 일반화는 후속. HANDOFF §9 A051/`docs/sensor-queries.md`.

A052 R05/R06: 회의2 L299~348, 현재 exporter/Prometheus2.55.1 및 공식 HTTP API를 대조해 metadata/series/instant·range query MCP를 배포했다. 실제9종 metadata에는 최신TS1/이상점수도 있어 플랫폼 상태만이라는 설명을 정정했다. VS1은 현재 exporter에 없으며 scrape 시각과 센서 이벤트 시각을 구분한다. 전체766/가동MCP17/실제 원천 중지→UNKNOWN→재시작 복구 확인. 새 Codex 질의 생성·지속조건 누락 판정은 미완료다. 기존 참고클론 검색 무결과를47레포 부재 판정으로 확대하지 않는다. HANDOFF §9 A052/`docs/sensor-queries.md`, 최종PowerShell worker0/config불변. 점수62.5 유지.

A053 R05/R06/R07: 기존 Evidence 조회오류/빈값의 false 변환과 원인 순위에서 오류 소거, 수동 원천 실패 후 판단 진행을7실패로 재현했다. WMS8ba09f44 `mcp/wms_mcp/mcp_server.py` L93~116의 오류/성공 분리를 대조하고 UNKNOWN 보존·진단 보류·비교 전 반올림 제거·포털 표시/이전 결과 폐기를 적용했다. 전체775/실제 reader·Neo4j·MCP·HTTP22 및 포털 정상→보류 확인. 별도 합성 시험 규칙만 수정/제거했으며 기존 설비/업무 원문은 변경하지 않았다. 새 Codex의 보류 재개/직접 판단 인수의 진단 출처 강제/평균 SQL의 관측 구간 검증은 미완료. HANDOFF §9 A053, 점수62.5 유지.

A054 R05/R06/R08: 기존 CEP가600초 관측 공백 후 RAISE/599초 공백 후 CLEAR하는 결함을 재현했다. DAQ cadence 공유·입력별 시각/품질·공백 hold 초기화·기존 경보 보존·VS1 slope 만료를 구현했다. 전체791/격리된 실제 Kafka 입력→같은 감지기 코드→출력11, 운영3설비 입력 수집을 확인했다. 현재lite VS1 heartbeat10초/20배속 경사 창3초 불일치로 팬UNKNOWN이 드러났다. 보고 계약 수정과 실제 팬 경로 검증은 최우선 후속이며 이번 성공에 포함하지 않는다. HANDOFF §9 A054. PLC/plant reset 없음,점수62.5 유지.

A055 R05/R06/R08/R14: lite 시간조건6입력 매초 수집, 추가4태그×3설비 실제DB60초 각60관측. 결정13.4와 팬 CLEAR 구현의 추가 slope<=0 불일치를 실제60관측/반례2실패로 확인해 하한1.1/60sim초 유지로 수정했다. 전체796/수정 후 팬14 확인. 앞선12/13 두 실행의 재시작 검토·MITIGATION_FAILED는 그대로 보존한다. 실제 경로는 legacy/LLM 템플릿 대체이며 새 Codex가 아니다. process160MiB의 메모리 압력으로512MiB 적용, 재시작 원인 확정 아님. 새 패턴 정의의 수집·실행 일반화와 전체 변경 시나리오 회귀 미완료. HANDOFF §9 A055,점수62.5 유지.


A060 R05/R06/R08: A059 최종process 배포·쿨러42/42(레거시). 감지기 자원정리6실패 재현 후 전체878/실제Neo4j timeout·회복4/새감지이미지 실제Kafka·재시작14. ontology-studio6a229be8 tools.py L21~65 세션조회와 실제드라이버 transaction timeout 대조. HANDOFF §9 A060.

A061 R02/R07: 표준PowerShell Codex 워커가 Windows 스크립트 정책 UnauthorizedAccess로 시작 전 거절. A033 도구거절과 구분, 우회/새추출작업 없음. R11 completion b272c9ab process_engine.py818~954/compensation_handler.py1~135와 HYD 영향계산·재개·종료조건 재대조, 구현미변경. 다음 반례/스케줄러 HANDOFF §9 A061. 전체Goal active/62.5 유지.

A062 R11/R12: 공개지원 정의의 독립 두경로 중 첫 종료가 다른진행작업을 두고 전체COMPLETED로 만들고 후속제출을 거절하는3반례. flow_state의 종료도착을 같은PG거래에 저장, 작업세대/생산경로별 보존·재작업 이력·남은작업 대기 연결. completion b272c9ab workitem_processor.py3455~3620/4889 및 process_engine.py978~1034 대조. 전체886/실제PG·HTTP·kill/start8/공통종료4/최종이미지쿨러42 통과. 일부기존폼 fixture는 진단진행 중 상급자를 강제활성화하던 구성을 실제진행/timeout으로 변경. 원본실패 보존. 직접UI는 Device Guard/브라우저부재로 미검증, 최신JS제공/구문만검사. 제어흐름밖 의존스케줄러와 전체Goal은 여전히 미완료. HANDOFF §9 A062.

A063 R11/R12: 명확한 생산자의 데이터/실제참조 의존 재작업을 새 UUID/세대와 흐름도달로 대기·재개, PG같은거래 저장·2세대이력·종료장벽에 연결. TODO직접제출 우회2반례를 재현해 거절. completion b272c9ab process_engine.py978~1034/workitem_processor.py3455~3620 대조, SUBMITTED=완료 가정은 비채택. 전체899/이후추가2포함 관련15/실제HTTP·PG·kill-start·동시완료·graph15/최종쿨러42 통과. 최초probe의400/409기대오류와 실패fixture 보존. 조건·게이트웨이·경계재판정, 최초실행 입력대기, 보상 및 다른 전체요구 미완료, 점수62.5 유지. 새Codex/직접UI 차단 경계 동일. HANDOFF §9 A063.

A064 R11/R12: completion b272c9ab database.py2651~2721의 inputData lookup/fallback을 대조하고 모든입력필수라는 추정을 배제했다. 명시 inputBindings의 생산자/최초입력만 필수대기, 작업별 실제입력/출처snapshot·구신세대보존·API/worker query일치·다른writer영향분리를 구현. 전체919/실제HTTP·PG·kill-start·worker점유·재작업·graph15통과. 결과는fixture이며 실제Codex 아님. 직접UI는 정책차단으로 미검증. HANDOFF §9 A064.

A065 R05/R09/R10/R14: A064 실제쿨러가 예측악화+0.6698/+2.2227℃로명령전PENDING; 한계0.5/2.0초과와승인/재검사관측10초차이를확인. 원본실패/중단/무명령사건보존. 실제23초원천측정 세설비각3상태/최대나이10.10초, edge heartbeat3반례후1Hz발행으로수정. 전체922/실제원천3설비각24상태·최대간격1.003초·최대나이1.652초/오류0검증. 허용치/20배속/명령경로변경없음. 최종쿨러결과와미결은HANDOFF A065. 전체Goal 미완료/점수62.5유지.


A066 R13/R01/R02/R06: 기존17클론보존+새30확보로47HEAD를고정기록했다. 부모gitlink23/기존5버전차이,C01기존인덱스차이690보존·선택파일HEAD비교를구분했다. 새30진입코드/설정한정열람,38파일행/SHA/HEAD일치검사; 전체소스/런타임검토아님. REFERENCE_ADOPTION.md/json의47행에채택·보류·HYD대응·미결을기록했다. T04연결검사/A04폼계약/T05모호값/P04승인후비동기적용/T06용어매핑/P01 ETL차이를후속대조로유지. A066제품코드·배포·새통합검사없음. 최신제품증거A065/전체Goal active·62.5유지. 다음원천/의미연결대조는HANDOFF §9 A066.


A067 R01/R02/R06: catalog cf41148d의물리/논리메타데이터와T06실제PostgreSQL저장코드대조. HYD업무MCP의잘못된식별자DDL/정밀도·주석·키손실을실제DB로확인하고catalog/DDL/COMMENT파싱/전체입력이름을보존. 실제HTTP커밋뒤uploads NameError500을발견해영속배치를확인·clear후낡은쓰기제거. 전체928/실제PG·배포MCP·process·Neo4j·규칙SQL·변경/복원18통과. 실패/정리/고정코드행근거는a067-*와HANDOFF §9 A067. 새Codex/직접UI/전체의미연결검증아님,점수62.5유지.


A068 R01/R06/R09/R10: t3_inputs물리출처누락과고정변수수집의반례5실패후현재DB단일행조회/전용reader/타입·중복출처UNKNOWN/승인값·출처·의미변경보류구현. 전체945/실제PG·HTTP·Neo4j·MCP·승인14,최초검사기라벨오류/정리409정확복구보존(a068-*). 기존쿨러42/최종배포결과는HANDOFF참조. Codex질의생성·전체의미·임의rank식검증은아니며다음대조는R09고정점수식/BSC조건. 전체62.5유지.


A069 R06/R09/R10: 회의2 385~413, D02전략맵검토/P03실제KPI기여도/P04확정대상ID→DMN초안·PR대조(고정4파일 a069-reference-read.json). 기존 rankRule 설명 인용/고정식 반례8실패 뒤 명시 산술 정책/동시수정검사/영수증/현재승인 근거 구현. 전체961/실제API·Neo4j·PG·MCP16·최종배포쿨러42/42,18서비스/worker0은HANDOFF참조. 자연어BSC조건/경로 집계·전체 의미/새Codex 미완료.

A070 R01/R06/R09/R10: 회의2 385~413/P03 1db85d3b age_adapter.py262~347 관계속성 보존 대조. 실제 max(weight)/head(conds) 경로혼합 반례와6단위실패 후 개별경로/명시조건/fact-forecast분리/TRUE·FALSE·UNKNOWN/중복없는추정/현재승인 구현. 전체973/실제14/동일배포쿨러42,18서비스/worker0. 자연어 전체 의미·정량인과·새Codex/직접UI는 미검증. HANDOFF A070·docs/bsc-conditions.md,62.5유지.

A071 R10/R11/R12: 회의2 19~24/434~436와 C03 b272c9ab 새작업/부착이벤트 고정2파일 대조. 별도 조건분기의 실제선행검토·새생산자UUID/세대 대기·조건snapshot·새타이머 도달 구현. 실제옛timeout후속 조기도달 결함을 발견/반례/수정. 전체982/실제24/쿨러42,실패2종보존·6fixture모두종결·18서비스/worker0. 효과보상/시작gateway/새Codex·직접UI는 미완료. HANDOFF A071,62.5유지.
