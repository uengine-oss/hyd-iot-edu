# 포털 잔여 UI 검증 — 2026-10-12

범위는 NOW U5·U6·U9~U15와 U17~U21 학생 동선에 필요한 화면이다. 실제 스택은 메인이 독점하고 이 기록의 시험은 독립 API/브라우저로 진행했다. 코드·시험 기대값·실제 실패를 구분하고 최종 사용자 시각 판정은 따로 남긴다.

## 조사

- 실제 계약: NOW, UIUX, UIUX_PLAN, ui-design-contract와 DECISIONS 112를 읽었다. 승인하지 않으면 대기, 거절하면 처리 없이 닫기, B/C는 업무 시스템에서 끝내는 흐름을 유지한다.
- 참고: 루트 `.evidence/portal-20261011/refs/process-gpt-vue3`의 PgAlert, 기존 읽은 PgField/PgCard 및 WorkItem/InstanceOutput; ProcessGPT 모노레포 README; ontology-studio README. 오류는 카드 안 알림, 입력은 의미 단위로 묶고 원문·심화 정보는 펼침으로 유지한다.
- U13 조사: app.js refreshSlow가 HTTP 성공 응답을 목록 검증 없이 state.incidents에 대입해 객체 응답이면 filter에서 깨진다. hitl.js의 조치 방법 편집은 저장된 draft.fields 검증 없이 Object.keys를 호출한다. 재현 시험으로 응답 오류와 잘못된 저장 초안을 구분할 예정이다.

## 변경·검증

제품 수정과 독립 Chromium 시험을 진행했다. 실제 스택·LLM 학생 완주 결과는 메인 검증 기록과 구분한다.

- U5·U12: 지령 전후 값을 팬/부하 지령으로 표시하고 단계에 붙지 않은 이전 조치 영향 확인·되돌리기 사건도 기록에 포함한다. 실행자·역할·사유·실패를 표시하며, 영향 확인을 실제 되돌림으로 표현하지 않는다. 도구 실패 시도를 성공 기록과 구별한다.
- U6·U15 일부: 관측 시계열 조회 오류와 스킬 파일 기록 실패를 기존 처리 기록에서 숨기지 않는지 시험했다. 구 회차 입력 스냅샷이 없으면 현재 값을 그 회차 입력으로 표시하지 않고 별도 펼침으로 구분한다. 실제 워커 한국어·근거 제한은 백엔드 담당 범위다.
- U9: 학생이 가져온 단일 흐름 삭제와 대기 중 시스템 단계 취소를 연결했다. 담당자·사유 검증, 서버 실패 시 입력 보존, 중복 제출 차단, 진행 중 삭제 거절, 기술 취소와 성공의 구별을 유지한다. 그래프 정리 재시도 응답을 완료로 숨기지 않는다.
- U10: 정의의 역할명·입력칸 이름을 처리 기록과 승인·결과에 연결한다. 공통 who의 기존 fallback 계약은 유지한다. KPI 사유의 알려진 내부 표·열 이름은 업무명으로 표시하고 원천 API 값과 계산 근거는 그대로 둔다. 지식 지도는 규칙 annotation/title을 이름으로 읽는다. 모든 미등록 이름의 자연어 표시를 완결했다고 주장하지 않는다.
- U11: B 정기 점검/C 재고 보충 승인 카드에는 실제 업무 값만 표시한다. 구매 수량·금액·납기 여유와 정비 누적 시간·주기·부품 수량을 분리하며 설비 예측값을 끌어오지 않는다. A 화면은 감지기의 실제 상태에 따라 복원→준비→재주입 순서를 안내한다.
- U13: JSON 해석 실패와 목록/설비 응답 형식 오류를 정상 빈 응답으로 바꾸지 않는다. 경보 마지막 유효 목록을 보존하고 오류를 표시한다. 손상된 저장 초안은 저장을 막고 사용자가 폐기를 확인하기 전 원문을 유지한다. 10월 11일 skills 캡처의 스택 없는 null 오류는 원인을 확정하지 않았으며, 이번에는 저장 초안 fields와 background plant.units null을 각각 재현했다.
- U14: 서버가 제공한 업무 규칙 목록·본문·연결 키를 읽고 만들기/수정/해제에 연결했다. 미등록 키는 임의 초기화하지 않는다. 실제 FastAPI/MemoryRepo로 저장·다시 읽기·규칙 변경/해제·실패 입력 보존을 시험했다.

