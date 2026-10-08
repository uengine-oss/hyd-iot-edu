# B7 — 작동유 열화: 사람 입력(오일 분석 기준 이탈)으로 시작하는 정비형 흐름이 끝까지 (확정 TODO B7, DECISIONS 110 ⑤)

작업 단위 B7, 2026-10-08 밤. 브랜치 `worktree-b7-oil`(기준 7cf6fd6, B1~B5 합친 뒤). 수업 장면(실라버스 4막): 학생이 출발본(기준 흐름 그림)을
받아 세 군데만 바꿔 작동유 대응 흐름을 만든다 — ① 시작 = 사람이 오일 분석 결과(기준 이탈)를 입력 ② 설비 명령 대신 작업지시(정비)
③ 교환 뒤 재분석 결과 입력(사람) → 정상이면 종결, 아니면 다시. **작동유 흐름은 학생이 만든다** — 코드 · 시드에 흐름 정답은 없고,
시험용 그림(`tests/fixtures/bpmn/oil_maintenance_student.bpmn`)은 시험에만 쓴다.

비유 한 줄: 센서 경보가 "자동 화재 감지기"라면 사람 입력 경보는 "화재 신고 전화"다. 신고를 받은 상황실은 감지기 신호와 **같은 접수 대장**에
같은 칸으로 적고(출처: 전화, 신고자 이름), 그다음부터는 같은 출동 절차(처리 건 · 사건 · 승인)를 밟는다.

## 핵심 결정 — 사람 입력을 경보와 같은 길로
B3 보고: 사람 입력/직접 시작 정의는 승인 · 효과 부품(조치 선택 · 작업지시)을 쓰면 값 연결 검사에서 거절된다(`incident` 는 경보만 만든다).
새 시작 계약(사건 없는 승인 원문)을 만드는 대신, 사람 입력을 **센서 경보와 같은 계약의 경보**로 만들어 기존 경로를 그대로 탄다.
- 경보 모양 = 감지기와 같다(`it/detector/det/cep.py:54-56` `_alert`: alertId · asset · pattern · severity · state · t · evidence) + 출처 표시
  `source: "human_input"` · `enteredBy {id, name, role}` · `evidence {item, item_name, unit, value?, memo?, out_of_spec, oil_analysis_out_of_spec}`.
- 들어가는 길 = `POST /api/incidents` 의 instance 갈래와 같다(`main.py:548` 이후: `source_record(..., source='http')` → `rt.alert_policy` →
  `source_inbox.receive` → `source_delivery.wait_for`, 원천 접수가 없으면 `rt.on_alert_raise`) → `instances.on_alert_raise`(`instances.py:338`) →
  `start_definition`(`:196`, 사건 생성 · 회복 기준 고정) → 사건 상태기계(`machine.on_card`).
- 어느 흐름이 여는지는 정하지 않는다: B4 `flow_deploy.route_definition` 이 정한다. OIL_ANALYSIS 를 받는 배포 흐름이 없으면 기준 흐름의
  `alertPolicy.unsupported` → 사람 검토(alert_triage) — **기존 그대로**(시험).
- 기준 이탈이 아니면 경보를 만들지 않는다(사유 + 감사 `HUMAN_INPUT_IN_SPEC`). 지식의 패턴 검사(`pattern:oil-analysis -TESTS-> in:oil-analysis == true`,
  `it/neo4j/v2/knowledge_a098.cypher:19-26`)와 같은 조건.

버린 대안: ① 사람 입력 시작(`startForm`) 흐름에 사건 없이 승인 원문을 만드는 계약 — 승인 · 작업지시 · 사건 상태기계 · 원장 검증을 두 갈래로
나눠야 하고 기존 안전 검사(사건 소유 · 상태)를 우회하게 된다. ② 기준 정의(anomaly_response)의 alertPolicy 에 OIL_ANALYSIS 추가 — 기준 흐름이
작동유를 받게 돼 "학생이 만든다"와 어긋나고 기준 보호 위반.

