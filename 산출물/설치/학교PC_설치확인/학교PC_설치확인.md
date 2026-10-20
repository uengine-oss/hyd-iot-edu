# 학교 PC 설치 · 실행 확인

유압설비 조치 포털 실습 스택을 학교 PC에 설치하고, 끝까지 켜지고 도는지를 30분 안에 확인하는 순서다. GitHub에서 이 문서를 열어 따라 한다(폰도 된다).
그림은 모두 2026-10-19에 클라우드(Linux)에서 스택을 실제로 띄워 진행한 순서대로 찍었다.
Windows 화면은 클라우드에서 찍을 수 없어 「자리」로 표시했다. 학교에서 처음 확인할 때 그 자리를 채운다.

## 명령을 치는 창은 세 가지다

명령 상자 위에 어느 창인지 적어 두었다. 명령은 상자 오른쪽 위 복사 버튼(GitHub)으로 복사해 창에 붙여 넣고 Enter를 누른다. PowerShell 창에서는 **마우스 오른쪽 클릭이 붙여넣기**다.

| 표시 | 여는 법 | 쓰는 곳 |
|---|---|---|
| **[PowerShell]** | 시작 버튼 → `PowerShell` 입력 → Enter | 저장소 받기, 버전 확인 |
| **[관리자 PowerShell]** | 시작 버튼 → `PowerShell` 입력 → 오른쪽 「관리자 권한으로 실행」 → 권한 창 「예」. 창 제목이 「관리자: Windows PowerShell」이면 맞다 | Windows 기능 켜기, 권한 설정 |
| **[VS Code 터미널]** | VS Code에서 실습 폴더를 연 채 위 메뉴 「터미널 → 새 터미널」 | 실습 코드 실행(`python llm_client.py`) |

`.bat` 파일은 창을 열 필요 없이 파일 탐색기에서 **더블클릭**한다.

## 0. 설치와 실행은 더블클릭 셋이다

| 순서 | 할 일 | 걸리는 시간 |
|---|---|---|
| 1 | Git이 없을 때만: **[PowerShell]** 에 `winget install -e --id Git.Git` | 2분 |
| 2 | **[PowerShell]** 에 아래 명령을 붙여 넣는다. 모든 계정이 쓰는 공용 폴더 `C:\hyd-iot-edu`에 받는다 | 1~2분 |
| 3 | 파일 탐색기에서 `C:\hyd-iot-edu`를 열고 **`설치.bat`** 을 더블클릭한다. 권한을 묻는 창에서 「예」. XG5000은 따로 설치한다. `설치.bat`이 안 되면 E절대로 하나씩 설치한다 | 처음 20~40분 |
| 4 | 결과 표 끝에 「PC를 다시 시작하세요」가 나오면 다시 시작하고, Docker Desktop을 한 번 열어 약관에 동의한다 | 5분 |
| 5 | **`시작.bat`** 을 더블클릭한다. Docker Desktop이 꺼져 있으면 스스로 켜고 기다린다 | 처음 10분 이상, 두 번째부터 짧다 |
| 5-1 | **`점검.bat`** 을 더블클릭한다(메인 PC에서 한 번). 서비스 응답 · 쿨러 사건 한 바퀴 · 실습 중계 연결을 자동으로 확인하고, 실습 `.env`가 비어 있으면 중계 주소와 키를 물어 적는다. 결과 표가 모두 「통과」면 된다 | 3~5분 |
| 6 | (5회차 실습 때만) 실습 폴더 `.env`에 세 줄을 적는다 | 1분 |

2번 — **[PowerShell]**:

```
git clone -b develop https://github.com/uengine-oss/hyd-iot-edu.git C:\hyd-iot-edu
```

끌 때는 **`끄기.bat`** 을 더블클릭한다. 데이터는 지워지지 않는다.

**포트가 겹치는 PC.** 실습 포트를 다른 프로그램이 이미 쓰고 있으면 `시작.bat`이 그 서비스만 비어 있는 다른 포트로 옮기고(예: 3000 → 13000), 마지막에 「이 PC에서 옮긴 포트」와 그 PC의 포털 주소를 보여 준다. 포털 화면은 옮긴 포트를 알아서 쓴다. 업무 DB 포트(54321~54326)는 옮기지 않고, 겹치면 어느 프로그램인지 알리고 멈춘다.

