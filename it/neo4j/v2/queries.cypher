// 온톨로지 v2 질의 예시 — 에이전트가 "스키마(schema_prompt.md) + 질문"으로 만들어야 할 Cypher의 정답 예시 (few-shot).
// 실행: python scripts/ontology_v2.py queries   (각 블록: @query 이름, @ask 자연어 질문, @params 매개변수)

// @query q1-entity
// @ask "유온이 오르고 냉각이 안 된다" — 질문의 말이 가리키는 노드부터 찾는다 (엔티티 인식)
// @params {"text": "유온 냉각"}
CALL db.index.fulltext.queryNodes('ont_names', $text) YIELD node, score
RETURN labels(node)[0] AS class, node.id AS id, node.name AS name, round(score, 2) AS score
ORDER BY score DESC LIMIT 8;

// @query q2-diagnosis-path
// @ask 유온 상승 증상에서 고장 유형, 원인 후보, 확인할 증거, 그 고장 유형의 조치 방법(SOP)과 매뉴얼까지 경로를 보여 줘
// @params {"symptom": "sym:ts1-rise"}
MATCH (sym:Symptom {id: $symptom})-[:INDICATES]->(fm:FailureMode)<-[:CAUSES]-(c:Cause)
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:Evidence)
WITH sym, fm, c, collect(DISTINCT e.name) AS evidence
MATCH (fm)-[k:MITIGATED_BY|REMEDIED_BY]->(s:Skill)
WHERE NOT (s)-[:ADDRESSES]->(:Cause) OR (s)-[:ADDRESSES]->(c)
OPTIONAL MATCH (s)-[co:CONSISTS_OF]->(a:Action)
OPTIONAL MATCH (s)-[:HAS_STEP]->(st:Step)-[:REFERS_TO]->(m:ManualSection)
RETURN fm.name AS failureMode, c.name AS cause, c.prior AS prior, evidence,
       CASE type(k) WHEN 'MITIGATED_BY' THEN '즉시 완화' ELSE '근본 조치' END AS kind, s.sopId AS sop, s.name AS skill,
       collect(DISTINCT a.code + '=' + toString(co.value)) AS commands, collect(DISTINCT m.ref) AS manual
ORDER BY prior DESC, kind DESC, sop;

// @query q2b-failure-mode-skills
// @ask 고장 유형마다 매칭된 조치 방법(스킬 = SOP)을 단계 수와 함께 보여 줘
// @params {}
MATCH (fm:FailureMode)-[k:MITIGATED_BY|REMEDIED_BY|PREVENTED_BY]->(s:Skill)
OPTIONAL MATCH (s)-[:ADDRESSES]->(c:Cause)
OPTIONAL MATCH (s)-[:HAS_STEP]->(st:Step)
RETURN fm.name AS failureMode, CASE type(k) WHEN 'MITIGATED_BY' THEN '즉시 완화' WHEN 'PREVENTED_BY' THEN '예방 조치' ELSE '근본 조치' END AS kind,
       s.sopId AS sop, s.name AS skill, count(DISTINCT st) AS steps, collect(DISTINCT c.name) AS onlyForCause
ORDER BY failureMode, kind DESC, sop;

// @query q3-candidate-cards
// @ask 쿨러 핀 오염일 때 에이전트가 내밀 조치 카드들을 예측값, 규정 판정, 승인 역할과 함께 비교해 줘
// @params {"cause": "cause:cooler-fin-fouling"}
MATCH (:Cause {id: $cause})-[:CAUSES]->(fm:FailureMode)
MATCH (sel:Rule {effect: 'SELECT'})-[:OUTPUTS]->(s:Skill), (sel)<-[:HAS_RULE]-(:DecisionTable)<-[:IMPLEMENTED_BY]-(:Decision {id: 'dec:action-candidates'})
WHERE sel.when CONTAINS fm.id
OPTIONAL MATCH (f:Forecast)-[:ASSUMES]->(s) WHERE (f)-[:GIVEN]->(:Cause {id: $cause})
OPTIONAL MATCH (f)-[:FORECASTS]->(v:StateVariable)
OPTIONAL MATCH (lim:Rule)-[:APPLIES_TO]->(s)
OPTIONAL MATCH (s)-[:APPROVED_BY]->(ro:Role)
RETURN s.sopId AS sop, s.name AS card, collect(DISTINCT v.name + ' ' + toString(f.value) + f.unit) AS forecast,
       collect(DISTINCT lim.effect + ' (' + lim.when + '): ' + lim.annotation) AS rules, ro.name AS approver
