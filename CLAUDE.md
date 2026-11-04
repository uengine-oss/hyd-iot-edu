# hyd-iot-edu — 프로젝트 계약 (이 파일은 이 PC의 저장소 루트에 두고, workspace 브랜치에 백업하며, main에는 없다)

## 0. 무엇이든 시키면

스킬 `hyd-task`의 길을 밟는다. 그 길은 작업 폴더 → 그 일 문서(`공통.md` + 일 문서 하나) 끝까지 읽기 → 그 회차 맥락만 뽑기 → 만들기 → 자동 검사 → 독립 검토 1회 → 목록만 고침 → 제자리 · 동기화 · 정리 순서다. 열린 작업 폴더(`작업/<날짜>_<제목>/`)가 있으면 그 폴더의 `스펙.md`와 `기록.md`부터 읽고 이어서 한다. 대화 요약 뒤에는 그 일 문서를 다시 읽는다. Claude에서는 `.claude/hooks/guide_gate.py`가 읽기 전의 편집을 막고, Codex에서는 `.codex/hooks.json`이 다시 읽으라고 안내한다.

- 유료 실행은 목적, 성공 기준, 상한을 먼저 정한다. 실패한 실행을 같은 조건으로 다시 돌리지 않는다.
- 지울 것은 「이건 이런 건데 필요합니까」로 묻는다. 사용자가 "알아서 해"로 맡겼으면, 분명히 필요 없는 것(지금 수업이나 개발에 쓰이지 않거나 최신 판이 따로 있는 것)은 지우고 애매한 것만 묻는다. 지운 것은 git 이력에 남는다.
- 같은 사실은 한 곳에만 쓰고, 나머지 자리는 그곳을 가리킨다.

## 1. 구조 — 어디에 무엇이 있나

| 자리 | 무엇 | 브랜치 |
|---|---|---|
| `README.md` · `compose*.yaml` · `.env.example` · `setup/`(설치 · 시작 · 끄기 · 점검) · `scripts/`(`setup/`의 파일이 부르는 것만) · `it/` `ot/` `dmz/` `common/` | 학생이 clone해 실행하는 것: 코드, 프롬프트, 설정, 수업 데이터(수업 문서 원문은 `it/portal/www/samples/`). 사람이 읽는 문서는 루트 README 하나뿐이다 | main |
| `workspace/README.md` | 하려는 일 → 읽을 문서의 색인. 이런 진입 표는 이곳 한 곳에만 둔다 | workspace |
| `workspace/강의제작/지침/` | `공통.md`, 일 문서 여섯(실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드), 사실표, 설계서 | workspace |
| `workspace/강의제작/산출물/` | 완성본의 최신 판만 둔다(과정별 이론 · 이론_오프라인 · 실습, 영상, 실라버스 엑셀) | workspace |
| `workspace/강의제작/제작도구/` | 다시 만들 재료(원고, 구성, 큐, 촬영도구, 음성 캐시, 촬영준비, 검사기) | workspace |
| `workspace/개발/` | 시스템 개발용 문서, 테스트, 생성기, 확인 도구. 목록은 `workspace/README.md`의 「폴더」 표에 있다 | workspace |
| `workspace/동기화.py` · `secret_scan.py` · `requirements-dev.txt` | 두 브랜치 동기화와 작업 폴더 시작 · 정리(`동기화.py`), 키 검사(`secret_scan.py`), 개발 의존성(`requirements-dev.txt`) | workspace |
| `.claude/` · `CLAUDE.md` · `AGENTS.md` | Claude와 Codex가 저장소 루트에서 읽는 규칙, 스킬, 훅 | workspace |
| `작업/<YYYY-MM-DD>_<제목>/` | 진행 중인 작업 하나의 폴더(`스펙.md`, `기록.md`, 원본, 임시 출력). 녹화 원본은 `작업/촬영/<도구>/`에, 공개하면 안 되는 개인 자료는 `작업/_로컬/`에 둔다. 저장소 밖에 사본 clone이나 결과 폴더를 만들지 않는다(학생 경로 시험 폴더 `D:/HYD-Practice` · `~/.hyd-toy-test`는 예외 — 학생 AI가 저장소 규칙 파일을 읽지 않게) | 어디에도 올리지 않는다 |
| `.env` · `.venv314/` | 이 PC 전용 | 어디에도 올리지 않는다 |

## 2. 브랜치와 동기화