## 원본(참고) 파일:줄 · HYD 차이
| 원본 | 내용 | HYD | 판단 |
|---|---|---|---|
| process-gpt-vue3@867e8cf `src/components/api/ProcessGPTBackend.ts:821-880` `start(input)` | 사람이 첫 폼 값(form_values)을 넣어 정의를 바로 시작 | 사람 입력은 **경보**가 되고, 경보 정책(배포 흐름)이 정의를 고른다 | 차이 있음, 유지 — HYD 승인 · 효과 부품은 사건(Incident)이 있어야 안전 검사가 성립(① 결함 아님 ② 회의 요구 "사람 승인 1회 뒤 실행"을 지키려면 필요) |
| HYD 감지기 `it/detector/det/cep.py:54-56` | 경보 계약 | 같은 칸 + 출처 표시 | 같음 |
| HYD A074 `scripts/probe_work_order_only_card.py` · `procsvc/work_orders.py:24-60` · `machine.on_work_order(work_order_only=True)` | 설비 명령 없는 작업지시 전용 카드 → 실제 CMMS 응답 → 사건 종결 | 그대로 씀(새 코드 없음) | 같음 |
| HYD A072 `machine.on_rework_reopen` | 재작업이 사건을 다시 열 때 이전 명령 · 작업지시를 `superseded` 로 보존 | `machine.on_recheck_reopen` 같은 모양(작업지시로만 닫힌 사건만) | 아래 |

## 만든 것
### 1. 사람 입력 경보 (`it/process/procsvc/human_alert.py` 새 파일)
- 계약 표 `PATTERNS["OIL_ANALYSIS"]`: 이름 · 지식 id(`pattern:oil-analysis` · `sym:oil-analysis-out-of-spec` · `in:oil-analysis` · 변수
  `oil_analysis_out_of_spec`) · 분석 항목 4(산가 TAN · 수분 함량 · 청정도(NAS · ISO 4406) · 점도 변화 — 증상 aliases · HM-9.1 표) · 회복 기준
  (`TS1 < 55`, requireClear — 정비형 흐름에서는 쓰이지 않음; 누가 설비 명령 · 재관측을 넣으면 해제(CLEAR)가 없어 재관측이 상급자로 간다).
  지식 id 는 시드 파일과 시험으로 대조.
- `build_alert(body)` → (경보 | None, 사유). 틀린 입력은 칸 이름과 함께 거절(`pattern · asset · item · out_of_spec · by · value`).
- API: `GET /api/human-alerts/form` · `POST /api/human-alerts` → `{raised, reason, alert, route(response|triage), definition{definition, version, name},
  route_text, instance, incident}` / 기준 안 → `{raised:false, reason}` / 400(칸) · 409(legacy 모드 · 접수 거절) · 503(접수 확인 시간 초과),
  감사 `HUMAN_ALERT_RAISED` · `HUMAN_INPUT_IN_SPEC`. `GET /api/human-alerts/current?asset&pattern[&alert_id]` → 사건이 열려 있는 사람 입력 경보
  (dmn-mcp 진단 도구가 서버 기록을 읽는 용도), 없으면 404.
- `main.py`(+20줄, 줄 추가만): `_admit_human_alert` = `POST /api/incidents` 와 같은 원천 접수 갈래, `open_alerts` = 끝나지 않은 사건의 경보.

### 2. B3 가져오기에서 사람 입력 패턴 고르기 (`bpmn_import.catalog`)
- 경보 시작 패턴 목록에 `human_alert.policy_patterns()` 를 보탠다(`human_patterns` 로 구분). 기준 정의 파일 · 기준 alertPolicy 는 그대로.
- 메시지 시작 그림의 기본 선택은 **감지기 패턴만**(사람 입력은 학생이 고름) — 다시 그린 기준 흐름이 같은 정의가 되는 B3 시험 그대로.
- 포털 흐름 화면의 패턴 이름은 `oilInput.js` 가 `PATTERN_LABEL.OIL_ANALYSIS = '오일 분석 기준 이탈 (사람 입력)'` 을 보탠다(app.js 수정 없음).

