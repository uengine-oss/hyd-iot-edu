# 조사 — process-gpt-lite 화면을 코드로 읽은 사실 (2026-11-16)

대상: 공개 저장소 `uengine-oss/process-gpt-lite`의 기본 브랜치 main 얕은 clone, 커밋 `8062a50`(feat(mining): 관리자가 대화로 필수·옵션을 BPMN 정의에 확정하고, 새 사례는 제안으로 받는다).
받아 둔 자리: `작업/2026-11-16_포털-lite-참고/lite/`. 아래의 `파일:줄`은 모두 이 폴더를 뿌리로 한 경로다.
조사자는 코드 · README · CHANGELOG · openspec만 읽었다. 앱을 띄우지 않았고(로그인과 AI 키가 필요하다), 이 폴더의 파일을 고치지 않았고, 네트워크로 아무것도 받지 않았다.
코드로 확인하지 못한 것은 그 자리에 「코드로 확인 못 함」이라고 적었다.

중요한 전제 두 가지:
- 본판 Process GPT의 화면 코드는 이 clone에 없다. `backends/process-gpt`와 `backends/office-host`는 받지 않은 서브모듈이라 빈 폴더다(`.gitmodules:1-8`). 그래서 「lite가 본판에서 무엇을 뺐는가」는 lite 코드의 주석과 README가 본판을 언급한 자리로만 말할 수 있고, 본판 화면과 줄 대 줄로 대조하지는 못했다(3절).
- lite에는 왼쪽 메뉴가 없다. 최상위 이동은 위 막대 가운데의 탭 3개(채팅 · 프로젝트 · 폴더)뿐이고, 폰 폭(760px 이하)에서만 「홈」 탭이 하나 더 붙는다(`src/components/TopBar.vue:19`, `src/viewport.js:4`). 설정류는 오른쪽 위 아바타를 누르면 열리는 시트의 목록 8줄이다(`src/components/SettingsSheet.vue:26`, `:152`).

---

## 1. 화면 지도

### 1.1 라우트 목록

라우터 정의는 `src/main.js:10-31`에 있다. 로그인하지 않은 사람은 `meta.public`이 아닌 모든 라우트에서 `/login`으로 보내진다(`src/main.js:35-37`). `/`는 `/chat`으로 넘어간다(`src/main.js:30`).

| 라우트 | 화면 파일 | 무엇을 하는 화면인가(한 문장) | 근거 |
|---|---|---|---|
| `/login` | `views/LoginView.vue` | Google 또는 이메일 6자리 코드로 로그인하는 화면이다. | `src/main.js:11`, `src/views/LoginView.vue:76-117` |
| `/auth/done` | `views/AuthDone.vue` | Google 로그인에서 돌아온 토큰을 저장하고 채팅이나 온보딩으로 넘기는 빈 화면이다. | `src/views/AuthDone.vue:8-17`, `:20` |
| `/welcome/age` | `views/OnboardAge.vue` | 처음 들어온 사람에게 생년월일(이메일 앞부분이 이름이면 이름까지)을 한 번 묻는다. | `src/views/OnboardAge.vue:31-50` |
| `/welcome/intro` | `views/OnboardIntro.vue` | 소개 문장 두 줄을 타자기처럼 쓴 뒤 저절로 `/chat?welcome=1`로 넘어간다. 누를 단추가 없다. | `src/views/OnboardIntro.vue:7`, `:11-15` |
| `/chat` | `views/MainView.vue`(mode chat) | 비서와의 대화 하나와, 그 왼쪽의 Home(나에게 온 일 · 알림 · 패널) 칸이다. | `src/main.js:15`, `src/views/MainView.vue:107-127` |
| `/chat/c/:cid` | 같은 화면 | 대화 맥락 라우터가 갈라 놓은 대화 하나만 걸러서 보이고, 그 대화가 만든 파일 더미를 오른쪽 아래에 띄운다. | `src/main.js:16-17`, `src/views/MainView.vue:59`, `:129` |
| `/projects` | 같은 화면(mode project) | 왼쪽에 프로젝트 · 프로세스 인스턴스 목록, 가운데에 새 프로젝트를 시작하는 입력창을 둔다. | `src/main.js:19`, `src/views/MainView.vue:112`, `:130-132` |
| `/projects/:id` | 같은 화면 | 프로젝트(장기 작업용 대화 스레드) 하나의 대화를 보인다. | `src/views/MainView.vue:65` |
| `/projects/p/:instId` | 같은 화면 | 프로세스 인스턴스 하나의 머리(상태 · 진행 · 내 입력 · 산출물)와, 그 인스턴스에 대해 묻는 대화를 한 칸에 보인다. | `src/main.js:18`, `src/views/MainView.vue:61-64`, `:125` |
| `/settings/:page?/:sub?` | 같은 화면 위의 `SettingsSheet` | 아바타로 여는 설정 시트다. page는 schedules · team · skills · accounts · wallet · system · security · profile 여덟이다. | `src/main.js:20`, `src/components/SettingsSheet.vue:26` |
| `/workroom/:kind/:id` | `views/WorkroomView.vue` | 에이전트의 작업 폴더를 터미널(Claude Code 또는 셸)과 파일 목록으로 여는 전체 화면이다. | `src/main.js:21`, `src/views/WorkroomView.vue:1-6` |
| `/folders` | `views/FoldersView.vue` → `FolderList` | 공유 폴더(git 기반) 목록과 색인 검색, 그리고 「스킬」 탭(스킬도 폴더로 다룸)이다. | `src/views/FoldersView.vue:2-5`, `:35`, `src/components/folders/FolderList.vue:71-183` |
| `/folders/:slug` | `FolderDetail` | 폴더 하나의 기준본(main) 파일 · 이력 · 색인과, 오른쪽의 변형(브랜치) 목록 · 일괄 반영이다. | `src/components/folders/FolderDetail.vue:2`, `:118-288` |
| `/folders/:slug/v/:variation` | `VariationView` | 변형 하나가 main과 무엇이 다른지 보고 인계 · 반영하는 화면이다. | `src/views/FoldersView.vue:5`, `:33` |
| `/mining/:id?` | `views/MiningView.vue` | 관리자 전용. 인계 기록에서 찾은 반복 흐름을 추천으로 보이고, 하나를 열면 근거와 함께 정식 등록 · 보류 · 대화로 확정한다. | `src/main.js:26-27`, `src/views/MiningView.vue:2-5` |
| `/improve/:defId?` | `views/ImproveView.vue` | 실행 기록으로 병목 · 가치 흐름 · 제약 · 크리티컬 패스를 계산해 보이고, 개선안을 미리 계산해 새 버전으로 적용한다. | `src/main.js:28-29`, `src/views/ImproveView.vue:2-5` |

라우트 주석 하나는 낡았다. `src/main.js:22`는 폴더를 「UI 프로토타입, 가짜 데이터」라고 적지만, 실제 화면은 서버 `/api/folders`를 부른다(`src/foldersApi.js:15-18`, `server/routes/folders.js:35`).

### 1.2 첫 화면의 칸 배치

공통 바탕: 화면 전체에 실시간 하늘 그림(`SkyCanvas`)이 깔리고 그 위에 유리 카드가 뜬다(`src/App.vue:12`, README.md:10 「실시간 하늘 배경과 유리 카드 UI(hark 스타일)」). 데스크톱에서 왼쪽 칸이 나오는 폭은 1000px 초과이고(`src/views/MainView.vue:29-30`), 폰 폭은 760px 이하다(`src/viewport.js:4`).

