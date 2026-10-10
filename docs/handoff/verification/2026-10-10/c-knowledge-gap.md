# 시나리오 C 지식 공백 — A정밀 추천 원인 추적 (2026-10-10)

작업 위치: merge-preview 워크트리. 라이브 실행 없음(정적 추적 · 단위 시험만). 증거 원본: `agent-afd136e4b22934cb9/.evidence/a161-c3/`
(`live/C-decision.json`, `ingest-PR-07.json`) — 이 워크트리에는 `.evidence/a161-c3/`가 없다.

**비유 한 줄**: 구매 기준서에 "불량이 잦은 공급사는 검사비를 더해 비교하라"고 적혀 있는데, 판단표에 '불량률' 칸이 없어서
AI도 사람 검토자도 그 문장을 표에 옮겨 적을 수 없었다. 게다가 검토 도장은 아무도 안 보고 찍혔다.

**스스로 판정할 체크 질문**
- 판단 기록의 카드 사실에 공급사 불량률이 숫자로 있고, 규칙 하나가 그 숫자를 시험하는가? (전: 없음)
- SOP-PUR-13(최단 납기)이 가리키는 공급사가 원문 1단계대로 "견적 중 리드타임이 가장 짧은 곳"인가? (전: A정밀 — 아님)
- 적재 영수증의 검토자(`by`)가 실제로 검토한 사람인가? (전: 스크립트가 지어낸 이름)

## 1. 원인 (파일:줄)

### 1.1 관측(라이브 4차 C 판단 `live/C-decision.json`)

| 카드 | 연결 공급사 | 점수 | 점수 성분 | 규정 결과 |
|---|---|---|---|---|
| SOP-PUR-13 최단 납기 긴급 발주 | sup:a A정밀 | **3.32 (1위)** | bsc 0 · delivery 1.32 · forecast 2 | 없음 |
| SOP-PUR-12 대체 승인 공급사 | sup:a A정밀 | 2.32 | bsc −1 | 없음 |
| SOP-PUR-11 순정(OEM) | sup:b B-OEM | 1.82 | bsc −1 · warn −0.5 | 300만 원 초과 경고 |

- 세 카드 모두 `penalties: []`, `scoreParts.quality: 0`. 카드 사실 `expected_defect_cost`는 A정밀 25.2 · B-OEM 6.6으로 계산됐지만
  **어떤 규칙 · 순위 식도 읽지 않았다**.
- SOP-PUR-13의 득실은 "설비 가동률 ↑"(추출이 PR-7.1에서 추론) 하나뿐이라 BSC가 0, 나머지 둘은 −1이다. 이 1점 차가 그대로 순위가 됐다.

### 1.2 고리별 판정 — 가설 대조

