# 매뉴얼 개정 적재 · 충돌 표시 · 실패 task 처리 수정 (F-1 · F-2 · F-3, 2026-10-10)

작업 위치: merge-preview 워크트리. 근거: `live-final.md` 발견 표 F-1~F-3, DECISIONS 35절.
범위: 코드 · 단위 시험만. 라이브 스택 · 워커 · docker는 건드리지 않음(메인이 반영). 절마다 덧붙임.

## 0. 통독 — 완료
점검표, 공용 헌법, 프로젝트 CLAUDE.md, DECISIONS 35절(+20절), live-final.md 읽음.

## 1. F-1 — 추출 결과의 SOP 충돌 표시가 자기 문서를 '다른 문서'로 표시 — 결함, 고침, 검증됨(단위)

- **원인**: 문서의 그래프 식별 키(`sha256(tenant):document_id`, 노드의 `_manual_document`)를 세 곳이 각자 만들었고(`manual_review.py:191`,
  `manual_graph.py:311` head, `manual_api.py:63` knowledge_conflicts), `manual_api.py:58-59`의 `sop_conflicts`만 날 `document_id`를 넘겼다.
  `manual_graph.sop_conflicts`(148-154)는 `owner != document`면 other_document로 내므로 자기 SOP가 모두 '다른 문서'로 나왔다.
- **분류**: 결함(백엔드 검토 보조 정보). 적재 판정(`_validate_targets`)은 plan['document']를 쓰므로 영향 없었음.
- **조치**: 키를 `manual_review.document_key(tenant, document_id)` 한 곳에서 만든다(manual_review가 가장 아래 모듈 — manual_graph가 이미 import).
  `manual_review.validate`, `manual_graph.head`, `manual_api.extraction_result`(SOP · 지식 충돌 둘 다 같은 키)가 이를 쓴다. `sha256(tenant` 검색 결과 이제 1곳.
- **시험**: `tests/test_manual_extraction.py::test_f1_review_conflicts_do_not_call_the_documents_own_sops_another_documents` — 실제 API 경로
  (`GET …/extractions/{id}`), 그래프에는 `manual_graph.desired`가 쓰는 태그로 이 문서가 SOP를 소유. 자기 SOP → conflicts `[]`, 지식 충돌도 같은 키,
  같은 번호를 다른 문서가 가지면 여전히 `other_document`. 통과.
- **뮤테이션**: `manual_api`에서 키를 날 id로 되돌림 → 실패(`owner … kind: other_document` — 라이브 2-3과 같은 증상). 되돌린 뒤 통과.

## 2. F-2 — 매뉴얼 개정 적재가 판단 이력 참조에 막힘 — 설계(구현 전 기록)

- **원인(확인)**: `manual_graph._snapshot`(67-90)이 문서 소유 노드에 닿는 *모든* 관계를 스냅숏에 넣고, `commit`(253-255)이 저널(after = `desired`)과 통째로 비교한다.
  저널에는 실행 이력이 없으므로 `case_projection.py:47` `MERGE (x:DecisionCase)-[:CHOSE]->(s:Skill)`이 문서 소유 Skill에 붙는 순간 문서가 영원히 개정 불가.
  게다가 `_replace`(183-214)는 소유 노드를 전부 `DELETE`하고 다시 `CREATE`하므로, 비교를 풀더라도 이력이 붙은 노드는 지울 수 없다(지우면 감사 기록이 끊김).
- **문서 소유 노드에 붙는 실행 이력(코드에서 확인)**: `case_projection.py` 두 쿼리뿐 —
  `DECISION_CASE_Q` `(DecisionCase)-[:CHOSE]->(Skill)`(47행), `INCIDENT_Q` `(Incident)-[:DIAGNOSED_AS]->(Cause)`(33행, Cause는 C1부터 문서 소유 가능).
  `execution_graph.py`의 실행 투영은 FlowNode · Role · System · Asset · Incident에만 닿아 문서 라벨에 닿지 않음. `skill_graph.py:54` `Rule-OUTPUTS->Skill`은 관리자 지식 쓰기(이력 아님).
