-- C2 (확정 TODO C, 2026-10-09) 승인 뒤 실행 부품의 업무 DB 쪽. 추가만 한다(기존 표 · 행은 바꾸지 않고, 함수는 같은 서명으로 본문을 넓힌다).
--   1. 예비품 재고(ent.spare_stock) · 재고 이동(ent.stock_movements) — ERP 재고 감시가 재주문점 이탈을 본다(시나리오 C 시작).
--   2. 부품별 공급사 견적(ent.part_quotes) — ent.suppliers 는 공급사 하나에 부품 하나(쿨러 코어)라 씰 키트 견적을 둘 곳이 없었다
--      (migration 37 머리말). 값은 온톨로지 SUPPLIED_BY(it/neo4j/v2/instances.cypher)와 같다: 씰 키트 sup:a 35/0.12/2 · sup:b 55/0.02/5 ·
--      sup:c 20/0.30/1(비AVL), 팬 베어링 sup:a 18/0.10/1 · sup:b 28/0.03/3. 쿨러 코어는 ent.suppliers 그대로 읽는다(같은 값을 두 곳에 두지 않음).
--   3. 예정된 정비 시간 규칙(ent.maintenance_window_rules) → 다가오는 예정된 정비 시간(ent.next_maintenance_windows) — 시나리오 B 의 정비 시점.
--   4. 발주(purchase_requests)에 부품 번호 · 수량 · 단가 · 금액 · 리드타임 · 입고 예정, 입고 표(ent.goods_receipts).
--   5. 작업지시(work_orders, 기존 skill:schedule-maintenance 그대로)에 예정된 정비 시간 id · 시작 시각 · 완료 시각.
--   6. ent.exec_skill: procure-part 가 수량 · 금액을 싣고 재고의 입고 예정을 올린다. 새 스킬 receive-goods(입고 · 검수) ·
--      complete-maintenance(정비 완료 · 부품 소모) · issue-spare(예비품 출고, 수업 원인 버튼) ·
--      pm-advance(운전시간 빨리 감기, 수업 원인 버튼) · pm-reset(시운전 통과 뒤 계수기 리셋) · delay-delivery(공급사 납기 지연, 수업 미달 버튼).
--   7. 시나리오 B 정기 정비: 정비 계획 · 운전시간 계수기(ent.pm_counters, 설정 ent.pm_settings) → 설비별 한 행 ent.pm_status(뷰, 판단 입력의
--      물리 출처로 묶을 수 있다). 감시기가 pm_due 를 보고 PM_DUE 처리 건을 연다.
-- 가용 재고 = 현재고 − 정비 예약 + 입고 예정 (PR-07 7.2, 온톨로지 in:spare-gap = 가용 − 재주문점).
-- 금액 만원, 시간은 실제 시각(timestamptz). 교육용 가상 값.

-- ---------------------------------------------------------------- 1. 예비품 재고 · 이동
create table if not exists ent.spare_stock (                 -- ERP: 중요 예비품 재고
  part_no text primary key references ent.parts(part_no),
  on_hand integer not null check (on_hand >= 0),             -- 창고 실물
  reserved integer not null default 0 check (reserved >= 0), -- 예정된 정비에 묶인 수량
  on_order integer not null default 0 check (on_order >= 0), -- 발주 후 입고 예정
  reorder_point integer not null check (reorder_point >= 0), -- 가용(on_hand - reserved + on_order)이 이보다 작으면 재고 기준 이탈
  target_stock integer not null check (target_stock >= 0),   -- 보충 목표 (필요량 = 목표 - 가용 - 입고 예정)
  reserved_for text,                                        -- 예약한 설비 (경보의 설비 키, ent.assets.code — 자산 행은 seed 가 넣으므로 FK 없음)
  base_on_hand integer not null,                            -- 수업 초기화 값
  base_reserved integer not null default 0,
  below_since timestamptz,                                  -- 재주문점 아래로 내려간 시각 (경보 회차 키, 회복하면 null)
  need_by_days numeric,                                     -- 필요일: 결품 전 남은 날 — 리드타임과 비교(PR-07 7.4)
  updated_at timestamptz not null default now()
);
comment on table ent.spare_stock is 'C2: ERP 중요 예비품 재고. 가용 = on_hand - reserved + on_order, 가용 < reorder_point 면 재고 기준 이탈(SPARE_BELOW_MIN)';

