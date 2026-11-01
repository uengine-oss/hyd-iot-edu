// hyd-iot-edu 온톨로지 v2 인스턴스 — schema.json(스키마)에 맞춰 만든 가상 기업 "경남유압"의 기준 데이터.
// kg-seed(seed.sh)가 시작할 때마다 constraints.cypher 다음, scenario_structure.cypher · pm_capabilities.cypher 앞에 적재한다.
// 대상은 모두 id로 적고 MERGE · SET만 쓴다 — 몇 번을 적재해도 그래프가 같다(그때 그래프에 있는 「전부」를 잇는 문장을 쓰지 않는다).
// 금액은 만원. 규정은 교육용 예시이며 실제 조문이 아니다.
// 고장 유형 · 원인 · 증거 · 조치(SOP) · 매뉴얼 규칙은 여기 넣지 않는다 — 수업 문서(HM-8 · PM-02 · PR-07) 적재가 만든다(scripts/class_knowledge.py).
// 업무 흐름(어떤 순서로 무엇을 하는지)은 실행 정의가 정본이다(수업 흐름 · it/process/definitions). 여기에는 프로세스를 객체(이름 · 목표 · 대상 설비)로만 둔다.
// 순서: 1 가치(BSC) → 2 리소스 → 3 판단 입력 → 4 설비 진단(이상 패턴 · 증상) → 5 조치 · 규칙(DMN) → 6 프로세스 → 7 외부 변수 → 8 지운 시드 정리

// ============================================================== 1. 가치 계층 (BSC)
UNWIND [['persp:learning','학습과 성장',1],['persp:internal','내부 프로세스',2],['persp:customer','고객',3],['persp:financial','재무',4]] AS r
MERGE (n:Perspective {id: r[0]}) SET n.name = r[1], n.order = r[2];

UNWIND [['obj:profit','영업이익 확대','persp:financial','매출을 늘리고 비용을 줄여 이익을 키운다.'],
        ['obj:cost','원가 절감','persp:financial','보전 · 에너지 · 부품 · 재고 · 지체상금 비용을 줄인다.'],
        ['obj:delivery','납기 신뢰','persp:customer','약속한 날짜에 약속한 수량을 출하한다.'],
        ['obj:quality','품질 신뢰','persp:customer','클레임 없이 고객 브랜드 신뢰를 지킨다.'],
        ['obj:availability','설비 가용성 확보','persp:internal','계획되지 않은 정지 없이 설비를 돌린다.'],
        ['obj:safety','무재해 운전','persp:internal','인터록 한계를 넘지 않는다. 금액과 맞바꾸지 않는다.'],
        ['obj:energy','에너지 효율','persp:internal','같은 생산량을 적은 전력으로 만든다.'],
        ['obj:knowledge','현장 판단 지식 축적','persp:learning','사람의 판단과 사유를 남겨 다음 판단에 쓴다.']] AS r
MERGE (n:Objective {id: r[0]}) SET n.name = r[1], n.description = r[3]
WITH n, r MATCH (p:Perspective {id: r[2]}) MERGE (n)-[:IN_PERSPECTIVE]->(p);

UNWIND [['obj:knowledge','obj:availability'],['obj:safety','obj:availability'],['obj:availability','obj:delivery'],
        ['obj:energy','obj:cost'],['obj:delivery','obj:profit'],['obj:quality','obj:profit'],['obj:cost','obj:profit']] AS r
MATCH (a:Objective {id: r[0]}), (b:Objective {id: r[1]}) MERGE (a)-[:SUPPORTS]->(b);

UNWIND [['dept:plant','공장 경영'],['dept:production','생산팀'],['dept:maintenance','설비보전팀'],['dept:purchasing','구매팀'],
        ['dept:quality','품질팀'],['dept:sales','영업팀'],['dept:energy','환경안전 · 에너지팀']] AS r
MERGE (n:OrgUnit {id: r[0]}) SET n.name = r[1];

// BSC 성과 지표: [id, name, aliases, unit, direction, objective, owner, formula, target, frequency, kpiRole]
// formula는 다른 성과 지표의 합 · 차다(id 그대로) — 성과 지표 화면(process kpi.py)이 이 식으로 합성 지표를 계산한다.
// kpiRole(BSC, Kaplan·Norton): lagging = 결과 지표(재무·고객 관점의 성과, 전략맵의 끝), leading = 선행 동인 지표(내부 프로세스·
// 학습 관점의 동인, INFLUENCES 경로로 결과 지표를 움직인다). 규칙: 후행 지표는 선행 지표에 INFLUENCES하지 않고, 모든 선행
// 지표는 INFLUENCES 경로로 후행 지표에 닿는다 (seed_checks.cypher가 적재마다 검사한다).
UNWIND [
  ['msr:op-profit','영업이익',['이익','수익','수익률'],'만원/월','UP','obj:profit','dept:plant','msr:revenue - msr:cost',null,'월','lagging'],
  ['msr:revenue','매출',['매출액'],'만원/월','UP','obj:profit','dept:sales',null,null,'월','lagging'],
  ['msr:cost','총비용',['비용','원가'],'만원/월','DOWN','obj:cost','dept:plant','msr:maint-cost + msr:energy-cost + msr:part-cost + msr:inventory-cost + msr:penalty',null,'월','lagging'],
  ['msr:maint-cost','보전비',['정비비','수리비'],'만원/월','DOWN','obj:cost','dept:maintenance',null,null,'월','lagging'],
  ['msr:energy-cost','에너지비',['전기요금','전력비'],'만원/월','DOWN','obj:cost','dept:energy',null,null,'월','lagging'],
  ['msr:part-cost','부품 구매비',['구매비'],'만원/월','DOWN','obj:cost','dept:purchasing',null,null,'월','lagging'],
  ['msr:inventory-cost','재고 보관비',['보관비','창고비'],'만원/월','DOWN','obj:cost','dept:production',null,null,'월','lagging'],
  ['msr:penalty','지체상금',['납기 위약금'],'만원/월','DOWN','obj:cost','dept:sales',null,0,'월','lagging'],
  ['msr:otd','납기 준수율',['납기','OTD'],'%','UP','obj:delivery','dept:sales',null,98,'주','lagging'],
  ['msr:quality-claim','품질 클레임',['클레임','불량 유출'],'건/월','DOWN','obj:quality','dept:quality',null,0,'월','lagging'],
  ['msr:brand','브랜드 신뢰',['브랜드','고객 신뢰'],'지수','UP','obj:quality','dept:sales',null,80,'분기','lagging'],
  ['msr:availability','설비 가동률',['가동률','가용성'],'%','UP','obj:availability','dept:production',null,95,'일','leading'],
  ['msr:throughput','생산량',['생산 속도','처리량'],'ea/h','UP','obj:availability','dept:production',null,120,'실시간','leading'],
  ['msr:mtbf','평균 고장 간격',['MTBF','설비 신뢰성'],'h','UP','obj:availability','dept:maintenance',null,2000,'월','leading'],
  ['msr:oil-life','작동유 잔여 수명',['작동유 수명','오일 수명'],'%','UP','obj:availability','dept:maintenance',null,null,'주','leading'],
  ['msr:safety-margin','인터록 여유',['안전 여유','트립 여유'],'℃','UP','obj:safety','dept:production',null,10,'실시간','leading'],
  ['msr:energy-use','전력 사용량',['전력량','에너지 사용'],'kWh/일','DOWN','obj:energy','dept:energy',null,null,'일','leading'],
  ['msr:inventory','재고량',['완제품 재고','재고'],'ea','DOWN','obj:cost','dept:production',null,null,'일','leading'],
  ['msr:part-price','부품 단가',['부품가'],'만원/개','DOWN','obj:cost','dept:purchasing',null,null,'건','leading'],
  ['msr:part-quality','부품 품질',['부품 신뢰도'],'지수','UP','obj:quality','dept:purchasing',null,null,'분기','leading'],
  ['msr:precedent','판단 선례 축적',['선례','판단 사례'],'건','UP','obj:knowledge','dept:plant',null,null,'월','leading']
] AS r
MERGE (n:Measure {id: r[0]}) SET n.name = r[1], n.aliases = r[2], n.unit = r[3], n.direction = r[4], n.formula = r[7], n.target = r[8], n.frequency = r[9], n.kpiRole = r[10]
WITH n, r MATCH (o:Objective {id: r[5]}), (d:OrgUnit {id: r[6]}) MERGE (n)-[:MEASURES]->(o) MERGE (n)-[:OWNED_BY]->(d);
MATCH (n:Measure {id:'msr:safety-margin'}) SET n.thresholdWarn = 5, n.thresholdCrit = 0;

