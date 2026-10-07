-- ============================================================================
-- 업무 DB (ent 스키마) — 기업 시스템 ERP · MES · CMMS · QMS · SCM · EMS 의 교육용 가상 데이터.
--
-- 회의(2026-10-01, 원문 L350~353 · L375~377 · L397~399): "주문량 · 원가 · 납기 · 에너지 · 규제 같은 일반 데이터는
-- 시계열에 있을 수 없다. 일반 RDB 가 하나 있어야 하고, Supabase 로 쓴다면 Supabase MCP 가 붙어야 한다."
-- 이 스키마가 그 RDB 다. 값은 it/enterprise-sim/entsim/data.py 의 가상 데이터와 같다 (금액 만원, 시간 h).
-- 에이전트(Claude Code)는 enterprise-mcp(HTTP, it/enterprise-mcp)가 읽기 전용 역할 hyd_enterprise_reader(20261004000003)로 읽은
-- 결과를 받는다 — Supabase MCP(anon/authenticated)가 아니다(A143 정정; seed.sql:61 · compose.yaml enterprise-mcp 참고).
-- 쓰기는 process 서비스가 승인 뒤 ent.exec_skill() 로만 한다.
-- 구조는 process-gpt-sample-app-wms/supabase 를 따른다: 스키마 분리 · RLS · 명령은 RPC 하나.
-- ============================================================================

create schema if not exists ent;

-- ---------------------------------------------------------------- 마스터 · 현황 (읽기)
create table if not exists ent.assets (
  code text primary key,                      -- HYD-01
  name text not null,
  line text
);

create table if not exists ent.production_orders (        -- MES: 각 설비가 지금 돌리는 생산오더
  order_id text primary key,                  -- MO-0930-0412
  asset text not null references ent.assets(code),
  item text not null,
  customer text not null,
  due_in_h numeric not null,                  -- 납기까지 남은 시간(h). 교육용 고정값; 실습 clock 기준
  remaining_qty integer not null,
  rate_per_h integer not null,
  hour_value numeric not null,                -- 시간당 생산 가치(만원)
  alt_asset text references ent.assets(code),
  alt_free_h numeric,
  alt_rate_per_h integer,
  changeover_h numeric,
  status text not null default 'RUNNING',
  moved_from text,
  updated_at timestamptz not null default now()
);

create table if not exists ent.sales_contracts (          -- ERP: 그 오더의 계약 조건
  sales_order text primary key,               -- SO-2609-118
  asset text not null references ent.assets(code),
  order_id text references ent.production_orders(order_id),
  customer text not null,
  customer_tier text not null,                -- OEM | 일반
  penalty_per_h numeric not null,             -- 납기 지연 시 고객 라인 정지 보상(만원/h)
  failure_cost numeric not null,              -- 계획 외 고장 1회 비용(만원)
  claim_cost numeric not null
);

create table if not exists ent.fg_inventory (             -- ERP: 완제품 재고
  asset text primary key references ent.assets(code),
  fg_item text not null,
  fg_stock integer not null,
  ship_in_h numeric not null,
  warehouse text not null default 'WH-1 완제품 창고'
);

create table if not exists ent.maintenance_profiles (     -- CMMS: 설비별 정비 기준
  asset text primary key references ent.assets(code),
  cleans_60d integer not null,
  last_clean_days integer not null,
  clean_h numeric not null,
  clean_cost numeric not null,
  night_in_h numeric not null,                -- 다음 야간 정비창까지
  oil_risk_per_h numeric not null,
  mtbf_h integer not null
);

create table if not exists ent.maintenance_history (      -- CMMS: 과거 작업지시
  id bigserial primary key,
  asset text not null references ent.assets(code),
  wo text not null,
  task text not null,
  days_ago integer not null
);

create table if not exists ent.quality_profiles (         -- QMS: 고온 구간에 생산된 로트
  asset text primary key references ent.assets(code),
  hot_min integer not null,
  auto_lot text, auto_qty integer not null default 0,
  gen_lot text, gen_qty integer not null default 0,
  inspect_h numeric not null, inspect_cost numeric not null, sample_cost numeric not null,
  gen_defect_p numeric not null, gen_claim numeric not null,
  auto_defect_p numeric not null, auto_claim numeric not null
);

create table if not exists ent.parts (                    -- SCM: 부품 표준단가
  part_no text primary key,                   -- P-CLR-CORE
  name text not null,
  std_price numeric not null
);

create table if not exists ent.suppliers (                -- SCM: 공급사 견적 (쿨러 코어)
  id text primary key,                        -- sup:a (온톨로지 Supplier.id 와 같음)
  key text not null,
  name text not null,
  part_no text not null references ent.parts(part_no),
  price numeric not null,
  fail_rate numeric not null,
  lead_d integer not null,
  avl boolean not null,                       -- 승인 공급사 목록(AVL) 여부
  quality_score numeric not null
);

