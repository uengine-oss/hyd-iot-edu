# 1조 프로세스 엔진: 레포 5개 (HEAD: process-gpt 6ad9db6 10-06 · completion b272c9a 10-01 · agent-sdk e4728a2 10-06 · bpmn-process-generation-skill f8c4b6d 07-26 · docs ad6944f 07-26)

읽기 전용으로 진행했고 HYD 파일은 고치지 않았다. 스냅샷 사본은 `scratchpad(952d3c36)/refs/<레포>`에 있는 git 체크아웃이다(process-gpt 3335272, agent-sdk 58ca16d). completion·D01·D03은 스냅샷 SHA와 HEAD가 같다. 동작은 HYD 순수 엔진과 MemoryRepo를 scratch 스크립트(`r14/g1_probe*.py`)로 돌려 확인했다. PG 함수는 SQL 본문만 읽었고 실행하지 않았다.

## 결론 먼저
1. **맞춰야 할 것 1: 워커 lease의 claim_count 의미가 SDK와 다르다.** HYD는 FB_REQUESTED로 다시 집을 때도 +1을 한다(`20261007000018_worker_lease.sql:51`, `procdb.py:307`). SDK는 회수(STARTED에서 다시 집기)일 때만 누적하고 피드백으로 다시 집으면 1로 되돌린다(`function.sql` claim_count CASE). SDK는 이 경우를 "멀쩡한 작업이 FAILED로 끝나는" 결함이라고 주석에 적어 두었다. 실측(MemoryRepo): 사람 답변 3회 뒤 claim_count는 4였고, 워커가 한 번 죽자 회수되지 않고 즉시 FAILED가 됐다. 고칠 범위는 SQL 1줄, MemoryRepo 1줄, 시험 1개다.
2. **맞춰야 할 것 2: 게이트웨이 없는 분기(activity fan-out)가 등록을 통과하고, 합류 활동이 두 번 실행된다.** D01과 bpmn-extractor에 같은 `_static_check`가 있고, 그 4번째 규칙 `uncontrolled_split`(`process_validator.py:577-590`)이 정확히 이 결함을 경고한다. HYD는 이 규칙만 뺐다(`definition_registry.py:146-147`). 실측: A→B, A→C, B→D, C→D 정의가 `validate_definition`을 통과했고, 엔진은 B 완료 뒤 D를 열었고 C 완료 뒤 D를 새로 한 번 더 만들었다(D DONE 1행 + IN_PROGRESS 1행).
3. **맞춰야 할 것 3(사용자 결정): 에이전트 활동 타입이 HYD 자체 고안인 `businessRuleTask`다.** D01은 Activity를 UserActivity(=userTask)만 허용하고(`02-generate-definition.md:124`, `save_to_supabase.py:68-73`), 에이전트 여부는 role·agentMode·orchestration으로 표현한다. 제품 폴링은 SUBMITTED된 businessRuleTask를 아무 핸들러로도 보내지 않는다(`polling_service.py:72-76`). 그래서 HYD 정의와 제품·D01 정의는 서로 실행되지 않는다. HYD 등록 규칙은 userTask에 agentMode를 금지한다(`definition_registry.py:81-82`).
4. **이전 기록 오류:**
   - REFERENCE_ADOPTION C03 행의 "A096 정적 연결성 검사 4종 추가"는 틀렸다. 실제로 들어간 것은 3종이다.
   - C03 행과 A092 행의 "병렬/포괄 합류 보류·병렬 없음"은 낡은 기록이다. A100이 병렬 합류를 이미 구현했다(`engine.py:568-591`, `definition_registry.py:83-92`).
   - C07 행의 "A097 반영 lease_until/claim_count/max 3"은 불완전하다. 위 1번의 의미 차이가 있다.
   - A092 행의 agent-sdk "같은 계약(42/42)"은 C07 행이 이미 정정했다.

---

