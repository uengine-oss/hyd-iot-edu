# 저장소 지도 전체 관련성 검토

현재 A066의 고정 스냅샷·제한된 코드 열람·채택 대응은 [REFERENCE_ADOPTION.md](REFERENCE_ADOPTION.md)와 [JSON](REFERENCE_ADOPTION.json)을 본다. 아래 초기 표의 강의 분류는 당시 조사 우선순위이며 현 시스템 범위/완료판정이 아니다.

2026-10-04 G1. [지도 원본](sources/repository-map/repositories.json)의 47개 항목과 연결 67개를 기준으로 한 **조사 순서/관련성 판정**이다. 아래 '핵심'은 해당 코드를 확인할 우선순위이며 설치·도입 완료가 아니다. 지도 내용은 2026-10-03 정적 조사이며 원격 최신 여부를 주장하지 않는다. 직접 읽은 파일/범위는 AUDIT의 읽기 기록을 따른다.

분류: **핵심**=필수/현재 요구와 직접 연결, **확장 검토**=강의에 유용한 인접 기능, **후반 비교**=제품 확장/운영 비교, **관련성 확인**=구현·연결을 조사하기 전 채택하지 않음. 여러 분류에 해당해도 첫 조사 목적 하나를 표시한다.

| 지도 ID | 저장소 | 조사 목적/관련성 | 연결 요구 |
|---|---|---|---|
| C01 | process-gpt | 핵심: 제품 서비스 연결·DB 계약·하위 고정 커밋 | R01,R11,R13 |
| C02 | process-gpt-vue3 | 핵심: ontology 계약·migration·프로세스/폼/상태 UI | R01,R10,R11,R12 |
| C03 | process-gpt-completion | 핵심: 정의/버전·활동 실행·분기·재시도·실패 의미 | R08,R11 |
| C04 | process-gpt-gateway | 확장 검토: 서비스/MCP 프록시 경로와 인증 경계 | R07,R10,R13 |
| C05 | process-gpt-infra-docker | 핵심: 실제 로컬 의존성·배포 구성 대조 | R07,R08,R13 |
| C06 | process-gpt-k8s | 후반 비교: 서비스/런너 배포; 이미지 원본 추적에 사용 | R13 |
| C07 | process-gpt-agent-sdk | 핵심: 워크아이템·컨텍스트·인증·이벤트·결과 계약 | R07,R08,R10,R11 |
| C08 | process-gpt-session-router | 후반 비교: 세션 격리·런너 회수, 호스트 워커 경계 비교 | R07,R13 |
| A01 | process-gpt-deepagents | 핵심: 실제 동적 도구 선택·정의/스킬/문서 생성 비교 | R02,R03,R06,R07 |
| A02 | process-gpt-base-agent-langchain-react | 핵심: MCP/세션/스킬 기반 업무 실행의 대안 구현 | R03,R06,R07 |
| A03 | process-gpt-a2a-orch | 확장 검토: 외부 에이전트 위임·중간 결과 계약 | R07,R12,R13 |
| A04 | process-gpt-codex | 핵심: Codex App Server 통합 비교; CLI provider와 동일시 금지 | R07,R12 |
| A05 | process-gpt-cli-agent | 핵심: 태스크/채팅→CLI 실행 전체 경로 | R07,R08,R11 |
| A06 | cliagents | 핵심: 프로바이더/MCP/세션/권한/이벤트 파서 | R03,R07 |
| A07 | process-gpt-openai-deep-research | 확장 검토: 조사 태스크·폴링/결과의 재사용 가치 | R07,R13 |
| A08 | process-gpt-deep-research | 확장 검토: 내부 자료+웹 조사 및 근거 보고 실습 | R02,R13,R14 |
| A09 | process-gpt-react-voice-agent | 후반 비교: 음성 입력; 핵심 실행 의미와 무관한 UI 확장 | R13 |
| T01 | process-gpt-memento | 핵심: 문서 원본/페이지/검색/산출물 provenance | R02,R03 |
| T02 | process-gpt-bpmn-extractor | 핵심: 업무 문서→프로세스/역할/DMN/스킬 추출 | R02,R11,R14 |
| T03 | process-gpt-office-mcp | 확장 검토: 실제 업무 보고/작업지시 문서 산출 | R10,R13,R14 |
| T04 | process-gpt-mcp-validator | 핵심: MCP 도구 발견·연결 오류를 사전 검증 | R03,R04,R07 |
| T05 | process-gpt-visionparser | 확장 검토: 표·스캔 매뉴얼 추출; 원문 유형에 따라 도입 | R02,R14 |
| T06 | process-gpt-glossary | 확장 검토: 업무 용어/컬럼 의미 매핑과 추출 | R01,R02,R06 |
| T07 | process-gpt-claude-skills | 확장 검토: 스킬 탐색/점진 로딩과 기존 CLI 경로 비교 | R07,R13 |
| T08 | process-gpt-computer-use | 후반 비교: 실행 격리와 파일/셸 도구; PLC 우회 금지 | R07,R13 |
| P01 | process-gpt-analytic | 확장 검토: 실행 이력의 통계/타임라인/자연어 SQL | R06,R12,R14 |
| P02 | process-gpt-instance-classifier | 확장 검토: 요청 유형·선례 탐색; 고정 패턴 라우팅과 비교 | R08,R09,R13 |
| P03 | process-gpt-strategy | 핵심: BSC·기업 운영 온톨로지·증분 동기화 | R01,R02,R09 |
| P04 | process-gpt-agent-feedback | 확장 검토: 승인된 피드백→스킬/DMN/프로세스 개선 | R11,R13,R14 |
| O01 | ontology-studio | 핵심: 인텐트/질문 기반 구축·추출·적재·검증·읽기 MCP | R01,R02,R03,R06 |
| O02 | ontologic | 핵심: 온톨로지 플랫폼 하위 연결 추적(지도에서 미전개) | R01,R02,R03,R06 |
| O03 | ontological-db | 후반 비교: 별도 그래프 DB 기능/계약; Neo4j 교체 근거는 없음 | R01,R13 |
| O04 | ontological-db-enterprise-custom | 관련성 확인: 비공개 기업판 차이 확인 전 기능 추정 금지 | R13 |
| O05 | process-gpt-knowledge-graph | 관련성 확인: 확보 스냅샷의 구현 유무 직접 확인 필요 | R01,R13 |
| D01 | bpmn-process-generation-skill | 핵심: 정의/역할/폼/DMN/스킬 생성 계약과 검증 | R02,R11,R14 |
| D02 | process-gpt-strategy-skill | 확장 검토: BSC 목표·상충 요구를 학생이 구체화하는 과정 | R01,R09,R14 |
| D03 | process-gpt-docs.github.io | 핵심: 제품 사용·정의 의미를 코드와 교차 확인 | R11,R13,R14 |
| D04 | process-gpt-agents.github.io | 관련성 확인: 에이전트 등록/실행 UI의 실제 역할 확인 | R07,R12 |
| D05 | process-gpt-sample-app-wms | 핵심: 실제 업무 DB/RPC/MCP·HITL·오류/멱등 처리 | R04,R09,R10,R11 |
| X01 | process-gpt-mobile | 후반 비교: 푸시/오프라인/모바일 승인 | R10,R13 |
| X02 | process-gpt-billing | 후반 비교: 제품 운영 비용/사용량; 결제 기능 도입 요청 아님 | R13 |
| X03 | process-gpt-crewai-action | 확장 검토: 협업 실행체의 폼 결과/이벤트 계약 비교 | R07,R11 |
| X04 | process-gpt-crewai-deep-research | 후반 비교: 실험용 병렬 보고서 구성; 검증 없이 도입 금지 | R13,R14 |
| X05 | process-gpt-langchain-react | 관련성 확인: A02와 별개 ReAct 클라이언트·도구 계약 비교 | R06,R07 |
| X06 | process-gpt-browser-use | 후반 비교: API 없는 업무의 브라우저 실행 및 승인 경계 | R07,R13 |
| X07 | process-gpt-agent-utils | 핵심: DMN·MCP·지식검색·사람 질문·결과 계약 | R03,R06,R07,R10 |
| X08 | process-gpt-llm-factory | 핵심: 런타임 공통 모델 설정/연결, 호출 의존성 확인 | R07 |

