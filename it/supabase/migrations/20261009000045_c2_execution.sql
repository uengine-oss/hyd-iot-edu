-- C2 (확정 TODO C, 2026-10-09) 승인 뒤 실행 부품의 업무 DB 쪽. 추가만 한다(기존 표 · 행은 바꾸지 않고, 함수는 같은 서명으로 본문을 넓힌다).
--   1. 예비품 재고(ent.spare_stock) · 재고 이동(ent.stock_movements) — ERP 재고 감시가 재주문점 이탈을 본다(시나리오 C 시작).
--   2. 부품별 공급사 견적(ent.part_quotes) — ent.suppliers 는 공급사 하나에 부품 하나(쿨러 코어)라 씰 키트 견적을 둘 곳이 없었다
--      (migration 37 머리말). 값은 온톨로지 SUPPLIED_BY(it/neo4j/v2/instances.cypher)와 같다: 씰 키트 sup:a 35/0.12/2 · sup:b 55/0.02/5 ·
--      sup:c 20/0.30/1(비AVL), 팬 베어링 sup:a 18/0.10/1 · sup:b 28/0.03/3. 쿨러 코어는 ent.suppliers 그대로 읽는다(같은 값을 두 곳에 두지 않음).
--   3. 정비창 규칙(ent.maintenance_window_rules) → 다가오는 정비창(ent.next_maintenance_windows) — 시나리오 B 의 정비 시점.
--   4. 발주(purchase_requests)에 부품 번호 · 수량 · 단가 · 금액 · 리드타임 · 입고 예정, 입고 표(ent.goods_receipts).
--   5. 작업지시(work_orders)에 정비창 id · 시작 시각 · 완료 시각, CMMS 일정(ent.cmms_calendar) · 처리 건 기록(ent.case_records).
--   6. ent.exec_skill: procure-part 가 수량 · 금액을 싣고 재고의 입고 예정을 올린다. 새 스킬 receive-goods(입고 · 검수) ·
--      complete-maintenance(정비 완료 · 부품 소모) · calendar-entry(CMMS 일정) · record-case(처리 건 기록) · issue-spare(예비품 출고, 수업 원인 버튼).
-- 금액 만원, 시간은 실제 시각(timestamptz). 교육용 가상 값.

-- ---------------------------------------------------------------- 1. 예비품 재고 · 이동
create table if not exists ent.spare_stock (                 -- ERP: 중요 예비품 재고
  part_no text primary key references ent.parts(part_no),
  on_hand integer not null check (on_hand >= 0),             -- 창고 실물
  reserved integer not null default 0 check (reserved >= 0), -- 예정된 정비에 묶인 수량
  on_order integer not null default 0 check (on_order >= 0), -- 발주 후 입고 예정
  reorder_point integer not null check (reorder_point >= 0), -- 가용(on_hand - reserved)이 이보다 작으면 재고 기준 이탈
  target_stock integer not null check (target_stock >= 0),   -- 보충 목표 (필요량 = 목표 - 가용 - 입고 예정)
  reserved_for text,                                        -- 예약한 설비 (경보의 설비 키, ent.assets.code — 자산 행은 seed 가 넣으므로 FK 없음)
  base_on_hand integer not null,                            -- 수업 초기화 값
  base_reserved integer not null default 0,
  below_since timestamptz,                                  -- 재주문점 아래로 내려간 시각 (경보 회차 키, 회복하면 null)
  updated_at timestamptz not null default now()
);
comment on table ent.spare_stock is 'C2: ERP 중요 예비품 재고. 가용 = on_hand - reserved, 가용 < reorder_point 면 재고 기준 이탈(SPARE_BELOW_MIN)';

create table if not exists ent.stock_movements (             -- ERP: 재고 이동 원장 (출고 · 소모 · 입고 · 초기화)
  id bigserial primary key,
  part_no text not null references ent.parts(part_no),
  kind text not null check (kind in ('ISSUE', 'CONSUME', 'RECEIPT', 'RESET')),
  qty integer not null,
  asset text,
  ref text,                                                 -- 출고 번호 · 작업지시 · 입고 번호
  by_whom text,
  reason text,
  on_hand_after integer not null,
  available_after integer not null,
  at timestamptz not null default now()
);

-- 쿨러 코어 부품 행은 seed.sql 이 넣는다(같은 값, on conflict do nothing). 이 마이그레이션의 재고 행이 참조하므로 먼저 둔다.
insert into ent.parts (part_no, name, std_price) values ('P-CLR-CORE', '쿨러 코어', 250) on conflict (part_no) do nothing;
insert into ent.spare_stock (part_no, on_hand, reserved, on_order, reorder_point, target_stock, reserved_for, base_on_hand, base_reserved) values
  ('P-PMP-SEAL', 4, 2, 0, 2, 7, 'HYD-03', 4, 2),   -- HYD-03 예방 교체에 2개 예약 · 가용 2 = 재주문점 (B 교체 1개 소모로 이탈)
  ('P-FAN-BRG', 3, 0, 0, 1, 3, 'HYD-03', 3, 0),
  ('P-CLR-CORE', 2, 0, 0, 1, 2, 'HYD-01', 2, 0)
