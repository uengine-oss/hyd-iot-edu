# B4 — 흐름 판본 배포 · 기준 흐름으로 되돌리기 · 기준 비교 + 선례 고정 (확정 TODO B4, DECISIONS 110 ②·④)

작업 단위 B4, 2026-10-08 밤. 브랜치 `worktree-b4-deploy`(기준 3f6c9c0). U4 커밋 `820116e`(브랜치 `worktree-agent-aa019e15ad24e961f`, 합치지 않았던 것)를 체리픽해 재기반하고(충돌은 `index.html` 한 곳 — A5 셸 자리와 스크립트 줄을 둘 다 살림), 마이그레이션을 `20261008000028` → **`20261008000044`**로 바꿨다. U4 문서 `u4-deploy.md`는 그대로 두고 번호만 고쳤다(이 문서가 최신).

## 원본(참고) 파일:줄 · HYD 차이

| 원본 | 내용 | HYD |
|---|---|---|
| process-gpt-vue3 `src/components/ProcessDefinitionVersionManager.vue:84`(반영 요청 버튼) · `:314`·`:455-463`(`getProdVersion` → "반영 버전" 표시) · `:479`(`onClickRequestDeployment` → 반영 요청 프로세스) | 정의별 반영(운영) 판본 하나 · 반영은 결재 흐름 | `proc_def.prod_version` = 운영 포인터, 배포는 사람·사유 필수 API 한 번(결재 흐름 없음 — 수업 범위). 차이 있음, 유지 |
| `src/components/api/PalModeBackend.ts:22,478-487` | `proc_def.prod_version` 열을 반영 판본으로 읽음 | 같은 열 이름·뜻 |
| `src/utils/bpmnDiff.ts:24,265-271` | added / removed / modified + 항목별 전·후 | `definition_diff.py` 같은 모양(JSON 정의를 직접 비교) |
| (제품에 없음) 경보 패턴 → 흐름 | ProcessGPT는 트리거가 정의를 부름 | HYD는 경보 하나 = 처리 건 하나이므로 `alertPolicy.patterns`로 패턴별 배포 흐름을 고른다(아래) |

## 만든 것

### 1. 배포(U4 재기반) — 운영 판본 포인터 · 이력 · 배포/되돌리기/판본 비교
U4 내용 그대로(`definition_diff.py`, `instances.py` `deployed_definition`·`definition_status`·`deploy_definition`·`rollback_definition`·`compare_definitions`, `instance_mode.py` 라우트 `GET/POST /api/process/definitions/{id}/versions|compare|deploy|rollback`, `_bootstrap_definition`, 포털 `definitionDeploy.js` 관리 패널, `tests/test_definition_deploy.py` 8개). A1~A11 합침 이후 코드와 충돌 없음(`instances.py`·`instance_mode.py`·`procdb.py` 자동 병합, 시험 통과).

### 2. 경보 → 흐름: 패턴별로 "지금 배포된 흐름" (`it/process/procsvc/flow_deploy.py` 신규)
- `InstanceRuntime.alert_policy(pattern)` → `flow_deploy.route_definition` → `alert_policy.for_definition(raw, pattern)`(기존 계약). 규칙:
  1. 배포 API로 배포된 학생 흐름(마지막 배포 기록 `deploy`/`rollback`) 중 메시지 시작 + `alertPolicy.patterns`에 그 패턴 → 여럿이면 최근 배포.
  2. 없으면 기준 흐름 `anomaly_response`의 운영 판본. 모르는 패턴은 그 정의의 `unsupported`(사람 검토 alert_triage).