| 화면 | 위 막대 | 왼쪽 칸 | 가운데 | 오른쪽 | 근거 |
|---|---|---|---|---|---|
| `/chat` (Home 펼침, 기본값) | 높이 68px, 투명. 왼쪽 Home 토글(48px 원), 가운데 탭 3(채팅 · 프로젝트 · 폴더), 오른쪽 메시지 · 검색 · 아바타 | `HomeDock` 폭 420px(안쪽 여백 위 84 · 좌우 16 · 아래 114). 알림 카드 → 할 일 카드 → 메일 액션 카드 → 날씨 → 패널 앱 → 패널 → 「새 패널 만들기」 순으로 세로로 쌓인다 | `ChatColumn` 폭 512px를 남은 폭의 가운데에 둔다. 머리에 `ConversationBar`, 아래에 메시지, 바닥에서 32px 위에 입력창(`Composer`) | 없다 | `TopBar.vue:67-82`, `HomeDock.vue:20-40`, `:44`, `MainView.vue:104`, `:121-127`, `:152`, `ChatColumn.vue:81`, `:99`, `app.js:20` |
| `/chat` (Home 접음) | 같다 | 없다. 대신 화면 왼쪽 아래에 요일 · 날짜 · 시각이 44px 큰 글로 뜬다 | `ChatColumn`이 화면 정가운데로 온다 | 없다 | `MainView.vue:115-119`, `:153` |
| `/chat/c/:cid` | 같다 | Home 칸(펼쳤으면) | 머리의 `ConversationBar`가 「전체 대화」 단추 · 대화 제목 · 「다른 대화 ▾」 줄로 바뀐다 | 오른쪽 아래(오른쪽 28px, 아래 112px)에 이 대화의 산출물 더미(64px) | `ConversationBar.vue:26-33`, `ArtifactStack.vue:88-90` |
| `/projects`, `/projects/:id` | 같다. 「프로젝트」 탭이 켜진다 | `ProjectList` 폭 420px(여백 위 100 · 좌우 40 · 아래 114): 「새 프로젝트」, 프로젝트 이름들, 「프로세스」 소제목과 「개선 분석 →」 링크, 인스턴스 이름들 | 새 프로젝트일 때는 서체가 큰 소개 문장(「프로젝트는 장기적인 작업과 경험을 정리하기 위한 공간입니다.」)과 입력창, 프로젝트를 열면 그 대화 | 없다 | `ProjectList.vue:21-47`, `:51`, `MainView.vue:130-132` |
| `/projects/p/:instId` | 같다 | `ProjectList`(그 인스턴스 줄이 굵게) | `ChatColumn` 512px 안의 맨 위에 `InstanceHeader`(제목 · 진행 막대 · 진행 상황 카드 · 내 입력 · 산출물), 그 아래가 인스턴스 대화, 바닥에 「이 프로세스에 대해 물어보기」 입력창. 이 화면만 열 때 맨 위에서 시작한다(keep-top) | 없다 | `MainView.vue:122-125`, `InstanceHeader.vue:41-92`, `ChatColumn.vue:37`, `:48` |
| `/settings…` | 사라진다(설정이 열리면 위 막대를 그리지 않는다) | 없다 | 폭 528px 시트 하나가 가운데에 온다. 뒤의 화면은 흐려지고 숨는다. 오른쪽 위에 닫기(48px 원)가 고정된다 | 없다 | `MainView.vue:105`, `:139`, `:150`, `SettingsSheet.vue:345-347` |
| `/mining`, `/improve`, `/folders` | 같은 `TopBar`(본문은 위에서 84px 아래부터) | 없다 | 본문 최대 폭: 마이닝 1120px, 개선 1160px, 폴더 목록 1180px. 폴더 하나를 열면 최대 1400px 안에서 왼쪽 1fr(파일) · 오른쪽 440px(변형) 두 칸 | 마이닝 추천 하나를 열면 오른쪽 아래에 56px 대화 다이얼. 누르면 오른쪽에 폭 400px 대화 서랍이 열린다 | `MiningView.vue:323-325`, `:418`, `:423`, `ImproveView.vue:465-467`, `FolderList.vue:187`, `FolderDetail.vue:291`, `:315` |
| `/workroom/…` | `TopBar` 없음. 어두운 전체 화면 머리 48px(뒤로 · 「Claude Code / deepagents」 · 폴더 칩 · 상태 · 제목 · Claude Code/셸 탭 · 「파일」) | 없다 | 터미널(xterm)이 화면이다. 파일을 누르면 터미널 자리에 파일이 열린다 | 「작업 파일」 칸 360px(900px 초과면 처음부터 열림) | `WorkroomView.vue:121-135`, `:198-215`, `:32` |
| `/login` | 없다 | 하늘 그림 칸(최대 672px)에 예시 요청 문장이 타자기로 돈다 | 오른쪽 칸 가운데 380px 안에 워드마크 · 한 줄 소개 · Google 단추 · 이메일 입력 · 계속 | — | `LoginView.vue:78-115`, `:120`, `:130` |
| `/welcome/age` | 없다 | — | 400px 카드: 워드마크, (이름), 생년월일 선택 3개, 계속 | — | `OnboardAge.vue:31-50`, `:54` |

폰 폭에서는 Home이 하나의 탭이 되어 입력창이 그 밑에 붙고(`MainView.vue:34-35`, `:133-135`), 프로젝트 탭은 목록을 먼저 보인다(`MainView.vue:36`). 폰 폭에서 메신저 진입은 Home 맨 위 카드로 내려간다(`HomeDock.vue:22-25`).

---

## 2. 첫 화면 요소 수

### 2.1 세는 법(가정)

- 데스크톱 폭 1280px, 밝은 테마, 관리자 계정, 접기 · 펼치기 · 탭 · 오버레이를 하나도 건드리지 않은 상태를 센다. 스크롤해야 보이는 부분도 「펼치지 않고 그려지는 것」이면 센다.
- **단추**: 누를 수 있는 `button`. 탭 · 세그먼트의 칸 하나하나, 줄 전체가 단추인 목록 줄, 아이콘 단추를 모두 1로 센다. 마우스를 올려야 보이는 단추(opacity 0)는 따로 「숨은 단추」로 센다.
- **링크**: `router-link`, `a`, 그리고 `role="link"`인 요소.
- **뱃지**: 상태 알약, 개수 점, 종류 태그, 코드 · 도구 칩처럼 모양을 갖춘 작은 표시.
- **글 덩어리**: 단추 이름과 뱃지 글을 뺀, 따로 보이는 글 요소. 제목 1, 한 줄 설명 1, 문단 1, 목록 줄 안의 보조 줄 1로 센다.
- **입력 칸**: input · textarea · select.
- 데이터는 목록마다 3~5줄의 보통 상태로 가정하고, 화면마다 그 가정을 적었다.

### 2.2 화면별 수

공통 위 막대(`TopBar`): 단추 7(Home 토글 1, 탭 3, 메시지 1, 검색 1, 아바타 1), 뱃지 0~1(안 읽은 메시지 수), 글 0(`TopBar.vue:47-62`, `team/TeamLayer.vue:25-28`).

| 화면(가정) | 단추 | 숨은 단추 | 링크 | 뱃지 | 글 덩어리 | 입력 | 그 밖 |
|---|---|---|---|---|---|---|---|
| `/chat` Home 펼침 — 알림 2(결정형 1: 선택지 2개, 마이닝 1), 할 일 1, 메일 액션 2, 날씨 1, 패널 앱 1, 대화 메시지 4(사용자 2 · 답 2) | 22 | 3 | 2 | 8 | 24 | 1 | 패널 앱 본문은 앱마다 달라 세지 않음 |
| └ 그중 Home 칸 | 11 | 3 | 0 | 6 | 20 | 0 | |
| └ 그중 가운데 대화 칸 | 4(대화 맥락 알약 1, 첨부 · 새 패널 · 받아쓰기 3) | 0 | 2(답 위 맥락 알약) | 2(맥락 판단 근거) | 4(말풍선) | 1 | 「··· 읽음」 0~1 |
| `/chat` Home 접음 | 11 | 0 | 2 | 2 | 4 | 1 | 큰 시계 글 3줄 |
| `/chat/c/:cid` Home 펼침 | 24 | 3 | 2 | 9 | 26 | 1 | 산출물 더미 1개(개수 점 포함) |
| `/projects` — 프로젝트 4(입력 필요 1 · 작업 중 1), 진행 인스턴스 3, 완료 5 중 3 표시 | 22 | 0 | 1 | 5 | 2 | 1 | |
| `/projects/:id` — 메시지 4 | 22 | 0 | 1 | 5 | 5 | 1 | |
| `/projects/p/:instId` — 아래 2.3 | 29 | 0 | 3 | 10 | 30 | 4 | 진행 막대 1 |
| `/settings` 첫 목록 | 10(닫기 1, 메뉴 8, 로그아웃 1) | 0 | 0 | 0 | 3(이름 · 메일 · 워드마크) | 0 | 위 막대 없음 |
| `/settings/skills` — 스킬 4(그중 1개 예약 있음) | 6(닫기 · 뒤로 · 줄 4) | 0 | 0 | 1(「예약 1」) | 10 | 0 | 추가 · 삭제 단추 없음 |
| `/settings/team` — 관리자, 팀원 4, 역할 5, 프로세스별 담당 1 | 6(닫기 · 뒤로 · 빼기 3 · 팀원 추가 1) | 0 | 0 | 0 | 23 | 9(이름 · 이메일 · 역할 검색 · 역할 담당 선택 5 · 하위 1) | 머리글자 원 4 |
| `/settings/accounts`(커넥터 포함) — Gmail 연결, 커넥터 Google · GitHub 연결 · YouTube 공개 · Slack · Notion 미연결, 보관함 3 | 23 | 0 | 0 | 26(연결됨 2, 도구 칩 21, 보관함 종류 3) | 32 | 2 | |
| `/improve` 목록 — 프로세스 3 | 10 | 0 | 0 | 0 | 11 | 0 | |
| `/improve/:defId` 병목 탭 — 단계 6, 인스턴스 8, 버전 1 | 27 | 0 | 0 | 14 | 77 | 0 | 분해 막대 14, BPMN 열지도 1 |
| `/mining` 목록 — 추천 3(그중 1개 제안 있음), 확인 필요 1 | 13 | 0 | 0 | 4 | 16 | 1 | |
| `/mining/:id` 추천 상태 — 단계 5(도구 2 · 스킬 1씩), 사례 6, 변형 3 | 11 | 0 | 0 | 61 | 56 | 0 | 대화 다이얼 1 |
| `/folders` — 폴더 4 | 15 | 0 | 0 | 4 | 31 | 1 | 구성원 아바타 묶음 4 |
| `/folders/:slug` — 파일 5(폴더 1개 안 3 + 맨 위 2, 카드 3), 변형 2, 지난 변형 3 | 28 | 5(파일 지우기) | 0 | 10 | 31 | 0 | |
| `/workroom/todo/:id` — 파일 10 | 16 | 0 | 0 | 2 | 5 | 1 | 터미널 1 |
| `/login` | 5 | 0 | 0 | 0 | 4 | 1 | 워드마크, 하늘 그림 |
| `/welcome/age` | 1 | 0 | 0 | 0 | 2(+이름을 물으면 2) | 3(+1) | |
| `/welcome/intro` | 0 | 0 | 0 | 0 | 2 | 0 | 저절로 넘어감 |

