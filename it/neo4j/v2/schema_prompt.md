# 온톨로지 스키마 (에이전트 제공용)

생성 파일이다 (scripts/ontology_v2.py gen, 원본 it/neo4j/v2/schema.json). 에이전트는 이 스키마와 사용자의 질문을 함께 받아 Cypher를 만든다.

## 규칙

- 모든 노드는 고유한 id를 가진다. 접두사가 클래스를 드러낸다 (kpi:, skill:, rule: …).
- 모든 노드는 사람이 읽는 한국어 name을 가진다. aliases는 엔티티 인식(entity resolution)용 다른 이름 목록이다.
- INFLUENCES · AFFECTS의 sign은 +1(같은 방향) 또는 -1(반대 방향)이다. 관계가 없으면 관계를 만들지 않는다 (0을 쓰지 않는다). 조건부면 sign을 두고 condition에 조건을 적는다.
- 금액은 만원 단위다.
- extends가 있는 클래스의 노드는 부모 레이블도 함께 단다. 예: (:Task:FlowNode).
- 표준의 모든 요소를 담지 않는다. 세 결함 시나리오가 실제로 쓰는 요소만 둔다. scripts/ontology_v2.py validate가 인스턴스가 쓰지 않는 스키마 요소를 보고한다.
- 임계값은 문장이 아니라 관계로 둔다: (규칙 또는 이상 패턴)-[:TESTS {operator, value, unit}]->(입력 데이터). 한 규칙의 TESTS는 모두 AND다 (DMN 결정표의 한 행). OR는 규칙을 두 행으로 나눈다.
- 모든 클래스는 label_ko(한글 이름)를 가진다. 표와 그림은 이 이름을 쓴다.
- 질문에 나온 말은 먼저 전문 검색 색인으로 노드를 찾는다: `CALL db.index.fulltext.queryNodes('ont_names', $text)`.
- 상충 관계 질문은 `AFFECTS` 한 번 뒤에 `INFLUENCES*`를 따라 `msr:op-profit`까지 가는 경로를 찾고, 경로의 sign을 곱해 방향을 정한다.
- 조치 방법은 Skill이다. 스킬 하나가 SOP 하나이고(sopId, 단계), 고장 유형에 매칭된다: `(:FailureMode)-[:MITIGATED_BY|REMEDIED_BY]->(:Skill)`. 근본 조치가 특정 원인에만 맞으면 `(:Skill)-[:ADDRESSES]->(:Cause)`가 있다.
- 조치 카드의 출처는 `Rule-[:DERIVED_FROM]->`와 `Skill-[:HAS_STEP]->Step-[:REFERS_TO]->ManualSection` 경로다.

## 가치 계층 (BSC) — BSC (Balanced Scorecard) — 관점 · 전략목표 · 성과지표 · 인과관계

회사가 무엇을 얻고 잃는지. BSC 관점 → 전략 목표(조직 목표) → 성과 지표. 성과 지표 사이의 상충 관계(INFLUENCES +/-)가 에이전트의 거시적 판단 근거다.

- `(:Perspective {id!, name!, order!})` BSC 관점. 재무 · 고객 · 내부 프로세스 · 학습과 성장.
- `(:Objective {id!, name!, description})` 전략 목표. 한 관점에 속하고, 다른 목표를 받쳐 준다 (전략맵의 인과 화살표).
- `(:Measure {id!, name!, aliases, unit!, direction![UP|DOWN], formula, target, thresholdWarn, thresholdCrit, frequency})` BSC 성과 지표. 전략 목표를 측정하고(목표값 · 경고 · 위험 임계값), 다른 성과 지표에 +/- 영향을 준다. 상충 관계의 노드다.

## 프로세스 계층 — BPMN 2.0 최소 집합 — Process · Event · Task · Gateway · SequenceFlow · 수행자

KPI를 달성하기 위해 일이 어떤 순서로, 누구에 의해, 어떤 데이터와 판단으로 진행되는지.

