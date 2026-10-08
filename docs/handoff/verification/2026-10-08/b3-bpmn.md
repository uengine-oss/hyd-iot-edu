# B3 — bpmn.io 그림 가져오기 → 부품 · 담당 매핑 → 사전 검사 → 판본 등록 (확정 TODO B3, DECISIONS 110 ②, 2026-10-08 밤)

범위: `TODO.md` 확정 TODO B 표 **B3**. 학생은 demo.bpmn.io 에서 흐름을 그리고 **Download BPMN diagram** 으로 받은 `.bpmn`(BPMN 2.0 XML)을
포털 **판단 → 흐름 가져오기** 화면에 올린다. 포털 안 모델러는 만들지 않는다(DECISIONS 110 ②). bpmn.io 기본 화면에는 조건식 · 확장 속성 입력이
없다고 보고, 실행에 필요한 것(부품 · 담당 · 시작 조건 · 분기 조건 · 타이머 기간)은 전부 포털 매핑 표에서 고른다.
경계: **등록까지**. 운영 판본 포인터(proc_def.prod_version)를 움직이는 배포 · 경보가 배포 판본을 쓰는 것 · 기준과 비교는 B4.

비유 한 줄: bpmn.io 그림은 "배선도", 부품은 "규격이 정해진 기성 모듈"이다. 배선도의 칸마다 모듈을 꽂고, 전원(시작 조건)과 스위치(분기 조건)를
정하면 사전 검사가 "모듈 입력에 신호가 들어오는가 · 차단기(사람 승인) 없이 설비에 전기가 가는가 · 회로가 닫히는가"를 본다.

## 원본 대조 (원본 파일:줄 → HYD)
| 원본 | 무엇 | HYD | 차이 · 판단 |
|---|---|---|---|
| process-gpt-bpmn-extractor@c7992ce `src/pdf2bpmn/bpmn_to_json.py:179-224` | lane → role(`flowNodeRef` 색인, `uengine:json` 의 endpoint) | `bpmn_import.parse_bpmn` `_lanes`(가장 안쪽 칸이 담당, childLaneSet 포함) → 매핑 `lanes{lane id: 역할 이름}` | bpmn.io 기본 그림에는 `uengine:json` 이 없으므로 칸 이름이 역할 이름과 같으면 그 역할을 미리 고르고, 아니면 사람이 고른다 |
| 같은 파일 `:251-335` `_extract_events` · `_extract_activities` | task 4종 · 시작/끝/중간 이벤트, task 확장 JSON 에서 tool · inputData · outputData 복원 | task 8종(`task·userTask·manualTask·serviceTask·scriptTask·businessRuleTask·sendTask·receiveTask`), 시작(빈 · 메시지) · 끝(빈 · 에스컬레이션) · **경계 타이머**(timeDuration) | 원본은 확장 JSON 이 없으면 `formHandler:defaultform`·빈 입출력으로 채움(빈 성공). HYD 는 BPMN 종류를 힌트로만 보고 **부품을 사람이 고르게** 한다. 중간 이벤트 · terminate 끝 · 멈추지 않는 타이머는 사유와 함께 거절 |
| 같은 파일 `:337-370` `_extract_gateways` · `_extract_sequences` | exclusive · parallel · **inclusive**, 선의 조건은 빈 문자열 | exclusive · parallel 만(inclusive · event-based · complex 는 요소 id · 이름과 사유), 선의 `conditionExpression` 은 엔진 조건식으로 읽히면 기본값, 아니면 매핑에서 고름 | 엔진(`engine.py`)이 실행하는 것만 받는다 |
| process-gpt-completion@b272c9a `polling_service/process_definition.py:77-96` | `ProcessSequence{id,name,source,target,condition,properties}` · `ProcessGateway{conditionData}` | 같은 칸 이름으로 정의 JSON 생성(`sequences[].condition` · `properties.default` · `gateways[].conditionData`) | 같음 |
| process-gpt-vue3@867e8cf `src/components/ProcessDefinitionChatHeader.vue:128-137` | 정의 편집기 메뉴 "BPMN 파일 가져오기"(`accept=".bpmn"`) → bpmn-js 편집기 | `flows.js` 파일 고르기 → 서버 파싱 → 매핑 표 | 원본은 bpmn-js 편집기에 올려 속성 패널에서 고친다. HYD 는 편집기 없이 매핑 표(DECISIONS 110 ②, 버린 대안: 포털 모델러) |
| 같은 원본 `src/components/api/ProcessGPTBackend.ts:573-611` · `:664-685` `putRawDefinition` | `proc_def.bpmn = xml`, `proc_def_version.snapshot = xml`, published 판본은 불변(번호 올림) | `bpmn_store.FlowStore.register`: `proc_def_version(snapshot=.bpmn 원본, origin='user', version_tag='hyd-immutable')`, `proc_def(bpmn, origin='user')` | 같은 칸. 원본은 저장 때 `proc_def.definition` 도 바꾼다 — HYD 는 **운영 판본 포인터(prod_version · definition)를 건드리지 않는다**(배포는 B4). 판본 번호는 학생 흐름마다 1, 2, 3 … |
| process-gpt-bpmn-extractor `src/pdf2bpmn/validation/process_validator.py` `_static_check`(A096 에서 이미 대조) | 닿지 않음 · 끝에 못 닿음 · 게이트웨이 없는 갈림 | 사전 검사가 같은 규칙을 **칸 위치(요소 종류 · id · 이름)와 사유 목록**으로 모두 보여 준 뒤, 통과하면 기존 등록 검사(`validate_definition`)까지 | 원본은 점수 · 경고. HYD 는 거절 |