- 브랜치는 main과 workspace 둘뿐이고, 다른 브랜치와 태그는 없어야 한다. main은 `.gitignore`로 `workspace/`와 `작업/`을 무시한다. workspace는 main과 이력을 공유하지 않으며, 둘을 병합하지 않는다.
- 동기화는 `PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/동기화.py` 하나로 한다. 순서는 `pull` → `commit "메시지" [main 경로 …] [--만 workspace 경로 …]` → 바로 `push`다. `push`는 origin에 없는 커밋마다 키 검사에서 걸린 수가 0일 때만 올리고, 강제 push는 하지 않는다. `commit`은 origin이 앞서 있으면 멈추고, `pull`은 원격 변경이 이 PC의 판과 겹치면 멈춘다. 멈추면 그 안내대로 하고 우회하지 않는다. 규칙 문서가 바뀐 커밋은 재편검사 오류가 0일 때만 만들어진다. 작업을 시작할 때와 커밋 직전에 `status`로 HEAD와 미커밋 변경을 보고, 다른 세션의 미커밋 변경은 보존한다. rebase, reset, stash는 쓰지 않는다. 사용법은 그 파일의 머리말에 있다.
- 노션과 학생 링크가 커밋에 고정된 주소를 쓰므로, 이력을 다시 쓰거나 브랜치를 지우지 않는다. 공개 저장소이므로 키, 개인 정보, 실물 매뉴얼 PDF를 어느 브랜치에도 올리지 않는다.
- 이력은 줄어들지 않으며 그 대부분이 mp4와 mp3다. 영상은 사용자가 들어 본 뒤 고칠 곳을 모아 한 번만 다시 올린다. 세션 사이에 넘겨주려고 영상, 음성, 원본을 올리지 않고, 이 PC에서 할 몫은 `workspace/강의제작/남은일.md`에 적는다(음성 캐시 `음성_저장/` · `쉼_저장/`은 재구매를 막는 재료라 올린다 — 영상 V-12). `git rev-list --disk-usage --objects origin/workspace`가 7GB를 넘으면 새 영상을 Release로 옮길지 사용자에게 묻는다.

## 3. 기록

- 진행 상황, 결정, 남은 일은 그 작업 폴더의 `기록.md` 하나에 지금 상태만 고쳐 쓴다. 확정되면 최종본은 산출물로, 재료는 제작도구로 옮기고, 동기화한 뒤 `동기화.py 정리 --실행`을 돌린다.
- 규칙은 한 곳에만 둔다. 교재 기준은 `공통.md`와 그 일 문서가, 작업 순서는 `hyd-task`가, 브랜치와 커밋은 이 문서 2절이 정한다. 규칙을 고칠 때는 그 자리를 다시 써서 합치고, 덧붙이기나 중복이 없어야 한다. 고친 뒤 `workspace/강의제작/제작도구/검사/재편검사.py`의 오류가 0이어야 한다.

## 4. 시스템 규칙

- **유지보수가 1순위다.** 지금 로직을 살려 근본 원인을 고친다. 관리할 곳(파일, 설정, 도구, 규칙 사본)이 줄어드는 쪽을 고르고, 새 장치를 더하기보다 지우기를 고른다. 시험은 한 기능을 한 곳에서 실제로 판정한다. 가짜는 시스템 밖의 것에만 쓰고, 호출 횟수 세기, 문자열 존재 확인, 현재 값 고정 같은 장난감 시험은 만들지 않는다. 설계가 갈리면 uengine-oss ProcessGPT 계열 레포를 참고한다.
- **fable 모델을 쓰지 않는다** — 메인 세션, 서브에이전트, 워커 모두에서.
- **시간은 세 갈래다.** 값은 compose.yaml 한 곳에만 있고 `.env`가 덮어쓰지 않는다. 바꾸는 법은 `workspace/개발/문서/RUNBOOK.md` §6에 있다.
  - 가상 설비, 감지기, 재관측은 배속 20배(`TIME_SCALE`)로 돈다.
  - 시간 대기와 입고(부품 대기)는 배속에 수업 압축 `PROCESS_WAIT_COMPRESSION` 60을 곱한 1200배로 돈다(납기 5일이 6분).
  - 사람이 읽고 고르는 시간(승인 시한, 승인 카드 신선도, 승인 지연 알림)은 벽시계다.
  - 경계 타이머는 그 타이머가 감싼 일의 시계를 따른다. 사람, 에이전트, IT 시스템 단계는 벽시계, 재관측과 시운전은 배속, 기다리는 부품은 배속 × 압축이다. 정본은 `it/process/procsvc/engine.py` 머리말의 「시간 규칙」이다.
  - "1~2배속 권장" 같은 문구가 없어야 한다. 20배속에서 흔들리는 코드는 배속을 기준으로 고친다.
