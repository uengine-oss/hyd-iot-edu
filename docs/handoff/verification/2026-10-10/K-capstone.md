# K 갈래 — 캡스톤(전체 과정 랩업) 이어가기 (K-20261010-capstone)

> 2026-10-10 · 브랜치 `K-20261010-capstone`(작업 브랜치 5e30f4f에서 갈라짐) · 작업 트리 `.claude/worktrees/K-20261010-capstone`
> 근거: `NOW.md` 3.4, 설계 `verification/2026-10-09/capstone-lab.md`, 구현 기록 `cap-g1g7.md` · `cap-g3g9.md` · `cap-kit.md`, 검토 `2026-10-09/review-scripts-kit.md`
> 증거: 루트 `.evidence/k-capstone/`(gitignore — 이 PC에만 있다)
> 형식: 발견 → 분류(결함 / 의도된 차이 / 오해 / 근거 부족) → 조치(파일:줄) → 검증(검증됨 / 실패 / 미검증 / 해당 없음)

## 합칠 때 옮길 것
- (작업하며 채움)

## 0. 시작
- 통독: 프로젝트 CLAUDE.md, NOW.md 전체, REVIEW_CHECKLIST.md, capstone-lab.md, cap-g1g7.md, cap-g3g9.md, cap-kit.md, review-scripts-kit.md, `students/_template/` 전체.
- 시작 상태(실측): 브랜치 5e30f4f, `.evidence/LIVE_LOCK` 없음, 그래프 볼륨 `hyd-iot-edu_neo4j-data`(전체판), 8097 듣는 워커 없음, `/api/scenario/status` B running null.
- 사용자는 외출 중 — 사용자 결정이 필요한 것은 하지 않고 끝의 "사용자가 할 일 · 결정할 일"에 모은다.

## 1. T2 — 학생 지식 적재 · 되돌리기 · 꼭 답할 질문 검사 틀 (잠금 없이)
- 발견: `students/_template/` 에 T2 가 없어 T8 `graph.json` 을 그래프에 넣는 길이 없었다(설계 6.1 T2, 6.2 "마친 뒤 정리"의 ns 단위 삭제가 손 질의). 분류: 미구현.
- 조치(커밋 040eecb):
  - `students/_template/load_graph.py` — `check`(그래프 없이 파일 검사) · `load` · `ask` · `wipe`, 폴더는 `--dir`(기본 = 스크립트 폴더).
    - 적재는 한 트랜잭션: ① 내 파일의 id 를 남(수업 기준 · 다른 이름 공간)이 쓰고 있으면 거절 ② 다리 끝(파일에 없는 끝점)은 그래프에 있는 수업 기준 노드만 ③ 쓰기 전 파일 행을 `ontology_v2.validate_ns` 로 검사 ④ MERGE(값은 매개변수) ⑤ 커밋 전에 그래프를 다시 읽어 같은 검사 + 같은 id 중복 + 수업 기준 노드 수 변화 → 하나라도 걸리면 되돌림.
    - 되돌리기는 `MATCH (n {ns: $ns}) DETACH DELETE n` 만. 지울 것이 0개면 실패(빈 성공 금지), 내 접두어 id 가 남으면 실패, 수업 기준 노드 수가 달라지면 되돌림. 흐름 투영(G8) 노드도 함께 지워지므로 종류별 개수를 보여 준다.
    - 질문은 `it/neo4j/v2/queries.cypher` 형식(`ontology_v2.parse_queries` 재사용), `$ns` 필수, 읽기 전용 세션, 0행 = 못 답함.
  - `students/_template/graph.json` · `questions.cypher`(T1 예시 s00 의 가장 작은 조각), `example_meeting/questions.cypher`(D1~D3 의 "답할 질문" 9개), `example_meeting/README.md` 한 줄.
  - 영역 밖 최소 수정(F 영역 `scripts/ontology_v2.py`): 그래프 읽기를 `read_rows(ses)` 로 꺼냄 — 같은 읽기를 커밋 전 검사에 쓰려는 것(질의 두 벌 방지). 동작 변화 없음.