// 상충 관계 (성과 지표 → 성과 지표). 대표 설명의 예시를 그대로 담았다.
//   매출 ↑ → 이익 ↑ / 비용 ↑ → 이익 ↓ / 재고 ↑ → 보관비 ↑ → 비용 ↑ / 재고와 매출은 관계없음 → 관계를 만들지 않는다
//   부품 단가 ↓ → 구매비 ↓ → 비용 ↓ (이익 ↑) 이지만 부품 단가 ↓ → 부품 품질 ↓ → 클레임 ↑ → 브랜드 ↓ → 매출 ↓ (이익 ↓)
UNWIND [
  ['msr:revenue','msr:op-profit',1,'high','매출에서 비용을 뺀 것이 이익'],
  ['msr:cost','msr:op-profit',-1,'high','매출에서 비용을 뺀 것이 이익'],
  ['msr:maint-cost','msr:cost',1,'medium',null],
  ['msr:energy-cost','msr:cost',1,'medium',null],
  ['msr:part-cost','msr:cost',1,'medium',null],
  ['msr:inventory-cost','msr:cost',1,'low',null],
  ['msr:penalty','msr:cost',1,'high',null],
  ['msr:inventory','msr:inventory-cost',1,'medium','재고가 쌓이면 보관 비용이 오른다. 재고량과 매출은 직접 관계가 없어 선을 긋지 않는다'],
  ['msr:part-price','msr:part-cost',1,'high','단가가 오르면 구매비가 오른다'],
  ['msr:part-price','msr:part-quality',1,'medium','싼 부품(비승인 · 저가)은 품질이 낮은 경향'],  // 조건: 아래 SET 참고
  ['msr:part-quality','msr:quality-claim',-1,'medium',null],
  ['msr:part-quality','msr:mtbf',1,'medium','부품 고장률이 낮으면 고장 간격이 길다'],
  ['msr:quality-claim','msr:brand',-1,'high',null],
  ['msr:quality-claim','msr:cost',1,'medium','클레임 처리 비용'],
  ['msr:brand','msr:revenue',1,'medium','브랜드가 떨어지면 수주가 준다'],
  ['msr:otd','msr:brand',1,'medium',null],
  ['msr:otd','msr:penalty',-1,'high','납기를 지키면 지체상금이 없다'],
  ['msr:throughput','msr:otd',1,'high',null],
  ['msr:throughput','msr:revenue',1,'medium','팔 물건을 만든다'],
  ['msr:availability','msr:throughput',1,'high','멈추면 못 만든다'],
  ['msr:mtbf','msr:availability',1,'medium',null],
  ['msr:mtbf','msr:maint-cost',-1,'medium','고장이 적으면 보전비가 준다'],
  ['msr:oil-life','msr:mtbf',1,'low','작동유가 열화하면 펌프 · 밸브 마모가 빨라진다'],
  ['msr:oil-life','msr:maint-cost',-1,'low','작동유 교환 비용'],
  ['msr:safety-margin','msr:availability',1,'high','여유가 0이 되면 인터록 트립으로 정지'],
  ['msr:energy-use','msr:energy-cost',1,'high',null],
  ['msr:precedent','msr:availability',1,'low','현장 판단 지식이 쌓이면 대응이 빨라진다']
] AS r
MATCH (a:Measure {id: r[0]}), (b:Measure {id: r[1]})
MERGE (a)-[i:INFLUENCES]->(b) SET i.sign = r[2], i.strength = r[3], i.note = r[4];
// 단가와 품질의 관계는 "공급사를 바꿔 단가를 낮출 때"만 성립한다. 같은 부품의 시세(환율 등) 변동으로는 품질이 바뀌지 않는다.
MATCH (:Measure {id:'msr:part-price'})-[i:INFLUENCES]->(:Measure {id:'msr:part-quality'}) SET i.condition = '공급사를 바꿔 단가를 낮출 때 (같은 부품의 시세 변동에는 해당 없음)';

