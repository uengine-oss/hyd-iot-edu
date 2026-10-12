-- Source policies and real scoped CMMS effects. No inventory/model/history facts are inserted.
alter table ent.pm_counters add column if not exists service_position integer check(service_position is null or service_position>=0);
alter table ent.work_orders add column if not exists scope_group text;
alter table ent.work_orders add column if not exists maintenance_plan jsonb;
alter table ent.work_orders add column if not exists package jsonb;
create table if not exists ent.pm_part_reservations(
  work_order text not null references ent.work_orders(id),part_no text not null references ent.parts(part_no),
  qty numeric not null check(qty>0),released_at timestamptz,primary key(work_order,part_no));
alter table ent.pm_part_reservations add column if not exists stock_effect text not null default 'reserve' check(stock_effect in('reserve','issue'));
alter table ent.pm_part_reservations enable row level security;
grant select on ent.pm_part_reservations to service_role,hyd_enterprise_reader,anon,authenticated;
grant insert,update on ent.pm_part_reservations to service_role;
drop policy if exists pm_reservation_reader on ent.pm_part_reservations;
create policy pm_reservation_reader on ent.pm_part_reservations for select to hyd_enterprise_reader,anon,authenticated using(true);

create or replace function ent.pm_scope_row(p_asset text) returns jsonb language sql stable as $$
  select to_jsonb(v)||jsonb_build_object('service_position',c.service_position,'pm_cycle',c.cycle,
    'package_semantics','base_interval_configuration','configured_base_package',v.package,
    'selected_service',(select package from ent.work_orders where id=c.plan_wo and maintenance_plan is not null),
    'existing_pm_order',(select to_jsonb(w)||jsonb_build_object('reserved_parts',
      coalesce((select jsonb_agg(jsonb_build_object('part_no',r.part_no,'qty',r.qty)) from ent.pm_part_reservations r
        where r.work_order=w.id and r.released_at is null and r.stock_effect='reserve'),'[]'::jsonb))
      from ent.work_orders w where w.id=c.plan_wo and w.asset=c.asset))
  from ent.pm_status v join ent.pm_counters c on c.asset=v.asset where v.asset=p_asset;
$$;
create or replace function ent.pm_status_read(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system','CMMS',
    'facts',(select ent.pm_scope_row(v.asset) from ent.pm_status v where p_asset is null or v.asset=p_asset order by v.asset limit 1),
    'records',coalesce((select jsonb_agg(ent.pm_scope_row(v.asset) order by v.asset) from ent.pm_status v where p_asset is null or v.asset=p_asset),'[]'::jsonb),
    'log',coalesce((select jsonb_agg(to_jsonb(l) order by l.id desc) from
      (select * from ent.pm_counter_log where p_asset is null or asset=p_asset order by id desc limit 20) l),'[]'::jsonb),
    'settings',(select to_jsonb(s)-'id' from ent.pm_settings s),'as_of',now());
$$;

create or replace function ent.pm_scope_check(p_plan jsonb,p_asset text,p_create boolean) returns void language plpgsql as $$
declare
  v_member jsonb;v_policy jsonb:=p_plan->'policy';v_contract_package jsonb;v_part jsonb;v_total jsonb;
  v_pm ent.pm_counters;v_stock ent.spare_stock;v_row jsonb;v_expected jsonb;
  v_interval numeric;v_tolerance numeric;v_previous numeric;v_position integer;v_period numeric;v_hours numeric;
  v_needed jsonb:='{}'::jsonb;v_crew numeric;v_prefix text;v_count integer;v_code text;v_peer text;v_peers text[];
