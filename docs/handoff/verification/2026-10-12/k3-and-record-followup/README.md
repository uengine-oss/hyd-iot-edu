# 처리 기록·회의 연결 계약 후속 작업

2026-10-12. **F27 구현·해당 실제 도구 기록 화면 검증을 완료했다.** 기존 B/C를 읽기만 한 [native 최종96항목](F27-native-3-result.json)에서 저장원문 자동조회·검증·업무 의미 소비와 판본/업무 저장값 불변을 확인했다. source807개는 고정/변경0이며 새전체 시험 통과를 뜻하지 않는다. 새LLM·워커/업무 재완주·전체 회귀0이다. U16/U20/F13·외부 회의 인증·전체 사용자 시각 인수와173쌍ledger coverage는 열림/UNVERIFIED다.

## 현재 동작과 실제 확인

큰 dict/list 도구 출력은 typed 축약표시와 `output_truncated`를 내보낸다. 원문·SHA는 보존하며 화면의 표시 행·현재task가 기존 소유권/tenant 보호 chunk GET으로 전체 원문을 자동 조회한다. 길이·SHA·cut/JSON을 검증한 다음 실제 MCP envelope에서 업무 의미를 읽는다. unsafe repr를 eval하지 않으며 조회 실패·손상·잘림·도구 오류를 빈 성공으로 바꾸지 않는다.

최종 native 검사는 Record·Trace·TaskDetail의 실제 semantic 결과, 원문9개 exactbytes, 같은 B/C의 작업/승인/효과·소스 불변, console/pageerror/쓰기시도0을 확인했다. 당시 C 구매A추천·평가/제출과 현재OEM승인은 구분하며 B추천없음/PENDING을 유지한다. 새 워커 생산 경로는 backend최종23으로 검증했고 새 지시 아래 워커/LLM을 실행했다고 주장하지 않는다.

- [C 실제 도구기록1440](F27-native-final-C-record-tool-1440.png) · [1024](F27-native-final-C-record-tool-1024.png)
- [C 당시 제출 원문1440](F27-native-final-C-task-submitted-original-1440.png) · [1024](F27-native-final-C-task-submitted-original-1024.png)
- [B 실제 도구기록1440](F27-native-final-B-record-tool-1440.png) · [1024](F27-native-final-B-record-tool-1024.png)
- [참고 화면과 최신F27 나란히](reference-comparison.html). Dify는 보존 공식문서 화면, ProcessGPT Vue는 원본 컴포넌트 컴파일 화면이며 전체 앱 동등성/사용자 시각 승인으로 확대하지 않는다.

루트는 위 C1440·Ctask1024·B1440 PNG를 직접 열어 부분 시각 확인했다. 전체 앱 시각 인수를 대신하지 않는다. [최소 상태SHA증거](F27-native-final-case-state-proof.json), [최종source807 고정](F27-final-source-manifest.json), [변경0 검증](F27-final-source-verification.json), [범위manifest](F27-final-scoped-manifest.json), [원본 복사SHA](F27-native-final-evidence-provenance.json)를 보존한다. 큰 전체 case응답은 원래H위치에 남기고 최소proof에 출처/파일SHA를 기록했다. pre-F27 [완료manifest](completed-source-manifest.json)와 [F27준비manifest](F27-final-preparation-manifest.json)는 덮지 않았다.

추가 [native 처리 흐름14항목](F27-trace-captures/result.json)은 [B 실제1440](F27-trace-captures/B-latest-native-flow-trace-1440.png)·[C 실제1440](F27-trace-captures/C-latest-native-flow-trace-1440.png)의 도구 의미·source/업무불변·GET전용을 확인했다. [별도 복사SHA](F27-trace-captures/provenance.json)를 보존하며96과 합산하지 않는다. 루트는 두 PNG를 직접 확인했다. B추천가능한 대안없음·4개제외와 C구매판단등록/사람승인·ERP실행의 차이를 읽을 수 있다. C의 긴 compact 요약은 ellipsis가 있어 전체문장이 화면에 펼쳐졌다고 주장하지 않으며 전체대상 DOM text는 `.txt`/result에 보존됐다.

최신 나란한 비교의 [렌더 메타데이터](reference-render-metadata.json)는 이미지6개 로드·참조14개 존재·console/pageerror/외부요청0·1920×2602를 확인했다. 루트가 [최종 비교PNG](reference-side-by-side.png)를 직접 열었으며 이전4이미지 비교는 `reference-comparison-pre-F27.html`·`reference-side-by-side-pre-F27.png`·`reference-render-pre-F27-metadata.json`으로 남겼다.

## 집중 검증과 실패 보존