### 3. 정비형 흐름이 끝까지 — 엔진 · 사건 상태기계 확인과 최소 수정
확인(수정 없음): 작업지시 전용 카드 → `work_orders.prepare`(승인된 work-order-only, 사건 AWAITING_APPROVAL) → 실제 CMMS 응답 →
`machine.on_work_order(work_order_only=True)` → `WORK_ORDER_CREATED → CLOSED`. 사건이 닫혀도 처리 건은 다음 task(재분석 입력)로 계속되고,
`reconcile_terminal_incidents` 의 조치 전 종료(A074)로 오인하지 않는다(작업지시 행이 시작됐으므로 — 시험).
막혔던 곳(최소 수정):
- **재분석 비정상 → 다시**: 되돌아가는 선이 새 판단 · 승인으로 돌아가면 승인이 `incident is CLOSED; approval requires review` 로 거절됐다.
  → `machine.on_recheck_reopen`(새 전이, `machine.py:209`): **설비 명령 없이 작업지시로 닫힌 사건만** 다음 승인 대기로 다시 연다. 닫은
  작업지시는 `superseded`(kind=recheck)에 보존, 같은 요청(다시 들어간 작업 행 id)은 한 번만.
  → `instances._recheck_round`(`instances.py:462`): 엔진의 반복 재진입(새 행)이 **모든 경로에서 끝보다 사람 승인을 먼저 만나는** task 이고 사건이
  작업지시만으로 닫혔으면 커밋 뒤 `_reopen_for_recheck` → 훅 `reopen_for_recheck`(`instance_mode.py:353`). 재분석 task 자체의 재진입("정상"이면
  끝날 수 있음)이나 측정만 반복하는 루프는 열지 않는다. 커밋 뒤 실패(재기동)는 `reconcile_terminal_incidents` 폴링이 다시 연다.
- **내장 판단 복구 경로가 승인된 첫 판단을 새 바퀴에 재생**하던 것: `reconcile_legacy_decisions`(`instance_mode.py:407`)가 이미 승인 · 전달된
  판단(`process_approval_id`)을 후보에서 뺀다 — 새 바퀴는 새 평가(LegacyAssessment)만 채운다. 첫 바퀴 동작은 같다.
- **메모리 저장소(단위 시험) 등록이 proc_def 머리를 안 둠** → B4 배포가 `등록되지 않은 정의 판본` 으로 실패(PG 는 머리 행이 있음).
  `bpmn_store.FlowStore.register` 메모리 갈래가 PG 처럼 머리 행(prod_version 비움)을 둔다. B3 시험 한 줄(`my_cooler` 머리 None → prod_version None)을 PG 와 맞춤.

### 4. 결정론 판단(AGENT_BRIDGE=legacy)과 실제 워커 도구가 OIL_ANALYSIS 를 처리
- 원래: OIL_ANALYSIS 원인 4개에는 센서 증거 규칙(Evidence)이 없어 `card.evidence_status` 가 UNSUPPORTED → **"현재 관측 근거로 뒷받침되는
  원인이 없어 조치를 보류합니다"**(사람이 입력한 분석이 근거인데도).
- `agentsvc/card.py` `human_evidence` · `with_human_evidence`: 출처가 사람 입력이고 기준 이탈인 경보는 **센서 증거 규칙이 없는 원인에만** 입력한
  분석을 증거 한 줄(`human:<alertId>`, PASS, 입력자 · 항목 · 값 · 메모)로 준다. 순위는 사전확률 × 1 = 지식 순서(산화 0.4 → 수분 · 오염 0.25 →
  교환 주기 0.1, `rule:dx-oil` 주석과 같음). 센서 증거가 있는 원인은 덮지 않고, 출처 표시 없는 경보는 사람 입력으로 보지 않는다. 인용 · 가드레일 통과.