## 지도 바깥/미확정 연결

- 기존 확보 `robo-data-text2sql`: 지도에는 제외됐으나 원문 R06과 연결되므로 기존 코드의 질의 생성·검증 참고 여부를 조사. 별도 ROBO 서비스 전체를 자동 이식하지 않는다.
- ontologic의 하위 서비스: `.gitmodules`부터 확인해 지도에 없는 구현을 찾는다.
- agent-router/agent-runtime-template, mcp-proxy-service, fcm-service, PAL 경로: 원지도에서 미확정. 관련 요구를 구현할 때 설정·실제 원본을 추적하며 동일 이름의 다른 서비스를 추정 연결하지 않는다.
- 내부 경로 8개는 소유 저장소의 일부로 추적하며 별도 레포로 중복 집계하지 않는다.
# 지도 외 의존성 확인 — 2026-10-04

`.evidence/reaudit/references/ontologic` e72adf14d66554e7f3018cf608eac69faf0f4007의 `.gitmodules` 전체와 git tree를 읽었다. 기존 47개 지도에서 확장하지 않았던 의존성 15개: antlr-code-parser, jinyoung/robo-data-fabric, robo-data-security-guard, robo-insight-domain-layer, robo-data-platform, neo4j-text2sql, process-gpt-bpmn-extractor, data-platform-olap, robo-data-agent-scheduler, robo-node-local-agent-scheduler, robo-data-catalog, robo-data-glossary, robo-data-frontend, robo-data-analyzer(refactor), ontology-studio. 등록된 모듈과 실제 gitlink/tree는 구분한다(data-platform-olap는 tree). 원본 자체에 README.md 없음.

