# A6 영문 · 시험 잔재 0 (2026-10-08 밤, worktree `a6-residue`)

범위: `TODO.md` 확정 TODO §1 **A6** — 회귀 검사기 영문 사유 → 한국어 "[회귀 검사]" 표기, 회귀 뒤 정리. 인수 기준 "포털 영문·시험 문구 0".
docker·compose는 쓰지 않았다(라이브 확인은 메인이 합친 뒤). 잔재 정리 스크립트는 임시 PostgreSQL 16 클러스터(시험 뒤 삭제)로만 돌렸다.

## 1. 결론
1. 검사기 53개 파일(`probe_*` 49 · `scenario_*test` 3 · `run_scenario_pump_fan_evidence`)이 처리 DB·그래프에 남기는 사유·담당자·메모·설명·정의/단계 이름·격리 테넌트 이름을
   한국어 `[회귀 검사] …`로 바꿨다(155줄, 표식 202개 — 영문 값 번역 + 한국어지만 표식 없던 시험 사유·담당자에 표식). 같은 문자열을 다시 비교하는 단언은 같은 값으로 함께 바꿔 검사 의미는 그대로다.
2. 잔재 정리: 새 `scripts/mark_regression_residue.py`(처리 DB, 기본 dry-run)와 기존 `scripts/cleanup_residue_cases.py`에 `--marker [--legacy]`(그래프 선례)를 더했다.
   둘 다 같은 표식 목록(MARKER·LEGACY)을 쓴다. **실행은 메인**이 한다(아래 §3 순서).
3. 포털: `UI.flowName`이 이름 없이 받는 끝 이벤트 id 5개, 상태 15개, 사건 기록 이벤트 11개에 한국어 용어를 더했다(`it/portal/www/ui.js` 줄 추가만).
4. 시험: 바꾼 파이썬 55개(검사기 53 + 정리 스크립트 2) `py_compile` 통과, `node --check ui.js` 통과, 전체 pytest **1284 passed**(122.9 s).

## 2. ① 검사기 문구 — 규칙과 결과

형식: 담당자(`by`)는 `[회귀 검사] A0xx 검사기/검토자/…`, 사유·메모는 `[회귀 검사] <한국어 문장>`. A번호는 증거 폴더와 잇기 위해 남겼다.
찾은 방법: AST 스캔(`.evidence/a6-residue/scan.py` — dict 키·키워드 인자 `by/reason/note/description/name/…`, 그리고 `reason/by` 매개변수를 가진 지역 함수의 위치 인자) +
"probe/fixture/reviewer/consent/acceptance…" 단어가 든 모든 문자열 상수 재검(메서드 위치 인자·테넌트 이름 같은 스캔 밖 자리). 바꾸기는 파일·줄을 지정한 정확 치환(`apply.py`·`apply_b.py`).

| 무엇 | 대표 예(파일:줄) | 바꾼 값 |
|---|---|---|
| 승인 사유(포털 "결정 사유"·"과거 같은 선택") | `probe_effect_compensation.py:127,146,156,224` "A072 probe: …" | `[회귀 검사] A072 첫 판단: 팬만 올림(OEM 오더는 전부하 유지)` 등 |
| 결정자·제출자 | `scenario_test.py:128,253`·`scenario_instance_test.py:290`·`run_scenario_pump_fan_evidence.py:340` "OP-17"/"test" | `[회귀 검사] 운전원` / `[회귀 검사] 권한 밖 승인 시도` |
| 사람 단계 메모(output.note) | `probe_decision_scope_live.py:155`, `probe_source_connection_failure.py:194`, `probe_source_persistence_failure.py:122` | 한국어 번역 + 표식 |
| 재작업·보류·재시도 요청 사유 | `probe_rework_*`, `probe_task_deferral_pg.py`, `probe_source_delivery.py`, `probe_source_inbox.py` | 〃 |
| 시나리오 검사 사유(한국어였지만 표식 없음) | `scenario_test.py:131`, `scenario_instance_test.py:294`, `scenario_pump_fan_test.py:151,209,239,258,273`, `run_scenario_pump_fan_evidence.py:247,342,381` | 앞에 `[회귀 검사] ` |
| 검사기가 등록한 정의·단계 이름 | `probe_rework_plan.py:29-30`, `probe_variable_provenance.py:26` | `[회귀 검사] 재작업 의존 미리보기 인수 시험` 등 |
| 그래프 고정 자료 | `probe_knowledge_live.py:56`(Process name), `probe_skill_http.py:33`·`probe_skill_edit_atomicity.py:26-27`·`probe_skill_authoring.py:58,70`(조치 방법 설명) | 〃 |
| 격리 테넌트 이름 | `probe_case_projection.py:50`, `probe_execution_projection.py:45`, `probe_knowledge_projection.py:38`, `probe_legacy_assessment_pg.py:46`, `probe_projection_receipts.py:46`, `probe_rework_generation_pg.py:54`, `probe_task_deferral_pg.py:53` | `[회귀 검사] A0xx 보존 … 시험` |
| CLI 인자 | `probe_projection_repair_live.py:95,110` `--by/--reason` | 〃 |

