# 지금 인계 — 병렬 세션 시작점 (2026-10-10)

`HANDOFF.md`는 길다(약 500 KB). **새 세션은 이 파일을 먼저 읽고, 자기 갈래가 가리키는 문서만 통독한다.**
새 세션 첫 대사: "`docs/handoff/NOW.md`를 읽고 <S | U | F | K> 갈래를 이어간다."
이 파일의 숫자 · 상태는 10-10 기준이다. 시작할 때 `git log -1` · `docker ps` · 시험 실행으로 다시 잰다(헌법 §2).

## 0. 현재 상태 (10-10 실측)

| 항목 | 값 |
|---|---|
| 브랜치 | `claude/hyd-handoff-work-xziutz`. A161 갈래 전부 합쳐짐. 시작할 때 `git log -1`로 이 파일이 든 커밋인지 본다 |
| 단위 시험 | 2076 통과 · 9 건너뜀 · 0 실패 (루트에서 `.venv/bin/python -m pytest -q -p no:cacheprovider`, 약 3분 30초) |
| 라이브 | A · B · C 버튼 완주 통과, C 추천 = SOP-PUR-11(B-OEM) — `verification/2026-10-10/live-final.md` 3 · 4차. 쿨러 회귀 40/40은 3차(8090310 빌드)에서만 돌렸다. 그 뒤 2190a84로 process · agent · dmn-mcp를 다시 빌드했고 **그 빌드로는 회귀를 돌리지 않았다** |
| 스택 | 떠 있음. compose 작업 폴더는 `.claude/worktrees/merge-preview`. 파일을 직접 물고 있는 컨테이너: portal ← `merge-preview`, grafana ← `agent-aed004354f1cd7a4c`, timescaledb · supabase studio ← `agent-afd136e4b22934cb9`. **이 세 작업 트리는 스택을 루트로 옮기기 전에 지우지 않는다.** process · agent · dmn-mcp 등 10-10에 다시 빌드한 서비스의 코드는 지금 브랜치와 같다(detector · redpanda · emqx 등 OT · 백본 쪽 이미지는 비교하지 않음) |
| 쉬는 상태 | 그래프 = 전체판, 흐름 = 기준 흐름(c3 흐름은 내려감), 워커 0, B · C 경보 표시 켜짐. **이 상태에서는 A · B · C 버튼 완주가 바로 되지 않는다**(2절 "버튼 완주 순서") |
| DB | Supabase 로컬(54322). 마이그레이션 45~48 · 50 · 51(049는 없음)은 `psql`로 직접 적용했다(`supabase_migrations` 장부는 44까지) |
| 지식 그래프 | 기본 볼륨 `hyd-iot-edu_neo4j-data` = 전체판. 구조판 + 수업 문서(HM-8 · PM-02 · PR-07 새 판)는 볼륨 `hyd-iot-edu_neo4j-data-c3` |
| 증거 | 화면 캡처 · 로그는 루트 `.evidence/`(gitignore — **이 PC에만 있다**). 최종 확인 `a161-final/live/` · `live4/`, U1 `a161-u1/`, C3 `a161-c3/` |

## 0.1 확정된 것 — 다시 정하지 않는다 (근거: DECISIONS 112, 검증 기록)

