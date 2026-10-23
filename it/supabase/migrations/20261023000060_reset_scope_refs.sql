-- 2026-10-23 업무 DB 점검(.evidence/audit2/enterprise.md) E1 · E2 · E3 · E4 · E6 · E7. 메모리 백엔드(it/enterprise-sim/entsim/state.py)와 같은 규칙.
--  E1 · E2 · E3 씰 키트(P-PMP-SEAL)는 B(정기 정비 오더 예약 · 즉시 출고)와 C(재고 보충 발주)가 같이 쓴다. 두 초기화가 부품 행 전체를 시작값으로
--     덮어(ent.reset_spare_stock) 다른 시나리오의 진행 중 건을 깼다 — C [초기화]가 B 오더의 예약을 지워 뒤의 B 취소가 기준 예약까지 깎았고,
--     B [초기화](059)가 C 발주의 입고 예정을 0으로 만들었으며, C [초기화]는 열린 발주를 '승인됨 → 발주'로 남겨 옛 발주가 입고 · 지연되었다.
--     고침: 초기화는 자기 시나리오가 실제로 잡은 것만 되돌린다.
--       B [초기화](reset_pm_counters): 부품을 잡은 정기 정비 오더를 취소로 닫고 예약을 푼 뒤, 그 오더가 잡은 수량만 되돌린다(예약 −, 출고면 실물 +).
--       C [초기화](reset_spare_stock): 그 부품의 열린 수량 발주를 취소로 닫고(입고 예정 = 남은 열린 발주 합계 = 0), 실물 · 예약을 시작값으로 —
--       단 아직 진행 중인 B 오더가 잡은 수량(예약 · 출고)은 남긴다. B가 시작값보다 많이 출고했으면 거절한다(B [초기화] 먼저).
--     업무 전체 초기화(reset_executions, 059)는 기록을 옮긴 뒤 두 함수를 부르므로 지금처럼 모두 시작값이다.
--  E4 구매요청 취소 보상(skill:cancel-purchase-request)이 수량 발주의 입고 예정(on_order)을 되돌리고 이동 원장에 CANCEL 을 남긴다.
--  E6 작업지시 취소 보상(skill:cancel-work-order)이 그 오더를 가리키는 pm_counters.plan_wo · plan_window · planned_at 을 지운다.
--  E7 실행 기록 · 오더 · 요청 번호(TX · WO · PR · GR · GI · RUN · PMR · SH)의 난수를 16진 4자리(16비트)에서 12자리(48비트)로 늘린다(ent.new_ref).
--     같은 날 100건이면 7 %로 기본키가 겹쳐 사람 승인 실행이 400으로 거절되었다. 054(12자리) · 056/058(16자리)은 이미 길다.
-- 현재 정의 사슬: exec_skill(058) → exec_skill_before_pm56(054) → exec_skill_before_pm54(045 본문) / exec_compensation(056) →
-- exec_compensation_before_pm56(022 본문). 아래 두 *_before_* 함수는 045 · 022 본문을 그대로 옮기고 위 고침만 더했다(이름 · 권한 유지).
-- 잠금 순서: 계수기 → 작업지시 → 재고(원문 범위 전체 취소와 같음), 발주 → 재고(입고 · 구매요청 취소와 같음).

alter table ent.stock_movements drop constraint if exists stock_movements_kind_check;
alter table ent.stock_movements add constraint stock_movements_kind_check
  check (kind in ('ISSUE', 'CONSUME', 'ORDER', 'RECEIPT', 'RESET', 'CANCEL'));   -- CANCEL: 발주 취소로 입고 예정이 줄었다(qty = 줄어든 입고 예정)

create or replace function ent.new_ref(p_prefix text) returns text language sql volatile as $$
  select p_prefix || '-' || to_char(now(), 'MMDD') || '-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 12))
$$;
comment on function ent.new_ref(text) is '실행 기록 · 오더 · 요청 번호: 접두-월일-16진 12자리(48비트 난수, gen_random_uuid 앞 12자리). 메모리 entsim.state._id 와 같은 꼴';

