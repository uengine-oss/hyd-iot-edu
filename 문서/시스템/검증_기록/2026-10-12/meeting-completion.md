# K3 회의 예제 계약과 실제 완료 — 2026-10-12

Sol 6.1 작업. 실제 Google 인증·메일 발송·일정 생성은 루트가 담당한다. 예제의 가상 회사·example.com·Drive 링크와 단위 시험을 실제 Google 완료 증거로 사용하지 않는다.

## 조사와 변경 범위

- `example_meeting/README.md`, `mapping.json`, SKILL, D1~D3, `google_mcp.md`, `test_capstone_kit.py`, importer와 typed extract를 대조했다. 가져오기 거절 세 줄은 강사가 실제 서버 결과 경로를 채우는 의도된 placeholder이며 제품 결함이 아니다.
- 결과 경로를 채워 구조 검사를 통과하는 것과 실제 서버의 입력 계약 검증은 다르다. 일정 생성에 필요한 종료 시각·시간대·캘린더·참석자·회의실·첨부는 선택 서버의 실제 inputSchema로 정해야 한다. 원본 mapping의 `start/room/attachments`를 일반 Google 계약으로 단정하지 않는다.
- `mcp_check.call`/`call_effect`는 실제 tools/list를 재조회하지만 입력 schema를 검증하지 않고 호출했다. 루트가 이 공유 파일의 사전 JSON Schema 검증 수정을 승인했다. 실제 도구 호출 전 실패하도록 수정하고 읽기 판정·승인 후 효과·idempotency를 유지한다.
- ProcessGPT 모노레포 README의 BPMN·감사·보상 구분과 ontology-studio README의 스키마·추출·Neo4j 저장 구분을 참고했다. HYD 지식 자료와 실제 Google 동작을 동일시하지 않는다.

## 외부 전제와 잔여

실제 Google MCP 서버 선택/등록·인증, 도구 목록과 schema, 접근 가능한 실제 자료·캘린더·필수 참석자 확인이 필요하다. 루트 확인 전 인증 가용성을 주장하지 않는다. `.env` 값과 개인 OAuth 설정은 읽지 않는다.

후속 루트 실제 GET `/api/mcp/servers`의 `D:/work/study/hyd-iot-edu/.evidence/final-completion-20261012/registered-mcp-names.json`을 직접 읽어 seed 서버5개(neo4j, hyd-dmn, enterprise, enterprise-maint, enterprise-purchase)만 확인했다. Google/Calendar/Drive 등록은 없다. 이름·전송방식 증거이며 토큰/개인 OAuth 값을 조회하지 않았다. 로컬 읽기 MCP 성공을 Google 회의 완주로 대체하지 않는다.

필수 참석자 명단과 일정 응답을 일치시켜 모두 accepted인 경우만 전원 수락이다. 누락·무응답·거절·tentative를 수락으로 바꾸지 않는다. 빈 명단은 전원 수락 근거가 아니다. Boolean을 반환하지 않는 서버의 참석자 배열에서 임의 원소를 꺼내 Boolean처럼 쓰지 않는다. 별도 확인 task/MCP가 필요하다.

## 검증

- `mcp_check.call`과 `call_effect`는 매 호출마다 실제 도구 목록의 입력 schema를 검증한다. required/type/enum/additionalProperties/배열/로컬 $defs와 조합을 정식 `jsonschema==4.26.0`으로 검사한다. 잘못된 schema·지원하지 않는 dialect·해결 못 하는 참조는 명시 거절이며 URL/파일 참조를 가져오지 않는다. format annotation을 임의의 추가 필수 정책으로 바꾸지 않는다. 거절 오류에 입력값·schema 원문·참조 주소를 출력하지 않는다.
- 쓰기 호출의 idempotency key 주입 뒤 최종 입력을 검증한다. 읽기 호출의 read-only gate와 강사 확인 계약을 유지한다. UI 시험 호출은 입력 불일치422·서버 입력schema 오류502, 없는도구404·읽기금지403으로 구분하며 거절도 기존 감사 기록에 남긴다.
- 첫 관련 시험: **126 passed/1 failed**. 기존 시험은 숫자 schema에 문자열을 보내 서버 도구 오류를 기대했다(`test_mcp_check.py` 기존230행). 새 계약은 호출 전 거절이다. 호출 횟수가 늘지 않는 더 강한 기대값으로 변경했고, 유효 입력에 대한 실제 HTTP 도구 `isError=true` 표시 검증을 별도 추가하여 기존 도구 오류 계약을 유지했다. 최초 실행은 도구 결과와 `meeting-input-contract-first-failure.txt`의 명시적인 전사 기록으로 보존하며 원본 redirected stdout으로 주장하지 않는다.
- 후속 시험: **128 passed, 4 warnings, 19.13초**. 로그 `D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/meeting-input-contract-tests.log`. API 상태분류2개를 추가한 최종 관련 시험은 **130 passed, 4 warnings, 20.72초, exit0**(`meeting-input-contract-final.log`)다. `git diff --check` 오류 없음.
- 명령: `.venv314/Scripts/python.exe -m pytest tests/test_mcp_input_contract.py tests/test_mcp_check.py tests/test_c2_parts.py tests/test_capstone_g3_mcp_extract.py tests/test_capstone_kit.py -q --tb=short`. 프로토콜 fixture는 실제 Google과 구분한다.

현재 Google 일정 생성·응답 재조회 완주는 미완료다. 직접 pin은 process 서비스와 dev requirements에만 추가했다. 공식 [검증 API](https://python-jsonschema.readthedocs.io/en/stable/validate/)와 [참조 registry](https://python-jsonschema.readthedocs.io/en/stable/referencing/) 문서를 대조했다.
