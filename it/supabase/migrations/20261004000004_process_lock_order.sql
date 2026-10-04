-- Every work-item mutation locks its instance before the child row. The
-- todolist updated_at trigger also writes the instance, so child-first claims
-- can deadlock with atomic engine transitions (A021 actual Codex run).
create or replace function public.claim_process_workitems(
  p_consumer text, p_limit integer, p_tenant text, p_instance text,
  p_orch text, p_kind text
) returns setof public.todolist language plpgsql volatile as $$
begin
  if p_kind not in ('worker','engine') then raise exception 'invalid claim kind'; end if;
  if p_limit is null or p_limit < 1 then return; end if;
  return query
  with eligible as materialized (
    select w.id,w.proc_inst_id,w.start_date from public.todolist w
    where (p_tenant is null or w.tenant_id=p_tenant)
      and (p_instance is null or w.proc_inst_id=p_instance)
      and ((p_kind='worker' and w.status='IN_PROGRESS'
            and (p_orch is null or p_orch='' or w.agent_orch::text=p_orch)
            and ((w.agent_mode in ('DRAFT','COMPLETE') and w.draft is null and w.draft_status is null)
                 or w.draft_status='FB_REQUESTED'))
           or (p_kind='engine' and w.status='SUBMITTED' and w.consumer is null))
  ), parents as materialized (
    select i.proc_inst_id from public.bpm_proc_inst i
    where i.status='RUNNING' and not i.is_deleted
      and (p_tenant is null or i.tenant_id=p_tenant)
      and exists(select 1 from eligible e where e.proc_inst_id=i.proc_inst_id)
    order by i.start_date,i.proc_inst_id limit p_limit for update of i skip locked
  ), picked as materialized (
    select w.id from public.todolist w join parents p using(proc_inst_id)
    join eligible e on e.id=w.id
    where ((p_kind='worker' and w.status='IN_PROGRESS'
            and ((w.agent_mode in ('DRAFT','COMPLETE') and w.draft is null and w.draft_status is null)
                 or w.draft_status='FB_REQUESTED'))
           or (p_kind='engine' and w.status='SUBMITTED' and w.consumer is null))
    order by w.start_date,w.id limit p_limit for update of w skip locked
  )
  update public.todolist w set consumer=p_consumer,
    draft_status=case when p_kind='worker' then 'STARTED'::public.draft_status else w.draft_status end
  from picked where w.id=picked.id returning w.*;
end $$;
revoke all on function public.claim_process_workitems(text,integer,text,text,text,text) from public;
grant execute on function public.claim_process_workitems(text,integer,text,text,text,text) to service_role,authenticated;

create or replace function public.fetch_pending_task(p_agent_orch text,p_consumer text,p_limit integer,p_env text)
returns setof public.todolist language sql volatile as $$
  select * from public.claim_process_workitems(p_consumer,p_limit,null,null,p_agent_orch,'worker');
$$;

create or replace function public.claim_submitted_workitems(p_consumer text,p_limit integer default 10)
returns setof public.todolist language sql volatile as $$
  select * from public.claim_process_workitems(p_consumer,p_limit,null,null,null,'engine');
$$;

create or replace function public.save_task_result(p_todo_id uuid,p_payload jsonb,p_final boolean)
returns void language plpgsql volatile as $$
declare v_mode text;
begin
  perform i.proc_inst_id from public.bpm_proc_inst i join public.todolist w using(proc_inst_id)
    where w.id=p_todo_id for update of i;
  select agent_mode into v_mode from public.todolist where id=p_todo_id;
  if p_final then
    if v_mode='COMPLETE' then
      update public.todolist set output=p_payload,status='SUBMITTED',draft_status='COMPLETED',consumer=null where id=p_todo_id;
    else
      update public.todolist set draft=p_payload,draft_status='COMPLETED',consumer=null where id=p_todo_id;
    end if;
  else
    update public.todolist set draft=p_payload where id=p_todo_id;
  end if;
end $$;

create or replace function public.cleanup_stale_consumers(p_minutes integer default 30)
returns integer language plpgsql volatile as $$
declare n integer;
begin
  with parents as materialized (
    select i.proc_inst_id from public.bpm_proc_inst i where exists(
      select 1 from public.todolist w where w.proc_inst_id=i.proc_inst_id
        and w.status='SUBMITTED' and w.consumer is not null
        and w.updated_at<now()-make_interval(mins=>p_minutes))
    order by i.proc_inst_id for update of i skip locked
  )
  update public.todolist w set consumer=null from parents p
    where w.proc_inst_id=p.proc_inst_id and w.status='SUBMITTED' and w.consumer is not null
      and w.updated_at<now()-make_interval(mins=>p_minutes);
  get diagnostics n=row_count;
  return n;
end $$;
