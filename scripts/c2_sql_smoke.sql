-- C2 업무 DB 연기 시험 (버리는 DB c2_check 에서만): 출고 → 재주문점 이탈 → 발주(금액 검사 · AVL) → 입고 → 회복, 작업지시 정비창 · 완료 소모, 일정 · 기록.
\set ON_ERROR_STOP 1
select ent.spare_stock_read('P-PMP-SEAL')->'facts' as before;
select ent.exec_skill('{"skill":"skill:issue-spare","asset":"HYD-03","by":"instructor","params":{"part_no":"P-PMP-SEAL","qty":1,"reason":"수업 원인: 타 라인 출고"}}')->>'detail' as issue;
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
select ent.exec_skill(jsonb_build_object('decision','dec-c','skill','skill:receive-goods','asset','HYD-03','by','process',
       'params', jsonb_build_object('ref',(select id from ent.purchase_requests where decision_id='dec-c'))))->>'detail' as gr;
select ent.spare_stock_read('P-PMP-SEAL')->'facts' as after_receipt;
select (ent.next_maintenance_windows('HYD-02', 3)).*;
select ent.exec_skill(jsonb_build_object('decision','dec-b','skill','skill:schedule-maintenance','asset','HYD-02','by','mgr',
       'params', jsonb_build_object('task','SOP-PMP-04 펌프 축 씰 교체','window_id',(select id from ent.next_maintenance_windows('HYD-02',3) where kind='N' limit 1))))->'after' as wo;
select ent.exec_skill(jsonb_build_object('decision','dec-b','skill','skill:complete-maintenance','asset','HYD-02','by','process',
       'params', jsonb_build_object('ref',(select id from ent.work_orders where decision_id='dec-b'),'sop','SOP-PMP-04')))->>'detail' as done;
select ent.exec_skill('{"decision":"k1","skill":"skill:calendar-entry","asset":"HYD-02","params":{"title":"정비 예약","duration_h":4}}')->>'detail' as cal;
select ent.exec_skill('{"decision":"k2","skill":"skill:record-case","asset":"HYD-03","params":{"title":"씰 키트 보충","body":"..."}}')->>'detail' as rec;
select kind, qty, on_hand_after, available_after, reason from ent.stock_movements order by id;
select ent.reset_spare_stock(null)->'facts' as reset;
select ent.maintenance_windows_read('HYD-02')->'facts' as windows;
