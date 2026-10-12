# 시스템 MCP 등록 의존성: 현재 계층과 최소 제안

실제 호출의 안전 검사는 이미 존재한다. 따라서 없는 Google 서버를 실제 호출하거나 잘못된 schema로 외부 쓰기하는 안전 결함을 확인한 것은 아니다. 확인된 누락은 **구조검사/등록의 화면이 외부 의존성 미준비를 알려 주지 않는 사전 진단 범위**다. 현재 문서 계약은 실제 연결/입력이 있어야 실행된다고 설명하므로 연결은 호출 시 검사하는 기존 설계와 양립한다. 등록을 반드시 차단해야 한다거나 start 정책을 바꿔야 한다는 결론은 이 조사에서 내리지 않는다.

## 이미 있는 검사

| 계층 | 실제 확인 | 범위 |
|---|---|---|
|서버 등록/수정|mcp_registry.py:157 run_check,477 register,494 update|실제 tools/list 실패면 서버 저장 거절. fingerprint/checked_at/판정 저장|
|에이전트 도구 배정|agent_authoring.py:128~151와 mcp_registry.py:419 refuse_reasons|존재/최근검사/설정동일·읽기도구게이트. 없는서버를agenttools로쓸수없음|
|흐름 구조/판본 등록|flows_api.py:64 catalog_of,202 check; bpmn_import.check|parts/roles/agents와서비스설정형식·승인경로·결과타입검사. tenant MCP레코드는context에없음|
|직접 시작|instances.py:230 start_definition|명시판본/시작입력/역할/승인주입금지검사. MCP사전연결조회없음. 미배포판본도수동시작가능|
|실제systemtask서버해결|instance_mode.py:503 _effect_server|EFFECT_MCP_SERVERS를먼저보고없으면tenant등록조회. 서버없음은LookupError. 기준이아닌서버gatefingerprint불일치도거절|
|실제MCP호출직전|mcp_check.py:699 call_effect 및call(read)|매호출fresh tools/list→도구존재→idempotencyruntime주입후schema검사→tools/call. read_only gate 별도 유지|
|실제오류보고|service_parts.py:135~165 _call_mcp|도구시작/실패event와사유기록뒤ServiceExecutionError. 빈값이나가짜성공으로대체안함|

## metadata와 근본 제한

`mcp_registry.run_check:169`은저장tools에name/title/description/annotations/read_only/reason/confirmable만남기며 **inputSchema를버린다**. `check_state:351`은ok/failed/stale/never와fingerprint상태를노출한다. `selectable:377`은agentread_only목록을만드는함수이므로승인뒤systemtask의쓰기tool존재진단에그selectable판정을그대로쓰면안된다. `store_for(repo)`의tenantservers/latestchecks를순수snapshot으로읽으면서버존재/검사상태/저장tool존재는알수있지만정확inputSchema는현재저장metadata만으로검증할수없다.

내부EFFECT_MCP_SERVERS는tenantregistry와별도의정식runtime경로다. tenant목록에없다는이유만으로hyd-effects같은기준서비스를결손이라고진단하면새오류가된다. configuration/credential값을UIcontext로내보내는것도금지한다. 순수snapshot에는서버명·fingerprint상태·도구명·판정·schema가있다면schema만주고비밀headers/env/URL자격값은주지않아야한다.

시작이아직모든값을갖지않는argument template을수신한다는점도구분한다. `{approved_option.slot}`같은승인뒤동적값은정적sample로만들어fullschema를통과시킬수없다. 정적키/필수키누락·명백한literal타입등검사가능한조건과runtime에서만검증되는조건을나누어야한다. runtimeidempotency_key는호출주입필드이므로mapping에서없다고required누락처리하지않는다.

## 최소 근본안: 기존 검사 화면의 별도 의존성 진단

우선구조check의ok/등록정책은유지하면서existingcheckresponse에`dependencies`같은명시목록을추가하는범위를제안한다. 각systemMCPtask의node id/name/server/tool과`준비 확인/연결 검사 필요/서버 미등록/도구 미확인/동적 입력은 호출 시 검사`를반환하여UI해당부품칸에보여준다. 이것은새업무단계·OAuth상태기계·mockfallback이아니다. 기존snapshot을읽는순수함수이며HTTP/tools-call/DB쓰기없다. 최종blocking severity와start허용정책은루트가사용자계약에맞춰별도결정한다.

제안실파일(아직수정0):

- 새`it/process/procsvc/mcp_dependencies.py`: sanitizedserver/checksnapshot에서systemtask의존성순수평가. EFFECT_MCP_SERVERS정식명단을동일원천에서주입.읽기효과false는read게이트판정,승인뒤쓰기는agentselectable로막지않음.
- `it/process/procsvc/flows_api.py`: catalog/view의기존checkresponse에진단추가. 현재구조검사함수는tenant/IO없는순수계층으로유지.
- `it/portal/www/flows.js`: 기존문제목록/해당task설정에dependency사유와'구조검사통과는외부연결확인이아님'을구체적으로표시. 시작차단정책을임의추가하지않음.
- schema사전검사까지확정할경우에만`mcp_registry.py:169`의정식toolsmetadata에inputSchema를보존. 과거레코드schema없음은미확인으로진단하고가짜schema생성/자동networkfetch하지않음.모든실제호출freshschema검사는유지.

## 필요한 좁은 부정 조건

새순수진단시험은없는서버/failed-stale-never검사/없는tool/readonlytask에write도구/내부EFFECT서버정상/동적승인입력보류/runtimekey필수값의예외/credential비노출을다룬다. 저장schema가없으면'확인안됨'이지schema통과가아니다. 이미있는`tests/test_mcp_input_contract.py`의invalid_advertised_input/required_and_fresh_contract/effect_validates_after_idempotency_injection/input_validation_does_not_override_read_only_gate와`tests/test_mcp_check.py`unknown_tool_and_bad_arguments가runtime불변조건이다. 이번조사에서이시험을재실행하거나기대값을변경하지않았다.

현재prepared3파일은기존offline구조검사ok이고실제Google등록0이다. UI사전진단최소안을채택하기전까지추가라이브등록은보류권고다. 이미존재하는명확한runtimeerror는보존하며등록/시작차단규칙을새로추측하지않는다.