**중계키 발급(강사 PC에서).** `scripts/relay_key.ps1`이 마스터 키로 학생용 키를 발급하고 실제로 답이 오는지 확인한 뒤, 실습 `.env`에 넣을 세 줄을 보여 준다. 마스터 키를 쓰므로 학교 PC가 아니라 강사 PC(gcloud 로그인)에서 실행한다. 서버 주소와 GCP 프로젝트는 실행할 때 묻는다. **[PowerShell]**:

```
powershell -ExecutionPolicy Bypass -File scripts\relay_key.ps1 -Alias gnu-class -Budget 10 -Duration 30d
```

이미 받은 키가 되는지만 볼 때:

```
powershell -ExecutionPolicy Bypass -File scripts\relay_key.ps1 -Verify
```

**`설치.bat`이 하는 일.** 학교 설치 목록(실습 스택 정보 xlsx, 확인일 2026-10-12)의 1~6번을 **목록과 같은 판으로** 설치한다(없는 것만). 7번 Arduino IDE는 빼고, 8번 XG5000은 직접 설치한다. 설치는 Windows 기본 설치 도구(winget)가 각 프로그램의 공식 배포처에서 받아 해시를 검사하고 무인 모드로 한다. 이미 있는 프로그램은 바꾸지 않고, 판이 목록과 다르면 결과 표에 **「다른 판」** 으로 알린다(맞추려면 그 프로그램을 지우고 `설치.bat`을 다시 실행).

| 목록 번호 | 프로그램 | 판 | 설치 방법 | 확인할 것 |
|---|---|---|---|---|
| — | BIOS 가상화 | — | 확인만 한다. 대부분 켜져 있어 꺼졌을 때만 표에 뜬다 | 「꺼짐」이 뜨고 Docker가 안 돌면 BIOS에서 Intel VT-x / AMD SVM을 켠다 |
| 2 | WSL 2 | 2.7.12 | Windows 기능 둘(Linux용 Windows 하위 시스템 · 가상 머신 플랫폼)을 켜고 winget `Microsoft.WSL` | 처음이면 PC를 다시 시작해야 켜진다 |
| 1 | Docker Desktop | 4.87.0 | winget `Docker.DockerDesktop` | 로그인한 계정과 「로그인한 모든 계정(Authenticated Users)」을 `docker-users` 그룹에 넣는다(복제된 PC의 다른 계정도 Docker를 쓴다). 다시 시작한 뒤 한 번 열어 약관 동의 |
| 3 | Visual Studio Code | 1.140.0 System | winget `Microsoft.VisualStudioCode`(PC 전체) | GitHub Copilot 채팅은 VS Code 안에서 로그인 |
| 4 | Python | 3.14.7 | winget `Python.Python.3.14`(PATH에 넣음) | 5회차 실습의 `python llm_client.py` |
| 5 | Node.js | 22.16.0 | winget `OpenJS.NodeJS.22` | — |
| 6 | Git | 버전 무관 | winget `Git.Git`(winget 최신판) | 있으면 건너뛴다 |
| 8 | XG5000 | 4.73 | **직접 설치** — E-7의 4.73 파일 링크 | `설치.bat`은 건드리지 않는다 |

저장소 폴더가 공용 폴더(`C:\hyd-iot-edu` 등)이면 로그인한 모든 계정에 쓰기 권한을 주고 Git 신뢰 폴더(`safe.directory`)로 등록한다. 사용자 폴더(`C:\Users\…`) 안이면 「옮김 권장」을 띄운다. 목록 밖으로 supabase CLI도 설치를 시도한다(업무 DB를 켜는 데 쓴다. 실패해도 `시작.bat`이 `npx`로 대신 받는다). **디스크**: C 드라이브 여유 40 GB 이상을 권한다. 실습 스택만 실측 약 17 GB(Docker 이미지 13.6 · 빌드 캐시 1.7 · 실습 데이터 1.1 · 컨테이너 0.3 · 저장소 0.5, 2026-10-20 Linux 실측)이고, 프로그램 설치분과 Docker Desktop 자체 여유는 Windows에서 재지 못해 여유를 더했다. PC 메모리가 8 GB보다 적으면 「부족할 수 있음」이 뜬다.