// ============================================================== 2. 리소스 계층
// 역할: [id, name, org unit, level]. 구매 담당(L1)은 예비품 구매 카드(시나리오 C)를 승인한다.
UNWIND [['role:operator','운전원','dept:production',1],['role:prod-mgr','생산관리자','dept:production',2],
        ['role:maint-mgr','설비보전팀장','dept:maintenance',2],['role:purchasing','구매 담당','dept:purchasing',1],
        ['role:purchasing-mgr','구매팀장','dept:purchasing',2],['role:quality-mgr','품질팀장','dept:quality',2],
        ['role:plant-mgr','공장장','dept:plant',3]] AS r
MERGE (n:Role {id: r[0]}) SET n.name = r[1], n.level = r[3]
WITH n, r MATCH (d:OrgUnit {id: r[2]}) MERGE (n)-[:MEMBER_OF]->(d);

UNWIND [['sys:scada','SCADA · PLC (설비 제어)','OT'],['sys:historian','공정 이력 저장소 (Historian)','IT'],['sys:agent','AI 에이전트','IT'],
        ['sys:process','처리 엔진 (사람 승인 · 실행)','IT'],['sys:cep','이상 감지기 (CEP)','IT'],['sys:mes','MES','IT'],['sys:erp','ERP','IT'],['sys:cmms','CMMS','IT'],['sys:scm','SCM 구매 포털','IT'],['sys:qms','QMS 품질 시스템','IT']] AS r
MERGE (n:System {id: r[0]}) SET n.name = r[1], n.zone = r[2];

// 설비 3대는 같은 구조다. 구성 요소 노드는 형식(타입) 수준이라 세 설비가 같은 노드를 가진다(HAS_COMPONENT N:M — 어느 호기의 일인지는 사건의 ON_ASSET이 정한다).
UNWIND [['asset:hyd-01','HYD-01'],['asset:hyd-02','HYD-02'],['asset:hyd-03','HYD-03']] AS r
MERGE (a:Asset {id: r[0]}) SET a.code = r[1], a.name = r[1] + ' 유압 파워팩',
  a.forecastModel = 'hydraulic-lumped-simulator-v1', a.forecastRevision = '1.1',
  a.forecastScope = '교육용 HYD 시뮬레이터 — 입력을 고정한 열린 루프 기준 예측', a.forecastHorizonS = 900;
UNWIND [['comp:cooler','오일 쿨러',['쿨러','열교환기']],['comp:fan','쿨러 팬',['팬','송풍기']],['comp:pump-a','주 펌프 (A)',['펌프','유압 펌프']],
        ['comp:pump-b','예비 펌프 (B)',['스탠바이 펌프']],['comp:motor','구동 모터',['모터']],['comp:tank','작동유 탱크',['탱크','리저버']]] AS r
MERGE (n:Component {id: r[0]}) SET n.name = r[1], n.aliases = r[2]
WITH n UNWIND ['asset:hyd-01','asset:hyd-02','asset:hyd-03'] AS aid
MATCH (a:Asset {id: aid}) MERGE (a)-[:HAS_COMPONENT]->(n);

// [state variable id, name, aliases, unit, kind, normal, limit]. 운전 펌프 선택은 A · B 중 하나를 고르는 값이라 단위가 없다.
UNWIND [['sv:fan-speed','팬 속도',['팬 회전수'],'%','manipulated',60,null],
        ['sv:load','펌프 부하',['부하','생산 속도 설정'],'%','manipulated',90,null],
        ['sv:pump-select','운전 펌프 선택',['펌프 전환'],'-','manipulated',null,null],
        ['sv:ts1','유온',['오일 온도','작동유 온도','TS1'],'℃','controlled',48,65],
        ['sv:ce','냉각 효율',['쿨러 효율','CE'],'%','controlled',84,null],
        ['sv:ps1','토출 압력',['펌프 압력','PS1'],'bar','controlled',182,130],
        ['sv:fs1','유량',['토출 유량','FS1'],'l/min','controlled',9,null],
        ['sv:vs1','팬 진동',['진동','VS1'],'mm/s','controlled',0.6,2.0],
        ['sv:leak','펌프 내부 누설',['누설률'],'%','disturbance',0,null],
        ['sv:fouling','쿨러 핀 오염도',['핀 막힘','오염'],'%','disturbance',0,null],
        ['sv:bearing-wear','팬 베어링 마모도',['베어링 마모'],'%','disturbance',0,null]] AS r
MERGE (n:StateVariable {id: r[0]}) SET n.name = r[1], n.aliases = r[2], n.unit = r[3], n.kind = r[4], n.normal = r[5], n.limit = r[6];

UNWIND [['sen:ts1','유온 센서','TS1','℃',false,'comp:cooler','sv:ts1'],['sen:ce','냉각 효율 (가상)','CE','%',true,'comp:cooler','sv:ce'],
        ['sen:ps1','토출 압력 센서','PS1','bar',false,'comp:pump-a','sv:ps1'],['sen:fs1','유량 센서','FS1','l/min',false,'comp:pump-a','sv:fs1'],
        ['sen:vs1','팬 진동 센서','VS1','mm/s',false,'comp:fan','sv:vs1']] AS r
MERGE (n:Sensor {id: r[0]}) SET n.name = r[1], n.tag = r[2], n.unit = r[3], n.virtual = r[4]
WITH n, r MATCH (c:Component {id: r[5]}), (v:StateVariable {id: r[6]}) MERGE (c)-[:MONITORED_BY]->(n) MERGE (n)-[:OBSERVES]->(v);

UNWIND [['actr:fan-drive','팬 인버터','FanSpeedSP',0,100,'comp:fan','sv:fan-speed'],
        ['actr:pump-drive','펌프 부하 설정','LoadSP',60,100,'comp:motor','sv:load'],
        ['actr:pump-selector','펌프 전환 밸브','PumpSelect',null,null,'comp:pump-b','sv:pump-select']] AS r
MERGE (n:Actuator {id: r[0]}) SET n.name = r[1], n.resource = r[2], n.min = r[3], n.max = r[4]
WITH n, r MATCH (c:Component {id: r[5]}), (v:StateVariable {id: r[6]}) MERGE (c)-[:ACTUATED_BY]->(n) MERGE (n)-[:MANIPULATES]->(v);
MATCH (c:Component {id:'comp:pump-a'}), (n:Actuator {id:'actr:pump-selector'}) MERGE (c)-[:ACTUATED_BY]->(n);

