# 18. Execution 레이어: 그래프는 원천의 그림자 (4부, 180분: 설명 50 / 실습 100 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
실행 기록(인스턴스 · 작업)이 지식 그래프에도 투영돼 정의 노드와 이어지는 것을 본다. 포털이 보여 주는 Cypher를 Neo4j Browser에 그대로 붙여 같은 결과를 얻고, 한 설비의 실행 이력을 센다.
끝나면 포털 표와 같은 질의 결과, 설비별 실행 수 질의 1건이 남는다.

## 준비
- 포털 **프로세스 인스턴스** → 인스턴스 상세 → **온톨로지 Execution 레이어** 표(`instances.js` 485행), Neo4j Browser.
- 파일: `it/process/procsvc/execution_graph.py`(`INSTANCE_Q`, `EXECUTION_Q`), API `GET /api/instances/{id}/graph`, 운영 계약 `docs/execution-projection.md`.
- 관계: ProcessInstance -INSTANCE_OF-> Process(정의 버전), WorkItem -IN_INSTANCE-> ProcessInstance, WorkItem -EXECUTES-> Task, -ASSIGNED_TO-> 역할(HANDOFF §2 "Execution 레이어").

## 실행 장면
1. [화면] 완료된 쿨러 인스턴스 상세 → Execution 레이어 표 → [관찰] 투영된 정의 버전 · 작업 노드 id → [확인] 표 아래 Cypher 본문을 복사.
2. [화면] Neo4j Browser에 붙여 넣고 실행 → [확인] 포털 표와 같은 행 수·id.
3. [화면] `MATCH (w:WorkItem)-[:IN_INSTANCE]->(p:ProcessInstance {id:'<인스턴스 id>'}) MATCH (w)-[:EXECUTES]->(t) RETURN w.activity_id, w.status, t.id, labels(t)` → [관찰] 작업 → 정의의 활동 노드 → [확인] `t.id`가 8회차·15회차에서 본 BPMN 노드 id(`task:diagnose` …)와 같다.
4. [명령] `curl -s 127.0.0.1:8080/api/instances/<id>/graph` → [확인] 2단계와 같은 내용(투영 상태 · 재시도 정보 포함).
5. [화면] `MATCH (p:ProcessInstance)-[:INSTANCE_OF]->(d) WHERE p.asset='HYD-01' RETURN d.id, p.status, count(*)`(속성 이름은 1단계 표에서 확인) → [확인] 한 설비의 실행 이력을 정의 버전별로 센다.
6. [정리] 그래프는 원천(PostgreSQL)의 그림자다: 투영이 늦거나 실패하면 `docs/execution-projection.md` "상태 확인"의 복구 절차, 원천은 바뀌지 않는다 → [확인] "원천 vs 투영" 한 줄.

## 막혔을 때
- 표가 비어 있음: 투영은 종결·승인 시점에 쓰인다(HANDOFF §6). 완료된 인스턴스를 고른다. 그래도 없으면 `/graph`의 상태와 `execution-projection.md`의 격리(quarantine)·복구.
- Cypher 속성 이름 불일치: `CALL db.schema.visualization()`에서 ProcessInstance · WorkItem 속성 확인.

## 증거
- 제작자 증거: 쿨러 42/42 안의 그래프 검사(ProcessInstance -INSTANCE_OF-> Process, WorkItem -EXECUTES-> Task, ROLE_BOUND) `.evidence/reaudit/reg-a116/cooler-42/scenario.log`, 투영 복구·격리 `probe_execution_projection.py`·`probe_projection_repair_live.py`(`docs/execution-projection.md` "검증"), 실행 범위 `probe_execution_scope.py`. 학생 완주 증거 아님.
- `.evidence/sessions/18/`: **미검증**.