**`git clone` 뒤 `docker compose up`만 하면 안 되는 까닭.** compose의 서비스 26개는 모두 프로필에 묶여 있고, 켤 프로필은 `.env`가 정하는데 `.env`는 저장소에 없다. 업무 DB(Supabase)는 compose 밖에서 따로 켜야 하고, 에이전트용 MCP 두 개는 별도 프로필이다. `시작.bat`이 이 넷(`.env` 강의 배포본 값 · 업무 DB · 시스템 · MCP)을 순서대로 한다.

> **자리** — Windows에서 `설치.bat` 결과 표와 Docker Desktop 「Engine running」 화면.

## A. 필수 확인 (약 30분)

### ① 시작.bat 결과: 단계 6개, 상태 10개, 「완료」

`시작.bat`을 더블클릭하면 검은 창에서 아래 순서가 지나간다. 마지막 줄이 `완료. 포털: http://127.0.0.1:8088`이면 된다.

![start_all.sh 실제 출력. 6/6 단계에서 포트 10개가 모두 ok, 시스템 컨테이너 18 · 업무 DB 9, 마지막 줄 「완료」](img/A1_start_all.png)

- 단계는 `1/6 Docker 확인` → `2/6 .env 준비` → `3/6 업무 DB(Supabase) 켜기` → `4/6 시스템 빌드 · 기동` → `5/6 에이전트용 MCP 서버 둘` → `6/6 상태 확인`이다.
- `6/6`에서 포트 10개(8000 · 8093 · 8090 · 8094 · 8092 · 8091 · 8080 · 8095 · 8199 · 8198)가 모두 `{"ok":true …}`로 나와야 한다.
- 컨테이너 수는 이 실행에서 시스템 18 · 업무 DB 9였다. 업무 DB 수는 supabase CLI 판에 따라 다를 수 있다.
- 그림의 `8091 … "llm":true,"llm_model":"coding"`은 이 클라우드 셸에 LLM 변수가 들어 있어서 나온 값이다. 학생 PC에서는 `"llm":false`가 정상이다. 실습 스택은 LLM 키 없이 끝까지 돈다.

> **자리** — Windows에서 `시작.bat`을 더블클릭한 창(마지막 「완료」 줄과 「계속하려면 아무 키나 누르십시오」).

### ② 포털 홈: 상태 점이 모두 초록

브라우저에서 `http://127.0.0.1:8088`을 연다.

![포털 홈. 위 막대에 「서비스 12/12」 초록 점, 설비 3기 · 열린 사건 0 · 시간 배율 20×](img/A2_home.png)

- 위 막대 오른쪽의 `서비스 12/12` 앞 점이 초록이면 된다.
- 왼쪽 메뉴 맨 아래 「시스템 구성」을 열면 서비스마다 점이 보인다. FUXA · Prometheus · Redpanda Console처럼 「(선택 도구)」라고 적힌 것은 꺼져 있어도 된다.

![시스템 구성. 서비스마다 초록 점](img/A2_system.png)

### ③ 쿨러 사건 한 바퀴

먼저 알아 둘 것이 있다. 새로 설치한 PC의 지식 그래프는 **수업용 구조판**이다(`SEED_EDITION=structure`, 설비 구조 · 센서 · 감시 패턴 · 규정만 들어 있다). 고장 원인과 조치 방법은 수업에서 학생이 매뉴얼을 적재해 만든다.
그래서 새 PC에서는 사건이 **「원인 진단 — 시스템 보류」에서 멈추는 것이 정상**이다. 승인 · 명령 · 종결까지는 지식이 들어 있어야 간다(③-2).

#### ③-1 새 PC 그대로: 경보 → 처리 건 → 진단 보류 (학생 PC에서 확인)

1. 왼쪽 「내 작업함」에서 **나**를 `김운전 · 운전원`으로 고른다.
2. 「결함 시뮬레이션」 → 오른쪽 위 **전체 초기화** → 20초쯤 기다린다. HYD-01 · 02 · 03 모두 유온 48.0 ℃, 경보 「감시 중」이 된다.

