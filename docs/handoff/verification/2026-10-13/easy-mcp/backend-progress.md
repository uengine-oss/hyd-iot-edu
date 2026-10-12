# OAuth backend 진행 — 2026-10-13

범위: 공유 교육 MCP 연결 초안/discovery/PKCE/browser binding/encrypted persistence/refresh/check/disconnect. 포털 로그인·회원가입 추가 없음. ChatGPT 연결을 HYD 권한으로 사용하지 않는다. live/DB/Google 호출 없이 격리 시험만 한다.

계약: /api/mcp/connections GET catalog/connections/configuration; POST /prepare; POST /{id}/start; GET /callback; POST /{id}/check; POST /{id}/disconnect. OAuth 후보는 tools 검사 통과 전 registry에 넣지 않는다. credentials는 기존 secret store의 암호화 blob으로 저장하며 HYD_MCP_OAUTH_KEY 또는 HYD_MCP_OAUTH_KEY_FILE 없으면 준비 필요. 운영자 callback URL 및 OAuth client 설정 필요. 단순 header/API-key 등록은 유지한다.

Runtime seam: mcp_oauth.access_headers(repo,tenant_id,name,entry), mcp_secrets.runtime_spec에서 합성. root는 main mount를 담당한다. 현재 구현/검증 진행 중이며 외부 인증 성공 주장은 없다.

구현/검증 후속: 신규 mcp_oauth.py와 mcp_secrets/mcp_registry/mcp_api runtime seam을 추가했다. 첫 API 시험은 Request annotation을 FastAPI가 query로 해석해 9통과/1실패였고 global Request로 수정 후 10통과. 이후 actual HTTP MCP gate 시험의 DNS stub이 localhost까지 바꿔 연결을 끊어 66통과/1실패; 원래 resolver를 격리 HTTP 시험에만 복원해 신규18통과(1.44초). 기존 G2/registry49개는 같은 집중 실행에서 통과했으며 다시 전체를 돌리지 않았다. 실패 원문 H/backend-first.log, backend-focused.log, backend-http-gate-diagnostic.log 보존.

참고 실제 코드: ProcessGPT .gitmodules services/frontend=process-gpt-vue3, services/memento/ontology-studio; Memento app/core/auth.py49~83 tenant_oauth 사전등록값으로 Google authorization_url 생성(여기의 state=tenant_id는 복제하지 않고 새 random state+PKCE+browser binding 적용). ontology-studio/backend/src/modules/ontology_mcp/server.py1~26 명시적 4 readonly tool boundary를 읽었다. OAuth 여부와 도구 쓰기 권한을 혼동하지 않는다.

Primary: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization (protected-resource + issuer metadata, PKCE, resource binding); https://docs.cloud.google.com/mcp/supported-products 의 Workspace 표는 Drive/Calendar endpoint와 Developer Preview를 확인한다. 현재 공식 docs의 새 stateless MCP 규격 지원은 외부 실제 검사 성공을 보장하지 않는다. HYD 기존 initialize/tools checker는 실제 통과해야만 연결됨이다.

최종 backend 동결: generic auth_mode=auto/none/oauth/api_key를 지원한다. auto는 실제 무인증 MCP initialize/tools-list 성공 때만 즉시 연결됨이고, 실제 401+표준 discovery 때만 외부 로그인을 준비한다. 표준 인증 정보 없는 401은 api_key_required(접속키 필요 여부/방식 확인)로 표시한다. 접속키는 header 방식 명시 선택 후 단일 password 값으로 전달하며 암호화 기록 외에 저장/응답하지 않는다. Google preset은 OAuth이며 실제 외부 로그인/Google tool 호출은0이다.

최종 집중 시험: 신규21+G2기존23=44통과7.38초(H/backend-final-auth-modes.log). 그 전 OAuth transport/registry/API 검사103통과35.34초(H/backend-final-focused.log)는19신규+84기존인 당시 판본의 별도 범위이며44와 합산하지 않는다. 신규 auto/key/unknown expiry 후에는 영향받는21+23만 다시 확인했다. HTTP gate에서 Business tools/call은0이며 읽기/쓰기 gate 분리가 실제 initialize/tools-list 응답으로 검증됐다.

