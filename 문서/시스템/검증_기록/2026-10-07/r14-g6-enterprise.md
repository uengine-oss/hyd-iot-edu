# 6조 업무 DB·RPC·MCP / DMN·사람 질문 / 배포 구성 — 레포 3개 (HEAD: wms 8ba09f44 07-31 · agent-utils 5dbd7e0b 03-31 · infra-docker 9e854852 10-06)

읽기 전용으로 진행했다. 바꾼 파일은 이 보고서 하나다. 레포 쪽 경로는 `.evidence/reaudit/references-latest/<레포>`를 기준으로 하고, HYD 쪽 경로는 `D:\work\study\hyd-iot-edu` 기준 상대경로로 적는다.
같은 커밋을 읽은 r13 group5(D05)·group9(X07)·group1(C05) 기록도 출처를 밝히고 재사용한 부분이 있다. 이번에 새로 따라간 흐름은 아래 세 가지다.
- wms: MCP 도구에서 DB 명령까지 (`create_rfq`→`_call_rpc`→`classify_error`, codegraph trace)
- HYD: `exec_skill`/`exec_compensation` 최신본(마이그레이션 019·020)과 `entsim` 백엔드 2종, `cards.evaluate`, `dmn-mcp`, worker lease(018)
- 제품 쪽 결정론 DMN 평가기 2곳 (vue3·completion. 비교 근거로만 읽었다)

## 결론 먼저
1. **infra-docker 10-06 변경은 작업 점유 lease 하나뿐이다.** `docker-compose.yml`과 서비스 gitlink는 그대로다(diff -rq와 ls-tree 결과 0건). HYD는 이 lease를 A097(마이그레이션 018)로 이미 들여왔지만 **세 군데가 다르고, 그중 둘은 레포 쪽이 맞다.**
   - (a) 레포는 `claim_count`를 **회수할 때만** 올린다(init.sql:2821-2824). HYD는 FB_REQUESTED·사람 답변으로 다시 집을 때도 매번 +1 한다(018:51, procdb.py:307).
   - (b) 레포는 lease를 쓰지 않는 점유 경로에서 `lease_until`을 NULL로 비운다(init.sql:2559-2564). HYD의 `legacy_assessment.claim`은 lease가 붙는 `fetch_pending_task`로 집으면서 연장을 하지 않는다(legacy_assessment.py:57).
2. **업무 실행 RPC는 wms 구조(스키마 분리·봉투·원장)를 따랐다. 멱등은 HYD 쪽이 더 강하다.** wms MCP는 키를 안 주면 새 uuid를 만들고(mcp_server.py:168), wms 자체 BPMN 지시문도 키를 넘기지 않는다(install_processgpt_integration.py:216). 그래서 재실행하면 RFQ가 중복 생성된다.
   반대로 **입력 검증·행 잠금은 레포 쪽이 낫다.** HYD `exec_skill`은 asset·supplier가 실제로 있는지 확인하지 않는다(019:53-70, 테이블에 FK 없음 enterprise.sql:112-121). `exec_compensation`은 대상 행을 `for update` 없이 읽고 조건 없이 갱신한다(020:39-43).
3. **DMN은 HYD 자체 설계다(박용주 v2, DECISIONS 12).** agent-utils의 DMN 도구는 LLM이 서술하는 방식이라(dmn_rule_tool.py:252-308) HYD가 따르지 않은 것이 맞다.
   다만 이전 기록에는 "제품 DMN은 LLM 도구"라고만 적혀 있다. 실제 제품에는 결정론 FIRST 평가기도 있다(vue3 ProcessGPTBackend.ts:2277-2295, completion regression/dmn_replay.py:253-271).
   HYD 내부에도 불일치가 하나 있다. 그래프에 선언된 hitPolicy(`dt:rank-actions`=PRIORITY, instances.cypher:407)를 코드가 읽지 않는다. 코드는 "정확히 1개가 맞아야 함"(UNIQUE)으로 동작한다(cards.py:134-135).

---

## process-gpt-sample-app-wms (8ba09f44 2026-07-31, 스냅샷 대비: 동일 — a066/r13이 같은 커밋을 읽음)