## 브라우저와 참고 화면

`tests/test_portal_remaining_ui.py`는 실제 index·전체 CSS·탭 이동 코드와 제품 렌더 함수를 Chromium에서 읽는다. 일부 비공개 함수 export만 시험 메모리에서 붙이며 제품에 시험 전용 API를 추가하지 않는다. API가 필요한 조작은 실제 FastAPI TestClient로 연결하고 오류는 HTTP/저장소 경계에서 주입한다. 기록용 합성 fixture와 실제 엔진 API 시험을 구분한다. 1440/1024px 캡처에서 문서 수평 넘침과 pageerror를 확인한다.

증거는 루트 `.evidence/portal-20261012/ui/`에 있다. agent-work-rules, flow-delete-denied, pending-system-close, record-effects, older-task-current-values, business-po_create, business-wo_create의 두 폭 PNG를 남겼다. 실제 생산 CSS·탭 제목이 적용된 화면을 육안으로도 확인했다.

`reference-comparison.html/png`는 Dify 공식 History and Logs 문서의 기존 실제 캡처와 HYD 독립 기록 화면을 나란히 둔다. 합성 제품 시안을 만들지 않았다. 원출처는 https://docs.dify.ai/en/guides/workflow/debug-and-preview/history-and-logs 이며 기존 `.evidence/a121/refs/SOURCES.txt`와 원본 PNG를 보존한다. 비교 HTML의 첫 PowerShell 파이프 생성본에서 한국어가 물음표로 바뀌어 UTF-8 직접 쓰기로 재생성하고 문자열·이미지 로딩 검증 후 다시 캡처했다.

ProcessGPT Vue 최신 HEAD를 `git ls-remote`로 확인한 값은 `867e8cf944b265a3383e442a48710ff66e1ab3c9`로 기존 참고 clone과 같다. 위 소스와 ontology-studio의 작업 맥락을 참고했으며, 독립 HYD 캡처를 ProcessGPT 실행 화면으로 주장하지 않는다.

## 시험 기록과 한계

- 최초 남은 UI 시험 15개 통과(25.52초), 앞선 기존 승인·흐름 묶음 29개 통과(42.06초).
- 이후 KPI 표시 시험을 추가한 묶음은 31 passed/1 failed(65.87초). 새 helper 삽입 누락을 실제 브라우저가 검출했고 제품 함수를 추가했다. 실패 로그 `pytest-portal-ui.log`를 보존했다. 최종 재검증은 별도 로그에 남긴다.
- 기존 관련 회귀 묶음은 47 passed/1 failed(8.05초). `test_capstone_g7_card.py:36`은 승인 담당 역할의 내부 ID 표시를 기대하지만 U10 구현은 정의의 실제 역할명을 표시한다. 기존 시험 기대값은 바꾸지 않았고, 통과를 위해 내부 ID 접기를 넣는 수정도 남기지 않았다. 메인에게 요구 충돌을 보고했다.
- 이후 사용자가 통상 구현 판단을 위임하고 메인이 계약 갱신을 지시했다. G7 시험에 실제 repo의 인물 목록을 주입하여 이름·정의 역할명 표시와 API 원래 식별자 보존을 검증하도록 갱신했다. 서로 다른 두 사건의 승인자·선택, 현재 값 오염, 첫 사건 재렌더까지 추가해 기존 문자열 한 개를 바꾸는 데 그치지 않았다. 첫 시험 helper에서 Node VM lexical UI 접근을 잘못해 7 failed/42 passed가 발생했고 helper 접근을 고쳐 재검증했다. 제품을 기대값에 맞춰 되돌리지 않았다.
- 최종 UI 묶음: `python -m pytest tests/test_portal_remaining_ui.py tests/test_portal_approval_ui.py tests/test_portal_flows_ui.py -q --tb=short` → **32 passed, 69.30초, exit 0**. 로그 `ui/pytest-portal-ui-final.log`.
- 최종 관련 기록 회귀: `python -m pytest tests/test_capstone_g7_card.py tests/test_u1_task_detail.py tests/test_a161_trace_gaps.py tests/test_live_leftovers_cards.py tests/test_b5_portal.py tests/test_failed_attempt_trace.py -q --tb=short` → **49 passed, 4 warnings, 9.82초, exit 0**. 경고는 FastAPI on_event 폐기 예정 안내. 로그 `ui/pytest-record-regression-final.log`; 앞선 실패 로그도 보존.
- `git diff --check` 오류 없음. 수정한 14개 JS 자산의 index cache 버전을 `20261012-remaining`으로 갱신했다.
- U17~U21의 독립 UI 조작은 일부 확인했지만 실제 워커·외부 모델·전체 학생 완주 및 최종 사용자 시각 판정은 이 기록만으로 완료 처리하지 않는다. 실제 스택 화면은 메인의 별도 캡처 범위다.