## process-gpt (6ad9db6 10-06, 스냅샷 3335272 대비: 하위 gitlink 23개 동일, openspec 17파일 추가)
### 이 레포가 하는 방식
- 메타 레포다. gitlink pin은 completion `621db777`(HEAD b272c9a 아님), skills/bpmn-process-generation-skill `f8c4b6d` 등이다. agent-sdk는 gitlink가 아니라 pip 의존성이다.
- DB 원형은 `docker-infra/volumes/db/init.sql`(3,534줄)이다. enum은 L68-112(todo_status 7값, draft_status 6값)이고, `fetch_pending_task`는 L2677-2721에 4인자 형태로 있어 **lease가 없다**(grep lease_until 0건). 타이머는 `register_cron_intermidiated` L2140-2177로 pg_cron을 등록하고, 발화하면 `update_todolist_status`가 proc_inst+activity_id의 **모든 행**을 SUBMITTED로 바꾼다.
- **스냅샷 이후 바뀐 것**: 새 openspec 두 개다.
  - `agent-sdk_workitem-claim-lease/spec.md`(128줄, e2e suite): SVC-LEASE-01~06, LEASE-BENCH-2~10. 회수 상한, HUMAN_ASKED 비회수, lease NULL 비회수, 점유 상실 워커의 FAILED 덮어쓰기 금지를 명세한다.
  - `deepagents_workitem-human-input/spec.md`(97줄): HITL-01~12. 질문을 산출물로 저장 금지, HUMAN_ASKED 시 점유 해제, 답변 원문으로 재개를 명세한다.
  - `completion_workitem-polling-execution`에는 e2e 스크린샷 3장만 추가됐다.
- **제품 내부 불일치**: lease 명세와 SDK 0.10은 6인자 RPC를 쓰는데 메타 init.sql은 4인자 그대로다. lease SQL은 infra-docker `tests/lease/apply-lease-local.sql`에만 있다. 배포 경로에서 적용되는지는 미확인이다(추측).
### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| enum·todolist 열 | init.sql L68-112·L389-430 | `20261003000001_process_engine.sql:20-40` | 같음(+query·gateway_decisions·generation 등 HYD 열) | 무해 | 아니오 |
| 워커 claim RPC | init.sql L2679(lease 없음) | `20261004000004_process_lock_order.sql:43-46` → `claim_process_workitems`(lease 포함) | 다름. HYD는 SDK HEAD 쪽을 따른다 | 메타 DB가 SDK보다 늦다 | 아니오 |
| 타이머 | pg_cron 등록 + 같은 활동의 모든 행 SUBMITTED | due_date + 폴링(`procdb.py:477-482`, `instances.py:631-657`) | 다름 | 아래 출처 판정 참고 | 아니오 |
| lease/HITL 명세 | openspec 2건(신규) | A097 lease, runner `_pause` | 대체로 같음. claim_count 의미는 다름 | 결론 1 | **예** |
### 이전 주장 판정 (C01)
- "메타 gitlink/DB 원형 → compose.yaml·Supabase migration": **불완전.** enum과 테이블 원형은 맞다. 다만 HYD의 lease 계약은 메타 init.sql이 아니라 SDK function.sql에서 왔다. 메타 쪽 새 openspec 두 건(HYD가 맞춰 볼 수용 기준)이 기록에 없다. JSON의 `read_files: 0`도 본문을 읽지 않았다는 뜻이다.
### 읽지 않은 것
init.sql의 L1037-1340·L2300-3534 본문, 다른 openspec spec, e2e 코드(services.py·test_service_lease.py), docker-compose.

## process-gpt-completion (b272c9a 10-01, 스냅샷 대비 동일)
### 이 레포가 하는 방식 (흐름 순서)
1. **폴링**(`polling_service.py:119-182`): 5초마다 SUBMITTED(consumer null) 10건과 PENDING 5건을 가져와 `asyncio.gather`로 **동시 처리**한다. 클레임은 SELECT 뒤 조건부 UPDATE로 하고 인스턴스 잠금은 없다(`database.py:909-985`). 정체 회수는 5분 주기이고, 30분 넘게 갱신 없는 SUBMITTED의 consumer를 풀어 준다(`database.py:1016-1045`).
2. **타입 분기**(`polling_service.py:64-76`): userTask·scriptTask·manualTask·callActivity는 `handle_workitem`, serviceTask는 `handle_service_workitem`으로 간다. **businessRuleTask·sendTask·receiveTask는 처리 분기가 없다.**
3. **정의 버전 고정**(`workitem_processor.py:4687-4706`, `database.py:265-319`): 우선순위는 workitem version_tag/version, 인스턴스 proc_def_version(arcv), prod_version, 최신 major, minor, 현재 정의 순이다.
4. **조건 판정**:
   - `get_sequence_condition_data`(2253-2317)가 경로상 시퀀스의 properties·name·condition을 모은다.
   - `_evaluate_sequence_conditions`(2377-2527)는 `properties.conditionFunction`을 restricted eval로 폼 데이터 컨텍스트 위에서 계산하고, 그 외 `condition`·name은 **LLM 자연어 판정**(`_evaluate_nl_conditions`)으로 보낸다.
   - 판정 결과는 `_persist_gateway_decisions`(2597-2607)로 저장한다.