- **시나리오 3개**: A 긴급 대응(HYD-01 쿨러 과열, 센서 경보로 시작) · B 정기 점검(HYD-02, CMMS) · C 재고 보충(HYD-03 씰 키트, ERP). 옛 기록의 "B 정비 계획 · 펌프 효율 저하", "C 예비품 구매"는 옛 이름이다.
- **흐름**: 에이전트 추천 1개(지는 안은 실제 손익 이유로 짐) → 사람 승인 1회 → 시스템 처리 → 자동 확인 → 결과 보고. 승인 전 에이전트는 조회 · 계산만.
- **B · C는 설비까지 가지 않는다**(처리되면 끝). CMMS/ERP 화면은 만들지 않고 enterprise-sim을 쓴다.
- **결함 실험 버튼**: [쿨러 열화 주입][쿨러 복구] | [정기 점검][초기화] | [재고 보충][초기화]. 시작 상태가 곧 'HYD-02 정기 점검 도래' · 'HYD-03 재고 보충 필요'. 끝나면 표시가 꺼지고 [초기화]로 다시 켜진다. 업무 감시(BUSINESS_MONITOR)는 기본 끔.
- **A 열화 세기는 moderate**(`scenario_buttons.A_SEVERITY`): high는 20배속에서 에이전트 판단보다 보호 정지가 먼저 온다.
- **블랙박스 없음**: 가져온 값 · 출처, 그래프 경로, 스킬, 도구 호출 입력/출력, 지는 안, 승인, 실행, 확인이 실시간과 처리 기록 화면에서 일반인 말로 읽힌다. 실패한 시도의 호출 · 감사 기록도 남긴다. 화면에 내부 id · 영문을 내지 않는다.
- **온톨로지 스키마 v2는 고정**(`it/neo4j/v2/schema.json` 2.6.0). 꼭 필요하면 기존 클래스 안에서 가산만(예: 판단 입력 `in:supplier-fail-rate`). 학생 지식은 이름 공간(ns)으로 따로.
- **지식 적재는 사람 검토 기록이 있어야 한다.** 문서 개정은 판단 이력(DecisionCase-CHOSE, Incident-DIAGNOSED_AS)을 지우지 않고 남는 노드를 제자리에서 고친다. 그래프 · 데이터를 손으로 고쳐 증상을 지우지 않는다(화면에서 가리는 것도 같다).
- **업무 MCP는 둘**: 정비(enterprise-maint 8196) · 구매(enterprise-purchase 8195). B · C 판단 task는 각 시나리오 에이전트가 맡는다.
- **망**: IT/OT를 잇는 것은 DMZ 서비스뿐. process ↔ plant-sim은 시뮬레이터 전용 `sim-net`(`tests/test_compose_contract.py`가 지킴).
- **MCP 비밀값**은 `${SECRET:KEY}` 자리표시자(값은 `mcp_secrets` 표, 실행 직전 채움, 기록에서 가림).
- **판단 id**: 제출한 판단 `DEC-`, 읽기 평가 `EVAL-`.
- **승인 카드 머리말**: 예측(유온 등)은 설비를 바꾸는 안이거나 안마다 예측이 다를 때만. 업무 안은 그 안의 업무 값. A 화면은 고정본(`tests/fixtures/a_cards_before.json`)과 같아야 한다.
- **TIME_SCALE=20**이 기본. 실측(실제 LLM, 20배속, live-final 3 · 4차): A 버튼 → 끝 215~218초(에이전트 94초 · 재관측 60초), B 72~105초, C 75~84초. PR-07 추출 116~141초. 에이전트 시간은 회차마다 다르다.
- **실라버스 고정 값**(`docs/실라버스.md`, 커밋 0a4cee2): 합계 통합 영상 2640 · 통합 오프 2520 · 실전 영상 1920 · 실전 오프 2280분, 행은 20분 이상 · 5분 단위, 막마다 이론 → 포털(A 전부 → B → C) → 랩업, 하위 주제 없음, A:B:C = 4:3:3, Notion 60분, ProcessGPT 시연 40/30분.

## 1. 병렬 규칙 — 세션끼리 부딪히지 않게

1. **세션마다 작업 트리 하나.** `git worktree add -b <갈래>-<날짜>-<이름> .claude/worktrees/<갈래>-<날짜>-<이름> claude/hyd-handoff-work-xziutz`. 이미 작업 트리 · 브랜치가 여럿 있으니(`git worktree list`) 이름이 겹치지 않게 한다. 레포 루트에서 직접 고치지 않는다(루트는 합치는 자리).
2. **라이브 스택은 하나뿐이다.** 쓰기 전에 `<루트>/.evidence/LIVE_LOCK`을 본다(작업 트리가 아니라 루트 절대 경로). 있으면 기다린다. 없으면 "갈래-이름 · 시작 시각 · 하는 일 · 예상 끝"을 한 줄 쓰고 시작하고, 2절의 복원을 끝낸 뒤 지운다.
   2시간 넘은 잠금은 `pgrep -fl 'worker.main|scenario_|probe_|run_final|record_shot|press.py|c3_ingest|c3_flows|playwright'`가 비어 있을 때만 사용자에게 묻고 푼다.
   - 잠금이 필요한 일: `docker compose build/up/restart`, 워커, 버튼 누르기(쓰기 요청 전부), 회귀, 추출 · 적재, 흐름 배포, 그래프 볼륨 바꾸기.
   - 잠금 없이 되는 일: GET 조회, 코드, 단위 시험, node vm 렌더 시험, 문서, 슬라이드.
   - 지금 상태 보기: `docker inspect hyd-iot-edu-neo4j-1 --format '{{range .Mounts}}{{.Name}} {{end}}'`(`neo4j-data` = 전체판, `-c3` = 구조판) · `curl -s localhost:8080/api/scenario/status`(running이 null인지) · `lsof -iTCP:8097 -sTCP:LISTEN`.
   - 검사기가 도는 동안 compose 금지(CLAUDE.md §3).
