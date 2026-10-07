// hyd-iot-edu 온톨로지 v2 인스턴스 — schema.json(스키마)에 맞춰 만든 가상 기업 "경남유압"의 데이터.
// 먼저 constraints.cypher를 실행한 뒤 이 파일을 실행한다. MERGE만 쓰므로 여러 번 실행해도 같다.
// 금액은 만원. 규정 · 매뉴얼은 교육용 예시이며 실제 조문이 아니다.
// 순서: 1 가치(BSC) → 2 리소스 → 3 설비 진단 → 4 스킬 · 규칙(DMN) → 5 프로세스(BPMN) → 6 외부 변수 · 예측 → 7 운영 기록(예시)

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
// kpiRole(BSC, Kaplan·Norton): lagging = 결과 지표(재무·고객 관점의 성과, 전략맵의 끝), leading = 선행 동인 지표(내부 프로세스·
// 학습 관점의 동인, INFLUENCES 경로로 결과 지표를 움직인다). 규칙: 후행 지표는 선행 지표에 INFLUENCES하지 않고, 모든 선행
// 지표는 INFLUENCES 경로로 후행 지표에 닿는다 (scripts/ontology_v2.py integrity · probe_semantic_links Q23).
UNWIND [
  ['msr:op-profit','영업이익',['이익','수익','수익률'],'만원/월','UP','obj:profit','dept:plant','msr:revenue - kpi:cost',null,'월','lagging'],
  ['msr:revenue','매출',['매출액'],'만원/월','UP','obj:profit','dept:sales',null,null,'월','lagging'],
  ['msr:cost','총비용',['비용','원가'],'만원/월','DOWN','obj:cost','dept:plant','msr:maint-cost + kpi:energy-cost + kpi:part-cost + kpi:inventory-cost + kpi:penalty',null,'월','lagging'],
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
UNWIND [['role:operator','운전원','dept:production',1],['role:prod-mgr','생산관리자','dept:production',2],
        ['role:maint-mgr','설비보전팀장','dept:maintenance',2],['role:purchasing-mgr','구매팀장','dept:purchasing',2],
        ['role:quality-mgr','품질팀장','dept:quality',2],['role:plant-mgr','공장장','dept:plant',3]] AS r
MERGE (n:Role {id: r[0]}) SET n.name = r[1], n.level = r[3]
WITH n, r MATCH (d:OrgUnit {id: r[2]}) MERGE (n)-[:MEMBER_OF]->(d);

UNWIND [['sys:scada','SCADA · PLC (cmd-gateway 경유)','OT'],['sys:historian','Historian (TimescaleDB)','IT'],['sys:agent','AI 에이전트','IT'],
        ['sys:process','HITL 프로세스 서비스','IT'],['sys:cep','CEP 탐지기 (Flink 대체)','IT'],['sys:mes','MES','IT'],['sys:erp','ERP','IT'],['sys:cmms','CMMS','IT'],['sys:scm','SCM 구매 포털','IT'],['sys:qms','QMS 품질 시스템','IT']] AS r
MERGE (n:System {id: r[0]}) SET n.name = r[1], n.zone = r[2];

// 설비 3대는 같은 구조다. 구성 요소 노드는 형식(타입) 수준으로 공유한다.
UNWIND [['asset:hyd-01','HYD-01'],['asset:hyd-02','HYD-02'],['asset:hyd-03','HYD-03']] AS r
MERGE (a:Asset {id: r[0]}) SET a.code = r[1], a.name = r[1] + ' 유압 파워팩',
  a.forecastModel = 'hydraulic-lumped-simulator-v1', a.forecastRevision = '1.0',
  a.forecastScope = 'HYD teaching simulator; constant-input open-loop nominal prediction', a.forecastHorizonS = 900;
UNWIND [['comp:cooler','오일 쿨러',['쿨러','열교환기']],['comp:fan','쿨러 팬',['팬','송풍기']],['comp:pump-a','주 펌프 (A)',['펌프','유압 펌프']],
        ['comp:pump-b','예비 펌프 (B)',['스탠바이 펌프']],['comp:motor','구동 모터',['모터']],['comp:tank','작동유 탱크',['탱크','리저버']]] AS r
MERGE (n:Component {id: r[0]}) SET n.name = r[1], n.aliases = r[2]
WITH n MATCH (a:Asset) MERGE (a)-[:HAS_COMPONENT]->(n);

// [state variable id, name, aliases, unit, kind, normal, limit]
UNWIND [['sv:fan-speed','팬 속도',['팬 회전수'],'%','manipulated',60,null],
        ['sv:load','펌프 부하',['부하','생산 속도 설정'],'%','manipulated',90,null],
        ['sv:pump-select','운전 펌프 선택',['펌프 전환'],'A|B','manipulated',null,null],
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
  ['sv:load','msr:throughput',1,'high',null,'부하가 곧 생산 속도'],
  ['sv:load','msr:energy-use',1,'medium',null,null],
  ['sv:fan-speed','msr:energy-use',1,'low',null,'팬 전력']
] AS r
MATCH (a {id: r[0]}), (b {id: r[1]})
MERGE (a)-[i:INFLUENCES]->(b) SET i.sign = r[2], i.strength = r[3], i.condition = r[4], i.note = r[5];

UNWIND [['part:cooler-core','쿨러 코어','P-CLR-CORE','comp:cooler'],['part:pump-seal','펌프 축 씰 키트','P-PMP-SEAL','comp:pump-a'],
        ['part:fan-bearing','팬 베어링','P-FAN-BRG','comp:fan']] AS r
MERGE (n:Part {id: r[0]}) SET n.name = r[1], n.partNo = r[2]
WITH n, r MATCH (c:Component {id: r[3]}) MERGE (c)-[:USES_PART]->(n);
UNWIND [['sup:a','A정밀 (저가)',true],['sup:b','B-OEM (순정)',true],['sup:c','C트레이딩 (최저가 · 비승인)',false]] AS r
MERGE (n:Supplier {id: r[0]}) SET n.name = r[1], n.avl = r[2];
UNWIND [['part:pump-seal','sup:a',35,0.12,2],['part:pump-seal','sup:b',55,0.02,5],['part:pump-seal','sup:c',20,0.30,1],
        ['part:fan-bearing','sup:a',18,0.10,1],['part:fan-bearing','sup:b',28,0.03,3],
        ['part:cooler-core','sup:a',180,0.12,3],['part:cooler-core','sup:b',260,0.02,5]] AS r
MATCH (p:Part {id: r[0]}), (s:Supplier {id: r[1]}) MERGE (p)-[x:SUPPLIED_BY]->(s) SET x.price = r[2], x.failRate = r[3], x.leadDays = r[4];

// ============================================================== 3. 설비 진단 지식 (ISO 13374)
UNWIND [['ks:manual-hm','HYD 유압 파워팩 운전 · 정비 매뉴얼','manual','HM rev.3'],
        ['ks:sr-04','설비안전규정 SR-04 (교육용 예시)','regulation','SR-04'],
        ['ks:pr-07','구매규정 PR-07 (교육용 예시)','regulation','PR-07'],
        ['ks:pricing','가격 정책 (교육용 예시)','policy','PP-01'],
        ['ks:strategy-map','경남유압 BSC 전략맵','strategy','BSC-2026']] AS r
MERGE (n:KnowledgeSource {id: r[0]}) SET n.name = r[1], n.kind = r[2], n.ref = r[3];

UNWIND [['HM-3.1','정비를 위한 LOCAL 전환','정비 작업 전 현장 패널에서 LOCAL로 전환하고 원격 명령을 차단한다.'],
        ['HM-3.2','운전 모드와 원격 조치 권한','REMOTE_AUTO에서만 IT 승인 조치를 받는다. 수동 조작이 들어오면 REMOTE_MANUAL로 바뀐다.'],
        ['HM-5.2','예비 펌프 전환','주 펌프 이상 시 예비 펌프로 무부하 전환한다. 전환 후 30초 안에 압력이 회복되어야 한다.'],
        ['HM-5.4','압력 설정 변경 금지','내부 누설이 의심될 때 압력 설정을 올리지 않는다. 씰 손상이 빨라진다.'],
        ['HM-5.6','펌프 축 씰 교체','LOCAL 전환 · 잠금 후 씰 키트를 교체하고 누설 시험을 한다.'],
        ['HM-7.3','팬 증속 운전','쿨러 성능 저하 시 팬을 80~100 %로 올린다. 100 % 연속 운전은 24시간 이내.'],
        ['HM-7.5','냉각 회복 판정','TS1 55 ℃ 미만 · 경보 해제가 15분 유지되면 완화 성공.'],
        ['HM-7.6','쿨러 핀 세척','설비 정지 · LOCAL 전환 후 압축공기로 핀을 세척한다.'],
        ['HM-7.7','캐비닛 환기','캐비닛 온도가 35 ℃ 이상이면 환기 필터를 청소하고 배기 팬을 점검한다.'],
        ['HM-8.1','팬 진동 점검','VS1 1.2 mm/s 초과 시 팬 속도를 낮추고 베어링 소음 · 온도를 확인한다.'],
        ['HM-8.3','팬 베어링 교체','계획 정지 후 베어링을 교체하고 VS1 0.9 mm/s 미만을 확인한다.'],
        ['HM-9.1','부하 저감 운전','펌프 부하는 60 % 미만으로 내리지 않는다 (최소 부하 인터록).'],
        ['HM-9.4','트립 후 재기동','유온 55 ℃ 미만에서만 리셋한다. 원인 조치 없이 재기동하면 재발한다.']] AS r
MERGE (n:ManualSection {id: r[0]}) SET n.ref = r[0], n.title = r[1], n.excerpt = r[2]
WITH n MATCH (k:KnowledgeSource {id:'ks:manual-hm'}) MERGE (n)-[:PART_OF]->(k);

UNWIND [['pattern:cooler-degradation','쿨러 성능 저하','COOLER_DEGRADATION','TS1 > 55 and CE < 70 and slope(TS1) > 0',60],
        ['pattern:pump-leakage','펌프 내부 누설','PUMP_LEAKAGE',"PLC.state == 'RUN' and PS1 < 165 and FS1 < 8.0 and LoadSP >= 80",60],
        ['pattern:fan-vibration','팬 진동 상승','FAN_VIBRATION','VS1 > 1.2 and slope(VS1) > 0',60],
        ['pattern:overheat-trip','과열 인터록 트립','OVERHEAT_TRIP','PLC state == TRIP',0]] AS r
MERGE (n:AnomalyPattern {id: r[0]}) SET n.name = r[1], n.code = r[2], n.rule = r[3], n.holdSeconds = r[4];

UNWIND [['sym:ts1-rise','유온 상승',['온도 상승','과열'],['sen:ts1'],['pattern:cooler-degradation','pattern:overheat-trip']],
        ['sym:ce-drop','냉각 효율 저하',['냉각 불량'],['sen:ce'],['pattern:cooler-degradation']],
        ['sym:ps1-drop','토출 압력 저하',['압력 저하','압력 떨어짐'],['sen:ps1'],['pattern:pump-leakage']],
        ['sym:fs1-drop','유량 저하',['유량 감소'],['sen:fs1'],['pattern:pump-leakage']],
        ['sym:vs1-rise','진동 증가',['떨림','소음'],['sen:vs1'],['pattern:fan-vibration']]] AS r
MERGE (n:Symptom {id: r[0]}) SET n.name = r[1], n.aliases = r[2]
WITH n, r UNWIND r[3] AS sid MATCH (s:Sensor {id: sid}) MERGE (n)-[:OBSERVED_BY]->(s)
WITH DISTINCT n, r UNWIND r[4] AS pid MATCH (p:AnomalyPattern {id: pid}) MERGE (p)-[:DETECTS]->(n);

UNWIND [['fm:cooling-loss','쿨러 냉각 성능 상실','comp:cooler',['sym:ts1-rise','sym:ce-drop']],
        ['fm:volumetric-loss','펌프 체적 효율 저하','comp:pump-a',['sym:ps1-drop','sym:fs1-drop']],
        ['fm:bearing-degradation','팬 베어링 열화','comp:fan',['sym:vs1-rise']],
        ['fm:overheat-trip','과열 정지','comp:motor',['sym:ts1-rise']],
        ['fm:oil-degradation','작동유 열화','comp:tank',[]]] AS r
MERGE (n:FailureMode {id: r[0]}) SET n.name = r[1]
WITH n, r MATCH (c:Component {id: r[2]}) MERGE (n)-[:OCCURS_IN]->(c)
WITH n, r UNWIND (CASE WHEN size(r[3]) = 0 THEN [null] ELSE r[3] END) AS sid
OPTIONAL MATCH (s:Symptom {id: sid}) FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END | MERGE (s)-[:INDICATES]->(n));
UNWIND [['fm:cooling-loss','fm:overheat-trip'],['fm:cooling-loss','fm:oil-degradation'],['fm:volumetric-loss','fm:oil-degradation'],['fm:bearing-degradation','fm:cooling-loss']] AS r
MATCH (a:FailureMode {id: r[0]}), (b:FailureMode {id: r[1]}) MERGE (a)-[:LEADS_TO]->(b);

