# A10 에이전트 시험 실행 · 비교 (2026-10-08 밤, worktree `a10-agentcompare`)

범위: 메인 `TODO.md` 확정 TODO §0 · §1 **A10** · 실험 E3(스킬) · E4(도구 구성) · §2 랩업 L16 · L17 · L19 · L24 행.
비유 한 줄: **같은 시험지(입력 스냅숏)를 두 학생(에이전트 A · B)에게 풀게 하고 답안지를 나란히 놓는 것**. 시험지가 같으니 답이 다르면 학생 차이다.

## 1. 결론
1. 고정 시나리오(쿨러 HYD-01 · 펌프 HYD-02 · 팬 HYD-03) + 에이전트 A · B를 **판단 단계만** 시험 실행한다: 원인 진단 → (스킬 절차의 보조 도구) → 판단 사실 수집 → 후보 · 규정 · 순위. 처리 건(bpm_proc_inst) · 작업(todolist) · 이벤트 · 판단 제출(`/api/decisions`) · 사건(`/api/incidents`) · 설비 명령을 만들지 않는다.
2. **같은 입력 보장 = 입력 스냅숏(record/replay)**. 세계를 읽는 호출은 처음 한 번만 실제 원천에서 읽어 스냅숏에 남기고, B와 재실행은 그 값을 그대로 쓴다(읽기 실패도 남김). 같은 스냅숏 + 같은 설정 → 같은 결과 지문(fingerprint). 다른 스냅숏끼리 비교하면 화면이 "입력이 다름"을 따로 알린다(규칙 · 지식 전 · 후).
3. 설정 차이가 결과를 바꾸는 곳(코드에 정답 없음): **도구 구성** — enterprise가 없으면 업무 DB 출처 사실을 받지 못해 그 값을 검사하는 규정이 '미확인'이 되고 1순위가 바뀔 수 있다(E4), hyd-dmn이 없으면 판단 자체를 못 한다(사유와 함께 멈춤). **스킬** — 본문에 적힌 도구를 적힌 순서대로 보조 조회로 부르고 결과를 근거 인용에 더한다(E3). 스킬이 제출 · 쓰기 도구를 가리키면 '막힘'으로 기록된다.
4. 경로 (b) 실제 Claude Code 워커는 **구현하지 않았다** — 기존 todolist/워커 구조로는 처리 건 없이 돌 수 없다(§4). 서버 내장 판단 (a)만.
5. A4 점수 함수는 이 기준 커밋(71c0a78)에 없다 → 점수 칸은 넣지 않았다(합친 뒤 A4가 있으면 비교 응답에 붙일 자리: `agent_trials.compare`).

