# NOW — 새 세션은 이 문서 하나로 시작한다 (2026-10-11 정리)

이 문서를 새로 썼다. 이전 판(갈래 L·F·K·U·S 병렬 서술)과 지난 경위는 git 이력과 `archive/`에 있다.
숫자·상태는 10-11 기준이다. 시작할 때 `git log -1` · `docker ps` · 단위 시험으로 다시 잰다.

## 1. 한눈에 보기

| 항목 | 값 |
|---|---|
| 브랜치 | `claude/hyd-handoff-work-xziutz` **하나**. 다른 갈래(A161, `K-20261010-capstone`, `F-20261010-keep`)는 모두 합쳐졌다. 인계 문서 정리까지 원격에 올렸다(10-11). 이후 커밋은 사용자가 맡긴 범위 안에서 push하고, main에 합치는 것은 사용자에게 묻는다 |
| 기능 | **끝났다.** 남은 것은 포털 화면(UI/UX)뿐이다(4.1절). UI/UX는 다른 세션이 일괄로 한다 |
| 단위 시험 | 2149 통과 · 9 건너뜀 · 0 실패 (10-11 00:55). 명령 `.venv/bin/python -m pytest -q -p no:cacheprovider`(레포 루트, 약 3분 30초) |
| 실제 스택 검증 | 합친 코드(`4e5f535` 빌드)로 A·B·C 각각 승인·거절, A·C 무응답, A 승인 뒤 [쿨러 복구]→바로 다시 주입, 단계 닫기, 손으로 그린 흐름으로 A 완주 — 모두 통과. 회귀 쿨러 40/40 · pump-fan 43/43 |
| 한계 | 위 검증은 **포털 화면이 아니라 process API로** 눌렀다. 포털에는 [거절] 버튼이 아직 없다. 화면에서 어떻게 보이는지는 본 적이 없다 |
| 실라버스 | 기준은 `/Users/uengine/agent-provider/안치윤/1~4일차 실라버스 확정안.xlsx`(통합반 1~4일차)뿐이다. 5일차 이후는 사용자가 확정해 보내는 대로 추가된다 |
| 교재(슬라이드) | 레포 밖 `/Users/uengine/agent-provider/안치윤/슬라이드/`에서 만든다. 기준 `슬라이드/제작기준.md`(6절이 최신). 통합반 1일차 `슬라이드/통합반/01일차_v3/`(71장, 그림체 컨펌), 2·3·4일차 제작 중. 랩 자료는 만들지 않는다 |
| 쉬는 상태(스택) | 그래프 = 전체판, 흐름 = 기준 흐름, 워커 0, 잠금 없음, RUNNING 0, B·C 표시 켜짐(10-11 03:07 실측). 이 상태에서 A·B·C 완주는 3절 순서로 준비해야 한다. A는 [쿨러 복구]만으로 연달아 돌릴 수 있다 |

## 2. 스택 올리고 확인하는 방법

환경: 이 PC는 macOS + colima. 전체 기동 절차는 `docs/RUNBOOK.md`(Windows/Git Bash 기준)이고, macOS 차이는 아래다.

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

### 4.1 포털 화면 (UI/UX 세션) — 확정된 일
기준: `UIUX.md`(사용자 지시: process-gpt-vue3 최신·Dify 모방, 핵심만, 폼은 섹션, 화면 말에서 내부 용어 빼기), `UIUX_PLAN.md`, `docs/ui-design-contract.md`, CLAUDE.md §4(카드 하나에 행동 1개, "학생이 10초 안에 할 일을 찾는가"). 캡처 없이 "비슷하게"로 끝내지 않는다 — 참고 화면과 우리 화면을 나란히. 코드: `it/portal/www/**`, 시험 `tests/js/*.js`(node vm에 실제 파일을 올려 그림) + `tests/test_c3_bc_review.py` · `test_live_leftovers_cards.py` · `test_capstone_g7_card.py`. A 화면을 일부러 바꿀 때는 고정본 `tests/fixtures/a_cards_before.json`도 근거와 함께 갱신한다. 화면 실물 캡처 `.evidence/a161-final/live/` · `live4/` · `a161-u1/`.

