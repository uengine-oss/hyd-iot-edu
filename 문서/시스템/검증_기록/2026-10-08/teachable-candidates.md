# 강의 가치 기준 재검토 — 회의가 말한 굵직한 블록 후보 (2026-10-08, 읽기 전용 조사)

기준: 사용자 10-08 "강의할 만한 대상이면 더 많이 가져올수록 좋다" + 조정 "세부 기능 말고 회의에서 언급된 굵직한 블록(한 회차 3시간 이상을 채우는 층·개념·구현)만 후보". 회의 원문에 없는 큰 단어는 넣지 않았다.

읽은 것: `sources/meeting-2.txt` 1~558행 전체(HYD는 1~461), `sources/meeting-1.txt` 1~150행 전체(국방 강의 전사 + 데이터 패브릭 Q&A — HANDOFF L24 "참고만", HYD 필수 요구 아님), `docs/회의자료/대표발언_20261001_온톨로지_정리본.md` 전체, `USER_UTTERANCES.md`·`USER_UTTERANCES_CODEX_20261004.md` 전체, REFERENCE_ADOPTION.md·.json(47개 repositories·followups), REPO_GAP.md 전체, DECISIONS 73~106, curriculum-75h.md 전체, `docs/sessions/` 25개 제목·"이번에 할 것", GOAL.md 완주 목표.
레포 확인: `.evidence/reaudit/references/{a066,ontologic,robo-data-catalog,neo4j-text2sql}`와 이전 세션 스크래치 `refs/`(completion·ontology-studio·memento·robo-data-text2sql 등)에서 README·모듈 목록을 직접 봤다. **ontologic의 data-fabric·robo-data-analyzer·data-secure-guard 서브모듈은 비어 있음(미체크아웃) — 그 본문은 "레포 미확인"**.
회의에 나왔지만 HYD에 이미 있어 후보에서 뺀 것: Neo4j MCP·스키마→Cypher(7회차), 엔티티 인식(`schema_prompt.md` L8 aliases·`ont_names` 색인), Text2SQL(enterprise MCP, 9·12회차), Prometheus/PromQL 트리거·조회(DECISIONS 58), 인제스천(9회차), HITL 포털·모니터링(14~16회차), 가드레일(14회차), BSC 상충 부호 계산(`bsc_conditions.py`, 6·23회차).

## 표 1 · 굵직한 블록 후보 (12개)