// 물리 영향 (상태 변수 → 상태 변수 → Measure). 설비 모델의 식과 같은 방향이다.
UNWIND [
  ['sv:fan-speed','sv:ts1',-1,'high',null,'팬을 올리면 냉각이 늘어 유온이 내려간다'],
  ['sv:fan-speed','sv:vs1',1,'medium','베어링 마모 시 크게','팬이 빠를수록 진동이 크다'],
  ['sv:load','sv:ts1',1,'high',null,'부하의 제곱에 비례해 발열'],
  ['sv:load','sv:ps1',1,'medium',null,null],
  ['sv:ce','sv:ts1',-1,'high',null,null],
  ['sv:fouling','sv:ce',-1,'high',null,'핀이 막히면 냉각 효율이 떨어진다'],
  ['sv:leak','sv:ps1',-1,'high',null,'내부 누설만큼 토출 압력이 떨어진다'],
  ['sv:leak','sv:fs1',-1,'high',null,null],
  ['sv:leak','sv:ts1',1,'low',null,'누설 유량이 열이 된다'],
  ['sv:bearing-wear','sv:vs1',1,'high',null,null],
  ['sv:ts1','msr:oil-life',-1,'medium','유온 60 ℃ 이상에서 크게','고온 운전은 작동유를 열화시킨다'],
  ['sv:ts1','msr:safety-margin',-1,'high',null,'인터록 65 ℃까지의 여유'],
  ['sv:vs1','msr:mtbf',-1,'medium',null,null],
  ['sv:vs1','msr:availability',-1,'high','VS1 ≥ 2.0 mm/s 진동 인터록',null],
  ['sv:ps1','msr:throughput',1,'medium','PS1 < 165 bar에서 사이클 지연',null],
  ['sv:ps1','msr:availability',1,'high','PS1 < 130 bar 저압 인터록',null],
  ['sv:fs1','msr:throughput',1,'medium','FS1 < 8.0 l/min에서 사이클 지연(유량 → 액추에이터 속도)',null],
  ['sv:load','msr:throughput',1,'high',null,'부하가 곧 생산 속도'],
  ['sv:load','msr:energy-use',1,'medium',null,null],
  ['sv:fan-speed','msr:energy-use',1,'low',null,'팬 전력']
] AS r
MATCH (a {id: r[0]}), (b {id: r[1]})
MERGE (a)-[i:INFLUENCES]->(b) SET i.sign = r[2], i.strength = r[3], i.condition = r[4], i.note = r[5];

// 부품: [id, name, partNo, 쓰는 구성 요소]. 리턴 필터 엘리먼트는 정기 정비 2,000 h 패키지 부품(작동유 탱크 리턴 라인, 시나리오 B)이다.
UNWIND [['part:cooler-core','쿨러 코어','P-CLR-CORE','comp:cooler'],['part:pump-seal','펌프 축 씰 키트','P-PMP-SEAL','comp:pump-a'],
        ['part:fan-bearing','팬 베어링','P-FAN-BRG','comp:fan'],['part:return-filter','리턴 필터 엘리먼트','P-RTN-FLT','comp:tank']] AS r
MERGE (n:Part {id: r[0]}) SET n.name = r[1], n.partNo = r[2]
WITH n, r MATCH (c:Component {id: r[3]}) MERGE (c)-[:USES_PART]->(n);
// 공급사(Supplier: 이름 · 승인 여부 avl · 순정 여부 oem)와 부품별 견적(SUPPLIED_BY)은 여기 두지 않는다 — 정본은 업무 DB(ent.suppliers · ent.quote_rows)이고
// 처리 엔진이 그래프로 옮긴다(procsvc/scm_sync: 시작 뒤 60초마다, 수업 지식 적재 전 한 번 — scripts/class_knowledge.py가 POST /api/kg/scm-sync).

// 회사가 정한 기준 문서(교육용 예시). 수업 문서(HM-8 · PM-02 · PR-07)의 출처는 적재가 만든다.
UNWIND [['ks:sr-04','설비안전규정 SR-04 (교육용 예시)','regulation','SR-04'],
        ['ks:strategy-map','경남유압 BSC 전략맵','strategy','BSC-2026'],
        ['ks:pm-plan','정기 정비 계획 기준 (회사 설정, 교육용 예시)','policy','PM-PLAN'],
        ['ks:monitoring-standard','감시 임계값 회사 설정값 (수업 문서에 없음, 교육용 예시)','policy','MON-SET'],
        // 수업 문서에 있는 감지 기준은 그 문서의 절 번호(ref)로 가리킨다. 적재가 만드는 절 노드에 바로 잇지 못하는 까닭: 절 · 문서 노드 id 가
        // PC 마다 다르고(manual:<테넌트 해시>:<적재 uuid>:…), 적재 때 서명 묶음 밖의 관계를 더하면 강사 서명 지식이 아니게 된다(재서명 = 사용자 결정, RUNBOOK §7).
        ['ks:monitoring-hm-8','쿨러 감시 기준 — 수업 문서 HM-8 「HM-8.3 냉각 성능 판정 기준」의 값 (경보 55 ℃ · 냉각 효율 70 % · 정상 52 ℃ · 인터록 65 ℃)','policy','HM-8.3'],
        ['ks:monitoring-pm-02','펌프 누설 감시 기준 — 토출 압력 165 bar · 유량 8.0 l/min 은 수업 문서 PM-02 「PM-2.10 정기 정비가 막는 고장」의 값','policy','PM-2.10'],
        ['ks:monitoring-pm-02-fan','팬 진동 감시 기준 — 1.2 mm/s 는 수업 문서 PM-02 「PM-2.9 시운전 확인」의 정상 경계(팬 진동 VS1 1.2 mm/s 미만)','policy','PM-2.9'],
        ['ks:monitoring-pr-07','예비품 재고 경보 기준 — 수업 문서 PR-07 「PR-7.2 적정 재고와 재주문점」 (가용 재고가 재주문점 아래)','policy','PR-7.2']] AS r
MERGE (n:KnowledgeSource {id: r[0]}) SET n.name = r[1], n.kind = r[2], n.ref = r[3];