-- C [초기화]: 열린 수량 발주를 닫고, 실물 · 예약을 시작값으로 — 진행 중 B 정비 오더가 잡은 수량은 남긴다
create or replace function ent.reset_spare_stock(p_part text default null) returns jsonb language plpgsql as $$
declare r ent.spare_stock; v_pr record; v_held_reserved integer; v_held_issued integer; v_open integer; v_closed jsonb; v_x jsonb; v_after ent.spare_stock;
begin
  perform 1 from ent.purchase_requests where status = '승인됨 → 발주' and qty is not null and part_no is not null
     and (p_part is null or part_no = p_part) order by id for update;
  for r in select * from ent.spare_stock where p_part is null or part_no = p_part order by part_no for update loop
    select coalesce(sum(x.qty) filter (where x.stock_effect = 'reserve'), 0)::integer, coalesce(sum(x.qty) filter (where x.stock_effect = 'issue'), 0)::integer
      into v_held_reserved, v_held_issued
      from ent.pm_part_reservations x join ent.work_orders w on w.id = x.work_order
     where x.part_no = r.part_no and x.released_at is null and w.status = '배정됨';
    if r.base_on_hand - v_held_issued < 0 then
      raise exception 'INVALID: % actual stock % is issued to open maintenance orders; reset B first', r.part_no, v_held_issued using errcode = '22023';
    end if;
    with closed as (
      update ent.purchase_requests set status = '취소', cancelled_at = now()
       where part_no = r.part_no and status = '승인됨 → 발주' and qty is not null
      returning id, qty, asset)
    select coalesce(jsonb_agg(jsonb_build_object('id', id, 'qty', qty, 'asset', asset) order by id), '[]'::jsonb) into v_closed from closed;
    select coalesce(sum(qty), 0)::integer into v_open from ent.purchase_requests
     where part_no = r.part_no and status = '승인됨 → 발주' and qty is not null;
    update ent.spare_stock set on_hand = base_on_hand - v_held_issued, reserved = base_reserved + v_held_reserved, on_order = v_open,
           below_since = null, updated_at = now()
     where part_no = r.part_no;
    perform ent.refresh_spare_flag(r.part_no);
    select * into v_after from ent.spare_stock where part_no = r.part_no;
    for v_x in select x from jsonb_array_elements(v_closed) x loop
      insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
      values (r.part_no, 'CANCEL', (v_x->>'qty')::integer, v_x->>'asset', v_x->>'id', 'instructor', format('수업 초기화 — 발주 %s 취소', v_x->>'id'),
              v_after.on_hand, v_after.on_hand - v_after.reserved + v_after.on_order);
    end loop;
    insert into ent.stock_movements (part_no, kind, qty, ref, by_whom, reason, on_hand_after, available_after)
    values (r.part_no, 'RESET', v_after.on_hand - r.on_hand, 'RESET', 'instructor', '수업 초기화', v_after.on_hand,
            v_after.on_hand - v_after.reserved + v_after.on_order);
  end loop;
  return ent.spare_stock_read(p_part);
end $$;

-- B [초기화]: 부품을 잡은 정기 정비 오더를 닫고 그 오더가 잡은 수량만 되돌린다. 계수기 · 이번 회차 오더 표시는 059와 같이 시작값으로.
create or replace function ent.reset_pm_counters(p_asset text default null) returns jsonb language plpgsql as $$
declare r ent.pm_counters; v_rel jsonb; v_x jsonb; v_stock ent.spare_stock; v_qty integer;
begin
  perform 1 from ent.pm_counters where p_asset is null or asset = p_asset order by asset for update;
  with open_orders as (
    update ent.work_orders w set status = '취소', cancelled_at = now()
     where w.status = '배정됨' and (p_asset is null or w.asset = p_asset)
       and exists (select 1 from ent.pm_part_reservations x where x.work_order = w.id and x.released_at is null)
    returning w.id),
  released as (
    update ent.pm_part_reservations x set released_at = now()
     where x.released_at is null and x.work_order in (select id from open_orders)
    returning x.work_order, x.part_no, x.qty, x.stock_effect)
  select coalesce(jsonb_agg(jsonb_build_object('part_no', part_no, 'stock_effect', stock_effect, 'qty', qty, 'orders', orders)
                            order by part_no, stock_effect), '[]'::jsonb)
    into v_rel
    from (select part_no, stock_effect, sum(qty) qty, string_agg(work_order, ', ' order by work_order) orders
            from released group by part_no, stock_effect) g;
  for v_x in select x from jsonb_array_elements(v_rel) x loop
    v_qty := (v_x->>'qty')::numeric::integer;
    select * into v_stock from ent.spare_stock where part_no = v_x->>'part_no' for update;
    if not found then
      raise exception 'INVALID: % is not a managed spare part', v_x->>'part_no' using errcode = '22023';
    end if;
    if v_x->>'stock_effect' = 'reserve' then
      if v_stock.reserved < v_qty then
        raise exception 'INVALID: % reservations (%) are less than open maintenance orders hold (%); stock ledger needs review',
          v_stock.part_no, v_stock.reserved, v_qty using errcode = '22023';
      end if;
      update ent.spare_stock set reserved = reserved - v_qty, updated_at = now() where part_no = v_stock.part_no;
    else
      update ent.spare_stock set on_hand = on_hand + v_qty, updated_at = now() where part_no = v_stock.part_no;
    end if;
    perform ent.refresh_spare_flag(v_stock.part_no);
    select * into v_stock from ent.spare_stock where part_no = v_stock.part_no;
    insert into ent.stock_movements (part_no, kind, qty, ref, by_whom, reason, on_hand_after, available_after)
    values (v_stock.part_no, 'RESET', case when v_x->>'stock_effect' = 'issue' then v_qty else 0 end, 'RESET', 'instructor',
            format('수업 초기화 — 정비 오더 %s %s', v_x->>'orders', case when v_x->>'stock_effect' = 'issue' then '출고 반납' else '예약 해제' end),
            v_stock.on_hand, v_stock.on_hand - v_stock.reserved + v_stock.on_order);
  end loop;
  for r in select * from ent.pm_counters where p_asset is null or asset = p_asset order by asset loop
    update ent.pm_counters set since_pm_h = base_since_pm_h, total_h = base_total_h, cycle = 1, last_done_at = null, due_since = null,
           plan_wo = null, plan_window = null, planned_at = null, updated_at = now() where asset = r.asset;
    perform ent.refresh_pm_flag(r.asset);
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (r.asset, 'BASE', r.base_since_pm_h - r.since_pm_h, r.base_since_pm_h, r.base_total_h, 1, 'RESET', 'instructor', '수업 초기화');
  end loop;
  return ent.pm_status_read(p_asset);
