# U1 — 처리 과정 실시간 · 블랙박스 0 (확정 TODO A1)

작성 2026-10-08 밤, worktree `agent-afc6344f92e6b85c2`. 범위: `TODO.md` 확정 TODO §0 원칙, §1 **A1** 행, §2 L12 · L20~L23 대응.
완료 기준(A1): 완료 · 진행 중 task 모두 다섯 칸, 진행 중 실시간, 영문 0.

## 1. 무엇이 생겼나 (수강생이 보는 것)

| 화면 | 들어가는 곳 | 보이는 것 |
|---|---|---|
| **지금 줄** | 처리 건 상세 머리글 아래 `#instNow` | `지금 <단계> — <누가> <무엇을 하는 중>`. 에이전트: `도구 지식 그래프 조회 호출 중` · `판단을 정리하는 중` · `AI 일꾼이 집어 가기를 기다리는 중`, 사람: `운전원 선택을 기다리는 중 · 3분 경과 · 기한까지 7분`, 시스템: `설비 응답을 기다리는 중` · `효과를 확인하는 중 · 재측정까지 32 s`. 끝난 건은 `끝 <종료 이벤트>`. 단계 이름을 누르면 흐름 탭 + 그 단계 패널. 1초마다 시계만 다시 그림 |
| **task 상세 패널** | 흐름도 task 노드 클릭 · 단계 행 클릭 · 지금 줄 · AI 일꾼 패널 · 주소 `#/instances/<처리 건>/task/<단계>` | ① 받은 입력(값 + 어느 단계에서 받았는지) ② 처리 과정(시작 · **에이전트 판단 메시지** · 도구 호출과 결과 · 시간 · **판단 근거** · 사람 질문/답 · 완료/실패, 진행 중이면 맨 아래 실시간 줄) ③ 판단 · 출력(**판단 근거 요지는 접지 않음** + 읽기 쉬운 표, 원문은 접기) ④ 다음 단계로 넘긴 값(넘김/대체됨/아직 + 받는 단계) ⑤ 진행 중이면 SSE 로 그 단계 이벤트만 즉시 반영 + 2.5 s 재조회 |
| 에이전트 단계 — 내장 판단(legacy) | 원인 진단 · 조치 후보 조회 · 규정 검토 · 조치 후보 정리 | 원인 표(원인 · 사전확률 · 점수 · 근거 조건 `유온 상승 추세 > 55 · 관측 58.2 · 가중치 3` 충족/미충족/미확인) + 점수 식, 선정 규칙별 후보, 제외 · 감점 · 경고 수, **카드 점수 구성**(순위 · 카드 · 점수 · 성과 지표 +6 · 예측 +2 · 경고 -0.5 · 판정) + 순위 규칙 · 점수 식 |
| 에이전트 단계 — 워커(Claude Code) | 같은 단계, `AGENT_BRIDGE=off` | 도구 호출 사이에 에이전트가 쓴 말("TS1 이 55 ℃ 를 넘었으니 쿨러 오염부터 확인합니다")이 타임라인과 ③ 판단 근거에, 최종 답변은 완료 줄의 접기에 |
| 사람 단계 | 조치 선택 · 책임자 확인 | 권고 · 고른 조치(**권고와 다름** 칩) · 사유 · 승인자(역할) · 대기 경과/기한 · 판단 결과 상태(승인 대기/반려/실행 완료) · 승인 전달, 받은 조치 카드 점수 구성 표, 기한 초과면 "책임자 확인 단계로 넘어갔습니다" |
| 시스템 단계 | 설비에 명령 · 효과 확인 · 정비 요청 | 보낸 명령(`팬 100 % · 부하 80 %`) · 명령 번호 · 설비 응답(실행함/거부함 · 인터록), 회복 기준(`유온 TS1 < 55 + 경보 해제`) · **재측정까지 남은 시간**(사건 이력의 `900 sim-s = 45 s` 에서 계산, `모의 15분 = 실제 45 s (20배속)`) · 경보 해제 · 회복 근거(`이상 완화 유온 TS1 50.0 < 55`) |
| 매뉴얼 추출 처리 건 | 원문 근거로 SOP 제안 | 원문 문서 `general.txt · 1쪽 · 11,926자`(원문 전문은 쏟지 않음) · 담당 구간 · 사람 검토 판정, 에이전트 판단 메시지 · 도구 호출, 추출 제안(절 · 절차 · 페이지 검토 · 주의 수 + 절차 표 + 주의 목록) |
| 지금 일하는 AI 일꾼 | 처리 건 탭 접기 `지금 일하는 AI 일꾼` | 일꾼 서비스 연결 · 실행 중 수 · 처리 · 폴링, 일꾼별 잡고 있는 단계, 일꾼을 기다리는 단계, `처리 과정 보기` → task 패널. 안 닿으면 사유 그대로 |
| 워커 콘솔 | `bash scripts/run_worker_host.sh` 터미널 | `[실행 시작] … · 모델 …`, `[판단] <처리 건> · <단계> · <에이전트가 쓴 말 120자>`, `[도구 시작] … · neo4j/read_neo4j_cypher · 입력 {…}`, `[도구 끝] … · 결과 … · 250 ms`, `[오류] …` |

