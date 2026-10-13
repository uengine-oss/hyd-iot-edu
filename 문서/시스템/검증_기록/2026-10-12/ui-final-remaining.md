# U10 최종 표시 이름 감사 (Sol 6.1)

기준은 HEAD 9343fe5, NOW/UIUX/UIUX_PLAN/ui-design-contract와 최신 실제 B의 `skill-delivery-approved` 저장 응답/캡처다. 운영 스택·워커는 이 작업에서 사용하지 않는다. ProcessGPT 모노레포 README의 정의/실행 감사 분리, Vue PgToolStep/EventTimeline의 표시명/상세 원문, ontology-studio ContextPanel의 스킬/참조파일 표시를 대조한다. 교재·lecture-deck·NOW는 수정하지 않는다.

기본 표제·목록·상태·칩·폼 라벨은 실제 한국어 metadata를 쓰고 내부 식별자를 접힌 원문에 보존한다. 원래 데이터·canonical slug·도구 인자/반환·사용자 작성 문장을 임의 번역하지 않는다. 표시명 누락을 정상 표시명처럼 만들지 않고 기록 누락/조회 실패로 구분한다. 원문을 보존한 선택 상세와 편집 동선을 실제 브라우저로 확인한다.

첫 감사에서 확인한 제품 결함:

- 최신 실제 B에 `pm-schedule-planning`가 기본 스킬 표제에 노출된다. 신규 snapshot은 실행 당시 등록 본문의 title을 기록해야 하고 과거 기록은 당시 description임을 명시한다. 현재 catalog로 과거 기록의 이름을 보충하지 않는다. worker/events·agents_store metadata는 root 소유로 분업한다.
- 최신 실제 B의 도구 이름은 `enterprise-maint/pm_status`와 `neo4j/read_neo4j_cypher`처럼 Codex adapter의 서버/도구 형태다. 기존 국문 해석기는 mcp__server__tool 형태만 인식하여 실제 저장값의 표시가 연결되지 않았다. 저장값은 유지하고 표시명 조회 키만 정규화해야 한다.
- AI 배정의 settings.skills와 선택 옵션에 canonical slug를 직접 출력하는 경로가 있다. 실제 catalog title 또는 additive skill_labels로 연결하고 식별자/설정을 원문에 보존해야 한다.
- 조치 방법 목록의 sopId, 스킬 문서 원문 기본 펼침, 흐름 매핑/부품 설정과 일부 이름 미등록 노드에 내부 ID가 나오는 경로를 추가 감사한다. 편집에 필요한 실제 식별자와 일반 사용 화면의 표시 계약을 구분한다.

관련 범위 전수 읽기와 의미 있는 회귀 후 최종 결과/한계·독립 렌더 캡처·참고 비교 경로를 이 문서에 추가한다. 운영 최종 캡처는 source stable 뒤 root에게 요청한다.

## 구현과 표시 계약

표시 키만 `서버/도구`와 `mcp__서버__도구`를 연결했다. 원래 tool 문자열·서버·도구 식별자와 호출 인자 키는 바꾸지 않는다. 알려진 정비/구매 서버는 같은 제품 도구 계약의 기존 국문 이름을 사용한다. 학생 도구는 실제 저장 catalog의 title/한국어 description을 사용한다. 등록명 없음, 이름 목록을 아직 읽는 중, 목록 조회 실패를 구별한다. 이름 조회 오류를 도구 실행 실패로 바꾸지 않는다.

신규 스킬 전달/읽기 metadata의 title은 root가 worker의 실제 전달 본문에서 기록한다. UI는 이 title을 사용하고 과거 snapshot은 그때 저장한 description임을 ‘당시 설명’으로 명시한다. 현재 catalog 이름을 과거 실행에 덧씌우지 않는다. 실행별 전달 상태·해시·읽기 요청·실패/보류 상태는 유지하며 slug/path와 snapshot 전체를 접힌 원문에 보존한다. 현재 AI 배정·선택 옵션은 실제 catalog title/skill_labels로 연결한다. 스킬 문서 원문은 선택 상세에서 펼치고 기존 편집 폼에서 그대로 고칠 수 있다.

도구 서버/도구 이름과 입력 라벨에서 식별자 중복을 제거했다. 서버 설정·등록 설명·서버가 보고한 원 이름·연결 오류 원문, 도구/input schema 식별자는 접힌 상세로 보존한다. 한국어 입력 이름으로 필수 입력 오류를 표시하면서 실제 POST는 원래 meeting_id 등의 key를 그대로 보낸다. 원시 도구 반환/질문 답변/자료 인용은 임의 번역하지 않는다. 명칭 없이 colon ID의 꼬리만 공백으로 바꾸던 해석은 표시 이름 누락 상태로 바꾼다. 식별자/표현식 자체를 작성하는 흐름·정의·SQL·문서 편집 동선은 원문 편집 기능이며 등록명/일반 목록과 구별한다.

조치 방법 목록의 중복 SOP 식별자와 상세 기본 표제의 ID를 접힌 상세로 옮겼다. 규칙은 실제 annotation 또는 이름 사전을 쓰고 미등록일 때 누락 상태와 원문 접기를 함께 보인다. 이미 정상 이름이 있는 A 카드의 기존 상세는 그대로 유지한다. 정의 선택도 등록명과 판본을 보여 주며 option의 실제 ID/version과 JSON 편집 원문은 유지한다. 사용자 저장 이름 `read_only 정규화 시험` 같은 실제 작성 문장 자체를 특정 시험용 번역표로 고치지 않는다. 이런 원문·제품/모델 고유명·자료 인용을 모두 UI 번역 누락으로 세지는 않으며, 현재 설정/기록에 한국어 이름 metadata가 없는 것은 누락으로 명시한다.

F3의 추가 preview.validation도 같은 묶음에서 연결했다. 현재 지식의 기계 검사 통과/수정할 항목과 별도 사람 검토 필요를 보인다. READY/technical_ready가 검토 완료·적재 승인이 아님을 기본 표시한다. checked/boolean/flags/issues 응답이 없거나 틀리면 검사 없음/읽기 실패이며 빈 이슈 성공으로 대체하지 않는다. 읽기 검사 can_commit=false를 기존 사람 검토/재검사 API 권한 대신 사용하지 않는다. 체크하지 않은 원문 검토 guard와 원문·인용·제안 편집 입력은 유지한다.

## 검증과 증거