5. **완료 판정**(`run_completed_determination` 3787-4133): 체크포인트 검사는 주석 처리돼 꺼져 있다. 시퀀스와 게이트웨이(parallel=모두 참, XOR/OR=하나 참 또는 미판정)로 DONE/PENDING을 정한다. 미판정이나 PENDING이면 completedActivities를 비우고, 이어서 `prompt_completed` **LLM이 완료를 다시 판단**한다(4925-4930).
6. **다음 활동**:
   - `resolve_next_activity_payloads`, 경계 이벤트를 `system` IN_PROGRESS 후보로 주입하는 `inject_boundary_events_as_next`(4431-4535), 그리고 `check_event_expression`·`check_subprocess_expression`(LLM), `check_task_status`, `check_role_binding`(LLM)을 차례로 거친다(4973-5000).
   - 합류(`check_task_status` 3455-3646): 블록 단위 `branch_merged_workitems`로 판단한다. parallel join은 전부 DONE/SUBMITTED/COMPLETED일 때, inclusive join은 IN_PROGRESS가 없을 때, 암시적 join(입력 2개 이상)은 상류 분기 타입으로 판단한다.
   - 예정 업무 TODO는 `upsert_todo_workitems`(`database.py:1787-1808`)가 도달 가능한 전체를 미리 생성한다. 취소 목록 `cancelledActivities`는 폴링 경로에서 항상 `[]`이다(4881). 안 탄 가지와 경계 짝은 취소되지 않는다.
7. **실패 처리**(`polling_service.py:83-100`): retry가 3 이상이면 **status DONE으로 덮어쓴다**. openspec `completion_workitem-polling-execution` L58-68이 이 동작을 명세로 굳혀 두었다.
8. **PENDING 재평가**(`handle_pending_workitem` 5276-5363): 서브프로세스 부모만 재평가하고, 일반 PENDING은 그대로 둔다.
9. **타이머**(`_register_event` 1706-1768): `_is_intermediate_event`(1769-1785) 목록에 boundaryEvent가 없다. 그래서 주입된 경계 타이머 워크아이템은 cron에 등록되지 않는다(정적 읽기 기준이고 실행 미확인).
10. **재작업**(`process_engine.py:954-1034`): 후보는 현재 활동, 그 폼을 inputData로 참조하는 DONE 활동, 하류 DONE 활동이다. 사람이 고른 활동마다 새 행을 만들고(시작 활동 IN_PROGRESS, 나머지 TODO, rework_count+1) 보상 코드를 생성한다. 기존 행 취소·변수 복원·세대 개념은 없다.
### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 엔진 클레임 | 행 단위 조건부 UPDATE, 인스턴스 잠금 없음 | `claim_process_workitems` 부모 인스턴스 `FOR UPDATE SKIP LOCKED`(`..._worker_lease.sql:32-46`) | 다름 | HYD는 같은 인스턴스 동시 처리(합류·변수 덮어쓰기 경합)를 막는다 | 아니오 |
| 예정 업무 TODO 선생성 | `upsert_todo_workitems` | `engine.start` L355-365 | 같음 | | 아니오 |
| 도달 시 [InputData] 부착 | `_append_input_data_to_query` | `engine.reach` L381-385 | 같음 | | 아니오 |
| 조건 형식 | `properties.conditionFunction`(eval) + `condition`(LLM 자연어) | `condition` 자체를 AST 화이트리스트 식으로 평가(`engine.py:171-218`), 자연어 거부 | 다름 | 결정론 확보(DECISIONS 3·12). 제품·D01 정의와 비호환 | 사용자 결정 |
| 조건 미충족 | LLM 재판정 | 즉시 PENDING + 사유(`engine.py:465-470`) | 다름 | HYD 쪽이 재현 가능 | 아니오 |
| XOR 동점 | priority → id | `_allowed_targets` L619-637 | 같음 | | 아니오 |
| 병렬 합류 | 블록 기반 branch_merged | 입력 소스별 최신 행 DONE(`_join_ready` L568-587) | 개념 같음, 구현 다름 | HYD가 정의 간선으로 직접 계산해 더 정확하다 | 아니오 |
| 포괄 합류·서브프로세스 | 있음 | 등록 거부(`definition_registry.py:65-66,91-92`), 단 `engine.py:87`은 subProcess 통과 | 다름 | 현재 정의 4종에서는 쓰지 않음 | 아니오 |
| **암시적 분기·합류** | 상류 분기 타입으로 대기 판단(완전 보장 여부는 추측) | 등록 통과, 합류 활동 2회 실행(실측) | 다름 | 결론 2 | **예** |
| 경계 타이머 | 주입만 하고 cron 미등록(정적) | ISO 기간 → due_date, 폴링 발화, 짝 취소(`engine.py:314-328,485-493,685-693`) | 다름 | HYD는 작동하고 배속 조절 가능 | 아니오 |
| 3회 실패 | DONE으로 덮어씀 | PENDING + 사람 닫기(`instances.py:402-421`) | 다름 | HYD 쪽이 맞다 | 아니오 |
| 버전 고정 | 우선순위 폴백 체인 | 인스턴스 proc_def_version 정확 일치만, 폴백 없음(`instances.py:129-137,153-162`), `hyd-immutable` 행(`procdb.py:522-543`) | 다름(더 엄격) | | 아니오 |
| 재작업 | 수동 선택 + 새 행 | 의존 폐포 계산 + 세대 + 변수 복원(`rework.py:30-120`, `dependency_schedule.py`) | 다름 | 아래 출처 판정 | 아니오 |
### 이전 주장 판정 (C03)
- "주장 참. engine.py L87 subProcess/callActivity 허용": **맞음.** 현재도 L87에 있다.
- "병렬/포괄 합류 … 쓰임이 없어 보류": **틀림(낡음).** 병렬 합류는 A100으로 구현됐다. 포괄 합류만 등록에서 거부된다.
- "A096: 정적 연결성 검사 4종 추가": **틀림.** 3종만 적용됐다(`definition_registry.py:142-177`). 4번째 규칙은 의도적으로 뺐고, 실측에서 결함이 확인됐다.
- "3회 실패→DONE은 HYD PENDING이 더 맞음": **맞음.** openspec 명세 L58-68이 제품 동작을 확인해 준다.
- r13-group4가 C03에서 "합류 없음"이라고 쓴 것은 당시에는 참이었다. 지금은 낡았다.
### 읽지 않은 것
workitem_processor.py의 1-1187, 2040-2252, 2610-3454(LLM 조건·이벤트·서브프로세스 체인), 3649-3786, 4138-4430(`resolve_next_activity_payloads` 본문), 5026-5275. database.py의 1097-1786(upsert_completed/next). block_finder.py 809줄(합류 블록 판정. 그래서 암시적 합류의 제품 동작은 추측으로 남는다). process_definition.py.