추가 확보: neo4j-text2sql 25ab12a8b9129b99fa3e83519214e71e12962a9d는 기존 robo-data-text2sql과 같은 HEAD. 별도 구현으로 중복 집계하지 않는다. robo-data-catalog cf41148dccd99765b6527cf70ee57b0b137f1329는 원천 identity/ownership 경계와 R02/R06/A004를 조사할 후보. 두 README를 읽었으나 코드/실행 검증은 후속이다. ontologic gitlink가 고정한 버전과 새 clone HEAD는 다를 수 있다. 새 snapshot은 `.evidence/reaudit/new-reference-snapshots.json`.



## A016 정의·폼 계약 준비 열람 (2026-10-04)

vue3 d88f78c `src/components/api/ProcessGPTBackend.ts` L421~572,615~700,943~1045 추가 열람. putRawDefinition(form)은 tenant/proc_def_id/activity_id로 form_def를 조회·갱신하며 fields_json을 추출한다. published archive 불변시 minor 증가, mutable archive는 uuid 재사용한다. getExecutionDefinition은 prod_version→major→minor 순서의 fallback을 포함한다(1045 뒤 fallback 나머지는 아직 이번 구간에서 미열람). HYD는 기존 A014의 정확 버전 실패 계약을 유지한다. 제품 폼의 버전 고정이 이미 구현됐다고 추측하지 않는다. HYD 폼/인스턴스 UI는 다음 구현 대상이며 아직 새 정의 등록/선택을 완료하지 않았다.

회의1 `sources/meeting-1.txt` 본문1~150행 전체 추가 확인(긴 출력의 꼬리121~150 재열람). 앞부분은 국방 예시의 아키텍처 설명, 후반은 데이터 패브릭 개념에 대한 정정 설명이다. HYD 직접 기능 지시인 회의2와 구별한다. 원문의 'Graph RAG 누락이 구조적으로 불가능'이나 'SQL 결과는 정확'이라는 절대 표현을 검증 없이 기술 사실로 채택하지 않는다. 코드/현재 데이터/관계 범위에 대한 실제 검증이 필요하다. 데이터 패브릭은 복제 금지나 단일 SQL을 필수로 하지 않는다는 원문 후반의 정정도 교재에 유지한다.


## A018~A019 점유/실행중단 원본 대조

agent-sdk58ca16d8680345ce0b030808c12712823248bd49 `processgpt_agent_sdk/function.sql`8~47과database.py131~170: CTE/SKIP LOCKED로STARTED+consumer를원자적으로설정하며SDK는p_limit1. HYD레거시의한결정전용claim에는instance필터를추가해타큐를만지지않는다(A018실제7/7).

cli-agent4475bf797a91fb6c6540e8a4f4b7f98012cf21b7 `core/runner.py`전체열람: on_start자식참조,asyncqueue/pump,wall-clock timeout,finallyterminate/join/kill,ConcurrencyLimit으로claim전동시수용량검사. HYD무출력timeout수정의직접원본이며아직이식전. 설치cliagents/execution.py196~354의동일on_start/teardown/thread-local결과도확인했다. 원본은직접자식terminate이며WindowsMCP자식트리정리는별도검증해야한다.


A020 후속: 위 cli-agent의 pump/on_start를 동기 queue로 이식하고 설치 cliagents의 parser/finally를 유지했다. 원본 직접자식 종료에 HYD의 Windows Job Object 확장을 추가했다. 실제Pg 조건부저장·Windows 자식/부모선종료9/9 및 실제Codex 두 정의 완료 확인(AUDIT A020). 앞의 '이식전'은 열람 당시 기록이다.


