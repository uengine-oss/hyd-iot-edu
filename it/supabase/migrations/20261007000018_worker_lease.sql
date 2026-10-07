-- A097 (R13 C07, process-gpt-agent-sdk e4728a2 function.sql lease_until/claim_count/max_claims · lease.py 120 s/30 s):
-- a worker claim is a lease. A worker that dies mid-run leaves draft_status='STARTED' with a consumer that never comes
-- back; before this the row stayed that way until a person closed it. Now the claim carries lease_until, the running
-- worker renews it every 30 s, another worker may reclaim the row once the lease expired (claim_count < 3), and the
-- engine's sweep marks a row FAILED after the third expired lease so the usual close path applies. Additive only.
alter table public.todolist add column if not exists lease_until timestamptz;
alter table public.todolist add column if not exists claim_count integer not null default 0;
comment on column public.todolist.lease_until is 'A097: worker claim lease; expired + STARTED = orphan (reclaimable while claim_count < 3)';
comment on column public.todolist.claim_count is 'A097: how many worker claims this row had (max 3, then FAILED by expire_worker_leases)';
-- rows already claimed before this migration get a lease from now: a live worker (new code) renews it, a dead one's expires
update public.todolist set lease_until=now()+interval '120 seconds', claim_count=greatest(claim_count,1)
  where status='IN_PROGRESS' and draft_status='STARTED' and lease_until is null;

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
                 or w.draft_status='FB_REQUESTED'
                 or (w.draft_status='STARTED' and w.lease_until is not null and w.lease_until < now() and w.claim_count < 3)))
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
                 or w.draft_status='FB_REQUESTED'
                 or (w.draft_status='STARTED' and w.lease_until is not null and w.lease_until < now() and w.claim_count < 3)))
           or (p_kind='engine' and w.status='SUBMITTED' and w.consumer is null))
    order by w.start_date,w.id limit p_limit for update of w skip locked
  )
  update public.todolist w set consumer=p_consumer,
    draft_status=case when p_kind='worker' then 'STARTED'::public.draft_status else w.draft_status end,
    lease_until=case when p_kind='worker' then now()+interval '120 seconds' else w.lease_until end,
    claim_count=case when p_kind='worker' then w.claim_count+1 else w.claim_count end,
    log=case when p_kind='worker' and w.draft_status='STARTED'
             then coalesce(w.log,'')||'[Lease expired: reclaimed by '||p_consumer||' (claim '||(w.claim_count+1)||')] ' else w.log end
  from picked where w.id=picked.id returning w.*;
end $$;

-- the running worker renews its lease; false = the lease is no longer this worker's (reclaimed or finished elsewhere)
create or replace function public.renew_task_lease(p_todo_id uuid, p_consumer text, p_seconds integer default 120)
returns boolean language plpgsql volatile as $$
declare n integer;
begin
  update public.todolist set lease_until=now()+make_interval(secs=>p_seconds)
    where id=p_todo_id and consumer=p_consumer and status='IN_PROGRESS' and draft_status='STARTED';
  get diagnostics n=row_count;
  return n>0;
end $$;

-- the engine's sweep: an orphan that already used its claims becomes FAILED (the person's close path, A082)
create or replace function public.expire_worker_leases(p_max_claims integer default 3)
returns integer language plpgsql volatile as $$
declare n integer;
begin
  with parents as materialized (
    select i.proc_inst_id from public.bpm_proc_inst i where exists(
      select 1 from public.todolist w where w.proc_inst_id=i.proc_inst_id
        and w.status='IN_PROGRESS' and w.draft_status='STARTED' and w.lease_until is not null and w.lease_until<now()
        and w.claim_count>=p_max_claims)
    order by i.proc_inst_id for update of i skip locked
  )
  update public.todolist w set draft_status='FAILED', consumer=null,
      log=coalesce(w.log,'')||'[Lease expired after '||w.claim_count||' claims: run marked FAILED] '
    from parents p
    where w.proc_inst_id=p.proc_inst_id and w.status='IN_PROGRESS' and w.draft_status='STARTED'
      and w.lease_until is not null and w.lease_until<now() and w.claim_count>=p_max_claims;
  get diagnostics n=row_count;
  return n;
end $$;
revoke all on function public.renew_task_lease(uuid,text,integer) from public;
grant execute on function public.renew_task_lease(uuid,text,integer) to service_role,authenticated;
revoke all on function public.expire_worker_leases(integer) from public;
grant execute on function public.expire_worker_leases(integer) to service_role,authenticated;