승인 단계 (출처 `F-keep.md` 4절 · `final-verify.md` 6절):
- [ ] U1. 세 시나리오 승인 패널에 **[거절] + 사유**(`instances.js renderSelectPanel`). `POST /api/todolist/{workitem_id}/reject-card` body `{decision, by, role, reason}`; 그 단계가 거절을 받는지는 활동 `outputData`에 `approval`이 있는지로 안다(없으면 [거절] 숨김). 계약 전문 `F-keep.md` 4절
- [ ] U2. **반려 결과 표시**: 결과 보고 `outcome: "반려"` · `level: "rejected"`, 처리 기록 줄 `APPROVAL_REJECTED`, 끝 이벤트 `E_rejected`, 사건 `REJECTED_BY_OPERATOR`, `/api/scenario/status last.outcome`
- [ ] U3. **승인 지연 알림 표시**: B·C에도 A와 같은 「승인 지연」 타이머와 알림 task(`outcome: "승인 지연"`, `level: "info"`). 알림 뒤에도 승인 task는 열려 있다
- [ ] U4. 흐름 가져오기 부품 목록의 "조치 카드 승인 · 거절"과 분기 조건 값 `approval`('승인'·'반려') 선택 확인
- [ ] U5. **[쿨러 복구] 기록의 지령 변화 표시**: 누름 기록 `data.setpoints {before, after}`("팬 지령 100 % → 60 %"처럼 일반인 말로)
- [ ] U6. 거절/무응답 뒤 A를 다시 누를 때의 안내(감지기 단계를 보고 누르라는 안내가 있는지)

종합 랩(개인 시나리오 — 「캡스톤」이라는 말은 쓰지 않는다) 때문에 필요한 화면 (출처 `K-capstone.md` 5.2 · 10절, `final-verify.md` 6절):
- [ ] U7. **흐름 가져오기 화면에 시스템 부품 설정 칸**(승인 뒤 MCP 호출 · 시간 대기 · 결과 보고; `it/portal/www/flows.js` taskRow 180~206행 근방). 칸이 없어 학생이 포털만으로 흐름을 등록하지 못한다 — 가장 큰 막힘. 칸이 생기면 `students/flows/README.md` 마지막 절을 화면 순서로 바꾼다
- [ ] U8. 흐름 가져오기 직후 시작 조건에 감지기 경보 셋이 모두 체크돼 있음, 시작 조건 칸 `PM_DUE` · `SPARE_BELOW_MIN`이 영문 그대로, 분기 조건이 `recovered == True`로 보임 — 화면 표기를 바꾸면 `tests/test_student_reference_flows.py`의 안내문 대조가 알려 준다
- [ ] U9. K가 본 결함: 시스템 task가 PENDING으로 멈춘 학생 처리 건을 닫는 길 · 학생 흐름 하나만 지우는 길이 화면에 없음
- [ ] U10. 내부 id·영문 노출: 학생이 만든 역할이 `role:demo-organizer`로 보임(승인 패널 머리 칩·역할 고르기·결과 보고), 처리 기록의 시작 문장이 흐름 id, 시작 값·승인 값이 값 이름 그대로("request id", "approval 승인"), 승인 단계에 고른 안이 안 보임(결과 보고에만), 그래프 도구 결과의 한글이 `\uXXXX`, 지식 지도 규칙 카드가 id로 보임