create table if not exists ent.stock_movements (             -- ERP: 재고 이동 원장 (출고 · 소모 · 입고 · 초기화)
  id bigserial primary key,
  part_no text not null references ent.parts(part_no),
  kind text not null check (kind in ('ISSUE', 'CONSUME', 'ORDER', 'RECEIPT', 'RESET')),
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
alter table ent.spare_stock add column if not exists need_by_days numeric;
insert into ent.spare_stock (part_no, on_hand, reserved, on_order, reorder_point, target_stock, reserved_for, base_on_hand, base_reserved) values
  ('P-PMP-SEAL', 5, 2, 0, 2, 7, 'HYD-03', 5, 2),   -- HYD-03 예방 교체에 2개 예약 · 가용 3. 수업 '자재 출고 −2' → 가용 1 < 2, 필요량 6 (B-OEM 330만원)
  ('P-FAN-BRG', 3, 0, 0, 1, 3, 'HYD-03', 3, 0),
  ('P-CLR-CORE', 2, 0, 0, 1, 2, 'HYD-01', 2, 0)
on conflict (part_no) do nothing;
update ent.spare_stock s set need_by_days = v.d from (values ('P-PMP-SEAL', 6), ('P-FAN-BRG', 7), ('P-CLR-CORE', 10)) v(p, d)
 where s.part_no = v.p and s.need_by_days is null;

create or replace function ent.refresh_spare_flag(p_part text) returns void language sql as $$
  update ent.spare_stock set below_since = case when on_hand - reserved + on_order < reorder_point then coalesce(below_since, now()) else null end,
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
  kind text not null check (kind in ('N', 'W', 'M')),       -- N 야간 정비 시간 · W 주말 계획 정지 · M 월간 계획 정지
  label text not null,
  first_at timestamptz not null,
  period_h numeric not null check (period_h > 0),
  duration_h numeric not null check (duration_h > 0),
  primary key (asset, kind)
);
-- 같은 이름의 표가 옛 판(N · W 만)으로 이미 있을 수 있다 — 칸 · 검사를 넓힌다
alter table ent.maintenance_window_rules add column if not exists crew_size integer not null default 2;  -- 그 시간의 정비 인원(명). 두 대 묶음은 4명 필요(PM-02)
alter table ent.maintenance_window_rules drop constraint if exists maintenance_window_rules_kind_check;
alter table ent.maintenance_window_rules add constraint maintenance_window_rules_kind_check check (kind in ('N', 'W', 'M'));
insert into ent.maintenance_window_rules (asset, kind, label, first_at, period_h, duration_h, crew_size)
select a.code, k.kind, k.label, now() + make_interval(hours => k.first_h), k.period_h, k.duration_h, k.crew
  from (values ('HYD-01'), ('HYD-02'), ('HYD-03')) a(code)
 cross join (values ('N', '야간 정비 시간', 9, 24, 4, 2), ('W', '주말 계획 정지', 105, 168, 24, 4), ('M', '월간 계획 정지', 280, 720, 48, 6))
       k(kind, label, first_h, period_h, duration_h, crew)
on conflict (asset, kind) do update set label = excluded.label, crew_size = excluded.crew_size;

-- 다가오는(또는 진행 중인) 정비창 p_n 개씩. id 는 설비 · 종류 · 시작 시각으로 정해져 같은 창은 같은 id 다.
-- 돌려주는 칸이 옛 판보다 늘었으므로(crew_size) 먼저 지운다(그것에 기대는 뷰 ent.pm_status 는 아래에서 다시 만든다).
drop function if exists ent.next_maintenance_windows(text, integer) cascade;
create or replace function ent.next_maintenance_windows(p_asset text, p_n integer default 3)
returns table (id text, asset text, kind text, label text, starts_at timestamptz, ends_at timestamptz, crew_size integer)
language sql stable as $$
  select 'MW-' || r.asset || '-' || r.kind || '-' || to_char(st at time zone 'UTC', 'YYYYMMDDHH24MI'), r.asset, r.kind, r.label, st,
         st + make_interval(secs => r.duration_h * 3600), r.crew_size
    from ent.maintenance_window_rules r
    cross join lateral (select greatest(0, ceil(extract(epoch from (now() - r.first_at)) / 3600 / r.period_h - r.duration_h / r.period_h))::int k0) b
    cross join lateral generate_series(b.k0, b.k0 + greatest(p_n, 1) - 1) g(k)
    cross join lateral (select r.first_at + make_interval(secs => g.k * r.period_h * 3600) st) s
   where r.asset = p_asset
   order by st