- `(:Process {id!, name!, isExecutable})` 업무 프로세스. KPI를 달성하기 위해 존재하고, 대상(ACTS_ON)인 설비에 대해 돈다.
- `(:FlowNode {id!, name!, definition_id, version, tenant_id, element_id, source_type})` 프로세스 안의 한 지점. Event · Task · Gateway의 부모.
- `(:Event:FlowNode {id!, name!, definition_id, version, tenant_id, element_id, source_type, position![start|boundary|end], eventDefinition![none|message|timer|escalation], messageRef, correlationKey, timer, semantic_id, semantic_warning, catchAll})` 프로세스를 시작 · 중단 · 종료시키는 사건. 트리거는 클래스가 아니라 이 이벤트의 속성(eventDefinition, messageRef, correlationKey)이고, 어떤 경보가 시작시키는지는 CORRELATES로 잇는다.
- `(:Task:FlowNode {id!, name!, definition_id, version, tenant_id, element_id, source_type, taskType![user|service|businessRule|manual|script|send|receive|subProcess|callActivity], tool, agentMode[DRAFT|COMPLETE], orchestration, semantic_id, semantic_warning})` 일의 단위. 종류에 따라 사람이 하거나(user), 시스템이 하거나(service), 판단 규칙을 부른다(businessRule).
- `(:Gateway:FlowNode {id!, name!, definition_id, version, tenant_id, element_id, source_type, gatewayType![exclusive|parallel], semantic_id, semantic_warning})` 흐름이 갈라지거나 합쳐지는 지점.

## 설비 진단 지식 (리소스 계층의 설비 코어) — ISO 13374 / MIMOSA OSA-CBM — SD(상태 감지) · HA(건강 평가) · AG(권고)

이상 패턴 → 증상 → 고장 유형 → 원인 → 증거, 그리고 매뉴얼 절. 아키텍처 v4 L7 설계를 따른다. 조치 방법은 스킬 계층의 Skill(= SOP)이 고장 유형에 매칭되어 이어진다.

- `(:AnomalyPattern {id!, name!, code!, rule!, holdSeconds, detectionMode[held|plc-trip], detectorScope, clearRule, clearHoldSeconds, slopeWindowSeconds, severity[LOW|MEDIUM|HIGH|CRITICAL]})` CEP가 감지하는 이상 패턴. 탐지 임계값은 TESTS의 AND 조건이다. rule은 사람이 읽는 요약이며 실행하지 않는다. held 실행은 명시된 해제 조건과 시간 계약을 함께 검증한다.
  - 필수: 탐지 임계값(TESTS)이 하나 이상 있어야 한다 (`TESTS` out, 최소 1)
- `(:Symptom {id!, name!, aliases, note})` 계측값의 이상 양상.
- `(:FailureMode {id!, name!})` 구성 요소 단위의 고장 유형. 조치 방법(스킬)은 고장 유형에 매칭된다.
- `(:Cause {id!, name!, aliases, prior!})` 고장의 근본 원인. prior는 사전 확률이다.
- `(:Evidence {id!, name!, rule!, sql!, expect![lt|gt|gte], threshold!, weight!, tag, windowSeconds})` 원인을 확정하는 정량 근거. sql 값이 expect 방향으로 threshold를 넘으면 통과한다. rule은 사람이 읽는 조건이다.
- `(:Step {id!, order!, text!, _manual_document, citation, source_id})` 조치 방법(스킬 = SOP)의 한 단계. 근거 매뉴얼 절을 가리킨다.
- `(:ManualSection {id!, ref!, title!, excerpt, _manual_document, citation, source_id})` 기술 매뉴얼의 절. 조치 카드의 출처로 인용된다.

## 리소스 계층 — 조직 · 시스템 · 설비 (ISO 14224 설비 분류 취지) · 상태 변수

실제로 일을 하는 주체와 대상. 사람(역할), 정보 시스템, 설비와 그 물리 상태 변수.

