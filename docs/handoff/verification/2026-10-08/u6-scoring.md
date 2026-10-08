# U6 판단 채점 (확정 TODO A4 · 실험 E5 · 랩업 L6·L18 · 실라버스 37·38)

2026-10-08 밤, 단위 U6(worktree `agent-aeddf82d751ea21dd`). 범위: 메인 `TODO.md` 확정 TODO §0, §1 A4, E5, §2 L6·L18.
완료 기준(A4): 일부러 틀리면 점수 하락, 내장 정답 0.

## 1. 한 줄 요약
사람이 화면(또는 CLI·API)에서 적은 정답표에 AI 판단을 대어 점수를 내고, 실행마다 그때의 지식 그래프 지문을 함께 남겨 두 실행을 고르면 점수 변화와 **두 실행 사이에 끊긴·생긴 관계**를 나란히 보여 준다. 정답표는 처음엔 비어 있고 코드·시드·파일 어디에도 정답이 없다.

비유: 시험지(정답표)는 선생님이 칠판에 쓰고, 채점기(순수 함수)는 시험지를 모른다. 교과서(지식 그래프)를 한 장 찢기 전·후로 같은 시험을 보면 몇 점이 떨어졌고 어느 쪽이 찢겼는지 같이 나온다.

## 2. 무엇을 만들었나
| 층 | 파일 | 내용 |
|---|---|---|
| 순수 로직 | `it/process/procsvc/judgment_eval.py` | 항목 검사 `validate_item`·지문 `item_hash`, 판단 정규화(`normalize_decision`·`normalize_evaluation`·`worker_judgement`), **채점 `score_judgement`**, 반복 `aggregate`(흔들림·결정론 `identical`), 실행 `new_run`, 지식 상태 `knowledge_state`·차이 `knowledge_diff`, 전후 `compare`, 저장소 `MemoryEvalStore`·`PgEvalStore` |
| HTTP | `it/process/procsvc/eval_api.py` (`main.py`에 등록 7줄) | 정답표 CRUD(저장 때 인용 id를 Neo4j에 물어 없으면 400), 지식 상태, 워커 후보, 채점 실행(규칙 판단·에이전트 읽기 평가·지난 처리 건), 실행 목록·상세·비교 |
| 저장 | `it/supabase/migrations/20261008000030_judgment_eval_runs.sql` | `judgment_golden_items`(정답표, 시드 없음), `judgment_eval_runs`(실행, insert·select만 — 불변) |
| 화면 | `it/portal/www/evaluation.js` (`window.hydEval.mount(el)`), `index.html` 최소 변경(메뉴 버튼 1줄 · 컨테이너 `<section id="view-evaluation"><div id="evalView">` · 스크립트 1줄) | ① 정답표(빈 상태 안내 → 새 항목 적기·고치기·지우기) ② 채점 실행(경로·반복·담당자·메모, 지난 처리 건 고르기) ③ 실행 기록(목록 → 상세: 항목별 점수·판단·검사 네 칸 바로 보임, 회차·순위는 접기) ④ 전·후 비교(지식 변화·항목별 점수·바뀐 검사·잃은/얻은 근거) |
| CLI | `scripts/evaluate_judgment.py` | `golden`·`golden-put`·`golden-del`·`knowledge`·`run`·`runs`·`show`·`compare` (API), `score item.json judged.json`(오프라인, 같은 순수 함수 — L18 "내 점수와 포털 점수 일치") |
| 시험 | `tests/test_judgment_eval.py` (35개) | 시험 코드 안의 가짜 정답표로만 |

### 판단 경로 (모두 읽기 전용 — 처리 건·설비 명령·기준 데이터 변경 없음)
- `decide` 규칙 판단: agent `POST /api/agent/decide`(`it/agent/agentsvc/main.py:293`)에 정답표의 가정 사실을 넣는다. LLM 없음 → 결정론. N회가 모두 같으면 "N회 모두 같음 — 결정론적이라 1회와 같습니다"로 한 번만 보인다.
- `evaluate` 에이전트 읽기 평가: agent `POST /api/agent/evaluate`(`main.py:183`, `pipeline(do_submit=False)`)에 채점 전용 경보 id(`EVAL-…`)로 전체 파이프라인을 돌린다. 사실은 지금 값이므로 정답표 가정과 다르면 항목에 "사실 다름"을 표시한다(점수는 그대로, 숨기지 않음).
- `worker` 지난 처리 건: 처리 건 변수(`task:diagnose` 출력 cause·failure_mode·guide_card, `task:rank` 출력 decision_id — `it/process/definitions/anomaly_response_v22.json`)와 process에 제출된 판단(`book`)을 채점. 같은 정답표 항목에 맞는 처리 건 여러 개는 반복으로 묶어 흔들림을 잰다.