on conflict (part_no) do nothing;

create or replace function ent.refresh_spare_flag(p_part text) returns void language sql as $$
  update ent.spare_stock set below_since = case when on_hand - reserved < reorder_point then coalesce(below_since, now()) else null end,
         updated_at = now()
   where part_no = p_part
$$;

-- ---------------------------------------------------------------- 2. 부품별 공급사 견적
create table if not exists ent.part_quotes (
  part_no text not null references ent.parts(part_no),
  supplier_id text not null,                                -- ent.suppliers.id (공급사 행은 seed 가 넣으므로 FK 없음, 읽을 때 join)
  price numeric not null check (price >= 0),                -- 단가 (만원)
  fail_rate numeric not null check (fail_rate >= 0),
  lead_d integer not null check (lead_d >= 0),
  primary key (part_no, supplier_id)
);
insert into ent.part_quotes (part_no, supplier_id, price, fail_rate, lead_d) values
  ('P-PMP-SEAL', 'sup:a', 35, 0.12, 2), ('P-PMP-SEAL', 'sup:b', 55, 0.02, 5), ('P-PMP-SEAL', 'sup:c', 20, 0.30, 1),
  ('P-FAN-BRG', 'sup:a', 18, 0.10, 1), ('P-FAN-BRG', 'sup:b', 28, 0.03, 3)
on conflict (part_no, supplier_id) do nothing;

-- 견적 한 줄: part_quotes 가 우선, 없으면 그 부품의 ent.suppliers 행(쿨러 코어)
create or replace function ent.quote_rows(p_part text) returns table (part_no text, supplier_id text, supplier_name text, price numeric,
                                                                     fail_rate numeric, lead_d integer, avl boolean)
language sql stable as $$
  select q.part_no, q.supplier_id, s.name, q.price, q.fail_rate, q.lead_d, s.avl
    from ent.part_quotes q join ent.suppliers s on s.id = q.supplier_id where q.part_no = p_part
  union all
  select s.part_no, s.id, s.name, s.price, s.fail_rate, s.lead_d, s.avl
    from ent.suppliers s where s.part_no = p_part and not exists (select 1 from ent.part_quotes q where q.part_no = p_part)
$$;

-- ---------------------------------------------------------------- 3. 정비창
create table if not exists ent.maintenance_window_rules (     -- CMMS: 반복 정비창 (야간 · 주말)
  asset text not null,                                      -- ent.assets.code (자산 행은 seed 가 넣으므로 FK 없음)
  kind text not null check (kind in ('N', 'W')),            -- N 야간 정비창 · W 주말 계획 정지
  label text not null,
  first_at timestamptz not null,
  period_h numeric not null check (period_h > 0),
  duration_h numeric not null check (duration_h > 0),
  primary key (asset, kind)
);
insert into ent.maintenance_window_rules (asset, kind, label, first_at, period_h, duration_h)
select a.code, k.kind, k.label, now() + make_interval(hours => k.first_h), k.period_h, k.duration_h
  from (values ('HYD-01'), ('HYD-02'), ('HYD-03')) a(code) cross join (values ('N', '야간 정비창', 9, 24, 4), ('W', '주말 계획 정지', 105, 168, 24)) k(kind, label, first_h, period_h, duration_h)
on conflict (asset, kind) do nothing;

-- 다가오는(또는 진행 중인) 정비창 p_n 개씩. id 는 설비 · 종류 · 시작 시각으로 정해져 같은 창은 같은 id 다.
create or replace function ent.next_maintenance_windows(p_asset text, p_n integer default 3)
returns table (id text, asset text, kind text, label text, starts_at timestamptz, ends_at timestamptz)
language sql stable as $$
  select 'MW-' || r.asset || '-' || r.kind || '-' || to_char(st at time zone 'UTC', 'YYYYMMDDHH24MI'), r.asset, r.kind, r.label, st,
         st + make_interval(secs => r.duration_h * 3600)
    from ent.maintenance_window_rules r
    cross join lateral (select greatest(0, ceil(extract(epoch from (now() - r.first_at)) / 3600 / r.period_h - r.duration_h / r.period_h))::int k0) b
    cross join lateral generate_series(b.k0, b.k0 + greatest(p_n, 1) - 1) g(k)
    cross join lateral (select r.first_at + make_interval(secs => g.k * r.period_h * 3600) st) s
   where r.asset = p_asset
   order by st
