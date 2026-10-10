# 캡스톤 갭 G1 · G7 — 일반 사람 승인 부품과 추천 카드 (2026-10-10)

브랜치 `cap-g1g7` (merge-preview 2fbefff에서 갈라짐). 설계 근거: 캡스톤 설계안 3.6 · 3.7 · 5.2 G1 · G7 행.

## 0. 시작
- 통독: 설계안 전문, 점검표, 공용 헌법, 프로젝트 CLAUDE.md.
- 참고 레포 확인: process-gpt `services/frontend/src/components/ui/HumanFeedbackPanel.vue` 99-131 · 422-429 — 승인 / 반려 단추 + 사유,
  응답 `answer: '승인' | '반려'`, `reason`. 이 모양을 그대로 따른다(폼 결과 `approval` = 승인 | 반려, `approval_reason`).
  다른 점: 제품은 에이전트 질문 응답(제출 경로 하나)이고, 여기는 승인 값(approved_*)을 서버만 넣는 별도 경로(/approve)다 —
  CLAUDE.md "사람 승인 1회 뒤 process 가 실행"과 보호 값 계약 때문(차이 있음, 유지).

## 1. G1 백엔드 (일반 사람 승인 부품)
- 새 순수 모듈 `it/process/procsvc/approval_part.py`: 부품 `human:approve` / tool `formHandler:approve` / 폼(승인·반려 고르기 + 사유) /
  설정 `options`(필수) · `key`(기본 slot) · `recommended` · `losers` · `docs` / 검사 `validate` · `validate_form` / 안 고르기 `choose`.
- `definition_registry.py`: `approved_option` 을 보호 값(PROTECTED_OUTPUTS)에, formHandler:approve 활동은 부품 검사 + 폼 고정 검사.
- `bpmn_import.py`: 일반 부품 목록에 추가, 매핑 → 활동(역할 해석은 `_human_role` 로 사람 task 와 공용), 부품마다 `server_values`
  (조치 선택 = 기존 값, 안 고르기 = approved_by · approved_role · approved_option), 효과 앞 승인 검사가 두 승인 부품을 모두 셈.
  쓰이지 않던 카탈로그 칸 `approval_values` 는 지움(포털 · 시험에서 읽는 곳 0 — grep).
- `instances.py` `approve` · `_approval_actor`: 승인자는 "나"(user:*) + 이 단계 담당 역할의 구성원(inbox.check_actor). 승인 → approved_* 넣기,
  반려 → 사유 필수 · approved_* 비우기, 이미 처리된 승인 · 안 없음 · 목록에 없는 안 · 결정 값 오류는 사유와 함께 거절.
- `instance_mode.py`: `POST /api/todolist/{id}/approve`, 일반 `/submit` 은 formHandler:approve 를 403 으로 막음.
- `inbox.py`: 작업함 항목 kind `approve`.
- 반려 결과 보고: `effect_parts.REPORT_OUTCOMES` 에 `반려 → info`(실행하지 않았다는 알림, 사건이 있으면 그대로). 결과 보고 facts 에
  approval · approval_reason · approved_option 을 싣는다(`service_parts._run_report`).

## 2. G1 검증 (검증됨 — 단위 · API 시험)
- 새 시험 `tests/test_capstone_g1_approve.py` 24건 통과: 가져오기(부품 · 폼 · 값 연결) · 효과 앞 승인 없음 거절 · 설정 오류 4종 · 등록 거절
  (폼 바꿈 · 입력 없음 · approved_option 주입) · 시작 값 주입 거절 · 승인 → MCP 인자에 고른 안 · 지는 안 고르기 · 반려(사유 필수, 바깥 호출 0,
  결과 보고 반려) · 권한 없음 3종 · 안 없음 / 목록 아님 / 구분 칸 없음 / 중복 / 목록에 없는 안 / 안 안 고름 · 이미 승인됨(승인 · 반려 둘 다) ·
  결정 값 오류 · 승인 기록 없는 효과 거절 · API(/submit 403, /approve 403 · 400 · 404 · 200 · 재승인 400).