**단언을 같이 바꾼 곳**(같은 리터럴을 요청과 비교에 함께 씀): `probe_source_delivery.py:94,100,103-106`(history[-1].by·error), `probe_skill_http.py:59`(UI 수정 뒤 기대 설명 →
`[회귀 검사] A047 응답 유실 뒤 저장` — 이 시험을 손으로 돌리는 사람은 이 문구를 설명 칸에 넣는다), `probe_post_delivery_discard_pg.py:35,38`, `probe_task_deferral_pg.py:19,72,94,96`,
`probe_legacy_assessment_pg.py:18`(HELD.error ↔ :63 비교), `probe_skill_edit_atomicity.py:26-27`(복원 스냅숏 비교), `probe_projection_receipts.py:61,64,66,69`(재전송 동일성).
한 줄에 내부 결과 dict가 섞인 `probe_source_inbox.py:142`는 `work.finish(final,{'fixture':'duplicate'})`를 원래대로 두고 `retry_failed`의 by·reason만 바꿨다.

**바꾸지 않은 것(이유)**
- 시험 인물 이름 `이생산`·`김운전`·`운전원`: 이미 한국어이고 역할 이름과 같다. 잔재 판별은 함께 남는 사유의 표식으로 한다.
- 식별자: 정의 data 변수(`question`·`score`·`a_out`·`count`…), 역할 레인 이름(`Agent`·`reviewer`·`requester`), 사람 답변 명령 `answer:'resume'`.
- 시험 입력 자체: `probe_ingest_identity.py:77` SQL 주입 문자열, `probe_input_bindings.py`의 측정값(`measurement A`·`fixture review`, 출력값 비교에 쓰임), `probe_alert_triage.py:113` "원문 그대로 보존" 확인용 경보 원문, `probe_ingest_ownership.py:92-97` 격리 그래프 관계 속성, `probe_claim_scope.py:30` 내부 draft.
- 거절되어 저장되지 않는 값: `reason:'x'`(403/409 확인), 거절되는 조치 방법 이름(`changed name`·`stale`·`valid edit` — 끝에 지우는 격리 고정 자료).
- 지식 내용: `probe_expert_answers_a098.py`·`probe_knowledge_to_judgment.py:89`의 영향 note(`A098: …`, `A079: …`) — 매뉴얼·전문가 답으로 적재되는 지식 문장이라 시험 사유가 아니다.
- 내부 기록: `run_scenario_pump_fan_evidence.py:221`·`scenario_pump_fan_test.py:126` `stopped.reason='task pending'`(보고서 JSON만).
- 범위 밖 검사기: `scripts/stability_test.py:120`(by=`STABILITY-…` id, 판단 id와 같은 값으로 쓰임), `scripts/ui_check_a147.py`(이미 한국어 "시험"), `scripts/ui_regression.py`(UI 입력 "UI 검증자"·"UI 상태 유지 확인") — 목록만.

재스캔 결과 남은 영문 by/reason/note 값은 위 '바꾸지 않은 것' 5건뿐(`answer resume`, 주입 문자열, `original edge`, `task pending` 2).

## 3. ② 잔재 정리 — 메인이 실행할 순서(데이터 삭제는 dry-run 기본)

| 층 | 도구 | 찾는 법 | `--apply`가 하는 일 | 되돌리기 |
|---|---|---|---|---|
| 처리 DB(PG) 처리 건 | **새** `scripts/mark_regression_residue.py` | 표식 `[회귀 검사]`(+`--legacy`: 표식 도입 전 검사기 문구 정확 일치)이 events.data · todolist.output/log · 승인 outbox · 효과/재작업 영수증 · 처리 건 이름 중 한 곳에 있는 처리 건 | backup.json 먼저 → `bpm_proc_inst.is_deleted=true, deleted_at` · 열린 todolist → CANCELLED + log 표시 · Neo4j ProcessInstance/WorkItem 투영 삭제 | backup.json의 id로 `is_deleted=false` |
| 그래프 선례 | `scripts/cleanup_residue_cases.py --marker [--legacy]` (A6 추가, 기존 `--before`도 그대로) | DecisionCase.reason에 표식/옛 문구 | DecisionCase만 DETACH DELETE(backup.json 먼저) | backup.json |
| 지금 도는 RUNNING | 둘 다 손대지 않음 | `--keep-recent-min`(기본 30분) 안에 갱신된 RUNNING은 제외 | — | — |
| 시간 경계 잔재 | 기존 `cleanup_residue_instances.py --before` | RUNNING만 | 기존과 같음 | 기존과 같음 |