### 이 레포가 하는 방식 (흐름 순서)
- **진입: BPMN 정의.** `install_processgpt_integration.py:106-136`
  - serviceTask 하나가 `tool: "mcp:<도구>"` 하나에 대응하고, checkpoint는 "정확히 1회 호출"이다.
  - userTask(HITL)는 폼으로 처리한다(:139-168, 승인 :228-235, 품질 :263-270).
  - 게이트웨이는 `approval_decision == 'APPROVED'` 조건으로 갈린다(:296-297).
- **MCP 도구 (FastMCP, stateless streamable HTTP).** `mcp/main.py:7-19`
  - 예: `create_rfq`(mcp_server.py:149-175) → `_call_rpc`(:39-47) → `client.rpc(...)` → 오류는 `classify_error`(client.py:143-148)로 넘어간다.
  - 오류 봉투는 `{result:error, error_kind, http_status_equivalent, message}`이고, CONFLICT 409 / FORBIDDEN 403 / INVALID 422 / UNKNOWN 500으로 나뉜다(:93-100).
  - 성공하면 `{result:ok, document_id, status, version, next_actions}`를 돌려준다(:170-173).
  - 쓰기 도구에는 `dry_run`이 있다(:160-163).
  - 작은 결함: `get_authed_client()`가 try 바깥에 있어서(:40) 로그인이 실패하면 봉투가 아니라 원래 예외가 그대로 나간다.
- **식별 3종.** client.py:5-15, config.py:34-63
  - PROCESS_AGENT, WCS_GATEWAY, AUDITOR 셋 다 실제 Supabase 사용자로 로그인한 anon 키 클라이언트다. 그래서 RLS·역할 검사가 사람과 똑같이 적용된다.
  - service_role 키는 테넌트 자동 준비(:67-116)에만 쓴다.
- **명령 RPC.** `wms_create_rfq`, core_schema.sql:347-401
  1. 멱등 기록을 먼저 조회하고, 있으면 저장된 응답을 그대로 반환한다(:365-369). 입력 비교는 하지 않는다.
  2. 창고 범위를 확인한다(FORBIDDEN, :371-373).
  3. `has_role`로 역할을 확인한다(:374-376).
  4. 입력과 마스터 데이터를 검증한다(INVALID: qty, unknown sku, :377-384).
  5. INSERT 후 `audit_events`에 after를 남긴다(:390-391).
  6. `idempotency_records`를 `on conflict do nothing`으로 저장한다(:394-398).
  - 승인 RPC는 PURCHASE_APPROVER/WMS_ADMIN만 허용하고, `expected_version`이 맞지 않으면 CONFLICT를 낸다(:403-439).
- **RLS.** :240-295
  - 모든 테이블이 SELECT만 허용한다(테넌트·창고 범위 함수 :201-233). 쓰기 정책이 없으니 쓰기는 SECURITY DEFINER RPC로만 가능하다(:241-244).
  - `idempotency_records`에는 select 정책도 없다(:287-288).
- **보상(역거래).** 계약표에는 `wms_cancel_rfq`·`wms_reverse_receipt`·`wms_cancel_purchase_order`·`wms_cancel_putaway_task`가 있다(docs/02-contracts.md:8-18). 하지만 **구현이 0건이다**(전체 SQL·py grep, mcp_server.py:9-11에 "compensate 미구현"이라고 적혀 있음).
  - 보상이 실제로 구현된 패턴은 뒤에 붙은 모듈의 `wms_cancel_*`다. 예: `wms_cancel_work_order`(wes_material_flow_control.sql:714-800)
    - 멱등 조회 :735-739, `for update` 행 잠금 :741, 범위·역할 확인 :745-750, version 확인 :751-753
    - 이미 종결된 상태면 INVALID :754-756
    - 연결된 설비 명령을 연쇄 취소 :758-769
    - before/after 감사 기록 :771-781, reason 저장 :774
- **배포.** docker-compose.yml:1-33
  - wms-mcp와 frontend 두 서비스뿐이고, Supabase는 넣지 않았다(기존 SaaS를 쓴다). healthcheck와 depends_on도 없다.
  - MCP 등록 형식은 `{type:url,url,transport:streamable_http}`다(docs/03-processgpt-integration.md:18-35).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 스키마·RLS | wms 스키마, 사용자·역할·창고 범위 SELECT RLS | `ent` 스키마, anon/authenticated `using(true)`(enterprise.sql:302-320), 전용 로그인 역할 `hyd_enterprise_reader` default read only·5 s(reader.sql:3-21) | 구조는 같고 범위는 다름 | 단일 테넌트 교육용이다. HYD는 DB 역할 차원에서 읽기 전용이 보장되어 더 강하다. 단, anon도 `ent.transactions`의 before/after까지 전부 읽을 수 있다(:304) | 아니오 |