// ============================================================== 3. 판단 입력
// 판단 · 이상 패턴이 검사하는 데이터: [id, name, typeRef, variable, source, represents]. 값은 실행 중에 출처(시스템 · 센서)에서 온다.
UNWIND [['in:pattern','경보 패턴','string','pattern','sys:cep',null],
        ['in:failure-mode','판정 고장 유형','string','failure_mode','sys:agent',null],
        ['in:cause','판정 원인','string','cause','sys:agent',null],
        ['in:ts1','유온','number','ts1','sen:ts1','sv:ts1'],['in:ts1-slope','유온 상승률','number','ts1_slope','sys:cep','sv:ts1'],
        ['in:ce','냉각 효율','number','ce','sen:ce','sv:ce'],
        ['in:ps1','토출 압력','number','ps1','sen:ps1','sv:ps1'],['in:fs1','유량','number','fs1','sen:fs1','sv:fs1'],
        ['in:load','펌프 부하 설정','number','load','sys:scada','sv:load'],
        ['in:vs1','팬 진동','number','vs1','sen:vs1','sv:vs1'],['in:vs1-slope','진동 상승률','number','vs1_slope','sys:cep','sv:vs1'],
        ['in:plc-mode','PLC 운전 모드','enum','plc_mode','sys:scada',null],['in:plc-state','PLC 상태','enum','plc_state','sys:scada',null],
        ['in:forecast-ts1','조치 후 예측 유온','number','forecast_ts1','sys:agent','sv:ts1'],
        ['in:forecast-ps1','조치 후 예측 토출 압력','number','forecast_ps1','sys:agent','sv:ps1'],
        ['in:skill-kind','후보 스킬 종류','enum','skill_kind','sys:agent',null],
        ['in:skill-code','후보 스킬의 명령 코드','string','skill_code','sys:agent',null],
        ['in:fan100-hours','팬 100 % 연속 운전 시간','number','fan100_hours','sys:historian','sv:fan-speed'],
        ['in:standby-ready','예비 펌프 가용','boolean','standby_ready','sys:cmms',null],
        ['in:order-due','긴급 오더 남은 시간','number','order_due_h','sys:mes','msr:otd'],
        ['in:order-penalty','납기 지연 시 시간당 보상','number','order_penalty_per_h','sys:erp','msr:penalty'],
        ['in:order-tier','고객 등급','string','order_customer_tier','sys:erp',null],
        ['in:hot-lot-claim','고온 구간 출하 대기 로트의 클레임 위험 (만원)','number','hot_lot_claim','sys:qms','msr:quality-claim'],
        ['in:hot-lot-qty','고온 구간 출하 대기 수량','number','hot_lot_qty','sys:qms',null],
        ['in:supplier-avl','공급사 승인 여부','boolean','supplier_avl','sys:scm',null],
        ['in:oil-analysis','오일 분석 결과 (기준 이탈 여부)','boolean','oil_analysis_out_of_spec','sys:cmms',null]] AS r
MERGE (n:InputData {id: r[0]}) SET n.name = r[1], n.typeRef = r[2], n.variable = r[3]
WITH n, r MATCH (src {id: r[4]}) MERGE (n)-[:SOURCED_FROM]->(src)
WITH n, r OPTIONAL MATCH (x {id: r[5]}) WHERE x:StateVariable OR x:Measure
FOREACH (_ IN CASE WHEN x IS NULL THEN [] ELSE [1] END | MERGE (n)-[:REPRESENTS]->(x));

// ============================================================== 4. 설비 진단 (ISO 13374): 이상 패턴 → 증상
// 증상: [id, name, aliases, 관측 센서, note]. 오일 분석 기준 이탈은 실시간 센서가 없고 사람이 정기 분석 결과를 입력한다.
UNWIND [['sym:ts1-rise','유온 상승',['온도 상승','과열'],['sen:ts1'],null],
        ['sym:ce-drop','냉각 효율 저하',['냉각 불량'],['sen:ce'],null],
        ['sym:ps1-drop','토출 압력 저하',['압력 저하','압력 떨어짐'],['sen:ps1'],null],
        ['sym:fs1-drop','유량 저하',['유량 감소'],['sen:fs1'],null],
        ['sym:vs1-rise','진동 증가',['떨림','소음'],['sen:vs1'],null],
        ['sym:oil-analysis-out-of-spec','오일 분석 기준 이탈',['TAN 상승','수분 2,500 ppm 초과','ISO 4406 등급 2단계 악화','점도 변화'],[],
         '실시간 센서가 없다. 정기 오일 분석(점도 · 산가 TAN · 수분 Karl Fischer · 청정도 ISO 4406) 결과를 사람이 입력한다.']] AS r
MERGE (n:Symptom {id: r[0]}) SET n.name = r[1], n.aliases = r[2], n.note = r[4]
WITH n, r UNWIND r[3] AS sid MATCH (s:Sensor {id: sid}) MERGE (n)-[:OBSERVED_BY]->(s);