begin
  if jsonb_typeof(p_plan) is distinct from 'object' or jsonb_typeof(v_policy) is distinct from 'object'
     or coalesce(p_plan->>'source_id','')='' or v_policy->'anchor'->>'source_id' is distinct from p_plan->>'source_id'
     or v_policy->'model_anchor'->>'source_id' is distinct from p_plan->>'source_id'
     or v_policy->>'scope' is distinct from p_plan->>'scope' then
    raise exception 'INVALID: reviewed source maintenance policy missing' using errcode='22023';
  end if;
  if p_plan->>'stock_effect' is distinct from v_policy->>'stock_effect'
     or (p_create and p_plan->>'stock_effect' not in ('reserve','issue'))
     or (not p_create and p_plan->>'stock_effect' is distinct from 'preserve') then
    raise exception 'INVALID: explicit source reservation/issue/preservation effect required' using errcode='22023';end if;
  v_interval:=(v_policy->>'interval_h')::numeric;v_tolerance:=(v_policy->>'tolerance_pct')::numeric;
  if v_interval<=0 or v_tolerance<0 or v_tolerance>=100 then raise exception 'INVALID: source PM interval' using errcode='22023'; end if;
  v_count:=jsonb_array_length(p_plan->'assets');
  if v_count <> (case when p_plan->>'scope'='bundle' then 2 else 1 end)
     or (select count(distinct x->>'asset') from jsonb_array_elements(p_plan->'assets') x)<>v_count
     or p_plan->'assets'->0->>'asset' is distinct from p_asset then
    raise exception 'INVALID: actual single or two-asset maintenance scope required' using errcode='22023';
  end if;
  if (select count(*) from ent.assets a where (v_policy->'model_assets') ? a.code)<>jsonb_array_length(v_policy->'model_assets') then
    raise exception 'INVALID: source model roster does not match actual assets' using errcode='22023';
  end if;
  -- Stable global lock order. Every verification completes before any write.
  perform 1 from ent.pm_counters c where c.asset in(select x->>'asset' from jsonb_array_elements(p_plan->'assets') x) order by c.asset for update;
  perform 1 from ent.spare_stock s where s.part_no in(select x->>'part_no' from jsonb_array_elements(p_plan->'parts_totals') x) order by s.part_no for update;
  if v_count=2 then
    select array_agg(v.asset order by v.asset) into v_peers from ent.pm_status v
      where v.asset<>p_asset and (v_policy->'model_assets') ? v.asset
        and v.pm_since_h>=v_interval*(1-v_tolerance/100)
        and v.night_window_at=(p_plan->'window'->>'starts_at')::timestamptz;
    if array_length(v_peers,1) is distinct from 1 then
      raise exception 'INVALID: actual eligible source peer missing or ambiguous' using errcode='22023';end if;
    v_peer:=v_peers[1];
  end if;
  for v_member in select x from jsonb_array_elements(p_plan->'assets') x loop
    v_code:=v_member->>'asset';
    if not (v_policy->'model_assets') ? v_code or (v_code<>p_asset and v_code is distinct from v_peer) then
      raise exception 'INVALID: peer is not actual same-source-model maintenance peer' using errcode='22023';
    end if;
    select * into v_pm from ent.pm_counters where asset=v_code;
    if not found then raise exception 'INVALID: actual PM counter missing' using errcode='22023'; end if;
    v_row:=ent.pm_scope_row(v_code);
    v_expected:=jsonb_build_object('cycle',v_pm.cycle,'pm_since_h',v_pm.since_pm_h,'pm_total_h',v_pm.total_h,
      'pm_planned_wo',v_pm.plan_wo,'service_position',v_pm.service_position);
    if v_expected is distinct from v_member->'expected_counter' or (p_create and v_pm.plan_wo is not null)
       or (v_row->>'pm_interval_h')::numeric is distinct from v_interval
       or (v_row->>'pm_tolerance_pct')::numeric is distinct from v_tolerance
       or v_pm.since_pm_h<v_interval*(1-v_tolerance/100) then
      raise exception 'INVALID: actual PM scope/counter/policy changed or peer below lower hours' using errcode='22023';
    end if;
    if coalesce((p_plan->'window'->>'immediate')::boolean,false) then
      if v_count<>1 then raise exception 'INVALID: bundle requires common planned window' using errcode='22023'; end if;
      v_hours:=v_pm.since_pm_h;
    else
      v_prefix:=case when p_plan->'window'->>'basis'='hours_at_following_window' then 'following' else 'night' end;
      if coalesce(v_member->'window'->>'id','')='' or v_member->'window'->>'id' is distinct from v_row->>(v_prefix||'_window_id')
         or (v_member->'window'->>'starts_at')::timestamptz is distinct from (v_row->>(v_prefix||'_window_at'))::timestamptz
         or (p_plan->'window'->>'starts_at')::timestamptz is distinct from (v_row->>(v_prefix||'_window_at'))::timestamptz then
        raise exception 'INVALID: actual common maintenance window changed or missing' using errcode='22023';
      end if;
      v_hours:=(v_row->>(case when v_prefix='following' then 'hours_at_following_window' else 'hours_at_next_window' end))::numeric;
    end if;
    if v_hours is null or v_hours>v_interval*(1+v_tolerance/100) then
      raise exception 'INVALID: target hours beyond source maintenance deadline' using errcode='22023';
    end if;
    v_previous:=v_pm.total_h-v_pm.since_pm_h;
    if v_previous<0 then raise exception 'INVALID: total and service hours inconsistent' using errcode='22023'; end if;
    if v_pm.service_position is not null then v_position:=v_pm.service_position+1;
    elsif mod(v_previous,v_interval)=0 then v_position:=(v_previous/v_interval)::integer+1;
    else raise exception 'INVALID: actual prior service position unavailable' using errcode='22023'; end if;
    select x into v_contract_package from jsonb_array_elements(v_policy->'packages') x
      where mod(v_position::numeric,(x->>'interval_h')::numeric/v_interval)=0 order by (x->>'interval_h')::numeric desc limit 1;
    v_period:=(v_contract_package->>'interval_h')::numeric;
    if v_period is null or (v_member->'service'->>'service_position')::integer is distinct from v_position
       or (v_member->'service'->>'next_due_total_h')::numeric is distinct from v_previous+v_interval
       or (v_member->'service'->>'package_interval_h')::numeric is distinct from v_period
       or v_member->'service'->>'package_sop' is distinct from v_contract_package->>'sop'
       or jsonb_array_length(v_member->'parts')<>jsonb_array_length(v_contract_package->'parts') then
      raise exception 'INVALID: actual source service cadence or package differs' using errcode='22023';
    end if;
    if v_member->'service' is distinct from jsonb_build_object('interval_h',v_interval,'since_pm_h',v_pm.since_pm_h,
       'total_h',v_pm.total_h,'last_service_total_h',v_previous,'next_due_total_h',v_previous+v_interval,
       'service_position',v_position,'package_interval_h',v_period,'package_sop',v_contract_package->>'sop',
       'package_name',v_contract_package->>'name') then
      raise exception 'INVALID: actual source package display and service evidence differ' using errcode='22023';end if;
    for v_part in select x from jsonb_array_elements(v_contract_package->'parts') x loop
      select * into v_stock from ent.spare_stock where part_no=v_part->>'part_no';
      if not found or v_part->>'qty' is null or (v_part->>'qty')::numeric<=0 then
        raise exception 'INVALID: source package part quantity or actual stock unknown' using errcode='22023';
      end if;
      if not exists(select 1 from jsonb_array_elements(v_member->'parts') x where x->>'part_no'=v_stock.part_no
         and (x->>'qty')::numeric=(v_part->>'qty')::numeric and (x->>'available')::numeric=v_stock.on_hand-v_stock.reserved+v_stock.on_order
         and x->'verified'='true'::jsonb) then
        raise exception 'INVALID: source package part evidence changed' using errcode='22023';
      end if;
      if p_plan->>'stock_effect'='preserve' and not exists(select 1 from ent.pm_part_reservations r
         where r.work_order=v_pm.plan_wo and r.part_no=v_stock.part_no and r.qty>=(v_part->>'qty')::numeric
           and r.released_at is null and r.stock_effect='reserve'
           and exists(select 1 from jsonb_array_elements(v_member->'parts') x
             where x->>'part_no'=r.part_no and (x->>'owned_qty')::numeric=r.qty)) then
        raise exception 'INVALID: actual owned PM order part allocation missing' using errcode='22023';end if;
      v_needed:=jsonb_set(v_needed,array[v_stock.part_no],to_jsonb(coalesce((v_needed->>v_stock.part_no)::numeric,0)+(v_part->>'qty')::numeric));
    end loop;
    v_crew:=least(v_crew,(v_row->>'pm_crew_available')::numeric);
    if v_row->>'pm_crew_available' is null then raise exception 'INVALID: actual maintenance staffing unknown' using errcode='22023'; end if;
  end loop;
  if (select count(*) from jsonb_object_keys(v_needed))<>jsonb_array_length(p_plan->'parts_totals') then
    raise exception 'INVALID: aggregate source parts scope differs' using errcode='22023';
  end if;
  for v_total in select x from jsonb_array_elements(p_plan->'parts_totals') x loop
    select * into v_stock from ent.spare_stock where part_no=v_total->>'part_no';
    if not found or (v_total->>'qty')::numeric is distinct from (v_needed->>v_stock.part_no)::numeric
       or (v_total->>'available')::numeric is distinct from v_stock.on_hand-v_stock.reserved+v_stock.on_order
       or (p_plan->>'stock_effect'='reserve' and v_stock.on_hand-v_stock.reserved+v_stock.on_order<(v_total->>'qty')::numeric)
       or (p_plan->>'stock_effect'='issue' and v_stock.on_hand-v_stock.reserved<(v_total->>'qty')::numeric) then
      raise exception 'INVALID: aggregate actual source parts unavailable' using errcode='22023';
    end if;
  end loop;
  if (p_plan->'staffing'->>'available')::numeric is distinct from v_crew or p_plan->'staffing'->'confirmed' is distinct from 'false'::jsonb
     or (v_count=2 and ((p_plan->'staffing'->>'required')::numeric is distinct from 4
       or (p_plan->'staffing'->>'shortfall')::numeric is distinct from greatest(4-v_crew,0)
       or (p_plan->'staffing'->>'arrangement_required')::boolean is distinct from (v_crew<4))) then
    raise exception 'INVALID: source staffing scope or shortage obligation differs' using errcode='22023';
  end if;