| 쓰기 경로 | 에이전트가 쓰기 MCP 도구를 호출하고 DB가 역할로 거부 | 에이전트에게 쓰기 도구가 없다(enterprise-mcp server.py:20-22). process가 승인을 받은 뒤 `/api/exec`를 호출(main.py:663-686)해 `ent.exec_skill`(service_role만, reader.sql:25-26)을 실행 | 다름 | 의도된 설계(enterprise.sql:7)다. 에이전트가 오작동해도 쓰기는 불가능하다 | 아니오 |
| 멱등 키 | 호출자가 주는 uuid. 없으면 새로 생성. 입력이 달라도 같은 키면 캐시 반환 | 서버가 정하는 (decision, skill) 키에 fingerprint를 비교하고, 다르면 23505(019:32-40). 보상은 (decision, skill, ref)(020:27-35, 015 인덱스) | 다름 | HYD가 더 강하다(재실행·재전송에도 중복이 생기지 않음) | 아니오 |
| 재생 응답 모양 | 첫 실행과 같은 캐시 jsonb | `exec_skill`의 재생 응답은 `decision_id/option_id/requested_by` 키를 쓰고 첫 응답은 `decision/option/by`를 쓴다(019:38 vs :104-105). 보상은 키를 맞춰 준다(020:33) | 다름(HYD 내부 불일치) | 소비자(main.py:682-684)는 ref·detail만 읽으므로 영향 없음. 단, entsim 로그의 `tx.get("decision")`(main.py:132)은 재생 때 None으로 찍힌다 | 예(작음, 019:38 한 줄) |
| 입력·마스터 검증 | unknown sku면 INVALID(core:381-384) | asset·supplier 존재 확인이 없다. 없는 supplier id는 `coalesce(v_sup_name,v_sup)`로 이름 칸에 들어간다(019:65-70) | 다름 | 지금 호출자는 온톨로지 값만 넘기므로 실제 발생은 낮다. DB 계약으로는 약하다 | 예 |
| 오류 분류 | 접두사 문자열 4종 → 409/403/422/500 | SQLSTATE 22023/23505 → entsim이 메시지를 보고 409/400을 정한다(main.py:126-130). memory 백엔드는 같은 충돌을 ValueError로 내서 **400**이 된다(state.py:91). DB 연결 오류도 400 | 다름 | 호출자가 코드별로 분기하지 않는다(main.py:394, :685). 지금은 무해하지만 백엔드마다 응답이 다르다 | 예(작음) |
| 보상 | 계약만 있고 핵심 슬라이스는 미구현. `cancel_*`는 잠금·version·reason·연쇄 처리 | 4종 정확한 역거래, 생성 상태일 때만(020:38-68), 되돌릴 수 없는 3종은 사람이 확인(state.py:28-30) | 부분 | HYD에는 행 잠금·reason 저장이 없다 | 예(잠금) |
| 감사 before/after | `audit_events` before/after(core:168-179) | A103: `ent.transactions.before/after`(019:4-7, 020) | 같음 | — | 완료 |
| 낙관적 동시성 | `expected_version` CONFLICT | 없음. 대신 상태 전제조건과 승인 직전 재검사 | 다름 | 쓰는 주체가 하나다 | 아니오(r13 보류 유지) |
| MCP 봉투 | 모든 도구를 try/except로 감싸 봉투 반환 | `query`·`describe_catalog`만 감쌌다(server.py:80-97). 이름 있는 읽기 7개(:32-71, tools.py:46-54)는 감싸지 않아 DB 장애 시 FastMCP 예외가 나간다 | 부분 | 에이전트가 오류 모양을 일관되게 받지 못한다 | 예(작음) |
| HITL 승인 | userTask 폼 + WMS 화면 + DB 역할 거부 | process 승인 API와 역할 검사(DECISIONS 12 "카드 선택의 역할 검사 403") | 다름 | 의도된 차이 | 아니오 |