- 관련 시험 파일 11개(bpmn_import · c2_execution(A · B · C select_card 흐름) · c2_parts · definition_registry · inbox · instance_mode ·
  instances · flow_deploy · c3_assembly · capstone_g10_roles + 새 파일): 204 passed, 1 skipped.
- 뮤테이션(한 번씩, 되돌림 확인): M1 역할 검사 제거 4 실패 · M2 승인으로 안 셈 2 실패 + 17 오류 · M3 /submit 우회 허용 1 · M4 반려 때 값 안 비움 1 ·
  M5 고른 안 무시 3 · M6 폼 고정 검사 제거 1 · M7 보호 값에서 뺌 2 · M8 이미 승인됨 검사 제거 1 — 모두 잡힘.

## 3. G7 포털 카드 (추천 1 + 지는 안 펼치기)
- `it/portal/www/approvalCard.js` `hydApprove.proposal(values, cfg)` · `proposalHtml(m, chosenId, opt)`: 기존 승인 카드 모양(ap-card · ap-head ·
  ap-title · ap-reasons · ap-evidence · 접힌 "다른 안 … 왜 졌나" · ap-lost) 재사용. 약속 = options[{slot, reason, score}] · recommended(key 값) ·
  losers[{slot, why}] · docs[{title, link}]. 벗어나면 "에이전트 제안이 칸 약속과 다릅니다" + 무엇이 다른지 목록 + 받은 값 JSON(펼침).
  http(s) 가 아닌 링크는 링크로 만들지 않는다.
- `instances.js` `renderApprovePanel` · `approveTask`: 승인 패널 = 카드 + 승인자 칸(내 작업함 "나") + [반려] [승인]. "나"가 없거나 안이 약속과
  달라 고를 수 없으면 승인 단추를 끄고 이유를 적는다. 다른 안 고르기 · 추천안으로 되돌리기.
- `taskDetail.js` `approveHtml`: 결정 · 고른 안(추천과 다르면 표시) · 사유 · 승인자(이 단계 APPROVAL_* 기록) + 받은 제안 카드(보기만).
- `inbox.js`: approve 항목에만 "승인 요청" 칩(select_card 항목 모양은 그대로).
- `flows.js`: 흐름 가져오기 매핑에 이 부품의 설정 칸 5개(options · key · recommended · losers · docs) — 없으면 학생이 화면에서 설정할 수 없었다.
- `index.html`: 바꾼 스크립트 5개 캐시 버전 `20261010-capg1g7`. `tests/js/render_task_detail.js` 가 approvalCard.js 도 올린다.

## 4. G7 검증
- 검증됨: `tests/test_capstone_g7_card.py` 2건 — 실제 런타임(G1 학생 흐름)의 view · 단계 상세를 node vm 으로 실제 ui.js · approvalCard.js ·
  taskDetail.js 에 넣어 그림. 승인 전(추천 · 이유 · 점수 · 다른 안 1 · 빠진 안 2와 이유 · 근거 링크) / 승인 뒤(바꾼 안 · 사유 · 승인자) /
  약속 위반 5종 문구 + JSON 노출 + javascript: 링크 안 만듦 / 안 자체가 없음. test_u1_task_detail 10건 함께 통과.
- 뮤테이션 5개 모두 잡힘: 위반 숨김 · reason 검사 제거 · 지는 안 안 그림 · 고른 안 무시 · 링크 검사 제거.
- node --check: approvalCard · instances · taskDetail · inbox · flows 통과.
- 미검증: instances.js 승인 패널 · flows.js 설정 칸은 DOM 이벤트가 있어 node 렌더 시험이 없다(문법 검사만). 라이브 브라우저 확인 필요(아래 절차).

