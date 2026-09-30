// hyd-iot-edu 전사 온톨로지 확장 (L7 → L8 → L9) — "에이전트가 조직의 판단 기준으로 트레이드오프를 결정하게 하는 지식 지도"
// seed.cypher(설비·관측·고장·조치 지식) 위에 얹는다. Idempotent (MERGE on id).
//
//  조직     : Role -MEMBER_OF-> Department ; KPI -OWNED_BY-> Department ; KPI -CONTRIBUTES_TO{weight}-> Goal
//  규정     : Policy{kind HARD|SOFT, expr, penalty} -GOVERNS-> Skill | Scenario ; Policy -SUPPORTS-> Goal
//  시스템   : InfoType{endpoint, prefix} -HELD_IN-> System ; BusinessProcess -RUNS_ON-> System
//  스킬     : Skill -EXECUTED_VIA-> System ; Skill -EXECUTED_IN-> BusinessProcess ; Skill -REQUIRES_INFO-> InfoType ;
//             Skill -APPROVED_BY-> Role ; Skill -IMPLEMENTS-> Action (기존 조치 지식과 연결)
//  판단     : Cause|AnomalyPattern -TRIGGERS_DECISION-> Scenario ; Scenario -NEEDS_INFO-> InfoType ; Scenario -HAS_OPTION-> Option ;
//             Option -USES_SKILL-> Skill ; Option -IMPACTS{expr, note}-> KPI ; Option -APPROVED_BY-> Role ; Option -BUYS_FROM-> Supplier
//  사례     : Decision -DECIDED-> Option ; Decision -ABOUT-> Scenario   (process 서비스가 승인 시 기록)
//
// 금액 단위는 모두 만원. 식(expr)은 에이전트의 판단 엔진이 기업 시스템에서 가져온 사실(prefix_name)과 대안 파라미터(o_name)로 계산한다.
// 규정 출처는 교육용 요약·예시이며 실제 조문 인용이 아니다.

CREATE CONSTRAINT dept_id IF NOT EXISTS FOR (n:Department) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT role_id IF NOT EXISTS FOR (n:Role) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kpi_id IF NOT EXISTS FOR (n:KPI) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT goal_id IF NOT EXISTS FOR (n:Goal) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT policy_id IF NOT EXISTS FOR (n:Policy) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT system_id IF NOT EXISTS FOR (n:System) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT info_id IF NOT EXISTS FOR (n:InfoType) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (n:Skill) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT bproc_id IF NOT EXISTS FOR (n:BusinessProcess) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT scenario_id IF NOT EXISTS FOR (n:Scenario) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT option_id IF NOT EXISTS FOR (n:Option) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT supplier_id IF NOT EXISTS FOR (n:Supplier) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (n:Decision) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT upload_id IF NOT EXISTS FOR (n:ManualUpload) REQUIRE n.id IS UNIQUE;

// ---------------------------------------------------------------- 조직 · 역할
UNWIND [['dept:production','생산팀'],['dept:maintenance','설비보전팀'],['dept:purchasing','구매팀'],['dept:quality','품질팀'],
        ['dept:sales','영업팀'],['dept:ehs','환경안전·에너지팀'],['dept:plant','공장 경영(전사)']] AS d
MERGE (x:Department {id: d[0]}) SET x.name = d[1];
UNWIND [['role:operator','운전원','dept:production',1],['role:prod-mgr','생산관리자','dept:production',2],['role:maint-mgr','설비보전팀장','dept:maintenance',2],
        ['role:purchasing-mgr','구매팀장','dept:purchasing',2],['role:quality-mgr','품질팀장','dept:quality',2],['role:sales-mgr','영업팀장','dept:sales',2],
        ['role:ehs-mgr','환경안전팀장','dept:ehs',2],['role:plant-mgr','공장장','dept:plant',3]] AS r
MERGE (x:Role {id: r[0]}) SET x.name = r[1], x.level = r[3]
WITH x, r MATCH (d:Department {id: r[2]}) MERGE (x)-[:MEMBER_OF]->(d);

// ---------------------------------------------------------------- 전사 목표 · KPI (부서 소유)
MERGE (g:Goal {id: 'goal:op-profit'}) SET g.name = '전사 영업이익', g.description = '부서 KPI의 금액 환산 영향을 합산해 판단한다 (전사 관점).';
MERGE (g:Goal {id: 'goal:safety'}) SET g.name = '무재해 · 법규 준수', g.description = 'HARD 규정으로 강제한다. 금액과 맞바꾸지 않는다.';
MERGE (g:Goal {id: 'goal:customer'}) SET g.name = '고객 신뢰', g.description = '납기와 품질로 측정한다.';
UNWIND [['kpi:otd','납기 준수 (지체상금)','dept:sales','만원'],['kpi:customer-trust','고객 신뢰 · 품질 클레임','dept:quality','만원'],
        ['kpi:oee','생산 원가 · OEE 기회비용','dept:production','만원'],['kpi:maint-cost','보전 비용','dept:maintenance','만원'],
        ['kpi:asset-health','설비 신뢰성 (MTBF · 작동유 수명)','dept:maintenance','만원'],['kpi:part-cost','부품 구매단가 절감','dept:purchasing','만원'],
        ['kpi:energy','에너지 비용 (최대수요 기본요금)','dept:ehs','만원']] AS k