![전체 초기화 뒤. 세 설비 유온 48.0 ℃, 경보 감시 중](img/A3_2_before.png)

3. HYD-01 카드 아래 **쿨러 열화 주입**을 누른다. 이 실행에서는 약 40초 뒤 경보가 났다(유온 55.6 ℃, 냉각 효율 46 %). 카드의 경보 칸이 「경보 발생 · 쿨러 성능 저하」로 바뀐다.

![쿨러 열화 주입 뒤 HYD-01. 경보 발생, 쿨러 성능 비율 55 %](img/A3_3_alarm.png)

4. 「처리 건」을 연다. 새 건이 생기고, 몇 초 뒤 「지금 원인 진단 — 시스템 보류 · 사람 확인 필요」가 된다. **여기까지 오면 설치 확인은 통과다.** 설비 → 수집 → 감지 → 프로세스 → 에이전트 → 지식 그래프 · 시계열 DB가 모두 이어져 있다는 뜻이다.

![처리 건. 원인 진단에서 시스템 보류](img/A3_4_instance.png)

5. 「처리 기록」 탭에 「센서 경보로 시작 → 원인 진단」이 남는다. 보류한 까닭은 지식 그래프에 이 경보의 원인 후보가 없기 때문이다(「현재 관측 근거로 뒷받침되는 원인이 없어 조치를 보류합니다」).

![처리 기록. 센서 경보로 시작한 기록](img/A3_5_record.png)

- 같은 시각 「이상 확인 · 조치」 화면은 이 사건을 「조치 선택 대기 · 조치 후보를 만드는 중…」으로 보여 준다. 처리 건 화면과 표시가 다르지만 고장이 아니다. 판단은 처리 건 화면을 따른다.
- 보류한 건은 그대로 두면 「책임자 확인」(생산관리자) 단계로 넘어간다(이 클라우드에서 09:43에 열린 건이 09:52에 그 단계였다).

![이상 확인 · 조치. 같은 사건이 조치 선택 대기로 보인다](img/A3_6_incident.png)

6. 확인이 끝나면 「결함 시뮬레이션」에서 **쿨러 복구**를 누른다.

#### ③-2 지식이 들어 있을 때: 승인 → 명령 → 재관측 → 종결 (강사 PC 확인용)

이 절은 원인 · 조치 지식이 들어 있는 **전체판**(`SEED_EDITION=full`, 회귀 시험과 같은 지식)을 더 적재한 뒤 같은 사건을 돌린 것이다. 학생 PC에서는 수업에서 매뉴얼을 적재한 뒤에 같은 모습이 된다.

1. **나**를 `이생산 · 생산관리자`로 고르고 「결함 시뮬레이션」에서 전체 초기화 → **쿨러 열화 주입**. 이 실행에서는 경보까지 약 40초 걸렸다.

![경보 발생. 팬 속도 60 %, 펌프 부하 90 %](img/D2_alarm.png)

2. 에이전트 단계 넷(원인 진단 · 조치 후보 조회 · 규정 검토 · 조치 후보 정리)은 각각 1초 안팎에 끝났다. 「처리 건」의 **내 차례**에 「조치 선택」이 뜬다. 누르면 승인 요청 카드가 열린다. AI 에이전트 추천은 「부하 70 % + 야간 세척」이었다.

![처리 건 → 내 차례 「조치 선택」 → 승인 요청. AI 에이전트 추천 카드와 지식 그래프 근거](img/D4_card.png)

3. 맨 아래 **사유**에 한 줄을 적고 **승인**을 누른다.