- `(:OrgUnit {id!, name!})` 부서. KPI를 소유한다.
- `(:Role {id!, name!, level!})` 일을 수행하거나 승인하는 역할. level이 높을수록 승인 권한이 크다.
- `(:System {id!, name!, zone![IT|OT], source_id, ingest_batch, _ingest_base, _ingest_history, _ingest_batches, _ingest_created})` 데이터를 갖고 있거나 스킬을 실행하는 시스템. ERP · MES · CMMS · SCADA · AI 에이전트 등.
- `(:Asset {id!, name!, code!, forecastModel, forecastRevision, forecastScope, forecastHorizonS})` 설비 한 대. 예: 유압 파워팩 HYD-01.
- `(:Component {id!, name!, aliases})` 설비 구성 요소. 쿨러, 팬, 주 펌프, 예비 펌프, 모터, 탱크.
- `(:Sensor {id!, name!, tag!, unit, virtual})` 계측 채널. 태그 이름이 실시간 데이터와 연결된다.
- `(:Actuator {id!, name!, resource!, min, max})` PLC가 값을 써서 움직이는 장치. 쓰기 자원 이름(resource)이 PLC 명령과 연결된다.
- `(:StateVariable {id!, name!, aliases, unit!, kind![manipulated|controlled|disturbance], normal, limit})` 설비의 물리량. 조작 변수(팬 속도, 부하)와 결과 변수(유온, 진동, 압력)가 있다. 물리 영향이 KPI로 이어지는 다리다.
- `(:Part {id!, name!, partNo})` 교체 부품.
- `(:Supplier {id!, name!, avl!})` 부품 공급사. avl=false면 승인 공급사 목록에 없다.

## 스킬 · 규칙 계층 — DMN 1.x 최소 집합 — Decision · InputData · DecisionTable(Rule) · KnowledgeSource

조치 방법(스킬 = SOP)과, 어떤 규칙으로 후보를 고르고 걸러 내는지. 규칙마다 출처(KnowledgeSource)가 있다.

- `(:Skill {id!, name!, sopId!, description!, kind![control|work_order], _manual_document, citation, source_id})` 조치 방법. 하나의 스킬이 곧 하나의 SOP(표준 작업 절차)다. 절차 번호(sopId)와 단계(Step)를 직접 갖고, 고장 유형(FailureMode)에 즉시 완화 또는 근본 조치로 매칭된다. 실행할 원자 조치(Action)를 파라미터 값과 함께 묶는다. 에이전트가 사람에게 내미는 조치 가이드 카드 한 장이 스킬 하나다.
  - 필수: SOP 단계가 하나 이상 있어야 한다 (`HAS_STEP` out, 최소 1)
  - 필수: 고장 유형 하나 이상에 매칭되어야 한다 (`MITIGATED_BY|REMEDIED_BY` in, 최소 1)
- `(:Action {id!, name!, code!, kind![command|transaction], param, min, max})` 더 쪼갤 수 없는 조치. 제어 명령 하나 또는 시스템 트랜잭션 하나.
- `(:Decision {id!, name!, question!})` 판단 정의. 질문 하나에 답한다. 입력 데이터와 하위 판단을 요구하고, 결정표로 구현되며, 지식 출처의 통제를 받는다.
- `(:InputData {id!, name!, typeRef!, variable!, source_id, ingest_batch, _ingest_base, _ingest_history, _ingest_batches, _ingest_created, datasource, catalog, schema, table, column, sqlType, assetColumn, derive[hours_from_now], sourceState[OK|MISSING|TYPE_CHANGED|COMMENT_CHANGED], sourceLiveType, sourceLiveComment, sourceBaseComment, sourceCheckedAt, ingested_at})` 판단과 작업 사이를 흐르는 데이터 항목 (DMN InputData = BPMN 데이터 객체 역할). 출처(시스템 · 센서)에서 오거나 앞 작업이 만든다(PRODUCES). REPRESENTS로 온톨로지의 상태 변수나 성과 지표를 가리킨다.
- `(:DecisionTable {id!, name!, hitPolicy![PRIORITY|COLLECT|UNIQUE]})` 규칙 묶음. hitPolicy가 여러 규칙이 맞을 때 결과를 합치는 방법을 정한다.
- `(:Rule {id!, order!, when!, effect![SELECT|EXCLUDE|PENALTY|WARN|RANK], penalty, annotation, rankingPolicy})` 결정표의 한 행. 입력 데이터에 대한 임계값 검사(TESTS)가 모두 맞으면 effect를 낸다. 후보 선택 규칙은 스킬을, 원인 판정 규칙은 원인을 출력하고, 규정 규칙은 스킬을 제외(EXCLUDE) · 감점(PENALTY) · 경고(WARN)한다. when은 같은 조건을 사람이 읽게 쓴 문장이다.
  - 필수: 임계값 검사(TESTS)가 하나 이상 있어야 한다 (RANK 규칙 제외) (`TESTS` out, 최소 1)