- 옛 UI에 실제 Codex alias·snapshot title·catalog alias 검증을 먼저 실행해 **3 failed, 2.36초**를 확인했다(`u10-display-original.log`). 첫 수정 시험에서는 중첩 summary 선택자와 normalize lookup 후 raw 반환값이 검출됐고 실제 원문 alias를 유지하도록 고쳤다(`u10-display-first.log`).
- 추가 MCP/F3 시험의 첫 묶음은 **3 passed/5 failed/1 error,169.90초**였다. MCP 시험 응답의 size_chars 등 실제 DTO 필드 누락과 없는 manuals 탭을 고른 harness 준비 오류였다. 검사 조건은 유지하고 실제 DTO/knowledge 탭으로 준비했다(`u10-display-second.log`). 새 8개 Chromium 묶음 **8 passed,12.63초**(`u10-display-third.log`).
- 실제 저장 B의 `skill-delivery-approved/before.json`을 최신 렌더러로 독립 재생했다. 원래 tool/skill slug 기본 노출 없음, ‘당시 설명’/프롬프트 전달 표시, browser 내 입력 JSON 전체 불변·instance RUNNING 불변을 확인했다. 운영 스택·새 모델 실행·처리 완료를 주장하지 않는다.
- 큰 관련 묶음은 **157 passed,4 warnings,82.08초**(`u10-related-final.log`)였다. 이후 규칙 원문 접기를 보완한 묶음에서는 **157 passed/1 failed,4 warnings,92.47초**(`u10-related-complete.log`). 보호된 A 카드 전체 golden에 정상 이름 규칙의 불필요한 추가 접기 문자열이 붙었다. golden/기존 기대값을 바꾸지 않고 미등록 규칙에만 필요한 원문 접기를 추가하는 것으로 범위를 정리했다.
- 최종 신규 표시·MCP 실제 원 key POST/필수 입력 오류·F3 4상태/기존 검토 guard·저장 B 재생·미등록 규칙 원문 접근 및 보호 A 카드 관련 묶음 **17 passed,18.65초,exit0**(`u10-final-display.log`). 새 UI 파일 11개 시험을 포함하며 원문 접기는 실제 native summary/키보드 Enter로 확인한다. 이전 실패 로그/PNG는 보존한다. 큰 묶음을 최종 판본 전체 통과로 과장하지 않으며 전체 통합 회귀는 root가 별도 수행한다.

최종 독립 화면은 루트 `.evidence/overnight-20261012/u10-final-display/`에 있다. 8상태 × 1440/1024px의 전체/패널 PNG 32개·출처/visible_text JSON 16개다. 기계 검사와 원문 접기 등의 실제 화면을 확인했으며 사용자 디자인 승인을 대신하지 않는다. `u10-reference-comparison/comparison.html`·`comparison-1440.png`·`checks.json`은 원본 이미지 6개의 최신 나란한 대조다. ProcessGPT 원본 컴포넌트의 기존 Vite 실제 compile fixture, ontology-studio 업스트림 저장 screenshot, 승인 후 실제 B 기존 캡처와 최신 UI의 같은 B 저장 응답 재생을 출처별로 구별한다. 6개 이미지 정상 로드·문서 overflow false·console/pageerror 0. 원본 이미지와 SHA-256을 checks에 보존했다.

이번 소유 변경은 JS 11개와 index의 script cache 키 `20261012-display`, UI 시험 2개, 이 문서뿐이다. CSS/색상은 변경하지 않았다. 사용자 색상 질문 때 41e21cd→964b3ff의 tokens/theme/shell diff0, instances.css의 ticker 3줄만 변경이며 기존 마지막 theme.css가 paper #f9f9f7/panel #fff를 사용하는 것을 확인했다. 추가 색상 조사는 중단하고 기존 스타일을 유지했다. `git diff --check` 오류 없음. source stable을 root에게 알렸고 제품/시험 쓰기를 종료했다. 운영 최신 캡처·전체 회귀 및 최종 인수 판정은 root 후속 증거와 연결한다.

## 전체 회귀에서 발견한 도구 정체성 누락 보완

루트 최신 전체 회귀는 `final-completion-20261012/pytest-all-final.log`의 **1 failed,2357 passed,24 skipped**였다. `test_failed_attempt_trace.py::test_the_task_panel_shows_each_failed_call_and_why`가 미등록 도구 이름을 일반 누락 문구로 표시한 뒤 각 실패 호출의 원래 정체성을 진단 표출에서 찾지 못했다. 해당 기존 시험·검사기·A 카드 golden은 변경하지 않았다.

ProcessGPT 모노레포의 실행 감사 보존, PgToolStep/EventTimeline의 도구 행과 상세 구분, ontology-studio ContextPanel의 접힌 문맥 접근을 다시 대조했다. 표시명이 없는 도구는 기본 한국어 누락 상태와 별개로 각 호출에 독립 native ‘호출 도구 원문’ 상세를 제공한다. trace·처리 기록·옛 상세 타임라인에서 같은 공통 함수를 쓰며 정확한 원래 문자열을 보존한다. 이미 이름이 있는 도구/A 카드 구성은 그대로이며, 요청·응답·실패 이유·재시도 회차를 지우지 않는다. 기본 화면에 임의 번역을 추가하지 않는다.

기존 실패 시험·U1·A 카드 첫 관련 검사는 **21 passed,8.76초**(`final-completion-20261012/pytest-tool-identity-first.log`)였다. 새 실제 Chromium 시험은 메모리 엔진의 세 번 실패→PENDING 기록을 사용하여 각 원문 상세의 닫힌 상태와 키보드 Enter 접근을 확인한다. 외부 MCP 응답은 독립 503 double이며 운영 장애나 실운영 재실행이 아니다. 추가 시험 첫 실행은 **3 failed,11 passed,1 skipped,33.89초**(`pytest-tool-identity-ui.log`): 기록의 상위 ‘시스템 기록’과 미리보기의 ‘절 본문 전체’가 원래 접혀 있었는데 준비 없이 내부 문구를 검사했다. 신규 시험의 실제 사용자 열기 동선만 보완했고 기존 기대값은 그대로다. 최초 실패 로그/캡처는 보존한다.

등록된 원천을 다시 여는 두 UI 경로는 새 GET preview를 사용한다. backend의 GET/기존 POST가 같은 읽기 handler이며 양쪽 validation 계약 시험을 유지한다. 업로드·사람 검토·적재 POST와 검토 체크 조건은 그대로이고 자동 검토 완료를 추가하지 않는다. 신규 Chromium 시험은 실제 두 버튼 동선에서 GET/no body, 원문 본문 접근, 검토 미체크를 확인한다. CSS/색상은 변경하지 않았고 변경 JS cache 키도 갱신했다.

최종 trace 관련 9파일 묶음은 **92 passed,1 skipped,4 warnings,92.38초,exit0**(`final-completion-20261012/pytest-trace-final.log`)이다. 기존 failed_attempt_trace/U1/A 카드 golden·trace gaps·G7/B5·U13 실패 화면·F3 GET/POST 계약과 신규 접근 검증을 함께 통과했다. skip은 이번 묶음에 운영 B 저장 파일 경로를 다시 주입하지 않은 명시적 saved-B 재생 시험이며, 앞선 실제 저장 B 검증을 대체하거나 실패를 제외한 것이 아니다.

`final-completion-20261012/tool-identity-final/failed-tool-identity-{trace,record}-{closed,opened}-{1440,1024}`에 16개 전체/패널 PNG와 8개 출처 JSON을 분리 보존했다. 세 실패 회차의 기본 한국어 표시, 정확한 원문 도구 identity 펼침, 각 실패 이유 보존을 실제 DOM/키보드로 확인했고 trace 1440 열린 원문 및 record 1024 닫힌 원문 PNG를 육안 대조했다. 접기 전 원문 도구 identity는 보이지 않으며 열면 각 회차의 정확한 값을 확인한다. 입력 인자·도구 반환·엔진 오류의 원래 기록은 임의 번역하지 않았다. `git diff --check` 오류 없음. 최종 source stable을 root에 알렸고 소유 제품/시험 쓰기를 종료한다. 전체 통합/실제 운영 GET 캡처는 root의 별도 최신 결과로 확정한다.