$$;

-- ---------------------------------------------------------------- 4 · 5. 발주 · 입고 · 작업지시 · 일정 · 기록
alter table ent.purchase_requests add column if not exists part_no text references ent.parts(part_no);
alter table ent.purchase_requests add column if not exists qty integer check (qty is null or qty > 0);
alter table ent.purchase_requests add column if not exists unit_price numeric;
alter table ent.purchase_requests add column if not exists amount numeric;
alter table ent.purchase_requests add column if not exists lead_d integer;
alter table ent.purchase_requests add column if not exists expected_at timestamptz;
alter table ent.purchase_requests add column if not exists received_at timestamptz;
comment on column ent.purchase_requests.amount is 'C2: 발주 금액(만원) = 수량 × 단가. 승인 경로가 확정한 값';
comment on column ent.purchase_requests.expected_at is 'C2: 입고 예정(업무 시각 = 발주 + 리드타임). 수업에서는 process 의 대기 압축으로 몇 분 뒤 입고된다';

create table if not exists ent.goods_receipts (               -- ERP: 입고 · 검수
  id text primary key,                                      -- GR-MMDD-XXXX
  pr_id text not null references ent.purchase_requests(id),
  part_no text,
  qty integer not null check (qty > 0),
  lot text not null,
  inspection text not null default '합격',
  decision_id text,
  received_at timestamptz not null default now(),
  unique (pr_id)
);

alter table ent.work_orders add column if not exists window_id text;
alter table ent.work_orders add column if not exists window_starts_at timestamptz;
alter table ent.work_orders add column if not exists completed_at timestamptz;

create table if not exists ent.cmms_calendar (                -- CMMS: 정비 · 생산 공지 일정 (MCP 쓰기 도구가 승인 뒤 기록)
  id text primary key,                                      -- CAL-MMDD-XXXX
  asset text references ent.assets(code),
  title text not null,
  starts_at timestamptz not null,
  ends_at timestamptz,
  wo_ref text,
  note text,
  decision_id text,
  created_at timestamptz not null default now()
);

create table if not exists ent.case_records (                 -- 처리 건 기록 (지식 자산화용 한 장)
  id text primary key,                                      -- CASE-MMDD-XXXX
  asset text,
  title text not null,
  body text,
  proc_inst_id text,
  decision_id text,
  created_at timestamptz not null default now()
);

-- 읽기 권한: enterprise-mcp 전용 읽기 계정
do $$
declare t text;
begin
  foreach t in array array['spare_stock', 'stock_movements', 'part_quotes', 'maintenance_window_rules', 'goods_receipts', 'cmms_calendar', 'case_records'] loop
    execute format('alter table ent.%I enable row level security', t);
    execute format('drop policy if exists %I on ent.%I', t || '_read_all', t);
    execute format('create policy %I on ent.%I for select to anon, authenticated using (true)', t || '_read_all', t);
    execute format('drop policy if exists enterprise_mcp_reader on ent.%I', t);
    execute format('create policy enterprise_mcp_reader on ent.%I for select to hyd_enterprise_reader using (true)', t);
    execute format('grant select on ent.%I to hyd_enterprise_reader', t);
  end loop;
end $$;
grant select on ent.part_quotes, ent.suppliers to hyd_enterprise_reader;

-- ---------------------------------------------------------------- 읽기 RPC (enterprise-sim · enterprise-mcp 같은 값)
create or replace function ent.spare_stock_read(p_part text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'ERP',
    'facts', (select jsonb_build_object('part_no', s.part_no, 'on_hand', s.on_hand, 'reserved', s.reserved, 'available', s.on_hand - s.reserved,
                                        'on_order', s.on_order, 'reorder_point', s.reorder_point, 'target_stock', s.target_stock,
                                        'need_qty', greatest(s.target_stock - (s.on_hand - s.reserved) - s.on_order, 0),
                                        'below_reorder_point', s.on_hand - s.reserved < s.reorder_point, 'below_since', s.below_since,
                                        'reserved_for', s.reserved_for)
                from ent.spare_stock s where s.part_no = p_part or p_part is null order by s.part_no limit 1),
    'records', coalesce((select jsonb_agg(jsonb_build_object('part_no', s.part_no, 'name', p.name, 'on_hand', s.on_hand, 'reserved', s.reserved,
                                        'available', s.on_hand - s.reserved, 'on_order', s.on_order, 'reorder_point', s.reorder_point,
                                        'target_stock', s.target_stock, 'need_qty', greatest(s.target_stock - (s.on_hand - s.reserved) - s.on_order, 0),
                                        'below_reorder_point', s.on_hand - s.reserved < s.reorder_point, 'below_since', s.below_since,
                                        'reserved_for', s.reserved_for) order by s.part_no)
                from ent.spare_stock s join ent.parts p on p.part_no = s.part_no where s.part_no = p_part or p_part is null), '[]'::jsonb),
    'movements', coalesce((select jsonb_agg(to_jsonb(m) order by m.id desc) from (select * from ent.stock_movements m
                 where m.part_no = p_part or p_part is null order by m.id desc limit 20) m), '[]'::jsonb),
    'as_of', now())
