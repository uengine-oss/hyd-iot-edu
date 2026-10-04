# 참고 레포 채택 대조 — A066

A069 후속: D02 전략맵 품질 기준·P03 KPI 기여도/매핑 프롬프트·P04 정확한 DMN 대상의 초안/PR 저장을 고정 코드로 대조했다. HYD의 [명시 순위 정책·수정 영수증](../ranking-policy.md)을 구현하고 실제16항목을 확인했다. 제품 KPI 기여도와 HYD 조치 순위를 같은 기능으로 취급하지 않으며 BSC 조건/경로 근거의 후속은 아래 A070 기록을 따른다.

A067 후속: T06의 실제 PostgreSQL 용어 저장과 지도 밖 catalog의 원천/소유/설명 계약을 추가로 읽고 HYD의 현재 메타데이터·DDL·원문 주석 보존을 구현했다. [운영 계약과 실제18검사](../enterprise-catalog.md), `a067-reference-read.json`, HANDOFF A067을 본다. 아래 표는 A066 당시의 열람 경계를 보존한다.

전체 Goal/R01~R14의 참고코드 대응표다. 기존 [47개 조사 우선순위](REPOSITORY_REVIEW.md)를 대체하는 완료표가 아니다. **47개 확보, 새 30개 진입 코드/설정의 제한된 열람, 기존 17개 읽기 기록 재사용**을 구분한다. 각 고정 SHA·실제 열람 파일/행·파일 SHA·HYD 경로는 [기계 판독 기록](REFERENCE_ADOPTION.json)에 있다. 아래 판단은 현 시스템에 대한 선택이며 참고 제품 전체의 품질 평가가 아니다. A066에는 참고 서비스 실행·HYD 제품코드 변경·새 통합시험을 하지 않았다.

## 버전과 증거

- `.evidence/reaudit/a066-acquisition.json`: 기존 17개 보존, 빠진 30개 확보 성공. 원지도 visibility는 당시 메타데이터다. private 표시 레포도 현재 인증으로 확보했다.
- 부모 `process-gpt` 3335272b의 gitlink 23개를 추적했다. 새 레포는 gitlink가 있으면 그 커밋, 없으면 확보 시점 HEAD를 사용했다. HEAD 기반 확보를 부모 고정 버전이라고 쓰지 않는다.
- 기존 스냅샷과 부모 pin이 다른 5개(C02/C03/D05/T01/T02)는 기존 검증 근거를 보존하기 위해 바꾸지 않았다. Compose/Kubernetes 이미지 태그 역시 소스 pin과 동일하다고 가정하지 않는다.
- 실제 47 HEAD는 확보 기록과 일치했다. 46개는 tracked 변경 없음. C01 기존 체크아웃은 인덱스/작업트리 차이 690개가 있어 그대로 보존했다. 사용한 `.gitmodules`와 `docker-infra/volumes/db/init.sql`은 HEAD와 LF 정규화 비교가 같았다. 이 정규화는 비교에만 썼으며 원본을 수정하지 않았다. C01 전체 clean 주장은 하지 않는다.
- `a066-snapshot-check.json`은 HEAD/인덱스 검사다. 빌드·실행·의미 정확성 검사가 아니다. JSON의 `read_files`는 이번에 실제 출력으로 읽은 행만 기록한다. 설정 이름 검색, 앞부분 열람, 과거 기록은 전체 코드 검토와 다르다.

## 47개 현재 대응

`계약 반영`도 해당 계약의 부분 채택이다. `대조 중`은 추가 확인이 필요하다. `보류`는 현재 회의 요구를 충족하는 데 해당 런타임을 추가해야 할 근거가 없다는 판단이며, 남은 시스템 요구를 삭제하는 뜻이 아니다.

