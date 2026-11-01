// 시나리오 B(정기 정비) · C(예비품 구매)의 구조 — instances.cypher 다음에 적재한다(seed.sh). id로만 MERGE · SET — 몇 번을 적재해도 같다.
// 여기에는 "문서가 기대는 자리"만 둔다: 업무 표 감시 패턴, 규칙이 검사할 판단 입력. 시행 방식 · 패키지 SOP와 규칙(허용 오차 · 생산 · 묶음 · 부품 ·
// 공급사)은 수업 문서 PM-02 · PR-07 적재가 만든다. 구매 담당 역할 · 리턴 필터 부품 · 정기 정비 계획 기준 출처는 instances.cypher에 있다.

// 판단 입력: [id, name, typeRef, variable, source, represents]. 값은 실행 중에 온다(ERP 재고 감시 · CMMS · MES 계획 · 에이전트 계산).
// in:supplier-fail-rate: PR-7.4 「불량률이 10 %를 넘는 승인 공급사에 발주할 때는 … 전수 검사 비용 20만 원을 더해 비교한다」가 검사하는 자리 —
// 값은 후보 카드의 공급사 견적(SCM)에서 카드마다 온다(cards.candidate_facts).
UNWIND [['in:spare-gap','예비품 가용 재고 − 재주문점 (개)','number','spare_gap','sys:erp',null],
        ['in:po-amount','발주 금액 (만원)','number','po_amount','sys:agent','msr:part-cost'],
        ['in:lead-slack-days','필요일 − 공급사 리드타임 (일)','number','lead_slack_days','sys:agent',null],
        ['in:supplier-fail-rate','후보 공급사 불량률 (견적, 0~1)','number','supplier_fail_rate','sys:scm','msr:part-quality'],
        ['in:hours-since-pm','마지막 정기 정비 뒤 운전시간 (h)','number','hours_since_pm','sys:cmms',null],
        ['in:next-scheduled-time','이번 예정된 정비 시간에 닿을 때의 운전시간 (h)','number','hours_at_next_window','sys:cmms',null],
        ['in:hours-if-deferred','그다음 예정된 정비 시간으로 미룰 때의 운전시간 (h)','number','hours_at_following_window','sys:cmms',null],
        ['in:pm-crew','예정된 정비 시간의 정비 인원 (명)','number','pm_crew_available','sys:cmms',null],
        ['in:spare-available','씰 키트 가용 재고 (CMMS 자재 키트, 개)','number','spare_available','sys:cmms',null]] AS r
MERGE (n:InputData {id: r[0]}) SET n.name = r[1], n.typeRef = r[2], n.variable = r[3]
WITH n, r MATCH (src {id: r[4]}) MERGE (n)-[:SOURCED_FROM]->(src)
WITH n, r OPTIONAL MATCH (x:Measure {id: r[5]})
FOREACH (_ IN CASE WHEN x IS NULL THEN [] ELSE [1] END | MERGE (n)-[:REPRESENTS]->(x));

// 판단이 읽는 입력(규칙이 검사하는 입력은 그 판단의 REQUIRES_INPUT에 선언한다 — 문서 적재가 이 목록 밖 입력을 쓰는 규칙을 거부한다).
// 후보 선택은 운전시간을, 규정 검토는 구매(금액 · 리드타임 · 불량률 · 경보 패턴)와 정비(일정 · 오더 납기 · 인원 · 부품)를 읽는다.
UNWIND [['dec:action-candidates','in:hours-since-pm'],
        ['dec:compliance','in:pattern'],['dec:compliance','in:po-amount'],['dec:compliance','in:lead-slack-days'],['dec:compliance','in:supplier-fail-rate'],
        ['dec:compliance','in:next-scheduled-time'],['dec:compliance','in:hours-if-deferred'],['dec:compliance','in:order-due'],
        ['dec:compliance','in:pm-crew'],['dec:compliance','in:spare-available']] AS r
MATCH (d:Decision {id: r[0]}), (i:InputData {id: r[1]}) MERGE (d)-[:REQUIRES_INPUT]->(i);

// 업무 표 감시 패턴 하나가 한 행이다: [id, name, code, 검사[[input, 식에 쓰는 이름, operator, value, unit]], 덧붙임 설명, 출처]
//   센서가 아니라 업무 시스템 감시(CMMS 계획 스케줄러 · ERP 재고 감시, process business_monitor)가 경보를 낸다 — detectionMode가 없으므로
//   감지기는 읽지 않고, 설비 증상이 아니므로 Symptom을 잇지 않는다(seed_checks의 설비 패턴 단언 밖). rule은 instances.cypher 4절과 같은 방식으로
//   검사 행에서 만든다. 주기 · 허용 오차(2,000 h ± 10 %)는 회사 설정(ks:pm-plan), 재주문점은 ERP 품목 설정이다.
UNWIND [
  ['pattern:pm-due','정기 정비 도래','PM_DUE',[['in:hours-since-pm','정비 뒤 운전시간','>=',1950,'h']],
    '주기 2,000 h의 50 h 전 — CMMS 계획 스케줄러',['ks:pm-plan']],
  ['pattern:spare-below-min','예비품 재고 기준 이탈','SPARE_BELOW_MIN',[['in:spare-gap','가용 재고 − 재주문점','<',0,'개']],
    '가용 재고 = 현재고 − 정비 예약 + 입고 예정 — ERP 재고 감시',['ks:monitoring-pr-07']]
] AS r
MERGE (p:AnomalyPattern {id: r[0]})
SET p.name = r[1], p.code = r[2], p.holdSeconds = 0, p.detectionMode = null,
    p.rule = reduce(s = '', t IN r[3] | s + CASE WHEN s = '' THEN '' ELSE ' and ' END + t[1] + ' ' + t[2] + ' '
                    + CASE WHEN t[3] IS :: STRING THEN "'" + t[3] + "'" ELSE toString(t[3]) END)
             + CASE WHEN r[4] IS NULL THEN '' ELSE ' (' + r[4] + ')' END
WITH p, r
OPTIONAL MATCH (p)-[old:TESTS]->(gone:InputData) WHERE gone.ns IS NULL AND NOT gone.id IN [t IN r[3] | t[0]]
DELETE old
WITH DISTINCT p, r
OPTIONAL MATCH (p)-[old:DERIVED_FROM]->(gone:KnowledgeSource) WHERE gone.ns IS NULL AND NOT gone.id IN r[5]
DELETE old
WITH DISTINCT p, r
CALL (p, r) { UNWIND r[3] AS t MATCH (i:InputData {id: t[0]}) MERGE (p)-[x:TESTS]->(i) SET x.operator = t[2], x.value = t[3], x.unit = t[4] }
CALL (p, r) { UNWIND r[5] AS kid MATCH (k:KnowledgeSource {id: kid}) MERGE (p)-[:DERIVED_FROM]->(k) };