## 2. 구조와 데이터 리니지
```
포털 compare.js ──POST /api/agent-trials/run {scenario, a:{agent, variant}, b:{…}, snapshot | reuse_latest}──▶ process
  process agent_trials.py
    ① 설정 읽기  users(is_agent, agent_type='agent').tools · skills + 스킬 저장소(tenant_skills) + tenants.mcp 서버 이름   (읽기만)
    ② 변형 적용  B에서 도구 · 스킬 '빼 보기'만(저장 안 함, 원래대로 = 변형 없음). 설정에 없는 이름은 400
    ③ 스냅숏     agent_trial_snapshots 새로 만들기 | 지정 | 이 시나리오 직전 것
    ④ A 판단     ──POST agent /api/agent/trial {scenario, agent, entries, tenant_servers}──▶ agent trial.py
                   Snapshot.read(key): 있으면 재생(source=snapshot), 없으면 LiveWorld로 읽고 기록(source=live, 실패도 기록)
                   diagnose(T1 · 증거 SQL · 원인 순위) → 스킬 보조 도구 → gather_facts(+도구 구성 경계) → cards.evaluate(후보 · 규정 · 순위) → guardrail.check_cards
                 ◀── {trial, added}  → snapshot.entries에 '처음 기록 우선'으로 덧붙임
    ⑤ B 판단     같은 스냅숏(A가 읽은 값 + 새로 읽은 값)으로 ④ 반복
    ⑥ 저장       agent_trials (setting · variant · status · fingerprint · result) ×2
    ⑦ 비교       compare(): 도구 호출 LCS 정렬 · 원인 · 1순위 · 순위 · 사실 · 규정 · 인용 · 규칙 집합 차이
  ◀── {scenario, snapshot, a, b, diff}
포털: 요약(접지 않음) → A · B 카드(도구 · 스킬 · 원인 · 1순위 · 근거 요지) → 도구 호출 정렬표(한쪽만=노랑, 결과 다름=파랑) → 순위표 → 접기(사실 · 인용 · 규정 · 원본)
전 · 후: GET /api/agent-trials → 두 개 고르기 → GET /api/agent-trials/diff?a=&b=
```
- 시험 기록 한 건이 담는 것: 도구 호출 순서(단계 · 서버 · 도구 · 입력 · 상태 · 결과 요약 · 인용 · 누가 시켰나[엔진/스킬 이름] · 원천/재생), 원인 후보와 증거, 판단 사실(출처 · 받지 못함 표시), 후보 규칙 발화, 규정 판정(제외 · 감점 · 경고), 순위 · 점수 항목, 1순위, 설명, 근거 인용 목록, 판단 규칙 id 집합, 상태 · 사유, 결과 지문.
- 실패 · 분기: 판단 도구 없음 → `NO_ENGINE_TOOL`, 근거 부족 → `WITHHELD`(사실 · 판단 안 함), 원천 읽기 실패 → `FAILED`(사유, 스냅숏에도 남아 B도 같은 실패), 가능한 조치 없음 → `NO_FEASIBLE_OPTION`, 가드레일 → `REJECTED_BY_GUARDRAIL`. agent 서비스 연결 실패 → 503 "판단 서비스(agent)에 연결하지 못했습니다", instance 실행 서비스 없음 → 503.