## A022 SQL 검증·수정 루프 열람

neo4j-text2sql25ab12a의 validate_sql.py1~180/299~542, ValidateSqlRepairGenerator 전체, repair prompt 전체를 읽었다. SQL guard/EXPLAIN/preview/오류 envelope/재검증 계약을 대조했으며 모델 실행·HYD 이식은 아직 하지 않았다(AUDIT A022). sql_autorepair.py 출력은 잘려 부분 열람. 기존 README만 읽었다는 기록 이후의 추가 범위이며 controller·context 구성 전체를 읽은 뜻은 아니다.


A022 추가: controller.py1687~1896, tools/context.py 전체, tools/__init__.py 전체. run_controller는 context 준비→요구추출→후보SQL 검증 뒤 rubric 판정 흐름이며 이 구간에 row_count0/모든값NULL의 일괄 거절이 있다. HYD의 규칙조건 조회는 0행이 정상인 경우가 있으므로 이 판단을 그대로 복사하지 않는다. '위반이 없음'과 '조회 실패'를 구분해 업무 질문/폼 계약으로 다뤄야 한다. controller의 나머지 후보생성·수렴 전체와 build_sql_context 내부는 아직 미열람/미실행이다.


A022 적용: 같은 커밋의 app/core/sql_guard.py 전체를 재열람했다. 원본의 AST SELECT/금지연산/깊이/표 이름 검사를 참고하고, HYD에는 Scope 기반 CTE·ent 스키마 제한 및 바깥 LIMIT를 추가했다. 전용DB역할과 RLS는 HYD 배포 계약이다. 원본 자체가 스키마 경계/DB 권한까지 해결했다고 설명하지 않는다. HTTP MCP49/49와 실제Codex 두정의/컬럼복구는 AUDIT 후속 근거다.


A021 추가 열람: process-gpt3335272b3f6978886e2b661b9977a0acfe7991e9 docker-infra/volumes/db/init.sql2101~2270의 실제pg_cron RPC와completion b272c9a database.py1016~1045의30분stale consumer해제를확인했다. timer RPC는p_input의proc_inst_id/activity_id만사용해SUBMITTED로변경한다. tenant/task ID/기존status조건은해당본문에없다. 원본의작동방식을근거로삼되HYD의동시성안전성을증명하는것으로취급하지않는다. 실제DB반례는AUDIT A021에기록했다.


A021 적용: 위 pg_cron/consumer 원본은 참고 계약으로 기록하고 HYD에는 별도 SQL 실행용 조회·인스턴스/자식 행 잠금·커밋 후 서비스 실행·Incident 재조회를 구현했다. 원본 RPC를 그대로 복사하지 않았으며 원본의 tenant/task/status 제한 누락을 제품 전체 안전성 평가로 확대하지 않는다. 실제 Pg11/11과 실제 PLC 후 process 강제종료38/38(AUDIT). 원본의 일반claim30분정리 계약은 여전히 남아 있으며 즉시 재시작복구라고 설명하지 않는다.


A024 추가열람: cli-agent4475bf7 core/hitl.py 전문, executor.py291~465의스트림/permission/완료/pause. SDK58ca16d chat_registry.py1~115의도구질문이벤트와이전턴완료대기180초설명. 설치cliagents providers/codex.py281~454의 command_execution.status=declined→PERMISSION_REQUEST를확인했다. 이 조건을실제CLI의모든정책거절/업무질문으로확대하지않는다. HYD에는명시적업무질문제어응답과원자DBpause를추가했고실제Codex2건의질문·답변/동일세션재개를검증했다(AUDIT A024). SDK의 나머지채팅/다중pod공유상태를이식했다고하지않는다.


A026 준비: ontology-studio6a229be8 backend/src/modules/ontology/tools.py520~663의batch_ingest를재열람(잘린574~663별도확인)했다. _source_id/parent_id/관계JSON은입력계약이며문서파일SHA/판본/인용좌표가자동보존되는계약은아니다. 노드별실패를모아status:ok와errors를함께반환하며문자열2000자절단도있다. HYD 매뉴얼경로의문서간절ID충돌/검증오류앞MERGE호출을순수함수/가짜IO로관찰(AUDIT A026), 원본이이미모든문서적재정답을보장한다는전제를두지않는다.

