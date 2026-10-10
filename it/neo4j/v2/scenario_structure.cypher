// 확정 TODO C1 — 시나리오 구조(시드, 두 판 공통). 스키마 v2의 기존 클래스 · 관계만 쓰는 인스턴스 추가다. 멱등(MERGE).
// instances.cypher · knowledge_a098.cypher 다음에 적용한다(seed.sh · scripts/ontology_v2.py load).
// 여기에는 "문서가 기대는 자리"만 둔다: 승인 역할, 감시 패턴, 규칙이 검사할 판단 입력. 고장 · 원인 · 조치 · 규칙은 문서 적재가 만든다.
// 시나리오 B(정기 정비, 2026-10-09 확정)의 시작 패턴 · 입력 · 부품은 이 파일 끝에 있다.

// C 예비품 구매: 구매 담당(카드 승인 L1). 구매팀장(role:purchasing-mgr, L2)은 instances.cypher에 있다.
MERGE (n:Role {id: 'role:purchasing'}) SET n.name = '구매 담당', n.level = 1
WITH n MATCH (d:OrgUnit {id: 'dept:purchasing'}) MERGE (n)-[:MEMBER_OF]->(d);

// 판단 입력: [id, name, typeRef, variable, source, represents]. 값은 실행 중에 온다(ERP 재고 감시 · 에이전트 계산). 지식에는 자리만 둔다.
// in:supplier-fail-rate (2026-10-10): PR-7.4 "불량률이 10 %를 넘는 승인 공급사에 발주할 때는 … 전수 검사 비용 20만 원을 더해 비교한다"가
// 시험할 자리. 이 자리가 없어 실제 추출(라이브 4차)도 사람 검토도 이 규칙을 적재할 수 없었다(check_graph가 REQUIRES_INPUT 밖 입력을 거부).
// 값은 후보 카드의 공급사 견적(SCM)에서 카드마다 온다(cards.candidate_facts).
UNWIND [['in:spare-gap','예비품 가용 재고 − 재주문점 (개)','number','spare_gap','sys:erp',null],
        ['in:po-amount','발주 금액 (만원)','number','po_amount','sys:agent','msr:part-cost'],
        ['in:lead-slack-days','필요일 − 공급사 리드타임 (일)','number','lead_slack_days','sys:agent',null],
        ['in:supplier-fail-rate','후보 공급사 불량률 (견적, 0~1)','number','supplier_fail_rate','sys:scm','msr:part-quality']] AS r
MERGE (n:InputData {id: r[0]}) SET n.name = r[1], n.typeRef = r[2], n.variable = r[3]
WITH n, r MATCH (src {id: r[4]}) MERGE (n)-[:SOURCED_FROM]->(src)
WITH n, r OPTIONAL MATCH (x:Measure {id: r[5]})
FOREACH (_ IN CASE WHEN x IS NULL THEN [] ELSE [1] END | MERGE (n)-[:REPRESENTS]->(x));

// 규정 검토가 문서 규칙으로 검사할 수 있는 입력(규칙이 검사하는 입력은 결정의 REQUIRES_INPUT · 작업의 READS로 선언한다 — validate 규칙).
UNWIND ['in:pattern','in:po-amount','in:lead-slack-days','in:supplier-fail-rate'] AS iid
MATCH (d:Decision {id: 'dec:compliance'}), (t:Task {id: 'task:compliance'}), (i:InputData {id: iid})
MERGE (d)-[:REQUIRES_INPUT]->(i) MERGE (t)-[:READS]->(i);

// 재고 기준 이탈 감시 패턴. 센서가 아니라 ERP 재고 감시(확정 TODO C2)가 경보를 낸다 — detectionMode가 없으므로 탐지기는 읽지 않는다.
// 설비 증상이 아니므로 Symptom을 잇지 않는다(seed_checks의 패턴 단언은 결정 1에 따라 설비 패턴에만 적용).
MERGE (p:AnomalyPattern {id: 'pattern:spare-below-min'})
  SET p.name = '예비품 재고 기준 이탈', p.code = 'SPARE_BELOW_MIN', p.rule = '가용 재고(현재고 − 정비 예약 + 입고 예정) < 재주문점 (ERP 재고 감시)', p.holdSeconds = 0
WITH p MATCH (i:InputData {id: 'in:spare-gap'}) MERGE (p)-[t:TESTS]->(i) SET t.operator = '<', t.value = 0, t.unit = 'ea'
WITH p MATCH (k:KnowledgeSource {id: 'ks:pr-07'}) MERGE (p)-[:DERIVED_FROM]->(k)
WITH p MATCH (e:Event {id: 'ev:alert'}) MERGE (e)-[:CORRELATES]->(p);

// ---------------------------------------------------------------- B 정기 정비 (2026-10-09 확정)
// 시작은 센서가 아니라 운전시간 계수기다(CMMS 계획 스케줄러). 센서 값은 시행 방식을 고르는 근거일 뿐 시작 신호가 아니다.
// 주기 · 허용 오차(2,000 h ± 10 %)는 회사 설정이다. 시행 방식 · 패키지 SOP와 규칙(허용 오차 · 생산 · 묶음 · 부품)은 B 문서(PM-02) 적재가 만든다.
MERGE (k:KnowledgeSource {id: 'ks:pm-plan'}) SET k.name = '정기 정비 계획 기준 (회사 설정, 교육용 예시)', k.kind = 'policy', k.ref = 'PM-PLAN';