$$;

create or replace function ent.part_quotes_read(p_part text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'SCM',
    'facts', case when not exists (select 1 from ent.parts where part_no = p_part) then null
                  else jsonb_build_object('part_no', p_part, 'std_price', (select std_price from ent.parts where part_no = p_part)) end,
    'records', coalesce((select jsonb_agg(jsonb_build_object('supplier', q.supplier_id, 'name', q.supplier_name, 'price', q.price,
                                          'fail_rate', q.fail_rate, 'lead_d', q.lead_d, 'avl', q.avl) order by q.supplier_id)
                         from ent.quote_rows(p_part) q), '[]'::jsonb))
$$;

create or replace function ent.maintenance_windows_read(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'CMMS',
    'facts', case when not exists (select 1 from ent.assets where code = p_asset) then null else
             (select jsonb_build_object('next_window_id', w.id, 'next_window_label', w.label, 'next_window_at', w.starts_at,
                                        'next_window_in_h', ent.hours_from_now(w.starts_at))
                from ent.next_maintenance_windows(p_asset, 1) w order by w.starts_at limit 1) end,
    'records', coalesce((select jsonb_agg(jsonb_build_object('id', w.id, 'kind', w.kind, 'label', w.label, 'starts_at', w.starts_at,
                                          'ends_at', w.ends_at, 'starts_in_h', ent.hours_from_now(w.starts_at)) order by w.starts_at)
                         from ent.next_maintenance_windows(p_asset, 3) w), '[]'::jsonb),
    'calendar', coalesce((select jsonb_agg(to_jsonb(c) order by c.starts_at) from ent.cmms_calendar c where c.asset = p_asset), '[]'::jsonb),
    'as_of', now())
$$;

create or replace function ent.purchase_order_read(p_ref text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'ERP',
    'facts', (select to_jsonb(r) || jsonb_build_object('expected_in_h', ent.hours_from_now(r.expected_at)) from ent.purchase_requests r where r.id = p_ref),
    'records', coalesce((select jsonb_agg(to_jsonb(g)) from ent.goods_receipts g where g.pr_id = p_ref), '[]'::jsonb))
$$;

grant execute on function ent.spare_stock_read(text), ent.part_quotes_read(text), ent.maintenance_windows_read(text), ent.purchase_order_read(text),
                          ent.next_maintenance_windows(text, integer), ent.quote_rows(text)
  to anon, authenticated, service_role, hyd_enterprise_reader;

-- ---------------------------------------------------------------- 6. 실행 (process 만 부른다 — 사람 승인 뒤 또는 수업 원인 버튼)
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
  v_row ent.transactions;
  v_system text;
  v_ref text; v_detail text; v_id text;
  v_alt text; v_order text; v_sup text; v_sup_name text; v_part text; v_lot text; v_inv ent.fg_inventory; v_q ent.quality_profiles;
  v_before jsonb; v_after jsonb;
  -- C2
  v_part_no text; v_qty integer; v_quote record; v_window record; v_window_label text; v_window_id text; v_window_at timestamptz;
  v_pr ent.purchase_requests; v_wo ent.work_orders; v_stock ent.spare_stock; v_std ent.task_standards; v_at timestamptz;