| 고리 | 위치 | 판정 |
|---|---|---|
| 원문 | `docs/samples/PR-07_spare-parts-standard.md` PR-7.4 | **판정 가능한 문장이 있다.** "불량률이 10 %를 넘는 승인 공급사에 발주할 때는 … 전수 검사 비용 20만 원을 더해 비교한다"(문턱 10 %, 감점 20만 원). 총비용식(불량 기대비용 = 수량 × 불량률 × 250만 원)도 있다. → 원문 보강은 필요 없다 |
| 판단 입력 자리(시드 구조) | `it/neo4j/v2/scenario_structure.cypher:11-22` | **끊긴 고리 ①.** C를 위해 규정 결정(dec:compliance)에 선언한 입력은 `in:po-amount` · `in:lead-slack-days`뿐이다. 공급사 불량률 입력이 없다. 기존 `instances.cypher:398-399, 433`에도 없다 |
| 추출 지시 | `it/process/procsvc/manual_extraction.py:38-40` | 결함 아님. "목록에 없는 … 입력 … 은 지어내지 말고 warnings에 적으세요"를 지켰다. 추출 경고 원문: "PR-7.4 '불량률이 10 %를 넘는 … 20만 원을 더해 비교한다'는 PENALTY 후보지만 dt:compliance에 공급사 불량률 입력이 없어 규칙으로 만들지 않았다(입력 신설은 사람 검토)" |
| 적재 검사 | `it/process/procsvc/manual_knowledge.py:395-403` (`check_graph`) | 결함 아님. 규칙의 검사 입력이 결정의 REQUIRES_INPUT에 없으면 거부한다 — 그래서 **사람 검토자도 이 규칙을 넣을 수 없었다**(검토 화면도 같은 목록만 고른다). 고리 ①이 막은 것 |
| 판단 엔진 사실 | `it/agent/agentsvc/cards.py:107-108` | **끊긴 고리 ②.** `expected_defect_cost = 단가 × 수량 × 불량률`(A정밀 25.2)은 PR-7.4 정의(수량 × 불량률 × 250 = 180)와 다르고, 이 변수를 선언한 InputData가 없어 어떤 지식도 시험할 수 없는 고아 사실이다. 판단 기록에는 "불량 기대비용 25.2만 원"으로 보여 읽는 사람을 오도한다 |
| 시험 | `tests/test_c2_judgement.py:147` | **같은 결함의 시험 쪽 그림자.** 지식에 없는 규칙 `rule:pur-defect`(expected_defect_cost > 20, 감점 40)를 시험이 직접 지어내서 "A정밀 불량 감점"이 통과했다. 실제 지식 경로로는 만들 수 없는 규칙이다 |
| 시험 대역 | `tests/c1_fixtures.py:116-119` | **우회 흔적.** 사람이 쓴 대역도 불량률 입력이 없어 `skill_code == 'PR_CREATE'` + `applies_to=['SOP-PUR-12']`로 "SOP-PUR-12는 불량 10 % 초과"를 손으로 박았다. 감점이 공급사의 불량률이 아니라 SOP 번호에 붙어, 다른 SOP가 A정밀을 가리키면 감점이 사라진다(라이브가 정확히 그 경우) |
| SOP 연결 | 추출 결과 SOP-PUR-13 → `sup:a` | **추출 오독.** 원문 1단계 "견적 공급사 중 리드타임이 가장 짧은 공급사를 고른다" → C트레이딩(1일), 2단계 "승인 공급사가 아니면 이 절차를 쓰지 않는다" → AVL 규칙이 제외해야 한다. 추출은 2단계 조건을 값 고르기에 미리 적용해 "승인 공급사 중 최단"(A정밀)으로 바꿨다(경고에 "추론 — 사람 검토가 필요하다"로 적음). 지시문에 "선택 기준과 적용 조건을 나누라"는 일반 규칙이 없다(`manual_extraction.py:49-52`) |
| 검토 단계 | `scripts/c3_ingest.py:59-61` | **끊긴 고리 ③ (시험 도구 결함).** 제안의 link를 그대로 `links`로, `by="[C3 조립] 실제 추출 검토"`, `reviewed=True`로 적재한다. 아무도 보지 않았는데 영수증에 검토자가 남는다. 수업 흐름(실라버스 OL7 "사람이 확인한 것만 지식에 잇는다 — 승인 안 한 항목은 안 들어감", OT9 "AI가 뽑은 표에 틀린 줄이 하나 숨어 있다")에서 검토는 학생이 포털에서 하는 단계다. 이 스크립트는 수업 경로가 아니라 라이브 검증 도구인데, 검증 판정의 근거가 된 지식을 "검토됨"으로 위장했다 |

### 1.3 결론 — 가설은 절반 맞다

- 맞는 부분: "비교 원칙이 판정 규칙으로 만들어지지 않았다", "SOP-PUR-13이 A정밀로 잘못 연결됐다", "적재 스크립트가 검토를 손대지 않고 승인했다".
- 틀린 부분: "추출이 원칙을 놓쳤다"가 아니다. 추출은 원칙을 읽었고 규칙으로 옮기려 했지만, **시드 구조에 그 규칙이 시험할 판단 입력(공급사 불량률)이 없어서**
  계약대로 멈췄다. 사람 검토자가 있었어도 이 규칙은 넣을 수 없었다(적재 검사가 거부). 원문 C3 보고서 7.4의 "원문에 판정할 문턱이 없다"도 틀렸다 — 10 % 문턱이 있다.