## 5. 전체 스위트 (1회)
- 1980 passed, 4 skipped, 1 failed — `tests/test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint` (error_kind 'closed' ≠ 'not_mcp').
  분류: 이 변경과 무관(근거: mcp_check.py · 시험 파일 · conftest 가 2fbefff 와 같고 바꾼 모듈을 import 하지 않음, 단독 실행 통과 ·
  파일 단독 실행에서 재현 → 로컬 HTTP 시험 서버의 순서 · 시점 의존). 고치지 않음(범위 밖) — 담당 확인 필요.

## 6. 스스로 판정할 질문 (설계안 5.2 끝)
- ① 학생 흐름이 기준 흐름(A · B · C)의 판본 · 기본 에이전트 · 시드를 바꾸는가? → 아니오. select_card 경로 · 기준 정의 · 에이전트 코드 변경 0,
  test_c2_execution(A · B · C) 통과. 결과 보고 facts 에 칸 3개 추가 · 반려 outcome 추가는 기준 흐름 값이 없으면 실리지 않음.
- ② 승인 전에 바깥(구글)에 쓴 호출이 0건인가? → 시험에서 승인 전 · 반려 · 권한 없음 · 잘못된 안 모두 MCP 호출 0건 확인. 사전 검사가 효과 앞 승인을
  요구하고, 반려 가지로 잘못 이어도 실행 때 approved_by 가 비어 있어 거절된다(실행 이중 확인).
- ③ 확정 스키마 변경 줄 0 → 이 작업은 스키마 파일을 건드리지 않음.

## 7. 라이브 확인 절차 (미검증 — 다른 담당의 라이브 검증이 끝난 뒤)
1. process · portal 재배포 뒤 포털 강력 새로고침(캐시 버전 capg1g7 확인).
2. 업무분장에 역할 1개(예: 주관자) + 사람 1명. 설계안 3.6 모양 .bpmn 가져오기 → 승인 task 에 "사람 승인 (안 고르기)", options=proposal.options ·
   recommended · losers · docs 칸 입력, 분기 approval == 승인 / 그 밖 → 반려 보고. 사전 검사 0건 · 등록 · 배포.
3. 직접 시작 → 에이전트 task 가 proposal 을 낸 뒤 내 작업함 "승인 요청" → 카드(추천 · 지는 안 펼치기 · 자료 링크) 확인 → 다른 안 고르고 승인 →
   승인 뒤 MCP 호출 인자에 고른 안 값 · 결과 보고 확정.
4. 비해피: 다른 사람으로 승인(403 문구) · 반려 사유 없이 반려(400) · 반려 → 결과 보고(반려), 바깥 호출 0건 · 약속 어긴 proposal(카드에 위반 + JSON).

## 8. 후속 3 — test_mcp_check html 시험 흔들림 (결함: 시험의 가짜 서버)
- 원인: `tests/test_mcp_check.py` `_Handler.do_POST`(고치기 전 54-59행)가 html · auth 모드에서 요청 본문을 읽지 않고 응답 뒤 소켓을 닫았다.
  읽지 않은 바이트가 남은 채 닫으면 커널이 RST 를 보내고, 클라이언트가 200 text/html 을 읽기 전에 RST 를 받으면
  `mcp_check.py:437` 이 ConnectionResetError → 'closed' 로 판정한다. mcp_check 의 판정은 맞다(실제로 끊긴 연결). 결함은 가짜 서버 쪽.
- 실측(같은 판정 60회): 고치기 전 html → not_mcp 53 · closed 7 / auth → auth 60. 고친 뒤 html → not_mcp 60 / auth 60.
- 조치: do_POST 가 모든 모드에서 본문을 먼저 읽고(`_serve_mcp(mode, msg)` 로 넘김) 응답한다.
- 검증: `tests/test_mcp_check.py` 10회 반복 실행 — 10회 모두 32 passed(흔들림 0). 뮤테이션 = 고치기 전 상태(위 실측 7/60).