## 전역 병렬 시험에서 발견한 폴링·승인 경합

메인의 새 가상환경 전체 시험에서 1 failed/2206 passed/17 skipped가 발생했다. `test_browser_delay_keeps_approval_open_and_accepts_approval[c3_spare]`에서 중복 클릭 직후 거절 버튼이 사라졌다. load()가 instance/task GET을 기다리기 전에 I.view/I.taskView를 null로 지워, 이 사이 기존 버튼의 동기 재렌더가 불완전한 상태를 읽는 제품 결함이었다. 기존 통과한 독립 32개 결과만으로 이를 무시하지 않았다.

- 제품은 마지막 완성 view/taskView를 응답 대기 동안 유지하고 응답 완료 시 교체하도록 수정했다. instances.js 캐시 키는 `20261012-remaining2`다.
- 새 회귀는 두 GET을 각각 의도적으로 보류한 뒤 같은 이벤트 루프에서 두 번 클릭한다. 두 버튼 잠금·입력 유지·POST 한 번·실제 승인 결과를 원래 계약 그대로 확인한다. timeout이나 기존 기대값을 완화하지 않았다.
- 저장된 제품은 변경하지 않고 시험 로더 메모리에서 선초기화 동작만 복원한 `reproduce-original-poll.py`로 **두 경로 모두 동일 null.disabled 실패**를 재현했다(2 failed/11 deselected, 5.71초). 이 진단 실패는 의도적 원인 입증이며 최종 성공으로 세지 않는다.
- 수정 후 새 가상환경 `pytest tests/test_portal_approval_ui.py -q -n 4 --tb=short`: **13 passed, 20.16초**.
- 승인·잔여 UI·흐름 브라우저 세 파일 `-q -n 4 --tb=short`: **34 passed, 32.77초, exit 0**.
- 근거는 루트 `.evidence/overnight-20261012/pytest-original-race-proof.log`, `pytest-approval-race.log`, `pytest-ui-race-final.log`다. 전체 회귀 재실행 및 실제 스택 최종 캡처는 메인이 수행한다.

## 마지막 표시 이름과 상세 캡처 보완 (Sol 6.1)

기존 변경을 보존하여 흐름 목록의 중복 내부 ID를 상세로 이동하고, 지식 지도에서 이름이 없는 Process 노드에 실제 등록된 정의 이름을 연결한다. 기준 이름은 정의 JSON과 학생 BPMN의 실제 이름만 사용한다. 사용자 후속 지시에 따라 미등록 옛 시험 ID는 기본 지도에서 ‘이름 미등록 흐름’으로 누락 상태를 보이고 선택 상세의 접힌 식별자에서 원문을 보존한다. 이름 API 조회 실패는 ‘흐름 이름 확인 불가’와 오류 사유로 구분하며 다시 읽기에서 재시도한다. 누락 이름을 지어 번역하거나 원문을 지우지 않는다.

ProcessGPT 모노레포 README의 프로세스 정의/실행 분리, Vue PgCard/WorkItem의 제목과 상세 분리, ontology-studio README의 그래프와 문서 원천 구분을 다시 읽었다. UI 원본 변경과 실제 스택 재배포는 분리한다. 라이브 실행은 메인 잠금 소유자가 담당한다.

