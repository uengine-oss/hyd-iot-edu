-- C3 B · C 단순화 (2026-10-09, 확정 지시 '설비까지 안 가기로 함, 처리되면 끝'):
--   * 수업 시작 상태가 곧 기본값이다 — HYD-02 '정기 점검 도래'(운전시간 1,950 h), HYD-03 '재고 보충 필요'(씰 키트 가용 1 < 재주문점 2).
--     예전 시작값(HYD-02 1,650 h · 씰 키트 실물 5)과 '+300 h' · '출고 −2' 버튼이 만들던 상태를 기준값으로 옮긴다(판단 사실은 같다:
--     1,950 / 1,959 / 2,230 h, 필요량 6 · B-OEM 330만원).
--   * 정기 정비 처리 건은 정비 오더 등록과 공지로 끝난다. 이번 회차에 오더가 등록되면 pm_counters.plan_wo 에 남기고(작업지시 표 트리거),
--     ent.pm_status.pm_alert(도래 · 오더 없음)가 꺼진다. 수업 초기화(reset_pm_counters)가 plan_wo 를 지운다.
--   * 재고 초기화는 기준값이 재주문점 아래면 이탈 시각(below_since)을 바로 기록한다.
-- 추가 · 바꾸기만 하고 두 번 적용해도 안전하다. 메모리 백엔드(it/enterprise-sim/entsim/data.py · state.py)가 같은 값 · 같은 칸을 낸다.

alter table ent.pm_counters add column if not exists plan_wo text;
alter table ent.pm_counters add column if not exists plan_window text;
alter table ent.pm_counters add column if not exists planned_at timestamptz;

-- 기준값: 손대지 않은 행(현재값 = 옛 기준값)은 새 기준값으로 옮긴다. 수업 중에 바뀐 행은 기준값만 바꾸고 다음 초기화 때 따라간다.
update ent.spare_stock set on_hand = 3, updated_at = now() where part_no = 'P-PMP-SEAL' and on_hand = 5 and base_on_hand = 5 and reserved = 2 and on_order = 0;
update ent.spare_stock set base_on_hand = 3 where part_no = 'P-PMP-SEAL';
update ent.pm_counters c set since_pm_h = v.s, total_h = v.t, updated_at = now()
  from (values ('HYD-01', 1200, 9200, 1500, 9500), ('HYD-02', 1650, 11650, 1950, 11950), ('HYD-03', 1580, 7580, 1880, 7880)) v(a, os, ot, s, t)
 where c.asset = v.a and c.since_pm_h = v.os and c.base_since_pm_h = v.os and c.cycle = 1;
update ent.pm_counters c set base_since_pm_h = v.s, base_total_h = v.t
  from (values ('HYD-01', 1500, 9500), ('HYD-02', 1950, 11950), ('HYD-03', 1880, 7880)) v(a, s, t) where c.asset = v.a;

-- 정기 정비 오더 표시: 정기 정비 도래 설비에 작업지시가 등록되면 이번 회차의 오더로 남긴다(한 회차에 하나 — 먼저 등록된 것).
create or replace function ent.mark_pm_plan() returns trigger language plpgsql as $$
begin
  update ent.pm_counters c set plan_wo = new.id, plan_window = new.window_label, planned_at = now(), updated_at = now()
    from ent.pm_settings s
   where c.asset = new.asset and c.plan_wo is null and c.since_pm_h >= s.interval_h - s.notice_h;
  return new;
end $$;
drop trigger if exists work_orders_mark_pm_plan on ent.work_orders;
create trigger work_orders_mark_pm_plan after insert on ent.work_orders for each row execute function ent.mark_pm_plan();

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
       c.last_done_at, c.due_since, c.updated_at,
       -- C3: 카드가 고른 시점(이번 · 그다음 예정된 정비 시간)을 작업지시에 싣기 위한 그다음 창 id · 시작 시각 (뒤에만 덧붙임)
       m.id as following_window_id, m.starts_at as following_window_at,
       -- C3 B·C 단순화: 이번 회차 정기 정비 오더(등록되면 '정기 점검 도래' 표시가 꺼진다) · 화면 표시 여부 (뒤에만 덧붙임)
       c.plan_wo as pm_planned_wo, c.plan_window as pm_planned_window, c.planned_at as pm_planned_at,
       (c.since_pm_h >= st.interval_h - st.notice_h and c.plan_wo is null) as pm_alert
  from ent.pm_counters c cross join ent.pm_settings st
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'N' order by x.starts_at limit 1) n on true
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'W' order by x.starts_at limit 1) w on true
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'M' order by x.starts_at limit 1) m on true
  left join lateral (select o.asset, o.since_pm_h from ent.pm_counters o
                      where o.asset <> c.asset and o.since_pm_h >= st.interval_h * (1 - st.tolerance_pct / 100)
                      order by o.since_pm_h desc, o.asset limit 1) p on true
  left join ent.spare_stock sp on sp.part_no = st.kit_part_no;
