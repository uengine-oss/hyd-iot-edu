# NOW — 새 세션은 이 문서 하나로 시작한다 (2026-10-12 검증·종료 갱신)

이 문서를 새로 썼다. 이전 판(갈래 L·F·K·U·S 병렬 서술)과 지난 경위는 git 이력과 `archive/`에 있다.
최신 숫자·상태는 10-12 검증·종료 기록이다. 이전 macOS와 10-11 종료 상태는 당시 기록으로 구분한다. 시작할 때 `git log -1` · `docker ps` · 단위 시험으로 다시 잰다.

## 1. 한눈에 보기

| 항목 | 값 |
|---|---|
| 브랜치 | 작업 `codex/portal-20261011` / `.claude/worktrees/codex-portal-20261011`. 기준 통합 브랜치 `claude/hyd-handoff-work-xziutz`. 코드 반영 해시는 git log와 최종 보고 참조 |
| 기능 | 기본 기능은 구현되어 있다. 이번 포털 U1~U4·U7·U8 구현·자동검증을 진행했고 캡처 사용자 시각 판정은 대기다. 나머지 UI/환경/학생 동선은 4절 |
| 전체 회귀 시험 | `pytest-final-integrated.log/xml` **2298 통과·23 건너뜀·64 경고,129.97초,exit0**. F20/F21 및 스킬 전달/읽기 요청 UI 후속 수정까지 포함한 최종 코드 기준 |
| 실제 스택 검증 | 현재 Windows: 최신 adapter·엄격 근거 alias 적용 `student-release` **18 checks PASS/exit0**. 실제 B는 도구 실행 후 지식 부족(causes=[]·PREVENTED_BY 없음)으로 자율보류 PENDING. A/B/C 현재 완주는 완료하지 않았다. **이전 macOS `4e5f535`의 A/B/C 완주·쿨러40/40·pump-fan43/43은 과거 증거**이며 현재 결과를 대신하지 않는다 |
| 한계 | 실제 `live-release` 46화면과 후속 `ui-f21-final` 6화면 모두 console/pageerror 0·무시 0·문서폭 넘침 0. 후속 ontology/flows의 식별자 검색 결과는 0이고 기존 작성명 `read_only` 1건은 보존했다. SVG 경계 초과 12개는 지도 내부 스크롤이며, 두 화면 폭에서 오른쪽 노드 이동·상세 클릭·키보드 선택 해제를 확인했다. 전체 국문화와 최종 디자인 승인은 별도다. `target-capture-final`의 기능 준비 7개는 통과했지만 health no-cors ERR_ABORTED로 전체 검사기는 exit1이다. 별도 CDP에서 HTTP200 뒤 opaque 응답 본문 취소·정상 health를 확인했고 원래 실패 결과를 보존했다. F3 사람 검토/적재·현재 A/B/C 지식 부족·K3 Google 외부 인증은 미완료. 최종 스킬 표시 수정은 독립 화면/전체 회귀로 검증했으며 실제 B 재캡처용 서비스 시작은 자동 승인 검토가 차단해 미실행(`portal-remaining.md`) |
| 실라버스 | **최종본이 나왔다(10-11).** 기준은 `docs/교재/기준/피지컬AI_실라버스_최종본.xlsx`다(네 시트: 통합반 온라인 44H · 11일, 실전반 온라인 32H · 8일, 통합반 오프라인 정규 10회, 실전반 오프라인 정규 9회). 통합반 1~4일차는 이전 확정안(`1~4일차 실라버스 확정안.xlsx`)과 행 단위로 같다 |
| 교재(슬라이드) | 레포 안 `docs/교재/`(안내 `README.md`). 기준 `docs/교재/기준/제작기준.md`, 통합반 1~4일차 덱 `docs/교재/통합반/0N일차/`(101 · 100 · 94 · 64장), 실전반 1~3일차 덱 `docs/교재/실전반/0N일차/`(101 · 93 · 75장, 통합반 덱에서 조립 — 제작 기준 13-1절). 원격 추가 교재4커밋은 통합반5일차66장·6일차73장·7일차57장·9일차72장으로 통합 시 보존한다. 8·10·11일차 존재는 추측하지 않는다. 실전반4일차 이후는 이 추가 목록에 없다, 컨펌받은 그림체 샘플 `통합반/샘플/`. 만드는 도구는 `.claude/skills/lecture-deck/`. 랩 자료는 만들지 않는다 |
| 현재 스택 | **10-12 03:28 KST 최종 정리 완료.** 실행 컨테이너0·관련 포트0·Docker Desktop/backend0·본인 LIVE_LOCK 해제. 두 Supabase backup=true, 볼륨/작업 트리 보존. 실제 B의 RUNNING/PENDING·열린 incident는 종료 전 상태 그대로 보존. 최신 지시로 재기동도 Sol 6.1만 사용한다. 코드 반영 해시는 git log와 최종 보고 참조 |

## 2. 스택 올리고 확인하는 방법

**10-12 03:28 KST 최종 상태가 우선**: 실제 검증에 사용한 제품 스택·독립 Supabase55322·Neo4j7787·학생 MCP8311·워커·Docker Desktop은 종료했다. 최신 `skill-delivery-live/services-off.json`·`cleanup-final.json`에서 실행 컨테이너·관련 포트·Desktop/backend0과 LIVE_LOCK 해제를 확인했다(02:53 최초 정리도 보존). 데이터 볼륨/작업 트리를 보존했고 B의 열린 incident/PENDING도 그대로 남긴다.

**현재 Windows 재기동은 Sol 전용 지시를 명시한다.** 제품 서비스를 먼저 준비하고 LIVE_LOCK 아래 워커1개만 실행한다. run_worker_host.sh와 settings의 다중 provider 기본값을 임의 변경하거나 개인 Codex 설정을 고치지 않는다. 아래 값은 이번 사용자 지시를 재현하는 실행별 환경변수다(실제 증거 worker-sol-only.log).

```powershell
$env:CLIAGENTS_DEFAULT_CLI = 'codex'
$env:CLI_MODEL = 'gpt-6.1-sol'
bash scripts/run_worker_host.sh
```

