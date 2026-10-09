-- C3 조립 (2026-10-09): 시나리오 B 작업지시의 정비 시간이 승인한 카드를 따라가도록, ent.pm_status 에 그다음 예정된 정비 시간(월간 창)의
-- id · 시작 시각을 덧붙인다. 칸은 뒤에만 더하므로 create or replace view 로 충분하다(기존 칸 · 순서 그대로). 두 번 적용해도 안전하다.
-- 메모리 백엔드는 it/enterprise-sim/entsim/data.py pm_row 가 같은 칸을 낸다.
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
       m.id as following_window_id, m.starts_at as following_window_at
  from ent.pm_counters c cross join ent.pm_settings st
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'N' order by x.starts_at limit 1) n on true
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'W' order by x.starts_at limit 1) w on true
  left join lateral (select * from ent.next_maintenance_windows(c.asset, 1) x where x.kind = 'M' order by x.starts_at limit 1) m on true
  left join lateral (select o.asset, o.since_pm_h from ent.pm_counters o
                      where o.asset <> c.asset and o.since_pm_h >= st.interval_h * (1 - st.tolerance_pct / 100)
                      order by o.since_pm_h desc, o.asset limit 1) p on true
  left join ent.spare_stock sp on sp.part_no = st.kit_part_no;