## process-gpt-agent-sdk (e4728a2 10-06 v0.10.1, 스냅샷 58ca16d 09-30 대비: 변경)
### 바뀐 것 (diff로 확인한 12파일)
- `function.sql`:
  - `fetch_pending_task`가 6인자가 됐다(`p_lease_seconds` 기본 NULL, `p_max_claims` 기본 3).
  - 집기 전에 상한에 닿은 만료 점유를 FAILED로 종결한다.
  - 만료된 STARTED(lease NOT NULL·claim_count < max)를 회수한다.
  - `claim_count`는 **이전이 STARTED일 때만 +1, 아니면 1**이다.
  - `renew_task_lease`가 추가됐다. jsonb로 `not_owner`, `not_started`, `missing`, `bad_request`를 돌려준다.
  - `release_task_lease`가 추가됐고, save_task_result가 lease_until을 비우며, `idx_todolist_lease_reclaim` 인덱스가 생겼다.
- `lease.py`(신규 198줄): 120 s / 30 s / 3회(환경변수로 설정). LeaseKeeper가 **별도 OS 스레드**에서 연장한다. `not_owner`면 실행을 취소하고, `not_started`면 연장만 멈춘다.
- `processgpt_agent_framework.py`: 컨텍스트 준비 중 점유를 잃으면 실행하지 않는다. 점유를 잃은 뒤의 오류는 FAILED로 기록하지 않는다. finally에서 release한다.
- `database.py`: consumer 이름을 `get_consumer_id()`로 통일했다. `mark_task_human_asked`는 STARTED일 때만 HUMAN_ASKED로 바꾸고 consumer·lease를 비운다.
- `event_queue_process.py`: INPUT_REQUIRED 뒤의 최종 아티팩트는 결과로 저장하지 않고 HUMAN_ASKED로 둔다. crew_completed도 내지 않는다.
- `database_schema.sql`: todolist 열 순서를 재배치하고, query·feedback_status·executor_dept·gateway_decisions·lease_until·claim_count 열과 트리거를 추가했다.
### HYD 대응 부품과 대조
| 단계/기능 | SDK HEAD | HYD | 같음/다름 | 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 점유 시 lease | now+120 s(env) | 고정 120 s(`..._worker_lease.sql:50`) | 같음(설정 불가) | 무해 | 아니오 |
| **claim_count** | 회수만 누적, FB 재집기는 1 | **모든 워커 집기에서 +1**(L51, `procdb.py:307`) | **다름** | 피드백 2회 이상이면 워커가 한 번 죽어도 FAILED(실측) | **예** |
| 연장 방식 | 별도 스레드, 이유 코드 반환 | 메인 스레드 `check_stop`을 25 ms마다 호출(`process_control.py:117-126`), CLI 출력은 펌프 스레드, bool 반환 | 동등 | CLI가 하위 프로세스라 루프가 막히지 않는다 | 아니오 |
| 점유 상실 시 | 실행 취소, FAILED 금지 | `Cancelled` → `release_worker_claim`(내 consumer일 때만) + "담당자가 실행을 취소했습니다" 이벤트(`runner.py:63-67`) | 거의 같음 | 이벤트 문구가 사람 취소처럼 오해된다 | 아니오(문구만) |
| 상한 종결 위치 | 매 폴링 RPC 안 | 60초 DDL 루프 `_lease_sweep_once`(`main.py:169-185`) | 다름 | 최대 60초 지연, 무해 | 아니오 |
| lease NULL 기존 행 | 회수하지 않음(구버전 워커 보호) | 이전 행에 now+120 s 부여(`..._worker_lease.sql:11-12`) | 다름 | 단일 코드베이스라 업그레이드 순간에만 위험 | 아니오 |
| HUMAN_ASKED 전이 | STARTED일 때만, 점유 해제 | `set_draft_status(expected_consumer)`(`procdb.py:668-672`) | 같음(소유자까지 검사) | | 아니오 |
### 이전 주장 판정 (C07)
- "주장 참이나 stale 정리는 절반 → A097 lease 반영, 실측 6/6": **불완전.** 반영은 됐다. 그러나 claim_count의 FB 경로 의미가 SDK와 다르고, `tests/test_worker.py:457-490`에 FB 경로 시험이 없다.
- A092 행의 "같은 계약(42/42)": C07 행이 이미 정정했고, 그 정정은 맞다.
### 읽지 않은 것
README diff 본문, tests/test_lease.py, framework L535-881, chat_mode·steering.

