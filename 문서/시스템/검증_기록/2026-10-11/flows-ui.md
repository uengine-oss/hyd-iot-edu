# 흐름 가져오기 U4/U7/U8 — 2026-10-11

## 변경과 검증 범위

실제 `flows.js`/`ui.js`/CSS를 Chromium에 올리고 FastAPI `flows_api`를 `MemoryRepo`에 연결했다. 이 기록은 실제 설비·MCP·SMTP·Docker 스택 완주 주장이 아니다.

- 세 참조 BPMN을 파일 입력으로 가져온 뒤 UI에서 경보·부품·역할·에이전트·지시문·메일·보고·분기·기한을 직접 입력, 검사, 등록했다. 저장된 작업 매핑과 분기를 참조 `*.mapping.json`과 정확히 비교한다. 등록 뒤 다시 열어 검사 통과 상태를 확인한다.
- 포털이 새 경보 초안을 가져올 때 `start_patterns: []`를 명시해 아무것도 선택하지 않는다. API 인자를 생략한 기존 호출의 센서 기본값과 `merge_mapping` 기본계약은 그대로 유지한다. 무선택 상태의 검사 거절과 재가져오기 선택 보존을 실제 API·브라우저로 확인한다. 기존 `test_bpmn_import.py` 준비 helper와 B7 기대값은 원본 그대로다.
- 시스템 설정의 false와 중첩 객체를 그대로 보존한다. 객체 자리의 배열 입력은 등록하지 못한다. 부품 변경 뒤 이전 설정이 다른 부품으로 넘어가지 않는지 검사한다.
- CMMS 정비 요청의 기존 실행 옵션 `window_var`/`mail`을 catalog에 노출했다. 엔진/API 의미를 바꾸지 않았다. 세부 메일은 받는 사람·참조·제목·본문 폼, 나머지는 데이터형에 맞는 선택/입력으로 작성한다. MCP 가변 인자·결과 추출처럼 임의 구조가 필요한 값은 객체 입력을 유지한다.
- 검사 실패 중 mapping을 부분 변경하지 않도록 복사본을 완성한 뒤 반영한다. 재렌더마다 쌓이던 이벤트 리스너를 AbortController로 교체하고, 입력 뒤 도착한 오래된 검사 응답을 버린다.
- README의 API 우회 절차를 실제 화면 순서로 교체했다. 연결 값 JSON 파일은 보존했다.

## 참고와 시각 대조

- 최신 ProcessGPT Vue3 clone `867e8cf`: `src/ds/components/PgField.vue`, `PgCard.vue`. 라벨 위 입력, 도움말, 얇은 테두리 카드 및 16px 간격을 적용했다.
- ProcessGPT 모노레포 `README.md`: BPMN과 역할 중심 흐름 관계를 확인. 이 페이지에서 모델러를 새로 만들지 않고 기존 가져오기 계약을 유지했다.
- ontology-studio `frontend/src/shared/ui/CollapsiblePanel.vue`: 필요한 때 펼치는 패널 패턴. 단계의 원시 연결 값은 접기로 보낸다.
- Dify 기존 실화면 `.evidence/a121/refs/dify-history-logs-2.png`를 직접 열어 확인. 화면의 주 정보와 부차 상세를 분리하는 방식을 참고했다. 실행 추적 화면을 흐름 편집기에 그대로 복사하지 않았다.

캡처: 루트 `.evidence/portal-20261011/flow-{cooling-emergency,pm-planning,spare-purchase}-{1440,1024}.png`. 격리된 흐름 컴포넌트 화면이며 포털 전체 셸/라이브 서버 캡처가 아니다. 1024 화면에서 메일 제목과 내용, 비교 연산이 잘리던 부분을 캡처를 읽고 수정했다. 콘솔 오류와 가로 넘침 검사는 보조 근거다. 사용자 시각 승인은 별도다.

## 재현 명령

PowerShell에서 `PYTHONUTF8=1`, PATH 앞에 `C:/Program Files/LibreOffice/program`, 선택적으로 `FLOW_UI_EVIDENCE=D:/work/study/hyd-iot-edu/.evidence/portal-20261011`를 설정한다.

`D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe -m pytest tests/test_portal_flows_ui.py -q`

첫 기능 검증: 4 passed (8.46s). 최종 캡처 및 회귀 결과는 후속 줄에 기록한다.

최종 결과: `tests/test_portal_flows_ui.py tests/test_bpmn_import.py tests/test_student_reference_flows.py` → **44 passed, 1 skipped (15.70s)**. 건너뜀은 별도 빈 PostgreSQL DB용 `HYD_FLOW_PG_DSN` 미지정. 로그 `flow-tests.log`.