기준 사용자·역할·스킬 누락은 공식 seed public 부분만 보완했고 누락된 정비/구매 MCP만 추가했다. ent 데이터·tenant 설정 전체를 덮지 않았다. uvx 없는 환경의 동일 버전 Neo4j MCP 별도 venv/서명 Python과 원래 명령 snapshot도 보존했다. 아래 10-11 종료 및 macOS Claude 설명은 과거 환경이며 현재 Sol 전용 재기동 값과 구분한다.

이번 Windows(2026-10-11)에서는 Docker 29.7.2로 제품 서비스를 빌드·기동했고 포털 8088은 `codex-portal-20261011` 작업 트리를 사용했다. 기존 Supabase DB는 `migration up --local`로 25→51 적용했다(새 DB 재현 시험 아님). 기존 `neo4j-data` 전체판, 워커 0, RUNNING 0을 확인했고 지식을 수동 교정하거나 새 추출/사람 검토를 대신 만들지 않았다. process StartedAt `2026-10-11T14:03:54.003148877Z`, RestartCount 0. 캡처 후 hyd compose stop과 supabase stop으로 정지, 열린 해당 포트 없음 및 본인 LIVE_LOCK 해제를 확인했다. 볼륨·컨테이너 마운트 작업 트리는 보존했다.

실제 Docker 빌드·46화면 캡처 뒤 시작 조건 가져오기 API 호환성과 Windows 워커 artifact의 LF 바이트 보존을 추가 수정했다. 해당 마지막 변경까지 컨테이너 재빌드·실제 LLM 완주를 수행한 근거는 아니다. 최종 코드 회귀 시험과 당시 실제 스택 화면을 구분한다. Docker Desktop도 종료했으며 데이터 볼륨은 보존했다.

아래는 **이전 macOS + colima 실측 기록**이다. 그 환경의 세 작업 트리 마운트를 이번 Windows 상태와 혼동하지 않는다. 전체 기동 절차는 `docs/RUNBOOK.md`(Windows/Git Bash 기준)이고, macOS 차이는 아래다.

- 파이썬: 레포 루트 `.venv`(3.12). 작업 트리에서는 `<루트 절대 경로>/.venv/bin/python`. 다시 만들 때 `uv venv --python 3.12 .venv && uv pip sync --python .venv/bin/python docs/handoff/tools/venv-py312-freeze.txt`. `host_libpq.sh`는 필요 없다. `requirements-dev.txt`만 깔면 `fastmcp`가 없어 시험 2건이 실패한다(4.2절).
- compose: `export COMPOSE_PROFILES=ot,backbone,detect,knowledge,agent,enterprise,process,cliagents` 뒤 `docker compose -p hyd-iot-edu …`. `.env`의 `COMPOSE_PROFILES`에는 `cliagents`가 없다. zsh는 `$변수`의 서비스 목록을 나누지 않으니 서비스 이름을 직접 적는다. `.env` 값은 열지 않는다. `PLANT_SIM_URL`은 두지 않는다(기본, `sim-net`).
- 포트: process API 8080 · 포털 8088 · agent 8091 · dmn-mcp 8198 · enterprise-mcp 8199(정비 8196 · 구매 8195) · effects-mcp 8197 · neo4j 7474/7687 · Supabase DB 54322 · 메일함 화면 54324 · 워커 8097 · 설비 시뮬레이터 8000.
- DB: Supabase 로컬(54322). 마이그레이션 45~48 · 50 · 51은 `psql`로 직접 적용했다(장부는 44까지, 049 없음).
- 워커: `bash scripts/run_worker_host.sh`(작업 트리에서는 `PYTHON=<루트>/.venv/bin/python …`). **1개만.** 멈춤 `pkill -f worker.main` 뒤 포트 확인. 워커는 Claude Code 구독으로 돌아 세션 한도에 걸리면 `RunFailed`다(리셋 시각을 기록하고 기다림). 실패한 에이전트 task는 `/cancel`이 아니라 `POST /api/todolist/{wid}/close`(포털 '단계 닫기')로 끝낸다.
- 긴 실행 전 `caffeinate -dimsu -t 28800 &`. `rtk` 훅이 git 출력을 줄인다(원문 `rtk proxy <명령>`).
- 지금 스택이 물고 있는 코드(10-11 `docker inspect` 실측): process · agent · plant-sim · neo4j = 레포 루트. **portal · dmn-mcp · effects-mcp · enterprise-* ← `.claude/worktrees/merge-preview`, detector · cmd-gateway · connect-* · emqx · redpanda · fuxa · grafana ← `.claude/worktrees/agent-aed004354f1cd7a4c`, timescaledb ← `.claude/worktrees/agent-afd136e4b22934cb9`.** 이 세 작업 트리는 컨테이너가 파일을 직접 물고 있어 지우지 않는다(스택을 루트 기준으로 옮긴 뒤에만).
- 상태 보기: `docker inspect hyd-iot-edu-neo4j-1 --format '{{range .Mounts}}{{.Name}} {{end}}'`(`neo4j-data` = 전체판, `-c3` = 구조판) · `curl -s localhost:8080/api/scenario/status`(running이 null인지) · `lsof -iTCP:8097 -sTCP:LISTEN`.

### 라이브 잠금
스택은 하나뿐이다. 쓰기 전에 `<루트>/.evidence/LIVE_LOCK`을 본다. 있으면 기다리고, 없으면 "누가·시각·하는 일·예상 끝" 한 줄을 쓰고 시작해 복원이 끝난 뒤 지운다. 2시간 넘은 잠금은 `pgrep -fl 'worker.main|scenario_|probe_|run_final|record_shot|press.py|c3_ingest|c3_flows|playwright'`가 비었을 때만 사용자에게 묻고 푼다.
- 잠금이 필요한 일: `docker compose build/up/restart`, 워커, 버튼 누르기(쓰기 요청 전부), 회귀, 추출·적재, 흐름 배포, 그래프 볼륨 바꾸기. 검사기가 도는 동안 compose 금지.
- 잠금 없이 되는 일: GET 조회, 코드, 단위 시험, node vm 렌더 시험, 문서.
- 내 화면 보기(UI 작업): 포털 컨테이너(8088)는 건드리지 않는다. 작업 트리에서 `<루트>/.venv/bin/python -m http.server 87NN --bind 127.0.0.1 -d it/portal/www`로 띄워 본다(API는 같은 스택 8080, CORS 허용). 버튼을 누르면 잠금. 끝나면 서버를 끄고 포트를 확인한다.
- 서비스를 내 작업 트리 코드로 바꿀 때: 그 폴더에 `.env`를 두고 바뀐 서비스만 `docker compose -p hyd-iot-edu build <서비스> && docker compose -p hyd-iot-edu up -d --no-deps <서비스>`, 끝나면 `docker inspect hyd-iot-edu-process-1 --format '{{.State.StartedAt}} {{.RestartCount}}'`.