### 점수 (가중치 0.3·0.3·0.2·0.2, 합 100)
원인 적중(원인+고장 유형) · 1위 허용(추천이 허용 목록 안) · 빠질 조치 미추천(`제외돼야 함`=후보 아님 또는 규칙으로 제외 / `1위면 안 됨`=추천 아님, 비율) · 근거 포함률(통과한 증거·발동 규칙·조치 출처·카드 인용 안에 있어야 할 id 비율). 보류·오류·가드레일·빈 후보는 0점(부분 점수 없음). 에이전트 연결 실패는 0점이 아니라 503(실행 저장 안 함).

### 지식 상태 (E5)
실행마다 Neo4j에서 노드·관계 수, 매뉴얼·DDL 배치·KnowledgeEdit 마지막 시각, **지문**(모든 `(id)-[유형]->(id)` + 항목 속성 해시)과 스냅숏(관계 목록·항목별 해시, 5만 개 이하)을 남긴다. Neo4j Browser에서 관계 하나를 끊으면 기록 시각은 없어도 지문이 바뀌고, 비교 화면이 "끊김 A —유형→ B"로 보여 준다. 시각 기록이 없으면 "기록된 변경 없음"으로 적고 지어내지 않는다. 정답표 항목을 두 실행 사이에 고쳤으면 그 항목에 "정답표 바뀜"을 표시해 점수 변화가 지식 때문인지 정답 때문인지 가린다.

## 3. A10이 쓸 순수 함수 (네트워크·DB 없음)
`procsvc.judgment_eval` 의
- `score_judgement(item, judged, weights=None) -> {score, checks{cause,top,forbidden,evidence}, outcome, facts_mismatch, …}` — 채점 본체
- `normalize_decision(decision, causes=None, extra_cited=None)` — agent decide 응답·process 판단 → `judged`
- `normalize_evaluation(run)` — agent evaluate 실행 기록 → `judged`
- `worker_judgement(candidate, decision, guide_card=None)` — 처리 건 → `judged`
- `aggregate(item, judged_runs, weights=None, deterministic=False)` — 반복·흔들림
- `compare(run_a, run_b)` · `knowledge_diff(k_a, k_b)` — 전후
- `validate_item(item)` · `item_hash(item)` — 정답표 항목(데이터) 검사·지문

## 4. 원본과의 대응·차이
| 원본(파일:줄) | 원본이 하는 것 | HYD | 판정 |
|---|---|---|---|
| ontology-studio@20afcde `skills/ontology-build/references/validation.md:62-72` | 사용자가 입력한 골든 퀘스천마다 answerable/partial/not_yet·확신도를 에이전트 리포트로 | HYD는 질문이 아니라 **경보 판단**(원인·조치 순위·근거)을 정답표에 대어 숫자 점수로 | 차이 있음, 유지 — 회의 L136~138 "상황을 던졌을 때 진단·판단·액션까지"를 재는 것이 목적. 문서별 질문 확인은 기존 A118(`procsvc/manual_golden.py`)이 담당 |
| ontology-studio@20afcde `frontend/src/features/ontology/GoldenQuestionReviewPanel.vue:24-40` | 사람이 답마다 "맞다/틀리다"를 누름 | 사람이 **먼저** 정답을 적고 채점은 자동 | 차이 있음, 유지 — 같은 판단을 반복·전후 비교하려면 사람 판정을 매번 다시 할 수 없다 |
| 같은 저장소(확인 범위) | 실행 저장·두 실행 비교 확인 못 함 | 실행 불변 저장 + 전후 비교 + 지식 지문 | HYD 추가(A4 완료 기준) |
| process-gpt-vue3 | 판단 채점 화면 없음(`screens-vue3.md` §2 끝 "8(AI 판단 채점 — 원본은 ontology-studio 골든 퀘스천)") | 레이아웃만 vue3식(목록 → 상세, 섹션 구분) | — |

