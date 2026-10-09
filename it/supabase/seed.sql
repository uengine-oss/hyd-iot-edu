-- 교육용 가상 데이터 (it/enterprise-sim/entsim/data.py 와 같은 값). 회사 · 고객 · 금액은 모두 예시. 금액 만원, 시간 h.
-- `supabase start` / `supabase db reset` 이 마이그레이션 뒤에 실행한다. 멱등.

insert into ent.assets (code, name, line) values
  ('HYD-01', '유압 파워팩 1호기', '창원 1공장 A라인'),
  ('HYD-02', '유압 파워팩 2호기', '창원 1공장 A라인'),
  ('HYD-03', '유압 파워팩 3호기', '창원 1공장 B라인')
on conflict (code) do update set name = excluded.name, line = excluded.line;

-- 시각 열(due_at 등)은 아래 ent.reanchor_scenario_times()가 '지금' 기준 시나리오 값(납기 6 h 등)으로 맞춘다 (A086).
insert into ent.production_orders (order_id, asset, item, customer, due_at, remaining_qty, rate_per_h, hour_value, alt_asset, alt_free_at, alt_rate_per_h, changeover_h) values
  ('MO-0930-0412', 'HYD-01', 'FG-AUTO-7 (유압 브래킷)', '가나자동차 (OEM, 교육용 가상)', now(), 1500, 300, 50, 'HYD-02', now(), 270, 1),
  ('MO-0930-0415', 'HYD-02', 'FG-IND-3 (산업용 매니폴드)', '다라산업 (일반, 교육용 가상)', now(), 800, 250, 40, 'HYD-03', now(), 240, 1),
  ('MO-0930-0419', 'HYD-03', 'FG-AUTO-9 (실린더 블록)', '가나자동차 (OEM, 교육용 가상)', now(), 600, 300, 50, 'HYD-01', now(), 280, 1)
on conflict (order_id) do update set asset = excluded.asset, remaining_qty = excluded.remaining_qty, moved_from = null;

insert into ent.sales_contracts (sales_order, asset, order_id, customer, customer_tier, penalty_per_h, failure_cost, claim_cost) values
  ('SO-2609-118', 'HYD-01', 'MO-0930-0412', '가나자동차 (OEM, 교육용 가상)', 'OEM', 120, 900, 300),
  ('SO-2609-131', 'HYD-02', 'MO-0930-0415', '다라산업 (일반, 교육용 가상)', '일반', 20, 500, 80),
  ('SO-2609-140', 'HYD-03', 'MO-0930-0419', '가나자동차 (OEM, 교육용 가상)', 'OEM', 120, 900, 300)
on conflict (sales_order) do nothing;

insert into ent.fg_inventory (asset, fg_item, fg_stock, ship_at) values
  ('HYD-01', 'FG-AUTO-7', 900, now()), ('HYD-02', 'FG-IND-3', 100, now()), ('HYD-03', 'FG-AUTO-9', 200, now())
on conflict (asset) do update set fg_stock = excluded.fg_stock;

insert into ent.maintenance_profiles (asset, clean_h, clean_cost, night_window_at, oil_risk_per_h, mtbf_h, standby_ready) values
  ('HYD-01', 3, 40, now(), 5, 1400, true), ('HYD-02', 3, 40, now(), 5, 2600, true), ('HYD-03', 3, 40, now(), 5, 3100, true)
on conflict (asset) do nothing;

delete from ent.maintenance_history;
-- 마지막 세척·60일 세척 횟수는 이 이력에서 계산한다(cmms_history). 수행 일시는 reanchor_scenario_times()가 맞춘다.
insert into ent.maintenance_history (asset, wo, task, performed_at) values
  ('HYD-01', 'WO-HIST-01-1', '쿨러 핀 세척', now()), ('HYD-01', 'WO-HIST-01-2', '쿨러 핀 세척', now()), ('HYD-01', 'WO-HIST-01-3', '쿨러 핀 세척', now()),
  ('HYD-02', 'WO-HIST-02-1', '쿨러 핀 세척', now()), ('HYD-03', 'WO-HIST-03-P', '쿨러 핀 세척', now());