- `(:KnowledgeSource {id!, name!, kind![manual|regulation|policy|strategy], ref, _manual_document, document_id, extractor, sha256, source_id})` 판단과 규칙의 권위 있는 출처. 매뉴얼, 사내 규정, 법규, 전략맵.

## 외부 변수 · 예측 — 변수 · 예측 프레임워크

회사가 통제하지 못하지만 KPI와 설비 상태에 영향을 주는 변수(환율, 외기온도, 전력단가 …)와 조치별 예측값.

- `(:ExternalVariable {id!, name!, aliases, unit!, source})` 회사가 통제하지 못하는 변수.
- `(:Forecast {id!, value!, unit!, horizon!, method!})` 어떤 변수의 예측값. 특정 스킬을 실행한다는 가정 아래의 조건부 예측일 수 있다.

## 운영 기록 — 사례 기록 (DMN 판단의 실행 인스턴스)

실행 중에 쌓이는 사건과 사람의 판단 사례. 다음 판단의 선례로 쓰인다.

- `(:Incident {id!, alertId!, openedAt!, status[AWAITING_APPROVAL|CMD_ISSUED|AWAITING_ACK|ACKED|RE_OBSERVING|RESOLVED|WORK_ORDER_CREATED|CLOSED|ESCALATED|REJECTED_BY_OPERATOR|RESOLVED_WITHOUT_ACTION], reason, closedAt, cleared, command_id, work_order_ref, sourcePattern, sourceTrip, sourceAlert, projection_revision, projection_warnings})` 경보 하나로 열린 사건.
- `(:DecisionCase {id!, decidedAt!, reason, followedRecommendation!, status[PENDING_APPROVAL|APPROVED|REJECTED|EXECUTED|PARTIAL], source_incident_id, projection_revision, projection_warnings})` 사람이 실제로 내린 판단 한 건. 고른 스킬과 사유가 남고, 같은 판단의 다음 실행에서 선례로 읽힌다.
- `(:IngestionControl {id!, name!, sequence!})` HYD 교육용 단일 그래프의 DDL 적재/되돌리기를 직렬화하는 기술 기록. 업무 지식이 아니다.
- `(:IngestionBatch {id!, name!, filename!, fingerprint!, status![ACTIVE|CLEARED], createdAt!, clearedAt})` 원본 DDL 적재의 내용 해시와 상태. 되돌린 영수증도 남겨 같은 ID의 재사용을 거절한다.
- `(:ProcessInstance {id!, name!, tenant_id!, status![NEW|RUNNING|COMPLETED|CANCELLED], start_date, end_date, end_event, current_activity_ids, version, definition_id, projection_warnings, rework_generation, projection_revision})` bpm_proc_inst에서 투영한 실행. ProcessGPT 실행 계층을 HYD Process에 연결한다.
- `(:WorkItem {id!, tenant_id!, activity_id!, activity_name, status![NEW|TODO|IN_PROGRESS|SUBMITTED|PENDING|DONE|CANCELLED], tool, agent_mode, agent_orch, draft_status[STARTED|CANCELLED|COMPLETED|FB_REQUESTED|HUMAN_ASKED|FAILED], retry, rework_count, duration, start_date, end_date, due_date, definition_id, version, generation, supersedes_id, rework_request_id})` todolist에서 투영한 작업. 활동 이름은 activity_name에 있고 결과 본문은 원천 DB에 둔다.
- `(:ProcessVersion {id!, name!, definition_id!, version!, tenant_id!, ontology_ref, projection_warnings})` 관계형 proc_def_version의 고정 정의 버전. HYD는 변경 전후 실습 비교를 위해 버전별 흐름 노드도 보존한다. 현재 head 요소만 투영하는 제품과의 차이다.
- `(:ExecutionProjection {id!, tenant_id, lock, revision, payload_hash})` 실행 정의·인스턴스·작업을 그래프에 쓸 때 판본 순서를 지키는 잠금·영수증 (execution_graph). 사람이 편집하지 않는다.
- `(:CaseProjection {id!, lock, revision, payload_hash})` 사건·판단 사례를 그래프에 쓸 때 판본 순서를 지키는 잠금·영수증 (case_projection).
- `(:KnowledgeEdit {id!, fingerprint, created_at, actor, kind, skill, rule, edge, reason, before, result})` 스킬·규칙 편집 요청 하나의 멱등 영수증 (skill_graph.write): 같은 request_id로 다시 오면 저장된 결과를 돌려준다.
- `(:ManualIngestionDocument {id!, tenant, head, snapshot})` 매뉴얼 한 문서의 적재 이력 머리: 현재 판본(head)과 그래프 스냅샷 (manual_graph).
- `(:ManualIngestionBatch {id!, tenant, document, previous, status, fingerprint, createdAt, rolledBackAt, rolledBackBy, plan, before, after, receipt})` 검토·적재 한 번의 영수증과 되돌리기 정보: 계획·전후 상태·상태(ACTIVE/ROLLED_BACK) (manual_graph).