UNWIND [['cause:cooler-fin-fouling','쿨러 핀 오염 (먼지 · 유막)',['핀 막힘','쿨러 오염'],0.6,'fm:cooling-loss','part:cooler-core'],
        ['cause:high-ambient','주변 온도 상승',['폭염','외기 고온'],0.2,'fm:cooling-loss',null],
        ['cause:pump-seal-wear','펌프 축 씰 마모',['씰 마모','내부 누설'],0.7,'fm:volumetric-loss','part:pump-seal'],
        ['cause:fan-bearing-wear','팬 베어링 마모',['베어링 마모','베어링 손상'],0.8,'fm:bearing-degradation','part:fan-bearing']] AS r
MERGE (n:Cause {id: r[0]}) SET n.name = r[1], n.aliases = r[2], n.prior = r[3]
WITH n, r MATCH (f:FailureMode {id: r[4]}) MERGE (n)-[:CAUSES]->(f)
WITH n, r OPTIONAL MATCH (p:Part {id: r[5]}) FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (n)-[:INVOLVES_PART]->(p));
// 원인은 상태 변수(외란)를 통해 물리 영향 경로에 들어간다
UNWIND [['cause:cooler-fin-fouling','sv:fouling'],['cause:pump-seal-wear','sv:leak'],['cause:fan-bearing-wear','sv:bearing-wear']] AS r
MATCH (c:Cause {id: r[0]}), (v:StateVariable {id: r[1]}) MERGE (c)-[d:DISTURBS]->(v) SET d.sign = 1;