- 검증됨(단위): `tests/test_capstone_t2_load_graph.py` 31개. 뮤테이션 15개(ns 강제 · 접두어 강제 · 덮어쓰기 · 다리 끝 ns/존재 · 쓰기 전 검사 · 빈 되돌리기 · 질문 $ns · 0행 · 중복 id · 남은 접두어 · 양 끝 밖 관계 · 레이블 낱말 · 예전 적재분 알림) — 14개 잡힘, M8(지우는 문장이 ns 를 안 가림)은 살아남음: 가짜 트랜잭션이 문장을 이름으로만 알아보기 때문. 문장 글자 고정 시험을 더해 다시 → 잡힘. 문장의 뜻은 2절 라이브에서 실측.

## 2. 라이브 — T2 적재 · `validate --extra` · 질문 · 지식 지도 (잠금 18:26~)
잠금: `.evidence/LIVE_LOCK` 에 한 줄 쓰고 시작. 시작 전 그래프(전체판 볼륨 `hyd-iot-edu_neo4j-data`): 노드 965(이름 공간 0) · 관계 2348.
증거 `.evidence/k-capstone/t2/01-load-ask.log` · `02-base-validate-with-student.log` · `03-base-validate-after-fix.log`, `map/`.
- 검증됨: 적재 전 `validate --extra` · `wipe` · `ask` 는 모두 FAIL(0개 노드 / 되돌릴 것 없음 / 9문항 0행). `load` → "노드 65 · 관계 107 적재, 수업 기준 노드 965 그대로", 그래프 1030 · 2455. 다시 `load` → 같은 수(멱등).
- 검증됨: `python scripts/ontology_v2.py validate --uri bolt://127.0.0.1:7687 --extra students/_template/example_meeting/schema.json` → "checked 65 nodes, 107 relationships … PASS"(review-scripts-kit 7절의 미검증 항목).
- 검증됨: `ask` 9문항 모두 답함(예: "미결 이슈는 몇 건인가" → open_issues 3, "4인실에서 고객 회의" → room_capacity < 6 EXCLUDE · 읽는 자리 room.capacity).
- **발견(결함) — 학생 지식을 적재하면 수업 기준 검사가 깨진다.** 적재 뒤 `ontology_v2.py validate`(--extra 없음)가 FAIL 124건, 124건 모두 demo 노드(스키마에 없는 레이블 Attendee … · 속성 ns · 학생 관계). 적재 전 같은 그래프는 위반 0. 설계 3.3 이 안 다를 고른 이유("반 전체 validate 가 학생마다 흔들리지 않게")와 반대 동작.
  - 조치 `scripts/ontology_v2.py` `base_scope` + `cmd_validate`: 수업 기준 검사는 이름 공간 없는 노드와 그 노드끼리의 관계만 본다. 뺀 것은 이름 공간별 개수로 한 줄 알린다("namespace 'demo': 65 nodes skipped here — checked by validate --extra …") — 조용히 빼지 않는다. 학생 노드 검사는 `--extra` 몫(변화 없음).
  - 검증됨(라이브): 고친 뒤 같은 그래프에서 "checked 965 nodes, 2348 relationships … PASS" + 건너뜀 한 줄. 단위 시험 `test_the_base_check_skips_student_nodes_and_says_how_many`, 뮤테이션 3개(다리 관계 남김 · 학생 노드 남김 · 건너뛴 수 안 셈) 모두 잡힘.
- 검증됨(지식 지도, review-scripts-kit 7절 미검증 항목): `GET :8091/api/ontology/namespaces` → `[{"ns":"demo","nodes":65}]`, `…/graph?asset=HYD-01&ns=demo` → 노드 65 · 관계 107(전부 ns demo), 기본 보기는 487 · 970 그대로(학생 노드 0). 브라우저(playwright 1440): 이름 공간 고르기에 "demo · 항목 65개", 고르면 "항목 65 · 연결 107 · 규칙 6 · 성과 지표 3", 층 칩에 "내 업무 개념", 콘솔 오류 0 — `map/map-1-base.png` · `map-2-ns-demo.png` · `map-2-ns-demo-text.txt`.
  - U 에 넘길 것(결함 아님 · 기존 동작): 규칙 카드가 `demo:rule:after-due` 처럼 id 로 보인다. 수업 기준 규칙도 같다(`rule:dx-cooler` — Rule 에 name 속성이 없어 id 가 이름 자리에 온다). 화면에 내부 id 를 내지 않는다는 원칙과 어긋남.
  - 미검증: 지도에서 항목을 눌렀을 때의 상세(자동 클릭이 "보이지 않는 요소"로 실패 — 지도 안 가로 스크롤 밖). 손으로는 확인하지 않았다.