begin
  v_system := case v_skill
    when 'skill:schedule-maintenance' then 'sys:cmms' when 'skill:reallocate-production' then 'sys:mes'
    when 'skill:procure-part' then 'sys:erp' when 'skill:hold-lot' then 'sys:qms' when 'skill:release-lot' then 'sys:qms'
    when 'skill:substitute-shipment' then 'sys:erp' when 'skill:demand-control' then 'sys:ems'
    when 'skill:receive-goods' then 'sys:erp' when 'skill:complete-maintenance' then 'sys:cmms'
    when 'skill:calendar-entry' then 'sys:cmms' when 'skill:record-case' then 'sys:cmms' when 'skill:issue-spare' then 'sys:erp' end;
  if v_system is null then
    raise exception 'unknown or non-enterprise skill %', v_skill using errcode = '22023';
  end if;
  if not exists (select 1 from ent.assets where code = v_asset) then
    raise exception 'INVALID: unknown asset %', v_asset using errcode = '22023';
  end if;

  if v_decision is not null then
    perform pg_advisory_xact_lock(hashtextextended('ent.exec_skill:' || v_decision || ':' || v_skill, 0));
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and compensates is null;
    if found then
      if v_prior.fingerprint <> v_fp then
        raise exception 'idempotency conflict: decision/skill already executed with different input' using errcode = '23505';
      end if;
      return ent.tx_response(v_prior);
    end if;
  end if;

  v_id := 'TX-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));

  if v_skill = 'skill:schedule-maintenance' then
    v_ref := 'WO-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    v_window_label := v_params->>'window';
    if v_params ? 'window_id' then                       -- C2: 승인된 정비창 id → 라벨 · 시작 시각 (설비가 다르거나 없는 창은 거절)
      select * into v_window from ent.next_maintenance_windows(v_asset, 14) w where w.id = v_params->>'window_id';
      if not found then
        raise exception 'INVALID: unknown maintenance window % for %', v_params->>'window_id', v_asset using errcode = '22023';
      end if;
      v_window_id := v_window.id; v_window_at := v_window.starts_at;
      v_window_label := coalesce(v_window_label, v_window.label || ' ' || to_char(v_window.starts_at at time zone 'Asia/Seoul', 'MM-DD HH24:MI'));
    elsif v_params ? 'window_starts_at' then
      v_window_at := (v_params->>'window_starts_at')::timestamptz;
    end if;
    insert into ent.work_orders (id, asset, task, window_label, decision_id, option_id, requested_by, window_id, window_starts_at)
    values (v_ref, v_asset, coalesce(v_params->>'task', '쿨러 핀 세척 (SOP-COOL-02)'),
            coalesce(v_window_label, case when (p->>'option') like '%derate%' then '야간 정비창' else '즉시' end), v_decision, p->>'option', p->>'by',
            v_window_id, v_window_at);
    v_detail := format('%s %s — %s', v_asset, coalesce(v_params->>'task', '쿨러 핀 세척 (SOP-COOL-02)'), coalesce(v_window_label, '즉시'));
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_ref;

  elsif v_skill = 'skill:reallocate-production' then
    select order_id, alt_asset into v_order, v_alt from ent.production_orders where asset = v_asset order by order_id limit 1 for update;
    if v_order is null then
      v_ref := '-'; v_detail := format('%s에 이관할 오더 없음', v_asset);
    else
      v_alt := coalesce(v_params->>'to', v_alt);
      if v_alt is null or v_alt = v_asset or not exists (select 1 from ent.assets where code = v_alt) then
        raise exception 'INVALID: unknown or same target asset %', v_alt using errcode = '22023';
      end if;
      select to_jsonb(o) into v_before from ent.production_orders o where o.order_id = v_order;
      update ent.production_orders set moved_from = v_asset, asset = v_alt where order_id = v_order;
      select to_jsonb(o) into v_after from ent.production_orders o where o.order_id = v_order;
      v_ref := v_order; v_detail := format('%s %s → %s 이관', v_order, v_asset, v_alt);
    end if;

  elsif v_skill = 'skill:procure-part' then
    v_sup := coalesce(v_params->>'supplier', 'sup:b');
    select name into v_sup_name from ent.suppliers where id = v_sup;
    if not found then
      raise exception 'INVALID: unknown supplier %', v_sup using errcode = '22023';
    end if;
    v_part := coalesce(v_params->>'part', '쿨러 코어');
    v_ref := 'PR-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    if v_params ? 'part_no' then                         -- C2: 부품 번호 · 수량이 있는 발주 — 견적 · AVL · 금액을 ERP 가 다시 확인한다
      v_part_no := v_params->>'part_no';
      v_qty := (v_params->>'qty')::integer;
      if v_qty is null or v_qty <= 0 then
        raise exception 'INVALID: purchase quantity must be positive' using errcode = '22023';
      end if;
      select * into v_quote from ent.quote_rows(v_part_no) q where q.supplier_id = v_sup;
      if not found then
        raise exception 'INVALID: supplier % has no quote for %', v_sup, v_part_no using errcode = '22023';
      end if;
      if not v_quote.avl then
        raise exception 'INVALID: supplier % is not on the approved vendor list (AVL)', v_sup using errcode = '22023';
      end if;
      if v_params ? 'amount' and (v_params->>'amount')::numeric <> v_quote.price * v_qty then
        raise exception 'INVALID: approved amount % differs from quote % x %', v_params->>'amount', v_qty, v_quote.price using errcode = '22023';
      end if;
      select name into v_part from ent.parts where part_no = v_part_no;
      insert into ent.purchase_requests (id, part, supplier, supplier_name, asset, decision_id, option_id, requested_by,
                                         part_no, qty, unit_price, amount, lead_d, expected_at)
      values (v_ref, v_part, v_sup, v_sup_name, v_asset, v_decision, p->>'option', p->>'by',
              v_part_no, v_qty, v_quote.price, v_quote.price * v_qty, v_quote.lead_d, now() + make_interval(days => v_quote.lead_d));
      update ent.spare_stock set on_order = on_order + v_qty, updated_at = now() where part_no = v_part_no;
      v_detail := format('%s %s개 발주 — %s, %s만원, 리드타임 %s일', v_part, v_qty, v_sup_name, v_quote.price * v_qty, v_quote.lead_d);
    else
      insert into ent.purchase_requests (id, part, supplier, supplier_name, asset, decision_id, option_id, requested_by)
      values (v_ref, v_part, v_sup, v_sup_name, v_asset, v_decision, p->>'option', p->>'by');
      v_detail := format('%s 구매요청 — %s', v_part, v_sup_name);
    end if;
    select to_jsonb(r) into v_after from ent.purchase_requests r where r.id = v_ref;

  elsif v_skill = 'skill:receive-goods' then              -- C2: 발주 한 건의 입고 · 검수 (공급사 납품 모사 포함)
    select * into v_pr from ent.purchase_requests where id = v_params->>'ref' for update;
    if not found then raise exception 'INVALID: no such purchase request %', v_params->>'ref' using errcode = '22023'; end if;
    if v_pr.qty is null then raise exception 'INVALID: purchase request % has no quantity to receive', v_pr.id using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then
      raise exception 'INVALID: purchase request % cannot be received in status %', v_pr.id, v_pr.status using errcode = '22023';
    end if;
    v_before := to_jsonb(v_pr);
    v_ref := 'GR-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    v_lot := coalesce(v_params->>'lot', 'LOT-' || to_char(now(), 'YYMMDD') || '-' || upper(substr(md5(random()::text), 1, 3)));
    insert into ent.goods_receipts (id, pr_id, part_no, qty, lot, inspection, decision_id)
    values (v_ref, v_pr.id, v_pr.part_no, v_pr.qty, v_lot, coalesce(v_params->>'inspection', '합격'), v_decision);
    update ent.purchase_requests set status = '입고 완료', received_at = now() where id = v_pr.id;
    update ent.spare_stock set on_hand = on_hand + v_pr.qty, on_order = greatest(on_order - v_pr.qty, 0) where part_no = v_pr.part_no
      returning * into v_stock;
    if v_stock.part_no is not null then
      perform ent.refresh_spare_flag(v_pr.part_no);
      insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
      values (v_pr.part_no, 'RECEIPT', v_pr.qty, v_asset, v_ref, p->>'by', format('발주 %s 입고', v_pr.id), v_stock.on_hand, v_stock.on_hand - v_stock.reserved);
    end if;
    v_detail := format('%s %s개 입고 · 검수 %s (발주 %s, 로트 %s)', v_pr.part, v_pr.qty, coalesce(v_params->>'inspection', '합격'), v_pr.id, v_lot);
    select to_jsonb(g) into v_after from ent.goods_receipts g where g.id = v_ref;

  elsif v_skill = 'skill:complete-maintenance' then       -- C2: 작업지시 완료 + SOP 표준 부품 소모
    select * into v_wo from ent.work_orders where id = v_params->>'ref' for update;
    if not found then raise exception 'INVALID: no such work order %', v_params->>'ref' using errcode = '22023'; end if;
    if v_wo.status <> '배정됨' then
      raise exception 'INVALID: work order % cannot be completed in status %', v_wo.id, v_wo.status using errcode = '22023';
    end if;
    v_before := to_jsonb(v_wo);
    update ent.work_orders set status = '완료', completed_at = now() where id = v_wo.id;
    insert into ent.maintenance_history (asset, wo, task, performed_at) values (v_wo.asset, v_wo.id, v_wo.task, now());
    select * into v_std from ent.task_standards where sop = v_params->>'sop';
    if found and v_std.part_no is not null and v_std.part_qty > 0 then
      update ent.spare_stock set on_hand = greatest(on_hand - v_std.part_qty, 0) where part_no = v_std.part_no returning * into v_stock;
      if v_stock.part_no is not null then
        perform ent.refresh_spare_flag(v_std.part_no);
        insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
        values (v_std.part_no, 'CONSUME', v_std.part_qty, v_wo.asset, v_wo.id, p->>'by', format('%s 정비 소모', v_params->>'sop'),
                v_stock.on_hand, v_stock.on_hand - v_stock.reserved);
      end if;
    end if;
    v_ref := v_wo.id;
    v_detail := format('%s 작업지시 %s 완료 (%s)%s', v_wo.asset, v_wo.id, v_wo.task,
                       case when v_std.part_no is not null then format(' — %s %s개 소모', v_std.part_no, v_std.part_qty) else '' end);
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_wo.id;

  elsif v_skill = 'skill:calendar-entry' then             -- C2: CMMS 일정 (MCP 쓰기 도구 add_calendar_entry)
    v_ref := 'CAL-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    v_at := coalesce((v_params->>'starts_at')::timestamptz, now());
    insert into ent.cmms_calendar (id, asset, title, starts_at, ends_at, wo_ref, note, decision_id)
    values (v_ref, v_asset, coalesce(nullif(v_params->>'title', ''), '정비 일정'), v_at,
            case when v_params ? 'duration_h' then v_at + make_interval(secs => (v_params->>'duration_h')::numeric * 3600) end,
            v_params->>'wo_ref', v_params->>'note', v_decision);
    v_detail := format('%s 일정 등록 — %s (%s)', v_asset, coalesce(nullif(v_params->>'title', ''), '정비 일정'), to_char(v_at at time zone 'Asia/Seoul', 'MM-DD HH24:MI'));
    select to_jsonb(c) into v_after from ent.cmms_calendar c where c.id = v_ref;

  elsif v_skill = 'skill:record-case' then                -- C2: 처리 건 기록 한 장 (MCP 쓰기 도구 record_case)
    v_ref := 'CASE-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.case_records (id, asset, title, body, proc_inst_id, decision_id)
    values (v_ref, v_asset, coalesce(nullif(v_params->>'title', ''), '처리 건 기록'), v_params->>'body', v_params->>'proc_inst_id', v_decision);
    v_detail := format('처리 건 기록 — %s', coalesce(nullif(v_params->>'title', ''), '처리 건 기록'));
    select to_jsonb(c) into v_after from ent.case_records c where c.id = v_ref;

  elsif v_skill = 'skill:issue-spare' then                -- C2: 예비품 출고 (수업의 원인 버튼 — 정비 · 타 라인 사용으로 재고가 줄어든 상황)
    v_part_no := coalesce(v_params->>'part_no', 'P-PMP-SEAL');
    v_qty := coalesce((v_params->>'qty')::integer, 1);
    if v_qty <= 0 then raise exception 'INVALID: issue quantity must be positive' using errcode = '22023'; end if;
    select * into v_stock from ent.spare_stock where part_no = v_part_no for update;
    if not found then raise exception 'INVALID: % is not a managed spare part', v_part_no using errcode = '22023'; end if;
    if v_stock.on_hand < v_qty then
      raise exception 'INVALID: only % of % on hand', v_stock.on_hand, v_part_no using errcode = '22023';
    end if;
    v_before := to_jsonb(v_stock);
    update ent.spare_stock set on_hand = on_hand - v_qty where part_no = v_part_no returning * into v_stock;
    perform ent.refresh_spare_flag(v_part_no);
    v_ref := 'GI-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
    values (v_part_no, 'ISSUE', v_qty, v_asset, v_ref, p->>'by', coalesce(v_params->>'reason', '예비품 출고'), v_stock.on_hand, v_stock.on_hand - v_stock.reserved);
    v_detail := format('%s %s개 출고 (%s) — 가용 %s / 재주문점 %s', v_part_no, v_qty, coalesce(v_params->>'reason', '예비품 출고'),
                       v_stock.on_hand - v_stock.reserved, v_stock.reorder_point);
    select to_jsonb(s) into v_after from ent.spare_stock s where s.part_no = v_part_no;

  elsif v_skill = 'skill:hold-lot' then
    select * into v_q from ent.quality_profiles where asset = v_asset;
    v_lot := coalesce(v_params->>'lot', v_q.auto_lot);
    insert into ent.lot_dispositions (lot, asset, kind, status, decision_id) values (v_lot, v_asset, 'HOLD', '격리 · 전수검사 대기', v_decision);
    v_ref := v_lot; v_detail := format('로트 %s 격리 · 전수검사', v_lot);
    select to_jsonb(d) into v_after from ent.lot_dispositions d where d.lot = v_lot and d.decision_id is not distinct from v_decision order by d.id desc limit 1;

  elsif v_skill = 'skill:release-lot' then
    select * into v_q from ent.quality_profiles where asset = v_asset;
    v_lot := coalesce(v_params->>'lot', v_q.gen_lot);
    insert into ent.lot_dispositions (lot, asset, kind, status, decision_id) values (v_lot, v_asset, 'RELEASE', '샘플검사 후 출하 승인', v_decision);
    v_ref := v_lot; v_detail := format('로트 %s 출하 승인', v_lot);
    select to_jsonb(d) into v_after from ent.lot_dispositions d where d.lot = v_lot and d.decision_id is not distinct from v_decision order by d.id desc limit 1;

  elsif v_skill = 'skill:substitute-shipment' then
    select * into v_inv from ent.fg_inventory where asset = v_asset;
    select * into v_q from ent.quality_profiles where asset = v_asset;
    v_ref := 'SH-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.shipments (id, item, qty, source, asset, decision_id) values (v_ref, v_inv.fg_item, v_q.auto_qty, 'WH-1 완제품 재고', v_asset, v_decision);
    v_detail := format('%s %s개 재고 대체 출하', v_inv.fg_item, v_q.auto_qty);
    select to_jsonb(s) into v_after from ent.shipments s where s.id = v_ref;

  elsif v_skill = 'skill:demand-control' then
    insert into ent.ems_actions (action, decision_id) values (coalesce(v_params->>'action', 'HYD-03 비긴급 오더 야간 이동에 맞춰 피크 수요 목표 설정'), v_decision);
    v_ref := 'EMS'; v_detail := coalesce(v_params->>'action', 'HYD-03 비긴급 오더 야간 이동에 맞춰 피크 수요 목표 설정');
    select to_jsonb(e) into v_after from ent.ems_actions e where e.decision_id is not distinct from v_decision order by e.id desc limit 1;
  end if;

  insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, before, after)
  values (v_id, v_system, v_skill, v_ref, v_detail, v_asset, v_decision, p->>'option', p->>'by', v_fp, v_before, v_after)
  returning * into v_row;
  return ent.tx_response(v_row);