### 이전 주장 판정 (REFERENCE_ADOPTION D05 행)
- "봉투 `{result, document}`·식별 분리·mcpServers 모양 동일" → **맞음.** tools.py:27-33 = mcp_server.py:93-100·114, reader.sql:3-26, docs/03:22-30.
- "멱등성은 HYD가 더 강함" → **맞음이지만 불완전.** wms는 키가 없으면 새로 만들고(mcp_server.py:168, 156 설명), 자체 BPMN 지시문도 키를 넘기지 않는다(install:216). 그래서 제품 흐름에서는 serviceTask를 재실행하면 실제로 중복이 생긴다. 차이가 기록보다 크다.
- "후속 후보: `ent.transactions`에 before/after jsonb" → **이미 반영돼 행이 낡았다.** A103 마이그레이션 019(exec_skill)·020(exec_compensation)에 들어가 있고, entsim 두 백엔드도 같다(supabase_backend.py:53-60, state.py:93-99).
- "has_role·expected_version·AUDITOR는 판별 대상 없음 → 보류" → **맞음.** 판단 근거가 그대로다.
- r13 group5 #7 "enterprise-sim은 메시지에 idempotency가 있으면 409" → **불완전.** Supabase 백엔드만 그렇고, memory 백엔드는 400이다.
- hyd_counterparts → **불완전.** `it/enterprise-sim`과 `procsvc/main.py exec_skill`이 빠져 있다(r13에서도 지적함).

### 읽지 않은 것
- `mcp_server.py` 300-3856(도구 95개 본문)
- 마이그레이션 10개 본문(r13과 같은 경계). `20260805/06`은 r13이 읽은 범위를 재사용했다.
- frontend, openspec
- HYD `hydcommon/enterprise.py`·`sql_read.py`(guard 본문)

## process-gpt-agent-utils (5dbd7e0b 2026-03-31, 스냅샷 대비: 동일)

### 이 레포가 하는 방식
- **`DMNRuleTool`.** dmn_rule_tool.py
  - 초기화할 때 `proc_def(type=dmn, owner=user_id)`를 읽어 온다(:79-90).
  - 질문 키워드로 규칙 이름을 찾고, 없으면 전체 규칙을 쓴다(:120-131).
  - DMN XML을 파싱해 input/output/rule 조건 문자열을 뽑는다(:172-246). **`hitPolicy` 속성은 읽지 않는다.**
  - gpt-4o에 "질문 분석·규칙 매칭표·최종 결과" 마크다운을 쓰게 한다(:252-308). 키가 없거나 실패하면 규칙을 나열하는 것으로 대신한다(:352-400).
  - 즉 **실행 엔진이 아니라 서술기**다. codegraph로 확인한 레포 안 호출자는 0개다(외부 소비자용 export).
- **`HumanQueryTool`.** human_query_tool.py
  - 질문 스키마는 `role/text/type(text|select|confirm)/options`다(:27-32).
  - sha256 signature로 같은 질문의 이전 답을 다시 쓰거나, 아직 답이 없으면 기존 job을 기다린다(:103-162).
  - 질문은 `events(human_asked)`에 저장하고 알림을 남긴다(:179-210).
  - 응답은 **180초 동안 5초 간격으로 폴링**하고, 시간이 지나면 "사용자 미응답 거절"을 반환한 뒤 그대로 진행한다(:221-247).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| DMN 평가 | LLM 서술, hitPolicy 무시 | 결정론 `cards.evaluate`(cards.py:153-238). 구조화 TESTS AND(:35-62), 알 수 없는 사실은 UNKNOWN으로 경고·제외(:194-203). LLM 0회 | 다름 | DECISIONS 12에서 결정함 | 아니오 |
| hitPolicy | 읽지 않음 | 그래프에 선언(instances.cypher:404-407: diagnose PRIORITY, candidates COLLECT, compliance COLLECT, rank PRIORITY)했지만 **코드에서 hitPolicy를 쓰는 곳이 없다**(it/ *.py grep 0건). 순위는 "정확히 1개 일치"(cards.py:134-135) | HYD 내부 불일치 | PRIORITY 선언을 믿고 순위 규칙을 하나 더 넣으면 판정 FAILED(decide.py:249-253) | 예 |
| 진단 결정표 | — | `dt:diagnose-cause` 규칙은 적재되지만 실행되지 않는다. 진단은 `card.rank_causes`의 prior×증거 가중치로 한다(card.py:21-50). 그런데 dmn-mcp 지시문은 이 결정표를 "실제 사실에 대어" 판단한다고 쓴다(server.py:17) | 설명과 코드 불일치 | 에이전트·수업 설명이 틀어진다 | 예(문구나 데이터) |
| 사람 질문 | role/type/options, 180초 뒤 거절하고 진행 | `__human_input__{question,options}`(hitl.py:17-37). DB HUMAN_ASKED로 멈추고 답이 오면 FB_REQUESTED로 재개(instances.py:603-628). 출처는 process-gpt-cli-agent(hitl.py:1) | 다름 | HYD는 기한 없이 기다리고 내구적이다. agent-utils의 시간 초과 후 진행은 HYD 정책과 반대(r13과 같은 판단) | 아니오 |

