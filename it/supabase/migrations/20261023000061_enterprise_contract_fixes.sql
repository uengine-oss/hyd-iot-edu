-- 2026-10-23 업무 DB 점검(.evidence/audit2/enterprise.md) E8 · E10 · E11. 메모리 백엔드(it/enterprise-sim/entsim/state.py)와 같은 규칙.
--  E8  enterprise-sim 이 뜰 때마다 시나리오 시각 기준점을 지금으로 옮겨(ent.reanchor_scenario_times) 승인 대기 중인 B 카드의 예정된 정비 시간
--      id(시작 시각을 품는다)가 사라졌다. 기준점은 process 가 설비 처리 건이 없을 때만 옮긴다(scenario_buttons.may_reanchor). 시작할 때는
--      기준점이 이미 지난 경우(가장 이른 시나리오 기한 — 생산 오더 납기 · 출하 — 가 지금 이전)만 옮긴다: ent.scenario_times_stale().
--  E10 결정 id 없는 실행(수업 버튼형 pm-advance · issue-spare · delay-delivery)은 멱등 키가 없는데(메모리 · exec_skill 모두
--      `if v_decision is not null`), 고유 인덱스가 decision_id null 끼리도 같다고 봐(nulls not distinct) 같은 스킬 두 번째부터 23505 였다.
--      인덱스를 결정 id 가 있는 행으로 좁힌다.
--  E11 ① 002 뒤에 만든 ent 표 · 시퀀스(spare_stock · stock_movements · goods_receipts · pm_counters · pm_counter_log · execution_archive …)에
--         service_role 표 권한이 없어 service_role 로 exec_skill · reset_* 을 부르면 permission denied 였다. 표 · 시퀀스 권한과 앞으로
--         만들 표의 기본 권한을 준다(service_role 은 BYPASSRLS).
--      ② ent.execution_archive 는 읽기 계정(hyd_enterprise_reader)에 SELECT 만 있고 RLS 정책이 없어 0행으로 보였다 — 정책을 준다.
--      ③ 업무 전체 초기화가 재고 이동 · 운전시간 원장을 남겨(메모리는 비움) '최근 재고 이동'이 백엔드마다 달랐다. 두 원장도 다른 실행 기록과
--         같이 보관한 뒤 비우고, 시작값은 B · C 초기화 함수가 남기는 RESET · BASE 한 줄씩으로 시작한다(메모리 reset() 과 같음).
--      ④ 업무 전체 초기화가 작업지시를 먼저 잠그고(삭제) 나중에 계수기를 잠가, 계수기 → 작업지시 순으로 잠그는 B [초기화] · 원문 범위
--         전체 취소 · 일정 변경과 동시에 돌면 교착(40P01)할 수 있었다. 계수기를 먼저 잠근다.

-- ---------------------------------------------------------------- E10
drop index if exists ent.ux_transactions_forward;
create unique index ux_transactions_forward on ent.transactions (decision_id, skill)
  where compensates is null and decision_id is not null;
drop index if exists ent.ux_transactions_compensation;
create unique index ux_transactions_compensation on ent.transactions (decision_id, skill, ref)
  where compensates is not null and decision_id is not null;

-- ---------------------------------------------------------------- E11 ① service_role 표 권한 (002 의 grant all 은 그때 있던 표에만 걸렸다)
grant all on all tables in schema ent to service_role;
grant usage, select on all sequences in schema ent to service_role;
alter default privileges in schema ent grant all on tables to service_role;
alter default privileges in schema ent grant usage, select on sequences to service_role;

-- ---------------------------------------------------------------- E11 ② 읽기 계정 RLS 정책 (003 은 그때 있던 표에만 만들었다)
do $$ declare t text; begin
  for t in select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'ent' and c.relkind = 'r' and c.relrowsecurity
              and not exists (select 1 from pg_policy p where p.polrelid = c.oid
                                and (select oid from pg_roles where rolname = 'hyd_enterprise_reader') = any (p.polroles)) loop
    execute format('create policy enterprise_mcp_reader on ent.%I for select to hyd_enterprise_reader using (true)', t);
  end loop;
end $$;

-- ---------------------------------------------------------------- E8 시작할 때 기준점을 옮겨야 하는가
create or replace function ent.scenario_times_stale() returns boolean language sql stable as $$
  select coalesce(least((select min(due_at) from ent.production_orders), (select min(ship_at) from ent.fg_inventory)) <= now(), true)
$$;
comment on function ent.scenario_times_stale() is
  '시나리오 시각 기준점이 지났는가(가장 이른 생산 오더 납기 · 출하 시각 <= 지금). enterprise-sim 시작 때만 이 값으로 기준점을 옮긴다 — 메모리 entsim.data.scenario_times_stale 과 같은 규칙';

-- ---------------------------------------------------------------- E11 ③ ④ 업무 전체 초기화 (059 본문 + 원장 보관 · 잠금 순서)
create or replace function ent.reset_executions() returns void language plpgsql as $$
declare n bigint;
begin
  -- 잠금 순서: 계수기 → 작업지시 → 발주 → 재고 (B [초기화] · 원문 범위 전체 취소 · 일정 변경과 같은 방향)
  perform 1 from ent.pm_counters order by asset for update;
  n := nextval('ent.execution_reset_no');
  insert into ent.execution_archive (reset_no, table_name, ref, decision_id, row)
    select n, 'goods_receipts', g.id, g.decision_id, to_jsonb(g) from ent.goods_receipts g
    union all select n, 'transactions', t.id, t.decision_id, to_jsonb(t) from ent.transactions t
    union all select n, 'work_orders', w.id, w.decision_id, to_jsonb(w) from ent.work_orders w
    union all select n, 'pm_part_reservations', p.work_order, null, to_jsonb(p) from ent.pm_part_reservations p
    union all select n, 'purchase_requests', r.id, r.decision_id, to_jsonb(r) from ent.purchase_requests r
    union all select n, 'shipments', s.id, s.decision_id, to_jsonb(s) from ent.shipments s
    union all select n, 'lot_dispositions', l.lot, l.decision_id, to_jsonb(l) from ent.lot_dispositions l
    union all select n, 'ems_actions', null, e.decision_id, to_jsonb(e) from ent.ems_actions e
    union all select n, 'maintenance_history', h.wo, null, to_jsonb(h) from ent.maintenance_history h where h.wo not like 'WO-HIST-%'
    union all select n, 'stock_movements', m.ref, null, to_jsonb(m) from ent.stock_movements m
    union all select n, 'pm_counter_log', c.ref, null, to_jsonb(c) from ent.pm_counter_log c;
  delete from ent.goods_receipts;
  delete from ent.transactions; delete from ent.pm_part_reservations; delete from ent.work_orders; delete from ent.purchase_requests;
  delete from ent.shipments; delete from ent.lot_dispositions; delete from ent.ems_actions;
  delete from ent.maintenance_history where wo not like 'WO-HIST-%';
  delete from ent.stock_movements; delete from ent.pm_counter_log;
  update ent.production_orders set asset = moved_from, moved_from = null where moved_from is not null;
  perform ent.reset_spare_stock(null);
  perform ent.reset_pm_counters(null);
  perform ent.reanchor_scenario_times();
end $$;

revoke execute on function ent.reset_executions(), ent.scenario_times_stale() from public, anon, authenticated;
grant execute on function ent.reset_executions(), ent.scenario_times_stale() to service_role;
