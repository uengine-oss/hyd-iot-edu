# Google 회의 연결 준비 — 로컬 MCP 검증과 OAuth 대기

2026-10-12, 사용자 위임에 따라 Codex Sol 6.1이 로컬 HYD 연결을 준비했다. HYD 워커용 사용자 OAuth와 Google 외부 쓰기는 하지 않았다. 아래 로컬 준비 작업에서 교재·lecture-deck·기존 meeting 예제·기존 backend 파일은 수정하지 않았다.

**학생 시연의 일반 동선은 포털 로그인이나 포털 Google OAuth가 아니다.** 학생이 Claude Code 등에서 사용할 MCP를 준비·인증하고, 강사가 선택한 이미 인증된 MCP 설정을 포털의 기존 T5 서버 등록 경로에 넣어 연결·호출을 시연한다. 기존 registry는 URL/stdio와 headers/env, `${SECRET:KEY}` 설정을 지원한다. 인증된 서버의 실제 주소·도구·접속 설정을 확인해 등록하는 동선이며, 학생 포털 로그인이나 모든 MCP에 GCP 프로젝트를 요구하지 않는다.

이 문서의 **직접 Google REST API를 호출하는 로컬 MCP 서버는 하나의 선택지**다. 아래 GCP Desktop client 절차는 이 선택지를 인증할 때만 적용한다. 다른 인증 완료 MCP를 등록하는 일반 동선의 필수 조건이 아니다. 현재 이 선택지는 OAuth client가 없어 로그인만으로 자동 연결할 수 없으며, 포털 로그인 UI나 포털 Google OAuth UI를 추가한 구현도 아니다. ChatGPT 앱 계정 연결과 HYD 서버 등록은 별개이므로 앱 연결만으로 HYD 인증 완료를 주장하지 않는다.

## 최신 ChatGPT 연결과 HYD 인증의 구분

사용자는 **ChatGPT Google MCP를 다른 Google 계정으로 연결했다**고 알렸다. root가 해당 연결의 Drive 파일명 검색을 읽기 전용으로 실행해 검색 성공·일치0건을 확인했다. 본문 읽기0·쓰기0이다. 이 검색에서 일치 파일이 없었다는 사실만으로 Drive 전체가 비었거나 필요한 자료가 없다고 단정하지 않는다. 이 연결을 통해 Calendar 일정 생성이나 회의 흐름을 실행한 것도 아니다.

ChatGPT의 연결 계정 변경에 아래 GCP/OAuth client 준비가 필요한 것은 아니다. 계정 변경 질문에 로컬 HYD 준비 절차를 안내했던 혼동을 정정했다. **ChatGPT 연결은 연결된 앱의 로그인이고, 아래 절차는 별도 Windows HYD MCP 서버가 사용할 OAuth다.** ChatGPT connector의 token을 로컬 HYD 워커로 내보내거나 두 인증이 자동 공유된다고 가정하지 않는다. 이번 ChatGPT Drive 검색은 로컬 HYD OAuth·Docker→host MCP 연결·회의 완주의 증거가 아니다.

## 준비 결과와 현재 상태

| 항목 | 결과 | 근거 |
|---|---|---|
| 실제 Google API를 호출하는 MCP 구현 | 준비 | `students/_template/google_meeting_mcp/server.py` — Google OAuth AuthorizedSession과 기존 FastMCP 사용 |
| 사용자 브라우저 OAuth CLI | 준비 | 같은 폴더 `auth.py`, `scripts/google_meeting_auth.py` — 공식 InstalledAppFlow·PKCE·loopback 임시 포트 |
| 입력·결과와 회의 예제 연결 계약 | 준비 | `meeting-contract.json`, `README.md` — 원래 BPMN 승인/반려/지연 가지와 실제 DB 칸을 대조 |
| Google 전용 계약 시험 | **45 통과** | `google-meeting-mcp/pytest.xml`의 Google test cases |
| 기존 meeting kit 포함 회귀 | **61 통과·경고 1, 2.54초, exit 0** | 같은 폴더 `pytest.log/xml` |
| 실제 로컬 HTTP·MCP 무인증 검사 | **8/8 통과** | `summary.json`, `tools.json`, `server.log` |
| 기본 사용자 OAuth client·token 파일 | **둘 다 없음** | 파일 존재 여부만 검사, 내용은 읽지 않음 |
| custom token·local MCP key 환경변수 | **둘 다 없음** | 키 존재 여부만 검사, 값 출력 없음 |
| 로컬 HYD Google OAuth·읽기·일정 생성 | **미완료** | 사용자 클라이언트·로그인 대기; 실제 외부 쓰기 0 |
| ChatGPT Google MCP의 다른 계정 연결 | **사용자 연결 알림·Drive 파일명 검색 성공** | 일치0·본문읽기0·쓰기0. 로컬 HYD 인증과 별도 |
| 실제 HYD process 등록·Docker→host 연결 | **미실행** | 새 서버 주소를 준비했으며 실제 스택 등록/실행은 root 담당 |