end $$;

do $$ begin
  if to_regprocedure('ent.exec_skill_before_pm56(jsonb)') is null then alter function ent.exec_skill(jsonb) rename to exec_skill_before_pm56; end if;
  if to_regprocedure('ent.exec_compensation_before_pm56(jsonb)') is null then alter function ent.exec_compensation(jsonb) rename to exec_compensation_before_pm56; end if;
end $$;
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
    values('TX-'||upper(substr(md5(random()::text),1,16)),'sys:cmms',v_skill,v_first,'Source-scoped maintenance orders registered',
      p->>'asset',p->>'decision',p->>'option',p->>'by',v_fp,null,v_after) returning * into v_tx;
  return ent.tx_response(v_tx);
end $$;

create or replace function ent.exec_compensation(p jsonb) returns jsonb language plpgsql as $$
declare
  v_ref text:=p->'params'->>'ref';v_forward ent.transactions;v_prior ent.transactions;v_tx ent.transactions;
  v_order ent.work_orders;v_counter ent.pm_counters;v_group text;v_before jsonb;v_after jsonb;v_part record;
  v_fp text:=md5(jsonb_build_object('decision',p->'decision','option',p->'option','skill',p->'skill','asset',p->'asset','params',p->'params')::text);
begin
  if p->>'skill'<>'skill:cancel-maintenance-scoped' then
    if p->>'skill'='skill:cancel-work-order' and exists(select 1 from ent.work_orders where id=v_ref and scope_group is not null) then
      raise exception 'INVALID: source scoped orders require whole-group compensation' using errcode='22023';
    end if;
    return ent.exec_compensation_before_pm56(p);
  end if;
  if coalesce(p->>'decision','')='' or coalesce(p->>'by','')='' or coalesce(p->>'compensates','')='' then
    raise exception 'INVALID: reviewed actual original scope transaction required' using errcode='22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('ent.pm_scope.cancel:'||v_ref,0));
  select * into v_prior from ent.transactions where decision_id=p->>'decision' and skill=p->>'skill' and ref=v_ref and compensates is not null;
  if found then
    if v_prior.fingerprint is distinct from v_fp then raise exception 'idempotency conflict' using errcode='23505';end if;
    return ent.tx_response(v_prior);
  end if;
  select * into v_forward from ent.transactions where id=p->>'compensates' and ref=v_ref and skill='skill:schedule-maintenance-scoped';
  if not found then raise exception 'INVALID: original scope transaction missing' using errcode='22023';end if;
  select scope_group into v_group from ent.work_orders where id=v_ref;
  if v_group is null then raise exception 'INVALID: original order group missing' using errcode='22023';end if;
  if v_forward.after->'plan'->>'stock_effect'='issue' then
    raise exception 'INVALID: actually issued parts need verified return before full rollback' using errcode='22023';end if;
  perform 1 from ent.pm_counters c where c.asset in(select asset from ent.work_orders where scope_group=v_group) order by c.asset for update;
  perform 1 from ent.work_orders w where scope_group=v_group order by w.asset for update;
  perform 1 from ent.spare_stock s where s.part_no in(select part_no from ent.pm_part_reservations where work_order in(select id from ent.work_orders where scope_group=v_group)) order by s.part_no for update;
  if (select count(*) from ent.work_orders where scope_group=v_group)<>jsonb_array_length(v_forward.after->'orders') then
    raise exception 'INVALID: original scope order group changed' using errcode='22023';end if;
  for v_order in select * from ent.work_orders where scope_group=v_group order by asset loop
    select * into v_counter from ent.pm_counters where asset=v_order.asset;
    if v_order.status<>'배정됨' or v_counter.plan_wo is distinct from v_order.id
       or not exists(select 1 from jsonb_array_elements(v_forward.after->'plan'->'assets') x
         where x->>'asset'=v_order.asset and (x->'expected_counter'->>'cycle')::integer=v_counter.cycle)
       or not exists(select 1 from jsonb_array_elements(v_forward.after->'orders') x where x=to_jsonb(v_order)||jsonb_build_object('ref',v_order.id))
       or exists(select 1 from ent.pm_part_reservations where work_order=v_order.id and released_at is not null)
       or (select count(*) from ent.pm_part_reservations where work_order=v_order.id) is distinct from
          (select jsonb_array_length(x->'parts') from jsonb_array_elements(v_forward.after->'plan'->'assets') x where x->>'asset'=v_order.asset)
       or exists(select 1 from jsonb_array_elements(v_forward.after->'plan'->'assets') x,
           lateral jsonb_array_elements(x->'parts') required where x->>'asset'=v_order.asset and not exists
           (select 1 from ent.pm_part_reservations r where r.work_order=v_order.id and r.part_no=required->>'part_no'
             and r.qty=(required->>'qty')::numeric and r.released_at is null)) then
      raise exception 'INVALID: one scoped order advanced; whole cancellation requires review' using errcode='22023';end if;
  end loop;
  select jsonb_build_object('plan',v_forward.after->'plan','orders',jsonb_agg(to_jsonb(w)||jsonb_build_object('ref',w.id) order by w.asset)) into v_before
    from ent.work_orders w where scope_group=v_group;
  for v_part in select r.part_no,sum(r.qty) qty from ent.pm_part_reservations r join ent.work_orders w on w.id=r.work_order
     where w.scope_group=v_group and r.released_at is null group by r.part_no loop
    if not exists(select 1 from ent.spare_stock where part_no=v_part.part_no and reserved>=v_part.qty) then
      raise exception 'INVALID: actual scoped reservations changed' using errcode='22023';end if;
    update ent.spare_stock set reserved=reserved-v_part.qty,updated_at=now() where part_no=v_part.part_no;
    perform ent.refresh_spare_flag(v_part.part_no);
  end loop;
  update ent.work_orders set status='취소',cancelled_at=now() where scope_group=v_group;
  update ent.pm_part_reservations set released_at=now() where work_order in(select id from ent.work_orders where scope_group=v_group);
  update ent.pm_counters set plan_wo=null,plan_window=null,planned_at=null,updated_at=now() where plan_wo in(select id from ent.work_orders where scope_group=v_group);
  select jsonb_build_object('plan',v_forward.after->'plan','orders',jsonb_agg(to_jsonb(w)||jsonb_build_object('ref',w.id) order by w.asset)) into v_after
    from ent.work_orders w where scope_group=v_group;
  insert into ent.transactions(id,system,skill,ref,detail,asset,decision_id,option_id,requested_by,fingerprint,compensates,before,after)
    values('TX-'||upper(substr(md5(random()::text),1,16)),'sys:cmms',p->>'skill',v_ref,'Entire source-scoped maintenance cancelled',
      p->>'asset',p->>'decision',p->>'option',p->>'by',v_fp,v_forward.id,v_before,v_after) returning * into v_tx;
  return ent.tx_response(v_tx);
end $$;
revoke execute on function ent.exec_skill(jsonb),ent.exec_skill_before_pm56(jsonb),ent.exec_compensation(jsonb),
  ent.exec_compensation_before_pm56(jsonb),ent.pm_scope_check(jsonb,text,boolean) from public,anon,authenticated;
grant execute on function ent.exec_skill(jsonb),ent.exec_skill_before_pm56(jsonb),ent.exec_compensation(jsonb),
  ent.exec_compensation_before_pm56(jsonb),ent.pm_scope_check(jsonb,text,boolean) to service_role;
grant execute on function ent.pm_status_read(text),ent.pm_scope_row(text) to anon,authenticated,hyd_enterprise_reader,service_role;
