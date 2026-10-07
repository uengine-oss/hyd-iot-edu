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
| C02 | 본문 대조 완료(스냅샷 d88f78c) | 주장 참(부분). 실행 중 에이전트 취소(`FormWorkItem.vue` L954-964, `draft_status=CANCELLED`)에 대응하는 HYD 포털 버튼/엔드포인트 없음 — 워커 `_cancelled`(runner)는 이미 감지 대기, `close_agent_task`는 PENDING·FAILED만. 위임·checkpoints 강제·DRAFT 초안 화면은 보류, 반송/되돌리기는 제품 백엔드도 미구현 | **A097 반영: `cancel_agent_task`·`POST /api/todolist/{wid}/cancel`·포털 "실행 취소"**. 근거 [r13-group4](verification/2026-10-07/r13-group4-C02-C03-C07.md) |
| C03 | 본문 대조 완료 | 주장 참. `engine.py` L87이 subProcess/callActivity를 허용하지만 실행 분기 0건 — 등록 경로(`definition_registry`)는 이미 거부하므로 파일 직접 로드에만 해당(기록). 제품의 `_process_sub_processes` L1188-1657·병렬/포괄 합류(`check_task_status` L3455-3646)·cron 중간 타이머·기한 계산은 현재 정의에 쓰임이 없어 보류. 제품의 3회 실패→DONE(polling_service L86-95)은 HYD PENDING이 더 맞음 | **A096: 정적 연결성 검사 4종을 등록 검증에 추가**(T02·D01 권고와 동일). 근거 r13-group4 |
| C04 | 현 경로 유지 | Spring 경로 재작성·MCP proxy 주소 → HYD compose/포털 | 게이트웨이 전체 이식·운영 인증 검증 없음 |
| C05 | 대조 완료·보류 | compose 890줄·.env.example·litellm·nginx·migrate-db·README 전부 열람. `fetch_pending_task`(init.sql L2705-2747)는 HYD 마이그레이션 L261-292와 본문 동일(이미 채택). 이 레포가 빌드하는 deepagents 이미지 `:24fbdd4`는 A01 스냅샷 1bf79e0의 조상 | LiteLLM·Supabase 자체호스팅·migrate-db·nginx upstream은 HYD 구조(직접 base URL·supabase CLI migrations·정적 포털)에 불필요. 미열람: kong.yml, init.sql DDL 본문. 근거 [r13-group1](verification/2026-10-07/r13-group1-C05-A01-A02.md) |
| C06 | 배포 보류 | Kubernetes 런너/MCP proxy/FCM 서비스 연결 → 운영 경계 대조 | 이미지 원본 일부 미확정; K8s 배포 없음 |
| C07 | 본문 대조 완료(스냅샷 58ca16d) | 주장 참이나 "stale 정리 같은 계약"은 절반 — HYD `cleanup_stale_consumers`는 엔진 SUBMITTED만 풀고 워커 STARTED 고아 회수 없음(스냅샷 SDK에도 없고 HEAD e4728a2에서 `lease_until/claim_count/max_claims=3`·`renew_task_lease`(function.sql L34-169, lease.py 120 s/30 s) 추가) | **A097 반영: `20261007000018_worker_lease.sql` lease_until/claim_count/max 3·renew 30 s·expire sweep, 실측 6/6(워커 사망→117초 뒤 회수→완료)**. 근거 r13-group4 |
| C08 | 배포 보류 | 대화 ID/agent type별 런너 프록시 진입 → workspace 비교 | resolve 후반 미열람; 호스트 워커 교체 근거 없음 |
| A01 | 대조 완료·격차 1건 반영(A095) | 주장 참(agent.py L120-227, 15파일 전부). 결정론 재실행+보상(replay.py L177-231)·입력 오프로드(L525-586)·HITL 체크포인터는 HYD가 dmn-mcp·effect_compensation·`_deliver_prompt`·DB 저장으로 대체. **격차: 샌드박스 env 화이트리스트(docker_sandbox.py L52-66)** — HYD 워커는 `SUPABASE_DSN` 등을 env로 갖고 cliagents `exec_env`가 `os.environ`을 복사해 Claude Code 자식 프로세스에 상속됨(직접 확인) → `worker/env_guard.py`로 설정 읽은 뒤 자기 환경에서 비밀 제거(A095) | 프레임워크 교체 근거 없음(서브에이전트 요구가 R표에 없음). 근거 r13-group1 |
| A02 | 대조 완료·격차 1건 반영(A095) | 강제 라우팅(L1265-1389)·옵션 elicitation(L1395-1678)·run 진입(L2456-2485) 열람, 주장 참. A02 HITL 상태는 프로세스 메모리 dict(executor L721/726, 재시작 유실) — HYD draft DB 저장이 더 강함. **격차: 작업별 MCP 서버 선택(executor L355-422)** — HYD `activity_capabilities`의 tools를 runner가 쓰지 않고 tenant_mcp 전체를 등록(직접 확인, 현재 정의 4종 tools 선언 0건이라 잠재) → `bridge.select_servers`로 선언 시 그 서버만 등록(A095) | 근거 r13-group1 |
| A03 | 런타임 보류 | AgentCard push 지원에 따른 webhook/sync 분기 → worker 이벤트 비교 | 외부 A2A가 필수라는 근거 없음; webhook 저장 미검증 |
| A04 | 현 경로 유지 | SDK 작업→런타임→폼/도구 이벤트 → outcome/provider 비교 | App Server로 정책 우회하지 않음; 새 Codex 미검증 |
| A05 | 본문 대조 완료(4475bf7) | 주장 참. 제품 astream은 exit code/stderr를 안 읽어 HYD `process_control`이 더 강함. 제품 RuntimeLease(실행 후 제공자 파일 복원, 테넌트 MCP 자격증명 사유)에 대응해 HYD는 `.mcp.json`에 서버 env 평문을 쓰고 72 h 보존했음 | **A096: `bridge.cleanup`으로 실행 종료 시 env 제거**(매 실행 install 재호출이라 재개 영향 없음). 보류: Journal·replay_limited, `_pause`가 remember() 반환값을 버려 알림 중복 가능(runner 244, 미실측). 근거 r13-group6 |
| A06 | 본문 대조 완료(7c7a392) | 주장 참. "최신 실행 차단"의 실체는 Codex 0.151 `exec resume` 플래그 순서(HYD codex_provider가 재배열). `exec_env`가 `os.environ`을 복사(A095 env_guard의 근거). 권한 거부 인식은 Claude 마커 4종 부분일치/Codex declined뿐(라이브러리 한계, HYD는 --allowedTools로 완화) | **A096: exit 0인데 stderr가 있으면 워커 로그에 꼬리 기록**(이전엔 버려짐). 근거 r13-group6 |
| A07 | 런타임 보류 | JSON→PromptMultiFormatFlow subprocess 진입 | 연구보고 플로 내부 미열람; 설비 판단 필수 경로 아님 |
| A08 | 런타임 보류 | task_record polling→run_deep_research 진입 | HYD 원문 검토/적재와 일반 연구보고를 구분 |
| A09 | UI 확장 보류 | WebSocket 사용자/대화→VoiceReactAgent 연결 | 음성은 현재 승인/현장제어 필수조건 아님 |
| T01 | 기존 대조 유지 | 문서 검색/메모리 스냅샷·과거 기록 재사용 | 이번 내부 코드 재열람 없음; 검색 품질 미결 |
| T02 | 본문 대조 완료(c7992ce) | 주장 참. A093/A094의 `manual_segments.py`(제목 경계 분할·결정적 병합·페이지 범위)가 제품 청크→병합(`test_chunk_integration`, 실 LLM+Neo4j 통합 시험)에 대응. 엔진 실제 실행 추적·LLM 교정·LLM SOP 경계·의미 병합·풍부한 HITL payload는 HYD 계약(사람 검토·고정 판본)과 달라 보류 | **A096: `process_validator` 527-625 정적 검사 4종 반영.** 남은 경계: 구간 경계에서 잘린 SOP 이어붙이기 없음(경고로만). 실측: 실물 EHU40 10/10(A094). 근거 r13-group6 |
| T03 | 런타임 보류 | office MCP 로드·이미지 편집 REST 진입 | 도구 전체 미열람; 문서/슬라이드 제작은 현 Goal 제외 |
| T04 | 검증 경계 참고 | initialize/list tools/timeout/partial → 기존 MCP probe와 비교 | 연결 성공은 도구 결과 정확성 증거 아님 |
| T05 | 대조 완료·OCR 경로만 후보 | formatter는 `final_output_pipeline.py:45-142`에 있음(참). 단 visionparser는 텍스트 레이어를 읽지 않고 모든 PDF를 400 dpi 래스터화+CLAHE 뒤 페이지마다 VLM OCR(`executor.py:670-681`), 다수결은 extraction_passes 기본 1회의 청크 간 최빈값(`executor.py:833-841`) — HYD는 pypdf 텍스트+빈 페이지 OCR_REQUIRED 차단(`manual_sources.py`), OCR 경로 0줄 | 채택 후보: 빈 페이지만 OCR로 채우는 `extract` 분기(추출기 태그 구분). 전면 래스터화는 채택 안 함(실물 PDF 텍스트 레이어로 10/10, A094). 근거 [r13-group2](verification/2026-10-07/r13-group2-T05-T06-T07.md) |
| T06 | 대조 완료·동의어 검색만 후보 | PostgreSQL `terms(status DEFAULT 'Draft', synonyms text[], batch_id)`+`term_owners/term_reviewers`(`10-app-schema.sql:45-74`) 참. **검토 권한 검사 없음**: `update_term_info`가 status를 누구나 Approved로 갱신(`glossary_manage_service.py:802-855`), 테넌트는 X-Tenant-Id 무검증·JWT 서명 미검증(`util/tenant.py:10-29`), 롤백은 batch_id DELETE(`bulk_service.py:1412-1435`) | 채택 후보: InputData 동의어 배열+동의어 포함 검색(R06). 상태·권한·롤백 모델은 HYD(`graph_ingest.clear` 복원·감사)가 더 강해 보류. 근거 r13-group2 |
| T07 | 대조 완료·채택 0 | description만 임베딩한 코사인 top-k(`search_engine.py:121-251`), 엔진은 권한 검사를 하지 않음(docstring 140-141), 문서는 read 시점 지연 fetch(`mcp_handlers.py:440-463`), 배치 10개 증분 색인(`http_server.py:2213-2238`) | HYD의 SOP 선택은 DMN 규칙 OUTPUTS 조인(`skill_graph.py`·`cards.py`)으로 대상이 다름 — 채택 없음. 근거 r13-group2 |
| T08 | 런타임 보류 | FastMCP→PodManager/Executor·TTL 초기화 | Pod shell 도입/PLC 경로 확대 근거 없음 |
| P01 | 대조 완료·보류 | 연결 주장 참(`main.py:18-32,111-115,260-287`). 고정 커밋 8308db5는 원격 main 이력에 없어 `git fetch <sha>`로만 도달. ETL은 60초마다 전체 테이블 UPSERT(워터마크 없음, `etl.py:1324-1389`), `etl_state`는 완료 시각/성공만이며 load 예외를 print로 삼켜 부분 실패도 success(`main.py:84-131`), fact_task가 비면 랜덤 샘플 삽입(`etl.py:1194-1321`) | HYD는 SSE 커서·투영 FENCE·`freshness{ok,age_s,max_age_s}`·승인 15초가 이미 더 강함. 후보는 LAG 윈도 식(`etl.py:1167-1188`)뿐. 근거 [r13-group3](verification/2026-10-07/r13-group3-P01-P04-D03.md) |
| P02 | 분류기 보류 | 신규 instance ingest·정의별 recluster 진입 | 클러스터와 확정 경보 패턴은 다름; ingest 내부 미열람 |
| P03 | 본문 대조 완료(1db85d3) | **주장 부분 틀림:** ontology_sync 계약을 실제 이식한 HYD 파일은 `ddl_sync.py`·`scm_sync.py`(docstring에 출처)이고 `knowledge_projection`은 그래프 내부 digest 재투영기. "소유권"은 제품에 없음(DETACH DELETE 삭제 216-223/324-336/409) — HYD graph_ingest/manual_graph 자체 설계. 제품 결함 1건(todolist 커서 전역 키 54/701/769 → 다중 테넌트 누락) | 제품 전용 로직 6개 비채택. 근거 [r13-group6](verification/2026-10-07/r13-group6-P03-T02-A05-A06.md) |
| P04 | 대조 완료·보류 | 배치 처리기는 DMN draft 판본+병합요청 생성 성공 여부로 applied를 돌려주나(`feedback_batch_manager.py:598-656`, 직접 확인) API 응답은 작업 생성 시점의 applied:true이고 처리 결과가 제안 GET에 실리지 않음(하위 조사 보고). 스킬 없음·커밋 예외를 "건너뜀"으로 정상 반환해 COMPLETED가 되는 경로(`skill_committer.py:155-157,197-206`, 직접 확인) | HYD `skill_graph.write`는 영수증·속성·관계를 한 트랜잭션, 같은 request_id=같은 결과, 불일치=409. 채택 후보: draft 판본 데이터 모양(`database.py:959-1050` is_draft·parent_version·source_todolist_id·requester_id[]·reviewer_id)을 R11 정의 변경 계약에 참고. 근거 r13-group3 |
| O01 | 본문 대조 완료(6a229be8) | 부분 참: "고정 스키마"는 제품 계약이 아니라 HYD 선택(제품은 실행 중 편집·rename→라벨 교체 `ontology/api.py:99-121`), "원문 근거"는 HYD 문자 앵커가 더 강함(제품은 sources 노드 id), "검증 루프"는 대상이 다름(제품 Golden Question 답 가능성 vs HYD 인용 WRONG/MISSING 재추출). 제품에 스키마 버전/이력 없음. 문서 청크 BM25+벡터 RRF는 제품에서도 미연결 | 조건부 후보: Golden Question 보고 형식 `{question,answer,status,confidence}`(R03), MCP 답변 `sources[]`+출처 없음 명시(R06). `ocr_service.py` 574줄은 T05와 함께 스캔 PDF 보강 시. 근거 r13-group5 |
| O02 | 연결 추적 유지 | 기존 15개 하위 경로 gitmodules/tree 추적 | 전체 패브릭 이식 아님; 지도 밖 catalog 후보 후속 |
| O03 | DB 교체 보류 | 기존 연구용 DB 스냅샷·조사 기록 유지 | 이번 내부 재열람 없음; Neo4j 교체 근거 없음 |
| O04 | DB 교체 보류 | Bolt listener/PostgreSQL 연결 설정 진입 | og_cypher 본문/성능/완전호환 미검증 |
| O05 | 구현 판단 보류 | 기존 확보 당시 빈 구현 기록 유지 | tree 재확인 전 현재 원격의 빈 레포로 단정하지 않음 |
| D01 | 본문 대조 완료(f8c4b6d5) | 부분 참: HYD registry는 스킬의 elements[] 형식이 아니라 `save_to_supabase.py:95-191 flatten()` 결과 형식을 받고, 폼은 D01 `form_def` 별도 테이블 vs HYD 판본 안 `forms`, 스킬(`skills[]`) 0건. 정적 연결성 4종(`process_validator.py:540-591`)은 HYD에 없었음(순환 금지+endEvent 존재만) | **A096: 정적 연결성 검사 반영.** 후속 후보: 분기 조건 변수가 선행 활동 outputData에 있는지 검사(`08-reference-info.md:63-80`). 실제 엔진 구동 검증+LLM 교정 루프는 HYD 불변 판본과 충돌해 보류. 근거 [r13-group5](verification/2026-10-07/r13-group5-D01-D05-O01.md) |
| D02 | 기존 대조 유지 | BSC 전략·상충 요구 스냅샷 유지 | 이번 본문 재열람 없음; 시스템 의미 연결 후속 |
| D03 | 문서 대조 완료·채택 0 | navigation은 ko에 셋 다, en은 dmn 없음(부분 참). rework.md는 "로그 역순 보상 자동 처리"+UI 절차만(효과 유형·불가 처리·세대 없음), reference-info.md는 C03 inputBindings UI, dmn.md는 승인/버전 없음, feedback-system.md는 P04 코드와 불일치 | HYD REWORK.md·CURRENT_APPROVAL.md가 원본 코드 대조로 더 깊음. 근거 r13-group3 |
| D04 | UI 확장 보류 | Vue router home/marketplace 연결 | 등록/실행 본문 미열람; 마켓플레이스 도입 요청 없음 |
| D05 | 본문 대조 완료(8ba09f44) | 주장 참(봉투 `{result, document}`·식별 분리·mcpServers 모양 동일). 멱등성은 HYD가 더 강함(제품은 같은 키면 입력이 달라도 캐시 반환 365-369, HYD는 fingerprint 불일치 거부) | **후속 후보: `ent.transactions`에 before/after jsonb**(제품 `audit_events` core_schema.sql:168-179; HYD는 detail text만, R10/R12). RPC별 has_role 게이트·expected_version CONFLICT·AUDITOR 전용 읽기는 HYD 권한 모델(service_role 한정)에서 판별 대상 없음 → 보류. 근거 r13-group5 |
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