## bpmn-process-generation-skill (f8c4b6d 07-26, 스냅샷 대비 동일)
### 이 레포가 하는 방식
- 작성 형식은 `elements[]+elementType`이다. Activity는 **UserActivity만** 쓴다(`02-generate-definition.md:124`).
- 저장은 `save_to_supabase.flatten`(95-191)으로 activities/events/gateways/sequences를 분리하고 type을 `userTask`로 매핑한다(68-73). `proc_def`는 (tenant,id)로 **덮어쓰기** upsert한다(259-280). 폼은 `form_def`에 proc_def_id+activity_id로 **버전 없이** 덮어쓴다(320-344).
- XOR은 직전 폼에 select-field를 두고, 그 option value가 `Sequence.condition` 문자열과 정확히 같아야 하며, `gateway.conditionData=["form.field"]`를 단다. inputData와 conditionData는 **선행 활동** 폼 필드만 쓸 수 있다(`08-reference-info.md:21-27,44-69`).
- 정적 검사는 4종이다(`scripts/validation/process_validator.py:540-591`). bpmn-extractor의 `_static_check`와 본문이 같다(diff 확인).
### HYD 대응 부품과 대조
| 단계/기능 | D01 | HYD | 같음/다름 | 영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 정의 저장 형식 | flatten 결과 | 같은 분리 배열(`definition_registry.py:24-35`) | 같음 | | 아니오 |
| 에이전트 활동 타입 | userTask + role(agent)/agentMode | **businessRuleTask**만 에이전트, userTask는 agentMode 금지(L79-82) | 다름 | 상호 비호환 | 사용자 결정 |
| 분기 조건 | condition 문자열 == 폼 select 값 + conditionData | Python 비교식(`chosen_option == '...'`) | 다름 | D01 산출물은 등록에서 SyntaxError로 거부된다 | 사용자 결정 |
| 조건 변수 출처 검사 | 선행 활동 폼 필드만 | "어떤 활동이든 outputData에 있으면 통과"(`definition_registry.py:128`) | 약함 | 하류 활동이 내는 변수도 통과해 실행 시 PENDING | 예(소) |
| 폼 저장 | form_def, 버전 없음 | 불변 판본 안 `forms`(L21-22,53-58) | 다름 | HYD가 실행 중 인스턴스의 폼을 지킨다 | 아니오 |
| 정적 검사 | 4종 | 3종(4번째 제외) | 다름 | 결론 2 | **예** |
### 이전 주장 판정 (D01)
- "부분 참: flatten 형식, form_def 대 forms, skills 0건": **맞음.**
- "정적 연결성 4종은 HYD에 없었음 → A096 반영": **불완전.** 3종만 반영됐다.
- r13-group5 후보 3의 "조건 변수 ⊆ **선행** 활동 outputData": HYD는 선행 조건 없이 구현했다(A098). **불완전.**
- businessRuleTask와 UserActivity의 차이는 r13 항목 7이 언급만 하고 차이로 판정하지 않았다. **누락.**
### 읽지 않은 것
references 01·03·04 후반·09-12, evals.json, assets/form-components.md, run_postprocess.py 본문.