3. **파일 영역**(3절 표)을 넘으면 먼저 자기 갈래 파일에 적고 최소로 고친다. 겹치기 쉬운 파일: `it/portal/www/index.html`(캐시 버전 줄), `instances.py` · `instance_mode.py` · `service_parts.py` · `bpmn_import.py` · `procdb.py`, `caseRecord.js` · `approvalCard.js` · `instances.js`.
4. **기록은 갈래 파일에만 쓴다**: `docs/handoff/verification/<날짜>/<갈래>-<이름>.md`(작업 시작 직후 만들고 절마다 덧붙임). `HANDOFF.md` · `NOW.md` · `DECISIONS.md` · `USER_UTTERANCES.md` · `QA.md`는 **합치는 세션만** 고친다 — CLAUDE.md §2의 "§9 먼저 갱신"은 병렬 동안 갈래 파일로 대신한다. 사용자 발화 원문 · 결정은 갈래 파일 맨 위 "합칠 때 옮길 것" 절에 적어 둔다.
5. **새 마이그레이션 번호**를 미리 나눈다: F = 052, K = 053, U = 054(더 필요하면 055부터 갈래 파일에 적고 쓴다).
6. 합칠 때: 자기 갈래를 작업 브랜치에 `--no-ff`로 합치고 전체 시험 1회. `index.html` 충돌은 양쪽 스크립트를 모두 남기고 바뀐 파일의 캐시 버전만 새로 붙인다. 합친 세션이 갈래 파일의 "합칠 때 옮길 것"을 HANDOFF §9 A161 · 이 파일 3절에 반영한다.
7. 커밋은 경로 지정(`git add .` 금지). push · 데이터 볼륨 삭제 · 외부 게시는 사용자에게 묻는다. `.env`는 키 이름만 읽는다.
   **fable 모델은 절대 쓰지 않는다**(사용자 지시 10-10 — 메인 세션 · 서브에이전트 · 워커 모두. 공용 헌법 §7의 "복잡한 코드는 fable"보다 이 지시가 우선한다. 서브에이전트는 `opus`로 지정한다).
8. 원칙: 근본 수정 · 땜빵 금지 · 폴백 금지(실패는 시끄럽게) · 해피패스 금지 · 클린코드 · 블랙박스 없음 · 참고 화면 모방 — 점검표 `REVIEW_CHECKLIST.md`. 새 시험은 일부러 깨뜨려 잡히는지 확인한다. 서브에이전트 보고의 핵심 주장은 실물로 다시 확인한다.

## 2. 환경 (이 PC, macOS · colima — CLAUDE.md §5 표에는 macOS가 없다. 이 절이 기준)

- 파이썬: 레포 루트 `.venv`(3.12). 작업 트리에서는 `<루트 절대 경로>/.venv/bin/python`을 쓴다. 다시 만들 때는 고정 목록으로: `uv venv --python 3.12 .venv && uv pip sync --python .venv/bin/python docs/handoff/tools/venv-py312-freeze.txt`(이 목록으로 2076 통과 실측). `host_libpq.sh`는 필요 없다.
  `requirements-dev.txt`만 깔면 `fastmcp`가 없어 시험 2건이 실패하고, MCP 서비스 요구 파일을 그 위에 얹으면 starlette가 올라가 다른 시험이 깨진다(10-10 실측) — 3.3 열린 일.
