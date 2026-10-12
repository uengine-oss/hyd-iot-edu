// 결과/후보.json 에서 승인된 후보와 관계를 출처와 함께 그래프 DB 에 넣는 문장이다.
// python 반영.py 가 만든 파일이다. 사람이 읽어 본 뒤 python 반영.py 넣기 로 넣는다.
// 두 번 넣어도 노드와 관계가 늘지 않는다.
// 넣는 후보: K-001, K-002, K-003, K-004, K-005, K-006, K-007
// 넣는 관계: R-001, R-002, R-003, R-004

// 문서 HM-8
MERGE (d:KnowledgeSource {id: 'HM-8'})
SET d.name = '유압 파워유닛 쿨러 팬 정비 매뉴얼', d.kind = 'manual', d.ref = 'HM-8', d._manual_document = 'HM-8';
// 절 HM-8.4
MERGE (s:ManualSection {id: 'HM-8.4'})
SET s.ref = 'HM-8.4', s.title = '쿨러 냉각 성능 상실 — 원인과 확인 증거', s._manual_document = 'HM-8';
MATCH (s:ManualSection {id: 'HM-8.4'}), (d:KnowledgeSource {id: 'HM-8'})
MERGE (s)-[r:PART_OF]->(d)
SET r._manual_document = 'HM-8';
// 절 HM-8.5
MERGE (s:ManualSection {id: 'HM-8.5'})
SET s.ref = 'HM-8.5', s.title = '즉시 완화 조치', s._manual_document = 'HM-8';
MATCH (s:ManualSection {id: 'HM-8.5'}), (d:KnowledgeSource {id: 'HM-8'})
MERGE (s)-[r:PART_OF]->(d)
SET r._manual_document = 'HM-8';
// 절 HM-8.7
MERGE (s:ManualSection {id: 'HM-8.7'})
SET s.ref = 'HM-8.7', s.title = '근본 조치', s._manual_document = 'HM-8';
MATCH (s:ManualSection {id: 'HM-8.7'}), (d:KnowledgeSource {id: 'HM-8'})
MERGE (s)-[r:PART_OF]->(d)
SET r._manual_document = 'HM-8';
// 절 HM-8.8
MERGE (s:ManualSection {id: 'HM-8.8'})
SET s.ref = 'HM-8.8', s.title = '금지와 제한', s._manual_document = 'HM-8';
MATCH (s:ManualSection {id: 'HM-8.8'}), (d:KnowledgeSource {id: 'HM-8'})
MERGE (s)-[r:PART_OF]->(d)
SET r._manual_document = 'HM-8';

// K-001 Cause 쿨러 핀 오염
// 그래프에 이미 있는 노드다. 새로 만들지 않고 출처와 단계만 덧붙인다.
MATCH (a:Cause {id: 'cause:cooler-fin-fouling'}), (b:ManualSection {id: 'HM-8.4'})
MERGE (a)-[r:REFERS_TO {citation: '- 쿨러 핀 오염(먼지 · 유막으로 핀이 막힘)이 가장 흔하다(사전 확률 0.6). 최근 30초 냉각 효율 평균이 70 % 미만이고, 최근 2분 팬 진동 VS1 평균이 0.9 mm/s 미만(팬은 정상)이면 핀 오염으로 판정한다. 관련 부품은 쿨러 코어다.'}]->(b)
SET r._manual_document = 'HM-8';

// K-002 Cause 주변 온도 상승
MERGE (n:Cause {id: 'cause:ambient-temperature-rise'})
SET n.name = '주변 온도 상승', n._manual_document = 'HM-8';
MATCH (a:Cause {id: 'cause:ambient-temperature-rise'}), (b:ManualSection {id: 'HM-8.4'})
MERGE (a)-[r:REFERS_TO {citation: '- 주변 온도 상승(외기 고온 · 캐비닛 환기 불량)은 사전 확률 0.2로 본다. 최근 2분 캐비닛 온도 TS4 평균이 35 ℃ 이상이면 외기 고온으로 판정한다.'}]->(b)
SET r._manual_document = 'HM-8';