## 관계

`!`는 필수 속성이다.

- `(:Objective)-[:IN_PERSPECTIVE]->(:Perspective)` N:1. 목표가 속한 BSC 관점
- `(:Objective)-[:SUPPORTS]->(:Objective)` N:M. 전략맵 인과: 아래 관점의 목표가 위 관점의 목표를 받쳐 준다
- `(:Measure)-[:MEASURES]->(:Objective)` N:1. 성과 지표가 측정하는 전략 목표
- `(:Measure)-[:OWNED_BY]->(:OrgUnit)` N:1. 성과 지표 책임 부서
- `(:Measure|StateVariable|ExternalVariable)-[:INFLUENCES {sign!, strength, condition, note, conditionPolicy}]->(:Measure|StateVariable)` N:M. 상충 관계. 원천이 오르면 대상이 sign 방향으로 움직인다. 관계가 없으면 만들지 않는다.
- `(:Process)-[:ACHIEVES]->(:Objective)` N:M. 프로세스가 달성하려는 BSC 전략 목표 (조직 목표)
- `(:Process|ProcessVersion)-[:HAS_NODE]->(:FlowNode)` 1:N. 프로세스에 속한 흐름 노드
- `(:Process)-[:ACTS_ON]->(:Asset)` N:M. 프로세스의 대상 설비. 시작 이벤트의 correlationKey가 이 대상을 고른다
- `(:FlowNode)-[:SEQUENCE_FLOW {condition, id, priority, isDefault}]->(:FlowNode)` N:M. 실행 순서
- `(:Event)-[:ATTACHED_TO]->(:Task)` N:1. 경계 이벤트가 붙은 작업 (예: 승인 시간 초과)
- `(:Task)-[:PERFORMED_BY]->(:Role|System)` N:1. 작업 수행자 (BPMN 레인)
- `(:Task)-[:READS]->(:InputData)` N:M. 작업이 읽는 데이터 (BPMN 데이터 연결)
- `(:Task)-[:PRODUCES]->(:InputData)` N:M. 작업이 만드는 데이터 (BPMN 데이터 출력). 다음 작업 · 판단의 입력이 된다
- `(:Task)-[:INVOKES]->(:Decision)` N:1. 판단 규칙 작업이 부르는 판단 (BPMN businessRuleTask → DMN)
- `(:Task|WorkItem)-[:EXECUTES]->(:Skill|Task|Event)` N:M. 정의 작업이 스킬을 실행하거나 실행 작업이 정의 활동을 가리킨다. 끝점 쌍을 구분한다.
  - 허용된 끝점 쌍: `Task → Skill`, `WorkItem → Task`, `WorkItem → Event`. 위 from/to 목록의 모든 조합을 허용하는 것은 아니다.