// 증거: [id, cause, name, rule, weight, expect, threshold, sql, tag, windowSeconds]. sql은 %(asset)s 하나를 받아 숫자 하나(value)를 돌려준다.
// tag · windowSeconds는 sql이 읽는 태그와 구간이다. 구간에 수집 계약보다 긴 관측 공백이 있으면 판정하지 않는다(A083).
UNWIND [
  ['evd:ce-low','cause:cooler-fin-fouling','냉각 효율 평균 70 % 미만 (최근 30초)','avg(CE) over 30s < 70',0.6,'lt',70,'SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = \'CE\' AND time > now() - interval \'30 seconds\'','CE',30],
  ['evd:fan-normal','cause:cooler-fin-fouling','팬 진동 정상 (팬 고장 아님)','avg(VS1) over 2m < 0.9',0.4,'lt',0.9,'SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = \'VS1\' AND time > now() - interval \'2 minutes\'','VS1',120],
  ['evd:ambient-high','cause:high-ambient','캐비닛 온도 35 ℃ 이상','avg(TS4) over 2m >= 35',1.0,'gte',35,'SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = \'TS4\' AND time > now() - interval \'2 minutes\'','TS4',120],
  ['evd:ps1-low','cause:pump-seal-wear','토출 압력 평균 165 bar 미만','avg(PS1) over 2m < 165',0.6,'lt',165,'SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = \'PS1\' AND time > now() - interval \'2 minutes\'','PS1',120],
  ['evd:fs1-drop','cause:pump-seal-wear','유량 평균 8.0 l/min 미만','avg(FS1) over 2m < 8.0',0.4,'lt',8.0,'SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = \'FS1\' AND time > now() - interval \'2 minutes\'','FS1',120],
  ['evd:vs1-trend','cause:fan-bearing-wear','진동 상승폭 0.2 mm/s 초과 (최근 5분)','max(VS1) - min(VS1) over 5m > 0.2',0.6,'gt',0.2,'SELECT max(value) - min(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = \'VS1\' AND time > now() - interval \'5 minutes\'','VS1',300],
  ['evd:ts1-normal','cause:fan-bearing-wear','유온 52 ℃ 미만 (냉각 문제 아님)','avg(TS1) over 2m < 52',0.4,'lt',52,'SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = \'TS1\' AND time > now() - interval \'2 minutes\'','TS1',120]
] AS r
MERGE (n:Evidence {id: r[0]}) SET n.name = r[2], n.rule = r[3], n.weight = r[4], n.expect = r[5], n.threshold = r[6], n.sql = r[7], n.tag = r[8], n.windowSeconds = r[9]
WITH n, r MATCH (c:Cause {id: r[1]}) MERGE (c)-[:EVIDENCED_BY]->(n);

// ============================================================== 4. 스킬 · 규칙 계층 (DMN)
// 원자 조치: [id, name, code, kind, param, min, max, target]
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