> 이 추천 카드는 **생산관리자 이상**만 승인할 수 있다. 같은 화면에서 `김운전 · 운전원`으로 승인하면 아래처럼 거부된다. 이것은 정상이다(사람 승인 권한 검사).
>
> ![운전원으로 승인했을 때. 「승인 권한 없음: '부하 70 % + 야간 세척'은(는) 생산관리자 이상이 승인해야 한다」](img/D5_operator_refused.png)
>
> 「조치 선택」은 운전원 공용 단계라 생산관리자의 「내 작업함」에는 뜨지 않는다. 생산관리자는 「처리 건」의 **내 차례**에서 연다.
> 승인 기한은 단계가 열린 뒤 **약 30초**다(흐름의 10분을 20배속으로 줄인 값, 이 클라우드 실측). 지나면 건이 「책임자 확인」으로 넘어가니, 카드가 뜨기 전에 「처리 건」을 열어 두고 바로 승인한다.

![승인 뒤. 조치 선택 단계에 승인 접수 · 승인 전달 완료, 다음은 설비에 명령](img/D6_after_go.png)

4. 승인 뒤 몇 초 안에 「설비에 명령」이 끝난다. 「결함 시뮬레이션」의 HYD-01에서 펌프 부하가 90 %에서 70 %로 바뀌고 「최근 명령 결과 완료」가 된다.

![명령 뒤 HYD-01. 펌프 부하 70 %, 최근 명령 결과 완료](img/D7_after_command.png)

5. 효과 확인(재관측)과 정비 요청 등록이 이어지고 건이 **완료 · 종결**된다. 이 실행에서는 승인부터 종결까지 약 1분 걸렸고, 건 전체는 1분 7초였다.

![처리 건 완료 · 종결, 단계 8/9](img/D8_closed.png)

![종결 뒤 HYD-01. 유온 50.4 ℃, 경보 감시 중](img/D10_cooling.png)

6. **쿨러 복구**를 누른다.

### ④ 5회차 실습 2 폴더: `python llm_client.py` → 「연결됨 · coding」

1. VS Code에서 `course/labs/offline/05-2-cause-agent` 폴더를 연다.
2. 왼쪽 탐색기에서 `.env`를 열어 등호 뒤에 적는다. 주소와 키는 수업에서 받은 것이다(창에서 치는 명령이 아니라 파일 내용이다).

```
OPENAI_BASE_URL=<수업에서 받은 주소>
LLM_API_KEY=<수업에서 받은 키>
LLM_MODEL=coding
```

3. 저장(Ctrl+S)한 뒤 **[VS Code 터미널]** 에서 실행한다. 첫 줄이 `연결됨 · coding`이고 둘째 줄에 서버가 보낸 인사 한 문장이 나오면 된다.

```
python llm_client.py
```

![연결됨 · coding — 실제 중계 서버에서 3초](img/A4_llm_client_ok.png)

> **자리** — 같은 화면을 Windows VS Code 터미널에서 찍은 것.

값을 틀렸을 때는 아래처럼 고칠 곳을 알려 준다. 모두 이 클라우드에서 실제로 나온 글이다(맨 위 줄은 서버 쪽 키를 고치기 전의 상태).

![llm_client.py 실제 출력 여섯 가지](img/A4_llm_client_messages.png)

| 나온 글 | 고칠 곳 |
|---|---|
| `LLM_API_KEY 가 비어 있다` | `.env`를 저장했는지(탭 이름 옆 흰 점) 본다 |
| `LLM_API_KEY 가 받은 키와 다르다` | 키를 다시 붙여 넣는다. 앞뒤 따옴표 · 빈칸이 없어야 한다 |
| `LLM_MODEL 이 서버에 없는 이름이다` | `LLM_MODEL=coding`. Copilot 채팅의 모델 이름(GPT-6 Luna)과는 별개다 |
| `OPENAI_BASE_URL 이 받은 주소와 다르다` · `서버에 닿지 못했다` | 주소를 다시 붙여 넣는다. 끝이 `/v1`이다. 학교 네트워크가 막혔는지도 본다 |
| `중계 서버 뒤쪽의 키가 맞지 않는다` · `서버가 지금 요청을 받지 못한다` | 학생 쪽 문제가 아니다. 강사에게 알린다. 429는 1분 뒤 다시 실행하면 대개 풀린다(서버가 막 깨어날 때 한 번 관찰) |

## B. 화면만 열리는지 (시간 나면)

포털 왼쪽 메뉴에서 차례로 누르고, 별도 도구는 주소를 연다. 화면이 뜨면 통과다.

