# hyd-iot-edu — 에이전트 세션 시작 지침 (Codex · Claude Code 공통)

이 저장소의 보강 작업은 `docs/handoff/` 폴더가 생명선이다. 대화 요약이 끊겨도 그 폴더만 읽으면 이어갈 수 있어야 한다.

## 현재 작업 범위 (2026-10-04 최신 사용자 지시)

최신 정정: 대상은 회의 내용·참고 레포에 근거한 **HYD 시스템 개발과 실제 검증**이다. 교재·슬라이드·시수표 제작/수정 및 강사·학생 리허설은 범위 밖이다. 시스템 사용/운영 문서와 요구·구현 근거·HANDOFF 기록은 계속 관리한다. 과거 GOAL/자동 재개 문구의 강의자료 조건을 완료 조건으로 다시 가져오지 않는다.

Codex 워커 F만 완료하는 작업에서 회의 원문·HYD 전체·47개 레포 지도 기반의 재대조 및 필요한 재구현으로 확대됐다. GOAL의 현재 목표와 HANDOFF §9 **G**, AUDIT.md를 따른다. 기존 완료 기록은 범위별 과거 증거이며 전체 충족을 뜻하지 않는다. 사용자는 컴퓨터 자원 사용과 필요한 삭제를 허용했다. 아래 과거 삭제 승인 규칙은 이 작업 범위에서 대체되며, 새 결제·원격 push는 계속 묻는다. 기존 §2·§3도 최신 사용자 지시/원문과 충돌하면 근거를 남기고 갱신한다.

## 시작할 때 읽는 순서

1. `docs/handoff/GOAL.md` — 의도와 인수조건
2. `docs/handoff/HANDOFF.md` — 현재 사실·규칙·진행 상태(§9 가 핵심; 첫 `[ ]`/`[~]` 항목이 다음 일)
3. `docs/handoff/DECISIONS.md` — 결정 경위(특히 11~14)
4. `docs/handoff/QA.md`, `docs/handoff/USER_UTTERANCES.md` — 사용자가 물은 것과 답
5. 상위 폴더 `D:\work\study\CLAUDE.md` — 강의 준비 공통 계약(Codex 는 `D:\work\study\AGENTS.md` 가 그리로 안내한다)

## 지켜야 할 것

- 한국어로 답한다. 단계가 끝날 때마다 `HANDOFF.md` §9 를 갱신한다.
- 유료 결제 · 원격 push · 파일 삭제 · 사용자 설정 파일(`~/.codex/config.toml`, `~/.claude`) 의 기존 내용 변경은 먼저 묻는다.
- 컨테이너 · Supabase · 워커는 스스로 켜고 끄되, 끈 뒤 실제로 꺼졌는지 확인한다(워커는 PowerShell `Get-CimInstance Win32_Process | ? CommandLine -like '*worker.main*'`).
- 실행한 것만 "됐다"고 쓴다. 단위 테스트 통과 ≠ 실제 경로 완주. 예상 · 실측 · 미검증을 구분한다.
- 회의 근거는 `HANDOFF.md` §1 의 원문 줄 번호로 댄다. §2(확정 방향) · §3(절대 규칙)은 바꾸지 않는다.

## 환경 (2026-10-04)

- Windows 11, Git Bash. Python 은 `.venv314/Scripts/python.exe`(공식 3.14; uv 파이썬은 앱 제어 정책으로 차단됨). 테스트: `PYTHONUTF8=1 .venv314/Scripts/python -m pytest -q`(259 통과).
- Docker compose 프로필은 `.env` 의 `COMPOSE_PROFILES`. enterprise-mcp · dmn-mcp 는 프로필 `cliagents` 에만 있다: `docker compose --profile cliagents up -d enterprise-mcp dmn-mcp`(agent-worker 컨테이너는 올리지 말 것).
- Supabase 로컬: `cd it/supabase && supabase start`(PostgreSQL 15, 포트 54322). `supabase stop --no-backup` 은 볼륨을 지운다.
- 호스트 워커: `bash scripts/run_worker_host.sh`(환경변수 `CLIAGENTS_DEFAULT_CLI=claude-code|codex`). 로그는 cp949 가 섞이므로 바이트로 읽어 `errors='replace'` 로 디코드한다.
- 통합 시험: `scripts/scenario_instance_test.py`(쿨러, `--worker` 로 실제 워커 기대), `scripts/scenario_pump_fan_test.py`(펌프 · 팬 · 가림), `scripts/scenario_test.py --quick`(레거시, `PROCESS_MODE=legacy` 로 process 재기동 필요).