// 리턴 필터 엘리먼트: 2,000 h 패키지 부품(작동유 탱크 리턴 라인). 공급 조건은 C 구매 범위 밖이라 두지 않는다.
MERGE (n:Part {id: 'part:return-filter'}) SET n.name = '리턴 필터 엘리먼트', n.partNo = 'P-RTN-FLT'
WITH n MATCH (c:Component {id: 'comp:tank'}) MERGE (c)-[:USES_PART]->(n);

// 판단 입력: [id, name, typeRef, variable, source, represents]. 값은 실행 중에 CMMS · MES 계획에서 온다(지식에는 자리만).
UNWIND [['in:hours-since-pm','마지막 정기 정비 뒤 운전시간 (h)','number','hours_since_pm','sys:cmms',null],
        ['in:next-scheduled-time','이번 예정된 정비 시간에 닿을 때의 운전시간 (h)','number','hours_at_next_window','sys:cmms',null],
        ['in:hours-if-deferred','그다음 예정된 정비 시간으로 미룰 때의 운전시간 (h)','number','hours_at_following_window','sys:cmms',null],
        ['in:pm-crew','예정된 정비 시간의 정비 인원 (명)','number','pm_crew_available','sys:cmms',null],
        ['in:spare-available','씰 키트 가용 재고 (CMMS 자재 키트, 개)','number','spare_available','sys:cmms',null]] AS r
MERGE (n:InputData {id: r[0]}) SET n.name = r[1], n.typeRef = r[2], n.variable = r[3]
WITH n, r MATCH (src {id: r[4]}) MERGE (n)-[:SOURCED_FROM]->(src);

// 후보 선택은 정기 정비 도래 · 운전시간을, 규정 검토는 일정 · 생산 오더 납기 · 인원 · 부품을 읽는다(REQUIRES_INPUT + 작업 READS).
UNWIND [['dec:action-candidates','task:candidates','in:hours-since-pm'],
        ['dec:compliance','task:compliance','in:next-scheduled-time'],['dec:compliance','task:compliance','in:hours-if-deferred'],
        ['dec:compliance','task:compliance','in:order-due'],['dec:compliance','task:compliance','in:pm-crew'],
        ['dec:compliance','task:compliance','in:spare-available']] AS r
MATCH (d:Decision {id: r[0]}), (t:Task {id: r[1]}), (i:InputData {id: r[2]})
MERGE (d)-[:REQUIRES_INPUT]->(i) MERGE (t)-[:READS]->(i);

// 정기 정비 도래 감시 규칙. CMMS 계획 스케줄러(확정 TODO C2 업무 표 기준값 감시기, source cmms)가 경보를 낸다 — detectionMode가 없으므로 CEP 탐지기는 읽지 않는다.
// 설비 증상이 아니므로 Symptom을 잇지 않는다(결정 1 — seed_checks의 패턴 단언은 설비 패턴에만).
MERGE (p:AnomalyPattern {id: 'pattern:pm-due'})
  SET p.name = '정기 정비 도래', p.code = 'PM_DUE', p.rule = '마지막 정기 정비 뒤 운전시간 ≥ 1,950 h (주기 2,000 h의 50 h 전, CMMS 계획 스케줄러)', p.holdSeconds = 0
WITH p MATCH (i:InputData {id: 'in:hours-since-pm'}) MERGE (p)-[t:TESTS]->(i) SET t.operator = '>=', t.value = 1950, t.unit = 'h'
WITH p MATCH (k:KnowledgeSource {id: 'ks:pm-plan'}) MERGE (p)-[:DERIVED_FROM]->(k)
WITH p MATCH (e:Event {id: 'ev:alert'}) MERGE (e)-[:CORRELATES]->(p);

// 구조판 전용: 회사 규정 rule:avl(구매규정 PR-07)의 적용 대상 rule:avl -APPLIES_TO-> skill:wo-pump-seal은 전체판 시드 스킬이라 구조판에는 없다.
// 적용 대상이 비면 "모든 후보에 적용"이 되어, 공급사가 없는 냉각 · 정비 카드까지 '승인 여부 모름'으로 제외된다(2026-10-09 B 판단 검증에서 발견).
// 그래서 구조판에서는 같은 규칙을 구매요청(PR_CREATE)이 든 스킬에만 걸리게 검사 하나를 더한다. 전체판은 그대로다.
// @edition structure
MATCH (r:Rule {id: 'rule:avl'}), (i:InputData {id: 'in:skill-code'}) WHERE NOT (r)-[:APPLIES_TO]->(:Skill)
MERGE (r)-[t:TESTS]->(i) SET t.operator = '==', t.value = 'PR_CREATE'
SET r.when = "skill_code == 'PR_CREATE' and supplier_avl == false";
