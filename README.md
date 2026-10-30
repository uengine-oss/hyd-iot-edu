# hyd-iot-edu

HYD 제조 AI 교육과정(경남대학교 피지컬AI 사관학교)의 실습 시스템이다. 유압 설비의 값이 올라와 저장되고, 이상이 감지되면 에이전트가 근거를 모아 조치를 추천하고, 사람이 승인하면 시스템이 실행한다. 이 시스템으로 온톨로지, 에이전트, 업무 흐름을 가르친다.

이 저장소는 학생이 받아서 자기 PC에서 실행하는 판이다. 아래 「실행 환경」 → 설치 → 「시스템 시작과 종료」 순서로 따라 한다.

## 프로젝트 구성

설비 데이터 수집·저장, 이상 감지, AI 판단 지원, 업무 처리를 하나의 로컬 환경에서 실행한다. Docker Compose로 서비스를 구성하고 포털에서 각 화면에 접근한다.

| 구성 | 역할 |
|---|---|
| EMQX / Redpanda | 설비 데이터와 사건 전달 |
| `connect-ingest` · `cmd-gateway` · `connect-sink` | 설비망 → 사무망 복제, 승인된 설비 명령만 내려보내는 통로, 시계열 적재 |
| TimescaleDB / Supabase | 시계열 측정값과 업무 데이터 저장(Supabase는 업무 DB — 시작 파일이 따로 켠다) |
| Neo4j | 설비·부품·업무 대상의 관계 저장 |
| FUXA / Grafana | 설비 화면과 데이터 시각화 |
| Nginx (`portal`) | 포털 제공과 서비스 요청 연결 |
| `plant-sim`, `detector`, `agent`, `process` | 설비 모사, 이상 감지, 판단 지원, 업무 처리 |
| `enterprise-sim` · `effects-mcp` | 업무 시스템(ERP · MES · CMMS 등) 모사, 승인 뒤 메일 · 일정 같은 쓰기 |
| `agent-worker` | AI 단계(판단 · 제안, 에이전트에게 질문)를 실행하는 AI 워커 |
| `enterprise-mcp`(+ `-maint` · `-purchase`), `dmn-mcp` | 에이전트가 쓰는 업무 데이터 조회와 의사결정 규칙 도구(4개) |

실행 대상은 `compose.yaml` 하나가 정한다(선택 도구 Prometheus · Redpanda Console만 따로 켠다). Docker 이미지는 실행에 필요한 파일 묶음이고, 컨테이너는 이미지를 기반으로 생성한 실행 환경이다. 데이터가 저장되는 볼륨은 프로그램 재설치와 별도로 보존해야 한다.

## 실행 환경

Windows에서는 Git Bash와 Docker Desktop의 WSL 2 기반 Linux 컨테이너를 사용한다. macOS에는 WSL과 Git Bash가 필요하지 않다. Docker의 운영체제·가상화 요구 조건은 공식 설치 문서를 따른다.