end $$;

-- 045 ent.exec_skill 본문(054에서 exec_skill_before_pm54 로 이름이 바뀜) — 번호만 ent.new_ref 로
create or replace function ent.exec_skill_before_pm54(p jsonb) returns jsonb
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

  v_id := ent.new_ref('TX');

  if v_skill = 'skill:schedule-maintenance' then
    v_ref := ent.new_ref('WO');
    v_window_label := v_params->>'window';
    if v_params ? 'window_id' then                       -- C2: 승인된 예정된 정비 시간 id → 라벨 · 시작 시각 (설비가 다르거나 없는 창은 거절)
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
    v_ref := ent.new_ref('PR');
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
    v_ref := ent.new_ref('GR');
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
    v_ref := ent.new_ref('GI');
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
    v_ref := ent.new_ref('RUN');
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
    v_ref := ent.new_ref('PMR');
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
    v_ref := ent.new_ref('SH');
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

-- 022 ent.exec_compensation 본문(056에서 exec_compensation_before_pm56 으로 이름이 바뀜) — 번호 · E4 · E6
create or replace function ent.exec_compensation_before_pm56(p jsonb) returns jsonb
language plpgsql
as $$
declare
  v_skill text := p->>'skill';
  v_ref text := p->'params'->>'ref';
  v_decision text := p->>'decision';
  v_compensates text := p->>'compensates';
  v_fp text := md5((jsonb_build_object('decision', p->'decision', 'option', p->'option', 'skill', p->'skill', 'asset', p->'asset', 'params', p->'params'))::text);
  v_prior ent.transactions;
  v_row ent.transactions;
  v_system text; v_detail text; v_id text; v_asset text;
  v_before jsonb; v_after jsonb;
  v_wo ent.work_orders; v_pr ent.purchase_requests; v_order ent.production_orders; v_hold ent.lot_dispositions;
  v_stock ent.spare_stock;
