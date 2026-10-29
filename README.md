# hyd-iot-edu

HYD 제조 AI 교육과정(경남대학교 피지컬AI 사관학교)의 실습 시스템이다. 유압 설비의 값이 올라와 저장되고, 이상이 감지되면 에이전트가 근거를 모아 조치를 추천하고, 사람이 승인하면 시스템이 실행한다. 이 시스템으로 온톨로지, 에이전트, 업무 흐름을 가르친다.

이 저장소는 학생이 받아서 자기 PC에서 실행하는 판이다. 아래 「실행 환경」 → 설치 → 「시스템 시작과 종료」 순서로 따라 한다.

## 프로젝트 구성

설비 데이터 수집·저장, 이상 감지, AI 판단 지원, 업무 처리를 하나의 로컬 환경에서 실행한다. Docker Compose로 서비스를 구성하고 포털에서 각 화면에 접근한다.

| 구성 | 역할 |
|---|---|
| EMQX / Redpanda | 설비 데이터와 사건 전달 |
| TimescaleDB / Supabase | 시계열 측정값과 업무 데이터 저장 |
| Neo4j | 설비·부품·업무 대상의 관계 저장 |
| FUXA / Grafana | 설비 화면과 데이터 시각화 |
| Nginx (`portal`) | 포털 제공과 서비스 요청 연결 |
| `plant-sim`, `detector`, `agent`, `process` | 설비 모사, 이상 감지, 판단 지원, 업무 처리 |
| `enterprise-mcp`, `dmn-mcp` | 업무 데이터 조회와 의사결정 규칙 도구 |

실행 대상은 `compose.yaml`과 활성 프로필·설정에 따라 달라진다. Docker 이미지는 실행에 필요한 파일 묶음이고, 컨테이너는 이미지를 기반으로 생성한 실행 환경이다. 데이터가 저장되는 볼륨은 프로그램 재설치와 별도로 보존해야 한다.

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

Git·WSL은 준비 시점의 공식 최신 안정판으로 설치·업데이트한다. 다른 네 프로그램은 기준 이상이면 유지하고, 없거나 낮으면 설치·업데이트 후 재확인한다. 표시한 버전은 프로젝트 준비 기준이며 제품 자체의 최소 시스템 요구 사항과는 다르다. 기준 이상 모든 판의 호환성을 보장하는 목록은 아니다.

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

## 프로젝트 받기