## 만든 것 · 바꾼 파일
| 파일 | 내용 |
|---|---|
| `it/process/procsvc/bpmn_import.py` (새) | 순수 로직. `parse_bpmn`(표준 `xml.etree`, DOCTYPE/ENTITY 거절, 2 MB 상한, 풀 하나만) · `catalog`(부품 목록 — **기준 정의 파일의 activity 에서 읽어 만든다**, 코드에 부품 내용 없음) · `merge_mapping`(다시 가져오기) · `check`(정의 JSON 생성 + 사전 검사) · `structure`(id · 이름 뺀 구조 서명) |
| `it/process/procsvc/bpmn_store.py` (새) | 초안(`proc_bpmn_draft`) · 판본 등록(그림 원본 함께, 포인터 불변) · 그림 내려받기 · 기준으로 되돌리기. PgRepo(SQL) / MemoryRepo(단위 시험) 두 갈래 |
| `it/process/procsvc/flows_api.py` (새) | 아래 API 9개. legacy 모드 503 |
| `it/process/procsvc/main.py` (+4줄) | `flows_api.register(app, runtime_factory=instance_mode.current, audit=_audit)` |
| `it/process/procsvc/definition_registry.py` | ① `loopPolicy: "guarded"` 가 있는 정의만 반복을 받고 `_guarded_loops`(반복마다 빠져나갈 배타 게이트웨이 · 병렬 게이트웨이 없음)로 검사 — 없으면 예전처럼 "반복 실행은 아직 검증되지 않았습니다" ② `_static_connectivity` 의 "끝에 닿는가"를 끝에서 거꾸로 닿기로 바꿈(예전 memo DFS 는 반복 위 노드를 잘못 죽은 노드로 판정 — 비순환 정의 결과는 같음) |
| `it/process/procsvc/instance_mode.py` · `legacy_assessment.py` · `instances.py` (각 10~20줄) | **수업 기본 경로(AGENT_BRIDGE=legacy)가 그림 id 로도 돌게**: 내장 결정론 판단(C4 평가기 `LegacyAssessment`)과 결과 재생(`_bridge_legacy_agent` · `reconcile_legacy_decisions`)이 activity id 대신 **기준 정의의 같은 tool 계약**으로 원인 진단 · 후보 · 규정 · 순위 task 를 찾고(`_legacy_key` · `_tools`), 조치 전 사건 종료(A074) 경로가 제어 경로 · 상급자 호출을 tool(`incident:command · incident:reobserve · enterprise:WO_CREATE` · `formHandler:escalate`)로도 찾는다. 기존 id 판정은 그대로 먼저 본다 |
| `it/supabase/migrations/20261008000043_flow_import.sql` (새) | `proc_def.origin` · `proc_def_version.origin`(학생 = `'user'`, 기준 = 비어 있음), `proc_bpmn_draft(tenant_id, proc_def_id, bpmn, file_name, mapping)` + RLS · 권한(000040 과 같은 교육 정책) |
| `it/portal/www/flows.js` · `flows.css` (새) | `window.hydFlows.mount(el)` — 가져오기 · 시작 조건 · 칸 → 역할 · task → 부품 · 담당 · 시간 초과 · 분기 조건 · 검사 · 판본 등록 · 내 흐름 목록(그림 받기 · 직접 시작) · 기준으로 되돌리기. 순수 함수 `window.hydFlows.pure`(폼 칸 글 ↔ 칸 · 기준 값 · 분 ↔ ISO) |
| `it/portal/www/index.html` (+7줄) · `shell.js` (+1줄) | 메뉴 "판단 → 흐름 가져오기"(`data-tab="flows"`), `<section id="view-flows"><div id="flowsView">`, css · script 한 줄씩, `MOUNTS.flows = 'hydFlows'` |
| `docs/definition-authoring.md` (1문장) | 공개 등록 계약의 반복 거절 예외(`loopPolicy: "guarded"`) |
| `tests/test_bpmn_import.py` (새, 30개) · `tests/fixtures/bpmn/anomaly_response_redraw.bpmn` (새) | 아래 시험. fixture 는 기준 흐름(anomaly_response 2.2)을 bpmn.io 내보내기 모양으로 다시 그린 그림 — 의미 부분(칸 6 · task 9 · 분기 2 · 끝 2 · 경계 타이머 1 · 선 15, 타이머 기간 없음)은 손으로 정했고 배치 좌표(DI)만 작은 스크립트로 계산(`.evidence/b3/gen_redraw.py`, 커밋 안 함). DI 가 들어 있어 bpmn.io 에 올릴 수 있는 모양이지만 실제로 demo.bpmn.io 에서 열어 본 것은 아니다(메인 확인 4번) |

