-- A103 (R13 D05, process-gpt-sample-app-wms audit_events core_schema.sql:168-179 · agentic_operations.sql:612-614): every
-- enterprise execution keeps the affected business row before and after it — the ledger used to hold `detail` text only.
-- Additive: two jsonb columns and the same exec_skill body with the captures; compensation (migration 15) is unchanged for now.
alter table ent.transactions add column if not exists before jsonb;
alter table ent.transactions add column if not exists after jsonb;
comment on column ent.transactions.before is 'A103: 영향 행의 실행 전 상태(수정형 스킬만, 생성형은 null)';
comment on column ent.transactions.after is 'A103: 영향 행의 실행 후 상태(생성·수정 결과 행)';

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
  v_system text;
  v_ref text; v_detail text; v_id text;
  v_alt text; v_order text; v_sup text; v_sup_name text; v_part text; v_lot text; v_inv ent.fg_inventory; v_q ent.quality_profiles;
  v_before jsonb; v_after jsonb;   -- A103: the affected business row before/after this execution (audit_events of the product)
begin
  v_system := case v_skill
    when 'skill:schedule-maintenance' then 'sys:cmms' when 'skill:reallocate-production' then 'sys:mes'
    when 'skill:procure-part' then 'sys:erp' when 'skill:hold-lot' then 'sys:qms' when 'skill:release-lot' then 'sys:qms'
    when 'skill:substitute-shipment' then 'sys:erp' when 'skill:demand-control' then 'sys:ems' end;
  if v_system is null then
    raise exception 'unknown or non-enterprise skill %', v_skill using errcode = '22023';
  end if;

  if v_decision is not null then
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill;
    if found then
      if v_prior.fingerprint <> v_fp then
        raise exception 'idempotency conflict: decision/skill already executed with different input' using errcode = '23505';
      end if;
      return to_jsonb(v_prior) - 'fingerprint';
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
    select order_id, alt_asset into v_order, v_alt from ent.production_orders where asset = v_asset limit 1;
    if v_order is null then
      v_ref := '-'; v_detail := format('%s에 이관할 오더 없음', v_asset);
    else
      v_alt := coalesce(v_params->>'to', v_alt);
      select to_jsonb(o) into v_before from ent.production_orders o where o.order_id = v_order;
      update ent.production_orders set moved_from = v_asset, asset = v_alt where order_id = v_order;
      select to_jsonb(o) into v_after from ent.production_orders o where o.order_id = v_order;
      v_ref := v_order; v_detail := format('%s %s → %s 이관', v_order, v_asset, v_alt);
    end if;

  elsif v_skill = 'skill:procure-part' then
    v_sup := coalesce(v_params->>'supplier', 'sup:b');
    select name into v_sup_name from ent.suppliers where id = v_sup;
    v_part := coalesce(v_params->>'part', '쿨러 코어');
    v_ref := 'PR-' || to_char(now(), 'MMDD') || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into ent.purchase_requests (id, part, supplier, supplier_name, asset, decision_id, option_id, requested_by)
    values (v_ref, v_part, v_sup, coalesce(v_sup_name, v_sup), v_asset, v_decision, p->>'option', p->>'by');
    v_detail := format('%s 구매요청 — %s', v_part, coalesce(v_sup_name, v_sup));
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
  values (v_id, v_system, v_skill, v_ref, v_detail, v_asset, v_decision, p->>'option', p->>'by', v_fp, v_before, v_after);
  return jsonb_build_object('id', v_id, 't', now(), 'system', v_system, 'skill', v_skill, 'ref', v_ref, 'detail', v_detail,
                            'asset', v_asset, 'decision', v_decision, 'option', p->>'option', 'by', p->>'by', 'before', v_before, 'after', v_after);
end $$;