- compose: `export COMPOSE_PROFILES=ot,backbone,detect,knowledge,agent,enterprise,process,cliagents` 뒤 `docker compose -p hyd-iot-edu …`. `.env`에도 `COMPOSE_PROFILES`가 있지만 `cliagents`가 빠져 있다 — export 없이 돌리면 enterprise-mcp · dmn-mcp가 빠진다. zsh는 `$변수`에 든 서비스 목록을 나누지 않으니 서비스 이름을 직접 적는다.
- `.env`: 루트에 있다(10-10에 스택이 쓰던 것으로 맞춤, 이전 것은 `.evidence/a161-final/root-env-before-20261010.bak`). 작업 트리에서 compose를 돌리려면 그 폴더에 복사한다(값은 열지 않는다). `PLANT_SIM_URL`은 두지 않는다(기본 `http://plant-sim:8000`, sim-net).
- 포트(10-10 `docker ps` 실측): process API 8080 · 포털 8088 · agent 8091 · dmn-mcp 8198 · enterprise-mcp 8199(정비 8196 · 구매 8195) · effects-mcp 8197 · neo4j 7474/7687 · Supabase DB 54322 · 메일함(Inbucket) 화면 54324 · SMTP 54325 · 워커 8097.
- 워커: 루트에서는 `bash scripts/run_worker_host.sh`, 작업 트리에서는 `PYTHON=<루트 절대 경로>/.venv/bin/python bash scripts/run_worker_host.sh`(스크립트가 자기 폴더의 `.venv`만 찾는다. 그 작업 트리의 워커 코드가 돈다). 워커는 1개만. 멈춤: `pkill -f worker.main` 뒤 포트 확인.
  워커는 Claude Code 구독으로 돈다 — 세션 한도에 걸리면 `RunFailed`. 리셋 시각을 기록하고 기다린다. 실패한 에이전트 task는 `/cancel`이 아니라 `POST /api/todolist/{wid}/close`(포털 '단계 닫기')로 끝낸다.
- **내 화면 보기(U 갈래)**: 포털 컨테이너(8088)는 건드리지 않는다 — 모든 세션이 같이 본다. 내 작업 트리에서 `<루트>/.venv/bin/python -m http.server 87NN --bind 127.0.0.1 -d it/portal/www`로 띄워 `http://127.0.0.1:87NN`에서 본다(API는 같은 스택 8080, CORS 허용 — `review-portal.md` 3절 선례. 10-10에 직접 띄워 보지는 않았다). 조회만이면 잠금 불필요, 버튼을 누르면 잠금. 끝나면 서버를 끄고 포트를 확인한다.
- 스택 서비스를 내 작업 트리 코드로 바꿔야 할 때(잠금 필요): 그 폴더에 `.env`를 두고 **바뀐 서비스만** `docker compose -p hyd-iot-edu build <서비스…> && docker compose -p hyd-iot-edu up -d --no-deps <서비스…>`. 끝나면 `docker inspect hyd-iot-edu-process-1 --format '{{.State.StartedAt}} {{.RestartCount}}'`. 갈래 파일에 "어느 서비스를 어느 커밋으로 올렸는지" 적는다.
  스택 전체를 레포 루트 기준으로 옮기는 일(전체 build + up)은 하지 않았다.
- **버튼 완주 순서**(잠금 필요, `live-final.md` 3-1~3-8):
  ① 그래프를 구조판으로: `docker compose -p hyd-iot-edu -f compose.yaml -f docs/handoff/tools/live/neo4j-c3.override.yaml up -d --no-deps neo4j`
  ② `.venv/bin/python scripts/c3_flows.py deploy` ③ 워커 1개 ④ 한 번에 한 건(A → 끝나면 [쿨러 복구], B, C)
  ⑤ 복원: `c3_flows.py deploy-reset <이름>` → 워커 멈춤 → 그래프 원래 볼륨(override 없이 `up -d --no-deps neo4j`) → 설비 `POST localhost:8000/api/reset` → B · C [초기화] → RUNNING 처리 건 0 확인 → 잠금 지움.
  회귀 검사기의 `/api/reset`은 완주가 만든 업무 행(WO · PR · GR)을 보관 표로 옮긴다(처리 건 기록은 남는다).
