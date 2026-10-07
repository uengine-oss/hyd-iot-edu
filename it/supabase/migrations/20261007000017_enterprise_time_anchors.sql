-- A086 (R05, 회의 L75~79 "기준 정보가 아니라 시간적으로 계속 바뀌는 실황 값"):
-- 업무 DB의 "지금부터 몇 시간/며칠" 열은 고정 숫자여서 시간이 흘러도 바뀌지 않았다(10-03에 넣은 납기 6 h가 10-07에도 6 h).
-- 다른 ent 테이블(작업지시·거래·구매요청)과 실제 MES/ERP/CMMS처럼 시각을 저장하고, 남은/경과 시간은 읽을 때 now()로 계산한다.
-- 현재 값은 "지금 + 남은 시간"으로 옮기고 옛 열은 지우지 않는다(사용 중단 표시). RPC의 facts 이름(due_in_h 등)과 의미(현재 기준 h)는 유지한다.
-- 세척 횟수와 마지막 세척은 CMMS 작업 이력(maintenance_history)에서 계산한다(프로필의 별도 숫자와 이력이 어긋났다: HYD-02 45일 대 이력 21일).

-- ---------------------------------------------------------------- 시각 열
alter table ent.production_orders add column if not exists due_at timestamptz;
alter table ent.production_orders add column if not exists alt_free_at timestamptz;
alter table ent.fg_inventory add column if not exists ship_at timestamptz;
alter table ent.maintenance_profiles add column if not exists night_window_at timestamptz;
alter table ent.maintenance_history add column if not exists performed_at timestamptz;

-- 옛 상대 열은 지우지 않는다(데이터 보존·되돌리기 가능). 값을 시각으로 옮긴 뒤 NOT NULL만 풀고 '갱신하지 않는 옛 값'으로 표시한다.
update ent.production_orders set due_at = now() + make_interval(secs => due_in_h * 3600) where due_at is null;
update ent.production_orders set alt_free_at = now() + make_interval(secs => alt_free_h * 3600) where alt_free_at is null and alt_free_h is not null;
update ent.fg_inventory set ship_at = now() + make_interval(secs => ship_in_h * 3600) where ship_at is null;
update ent.maintenance_profiles set night_window_at = now() + make_interval(secs => night_in_h * 3600) where night_window_at is null;
update ent.maintenance_history set performed_at = now() - make_interval(days => days_ago) where performed_at is null;
-- 프로필에만 있던 마지막 세척(이력에 없는 것)은 이력 행으로 옮겨 보존한다: HYD-03 80일
insert into ent.maintenance_history (asset, wo, task, days_ago, performed_at)
select m.asset, 'WO-HIST-' || right(m.asset, 2) || '-P', '쿨러 핀 세척', m.last_clean_days, now() - make_interval(days => m.last_clean_days)
  from ent.maintenance_profiles m
 where not exists (select 1 from ent.maintenance_history h where h.asset = m.asset and h.task like '쿨러 핀 세척%');

alter table ent.production_orders alter column due_in_h drop not null;
alter table ent.fg_inventory alter column ship_in_h drop not null;
alter table ent.maintenance_profiles alter column night_in_h drop not null, alter column last_clean_days drop not null, alter column cleans_60d drop not null;
alter table ent.maintenance_history alter column days_ago drop not null;
comment on column ent.production_orders.due_in_h is '사용 중단(A086): 2026-10-03 시점의 고정값이며 갱신하지 않는다. 납기는 due_at을 쓴다';
comment on column ent.production_orders.alt_free_h is '사용 중단(A086): 고정값, 갱신하지 않는다. alt_free_at을 쓴다';
comment on column ent.fg_inventory.ship_in_h is '사용 중단(A086): 고정값, 갱신하지 않는다. ship_at을 쓴다';
comment on column ent.maintenance_profiles.night_in_h is '사용 중단(A086): 고정값, 갱신하지 않는다. night_window_at을 쓴다';
comment on column ent.maintenance_profiles.last_clean_days is '사용 중단(A086): 고정값, 갱신하지 않는다. maintenance_history.performed_at에서 계산한다';
comment on column ent.maintenance_profiles.cleans_60d is '사용 중단(A086): 고정값, 갱신하지 않는다. maintenance_history.performed_at에서 계산한다';
comment on column ent.maintenance_history.days_ago is '사용 중단(A086): 고정값, 갱신하지 않는다. performed_at을 쓴다';

alter table ent.production_orders alter column due_at set not null;
alter table ent.fg_inventory alter column ship_at set not null;
alter table ent.maintenance_profiles alter column night_window_at set not null;
alter table ent.maintenance_history alter column performed_at set not null;