| 프로그램 | 프로젝트 준비 기준 | 공식 다운로드·문서 | 설치 확인 |
|---|---|---|---|
| VS Code | 1.132.0(2026년 8월 판) 이상. 프로젝트 편집용 | [Windows](https://code.visualstudio.com/download) · [macOS Universal ZIP](https://update.code.visualstudio.com/latest/darwin-universal/stable) · [Mac 설치](https://code.visualstudio.com/docs/setup/mac) | 정보(About) 또는 `code --version` |
| Git | 공식 최신 안정판 | [Windows](https://git-scm.com/install/windows) · [macOS](https://git-scm.com/install/mac) | `git --version` |
| Node.js | 24.22.1 이상. 24.x LTS 권장 | [Windows x64 MSI](https://nodejs.org/dist/v24.22.1/node-v24.22.1-x64.msi) · [macOS PKG](https://nodejs.org/dist/v24.22.1/node-v24.22.1.pkg) · [다른 CPU·버전](https://nodejs.org/en/download) | `node --version`, `npm --version` |
| Python | 3.13 이상(없으면 3.14.7 설치) | [Windows x64 EXE](https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe) · [macOS Universal2 PKG](https://www.python.org/ftp/python/3.14.7/python-3.14.7-macos11.pkg) · [릴리스 정보](https://www.python.org/downloads/release/python-3147/) | `python --version` / macOS `python3 --version` |
| WSL | 공식 최신 안정판, WSL 2 실행 환경(Windows) | [설치](https://learn.microsoft.com/ko-kr/windows/wsl/install) · [명령](https://learn.microsoft.com/ko-kr/windows/wsl/basic-commands) | `wsl --version`, `wsl --status` |
| Docker Desktop | 4.87.0 이상 | [Windows](https://docs.docker.com/desktop/setup/install/windows-install/) · [macOS](https://docs.docker.com/desktop/setup/install/mac-install/) | 앱 About, `docker info`, `docker compose version` |

Git·WSL은 준비 시점의 공식 최신 안정판으로 설치·업데이트한다. 다른 네 프로그램은 기준 이상이면 유지하고, 없거나 낮으면 설치·업데이트 후 재확인한다. 표시한 버전은 프로젝트 준비 기준이며 제품 자체의 최소 시스템 요구 사항과는 다르다. 기준 이상 모든 판의 호환성을 보장하는 목록은 아니다. 설치 파일(`설치.bat` · `설치.command`)과 시작 파일이 쓰는 기준 판은 `scripts/versions.txt` 한 곳에 있다.

**XG5000 4.73**은 winget에 없어 `설치.bat`이 건드리지 않으므로 직접 설치한다: [한국어판 약 394 MB](https://sftpssqblobcdn.blob.core.windows.net/prod/largefile/document/16849776042931/XG5000_V4.73_20230522_Kr.exe) · [영어판](https://sftpssqblobcdn.blob.core.windows.net/prod/largefile/document/16849776042930/XG5000_V4.73_20230522_En.exe). LS ELECTRIC 자료 페이지(<https://ssq.ls-electric.com/kr/ko/product/document/2201>)의 판 목록에서 4.73을 고른 파일이다.

### 공식 설치 파일로 준비

표의 Node.js 설치 파일은 **24.22.1**, Python 설치 파일은 **3.14.7**이다. Windows 링크는 x64용이며 ARM64 PC는 공식 배포 페이지에서 CPU에 맞는 파일을 선택한다. macOS는 Node.js PKG와 Python Universal2 PKG를 사용하며, VS Code Universal ZIP은 압축을 풀어 앱을 응용 프로그램 폴더로 옮긴다. VS Code 링크는 최신 안정판으로 연결되므로 기준 버전을 확인한다. 각 제품의 macOS 지원 조건은 공식 문서를 따른다.

위 공식 링크에서 운영체제와 CPU에 맞는 안정판 설치 파일을 받는다. Windows에서 확인할 항목은 다음과 같다.

- **VS Code:** 개인 계정은 User Installer 사용 가능. PATH 추가를 유지한다.
- **Git:** 명령 프롬프트와 다른 프로그램에서 사용할 수 있는 권장 PATH 옵션을 유지한다. Git Bash도 함께 설치한다.
- **Node.js:** npm과 PATH가 포함된 기본 구성으로 설치한다.
- **Python:** 3.14.x 전통 설치기를 사용한다면 `Add python.exe to PATH`를 확인한다. [공식 설치 설명](https://docs.python.org/3.14/using/windows.html#the-full-installer-deprecated). Python Install Manager는 설치 방식과 화면이 다르다.
- **WSL:** 아래 WSL 준비 절차에 따라 `wsl --version`으로 먼저 확인한다. 별도 Ubuntu는 설치하지 않는다.
- **Docker Desktop:** WSL 2 옵션이 이미 선택돼 있으면 유지한다. 옵션 화면이 없으면 설치 후 설정에서 확인한다. Linux 컨테이너 엔진이 준비돼야 한다.

설치 후 새 터미널에서 위 확인 명령을 실행한다. 명령을 찾지 못하면 설치 위치와 PATH를 확인한다. `docker --version`의 CLI 버전과 Docker Desktop 앱의 버전은 다르며, 앱 설치 완료와 엔진 실행 상태도 별도로 확인한다.

### WSL 준비 — Ubuntu 없이 Docker 실행 기반 설치

이 프로젝트는 Windows의 Git Bash에서 실행 명령을 사용한다. WSL 2는 Docker Desktop의 Linux 컨테이너 실행 기반으로 필요하지만, 사용자가 작업할 별도의 Ubuntu 배포판은 필요하지 않다. Docker Desktop은 자체 `docker-desktop` 환경을 관리한다. [Docker 공식 설명](https://docs.docker.com/desktop/features/wsl/#enable-docker-in-a-wsl-2-distribution)

PowerShell에서 먼저 확인한다.

```powershell
wsl --version
```

버전이 출력되면 WSL이 설치된 상태다. 일부 Windows 환경에서는 WSL 미설치 시 이 명령을 호출했을 때 설치 안내가 나타나고, 안내에 따라 Ubuntu 없이 WSL을 설치할 수 있다. `--version` 자체의 명령 기능은 버전 조회이므로 모든 Windows에서 자동 설치된다고 가정하지 않는다. 설치 안내 없이 미설치 오류가 나오면 관리자 PowerShell에서 다음 명령으로 WSL만 설치한다.

```powershell
wsl --install --no-distribution
```

기존 WSL의 업데이트가 필요한 경우에는 다음을 실행한다.

```powershell
wsl --update
```

요청된 재부팅을 마친 뒤 버전을 다시 확인한다. **`wsl --install`만 실행하면 기본 Ubuntu까지 설치되므로 이 프로젝트의 준비 명령으로 사용하지 않는다.** Ubuntu 계정·암호 설정도 필요하지 않다. [Microsoft 명령 안내](https://learn.microsoft.com/ko-kr/windows/wsl/basic-commands)

## 프로젝트 받기와 새 판 받기

실습 폴더는 **Git으로 한 번 받고, 새 판도 같은 폴더에서 받는다.** 실습 기록(처리 건 · 적재한 지식 · 업무 데이터)은 폴더 하나에 묶여 있어서, 새 판을 다른 폴더에 받으면 빈 시스템이 하나 더 생긴다(시작 파일이 「다른 폴더의 시스템이 있습니다」라고 알려 준다).

- **처음 받기**: 위 「실행 환경」의 Git을 설치한 뒤, 터미널에서 실습 폴더를 둘 곳(공용 PC는 `C:\`, 개인 PC는 문서 폴더 등)으로 이동해 `git clone https://github.com/uengine-oss/hyd-iot-edu.git` 을 실행한다. 만들어진 `hyd-iot-edu` 폴더(공용 PC면 `C:\hyd-iot-edu` — `README.md`, `compose.yaml`, `scripts`, `setup`이 함께 있는 폴더)가 프로젝트 루트다.
- **새 판 받기**: 시작 파일이나 점검 파일이 「새 판을 받으세요」라고 하면, 수업 시스템을 끈 뒤(`끄기.bat` · Mac `bash scripts/stop_all.sh`) 프로젝트 루트에서 `git pull` 을 실행하고 시작 파일을 다시 실행한다.
- Git이 아직 없어 자동 설치 파일로 프로그램부터 준비하려면, [ZIP 다운로드](https://github.com/uengine-oss/hyd-iot-edu/archive/refs/heads/main.zip)로 받은 폴더에서 아래 「자동 설치 파일」만 실행하고, 설치가 끝나면 위처럼 `git clone`으로 실습 폴더를 받는다(ZIP 폴더는 설치용이라 지워도 된다).

VS Code의 **File → Open Folder**에서 이 프로젝트 폴더를 연다. 한국어 표시가 필요하면 [Microsoft 한국어 언어 팩](https://marketplace.visualstudio.com/items?itemName=MS-CEINTL.vscode-language-pack-ko)을 설치하고 [표시 언어](https://code.visualstudio.com/docs/configure/locales)를 변경할 수 있다. AI 코딩을 사용할 경우 [OpenAI Codex 확장](https://learn.chatgpt.com/docs/codex/ide)을 설치하고 본인 계정을 연결한다. 사용 가능한 모델·사용량은 계정과 제품에 따라 다르다.

### 자동 설치 파일

공식 설치 파일로 준비했으면 설치 BAT를 다시 실행할 필요가 없다. 기존 자동 설치 경로도 제공한다. 다만 현재 자동 설치 구현은 Git·WSL을 과거 최소 기준으로 유지할 수 있으므로, 두 프로그램의 **공식 최신판 확인은 별도로 수행**한다.

<details>
<summary>Windows: 설치.bat</summary>

1. 실습 폴더(또는 Git이 없을 때 위 ZIP을 **모두 압축 풀기**로 푼 폴더)에 `setup` 폴더(설치 · 시작 · 끄기 · 점검)와 `scripts` 폴더가 함께 있는지 확인한다. ZIP 안에서 바로 실행하거나 배치 파일만 따로 옮기지 않는다.
2. **`setup` 폴더의 `설치.bat`을 더블클릭**하고 관리자 승인 창의 내용을 확인한 뒤 승인한다(「아니요」를 누르면 아무것도 설치하지 않고 다시 실행하라고 알린다). 앞에서 소개한 Docker Desktop·VS Code·Node.js·Git·Python과 WSL 실행 기능을 준비한다. 개별 설치 옵션을 하나씩 설정하는 대신 배치가 설치를 진행한다.
3. 결과 표에서 설치·업데이트·유지 여부를 확인한다. 실패 항목은 비고를 확인하고, 재부팅 안내가 나오면 재부팅한다.

Windows에서는 설치·업데이트가 필요한 항목에 `winget`을 사용한다. 실행 경로에서 찾지 못하면 Windows에 등록된 앱 설치 관리자(App Installer)의 위치를 자동 확인한다. 사용자 이름·드라이브·패키지 버전 경로를 직접 입력할 필요는 없다. 이미 기준을 만족하는 항목은 `winget` 없이도 유지 여부를 확인한다.

이 선택 경로에서는 기준을 만족하는 도구는 빠르게 건너뛰고, 처음 설치하는 PC는 다운로드 때문에 더 오래 걸린다. 배치는 학교 공용 PC용 Docker 사용 권한을 준비하고, 실습 폴더가 사용자 폴더(`C:\Users\…`) 밖(예: `C:\hyd-iot-edu`)에 있으면 로그인한 모든 계정이 그 폴더를 쓰게 한다. 사용자 폴더 안이면 개인 PC로 보고 그대로 둔다(결과 표에 「개인 폴더」 — 실패가 아니다).

**Windows 준비도 설치 파일에 포함:** Python·WSL과 필요한 Windows 기능까지 설치·확인한다. WSL 설치에는 별도 Ubuntu 배포판이 필요하지 않다. 재부팅 요청이 나오면 재부팅 후 `설치.bat`을 다시 실행해 결과를 확인한다. BIOS 가상화, 관리자 승인, Docker 약관 동의는 화면 안내에 따라 처리한다. `winget`이 없으면 Microsoft Store의 앱 설치 관리자(App Installer)를 먼저 준비한다.

</details>

<details>
<summary>macOS: 설치.command</summary>

1. 실습 폴더(또는 Git이 없을 때 위 ZIP을 Finder에서 푼 폴더)에 `setup` 폴더(`설치.command` · `시작.command` · `점검.command`)와 `scripts` 폴더가 함께 있는지 확인한다.
2. **`setup` 폴더의 `설치.command`를 더블클릭**한다. [Homebrew](https://brew.sh/)가 없으면 공식 설치 스크립트로 먼저 준비한다. 터미널의 설치 내용·Enter·관리자 암호 요청을 확인한다. 암호 입력 중 글자가 보이지 않는 것은 정상이다. 전체 파일을 `sudo`로 실행하지 않는다.
3. Docker Desktop·VS Code·Node.js·Git·Python의 `[유지]`·`[완료]`·`[실패]` 결과를 확인한다. 기준 미달인 항목만 [Homebrew 설치·업데이트](https://docs.brew.sh/Manpage)를 수행한다. 의존 패키지도 함께 설치될 수 있다. Docker·VS Code는 업데이트 전에 작업을 저장하고 종료한다. `/Applications`와 `~/Applications`의 앱을 확인하며 두 곳에 중복된 앱은 자동 교체하지 않는다.
4. **Python도 설치 파일이 준비한다.** 3.13 이상이 있으면 유지하며(Windows와 같은 기준) 기존 Python·Anaconda는 삭제하지 않는다. Mac에는 WSL·Git Bash가 필요 없다.
5. Docker Desktop을 열어 초기 설정과 약관 동의를 완료하고 **Engine running**을 확인한다. 현재 macOS가 [Docker Desktop 지원 조건](https://docs.docker.com/desktop/setup/install/mac-install/)과 Homebrew 지원 조건을 만족해야 한다.

ZIP 다운로드 후 실행 권한 오류가 나면 터미널에서 `cd ` 뒤에 압축을 푼 폴더를 끌어다 놓고 Enter를 누른 다음 아래를 한 번 실행한다. 이후 더블클릭할 수 있다.

```bash
chmod +x setup/설치.command setup/시작.command setup/점검.command
./setup/설치.command
```

보안 경고가 나오면 출처와 파일을 확인한 뒤 **시스템 설정 → 개인정보 보호 및 보안**에서 해당 파일의 실행 허용을 확인한다. 보안 기능 전체를 끄지 않는다. 더블클릭 대신 프로젝트 폴더에서 `bash setup/설치.command`, `bash setup/시작.command`, `bash setup/점검.command`로 실행할 수도 있다.

**Mac 검증 범위:** 설치 정책과 쉘 구문은 자동 검사 대상이다. 실제 Intel·Apple Silicon Mac에서 설치, Docker 이미지 실행, 포털 접속까지의 검증은 아직 완료하지 않았다.

</details>

## 시스템 시작과 종료

Docker Desktop에서 **Engine running**을 확인하고 `setup` 폴더의 **Windows `시작.bat` / macOS `시작.command`**를 실행한다. 실행 창은 유지한다. 두 시작 파일은 `scripts/start_all.sh`를 실행한다. 보안 차단이 발생하면 실행을 중단하고 원인을 확인한다. 보안 기능 해제나 차단된 파일의 우회 실행을 전제로 하지 않는다.

| 단계 | 처리 내용 |
|---|---|
| 1. Docker 확인 | 엔진 응답과 Compose 확인(꺼져 있으면 켜고 기다린다) |
| 2. `.env` · 이 PC 값 준비 | 키가 있으면 AI 단계를 실제 AI, 없으면 강사가 저장한 응답 재생으로 정하고, 이 폴더의 프로젝트 이름 · 포트를 정한다(다른 프로그램과 겹치면 옮긴다). 이 PC 값은 git이 추적하지 않는 파일(`.env` · `.hyd-runtime/` · `it/supabase/.env`)에만 쓴다 |
| 3. 업무 DB | `it/supabase`에서 Supabase 켜기 + 새 판의 업무 DB 구조 적용 |
| 4. 시스템 기동 | `docker compose up -d --build`(AI 워커 · 에이전트용 도구 서버 포함) |
| 5. 서비스 확인 | 모든 서비스가 떴는지(멈춘 것 · 계속 다시 시작하는 것은 실패), 포털 응답 |
| 6. 수업 흐름 | 업무 흐름 A(냉각) · B(정기 정비) · C(예비품 구매) 배포(있으면 건너뜀) |
| 7. 기본 지식 | 수업 문서 셋(HM-8 · PM-02 · PR-07)의 검토한 지식 넣기(있으면 건너뜀, AI 없음) |
| 8. AI 단계 확인 | 키 없음: 저장된 응답이 있는지 · 키 있음: 강의 중계에 닿고 수업 모델을 쓸 수 있는지 |

초기 실행에는 이미지 다운로드와 빌드 시간이 필요하다. `Pulling`·`Downloading`은 다운로드, `Extracting`은 압축 해제, `CACHED`는 이전 빌드 결과 재사용을 뜻한다. 이미 준비된 이미지가 있으면 다음 실행은 빨라질 수 있다. 오류로 중단된 단계는 정상 대기로 간주하지 않는다.

완료 메시지에 출력된 **포털 주소**로 접속한다. 다른 프로그램과 포트가 겹치면 주소가 달라질 수 있으므로 이번 출력값을 사용한다. 8단계(AI 단계 확인)만 실패하면 포털 주소와 까닭을 함께 보여 준다 — 포털은 쓸 수 있고, AI 단계만 그 까닭을 고친 뒤 시작 파일을 다시 실행하면 된다.

프로젝트 루트에서 `docker compose ps`로 서비스 상태를, `docker compose logs portal`로 포털 로그를 확인할 수 있다. 종료는 Windows `끄기.bat`, macOS `bash scripts/stop_all.sh`를 사용한다. 이미지·볼륨 삭제는 일반 종료 절차가 아니다. 폴더를 옮겨도 시작 파일이 알아보고 실습 기록을 이어 쓴다.

## 실행 파일(setup 폴더)

`setup` 폴더의 실행 파일은 더블클릭으로 쓴다. Windows는 `.bat`, macOS는 `.command`이며, macOS에 파일이 없는 단계는 표의 명령을 프로젝트 폴더에서 실행한다.

| 언제 | Windows | macOS | 하는 일 |
|---|---|---|---|
| 처음 한 번, 프로그램 기준이 바뀌었을 때 | `설치.bat`(관리자 승인) | `설치.command` | 위 「실행 환경」 표의 프로그램이 없거나 기준보다 낮으면 설치 · 업데이트하고 결과 표를 보여 준다. 재부팅 안내가 나오면 재부팅 뒤 다시 실행해 결과를 확인한다 |
| 수업을 시작할 때 | `시작.bat` | `시작.command` | 스택을 켜고 이 PC의 포털 주소를 보여 준다(위 「시스템 시작과 종료」) |
| 시작이 「완료」된 뒤 | `점검.bat` | `점검.command` | 서비스 응답 · 쿨러 사건 한 바퀴(경보 → AI 판단 → 승인 → 냉각 명령 → 재관측 → 작업지시) · 강의 중계 연결을 확인한다. 「실패」가 없으면 된다. 키 없는 PC의 강의 중계 줄은 **「해당 없음」**이 정상이다 |
| 수업을 마칠 때 | `끄기.bat` | `bash scripts/stop_all.sh` | 스택을 끈다. 데이터는 지우지 않는다 |

**강의 중계 키(오프라인 수업):** 수업에서 키를 받았으면 **프로젝트 루트 `.env`의 `LLM_API_KEY=` 뒤에 키 한 줄만** 넣고 시작 파일을 실행한다(`.env`가 없으면 시작 파일이 `.env.example`을 복사해 만든다. 나머지 값은 시작 파일이 채운다). 키를 받지 않은 온라인 수업은 비워 둔다 — AI 단계는 강사가 저장한 응답을 재생한다. 키를 넣은 `.env`는 커밋 · 푸시하지 않는다(git이 무시한다).

## 폴더

| 폴더 | 내용 |
|---|---|
| `ot/` `dmz/` `it/` | 시스템의 코드. 망의 영역대로 나뉜다(현장, 완충 구역, 사무) |
| `common/` | 여러 서비스가 함께 쓰는 코드(공용 토픽 · 스키마 등). 서비스 이미지를 만들 때 함께 들어간다 |
| `setup/` | 더블클릭하는 설치 · 시작 · 끄기 · 점검 파일(Windows `.bat` · macOS `.command`) |
| `scripts/` | `setup/` 파일이 부르는 실행 스크립트 |
| `it/portal/www/samples/` | 수업 문서 원문(매뉴얼 · 점검표 · 구매 기준) — 포털 실습에서 올리는 파일. 시작할 때는 이 원문으로 검토해 둔 지식(`it/neo4j/class-knowledge/`)을 넣는다 |

## 지키는 것

- 공개 저장소다. `.env`에 넣은 키는 출력 · 로그 · 커밋하지 않는다.
- 학생은 clone · pull만 한다. 받은 파일을 고쳐 올리지 않는다.
