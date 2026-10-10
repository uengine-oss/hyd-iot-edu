# 전체 과정 랩업 빈틈 G3 · G9 (브랜치 cap-g3g9)

> 2026-10-10 · 기준 merge-preview 2fbefff · 설계 근거 capstone-lab.md 3.5~3.7, 5.2 G3 · G9 행

## 0. 진행 기록
- 설계 문서 · 점검표 · 헌법 · 프로젝트 CLAUDE.md 통독 완료.
- 코드 통독(실제 행): effect_parts.py PARTS·validate·activity_for, service_parts.py `_run_mcp_call`·`_call_mcp`, bpmn_import.py check(값 연결 · 효과 앞 승인 · data 자료형), instance_mode.py `mcp_call`(call_effect), mcp_check.py `read_only_verdict`·`call`·`shape_result`, worker workspace.py CONSTITUTION · runner.py provision(+ codex 경로가 CONSTITUTION 을 직접 붙임 168행), agents_store.agent_settings, agent_authoring(create · clone · Pg write_agent), config_bundle(에이전트 내보내기 · 가져오기).

## 1. 참고 레포 대조
- MCP 결과 → 처리 건 값: ProcessGPT 프런트 `services/frontend/.../panel/ServiceTaskPanel.vue` 283~310행 — uEngine 서비스 task 의 `outputMapping.mappingContext.mappingElements`(응답 경로 → 프로세스 변수). HYD `extract: {값이름: {path, type}}` 는 같은 뜻(응답 경로 → 처리 건 값)을 평평한 한 칸으로 둔다. 차이: 자료형을 같은 칸에 선언(분기 조건 검사용) — 요구(등록 검사의 자료형 선언)를 채우려는 차이, 유지. 백엔드(completion/polling_service, deepagents, a2a-orch, mcp-hub)에서 MCP 결과를 변수로 꺼내는 코드는 찾지 못함(검색어 outputMapping · jsonpath · serviceTask).
- 에이전트 고정 규칙: `services/cli-agent/executor.py` 501~516행 `_instructions` — 업무 없는 공통 줄("# ProcessGPT 업무 에이전트", 작업 디렉터리 밖 수정 금지 · 지어내지 말기 · 도구로 확인)만 넣는다. HYD 공통부가 이 모양이고, HYD 설비 문구는 업무부로 뺀다.

## 2. 설계 결정
- G3 `extract` 한 값 = `{"path": "a.b.0.c", "type": "Boolean|Number|Text"}`. 문서의 `{값이름: "JSON 경로"}` 에 자료형 선언을 같은 칸에 붙임(두 칸으로 나누면 이름이 어긋나는 경우가 생김).
- 꺼내기 실패(JSON 아님 · 잘림 · 경로 없음 · 자료형 불일치)는 task 실패(사유: task · 경로 · 결과 앞부분). 재시도는 기존 정해진 재시도(MAX_RETRIES=3 → PENDING)를 따르며 다시 부른다 — 처음엔 영수증을 draft 에 저장해 재호출을 막으려 했으나, 서비스 처리기는 처리 건 전이(트랜잭션) 안에서 돌고 실패하면 그 저장도 함께 되돌려져 죽은 코드였다(시험이 3회 호출로 드러냄) → 지움. 읽기는 다시 불러도 해가 없고, 쓰기는 같은 idempotency_key 로 부른다(기존 계약).
- `effect: false` = 읽기 확인: 효과로 세지 않음(승인 앞 가능) + 실행은 새 훅 `mcp_read` → `mcp_check.call`(호출 직전 도구 목록을 다시 받아 `read_only_verdict` + 강사 확인 목록으로 판정, 쓰기면 tools/call 없이 거절). 사전 검사에서 정적 판정은 하지 않음 — 저장된 검사 도장은 낡을 수 있고, 호출 시점 판정이 권위(미구현으로 기록).
- G9 업무부 선택 = 에이전트 칸 `users.work_rules`(키). 기준 에이전트 4개(sys:agent · agent:cooling · agent:pm-plan · agent:spare-buy)는 `hyd-plant`. 키 없음 → 공통부만 + 처리 기록 알림. 모르는 키 → 실행 실패(조용한 대체 없음).

