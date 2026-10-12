# K3 외부 Google 연결 가능성 — 읽기 조사 2026-10-12

현재 ChatGPT 문맥의 Google Drive 앱은 `get_profile` 인증 읽기에 성공했다. 이름·메일·사진·토큰은 출력하거나 증거에 저장하지 않았다. 현재 문맥의 Calendar 플러그인은 미설치로 조회되었으며, 다른 계정/문맥의 연결 여부를 부정하는 근거는 아니다. 앱 연결과 HYD 워커 연결은 별개다.

## 현재 실제 근거

- `runtime-boundary.json`: 실제 GET `/api/mcp/servers` 200. 등록 서버는 neo4j, hyd-dmn, enterprise, enterprise-maint, enterprise-purchase 다섯 개이며 Google 등록은 없다. localhost8511/8512 건강 확인은 연결 불가였다. 서비스를 새로 띄우지 않았다.
- `registered-capabilities.json`: 다섯 서버의 실제 GET 도구 목록. hyd-dmn19, enterprise14, enterprise-maint4, enterprise-purchase3; neo4j는 HTTP200이나 도구0이며 정상 연결로 판정하지 않는다. 도구 호출/자료 조회/등록 쓰기0. 해당 내부 도구들은 Google Drive/Calendar 인증 증거가 아니다.
- `connector-auth-state.json`: 연결된 Drive 앱 인증 읽기 성공 boolean만 보존. 앱 설치/권한 변경/Calendar 쓰기0.
- 기본 HYD Google token/client 파일은 존재하지 않았다. .env는 키 이름만 확인했다. 다른 설정 위치나 다른 계정의 인증 파일 존재를 전역적으로 부정하지 않는다. 다른 CLI 개인 설정·credential 내용은 읽지 않았다.

## 근본 경계와 로그인 동선

`it/agent-worker/worker/bridge.py` install은 tenant 등록 MCP만 CLI 설정으로 만들고 `--ignore-user-config --disable apps`로 개인 앱 상속을 차단한다. 이는 개인 도구 노출을 막기 위한 경계이며 삭제해서 연결을 우회할 대상이 아니다. `worker/context.py`의 with_secrets는 HYD 등록 서버의 headers/env 자리표시자만 해석한다. 현재 제공된 앱 도구에는 HYD용 인증서/토큰 내보내기나 재사용 가능한 외부 MCP 주소를 반환하는 도구가 없다.

`it/process/procsvc/mcp_check.py` normalize/_open은 URL/정적 headers 또는 stdio/env를 소비한다. HTTP401/403에는 인증 실패를 반환한다. OAuth 메타데이터 탐색·브라우저 로그인·callback·refresh lifecycle은 이 경로에 구현되어 있지 않다. 따라서 “Google 앱 이미 연결 → HYD 설정에서 그 연결 선택” 동선은 현재 없다. 학생 포털 계정 로그인은 이 외부 Google 동의 절차와 다른 문제다.

현재 `students/_template/google_meeting_mcp/auth.py`는 미리 제공된 OAuth client 파일로 Google 브라우저 동의 후 로컬 token 파일을 만들고, server.py가 AuthorizedSession으로 Google REST를 호출하는 방식이다. 이 템플릿의 client 설정 요구를 모든 외부 MCP 서비스나 모든 학생에게 GCP 프로젝트가 필수라는 주장으로 확대하면 안 된다. 강사/기관이 제공하는 적법하게 인증된 MCP 서버도 HYD 등록 계약을 충족할 수 있다.

## 원래 요구와 완료 경계

정확한 최초 설계 `docs/handoff/verification/2026-10-09/capstone-lab.md:5`는 구글 계정·인증을 사용자 몫으로 정했다. 같은 파일26행은 **(가) 내 업무 표 읽기 서버와 (나) Google Drive·Calendar 서버** 등록을 함께 요구하고,29행은 실제 Google 일정 생성→자동 확인→보고까지 닫는 한 건을 요구한다. 11행의 개인 시나리오는 실제 서비스의 일반화 예시지만 회의 시연의 구체적 완료 조건은 Google이다.