## 운영 캡처에서 발견한 미리보기 과다 원문과 대상 이름 보완

루트 실제 `final-completion-20261012/portal-live/PM-02-preflight-1440.png`를 직접 확인했다. 검사 message가 fm/cause 식별자를 기본 목록에 출력하고 추출 경고 23개의 원문 전체가 긴 빨간 문단으로 기본 펼쳐져 있었다. ProcessGPT 모노레포의 실행·감사 상세 구분과 ontology-studio의 CollapsiblePanel 문맥 접근 원칙을 적용하여 이 마지막 결함을 같은 UI 묶음에서 보완했다.

검사 설명은 H.preview.procedures/knowledge 및 H.catalog의 실제 name/annotation과 명시된 참조 키를 연결한다. 절차는 실제 이름과 출처 SOP 번호를 함께 보여준다. 표시명이 없으면 해당 대상의 이름 미등록 상태를 보이고 임의로 slug를 번역하지 않는다. 원래 issue의 sop/field/code/message JSON은 각 ‘검사 항목 원문’에 정확히 보존한다. 기계 준비도·실패 종류·범위/참조 검사 자체를 제거하지 않는다.

경고 기본 표시를 개수와 원문 대조·단계/연결 검토 안내로 바꾸었다. ‘추출 경고 원문’ native 접힘에는 23개를 포함한 원래 warnings 전량·순서를 그대로 보존한다. 추출 제안·원문/인용·편집 값·사람 검토 체크 및 적재 guard·CSS/색상을 변경하지 않았고 hitl script cache 키를 갱신했다.

신규 실제 Chromium 시험은 독립 저장 제안에 실제 backend manual_preflight.validate를 실행한 결과로 등록명/누락 상태·모든 issue JSON·경고 23개의 정확한 DOM textContent·키보드 접근·입력 불변을 검사한다. 추가 실제 저장 a161-c3/proposal-PM-02.json 재생은 제안 knowledge의 실제 한국어 이름과 경고 접기를 확인한다. 과거 추출 제안의 재생이며 현재 운영 DB 검사나 사람 검토 승인이 아니다.

첫 신규 묶음은 **1 failed,7 passed,9 deselected,16.92초**(`pytest-preflight-names-first.log`)였다. 브라우저 innerText가 끝 공백을 정규화하여 원문 문자열 비교가 실패했다. 정확한 원문 보존 확인은 all_text_contents로 강화했다. 다음 관련 묶음은 **1 failed,53 passed,1 skipped,2 warnings,68.56초**(`pytest-preflight-names-final.log`): 기존 U13 app 복구 시험의 POST 안내 문구가 후속 await refreshBiz GET보다 먼저 갱신되어 상태 읽기가 완료되기 전에 검사하는 준비 race였다. app 제품 소스나 기존 assert는 바꾸지 않고 실제 상태 GET 완료를 기다리도록 준비 순서만 정리했다. 모든 초기 로그/PNG를 보존한다.

루트가 기존 검사/준비 변경으로 통과시키지 말라는 계약을 재확인하여 위 U13의 준비 wait 추가를 원복했다. 중간 `pytest-preflight-names-approved.log`의 54 passed는 그 준비 wait를 포함한 중간 판본이므로 최종 제품 근거로 채택하지 않는다. 원래 개별 시험은 타이밍에 따라 **1 passed,2.48초**(`pytest-app-status-original-individual.log`)였다. 요청은 최초 status GET503→start POST200→후속 status GET200이며, 기존 app.js는 성공/기준점 안내를 먼저 표시한 뒤 상태 GET를 기다렸다. hitl 수정과 별개인 app 함수의 실사용 화면 순서 결함이다.

새 독립 Chromium 시험은 후속 status GET를 HTTP 경계에서 보류한다. 옛 제품에서 GET 미완료인데 성공 안내가 이미 나오는 것을 **1 failed,2.45초**로 입증했다(`pytest-app-status-negative.log`). 실패 후 보류 요청 teardown 취소 로그도 그대로 보존한다. 기존 U13 시험의 기대/준비는 바꾸지 않고 제품 biz-start만 상태 GET 완료→화면 칩 갱신→성공 안내 순서로 수정했다. 명령/API·원래 응답/기준점·성공 문구는 유지하며 app cache 키를 갱신했다. 신규 보류 GET 시험과 원래 U13 시험 **2 passed,3.80초**(`pytest-app-status-fixed.log`). CSS/색상은 그대로다.

최종 제품 판본 관련 6파일 묶음은 **73 passed,1 skipped,2 warnings,89.73초,exit0**(`final-completion-20261012/pytest-preflight-final-source.log`)이다. preflight 이름/경고·기존 사람 검토 guard·원천 GET/기존 POST·저장 실제 PM 재생·U13 기존 app 시험의 원래 준비/기대·GET 보류 부정 시험·remaining UI·B5/A 카드 golden을 함께 통과했다. skip은 saved B 경로를 다시 주입하지 않은 명시적 재생 시험이고, 저장 PM 시험은 실제 수행해 통과했다.

최신 독립 캡처는 `final-completion-20261012/preflight-final-source/`에 분리했다. `saved-pm-preflight-names-*`는 실제 저장 PM 제안의 재생, `preflight-names-warnings-closed-*`는 독립 catalog/제안 fixture의 기본 핵심 표시다. 원문 펼침 전 canonical 대상 ID·긴 경고 원문 비노출, 펼친 후 원래 issue JSON 전체와 경고 23개 순서/끝 공백까지 정확한 textContent, 제안 입력 불변과 사람 검토 미체크를 확인했다. 운영의 최신 PM/PR GET 상태·최종 전체 통합은 root가 별도 캡처/회귀로 확인한다. 소유 제품/시험/문서 쓰기를 종료했고 source stable을 root에 알렸다.

## 구매 원문 절차의 명시적 검토 모델과 SCM 읽기 범위 (5747907 이후)

루트 baseline5747907(2381 통과 검증/커밋/rebase/push) 전에는 제품 쓰기를 동결하고 읽기 조사만 했다. 재개 승인 뒤 read_audit가 소유한 source-backed purchase 모델과 계약을 맞췄다. ProcessGPT 모노레포의 업무 정의/실행 감사 분리와 ontology-studio의 출처·문맥 접근을 참고한다.

구매 검토 폼은 scope=purchase를 명시하고 실제 GET /api/kg/manuals/catalog의 Part·Role을 선택한다. 고장 조치는 기존 scope 생략/고장 유형 필수 계약을 유지한다. executable은 명시적 참고 보관 또는 실행 후보 선택이며 미지정을 자동 true/false로 만들지 않는다. 참고 보관은 ERP 구매요청을 만들지 않고 실행 후보에서 제외한다. 실행 후보는 원문 구매요청 Action·승인 Role·Supplier/Part 관계를 backend가 검사한다. UI는 ERP 시스템을 임의 입력해 범위를 바꾸는 필드를 추가하지 않는다.