증거 루트는 `D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012/google-meeting-mcp/`다. 무인증 프로브는 기존 인증 파일을 사용하지 않고 저장소 밖 임시 폴더에 **없는 파일 경로**를 지정했다. 자신이 시작한 서버만 종료했다. 프로브의 8개 조건은 health HTTP 503, 실제 HTTP MCP 도구 5개, 생성의 읽기 표시 false, 무인증 읽기 MCP 오류 503, 기본 생성 오류 403, 중복 입력 오류 422, OAuth 상태 exit 2, 소유 서버 종료다.

처음 넓힌 회귀는 88 통과·1 실패였다. 실패는 `tests/test_mcp_check.py:299`의 기존 dmn/enterprise 도구 개수 기대 30과 현재 33의 차이이며, 새 Google 파일은 이 집계 대상에 포함되지 않는다. root에 전달했고 여기서 기대값을 완화하지 않았다. 실패 원문은 작업 세션 출력에 보존되며, 최종 이 범위 시험 로그는 위 61 통과 로그다.

## 구현 범위와 실패 계약

Drive의 `search_files`, `read_file`은 읽기만 한다. Google Doc의 text/plain export, UTF-8 텍스트, 텍스트 PDF를 지원한다. 응답·본문 크기를 제한하고 원본 URL과 untrusted content 표시를 돌려준다. 임의 주소·SQL·전체 Google REST 호출 도구를 노출하지 않는다.

Calendar의 `free_busy`는 실제 참석자·자원 캘린더의 busy 구간을 읽는다. 누락·권한 오류가 있는 캘린더를 빈 시간으로 보고하지 않는다. `get_event`는 실제 `required=true` 명단을 입력받아 해당 일정의 참석 응답과 대조한다. 비어 있는 명단·중복 입력은 오류, 누락·거절·무응답·tentative는 false이며 선택 참석자의 거절만으로 필수 미달로 바꾸지 않는다. 취소·참석자 결과 생략도 확정을 막는다.

유일한 쓰기 도구 `create_event`는 `readOnlyHint=false`이며 기본 403이다. `--allow-create`와 명시한 `--write-calendar`를 모두 요구한다. HTTP 서버를 켜거나 계약을 읽거나 OAuth 로그인할 때 일정이 만들어지지 않는다. 실제 실행에서는 Google `sendUpdates=all`로 초대를 요청하므로 주관자 승인 뒤 시스템 task에서만 호출한다. Gmail, Drive 생성·공유 변경, Calendar 수정·삭제는 구현하지 않았다.

승인한 인스턴스·task의 고정 idempotency key로 event ID를 결정하고 생성 전에 조회한다. 동일 키·다른 입력, 기존 일정의 수동 수정·취소는 409다. 생성 후 통신 타임아웃은 결과 미상 오류이고, 무조건 POST를 반복하지 않는다. 다음 호출에서 같은 ID를 조회하고 내용까지 대조한다. Google의 분산 ID 충돌 탐지 제약이 있어 절대적인 exactly-once 보장으로 주장하지 않는다.

오류에는 `trace_id`, 안전한 오류 종류, status와 upstream status만 넣는다. Google 오류 응답 본문·인증 URL·토큰을 로그에 넣지 않는다. FastMCP의 `ToolError`로 **MCP `isError=true`**를 전달하므로 HYD `service_parts.py`의 실패 분기에서 멈출 수 있다. 단순 `{result:error}` 성공 응답만 반환하는 형태는 사용하지 않는다. HTTP·네트워크·OAuth 오류를 성공으로 바꾸는 시험 완화는 없다.