- **결정(메인)대로 구현할 것**:
  (a) 새 판에도 같은 (라벨, id)로 남는 노드는 제자리에서 속성만 바꾼다(`SET n = 새 속성`, 지우지 않음). 문서 소유 관계는 지금처럼 기록 대조로 지우고 새로 만든다.
  (b) 새 판에서 빠지는 노드에 이력 관계가 있으면 노드 · 관계 종류 · 건수를 밝혀 409로 거절(쓰기 전에 검사, 한 트랜잭션).
  (c) 스냅숏을 '문서 그래프'와 '허용된 이력 관계'로 나눈다. 허용 목록 = `HISTORY_RELATIONS`(위 두 종류, 이력 쪽 끝이 문서 밖 노드일 때만).
      문서 그래프 비교는 지금처럼 엄격 — 사람이 고친 노드 · 관계, 목록에 없는 바깥 관계는 무엇이 다른지 밝혀 409.
  되돌리기도 같은 분리 · 제자리 갱신 · (b) 거절. 배치 기록의 before/after에는 문서 그래프만 남긴다(이력은 다시 만들지 않음 — 지워지지 않았으므로).
  영수증에 보존한 이력(`history_kept`: 노드 · 관계 종류 · 건수)을 남겨 처리 기록에서 읽히게 한다.

## 2-1. F-2 — 구현 · 검증 — 고침, 검증됨(버릴 Neo4j 실제 Cypher), 라이브 미검증

- **분류**: 설계 충돌 → 메인 결정대로 구현(결함 수정).
- **조치** (`it/process/procsvc/manual_graph.py`):
  - `HISTORY_RELATIONS`(명시 목록 2종) · `_is_history`: 문서 밖 노드 → 문서 소유 노드 방향, 목록의 (바깥 라벨, 관계, 소유 라벨)일 때만 이력.
  - `_snapshot` → `(문서 그래프, 이력)`. 판별은 끝점이 소유 노드 집합(elementId)에 드는지로 한다. 그 밖의 바깥 관계는 문서 그래프에 남아 비교에서 걸린다.
  - `_check_unchanged`: 판정은 그대로 전체 동일성. 다르면 `_drift`가 기록에 없는 노드 · 사라진 노드 · 속성이 바뀐 노드 · 기록에 없는 관계 · 사라지거나 바뀐 관계를
    종류별 건수와 앞 5개(`DRIFT_SHOWN`) 이름으로 409 메시지에 적는다(라이브 2-4처럼 읽기 전용 비교 스크립트를 따로 돌릴 필요 없음).
  - `_replace(tx, current, target, history)`: ① 빠지는 노드에 이력이 있으면 쓰기 전에 409(`새 판에서 빠지는 노드에 판단 이력이 연결돼 있어 거절했습니다 … Skill skill:x ← CHOSE N건`)
    ② 문서 관계는 기록 대조로 지움(그대로) ③ 빠지는 노드만 `DELETE`(DETACH 아님 — 남은 관계가 있으면 트랜잭션 실패) ④ 남는 노드는 `SET n = 새 속성`(1건 아니면 409) ⑤ 새 노드 CREATE ⑥ 새 관계 CREATE.
  - `commit`/`rollback` 모두 같은 경로. 배치 기록 before/after에는 문서 그래프만 저장(이력은 지워지지 않으므로 되돌릴 때 다시 만들지 않음 — 중복 방지).
    영수증 · 되돌리기 결과에 `history_kept`(노드 · 관계 종류 · 건수). 모두 한 `execute_write` 트랜잭션.
  - 옛 배치 기록과의 호환: 옛 코드는 before == 저널(= `desired`, 이력 없음)을 요구했으므로 옛 before에는 이력 관계가 없다 — 변환 불필요.
  - `scripts/probe_manual_graph.py`(라이브 검사기)가 `_snapshot` · `_replace`를 직접 써서 새 반환 · 인자에 맞춤.
  - DECISIONS 35절에 보강 문단(메인 결정 · 허용 목록 · 거절 조건).