- 조치(작은 것): `load_graph.py` 가 Neo4j 드라이버 알림(없는 레이블 · 속성 경고 수십 줄)을 끈다 — 빈 이름 공간에 질문을 돌리면 경고가 결과를 덮었다. 틀린 이름은 검사 위반이나 0행으로 드러난다.

## 3. 라이브 — T3 DDL · T4 서버 · 포털 MCP 등록 (review-scripts-kit 7절 · cap-kit 4절의 미검증 항목)
증거 `.evidence/k-capstone/t3/01-ddl.log`, `t4/api.jsonl` · `server.log`. 읽기 계정 암호는 스크래치에만 두고(증거 · 기록에서 가림) 끝에 계정째 지웠다.
- 검증됨(T3): `example_meeting/table.sql`(암호만 바꿈)을 Supabase(54322)에 실행 → 스키마 `stu_demo` · 표 3개(요청 1 · 참석자 6 · 회의실 3행) · 계정 `stu_demo_reader`(super · createrole · createdb · bypassrls 모두 f, `default_transaction_read_only=on`). 다시 실행해도 INSERT 0(멱등).
  읽기 계정으로: 조회 됨 / INSERT → "cannot execute INSERT in a read-only transaction" / `begin read write` 로 우겨도 "permission denied for table room" / `ent.work_orders` → "permission denied for schema ent" / CREATE TABLE 거절.
  나중에 postgres 로 표 2개를 더 만들었을 때 읽기 계정이 새 grant 없이 읽었다(`alter default privileges` 가 실제로 먹음 — `t3/02-calendar-standin.log`).
- 검증됨(T4): 환경 변수 없이 → 무엇이 빠졌는지 말하고 종료, `change-me` 암호 → 거절. 실제 암호로 기동 → `/healthz` `{"ok":true,"schema":"stu_demo","session_read_only":"on"}`.
- 검증됨(포털 등록): `POST /api/mcp/check`(등록 전 검사) ok · 도구 3개 모두 read_only. 틀린 포트로 등록 → 422 "연결 거부 — host.docker.internal:8312 …". 맞는 주소로 등록 → 201, `gate.read_tools = [list_tables, describe_table, read_rows]`, 막힌 도구 0.
  포털 "써 보기"(`POST /api/mcp/servers/my-biz/tools/read_rows/call`) → 필수 참석자 2행. 없는 칸 `nope; drop` → INVALID 봉투.

## 4. 라이브 — 역할 · 스킬 · 에이전트 · 질문하기, **G9 확인**
증거 `agent/api.jsonl`, `ask/*.json`, `g9/*.log` · `g9/student-agent-CLAUDE.md`, 워커 로그 `worker/worker.log`, 작업 폴더 `worker/workspace/`.
- 검증됨(G10 역할): `POST /api/roles`(회의 주관자, 키 demo-organizer) 201 → 구성원 `user:lee-prod` 추가 201 → 흐름 가져오기에서 레인 "회의 주관자"가 이 역할에 자동으로 이어짐.
- **막히는 곳 ①(예시 그대로는 에이전트가 안 만들어진다)**: 키트 `agent.json` 그대로(`tools: neo4j · my-biz · gdrive · gcal`) → 422 "등록되지 않은 도구 서버입니다: gdrive, gcal". 구글 서버 등록(사용자 몫) 전에는 도구를 `neo4j · my-biz` 로 줄여야 만들어진다. 분류: 의도된 동작(지어낸 서버를 받지 않음). 줄여서 만듦 → `agent:u-a6f0174f`, 업무 규칙 null.
- 결함(F 영역 최소 수정, 커밋 74ac76c): 호스트 워커가 학생 MCP 를 못 찾는다. T4 가 안내하는 등록 주소 `http://host.docker.internal:8311/mcp` 는 process 컨테이너가 닿는 이름이고, macOS 호스트에서는 풀리지 않는다(`ping host.docker.internal` → Unknown host). 연결 검사 · 시스템 task 는 되는데 에이전트만 그 도구를 못 쓰는 모양(G2⓪과 같은 종류).
  조치 `scripts/run_worker_host.sh` 의 `MCP_HOST_REWRITE` 기본에 `host.docker.internal=127.0.0.1`. 검증됨(라이브): 작업 폴더 `.mcp.json` 의 my-biz 주소가 `http://127.0.0.1:8311/mcp` 로 쓰이고 에이전트가 `my-biz/read_rows` 를 9번 불렀다.