적재 전 실제 사람 검토 checkbox 조건은 그대로다. scope/부품/역할/단계 등 내용을 고치면 검토 체크를 해제하고 받은 제안 검사와 편집한 연결을 구별한다. 실행 후보 기계 검사 통과는 실제 구매 승인이나 ERP 실행 완료를 뜻하지 않는다. reference/ready/mismatch는 절차별 execution[] 결과와 정확한 원문 접기를 제공한다. 최상위 links의 명시 key(빈 객체 포함)가 inline p.link보다 우선하며 원문 affects 값을 폼에 보존한다. 참고 보관을 명시적으로 선택한 경우 검토 링크의 actions는 빈 목록이고 original inline/override/제안 본문은 그대로 별도 보존한다. 자동 사람 검토/승인·새 공급사/견적/가격 데이터는 만들지 않는다.

SCM 실제 읽기 원장은 final-completion-20261012/C-scm-read-utf8.json이다. HTTP GET 4개 전부200, DB reader의 transaction_read_only=on 상태에서 SELECT6개를 확인했다. ent.suppliers 3행은 공급사 원천에 직접 연결된 P-CLR-CORE 범위이며 ent.part_quotes(P-PMP-SEAL)·quote_rows는 실제3행이다. 승인 여부는 sup:a/b true, sup:c false이고 ERP 필요량6을 확인했다. 실제 배포된 scm_suppliers 함수도 원천표의 part_no만 조회한다. 따라서 씰 부품 공급사0건은 기존 조회 범위의 정상 결과이며 전체 견적/승인 공급사 부재를 뜻하지 않는다. tests/test_whatif.py의 기존 씰0/core3 기대를 유지한다. 처음 PowerShell HTML parser 실패/문자 인코딩 오류를 포함한 별도 JSON은 보존하되 정상 UTF8 Python+DB 원장을 판정 근거로 사용했다.

enterprise-mcp/server.py의 scm_suppliers·part_quotes 설명 두 곳만 각 원천의 자료 범위를 명시했다. 현재 부품별 가격/품질/납기/AVL은 part_quotes로 읽어 대조하며 ‘fallback’이나 없는 자료를 채우는 동작으로 설명하지 않는다. 원래 RPC·SQL·seed·MCP read 권한과 실행 코드는 바꾸지 않았다. 소유 범위는 read_audit와 사전 합의했다.

신규 실제 Chromium 시험은 GET catalog/미리보기와 독립 POST 경계를 사용하며 outgoing purchase 링크를 공용 purchase_shape로 실제 검사한다. 참고 보관/FM-free 구매, 기존 fault FM 필수, 명시 선택 누락·Part 누락·Role 누락 거절, 503/잘못된 catalog, inline과 빈 top override 구분, 원문/인용/affects 불변, 변경 후 검토 해제 및 native keyboard/필드 라벨 접근을 확인했다. Supplier/Part 관계 유무는 실제 backend manual_preflight 결과를 렌더하여 ready/mismatch와 원문 보존을 검사했다. 실제 FastMCP discovery는 도구 설명/읽기 묶음과 기존0/3행·AVL값을 검사한다.

- baseline5747907 hitl.js를 독립 Chromium에 원문 그대로 읽어 새 구매 참고 검증 **1 failed,3.97초**(`pytest-purchase-ui-original-negative.log`). 운영 파일/기존 검사기 교체 없이 옛 제품의 구매 폼 미지원을 입증했다.
- 첫 UI 묶음 **23 passed,1 skipped,46.81초**(`pytest-purchase-ui-first.log`). 관련 UI/whatif/worker/SCM 기존 기대/A 카드 묶음 **88 passed,1 skipped,5 warnings,116.18초**(`pytest-purchase-ui-related.log`).
- backend 관계 검사 표시를 포함한 묶음 **26 passed,1 skipped,1 warning,52.36초**(`pytest-purchase-ui-final-source.log`). 마지막 접근 가능한 필드/정확한 조회 DTO/신규 source 계약 검증 **9 passed,1 warning,18.23초**(`pytest-purchase-ui-approved.log`). skip은 경로를 주입하지 않은 saved B 재생뿐이다.

최신 독립 화면은 final-completion-20261012/purchase-ui-approved/에 있다. purchase-reference-fields-1440-panel.png를 육안 확인했고 1440/1024 문서폭 초과 없음·pageerror 없음·Part/Role 실제 라벨·기본 canonical ID 미노출·원문 접근을 검증했다. 이는 독립 fixture/실제 pure preflight의 UI 증거이며 실제 운영 적재/ERP 실행이 아니다. 소유 변경은 hitl.js/index cache 키, server.py 설명 두 곳, 새 UI/metadata 시험 두 파일과 이 문서다. CSS/색상/교재/NOW는 변경하지 않았다. git diff --check 오류 없고 source stable을 root에 알렸다. 소유 제품/시험/문서 쓰기를 종료하며 실제 원문 검토·적재·배포·전체 통합은 root의 후속 원장으로 확정한다.

## 새 구매 도구와 동적 공급사 선정 설명

새 실제 purchase_context/evaluate_purchase/submit_purchase 계약을 읽고 ProcessGPT 모노레포의 감사/실행 구분과 ontology-studio의 원문 문맥 접근을 대조했다. ui/plainWords/compare와 trace 연결, 필요한 caseRecord 실패 분류 및 index 캐시 키를 같은 묶음에서 보완했다. CSS/색상·기존 A golden·기존 기대값은 유지했다.

구매 부품 근거 조회는 실제 ERP 재주문점 이탈→등록 Part→원문 구매 절차와 참고/실행용 구분을 표시한다. 원문 executable=true는 실행 후보 검토 대상이지 실제 승인/실행 성공이 아니다. 구매 후보 비교는 Part·필요량·후보 수·실제 추천명·정책의 실제 견적/AVL을 설명하며 조회/계산만이다. 구매 판단 등록은 실제 SUBMITTED 상태와 판단 id가 함께 있는 경우만 등록됨으로 표시한다. 평가용 RUN/id만으로 등록을 주장하지 않고 사람 승인/ERP 실행 완료와 구별한다. 핵심 결과/제한 문구를 요약 앞에 두어 기존 trace 말줄임에서 의미가 빠지지 않게 했다.

compare는 상세 결과 값이 저장되지 않은 호출에서 후보 수/등록 성공을 추정하지 않는다. 입력은 부품 번호와 호출 목적을 한국어로 보이고 차단/실패 이유와 정확한 호출 원문을 native 접기에 보존한다. unknown schema는 원문 확인 상태다. 새3 trace 원문은 8000자 표시 절단 없이 전량 보존하며 12000자 unknown 응답 JSON까지 실제 키보드 접근으로 동일하게 대조했다. MCP가 result=error를 정상 protocol 응답(is_error=false)으로 반환해도 새 구매 도구의 trace/caseRecord/compare는 명시적 실패로 표시한다. 원래 provider flag/output은 바꾸지 않는다. 기존 도구의 오류/원문/A 표시 경로는 그대로다.