- **시험** `tests/test_manual_revision_history.py`(실제 그래프 시험은 `HYD_MANUAL_NEO4J_URI`/`HYD_MANUAL_NEO4J_PASSWORD`의 **버릴 빈 Neo4j**에서만 — 노드가 있으면 실패로 멈춤, 저장소의 `HYD_*_PG_DSN` 관례):
  - 순수(항상 실행): 허용 목록이 `case_projection.py` 실제 쿼리(`MERGE (x)-[:CHOSE]->(s)` · `MERGE (i)-[:DIAGNOSED_AS]->(c)`)와 같은지, 문서 관계 종류와 겹치지 않는지 / `_is_history` 7가지(허용 2 · 양끝 소유 · 역방향 · 모르는 관계 · 모르는 바깥 라벨 · 선언 안 된 소유 라벨).
  - Neo4j(이력은 실제 생산자 `case_projection.DECISION_CASE_Q`로 만듦):
    1. 이력 3건이 붙은 Skill이 남는 개정 성공 — 같은 Skill 노드(elementId 동일)에 이력 3건 그대로, Step 문장 · 개수 새 판대로(옛 Step 안 남음), `history_kept` 정확. 이어 되돌리기도 성공 · 이력 유지 · 문서 그래프 = 복원된 저널.
    2. 이력이 붙은 Skill이 빠지는 개정 → 409(`Skill skill:sop-ref-92 ← CHOSE 1건`), head · 이력 · 옛 그래프 그대로. 첫 배치 되돌리기도 같은 이유로 409.
    3. 손으로 고친 Skill 이름(허용 이력이 함께 있어도) → 409 `속성이 바뀐 노드 1건: Skill …`, 되돌리기도 409.
    4. 모르는 바깥 관계 `(DecisionCase)-[:CITES]->`, `(Execution)-[:CHOSE]->` → 409 `(… x:1)-[:…]->(Skill …)` 명시.
  - 결과: 13 passed(버릴 Neo4j 5.26.31, `docker run` 별도 컨테이너 · 포트 17687, compose · 라이브 스택 미접촉). 환경변수 없으면 8 passed · 5 skipped.
- **뮤테이션** (각 1회, 되돌린 뒤 13 passed):
  | 뮤테이션 | 잡은 시험 |
  |---|---|
  | M1 이력 분리 없음(`_is_history` 항상 False — 고치기 전 동작) | 유지 개정 · 빠지는 노드 거절 · 판별 2건 실패(유지 개정은 라이브와 같은 409) |
  | M2 빠지는 노드 이력 검사 없음 | 빠지는 노드 거절 실패(Neo4j 노드 삭제 오류로 끝나 이름 있는 409가 아님) |
  | M3 노드 속성 비교 없음(관계만 비교) | 손 수정 거절 실패 |
  | M4 바깥 관계 무조건 이력 | 모르는 바깥 관계 2건 · 판별 4건 등 실패 |
- **기존 라이브 검사기 사본 실행**: `probe_manual_graph.py`를 버릴 Neo4j로 향하게 한 사본 → **17/17 PASS**(동시 8요청 1배치, 규칙 참조 거절, 외부 속성 거절, 되돌리기 복원 등 기존 계약 회귀 없음).
  증거 `.evidence/a161-final/manual-revision-fix/probe-manual-graph-throwaway.json`, 사본 `probe_throwaway.py`.
- **미검증**: 실제 구조판 그래프(`hyd-iot-edu_neo4j-data-c3`)에서 PR-07 새 판 적재(SOP-PUR-13에 CHOSE 3건). Cause 쪽 이력(`Incident-DIAGNOSED_AS->Cause`)은 판별 단위 시험만(문서 소유 Cause를 만드는 지식 적재까지 실제 그래프로는 안 돌림).

