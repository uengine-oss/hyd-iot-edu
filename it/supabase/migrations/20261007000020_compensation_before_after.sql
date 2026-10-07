-- A103 (follow-up, 2026-10-07): the exact-reverse executions (ent.exec_compensation, migration 15) now keep the reversed
-- business row before and after the reversal, like ent.exec_skill does since migration 19. Live 2026-10-07 08:13 the
-- cancel-work-order row in the ledger had before/after NULL while the forward schedule-maintenance row had `after`.
-- Additive: same signature, same checks, same idempotency; only v_before/v_after are captured and stored.
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
  v_system text; v_detail text; v_id text; v_asset text;
  v_before jsonb; v_after jsonb;   -- A103: the reversed business row before/after this execution
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
  if v_decision is not null then
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and ref = v_ref and compensates is not null;
    if found then
      if v_prior.fingerprint <> v_fp then
        raise exception 'idempotency conflict: decision/skill/ref already compensated with different input' using errcode = '23505';
      end if;
      return (to_jsonb(v_prior) - 'fingerprint') || jsonb_build_object('decision', v_prior.decision_id, 'option', v_prior.option_id, 'by', v_prior.requested_by);
    end if;
  end if;
  v_id := 'TX-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));

  if v_skill = 'skill:cancel-work-order' then
    select * into v_wo from ent.work_orders where id = v_ref;
    if not found then raise exception 'no such work order %', v_ref using errcode = '22023'; end if;
    if v_wo.status <> '배정됨' then raise exception 'work order % cannot be cancelled in status %', v_ref, v_wo.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_wo);
    update ent.work_orders set status = '취소', cancelled_at = now() where id = v_ref;
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_ref;
    v_asset := v_wo.asset; v_detail := format('%s 작업지시 %s 취소 (%s)', v_wo.asset, v_ref, v_wo.task);
  elsif v_skill = 'skill:cancel-purchase-request' then
    select * into v_pr from ent.purchase_requests where id = v_ref;
    if not found then raise exception 'no such purchase request %', v_ref using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then raise exception 'purchase request % cannot be cancelled in status %', v_ref, v_pr.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_pr);
    update ent.purchase_requests set status = '취소', cancelled_at = now() where id = v_ref;
    select to_jsonb(r) into v_after from ent.purchase_requests r where r.id = v_ref;
    v_asset := v_pr.asset; v_detail := format('구매요청 %s 취소 (%s — %s)', v_ref, v_pr.part, v_pr.supplier_name);
  elsif v_skill = 'skill:restore-production' then
    select * into v_order from ent.production_orders where order_id = v_ref;
    if not found or v_order.moved_from is null then raise exception 'order % has no reallocation to restore', v_ref using errcode = '22023'; end if;
    v_before := to_jsonb(v_order);
    update ent.production_orders set asset = moved_from, moved_from = null where order_id = v_ref;
    select to_jsonb(o) into v_after from ent.production_orders o where o.order_id = v_ref;
    v_asset := v_order.moved_from; v_detail := format('%s %s → %s 원복', v_ref, v_order.asset, v_order.moved_from);
  elsif v_skill = 'skill:release-hold' then
    select * into v_hold from ent.lot_dispositions where lot = v_ref and kind = 'HOLD' order by created_at desc limit 1;
    if not found then raise exception 'no hold on lot %', v_ref using errcode = '22023'; end if;
    if v_hold.status <> '격리 · 전수검사 대기' then raise exception 'lot % hold cannot be released in status %', v_ref, v_hold.status using errcode = '22023'; end if;
    v_before := to_jsonb(v_hold);
    update ent.lot_dispositions set status = '격리 해제', released_at = now() where id = v_hold.id;
    select to_jsonb(d) into v_after from ent.lot_dispositions d where d.id = v_hold.id;
    v_asset := v_hold.asset; v_detail := format('로트 %s 격리 해제', v_ref);
  end if;

  insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, compensates, before, after)
  values (v_id, v_system, v_skill, v_ref, v_detail, coalesce(p->>'asset', v_asset), v_decision, p->>'option', p->>'by', v_fp, coalesce(v_compensates, ''), v_before, v_after);
  return jsonb_build_object('id', v_id, 't', now(), 'system', v_system, 'skill', v_skill, 'ref', v_ref, 'detail', v_detail,
                            'asset', coalesce(p->>'asset', v_asset), 'decision', v_decision, 'option', p->>'option', 'by', p->>'by',
                            'compensates', v_compensates, 'before', v_before, 'after', v_after);
end $$;

revoke execute on function ent.exec_compensation(jsonb) from public, anon, authenticated;
grant execute on function ent.exec_compensation(jsonb) to service_role;
comment on function ent.exec_compensation(jsonb) is 'HYD A072/A103: exact reverse of one forward enterprise record by reference, keeping the row before/after; refuses records that moved on';