// 설비 · PLC · 사람 입력 이상 패턴 하나가 한 행이다: [id, name, code, holdSeconds, detectionMode, 검사, 덧붙임 설명, 해제(held만), 증상, 감지 기준 출처]
//   검사 = TESTS 행 [input, 식에 쓰는 이름, operator, value, unit] — 한 패턴의 검사는 모두 AND다. 사람이 읽는 조건(rule)은 이 행에서 만든다
//          (손으로 따로 적은 문장이 TESTS와 어긋날 수 없게). 감지기는 TESTS만 실행한다(it/detector/det/patterns.py).
//   (행 끝 = 감지 기준의 출처 KnowledgeSource 목록 — 아래 근거 출처)
//   detectionMode: held = 감지기가 TESTS 지속 조건으로 감지하고 해제 = [clearRule, clearHoldSeconds, slopeWindowSeconds, severity]로 푼다.
//                  plc-trip = PLC가 보호 정지(TRIP)를 내고 감지기는 PLC 사유를 패턴 코드로 그대로 전한다(it/detector/det/cep.py) — 덧붙임이 PLC 인터록 기준.
//                  null = 사람이 입력하는 경보(오일 분석 결과).
//   해제 기준은 경보 기준보다 안쪽이다(히스테리시스 — 쿨러 55/52 ℃, 펌프 165/168 bar, 팬 1.2/1.1 mm/s; HM-8.3 정상 52 ℃ 미만 · 경보 55 ℃ 초과).
//   근거 출처(행 끝 출처 목록 → DERIVED_FROM): 쿨러 값(경보 55 ℃ · 냉각 효율 70 % · 해제 52 ℃)과 과열 인터록 65 ℃는 수업 문서 HM-8.3(ks:monitoring-hm-8),
//   펌프 누설의 토출 압력 165 bar · 유량 8.0 l/min 은 PM-02 PM-2.10(ks:monitoring-pm-02)에 있다. 팬 진동 경보 1.2 mm/s 는 PM-02 PM-2.9 시운전 확인의 정상 경계(ks:monitoring-pm-02-fan)다.
//   펌프 누설의 부하 80 % · 해제 168 bar, 팬 진동 해제 1.1 mm/s, 저압 130 bar, 진동 인터록 2.0 mm/s, 오일 분석 기준은 어느 수업 문서에도 없는
//   회사 설정이다(ks:monitoring-standard).
//   시간은 설비 시간(초)이고 감지기가 TIME_SCALE 배속으로 잰다. 값은 적재마다 이 행으로 맞춘다 — 기존 PC도 다음 시작에 같은 기준이 된다.
UNWIND [
  ['pattern:cooler-degradation','쿨러 성능 저하','COOLER_DEGRADATION',60,'held',
    [['in:ts1','TS1','>',55,'℃'],['in:ce','CE','<',70,'%'],['in:ts1-slope','slope(TS1)','>',0,'℃/s']],null,
    ['TS1 < 52 and slope(TS1) <= 0',60,60,'HIGH'],['sym:ts1-rise','sym:ce-drop'],['ks:monitoring-hm-8']],
  ['pattern:pump-leakage','펌프 내부 누설','PUMP_LEAKAGE',60,'held',
    [['in:plc-state','PLC.state','==','RUN',null],['in:ps1','PS1','<',165,'bar'],['in:fs1','FS1','<',8.0,'l/min'],['in:load','LoadSP','>=',80,'%']],null,
    ["PLC.state == 'RUN' and ((PS1 >= 168 and FS1 >= 8) or LoadSP < 80)",60,60,'HIGH'],['sym:ps1-drop','sym:fs1-drop'],['ks:monitoring-pm-02','ks:monitoring-standard']],
  ['pattern:fan-vibration','팬 진동 상승','FAN_VIBRATION',60,'held',
    [['in:vs1','VS1','>',1.2,'mm/s'],['in:vs1-slope','slope(VS1)','>',0,'mm/s²']],null,
    ['VS1 < 1.1',60,60,'HIGH'],['sym:vs1-rise'],['ks:monitoring-pm-02-fan','ks:monitoring-standard']],
  ['pattern:overheat-trip','과열 인터록 트립','OVERHEAT_TRIP',0,'plc-trip',
    [['in:plc-state','PLC.state','==','TRIP',null]],'PLC 과열 인터록: 유온 65 ℃ 이상',null,['sym:ts1-rise'],['ks:monitoring-hm-8']],
  ['pattern:low-pressure-trip','저압 인터록 트립','LOW_PRESSURE_TRIP',0,'plc-trip',
    [['in:plc-state','PLC.state','==','TRIP',null]],'PLC 저압 인터록: 토출 압력 130 bar 미만',null,['sym:ps1-drop'],['ks:monitoring-standard']],
  ['pattern:high-vibration-trip','고진동 인터록 트립','HIGH_VIBRATION_TRIP',0,'plc-trip',
    [['in:plc-state','PLC.state','==','TRIP',null]],'PLC 진동 인터록: 팬 진동 2.0 mm/s 이상',null,['sym:vs1-rise'],['ks:monitoring-standard']],
  ['pattern:oil-analysis','오일 분석 기준 이탈 (사람 입력)','OIL_ANALYSIS',0,null,
    [['in:oil-analysis','오일 분석 기준 이탈','==',true,null]],'사람 입력: TAN 2 이상 상승 · 수분 2,500 ppm 초과 · ISO 4406 2단계 악화 · 점도 등급 이탈 중 하나',null,['sym:oil-analysis-out-of-spec'],['ks:monitoring-standard']]
] AS r
MERGE (p:AnomalyPattern {id: r[0]})
SET p.name = r[1], p.code = r[2], p.holdSeconds = r[3], p.detectionMode = r[4],
    p.rule = reduce(s = '', t IN r[5] | s + CASE WHEN s = '' THEN '' ELSE ' and ' END + t[1] + ' ' + t[2] + ' '
                    + CASE WHEN t[3] IS :: STRING THEN "'" + t[3] + "'" ELSE toString(t[3]) END)
             + CASE WHEN r[6] IS NULL THEN '' ELSE ' (' + r[6] + ')' END,
    p.clearRule = r[7][0], p.clearHoldSeconds = r[7][1], p.slopeWindowSeconds = r[7][2], p.severity = r[7][3]
WITH p, r
OPTIONAL MATCH (p)-[old:TESTS]->(gone:InputData) WHERE gone.ns IS NULL AND NOT gone.id IN [t IN r[5] | t[0]]
DELETE old
WITH DISTINCT p, r
OPTIONAL MATCH (p)-[old:DETECTS]->(gone:Symptom) WHERE gone.ns IS NULL AND NOT gone.id IN r[8]
DELETE old
WITH DISTINCT p, r
CALL (p, r) { UNWIND r[5] AS t MATCH (i:InputData {id: t[0]}) MERGE (p)-[x:TESTS]->(i) SET x.operator = t[2], x.value = t[3], x.unit = t[4] }
CALL (p, r) { UNWIND r[8] AS sid MATCH (s:Symptom {id: sid}) MERGE (p)-[:DETECTS]->(s) }
WITH DISTINCT p, r
OPTIONAL MATCH (p)-[old:DERIVED_FROM]->(gone:KnowledgeSource) WHERE gone.ns IS NULL AND coalesce(gone.kind, '') <> 'manual' AND NOT gone.id IN r[9]
DELETE old
WITH DISTINCT p, r
UNWIND r[9] AS kid MATCH (k:KnowledgeSource {id: kid}) MERGE (p)-[:DERIVED_FROM]->(k);

// ============================================================== 5. 조치 · 규칙 계층 (DMN)
// 원자 조치: [id, name, code, kind, param, min, max, target]. code는 cmd-gateway 허용 목록, param은 action.cmd의 값 키다.
UNWIND [['action:set-fan','팬 속도 설정','FAN_SET','command','fan_pct',0,100,'actr:fan-drive'],
        ['action:set-load','펌프 부하 설정','LOAD_SET','command','load_pct',60,100,'actr:pump-drive'],
        ['action:select-pump','운전 펌프 전환','PUMP_SELECT','command','pump',null,null,'actr:pump-selector'],
        ['action:raise-pressure','압력 설정 상향','PRESSURE_SET','command','pressure_delta',0,20,'actr:pump-drive'],
        ['action:controlled-stop','계획 정지','STOP','command',null,null,null,'actr:pump-drive'],
        ['action:reset','인터록 리셋','RESET','command',null,null,null,'actr:pump-drive'],
        ['action:work-order','정비 작업지시 발행','WO_CREATE','transaction','sop',null,null,'sys:cmms'],
        ['action:purchase-request','부품 구매요청','PR_CREATE','transaction','supplier',null,null,'sys:erp']] AS r