실제 상세 캡처의 조치 방법 선택자는 `#skillList .item`/`#skillDetail`이다. agents 내부 스킬 선택자를 쓰던 계획은 정정한다. 매뉴얼 원문과 등록 이력은 기본 접힌 details이므로 DOM 준비 후 열고 실제 원문 링크/행을 확인한다. 학생 이름 공간 없음은 기준 지도로 대체하여 통과시키지 않는다. 최초 실패 증거는 그대로 보존하고 별도 final 디렉터리로 재캡처한다.

- `ui.js`, `enterprise.js`, `flows.js`, `agents.js`와 index의 해당 cache 키를 `20261012-names`로 갱신했다. 실제 등록 이름이 있으면 기준 매핑보다 우선하고, 등록 이름 변경은 다시 읽기로 반영된다. 이름 조회 실패에서 미등록으로 단정하지 않는다. 원문 질문과 답변의 `read_rows`, `meeting_id` 등 실제 인용은 수정하지 않았다.
- 에이전트 배정 목록의 `read_only`는 역할 값이 아니라 실제 등록 정의명 `read_only 정규화 시험 (A148-53)` 안의 기술 용어였다. 처음 추가한 해당 시험명 하나만의 명칭표 변환은 메인 최종 검토에서 특정 시험 데이터에 맞춘 변경으로 지적되어 제거했다. `stepLabel`의 정의명 변환과 근거가 없던 역할 값 변환도 제거했다. 사용자 저장 정의명은 원문대로 보존하며 이 옛 이름의 외국어 잔여를 한계로 기록한다. 기준 정의 ID의 국문 매핑과 실제 등록 이름 조회는 유지한다. 제거한 JS의 cache 키는 `20261012-names2`다.
- 이름 연결/실패/복구와 식별자 상세 보존 2개 Chromium 회귀를 추가했다. 첫 시험은 harness의 fmt 중복 선언/P 누락, 두 번째는 비활성 탭 클릭 대기로 실패했고 fixture 설정을 바로잡았다. 실패 로그 `pytest-ui-names-first.log`, `pytest-ui-names-second.log`를 보존한다. 제품 조건을 완화하지 않았다.
- 이름 누락 표시 후속 지시까지 적용한 최종 세 파일 회귀 `pytest tests/test_portal_remaining_ui.py tests/test_portal_flows_ui.py tests/test_portal_approval_ui.py -q -n 4 --tb=short` → **36 passed, 33.07초, exit 0**. 근거 `.evidence/overnight-20261012/pytest-ui-names-complete.log`. `git diff --check` 오류 없음. 이전 전체 2275 통과 이후 변경은 UI와 UI 시험이며 전체 회귀를 무한 반복하지 않았다.
- 위 36개 통과 뒤 특정 시험명 변환을 제거한 최종 검토 반영본은 에이전트 설정·등록 흐름명/실패/복구·식별자 상세 3개 관련 Chromium 시험 **3 passed, 15 deselected, 5.99초, exit 0**다. 로그 `pytest-ui-name-review.log`. 해당 시험명을 기대값으로 고정한 시험은 없었으며, 일반 이름 연결·오류·원문 보존 검증을 그대로 통과했다. 36개 결과는 제거 전 범위이며 제거 후 전체 재실행으로 과장하지 않는다.
- 별도 `.evidence/overnight-20261012/target-capture-final.py`는 조치 방법·매뉴얼 준비 조건, 요청 원문 로그·health_state 및 고정 헤더 아래 스크롤을 보완했다. 기존 script/실패 PNG/JSON은 그대로 보존한다. no-cors health의 broad interception 영향을 비교하도록 기본 interception 범위를 제한하고 `--intercept-all`도 제공한다. 이 작성자는 실제 스택 실행을 하지 않았으며 건강 확인의 ERR_ABORTED 원인을 확정하거나 성공으로 숨기지 않았다. 실제 후속 결과는 메인 실행 로그가 기준이다.

### 실제 health 요청 CDP 진단 (메인 허용한 GET만, Sol 6.1)