$$;

-- ---------------------------------------------------------------- 3b. 시나리오 B 정기 정비 계획 · 운전시간 계수기 (CMMS)
create table if not exists ent.pm_settings (                  -- 회사 설정(교육용): 주기 · 허용 오차 · 사전 알림 · 정비 패키지 · 소모 부품
  id integer primary key default 1 check (id = 1),
  interval_h numeric not null default 2000 check (interval_h > 0),
  tolerance_pct numeric not null default 10 check (tolerance_pct >= 0 and tolerance_pct < 100),
  notice_h numeric not null default 50 check (notice_h >= 0),
  package text not null default '2,000 h 정기 점검 (축 씰 · 리턴 필터 교체, 잔압 해제, 시운전)',
  kit_part_no text references ent.parts(part_no),
  kit_qty integer not null default 1 check (kit_qty >= 0)
);
insert into ent.pm_settings (id, kit_part_no) values (1, 'P-PMP-SEAL') on conflict (id) do nothing;

create table if not exists ent.pm_counters (                  -- 설비별 운전시간 계수기 (마지막 정기 정비 뒤 운전시간 · 누적)
  asset text primary key,                                   -- ent.assets.code (자산 행은 seed 가 넣으므로 FK 없음)
  since_pm_h numeric not null check (since_pm_h >= 0),
  total_h numeric not null check (total_h >= 0),
  cycle integer not null default 1,                         -- 정기 정비 회차 (리셋마다 +1, 감시 경보 회차 키)
  last_done_at timestamptz,
  due_since timestamptz,                                    -- PM_DUE 가 된 시각 (리셋하면 null)
  base_since_pm_h numeric not null, base_total_h numeric not null,   -- 수업 초기화 값
  updated_at timestamptz not null default now()
);
insert into ent.pm_counters (asset, since_pm_h, total_h, base_since_pm_h, base_total_h) values
  ('HYD-01', 1200, 9200, 1200, 9200), ('HYD-02', 1650, 11650, 1650, 11650), ('HYD-03', 1580, 7580, 1580, 7580)
on conflict (asset) do nothing;   -- 수업 '운전시간 빨리 감기 +300 h' → HYD-02 1,950 h(PM_DUE) · HYD-03 1,880 h(허용 오차 안, 묶음 후보)

create table if not exists ent.pm_counter_log (               -- 계수기 원장 (ADVANCE 빨리 감기 · RESET 정비 완료 · BASE 수업 초기화)
  id bigserial primary key,
  asset text not null,
  kind text not null check (kind in ('ADVANCE', 'RESET', 'BASE')),
  delta_h numeric not null,
  since_after numeric not null,
  total_after numeric not null,
  cycle integer not null,
  ref text, by_whom text, reason text,
  at timestamptz not null default now()
);

create or replace function ent.refresh_pm_flag(p_asset text) returns void language sql as $$
  update ent.pm_counters c set due_since = case when c.since_pm_h >= s.interval_h - s.notice_h then coalesce(c.due_since, now()) else null end,
         updated_at = now()
    from ent.pm_settings s where c.asset = p_asset
$$;

-- ---------------------------------------------------------------- 4 · 5. 발주 · 입고 · 작업지시 · 일정 · 기록
alter table ent.purchase_requests add column if not exists part_no text references ent.parts(part_no);
alter table ent.purchase_requests add column if not exists qty integer check (qty is null or qty > 0);
alter table ent.purchase_requests add column if not exists unit_price numeric;
alter table ent.purchase_requests add column if not exists amount numeric;
alter table ent.purchase_requests add column if not exists lead_d integer;
alter table ent.purchase_requests add column if not exists expected_at timestamptz;
alter table ent.purchase_requests add column if not exists received_at timestamptz;
alter table ent.purchase_requests add column if not exists delay_d numeric not null default 0;   -- 공급사가 알린 납기 지연(일, 수업 버튼)
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
alter table ent.goods_receipts add column if not exists created_at timestamptz not null default now();   -- enterprise-sim 화면(snapshot)의 정렬 칸

alter table ent.work_orders add column if not exists window_id text;
alter table ent.work_orders add column if not exists window_starts_at timestamptz;
alter table ent.work_orders add column if not exists completed_at timestamptz;