- 세 고리 가운데 하나만 고쳐서는 B-OEM이 이기지 않는다(2절 계산).

## 2. 분류

| 발견 | 분류 | 근거 |
|---|---|---|
| 시드 구조에 공급사 불량률 판단 입력이 없음 | **결함**(지식 자리 누락) | 원문에 판정 문장이 있는데 추출 · 사람 검토 어느 길로도 적재할 수 없다(`check_graph` 거부) |
| `expected_defect_cost` = 단가 × 수량 × 불량률 | **결함**(원문과 다른 식 · 고아 사실) | PR-7.4 정의와 다르고, 선언된 InputData가 없어 어떤 지식도 시험 못 함. 판단 기록에 틀린 금액(25.2만 원)을 보인다 |
| `test_c2_judgement`의 `rule:pur-defect` | **결함**(시험이 지식에 없는 규칙을 지어냄) | 실제 경로로는 생길 수 없는 감점으로 "A정밀 불량 감점"이 통과했다 |
| C1 대역 `rule:pur-inspection`의 `skill_code`+`SOP-PUR-12` | **우회**(입력 부재를 SOP 번호로 메움) | 감점이 공급사가 아니라 SOP 번호에 붙는다 |
| 추출의 SOP-PUR-13 → sup:a | **결함**(추출 지시에 일반 규칙 없음) + LLM 오독 | 선택 기준(1단계)과 적용 조건(2단계)을 섞음. 지시문이 둘을 나누라고 하지 않았다 |
| `c3_ingest.py`의 무조건 승인 | **결함**(시험 도구) — 수업 의도 아님 | 수업에서 검토는 학생 단계(OL7 · OT9). 도구가 검토 없이 `reviewed=true`와 지어낸 검토자를 남겼다 |
| 원문 보강 필요 여부 | **오해** | 10 % 문턱 · 20만 원이 이미 원문에 있다. 보강하지 않았다 |
| "불량 기대비용(수량 × 불량률 × 250만 원)" 총비용 비교 | **근거 부족 → 이번에 안 함** | 스키마 v2의 규정 규칙은 "입력 · 연산자 · 상수 문턱 → 상수 감점"이라 금액 자체를 더하는 비교는 규칙이 아니라 순위 정책(`rule:rank-value.rankingPolicy`)의 일이다. 순위 정책은 카드별 사실이 아니라 결정 수준 사실만 읽고(`cards.py:280` `score_option(o, base_facts, …)`), 성분 추가는 A078 결론대로 전문가 결정이다. 원문 문턱 규칙만으로 B-OEM이 이긴다(4절 계산) |

## 3. 조치 (근본 수정 · 정답 하드코딩 없음)

1. **판단 입력 자리 추가** — `it/neo4j/v2/scenario_structure.cypher:11-17, 24`: InputData `in:supplier-fail-rate`(변수 `supplier_fail_rate`, 출처 `sys:scm`, REPRESENTS `msr:part-quality`)와
   `dec:compliance` REQUIRES_INPUT · `task:compliance` READS. 스키마 v2 클래스 · 관계만 쓰는 가산 인스턴스(기존 `in:po-amount`와 같은 관례), 근거 PR-7.4 문장을 주석에 남김.
2. **엔진 사실** — `it/agent/agentsvc/cards.py:100-111`: 카드가 고른 공급사 견적의 불량률을 `supplier_fail_rate`로 싣는다(감점이 공급사를 따라간다).
   원문과 다른 식의 고아 사실 `expected_defect_cost`를 지웠다(`cards.py:267` 카드 사실 목록도). 1번 자리가 생겨 추출이 원문 문장
   "불량률이 10 %를 넘는 … 20만 원을 더해 비교한다"를 `supplier_fail_rate > 0.1 → PENALTY 20`으로 적재할 수 있다.
