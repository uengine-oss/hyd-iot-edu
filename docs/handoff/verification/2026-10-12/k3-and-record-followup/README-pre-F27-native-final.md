# 처리 기록·회의 연결 계약 후속 작업

2026-10-12. 이전 2673개 전체 시험과 phase2 GET203항목은 해당 판본의 증거로 보존한다. 실제 PNG 재검토에서 구매 처리 기록의 `purchase-part` 미등록 오류, 넓은 정비 입력의 텍스트 겹침, 보류·대체된 단계가 실행 중으로 설명되는 결함을 발견했다. 기존 자동 검사가 이 의미·가독성 오류를 검출하지 못했으므로 UIUX 완료 근거로 사용하지 않는다.

## 변경 전 수용 기준

- 구매 판단의 실제 생산자가 내보내는 경로를 처리 기록 소비자가 명시적으로 읽는다. 미등록 경로의 오류는 계속 드러낸다. 전체 기록·과거 판단·현재 승인 및 실제 발주·입고 값을 보존한다.
- 1440·1024px에서 긴 정비 입력은 인접 값과 겹치지 않고 전체 내용을 읽을 수 있다. 생략·가림으로 해결하지 않는다.
- 같은 실행의 보류·취소·대체·종료 기록과 현재 작업 상태를 구분한다. 종료한 실행에 진행 중 설명이나 회전 표시를 붙이지 않는다. 아직 수행 중인 다른 실행을 보류로 오표시하지 않는다.
- 회의 예시는 등록한 Google MCP 도구의 실제 입력·반환 계약에 맞는 새 가져오기 파일을 준비한다. 원래 예시를 보존하고 필수 일정·회의실·참석자·서버·담당 값 누락은 오류로 알린다. 중복 실행 방지 키는 기존 실행 경로에서 생성한다.
- 인증·외부 실행·사람 검토를 대신했다고 표시하지 않는다. 준비·독립 계약 시험과 인증된 외부 회의 완주를 구분한다.

## 현재 결과와 한계

- 최종 새 UI 계약 [10개 통과](record-ui-final-source-contract.log), 관련 집중 [32개 통과](record-ui-final-shared-affected.log). 이전 판본의 통과 수와 중복 합산하지 않는다.
- 첫 실제 화면 검사 [59항목 중 57개 통과·2개 실패](first-result.json)는 구매 상세의 실제 부품 이름 연결 누락을 드러냈다. 그때의 C 처리 기록에는 당시 AI 추천을 현재 승인 선택으로 덮어 설명하는 오류도 있었다. 원본 PNG·검사 결과를 보존했다.
- 실제 상세 조회의 의존성과 과거 판본 연결을 수정한 뒤 **C 기록·출력만** [21항목 통과](final-c-result.json)를 확인했다. 당시 3후보·대체 공급사 추천과 현재 OEM 승인, 실제 부품 이름, B/C 업무 저장값 불변을 구분한다. 이미 통과한 B 화면은 다시 실행하지 않았다. 전체 회귀·LLM·업무 재완주0이다.
- [B 긴 값](first-B-record-1440.png), [보류 단계](first-B-step-07-1440.png), [C 당시 추천](final-c-C-historical-agent-1440.png), [C 구매 상세](final-c-C-task-output-1440.png), [참고 화면과 나란히](reference-comparison.html)를 보존했다. 1440·1024px 양쪽을 확인했지만 전체 UIUX의 사용자 시각 승인은 아니다.
- 넓힌 집중 검사 [60통과·2실패](record-ui-final-affected.log) 중 새 시험 배치 실수는 수정 후 위 최종 계약으로 확인했다. 기존 `test_portal_failure_states_ui.py:206`은 옛 `tool:read2` 키를 요구한다. 현재·수정 전 HEAD가 동일한 작업/실행별 키와 실패 상태를 반환함을 [독립 대조](record-ui-baseline-proof-final.log)로 확인했다. 기존 시험과 기대값은 바꾸지 않았으며 관련 시험 전체 통과라고 쓰지 않는다.
- 회의 준비 [27개 통과·Authlib 폐기예고1](k3-pytest-final.log). 실제 가져오기 검사·typed 입력·반려 분기·MCP 도구 스키마·재시도 실행 키를 확인했다. 원래 예시는 불변이고, 실제 등록명이 없어 실행용 사본은 생성하지 않았다. 외부 인증·자료 접근·실제 초대와 응답은 미검증이다.
- **F27은 열림**이다. [읽기 전용 생산·소비 조사](tool-output-consumer-audit.json)에서 긴 dict/list가 worker의 `repr(value)[:4000]` 미리보기로 변하고 화면이 JSON으로 읽지 못해 ‘결과 기록을 확인할 수 없습니다’라고 쓰는 첫 어긋남을 확인했다. 실제 C 평가·제출과 B 정비 도구의 원문은 `full_output.stored=true` 등 저장 메타데이터·참조가 있다. 이 조사에서는 전체 원문을 조회하지 않았으므로 업무 의미를 복원하거나 원문 성공을 주장하지 않는다. [변경 전 명세](F27-spec.md)까지 준비됐으며 구현·시험·실제 화면 해소는 별도다.