MERGE (x:KPI {id: k[0]}) SET x.name = k[1], x.unit = k[3]
WITH x, k MATCH (d:Department {id: k[2]}) MERGE (x)-[:OWNED_BY]->(d)
WITH x MATCH (g:Goal {id: 'goal:op-profit'}) MERGE (x)-[c:CONTRIBUTES_TO]->(g) SET c.weight = 1.0;
MATCH (k:KPI), (g:Goal {id: 'goal:customer'}) WHERE k.id IN ['kpi:otd','kpi:customer-trust'] MERGE (k)-[c:CONTRIBUTES_TO]->(g) SET c.weight = 1.0;

// ---------------------------------------------------------------- 기업 시스템 · 정보 유형 (에이전트가 "어디서 무엇을" 가져오는지)
UNWIND [['sys:erp','ERP','수주 · 납기 · 지체상금 · 재고 · 구매 (SAP S/4 역할)','IT'],['sys:mes','MES','생산오더 · 설비 가용능력 · 로트 이력','IT'],
        ['sys:cmms','CMMS','정비 이력 · 작업지시 (설비보전 시스템)','IT'],['sys:qms','QMS','로트 품질 · 부적합 격리 · 검사','IT'],
        ['sys:scm','SCM 구매 포털','공급사 단가 · 품질 점수 · 리드타임 · AVL','IT'],['sys:ems','EMS','전력 수요 · 계약전력 · 요금','IT'],
        ['sys:scada','SCADA · PLC','즉시 제어 (cmd-gateway 경유, L1~L6)','OT'],['sys:historian','Historian (TimescaleDB)','센서 시계열 · 이상 점수','IT']] AS s
MERGE (x:System {id: s[0]}) SET x.name = s[1], x.description = s[2], x.zone = s[3];
UNWIND [['info:mes-order','현재 생산오더 · 대체 설비 가용능력','sys:mes','/mes/orders?asset={asset}','mes'],
        ['info:erp-contract','고객 계약 · 지체상금 · 고장 비용','sys:erp','/erp/contract?asset={asset}','erp'],
        ['info:erp-inventory','완제품 재고 · 출하 일정','sys:erp','/erp/inventory?asset={asset}','erp'],
        ['info:cmms-history','정비 이력 · 세척 소요 · 야간 정비창','sys:cmms','/cmms/history?asset={asset}','cmms'],
        ['info:scm-suppliers','쿨러 코어 공급사 단가 · 고장률 · 리드타임','sys:scm','/scm/suppliers?part=P-CLR-CORE','scm'],
        ['info:qms-lots','과열 구간 생산 로트 · 검사 비용','sys:qms','/qms/lots?asset={asset}','qms'],
        ['info:ems-demand','전력 수요 · 계약전력 · 기본요금 단가','sys:ems','/ems/demand','ems']] AS i
MERGE (x:InfoType {id: i[0]}) SET x.name = i[1], x.endpoint = i[3], x.prefix = i[4]
WITH x, i MATCH (s:System {id: i[2]}) MERGE (x)-[:HELD_IN]->(s);

// ---------------------------------------------------------------- 업무 프로세스 (L9)
UNWIND [['proc:hitl-cmd','HITL 즉시 제어 (승인 → action.cmd → ACK → 재관측)','sys:scada'],['proc:maintenance-wo','정비 작업지시 (발행 → 배정 → 완료)','sys:cmms'],
        ['proc:production-change','생산오더 변경 (이관 · 일정 조정)','sys:mes'],['proc:purchase','구매 (요청 → 승인 → 발주)','sys:erp'],
        ['proc:nc-control','부적합 관리 (격리 → 검사 → 판정)','sys:qms'],['proc:shipping','출하 (지시 · 대체 출하)','sys:erp'],
        ['proc:energy-peak','최대수요 관리 (부하 이동 · 수요 제어)','sys:ems']] AS p
MERGE (x:BusinessProcess {id: p[0]}) SET x.name = p[1]
WITH x, p MATCH (s:System {id: p[2]}) MERGE (x)-[:RUNS_ON]->(s);

