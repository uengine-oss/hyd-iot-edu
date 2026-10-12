# 회의 예제용 실제 Google MCP 연결 준비

이 서버는 Google Calendar·Drive REST API를 FastMCP로 연결한다. 로컬 도구 계약과 실패 검증은 준비했으며, 현재 사용자 OAuth 클라이언트·로그인·실제 Google 조회는 확인하지 않았다. 계정 비밀번호를 전달하지 않는다. 사용자가 Google 공식 브라우저 창에서 로그인하고 권한을 선택한다.

`example_meeting`의 가상 메일·회의실·Drive 링크는 실제 호출에 사용하지 않는다. 원래 예제 파일은 설계 참고용으로 보존한다. 이 폴더의 `meeting-contract.json`은 실제 도구에 맞춘 입력·결과 경로와 값의 출처이며, 추가 실행 값이 아직 없는 상태에서 가져올 완성 흐름은 아니다.

## 1. Google에서 한 번 준비할 것

1. [Google Cloud 콘솔](https://console.cloud.google.com/)에서 사용 가능한 기존 프로젝트를 선택한다. 프로젝트가 없다면 사용자가 만들거나 관리자의 수업용 OAuth 클라이언트를 받는다. 이 작업은 프로젝트 생성·결제 설정·전역 SDK 설치를 실행하지 않는다.
2. 콘솔의 API 라이브러리에서 Google Calendar API와 Google Drive API를 사용 설정한다. Google Auth Platform에서 앱 이름·지원 연락처·대상을 정한다. 개인 Gmail은 External, 테스트 상태라면 로그인할 계정을 Test users에 등록한다. 조직 계정은 관리자가 허용한 설정을 따른다.
3. Google Auth Platform → Clients → Create client → **Desktop app**으로 만든다. JSON 다운로드 파일을 저장소 밖, 예를 들어 `$env:LOCALAPPDATA\HYD\google-meeting\client.json`에 둔다. 파일 내용·토큰을 채팅·포털 설정·Git에 넣지 않는다. [Google Python 빠른 시작](https://developers.google.com/workspace/calendar/api/quickstart/python)에 해당 화면 순서가 있다.

기본 로그인은 Drive 문서 검색·본문 읽기용 `drive.readonly`, 일정 읽기용 `calendar.events.readonly`, 빈 시간용 `calendar.events.freebusy`를 요청한다. Drive의 기존 문서 본문을 검색·읽으므로 `drive.readonly`를 사용하며 이는 Google이 분류한 **restricted scope**이다. `drive.file`은 사용자가 앱으로 선택하거나 공유한 파일에 한정되어 현재 전체 접근 가능 문서 검색 계약을 대신하지 않는다. 공개 배포·조직 사용 가능 여부는 실제 계정 정책과 Google 심사 조건을 확인해야 한다. [Google Drive scope 설명](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

## 2. 사용자 브라우저에서 로그인

저장소 루트의 PowerShell에서 실행한다. Python 경로는 이 환경의 프로젝트 venv를 가리킨다. 다른 환경에서는 그 프로젝트 venv 경로로 바꾼다.

```powershell
$py = 'D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe'
& $py -m pip install -r students/_template/google_meeting_mcp/requirements.txt
& $py scripts/google_meeting_auth.py status
& $py scripts/google_meeting_auth.py login --client-file "$env:LOCALAPPDATA/HYD/google-meeting/client.json"
```

`status`는 인증 파일이 없으면 exit 2를 반환한다. `login`은 Google의 공식 로그인 페이지를 기본 브라우저에 열고, 임시 `127.0.0.1` 포트로 승인 응답을 받는다. PKCE를 사용하고 180초 안에 응답이 없으면 실패한다. 로그인 URL·인증 코드·토큰은 콘솔에 출력하지 않는다. 로그인 페이지가 열리지 않으면 실패 상태를 유지하고 기본 브라우저 설정을 확인한다. 사용자 자신이 계정과 동의 화면의 앱 이름·요청 권한을 확인한다. [Google Desktop OAuth·PKCE·loopback 계약](https://developers.google.com/identity/protocols/oauth2/native-app), [공식 Python OAuth helper](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html).

토큰은 기본적으로 `%LOCALAPPDATA%/HYD/google-meeting/token.json`에만 저장된다. `GOOGLE_MEETING_TOKEN_FILE`로 저장소 밖의 다른 파일을 지정할 수 있다. 인증 파일을 읽거나 저장할 때 Git checkout 안의 경로는 거절한다. Unix에서는 파일 권한 0600으로 저장하며 Windows에서는 사용자 AppData의 접근 권한을 따른다. 읽기 scope가 줄어든 부분 동의는 성공으로 저장하지 않는다. scope를 추가하려면 다시 로그인한다.

로그인 성공 출력은 **인증 파일 준비 상태**다. `google_read_verified=false`는 계속 유지하며, 실제 읽기 성공과 구분한다. 읽기만으로 시작하고 일정 생성이 명시적으로 승인된 뒤에만 `login ... --allow-create`로 `calendar.events` 권한을 추가한다. 이 플래그 자체가 주관자의 회의 승인이나 일정 생성 호출을 대신하지 않는다.

## 3. 서버 시작과 포털 등록

로컬 검사에는 기본 loopback 바인딩을 쓴다.

```powershell
& $py students/_template/google_meeting_mcp/server.py --service calendar --port 8511
# 다른 터미널
& $py students/_template/google_meeting_mcp/server.py --service drive --port 8512
```

process 컨테이너에서 연결하려면 호스트 주소로 닿는 바인딩이 필요하다. `HYD_GOOGLE_MCP_KEY`에 별도 32자 이상 로컬 접속 비밀을 환경변수로 넣고 `--host 0.0.0.0`으로 실행한다. 이 값은 Google OAuth 토큰과 다르다. 방화벽에서는 수업의 process가 접근할 주소만 허용한다. 포털 비밀 값에 **같은 로컬 접속 비밀**을 `GOOGLE_MEETING_MCP_KEY`로 저장하고 등록 헤더에 `Authorization=Bearer ${SECRET:GOOGLE_MEETING_MCP_KEY}`를 적는다. Google OAuth 토큰을 포털에 복사할 필요가 없다.

```powershell
# HYD_GOOGLE_MCP_KEY는 사용자/강사가 비밀 환경변수로 먼저 설정한다. 값은 출력하지 않는다.
& $py students/_template/google_meeting_mcp/server.py --service calendar --host 0.0.0.0 --port 8511
# 다른 터미널, 같은 접속 비밀 환경변수를 설정한 뒤
& $py students/_template/google_meeting_mcp/server.py --service drive --host 0.0.0.0 --port 8512
```

| 등록 이름 | HTTP streamable 주소 | 도구 |
|---|---|---|
| `gcal` | `http://host.docker.internal:8511/mcp` | `free_busy`, `get_event` 읽기 / `create_event` 쓰기 |
| `gdrive` | `http://host.docker.internal:8512/mcp` | `search_files`, `read_file` 읽기 |

실제 포털 서버 이름과 주소는 등록 화면에서 확인한다. 연결 검사가 도구 목록을 읽었다고 Google 계정 연결까지 완료된 것은 아니다. 인증 전 `/healthz`는 HTTP 503, 읽기 호출은 MCP `isError=true`와 `AUTH_REQUIRED`·status 503을 반환한다. 인증 파일이 준비된 health 응답에도 `google_read_verified=false`가 있다. 실제 사용자 문서 검색·읽기, 참석자와 회의실 캘린더 빈 시간 조회가 각각 성공해야 연결을 확인할 수 있다.

에이전트는 `readOnlyHint=true`인 읽기 도구만 쓴다. 일정 생성은 포털의 승인 뒤 `svc:mcp-call` 시스템 task에서만 호출한다. 승인 뒤 실제 생성이 허용된 경우 서버를 다음과 같이 재시작한다.

```powershell
& $py students/_template/google_meeting_mcp/server.py --service calendar --host 0.0.0.0 --port 8511 --allow-create --write-calendar primary
```

`primary`는 로그인한 사용자의 기본 캘린더다. 별도 수업용 캘린더라면 실제 ID를 명시한다. 기본 서버에서 생성은 403이며, 지정되지 않은 캘린더도 403이다. 생성 호출은 `sendUpdates=all`로 초대 알림을 요청하므로 **실제 초대가 발송되는 외부 쓰기**다. 현재 준비·시험에서는 이 호출을 실제 Google 계정에 실행하지 않았다. [Google events.insert 계약](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert).

## 4. 회의 흐름의 실제 필드

`meeting-contract.json`을 기준으로 원래 `mapping.json`의 복사본을 채운다. 주요 추가 값은 실제 `calendar_id`, 승인한 시작·종료 시각·시간대, 실제 회의실 자원 이메일, 전체 초대 명단, 필수 참석자 명단이다. 원래 `summary/start/room/attachments` 설계용 입력만으로는 새 도구 필수값을 충족하지 않는다.

`meeting_request.duration_min`으로 종료 시각을 계산하고 승인안에 보존한다. `attendee.required=true`에서 `required_emails`를 만들고, 전체 참석자를 `{email,required}`로 전달한다. `room_id`를 메일로 추정하지 말고 실제 자원 캘린더 주소를 사용한다. `proposal.docs`의 `{title,link}`는 실제 Google 문서 링크를 확인한 뒤 `{title,file_url}`로 바꾼다. 문서 링크를 붙이는 것은 Drive 공유 권한을 변경하지 않으므로 참석자 접근 권한도 별도로 확인한다.

일정 생성 결과 경로는 **`document.event_id`**, 참석 응답 확인 결과는 **`document.all_required_accepted`**(Boolean)다. 한 사람의 응답 문자열을 전체 수락으로 쓰지 않는다. 비어 있는 필수 명단·중복 명단은 입력 오류이고, 누락·거절·무응답·tentative는 false다. 선택 참석자 거절만으로 false로 바꾸지 않는다. 취소된 일정·잘린 참석자 결과는 확정할 수 없다. [Google events.get](https://developers.google.com/workspace/calendar/api/v3/reference/events/get).

원래 흐름의 `approval == '승인'` 선, 반려 가지, 4시간 승인 지연 알림, 확인 읽기의 `effect:false`를 유지한다. 추가 실행 값은 실제 DB/조회 결과로 채우고 타입과 출처를 기록해야 한다. 승인 카드의 기존 `slot/reason/score/losers/docs` 이름과 slot 고유성도 유지한다. 이 준비 파일을 만들었다고 그 추가 값이나 실제 흐름 등록이 완료됐다고 주장하지 않는다.

`idempotency_key`는 승인한 **인스턴스·task 실행을 식별하는 고정 값**이며 재시도 때 바꾸지 않는다. 같은 키에 다른 내용이 들어오거나 기존 일정이 수동 수정·취소되면 409 충돌이다. 생성 전 결정적 event ID로 조회하고, 생성 후 타임아웃에는 성공을 보고하지 않는다. 재시도 시 같은 ID를 다시 조회하여 확인한다. Google은 분산 환경의 모든 ID 충돌 탐지를 보장하지 않으므로 절대적인 exactly-once 보장으로 설명하지 않는다.

## 5. 현재 검증과 다음 실제 확인

```powershell
& $py -m pytest tests/test_google_meeting_mcp.py -q
& $py scripts/google_meeting_probe.py --output .evidence/google-meeting-noauth
```

프로브는 임시 폴더의 **없는 인증 파일**만 사용하며 실제 HTTP/MCP 연결·도구 목록·오류 플래그·503·기본 쓰기 403·중복 422를 확인하고 자신이 띄운 서버를 종료한다. 기존 사용자 인증 파일은 읽지 않는다. 단위 시험의 가짜 API는 중복·타임아웃·참석자 응답 등의 계약 검증이며 Google 성공 증거가 아니다.

남은 실제 확인은 사용자의 Desktop OAuth 클라이언트 준비와 브라우저 로그인, 실제 읽기 접근 확인, 값이 채워진 흐름 복사본 등록, 주관자 승인 뒤 일정 생성·초대 및 필수 참석자의 거절/무응답 가지 기록이다. Gmail 도구, Drive 파일 생성·공유 변경, 일정 수정·삭제는 이 서버가 노출하지 않는다.

참고로 [Google 공식 Calendar remote MCP](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server)는 현재 Developer Preview이며 `https://calendarmcp.googleapis.com/mcp/v1`을 안내한다. Preview 등록·API 사용 설정·OAuth를 별도로 요구한다. 이 서버의 로컬 구현과 다른 연결 방법이며, 현재 그 endpoint 접속·권한·도구 계약은 실측하지 않았다. ChatGPT의 Google 연결과 로컬 HYD 인증도 서로 별개다.