최초 조사 뒤 루트가 저장 원문9개를 기존 보호 GET으로 읽었고 문서 갈래에서도 길이·event/storage SHA·`cut=false`와 JSON을 독립 확인했다. [작은 원문 검증 요약](F27-actual-stored-payload-proof.json)과 [실제 envelope 의미](F27-actual-stored-payload-semantics.json)를 보존한다. B 판단은 `NO_FEASIBLE_OPTION`/추천없음, C 구매는 당시 `EVALUATED`·`SUBMITTED`/`skill:sop-pur-12`이며 현재 OEM 승인·발주와 구분한다. 최초 audit의 미조회 기록을 고치지 않고 뒤의 읽기 결과를 덧붙인다. F27 소비자 구현·새 판본 집중 시험·실제 화면 해소는 여전히 별도다.

## F27 최종 문서 준비 시점 — 아직 실제 화면 해소 아님

[backend 진행](F27-backend-progress.json)은 typed 미리보기 생산·`output_truncated` 명시와 집중22통과(4.11초), [같은 원문 공유1통과](F27-backend-shared-origin.log)(1.17초)를 별도 실행으로 기록한다. 기존 원문·case 소유권을 유지한 공유이며 다른 task에서 같은 원문을 썼다는 이유로 실제 실패로 만들지 않는다. [옛 repr를 의도적으로 복원한9실패](F27-backend-negative.log)는 부정 검사가 원래 결함을 잡는 증거다.

기존69개 관련 시험은 [처음67통과·2실패·3경고](F27-backend-regression.log)(9.64초), [UTF8 환경 보완 뒤 원문fold1통과·VM1실패](F27-backend-regression-utf8.log), [VM 단독 load1통과](F27-backend-ui-load-followup.log)(0.27초)로 분리한다. 첫 실패·UnicodeDecodeError/PytestUnhandledThreadExceptionWarning 등을 지우지 않는다. 한 실행에서69개 모두 통과한 것처럼 쓰거나 신규23·기존69·앞선10/32와 겹쳐 합산하지 않는다.

`F27-ui-first/second/third/fourth.log`와 `F27-ui-vm-load.log`는 중간 오류·수정/중단 이력이다. 새 mounted 시험의 빈 workitems 배치는 harness 문제로 구분하며 제품의 빈 성공·폴백을 만들 근거가 아니다. 최종 안정 판본의 UI 시험·root 실제 GET/캡처·source SHA·업무 불변 확인 전에는 F27 해소를 선언하지 않는다. [복사 SHA 원장](final-preparation-evidence-provenance.json)은 이 준비 시점의 파일을 그대로 보존한다.

[실제18:59 KST 읽기 전용 상태](runtime-readonly-followup.json)는 서비스29·LIVE_LOCK없음·8097없음이다. 이 시각 이후 배포/캡처와 최종 실행 상태는 루트의 새 근거로 갱신한다.

## 남은 수용 조건의 정확한 범위

최종 준비의 추가 근거는 [F27별도 소스/증거 manifest](F27-final-preparation-manifest.json)다. frozen UI/backend/시험9개 현재SHA가 모두 일치하고 pre-F27 manifest를 변경하지 않았다. [backend 최종23통과](F27-backend-final-23.log)(7.40초)와 [소스/proof](F27-backend-final-23-proof.json)를 새로 보존한다. 처음22개 원문 로그가 없어 진행 JSON만 남았다는 한계를 기록하며 새 최종23개를 확정 근거로 쓴다.

UI의 [첫집중58통과·1실패](F27-ui-final-focused.log)(151.93초)는 오류 응답에 대한 기존 구체적 업무 문구가 일반 오류 문구로 바뀐 실패를 보존한다. [오류 문구 우선순위3통과](F27-ui-final-error-followup.log)(7.50초)와 [typed text4통과](F27-ui-typed-text-followup.log)(12.08초)는 후속 별도 범위다. 신규59개 한 번 통과나 겹치는 수의 합계로 설명하지 않는다. 실제 파일명은 `F27-ui-final-error-followup.log`이며 별도의 `error-priority.log`는 없다. 이 준비 시점 root native 읽기 전용 캡처 결과·최종source/state 확인 전이므로 F27완료는 선언하지 않는다.