ORDER BY sop;

// @query q4-tradeoff-paths
// @ask "팬 최대 + 부하 80 %"를 하면 영업이익에 어떤 경로로 득과 실이 생기나?
// @params {"skill": "skill:fan-max-derate"}
MATCH (s:Skill {id: $skill})-[a:AFFECTS]->(x)
MATCH p = (x)-[:INFLUENCES*0..8]->(goal:Measure {id: 'msr:op-profit'})
WITH s, a, p, a.sign * reduce(z = 1, r IN relationships(p) | z * r.sign) AS net
RETURN CASE net WHEN 1 THEN '이익 +' ELSE '이익 -' END AS effect,
       [s.name] + [n IN nodes(p) | n.name] AS path,
       [r IN relationships(p) WHERE r.condition IS NOT NULL | r.condition] AS conditions
ORDER BY effect, size(nodes(p));

// @query q5-card-balance
// @ask 같은 원인의 후보 카드마다 어떤 성과 지표가 좋아지고 어떤 성과 지표가 나빠지나? 그 성과 지표는 어느 부서 것인가? (BSC 상충 관계 — 거시적 판단의 재료)
// 조건 없는 영향은 gains · losses로, 조건이 붙은 경로(인터록 근처에서만 성립 등)는 conditional로 따로 낸다.
// @params {"cause": "cause:fan-bearing-wear"}
MATCH (c:Cause {id: $cause})-[:CAUSES]->(:FailureMode)-[:MITIGATED_BY|REMEDIED_BY]->(s:Skill)
WHERE NOT (s)-[:ADDRESSES]->(:Cause) OR (s)-[:ADDRESSES]->(c)
CALL (s) {
  MATCH (s)-[a:AFFECTS]->(x)
  MATCH p = (x)-[:INFLUENCES*0..4]->(k:Measure)
  WHERE all(n IN nodes(p)[0..-1] WHERE NOT n:Measure)
  WITH k, a.sign * reduce(z = 1, r IN relationships(p) | z * r.sign) AS dir,
       [r IN relationships(p) WHERE r.condition IS NOT NULL | r.condition] AS conds
  OPTIONAL MATCH (k)-[:OWNED_BY]->(o:OrgUnit)
  WITH k, dir, conds, k.name + CASE dir WHEN 1 THEN ' ↑' ELSE ' ↓' END + ' [' + coalesce(o.name, '-') + ']' AS label, (dir = 1) = (k.direction = 'UP') AS good
  RETURN collect(DISTINCT CASE WHEN size(conds) = 0 AND good THEN label END) AS gains,
         collect(DISTINCT CASE WHEN size(conds) = 0 AND NOT good THEN label END) AS losses,
         collect(DISTINCT CASE WHEN size(conds) > 0 THEN label + CASE WHEN good THEN ' (득)' ELSE ' (실)' END + ' — ' + conds[0] END) AS conditional
}
OPTIONAL MATCH (s)-[:APPROVED_BY]->(ro:Role)
RETURN s.name AS skill, gains, losses, conditional, ro.name AS approver
ORDER BY size(gains) - size(losses) DESC;

// @query q6-card-sources
// @ask "예비 펌프 전환" 카드의 근거(출처)를 사람이 확인할 수 있게 모두 보여 줘
// @params {"skill": "skill:switch-standby-pump"}
MATCH (s:Skill {id: $skill})
OPTIONAL MATCH (fm:FailureMode)-[:MITIGATED_BY|REMEDIED_BY|PREVENTED_BY]->(s)
OPTIONAL MATCH (c:Cause)-[:CAUSES]->(fm) WHERE NOT (s)-[:ADDRESSES]->(:Cause) OR (s)-[:ADDRESSES]->(c)
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:Evidence)
OPTIONAL MATCH (sel:Rule)-[:OUTPUTS]->(s)
OPTIONAL MATCH (lim:Rule)-[:APPLIES_TO]->(s)
OPTIONAL MATCH (r2:Rule)-[:DERIVED_FROM]->(src) WHERE r2 IN [sel, lim]
OPTIONAL MATCH (s)-[:HAS_STEP]->(st:Step)-[:REFERS_TO]->(m:ManualSection)
RETURN s.sopId AS sop, s.name AS card, collect(DISTINCT fm.name) AS failureMode, collect(DISTINCT c.name) AS cause, collect(DISTINCT e.name) AS evidence,
       collect(DISTINCT sel.annotation) AS selectedBy, collect(DISTINCT lim.effect + ': ' + lim.annotation) AS limitedBy,
       collect(DISTINCT coalesce(src.ref, src.name)) AS ruleSources, collect(DISTINCT toString(st.order) + '. ' + st.text + ' [' + m.ref + ']') AS sopSteps;

