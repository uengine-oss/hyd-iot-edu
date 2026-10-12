-- Existing PM order scheduling capability. No example orders or business facts are inserted.
do $$ begin
  if to_regprocedure('ent.exec_skill_before_pm54(jsonb)') is null then
    alter function ent.exec_skill(jsonb) rename to exec_skill_before_pm54;
  end if;
end $$;

create or replace function ent.pm_status_read(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system','CMMS',
    'facts',(select to_jsonb(v) || jsonb_build_object('pm_cycle',v.cycle,
       'existing_pm_order',(select to_jsonb(w) from ent.work_orders w where w.id=v.pm_planned_wo and w.asset=v.asset))
       from ent.pm_status v where v.asset=p_asset or p_asset is null order by v.asset limit 1),
    'records',coalesce((select jsonb_agg(to_jsonb(v) order by v.asset) from ent.pm_status v where v.asset=p_asset or p_asset is null),'[]'::jsonb),
    'log',coalesce((select jsonb_agg(to_jsonb(l) order by l.id desc) from
       (select * from ent.pm_counter_log where asset=p_asset or p_asset is null order by id desc limit 20) l),'[]'::jsonb),
    'settings',(select to_jsonb(s)-'id' from ent.pm_settings s),'as_of',now());
$$;

create or replace function ent.exec_skill(p jsonb) returns jsonb language plpgsql as $$
declare
  v_skill text := p->>'skill'; v_params jsonb := p->'params';
  v_asset text := p->>'asset'; v_decision text := p->>'decision';
  v_wo ent.work_orders; v_pm ent.pm_counters; v_status record; v_window record;
  v_prior ent.transactions; v_tx ent.transactions; v_before jsonb; v_after jsonb;
  v_fp text := md5(jsonb_build_object('decision',p->'decision','option',p->'option','skill',p->'skill','asset',p->'asset','params',p->'params')::text);
begin
  if v_skill <> 'skill:reschedule-maintenance' then return ent.exec_skill_before_pm54(p); end if;
  if coalesce(v_decision,'')='' or coalesce(p->>'by','')='' or coalesce(p->>'option','')='' or coalesce(v_params->>'ref','')=''
     or coalesce(v_params->>'window_id','')='' or jsonb_typeof(v_params->'expected_order') is distinct from 'object' then
    raise exception 'INVALID: reschedule requires approval, existing order snapshot and exact target window' using errcode='22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('ent.exec_skill:'||v_decision||':'||v_skill,0));
  select * into v_prior from ent.transactions where decision_id=v_decision and skill=v_skill and compensates is null;
  if found then
    if v_prior.fingerprint is distinct from v_fp then raise exception 'idempotency conflict' using errcode='23505'; end if;
    return ent.tx_response(v_prior);
  end if;
  select * into v_pm from ent.pm_counters where asset=v_asset for update;
  if not found or v_pm.plan_wo is distinct from v_params->>'ref' or v_pm.cycle is distinct from (v_params->>'cycle')::integer then
    raise exception 'INVALID: existing order is not this PM cycle plan' using errcode='22023';
  end if;
  select * into v_wo from ent.work_orders where id=v_pm.plan_wo and asset=v_asset for update;
  if not found or v_wo.status <> '배정됨' or v_wo.completed_at is not null or to_jsonb(v_wo) is distinct from v_params->'expected_order' then
    raise exception 'INVALID: approved existing order changed or cannot be rescheduled' using errcode='22023';
  end if;
  select * into v_status from ent.pm_status where asset=v_asset;
  if v_status.following_window_id is distinct from v_params->>'window_id'
     or v_status.hours_at_following_window is null
     or v_status.hours_at_following_window > v_status.pm_interval_h*(1+v_status.pm_tolerance_pct/100) then
    raise exception 'INVALID: following maintenance window unknown or beyond PM deadline' using errcode='22023';
  end if;
  select * into v_window from ent.next_maintenance_windows(v_asset,14) where id=v_params->>'window_id';
  if not found then raise exception 'INVALID: target maintenance window missing' using errcode='22023'; end if;
  v_before := to_jsonb(v_wo);
  update ent.work_orders set window_id=v_window.id,window_starts_at=v_window.starts_at,window_label=v_window.label where id=v_wo.id;
  update ent.pm_counters set plan_window=v_window.label,planned_at=now(),updated_at=now() where asset=v_asset;
  select to_jsonb(w) into v_after from ent.work_orders w where id=v_wo.id;
  insert into ent.transactions(id,system,skill,ref,detail,asset,decision_id,option_id,requested_by,fingerprint,before,after)
    values('TX-'||upper(substr(md5(random()::text),1,12)),'sys:cmms',v_skill,v_wo.id,
      'PM order rescheduled to '||v_window.id,v_asset,v_decision,p->>'option',p->>'by',v_fp,v_before,v_after) returning * into v_tx;
  return ent.tx_response(v_tx);
end $$;
revoke execute on function ent.exec_skill(jsonb),ent.exec_skill_before_pm54(jsonb) from public,anon,authenticated;
grant execute on function ent.exec_skill(jsonb),ent.exec_skill_before_pm54(jsonb) to service_role;
grant execute on function ent.pm_status_read(text) to anon,authenticated,hyd_enterprise_reader;
