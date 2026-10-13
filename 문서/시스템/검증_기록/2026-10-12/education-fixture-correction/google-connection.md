# Google 연결 준비를 우리가 맡는 실제 경로

사용자에게 모르는 서버 URI나 OAuth JSON 위치를 찾아 달라고 요구하지 않는다. 서버 코드·주소·프로세스 설정은 우리가 준비한다. 다만 Google이 발급하는 앱 등록과 본인 계정 동의를 대신 만들거나 기존 ChatGPT 앱 토큰을 추출할 수는 없다. 현재 K3의 Google 실행은 완료되지 않았다.

## 가장 짧은 선택: 기존 로컬 Google MCP

현재 clean-venv에 fastmcp2.13.0.2/google-auth2.61.0/google-auth-oauthlib1.5.0/requests2.34.2/pypdf5.1.0/tzdata2026.5가 설치되어 있다. 추가 설치 없이 기존 `scripts/google_meeting_auth.py`와 `students/_template/google_meeting_mcp/server.py`를 사용할 준비가 있다. 패키지 metadata와11개 source SHA/참고4repo HEAD는 로컬 `.evidence/education-fixture-correction-20261012/google/preparation-proof.json`에 남겼다. 이번에는 인증파일 내용·로그인·서버 시작·등록·조회·쓰기·시험을 실행하지 않았다.

우리가 정할 서버는 Calendar8511과 Drive8512이며 HYD process에서 사용할 주소는 각각 `http://host.docker.internal:8511/mcp`, `http://host.docker.internal:8512/mcp`다. **예정 주소이며 현재 가동/등록 성공을 뜻하지 않는다.** Docker에서 호스트로 접근하려면 호스트 서버를0.0.0.0에 바인딩해야 하므로 별도의32자 이상 랜덤 `HYD_GOOGLE_MCP_KEY`와 필요한 호스트 접근 제한을 우리가 설정한다. Google OAuth token과 이 로컬접속 key는 별개이며 Google token을 포털 헤더에 복사하지 않는다.

### 실제 작업 순서와 사용자 참여 지점