## 3. F-3 — 워커가 실패로 끝낸 에이전트 task — 끝내기 경로는 이미 있음(운용 오해), 추출 결과 API의 실패 표시는 결함 → 고침

생산자 → 소비자 추적(파일:줄):
1. 워커: `it/agent-worker/worker/runner.py:96` 실행 예외 → `_fail`(412-421) → `repo.update_task_error`(413) = `procdb.py:898` `set_draft_status('FAILED')` —
   행은 `status=IN_PROGRESS`, `draft_status=FAILED`, `consumer=None`. 같은 곳에서 `TASK_ERROR` error 이벤트(원문 `raw_error`, 안내 "담당자가 확인한 뒤 다시 보낼 수 있습니다").
   라이브 실물 일치: 정리 백업 `.evidence/a161-final/residue-extract-limit/backup.json`의 todo `866a2c12…` = IN_PROGRESS · FAILED · consumer None, `worker2.log:15` `failed: RunFailed: You've hit your session limit`.
2. 처리 건 화면: `it/portal/www/trace.js:233` · `caseRecord.js:132` — `draft_status === 'FAILED'`면 단계 상태 'fail'(실패로 보임).
3. 끝내기: `instances.py:766-818` `close_agent_task`(A082) — `IN_PROGRESS + draft FAILED/CANCELLED` 또는 PENDING을 사유와 함께 CANCELLED, 혼자 남은 처리 건은 `closed-by-human`으로 끝냄.
   API `POST /api/todolist/{wid}/close`(`instance_mode.py:1048-1058`), 포털 '단계 닫기' 버튼(`instances.js:392`, 정확히 같은 조건). 시험 `tests/test_close_agent_task.py`(문서 추출 + `update_task_error`로 죽은 실행을 닫는 사례 그대로) 10 passed.
   `/cancel`(1060-1070, `cancel_agent_task` 744-764)은 **실행 중(STARTED · 점유 있음)인 실행을 멈추라는 요청**이라 실패한 행을 거절하는 것이 맞다.
4. 다시 하기: 문서 추출은 같은 원천에 새 추출 요청(`POST …/extractions`, 포털 '에이전트 추출 요청') — 라이브 2-3이 실제로 그렇게 다시 돌렸다. 사건 처리 건의 에이전트 단계는 '다시 수행'(rework).

- **분류 ①(끝내기 · 실패 표시)**: 오해 — 경로가 있는데 라이브 운용이 `/cancel`을 썼다. `live-final.md` F-3의 "실패한 task를 끝낼 API가 없다"는 틀린 진단. **고치지 않음.**
- **분류 ②(추출 결과의 상태)**: 결함 — `manual_extraction._task_state`(고치기 전 258행)가 `status=wi['status']`만 내서 죽은 실행을 계속 `IN_PROGRESS`로 돌려줬다.
  그래서 `scripts/c3_ingest.py:159`(FAILED · CANCELLED면 멈춤)가 실패를 못 보고 시간 한도까지 폴링(라이브에서 pkill), 지식 화면 '추출 상태'(`hitl.js:494`)도 '진행 중'으로 표시.
  구간 추출의 `STATUS_RANK`(`'FAILED':0`)도 행 status가 FAILED가 될 일이 없어 죽은 값이었다.
- **조치**: `it/process/procsvc/manual_extraction.py` `STOPPED_RUNS=('FAILED','CANCELLED')` — 행이 IN_PROGRESS이고 draft가 그중 하나면 추출 상태를 그 값으로 보고.
  사람이 닫으면 행이 CANCELLED라 CANCELLED. instances.py · instance_mode.py · 포털은 건드리지 않음(다른 담당 작업 중 파일).