## process-gpt-docs.github.io (ad6944f 07-26, 스냅샷 a066 대비 동일)
- `content/ko/advanced-features/rework.md`(33줄): "로그를 역순으로 탐색해 보상"하는 설명과 UI 절차만 있다(L8-16, L27-33). `dmn.md`는 ko에만 있고 en에는 없다.
- 이 문서는 동작 근거가 아니라 사용 설명이다. 실제 재작업 코드(위 completion 10번)는 보상 생성 외에 기존 행 취소도 변수 복원도 하지 않는다.
### 이전 주장 판정 (D03)
- "navigation ko 3종, en은 dmn 없음, rework.md는 역순 보상+UI만, 채택 0": **맞음.**
### 읽지 않은 것
reference-info.md·dmn.md 본문 전문, en 페이지, 튜토리얼 Lv1-5.

---

## 출처 판정
| HYD 기능(파일:줄) | 출처 | 맞는 레포의 방식(파일:줄) |
|---|---|---|
| 정의 구조·검증(`engine.py:47-153`, `definition_registry.py:14-119`) | 맞는 레포 따름(completion·D01 flatten 형식) | `save_to_supabase.py:95-191` |
| 예정 업무 TODO 선생성(`engine.py:355-365`) | 맞는 레포 따름 | `database.py:1787-1808` |
| 도달·[InputData]·reference_ids(`engine.py:368-404`) | 맞는 레포 따름 | `workitem_processor.py:1022-1117` |
| XOR priority·default·gateway_decisions(`engine.py:619-682`) | 맞는 레포 따름 | `workitem_processor.py:2548-2607, 3787-4133` |
| **조건 평가 = `condition` 필드의 AST 식**(`engine.py:171-218`) | 맞는 레포에서 eval만 빌리고 필드는 자체 결정 | conditionFunction은 `properties`(`workitem_processor.py:2433-2514`), condition은 자연어(LLM) / D01은 select 값 일치(`08-reference-info.md:47,63-69`) |
| 조건 미충족 → PENDING(`engine.py:465-470`) | HYD 자체 결정(제품 LLM 재판정 제거) | `workitem_processor.py:4925-4930` |
| 병렬 합류(`engine.py:568-591`) | 맞는 레포 개념, HYD 구현 | `check_task_status` 3455-3646 |
| **암시적 분기 허용·합류 대기 없음**(`definition_registry.py:142-147`, `engine.py:500-510`) | HYD 자체 결정(맞는 레포 규칙 제외) | `process_validator.py:577-590`(D01=bpmn-extractor) |
| 경계 타이머 due_date + 폴링(`engine.py:314-328`, `instances.py:631-657`) | HYD 자체 고안 | pg_cron `register_cron_intermidiated`(init.sql L2140-2177), `workitem_processor.py:1874-1903` |
| 대안 취소(경계 짝·종료 시 TODO)(`engine.py:476-493,555-565`) | HYD 자체 고안 | 없음(`cancelledActivities: []`, 4881) |
| 엔진 클레임 + 인스턴스 잠금(`..._worker_lease.sql:14-55`) | HYD 자체 고안(이름은 제품 RPC) | `database.py:909-985` |
| 3회 실패 → PENDING(`instances.py:402-421`) | HYD 자체 결정 | `polling_service.py:86-95`(DONE) |
| 정의 버전 고정(`instances.py:129-162`, `procdb.py:522-552`) | 맞는 레포 테이블(proc_def_version) + 자체 규칙(정확 일치·불변) | `database.py:265-319` 폴백 체인 |
| 폼 = 판본 내부 `forms` | HYD 자체 고안 | `form_def` 테이블(`save_to_supabase.py:320-344`) |
| **에이전트 활동 = businessRuleTask**(`definition_registry.py:65,79-82`, `engine.py:34`) | HYD 자체 고안 | userTask + agentMode/orchestration(`save_to_supabase.py:68-73`, `database.py:1491-1494,1538-1542`) |
| inputData = 평면 변수 키 + inputBindings(`input_bindings.py:1-30`) | HYD 자체 고안 | `<form_id>.<field>`(`08-reference-info.md:15-40`, `process_engine.py:880-893`) |
| 조건 변수 출처 검사(`definition_registry.py:122-139`) | 맞는 레포 빌림(약화) | 선행 활동만(`08-reference-info.md:21-27`) |
| 재작업 계획·세대·생산자 대기(`rework.py`, `dependency_schedule.py`) | HYD 자체 고안(제품 의미 확장) | `process_engine.py:954-1034` |
| 워커 lease(`..._worker_lease.sql`, `runner.py:171-181`) | 맞는 레포 따름(SDK). claim_count 규칙만 이탈 | `function.sql`, `lease.py` |
| HUMAN_ASKED/FB_REQUESTED(`runner.py:230-252`, `instances.py:604-`) | 맞는 레포 따름 | `database.py` mark_task_human_asked, openspec HITL-01~09 |