// ---------------------------------------------------------------- 에이전트 스킬 (실행 가능한 업무 단위)
// name · description · detail 은 포탈 "에이전트 스킬 카탈로그"에서 사람이 고칠 수 있다. 재적재가 편집을 덮지 않도록
// coalesce로 "없을 때만" 채우고, 편집된 스킬(x.edited = true)은 관계도 다시 만들지 않는다.
UNWIND [['skill:cooling-adjust','냉각 즉시 제어 (팬 ↑ · 부하 ↓)','sys:scada','proc:hitl-cmd','role:operator','즉각 제어 — L1~L6 영역',
         '쿨러 팬 속도를 올리고 펌프 부하를 낮춰 유온 상승을 즉시 멈춘다. 설비 하나만 보는 즉각 제어다.',
         '입력: 현재 유온 TS1, 냉각 효율 CE, PLC 운전 모드\n실행: 인시던트 승인 → action.cmd(만료 120 s) → cmd-gateway 5종 검증 → PLC cmd/auto\n파라미터: 팬 80~100 %, 부하 60~90 % (온톨로지 Action.min/max)\n산출: PLC ACK DONE, 15분 재관측\n가드레일: REMOTE_AUTO 모드에서만, 인터록 65 ℃, 팬 100 % 연속 24 h 이내'],
        ['skill:schedule-maintenance','정비 작업지시 발행','sys:cmms','proc:maintenance-wo','role:maint-mgr','근본 조치',
         'CMMS에 정비 작업지시를 만든다. 즉시 또는 야간 정비창에 배정한다.',
         '입력: 정비 이력(세척 주기 · 소요 시간), 생산오더 납기\n실행: CMMS 작업지시 발행 → 정비팀 배정 → 완료 보고\n파라미터: 작업(SOP), 시점(즉시 | 야간 정비창)\n산출: 작업지시 번호 WO-…\n가드레일: 정비 전 LOCAL 전환 (매뉴얼 HM-3.1)'],
        ['skill:reallocate-production','생산오더 대체 설비 이관','sys:mes','proc:production-change','role:prod-mgr','생산 조정',
         'MES에서 진행 중인 생산오더를 가용 능력이 있는 다른 설비로 옮긴다.',
         '입력: 현재 오더(납기 · 잔량 · 속도), 대체 설비 가용 시간\n실행: MES 오더 이관 → 금형·조건 교체 → 초품 검사\n산출: 이관된 오더와 새 설비\n가드레일: 자동차 고객 오더는 초품 검사(PPAP) 필수'],
        ['skill:procure-part','부품 구매요청','sys:erp','proc:purchase','role:purchasing-mgr','구매',
         'ERP에 교체 부품 구매요청을 올린다. 공급사는 SCM의 단가 · 고장률 · 리드타임으로 고른다.',
         '입력: SCM 공급사 견적, ERP 고장 비용 · 클레임 비용\n실행: 구매요청 → 승인 → 발주\n파라미터: 공급사\n산출: 구매요청 번호 PR-…\n가드레일: 핵심 부품은 AVL 공급사만 (구매규정 PR-07)'],
        ['skill:hold-lot','로트 격리 · 전수검사','sys:qms','proc:nc-control','role:quality-mgr','품질',
         '공정 이상 구간에 만든 로트를 QMS에서 격리하고 전수검사를 건다.',
         '입력: 과열 구간 생산 로트, 검사 소요 · 비용\n실행: 격리 → 전수검사 → 판정(합격 · 재작업 · 폐기)\n산출: 격리된 로트 목록\n가드레일: 자동차 고객 로트는 격리 · 검사 없이 출하 불가 (IATF 취지)'],
        ['skill:release-lot','로트 출하 승인','sys:qms','proc:shipping','role:quality-mgr','품질',
         '검사를 마친 로트, 또는 영향이 없는 일반 로트를 출하 승인한다.',
         '입력: 로트 검사 결과\n실행: 출하 승인 → 출하 지시\n산출: 출하 승인된 로트\n가드레일: 자동차 로트 무검사 출하 금지'],
        ['skill:substitute-shipment','완제품 재고 대체 출하','sys:erp','proc:shipping','role:sales-mgr','영업',
         '격리된 로트 대신 ERP 완제품 재고로 고객 납기를 지킨다.',
         '입력: 완제품 재고 수량, 출하 일정\n실행: 출하 오더 변경 → 재고 출고\n산출: 대체 출하 번호 SH-…\n가드레일: 재고 수량이 로트 수량 이상일 때만'],
        ['skill:demand-control','전력 수요 제어 (공조 · 부하)','sys:ems','proc:energy-peak','role:ehs-mgr','에너지',
         'EMS에서 피크 시간대 최대수요를 계약전력 아래로 관리한다.',
         '입력: 현재 수요 · 계약전력 · 기본요금 단가\n실행: 부하 이동 · 수요 목표 설정\n산출: 수요 제어 조치\n가드레일: 폭염 시 작업장 공조 정지 금지 (온열질환 예방)']] AS k
MERGE (x:Skill {id: k[0]})
SET x.name = coalesce(x.name, k[1]), x.description = coalesce(x.description, k[6]), x.detail = coalesce(x.detail, k[7]), x.category = coalesce(x.category, k[5])
WITH x, k WHERE coalesce(x.edited, false) = false
MATCH (s:System {id: k[2]}), (p:BusinessProcess {id: k[3]}), (r:Role {id: k[4]})
MERGE (x)-[:EXECUTED_VIA]->(s) MERGE (x)-[:EXECUTED_IN]->(p) MERGE (x)-[:APPROVED_BY]->(r);