comment on column ent.production_orders.due_at is 'MES 생산오더 납기 일시. 납기까지 남은 시간(h) = extract(epoch from due_at - now())/3600';
comment on column ent.production_orders.alt_free_at is '대체 설비가 비는 일시. 가용까지 남은 시간(h) = extract(epoch from alt_free_at - now())/3600';
comment on column ent.fg_inventory.ship_at is '다음 출하 일시. 출하까지 남은 시간(h) = extract(epoch from ship_at - now())/3600';
comment on column ent.maintenance_profiles.night_window_at is '다음 야간 정비창 시작 일시';
comment on column ent.maintenance_history.performed_at is 'CMMS 과거 작업 수행 일시. 마지막 세척·최근 60일 세척 횟수는 이 이력에서 계산한다';

-- ---------------------------------------------------------------- 읽기 RPC: 같은 facts 이름, 지금 기준 값
create or replace function ent.hours_from_now(p_at timestamptz) returns numeric language sql stable as $$
  select case when p_at is null then null else round((extract(epoch from p_at - now()) / 3600)::numeric, 2) end
$$;

create or replace function ent.mes_orders(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'MES',
    'facts', (select to_jsonb(o) - 'item' - 'customer' - 'status' - 'moved_from' - 'updated_at' - 'asset' - 'due_at' - 'alt_free_at' - 'due_in_h' - 'alt_free_h'
                     || jsonb_build_object('due_in_h', ent.hours_from_now(o.due_at), 'alt_free_h', ent.hours_from_now(o.alt_free_at), 'due_at', o.due_at)
                from ent.production_orders o where o.asset = p_asset or o.moved_from = p_asset order by (o.asset = p_asset) desc limit 1),
    'records', coalesce((select jsonb_agg(to_jsonb(o) - 'due_in_h' - 'alt_free_h' || jsonb_build_object('due_in_h', ent.hours_from_now(o.due_at), 'alt_free_h', ent.hours_from_now(o.alt_free_at)))
                from ent.production_orders o where o.asset = p_asset or o.moved_from = p_asset), '[]'::jsonb),
    'as_of', now())
$$;

create or replace function ent.erp_inventory(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'ERP',
    'facts', (select jsonb_build_object('fg_item', i.fg_item, 'fg_stock', i.fg_stock, 'ship_in_h', ent.hours_from_now(i.ship_at), 'ship_at', i.ship_at)
                from ent.fg_inventory i where i.asset = p_asset),
    'records', coalesce((select jsonb_agg(to_jsonb(i) - 'ship_in_h' || jsonb_build_object('ship_in_h', ent.hours_from_now(i.ship_at))) from ent.fg_inventory i where i.asset = p_asset), '[]'::jsonb),
    'as_of', now())
$$;

create or replace function ent.cmms_history(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'CMMS',
    'facts', (select to_jsonb(m) - 'asset' - 'night_window_at' - 'night_in_h' - 'last_clean_days' - 'cleans_60d'
                     || jsonb_build_object('night_in_h', ent.hours_from_now(m.night_window_at),
                          'cleans_60d', (select count(*) from ent.maintenance_history h where h.asset = m.asset and h.task like '쿨러 핀 세척%' and h.performed_at > now() - interval '60 days'),
                          'last_clean_days', (select floor(extract(epoch from now() - max(h.performed_at)) / 86400)::int from ent.maintenance_history h where h.asset = m.asset and h.task like '쿨러 핀 세척%'))
                from ent.maintenance_profiles m where m.asset = p_asset),
    'records', coalesce((select jsonb_agg(jsonb_build_object('wo', h.wo, 'task', h.task, 'performed_at', h.performed_at,
                                                             'days_ago', floor(extract(epoch from now() - h.performed_at) / 86400)::int) order by h.performed_at desc)
                from ent.maintenance_history h where h.asset = p_asset), '[]'::jsonb),
    'work_orders', coalesce((select jsonb_agg(to_jsonb(w) order by w.created_at desc) from ent.work_orders w where w.asset = p_asset), '[]'::jsonb),
    'as_of', now())
$$;

-- ---------------------------------------------------------------- 교육용 시나리오 시각
-- 실습 시나리오의 기준(납기 6 h 등)은 "초기화한 지금"에서 출발한다. 초기화하지 않으면 시각은 그대로 흐른다(납기가 지나면 음수).
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
end $$;

create or replace function ent.reset_executions() returns void language plpgsql as $$
begin
  delete from ent.transactions; delete from ent.work_orders; delete from ent.purchase_requests; delete from ent.shipments;
  delete from ent.lot_dispositions; delete from ent.ems_actions;
  update ent.production_orders set asset = moved_from, moved_from = null where moved_from is not null;
  perform ent.reanchor_scenario_times();
end $$;

revoke execute on function ent.reanchor_scenario_times(), ent.reset_executions() from public, anon, authenticated;
grant execute on function ent.reanchor_scenario_times(), ent.reset_executions() to service_role;
grant execute on function ent.hours_from_now(timestamptz) to anon, authenticated, service_role, hyd_enterprise_reader;
grant execute on function ent.mes_orders(text), ent.erp_inventory(text), ent.cmms_history(text) to anon, authenticated, service_role, hyd_enterprise_reader;