- 라이브 구동 · 캡처 도구(검토 전 도구 — 읽고 쓴다): `docs/handoff/tools/live/` — `run_final.py A|B|C <출력 폴더>`(버튼 완주 + 캡처), `record_shot.py`(처리 기록 전체 캡처), `press.py`, `render_approval.js`, `snapdiff.py`(PR-07 전용, 문서 id 고정). playwright 패키지는 루트 `.venv`에 있다(브라우저가 없다고 하면 `.venv/bin/python -m playwright install chromium`).
- 컴퓨터가 잠들면 실행이 끊긴다: 긴 실행 전 `caffeinate -dimsu -t 28800 &`.
- `rtk` 훅이 git · grep 출력을 줄인다. 원문이 필요하면 `rtk proxy <명령>`.

## 3. 갈래

| 갈래 | 시작 문서 | 주 파일 영역 | 라이브 스택 |
|---|---|---|---|
| S 이론 슬라이드 | `HANDOFF_실라버스교재.md` §10 | `docs/`(덱 MD · pptx), 코드 없음 | 불필요 |
| U UI/UX | 3.2 | `it/portal/www/**`, `tests/js/**` | 내 화면은 정적 서버로, 버튼은 잠금 |
| F 기능 · 남은 결함 | 3.3 | `it/process` · `it/agent` · `it/agent-worker` · `it/dmn-mcp` · `it/neo4j` · `it/supabase/migrations` · `compose.yaml` · `scripts` · `tests` | 검증 때 잠금 |
| K 캡스톤(전체 과정 랩업) | 3.4 | `students/_template/**`, G6 | 예시 실행 때 잠금 |

겹침 정리: **G6은 K가 한다**(`instances.py` · `procdb.py` · `instances.js`의 G6 부분) — F · U는 그동안 그 부분을 읽기만 한다. **캡스톤 화면의 브라우저 확인은 K가 한다** — U는 K가 결함을 적어 주면 고친다. `compose.yaml` · `it/neo4j/v2/**` · `it/dmn-mcp/**`는 F 영역이고 다른 갈래는 고치기 전에 자기 갈래 파일에 적는다.

### 3.1 S 이론 슬라이드
`HANDOFF_실라버스교재.md` **§10만** 따른다(§1~§9는 10-08 기록). 사용자가 실라버스를 주면 시작한다. 그 전에는 스킬 통독과 시작할 때 물을 것 정리만 한다.
시작할 때 한 번에 물을 것: ① 시간당 장수(25~30장은 제안, 미확정) ② 산출물 자리(제안: `docs/슬라이드/<막>/` — 덱 MD + pptx) ③ "배울 내용 소개 → 본문 → 실습 → 퀴즈" 틀에서 실습 장을 비울지 자리만 둘지(이론만 만들기로 함) ④ 이미 있다는 Notion pptx의 위치(레포에는 pptx가 없다).
lecture-deck 스킬은 레포 밖(`/Users/uengine/agent-provider/안치윤/.claude/skills/lecture-deck`)이라 이 PC에서만 쓸 수 있다.