- **시험**: `tests/test_manual_extraction.py::test_f3_a_failed_worker_run_reads_as_failed_and_a_person_can_close_it_and_extract_again` — 실제 `Runner`가 CLI 오류 결과
  (`You've hit your session limit …`, is_error)로 task를 실패시킴 → 행 IN_PROGRESS · FAILED, TASK_ERROR 원문 → 결과 API `status: FAILED`, preview 없음 → `close_agent_task` → `CANCELLED`, 처리 건 COMPLETED → 새 추출 요청은 새 처리 건으로 IN_PROGRESS. 통과.
- **뮤테이션**: 상태를 `wi['status']`로 되돌림 → `'IN_PROGRESS' == 'FAILED'` 실패(라이브 증상). 되돌린 뒤 파일 34 passed.
- **참고 레포**: 경로가 이미 있어 새로 맞출 것이 없음(A082/A097이 process-gpt-vue3 FormWorkItem 취소 · 닫기를 따른 것). 대조하지 않음.

## 4. 회귀 · 정리 — 검증됨(단위)

- 관련 파일(`test_manual_*` · `test_c1_knowledge` · `test_c1_scenario_b` · `test_b7_oil` · `test_c3_bc_review`, 버릴 Neo4j 포함): 215 passed(F-3 전). `test_close_agent_task.py` 10 passed.
- 전체 스위트 1회(F-1~F-3 반영, Neo4j 환경변수 없음): **1967 passed · 9 skipped · 1 failed** — 실패는 알려진 흔들림
  `tests/test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint`, 단독 재실행 1 passed. skipped 9 중 5는 이번 Neo4j 시험(환경변수 없으면 건너뜀).
- 버릴 Neo4j 컨테이너 `mrf-neo4j-throwaway`와 그 익명 볼륨 2개 지움. 라이브 스택 미접촉(process StartedAt 2026-10-09T20:58:13Z, RestartCount 0 그대로). docker compose · 워커 · push 없음.

## 5. 라이브에서 확인할 절차(메인 몫 — 미검증)

1. process 이미지에 반영(`manual_graph.py` · `manual_review.py` · `manual_api.py` · `manual_extraction.py`) 뒤 `docker inspect hyd-iot-edu-process-1 --format '{{.State.StartedAt}} {{.RestartCount}}'`로 안정 확인.
2. neo4j를 구조판 볼륨 `hyd-iot-edu_neo4j-data-c3`로(live-final 2-1과 같은 덮어쓰기). 판단 이력 확인:
   `MATCH (c:DecisionCase)-[:CHOSE]->(k:Skill {id:'skill:sop-pur-13'}) RETURN count(c)` = 3, `elementId(k)` 기록.
3. F-1: `GET /api/kg/manuals/sources/{PR-07 새 판 source}/extractions/{059b0927…}` → `preview.conflicts`에 SOP-PUR-11/12/13이 **없어야** 한다(자기 문서).
4. F-2: `c3_ingest.py commit PR-07 --review review3-PR-07.json`(또는 같은 추출로 새 검토) → 200, 영수증 `history_kept`에 `Skill skill:sop-pur-13 · CHOSE · 3`.
   적재 뒤 2의 질의가 같은 elementId에 3건, 문서 head가 새 배치, SOP-PUR-13 link 값 · 불량률 규칙이 새 판대로.
   (새 판에서 빠지는 노드에 이력이 있으면 409 메시지가 노드 · 관계 · 건수를 말해야 함 — PR-07은 SOP 셋이 그대로라 해당 없음 예상.)
5. F-3(선택): 실패한 에이전트 task는 처리 건 화면 '단계 닫기'(또는 `POST /api/todolist/{wid}/close` `{by, reason}`)로 끝낸다 — `/cancel` 아님.
   추출 결과 `GET …/extractions/{id}`가 실패 실행에 `status: FAILED`를 돌려주는지(워커 실패를 다시 일으키기는 어려우므로 다음 실패 때 확인).