## 3. 버튼 완주 순서 (잠금 필요)

1. 그래프를 구조판으로: `docker compose -p hyd-iot-edu -f compose.yaml -f docs/handoff/tools/live/neo4j-c3.override.yaml up -d --no-deps neo4j`
2. `.venv/bin/python scripts/c3_flows.py deploy` (명령: `check | deploy | export DIR | deploy-reset BY`)
3. 워커 1개
4. 한 번에 한 건: A → 끝나면 [쿨러 복구], B, C. 승인 단계 확인은 `scripts/approval_stage_live.py <경우> <폴더>`(경우: A/B/C 승인·거절·무응답, 옵션 `--flow`, `--no-settle`)
5. 복원: `c3_flows.py deploy-reset <이름>` → 워커 멈춤 → 그래프 원래 볼륨(override 없이 `up -d --no-deps neo4j`) → 설비 `POST localhost:8000/api/reset` → B·C [초기화] → RUNNING 처리 건 0 확인 → 잠금 지움.
- 회귀 검사기의 `/api/reset`은 완주가 만든 업무 행(WO·PR·GR)을 보관 표로 옮긴다(처리 건 기록은 남음).
- 회귀: 쿨러 `scripts/scenario_instance_test.py --worker`, pump-fan `scripts/scenario_pump_fan_test.py --worker --reassess-held`(흐름 기준 · 그래프 전체판 · 설비 reset · 워커 1개 상태에서).
- 거절·무응답으로 끝난 A는 경보가 올라간 채라 [쿨러 복구] 뒤 감지기가 내릴 때까지(약 65초) 다음 주입이 새 처리 건을 열지 않는다(결함 아님).
- 도구(검토 전, 읽고 쓴다): `docs/handoff/tools/live/` — `run_final.py A|B|C <폴더>`(완주 + 캡처), `record_shot.py`, `press.py`, `render_approval.js`, `snapdiff.py`(PR-07 전용), `draw_flows.py`(`students/flows/*.bpmn` 그리기 — `c3_flows.py`를 고치면 다시 돌림). playwright는 루트 `.venv`에 있다.

## 4. 남은 일

2026-10-12 최신 사용자 지시 「아예 싹 다 밤새 진행 / 목표 설정」으로 U5·U6·U9~U21, F1~F21, K1~K4 전수 구현/검증과 서비스 정리를 수행했다(최신 지시: 모든 작업과 실제 워커는 Sol 6.1만). 사용자가 Claude 한도 뒤 Codex 워커 전환과 통상 구현 판단 자율 진행을 승인했다. 현재 판정·증거·차단 원인은 [overnight-status.md](verification/2026-10-12/overnight-status.md)에 모으며 체크는 명시한 검증 범위 완료를 뜻한다. 교재 수정은 제외한다. 최종 전체 회귀2298개·실제46화면·Codex student-release18개·독립PG K1 17개를 확인했다. 후속 변경은 해당 묶음의 검증으로 구분하며 실제 A/B/C 완주·사람 검토/적재·외부 인증 잔여는 아래에 남긴다. 앞선 실패 기록은 보존한다.

### 4.1 포털 화면 (UI/UX 세션) — 확정된 일
10-11 이번 작업의 **U1~U4·U7·U8은 구현·자동검증 완료, 사용자 캡처 시각 판정 대기**다. 아래 체크는 구현/자동시험 범위를 뜻하며 UIUX 최종 승인과 구분한다. 근거는 `verification/2026-10-11/approval-ui.md`·`flows-ui.md`·`portal-20261011.md`. 브라우저·MemoryRepo API 검증과 실제 LLM·설비 스택 완주를 구분한다.

기준: `UIUX.md`(사용자 지시: process-gpt-vue3 최신·Dify 모방, 핵심만, 폼은 섹션, 화면 말에서 내부 용어 빼기), `UIUX_PLAN.md`, `docs/ui-design-contract.md`, CLAUDE.md §4(카드 하나에 행동 1개, "학생이 10초 안에 할 일을 찾는가"). 캡처 없이 "비슷하게"로 끝내지 않는다 — 참고 화면과 우리 화면을 나란히. 코드: `it/portal/www/**`, 시험 `tests/js/*.js`(node vm에 실제 파일을 올려 그림) + `tests/test_c3_bc_review.py` · `test_live_leftovers_cards.py` · `test_capstone_g7_card.py`. A 화면을 일부러 바꿀 때는 고정본 `tests/fixtures/a_cards_before.json`도 근거와 함께 갱신한다. 화면 실물 캡처 `.evidence/a161-final/live/` · `live4/` · `a161-u1/`.