create table if not exists ent.energy_demand (            -- EMS: 오늘 오후 수요 대 계약
  site text primary key,
  contract_kw numeric not null, demand_kw numeric not null, fan_boost_kw numeric not null,
  basic_rate numeric not null, peak_h numeric not null, peak_window text not null,
  outdoor_c numeric not null, energy_rate numeric not null
);

-- ---------------------------------------------------------------- 실행 결과 (쓰기 — 승인 뒤 process 서비스만)
create table if not exists ent.work_orders (
  id text primary key, asset text not null, task text not null, window_label text not null,
  status text not null default '배정됨', decision_id text, option_id text, requested_by text,
  created_at timestamptz not null default now()
);
create table if not exists ent.purchase_requests (
  id text primary key, part text not null, supplier text not null, supplier_name text, asset text,
  status text not null default '승인됨 → 발주', decision_id text, option_id text, requested_by text,
  created_at timestamptz not null default now()
);
create table if not exists ent.shipments (
  id text primary key, item text not null, qty integer not null, source text not null, asset text,
  decision_id text, created_at timestamptz not null default now()
);
create table if not exists ent.lot_dispositions (
  id bigserial primary key, lot text not null, asset text not null, kind text not null check (kind in ('HOLD', 'RELEASE')),
  status text not null, decision_id text, created_at timestamptz not null default now()
);
create table if not exists ent.ems_actions (
  id bigserial primary key, action text not null, decision_id text, created_at timestamptz not null default now()
);
create table if not exists ent.transactions (             -- 모든 실행의 원장 (멱등 키: decision + skill)
  id text primary key,
  t timestamptz not null default now(),
  system text not null,
  skill text not null,
  ref text,
  detail text,
  asset text,
  decision_id text,
  option_id text,
  requested_by text,
  fingerprint text not null,
  unique nulls not distinct (decision_id, skill)
);

-- ---------------------------------------------------------------- 읽기 RPC — enterprise-sim 의 {system, facts, records} 계약 그대로
create or replace function ent.mes_orders(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'MES',
    'facts', (select to_jsonb(o) - 'item' - 'customer' - 'status' - 'moved_from' - 'updated_at' - 'asset' from ent.production_orders o where o.asset = p_asset or o.moved_from = p_asset order by (o.asset = p_asset) desc limit 1),
    'records', coalesce((select jsonb_agg(to_jsonb(o)) from ent.production_orders o where o.asset = p_asset or o.moved_from = p_asset), '[]'::jsonb))
$$;

create or replace function ent.erp_contract(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'ERP',
    'facts', (select jsonb_build_object('sales_order', c.sales_order, 'customer_tier', c.customer_tier, 'penalty_per_h', c.penalty_per_h,
                                        'failure_cost', c.failure_cost, 'claim_cost', c.claim_cost) from ent.sales_contracts c where c.asset = p_asset limit 1),
    'records', coalesce((select jsonb_agg(to_jsonb(c)) from ent.sales_contracts c where c.asset = p_asset), '[]'::jsonb))
$$;

create or replace function ent.erp_inventory(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'ERP',
    'facts', (select jsonb_build_object('fg_item', i.fg_item, 'fg_stock', i.fg_stock, 'ship_in_h', i.ship_in_h) from ent.fg_inventory i where i.asset = p_asset),
    'records', coalesce((select jsonb_agg(to_jsonb(i)) from ent.fg_inventory i where i.asset = p_asset), '[]'::jsonb))
$$;

create or replace function ent.cmms_history(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'CMMS',
    'facts', (select to_jsonb(m) - 'asset' from ent.maintenance_profiles m where m.asset = p_asset),
    'records', coalesce((select jsonb_agg(jsonb_build_object('wo', h.wo, 'task', h.task, 'days_ago', h.days_ago) order by h.days_ago) from ent.maintenance_history h where h.asset = p_asset), '[]'::jsonb),
    'work_orders', coalesce((select jsonb_agg(to_jsonb(w) order by w.created_at desc) from ent.work_orders w where w.asset = p_asset), '[]'::jsonb))
$$;

create or replace function ent.qms_lots(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'QMS',
    'facts', (select to_jsonb(q) - 'asset' from ent.quality_profiles q where q.asset = p_asset),
    'records', coalesce((select jsonb_agg(r) from (
        select jsonb_build_object('lot', q.auto_lot, 'customer', 'OEM', 'qty', q.auto_qty, 'status', '출하 대기') r from ent.quality_profiles q where q.asset = p_asset and q.auto_qty > 0
        union all
        select jsonb_build_object('lot', q.gen_lot, 'customer', '일반', 'qty', q.gen_qty, 'status', '출하 대기') from ent.quality_profiles q where q.asset = p_asset and q.gen_qty > 0) x), '[]'::jsonb))