3. **추출 지시 일반 규칙** — `it/process/procsvc/manual_extraction.py:13, 52-54` (정의 2.0 → **2.1**, 같은 판본 변경은 등록이 거절되므로 올림):
   "값은 단계의 선택 기준을 그대로 적용해 고르고, 같은 절차의 적용 조건으로 다른 값으로 바꾸지 말며, 조건은 dt:compliance EXCLUDE 규칙으로 옮긴다". C 전용 문구 없음.
4. **검토 단계** — `scripts/c3_ingest.py` 재작성: `extract`(제안만 저장, 적재 안 함)와 `commit --review <파일>`(사람 검토 기록 적용 뒤 적재)로 나눔.
   검토 기록은 검토자 · 검토한 추출 인스턴스 · 경고 읽음 표시가 있어야 하고, 고친 연결 · 뺀/더한 지식마다 사유와 **원문에 한 번만 있는 인용**이 있어야 한다
   (좌표를 계산해 영수증에 남김). 맞지 않으면 좌표 있는 오류로 적재하지 않는다. 옛 기본 동작(같은 원문의 끝난 추출 자동 재사용)은
   `--reuse`로만 — 시드 · 지시가 바뀐 뒤의 옛 추출은 옛 목록을 본 것이라서.
5. **시험 정리** — `tests/test_c2_judgement.py`: 지어낸 `rule:pur-defect`를 원문 규칙(`supplier_fail_rate > 0.1`, 감점 20)으로 바꿈, 불량률 사실 단정 추가,
   "감점은 SOP 번호가 아니라 공급사를 따라간다"(SOP-PUR-13 → A정밀이어도 감점) 시험 추가. `tests/c1_fixtures.py`: 우회 규칙을 원문 인용 그대로의 입력 규칙으로.
   `tests/test_c1_knowledge.py`: 가짜 그래프의 규정 입력이 **시드 파일이 실제로 선언한 입력**과 같은지 대조하는 시험(손 복사본이 시드와 어긋나면 잡힘), 정의 2.1 단정,
   문서 C 적재가 불량률 규칙을 SOP 셋 모두에 거는지 단정. `tests/test_c3_ingest_review.py`(새 파일, 14개).
6. **라이브 검사기 기대값** — `scripts/probe_c1_knowledge.py:122-124, 197-201`: 전체판에 더해지는 노드에 `in:supplier-fail-rate`, C 순위 확인은 견적(그래프 SUPPLIED_BY)으로
   카드 사실을 계산하게 함(전에는 결정 수준 po_amount를 넣어 카드별 값이 비었다). 실행은 안 함(neo4j 필요).
7. 문서 — `docs/handoff/verification/2026-10-09/c3-assembly.md` 7.4 C 행에 정정 한 줄.

## 4. 검증

| 항목 | 결과 |
|---|---|
| 관련 시험 13개 파일(`test_c1_knowledge` · `test_c2_judgement` · `test_seed_editions` · `test_c3_ingest_review` · `test_manual_extraction` · `test_cards` · `test_c2_parts` · `test_c2_execution` · `test_c3_assembly` · `test_c3_bc_simplified` · `test_decide_facts` · `test_forecast_cards` · `test_kpi`) | **검증됨** 232 통과 |
| 뮤테이션 M1: 시드 REQUIRES_INPUT에서 `in:supplier-fail-rate` 빼기 | **검증됨** — `test_fake_catalog_compliance_inputs_are_declared_by_the_seed` 실패 |
| 뮤테이션 M2: 엔진이 `supplier_fail_rate`를 None으로 | **검증됨** — `test_c2_judgement` 2개 실패(추천 · 감점) |
| 뮤테이션 M3: 검토 기록의 경고 읽음 확인 끄기 | **검증됨** — `test_c3_ingest_review` 1개 실패 |
| 뮤테이션 M4: 검토자의 연결 수정 적용 안 하기 | **검증됨** — `test_c3_ingest_review` 1개 실패 |
| 라이브 C 추천이 B-OEM | **미검증**(지시대로 라이브 안 함) |
| 실제 LLM이 2.1 지시로 SOP-PUR-13을 sup:c로 연결하고 불량률 규칙을 만드는지 | **미검증** |
| `probe_c1_knowledge.py` 수정분 | **미검증**(문법 검사만) |