// @query q7-layers
// @ask 설비 가용성 확보라는 조직 목표(BSC)를 달성하는 프로세스, 그 일을 하는 리소스, 리소스의 스킬(SOP)을 계층대로 보여 줘 (BSC → 프로세스 → 리소스 → 스킬)
// @params {"objective": "obj:availability"}
MATCH (o:Objective {id: $objective})-[:IN_PERSPECTIVE]->(pe:Perspective)
MATCH (o)<-[:ACHIEVES]-(p:Process)-[:HAS_NODE]->(t:Task)-[:PERFORMED_BY]->(res)
OPTIONAL MATCH (res)-[:HAS_SKILL]->(s:Skill)
OPTIONAL MATCH (t)-[:INVOKES]->(d:Decision)
RETURN pe.name + ' / ' + o.name AS bsc, p.name AS process, t.name AS task, t.taskType AS taskType, labels(res)[0] + ' ' + res.name AS resource,
       d.name AS decision, collect(DISTINCT s.sopId + ' ' + s.name)[0..4] AS skills
ORDER BY task;

// @query q8-part-price
// @ask 비용을 줄이려고 부품 단가를 낮추면 이익은 어떻게 되나? (대표 설명의 예시)
// @params {"lever": "msr:part-price", "change": -1}
MATCH p = (:Measure {id: $lever})-[:INFLUENCES*1..8]->(goal:Measure {id: 'msr:op-profit'})
WITH p, $change * reduce(z = 1, r IN relationships(p) | z * r.sign) AS net
RETURN CASE net WHEN 1 THEN '이익 +' ELSE '이익 -' END AS effect, [n IN nodes(p) | n.name] AS path,
       [r IN relationships(p) WHERE r.condition IS NOT NULL | r.condition] AS conditions
ORDER BY effect, size(nodes(p));

// @query q9-external
// @ask 환율이 오르면 무엇이 어떻게 움직이고 이익에는 어떤 방향인가? 조건부 영향은 조건과 함께
// @params {"var": "ext:fx"}
MATCH (x:ExternalVariable {id: $var})-[i:INFLUENCES]->(t)
OPTIONAL MATCH p = (t)-[:INFLUENCES*0..8]->(:Measure {id: 'msr:op-profit'})
WHERE all(r IN relationships(p) WHERE r.condition IS NULL)
WITH x, i, t, collect(DISTINCT i.sign * reduce(z = 1, r IN relationships(p) | z * r.sign)) AS nets
RETURN t.name AS target, CASE i.sign WHEN 1 THEN '↑' ELSE '↓' END AS direction, i.condition AS condition, i.note AS note,
       [n IN nets | CASE n WHEN 1 THEN '이익 +' ELSE '이익 -' END] AS profitEffect;

// @query q10-precedent
// @ask 쿨러 핀 오염 사건에서 사람들은 지금까지 어떤 카드를 왜 골랐나? (선례)
// @params {"cause": "cause:cooler-fin-fouling"}
MATCH (dc:DecisionCase)-[:FOR_INCIDENT]->(:Incident)-[:DIAGNOSED_AS]->(:Cause {id: $cause})
// 교육용 고정: 시드 선례만 센다(templates/t3_precedents.cypher와 같은 기준). 이 조건을 빼면 승인으로 쌓인 사례까지 보인다 — DECISIONS 110 ④
WHERE dc.seeded = true
MATCH (dc)-[:CHOSE]->(s:Skill), (dc)-[:DECIDED_BY]->(r:Role)
RETURN s.name AS chosen, count(*) AS times, collect(r.name + ': ' + dc.reason) AS reasons,
       sum(CASE WHEN dc.followedRecommendation THEN 0 ELSE 1 END) AS overrides
ORDER BY times DESC;

// @query q11-process-flow
// @ask 설비 이상 조치 프로세스의 순서와 수행자, 각 단계가 부르는 판단을 보여 줘
// @params {}
MATCH (a:FlowNode)-[f:SEQUENCE_FLOW]->(b:FlowNode), (:Process {id: 'proc:anomaly-response'})-[:HAS_NODE]->(a)
OPTIONAL MATCH (a)-[:PERFORMED_BY]->(who)
OPTIONAL MATCH (a)-[:INVOKES]->(d:Decision)
RETURN a.name AS from, labels(a)[1] AS kind, who.name AS performer, d.name AS decision, f.condition AS condition, b.name AS to;