캡처에서 공통 `UI.who()`가 서로 다른 에이전트 이름을 모두 “AI 에이전트”로 바꾸는 회귀를 발견했다. 선택 목록은 catalog의 명시 이름 `a.name`을 우선하도록 수정하고 A/B/C 각각 선택된 에이전트 이름 assertion을 추가했다. 최종 Chromium 재실행 **5 passed (17.64s)**, 로그 `flow-ui-tests.log`, 여섯 캡처 갱신. 역할 미선택 등록 거절→선택 후 통과, 폼 이름 보존 및 재열기 후 false/중첩 객체 보존도 포함한다.

## 추가 증거: 실제 ProcessGPT 컴포넌트 렌더와 나란히 비교

사용자 요청에 따라 참조 레포 `867e8cf`의 실제 `PgField.vue`·`PgCard.vue`·`PgAlert.vue`와 의존 컴포넌트를 별도 최소 Vue/Vite harness에서 **직접 import해 컴파일**했다. 원본 `src/ds/styles/tokens.css`와 MDI 폰트도 로드했다. 컴포넌트 CSS를 복제하지 않았으며 harness 자체 CSS는 바깥 배치만 담당한다. 전체 ProcessGPT 앱 화면이 아니라 컴포넌트 렌더이며 입력 내용·배치는 비교용 fixture다.

- [나란히 비교 HTML](D:/work/study/hyd-iot-edu/.evidence/portal-20261011/flow-processgpt-comparison.html)
- [나란히 비교 PNG](D:/work/study/hyd-iot-edu/.evidence/portal-20261011/flow-processgpt-comparison.png)
- [참고 컴포넌트 1440](D:/work/study/hyd-iot-edu/.evidence/portal-20261011/flow-reference-components-1440.png) · [1024](D:/work/study/hyd-iot-edu/.evidence/portal-20261011/flow-reference-components-1024.png)
- [실제 포털 CMMS 설정 카드](D:/work/study/hyd-iot-edu/.evidence/portal-20261011/flow-cmms-card.png)
- 재현 소스: 루트 `.evidence/portal-20261011/pg-components-harness/`의 `App.vue`, `vite.config.js`, `package-lock.json`; 캡처 스크립트 `capture-flow-reference.py`.

Chromium 콘솔 오류 0. 실제 참고 컴포넌트 캡처와 나란히 비교 PNG를 직접 열어 확인했다. 라벨 위 입력·얇은 테두리·카드 여백을 적용했고, 제품에서는 긴 메일 본문을 전체 폭으로 표시하고 원시 연결 값을 접는다. 포털 공통 파란색 토큰과 흐름 전체 검사 영역은 유지했다. 제품 코드나 기존 테스트는 이번 증거 작업에서 변경하지 않았다. 최소 harness 서버는 캡처 뒤 종료했다.


## API 호환성 수정 — 전체 회귀에서 발견한 B7 결함

초기 구현은 `merge_mapping`의 모든 신규 경보 기본값을 빈 목록으로 바꿔 B7의 기존 센서 기본값 계약을 깨뜨렸다. `tests/test_b7_oil.py::test_catalog_offers_the_human_input_pattern_but_message_default_stays_sensor` 실패를 확인하고 기대값을 바꾸지 않고 제품을 수정했다.

- `merge_mapping` 센서 기본값을 원상복구했다. `test_bpmn_import.py`에 임시로 추가했던 준비 helper 수정도 제거했다(해당 파일 git diff 없음).
- `ImportReq.start_patterns: list[str] | None`을 호환 선택 인자로 추가했다. 생략/None은 기존 기본값, 명시한 배열은 **처음 가져온 경보 초안**에만 적용한다. 포털은 []를 보내고 사용자가 직접 경보를 고른다.
- 재가져오기는 새 요청의 배열보다 저장된 선택을 우선한다. 사람 입력 시작의 종류도 바꾸지 않는다. 모르는 경보 패턴은 기존 검사기가 거절한다.
- 새 `tests/test_flow_import_start_selection.py`: 기존 생략 호출, 명시 빈 배열, PM_DUE 선택, 기존·선택·빈 초안의 재가져오기 보존, 사람 입력 시작, 미등록 패턴 거절 검증. 세 참조 흐름 Chromium 테스트에도 실제 파일 재가져오기 후 체크 보존을 추가했다.

최종 관련 검사: `tests/test_flow_import_start_selection.py tests/test_portal_flows_ui.py tests/test_bpmn_import.py tests/test_b7_oil.py tests/test_student_reference_flows.py` → **73 passed, 1 skipped (13.55s)**. 기존 B7 기대값 수정 없음. 로그: 루트 `.evidence/portal-20261011/flow-start-compatibility-tests.log`. 전체 회귀가 이미 변경 전 코드를 수집했으므로 최종 전체 회귀는 메인에서 재실행한다.