## 부품 (기준 정의 파일에서 읽음)
- 원천: `it/process/definitions/<PROCESS_DEFINITION_FILE>`(지금 `anomaly_response_v22.json`, 2.2). 학생 판본이 나중에 배포돼도 부품은 이 파일에서 읽는다(`flows_api.default_base_loader`).
- **시나리오 부품** = 기준 activity 하나(원인 진단 · 조치 후보 조회 · 규정 검토 · 우선순위 · 카드 작성 · 조치 카드 선택 · 상급자 호출 · PLC 명령 발행 · 재관측 · 정비 작업지시).
  activity 의 계약(type · role · agent · agentMode · orchestration · decision · tool · instruction · inputData · outputData · checkpoints · duration)과 폼(`forms[<폼 id>]`)을 **그대로** 가져온다.
  사람 부품은 담당 역할만, 에이전트 부품은 맡길 에이전트만 바꿀 수 있다. 시스템 부품(명령 · 재관측 · 작업지시)의 담당은 부품이 정한다.
- 부품 성질은 이름이 아니라 **tool 계약**으로 판정: 사람 승인 = `formHandler:select_card`(역할 검사가 있는 `/select` 경로로만 제출), 효과 = `incident:command`(설비 명령) · `enterprise:WO_CREATE`(작업지시).
- **일반 부품**: 사람 task(담당 역할 · 폼 칸 · 받을 값), 에이전트 task(맡길 에이전트 · 지시문 · 결과 값 이름과 종류 · 받을 값 → `userTask + agentMode COMPLETE + orchestration cliagents`, 폼 = 결과 값), 작업지시(= 기준의 정비 작업지시 부품).
- 역할 목록 = 기준 정의의 roles + users 표의 `role:*` 사람 역할(예: 정비관리자 `role:maint-mgr`). 에이전트 목록 = users 표 `is_agent ∧ agent_type='agent'`(B1 이 만든 에이전트도 여기 나타난다).
- 경계 타이머 기간: 그림의 timeDuration → 매핑 → 그 task 부품의 기준 타이머(조치 선택 PT10M) 순서로 기본값.

## 시작 조건
- **경보 패턴**: 기준 정의 `alertPolicy.patterns` 중 고른 것만(회복 기준 그대로) + `unsupported`(미지원 경보 사람 검토) 그대로. 시작 이벤트는 기준의 메시지 시작(`eventDefinition: message`, `messageRef`, `correlationKey`)을 복사. 시작 때 있는 값 = `asset · alert · pattern · alert_id · incident`(`instances.start_definition` 이 넣는 값).
- **사람 입력 · 직접 시작**: 시작 폼 칸을 정의의 `startForm.fields_json` 에 둔다(엔진은 읽지 않음 — 포털 "직접 시작"이 이 칸으로 기존 `POST /api/instances/start {variables}` 를 부른다). 시작 값 = 폼 칸. `incident · approved_by · chosen_option · commands · decision_id` 같은 서버 승인 값 이름은 거절.