## 3. G3 구현 · 검증
- 구현: `effect_parts.py` PARTS 설명(extract · effect), validate(MCP: effect bool · `_extract_types` · outputData = [output, *extract]), `activity_for`(읽기 확인 checkpoint), 새 함수 `_extract_types` · `extract_types` · `is_read_check` · `extract_values` · `condition_type_problems`, `lookup` 을 `_walk` 로 나눔. `service_parts.py` `_run_mcp_call`(읽기 확인이면 승인 검사 없이 `hooks.mcp_read`, 꺼낸 값을 outputData 로, 처리 기록 `MCP_RESULT_VALUES` 사건) · `_call_mcp`(영수증 + 결과를 돌려줌, 읽기 호출은 `MCP_READ_CALL`/감사 `MCP_READ_*` 로 구분). `instances.py` Hooks 에 `mcp_read` 한 칸. `instance_mode.py` `_runtime_server` 로 공통 부분을 묶고 `mcp_read` = `mcp_check.call`(read_only_verdict + 강사 확인 목록). `bpmn_import.py` 최소 3곳: 효과 앞 승인 검사에서 읽기 확인 제외, 분기 조건 자료형 검사, data 자료형에 꺼낸 값 선언.
- 시험 `tests/test_capstone_g3_mcp_extract.py` 25개 통과: 사전 검사(출력 · 자료형 · 분기 연결, 자료형 불일치 4종, 아무도 안 내는 값, 설정 오류 6종, effect 칸 형식, effect 없으면 승인 필요) · 실행(참/거짓 두 가지 분기, 처리 기록 사건 · 출력 값, JSON 아님 · 경로 없음 · Boolean/Number 불일치 · 잘림 → PENDING · 값 없음 · 사유에 task · 서버.도구 · 경로 · 결과 앞부분) · 실제 판정(instance_mode.mcp_read → 가짜 stdio MCP 서버: submit_note(readOnlyHint=false) · delete_rows(이름) · greet(표시 없음) 거절, add(읽기) 는 불림).
- 뮤테이션(한 번씩, 되돌림 확인): M1 읽기 확인 판정 끔 12 실패 · M2 자료형 검사 끔 2 · M3 분기 자료형 검사 끔 4 · M4 data 선언 무시 1 · M5 읽기를 쓰기 경로로 11 · M6 mcp_read 를 판정 없는 call_effect 로 3 (첫 시도는 문법 오류 변이라 rc=2 — 잡힌 것으로 세지 않고 다시 함) · M7 잘림 검사 끔 1 · M8 보호 값 이름 허용 2. 전부 잡힘.
- 관련 기존 시험 test_c2_execution · test_instance_mode · test_c3_assembly · test_capstone_g2_mcp_secrets 74 통과(G3 변경 직후).
- 발견: 실패한 서비스 task 의 도구 호출 사건(tool_usage_*)은 처리 건 전이와 함께 되돌려져 남지 않는다(error 사건과 작업 행 log 만 남음). 기존 동작이고 이번 범위 밖 — 블랙박스 관점의 후속 과제로 기록(분류: 근거 부족 → 결함 후보).

### 3.1 추가 요청(코디네이터): 부품 설정의 모르는 칸
- 발견(직접 확인): `effect_parts.validate` 는 작업지시(WO_CREATE)만 칸 목록을 검사하고, 승인 뒤 실행 부품 7종은 모르는 칸을 거절하지 않았다. 실측: svc:mcp-call 설정에 `extarct` · `retries` 를 넣어도 검사 통과, 칸은 정의에 남지만 실행은 읽지 않음 → 오타가 조용히 무시된다. 분류: 결함.
- 조치: `effect_parts.validate` — 부품의 `PARTS[...]["config"]` 칸 목록 밖이면 "활동 <id>: 모르는 설정 칸 <칸> — <부품> 이(가) 받는 칸: …" 로 거절. 가져오기 사전 검사(bpmn_import → problem(task, "config"))와 등록 검사(definition_registry 75행) 둘 다 같은 함수라 함께 걸린다.
- 기준 확인: 기준 정의 파일 4개(anomaly_response*.json)의 활동 전부 validate 통과(부품 설정 없음), 기준 흐름 A · B · C(scripts/c3_flows.py FLOWS, 시나리오 에이전트 목록으로 만든 부품 목록) 사전 검사 ok — 시험 `test_baseline_flows_and_definitions_use_only_known_config_keys`.
- 시험: mcp-call `extarct` · report `sumary` 가 task · 칸 이름과 함께 거절. 뮤테이션 M9(검사 끔) → 2 실패로 잡힘.

