-- A115 (r14 A7; process-gpt-sample-app-wms cancel_* `for update` and `INVALID: unknown sku`). Three defects of the
-- enterprise executions (migrations 19/20) found against the product sample:
--  1. the row an execution changes was read without a lock and then updated, so two concurrent decisions could both
--     see '배정됨' and both cancel / both reallocate; now `for update`.
--  2. exec_skill accepted any asset / supplier / target asset and wrote records for equipment or suppliers that do not
--     exist (the supplier name fell back to the raw id); now refused with INVALID like the wms sample.
--  3. a replay returned the stored row (`decision_id`, `option_id`, `requested_by`, compensates '') while the first call
--     returned `decision`, `option`, `by`; both now come from ent.tx_response, so the keys are the same by construction.
-- Also: concurrent requests of the same decision/skill(/ref) are serialised with a transaction advisory lock so the
-- second one replays instead of failing on the unique index. Same signatures, same checks otherwise, same idempotency.

create or replace function ent.tx_response(t ent.transactions) returns jsonb
language sql immutable
as $$
  select jsonb_build_object('id', t.id, 't', t.t, 'system', t.system, 'skill', t.skill, 'ref', t.ref, 'detail', t.detail,
                            'asset', t.asset, 'decision', t.decision_id, 'option', t.option_id, 'by', t.requested_by,
                            'compensates', nullif(t.compensates, ''), 'before', t.before, 'after', t.after)
$$;
revoke execute on function ent.tx_response(ent.transactions) from public, anon, authenticated;
grant execute on function ent.tx_response(ent.transactions) to service_role;

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
begin
  v_system := case v_skill
    when 'skill:schedule-maintenance' then 'sys:cmms' when 'skill:reallocate-production' then 'sys:mes'
    when 'skill:procure-part' then 'sys:erp' when 'skill:hold-lot' then 'sys:qms' when 'skill:release-lot' then 'sys:qms'
    when 'skill:substitute-shipment' then 'sys:erp' when 'skill:demand-control' then 'sys:ems' end;
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
    insert into ent.work_orders (id, asset, task, window_label, decision_id, option_id, requested_by)
    values (v_ref, v_asset, coalesce(v_params->>'task', '쿨러 핀 세척 (SOP-COOL-02)'),
            coalesce(v_params->>'window', case when (p->>'option') like '%derate%' then '야간 정비창' else '즉시' end), v_decision, p->>'option', p->>'by');
    v_detail := format('%s %s — %s', v_asset, coalesce(v_params->>'task', '쿨러 핀 세척 (SOP-COOL-02)'), coalesce(v_params->>'window', '즉시'));
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
    insert into ent.purchase_requests (id, part, supplier, supplier_name, asset, decision_id, option_id, requested_by)
    values (v_ref, v_part, v_sup, v_sup_name, v_asset, v_decision, p->>'option', p->>'by');
    v_detail := format('%s 구매요청 — %s', v_part, v_sup_name);
    select to_jsonb(r) into v_after from ent.purchase_requests r where r.id = v_ref;

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

create or replace function ent.exec_compensation(p jsonb) returns jsonb
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
  v_id := 'TX-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));

  if v_skill = 'skill:cancel-work-order' then
    select * into v_wo from ent.work_orders where id = v_ref for update;
    if not found then raise exception 'no such work order %', v_ref using errcode = '22023'; end if;
    if v_wo.status <> '배정됨' then raise exception 'work order % cannot be cancelled in status %', v_ref, v_wo.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_wo);
    update ent.work_orders set status = '취소', cancelled_at = now() where id = v_ref;
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_ref;
    v_asset := v_wo.asset; v_detail := format('%s 작업지시 %s 취소 (%s)', v_wo.asset, v_ref, v_wo.task);
  elsif v_skill = 'skill:cancel-purchase-request' then
    select * into v_pr from ent.purchase_requests where id = v_ref for update;
    if not found then raise exception 'no such purchase request %', v_ref using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then raise exception 'purchase request % cannot be cancelled in status %', v_ref, v_pr.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_pr);
    update ent.purchase_requests set status = '취소', cancelled_at = now() where id = v_ref;
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

revoke execute on function ent.exec_skill(jsonb) from public, anon, authenticated;
grant execute on function ent.exec_skill(jsonb) to service_role;
revoke execute on function ent.exec_compensation(jsonb) from public, anon, authenticated;
grant execute on function ent.exec_compensation(jsonb) to service_role;
comment on function ent.exec_compensation(jsonb) is 'HYD A072/A103/A115: exact reverse of one forward enterprise record by reference under a row lock, keeping the row before/after; refuses records that moved on';