- 검증됨(단계 6 질문하기 · T4 에이전트 호출): 학생 에이전트에게 "필수 참석자는 누구인가, 4인실 room-a 에서 해도 되는가" → 45초, 도구 호출 13(my-biz list_tables · describe_table×3 · read_rows×3, neo4j 스키마 · 규칙 질의), 답 = 필수 2명(김주관 · 박임원) + "room-a 좌석 4 < 6 → 제외(D1 §4 원문 인용)", 캘린더는 "확인 못 함"이라고 적음.
- **G9 검증됨**(cap-g3g9 6절 절차 1~3):
  1. `select id, work_rules from users where is_agent` → 기준 넷(sys:agent · agent:cooling · agent:pm-plan · agent:spare-buy) `hyd-plant`, 학생 에이전트 null(`g9/01-db-work-rules.log`).
  2. 기준 에이전트: 작업 폴더 `CLAUDE.md` 를 `tests/fixtures/constitution_hyd_2fbefff.md` 와 `cmp` → 같음(3936바이트), "업무 규칙이 붙어 있지 않아" 알림 없음. **절차와 다른 점**: A 시나리오 완주 대신 "에이전트에게 질문하기"로 sys:agent 를 한 번 돌렸다(같은 워커 경로 · 같은 작업 폴더 준비. A 완주는 구조판 볼륨 · c3 흐름 배포가 필요해 이번 잠금 범위에 넣지 않음).
  3. 학생 에이전트: `CLAUDE.md` 2453바이트, HYD · Neo4j · enterprise · hyd-dmn · PLC · 설비 · describe_schema 모두 0회, `task.json` 의 `work_rules: null`, 처리 건 보기와 단계 상세에 알림 한 줄("이 에이전트에는 업무 규칙이 붙어 있지 않아 공통 규칙만 넣었습니다 …").
- 관찰(결함 후보 · F 에 넘김, 고치지 않음): **호스트 워커의 Claude Code 가 강사 개인 claude.ai 연결 도구를 에이전트에게 보인다.** 학생 에이전트가 `mcp__claude_ai_Google_Drive__search_files` 를 6번 불렀다(검색어 "fullText contains '가온상사'" 등). 모두 "Claude requested permissions … haven't granted it yet" 로 거절돼 읽은 것은 없다(`worker/workspace/hyd/9b597814…/run-*.events.jsonl`). 허용 목록(`--allowedTools`)이 막았지만, 등록하지 않은 개인 도구가 목록에 보이는 것 자체가 "에이전트는 등록한 MCP 의 읽기 도구만"과 어긋난다. 워커 실행 인자(`it/agent-worker/worker/runner.py:187-194`)에 등록 서버만 싣는 길(`--strict-mcp-config`)이 있는지는 F 가 회귀와 함께 판단.
- 관찰: 학생 에이전트 작업 폴더의 `context/schema_prompt.md` 는 v2 스키마만 담는다(학생 클래스 Meeting 등은 없음). 에이전트는 `get_neo4j_schema` 로 알아냈다. 학생 스키마를 프롬프트에 싣는 것은 하지 않음(설계에 없음).