## 2. 원본 대조 (process-gpt-vue3, `scratchpad/refs-A/process-gpt-vue3/src`)

| 원본 | 파일:줄 | HYD | 차이 · 판정 |
|---|---|---|---|
| 흐름도 완료 노드 → 단계 산출물 드로어 | `components/BpmnUengineViewer.vue:1002` (`openFeedbackPanel`), `components/apps/todolist/InstanceProgress.vue:17-44` | `flow.js` task `<g data-node>` + `taskDetail.js` 클릭 위임 | 원본은 완료 노드 더블클릭만, HYD 는 모든 task 노드 한 번 클릭(아직 시작 안 한 단계는 정의의 읽을 값 · 만들 값). 차이 있음, 유지(수강생 동선이 짧다) |
| 업무 상세 탭(진행 · 에이전트 모니터) | `components/apps/todolist/WorkItem.vue:974-1011` | 한 패널 안 다섯 칸(접기 섹션) | 탭 대신 섹션 — "판단 결과 · 근거 요지는 접지 않음" 원칙 때문에 ③을 기본 펼침. 차이 있음, 유지 |
| 입력 데이터 | `components/apps/todolist/FormWorkItem.vue:54` (`ActivityInputData`) | ① 받은 입력 + 출처(`input_sources` · `variable_sources`) | HYD 는 값마다 "어느 단계에서 받음"까지. 결함 아님 |
| 그 단계 이벤트 실시간 구독 | `views/markdown/AgentMonitor.vue:857-871` (`task_working` · `tool_usage_*` · `human_asked`, `todo_id` 로 거름) | `liveStream.js` → `hydTaskDetail.onEvent` (todo_id) | 같은 방식. 원본 Supabase realtime, HYD process SSE `/api/events/stream` |
| 업무 하나 = 메시지 하나, 끝났나 | `components/apps/todolist/InstanceTimeline.vue:377,726-727` (`todo_id`, `isAgentFinished`) | ② 처리 과정 타임라인 | 같음 |
| 전역 일꾼 현황 | 없음(단계별 대기 표시 `AgentMonitor.vue`) | `agentsPanel.js` (`/api/agents/status` + 임대 중 행) | 회의 L434 "어떤 에이전트가 지금 동작" 요구 — HYD 추가 |
| 에이전트 문장 | 원본 cli-agent 는 텍스트를 화면 스트림으로만(HYD `worker/events.py` `row_of` 주석: text · thinking · plan · agent_log 는 stream-only) | `NoteBuffer` 가 문단 하나를 `task_working{type:text}` 행 하나로 저장(1,500자) | 저장하지 않으면 새로고침 · 끝난 단계에서 "왜"가 사라짐 → 블랙박스 0 요구를 못 채움(②). 반영 |

## 3. 바꾼 파일