A026 추가: 같은 HEAD의 agent_session/service.py71~237, document_indexing/tools.py 전문, document_indexing/service.py162~227/347~381을 읽었다. 고정 target_schema·구조/의미/레코드 추출·실제 질문 검증 루프, 원문 SHA/페이지/chunk_ref, 검색 결과와 원문 분리를 참고한다. service의 document_id=path.name은 HYD의 논리 문서 ID로 복사하지 않는다. PDF OCR 구현 전체와 실제 제품 실행은 아직 확인하지 않았다. HYD cards.py147~174의 후보는 Rule OUTPUTS에서 오므로 SOP 적재만으로 자동 활성화된다고 설명하지 않는다. `MANUAL_INGESTION.md`에 후속 계약을 기록했다.


A026 적용(09:56): 위6a229be8고정스키마/원문좌표/검증루프를참고하여HYD manual_sources/review/graph/api를연결했다. 문서UUID+SHA,정확인용,사람검토,한거래적재와소유권비교/최신순되돌림은HYD가추가한계약이다. 실제Neo4j17/17·HTTP21/21·105단계4/4범위를MANUAL_INGESTION에기록했다. 원본에이미같은보장이있었다거나원본제품전체를이식했다고하지않는다. 실제Codex일반문서추출루프는아직연결전이다.


A027재작업후속열람(10:49): vue3 d88f78ca0b60d979d9de4988f0cd2969949f7ece의WorkItem.vue2294~2358, ProcessGPTBackend.ts8351~8425에서사용자가범위를고르고completion/rework-complete를호출하는흐름을확인했다. completion b272c9a process_engine.py818~900·954~1033은새UUID/output초기화/rework_count증가·참조활동조회·보상호출을보여준다. polling_service/workitem_processor.py1072~1106은실행scope와최신회차선택이다. 보상본문/트랜잭션/권한/제품실행은아직검증하지않았고HYD에이식하지않았다. 변경된판단의재작업계약은현재승인스냅샷/PLC효과/불변정의와함께설계한다.

A033 사전 열람: completion b272c9ab458f3ca3e18fe286e4e770d291b99e89 process_start_api.py 전문 및 polling_service/polling_service.py 전문(두 파일 Git 수정 없음), database.py909~1048. 원천 이벤트 inbox와 시작활동 조회/업무 폴링을 구분했다. SHA와 정확한 줄수/보존본은 a033-reference/read-manifest.json. 현재 EVENT_INBOX는 설계이며 실제 구현/복구 검증은 아직 아니다.

A064 추가열람: completion b272c9ab database.py2651~2721/get_input_data는 선언필드 값을 조회하되None을제외하며 비시작활동의 빈입력에는 이전활동출력을fallback한다. inputData만으로모든필수입력대기를제품기능이라고할수없다. HYD는별도명시 inputBindings계약과입력snapshot을추가했으며실제15검사는PGclaim/fixture출력/엔진전이범위다. A063의rootIN_PROGRESS/후행TODO 및 분기상태검사원본과함께참고하되이추가계약자체를제품원본기능으로기술하지않는다.


A067 추가대조: robo-data-catalog cf41148d의contracts/schema.py전체/api/schema.py1~140/graph/schema_queries.py1~145에서물리원천·논리명/설명·owner경계를확인했다. T06의backend/service/glossary_manage_service.py258~310은public.terms에PostgreSQL로기록한다. 라우터주석의Neo4j표현을실제저장사실로쓰지않는다. HYD에는현재DB메타데이터보존/인용DDL/주석의미보존을구현했고제품전체glossary/catalog이식은아니다. 실제18/전체928범위는HANDOFF A067,열람해시는a067-reference-read.json.


A069: D02/P03/P04의 추가 고정 코드 대조와 HYD 명시 순위 정책 대응은 REFERENCE_ADOPTION의 후속 항목 및 a069-reference-read.json을 따른다. BSC 조건 전체/제품 DMN 런타임 이식은 완료로 세지 않는다.

A070: P03 1db85d3b app/graph/age_adapter.py262~347 관계 양 끝·종류·속성 보존을 실제대조했다. 로컬 CRLF와 HEAD LF 외 행내용일치(a070-reference-read.json). HYD 개별 BSC 경로/조건근거에 반영했으며 AGE 삭제/재생성이나 제품 조건엔진 이식으로 확대하지 않는다. 실제14/쿨러42·전체973, HANDOFF A070.

A071 C03 후속: 새작업/부착이벤트의 고정2파일 대조와 HYD 조건·타이머 재검토 대응은 REFERENCE_ADOPTION 및 a071-reference-read.json을 따른다. 제품의 보상 생성 호출과 실제 PLC/업무 효과 보상은 구별하며 후자는 미완료다.