## 5. 라이브 — 흐름 가져오기, **막히는 곳**, G1 · G3 확인
증거 `flow/api.jsonl` · `mapping-*.json` · `flows-mapping.png` · `flows-mapping-rows.json`, `bpmn/`, `run1/` ~ `run4/`.
### 5.1 예시 흐름을 키트 그대로 가져오면
- 검증됨: `flow.bpmn` + `mapping.json`(에이전트 id 만 채움) → 사전 검사 거절 **3줄**(일정 만들기 결과 경로 자리 · 일정 읽기 결과 경로 자리 · 그 값을 쓰는 분기 조건), 등록 400. README · 시험 기대값과 같다.
- **발견(키트 결함) — 그 3줄을 채워도 네 번째 거절이 나온다.** 경로 자리를 임의 경로로 채워 검사 → "'주관자 승인'의 반려(또는 조건 없는) 경로로 MCP 쓰기(메일) 부품에 닿습니다 …". 사람 승인(안 고르기)은 반려도 내는데 T7 · T8 그림에는 승인 뒤 분기가 없었다(cap-g1g7 9절의 검사가 cap-kit 그림보다 나중에 들어옴). 강사가 구글 서버를 고르고 경로를 채워도 등록이 안 됐을 것.
  - 조치(커밋 b13dfed): T7 `flow.bpmn` · T8 `example_meeting/flow.bpmn` 에 "승인?" 분기 · 반려 보고 · 끝(반려) 추가(DI 포함), `mapping.json` 에 `Flow_approve_yes: approval == '승인'` · 반려 보고 부품, README.
  - 검증됨: `tests/test_capstone_kit.py` 16개(경로만 채우면 통과 · 승인 조건을 빼면 거절). 뮤테이션: 두 그림을 고치기 전으로 되돌리면 각각 2개 실패. bpmn.io 의 그리기 라이브러리(bpmn-js 17.11.1, process-gpt node_modules 를 읽기만)로 열어 경고 0 · T7 도형 17 선 12 · T8 도형 21 선 15, 일부러 끊은 선은 "unresolved reference" 경고로 잡힘 — `bpmn/t7-blank.png` · `t8-example.png` · `open.log`(cap-kit 4절 "bpmn.io 화면" 미검증 항목: 같은 라이브러리로 그려 확인. demo.bpmn.io 사이트에 올려 보지는 않았다).