- `(:Event)-[:CORRELATES]->(:AnomalyPattern)` N:M. 메시지 시작 이벤트가 받는 경보 패턴
- `(:Role)-[:MEMBER_OF]->(:OrgUnit)` N:1. 역할의 소속 부서
- `(:Asset)-[:HAS_COMPONENT]->(:Component)` 1:N. 설비의 구성 요소
- `(:Component)-[:MONITORED_BY]->(:Sensor)` N:M. 구성 요소를 계측하는 센서
- `(:Component)-[:ACTUATED_BY]->(:Actuator)` N:M. 구성 요소를 움직이는 구동기
- `(:Sensor)-[:OBSERVES]->(:StateVariable)` N:1. 센서가 읽는 상태 변수
- `(:Actuator)-[:MANIPULATES]->(:StateVariable)` 1:1. 구동기가 바꾸는 조작 변수
- `(:Component)-[:USES_PART]->(:Part)` N:M. 구성 요소에 들어가는 교체 부품
- `(:Part)-[:SUPPLIED_BY {price!, failRate!, leadDays}]->(:Supplier)` N:M. 부품 공급 조건
- `(:Role|System)-[:HAS_SKILL {_manual_document}]->(:Skill)` N:M. 리소스가 수행할 수 있는 스킬
- `(:InputData)-[:SOURCED_FROM]->(:System|Sensor)` N:1. 입력 데이터의 출처
- `(:InputData)-[:REPRESENTS]->(:StateVariable|Measure)` N:1. 입력 데이터가 나타내는 상태 변수나 성과 지표. 임계값을 온톨로지의 한계 · 목표와 잇는다
- `(:AnomalyPattern)-[:DETECTS]->(:Symptom)` N:M. 패턴이 감지하는 증상
- `(:Symptom)-[:OBSERVED_BY]->(:Sensor)` N:M. 증상이 보이는 센서
- `(:Symptom)-[:INDICATES]->(:FailureMode)` N:M. 증상이 가리키는 고장 모드
- `(:FailureMode)-[:OCCURS_IN]->(:Component)` N:1. 고장이 일어나는 구성 요소
- `(:FailureMode)-[:LEADS_TO]->(:FailureMode)` N:M. 고장의 전파
- `(:Cause)-[:CAUSES]->(:FailureMode)` N:M. 원인이 일으키는 고장 모드
- `(:Cause)-[:INVOLVES_PART]->(:Part)` N:M. 원인과 관련된 부품
- `(:Cause)-[:DISTURBS {sign!}]->(:StateVariable)` N:M. 원인이 움직이는 외란 상태 변수. 여기서 물리 영향(INFLUENCES) 경로가 시작된다
- `(:Cause)-[:EVIDENCED_BY]->(:Evidence)` 1:N. 원인을 확정하는 증거
- `(:FailureMode)-[:MITIGATED_BY {_manual_document}]->(:Skill)` N:M. 고장 유형을 즉시 완화하는 조치 방법(스킬 = SOP)
- `(:FailureMode)-[:REMEDIED_BY {_manual_document}]->(:Skill)` N:M. 고장 유형을 근본적으로 없애는 조치 방법(스킬 = SOP). 특정 원인에만 맞으면 ADDRESSES로 원인을 함께 단다
- `(:Skill)-[:ADDRESSES]->(:Cause)` N:M. 조치 방법이 특정 원인에만 맞을 때 그 원인. 없으면 고장 유형의 모든 원인에 쓸 수 있다
- `(:Skill)-[:HAS_STEP {_manual_document}]->(:Step)` 1:N. 스킬(SOP)의 단계
- `(:Step)-[:REFERS_TO {_manual_document}]->(:ManualSection)` N:1. 단계의 근거 매뉴얼 절
- `(:ManualSection)-[:PART_OF {_manual_document}]->(:KnowledgeSource)` N:1. 매뉴얼 절이 속한 문서
- `(:Skill)-[:CONSISTS_OF {value, seq}]->(:Action)` N:M. 스킬을 이루는 원자 조치와 그 값
- `(:Action)-[:TARGETS]->(:Actuator|System)` N:1. 조치가 쓰는 대상 (구동기 또는 시스템)
- `(:Skill)-[:APPROVED_BY {_manual_document}]->(:Role)` N:1. 스킬 실행을 승인할 최소 역할
- `(:Skill)-[:AFFECTS {sign!, delta, unit, note, conditionPolicy, condition, _manual_document}]->(:StateVariable|Measure)` N:M. 스킬이 상태 변수나 성과 지표를 움직이는 방향과 크기. INFLUENCES 경로를 따라 영업이익까지 이어진다
- `(:Decision)-[:REQUIRES_INPUT]->(:InputData)` N:M. 판단에 필요한 입력 (DMN information requirement)
- `(:Decision)-[:REQUIRES_DECISION]->(:Decision)` N:M. 먼저 내려야 하는 하위 판단 (DMN information requirement)
- `(:Decision)-[:IMPLEMENTED_BY]->(:DecisionTable)` 1:1. 판단을 구현하는 결정표 (DMN decision logic)
- `(:Decision)-[:GOVERNED_BY]->(:KnowledgeSource)` N:M. 판단을 통제하는 출처 (DMN authority requirement)
- `(:DecisionTable)-[:HAS_RULE]->(:Rule)` 1:N. 결정표의 규칙
- `(:Rule|AnomalyPattern)-[:TESTS {operator!, value!, unit}]->(:InputData)` N:M. 임계값 검사. 입력 데이터 값을 operator로 value와 비교한다. 한 규칙의 검사는 모두 AND
- `(:Rule)-[:OUTPUTS]->(:Skill|Cause)` N:M. SELECT 규칙이 내는 결과. 원인 판정 규칙은 원인을, 후보 선택 규칙은 스킬을 낸다
- `(:Rule)-[:APPLIES_TO]->(:Skill)` N:M. EXCLUDE · PENALTY · WARN 규칙이 적용되는 스킬
- `(:Rule)-[:PENALIZES]->(:Measure)` N:1. PENALTY 규칙이 깎는 성과 지표
- `(:Rule|AnomalyPattern)-[:DERIVED_FROM]->(:KnowledgeSource|ManualSection)` N:M. 규칙 · 탐지 임계값의 출처. 조치 카드와 경보 설명에 인용된다
- `(:Forecast)-[:FORECASTS]->(:StateVariable|Measure|ExternalVariable)` N:1. 예측 대상 변수
- `(:Forecast)-[:ASSUMES]->(:Skill)` N:1. 이 스킬을 실행한다고 가정한 예측
- `(:Forecast)-[:GIVEN]->(:Cause)` N:1. 이 원인이 있는 상태를 가정한 예측
- `(:Incident|ProcessInstance)-[:ON_ASSET]->(:Asset)` N:1. 사건 또는 프로세스 실행의 대상 설비
- `(:Incident)-[:RAISED_BY]->(:AnomalyPattern)` N:1. 사건을 연 경보 패턴
- `(:Incident)-[:DIAGNOSED_AS]->(:Cause)` N:1. 판정된 원인
- `(:DecisionCase|ProcessInstance)-[:INSTANCE_OF {version}]->(:Decision|Process)` N:1. 판단 사례 또는 프로세스 실행이 자기 정의를 가리킨다. 끝점 쌍을 구분한다.
  - 허용된 끝점 쌍: `DecisionCase → Decision`, `ProcessInstance → Process`. 위 from/to 목록의 모든 조합을 허용하는 것은 아니다.