이전부터 열린 것:
- [ ] U11. 시나리오 B·C 화면 다듬기(지금은 A와 같은 틀에 B·C 값이 들어간 상태. 구매·정비 담당 눈높이로 카드·결과 보고) — `HANDOFF.md:273`
- [ ] U12. `EFFECT_COMPENSATION` · `EFFECT_REVIEW` 이벤트가 처리 기록 화면에 안 보임(단계 없는 events — `review-c3-bc.md` 4절)
- [ ] U13. 화면에서 본 적 없는 표시: 재관측 실패(`reobsSeries.error`), 스킬을 작업 폴더에 못 넣음(`skills[].written`)(`2026-10-09/review-backend.md` 4-4 · 10절), 처리 건 목록 읽기 실패, `app.js`의 표시 확인 중/못 읽음·기준점 문구(`review-c3-bc.md` 3절), `MCP_RESULT_VALUES` · 실패 시도(`attempt_failed`) 줄(`cap-g3g9.md` 5절)
- [ ] U14. 에이전트 화면에 업무 규칙(work_rules) 표시 없음(`cap-g3g9.md` 5절 ②)
- [ ] U15. U1 남은 것: 에이전트 혼잣말이 영어(워커 지시 문제 — 4.2의 F와 조율), 결함 16·17(`2026-10-09/u1-uiux.md` 7절)
- [ ] U16. 슬라이드에 넣을 실제 화면 캡처가 없다: 지금 포털의 시스템 구성 · 지식 지도 · 조치 방법 · 매뉴얼을 넣은 뒤의 지식 관리 · 질의 결과. 화면을 고친 뒤 1440 폭으로 찍어 `.evidence`에 두면 슬라이드 쪽이 가져간다
- 고치지 않는 것: 옛 기록의 이름 중복·출처 번호 중복은 저장된 값이 옛 값이라 보이는 것이다(코드는 고침). 화면에서 가리지 않는다.
- 화면 검사: `scripts/ui_capture_all_tabs.py`(콘솔 오류 0 · 가로 넘침 0은 전제일 뿐, 완료는 사용자가 캡처를 보고 판정).

### 4.2 기능·환경 잔여 (작고 급하지 않음)
- [ ] F1. 호스트 워커의 Claude Code가 강사 개인 claude.ai 연결 도구를 에이전트에게 보인다(허용 목록이 거절은 함) — `it/agent-worker/worker/runner.py:187-194`, `K-capstone.md` 4절
- [ ] F2. 정의를 지운 뒤 실행 그래프의 정의 투영을 정리하는 길이 제품에 없다(시험 흐름을 지울 때마다 손으로 좁힌 SQL — `final-verify.md` 7절, `K-capstone.md` 5.3·11절). 구조판 볼륨에 시험 흐름 `my_cooling@1` · `fv_close_probe@1` 투영이 남아 있다
- [ ] F3. HM-8 · PR-07을 추출 지시 2.2로 다시 추출·검토·적재(출처 번호 중복이 사라지는지) — `scripts/c3_ingest.py`(extract → 사람 검토 기록 → commit), 구조판 볼륨, 워커 필요
- [ ] F4. 개정 적재 라이브 미확인: 새 판에서 빠지는 노드에 판단 이력이 있을 때의 409 문구, 배치 되돌리기(rollback)가 같은 검사를 받는지(`manual-revision-fix.md` 5절)
- [ ] F5. 제출되지 않은 판단(가드레일 거절 · 후보 없음)의 `DEC-` id가 404(`live-leftovers.md` 5)
- [ ] F6. C 승인 순간 재확인이 설비 예측 문맥을 대조 — 그사이 설비 값이 바뀌면 발주 승인이 막힐 수 있음(코드만 읽음, 실측 없음 — `F-keep.md`가 아니라 `live-leftovers.md`)
- [ ] F7. Pg 경로 미검증: `list_instances(asset=…)` SQL, 이벤트 커서 페이지(모르는 커서 404), 비밀 값 저장소(`review-backend.md` 5-1 · 10절), 실패 시도 기록·감사 기록 보존, `agent_authoring`의 work_rules insert/update
- [ ] F8. 워커 `saved_path`가 `tool-results` 이름 폴더 아래면 어느 파일이든 읽는 잔여 위험(`review-backend.md` 3-5, 고치지 않음)
- [ ] F9. 시험 환경 재현: `requirements-dev.txt`에 `fastmcp`가 없고 서비스 요구 파일끼리 공용 패키지 버전이 맞지 않는다. CLAUDE.md §5 명령만으로는 전체 시험이 통과하지 않는다(실패 2건: `test_a144_mcp_worker` · `test_capstone_g5_table_reader`). 위 freeze 목록으로는 통과
- [ ] F10. `supabase_migrations` 장부가 44에서 멈춤 — 새 DB에서 `supabase start`가 51까지 올리는지 확인
- [ ] F11. `docs/보고서/2026-10-09_HYD_시나리오_3개.md:221`이 "C 추천이 A정밀"로 남아 있다 — 지금은 B-OEM(`live-final.md` 3-5)
- [ ] F12. 근거 부족으로 남긴 것: kg-seed 컨테이너 기동 16분 지연, 고아 문서 `b7379c5e…`(`live-final.md`), `scripts/ui_regression.py`는 전체판에서만(`c3-assembly.md` 6절)
- [ ] F13. 옛 `HANDOFF.md` §9의 `[ ]`(10-08 기록) 가운데 아직 유효한지 판정이 필요한 것: 기능 통합 검증 V(학생 동선으로 시나리오를 포털 직접 만들기로 끝까지, `HANDOFF.md:312`), 기능 보고서 갱신(`:313`). 사용자가 다시 요구한 기록은 못 찾았다 — 필요할 때만 한다