승인 단계 (출처 `F-keep.md` 4절 · `final-verify.md` 6절):
- [x] U1. 세 시나리오 승인 패널의 **[거절] + 사유**. 기존 reject-card API와 outputData 계약 유지, 1~2000자·권한 오류·서버 실패·입력 보존·중복제출 방지 시험. 사용자 시각 판정 대기
- [x] U2. **반려 결과 표시**. 결과·처리 기록·실시간 단계·업무 경보 직전 결과의 반려 표시, 실제 엔진 거절 뒤 설비/업무 효과 없음 확인. 사용자 시각 판정 대기
- [x] U3. **승인 지연 알림 표시**. A/B/C 실제 타이머 뒤 승인 작업이 열리고 화면에서 승인 가능. 알림만 들어오는 poll·입력 포커스 보존 확인. 사용자 시각 판정 대기
- [x] U4. 흐름 가져오기 부품 목록의 "조치 카드 승인 · 거절"과 분기 `approval`('승인'·'반려')를 실제 A/B/C 가져오기·검사·등록으로 확인. 사용자 시각 판정 대기
- [x] U5. 복구 지령 전후 표시 구현·자동검증. 팬/부하 이름으로 표시한다(`2026-10-12/portal-remaining.md`). 실제 A 재완주와 사용자 시각 판정은 별도.
- [x] U6. 감지기 상태에 따라 복원→준비→재주입 안내 구현·자동검증. 실제 A 거절/무응답 재완주는 별도.

종합 랩(개인 시나리오 — 「캡스톤」이라는 말은 쓰지 않는다) 때문에 필요한 화면 (출처 `K-capstone.md` 5.2 · 10절, `final-verify.md` 6절):
- [x] U7. **흐름 가져오기 시스템 부품 설정 칸** 구현. 메일·보고·대기·MCP 연결 값을 실제 UI→API→저장 매핑으로 대조했고 README를 화면 순서로 갱신했다. 가변 구조는 객체 입력 유지. 사용자 시각 판정 대기
- [x] U8. 새 가져오기 시작 조건 기본 미선택, 업무 경보·분기 값 한국어 표시, 무선택 거절 및 A/B/C 올바른 매핑 등록 시험. 사용자 시각 판정 대기
- [x] U9. PENDING 시스템 단계 닫기·단일 학생 흐름 삭제 UI/API 구현. 실제 실패→진행 중 삭제 409→닫기→단일 삭제·404·그래프 정리 확인(`student-codex-stdin` 18 checks).
- [ ] U10. 역할·입력칸·선택안·흐름·규칙 이름과 도구 결과 한글 표시를 구현·검증했다(`portal-remaining.md`). 최종 ontology/flows 식별자 검색 결과는 0이다. 실제 작성된 영문 정의명과 원문 도구 인용은 보존하며, 전체 국문화와 사용자 시각 판정은 남았다. 옛 내부 ID 표시 사례 전부가 현재 미구현이라는 뜻은 아니다.

이전부터 열린 것:
- [x] U11. B·C 카드·결과를 정비/구매 실제 업무 값으로 분리, 독립 브라우저·회귀 검증 완료. 실제 시나리오 재완주와 최종 시각 판정은 별도.
- [x] U12. 단계 없는 보상·검토 사건과 실행자·역할·사유·실패 표시 구현·자동검증. 검토를 실제 되돌림으로 표시하지 않는다.
- [x] U13. 재관측·스킬 전달·목록 조회·상태 확인·MCP 반환·실패 시도 화면을 15상태 × 1440/1024px로 검증했다. 파일 전달 실패를 ‘폴더에 있었지만 안 읽음’으로 설명하던 결함을 수정했고, 프롬프트 전달·전달 기록 누락·실행 회차별 기록을 구분한다. 도구 시작 기록은 읽기 요청이며 성공/활용으로 단정하지 않는다. 관련149개 통과, 수정 전7개 실패 증거 보존(`portal-remaining.md`). 합성 기록/독립 HTTP 오류 주입이며 운영 장애를 일으킨 검증은 아니다. 과거 null 오류의 원인을 전부 특정했다는 뜻도 아니다.
- [x] U14. 업무 규칙 표시·생성/변경/해제 구현, 실제 API·PG 저장 및 학생 동선 검증. 미등록 키는 원 키·오류를 보존한다.
- [x] U15. 최초 실행·사람 응답 재개·형식 교정에 한국어 진행 설명 지시를 적용했다. 결함16의 옛 회차 입력/현재 값 구분과 결함17의 근거 대조도 구현·검증했다. 실제 student-release의 진행 설명/결과/질문 답변, K4 보류 사유, Sol PM-02·PR-07 추출 진행 설명이 한국어임을 확인했다(`student-probe.md`). 도구 필드·반환값·자료 인용 원문은 그대로 보존한다.
- [ ] U16. 실제 화면은 `live-release` 46개·`ui-f21-final` 6개·`target-capture-final`의 기능 준비7개에 있다(`capture-review.md`). 시스템 구성·지도·조치 방법·원문 등록 이력·질의 결과 캡처를 교재 세션이 가져갈 수 있다. **사람 검토 후 매뉴얼 적재까지 완료한 화면**은 F3 완료 뒤 추가한다. 제안 생성 화면을 적재 완료로 소개하지 않는다.
최종 실라버스가 요구하는 화면 검증(기능 부재 판정이 아님; `verification/2026-10-11/portal-syllabus.md`):
- [x] U17. 이름·목표·역할·읽기 도구·업무 규칙 설정 → 실제 Codex 질문 → MCP 근거·호출 기록 검증 완료(`student-codex-stdin`, F16 후속 엄격 검증은 별도).
- [x] U18. 실제 학생 MCP 등록·연결 검사·read_rows 입력/반환·호출 기록·에이전트 연결 검증 완료(`student-codex-stdin`).
- [x] U19. 역할 선택→권한 부족403·입력 보존→담당자 승인200과 반려·서버 실패·재시도 동선을 실제 FastAPI/MemoryRepo 엔진 및 Chromium 화면으로 검증했다(`portal-remaining.md`, `u13-failure-review/approval-existing`·`review-complete`). 독립 노트북의 역할 선택·membership 검사는 로그인 인증이 아니며 외부 업무 실행은 double로 검증했다. 실라버스69행의 권한 제한 설명 범위이며 공용 서버 로그인 구축은 포함하지 않는다.
- [ ] U20. A·B·C 매핑 → 검사 → 등록·배포는 U7·U8과 공식 c3 배포 증거가 있다(94·95·102·104행). 현재 Windows에서 담당·대기·최종 결과까지 세 시나리오를 다시 완주하는 검증은 F3 사람 검토/적재와 업무 지식 보완 뒤 수행한다. 제공 mapping.json/API 보완 경로와 실제 업무 완주를 구분한다.
- [x] U21. 로컬 읽기 개인 흐름 등록 → 실제 Codex MCP 호출 → 결과 보고 DONE 확인(`student-codex-stdin`). Google 일정 등 외부 쓰기와 K3 완료를 뜻하지 않는다.