| 파일 | 무엇 |
|---|---|
| `it/portal/www/taskDetail.js` (새) | task 상세 패널 · 지금 줄 · 해시 진입. 판단 근거(내장 판단 evidence · 워커 판단 메시지), 원인 점수 · 조건 표(`causesTable`), 카드 점수 구성(`cardsTable`, `/api/decisions/{id}`), 사람 단계(`selectHtml`, 대기 경과 · 권고와 다름), 시스템 단계(`/api/incidents/{id}` → 명령 · 응답 · `reobsWindow` 재측정 · 회복 근거), 매뉴얼 추출(`manual_source` · `segment` · `review_feedback` · `proposal`), 변수 이름표(정의 설명의 `dec:…` 대신) |
| `it/portal/www/taskDetail.css` (새) | 선택 하이라이트 · 패널 · 지금 줄 · 판단 근거 상자 · 조건/점수 구성 칸 |
| `it/portal/www/agentsPanel.js` (새) | 지금 일하는 AI 일꾼 |
| `it/portal/www/flow.js` | task 노드에 `data-node` 1줄 |
| `it/portal/www/instances.js` | 단계 행 `data-step-task`, 흐름 탭 패널 자리, 머리글 `#instNow`, `hydTaskDetail.mount` 호출 (3줄) |
| `it/portal/www/liveStream.js` | SSE 이벤트를 패널에 넘김, `task_working` 의 판단 메시지 · 판단 근거 · 알림 제목을 한국어로(전에는 `notice` · `text` 가 영문 그대로) |
| `it/portal/www/index.html` | css · js 2줄, AI 일꾼 접기 1줄 |
| `it/agent-worker/worker/events.py` | `ConsoleLog`(도구 한 줄 로그 + `[판단]`), `NoteBuffer`(텍스트 델타 → 문단 행, 최종 답변 중복 제거), `NOTE_BOUNDARY` |
| `it/agent-worker/worker/runner.py` | `_stream` 에서 판단 메시지를 도구 호출 앞에 기록 · 콘솔 출력, 스트림 끝에 남은 말 기록 |
| `it/process/procsvc/instance_mode.py` | `_legacy_evidence` — 내장 판단 4단계마다 `task_working{type:evidence}` 1행(원인 점수 · 통과 근거 수, 선정 규칙, 제외 · 감점 · 경고 수, 카드 점수 구성 · 순위 규칙 식). 값은 결정 · 가이드 카드에서 그대로 복사, 다시 계산하지 않음 |
| `tests/test_u1_task_detail.py` (새) | 아래 시험 10개 |
| `tests/js/render_task_detail.js` (새) | 실제 `ui.js` · `names.json` · `taskDetail.js`(+ `app.js` 의 패턴 이름 줄, `enterprise.js` 의 조치 이름 줄)를 node vm 에 올려 렌더 |

정답 · 과제 표시 없음: 패널은 결정 · 사건 · 이벤트에 있는 값만 그린다(수강생이 랩업에서 만든 에이전트의 판단 메시지 · 도구 호출도 같은 칸에 나옴).

## 4. 시험 결과

- 전체: `/home/user/hyd-iot-edu/.venv/bin/python -m pytest -q` → **1294 passed** (155 s).
- JS: `node --check it/portal/www/*.js tests/js/render_task_detail.js` 전부 통과.
- U1 시험(`tests/test_u1_task_detail.py`, 10개):
  1. 단계 view 가 입력 · 출처 · 그 단계 이벤트 · 출력을 준다(새 API 없음).
  2. 콘솔 한 줄 로그(도구 시작/끝 · ms · 실행 시작 · 오류, 생각은 안 찍음).
  3. 러너가 도구 호출을 콘솔에 찍는다.
  4. `NoteBuffer`: 델타 → 문단 하나, 1,500자 자름, 공백만이면 없음, 최종 답변은 잘라 냄.
  5. 러너: 판단 메시지 2문단이 저장되고 첫 문단이 도구 호출 **앞**, 최종 답변은 `task_completed` 에만, 콘솔 `[판단]`.
  6. 내장 판단 다리: 4단계마다 evidence 1행, 원인 점수 · 통과 근거, 선정 규칙, 경고 수, 카드 점수 구성 · 순위 식, 순서 시작 < 근거 < 완료.
  7. 영문 검출기 자체 시험(일부러 넣은 `cause:made-up-cause` · `IN_PROGRESS` · `FAN_SET` · `legacy agent` · `READY` · `work_order` · `[object Object]` 를 잡고, 원문 접기 · 점수 식 코드는 통과).
  8. 실제 런타임(쿨러 경보 → 내장 판단 → 사람 선택 → 명령 → ACK → 효과 확인 → 종결)의 스냅숏 9개를 실제 `taskDetail.js` 로 렌더: 모든 장면에 네 칸 제목, 영문 0(패널 · 지금 줄), 주소 진입(`#/instances/<id>/task/<id>` → 흐름 탭 + 그 단계), 원인 표 숫자, 카드 점수 구성, 사람 대기 · 권고, 보낸 명령 `팬 100 % 부하 80 %`, `재측정까지` · `모의 15분 0초 = 실제 45.0 s (20배속)`, 회복 근거 `유온 TS1 50.0 < 55`, 끝난 건 `끝`.
  9. E7 권고와 다른 선택(실제 `rt.select` 로 두 번째 카드) → `권고와 다름`, 사유 · 승인자 · `조치 종류 넘김 정비 요청`.
  10. 실제 워커 경로(Runner + 매뉴얼 추출 처리 건): 판단 메시지 · 도구 · 원문 요약(전문 미노출) · 절차 표 · 주의, 지금 줄 `결과 제출 · 다음 단계로 넘기는 중` → `끝`.