| # | 블록 | 회의 원문 위치 | 회의가 말한 뜻 | 지금 HYD | 레포 참고 구현 | 한 회차로 만들면: 학생이 만들 것 / 볼 것 | 회차 | 크기 | 기존 구조 충돌 | 강의 가치 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **데이터 패브릭(다종 DB를 한 창구로)** | meeting-2.txt:63-67, 438-447; meeting-1.txt:16-29, 131-150 | 현장 DB는 Supabase 한 종이 아니라 Oracle·SAP ERP 등 여럿 → 옮기지 않고 연결해 한 창구로 조회, 카탈로그·권한·품질을 같이 관리 | **없음** — HANDOFF §2 L54 "구현하지 않고 후반 설명만", 24회차는 그림·말만 | ontologic `specs/001-datasource-backed-virtual-classes`(클래스를 테이블에 바인딩, 질의 시 SQL로 확장, Implemented), `data-fabric` 서브모듈은 **레포 미확인(빈 폴더)** | 두 번째 업무 DB(예: 별도 ERP 스키마)를 붙이고, 온톨로지 InputData가 "어느 원천의 어느 열"을 가리키게 한 뒤 에이전트가 한 창구로 두 원천을 조인 / 원천이 바뀌어도 질의 쪽은 그대로인 것 | 24(설명→실습), 신규 6부 | L — 원천 추가·조회 창구·카탈로그 연결·enterprise MCP 확장, 패브릭 구현 본문 미확인 | **충돌**: HANDOFF.md §2 확정 방향(L54)을 사용자가 바꿔야 함. `it/enterprise-mcp`는 단일 DB 전제 | **상** — 두 회의 모두 "다음 확장"으로 명시한 유일한 큰 층 |
| 2 | **레거시 메타데이터 증강 → 카탈로그·리니지** | meeting-1.txt:30-42; meeting-2.txt:253-293(회사 DB 스키마·기존 문서 인제스천) | 테이블·컬럼이 코드명이고 FK도 없는 DB를 DDL + 스토어드 프로시저(사용 코드)로 LLM이 의미를 복원하고, 생성→사용 리니지까지 관리. 자동화는 추출까지, 승인은 사람 | **얕음** — DDL 인제스천은 주석·원천·소유만 보존(`ingest.py`·`ddl_sync.py`·`docs/enterprise-catalog.md`), 코드 해석·리니지·LLM 증강 없음 | `robo-data-catalog`(`enrichment/`·`lineage/`·`search/`, FK·READS·WRITES·DATA_FLOWS_TO), ontologic `specs/008-legacy-metadata-to-ontology`(Draft: 난독화 DDL + 프로시저·샘플로 증강), `robo-data-analyzer` **레포 미확인** | 이름이 코드인 레거시 스키마 + 프로시저를 받아 에이전트가 설명·관계 후보를 내고 사람이 승인해 InputData에 반영 / 증강 전엔 질의가 테이블을 못 고르고 증강 뒤엔 고르는 차이 | 9 뒤 신규, 12 | L — 증강 작업 정의·승인 화면·리니지 관계 스키마 추가 | **주의**: `schema.json` 단일 원본(DECISIONS 89), DDL 변경 바인딩 상태(DECISIONS 86) 규칙 위에서 해야 함 | **상** — "인제스천 과정을 학생에게"(meeting-2 L271)의 실제 난제 |
| 3 | **피드백 → 규칙·스킬·정의 개선 제안(학습 루프)** | meeting-2.txt:7-8(사고 인스턴스를 남겨 향후 피드백), 448(룰을 관리하기 위해 ProcessGPT) | 사고·판단 기록이 다음 판단과 규칙 개정으로 돌아오는 층 | **얕음** — 선례 읽기(`templates/t3_precedents.cypher`, DecisionCase→CHOSE), 검토자 판정 핀(DECISIONS 74), 순위 정책 수정 영수증(`ranking-policy.md`). 사례를 모아 규칙 개정안을 만드는 단계 없음(P04 "보류") | `process-gpt-agent-feedback`(`core/feedback_batch_manager.py`: 활동별 배치 5건/3일 → SKILL·DMN_RULE·PROCESS_DEFINITION 분류 → 제안 → 대상별 승인 → draft 판본+병합요청, `core/dmn_xml.py`) | 같은 경보에서 사람이 추천과 다른 카드를 고른 사례 몇 건 → 에이전트가 DMN 규칙 개정안 작성 → 사람이 승인 → 새 판본에서 순위가 바뀜 / 제안·승인·적용이 분리된 기록 | 23 뒤 신규, 16 | L — 사례 수집·분류 작업 정의·제안 저장·판본 적용(P04는 적용 결과 응답 결함 있음, REFERENCE_ADOPTION P04) | **주의**: `skill_graph.py` 영수증·409, 판본 고정(DECISIONS 22·24), 사람 승인 원칙(HANDOFF §3) 안에서 | **상** — 6계층의 마지막 층(피드백)을 실제로 돌리는 장면 |
| 4 | **자연어·문서 → 프로세스 정의 생성** | meeting-2.txt:448(프로세스들을 자유롭게 바꾸고), 436(구현하다 보면 ProcessGPT) | 프로세스를 코드 없이 바꾸는 것이 ProcessGPT의 존재 이유 | **얕음** — 정의는 사람이 JSON으로 작성(`docs/definition-authoring.md`), 등록 검증·정적 연결성·제품 모양 수용은 있음(`definition_registry.py`, A096·A115·A116) | `bpmn-process-generation-skill`(D01 스킬, 제품 설계기 모양), `process-gpt-bpmn-extractor`(문서→BPMN, 검증기 `process_validator.py`) | 코딩 에이전트에 D01 스킬을 주고 "점검 결과 검토 프로세스"를 말로 요구 → 생성된 정의를 HYD 등록기에 올려 거부 사유로 고치고 → 실행 / 말→정의→등록 검증→인스턴스 | 16(정의 변경 실습 확장), 24 | M — 스킬은 있음, B5로 제품 모양을 이미 받음; 생성→등록 왕복 절차·예제 정의 | 없음(등록기가 받는 모양 그대로). 생성 정의 실행 시 기존 정의 2.2 불변 | **상** — "ProcessGPT가 무엇인가"를 학생 손으로 확인 |
| 5 | **What-if 상충 시뮬레이션(외부 변수 → KPI)** | 대표발언 정리본 §1(외부 변수·예측 프레임워크), §4(환율→매출·비용·재고, 부품가↔품질); meeting-2.txt:386-413(납기 vs 장비 상충) | 온톨로지의 본뜻은 가치의 상충 관계 — 변수 하나를 바꾸면 지표들이 어떻게 엇갈리는가 | **얕음** — 관계 부호 곱 상충(`bsc_conditions.py`, `docs/bsc-conditions.md`), 설비 물리 예측(`forecasting.py`, FORECAST_MODEL). 시간 축 KPI 시뮬레이션·인과 발견 없음 | ontologic `what-if-simulator`(CLD 극성·Driver/State/KPI·Stock/Flow, `edge_based_simulation.py`, `causal_discovery.py`, `ontology_loader.py`(Neo4j)) | 6회차 영향 사슬에 영향 함수(계수)를 붙여 "부품가 10% 인하 / 납기 우선 운전"을 몇 주기 돌려 매출·비용·품질 곡선 비교 / 같은 그래프가 판단 근거이자 실험실이 되는 것 | 6, 23 | L — 영향 함수 스키마 추가·시뮬 엔진 이식(torch·TTM·MindsDB 부분은 제외) | **주의**: 수치 영향 함수가 `schema.json`(DECISIONS 89)에 없음, 업무 수치는 업무 DB가 주인(DECISIONS 87) | **상** — 대표가 "이런 걸 온톨로지라고 부른다"고 한 바로 그 예 |
| 6 | **하이브리드 RAG 라우팅(벡터·Text2SQL·GraphRAG)** | meeting-1.txt:59-70; meeting-2.txt:242-245(이 구조엔 문서 RAG 비중이 작다) | 질문 유형별로 문서는 벡터, 수치는 SQL, 관계는 그래프로 보내고 근거만 합친다. 벡터 RAG는 잘린 예외 조항에서 틀린다 | **얕음** — GraphRAG·Text2SQL은 있음, 매뉴얼 원문 청크·벡터 색인 없음(REPO_GAP §5 "지식 문서 색인 없음", B8 본문 검색 "선택·미착수") | `ontology-studio/backend/src/modules/document_indexing/`(OCR·청크 1,200/150·임베딩·Neo4j 풀텍스트+벡터), `robo-data-text2sql`(HyDE·다축 벡터·FK 경로), `process-gpt-memento` | 매뉴얼 HM-8/9를 청크·벡터 색인 → 같은 질문 세트를 세 경로로 답하고 틀린 사례(예외 조항 누락) 비교 → 라우팅 규칙 작성 / 경로별 정답·실패 표 | 12, 9 후반 | M — 색인·라우터·비교 질문 세트 | **주의**: 매뉴얼 원문은 SQLite 보관·그래프엔 절/단계만(REPO_GAP §5), 임베딩 모델 선택(로컬 BGE-M3 또는 유료 API) | **상** — 세 방식의 장단을 같은 데이터로 체험 |
| 7 | **에이전트 경로 고착화(RPA화)** | meeting-1.txt:78-96(RPA는 사람이 길을 그림·AI 비용 없음·결과 동일, 에이전트는 길을 찾음) | 같은 일을 반복하면 에이전트 판단을 정해진 길로 굳혀 비용·변동을 없앤다 | **없음** — 결정론 DMN 엔진은 있으나 에이전트 실행 이력을 코드로 굳히는 단계 없음(REPO_GAP §1 13 "후반 설명") | `process-gpt-completion/deterministic_generator.py`(DONE 확정 때 work_history 정규화→파이썬 코드 생성), `deterministic_signature.py`, `deterministic_template.py` | 펌프 진단 작업을 여러 번 돌린 이벤트 기록에서 고정 경로 코드를 만들고, 다음 경보는 LLM 없이 처리 → 입력이 달라지면 다시 에이전트로 / 비용·시간·결과 차이 | 10·14 뒤 신규, 24 | L — 이력 정규화·생성기·되돌림 조건, 제품 코드 규모 큼 | **주의**: 워커 이벤트 모양(`worker/events.py`)과 제품 work_history가 다름 | **상** — "언제 에이전트, 언제 규칙"의 실물 답 |
| 8 | **에이전트 옵스·프로세스 분석** | meeting-1.txt:104-107; meeting-2.txt:434-435(모니터링 화면) | 어떤 에이전트가 어떤 도구·지식을 썼고 어디서 지연·실패했는지 기록·분석해야 개선을 검증할 수 있다 | **얕음** — 건별 이벤트·트레이스·인스턴스 화면은 있음, 집계(병목·실패율·재작업·도구별 지연) 없음 | `process-gpt-analytic`(`backend/app/etl.py` 스타 스키마, `/api/analytics/bottleneck`·`rework`·`workload`·`process-performance`, `timeline_service.py`) | todolist·events를 분석 테이블로 적재하고 병목·재작업·도구별 시간 질의·대시보드 / 세 시나리오 완주 기록에서 어디가 느렸나 | 15, 18, 19~22 뒤 | M — ETL·질의 몇 개·포털 탭 | 없음(읽기 전용 집계). 레포의 전체 UPSERT·f-string SQL은 따라 하지 않음(REFERENCE_ADOPTION P01) | **중** — 측정 개념은 좋으나 신기술보다 SQL 집계 위주 |
| 9 | **사람 알림 채널(Mattermost 등)** | meeting-2.txt:405-426(Mattermost 같은 내부 알림 툴, 노티까지만 주고 버튼), meeting-1.txt:102-104(모바일 알림) | 에이전트가 사람에게 알리고 사람은 버튼만 누른다 | **얕음** — `notifications` 테이블·포털 표시(`20261003000001_process_engine.sql`), 외부 채널은 "후반 설명"(REPO_GAP §1 알림) | 레포 참고 구현: Mattermost **없음**; 푸시는 `process-gpt-k8s` fcm-service 매니페스트·`process-gpt-mobile`(Firebase — 표 2) | 로컬 Mattermost 컨테이너에 알림 봇을 붙여 사람 작업이 열리면 채널 메시지 + 포털 링크 / 알림→포털 승인→PLC ACK까지 | 16 | M — 컨테이너·웹훅·알림 소비자 | 없음. 단 버튼으로 직접 제어 금지(meeting-2 L430, HANDOFF §3) | **중** — 장면은 좋지만 한 회차를 채우기엔 얇음 |
| 10 | **LLM 프록시(감사·쿼터·비식별·등급 라우팅)** | meeting-1.txt:108-114 | 모든 LLM 요청이 거치는 관문 — 사용량·실패 원인을 보고 민감 정보를 가린다 | **얕음** — LiteLLM 중계는 실행 단위로만(DECISIONS 69), 워커는 구독 로그인 CLI | `process-gpt-infra-docker/docker-compose.yml`의 litellm·litellm-db 서비스; `data-secure-guard` **레포 미확인** | LiteLLM을 띄워 워커 CLI의 기본 주소를 프록시로 돌리고 사용량·실패 로그·키별 한도를 본다 / 한 사건의 토큰·비용 | 11, 13 | M | **주의**: 프록시 경유는 API 키 경로(구독 로그인과 다름) → 실호출은 유료 키 필요 | **중** — 운영 필수 개념이나 비용 제약 |
| 11 | **작업 큐와 워커 풀(여러 워커가 일감 나눠 갖기)** | meeting-1.txt:115-117 | 에이전트 한 건이 실행 단위를 점유하므로 큐를 두고 여러 워커가 하나씩 가져간다 | **있음(단일)** — DB 큐 + 임대(lease·claim_count·회수, `20261007000018_worker_lease.sql`·`..21_claim_count_reclaim_only.sql`), 여러 워커 동시 claim은 미검증(REFERENCE_ADOPTION A092 표) | `process-gpt-k8s/keda/keda-scaled-objects.yaml`(SQL 트리거 자동 확장), `process-gpt-agent-sdk` lease | 워커 2~3개를 띄우고 동시에 경보 세 개 → 누가 무엇을 집었는지, 한 워커를 죽이면 회수되는지 / 큐·임대·회수 | 13 | S~M — 기존 임대 위에 다중 기동 절차·관찰 화면 | **주의**: K8s/KEDA 자체는 표 2(단일 호스트 compose), 검증 1회 원칙(DECISIONS 104) | **중** — 구조 이해엔 좋으나 기존 13회차와 겹침 |
| 12 | **프로세스 계층과 하위 프로세스** | meeting-1.txt:97-102(메가·메이저·메인·서브·태스크, 에이전트는 태스크) | 업무는 계층이고 에이전트는 가장 아래 태스크를 맡는다 | **없음** — 서브프로세스·다중 인스턴스 실행 분기 0(REFERENCE_ADOPTION C03, `engine.py`) | `process-gpt-completion/polling_service/workitem_processor.py` `_process_sub_processes` L1188-1657·`resolve_multi_instance_count` L1397 | "정비 요청" 단계를 하위 프로세스(부품 확인→작업지시)로 분리하고 설비 3대에 다중 인스턴스 / 부모·자식 인스턴스와 화면 | 15·16 | L — 엔진 분기·투영·화면 | **충돌**: DECISIONS 95 "서브프로세스·다중 인스턴스는 이번 범위 밖(사용자 결정)" | **중** — BPMN 핵심이나 국방 강의 쪽 언급이고 HYD 회의에는 없음 |