- 열린 처리 건은 자기 판본(열 때 `proc_def_id`·`proc_def_version` 고정) — 원천 접수 재처리도 접수 당시 정책.
- 학생이 기준 id의 새 판본(`anomaly_response@2.3-…`)을 배포해도 되고(포인터 이동), 다른 id의 흐름(B3 가져오기)을 배포해도 된다(패턴 가져감).
- **기준 흐름으로 되돌리기** `POST /api/flows/deploy-reset {by, reason?}`: 학생 흐름 `withdraw`(포인터 null, 등록 판본은 남음) + 기준 흐름 운영 판본 → 기준 판본(기동 파일 판본, `reset`). 이미 기준이면 `already_reference: true`. 이름은 B3의 `POST /api/flows/reset`(학생 정의 삭제)과 겹치지 않게.
- `GET /api/flows/deployments` — 패턴 → 흐름·판본 표, 학생 흐름별 `opens`/`shadowed`, `at_reference`.
- `GET /api/flows/deploy-compare?definition=&version=` — 학생 판본 vs 기준 판본(`anomaly_response@2.2`)의 바뀐 단계·연결 목록(`steps`) + 요약.
- 안전장치: 마지막 기록이 `seed`(기동·마이그레이션 백필)인 흐름은 경보를 가져가지 않고, 기준 id의 마지막 기록이 `seed`면 기동은 파일을 따른다 — 옛 "마지막 등록" 포인터(백필)가 조용히 경보를 가로채거나 기동 정의를 바꾸지 않게.
- 저장소: `procdb.deployed_heads`(배포된 정의 + 마지막 배포 시각·action, Pg는 `left join lateral`), `clear_deployment`(withdraw). 마이그레이션 044: `version` null 허용(withdraw만), action에 `reset`·`withdraw`.
- 기준 보호: `rt.reference_ids = {anomaly_response, alert_triage}`, `rt.base_version = 파일 판본`(`instance_mode.build`). 판본 원문은 불변 등록이라 학생이 기준 판본을 고칠 수 없다.
- 포털(관리 → 흐름 판본 배포 패널, `definitionDeploy.js`): "경보 → 흐름 (지금 배포된 것)" 카드(패턴 한국어 이름 · 흐름 · 판본 · 기준/내가 배포한 흐름) + **기준 흐름으로 되돌리기**(확인 대화상자), 판본마다 **기준과 비교**.

### 3. 선례 고정(교육용)
- 실제 Cypher 위치: `it/neo4j/templates/t3_precedents.cypher` — agent(`agentsvc/tools/mcp_kg.py:69-70` `precedents` → `t3_precedents`)와 dmn-mcp(`it/dmn-mcp/dmn_mcp/tools.py:153-154` → 같은 `mcp_kg.KnowledgeGraph`, Dockerfile이 같은 `it/neo4j/templates`를 `/srv/templates`로 복사)이 **같은 파일**을 쓴다 → dmn-mcp `precedents` 도구도 같은 기준(도구 설명에 한 줄 추가).
- 한 줄 조건: `WHERE dc.seeded = true` + 바로 위 주석 "교육용 고정: 시드 선례만 센다. 이 조건을 빼면 승인할 때마다 선례가 쌓이는 학습(제품 동작)이 켜진다 — DECISIONS 110 ④". 점수식(`cards.py` `precedent_share`·랭킹 정책 `1.5 * precedent_share`)은 그대로, `cards.py` 선례 계산 위에 출처 주석 한 줄.
- 시드 식별 근거: `it/neo4j/v2/instances.cypher` §7 "운영 기록 (예시 — 선례 질의 시연용)" `case:demo-1..3`(`inc:demo-1..3`), 투영된 사례(`procsvc/case_projection.py` `DECISION_CASE_Q`)는 `source_incident_id`가 있고 `seeded`는 쓰지 않는다(시험으로 고정). `scripts/cleanup_residue_cases.py` 머리말도 같은 구분("Seeded demo precedents (case:demo-*, no source_incident_id)").
- id 접두사 대신 **명시 속성** `seeded: boolean`: `schema.json` DecisionCase에 속성 추가(설명 포함) → `python scripts/ontology_v2.py gen`으로 `ontology-schema.ttl`·`schema_prompt.md` 재생성(다른 생성물 변화 없음), 시드 MERGE에 `c.seeded = true`, `seed_checks.cypher`에 "seeded 사례 0건이면 실패" 한 줄, 예시 질의 `queries.cypher` q10에도 같은 조건, `docs/ontology/schema-v2.md` 선례 문단에 고정 설명.
- 포털: 카드의 "과거 같은 선택 N건 (x %)" 옆에 "미리 넣은 예시만 반영(교육용 고정)"(`ui.js` `card.precedentFixed` 한 곳, `enterprise.js` 표시 한 곳).

