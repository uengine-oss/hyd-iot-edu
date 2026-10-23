-- 2026-10-23 수업 전 점검: 초기화 두 가지가 정기 정비 오더의 부품 예약(ent.pm_part_reservations, 056)을 몰랐다.
--  1) B [초기화](ent.reset_pm_counters)는 계수기 · 이번 회차 오더 표시만 시작값으로 돌리고, 승인된 정기 정비 오더가 잡은 씰 키트 · 리턴 필터
--     예약(또는 즉시 출고)은 남겼다. 다시 연 B는 "정기 점검 도래"인데 부품 가용이 0이라 단독 · 즉시 시행이 재고 부족으로 빠져 추천이 없었다
--     (라이브 실측: B를 두 번 승인한 뒤 세 번째 B — 후보 4장 모두 제외).
--  2) 업무 전체 초기화(ent.reset_executions)는 작업지시를 지우는데 예약 행이 그 작업지시를 참조해 FK 위반으로 실패했다
--     (B를 한 번이라도 승인하면 POST /api/reset 이 500).
-- 고침: B [초기화]는 아직 부품을 잡은 정기 정비 오더를 취소로 닫고 예약을 푼 뒤(released_at), 잡았던 부품의 재고를 수업 시작값으로 돌린다.
-- 전체 초기화는 예약 행을 다른 실행 기록과 같이 ent.execution_archive 에 옮긴 뒤 지운다.

create or replace function ent.reset_pm_counters(p_asset text default null) returns jsonb language plpgsql as $$
declare r ent.pm_counters; v_parts text[]; v_part text;
begin
  with open_orders as (
    update ent.work_orders w set status = '취소', cancelled_at = now()
     where w.status = '배정됨' and (p_asset is null or w.asset = p_asset)
       and exists (select 1 from ent.pm_part_reservations x where x.work_order = w.id and x.released_at is null)
    returning w.id),
  released as (
    update ent.pm_part_reservations x set released_at = now()
     where x.released_at is null and x.work_order in (select id from open_orders)
    returning x.part_no)
  select coalesce(array_agg(distinct part_no order by part_no), '{}') into v_parts from released;
  foreach v_part in array v_parts loop
    perform ent.reset_spare_stock(v_part);
  end loop;
  for r in select * from ent.pm_counters where p_asset is null or asset = p_asset for update loop
    update ent.pm_counters set since_pm_h = base_since_pm_h, total_h = base_total_h, cycle = 1, last_done_at = null, due_since = null,
           plan_wo = null, plan_window = null, planned_at = null, updated_at = now() where asset = r.asset;
    perform ent.refresh_pm_flag(r.asset);
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (r.asset, 'BASE', r.base_since_pm_h - r.since_pm_h, r.base_since_pm_h, r.base_total_h, 1, 'RESET', 'instructor', '수업 초기화');
  end loop;
  return ent.pm_status_read(p_asset);
end $$;

create or replace function ent.reset_executions() returns void language plpgsql as $$
declare n bigint := nextval('ent.execution_reset_no');
begin
  insert into ent.execution_archive (reset_no, table_name, ref, decision_id, row)
    select n, 'goods_receipts', g.id, g.decision_id, to_jsonb(g) from ent.goods_receipts g
    union all select n, 'transactions', t.id, t.decision_id, to_jsonb(t) from ent.transactions t
    union all select n, 'work_orders', w.id, w.decision_id, to_jsonb(w) from ent.work_orders w
    union all select n, 'pm_part_reservations', p.work_order, null, to_jsonb(p) from ent.pm_part_reservations p
    union all select n, 'purchase_requests', r.id, r.decision_id, to_jsonb(r) from ent.purchase_requests r
    union all select n, 'shipments', s.id, s.decision_id, to_jsonb(s) from ent.shipments s
    union all select n, 'lot_dispositions', l.lot, l.decision_id, to_jsonb(l) from ent.lot_dispositions l
    union all select n, 'ems_actions', null, e.decision_id, to_jsonb(e) from ent.ems_actions e
    union all select n, 'maintenance_history', h.wo, null, to_jsonb(h) from ent.maintenance_history h where h.wo not like 'WO-HIST-%';
  delete from ent.goods_receipts;
  delete from ent.transactions; delete from ent.pm_part_reservations; delete from ent.work_orders; delete from ent.purchase_requests;
  delete from ent.shipments; delete from ent.lot_dispositions; delete from ent.ems_actions;
  delete from ent.maintenance_history where wo not like 'WO-HIST-%';
  update ent.production_orders set asset = moved_from, moved_from = null where moved_from is not null;
  perform ent.reset_spare_stock(null);
  perform ent.reset_pm_counters(null);
  perform ent.reanchor_scenario_times();
end $$;

grant delete on ent.pm_part_reservations to service_role;
revoke execute on function ent.reset_executions(), ent.reset_pm_counters(text) from public, anon, authenticated;
grant execute on function ent.reset_executions(), ent.reset_pm_counters(text) to service_role;
