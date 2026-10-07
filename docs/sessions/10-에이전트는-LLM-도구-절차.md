# 10. 에이전트는 LLM + 도구 + 절차 (3부, 180분: 설명 70 / 실습 80 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
쿨러 경보 하나에 대해 서버 안 에이전트가 남긴 실행 기록(트레이스)을 단계별로 읽고, 각 단계가 어느 도구로 어느 출처(그래프 · 시계열 DB · 기업 시스템)를 읽었는지 표로 만든다.
끝나면 "단계 · 도구 · 출처 · 읽은 값" 표 1장이 남는다.

## 준비
- 1회차처럼 쿨러 경보 1건을 낸다(포털 결함 시뮬레이션 → HYD-01 쿨러 열화 주입).
- 포털 **이상 확인 · 조치** 탭, 에이전트 API http://127.0.0.1:8091/docs.
- 파일: `it/agent/agentsvc/main.py` `pipeline()`(45~120행), `decide.py`(사실 수집), `tools/mcp_kg.py`·`mcp_tsdb.py`·`mcp_ent.py`·`mcp_prom.py`.

## 실행 장면
1. [화면] 이상 확인 · 조치 → HYD-01 도식 클릭 → **에이전트 트레이스** → [관찰] 단계가 순서대로: `alert_policy → freshness → t1_causes → evidence (→ evidence_assessment) → rank → t2_skills → card → guardrail → cards (→ submit)` → [확인] 단계 수를 센다(커리큘럼의 "8단계"는 예전 표현이고 현재 코드는 9~11단계. 인스턴스 모드에서는 `cards`가 "읽기 평가 결과 … 여기서는 제출/실행하지 않습니다"로 끝나고 `submit`은 레거시 경로에서만 보인다).
2. [명령] `curl -s 127.0.0.1:8091/api/agent/runs | python -m json.tool | head -60` → 최근 run id → `curl -s 127.0.0.1:8091/api/agent/runs/<id>` → [관찰] 단계마다 `note`(예 "mcp-tsdb: Evidence SQL 템플릿 실행 (tag_1s)") → [확인] 표의 "도구·출처" 열을 채운다.
3. [파일] `main.py` 50행(`alert_policy`)·57행(`freshness`, mcp-prom)·66행(`t1_causes`, 그래프 T1)·71행(`evidence`, 시계열 DB SQL)·76행(`evidence_assessment`)·80행(`rank`)·84행(`t2_skills`)·92행(`card`, 근거 노드 id 인용)·95행(`guardrail`)·120행(`submit`, "process API에 카드 제출 — 에이전트의 유일한 쓰기")·138행(`cards`) → [확인] 각 단계의 코드 줄을 표에 붙인다(`grep -n "run.step(" it/agent/agentsvc/main.py`로 다시 확인).
4. [비교] **경보가 아직 열려 있고 카드를 고르기 전에**(카드를 고르면 팬·부하가 바뀌어 사실값이 달라진다) 같은 설비·패턴으로 **조치 판단 규칙** 탭을 실행(dmn-mcp `evaluate_cards`)하고 트레이스 `cards` 단계의 `result.options`와 나란히 → [확인] 카드 순위가 같다. 경보가 끝난 뒤 실행하면 예측·사실값이 달라져 점수와 순위가 다르다 — 그 차이 자체가 "같은 규칙, 다른 사실값"의 예다.
5. [정리] 사실 수집은 그래프의 `InputData -SOURCED_FROM-> System`을 따라 출처별로 읽는다(`decide.py gather_facts`) → [확인] 9회차에서 넣은 InputData가 여기서 어떻게 쓰이는지 한 줄.

## 막혔을 때
- runs가 비어 있음: 경보가 아직 안 났거나 agent가 Kafka `alerts`를 못 읽는다(`curl 127.0.0.1:8091/healthz`의 kafka·neo4j).
- 트레이스에 `WITHHELD`/`FAILED`: 증거 조회 실패나 신선도 부족이다(`evidence_assessment` note). 조치 없이 데이터 상태를 먼저 본다 — 실패를 0으로 바꾸지 않는다.

## 증거
- `.evidence/sessions/10/`(2026-10-07 제작자, `run.py`·`commands.md`): 새 경보 없이 오늘 13:01 쿨러 run(`RUN-0009`, HYD-01)을 API로 읽음 — 1·2 단계 9개(`alert_policy … guardrail · cards`)와 단계별 `note`(`02_steps_table.json`) · 3 `main.py` 줄 번호 11개 · 4 run의 `cards` 순위(경보 중: 팬 최대+부하 80 % 3.87 …)와 지금 실행한 판단(정상 상태: 팬 최대 3.9 …)이 다름을 기록 · 5 `decide.py gather_facts` 3·76·196·202행 — **검증됨**. 4단계 "경보 중 비교"는 2차(`10/alarm/`, 1회차와 같은 쿨러 경보 1건)에서 실행: 트레이스 `RUN-0027` cards(ts1 57.69) 1위 팬 최대+부하 80 % 3.88 · 2위 야간 청소 감산 1.99 · 3위 팬 최대 -0.29 · 4위 쿨러 핀 세척 -2.06, 경보 RAISED 중 판단(카드 선택 · 명령 뒤, ts1 61.4) 1위 같은 카드 3.88 · 2~4위는 팬 최대 3.83 · 핀 세척 3.44 · 야간 청소 3.07로 다름 — 1위 일치 **검증됨**, 2~4위 차이는 선택 뒤에 돌려 사실값이 달라진 것(절차에 "고르기 전에"를 넣음).
- 제작자 증거: 같은 트레이스를 자동으로 확인한 `.evidence/reaudit/reg-a116/cooler-42/scenario.log`, 관측 공백이 UNKNOWN으로 남는 검사 `.evidence/reaudit/a083-coverage-1/`. 학생 완주 증거 아님.
