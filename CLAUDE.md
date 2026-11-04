# hyd-iot-edu — 프로젝트 계약 (이 PC의 저장소 루트에 둔다 · workspace 브랜치에 백업 · main에는 없다)

## 0. 무엇이든 시키면

스킬 `hyd-task`의 길을 밟는다: **작업 폴더 → 그 일 문서(`공통.md` + 일 문서 하나) 끝까지 읽기 → 그 회차 맥락만 뽑기 → 만들기 → 자동 검사 → 독립 검토 1회 → 목록만 고침 → 제자리 · 동기화 · 정리.** 열린 작업 폴더(`작업/<날짜>_<제목>/`)가 있으면 그 `스펙.md` · `기록.md`부터 잇는다. 대화 요약 뒤에는 그 일 문서를 다시 읽는다(Claude는 `.claude/hooks/guide_gate.py`가 읽기 전 편집을 막고, Codex는 `.codex/hooks.json`이 안내한다).

- 유료 실행은 목적 · 성공 기준 · 상한을 정하고, 실패한 같은 조건을 다시 돌리지 않는다.
- 지울 것은 「이건 이런 건데 필요합니까」로 묻는다. "알아서 해"로 맡겼으면 분명히 필요 없는 것(지금 수업 · 개발에 안 쓰이거나 최신 판이 따로 있는 것)은 지우고(git 이력에 남는다) 애매한 것만 묻는다.
- 같은 사실은 한 곳에만 쓰고 나머지는 가리킨다.

## 1. 구조 — 어디에 무엇이 있나

| 자리 | 무엇 | 브랜치 |
|---|---|---|
| `README.md` · `compose*.yaml` · `.env.example` · `setup/`(설치 · 시작 · 끄기 · 점검) · `scripts/`(그 파일이 부르는 것만) · `it/` `ot/` `dmz/` `common/` | 학생이 clone해 실행하는 것 — 코드 · 프롬프트 · 설정 · 수업 데이터(수업 문서 원문 `it/portal/www/samples/`). 사람용 문서는 루트 README 하나 | main |
| `workspace/README.md` | **하려는 일 → 읽을 문서** 색인(진입 표는 여기 한 곳) | workspace |
| `workspace/강의제작/지침/` | `공통.md` · 일 문서 여섯(실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드) · 사실표 · 설계서 | workspace |
| `workspace/강의제작/산출물/` | 완성본 최신 판만(과정별 이론 · 이론_오프라인 · 실습, 영상, 실라버스 엑셀) | workspace |
| `workspace/강의제작/제작도구/` | 다시 만들 재료(원고 · 구성 · 큐 · 촬영도구 · 음성 캐시 · 촬영준비 · 검사기) | workspace |
| `workspace/개발/` | 시스템 개발용 문서 · 테스트 · 생성기 · 확인 도구(목록은 `workspace/README.md` 「폴더」) | workspace |
| `workspace/동기화.py` · `secret_scan.py` · `requirements-dev.txt` | 두 브랜치 동기화 · 작업 폴더 시작 · 정리 · 키 검사 · 개발 의존성 | workspace |
| `.claude/` · `CLAUDE.md` · `AGENTS.md` | Claude · Codex가 루트에서 읽는 규칙 · 스킬 · 훅 | workspace |
| `작업/<YYYY-MM-DD>_<제목>/` | 진행 중 작업 하나(`스펙.md` · `기록.md` · 원본 · 임시 출력). `작업/촬영/<도구>/` 녹화 원본, `작업/_로컬/` 공개 금지 개인 자료. 저장소 밖에 사본 clone · 결과 폴더를 만들지 않는다 | 어디에도 안 올림 |
| `.env` · `.venv314/` | 이 PC 전용 | 어디에도 안 올림 |

## 2. 브랜치와 동기화