read_audit와 supplier_policy DTO를 직접 합의했다. 원문 공급사 고정값(현재 등록명)/미상과 정책 모드를 구분한다. 정책은 oem/lowest_approved/fastest_quote 명시 선택이고 기본 미지정 값에서 Supplier를 자동 추정하지 않는다. 정책을 선택한 검토 링크는 같은 원문 PR Action의 value=null과 supplier_policy만 보내며 원문의 fixed 값을 별도 보존한다. 참고 보관은 선정 정책을 거절한다. 순정은 현재 원천 정본의 정확한 B-OEM (순정) 라벨 계약, 최저가는 승인된 비순정 중 최저가, 최단 납기는 전체 견적 중 선택 후 AVL을 별도 검사한다. 다른 이름에서 OEM 여부를 임의 추측하지 않는다. resolve_supplier의 실제 기존 부품별 quote_rows 결과로 55/5일/AVL true,35/2일/true,20/1일/false를 확인했고 새로운 상품/가격/공급사 자료는 넣지 않았다. 이 AVL은 공급사 등록 여부이며 현재 처리 건의 사람 승인이나 발주 완료가 아니다.

증거는 모두 final-completion-20261012에 있다. 새 도구 첫 실제 Chromium 묶음 **5 passed,11.89초**(pytest-purchase-tools-first.log). trace/U1/A 카드/실패 시도/기존 trial 묶음 **96 passed,1 skipped,4 warnings,48.44초**(pytest-purchase-tools-policy.log), display/A/실패 호출 **48 passed,1 skipped,71.38초**(pytest-purchase-tools-policy-approved.log). 추가 unknown 전량 원문/실패 envelope/정책/검토 guard 관련 최종 **55 passed,68.56초**(pytest-purchase-display-approved.log), 핵심 문구 순서를 정리한 최종 새도구 **9 passed,15.23초**(pytest-purchase-tools-final-order.log). 최종 두 묶음은 skip0이며 앞선 선택적 시험 skip을 실제 성공으로 대신하지 않는다.

실제 backend Part 경로 계산/메모리 판단 등록과 단독 graph/ERP/submit double을 사용해 UI를 검증했다. 이는 운영 처리 건/사람 승인/실제 ERP 효과가 아니다. 최신 화면은 purchase-tools-final-order/ 및 purchase-display-approved/에 분리했고 이전 PNG/로그를 보존했다. purchase-tools-trace-1440-panel.png를 육안 확인했다. 기본 내부 도구/Part/Skill id 미노출, 실제 부품·후보·등록 구분과 원문 접근을 검증했다. git diff --check 오류 없고 최종 source stable을 root에 알렸으며 소유 제품/시험/문서 쓰기를 종료한다. 운영의 최신 조회/적재/제출/승인/실행과 최종 전체 통합은 root의 후속 원장으로 확인한다.

일반 원문 참고 절차와 기존 실행 절차 재참조를 연결했다. ProcessGPT 모노레포 README의 정의·감사·실행 구분과 ontology-studio ContextPanel.vue의 접힌 문맥을 다시 읽고 대조했다. kind=reference/executable=false를 명시적으로 보존하며 정비 요청/설비 제어/담당 역할로 추정 변환하지 않는다. inline/명시 links override(빈 객체 포함)/당시 역할/참조 metadata는 원문 접기에 보존한다. 기존 사람 검토 체크와 편집 시 해제 계약은 그대로다.

실제 catalog.skills[].reference_contract의 대상·SOP 번호·전체 단계·해시를 대조하고, 불일치하면 요청 전 오류를 표시한다. 과거 pin을 현재 catalog로 자동 덮지 않고 사용자의 명시적 선택에만 조회 판본을 고정한다. 미상 역할은 그대로다. 실제 계약에서 읽은 reference_contract.sections의 등록 설명은 원본 인용과 구분한다. 원문 0.9와 기존 설명 1.2를 각각 그대로 대조하며 기존 실행 기준이나 active HAS_STEP을 수정하지 않는다. 독립 fixture에서 실제 manual_review.validate/check_binding/manual_graph.desired를 사용해 exact 참조는 Skill/active HAS_STEP을 추가하지 않고 DOCUMENTS 두 단계만 보관함을 검증했다. 운영 DB 변경은 아니다.

PM은 실제 maintenancePlan 생성기의 기존 오더 일정 변경과 새 오더 생성 계획을 구분한다. execution:pm-plan의 제외 annotation을 모두 표시하고 기존 오더·정비 시간·기한 미상 때 새 오더/창을 추정하지 않는다. 처리 기록/승인 카드/업무 카드/단계 상세의 해당 metadata만 추가하고 계획·제외 근거 전체 원문을 접기에 보존한다. CSS/색상·기존 A golden·기존 시험 기대값은 불변이다.

final-completion-20261012/pytest-reference-ui-original-negative.log: 기존 baseline 5747907 스크립트를 메모리로 읽은 새 부정 시험 1 failed,4.52초(reference가 work_order로 선택됨). 최초 새 source 시험 2 failed/4 passed,73.53초는 fixture URL의 colon 인코딩 누락으로 원문 GET을 잡지 못한 준비 오류였다. 수정 후 pytest-reference-purchase-ui.log 18 passed,37.38초. pytest-reference-pm-ui-final.log 1 failed/29 passed,61.86초와 pytest-reference-pm-ui-approved.log 1 failed/77 passed/1 skipped,126.63초는 새 PM 시험이 기존 '다른 안' 접기를 펼치지 않은 준비 오류다. 기대를 줄이지 않고 실제 키보드 펼침을 추가했다. pytest-reference-pm-ui-stable.log 1 failed/9 passed,23.29초는 새 미상역할 시험이 연결 JSON 대신 첫 인용 접기를 골랐던 선택자 오류다. 정확한 원문 제목을 선택하도록 고쳤다. 기존 시험/준비 파일은 변경하지 않았고 초기 로그는 모두 보존했다.

관련 backend/UI 계약 pytest-reference-pm-ui-last.log 64 passed/13 skipped/2 warnings,27.41초(선택적 실제 Neo4j 13 skip은 미실행). 기존 A 카드·U1·cards pytest-reference-pm-a-golden.log 30 passed,8.00초. 최신 reference/PM/A 카드 pytest-reference-pm-ui-release.log 16 passed,28.07초. 마지막 번호 표시 정리 후 pytest-reference-pm-ui-approved-final.log 16 passed,21.63초,skip0. 최종 캡처 reference-pm-ui-approved-final/에 preview HTML/원문·catalog JSON/1440·1024 PNG를 보존했다. 부모 scroller가 긴 preview 전체 panel 일부를 가려 비교 영역을 실제로 스크롤해 별도 PNG를 추가했고 reference-contract-comparison-1440-panel.png를 육안 확인했다. 두 판본과 단계·미상역할·접힌 정확 원문이 읽힌다.

모든 HTTP·캡처·판단은 독립 Chromium와 합성 catalog 또는 실제 원문 파서/계약 생성기 fixture이며 운영 적재·실제 승인·오더 변경이 아니다. git diff --check 통과. 소유 제품/시험/문서 쓰기를 종료한다. 최신 운영 적용/캡처·최종 전체 회귀는 root 소유 후속 작업이다.