- 고치지 않는 것: 옛 기록의 이름 중복·출처 번호 중복은 저장된 값이 옛 값이라 보이는 것이다(코드는 고침). 화면에서 가리지 않는다.
- 화면 검사: `scripts/ui_capture_all_tabs.py`(콘솔 오류 0 · 가로 넘침 0은 전제일 뿐, 완료는 사용자가 캡처를 보고 판정).

### 4.2 기능·환경 잔여 (작고 급하지 않음)
- [x] F1. 현재 Codex 제품 경로는 run-local 등록 도구만 허용하고 ignore-user-config·apps=false·명시 MCP 구성을 유지한다. 실제 학생 읽기 도구 호출18 checks로 확인. 과거 Claude 개인 연결의live 재현은 현재 Sol 전용 지시 밖이며 Codex 필수 미완으로 남기지 않는다.
- [x] F2. 단일 학생 흐름 삭제와 durable projection 정리 구현. 실제 Neo4j 3개 시험 및 학생 live 삭제 뒤 ProcessVersion/Instance 없음 확인. 정상 ExecutionProjection fence는 보존한다. 과거 수업 잔재 수동 삭제는 하지 않았다.
- [ ] F3. HM-8·PM-02·PR-07 재추출→실제 사람 검토→적재 미완료. 첫 신규 정의2.3·기존2.2 불변. PR-07 구매 절차 범위 제품결함을 신규2.4로 보완했고 실제 Sol 재추출COMPLETED·SOP6/단계21을 확인했다. 이전2.3 제안도 보존한다. HM-8 실제 추출 제안 `activeworktree/.evidence/a161-c3/proposal-HM-8.json` 생성(8 procedures·18 warnings)만 확인. 모델 전환 전 완료된 Astra 산출물이다. PM-02 Astra 실행은 사용자 Sol 전용 지시로 공식 취소(`astra-cancel.json`)했고 Sol 6.1 PM-02 실제 제안 생성(절10·절차8·단계33)을 확인했으며 첫 PR-07 절차0은 범위 결함의 이력으로 보존하며 신규2.4는 절7·절차6·단계21·warnings14·rules7이다. 사람 검토 쟁점은 `manual-review-packet.md`에 연결한다. 제안을 reviewed/적재 완료로 표시하지 않는다.
- [x] F4. 독립 실제 Neo4j·HTTP 보호 검증16개 통과(8.98초). 개정/rollback의 판단 이력 보호·409 경로 확인, 시험 전 빈 그래프·시험 후 정리. `manual-http-neo4j.log/xml`.
- [x] F5. 제출 성공 전 EVAL, 성공 후 DEC로 전환하도록 수정·회귀 확인. 거절·후보 없음·연결 실패를 제출된 판단으로 표시하지 않는다.
- [x] F6. 설비 물리 명령에만 forecast 동의 재확인 적용, 업무 공급사·정책·순위·필수 사실 검사는 유지. 예측만 변경/공급사 변경/설비 명령 세 경로 회귀 확인. 실제 C 재완주는 별도.
- [x] F7. 독립 실제 PG에서 자산 필터·커서 404·비밀 저장·실패/감사 보존·work_rules 저장 3개 계약 시험 통과, 기존 PG4 순차 실행도 통과.
- [x] F8. 신뢰하는 작업/프로젝트/세션 문맥의 결과 파일만 읽도록 수정·회귀 확인. 위장 폴더·다른 작업·링크 탈출 거절, 원문 미보존 안내 유지.
- [x] F9. requirements-dev 의존 조합 수정, 새 venv 설치·pip check·전체 시험2275 통과로 재현. 독립 Docker 서비스 pin은 그대로다.
- [x] F10. 새 Supabase 프로젝트에서 42 SQL 파일·최종 20261010000051·seed 적용 확인. 기존 DB migration up와 구분한 신규 DB 검증이다.
- [x] F11. 보고서의 A정밀은 당시 기록임을 명시하고 10-10 B-OEM 추천 근거로 연결했다(`backend-remaining.md`).
- [ ] F12. 근거 부족으로 남긴 것: kg-seed 컨테이너 기동 16분 지연, 고아 문서 `b7379c5e…`(`live-final.md`), `scripts/ui_regression.py`는 전체판에서만(`c3-assembly.md` 6절)
- [ ] F13. 최신 밤샘 전수 지시로 학생 직접 작성 통합 검증·보고를 진행한다. 로컬 읽기 학생 동선 18개는 완료, A/B/C 실제 재완주와 최종 기능 보고는 진행 중이다.
- [x] F14. 차이 0.52/0.02는 수동 renderer fixture의 총점·성분 독립 상수 때문임을 확인했다. 실제 ranking.score 합산 계약을 시험했고 golden은 보존했다. 이 fixture를 계산 교육자료로 사용하지 않는다.