- 브랜치는 main · workspace 둘뿐이다(다른 브랜치 · 태그 0). main은 `.gitignore`로 `workspace/` · `작업/`을 무시한다. workspace는 main과 이력을 공유하지 않고 병합하지 않는다.
- 동기화는 `PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/동기화.py` 하나로: `pull` → `commit "메시지" [main 경로 …] [--만 workspace 경로 …]` → 바로 `push`(origin에 없는 커밋마다 키 검사 0일 때만, 강제 push 없음). `commit`은 origin이 앞서 있으면, `pull`은 원격 변경이 이 PC 판과 겹치면 멈춘다 — 그 안내대로 하고 우회하지 않는다. 규칙 문서가 바뀐 커밋은 재편검사 오류 0일 때만 붙는다. 시작과 커밋 직전에 `status`로 HEAD · 미커밋을 보고 다른 세션의 미커밋은 보존한다. rebase · reset · stash 0. 사용법은 그 파일 머리.
- 노션 · 학생 링크가 커밋 고정 주소라 이력을 다시 쓰거나 브랜치를 지우지 않는다. 공개 저장소다 — 키 · 개인 정보 · 실물 매뉴얼 PDF를 어느 브랜치에도 올리지 않는다.
- 이력은 줄지 않고 대부분이 mp4 · mp3다. 영상은 사용자가 들어 본 뒤 고칠 곳을 모아 한 번만 다시 올리고, 세션 사이 전달용으로 영상 · 음성 · 원본을 올리지 않는다(이 PC 몫은 `workspace/강의제작/남은일.md`). `git rev-list --disk-usage --objects origin/workspace`가 7GB를 넘으면 새 영상을 Release로 옮길지 묻는다.

## 3. 기록

- 진행 · 결정 · 남은 일은 그 작업 폴더 `기록.md` 하나에 지금 상태만 고쳐 쓴다. 확정되면 최종본은 산출물로, 재료는 제작도구로 옮기고 동기화한 뒤 `동기화.py 정리 --실행`.
- 규칙은 한 곳: 교재 기준은 `공통.md` + 그 일 문서, 작업 순서는 `hyd-task`, 브랜치 · 커밋은 이 문서 2절. 고칠 때는 그 자리를 다시 써서 합치고(덧붙이기 · 중복 0) `workspace/강의제작/제작도구/검사/재편검사.py` 오류 0.

## 4. 시스템 규칙