## 3. 에이전트 설정이 결과에 닿는 규칙 (범용, 정답 미내장)
| 설정 | 시험 실행에서의 뜻 | 실제 워커와의 차이 |
|---|---|---|
| 도구 `hyd-dmn` | 원인 진단 · 사실 수집 · 판단 엔진 · 시계열 조회 | 같음(워커도 이 서버로 진단 · 판단) |
| 도구 `enterprise` | 업무 DB 출처(sys:mes · sys:erp · sys:qms · sys:cmms · 물리 열 binding) 사실을 받는 경계. 없으면 그 사실은 "업무 DB 도구(enterprise)가 없어 이 값을 받지 못했습니다" | **다름**: 워커의 hyd-dmn `gather_facts`는 엔진 안에서 업무 DB를 읽으므로 enterprise 서버가 없어도 값이 온다. 시험 실행은 도구 구성을 '읽을 수 있는 원천의 경계'로 정의해 그 차이를 결정론으로 보여 준다(E4) |
| 도구 `neo4j` | 스킬의 ```cypher 블록 읽기 질의(쓰기 키워드는 거절, READ 세션) | 워커는 LLM이 직접 Cypher를 만든다 |
| 테넌트에 없는 서버 | 없는 것으로 봄(`tool_notes`에 사유) | 워커 `bridge.select_servers`(it/agent-worker/worker/bridge.py:52)와 같은 규칙 |
| 스킬 | 본문에서 도구 이름을 등장 순서대로(``` `이름` ```, `mcp__서버__도구`, 밑줄 있는 이름) 보조 조회로 부름. 인자는 시나리오 · 진단 결과 · ```sql/```cypher 블록(`{asset}` 치환). 본문이 다른 설비 · 패턴만 가리키면 따르지 않음(사유). 본문 없음 → 사유 | 워커는 SKILL.md를 작업 폴더에 두고 LLM이 해석(U2). 시험 실행은 같은 본문을 결정론으로 읽는다 |
| 스킬이 가리킨 제출 · 쓰기 · 미지원 도구 | `submit_decision` · `write_neo4j_cypher` · `forecast_actions` · 업무 DB 자유 SQL 등 → '막힘'과 사유 | 워커는 hyd-dmn submit_decision을 실제로 부를 수 있다 |

- 스킬 절차는 원인 진단 뒤 · 사실 수집 앞에 끼운다(원인 · 고장 유형이 인자로 필요). 스킬은 이름순으로 따른다.
- 스킬은 보조 조회와 인용을 바꾼다. 같은 엔진 입력이면 후보 · 순위는 같다 — 순위를 바꾸는 것은 규칙 · 사실(도구 구성 · 지식 전 · 후)이다. 이것도 화면에서 확인된다(시험 `test_skill_difference_shows_up_as_call_order_and_citation_difference_E3`).

## 4. 경로 (b) 실제 Claude Code 워커를 쓰지 않은 이유 (파일:줄)
- 워커는 `fetch_pending_task` → `claim_process_workitems(…,'worker')`로만 작업을 집는다(it/process/procsvc/procdb.py:665-669). 이 함수는 **RUNNING 상태의 부모 처리 건이 있는 행만** 고른다: `where i.status='RUNNING' and not i.is_deleted`(it/supabase/migrations/20261007000021_claim_count_reclaim_only.sql:26), `join parents p using(proc_inst_id)`(:31). 처리 건 없이 todolist 행만 만들면 집히지 않는다.
- 결과 저장은 행을 SUBMITTED로 바꿔 엔진이 다음 단계로 진행시킨다(procdb.py:679).
- 테넌트 MCP의 hyd-dmn에는 쓰기 도구 `submit_decision`이 있다(it/dmn-mcp/dmn_mcp/server.py:103). 워커는 서버 단위로 붙인다(bridge.py:52).
- 따라서 "기존 todolist/워커 구조"로는 처리 건 · 판단 제출 0을 지킬 수 없다. 새 claim 경로 · 새 큐를 만드는 것은 범위(가볍게 · 기존 구조)를 넘고, U2가 같은 워커 파일(runner.py · context.py)을 바꾸는 중이라 충돌한다.

## 5. 원본 대응 (process-gpt-vue3 @ refs-A, 데이터로만 읽음)
| HYD | 원본 파일:줄 | 차이 |
|---|---|---|
| 같은 입력을 재생해 전 · 후 비교 | `src/components/pr/PrVerification.vue:45-47`(병합 전 검증은 저장된 분기 판정으로 재생), `:103-105`(base → head 판정), `:302-310`(사례별 전 · 후 칩) | 원본은 PR(정의 · 스킬 변경) 단위 검증, HYD는 에이전트 설정 단위. 재생 대상은 원천 읽기 결과(스냅숏) |
| A · B 나란히 + 차이 강조 | `src/components/ui/ProcessFeedbackCompare.vue:39-61`(전 · 후 두 뷰어), `:69`(차이 범례) | 원본은 BPMN 두 장, HYD는 도구 호출 순서 정렬표 · 순위표 |
| 시험 실행(실제 반영 없음) | `src/components/business-rules/BusinessRuleDefinitions.vue:121,454-455`(규칙 테스트 실행기) | 원본은 규칙 하나, HYD는 에이전트 한 명의 판단 단계 전체 |
| 에이전트 설정 원천 | `src/components/api/ProcessGPTBackend.ts:4250-4287`(users 행의 tools · skills — U2 조사 인용) | HYD는 포털에서 읽기만, 수정은 랩업 |

## 6. 바꾼 파일
- 새: `it/agent/agentsvc/trial.py`(판단 · 스냅숏 · 스킬 절차 · 지문), `it/process/procsvc/agent_trials.py`(설정 읽기 · 변형 · 저장 · 비교 · API), `it/supabase/migrations/20261008000040_agent_trials.sql`, `it/portal/www/compare.js`(`window.hydCompare.mount(el)`), `it/portal/www/compare.css`, `tests/test_agent_trial.py`, `tests/test_agent_trials_api.py`.
- 최소 줄: `it/agent/agentsvc/main.py`(+19: `TrialReq` · `POST /api/agent/trial`), `it/process/procsvc/main.py`(+4: `agent_trials.register`), `it/portal/www/index.html`(+9: 메뉴 버튼 1 · `view-compare` 섹션 · css · js). U7 셸이 들어오면 `#compareView`에 `hydCompare.mount`만 부르면 된다(compare.js 끝의 자체 연결은 `#compareView`와 `data-tab="compare"` 버튼이 있을 때만 동작).
- API: `GET /api/agent-trials/options` · `POST /api/agent-trials/run` · `GET /api/agent-trials` · `GET /api/agent-trials/diff?a=&b=` · `GET /api/agent-trials/{id}`(process), `POST /api/agent/trial`(agent).