## 사전 검사 (모두 칸 위치 `{kind, kind_label, id, name}` + 매핑 칸 `field` + 사유)
1. 읽기: XML 오류(행 · 열), 지원하지 않는 요소(하위 프로세스 · callActivity · 포함/이벤트/복합 분기 · 중간 이벤트 · terminate 끝 · 멈추지 않는/날짜/반복 타이머 · task 반복 표시), 풀 여러 개, 없는 요소를 가리키는 선.
2. 부품: 고르지 않은 task, 목록에 없는 부품 · 역할 · 에이전트, 사람 역할이 아닌 담당, 비어 있는 지시문 · 결과 값, 쓸 수 없는 값 이름.
3. 끊긴 선 · 끝 닫힘: 들어오는/나가는 선 없음, 시작에서 닿지 않음, 끝 이벤트에 닿지 못함, 끝 이벤트 없음, 분기 없이 여러 갈래.
4. 분기 조건: 배타 분기에서 나가는 선마다 "값 · 비교(== != > >= < <=) · 기준" 또는 "그 밖의 경우"(하나만). 값은 **분기 앞 단계가 낸 값**에서 고른다(`available`). 크기 비교에는 숫자만.
5. 값 연결: task 가 받을 값마다 시작 또는 앞 단계(그 task 로 올 수 있는 노드)가 내는가. 사람 승인 부품은 서버 승인 값(`approved_by · approved_role · chosen_option · commands`)도 낸다.
6. **안전**: 시작에서 효과 부품(설비 명령 · 작업지시)까지 사람 승인(조치 선택)을 거치지 않고 가는 길이 있으면 거절. 승인 task 의 **시간 초과 갈래는 승인으로 치지 않는다**. 되돌아가는 선이 효과 부품을 승인 없이 다시 실행해도 거절.
7. 되돌아가는 선(루프): 살려서 `sequences` 에 넣고 정의에 `loopPolicy: "guarded"`. 반복마다 빠져나갈 배타 분기가 있어야 하고 병렬 분기는 안에 둘 수 없다(엔진 재진입 `engine.py` `_advance` "re-entry (loop) → a fresh row").
8. 위가 모두 통과하면 기존 등록 검사 `validate_definition`(폼 = outputData, 서비스 도구 목록, 조건 변수 생산자, 정적 연결 …) — 실패 사유는 "등록 검사: …".

## API
- `GET /api/flows/catalog` → `{base, parts[], roles[], agents[], agent_role, patterns[], alert_policy, alert_start, data{}, field_types, ops, alert_start_values, approval_values}`
- `POST /api/flows/import {xml, file_name?, definition_id?}` → `{definition_id, file_name, parsed, mapping, reimport{previous, kept[], dropped[], new[]}, check{ok, problems[], definition, available{node id: [{value, from}]}, loops}, next_version, versions[], base}`.
  흐름 id 를 비우면 그림의 프로세스 id. 기준 정의 id(origin 이 user 가 아닌 판본 · 머리가 있는 id) → **409**. XML 오류 → 400 `{reason, problems}`.
- `GET /api/flows` → `{drafts[], versions[]}` · `GET /api/flows/{id}` → import 와 같은 모양(초안 없으면 404)
- `PUT /api/flows/{id}/mapping {mapping}` → 저장 + 검사 · `POST /api/flows/{id}/check {mapping?}` → 검사만
- `POST /api/flows/{id}/register {mapping?}` → **201** `{definition_id, version, name, origin:"user", deployed:false, start, definition}` · 검사 실패 400 `{reason:"사전 검사를 통과하지 못해 등록하지 않았습니다 (N건) — <첫 칸>: <사유>", problems}` · 감사 `FLOW_REGISTERED`
- `GET /api/flows/{id}/versions/{v}/bpmn` → 그 판본의 `.bpmn` 원본(`Content-Disposition: attachment; filename="<id>-v<v>.bpmn"`), 그림이 없는 판본(기준 등) 404
- `POST /api/flows/reset` → `{versions, definitions, drafts, hidden_instances}` · 진행 중(NEW · RUNNING) 처리 건이 학생 판본을 쓰면 **409** `{reason, running[]}`(아무것도 지우지 않음) · 감사 `FLOWS_RESET`