- 관찰: 사전 검사는 등록되지 않은 MCP 서버 이름(`gcal`)을 거르지 않는다(cap-g3g9 5절 ①에 적힌 대로 실행 때 판정). 실행 때 "config" 실패로 멈춘다.
### 5.2 **막히는 곳 ②(가장 큼) — 포털 화면에는 시스템 부품의 설정 칸이 없다**
- 발견: 흐름 가져오기 매핑 화면(`it/portal/www/flows.js` `taskRow` 180~206행)에서 설정을 넣을 수 있는 부품은 에이전트 · 사람 · 사람 승인뿐이다. `승인 뒤 MCP 호출`(server · tool · arguments · extract · effect) · `시간 대기`(duration) · `결과 보고`(outcome · title · summary) 행은 입력 칸이 0개다(`flow/flows-mapping-rows.json` — 브라우저에서 읽은 행별 입력 목록). 학생이 포털에서 이 부품을 고르면 사전 검사가 설정이 없다고 거절하는데 화면에서 고칠 자리가 없다.
- 분류: 결함(설계 2절 단계 8 "포털로 가져와 묶기"를 포털만으로 끝낼 수 없다). 지금 되는 길은 매핑 JSON 을 API(`PUT /api/flows/{id}/mapping`)로 넣는 것뿐 — 이번 확인도 그렇게 했다.
- 조치: 하지 않음. U 영역(`flows.js`)이고, 칸 모양(서버 · 도구 고르기, 인자 줄, 꺼낼 값 줄, 읽기 확인 체크)은 참고 화면(process-gpt `ServiceTaskPanel.vue`)을 보고 정할 화면 설계다. JSON 글상자 하나로 때우지 않았다. → "U 에 넘길 것" 1번.
- 검증됨(G1 의 미검증 항목): 사람 승인 부품의 설정 칸 5개(options · key · recommended · losers · docs)는 화면에 그려지고 저장된 값이 들어 있다. 콘솔 오류 0.
### 5.3 한 건 돌리기 — 다섯 번 (확인용 매핑: 구글 자리를 수업 메일함 · 내 업무 표로 바꾼 대역)
구글 계정 없이 G1 · G3 를 확인하려고 예시 매핑의 두 칸만 바꿨다(`flow/mapping-live-standin*.json`): 일정 등록 = `hyd-effects.send_mail`(수업 메일함), 응답 확인 = `my-biz.read_rows`(effect:false, `document.rows.0.required` 를 Boolean 으로 꺼냄 — 참석 응답의 **대역**이지 실제 수락 여부가 아니다). 키트에는 넣지 않았다.
| 회 | 무엇 | 결과 | 증거 |
|---|---|---|---|
| 1 | 판본 1, 캘린더 대역 없음 | **막히는 곳 ③** 에이전트가 "캘린더 빈 시간을 조회하지 못해 후보를 낼 수 없습니다"로 보류(PENDING). 지어내지 않음. 포털 '단계 닫기' → 단계는 CANCELLED 인데 처리 건은 RUNNING 으로 남음(아래 결함) | `run1/` |
| 2 | 판본 2, 캘린더 대역 표 2개(`t3/02-calendar-standin.sql`, 가상 값)를 지시문으로 안내 | 제안은 나왔으나 같은 시각에 회의실만 다른 안 둘 → 승인 카드 "‘slot’ 값 … 이(가) 두 번 있습니다", 승인 단추 꺼짐, 서버도 400. 다른 사람 승인 403 · 구성원 아님 403 · `/submit` 우회 403 · 사유 없는 반려 400(화면에 문구). 사유 적고 반려(화면) → 반려 보고 → 끝(반려), 메일 0통 | `run2/` |
| 3 | 판본 3(요령에 구분 값 규칙) | 포털 [직접 시작] → 제안(61초) → 승인 패널에서 **추천이 아닌 안**을 골라 승인(화면) → 메일 본문에 고른 안("일시 2026-10-20T06:00:00Z · 회의실 room-c") → `event_id` 꺼냄 → 대기 72초(P1D ÷ 20 ÷ 60) → 읽기 확인 → `all_required_accepted = true` → 확정 | `run3/`(처리 기록 캡처 1440 · 390 포함) |
| 4 | 판본 3, 승인을 미룸 | 12분(PT4H ÷ 20) 뒤 "승인 지연" 보고, 그동안 메일 0통 · 승인 값 없음. 그 뒤 승인 → 읽기 확인 false → 미확정 | `run4/` |
| 5 | 판본 4: 확인 단계를 쓰기 도구(send_mail)로 두고 effect:false | 3회 모두 "서버가 이 도구를 쓰기 도구(readOnlyHint=false)로 표시했습니다"로 거절 → PENDING. 그 주소로 간 메일 0통. 실패한 시도의 도구 호출 사건 6건(attempt_failed) · 감사 MCP_READ_FAILED 3건이 남음 | `run5/` |
- **G1 검증됨**(cap-g1g7 7절 1~4): 승인 패널 · 설정 칸 · 다른 안 고르기 · 고른 안이 MCP 인자로 · 403/400 · 반려 가지 · 약속 어긴 제안의 카드. 추천안 그대로 승인은 4회에서 API 로 했다(화면 단추로는 다른 안 승인 · 반려만 눌렀다).
- **G3 검증됨**(cap-g3g9 6절 4): effect:false + extract(Text · Boolean) → 분기 두 가지, 쓰기 도구는 거절. 처리 기록 화면에 "MCP 결과에서 값을 꺼냄" 줄이 보인다. cap-g3g9 7 · 7.1 의 "라이브(Pg) 미검증"(실패 시도 사건 · 감사 보존)도 5회에서 확인.
- 결함(F 영역, 커밋 74ac76c) `it/process/procsvc/instances.py` `close_agent_task`: 열린 일 판정에 TODO 를 넣어, 엔진이 미리 만든 "아직 닿지 않은 단계" 행 때문에 단계가 여럿인 흐름은 닫아도 끝나지 않았다. 엔진과 같은 기준(IN_PROGRESS · SUBMITTED · PENDING + 예정 대기)으로 고치고, 끝낼 때 닿지 않은 단계 행도 CANCELLED. 시험 2개 추가(`tests/test_close_agent_task.py`), 뮤테이션 3개 모두 잡힘. **라이브 미검증** — process 이미지를 다시 빌드해야 하는데 권한 확인에서 거절돼 하지 않았다(스택의 process 는 고치기 전 코드 그대로).
- 키트 수정(커밋 4bb70e4): T6 · T8 `SKILL.md` 에 "slot 은 안마다 달라야 한다 · docs.link 는 http(s)만". 2회의 link 위반은 내가 확인용 지시문에 "원문 위치를 link 에 적어라"고 쓴 탓(3회에서 뺌).
- 관찰(고치지 않음): ① 시스템 task 가 PENDING 으로 멈춘 학생 처리 건(5회)을 닫는 길이 없다 — '단계 닫기'는 에이전트 작업만 받는다. ② 학생 흐름 하나만 지우는 길이 없다 — '기준으로 되돌리기'는 학생 흐름 전부(c3_* 포함)를 지운다. ③ 정의를 지워도 실행 그래프의 정의 투영(ProcessVersion · FlowNode)은 남는다. ④ 구성 내보내기는 학생 것 전부를 한 묶음으로 낸다(내 것 1 + c3 흐름 3).