// 조치 방법 = Skill = SOP. 스킬 하나가 SOP 하나다 (절차 번호 sopId와 단계를 직접 갖는다). 조치 가이드 카드 한 장이 스킬 하나다.
// [id, name, sopId, kind, description, approver, executor, [[action, value]], steps[[text, manual]]]
UNWIND [
  ['skill:fan-max','팬 최대','SOP-COOL-01','control','팬만 100 %로 올린다. 생산은 그대로 유지한다.','role:operator','sys:scada',[['action:set-fan',100]],
    [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.','HM-3.2'],['팬 속도를 100 %로 올린다 (연속 24시간 이내).','HM-7.3'],['15분 재관측: TS1 55 ℃ 미만이고 경보 해제면 완화 성공.','HM-7.5']]],
  ['skill:fan-max-derate','팬 최대 + 부하 80 %','SOP-COOL-02','control','팬 100 %와 부하 80 %로 유온을 확실히 내린다.','role:prod-mgr','sys:scada',[['action:set-fan',100],['action:set-load',80]],
    [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.','HM-3.2'],['팬 속도를 100 %로 올린다.','HM-7.3'],['펌프 부하를 80 %로 낮춘다 (최소 60 %).','HM-9.1'],['15분 재관측: TS1 55 ℃ 미만이고 경보 해제면 완화 성공.','HM-7.5']]],
  ['skill:derate-night-clean','부하 70 % + 야간 세척','SOP-COOL-03','control','팬은 그대로 두고 부하를 70 %로 낮춘 뒤 야간 정비창에 쿨러를 세척한다.','role:prod-mgr','sys:scada',[['action:set-load',70],['action:work-order','SOP-COOL-04']],
    [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.','HM-3.2'],['펌프 부하를 70 %로 낮춘다.','HM-9.1'],['15분 재관측: TS1 55 ℃ 미만이면 완화 성공.','HM-7.5'],['야간 정비창에 쿨러 핀 세척 작업지시(SOP-COOL-04)를 건다.','HM-7.6']]],
  ['skill:wo-cooler-clean','쿨러 핀 세척','SOP-COOL-04','work_order','설비를 세우고 쿨러 핀을 세척한다. CMMS 작업지시로 발행한다.','role:maint-mgr','sys:cmms',[['action:work-order','SOP-COOL-04']],
    [['설비를 정지하고 LOCAL로 전환한다.','HM-3.1'],['압축공기로 핀을 세척한다.','HM-7.6'],['재가동 후 CE 80 % 이상 복귀를 확인한다.','HM-7.5']]],
  ['skill:wo-ventilation','캐비닛 환기 개선','SOP-COOL-05','work_order','외기 고온으로 냉각 여유가 없을 때 캐비닛 환기를 보강한다. CMMS 작업지시로 발행한다.','role:maint-mgr','sys:cmms',[['action:work-order','SOP-COOL-05']],
    [['캐비닛 온도(TS4)와 외기 온도를 기록한다.','HM-7.7'],['환기 필터를 청소하고 배기 팬을 점검한다.','HM-7.7'],['캐비닛 온도가 35 ℃ 아래로 내려왔는지 확인한다.','HM-7.7']]],
  ['skill:switch-standby-pump','예비 펌프 전환','SOP-PMP-01','control','예비 펌프 B로 전환해 압력을 즉시 회복한다.','role:prod-mgr','sys:scada',[['action:select-pump','B']],
    [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.','HM-3.2'],['예비 펌프 B로 무부하 전환한다.','HM-5.2'],['30초 안에 PS1이 175 bar 이상으로 회복됐는지 확인한다.','HM-5.2']]],
  ['skill:derate-70','부하 70 %','SOP-PMP-02','control','부하를 70 %로 낮춰 압력 부족과 누설 진행을 늦춘다.','role:operator','sys:scada',[['action:set-load',70]],
    [['PLC 운전 모드가 REMOTE_AUTO인지 확인한다.','HM-3.2'],['펌프 부하를 70 %로 낮춘다.','HM-9.1'],['PS1 하락이 멈췄는지 10분간 확인한다.','HM-5.2']]],
  ['skill:raise-pressure','압력 설정 상향 (구 절차)','SOP-PMP-03','control','압력 설정을 10 bar 올려 부족분을 메운다. 개정 매뉴얼에서 누설 시 금지된 옛 절차다.','role:operator','sys:scada',[['action:raise-pressure',10]],
    [['압력 설정을 10 bar 올린다. 누설 의심 시에는 금지 (개정 HM-5.4).','HM-5.4'],['PS1이 175 bar 이상인지 확인한다.','HM-5.2']]],
  ['skill:wo-pump-seal','펌프 축 씰 교체','SOP-PMP-04','work_order','씰 키트를 구매요청하고 교체 작업지시를 발행한다.','role:maint-mgr','sys:cmms',[['action:purchase-request','sup:b'],['action:work-order','SOP-PMP-04']],
    [['주 펌프를 LOCAL로 전환하고 잠근다.','HM-3.1'],['씰 키트를 교체한다.','HM-5.6'],['누설 시험 후 주 펌프로 복귀한다.','HM-5.6']]],
  ['skill:fan-slow-derate','팬 40 % + 부하 80 %','SOP-FAN-01','control','팬을 낮춰 진동을 줄이고 부하도 낮춰 유온 상승을 막는다.','role:prod-mgr','sys:scada',[['action:set-fan',40],['action:set-load',80]],
    [['팬 속도를 40 %로 낮춘다.','HM-8.1'],['유온이 55 ℃를 넘지 않도록 부하를 80 %로 낮춘다.','HM-9.1'],['VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.','HM-8.1']]],
  ['skill:fan-slow','팬 40 %','SOP-FAN-02','control','팬만 40 %로 낮춘다. 생산은 그대로 유지한다.','role:operator','sys:scada',[['action:set-fan',40]],
    [['팬 속도를 40 %로 낮춘다.','HM-8.1'],['유온을 15분간 감시한다. 55 ℃를 넘으면 부하를 낮춘다.','HM-7.5'],['VS1이 1.2 mm/s 아래로 내려왔는지 확인한다.','HM-8.1']]],
  ['skill:planned-stop','계획 정지 + 베어링 교체','SOP-FAN-03','control','설비를 계획 정지하고 바로 베어링을 교체한다.','role:plant-mgr','sys:scada',[['action:controlled-stop',1],['action:work-order','SOP-FAN-04']],
    [['생산오더를 마감하고 계획 정지한다.','HM-3.1'],['LOCAL로 전환하고 베어링을 교체한다.','HM-8.3'],['재가동 후 VS1 0.9 mm/s 미만을 확인한다.','HM-8.3']]],
  ['skill:wo-fan-bearing','팬 베어링 교체','SOP-FAN-04','work_order','다음 계획 정지 때 베어링을 교체하도록 CMMS 작업지시를 발행한다.','role:maint-mgr','sys:cmms',[['action:work-order','SOP-FAN-04']],
    [['LOCAL로 전환하고 잠근다.','HM-3.1'],['베어링을 교체한다.','HM-8.3'],['재가동 후 VS1 0.9 mm/s 미만을 확인한다.','HM-8.3']]],
  ['skill:reset-after-cool','냉각 후 리셋','SOP-TRIP-01','control','유온 55 ℃ 미만에서 인터록을 리셋하고 재관측한다.','role:prod-mgr','sys:scada',[['action:reset',1]],
    [['유온이 55 ℃ 미만인지 확인한다.','HM-9.4'],['원인 조치(세척 · 교체) 계획이 있는지 확인한다.','HM-9.4'],['PLC를 리셋하고 재관측한다.','HM-9.4']]]
] AS r
MERGE (n:Skill {id: r[0]}) SET n.name = coalesce(n.name, r[1]), n.sopId = r[2], n.kind = r[3], n.description = coalesce(n.description, r[4])
WITH n, r MATCH (ap:Role {id: r[5]}), (ex:System {id: r[6]})
FOREACH (_ IN CASE WHEN EXISTS { (n)-[:APPROVED_BY]->() } THEN [] ELSE [1] END | MERGE (n)-[:APPROVED_BY]->(ap))
MERGE (ex)-[:HAS_SKILL]->(n)
WITH n, r UNWIND range(0, size(r[7]) - 1) AS i
MATCH (a:Action {id: r[7][i][0]}) MERGE (n)-[c:CONSISTS_OF]->(a) SET c.value = r[7][i][1], c.seq = i + 1
WITH DISTINCT n, r UNWIND range(0, size(r[8]) - 1) AS j
MERGE (st:Step {id: r[2] + '/' + (j + 1)}) SET st.order = j + 1, st.text = coalesce(st.text, r[8][j][0])
MERGE (n)-[:HAS_STEP]->(st)
WITH st, r, j MATCH (m:ManualSection {id: r[8][j][1]}) MERGE (st)-[:REFERS_TO]->(m);
UNWIND [['role:operator',['skill:fan-max','skill:derate-70','skill:fan-slow']],
        ['role:maint-mgr',['skill:wo-cooler-clean','skill:wo-ventilation','skill:wo-pump-seal','skill:wo-fan-bearing']]] AS r
UNWIND r[1] AS sid MATCH (ro:Role {id: r[0]}), (s:Skill {id: sid}) MERGE (ro)-[:HAS_SKILL]->(s);

// 고장 유형 → 조치 방법 (즉시 완화 / 근본 조치). 조치 방법(스킬 = SOP)은 고장 유형에 매칭된다.
UNWIND [['fm:cooling-loss','MITIGATED_BY',['skill:fan-max','skill:fan-max-derate','skill:derate-night-clean']],
        ['fm:cooling-loss','REMEDIED_BY',['skill:wo-cooler-clean','skill:wo-ventilation']],
        ['fm:volumetric-loss','MITIGATED_BY',['skill:switch-standby-pump','skill:derate-70','skill:raise-pressure']],
        ['fm:volumetric-loss','REMEDIED_BY',['skill:wo-pump-seal']],
        ['fm:bearing-degradation','MITIGATED_BY',['skill:fan-slow-derate','skill:fan-slow']],
        ['fm:bearing-degradation','REMEDIED_BY',['skill:planned-stop','skill:wo-fan-bearing']],
        ['fm:overheat-trip','MITIGATED_BY',['skill:reset-after-cool']]] AS r
UNWIND r[2] AS sid MATCH (f:FailureMode {id: r[0]}), (s:Skill {id: sid})
FOREACH (_ IN CASE WHEN r[1] = 'MITIGATED_BY' THEN [1] ELSE [] END | MERGE (f)-[:MITIGATED_BY]->(s))
FOREACH (_ IN CASE WHEN r[1] = 'REMEDIED_BY' THEN [1] ELSE [] END | MERGE (f)-[:REMEDIED_BY]->(s));
// 근본 조치가 특정 원인에만 맞을 때 (같은 냉각 성능 상실이라도 핀 오염이면 세척, 외기 고온이면 환기 개선)
UNWIND [['skill:wo-cooler-clean','cause:cooler-fin-fouling'],['skill:derate-night-clean','cause:cooler-fin-fouling'],
        ['skill:wo-ventilation','cause:high-ambient'],['skill:wo-pump-seal','cause:pump-seal-wear'],
        ['skill:planned-stop','cause:fan-bearing-wear'],['skill:wo-fan-bearing','cause:fan-bearing-wear']] AS r
MATCH (s:Skill {id: r[0]}), (c:Cause {id: r[1]}) MERGE (s)-[:ADDRESSES]->(c);

// 스킬이 움직이는 것 (스킬 → 상태 변수 · Measure). 여기서 INFLUENCES 경로를 따라 영업이익까지 간다.
// [skill, target, sign, delta, unit, note]
UNWIND [
  ['skill:fan-max','sv:fan-speed',1,40,'%','60 → 100'],
  ['skill:fan-max-derate','sv:fan-speed',1,40,'%','60 → 100'],
  ['skill:fan-max-derate','sv:load',-1,-10,'%','90 → 80'],
  ['skill:derate-night-clean','sv:load',-1,-20,'%','90 → 70'],
  ['skill:derate-night-clean','sv:fouling',-1,null,null,'야간 세척으로 오염 제거'],
  ['skill:switch-standby-pump','sv:leak',-1,null,null,'누설 없는 예비 펌프로 운전'],
  ['skill:switch-standby-pump','msr:mtbf',-1,null,null,'예비 설비 여유가 사라진다'],
  ['skill:derate-70','sv:load',-1,-20,'%','90 → 70'],
  ['skill:raise-pressure','sv:ps1',1,10,'bar','압력 보상'],
  ['skill:raise-pressure','sv:leak',1,null,null,'씰 손상 가속'],
  ['skill:fan-slow-derate','sv:fan-speed',-1,-20,'%','60 → 40'],
  ['skill:fan-slow-derate','sv:load',-1,-10,'%','90 → 80'],
  ['skill:fan-slow','sv:fan-speed',-1,-20,'%','60 → 40'],
  ['skill:planned-stop','msr:availability',-1,null,null,'교체 동안 정지'],
  ['skill:planned-stop','sv:bearing-wear',-1,null,null,'베어링 교체'],
  ['skill:planned-stop','msr:maint-cost',1,null,null,'교체 작업비'],
  ['skill:reset-after-cool','msr:availability',1,null,null,'재기동'],
  ['skill:wo-ventilation','sv:ts1',-1,null,null,'캐비닛 온도를 낮춰 냉각 여유 회복'],
  ['skill:wo-ventilation','msr:maint-cost',1,null,null,'환기 보강 작업비'],
  ['skill:wo-cooler-clean','sv:fouling',-1,null,null,null],
  ['skill:wo-cooler-clean','msr:maint-cost',1,null,null,'세척 작업비'],
  ['skill:wo-pump-seal','sv:leak',-1,null,null,null],
  ['skill:wo-pump-seal','msr:maint-cost',1,null,null,'씰 교체 작업비'],
  ['skill:wo-fan-bearing','sv:bearing-wear',-1,null,null,null],
  ['skill:wo-fan-bearing','msr:maint-cost',1,null,null,'베어링 교체 작업비']
] AS r
MATCH (s:Skill {id: r[0]}), (t {id: r[1]})
MERGE (s)-[a:AFFECTS]->(t) SET a.sign = r[2], a.delta = r[3], a.unit = r[4], a.note = r[5];

// 판단 · 작업 사이를 흐르는 데이터: [id, name, typeRef, variable, source, represents]
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
        ['in:chosen-skill','사람이 고른 스킬','string','chosen_skill','sys:process',null]] AS r
MERGE (n:InputData {id: r[0]}) SET n.name = r[1], n.typeRef = r[2], n.variable = r[3]
WITH n, r MATCH (src {id: r[4]}) MERGE (n)-[:SOURCED_FROM]->(src)
WITH n, r OPTIONAL MATCH (x {id: r[5]}) WHERE x:StateVariable OR x:Measure
FOREACH (_ IN CASE WHEN x IS NULL THEN [] ELSE [1] END | MERGE (n)-[:REPRESENTS]->(x));

// 이상 패턴의 탐지 임계값 (DMN식 임계값 검사): [pattern, input, operator, value, unit]
UNWIND [['pattern:cooler-degradation','in:ts1','>',55,'℃'],['pattern:cooler-degradation','in:ce','<',70,'%'],['pattern:cooler-degradation','in:ts1-slope','>',0,'℃/s'],
        ['pattern:pump-leakage','in:ps1','<',165,'bar'],['pattern:pump-leakage','in:fs1','<',8.0,'l/min'],['pattern:pump-leakage','in:load','>=',80,'%'],
        ['pattern:fan-vibration','in:vs1','>',1.2,'mm/s'],['pattern:fan-vibration','in:vs1-slope','>',0,'mm/s²'],
        ['pattern:overheat-trip','in:plc-state','==','TRIP',null]] AS r
MATCH (a:AnomalyPattern {id: r[0]}), (i:InputData {id: r[1]})
MERGE (a)-[x:TESTS]->(i) SET x.operator = r[2], x.value = r[3], x.unit = r[4];
// 탐지 임계값의 근거 매뉴얼 절
UNWIND [['pattern:cooler-degradation','HM-7.3'],['pattern:pump-leakage','HM-5.2'],['pattern:fan-vibration','HM-8.1'],['pattern:overheat-trip','HM-9.4']] AS r
MATCH (a:AnomalyPattern {id: r[0]}), (m:ManualSection {id: r[1]}) MERGE (a)-[:DERIVED_FROM]->(m);

// 판단 정의: [id, name, question, table, hitPolicy, inputs, knowledge sources]
UNWIND [
  ['dec:diagnose-cause','고장 유형 · 원인 판정','이 경보의 고장 유형과 근본 원인은 무엇인가?','dt:diagnose-cause','PRIORITY',['in:pattern','in:ts1','in:ce','in:ps1'],['ks:manual-hm']],
  ['dec:action-candidates','조치 후보 선택','이 고장 유형에 쓸 수 있는 조치 방법(스킬 = SOP)은 무엇인가? (원인 한정 스킬은 원인으로 거른다)','dt:action-candidates','COLLECT',['in:failure-mode','in:cause','in:plc-state'],['ks:manual-hm']],
  ['dec:compliance','규정 적합성','후보 스킬 중 규정상 쓸 수 없거나 감점할 것은 무엇인가?','dt:compliance','COLLECT',['in:skill-kind','in:skill-code','in:failure-mode','in:plc-mode','in:plc-state','in:forecast-ts1','in:forecast-ps1','in:fan100-hours','in:standby-ready','in:supplier-avl'],['ks:sr-04','ks:manual-hm','ks:pr-07']],
  ['dec:rank-actions','조치 우선순위','남은 후보 중 회사 가치(영업이익)에 가장 유리한 순서는?','dt:rank-actions','UNIQUE',['in:forecast-ts1','in:order-due','in:order-penalty','in:order-tier','in:hot-lot-claim','in:hot-lot-qty'],['ks:strategy-map']]
] AS r
MERGE (d:Decision {id: r[0]}) SET d.name = r[1], d.question = r[2]
MERGE (t:DecisionTable {id: r[3]}) SET t.name = r[1] + ' 결정표', t.hitPolicy = r[4]
MERGE (d)-[:IMPLEMENTED_BY]->(t)
WITH d, r UNWIND r[5] AS iid MATCH (i:InputData {id: iid}) MERGE (d)-[:REQUIRES_INPUT]->(i)
WITH DISTINCT d, r UNWIND r[6] AS kid MATCH (k:KnowledgeSource {id: kid}) MERGE (d)-[:GOVERNED_BY]->(k);
UNWIND [['dec:action-candidates','dec:diagnose-cause'],['dec:compliance','dec:action-candidates'],['dec:rank-actions','dec:compliance']] AS r
MATCH (a:Decision {id: r[0]}), (b:Decision {id: r[1]}) MERGE (a)-[:REQUIRES_DECISION]->(b);

// 규칙 = 결정표의 한 행. 임계값은 TESTS 관계로: [input, operator, value, unit]. 한 행의 검사는 모두 AND.
// [id, table, order, when, effect, penalty, annotation, outputs(SELECT)/applies(other), penalizes, sources, tests]
UNWIND [
  ['rule:dx-cooler','dt:diagnose-cause',1,"pattern == 'COOLER_DEGRADATION' and ce < 70",'SELECT',null,'냉각 효율이 낮으면 쿨러 핀 오염이 1순위 (근거 evd:ce-low)',['cause:cooler-fin-fouling'],null,['HM-7.3'],
    [['in:pattern','==','COOLER_DEGRADATION',null],['in:ce','<',70,'%']]],
  ['rule:dx-pump','dt:diagnose-cause',2,"pattern == 'PUMP_LEAKAGE' and ps1 < 165",'SELECT',null,'토출 압력이 165 bar 미만이면 씰 마모 (근거 evd:ps1-low)',['cause:pump-seal-wear'],null,['HM-5.2'],
    [['in:pattern','==','PUMP_LEAKAGE',null],['in:ps1','<',165,'bar']]],
  ['rule:dx-fan','dt:diagnose-cause',3,"pattern == 'FAN_VIBRATION' and ts1 < 52",'SELECT',null,'유온이 정상인데 진동만 오르면 베어링 (근거 evd:vs1-trend)',['cause:fan-bearing-wear'],null,['HM-8.1'],
    [['in:pattern','==','FAN_VIBRATION',null],['in:ts1','<',52,'℃']]],
  ['rule:cand-cooler','dt:action-candidates',1,"failure_mode == 'fm:cooling-loss'",'SELECT',null,'냉각 성능 상실 → 즉시 완화 SOP (팬 최대 · 팬 최대+부하 저감 · 부하 저감+야간 세척) + 근본 조치 작업지시 (핀 세척 · 캐비닛 환기)',['skill:fan-max','skill:fan-max-derate','skill:derate-night-clean','skill:wo-cooler-clean','skill:wo-ventilation'],null,['HM-7.3','HM-9.1'],
    [['in:failure-mode','==','fm:cooling-loss',null]]],
  ['rule:cand-pump','dt:action-candidates',2,"failure_mode == 'fm:volumetric-loss'",'SELECT',null,'펌프 체적 효율 저하 → 즉시 완화 SOP (예비 펌프 전환 · 부하 저감 · 압력 상향) + 근본 조치 작업지시 (축 씰 교체 · 씰 키트 구매요청)',['skill:switch-standby-pump','skill:derate-70','skill:raise-pressure','skill:wo-pump-seal'],null,['HM-5.2'],
    [['in:failure-mode','==','fm:volumetric-loss',null]]],
  ['rule:cand-fan','dt:action-candidates',3,"failure_mode == 'fm:bearing-degradation'",'SELECT',null,'팬 베어링 열화 → 팬 감속+부하 저감 · 팬 감속 · 계획 정지 + 근본 조치 작업지시 (베어링 교체)',['skill:fan-slow-derate','skill:fan-slow','skill:planned-stop','skill:wo-fan-bearing'],null,['HM-8.1','HM-8.3'],
    [['in:failure-mode','==','fm:bearing-degradation',null]]],
  ['rule:cand-trip','dt:action-candidates',4,"plc_state == 'TRIP' and pattern == 'OVERHEAT_TRIP'",'SELECT',null,'과열 트립이면 제어 명령 대신 냉각 후 리셋 (A098: 저압 · 고진동 트립은 knowledge_a098.cypher의 별도 규칙)',['skill:reset-after-cool'],null,['HM-9.4'],
    [['in:plc-state','==','TRIP',null],['in:pattern','==','OVERHEAT_TRIP',null]]],
  ['rule:cand-trip-fm','dt:action-candidates',5,"failure_mode == 'fm:overheat-trip'",'SELECT',null,'과열 정지로 판정되면 냉각 후 리셋 (트립 규칙과 OR — 행을 나눔)',['skill:reset-after-cool'],null,['HM-9.4'],
    [['in:failure-mode','==','fm:overheat-trip',null]]],
  ['rule:no-pressure-raise','dt:compliance',1,"skill_code == 'PRESSURE_SET' and failure_mode == 'fm:volumetric-loss'",'EXCLUDE',null,'누설 의심 시 압력 설정 상향 금지',['skill:raise-pressure'],null,['HM-5.4'],
    [['in:skill-code','==','PRESSURE_SET',null],['in:failure-mode','==','fm:volumetric-loss',null]]],
  ['rule:ts1-hard','dt:compliance',2,'forecast_ts1 >= 65','EXCLUDE',null,'예측 유온이 인터록 한계 이상이면 제외 (모든 제어 후보에 예측값으로 적용)',[],null,['ks:sr-04'],
    [['in:forecast-ts1','>=',65,'℃']]],
  ['rule:auto-mode','dt:compliance',3,"skill_kind == 'control' and plc_mode != 'REMOTE_AUTO'",'EXCLUDE',null,'원격 제어는 REMOTE_AUTO에서만',['skill:fan-max','skill:fan-max-derate','skill:derate-night-clean','skill:switch-standby-pump','skill:derate-70','skill:fan-slow-derate','skill:fan-slow'],null,['HM-3.2'],
    [['in:skill-kind','==','control',null],['in:plc-mode','!=','REMOTE_AUTO',null]]],
  ['rule:standby','dt:compliance',4,'standby_ready == false','EXCLUDE',null,'예비 펌프가 정비 중이면 전환 불가',['skill:switch-standby-pump'],null,['HM-5.2'],
    [['in:standby-ready','==',false,null]]],
  ['rule:ts1-warn','dt:compliance',5,'forecast_ts1 >= 55','WARN',null,'예측 유온이 55 ℃ 이상이면 경보 해제 실패 가능',['skill:fan-max','skill:fan-slow'],null,['HM-7.5'],
    [['in:forecast-ts1','>=',55,'℃']]],
  ['rule:ps1-warn','dt:compliance',9,'forecast_ps1 < 165','WARN',null,'예측 토출 압력이 165 bar 미만이면 저압 경보가 이어질 수 있음',[],null,['HM-5.2'],
    [['in:forecast-ps1','<',165,'bar']]],
  ['rule:fan-24h','dt:compliance',6,'fan100_hours > 24','PENALTY',20,'팬 100 % 연속 24시간 초과 시 수명 감점',['skill:fan-max','skill:fan-max-derate'],'msr:mtbf',['HM-7.3'],
    [['in:fan100-hours','>',24,'h']]],
  ['rule:avl','dt:compliance',7,'supplier_avl == false','EXCLUDE',null,'핵심 부품은 승인 공급사에서만 구매',['skill:wo-pump-seal'],null,['ks:pr-07'],
    [['in:supplier-avl','==',false,null]]],
  ['rule:trip-reset-only','dt:compliance',8,"plc_state == 'TRIP' and skill_code != 'RESET'",'EXCLUDE',null,'트립 중에는 PLC가 리셋 외 제어 명령을 거부한다 (냉각 후 리셋만)',[],null,['HM-9.4'],
    [['in:plc-state','==','TRIP',null],['in:skill-code','!=','RESET',null]]],
  ['rule:rank-value','dt:rank-actions',1,'true','RANK',null,'점수 = BSC 득실(스킬 → 처음 닿는 성과 지표, 강도 high 1 · medium 0.6 · low 0.3, 조건부는 절반) + 예측 유온 여유 (55 − 예측)/3 (±2 한도) − 경고 0.5 − 감점/20 + 선례 비율 × 1.5 + 납기 긴급도((24 − 남은 h)/24 × 지연 보상/100, 0~1) × 생산 영향(유지 +1 · 감산 +0.4 · 정지 −1) × 1.5 − 품질 위험(고온 구간 출하 대기 로트가 있고 예측 유온 ≥ 55 ℃ 면 클레임/1000, ≤ 1) × 1.5. 제외된 카드는 뒤로, 동점이면 승인 직급이 낮은 쪽',[],null,['ks:strategy-map'],[]]
] AS r
MERGE (n:Rule {id: r[0]}) SET n.order = r[2], n.when = r[3], n.effect = r[4], n.penalty = r[5], n.annotation = r[6]
WITH n, r MATCH (t:DecisionTable {id: r[1]}) MERGE (t)-[:HAS_RULE]->(n)
WITH n, r UNWIND (CASE WHEN size(r[7]) = 0 THEN [null] ELSE r[7] END) AS sid
OPTIONAL MATCH (s {id: sid}) WHERE s:Skill OR s:Cause
FOREACH (_ IN CASE WHEN s IS NOT NULL AND r[4] = 'SELECT' THEN [1] ELSE [] END | MERGE (n)-[:OUTPUTS]->(s))
FOREACH (_ IN CASE WHEN s IS NOT NULL AND r[4] <> 'SELECT' THEN [1] ELSE [] END | MERGE (n)-[:APPLIES_TO]->(s))
WITH DISTINCT n, r OPTIONAL MATCH (k:Measure {id: r[8]}) FOREACH (_ IN CASE WHEN k IS NULL THEN [] ELSE [1] END | MERGE (n)-[:PENALIZES]->(k))
WITH n, r UNWIND r[9] AS src MATCH (x {id: src}) WHERE x:KnowledgeSource OR x:ManualSection MERGE (n)-[:DERIVED_FROM]->(x)
WITH DISTINCT n, r UNWIND (CASE WHEN size(r[10]) = 0 THEN [null] ELSE r[10] END) AS tst
OPTIONAL MATCH (i:InputData {id: tst[0]})
FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (n)-[x:TESTS]->(i) SET x.operator = tst[1], x.value = tst[2], x.unit = tst[3]);

// ============================================================== 5. 프로세스 계층 (BPMN 최소 집합)
MERGE (p:Process {id: 'proc:anomaly-response'}) SET p.name = '설비 이상 조치', p.isExecutable = true;
MERGE (p:Process {id: 'proc:maintenance-wo'}) SET p.name = '정비 작업지시', p.isExecutable = false;
MERGE (p:Process {id: 'proc:alert-triage'}) SET p.name = '미지원 경보 현장 검토', p.isExecutable = true;
// 프로세스가 달성하려는 BSC 전략 목표 (조직 목표)
UNWIND [['proc:anomaly-response',['obj:availability','obj:safety','obj:delivery']],['proc:maintenance-wo',['obj:availability','obj:cost']],['proc:alert-triage',['obj:safety']]] AS r
UNWIND r[1] AS oid MATCH (p:Process {id: r[0]}), (o:Objective {id: oid}) MERGE (p)-[:ACHIEVES]->(o);
// 프로세스의 대상: 경보의 asset(correlationKey)이 고르는 설비
MATCH (p:Process), (a:Asset) MERGE (p)-[:ACTS_ON]->(a);

// 흐름 노드: [id, label, name, props, performer]
UNWIND [
  ['ev:alert','Event','경보 수신',{position:'start', eventDefinition:'message', messageRef:'alerts (state=RAISE)', correlationKey:'asset'},null],
  ['task:diagnose','Task','원인 진단',{taskType:'businessRule'},'sys:agent'],
  ['task:candidates','Task','조치 후보 조회',{taskType:'businessRule'},'sys:agent'],
  ['task:compliance','Task','규정 검토',{taskType:'businessRule'},'sys:agent'],
  ['task:rank','Task','우선순위 · 카드 작성',{taskType:'businessRule'},'sys:agent'],
  ['task:select','Task','조치 카드 선택 (HITL)',{taskType:'user'},'role:operator'],
  ['ev:select-timeout','Event','선택 시간 초과',{position:'boundary', eventDefinition:'timer', timer:'PT10M'},null],
  ['task:escalate','Task','상급자 호출',{taskType:'user'},'role:prod-mgr'],
  ['gw:control','Gateway','즉시 제어 포함?',{gatewayType:'exclusive'},null],
  ['task:command','Task','PLC 명령 발행',{taskType:'service'},'sys:scada'],
  ['task:reobserve','Task','재관측 (15분)',{taskType:'service'},'sys:process'],
  ['gw:recovered','Gateway','회복?',{gatewayType:'exclusive'},null],
  ['task:work-order','Task','정비 작업지시',{taskType:'service'},'sys:cmms'],
  ['ev:closed','Event','종결',{position:'end', eventDefinition:'none'},null],
  ['ev:escalated','Event','에스컬레이션 종료',{position:'end', eventDefinition:'escalation'},null]
] AS r
MERGE (n:FlowNode {id: r[0]}) SET n.name = r[2], n += r[3]
WITH n, r
FOREACH (_ IN CASE WHEN r[1] = 'Event' THEN [1] ELSE [] END | SET n:Event)
FOREACH (_ IN CASE WHEN r[1] = 'Task' THEN [1] ELSE [] END | SET n:Task)
FOREACH (_ IN CASE WHEN r[1] = 'Gateway' THEN [1] ELSE [] END | SET n:Gateway)
WITH n, r MATCH (p:Process {id: 'proc:anomaly-response'}) MERGE (p)-[:HAS_NODE]->(n)
WITH n, r OPTIONAL MATCH (who {id: r[4]}) FOREACH (_ IN CASE WHEN who IS NULL THEN [] ELSE [1] END | MERGE (n)-[:PERFORMED_BY]->(who));

UNWIND [['ev:alert','task:diagnose',null],['task:diagnose','task:candidates',null],['task:candidates','task:compliance',null],
        ['task:compliance','task:rank',null],['task:rank','task:select',null],['task:select','gw:control',null],
        ['gw:control','task:command','선택 스킬 kind == control'],['gw:control','task:work-order','선택 스킬 kind == work_order'],
        ['task:command','task:reobserve',null],['task:reobserve','gw:recovered',null],
        ['gw:recovered','task:work-order','TS1 < 55 and 경보 해제'],['gw:recovered','task:escalate','미회복'],
        ['task:work-order','ev:closed',null],['ev:select-timeout','task:escalate',null],['task:escalate','ev:escalated',null]] AS r
MATCH (a:FlowNode {id: r[0]}), (b:FlowNode {id: r[1]}) MERGE (a)-[f:SEQUENCE_FLOW]->(b) SET f.condition = r[2];
MATCH (e:Event {id:'ev:select-timeout'}), (t:Task {id:'task:select'}) MERGE (e)-[:ATTACHED_TO]->(t);
MATCH (e:Event {id:'ev:alert'}), (p:AnomalyPattern) MERGE (e)-[:CORRELATES]->(p);
UNWIND [['task:diagnose','dec:diagnose-cause'],['task:candidates','dec:action-candidates'],['task:compliance','dec:compliance'],['task:rank','dec:rank-actions']] AS r
MATCH (t:Task {id: r[0]}), (d:Decision {id: r[1]}) MERGE (t)-[:INVOKES]->(d);
// 데이터 흐름: 작업이 읽는 데이터(READS)와 만드는 데이터(PRODUCES). 판단 작업은 그 판단의 입력을 모두 읽는다.
UNWIND [['task:diagnose',['in:pattern','in:ts1','in:ce','in:ps1']],
        ['task:candidates',['in:failure-mode','in:cause','in:plc-state']],
        ['task:compliance',['in:skill-kind','in:skill-code','in:failure-mode','in:plc-mode','in:plc-state','in:forecast-ts1','in:forecast-ps1','in:fan100-hours','in:standby-ready','in:supplier-avl']],
        ['task:rank',['in:forecast-ts1','in:order-due','in:order-penalty','in:order-tier','in:hot-lot-claim','in:hot-lot-qty']],
        ['task:command',['in:chosen-skill','in:plc-mode']],
        ['task:reobserve',['in:ts1']],
        ['task:work-order',['in:chosen-skill']]] AS r
UNWIND r[1] AS iid MATCH (t:Task {id: r[0]}), (i:InputData {id: iid}) MERGE (t)-[:READS]->(i);
UNWIND [['task:diagnose',['in:failure-mode','in:cause']],
        ['task:candidates',['in:forecast-ts1','in:forecast-ps1','in:skill-kind','in:skill-code']],
        ['task:select',['in:chosen-skill']]] AS r
UNWIND r[1] AS iid MATCH (t:Task {id: r[0]}), (i:InputData {id: iid}) MERGE (t)-[:PRODUCES]->(i);
MATCH (t:Task {id:'task:command'}), (s:Skill {kind:'control'}) MERGE (t)-[:EXECUTES]->(s);
MATCH (t:Task {id:'task:work-order'}), (s:Skill {kind:'work_order'}) MERGE (t)-[:EXECUTES]->(s);

// A079: 미지원 경보 현장 검토(proc:alert-triage)의 흐름 노드 — 실행 정의 alert_triage_v1.json을 그대로 옮긴 것(실행 버전 MAPS_TO 대응용)
UNWIND [
  ['ev:unhandled-alert','Event','미지원 경보 접수',{position:'start', eventDefinition:'message', messageRef:'alerts (명시 진단/회복 계약 없음)', correlationKey:'asset', catchAll:true},null],
  ['task:triage','Task','미지원 경보 현장 검토',{taskType:'user'},'role:prod-mgr'],
  ['ev:review-recorded','Event','현장 검토 기록 완료',{position:'end', eventDefinition:'none'},null]
] AS r
MERGE (n:FlowNode {id: r[0]}) SET n.name = r[2], n += r[3]
WITH n, r
FOREACH (_ IN CASE WHEN r[1] = 'Event' THEN [1] ELSE [] END | SET n:Event)
FOREACH (_ IN CASE WHEN r[1] = 'Task' THEN [1] ELSE [] END | SET n:Task)
WITH n, r MATCH (p:Process {id: 'proc:alert-triage'}) MERGE (p)-[:HAS_NODE]->(n)
WITH n, r OPTIONAL MATCH (who {id: r[4]}) FOREACH (_ IN CASE WHEN who IS NULL THEN [] ELSE [1] END | MERGE (n)-[:PERFORMED_BY]->(who));
UNWIND [['ev:unhandled-alert','task:triage',null],['task:triage','ev:review-recorded',null]] AS r
MATCH (a:FlowNode {id: r[0]}), (b:FlowNode {id: r[1]}) MERGE (a)-[f:SEQUENCE_FLOW]->(b) SET f.condition = r[2];
// 이 시작 이벤트는 명시 계약이 없는 경보를 받으므로 특정 AnomalyPattern과 CORRELATES 하지 않는다(alert_policy 'triage' 경로).
UNWIND ['in:pattern','in:plc-state'] AS iid MATCH (t:Task {id:'task:triage'}), (i:InputData {id: iid}) MERGE (t)-[:READS]->(i);

// ============================================================== 6. 외부 변수 · 예측
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

// 조치별 예측 (카드에 보이는 예측값). 쿨러 시나리오는 설비 모델의 평형식으로 계산한 값, 나머지는 설계 목표값이다.
// [id, cause, skill, variable, value, unit, method]
UNWIND [
  ['fc:cooler-none','cause:cooler-fin-fouling',null,'sv:ts1',70.0,'℃','열평형 모델 (thermal.equilibrium_ts1)'],
  ['fc:cooler-fan-max','cause:cooler-fin-fouling','skill:fan-max','sv:ts1',55.4,'℃','열평형 모델 (thermal.equilibrium_ts1)'],
  ['fc:cooler-fan-max-derate','cause:cooler-fin-fouling','skill:fan-max-derate','sv:ts1',49.0,'℃','열평형 모델 (thermal.equilibrium_ts1)'],
  ['fc:cooler-derate70','cause:cooler-fin-fouling','skill:derate-night-clean','sv:ts1',52.2,'℃','열평형 모델 (thermal.equilibrium_ts1)'],
  ['fc:pump-switch','cause:pump-seal-wear','skill:switch-standby-pump','sv:ps1',182.0,'bar','설계 목표값'],
  ['fc:pump-derate70','cause:pump-seal-wear','skill:derate-70','sv:ps1',160.0,'bar','설계 목표값'],
  ['fc:fan-slow-derate','cause:fan-bearing-wear','skill:fan-slow-derate','sv:ts1',50.5,'℃','열평형 모델 (thermal.equilibrium_ts1)'],
  ['fc:fan-slow','cause:fan-bearing-wear','skill:fan-slow','sv:ts1',57.2,'℃','열평형 모델 (thermal.equilibrium_ts1)'],
  ['fc:fan-slow-vs1','cause:fan-bearing-wear','skill:fan-slow','sv:vs1',1.0,'mm/s','설계 목표값']
] AS r
MERGE (f:Forecast {id: r[0]}) SET f.value = r[4], f.unit = r[5], f.horizon = 'steady-state', f.method = r[6]
WITH f, r MATCH (c:Cause {id: r[1]}), (v:StateVariable {id: r[3]}) MERGE (f)-[:GIVEN]->(c) MERGE (f)-[:FORECASTS]->(v)
WITH f, r OPTIONAL MATCH (s:Skill {id: r[2]}) FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END | MERGE (f)-[:ASSUMES]->(s));

// ============================================================== 7. 운영 기록 (예시 — 선례 질의 시연용)
UNWIND [['inc:demo-1','ALT-hyd01-0001-demo',datetime('2026-09-25T10:12:00+09:00'),'pattern:cooler-degradation','cause:cooler-fin-fouling'],
        ['inc:demo-2','ALT-hyd01-0002-demo',datetime('2026-09-28T14:40:00+09:00'),'pattern:cooler-degradation','cause:cooler-fin-fouling'],
        ['inc:demo-3','ALT-hyd01-0003-demo',datetime('2026-09-30T09:05:00+09:00'),'pattern:pump-leakage','cause:pump-seal-wear']] AS r
MERGE (i:Incident {id: r[0]}) SET i.alertId = r[1], i.openedAt = r[2]
WITH i, r MATCH (a:Asset {id:'asset:hyd-01'}), (p:AnomalyPattern {id: r[3]}), (c:Cause {id: r[4]})
MERGE (i)-[:ON_ASSET]->(a) MERGE (i)-[:RAISED_BY]->(p) MERGE (i)-[:DIAGNOSED_AS]->(c);
UNWIND [['case:demo-1','inc:demo-1','skill:fan-max-derate','role:prod-mgr',true,'OEM 납기 우선, 야간 세척 예정',datetime('2026-09-25T10:20:00+09:00')],
        ['case:demo-2','inc:demo-2','skill:derate-night-clean','role:prod-mgr',false,'팬 100 % 운전이 이번 주 이미 30시간 — 팬 수명 보호',datetime('2026-09-28T14:47:00+09:00')],
        ['case:demo-3','inc:demo-3','skill:switch-standby-pump','role:prod-mgr',true,'예비 펌프 정비 완료 상태 확인',datetime('2026-09-30T09:11:00+09:00')]] AS r
MERGE (c:DecisionCase {id: r[0]}) SET c.followedRecommendation = r[4], c.reason = r[5], c.decidedAt = r[6]
WITH c, r MATCH (i:Incident {id: r[1]}), (s:Skill {id: r[2]}), (ro:Role {id: r[3]}), (d:Decision {id:'dec:rank-actions'})
MERGE (c)-[:FOR_INCIDENT]->(i) MERGE (c)-[:CHOSE]->(s) MERGE (c)-[:DECIDED_BY]->(ro) MERGE (c)-[:INSTANCE_OF]->(d);

// A069: fresh seed only. Live policy changes use the reviewed ranking-policy API.
MATCH (r:Rule {id: 'rule:rank-value'}) WHERE r.rankingPolicy IS NULL
SET r.rankingPolicy = '{"version":1,"inputs":{"due":"order_due_h","penalty":"order_penalty_per_h","claim":"hot_lot_claim","qty":"hot_lot_qty"},"components":{"bsc":"bsc_gain + 0.5 * bsc_conditional_gain - bsc_loss - 0.5 * bsc_conditional_loss","forecast":"0 if forecast_ts1 is None else clamp((55 - forecast_ts1) / 3, -2, 2)","warn":"-0.5 * warning_count","penalty":"-penalty_total / 20","precedent":"1.5 * precedent_share","delivery":"(0 if due is None or penalty is None or penalty <= 0 else round(clamp((24 - due) / 24, 0, 1) * clamp(penalty / 100, 0, 1), 2)) * (1 if production == \'keep\' else (0.4 if production == \'reduce\' else -1)) * 1.5","quality":"0 if claim is None or claim <= 0 or (qty is not None and qty <= 0) or forecast_ts1 is None or forecast_ts1 < 55 else -1.5 * round(min(1, claim / 1000), 2)"},"tieBreak":"lower_approver"}';