MERGE (n:Action {id: r[0]}) SET n.name = r[1], n.code = r[2], n.kind = r[3], n.param = r[4], n.min = r[5], n.max = r[6]
WITH n, r MATCH (t {id: r[7]}) MERGE (n)-[:TARGETS]->(t);

// 판단 정의: [id, name, question, table, hitPolicy, inputs, knowledge sources]. 정기 정비 · 구매 판단의 입력은 scenario_structure.cypher가 더한다.
UNWIND [
  ['dec:diagnose-cause','고장 유형 · 원인 판정','이 경보의 고장 유형과 근본 원인은 무엇인가?','dt:diagnose-cause','PRIORITY',['in:pattern','in:ts1','in:ce','in:ps1'],[]],
  ['dec:action-candidates','조치 후보 선택','이 고장 유형에 쓸 수 있는 조치 방법(스킬 = SOP)은 무엇인가? (원인 한정 스킬은 원인으로 거른다)','dt:action-candidates','COLLECT',['in:failure-mode','in:cause','in:plc-state','in:pattern'],[]],
  ['dec:compliance','규정 적합성','후보 스킬 중 규정상 쓸 수 없거나 감점할 것은 무엇인가?','dt:compliance','COLLECT',['in:skill-kind','in:skill-code','in:failure-mode','in:plc-mode','in:plc-state','in:forecast-ts1','in:forecast-ps1','in:fan100-hours','in:standby-ready','in:supplier-avl'],['ks:sr-04']],
  ['dec:rank-actions','조치 우선순위','남은 후보 중 회사 가치(영업이익)에 가장 유리한 순서는?','dt:rank-actions','UNIQUE',['in:forecast-ts1','in:order-due','in:order-penalty','in:order-tier','in:hot-lot-claim','in:hot-lot-qty'],['ks:strategy-map']]
] AS r
MERGE (d:Decision {id: r[0]}) SET d.name = r[1], d.question = r[2]
MERGE (t:DecisionTable {id: r[3]}) SET t.name = r[1] + ' 결정표', t.hitPolicy = r[4]
MERGE (d)-[:IMPLEMENTED_BY]->(t)
WITH d, r CALL (d, r) { UNWIND r[5] AS iid MATCH (i:InputData {id: iid}) MERGE (d)-[:REQUIRES_INPUT]->(i) }
CALL (d, r) { UNWIND r[6] AS kid MATCH (k:KnowledgeSource {id: kid}) MERGE (d)-[:GOVERNED_BY]->(k) };
UNWIND [['dec:action-candidates','dec:diagnose-cause'],['dec:compliance','dec:action-candidates'],['dec:rank-actions','dec:compliance']] AS r
MATCH (a:Decision {id: r[0]}), (b:Decision {id: r[1]}) MERGE (a)-[:REQUIRES_DECISION]->(b);

// 회사 규칙 = 결정표의 한 행: [id, table, order, effect, annotation, sources, tests[[input, operator, value, unit]]].
// 한 행의 검사는 모두 AND다. 사람이 읽는 조건(when)은 TESTS에서 만든다(문서 적재 규칙과 같은 모양 — manual_knowledge.when_text). 검사가 없으면 'true'.
// 매뉴얼에서 온 진단 · 후보 · 규정 규칙은 문서 적재가 만든다. 구매 승인 공급사 규정은 수업 문서 PR-07의 규칙(rule:pr07-approved-supplier-only)이다.
UNWIND [
  ['rule:ts1-hard','dt:compliance',2,'EXCLUDE','예측 유온이 인터록 한계 이상이면 제외 (모든 제어 후보에 예측값으로 적용)',['ks:sr-04'],
    [['in:forecast-ts1','>=',65,'℃']]],
  ['rule:rank-value','dt:rank-actions',1,'RANK','점수 = 성과 득실(스킬 → 처음 닿는 성과 지표까지 경로마다 강도의 곱 — high 1 · medium 0.6 · low 0.3, 조건부 경로는 절반) + 예측 유온 여유 (55 − 예측)/3 (±2 한도) − 경고 0.5 − 감점/20 + 선례 비율 × 1.5 + 납기 긴급도((24 − 남은 h)/24 × 지연 보상/100, 0~1) × 생산 영향(유지 +1 · 감산 +0.4 · 정지 −1) × 1.5 − 품질 위험(고온 구간 출하 대기 로트가 있고 예측 유온 ≥ 55 ℃ 면 클레임/1000, ≤ 1) × 1.5. 제외된 카드는 뒤로, 동점이면 승인 직급이 낮은 쪽',['ks:strategy-map'],[]]
] AS r
MERGE (n:Rule {id: r[0]}) SET n.order = r[2], n.effect = r[3], n.annotation = r[4], n.penalty = null
WITH n, r MATCH (t:DecisionTable {id: r[1]}) MERGE (t)-[:HAS_RULE]->(n)
WITH n, r CALL (n, r) { UNWIND r[5] AS src MATCH (k:KnowledgeSource {id: src}) MERGE (n)-[:DERIVED_FROM]->(k) }
WITH n, r
OPTIONAL MATCH (n)-[old:TESTS]->(gone:InputData) WHERE NOT gone.id IN [t IN r[6] | t[0]]
DELETE old
WITH DISTINCT n, r
CALL (n, r) {
  UNWIND r[6] AS t MATCH (i:InputData {id: t[0]}) MERGE (n)-[x:TESTS]->(i) SET x.operator = t[1], x.value = t[2], x.unit = t[3]
  RETURN collect(i.variable + ' ' + t[1] + ' ' + CASE WHEN t[2] IS :: STRING THEN "'" + t[2] + "'" ELSE toString(t[2]) END) AS parts
}
SET n.when = CASE WHEN size(parts) = 0 THEN 'true' ELSE reduce(s = '', p IN parts | s + CASE WHEN s = '' THEN '' ELSE ' and ' END + p) END;

