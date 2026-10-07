# A113 참고 레포 재확인 종합 — "맞는 레포를 따랐나, 빌렸나, 지어냈나" (2026-10-07)

**왜 했나.** 사용자가 "온톨로지 인제스천이 ontology-studio 방식과 같은가"를 물었고, 이전 기록("studio엔 분할 로직이 없다")이 키워드 검색만 본 오류였음이 드러났다. 사용자 기준: 위험한 것은 버전 차이보다 **그 부품에 맞는 레포가 있는데 다른 레포 방식을 가져왔거나 HYD가 지어낸 것**이고, 돌아가더라도 **적대적으로 어느 쪽이 나은지** 판정한다.

**어떻게 했나.** HYD 부품마다 기준 레포 24개를 최신 HEAD로 받아(`scripts/refs_latest.sh`, `.evidence/reaudit/references-latest/heads.tsv`) codegraph로 색인하고, 6개 조가 병렬로 "진입 → 흐름 → 저장 → 화면" 순서로 읽었다(공통 지시 `.evidence/reaudit/a113/brief.md`). 조별 보고서: `r14-g1-engine.md`·`r14-g2-frontend.md`·`r14-g3-agent.md`·`r14-g4-ontology.md`·`r14-g5-metadata.md`·`r14-g6-enterprise.md`. 아래 ✔ 표시는 조의 주장을 메인 세션이 코드·실행으로 다시 확인한 것.

**스냅샷 이후 바뀐 레포(전부 10-06):** process-gpt(openspec lease·human-input 명세 2건 추가), process-gpt-vue3(질문 필드·재개 패치 4파일), agent-sdk(v0.10.1 lease.py·renew/release), infra-docker(DB lease 함수), deepagents(샌드박스 env 화이트리스트 제거→TENANT_ID만, 도구 필터), codex·cli-agent(SDK pin만). 나머지 15개는 스냅샷과 같고 robo-data-catalog·neo4j-text2sql은 처음 받음.

## A. 레포 쪽이 낫고 작게 고칠 수 있는 결함 (바로 고침)