- `(:DecisionCase)-[:CHOSE]->(:Skill)` N:1. 사람이 고른 스킬
- `(:DecisionCase)-[:DECIDED_BY]->(:Role)` N:1. 판단한 역할
- `(:DecisionCase)-[:FOR_INCIDENT]->(:Incident)` N:1. 판단 대상 사건
- `(:ProcessInstance)-[:HANDLES]->(:Incident)` N:1. 프로세스 실행이 처리하는 사건
- `(:WorkItem)-[:IN_INSTANCE]->(:ProcessInstance)` N:1. 실행 작업이 속한 인스턴스
- `(:WorkItem)-[:ASSIGNED_TO {kind}]->(:Role|System)` N:M. HYD의 역할/정보시스템 수행자. 제품 User/Agent 해석과 구분한다.
- `(:ProcessInstance)-[:ROLE_BOUND {role_name}]->(:Role|System)` N:M. 실행의 역할 바인딩. 제품 User 대신 HYD 역할/시스템으로 해석한다.
- `(:ProcessInstance)-[:USES_VERSION]->(:ProcessVersion)` N:1. 이 실행이 사용하는 고정 정의 버전
- `(:FlowNode)-[:MAPS_TO]->(:FlowNode)` N:1. 버전별 실행 정의 요소와 원래 업무 온톨로지 요소의 명시 대응. 원래 Process의 HAS_NODE 범위 안에서만 연결