매핑 형식(초안 · 판본의 `bpmnImport.mapping`):
```json
{"name": "흐름 이름",
 "start": {"kind": "alert", "patterns": ["COOLER_DEGRADATION"]}   // 또는 {"kind": "human", "fields": [{"key","text","type","items?"}]}
 "lanes": {"<lane id>": "<역할 이름>"},
 "tasks": {"<task id>": {"part": "<기준 activity id>", "role?": "...", "agent?": "..."}
          | {"part": "human", "role": "...", "fields": [...], "inputs": [...]}
          | {"part": "agent", "agent": "...", "instruction": "...", "outputs": [{"key","type"}], "inputs": [...]}},
 "timers": {"<boundary id>": "PT10M"},
 "flows": {"<flow id>": {"var": "...", "op": "==", "value": "control"} | {"default": true}}}
```

## 기준 보호 · 되돌리기
- 학생 판본은 `origin='user'`. 기준 흐름 id(`anomaly_response` · `alert_triage` · origin 없는 판본이 있는 id)로는 가져오기 · 등록 모두 409.
- 등록은 `proc_def_version` 에 새 판본만 넣고 `proc_def` 머리는 학생 흐름이면 `bpmn · name` 만 갱신(prod_version · definition 은 NULL 그대로). 기준 머리는 손대지 않는다(PG 시험에서 등록 전후 같은 행).
- 되돌리기: `origin='user'` 판본 · 머리 · 초안만 지우고, 그 판본으로 **끝난** 처리 건은 `is_deleted=true`(정의가 사라지므로 목록에서 숨김). 진행 중이면 거절.
- 코드 · 시드에 정답 없음: 부품은 기준 파일에서 읽고, 매핑을 미리 채우는 것은 "칸 이름 = 역할 이름"과 "그 부품의 기준 타이머 기간"뿐(부품 · 조건은 사람이 고른다).

## 시험
- `tests/test_bpmn_import.py` **30개**(PG 1개는 `HYD_FLOW_PG_DSN` 이 있을 때만):
  - 다시 그린 기준 흐름 → 부품 고르기 → `structure(변환) == structure(기준 2.2)`(activity 계약 · 폼 · 선과 조건 · 경계 타이머 · 역할 · data · 경보 정책) / 조건 하나 · 부품 하나 · 타이머를 바꾸면 서명이 달라짐(비교가 공허하지 않음) / 변환 정의로 경보 시작 → 에이전트 4 → 시간 초과 → 상급자 → 에스컬레이션 끝까지 엔진에서 실제로 돎.
  - 일부러 깨뜨림: 승인 앞 설비 명령(우선순위 → 분기 직결) → `작업 'PLC 명령 발행' — 설비 명령 부품 앞 경로에 사람 승인('조치 카드 선택 (HITL)')이 없습니다` + 끊긴 선 / 시간 초과 갈래로 명령 → 거절 / 루프로 명령 재실행 → 거절 / 선 하나 지움 → 나가는 · 들어오는 선 없음 / 없는 요소를 가리키는 선 / 조건 누락 → 그 선 id · 분기 이름 / 앞 단계가 안 낸 값 → 받는 task 위치 / 부품 미선택 / 포함 분기 · 하위 프로세스 → 요소 id · 이름 / 읽을 수 없는 파일 5종.
  - 루프: 되돌아가는 선이 `sequences` 에 남고 `loopPolicy: "guarded"`, 실제 실행에서 측정 → 기준 밖 → 새 작업 행 → 기준 안 → 끝(작업 행 2개) / 빠져나갈 분기 없는 반복 거절 · loopPolicy 없는 반복은 공개 등록에서 그대로 거절 · 반복 안 병렬 분기 거절.
  - 사람 입력 시작 + 일반 부품(에이전트 · 사람, 정비관리자 역할) 정의 → 기존 `start_definition` 으로 시작 → 에이전트 작업이 `COMPLETE/cliagents` 로 열리고 시작 값이 입력에 들어감 / 시작 값이 안 낸 값 · 서버 승인 값 이름 · 사람 역할 아닌 담당 거절.
  - API: 등록 → 판본 1 · 같은 흐름 다시 등록 → 판본 2(1 불변) · 기준 머리 불변 · 새 흐름 머리 없음 · 그림 받기 = 원본 그대로 · 404 / 검사 실패 400(칸 위치) · 기준 id 409 · XML 오류 400 · 잘못된 흐름 id 400 / 다시 가져오기: 같은 id 매핑 유지 · 지운 task 는 dropped · 새 task 는 "부품을 고르세요" / 되돌리기: 진행 중이면 409 · 끝나면 학생 것만(기준 판본 목록 동일) · 감사 / legacy 모드 503 / 부품이 기준 파일에서 읽힘(파일을 바꾸면 부품 계약이 바뀜, 소스에 부품 내용 없음) / 포털 순수 함수(node).
  - 수업 기본 경로: 가져온 흐름(그림 id)으로 경보 시작 → C4 평가기가 원인 진단 task 를 집어 네 에이전트 task DONE → 조치 선택 → 생산관리자 승인 → 설비 명령(AWAITING_ACK) / 조치 전 경보 해제 → 열린 일 취소 · 그림의 상급자 호출 → 에스컬레이션 끝.
  - 고의 변형 확인: 승인 검사를 끄면 3개, 승인 경로 차단을 끄면 4개, `_legacy_key` 를 끄면 1개, `legacy_assessment` · `instances` tool 판정을 되돌리면 각 1개 시험이 실패했다(되돌린 뒤 모두 통과).