- `agentsvc/main.py` pipeline(내장 결정론 판단 = `/api/agent/evaluate`): 위 근거로 진단 → `decide`. 후보가 없으면 보류 사유에 `explanation` 을 쓴다.
- `agentsvc/cards.py` `explain`: 후보 규칙이 **맞았지만 내놓는 조치가 없으면** "후보 선택 규칙 rule:cand-oil 은(는) 맞았지만 내놓는 조치(SOP)가
  없다 … 매뉴얼을 적재해 조치를 고장 유형에 연결하면 후보가 된다" — **HM-9 적재 전 사유**. 적재 뒤에는 `rule:cand-oil → SOP-OIL-21`(work_order).
- `dmn-mcp diagnose(asset, pattern, alert_id?)`(실제 워커가 쓰는 도구): 센서 증거 규칙 없는 원인이 있으면 **process 서버 기록**
  (`/api/human-alerts/current`)에서 처리 중인 사람 입력 경보를 읽어 같은 근거로 쓴다 — 호출자 인자를 근거로 믿지 않는다. 도구 설명에 한 줄.
- 적재 경로 확인(수정 없음): 시드 `rule:cand-oil` 은 고장 유형 하나만 검사하는 후보 규칙(`skill_graph.CANDIDATE_RULES_Q` 조건)이라
  HM-9 커밋(`manual_api.commit` → `candidate_rules` → `manual_graph.desired`)이 `rule:cand-oil -OUTPUTS-> SOP-OIL-21` 을 만든다.

### 5. 포털 `it/portal/www/oilInput.js` (새) — 메뉴 "설비 → 오일 분석 입력"(`#/oil`)
설비 · 분석 항목 · 측정값 · 기준 이탈 여부(예/아니요) · 메모 · 입력자(내 작업함의 "나", 없으면 이름) → 보내기 → "경보 만듦 · 배포된 흐름(흐름
이름 · 판본) · 처리 건 보기 →" 또는 "경보 만듦 · 사람 검토" 또는 "경보 없음 + 사유". `index.html` +3줄(메뉴 · 섹션 · 스크립트), `shell.js` +1줄.

## 바꾼 파일
- 새: `it/process/procsvc/human_alert.py`, `it/portal/www/oilInput.js`, `tests/test_b7_oil.py`, `tests/fixtures/bpmn/oil_maintenance_student.bpmn`(의미 부분
  손으로 정함 · 배치 좌표만 스크립트 계산, 커밋 안 함), 이 문서.
- 수정: `it/process/procsvc/{bpmn_import.py, bpmn_store.py, instances.py, instance_mode.py, machine.py, main.py}`, `it/agent/agentsvc/{card.py, cards.py, main.py}`,
  `it/dmn-mcp/dmn_mcp/{tools.py, server.py}`, `it/portal/www/{index.html, shell.js}`, `tests/test_bpmn_import.py`(1줄).
- 마이그레이션 없음(`20261008000047` 미사용 — 원천 접수 `source='http'` 그대로, 출처 표시는 경보 본문에). 시드 변경 없음.

## 시험
`tests/test_b7_oil.py` **27개**:
- 사람 입력 → 경보: 감지기와 같은 칸 · 출처 · 입력자, 입력 하나 = 경보 하나 / 기준 안 → 경보 없음 · 사유 / 틀린 칸 7종 거절(칸 이름) /
  계약의 지식 id 가 시드에 있음.
- API: 배포 흐름 없음 → alert_triage 처리 건 · 사건 ESCALATED(UNSUPPORTED_ALERT_PATTERN, 기존 사람 검토) / 기준 안 → 처리 건 · 사건 0 /
  400 · 양식 / legacy 모드 409 / 배포 뒤 → 배포 흐름 + 진단 도구용 `current` 200 · 다른 설비 404.
- 사전 검사: 목록에 OIL_ANALYSIS, 메시지 기본값은 감지기 패턴 3개 / **사람 입력 경보 시작 + 승인 + 작업지시 통과**(설비 명령 부품 0, loopPolicy guarded) /
  **승인 없는 작업지시 · 승인 없는 설비 명령 · 승인을 건너뛰는 되돌아가는 선 거절**(칸 위치 사유).