- [x] F15. Codex 최초·재개·교정에 전체 UTF-8 본문 stdin 전달 구현, 관련 86개 시험 및 실제 학생 동선 18개 통과. 이전 실패 기록은 보존한다.
- [x] F16. 질문 근거를 실제 서버/도구·전체 인자로 엄격 대조하고 폼별 교정 계약을 분리했다. 관련 179개 시험 통과. 이 후속 변경의 live 재검증은 별도로 추적한다(`backend-remaining.md`).
- [x] F17. 신규 매뉴얼 추출 2.3은 배포 provider를 따르며 기존 2.2 immutable 정의는 보존한다. 관련 시험은 F16 묶음에 포함. 실제 첫2.3 제안3건은 생성됐다. PR-07 신규2.4 실제 Sol 재추출은 완료했다. 사람 검토/적재는 F3에서 추적한다.
- [x] F18. 워커 시작 실패의 Fatal 꼬리 보존·알려진 비밀 표식 가림, live 검사기의 FAILED 즉시 미완 종료 구현. 관련 55개 시험 통과. 현재 B 재진단 결과는 별도다.
- [x] F19. Codex에 배정된 등록 스킬 본문·출처·SHA-256을 stdin으로 전달하고 snapshot/실제 제공파일/audit 해시 일치 검증. 관련75개 시험 통과, 실제 B에서 도구 실행까지 확인. 지식 부족 자율보류를 성공 결과로 바꾸지 않는다.
- [x] F20. 매뉴얼 추출 지시가 구매 SOP를 제외한 제품 범위 결함을 신규2.4로 수정. 기존2.3 정의 실제 불변·79개/확대247개 회귀·실제 Sol PR-07 COMPLETED/6SOP21단계 확인. 첫2.3 절차0 제안과 준비 전 GET 실패도 보존한다. 사람 검토·적재 완료와는 구분한다.
- [x] F21. 지식 지도 query에서 내부 투영/적재 기록5종 조회제외 수정·독립Neo4j/API45pass·3skip·실제 운영배포 확인. API1592→636, DB저장420/428/50/27/31 불변, Incident187·DecisionCase99·ManualSection18·KnowledgeSource7 유지. 최신6화면console0·폭0이며ontologySVG12는내부스크롤로접근가능함을실제검증했고기존작성명read_only1은보존한다.

최종 실라버스 대조만으로 새 기능 결함을 만들지는 않는다. F15는 U17·U21 실제 실행에서 재현된 결함이다. 남은 수업 운영 검증은 학생별 환경 또는 순차 배포, 외부 MCP 설치·권한·접속, Notion 쓰기 권한, SDD 실패 재현 입력, 수강생 실행 시간 리허설이다(통합 온라인 122·124행 및 다른 세 시트 대응 행; `verification/2026-10-11/portal-syllabus.md`).

### 4.3 종합 랩(개인 시나리오) 키트 잔여
설계 `verification/2026-10-09/capstone-lab.md`, 구현 기록 `2026-10-10/cap-g1g7.md` · `cap-g3g9.md` · `cap-kit.md` · `K-capstone.md`, 키트 `students/_template/`(T0~T8), 참조 흐름 `students/flows/`. T2·G1·G3·G9·T3·T4·G8·`validate --extra`·`close_agent_task`·손으로 그린 흐름 A 완주는 끝났다.
- [x] K1. 구성 꼬리표·필터·선택 내보내기 구현/검증. 최종 두 수정(메일 의존·URL query 비밀값) 포함 독립 PG17개·전체2275개 통과. 실제1440/1024 태그 저장→필터→export1flow·1agent·1MCP→제거 확인. 해당 캡처는 두 수정 전이며 최종process재빌드02:23:44 KST 확인과 구분한다. 인증 기반 공용 서버 격리는 아니다.
- [x] K2. 실제 bpmn.io A/B/C 및 생성 구성 왕복differences=[]에 더해 공식 T2 학생지식65nodes/107rels 적재→실제 질문9개 모두pass→학생 노드 상세 캡처 확인→공식ns wipe65개/remaining0까지 확인. 최신 target7개 기능 준비는 모두pass지만 health 요청abort로 전체exit1이므로 모든 캡처 검사 통과를 주장하지 않는다.
- [ ] K3. 예시 사례(회의 준비) 실제 1회: 구글 인증은 사용자 몫. 예시 흐름은 결과 경로 자리 3줄 때문에 가져오기가 거절된다(`students/_template/example_meeting/README.md`). 전원 수락 여부를 참/거짓으로 주지 않는 서버면 확인 단계를 바꿔야 한다
- [x] K4. 실제 Sol6.1이 read_rows로 필수 customer 미응답을 확인→self-deferred PENDING→공식 close→task/미도달 Report CANCELLED·instance COMPLETED/closed-by-human을7 checks 모두 PASS로 확인(`k4-live/summary.json`). 업무 보고/일정 확정은 실행하지 않았다. B 열린 incident의close409와 별도 개인 흐름 검증이다.

### 4.4 최종 실라버스 대조 결과 (2026-10-11)
최종 xlsx 네 시트를 대조했고 결과를 사용자에게 먼저 제시했다. 행별 근거는 `verification/2026-10-11/portal-syllabus.md`. 옛 `syllabus-gap.md`의 있음 29·부분 12·없음 22·다름 4·시스템 밖 13은 최종본 구현 현황으로 쓰지 않는다.
- 실제 포털 실습의 화면 검증은 **U17~U21**로 옮겼다. 메뉴 존재만으로 학생 실습 완료를 선언하지 않는다.
- **U7은 기존 종합 랩 요구로 유지**한다. 최종본 94·102행은 화면 밖 연결을 제공 mapping.json·API 절차로 보완한다고 명시하므로 설정 칸 부재를 최종 실라버스의 필수 UI 결함이라고 과장하지 않는다.
- **추가하지 않는 기능**: 예약 대기·시운전·입고 대기·미달·납기 초과·고장 원인 입력 버튼. B는 승인 후 오더·생산 공지·종료(102행), C는 발주·통지·시뮬레이션상 즉시 입고·재고 반영·종료(104행)여서 기존 결정과 맞는다. 옛 흐름·이름 변경 요구를 되살리지 않는다.
- VS Code 제작 실습(50~52·61~63·70~74·80~83·112~114행)은 새 포털 메뉴 근거가 아니다. 83행도 다중 출처 인수인계 실습이며 새 데이터 플랫폼 구축이 아니다. 옛 메뉴 활용 조사에서 새 기능을 추론하지 않는다.
- **Notion 학습노트 자체는 필수**(7·117행)이고 API/MCP 연동만 조건부다. 코치는 Markdown·텍스트 우선(63행), Notion 쓰기 권한 검증 시 MCP를 시연하며 미연결 환경은 직접 정리한다(117행). 교재·슬라이드 변경은 이번 범위에 없다.