### 이전 주장 판정 (X07 행, r13 group9)
- "human_query·database·deterministic 본문 대조 — 공통 결과 계약 없음, 채택 없음" → **맞음.**
- REPO_GAP.md:77과 DECISIONS 12의 "제품 DMN = LLM 도구(후반 설명)" → **불완전.**
  - 제품에는 결정론 평가기가 있다: vue3 `executeBusinessRule`(ProcessGPTBackend.ts:2277-2295, FIRST 일치 :2285, 조건 :2361-2394), completion `regression/dmn_replay.py`(FEEL 단항 :75-101, FIRST :253-271, 일치 없으면 -1).
  - HYD는 A056에서 감지 패턴용으로 dmn_replay를 이미 대조했다(HANDOFF.md:469). 하지만 L8 카드 DMN의 근거 문장은 고치지 않았다.
  - 결정 자체(HYD 엔진 유지)를 뒤집을 사실은 아니다. FIRST 표 하나로는 여러 카드 후보·규정·순위를 표현할 수 없다.
- JSON `hyd_counterparts: []` → **불완전.** `it/dmn-mcp`, `agentsvc/cards.py`, `agent-worker/worker/hitl.py`(대조 대상)를 적어야 한다.

### 읽지 않은 것
- `knowledge_manager.py`, `a2a_client_tool.py`, `image_manager.py`
- `safe_tool_loader.py`·`deterministic_code_tool.py` 본문(r13 group9 재사용)

## process-gpt-infra-docker (9e854852 2026-10-06, 스냅샷 754751629c 대비: 변경 — DB 점유 lease 하나)

### 10-06 변경 (diff -rq 결과: `volumes/db/init.sql`, `volumes/db/migration.sql`, `tests/lease/*` 신규 2,439줄. compose·gitlink는 동일)
- `todolist.lease_until`(NULL = 회수 대상 아님)과 `claim_count`(init.sql:454-459)를 추가했다. migration.sql:2589-2616에는 인덱스 `idx_todolist_lease_reclaim`도 있다.
- `fetch_pending_task(..., p_lease_seconds DEFAULT NULL, p_max_claims DEFAULT 3)`(:2753-2832)
  1. 상한에 닿은 만료 행을 먼저 FAILED로 끝낸다(:2769-2779).
  2. 만료된 STARTED이면서 count<상한인 행을 회수한다(:2794-2804).
  3. **`claim_count`는 회수일 때만 +1, 새 작업이나 FB_REQUESTED는 1로 되돌린다**(:2821-2824). 피드백을 주고받은 작업이 상한을 먹지 않게 하려는 것이다.
- `renew_task_lease`는 jsonb와 함께 사유를 돌려준다: `not_owner`(버린다) / `not_started`·`missing`(heartbeat만 멈춘다)(:2834-2890). `release_task_lease`도 추가됐다(:2892-2917).
- **lease를 쓰지 않는 다른 점유 RPC는 `lease_until`을 NULL로 비운다**(:2559-2564, :2674-2679). 과거 시각이 남아 있으면 다른 워커가 회수해 같은 작업을 두 번 수행하기 때문이다.
- 값은 lease 120 s, heartbeat 30 s, 상한 3이다. heartbeat는 별도 OS 스레드에서 돈다(tests/lease/README.md:44-50, 63-73).
- 권한은 `anon`에게 GRANT다(:2919-2921).