```bash
# 1) 목록만 (아무것도 안 바뀜) — report.json에 처리 건마다 어디서 어떤 문구로 걸렸는지 3줄 발췌
.venv/bin/python scripts/mark_regression_residue.py --out .evidence/<A>/residue-dry --legacy
.venv/bin/python scripts/cleanup_residue_cases.py --marker --legacy --out .evidence/<A>/cases-dry
# 2) report.json의 matches를 훑어 사람 것(학생·강사 입력)이 섞이지 않았는지 본 뒤 적용
.venv/bin/python scripts/mark_regression_residue.py --out .evidence/<A>/residue-apply --legacy --apply
.venv/bin/python scripts/cleanup_residue_cases.py --marker --legacy --out .evidence/<A>/cases-apply --apply
# 3) 다시 dry-run → residue_instances 0 확인
```
- Neo4j가 꺼져 있으면 `--apply`는 아무것도 바꾸지 않고 사유를 내고 멈춘다(PG만 숨기고 투영이 남는 반쪽 상태 방지). PG만 하려면 `--skip-graph`.
- **보고만 하는 것**(report.json): process SQLite 스냅숏의 사건·판단(`/api/incidents`·`/api/decisions`를 읽어 표식 든 id·건수만). 실행 중 process가 메모리 상태로 스냅숏을
  덮어쓰므로 이 스크립트는 고치지 않는다. 이 둘은 포털 "이상 확인·조치"·"승인과 실행"에 계속 보이지만 사유에 `[회귀 검사]`가 붙어 시험임이 드러난다.
  완전히 지우려면 process를 멈춘 상태에서 `/data/process.sqlite3`을 백업 뒤 손질해야 하며 이번 범위에서 자동화하지 않았다(사용자 결정 필요).
- 검사기가 만든 격리 테넌트(`tenants.id != hyd`, 이름이 이제 `[회귀 검사] …`)는 테넌트별 처리 건 수만 적는다. 테넌트 삭제는 cascade 삭제라 사용자에게 묻는다(CLAUDE.md §3).
- 검사기가 등록한 정의(proc_def.name에 표식)는 목록만 — 정리는 `cleanup_invalid_definitions.py` 쪽 판단.
- `--legacy` 목록은 표식 도입 전 실제로 쓰인 문구 정확 일치만 넣었다. `fixture`·`test`·`again` 같은 일반 단어와 시험 인물 이름은 넣지 않았다. 다만 옛 시나리오 사유
  (`예비 펌프 정비 완료 상태`, `OEM 납기 오더 진행 중 — …`)는 사람이 같은 문장을 칠 수 있으니 2) 단계에서 발췌를 꼭 본다.

검증(임시 PG 16, 같은 열 이름의 최소 표 7개 + 시드 6건, `.evidence/a6-residue/tempdb-runs/`): 표식만 → 2건(승인 사유·처리 건 이름), `--legacy` → 3건(옛 영문 사유 이벤트 추가),
사람 것(p3) 0, 최근 RUNNING(p4) 제외, 격리 테넌트·표식 정의는 목록만. Neo4j 꺼짐 + `--apply` → 0건 변경으로 중단, `--skip-graph --apply` → 3건 숨김 · 열린 작업 1건 취소,
다시 dry-run → 0건. process 상태 보고는 스텁 HTTP로 표식 사건 1/2건 확인. 그래프 Cypher(`--marker`)는 Neo4j가 없어 실행 확인 못 함 — 메인 dry-run에서 확인 필요.

## 4. ③ 포털 영문 id 노출 후보와 처리