### 4.5 사용자 결정 대기
- 작업 브랜치를 main에 합칠지
- 구조판 볼륨 `hyd-iot-edu_neo4j-data-c3` 삭제 여부(수업 문서 새 판 HM-8 · PM-02 · PR-07이 들어 있음 — 지우지 않는 쪽이 안전)
- 업무 감시(BUSINESS_MONITOR) 유지 여부(기본 끔)
- B·C 처리 건이 진행 중일 때 [초기화]를 거절할지(지금은 업무 값만 되돌리고 처리 건은 계속 간다 — `review-c3-bc.md` 4절)
- `students/flows/`에 연결 값 파일(`*.mapping.json`)을 같이 둔 것 — 포털에 시스템 부품 설정 칸이 생기면 뺄지. 흐름 이름은 `c3_flows.py` 그대로("냉각 긴급 대응" · "정기 정비" · "예비품 구매")라 시나리오 이름(긴급 대응 · 정기 점검 · 재고 보충)과 낱말이 다르다 — 확정안과 대조
- G6(K1)은 독립 노트북의 구성 꼬리표·필터·선택 export 구현으로 처리했다. 공용 서버 인증 격리는 별도 범위이며 현재 사용자 결정 대기로 중단하지 않는다
- 이전 이미지 꼬리표가 없다(`final-verify.md` 3절). 되돌릴 일이 있으면 `F-20261010-keep` 작업 트리에서 다시 빌드
- macOS에서의 작업보고 위치(CLAUDE.md §2의 `D:/work/작업보고/`는 이 PC에 없다)
- 끝난 작업 트리 정리: 10-11 한 번 했다(4.6절). 남은 것의 정리 시점

### 4.6 작업 트리 (10-11 정리 후)
- 지운 것: 9개 — `agent-a43cb88bab1647e3b` · `agent-afbc3de09be36a2d6` · `c3-fixes` · `c3-trace-ui` · `cap-g1g7` · `cap-g3g9` · `cap-kit` · `capstone-gaps` · `L-20261010-labs`(작업 트리만, 브랜치는 모두 남아 있다). 그 작업 트리에만 있던 무시 파일 `.evidence`는 루트 `.evidence/removed-worktrees/<이름>/`으로 복사했다(이 PC에만 있다).
- 컨테이너가 물어 지우지 않는 것: `merge-preview` · `agent-aed004354f1cd7a4c` · `agent-afd136e4b22934cb9`.
- 24시간 안에 수정된 파일이 있어 남긴 것: `F-20261010-keep`(합쳐짐) · `K-20261010-capstone`(합쳐짐) · `F-20261010-syllabus`(합쳐지지 않은 커밋 4개, 기록용). 하루 지나면 지워도 된다(`F-20261010-keep`은 스택과 무관).
- 합쳐지지 않은 커밋이 있는 브랜치: `F-20261010-syllabus` 4개(채택하지 않음; 기록 `F-syllabus.md`는 그 브랜치에만 있다), `L-20261010-labs` 1개(랩 자료 키트 `students/labs/`와 기록 `L-labs.md`는 그 브랜치에만 있다. 랩 자료는 만들지 않기로 했으므로 지금 쓰지 않는다). 브랜치는 지우지 않는다.

## 5. 지켜야 할 제약 (다시 정하지 않는다 — 근거 `DECISIONS.md` 112 외)

**시나리오와 흐름**
- 시나리오 3개: A 긴급 대응(HYD-01 쿨러 과열, 센서 경보로 시작) · B 정기 점검(HYD-02, CMMS) · C 재고 보충(HYD-03 씰 키트, ERP). 옛 이름 "B 정비 계획 · 펌프 효율 저하", "C 예비품 구매"는 쓰지 않는다.
- 세 시나리오 모두: 버튼 → 이벤트 → 처리 건 → 에이전트 추천 1개(지는 안은 실제 손익 이유로 짐) → 담당자 알림 → 승인 또는 거절 → 시스템 처리 → 자동 확인 → 결과 보고. 승인 전 에이전트는 조회·계산만.
- 승인하지 않으면 그 단계에서 대기(자동 취소·자동 거절 없음, 기한이 지나면 지연 알림만). 거절하면 처리 없이 반려로 닫힌다. 예약 대기·시운전·입고 대기·미달·납기 초과·수업용 원인 입력은 없다. 브랜치는 하나로 간다.
- B·C는 설비까지 가지 않는다(처리되면 끝). CMMS/ERP 화면은 만들지 않고 enterprise-sim을 쓴다. 업무 MCP는 정비(enterprise-maint 8196) · 구매(enterprise-purchase 8195).
- 결함 실험 버튼: [쿨러 열화 주입][쿨러 복구] | [정기 점검][초기화] | [재고 보충][초기화]. 끝나면 표시가 꺼지고 [초기화]로 다시 켜진다. A 열화 세기는 moderate(`scenario_buttons.A_SEVERITY`, high는 보호 정지가 먼저 온다). [쿨러 복구]는 팬·부하 지령도 평소 운전점(60 %·90 %)으로 되돌린다.
- TIME_SCALE=20이 기본. 실측(실제 LLM, 20배속): A 버튼 → 끝 215~218초, B 72~105초, C 75~84초, PR-07 추출 116~141초.