- 끝까지(MemoryRepo · 내장 결정론 판단 · 실제 사건 상태기계): B3 등록 → B4 배포 → 사람 입력 경보 → my_oil 처리 건 · 사건 AWAITING_APPROVAL →
  LegacyAssessment(원래 경보 그대로 평가) → 네 에이전트 task DONE → 운전원 승인 거절(403) · 정비관리자 승인 → **작업지시 1건 · 설비 명령 0건** ·
  사건 CLOSED(WO 응답 번호) → 재분석 task 열림(폴링해도 그대로) → "정상" → COMPLETED(종결) / **"비정상" → 원인 진단 새 행 · 사건 다시 승인 대기
  (첫 작업지시 superseded) · 복구 경로가 첫 판단을 재생하지 않음 → 새 평가 · 새 승인 · 작업지시 2건째(명령 0) → "정상" → COMPLETED** /
  다시 열기가 커밋 뒤 실패해도 폴링이 다시 엶(한 번만) / 측정만 반복하는 루프는 사건을 안 엶 / `on_recheck_reopen` 은 작업지시로만 닫힌 사건만(명령 낸 사건 거절).
- 결정론 판단: 사람 입력 없으면 보류(지금과 같음) · 있으면 SUPPORTED · 산화 1순위 · 인용 · 가드레일 통과 · 센서 증거는 안 덮음 · 출처 위조 안 받음 /
  **HM-9 적재 전**(rule:cand-oil 출력 없음) → WITHHELD + "rule:cand-oil … 조치(SOP)가 없다" · 진단은 됨 / **적재 뒤** → EVALUATED, 카드 SOP-OIL-21(work_order, 명령 0) /
  적재 계획이 `rule:cand-oil -OUTPUTS-> SOP-OIL-21` · `sys:cmms -HAS_SKILL->` 를 만듦 / dmn-mcp diagnose 가 서버 기록을 읽어 진단(센서 패턴은 묻지 않음).
- **일부러 깨뜨림 10/10 잡힘**(`.evidence/b7/mutations.json`): 다시 열기 끔 · 다시 열기 조건 느슨하게(재분석 재진입에서도 엶 — 실제로 둘째 작업지시 뒤
  사건이 다시 열렸던 결함) · 승인된 첫 판단 재생 · 사람 입력 근거 끔 · 기준 안도 경보 · B3 목록에서 사람 입력 패턴 뺌 · 메모리 머리 행 없음 ·
  조치 없음 사유 지움 · dmn-mcp 가 서버 기록 안 읽음 · 명령 낸 사건도 다시 엶.
- 전체 `.venv/bin/python -m pytest -q`: **1662 passed, 3 skipped**(263 s, `.evidence/b7/pytest-full.log`). `node --check oilInput.js · shell.js` 통과.
- 화면(Playwright, MemoryRepo API + 정적 포털, 증거 `.evidence/b7/b7-ui-smoke-{deploy,nodeploy}.json` · png): 메뉴 → 항목 4개(한국어) → 이탈 여부 안 고르면 사유 →
  이탈 입력 → "경보 만듦 · 배포된 흐름 — 작동유 열화 대응 (학생 그림 예) (판본 1)" · 처리 건 링크 / 배포 없음 → "사람 검토" / 기준 안 → "경보 없음" ·
  화면 영문 id 0 · 페이지 오류 0 (각 8/8).