// ---------------------------------------------------------------- 사람의 판단을 다음 판단에 (HITL 환류)
// 승인된 Decision은 Option을 가리킨다. 같은 시나리오의 과거 선택 비율이 이 KPI로 들어가 다음 권고 점수에 더해진다.
MERGE (k:KPI {id: 'kpi:precedent'}) SET k.name = '현장 판단 선례 (HITL 환류)', k.unit = '만원', k.value_per_share = coalesce(k.value_per_share, 60),
  k.description = '과거 같은 판단에서 사람이 고른 비율 × value_per_share. 조직의 암묵적 기준을 다음 판단에 반영한다.'
WITH k MATCH (d:Department {id: 'dept:plant'}), (g:Goal {id: 'goal:op-profit'}) MERGE (k)-[:OWNED_BY]->(d) MERGE (k)-[c:CONTRIBUTES_TO]->(g) SET c.weight = 1.0;
MATCH (k:Skill {id:'skill:cooling-adjust'}), (a:Action) WHERE a.id IN ['act:fan-boost','act:reduce-load'] MERGE (k)-[:IMPLEMENTS]->(a);
MATCH (k:Skill {id:'skill:schedule-maintenance'}), (a:Action) WHERE a.id IN ['act:cooler-clean-wo','act:fan-inspect-wo','act:ventilation-wo'] MERGE (k)-[:IMPLEMENTS]->(a);
UNWIND [['skill:cooling-adjust',['info:cmms-history']],['skill:schedule-maintenance',['info:cmms-history','info:mes-order']],
        ['skill:reallocate-production',['info:mes-order','info:erp-contract']],['skill:procure-part',['info:scm-suppliers','info:erp-contract']],
        ['skill:hold-lot',['info:qms-lots']],['skill:release-lot',['info:qms-lots','info:erp-inventory']],
        ['skill:substitute-shipment',['info:erp-inventory']],['skill:demand-control',['info:ems-demand']]] AS m
UNWIND m[1] AS iid
MATCH (k:Skill {id: m[0]}), (i:InfoType {id: iid}) MERGE (k)-[:REQUIRES_INFO]->(i);

// ---------------------------------------------------------------- 공급사 (SCM 마스터 데이터와 연결)
UNWIND [['sup:a','A정밀 (저가)',true],['sup:b','B-OEM (순정)',true],['sup:c','C트레이딩 (최저가 · 비승인)',false]] AS s
MERGE (x:Supplier {id: s[0]}) SET x.name = s[1], x.avl = s[2];

// ---------------------------------------------------------------- 규정 (HARD = 제외, SOFT = 페널티)
MERGE (p:Policy {id: 'pol:ts1-limit'}) SET p.name = '유온 65 ℃ 이상 운전 금지', p.kind = 'HARD', p.expr = 'o_peak_ts1 >= 65',
  p.source = '사내 설비안전규정 SR-04 (교육용 예시) · 매뉴얼 HM-7.3 · PLC 인터록';
MERGE (p:Policy {id: 'pol:ts1-warn'}) SET p.name = '유온 60~65 ℃ 경고 구간 운전 시 수명 페널티', p.kind = 'SOFT', p.expr = 'o_peak_ts1 >= 60', p.penalty = '-30', p.kpi = 'kpi:asset-health',
  p.source = '보전 기준 MS-02 (교육용 예시)';
MERGE (p:Policy {id: 'pol:fan-24h'}) SET p.name = '팬 100 % 연속 운전 24시간 이내', p.kind = 'SOFT', p.expr = 'o_fan100_h > 24', p.penalty = '-20', p.kpi = 'kpi:asset-health',
  p.source = '매뉴얼 HM-7.3';
MERGE (p:Policy {id: 'pol:avl'}) SET p.name = '안전·품질 핵심 부품은 승인 공급사(AVL)에서만 구매', p.kind = 'HARD', p.expr = 'o_avl == 0',
  p.source = '사내 구매규정 PR-07 (교육용 예시)';
MERGE (p:Policy {id: 'pol:iatf-nc'}) SET p.name = '자동차 고객 로트는 공정 이상 시 격리·검사 후 출하', p.kind = 'HARD', p.expr = 'o_ship_auto_unchecked == 1 and qms_hot_min > 0',
  p.source = 'IATF 16949 부적합 출력물 관리 취지 (교육용 요약)';
MERGE (p:Policy {id: 'pol:heat-stress'}) SET p.name = '폭염 시 작업장 공조 정지 금지 (온열질환 예방)', p.kind = 'HARD', p.expr = 'o_hvac_off == 1 and ems_outdoor_c >= 33',
  p.source = '산업안전보건기준 온열질환 예방 취지 (교육용 요약)';