- **일부러 깨뜨림** (`.evidence/U1/mutations.log`, 각각 원복 후 10 passed):
  M1 워커 판단 메시지 기록 끔 → 2 실패 · M2 내장 판단 근거 이벤트 끔 → 2 실패 · M3 원인 점수 · 조건 표 끔 → 1 실패 · M4 이상 패턴 한국어 이름 끔 → 1 실패(영문 `COOLER_DEGRADATION`) · M5 재측정 · 회복 근거 끔 → 1 실패 · M6 권고와 다름 표시 끔 → 1 실패.
- 검토 중 발견해 고친 것(렌더 결과를 직접 읽음): 변수 이름에 정의 설명의 `dec:action-candidates` 가 노출, 권장 조치 `FAN_SET` 코드, `legacy agent`, `READY`, 조치 종류 `work_order`, 보낸 명령에 값 없음(`팬 · 부하`), 끝난 단계에서 시계 차이로 음수 소요 시간, 에이전트 최종 답변 `\uXXXX`, SSE 흐름에 `text` · `notice` 영문 제목.
- 렌더 결과 HTML: `U1_RENDER_DUMP=<폴더> pytest tests/test_u1_task_detail.py` → 장면별 `.html` (이번 실행 `.evidence/U1/render/`).

## 5. 확인하지 못한 것 (라이브 — 메인이 합친 뒤 한 번)

docker · compose 금지 범위라 라이브 확인은 하지 않았다. 합친 뒤 확인 경로:
1. 쿨러 경보 1건(20배속, `PROCESS_MODE=instance`, core 는 `AGENT_BRIDGE=legacy`) → 포털 `처리 건` → 그 건 → 머리글 `지금:` 줄이 단계마다 바뀌는지, `흐름` 탭에서 노드 클릭 → 원인 진단(원인 표) · 조치 후보 정리(카드 점수 구성) · 조치 선택(대기 경과 · 권고) · 설비에 명령(명령 · 응답) · 효과 확인(재측정까지 45 s 카운트다운 → 회복 근거).
2. 주소창 `http://<포털>/#/instances/<처리 건 id>/task/<단계 id>` 새로고침 → 같은 단계 패널.
3. 워커 경로(`AGENT_BRIDGE=off`, `bash scripts/run_worker_host.sh`) → 워커 터미널에 `[판단]` · `[도구 시작]` · `[도구 끝] … ms`, 포털 원인 진단 패널 타임라인에 `에이전트 판단` 줄이 도구 호출 앞에, `지금 일하는 AI 일꾼` 에 그 단계.
4. 지식 관리에서 매뉴얼 추출 1건 → 그 처리 건의 `원문 근거로 SOP 제안` 패널(원문 요약 · 추출 제안 표).
5. 권고와 다른 카드 선택 · 거부 · 10분(20배속 30 s) 기한 초과 각각에서 흐름도 하이라이트와 사람 단계 패널(권고와 다름 / 판단 결과 상태 반려 / 책임자 확인으로 넘어감).

알려진 한계: 시스템 단계 재측정 시간은 사건 이력의 `RE_OBSERVING` 기록에서 계산하므로, 연장(`REOBSERVATION_EXTENDED`, 1/3 창)이 일어나면 "재측정 시각 지남 · 판정 대기 · 연장 n회"로 보인다(연장 창의 남은 초는 감사 기록에만 있어 세지 않음). HANDOFF §9 는 다른 단위와의 충돌을 피해 이 worktree 에서 고치지 않았다(메인이 합칠 때 기록).