### 빌림·자체 고안 비교
**A. 암시적 분기·합류(4번째 정적 규칙 제외)**
- 정확성: 레포 쪽이 낫다. 실측에서 합류 활동이 중복 실행됐고, D01이 정확히 이 결함을 경고한다.
- 재현성: 같다.
- 속도·비용: 차이가 없다.
- 복구: HYD는 중복 행을 사람이 닫아야 한다.
- 수업: "게이트웨이를 거쳐 갈라진다"는 규칙 하나로 설명된다.
- **판정: 레포 쪽이 낫다.**
- 범위: `definition_registry._static_connectivity`에 uncontrolled_split을 critical로 추가한다(경계 이벤트 간선은 제외). 현재 정의 4종에는 activity fan-out이 0건이라 영향이 없다. 이 형태에 기대는 재작업 시험(`tests/test_rework_*.py`)은 정의를 고쳐야 한다. 약 0.5~1일.

**B. claim_count FB 누적**
- 정확성: 레포 쪽이 낫다. 피드백 왕복이 회수 예산을 소모한다(실측).
- 재현성·비용: 같다.
- 복구: HYD는 정상 작업이 FAILED가 되고 사람이 다시 보내야 한다.
- 수업: SDK 주석이 그대로 설명이 된다.
- **판정: 레포 쪽이 낫다.**
- 범위: `20261007000021_*`를 새로 만들어 `claim_process_workitems`의 claim_count를 `case when w.draft_status='STARTED' then +1 else 1`로 바꾼다. `procdb.py:307` MemoryRepo도 고치고, FB 경로 시험 1개를 추가한다. 약 1~2시간.

**C. businessRuleTask = 에이전트**
- 정확성: HYD 내부에서는 동작한다. BPMN 의미(업무 규칙 = DMN)와 어긋나고, 제품 폴링에서 SUBMITTED가 멈춘다.
- 재현성: 같다.
- 비용: 같다.
- 복구: 같다.
- 수업: "ProcessGPT가 제품화한 그대로"라는 설명과 충돌하고, D01 스킬 산출물을 그대로 실행할 수 없다.
- **판정: 레포 쪽이 낫다(호환·수업). 바꿀 시점은 사용자 결정.**
- 범위:
  - `definition_registry.py:65,79-82`: userTask에 agentMode와 cliagents를 허용한다.
  - `engine.py:34`
  - `manual_extraction.py:51`
  - `neo4j/v2/schema.json`의 매핑
  - 새 판본 정의(불변 규칙상 v2.2 파일, 기존 v21 보존)
  - 워커 `context.activity_capabilities` 확인과 시험
  - 약 1일.