## 5. 이전 미완성본에서 바꾼 것
- 내장 정답 `it/process/procsvc/judgment_golden.json`(6항목) **삭제**. `load_golden`·`GOLDEN_PATH` 제거 → 정답표는 저장소(`judgment_golden_items`)의 데이터, 처음엔 빈 목록.
- `mode: server|worker` → `path: decide|evaluate|worker` (agent `evaluate` 경로 추가).
- 지식 상태에 지문·스냅숏 추가(기록 없는 관계 끊기도 감지), 비교에 지식 차이·정답표 바뀜·잃은/얻은 근거 추가.
- `index.html`에 그려 두었던 화면 골격(29줄)을 빼고 `evaluation.js`가 `#evalView`에 그린다(U7 셸 재편 대비).
- 워커 경로: 처리 건 변수의 `guide_card`(실제 워커 출력)를 근거로 먼저 쓰고, 같은 항목 처리 건 여러 개를 반복으로 묶음.

## 6. 시험 결과
- `tests/test_judgment_eval.py` 35 passed (`.evidence/U6/pytest-judgment-eval.txt`).
  - 내장 정답 0: `judgment_golden.json` 없음, 제품 코드 4개 파일에 온톨로지 id 문자열 0, 마이그레이션에 insert 0, 새 저장소의 `GET /api/eval/golden` → `items: []`, 빈 정답표로 채점하면 400.
  - 일부러 틀리면 점수 하락: 원인 틀림 70, 1위 틀림 70, 금지 조치 1위 50, 근거 빠짐 <100, 보류·오류·가드레일 0, 규칙 제외 대신 낮은 순위면 빠질 조치 검사 실패, 정답표를 바꾸면 같은 판단도 점수 변화(100→70).
  - 비교 계산: 관계 하나 끊은 뒤 실행 → `removed_rels`에 그 관계, 항목 `regressed`·`evidence_lost`, 평균 변화 −25, 정답표 바뀐 항목 표시, 순서 뒤집으면 `improved`.
  - HTTP: 정답표 CRUD(중복 409, 그래프에 없는 id 400, 그래프 끊김 503, 감사 기록), 반복 2회 결정론 `identical`, evaluate 경로 사실 다름 표시, worker 경로 2건 → 반복 2·흔들림 0.5, 에이전트 연결 실패 503·저장 안 함.
  - CLI `score` 오프라인 점수 = 포털 함수 점수(100·50).
- 전체 `pytest -q`: **1319 passed** (worktree, 2026-10-08).
- `node --check it/portal/www/evaluation.js` 통과.

## 7. 라이브 확인 (합친 뒤 메인이 1회)
docker 금지라 이 단위에서는 돌리지 않았다. 확인 경로:
1. Supabase에 마이그레이션 30 적용 → `PROCESS_MODE=instance`로 process 재기동.
2. 포털 "판단 채점" → 빈 정답표 안내 확인 → 쿨러 항목 하나 적기(그래프에 없는 id를 넣으면 거부되는지).
3. "규칙 판단" 1회 채점 → Neo4j Browser에서 그 항목 근거 관계 하나 삭제(예: 원인 → 증거) → 다시 채점 → 비교에서 끊긴 관계·점수 하락 확인 → 관계 복구.
4. "지난 처리 건" 경로: 쿨러 처리 건 1건(워커) 뒤 후보 목록에 나오고 채점되는지.
5. CLI: `python scripts/evaluate_judgment.py runs` / `compare A B`.
미검증(라이브 필요): `PgEvalStore` SQL, Neo4j 지문 질의(`KNOWLEDGE_RELS_Q`·`KNOWLEDGE_NODES_Q`)의 실제 그래프 크기·시간, agent evaluate 경로의 실제 응답 모양.

## 8. 사용자가 스스로 판정할 체크 질문
- 정답표를 다 지운 상태에서 채점 버튼이 막히고 "비어 있습니다"가 보이는가? (내장 정답이 있다면 점수가 나왔을 것)
- 관계 하나를 끊고 다시 채점했을 때, 비교 화면이 **어느 관계**가 끊겼는지와 **어느 항목·검사**가 떨어졌는지를 같이 보여 주는가?
- 같은 판단에 정답표의 허용 1위 조치만 바꿨을 때 점수가 바뀌고, 비교에 "정답표 바뀜"이 붙는가?
- CLI `score`로 낸 내 점수와 포털 점수가 같은가? (L18)