## 4. G9 구현 · 검증
- 구현: 새 `it/process/procsvc/work_rules.py` — 공통부 조각(_INTRO · _WORKSPACE · _TOOLS · _CITATION · _NO_INVENTION · _RESULT · _SCRIPT · _DEFERRED · _KOREAN · _LANGUAGE · _NAMING · _FORBIDDEN_EFFECTS)과 `BusinessRules`(title · tool_sources · citation · reassessment · naming_example · sections · forbidden_effects · forbidden_extra · footer), `constitution(rules)` 조립, `HYD_PLANT`, `rules_for(key)`(빈 값 None, 모르는 키 `UnknownWorkRules`). worker `workspace.py` 에서 CONSTITUTION 상수를 지우고 `provision(constitution=…)` 로 받음. `runner.py` 가 `agent.work_rules` → `rules_for` → `constitution` 을 Claude Code 작업 폴더와 Codex 프롬프트(옛 168행 `workspace.CONSTITUTION`) 둘 다에 씀, 업무부 없으면 `NO_WORK_RULES_NOTICE` 알림 사건. `agents_store.AgentSettings.work_rules` + summary(task.json)에 키. DB: 마이그레이션 `20261010000051_agent_work_rules.sql`(users.work_rules text), `seed.sql` 기준 에이전트 넷 'hyd-plant'. 생산자 배선: `agent_authoring` 만들기(없으면 None) · 고치기(칸이 없으면 지금 값 유지, 모르는 키 거절) · 복제(원본 값 복사) · Pg insert/update, `config_bundle` 내보내기 · 가져오기 검사(모르는 키는 검사 단계에서 거절) · 기대값. worker `Dockerfile` 에 work_rules.py COPY.
- 공통부 분류 근거: 요구의 넷(작업 폴더 밖 금지 · 도구로 확인 · 승인 전 쓰기 금지 · 근거 인용) + 업무와 상관없는 워커 계약(결과 파일 · 보류 JSON · 스크립트 한 명령 · 한국어 진행 설명). 보류 JSON 설명의 "원인 근거가 불일치하면 UNSUPPORTED" 한 줄은 워커 보류 계약 문장이라 공통부에 둠(근거 부족 — 학생 업무에 맞게 다듬을지는 후속). 공통부 문구에 HYD · Neo4j · enterprise · hyd-dmn · PLC · 설비 · cause: · describe_schema · schema_prompt 없음(시험).
- 바이트 동일: `constitution(HYD_PLANT)` == 2fbefff 의 CONSTITUTION(1940자, 3936바이트) — 고정 파일 `tests/fixtures/constitution_hyd_2fbefff.md`. 실제 Runner 로 기준 에이전트(sys:agent, hyd-plant) 실행 시 작업 폴더 CLAUDE.md 바이트 동일 · Codex 프롬프트 앞부분 바이트 동일 · 알림 없음.
- 시험 `tests/test_capstone_g9_work_rules.py` 8개 통과(바이트 고정 · 기준 에이전트 실행 · Codex · 업무부 없음 → 공통부만 + 알림 + task.json · 모르는 키 → CLI 안 띄우고 실패 사유 · 시드/마이그레이션 · 복제/고치기 유지/비우기 · 새 에이전트 None/모르는 키 거절). 기존 시험 수정: test_worker(시드 모양 + provision 인자), test_u2(provision 인자), test_c3_assembly(공통부에서 한국어 규칙 확인), test_b1 · test_b6 시드에 sys:agent work_rules(seed.sql 과 같게), test_b6 BAD_CASES 에 "모르는 업무 규칙" + 검사 단계 거절 확인.
- 뮤테이션: G1 모르는 키를 공통부로 대체 2 실패 · G2 알림 끔 1 · G3 Codex 공통부만 1 · G4 복제가 칸 버림 1 · G5 HYD 문구 한 글자 3 · G6 설정이 칸 안 읽음 3 · G7 공통부에 HYD 섞임 1 · G8 내보내기가 칸 버림 1 · G9 가져오기 검사 끔 — 처음엔 살아남음(적용 단계가 같은 사유로 실패 · 되돌려 같은 결과) → BAD_CASES 시험에 "검사 단계 거절(failed_step 없음)"을 더해 다시: 1 실패로 잡힘.
- 관련 시험 12개 파일 272 통과 · 3 건너뜀(PG DSN 없는 것).
- 전체 스위트 1차: 1 실패 — `test_u1_task_detail.py::test_worker_task_and_manual_extraction_show_the_agents_words_tools_and_proposal`: 새 알림 문구에 `work_rules`(영문 식별자)가 들어가 포털 패널 영문 잔재 검사에 걸림 → 문구에서 뺌. 이 시험의 추출 실행은 `sys:agent` 로 도는데 시험 시드에 업무 규칙 값이 없어 알림이 보였다(실제 seed.sql 은 hyd-plant — 운영 영향 없음).
- 같은 조사에서 찾은 위험: 이미 시드된 라이브 DB 가 마이그레이션만 올리면 기준 에이전트 넷이 null → 공통부만 받는다(기준 동작 변경). 조치: 마이그레이션에 같은 갱신(`work_rules is null` 일 때만)을 넣음 — 새 DB 에서는 행이 없어 아무 일 없고 seed.sql 이 넣는다. 시험 + 뮤테이션 G10(갱신 빠짐 → 1 실패).