### 배포 구성 (compose 불변, 이번에 다시 셈)
- 서비스 **35개**, healthcheck **16개**, `condition:` 11개. 나머지 depends_on은 조건 없는 목록이다(예: polling-service :119-122).
- Supabase 11종을 직접 띄우고 LiteLLM·nginx가 있다. cli-agent·codex 서비스는 없다. deepagents 이미지는 `:24fbdd4`로 고정돼 있다(gitlink 동일).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| lease 열·회수·상한 | init.sql:2753-2832 | 018:6-55(claim_process_workitems에 내장), FAILED는 엔진 sweep에서 처리(018:69-87, main.py:169-176) | 의미 같음 | FAILED를 정하는 위치만 다르고 결과는 같다 | 아니오 |
| claim_count 누적 | 회수일 때만 | 워커가 집을 때마다 +1(018:51, procdb.py:307). 사람 답변·교정 재작업은 FB_REQUESTED로 다시 집힌다(instances.py:626, :393) | **다름** | 첫 실행 뒤 피드백 2회를 거치면 count=3이 된다. 이 상태에서 워커가 죽으면 회수 없이 바로 FAILED(018:30·77) | **예** |
| NULL lease | 회수하지 않음 | 마이그레이션 때 기존 STARTED에 now+120 s를 부여(018:10-12) | 다름 | 구버전 워커와 새 DB가 함께 도는 경우가 없다(단일 compose 동시 교체). 무해 | 아니오 |
| 다른 점유 경로 | lease_until NULL | `legacy_assessment.claim`이 `fetch_pending_task`로 집는다(legacy_assessment.py:57). 그러면 lease 120 s가 붙지만 renew는 runner.py:181에만 있다. 전달 재시도(:177-181, 최대 60 s 간격)가 이어져 120 s를 넘기면 cliagents 워커가 같은 행을 회수할 수 있다. .env.example:27-29는 legacy와 cliagents를 같이 켜는 구성을 허용한다 | **다름** | 잠재적 이중 수행이다(추측, 실측 안 함) | **예** |
| renew 사유 | not_owner / not_started 구분 | boolean. false면 무조건 Cancelled(018:58-66, runner.py:181) | 다름 | 실행 중 not_started가 될 경로는 사람 취소뿐이라 버려도 맞다 | 아니오 |
| heartbeat 스레드 | 별도 OS 스레드 | CLI 출력은 펌프 스레드가 받고, `check_stop`은 25 ms마다 호출된다(process_control.py:119-124) | 동등 | — | 아니오 |
| 권한 | anon GRANT | service_role·authenticated(018:88-91) | 다름 | HYD 쪽이 낫다 | 아니오 |
| 배포 | 35 서비스 직접 구동, 의존 조건 적음 | 23 서비스, healthcheck 15, condition 28. Supabase는 외부 `supabase start`(wms compose:1-6과 같은 선택), LiteLLM 없음 | 다름 | 교육용 경량 구성. 의존·헬스 조건은 HYD가 더 엄격하다 | 아니오 |

### 이전 주장 판정 (C05 행, r13 group1)
- "`fetch_pending_task` 본문 동일(이미 채택)" → **최신 기준으로 틀림.** 10-06에 lease 인자와 회수 로직이 붙어 본문이 달라졌다. HYD는 agent-sdk판(e4728a2)을 A097로 따랐으나 claim_count 규칙과 다른 경로 처리가 다르다.
- "서비스 37개·healthcheck 14개"(r13 group1:8) → **수치 틀림.** 같은 파일을 다시 세어 보니 35개·16개다(Supabase 11종).
- "LiteLLM·Supabase 자체호스팅·nginx는 HYD에 불필요" → **맞음.**
- 018 머리말의 "agent-sdk e4728a2 function.sql lease_until/claim_count/max_claims를 따른다" → **불완전.** agent-sdk function.sql:102-105도 회수할 때만 누적한다. 헤더가 말하는 출처와 구현이 다르다.

### 읽지 않은 것
- `tests/lease/run_bench.sh` 1,048줄, `worker.py`, `test_lease_rpc.sql` 본문
- kong.yml, init.sql의 lease 밖 DDL
- HYD `procdb.py` 290-310 이외 범위

---

