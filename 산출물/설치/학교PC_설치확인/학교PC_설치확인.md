# 학교 PC 설치 · 실행 확인

유압설비 조치 포털 실습 스택을 학교 PC에 설치하고, 시작·점검까지 확인하는 전체 순서다. [README 설치 흐름](../../../README.md#학교-pc에-설치하고-켜기)과 같은 순서로 진행한다. 첫 설치·이미지 다운로드 시간은 PC와 네트워크에 따라 달라진다.

이 문서의 실행 그림은 2026-10-19 클라우드(Linux)에서 실제 스택을 실행한 기록이다. Windows의 실제 설정 화면과 명령어는 [WSL·Docker 오류 해결 가이드](../../../문서/시스템/참조/Windows_Docker_설치.md)에 있다. 학교 PC의 설치 성공을 확인한 기록으로 해석하지 않는다.

## 명령을 치는 창은 세 가지다

명령 상자 위에 어느 창인지 적어 두었다. 명령은 상자 오른쪽 위 복사 버튼(GitHub)으로 복사해 창에 붙여 넣고 Enter를 누른다. PowerShell 창에서는 **마우스 오른쪽 클릭이 붙여넣기**다.

| 표시 | 여는 법 | 쓰는 곳 |
|---|---|---|
| **[PowerShell]** | 시작 버튼 → `PowerShell` 입력 → Enter | 저장소 받기, 버전 확인 |
| **[관리자 PowerShell]** | 시작 버튼 → `PowerShell` 입력 → 오른쪽 「관리자 권한으로 실행」 → 권한 창 「예」. 창 제목이 「관리자: Windows PowerShell」이면 맞다 | Windows 기능 켜기, 권한 설정 |
| **[VS Code 터미널]** | VS Code에서 실습 폴더를 연 채 위 메뉴 「터미널 → 새 터미널」 | 실습 코드 실행(`python llm_client.py`) |

`.bat` 파일은 창을 열 필요 없이 파일 탐색기에서 **더블클릭**한다.

## 0. 설치부터 점검까지

**재부팅하면 초기화되는 PC는 먼저** 강의실 관리자와 복원 기능 해제·변경 유지 방법을 확인한다. 이 준비 없이 설치·재부팅하면 설치 내용이 사라질 수 있다.

| 순서 | 할 일 | 걸리는 시간 |
|---|---|---|
| 1 | Git이 없을 때만: **[PowerShell]** 에 `winget install -e --id Git.Git` | 2분 |
| 2 | **[PowerShell]** 에 아래 명령을 붙여 넣는다. 모든 계정이 쓰는 공용 폴더 `C:\hyd-iot-edu`에 받는다 | 1~2분 |
| 3 | 파일 탐색기에서 `C:\hyd-iot-edu`를 열고 **`설치.bat`** 을 더블클릭한다. 권한을 묻는 창에서 「예」. 결과 표의 실패 항목을 확인한다. XG5000은 없을 때만 별도 설치한다 | 처음 20~40분 이상 |
| 4 | 안내에 따라 재부팅하고 Docker Desktop을 열어 약관에 동의한다. **Engine running** 확인. WSL·Docker 오류는 아래 오류 해결 링크로 복구한 뒤 돌아온다 | PC 상태에 따라 다름 |
| 4-1 | Google Drive에 보관한 `.env`의 주소·중계키·모델 값을 `course/labs/offline/05-2-cause-agent/.env`에 복사하고 저장한다. 이미 값이 있으면 생략 | 1분 |
| 5 | **`시작.bat`** 을 더블클릭한다. Docker Desktop이 꺼져 있으면 스스로 켜고 기다린다 | 처음 10분 이상, 두 번째부터 짧다 |
| 6 | **`점검.bat`** 을 더블클릭한다. 서비스 응답·처리 흐름·중계 연결을 확인한다. 실패가 없고 **중계 서버가 「연결됨」**이어야 한다. 「건너뜀」이면 접속 설정을 확인한다 | 3~5분 이상 |

**WSL 설치나 Docker 엔진 실행이 막히면:** [사진·명령어 오류 해결 가이드](../../../문서/시스템/참조/Windows_Docker_설치.md)에서 Hyper-V 사용 가능 여부부터 확인한다. Docker가 정상 실행되면 위 4-1번부터 계속한다. 이미 다른 프로그램이 설치됐으면 전체 `설치.bat`을 반복할 필요 없이 남은 실패 항목만 해결한다. WSL 이외 도구를 수동 설치해야 하면 E절을 사용한다.

2번 — **[PowerShell]**:

```
git clone -b develop https://github.com/uengine-oss/hyd-iot-edu.git C:\hyd-iot-edu
```

이미 저장소가 있으면 그 폴더의 PowerShell에서 `git branch --show-current`가 `develop`인지 확인한 뒤 `git pull --ff-only origin develop`으로 갱신한다. 로컬 수정으로 갱신이 거부되면 강제로 덮어쓰지 않는다.

끌 때는 **`끄기.bat`** 을 더블클릭한다. 데이터는 지워지지 않는다.

**포트가 겹치는 PC.** 다른 프로그램이 포트를 쓰고 있으면 `시작.bat`이 빈 포트를 찾아 옮긴다(업무 DB·메일 포함). 마지막 완료 메시지의 포털 주소를 사용한다. 포털과 `점검.bat`은 `.hyd-runtime/ports.json`의 같은 포트 설정을 읽는다. 복제된 PC에서도 시작 시 다시 확인한다.

**중계 설정은 기존 키 복사로 끝낸다.** 학교 PC에서 Google Drive에 보관한 `.env`를 열고 `OPENAI_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` 세 항목의 실제 값을 복사한다. 저장소 폴더의 PowerShell에서 아래 명령으로 대상 파일을 연다.

```powershell
notepad.exe '.\.env'
```

해당 세 줄의 값만 바꾸고 Ctrl+S로 저장한다. 저장소 최상위 `.env`를 사용하며, 다른 설정은 유지한다. 파일이 없으면 `.env.example`을 복사해 만든다. `OPENAI_API_KEY`는 비워도 된다. `점검.bat` 더블클릭만으로 루트 설정을 사용한다. 값이 들어 있으면 `점검.bat`에서 주소·키를 다시 묻지 않는다. **기존에 발급한 중계키를 사용하므로 gcloud 조회·키 재발급은 필요 없다.** 키를 넣은 파일은 커밋·푸시하지 않는다. A절 ④의 `python llm_client.py`는 수업에서 직접 연결을 확인하는 추가 절차이며, 지금의 자동 점검을 위해 별도 실행할 필요는 없다.

**`설치.bat`이 하는 일.** 기존 프로그램은 **버전과 관계없이 유지하고 건너뛴다.** 버전을 맞추려고 재설치·업데이트·삭제하지 않는다. 자동 설치 대상은 Docker Desktop·VS Code·Node.js·Git이다. Python·Anaconda는 기존 환경을 유지하며, Python과 WSL은 설치하지 않고 WSL용 Windows 기능도 활성화하지 않는다. 아래 판은 프로그램이 없을 때 설치하는 대상이다. winget으로 공식 배포 파일을 받아 설치하며 Arduino IDE와 XG5000은 자동 설치하지 않는다.

| 목록 번호 | 프로그램 | 판 | 설치 방법 | 확인할 것 |
|---|---|---|---|---|
| — | BIOS 가상화 | — | 확인만 한다. 대부분 켜져 있어 꺼졌을 때만 표에 뜬다 | 「꺼짐」이 뜨고 Docker가 안 돌면 BIOS에서 Intel VT-x / AMD SVM을 켠다 |
| 2 | WSL 2 | — | 자동 설치 제외 | Docker Hyper-V 경로가 정상 실행되면 필요 없음 |
| 1 | Docker Desktop | 4.87.0 | winget `Docker.DockerDesktop` | 로그인한 계정과 「로그인한 모든 계정(Authenticated Users)」을 `docker-users` 그룹에 넣는다(복제된 PC의 다른 계정도 Docker를 쓴다). 다시 시작한 뒤 한 번 열어 약관 동의 |
| 3 | Visual Studio Code | 1.140.0 System | winget `Microsoft.VisualStudioCode`(PC 전체) | GitHub Copilot 채팅은 VS Code 안에서 로그인 |
| 4 | Python | 기존 설치 유지 | 자동 설치 제외 | 5회차 실습의 `python llm_client.py` |
| 5 | Node.js | 22.16.0 | winget `OpenJS.NodeJS.22` | — |
| 6 | Git | 버전 무관 | winget `Git.Git`(winget 최신판) | 있으면 건너뛴다 |
| 8 | XG5000 | 4.73 | **직접 설치** — E-7의 4.73 파일 링크 | `설치.bat`은 건드리지 않는다 |

저장소 폴더가 공용 폴더(`C:\hyd-iot-edu` 등)이면 로그인한 모든 계정에 쓰기 권한을 주고 Git 신뢰 폴더(`safe.directory`)로 등록한다. 사용자 폴더(`C:\Users\…`) 안이면 「옮김 권장」을 띄운다. 목록 밖으로 supabase CLI도 설치를 시도한다(업무 DB를 켜는 데 쓴다. 실패해도 `시작.bat`이 `npx`로 대신 받는다). **디스크**: C 드라이브 여유 40 GB 이상을 권한다. 실습 스택만 실측 약 17 GB(Docker 이미지 13.6 · 빌드 캐시 1.7 · 실습 데이터 1.1 · 컨테이너 0.3 · 저장소 0.5, 2026-10-20 Linux 실측)이고, 프로그램 설치분과 Docker Desktop 자체 여유는 Windows에서 재지 못해 여유를 더했다. PC 메모리가 8 GB보다 적으면 「부족할 수 있음」이 뜬다.

**`git clone` 뒤 `docker compose up`만 하면 안 되는 까닭.** compose의 서비스 26개는 모두 프로필에 묶여 있고, 켤 프로필은 `.env`가 정하는데 `.env`는 저장소에 없다. 업무 DB(Supabase)는 compose 밖에서 따로 켜야 하고, 에이전트용 MCP 두 개는 별도 프로필이다. `시작.bat`이 이 넷(`.env` 강의 배포본 값 · 업무 DB · 시스템 · MCP)을 순서대로 한다.

> **자리** — Windows에서 `설치.bat` 결과 표와 Docker Desktop 「Engine running」 화면.

## A. 필수 확인 (약 30분)

### ① 시작.bat 결과: 단계 6개, 상태 10개, 「완료」

`시작.bat`을 더블클릭하면 검은 창에서 아래 순서가 지나간다. 마지막 줄의 「완료」와 이 PC에 표시된 포털 주소를 확인한다. 아래 그림의 `http://127.0.0.1:8088`은 촬영 당시 예시이며 포트 충돌 시 주소가 달라질 수 있다.

![start_all.sh 실제 출력. 6/6 단계에서 포트 10개가 모두 ok, 시스템 컨테이너 18 · 업무 DB 9, 마지막 줄 「완료」](img/A1_start_all.png)

- 단계는 `1/6 Docker 확인` → `2/6 .env 준비` → `3/6 업무 DB(Supabase) 켜기` → `4/6 시스템 빌드 · 기동` → `5/6 에이전트용 MCP 서버 둘` → `6/6 상태 확인`이다.
- `6/6`에서 서비스 상태가 모두 정상이어야 한다. 그림에 나온 포트 번호는 촬영 당시 값이며 현재 PC에서는 자동 조정될 수 있다.
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

학교는 메인 PC 한 대에 설치하면 나머지 PC에 복제해 준다. 메인 PC에서 다운로드·빌드를 끝내 두면 여러 대의 동시 다운로드를 줄일 수 있다. 복제 범위에 Docker 데이터가 포함되는지는 현장에서 확인한다.
복제한 PC가 이미지를 다시 받지 않고 바로 켜지려면, 복제 전에 메인 PC에서 아래를 끝내 둔다.

1. 저장소를 공용 폴더 `C:\hyd-iot-edu`에 받고(0절 2번) `설치.bat`으로 Docker Desktop·VS Code·Node.js·Git 중 없는 것만 설치한다(XG5000은 따로). 기존 프로그램의 사용자별 설치는 그대로 유지하므로, 실제 사용할 학생 계정에서도 실행 가능한지 확인한다.
2. `시작.bat`을 한 번 끝까지 돌린다. 이미지 받기 · 빌드가 이때 끝나 메인 PC에 남는다.
3. 루트 `.env` 접속 설정을 저장하고 `점검.bat`을 실행해 실패 없음·중계 서버 「연결됨」을 확인한다. A절의 수동 확인이 추가로 필요하면 진행한 뒤 「결함 시뮬레이션」 → **전체 초기화**, 그리고 `끄기.bat`.
4. 그 상태로 학교에 복제를 맡긴다.

복제된 PC에서 `시작.bat`이 다시 이미지를 받기 시작하면(4/6 단계에서 `Pulling …` 줄이 길게 이어진다) 복제에 Docker 데이터가 빠진 것이다.
Docker Desktop은 이미지를 **Windows 사용자 계정마다** 저장한다(`%LOCALAPPDATA%\Docker`). 학생이 메인 PC와 다른 계정으로 로그인하면 이미지가 없을 수 있다. 이때는 한 대씩 차례로 `시작.bat`을 돌린다.

이 클라우드에서도 첫 기동 중 Supabase 이미지(public.ecr.aws)를 받다가 레지스트리 한도에 걸려 재시도한 줄이 실제로 나왔다(재시도로 통과). 여러 대가 동시에 받으면 이런 줄이 늘고 결국 멈출 수 있다.

![실제로 나온 레지스트리 한도 줄 — Data limit exceeded, Retrying after 4s](img/R1_registry_limit.png)

## E. 하나씩 직접 설치하기 (`설치.bat`이 안 될 때)

`설치.bat`이 실패한 도구만 손으로 설치하는 절차다. 아래 판은 도구가 없을 때의 설치 대상이며 기존 설치는 버전과 관계없이 유지한다(Arduino IDE 제외). 링크는 각 프로그램의 공식 내려받기 주소다(눌러서 받은 파일을 더블클릭해 설치). 이미 설치된 프로그램은 건너뛴다. 창 여는 법은 맨 앞 「명령을 치는 창은 세 가지다」.

이전 링크 확인 기록(2026-10-20): 당시 내려받은 WSL · VS Code · Node.js 파일은 학교 목록의 크기·해시와 비교했다. Python은 이후 없는 PC에만 3.13.4를 설치하도록 변경했으므로 당시 파일 검증 기록을 적용하지 않는다. Docker 4.87.0은 Docker 공식 릴리스 노트(2026-08-17)의 Windows 링크와 같은 빌드(236836)이고 Docker가 낸 체크섬과도 같다. 이번 문서 동기화에서는 설치 파일을 다시 내려받거나 설치하지 않았다.

### E-1. WSL 2 (2.7.12)

1. **[관리자 PowerShell]** 에 두 줄을 붙여 넣는다(Windows 기능 둘을 켠다). 줄마다 「작업을 완료했습니다」가 나오면 된다.

   ```
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   ```

2. PC를 다시 시작한다.
3. 받아서 설치한다: <https://github.com/microsoft/WSL/releases/download/2.7.12/wsl.2.7.12.0.x64.msi>
4. 확인 — **[PowerShell]**: WSL 버전 정보가 출력되는지 확인한다. 기존 다른 버전이 정상 설치되어 있으면 유지한다.

   ```
   wsl --version
   ```

### E-2. Docker Desktop (4.87.0)

1. 받아서 설치한다: <https://desktop.docker.com/win/main/amd64/236836/Docker%20Desktop%20Installer.exe>
2. WSL을 사용할 수 있는 PC는 WSL 2 경로로 설치한다. WSL 오류가 난 PC는 먼저 [오류 해결 가이드](../../../문서/시스템/참조/Windows_Docker_설치.md)에서 Hyper-V 지원 여부와 전체 사용자용 설치 조건을 확인한다. 설치·설정 화면은 해당 가이드의 실제 사진을 따른다.
3. **[관리자 PowerShell]** 에 한 줄을 붙여 넣는다(이 PC에 로그인하는 모든 계정이 Docker를 쓰게 한다). 아무 글 없이 끝나면 된다.

   ```
   Add-LocalGroupMember -Group docker-users -Member S-1-5-11
   ```

4. PC를 다시 시작하고 Docker Desktop을 연다. 약관 「Accept」, 로그인 창은 「Skip」. 왼쪽 아래가 「Engine running」이면 된다.

### E-3. Visual Studio Code (1.140.0, System Installer)

1. 받아서 설치한다: <https://vscode.download.prss.microsoft.com/dbazure/download/stable/07f806f999227108933c2e30515b26eecc1fda74/VSCodeSetup-x64-1.140.0.exe>
2. 기본값 그대로 「다음」. 「PATH에 추가」는 체크된 채로 둔다.

### E-4. Python (기존 설치 유지, 없을 때만 3.13.4)

1. **[PowerShell]**에서 `python --version`을 확인한다. 없으면 `py --version`도 확인한다. Python·Anaconda가 이미 설치되어 있으면 버전과 관계없이 이 설치를 건너뛴다.
2. 실제로 없을 때만 **[관리자 PowerShell]**에서 실행한다.

   ```powershell
   winget install -e --id Python.Python.3.13 --version 3.13.4 --scope machine --accept-package-agreements --accept-source-agreements
   ```

3. 설치가 끝나면 **새 PowerShell 창**에서 `py --version`으로 응답을 확인한다. 기존 Python 버전을 바꾸기 위해 이 명령을 실행하지 않는다.

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

## F. 검증 범위와 현장 확인

- 이 문서의 클라우드 실행 그림과 과거 시험은 당시 판본의 근거다. 후속 Windows 설정 사진은 [오류 해결 가이드](../../../문서/시스템/참조/Windows_Docker_설치.md)에 있으며 개인 PC의 Docker Linux 엔진 응답을 확인했다. 이 사실이 학교 PC의 WSL 복구·winget 설치·전체 시작·점검 성공을 의미하지는 않는다. 이번 문서 동기화는 명령 문법·로컬 링크·실제 스크립트의 설정 경로를 확인하며, 설치를 다시 실행하지 않는다.
- 학교 네트워크에서 LiteLLM 서버 · Docker Hub에 닿는지.
- 학교의 복제 방식으로 Docker 이미지가 함께 복제되는지(D절).
- E절의 직접 설치 순서. 링크는 winget 목록이 쓰는 공식 주소와 같음을 확인했지만, 설치 화면 문구는 Windows에서 따라가 보지 않았다.
- ③-2를 학생 PC의 수업 흐름(매뉴얼 적재 뒤)으로 돌린 것. 이 문서의 ③-2는 회귀 시험용 전체판 지식으로 돌렸다.