- **떠 있는 스택을 쓰는 테스트와 도구(`test_portal_ui.py`, `class_round.py`)가 도는 동안에는 `docker compose build/up/restart`를 하지 않는다.** process가 재시작되어 `RemoteDisconnected`로 끊기기 때문이다. 배포를 먼저 끝내고 `docker inspect $(docker compose ps -q process) --format '{{.State.StartedAt}} {{.RestartCount}}'`로 안정됐는지 본다(이 PC의 컨테이너 이름은 `.hyd-runtime/project.json`에 있다). 에러 없이 재시작했으면 커널 OOM을 의심한다(`wsl -d docker-desktop -e sh -c "dmesg | grep -i oom"`).
- 워커는 늘 하나만 띄운다. 호스트 워커(`workspace/개발/scripts/run_worker_host.sh`, 개발용)를 쓰려면 먼저 `docker compose stop agent-worker`를 한다.
- 완주 검증과 E2E 검증은 학생 대역 1명, 인스턴스 1건으로 1회만 돌린다. 학생 수만큼 동시에 돌리지 않는다.
- AI 워커(`agent-worker`)와 에이전트용 MCP(enterprise-mcp · -maint · -purchase · dmn-mcp)는 기본 서비스다. 선택 프로필은 `monitor`와 `tools`뿐이다. 시스템 안의 모든 AI는 강의 중계 LiteLLM(GCP Cloud Run)으로 간다. 이 중계는 키마다 비용 한도를 두고 가장 싼 모델을 쓰며, 첫 요청은 콜드스타트로 느리다(의도한 동작이다). 워커 CLI는 키를 받지 않고 process의 로컬 중계 관문(`procsvc/course_model.py`)을 거친다. 이 관문은 작업에 묶인 토큰과 PC당 호출 상한을 쓰고, 장부는 `procsvc/course_ledger.py`다. process는 `.env`의 `LLM_API_KEY`와 compose의 `LLM_RELAY_URL`로 중계를 부른다. 학생의 바이브 코딩은 학생 각자의 Codex 계정으로 하므로 시스템과 별개다.
- 키가 없으면 AI 자리는 강사 녹화를 재생한다. 시작.bat이 `LLM_API_KEY`가 있는지에 따라 `AI_MODE`(live 또는 replay)를 적는다. 동작과 녹화 방법은 `workspace/개발/문서/재생모드.md`에 있다.
- Supabase 로컬은 시작 스크립트가 `npx -y supabase@2.119.0 start`로 켠다(PostgreSQL 15). 이 PC의 project_id와 포트는 git 밖의 `it/supabase/.env`와 `.hyd-runtime/`에 있다(업무 DB 포트는 64322). `config.toml`은 커밋된 값 그대로 둔다. `supabase stop --no-backup`은 볼륨을 지운다.
- 컨테이너, Supabase, 워커는 스스로 켜고 끈다. 시험 잔재(임시 DB, 시험 인스턴스)는 스스로 정리하고 꺼졌는지 확인한다. 프로젝트 데이터 볼륨, 원자료, 강사 손질본의 삭제와 결제는 먼저 묻는다.

## 5. 내용 규칙