## 6. G8 · 내보내기 · T2 보완
- 검증됨(G8, review-scripts-kit 7절 미검증 항목): `project_student_flow.py` 로 등록한 판본 3을 demo 에 투영 → 흐름 노드 16 · 수행자 관계 9, 다시 돌려도 같은 수, `validate --extra` PASS(83노드 · 148관계) — `g8/01-project.log`. 투영 Process 는 `demo:proc:<흐름 id>` 라 graph.json 의 `demo:proc:qbr-prep` 와 다른 노드가 됐다 → README 에 "흐름 id 를 qbr-prep 로" 적음.
- 검증됨(단계 10 내보내기만): `GET /api/config/export` 에 my-biz · qbr-prep · 에이전트 · 역할 구성원 · 흐름이 담기고 읽기 계정 암호는 없음. 되돌리기 → 가져오기로 같은 상태가 되는지는 **미검증**.
- T2 보완(커밋 1f35b48): 적재 중 그래프의 수업 기준 노드 수가 965 → 1094 로 늘었다(처리 건 투영). 전체 수 대조는 학생이 흐름을 돌리는 중에 적재하면 거짓 실패를 낸다 → 다리 끝 노드가 그대로인지 · 지운 수 = 내 노드 수로 바꿈. 시험 33개, 뮤테이션 17개 모두 잡힘. 라이브에서 다시 load · wipe 확인.

## 7. 복원 (잠금 18:26 ~ 19:26)
증거 `restore/`. 워커 멈춤(8097 듣는 것 0) → 멈춘 처리 건 2건은 `scripts/cleanup_residue_instances.py`(dry-run 으로 내 2건뿐임을 본 뒤 --apply) → `POST /api/flows/deploy-reset`(배포 상태가 시작 전과 같음) → 내 흐름 k_qbr_prep 만 지움(`restore/remove-my-flow.sql` — 포털 되돌리기와 같은 문장을 이 흐름 id 로 좁힘, 지우기 전 행 백업) → 에이전트 · 스킬 · 역할 · MCP 는 포털 API 로 삭제 → 내 질문 2건 숨김 → T4 서버 멈춤 → `drop schema stu_demo cascade; drop role stu_demo_reader`(T3 머리말 문장 그대로 됨) → T2 `wipe`(흐름 노드 16 · 그 밖 67 삭제, 다시 하면 FAIL) → 내 흐름의 정의 투영 68노드 삭제(백업 있음) → 내 메일 3통 삭제 → 잠금 지움.
- 시작 전 스냅숏(`before/`)과 끝난 뒤(`after/`) 비교: MCP 서버 · 흐름 · 배포 · 에이전트 · 사용자 · 작업함 사용자 · 배정 · 스킬 · 비밀 값 9개 모두 같음. 그래프 965 → 972 노드(차이 7 = 내 처리 건 7개의 삭제 표지 ExecutionProjection, 제품이 일부러 남기는 것) · 관계 2348 그대로 · 이름 공간 0. process 컨테이너 재시작 0 · 이미지 그대로. B · C 표시 켜짐 · RUNNING 0.
- 손으로 한 것(API 가 없어서): 흐름 행 삭제 SQL, 질문 2건 숨김, 정의 투영 삭제. 증상을 가리려는 것이 아니라 내가 만든 시험 잔재 정리이고, 문장과 백업을 증거에 남겼다.