| 화면 | 여는 곳 |
|---|---|
| 실시간 모니터링 | 포털 메뉴 |
| 지식 지도 | 포털 메뉴 |
| 조치 판단 규칙 | 포털 메뉴 |
| 조건별 손익 | 포털 메뉴 |
| 지식 관리 | 포털 메뉴 |
| 흐름 가져오기 | 포털 메뉴 |
| FUXA (설비 운전 화면) | `http://127.0.0.1:1881` |
| Grafana (설비 추세) | `http://127.0.0.1:3000` |
| Neo4j Browser (지식 그래프) | `http://127.0.0.1:7474` — 로그인 화면이 뜨면 통과 |
| Supabase Studio (업무 DB) | `http://127.0.0.1:54323` |

![실시간 모니터링](img/B1_trends.png)

![지식 지도](img/B2_ontology.png)

![조치 판단 규칙](img/B3_decision.png)

![조건별 손익](img/B4_whatif.png)

![지식 관리](img/B5_knowledge.png)

![흐름 가져오기](img/B6_flows.png)

![FUXA :1881](img/B7_fuxa.png)

![Grafana :3000](img/B8_grafana.png)

![Neo4j Browser :7474](img/B9_neo4j.png)

![Supabase Studio :54323](img/B10_studio.png)

## C. 막혔을 때 첫 조치

`시작.bat` 창에 `[멈춤]`으로 시작하는 줄이 나오면 그 줄의 뜻과 첫 조치는 아래와 같다. 더 자세한 것은 `문서/시스템/참조/RUNBOOK.md` §3이다.

| `[멈춤]` 문구 | 뜻 | 첫 조치 |
|---|---|---|
| `Git for Windows가 없습니다` | `시작.bat`이 bash를 못 찾았다 | Git을 설치하고 다시 더블클릭 |
| `docker 명령이 없습니다` | Docker Desktop이 없거나, 설치 뒤 PC를 다시 시작하지 않았다 | `설치.bat` → PC 다시 시작 → 다시 |
| `Docker가 응답하지 않습니다` | `시작.bat`이 Docker Desktop을 켜고 3분 기다렸지만 엔진이 뜨지 않았다 | Docker Desktop 창을 열어 약관 동의 창이 있으면 동의하고, 「Engine running」을 기다린 뒤 다시 |
| `docker compose가 없습니다` | Docker Desktop이 오래된 판 | Docker Desktop 최신판 설치 |
| `Supabase가 켜지지 않았습니다` | 업무 DB 포트(54321~54329) 충돌이나 이미지 받기 실패 | `cd it/supabase && supabase stop` 뒤 다시(RUNBOOK §3 「Supabase 포트 충돌」) |
| `docker compose up이 실패했습니다` | 이미지 받기 · 빌드 실패 | 창의 오류에서 서비스 이름을 찾아 `docker compose logs <서비스>`. `429` · `Too Many Requests`면 잠시 뒤 다시(D절) |
| `enterprise-mcp · dmn-mcp가 올라오지 않았습니다` | MCP 서버 두 개가 안 떴다 | `docker compose up -d enterprise-mcp dmn-mcp`를 다시 |
| `응답하지 않는 포트: …` | 3분 안에 상태 확인이 끝나지 않았다 | 8080이면 `docker restart hyd-iot-edu-process-1`(RUNBOOK §3 첫 줄). 메모리로 죽으면 Docker Desktop 메모리 4 GB 이상 |

포털에서 경보가 안 나면 HYD-01 카드의 운전 모드가 **원격 자동**인지 본다(RUNBOOK §3 「승인했는데 PLC ACK가 없다」 · 「경보가 안 난다」).

## D. 메인 PC 한 대에 설치하고 학교가 나머지 PC로 복제한다

학교는 메인 PC 한 대에 설치하면 나머지 PC에 그대로 복제해 준다. 이미지를 받는 PC가 한 대뿐이니, 여러 대가 같은 학교 IP로 동시에 받다가 막히는 일(Docker Hub `429`)은 생기지 않는다.
복제한 PC가 이미지를 다시 받지 않고 바로 켜지려면, 복제 전에 메인 PC에서 아래를 끝내 둔다.