## 5. 검증됨 / 미검증
- 검증됨(단위 · 통합 시험, MemoryRepo · 실제 Runner · 실제 mcp_check 와 가짜 stdio MCP 서버): 위 G3 · G9 · 모르는 칸 전부, 뮤테이션 18건 전부 잡힘(M1~M9, G1~G10; 첫 M6 은 문법 오류 변이로 다시 함, 첫 G9 는 살아남아 시험 보강 뒤 잡힘).
- 미검증: 라이브 스택(Supabase 마이그레이션 실제 적용 · 실제 워커 · 실제 구글 MCP), 포털 화면에서 `MCP_RESULT_VALUES` · 알림 줄이 읽히는 모습(같은 모양의 사건이 caseRecord.js 76행 · trace.js 174행 기존 분기로 그려진다는 것은 코드로만 확인), Pg 경로의 agent_authoring insert/update(PG DSN 시험 건너뜀).
- 하지 않은 것(기록): ① effect:false 의 사전(정적) 읽기 판정 — 실행 시점 판정이 권위라 두지 않음. ② 포털 에이전트 화면에 업무 규칙 표시 · 고르기 — 학생은 비워 두는 것이 기본이고, 처리 기록 알림과 task.json 으로 보인다. ③ 흐름 단위 업무 규칙(요구의 "또는 흐름") — 에이전트 칸 하나로 충분. ④ 실패한 서비스 task 의 도구 호출 사건이 전이와 함께 되돌려지는 기존 동작(블랙박스 후속).

## 6. 라이브에서 확인할 절차(다른 담당 라이브 검증이 끝난 뒤)
1. `supabase migration up`(또는 reset) 뒤 `select id, work_rules from users where is_agent` — 기준 넷이 hyd-plant, 학생 것은 null.
2. 워커 재기동 후 A 시나리오 한 건: 작업 폴더 `CLAUDE.md` 를 `tests/fixtures/constitution_hyd_2fbefff.md` 와 `cmp` — 같아야 함. 처리 기록에 "업무 규칙이 붙어 있지 않아" 알림이 없어야 함.
3. 포털에서 새 에이전트(업무 규칙 없음)를 만들어 흐름 하나에 묶고 한 건: CLAUDE.md 에 HYD · Neo4j 문구 없음, 처리 기록에 알림 한 줄.
4. G3: 읽기 도구가 있는 학생 MCP(연결 검사 통과)로 `svc:mcp-call` effect:false + extract 흐름을 가져와 한 건 — task 상세에 "MCP 결과에서 값을 꺼냄"과 넘긴 값, 분기 하이라이트. 같은 흐름에 쓰기 도구(예: hyd-effects send_mail)를 effect:false 로 두면 PENDING + 거절 사유, 수업 메일함에 메일 0통.
- 전체 스위트 최종 1회: 1992 통과 · 4 건너뜀 · 0 실패 (191 s).