MATCH (p:Policy {id:'pol:fan-24h'}), (k:Skill {id:'skill:cooling-adjust'}) MERGE (p)-[:GOVERNS]->(k);
MATCH (p:Policy {id:'pol:avl'}), (k:Skill {id:'skill:procure-part'}) MERGE (p)-[:GOVERNS]->(k);
MATCH (p:Policy {id:'pol:iatf-nc'}), (k:Skill {id:'skill:release-lot'}) MERGE (p)-[:GOVERNS]->(k);
MATCH (p:Policy {id:'pol:heat-stress'}), (k:Skill {id:'skill:demand-control'}) MERGE (p)-[:GOVERNS]->(k);
MATCH (p:Policy), (g:Goal {id:'goal:safety'}) WHERE p.kind = 'HARD' MERGE (p)-[:SUPPORTS]->(g);
MATCH (p:Policy {id:'pol:ts1-limit'}), (c:Constraint {id:'cons:ts1-max'}) MERGE (p)-[:ENFORCED_BY]->(c);

// ---------------------------------------------------------------- 판단 시나리오 1: 고객 납기 vs 설비 보전 (쿨러 열화 경보에서 자동 기동)
MERGE (s:Scenario {id: 'sc:delivery-vs-maintenance'}) SET s.no = 1, s.name = '고객 납기 vs 설비 보전', s.asset = 'HYD-01',
  s.question = 'HYD-01 쿨러 성능이 떨어졌다. 자동차 OEM 긴급 오더 납기가 6시간 남았다. 지금 세울 것인가, 버틸 것인가, 옮길 것인가?',
  s.immediate = '즉각 제어 수준의 대응: 팬 100 %, 부하 80 % (유온만 본다)',
  s.lesson = '같은 경보라도 MES 오더 · ERP 지체상금 · CMMS 정비창을 함께 봐야 답이 나온다. 부서마다 1위 안이 다르다.';
MATCH (c:Cause {id:'cause:cooler-fin-fouling'}), (s:Scenario {id:'sc:delivery-vs-maintenance'}) MERGE (c)-[:TRIGGERS_DECISION]->(s);
MATCH (p:Policy {id:'pol:ts1-limit'}), (s:Scenario {id:'sc:delivery-vs-maintenance'}) MERGE (p)-[:GOVERNS]->(s);

UNWIND [['opt:sc1-stop','즉시 정지 · 쿨러 세척','설비를 세우고 지금 세척한다. 설비는 가장 안전하지만 납기를 놓친다.','{"peak_ts1": 48}','role:plant-mgr',
          ['skill:schedule-maintenance'],
          [['kpi:otd','-erp_penalty_per_h * max(0, cmms_clean_h + mes_remaining_qty / mes_rate_per_h - mes_due_in_h)','세척 3 h + 잔량 생산 → 납기 초과 시간 × 지체상금'],
           ['kpi:oee','-cmms_clean_h * mes_hour_value','정지 시간 × 설비 시간당 가치'],
           ['kpi:maint-cost','-cmms_clean_cost','세척 작업비']]],
        ['opt:sc1-derate','감속 운전 + 야간 세척','팬 100 %, 부하 80 %로 버티며 오더를 끝내고 야간 정비창에 세척한다.','{"peak_ts1": 49, "fan100_h": 9}','role:prod-mgr',
          ['skill:cooling-adjust','skill:schedule-maintenance'],
          [['kpi:otd','-erp_penalty_per_h * max(0, mes_remaining_qty / (mes_rate_per_h * 80 / 90) - mes_due_in_h)','부하 80 %로 늘어난 생산 시간이 납기를 넘는가'],
           ['kpi:oee','-(mes_remaining_qty / (mes_rate_per_h * 80 / 90) - mes_remaining_qty / mes_rate_per_h) * mes_hour_value','속도 손실 시간 × 시간당 가치'],
           ['kpi:maint-cost','-cmms_clean_cost','야간 세척 작업비'],
           ['kpi:asset-health','-cmms_night_in_h * cmms_oil_risk_per_h','야간까지 고온 운전 → 작동유 열화 위험 (fm:oil-degradation)']]],
        ['opt:sc1-continue','현 상태로 계속 운전','아무것도 하지 않는다. 당장 손실은 없어 보인다.','{"peak_ts1": 70}','role:operator',
          [],
          [['kpi:otd','-erp_penalty_per_h * max(0, 8 + mes_remaining_qty / mes_rate_per_h - mes_due_in_h) * 0.9','약 40분 뒤 65 ℃ 인터록 트립(확률 0.9) → 8 h 복구 후 잔량 생산'],
           ['kpi:oee','-8 * mes_hour_value * 0.9','트립 복구 8 h × 시간당 가치 × 확률'],
           ['kpi:maint-cost','-cmms_clean_cost * 3 * 0.9','트립 후 쿨러 세척 + 작동유 교환'],
           ['kpi:asset-health','-12 * cmms_oil_risk_per_h','고온 운전 12 h 상당 작동유 열화']]],
        ['opt:sc1-transfer','HYD-02로 물량 이관 + 즉시 세척','MES에서 HYD-02의 빈 능력으로 오더를 옮기고 HYD-01은 바로 세척한다.','{"peak_ts1": 48, "fai_cost": 20}','role:prod-mgr',
          ['skill:reallocate-production','skill:schedule-maintenance'],
          [['kpi:otd','-erp_penalty_per_h * max(0, mes_changeover_h + mes_remaining_qty / mes_alt_rate_per_h - mes_due_in_h)','교체 1 h + HYD-02 속도로 잔량 생산'],
           ['kpi:oee','-mes_changeover_h * mes_hour_value','금형·조건 교체 시간'],
           ['kpi:maint-cost','-cmms_clean_cost','세척 작업비'],
           ['kpi:customer-trust','-o_fai_cost','대체 설비 초품 검사 (고객 PPAP 요구)']]]] AS o
