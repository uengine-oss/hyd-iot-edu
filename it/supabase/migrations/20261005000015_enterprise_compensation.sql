-- A072 (2026-10-05): exact compensating transactions in the business systems. A compensation reverses one forward
-- record by its reference, only while the record is still in the state the forward transaction created, and is keyed by
-- (decision, skill, reference) so one decision may reverse several records. Irreversible skills (release-lot,
-- substitute-shipment, demand-control) have no RPC here on purpose: the process asks a person instead.
alter table ent.transactions add column if not exists compensates text;
alter table ent.transactions drop constraint if exists transactions_decision_id_skill_key;
create unique index if not exists ux_transactions_forward on ent.transactions (decision_id, skill)
  nulls not distinct where compensates is null;
create unique index if not exists ux_transactions_compensation on ent.transactions (decision_id, skill, ref)
  nulls not distinct where compensates is not null;

alter table ent.work_orders add column if not exists cancelled_at timestamptz;
alter table ent.purchase_requests add column if not exists cancelled_at timestamptz;
alter table ent.lot_dispositions add column if not exists released_at timestamptz;

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
    update ent.work_orders set status = '취소', cancelled_at = now() where id = v_ref;
    v_asset := v_wo.asset; v_detail := format('%s 작업지시 %s 취소 (%s)', v_wo.asset, v_ref, v_wo.task);
  elsif v_skill = 'skill:cancel-purchase-request' then
    select * into v_pr from ent.purchase_requests where id = v_ref;
    if not found then raise exception 'no such purchase request %', v_ref using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then raise exception 'purchase request % cannot be cancelled in status %', v_ref, v_pr.status using errcode = '22023'; end if;
    update ent.purchase_requests set status = '취소', cancelled_at = now() where id = v_ref;
    v_asset := v_pr.asset; v_detail := format('구매요청 %s 취소 (%s — %s)', v_ref, v_pr.part, v_pr.supplier_name);
  elsif v_skill = 'skill:restore-production' then
    select * into v_order from ent.production_orders where order_id = v_ref;
    if not found or v_order.moved_from is null then raise exception 'order % has no reallocation to restore', v_ref using errcode = '22023'; end if;
    update ent.production_orders set asset = moved_from, moved_from = null where order_id = v_ref;
    v_asset := v_order.moved_from; v_detail := format('%s %s → %s 원복', v_ref, v_order.asset, v_order.moved_from);
  elsif v_skill = 'skill:release-hold' then
    select * into v_hold from ent.lot_dispositions where lot = v_ref and kind = 'HOLD' order by created_at desc limit 1;
    if not found then raise exception 'no hold on lot %', v_ref using errcode = '22023'; end if;
    if v_hold.status <> '격리 · 전수검사 대기' then raise exception 'lot % hold cannot be released in status %', v_ref, v_hold.status using errcode = '22023'; end if;
    update ent.lot_dispositions set status = '격리 해제', released_at = now() where id = v_hold.id;
    v_asset := v_hold.asset; v_detail := format('로트 %s 격리 해제', v_ref);
  end if;

  insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, compensates)
  values (v_id, v_system, v_skill, v_ref, v_detail, coalesce(p->>'asset', v_asset), v_decision, p->>'option', p->>'by', v_fp, coalesce(v_compensates, ''));
  return jsonb_build_object('id', v_id, 't', now(), 'system', v_system, 'skill', v_skill, 'ref', v_ref, 'detail', v_detail,
                            'asset', coalesce(p->>'asset', v_asset), 'decision', v_decision, 'option', p->>'option', 'by', p->>'by',
                            'compensates', v_compensates);
end $$;

revoke execute on function ent.exec_compensation(jsonb) from public, anon, authenticated;
grant execute on function ent.exec_compensation(jsonb) to service_role;
comment on function ent.exec_compensation(jsonb) is 'HYD A072: exact reverse of one forward enterprise record by reference; refuses records that moved on';