1. 저장소를 공용 폴더 `C:\hyd-iot-edu`에 받고(0절 2번) `설치.bat`으로 6개를 설치한다(XG5000은 따로). 프로그램은 모두 PC 전체 설치라 복제된 PC의 모든 계정이 쓴다.
2. `시작.bat`을 한 번 끝까지 돌린다. 이미지 받기 · 빌드가 이때 끝나 메인 PC에 남는다.
3. A절 ①~③-1을 확인한 뒤 「결함 시뮬레이션」 → **전체 초기화**, 그리고 `끄기.bat`.
4. 그 상태로 학교에 복제를 맡긴다.

복제된 PC에서 `시작.bat`이 다시 이미지를 받기 시작하면(4/6 단계에서 `Pulling …` 줄이 길게 이어진다) 복제에 Docker 데이터가 빠진 것이다.
Docker Desktop은 이미지를 **Windows 사용자 계정마다** 저장한다(`%LOCALAPPDATA%\Docker`). 학생이 메인 PC와 다른 계정으로 로그인하면 이미지가 없을 수 있다. 이때는 한 대씩 차례로 `시작.bat`을 돌린다.

이 클라우드에서도 첫 기동 중 Supabase 이미지(public.ecr.aws)를 받다가 레지스트리 한도에 걸려 재시도한 줄이 실제로 나왔다(재시도로 통과). 여러 대가 동시에 받으면 이런 줄이 늘고 결국 멈출 수 있다.

![실제로 나온 레지스트리 한도 줄 — Data limit exceeded, Retrying after 4s](img/R1_registry_limit.png)

## E. 하나씩 직접 설치하기 (`설치.bat`이 안 될 때)

`설치.bat`이 하는 일을 손으로 하는 순서다. 판은 학교 설치 목록과 같다(7번 Arduino IDE 제외). 링크는 각 프로그램의 공식 내려받기 주소다(눌러서 받은 파일을 더블클릭해 설치). 이미 설치된 프로그램은 건너뛴다. 창 여는 법은 맨 앞 「명령을 치는 창은 세 가지다」.

링크 확인(2026-10-20): 아래 다섯 링크는 실제로 받아 본 파일이 그 판이다. WSL · VS Code · Python · Node.js는 크기가 학교 목록 「출처」 시트의 바이트 수와 같고, 다섯 파일 모두 SHA256 해시가 winget 목록과 같다. Docker 4.87.0은 Docker 공식 릴리스 노트(2026-08-17)의 Windows 링크와 같은 빌드(236836)이고 Docker가 낸 체크섬과도 같다. Git은 최신판, XG5000은 페이지에서 4.73을 직접 고른다.

### E-1. WSL 2 (2.7.12)

1. **[관리자 PowerShell]** 에 두 줄을 붙여 넣는다(Windows 기능 둘을 켠다). 줄마다 「작업을 완료했습니다」가 나오면 된다.

   ```
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   ```

2. PC를 다시 시작한다.
3. 받아서 설치한다: <https://github.com/microsoft/WSL/releases/download/2.7.12/wsl.2.7.12.0.x64.msi>
4. 확인 — **[PowerShell]**: 첫 줄에 `2.7.12`가 보이면 된다.

   ```
   wsl --version
   ```

### E-2. Docker Desktop (4.87.0)

1. 받아서 설치한다: <https://desktop.docker.com/win/main/amd64/236836/Docker%20Desktop%20Installer.exe>
2. 설치 화면의 「Use WSL 2 instead of Hyper-V」는 체크된 채로 두고 OK → 끝나면 「Close and restart」.
3. **[관리자 PowerShell]** 에 한 줄을 붙여 넣는다(이 PC에 로그인하는 모든 계정이 Docker를 쓰게 한다). 아무 글 없이 끝나면 된다.

   ```
   Add-LocalGroupMember -Group docker-users -Member S-1-5-11
   ```

4. PC를 다시 시작하고 Docker Desktop을 연다. 약관 「Accept」, 로그인 창은 「Skip」. 왼쪽 아래가 「Engine running」이면 된다.

### E-3. Visual Studio Code (1.140.0, System Installer)