- 실제 PostgreSQL 16(임시 클러스터 — Supabase CLI · docker 아님, 마이그레이션 파일 **33개 전부**(000001~000043) 적용 오류 0): `HYD_FLOW_PG_DSN=… pytest -k pg` 통과 — 기준 머리 행 불변, 학생 머리 `prod_version · definition` NULL · `bpmn` = 원본 · `origin='user'`, 판본 snapshot 2건, 되돌리기 거절 → 끝난 뒤 `{versions:3, definitions:2, drafts:2, hidden_instances:1}`. 임시 클러스터는 지움.
- 전체: `HYD_FLOW_PG_DSN=… pytest -q` **1538 passed, 1 skipped**(3분 16초, `.evidence/b3/pytest-full.log`). `node --check flows.js · shell.js` 통과.
- 화면(Playwright, MemoryRepo API + 정적 포털, 증거 worktree `.evidence/b3/`): 메뉴 → 다시 그린 그림 가져오기 → task 9행 → 이름 보고 부품 고르기 → 분기 조건 4건만 남음 → 조건 4개 → 검사 통과 → 판본 1 등록 · 그림 받기 링크 → 조치 선택을 사람 task 로 바꾸면 `작업 PLC 명령 발행 — … 사람 승인 … 없습니다` 거절 → 루프 그림 + 사람 입력 시작 등록 → 직접 시작 → `#/instances/<id>` · 흐름 화면 영문 id 0 · 페이지 오류 0 (12/12, `b3-ui-smoke.json` · `b3-mapping.png` · `b3-refused.png`).

## 메인이 라이브로 확인할 경로 (합친 뒤, 배포 → 검사 순서)
0. 마이그레이션 `20261008000043_flow_import.sql` 적용, process 이미지 재빌드(새 파이썬 파일 3개 + definition_registry · instance_mode · instances · legacy_assessment · main), 포털 정적 파일 갱신. `PROCESS_MODE=instance`. 검사기가 돌지 않을 때 배포(CLAUDE.md §3).
1. `curl :8080/api/flows/catalog` → parts 에 기준 9개 + 사람 task · 에이전트 task, patterns 3개.
2. 포털 **판단 → 흐름 가져오기** → `tests/fixtures/bpmn/anomaly_response_redraw.bpmn` 을 흐름 id `my_cooler` 로 가져오기 → task 이름 보고 부품 9개 → 분기 4선 조건(`chosen_skill_kind == control / work_order`, `recovered == 예 / != 예`) → 검사 통과 → **판본 등록** → "판본 1".
3. psql: `select id, prod_version, definition is null, origin, length(bpmn) from proc_def where id in ('anomaly_response','my_cooler');` → 기준 행 그대로, my_cooler 는 prod_version NULL · origin user. `select version, origin, length(snapshot) from proc_def_version where proc_def_id='my_cooler';`
4. 목록의 **그림 받기** → 받은 파일을 demo.bpmn.io 에 끌어다 놓으면 같은 그림(fixture 가 bpmn.io 에서 열리는지도 여기서 처음 확인).
5. 일부러 깨뜨림: "조치 카드 선택" task 부품을 사람 task 로 → 판본 등록 → `작업 PLC 명령 발행 — 설비 명령 부품 앞 경로에 사람 승인(…)이 없습니다`.
6. 사람 입력 시작: 작은 그림(시작 → 사람 task → 분기 → 되돌아가는 선/끝)을 가져와 시작 폼 칸 · 사람 task 폼 칸 · 조건 → 등록 → **직접 시작** → 처리 건 화면에서 같은 task 가 두 번 열리는지(되돌아가는 선).
7. **기준으로 되돌리기** → 진행 중 처리 건이 있으면 사유와 함께 거절, 닫은 뒤 다시 → 학생 흐름만 사라지고 `anomaly_response` 판본 목록(`GET /api/process/definitions`) 그대로.