$$;

create or replace function ent.scm_suppliers(p_part text default 'P-CLR-CORE') returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'SCM',
    'facts', (select jsonb_build_object('std_price', p.std_price) || coalesce((select jsonb_object_agg(k, v) from (
                 select s.key || '_price' k, to_jsonb(s.price) v from ent.suppliers s where s.part_no = p_part
                 union all select s.key || '_fail', to_jsonb(s.fail_rate) from ent.suppliers s where s.part_no = p_part
                 union all select s.key || '_lead_d', to_jsonb(s.lead_d) from ent.suppliers s where s.part_no = p_part
                 union all select s.key || '_avl', to_jsonb((s.avl)::int) from ent.suppliers s where s.part_no = p_part) kv), '{}'::jsonb)
              from ent.parts p where p.part_no = p_part),
    'records', coalesce((select jsonb_agg(to_jsonb(s) || jsonb_build_object('part', p_part, 'fail', s.fail_rate)) from ent.suppliers s where s.part_no = p_part), '[]'::jsonb))
$$;

create or replace function ent.ems_demand() returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'EMS',
    'facts', (select to_jsonb(e) - 'site' from ent.energy_demand e limit 1),
    'records', coalesce((select jsonb_agg(to_jsonb(e)) from ent.energy_demand e), '[]'::jsonb))
$$;

-- ---------------------------------------------------------------- 쓰기 RPC — 승인된 스킬의 시스템 트랜잭션 (멱등)
-- p = {decision, option, skill, asset, by, params{...}}. 같은 (decision, skill) 은 두 번 실행하지 않고 첫 결과를 돌려준다.
-- 입력이 다른데 같은 키로 다시 오면 오류 (enterprise-sim state.py 의 fingerprint 규칙과 동일).
create or replace function ent.exec_skill(p jsonb) returns jsonb
language plpgsql
as $$
declare
  v_skill text := p->>'skill';
  v_asset text := coalesce(p->>'asset', 'HYD-01');
  v_decision text := p->>'decision';
  v_params jsonb := coalesce(p->'params', '{}'::jsonb);
  v_fp text := md5((jsonb_build_object('decision', p->'decision', 'option', p->'option', 'skill', p->'skill', 'asset', p->'asset', 'params', p->'params'))::text);
  v_prior ent.transactions;
  v_system text;
  v_ref text; v_detail text; v_id text;
  v_alt text; v_order text; v_sup text; v_sup_name text; v_part text; v_lot text; v_inv ent.fg_inventory; v_q ent.quality_profiles;