## 메인이 라이브로 확인할 순서 (합친 뒤, 배포 → 검사. 검사기 도는 동안 compose 금지)
0. 배포: process · agent · dmn-mcp 이미지 재빌드(파이썬 변경), 포털 정적 파일. `PROCESS_MODE=instance`, `ENTERPRISE_BACKEND=supabase`. 마이그레이션 없음.
1. **kg 상태 확인**(cypher-shell): `MATCH (p:AnomalyPattern {code:'OIL_ANALYSIS'})-[:DETECTS]->(:Symptom)-[:INDICATES]->(f:FailureMode) RETURN p.id, f.id;`(1행) ·
   `MATCH (r:Rule {id:'rule:cand-oil'}) OPTIONAL MATCH (r)-[:OUTPUTS]->(s) RETURN count(s);` — 0 이면 적재 전(수업 시작 상태). 이미 SOP-OIL-21 이 있으면
   (A098 라이브 적재) 지식 관리에서 그 배치를 되돌리거나 "적재 뒤" 단계부터 본다.
2. **적재 전 판단**: 아래 3~4를 먼저 하면 내장 판단의 원인 진단 task 가 보류(작업 보류 사유: "후보 선택 규칙 rule:cand-oil 은(는) 맞았지만 내놓는 조치(SOP)가 없다…").
3. **흐름 가져오기 · 배포**: 포털 판단 → 흐름 가져오기 → `tests/fixtures/bpmn/oil_maintenance_student.bpmn` 을 흐름 id `my_oil` 로 → 시작 조건 "경보" + **오일 분석 기준 이탈 (사람 입력)** 만 →
   task 부품(원인 진단 · 조치 후보 조회 · 규정 검토 · 우선순위·카드 작성 · 조치 카드 선택(담당 정비관리자) · 정비 작업지시 · 재분석 = 사람 task[정비관리자, 받을 값 work_order,
   칸 `recheck_result | 재분석 결과 | select | 정상,비정상`] · 정비 책임자 확인 = 사람 task[생산관리자]) → 분기: "정상" 선 `recheck_result == 정상`, 되돌아가는 선 "그 밖의 경우" →
   검사 통과 → 판본 등록 → 관리 → 흐름 판본 배포에서 `my_oil` 배포(경보 표에 OIL_ANALYSIS = 내가 배포한 흐름). (배포 전에 4를 하면 "사람 검토"로 가는 것도 한 번 확인)
4. **오일 분석 입력**: 포털 설비 → 오일 분석 입력 → HYD-01 · 수분 함량 · 620 · 예 · 메모 → "경보 만듦 · 배포된 흐름" → 처리 건 보기. 또는
   `curl -XPOST :8080/api/human-alerts -H 'content-type: application/json' -d '{"pattern":"OIL_ANALYSIS","asset":"HYD-01","item":"water","value":620,"out_of_spec":true,"by":"김정비"}'`.
   기준 안(`out_of_spec:false`) → `raised:false` + 사유, 처리 건 없음.
5. **HM-9 인제스천**(지식 관리, 워커 필요): `tests/fixtures/manuals/HM-9_oil-degradation-manual.md` 추출 → 검토 → SOP-OIL-21 을 `fm:oil-degradation`(REMEDIED_BY, kind work_order,
   승인 정비관리자)에 연결해 커밋 → 1의 `count(s)` ≥ 1. (A098 `scripts/probe_expert_answers_a098.py` 가 같은 경로를 자동으로 한다.)
6. **결정론 경로(AGENT_BRIDGE=legacy, 워커 정지)**: 4 다시 → 원인 진단(근거 "사람 입력 분석 결과: 수분 함량 기준 이탈 (김정비)", 1순위 산화) → 카드 SOP-OIL-21 →
   내 작업함/처리 건에서 정비관리자로 선택 → 작업지시 task DONE(CMMS 번호) · **설비 명령 0건**(`select count(*) from …`/감사 `CMD_PUBLISHED` 없음, cmd-gateway 로그 없음) →
   사건 CLOSED → 재분석 task 열림 → "비정상" → 원인 진단 새 행 · 사건 `AWAITING_APPROVAL`(이력 note `reopened for recheck …`) → 새 카드 · 승인 · 작업지시 2건째 →
   "정상" → 처리 건 COMPLETED(종결).