// 순위 정책(실행되는 식, hydcommon.ranking이 검사한다). 그래프에서 이 값을 바꾸는 편집 기능은 없다 — 적재마다 이 값으로 맞춘다(저장소에서 고치면 기존 PC도 다음 시작에 같아진다).
MATCH (r:Rule {id: 'rule:rank-value'})
SET r.rankingPolicy = '{"version":1,"inputs":{"due":"order_due_h","penalty":"order_penalty_per_h","claim":"hot_lot_claim","qty":"hot_lot_qty"},"components":{"bsc":"bsc_gain + 0.5 * bsc_conditional_gain - bsc_loss - 0.5 * bsc_conditional_loss","forecast":"0 if forecast_ts1 is None else clamp((55 - forecast_ts1) / 3, -2, 2)","warn":"-0.5 * warning_count","penalty":"-penalty_total / 20","precedent":"1.5 * precedent_share","delivery":"(0 if due is None or penalty is None or penalty <= 0 else round(clamp((24 - due) / 24, 0, 1) * clamp(penalty / 100, 0, 1), 2)) * (1 if production == \'keep\' else (0.4 if production == \'reduce\' else -1)) * 1.5","quality":"0 if claim is None or claim <= 0 or (qty is not None and qty <= 0) or forecast_ts1 is None or forecast_ts1 < 55 else -1.5 * round(min(1, claim / 1000), 2)"},"tieBreak":"lower_approver"}';

// ============================================================== 6. 프로세스 (객체: 이름 · 달성 목표 · 대상 설비)
// 처리 순서 · 담당 · 분기 조건은 실행 정의가 정본이다. 배포된 정의의 판본은 처리 엔진이 ProcessVersion으로 투영한다(execution_graph).
UNWIND [['proc:anomaly-response','설비 이상 조치',true,['obj:availability','obj:safety','obj:delivery']],
        ['proc:maintenance-wo','정비 작업지시',false,['obj:availability','obj:cost']],
        ['proc:alert-triage','미지원 경보 현장 검토',true,['obj:safety']]] AS r
MERGE (p:Process {id: r[0]}) SET p.name = r[1], p.isExecutable = r[2]
WITH p, r CALL (p, r) { UNWIND r[3] AS oid MATCH (o:Objective {id: oid}) MERGE (p)-[:ACHIEVES]->(o) }
WITH p UNWIND ['asset:hyd-01','asset:hyd-02','asset:hyd-03'] AS aid
MATCH (a:Asset {id: aid}) MERGE (p)-[:ACTS_ON]->(a);

// ============================================================== 7. 외부 변수
UNWIND [['ext:fx','원/달러 환율',['환율'],'원/USD','한국은행'],['ext:ambient','외기 온도',['기온','폭염'],'℃','기상청'],
        ['ext:power-tariff','전력 단가',['전기요금 단가'],'원/kWh','한전'],['ext:demand','고객 수요',['수주','주문량'],'ea/월','영업 수요예측']] AS r
MERGE (n:ExternalVariable {id: r[0]}) SET n.name = r[1], n.aliases = r[2], n.unit = r[3], n.source = r[4];
// 환율: 수입 부품가 ↑ (확실), 매출 · 재고는 가격 정책에 따라 달라지는 조건부 영향
UNWIND [['ext:fx','msr:part-price',1,'high',null,'수입 부품 원가가 오른다'],
        ['ext:fx','msr:revenue',-1,'medium','가격 정책 PP-01: 원가 상승분을 판가에 반영하지 않을 때','원가가 올라 판가를 못 올리면 매출 이익이 준다'],
        ['ext:fx','msr:inventory',1,'low','가격 정책 PP-01: 판가를 올려 판매가 줄 때','팔리지 않은 재고가 쌓인다'],
        ['ext:ambient','sv:ts1',1,'medium',null,'외기가 더우면 냉각 여유가 준다'],
        ['ext:power-tariff','msr:energy-cost',1,'high',null,null],
        ['ext:demand','msr:revenue',1,'high',null,null],
        ['ext:demand','msr:inventory',-1,'medium',null,'수요가 늘면 재고가 빠진다']] AS r
MATCH (a:ExternalVariable {id: r[0]}), (b {id: r[1]})
MERGE (a)-[i:INFLUENCES]->(b) SET i.sign = r[2], i.strength = r[3], i.condition = r[4], i.note = r[5];

// ============================================================== 8. 지운 시드 정리 (2026-10-30)
// 시드에서 지운 노드가 이미 적재된 그래프(학생 PC의 Neo4j 볼륨)에 남지 않게 id로 지운다. 지운 까닭:
//   손으로 옮겨 적은 업무 흐름 사본(흐름 노드 18개 — 순서의 정본은 실행 정의, 온톨로지는 객체 모델) · 문서 적재 규칙과 겹친
//   구매 규정 사본(rule:avl, 출처 ks:pr-07) · 절이 없는 매뉴얼 출처(ks:manual-hm) · 아무것과도 잇지 않은 가격 정책(ks:pricing) ·
//   어느 판단도 읽지 않는 사람 선택 입력(in:chosen-skill). 실행 투영의 흐름 노드(id 'flow:…', ProcessVersion 소속)는 건드리지 않는다.
MATCH (n:FlowNode) WHERE n.id IN ['ev:alert','task:diagnose','task:candidates','task:compliance','task:rank','task:select','ev:select-timeout',
                                  'task:escalate','gw:control','task:command','task:reobserve','gw:recovered','task:work-order','ev:closed',
                                  'ev:escalated','ev:unhandled-alert','task:triage','ev:review-recorded']
  AND NOT EXISTS { (:ProcessVersion)-[:HAS_NODE]->(n) }
DETACH DELETE n;
MATCH (n) WHERE (n:Rule AND n.id = 'rule:avl') OR (n:KnowledgeSource AND n.id IN ['ks:pr-07','ks:manual-hm','ks:pricing'])
             OR (n:InputData AND n.id = 'in:chosen-skill')
DETACH DELETE n;
// 스키마에서 지운 클래스(Forecast — 조치별 예측은 설비 모델이 계산한다)의 고유 제약. constraints.cypher(생성 파일)는 지금 클래스의 제약만 만든다.
DROP CONSTRAINT v2_forecast_id IF EXISTS;
// 옛 판이 「그때 있는 프로세스 · 설비 전부」를 이은 선 중 학생 이름 공간 노드에 그은 것은 학생이 직접 그은 선과 구별할 수 없어 지우지 않는다.
