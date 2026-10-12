# 외부 서비스 연결 화면 — 구현 진행

기존 서버 등록·도구 지도·읽기 시험·쓰기 제한은 유지한다. 일반 화면은 서비스 선택(Google Drive, Google Calendar, 다른 서버 주소)과 연결 버튼으로 시작한다. 포털 회원가입이나 자체 로그인은 만들지 않는다. 외부 서비스의 동의는 해당 서비스 창에서만 받으며 실제 Google 동의가 아직 없다는 사실을 연결 상태와 구분한다.

현재 교육용 공용 연결임을 기본 표시한다. 다른 학생의 개인 계정을 자동 혼용하지 않는다. 운영자 설정은 접힌 별도 영역으로 두고, 일반 동선에서 토큰·JSON·클라우드 프로젝트를 요구하지 않는다. 원본 등록 폼은 관리 영역에서 계속 사용할 수 있다.

서버 계약: GET /api/mcp/connections의 catalog/connections/configuration을 조회한다. prepare→start→외부 동의→check 실제 도구 검사→connected 뒤만 사용 가능이다. 상태를 꾸며 성공시키지 않는다. 해제는 실제 disconnect API 성공 이후에만 반영한다. 팝업 반환은 origin/source/attempt/state를 확인한 뒤 서버에서 현재 상태를 다시 검사한다. 취소·만료·권한 부족·팝업 차단·오류는 명시하고 입력과 포커스를 보존한다.

구현 소유: mcp.js 및 새 mcpConnections.js, 새 Node 계약 검사. index의 script/cache 통합과 라이브 검증은 루트 소유다. 비밀값·DB·워커·배포·라이브 쓰기는 수행하지 않는다.

참고 검토: ProcessGPT 최신 monorepo docs/en/architecture.md의 영속 상태/도구 실행 분리, 보존 Vue MCPServer.vue의 등록 목록/검사 상태 구분, ontology-studio FilePanel.vue의 원본/표시 분리, Dify tracing-panel.tsx의 표시와 실제 실행 상세 분리를 직접 확인한다. 실제 인증과 도구 성공은 프론트 정적 표시로 대체하지 않는다.

진행: 기존 mcp.js 등록 bodyFrom/check/save/delete 계약을 읽고 유지했다. 새 mcpConnections.js가 실제 서버 상태를 조회하며 입력 DOM을 교체하지 않는다. 같은 출처의 /api/mcp/connections로만 요청하고 서버 binding cookie를 사용한다. popup origin/source/connection_id/attempt_id/state를 확인하며, 초 단위 만료 값을 명시적으로 처리한다. 인증창의 창 분리 정책 때문에 closed가 된 경우 취소로 단정하지 않고 서버 상태를 계속 조회한다. 성공·해제 응답의 해당 연결 번호와 상태를 검사한다.

일반 서버: auto prepare의 실제 무인증 도구 검사가 통과하면 별도 인증창 없이 사용 가능으로 간다. 표준 로그인 서버만 외부 동의를 진행한다. 접속키가 필요한 실제 응답이 오면 단일 비밀 입력과 접속 방식 선택을 표시한다. 비밀값은 컨트롤러 상태·브라우저 저장소·주소에 저장하지 않고 요청에만 보내며 연결 성공 뒤 입력을 지운다. 표준 로그인 서비스에서 개인 토큰을 요구하지 않는다. 설정과 제공 서비스의 실재 권한에 따라 실제 사용 가능 여부가 달라진다.

참고 실물: `R/.evidence/reaudit/references-latest/process-gpt/docs/en/architecture.md`, `process-gpt-vue3/src/components/pages/account-settings/MCPServer.vue`, `ontology-studio/frontend/src/features/files/FilePanel.vue`를 직접 읽었다. Dify clone이 있다고 주장하지 않는다. 공식 [tracing-panel.tsx](https://raw.githubusercontent.com/langgenius/dify/main/web/app/components/workflow/run/tracing-panel.tsx)를 직접 읽은 웹 기록의 표시/실행 상세 분리를 참고했다.

집중 검증: 새 Node 소비자 검사는 동의 뒤 자동 검사·팝업 출처와 요청 범위·차단 복구·취소/만료·권한 부족·준비 실패·재인증·늦은 응답·일반 서버 입력·무인증·접속키·현재 공용 연결 표시 및 동일 출처 쿠키 요청을 검사한다. 실제 UI helper를 올린 mount 검사에서 입력 컨트롤 객체와 값을 보존한다. 기존 등록/도구 입력 검사 2개도 통과했다. Node mount의 입력 보존은 실제 브라우저 포커스 측정을 대신하지 않는다.

네이티브 검증 계획(루트 소유): index script/cache와 동일 출처 proxy 통합 후 준비 상태·서비스 선택·일반 주소 입력의 포커스/값·관리 영역 기본 접힘을 1440/1024에서 확인한다. 격리된 실제 무인증 서버와 실제 가상 인증 서버의 consent/callback/check 흐름은 실물 backend HTTP 증거로 따로 검증한다. Google 실제 계정 동의·Drive/Calendar 실행은 아직 수행하지 않았다. 이를 시험 응답으로 완료했다고 주장하지 않는다.