7. **실제 워커(AGENT_BRIDGE=off, 워커 1개)**: 4 → 워커가 dmn-mcp `diagnose(HYD-01, OIL_ANALYSIS[, alert_id])` 를 부르면 서버 기록의 사람 입력이 근거(도구 결과
   `causes[0].evidence[0].id = human:<alertId>`) → evaluate_cards · submit_decision → 카드 → 승인 → 작업지시 → 재분석 입력 → 종결. 워커 콘솔 로그의 도구 호출로 확인.
8. **작업지시 확인**: CMMS(업무 DB) 작업지시 행 2건(비정상 한 번 돌린 경우)과 사건 `superseded[0].kind = recheck`, 처리 건 기록 `INCIDENT_REOPENED_RECHECK`.

스스로 판정할 체크 질문:
- 오일 분석을 "기준 안"으로 넣었을 때 처리 건 목록이 정말 그대로인가? "기준 이탈"이면 감지기 경보와 같은 사건 화면에 입력자 이름이 남는가?
- 내 흐름을 배포하기 전에 같은 입력을 넣으면 "사람 검토(미지원 경보 현장 검토)"로 가는가 — 기준 흐름이 작동유를 대신 처리하지 않는가?
- 작업지시까지 가는 동안 설비 명령(PLC)이 한 번이라도 나갔는가? 재분석 "비정상" 뒤 새 승인 없이 작업지시가 다시 나가는가(나가면 안 된다)?

## 남은 위험
- **실제 워커는 라이브 1회에서 원인 진단까지 확인**(10-08, 산화 · 사람 입력 근거, HANDOFF A159) — 승인 뒤 단계는 미확인: 원인 진단 에이전트가 dmn-mcp `diagnose` 를 부르지 않고 그래프를 직접 조회하면 증거 규칙이 없어 보류할 수 있다(지시문은 기준 정의 고정).
  도구 설명에 사람 입력 근거를 적었고, 서버 기록이 근거라 위조는 막지만, LLM 이 그 도구를 고르는지는 7번에서 확인. `alert_id` 없이 부르면 그 설비 · 패턴의
  가장 최근 처리 중 사람 입력 경보를 쓴다(같은 설비에 오일 분석 처리 건이 둘 열려 있으면 최근 것).
- 재분석 "비정상"의 다시 열기는 **모든 경로가 끝보다 승인을 먼저 만나는 task 로 되돌아갈 때만**. 승인 대신 "조치 카드 선택" 없이 작업지시로 바로 돌아가는 선은 B3 가
  거절하고, 승인으로 곧장 돌아가는 선(같은 판단 재사용)은 첫 판단이 이미 승인돼 `decision is APPROVED` 로 거절된다 — 새 판단(에이전트 부품)부터 다시 그려야 한다(사유가 보임).
- 다시 열기는 커밋 뒤 효과(사건 저장은 process 메모리 + 파일 저장)다. 커밋과 다시 열기 사이에 죽으면 다음 폴링(`reconcile_terminal_incidents`)이 다시 연다(시험) —
  그 사이 원인 진단이 끝나면 카드 저장(`update_incident_card`)이 한 번 실패하고 재시도된다.
- 회복 기준 `TS1 < 55` 는 사람 입력 패턴에 쓰이지 않는 자리 채움(alert_policy 계약상 필수). 학생이 작동유 흐름에 설비 명령 · 재관측을 넣으면 해제(CLEAR)가 오지 않아
  재관측이 상급자로 간다 — 설계상 "사람 재분석이 회복 판단"이지만 화면에 그 이유가 따로 적히지는 않는다.
- 시간 초과 갈래(정비 책임자 확인 → 끝)로 처리 건이 끝나도 사건은 승인 대기로 남는다 — 기준 흐름의 상급자 호출 끝과 같은 기존 동작(B7 범위 밖).
- `/api/human-alerts/current` 는 끝나지 않은 사건만 본다(메모리 `incidents`). process 재기동 뒤에도 사건 저장소에서 복원되는 범위에서 동작.
- HANDOFF §9 · TODO B7 줄 · 작업보고는 합칠 때 메인이 갱신(공유 파일 충돌 회피, B3 와 같은 방식).