세부 근거:
- Home 칸: 알림 카드는 종류 뱃지 1 · 제목 1 · 닫기(×) 1 · 출처와 시각 1 · 맥락 3줄 1 · 선택지 단추와 「자세히」 또는 「검토하기」로 그려진다(`NotificationCard.vue:49-69`). 할 일 카드는 카드 전체가 단추이고 「Review/Submit」 뱃지와 두 줄 글이다(`HomeDock.vue:27-31`). 메일 액션 카드도 카드 전체가 단추이고 동사 뱃지 · 글 · 기한, 닫기는 마우스를 올려야 보인다(`ActionCard.vue:29-36`, `:46-47`). 날씨는 장소와 세 칸(상태 · 체감 · 일몰)이다(`WeatherPanel.vue:19-30`). 패널 앱 머리는 제목 · 「행 권한」 · 인원 수이고 「⋯」 메뉴는 마우스를 올려야 보인다(`panelApps/PanelAppCard.vue:166-171`, `:285-286`).
- 가운데 대화 칸: `ConversationBar`가 대화가 있으면 「대화 N개 · 맥락별로 보기」 알약 하나만 둔다(`ConversationBar.vue:34-36`). 답 위의 맥락 알약은 `role="link"`이고 판단 근거 뱃지를 단다(`Message.vue:58-61`). 입력창은 글이 없을 때 첨부 · 새 패널 · 받아쓰기 세 단추이고, 글을 쓰면 보내기 단추로 바뀐다(`Composer.vue:133-138`).
- `/projects`: `ProjectList.vue:22-45`. 완료된 인스턴스는 3개까지만 그리고 「완료된 프로세스 N개 더 보기」 단추를 둔다(`ProjectList.vue:12-17`, `:45`).
- `/settings/accounts`: `SettingsSheet.vue:173-225`, `ConnectorCards.vue:48-67`. 도구 칩 21은 커넥터 정의의 도구 수다(Google 8, YouTube 3, Slack 3, GitHub 3, Notion 4 — `server/mcp/connectors.js:12`, `:45`, `server/mcp/connectors/google.js`, `youtube.js`, `saas.js`의 `tools` 배열).
- `/improve/:defId`: `ImproveView.vue:188-270`(머리 · 탭 · 병목 카드 셋). 표의 열이 7개이고(`ImproveView.vue:231`) 단계 줄마다 분해 막대를 단다(`:237`).
- `/mining/:id`: `MiningView.vue:180-261`. 사례는 개수 제한 없이 모두 그린다(`MiningView.vue:237`).
- `/folders/:slug`: `FolderDetail.vue:122-279`.

### 2.3 `/projects/p/:instId` 인스턴스 화면을 따로 센 것

가정: 상태 RUNNING. 정의 단계는 시작 1 · 사람 3 · 에이전트 3 · 끝 1. 상태는 사람1 끝남, 에이전트1 끝남, 에이전트2 실행 중, 사람2가 내 차례, 나머지 대기. 에이전트 단계마다 스킬 1개. 산출물은 긴 보고서 필드 1개와 파일 1개. 내 할 일 폼은 필드 3개이고 앞 단계 산출물 칩 1개가 붙는다. 인스턴스 대화는 아직 없다.

| 부분 | 단추 | 링크 | 뱃지 | 글 | 입력 | 근거 |
|---|---|---|---|---|---|---|
| 제목 블록: 상태 알약, 제목(서체 30px), 「정의 이름 · 시작 시각 · 2/6 단계」, 진행 막대, 「이 프로세스의 병목·크리티컬 패스 보기 →」 | 0 | 1 | 1 | 2 | 0 | `InstanceHeader.vue:42-48` |
| 「진행 상황」 카드: 목록/다이어그램 세그먼트, 단계 8줄(이름 8 · 역할 줄 6), 「입력 필요」 1, 「동작 보기」 2, 스킬 코드 3 | 4 | 0 | 4 | 15(머리 1 + 이름 8 + 역할 6) | 0 | `InstanceHeader.vue:50-57`, `StepTimeline.vue:14-35` |
| 「내 입력이 필요해요」: 앞 단계 산출물 칩, 폼 제목 · 부제 · 라벨 3 · 입력 3 · 제출 | 2 | 0 | 0 | 7 | 3 | `InstanceHeader.vue:59-62`, `TodoCard.vue:34-43`, `mining/StepOutputs.vue:24-29`, `FormCard.vue:43-75` |
| 「산출물 2」: 파일 링크 1, 문서 카드(제목 · 단계 · 140px로 자른 미리보기 · 펼치기) | 1 | 1 | 0 | 4 | 0 | `InstanceHeader.vue:64-89` |
| 구분선 「이 프로세스에 대해 물어보세요」 | 0 | 0 | 0 | 1 | 0 | `InstanceHeader.vue:90` |
| 인스턴스 머리 합 | 7 | 2 | 5 | 29 | 3 | |
| 위 막대 + 왼쪽 목록 + 입력창 | 7 + 12 + 3 | 1 | 5 | 1 | 1 | `TopBar.vue`, `ProjectList.vue`, `Composer.vue` |
| **화면 합** | **29** | **3** | **10** | **30** | **4** | 진행 막대 1 |

머리는 「제목 → 살아 있는 흐름 → 내 입력 → 산출물」 순서다. 코드 주석이 그렇게 적는다: "Top of an instance page: title, live flow, my pending inputs, and produced artifacts."(`InstanceHeader.vue:13`). 진행 상황은 기본이 「목록」(단계 타임라인)이고 BPMN 다이어그램은 세그먼트를 눌러야 보인다(`InstanceHeader.vue:17`, `:52`, `:54-56`). 진행 막대의 분모는 사람 · 에이전트 단계만이다(시작 · 끝 · 게이트웨이 · 이벤트를 세지 않음, `InstanceHeader.vue:24-27`).

---

## 3. 뺀 것 · 숨긴 것

### 3.1 문서로 남은 원칙

lite의 화면 원칙이나 「덜어 낸 까닭」을 한데 적은 문서는 README · CHANGELOG · openspec 어디에도 없다. 원칙은 컴포넌트 주석과 CHANGELOG의 고침 기록에 흩어져 있다. 그대로 옮긴다.

- README.md:3 「대화로 일하는 AI 업무 비서 — Process GPT 위에서 동작합니다.」
- README.md:10 「Process GPT Lite는 실시간 하늘 배경과 유리 카드 UI(hark 스타일)로 된 Vue 3 앱과 Express BFF입니다. 사용자는 채팅 하나로 프로세스를 만들고 실행하며, 브라우저 에이전트·스킬·예약 미션·문서 편집·패널 앱을 씁니다. 실행 엔진·에이전트·저장소는 Process GPT 백엔드(deepagents, completion, Supabase …)를 그대로 쓰고, 이 저장소에는 Lite 전용 화면과 BFF만 있습니다.」
- README.md:212 「5초마다 갱신. 내 차례가 오면 채팅에 폼 카드가 자동으로 올라옴」
- CHANGELOG.md:192 「프로세스 스피너는 에이전트가 실제로 작업 항목을 잡고 있을 때만 돈다. 사람 단계는 "담당자 확인 대기".」
- CHANGELOG.md:122 「빠른 답 버튼: 답이 질문과 짧은 선택지로 끝날 때만 버튼이 됩니다. 보고문의 글머리 목록은 그대로(`src/replies.js`).」
- CHANGELOG.md:68 「메시지 본문의 샌드박스·호스트 경로는 채팅·인스턴스 화면·Craft 대화 오버레이처럼 파일 이름으로 보입니다(`src/paths.js` `hidePaths`).」
- CHANGELOG.md:94 「저장된 카드의 「흐름 보기」는 펼치면 화면 안으로.」
- CHANGELOG.md:99 「실패한 예약 실행이 채팅·Home 어디에도 안 보이던 것 — 모든 예약이 실행 기록을 남기고 실패는 채팅과 Home 카드로」
- CHANGELOG.md:113 「관리자가 하나도 없으면 처음 로그인한 사람이 관리자가 되고, 비관리자의 「설정 › 팀·역할」은 읽기 전용입니다.」
- CHANGELOG.md:186 「대화별 산출물 스택: 그 대화가 만든 파일이 Dock 스택처럼 쌓였다가 부채꼴·격자로 펼쳐짐.」
- openspec/changes/intent-and-admin-boundary/design.md:53 「무엇에 대한 대화인지가 화면으로 정해진다. 고친 결과가 바로 옆 단계 카드에 보인다」(대화를 홈이 아닌 추천 화면에 둔 까닭)
- 같은 파일 :55 「근거(…)는 저장된 값으로 계산해 모델에 넘긴다. 모델은 관리자의 말을 도구 호출(…)로 바꾸거나, 근거를 풀어 말한다. 도구는 서버가 실행하고, 무엇이 바뀌었는지는 서버가 정한 문장으로 답한다.」
- 같은 파일 :81 「화면에는 "재무 검토 · 옵션 · 관리자 확정"이 떴지만, 정식 등록된 정의는 유저 태스크 여섯 개가 한 줄이라 재무 검토가 매번 실행됐다. 식별의 결과물은 정식 등록되는 BPMN 프로세스 정의이므로 이 둘이 어긋나면 관리자를 속이는 화면이 된다.」
- openspec/changes/intent-and-admin-boundary/tasks.md:60 「제안의 반영·넣지 않기 버튼이 아래 정식 등록 막대에 가렸다. 제안 제목 줄로 옮겼다」, :61 「빠진 필수 단계가 첫 낱말로만 보여 "견적서 작성"과 "견적서 검토"가 같아 보였다. 단계 이름 전부를 보인다」
- openspec/changes/intent-and-admin-boundary/specs/mining-suggestion/spec.md:30 「항목마다 그 업무가 무엇인지 알 수 있는 정보와 거친 단계, 확인이 필요한 이유가 보여야 한다(MUST).」
- 컴포넌트 주석: `ProjectList.vue:11` "running and waiting-on-me first; finished ones stay folded unless asked", `ProjectList.vue:37-38` "the spinner is for an agent actually at work; a step waiting on a person (HITL) or a long-running process at rest gets a still badge", `StepTimeline.vue:46` "an active step is ringed; only an agent actually at work pulses (a step waiting on a person stays still)", `HomeDock.vue:15` "a work item that already has a notification card is not listed twice", `server/lib/agent.js:524-525` "While skill-creator works its raw output (test prompts, sample data, interleaved subagent streams) is not for reading; the chat shows the step it is on and, at the end, a summary card.", `src/paths.js:1-4` "a sandbox or host path means nothing to the person, and the file itself already comes as a card under the answer."