`students/_template/example_meeting/README.md`는 가상 ID/example.com/문서를 완성 참고 예로 명시하며 끝까지 돌리려면 T5 Calendar·Drive가 필요하다고 적는다. `2026-10-10/K-capstone.md`의9절도 Google 연결/그 서버 예시 완주를 미검증으로 남겼다. NOW의 K3는 실제 회의1회를 요구한다. 그러므로 실제 업무 데이터를 읽는 별도의 generic MCP 등록 실습은 **(가)의 독립 성과**로 할 수 있지만 Google K3나 현재 사용자가 요청한 외부 Google 완주를 대신할 수 없다. 로컬 읽기 개인 흐름 U21은 이미 그 독립 성과이며 새 성공으로 재포장하지 않는다.

T5 `students/_template/google_mcp.md`는 강사가 서버와 인증 방법을 정하고 학생이 전달받은 서버를 등록하는 동선이다. 필수는 학생 포털 로그인이나 학생마다 GCP 생성이 아니라 **HYD process에서 접근 가능한 실제 MCP 끝점/stdio 실행 환경, 해당 서버에 적법한 인증, 실제 도구 스키마와 자료 접근권한**이다. 현재는 사용자 연결 앱을 HYD 서버로 사용할 수 있는 endpoint/auth handoff가 확인되지 않았다.

## 외부 공식 계약 대조

Google의 [Calendar MCP 설정 문서](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server)는 Developer Preview에 대한 별도 가입/Cloud 프로젝트/API 활성화/OAuth client 설정과 OAuth2 HTTP 끝점을 안내한다. 이는 **그 공식 Preview 선택 시**의 요구이며 모든 선택지의 공통 조건은 아니다. 도구 계약도 로컬 free/busy 템플릿과 동일하다고 가정하지 않는다.

[MCP authorization 명세](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)는 HTTP OAuth의 client/server 역할과 대상 resource를 구분한다. 다른 앱의 토큰을 추출해 HYD나 별도 MCP에 넘기는 길은 제안하지 않는다. [Google native-app OAuth 문서](https://developers.google.com/identity/protocols/oauth2/native-app)는 현재 템플릿의 외부 브라우저 동의와 client 설정 선택을 설명하는 근거다.

## 다음 큰 구현 제안 — 아직 구현/등록하지 않음

1. 강사가 선택한 실제 provider/서버를 먼저 확정한다. 현재 연결된 ChatGPT 앱만으로는 HYD 등록용 끝점·인증 handoff가 확정되지 않는다. 제공된 authenticated MCP가 있다면 generic 등록 UI를 그대로 사용하고 실제 read-only tools/list/inputSchema/자료 접근부터 확인한다.
2. 사용자가 원한 “외부 MCP 설정에서 Google 브라우저 연결”을 제공하려면 서버별 OAuth 상태·metadata discovery·PKCE browser callback·grant refresh/revoke를 위한 HYD auth adapter가 필요하다. 로컬 템플릿을 택하면 강사가 제공한 client 설정을 이용한 기존 login helper를 연결 UI에서 실행/안내하고 token 파일은 기존 로컬 보관 경계를 유지한다. 사용자에게 임의 access token을 복사하도록 요구하지 않는다.
3. grant는 tenant/server/승인한 외부 계정에 묶고 연결 취소·만료·부분 scope·권한 거절을 구분한다. secret을 응답/로그/구성 내보내기에 싣지 않으며 워커의 개인 앱 격리는 유지한다. 도구 목록 검사 성공 후에만 실제 server 이름과 정확한 schema로 회의 매핑 사본을 준비한다.
4. 실제 초대는 주관자 승인 뒤 시스템 task만 수행한다. 그 전에는 읽기만 검증하고 필수 참석자·회의실·시간·문서 접근을 실제 계정으로 확인한다. 준비27pass 재실행0, 새 LLM/worker/회의 호출0; 이번 조사는 실제 OAuth/회의 완료 증거가 아니다.

## 조사 적용 skill

`C:/Users/roede/.codex/plugins/cache/openai-curated-remote/plugin-management/0.1.0/skills/plugin-management/SKILL.md`의 연결된 도구 우선/검색 후 판단을 적용했다. get_app_permissions는 OAuth scope/auth 상태를 뜻하지 않으므로 호출하지 않았다. 앱 설치와 새로운 권한 요청은 하지 않았다.