**점수 계산(라이브 4차 성분 기준, 예상)**: 납기 1.32 · 예측 2.0은 세 카드가 같다.
- 연결이 원문대로(13 → C트레이딩)일 때: 13 제외(AVL) · 12(A정밀) = −1(BSC) − 1(감점 20/20) + 3.32 = **1.32** · 11(B-OEM) = −1 − 0.5(경고) + 3.32 = **1.82** → **B-OEM 1위**.
- 불량률 규칙 없이 연결만 고치면: 12 = 2.32 > 11 = 1.82 → A정밀. 규칙만 넣고 13 → A정밀이 남으면: 13 = 3.32 − 1 = 2.32 > 1.82 → A정밀.
  **두 고리를 다 고쳐야 B-OEM이 이긴다.**

## 5. 라이브 확인 절차 (메인이 스택 반영 뒤 한 번)

검사기(run_regression · probe_*)가 돌지 않을 때 배포를 끝낸다(CLAUDE.md §3). neo4j는 C3 때처럼 구조판 볼륨 `hyd-iot-edu_neo4j-data-c3`.

1. **이미지 반영**: `process`(추출 정의 2.1), `agent` · `dmn-mcp`(둘 다 `agentsvc/cards.py`를 담는다) 재빌드 · 기동 →
   `docker inspect hyd-iot-edu-process-1 --format '{{.State.StartedAt}} {{.RestartCount}}'`로 안정 확인.
2. **시드 구조 반영(멱등 MERGE)**: `SEED_EDITION=structure docker compose --profile knowledge run --rm kg-seed`.
   확인: `MATCH (:Decision {id:'dec:compliance'})-[:REQUIRES_INPUT]->(i:InputData {id:'in:supplier-fail-rate'}) RETURN i.variable` → `supplier_fail_rate`,
   `GET /api/kg/manuals/catalog`의 `dt:compliance` 입력에 같은 id.
3. **PR-07 재추출(재사용 금지)**: `.venv/bin/python scripts/c3_ingest.py extract PR-07` (`--reuse` 쓰지 말 것 — 옛 추출은 옛 목록을 봤다) →
   `.evidence/a161-c3/proposal-PR-07.json`에서 볼 것:
   - `preview.knowledge.rules`에 `dt:compliance` · `PENALTY` · 검사 `in:supplier-fail-rate > 0.1` · 감점 20 · `applies_to` 세 SOP인 규칙이 있는가
   - `preview.warnings`에 "불량률 입력이 없어 규칙으로 만들지 않았다"가 **없는가**
   - `SOP-PUR-13`의 `link.actions[0].value`가 `sup:c`인가(지시 2.1의 효과). `sup:a`면 LLM이 지시를 따르지 않은 것 — 아래 4에서 사람 검토로 고치고 그 사실을 기록
4. **사람 검토 기록 쓰기**(검토자가 proposal을 원문과 대조한 뒤) — 예시(13이 sup:a로 다시 나온 경우, `extraction`은 proposal의 값):
   ```json
   {"doc": "PR-07", "by": "<검토한 사람>", "extraction": "<proposal-PR-07.json 의 preview.extraction.instance>", "warnings_read": true,
    "links": {"SOP-PUR-13": {"set": {"actions": [{"action": "action:purchase-request", "value": "sup:c"}]},
              "reason": "1단계 기준(견적 중 최단 리드타임)은 C트레이딩 1일. 승인 공급사가 아님은 2단계 조건이라 AVL 규정(EXCLUDE)이 판단한다",
              "quote": "견적 공급사 중 리드타임이 가장 짧은 공급사를 고른다."}}}
   ```
   불량률 규칙이 빠졌으면 `"add": {"rules": [ {…규칙…, "quote": "불량률이 10 %를 넘는 승인 공급사에 발주할 때는 입고 검사를 전수 검사로 강화하고, 전수 검사 비용 20만 원을 더해 비교한다.", "reason": "…"} ]}`.
   고칠 것이 없으면 `links` 없이 `warnings_read: true`만.