### 3.2 본판과 비교해 확인되는 것

본판 화면 코드는 이 clone에 없으므로 「본판 화면에서 무엇을 뺐는가」의 목록은 **코드로 확인 못 함**이다. lite 코드가 본판을 언급한 자리에서 확인되는 것만 적는다.
- 프로세스 정의는 대화로만 만든다. 화면에 BPMN 편집기가 없고, 그림은 보기 전용 `NavigatedViewer`뿐이다(README.md:209-232, `src/components/BpmnView.vue:3`, `src/components/improve/HeatBpmn.vue:6`. `Modeler`를 검색해 0건). 폼 편집기도 화면에 없다(「폼 편집 · 양식 편집 · FormDesigner」 검색 0건). 폼은 본판의 `form_def.fields_json`을 그대로 그린다(`FormCard.vue:7`).
- 개선 화면의 지표와 색은 본판 `BottleneckAnalysis` · `LeadTimeBreakdownBar`를 옮긴 것이다(`src/components/improve/fmt.js:1`, `:24`, `LeadBar.vue:2`, `HeatBpmn.vue:3`). 즉 이 화면은 덜어 낸 화면이 아니라 본판 분석을 그대로 가져온 화면이다.
- 팀 대화 속 에이전트 제안은 본판에서 물려받았다. 본판은 모든 채팅 메시지를 gpt-4o로 분류하지만 lite는 규칙과 값싼 판단 모델로 가른다(`server/lib/team/assist.js:1-8`).
- 문서 편집기(이음오피스)는 본판 `process-gpt-vue3`에서 옮겼다(`src/officeEditor.js:1`, `OfficeEditorFrame.vue:2`).

### 3.3 숨긴 방식과 그 자리

| 방식 | 자리 | 근거 |
|---|---|---|
| 메뉴에 두지 않고 설정 시트로 | 계정 · 지갑 · 보안 · 시스템 · 스킬 · 팀 · 예약 · 프로필이 모두 아바타 뒤 한 목록이다. 시트가 열리면 위 막대가 사라지고 뒤 화면이 흐려진다 | `TopBar.vue:61`, `SettingsSheet.vue:26`, `:146-155`, `MainView.vue:105`, `:150` |
| 메뉴에 두지 않고 알림 카드와 본문 링크로 | 마이닝 화면은 어떤 메뉴에도 없다. 관리자에게 「추천」 알림이 Home에 오고, 그 카드의 「검토하기」로 들어간다. 개선 화면은 프로젝트 목록의 작은 「개선 분석 →」 링크, 인스턴스 머리의 링크, 「제약」 알림으로 들어간다 | `NotificationCard.vue:21`, `:37`, `:39`, `:67`, `server/lib/mining/service.js:334-345`, `ProjectList.vue:31`, `InstanceHeader.vue:47` (`/mining` 링크를 검색해 알림 카드와 마이닝 화면 자신의 「뒤로」만 나옴) |
| 「추가」 단추 대신 대화로 묻게 | 스킬 목록: 「채팅에서 "○○ 스킬 만들어줘"로 추가돼요.」 예약 목록이 비면: 「채팅에서 "매일 아침 8시에 …"처럼 말하거나, 스킬을 저장할 때 주기를 정하면 여기에 추가돼요.」 폴더 변형이 없으면: 「채팅에서 "… 폴더의 … 고쳐줘" 라고 하면 에이전트가 변형을 만들어 일해요.」 마이닝 추천은 대화 다이얼로 고친다. 패널은 「패널에 질문하기 / 패널 수정하기」가 대화 입력창에 미리 글을 채운다. 인스턴스에 대한 질문은 그 인스턴스 상태를 맥락으로 붙여 대화로 보낸다 | `SkillList.vue:58`, `MissionList.vue:84`, `FolderDetail.vue:257`, `MiningView.vue:291-316`, `PanelFrame.vue:38-48`, `MainView.vue:90-95` |
| 접기 · 펼치기 | 산출물 문서는 140px(채팅 문서 카드는 150px)까지만 보이고 아래가 흐려지며, 카드 아래 가운데의 둥근 꺾쇠 단추로 펼친다. 프로세스 카드의 흐름은 「흐름 보기」를 눌러야 펼친다. 마이닝 규칙 설명은 `details`(「사례는 어떻게 묶이나요?」). skill-creator 작업 메모도 `details`. 폴더의 하위 폴더 줄은 ▾/▸로 접는다 | `InstanceHeader.vue:80-86`, `:121-126`, `Message.vue:80-86`, `:172-176`, `ProcessCard.vue:15`, `:53`, `:56`, `MiningView.vue:168-176`, `SkillSheet.vue:33-36`, `FolderDetail.vue:173-176` |
| 완료 건 접기 | 완료된 인스턴스는 3개만, 나머지는 「완료된 프로세스 N개 더 보기」. 완료 줄은 흐리게(불투명도 .6). 지난 변형은 「지난 변형 N개 (반영됨·버림)」 단추 뒤에. 제출한 할 일 카드는 「○○ 제출됨」 한 줄 알약으로 줄어든다 | `ProjectList.vue:11-17`, `:45`, `:63`, `FolderDetail.vue:258-267`, `TodoCard.vue:33` |
| 「동작 보기」 같은 상세 열기 | 에이전트 단계가 무엇을 읽고 불렀는지는 타임라인에 없고, 끝났거나 도는 에이전트 단계의 「동작 보기」를 누르면 어두운 시트로 뜬다. 작업실은 그 시트 안의 「작업실 열기」로만 간다. 스킬 원문은 「SKILL.md 전체 보기」 시트로. 브라우저 작업의 계획 단계는 실시간 화면 위 제목 알약을 눌러야 보인다 | `StepTimeline.vue:30`, `AgentActivity.vue:79-110`, `:88`, `SkillList.vue:90`, `:108`, `SkillDraftCard.vue:44`, `:55`, `TaskCard.vue:45-60` |
| 오버레이 | 검색, 팀 메신저, BPMN 「크게 보기」, 개선안 적용 확인, 새 폴더 · 저장소 연결, 브라우저 작업 전체 화면 | `SearchOverlay.vue:26-37`, `team/TeamLayer.vue:29-39`, `BpmnView.vue:65-68`, `ImproveView.vue:451-459`, `FolderList.vue:165-182`, `MainView.vue:141` |
| 탭 · 세그먼트 | 인스턴스 진행 상황 「목록 / 다이어그램」(기본 목록). 개선 「병목 · 가치 흐름 · 제약 · 크리티컬 패스 · 개선 실행」. 폴더 「파일 · 이력 · 색인(· 스킬)」. 작업실 「Claude Code / 셸」. 대화 맥락 목록은 알약 하나로 접혀 있다가 펼친다 | `InstanceHeader.vue:52`, `ImproveView.vue:22`, `:212-214`, `FolderDetail.vue:155-159`, `WorkroomView.vue:130-133`, `ConversationBar.vue:34-47` |
| 마우스를 올려야 보임 | 메시지 시각, 메일 액션 카드 닫기, 패널 · 패널 앱의 「⋯」 메뉴(삭제가 그 안), 폴더 파일 지우기. 문서 카드 요약은 「카드」 뱃지의 툴팁, 마이닝 단계의 필수 · 옵션 근거와 맥락 판단 근거도 툴팁 | `Message.vue:152-154`, `ActionCard.vue:46-47`, `PanelFrame.vue:60-67`, `:78-79`, `panelApps/PanelAppCard.vue:171-182`, `:285-286`, `FolderDetail.vue:178`, `:338-339`, `MiningView.vue:200`, `Message.vue:58` |
| 개수 상한(「더 보기」 없음) | Home 알림 6장, 할 일 3장, 메일 액션 5장. 이미 알림 카드가 있는 할 일은 다시 싣지 않는다. 개선 인스턴스 14개, 브랜치 산출물 파일 8개(「외 N개 파일」), 스킬 초안 절차 3줄 | `HomeDock.vue:15-16`, `:26`, `:32`, `ImproveView.vue:248`, `InstanceHeader.vue:77-78`, `SkillDraftCard.vue:53` |
| 원문 · 경로 감추기 | 샌드박스 · 호스트 경로는 파일 이름으로 바꿔 보인다. 대화 폴더 링크는 열리지 않는 링크라 글만 남기고 파일은 카드로 연다. skill-creator의 원 출력은 보이지 않고 「스킬 만드는 중 · 파일 작성 (3단계)」와 요약 카드만. 보고문의 글머리는 버튼으로 바꾸지 않는다 | `src/paths.js:1-4`, `Message.vue:31-35`, `server/lib/agent.js:524-534`, `src/replies.js:1-13` |
| 권한으로 숨김 · 읽기 전용 | 팀원 추가 · 빼기와 역할 지정은 관리자만(그 밖은 안내 문장과 잠긴 선택). 마이닝은 관리자만(「관리자만 볼 수 있어요.」). 개선안 적용은 프로세스 담당자 · 관리자만 | `TeamRoles.vue:75-83`, `:93`, `MiningView.vue:135`, `ImproveView.vue:414-415` |
| 상태일 때만 나타남 | 답을 쓰는 동안만 「멈추기」와 작업 알약, 입력을 기다릴 때만 주황 「조치 필요」 삼각 단추, 실패한 단계에만 이유와 「다시 시도」, 산출물이 있을 때만 「산출물」, 내 차례가 있을 때만 「내 입력이 필요해요」 | `ChatColumn.vue:69-71`, `StepTimeline.vue:24-27`, `InstanceHeader.vue:59-64` |
| 빈 상태에서 아무것도 안 그림 | 대화가 비어도 빈 상태 문구를 쓰지 않는다(`emptyText`가 늘 빈 글) | `MainView.vue:124`, `ChatColumn.vue:57` |