-- 읽기 권한: enterprise-mcp 전용 읽기 계정
do $$
declare t text;
begin
  foreach t in array array['spare_stock', 'stock_movements', 'part_quotes', 'maintenance_window_rules', 'goods_receipts',
                           'pm_settings', 'pm_counters', 'pm_counter_log'] loop
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
create or replace function ent.spare_row(s ent.spare_stock) returns jsonb language sql stable as $$
  select jsonb_build_object('part_no', s.part_no, 'name', (select name from ent.parts where part_no = s.part_no), 'on_hand', s.on_hand,
                            'reserved', s.reserved, 'on_order', s.on_order, 'available', s.on_hand - s.reserved + s.on_order,
                            'spare_gap', s.on_hand - s.reserved + s.on_order - s.reorder_point,
                            'reorder_point', s.reorder_point, 'target_stock', s.target_stock,
                            'need_qty', greatest(s.target_stock - (s.on_hand - s.reserved + s.on_order), 0),
                            'below_reorder_point', s.on_hand - s.reserved + s.on_order < s.reorder_point, 'below_since', s.below_since,
                            'reserved_for', s.reserved_for, 'need_by_days', s.need_by_days, 'updated_at', s.updated_at)
$$;

create or replace function ent.spare_stock_read(p_part text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'ERP',
    'facts', (select ent.spare_row(s) from ent.spare_stock s where s.part_no = p_part or p_part is null order by s.part_no limit 1),
    'records', coalesce((select jsonb_agg(ent.spare_row(s) order by s.part_no) from ent.spare_stock s where s.part_no = p_part or p_part is null), '[]'::jsonb),
    'movements', coalesce((select jsonb_agg(to_jsonb(m) order by m.id desc) from (select * from ent.stock_movements m
                 where m.part_no = p_part or p_part is null order by m.id desc limit 20) m), '[]'::jsonb),
    'as_of', now())
$$;

-- 시나리오 B: 설비별 정기 정비 상태 한 행 (판단 입력의 물리 출처 — ent.pm_status.<칸> 을 asset 으로 한 행 읽는다).
-- 운전시간은 실제 시간과 같이 흐른다고 보고(24 h 운전) 정비 시간까지의 시간을 허용 한계까지 남은 시간과 비교한다. entsim/data.py pm_row 와 같은 계산.
create or replace view ent.pm_status as
select c.asset, 'PM-' || c.asset || '-2000' as plan_id, st.package, c.cycle,
       c.since_pm_h as pm_since_h, c.total_h as pm_total_h, st.interval_h as pm_interval_h, st.tolerance_pct as pm_tolerance_pct,
       st.notice_h as pm_notice_h, st.interval_h - c.since_pm_h as pm_due_in_h,
       round(st.interval_h * (1 + st.tolerance_pct / 100) - c.since_pm_h, 2) as pm_limit_in_h,
       c.since_pm_h >= st.interval_h * (1 - st.tolerance_pct / 100) as pm_window_open,
       c.since_pm_h >= st.interval_h - st.notice_h as pm_due,
       c.since_pm_h > st.interval_h * (1 + st.tolerance_pct / 100) as pm_over_limit,
       n.id as night_window_id, n.starts_at as night_window_at, ent.hours_from_now(n.starts_at) as night_window_in_h,
       ent.hours_from_now(w.starts_at) as weekend_window_in_h, ent.hours_from_now(m.starts_at) as monthly_window_in_h,
       st.interval_h * (1 + st.tolerance_pct / 100) - c.since_pm_h >= ent.hours_from_now(n.starts_at) as night_within_limit,
       st.interval_h * (1 + st.tolerance_pct / 100) - c.since_pm_h >= ent.hours_from_now(w.starts_at) as weekend_within_limit,
       st.interval_h * (1 + st.tolerance_pct / 100) - c.since_pm_h >= ent.hours_from_now(m.starts_at) as monthly_within_limit,
       p.asset as bundle_peer, p.since_pm_h as bundle_peer_since_h,
       round(st.interval_h * (1 + st.tolerance_pct / 100) - p.since_pm_h, 2) as bundle_peer_limit_in_h,
       n.crew_size as night_crew_size, n.crew_size >= 4 as bundle_crew_ok,
       -- 온톨로지 B 판단 입력(scenario_structure)의 변수 이름 그대로
       c.since_pm_h as hours_since_pm, round(c.since_pm_h + ent.hours_from_now(n.starts_at), 2) as hours_at_next_window,
       round(c.since_pm_h + ent.hours_from_now(m.starts_at), 2) as hours_at_following_window, n.crew_size as pm_crew_available,
       sp.on_hand - sp.reserved + sp.on_order as spare_available,
       st.kit_part_no, st.kit_qty,
       sp.on_hand - sp.reserved + sp.on_order - st.kit_qty - sp.reorder_point as spare_gap_after_pm,
       sp.on_hand - sp.reserved + sp.on_order - 2 * st.kit_qty - sp.reorder_point as spare_gap_after_bundle,
       c.last_done_at, c.due_since, c.updated_at
  from ent.pm_counters c cross join ent.pm_settings st
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'N' order by x.starts_at limit 1) n on true
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'W' order by x.starts_at limit 1) w on true
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'M' order by x.starts_at limit 1) m on true
  left join lateral (select o.asset, o.since_pm_h from ent.pm_counters o
                      where o.asset <> c.asset and o.since_pm_h >= st.interval_h * (1 - st.tolerance_pct / 100)
                      order by o.since_pm_h desc, o.asset limit 1) p on true
  left join ent.spare_stock sp on sp.part_no = st.kit_part_no;