// K-003 Cause 팬 구동 불량
MERGE (n:Cause {id: 'cause:fan-drive-fault'})
SET n.name = '팬 구동 불량', n._manual_document = 'HM-8';
MATCH (a:Cause {id: 'cause:fan-drive-fault'}), (b:ManualSection {id: 'HM-8.4'})
MERGE (a)-[r:REFERS_TO {citation: '- 팬 구동 불량(벨트 슬립 · 베어링 마모)은 사전 확률 0.2로 본다. 최근 2분 팬 진동 VS1 평균이 0.9 mm/s 이상이면 HM-8.1 점검으로 넘어간다.'}]->(b)
SET r._manual_document = 'HM-8';

// K-004 Skill 팬 최대 운전
// 그래프에 이미 있는 노드다. 새로 만들지 않고 출처와 단계만 덧붙인다.
MATCH (a:Skill {id: 'skill:fan-maximum-run'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO {citation: '### SOP-COOL-11 팬 최대 운전'}]->(b)
SET r._manual_document = 'HM-8';
// K-004 단계 1
MERGE (n:Step {id: 'step:fan-maximum-run/1'})
SET n.order = 1, n.text = 'PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', n.citation = '1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run'}), (b:Step {id: 'step:fan-maximum-run/1'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:fan-maximum-run/1'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-004 단계 2
MERGE (n:Step {id: 'step:fan-maximum-run/2'})
SET n.order = 2, n.text = '팬 속도를 100 %로 올린다. 100 % 연속 운전은 24시간 이내로 한다.', n.citation = '2. 팬 속도를 100 %로 올린다. 100 % 연속 운전은 24시간 이내로 한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run'}), (b:Step {id: 'step:fan-maximum-run/2'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:fan-maximum-run/2'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-004 단계 3
MERGE (n:Step {id: 'step:fan-maximum-run/3'})
SET n.order = 3, n.text = '15분 재관측으로 HM-8.6 회복 판정을 한다.', n.citation = '3. 15분 재관측으로 HM-8.6 회복 판정을 한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run'}), (b:Step {id: 'step:fan-maximum-run/3'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:fan-maximum-run/3'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-004 조건 1 (금지)
MATCH (a:Skill {id: 'skill:fan-maximum-run'}), (b:ManualSection {id: 'HM-8.8'})
MERGE (a)-[r:REFERS_TO {citation: '- 원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.'}]->(b)
SET r.kind = '금지', r.text = '원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.', r._manual_document = 'HM-8';

// K-005 Skill 팬 최대 운전과 부하 80 %
MERGE (n:Skill {id: 'skill:fan-maximum-run-and-load-80-percent'})
SET n.name = '팬 최대 운전과 부하 80 %', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run-and-load-80-percent'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO {citation: '### SOP-COOL-12 팬 최대 운전과 부하 80 %'}]->(b)
SET r._manual_document = 'HM-8';
// K-005 단계 1
MERGE (n:Step {id: 'step:fan-maximum-run-and-load-80-percent/1'})
SET n.order = 1, n.text = 'PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', n.citation = '1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run-and-load-80-percent'}), (b:Step {id: 'step:fan-maximum-run-and-load-80-percent/1'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:fan-maximum-run-and-load-80-percent/1'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-005 단계 2
MERGE (n:Step {id: 'step:fan-maximum-run-and-load-80-percent/2'})
SET n.order = 2, n.text = '팬 속도를 100 %로 올린다.', n.citation = '2. 팬 속도를 100 %로 올린다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run-and-load-80-percent'}), (b:Step {id: 'step:fan-maximum-run-and-load-80-percent/2'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:fan-maximum-run-and-load-80-percent/2'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-005 단계 3
MERGE (n:Step {id: 'step:fan-maximum-run-and-load-80-percent/3'})
SET n.order = 3, n.text = '펌프 부하를 80 %로 낮춘다.', n.citation = '3. 펌프 부하를 80 %로 낮춘다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run-and-load-80-percent'}), (b:Step {id: 'step:fan-maximum-run-and-load-80-percent/3'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:fan-maximum-run-and-load-80-percent/3'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-005 단계 4
MERGE (n:Step {id: 'step:fan-maximum-run-and-load-80-percent/4'})
SET n.order = 4, n.text = '15분 재관측으로 HM-8.6 회복 판정을 한다.', n.citation = '4. 15분 재관측으로 HM-8.6 회복 판정을 한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:fan-maximum-run-and-load-80-percent'}), (b:Step {id: 'step:fan-maximum-run-and-load-80-percent/4'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:fan-maximum-run-and-load-80-percent/4'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-005 조건 1 (금지)
MATCH (a:Skill {id: 'skill:fan-maximum-run-and-load-80-percent'}), (b:ManualSection {id: 'HM-8.8'})
MERGE (a)-[r:REFERS_TO {citation: '- 원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.'}]->(b)
SET r.kind = '금지', r.text = '원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.', r._manual_document = 'HM-8';

// K-006 Skill 부하 70 %와 야간 핀 세척
MERGE (n:Skill {id: 'skill:load-70-percent-and-night-fin-cleaning'})
SET n.name = '부하 70 %와 야간 핀 세척', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:load-70-percent-and-night-fin-cleaning'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO {citation: '### SOP-COOL-13 부하 70 %와 야간 핀 세척'}]->(b)
SET r._manual_document = 'HM-8';
// K-006 단계 1
MERGE (n:Step {id: 'step:load-70-percent-and-night-fin-cleaning/1'})
SET n.order = 1, n.text = 'PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', n.citation = '1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:load-70-percent-and-night-fin-cleaning'}), (b:Step {id: 'step:load-70-percent-and-night-fin-cleaning/1'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:load-70-percent-and-night-fin-cleaning/1'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-006 단계 2
MERGE (n:Step {id: 'step:load-70-percent-and-night-fin-cleaning/2'})
SET n.order = 2, n.text = '펌프 부하를 70 %로 낮춘다. 팬 속도는 그대로 둔다.', n.citation = '2. 펌프 부하를 70 %로 낮춘다. 팬 속도는 그대로 둔다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:load-70-percent-and-night-fin-cleaning'}), (b:Step {id: 'step:load-70-percent-and-night-fin-cleaning/2'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:load-70-percent-and-night-fin-cleaning/2'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-006 단계 3
MERGE (n:Step {id: 'step:load-70-percent-and-night-fin-cleaning/3'})
SET n.order = 3, n.text = '15분 재관측으로 HM-8.6 회복 판정을 한다.', n.citation = '3. 15분 재관측으로 HM-8.6 회복 판정을 한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:load-70-percent-and-night-fin-cleaning'}), (b:Step {id: 'step:load-70-percent-and-night-fin-cleaning/3'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:load-70-percent-and-night-fin-cleaning/3'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-006 단계 4
MERGE (n:Step {id: 'step:load-70-percent-and-night-fin-cleaning/4'})
SET n.order = 4, n.text = '야간 예정된 정비 시간에 SOP-COOL-14 핀 세척 작업지시를 건다.', n.citation = '4. 야간 예정된 정비 시간에 SOP-COOL-14 핀 세척 작업지시를 건다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:load-70-percent-and-night-fin-cleaning'}), (b:Step {id: 'step:load-70-percent-and-night-fin-cleaning/4'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:load-70-percent-and-night-fin-cleaning/4'}), (b:ManualSection {id: 'HM-8.5'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-006 조건 1 (금지)
MATCH (a:Skill {id: 'skill:load-70-percent-and-night-fin-cleaning'}), (b:ManualSection {id: 'HM-8.8'})
MERGE (a)-[r:REFERS_TO {citation: '- 원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.'}]->(b)
SET r.kind = '금지', r.text = '원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.', r._manual_document = 'HM-8';

// K-007 Skill 쿨러 핀 세척
MERGE (n:Skill {id: 'skill:cooler-fin-cleaning'})
SET n.name = '쿨러 핀 세척', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:cooler-fin-cleaning'}), (b:ManualSection {id: 'HM-8.7'})
MERGE (a)-[r:REFERS_TO {citation: '### SOP-COOL-14 쿨러 핀 세척'}]->(b)
SET r._manual_document = 'HM-8';
// K-007 단계 1
MERGE (n:Step {id: 'step:cooler-fin-cleaning/1'})
SET n.order = 1, n.text = '설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.', n.citation = '1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:cooler-fin-cleaning'}), (b:Step {id: 'step:cooler-fin-cleaning/1'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:cooler-fin-cleaning/1'}), (b:ManualSection {id: 'HM-8.7'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-007 단계 2
MERGE (n:Step {id: 'step:cooler-fin-cleaning/2'})
SET n.order = 2, n.text = '압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.', n.citation = '2. 압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:cooler-fin-cleaning'}), (b:Step {id: 'step:cooler-fin-cleaning/2'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:cooler-fin-cleaning/2'}), (b:ManualSection {id: 'HM-8.7'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';
// K-007 단계 3
MERGE (n:Step {id: 'step:cooler-fin-cleaning/3'})
SET n.order = 3, n.text = '재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.', n.citation = '3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.', n._manual_document = 'HM-8';
MATCH (a:Skill {id: 'skill:cooler-fin-cleaning'}), (b:Step {id: 'step:cooler-fin-cleaning/3'})
MERGE (a)-[r:HAS_STEP]->(b)
SET r._manual_document = 'HM-8';
MATCH (a:Step {id: 'step:cooler-fin-cleaning/3'}), (b:ManualSection {id: 'HM-8.7'})
MERGE (a)-[r:REFERS_TO]->(b)
SET r._manual_document = 'HM-8';

// R-001 CAUSES cause:cooler-fin-fouling → fm:cooler-cooling-performance-loss
// 그래프에 이미 있는 관계다. 새로 만들지 않고 출처만 더한다.
MATCH (a:Cause {id: 'cause:cooler-fin-fouling'})-[r:CAUSES]->(b:FailureMode {id: 'fm:cooler-cooling-performance-loss'})
SET r.source = 'HM-8.4', r.citation = '- 쿨러 핀 오염(먼지 · 유막으로 핀이 막힘)이 가장 흔하다(사전 확률 0.6). 최근 30초 냉각 효율 평균이 70 % 미만이고, 최근 2분 팬 진동 VS1 평균이 0.9 mm/s 미만(팬은 정상)이면 핀 오염으로 판정한다. 관련 부품은 쿨러 코어다.';

// R-002 CAUSES cause:ambient-temperature-rise → fm:cooler-cooling-performance-loss
MATCH (a:Cause {id: 'cause:ambient-temperature-rise'}), (b:FailureMode {id: 'fm:cooler-cooling-performance-loss'})
MERGE (a)-[r:CAUSES]->(b)
SET r.source = 'HM-8.4', r.citation = '- 주변 온도 상승(외기 고온 · 캐비닛 환기 불량)은 사전 확률 0.2로 본다. 최근 2분 캐비닛 온도 TS4 평균이 35 ℃ 이상이면 외기 고온으로 판정한다.', r._manual_document = 'HM-8';

// R-003 CAUSES cause:fan-drive-fault → fm:cooler-cooling-performance-loss
MATCH (a:Cause {id: 'cause:fan-drive-fault'}), (b:FailureMode {id: 'fm:cooler-cooling-performance-loss'})
MERGE (a)-[r:CAUSES]->(b)
SET r.source = 'HM-8.4', r.citation = '- 팬 구동 불량(벨트 슬립 · 베어링 마모)은 사전 확률 0.2로 본다. 최근 2분 팬 진동 VS1 평균이 0.9 mm/s 이상이면 HM-8.1 점검으로 넘어간다.', r._manual_document = 'HM-8';

// R-004 RELATED_TO cause:cooler-fin-fouling → part:p-clr-core
// 그래프에 이미 있는 관계다. 새로 만들지 않고 출처만 더한다.
MATCH (a:Cause {id: 'cause:cooler-fin-fouling'})-[r:RELATED_TO]->(b:Part {id: 'part:p-clr-core'})
SET r.source = 'HM-8.4', r.citation = '- 쿨러 핀 오염(먼지 · 유막으로 핀이 막힘)이 가장 흔하다(사전 확률 0.6). 최근 30초 냉각 효율 평균이 70 % 미만이고, 최근 2분 팬 진동 VS1 평균이 0.9 mm/s 미만(팬은 정상)이면 핀 오염으로 판정한다. 관련 부품은 쿨러 코어다.';