#### 실행 중 그래프 반영 방법(메인)
`kg-seed`는 멱등(MERGE + SET)이고 agent·dmn-mcp가 그 완료에 의존하므로, 합친 뒤 `docker compose up -d`(또는 `docker compose --profile knowledge run --rm kg-seed`)이면 `case:demo-1..3`에 `seeded = true`가 들어간다. 손으로만 넣으려면:
```cypher
MATCH (c:DecisionCase) WHERE c.id IN ['case:demo-1','case:demo-2','case:demo-3'] SET c.seeded = true RETURN count(c);   // 3
```
**템플릿은 이미지에 복사**되므로 agent·dmn-mcp 이미지를 다시 빌드해야 새 조건이 적용된다. 반영 전(템플릿만 새것, 그래프는 옛것)이면 선례가 0건 → 선례 몫 0으로 순위가 바뀔 수 있으니 순서: 그래프 반영 → agent·dmn-mcp 재빌드·재기동.

## 바꾼 파일
- 신규: `it/process/procsvc/flow_deploy.py`, `it/process/procsvc/definition_diff.py`(U4), `it/portal/www/definitionDeploy.js`(U4+B4), `it/supabase/migrations/20261008000044_definition_deployment.sql`, `tests/test_definition_deploy.py`(U4), `tests/test_flow_deploy.py`, `tests/test_precedent_fixed.py`, 이 문서, `docs/handoff/verification/2026-10-08/u4-deploy.md`(U4, 번호만 수정).
- 수정: `it/process/procsvc/instances.py`, `instance_mode.py`, `procdb.py`, `it/portal/www/index.html`(관리 패널 + 스크립트 한 줄), `it/portal/www/enterprise.js`·`ui.js`(문구 한 곳), `it/agent/agentsvc/cards.py`(주석), `it/dmn-mcp/dmn_mcp/server.py`(도구 설명), `it/neo4j/templates/t3_precedents.cypher`, `it/neo4j/v2/{schema.json,instances.cypher,seed_checks.cypher,queries.cypher,ontology-schema.ttl,schema_prompt.md}`, `docs/ontology/schema-v2.md`, `docs/definition-authoring.md`, U4가 고친 `docs/curriculum-75h.md`·`docs/sessions/README.md`·`docs/sessions/16-…md`·`scripts/probe_definition_versions.py`.

## 시험
- `tests/test_flow_deploy.py` 7개: 학생 흐름 배포 → 다음 PUMP 경보는 학생 흐름(이름 '내 원인 진단'), 쿨러는 기준, 배포 전에 열린 건은 `anomaly_response@2.2` 유지 · **일부러 깨뜨리기**(U4처럼 기준만 보는 라우터로 바꾸면 계약 위반이 잡힘) · 되돌리기(withdraw + reset, 감사 2종, 다음 경보 기준, 등록 판본·열린 학생 건 유지, 두 번째는 already_reference, 재기동 파일) · seed(백필)만 있는 흐름은 경보를 못 가져감 + 기준 id 백필은 기동을 못 바꿈 · 같은 패턴 두 흐름이면 최근 배포가 이기고 가려진 패턴 표시 · 기준 비교 단계 목록 · HTTP(deployments·deploy-compare 404·deploy-reset 422/200·start).
- `tests/test_precedent_fixed.py` 6개: 투영 질의가 seeded를 쓰지 않음 · 템플릿 WHERE 줄과 바로 위 교육용 주석 · 시드 선례 반영(쿨러 2종 각 1건, 펌프 1건 — 실제 instances.cypher에서 읽음) · 같은 경보 25번 반복 승인해도 선례 불변 · **일부러 깨뜨리기**(WHERE 줄을 빼면 26건으로 늘어 잡힘, 모르는 조건은 시험이 거절) · 카드 순위·선례 몫 불변(반복 승인 20건), 학습을 켜면 선례 몫 변화(0.75 → 1.42).
- U4 `tests/test_definition_deploy.py` 8개 통과.
- 전체 `.venv/bin/python -m pytest -q`: **1529 passed, 1 skipped**(198 s).
- `node --check` definitionDeploy.js · enterprise.js · ui.js 통과.