독립 최종 감사의 PM 실행 조건 누락을 읽고 read_audit의 실제 DTO와 소비 계약을 맞춘 후 UI 마지막 묶음을 완료했다. ProcessGPT 모노레포 README의 정의·감사·실행 구분과 ontology-studio ContextPanel.vue의 접힌 문맥/원문 접근을 다시 대조했다. 소유 변경은 ui/plainWords/approvalCard/caseRecord/taskDetail/index와 UI 시험뿐이며 CSS/색상·기존 A golden은 불변이다. 운영 Docker/워커/graph/ERP 쓰기는 수행하지 않았다.

maintenancePlan.assets[].service와 실행 불가의 maintenanceDiagnostics에서 실제 누적 운전시간 11,950, 마지막 정비 누적 10,000, 다음 차례 12,000, 해당 4,000시간 패키지를 읽는다. UI는 간격/패키지/차례를 계산하지 않는다. 실패에서도 부분 진단을 보존하고 후보 제외·미연결 리턴 필터/작동유·수량/재고 미상을 표시한다. 동종 원문 적용 범위, 상대 설비 하한·실측값, 목표 운전시간·상한, 공통 창, 두 설비별 부품과 전체 필요량을 실제 applicability/parts/parts_totals 값으로 읽는다. false는 불일치/미달이고, 누락은 검사 기록 없음이다. 인력 필요/가용/부족과 confirmed=false를 그대로 표시하여 확보 완료나 정비 완료를 주장하지 않는다. 실제 ERP에 필터/작동유가 없어 현재 B 실행 계획이 막힌 사실을 UI에서 feasible로 바꾸지 않는다.

stock_effect는 예약/reserve, 실물 출고/issue, 기존 할당 유지/preserve로 구분했다. on_hand/reserved는 실물과 기존 예약, owned_qty는 해당 기존 오더의 할당이다. 새 예약·재출고를 추정하지 않는다. receipt.after.plan과 after.orders[]의 실제 두 asset/ref/status/package/window_starts_at을 구별하고 실제 행이 없거나 두 설비 범위와 맞지 않으면 두 오더 등록 완료를 주장하지 않는다. 그룹 취소는 각 오더의 취소 상태를 읽고 물리 정비 완료와 구별한다. 실제 scoped CMMS가 한 오더의 상태 변경 때문에 전체 취소를 거절한 영어 원문은 정확한 알려진 guard 문장에 한해 한국어로 표시하며, 원래 오류 문자열 전량을 native 접기에 보존한다. 알 수 없는 함수 이름이나 오류 의미는 추정 번역하지 않는다.

기존 pm_status.package는 package_semantics=base_interval_configuration이 명시된 경우에만 ‘등록된 기본 정비 내용’으로 표시한다. configured_base_package도 등록 설정이고 다음 4,000시간 패키지 선택과 다르다. 동일 의미를 scalar/object/records 화면에서 한국어로 읽고 enum 원문은 접기에 남긴다. 없는 역사 metadata를 현재 설정으로 보충하지 않는다. cache key는 pmpackage로 갱신했다.

증거는 final-completion-20261012에 있다. 직전 plainWords-pm-package-before.js를 메모리에서 재사용한 새 부정 검증 pytest-pm-package-ui-original-negative.log는 2 failed,3.06초로 두 설비 범위·실행 불가의 4,000/12,000 근거 누락을 입증했다. 새 첫 시험 3 failed,4.82초는 전체 원문 패키지 범위를 요구하는 backend 정책에 시험 fixture의 필터/작동유가 빠진 입력 오류였다. 전체 범위를 명시한 뒤 3 passed,5.96초. 실제 memory 영수증 첫 묶음 1 failed/5 passed,10.70초는 독립 정책 5%와 실제 memory 회사 설정 10%의 불일치였고 해당 fixture만 실제 설정을 명시한 뒤 6 passed,10.99초. source_id 동일 판본·stock_effect mandatory 필드가 병행 구현 중 추가되어 새 fixture들이 차단된 5 failed 로그들도 보존했다. 검사를 완화하지 않고 명시 입력을 보강했다.

기존 test_portal_maintenance_plan_ui 두 실패는 실제 추가된 부품 원문 접기 때문에 summary/pre가 복수 선택된 점, WO_RESCHEDULE fixture에서 코드만 WO_CREATE로 바꿔 preserve가 남았던 점이다. pytest-pm-package-ui-release.log 2 failed/47 passed,39.35초와 final-stable.log 2 failed/47 passed,30.30초를 보존했다. read_audit 요청과 root 보고에 따라 원래 JSON을 담은 제목의 native fold를 정확히 선택하고 create 입력에 reserve를 명시했다. 기존 raw JSON 동일성·상태·내용 assert는 유지했으며 create 금지 계약을 제품에서 완화하지 않았다.

최신 PM/Scoped CMMS/UI/U1/실패 호출/A golden 관련 묶음은 pytest-pm-package-ui-final-approved.log **49 passed,26.79초,skip0**이다. 신규 UI 시험 8개는 실제 maintenance_policy/plan/scope와 독립 EnterpriseState.execute를 사용했다. 실행 가능 분기는 시험 전용 부품 재고와 계수기를 명시한 메모리 fixture이며 실제 ERP master에 필터/작동유를 넣지 않았다. 가상의5% 정책 시험과 실제 회사10% memory 시험을 구분한다. 실제 Neo/PG 검증은 root/read_audit 소유 증거이며 이 UI 시험을 실제 운영 승인/적재/오더 실행으로 주장하지 않는다.

최종 캡처 pm-package-ui-final-approved/에 실패 4,000/12,000·설비별 근거·두 실제 memory 오더 영수증·그룹 취소·실제 거절 pending 화면을 1440/1024로 보존했다. 부모 scroller 때문에 긴 전체 panel 하단이 가릴 수 있어 각 data-pm-asset와 data-pm-orders를 실제 스크롤하여 별도 상세 PNG를 남겼다. pm-infeasible-retains-4000-and-12000-1440-panel.png와 두 오더 상세 PNG를 육안 확인했다. 원문/영수증은 키보드 펼침 뒤 전량 JSON과 deep equality로 검증했다. git diff --check 통과. UI 소유 제품/시험/문서 쓰기를 종료하고 source stable을 root에 전달한다. 운영 배포·실제 B/C 대조와 전체 통합 회귀는 root 후속 작업이다.


실행 검사와 규칙 비교의 UI 경계를 마지막 묶음으로 연결했다. 최신 보존 ProcessGPT 모노레포 README와 업무 카드/이벤트 화면, ontology-studio ContextPanel.vue의 접힌 문맥을 다시 읽고 대조했다. evaluation_mode/정확한 bool execution_checked의 실제 기록만 판정한다. rule_analysis는 ‘규칙 비교 · 모의 순위 / 실제 승인 · 실행 준비는 확인하지 않음’, structural은 연결 구조 검사, metadata 누락·타입 오류·부모/후보 충돌은 확인 안 됨이다. 실제 execution/true의 정상 A 기본 카드에는 새 경고나 원문 접기를 추가하지 않는다. 과거 metadata 없는 기록을 현재 설정으로 채우거나 실행 검사를 받았다고 하지 않는다. 기존 역사 기록의 서버 재검사 호환은 유지하며 명시적인 모의/불일치 metadata는 승인 선택을 막는다.