| 범위 | 실제 결과 | 원문 |
|---|---|---|
| F27 backend 최종 단일실행 | 23통과·7.40초·source불변 | [로그](F27-backend-final-23.log) · [proof](F27-backend-final-23-proof.json) |
| F27 UI 첫집중과 후속 | 첫58통과/1실패·151.93초, 오류문구우선순위3통과·7.50초, typedtext4통과·12.08초 | [첫집중](F27-ui-final-focused.log) · [오류3](F27-ui-final-error-followup.log) · [typed4](F27-ui-typed-text-followup.log) |
| 기존69 관련시험 | 초기67통과/2실패/3경고·9.64초, UTF8후속rawfold1통과/VM1실패, VMload1통과·0.27초 | [초기](F27-backend-regression.log) · [UTF8후속](F27-backend-regression-utf8.log) · [VM후속](F27-backend-ui-load-followup.log) |
| 의도적 legacy repr 복원 | 9실패 expected·2.01초: 부정검사가 원래결함을 잡음 | [부정로그](F27-backend-negative.log) |
| native 첫화면 | 89/96통과·7실패: 숨긴sections와 동적축소nth선택 | [첫결과](F27-native-1-result.json) · [로그](F27-live-native-final-1.log) |
| native 두번째 | assert실패없이61항목뒤 닫힌summary nth timeout, 전체실패 | [두번째결과](F27-native-2-result.json) · [로그](F27-live-native-final-2.log) |
| native 최종 | 96/96통과, 실제UI조작·GET만, source/업무불변·console/pageerror/write0 | [최종결과](F27-native-3-result.json) · [로그](F27-live-native-final-3.log) · [최종driver](F27-live-native-final-driver.py) |
| pre-F27 UI6파일 | 새계약10통과·19.90초, 관련32통과·50.33초, 첫실제57/59→C기록/출력21통과 | [새10](record-ui-final-source-contract.log) · [관련32](record-ui-final-shared-affected.log) · [첫실제](first-result.json) · [C21](final-c-result.json) |
| K3 준비 | 27통과/1Authlib폐기예고·3.51초, 실제OAuth/실행용등록사본0 | [로그](k3-pytest-final.log) · [SHA](k3-manifest.json) |

범위가 겹치는 수를 합산하지 않는다. backend 최초22의 rawlog는 없어서 진행JSON만 보존하고 새최종23을 확정 근거로 쓴다. 기존69는 한실행69통과로 쓰지 않으며 UnicodeDecodeError/PytestUnhandledThreadExceptionWarning 등 초기경고도 남긴다. UI중간실패/중단은 `F27-ui-first/second/third/fourth.log`와 `F27-ui-vm-load.log`에 보존했다. mounted시험의 빈workitems 배치는 harness결함이며 제품폴백을 만들지 않았다. pre-F27 넓힌60통과/2실패의 새queued 시험배치 교정과 기존 `tool:read2` 기대의 수정전HEAD 동일 결과도 [초기범위로그](record-ui-final-affected.log)/[baseline대조](record-ui-baseline-proof-final.log)에 남겼다. 기존 시험 기대값을 바꾸지 않았다.

최초 K3 partial test의 `parsed` 결과형식 오류26/1은 실제 `mcp_check.shape_result` JSONtext 입력으로 고쳐27통과했다. [첫실패](k3-pytest-first-failure.log)도 Google성공으로 해석하지 않는다. 원래 example 파일은 byte불변이며 등록된실제agent/role/Calendar/Drive값이 없어 실행용사본을 만들지 않았다.

## 남은 수용 조건

[최종XLSX/실제상태 대조 당시기록](remaining-acceptance-audit.md)와 [좌표/SHA](remaining-acceptance-audit.json)는 통합온라인95행이 물리복구 성공을 필수라고 쓰지 않음을 확인한다. audit 당시 F27진행중 상태는 그시점 기록이며 현재 해소 판정은 위96/별도14근거다. A미달 프로세스COMPLETED·incident_closed=false는 실제 과정/처리이력 실습근거이며 경보해제·복구성공으로 바꾸지 않는다. B는 진짜 패키지재고/기한 조건에 따라 PENDING, C는 교육용ERP 발주/합격입고/재고 완료다. 성공용자료 생성이나 새해피패스 재완주를 요구하지 않는다.

정본173원본/수정본의 번호·관찰·최종SHA 쌍ledger는 기록한검색범위에서 찾지 못했다. coverage는 **UNVERIFIED이며0이라고 단정하지 않는다.** 확인한22PNG·46화면·203항목·부분후속은 다른범위다. F27해소가 U16/U20/F13·전체수업운영·전체사용자시각인수·K3외부인증을 닫지 않는다. 과거추출draft와 현재설치정책의 차이는 판본표시/편집사용성을 확인할 대상으로 남기며 새확정코드결함으로 단정하지 않는다.

이전2673전체시험은 당시판본에만 유효하다. [source807](F27-final-source-manifest.json)의 scope와 whole_reruns0을 지키며 새변경까지 전체통과로 확장하지 않는다. 프로세스GPT모노레포·ontology-studio는 원문/이력/읽을수있는인터페이스의 참고이며 제품동등성 증거가 아니다. [변경전명세](F27-spec.md), [최초읽기전용audit](tool-output-consumer-audit.json), [후속원문9개검증](F27-actual-stored-payload-proof.json), [당시문서](README-pre-F27-native-final.md)는 그대로 보존한다.