insert into ent.quality_profiles (asset, hot_min, auto_lot, auto_qty, gen_lot, gen_qty, inspect_h, inspect_cost, sample_cost, gen_defect_p, gen_claim, auto_defect_p, auto_claim) values
  ('HYD-01', 12, 'L-0930-A17', 800, 'L-0930-G05', 600, 4, 60, 10, 0.03, 400, 0.05, 3000),
  ('HYD-02', 0, '-', 0, 'L-0930-G09', 500, 3, 40, 8, 0.01, 200, 0.0, 0),
  ('HYD-03', 5, 'L-0930-A21', 400, '-', 0, 3, 35, 0, 0.0, 0, 0.04, 3000)
on conflict (asset) do nothing;

insert into ent.parts (part_no, name, std_price) values ('P-CLR-CORE', '쿨러 코어', 250) on conflict (part_no) do nothing;
insert into ent.suppliers (id, key, name, part_no, price, fail_rate, lead_d, avl, quality_score) values
  ('sup:a', 'a', 'A정밀 (저가)', 'P-CLR-CORE', 180, 0.12, 3, true, 0.78),
  ('sup:b', 'b', 'B-OEM (순정)', 'P-CLR-CORE', 260, 0.02, 5, true, 0.97),
  ('sup:c', 'c', 'C트레이딩 (최저가)', 'P-CLR-CORE', 120, 0.20, 2, false, 0.61)
on conflict (id) do nothing;

insert into ent.energy_demand (site, contract_kw, demand_kw, fan_boost_kw, basic_rate, peak_h, peak_window, outdoor_c, energy_rate) values
  ('창원 1공장 (교육용 가상)', 450, 438, 6, 0.8, 3, '14:00-17:00', 35, 0.015)
on conflict (site) do nothing;