MERGE (x:Option {id: o[0]}) SET x.name = o[1], x.description = o[2], x.params = o[3]
WITH x, o MATCH (s:Scenario {id:'sc:delivery-vs-maintenance'}), (r:Role {id: o[4]}) MERGE (s)-[:HAS_OPTION]->(x) MERGE (x)-[:APPROVED_BY]->(r)
WITH x, o UNWIND o[6] AS imp MATCH (k:KPI {id: imp[0]}) MERGE (x)-[i:IMPACTS]->(k) SET i.expr = imp[1], i.note = imp[2];
UNWIND [['opt:sc1-stop','skill:schedule-maintenance'],['opt:sc1-derate','skill:cooling-adjust'],['opt:sc1-derate','skill:schedule-maintenance'],
        ['opt:sc1-transfer','skill:reallocate-production'],['opt:sc1-transfer','skill:schedule-maintenance']] AS u
MATCH (x:Option {id: u[0]}), (k:Skill {id: u[1]}) MERGE (x)-[:USES_SKILL]->(k);

// ---------------------------------------------------------------- 판단 시나리오 2: 교체 부품 구매 — 구매팀 KPI vs 전사 KPI (팔란티어형)
MERGE (s:Scenario {id: 'sc:part-procurement'}) SET s.no = 2, s.name = '교체 부품 구매: 구매단가 vs 전사 이익', s.asset = 'HYD-01',
  s.question = 'CMMS를 보니 HYD-01 쿨러를 60일 동안 3번 세척했다. 쿨러 코어를 교체한다. 어느 공급사에서 살 것인가?',
  s.immediate = '즉각 제어 수준의 대응: 해당 없음 (세척만 반복)',
  s.condition = 'cmms_cleans_60d >= 3',
  s.lesson = '구매팀은 단가를 낮추면 KPI가 오르지만, 고장률이 높은 부품은 설비 정지 · 고객 클레임으로 매출을 깎는다. 온톨로지가 부품 → 설비 → 고객 오더 → 매출을 이어 준다.';
MATCH (c:Cause {id:'cause:cooler-fin-fouling'}), (s:Scenario {id:'sc:part-procurement'}) MERGE (c)-[:TRIGGERS_DECISION]->(s);
UNWIND [['opt:sc2-a','A정밀 (저가) 구매','단가 180만원, 필드 고장률 연 12 %','{"avl": 1}','role:purchasing-mgr','sup:a',
          [['kpi:part-cost','scm_std_price - scm_a_price','표준단가 대비 절감액 (구매팀 KPI)'],
           ['kpi:asset-health','-scm_a_fail * erp_failure_cost','연 고장확률 × 고장 1회 비용 (정지 · 긴급 정비)'],
           ['kpi:customer-trust','-scm_a_fail * erp_claim_cost','연 고장확률 × OEM 클레임 · 점수 하락']]],
        ['opt:sc2-b','B-OEM (순정) 구매','단가 260만원, 필드 고장률 연 2 %, 리드타임 5일','{"avl": 1}','role:plant-mgr','sup:b',
          [['kpi:part-cost','scm_std_price - scm_b_price','표준단가 초과 (구매팀 KPI 악화)'],
           ['kpi:asset-health','-scm_b_fail * erp_failure_cost',''],
           ['kpi:customer-trust','-scm_b_fail * erp_claim_cost',''],
           ['kpi:maint-cost','-max(0, scm_b_lead_d - 4) * 10','리드타임 초과일 동안 임시 세척']]],
        ['opt:sc2-c','C트레이딩 (최저가) 구매','단가 120만원, AVL 미등록','{"avl": 0}','role:purchasing-mgr','sup:c',
          [['kpi:part-cost','scm_std_price - scm_c_price',''],
           ['kpi:asset-health','-scm_c_fail * erp_failure_cost',''],
           ['kpi:customer-trust','-scm_c_fail * erp_claim_cost','']]]] AS o