실제 trial ranking/whatif cards/업무 후보/승인 요약/처리 기록의 노출 경로에서 같은 구분을 적용했다. 모의 순위의 원래 점수·feasible·제외 원인·recommended 값은 그대로다. 처리 기록 문장은 모의 1순위 계산이며 실제 승인 준비는 미확인임을 명시한다. 평가 metadata 전체는 native 원문 접기에 보존한다. 승인 요약에서는 경고를 머리에 표시하고 보조 원문은 끝에 두어 기존 ‘다른 안’ 접근 순서를 유지한다. 실제 PR_CREATE 후보는 공통 구매 표시 함수로 승인 머리·다른 안·처리 기록에 부품 이름/번호, 필요 수량, 금액, 납기 여유, 실제 정책/견적 공급사/가격/납기/등록 검사 근거를 보여 준다. 원래 action/quote/facts는 전량 원문에 보존하고 공급사나 판본을 추정하지 않는다. 이것은 구매요청 계획이며 사람 승인·발주 완료가 아니다.

purchase preflight ready=true는 ‘실행 후보 기계 검사 통과 · 연결 구조 검사 통과’다. 실제 견적·재고는 실행 판단 시 확인하며 현재 실제 승인·실행 준비는 미확인이라고 별도로 명시한다. ready 원래 생산자 판정이나 기존 assertion을 바꾸지 않았다. PM의 structural/false/ready=false도 실제 계획 가능성과 혼동하지 않는다. 원문 검토 체크·실제 commit 보호·사람 권한은 그대로다. CSS/색상은 verified 5747907 이후 변경 0이며 A golden 원본/기대값은 불변이다. index의 해당 JS cache key는 evaluation 판본으로 갱신했다.

독립 실제 producer→Chromium 신규 시험은 tests/test_portal_evaluation_mode_ui.py이다. pure cards/trial, 실제 Enterprise HTTP TestClient를 쓰는 whatif, 구매 DmnTools/정식 AVL 규칙, manual_preflight의 실제 catalog 계약, 실제 FastAPI/MemoryRepo 승인 패널을 재사용했다. 운영 장애/승인/ERP 실행이 아니다. 1440/1024 실제 승인 버튼 비활성·POST 0·실행 0, 모의 순위와 제외 이유 보존, unknown/false/string bool/부모 충돌, native 키보드 원문과 deep equality를 검증한다. 기존 A 시험에는 실제 신규 생산자의 execution/true metadata만 명시했고 기존 assertion/fixtures/a_cards_before.json은 바꾸지 않았다.

증거는 delegated-review-20261012에 보존했다. pytest-evaluation-ui-original-negative-clean.log는 옛 UI의 실제 모의 producer 결과가 승인처럼 표시된 1 failed/3.72초의 부정 증거다. 초기 새 시험의 local escape 함수 오류, 새 capture expected 인자 타입·native keyboard 선택 오류, 독립 fixture의 AVL 규칙/완전한 catalog 키 누락 로그도 보존했다. 추가 승인 시험 첫 실패는 실제 pattern 없는 pure bundle을 필수 필드로 읽었던 준비 오류였다. 다음 실패는 이미 렌더한 역사 snapshot을 같은 id로 바꾸어 UI의 기존 cache가 유지된 준비 오류였다. 새 합성 기록을 제품 최초 GET 전에 제공하도록 고쳤으며 제품 cache나 기존 준비 파일/기대값을 변경하지 않았다.

pytest-evaluation-ui-fourth.log는 신규 UI와 A **17 passed/2 warnings/27.97초**이고 pytest-evaluation-ui-approval-third.log는 실제 승인/처리 기록 **2 passed/9.58초**이다. 넓은 UI 10파일 묶음 pytest-evaluation-ui-final.log는 **84 passed/2 failed/2 warnings/179.06초**였으며 실패를 성공으로 덮지 않았다. 기존 구매 기계 검사 명칭 누락과 새 평가 원문 접기가 ‘다른 안’ 앞에 생긴 호환 문제를 제품에서 고쳤다. 기존 구매/PM 시험·기대·선택자는 불변이다. 수정 뒤 해당 경로와 신규 의미 검증/A golden 전체 pytest-evaluation-ui-compat.log는 **34 passed/2 warnings/61.09초, skip0**이다. 이전 넓은 84 통과를 수정 뒤 전체 86 통과라고 합산하지 않으며 최신 전역 통합은 root의 후속 전체 회귀로 확정한다.

최신 독립 캡처 evaluation-ui-compat/와 실제 모의 승인 전체 패널 evaluation-ui-approval-third/에 1440/1024 PNG/visible text/provenance JSON을 보존했다. 모의 승인 패널과 실제 구매 정책·견적 상세 PNG를 육안 확인했다. 원문 접근을 검증한 일부 PNG는 native 원문 접기가 열린 상태이며 기본 화면 영문 노출 증거로 주장하지 않는다. 기존 승인 재검증 캡처는 evaluation-ui-final/에 별도로 보존했다. 문서 overflow 검사는 retain/capture에서 유지했다.

실제 운영 GET 캡처는 F/capture-delegated-live.py와 reference-delegated-comparison.html을 준비했다. 기본 실행은 오프라인 준비만 수행하며 HTTP/browser를 실행하지 않는다. root가 최종 검증 source manifest/배포/실제 원문 적재/C 상태를 준비한 뒤 --run-live로 실행한다. 전체 portal 파일 SHA를 배포 mount와 비교하고 불일치하면 실패한다. 같은 root 실제 A/B/C id, 1440/1024, console/page errors 0, document overflow 0, GET-only/browser writes 차단, 전후 case/task/approval/effect/manual journal 불변을 검사한다. A 미달/B 보류/C 실제 상태를 보존하고 actual4000/12000·필터/작동유 누락 이유를 읽는다. 실제 원문 전체 bytes SHA와 사용자 위임 Codex의 ACTIVE 이력, 역사 reference pin/등록 영수증/현재 전체 계약을 GET으로 대조한다. source preview는 원래 추출 제안이며 검토 연결을 화면에 주입하지 않는다. 비교 HTML의 오른쪽은 실제 실행 전에는 캡처 미완료로 표시한다. ProcessGPT 최신 보존 E2E 목록 PNG와 기존 Dify 공식 문서 PNG의 원본 SHA를 보존하며 새 upstream/live 참고 화면이라고 주장하지 않는다.

최종 own UI/test 해시는 evaluation-ui-source-sha256.json에 있다. git diff --check 통과. 제품/시험/소유 문서 쓰기를 종료하고 source freeze를 root에게 알린다. Docker/서비스/워커/운영 graph·ERP 쓰기는 하지 않았다. 실제 배포·적재·C 승인/발주/입고·B 보류와 최종 전체 회귀는 root 소유이다.


### 실제 C 도구 요약·실행별 짝짓기와 구매 원문 비용 표시 후속 검증