## 8. 전체 시험
`.venv/bin/python -m pytest -q -p no:cacheprovider` → **2113 통과 · 9 건너뜀 · 0 실패**(206초, 이 갈래 끝 상태).

## 9. 하지 않은 것 · 미검증
- G6(학생 것 격리): 구현하지 않음. 꼬리표를 누가 어디서 붙이는지 · 값 모양 · 기존 c3 흐름을 어떻게 볼지가 설계 5.2 에 없다. 마이그레이션 053 은 쓰지 않았다.
- 구글 드라이브 · 캘린더 연결과 그 서버로 하는 예시 완주(사용자 인증 몫).
- `close_agent_task` 수정의 라이브 확인(process 재빌드 필요).
- 지식 지도에서 학생 항목을 눌렀을 때의 상세, demo.bpmn.io 사이트에 직접 올려 보기, 구성 가져오기, A 시나리오 완주로 하는 G9 확인(질문하기로 대신함).

## 10. U 에 넘길 것 (화면 — 고치지 않음)
1. 흐름 가져오기 매핑 화면에 시스템 부품(승인 뒤 MCP 호출 · 시간 대기 · 결과 보고) 설정 칸이 없다(`flows.js` taskRow) — 5.2. **이것이 풀려야 학생이 포털만으로 끝까지 간다.**
2. 학생이 만든 역할이 승인 패널 머리 칩 · 역할 고르기 · 결과 보고에 `role:demo-organizer`(또는 "역할 demo organizer")로 보인다.
3. 처리 기록: 시작 문장이 흐름 이름이 아니라 id("‘k qbr prep’ 처리 건이 시작됐습니다"), 시작 값 · 승인 값이 값 이름 그대로("request id", "approval 승인"), 승인 단계에 고른 안이 안 보임(결과 보고에만), 그래프 도구 결과의 한글이 `\uXXXX` 로 보임.
4. 흐름 시작 조건 칸에 `SPARE_BELOW_MIN` · `PM_DUE` 가 그대로 보인다. 지식 지도 규칙 카드가 id 로 보인다(수업 기준 규칙도 같음).

## 11. F 에 넘길 것
- 호스트 워커가 강사 개인 claude.ai 연결 도구를 에이전트에게 보인다(4절, 거절은 됨).
- 시스템 task PENDING 처리 건을 닫는 길 · 학생 흐름 하나만 지우는 길 · 정의 투영 정리(5.3 관찰).
- 이 갈래가 F 영역에서 고친 것: `scripts/ontology_v2.py`(read_rows · base_scope), `scripts/run_worker_host.sh`, `it/process/procsvc/instances.py`.

## 합칠 때 옮길 것 (맨 위 절 대신 여기)
- NOW 3.4: T2 완료, G1 · G3 · G9 라이브 확인 완료, 키트 미검증 가운데 T3 · T4 · 포털 등록 · 에이전트 호출 · `validate --extra` · G8 · 학생 지식 지도 · bpmn-js 열기 완료. 남는 것 = 9절.
- NOW 3.2 에 10절, 3.3 에 11절.
- 사용자 지시(10-10): 「캡스톤」 대신 「종합 랩(개인 시나리오)」이라고 부른다. 학생 · 강사에게 보이는 새 문구에 「캡스톤」을 쓰지 않는다(기존 파일 · 브랜치 이름은 그대로).