MERGE (x:Option {id: o[0]}) SET x.name = o[1], x.description = o[2], x.params = o[3]
WITH x, o MATCH (s:Scenario {id:'sc:part-procurement'}), (r:Role {id: o[4]}), (sp:Supplier {id: o[5]}), (k:Skill {id:'skill:procure-part'})
MERGE (s)-[:HAS_OPTION]->(x) MERGE (x)-[:APPROVED_BY]->(r) MERGE (x)-[:BUYS_FROM]->(sp) MERGE (x)-[:USES_SKILL]->(k)
WITH x, o UNWIND o[6] AS imp MATCH (k:KPI {id: imp[0]}) MERGE (x)-[i:IMPACTS]->(k) SET i.expr = imp[1], i.note = imp[2];

// ---------------------------------------------------------------- 판단 시나리오 3: 품질 격리 — 규정 준수 vs 납기
MERGE (s:Scenario {id: 'sc:quality-hold'}) SET s.no = 3, s.name = '과열 구간 생산 로트: 규정 vs 납기', s.asset = 'HYD-01',
  s.question = '유온이 60 ℃를 넘은 12분 동안 만든 로트가 있다. 자동차 OEM 로트는 2시간 뒤 출하다. 그대로 내보낼 것인가?',
  s.immediate = '즉각 제어 수준의 대응: 유온을 내리면 끝 (이미 만든 제품은 보지 않는다)',
  s.condition = 'qms_hot_min > 0',
  s.lesson = '규정(HARD)은 금액과 맞바꾸지 않는다. 대신 ERP 재고를 찾아 규정과 납기를 함께 지키는 안을 온톨로지가 찾아 준다.';
MATCH (p:AnomalyPattern {id:'pattern:cooler-degradation'}), (s:Scenario {id:'sc:quality-hold'}) MERGE (p)-[:TRIGGERS_DECISION]->(s);
UNWIND [['opt:sc3-ship','전량 즉시 출하','검사 없이 두 로트 모두 내보낸다.','{"ship_auto_unchecked": 1}','role:sales-mgr',['skill:release-lot'],
          [['kpi:otd','0',''],['kpi:customer-trust','-qms_gen_defect_p * qms_gen_claim - qms_auto_defect_p * qms_auto_claim','불량 유출 위험 (OEM 라인 정지 클레임 포함)']]],
        ['opt:sc3-hold-auto','자동차 로트 격리 · 전수검사 후 출하','일반 로트는 샘플검사 후 출하. 자동차 로트는 검사 4시간만큼 늦는다.','{"ship_auto_unchecked": 0}','role:quality-mgr',['skill:hold-lot','skill:release-lot'],
          [['kpi:otd','-erp_penalty_per_h * max(0, qms_inspect_h - erp_ship_in_h)','검사 시간이 출하 시각을 넘긴 만큼 지체상금'],
           ['kpi:customer-trust','-qms_gen_defect_p * qms_gen_claim * 0.5','일반 로트 샘플검사 후 잔여 유출 위험'],
           ['kpi:oee','-qms_inspect_cost - qms_sample_cost','전수검사 · 샘플검사 공수']]],
        ['opt:sc3-hold-all','전량 격리 · 전수검사','두 로트 모두 격리하고 전수검사한다.','{"ship_auto_unchecked": 0}','role:quality-mgr',['skill:hold-lot'],
          [['kpi:otd','-erp_penalty_per_h * max(0, qms_inspect_h - erp_ship_in_h) - 30','자동차 로트 지체상금 + 일반 고객 지연'],
           ['kpi:customer-trust','0','유출 위험 없음'],
           ['kpi:oee','-qms_inspect_cost * 1.75','두 로트 전수검사 공수']]],
        ['opt:sc3-substitute','자동차 로트 격리 + ERP 완제품 재고로 대체 출하','ERP 재고로 OEM 납기를 지키고, 격리 로트는 검사 후 재고로 돌린다.','{"ship_auto_unchecked": 0, "restock_cost": 15}','role:quality-mgr',
          ['skill:hold-lot','skill:release-lot','skill:substitute-shipment'],
          [['kpi:otd','0 if erp_fg_stock >= qms_auto_qty else -erp_penalty_per_h * max(0, qms_inspect_h - erp_ship_in_h)','재고가 로트 수량 이상이면 지연 없음'],
           ['kpi:customer-trust','-qms_gen_defect_p * qms_gen_claim * 0.5','일반 로트 샘플검사 후 잔여 유출 위험'],
           ['kpi:oee','-qms_inspect_cost - qms_sample_cost - o_restock_cost','검사 공수 + 재고 보충 생산']]]] AS o
MERGE (x:Option {id: o[0]}) SET x.name = o[1], x.description = o[2], x.params = o[3]
WITH x, o MATCH (s:Scenario {id:'sc:quality-hold'}), (r:Role {id: o[4]}) MERGE (s)-[:HAS_OPTION]->(x) MERGE (x)-[:APPROVED_BY]->(r)
WITH x, o UNWIND o[5] AS sk MATCH (k:Skill {id: sk}) MERGE (x)-[:USES_SKILL]->(k)
WITH DISTINCT x, o UNWIND o[6] AS imp MATCH (k:KPI {id: imp[0]}) MERGE (x)-[i:IMPACTS]->(k) SET i.expr = imp[1], i.note = imp[2];