---

## 4. 부품의 모양 값

### 4.1 색 토큰 (`src/styles/base.css`)

기본은 어두운 테마이고, `:root[data-theme="light"]`가 밝은 값을 덮는다(`base.css:4-5`, `:39`). 테마는 해의 위치로 저절로 바뀌고(낮이면 light), 설정 › 시스템에서 「자동 · 낮 · 밤」으로 고정할 수 있다(`src/stores/sky.js:7`, `:13`, `:35-37`, `:66-68`, `SettingsSheet.vue:281-282`).

| 토큰 | 밝은 테마 | 어두운 테마(기본) | 줄 |
|---|---|---|---|
| `--text` | `#000` | `#fff` | 40 / 12 |
| `--text-primary` | `rgb(29 29 31)` | `rgb(245 245 247)` | 41 / 13 |
| `--text-secondary` | `rgba(29 29 31 / .5)` | `rgba(245 245 247 / .5)` | 42 / 14 |
| `--text-tertiary` | `rgba(29 29 31 / .3)` | `rgba(245 245 247 / .3)` | 43 / 15 |
| `--text-primary-on` | `rgb(249 249 250)` | `rgb(29 29 31)` | 44 / 16 |
| `--ink` | `rgb(29 29 31)` | `rgb(245 245 247)` | 45 / 17 |
| `--ink-inverse` | `rgb(249 249 250)` | `rgb(29 29 31)` | 46 / 18 |
| `--hairline` | `rgba(0 0 0 / .08)` | `rgba(255 255 255 / .1)` | 47 / 19 |
| `--bubble-user-bg` | `rgba(255 255 255 / .3)` | `rgba(29 29 31 / .3)` | 49 / 21 |
| `--bubble-agent-bg` | `rgba(255 255 255 / .98)` | `rgba(29 29 31 / .7)` | 50 / 22 |
| `--composer-bg` | `rgba(255 255 255 / .55)` | `rgba(29 29 31 / .618)` | 51 / 23 |
| `--thin-bg` | `rgba(255 255 255 / .55)` | `rgba(29 29 31 / .615)` | 52 / 24 |
| `--cell-bg` | `rgba(255 255 255 / .6)` | `rgba(255 255 255 / .05)` | 53 / 25 |
| `--regular-bg` | `rgba(255 255 255 / .668)` | `rgba(29 29 31 / .618)` | 54 / 26 |
| `--regular-solid-bg` | `rgba(255 255 255 / .96)` | `rgba(29 29 31 / .96)` | 55 / 27 |
| `--button-bg` | `rgba(29 29 31 / .05)` | `rgba(255 255 255 / .08)` | 56 / 28 |
| `--field-bg` | `rgba(29 29 31 / .055)` | `rgba(255 255 255 / .08)` | 57 / 29 |
| `--chip-bg` | `rgba(255 255 255 / .9)` | `rgba(255 255 255 / .12)` | 58 / 30 |
| `--surface-secondary` | `#f3f5fa` | `#1c1c1e` | 59 / 31 |
| `--shadow-card` | `0 8px 40px rgba(29 29 31 / .12)` | `0 8px 40px rgba(0 0 0 / .25)` | 60 / 32 |
| `--color-info` | `#005AD7` | `#A1D0FF` | 62 / 34 |
| `--color-success` | `#0F9D58` | `#96F0B0` | 63 / 35 |
| `--color-error` | `#D64545` | `rgba(255 100 100 / .9)` | 64 / 36 |
| `--color-attention` | 덮지 않음 → `#FF4D00` | `#FF4D00` | 37 |
| `--font-sans` | `'Pretendard Variable', Pretendard, -apple-system, system-ui, sans-serif` | 같음 | 6 |
| `--font-serif` | `'Newsreader', 'Noto Serif KR', serif` | 같음 | 7 |
| `--spring` | `cubic-bezier(.2, .9, .25, 1.05)` | 같음 | 10 |
| `--mode-ease` / `--mode-dur` | `cubic-bezier(.45, 0, .55, 1)` / `.8s` | 같음 | 8-9 |

토큰 밖에 손으로 박은 색이 여럿 있다. 주 단추 `#1d1d1f`(`base.css:104`), 「입력 필요」 · 제약 강조 `#e0613f`(`ProjectList.vue:66`, `ImproveView.vue:474`, `:482`), 안 읽음 점 `#e5484d`(`TopBar.vue:79`, `TeamLayer.vue:46`), 팀 · 멘션 알림 파랑 `#2a78d6`(`NotificationCard.vue:76`), BPMN 상태색 `#0F9D58` · `#FF4D00`(`BpmnView.vue:97-99`). 글꼴은 웹에서 받는다(Pretendard는 jsDelivr, Newsreader · Noto Serif KR은 Google Fonts, `base.css:1-2`). 바탕은 `body #0a0f24` 위의 하늘 그림이다(`base.css:74`, `App.vue:12`).

유리 효과: `.glass`는 `--regular-bg`에 `backdrop-filter: blur(50px)`(`base.css:86-91`), `.glass-thin`은 `--thin-bg`에 같은 흐림(`base.css:92`). 위 막대 밑과 입력창 위에서는 여섯 겹 흐림 띠(`EdgeBlur`)로 글이 녹아 사라진다(`EdgeBlur.vue:1-4`, `ChatColumn.vue:53`, `:66`).

### 4.2 부품별 값