5. **적재**: `.venv/bin/python scripts/c3_ingest.py commit PR-07 --review <검토 기록.json>` → `ingest-PR-07.json`의 `commit_status` 200, `by` = 검토자,
   `review_changes`(사유 · 원문 좌표). 같은 문서의 앞 배치(0092c109…)는 재적재가 대체한다 — 그래프에서 옛 규칙 id가 남지 않았는지 확인
   (`MATCH (r:Rule)-[:DERIVED_FROM]->(:ManualSection) WHERE r.id STARTS WITH 'rule:pur' RETURN r.id, r.when`).
   대체는 `manual_graph.commit`이 앞 배치 스냅숏과 지금 그래프가 같을 때만 한다(`manual_graph.py:250-257`). 4차 완주가 그 SOP를 가리키는 기록을 남겨
   409 "적재 뒤 … 참조가 바뀌었습니다"가 나면 우회하지 말고 그 결과를 그대로 보고한다(배치 되돌리기 `POST /api/kg/manuals/batches/{batch}/rollback`도 같은 검사를 받는다 — 미확인).
6. `scripts/c3_flows.py deploy` 뒤 포털 [재고 보충]으로 C 1회 → `C-decision.json`에서 볼 것:
   - `recommended` = `skill:sop-pur-11`(순정 OEM 표준 발주, 330만 원) · rank 1, 경고 `po_amount > 300`만
   - SOP-PUR-12(A정밀): `facts.supplier_fail_rate` 0.12, `penalties`에 불량률 규칙, `scoreParts.penalty` −1.0 → 점수 약 1.32
   - SOP-PUR-13: `feasible` false, 위반 = AVL 규칙(공급사 C트레이딩) — 13이 sup:c일 때
   - SOP-PUR-11: `facts.supplier_fail_rate` 0.02, 감점 없음 → 점수 약 1.82 (BSC 득실이 4차와 같다면)
   - 판단 기록 카드 사실에 `expected_defect_cost`가 없고 `supplier_fail_rate`가 있다
7. 끝나면 C3 7.3과 같이 흐름 `deploy-reset` · neo4j 원래 볼륨.

## 6. 남는 일 · 다른 담당에게

- **포털(손대지 않음)**: `it/portal/www/plainWords.js:46-47` 사실 이름표에 `supplier_fail_rate`(예: 공급사 불량률, 단위 없음 또는 %)가 없어
  카드 사실에 "supplier fail rate" 영문이 보일 수 있다. 지운 `expected_defect_cost` 이름표는 쓰이지 않게 됐다. 포털 담당이 정리할 것.
- **총비용(불량 기대비용) 비교**: 순위 정책 성분으로 넣으려면 ① 순위 식이 카드별 사실을 읽게(`cards.py:280` base_facts → 카드 사실) ② 검토된
  순위 정책 API로 성분 추가가 필요하다. 원문 문턱 규칙만으로 설계 결과가 나오므로 이번에는 하지 않았다(A078: 어떤 조건을 넣을지는 전문가 결정).
- `docs/보고서/2026-10-09_HYD_시나리오_3개.md:221`의 "적재 전 검토 단계에서 사람이 고쳐야 할 지점"은 절반만 맞다(사람도 불량률 규칙은 넣을 수 없었다).
  라이브 확인 뒤 메인이 고친다. `docs/handoff/verification/2026-10-09/c2-execution.md:59`의 `expected_defect_cost` 언급은 옛 기록으로 둔다.
- HANDOFF §9 갱신은 메인 몫(다른 담당과 동시 편집을 피함).
