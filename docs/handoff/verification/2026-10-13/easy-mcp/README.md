# 간편 MCP 연결과 실시간 처리 — 2026-10-13

포털 로그인 없이 서비스 선택→필요한 외부 로그인·동의→실제 도구 검사→등록하는 연결 화면과 실행 인증 경로를 구현·배포했다. SYSTEM 도구 시작이 업무 트랜잭션 종료까지 보이지 않던 결함도 수정했다. 실제 진행 기록과 업무 상태를 분리하므로 외부 응답 대기 중에도 시작이 전달되고, 응답 성공과 업무 반영 성공을 같은 것으로 표시하지 않는다.

사용자의 최신 범위는 포털 UI/UX와 기능 개발이다. 실습랩 전체 구축·모든 실습 수행·Google 계정 회의 완주는 개발 완료 조건이 아니다. 기존 A 부정 종결·B 작업지시/예약/공지·C 구매/입고 완료 근거는 이전 기록을 재사용했고 이번에 전체 회귀나 LLM 업무 완주를 반복하지 않았다. 사용자 최종 시각 인수와 실제 외부 계정 실행은 별도이며 완료한 것으로 기록하지 않는다.

## 결과와 적용 범위

| 확인 대상 | 결과 | 실제 근거와 한계 |
|---|---|---|
| OAuth 발견·PKCE·콜백·암호화 저장·갱신·해제·도구 검사 후 등록 | 집중 44 통과 | 해당 동결 판본의 신규21+기존23. Calendar 기본 읽기 3권한 후속은 별도 1 통과 |
| 워커 현재 점유·읽기 제한·요청마다 인증 갱신 | 집중 37 통과 | 실제 갱신 HTTP와 시작 토큰 고정 역실험 포함. 실제 CLI/Google 실행을 뜻하지 않음 |
| 통제된 연결 실패 사유의 공개 표시 | 후속 3 통과 | 실제 생산자→실시간/흐름/작업/기록 JS 소비자. 임의 오류 내용은 그대로 공개하지 않음 |
| 처리 준비/실패/취소/복구와 health, 콜백 로그, 키 준비 | 집중 11 통과 | health/log 보호 제거 역실험은 기대대로 실패. 기존 FastAPI 폐기예고 2개 |
| 연결 화면·기존 등록 폼 | Node 및 기존 폼 2 통과 | 콜백 상관·취소·만료·입력 보존·조건부 접속키·한국어 서비스명·영역 전용 숨김 CSS |
| 격리 HTTP OAuth→실제 제품 API→Chromium | 17 항목 통과 | 동의/자동 검사/등록/해제/거절/무인증/접속키. Google나 LLM 실행 아님 |
| 배포된 실제 포털 1440/1024 | 최종 GET 18 항목 통과 | 쓰기0·콘솔0·가로 넘침0·서빙 바이트 일치. 새 이미지 뒤 동일 자산 SHA 재확인 |
| SYSTEM 진행 저널·확정된 점유·실패/롤백/중단 복구 | 집중 84 통과 | 신규24=실제PG12+Memory12, 기존60. 기존 계약 충돌1·기존 JS load 실패1은 아래 별도 |
| SYSTEM 실패 결과의 실제 JS 소비 | 독립 1 통과 | 원본 enterprise.js 전체를 로드. 기존 검사기·기대값 변경0 |
| 실제 PG→HTTP 응답 대기→제품 SSE→native 실시간 컴포넌트 | 도구 호출1·fresh 이벤트3 | 별도 PG 독자가 응답 전 시작만 조회. 실제 화면 ‘진행 중’→응답→업무 반영. 정상 엔진 COMPLETED/DONE, 실제 응답 저장 |

숫자는 서로 다른 집중 범위이고 합산한 전체 회귀 결과가 아니다. 이전 2673 전체 통과는 당시 판본의 근거로만 유지한다. 각 단계의 초기 실패도 삭제하지 않았다.

## 화면과 실제 실행 증거

- [현재 실제 포털 1440](evidence/native-live/mcp-connections-1440.png), [1024](evidence/native-live/mcp-connections-1024.png), [참고 화면과 나란한 비교](evidence/native-live/comparison.png).
- [실제 HTTP 응답 대기 중](evidence/native-system-progress/system-tool-running-1440.png), [응답과 업무 반영 뒤](evidence/native-system-progress/system-tool-finished-1440.png).
- [응답 전 PG 상태](evidence/native-system-progress/blocked-pg-proof.json), [응답 뒤 PG 상태](evidence/native-system-progress/final-pg-proof.json), [실제 SSE 이벤트](evidence/native-system-progress/actual-sse-frames.json).
- [최종 집중 SYSTEM 결과](evidence/system-progress-final-result.json), [배포 이미지/소스 SHA](evidence/final-deployment.json), [서비스·자산·정리 상태](evidence/final-cleanup.json).

