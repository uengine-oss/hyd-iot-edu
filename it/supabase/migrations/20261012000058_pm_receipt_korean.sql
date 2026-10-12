-- Future receipt display wording only; existing transactions and replay are preserved.
create or replace function ent.exec_skill(p jsonb) returns jsonb language plpgsql as $$
declare
  v_skill text:=p->>'skill';v_plan jsonb:=p->'params'->'plan';v_member jsonb;v_part jsonb;
  v_group text;v_ref text;v_first text;v_tx ent.transactions;v_prior ent.transactions;v_after jsonb;
  v_fp text:=md5(jsonb_build_object('decision',p->'decision','option',p->'option','skill',p->'skill','asset',p->'asset','params',p->'params')::text);
begin
  if v_skill='skill:pm-reset' and exists(select 1 from ent.work_orders w join ent.pm_counters c on c.plan_wo=w.id
       where c.asset=p->>'asset' and w.maintenance_plan is not null) then
    raise exception 'INVALID: source package verified completion required before service-position reset' using errcode='22023';
  end if;
  if v_skill='skill:complete-maintenance' and exists(select 1 from ent.work_orders where id=p->'params'->>'ref' and maintenance_plan is not null) then
    raise exception 'INVALID: source package physical completion requires verified field and trial-run records' using errcode='22023';
  end if;
  if v_skill<>'skill:schedule-maintenance-scoped' then
    if v_skill='skill:reschedule-maintenance' and v_plan is not null then
      perform ent.pm_scope_check(v_plan,p->>'asset',false);
      p:=jsonb_set(p,array['params','expected_order'],(p->'params'->'expected_order')-'reserved_parts');
    end if;
    return ent.exec_skill_before_pm56(p);
  end if;
  if coalesce(p->>'decision','')='' or coalesce(p->>'by','')='' or coalesce(p->>'option','')='' or v_plan->>'code' is distinct from 'WO_CREATE' then
    raise exception 'INVALID: approved source scheduling plan required' using errcode='22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('ent.exec_skill:'||(p->>'decision')||':'||v_skill,0));
  select * into v_prior from ent.transactions where decision_id=p->>'decision' and skill=v_skill and compensates is null;
  if found then
    if v_prior.fingerprint is distinct from v_fp then raise exception 'idempotency conflict' using errcode='23505'; end if;
    return ent.tx_response(v_prior);
  end if;
  perform ent.pm_scope_check(v_plan,p->>'asset',true);
  v_group:='PM-SCOPE-'||md5((p->>'decision')||':'||(p->>'option'));
  for v_member in select x from jsonb_array_elements(v_plan->'assets') x loop
    v_ref:='WO-'||upper(substr(md5(random()::text),1,16));if v_first is null then v_first:=v_ref;end if;
    insert into ent.work_orders(id,asset,task,window_label,decision_id,option_id,requested_by,window_id,window_starts_at,scope_group,maintenance_plan,package)
      values(v_ref,v_member->>'asset',coalesce(p->'params'->>'task',v_member->'service'->>'package_name'),
        coalesce(v_plan->'window'->>'label',case when (v_plan->'window'->>'immediate')::boolean then '즉시' else '예정된 정비 시간' end),
        p->>'decision',p->>'option',p->>'by',case when (v_member->'window'->>'immediate')::boolean then null else v_member->'window'->>'id' end,
        (v_member->'window'->>'starts_at')::timestamptz,v_group,v_plan,v_member->'service');
    update ent.pm_counters set plan_wo=v_ref,plan_window=coalesce(v_plan->'window'->>'label','예정된 정비 시간'),planned_at=now(),updated_at=now()
      where asset=v_member->>'asset';
    for v_part in select x from jsonb_array_elements(v_member->'parts') x loop
      insert into ent.pm_part_reservations(work_order,part_no,qty,stock_effect) values(v_ref,v_part->>'part_no',(v_part->>'qty')::numeric,v_plan->>'stock_effect');
    end loop;
  end loop;
  for v_part in select x from jsonb_array_elements(v_plan->'parts_totals') x loop
    if v_plan->>'stock_effect'='reserve' then
      update ent.spare_stock set reserved=reserved+(v_part->>'qty')::numeric,updated_at=now() where part_no=v_part->>'part_no';
    else
      update ent.spare_stock set on_hand=on_hand-(v_part->>'qty')::numeric,updated_at=now() where part_no=v_part->>'part_no';
    end if;
    perform ent.refresh_spare_flag(v_part->>'part_no');
  end loop;
  select jsonb_build_object('plan',v_plan,'orders',jsonb_agg(to_jsonb(w)||jsonb_build_object('ref',w.id) order by w.asset)) into v_after
    from ent.work_orders w where scope_group=v_group;
  insert into ent.transactions(id,system,skill,ref,detail,asset,decision_id,option_id,requested_by,fingerprint,before,after)
    values('TX-'||upper(substr(md5(random()::text),1,16)),'sys:cmms',v_skill,v_first,'원문 정비 범위 '||(select string_agg(x->>'asset',', ' order by ord) from jsonb_array_elements(v_plan->'assets') with ordinality as p(x,ord))||' 오더 등록',
      p->>'asset',p->>'decision',p->>'option',p->>'by',v_fp,null,v_after) returning * into v_tx;
  return ent.tx_response(v_tx);
end $$;