[실라버스/상태 대조](remaining-acceptance-audit.md)와 [원문 좌표·SHA](remaining-acceptance-audit.json)는 최종 XLSX 통합온라인95행이 물리적 복구 성공 자체를 필수라고 쓰지 않음을 확인한다. 실제 A는 미달 경로의 프로세스COMPLETED·`incident_closed=false`이며 과정 실행/처리 이력 실습의 근거다. 수치 기준을 통과했다고 경보해제·복구성공으로 바꾸지 않으며 새 해피패스 완주를 요구하지 않는다. B는 실제 재고/기간 자료에 따라 정상 PENDING, C는 교육용ERP 발주/입고 완료다.

173개 원본/수정본 각각의 번호·관찰·최종SHA를 갖는 정본 쌍 ledger는 기록한 검색 범위에서 찾지 못했다. coverage는 **UNVERIFIED이며0이라고 단정하지 않는다.** 확인한22PNG·46화면·203항목·부분후속은 서로 다른 범위다. 외부 인증과 전체 사용자 시각 인수, 진짜 자료 기반 B 수업준비가 남았으며 이 대조에서 F27 외에 새 확정 제품 코드 결함은 추가하지 않았다. 과거 추출 draft와 현재 설치 정책의 차이는 판본 표시/편집 사용성을 확인할 대상이며 현재 정책 결함으로 단정하지 않는다.

생산자→소비자와 과거/현재 판본 선택 근거는 [원인 기록](record-ui-contract-findings.md), 원본 위치·SHA는 [복사 대조](followup-evidence-provenance.json), 회의 준비 판본은 [K3 SHA](k3-manifest.json)에 있다. 앞선 2673개 전체 시험을 이번 변경까지 통과한 것처럼 확장하지 않는다.

완료 UI6파일·K3·실제 시험 소스와 로그 SHA는 [완료 소스 고정](completed-source-manifest.json)에 있다. 실제 C 최종 캡처 전후 파일 SHA와 같은 판본이며, 이 고정 이후의 F27 구현은 포함하지 않는다. 최종 C의 [저장값 불변](final-c-case-state-proof.json)과 [판본 불변](final-c-source-before.json)/[캡처 후 판본](final-c-source-after.json)을 보존한다.

기존 비교 HTML을 외부 접속 없이 로컬 Chromium에서 렌더링한 [나란한 PNG](reference-side-by-side.png)와 [검증 메타데이터](reference-render-metadata.json)를 추가했다. 이미지4개 모두 로드·참조9개 파일 존재·console0·pageerror0이며 HTML/이미지 SHA를 기록했다. Dify는 보존한 공식 문서 화면, ProcessGPT Vue는 원본 컴포넌트 컴파일 화면이라 전체 앱 동등성이나 사용자 시각 승인으로 확대하지 않는다.

## 실행 명령과 시험 판본

아래는 당시 집중 시험의 실제 명령이다. 10개와32개는 겹치는 파일을 포함하므로 통과 수를 합하지 않는다. 새 전체 시험은 실행하지 않았다.

```powershell
$env:PYTHONUTF8='1'
& D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe -m pytest -q tests/test_portal_actual_record_contracts_ui.py --tb=short
& D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe -m pytest -q tests/test_portal_actual_record_contracts_ui.py tests/test_portal_pm_deferral_ui.py tests/test_portal_purchase_tools_ui.py tests/test_portal_pm_package_scope_ui.py --tb=short
$env:PATH='C:/Program Files/LibreOffice/program;' + $env:PATH
& D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/clean-venv/Scripts/python.exe -m pytest tests/test_google_meeting_mapping_preparation.py -q
```

K3 첫 독립 시험은 partial test가 실제 결과 소비자에 없는 `parsed` 키를 넣어26통과·1실패했다. 실제 `mcp_check.shape_result`의 JSON text 형식으로 시험 입력을 고쳐27통과한 것이다. [첫 실패](k3-pytest-first-failure.log)도 보존하며 Google 호출 성공으로 해석하지 않는다.

## 검증 범위

실제 보존 데이터로 수정 전 실패를 확인하고 영향을 받는 계약·브라우저 시험만 수행한다. 마지막으로 기존 B/C 처리 기록과 해당 단계의 실제 GET 화면만 확인하며 업무·LLM 완주와 전체 회귀를 반복하지 않는다. 원래 실패 PNG와 검사 결과를 삭제하거나 덮지 않는다. 사용자 시각 승인은 여전히 별도다.