## 로컬 HYD MCP를 인증할 때 필요한 조작

이 절은 **HYD 워커용 별도 서버 연결**에만 적용한다. ChatGPT Google 연결 계정을 바꾸는 절차로 안내하지 않는다.

사용 가능한 Google Cloud 프로젝트에서 Calendar API·Drive API를 사용 설정하고, Google Auth Platform에 동의 화면을 준비한다. 개인 계정의 External 테스트 앱이면 로그인할 계정을 Test users에 추가한다. **Desktop app OAuth client JSON**을 저장소 밖 `%LOCALAPPDATA%/HYD/google-meeting/client.json`에 다운로드한다. 계정 비밀번호나 JSON 내용을 전달할 필요는 없다. 기존 관리자가 제공한 수업용 클라이언트를 사용할 수 있다. 프로젝트 생성·결제·전역 SDK 설치는 이 작업이 실행하지 않았다.

그다음 `scripts/google_meeting_auth.py login --client-file <저장소 밖 client.json 경로>`를 프로젝트 Python으로 실행하면 공식 Google 브라우저 창이 열린다. 사용자가 계정과 앱 이름·읽기 권한을 직접 확인하고 동의한다. token은 로컬 AppData에만 저장된다. 부분 동의·취소·시간 초과는 실패로 남긴다. 기본 로그인은 읽기만 요청하며, 나중에 실제 일정 생성이 명시적으로 승인되면 `--allow-create`로 events scope를 추가한다. 로그인 성공은 실제 자료 조회나 회의 완료를 뜻하지 않는다.

구체적 명령과 화면 순서는 [서버 README](../../../../students/_template/google_meeting_mcp/README.md)에 있다. Windows 호스트 서버는 Calendar **8511**, Drive **8512**를 사용하고, Linux process에서 `http://host.docker.internal:<포트>/mcp`로 연결한다. 이때 호스트 바인딩 `0.0.0.0`과 별도 `HYD_GOOGLE_MCP_KEY`가 필요하다. 포털에는 그 로컬 접속 비밀을 저장하고 `${SECRET:GOOGLE_MEETING_MCP_KEY}` 헤더로 연결한다. Google OAuth token을 포털이나 ChatGPT connector에서 내보내지 않는다.

root가 인증 뒤 실제 자료 검색·읽기와 참석자·회의실 free/busy를 확인하고 도구 목록·입력 스키마를 실측해야 한다. meeting-contract의 추가 typed context 값과 실제 승인안을 준비한 후 흐름 복사본을 등록한다. 현재 원래 예제에 없는 값까지 채워져 가져오기·완주가 끝났다고 기록하지 않는다. 주관자 반려/지연에서 일정 생성이 없어야 하고, 실제 승인 뒤 생성·초대·필수 참석자의 거절 또는 무응답 가지를 기록해야 Google 회의 완주를 판정할 수 있다.

## 공식 근거와 참고 코드

- [Google Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app): PKCE, loopback IP redirect와 브라우저 사용자 승인.
- [Google Python OAuth helper](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html): InstalledAppFlow와 로컬 callback 서버.
- [Google Calendar Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python): API enable·동의 화면·Desktop OAuth client 준비.
- [Calendar events.insert](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [events.get](https://developers.google.com/workspace/calendar/api/v3/reference/events/get), [freebusy.query](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query): 실제 필수 입력·응답·초대와 시간 조회 계약.
- [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list), [files.export](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export): 기존 문서 읽기 권한과 실제 검색·본문 export 계약.
- [Google 공식 Calendar remote MCP](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server): 별도로 존재하는 Developer Preview endpoint `https://calendarmcp.googleapis.com/mcp/v1`. Preview 등록·API enable·OAuth가 필요하며 실제 접속은 아직 검증하지 않았다. Google 소유 CLI의 현재 native MCP 유무와는 별개다.

로컬 참고는 ProcessGPT monorepo `openspec/specs/completion_mcp-server-config/spec.md`의 카탈로그·URL transport 명세와 ontology-studio `backend/src/modules/ontology_mcp/adapters.py`의 안전한 출력·출처 경계다. HYD 기존 `mcp_table_reader/server.py`의 FastMCP·봉투·healthz를 재사용 가능한 패턴으로 대조했다. 이 참고 저장소나 기존 서비스의 소스는 수정하지 않았다.