- **유지보수가 1순위다.** 지금 로직을 살려 근본 원인을 고치고, 관리할 곳(파일 · 설정 · 도구 · 규칙 사본)이 줄어드는 쪽, 새 장치보다 지우기를 고른다. 시험은 한 기능을 한 곳에서 실제로 판정한다 — 가짜는 시스템 밖만, 호출 횟수 · 문자열 존재 · 현재 값 고정 같은 장난감 금지. 설계가 갈리면 uengine-oss ProcessGPT 계열 레포를 참고한다.
- **fable 모델을 쓰지 않는다** — 메인 세션 · 서브에이전트 · 워커 모두.
- **시간은 세 갈래다(값은 compose.yaml 한 곳 — `.env`가 덮지 않는다, 바꾸는 법은 `workspace/개발/문서/RUNBOOK.md` §6).** 가상 설비 · 감지기 · 재관측은 배속 20배(`TIME_SCALE`). 시간 대기 · 입고(부품 대기)는 배속 × 수업 압축 `PROCESS_WAIT_COMPRESSION` 60 = 1200배(납기 5일이 6분). **사람이 읽고 고르는 시간(승인 시한 · 승인 카드 신선도 · 승인 지연 알림)은 벽시계다.** 경계 타이머는 감싼 일의 시계다 — 사람 · 에이전트 · IT 시스템 단계는 벽시계, 재관측 · 시운전은 배속, 기다리는 부품은 배속 × 압축(정본 `it/process/procsvc/engine.py` 머리말 「시간 규칙」). "1~2배속 권장" 문구 0. 20배속에서 흔들리는 코드는 배속 기준으로 고친다.
- **떠 있는 스택을 쓰는 테스트 · 도구(`test_portal_ui.py`, `class_round.py`)가 도는 동안 `docker compose build/up/restart` 금지** — process가 재시작돼 `RemoteDisconnected`로 끊긴다. 배포를 먼저 끝내고 `docker inspect $(docker compose ps -q process) --format '{{.State.StartedAt}} {{.RestartCount}}'`로 안정을 본다(이 PC의 컨테이너 이름은 `.hyd-runtime/project.json`). 에러 없이 재시작했으면 커널 OOM을 의심한다(`wsl -d docker-desktop -e sh -c "dmesg | grep -i oom"`).
- 워커는 늘 하나다: 호스트 워커(`workspace/개발/scripts/run_worker_host.sh`, 개발용)를 쓰면 먼저 `docker compose stop agent-worker`.
- 완주 · E2E 검증은 학생 대역 1명 · 인스턴스 1건 · 1회. 학생 수만큼 동시에 돌리지 않는다.
- AI 워커(`agent-worker`)와 에이전트용 MCP(enterprise-mcp · -maint · -purchase · dmn-mcp)는 기본 서비스다(선택 프로필은 `monitor` · `tools`뿐). 시스템 안의 모든 AI는 강의 중계 LiteLLM(GCP Cloud Run, 키별 비용 한도 · 가장 싼 모델, 첫 요청은 콜드스타트로 느림 — 의도)으로 간다. 워커 CLI는 키를 받지 않고 process의 로컬 중계 관문(`procsvc/course_model.py`, 작업에 묶인 토큰 · PC당 호출 상한, 장부 `procsvc/course_ledger.py`)을 거치고, process가 `.env`의 `LLM_API_KEY`와 compose의 `LLM_RELAY_URL`로 중계를 부른다. 학생 바이브 코딩은 각자 Codex 계정이라 시스템과 별개다.
- 키가 없으면 AI 자리는 강사 녹화 재생이다 — 시작.bat이 `LLM_API_KEY` 유무로 `AI_MODE`(live · replay)를 적는다. 동작 · 녹화는 `workspace/개발/문서/재생모드.md`.
- Supabase 로컬: 시작 스크립트가 `npx -y supabase@2.119.0 start`로 켠다(PostgreSQL 15). 이 PC의 project_id · 포트는 git 밖 `it/supabase/.env` · `.hyd-runtime/`(업무 DB 포트 64322), `config.toml`은 커밋된 값 그대로. `supabase stop --no-backup`은 볼륨을 지운다.
- 컨테이너 · Supabase · 워커는 스스로 켜고 끄고, 시험 잔재(임시 DB · 시험 인스턴스)는 스스로 정리하고 꺼졌는지 확인한다. 프로젝트 데이터 볼륨 · 원자료 · 강사 손질본 삭제와 결제는 묻는다.

## 5. 내용 규칙