메인의 `target-capture-final/checks.json`은 7개 기능 준비 조건 모두 true·문서 overflow false다. 시스템/에이전트/질문/학생 지도 캡처에는 health 3개 요청의 `ERR_ABORTED`가 남아 있어 strict summary를 임의 통과시키지 않았다. `requests.json`에서 GET/HEAD/OPTIONS 외 요청은 없었다. 46개 화면 콘솔 검사와 이 요청 실패 계측은 범위가 다르다.

메인이 건강 확인의 독립 GET 진단을 허용한 뒤 `cdp-health-probe.py`로 Chromium CDP Network.requestWillBeSent/responseReceived/responseReceivedExtraInfo/loadingFailed를 같은 requestId별로 보존했다. 학생 지도를 재선택하거나 업무 데이터를 변경하지 않았다. 검사 브라우저는 7.78초 후 닫았다. 근거 `.evidence/overnight-20261012/cdp-health-probe/{events,result,errors}.json` 및 `cdp-health-probe.log`.

- Grafana `:3000/api/health`, Neo4j `:7474/`, Redpanda `:9644/v1/status/ready`는 네트워크 응답 200 뒤 `Fetch`, `net::ERR_ABORTED`, `canceled=true`를 기록했다. blockedReason/corsErrorStatus는 없었다. broad routing을 사용하지 않은 독립 요청에서도 재현됐다.
- 세 URL의 직접 `fetch(mode:'no-cors')`는 **모두 resolve**되었고 response.type=`opaque`, status=0, body=null, 읽은 text는 빈 문자열이었다. 소요는 10.4/19.1/11.2ms로 4초 AbortSignal timeout과 무관하다. 생산 코드도 같은 요청을 연결 성공으로 받아 health_state=`up`, 화면 ‘서비스 12/12’였다. console/pageerror는 0이다.
- 실제 반환값과 동일 requestId의 CDP 이벤트에 근거하면 취소 지점은 opaque 응답의 접근 불가능한 본문 처리다. 제품 코드와 분리한 직접 요청에서도 같은 결과이므로 이 증거에서 제품 JS 실패·실제 연결 실패·CORS 거절은 확인되지 않았다. Chromium 내부의 정확한 취소 분기를 소스 디버거로 확정한 것은 아니다. opaque의 status 0/ok false는 HTTP 서버 실패의 0과 구분한다. 실제 HTTP status를 검증하는 인증·본문 기반 건강 확인으로 확장했다는 뜻도 아니다.

최초 실패 JSON과 final strict summary 및 검사기 expectation은 변경하지 않았다. 기능 준비/콘솔/레이아웃 성공과 health 본문 취소의 별도 진단을 함께 인계한다.

### 최종 SVG 경계 초과 판정 (GET만, 변경 없음)

`ui-f21-final/layout.json`의 SVG/자식 경계 초과 12건은 지식 지도 내부 스크롤 내용이다. 실제 Chromium 1440/1024px에서 map 폭 1111/711px, 내용 폭 1354px, 높이 646px·max-height 648px·overflow X/Y auto를 확인했다. 가로 스크롤 243/643px로 오른쪽 끝 열의 ‘외기 온도’에 이동하여 실제 클릭→선택 상세 제목→키보드 Enter 해제를 확인했고 노드 전체 경계가 map 안에 들어왔다. 문서 폭은 viewport와 같고 실제 문서 높이는 900px였다. 캡처의 10,731/10,804px 높이는 `scripts/ui_capture_all_tabs.py:24`의 UNLOCK_CSS가 `.onto-map` max-height를 해제하여 내부 세로 내용을 펼친 결과다. 접근 불가 잘림으로 판정하지 않으며 소스 수정은 없다.

ProcessGPT BpmnUengineViewer의 pan/zoom/확대와 ontology-studio OntologyGraphPanel의 pan/fit·선택 상세 원칙을 대조했다. HYD는 native scroll+선택 상세 방식이라는 차이를 유지한다. 전체 지도를 한 화면에 읽기 위해 축소한 것이 아니다. 증거 `.evidence/overnight-20261012/ontology-scroll-probe/{result.json,rightmost-selected-1440.png,rightmost-selected-1024.png}` 및 로그. PNG는 오른쪽 열 이동 후 키보드 선택 해제 시점이며 선택/상세 성공 값은 JSON에 별도로 보존했다. pageerror 0, 업무 쓰기 0, 브라우저 종료 확인.