**D. 조건 형식(`condition` = 식)**
- 정확성·재현성: HYD 쪽이 낫다. 제품의 자연어 LLM 판정은 같은 입력에 같은 결과를 보장하지 못한다.
- 호환: 레포 쪽이 낫다. D01은 `condition`에 select 값 문자열, `conditionData`에 결정 필드를 둔다. 이것도 결정론적 동치 비교로 구현할 수 있다.
- **판정: 비슷하다(결정론은 HYD가 유지).** C를 할 때 D01 형식(값 == conditionData 필드)을 함께 받으면 호환이 생긴다. 선택 사항이며 약 0.5일.

**E. 조건 변수 검사 약화**
- **판정: 레포 쪽이 낫다(소).** `_condition_variables`의 `produced`를 해당 게이트웨이의 선행 활동(`dependency_schedule.control_predecessors` 재사용)으로 좁힌다. 약 1시간.

**F. 경계 타이머(due_date 폴링)**
- 정확성: HYD 쪽이 낫다. 제품은 경계 타이머를 cron에 등록하지 않는다(정적). 발화 시 같은 활동의 모든 행을 SUBMITTED로 바꾸는 문제도 있다.
- 재현성: HYD가 time_scale로 낫다.
- 비용: pg_cron이 필요 없다.
- 수업: HYD가 쉽다.
- **판정: HYD 쪽이 낫다.**

**G. 인스턴스 잠금 클레임, 3회 실패 PENDING, 대안 취소**
- 셋 다 정확성과 복구에서 HYD가 낫다(경합 방지, 거짓 완료 방지, 남은 TODO 정리).
- **판정: HYD 쪽이 낫다.**

**H. 폼을 판본 안에 고정, 버전 정확 일치**
- 재현성: HYD가 낫다. 실행 중 인스턴스의 폼과 정의가 바뀌지 않는다.
- 수업: 같다.
- **판정: HYD 쪽이 낫다.**

**I. 평면 변수 + inputBindings**
- 정확성: 레포 쪽이 약간 낫다. `form.field` 이름이 충돌을 원천 차단한다. HYD는 bindings로 보완한다.
- 바꾸는 비용이 크다(정의·조건·재작업 계획 전부).
- **판정: 비슷하다(차이 무해).** 현재 정의에는 충돌하는 키가 없다(4종 확인은 안 함, 추측).

**J. 재작업 세대·의존 폐포**
- 정확성: HYD 쪽이 낫다. 진행 중 행을 취소하고 변수를 복원한다. 제품은 새 행만 추가한다.
- 수업: 제품이 훨씬 단순하다. HYD 쪽은 코드가 800줄 이상이다.
- **판정: HYD 쪽이 낫다(설명 부담은 있다).**

## 조 요약
| 레포 | 핵심 차이 | 맞춰야 할 것 | 이전 기록 오류 |
|---|---|---|---|
| process-gpt | 스냅샷 이후 openspec lease·HITL 명세가 추가됐다. 메타 init.sql은 lease 미반영 | lease·HITL 명세를 HYD 시험 기준으로 쓴다 | C01 "DB 원형" 근거 불완전(lease는 SDK 출처, 새 명세 누락) |
| completion | 제품은 조건·완료에 LLM을 쓰고, 3회 실패→DONE, 경계 타이머 미등록, 인스턴스 잠금이 없다 | 암시적 분기 금지(4번째 정적 규칙) | C03 "4종 반영" 틀림(3종), "병렬 합류 보류" 낡음(A100 구현) |
| agent-sdk | v0.10 lease·HUMAN_ASKED 보존 | claim_count를 회수에만 누적 | C07 "A097 반영" 불완전(FB 경로 의미가 다르고 시험 없음) |
| D01 | UserActivity만 사용, select 값 == condition, 선행 필드만, form_def 무버전 | 조건 변수를 선행 활동으로 제한. businessRuleTask→userTask+agentMode는 사용자 결정 | D01 "정적 검사 반영" 불완전, businessRuleTask 차이 누락 |
| docs | 사용 설명뿐 | 없음 | 없음(D03 판정 맞음) |

### 읽지 않은 것(전체)
codegraph는 호출자 확인 2회만 썼다. 나머지는 파일 줄 범위를 직접 읽었다. 제품 런타임(LLM 경로·block_finder)은 실행하지 않았다. PG의 `claim_process_workitems` FB 결함은 SQL 정적 읽기와 MemoryRepo 실측으로 확인했고, PG 실측은 하지 않았다.