[저장소 main](https://github.com/uengine-oss/hyd-iot-edu/tree/main) · [ZIP 다운로드](https://github.com/uengine-oss/hyd-iot-edu/archive/refs/heads/main.zip)

GitHub의 **Code → Download ZIP**으로 받거나 위 ZIP 링크를 사용한다. 탐색기에서 **모두 압축 풀기**로 새 폴더에 풀고 기존 프로젝트에 덮어쓰지 않는다. `README.md`, `compose.yaml`, `scripts`, `시작.bat`이 함께 있는 폴더가 프로젝트 루트다. ZIP 안에서 실행하거나 시작 파일만 따로 옮기지 않는다.

VS Code의 **File → Open Folder**에서 이 프로젝트 폴더를 연다. 한국어 표시가 필요하면 [Microsoft 한국어 언어 팩](https://marketplace.visualstudio.com/items?itemName=MS-CEINTL.vscode-language-pack-ko)을 설치하고 [표시 언어](https://code.visualstudio.com/docs/configure/locales)를 변경할 수 있다. AI 코딩을 사용할 경우 [OpenAI Codex 확장](https://learn.chatgpt.com/docs/codex/ide)을 설치하고 본인 계정을 연결한다. 사용 가능한 모델·사용량은 계정과 제품에 따라 다르다.

### 자동 설치 파일

공식 설치 파일로 준비했으면 설치 BAT를 다시 실행할 필요가 없다. 기존 자동 설치 경로도 제공한다. 다만 현재 자동 설치 구현은 Git·WSL을 과거 최소 기준으로 유지할 수 있으므로, 두 프로그램의 **공식 최신판 확인은 별도로 수행**한다.

<details>
<summary>Windows: 설치.bat</summary>

1. [저장소 main](https://github.com/uengine-oss/hyd-iot-edu/tree/main)을 열고 **Code → Download ZIP**으로 프로젝트 전체를 받는다.
2. 탐색기에서 **모두 압축 풀기**를 선택한다. 압축을 푼 폴더 안에 `설치.bat`, `시작.bat`, `scripts` 폴더가 함께 있는지 확인한다. ZIP 안에서 바로 실행하거나 배치 파일만 따로 옮기지 않는다. 기존 프로젝트 폴더에 덮어쓰지 않는다.
3. **`설치.bat`을 더블클릭**하고 관리자 승인 창의 내용을 확인한 뒤 승인한다. 앞에서 소개한 Docker Desktop·VS Code·Node.js·Git·Python과 WSL 실행 기능을 준비한다. 개별 설치 옵션을 하나씩 설정하는 대신 배치가 설치를 진행한다.
4. 결과 표에서 설치·업데이트·유지 여부를 확인한다. 실패 항목은 비고를 확인하고, 재부팅 안내가 나오면 재부팅한다.

Windows에서는 설치·업데이트가 필요한 항목에 `winget`을 사용한다. 실행 경로에서 찾지 못하면 Windows에 등록된 앱 설치 관리자(App Installer)의 위치를 자동 확인한다. 사용자 이름·드라이브·패키지 버전 경로를 직접 입력할 필요는 없다. 이미 기준을 만족하는 항목은 `winget` 없이도 유지 여부를 확인한다.

이 선택 경로에서는 기준을 만족하는 도구는 빠르게 건너뛰고, 처음 설치하는 PC는 다운로드 때문에 더 오래 걸린다. 배치는 학교 공용 PC용 Docker 사용 권한과 프로젝트 폴더 접근 권한도 준비한다.

**Windows 준비도 설치 파일에 포함:** Python·WSL과 필요한 Windows 기능까지 설치·확인한다. WSL 설치에는 별도 Ubuntu 배포판이 필요하지 않다. 재부팅 요청이 나오면 재부팅 후 `설치.bat`을 다시 실행해 결과를 확인한다. BIOS 가상화, 관리자 승인, Docker 약관 동의는 화면 안내에 따라 처리한다. `winget`이 없으면 Microsoft Store의 앱 설치 관리자(App Installer)를 먼저 준비한다.

</details>

<details>
<summary>macOS: 설치.command</summary>

1. 같은 저장소에서 **Code → Download ZIP**으로 받고 Finder에서 ZIP을 열어 압축을 푼다. `설치.command`, `시작.command`, `scripts` 폴더를 함께 둔다. 기존 프로젝트에 덮어쓰지 않는다.
2. **`설치.command`를 더블클릭**한다. [Homebrew](https://brew.sh/)가 없으면 공식 설치 스크립트로 먼저 준비한다. 터미널의 설치 내용·Enter·관리자 암호 요청을 확인한다. 암호 입력 중 글자가 보이지 않는 것은 정상이다. 전체 파일을 `sudo`로 실행하지 않는다.
3. Docker Desktop·VS Code·Node.js·Git·Python의 `[유지]`·`[완료]`·`[실패]` 결과를 확인한다. 기준 미달인 항목만 [Homebrew 설치·업데이트](https://docs.brew.sh/Manpage)를 수행한다. 의존 패키지도 함께 설치될 수 있다. Docker·VS Code는 업데이트 전에 작업을 저장하고 종료한다. `/Applications`와 `~/Applications`의 앱을 확인하며 두 곳에 중복된 앱은 자동 교체하지 않는다.
4. **Python도 설치 파일이 준비한다.** 3.13 이상이 있으면 유지하며 기존 Python·Anaconda는 삭제하지 않는다. Mac에는 WSL·Git Bash가 필요 없다.
5. Docker Desktop을 열어 초기 설정과 약관 동의를 완료하고 **Engine running**을 확인한다. 현재 macOS가 [Docker Desktop 지원 조건](https://docs.docker.com/desktop/setup/install/mac-install/)과 Homebrew 지원 조건을 만족해야 한다.

ZIP 다운로드 후 실행 권한 오류가 나면 터미널에서 `cd ` 뒤에 압축을 푼 폴더를 끌어다 놓고 Enter를 누른 다음 아래를 한 번 실행한다. 이후 더블클릭할 수 있다.

```bash
chmod +x 설치.command 시작.command
./설치.command
```

보안 경고가 나오면 출처와 파일을 확인한 뒤 **시스템 설정 → 개인정보 보호 및 보안**에서 해당 파일의 실행 허용을 확인한다. 보안 기능 전체를 끄지 않는다. 더블클릭 대신 프로젝트 폴더에서 `bash 설치.command`, `bash 시작.command`로 실행할 수도 있다.

**Mac 검증 범위:** 설치 정책과 쉘 구문은 자동 검사 대상이다. 실제 Intel·Apple Silicon Mac에서 설치, Docker 이미지 실행, 포털 접속까지의 검증은 아직 완료하지 않았다.

</details>

## 시스템 시작과 종료

Docker Desktop에서 **Engine running**을 확인하고 프로젝트 루트의 **Windows `시작.bat` / macOS `시작.command`**를 실행한다. 실행 창은 유지한다. 두 시작 파일은 `scripts/start_all.sh`를 실행한다. 보안 차단이 발생하면 실행을 중단하고 원인을 확인한다. 보안 기능 해제나 차단된 파일의 우회 실행을 전제로 하지 않는다.

| 단계 | 처리 내용 |
|---|---|
| 1. Docker 확인 | 엔진 응답과 Compose 확인 |
| 2. 설정·포트 준비 | 실행 설정 준비, 프로젝트의 `scripts/prepare_ports.py`로 포트 충돌 처리 |
| 3. 업무 DB | `it/supabase`에서 `npx -y supabase@2.119.0 start` 실행 |
| 4. 시스템 기동 | `docker compose up -d --build` |
| 5. MCP | `enterprise-mcp`, `dmn-mcp` 기동 |
| 6. 상태 확인 | 서비스 응답과 포털 응답 확인, 접속 주소 출력 |

초기 실행에는 이미지 다운로드와 빌드 시간이 필요하다. `Pulling`·`Downloading`은 다운로드, `Extracting`은 압축 해제, `CACHED`는 이전 빌드 결과 재사용을 뜻한다. 이미 준비된 이미지가 있으면 다음 실행은 빨라질 수 있다. 오류로 중단된 단계는 정상 대기로 간주하지 않는다.

완료 메시지에 출력된 **포털 주소**로 접속한다. 다른 프로그램과 포트가 겹치면 주소가 달라질 수 있으므로 이번 출력값을 사용한다. 포털 접속과 후속 AI 기능의 접속 설정·검증은 구분한다.

프로젝트 루트에서 `docker compose ps`로 서비스 상태를, `docker compose logs portal`로 포털 로그를 확인할 수 있다. 종료는 Windows `끄기.bat`, macOS `bash scripts/stop_all.sh`를 사용한다. 이미지·볼륨 삭제는 일반 종료 절차가 아니다.

## 루트 실행 파일

프로젝트 루트의 실행 파일은 더블클릭으로 쓴다. Windows는 `.bat`, macOS는 `.command`이며, macOS에 파일이 없는 단계는 표의 명령을 프로젝트 폴더에서 실행한다.

| 언제 | Windows | macOS | 하는 일 |
|---|---|---|---|
| 처음 한 번, 프로그램 기준이 바뀌었을 때 | `설치.bat`(관리자 승인) | `설치.command` | 위 「실행 환경」 표의 프로그램이 없거나 기준보다 낮으면 설치 · 업데이트하고 결과 표를 보여 준다. 재부팅 안내가 나오면 재부팅 뒤 다시 실행해 결과를 확인한다 |
| 수업을 시작할 때 | `시작.bat` | `시작.command` | 스택을 켜고 이 PC의 포털 주소를 보여 준다(위 「시스템 시작과 종료」) |
| 시작이 「완료」된 뒤 | `점검.bat` | — | 서비스 응답 · 쿨러 사건 한 바퀴 · 5회차 실습 중계 서버 연결을 확인한다. 실패 항목이 없고 중계 서버가 **「연결됨」**인지 본다 |
| 수업을 마칠 때 | `끄기.bat` | `bash scripts/stop_all.sh` | 스택을 끈다. 데이터는 지우지 않는다 |

**점검 전 접속 설정:** 수업에서 받은 `OPENAI_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` 세 값을 **저장소 루트 `.env`**에 저장한다. 루트 `.env`가 없으면 `.env.example`을 복사해 만든다. `OPENAI_API_KEY`는 비워도 된다. `점검.bat`은 루트 설정을 자동으로 쓰고, 명시적인 `-LlmEnvFile` 지정이 우선한다. 값이 있으면 점검 때 다시 묻지 않는다. 중계 서버 「건너뜀」은 연결 확인 완료가 아니다. 실제 키를 넣은 파일은 커밋 · 푸시하지 않는다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `ot/` `dmz/` `it/` | 시스템의 코드. 망의 영역대로 나뉜다(현장, 완충 구역, 사무) |
| `common/` | 여러 서비스가 함께 쓰는 코드(공용 토픽 · 스키마 등). 서비스 이미지를 만들 때 함께 들어간다 |
| `scripts/` | 루트의 설치 · 시작 · 끄기 · 점검 파일이 부르는 실행 스크립트 |
| `문서/시스템/참조/수업_문서_원문/` | 시작할 때 포털 지식에 넣는 수업 문서 원문 |

## 지키는 것

- 공개 저장소다. `.env`에 넣은 키는 출력 · 로그 · 커밋하지 않는다.
- 학생은 clone · pull만 한다. 받은 파일을 고쳐 올리지 않는다.