comment on view ent.pm_status is 'C2 시나리오 B: 설비별 정기 정비 상태(운전시간 · 주기 · 허용 오차 · 예정된 정비 시간까지 · 묶음 후보 · 부품 영향). 판단 입력의 물리 출처';
grant select on ent.pm_status to anon, authenticated, hyd_enterprise_reader;

create or replace function ent.pm_status_read(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'CMMS',
    'facts', (select to_jsonb(v) from ent.pm_status v where v.asset = p_asset or p_asset is null order by v.asset limit 1),
    'records', coalesce((select jsonb_agg(to_jsonb(v) order by v.asset) from ent.pm_status v where v.asset = p_asset or p_asset is null), '[]'::jsonb),
    'log', coalesce((select jsonb_agg(to_jsonb(l) order by l.id desc) from (select * from ent.pm_counter_log l
                     where l.asset = p_asset or p_asset is null order by l.id desc limit 20) l), '[]'::jsonb),
    'settings', (select to_jsonb(s) - 'id' from ent.pm_settings s),
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
                                        'next_window_in_h', ent.hours_from_now(w.starts_at), 'next_window_crew_size', w.crew_size)
                from ent.next_maintenance_windows(p_asset, 1) w order by w.starts_at limit 1) end,
    'records', coalesce((select jsonb_agg(jsonb_build_object('id', w.id, 'kind', w.kind, 'label', w.label, 'starts_at', w.starts_at,
                                          'ends_at', w.ends_at, 'starts_in_h', ent.hours_from_now(w.starts_at), 'crew_size', w.crew_size) order by w.starts_at)
                         from ent.next_maintenance_windows(p_asset, 3) w), '[]'::jsonb),
    'as_of', now())
$$;

create or replace function ent.purchase_order_read(p_ref text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'ERP',
    'facts', (select to_jsonb(r) || jsonb_build_object('expected_in_h', ent.hours_from_now(r.expected_at)) from ent.purchase_requests r where r.id = p_ref),  -- delay_d 포함
    'records', coalesce((select jsonb_agg(to_jsonb(g)) from ent.goods_receipts g where g.pr_id = p_ref), '[]'::jsonb))
$$;

grant execute on function ent.spare_stock_read(text), ent.part_quotes_read(text), ent.maintenance_windows_read(text), ent.purchase_order_read(text),
                          ent.next_maintenance_windows(text, integer), ent.quote_rows(text), ent.spare_row(ent.spare_stock), ent.pm_status_read(text)
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
  v_pm ent.pm_counters; v_pmset ent.pm_settings; v_hours numeric; v_days numeric; v_done numeric;