// ---------------------------------------------------------------- 판단 시나리오 4: 폭염 피크 전력 vs 냉각
MERGE (s:Scenario {id: 'sc:peak-power'}) SET s.no = 4, s.name = '폭염 피크 전력 vs 냉각', s.asset = 'ALL',
  s.question = '폭염으로 3기 모두 냉각이 부족하다. 14~17시 피크에 팬을 모두 100 %로 올리면 계약전력을 넘는다. 어떻게 할 것인가?',
  s.immediate = '즉각 제어 수준의 대응: 3기 모두 팬 100 %',
  s.lesson = '최대수요전력을 한 번 넘으면 1년 동안 기본요금이 오른다. 에너지 · 생산 · 안전 규정을 함께 봐야 한다.';
MATCH (c:Cause {id:'cause:high-ambient'}), (s:Scenario {id:'sc:peak-power'}) MERGE (c)-[:TRIGGERS_DECISION]->(s);
MATCH (p:Policy), (s:Scenario {id:'sc:peak-power'}) WHERE p.id IN ['pol:ts1-limit','pol:ts1-warn'] MERGE (p)-[:GOVERNS]->(s);
UNWIND [['opt:sc4-all-fans','3기 모두 팬 100 %','냉각은 확실하지만 최대수요가 계약전력을 넘는다.','{"peak_ts1": 52, "fan100_h": 3}','role:prod-mgr',['skill:cooling-adjust'],
          [['kpi:energy','-max(0, ems_demand_kw + 3 * ems_fan_boost_kw - ems_contract_kw) * ems_basic_rate * 12','초과 kW × 기본요금 × 12개월']]],
        ['opt:sc4-shift','HYD-01·02만 팬 100 %, HYD-03 비긴급 오더 야간 이동','MES에서 HYD-03 오더를 야간으로 옮겨 피크 수요를 줄인다.','{"peak_ts1": 52, "fan100_h": 3, "hyd03_kw": 25}','role:prod-mgr',
          ['skill:cooling-adjust','skill:reallocate-production'],
          [['kpi:energy','-max(0, ems_demand_kw + 2 * ems_fan_boost_kw - ems_contract_kw - o_hyd03_kw) * ems_basic_rate * 12',''],
           ['kpi:oee','-ems_peak_h * mes_hour_value * 0.3','야간 이동 할증 (30 %)']]],
        ['opt:sc4-no-boost','팬 증속 없이 운전','전력은 그대로지만 유온이 경고 구간에 머문다.','{"peak_ts1": 63}','role:prod-mgr',[],
          [['kpi:asset-health','-3 * ems_peak_h * cmms_oil_risk_per_h','3기 × 피크 시간 동안 작동유 열화']]],
        ['opt:sc4-hvac-off','팬 100 % + 공장 공조 일시 정지','공조 전력으로 피크를 상쇄한다. 에너지 KPI만 보면 최선이다.','{"peak_ts1": 52, "fan100_h": 3, "hvac_off": 1, "hvac_kw": 40}','role:ehs-mgr',
          ['skill:cooling-adjust','skill:demand-control'],
          [['kpi:energy','o_hvac_kw * ems_peak_h * ems_energy_rate','공조 정지로 초과 없음 + 피크 시간 전력량 절감']]]] AS o
MERGE (x:Option {id: o[0]}) SET x.name = o[1], x.description = o[2], x.params = o[3]
WITH x, o MATCH (s:Scenario {id:'sc:peak-power'}), (r:Role {id: o[4]}) MERGE (s)-[:HAS_OPTION]->(x) MERGE (x)-[:APPROVED_BY]->(r)
WITH x, o UNWIND (CASE WHEN size(o[5]) = 0 THEN [null] ELSE o[5] END) AS sk
OPTIONAL MATCH (k:Skill {id: sk}) FOREACH (_ IN CASE WHEN k IS NULL THEN [] ELSE [1] END | MERGE (x)-[:USES_SKILL]->(k))
WITH DISTINCT x, o UNWIND o[6] AS imp MATCH (k:KPI {id: imp[0]}) MERGE (x)-[i:IMPACTS]->(k) SET i.expr = imp[1], i.note = imp[2];

// 시나리오가 필요로 하는 정보 = 대안이 쓰는 스킬의 정보 + 식에 등장하는 정보
UNWIND [['sc:delivery-vs-maintenance',['info:mes-order','info:erp-contract','info:cmms-history']],
        ['sc:part-procurement',['info:scm-suppliers','info:erp-contract','info:cmms-history']],
        ['sc:quality-hold',['info:qms-lots','info:erp-inventory','info:erp-contract']],
        ['sc:peak-power',['info:ems-demand','info:mes-order','info:cmms-history']]] AS m
UNWIND m[1] AS iid
MATCH (s:Scenario {id: m[0]}), (i:InfoType {id: iid}) MERGE (s)-[:NEEDS_INFO]->(i);