- **수업 경계**: 학생은 포털 기능을 모두 실제로 써 본다. 통제하는 것은 AI가 답을 만드는 자리뿐이다. 키가 없으면 강사 녹화를 재생하고, 키가 있으면 실제 AI가 답한다. 키가 있을 때도 큰 문서 인제스천은 제공 문서의 캐시를 쓰고, 같은 요청에는 저장된 응답을 돌려준다(질문은 저장하지 않는다). 막는 것은 악용 지점(허용 밖 문서, 대용량, 외부 도구 서버 등록, 수업 모델 밖 모델)뿐이다. 재생 화면은 실제 AI 화면과 같아야 하고 「강사」나 「녹화」라는 말이 없어야 한다. 재생이 지원하지 않는 행동에서만 「AI 키가 없을 때 쓰는 재생 모드에서는 …」으로 안내하고 그 행동을 실패로 둔다. 정본은 `it/process/procsvc/course_policy.py` 한 곳이고, 화면과 워커는 이 정책을 서버에서 읽는다. PBL 해제는 강사가 서명한 단계 선언(`it/process/procsvc/course_phase.json`, 도구는 `workspace/개발/scripts/course_phase_sign.py`)을 커밋하고 push하는 것 하나뿐이다(최종 방어는 중계 키의 한도다).
- 시나리오, BPMN, 온톨로지에는 저장소에 있는 이름만 쓴다. 작업 전에 코드(agentsvc · procsvc · entsim · seed)를 먼저 읽는다. 정본은 `workspace/개발/문서/ontology/schema-v2.md`, `it/neo4j/v2/instances.cypher`, 템플릿 `it/neo4j/templates/`다. 온톨로지는 객체 모델(클래스, 속성, 관계)이고, 프로세스 설명은 온톨로지가 아니다.
- 해피패스 데이터와 구세주 데이터(문제를 마침 풀어 주도록 끼워 넣은 데이터)는 금지다. 사례마다 손익으로 지는 대안과 실제로 밟는 비해피 가지가 있어야 한다.
- 승인 전에 에이전트는 조회, 계산, 보고서 작성만 한다. 사람이 1회 승인한 뒤에 process가 실행한다.
- 업무 흐름은 사건 한 건을 프로세스 인스턴스 하나로 쓰고, 그 안을 task 단위(시스템 · 에이전트 · 규칙 · 사람 · 현장)로 나눠 쓴다.
- 온톨로지나 스키마 결과를 사용자에게 보고할 때는 전문 용어에 비유 한 줄을 붙이고, "사용자가 스스로 판정할 체크 질문"을 함께 준다.
- 참고 레포와 다른 곳은 두 가지만 묻는다: ① 실제 결함인가 ② 회의나 계약의 요구를 채우지 못하는가. 둘 다 아니면 "차이 있음, 유지"로 기록한다.
- 포털 UI는 새로 추가한 것만 `workspace/개발/문서/UIUX_PLAN.md`를 기준으로 다듬는다.
- 강의 작업에서는 포털 로직, DB, 서비스를 바꾸지 않는다. 교재 규칙은 `workspace/강의제작/지침/공통.md`와 그 일 문서가 정한다.

## 6. 환경 (로컬 Windows)

파이썬은 세 갈래다. 서비스 컨테이너는 `python:3.12-slim`이다. 학생 PC는 3.13 이상이고, 시작.bat 보조와 코딩 랩에 쓰며 표준 라이브러리만 쓴다. 이 PC의 개발 · 제작 도구는 `.venv314`(공식 3.14, 의존성은 `workspace/requirements-dev.txt`)다.

| | 로컬 Windows |
|---|---|
| Python | `.venv314/Scripts/python.exe`를 쓰고 늘 `PYTHONUTF8=1`을 붙인다. uv 파이썬은 Smart App Control이 막는다 |
| 테스트 | `workspace/개발/문서/RUNBOOK.md` §5의 첫 줄 명령을 쓴다(이 PC의 업무 DB 포트는 64322, 포털은 8088). 테스트 DB 이름은 `hyd_test…`만 받으며, 테스트가 그 DB를 지우고 다시 만든다. Docker가 켜져 있어야 한다 |
| 떠 있는 스택 확인 | 점검은 `bash scripts/check_all.sh`(점검.bat과 같다), 수업 한 바퀴는 `workspace/개발/scripts/class_round.py` |
| 호스트 워커 멈추기 | `workspace/개발/scripts/stop_worker_host.ps1`을 돌리고 포트 8097이 내려갔는지 확인한다(워커 1개가 python 프로세스 2개로 보인다) |
| compose 값 바꾸기 | 이 PC에서만 저장소 루트의 `compose.override.yaml`에 쓴다(git이 무시하고, compose가 저절로 합친다). 쓰는 법은 RUNBOOK에 있다. `.env`에 적은 수업 값은 compose가 읽지 않는다 |
| Docker | Docker Desktop(메모리 4 GB 이상). 꺼져 있으면 직접 켜고 `docker info`가 응답할 때까지 기다린다 |
| 렌더 · 영상 도구 | PATH에 없다. `ffmpeg`와 `ffprobe`는 `%LOCALAPPDATA%/Microsoft/WinGet/Packages/Gyan.FFmpeg_*/ffmpeg-*/bin`, `pdftoppm`은 `.../oschwartz10612.Poppler_*/poppler-*/Library/bin`, `soffice`는 `C:/Program Files/LibreOffice/program`에 있다. Git Bash에서는 `$(cygpath -u "$LOCALAPPDATA")`로 경로를 잡아 PATH에 더한다. 역슬래시 경로를 그대로 넣으면 `C:`의 콜론에서 경로가 갈라지기 때문이다 |

## 7. 클라우드 세션 (`CLAUDE_CODE_REMOTE=true`)