| # | 결함 | 레포 방식 | 확인 | 범위 |
|---|---|---|---|---|
| A1 | **임대 횟수(claim_count)를 사람 답변 뒤 재집기에도 +1** → 질문이 두 번 오간 작업은 워커가 한 번 죽으면 회수되지 않고 FAILED | agent-sdk `function.sql:102-105`·infra-docker `init.sql:2821-2824`: 회수(STARTED)일 때만 +1, 그 외 1 | ✔ 018:51·procdb.py:307, MemoryRepo 재현(답변 3회 뒤 4 → 한 번 죽자 FAILED) | 마이그레이션 1 + MemoryRepo 1줄 + 시험, 1~2시간 |
| A2 | 연장 중 DB 예외 1회로 살아 있는 실행을 실패 처리, 회수당함과 이미 끝남을 구분하지 않음 | agent-sdk `lease.py:163-170`(예외는 다음 주기 재시도), `renew_task_lease`가 not_owner/not_started 구분 | 3조 | runner check_stop + renew 반환 이유, 반나절 |
| A3 | **CLI 선택 키** — 제품 화면은 `agent_cli`에 저장, HYD 워커는 `cli`/`agent`만 읽어 Codex 지정 정의가 말없이 Claude Code로 실행 | cli-agent `selection.py` `_AGENT_KEYS=("agent_cli","agentCli","cli_agent","cliAgent")`, vue3 `AgentSelectField.vue:327` | ✔ runner.py:81 | 한 줄 + 시험 |
| A4 | **Codex 경로 비밀 잔존** — 실행 뒤 `.mcp.json`만 비우고 `codex-mcp.toml`의 서버 env(Neo4j 비밀번호 등)는 72시간 남음 | cli-agent RuntimeLease(실행 뒤 원복) | ✔ bridge.py install(toml에 env 기록)·cleanup(.mcp.json만) | cleanup 확장 + 시험, 1~2시간 |
| A5 | 비밀 차단이 블록리스트라 `*_TOKEN`·`*_API_KEY`가 자식 프로세스로 감 | deepagents 최신: TENANT_ID만 전달(docker_sandbox.py:216-218) | ✔ env_guard.py:10-12 | 접미사 추가(필요한 키는 keep), 1시간 |
| A6 | **게이트웨이 없이 갈라졌다 다시 만나는 흐름이 등록을 통과하고, 합류 활동이 두 번 실행됨**(한 가지가 먼저 끝나 합류 활동이 완료된 뒤 다른 가지가 끝나면) | bpmn-extractor `process_validator.py` `uncontrolled_split`, bpmn-process-generation-skill | ✔ g1_probe 재현(D DONE 뒤 D 재생성), g1_probe2 등록 통과 | 등록 규칙 + 재작업 시험 정의 조정, 0.5~1일 |
| A7 | 보상 함수가 대상 행을 잠그지 않고 읽은 뒤 갱신, `exec_skill`이 asset·supplier 존재를 확인하지 않음, 재생 응답 키가 첫 응답과 다름 | sample-app-wms `cancel_*` `for update`, `INVALID: unknown sku` | ✔ 020:39-43(select 후 update, 잠금 없음) | 마이그레이션 1~2, 2시간 |
| A8 | legacy 평가 경로가 lease 붙는 fetch로 집고 연장하지 않음 → 120초 넘으면 다른 워커가 같은 행을 회수할 수 있음(미실측) | infra-docker 10-06: lease 안 쓰는 경로는 NULL | 6조 | 1시간 |
| A9 | 에이전트 SQL 작성 규칙(스키마 먼저·없는 열 금지·수정 2회·실패를 0으로 바꾸지 않기)이 시험 지시문에만 있고 작업자 상시 지시에 없음 | neo4j-text2sql 고정 규칙·수정 루프 | ✔ workspace.py CONSTITUTION에 없음, probe_codex_sql_repair.py:24-28에만 | 지시문 5~6줄, 반나절(실측은 LLM 비용 → 확인 후) |
| A10 | DB 컬럼 주석만 바뀌면 그래프에 옛 의미가 남음(드리프트 상태가 OK/MISSING/TYPE_CHANGED뿐), 형식 매핑이 부분 문자열이라 `interval`이 `int`로 잡힘 | HYD 자체 결함(레포에도 없음) | ✔ ddl_sync.py:22-23·ingest.py:30 | COMMENT_CHANGED + 매핑 수정, 반나절 |
| A11 | 판단 규칙: 그래프에 PRIORITY로 선언한 hitPolicy를 코드가 읽지 않고 "정확히 하나" 로 동작, 진단 규칙(dec:diagnose-cause)은 실행되지 않는데 dmn-mcp 안내문은 적용한다고 씀 | DMN 표준(hit policy 준수) | ✔ cards.py:134-135, instances.cypher:410, dmn-mcp server.py:17 | 선언·동작 일치 + 안내문 정정, 반나절 |
| A12 | 사람 질문 카드가 `text`만 읽음(SDK 에이전트는 `question`) | vue3 10-06 `humanQuestionText` | 2조 | 한 줄 |

## B. 레포 쪽이 낫지만 구조를 바꾸는 일 (사용자 결정 또는 별도 작업)