- **수업 경계**: 학생은 포털 기능을 다 실제로 써 본다. 통제하는 것은 AI가 답을 만드는 자리뿐이고(키 없음 = 강사 녹화 재생, 키 있음 = 실제 AI + 큰 문서 인제스천은 제공 문서 캐시, 같은 요청은 저장 응답 — 질문은 저장하지 않음), 막는 것은 악용 지점(허용 밖 문서 · 대용량 · 외부 도구 서버 등록 · 수업 모델 밖 모델)뿐이다. 재생 화면은 실제 AI와 같고(「강사」 · 「녹화」 말 0), 재생이 지원하지 않는 행동에서만 「AI 키가 없을 때 쓰는 재생 모드에서는 …」으로 안내하고 실패로 둔다. 정본은 `it/process/procsvc/course_policy.py` 한 곳이고 화면 · 워커는 서버에서 읽는다. PBL 해제는 강사 서명 단계 선언(`it/process/procsvc/course_phase.json`, 도구 `workspace/개발/scripts/course_phase_sign.py`)을 커밋 · push하는 것 하나다(최종 방어는 중계 키 한도).
- 시나리오 · BPMN · 온톨로지는 저장소에 있는 이름만 쓴다. 작업 전에 코드(agentsvc · procsvc · entsim · seed)를 먼저 읽는다. 정본: `workspace/개발/문서/ontology/schema-v2.md`, `it/neo4j/v2/instances.cypher`, 템플릿 `it/neo4j/templates/`. 온톨로지는 객체 모델(클래스 · 속성 · 관계)이고 프로세스 설명은 온톨로지가 아니다.
- 해피패스 · 구세주 데이터 금지: 사례마다 손익으로 지는 대안과 실제로 밟는 비해피 가지가 있다.
- 승인 전 에이전트는 조회 · 계산 · 보고서만 한다. 사람 승인 1회 뒤 process가 실행한다.
- 업무 흐름은 "사건 한 건 = 프로세스 인스턴스 하나, 그 안을 task 단위(시스템 · 에이전트 · 규칙 · 사람 · 현장)"로 쓴다.
- 온톨로지 · 스키마 결과를 사용자에게 보고할 때는 전문 용어에 비유 한 줄과 "사용자가 스스로 판정할 체크 질문"을 같이 준다.
- 참고 레포와 다른 곳은 ① 실제 결함인가 ② 회의 · 계약 요구를 못 채우는가만 묻고, 둘 다 아니면 "차이 있음, 유지"로 기록한다.
- 포털 UI는 추가한 것만 `workspace/개발/문서/UIUX_PLAN.md` 기준으로 다듬는다.
- 강의 작업에서 포털 로직 · DB · 서비스를 바꾸지 않는다. 교재 규칙은 `workspace/강의제작/지침/공통.md` + 그 일 문서가 정한다.

## 6. 환경 (로컬 Windows)

파이썬은 세 갈래다: 서비스 컨테이너 `python:3.12-slim`, 학생 PC 3.13 이상(시작.bat 보조 · 코딩 랩, 표준 라이브러리만), 이 PC 개발 · 제작 도구 `.venv314`(공식 3.14, 의존성 `workspace/requirements-dev.txt`).

| | 로컬 Windows |
|---|---|
| Python | `.venv314/Scripts/python.exe`(늘 `PYTHONUTF8=1`). uv 파이썬은 Smart App Control이 막는다 |
| 테스트 | `workspace/개발/문서/RUNBOOK.md` §5 첫 줄(이 PC 업무 DB 포트 64322 · 포털 8088). DB 이름은 `hyd_test…`만 받고 지우고 다시 만든다. Docker가 켜져 있어야 한다 |
| 떠 있는 스택 확인 | 점검 `bash scripts/check_all.sh`(= 점검.bat), 수업 한 바퀴 `workspace/개발/scripts/class_round.py` |
| 호스트 워커 멈추기 | `workspace/개발/scripts/stop_worker_host.ps1`, 포트 8097이 내려갔는지 확인(워커 1개가 python 2개로 보인다) |
| compose 값 바꾸기 | 이 PC에서만 저장소 루트 `compose.override.yaml`(git 무시, compose가 저절로 합친다) — 쓰는 법은 RUNBOOK. `.env`의 수업 값은 compose가 읽지 않는다 |
| Docker | Docker Desktop(메모리 4 GB 이상). 꺼져 있으면 직접 켜고 `docker info` 응답을 기다린다 |
| 렌더 · 영상 도구 | PATH에 없다. `ffmpeg` · `ffprobe`는 `%LOCALAPPDATA%/Microsoft/WinGet/Packages/Gyan.FFmpeg_*/ffmpeg-*/bin`, `pdftoppm`은 `.../oschwartz10612.Poppler_*/poppler-*/Library/bin`, `soffice`는 `C:/Program Files/LibreOffice/program`. Git Bash에서는 `$(cygpath -u "$LOCALAPPDATA")`로 잡아 PATH에 더한다(역슬래시 경로를 그대로 넣으면 `C:`의 콜론에서 갈라진다) |

## 7. 클라우드 세션 (`CLAUDE_CODE_REMOTE=true`)