begin
  v_system := case v_skill
    when 'skill:schedule-maintenance' then 'sys:cmms' when 'skill:reallocate-production' then 'sys:mes'
    when 'skill:procure-part' then 'sys:erp' when 'skill:hold-lot' then 'sys:qms' when 'skill:release-lot' then 'sys:qms'
    when 'skill:substitute-shipment' then 'sys:erp' when 'skill:demand-control' then 'sys:ems'
    when 'skill:receive-goods' then 'sys:erp' when 'skill:complete-maintenance' then 'sys:cmms'
    when 'skill:issue-spare' then 'sys:erp'
    when 'skill:pm-advance' then 'sys:cmms' when 'skill:pm-reset' then 'sys:cmms' when 'skill:delay-delivery' then 'sys:scm' end;
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
            coalesce(v_window_label, case when (p->>'option') like '%derate%' then '예정된 정비 시간 (야간)' else '즉시' end), v_decision, p->>'option', p->>'by',
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
      update ent.spare_stock set on_order = on_order + v_qty, updated_at = now() where part_no = v_part_no returning * into v_stock;
      if v_stock.part_no is not null then
        perform ent.refresh_spare_flag(v_part_no);
        insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
        values (v_part_no, 'ORDER', v_qty, v_asset, v_ref, p->>'by', format('발주 %s 입고 예정', v_ref), v_stock.on_hand,
                v_stock.on_hand - v_stock.reserved + v_stock.on_order);
      end if;
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
      values (v_pr.part_no, 'RECEIPT', v_pr.qty, v_asset, v_ref, p->>'by', format('발주 %s 입고', v_pr.id), v_stock.on_hand,
              v_stock.on_hand - v_stock.reserved + v_stock.on_order);
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
                v_stock.on_hand, v_stock.on_hand - v_stock.reserved + v_stock.on_order);
      end if;
    end if;
    v_ref := v_wo.id;
    v_detail := format('%s 작업지시 %s 완료 (%s)%s', v_wo.asset, v_wo.id, v_wo.task,
                       case when v_std.part_no is not null then format(' — %s %s개 소모', v_std.part_no, v_std.part_qty) else '' end);
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_wo.id;

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
    values (v_part_no, 'ISSUE', v_qty, v_asset, v_ref, p->>'by', coalesce(v_params->>'reason', '예비품 출고'), v_stock.on_hand,
            v_stock.on_hand - v_stock.reserved + v_stock.on_order);
    v_detail := format('%s %s개 출고 (%s) — 가용 %s / 재주문점 %s', v_part_no, v_qty, coalesce(v_params->>'reason', '예비품 출고'),
                       v_stock.on_hand - v_stock.reserved + v_stock.on_order, v_stock.reorder_point);
    select to_jsonb(s) into v_after from ent.spare_stock s where s.part_no = v_part_no;

  elsif v_skill = 'skill:pm-advance' then                 -- C2 시나리오 B: 운전시간 빨리 감기 (수업 원인 버튼, 설비 한 대)
    v_hours := coalesce((v_params->>'hours')::numeric, 300);
    if v_hours <= 0 or v_hours > 5000 then raise exception 'INVALID: hours must be between 0 and 5000' using errcode = '22023'; end if;
    select * into v_pm from ent.pm_counters where asset = v_asset for update;
    if not found then raise exception 'INVALID: % has no maintenance plan', v_asset using errcode = '22023'; end if;
    v_before := to_jsonb(v_pm);
    update ent.pm_counters set since_pm_h = since_pm_h + v_hours, total_h = total_h + v_hours where asset = v_asset;
    perform ent.refresh_pm_flag(v_asset);
    select * into v_pm from ent.pm_counters where asset = v_asset;
    v_ref := 'RUN-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (v_asset, 'ADVANCE', v_hours, v_pm.since_pm_h, v_pm.total_h, v_pm.cycle, v_ref, p->>'by', coalesce(v_params->>'reason', '운전시간 빨리 감기 (수업 원인)'));
    select * into v_pmset from ent.pm_settings where id = 1;
    v_detail := format('%s 운전시간 +%s h — 마지막 정기 정비 뒤 %s h / 주기 %s h', v_asset, v_hours, v_pm.since_pm_h, v_pmset.interval_h);
    v_after := to_jsonb(v_pm);

  elsif v_skill = 'skill:pm-reset' then                   -- C2 시나리오 B: 시운전 통과 뒤 계수기 리셋 · 다음 기한 기록
    select * into v_pm from ent.pm_counters where asset = v_asset for update;
    if not found then raise exception 'INVALID: % has no maintenance plan', v_asset using errcode = '22023'; end if;
    v_before := to_jsonb(v_pm); v_done := v_pm.since_pm_h;
    update ent.pm_counters set since_pm_h = 0, cycle = cycle + 1, last_done_at = now() where asset = v_asset;
    perform ent.refresh_pm_flag(v_asset);
    select * into v_pm from ent.pm_counters where asset = v_asset;
    select * into v_pmset from ent.pm_settings where id = 1;
    v_ref := 'PMR-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (v_asset, 'RESET', -v_done, 0, v_pm.total_h, v_pm.cycle, v_ref, p->>'by',
            coalesce(v_params->>'reason', format('정기 정비 완료 (%s)', coalesce(v_params->>'ref', '-'))));
    v_detail := format('%s 운전시간 계수기 리셋 (%s h 에 정기 정비) — 다음 기한 %s h (허용 %s~%s h)', v_asset, v_done, v_pmset.interval_h,
                       trim_scale(round(v_pmset.interval_h * (1 - v_pmset.tolerance_pct / 100), 1)), trim_scale(round(v_pmset.interval_h * (1 + v_pmset.tolerance_pct / 100), 1)));
    v_after := to_jsonb(v_pm);

  elsif v_skill = 'skill:delay-delivery' then             -- C2 시나리오 C 미달 가지: 공급사 납기 지연 통보 (수업 버튼)
    v_days := coalesce((v_params->>'days')::numeric, 3);
    if v_days <= 0 or v_days > 60 then raise exception 'INVALID: days must be between 0 and 60' using errcode = '22023'; end if;
    select * into v_pr from ent.purchase_requests r
     where r.status = '승인됨 → 발주' and r.qty is not null
       and (not v_params ? 'ref' or r.id = v_params->>'ref') and (not v_params ? 'part_no' or r.part_no = v_params->>'part_no')
     order by r.created_at desc limit 1 for update;
    if not found then raise exception 'INVALID: no open purchase order to delay' using errcode = '22023'; end if;
    v_before := to_jsonb(v_pr);
    update ent.purchase_requests set delay_d = delay_d + v_days, expected_at = expected_at + make_interval(secs => v_days * 86400)
     where id = v_pr.id returning * into v_pr;
    v_ref := v_pr.id;
    v_detail := format('발주 %s 납기 %s일 지연 통보 — 리드타임 %s+%s일', v_pr.id, v_days, v_pr.lead_d, v_pr.delay_d);
    v_after := to_jsonb(v_pr);

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