comment on view ent.pm_status is 'C2 시나리오 B: 설비별 정기 정비 상태(운전시간 · 주기 · 허용 오차 · 예정된 정비 시간까지 · 묶음 후보 · 부품 영향). C3: pm_alert = 도래 · 이번 회차 오더 없음';
grant select on ent.pm_status to anon, authenticated, hyd_enterprise_reader;

-- 수업 초기화: 재고 — 기준값이 재주문점 아래면 이탈 시각을 바로 남긴다(화면 '재고 보충 필요')
create or replace function ent.reset_spare_stock(p_part text default null) returns jsonb language plpgsql as $$
declare r ent.spare_stock;
begin
  for r in select * from ent.spare_stock where p_part is null or part_no = p_part for update loop
    update ent.spare_stock set on_hand = base_on_hand, reserved = base_reserved, on_order = 0, below_since = null, updated_at = now()
     where part_no = r.part_no;
    perform ent.refresh_spare_flag(r.part_no);
    insert into ent.stock_movements (part_no, kind, qty, ref, by_whom, reason, on_hand_after, available_after)
    values (r.part_no, 'RESET', r.base_on_hand - r.on_hand, 'RESET', 'instructor', '수업 초기화', r.base_on_hand, r.base_on_hand - r.base_reserved);
  end loop;
  return ent.spare_stock_read(p_part);
end $$;

-- 수업 초기화: 운전시간 계수기 — 시작값으로, 이번 회차 오더 표시를 지우고, 시작값이 도래면 도래 시각을 바로 남긴다(화면 '정기 점검 도래')
create or replace function ent.reset_pm_counters(p_asset text default null) returns jsonb language plpgsql as $$
declare r ent.pm_counters;
begin
  for r in select * from ent.pm_counters where p_asset is null or asset = p_asset for update loop
    update ent.pm_counters set since_pm_h = base_since_pm_h, total_h = base_total_h, cycle = 1, last_done_at = null, due_since = null,
           plan_wo = null, plan_window = null, planned_at = null, updated_at = now() where asset = r.asset;
    perform ent.refresh_pm_flag(r.asset);
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (r.asset, 'BASE', r.base_since_pm_h - r.since_pm_h, r.base_since_pm_h, r.base_total_h, 1, 'RESET', 'instructor', '수업 초기화');
  end loop;
  return ent.pm_status_read(p_asset);
end $$;

-- 정기 정비 완료(시운전 통과 리셋)도 회차가 바뀌므로 오더 표시를 지운다
create or replace function ent.clear_pm_plan_on_cycle() returns trigger language plpgsql as $$
begin
  if new.cycle <> old.cycle then
    new.plan_wo := null; new.plan_window := null; new.planned_at := null;
  end if;
  return new;
end $$;
drop trigger if exists pm_counters_clear_plan on ent.pm_counters;
create trigger pm_counters_clear_plan before update on ent.pm_counters for each row execute function ent.clear_pm_plan_on_cycle();

revoke execute on function ent.reset_spare_stock(text), ent.reset_pm_counters(text), ent.mark_pm_plan(), ent.clear_pm_plan_on_cycle()
  from public, anon, authenticated;
grant execute on function ent.reset_spare_stock(text), ent.reset_pm_counters(text) to service_role;

-- 지금 상태의 표시 시각을 맞춘다(새 기준값으로 옮긴 행)
do $$ begin
  perform ent.refresh_spare_flag('P-PMP-SEAL');
  perform ent.refresh_pm_flag(a) from (values ('HYD-01'), ('HYD-02'), ('HYD-03')) v(a);
end $$;