begin
  v_system := case v_skill
    when 'skill:schedule-maintenance' then 'sys:cmms' when 'skill:reallocate-production' then 'sys:mes'
    when 'skill:procure-part' then 'sys:erp' when 'skill:hold-lot' then 'sys:qms' when 'skill:release-lot' then 'sys:qms'
    when 'skill:substitute-shipment' then 'sys:erp' when 'skill:demand-control' then 'sys:ems' end;
  if v_system is null then
    raise exception 'unknown or non-enterprise skill %', v_skill using errcode = '22023';
  end if;

  if v_decision is not null then
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill;
    if found then
      if v_prior.fingerprint <> v_fp then
        raise exception 'idempotency conflict: decision/skill already executed with different input' using errcode = '23505';
      end if;
      return to_jsonb(v_prior) - 'fingerprint';
    end if;
  end if;

  v_id := 'TX-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));

  if v_skill = 'skill:schedule-maintenance' then
    v_ref := 'WO-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.work_orders (id, asset, task, window_label, decision_id, option_id, requested_by)
    values (v_ref, v_asset, coalesce(v_params->>'task', '쿨러 핀 세척 (SOP-COOL-02)'),
            coalesce(v_params->>'window', case when (p->>'option') like '%derate%' then '야간 정비창' else '즉시' end), v_decision, p->>'option', p->>'by');
    v_detail := format('%s %s — %s', v_asset, coalesce(v_params->>'task', '쿨러 핀 세척 (SOP-COOL-02)'), coalesce(v_params->>'window', '즉시'));

  elsif v_skill = 'skill:reallocate-production' then
    select order_id, alt_asset into v_order, v_alt from ent.production_orders where asset = v_asset limit 1;
    if v_order is null then
      v_ref := '-'; v_detail := format('%s에 이관할 오더 없음', v_asset);
    else
      v_alt := coalesce(v_params->>'to', v_alt);
      update ent.production_orders set moved_from = v_asset, asset = v_alt where order_id = v_order;
      v_ref := v_order; v_detail := format('%s %s → %s 이관', v_order, v_asset, v_alt);
    end if;

  elsif v_skill = 'skill:procure-part' then
    v_sup := coalesce(v_params->>'supplier', 'sup:b');
    select name into v_sup_name from ent.suppliers where id = v_sup;
    v_part := coalesce(v_params->>'part', '쿨러 코어');
    v_ref := 'PR-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.purchase_requests (id, part, supplier, supplier_name, asset, decision_id, option_id, requested_by)
    values (v_ref, v_part, v_sup, coalesce(v_sup_name, v_sup), v_asset, v_decision, p->>'option', p->>'by');
    v_detail := format('%s 구매요청 — %s', v_part, coalesce(v_sup_name, v_sup));

  elsif v_skill = 'skill:hold-lot' then
    select * into v_q from ent.quality_profiles where asset = v_asset;
    v_lot := coalesce(v_params->>'lot', v_q.auto_lot);
    insert into ent.lot_dispositions (lot, asset, kind, status, decision_id) values (v_lot, v_asset, 'HOLD', '격리 · 전수검사 대기', v_decision);
    v_ref := v_lot; v_detail := format('로트 %s 격리 · 전수검사', v_lot);

  elsif v_skill = 'skill:release-lot' then
    select * into v_q from ent.quality_profiles where asset = v_asset;
    v_lot := coalesce(v_params->>'lot', v_q.gen_lot);
    insert into ent.lot_dispositions (lot, asset, kind, status, decision_id) values (v_lot, v_asset, 'RELEASE', '샘플검사 후 출하 승인', v_decision);
    v_ref := v_lot; v_detail := format('로트 %s 출하 승인', v_lot);

  elsif v_skill = 'skill:substitute-shipment' then
    select * into v_inv from ent.fg_inventory where asset = v_asset;
    select * into v_q from ent.quality_profiles where asset = v_asset;
    v_ref := 'SH-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.shipments (id, item, qty, source, asset, decision_id) values (v_ref, v_inv.fg_item, v_q.auto_qty, 'WH-1 완제품 재고', v_asset, v_decision);
    v_detail := format('%s %s개 재고 대체 출하', v_inv.fg_item, v_q.auto_qty);

  elsif v_skill = 'skill:demand-control' then
    insert into ent.ems_actions (action, decision_id) values (coalesce(v_params->>'action', 'HYD-03 비긴급 오더 야간 이동에 맞춰 피크 수요 목표 설정'), v_decision);
    v_ref := 'EMS'; v_detail := coalesce(v_params->>'action', 'HYD-03 비긴급 오더 야간 이동에 맞춰 피크 수요 목표 설정');
  end if;

  insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint)
  values (v_id, v_system, v_skill, v_ref, v_detail, v_asset, v_decision, p->>'option', p->>'by', v_fp);
  return jsonb_build_object('id', v_id, 't', now(), 'system', v_system, 'skill', v_skill, 'ref', v_ref, 'detail', v_detail,
                            'asset', v_asset, 'decision', v_decision, 'option', p->>'option', 'by', p->>'by');
end $$;

-- 교육용 초기화: 실행 결과만 지우고 마스터는 유지한다 (enterprise-sim /api/reset 과 같은 의미)
create or replace function ent.reset_executions() returns void language plpgsql as $$
begin
  delete from ent.transactions; delete from ent.work_orders; delete from ent.purchase_requests; delete from ent.shipments;
  delete from ent.lot_dispositions; delete from ent.ems_actions;
  update ent.production_orders set asset = moved_from, moved_from = null where moved_from is not null;
end $$;

-- ---------------------------------------------------------------- 권한 · RLS
grant usage on schema ent to anon, authenticated, service_role;
grant select on all tables in schema ent to anon, authenticated;
grant all on all tables in schema ent to service_role;
grant usage, select on all sequences in schema ent to service_role;
grant execute on all functions in schema ent to anon, authenticated, service_role;
-- 읽기 RPC 는 누구나, 쓰기 RPC(exec_skill · reset_executions)는 서비스 키만. 에이전트가 실제로 쓰는 읽기 경로는 anon/authenticated 가
-- 아니라 enterprise-mcp + hyd_enterprise_reader 역할이다(20261004000003; A143 정정).
revoke execute on function ent.exec_skill(jsonb) from anon, authenticated;
revoke execute on function ent.reset_executions() from anon, authenticated;

do $$ declare t text; begin
  foreach t in array array['assets', 'production_orders', 'sales_contracts', 'fg_inventory', 'maintenance_profiles', 'maintenance_history',
                           'quality_profiles', 'parts', 'suppliers', 'energy_demand', 'work_orders', 'purchase_requests', 'shipments',
                           'lot_dispositions', 'ems_actions', 'transactions'] loop
    execute format('alter table ent.%I enable row level security', t);
    execute format('drop policy if exists %I on ent.%I', t || '_read_all', t);
    execute format('create policy %I on ent.%I for select to anon, authenticated using (true)', t || '_read_all', t);
  end loop;
end $$;