| 부품 | 값 | 근거 |
|---|---|---|
| 위 막대 | 높이 68px, 좌우 여백 16px, 배경 없음(막대 자체는 눌리지 않고 안의 부품만 눌림). 탭은 가운데 세그먼트: 바깥 `glass-thin`, 안쪽 여백 2px, 완전한 둥근 모서리. 탭 칸 높이 44px, 좌우 20px, 15px · 굵기 500, 꺼진 칸은 `--text-secondary`. 켜진 칸 뒤로 `--ink` 색 알약(thumb)이 0.45초 스프링으로 미끄러지고 글은 `--text-primary-on`. 세그먼트의 가로 위치는 대화 칸 가운데(`--chat-center`)를 따라간다. 양옆 단추는 48px 원(Home), 높이 48px 알약(메시지 · 검색), 48px 그라데이션 원(아바타) | `TopBar.vue:67-82`, `MainView.vue:104`, `team/TeamLayer.vue:43` |
| 왼쪽 목록 칸 | 폭 420px, 여백 위 100 · 좌우 40 · 아래 114. 줄은 26px · 줄 높이 1.3 · 자간 -0.02em · 위아래 14px(한 줄이 약 62px). 프로세스 인스턴스 줄은 19px. 기본 색 `--text-secondary`, 고른 줄은 바탕 칠 없이 `--text-primary` + 굵기 500으로만 표시한다. 소제목은 13px `--text-tertiary` · 자간 .04em | `ProjectList.vue:51`, `:55-57`, `:61-62` |
| Home 칸 카드 | 폭 420px 칸 안에 카드 사이 10px. 카드 모서리 24px, 안쪽 17/16/19/22px, 16px 글. 위아래 76px · 60px 구간이 투명하게 사라지는 마스크 | `HomeDock.vue:44-49` |
| 카드 | 모서리 대부분 24px(대화 카드 · 폼 · 알림 · 인스턴스 진행 카드), 분석 화면은 20~22px. 안쪽 여백 16~18px. 바탕은 `--bubble-agent-bg`(밝은 테마에서 흰색 .98) 또는 `.glass`. 그림자는 `--shadow-card`. 설정 목록은 모서리 24px · 좌우 22px이고 줄 사이를 1px `--hairline`으로 나눈다 | `InstanceHeader.vue:106`, `Message.vue:170`, `FormCard.vue:80`, `NotificationCard.vue:73`, `ImproveView.vue:491`, `SettingsSheet.vue:353-361` |
| 카드 안 소제목 | 13px `--text-secondary`(대화 칸 안). 분석 화면은 16.5px · 500에 보조 설명 12.5px `--text-tertiary` | `InstanceHeader.vue:107`, `ImproveView.vue:492-493` |
| 상태 알약 | 목록 칸: 높이 28px, 좌우 12px, 완전 둥근, 13px · 500, 바탕 `--bubble-user-bg`. 인스턴스 머리: 높이 24px, 좌우 10px, 12px · 500. 타임라인 안: 높이 22px, 좌우 9px, 12px. 마이닝: 높이 24px, 모서리 12px, 12.5px. Home 카드의 동사 뱃지는 모서리 8px의 각진 모양(높이 30~34px, 15~16px) | `ProjectList.vue:65`, `InstanceHeader.vue:98`, `StepTimeline.vue:57-60`, `MiningView.vue:351`, `NotificationCard.vue:75`, `HomeDock.vue:50` |
| 알약 색 규칙 | 주황(`--color-attention` 또는 `#e0613f`) 흰 글 = 내가 할 일(입력 필요 · 결정 · 추천). 빨강(`--color-error`) 흰 글 = 실패. 회색 바탕에 `--text-secondary` 글 + 멈춘 점 또는 손 아이콘 = 남이 할 일 · 대기(「담당자 확인 대기」, 「진행 중」). 회전 고리 = 에이전트가 지금 일함. 파랑 섞음(`--color-info` 22%) = 인스턴스 진행 중. 초록 섞음(`--color-success` 26%) = 완료. 팀 · 멘션 알림은 파랑 `#2a78d6`, 예약 결과는 짙은 회색 `#3d3d3a` | `ProjectList.vue:36-42`, `:65-70`, `InstanceHeader.vue:98-100`, `NotificationCard.vue:75-78`, `StepTimeline.vue:57-60` |
| 주 단추(`.dark-btn`) | 높이 48px, 좌우 22px, 완전 둥근, 바탕 `#1d1d1f` · 글 `#f5f5f7`, 15px · 500. 어두운 테마에서는 흰 바탕 검은 글로 뒤집는다. 비활성은 불투명도 .35. 폼 안에서는 높이 44px | `base.css:102-109`, `TodoCard.vue:53`, `FormCard.vue:105` |
| 보통 단추(`.pill-btn`) | 높이 48px, 좌우 20px, 완전 둥근, 15px · 500, 글 `--text-secondary`, 바탕 `--thin-bg` + 흐림 8px. 마우스를 올리면 글이 `--text-primary`. 설정 안의 작은 판은 높이 34px · 14px | `base.css:94-100`, `SettingsSheet.vue:374` |
| 강조 결정 단추 | 마이닝 · 개선의 「정식 등록 · 개선안 적용」은 높이 44px, 모서리 22px, 주황 바탕 흰 글 · 500. 짝인 「보류 · 취소」는 `--button-bg` | `MiningView.vue:396-399`, `ImproveView.vue:571-573` |
| 누름 효과 · 위험 | 눌리는 동안 크기 .96(`.press`, `.pill-btn`). 삭제 · 로그아웃은 `--color-error` 글 | `base.css:101`, `SettingsSheet.vue:356`, `MissionList.vue:157` |
| 펼치기 단추 | 카드 아래 가장자리 가운데(아래 -14px)에 걸친 32px 원, 바탕 `--regular-solid-bg`, 그림자 `0 2px 10px rgba(0 0 0 / .1)`, 아래 꺾쇠가 펼치면 180도 돈다. 잘린 내용은 최대 높이 140~150px에 아래로 흐려지는 마스크, 펼치면 마스크를 걷는다 | `InstanceHeader.vue:121-126`, `Message.vue:172-176` |
| 빈 상태 문구 | 「무엇이 아직 없는지 + 언제 · 어떻게 생기는지」를 한 문장으로 쓴다. 예: 「아직 반복되는 흐름이 없어요. 같은 일이 몇 번 더 쌓이면 여기에 추천이 나와요.」, 「아직 분석할 실행 기록이 있는 프로세스가 없어요. 프로세스를 몇 번 끝까지 돌리면 여기에 나와요.」, 「아직 폴더가 없어요」 + 문장 + 「새 폴더」 단추, 「아직 기록된 동작이 없어요.」, 「이 프로세스에는 저장된 BPMN 다이어그램이 없어요.」. 상자는 유리 카드 모서리 22px · 안쪽 36~40px · 가운데 정렬 · `--text-secondary` | `MiningView.vue:146`, `:334`, `ImproveView.vue:178`, `FolderList.vue:133-138`, `:207`, `AgentActivity.vue:106`, `BpmnView.vue:70`, `MissionList.vue:84` |
| 목록 「더 보기」 | 테두리 없는 글 단추 14px `--text-secondary`, 위아래 10px. 문구에 숨은 개수를 넣는다(「완료된 프로세스 N개 더 보기」, 「지난 변형 N개 (반영됨·버림)」, 「… 외 N단계」, 「외 N개 파일」) | `ProjectList.vue:45`, `:64`, `FolderDetail.vue:258`, `SkillList.vue:84`, `InstanceHeader.vue:78` |
| 단계 타임라인 | 세로 목록, 칸은 24px(점) + 나머지, 사이 10px, 줄 아래 14px. 점은 24px 원 · 바탕 `--cell-bg` · 안쪽 2px `--hairline` 테. 끝남 = 초록 칠 + 12px 체크. 진행 중 = 안쪽 2px `--text-primary` 테. 에이전트가 실제로 도는 중 = 1.6초 맥박. 내 차례 = 주황 칠. 실패 = 빨강 칠. 게이트웨이 = 45도 돌린 모서리 6px 사각형(크기 .78). 건너뜀 · 취소 = 불투명도 .38. 이음선은 점 가운데(왼쪽 11px) 2px `--hairline`, 끝난 단계 아래 선은 초록 55% 섞음. 단계 이름 15px · 줄 높이 1.35, 대기 단계 이름은 `--text-secondary`, 역할 줄 12.5px + 종류 아이콘(사람 손 · 에이전트 패널). 줄은 40ms씩 늦게 차례로 나타난다 | `StepTimeline.vue:9`, `:13-35`, `:40-66` |
| 진행 막대 | 높이 4px, 모서리 4px, 바탕 `--hairline`, 채움 `--text-primary`(밝은 테마에서 검정), 폭 변화 0.8초 스프링. 분자 · 분모는 사람 · 에이전트 단계만 | `InstanceHeader.vue:46`, `:103-104`, `:24-27` |
| 대화 입력창 | 최소 높이 48px, 모서리 24px, `glass-thin`에 `--composer-bg`. 글자 15px · 줄 높이 19px, 글이 늘면 200px까지 자란다. 아이콘 단추 36px 원, 보내기 36px 검정 원 | `Composer.vue:41-46`, `:152-160` |
| 폼 입력 칸 | 높이 44px, 완전 둥근, 바탕 `--field-bg`, 15px, 포커스 때 안쪽 1.5px `--text-primary` 테. 여러 줄은 모서리 18px. 선택지는 36px 알약 단추(고르면 `--ink`), 참 · 거짓은 48×28 토글. 라벨 13px `--text-secondary` | `FormCard.vue:85-94` |
| 설정 입력 칸 | 높이 48px, 완전 둥근, 바탕 `--cell-bg`, 16px | `SettingsSheet.vue:389` |
| 글 크기 단계 | 본문 기본 16px · 자간 -0.005em(`base.css:70-78`). 화면 제목: 마이닝 · 개선 · 폴더 h1 30px · 500(`MiningView.vue:327`, `ImproveView.vue:469`, `FolderList.vue:189`), 설정 h1 34px · 500(`SettingsSheet.vue:359`), 상세 큰 제목은 서체 38~40px(`ImproveView.vue:477`, `MiningView.vue:357`), 인스턴스 제목 서체 30px · 300(`InstanceHeader.vue:101`), 대화 카드 제목 서체 22~24px(`Message.vue:171`, `FormCard.vue:82`). 본문: 말풍선 16px · 줄 높이 1.6(`Message.vue:157`), 단계 이름 15px. 보조: 13~14px `--text-secondary`. 라벨 · 태그: 11.5~12.5px |
| 아이콘 | 한 파일(`Icon.vue`)에 선 아이콘 경로를 모아 두고 크기만 넘긴다(home · plus · mic · close · back · chevron · trash · check · alert · expand …) | `src/components/Icon.vue:1-20` |
| 움직임 | 나타날 때 흐림이 걷히며 6px 올라오는 `blur-in` 0.5초 스프링, 목록은 `pop-in`, 반짝이는 글 `shimmer-text` 2.2초, 맥박 `pulse` 1.6초 | `base.css:112-136` |

---

## 5. 실시간으로 흘러나오는 자리

| 자리 | 무엇이 보이나 | 「무엇을 읽고 불렀는지」가 보이나 | 근거 |
|---|---|---|---|
| 대화 답을 쓰는 동안(입력창 위 알약) | 서버가 에이전트가 방금 손댄 도구를 일상어 단계로 바꿔 보낸다. 예: 「문서 읽는 중」, 「찾아보는 중」, 「파일 살펴보는 중」, 「메일 확인하는 중」, 「프로세스 확인하는 중」. 글은 `shimmer-text`로 반짝인다. 도구가 없으면 「생각하는 중」, 스레드가 일하는 상태면 「작업하는 중」. 옆에 「멈추기」 | **종류만 보인다.** 도구 이름 · 인자 · 파일 경로는 보이지 않는다. 주석: "What the person sees above the composer while the agent works (hark's "패널 만드는 중"): the tool the agent just reached for, in everyday words." | `server/lib/agent.js:536-557`, `:822-828`, `src/components/ChatColumn.vue:16`, `:24`, `:68-70`, `src/stores/app.js:156-157`, `base.css:122-128` |
| 대화 답의 글 | 답 글이 말풍선 안에 조각조각 흘러나온다(`delta` 이벤트) | 답 글 자체 | `src/stores/app.js:179`, `:199`, `ChatColumn.vue:63` |
| 스킬을 만드는 동안 | 「스킬 만드는 중 · 파일 작성 (3단계)」처럼 단계 이름과 몇 번째 단계인지. 원 출력은 숨기고 끝에 요약 카드 | 단계 종류와 횟수만 | `server/lib/agent.js:524-534` |
| 프로세스 인스턴스 화면 | RUNNING이면 5초마다, process 이벤트가 오면 즉시 다시 읽는다. 타임라인에서 실제로 도는 에이전트 단계는 이름이 반짝이고 점이 맥박친다. 사람 차례인 단계는 멈춘 「확인 대기」 | 단계 단위만 | `src/views/MainView.vue:62-64`, `src/stores/app.js:153-155`, `StepTimeline.vue:18`, `:21`, `:46-48` |
| 「동작 보기」 시트 | 그 단계의 이벤트 로그를 3초마다 다시 읽는다(단계가 active일 때). 도구 호출마다 한 줄: 시각(초까지), 셸이면 `$ 명령`, 아니면 `› 도구 이름 + 파일 경로 / URL / 검색 패턴 / 메모`. 아직 도는 호출은 작은 회전 고리. 셸 출력은 96px로 잘라 바로 보이고, 다른 도구의 결과는 줄을 눌러야 펼친다. 시작 · 완료 표시, 에이전트 메모(task_working), 오류, 사람 확인 요청 줄도 섞인다. 머리에 「도구 호출 N회 · 셸 명령 N회 · 실행 중」 | **보인다.** 무엇을 읽고(파일 경로) 무엇을 불렀는지(도구 · 명령 · 결과)가 시간순으로 쌓인다. 단, 접혀 있는 시트를 열어야 한다 | `AgentActivity.vue:6-7`, `:14-21`, `:28-59`, `:61-70`, `:84-86`, `:92-106`, `:132` |
| 왼쪽 목록의 인스턴스 배지 | 회전 고리 「에이전트 작업 중」은 에이전트가 작업 항목을 실제로 잡고 있을 때만(`draft_status`가 STARTED이거나, 소비자가 있거나, 임대 기한이 남음). 사람 대기는 손 아이콘의 멈춘 「담당자 확인 대기」, 그 밖은 멈춘 점의 「진행 중」, 실패는 빨강 | 상태만 | `ProjectList.vue:36-42`, `server/lib/processes.js:88-91`, `:113-117`, CHANGELOG.md:192 |
| 브라우저 작업 카드 | CDP 화면 캡처가 실시간 그림으로 흐르고, 진행 중이면 제목 알약에 점 세 개가 움직인다. 제목 알약을 누르면 계획 단계 목록(끝난 것 표시)이 뜬다 | 화면 그림과 계획 단계 | `TaskCard.vue:11`, `:41-60`, README.md:199 |
| Home 메일 액션 카드 실행 중 | 카드 글이 반짝인다 | 아니다 | `ActionCard.vue:33` |
| 마이닝 추천 대화 | 「확인하는 중」 반짝이는 말풍선, 다이얼 둘레에 회전 테두리 | 아니다 | `MiningView.vue:302`, `:420` |
| 예약 실행 기록 | 실행 중인 기록의 상태 글이 맥박친다 | 아니다 | `MissionList.vue:164` |
| 폴더 | 색인 중 배지에 회전 고리, 올리는 중인 파일 이름과 고리, 변형 작업 중 고리 | 파일 이름만 | `FolderList.vue:159`, `FolderDetail.vue:163`, `:244` |
| 작업실 | Claude Code 세션이나 셸 터미널 자체가 실시간 화면이다. deepagents 실행이면 터미널 아래에 「실행 중인 에이전트에게 방향 지시」 입력 | **전부 보인다**(터미널 원문) | `WorkroomView.vue:2-6`, `:161-173` |
| 개선 화면 | 「기록을 읽고 계산하는 중…」, 「다시 계산하는 중…」 멈춘 글 | 아니다 | `ImproveView.vue:418`, `:446` |