## 출처 판정
| HYD 기능(파일:줄) | 출처 | 맞는 레포의 방식(파일:줄) |
|---|---|---|
| ent 스키마·RLS·읽기 역할(enterprise.sql:8·302-320, reader.sql:3-29) | 맞는 레포 따름(wms) + 범위 축소 | core_schema.sql:201-295 |
| 업무 실행 RPC `exec_skill`(019:9-106) | 맞는 레포 따름(wms 원장·봉투) + **HYD 고안**(jsonb 디스패처 하나, (decision,skill) 키) | wms 명령별 RPC core_schema.sql:347-401 |
| 역거래 `exec_compensation`(020:5-80, state.py:20-31) | **다른 레포 빌림**(completion compensation.py 원칙, state.py:21·effect_compensation.py:3) + HYD 고안. 업무 쪽 정답 레포는 wms인데 핵심 보상은 미구현 | wms `cancel_*` wes_material_flow_control.sql:714-800 |
| 오류 코드(entsim main.py:122-130, enterprise-mcp tools.py:31-33) | wms 어휘 부분 차용(2/4종) + HYD 고안(메시지 문자열 매칭) | client.py:134-148, mcp_server.py:93-100 |
| enterprise-mcp 도구·봉투(server.py, tools.py) | 맞는 레포 따름(wms-mcp). `query` 자유 SELECT는 회의 6번에 따른 HYD 추가 | mcp_server.py:103-145 |
| 승인·HITL(process 승인 API, 에이전트 쓰기 없음) | HYD 고안(DECISIONS 12, 회의 L430) | wms userTask+폼 install:228-235, DB 역할 거부 core:421-423 |
| 사람 질문 `__human_input__`(hitl.py:17-37, instances.py:603-628) | 맞는 레포 따름(process-gpt-cli-agent hitl.py). agent-utils는 crewai용이라 해당 없음 | agent-utils human_query_tool.py:103-247(대조용) |
| DMN 평가 `cards.evaluate`/`rule_fires`(cards.py:35-62·153-238), dmn-mcp | **HYD 자체 고안**(박용주 v2, DECISIONS 12). agent-utils를 따르지 않음 | 제품 결정론: vue3 ProcessGPTBackend.ts:2277-2295·2361-2394, completion dmn_replay.py:75-101·218-271 (FIRST) |
| 카드 순위(cards.py:110-136, hydcommon.ranking) | HYD 자체(A069, 회의 L385-404) | 이 조 레포에 대응 없음 |
| guardrail(guardrail.py:8-71) | HYD 자체 | 대응 없음 |
| 시간 앵커(017) | HYD 자체(회의 L75-79) | wms는 원래 timestamptz로 저장 — 방향 같음 |
| worker lease(018, procdb.py:43-44·297-307, runner.py:176-181) | 맞는 레포 따름(agent-sdk·infra-docker)이지만 **규칙 2곳 다름** | init.sql:2559-2564·2753-2890 |
| compose 배포(compose.yaml) | HYD 자체(L1~L9). Supabase 외부는 wms와 같음 | infra docker-compose.yml(전체 스택), wms docker-compose.yml:1-33 |

### 빌림·자체 고안 항목의 나란히 비교
1. **exec_skill (HYD 디스패처 + 서버 멱등 키) 대 wms 명령별 RPC.**
   - 정확성: 레포가 낫다. 마스터 존재 확인 INVALID가 있다(core:381-384). HYD는 019:53-70에서 확인하지 않는다.
   - 재현성·실패 시 복구: HYD가 낫다. 키를 서버가 정하고 fingerprint로 거부한다. wms는 키가 없으면 새로 만들어 중복이 생긴다.
   - 속도·비용: 비슷하다.
   - 수업 재현: 레포가 낫다. 명령마다 계약이 보인다.
   - **판정: 멱등은 HYD가 낫다. 입력 검증은 레포가 낫다.** 바꿀 범위: 새 마이그레이션 1개로 `exec_skill`에 asset(ent.assets)·supplier(ent.suppliers) 존재 확인을 넣는다(22023, 약 20줄). 019:38 재생 키도 함께 맞춘다. `tests/test_entsim_backends.py`에 사례 2개를 추가한다. 약 1~2시간.
2. **exec_compensation 대 wms cancel_*.**
   - 정확성·실패 시 복구: 레포가 낫다. `for update`(:741)로 잠그고 종결 상태를 거부한다(:754). HYD는 select 후 조건 없이 update해서(020:39-43) decision이 다른 동시 취소 2건이 둘 다 통과할 수 있다(추측, 호출자는 process 하나).
   - 재현성: 비슷하다. 둘 다 멱등이다.
   - 수업: 비슷하다.
   - **판정: 레포 쪽이 낫다(작음).** 범위: 020의 4개 분기에 `for update`를 넣거나 `update ... where status=<생성 상태>`로 바꾸고 영향 행 수를 확인한다. 마이그레이션 1개, 약 1시간. reason 저장은 선택이다.