**원칙**
- 블랙박스 없음: 가져온 값·출처, 그래프 경로, 스킬, 도구 호출 입력/출력, 지는 안, 승인, 실행, 확인이 실시간과 처리 기록 화면에서 일반인 말로 읽힌다. 실패한 시도도 남긴다. 화면에 내부 id·영문을 내지 않는다.
- 근본 수정, 땜빵·폴백·해피패스 금지(실패는 시끄럽게). 우회 항목은 먼저 짚는다. 새 시험은 일부러 깨뜨려 잡히는지 확인한다. 서브에이전트 보고의 핵심 주장은 실물로 다시 확인한다. 점검표 `REVIEW_CHECKLIST.md`.
- UI/UX는 참고 화면(process-gpt-vue3 · Dify)을 그대로 모방한다. 구현 지시에는 ProcessGPT 모노레포 · ontology-studio 참고를 명시한다.
- 온톨로지 스키마 v2 고정(`it/neo4j/v2/schema.json` 2.6.0), 필요하면 기존 클래스 안에서 가산만. 학생 지식은 이름 공간(ns)으로 따로. 지식 그래프가 중심이고 RAG는 보조.
- 지식 적재는 사람 검토 기록이 있어야 한다. 문서 개정은 판단 이력(DecisionCase-CHOSE, Incident-DIAGNOSED_AS)을 지우지 않고 노드를 제자리에서 고친다. 그래프·데이터를 손으로 고쳐 증상을 지우지 않는다(화면에서 가리는 것도 같다).
- 망: IT/OT를 잇는 것은 DMZ 서비스뿐. process ↔ plant-sim은 `sim-net` 전용(`tests/test_compose_contract.py`가 지킴). MCP 비밀값은 `${SECRET:KEY}` 자리표시자. 판단 id: 제출 `DEC-`, 읽기 평가 `EVAL-`.
- 승인 카드 머리말: 예측(유온 등)은 설비를 바꾸는 안이거나 안마다 예측이 다를 때만. 업무 안은 그 안의 업무 값. A 화면은 고정본(`tests/fixtures/a_cards_before.json`)과 같아야 한다.
- 수업 구성(막마다 이론 → 설비 체험 → 랩업 등 옛 실라버스의 구조)은 이제 제약이 아니다. 실라버스는 사용자가 직접 쓰며 최종본이 기준이다(1절). 랩업을 Claude Code 바이브 코딩으로 한다는 방식과 그 계약 원문은 `archive/HANDOFF_실라버스교재.md` §7에 있다. 학생 AI는 키로 제공되니 계정 걱정·결정론 대비 경로를 설계하지 않는다.
- **최신 사용자 지시: 메인·하위 작업·워커 모두 Sol 6.1만 사용한다.** 기존 fable 금지와 opus/Astra 배정 규칙보다 이 최신 지시가 우선한다. `.env`는 키 이름만 읽는다. push · 데이터 볼륨 삭제 · 외부 게시는 사용자에게 묻는다. 커밋은 경로 지정(`git add .` · `-A` 금지).
- 여러 세션이 같이 일할 때: 작업 트리 하나씩(`git worktree add -b <이름> .claude/worktrees/<이름> claude/hyd-handoff-work-xziutz`), 레포 루트는 합치는 자리. 새 마이그레이션 번호는 052부터 이어서(미사용 053 · 054), 겹침 위험 파일은 `it/portal/www/index.html`(캐시 버전 줄) · `instances.py` · `instance_mode.py` · `service_parts.py` · `bpmn_import.py` · `procdb.py` · `caseRecord.js` · `approvalCard.js` · `instances.js`. 기록은 `verification/<날짜>/<이름>.md`에 쓰고 `NOW.md` · `HANDOFF.md` · `DECISIONS.md`는 합치는 세션만 고친다.

## 6. 문서 지도

| 무엇 | 어디 |
|---|---|
| 이 문서 | `docs/handoff/NOW.md` |
| 결정 경위·폐기된 판단 (고치지 않는다) | `docs/handoff/DECISIONS.md` |
| 현재 사실·규칙 원장 (§1 회의 원문 줄 번호, §2 확정 방향, §3 절대 규칙; 길다 — 필요한 절만) | `docs/handoff/HANDOFF.md` |
| 질문과 확정 답 | `docs/handoff/QA.md` |
| 점검표 | `docs/handoff/REVIEW_CHECKLIST.md` |
| 화면 작업(다른 세션이 쓴다) | `docs/handoff/UIUX.md` · `UIUX_PLAN.md` · `docs/ui-design-contract.md` |
| 코드가 가리키는 근거 원장 | `docs/handoff/REPO_GAP.md`(제품 ProcessGPT 대조, engine.py · instances.py 주석) · `docs/handoff/AUDIT.md`(회의·레포 대조, ingest.py 주석) |
| 검증 기록 (구조 불변) | `docs/handoff/verification/<날짜>/` — 현재 근거 `2026-10-12/overnight-status.md`·`student-cases.md`·`student-probe.md`·`capture-review.md`·`manual-review-packet.md`, 이전 근거 `2026-10-10/final-verify.md`(합친 코드 라이브 검증·회귀), `F-keep.md`(승인 단계·포털에 넘길 API), `K-capstone.md`(종합 랩), `cap-*.md`, `live-final.md`, `live-leftovers.md`, `manual-revision-fix.md`, `review-c3-bc.md`, `c-knowledge-gap.md`. **`syllabus-gap.md` · `syllabus-portal-underuse.md`와 10-09 이전 기록 안의 실라버스 언급은 옛 실라버스 기준이다** |
| 회의 원문·출처 | `docs/handoff/sources/` |
| 라이브 도구 · 고정 패키지 목록 | `docs/handoff/tools/live/` · `tools/venv-py312-freeze.txt` |
| 끝난 작업·옛 목표·옛 실라버스 보관 (한 줄 안내) | `docs/handoff/archive/README.md` |
| 기동 한 장 (Windows 기준) · 학생 안내 · 시나리오 설명 · 정의 작성 | `docs/RUNBOOK.md` · `student-guide.md` · `scenario-walkthrough.md` · `definition-authoring.md` · `docs/sessions/`(25회차) |
| 수업 준비물 | `students/_template/`(종합 랩 키트) · `students/flows/`(A·B·C 참조 흐름) |
| 증거 (gitignore, 이 PC에만) | 루트 `.evidence/` — 최종 `a164-final/`, 승인 단계 `a163-restore/`, 화면 `a161-final/` · `a161-u1/` · `a161-c3/`, 종합 랩 `k-capstone/`, 지운 작업 트리 것 `removed-worktrees/` |
| 실라버스 (유일한 기준) | `docs/교재/기준/피지컬AI_실라버스_최종본.xlsx` (통합반 1~4일차 교재는 같은 폴더의 `1~4일차 실라버스 확정안.xlsx`로 만들었고 내용이 같다) |
| 교재 | `docs/교재/`(`README.md` 안내, `기준/제작기준.md`, 기술사실표 둘, `통합반/01일차` … `04일차`, `통합반/샘플`). 덱 생성 도구 `.claude/skills/lecture-deck/` |