| ID | 현재 판단 | 확인한 계약과 HYD 대응 | 남은 경계 |
|---|---|---|---|
| C01 | 계약 반영 | 메타 gitlink/DB 원형 → compose.yaml·Supabase migration | 전체 제품 배포 아님; 인덱스 차이 보존 |
| C02 | 계약 반영 | 기존 Execution/폼/재작업 UI 대조 → execution_graph·포털 | 최신 직접 UI·전체 의미 연결 |
| C03 | 계약 반영 | 기존 정의/작업/재작업/inputData → engine·input_bindings | 조건 재판정·보상; inputBindings는 HYD 확장 |
| C04 | 현 경로 유지 | Spring 경로 재작성·MCP proxy 주소 → HYD compose/포털 | 게이트웨이 전체 이식·운영 인증 검증 없음 |
| C05 | 대조 중 | Compose 서비스·이미지·healthcheck 목록 → compose.yaml | 설정 전체 미열람; 이미지 태그와 소스 pin 별도 |
| C06 | 배포 보류 | Kubernetes 런너/MCP proxy/FCM 서비스 연결 → 운영 경계 대조 | 이미지 원본 일부 미확정; K8s 배포 없음 |
| C07 | 계약 반영 | 기존 todolist/events/원자 claim → PG·worker | SDK 전체 이식 아님; 최신 실제 Codex |
| C08 | 배포 보류 | 대화 ID/agent type별 런너 프록시 진입 → workspace 비교 | resolve 후반 미열람; 호스트 워커 교체 근거 없음 |
| A01 | 대조 중 | 도구/스킬/sandbox/checkpointer → create_deep_agent | HYD 변경 지식·추출 실제 검증; 프레임워크 교체 미결정 |
| A02 | 대조 중 | ReAct 세션/PDF2BPMN 필수 선택 선언 → HITL/추출 비교 | agent.py 첫180행; 강제 라우팅 본문 미열람 |
| A03 | 런타임 보류 | AgentCard push 지원에 따른 webhook/sync 분기 → worker 이벤트 비교 | 외부 A2A가 필수라는 근거 없음; webhook 저장 미검증 |
| A04 | 현 경로 유지 | SDK 작업→런타임→폼/도구 이벤트 → outcome/provider 비교 | App Server로 정책 우회하지 않음; 새 Codex 미검증 |
| A05 | 계약 반영 | 기존 CLI pump/on_start/timeout/HITL → runner/hitl | 자식트리/PG 조건부 저장은 HYD 확장 |
| A06 | 사용 중 | CLI provider/resume/이벤트 파서 → 실제 worker | 전체 provider 검증 아님; 최신 실행 차단 |
| A07 | 런타임 보류 | JSON→PromptMultiFormatFlow subprocess 진입 | 연구보고 플로 내부 미열람; 설비 판단 필수 경로 아님 |
| A08 | 런타임 보류 | task_record polling→run_deep_research 진입 | HYD 원문 검토/적재와 일반 연구보고를 구분 |
| A09 | UI 확장 보류 | WebSocket 사용자/대화→VoiceReactAgent 연결 | 음성은 현재 승인/현장제어 필수조건 아님 |
| T01 | 기존 대조 유지 | 문서 검색/메모리 스냅샷·과거 기록 재사용 | 이번 내부 코드 재열람 없음; 검색 품질 미결 |
| T02 | 계약 반영 | 기존 고정 스키마 추출 대조 → manual_extraction | 실제 Codex 일반문서/PDF 추출 정확성 |
| T03 | 런타임 보류 | office MCP 로드·이미지 편집 REST 진입 | 도구 전체 미열람; 문서/슬라이드 제작은 현 Goal 제외 |
| T04 | 검증 경계 참고 | initialize/list tools/timeout/partial → 기존 MCP probe와 비교 | 연결 성공은 도구 결과 정확성 증거 아님 |
| T05 | 대조 중 | resolved/ambiguous/raw 분리 formatter → manual_review 비교 | 다수결은 참값 보장 아님; 좌표/복수값/실제 추출 |
| T06 | 대조 중 | 용어 상태/동의어/소유자·확정 매핑/조인 입력 모델 | 저장·검토 권한 본문/전체 의미 연결 미완료 |
| T07 | 대조 중 | SkillsMCPServer 검색엔진/부분 로딩 상태 진입 | 검색/실행 본문 미열람; 이름으로 채택하지 않음 |
| T08 | 런타임 보류 | FastMCP→PodManager/Executor·TTL 초기화 | Pod shell 도입/PLC 경로 확대 근거 없음 |
| P01 | 대조 중 | ETL scheduler·instance/timeline 서비스 연결 → 모니터링 비교 | ETL 지연/원천 상태 대조; 분석 서비스 미배포 |
| P02 | 분류기 보류 | 신규 instance ingest·정의별 recluster 진입 | 클러스터와 확정 경보 패턴은 다름; ingest 내부 미열람 |
| P03 | 계약 반영 | 기존 원천→그래프 증분·소유권 → knowledge_projection | BSC 전체 의미 연결·업무 상충 변화 |
| P04 | 대조 중 | 대상별 승인→SKILL/DMN 비동기·정의 draft 결과 | applied:true 조기응답을 완료로 채택하지 않음 |
| O01 | 계약 반영 | 기존 고정 스키마/원문 근거/검증 루프 → manual 계층 | 실제 추출·전체 질문/관계 검증 |
| O02 | 연결 추적 유지 | 기존 15개 하위 경로 gitmodules/tree 추적 | 전체 패브릭 이식 아님; 지도 밖 catalog 후보 후속 |
| O03 | DB 교체 보류 | 기존 연구용 DB 스냅샷·조사 기록 유지 | 이번 내부 재열람 없음; Neo4j 교체 근거 없음 |
| O04 | DB 교체 보류 | Bolt listener/PostgreSQL 연결 설정 진입 | og_cypher 본문/성능/완전호환 미검증 |
| O05 | 구현 판단 보류 | 기존 확보 당시 빈 구현 기록 유지 | tree 재확인 전 현재 원격의 빈 레포로 단정하지 않음 |
| D01 | 계약 반영 | 기존 정의/역할/폼/스킬 계약 → definition_registry | 실제 에이전트 신규 정의 생성 종합검증 |
| D02 | 기존 대조 유지 | BSC 전략·상충 요구 스냅샷 유지 | 이번 본문 재열람 없음; 시스템 의미 연결 후속 |
| D03 | 문서 대조 중 | 사이트 navigation에 rework/reference/DMN 안내 연결 | 안내 본문 미열람; 메뉴 존재는 동작 증거 아님 |
| D04 | UI 확장 보류 | Vue router home/marketplace 연결 | 등록/실행 본문 미열람; 마켓플레이스 도입 요청 없음 |
| D05 | 계약 반영 | 기존 업무 DB/RPC/MCP·성공/오류 → enterprise-mcp/PG | HYD 업무 데이터/권한 별도; WMS 전체 이식 아님 |
| X01 | UI 확장 보류 | 주입형 token store/push/file native bridge 진입 | 주석만으로 안전 저장 보장하지 않음; 모바일 미배포 |
| X02 | 현 도입 제외 | 결제 검증→승인→거래/영수증 API | 결제 기능 개발/결제 요청 없음 |
| X03 | 런타임 보류 | CrewAI 작업상태·폼/산출물 이벤트 → worker 비교 | 협업 프레임워크 교체 근거 없음; 실제 실행 미검증 |
| X04 | 런타임 보류 | JSON→MultiFormatFlow·finally adapter shutdown | 연구 플로 내부 미열람; 설비 판단 필수 경로 아님 |
| X05 | 런타임 보류 | MCP+이미지/만화 생성 loader; A02와 별개 | 이미지 도구는 현재 설비 판단에 불필요 |
| X06 | 런타임 보류 | SDK/browser-use optional import·executor 진입 | 자동화 본문 미열람; 브라우저 정책 우회로 사용 안 함 |
| X07 | 기존 대조 유지 | 공통 도구/결과 계약 스냅샷·기존 조사 유지 | 이번 내부 재열람 없음; 공통 유틸 전체 이식 아님 |
| X08 | 현 연결 유지 | 환경 provider별 LangChain 모델/embedding factory | CLI와 다른 경로; 기본 모델명은 현 가용성 보장 아님 |