-- ============================================================================
-- 프로세스 엔진 시드 (public) — 테넌트 MCP · 사람과 에이전트 · 폼 계약. ProcessGPT 는 화면에서 등록하는 것들이다.
-- ============================================================================
insert into public.tenants (id, name, owner, mcp) values ('hyd', '유압설비 교육 공장', 'role:prod-mgr', '{
  "mcpServers": {
    "neo4j":      {"command": "uvx", "args": ["--with", "fastmcp==2.13.0.2", "mcp-neo4j-cypher@0.4.1", "--transport", "stdio"],
                   "env": {"NEO4J_URI": "bolt://neo4j:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "hydpass123", "NEO4J_READ_ONLY": "true"}},
    "enterprise": {"type": "url", "url": "http://enterprise-mcp:8199/mcp", "transport": "streamable_http"},
    "hyd-dmn":    {"type": "url", "url": "http://dmn-mcp:8198/mcp", "transport": "streamable_http"},
    "enterprise-maint":    {"type": "url", "url": "http://enterprise-mcp-maint:8196/mcp", "transport": "streamable_http"},
    "enterprise-purchase": {"type": "url", "url": "http://enterprise-mcp-purchase:8195/mcp", "transport": "streamable_http"}
  }}'::jsonb)
on conflict (id) do update set name = excluded.name, owner = excluded.owner, mcp = excluded.mcp;

insert into public.users (id, email, username, role, is_agent, agent_type, goal, tools, tenant_id) values
  ('role:operator',  'operator@hyd.local',  '운전원',     'operator',  false, null,     null, null, 'hyd'),
  ('role:prod-mgr',  'prodmgr@hyd.local',   '생산관리자', 'manager',   false, null,     null, null, 'hyd'),
  ('role:maint-mgr', 'maintmgr@hyd.local',  '정비관리자', 'manager',   false, null,     null, null, 'hyd'),
  ('sys:agent',      null, 'AI 에이전트 (Claude Code)', 'agent', true, 'agent',  '경보의 원인을 진단하고 조치 카드를 올린다', 'neo4j,enterprise,hyd-dmn', 'hyd'),
  ('sys:scada',      null, 'SCADA',        'system',    true,  'system', 'PLC 명령 발행 (Incident 경로)', null, 'hyd'),
  ('sys:process',    null, '프로세스',     'system',    true,  'system', '타이머 · 재관측', null, 'hyd'),
  ('sys:cmms',       null, 'CMMS',         'system',    true,  'system', '작업지시', null, 'hyd')
on conflict (id) do update set email = excluded.email, username = excluded.username, role = excluded.role, is_agent = excluded.is_agent,
  agent_type = excluded.agent_type, goal = excluded.goal, tools = excluded.tools;

-- 폼 = 작업의 결과 계약 (에이전트의 JSON 제출 형식 · 사람의 입력 폼). key 는 정의의 outputData 와 같다.
insert into public.form_def (id, tenant_id, proc_def_id, activity_id, fields_json) values
  ('diagnose',   'hyd', 'anomaly_response', 'task:diagnose',   '[{"key":"cause","type":"text","text":"판정한 원인 노드 id (예: cause:cooler-fin-fouling)"},{"key":"failure_mode","type":"text","text":"고장 유형 노드 id (예: fm:cooling-loss)"},{"key":"guide_card","type":"object","text":"hyd-dmn diagnose 도구가 돌려준 가이드 카드 객체 그대로 (alert · causes · recommended · skills · citations · summary)"}]'),
  ('candidates', 'hyd', 'anomaly_response', 'task:candidates', '[{"key":"candidates","type":"array","text":"후보 스킬 id 목록 (dec:action-candidates 결과)"}]'),
  ('compliance', 'hyd', 'anomaly_response', 'task:compliance', '[{"key":"compliance","type":"object","text":"스킬 id → {feasible, excluded[], penalties[], warnings[]} (dec:compliance 결과)"}]'),
  ('rank',       'hyd', 'anomaly_response', 'task:rank',       '[{"key":"decision","type":"object","text":"순위 결과 요약 {recommended, explanation, order[]} — hyd-dmn evaluate_cards · submit_decision 결과"},{"key":"decision_id","type":"text","text":"submit_decision 이 돌려준 조치 카드 묶음 id"}]'),
  ('select_card','hyd', 'anomaly_response', 'task:select',     '[{"key":"chosen_skill","type":"text","text":"고른 스킬(SOP) id"},{"key":"chosen_skill_kind","type":"select","text":"스킬 종류","items":[{"control":"즉시 제어"},{"work_order":"작업지시만"}]}]'),
  ('escalate',   'hyd', 'anomaly_response', 'task:escalate',   '[{"key":"note","type":"textarea","text":"생산관리자 확인 메모"}]')
on conflict (id, tenant_id) do update set proc_def_id = excluded.proc_def_id, activity_id = excluded.activity_id, fields_json = excluded.fields_json;

-- ============================================================================
-- U5 (2026-10-08) 사람 사용자 · 업무분장 (migration 000029 role_members). 역할 사용자(role:*)는 위 users 에 있다.
-- 운전원은 2명이라 조치 선택 단계는 역할 공용으로 남고, 생산관리자·정비관리자는 1명이라 그 사람에게 바로 배정된다(procsvc/inbox.py).
-- ============================================================================
insert into public.users (id, email, username, role, is_agent, agent_type, tenant_id) values
  ('user:kim-op',     'kim.op@hyd.local',     '김운전', 'operator', false, null, 'hyd'),
  ('user:choi-op',    'choi.op@hyd.local',    '최운전', 'operator', false, null, 'hyd'),
  ('user:lee-prod',   'lee.prod@hyd.local',   '이생산', 'manager',  false, null, 'hyd'),
  ('user:park-maint', 'park.maint@hyd.local', '박정비', 'manager',  false, null, 'hyd')
on conflict (id) do update set email = excluded.email, username = excluded.username, role = excluded.role;

insert into public.role_members (tenant_id, role_id, user_id) values
  ('hyd', 'role:operator',  'user:kim-op'),
  ('hyd', 'role:operator',  'user:choi-op'),
  ('hyd', 'role:prod-mgr',  'user:lee-prod'),
  ('hyd', 'role:maint-mgr', 'user:park-maint')
on conflict do nothing;

select ent.reanchor_scenario_times();