// @query q12-scenario-profile
// @ask 펌프 누설 경보가 오면 어떤 프로세스가 무엇을 대상으로 시작되고, 어떤 임계값으로 탐지 · 판정되며, 어떤 조치 카드와 규정이 걸리나?
// @params {"pattern": "pattern:pump-leakage"}
MATCH (p:Process)-[:HAS_NODE]->(ev:Event {position: 'start'})-[:CORRELATES]->(ap:AnomalyPattern {id: $pattern})
OPTIONAL MATCH (p)-[:ACTS_ON]->(a:Asset)
MATCH (ap)-[t:TESTS]->(i:InputData)
WITH p, ev, a, ap, collect(i.variable + ' ' + t.operator + ' ' + toString(t.value) + coalesce(' ' + t.unit, '')) AS detection
OPTIONAL MATCH (dx:Rule)-[dt:TESTS]->(:InputData {id: 'in:pattern'}) WHERE dt.value = ap.code
OPTIONAL MATCH (dx)-[:OUTPUTS]->(c:Cause)-[:CAUSES]->(fm:FailureMode)
OPTIONAL MATCH (cand:Rule)-[ct:TESTS]->(:InputData {id: 'in:failure-mode'}) WHERE ct.value = fm.id
OPTIONAL MATCH (cand)-[:OUTPUTS]->(s:Skill)
OPTIONAL MATCH (g:Rule)-[:APPLIES_TO]->(s)
RETURN p.name AS process, ev.eventDefinition + ' ' + ev.messageRef + ' / key=' + ev.correlationKey AS start, a.name AS target,
       detection, dx.when AS diagnosisRule, c.name AS cause, fm.name AS failureMode,
       collect(DISTINCT s.sopId + ' ' + s.name) AS cards, collect(DISTINCT g.effect + ' if ' + g.when) AS guards;

// @query q13-data-flow
// @ask 설비 이상 조치 프로세스에서 작업마다 어떤 데이터를 어디서 읽고 무엇을 만들어 다음 작업에 넘기나? (BPMN 데이터 연결성)
// @params {}
MATCH (:Process {id: 'proc:anomaly-response'})-[:HAS_NODE]->(t:Task)
MATCH sp = shortestPath((:Event {id: 'ev:alert'})-[:SEQUENCE_FLOW*..12]->(t))
OPTIONAL MATCH (t)-[:READS]->(i:InputData)
OPTIONAL MATCH (prod:Task)-[:PRODUCES]->(i)
OPTIONAL MATCH (i)-[:SOURCED_FROM]->(src)
WITH t, length(sp) AS step, i, collect(DISTINCT prod.name) AS producers, collect(DISTINCT src.name) AS sources
WITH t, step, collect(i.variable + ' ← ' + CASE WHEN size(producers) > 0 THEN '작업 ' + producers[0] ELSE sources[0] END) AS reads
OPTIONAL MATCH (t)-[:PRODUCES]->(o:InputData)
OPTIONAL MATCH (t)-[:INVOKES]->(d:Decision)
RETURN step, t.name AS task, t.taskType AS type, d.name AS decision, reads, collect(DISTINCT o.variable) AS produces
ORDER BY step;

// @query q14-thresholds
// @ask 탐지 · 판단 규칙의 수치 임계값을 모두 보여 주고, 각 임계값이 어느 상태 변수 · 성과 지표의 어떤 한계와 이어지는지, 근거는 무엇인지 알려 줘 (DMN 임계값)
// @params {}
MATCH (x)-[t:TESTS]->(i:InputData) WHERE t.operator IN ['<', '<=', '>', '>=']
OPTIONAL MATCH (i)-[:REPRESENTS]->(v)
OPTIONAL MATCH (x)-[:DERIVED_FROM]->(src)
RETURN labels(x)[0] AS kind, x.id AS id, i.variable + ' ' + t.operator + ' ' + toString(t.value) + coalesce(' ' + t.unit, '') AS threshold,
       v.name AS represents, coalesce(toString(v.limit), toString(v.target)) AS limitOrTarget, collect(DISTINCT coalesce(src.ref, src.name)) AS source
ORDER BY represents, threshold;