## A092 추가 대조 (2026-10-07, 고정 커밋을 다시 받아 코드로 읽음)

| 레포(커밋) | 이번에 읽은 것 | HYD 대응과 남은 경계 |
|---|---|---|
| process-gpt-completion b272c9a | `polling_service/workitem_processor.py` 5,550줄의 활동 분기(subProcess·adHocSubProcess·callActivity·multiInstance foreach·parallel/inclusive/exclusive), `process_engine.py` rework/feedback 핸들러, 전체 4.7만 줄 | HYD 엔진은 사람/서비스/businessRule·배타·경계 타이머·재작업·보상까지. 서브프로세스·병렬·다중 인스턴스는 **없음** — 회의 요구(R11)는 "인스턴스/태스크 구조"라 필수는 아니나 ProcessGPT 동등성 주장에는 못 미침 |
| process-gpt-agent-sdk e4728a2 | `database.py` polling(lease·max_claims·browser-automation 분기), `processgpt_agent_framework.py` 서버 루프 | HYD 워커의 claim·stale 정리와 같은 계약(42/42). lease 갱신·여러 pod 동시 claim은 HYD 단일 워커라 미검증 |
| process-gpt-bpmn-extractor c7992ce | `pdf_extractor.py`(OCR 50쪽·SOP 경계 30쪽·청크 1000/200·의미 청크), `hitl.py` 728줄(pause_for_hitl→HUMAN_ASKED→FB_REQUESTED 재진입, 질문 payload·배치 응답), `process_validator.py` 1,315줄(엔진 실제 실행 추적 비교), `test_chunk_integration` 5종(청크 간 통합·역할 중복 제거·순서) | HYD는 통문서 1작업+문자 좌표 앵커+교정 3회. HITL은 같은 상태 전이(HUMAN_ASKED/FB_REQUESTED, A024)이나 질문 payload·배치 응답 계약은 단순. 분할·병합·엔진 실행 검증 없음. **대형 문서 실측은 HANDOFF A092** |
| ontology-studio 6a229be | `document_indexing/service.py` 878줄(OCR·토큰 청크 1200/150·임베딩·풀텍스트+벡터 인덱스·HAS_CHUNK), `agent_session/service.py` 1,786줄(히스토리 압축 12k 토큰) | HYD에 원문 청크·벡터 검색 없음(매뉴얼 원문은 SQLite 보관, 절/단계만 그래프). 회의 R02 "문서→인스턴스"에는 지금 구조로 답하지만 "매뉴얼 의미 검색"(SCADA 회전 기억)은 미구현 |