### 회의 언급 없음 — 레포에만 있는 큰 블록(따로 둠)

| 블록 | 레포·파일 | 한 줄 |
|---|---|---|
| 멀티 에이전트(서브에이전트 위임) | `process-gpt-deepagents`(create_deep_agent, A01) | 회의는 "범용 딥에이전트 하나"(meeting-2 L154-156). 서브에이전트 요구 없음(REFERENCE_ADOPTION A01) |
| 인스턴스 자동 분류·Top 리스트 | `process-gpt-instance-classifier`(pgvector kNN + BERTopic, `app/cluster.py`) | 사건 묶음 분석으로는 흥미로우나 경보 패턴은 선언 규칙(P02) |
| 장기 메모리·문서 기억 | `process-gpt-memento`, completion `mem0_agent_client.py` | 표 1-3(피드백)·1-6(RAG)에 흡수 가능 |
| 딥리서치·브라우저 자동화·A2A | A07/A08/X04, X06, A03 | 설비 판단 경로 아님 |

## 표 2 · 가져오면 안 되는 것

| 대상 | 이유 |
|---|---|
| ProcessGPT 제품 전체 스택 기동(`process-gpt-infra-docker` compose, 실제 completion 엔진 구동) | LiteLLM 뒤 유료 LLM 키·서비스 35개 전제, 제품 구동은 "미검증" 경계로 남김(DECISIONS 101) — 24회차 대응표 설명으로 |
| IoT·SCADA 층 제품 교체(Flink+ONNX·EdgeX·Kafka Connect·Alertmanager·MinIO) | DECISIONS 106으로 닫힘(현 구조 유지, 24회차 비교 설명) |
| 실설비 SCADA 액션·버튼 직접 제어 | meeting-2 L425-430 "노티까지만, 직접 제어는 현장", HANDOFF §3 절대 규칙 |
| 모바일 푸시(FCM)·모바일 앱 | Firebase 외부 계정(`process-gpt-k8s` fcm-service, X01) |
| K8s·KEDA 배포 | 단일 호스트 compose 강의 환경(REFERENCE_ADOPTION C06) |
| 결제(X02)·OpenAI Realtime 음성(A09) | 유료 결제·유료 API, 요구 없음 |
| B4 코드 파서 + LLM 혼합 추출 | A119 재현성 비교로 "하지 않음" 판정(DECISIONS 101) |
| computer-use Pod 셸(T08) | k8s 의존, PLC 경로 확대 금지 |
| Neo4j → ontological-db 교체(O03/O04) | UNION·FOREACH·shortestPath 미지원으로 감사가 거짓 통과 |
| 전면 래스터화 VLM OCR(T05) | 텍스트 레이어로 10/10, VLM 호출 비용 |