실제 C 공개문장 PNG에서 Cypher 전문과 `[] · text`가 기본 행에 노출됐다. trace 소비자는 구매 세 도구만 공통 쉬운 말 해석기를 사용하고 나머지는 입력·응답 원문을 기본 요약에 넣었다. 공통 해석기로 연결하고 실제 조회 목적을 확인할 수 있는 알려진 질의 형식, 등록된 설명, 반환 배열 건수만 요약한다. 목적/결과 의미를 알 수 없으면 미확인과 원문 확인을 표시한다. 0건은 읽기 실패·알 수 없는 형식과 구분한다. 원문 입력·응답은 키보드로 펼칠 수 있고 본문 끝과 구조를 그대로 보존한다. 새 Chromium 부정 검증은 수정 전 5실패, 수정 후 통과했다(`ui-tool-semantic-before.log`).

Codex의 다음 실행에서 `item_1`이 재사용되면서 과거 도구와 새 도구의 DOM key가 같았던 제품 결함도 수정했다. 공통 식별자는 처리 건·작업·worker job·tool_use_id의 네 값이다. trace, 처리 기록, 기존 작업 상세, 현재 실행 도구 표시가 같은 기준을 사용한다. 서로 다른 실행의 시작/완료 교차, 완료 먼저 수신, 재접속 replay에서도 원문 입력·응답은 해당 실행에만 결합되며 DOM key 중복이 없다. 해당 3상태 검증은 신규 시험에 포함한다. 과거 실제 C tool PNG는 오래된 행을 찍은 한계가 있어 최신 도구를 보여 준 실시간 근거로 주장하지 않는다. F watcher는 새 실행별 실제 UI 식별자로 정확한 행을 선택하며, 저장 기록의 마지막 도구 GET 캡처는 완료 후 읽기 증거로 별도 표시한다. B는 task_deferred 실제 receipt와 worker job을 결합해 평가 종료로만 기록하고 업무 완료라고 표시하지 않는다.

구매 경제 DTO의 발주 금액·기대 불량 비용·전수 검사 비용·비교 총비용을 승인/다른 안/처리 기록/도구 결과에 구분하여 표시한다. 비교 총비용은 금액이고 기존 물리 예측 점수로 해석하지 않는다. 원문 정책의 손실·불량률 검사 기준·검사비와 정확한 인용은 보존하며 UI의 고정 250 계산은 없다. 독립 정책 137/17 입력은 210·32.88·17·259.88을 그대로 표시해 반올림/고정값 혼입을 검출한다. 보호된 PR7.4 실제 텍스트를 사용한 생산자 시험은 410 대 360의 총비용과 다른 안의 비용 차이를 확인했다. 동점에는 ‘비교 총비용 같음’을 표시하며 점수가 0 낮다는 이유를 만들지 않는다. 경제 기록이나 값이 없으면 발주 금액으로 총비용을 추정하지 않는다. 시작 변수의 알려진 경보 패턴은 기존 한국어 의미로, 사건/경보 식별값은 해당 값이 있다는 관측만 기본 표시하고 실제 식별자를 원문에 보존한다.

최종 관련 묶음은 78통과·4경고·64.27초(`ui-tool-cost-identity-final.log`), 마지막 비용/PR7.4 원문/기존 A 승인 화면 확인은 15통과·10선택 제외·25.59초(`ui-cost-source-and-A-final.log`)다. 최초 관련 실행의 21통과/1실패는 병렬 작성 중 backend purchase_comparison.py의 미완성 구문을 읽은 것이며 원문 로그를 보존하고 작성 종료 뒤 통과한 판본을 구분했다. 기존 시험 assertion은 변경하지 않았다. 추가된 시험은 `tests/test_portal_tool_semantics_ui.py` 하나다. 1440/1024 PNG는 F/ui-tool-cost-final의 독립 Chromium fixture 증거이며 실제 운영 실행이나 추가 LLM 실행으로 주장하지 않는다. ProcessGPT 모노레포와 연결된 최신 Vue PgToolStep/agentEventTimeline, ontology-studio OntologyGraphPanel의 표시명/상세 원문 구조를 대조했다. CSS·색상 변경은 없고 기존 A 표시 조건을 유지했다. 최종 제품 7파일 해시는 F/purchase-ui-source-sha.json에 고정했으며 이 뒤 제품 쓰기를 종료한다.


2026-10-12 B 실제 보류 근거 표시 추가 검증: 실제 GET 저장본의 task_deferred.receipt.assessment.evidence.evaluate_cards.document.options를 trace·처리 기록·단계 결과가 같은 정비 진단 표시 계약으로 읽는다. 4,000시간 패키지·누적 12,000시간 정비 차례·리턴 필터 미확인을 당시 근거 그대로 보여 주며, 보류 당시 평가를 판단 등록·승인·실행·업무 완료로 표시하지 않는다. 미상·조회 오류는 빈 성공이나 재고 0으로 바꾸지 않는다. 공식 Codex 생산자의 shell/문자열 입력도 명령 실행 표시명에 연결하고, 단순 파일 읽기 요청만 문맥 목적을 설명한다. 복합·미등록 명령은 목적 미상이며 정확한 명령 원문을 접힘에 보존한다. 등록된 AnomalyPattern/code 표시명은 일반 화면에서 한국어로 읽고 당시 원문 설명은 전량 접힘에 남긴다. ProcessGPT의 PgToolStep/EventTimeline 및 ontology-studio의 등록 표시명·원문 구분을 참고했으며 CSS·색상 변경은 없다.

기존 화면 부정 검증 2실패는 delegated-review-20261012/pm-deferral-ui-before.log에 보존했다. 새 기록 fragment 시험의 최초 1실패는 실제 .cr-step wrapper가 시험 DOM에 없어 본문 CSS가 감춘 준비 오류였다(pm-deferral-ui-focused-first.log); 새 fixture 준비를 실제 DOM 구조로 맞추고 기대값을 유지했다. 새 5시험 및 기존 정비·공개 도구 요청/반환·교차 실행 키·실패 trace·A 승인 묶음은 46 passed, 136.90초(pm-deferral-ui-final.log). 저장된 실제 B를 독립 Chromium에서 렌더한 1440/1024 화면은 pm-deferral-ui-fixture/에 보관했다. 이는 저장 근거 표시 검증이며 현재 운영 재평가·실시간 재실행 증거가 아니다. 운영 B/C/지식 이력의 후속 GET 캡처는 root가 새 source manifest로 수행한다. 최초 실패 및 phase1 manifest는 보존하며 새 제품 6파일 SHA는 pm-deferral-ui-source-sha.json이다.

캡처 driver는 실제 단계 li의 [data-cr-toggle] .cr-title > b만 선택한다(제목이 없는 간격 행은 단계가 아님). --cases B C로 이미 확보한 A 스크린샷을 반복하지 않고 B/C 및 지식 이력을 이어서 확보할 수 있다. 4,000/12,000·미확인 부품·읽기만/쓰기 차단·현재 source SHA·문서 폭·통신 오류·모든 사례 불변 검사 조건은 그대로다. root 전용 실행 준비물은 pm-deferral-ui-capture-plan.json이며 본 에이전트의 운영 HTTP·워커·compose 호출은 0회다.