## 7. 시험 결과
- 전체 `pytest -q`: **1317 passed**(기준 1284 + 새 33, Supabase 표 시험 포함 — 임시 로컬 PostgreSQL 16에 migration 000001 + 000040을 적용해 `HYD_TRIAL_PG_DSN`으로 실행, 시험 뒤 클러스터 정지 · 삭제). 환경변수가 없으면 그 1건은 건너뛴다.
- 완료 기준 대응: 처리 건 · 작업 · 이벤트 · 알림 0(`test_compare_runs_both_on_one_snapshot_and_creates_no_instance_task_or_decision`, PG 시험의 행 수 전후 동일, 시험 모듈에 제출 경로 없음), 같은 입력 · 설정 → 같은 지문 · 원천 재조회 0(`test_same_snapshot_and_same_setting_*`, `test_a_failed_read_is_part_of_the_frozen_input`), 설정 차이 → 차이 표시(E4 1순위 SOP-2 → SOP-1 · 사실 3개 '받지 못함', E3 호출 순서 · 인용 차이), 입력이 다르면 따로 표시.
- 일부러 깨뜨리기(변이 3개, 모두 잡힘): 스냅숏 무시 → 5건 실패, 도구 구성 경계 제거 → 3건 실패, 스킬 절차 무시 → 6건 실패. 되돌린 뒤 통과.
- 화면: 정적 포털 + 시험용 process 경로(가짜 원천 · 진짜 판단 엔진)로 Playwright 캡처, 페이지 오류 0. `.evidence/a10/`(worktree, gitignore) `2-result.png` · `3-variant.png` · `5-result-element.png` · `6-history-diff.png` · `4-mobile.png`, 화면 문자 `view.txt`. 화면의 `skill:mix`·`cause:other` 등은 시험 고정값 id라 names.json에 없어 그대로 보인 것(실제 온톨로지 id는 이름으로 바뀜).
- `node --check it/portal/www/compare.js` 통과.

## 8. 합친 뒤 통합 검증(메인)에서 할 것
1. migration 000040 적용 → process · agent 재기동(compose, 검사기 미실행 중) → 포털 "에이전트 시험 비교".
2. 쿨러 경보를 넣은 상태에서 A=B=기본 에이전트 → "결과 같음"(같은 지문). B에서 업무 DB 빼기 → 사실 '받지 못함' · 규정 차이 확인. 펌프 · 팬도 1회씩. 설비가 시나리오 상태가 아니면 "근거 부족 · 보류"가 정상 결과다.
3. 처리 건 목록 · `/api/decisions` · 감사 기록이 시험 전후 같은지 확인.
4. 랩업 대응: L16 스킬(본문에 도구 이름 · ```sql) 추가 → 목록에 나타나고 B로 비교(E3). L17 규칙 추가 → "지난 시험과 비교"에서 전 · 후(규칙 차이 · 후보 차이). L19 통합 에이전트 → 기본 에이전트와 1순위 · 근거 비교. L24 펌프 판단 추가 → 쿨러 직전 시험과 비교해 1순위가 그대로인지.

## 9. 사용자가 스스로 판정할 체크 질문
- 두 에이전트를 같은 설정으로 돌렸을 때 화면이 "결과 같음"이라고 하는가? (아니면 같은 입력 보장이 깨진 것)
- 업무 DB 도구를 뺀 B에서 '받지 못함'으로 표시된 사실이 실제로 업무 시스템(MES · ERP · QMS · CMMS) 출처인가?
- 스킬을 붙인 B의 도구 호출 순서가 스킬 본문에 적은 순서와 같은가?
- 시험 실행 뒤 처리 건 목록과 판단 결과 목록에 새 항목이 생기지 않았는가?