**준비는 한 길이다: 사용자가 환경의 셋업 스크립트 칸에 `git fetch -q --depth 1 origin workspace && git show FETCH_HEAD:workspace/개발/scripts/cloud_setup.sh | bash`를 넣으면 새 세션이 도구 설치와 workspace 풀기를 자동으로 마친다.** 「셋업 실패」나 「부트스트랩 실패」 알림이 보이면 먼저 사용자에게 알린다. 위 절의 `.venv314` 명령은 클라우드에서 `python3`로 바꿔 읽는다. 클라우드는 GitHub에 올라간 것만 받는다.

| | 클라우드 |
|---|---|
| 커밋 · push | 2절과 같다. pull과 commit은 해시 계산에 5~10분 걸리니 백그라운드로 돌린다. 그 사이 origin이 앞서 밀리면 pull → commit → push를 바로 다시 한다. main이 origin보다 뒤처졌으면, main에 미커밋 변경이 없을 때 `git merge --ff-only origin/main`을 한 뒤 push한다 |
| 작업 폴더 | VM이 회수되면 파일이 사라지므로 확정분은 그때그때 push한다. `작업/`은 커밋하지 않는다. 이어받을 사람이 있을 때만 인계 자료를 `workspace/강의제작/제작도구/근거/<날짜>_<제목>/`에 두고, 그 일이 확정되면 지운다. 렌더 그림, 영상 출력, 중간 파일은 남기지 않는다. 이어받을 스펙과 기록은 요청문에 담는다 |
| 덱 렌더 | 맑은 고딕 글꼴이 있어야 한다. 글꼴 파일은 사용자에게 파일 첨부로 받고(메시지에 `@C:\Windows\Fonts\…` 경로를 적어서는 파일이 오지 않는다) 커밋하지 않는다. `sudo bash workspace/강의제작/제작도구/기존제작/tools/deck/렌더환경_클라우드.sh <맑은 고딕 폴더>`를 돌린 뒤(VM이 다시 켜지면 다시 돌린다) `PATH=/usr/local/lo268/bin:$PATH`로 `deck2pptx.py --render`를 돌린다. apt로 설치한 LibreOffice와 Noto 글꼴로 렌더하면 줄바꿈이 달라서, 그 결과는 넘침 판정에 쓰지 않는다. 글꼴이 없으면 이 PC에서 렌더한 PDF를 받아 `pdftoppm -r 150`으로 `tools/video/슬라이드/<덱>/s-NN.png`에 넣고, `stamp`에 PPTX SHA256을 적는다(그러면 `강의영상.py`가 장을 다시 그리지 않는다). 강조 글씨의 글꼴은 `EMPH_FONT`로 정한다 |
| 사실 대조 그래프 | `dockerd`를 띄운 뒤 `AI_MODE=replay CMD_FINGERPRINT_KEY=x PROCESS_CALLER_TOKEN=x docker compose up -d neo4j kg-seed`를 돌린다. 이것은 기본 시드만 올린다. 수업 문서 적재분은 이 PC의 `작업/_보관/근거/2026-11-03_5-6회차_인계/실측/` 덤프에만 있고 클라우드에는 없다 |
| 음성 키 | 환경 변수가 `ElevenLabs_API_KEY`라는 이름으로 들어오면 `ELEVENLABS_API_KEY="$ElevenLabs_API_KEY"`로 넘긴다(값은 출력하지 않는다). `api.elevenlabs.io`가 네트워크 허용 목록에 있어야 한다 |
| 속도 | 4코어 VM에서는 이론 영상 굽기가 한 편에 22~30분, 강조 첫 실행이 15~35분(3편 동시) 걸리므로 시작 전에 알린다. 이 PC는 굽기 127초, 강조 306초(1편)이므로 렌더 뒤의 일은 이 PC에서 하는 쪽을 먼저 고른다. 도는 작업 수는 `ps -eo args \| grep -cE "^python3 .*tools/video/.*\.py "`로 센다(`pgrep -f`는 한글을 ?로 보여 줘서 0으로 센다). 오래 도는 일은 `setsid nohup`으로 띄운다 |
| 못 하는 것 | 클라우드에서는 ego 브라우저, 네이티브 VS Code, 데스크톱 캡처, 학생 Codex 로그인을 쓸 수 없다. 그래서 ARROWS, Notion, Neo4j, 웹 VS Code 촬영과 가이드 사진, 학생 경로 리허설은 이 PC에서 한다. 포털 촬영은 클라우드 Playwright가 정본이다(포털 촬영준비 「길」의 클라우드 항목) |