### 3.2 U UI/UX
- 기준: `UIUX.md`(사용자 지시 — process-gpt-vue3 최신 · Dify 모방, 핵심만, 폼은 섹션, 화면 말에서 내부 용어 빼기), `UIUX_PLAN.md`, `docs/ui-design-contract.md`, CLAUDE.md §4(카드 하나에 행동 1개, "학생이 10초 안에 할 일을 찾는가"). 캡처 없이 "비슷하게"로 끝내지 않는다 — 참고 화면과 우리 화면을 나란히.
- 지금 화면의 실물: `.evidence/a161-final/live/` · `live4/`(A · B · C 승인 카드 · 처리 기록, 1440 · 390), `.evidence/a161-u1/`. 이전 보고 `verification/2026-10-09/u1-uiux.md` · `review-portal.md`.
- 코드: 처리 기록 `caseRecord.js` · `caseRecord.css` · `plainWords.js`(일반인 말 사전). 승인 카드 `approvalCard.js`(머리말 규칙 `forecastDecides` · `ownValues`). 시험 `tests/js/*.js`(node vm에 실제 파일을 올려 그림) + `tests/test_c3_bc_review.py` · `test_live_leftovers_cards.py` · `test_capstone_g7_card.py`. A 화면을 일부러 바꿀 때는 고정본(`tests/fixtures/a_cards_before.json`)도 근거와 함께 갱신한다.
- 열린 것:
  - [ ] U2 시나리오 B · C 화면 다듬기(지금은 A와 같은 틀에 B · C 값이 들어간 상태. 구매 · 정비 담당 눈높이로 카드 · 결과 보고를 본다)
  - [ ] `EFFECT_COMPENSATION` · `EFFECT_REVIEW` 이벤트가 처리 기록 화면에 안 보임(단계 없는 events — `review-c3-bc.md` 4절)
  - [ ] 화면에서 본 적 없는 표시: 재관측 실패(`reobsSeries.error`) · 스킬을 작업 폴더에 못 넣음(`skills[].written`)(`review-backend.md` 4-4 · 10절), 처리 건 목록 읽기 실패, `app.js`의 표시 확인 중/못 읽음 · 기준점 문구(`review-c3-bc.md` 3절 ②), `MCP_RESULT_VALUES` · 실패 시도(`attempt_failed`) 줄(`cap-g3g9.md` 5절)
  - [ ] 에이전트 화면에 업무 규칙(work_rules) 표시 없음(`cap-g3g9.md` 5절 ②)
  - [ ] U1 남은 것: 에이전트 혼잣말이 영어(워커 지시 문제 — F와 조율), 결함 16 · 17(`u1-uiux.md` 7절)
  - 고치지 않는 것: 옛 기록의 이름 중복 · 출처 번호 중복은 저장된 값이 옛 값이라 보이는 것이다(코드는 고침). 화면에서 지우지 않는다.

### 3.3 F 기능 · 남은 결함
- 기준: `HANDOFF.md` §9 A161, `DECISIONS.md` 112, 검증 기록 `verification/2026-10-10/*.md` · `2026-10-09/review-backend.md`.
- 열린 것:
  - [ ] 지금 스택(2190a84 빌드)에서 회귀 1회: 쿨러 `scripts/scenario_instance_test.py --worker`(약 6분), pump-fan `scripts/scenario_pump_fan_test.py --worker --reassess-held`(마지막 통과는 각각 8090310 빌드 · 10-10 새벽 빌드)
  - [ ] HM-8 · PR-07을 추출 지시 2.2로 다시 추출 · 검토 · 적재(출처 번호 중복이 사라지는지) — `scripts/c3_ingest.py`(extract → 사람 검토 기록 → commit), 구조판 볼륨, 워커 필요
  - [ ] 개정 적재 라이브 미확인: 새 판에서 빠지는 노드에 판단 이력이 있을 때의 409 문구, 배치 되돌리기(rollback)가 같은 검사를 받는지(`manual-revision-fix.md` 5절). 추출 실패가 FAILED로 보이는지는 다음 실패 때 확인
  - [ ] 제출되지 않은 판단(가드레일 거절 · 후보 없음)의 `DEC-` id가 404(`live-leftovers.md` 5)
  - [ ] 발주 카드 · A 작업지시 카드에 `window: 즉시 (지금 정지하고 시행)`(`cards.py:114 option_window` — process가 읽는 값이라 영향 확인 필요, `live-leftovers.md` 끝의 보고만 한 것)
  - [ ] C 승인 순간 재확인이 설비 예측 문맥을 대조 — 그사이 설비 값이 바뀌면 발주 승인이 막힐 수 있음(코드만 읽음, 실측 없음 — 같은 절)
  - [ ] B · C 처리 건이 진행 중일 때 [초기화]를 누르면 업무 값만 되돌리고 처리 건은 계속 간다 — 거절할지는 사용자 결정(`review-c3-bc.md` 4절)
  - [ ] Pg 경로 미검증: `list_instances(asset=…)` SQL, 이벤트 커서 페이지(모르는 커서 404) · 비밀 값 저장소(`review-backend.md` 5-1 · 10절), 실패 시도 기록 · 감사 기록 보존, `agent_authoring`의 work_rules insert/update
  - [ ] 워커 `saved_path`가 `tool-results` 이름 폴더 아래면 어느 파일이든 읽는 잔여 위험(`review-backend.md` 3-5, 고치지 않음)
  - [ ] 시험 환경 재현: `requirements-dev.txt`가 시험에 필요한 `fastmcp`를 담지 않고 서비스 요구 파일끼리 공용 패키지 버전이 맞지 않는다. CLAUDE.md §5의 설치 명령만으로는 전체 시험이 통과하지 않는다(실패 2건: `test_a144_mcp_worker` · `test_capstone_g5_table_reader`)
  - [ ] `supabase_migrations` 장부가 44에서 멈춤 — 새 DB에서 `supabase start`가 51까지 올리는지 확인
  - [ ] `docs/보고서/2026-10-09_HYD_시나리오_3개.md:221`이 "C 추천이 A정밀"로 남아 있다 — 지금은 B-OEM(`live-final.md` 3-5)
  - [ ] 근거 부족으로 남긴 것: kg-seed 컨테이너 기동 16분 지연, 고아 문서 `b7379c5e…`(`live-final.md`), `scripts/ui_regression.py`는 전체판에서만(`c3-assembly.md` 6절)
  - [ ] 이전부터 열린 것: `HANDOFF.md` §9의 A160 · A159 `[ ]`(core 회귀 pump-fan 1건, 기능 보고서 갱신 등) — 지금도 유효한지 먼저 판정