| 후보(파일:줄) | 무엇이 보였나 | 처리 |
|---|---|---|
| `instances.js:289` 처리 건 목록 끝 칩 `UI.flowName(end_event)` · `ui.js` 로그 `cancelled: instance ended (ev:…)` | 이름 없이 id가 오는 끝/시작 이벤트: `review-recorded`, `unhandled-alert`(현장 검토 정의), `alert`, `select-timeout`, `start`(매뉴얼 추출·골든 질문 정의) | `flow.name.*` 5개 추가(정의 events[].name과 같은 말) |
| `instanceEffects.js:53` 영수증 칩 · `UI.status` 일반 | `RECORDED` 등 백엔드가 내는 상태 중 사전에 없던 값 | `states`에 15개 추가: RECORDED·HANDLED·QUEUED·CLAIMED·WAITING·SUPERSEDED·ACTIVE·ROLLED_BACK·UNKNOWN·UNSUPPORTED·READY·OCR_REQUIRED·AWAITING_AGENT·BLOCKED_FOR_REVIEW·CORRECTED |
| `app.js:509` 사건 기록 `UI.eventName(a.event)` | audit 이벤트 중 사전에 없던 값 | `eventNames`에 11개 추가: ACK_REJECTED·GUIDE_REJECTED·WORK_ORDER_FAILED·SKILL_FAILED·SKILL_CREATED·AGENT_TASK_CLOSED·MANUAL_ROLLED_BACK·DDL_INGESTED·DDL_SOURCE_DRIFT·INGEST_CLEARED·SCM_SOURCE_SYNCED |
| `ui.js` `logPatterns` | process가 단계 log에 붙이는 영문 조각(engine.py·instances.py·task_deferral.py 전수 grep) | 전부 기존 패턴에 걸림 — 추가 없음 |
| 운영 정의 5개(`it/process/definitions/*.json`) 단계·분기·흐름 이름 | — | 모두 한국어이거나 `flow.name/seq` 있음 — 추가 없음 |
| `instances.js:287` 진행 중 단계 칩 `names[id] \|\| id` · `ui.js` `defName` 폴백(`rework_plan_x` → "rework plan x") | 검사기가 등록한 시험 정의에서만 나옴 | 유지 — 시험 정의 처리 건은 §3으로 숨김 |
| `ui.js` `toolName` 폴백(`server · tool`) | 수강생이 직접 붙인 MCP 도구 | 유지 — 정답을 코드로 정하지 않는 원칙(수강생 도구 이름은 그대로 보임) |
| `ui.js` `who(by)` 폴백 | 사람이 적은 담당자 문자열 | 유지 — 검사기 값은 §2로 한국어화 |
| `liveStream.js:29` task_started의 `data.goal` | 워커가 쓰는 목표 문구(현재 한국어 지시문) | 유지, 라이브에서 영문이 보이면 워커 쪽 문구를 고친다 |

확인: `node -e`로 `UI.flowName('review-recorded')` → 현장 검토 기록 완료, `UI.status('RECORDED')` → 기록됨, `UI.eventName('ACK_REJECTED')` → 설비 명령 거절,
`UI.logText('cancelled: instance ended (ev:unhandled-alert)')` → 처리 건 종료(미지원 경보 접수)로 취소.

## 5. 바꾼 파일 · 시험
- 검사기 53개(`scripts/probe_*` 49 · `scenario_test.py` · `scenario_instance_test.py` · `scenario_pump_fan_test.py` · `run_scenario_pump_fan_evidence.py`) — 문자열만, 로직 변경 없음.
- 새 `scripts/mark_regression_residue.py`, 수정 `scripts/cleanup_residue_cases.py`(`--marker`·`--legacy`, `--before` 선택화), `it/portal/www/ui.js`(용어 줄 추가).
- `py_compile` 55개 통과 · `node --check it/portal/www/ui.js` 통과 · `.venv/bin/python -m pytest -q` 1284 passed.
- 라이브 확인(메인, 합친 뒤): 쿨러·펌프·팬 회귀 한 번 → 포털 "이상 확인·조치" 결정 사유와 "처리 건" 기록에 영문 시험 문구가 없고 `[회귀 검사]`만 보이는지 → §3 dry-run·apply → 처리 건 목록에서 사라졌는지.

## 6. 스스로 판정할 체크 질문
- 회귀를 한 번 돌린 뒤 포털 "이상 확인·조치"의 결정 사유·"처리 건" 기록에 영어 문장이 하나라도 보이는가? (보이면 그 문장을 grep해 어느 검사기인지 찾는다)
- `mark_regression_residue.py` dry-run의 matches에 학생·강사가 직접 넣은 사유가 섞여 있는가? (섞이면 `--legacy` 없이 표식만으로 돌린다)
- 정리 뒤 "처리 건" 목록이 비었는데 "이상 확인·조치"에는 시험 사건이 남는 것을 받아들일 수 있는가? (아니면 SQLite 스냅숏 정리를 별도로 결정)