3. **오류 코드.**
   - 정확성: 레포가 낫다. 일시 장애(UNKNOWN 500)와 입력 오류가 구분된다. HYD는 DB 장애도 400이고 백엔드마다 409/400이 다르다.
   - 복구: 지금 호출자는 코드를 보지 않으므로 같다.
   - **판정: 비슷하다(현재 무해).** 백엔드 불일치만 고치면 된다. state.py에서 충돌을 별도 예외로 내고 main.py에서 409로 매핑. 30분.
4. **DMN (HYD 그래프 TESTS 엔진) 대 제품 FIRST 평가기.**
   - 정확성: HYD가 낫다. UNKNOWN을 경고·제외로 드러낸다(cards.py:194-203). 제품은 입력이 없으면 조용히 불일치로 처리한다(ts:2369-2392 `Number(undefined)` 비교 false).
   - 재현성: 같다. 둘 다 결정론이다.
   - 속도·비용: 같다. LLM 0회다.
   - 실패 시 복구: HYD가 낫다. 규칙 trace와 policy_sha256가 남는다(:211·220).
   - 수업: 레포가 낫다. 표준 DMN 표·FIRST라 설명이 쉽고 화면 편집기가 있다.
   - **판정: HYD 쪽이 낫다.** 단 HYD 내부 불일치 2건은 고쳐야 한다. (a) instances.cypher:404·407의 hitPolicy를 실제 동작(rank=UNIQUE)에 맞추거나, cards가 선언을 검사하게 한다. (b) dmn-mcp server.py:17의 "dec:diagnose-cause 결정표 적용" 문구를 실제 동작(prior×증거)에 맞춘다. 데이터·문구 수정, kg-seed 재적재, 30분~1시간.
5. **사람 질문·승인(HYD 고안) 대 wms·agent-utils.**
   - 정확성: HYD가 낫다. 쓰기 권한이 아예 없다.
   - 복구: HYD가 낫다. DB에 기한 없이 대기한다.
   - 수업: 비슷하다.
   - **판정: HYD 쪽이 낫다.**
6. **worker lease (따랐으나 규칙 다름).**
   - 정확성: 레포가 낫다. 피드백을 몇 번 오가도 회수가 막히지 않고, 다른 경로 행이 이중 수행되지 않는다.
   - **판정: 레포 쪽이 낫다.** 범위: (a) 새 마이그레이션으로 `claim_process_workitems`의 claim_count를 `case when w.draft_status='STARTED' then +1 else 1`로 바꾸고, procdb.py:307 메모리 저장소도 같은 규칙으로 맞춘다. 시험 1개(FB_REQUESTED 2회 뒤 워커 사망 → 회수). 약 1시간. (b) legacy_assessment.claim 직후 `lease_until`을 NULL로 비우거나 legacy tick 안에서 renew한다. 1~3줄과 시험 1개, 약 1시간.

## 조 요약
| 레포 | 핵심 차이 | 맞춰야 할 것 | 이전 기록 오류 |
|---|---|---|---|
| sample-app-wms | 쓰기는 HYD가 process 전용, 멱등은 HYD가 강함. 입력 검증·행 잠금·오류 4분류는 레포가 강함 | exec_skill 존재 검증 + 재생 키 통일, exec_compensation 행 잠금, MCP 이름 읽기 봉투, entsim 409 통일 | D05 "후속 후보 before/after"는 A103으로 이미 반영됨(행 낡음). 멱등 차이를 과소평가(wms 키 자동 생성으로 사실상 무효). r13 "409" 기록은 Supabase 백엔드만 해당 |
| agent-utils | DMN이 LLM 서술 → HYD가 따르지 않은 것이 맞음 | HYD hitPolicy 선언과 코드 불일치, diagnose 결정표 문구 | REPO_GAP:77·DECISIONS 12 "제품 DMN = LLM 도구"는 불완전(vue3·completion에 결정론 FIRST 평가기 있음). X07 hyd_counterparts 비어 있음 |
| infra-docker | 10-06 lease 추가(compose 불변) | claim_count를 회수할 때만 누적, legacy 점유 경로 lease 정리 | C05 "fetch_pending_task 본문 동일"은 최신 기준 틀림. 서비스 37·헬스 14 → 35·16. 018 헤더의 출처 주장이 구현과 다름 |