스스로 판정할 체크 질문:
- 받은 `.bpmn` 을 bpmn.io 에서 다시 열었을 때 내가 그린 그림 그대로인가(포털이 그림을 바꾸지 않았나)?
- 승인(조치 선택)을 지나지 않고 "PLC 명령 발행"이나 "정비 작업지시"에 닿는 선을 하나 그리면 등록이 거절되는가 — 시간 초과 선으로 우회해도?
- 판본을 등록한 뒤에도 새 경보가 여전히 기준 흐름(anomaly_response 2.2)으로 열리는가(배포 전)?

## 남은 위험
- **B4 와의 경계**: 배포가 `proc_def.prod_version` 을 학생 판본으로 옮긴 뒤 되돌리기를 누르면 내 reset 은 그 판본을 지운다 — 합친 버튼은 **B4 되돌리기(포인터 원위치)를 먼저**, 그다음 `POST /api/flows/reset` 순서로 부를 것. 진행 중 처리 건이 있으면 내 reset 은 거절한다.
- 기존 공개 경로 `POST /api/process/definitions`(관리 화면 JSON 등록)는 여전히 아무 id 로나 새 판본을 넣고 `proc_def.prod_version` 을 옮긴다(`procdb.upsert_proc_def`) — 기준 id 보호는 내 가져오기 경로에만 있다. B4 가 배포 포인터를 정의하면서 이 경로도 정리할 것.
- 일반 에이전트 task 는 계약(userTask + COMPLETE + cliagents, 폼 = 결과 값)까지 시험했고 **실제 워커가 지시문만으로 결과를 내는지는 라이브 미확인**. AGENT_BRIDGE=legacy 의 내장 결정론 경로는 **시나리오 부품 4개(원인 진단 · 조치 후보 · 규정 검토 · 우선순위)만** 대신한다(그림 id 여도 tool 로 찾음 — 시험) — 일반 에이전트 task 는 워커가 없으면 기다린다.
- 기준 activity id 를 직접 보는 곳이 더 있을 수 있다(포털 표시 용어 `flow.name.*` 는 이름 기준이라 영향 없음). 이번에 찾아 고친 곳: C4 평가기 · 결과 재생 · A074 조치 전 종료. 나머지 id 판정(`legacy_meaning` · `manual_*` 의 자체 정의)은 학생 흐름과 무관.
- 사람 입력 시작 흐름에서 승인 · 효과 부품을 쓰려면 `incident`(경보가 만듦)가 필요해 값 연결 검사에서 거절된다 — B7(작동유, 사람 입력 시작 정비형)은 작업지시 경로에 Incident 없이 승인 원문을 만드는 계약이 따로 필요하다.
- 루프는 엔진 재진입 + 등록 검사까지. 루프 안의 재작업(rework) · 입력 바인딩(`inputBindings`) · 경계 타이머 재무장은 통합 검증하지 않았다(`_guarded_loops` 는 병렬 분기만 막는다).
- `startForm` 은 HYD 추가 칸(제품 정의에는 없음) — 포털 직접 시작만 읽는다. 엔진은 시작 값의 종류를 검사하지 않는다(포털에서 숫자 칸만 숫자로 바꿔 보냄).
- bpmn.io 외 도구(Camunda Modeler 등)의 `conditionExpression`(JUEL `${…}`)은 엔진 조건식으로 읽히지 않으면 버리고 매핑에서 다시 고르게 한다.
- HANDOFF §9 · TODO B3 줄 · 작업보고는 합칠 때 메인이 갱신(공유 파일 충돌을 피해 이 단위에서는 고치지 않음).
