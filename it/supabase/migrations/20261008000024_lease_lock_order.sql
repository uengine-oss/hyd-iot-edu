-- A143 (remaining-sweep 12/36·708): every todolist write locks its bpm_proc_inst row first (migration 000004, DECISIONS 31),
-- because the todolist AFTER UPDATE trigger (trigger_update_bpm_proc_inst_updated_at) writes the parent row. renew_task_lease
-- (000018) and PgRepo.clear_task_lease updated todolist directly, so a worker renewing its lease while the engine held the
-- parent for a transition deadlocked (reproduced on an empty DB with migrations 1~23: `.evidence/a143/lease_lock_order.json`
-- before = "deadlock detected"). Same function body as 000018 plus the parent lock. Additive only (function replace + comments).
create or replace function public.renew_task_lease(p_todo_id uuid, p_consumer text, p_seconds integer default 120)
returns boolean language plpgsql volatile as $$
declare n integer;
begin
  -- parent first, child second — the same order as claim/save/release/sweep; waits behind an engine transition instead of
  -- crossing it (the transition's child UPDATE would otherwise wait on this row while this trigger waits on its parent)
  perform i.proc_inst_id from public.bpm_proc_inst i join public.todolist w using(proc_inst_id)
    where w.id=p_todo_id for update of i;
  update public.todolist set lease_until=now()+make_interval(secs=>p_seconds)
    where id=p_todo_id and consumer=p_consumer and status='IN_PROGRESS' and draft_status='STARTED';
  get diagnostics n=row_count;
  return n>0;
end $$;
comment on function public.renew_task_lease(uuid,text,integer) is
  'A097/A143: running worker renews its claim lease; locks the parent instance first (lock order of migration 000004)';

-- A143 (remaining-sweep 36·714): the draft column carries more than the DRAFT-mode draft
comment on column public.todolist.draft is
  'agent_mode=DRAFT: the agent''s draft awaiting a person''s submit; also the worker''s _human_request (HUMAN_ASKED question + cliagents_session_id) and _deferral (task_deferred) records';