**준비는 한 길이다: 사용자가 환경의 셋업 스크립트 칸에 `git fetch -q --depth 1 origin workspace && git show FETCH_HEAD:workspace/개발/scripts/cloud_setup.sh | bash`를 넣으면 새 세션이 도구 설치와 workspace 풀기를 자동으로 마친다.** 「셋업 실패」 · 「부트스트랩 실패」 알림이 보이면 먼저 사용자에게 알린다. 위 절의 `.venv314` 명령은 `python3`로 읽는다. 클라우드는 GitHub에 올라간 것만 받는다.

| | 클라우드 |
|---|---|
| 커밋 · push | 2절과 같다. pull · commit이 해시에 5~10분 걸리니 백그라운드로 돌리고, 밀리면 pull → commit → push를 바로 다시. main이 origin보다 뒤면(main 미커밋 0일 때) `git merge --ff-only origin/main` 뒤 push |
| 작업 폴더 | VM이 회수되면 파일이 사라진다 — 확정분은 그때그때 push한다. `작업/`은 커밋하지 않고, 일을 닫기 전에 판정 · 다시 쓸 도구만 `workspace/강의제작/제작도구/근거/<날짜>_<제목>/`에 남긴다(렌더 그림 · 영상 출력 · 중간 파일 0). 이어받을 스펙 · 기록은 요청문에 담는다 |
| 덱 렌더 | 맑은 고딕이 있어야 한다 — 사용자에게 파일 첨부로 받고(메시지의 `@C:\Windows\Fonts\…` 경로로는 파일이 오지 않는다) 커밋하지 않는다. `sudo bash workspace/강의제작/제작도구/기존제작/tools/deck/렌더환경_클라우드.sh <맑은 고딕 폴더>`(VM이 다시 켜지면 다시) 뒤 `PATH=/usr/local/lo268/bin:$PATH`로 `deck2pptx.py --render`. apt LibreOffice · Noto 렌더는 줄바꿈이 달라 넘침 판정에 쓰지 않는다. 글꼴이 없으면 이 PC 판 렌더 PDF를 받아 `pdftoppm -r 150`으로 `tools/video/슬라이드/<덱>/s-NN.png`에 넣고 `stamp`에 PPTX SHA256을 적는다(`강의영상.py`가 다시 그리지 않는다). 강조 글씨 글꼴은 `EMPH_FONT` |
| 사실 대조 그래프 | `dockerd`를 띄운 뒤 `AI_MODE=replay CMD_FINGERPRINT_KEY=x PROCESS_CALLER_TOKEN=x docker compose up -d neo4j kg-seed`(기본 시드만 — 수업 문서 적재분은 이 PC `작업/_보관/근거/2026-11-03_5-6회차_인계/실측/` 덤프, 클라우드에는 없음) |
| 음성 키 | 환경 변수가 `ElevenLabs_API_KEY`로 들어오면 `ELEVENLABS_API_KEY="$ElevenLabs_API_KEY"`로 넘긴다(값은 찍지 않음). `api.elevenlabs.io`가 네트워크 허용 목록에 있어야 한다 |
| 속도 | 4코어 VM: 이론 영상 굽기 한 편 22~30분 · 강조 첫 실행 15~35분(동시 3편) — 시작 전에 알린다. 이 PC는 굽기 127초 · 강조 306초(1편)라 렌더 뒤 일은 이 PC를 먼저 고른다. 도는 수는 `ps -eo args \| grep -cE "^python3 .*tools/video/.*\.py "`(`pgrep -f`는 한글을 ?로 보여 0으로 센다). 오래 도는 일은 `setsid nohup` |
| 못 하는 것 | ego 브라우저 · 네이티브 VS Code · 데스크톱 캡처 · 학생 Codex 로그인 — ARROWS · Notion · Neo4j · 웹 VS Code 촬영, 가이드 사진, 학생 경로 리허설은 이 PC에서. 포털 촬영은 클라우드 Playwright가 정본(포털 촬영준비 「길」 클라우드) |