정리: lite는 「도는 고리만」을 피하려고 고리를 실제로 일할 때만 돌리고(CHANGELOG.md:192), 대화에서는 무엇을 하는지를 일상어 한 줄로 흘린다. 그러나 대화에서는 파일 이름 · 도구 인자까지 흘리지 않고, 그 원문은 프로세스 단계의 「동작 보기」 시트와 작업실에서만 보인다.

---

## 6. 흐름 그림 · BPMN

- **쓰는 부품**: `bpmn-js`의 `NavigatedViewer`(보기 전용, 끌기 · 확대만 됨, 편집 불가)다. `bpmn-js/dist/assets/diagram-js.css`와 `bpmn-js.css`를 함께 싣는다(`src/components/BpmnView.vue:3-5`, `:49`). 판은 `bpmn-js ^18.31.1`이다(`package.json`). 개선 화면의 열지도도 같은 뷰어에 `overlays`를 얹는다(`src/components/improve/HeatBpmn.vue:6`, `:34-66`).
- **그림 원천**: 서버 `/api/processes/:defId/bpmn`이 저장된 BPMN XML을 주고 `importXML`로 그린다(`BpmnView.vue:29-33`). 서버는 본판 프런트의 `getRawDefinition`과 같은 순서로 찾는다(`server/lib/processes.js:240`).
- **상태 칠하기**: 단계 id마다 `canvas.addMarker`로 표시 하나를 단다. 내 차례(`st-mine`)가 끝남(`st-done`)보다, 끝남이 진행(`st-active`)보다 먼저다(`BpmnView.vue:17-27`). 단계 상태가 바뀌면 다시 칠한다(`BpmnView.vue:53`).
  - 끝남: 채움 `#0F9D58` 22% 섞음, 테 `#0F9D58` 2px(`BpmnView.vue:97`).
  - 진행: 테 `--text-primary` 2.5px + 1.6초 맥박(`:98`).
  - 내 차례: 채움 `#FF4D00` 18% 섞음, 테 `#FF4D00` 2.5px(`:99`).
  - 건너뜀: 불투명도 .35(`:100`).
  - README의 말: 「bpmn-js로 렌더, 단계 상태 색칠(완료 초록 / 내 차례 주황 / 진행 중 강조), 크게 보기」(README.md:232).
- **테마 맞추기**: bpmn-js가 줄 단위 style로 그리므로 CSS `!important`로 덮는다. 도형 테는 `--text-secondary`, 채움은 `--regular-solid-bg`, 연결선은 `--text-tertiary`, 글은 `--font-sans`, 풀 · 레인은 투명 채움에 `--hairline` 테(`BpmnView.vue:89-96`).
- **bpmn.io 표시를 숨긴다**: `.bjs-powered-by { display: none; }`(`BpmnView.vue:90`). bpmn-js 배포본의 라이선스(bpmn.io License)는 그림에 붙는 bpmn.io 표시를 지우거나 가리지 말라고 요구하는 것으로 알고 있으나, 이 clone에는 `node_modules`가 없어 그 라이선스 파일을 직접 확인하지는 못했다. 우리 포털은 이 부분을 따라 하지 않는다.
- **크기**: 기본 높이 값은 360px이고, 그림의 가로세로 비를 따라 `max(180, min(높이 값, 칸 폭 × 그림 높이 ÷ 그림 폭 + 48))`로 줄인다(넓은 흐름이 실처럼 가늘어지지 않게, `BpmnView.vue:10`, `:34-37`). 인스턴스 화면은 380px(`InstanceHeader.vue:56`), 프로세스 카드 · 마이닝 등록 정의는 300px(`ProcessCard.vue:59`, `MiningView.vue:267`), 개선 열지도는 330px · 크리티컬 패스는 300px(`ImproveView.vue:224`, `:331`). 높이가 0.42초 동안 바뀐 뒤 화면에 맞춘다(`BpmnView.vue:39-41`).
- **도구**: 오른쪽 아래에 높이 30px 알약 「맞춤」 · 「크게 보기」(`BpmnView.vue:71-74`, `:87-88`). 「크게 보기」는 그림을 `body`로 옮겨 화면 가장자리 40px 안쪽을 채우고 뒤를 흐린다(`BpmnView.vue:65-68`, `:85-86`).
- **놓인 자리**: 인스턴스 화면에서는 기본이 단계 목록이고 그림은 「다이어그램」 세그먼트 뒤에 있다(`InstanceHeader.vue:17`, `:52-56`). 프로세스 카드에서도 「흐름 보기」를 연 뒤 「목록 / 다이어그램」을 고른다(`ProcessCard.vue:56-59`).

---

## 7. 스킬 · 커넥터 · 팀 역할 · 예약 미션 화면

| 화면 | 목록 줄 하나에 보이는 것 | 상세를 여는 법 | 추가 단추 | 삭제 단추 | 근거 |
|---|---|---|---|---|---|
| 스킬(설정 › 스킬) | 스킬 이름, 예약이 있으면 「예약 N」 태그, 설명 2줄 잘림, 오른쪽 꺾쇠. 목록 위에 「테넌트 스킬 N개 · 채팅에서 "○○ 스킬 만들어줘"로 추가돼요.」 | 줄 전체를 누르면 같은 시트 안의 상세(`/settings/skills/:name`)로 바뀐다. 상세: 서체 28px 이름, 설명, 서비스 태그, 「절차 N단계」, 절차 목록과 쓰는 도구, 「SKILL.md 전체 보기」(시트), 이 스킬을 쓰는 예약, 주기 프리셋 칩 4개(고르면 입력값 JSON과 「○○ 예약 만들기」) | 없다(대화로 만든다) | 상세 맨 아래 「스킬 삭제」(빨간 글 알약, 확인 창) | `SkillList.vue:57-68`, `:70-110`, `:17-22`, `:49-53`, `:120` |
| 스킬(폴더 › 스킬 탭) | 스킬 이름 · 폴더 설명, 공개 범위 뱃지(내 스킬 / 전사 공유), 작성자, 진행 중인 변형 수 | 줄을 누르면 그 스킬 폴더(`/folders/:slug`)로 간다. 고칠 점은 변형으로 제안하고 작성자 · 담당자가 반영한다 | 없다 | 없다 | `FolderList.vue:120-130`, `FolderDetail.vue:138-144`, `:199-218` |
| 커넥터(설정 › 계정 › 연결) | 고정된 다섯 카드(Google · YouTube · Slack · GitHub · Notion). 카드마다 파비콘, 이름, 안내 한 줄, 오른쪽에 「✓ 연결됨」 또는 「연결」 단추(YouTube는 공개 데이터라 둘 다 없음), 아래에 그 커넥터의 도구 이름 칩 전부(미연결이면 흐리게). 연결된 카드에는 「다시 연결(권한 넓히기)」 또는 「토큰 바꾸기」 밑줄 글 단추. 목록 아래에 「토큰은 암호화된 보관함에만 저장되고, … mcp-hub 에서 이 계정에 묶입니다」 | 상세 화면이 없다. 토큰형은 「연결」을 누르면 카드 안에 비밀 입력 · 「토큰 만들기」 링크 · 「저장」이 펼쳐진다. Google은 OAuth 창으로 간다 | 없다(임의 MCP 서버 등록 화면 없음) | 없다(연결 끊기 없음) | `ConnectorCards.vue:15-21`, `:32-36`, `:48-67`, `:82-83`, `server/mcp/connectors.js:12`, `:45` (검색어 「disconnect · 연결 끊 · 연결 해제 · MCP 서버 추가 · 서버 등록」 화면 쪽 0건) |
| 팀 · 역할(설정 › 팀·역할) | 팀원 줄: 머리글자 원, 이름(나이면 「· 나」), 이메일, 관리자에게만 「빼기」. 역할 줄: 역할 이름, 그 역할을 쓰는 프로세스 이름들(가운뎃점으로 이음), 오른쪽 담당자 선택(기본 「시작한 사람」). 그 프로세스만의 담당이 있으면 아래에 「↳ 프로세스 이름」 하위 줄과 선택(「위 담당 따름」). 담당이 있는 역할이 먼저 온다 | 상세 화면이 없다. 줄 안의 선택을 바꾸면 바로 저장한다 | 팀원 목록 바로 아래 이름 · 이메일 입력 + 「+ 팀원 추가」(관리자만). 비관리자에게는 「팀원 추가·빼기와 역할 담당 지정은 관리자만 할 수 있어요.」 | 팀원 줄 오른쪽 「빼기」 글 단추(관리자만, 나 자신 제외) | `TeamRoles.vue:22-27`, `:69-107` |
| 예약된 작업(설정 › 예약된 작업) | 이름(일시정지면 태그), 「Custom schedule (cron) · 스킬 X / 프로세스 X / 프롬프트」, 마지막 실행 「완료됨 – 11월 15일 오전 8:00」, 오른쪽 꺾쇠. 비어 있으면 대화로 만드는 법 한 문장 | 줄을 누르면 같은 자리가 상세로 바뀐다(「← 목록」). 상세: 상태 스위치(일시정지), 일정과 다음 실행, 전달 위치, 스킬, 입력, 실행할 에이전트(Deep Agents · Claude Code · Codex 세그먼트), 알림 방식, 「지금 실행」 · 「삭제」, 이전 실행 카드들(요약 · 인스턴스 보기 · 만든 일정). 대화에 올라온 예약 실행 구분선의 「○○ 관리」 알약으로도 바로 열린다 | 없다(대화나 스킬 저장 때 주기로 만든다) | 상세 안 「삭제」(빨간 글 알약, 확인 창 없음) | `MissionList.vue:72-85`, `:87-125`, `:31-33`, `:64-68`, `Message.vue:63` |

