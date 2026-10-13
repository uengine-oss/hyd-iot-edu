# 온톨로지 클래스 (생성 파일 — schema.json)

| 계층 | 클래스 (영문) | 클래스 (한글) | 준용 표준 |
|---|---|---|---|
| 가치 계층 (BSC) | Perspective | BSC 관점 | BSC Perspective |
| 가치 계층 (BSC) | Objective | 전략 목표 (조직 목표) | BSC Strategic Objective |
| 가치 계층 (BSC) | Measure | 성과 지표 | BSC Measure (성과 지표) |
| 프로세스 계층 | Process | 프로세스 | BPMN Process |
| 프로세스 계층 | FlowNode | 흐름 노드 (추상) | BPMN FlowNode (추상) |
| 프로세스 계층 | Event | 이벤트 | BPMN Event |
| 프로세스 계층 | Task | 작업 | BPMN Task |
| 프로세스 계층 | Gateway | 게이트웨이 | BPMN Gateway |
| 리소스 계층 | OrgUnit | 조직 (부서) | 조직 단위 |
| 리소스 계층 | Role | 역할 | BPMN Performer / 직무 |
| 리소스 계층 | System | 정보 시스템 | 정보 시스템 (BPMN DataStore 취지) |
| 리소스 계층 | Asset | 설비 | ISO 14224 Equipment unit / MIMOSA Asset |
| 리소스 계층 | Component | 구성 요소 | ISO 14224 Maintainable item |
| 리소스 계층 | Sensor | 센서 | MIMOSA DA (Data Acquisition) |
| 리소스 계층 | Actuator | 구동기 | 구동기 (PLC 쓰기 대상) |
| 리소스 계층 | StateVariable | 상태 변수 | 공정 상태 변수 |
| 리소스 계층 | Part | 부품 | 예비품 / 자재 |
| 리소스 계층 | Supplier | 공급사 | 공급사 |
| 설비 진단 지식 (리소스 계층의 설비 코어) | AnomalyPattern | 이상 패턴 | ISO 13374 SD (State Detection) |
| 설비 진단 지식 (리소스 계층의 설비 코어) | Symptom | 증상 | ISO 13374 HA (Health Assessment) — 관측 증상 |
| 설비 진단 지식 (리소스 계층의 설비 코어) | FailureMode | 고장 유형 | ISO 14224 Failure mode |
| 설비 진단 지식 (리소스 계층의 설비 코어) | Cause | 원인 | ISO 14224 Failure cause |
| 설비 진단 지식 (리소스 계층의 설비 코어) | Evidence | 증거 | MIMOSA 확증 규칙 |
| 설비 진단 지식 (리소스 계층의 설비 코어) | Step | SOP 단계 | SOP 단계 |
| 설비 진단 지식 (리소스 계층의 설비 코어) | ManualSection | 매뉴얼 절 | 지식 베이스 문서 조각 |
| 스킬 · 규칙 계층 | Skill | 조치 방법 (스킬 = SOP) | 조치 방법 = SOP (DMN 판단의 출력 · BPMN 서비스 작업이 수행) |
| 스킬 · 규칙 계층 | Action | 원자 조치 | 원자 조치 (PLC 쓰기 또는 시스템 트랜잭션) |
| 스킬 · 규칙 계층 | Decision | 판단 (DMN) | DMN Decision |
| 스킬 · 규칙 계층 | InputData | 입력 데이터 | DMN InputData |
| 스킬 · 규칙 계층 | DecisionTable | 결정표 | DMN Decision Table |
| 스킬 · 규칙 계층 | Rule | 규칙 | DMN Decision Rule |
| 스킬 · 규칙 계층 | KnowledgeSource | 지식 출처 | DMN KnowledgeSource |
| 외부 변수 · 예측 | ExternalVariable | 외부 변수 | 외생 변수 |
| 외부 변수 · 예측 | Forecast | 예측 | 예측 |
| 운영 기록 | Incident | 사건 | 사건 기록 |
| 운영 기록 | DecisionCase | 판단 사례 | DMN 판단의 실행 인스턴스 |
| 운영 기록 | IngestionControl | 적재 트랜잭션 제어 | HYD ingestion provenance (implementation record) |
| 운영 기록 | IngestionBatch | 적재 배치 | HYD ingestion provenance (implementation record) |
| 운영 기록 | ProcessInstance | 프로세스 실행 | ProcessGPT SCHEMA 0.2.0 Execution (HYD adapter) |
| 운영 기록 | WorkItem | 실행 작업 | ProcessGPT SCHEMA 0.2.0 Execution (HYD adapter) |
| 운영 기록 | ProcessVersion | 프로세스 정의 버전 | ProcessGPT version provenance; HYD immutable element snapshot |
| 운영 기록 | ExecutionProjection | 실행 투영 잠금 | 내부 기록 |
| 운영 기록 | CaseProjection | 사건·판단 투영 잠금 | 내부 기록 |
| 운영 기록 | KnowledgeEdit | 지식 편집 영수증 | 내부 기록 |
| 운영 기록 | ManualIngestionDocument | 매뉴얼 적재 문서 | 내부 기록 |
| 운영 기록 | ManualIngestionBatch | 매뉴얼 적재 배치 | 내부 기록 |