### 4.3 종합 랩(개인 시나리오) 키트 잔여
설계 `verification/2026-10-09/capstone-lab.md`, 구현 기록 `2026-10-10/cap-g1g7.md` · `cap-g3g9.md` · `cap-kit.md` · `K-capstone.md`, 키트 `students/_template/`(T0~T8), 참조 흐름 `students/flows/`. T2·G1·G3·G9·T3·T4·G8·`validate --extra`·`close_agent_task`·손으로 그린 흐름 A 완주는 끝났다.
- [ ] K1. G6 학생 것 격리(노트북별 운영이면 "내 사례" 꼬리표·거르기·내보내기 — 설계 5.2). 꼬리표를 누가 어디서 붙이는지 · 값 모양이 설계에 없어 구현하지 않았다(사용자 결정 필요)
- [ ] K2. 지식 지도에서 학생 항목을 눌렀을 때의 상세, demo.bpmn.io 사이트에 직접 올려 보기(로컬 bpmn-js로만 열어 봄 — `students/flows`도 같다), 구성 내보내기 → 되돌리기 → 가져오기
- [ ] K3. 예시 사례(회의 준비) 실제 1회: 구글 인증은 사용자 몫. 예시 흐름은 결과 경로 자리 3줄 때문에 가져오기가 거절된다(`students/_template/example_meeting/README.md`). 전원 수락 여부를 참/거짓으로 주지 않는 서버면 확인 단계를 바꿔야 한다
- [ ] K4. `close_agent_task`의 PENDING 쪽(에이전트가 스스로 보류한 단계를 닫기)은 단위 시험만(`tests/test_close_agent_task.py`), 라이브 미검증

### 4.4 확정 전이라 보류 (옛 실라버스에서 나온 항목 — 본 목록에 섞지 않는다)
5일차 이후 실라버스가 확정되기 전까지 아래는 「정해진 것」이 아니다. 확정안이 오면 그때 다시 대조한다.
- 옛 실라버스(`archive/실라버스.md` 등)와 `피지컬ai_실라버스_최종.xlsx`(이제 없음)에서 나온 「미구현」 판정 전부. 근거 사본 `verification/2026-10-10/syllabus-gap.md`(통합반 80행: 있음 29 · 부분 12 · 없음 22 · 다름 4 · 시스템 밖 13) — 옛 실라버스 기준이다.
- 9~10일차 포털 실습 행이 요구한다고 적힌 화면: 흐름 가져오기·작업 매핑·흐름 검사 결과·가져오기 설정 칸(대기·시운전·입고 부품의 `until` · `criteria` · 타이머). 시스템 부품 설정 칸(U7)은 실라버스와 무관하게 종합 랩에 필요해서 4.1에 두었다.
- 실라버스를 덜 쓰는 포털 메뉴 조사(`verification/2026-10-10/syllabus-portal-underuse.md`): 시험 비교 · 판단 채점 · 조치 판단 규칙 · 손익·What-if · 데이터 연결 · 오일 분석 입력이 학생 손으로 어디까지 되는지 화면에서 확인한다는 제안 — 실라버스가 정해진 뒤 한다.
- 폐기된 것(사용자 결정): 예약 대기·시운전·입고 대기·조치 미달·시운전 미달·납기 초과·수업용 원인 입력 버튼, 시나리오 이름 변경, 정비·구매의 실라버스 모양 흐름(`F-20261010-syllabus` 브랜치, 기록용). 옛 실라버스의 8~10일차 문구는 원래 결정보다 나간 것이었다.
- 슬라이드 쪽 열린 질문(실라버스 8·9행의 빈 노트 틀만 vs 노션 덱의 데이터베이스·템플릿·링크 게시, 노션 덱 본문에 남은 다른 강의 문구)은 슬라이드 세션 몫이다.