## 미확정 연결의 현재 증거

1. `agent-router`/`agent-runtime-template`: k8s의 agent-router-deployment에 각각 ghcr 이미지 참조가 있다. `process-gpt-session-router` C08과 이름이 비슷하다는 이유로 같은 소스라고 연결하지 않는다.
2. `mcp-proxy-service`: Service의 80→8080 및 deployment의 `mcp-proxy:v0.3.8` 이미지를 확인했다. C04 gateway도 이 서비스로 전달한다. 소스 레포/커밋은 아직 미확정이다.
3. `fcm-service`: deployment의 `ghcr.io/uengine-oss/fcm-service:3c231a7`, 포트8666, Firebase credential volume 참조를 확인했다. 소스/실제 푸시 전달 검증은 없다.
4. PAL: 이번 C05/C06 YAML·Markdown 검색에서는 연결을 확인하지 못했다. 지도 전체에서 없다는 판정이 아니다. 필요 기능과 소유 레포가 확인될 때까지 미확정으로 유지한다.

## 다음 실제 개발 대조

R13은 여전히 미완료/25점이다. 모든 런타임 설치나 파일 수는 완료 기준이 아니다. 다음은 T06 glossary의 저장/승인 의미와 기존 O01/P03 및 지도 밖 data-catalog의 원천 식별을 HYD R01/R02/R06에 대조한다. 원천→테이블/컬럼→업무 용어→규칙 입력→작업/판단으로 이어지는 **실제 빠진 관계 또는 변경 실패**를 찾아 수정·검증한다. 이미 구현한 일반 스케줄러를 계속 확장하는 일로 대체하지 않는다. T05 추출의 모호성 보존, P04 승인/적용 완료 구분, P01 원천 상태와 분석 지연도 이 표의 미결로 유지한다. 새 Codex/직접 UI 차단과 R11 조건·보상 범위는 그대로 남는다.

A070: P03 1db85d3b app/graph/age_adapter.py262~347의 관계 양 끝·종류·속성 보존을 HYD 개별 BSC 경로 근거에 반영했다. 조건 실행 엔진 코드가 아니며 AGE의 삭제/재생성 구현은 비채택이다. [BSC 운영 계약](../bsc-conditions.md), 실제14/쿨러42·전체973과 원문/HEAD 내용 비교(a070-reference-read.json)를 기록했다. 원문 전체 의미·AI해석·정량 인과 모델은 남는다.

A071: C03 b272c9ab process_engine.py978~1034 및 polling_service/workitem_processor.py4431~4535를 대조했다(a071-reference-read.json,고정HEAD행내용일치). 새재작업행·부착이벤트 후보를 참고해 HYD 조건재검토·정확한생산자대기·새timer도달을 연결했다. 제품보상호출을 실제효과취소로 간주하지 않는다. 전체982/실제24/동일배포쿨러42, 실패2종·미결경계는 HANDOFF A071·운영계약 rework-conditions.md.