- 흐름 배포 · 되돌리기: `scripts/c3_flows.py check|deploy|export DIR|deploy-reset BY`(모르는 명령은 종료 2).

### 3.4 K 캡스톤(전체 과정 랩업)
- 설계 `verification/2026-10-09/capstone-lab.md`, 구현 기록 `verification/2026-10-10/cap-g1g7.md` · `cap-g3g9.md` · `cap-kit.md`, 키트 `students/_template/`(T0 · T1 · T3~T8).
- 열린 것:
  - [ ] G6 학생 것 격리(노트북별 운영이면 "내 사례" 꼬리표 · 거르기 · 내보내기 — 설계 5.2)
  - [ ] T2(적재 · 되돌리기 스크립트 틀)가 `students/_template/`에 없음
  - [ ] G1 · G3 · G9 라이브 확인(한 번도 돌리지 않음): 승인 패널(`instances.js renderApprovePanel`) · 흐름 가져오기 설정 칸(`flows.js`)은 문법 검사만 했다. 절차는 `cap-g1g7.md` 7절, `cap-g3g9.md` "라이브에서 확인할 절차"
  - [ ] 키트 미검증(`review-scripts-kit.md` 7절, `cap-kit.md` 4절): 학생 노드가 있는 지식 지도 화면, G8 흐름 투영 실제 적재 · 재적재, T3 DDL 실제 실행, T4 서버 기동 → 포털 MCP 등록 → 에이전트 호출, `validate --extra`를 실제 그래프에, bpmn.io에서 T7 · T8 열기
  - [ ] 예시 사례(회의 준비) 실제 1회: 구글 인증은 사용자 몫. 예시 흐름은 결과 경로 자리 3줄 때문에 지금 가져오기가 거절된다(강사가 서버를 고른 뒤 채움 — `students/_template/example_meeting/README.md`). 전원 수락 여부를 참/거짓으로 주지 않는 서버면 확인 단계를 바꿔야 한다

## 4. 사용자 결정 대기

- 구조판 볼륨 `hyd-iot-edu_neo4j-data-c3` 삭제 여부(지금 수업 문서 새 판이 들어 있음 — 지우지 않는 쪽이 안전)
- 업무 감시(BUSINESS_MONITOR) 유지 여부
- B · C 진행 중 [초기화]를 거절할지
- 슬라이드: 3.1의 물을 것 네 가지
- 작업 브랜치를 main에 합칠지
- 끝난 작업 트리(`.claude/worktrees/*`) 정리 — 스택을 루트 기준으로 옮긴 뒤에만. 증거(`.evidence`)는 루트로 복사해 두었다(10-10)
- macOS에서의 작업보고 위치(CLAUDE.md §2의 `D:/work/작업보고/`는 이 PC에 없다)