begin
  v_system := case v_skill when 'skill:cancel-work-order' then 'sys:cmms' when 'skill:cancel-purchase-request' then 'sys:erp'
                           when 'skill:restore-production' then 'sys:mes' when 'skill:release-hold' then 'sys:qms' end;
  if v_system is null then
    raise exception 'unknown compensation skill %', v_skill using errcode = '22023';
  end if;
  if v_ref is null or v_ref = '' then
    raise exception '% needs the reference of the record to reverse (params.ref)', v_skill using errcode = '22023';
  end if;
  if p->>'asset' is not null and not exists (select 1 from ent.assets where code = p->>'asset') then
    raise exception 'INVALID: unknown asset %', p->>'asset' using errcode = '22023';
  end if;
  if v_decision is not null then
    perform pg_advisory_xact_lock(hashtextextended('ent.exec_compensation:' || v_decision || ':' || v_skill || ':' || v_ref, 0));
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and ref = v_ref and compensates is not null;
    if found then
      if v_prior.fingerprint <> v_fp then
        raise exception 'idempotency conflict: decision/skill/ref already compensated with different input' using errcode = '23505';
      end if;
      return ent.tx_response(v_prior);
    end if;
  end if;
  v_id := ent.new_ref('TX');

  if v_skill = 'skill:cancel-work-order' then
    -- 잠금 순서: 계수기 → 작업지시 (원문 범위 전체 취소 · B [초기화]와 같은 순서)
    perform 1 from ent.pm_counters where plan_wo = v_ref order by asset for update;
    select * into v_wo from ent.work_orders where id = v_ref for update;
    if not found then raise exception 'no such work order %', v_ref using errcode = '22023'; end if;
    if v_wo.status <> '배정됨' then raise exception 'work order % cannot be cancelled in status %', v_ref, v_wo.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_wo);
    update ent.work_orders set status = '취소', cancelled_at = now() where id = v_ref;
    -- 점검 E6: 이 오더가 '이번 회차 정기 정비 오더'(trigger ent.mark_pm_plan)였으면 표시를 지운다 — 남기면 pm_alert 가 꺼진 채 B가 거절됐다
    update ent.pm_counters set plan_wo = null, plan_window = null, planned_at = null, updated_at = now() where plan_wo = v_ref;
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_ref;
    v_asset := v_wo.asset; v_detail := format('%s 작업지시 %s 취소 (%s)', v_wo.asset, v_ref, v_wo.task);
  elsif v_skill = 'skill:cancel-purchase-request' then
    select * into v_pr from ent.purchase_requests where id = v_ref for update;
    if not found then raise exception 'no such purchase request %', v_ref using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then raise exception 'purchase request % cannot be cancelled in status %', v_ref, v_pr.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_pr);
    update ent.purchase_requests set status = '취소', cancelled_at = now() where id = v_ref;
    -- 점검 E4: 수량 발주(C2)면 재고의 입고 예정을 되돌린다 — 남기면 취소한 발주가 가용을 부풀려 '재고 보충 필요'가 꺼진 채였다
    if v_pr.qty is not null and v_pr.part_no is not null then
      select * into v_stock from ent.spare_stock where part_no = v_pr.part_no for update;
      if found then
        if v_stock.on_order < v_pr.qty then
          raise exception 'INVALID: on-order quantity of % (%) is less than purchase request % (%)', v_pr.part_no, v_stock.on_order, v_ref, v_pr.qty
            using errcode = '22023';
        end if;
        update ent.spare_stock set on_order = on_order - v_pr.qty, updated_at = now() where part_no = v_pr.part_no returning * into v_stock;
        perform ent.refresh_spare_flag(v_pr.part_no);
        insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
        values (v_pr.part_no, 'CANCEL', v_pr.qty, v_pr.asset, v_ref, p->>'by', format('발주 %s 취소', v_ref), v_stock.on_hand,
                v_stock.on_hand - v_stock.reserved + v_stock.on_order);
      end if;
    end if;
    select to_jsonb(r) into v_after from ent.purchase_requests r where r.id = v_ref;
    v_asset := v_pr.asset; v_detail := format('구매요청 %s 취소 (%s — %s)', v_ref, v_pr.part, v_pr.supplier_name);
  elsif v_skill = 'skill:restore-production' then
    select * into v_order from ent.production_orders where order_id = v_ref for update;
    if not found or v_order.moved_from is null then raise exception 'order % has no reallocation to restore', v_ref using errcode = '22023'; end if;
    v_before := to_jsonb(v_order);
    update ent.production_orders set asset = moved_from, moved_from = null where order_id = v_ref;
    select to_jsonb(o) into v_after from ent.production_orders o where o.order_id = v_ref;
    v_asset := v_order.moved_from; v_detail := format('%s %s → %s 원복', v_ref, v_order.asset, v_order.moved_from);
  elsif v_skill = 'skill:release-hold' then
    select * into v_hold from ent.lot_dispositions where lot = v_ref and kind = 'HOLD' order by created_at desc limit 1 for update;
    if not found then raise exception 'no hold on lot %', v_ref using errcode = '22023'; end if;
    if v_hold.status <> '격리 · 전수검사 대기' then raise exception 'lot % hold cannot be released in status %', v_ref, v_hold.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_hold);
    update ent.lot_dispositions set status = '격리 해제', released_at = now() where id = v_hold.id;
    select to_jsonb(d) into v_after from ent.lot_dispositions d where d.id = v_hold.id;
    v_asset := v_hold.asset; v_detail := format('로트 %s 격리 해제', v_ref);
  end if;

  insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, compensates, before, after)
  values (v_id, v_system, v_skill, v_ref, v_detail, coalesce(p->>'asset', v_asset), v_decision, p->>'option', p->>'by', v_fp, coalesce(v_compensates, ''), v_before, v_after)
  returning * into v_row;
  return ent.tx_response(v_row);
end $$;

revoke execute on function ent.new_ref(text), ent.reset_spare_stock(text), ent.reset_pm_counters(text),
  ent.exec_skill_before_pm54(jsonb), ent.exec_compensation_before_pm56(jsonb) from public, anon, authenticated;
grant execute on function ent.new_ref(text), ent.reset_spare_stock(text), ent.reset_pm_counters(text),
  ent.exec_skill_before_pm54(jsonb), ent.exec_compensation_before_pm56(jsonb) to service_role;
