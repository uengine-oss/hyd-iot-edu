-- C2 업무 DB 연기 시험 (버리는 DB c2_check 에서만): 출고 −2 → 재주문점 이탈 → 발주(금액 검사 · AVL) → 납기 지연 → 입고 → 회복, 작업지시 정비 시간 · 완료 소모,
-- 운전시간 빨리 감기 → PM_DUE → 계수기 리셋.
\set ON_ERROR_STOP 1
select ent.spare_stock_read('P-PMP-SEAL')->'facts' as before;
select ent.exec_skill('{"skill":"skill:issue-spare","asset":"HYD-03","by":"instructor","params":{"part_no":"P-PMP-SEAL","qty":2,"reason":"수업 원인: 자재 출고 −2"}}')->>'detail' as issue;
select ent.spare_stock_read('P-PMP-SEAL')->'facts' as after_issue;
select ent.part_quotes_read('P-PMP-SEAL') as quotes;
do $$ begin
  perform ent.exec_skill('{"decision":"dec-x","skill":"skill:procure-part","asset":"HYD-03","by":"t","params":{"supplier":"sup:c","part_no":"P-PMP-SEAL","qty":6}}');
  raise exception 'non-AVL accepted';
exception when sqlstate '22023' then raise notice 'non-AVL refused: %', sqlerrm; end $$;
do $$ begin
  perform ent.exec_skill('{"decision":"dec-y","skill":"skill:procure-part","asset":"HYD-03","by":"t","params":{"supplier":"sup:b","part_no":"P-PMP-SEAL","qty":6,"amount":300}}');
  raise exception 'wrong amount accepted';
exception when sqlstate '22023' then raise notice 'amount mismatch refused: %', sqlerrm; end $$;
select ent.exec_skill('{"decision":"dec-c","skill":"skill:procure-part","asset":"HYD-03","by":"buyer","params":{"supplier":"sup:b","part_no":"P-PMP-SEAL","part":"펌프 축 씰 키트","qty":6,"amount":330}}')->>'detail' as po;
select ent.spare_stock_read('P-PMP-SEAL')->'facts'->>'on_order' as on_order;
select ent.exec_skill('{"decision":"cls-d","skill":"skill:delay-delivery","asset":"HYD-03","by":"instructor","params":{"days":3,"part_no":"P-PMP-SEAL"}}')->>'detail' as delay;
select ent.purchase_order_read((select id from ent.purchase_requests where decision_id='dec-c'))->'facts'->>'delay_d' as delay_d;
select ent.exec_skill(jsonb_build_object('decision','dec-c','skill','skill:receive-goods','asset','HYD-03','by','process',
       'params', jsonb_build_object('ref',(select id from ent.purchase_requests where decision_id='dec-c'))))->>'detail' as gr;
select ent.spare_stock_read('P-PMP-SEAL')->'facts' as after_receipt;
select (ent.next_maintenance_windows('HYD-02', 3)).*;
select ent.exec_skill(jsonb_build_object('decision','dec-b','skill','skill:schedule-maintenance','asset','HYD-02','by','mgr',
       'params', jsonb_build_object('task','SOP-PMP-04 펌프 축 씰 교체','window_id',(select id from ent.next_maintenance_windows('HYD-02',3) where kind='N' limit 1))))->'after' as wo;
select ent.exec_skill(jsonb_build_object('decision','dec-b','skill','skill:complete-maintenance','asset','HYD-02','by','process',
       'params', jsonb_build_object('ref',(select id from ent.work_orders where decision_id='dec-b'),'sop','SOP-PMP-04')))->>'detail' as done;
select kind, qty, on_hand_after, available_after, reason from ent.stock_movements order by id;
select ent.reset_spare_stock(null)->'facts' as reset;
select ent.maintenance_windows_read('HYD-02')->'facts' as windows;
select asset, pm_since_h, pm_due, pm_window_open, pm_limit_in_h, night_window_in_h, night_within_limit, monthly_within_limit, bundle_peer, bundle_crew_ok,
       spare_gap_after_pm, spare_gap_after_bundle from ent.pm_status order by asset;
select ent.exec_skill(jsonb_build_object('decision','cls-a-'||a,'skill','skill:pm-advance','asset',a,'by','instructor','params','{"hours":300}'::jsonb))->>'detail' as advance
  from unnest(array['HYD-01','HYD-02','HYD-03']) a;
select asset, pm_since_h, pm_due, pm_window_open, pm_limit_in_h, night_within_limit, monthly_within_limit, bundle_peer, bundle_peer_since_h, due_since is not null as due_marked
  from ent.pm_status order by asset;
select ent.exec_skill('{"decision":"dec-pm","skill":"skill:pm-reset","asset":"HYD-02","by":"process","params":{"ref":"WO-x"}}')->>'detail' as pm_reset;
select ent.pm_status_read('HYD-02')->'facts'->>'pm_since_h' as since_after_reset, ent.pm_status_read('HYD-02')->'facts'->>'cycle' as cycle;
select kind, delta_h, since_after, cycle from ent.pm_counter_log order by id;
select ent.reset_pm_counters(null)->'facts'->>'pm_since_h' as pm_reset_base;