### 4.5 사용자 결정 대기
- 작업 브랜치를 main에 합칠지
- 구조판 볼륨 `hyd-iot-edu_neo4j-data-c3` 삭제 여부(수업 문서 새 판 HM-8 · PM-02 · PR-07이 들어 있음 — 지우지 않는 쪽이 안전)
- 업무 감시(BUSINESS_MONITOR) 유지 여부(기본 끔)
- B·C 처리 건이 진행 중일 때 [초기화]를 거절할지(지금은 업무 값만 되돌리고 처리 건은 계속 간다 — `review-c3-bc.md` 4절)
- `students/flows/`에 연결 값 파일(`*.mapping.json`)을 같이 둔 것 — 포털에 시스템 부품 설정 칸이 생기면 뺄지. 흐름 이름은 `c3_flows.py` 그대로("냉각 긴급 대응" · "정기 정비" · "예비품 구매")라 시나리오 이름(긴급 대응 · 정기 점검 · 재고 보충)과 낱말이 다르다 — 확정안과 대조
- G6(K1) 설계 결정
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
- 수업 구성(막마다 이론 → 설비 체험 → 랩업 등 옛 실라버스의 구조)은 이제 제약이 아니다. 실라버스는 사용자가 직접 쓰며 확정안(1~4일차)이 기준이다(4.4절). 랩업을 Claude Code 바이브 코딩으로 한다는 방식과 그 계약 원문은 `archive/HANDOFF_실라버스교재.md` §7에 있다. 학생 AI는 키로 제공되니 계정 걱정·결정론 대비 경로를 설계하지 않는다.
- **fable 모델은 쓰지 않는다**(메인 · 서브에이전트 · 워커 모두, 서브에이전트는 `opus`). `.env`는 키 이름만 읽는다. push · 데이터 볼륨 삭제 · 외부 게시는 사용자에게 묻는다. 커밋은 경로 지정(`git add .` · `-A` 금지).
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
| 검증 기록 (구조 불변) | `docs/handoff/verification/<날짜>/` — 최신 근거 `2026-10-10/final-verify.md`(합친 코드 라이브 검증·회귀), `F-keep.md`(승인 단계·포털에 넘길 API), `K-capstone.md`(종합 랩), `cap-*.md`, `live-final.md`, `live-leftovers.md`, `manual-revision-fix.md`, `review-c3-bc.md`, `c-knowledge-gap.md`. **`syllabus-gap.md` · `syllabus-portal-underuse.md`와 10-09 이전 기록 안의 실라버스 언급은 옛 실라버스 기준이다** |
| 회의 원문·출처 | `docs/handoff/sources/` |
| 라이브 도구 · 고정 패키지 목록 | `docs/handoff/tools/live/` · `tools/venv-py312-freeze.txt` |
| 끝난 작업·옛 목표·옛 실라버스 보관 (한 줄 안내) | `docs/handoff/archive/README.md` |
| 기동 한 장 (Windows 기준) · 학생 안내 · 시나리오 설명 · 정의 작성 | `docs/RUNBOOK.md` · `student-guide.md` · `scenario-walkthrough.md` · `definition-authoring.md` · `docs/sessions/`(25회차) |
| 수업 준비물 | `students/_template/`(종합 랩 키트) · `students/flows/`(A·B·C 참조 흐름) |
| 증거 (gitignore, 이 PC에만) | 루트 `.evidence/` — 최종 `a164-final/`, 승인 단계 `a163-restore/`, 화면 `a161-final/` · `a161-u1/` · `a161-c3/`, 종합 랩 `k-capstone/`, 지운 작업 트리 것 `removed-worktrees/` |
| 실라버스 (유일한 기준) | `/Users/uengine/agent-provider/안치윤/1~4일차 실라버스 확정안.xlsx` (레포 밖) |
| 교재 | `/Users/uengine/agent-provider/안치윤/슬라이드/`(제작기준.md, 통합반/01일차_v3 …) (레포 밖) |