---

## 8. lite에 없는 것

| 찾은 것 | 결과 | 찾은 방법 |
|---|---|---|
| 지식 그래프 · 온톨로지 화면 | **없음.** | `src` · `server`에서 `neo4j`, `ontology`, `온톨로지` 0건. `graph`는 개선 화면의 프로세스 흐름 그래프(CPM, `server/lib/improve/graph.js`)와 VectorCraft 설명에만 나온다. `그래프`도 VectorCraft 설명 한 줄뿐(`server/lib/systems.js:25`) |
| 문서를 올려 지식으로 적재하는 전용 화면 | **전용 화면은 없음.** 적재는 두 길로 일어난다. ① 대화 첨부: 입력창의 📎 · 붙여넣기 · 끌어 놓기로 한 번에 10개까지(파일당 50MB) 올리면, 보낼 때 memento `/save-to-storage`에 그 대화(room) 몫으로 저장 · 색인되어 「이 대화의 지식 문서」가 된다. 색인하는 형식은 pdf · hwp · hwpx · doc · docx · pptx · txt · xlsx. ② 공유 폴더 「올리기」: 파일을 main에 커밋하면 색인이 돌아 문서마다 빠른 모델로 1~2문장 요약 + 키워드 「문서 카드」를 만든다. 문서가 200개, 카드 약 12k 토큰, 본문 5MB를 넘으면 본문 색인을 켜고 memento `/knowledge/files/upload`로도 보낸다 | `src/components/Composer.vue:48-75`, `:133`, `src/stores/app.js:164-171`, `server/lib/attachments.js:1-5`, `:15-18`, `:48-69`, `:82`, `src/components/folders/FolderDetail.vue:73-84`, `:164-167`, `:190`, `server/routes/folders.js:156-161`, `server/lib/folders/indexer.js:1-4`, `:21`, `:106-137`, `:139-147` |
| 여러 문서를 한 번에 적재 | **부분적으로 있음.** 폴더에 여러 파일 · 폴더째 끌어 놓을 수 있으나, 화면이 파일마다 하나씩 차례로 올리고(요청 하나에 파일 하나) 색인은 서버 대기열이 뒤에서 돌린다. 끝나면 「올렸어요 — 문서 카드는 잠시 뒤 생겨요」. 「저장소 연결」은 이 컴퓨터의 git 저장소 경로를 통째로 폴더로 잇는다(내용은 바꾸지 않음) | `FolderDetail.vue:73-84`, `server/routes/folders.js:41-45`, `:156-161`, `FolderList.vue:169-172` |
| 사람이 AI 추출 결과를 검토한 뒤 적재 | **문서 카드에는 없음.** 카드는 모델 답을 그대로 저장하고(`makeCard`), 화면은 「색인」 탭의 「에이전트가 보는 목록」(읽기 전용 텍스트)과 「카드」 뱃지 툴팁으로 보여 줄 뿐 고치거나 승인하는 단추가 없다. 비슷한 「AI 초안 → 사람이 확인해 저장」 길은 다른 곳에 있다: 프로세스 초안 카드의 「프로세스로 저장」, 스킬 초안의 저장, 마이닝 추천의 「정식 등록 / 보류」와 「확인 필요」 범주 지정, 폴더 변형의 검토 후 반영, 보관함이 브라우저에서 잡은 값의 「저장」 확인, 개선안 적용 확인 창 | `server/lib/folders/indexer.js:115-137`, `FolderDetail.vue:220-229`, `:113-114`, `ProcessDraftCard.vue:41`, `SkillDraftCard.vue:67-73`, `MiningView.vue:153-167`, `:254-261`, `FolderDetail.vue:276-279`, `SettingsSheet.vue:214`, `ImproveView.vue:451-459` |
| 대시보드 · 지표 화면 | **시스템 대시보드는 없음.** 지표가 있는 화면은 프로세스 개선(`/improve`) 하나다(완료 수 · 리드타임 중앙값과 p80 · 흐름 효율 · 가동률 · 표 · 간트). 사람이 말로 만드는 Home 「패널」(미니 앱)이 대시보드 노릇을 하며, 서버는 「대시보드 · 현황판 · 추적」 같은 말을 패널 만들기로 보낸다 | `ImproveView.vue:195-200`, `:228-243`, `:333-344`, `server/lib/agent.js:483-484`, `HomeDock.vue:34-38`, README.md:202 (`dashboard`, `대시보드`는 이 두 줄에서만 나옴) |
| 시스템 구성 그림 화면 | **없음.** 구성은 README의 글자 그림뿐이다. 설정 › 보안은 보관함 암호화 설명을 글 목록으로 보일 뿐 그림이 아니다 | README.md:61-77, `SettingsSheet.vue:297-329` (`architecture`, `구성도` 검색 0건) |
| 서버 라우트 | `server/index.js`와 `server/routes/*.js`의 경로를 훑었다. `/api/attachments`(대화 첨부 하나), `/api/folders/:slug/files`(폴더 파일 하나), `/api/folders/:slug/reindex`, `/api/folders/search`가 문서 쪽 전부이고, `knowledge` · `graph` · `ontology` · `dashboard` 경로는 없다 | `server/index.js:381-385`, `server/routes/folders.js:46`, `:91`, `:156` |

---

## 9. 우리 포털을 덜어 낼 때 쓸 만한 점(조사자의 정리)

- 최상위 이동은 탭 셋뿐이고, 관리 · 분석 화면(마이닝 · 개선)은 메뉴 없이 알림 카드와 본문 링크로 들어간다. 설정류는 아바타 뒤 시트 한 목록에 모은다(`TopBar.vue:19`, `NotificationCard.vue:37-39`, `SettingsSheet.vue:26`).
- 「추가」 단추를 두지 않고 대화로 만들게 하며, 빈 목록이 「채팅에서 ○○라고 하면 여기에 생겨요」로 길을 알려 준다(`SkillList.vue:58`, `MissionList.vue:84`, `FolderDetail.vue:257`).
- 색은 내 차례에만 쓴다. 주황은 내가 할 일, 빨강은 실패, 멈춘 회색은 남이 할 일 · 대기이고, 회전 · 맥박은 에이전트가 실제로 일할 때만이다(CHANGELOG.md:192, `ProjectList.vue:36-42`, `StepTimeline.vue:46-49`).
- 원문은 접고 결론을 먼저 보인다. 문서는 140~150px만, 완료 건은 3개만, Home 카드는 개수 상한, 경로는 파일 이름으로, 에이전트 도구 기록은 「동작 보기」 시트로, 삭제 · 시각 · 근거는 마우스를 올리거나 툴팁으로(3.3절).
- 흐르는 표시는 두 층이다. 대화에서는 「문서 읽는 중」 같은 일상어 한 줄을 흘리고, 단계별 원문(명령 · 경로 · 출력)은 3초마다 새로 읽는 상세 시트에 둔다(`server/lib/agent.js:536-557`, `AgentActivity.vue:14-21`).

주의할 점도 둘 있다. lite가 모든 화면을 덜어 낸 것은 아니다. 개선 · 마이닝 · 폴더 상세는 표와 태그가 빽빽한 화면이다(2.2절: 개선 병목 탭 글 77, 마이닝 추천 태그 61, 사례는 개수 제한 없이 모두 그림). 그리고 bpmn.io 표시를 CSS로 숨긴다(6절). 이 두 가지는 본뜨지 않는다.
