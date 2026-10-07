# 10. 에이전트는 LLM + 도구 + 절차 (3부, 180분: 설명 70 / 실습 80 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
쿨러 경보 하나에 대해 서버 안 에이전트가 남긴 실행 기록(트레이스)을 단계별로 읽고, 각 단계가 어느 도구로 어느 출처(그래프 · 시계열 DB · 기업 시스템)를 읽었는지 표로 만든다.
끝나면 "단계 · 도구 · 출처 · 읽은 값" 표 1장이 남는다.

## 준비
- 1회차처럼 쿨러 경보 1건을 낸다(포털 결함 시뮬레이션 → HYD-01 쿨러 열화 주입).
- 포털 **이상 확인 · 조치** 탭, 에이전트 API http://127.0.0.1:8091/docs.
- 파일: `it/agent/agentsvc/main.py` `pipeline()`(45~120행), `decide.py`(사실 수집), `tools/mcp_kg.py`·`mcp_tsdb.py`·`mcp_ent.py`·`mcp_prom.py`.

## 실행 장면
1. [화면] 이상 확인 · 조치 → HYD-01 도식 클릭 → **에이전트 트레이스** → [관찰] 단계가 순서대로: `alert_policy → freshness → t1_causes → evidence (→ evidence_assessment) → rank → t2_skills → card → guardrail → cards → submit` → [확인] 단계 수를 센다(커리큘럼의 "8단계"는 예전 표현이고 현재 코드는 10~11단계).
2. [명령] `curl -s 127.0.0.1:8091/api/agent/runs | python -m json.tool | head -60` → 최근 run id → `curl -s 127.0.0.1:8091/api/agent/runs/<id>` → [관찰] 단계마다 `note`(예 "mcp-tsdb: Evidence SQL 템플릿 실행 (tag_1s)") → [확인] 표의 "도구·출처" 열을 채운다.
3. [파일] `main.py` 57행(`freshness`, mcp-prom)·66행(`t1_causes`, 그래프 T1)·71행(`evidence`, 시계열 DB SQL)·40행 부근(`t2_skills`)·48행(`card`, 근거 노드 id 인용)·51행(`guardrail`)·76행(`submit`, "process API에 카드 제출 — 에이전트의 유일한 쓰기") → [확인] 각 단계의 코드 줄을 표에 붙인다.
4. [비교] 같은 경보의 **조치 판단 규칙** 탭 결과(dmn-mcp `evaluate_cards`)와 트레이스 `cards` 단계 → [확인] 카드 순위가 같다.
5. [정리] 사실 수집은 그래프의 `InputData -SOURCED_FROM-> System`을 따라 출처별로 읽는다(`decide.py gather_facts`) → [확인] 9회차에서 넣은 InputData가 여기서 어떻게 쓰이는지 한 줄.

## 막혔을 때
- runs가 비어 있음: 경보가 아직 안 났거나 agent가 Kafka `alerts`를 못 읽는다(`curl 127.0.0.1:8091/healthz`의 kafka·neo4j).
- 트레이스에 `WITHHELD`/`FAILED`: 증거 조회 실패나 신선도 부족이다(`evidence_assessment` note). 조치 없이 데이터 상태를 먼저 본다 — 실패를 0으로 바꾸지 않는다.

## 증거
- 제작자 증거: 같은 트레이스를 자동으로 확인한 `.evidence/reaudit/reg-a116/cooler-42/scenario.log`, 관측 공백이 UNKNOWN으로 남는 검사 `.evidence/reaudit/a083-coverage-1/`. 학생 완주 증거 아님.
- `.evidence/sessions/10/`: **미검증**.