| # | 무엇 | 판정 근거 | 범위 |
|---|---|---|---|
| B1 | **매뉴얼 인제스천 결과를 파일로 받기** — 분할이 필요했던 진짜 원인은 결과를 LLM 마지막 메시지 JSON으로 받는 출력 경로(A092 160 KB). studio는 파일로 쓰고 경로로 적재 | 4조, ontology-studio `batch_ingest(파일 경로)` | `worker/outcome.py`·`workspace.py`·`manual_extraction.py`, 1~2일 + 재실측(HM-FULL3 약 80분, EHU40 약 15분) |
| B2 | 원문 인용 위치를 서버가 찾기(에이전트는 `{page, quote}`만) — EHU40 1차 교정 2회의 원인 | memento `citations.py:203-248` | 0.5일 |
| B3 | 문서별 골든 퀘스천 보고 — HYD Q01~Q22는 그래프 전체 연결 감사라 "이 문서로 이 질문에 답할 수 있나"를 보지 않음 | studio `ontology_build_report{question,status,confidence}` | 0.5~1일 |
| B4 | 구조는 코드, 절차 의미는 LLM(패턴 A+B 혼합) — 실험: 정규식 파서는 EHU40 장·절 구조는 맞췄으나 절차 37개 중 8개 | 4조 실험(`.evidence/reaudit/a113/g4exp`) | 2~3일, 사용자 결정 |
| B5 | **에이전트 활동 유형** — HYD는 `businessRuleTask`, 제품·D01은 userTask + agentMode. 제품 폴링은 businessRuleTask를 처리하지 않아 정의가 서로 실행되지 않음 → "ProcessGPT 그대로"라는 수업 설명과 어긋남 | ✔ completion `polling_service.py:72-76`, D01 | 등록 규칙·engine·manual_extraction·schema·정의 v2.2, 약 1일 |
| B6 | 업무 프로세스 화면 BPMN을 실제 정의에서 그리기(지금은 손으로 그린 고정 그림이라 정의 2.1의 규정 검토·책임자 호출·선택 시간초과·회복 분기가 없고 정의에 없는 "판단 사례 기록"이 있음), 레인은 에이전트·담당자·시스템 | ✔ hitl.js:11-27 vs 정의 2.1 활동·이벤트·게이트웨이 | 1~2일, UI/UX 작업에 편입 |
| B7 | 인스턴스 상세(한 페이지 13섹션, 내부 원문 노출) → 탭·접기, 이전 단계 입력을 라벨 붙은 읽기 전용 폼으로, 상태 이름·색(TODO "할 일"이 "내 할일"과 겹침, SUBMITTED "검토 요청" 오해, 칩 전부 회색), 이상 확인 탭의 결정 버튼(서버가 409) 제거 | ✔ ui.js 상태 이름, main.py `_require_legacy_incident` 409 | UI/UX 작업에 편입 |
| B8 | InputData 동의어(용어→컬럼), 스캔 문서 OCR, 매뉴얼 본문 검색 | 5조·4조 | 선택, 사용자 결정 |

## C. HYD 쪽이 나아서 유지

- 엔진: 경계 타이머를 기한 저장 + 폴링으로 발화(제품은 cron에 등록하지 않음), 작업 집을 때 인스턴스 잠금, 3회 실패 시 PENDING(제품은 DONE으로 덮어씀), 안 탄 가지·경계 짝 취소, 폼을 정의 판본에 고정, 재작업 의존 범위·세대·변수 복원(설명은 제품 방식이 쉬움).
- 에이전트: 사람 질문(`__human_input__`)과 DB 기준 재개, 보류(`__deferred__`), 긴 지시문 파일 전달(제품은 8,000자에서 자름), MCP를 부모 설정에 붙이기(차이 무해, 출처 표기만 정정).
- 업무 DB: 멱등 키를 서버가 (decision, skill)로 정하고 입력이 다르면 거부(wms는 키가 없으면 새로 만들어 재실행 시 중복), 에이전트에 쓰기 권한이 없는 승인 구조.
- 메타데이터: DDL 투영(지금 규모에서는 배치 단위 되돌리기·규칙 입력 직결이 analyzer식 TABLE/COLUMN 그래프보다 낫다), DDL 드리프트 감지(analyzer에 없음), SQL 검사(text2sql보다 엄격), BSC 상충 계산(strategy에 없는 기능).
- 온톨로지: 결정적 id·소유권 충돌·되돌리기·스키마 강제 검증, 구간 분할 자체는 bpmn-extractor보다 낫다(그쪽은 SOP 경계 판정을 앞 30쪽에만 함 — 코드 기준 추론).
- 프론트: 폼 렌더러(빌드 없는 정적 포털), 실시간 스트림(`tool_use_id` 짝 맞추기).
- 판단: DMN 결정론 평가·카드 순위(제품의 결정론 평가기보다 모르는 입력을 드러내고 여러 카드 순위를 냄).

## D. 고칠 기록 오류 (REFERENCE_ADOPTION 등)