## 메인이 라이브로 확인할 것 (합친 뒤, 이 순서)
1. 마이그레이션 044 적용 → `select id, prod_version from proc_def; select action, proc_def_id, version, previous_version, actor from proc_def_deployment order by created_at;` — 백필 seed 행. process 재기동 로그 `instance mode: definition anomaly_response@2.2`, `GET /api/process/mode`의 `deployed_version = 2.2`, `GET /api/flows/deployments` → `at_reference: true`, 세 패턴 모두 기준 흐름.
2. **선례 고정 반영**: kg-seed 재실행 → `MATCH (c:DecisionCase {seeded:true}) RETURN c.id`(3건), agent·dmn-mcp 재빌드·재기동. 그다음 **쿨러(HYD-01 COOLER_DEGRADATION)·펌프(HYD-02 PUMP_LEAKAGE)·팬(HYD-03 FAN_VIBRATION) 1순위가 합치기 전과 같은가** — 판단 화면 또는 `scripts/scenario_instance_test.py`·`scenario_pump_fan_test.py`의 1순위 단언. 카드의 "과거 같은 선택 N건" 값: 쿨러 fan-max-derate·derate-night-clean 각 1건(50 %), 펌프 switch-standby-pump 1건(100 %), 팬 없음. 옆에 "미리 넣은 예시만 반영(교육용 고정)". 지금 라이브 그래프에 회귀 잔재 DecisionCase(A155 미적용)가 있으면 합치기 **전** 1순위가 잔재에 기대고 있었을 수 있다 — 달라지면 `scripts/cleanup_residue_cases.py`(목록만)로 잔재 수를 같이 적는다.
3. 같은 쿨러 경보를 2~3번 승인한 뒤 다시 판단 → 선례 몫·순위 불변. dmn-mcp `precedents(fm…)` 도구 결과도 시드 건수만.
4. 흐름 배포: 포털 관리 → 흐름 판본 배포 패널. 기준 정의를 복사해 id `my_pump`·판본 `1.0`·`alertPolicy.patterns`를 `PUMP_LEAKAGE`만 남기고 단계 이름 하나 바꿔 등록(B3 가져오기가 합쳐졌으면 그것으로) → "기준과 비교"(바뀐 단계) → 담당자·사유 → "이 판본 배포" → 경보 표에서 펌프 = 내가 배포한 흐름. 펌프 결함 주입 → 처리 건 정의가 `my_pump@1.0`; 배포 전에 열어 둔 펌프 건은 `anomaly_response@2.2`로 끝까지; 쿨러 주입은 기준 흐름.
5. "기준 흐름으로 되돌리기" → 경보 표 모두 기준, 다음 펌프 경보 `anomaly_response@2.2`, 이력에 withdraw·reset. `docker compose restart process` 뒤에도 기준 유지.

## 남은 위험 · 메모
- 학생 흐름이 기준 흐름 단계(에이전트·작업지시 부품)를 그대로 쓰지 않으면 워커·legacy 다리(`task:diagnose` 등 활동 id 기반)가 처리하지 못할 수 있다 — 그건 B3 부품 매핑의 몫, 배포는 `validate_definition` 통과만 본다.
- B3가 `/api/flows/{id}` 같은 경로 매개변수 라우트를 먼저 등록하면 `/api/flows/deployments`·`deploy-compare`·`deploy-reset`과 겹칠 수 있다 — 합칠 때 라우트 순서 확인.
- B3가 학생 정의를 `isdeleted`로 지우면 Pg `deployed_heads`는 빠지지만, 메모리 저장소는 지우기 개념이 없다. 하나의 "기준으로 되돌리기" 버튼으로 묶을 때 순서는 deploy-reset → B3 reset.
- 학생이 기준 id(`anomaly_response`)로 새 판본을 배포한 상태에서 기동 파일을 바꾸면 배포가 이긴다(사람의 배포가 남는 것이 의도). 기준 판본(되돌리기 목표)은 항상 파일 판본.
- Pg 경로(`deployed_heads` lateral 질의 · `clear_deployment` · 마이그레이션 check)는 컨테이너 금지로 이 단위에서 실행하지 못했다 — 위 1·4·5가 그 검증.
- 선례 고정 뒤 순위는 시드 선례만으로 정해진다. 라이브 그래프의 투영 사례는 남지만(감사·KPI 역추적에 쓰임) 순위에 들어가지 않는다.