end $$;

revoke execute on function ent.exec_skill(jsonb) from public, anon, authenticated;
grant execute on function ent.exec_skill(jsonb) to service_role;

-- 수업 초기화: 예비품 재고를 기준값으로 (출고 버튼 되돌리기). 이동 원장에 RESET 을 남긴다.
create or replace function ent.reset_spare_stock(p_part text default null) returns jsonb language plpgsql as $$
declare r ent.spare_stock;
begin
  for r in select * from ent.spare_stock where p_part is null or part_no = p_part for update loop
    update ent.spare_stock set on_hand = base_on_hand, reserved = base_reserved, on_order = 0, below_since = null, updated_at = now()
     where part_no = r.part_no;
    insert into ent.stock_movements (part_no, kind, qty, ref, by_whom, reason, on_hand_after, available_after)
    values (r.part_no, 'RESET', r.base_on_hand - r.on_hand, 'RESET', 'instructor', '수업 초기화', r.base_on_hand, r.base_on_hand - r.base_reserved);
  end loop;
  return ent.spare_stock_read(p_part);
end $$;

-- 시나리오 시각 · 실행 초기화에 C2 표를 포함한다(본문은 migration 17 + 아래 추가)
create or replace function ent.reanchor_scenario_times() returns void language plpgsql as $$
begin
  update ent.production_orders o set due_at = now() + make_interval(hours => s.due_h), alt_free_at = now() + make_interval(hours => s.alt_h)
    from (values ('MO-0930-0412', 6, 8), ('MO-0930-0415', 20, 4), ('MO-0930-0419', 3, 2)) s(order_id, due_h, alt_h)
   where o.order_id = s.order_id;
  update ent.fg_inventory i set ship_at = now() + make_interval(hours => s.h)
    from (values ('HYD-01', 2), ('HYD-02', 10), ('HYD-03', 3)) s(asset, h) where i.asset = s.asset;
  update ent.maintenance_profiles set night_window_at = now() + interval '9 hours';
  update ent.maintenance_history h set performed_at = now() - make_interval(days => s.d)
    from (values ('WO-HIST-01-1', 21), ('WO-HIST-01-2', 38), ('WO-HIST-01-3', 55), ('WO-HIST-02-1', 21), ('WO-HIST-03-P', 80)) s(wo, d)
   where h.wo = s.wo;
  -- C2: 정비창 규칙의 첫 창 = 지금 + 9 h(야간, maintenance_profiles.night_window_at 과 같음) · + 105 h(주말)
  update ent.maintenance_window_rules set first_at = now() + make_interval(hours => case kind when 'N' then 9 else 105 end);
end $$;

create or replace function ent.reset_executions() returns void language plpgsql as $$
begin
  delete from ent.goods_receipts; delete from ent.cmms_calendar; delete from ent.case_records;
  delete from ent.transactions; delete from ent.work_orders; delete from ent.purchase_requests; delete from ent.shipments;
  delete from ent.lot_dispositions; delete from ent.ems_actions;
  delete from ent.maintenance_history where wo not like 'WO-HIST-%';
  update ent.production_orders set asset = moved_from, moved_from = null where moved_from is not null;
  perform ent.reset_spare_stock(null);
  perform ent.reanchor_scenario_times();
end $$;

revoke execute on function ent.reanchor_scenario_times(), ent.reset_executions(), ent.reset_spare_stock(text), ent.refresh_spare_flag(text)
  from public, anon, authenticated;
grant execute on function ent.reanchor_scenario_times(), ent.reset_executions(), ent.reset_spare_stock(text), ent.refresh_spare_flag(text) to service_role;