## 표 3 · 작은 것(참고만)

- 동의어 배열·동의어 검색(T06, B8 선택)
- 빈 페이지만 OCR 분기(T05)
- 포털에 거래 before/after 노출(DECISIONS 97 후속)
- DMN draft 판본 데이터 모양(P04 `database.py:959-1050`) — 표 1-3에 포함
- 60초 넘는 간격 대기 구간 표시(P01 `timeline_service.py:301-310`) — 표 1-8에 포함
- 분기 조건 변수의 선행 활동 출력 검사(D01)
- 실행 전 MCP 점검(T04, 후보에서 내림)
- HWPX/DOCX 매뉴얼 변환기(T03, 요구 0건)
- seed 뒤 되읽기 단언(O04)
- Measure leading/lagging kpiRole(D02, 전문가 결정)
- 선례 사유 텍스트 유사검색(P02)
- 포털 골든 퀘스천 보고 표시(O01 후속)
- 실행 중 취소·결과 파일 칩·인용 위치 단계 등 이미 반영된 세부(A097·A117·A119)

## 1차 추천 5개 (모두 강의 가치 상)

1. **데이터 패브릭(표 1-1)** — 두 회의가 모두 "기본 모델 다음 확장"으로 지목했고 meeting-2 L438-447은 이것을 과정의 자연스러운 다음 이야기로 말했다. 학생은 원천이 늘어도 온톨로지가 "어디에 있는가"를 가리키는 디렉터리 역할을 하는 것을 직접 보게 된다. (HANDOFF §2 확정 방향 변경이 먼저 필요)
2. **자연어·문서 → 프로세스 정의 생성(표 1-4)** — "프로세스를 자유롭게 바꾸려면 ProcessGPT가 필요하다"(L448)를 말이 아니라 실행으로 보여 주는 회차가 된다. 이미 B5로 제품 모양 정의를 받으므로 크기 대비 효과가 가장 크다.
3. **피드백 → 규칙·스킬 개선 제안(표 1-3)** — 회의 첫머리의 6계층 중 마지막 층(사고를 남겨 향후 피드백, L7-8)이 지금은 선례 읽기에서 멈춰 있다. 사례가 규칙 개정안이 되고 사람이 승인해 판단이 바뀌는 순환을 보면 에이전트·규칙·사람의 역할 분담이 완성된다.
4. **What-if 상충 시뮬레이션(표 1-5)** — 대표가 10-01에 직접 든 환율·부품가·품질 예시가 그대로 레포(`what-if-simulator`)에 구현되어 있다. 6회차의 정적 영향 사슬이 "바꿔 보면 어떻게 되나"의 실험으로 이어져 온톨로지를 왜 만드는지가 분명해진다.
5. **레거시 메타데이터 증강 → 카탈로그·리니지(표 1-2)** — 현장 DB는 이름이 코드이고 FK가 없다는 문제를 meeting-1 L30-42가 구체적으로 설명했고, ontologic spec 008이 바로 그 시나리오다. 9회차 인제스천이 깨끗한 DDL에서 끝나는 한계를 넘어 "사람이 승인하는 자동화"를 배운다.

차순위(상): 에이전트 경로 고착화(1-7), 하이브리드 RAG 라우팅(1-6).