1. 받아서 설치한다: <https://vscode.download.prss.microsoft.com/dbazure/download/stable/07f806f999227108933c2e30515b26eecc1fda74/VSCodeSetup-x64-1.140.0.exe>
2. 기본값 그대로 「다음」. 「PATH에 추가」는 체크된 채로 둔다.

### E-4. Python (3.14.7)

1. 받아서 설치한다: <https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe>
2. 첫 화면 아래 **「Add python.exe to PATH」를 체크**한다.
3. 「Customize installation」 → 「Next」 → **「Install Python 3.14 for all users」를 체크** → 「Install」(복제된 PC의 다른 계정도 쓰게).
4. 확인 — **새로 연 [PowerShell]**(설치 전에 열어 둔 창은 옛 PATH라 안 된다): `Python 3.14.7`이 나오면 된다.

   ```
   python --version
   ```

### E-5. Node.js (22.16.0)

1. 받아서 설치한다: <https://nodejs.org/dist/v22.16.0/node-v22.16.0-x64.msi>
2. 기본값 그대로 「Next」. 「Tools for Native Modules」는 체크하지 않는다.
3. 확인 — **새로 연 [PowerShell]**: `v22.16.0`이 나오면 된다.

   ```
   node --version
   ```

### E-6. Git (최신)

이미 있으면 건너뛴다. 없으면 <https://git-scm.com/downloads/win> 에서 받아 기본값 그대로 설치한다. 확인 — **새로 연 [PowerShell]**:

```
git --version
```

### E-7. XG5000 (4.73)

받아서 설치한다(한국어판, 약 394 MB): <https://sftpssqblobcdn.blob.core.windows.net/prod/largefile/document/16849776042931/XG5000_V4.73_20230522_Kr.exe>

영어판: <https://sftpssqblobcdn.blob.core.windows.net/prod/largefile/document/16849776042930/XG5000_V4.73_20230522_En.exe>. 두 링크는 LS ELECTRIC 자료 페이지 <https://ssq.ls-electric.com/kr/ko/product/document/2201> 에서 판 목록의 4.73을 고르면 나오는 파일이다(2026-10-20 확인).

### E-8. 저장소 받기와 공용 폴더 설정

1. **[PowerShell]** 에 붙여 넣는다(`C:\hyd-iot-edu`에 받는다).

   ```
   git clone -b develop https://github.com/uengine-oss/hyd-iot-edu.git C:\hyd-iot-edu
   ```

2. **[관리자 PowerShell]** 에 두 줄을 붙여 넣는다(복제된 PC의 다른 계정도 이 폴더를 쓰고 `git pull`을 할 수 있게).

   ```
   icacls C:\hyd-iot-edu /grant "*S-1-5-11:(OI)(CI)M" /T /C /Q
   git config --system --add safe.directory C:/hyd-iot-edu
   ```

3. 파일 탐색기에서 `C:\hyd-iot-edu\시작.bat`을 더블클릭한다. 그다음은 A절이다.

## F. 이 문서가 확인하지 못한 것

- Windows에서 `설치.bat` · `시작.bat` · `끄기.bat`을 더블클릭하는 것(「자리」 표시). `설치.bat`의 PowerShell은 문법 검사와 버전 확인 함수만 Linux의 PowerShell 7에서 돌렸고, `시작.bat`의 Docker Desktop 자동 켜기는 가짜 docker로 네 경우(곧 켜짐 · 끝내 안 켜짐 · 이미 켜짐 · 미설치)만 시험했다. winget 설치 자체는 Windows에서만 확인할 수 있다.
- 학교 네트워크에서 LiteLLM 서버 · Docker Hub에 닿는지.
- 학교의 복제 방식으로 Docker 이미지가 함께 복제되는지(D절).
- E절의 직접 설치 순서. 링크는 winget 목록이 쓰는 공식 주소와 같음을 확인했지만, 설치 화면 문구는 Windows에서 따라가 보지 않았다.
- ③-2를 학생 PC의 수업 흐름(매뉴얼 적재 뒤)으로 돌린 것. 이 문서의 ③-2는 회귀 시험용 전체판 지식으로 돌렸다.