1. 우리가 연결용 Google OAuth 앱을 준비한다. 앱 소유 Cloud 프로젝트가 아직 없으므로 본인/기관이 관리하는 Google Cloud Console에서 새 프로젝트를 만드는 화면부터 안내해야 한다. 사용자에게 기존 JSON 파일을 찾아오라고 하지 않는다. [Cloud Console](https://console.cloud.google.com/)에서 프로젝트 선택→새 프로젝트, API 및 서비스→라이브러리→Google Drive API/Google Calendar API 사용, Google Auth Platform→시작하기에서 앱 이름 `HYD 교육 회의 연결`과 본인 지원 연락처를 지정한다. 개인 계정이면 External/testing 및 본인 계정을 test user로 등록한다. Clients→Create client→Desktop app을 선택하고 Download JSON을 누른다. Google이 만든 파일은 우리가 지정하는 Git 밖 `%LOCALAPPDATA%/HYD/google-meeting/client.json`에 보관한다. 이 클릭은 계정/프로젝트 소유자 권한이 필요하며 지금 대신 실행하지 않았다. 조직이 이미 관리하는 앱을 제공할 수 있으면 이 앱 준비는 학생마다 반복하지 않는다. [Google installed-app OAuth 계약](https://developers.google.com/identity/protocols/oauth2/native-app).
2. 앱 준비 후 우리가 아래 login helper를 실행하면 사용자에게 Google 브라우저 계정 선택/권한 동의 창이 열린다. **이때 본인 계정과 권한을 직접 확인하는 동의가 필요하다.** 앱 준비가 없는 현재 시점에 “로그인 버튼만 누르면 된다”는 안내는 정확하지 않다. 읽기 scope는 `drive.readonly`, `calendar.events.readonly`, `calendar.events.freebusy` 세 개다. 전체 Drive 읽기 권한은 해당 계정이 접근 가능한 파일을 읽을 수 있으므로 교육용 계정을 쓰거나 대상 자료를 명확히 제한한다. Gmail·Drive 파일변경·공유권한 변경은 요청하지 않는다.
3. 우리는 read-only Calendar/Drive 서버를 실행하고 HYD 포털→도구(MCP)→비밀 값에 **로컬 MCP 접속 key**만 저장한다. 서버 등록에서 이름 `google-meeting-calendar`/`google-meeting-drive`, HTTP(streamable), 위 두 주소, 헤더 `Authorization=Bearer ${SECRET:GOOGLE_MEETING_MCP_KEY}`를 넣어 검사 후 등록한다. 이름은 준비안이며 실제 저장된 이름을 최종 mapping에 사용한다. process에서 두 끝점에 닿고 tools/list 검사까지 통과해야 등록 성공이다. 개인 CLI 앱 격리를 해제하지 않는다.
4. 실제 읽기 도구 schema와 계정의 자료/캘린더 접근을 확인한 뒤 실제 회의 준비 사본을 만든다. 사용자에게 서버 URI를 묻지 않고 우리가 등록 화면의 값으로 준비한다. 초대 전에는 사용자에게 실제 참석자·날짜·시간·주관자 승인 대상을 보여 준다.
5. 일정 생성이 승인되면 별도 `--allow-create` 로그인으로 `calendar.events` 권한을 요청하고 해당 실제 calendar ID만 `--write-calendar`로 허용한다. 읽기에서 초대 권한으로 자동 승격하지 않는다. 초대는 사람 주관자 승인 뒤 system task에서만 `sendUpdates=all`로 Google에 발송한다. 실제 회의실 자원 주소가 없으면 꾸며내지 않는다. Calendar의 event ID와 필수 참석자 응답을 실제로 다시 읽어 미확정/확정을 보고해야 K3 완료 근거가 된다.

실행 준비 명령(아직 실행하지 않은 절차):

```powershell
$py = 'D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/clean-venv/Scripts/python.exe'
$clientFile = Join-Path $env:LOCALAPPDATA 'HYD/google-meeting/client.json'
& $py scripts/google_meeting_auth.py login --client-file $clientFile
# 서버 key는 우리가 안전하게 생성/보관하며 콘솔 출력하지 않는다.
& $py -m students._template.google_meeting_mcp.server --service calendar --host 0.0.0.0 --port 8511
# Drive는 별도 숨긴 서버 프로세스로 실행한다.
& $py -m students._template.google_meeting_mcp.server --service drive --host 0.0.0.0 --port 8512
```

현재 구현은 login helper의 PKCE·loopback callback·outside-Git token 저장·scope 검사와 API AuthorizedSession의 refresh를 갖고 있다. OAuth 앱 준비와 본인 계정 동의가 인증의 선행조건이며, 이후 실제 자료/캘린더 접근도 확인해야 한다. 새 서버를 개발하거나 사용자에게 토큰 문자열을 복사시킬 필요가 없다. Cloud 앱의 Data Access에는 위 읽기 scope를 설정하며 쓰기 승격 시 calendar.events를 별도 확인한다. 호스트 서비스 시작/키 생성/포털 등록은 루트가 실제 실행 범위와 잠금을 관리한다.

## 공식 원격 MCP 선택은 가능하지만 현재 더 짧지 않다

서버 주소는 이미 공식 공개값이다: Drive `https://drivemcp.googleapis.com/mcp/v1`, Calendar `https://calendarmcp.googleapis.com/mcp/v1`. 사용자에게 주소를 찾으라고 할 필요가 없다. 다만 공식 문서는 Developer Preview 가입, Cloud 프로젝트/API·MCP 서비스 활성화와 OAuth client를 요구한다. HYD 현재 HTTP client는 OAuth discovery/browser callback/refresh lifecycle을 지원하지 않으므로 주소만 등록해서 동작한다고 주장하지 않는다. 공식 [Drive 설정](https://developers.google.com/workspace/drive/api/guides/configure-mcp-server), [Calendar 설정](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server).

원격 Drive 권한 안내는 drive.readonly/drive.file이며 Calendar 설정 안내는 calendar.calendarlist.readonly/calendar.events.freebusy/calendar.events.readonly다. 이 안내의 Calendar 읽기 scope만으로 실제 초대 생성 권한을 확보했다고 취급하지 않는다. 로컬 `free_busy`와 원격 `suggest_time` 등 도구 계약은 다르므로 기존 mapping을 재사용한다고 단정할 수도 없다. 원격을 택하면 HYD의 정식 OAuth client adapter부터 준비해야 한다.

## 참고 구현을 실제로 읽은 결과

ProcessGPT 모노레포 `.gitmodules`는 frontend/completion/memento를 별도 서비스로 연결한다. 해당 로컬 snapshot의 Vue `DriveTab.vue`는 `/memento/auth/google/url`로 이동하고 callback을 `/memento/auth/google/callback`에 넘긴다. Memento `app/api/auth.py`는 **tenant_oauth에 먼저 존재하는 client_id/redirect_uri**로 인가 URL을 만든다. 따라서 참고 제품도 앱 등록 없이 Google 연결이 되는 것은 아니다. 이 경로는 Drive 연동으로 generic MCP서버 OAuth와 동일하지 않다. snapshot의 `state=tenant_id`를 그대로 복사하지 않고 새 HYD UI를 만들 경우 난수state·PKCE·callback 소유자/tenant binding을 검증해야 한다. 참고에서 credential을 조회하거나 가져오지 않았다.

ontology-studio `backend/src/modules/ontology_mcp/server.py`는 FastMCP의4개 읽기 전용 ontology 도구와 sources 출처를 제공하며 `__main__.py`는 stdio/http/sse 실행을 선택한다. 그 모듈에는 Google OAuth 로그인 구현이 없다. 이를 Google 로그인 해법이라고 인용하지 않는다. [ProcessGPT](https://github.com/uengine-oss/process-gpt)·[ontology-studio](https://github.com/uengine-oss/ontology-studio)의 source 읽기 근거는 별도SHA로 남겼으며 현재 최신 원격 배포의 완전 동등성을 주장하지 않는다.

## 비용·외부 전송·필수 통제

현재 설치0/유료 서비스 가입0/Cloud 프로젝트 생성0/Google 권한 변경0이다. 이미 설치된 Python package만으로 로컬 경로를 준비할 수 있어 추가 유료 AI 호스트는 필요하지 않다. Google은 [Drive API 표준 사용](https://developers.google.com/workspace/drive/api/guides/limits)과 [Calendar API 표준 사용](https://developers.google.com/workspace/calendar/api/guides/quota)에 추가 비용이 없다고 안내한다. 실제 quota/고속 확장 정책과 공식 Preview 조건은 실행 시 적용된다. Cloud billing 활성화나 유료 API 사용은 이 조사에서 수행하지 않았다.

로그인 때 계정동의/code교환/refresh는 Google accounts/oauth2 끝점과 로컬 callback 사이에서 이루어진다. 실제 자료 읽기는 Google API→로컬 MCP→HYD 도구 결과로 들어간다. 나중에 에이전트가 요약하면 해당 자료가 구성된 LLM 제공자에게 전달될 수 있으므로 실행 전 모델/자료 범위를 확인한다. 이번 조사에는 Google 자료·LLM 전송0이다. 쓰기 시에는 제목·시간·참석자·회의실·첨부 링크가 Google Calendar에 전송되고 참석자에게 실제 초대 알림이 발송된다. Drive 공유권한은 자동 변경하지 않는다.

기존 ChatGPT Drive profile 인증 성공은 재호출하지 않았다. 앱의 private token 추출/다른 client token 재사용/ignoreapps 해제는 하지 않는다. Google 인증·K3 성공을 꾸미거나 교육용 로컬 데이터를 외부 Google 성공으로 바꾸지 않는다. 사용자에게 남는 설명은 “서버와 설정은 준비할 수 있고, Google이 앱에 접근권한을 주는 본인 계정 화면은 직접 확인해야 한다”이다.