- **O01**(A112): studio "수 초·동일 결과"·"청크 검색으로 근거" → 틀림(빌드는 에이전트 991초/361초, 노드 수가 에이전트마다 다름; `hybrid_search_chunks`는 연결 안 됨). 골든 퀘스천 "추가 구현 불필요" → 틀림(목적이 다름). — `ontology-studio-latest-ingestion.md` 정정 완료.
- **T02**: "청크→병합 대응(참)" → 불완전(개념만 같고 수치·규칙은 HYD 자체). `manual_segments.py` docstring 출처 과장. `instances.py:372` 교정 3회의 출처 "product process_validator"는 제품 기본 5회·대상도 다름.
- **O02**: ontologic specs 004·005(agent-bridge, 패턴 A~D)가 공개 코드보다 앞서 있음, bpmn-extractor pin 8156f77 ≠ 대조한 c7992ce.
- **A05**(r13 group6): 서브에이전트 정의 생성을 "해당 없음"으로 분류 → 틀림(제품의 유일한 MCP 연결 경로). HYD가 출처로 든 `core/bridge.install`은 제품에서 호출되지 않음. selection.py 미열람으로 키 불일치 누락.
- **A01**: "샌드박스 env 화이트리스트" → 최신 HEAD에서 낡음, HYD env_guard는 처음부터 블록리스트.
- **A096/A097**: "실행 종료 시 env 제거"는 Codex 경로에서 불완전, "agent-sdk lease 반영"은 횟수 규칙·예외 처리에서 불완전, 018 머리말 출처 표기 과장.
- **T04**: "실행 전 MCP 점검"은 제품 방식이 아님(제품은 설정 화면에서 검증기 호출).
- **X08**: llm.py의 출처 "process-gpt-utils model_factory"는 없는 모듈 → process-gpt-llm-factory.
- **A04**: Codex 모델 서버 설정 출처(process-gpt-codex config.py:569-586) 미기록.
- **C01**: lease는 메타 DB가 아니라 SDK에서 옴, 새 openspec 2건 미기록.
- **C02**: 실행 중 취소 근거 `FormWorkItem.vue:954-964` → 실제 멈춤은 `AgentMonitor.vue:68`·`stopTask:1217-1229`(A097 결론은 유효). 포털 문구 "나에게 배정된 IN_PROGRESS 작업"은 틀림(사용자 필터 없음).
- **C03**: "정적 연결성 검사 4종" → 3종(uncontrolled_split 제외), "병렬 합류 보류"는 A100으로 낡음.
- **C05**·r13 group1: "fetch_pending_task 본문 동일"은 10-06 이후 틀림, 서비스·헬스체크 수 재집계 35·16.
- **C07**: "A097 반영, 실측 6/6" → 불완전(A1, 답변 뒤 재집기 시험 없음).
- **D01**: 정적 검사 반영 불완전, businessRuleTask와 UserActivity 차이 미판정.
- **D05**: "후속 후보 transactions before/after"는 A103으로 낡음, 멱등 차이 과소 기재, enterprise-sim 대응 누락. **X07** hyd_counterparts 비어 있음.
- **P01**: 후보에 60초 넘는 간격의 대기 구간 표시 추가, analytic 조회 SQL의 f-string 주입 위험 기록.
- **P03**·`bsc-conditions.md:56`·A070: strategy `age_adapter` 262~347을 BSC 경로 근거로 인용 → 과함(일반 link/unlink, strategy에 상충 계산 없음) → "HYD 자체 고안".
- **A067**(채택표 머리말): "catalog 계약을 읽고 구현" → 불완전(catalog는 투영하지 않음, 투영 원본은 robo-data-analyzer, 미대조).
- **HANDOFF.md:94** text2sql 설명 불완전(그래프를 만들지 않고 읽기만, ReAct 아닌 고정 controller, 그래프 구조가 현 catalog/analyzer와 다름). **REBUILD.md:39** "README만 읽음" 낡음. **REPO_GAP:77·DECISIONS 12** "제품 DMN = LLM 도구" 불완전(제품에도 결정론 평가기 있음; HYD 엔진 유지 결정은 그대로).
- r13 group5 "충돌이면 409"는 Supabase 백엔드만(메모리 백엔드는 400).

## 읽지 않은 범위(조별 보고서 끝에 상세)

completion LLM 조건 판정 체인·block_finder, deepagents executor.py 본문 대부분, wms mcp_server.py 300행 이후, vue3 Chat·EventTimeline·BpmnUengine 내부, robo-data-analyzer 최신 HEAD(로컬 체크아웃 일부만), HYD LLM 추출의 반복 재현성(실측 없음).