루트는 최종 포털 1440/1024·참고 비교와 SYSTEM 진행/종료 PNG를 직접 확인했다. ProcessGPT/Dify 이미지는 출처·SHA가 있는 보존 캡처이며 이번 최신 서비스에 접속해 다시 찍었다고 주장하지 않는다. 전역 색상/CSS는 이번에 수정하지 않았다. 합성 SYSTEM 도구에는 등록 표시 이름이 없으므로 ‘도구 표시 이름 기록 없음’을 정직하게 보여 준다. 이 격리 컴포넌트 증거는 운영 A/B/C의 모든 단계 live PNG나 전체 시각 인수를 대신하지 않는다.

## 실패를 보존한 이유

실제 포털 첫13검사는 hidden 스타일 충돌을 놓쳤다. 루트 PNG 검토가 이를 발견했고 강화한 가시성 검사는 수정 전 실패했다. MCP 영역 전용 CSS 뒤18검사가 통과했다. 격리 OAuth 첫 콘솔 오류는 수집기의 secrets API/아이콘/이름 사전 누락이었다. 실제 자원을 제공한 뒤 통과했으며 콘솔 기대를 완화하지 않았다.

SYSTEM 첫 도구 시작은 실제 업무 트랜잭션 안에 있었다. 별도 진행 기록만 추가했을 때는 post-commit SYSTEM consumer=None이라 소유권 검사에 걸리는 기존5회귀가 발생했다. 짧은 점유 저장·커밋 뒤 업무 전이를 시작하고 부모 전이 내부 호출은 커밋 뒤 실행하여 해결했다. 업무 상태를 통째로 중간 커밋하거나 승인 단계를 추가하지 않았다. 중단 뒤 응답 없는 옛 호출은 ‘응답 미확인’으로 종료하고 효과 재시도 키는 보존한다.

기존 `test_failed_attempt_trace.py::test_inside_an_open_transition_nothing_is_rolled_back_so_nothing_is_written_twice`는 부모 안 즉시 실행·되돌림 없음이라는 옛 계약을 기대해 **1건 실패**한다. 원본 시험을 고쳐 통과시키지 않았다. 새 계약은 부모 안 외부 호출0→부모 커밋→확정된 점유→실행 실패 시 실제 업무 롤백이다. 신규 Memory/PG 검사에서 시작/끝/감사 각각1회·실제 오류 응답 보존·출력 원복·롤백 표시를 확인했다. 이 구계약 충돌을 전체 통과로 숨기지 않는다.

기존 `tests/js/render_task_detail.js`는 LF 전용 추출 정규식과 실제 CRLF enterprise.js가 불일치해 제품 로직 전 로드에 실패했다. 검사기와 기대값을 수정하지 않았고, 전체 실제 JS를 로드한 독립 소비자 검사1통과를 별도 남겼다. 신규 nested 시험 작성에서 감사 명칭을 잘못 적은 첫2실패도 보존하고, 실제 공식 명칭 MCP_EFFECT_FAILED와 정확1회 조건으로 바로잡았다.

SYSTEM 최초 수집기는 제품 shell CSS를 독립 화면에 넣으면서 본문이 짧은 grid 행에 잘렸다. DB/SSE 결과가 통과했더라도 첫 PNG를 UI 성공으로 보지 않았다. 원본을 보존하고 검증용 틀의 레이아웃·실제 가시성만 수정하여 같은 경계만 다시 수집했다. 제품 소스는 불변이고 최종 콘솔/가로 넘침0이다.

## 배포와 남은 외부 경계

process 마지막 기동은 **2026-10-12T18:04:27.714026201Z**, RestartCount0이며 실제 poll ready/health200이다. portal은 **2026-10-12T15:25:25.486708989Z**에서 재생성하지 않았다. 기존29서비스·등록 서버5개·Google 등록0을 유지했다. Git 밖 영속 암호화/실행 인증 키를 설치했고 값은 기록하지 않았다. 별도 임시 PG는 소유자 라벨 확인 후 제거했고 helper 포트와8097은 닫혔다. 프로젝트 데이터 볼륨·컨테이너가 참조하는 작업 트리는 삭제하지 않았다.

공식 Google MCP 프리셋과 표준 OAuth 구현은 있으나 HYD의 Google OAuth 앱 등록·본인 동의·실제 Google 도구 실행은 **0**이다. ChatGPT Google 연결은 HYD로 이전되지 않는다. [운영자가 한 번 준비하는 설정과 학생 동선](operator-connections.md)을 구분한다. 모든 서비스가 Google 로그인 하나로 연결된다는 뜻이 아니다. HTTP 무인증/접속키/표준 OAuth를 지원하며 임의 서비스 전용 인증이나 모든 전송 방식의 자동화를 약속하지 않는다.

개발 발행은 명시 경로 커밋→요청 원격 브랜치 pull --rebase→push 순서다. 발행 뒤 SHA·청결 상태·보호 경로0·제품 바이트 불변은 루트 `.evidence/easy-mcp-20261013/publication.json`에 기록한다. 새 외부 계정 승인이나 실습랩 전체 수행을 발행의 선행 조건으로 다시 추가하지 않는다.
