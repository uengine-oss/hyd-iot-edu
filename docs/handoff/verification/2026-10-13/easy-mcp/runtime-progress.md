# MCP 실행 연결과 운영 준비상태

2026-10-13 사전 범위: worker bridge/context 실행 연결과 instance_mode 폴링 상태, 새 격리 시험만 수정한다. main.py 통합은 루트, OAuth 저장·갱신·runtime_spec·API는 meeting_contract 담당이다. 실제 DB, Docker, 계정 인증, LLM 및 업무 실행은 하지 않는다.

확인한 원인: context.with_secrets는 SECRET 참조가 없으면 반환하므로 OAuth 전용 연결이 실행 자격증명을 받지 못한다. bridge는 원래 레지스트리 설정 해시를 검사한다. 따라서 갱신된 헤더는 원래 설정과 분리된 비공개 실행 자료로 전달하고 프롬프트에서 제거해야 한다. API 경계는 담당자와 합의 후 구현한다.

instance_mode._polling은 예외를 기록한 뒤 반복하지만 준비상태를 제공하지 않는다. 시작 준비 중, 전체 폴링 성공, 실패, 취소 및 종료를 구별하는 runtime_readiness 읽기 인터페이스를 제공한다. 준비상태 조회는 새 DB 쿼리를 하지 않고 다른 소스 오류를 제거하지 않는다. 예외 원문은 상태 응답에 넣지 않는다.

직접 참고: 보존된 ProcessGPT monorepo `.evidence/reaudit/references-latest/process-gpt/docs/en/architecture.md`의 실행 엔진/MCP 프록시 분리, ontology-studio `.evidence/reaudit/references-latest/ontology-studio/frontend/src/features/files/FilePanel.vue`의 원본 이름/출력 분리. 이는 보존된 참고 판본이며 현재 외부 인증 성공 증거가 아니다.

시험 계획: 실제 production 폴링 호출에 실패 주입→전체 성공 회복, 타임아웃/정리 실패, 취소·종료, 다른 상태 오류 보존, 비밀 원문 부재; OAuth 실행 헤더의 원래 fingerprint/읽기 전용 gate/실행 파일 정리 유지. 전체 회귀나 기존 A/B/C를 재실행하지 않는다.

실행 연결 설계 확정: 시작 때 외부 토큰을 워커에 주는 초안은 실행 중 만료를 처리하지 못하므로 폐기했다. `/internal/worker/mcp-runtime`은 파일 인증 뒤 담당 단계·임대·설정 해시·읽기 검사에 묶인 서명 권한만 반환한다. 외부 토큰을 반환하는 경로는 없다. 워커 CLI 설정에는 중계 주소와 이 한 실행의 제한된 권한만 들어가며 장기 워커 키나 외부 토큰은 들어가지 않는다. 실행 파일은 기존 finally 정리에서 제거한다.

`/internal/worker/mcp/{name}`은 요청마다 현재 담당 단계·유효 임대·현재 검사 해시를 다시 확인하고, `runtime_spec`이 연결 저장소의 자격증명을 갱신한다. DNS 고정·TLS 호스트 검증·이동 금지 transport를 재사용한다. 승인 전 읽기 도구만 허용하며 승인 후 시스템 쓰기는 기존 별도 승인 경로다. JSON 및 POST SSE 응답, 실행별 세션 종료를 지원한다. 선택 기능인 GET 스트림과 기존 OAuth SSE 방식은 명시적으로 지원하지 않는다. 요청을 401 뒤 자동 재실행하지 않고 연결을 다시 확인하도록 표시한다. 서명 권한은 최대 1800초이며 요청마다 실제 임대 만료를 더 짧은 유효 경계로 적용한다. 세션은 서명 권한별로 분리한다.

현재 집중 근거: 폴링/기동 10 통과, 중계·기존 CLI 근접 검사 27 통과, 별도 원본 연결 메타데이터 소비(read/system) 2 통과. 이는 중간 판본별 기록이며 합산한 전체 회귀 숫자가 아니다. 처음 redaction의 지역 import 충돌과 새 시험 저장소 메서드 오타는 실패 원문을 H/runtime에 보존하고 바로잡았다. 최종 동결 및 최종 집중 결과는 같은 폴더 result.json에 기록한다. 실제 외부 계정 동의·Google 도구 실행·배포·LLM 성공 근거는 아니다.

최종 동결 판본: 새 집중 시험 35개와 기존 가까운 CLI 2개, 합계 **37 통과·8.41초**, `runtime/final-focused.log`. 같은 실제 HTTP 만료 검사에 시작 시점 토큰만 재사용하도록 메모리 결함을 주입한 역검사는 **1 실패·1.43초**: 실제 refresh 요청 0이 기대 1과 달라 assertion이 실패했다. `fault-start-only-token.log`에 원문을 보존했다. 제품 및 새 시험 9파일 SHA는 최종 검사와 역검사 전후 불변이며 `runtime/result.json`의 ok=true로 확인한다. 기존 전체 회귀는 재실행하지 않았다.

좁은 후속 사전 기록: 읽기 전용 수용 감사에서 `Runner._fail`의 연결 오류 사유가 raw_error에만 있고 friendly는 모든 실패에 같은 일반 문장이어서, 네 소비자(실시간/Trace/TaskDetail/Record)의 기본 표시에서 재연결 안내가 가려짐을 확인했다. 루트 승인으로 통제된 RuntimeConnectionError에만 안전한 한국어 사유를 friendly에 쓰고 일반 예외는 기존 가림/원문 분리를 유지한다. 실제 생산자→현재 네 JS 소비자 모델 대조와 그 안내를 다시 가리는 메모리 역검사만 추가한다. 이전37검사/동결 원본은 보존하고 관련 runner 및 새 시험 SHA를 후속 판본으로 분리한다.

연결 안내 후속 완료: 해당3검사 **PASS·1.22초**, 일반 오류 본문은 기본 표시로 풀리지 않는다. 메모리에서 이전 generic 안내를 복원하면 새 검사 **1 예상 실패·0.72초**로 통제된 재연결 사유 불일치를 잡는다. 첫 VM 수집 환경의 setInterval 미정의 오류를 `public-reason-focused-first.log`에 보존하고 현재 production timer 함수를 바꾸지 않고 격리 VM 환경만 보완했다. `runtime/result-before-public-reason.json`은37검사 판본, `runtime/result.json`은 runner/새시험2파일의 의도한 변경과 후속3검사 판본이다. 나머지7파일 SHA는 그대로이며 관련 후속 검사 이후 제품 변경은 없다.