## 7. 추가 근본 수정(코디네이터): 실패한 시도의 도구 호출 기록이 사라지던 것
- 원인(실물 확인): 서비스 처리기는 처리 건 전이 안에서 돈다(instances._run_service → _transition → repo.instance_transaction). 사건 쓰기도 같은 연결을 쓴다(procdb Pg record_events 가 전이의 연결을 재사용, MemoryRepo instance_transaction 206~214행은 실패하면 events 까지 되돌림). 그래서 실패한 시도의 tool_usage_started/finished 가 상태와 함께 사라지고 error 사건(_fail, 전이 밖)만 남았다. 분류: 결함(요구 '처리 과정에 블랙박스 없음').
- 참고 레포: ProcessGPT processgpt_agent_sdk database.py 211~251행 record_events_bulk · record_event — 사건은 상태 변경과 따로 남기는 일지. 같은 원칙을 따름.
- 조치: 상태 정합성은 그대로(되돌림 유지). 이 호출이 전이를 여는 경우에만(instances.py:912, 중첩이면 되돌림이 없으므로 모으지 않음 — 중복 방지) 시도 동안 도구 호출 사건(crew tool)을 따로 모으고(service_parts.py:54 _event), 실패하면 되돌린 뒤 그것을 attempt_failed=true 로 남기고(service_parts.py:62 _keep_failed_attempt_trace) 이어서 기존 _fail 이 error 사건(사유 · 회차)을 남긴다. 성공하면 지금처럼 전이 안에서 한 번만 남는다.
- 시험 tests/test_failed_attempt_trace.py 3개: 도구가 오류를 돌려주는 읽기 확인을 3회 재시도 → PENDING 까지 회차마다 started(서버.도구 · 입력) · finished(오류 본문, attempt_failed) · error(retry 1,2,3 · 사유)가 그 순서로 남음, 출력 · 다음 단계 없음(되돌림 유지) / 성공 시 한 번만 / task 상세 패널(node 렌더)에 회차마다 도구 줄과 오류 문구가 보임.
- 뮤테이션: T1 남기기 끔 → 2 실패, T2 모으기 끔 → 2 실패. 관련 시험 7개 파일 113 통과. 전체 스위트 1995 통과 · 4 건너뜀 · 0 실패.
- (7.1 에서 고침) 실패한 시도의 감사 기록도 전이와 함께 버려지던 것. 라이브(Pg)에서 같은 동작은 미검증(Pg 경로는 같은 record_events 를 전이 밖에서 부름 — 코드 확인만).

### 7.1 추가 근본 수정(코디네이터): 실패한 시도의 감사 기록
- 원인(같은 원인): `_transition` 은 `_after_commit` 으로 미룬 일(감사 포함)을 커밋에 성공한 뒤에만 실행한다(instances.py 140~145행). 실패하면 그 목록이 상태와 함께 버려져 MCP_READ_FAILED · MCP_EFFECT_FAILED · SKILL_FAILED 같은 실패 사실이 감사 기록에서 사라졌다. 분류: 결함.
- 조치: 시스템 task 시도가 전이를 소유할 때만 `_after_commit(self.hooks.audit, …)` 을 따로도 모은다(instances.py `_after_commit` — 감사 훅만, 다른 커밋 뒤 일(알림 · 투영)은 모으지 않음). 실패하면 되돌린 뒤 `_keep_failed_attempt_record`(service_parts.py, 사건 기록과 같은 자리 — 이름을 `_keep_failed_attempt_trace` 에서 바꿈, 옛 이름 검색 0)가 감사를 detail 에 attempt_failed=true 로 한 번씩 남긴다. 감사 저장 실패는 커밋 뒤 일과 같은 규칙으로 로그에 남기고 task 실패 처리를 막지 않는다. 성공한 시도는 커밋 뒤 한 번만(이 길을 타지 않음).
- 시험 tests/test_failed_attempt_trace.py 5개 통과: 3회 재시도 → MCP_READ_FAILED 감사 3건(attempt_failed · 서버 · 도구 · 처리 건), MCP_READ_CALLED 0 / 성공 시 MCP_READ_CALLED 1건 · attempt_failed 없음 / 이미 열린 전이 안에서 불리면(되돌림 없음) 도구 사건 · 감사 모두 한 번씩.
- 뮤테이션: A1 감사 모으기 끔 → 1 실패, A2 감사 버퍼가 전이 소유 무시 → 1 실패, A3 사건 버퍼가 전이 소유 무시 → 1 실패(앞 커밋의 중첩 방지 가드도 이번에 시험으로 덮음).
- 관련 시험 7개 파일 115 통과. 전체 스위트 1997 통과 · 4 건너뜀 · 0 실패.
- 관찰(이번 범위 밖, 기록): 이미 열린 전이 안에서 실패하면 `_fail` 이 기존 consumer 가드로 일찍 돌아가 error 사건이 남지 않는다. 지금 그 경로를 부르는 코드는 없다(_run_service 호출처는 poll_once · reconcile_services 뿐).
