-- A114 (A113 r14-summary A1; process-gpt-agent-sdk e4728a2 function.sql:102-105 · process-gpt-infra-docker 9e85485
-- init.sql:2821-2824): claim_count counts only RECLAIMS of an expired lease. A fresh claim and a re-claim after a person's
-- answer (FB_REQUESTED) start again at 1. Before this, every worker claim added 1, so a task whose agent asked a person
-- twice reached the cap and, if its worker then died once, was marked FAILED instead of reclaimed (reproduced on
-- MemoryRepo: 3 answers → claim_count 4 → one dead worker → FAILED). Same function as 018 except the claim_count line.
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
    -- reclaim (old draft_status STARTED) accumulates; a fresh claim or a re-claim after a person's answer starts at 1
    claim_count=case when p_kind='worker' and w.draft_status='STARTED' then w.claim_count+1
                     when p_kind='worker' then 1 else w.claim_count end,
    log=case when p_kind='worker' and w.draft_status='STARTED'
             then coalesce(w.log,'')||'[Lease expired: reclaimed by '||p_consumer||' (claim '||(w.claim_count+1)||')] ' else w.log end
  from picked where w.id=picked.id returning w.*;
end $$;
comment on column public.todolist.claim_count is 'A097/A114: reclaims of an expired lease (fresh or post-answer claim = 1; max 3, then FAILED by expire_worker_leases)';