-- 수업 초기화: 운전시간 계수기를 시작값으로 (빨리 감기 버튼 되돌리기). 원장에 BASE 를 남긴다.
create or replace function ent.reset_pm_counters(p_asset text default null) returns jsonb language plpgsql as $$
declare r ent.pm_counters;
begin
  for r in select * from ent.pm_counters where p_asset is null or asset = p_asset for update loop
    update ent.pm_counters set since_pm_h = base_since_pm_h, total_h = base_total_h, cycle = 1, last_done_at = null, due_since = null,
           updated_at = now() where asset = r.asset;
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (r.asset, 'BASE', r.base_since_pm_h - r.since_pm_h, r.base_since_pm_h, r.base_total_h, 1, 'RESET', 'instructor', '수업 초기화');
  end loop;
  return ent.pm_status_read(p_asset);
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
  update ent.maintenance_window_rules set first_at = now() + make_interval(hours => case kind when 'N' then 9 when 'W' then 105 else 280 end);
end $$;

create or replace function ent.reset_executions() returns void language plpgsql as $$
begin
  delete from ent.goods_receipts;
  delete from ent.transactions; delete from ent.work_orders; delete from ent.purchase_requests; delete from ent.shipments;
  delete from ent.lot_dispositions; delete from ent.ems_actions;
  delete from ent.maintenance_history where wo not like 'WO-HIST-%';
  update ent.production_orders set asset = moved_from, moved_from = null where moved_from is not null;
  perform ent.reset_spare_stock(null);
  perform ent.reset_pm_counters(null);
  perform ent.reanchor_scenario_times();
end $$;

revoke execute on function ent.reanchor_scenario_times(), ent.reset_executions(), ent.reset_spare_stock(text), ent.refresh_spare_flag(text),
                           ent.reset_pm_counters(text), ent.refresh_pm_flag(text)
  from public, anon, authenticated;
grant execute on function ent.reanchor_scenario_times(), ent.reset_executions(), ent.reset_spare_stock(text), ent.refresh_spare_flag(text),
                          ent.reset_pm_counters(text), ent.refresh_pm_flag(text) to service_role;