Root의 google-public-metadata.json 실제 공개 metadata GET 근거를 재사용한다: Google issuer accounts.google.com은 S256을 광고하고 Drive protected-resource metadata는 정확한 /mcp/v1 resource/issuer를 제공했다. 특례 어댑터나 PKCE 기준 완화 없이 표준 discovery가 가능하다. 이것은 계정 동의/Preview 가입/실제 tools 접근 성공을 뜻하지 않는다. 공식 [Drive 구성](https://developers.google.com/workspace/drive/api/guides/configure-mcp-server)·[Calendar 구성](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server)은 Preview 프로그램/API 활성화/사전 OAuth 앱 설정을 요구한다.

연결 초안과 credentials는 기존 public.mcp_secrets text 칸에 Fernet 암호화 blob으로 저장한다. 새 DB 스키마/라이브 DB 변경은0. HYD_OAUTH_* namespace를 공개 비밀 목록·자리표시자·worker용 load에서 제외했다. 키가 없거나 복호화/표 접근에 실패하면 준비 필요/503으로 멈추며 평문/메모리 영속 대체는 없다. Root는 /data/mcp/oauth.key 영속 키와 callback origin을 준비한다. 사전 OAuth client 설정은 운영자의 HYD_MCP_OAUTH_CLIENTS issuer-keyed JSON(외부 앱 생성은 별도)이고 API 응답/로그에 secret이 없다. 동적 등록을 지원하는 서버는 표준 등록을 사용한다.

통합: root main에 mcp_oauth.mount(app,runtime_factory=...,audit=...) 추가. fixed HYD_MCP_OAUTH_CALLBACK_URL=http://localhost:8088/api/mcp/connections/callback, 같은 origin nginx proxy 및 callback query access-log 제거는 root 소유. start→authorization_url/connection_id/attempt_id/frontend state/expires_at, HttpOnly SameSite=Lax binding cookie. callback은 backend random OAuth state+PKCE+browser binding+단회/만료 검증 뒤 같은-origin opener에 상관값만 전달한다. UI는 실제 GET→login_complete→check 자동 검증을 수행한다. 공개 row는 id/name/url/preset/auth_mode/status/reason/reason_code/expires_at/shared/account_label(null)뿐이다.

실행 seam: access_headers(repo,tenant,name,original_entry), runtime_spec에서 original hyd를 보존하여 해석한 뒤 normalize한다. OAuth/key/none 공유 연결은 이름·URL·tenant·연결됨 상태가 맞아야 한다. known expiry만 refresh를 수행하고 unknown expiry는 null로 보존하며 예약 갱신을 만들지 않는다. 실제401은 mark_auth_failure로 재로그인 필요를 기록하며 자동재시도0. encrypted key/token 원문은 짧은 값까지 redact한다. Transport.open(method,url,body=None,headers=None,timeout=8)→(conn,response)는 DNS 검증+IP 고정/TLS hostname 검증/redirect 거부이며 호출자가 streaming body 한도와 close를 책임진다. Worker의 claim-bound 내부 relay는 capture 담당 /internal/worker/mcp-runtime이며 사용자 공개 proxy에 포함하지 않는다. 암호화키/업스트림 OAuth token을 worker에 전달하지 않는다.

한계: 현재 공유 교육 연결이며 학생 개인계정 자동 혼용/포털 회원가입 없음. 실제 OAuth 앱/외부 동의와 계정 scope는 외부 준비 상태에 따른다. 현재 Google 실행 완료/전체 실습랩 수행/새 전체회귀 성공 주장은 없다. disconnect는 포털 token/API-key/owned registry를 지우지만 외부 서비스에서 부여한 동의 철회까지 수행했다고 표시하지 않는다.

## SYSTEM MCP 진행 이력 계약 — 구현 전

결함: _run_service→instance_transaction→_call_mcp의 tool_usage_started가 같은 transaction connection에 들어가므로 upstream 대기 중 두 번째 reader/SSE는 시작을 읽을 수 없다. /healthz와 별개이며 프런트 폴링/연출로 고치지 않는다.

최소 근본 수정: 기존 events 저널에 SYSTEM의 관측 이벤트만 별도 connection/짧은 transaction으로 기록한다. 업무 인스턴스/작업/승인/출력/후속 전이는 기존 잠금·transaction 안에 두며 전체 업무 transaction을 flush/commit하지 않는다. events에는 parent FK가 없으므로 별도 writer가 잠긴 부모를 읽는 SELECT(MVCC, FOR UPDATE 금지)와 사건 insert만 수행한다. tenant/instance/workitem/committed SYSTEM claim owner를 대조한 뒤만 쓴다.

상관: service attempt_uuid와 call tool_use_id를 시작·끝·업무전이 확정/rollback 표시에 공유한다. 효과 idempotency_key는 기존 값 그대로. 원래 시작/실제 도구 결과를 실패 재생으로 복제하거나 변조하지 않는다. 업무 rollback은 별도 SYSTEM_ATTEMPT_ROLLED_BACK 관측행으로 남겨 도구 응답과 업무 적용 결과를 구분한다. upstream 예외도 실제 실패 finish를 남긴다. 진행 시작 저장 실패는 외부 도구를 호출하지 않는 fail-closed이며 finish/closure 실패는 완료라고 꾸미지 않는다.

검증: root 제공 localhost55757 isolated migrated PG만 사용한다. 두 reader connection에서 upstreamblocked 동안 시작행만 visible/업무consumer와output 미커밋을 확인한다. 성공 commit, upstream실패/업무후속실패 rollback, owner/tenant거절, 독립기록 오류(no upstreamcall), 상관/중복 없음, 기존단위실행계약 집중 검증. production/Docker/LLM 없음. Root isolated provision 근거 H/isolated-pg-migration.json.

SYSTEM 첫 실제 PG 검증: 신규18개 중14통과/4실패(메모리 fixture output칸 누락 KeyError, 실제PG9개는 통과). 기대값을 바꾸지 않고 생성하는 초기 작업행에 output=None을 명시해 PG 기본값과 동일하게 한다. 최초 H/system-progress-pg-first.log 보존. 기존32 backend통과+1UI harness load실패도 별도 보존했다. 원문enterprise.js CRLF와 tests/js/render_task_detail.js LF-only const/actionLabel추출 regex가 불일치하며 제품logic전 실패다; 원본 inspector/기대값은 수정하지 않는다.

SYSTEM 다음 집중 시험74통과/5실패/1legacyharness제외를 원문 보존한다(H/system-progress-final-focused.log). 추가한 guard의 user_id=sys:process 조건이 실제 엔진 서비스 행 계약과 달랐다: engine._make_workitem은 서비스에도 lane의 role binding을 보존하며 실행기는 agent_orch=hyd-process로 정한다. 기존 waiting_services/claim 계약과 같이 tenant/instance/SUBMITTED/hyd-process/committed consumer로 검증하고 임의 사용자ID 제한을 제거한다. cliagents 행 거절 negative도 추가해 경계 완화를 검증한다. 실제 PG9개+메모리9개는 모두 통과한 상태였고 기존B/C 공지의 role binding 경로5개만 거절됐었다.


## SYSTEM 최종 구현 및 동결 범위

최종 원인은 post-commit으로 도달한 SYSTEM 작업행의 consumer=None이었다. 앞선 role binding 제한을 제거한 뒤에도 이 미확정 소유권 때문에 기존 경로 5건이 계속 거절됐다. 관찰 guard를 완화하지 않고 기존 instance_transaction 잠금에서 짧게 시도별 UUID executor claim을 저장하고 커밋한 뒤 업무 전이를 시작하도록 수정했다. 활성 부모 전이에서는 기존 after_commit 큐로 넘겨 부모 내부의 외부 호출과 관측 기록을 0으로 유지한다. 독립 journal writer는 별도 연결에서 committed tenant/case/SYSTEM claim을 계속 대조한다. 업무 transaction 전체를 중간에 commit하지 않는다. 효과 idempotency_key는 유지하고 attempt/tool_use 상관값은 분리한다. 이전 시작만 남은 호출은 소유권을 안전하게 복구한 뒤 실제 응답 미확인/interrupted finish로 닫으며 결과나 외부 실행 취소를 만들어내지 않는다.

최초 검증은 기존 backend 32통과와 UI harness load 실패 1건이었다. 다음 실제 PG 검증은 신규 14통과/4실패였으며, 실패는 메모리 fixture의 output 칸 누락이었다. 이후 74통과/5실패에서는 잘못된 user_id 제한을 발견했으나, 이를 바로잡은 후에도 consumer=None 때문에 기존 5건이 남았다. 각 최초 실패 로그는 보존하며 최종 원인과 구분한다.

최종 집중 검사는 84통과/2제외, 9.78초다(system-progress-final-backend.log). 범위는 신규 24건(실제 PG 12건과 Memory 12건) 및 관련 기존 60건이다. 새 부모 전이 검사는 내부 호출/관측 0, commit 후 호출 1, 시작/끝/감사 각 1, 실제 한국어 503 응답 보존, 업무 vars/output 원복과 retry 1, rollback closure 1을 모두 확인한다. 시작 journal 저장 장애 시 upstream 호출 0, owner/tenant/case/비업무 관측 경계, 두 PG reader와 production SSE cursor의 대기 중 시작 가시성, orphan 복구를 포함한다.

system-progress-final-strong-contract.log의 신규 2실패는 테스트 작성자가 감사 명칭을 MCP_CALL_FAILED로 잘못 적은 오류였다. 실제 공식 명칭 MCP_EFFECT_FAILED를 직접 확인해 신규 assertion만 수정했으며 정확히 1회라는 의미 검사는 유지했다. 기존 test_failed_attempt_trace.py의 nested 검사 1건은 원본 그대로 실패한다. 부모 내부 즉시 호출과 rollback 없음이라는 구계약이 승인된 안전 계약과 충돌하기 때문이다. 사용자의 기존 검사 변경 금지에 따라 수정하거나 완화하지 않았다. CRLF 원본 inspector 1건은 제품 logic 전에 load 실패한 상태다. 별도 독립 VM은 enterprise.js 전체 실제 원문을 로딩하고 실제 taskDetail/trace consumer로 동일 실패 응답과 회차 assertions를 수행해 1통과했다(system-progress-direct-consumer-fourth.log). 원본 inspector와 표시 label은 수정하거나 대체하지 않았다. 독립 harness 준비 과정의 path/config 및 let/const 오류 로그도 보존한다.

ProcessGPT 모노레포 SDK의 database.record_events_bulk 독립 관측 기록과 최신 Vue ChatRoomPage.vue 10466행의 tool_usage_started/finished 처리를 직접 참고했다. ontology-studio의 별도 MCP 도구 및 호출 경계도 참고했다. 현재 증거는 isolated PG와 단위 소비자 범위이며 root의 실제 HTTP→SSE→native 검증은 별도다. 제품 동결 SHA와 실행 중 시험 0은 system-progress-final-result.json에 기록했다.

Calendar 최소권한 followup은 공식 Workspace MCP 문서의 calendar.calendarlist.readonly, calendar.events.freebusy, calendar.events.readonly 세 scope를 반영한 신규 단독 1통과다(calendar-scope-followup-result.json). 앞선 44통과 결과와 합산하거나 Google 계정 동의 및 호출 성공으로 표시하지 않는다.
