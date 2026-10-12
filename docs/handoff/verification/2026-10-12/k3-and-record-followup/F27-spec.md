# F27 — 긴 도구 출력의 생산·소비 계약

2026-10-12. **아래는 원인 조사·변경 전 명세를 쓴 당시 기록이다.** 이후 구현·해당 실제native화면96항목과 별도흐름14항목을 검증했으며 최종판정은 [최종범위README](README.md)에 있다. 먼저 끝난 6개 UI 파일의 판본은 [완료 소스 고정](completed-source-manifest.json)에 보존한다. 이 명세 이후의 F27 변경에 앞선 10/32/21 통과를 확대 적용하지 않는다.

## 문제와 의도

큰 dict/list가 `worker.events._truncate`에서 `repr(value)[:4000]`으로 변하면서 JSON으로 해석할 수 없는 미리보기가 된다. 실제 C 구매 평가·제출은 `full_output.stored=true`, `content_type=json`, `cut=false`와 원문 참조를 갖지만 화면 소비자는 `data.output`만 해석해 ‘구매 결과 기록을 확인할 수 없습니다’라고 쓴다. 원문이 없다는 뜻으로 표시하면 보존 사실과 어긋난다. [읽기 전용 원인 조사](tool-output-consumer-audit.json)는 저장 메타데이터와 미리보기를 확인했으며 전체 원문의 업무 의미는 아직 조회하지 않았다.

목표는 원문·SHA·과거 판단을 보존하면서, 미리보기 축약과 실제 실패·원문 부재를 구분하고 검증한 원문에 근거해 읽을 수 있는 결과를 표시하는 것이다. Python repr를 브라우저에서 `eval`하거나 현재 승인·새 판단으로 과거 결과를 대체하지 않는다.

## 생산자와 소비자

- 생산자: `worker.runner`의 원 이벤트 확보 → `worker.payloads`의 JSON 저장·SHA → `worker.events`의 화면 이벤트. 긴 JSON의 새 미리보기는 `{kind:'tool_output_preview', truncated:true, original_chars, content_type:'json'}`와 같이 식별되는 타입 있는 축약 설명을 사용한다. 모든 축약된 출력에 `output_truncated`를 명시한다. 저장 원문은 변경하지 않는다.
- 소비자: `plainWords`의 실제 envelope 정규화 → `trace`, `caseRecord`, `taskDetail`의 도구 결과. `document`, `structured_content`/`structuredContent`, `content` 안 text JSON·배열처럼 서버가 실제 내보내는 모양만 명시적으로 지원한다. 알려지지 않은 형식이나 실제 누락은 오류·미확인으로 드러낸다.
- 과거 출력: 기존 소유자·tenant 확인이 있는 chunk GET으로 원문을 읽는다. 전체 문자 길이·SHA·`cut` 상태를 확인한 뒤에만 JSON 의미를 해석한다. 응답 실패·불일치·잘림·형식 오류를 현재 판단이나 미리보기 추정으로 우회하지 않는다. 읽기 응답이 늦게 오더라도 다른 선택 task/instance의 화면을 덮지 않는다.
- 원문을 아직 읽지 않은 상태: ‘미리보기는 축약됐고 전체 결과가 보관돼 있습니다’처럼 실제 상태를 알린다. 화면에 표시된 행·현재 선택한 task는 원문을 자동으로 읽고 검증하여 업무 의미를 표시한다. ‘원문 열기’를 눌러야만 결과를 이해할 수 있는 동선으로 끝내지 않는다. `stored=true`를 업무 성공으로 해석하지 않으며 성공·실패 요약은 검증한 원문에서만 만든다.

## 수용 기준과 부정 검증

1. 짧은 구조화 결과와 긴 JSON 모두 원문 저장값·SHA가 불변이다. 긴 결과는 repr 문자열을 새 JSON 미리보기인 것처럼 내보내지 않는다. 다른 종류의 축약 출력도 축약 여부가 명시된다.
2. 실제 C 평가·제출 및 B 유지보수 창/PM/판단 결과의 저장 모양을 재현한다. 원문 조회 전에는 보관/축약 상태를 쓰고, 조회·검증 후에는 그 출력의 근거만 요약한다. 빈 cause/후보/응답을 성공 값으로 만들지 않는다.
3. SHA·길이 불일치, `cut=true`, 손상 JSON, 누락된 참조, 조회 실패, 다른 tenant/owner 요청을 각각 거절한다. unsafe repr는 해석하지 않는다. 소비자가 이미 판별 가능한 도구 실패를 성공 문구로 바꾸지 않는다.
4. 현재 OEM 승인과 당시 A 추천·후보3개를 구분하고 B/C 업무 행·작업·승인·효과를 변경하지 않는다. 새 LLM 실행·시나리오 재완주·전체 회귀는 이 수정의 검증 방식으로 사용하지 않는다.
5. 실제 변경을 일부러 제거/손상했을 때 잡히는 집중 시험과 원문 참조 읽기 경로를 검증한다. 현재 열린 F27은 그 검사 및 필요한 실제 화면 확인 후에만 해소 판정한다. 전체 UIUX 사용자 시각 승인은 별도다.

ProcessGPT 모노레포·ontology-studio 참고는 원문과 실행 이력을 구분하고 출처를 남기는 설계 맥락이다. 이 명세는 HYD의 현행 payload 소유권·저장·조회 계약을 사용한다.

## 최초 조사 뒤 실제 원문 확인

루트가 기존 보호 chunk GET으로 실제 B/C 저장 원문9개를 읽었고 길이·event/storage SHA·참조·`cut=false`를 확인했다. [작은 검증 요약](F27-actual-stored-payload-proof.json)과 [원문 envelope 의미](F27-actual-stored-payload-semantics.json)에 기록한다. 최초 audit의 ‘전체 원문 미조회’는 그때의 사실로 보존한다. 실제 B 판단은 `NO_FEASIBLE_OPTION`/추천없음이며 C 구매는 당시 `EVALUATED`·`SUBMITTED`/`skill:sop-pur-12`다. 도구 응답의 `result=ok`를 B 업무 완료·구매 발주 실행으로 해석하지 않는다. 이 읽기는 소비자 구현·새 판본 시험·화면 검증 완료를 뜻하지 않는다.
